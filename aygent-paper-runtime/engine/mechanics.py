"""Pure manuscript checks shared by the read-only tool and final render gate."""
import hashlib
import re
from urllib.parse import unquote

MAX_SOURCES = 120
CITATION = re.compile(r'\[S(?=\d)[^\]\n]*\]')
META = {'作者':'author', '导师':'supervisor', '学院':'department', '院系':'department',
        '学号':'student_id', '日期':'date', '副标题':'subtitle'}


def citation_ids(group):
    inner = group[1:-1].replace('，', ',').replace('–', '-').replace('—', '-')
    ids = []
    for part in inner.split(','):
        m = re.fullmatch(r'\s*S([1-9]\d*)(?:\s*-\s*S?([1-9]\d*))?\s*', part)
        if not m: raise ValueError('Invalid citation syntax: ' + group[:40])
        start, end = int(m[1]), int(m[2] or m[1])
        if end < start or end - start >= MAX_SOURCES or end > 999: raise ValueError('Invalid citation range')
        ids.extend('S'+str(n) for n in range(start,end+1))
    return list(dict.fromkeys(ids))


def split_manuscript(markdown):
    parts = re.split(r'^#{1,3}\s*(?:参考文献|References)\s*$', markdown, flags=re.M|re.I)
    if len(parts) != 2: raise ValueError('Exactly one reference section required')
    body, reftext = parts
    # Stage labels and revision notes are not manuscript material.
    body = re.sub(r'^\s*PAPER_STATUS:\s*READY\s*\n', '', body, count=1)
    reftext = re.split(r'^#{1,3}\s*修订说明\s*$', reftext, flags=re.M)[0].rstrip()
    reftext = re.sub(r'\n---\s*$', '', reftext)
    refs, current = {}, None
    for line in reftext.splitlines():
        line = line.strip()
        if not line: continue
        m = re.match(r'^(?:[-*]\s+)?\[(S[1-9]\d*)\]\s*(.*)', line)
        if m:
            current = m[1]
            if current in refs: raise ValueError('Duplicate bibliography id')
            refs[current] = m[2]
        elif current and not line.startswith('#'): refs[current] += ' ' + line
        else: raise ValueError('References must be separate [Sx] paragraphs')
    return body, refs


def front_matter(body, explicit=None):
    """Extract only recognized leading metadata; never discard unknown prose."""
    metadata, kept = {}, []
    active = True
    for line in body.splitlines():
        if active:
            if not line.strip(): continue
            title = re.match(r'^#\s+(.+)$',line)
            subtitle = re.match(r'^##\s+([—–-]{1,2}.+)$',line)
            clean = line.replace('**','').strip()
            item = re.fullmatch(r'(作者|导师|学院|院系|学号|日期|副标题)\s*[:：]\s*(.*)',clean)
            if title and 'title' not in metadata: metadata['title']=title[1].strip(); continue
            if subtitle: metadata['subtitle']=subtitle[1].lstrip('—–- ').strip(); continue
            if item: metadata[META[item[1]]]=item[2].strip(); continue
            active=False
        kept.append(line)
    if explicit is not None:
        if not isinstance(explicit,dict) or set(explicit)-set(META.values()): raise ValueError('Invalid front_matter')
        for key,value in explicit.items():
            if not isinstance(value,str) or len(value)>200: raise ValueError('Invalid front_matter value')
            if metadata.get(key) and value and metadata[key]!=value: raise ValueError('Conflicting front matter')
            if value or key not in metadata: metadata[key]=value
    return metadata,'\n'.join(kept)


def normalized_doi(value):
    value=unquote(str(value or '')).strip()
    value=re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)','',value,flags=re.I)
    value=value.rstrip('.,;。；').casefold()
    while value.endswith(')') and value.count(')')>value.count('('): value=value[:-1]
    return value if re.fullmatch(r'10\.\d{4,9}/\S+',value) else None


def manuscript_boundary(tokens):
    """Locate generation-process wording for human review, never rewrite prose.

    Research about software testing, APIs or retrieval is not inherently suspect.
    Hits are contextual diagnostics, not factual/semantic failure decisions.
    """
    patterns = ('本任务已保存', '本轮门禁', '原门禁通过', '结构化资格检查',
                '批准用途', '稿件哈希', '排版测试', '审查JSON', '审查 JSON')
    hits = []
    for token in tokens:
        if token.type != 'inline': continue
        prose = ''.join(t.content for t in token.children or [] if t.type == 'text')
        for phrase in patterns:
            start = prose.find(phrase)
            if start >= 0:
                hits.append({'phrase':phrase, 'lines': [token.map[0]+1,token.map[1]] if token.map else None,
                             'excerpt':prose[max(0,start-40):start+len(phrase)+60]})
    return {'required':bool(hits),'hits':hits,
            'scope':'Manuscript inline text including abstracts, headings and tables; excludes code and bibliography. Line numbers refer to the parsed body after leading metadata removal.',
            'note':'Contextual diagnostic only. An independent reviewer must distinguish the research system from the manuscript-generation system; no automatic deletion or PASS.'}


def check(data):
    """No writes, network, model calls or compilation. Does not evaluate scientific truth."""
    from markdown_it import MarkdownIt
    if not isinstance(data,dict): raise ValueError('Expected an object')
    text=data.get('markdown')
    if not isinstance(text,str) or not 1<=len(text)<=100000: raise ValueError('Invalid markdown size')
    sources=data.get('sources')
    if not isinstance(sources,list) or not 1<=len(sources)<=MAX_SOURCES: raise ValueError('Invalid sources')
    req=data.get('requirements') or {}
    if not isinstance(req,dict) or set(req)-{'min_chinese','max_chinese','min_sources','max_sources'}: raise ValueError('Invalid requirements')
    for name,value in req.items():
        maximum = MAX_SOURCES if name.endswith('_sources') else 100000
        if value is not None and (type(value) is not int or not 0<=value<=maximum): raise ValueError('Invalid requirement bounds')
    low,high=req.get('min_chinese'),req.get('max_chinese')
    if low is not None and high is not None and low>high: raise ValueError('Invalid count interval')
    min_sources,max_sources=req.get('min_sources'),req.get('max_sources')
    if min_sources is not None and max_sources is not None and min_sources>max_sources: raise ValueError('Invalid source count interval')
    body,refs=split_manuscript(text)
    meta,body=front_matter(body,data.get('front_matter'))
    tokens=MarkdownIt('commonmark',{'html':False}).enable('table').parse(body)
    errors=[];ids=[];dois={};cited=[];visible=[];skip=0;heading=False;chapters=[]
    abstract_visible=[];abstract_level=None;heading_level=0
    body_paragraphs=0;paragraph_occurrences={}
    for source in sources:
        if not isinstance(source,dict) or not re.fullmatch(r'S[1-9]\d*',str(source.get('id',''))): raise ValueError('Invalid source id')
        sid=source['id']
        if sid in ids: errors.append({'code':'duplicate_source_id','id':sid})
        ids.append(sid)
        # The same DOI in explicit field and URL for one source is not a duplicate work.
        values={normalized_doi(source.get(k)) for k in ['doi','url','doi_url']}
        values.discard(None)
        # Sources often carry only OpenAlex URL; also inspect the supplied bibliography DOI.
        values.update(normalized_doi(v) for v in re.findall(r'10\.\d{4,9}/[^\s<>\]"}]+',refs.get(sid,'')))
        values={v for v in values if v}
        for doi in values:
            if doi in dois and dois[doi]!=sid: errors.append({'code':'duplicate_doi','ids':[dois[doi],sid],'doi':doi})
            dois[doi]=sid
    if set(refs)!=set(ids) or any(not s.strip() for s in refs.values()): errors.append({'code':'bibliography_source_mismatch'})
    for t in tokens:
        if t.type in ('table_open','blockquote_open'): skip+=1
        if t.type=='heading_open': heading=True;heading_level=int(t.tag[1:])
        if t.type=='inline':
            # Citations are checked in prose and tables, not code, URLs or bibliography labels.
            for child in t.children or []:
                if child.type=='text':
                    for match in CITATION.finditer(child.content):
                        try: cited.extend(citation_ids(match[0]))
                        except ValueError: errors.append({'code':'invalid_citation','value':match[0][:40]})
            if heading:
                chapters.append(t.content)
                if not skip:
                    title=re.sub(r'\s+','',t.content).casefold()
                    if title in ('摘要','中文摘要','英文摘要','abstract'):
                        abstract_level=heading_level
                    elif abstract_level is not None and heading_level<=abstract_level:
                        abstract_level=None
            elif not skip and not re.match(r'^(?:\*\*)?(?:关键词|Keywords)\s*[:：]',t.content,re.I):
                prose=''.join(child.content for child in t.children or [] if child.type=='text')
                visible.append(prose)
                if abstract_level is not None:
                    abstract_visible.append(prose)
                elif prose.strip():
                    body_paragraphs+=1
                    # A diagnostic for literal padding, not a semantic originality score.
                    normalized=re.sub(r'\s+','',CITATION.sub('',prose))
                    if len(re.findall(r'[\u4e00-\u9fff]',normalized))>=80:
                        paragraph_occurrences.setdefault(normalized,[]).append(body_paragraphs)
        if t.type=='heading_close': heading=False
        if t.type in ('table_close','blockquote_close'): skip-=1
    missing=sorted(set(cited)-set(ids));unused=sorted(set(ids)-set(cited))
    if missing: errors.append({'code':'unknown_citations','ids':missing})
    if unused: errors.append({'code':'uncited_sources','ids':unused})
    unique_sources=len(set(ids))
    if min_sources is not None and unique_sources<min_sources: errors.append({'code':'too_few_sources','actual':unique_sources,'min':min_sources})
    if max_sources is not None and unique_sources>max_sources: errors.append({'code':'too_many_sources','actual':unique_sources,'max':max_sources})
    count=len(re.findall(r'[\u4e00-\u9fff]',''.join(visible)))
    abstract_count=len(re.findall(r'[\u4e00-\u9fff]',''.join(abstract_visible)))
    repeats=[]
    for paragraph,numbers in paragraph_occurrences.items():
        if len(numbers)>1:
            paragraph_count=len(re.findall(r'[\u4e00-\u9fff]',paragraph))
            repeats.append({'paragraph_numbers':numbers,'chinese_count':paragraph_count,
                            'excess_chinese_count':paragraph_count*(len(numbers)-1),
                            'normalized_sha256':hashlib.sha256(paragraph.encode()).hexdigest()})
    repeated_count=sum(item['excess_chinese_count'] for item in repeats)
    if low is not None and count<low: errors.append({'code':'too_short','actual':count,'min':low})
    if high is not None and count>high: errors.append({'code':'too_long','actual':count,'max':high})
    return {'schema_version':1,'execution':'deterministic_python','passed':not errors,
            'manuscript_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'chinese_count':count,'count_scope':'includes abstract; excludes title/headings, keywords, tables, blockquotes, code, references and revision notes',
            'abstract_chinese_count':abstract_count,'body_chinese_count':count-abstract_count,
            'body_chinese_count_less_exact_repeats':count-abstract_count-repeated_count,
            'repetition_review':{'required':bool(repeats),'exact_repeated_paragraphs':repeats,
                                 'scope':'Body prose paragraphs with at least 80 Han characters; whitespace and citation markers ignored. Not a semantic redundancy or plagiarism verdict.'},
            'manuscript_boundary_review':manuscript_boundary(tokens),
            'requirements':req,'citation_ids':list(dict.fromkeys(cited)),'source_count':len(ids),
            'unique_doi_count':len(dois),'chapters':chapters,'errors':errors,
            'note':'Mechanical checks only, not factual accuracy or authoritative final-review approval.'}


def check_request(data):
    """Return a structured negative result for missing/malformed manuscripts, never a fake count.

    Only the transport uses this envelope. Render still calls strict check/validate.
    """
    text=data.get('markdown') if isinstance(data,dict) else None
    code=None
    if isinstance(text,str) and re.match(r'^\s*PAPER_STATUS:\s*(NEEDS_INPUT|BLOCKED)\b',text):
        code='manuscript_not_ready'
    if not code:
        try:
            return check(data)
        except (ValueError,TypeError,KeyError) as exc:
            code={'Exactly one reference section required':'reference_section_required',
                  'Duplicate bibliography id':'duplicate_bibliography_id',
                  'Invalid markdown size':'invalid_manuscript_size'}.get(str(exc),'invalid_check_input')
    return {'schema_version':1,'execution':'deterministic_python','passed':False,
            'chinese_count':None,'abstract_chinese_count':None,'body_chinese_count':None,
            'body_chinese_count_less_exact_repeats':None,'repetition_review':None,
            'manuscript_sha256':hashlib.sha256(text.encode()).hexdigest() if isinstance(text,str) else None,
            'errors':[{'code':code}], 'note':'No valid manuscript count produced; correct the indicated input before review.'}


class MechanicalError(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('Mechanical manuscript checks failed')
