"""GHA-only production key injection; no key value is printed or packaged."""
from pathlib import Path
import os
import re
import hashlib
import json
if os.environ.get('GITHUB_ACTIONS') != 'true': raise SystemExit('Production engine is built only in GitHub Actions')
value = os.environ.get('LZPACK_KEY_HEX', '')
if not re.fullmatch('[a-fA-F0-9]{64}', value): raise SystemExit('LZPACK_KEY_V1 secret is missing or invalid')
key = bytes.fromhex(value)
root = Path(__file__).resolve().parents[2]
path = root/'src/xrCore/_lzpack_key.generated.h'
path.write_text('#pragma once\nstatic const unsigned char lzpack_master_key[32] = {' +
                ','.join(str(v) for v in key) + '};\n', encoding='ascii')
manifest=root/'_build/lzpack-format.json'
manifest.parent.mkdir(parents=True,exist_ok=True)
manifest.write_text(json.dumps({'format':'LZPACK1','key_id':'v1','key_fingerprint':hashlib.sha256(key).hexdigest()[:16]}))
print('Archive key injected into compiler input; it is excluded from artifacts')
