"""Bones of a skeletal OGF: parent, model-space bind position, shape and joint type,
mass, and the bounding box. Used to place vehicle seats (doc 137).

    python tools/ogf-bones.py model.ogf
"""
import math
import struct
import sys
from pathlib import Path

SHAPE = {0: "none", 1: "box", 2: "sphere", 3: "cylinder"}
JOINT = {0: "rigid", 1: "cloth", 2: "joint", 3: "wheel", 4: "none", 5: "slider", 6: "ball"}


def chunks(data):
    pos, out = 0, {}
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from("<II", data, pos)
        out[cid & 0x7fffffff] = data[pos + 8:pos + 8 + size]
        pos += 8 + size
    return out


def xyzi(x, y, z):
    """Fmatrix::setXYZi: rotation by -x, -y, -z (X-Ray order), as rows."""
    def rx(a): c, s = math.cos(a), math.sin(a); return [[1, 0, 0], [0, c, s], [0, -s, c]]
    def ry(a): c, s = math.cos(a), math.sin(a); return [[c, 0, -s], [0, 1, 0], [s, 0, c]]
    def rz(a): c, s = math.cos(a), math.sin(a); return [[c, s, 0], [-s, c, 0], [0, 0, 1]]
    def mul(a, b): return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(rx(-x), ry(-y)), rz(-z))


def main(path):
    c = chunks(Path(path).read_bytes())
    header = c[1]
    bbox = struct.unpack_from("<6f", header, 4)  # u8 format, u8 type, u16 shader, Fbox, Fsphere
    print("bbox min (%.2f %.2f %.2f) max (%.2f %.2f %.2f)" % bbox)
    body = c[13]
    count, = struct.unpack_from("<I", body, 0)
    pos, bones = 4, []
    for _ in range(count):
        z = body.index(b"\0", pos); name = body[pos:z].decode(); pos = z + 1
        z = body.index(b"\0", pos); parent = body[pos:z].decode(); pos = z + 1
        pos += 60
        bones.append({"name": name, "parent": parent})
    ik = c[16]; p = 0
    for b in bones:
        version, = struct.unpack_from("<I", ik, p); p += 4
        z = ik.index(b"\0", p); b["material"] = ik[p:z].decode(); p = z + 1
        shape_type, flags = struct.unpack_from("<HH", ik, p); p += 112
        joint_type, = struct.unpack_from("<I", ik, p); p += 4 + 48 + 4 * 5 + (4 if version > 0 else 0)
        rot = struct.unpack_from("<3f", ik, p); p += 12
        off = struct.unpack_from("<3f", ik, p); p += 12
        b["mass"], = struct.unpack_from("<f", ik, p); p += 4 + 12
        b.update(shape=SHAPE.get(shape_type, shape_type), joint=JOINT.get(joint_type, joint_type), rot=rot, off=off)
    assert p == len(ik), (p, len(ik))
    index = {b["name"]: b for b in bones}

    def world(b):
        if "world" in b: return b["world"]
        r = xyzi(*b["rot"]); t = list(b["off"])
        if b["parent"]:
            pr, pt = world(index[b["parent"]])
            rr = [[sum(r[i][k] * pr[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            tt = [pt[j] + sum(t[k] * pr[k][j] for k in range(3)) for j in range(3)]
            b["world"] = (rr, tt)
        else:
            b["world"] = (r, t)
        return b["world"]
    for b in bones:
        _, t = world(b)
        print(f"{b['name']:20s} parent={b['parent']:16s} pos=({t[0]:6.2f},{t[1]:6.2f},{t[2]:6.2f}) "
              f"shape={b['shape']:8s} joint={b['joint']:6s} mass={b['mass']:.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
