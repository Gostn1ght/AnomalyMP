"""Copy an OGF with its userdata chunk (17, the model's ini text) replaced.
Used for the flyable Mi-2 (doc 137): the same mesh, skeleton and motions,
but a car profile instead of the AI helicopter's one.

    python tools/ogf-userdata.py in.ogf out.ogf '#include "models\\vehicles\\veh_mi2_pilot.ltx"'
"""
import struct
import sys
from pathlib import Path

USERDATA = 17


def main(source, target, text):
    data = Path(source).read_bytes()
    out, pos, replaced = bytearray(), 0, False
    while pos + 8 <= len(data):
        cid, size = struct.unpack_from("<II", data, pos)
        body = data[pos + 8:pos + 8 + size]
        if cid & 0x7fffffff == USERDATA:
            body = text.encode("cp1251") + b"\0"
            cid, replaced = USERDATA, True  # never compressed
        out += struct.pack("<II", cid, len(body)) + body
        pos += 8 + size
    assert pos == len(data), "trailing bytes"
    assert replaced, "no userdata chunk"
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_bytes(bytes(out))
    print(f"{target}: {len(out)} bytes, userdata {text!r}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
