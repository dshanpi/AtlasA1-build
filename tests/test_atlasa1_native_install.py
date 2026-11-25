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
                    installer.subprocess, 'check_output', return_value=installer.REVISION+'\n'), patch.object(
                    installer, 'fix_family_menu'):
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

    def test_family_menu_patch_is_idempotent(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            framework = Path(folder)
            subprocess.run(['git', 'init', '-q', str(framework)], check=True)
            target = framework/'lib/functions/configuration/interactive.sh'
            target.parent.mkdir(parents=True)
            target.write_text('''function get_kernel_info_for_branch() {
	local search_branch="$1"
	local conf_file="${SRC}/config/sources/families/${BOARDFAMILY}.conf"

	# Recognises both `branch)` and `pat1 | pat2 | …)` case labels (#8957).
	awk -v branch="$search_branch" '
''', encoding='utf-8')
            installer.fix_family_menu(framework)
            first = target.read_bytes()
            installer.fix_family_menu(framework)
            self.assertEqual(first, target.read_bytes())
            self.assertIn(b'${USERPATCHES_PATH}/config/sources/families/', first)


if __name__ == '__main__':
    unittest.main()
