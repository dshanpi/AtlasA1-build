import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('fetch_inputs', Path(__file__).resolve().parents[1] / 'tools/fetch_atlasa1_inputs.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class FrozenInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = self.root / 'lock.json'
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.lock.write_text(json.dumps({'assets': [{'name': 'input.tar.zst', 'size': 4,
            'sha256': hashlib.sha256(b'good').hexdigest(), 'url': 'https://example.invalid/input'}]}))

    def test_corrupted_cache_is_rejected_without_download(self):
        (self.cache / 'input.tar.zst').write_bytes(b'evil')
        with patch.object(fetch.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                fetch.fetch(self.lock, self.cache)
            run.assert_not_called()

    def test_complete_partial_recovers_without_network(self):
        (self.cache / 'input.tar.zst.partial').write_bytes(b'good')
        with patch.object(fetch.subprocess, 'run') as run:
            fetch.fetch(self.lock, self.cache)
            run.assert_not_called()
        self.assertEqual((self.cache / 'input.tar.zst').read_bytes(), b'good')

    def test_bad_download_never_becomes_final_asset(self):
        def bad_download(*args, **kwargs):
            (self.cache / 'input.tar.zst.partial').write_bytes(b'evil')
        with patch.object(fetch.subprocess, 'run', side_effect=bad_download):
            with self.assertRaises(RuntimeError):
                fetch.fetch(self.lock, self.cache)
        self.assertFalse((self.cache / 'input.tar.zst').exists())


if __name__ == '__main__':
    unittest.main()
