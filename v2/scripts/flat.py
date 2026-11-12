"""Composite transparent renders over a flat studio colour: flat.py <bg hex> <in.png> [more.png ...]
Writes <name>_bg.png next to each input (system Python + Pillow)."""
import sys

from PIL import Image

bg = sys.argv[1].lstrip("#")
col = tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
for path in sys.argv[2:]:
    im = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", im.size, col)
    base.alpha_composite(im)
    base.convert("RGB").save(path[:-4] + "_bg.png")
