"""First-login display defaults must not override saved or unsupported layouts."""
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'config/gnome-wayland/atlasa1-display-default'


class DisplayDefaults(unittest.TestCase):
    def run_helper(self, root, modes=None, monitors=1, fail=False):
        calls = []
        spec = ('HDMI-1', 'A&B', 'Test <Panel>', '123')
        if modes is None:
            modes = [('1080p60', 1920, 1080, 60.0, 1.0, [1.0], {})]
        state = (7, [(spec, modes, {})] * monitors,
                 [(0, 0, 1.0, 0, True, [spec], {})], {'layout-mode': 1})

        class Error(Exception):
            pass

        def call(*args):
            if args[3] == 'GetCurrentState':
                return SimpleNamespace(unpack=lambda: state)
            calls.append(args[4])
            if fail:
                raise Error('display apply failed')
            return None

        gio = SimpleNamespace(bus_get_sync=lambda *a: SimpleNamespace(call_sync=call),
                              BusType=SimpleNamespace(SESSION=0),
                              DBusCallFlags=SimpleNamespace(NONE=0))
        glib = SimpleNamespace(Error=Error, Variant=lambda signature, value: (signature, value))
        with patch.dict(sys.modules, {'gi': SimpleNamespace(), 'gi.repository': SimpleNamespace(Gio=gio, GLib=glib)}), \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root)}), \
             patch.object(sys, 'argv', [str(SCRIPT)]), patch('time.sleep'):
            runpy.run_path(str(SCRIPT), run_name='__main__')
        return calls

    def test_apply_without_confirmation_and_save_matching_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = self.run_helper(root)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1][1], 1)
            document = ET.parse(root / 'monitors.xml')
            self.assertEqual(document.findtext('.//vendor'), 'A&B')
            self.assertEqual(document.findtext('.//product'), 'Test <Panel>')
            self.assertEqual(document.findtext('.//width'), '1920')
            self.assertEqual(document.findtext('.//rate'), '60.000')
            self.assertEqual(list(root.glob('.atlas-monitor-*')), [])

    def test_saved_configuration_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'monitors.xml').write_text('user configuration')
            self.assertFalse(self.run_helper(root))
            self.assertEqual((root / 'monitors.xml').read_text(), 'user configuration')

    def test_unsupported_or_multiple_monitors_are_untouched(self):
        for options in ({'modes': []}, {'monitors': 2}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.assertFalse(self.run_helper(root, **options))
                self.assertFalse((root / 'monitors.xml').exists())

    def test_failed_apply_does_not_save_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_helper(root, fail=True)
            self.assertFalse((root / 'monitors.xml').exists())


if __name__ == '__main__':
    unittest.main()
