"""Soviet propaganda poster for the 3D menu room from a photo.

    python tools/make-soviet-poster.py <photo> [--out scripts/netcoop-overlay/client/textures/netcoop/poster_folk.dds]

Aged paper, red sun rays and a star, the figure from the photo as a red and
black two-tone print, slogan «РЕВОЛЮЦИОННЫЙ ПРОЕКТ «ФОЛК ВОСЯНКА»». Writes
the DDS (DXT1, 1024x1536) the room uses and a PNG preview next to it.
build-lostzone-room.py hangs it on the back wall when the DDS exists.
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1024, 1536
PAPER = (232, 214, 176)
RED = (186, 28, 28)
DARK_RED = (120, 14, 14)
INK = (28, 18, 16)
FONTS = ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf"]


def font(size):
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_text(draw, text, max_width, start):
    size = start
    while size > 20:
        f = font(size)
        if draw.textlength(text, font=f) <= max_width:
            return f
        size -= 4
    return font(size)


def paper():
    img = Image.new("RGB", (W, H), PAPER)
    noise = Image.effect_noise((W, H), 28).convert("L")
    grain = ImageOps.colorize(noise, (196, 174, 132), (246, 232, 204))
    img = Image.blend(img, grain, 0.35)
    # Darker, worn edges.
    vignette = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vignette)
    for i in range(60):
        d.rectangle([i, i, W - 1 - i, H - 1 - i], outline=int(150 * (1 - i / 60) ** 2))
    return Image.composite(Image.new("RGB", (W, H), (150, 120, 80)), img, vignette)


def rays(img, center, count=18):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = center
    for i in range(count):
        if i % 2:
            continue
        a0 = 2 * math.pi * i / count
        a1 = 2 * math.pi * (i + 1) / count
        far = 2000
        d.polygon([(cx, cy), (cx + far * math.cos(a0), cy + far * math.sin(a0)),
                   (cx + far * math.cos(a1), cy + far * math.sin(a1))], fill=RED + (150,))
    d.ellipse([cx - 170, cy - 170, cx + 170, cy + 170], fill=RED + (235,))


def star(img, center, radius, color):
    d = ImageDraw.Draw(img)
    cx, cy = center
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.4
        a = -math.pi / 2 + i * math.pi / 5
        points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(points, fill=color)


def figure(photo, box):
    """The person as a two-tone print: dark ink shadows, red mid-tones."""
    x0, y0, x1, y1 = box
    src = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    src = ImageOps.fit(src, (x1 - x0, y1 - y0), method=Image.LANCZOS, centering=(0.5, 0.35))
    gray = ImageOps.autocontrast(ImageOps.grayscale(src), cutoff=2)
    gray = gray.filter(ImageFilter.SMOOTH_MORE)
    levels = ImageOps.posterize(gray.convert("RGB"), 2).convert("L")
    tinted = ImageOps.colorize(levels, black=INK, mid=DARK_RED, white=PAPER)
    # Highlights stay unprinted so the rays show through; the edges fade out.
    ink = gray.point(lambda v: 0 if v > 160 else 255)
    edge = Image.new("L", src.size, 0)
    ImageDraw.Draw(edge).rounded_rectangle([0, 0, src.size[0] - 1, src.size[1] - 1], radius=40, fill=255)
    edge = edge.filter(ImageFilter.GaussianBlur(18))
    mask = ImageChops.multiply(ink.filter(ImageFilter.GaussianBlur(1)), edge)
    return tinted, mask


def make(photo, out):
    img = paper()
    rays(img, (W // 2, 560))
    tinted, mask = figure(photo, (110, 250, W - 110, 1130))
    img.paste(tinted, (110, 250), mask)
    star(img, (W - 150, 160), 90, RED)
    star(img, (150, 160), 60, DARK_RED)
    d = ImageDraw.Draw(img)
    # Top slogan band.
    d.rectangle([0, 1150, W, 1536], fill=RED)
    d.rectangle([0, 1150, W, 1162], fill=INK)
    top = "РЕВОЛЮЦИОННЫЙ ПРОЕКТ"
    f = fit_text(d, top, W - 120, 110)
    d.text((W // 2, 1235), top, font=f, fill=PAPER, anchor="mm")
    name = "«ФОЛК ВОСЯНКА»"
    f = fit_text(d, name, W - 100, 170)
    d.text((W // 2 + 5, 1395 + 5), name, font=f, fill=INK, anchor="mm")
    d.text((W // 2, 1395), name, font=f, fill=(250, 226, 120), anchor="mm")
    d.text((W // 2, 80), "ЗОНА ОТЧУЖДЕНИЯ · 2026", font=font(44), fill=INK, anchor="mm")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out.with_suffix(".png"))
    img.save(out, format="DDS", pixel_format="DXT1")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("photo")
    p.add_argument("--out", default=str(Path(__file__).resolve().parents[1] /
                                         "scripts/netcoop-overlay/client/textures/netcoop/poster_folk.dds"))
    args = p.parse_args()
    print(make(args.photo, args.out))
