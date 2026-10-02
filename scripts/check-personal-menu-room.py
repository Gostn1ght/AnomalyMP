"""Check room geometry and support surfaces without launching or controlling UI."""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import struct

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('room_builder', root/'scripts/build-personal-menu-room.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('meshes', type=Path)
args = parser.parse_args()
scene = root/'scripts/netcoop-overlay/client/meshes/netcoop/personal_room.room'
manifest = json.loads(scene.with_suffix('.json').read_text())
objects = {obj['name']: obj for obj in manifest['objects']}

def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a, b): return sum(x*y for x, y in zip(a,b))
def ray_hit(origin, direction, tri):
    edge1, edge2 = sub(tri[1],tri[0]), sub(tri[2],tri[0])
    p = cross(direction,edge2); det = dot(edge1,p)
    if abs(det) < 1e-8: return None
    t = sub(origin,tri[0]); u = dot(t,p)/det
    q = cross(t,edge1); v = dot(direction,q)/det
    if u < -1e-6 or v < -1e-6 or u+v > 1.000001: return None
    distance = dot(edge2,q)/det
    return distance if distance > 0 else None

def model_triangles(obj):
    data = dict(builder.chunks((args.meshes/'dynamics/Decor'/(obj['model']+'.ogf')).read_bytes()))
    result = []
    for _, child in builder.chunks(data[9]):
        parts = dict(builder.chunks(child))
        if b'lightplanes' in parts[2]: continue
        vertices = parts[3]; _, count = struct.unpack_from('<II',vertices)
        points = []
        for i in range(count):
            point = struct.unpack_from('<3f',vertices,8+i*60)
            point = builder.rotate(tuple(point[k]*obj['scale'][k] for k in range(3)),obj['angles'])
            points.append(tuple(point[k]+obj['position'][k] for k in range(3)))
        count, = struct.unpack_from('<I',parts[4])
        indices = struct.unpack_from('<'+str(count)+'H',parts[4],4)
        result.extend(tuple(points[i] for i in indices[start:start+3]) for start in range(0,count,3))
    return result

table = model_triangles(objects['table'])
pda = model_triangles(objects['PDA'])
points = [v for tri in pda for v in tri]
bottom = min(p[1] for p in points)
centre = objects['PDA']['position']
hits = [ray_hit((centre[0],2,centre[2]),(0,-1,0),tri) for tri in table]
top = 2-min(d for d in hits if d is not None)
assert abs(bottom-top) < .001, ('PDA support gap',bottom-top)

data = scene.read_bytes(); magic, version, count = struct.unpack_from('<4sII',data)
assert magic == b'NCRM' and version == 2
offset = 12; triangles = 0; all_triangles = []
for _ in range(count):
    end = data.index(0,offset); texture = data[offset:end].decode('cp1251'); offset = end+1
    size, = struct.unpack_from('<I',data,offset); offset += 4
    assert size % 3 == 0
    batch = []
    for i in range(size):
        vertex = struct.unpack_from('<3f3fI2f',data,offset+i*36)
        assert all(math.isfinite(v) for v in (*vertex[:6],*vertex[7:]))
        assert abs(dot(vertex[3:6],vertex[3:6])-1) < .002
        batch.append(vertex[:3])
    all_triangles.extend(tuple(batch[i:i+3]) for i in range(0,size,3))
    if texture in {f['texture'].replace('/','\\') for f in manifest['concrete_shell']}:
        for i in range(0,size,3):
            vertex = struct.unpack_from('<3f3fI2f',data,offset+i*36)
            geometric = cross(sub(batch[i+1],batch[i]),sub(batch[i+2],batch[i]))
            assert dot(geometric,vertex[3:6]) > 0, ('shell face points away from room',texture)
    triangles += size//3; offset += size*36
assert offset == len(data) and triangles < 10000
shell = manifest['concrete_shell']
assert len(shell) == 5 and all('beton' in f['texture'] for f in shell)
for face in shell:
    assert all(abs(dot(sub(p,face['corners'][0]),face['normal'])) < 1e-6 for p in face['corners'])

for origin, target, expected in [((0,1.35,-4.6),(1.5,.92133,1.1),pda),
                       ((1.4,1.7,.1),(1.5,.92133,1.1),pda),
                       ((-1.5,1.6,.9),(-1.5,1.65,2.14),model_triangles(objects['map']))]:
    delta = sub(target,origin); distance = math.sqrt(dot(delta,delta)); direction = tuple(v/distance for v in delta)
    hits = [ray_hit(origin,direction,tri) for tri in all_triangles]
    nearest = min(d for d in hits if d is not None)
    expected_hits = [ray_hit(origin,direction,tri) for tri in expected]
    expected_distance = min(d for d in expected_hits if d is not None)
    assert abs(nearest-expected_distance) < .001, ('focus obstructed',origin,nearest,expected_distance)
print(f'Room PASS: concrete shell, {triangles} triangles/{count} materials, PDA support gap {(bottom-top)*1000:.3f} mm, map/PDA unobstructed')
