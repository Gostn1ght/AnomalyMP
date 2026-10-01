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


# Draw the actual selected keyframe, using the engine's OMF bone transforms.
# Costume detail is deliberately sparse so small white outlines remain readable.
import importlib, configparser
Motions = importlib.import_module('read-omf-poses').Motions
runtime = Path(__file__).resolve().parents[2] / 'gamma-runtime/gamedata/meshes'
actor = runtime/'actors/stalker_radseva_series/stalker_monolith_radseva.ogf'
libraries = [Motions(runtime/'actors'/name, actor) for name in
             ('stalker_animation.omf','stalker_scripts_animation.omf','stalker_smart_cover_animation.omf')]
cfg = configparser.ConfigParser(allow_no_value=True)
cfg.read(CLIENT/'configs/netcoop/rp_anims.ltx')
pose_sources = {}

def pose(name):
    import numpy as np
    section=cfg['rp_'+name]
    motions=[n.strip() for n in (section['mid'] or section['in']).split(',') if n.strip()]
    motion=motions[0] if section['mid'] else motions[-1]
    library=next(m for m in libraries if motion in m.motions)
    points=library.pose(motion, .4)
    angle=math.radians(22)
    if name in ('sleep','pushups'): angle=math.radians(78)
    elif name.startswith('bar_') or name in ('loot','wounded_2'): angle=math.radians(45)
    keys=['bip01_head','bip01_neck','bip01_pelvis']
    for side in ('l','r'):
        keys += ['bip01_'+side+'_'+n for n in ('upperarm','forearm','hand','thigh','calf','foot','toe0')]
    def raw(n):
        x,y,z=points[n];return np.array((-x*math.cos(angle)+z*math.sin(angle),-y))
    bounds=np.array([raw(n) for n in keys])
    lo=bounds.min(0)-(.24,.25);hi=bounds.max(0)+(.24,.20)
    scale=min(100/(hi[0]-lo[0]),104/(hi[1]-lo[1]))
    centre=(lo+hi)/2
    def at(n):return tuple((raw(n)-centre)*scale+(64,64))
    o=Outline()
    def limb(nodes,widths):o.tube([at(n) for n in nodes], [v*scale for v in widths])
    for side in ('l','r'):
        pre='bip01_'+side+'_'
        limb([pre+'thigh',pre+'calf',pre+'foot'], [.095,.078,.06])
        o.tube([at(pre+'foot'),at(pre+'toe0')],[.065*scale,.05*scale])
    # Jacket contour joins the actual shoulder and hip locations.
    left=np.array(at('bip01_l_upperarm'));right=np.array(at('bip01_r_upperarm'))
    hip=np.array(at('bip01_pelvis'));neck=np.array(at('bip01_neck'))
    down=hip-neck;down/=np.linalg.norm(down)
    across=np.array((down[1],-down[0]));w=.15*scale
    if np.dot(right-left,across)<0: across=-across
    polygon=[tuple(left-across*.025*scale),tuple(right+across*.025*scale),
             tuple(hip+across*w+down*.10*scale),tuple(hip-across*w+down*.10*scale)]
    o.draw.polygon([(round(x*SCALE),round(y*SCALE)) for x,y in polygon],fill=(0,0,0,0))
    o.line(polygon,closed=True)
    o.line([tuple(neck),tuple(hip+down*.085*scale)],1.5)
    o.line([tuple(hip-across*w),tuple(hip+across*w)],1.7)
    for side in ('l','r'):
        pre='bip01_'+side+'_'
        limb([pre+'upperarm',pre+'forearm',pre+'hand'],[.075,.06,.037])
        x,y=at(pre+'hand');o.ellipse((x-2.6,y-2.6,x+2.6,y+3.8),1.7)
    h=np.array(at('bip01_head'))-down*.09*scale
    def head(u,v):return tuple(h+across*u*scale+down*v*scale)
    hood=[head(-.075,.085),head(-.09,-.035),head(-.06,-.13),head(0,-.16),
          head(.06,-.13),head(.09,-.035),head(.075,.085),head(0,.11)]
    o.draw.polygon([(round(x*SCALE),round(y*SCALE)) for x,y in hood],fill=(0,0,0,0))
    o.line(hood,closed=True)
    o.line([head(-.048,.035),head(-.05,-.035),head(0,-.09),head(.05,-.035),head(.048,.035)],1.5)
    o.line([head(-.047,.035),head(.047,.035)],1.5)
    if name=='gop_stop':
        # Recognisable sidearm rather than the old raised-fingers doodle.
        x,y=at('bip01_r_hand')
        o.line([(x-2,y),(x-2,y-13),(x+12,y-13),(x+12,y-9),(x+3,y-9),(x+3,y)],1.9,True)
    if name.startswith('bar_'):
        hands=[at('bip01_l_hand'),at('bip01_r_hand')]
        y=min(112,max(v[1] for v in hands)+3)
        o.line([(15,y),(113,y)],1.8)
        o.line([(25,y),(25,116)],1.6);o.line([(104,y),(104,116)],1.6)
    if name=='loot':
        x,y=at('bip01_l_hand');o.line([(x-8,y+8),(x+8,y+8),(x+8,y+18),(x-8,y+18)],1.7,True)
    pose_sources[name]={'motion':motion,'frame_fraction':.4}
    return o.result()


atlas=Image.new('RGBA',(1024,512))
icons=[pose(name) for name in NAMES]
for i,icon in enumerate(icons): atlas.paste(icon,((i%8)*128,(i//8)*128))
atlas.save(TEX/'netcoop_rp_poses.dds')
ring=Image.new('RGBA',(1024,1024))
d=ImageDraw.Draw(ring)
d.ellipse((4,4,1020,1020),fill=(14,17,14,218),outline=ACCENT,width=2)
d.ellipse((155,155,869,869),outline=(139,127,94,255),width=2)
d.ellipse((301,301,723,723),fill=(11,14,12,236),outline=(139,127,94,255),width=2)
for i in range(14):
    a=-math.pi/2+(i-.5)*2*math.pi/14
    d.line([(512+211*math.cos(a),512+211*math.sin(a)),
            (512+508*math.cos(a),512+508*math.sin(a))],fill=(168,155,119,255),width=2)
ring.save(TEX/'netcoop_rp_ring.dds')
selection=Image.new('RGBA',(128,128));d=ImageDraw.Draw(selection)
d.ellipse((7,7,121,121),fill=(188,148,55,52),outline=(230,197,125,255),width=2)
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
    a=-math.pi/2+(i%14)*2*math.pi/14
    radius=(296 if i<14 else 196)*1024/700
    size=round((78 if i<14 else 68)*1024/700)
    small=icon.resize((size,size),Image.Resampling.LANCZOS)
    preview.alpha_composite(small,(round(512+radius*math.cos(a)-size/2),round(512+radius*math.sin(a)-size/2)))
preview_dir=Path(__file__).resolve().parents[2]/'build-logs'
preview_dir.mkdir(parents=True,exist_ok=True)
preview.save(preview_dir/'netcoop_rp_preview.png')
atlas.save(preview_dir/'netcoop_rp_white_contours.png')
print('Rendered 28 white outline poses, wheel, selection and texture descriptors')

import json
(CLIENT/'configs/netcoop/rp_icon_sources.json').write_text(json.dumps(pose_sources,indent=2))
