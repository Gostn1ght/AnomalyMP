"""Render the RP wheel's editable, white contour pose drawings.

Requires Pillow. These are code-native outline illustrations: every figure has
transparent interiors, jacket / hood details and distinct limb silhouettes.
No generated bitmap is filtered or recolored. Slots match netcoop_rp_menu.script.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import math

CLIENT = Path(__file__).resolve().parent / 'netcoop-overlay/client'
TEX = CLIENT / 'textures/ui'
DESC = CLIENT / 'configs/ui/textures_descr'
TEX.mkdir(parents=True, exist_ok=True)
DESC.mkdir(parents=True, exist_ok=True)
NAMES = 'hands_pockets salute greet refuse hands_behind look_around listen hands_up guard sit_1 sit_2 sit_3 sleep pushups bar_1 bar_2 bar_3 bar_4 bar_5 bar_6 trance_1 trance_2 wounded_1 wounded_2 prisoner psy gop_stop loot'.split()
WHITE = (255, 255, 255, 255)
ACCENT = (165, 144, 93, 255)
SCALE = 4


class Outline:
    """Draw unfilled paths at 4x resolution for smooth UI strokes."""
    def __init__(self):
        self.image = Image.new('RGBA', (128*SCALE, 128*SCALE))
        self.draw = ImageDraw.Draw(self.image)

    def line(self, points, width=2.2, closed=False):
        pts = [(round(x*SCALE), round(y*SCALE)) for x,y in points]
        if closed: pts.append(pts[0])
        self.draw.line(pts, fill=WHITE, width=round(width*SCALE), joint='curve')

    def ellipse(self, box, width=2.2):
        self.draw.ellipse(tuple(round(v*SCALE) for v in box), outline=WHITE, width=round(width*SCALE))

    def tube(self, points, widths):
        # Closed sleeve / trouser contours rather than a single stick limb.
        edges = [[], []]
        for i, (x,y) in enumerate(points):
            before = points[max(0,i-1)]; after = points[min(len(points)-1,i+1)]
            dx,dy = after[0]-before[0], after[1]-before[1]
            length = math.hypot(dx,dy) or 1
            px,py = -dy/length*widths[i]/2, dx/length*widths[i]/2
            edges[0].append((x+px,y+py)); edges[1].append((x-px,y-py))
        self.line(edges[0]+list(reversed(edges[1])), closed=True)

    def hand(self, x,y):
        self.ellipse((x-3.2,y-3.5,x+3.2,y+3.5),1.8)

    def torso(self, shoulder, waist, rear=False):
        sx,sy=shoulder; wx,wy=waist
        dx,dy=wx-sx,wy-sy
        length=math.hypot(dx,dy) or 1
        right=(dy/length,-dx/length); down=(dx/length,dy/length)
        def p(u,v): return (sx+right[0]*u+down[0]*v,sy+right[1]*u+down[1]*v)
        self.line([p(-15,0),p(-17,6),p(-13,length),p(13,length),p(17,6),p(15,0),p(7,-4),p(-7,-4)],closed=True)
        self.line([p(-7,-4),p(0,3),p(7,-4)],1.5)
        if rear:
            self.line([p(-9,5),p(-10,length-5),p(10,length-5),p(9,5)],1.5,True)
            self.line([p(-7,8),p(7,8)],1.3)
        else:
            self.line([p(0,3),p(0,length-2)],1.3)
            for side in (-1,1):
                self.line([p(side*4,length-12),p(side*10,length-12),p(side*10,length-5),p(side*4,length-5)],1.3)
        self.line([p(-13,length-3),p(13,length-3)],1.3)
        hx,hy=p(0,-17)
        # Pointed hood, face opening and a simple scarf; no solid head fill.
        def h(u,v): return (hx+right[0]*u+down[0]*v,hy+right[1]*u+down[1]*v)
        self.line([h(-9,8),h(-11,-1),h(-8,-11),h(0,-15),h(8,-11),h(11,-1),h(9,8),h(0,12)],closed=True)
        if not rear:
            self.line([h(-6,2),h(-6,-4),h(0,-9),h(6,-4),h(6,2),h(0,7)],1.5,True)
            self.line([h(-6,2),h(6,2)],1.4)

    def arm(self, points):
        self.tube(points,[8,7,4.5]); self.hand(*points[-1])

    def leg(self, points):
        self.tube(points,[10,9,7])
        x,y=points[-1]
        self.line([(x-4,y-2),(x+4,y-2),(x+9,y+3),(x+9,y+6),(x-4,y+6)],closed=True)

    def result(self):
        # Rasterize our vector-style source drawing, preserving alpha. White
        # RGB is constant; only coverage changes on antialiased edges.
        alpha=self.image.getchannel('A').resize((128,128),Image.Resampling.LANCZOS)
        result=Image.new('RGBA',(128,128),WHITE);result.putalpha(alpha)
        return result


def pose(name):
    o=Outline()
    shoulder=(64,40); waist=(64,73)
    arms=[[(49,43),(43,62),(47,78)],[(79,43),(85,62),(81,78)]]
    legs=[[(57,74),(54,91),(52,109)],[(71,74),(75,91),(77,109)]]
    rear=name=='hands_behind'
    if name=='hands_pockets':
        arms=[[(49,43),(40,60),(53,65)],[(79,43),(88,60),(75,65)]]
    elif name=='salute': arms[1]=[(79,43),(94,39),(74,23)]
    elif name=='greet': arms[1]=[(79,43),(97,34),(100,13)]
    elif name=='refuse': arms=[[(49,43),(44,60),(78,42)],[(79,43),(85,60),(50,42)]]
    elif name=='hands_behind': arms=[[(49,43),(43,62),(60,79)],[(79,43),(85,62),(68,79)]]
    elif name=='look_around': arms[1]=[(79,43),(96,35),(68,18)]
    elif name=='listen': arms[1]=[(79,43),(95,43),(78,28)]
    elif name=='hands_up': arms=[[(49,43),(32,36),(30,12)],[(79,43),(96,36),(98,12)]]
    elif name=='guard': arms=[[(49,43),(43,66),(62,59)],[(79,43),(86,63),(76,52)]]
    elif name.startswith('sit_') or name in ('trance_2','wounded_2','prisoner'):
        shoulder=(64,49); waist=(64,79)
        arms=[[(49,52),(39,73),(42,86)],[(79,52),(90,73),(86,86)]]
        legs=[[(57,80),(36,89),(41,109)],[(71,80),(91,89),(91,109)]]
        if name=='sit_2':
            arms=[[(49,52),(44,73),(53,81)],[(79,52),(84,73),(75,81)]]
            legs=[[(57,80),(56,94),(54,109)],[(71,80),(73,94),(75,109)]]
        elif name=='sit_3' or name=='trance_2':
            legs=[[(57,80),(34,101),(77,109)],[(71,80),(96,101),(49,110)]]
        if name=='trance_2': arms=[[(49,52),(36,77),(28,78)],[(79,52),(92,77),(100,78)]]
        elif name=='wounded_2':
            shoulder=(57,52)
            arms=[[(42,55),(36,75),(63,73)],[(72,55),(83,77),(58,79)]]
        elif name=='prisoner':
            arms=[[(49,52),(34,37),(53,28)],[(79,52),(94,37),(75,28)]]
            legs=[[(57,80),(42,99),(58,108)],[(71,80),(88,99),(71,108)]]
    elif name=='sleep':
        shoulder=(39,76);waist=(75,80)
        arms=[[(42,63),(36,82),(24,86)],[(42,89),(56,98),(31,92)]]
        legs=[[(76,74),(93,82),(109,95)],[(76,87),(90,100),(108,101)]]
    elif name=='pushups':
        shoulder=(38,59);waist=(78,72)
        arms=[[(41,46),(32,75),(25,100)],[(35,72),(43,84),(39,101)]]
        legs=[[(80,67),(98,82),(108,99)],[(76,79),(88,91),(95,103)]]
    elif name.startswith('bar_'):
        if name in ('bar_1','bar_3','bar_5'): shoulder=(58,41)
        arms=[[(shoulder[0]-15,44),(35,64),(55,68)],[(shoulder[0]+15,44),(87,63),(75,68)]]
        if name=='bar_2': arms[1]=[(79,43),(95,47),(77,29)]
        elif name=='bar_3': arms[1]=[(73,44),(85,67),(101,67)]
        elif name=='bar_4': arms[1]=[(79,43),(96,47),(100,29)]
        elif name=='bar_5':
            shoulder=(55,49)
            arms=[[(40,52),(31,67),(48,69)],[(70,52),(87,67),(79,69)]]
        elif name=='bar_6': arms=[[(49,43),(32,54),(22,42)],[(79,43),(96,54),(106,42)]]
    elif name=='trance_1':
        arms=[[(49,43),(35,61),(30,80)],[(79,43),(93,61),(98,80)]]
    elif name=='wounded_1':
        shoulder=(55,48)
        arms=[[(40,51),(35,72),(63,70)],[(70,51),(82,73),(57,78)]]
        legs=[[(57,74),(48,92),(45,110)],[(71,74),(80,92),(85,110)]]
    elif name=='psy': arms=[[(49,43),(32,31),(52,24)],[(79,43),(96,31),(76,24)]]
    elif name=='gop_stop': arms=[[(49,43),(35,63),(38,79)],[(79,43),(95,40),(106,25)]]
    elif name=='loot':
        shoulder=(56,55);waist=(67,81)
        arms=[[(41,58),(31,76),(22,95)],[(71,58),(88,77),(96,97)]]
        legs=[[(60,82),(44,101),(65,110)],[(74,82),(90,88),(95,110)]]
    # Rear limbs first. Jacket seams stay readable through the transparent art.
    for leg in legs: o.leg(leg)
    o.torso(shoulder,waist,rear)
    for arm in arms: o.arm(arm)
    if name=='guard':
        o.line([(37,55),(83,52),(95,48),(100,50),(83,57),(60,60),(45,61),(38,67)],closed=True)
        o.line([(71,56),(72,64),(78,63),(78,55)],1.5)
    if name.startswith('bar_'):
        o.line([(20,72),(108,72),(108,78),(20,78)],1.8,True)
        o.line([(28,78),(28,115)],1.8);o.line([(101,78),(101,115)],1.8)
        if name=='bar_2':
            o.line([(75,23),(83,23),(83,34),(75,34)],1.6,True)
            o.line([(83,25),(87,25),(87,31),(83,31)],1.5)
    if name=='sit_2':
        o.line([(47,84),(84,84),(84,88),(47,88)],1.6,True)
        o.line([(47,88),(47,115)],1.6);o.line([(84,88),(84,115)],1.6)
    if name=='sleep' or name=='pushups': o.line([(12,116),(116,116)],1.5)
    if name=='loot': o.line([(10,105),(27,101),(39,107),(36,117),(12,117)],1.7,True)
    if name=='greet':
        o.line([(108,18),(113,15)],1.7);o.line([(106,9),(108,4)],1.7)
    if name=='gop_stop':
        o.line([(103,28),(101,18),(103,15),(105,23),(105,12),(108,11),(108,22),(110,14),(113,15),(112,28)],1.6)
    return o.result()


atlas=Image.new('RGBA',(1024,512))
icons=[pose(name) for name in NAMES]
for i,icon in enumerate(icons): atlas.paste(icon,((i%8)*128,(i//8)*128))
atlas.save(TEX/'netcoop_rp_poses.dds')
ring=Image.new('RGBA',(1024,1024))
d=ImageDraw.Draw(ring)
d.ellipse((7,7,1017,1017),fill=(17,20,16,235),outline=ACCENT,width=3)
d.ellipse((149,149,875,875),fill=(11,14,12,231),outline=(116,116,82,255),width=2)
for i in range(28):
    a=-math.pi/2+(i-.5)*2*math.pi/28
    d.line([(512+363*math.cos(a),512+363*math.sin(a)),(512+505*math.cos(a),512+505*math.sin(a))],fill=(190,183,158,255),width=2)
    d.line([(512+350*math.cos(a),512+350*math.sin(a)),(512+342*math.cos(a),512+342*math.sin(a))],fill=ACCENT,width=2)
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
# Developer art / layout previews, not captures of the game.
preview=ring.copy()
for i,icon in enumerate(icons):
    a=-math.pi/2+i*2*math.pi/28
    small=icon.resize((86,86),Image.Resampling.LANCZOS)
    preview.alpha_composite(small,(round(512+443*math.cos(a)-43),round(512+443*math.sin(a)-43)))
preview_dir=Path(__file__).resolve().parents[2]/'build-logs'
preview_dir.mkdir(parents=True,exist_ok=True)
preview.save(preview_dir/'netcoop_rp_preview.png')
atlas.save(preview_dir/'netcoop_rp_white_contours.png')
print('Rendered 28 white outline poses, wheel, selection and texture descriptors')
