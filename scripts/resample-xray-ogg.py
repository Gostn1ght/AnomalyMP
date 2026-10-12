"""48 kHz Vorbis overlay, preserving every original (including binary X-Ray) tag.

uv run --with soundfile --with scipy python scripts/resample-xray-ogg.py
No reference game file is modified.
"""
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def pages(data):
    position = 0
    while position < len(data):
        assert data[position:position + 4] == b"OggS"
        assert data[position + 4] == 0
        count = data[position + 26]
        segments = data[position + 27:position + 27 + count]
        end = position + 27 + count + sum(segments)
        assert end <= len(data)
        yield data[position:end]
        position = end


def packets(data):
    packet = bytearray()
    for page in pages(data):
        count = page[26]
        position = 27 + count
        for size in page[27:position]:
            packet.extend(page[position:position + size])
            position += size
            if size < 255:
                yield bytes(packet)
                packet.clear()
    assert not packet


def crc(data):
    value = 0
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
    return value


def replace_comments(encoded, comment):
    result = bytearray()
    replaced = 0
    for page in pages(encoded):
        count = page[26]
        lacing = page[27:27 + count]
        payload = page[27 + count:]
        if payload.startswith(b"\x03vorbis"):
            # libsndfile emits the complete comments at the start of a header
            # page, followed by the setup packet. Keep setup, granule, flags,
            # serial and sequence; change lacing and checksum only.
            assert not page[5] & 1, "continued comments unsupported"
            stop = next(i + 1 for i, n in enumerate(lacing) if n < 255)
            old_length = sum(lacing[:stop])
            segments = bytes([255] * (len(comment) // 255) + [len(comment) % 255]) + lacing[stop:]
            assert len(segments) <= 255, "comment header exceeds single page"
            header = bytearray(page[:27])
            header[26] = len(segments)
            header[22:26] = bytes(4)
            updated = header + segments + comment + payload[old_length:]
            updated[22:26] = struct.pack("<I", crc(updated))
            page = updated
            replaced += 1
        result.extend(page)
    assert replaced == 1
    return bytes(result)


def main():
    import io
    import soundfile as sf
    from scipy.signal import resample_poly
    source = ROOT.parent / "gamma-runtime/gamedata/sounds/anomaly/teleport_work_2.ogg"
    original = source.read_bytes()
    comment = next(p for p in packets(original) if p.startswith(b"\x03vorbis"))
    samples, rate = sf.read(io.BytesIO(original), always_2d=True)
    assert rate == 96000, rate
    output = io.BytesIO()
    sf.write(output, resample_poly(samples, 1, 2, axis=0), 48000, format="OGG", subtype="VORBIS")
    encoded = replace_comments(output.getvalue(), comment)
    assert next(p for p in packets(encoded) if p.startswith(b"\x03vorbis")) == comment
    info = sf.info(io.BytesIO(encoded))
    assert info.samplerate == 48000 and info.channels == samples.shape[1]
    assert abs(info.frames * 2 - len(samples)) <= 2
    for side in ("client", "server"):
        target = ROOT / "scripts/netcoop-overlay" / side / "gamedata/sounds/anomaly/teleport_work_2.ogg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
    print("PASS teleport sound: 96000 -> 48000 Hz; duration/channels and exact original Vorbis comments preserved")


if __name__ == "__main__":
    main()
