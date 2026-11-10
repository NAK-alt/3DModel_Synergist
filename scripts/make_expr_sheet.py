"""Expression sheet: python scripts/make_expr_sheet.py -> renders/expressions_sheet.png (5x4, labelled).
Order follows the PRESETS dict in 04_face.py (parsed from the file, no Blender needed)."""
import os
import re

from PIL import Image, ImageDraw, ImageFont

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(root, "scripts", "04_face.py"), encoding="utf-8").read()
block = src[src.index("PRESETS.update({"):src.index("})", src.index("PRESETS.update({"))]
names = re.findall(r'^\s+"([^"]+)": dict\(', block, flags=re.M)
cols, cell, label = 5, 400, 44
rows = (len(names) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cell, rows * (cell + label)), (232, 227, 224))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("arialbd.ttf", 26)
except OSError:
    font = ImageFont.load_default()
for i, name in enumerate(names):
    im = Image.open(os.path.join(root, "renders", f"expr_{name.replace(' ', '_')}.png")).convert("RGB")
    x, y = (i % cols) * cell, (i // cols) * (cell + label)
    sheet.paste(im.resize((cell, cell), Image.LANCZOS), (x, y + label))
    tw = draw.textlength(name, font=font)
    draw.text((x + (cell - tw) / 2, y + 8), name, fill=(16, 22, 41), font=font)
out = os.path.join(root, "renders", "expressions_sheet.png")
sheet.save(out)
print(out, sheet.size, len(names), "expressions")
