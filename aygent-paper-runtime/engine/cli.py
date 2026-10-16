"""Task-local deterministic PDF commands. No network, listener, model or fake review."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import sys
sys.path.insert(0,str(Path(__file__).parent/'deps'))
# Limit the copied compiler libraries to this command and its TeX children.
private_lib=Path(__file__).parent/'toolchain-lib'
if private_lib.is_dir():os.environ['LD_LIBRARY_PATH']=str(private_lib)
from mechanics import check_request
from validation import validate
from latex_render import compile_pdf
from pdf_preview import contact_sheet, page_png

VERSION='runtime-local-v1'
WORKSPACE=Path('/workspace')
MAX_INPUT=384*1024
MAX_PDF=32*1024*1024

def task_folder(value):
    p=Path(value)
    if p.is_symlink():raise ValueError('Task directory cannot be a symlink')
    p=p.resolve()
    if p.parent!=WORKSPACE or not re.fullmatch(r'paper-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',p.name) or not p.is_dir():
        raise ValueError('Authorized /workspace/paper-UUID directory required')
    return p

def read_input():
    b=sys.stdin.buffer.read(MAX_INPUT+1)
    if not 0<len(b)<=MAX_INPUT:raise ValueError('Invalid input size')
    return json.loads(b)

def inspect_pdf(raw):
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    if not raw.startswith(b'%PDF-') or len(raw)>MAX_PDF:raise ValueError('Invalid PDF bytes/size')
    reader=PdfReader(io.BytesIO(raw))
    if not 1<=len(reader.pages)<=150:raise ValueError('Invalid PDF page count')
    if any(abs(float(p.mediabox.width)-595.28)>2 or abs(float(p.mediabox.height)-841.89)>2 for p in reader.pages):raise ValueError('Expected A4')
    doc=pdfium.PdfDocument(raw);length=0
    try:
        for i in range(len(doc)):
            p=doc[i];t=p.get_textpage()
            try:length+=len(t.get_text_range())
            finally:t.close();p.close()
    finally:doc.close()
    if length<300:raise ValueError('PDF text validation failed')
    return len(reader.pages)

def render(data,work):
    if data.get('template') not in ['generic-paper-v1','sjtu-paper-v1']:raise ValueError('Unsupported formal template; no fallback')
    data=validate(data)
    directory=work/'.paper-render';directory.mkdir(mode=0o700,exist_ok=False)
    (directory/'input.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    (directory/'sources-and-review.json').write_text(json.dumps(data['audit']|{'sources':data['sources']},ensure_ascii=False,indent=2),encoding='utf8')
    layout=compile_pdf(data,directory)
    raw=(directory/'paper.pdf').read_bytes();pages=inspect_pdf(raw)
    inspection=contact_sheet(raw,directory)
    (directory/'pdf-inspection.json').write_text(json.dumps(inspection,ensure_ascii=False),encoding='utf8')
    names=['paper.pdf','pdf-contact-sheet.png','pdf-inspection.json','layout-report.json','latex-source.zip']
    result={'status':'completed','execution':'xelatex_pdf','backend':VERSION,'template':layout['profile'],'pages':pages,
        'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'layout':layout,
        'files':{n:'.paper-render/'+n for n in names},'note':'Local deterministic compilation only; independent and visual reviews are separate gates.'}
    (directory/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

def previews(data,work):
    p=work/'paper.pdf'
    if p.is_symlink():raise ValueError('PDF cannot be a symlink')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=data.get('sha256'):raise ValueError('PDF hash mismatch')
    pages=inspect_pdf(raw)
    if pages!=data.get('pages'):raise ValueError('PDF page count mismatch')
    folder=work/'preview'
    if folder.is_symlink():raise ValueError('Preview directory cannot be a symlink')
    folder.mkdir(exist_ok=True);digests={}
    for number in range(1,pages+1):
        output=folder/(str(number)+'.png')
        if output.is_symlink():raise ValueError('Preview file cannot be a symlink')
        png=page_png(raw,number);output.write_bytes(png);digests[str(number)]=hashlib.sha256(png).hexdigest()
    return {'pdf_sha256':hashlib.sha256(raw).hexdigest(),'pages':digests,'backend':VERSION}

def doctor():
    for name in ['xelatex','latexmk']:
        if not shutil.which(name):raise RuntimeError('Required compiler tool missing: '+name)
    return {'backend':VERSION,'listener':False,'networkRequired':False,
        'python':sys.version.split()[0],'dependencies':{n:importlib.metadata.version(n) for n in ['markdown-it-py','pypdf','pypdfium2']},
        'tools':{n:bool(shutil.which(n)) for n in ['xelatex','latexmk']}}

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['doctor','check','render','preview']);p.add_argument('--workdir');a=p.parse_args()
    if a.action=='doctor':result=doctor()
    else:
        data=read_input()
        if a.action=='check':result=check_request(data)
        else:
            work=task_folder(a.workdir or '')
            result=render(data,work) if a.action=='render' else previews(data,work)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as error:
        # Do not log manuscripts, capability URLs or credentials.
        print(type(error).__name__+': '+str(error)[:400],file=sys.stderr);raise SystemExit(1)
