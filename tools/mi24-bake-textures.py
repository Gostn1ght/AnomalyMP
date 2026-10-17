"""MI24 (owner's commissioned model) textures for X-Ray.

The body uses an Unreal layered material: no albedo, only masks (MA, MAH)
over tiling paint/metal/rust. A plausible albedo is baked from the masks:
two-tone camouflage (MAH.G), edge wear to bare metal (MA.G), grime in
cavities (MA.B), rust/stains (MA.R), ambient occlusion (MA.A). Details and
rotor have real albedo maps. Output: DXT DDS with full mip chains.
"""
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(r"J:\LostZone_Work\_work\mi24_src\MI24\Textures")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"J:\LostZone_Work\_work\mi24_src\out\textures\veh")
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 2048


def load(name, size=SIZE):
    im = Image.open(SRC / f"T_{name}_MIP0.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def bake_body(index):
    ma, mah = load(f"air_mi24_base_{index}_MA"), load(f"air_mi24_base_{index}_MAH")
    light = np.array([0.47, 0.43, 0.31], np.float32)   # sand
    dark = np.array([0.25, 0.29, 0.19], np.float32)    # olive
    metal = np.array([0.52, 0.52, 0.50], np.float32)
    grime = np.array([0.17, 0.15, 0.11], np.float32)
    rust = np.array([0.34, 0.22, 0.14], np.float32)
    color = lerp(np.broadcast_to(light, ma.shape[:2] + (3,)), dark, mah[..., 1])
    color = lerp(color, rust, ma[..., 0] * 0.22)
    color = lerp(color, grime, ma[..., 2] * 0.45)
    color = lerp(color, metal, np.clip(ma[..., 1] * 1.3 - 0.35, 0, 1) * 0.7)
    color *= (0.35 + 0.65 * ma[..., 3])[..., None]
    return np.clip(color, 0, 1)


def mip_chain(image):
    levels = [image]
    while min(levels[-1].size) > 4:
        w, h = levels[-1].size
        levels.append(levels[-1].resize((max(1, w // 2), max(1, h // 2)), Image.LANCZOS))
    return levels


def write_dds(path, image, fmt):
    """DXT1/DXT5 with a full mip chain: each level is compressed by Pillow
    and the payloads are joined under one header."""
    image = image.convert("RGBA")
    payloads = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, level in enumerate(mip_chain(image)):
            p = Path(tmp) / f"{i}.dds"
            level.save(p, pixel_format=fmt)
            payloads.append(p.read_bytes()[128:])
    header = bytearray(128)
    w, h = image.size
    block = 8 if fmt == "DXT1" else 16
    struct.pack_into("<4sIIIIIII", header, 0, b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000,
                     h, w, max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block, 0, len(payloads))
    struct.pack_into("<II4s", header, 76, 32, 0x4, fmt.encode())
    struct.pack_into("<I", header, 108, 0x1000 | 0x8 | 0x400000)
    path.write_bytes(bytes(header) + b"".join(payloads))
    return len(payloads)


def save(name, array_or_image, fmt="DXT1"):
    image = array_or_image if isinstance(array_or_image, Image.Image) else Image.fromarray((array_or_image * 255).astype(np.uint8))
    image.save(OUT.parent.parent / f"preview_{name}.png") if image.mode != "RGBA" else None
    mips = write_dds(OUT / f"{name}.dds", image, fmt)
    print(name, image.size, fmt, "mips", mips, (OUT / f"{name}.dds").stat().st_size)


save("veh_mi24_lz_body1", bake_body(1))
save("veh_mi24_lz_body2", bake_body(2))
details = Image.open(SRC / "T_air_mi24_details_D_MIP0.png").convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
save("veh_mi24_lz_details", details)
rotor = Image.open(SRC / "T_air_mi24_rotor_D_MIP0.png").convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
save("veh_mi24_lz_rotor", rotor, "DXT5")
# Glass: tinted, partly transparent (models\transparent uses the alpha).
glass = Image.new("RGBA", (64, 64), (52, 62, 66, 110))
save("veh_mi24_lz_glass", glass, "DXT5")
