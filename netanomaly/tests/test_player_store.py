import copy
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('player_store', Path(__file__).resolve().parents[1] / 'server/store.py')
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)
session_spec = importlib.util.spec_from_file_location('player_sessions', Path(__file__).resolve().parents[1] / 'server/sessions.py')
sessions = importlib.util.module_from_spec(session_spec)
session_spec.loader.exec_module(sessions)
ticket_spec = importlib.util.spec_from_file_location('player_tickets', Path(__file__).resolve().parents[1] / 'server/tickets.py')
tickets = importlib.util.module_from_spec(ticket_spec)
ticket_spec.loader.exec_module(tickets)


def state(money, item_id='1' * 32):
    return {'level': 'l01_escape', 'position': [1, 2, 3], 'direction': [0, 0, 1],
            'money': money, 'health': 0.75, 'quests': [{'id': 'random_task', 'progress': 0}],
            'inventory': [{'id': item_id, 'section': 'wpn_ak74', 'condition': 0.42,
                           'ammo': 17, 'properties': {'scope': True}}]}


class PlayerStoreTest(unittest.TestCase):
    def test_native_role_mirror_and_tickets(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = store.AccountStore(Path(tmp) / 'accounts.sqlite3')
            try:
                account = db.register('Stalker', 'stalker-password')
                role_file = Path(tmp) / 'account_roles' / (account + '.role')
                self.assertEqual(role_file.read_text(), f'GAMMA_ROLE_V3\n{account}\nplayer\n')
                local = store.LocalConsoleAccounts(db)
                local.set_role('Stalker', 'admin')
                self.assertEqual(role_file.read_text().splitlines()[-1], 'admin')
                local.set_role('Stalker', 'player')
                self.assertEqual(role_file.read_text().splitlines()[-1], 'player')
                directory = Path(tmp) / 'auth_tickets'
                with self.assertRaises(ValueError):
                    tickets.issue_ticket(db, directory, 'Stalker', 'wrong', 'a' * 64, now=1000)
                self.assertFalse(directory.exists())
                token = tickets.issue_ticket(db, directory, 'Stalker', 'stalker-password', 'a' * 64, now=1000)
                self.assertEqual(len(token), 64)
                self.assertEqual((directory / (token + '.ticket')).read_text(),
                                 f'GAMMA_AUTH_V3\n{account}\n' + 'a' * 64 + '\n1300\n')
            finally:
                db.close()

    def test_session_capacity_boundary(self):
        class FakeAuthentication:
            def authenticate(self, login, password):
                return login
        peers = sessions.PlayerSessions(FakeAuthentication())
        for peer_id in range(1, 129):
            peers.login(peer_id, str(peer_id), 'test')
        with self.assertRaises(ValueError):
            peers.login(129, 'extra', 'test')
        self.assertEqual(len(peers.peers), 128)

    def test_session_authentication_admin_and_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = store.AccountStore(Path(tmp) / 'server.sqlite3')
            try:
                account_id = db.register('Stalker', 'stalker-password')
                peers = sessions.PlayerSessions(db)
                with self.assertRaises(ValueError):
                    peers.checkpoint(1001, state(123), 0)
                self.assertFalse(peers.is_admin(1001))
                self.assertEqual(peers.login(1001, 'Stalker', 'stalker-password'), account_id)
                with self.assertRaises(ValueError):
                    peers.login(1002, 'STALKER', 'stalker-password')
                self.assertFalse(peers.is_admin(1001))
                store.LocalConsoleAccounts(db).set_role('Stalker', 'admin')
                self.assertTrue(peers.is_admin(1001))
                store.LocalConsoleAccounts(db).set_role('Stalker', 'player')
                self.assertFalse(peers.is_admin(1001))
                self.assertEqual(peers.disconnect(1001, state(123), 0), 1)
                with self.assertRaises(ValueError):
                    peers.load_player(1001)
                peers.login(1002, 'Stalker', 'stalker-password')
                self.assertEqual(peers.load_player(1002), (1, state(123)))
            finally:
                db.close()
    def test_account_identity_roles_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'server.sqlite3'
            db = store.AccountStore(path)
            try:
                first = db.register('PlayerOne', 'correct-password-one')
                second = db.register('PlayerTwo', 'correct-password-two')
                self.assertEqual(db.role(first), 'player')
                self.assertEqual(db.role(second), 'player')
                self.assertEqual(db.authenticate('playerone', 'correct-password-one'), first)
                self.assertIsNone(db.authenticate('PlayerOne', 'wrong-password'))
                with self.assertRaises(sqlite3.IntegrityError):
                    db.register('PLAYERONE', 'other-password')
                self.assertEqual(db.save_player(first, state(100)), 1)
                self.assertEqual(db.save_player(second, state(200, '2' * 32)), 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    db.save_player(second, state(999), expected_revision=1)
                self.assertEqual(db.load_player(second), (1, state(200, '2' * 32)))
                store.LocalConsoleAccounts(db).set_role('PlayerOne', 'admin')
                self.assertEqual(db.role(first), 'admin')
                self.assertEqual(db.role(second), 'player')
            finally:
                db.close()
            db = store.AccountStore(path)
            try:
                self.assertEqual(db.load_player(first), (1, state(100)))
                self.assertEqual(db.load_player(second), (1, state(200, '2' * 32)))
                stale = state(999)
                with self.assertRaises(ValueError):
                    db.save_player(first, stale)
                self.assertEqual(db.load_player(first), (1, state(100)))
                self.assertEqual(db.save_player(first, stale, expected_revision=1), 2)
                self.assertEqual(db.load_player(second), (1, state(200, '2' * 32)))
                self.assertNotIn('correct-password-one', path.read_bytes().decode('latin1'))
            finally:
                db.close()

    def test_no_world_snapshot_or_invalid_inventory(self):
        for change in ('world', 'nan', 'duplicate_item', 'negative_money'):
            data = copy.deepcopy(state(100))
            if change == 'world':
                data['world'] = {'alife': 'SP snapshot'}
            elif change == 'nan':
                data['position'][0] = float('nan')
            elif change == 'duplicate_item':
                data['inventory'].append(copy.deepcopy(data['inventory'][0]))
            else:
                data['money'] = -1
            with self.assertRaises(ValueError):
                store.validate_state(data)

    def test_atomic_item_and_money_transfer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = store.AccountStore(Path(tmp) / 'server.sqlite3')
            try:
                sender = db.register('Sender', 'sender-password')
                buyer = db.register('Buyer', 'buyer-password')
                one, two = state(100), state(200, '2' * 32)
                db.save_players({sender: (one, 0), buyer: (two, 0)})
                transferred_one, transferred_two = copy.deepcopy(one), copy.deepcopy(two)
                transferred_two['inventory'].append(transferred_one['inventory'].pop())
                transferred_one['money'] += 75
                transferred_two['money'] -= 75
                with self.assertRaises(ValueError):
                    db.save_players({sender: (transferred_one, 1), buyer: (transferred_two, 0)})
                self.assertEqual(db.load_player(sender), (1, one))
                self.assertEqual(db.load_player(buyer), (1, two))
                revisions = db.save_players({sender: (transferred_one, 1), buyer: (transferred_two, 1)})
                self.assertEqual(revisions, {sender: 2, buyer: 2})
                self.assertEqual(db.load_player(sender), (2, transferred_one))
                self.assertEqual(db.load_player(buyer), (2, transferred_two))
                self.assertEqual(db.db.execute('SELECT account_id FROM owned_items WHERE item_id=?', ('1' * 32,)).fetchone()[0], buyer)
            finally:
                db.close()
