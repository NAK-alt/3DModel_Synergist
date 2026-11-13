"""Labelled contact sheet: sheet.py <out.png> <cols> <cell px> <bg hex> <label:path> ...  (system Python + Pillow)"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

out, cols, cell, bg = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4].lstrip("#")
items = [a.split("::", 1) for a in sys.argv[5:]]
col = tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4))
rows = (len(items) + cols - 1) // cols
pad, lab = 16, 44
W, Hh = cols * (cell + pad) + pad, rows * (cell + lab + pad) + pad
sheet = Image.new("RGB", (W, Hh), col)
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 26)
except Exception:
    font = ImageFont.load_default()
dark = sum(col) < 380
for k, (label, path) in enumerate(items):
    x = pad + (k % cols) * (cell + pad)
    y = pad + (k // cols) * (cell + lab + pad)
    im = Image.open(path).convert("RGBA")
    im.thumbnail((cell, cell), Image.LANCZOS)
    tile = Image.new("RGBA", (cell, cell), col + (255,))
    tile.alpha_composite(im, ((cell - im.width) // 2, (cell - im.height) // 2))
    sheet.paste(tile.convert("RGB"), (x, y))
    tw = draw.textlength(label, font=font)
    draw.text((x + (cell - tw) / 2, y + cell + 6), label, fill=(240, 240, 240) if dark else (30, 34, 50), font=font)
os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
sheet.save(out)
print("sheet", out, sheet.size)
