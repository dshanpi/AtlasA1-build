"""Backups must verify Git bytes even when the working tree differs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/verify_source_manifest.py'
spec = importlib.util.spec_from_file_location('source_manifest', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceManifestTests(unittest.TestCase):
    def fixture(self, root):
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        (root / '.gitattributes').write_text('*.log -text\n')
        raw = b'UART\r\r\nprogress\rcomplete\n'
        (root / 'capture.log').write_bytes(raw)
        entry = {'path': 'capture.log', 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        (root / 'SOURCE-MANIFEST.json').write_text(json.dumps({'repository': 'test', 'files': [entry]}))
        subprocess.run(['git', '-C', str(root), 'add', '-f', '.gitattributes', 'capture.log', 'SOURCE-MANIFEST.json'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '-qm', 'fixture'], check=True)
        return entry

    def test_committed_capture_survives_worktree_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.assertTrue(module.verify(root, 'HEAD')['passed'])
            (root / 'capture.log').write_bytes(b'dirty worktree')
            self.assertFalse(module.verify(root)['passed'])
            self.assertTrue(module.verify(root, 'HEAD')['passed'])

    def test_absent_committed_file_is_not_hidden_by_local_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            subprocess.run(['git', '-C', str(root), 'rm', '--cached', '-q', 'capture.log'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'remove capture from Git only'], check=True)
            self.assertTrue(module.verify(root)['passed'])
            result = module.verify(root, 'HEAD')
            self.assertFalse(result['passed'])
            self.assertEqual(result['errors'][0]['error'], 'missing regular file')

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = self.fixture(root)
            entry['path'] = '../outside'
            (root / 'SOURCE-MANIFEST.json').write_text(json.dumps({'repository': 'test', 'files': [entry]}))
            with self.assertRaises(ValueError):
                module.verify(root)


if __name__ == '__main__':
    unittest.main()
