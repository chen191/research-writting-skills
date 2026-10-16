"""Build-only allowlisted transfer from the pinned Debian 13 compiler image.

Never copy /data, HTTP applications, the old Python interpreter or model SDKs.
The destination inherits the platform runtime, not the former service entrypoint.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import re
import shutil
import subprocess

ROOT=Path('/toolchain-root')
PRIVATE=ROOT/'opt/aygenta-paper-pdf'
ROOT.mkdir(exist_ok=False)
PRIVATE.mkdir(parents=True)

def copy(path):
    source=Path(path);target=ROOT/str(source).lstrip('/')
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.is_dir():shutil.copytree(source,target,symlinks=True,dirs_exist_ok=True)
    else:shutil.copy2(source,target,follow_symlinks=True)

# Preserve TeX package/formats and Perl modules from the same Debian release.
for path in ['/usr/share/texlive','/usr/share/texmf','/var/lib/texmf','/etc/texmf',
             '/usr/share/fonts','/usr/share/perl','/usr/share/perl5',
             '/usr/lib/x86_64-linux-gnu/perl','/usr/lib/x86_64-linux-gnu/perl5']:
    if Path(path).exists():copy(path)

binaries=['xetex','xelatex','xdvipdfmx','dvipdfmx','kpsewhich','latexmk','bibtex','makeindex']
report={'offline':True,'binaries':{},'libraries':{},'python':{}}
owned=set()
libraries=PRIVATE/'toolchain-lib';libraries.mkdir()
for name in binaries:
    path=Path('/usr/bin')/name
    if not path.exists():raise RuntimeError('Required compiler tool missing: '+name)
    copy(path);owned.add(str(path.resolve()))
    report['binaries'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.read_bytes().startswith(b'\x7fELF'):continue
    deps=subprocess.run(['ldd',str(path)],check=True,capture_output=True,text=True).stdout
    if 'not found' in deps:raise RuntimeError('Unresolved original compiler dependency')
    for match in re.finditer(r'(?:=>\s+|^\s*)(/\S+)\s+\(',deps,re.M):
        lib=Path(match.group(1));base=lib.name
        # Keep the destination runtime's glibc/loader; both images are Debian 13.
        if base.startswith(('ld-linux','libc.so','libm.so','libpthread.so','libdl.so','librt.so','libresolv.so')):continue
        dest=libraries/base
        digest=hashlib.sha256(lib.read_bytes()).hexdigest()
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:raise RuntimeError('Library collision')
        shutil.copy2(lib,dest,follow_symlinks=True);owned.add(str(lib.resolve()))
        report['libraries'][base]=digest

deps=PRIVATE/'deps';deps.mkdir()
for distribution,module in [('markdown-it-py','markdown_it'),('mdurl','mdurl'),('pypdf','pypdf'),
                            ('pypdfium2','pypdfium2'),('pypdfium2','pypdfium2_raw')]:
    dist=importlib.metadata.distribution(distribution)
    source=Path(dist.locate_file(module));shutil.copytree(source,deps/module,symlinks=True)
    info=next(p.parts[0] for p in dist.files if p.parts[0].endswith('.dist-info'))
    if not (deps/info).exists():shutil.copytree(dist.locate_file(info),deps/info,symlinks=True)
    report['python'][distribution]=dist.version

# Retain Debian copyright/license notices along with existing TeX package licenses.
packages=set()
for source in owned:
    found=subprocess.run(['dpkg-query','-S',source],capture_output=True,text=True)
    for line in found.stdout.splitlines():
        if ': /' in line:packages.add(line.split(': /',1)[0].split(':',1)[0])
packages.update(['perl','perl-base','perl-modules-5.40','texlive-base','texlive-binaries',
                 'texlive-xetex','texlive-lang-chinese','texlive-latex-extra',
                 'texlive-fonts-recommended','texlive-science','latexmk'])
for package in sorted(packages):
    license=Path('/usr/share/doc')/package/'copyright'
    if license.is_file():
        dest=PRIVATE/'third-party-notices'/package/'copyright';dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(license,dest,follow_symlinks=True)
(PRIVATE/'TOOLCHAIN.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps({'offline':True,'binaries':len(binaries),'libraries':len(report['libraries']),'python':report['python']}))
