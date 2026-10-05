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
  0 PDA on the table  -> server and entering the Zone
  1 radio             -> menu music
  2 character on sofa -> characters
  3 toolbox on crate  -> settings
  4 bunker door       -> leave the game (behind the camera)
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
X0, X1 = -2.5, 2.5
Z0, Z1 = -2.6, 3.0
H = 3.0
WAINSCOT = 1.0
WALL, LOWER, FLOOR, CEILING = 'crete/crete_beton_lom', 'wood/wood_walls8', 'wood/wood_plank6_bar', 'crete/crete_beton_lom'
TILE = 2.0  # metres per texture repeat on every surface

parts, objects, provenance, report = [], [], {}, []


def panel(texture, points, normal, uv=None, owner='shell'):
    """Quad with the given inward normal; UVs at TILE metres per repeat."""
    w = math.dist(points[0], points[1]) / TILE
    h = math.dist(points[1], points[2]) / TILE
    edge1 = [points[1][k] - points[0][k] for k in range(3)]
    edge2 = [points[2][k] - points[0][k] for k in range(3)]
    cross = [edge1[1] * edge2[2] - edge1[2] * edge2[1], edge1[2] * edge2[0] - edge1[0] * edge2[2],
             edge1[0] * edge2[1] - edge1[1] * edge2[0]]
    indices = [0, 1, 2, 0, 2, 3] if sum(cross[k] * normal[k] for k in range(3)) >= 0 else [0, 2, 1, 0, 3, 2]
    parts.append(dict(texture=texture, position=sum((list(p) for p in points), []), normal=list(normal) * 4,
                      uv=uv or [0, 0, w, 0, w, h, 0, h], index=indices, emissive=False, owner=owner))


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


def surface_y(owner, x, z):
    """Highest surface of `owner`'s triangles straight below (x, z), or None:
    the real shelf board under an object, not the top of the posts."""
    best = None
    for p in parts:
        if p.get('owner') != owner:
            continue
        P, I = p['position'], p['index']
        for t in range(0, len(I), 3):
            a_, b_, c_ = (P[I[t + k] * 3:I[t + k] * 3 + 3] for k in range(3))
            d = (b_[2] - c_[2]) * (a_[0] - c_[0]) + (c_[0] - b_[0]) * (a_[2] - c_[2])
            if abs(d) < 1e-12:
                continue
            l1 = ((b_[2] - c_[2]) * (x - c_[0]) + (c_[0] - b_[0]) * (z - c_[2])) / d
            l2 = ((c_[2] - a_[2]) * (x - c_[0]) + (a_[0] - c_[0]) * (z - c_[2])) / d
            l3 = 1 - l1 - l2
            if min(l1, l2, l3) < -1e-6:
                continue
            y = l1 * a_[1] + l2 * b_[1] + l3 * c_[1]
            best = y if best is None else max(best, y)
    return best


def surface_under(owner, x, z, half_x, half_z):
    """Support height for an object centred at (x, z): highest surface of
    `owner` sampled at the centre and four inner points of the footprint."""
    samples = [surface_y(owner, x + dx * half_x * 0.5, z + dz * half_z * 0.5)
               for dx, dz in ((0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))]
    samples = [v for v in samples if v is not None]
    assert samples, f'no {owner} surface under ({x}, {z})'
    return max(samples)


def on(owner, name, asset, x, z, half=(0.05, 0.05), **kw):
    """Place `asset` on the real surface of `owner` under (x, z)."""
    return place(name, asset, x, z, surface_under(owner, x, z, *half), **kw)


picks = {}
HALF_PI = math.pi / 2
# Wall decor rotations: flat models face the room from each wall.
BACK_WALL, LEFT_WALL, RIGHT_WALL, FRONT_WALL = (-HALF_PI, 0, 0), (-HALF_PI, -HALF_PI, 0), (-HALF_PI, HALF_PI, 0), (-HALF_PI, math.pi, 0)
SOFA_X = -0.15
SOFA_Z = Z1 - 0.55
# Sofa against the back wall facing the camera. The character sits on its
# left half with the table in front; the backpack lies on the right half.
place('sofa', 'dynamics/efp_props/prop_couch_1.ogf', SOFA_X, SOFA_Z, rot=(0, HALF_PI, 0))
SEAT_X = SOFA_X - 0.45
TABLE = (SEAT_X + 0.05, SOFA_Z - 1.20)
# Thin rug under the table; furniture stands through it on the floor.
place('rug', 'dynamics/decor/rug.ogf', TABLE[0] + 0.15, TABLE[1] + 0.15, rot=(0, HALF_PI, 0), scale=(0.6, 0.3, 0.48))
_, table_hi = place('table', 'dynamics/efp_props/prop_table_2.ogf', TABLE[0], TABLE[1], rot=(0, HALF_PI, 0))
TOP = table_hi[1]
LAMP = (TABLE[0] + 0.42, TABLE[1] + 0.18)
place('lamp', 'dynamics/el_tehnika/table_lamp_01.ogf', LAMP[0], LAMP[1], TOP, rot=(0, 2.6, 0))
PDA = (TABLE[0] - 0.24, TABLE[1] - 0.18)
place('PDA', 'netcoop/dev_pda.ogf', PDA[0], PDA[1], TOP, rot=(0, 0.35, 0), scale=(1.6, 1.6, 1.6), pick=0)
place('journal', 'dynamics/decor/notes_writing_book.ogf', TABLE[0] + 0.02, TABLE[1] + 0.12, TOP, rot=(0, 0.3, 0), scale=(0.7, 0.7, 0.7))
place('tin', 'dynamics/devices/dev_conserv/dev_conserv.ogf', TABLE[0] + 0.36, TABLE[1] - 0.22, TOP)
place('mug', 'dynamics/kitchen_room/kitchen_krujka.ogf', TABLE[0] + 0.18, TABLE[1] - 0.05, TOP, rot=(0, 1.1, 0))
place('ashtray', 'dynamics/decor/ashtray.ogf', TABLE[0] - 0.42, TABLE[1] + 0.20, TOP, scale=(0.8, 0.8, 0.8))
CUSHION_Z = SOFA_Z - 0.20
on('sofa', 'backpack', 'dynamics/equipments/sumka3.ogf', SOFA_X + 0.55, CUSHION_Z, (0.2, 0.15),
   rot=(0, HALF_PI + 0.25, 0), scale=(1.15, 1.15, 1.15))
# Wooden shelf unit right of the sofa: small radio on the top board, bottles
# on the middle one, tins on the bottom one.
SHELF_X = X1 - 0.74
SHELF_Z = Z1 - 0.25
_, shelf_hi = place('shelf', 'dynamics/efp_props/prop_shelf_1.ogf', SHELF_X, SHELF_Z, rot=(0, HALF_PI, 0))
RADIO = (SHELF_X - 0.15, SHELF_Z - 0.02)
SHELF_TOP = surface_under('shelf', RADIO[0], RADIO[1], 0.23, 0.07)
place('radio', 'dynamics/el_tehnika/priemnik_gorizont.ogf', RADIO[0], RADIO[1], SHELF_TOP, rot=(0, math.pi, 0),
      scale=(1.3, 1.3, 1.3), pick=1)
print(f'shelf posts top {shelf_hi[1]:.3f} m, board under the radio {SHELF_TOP:.3f} m')
on('shelf', 'jar', 'dynamics/kitchen_room/bottle_3l.ogf', SHELF_X + 0.40, SHELF_Z - 0.02, scale=(0.75, 0.75, 0.75))
on('shelf', 'shelf mug', 'dynamics/efp_props/prop_mug.ogf', SHELF_X + 0.14, SHELF_Z - 0.06, rot=(0, 2.2, 0))
# Lower board tops measured on prop_shelf_1: 0.540 and 0.200 m.
for i, (asset, dx, turn) in enumerate((('vanilla/drink/dev_vodka', -0.48, 0.0), ('vanilla/drink/dev_vodka2', -0.38, 0.8),
                                       ('vanilla/drink/dev_vodka', -0.29, 2.0), ('vanilla/drink/dev_beer2', -0.12, 0.4),
                                       ('vanilla/drink/dev_beer2', -0.03, 1.9), ('vanilla/drink/dev_mineral_water2', 0.10, 0.3))):
    place(f'bottle {i + 1}', f'dynamics/{asset}.ogf', SHELF_X + dx, SHELF_Z - 0.03 + 0.03 * (i % 2), 0.54, rot=(0, turn, 0))
place('ration', 'dynamics/vanilla/food/ration_ru2.ogf', SHELF_X + 0.38, SHELF_Z - 0.02, 0.54, rot=(0, HALF_PI, 0))
for i, (asset, dx) in enumerate((('dev_tushonka2', -0.50), ('dev_tushonka2', -0.41), ('dev_tushonka2', -0.32),
                                 ('dev_beans2', -0.16), ('dev_corn2', -0.06), ('dev_beans2', 0.04))):
    place(f'tin {i + 1}', f'dynamics/vanilla/food/{asset}.ogf', SHELF_X + dx, SHELF_Z - 0.04, 0.20, rot=(0, i * 0.9, 0))
place('conserve 1', 'dynamics/vanilla/food/dev_conserv2.ogf', SHELF_X + 0.30, SHELF_Z - 0.04, 0.20)
place('conserve 2', 'dynamics/vanilla/food/dev_conserv2.ogf', SHELF_X + 0.24, SHELF_Z + 0.06, 0.20, rot=(0, 0.7, 0))
place('book', 'dynamics/equipments/trade/book2.ogf', SHELF_X + 0.48, SHELF_Z - 0.04, 0.20, rot=(0, 0.2, 0), scale=(1.3, 1.3, 1.3))
place('clock', 'dynamics/efp_props/prop_clock.ogf', SHELF_X - 0.05, Z1 - 0.005, rot=BACK_WALL, y=1.55)
# Kitchen corner left of the sofa: the stove (front = model +X) stands with
# its back to the back wall facing the camera, the gas cylinder between it
# and the sofa, a kettle on the cooktop.
STOVE = (X0 + 0.40, Z1 - 0.48)
place('stove', 'dynamics/efp_props/prop_stove2.ogf', STOVE[0], STOVE[1], rot=(0, HALF_PI, 0))
on('stove', 'kettle', 'dynamics/kitchen_room/teapot_1.ogf', STOVE[0] + 0.12, STOVE[1] - 0.05, (0.08, 0.08), rot=(0, 2.4, 0), scale=(0.8, 0.8, 0.8))
place('gas cylinder', 'dynamics/decor/gaz_balon.ogf', X0 + 1.02, Z1 - 0.30, scale=(0.85, 0.85, 0.85))
place('bucket', 'dynamics/workshop_room/vedro_01.ogf', X0 + 0.28, 1.35, rot=(0, 0.6, 0), scale=(0.75, 0.75, 0.75))
place('poster left', 'dynamics/decor/poster6.ogf', X0 + 0.005, 1.10, rot=LEFT_WALL, scale=(0.75, 0.75, 0.75), y=1.80)
# Zone map pinned above the sofa.
place('map', 'dynamics/decor/map2.ogf', SOFA_X, Z1 - 0.005, rot=BACK_WALL, scale=(0.55, 0.55, 0.55), y=1.80)
# Soviet poster «Революционный проект «Фолк Восянка»» on the back wall behind
# the seated character, between the stove and the map. Its texture comes from
# the owner's photo (tools/make-soviet-poster.py); without it the wall stays bare.
POSTER_TEXTURE = 'netcoop/poster_folk'
POSTER_DDS = root / 'scripts/netcoop-overlay/client/textures' / (POSTER_TEXTURE + '.dds')
if POSTER_DDS.exists():
    px0, px1, py0, py1, pz = -1.60, -1.00, 1.36, 2.26, Z1 - 0.004
    panel(POSTER_TEXTURE, [(px0, py0, pz), (px0, py1, pz), (px1, py1, pz), (px1, py0, pz)], (0, 0, -1),
          uv=[0, 1, 0, 0, 1, 0, 1, 1], owner='poster')
# Right wall: a crate with the toolbox (settings), an ammo box, posters.
CRATE = (X1 - 0.46, 0.75)
place('crate', 'dynamics/box/box_wood_01.ogf', CRATE[0], CRATE[1], rot=(0, 0.06, 0))
TOOLBOX = (CRATE[0] - 0.02, CRATE[1] - 0.05)
on('crate', 'toolbox', 'dynamics/devices/dev_instrument_1/dev_instrument_1.ogf', TOOLBOX[0], TOOLBOX[1], (0.15, 0.15),
   rot=(0, HALF_PI + 0.35, 0), pick=3)
place('ammo box', 'dynamics/efp_props/prop_ammo_box.ogf', X1 - 0.31, 1.86)
place('poster right', 'dynamics/decor/poster2.ogf', X1 - 0.005, CRATE[1], rot=RIGHT_WALL, scale=(0.55, 0.55, 0.55), y=1.75)
place('painting', 'dynamics/decor/kartina03.ogf', X1 - 0.005, 1.90, rot=RIGHT_WALL, scale=(0.9, 0.9, 0.9), y=1.55)
# Heavy bunker door in the wall behind the camera; the camera turns to it.
place('door', 'dynamics/door/door_trader.ogf', -0.705, Z0 + 0.14, pick=4)
# Small bracket lamp over the door: the dim second light of the room.
place('door lamp', 'dynamics/light/light_uglovaya_1_glass.ogf', 0.0, Z0 - 0.05, rot=(0, -HALF_PI, 0), y=2.80)
BULB = [0.0, 2.84, Z0 + 0.16]
place('canister', 'dynamics/balon/kanistra.ogf', -1.20, Z0 + 0.22, rot=(0, HALF_PI, 0))
place('boots', 'dynamics/equipments/trade/boots.ogf', 1.00, Z0 + 0.30, rot=(0, 0.3, 0), scale=(1.1, 1.1, 1.1))
place('poster door', 'dynamics/decor/poster5.ogf', 1.45, Z0 + 0.005, rot=FRONT_WALL, scale=(0.9, 0.9, 0.9), y=1.65)

# Wall containment: nothing may pass through the shell.
problems = []
for r in report:
    if r['lo'][0] < X0 - 0.005 or r['hi'][0] > X1 + 0.005 or r['lo'][2] < Z0 - 0.005 or r['hi'][2] > Z1 + 0.005 or r['hi'][1] > H:
        problems.append(f"{r['name']} crosses the shell: {r['lo']} .. {r['hi']}")
    if r['gap'] is not None and abs(r['gap']) > 0.002:
        problems.append(f"{r['name']} not on its support: gap {r['gap']} m")
    if r['gap'] is None and min(Z1 - r['hi'][2], r['lo'][2] - Z0, X1 - r['hi'][0], r['lo'][0] - X0) > 0.03:
        problems.append(f"{r['name']} hangs away from its wall: {r['lo']} .. {r['hi']}")

batches = collections.defaultdict(bytearray)
for p in parts:
    if p['owner'] != 'poster':  # the poster ships in the overlay, not the game archives
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
# hovering), on the left half of the sofa, facing the camera (-Z).
SEAT_HEADING = math.pi
seat = [SEAT_X, 0.49, SOFA_Z - 0.12]
picks[2] = ([seat[0] - 0.35, 0.0, seat[2] - 0.70], [seat[0] + 0.35, 1.45, seat[2] + 0.35])
lamp = [LAMP[0] - 0.04, TOP + 0.35, LAMP[1] - 0.09]
# Light model shared by the game shader and the room check page (three.js
# units: point intensity in candela, physical decay 2 with a range cutoff).
lights = dict(lamp=dict(color='#ffb060', intensity=9.0, range=9.0, position=lamp),
              bulb=dict(color='#ffc890', intensity=3.0, range=6.0, position=BULB),
              hemisphere=dict(sky='#5a6270', ground='#2a2018', intensity=0.12))
# Close-ups keep the object off-centre, away from the menu panel beside it:
# PDA left of the server panel, radio right of the music panel, character
# left of the characters panel.
views = [dict(name='overview', eye=[0.00, 1.62, -2.20], target=[0.00, 0.95, 1.80]),
         dict(name='pda', eye=[PDA[0] + 0.42, 1.22, PDA[1] - 0.62], target=[PDA[0] + 0.26, TOP + 0.02, PDA[1] + 0.02]),
         dict(name='radio', eye=[RADIO[0] - 0.75, 1.40, RADIO[1] - 1.30], target=[RADIO[0] - 0.42, SHELF_TOP + 0.12, RADIO[1]]),
         dict(name='character', eye=[seat[0] + 0.62, 1.40, seat[2] - 1.90], target=[seat[0] + 0.50, 0.95, seat[2]]),
         dict(name='settings', eye=[TOOLBOX[0] - 1.20, 1.45, TOOLBOX[1] - 0.70], target=[TOOLBOX[0], 0.95, TOOLBOX[1]]),
         # The door behind the camera, whole in frame from 3 m. The engine
         # lerps eye and target, so the side offset makes the 180 degree turn
         # a level swing instead of a dip through the floor.
         dict(name='door', eye=[1.20, 1.55, 0.50], target=[-0.10, 1.30, Z0])]
out.mkdir(parents=True, exist_ok=True)
(out / 'personal_room.room').write_bytes(binary)
values = sum((v['eye'] + v['target'] for v in views), []) + lamp + seat + [SEAT_HEADING]
(out / 'personal_room.camera').write_bytes(b'NCRC' + struct.pack('<I', 3) + struct.pack('<43f', *values))
# Cursor picking boxes, padded so the small PDA and toolbox are easy to hit.
pick_data = bytearray(b'NCRP' + struct.pack('<II', 1, 5))
for index in range(5):
    lo, hi = picks.get(index, ([1, 1, 1], [0, 0, 0]))
    pad = 0.06 if index == 0 else 0.05 if index == 3 else 0.02
    pick_data.extend(struct.pack('<6f', *(v - pad for v in lo), *(v + pad for v in hi)) if index in picks
                     else struct.pack('<6f', 1, 1, 1, 0, 0, 0))
(out / 'personal_room.pick').write_bytes(pick_data)


def linear(color, scale=1.0):
    """sRGB hex colour to linear RGB (three.js ColorManagement), scaled."""
    c = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [scale * (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c]


def hlsl(v):
    return 'float3(%s)' % ','.join(f'{x:.5f}' for x in v)


shader = root / 'scripts/netcoop-overlay/client/shaders/r3/netcoop_menu_lights.h'
shader_lines = [
    '// Generated by scripts/build-lostzone-room.py: the lights of the menu room,',
    '// the same values the room check page renders with.',
    f"static const float3 menu_lamp_color={hlsl(linear(lights['lamp']['color'], lights['lamp']['intensity']))};",
    f"static const float menu_lamp_range={lights['lamp']['range']:.3f};",
    f"static const float3 menu_bulb_position={hlsl(BULB)};",
    f"static const float3 menu_bulb_color={hlsl(linear(lights['bulb']['color'], lights['bulb']['intensity']))};",
    f"static const float menu_bulb_range={lights['bulb']['range']:.3f};",
    f"static const float3 menu_sky_color={hlsl(linear(lights['hemisphere']['sky'], lights['hemisphere']['intensity']))};",
    f"static const float3 menu_ground_color={hlsl(linear(lights['hemisphere']['ground'], lights['hemisphere']['intensity']))};",
]
shader.write_bytes(''.join(line + '\r\n' for line in shader_lines).encode('ascii'))
manifest = dict(version=3, source='Lost Zone closed bunker box', room=dict(x=[X0, X1], z=[Z0, Z1], height=H),
                materials_set=dict(wall=WALL, lower=LOWER, floor=FLOOR, ceiling=CEILING, tile_m=TILE),
                objects=objects, views=views, lamp=lamp, lights=lights, seat=seat, seat_heading=SEAT_HEADING, picks={str(k): v for k, v in picks.items()}, triangles=triangles, materials=sorted(batches),
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
