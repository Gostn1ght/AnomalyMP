"""Issue short-lived, single-use local tickets consumed by the native engine."""
import os
from pathlib import Path
import re
import secrets
import time


def issue_ticket(store, directory, login, password, content_sha256, now=None):
    if not isinstance(content_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', content_sha256):
        raise ValueError('Invalid GAMMA content fingerprint')
    account_id = store.authenticate(login, password)
    if account_id is None:
        raise ValueError('Authentication failed')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    expiry = int(time.time() if now is None else now) + 300
    data = f'GAMMA_AUTH_V3\n{account_id}\n{content_sha256}\n{expiry}\n'
    temporary = directory / (token + '.tmp')
    with temporary.open('x', encoding='ascii', newline='\n') as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(directory / (token + '.ticket'))
    return token
