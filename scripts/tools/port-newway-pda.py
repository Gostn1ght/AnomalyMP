"""Port the owner's local New Way PDA atlas/layouts without replacing GAMMA UI IDs."""
import argparse
import copy
import hashlib
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve()
dest = ROOT/'scripts/netcoop-overlay/client'
descriptor = source/'configs/ui/textures_descr/ui_pda_extra.xml'
atlas = source/'textures/ui/ui_pda_extra.dds'
extra = source/'configs/ui/pda_extra.xml'
notes = source/'configs/ui/pda_notes.xml'
general = source/'configs/ui/pda_global_chat.xml'
inputs = [descriptor,atlas,extra,notes,general]
for path in inputs:
    if not path.is_file():
        raise FileNotFoundError(path)
def rename(element):
    for child in element.iter():
        if child.text:
            child.text = child.text.replace('pda_x_', 'lz_nw_pda_')
        if child.get('id'):
            child.set('id', child.get('id').replace('pda_x_', 'lz_nw_pda_'))

textures = ET.parse(descriptor).getroot()
rename(textures)
textures.find('file').set('name', r'ui\lostzone_newway_pda')
target_descriptor = dest/'configs/ui/textures_descr/ui_lostzone_newway_pda.xml'
target_descriptor.parent.mkdir(parents=True,exist_ok=True)
ET.indent(textures)
ET.ElementTree(textures).write(target_descriptor,encoding='windows-1251',xml_declaration=True)
target_atlas = dest/'textures/ui/lostzone_newway_pda.dds'
target_atlas.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(atlas,target_atlas)

layout_path = dest/'configs/ui/ui_netcoop_pdanet.xml'
layout = ET.parse(layout_path).getroot()
for child in list(layout):
    if child.tag.startswith('nw_') or child.tag in ('anonymous','anon_label','cam_lt','cam_rt','cam_lb','cam_rb','cam_ring'):
        layout.remove(child)
for tag,texture in [('frame','shell'),('panel','panel')]:
    node=layout.find(tag)
    node.find('texture').text='lz_nw_pda_'+texture
    node.find('texture').attrib.clear()
layout.find('frame').attrib.update(x='28',y='104',width='764',height='596')
layout.find('panel').attrib.update(width='20',height='20') # both 6px borders fit even before the Lua resize
style = ET.parse(extra).getroot().find('btn_chats/text_color')
for tag in ('button','row','seek'):
    node=layout.find(tag)
    node.find('texture').text='lz_nw_pda_button'
    old=node.find('text_color')
    if old is not None: node.remove(old)
    node.append(copy.deepcopy(style))
for key in ('chats','contacts','gallery','photo','voice'):
    page=copy.deepcopy(ET.parse(extra).getroot().find(key))
    page.tag='nw_'+key
    rename(page)
    layout.append(page)
for key,path in [('notes',notes),('global',general)]:
    page=ET.parse(path).getroot()
    page.tag='nw_'+key
    rename(page)
    layout.append(page)
anonymous=ET.SubElement(layout,'anonymous',x='44',y='668',width='20',height='20')
ET.SubElement(anonymous,'texture').text='lz_nw_pda_check'
label=ET.SubElement(layout,'anon_label',x='72',y='666',width='220',height='24')
ET.SubElement(label,'text',font='letterica16',align='l',vert_align='c',r='132',g='151',b='163')
for tag,x,y in [('lt',64,64),('rt',888,64),('lb',64,632),('rb',888,632)]:
    corner=ET.SubElement(layout,'cam_'+tag,x=str(x),y=str(y),width='72',height='72',stretch='1')
    ET.SubElement(corner,'texture').text='lz_nw_pda_vf_'+tag
ring=ET.SubElement(layout,'cam_ring',x='464',y='336',width='96',height='96',stretch='1')
ET.SubElement(ring,'texture').text='lz_nw_pda_vf_ring'
ET.indent(layout)
ET.ElementTree(layout).write(layout_path,encoding='windows-1251',xml_declaration=True)
provenance = ROOT/'docs/audit/107_NEW_WAY_PDA_PROVENANCE_2026-10-14.md'
lines = ['# New Way PDA source and adaptation','',
         'Source: owner-provided local `NW_unpacked` game data. No public-license claim is made.',
         'Original atlas bytes are preserved. Texture IDs and atlas filename are isolated from GAMMA.',
         'Layouts for global/chat/contact/gallery/photo/voice/notes are retained under `nw_*` XML nodes.',
         'Network actions and player data remain Lost Zone server-authoritative.', '',
         'Original SHA256:', '']
lines += [f'- `{p.relative_to(source).as_posix()}`: `{hashlib.sha256(p.read_bytes()).hexdigest()}`' for p in inputs]
lines += ['', 'This records imported resources; it does not certify visual acceptance or that every page has been adapted.','']
provenance.write_text('\n'.join(lines),encoding='utf-8')
print('Imported isolated New Way atlas and seven page layouts; source checksums recorded.')
