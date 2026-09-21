"""Extract and verify the GitHub-built runtime through an already fetched git ref."""
import argparse
import hashlib
import subprocess
from pathlib import Path

def install(root, expected):
    if not (root / 'custom-test-manifest.json').is_file():
        raise ValueError('Expected isolated Custom copy')
    def read(name):
        return subprocess.check_output(['git', 'show', 'origin/codex/netanomaly-runtime:runtime/' + name])
    revision = read('built-from.txt').decode().strip()
    if revision != expected:
        raise ValueError('Runtime source mismatch: ' + revision)
    exe = read('AnomalyNetDX11.exe')
    sha = hashlib.sha256(exe).hexdigest()
    if sha != read('sha256.txt').decode().split()[0]:
        raise ValueError('Runtime checksum mismatch')
    (root / 'bin/AnomalyNetDX11.exe').write_bytes(exe)
    (root / 'bin/built-from.txt').write_text(revision + '\n' + sha + '\n', encoding='ascii')
    print('Installed GitHub build ' + revision + ' SHA256 ' + sha)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--expected', required=True)
    args = parser.parse_args()
    install(args.root, args.expected)
