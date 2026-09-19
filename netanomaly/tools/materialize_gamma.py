"""Copy installed GAMMA content to an isolated runtime without any Custom files.

Does not build or launch an engine. Original archives are mounted for reading;
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
from callback_scripts import patch_ledge, patch_ubgl, patch_dynamic_anomalies, patch_combat_schemes, patch_meet


def set_ini_values(path, section, values):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    current = None
    found = set()
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if current == section:
                for key, value in values.items():
                    if key not in found:
                        output.append(f'{key} = {value}')
                        found.add(key)
            current = stripped[1:-1].strip()
        if current == section and '=' in line and not stripped.startswith(';'):
            key = line.split('=', 1)[0].strip()
            if key in values:
                line = f'{key} = {values[key]}'
                found.add(key)
        output.append(line)
    if current == section:
        for key, value in values.items():
            if key not in found:
                output.append(f'{key} = {value}')
                found.add(key)
    elif not found:
        output.extend([f'[{section}]', *(f'{key} = {value}' for key, value in values.items())])
    path.write_text('\n'.join(output) + '\n', encoding='utf-8')


def finalize(destination):
    destination = destination.resolve(strict=True)
    marker = destination / 'gamma-runtime.json'
    report = json.loads(marker.read_text(encoding='utf-8'))
    if report.get('content') != 'GAMMA' or not report.get('content_prepared'):
        raise ValueError('GAMMA content copy has not completed')
    mp_archives = destination / 'mp'
    mp_archives.mkdir(exist_ok=True)
    # Explicit data mount also supports executables in separate role/bin folders.
    for role in ('server', 'p1', 'p2'):
        fs = destination / f'fsgame_{role}.ltx'
        lines = fs.read_text(encoding='utf-8').splitlines()
        entries = [line for line in lines if line.split('=')[0].strip() == '$game_data$']
        if len(entries) != 1:
            raise ValueError('Missing or ambiguous GAMMA data mount')
        role_root = destination / ('server' if role == 'server' else 'client')
        lines = [line for line in lines if line.split('=')[0].strip() != '$fs_root$']
        lines.insert(0, '$fs_root$ = false | false | ' + str(destination) + '\\')
        if not any(line.split('=')[0].strip() == '$game_arch_mp$' for line in lines):
            lines.insert(1, '$game_arch_mp$ = false | false | ' + str(mp_archives) + '\\')
        replacements = {
            '$arch_dir$': '$arch_dir$ = false | false | ' + str(Path(report['game']) / 'db') + '\\',
            '$game_arch_mp$': '$game_arch_mp$ = false | false | ' + str(mp_archives) + '\\',
            '$game_data$': '$game_data$ = true | true | ' + str(destination / 'gamedata') + '\\',
            '$game_config$': '$game_config$ = true | false | ' + str(role_root / 'configs') + '\\',
            '$game_scripts$': '$game_scripts$ = true | false | ' + str(role_root / 'scripts') + '\\',
        }
        fs.write_text('\n'.join(replacements.get(line.split('=')[0].strip(), line)
                                for line in lines) + '\n', encoding='utf-8')
    shutil.copytree(ROOT / 'server', destination / 'server/services', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.sqlite3', '*.sqlite3-*'))
    for role in ('server', 'client'):
        role_root = destination / role
        # Role aliases cannot see archived configs/scripts under $fs_root$/gamedata.
        # The base preparation step supplies those files in the merged loose tree.
        for directory in ('configs', 'scripts'):
            for source in (destination / 'gamedata' / directory).rglob('*'):
                if source.is_file():
                    target = role_root / directory / source.relative_to(destination / 'gamedata' / directory)
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
        (role_root / 'configs/gamma_net_role.ltx').write_text(
            '[network]\nrole = ' + role + '\nprotocol = 3\ncontent_sha256 = ' + report['inventory_sha256'] + '\n',
            encoding='ascii')
        shutil.copy2(ROOT / 'runtime/gamedata/scripts/gamma_net_compat.script',
                     role_root / 'scripts/gamma_net_compat.script')
        shutil.copy2(ROOT / 'runtime/gamedata/scripts/gamma_admin.script',
                     role_root / 'scripts/gamma_admin.script')
        for name, patch in (('axr_main.script', patch_axr), ('ui_main_menu.script', patch_menu)):
            (role_root / 'scripts' / name).write_bytes(patch((destination / 'gamedata/scripts' / name).read_bytes()))
        for name, patch in (('demonized_ledge_grabbing.script', patch_ledge), ('ubgl_no_3db.script', patch_ubgl),
                            ('drx_da_main.script', patch_dynamic_anomalies),
                            ('schemes_ai_gamma.script', patch_combat_schemes), ('xr_meet.script', patch_meet)):
            source = destination / 'gamedata/scripts' / name
            if source.is_file():
                (role_root / 'scripts' / name).write_bytes(patch(source.read_bytes()))
        for name in DEBUG_SCRIPTS:
            original = destination / 'gamedata/scripts' / name
            if original.is_file():
                (role_root / 'scripts' / name).write_bytes(patch_debug(original.read_bytes(), name))
    # A dedicated process has no character-creation UI. Supply the GAMMA values
    # which that UI normally writes so ALife creates its authority actor on the
    # Great Swamps instead of falling back to an arbitrary/default location.
    server_options = destination / 'server/configs/axr_options.ltx'
    if server_options.is_file():
        set_ini_values(server_options, 'character_creation', {
            'new_game_faction': 'csky',
            'new_game_map': 'hidden_base',
        })
    report['server_storage_component_prepared'] = True
    report['server_storage_engine_integration'] = False
    report['player_storage'] = 'appdata/server/accounts.sqlite3'
    marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def inventory(game, engine_data, profile, base_data=()):
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
    # Extracted configs/scripts are the lowest priority layer. Their role aliases
    # cannot resolve entries indexed under the common gamedata archive root.
    layers = [('GAMMA extracted base', folder) for folder in base_data]
    layers += [('GAMMA base', game / 'gamedata'), ('NetAnomaly engine data', engine_data)]
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


def materialize(game, engine_data, destination, profile='G.A.M.M.A', copy=False, base_data=()):
    game = game.resolve(strict=True)
    engine_data = engine_data.resolve(strict=True)
    destination = destination.resolve()
    if not engine_data.is_dir() or engine_data.name.casefold() != 'gamedata':
        raise ValueError('Engine input must be its gamedata directory, not a Custom test installation')
    if Path(profile).name != profile or profile in ('.', '..'):
        raise ValueError('Invalid profile name')
    base_data = [folder.resolve(strict=True) for folder in base_data]
    for original in (game, engine_data, *base_data):
        if destination == original or original in destination.parents or destination in original.parents:
            raise ValueError('Destination overlaps original content')
    winners, disabled, profile_hash = inventory(game, engine_data, profile, base_data)
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
              'base_data': [str(folder) for folder in base_data],
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
        (role_root / 'configs/gamma_net_role.ltx').write_text('[network]\nrole = ' + role + '\nprotocol = 3\n', encoding='ascii')
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
            '$game_scripts$': '$game_scripts$ = true | false | $game_data$ | scripts\\',
            '$game_config$': '$game_config$ = true | false | $game_data$ | configs\\',
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
    parser.add_argument('--base-data', type=Path, action='append', default=[],
                        help='Extracted original GAMMA archive tree (configs/scripts); may be repeated')
    parser.add_argument('--copy', action='store_true')
    parser.add_argument('--finalize-only', action='store_true')
    args = parser.parse_args()
    if args.finalize_only:
        print(json.dumps(finalize(args.destination), ensure_ascii=False, indent=2))
    else:
        if args.engine_data is None:
            parser.error('--engine-data is required when preparing content')
        materialize(args.game, args.engine_data, args.destination, args.profile, args.copy, args.base_data)
