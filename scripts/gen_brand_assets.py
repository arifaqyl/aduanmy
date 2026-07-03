"""Generate icon-512.png and og-image.png matching the departure-board brand.

Run: python scripts/gen_brand_assets.py
"""
from PIL import Image, ImageDraw, ImageFont

BG = (247, 247, 247)
GREEN = (88, 204, 2)
GREEN_DARK = (70, 163, 2)
WHITE = (255, 255, 255)
INK = (60, 60, 60)
MUTED = (119, 119, 119)

FONT_DIR = "C:/Windows/Fonts/"


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def gen_icon(path="static/icon-512.png", size=512):
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    radius = int(size * 0.18)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=GREEN)

    cy = int(size * 0.5)
    r = int(size * 0.045)
    xs = [int(size * 0.28), int(size * 0.5), int(size * 0.72)]
    line_w = max(6, int(size * 0.018))
    d.line([(xs[0], cy), (xs[-1], cy)], fill=WHITE, width=line_w)
    for x in xs:
        d.ellipse([x - r, cy - r, x + r, cy + r], fill=WHITE)

    out_size = 512
    img = img.resize((out_size, out_size), Image.LANCZOS)
    img.save(path, "PNG")
    print(f"wrote {path}")


def gen_og(path="static/og-image.png", w=1200, h=630):
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # subtle top/bottom hairlines for board feel
    d.line([(0, 0), (w, 0)], fill=(40, 40, 40), width=2)
    d.line([(0, h - 1), (w, h - 1)], fill=(40, 40, 40), width=2)

    # logo mark
    mx, my = 90, 150
    box = 96
    d.rounded_rectangle([mx, my, mx + box, my + box], radius=18, fill=GREEN, outline=GREEN_DARK, width=4)
    cy = my + box // 2
    r = 7
    xs = [mx + 22, mx + box // 2, mx + box - 22]
    d.line([(xs[0], cy), (xs[-1], cy)], fill=WHITE, width=5)
    for x in xs:
        d.ellipse([x - r, cy - r, x + r, cy + r], fill=WHITE)

    title_font = font("arialbd.ttf", 68)
    tag_font = font("arialbd.ttf", 26)
    body_font = font("arial.ttf", 30)

    tx = mx + box + 40
    d.text((tx, my + 6), "TrafficMY", font=title_font, fill=INK)

    body_y = my + box + 60
    lines = [
        "Is your line delayed?",
        "See it at a glance.",
    ]
    for i, line in enumerate(lines):
        d.text((mx, body_y + i * 42), line, font=body_font, fill=MUTED)

    img.save(path, "PNG")
    print(f"wrote {path}")


if __name__ == "__main__":
    gen_icon()
    gen_og()
