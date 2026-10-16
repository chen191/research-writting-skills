"""Exact current server input gate; no HTTP listener or model dependency."""
import re
from urllib.parse import urlsplit
from mechanics import MAX_SOURCES, check as check_manuscript, MechanicalError
from template_profiles import select as select_template
from latex_render import PROFILE, LEGACY_PROFILE

def validate(data):
    if not isinstance(data, dict) or set(data) - {'title', 'markdown', 'sources', 'audit', 'template', 'school', 'front_matter', 'requirements'}:
        raise ValueError('Unexpected input field')
    if data.get('template') != 'legacy-a4':
        select_template(data)
    title, md = data.get('title'), data.get('markdown')
    if not isinstance(title, str) or not 1 <= len(title) <= 200:
        raise ValueError('Invalid title')
    if not isinstance(md, str) or not 500 <= len(md) <= 100000:
        raise ValueError('Manuscript must contain 500..100000 characters')
    audit = data.get('audit')
    if not isinstance(audit, dict) or audit.get('verdict') != 'PASS' or audit.get('blocking_issues') != []:
        raise ValueError('Independent final audit must PASS with empty blocking_issues')
    if not isinstance(audit.get('scope'), str) or not audit['scope'].strip():
        raise ValueError('Explicit evidence scope required')
    sources = data.get('sources')
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError(f'1..{MAX_SOURCES} real sources required')
    ids = set()
    for s in sources:
        if not isinstance(s, dict) or not re.fullmatch(r'S[1-9][0-9]*', str(s.get('id', ''))):
            raise ValueError('Source id must be S1, S2, ...')
        if s['id'] in ids: raise ValueError('Duplicate source id')
        ids.add(s['id'])
        u = urlsplit(str(s.get('url', '')))
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            raise ValueError('Source must have an HTTPS URL without credentials')
        if not s.get('title') or s.get('evidence_level') not in ('abstract', 'fulltext', 'user_provided'):
            raise ValueError('Source title and explicit evidence_level required')
    if not re.search(r'^#{1,3}\s*(参考文献|References)', md, re.M | re.I):
        raise ValueError('Missing reference section')
    if re.search(r'!\[.*?\]\(|<\s*(script|iframe|object|embed|svg|img)\b', md, re.I):
        raise ValueError('Executable HTML and embedded images are not supported; use evidence tables')
    if '\x00' in md: raise ValueError('NUL not allowed')
    report=check_manuscript(data)
    if not report['passed']: raise MechanicalError(report)
    # Old requests remain readable, but newly rendered output uses the clean profile.
    if data.get('template') == LEGACY_PROFILE:
        data = dict(data, template=PROFILE)
    return data
