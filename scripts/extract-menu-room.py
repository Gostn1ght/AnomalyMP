"""Extract the Cordon trader bunker from an installed, unpacked game level.

Preserves the original triangles, UVs, materials and static furnishings. No
gameplay level, ALife world or connection is started by the menu renderer.
The binary uses XYZ / D3DCOLOR / UV vertices consumed by netcoop_menu_room.inc.
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
    while offset + 8 <= len(data):
        kind, size = struct.unpack_from('<II', data, offset)
        if kind & 0x80000000 or offset + 8 + size > len(data):
            raise ValueError('Unsupported compressed/corrupted level chunk')
        yield kind, memoryview(data)[offset + 8:offset + 8 + size]
        offset += 8 + size
    if offset != len(data):
        raise ValueError('Trailing level bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('level', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent /
                        'netcoop-overlay/client/meshes/netcoop/cordon_bunker.room')
    args = parser.parse_args()
    level_bytes = (args.level / 'level').read_bytes()
    geom_bytes = (args.level / 'level.geom').read_bytes()
    level, geom = dict(chunks(level_bytes)), dict(chunks(geom_bytes))
    shaders = bytes(level[2])[4:].split(b'\0')
    sizes = [4, 8, 12, 16, 4, 4, 4, 8, 4, 4, 8, 4, 8, 4, 4, 4, 8]
    source = geom[9]
    count, offset = struct.unpack_from('<I', source)[0], 4
    buffers = []
    for _ in range(count):
        declaration = {}
        stride = 0
        while True:
            stream, start, kind, method, usage, index = struct.unpack_from('<HHBBBB', source, offset)
            offset += 8
            if stream == 255:
                break
            assert stream == 0 and method == 0
            declaration[usage, index] = (start, kind)
            stride = max(stride, start + sizes[kind])
        vertices = struct.unpack_from('<I', source, offset)[0]
        offset += 4
        buffers.append((source[offset:offset + vertices * stride], stride, declaration))
        offset += vertices * stride
    assert offset == len(source)
    source = geom[10]
    count, offset = struct.unpack_from('<I', source)[0], 4
    indices = []
    for _ in range(count):
        size = struct.unpack_from('<I', source, offset)[0]
        offset += 4
        indices.append(source[offset:offset + size * 2])
        offset += size * 2
    assert offset == len(source)

    low, high = (-251.5, -24.86, -136.6), (-239.3, -20.80, -132.25)
    origin = (-245.8, -24.80, -134.4)
    batches = collections.defaultdict(bytearray)
    triangles = 0
    for _, visual in chunks(level[3]):
        sections = dict(chunks(visual))
        header = struct.unpack_from('<BBH10f', sections[1])
        if header[1] != 0 or 21 not in sections:
            continue
        if any(header[3 + k] > high[k] or header[6 + k] < low[k] for k in range(3)):
            continue
        material = shaders[header[2]].decode('cp1251')
        shader, texture = material.split('/', 1)
        # Transparent litter/glow planes and invisible sun-blocking geometry
        # need the full world renderer; omit them from this isolated room.
        if 'aref' in shader or 'trans' in shader or 'lightplanes' in shader or 'fake' in texture:
            continue
        texture = texture.split(',', 1)[0]
        vb, vbase, vcount, ib, ibase, icount = struct.unpack_from('<6I', sections[21])
        data, stride, declaration = buffers[vb]
        assert declaration[0, 0][1] == 2 and declaration[3, 0][1] == 4
        uv_offset, uv_type = declaration[5, 0]
        assert uv_type in (6, 7)
        normal_offset = declaration[3, 0][0]
        tangent_offset, binormal_offset = declaration[6, 0][0], declaration[7, 0][0]
        table = {}
        def vertex(index):
            if index in table:
                return table[index]
            assert index < vcount
            start = (vbase + index) * stride
            pos = struct.unpack_from('<3f', data, start)
            normal = tuple(data[start + normal_offset + k] / 127.5 - 1 for k in (2, 1, 0))
            u, v = struct.unpack_from('<2h', data, start + uv_offset)
            du = data[start + tangent_offset + 3] / 255.0
            dv = data[start + binormal_offset + 3] / 255.0
            uv = ((u + du) / 1024.0, (v + dv) / 1024.0)
            # Rotate the long bunker corridor into the menu camera's +Z axis.
            point = (-(pos[2] - origin[2]), pos[1] - origin[1], pos[0] - origin[0])
            nx, ny, nz = -normal[2], normal[1], normal[0]
            key = max(0.0, (-.4 * nx + .7 * ny - .7 * nz) / math.sqrt(1.14))
            hemi = data[start + normal_offset + 3] / 255.0
            lighting = .38 + .48 * key + .12 * hemi
            rgb = [min(255, round(255 * lighting * tint)) for tint in (1., .93, .80)]
            color = 0xff000000 | rgb[0] << 16 | rgb[1] << 8 | rgb[2]
            value = (pos, struct.pack('<3fI2f', *point, color, *uv))
            table[index] = value
            return value
        for offset in range(ibase * 2, (ibase + icount) * 2, 6):
            tri = [vertex(i) for i in struct.unpack_from('<3H', indices[ib], offset)]
            # Keep crossing wall/floor triangles: crop by intersection, not by
            # requiring every corner inside, which produces holes in a room.
            if any(min(p[0][k] for p in tri) > high[k] or max(p[0][k] for p in tri) < low[k] for k in range(3)):
                continue
            # Exclude very large outside terrain faces that touch the crop.
            if any(p[0][1] > high[1] + .4 for p in tri):
                continue
            batches[texture].extend(b''.join(p[1] for p in tri))
            triangles += 1
    assert triangles > 1000, 'Empty or incorrect bunker crop'
    output = bytearray(b'NCRM' + struct.pack('<II', 1, len(batches)))
    for texture, vertices in sorted(batches.items()):
        output.extend(texture.encode('cp1251') + b'\0')
        output.extend(struct.pack('<I', len(vertices) // 24))
        output.extend(vertices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    manifest = dict(source='l01_escape trader bunker', source_origin=origin,
                    source_bounds=[low, high], triangles=triangles,
                    materials={k: len(v) // 72 for k, v in sorted(batches.items())},
                    level_sha256=hashlib.sha256(level_bytes).hexdigest(),
                    geom_sha256=hashlib.sha256(geom_bytes).hexdigest())
    args.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'{args.output}: {triangles} original triangles, {len(batches)} original materials, {len(output)} bytes')


if __name__ == '__main__':
    main()
