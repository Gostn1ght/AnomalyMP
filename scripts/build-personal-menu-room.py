"""Assemble a private hideout from installed STALKER decor meshes.

Preserves original geometry, UVs and textures. Rigid meshes are baked in their
bind pose, so the menu needs neither physics nor a running level. No generated
furniture or background illustration is used. The manifest records provenance.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import struct


def chunks(data):
    offset = 0
    while offset < len(data):
        kind, size = struct.unpack_from('<II', data, offset)
        assert not kind & 0x80000000 and offset + 8 + size <= len(data)
        yield kind, data[offset + 8:offset + 8 + size]
        offset += size + 8
    assert offset == len(data)


def rotate(v, angles):
    # Rotate around X (pitch), then Y (heading); room assets have no bank.
    h, p, _ = angles
    x, y, z = v
    y, z = y * math.cos(p) - z * math.sin(p), y * math.sin(p) + z * math.cos(p)
    return (x * math.cos(h) + z * math.sin(h), y, -x * math.sin(h) + z * math.cos(h))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('meshes', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent /
                        'netcoop-overlay/client/meshes/netcoop/personal_room.room')
    args = parser.parse_args()
    objects = []
    def add(name, model, pos, angles=(0, 0, 0), scale=(1, 1, 1)):
        objects.append(dict(name=name, model=model, position=pos, angles=angles, scale=scale))

    # Clear 5.5 x 6 m floor, 3 m ceiling. The front stays open to the menu camera.
    add('back wall', 'wall', (0, 0, 2.65), scale=(1.18, 1.16, 1))
    for side in (-1, 1):
        for z in (-1.15, 1.18):
            add('side wall', 'wall02', (side * 2.95, 0, z),
                (side * math.pi / 2, 0, 0), (1, 1.16, 1))
    for x in (-1.4, 1.4):
        for z in (-2.0, 0, 2.0):
            add('floor', 'wooden_board', (x, -.071, z), scale=(1.12, 1, 1))
            add('ceiling', 'wooden_board', (x, 3.0, z), scale=(1.12, 1, 1))
    add('map', 'map1', (-1.5, 1.65, 2.14), (0, -math.pi / 2, 0), (.68, .68, .68))
    add('table', 'metal_table1', (1.65, 0, 1.45), scale=(.9, 1, .9))
    add('PDA', '../../netcoop/dev_pda', (1.50, .916, 1.10), (0, 0, 0), (1.8, 1.8, 1.8))
    add('radio', 'radiola', (2.07, .90, 1.68), (math.pi, 0, 0), (.40, .40, .40))
    add('chest', 'Storage01', (-1.65, .01, .3), (0, 0, 0), (1.1, 1.1, 1.1))
    add('seat', 'stool', (.75, 0, 1.15))
    add('ceiling lamp', 'light/lightbulb_1', (-1.4, 2.717, -1.6), scale=(.4, .4, .4))
    add('rug', 'rug', (0, -.015, .20), scale=(.7, .7, .7))

    batches = collections.defaultdict(bytearray)
    provenance = {}
    for obj in objects:
        path = args.meshes / 'dynamics/Decor' / (obj['model'] + '.ogf')
        data = path.read_bytes()
        provenance[obj['model']] = hashlib.sha256(data).hexdigest()
        root = dict(chunks(data))
        assert struct.unpack_from('<BBH', root[1])[1] == 10, path
        # Rigid mesh render transforms are bind * inverse(bind) = identity.
        for _, child in chunks(root[9]):
            parts = dict(chunks(child))
            texture, material = [x.decode('cp1251') for x in parts[2].split(b'\0')[:2]]
            if 'lightplanes' in material:
                continue  # Old billboard glow needs world fog/blending, not room geometry.
            emissive = 'selflight' in material or (obj['name'] == 'ceiling lamp' and 'lampa_g' in texture)
            vertices = parts[3]
            kind, count = struct.unpack_from('<II', vertices)
            assert kind in (1, 0x12071980) and len(vertices) == 8 + count * 60, path
            indices = parts[4]
            index_count, = struct.unpack_from('<I', indices)
            assert len(indices) == 4 + index_count * 2 and index_count % 3 == 0
            values = []
            for i in range(count):
                v = struct.unpack_from('<14fI', vertices, 8 + 60 * i)
                point = rotate(tuple(v[k] * obj['scale'][k] for k in range(3)), obj['angles'])
                point = tuple(point[k] + obj['position'][k] for k in range(3))
                normal = rotate(v[3:6], obj['angles'])
                # Alpha marks luminous lamp glass. The room shader computes lighting.
                color = 0xffffff | (0xff000000 if emissive else 0)
                assert all(math.isfinite(x) for x in (*point, *v[12:14]))
                values.append(struct.pack('<3f3fI2f', *point, *normal, color, *v[12:14]))
            for index in struct.unpack_from('<' + str(index_count) + 'H', indices, 4):
                assert index < count
                batches[texture].extend(values[index])
    output = bytearray(b'NCRM' + struct.pack('<II', 2, len(batches)))
    for texture, vertices in sorted(batches.items()):
        output.extend(texture.encode('cp1251') + b'\0')
        output.extend(struct.pack('<I', len(vertices) // 36))
        output.extend(vertices)
    args.output.write_bytes(output)
    args.output.with_suffix('.json').write_text(json.dumps(dict(objects=objects,
        source_sha256=provenance, triangles=sum(len(v)//108 for v in batches.values()),
        materials=list(sorted(batches))), indent=2) + '\n')
    print(f'{len(objects)} original objects, {len(batches)} materials, {len(output)} bytes')


if __name__ == '__main__':
    main()
