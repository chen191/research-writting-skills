"""Bounded Markdown -> selected manuscript profile. Never execute user TeX.

Only generated source is compiled. Unknown Markdown constructs fail closed rather
than disappearing. University affiliation and unprovided personal data are not inferred.
"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import unicodedata
import zipfile
from mechanics import CITATION, citation_ids, split_manuscript, front_matter, check as check_manuscript
from template_profiles import select as select_template, GENERIC

PROFILE = 'sjtu-paper-v1'
LEGACY_PROFILE = 'sjtu-master-test-v1'
TIMEOUT = 90
SHORT_MANUSCRIPT_CHARS = 6000


def tex(value):
    chars = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
             '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
             '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(chars.get(c, c) for c in value)


def plain(value, ids, citations=True):
    # Long machine identifiers can break without altering their visible characters.
    pattern = r'(\[S(?=\d)[^\]\n]*\]|[A-Za-z0-9]{40,})'
    result = []
    for part in re.split(pattern, value):
        if CITATION.fullmatch(part) and citations:
            found=citation_ids(part)
            if set(found)-ids: raise ValueError('Unknown citation id')
            result.append(r'\cite{' + ','.join(found) + '}')
        elif re.fullmatch('[A-Za-z0-9]{40,}', part):
            result.append(r'\seqsplit{' + tex(part) + '}')
        else:
            result.append(tex(part))
    return ''.join(result)


def inline(children, ids, citations=True):
    result = []
    for t in children or []:
        if t.type == 'text': result.append(plain(t.content, ids, citations))
        elif t.type in ('softbreak', 'hardbreak'): result.append(' ')
        elif t.type == 'strong_open': result.append(r'\textbf{')
        elif t.type == 'em_open': result.append(r'\emph{')
        elif t.type in ('strong_close', 'em_close'): result.append('}')
        elif t.type == 'code_inline': result.append(r'\texttt{' + tex(t.content) + '}')
        elif t.type == 'link_open':
            from urllib.parse import urlsplit
            url = t.attrGet('href') or ''
            u = urlsplit(url)
            if u.scheme != 'https' or not u.hostname or u.username or u.password:
                raise ValueError('LaTeX links must be HTTPS without credentials')
            result.append(r'\href{' + tex(url) + '}{')
        elif t.type == 'link_close': result.append('}')
        else: raise ValueError('Unsupported inline Markdown: ' + t.type)
    return ''.join(result)


def strip_number(title):
    # Strip only explicit numbering labels, not research names such as 3D or GPT-4.
    # Multiple labels ("2.1 （一）") may come from an already numbered manuscript.
    label = (r'^(?:第[零〇一二三四五六七八九十百千\d]+[章节]\s*[、.．：:]?\s*'
             r'|[（(][零〇一二三四五六七八九十百千\d]+[）)]\s*'
             r'|[一二三四五六七八九十百]+[、.．]\s*'
             r'|\d{1,3}(?:[.．]\d{1,3})*[.、．]?\s+)')
    clean = title.strip()
    while True:
        next_title = re.sub(label, '', clean, count=1)
        if next_title == clean or not next_title.strip():
            return clean
        clean = next_title.strip()


def table_tex(rows, ids, caption=None):
    if not rows or not 2 <= len(rows[0]) <= 10 or len(rows) > 61:
        raise ValueError('Tables support 2..10 columns and at most 60 data rows')
    n = len(rows[0])
    if any(len(row) != n for row in rows): raise ValueError('Uneven table columns')
    if any(len(''.join(t.content for t in cell)) > 600 for row in rows for cell in row):
        raise ValueError('Table cell too long; split it into prose or smaller rows')
    rendered = [[inline(cell, ids) for cell in row] for row in rows]
    # Keep ordinary comparisons in their original row/column orientation.
    # Only exceptionally wide tables retain the bounded, lossless fallback.
    if n > 6 and len(rows) <= 4:
        rendered = [list(row) for row in zip(*rendered)]
    elif n > 6:
        # Many wide records: lossless, readable two-column record cards.
        return '\n'.join(make_table([['字段', '内容']] + list(zip(rendered[0], row)),
                                    (caption+f'（记录{j}）') if caption else None)
                         for j,row in enumerate(rendered[1:],1))
    weights = None
    if 5 <= n <= 6:
        # Square-root weighting gives verbose columns space without starving
        # identifiers/headers. Measure visible text, not escaped TeX commands.
        def width(cell):
            value = ''.join(t.content for t in cell)
            return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in value)
        weights = [max(10, max(width(row[j]) for row in rows)) ** .5 for j in range(n)]
    return make_table(rendered,caption,weights)


def make_table(rows,caption=None,weights=None):
    n = len(rows[0])
    weights = weights or ([.20, .72] if n == 2 else [.18, .37, .37] if n == 3 else [1] * n)
    # Budget inter-column spacing explicitly; the complete table fits linewidth.
    # Floor rather than round ratios so floating-point rounding cannot overflow.
    ratios = [int(w / sum(weights) * 100000) / 100000 for w in weights]
    fmt = '@{}' + ''.join(r'>{\raggedright\arraybackslash}p{\dimexpr' + f'{w:.5f}' +
                          r'\paperTableWidth-' + f'{w * 2 * (n-1):.5f}' + r'\tabcolsep\relax}'
                          for w in ratios) + '@{}'
    head = ' & '.join(r'\textbf{' + c + '}' for c in rows[0]) + r' \\ \midrule'
    # Keep caption/header/first row together, not an arbitrary 68% of a page.
    # longtable remains free to paginate and repeat its header.
    reserve = r'\Needspace{8\baselineskip}'
    return '\n'.join([reserve, r'\begingroup\small',
                      # Paragraph columns change \linewidth while longtable builds
                      # its header. Freeze the outer width for every row/column.
                      r'\setlength{\paperTableWidth}{\linewidth}',
                      r'\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.3}',
                      r'\begin{longtable}{' + fmt + '}'] +
                     ([r'\caption{'+tex(caption)+r'}\\'] if caption else []) + [r'\toprule', head,
                      r'\endfirsthead', r'\toprule', head, r'\endhead',
                      r'\bottomrule\endfoot'] +
                     [' & '.join(row) + r' \\ \addlinespace[3pt]' for row in rows[1:]] +
                     [r'\end{longtable}', r'\endgroup'])


def blocks(tokens, ids):
    result, i, caption = [], 0, None
    while i < len(tokens):
        t = tokens[i]
        if t.type == 'table_open':
            rows, row = [], []
            i += 1
            while i < len(tokens) and tokens[i].type != 'table_close':
                if tokens[i].type == 'tr_open': row = []
                elif tokens[i].type == 'inline': row.append(tokens[i].children)
                elif tokens[i].type == 'tr_close': rows.append(row)
                i += 1
            result.append(table_tex(rows, ids, caption)); caption=None
        elif t.type == 'heading_open':
            level = int(t.tag[1:])
            cmd = {1:'chapter', 2:'chapter', 3:'section', 4:'subsection', 5:'subsubsection', 6:'paragraph'}[level]
            heading = strip_number(tokens[i+1].content)
            table_heading=re.match(r'^表\s*\d+(?:[.．-]\d+)?\s*[：:.．、-]?\s*(.+)',tokens[i+1].content)
            if table_heading and i+3<len(tokens) and tokens[i+3].type=='table_open':
                caption=table_heading[1]; i+=3; continue
            result.append('\\' + cmd + '{' + tex(heading) + '}\n')
            i += 2
        elif t.type == 'inline': result.append(inline(t.children, ids))
        elif t.type == 'paragraph_close': result.append('\n\n')
        elif t.type == 'paragraph_open':
            pass
        elif t.type in ('bullet_list_open','ordered_list_open'):
            result.append(r'\begin{' + ('itemize' if t.type == 'bullet_list_open' else 'enumerate') + '}')
        elif t.type in ('bullet_list_close','ordered_list_close'):
            result.append(r'\end{' + ('itemize' if t.type == 'bullet_list_close' else 'enumerate') + '}')
        elif t.type == 'list_item_open': result.append(r'\item ')
        elif t.type == 'list_item_close': pass
        elif t.type == 'blockquote_open': result.append(r'\begin{quote}')
        elif t.type == 'blockquote_close': result.append(r'\end{quote}')
        elif t.type in ('fence','code_block'):
            # No verbatim delimiter injection: each code line is fully escaped as text.
            result.append(r'\begin{quote}\small\ttfamily\raggedright' + '\n' +
                          '\n'.join(tex(line) + r'\par' for line in t.content.splitlines()) +
                          '\n' + r'\end{quote}')
        elif t.type == 'hr': result.append(r'\par\medskip\hrule\medskip')
        else: raise ValueError('Unsupported block Markdown: ' + t.type)
        i += 1
    return '\n'.join(result)


def prepare(data, path):
    from markdown_it import MarkdownIt
    profile, selection = select_template(data)
    md = MarkdownIt('commonmark', {'html':False, 'linkify':False}).enable('table')
    text = data['markdown']
    if any(ord(c) < 32 and c not in '\n\r\t' for c in text): raise ValueError('Invalid control character')
    ids = {s['id'] for s in data['sources']}
    body, refs = split_manuscript(text)
    if set(refs) != ids or any(not s.strip() for s in refs.values()):
        raise ValueError('Reference paragraphs must match sources')
    metadata,body=front_matter(body,data.get('front_matter'))
    tokens = md.parse(body)
    if not tokens: raise ValueError('Empty body')
    # This is a layout threshold, not the academic word-count gate. Exclude
    # bibliography/front metadata and whitespace; include abstract/table text.
    layout_chars = sum(len(re.sub(r'\s', '', t.content)) for t in tokens if t.type == 'inline')
    compact = layout_chars <= SHORT_MANUSCRIPT_CHARS
    front, main = [], []
    abstract_lang, i = None, 0
    while i < len(tokens):
        if tokens[i].type == 'heading_open' and tokens[i].tag in ('h1','h2'):
            title = tokens[i+1].content.strip()
            if title in ('摘要','中文摘要','Abstract','ABSTRACT','英文摘要'):
                if abstract_lang: front.append(r'\end{abstract}')
                abstract_lang = 'en' if title in ('Abstract','ABSTRACT','英文摘要') else 'zh'
                front.append(r'\begin{abstract}[' + abstract_lang + ']')
                i += 3
                continue
            if abstract_lang:
                front.append(r'\end{abstract}'); abstract_lang = None
        if abstract_lang and tokens[i].type == 'paragraph_open' and tokens[i+1].type == 'inline':
            raw = tokens[i+1].content
            clean = re.sub(r'\*+', '', raw)
            if re.match(r'^(关键词|Keywords)\s*[:：]', clean, re.I):
                # Preserve exact keywords as an abstract paragraph; no guessing metadata.
                front.append(blocks(tokens[i:i+3], ids)); i += 3; continue
        if abstract_lang:
            if tokens[i].type == 'heading_open': raise ValueError('Nested abstract headings unsupported')
            # Process one complete paragraph/list block by accumulation below.
            start = i
            if tokens[i].nesting == 1:
                depth = 1; i += 1
                while i < len(tokens) and depth:
                    depth += tokens[i].nesting; i += 1
                front.append(blocks(tokens[start:i], ids)); continue
            front.append(blocks([tokens[i]], ids))
        else: main.append(tokens[i])
        i += 1
    if abstract_lang: front.append(r'\end{abstract}')
    if not main: raise ValueError('Body chapters required')
    path.mkdir(parents=True, exist_ok=True)
    (path/'body.tex').write_text(blocks(main, ids), encoding='utf-8')
    abstract = '\n'.join(front)
    if profile['id'] != PROFILE:
        abstract = abstract.replace(r'\begin{abstract}[zh]', r'\chapter*{摘要}\addcontentsline{toc}{chapter}{摘要}')
        abstract = abstract.replace(r'\begin{abstract}[en]', r'\chapter*{Abstract}\addcontentsline{toc}{chapter}{Abstract}')
        abstract = abstract.replace(r'\end{abstract}', '')
    (path/'abstract.tex').write_text(abstract, encoding='utf-8')
    ref_lines = [r'\begin{thebibliography}{99}', r'\addcontentsline{toc}{chapter}{参考文献}']
    if profile['id'] == GENERIC:
        ref_lines.append(r'\raggedright')
    for sid, value in refs.items():
        # Preserve supplied bibliographic information instead of inventing authors or dates.
        ref_lines.append(r'\bibitem{' + sid + '}' + inline(md.parseInline(value)[0].children, ids, False))
    ref_lines.append(r'\end{thebibliography}')
    (path/'references.tex').write_text('\n'.join(ref_lines), encoding='utf-8')
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    main_tex = r'''% Generated from validated Markdown; raw user TeX is never evaluated.
\documentclass[type=master,oneside,openany,cjk-font=fandol]{sjtuthesis}
\sjtusetup{info={zh/title={TITLE},zh/subject={},zh/degree={},zh/author={AUTHOR},date={DATE}}}
\usepackage{booktabs,longtable,array,needspace,seqsplit}
\newlength{\paperTableWidth}
\usepackage{hyperref}
\hypersetup{hidelinks,pdfauthor={},pdftitle={TITLE}}
\setlength{\emergencystretch}{3em}
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\raggedbottom
\begin{document}
% Neutral cover: using typography does not imply institutional affiliation.
\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{0.17\textheight}
% Measure the actual font, then balance a wrapping title instead of leaving
% one or two characters on a final line. Metadata retains the unbroken title.
\newsavebox{\papertitlebox}
\sbox{\papertitlebox}{\LARGE\bfseries TITLE}
\newlength{\papertitlewidth}
\newcount\papertitlelines
\papertitlelines=1
\setlength{\papertitlewidth}{\wd\papertitlebox}
\loop\ifdim\papertitlewidth>\textwidth
  \advance\papertitlelines by 1
  \setlength{\papertitlewidth}{\wd\papertitlebox}
  \divide\papertitlewidth by \papertitlelines
\repeat
\ifnum\papertitlelines>1
  \addtolength{\papertitlewidth}{1em}
\fi
\ifdim\papertitlewidth>\textwidth
  \setlength{\papertitlewidth}{\textwidth}
\fi
\parbox{\papertitlewidth}{\centering\LARGE\bfseries TITLE\par}
\vspace{2cm}
COVERMETADATA
\vfill
{\large DATE\par}
\vspace*{1.5cm}
\end{titlepage}
\fancyhead[L]{论文}
\fancyhead[R]{\nouppercase{\leftmark}}
\frontmatter
\input{abstract}
\tableofcontents
\mainmatter
BODYLAYOUT
\input{body}
\backmatter
\ctexset{chapter/break=\clearpage}
\fancyhead[R]{\nouppercase{\leftmark}}
\input{references}
\end{document}
'''
    cover_title=data['title']
    if metadata.get('subtitle') and metadata['subtitle'] not in cover_title:
        cover_title+='——'+metadata['subtitle']
    # Insert only fixed trusted TeX, before escaping all user-supplied metadata.
    body_layout = (r'\ctexset{chapter={break={\par\Needspace{8\baselineskip}},'
                   r'beforeskip=18bp,afterskip=12bp}}' '\n'
                   # Several chapters may share a page; its last chapter mark
                   # must not misleadingly label the whole page.
                   r'\fancyhead[R]{正文}') if compact else ''
    main_tex=main_tex.replace('BODYLAYOUT',body_layout)
    # Omit unknown fields rather than printing empty identity forms.
    cover_fields = [('author','作者'),('department','单位'),('supervisor','指导教师'),('student_id','学号')]
    cover_metadata = '\n'.join(r'{\large ' + label + '：' + tex(metadata[key]) + r'\par}\vspace{0.5cm}'
                               for key,label in cover_fields if metadata.get(key))
    replacements={'TITLE':tex(cover_title),'DATE':tex(today),'AUTHOR':tex(metadata.get('author','')),
                  'COVERMETADATA':cover_metadata}
    if profile['id'] == GENERIC:
        main_tex = main_tex.replace(
            r'\documentclass[type=master,oneside,openany,cjk-font=fandol]{sjtuthesis}',
            r'\documentclass[UTF8,a4paper,12pt,oneside,openany,fontset=fandol]{ctexbook}'+'\n'+
            r'\usepackage[margin=25mm,headheight=16pt]{geometry}'+'\n'+
            r'\usepackage{fancyhdr}'+'\n'+r'\usepackage[numbers,sort&compress]{natbib}'+'\n'+
            r'\pagestyle{fancy}\fancyhf{}\fancyfoot[C]{\thepage}')
        main_tex = main_tex.replace(r'\sjtusetup{info={zh/title={TITLE},zh/subject={},zh/degree={},zh/author={AUTHOR},date={DATE}}}', '')
    # One-pass replacement: provided text cannot introduce another replacement marker.
    if replacements:
        main_tex=re.sub('|'.join(replacements),lambda m:replacements[m[0]],main_tex)
    (path/'main.tex').write_text(main_tex, encoding='utf-8')
    (path/'compile.sh').write_text('#!/bin/sh\nset -eu\nlatexmk -norc -g -xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error -file-line-error main.tex\n', encoding='utf-8')
    (path/'README.md').write_text('# LaTeX source package\n\nProfile: '+profile['id']+'\n\n'
        'Requires XeLaTeX, latexmk and the selected template dependencies. Run `sh compile.sh`.\n'
        'No shell escape, remote resource download, raw LaTeX input or bibliography fabrication. '
        'Original references are preserved in references.tex, not parsed into guessed BibTeX fields. '
        'Markdown support: headings, paragraphs, emphasis, lists, quotes, HTTPS links, text code and tables. '
        'Images and executable maths/LaTeX are not supported by this profile.\n'
        'Template: '+profile['provenance']+'. No institutional affiliation is inferred. See layout-report.json for technical checks and sources-and-review.json for evidence scope.\n', encoding='utf-8')
    provenance = Path(__file__).parent/'template-provenance'
    if profile['id'] == PROFILE and provenance.is_dir(): shutil.copytree(provenance, path/'template-provenance')
    (path/'template-selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'profile':profile['id'], 'engine':'xelatex', 'class':profile['class'],
            **({'sjtutex_version':'2.2'} if profile['id'] == PROFILE else {}),
            'template_selection':selection,
            'source_ids':list(refs), 'body_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'format_only':True, 'raw_tex_allowed':False,
            'presentation':'neutral_manuscript', 'template_provenance':profile['provenance'],
            'evidence_scope':data['audit']['scope'],
            'chapter_pagination':'continuous_short_manuscript' if compact else 'chapter_new_page',
            'layout_character_count':layout_chars, 'short_manuscript_threshold':SHORT_MANUSCRIPT_CHARS,
            'table_layout':'original_orientation_up_to_six_columns',
            'bibliography':'verbatim reviewed reference paragraphs with numeric LaTeX labels',
            'mechanical_checks':check_manuscript(data)}


def compile_pdf(data, directory):
    source = directory/'latex-source'
    meta = prepare(data, source)
    env = dict(os.environ, HOME='/tmp', TEXMFVAR='/tmp/texmf-var', TEXMFCONFIG='/tmp/texmf-config',
               openin_any='p', openout_any='p', TEXMFOUTPUT=str(source))
    with (source/'compile.log').open('wb') as log:
        p = subprocess.Popen(['latexmk','-norc','-g','-xelatex','-no-shell-escape',
            '-interaction=nonstopmode','-halt-on-error','-file-line-error','main.tex'],
            cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try: rc = p.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait()
            raise RuntimeError('LaTeX compilation timed out; no completed delivery')
    if rc: raise RuntimeError('LaTeX compilation failed; no completed delivery')
    log = (source/'main.log').read_text(errors='replace')
    failures = re.findall(r'(?:Missing character:|LaTeX Error:|There were undefined references|Citation .+ undefined|Overfull \\[hv]box)[^\n]*',log)
    if failures: raise RuntimeError('LaTeX layout/reference gate failed; simplify long cells or text')
    shutil.copyfile(source/'main.pdf',directory/'paper.pdf')
    meta['checks'] = {'compiled':True,'missing_glyphs':False,'undefined_references':False,'overfull_boxes':False}
    (directory/'layout-report.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(directory/'latex-source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in source.rglob('*'):
            if p.is_file() and p.name != 'main.pdf' and p.suffix not in ('.log','.aux','.toc','.out','.fls','.fdb_latexmk'):
                z.write(p,str(p.relative_to(source)))
        z.write(directory/'layout-report.json','layout-report.json')
    return meta
