"""Scoped migration regression; mocks never represent real independent review."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(PACKAGE/'engine'),str(PACKAGE.parent/'research-writing-aygent/scripts')]
import cli
import paper
import runtime_transport as transport
from latex_render import tex
from validation import validate

class RuntimeTests(unittest.TestCase):
    def test_original_modules_unchanged(self):
        origin=json.loads((PACKAGE/'ORIGIN.json').read_bytes())
        for name,meta in origin['files'].items():
            self.assertEqual(hashlib.sha256((PACKAGE/'engine'/name).read_bytes()).hexdigest(),meta['sha256'])

    def test_no_http_or_daemon(self):
        code=(PACKAGE.parent/'research-writing-aygent/scripts/paper.py').read_text(encoding='utf8')
        self.assertNotIn('urlopen',code)
        config=json.loads((PACKAGE.parent/'research-writing-aygent/scripts/service-endpoints.json').read_bytes())
        self.assertEqual(config,{'backend':transport.BACKEND,'runtime_python':transport.PYTHON,'runtime_cli':transport.CLI})
        docker=(PACKAGE/'Dockerfile').read_text(encoding='utf8')
        self.assertNotIn('\nEXPOSE ',docker);self.assertNotIn('\nENTRYPOINT ',docker)

    def test_missing_runtime_blocks(self):
        with self.assertRaisesRegex(RuntimeError,'missing from this runtime'):
            transport.call('check',{})

    def test_action_allowlist(self):
        with self.assertRaises(ValueError):transport.call('serve',{})

    def test_no_review_rejected(self):
        with self.assertRaisesRegex(ValueError,'Independent final audit'):
            validate({'title':'fixture','markdown':'字'*600,'template':'generic-paper-v1'})

    def test_unknown_profile_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unsupported formal template'):
            cli.render({'template':'unknown'},Path('/workspace'))

    def test_no_raw_tex(self):
        self.assertNotIn(r'\input{',tex(r'\input{/etc/passwd}'))
        self.assertIn(r'\textbackslash{}input',tex(r'\input{/etc/passwd}'))

    def test_task_path_restricted(self):
        for name in ['/tmp/paper-00000000-0000-0000-0000-000000000000','/workspace','/etc']:
            with self.assertRaises(ValueError):cli.task_folder(name)

    def test_artifact_traversal_rejected(self):
        with self.assertRaises(ValueError):transport.artifact(Path('.'),'../paper.pdf','paper.pdf')
        with self.assertRaises(ValueError):transport.artifact(Path('.'),'.paper-render/secret','secret')

    def test_artifact_read_and_size(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder);target=work/'.paper-render';target.mkdir();(target/'paper.pdf').write_bytes(b'%PDF-fixture')
            self.assertEqual(transport.artifact(work,'.paper-render/paper.pdf','paper.pdf'),b'%PDF-fixture')
            with patch.object(transport,'MAX_BYTES',2),self.assertRaises(ValueError):transport.artifact(work,'.paper-render/paper.pdf','paper.pdf')

    def test_render_requires_actual_approval(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(paper,'runtime_call') as call:
            with self.assertRaises(OSError):paper.render(Path(folder))
            call.assert_not_called()

    def test_unknown_render_not_replayed(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(paper,'approved',return_value=({},{})),patch.object(paper,'runtime_call') as call:
            work=Path(folder);(work/'render-request.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'do not replay'):paper.render(work)
            call.assert_not_called()

    def test_preview_wrong_pdf_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder);(work/'paper.pdf').write_bytes(b'%PDF-fixture')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):cli.previews({'sha256':'wrong','pages':1},work)

    def test_publish_no_visual_evidence(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(paper,'compiled',return_value={'pages':1,'sha256':'x'}):
            with self.assertRaises(OSError):paper.publish(Path(folder))
            self.assertFalse((Path(folder)/'portal-result.json').exists())

    def test_publish_stale_visual_blocked(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(paper,'compiled',return_value={'pages':1,'sha256':'current'}):
            work=Path(folder)
            paper.write(work/'visual-review.json',{'verdict':'PASS','blocking_issues':[],'pdf_sha256':'old'})
            paper.write(work/'previews.json',{'pdf_sha256':'old'})
            with self.assertRaisesRegex(ValueError,'another PDF'):paper.publish(work)
            self.assertFalse((work/'portal-result.json').exists())

if __name__=='__main__':unittest.main()
