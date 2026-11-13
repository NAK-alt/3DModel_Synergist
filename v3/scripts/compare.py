"""Side by side and 50 % overlay of the plush photo and the matched render (system Python + Pillow)."""
import os
import sys

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
photo = Image.open(os.path.join(ROOT, "refs", "mascot.png")).convert("RGB")
r = Image.open(os.path.join(ROOT, "tmp", "match.png")).convert("RGBA")
bg = Image.new("RGBA", r.size, (224, 219, 216, 255))
bg.alpha_composite(r)
render = bg.convert("RGB").resize(photo.size, Image.LANCZOS)
render.save(os.path.join(ROOT, "tmp", "match_bg.png"))
side = Image.new("RGB", (photo.width * 2, photo.height))
side.paste(photo, (0, 0))
side.paste(render, (photo.width, 0))
side.save(os.path.join(ROOT, "tmp", "match_side.png"))
Image.blend(photo, render, 0.5).save(os.path.join(ROOT, "tmp", "match_blend.png"))
if len(sys.argv) > 1:  # crops: name x0 y0 x1 y1
    x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
    c = Image.new("RGB", ((x1 - x0) * 2, y1 - y0))
    c.paste(photo.crop((x0, y0, x1, y1)), (0, 0))
    c.paste(render.crop((x0, y0, x1, y1)), (x1 - x0, 0))
    c.save(os.path.join(ROOT, "tmp", f"match_{sys.argv[1]}.png"))
