"""Copy installed GAMMA content to an isolated runtime without any Custom files.

Does not build or launch an engine. Original archives are mounted read-only;
winning loose files are copied independently, never hardlinked.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from prepare_gamma import DEFAULT_GAME
from prepare_profile import POLICY, ROOT, patch_axr, patch_menu
from admin_scripts import DEBUG_SCRIPTS, patch_debug


def finalize(destination):
    destination = destination.resolve(strict=True)
    marker = destination / 'gamma-runtime.json'
    report = json.loads(marker.read_text(encoding='utf-8'))
    if report.get('content') != 'GAMMA' or not report.get('content_prepared'):
        raise ValueError('GAMMA content copy has not completed')
    # Explicit data mount also supports executables in separate role/bin folders.
    for role in ('server', 'p1', 'p2'):
        fs = destination / f'fsgame_{role}.ltx'
        lines = fs.read_text(encoding='utf-8').splitlines()
        entries = [line for line in lines if line.split('=')[0].strip() == '$game_data$']
        if len(entries) != 1:
            raise ValueError('Missing or ambiguous GAMMA data mount')
        replacement = '$game_data$ = true | true | ' + str(destination / 'gamedata') + '\\'
        fs.write_text('\n'.join(replacement if line == entries[0] else line for line in lines) + '\n', encoding='utf-8')
    shutil.copytree(ROOT / 'server', destination / 'server/services', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.sqlite3', '*.sqlite3-*'))
    for role in ('server', 'client'):
        role_root = destination / role
        (role_root / 'configs/gamma_net_role.ltx').write_text(
            '[network]\nrole = ' + role + '\nprotocol = 3\ncontent_sha256 = ' + report['inventory_sha256'] + '\n',
            encoding='ascii')
        shutil.copy2(ROOT / 'runtime/gamedata/scripts/gamma_net_compat.script',
                     role_root / 'scripts/gamma_net_compat.script')
        shutil.copy2(ROOT / 'runtime/gamedata/scripts/gamma_admin.script',
                     role_root / 'scripts/gamma_admin.script')
        for name in DEBUG_SCRIPTS:
            original = destination / 'gamedata/scripts' / name
            if original.is_file():
                (role_root / 'scripts' / name).write_bytes(patch_debug(original.read_bytes(), name))
    report['server_storage_component_prepared'] = True
    report['server_storage_engine_integration'] = False
    report['player_storage'] = 'appdata/server/accounts.sqlite3'
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def inventory(game, engine_data, profile):
    mo2 = game / 'GAMMA RC3.7'
    modlist = mo2 / 'profiles' / profile / 'modlist.txt'
    data = modlist.read_bytes()
    names = list(dict.fromkeys(line[1:] for line in data.decode('utf-8-sig').splitlines()
                               if line.startswith('+') and not line.endswith('_separator')))
    disabled = [name for name in names if name in POLICY['disabled_mods']]
    names = [name for name in names if name not in POLICY['disabled_mods']]
    missing = [name for name in names if not (mo2 / 'mods' / name).is_dir()]
    if missing:
        raise ValueError('Missing enabled GAMMA mods: ' + ', '.join(missing))
    layers = [('GAMMA base', game / 'gamedata'), ('NetAnomaly engine data', engine_data)]
    layers += [(name, mo2 / 'mods' / name / 'gamedata') for name in reversed(names)]
    layers.append(('GAMMA overwrite', mo2 / 'overwrite/gamedata'))
    winners = {}
    for layer, folder in layers:
        for directory, _, files in os.walk(folder):
            for name in files:
                source = Path(directory) / name
                relative = source.relative_to(folder)
                winners[str(relative).casefold()] = (source, relative, layer)
    if not winners:
        raise ValueError('No GAMMA content found')
    return winners, disabled, hashlib.sha256(data).hexdigest()


def materialize(game, engine_data, destination, profile='G.A.M.M.A', copy=False):
    game = game.resolve(strict=True)
    engine_data = engine_data.resolve(strict=True)
    destination = destination.resolve()
    if not engine_data.is_dir() or engine_data.name.casefold() != 'gamedata':
        raise ValueError('Engine input must be its gamedata directory, not a Custom test installation')
    if Path(profile).name != profile or profile in ('.', '..'):
        raise ValueError('Invalid profile name')
    for original in (game, engine_data):
        if destination == original or original in destination.parents or destination in original.parents:
            raise ValueError('Destination overlaps original content')
    winners, disabled, profile_hash = inventory(game, engine_data, profile)
    size = sum(source.stat().st_size for source, _, _ in winners.values())
    fingerprint = hashlib.sha256()
    for source, relative, layer in sorted(winners.values(), key=lambda item: str(item[1]).casefold()):
        stat = source.stat()
        fingerprint.update(f'{relative}|{source}|{layer}|{stat.st_size}|{stat.st_mtime_ns}\n'.encode())
    fingerprint = fingerprint.hexdigest()
    parent = destination.parent
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    report = {'content': 'GAMMA', 'game': str(game), 'engine_data': str(engine_data),
              'profile': profile, 'profile_sha256': profile_hash,
              'inventory_sha256': fingerprint, 'files': len(winners), 'bytes': size,
              'free_bytes': free, 'destination': str(destination), 'disabled_mods': disabled,
              'content_prepared': False, 'multiplayer_ready': False,
              'build_environment': 'github_actions_only'}
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not copy:
        return report
    marker = destination / 'gamma-runtime.json'
    if destination.exists():
        if not marker.is_file():
            raise ValueError('Destination is not a marked GAMMA runtime')
        old = json.loads(marker.read_text(encoding='utf-8'))
        if old['inventory_sha256'] != fingerprint:
            raise ValueError('Source content changed; use a new destination')
    elif free < size + 5 * 1024**3:
        raise ValueError('Insufficient space for an independent GAMMA copy')
    # Validate callback patches before the expensive copy.
    axr = winners[str(Path('scripts/axr_main.script')).casefold()][0]
    menu = winners[str(Path('scripts/ui_main_menu.script')).casefold()][0]
    patched_axr, patched_menu = patch_axr(axr.read_bytes()), patch_menu(menu.read_bytes())
    destination.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    start = time.monotonic()

    def copy_file(item):
        source, relative, _ = item
        target = destination / 'gamedata' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size == source.stat().st_size and target.stat().st_mtime_ns == source.stat().st_mtime_ns:
            return
        shutil.copy2(source, target)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, _ in enumerate(pool.map(copy_file, winners.values()), 1):
            if index % 5000 == 0:
                print(f'GAMMA: {index}/{len(winners)} files copied ({time.monotonic() - start:.0f}s)', flush=True)
    provenance = {str(relative): {'source': str(source), 'layer': layer}
                  for source, relative, layer in winners.values()}
    (destination / 'content-provenance.json').write_text(json.dumps(provenance, ensure_ascii=False), encoding='utf-8')
    fs_base = (game / 'fsgame.ltx').read_text(encoding='utf-8-sig')
    for role in ('server', 'client'):
        role_root = destination / role
        (role_root / 'bin').mkdir(parents=True, exist_ok=True)
        shutil.copytree(destination / 'gamedata/scripts', role_root / 'scripts', dirs_exist_ok=True)
        shutil.copytree(destination / 'gamedata/configs', role_root / 'configs', dirs_exist_ok=True)
        (role_root / 'scripts/axr_main.script').write_bytes(patched_axr)
        (role_root / 'scripts/ui_main_menu.script').write_bytes(patched_menu)
        shutil.copy2(ROOT / 'runtime/gamedata/scripts/gamma_net_compat.script', role_root / 'scripts')
        (role_root / 'configs/gamma_net_role.ltx').write_text('[network]\nrole = ' + role + '\nprotocol = 2\n', encoding='ascii')
        for name in ('discord_game_sdk.dll', 'icudt65.dll', 'icuuc65.dll', 'soft_oal.dll', 'tbb.dll'):
            source = game / 'bin' / name
            if source.is_file():
                shutil.copy2(source, role_root / 'bin' / name)
    for process_role in ('server', 'p1', 'p2'):
        role = 'server' if process_role == 'server' else 'client'
        appdata = destination / 'appdata' / process_role
        appdata.mkdir(parents=True, exist_ok=True)
        for name in ('user.ltx', 'axr_options.ltx', 'localization.ltx'):
            source = game / 'appdata' / name
            if source.is_file():
                shutil.copy2(source, appdata / name)
        mounts = {
            '$game_data$': '$game_data$ = true | true | ' + str(destination / 'gamedata') + '\\',
            '$app_data_root$': '$app_data_root$ = true | false | ' + str(appdata) + '\\',
            '$arch_dir$': '$arch_dir$ = false | false | ' + str(game) + '\\ | db\\',
            '$game_scripts$': '$game_scripts$ = true | false | ' + str(destination / role / 'scripts') + '\\',
            '$game_config$': '$game_config$ = true | false | ' + str(destination / role / 'configs') + '\\',
        }
        lines = [mounts.get(line.split('=')[0].strip(), line) for line in fs_base.splitlines()]
        (destination / f'fsgame_{process_role}.ltx').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    report['content_prepared'] = True
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report = finalize(destination)
    print('GAMMA content prepared. No engine built or launched.', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--game', type=Path, default=DEFAULT_GAME)
    parser.add_argument('--engine-data', type=Path)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--profile', default='G.A.M.M.A')
    parser.add_argument('--copy', action='store_true')
    parser.add_argument('--finalize-only', action='store_true')
    args = parser.parse_args()
    if args.finalize_only:
        print(json.dumps(finalize(args.destination), ensure_ascii=False, indent=2))
    else:
        if args.engine_data is None:
            parser.error('--engine-data is required when preparing content')
        materialize(args.game, args.engine_data, args.destination, args.profile, args.copy)
