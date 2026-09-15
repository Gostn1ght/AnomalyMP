import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('dedicated', Path(__file__).resolve().parents[1] / 'server/dedicated.py')
dedicated = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dedicated)


class DedicatedConsoleTest(unittest.TestCase):
    def test_console_owns_only_server_and_reports_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe = root / 'server/bin/AnomalyGammaNetServerDX11.exe'
            exe.parent.mkdir(parents=True)
            exe.touch()
            (root / 'fsgame_server.ltx').touch()
            (root / 'appdata/server').mkdir(parents=True)
            process = Mock(pid=1234)
            process.poll.side_effect = [None, 0]
            with patch.object(dedicated.subprocess, 'Popen', return_value=process) as spawn, patch.object(dedicated.threading.Thread, 'start'):
                server = dedicated.DedicatedProcess(root)
                server.start()
                args = spawn.call_args.args[0]
                self.assertIn('-dedicated', args)
                self.assertIn('server(all/single/alife/new/portsv=1237/maxplayers=128)', args)
                self.assertEqual(sum(arg.startswith('client(') for arg in args), 1)
                self.assertIn('client(localhost/name=ServerAuthority/port=1237/portcl=1238)', args)
                self.assertEqual(spawn.call_count, 1)
                state_path = root / 'appdata/server/dedicated-process.json'
                self.assertFalse(json.loads(state_path.read_text())['gameplay_ready'])
                with self.assertRaises(RuntimeError):
                    server.start()
                server.watcher = None
                server.close()
                process.terminate.assert_called_once()
                self.assertEqual(json.loads(state_path.read_text())['state'], 'exited')


if __name__ == '__main__':
    unittest.main()
