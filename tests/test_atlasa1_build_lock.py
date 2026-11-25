"""Prevent overlapping builds while allowing configuration inspection."""
from pathlib import Path
import subprocess
import tempfile
import unittest


EXTENSION = Path(__file__).resolve().parents[1]/'userpatches/extensions/atlasa1.sh'


class BuildLockTests(unittest.TestCase):
    def test_concurrent_build_and_release(self):
        with tempfile.TemporaryDirectory() as folder:
            script = '''set -eu
source "$1"
SRC="$2"
function exit_with_error() { echo "$*" >&2; exit 91; }
CONFIG_DEFS_ONLY="$3"
atlasa1_acquire_build_lock
atlasa1_acquire_build_lock
echo locked
if [[ "$4" == hold ]]; then read -r release; fi
'''
            args = ['bash', '-c', script, 'lock-test', str(EXTENSION), folder]
            first = subprocess.Popen(args+['no', 'hold'], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(first.stdout.readline().strip(), 'locked')
                second = subprocess.run(args+['no', 'exit'], capture_output=True, text=True)
                self.assertEqual(second.returncode, 91, second.stderr)
                self.assertIn('Another AtlasA1 build', second.stderr)
                config = subprocess.run(args+['yes', 'exit'], capture_output=True, text=True)
                self.assertEqual(config.returncode, 0, config.stderr)
            finally:
                first.communicate('release\n', timeout=10)
            final = subprocess.run(args+['no', 'exit'], capture_output=True, text=True)
            self.assertEqual(final.returncode, 0, final.stderr)


if __name__ == '__main__':
    unittest.main()
