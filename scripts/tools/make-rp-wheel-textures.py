"""The RP wheel's textures, after New Way's radial menu (owner 2026-10-24):
a dark translucent disc with a light rim and an inner circle, a round slot
behind each icon and the gold hover ring. Drawn here (NW draws them in code).
usage: make-rp-wheel-textures.py <overlay client dir>"""
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("nw", HERE / "import-nw-anims.py")
nw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nw)


def disc(size, fill, rims, scale=4):
    """A circle with rims [(radius as a part of the half size, width px, rgba)], antialiased."""
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    half = big / 2
    if fill:
        draw.ellipse((0, 0, big - 1, big - 1), fill=fill)
    for part, width, color in rims:
        r = half * part
        draw.ellipse((half - r, half - r, half + r, half + r), outline=color, width=width * scale)
    return image.resize((size, size), Image.LANCZOS)


def main(client):
    ui = Path(client) / "textures/ui"
    nw.dds_bc3(disc(1024, (18, 21, 34, 225), [(0.995, 3, (190, 195, 210, 255)), (0.36, 3, (170, 175, 190, 255))]),
               ui / "netcoop_rp_wheel.dds")
    nw.dds_bc3(disc(128, (30, 34, 50, 235), [(0.97, 3, (150, 155, 170, 255))]), ui / "netcoop_rp_slot.dds")
    nw.dds_bc3(disc(128, None, [(0.97, 6, (235, 180, 40, 255)), (0.88, 2, (255, 215, 90, 200))]),
               ui / "netcoop_rp_slot_hover.dds")
    print("wheel textures written")


if __name__ == "__main__":
    main(sys.argv[1])
