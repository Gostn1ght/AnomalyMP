"""Build the Lost Zone menu room: a closed bunker box from installed game assets.

Four walls, floor and ceiling (the wall behind the camera too), so no camera
angle sees empty space. One material set at one texel density (2 m per tile):
concrete walls and ceiling, dark wood wainscot and floor. Every furnishing is
dropped onto its support (floor, table top, stool) by its lowest vertex and
checked against the walls; the support report is printed and stored.

Outputs: personal_room.room (NCRM v2; vertex colour RGB holds the
interactive object id 1..5, 255 elsewhere), personal_room.camera (NCRC v3:
6 views, lamp, seat, seat heading), personal_room.pick (NCRP v1: one box per
interactive object for cursor picking), personal_room.json, and
build-logs/lostzone-room.json for scripts/check-room.py.

View indices used by the menu (menu_room::focus / interaction = view + 1):
  0 PDA on the table  -> server address
  1 radio             -> settings
  2 character on sofa -> characters
  3 character (spare, same view)
  4 bunker door       -> enter the Zone
"""
from pathlib import Path
import collections, hashlib, json, math, struct, sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools/room-editor'))
from assets import Assets
from server import rotate

runtime = root.parent / 'gamma-runtime'
out = root / 'scripts/netcoop-overlay/client/meshes/netcoop'
a = Assets(runtime, root / 'tools/room-editor'); a.index()

# Room box (X right, Y up, Z away from the camera), metres.
X0, X1 = -2.2, 2.2
Z0, Z1 = -2.6, 3.0
H = 3.0
WAINSCOT = 1.0
WALL, LOWER, FLOOR, CEILING = 'crete/crete_beton_lom', 'wood/wood_walls8', 'wood/wood_plank6_bar', 'crete/crete_beton_lom'
TILE = 2.0  # metres per texture repeat on every surface

parts, objects, provenance, report = [], [], {}, []


def panel(texture, points, normal):
    """Quad with the given inward normal; UVs at TILE metres per repeat."""
    w = math.dist(points[0], points[1]) / TILE
    h = math.dist(points[1], points[2]) / TILE
    edge1 = [points[1][k] - points[0][k] for k in range(3)]
    edge2 = [points[2][k] - points[0][k] for k in range(3)]
    cross = [edge1[1] * edge2[2] - edge1[2] * edge2[1], edge1[2] * edge2[0] - edge1[0] * edge2[2],
             edge1[0] * edge2[1] - edge1[1] * edge2[0]]
    indices = [0, 1, 2, 0, 2, 3] if sum(cross[k] * normal[k] for k in range(3)) >= 0 else [0, 2, 1, 0, 3, 2]
    parts.append(dict(texture=texture, position=sum((list(p) for p in points), []), normal=list(normal) * 4,
                      uv=[0, 0, w, 0, w, h, 0, h], index=indices, emissive=False, owner='shell'))


def wall(texture, x0, z0, x1, z1, y0, y1, normal):
    panel(texture, [(x0, y0, z0), (x0, y1, z0), (x1, y1, z1), (x1, y0, z1)], normal)


# Shell: floor, ceiling, four walls; lower wainscot sits 1 cm in front.
panel(FLOOR, [(X0, 0, Z0), (X0, 0, Z1), (X1, 0, Z1), (X1, 0, Z0)], (0, 1, 0))
panel(CEILING, [(X0, H, Z0), (X1, H, Z0), (X1, H, Z1), (X0, H, Z1)], (0, -1, 0))
for texture, inset, y0, y1 in ((WALL, 0.0, WAINSCOT, H), (LOWER, 0.01, 0.0, WAINSCOT), (WALL, 0.0, 0.0, WAINSCOT)):
    wall(texture, X0, Z1 - inset, X1, Z1 - inset, y0, y1, (0, 0, -1))   # back
    wall(texture, X0, Z0 + inset, X1, Z0 + inset, y0, y1, (0, 0, 1))    # behind the camera
    wall(texture, X0 + inset, Z0, X0 + inset, Z1, y0, y1, (1, 0, 0))    # left
    wall(texture, X1 - inset, Z0, X1 - inset, Z1, y0, y1, (-1, 0, 0))   # right


def bounds(asset, rot, scale):
    m = a.mesh(asset)
    pts = [rotate([p['position'][i + k] * scale[k] for k in range(3)], rot)
           for p in m['parts'] for i in range(0, len(p['position']), 3)]
    return m, [min(v[k] for v in pts) for k in range(3)], [max(v[k] for v in pts) for k in range(3)]


def place(name, asset, x, z, support=0.0, rot=(0, 0, 0), scale=(1, 1, 1), y=None, pick=None):
    """Put the object's lowest vertex on `support` (or at explicit y for wall
    decor); record its world bounds for the support/wall report."""
    m, lo, hi = bounds(asset, rot, scale)
    py = support - lo[1] if y is None else y
    pos = (x, py, z)
    obj = dict(name=name, asset=asset, position=list(pos), rotation=list(rot), scale=list(scale), hidden=False,
               uid=str(len(objects) + 1))
    objects.append(obj)
    provenance[asset] = hashlib.sha256(a.read('meshes/' + asset)).hexdigest()
    world_lo = [lo[k] + pos[k] for k in range(3)]
    world_hi = [hi[k] + pos[k] for k in range(3)]
    report.append(dict(name=name, bottom=round(world_lo[1], 4), support=None if y is not None else support,
                       gap=None if y is not None else round(world_lo[1] - support, 4),
                       lo=[round(v, 3) for v in world_lo], hi=[round(v, 3) for v in world_hi]))
    for p in m['parts']:
        q = dict(p); q['position'] = []; q['normal'] = []; q['owner'] = name; q['pick'] = pick
        for i in range(0, len(p['position']), 3):
            point = rotate([p['position'][i + k] * scale[k] for k in range(3)], rot)
            normal = rotate([p['normal'][i + k] / scale[k] for k in range(3)], rot)
            length = math.sqrt(sum(v * v for v in normal)) or 1
            q['position'].extend(point[k] + pos[k] for k in range(3))
            q['normal'].extend(v / length for v in normal)
        parts.append(q)
    if pick is not None:
        picks[pick] = (world_lo, world_hi)
    return world_lo, world_hi


picks = {}
HALF_PI = math.pi / 2
SOFA_X = -0.55
SOFA_Z = Z1 - 0.55
# Sofa against the back wall facing the camera, table in front of it.
place('sofa', 'dynamics/efp_props/prop_couch_1.ogf', SOFA_X, SOFA_Z, rot=(0, HALF_PI, 0))
_, table_hi = place('table', 'dynamics/efp_props/prop_table_2.ogf', SOFA_X, SOFA_Z - 1.20, rot=(0, HALF_PI, 0))
TOP = table_hi[1]
LAMP = (SOFA_X + 0.42, SOFA_Z - 1.02)
place('lamp', 'dynamics/el_tehnika/table_lamp_01.ogf', LAMP[0], LAMP[1], TOP, rot=(0, 2.6, 0))
PDA = (SOFA_X - 0.28, SOFA_Z - 1.40)
place('PDA', 'netcoop/dev_pda.ogf', PDA[0], PDA[1], TOP, rot=(0, 0.35, 0), scale=(1.6, 1.6, 1.6), pick=0)
place('journal', 'dynamics/decor/notes_writing_book.ogf', SOFA_X + 0.05, SOFA_Z - 1.05, TOP, rot=(0, 0.3, 0), scale=(0.7, 0.7, 0.7))
place('tin', 'dynamics/devices/dev_conserv/dev_conserv.ogf', SOFA_X + 0.38, SOFA_Z - 1.42, TOP)
# Small radio on a wooden shelf unit against the back wall, right of the sofa.
SHELF_X = X1 - 0.78
_, shelf_hi = place('shelf', 'dynamics/efp_props/prop_shelf_1.ogf', SHELF_X, Z1 - 0.25, rot=(0, HALF_PI, 0))
place('radio', 'dynamics/el_tehnika/priemnik_gorizont.ogf', SHELF_X - 0.10, Z1 - 0.27, shelf_hi[1], rot=(0, math.pi, 0),
      scale=(1.3, 1.3, 1.3), pick=1)
# Heavy bunker door in the wall behind the camera; the camera turns to it.
place('door', 'dynamics/door/door_trader.ogf', -0.705, Z0 + 0.14, pick=4)
# Decor.
place('stove', 'dynamics/efp_props/prop_stove2.ogf', X0 + 0.40, 0.10, rot=(0, -HALF_PI, 0))
place('gas cylinder', 'dynamics/decor/gaz_balon.ogf', X0 + 0.30, 0.85)
place('backpack', 'dynamics/equipments/sumka3.ogf', SHELF_X - 0.20, Z1 - 0.95, rot=(0, 0.4, 0), scale=(1.2, 1.2, 1.2))
place('poster', 'dynamics/decor/poster2.ogf', SOFA_X + 0.55, Z1 - 0.02, rot=(-HALF_PI, 0, 0), scale=(0.55, 0.55, 0.55), y=1.80)
place('map', 'dynamics/decor/map1.ogf', X0 + 0.02, 0.45, rot=(-HALF_PI, -HALF_PI, 0), scale=(0.55, 0.55, 0.55), y=1.75)

# Wall containment: nothing may pass through the shell.
problems = []
for r in report:
    if r['lo'][0] < X0 - 0.005 or r['hi'][0] > X1 + 0.005 or r['lo'][2] < Z0 - 0.005 or r['hi'][2] > Z1 + 0.005 or r['hi'][1] > H:
        problems.append(f"{r['name']} crosses the shell: {r['lo']} .. {r['hi']}")
    if r['gap'] is not None and abs(r['gap']) > 0.002:
        problems.append(f"{r['name']} not on its support: gap {r['gap']} m")
    if r['gap'] is None and min(Z1 - r['hi'][2], X1 - r['hi'][0], r['lo'][0] - X0) > 0.03:
        problems.append(f"{r['name']} hangs away from its wall: {r['lo']} .. {r['hi']}")

batches = collections.defaultdict(bytearray)
for p in parts:
    a.read('textures/' + p['texture'] + '.dds')
    # Vertex colour RGB = interactive object id (pick index + 1); 255 = none.
    ident = p['pick'] + 1 if p.get('pick') is not None else 255
    for i in p['index']:
        batches[p['texture'].replace('/', '\\')].extend(struct.pack('<3f3fI2f', *p['position'][i * 3:i * 3 + 3],
                                                                    *p['normal'][i * 3:i * 3 + 3], ident * 0x010101,
                                                                    *p['uv'][i * 2:i * 2 + 2]))
triangles = sum(len(v) // 108 for v in batches.values())
assert triangles < 100000 and len(batches) <= 128
binary = bytearray(b'NCRM' + struct.pack('<II', 2, len(batches)))
for texture, vertices in sorted(batches.items()):
    binary.extend(texture.encode('cp1251') + b'\0' + struct.pack('<I', len(vertices) // 36) + vertices)

# Seated character: pelvis just above the 0.34 m cushion (0.61 left it
# hovering), on the seat half of the sofa, facing the door (-X).
SEAT_HEADING = math.pi
seat = [SOFA_X - 0.05, 0.49, SOFA_Z - 0.12]
picks[2] = ([seat[0] - 0.35, 0.0, seat[2] - 0.70], [seat[0] + 0.35, 1.45, seat[2] + 0.35])
lamp = [LAMP[0] - 0.04, TOP + 0.35, LAMP[1] - 0.09]
views = [dict(name='overview', eye=[0.00, 1.62, -2.20], target=[0.00, 0.95, 1.80]),
         dict(name='pda', eye=[PDA[0] + 0.20, 1.30, PDA[1] - 0.70], target=[PDA[0], TOP + 0.02, PDA[1]]),
         dict(name='radio', eye=[SHELF_X - 0.45, 1.55, Z1 - 1.30], target=[SHELF_X - 0.10, shelf_hi[1] + 0.15, Z1 - 0.27]),
         dict(name='character', eye=[seat[0] + 0.25, 1.45, seat[2] - 1.75], target=[seat[0], 1.00, seat[2]]),
         dict(name='character', eye=[seat[0] + 0.25, 1.45, seat[2] - 1.75], target=[seat[0], 1.00, seat[2]]),
         # Swing to the door behind the camera from the side, so the look
         # direction never passes through the eye during the transition.
         dict(name='door', eye=[0.80, 1.55, -0.60], target=[0.00, 1.30, Z0])]
out.mkdir(parents=True, exist_ok=True)
(out / 'personal_room.room').write_bytes(binary)
values = sum((v['eye'] + v['target'] for v in views), []) + lamp + seat + [SEAT_HEADING]
(out / 'personal_room.camera').write_bytes(b'NCRC' + struct.pack('<I', 3) + struct.pack('<43f', *values))
# Cursor picking boxes, padded so the small PDA is easy to hit; slot 3 empty.
pick_data = bytearray(b'NCRP' + struct.pack('<II', 1, 5))
for index in range(5):
    lo, hi = picks.get(index, ([1, 1, 1], [0, 0, 0]))
    pad = 0.06 if index == 0 else 0.02
    pick_data.extend(struct.pack('<6f', *(v - pad for v in lo), *(v + pad for v in hi)) if index in picks
                     else struct.pack('<6f', 1, 1, 1, 0, 0, 0))
(out / 'personal_room.pick').write_bytes(pick_data)
manifest = dict(version=3, source='Lost Zone closed bunker box', room=dict(x=[X0, X1], z=[Z0, Z1], height=H),
                materials_set=dict(wall=WALL, lower=LOWER, floor=FLOOR, ceiling=CEILING, tile_m=TILE),
                objects=objects, views=views, lamp=lamp, seat=seat, seat_heading=SEAT_HEADING, picks={str(k): v for k, v in picks.items()}, triangles=triangles, materials=sorted(batches),
                support=report, problems=problems, source_sha256=provenance)
(out / 'personal_room.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(root.parent / 'build-logs').mkdir(exist_ok=True)
(root.parent / 'build-logs/lostzone-room.json').write_text(json.dumps(dict(parts=parts, manifest=manifest)), encoding='utf-8')
for r in report:
    print(f"{r['name']:14s} bottom {r['bottom']:7.3f}  gap {r['gap']}")
print(f'{triangles} triangles, {len(batches)} materials')
if problems:
    print('PROBLEMS:\n  ' + '\n  '.join(problems))
    sys.exit(1)
print('support and wall checks OK')
