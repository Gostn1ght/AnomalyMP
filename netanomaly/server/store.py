"""Server-side account and player persistence, independent of SP world saves.

This is a storage component, not a client API. Engine authentication, server-owned
inventory collection and reconnect restoration must call it through a server adapter.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

ITERATIONS = 600_000
LOGIN = re.compile(r'[A-Za-z0-9_.-]{3,32}')
SECTION = re.compile(r'[A-Za-z0-9_.-]{1,128}')


def validate_state(state):
    required = {'level', 'position', 'direction', 'money', 'health', 'inventory', 'quests'}
    if not isinstance(state, dict) or set(state) != required:
        raise ValueError('Only per-player state fields are accepted')
    if not isinstance(state['level'], str) or not SECTION.fullmatch(state['level']):
        raise ValueError('Invalid level')
    for key in ('position', 'direction'):
        vector = state[key]
        if not isinstance(vector, list) or len(vector) != 3:
            raise ValueError('Invalid player vector')
        if any(type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1_000_000 for value in vector):
            raise ValueError('Invalid player coordinates')
    if type(state['money']) is not int or not 0 <= state['money'] <= 2**32 - 1:
        raise ValueError('Invalid player balance')
    if type(state['health']) not in (int, float) or not math.isfinite(state['health']) or not 0 <= state['health'] <= 1:
        raise ValueError('Invalid health')
    inventory = state['inventory']
    if not isinstance(inventory, list) or len(inventory) > 8192:
        raise ValueError('Invalid inventory')
    item_ids = set()
    for item in inventory:
        if not isinstance(item, dict) or set(item) != {'id', 'section', 'condition', 'ammo', 'properties'}:
            raise ValueError('Invalid inventory item')
        if not isinstance(item['id'], str) or not re.fullmatch(r'[0-9a-f]{32}', item['id']) or item['id'] in item_ids:
            raise ValueError('Invalid or duplicate persistent item identity')
        item_ids.add(item['id'])
        if not isinstance(item['section'], str) or not SECTION.fullmatch(item['section']):
            raise ValueError('Invalid item section')
        if type(item['condition']) not in (int, float) or not math.isfinite(item['condition']) or not 0 <= item['condition'] <= 1:
            raise ValueError('Invalid item condition')
        if type(item['ammo']) is not int or not 0 <= item['ammo'] <= 65535:
            raise ValueError('Invalid ammunition count')
        if not isinstance(item['properties'], dict):
            raise ValueError('Invalid item properties')
    if not isinstance(state['quests'], list) or len(state['quests']) > 1024:
        raise ValueError('Invalid player quests')
    payload = json.dumps(state, allow_nan=False, ensure_ascii=False, separators=(',', ':'))
    if len(payload.encode('utf-8')) > 4 * 1024**2:
        raise ValueError('Player state exceeds storage limit')
    return payload


class AccountStore:
    def __init__(self, database):
        database = Path(database)
        database.parent.mkdir(parents=True, exist_ok=True)
        self.roles_directory = database.parent / 'account_roles'
        self.roles_directory.mkdir(exist_ok=True)
        self.db = sqlite3.connect(database, isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY, login TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt BLOB NOT NULL, password_hash BLOB NOT NULL,
                iterations INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'player' CHECK(role IN ('player','admin'))
            );
            CREATE TABLE IF NOT EXISTS player_state (
                account_id TEXT PRIMARY KEY REFERENCES accounts(id),
                revision INTEGER NOT NULL CHECK(revision > 0),
                state_json TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS role_audit (
                id INTEGER PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
                role TEXT NOT NULL, changed_at INTEGER NOT NULL,
                origin TEXT NOT NULL CHECK(origin = 'local_console')
            );
            CREATE TABLE IF NOT EXISTS owned_items (
                item_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(id)
            );
        ''')

        for account_id, role in self.db.execute('SELECT id,role FROM accounts'):
            self.publish_role(account_id, role)

    def publish_role(self, account_id, role):
        if not re.fullmatch(r'[0-9a-f]{32}', account_id) or role not in ('player', 'admin'):
            raise ValueError('Invalid role record')
        target = self.roles_directory / (account_id + '.role')
        temporary = target.with_suffix('.' + secrets.token_hex(8) + '.tmp')
        try:
            with temporary.open('x', encoding='ascii', newline='\n') as output:
                output.write(f'GAMMA_ROLE_V3\n{account_id}\n{role}\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        self.db.close()

    def register(self, login, password):
        if not isinstance(login, str) or not LOGIN.fullmatch(login):
            raise ValueError('Login must contain 3..32 ASCII letters, digits, dot, underscore or hyphen')
        if not isinstance(password, str) or not 10 <= len(password) <= 256:
            raise ValueError('Password must contain 10..256 characters')
        salt = secrets.token_bytes(32)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
        account_id = uuid.uuid4().hex
        self.db.execute('INSERT INTO accounts(id,login,salt,password_hash,iterations) VALUES(?,?,?,?,?)',
                        (account_id, login, salt, hashed, ITERATIONS))
        self.publish_role(account_id, 'player')
        return account_id

    def authenticate(self, login, password):
        if not isinstance(login, str) or not LOGIN.fullmatch(login) or not isinstance(password, str) or len(password) > 256:
            return None
        row = self.db.execute('SELECT id,salt,password_hash,iterations FROM accounts WHERE login=?', (login,)).fetchone()
        salt, expected, iterations = (row[1], row[2], row[3]) if row else (bytes(32), bytes(32), ITERATIONS)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
        valid = hmac.compare_digest(actual, expected)
        return row[0] if row and valid else None

    def role(self, account_id):
        row = self.db.execute('SELECT role FROM accounts WHERE id=?', (account_id,)).fetchone()
        return row[0] if row else None

    def save_player(self, account_id, state, expected_revision=0):
        return self.save_players({account_id: (state, expected_revision)})[account_id]

    def save_players(self, changes):
        """Commit all affected player states together, including trades and ownership.

        Only a server adapter may provide these states; callers must pass the
        revisions previously read for every affected account.
        """
        if not isinstance(changes, dict) or not 1 <= len(changes) <= 128:
            raise ValueError('Invalid player transaction')
        prepared = []
        for account_id, (state, expected_revision) in changes.items():
            payload = validate_state(state)
            if type(expected_revision) is not int or expected_revision < 0:
                raise ValueError('Invalid revision')
            prepared.append((account_id, state, payload, expected_revision))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for account_id, _, _, expected_revision in prepared:
                if self.role(account_id) is None:
                    raise ValueError('Unknown account')
                row = self.db.execute('SELECT revision FROM player_state WHERE account_id=?', (account_id,)).fetchone()
                current = row[0] if row else 0
                if current != expected_revision:
                    raise ValueError('Stale player snapshot')
            # Release all affected ownership records before inserting recipients.
            # The surrounding transaction prevents visibility of intermediate states.
            self.db.executemany('DELETE FROM owned_items WHERE account_id=?',
                                [(account_id,) for account_id, _, _, _ in prepared])
            for account_id, state, payload, expected_revision in prepared:
                self.db.executemany('INSERT INTO owned_items(item_id,account_id) VALUES(?,?)',
                                    [(item['id'], account_id) for item in state['inventory']])
                self.db.execute('''INSERT INTO player_state VALUES(?,?,?,?)
                    ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,
                    state_json=excluded.state_json,updated_at=excluded.updated_at''',
                    (account_id, expected_revision + 1, payload, int(time.time())))
            self.db.execute('COMMIT')
            return {account_id: revision + 1 for account_id, _, _, revision in prepared}
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def load_player(self, account_id):
        row = self.db.execute('SELECT revision,state_json FROM player_state WHERE account_id=?', (account_id,)).fetchone()
        return (row[0], json.loads(row[1])) if row else (0, None)


class LocalConsoleAccounts:
    """Local console adapter only; never route client commands into this class."""
    def __init__(self, store):
        self.store = store

    def set_role(self, login, role):
        if role not in ('admin', 'player'):
            raise ValueError('Invalid account role')
        db = self.store.db
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('SELECT id FROM accounts WHERE login=?', (login,)).fetchone()
            if not row:
                raise ValueError('Unknown account')
            if role == 'player':
                self.store.publish_role(row[0], 'player')
            db.execute('UPDATE accounts SET role=? WHERE id=?', (role, row[0]))
            db.execute('INSERT INTO role_audit(account_id,role,changed_at,origin) VALUES(?,?,?,?)',
                       (row[0], role, int(time.time()), 'local_console'))
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
        if role == 'admin':
            self.store.publish_role(row[0], 'admin')
