"""Local account console for the server storage component (engine not connected yet)."""
import argparse
import getpass
import json
from pathlib import Path
import shlex

from store import AccountStore, LocalConsoleAccounts
from tickets import issue_ticket


def run(runtime):
    runtime = runtime.resolve(strict=True)
    manifest = json.loads((runtime / 'gamma-runtime.json').read_text(encoding='utf-8'))
    if manifest.get('content') != 'GAMMA' or not manifest.get('content_prepared'):
        raise ValueError('Expected a prepared isolated GAMMA runtime')
    db = AccountStore(runtime / 'appdata/server/accounts.sqlite3')
    local = LocalConsoleAccounts(db)
    print('GAMMA local account console. Engine integration is not connected.')
    print('Commands: register LOGIN, accounts, admin LOGIN, unadmin LOGIN, ticket LOGIN p1|p2, quit')
    try:
        while True:
            try:
                command = shlex.split(input('accounts> '))
            except (EOFError, KeyboardInterrupt):
                break
            except ValueError as error:
                print(error)
                continue
            if not command:
                continue
            try:
                if command == ['quit']:
                    break
                if command == ['accounts']:
                    for login, role in db.db.execute('SELECT login,role FROM accounts ORDER BY login'):
                        print(f'{login}: {role}')
                elif len(command) == 2 and command[0] == 'register':
                    password = getpass.getpass('Password: ')
                    if getpass.getpass('Confirm password: ') != password:
                        raise ValueError('Passwords do not match')
                    db.register(command[1], password)
                    del password
                    print('Account registered with player role.')
                elif len(command) == 2 and command[0] in ('admin', 'unadmin'):
                    role = 'admin' if command[0] == 'admin' else 'player'
                    local.set_role(command[1], role)
                    print(f'{command[1]}: {role}')
                elif len(command) == 3 and command[0] == 'ticket' and command[2] in ('p1', 'p2'):
                    password = getpass.getpass('Password: ')
                    token = issue_ticket(db, runtime / 'appdata/server/auth_tickets', command[1],
                                         password, manifest['inventory_sha256'])
                    del password
                    destination = runtime / 'appdata' / command[2] / 'gamma_ticket.txt'
                    temporary = destination.with_suffix('.tmp')
                    temporary.write_text(token + '\n', encoding='ascii')
                    temporary.replace(destination)
                    print('Single-use client ticket staged; expires in 5 minutes.')
                else:
                    print('Unknown command. No engine commands are exposed by this console.')
            except Exception as error:
                print(str(error))
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    run(args.runtime)
