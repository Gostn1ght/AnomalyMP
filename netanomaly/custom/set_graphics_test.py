"""Apply reversible diagnostic graphics settings to the isolated Custom copy."""
import argparse
import json
import re
from pathlib import Path

SETTINGS = {
    'texture_lod': '0', 'r__tf_aniso': '16', 'r__tf_mipbias': '0',
    'ssfx_taa': '(0, 0, 0.6, 0)', 'r2_smaa': 'high',
    'r2_dof_enable': 'off', 'r2_mblur_enabled': 'off', 'r2_mblur': '0',
    'ssfx_motionblur': '(6, 0, 0, 0)', 'ssfx_wpn_dof_1': '(0, 0, 0, 1.1)',
    'ssfx_wpn_dof_2': '0',
}

def apply(root):
    if not (root / 'custom-test-manifest.json').is_file():
        raise ValueError('Expected isolated Custom copy')
    for role in ('server', 'p1', 'p2'):
        file = root / ('appdata_' + role) / 'user.ltx'
        backup = file.with_name('user.before-graphics-test.ltx')
        if not backup.exists():
            backup.write_bytes(file.read_bytes())
        text = file.read_text(encoding='utf-8-sig')
        for key, value in SETTINGS.items():
            text = re.sub(r'(?m)^' + re.escape(key) + r'\s+[^\r\n]*\r?\n?', '', text)
            text += '\n' + key + ' ' + value + '\n'
        file.write_text(text, encoding='utf-8')
    (root / 'graphics-test.json').write_text(json.dumps(SETTINGS, indent=2), encoding='utf-8')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('root', type=Path)
    apply(parser.parse_args().root)
