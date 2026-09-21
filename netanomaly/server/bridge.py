"""Server-local spool bridge between the native dedicated process and SQLite.

The directory lives below the dedicated server's appdata. Clients never receive a
path or network message for this protocol; the authenticated native server writes
requests and this worker commits them through AccountStore.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time

try:
    from .store import AccountStore
except ImportError:  # Direct execution from the deployed server directory.
    from store import AccountStore

MAGIC = 'GAMMA_PLAYER_STATE_V1'
REQUEST_NAME = re.compile(r'[0-9a-f]{32}\.json')
MAX_REQUEST = 4 * 1024**2 + 4096


class StateBridge:
    def __init__(self, appdata):
        self.root = Path(appdata).resolve(strict=True)
        self.inbox = self.root / 'player_state_bridge' / 'inbox'
        self.outbox = self.root / 'player_state_bridge' / 'outbox'
        self.failed = self.root / 'player_state_bridge' / 'failed'
        for directory in (self.inbox, self.outbox, self.failed):
            directory.mkdir(parents=True, exist_ok=True)
        self.store = AccountStore(self.root / 'accounts.sqlite3')

    def close(self):
        self.store.close()

    @staticmethod
    def _read(path):
        if not REQUEST_NAME.fullmatch(path.name) or path.stat().st_size > MAX_REQUEST:
            raise ValueError('Invalid bridge request')
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict) or value.get('magic') != MAGIC:
            raise ValueError('Invalid bridge protocol')
        return value

    @staticmethod
    def _publish(directory, name, value):
        temporary = directory / (name + '.tmp')
        destination = directory / name
        data = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')) + '\n'
        with temporary.open('x', encoding='utf-8', newline='\n') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)

    def process(self, path):
        request = self._read(path)
        if set(request) == {'magic', 'operation', 'account'} and request['operation'] == 'load':
            revision, state = self.store.load_player(request['account'])
            result = {'magic': MAGIC, 'ok': True, 'revision': revision, 'state': state}
        elif (set(request) == {'magic', 'operation', 'account', 'revision', 'state'} and
              request['operation'] == 'save'):
            revision = self.store.save_player(request['account'], request['state'], request['revision'])
            result = {'magic': MAGIC, 'ok': True, 'revision': revision}
        else:
            raise ValueError('Invalid bridge operation')
        self._publish(self.outbox, path.name, result)
        path.unlink()

    def process_available(self):
        processed = 0
        for path in sorted(self.inbox.iterdir()):
            if not path.is_file() or path.suffix == '.tmp':
                continue
            try:
                self.process(path)
            except Exception as error:
                result = {'magic': MAGIC, 'ok': False, 'error': str(error)[:512]}
                try:
                    self._publish(self.failed, path.name, result)
                finally:
                    path.unlink(missing_ok=True)
            processed += 1
        return processed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--appdata', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=float, default=0.05)
    args = parser.parse_args()
    bridge = StateBridge(args.appdata)
    try:
        while True:
            bridge.process_available()
            if args.once:
                break
            time.sleep(max(0.01, min(args.interval, 1.0)))
    finally:
        bridge.close()


if __name__ == '__main__':
    main()
