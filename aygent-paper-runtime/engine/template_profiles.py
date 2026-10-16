"""Two built-in profiles only: SJTU for explicit SJTU requests, generic otherwise."""
import re

GENERIC = 'generic-paper-v1'
SJTU = 'sjtu-paper-v1'
LEGACY = 'sjtu-master-test-v1'


def normalized_school(value):
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('school must be a string of at most 200 characters')
    return re.sub(r'\s+', '', value).casefold()


def profiles():
    result = {
        GENERIC: {'id': GENERIC, 'schools': [], 'name': '通用 A4 论文', 'class': 'ctexbook',
                  'provenance': 'Project generic A4 manuscript layout; no university affiliation'},
        SJTU: {'id': SJTU, 'schools': ['上海交通大学', '上海交大', '上交', 'SJTU', 'Shanghai Jiao Tong University'],
               'name': '上海交通大学 SJTUTeX 排版', 'class': 'sjtuthesis',
               'provenance': 'SJTUTeX 2.2; upstream licenses included in latex-source.zip'},
    }
    return result


def select(data):
    requested = data.get('template', 'auto')
    school = data.get('school', '')
    key = normalized_school(school)
    available = profiles()
    requested = SJTU if requested == LEGACY else requested
    if not isinstance(requested, str): raise ValueError('Invalid template')
    reason = 'explicit_template'
    if requested == 'auto':
        matches = [p['id'] for p in available.values()
                   if key and key in {normalized_school(s) for s in p['schools']}]
        ident = matches[0] if matches else GENERIC
        reason = 'school_match' if matches else 'other_school_generic' if key else 'school_not_specified'
    elif requested in available:
        ident = requested
        if key and ident != GENERIC and key not in {normalized_school(s) for s in available[ident]['schools']}:
            raise ValueError('Selected template does not match requested school')
    else:
        raise ValueError('Unknown template id; use auto with school, or generic-paper-v1 / sjtu-paper-v1')
    return available[ident], {'requested_school': school, 'requested_template': requested,
                            'selected_template': ident, 'reason': reason,
                            'fallback': reason == 'other_school_generic'}


def catalog():
    return [{k: p[k] for k in ('id', 'schools', 'name', 'class', 'provenance')} for p in profiles().values()]

