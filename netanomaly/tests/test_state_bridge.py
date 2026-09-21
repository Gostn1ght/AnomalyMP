import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

SERVER = Path(__file__).resolve().parents[1] / 'server'
sys.path.insert(0, str(SERVER))
spec = importlib.util.spec_from_file_location('state_bridge', SERVER / 'bridge.py')
bridge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_module)


def player_state(money=100):
    return {'level': 'l01_escape', 'position': [1, 2, 3], 'direction': [0, 0, 1],
            'money': money, 'health': 0.75, 'quests': [],
            'inventory': [{'id': '1' * 32, 'section': 'wpn_ak74',
                           'condition': 0.5, 'ammo': 30, 'properties': {}}]}


class StateBridgeTest(unittest.TestCase):
    def request(self, service, value):
        name = uuid.uuid4().hex + '.json'
        (service.inbox / name).write_text(json.dumps(value), encoding='utf-8')
        self.assertEqual(service.process_available(), 1)
        directory = service.outbox if (service.outbox / name).exists() else service.failed
        return json.loads((directory / name).read_text(encoding='utf-8'))

    def test_server_local_save_load_and_revision_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp)
            service = bridge_module.StateBridge(appdata)
            try:
                account = service.store.register('BridgePlayer', 'bridge-password')
                saved = self.request(service, {'magic': bridge_module.MAGIC, 'operation': 'save',
                                               'account': account, 'revision': 0,
                                               'state': player_state()})
                self.assertEqual(saved, {'magic': bridge_module.MAGIC, 'ok': True, 'revision': 1})
                loaded = self.request(service, {'magic': bridge_module.MAGIC, 'operation': 'load',
                                                'account': account})
                self.assertEqual((loaded['revision'], loaded['state']), (1, player_state()))
                stale = self.request(service, {'magic': bridge_module.MAGIC, 'operation': 'save',
                                               'account': account, 'revision': 0,
                                               'state': player_state(999)})
                self.assertFalse(stale['ok'])
                self.assertEqual(service.store.load_player(account), (1, player_state()))
            finally:
                service.close()

    def test_rejects_world_state_and_bad_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = bridge_module.StateBridge(Path(tmp))
            try:
                account = service.store.register('BridgePlayer', 'bridge-password')
                value = player_state()
                value['world'] = {'alife': 'forbidden'}
                result = self.request(service, {'magic': bridge_module.MAGIC, 'operation': 'save',
                                                'account': account, 'revision': 0, 'state': value})
                self.assertFalse(result['ok'])
                (service.inbox / 'client-chosen.json').write_text('{}', encoding='utf-8')
                service.process_available()
                self.assertTrue((service.failed / 'client-chosen.json').exists())
            finally:
                service.close()


if __name__ == '__main__':
    unittest.main()
