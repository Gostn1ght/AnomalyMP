"""Original vector-style hooded pose symbols for the native RP wheel.

Requires Pillow. Generates RGBA DDS assets and their X-Ray texture descriptors.
All pose slots match netcoop_rp_menu.script; no third-party artwork is used.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

CLIENT = Path(__file__).resolve().parent / 'netcoop-overlay/client'
TEX = CLIENT / 'textures/ui'
DESC = CLIENT / 'configs/ui/textures_descr'
TEX.mkdir(parents=True, exist_ok=True)
DESC.mkdir(parents=True, exist_ok=True)
NAMES = 'hands_pockets salute greet refuse hands_behind look_around listen hands_up guard sit_1 sit_2 sit_3 sleep pushups bar_1 bar_2 bar_3 bar_4 bar_5 bar_6 trance_1 trance_2 wounded_1 wounded_2 prisoner psy gop_stop loot'.split()
INK = (217, 204, 165, 255)
ACCENT = (165, 144, 93, 255)
DARK = (26, 28, 23, 255)
font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 18)

def pose(name, number):
    im = Image.new('RGBA', (128, 128))
    d = ImageDraw.Draw(im)
    def line(points, width=7, fill=INK):
        d.line(points, fill=fill, width=width, joint='curve')
        r = width / 2
        for x,y in points:
            d.ellipse((x-r,y-r,x+r,y+r), fill=fill)
    def hood(x=64,y=23):
        d.ellipse((x-11,y-13,x+11,y+11), fill=INK)
        d.rounded_rectangle((x-7,y-4,x+7,y+6), radius=3, fill=DARK)
    def body(x=64,y=40, lean=0):
        hood(x+lean,y-17)
        d.polygon([(x-14+lean,y),(x+14+lean,y),(x+11,y+30),(x-11,y+30)], fill=INK)
        d.line([(x+lean,y+3),(x,y+27)], fill=DARK, width=2)
        d.rectangle((x-10,y+16,x-3,y+23), fill=ACCENT)
        d.rectangle((x+3,y+16,x+10,y+23), fill=ACCENT)
    def legs(x=64,y=70, mode='stand'):
        if mode == 'stand':
            line([(x-7,y),(x-12,100),(x-18,100)], 8)
            line([(x+7,y),(x+12,100),(x+18,100)], 8)
        elif mode == 'sit':
            line([(x-6,y),(x-22,y+10),(x-12,100),(x-3,100)], 8)
            line([(x+6,y),(x+25,y+10),(x+22,100),(x+31,100)], 8)
        elif mode == 'kneel':
            line([(x-6,y),(x-20,y+15),(x-2,100)], 8)
            line([(x+6,y),(x+22,y+8),(x+17,100),(x+31,100)], 8)
    if name == 'sleep':
        hood(26,76)
        line([(40,76),(70,80),(95,78),(106,86)], 13)
        line([(42,78),(56,91),(70,90)], 6)
        line([(18,100),(109,100)], 2, ACCENT)
    elif name == 'pushups':
        hood(27,56)
        line([(42,60),(72,68),(102,92)], 11)
        line([(47,64),(42,88),(30,96)], 6)
        line([(18,102),(110,102)], 2, ACCENT)
    else:
        sitting = name in ('sit_1','sit_2','sit_3','trance_2','wounded_2','prisoner')
        x,y,lean = 64, (51 if sitting else 40), 0
        if name in ('wounded_1','wounded_2','loot','bar_3','bar_5'): lean=-9
        body(x,y,lean)
        legs(x,y+30,'kneel' if name=='loot' else 'sit' if sitting else 'stand')
        sy = y+3
        arms = {
            'hands_pockets': [[(50,sy),(43,60),(53,70)],[(78,sy),(85,60),(75,70)]],
            'salute': [[(50,sy),(44,64),(43,76)],[(78,sy),(91,40),(78,19)]],
            'greet': [[(50,sy),(43,62),(43,77)],[(78,sy),(96,37),(98,13)]],
            'refuse': [[(50,sy),(41,56),(62,50)],[(78,sy),(90,53),(67,46)]],
            'hands_behind': [[(50,sy),(40,61),(55,75)],[(78,sy),(89,61),(73,75)]],
            'look_around': [[(50,sy),(43,65),(45,79)],[(78,sy),(93,40),(74,18)]],
            'listen': [[(50,sy),(41,57),(48,74)],[(78,sy),(94,43),(82,24)]],
            'hands_up': [[(50,sy),(32,40),(30,14)],[(78,sy),(96,40),(98,14)]],
            'guard': [[(50,sy),(43,58),(63,62)],[(78,sy),(86,59),(66,63)]],
            'sit_1': [[(50,sy),(41,76),(45,86)],[(78,sy),(88,76),(87,88)]],
            'sit_2': [[(50,sy),(43,68),(56,63)],[(78,sy),(85,68),(70,63)]],
            'sit_3': [[(50,sy),(40,70),(53,76)],[(78,sy),(87,70),(70,77)]],
            'bar_1': [[(50,sy),(43,64),(61,67)],[(78,sy),(85,64),(67,66)]],
            'bar_2': [[(50,sy),(40,64),(55,65)],[(78,sy),(93,49),(82,33)]],
            'bar_3': [[(41,sy),(30,65),(54,67)],[(69,sy),(78,64),(99,64)]],
            'bar_4': [[(50,sy),(41,58),(57,57)],[(78,sy),(93,62),(80,70)]],
            'bar_5': [[(41,sy),(30,58),(51,51)],[(69,sy),(82,59),(102,51)]],
            'bar_6': [[(50,sy),(36,52),(21,38)],[(78,sy),(92,52),(107,38)]],
            'trance_1': [[(50,sy),(37,58),(35,83)],[(78,sy),(91,58),(93,83)]],
            'trance_2': [[(50,sy),(37,69),(26,63)],[(78,sy),(91,69),(103,63)]],
            'wounded_1': [[(41,sy),(31,66),(53,67)],[(69,sy),(80,63),(56,68)]],
            'wounded_2': [[(41,sy),(32,75),(53,76)],[(69,sy),(82,72),(56,76)]],
            'prisoner': [[(50,sy),(39,39),(53,27)],[(78,sy),(89,39),(75,27)]],
            'psy': [[(50,sy),(37,37),(53,22)],[(78,sy),(91,37),(75,22)]],
            'gop_stop': [[(50,sy),(32,55),(17,51)],[(78,sy),(98,54),(112,42)]],
            'loot': [[(41,sy),(31,73),(19,89)],[(69,sy),(80,75),(96,91)]]
        }
        for arm in arms[name]: line(arm,6)
        if name.startswith('bar_'):
            line([(17,76),(111,76)],3,ACCENT)
            line([(27,77),(27,101)],3,ACCENT)
            if name=='bar_2': d.rectangle((74,26,84,35),fill=ACCENT)
        if name.startswith('sit_'):
            line([(36,87),(94,87)],2,ACCENT)
            if name=='sit_2': line([(20,62),(103,65)],3,ACCENT)
        if name=='guard': line([(43,58),(90,58)],3,ACCENT)
        if name in ('wounded_1','wounded_2'):
            d.rectangle((58,y+17,68,y+22),fill=(143,66,49,255))
        if name.startswith('trance_') or name=='psy':
            d.arc((43,0,85,34),190,340,fill=ACCENT,width=2)
        if name=='loot': d.rectangle((13,92,34,103),outline=ACCENT,width=2)
        if name=='greet': line([(108,16),(116,12)],2,ACCENT)
    d.text((64,117),f'{number:02}',font=font,fill=ACCENT,anchor='mm')
    return im

atlas=Image.new('RGBA',(1024,512))
for i,name in enumerate(NAMES): atlas.paste(pose(name,i+1),((i%8)*128,(i//8)*128))
atlas.save(TEX/'netcoop_rp_poses.dds')
ring=Image.new('RGBA',(1024,1024))
d=ImageDraw.Draw(ring)
d.ellipse((7,7,1017,1017),fill=(17,20,16,235),outline=ACCENT,width=3)
d.ellipse((149,149,875,875),fill=(11,14,12,231),outline=(116,116,82,255),width=2)
for i in range(28):
    a=-math.pi/2+(i-.5)*2*math.pi/28
    d.line([(512+363*math.cos(a),512+363*math.sin(a)),(512+505*math.cos(a),512+505*math.sin(a))],fill=(110,105,76,255),width=2)
    for r in (350,517):
        if r==517: continue
        d.line([(512+r*math.cos(a),512+r*math.sin(a)),(512+(r-8)*math.cos(a),512+(r-8)*math.sin(a))],fill=ACCENT,width=2)
# Subtle PDA grid within the centre, with clear space for labels.
for y in range(360,670,12): d.line([(270,y),(754,y)],fill=(36,42,32,85))
d.line([(352,370),(672,370)],fill=ACCENT,width=2)
d.line([(352,686),(672,686)],fill=ACCENT,width=2)
ring.save(TEX/'netcoop_rp_ring.dds')
selection=Image.new('RGBA',(128,128));d=ImageDraw.Draw(selection)
d.rounded_rectangle((4,4,123,123),radius=12,fill=(188,148,55,58),outline=(246,202,106,255),width=3)
selection.save(TEX/'netcoop_rp_selection.dds')
entries=['<?xml version="1.0" encoding="windows-1251"?>','<w>','<file name="ui\\netcoop_rp_poses">']
for i,name in enumerate(NAMES):
    entries.append(f'<texture id="ui_netcoop_pose_{name}" x="{i%8*128}" y="{i//8*128}" width="128" height="128"/>')
entries+=['</file>','<file name="ui\\netcoop_rp_ring"><texture id="ui_netcoop_rp_ring" x="0" y="0" width="1024" height="1024"/></file>',
    '<file name="ui\\netcoop_rp_selection"><texture id="ui_netcoop_rp_selection" x="0" y="0" width="128" height="128"/></file>','</w>']
(DESC/'ui_netcoop_rp.xml').write_text('\n'.join(entries)+'\n',encoding='ascii')
# Developer layout preview; not a game screenshot.
preview=ring.copy()
for i,name in enumerate(NAMES):
    a=-math.pi/2+i*2*math.pi/28
    icon=pose(name,i+1).resize((86,86),Image.Resampling.LANCZOS)
    preview.alpha_composite(icon,(round(512+443*math.cos(a)-43),round(512+443*math.sin(a)-43)))
preview_path = Path(__file__).resolve().parents[1] / 'build-logs/netcoop_rp_preview.png'
preview_path.parent.mkdir(parents=True, exist_ok=True)
preview.save(preview_path)
print('Generated 28 pose icons, wheel, selection and texture descriptors')
