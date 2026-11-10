"""Contact sheet: python scripts/make_sheet.py <prefix> [views...] -> renders/<prefix>_sheet.png (2048 px wide)."""
import os
import sys
from PIL import Image, ImageDraw

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
prefix = sys.argv[1] if len(sys.argv) > 1 else "model"
views = sys.argv[2:] or ["front", "threequarter", "side", "back", "face"]
w = 2048 // len(views)
sheet = Image.new("RGB", (w * len(views), w + 40), (40, 40, 40))
draw = ImageDraw.Draw(sheet)
for i, v in enumerate(views):
    im = Image.open(os.path.join(root, "renders", f"{prefix}_{v}.png")).convert("RGB").resize((w, w), Image.LANCZOS)
    sheet.paste(im, (i * w, 40))
    draw.text((i * w + 12, 12), v, fill=(230, 230, 230))
out = os.path.join(root, "renders", f"{prefix}_sheet.png")
sheet.save(out)
print(out, sheet.size)
