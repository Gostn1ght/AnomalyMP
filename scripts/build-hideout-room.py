"""Build the 3D hideout from the Cordon bunker shell and installed game props.

Original bunker UVs and curved masonry survive clipping. Its old furniture is
excluded by material. No stock furnished level is loaded at menu runtime.
"""
from pathlib import Path
import collections, hashlib, json, math, struct, sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools/room-editor'))
from assets import Assets, chunks
from server import rotate
runtime=root.parent/'gamma-runtime'
out=root/'scripts/netcoop-overlay/client/meshes/netcoop'
a=Assets(runtime,root/'tools/room-editor'); a.index()
parts=[]; provenance={}; objects=[]
def mesh(name,asset,pos,rot=(0,0,0),scale=(1,1,1),floor=False):
    m=a.mesh(asset)
    if floor:
        lowest=min(rotate([p['position'][i+k]*scale[k] for k in range(3)],rot)[1]
                   for p in m['parts'] for i in range(0,len(p['position']),3))
        pos=(pos[0],pos[1]-lowest,pos[2])
    obj=dict(name=name,asset=asset,position=list(pos),rotation=list(rot),scale=list(scale),hidden=False,uid=str(len(objects)+1))
    objects.append(obj); provenance[asset]=hashlib.sha256(json.dumps(m,sort_keys=True).encode() if asset.startswith('level:') else a.read('meshes/'+asset)).hexdigest()
    for p in m['parts']:
        q=dict(p); q['position']=[]; q['normal']=[]
        for i in range(0,len(p['position']),3):
            point=rotate([p['position'][i+k]*scale[k] for k in range(3)],rot)
            normal=rotate([p['normal'][i+k]/scale[k] for k in range(3)],rot)
            length=math.sqrt(sum(x*x for x in normal)) or 1
            q['position'].extend(point[k]+pos[k] for k in range(3)); q['normal'].extend(x/length for x in normal)
        parts.append(q)
    return obj

def clip(vertices,axis,bound,greater):
    if not vertices:return []
    result=[]
    for prev,current in zip(vertices[-1:]+vertices[:-1],vertices):
        inside=lambda v:(v[axis]>=bound if greater else v[axis]<=bound)
        if inside(prev)!=inside(current):
            t=(bound-prev[axis])/(current[axis]-prev[axis]); result.append([p+(c-p)*t for p,c in zip(prev,current)])
        if inside(current):result.append(current)
    return result

source='l01_escape'; _,visuals=a.levels[source]
shell_counts=collections.Counter()
origin=(-248.5,-24.8,-134.4)
for ident,(_,texture,shader,bounds) in visuals.items():
    texture=texture.replace('\\','/').lower()
    if not texture.startswith(('wall/','crete/','floor/','tile/','wood/wood_walls','mtl/mtl_angar')): continue
    if any(x in shader for x in ('trans','aref','lightplanes')):continue
    # This crop selects the rear domestic half, excluding the trader's desk.
    low=(-251.1,-24.86,-136.4); high=(-245.3,-20.65,-132.4)
    if any(bounds[k]>high[k] or bounds[k+3]<low[k] for k in range(3)):continue
    p=a.mesh(f'level:{source}:{ident}')['parts'][0]
    centre=((bounds[0]+bounds[3])/2,bounds[1],(bounds[2]+bounds[5])/2)
    q=dict(texture=texture,shader=shader,position=[],normal=[],uv=[],index=[],emissive=False)
    for start in range(0,len(p['index']),3):
        vertices=[]
        for i in p['index'][start:start+3]:
            pos=[p['position'][i*3+k]+centre[k] for k in range(3)]
            normal=p['normal'][i*3:i*3+3]
            vertices.append([-(pos[2]-origin[2]),pos[1]-origin[1],pos[0]-origin[0],-normal[2],normal[1],normal[0],*p['uv'][i*2:i*2+2]])
        for axis,bound,greater in [(0,-2,True),(0,2,False),(1,-.03,True),(1,4.1,False),(2,.50,True),(2,3.2,False)]:
            vertices=clip(vertices,axis,bound,greater)
        for i in range(1,len(vertices)-1):
            for v in [vertices[0],vertices[i],vertices[i+1]]:
                q['index'].append(len(q['position'])//3); q['position'].extend(v[:3])
                length=math.sqrt(sum(x*x for x in v[3:6])) or 1
                q['normal'].extend(x/length for x in v[3:6]); q['uv'].extend(v[6:8])
    if q['index']:
        parts.append(q); shell_counts[texture]+=len(q['index'])//3
assert sum(shell_counts.values())>200, 'Bunker shell crop empty'

def panel(texture,points,normal,uv=None):
    if uv is None:uv=[0,0,math.dist(points[0],points[1])/2,0,math.dist(points[0],points[1])/2,math.dist(points[1],points[2])/2,0,math.dist(points[1],points[2])/2]
    edge1=[points[1][k]-points[0][k] for k in range(3)]; edge2=[points[2][k]-points[0][k] for k in range(3)]
    cross=[edge1[1]*edge2[2]-edge1[2]*edge2[1],edge1[2]*edge2[0]-edge1[0]*edge2[2],edge1[0]*edge2[1]-edge1[1]*edge2[0]]
    indices=[0,1,2,0,2,3] if sum(cross[k]*normal[k] for k in range(3))>=0 else [0,2,1,0,3,2]
    parts.append(dict(texture=texture,position=sum((list(p) for p in points),[]),normal=list(normal)*4,uv=uv,index=indices,emissive=False))
# Close the extracted boundary at the back; retain the bunker arched ceiling.
panel('wall/wall_stucco_03',[(-2,0,3.19),(-2,3.25,3.19),(2,3.25,3.19),(2,0,3.19)],(0,0,-1))
panel('wood/wood_plank6_bar',[(-2,.004,-2.6),(-2,.004,3.2),(2,.004,3.2),(2,.004,-2.6)],(0,1,0))
# Domestic wooden wainscot stops at shoulder height; masonry remains visible.
panel('wood/wood_walls8',[(-1.95,.01,3.16),(-1.95,1.02,3.16),(1.95,1.02,3.16),(1.95,.01,3.16)],(0,0,-1))
for x,normal in [(-1.97,(1,0,0)),(1.97,(-1,0,0))]:
    points=[(x,.01,-2.4),(x,1.02,-2.4),(x,1.02,3.16),(x,.01,3.16)]
    if x>0: points.reverse()
    panel('wood/wood_walls8',points,normal)
# Seal the cut front half and carry the bunker vault into the entry alcove.
for x,normal in [(-1.99,(1,0,0)),(1.99,(-1,0,0))]:
    panel('wall/wall_stucco_03',[(x,1.02,-2.6),(x,3.1,-2.6),(x,3.1,3.18),(x,1.02,3.18)],normal)
for i in range(24):
    angles=[math.pi*i/24,math.pi*(i+1)/24]
    x0,x1=[2*math.cos(v) for v in angles]; y0,y1=[2.4+.7*math.sin(v) for v in angles]
    normal=(-(x0+x1)*.25,-1,0);n=math.sqrt(sum(v*v for v in normal));normal=tuple(v/n for v in normal)
    panel('wall/wall_stucco_03',[(x0,y0,-2.6),(x1,y1,-2.6),(x1,y1,.51),(x0,y0,.51)],normal)
mesh('sofa','dynamics/efp_props/prop_couch_1.ogf',(.75,.01,2.5),(0,math.pi/2,0),floor=True)
mesh('table','dynamics/efp_props/prop_table_2.ogf',(.25,.01,.65),(0,math.pi/2,0),floor=True)
mesh('lantern','dynamics/equipments/item_lantern.ogf',(-.10,.65421,.85),scale=(1.2,1.2,1.2),floor=True)
mesh('stove','dynamics/efp_props/prop_stove2.ogf',(-1.4,.01,2.65),(0,math.pi,0),floor=True)
mesh('safe','level:jupiter:29717',(-1.55,.45,1.15),scale=(.5,.5,.5),floor=True)
mesh('safe stand','dynamics/decor/stool.ogf',(-1.55,.01,1.15),floor=True)
mesh('map','dynamics/decor/map1.ogf',(.55,1.70,3.12),(-math.pi/2,0,0),(.60,.60,.60))
mesh('PDA','netcoop/dev_pda.ogf',(1.50,1.40,2.90),(-math.pi/2,0,0),(1.8,1.8,1.8))
# The original world backpack rather than a weapon HUD with arms.
bag=[x for x in a.catalog if 'sumka3.ogf' in x['id']]
if not bag:bag=[x for x in a.catalog if 'backpack' in x['id'] and x['id'].startswith('dynamics/') and '/wpn_eat' not in x['id'] and '/psu' not in x['id']]
assert bag,'No standalone backpack installed'
mesh('backpack',bag[0]['id'],(1.52,.44,2.22),(0,math.pi,0),scale=(1.2,1.2,1.2),floor=True)
mesh('door','dynamics/decor/door_wood_100x190.ogf',(-1.96,.05,-1.20),(0,math.pi/2,0),floor=True)
mesh('poster','dynamics/decor/poster2.ogf',(-.95,1.8,3.12),(-math.pi/2,0,0),(.55,.55,.55))
mesh('gas cylinder','dynamics/decor/gaz_balon.ogf',(-1.75,.01,2.85),floor=True)
mesh('pot','dynamics/decor/pot.ogf',(-1.4,1.30,2.65),scale=(.5,.5,.5),floor=True)
mesh('journal','dynamics/decor/notes_writing_book.ogf',(.05,.65421,.40),scale=(.7,.7,.7),floor=True)
mesh('tin','dynamics/devices/dev_conserv/dev_conserv.ogf',(-.10,.65421,.48),floor=True)

batches=collections.defaultdict(bytearray)
for p in parts:
    a.read('textures/'+p['texture']+'.dds')
    for i in p['index']:
        batches[p['texture'].replace('/','\\')].extend(struct.pack('<3f3fI2f',*p['position'][i*3:i*3+3],*p['normal'][i*3:i*3+3],0xffffff | (0xff000000 if p['emissive'] else 0),*p['uv'][i*2:i*2+2]))
triangles=sum(len(v)//108 for v in batches.values())
assert triangles<100000 and len(batches)<=128
binary=bytearray(b'NCRM'+struct.pack('<II',2,len(batches)))
for texture,vertices in sorted(batches.items()):binary.extend(texture.encode('cp1251')+b'\0'+struct.pack('<I',len(vertices)//36)+vertices)
out.mkdir(parents=True,exist_ok=True); (out/'personal_room.room').write_bytes(binary)
views=[dict(name='Комната',eye=[-.70,1.25,-1.95],target=[.35,1.0,1.9]),
       dict(name='Карта',eye=[.20,1.65,1.25],target=[.55,1.70,3.05]),
       dict(name='КПК',eye=[1.35,1.50,1.45],target=[1.50,1.40,3.05]),
       dict(name='Рюкзак',eye=[.90,1.10,.9],target=[1.52,.73,2.22]),
       dict(name='Сейф',eye=[-.75,1.10,-.10],target=[-1.55,.65,1.15]),
       dict(name='Дверь',eye=[-.75,1.45,.10],target=[-1.90,1.0,-1.20])]
lamp=[-.10,1.05,.85]; values=sum((v['eye']+v['target'] for v in views),[])+lamp+[.45,.61,2.37]
(out/'personal_room.camera').write_bytes(b'NCRC'+struct.pack('<I',2)+struct.pack('<42f',*values))
manifest=dict(version=2,source='l01_escape rear trader bunker structural geometry',origin=origin,
    shell_materials=dict(shell_counts),objects=objects,views=views,lamp=lamp,seat=[.45,.61,2.37],triangles=triangles,
    materials=sorted(batches),source_sha256=provenance,level_sha256=hashlib.sha256((runtime/'gamedata/levels/l01_escape/level').read_bytes()).hexdigest())
(out/'personal_room.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(root.parent/'build-logs/hideout-preview.json').write_text(json.dumps(dict(parts=parts,manifest=manifest)),encoding='utf-8')
print(f'Bunker shell: {sum(shell_counts.values())} triangles; furnished: {triangles} triangles, {len(batches)} materials; backpack: {bag[0]["id"]}')
