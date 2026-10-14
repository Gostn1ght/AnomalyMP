"""Validate imported New Way assets, native Lua API names and used layout paths."""
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
client = root/'scripts/netcoop-overlay/client'
atlas = (client/'textures/ui/lostzone_newway_pda.dds').read_bytes()
assert atlas[:4] == b'DDS ' and struct.unpack_from('<I',atlas,4)[0] == 124
height,width = struct.unpack_from('<II',atlas,12)
descriptor = ET.parse(client/'configs/ui/textures_descr/ui_lostzone_newway_pda.xml').getroot()
textures = {}
for element in descriptor.find('file'):
    name = element.get('id')
    assert name.startswith('lz_nw_pda_') and name not in textures
    x,y,w,h = (int(element.get(k)) for k in ('x','y','width','height'))
    assert x>=0 and y>=0 and w>0 and h>0 and x+w<=width and y+h<=height, name
    textures[name] = element
assert descriptor.find('file').get('name') == r'ui\lostzone_newway_pda'
layout = ET.parse(client/'configs/ui/ui_netcoop_pdanet.xml').getroot()
for element in layout.iter('texture'):
    name = (element.text or '').strip()
    if not name.startswith('lz_nw_pda_') or name in textures: continue
    groups = [('_lt','_t','_rt','_l','_back','_r','_lb','_b','_rb'),('_e','_h','_t','_d'),('_b','_back','_e')]
    assert any(all(name+s in textures for s in group) for group in groups), name
bindings = (root/'src/xrGame/ScriptXMLInit.cpp').read_text(encoding='utf-8-sig')
methods = set(re.findall(r'\.def\("(Init\w+)"', bindings))
code = '\n'.join((client/name).read_text(encoding='utf-8') for name in
                 ('netcoop_pdanet_ui.script','netcoop_pdanet_photo.script','netcoop_pdanet_voice.script'))
for method in re.findall(r':(Init\w+)\(',code):
    if method == 'InitTexture': continue # CUIStatic, not CScriptXmlInit.
    assert method in methods, f'Unbound XML Lua method: {method}'
for path,kind in re.findall(r'layout(?:_button)?\(self,\s*"(nw_[^"\n]+)"(?:,\s*"(Frame|EditBox)")?',code):
    element = layout.find(path.replace(':','/'))
    assert element is not None, path
    assert 'Init'+(kind or 'Static') in methods
    assert float(element.get('width','0'))>0 and float(element.get('height','0'))>0, path
for page in ('global','chats','contacts','gallery','photo','voice','notes'):
    assert layout.find('nw_'+page) is not None
for corner in ('lt','rt','lb','rb','ring'):
    node=layout.find('cam_'+corner)
    assert node is not None and node.find('texture').text in textures
anonymous=layout.find('anonymous')
assert float(anonymous.get('x'))+float(anonymous.get('width')) < 300, 'checkbox overlaps UID footer'
assert 'self.title:Show(false)' in code and 'self.clock:Show(false)' in code
assert 'w:Show(not self.viewing)' in code, 'photo view leaks clicks to camera/page buttons'
print('PASS New Way PDA: seven layouts, atlas bounds, complete frame/button/input groups, real native XML Lua bindings, camera art and photo controls')
