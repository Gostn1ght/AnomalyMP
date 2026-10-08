"""Targeted GAMMA loadout compatibility repair; preview unless --apply.

Keep source bytes, comments, attachments, weights and chance fields. Reject
customized/missing entries before writing. Preserve originals in a new backup
directory; atomic replacement avoids writing through a shared hard-linked file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(config_root):
    manifest = json.loads((Path(__file__).parent / 'fixtures/npc-loadouts/compatibility.json').read_text(encoding='utf-8'))
    folder = (config_root / 'items/settings/npc_loadouts').resolve(strict=True)
    if not folder.is_relative_to(config_root):
        raise ValueError('Loadout directory escapes the selected config root')
    plan = {}
    for entry in manifest:
        name = entry['file']
        if not re.fullmatch(r'npc_loadouts_[a-z_]+\.ltx', name):
            raise ValueError('Unexpected loadout filename')
        path = folder / name
        if path.is_symlink() or path.resolve(strict=True).parent != folder:
            raise ValueError('Refusing indirect loadout file')
        if path not in plan:
            original = path.read_bytes()
            plan[path] = {'original': original, 'updated': original, 'changed_rows': 0}
        item = plan[path]
        lines = item['updated'].splitlines(keepends=True)
        # Match the complete key before comments/values, never a substring.
        keys = []
        section = None
        for line in lines:
            key = line.split(b';', 1)[0].split(b'=', 1)[0].strip()
            if key.startswith(b'['):
                section = key[1:key.index(b']')].decode('ascii')
            keys.append((section, key))
        old, new = entry['old'].encode('ascii'), entry['new'].encode('ascii')
        expected = entry.get('count', 1)
        sections = entry['sections']
        if len(sections) != expected or len(set(sections)) != expected:
            raise ValueError('Unexpected section manifest')
        before = sum(key == old and section in sections for section, key in keys)
        after = sum(key == new and section in sections for section, key in keys)
        if any(key == old and section not in sections for section, key in keys):
            raise ValueError(f'Unexpected additional stale entry preserved: {name}')
        if before == 0 and after == expected:
            continue
        if before != expected or after:
            raise ValueError(f'Custom/missing/ambiguous entry preserved: {name}: {entry["old"]}')
        for i, (section, key) in enumerate(keys):
            if section in sections and key == old:
                lines[i] = lines[i].replace(old, new, 1)
        item['updated'] = b''.join(lines)
        item['changed_rows'] += expected
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configs', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    config_root = args.configs.resolve(strict=True)
    plan = prepare(config_root)  # All compatibility checks precede mutations.
    changed = {path: item for path, item in plan.items() if item['original'] != item['updated']}
    report = {'configs': str(config_root), 'apply': args.apply,
              'changed_rows': sum(item['changed_rows'] for item in changed.values()),
              'files': {str(path.relative_to(config_root)): {
                  'before': digest(item['original']), 'after': digest(item['updated']),
                  'changed_rows': item['changed_rows']} for path, item in plan.items()}}
    if args.apply and changed:
        if not args.backup_dir:
            parser.error('--apply requires --backup-dir for original files')
        backup = args.backup_dir.resolve()
        if backup.is_relative_to(config_root):
            raise ValueError('Backup must be outside the active config tree')
        backup.mkdir(parents=True, exist_ok=False)
        for path, item in changed.items():
            target = backup / path.relative_to(config_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item['original'])
        (backup / 'manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        for path, item in changed.items():
            if path.read_bytes() != item['original']:
                raise ValueError(f'Config changed during installation; backup retained: {path}')
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
                    temp_name = temp.name
                    temp.write(item['updated'])
                    temp.flush()
                    os.fsync(temp.fileno())
                os.replace(temp_name, path)
                temp_name = None
                if digest(path.read_bytes()) != report['files'][str(path.relative_to(config_root))]['after']:
                    raise ValueError(f'Installed config verification failed: {path}')
            finally:
                if temp_name:
                    Path(temp_name).unlink()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
