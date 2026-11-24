"""Keep user kernel settings when reinstalling board support."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import install_atlasa1_armbian as installer


class InstallTests(unittest.TestCase):
    def test_kernel_menu_settings_survive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            recipe, framework = root/'recipe', root/'armbian'
            (framework/'lib').mkdir(parents=True)
            (framework/'lib/single.sh').write_text('# framework\n')
            for name in installer.FILES:
                source = recipe/'userpatches'/name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text('# baseline\n')
            with patch.object(installer, 'ROOT', recipe), patch.object(
                    installer.subprocess, 'check_output', return_value=installer.REVISION+'\n'):
                installer.install(framework)
                config = framework/'userpatches/config/kernel/linux-atlasa1-current.config'
                config.write_text('CONFIG_TEST_USER_CHOICE=y\n')
                installer.install(framework)
                installer.install(framework)
                self.assertEqual(config.read_text(), 'CONFIG_TEST_USER_CHOICE=y\n')
                family = framework/'userpatches/config/sources/families/atlasa1.conf'
                family.write_text('# user family\n')
                with self.assertRaisesRegex(ValueError, 'modified user file'):
                    installer.install(framework)
                self.assertEqual(family.read_text(), '# user family\n')


if __name__ == '__main__':
    unittest.main()
