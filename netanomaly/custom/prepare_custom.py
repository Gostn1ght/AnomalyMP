"""Materialize a separate Custom test gamedata using MO2's actual winning files."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path


def inventory(game, mo2, profile, engine):
    layers = [('base-loose', game / 'gamedata'), ('engine-data', engine / 'gamedata')]
    text = (mo2 / 'profiles' / profile / 'modlist.txt').read_text(encoding='utf-8-sig')
    names, seen = [], set()
    for line in text.splitlines():
        if not line.startswith('+') or line.endswith('_separator'):
            continue
        name = line[1:]
        if name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
    missing = []
    for name in reversed(names):
        folder = mo2 / 'mods' / name
        if not folder.is_dir():
            missing.append(name)
            continue
        data = folder / 'gamedata'
        if data.is_dir():
            layers.append((name, data))
    if missing:
        raise ValueError('Enabled mods missing: ' + ', '.join(missing))
    if (mo2 / 'overwrite/gamedata').is_dir():
        layers.append(('MO2 overwrite', mo2 / 'overwrite/gamedata'))
    winners = {}
    for name, root in layers:
        if not root.is_dir():
            continue
        for directory, _, files in os.walk(root):
            for filename in files:
                source = Path(directory) / filename
                relative = source.relative_to(root)
                winners[str(relative).casefold()] = (source, relative, name, source.stat().st_size)
    return winners, names


def prepare(game, mo2, profile, engine, destination, copy=False):
    for path in (game, mo2, engine):
        if not path.is_dir():
            raise ValueError('Missing input: ' + str(path))
    destination = destination.resolve()
    if destination == game.resolve() or game.resolve() in destination.parents:
        raise ValueError('Test copy must be outside the installed game')
    winners, names = inventory(game, mo2, profile, engine)
    size = sum(item[3] for item in winners.values())
    report = {'game': str(game), 'profile': profile, 'destination': str(destination),
              'enabled_mods': len(names), 'files': len(winners), 'bytes': size,
              'free_bytes': shutil.disk_usage(destination.parent).free,
              'archives': 'Read-only paths to the installed game; loose gamedata is copied.'}
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not copy:
        return
    marker = destination / 'custom-test-manifest.json'
    if destination.exists() and not marker.exists():
        raise ValueError('Refusing to overwrite an unmarked directory')
    if report['free_bytes'] < size + 5 * 1024**3 and not destination.exists():
        raise ValueError('Not enough free space for an independent gamedata copy')
    destination.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    start = time.monotonic()

    def copy_file(item):
        source, relative, _, _ = item
        target = destination / 'gamedata' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Resumable only inside our marked test directory. Never link writable data.
        if target.exists() and target.stat().st_size == source.stat().st_size and target.stat().st_mtime_ns == source.stat().st_mtime_ns:
            return
        shutil.copy2(source, target)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index, _ in enumerate(pool.map(copy_file, winners.values()), 1):
            if index % 10000 == 0:
                print(f'Copied {index}/{len(winners)} files in {time.monotonic() - start:.0f}s', flush=True)
    provenance = {str(v[1]): {'layer': v[2], 'source': str(v[0]), 'bytes': v[3]} for v in winners.values()}
    (destination / 'gamedata-provenance.json').write_text(json.dumps(provenance, ensure_ascii=False), encoding='utf-8')
    (destination / 'bin').mkdir(exist_ok=True)
    for name in ('discord_game_sdk.dll', 'icudt65.dll', 'icuuc65.dll', 'soft_oal.dll', 'tbb.dll'):
        source = game / 'bin' / name
        if source.is_file():
            shutil.copy2(source, destination / 'bin' / name)
    fs_base = (game / 'fsgame.ltx').read_text(encoding='utf-8-sig')
    user = game / 'appdata/user.ltx'
    config = user.read_text(encoding='utf-8-sig') if user.exists() else ''
    for key, value in {'rs_fullscreen': 'off', 'vid_mode': '1280x720', 'net_cl_update_rate': '30',
                       'net_sv_update_rate': '30', 'net_cl_interpolation': '0.1'}.items():
        config = re.sub(r'(?m)^' + key + r'\s+.*\n?', '', config) + '\n' + key + ' ' + value + '\n'
    for role in ('server', 'p1', 'p2'):
        appdata = destination / ('appdata_' + role)
        appdata.mkdir(exist_ok=True)
        (appdata / 'user.ltx').write_text(config, encoding='utf-8')
        for name in ('axr_options.ltx', 'localization.ltx'):
            old = game / 'appdata' / name
            if old.exists():
                shutil.copy2(old, appdata / name)
        lines = []
        for line in fs_base.splitlines():
            if line.startswith('$app_data_root$'):
                line = '$app_data_root$ = true | false | $fs_root$ | appdata_' + role + '\\'
            elif line.startswith('$arch_dir$'):
                line = '$arch_dir$ = false | false | ' + str(game) + '\\ | db\\'
            lines.append(line)
        (destination / ('fsgame_' + role + '.ltx')).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Custom test data ready in {time.monotonic() - start:.0f}s', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--game', type=Path, required=True)
    p.add_argument('--mo2', type=Path, required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--copy', action='store_true')
    prepare(**vars(p.parse_args()))
