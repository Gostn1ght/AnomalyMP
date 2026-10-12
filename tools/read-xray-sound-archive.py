"""Read retained plaintext X-Ray DB metadata without launching the engine.

Port of src/xrCore/LzHuf.cpp's decoder; file payloads use LZO, not LzHuf.
Usage: python tools/read-xray-sound-archive.py archive.db0 [destination]
Only nature/wind Ogg files are selected. Existing destinations are refused.
"""
from pathlib import Path
import re
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]


def decompress_lzhuf(data):
    size, = struct.unpack_from("<I", data)
    if size > 8 * 1024 * 1024:
        raise ValueError("Archive table too large")
    source = (ROOT / "src/xrCore/LzHuf.cpp").read_text(encoding="latin-1")
    def table(name):
        body = re.search(r"u8 " + name + r"\[256\]\s*=\s*\{(.*?)\};", source, re.S).group(1)
        values = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", body)]
        assert len(values) == 256
        return values
    codes, lengths = table("d_code"), table("d_len")
    nchar, total, root = 314, 627, 626
    freq = [1] * nchar + [0] * (total + 1 - nchar)
    son = list(range(total, total + nchar)) + [0] * (total - nchar)
    parent = [0] * (total + nchar)
    for i in range(nchar):
        parent[total + i] = i
    for j in range(nchar, total):
        i = 2 * (j - nchar)
        freq[j] = freq[i] + freq[i + 1]
        son[j] = i
        parent[i] = parent[i + 1] = j
    freq[total] = 0xffff
    pos = 32
    def bit():
        nonlocal pos
        # The original pads its final lookahead with zero bits.
        value = (data[pos // 8] >> (7 - pos % 8)) & 1 if pos < len(data) * 8 else 0
        pos += 1
        if pos > len(data) * 8 + 16:
            raise ValueError("Truncated LzHuf table")
        return value
    def update(c):
        if freq[root] == 0x4000:
            leaves = [((freq[i] + 1) // 2, son[i]) for i in range(total) if son[i] >= total]
            for i, (f, s) in enumerate(leaves):
                freq[i], son[i] = f, s
            for j in range(nchar, total):
                i = 2 * (j - nchar)
                f = freq[i] + freq[i + 1]
                k = j
                while k > 0 and f < freq[k - 1]:
                    k -= 1
                freq[k + 1:j + 1] = freq[k:j]
                son[k + 1:j + 1] = son[k:j]
                freq[k], son[k] = f, i
            for i, s in enumerate(son):
                parent[s] = i
                if s < total:
                    parent[s + 1] = i
        c = parent[c + total]
        while True:
            freq[c] += 1
            k, l = freq[c], c + 1
            if k > freq[l]:
                while k > freq[l + 1]:
                    l += 1
                freq[c], freq[l] = freq[l], k
                i, j = son[c], son[l]
                parent[i] = l
                if i < total:
                    parent[i + 1] = l
                parent[j] = c
                if j < total:
                    parent[j + 1] = c
                son[l], son[c], c = i, j, l
            c = parent[c]
            if c == 0:
                break
    ring, r, output = bytearray(b" " * 4036 + bytes(60)), 4036, bytearray()
    while len(output) < size:
        c = son[root]
        while c < total:
            c = son[c + bit()]
        c -= total
        update(c)
        if c < 256:
            output.append(c); ring[r] = c; r = (r + 1) & 4095
        else:
            i = 0
            for _ in range(8):
                i = (i << 1) + bit()
            upper, length = codes[i] << 6, lengths[i] - 2
            for _ in range(length):
                i = (i << 1) + bit()
            start = (r - (upper | (i & 63)) - 1) & 4095
            for j in range(c - 253):
                value = ring[(start + j) & 4095]
                output.append(value); ring[r] = value; r = (r + 1) & 4095
    if len(output) != size:
        raise ValueError("Invalid decoded table length")
    return bytes(output)


def entries(archive):
    with Path(archive).open("rb") as stream:
        while header := stream.read(8):
            kind, size = struct.unpack("<II", header)
            if kind & 0x7fffffff != 1:
                stream.seek(size, 1)
                continue
            table = stream.read(size)
            if kind & 0x80000000:
                table = decompress_lzhuf(table)
            pos = 0
            while pos < len(table):
                length, = struct.unpack_from("<H", table, pos); pos += 2
                if length < 16 or pos + length > len(table):
                    raise ValueError("Malformed archive entry")
                real, packed, crc = struct.unpack_from("<III", table, pos)
                name = table[pos + 12:pos + length - 4].decode("cp1251")
                offset, = struct.unpack_from("<I", table, pos + length - 4)
                yield name, offset, real, packed, crc
                pos += length
            return
    raise ValueError("Archive table absent")


def main():
    archive = Path(sys.argv[1])
    destination = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    for name, offset, real, packed, crc in entries(archive):
        if not re.search(r"(?:^|\\)nature\\wind[^\\]*\.ogg$", name, re.I):
            continue
        print(name, real, packed)
        if destination is None:
            continue
        with archive.open("rb") as stream:
            stream.seek(offset); data = stream.read(packed)
        if packed != real:
            import lzokay
            data = lzokay.decompress(data, real)
        if len(data) != real or zlib.crc32(data) != crc or not data.startswith(b"OggS"):
            raise ValueError("Invalid sound payload/checksum")
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name.split("\\")[-1]
        with target.open("xb") as stream:
            stream.write(data)


if __name__ == "__main__":
    main()
