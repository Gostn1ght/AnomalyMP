"""Prepare an isolated GAMMA migration bundle; never install a Custom binary."""
import argparse
import json
from pathlib import Path

from prepare_profile import prepare

DEFAULT_GAME = Path(r'C:\Users\Mahito\Downloads\GAMMA\GAMMA')


def winning_file(game, mo2, lines, relative):
    # MO2 stores enabled mods in descending priority; overwrite wins over all mods.
    candidates = [mo2 / 'overwrite' / relative]
    candidates += [mo2 / 'mods' / line[1:] / relative
                   for line in lines if line.startswith('+')]
    candidates.append(game / relative)
    return next((path for path in candidates if path.is_file()), None)


def migrate(game, output, profile='G.A.M.M.A'):
    game, output = game.resolve(strict=True), output.resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new directory')
    if output == game or game in output.parents:
        raise ValueError('Prepare outside the original GAMMA installation')
    if Path(profile).name != profile or profile in ('.', '..'):
        raise ValueError('Profile must be a single directory name')
    mo2 = game / 'GAMMA RC3.7'
    modlist = mo2 / 'profiles' / profile / 'modlist.txt'
    lines = modlist.read_text(encoding='utf-8-sig').splitlines()
    missing = [line[1:] for line in lines if line.startswith('+')
               and not line.endswith('_separator')
               and not (mo2 / 'mods' / line[1:]).is_dir()]
    axr = winning_file(game, mo2, lines, Path('gamedata/scripts/axr_main.script'))
    menu = winning_file(game, mo2, lines, Path('gamedata/scripts/ui_main_menu.script'))
    failures = []
    if missing:
        failures.append('Enabled mods missing from this installation')
    if not axr or not menu:
        failures.append('Winning loose GAMMA callback/menu scripts not found')
    output.mkdir(parents=True)
    configuration = {
        'content_root': str(game), 'mo2_root': str(mo2), 'source_profile': profile,
        'custom_content': False,
        'client_binary': 'client/bin/GammaClientDX11.exe',
        'server_binary': 'server/bin/GammaDedicated.exe',
        'server_requirements_not_implemented': {'max_players': 128, 'port': 1237,
                   'authoritative': ['alife', 'npc_visuals', 'inventory', 'weapons',
                                     'damage', 'money', 'quests', 'accounts', 'admin_commands'],
                   'default_account_role': 'player',
                   'admin_grant_origin': 'local_server_console',
                   'debug_access': 'server_authenticated_admin',
                   'quests': 'independent_random_secondary_quests_per_account'},
        'player_persistence_requirements_not_implemented': {
            'owner': 'server', 'key': 'authenticated_account_id',
            'fields': ['level', 'position', 'orientation', 'inventory', 'item_condition',
                       'ammo', 'money', 'health', 'secondary_quests'],
            'write_triggers': ['periodic_checkpoint', 'disconnect', 'clean_server_shutdown'],
            'restore_trigger': 'authenticated_reconnect',
            'restore_entire_single_player_world': False,
        },
        'build_environment': 'github_actions_only',
        'clients': [{'role': 'p1', 'port': 1241}, {'role': 'p2', 'port': 1242}],
        'status': 'migration_preparation_only',
        'runtime_ready': False,
        'blocking_errors': failures,
        'missing_enabled_mods': missing,
        'winning_axr': str(axr) if axr else None,
        'winning_menu': str(menu) if menu else None,
        'unimplemented': ['dedicated_engine_and_build', 'server_owned_gameplay_transactions',
                          'authenticated_accounts_and_roles', 'per_account_quest_persistence',
                          'admin_console_integration', 'admin_only_network_debug_menu',
                          'two_client_join_acceptance', '128_client_load_acceptance'],
    }
    for role in ('client', 'server', 'p1', 'p2'):
        appdata = output / role / 'appdata'
        appdata.mkdir(parents=True)
        if role in ('client', 'server'):
            (output / role / 'bin').mkdir()
        fs = (game / 'fsgame.ltx').read_text(encoding='utf-8-sig')
        replacement = '$app_data_root$ = true | false | ' + str(appdata) + '\\'
        matches = [line for line in fs.splitlines()
                   if line.strip().startswith('$app_data_root$')]
        if len(matches) != 1:
            raise ValueError('Expected exactly one appdata filesystem entry')
        fs = fs.replace(matches[0], replacement)
        (output / role / 'fsgame.ltx').write_text(fs, encoding='utf-8')
    if not failures:
        for role in ('client', 'server'):
            prepare(modlist, output / ('profile-' + role), role, axr, menu=menu)
    (output / 'migration.json').write_text(
        json.dumps(configuration, ensure_ascii=False, indent=2), encoding='utf-8')
    return configuration


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--game', type=Path, default=DEFAULT_GAME)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', default='G.A.M.M.A')
    args = parser.parse_args()
    result = migrate(args.game, args.output, args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
