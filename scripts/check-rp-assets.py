"""Verify RP DDSs through the prepared client's actual fsgame aliases.

Usage: python scripts/check-rp-assets.py ../gamma-runtime
This checks deployment and source art; it does not claim in-game visual QA.
"""
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from PIL import Image

runtime = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parent/'netcoop-overlay/client'
config = (source/'configs/netcoop/rp_anims.ltx').read_text()
names = re.search(r'^\[rp_list\]\s*\n(.*?)(?=^\[)', config, re.M|re.S).group(1).split()
assert len(names) == 28

for role in ('p1', 'p2'):
    aliases = {}
    for line in (runtime/f'fsgame_{role}.ltx').read_text().splitlines():
        match = re.match(r'(\$[^$]+\$)\s*=\s*(.*)', line)
        if match: aliases[match[1]] = [p.strip() for p in match[2].split('|')]

    def resolve(alias, stack=()):
        assert alias not in stack, 'Cyclic filesystem alias'
        fields = aliases[alias]
        root = fields[2]
        base = resolve(root,stack+(alias,)) if root.startswith('$') else Path(root)
        return base / (fields[3] if len(fields)>3 else '')

    texture_root = resolve('$game_textures$')
    config_root = resolve('$game_config$')
    descriptor = config_root/'ui/textures_descr/ui_netcoop_rp.xml'
    assert descriptor.read_bytes() == (source/'configs/ui/textures_descr/ui_netcoop_rp.xml').read_bytes()
    found = []
    for entry in ET.parse(descriptor).findall('file'):
        relative = Path(entry.attrib['name']+'.dds')
        path = texture_root/relative
        assert path.is_file(), f'{role}: texture missing through $game_textures$: {path}'
        assert path.read_bytes() == (source/'textures'/relative).read_bytes(), f'Stale texture: {path}'
        with Image.open(path) as texture:
            assert texture.mode == 'RGBA'
            assert texture.getchannel('A').getextrema() == (0,255)
            for region in entry.findall('texture'):
                a=region.attrib
                x,y,w,h=(int(a[k]) for k in ('x','y','width','height'))
                assert 0 <= x < x+w <= texture.width and 0 <= y < y+h <= texture.height
                icon = texture.crop((x,y,x+w,y+h))
                assert icon.getchannel('A').getbbox(), f'Empty sprite: {a["id"]}'
                if a['id'].startswith('ui_netcoop_pose_'):
                    found.append(a['id'].removeprefix('ui_netcoop_pose_'))
                    # Only white strokes with antialiased coverage; never a
                    # colored or solid-background figure. Each cell has air
                    # around all four edges to avoid atlas bleeding.
                    assert all(r==g==b==255 for r,g,b,alpha in icon.get_flattened_data() if alpha)
                    bbox=icon.getchannel('A').getbbox()
                    assert 0 < bbox[0] < bbox[2] < w and 0 < bbox[1] < bbox[3] < h
    assert found == names, 'Texture slots do not match the native RP list'
    print(f'PASS {role}: actual fsgame texture root, all 28 sprites, DDS alpha / white contours / bounds')
