"""Standalone task workspace bridge; no model, search, scoring or academic PASS generation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid
from runtime_transport import call as runtime_call, artifact as runtime_artifact

MAX_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def valid_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def request(work):
    value = read(work / 'request.json')
    validate_request(work, value)
    return value


def validate_request(work, value):
    require(valid_uuid(value.get('task_id')), 'A real frontend task UUID is required')
    require(work.name == 'paper-' + value['task_id'], 'Task directory mismatch')
    require(type(value.get('word_target')) is int and value['word_target'] > 0, 'Invalid word target')
    require(type(value.get('min_sources')) is int and value['min_sources'] > 0, 'Invalid source minimum')
    require(isinstance(value.get('title'), str) and 1 <= len(value['title']) <= 200, 'Invalid title')
    require(isinstance(value.get('requirements'), str), 'Preserve user requirements')
    require(value.get('template') in ('generic-paper-v1', 'sjtu-paper-v1'), 'Unsupported user template')


def freeze(work, source):
    value = read(source)
    require(not (work / 'request.json').exists(), 'Request already frozen; do not replace it')
    validate_request(work, value)
    write(work / 'request.json', value, exclusive=True)
    return {'task_id': value['task_id'], 'frozen': True}


def inputs(work):
    req = request(work)
    sources = read(work / 'sources.json')
    require(isinstance(sources, list) and len(sources) >= req['min_sources'], 'Insufficient real sources')
    for source in sources:
        require(isinstance(source, dict), 'Invalid source')
        require(re.fullmatch(r'S[1-9]\d*', str(source.get('id', ''))), 'Invalid source id')
        url = urlsplit(source.get('url', ''))
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password, 'Source URL must be HTTPS without credentials')
        require(source.get('evidence_level') in ('abstract', 'fulltext', 'user_provided'), 'Unverified source evidence scope')
        require(all(isinstance(source.get(k), str) and source[k].strip() for k in ('title', 'locator', 'evidence', 'retrieval')), 'Source evidence and retrieval provenance required')
    hashes = {k: sha((work / name).read_bytes()) for k, name in
              [('request', 'request.json'), ('manuscript', 'paper.md'), ('sources', 'sources.json')]}
    return req, sources, hashes


def render_input(work):
    req, sources, hashes = inputs(work)
    # Preserve CRLF bytes: the compiler hashes the submitted UTF-8 string, not universal-newline text.
    value = {'title': req['title'], 'markdown': (work / 'paper.md').read_bytes().decode('utf-8'),
             'sources': sources, 'template': req['template'],
             'requirements': {'min_chinese': req['word_target'], 'min_sources': req['min_sources']}}
    return value, hashes


def check(work):
    value, hashes = render_input(work)
    report = runtime_call('check', {k: value[k] for k in ('markdown', 'sources', 'requirements')})
    require(isinstance(report, dict) and report.get('manuscript_sha256') == hashes['manuscript'], 'Mechanical response not bound to manuscript')
    body = report.get('body_chinese_count_less_exact_repeats')
    if report.get('passed') is True and (type(body) is not int or body < request(work)['word_target']):
        report['passed'] = False
        report.setdefault('errors', []).append({'code': 'body_below_user_target', 'actual': body})
    report['input_hashes'] = hashes
    write(work / 'mechanical.json', report)
    return report


def checked(work):
    _, _, hashes = inputs(work)
    result = read(work / 'mechanical.json')
    require(result.get('passed') is True and result.get('input_hashes') == hashes, 'Mechanical check failed or inputs changed')
    return hashes


def review_input(work):
    hashes = checked(work)
    result = {'schema_version': 1, 'task_id': request(work)['task_id'], 'input_hashes': hashes,
              'files': ['request.json', 'outline.md', 'sources.json', 'paper.md', 'mechanical.json'],
              'instruction': 'Independently read all inputs and verify actual sources, citation support, argument, limitations and relevance of writing guides. Write review.json yourself and return its exact JSON. No nested delegation or authorship of the manuscript.'}
    write(work / 'review-input.json', result)
    return result


def accept_review(work, source):
    hashes = checked(work)
    native = read(source)
    require(native.get('status') == 'completed' and native.get('error') in (None, ''), 'Independent native run not completed')
    require(valid_uuid(native.get('thread_id')) and valid_uuid(native.get('run_id'))
            and native['thread_id'] != native['run_id'], 'Actual native reviewer identifiers required')
    answer = native.get('answer')
    require(isinstance(answer, str), 'Exact native final answer required')
    report = json.loads(answer)
    require(report == read(work / 'review.json'), 'Reviewer file differs from actual returned answer')
    require(report.get('schema_version') == 1 and report.get('task_id') == request(work)['task_id'], 'Review task mismatch')
    require(report.get('input_hashes') == hashes, 'Review covers another manuscript version')
    require(report.get('verdict') in ('PASS', 'REVISE', 'BLOCKED'), 'Invalid review verdict')
    require(isinstance(report.get('blocking_issues'), list), 'Explicit blockers required')
    require(all(isinstance(report.get(k), str) and report[k].strip() for k in ('scope', 'notes')), 'Actual independent review scope and findings required')
    require(report['verdict'] == 'PASS' and report['blocking_issues'] == [], 'Independent review did not PASS')
    result = {'review': report, 'native_return': native,
              'provenance_scope': 'Structural and hash validation only; actual native execution is verified in host History, not cryptographically authenticated by this offline bridge.'}
    write(work / 'accepted-review.json', result)
    return {'verdict': 'PASS', 'input_hashes': hashes}


def approved(work):
    hashes = checked(work)
    report = read(work / 'accepted-review.json')['review']
    require(report.get('verdict') == 'PASS' and report.get('blocking_issues') == []
            and report.get('input_hashes') == hashes, 'Independent review missing, failed or stale')
    return report, hashes


def render(work):
    audit, hashes = approved(work)
    require(not (work / 'render-request.json').exists(), 'Prior render exists or outcome unknown; do not replay compilation')
    value, _ = render_input(work)
    value['audit'] = {'verdict': 'PASS', 'blocking_issues': [], 'scope': audit['scope']}
    write(work / 'render-request.json', {'input_hashes': hashes, 'input': value}, exclusive=True)
    receipt = runtime_call('render', value, work)
    require(receipt.get('backend') == 'runtime-local-v1', 'Unexpected compiler backend')
    require(receipt.get('status') == 'completed' and receipt.get('execution') == 'xelatex_pdf', 'No successful PDF compilation')
    require(type(receipt.get('pages')) is int and 1 <= receipt['pages'] <= 150, 'Invalid page count')
    require(receipt.get('template') == value['template'], 'Compiler changed user template')
    files = receipt.get('files', {})
    require({'paper.pdf', 'pdf-contact-sheet.png'} <= set(files), 'Missing compiled artifacts')
    paths = {}
    for name in ('paper.pdf', 'pdf-contact-sheet.png', 'pdf-inspection.json'):
        if name not in files:
            continue
        raw = runtime_artifact(work, files[name], name)
        if name == 'paper.pdf':
            require(raw.startswith(b'%PDF-') and sha(raw) == receipt.get('sha256')
                    and len(raw) == receipt.get('size_bytes'), 'PDF receipt mismatch')
        else:
            require(raw.startswith(b'\x89PNG\r\n\x1a\n') if name.endswith('.png') else isinstance(json.loads(raw), dict), 'Invalid preview artifact')
        require(not (work / name).is_symlink(), 'Unsafe local artifact destination')
        (work / name).write_bytes(raw)
        paths[name] = files[name]
    receipt.pop('files', None)
    receipt['input_hashes'] = hashes
    write(work / 'render-receipt.json', receipt)
    write(work / 'artifact-paths.json', paths)
    return {'pages': receipt['pages'], 'sha256': receipt['sha256']}


def compiled(work):
    _, hashes = approved(work)
    receipt = read(work / 'render-receipt.json')
    raw = (work / 'paper.pdf').read_bytes()
    require(receipt.get('input_hashes') == hashes, 'Compiled inputs changed')
    require(raw.startswith(b'%PDF-') and sha(raw) == receipt.get('sha256') and len(raw) == receipt.get('size_bytes'), 'Current PDF differs from compiler receipt')
    return receipt


def preview(work):
    receipt = compiled(work)
    result = runtime_call('preview', {'sha256':receipt['sha256'], 'pages':receipt['pages']}, work)
    require(result.get('backend') == 'runtime-local-v1' and result.get('pdf_sha256') == receipt['sha256'], 'Preview backend/PDF mismatch')
    folder = work / 'preview'
    pages = {}
    for number in range(1, receipt['pages'] + 1):
        file = folder / (str(number) + '.png')
        require(not folder.is_symlink() and not file.is_symlink(), 'Unsafe local preview path')
        raw = file.read_bytes()
        require(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid page preview')
        require(sha(raw) == result.get('pages', {}).get(str(number)), 'Local page preview hash mismatch')
        pages[str(number)] = sha(raw)
    require(set(result['pages']) == set(pages), 'Unexpected preview pages')
    result = {'pdf_sha256': receipt['sha256'], 'pages': pages, 'backend':'runtime-local-v1'}
    write(work / 'previews.json', result)
    return {'pages_downloaded': len(pages), 'visual_review_done': False}


def publish(work):
    receipt = compiled(work)
    visual = read(work / 'visual-review.json')
    previews = read(work / 'previews.json')
    expected = list(range(1, receipt['pages'] + 1))
    require(visual.get('verdict') == 'PASS' and visual.get('blocking_issues') == [], 'Visual review did not PASS')
    require(visual.get('pdf_sha256') == receipt['sha256'] == previews.get('pdf_sha256'), 'Visual review covers another PDF')
    require(visual.get('pages_inspected') == expected and set(previews.get('pages', {})) == {str(n) for n in expected}, 'All actual pages must be inspected')
    require(isinstance(visual.get('notes'), str) and visual['notes'].strip(), 'Actual visual findings required')
    for number, digest in previews['pages'].items():
        require(sha((work / 'preview' / (number + '.png')).read_bytes()) == digest, 'Page preview changed')
    result = {'schema_version': 1, 'status': 'ready', 'task_id': request(work)['task_id'],
              'pdf': {'path': str((work / 'paper.pdf').as_posix()), 'sha256': receipt['sha256'], 'size': receipt['size_bytes']},
              'checks': {'independent_review': True, 'mechanical': True, 'pdf_hash': True, 'visual_review': True},
              'note': 'Model independent review and actual compilation, not academic certification; human source checking remains necessary.'}
    write(work / 'portal-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'check', 'review-input', 'accept-review', 'render', 'preview', 'publish'])
    parser.add_argument('--workdir', required=True)
    parser.add_argument('--input')
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    require(work.is_dir(), 'Create only the authorized task directory first')
    if args.action in ('freeze', 'accept-review'):
        require(args.input, '--input is required')
        result = {'freeze': freeze, 'accept-review': accept_review}[args.action](work, args.input)
    else:
        result = {'check': check, 'review-input': review_input, 'render': render, 'preview': preview, 'publish': publish}[args.action](work)
    print(json.dumps(result, ensure_ascii=False))
    if result.get('passed') is False:
        raise SystemExit(2)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
