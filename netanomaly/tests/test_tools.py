import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


profile = module('prepare_profile')
launch = module('launch_settings')


class ToolsTest(unittest.TestCase):
    def test_profile_priorities_and_duplicates(self):
        text = '+A\n+A\n+G.A.M.M.A. Books Pass Time\n-B\n+GAMMA NetAnomaly - server\n'
        result, disabled = profile.transform_modlist(text, 'client')
        self.assertEqual(result.splitlines()[1], '+GAMMA NetAnomaly - client')
        self.assertEqual(result.count('+A\n'), 1)
        self.assertIn('-G.A.M.M.A. Books Pass Time\n', result)
        self.assertEqual(disabled, ['G.A.M.M.A. Books Pass Time'])
        self.assertNotIn('+GAMMA NetAnomaly - server', result)

    def test_source_preserved_and_existing_output_rejected(self):
        modlist = profile.REPO / 'G.A.M.M.A/modpack_data/modlist.txt'
        axr = profile.REPO / 'G.A.M.M.A/modpack_patches/gamedata/scripts/axr_main.script'
        before = modlist.read_bytes(), axr.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'bundle'
            profile.prepare(modlist, output, 'server', axr)
            with self.assertRaises(ValueError):
                profile.prepare(modlist, output, 'server', axr)
            patched = next(output.rglob('axr_main.script')).read_bytes()
            self.assertEqual(patched.count(b'gamma_net_compat.install()'), 1)
            self.assertIn(b'imgui_on_render = {}', patched)
            menu = next(output.rglob('ui_main_menu.script')).read_bytes()
            self.assertEqual(menu.count(b'gamma_net_compat.unavailable()'), 4)
        self.assertEqual(before, (modlist.read_bytes(), axr.read_bytes()))

    def test_launcher_injection_and_capacity(self):
        for nickname in ['bad/name', 'name) -start server(', 'a"b', 'a b', 'a' * 33]:
            with self.assertRaises(ValueError):
                launch.settings('client', nickname=nickname)
        for players in (0, 129, -1):
            with self.assertRaises(ValueError):
                launch.settings('server', players=players)
        with self.assertRaises(ValueError):
            launch.settings('server', port=65535, client_port=65535)
        args = launch.settings('server')['arguments']
        self.assertIn('/maxplayers=128)', args)
        self.assertIn('/portsv=1237/', args)
        self.assertIn('client(localhost/', args)
        self.assertNotIn('server(', launch.settings('client')['arguments'])


if __name__ == '__main__':
    unittest.main()
