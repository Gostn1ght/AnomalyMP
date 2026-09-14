"""Create a new MO2 profile and role addon from an installed GAMMA profile. No in-place edits."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
POLICY = json.loads((ROOT / 'profile-policy.json').read_text(encoding='utf-8'))


def transform_modlist(text, role):
    if role not in ('client', 'server'):
        raise ValueError('Role must be client or server')
    lines, disabled, seen = [], [], set()
    for line in text.splitlines():
        if line.startswith(('+', '-')):
            name = line[1:]
            if name.startswith('GAMMA NetAnomaly - '):
                continue
            # Duplicate entries (present in upstream GAMMA) produce ambiguous MO2 state.
            if name in seen:
                continue
            seen.add(name)
            if line.startswith('+') and name in POLICY['disabled_mods']:
                disabled.append(name)
                line = '-' + name
        lines.append(line)
    # MO2 modlist is highest priority first. Role addon must override axr_main.
    return '\n'.join(['# GAMMA NetAnomaly experimental profile', '+GAMMA NetAnomaly - ' + role] + lines) + '\n', disabled


def patch_axr(data):
    # Preserve original encoding and all GAMMA callbacks; add only a bootstrap.
    start = b'function on_game_start()'
    if data.count(start) != 1:
        raise ValueError('axr_main differs from the expected GAMMA callback manager')
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    data = data.replace(start, start + newline + b'\tgamma_net_compat.install()')
    if b'imgui_on_render\t' not in data and b'imgui_on_render ' not in data:
        anchor = b'local intercepts = {'
        if data.count(anchor) != 1:
            raise ValueError('Callback table missing in axr_main')
        data = data.replace(anchor, anchor + newline + b'\timgui_on_render = {},')
    return data


def patch_menu(data):
    for name in ('OnButton_save_clicked', 'OnButton_load_clicked', 'OnButton_last_save', 'OnButton_new_game'):
        pattern = rb'(function main_menu:' + name.encode('ascii') + rb'\([^\r\n]*\))'
        data, count = re.subn(pattern, rb'\1\n\tdo return gamma_net_compat.unavailable() end', data)
        if count != 1:
            raise ValueError('Expected one GAMMA menu handler: ' + name)
    return data


def prepare(modlist, output, role, axr, user_ltx=None, menu=None):
    output = output.resolve()
    if output.exists():
        raise ValueError(f'Refusing to overwrite an existing profile bundle: {output}')
    transformed, disabled = transform_modlist(modlist.read_text(encoding='utf-8-sig'), role)
    patched = patch_axr(axr.read_bytes())
    menu = menu or REPO / 'G.A.M.M.A/modpack_addons/109- MCM Mod Configuration Menu - RavenAscendant/gamedata/scripts/ui_main_menu.script'
    patched_menu = patch_menu(menu.read_bytes())
    profile = output / 'profiles' / ('GAMMA NetAnomaly - ' + role)
    addon = output / 'mods' / ('GAMMA NetAnomaly - ' + role)
    profile.mkdir(parents=True)
    shutil.copytree(ROOT / 'runtime', addon)
    scripts = addon / 'gamedata' / 'scripts'
    (scripts / 'axr_main.script').write_bytes(patched)
    (scripts / 'ui_main_menu.script').write_bytes(patched_menu)
    configs = addon / 'gamedata' / 'configs'
    configs.mkdir(parents=True, exist_ok=True)
    (configs / 'gamma_net_role.ltx').write_text('[network]\nrole = ' + role + '\nprotocol = 3\n', encoding='ascii')
    (profile / 'modlist.txt').write_text(transformed, encoding='utf-8')
    if user_ltx:
        text = user_ltx.read_text(encoding='utf-8-sig')
        settings = {'net_cl_update_rate': '30', 'net_sv_update_rate': '30', 'net_cl_interpolation': '0.1'}
        for key, value in settings.items():
            text = re.sub(r'(?m)^' + key + r'\s+.*\n?', '', text)
            text += '\n' + key + ' ' + value + '\n'
        (profile / 'user.ltx').write_text(text, encoding='utf-8')
    report = {'role': role, 'disabled_mods': {n: POLICY['disabled_mods'][n] for n in disabled},
              'source_modlist_sha256': hashlib.sha256(modlist.read_bytes()).hexdigest(),
              'source_axr_sha256': hashlib.sha256(axr.read_bytes()).hexdigest(),
              'unsupported': POLICY['unsupported'], 'status': 'experimental, not gameplay validated'}
    (output / 'compatibility-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--modlist', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--role', choices=['client', 'server'], required=True)
    parser.add_argument('--axr', type=Path, default=REPO / 'G.A.M.M.A/modpack_patches/gamedata/scripts/axr_main.script')
    parser.add_argument('--user-ltx', type=Path)
    parser.add_argument('--menu', type=Path)
    args = parser.parse_args()
    report = prepare(args.modlist, args.output, args.role, args.axr, args.user_ltx, args.menu)
    print(json.dumps(report, indent=2, ensure_ascii=False))
