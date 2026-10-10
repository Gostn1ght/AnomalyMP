"""Merge animations into GAMMA's stalker_animation.omf.

Owner 2026-10-10 (doc 90 §4): xAGNA - xrMPE player animations adapted for
Anomaly-GAMMA (author Chemzs, animator Nazerttop / xrMPE team, Creative
Commons) - for players and NPCs alike. Every motion xAGNA has replaces
GAMMA's motion of that name (data and parameters); the motions only GAMMA
has (devices, binoculars, eating, extras) stay, so nothing GAMMA uses is lost.

usage: merge-player-anims.py <gamma.omf> <source.omf> <out.omf>
"""
import re
import struct
import sys

OGF_S_MOTIONS, OGF_S_SMPARAMS = 0x0E, 0x0F


def chunks(data, off=0, end=None):
    end = len(data) if end is None else end
    out = []
    while off + 8 <= end:
        cid, size = struct.unpack_from("<II", data, off)
        out.append((cid, off + 8, size))
        off += 8 + size
    return out


def chunk(cid, payload):
    return struct.pack("<II", cid, len(payload)) + payload


class Reader:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def f32(self):
        v = struct.unpack_from("<f", self.d, self.p)[0]; self.p += 4; return v

    def strz(self):
        z = self.d.index(b"\0", self.p)
        s = self.d[self.p:z].decode("latin1"); self.p = z + 1; return s

    def line(self):  # IReader::r_string / advance_term_string: at least one char, then all CR/LF after it
        start = self.p
        self.p += 1
        while self.p < len(self.d) and self.d[self.p] not in (10, 13):
            self.p += 1
        end = self.p
        while self.p < len(self.d) and self.d[self.p] in (10, 13):
            self.p += 1
        return self.d[start:end]


def parse(path):
    data = open(path, "rb").read()
    top = chunks(data)
    params = motions = None
    for cid, start, size in top:
        if cid & 0x80000000:
            raise SystemExit(f"{path}: compressed chunk {cid & 0x7fffffff}")
        if cid == OGF_S_SMPARAMS:
            params = (start, size)
        elif cid == OGF_S_MOTIONS:
            motions = (start, size)
    r = Reader(data, params[0])
    version = r.u16()
    parts = []
    for _ in range(r.u16()):
        name = r.strz()
        bones = [(r.strz(), r.u32()) for _ in range(r.u16())]
        parts.append((name, bones))
    defs = []
    for _ in range(r.u16()):
        begin = r.p
        name = r.strz()
        flags = r.u32()
        part, motion = r.u16(), r.u16()
        r.p += 16  # speed, power, accrue, falloff
        if version >= 4:
            for _ in range(r.u32()):
                r.line()
                intervals = r.u32()  # (not "r.p += 8 * r.u32()": that adds to the old r.p)
                r.p += 8 * intervals
        defs.append({"name": name, "flags": flags, "part": part, "motion": motion, "raw": data[begin:r.p]})
    assert r.p == params[0] + params[1], "SMPARAMS not fully read"
    subs = chunks(data, motions[0], motions[0] + motions[1])
    count = struct.unpack_from("<I", data, subs[0][1])[0]
    blobs = {}
    for cid, start, size in subs[1:]:
        z = data.index(b"\0", start)
        blobs[cid - 1] = (data[start:z].decode("latin1"), data[z + 1:start + size])
    assert len(blobs) == count
    return {"data": data, "top": top, "version": version, "parts": parts, "defs": defs, "count": count, "blobs": blobs}


def main(gamma_path, source_path, out_path):
    g, s = parse(gamma_path), parse(source_path)
    # the same skeleton: the same bones in each partition with the same motion
    # bone index (the motion data is stored in that order); listing order may differ
    for (gn, gb), (sn, sb) in zip(g["parts"], s["parts"]):
        assert gn == sn and dict(gb) == dict(sb), f"partition {gn} differs"
    by_name = {d["name"]: d for d in s["defs"]}
    data = g["data"]
    defs, blobs = [], dict(g["blobs"])
    replaced = 0
    for d in g["defs"]:
        src = by_name.get(d["name"])
        if src is None:
            defs.append(d["raw"])                      # GAMMA's own (devices, extras): kept
            continue
        # xAGNA's motion and its parameters (speed, blend, footstep marks),
        # at GAMMA's motion index
        rest = src["raw"][len(src["name"]) + 1:]
        rest = rest[:6] + struct.pack("<H", d["motion"]) + rest[8:]
        defs.append(d["name"].encode("latin1") + b"\0" + rest)
        blobs[d["motion"]] = (d["name"], s["blobs"][src["motion"]][1])
        replaced += 1
    out = b""
    for cid, start, size in g["top"]:
        if cid == OGF_S_SMPARAMS:
            r = Reader(data, start)
            r.u16()
            for _ in range(r.u16()):
                r.strz()
                for _ in range(r.u16()):
                    r.strz(); r.u32()
            body = data[start:r.p] + struct.pack("<H", len(defs)) + b"".join(defs)
            out += chunk(OGF_S_SMPARAMS, body)
        elif cid == OGF_S_MOTIONS:
            subs = [chunk(0, struct.pack("<I", g["count"]))]
            for i in range(g["count"]):
                name, blob = blobs[i]
                subs.append(chunk(i + 1, name.encode("latin1") + b"\0" + blob))
            out += chunk(OGF_S_MOTIONS, b"".join(subs))
        else:
            out += chunk(cid, data[start:start + size])
    open(out_path, "wb").write(out)
    print(f"{replaced} of {len(g['defs'])} motions from {source_path}; the rest GAMMA's -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
