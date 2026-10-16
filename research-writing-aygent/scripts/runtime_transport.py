"""Invoke the pinned local runtime compiler; HTTP fallback and background services are forbidden."""
from pathlib import Path
import json
import subprocess

PYTHON='/usr/bin/python3'
CLI='/opt/aygenta-paper-pdf/cli.py'
BACKEND='runtime-local-v1'
MAX_BYTES=64*1024*1024

def call(action,value,work=None):
    config=json.loads(Path(__file__).with_name('service-endpoints.json').read_bytes())
    if config!={'backend':BACKEND,'runtime_python':PYTHON,'runtime_cli':CLI}:raise ValueError('Local runtime compiler configuration mismatch; no service fallback')
    if action not in ['check','render','preview']:raise ValueError('Unsupported runtime action')
    if not Path(PYTHON).is_file() or not Path(CLI).is_file():raise RuntimeError('PDF compiler is missing from this runtime; select the paper runtime, no HTTP fallback')
    argv=[PYTHON,CLI,action]
    if work is not None:argv+=['--workdir',str(work)]
    try:
        # Full-page PNG generation is CPU-bound; preserve the existing 150-page limit.
        result=subprocess.run(argv,input=json.dumps(value,ensure_ascii=False).encode('utf8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=900 if action=='preview' else 240,start_new_session=True)
    except subprocess.TimeoutExpired:raise RuntimeError('Local compiler outcome unknown; do not replay render') from None
    if result.returncode:
        if work is not None:(work/'runtime-compiler-error.log').write_bytes(result.stderr[:8192])
        raise RuntimeError('Local compiler rejected request or failed; inspect runtime/task logs, do not replay render')
    if len(result.stdout)>MAX_BYTES:raise ValueError('Local compiler response exceeds limit')
    value=json.loads(result.stdout)
    if not isinstance(value,dict):raise ValueError('Invalid local compiler response')
    return value

def artifact(work,relative,name):
    if relative!='.paper-render/'+name or name not in ['paper.pdf','pdf-contact-sheet.png','pdf-inspection.json','layout-report.json','latex-source.zip']:
        raise ValueError('Untrusted local compiler artifact path')
    folder=work/'.paper-render';p=folder/name
    if folder.is_symlink() or p.is_symlink() or p.resolve().parent!=folder.resolve():raise ValueError('Compiler artifact escapes task directory')
    if not p.is_file() or p.stat().st_size>MAX_BYTES:raise ValueError('Missing or oversized local compiler artifact')
    return p.read_bytes()
