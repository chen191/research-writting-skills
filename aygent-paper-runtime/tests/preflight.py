"""Run in the staged image with --network none. Does not bypass production gates."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
sys.path.insert(0,'/opt/aygenta-paper-pdf')
sys.path.insert(0,'/skill/scripts')
import cli
import runtime_transport
from fixture import payload

root=Path('/workspace');report={'scope':'deterministic engineering preflight only; no LLM, review PASS, publish or ready index','profiles':[]}
for number,profile in enumerate(['generic-paper-v1','sjtu-paper-v1'],1):
    work=root/f'paper-00000000-0000-0000-0000-{number:012d}';work.mkdir(exist_ok=False)
    data=payload(profile)
    check=runtime_transport.call('check',{k:data[k] for k in ['markdown','sources','requirements']})
    assert check['passed'] and check['body_chinese_count_less_exact_repeats']>=400,check
    try:cli.validate(data)
    except ValueError as error:assert 'Independent final audit' in str(error)
    else:raise AssertionError('Missing actual independent review must block production render')
    directory=work/'engineering-layout';directory.mkdir()
    try:layout=cli.compile_pdf(data,directory)
    except Exception:
        log=directory/'latex-source/compile.log'
        print(log.read_text(errors='replace')[-3500:] if log.exists() else 'No compile log',file=sys.stderr);raise
    raw=(directory/'paper.pdf').read_bytes();pages=cli.inspect_pdf(raw)
    inspection=cli.contact_sheet(raw,directory)
    (directory/'pdf-inspection.json').write_text(json.dumps(inspection))
    shutil.copyfile(directory/'paper.pdf',work/'paper.pdf')
    digest=hashlib.sha256(raw).hexdigest()
    preview=runtime_transport.call('preview',{'sha256':digest,'pages':pages},work)
    assert len(preview['pages'])==pages and preview['pdf_sha256']==digest
    text=(directory/'latex-source/body.tex').read_text()
    assert r'\input{/etc/passwd}' not in text and r'\textbackslash{}input' in text
    assert not (work/'portal-result.json').exists() and not (work/'accepted-review.json').exists()
    report['profiles'].append({'profile':profile,'pages':pages,'sha256':digest,'sizeBytes':len(raw),
        'mechanical':True,'missingReviewBlocked':True,'allPreviewsRendered':True,'layout':layout['checks']})
(root/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
