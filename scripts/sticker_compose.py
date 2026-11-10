"""Compose Telegram static stickers from the raw character renders.

  python scripts/sticker_compose.py            # all stickers in exports/stickers/raw/
Inputs : exports/stickers/raw/<NN>_<slug>.png  (character layer, transparent, from 06_stickers.py)
         exports/stickers/captions.json        ({"NN_slug": "caption with | line breaks"})
Outputs: exports/stickers/<NN>_<slug>.png/.webp          (512x512, caption)
         exports/stickers/notext/<NN>_<slug>.png/.webp   (512x512, no caption)
         copies in renders/stickers/ (for git) and renders/stickers_sheet.png (5x4 contact sheet)
Telegram static stickers: one side exactly 512 px, PNG or WEBP, < 512 KB.
"""
import json
import os
import shutil
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sticker_text import render_caption  # noqa: E402

RAW = os.path.join(ROOT, "exports", "stickers", "raw")
OUT = os.path.join(ROOT, "exports", "stickers")
CAP_DIR = os.path.join(OUT, "captions")
SIZE = 512
OUTLINE = 8        # white sticker border (px at 512)
MARGIN = 12        # keep outline + shadow inside the canvas


def trim(im):
    bbox = im.getchannel("A").point(lambda a: 255 if a > 6 else 0).getbbox()
    return im.crop(bbox) if bbox else im


def fit(im, max_w, max_h):
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def sticker_finish(layer):
    """White outline around everything + soft drop shadow, on a 512 canvas."""
    alpha = layer.getchannel("A")
    solid = alpha.point(lambda a: 255 if a > 40 else 0)
    grown = solid.filter(ImageFilter.MaxFilter(2 * OUTLINE + 1)).filter(ImageFilter.GaussianBlur(1.2))
    white = Image.new("RGBA", layer.size, (255, 255, 255, 0))
    white.putalpha(grown)
    shadow_a = grown.filter(ImageFilter.GaussianBlur(6)).point(lambda a: int(a * 0.35))
    shadow = Image.new("RGBA", layer.size, (16, 22, 41, 0))
    shadow.putalpha(ImageChops.offset(shadow_a, 0, 5))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(white)
    out.alpha_composite(layer)
    return out


def compose(char_png, caption_png=None):
    char = trim(Image.open(char_png).convert("RGBA"))
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    inner = SIZE - 2 * (MARGIN + OUTLINE)
    if caption_png is None:
        c = fit(char, inner, inner)
        canvas.alpha_composite(c, ((SIZE - c.width) // 2, (SIZE - c.height) // 2))
        return sticker_finish(canvas)
    cap = trim(Image.open(caption_png).convert("RGBA"))
    cap = fit(cap, inner, inner * 0.30)
    overlap = int(cap.height * 0.25)                     # caption overlaps the feet a little
    c = fit(char, inner, inner - cap.height + overlap)
    top = MARGIN + OUTLINE + (inner - (c.height + cap.height - overlap)) // 2
    canvas.alpha_composite(c, ((SIZE - c.width) // 2, top))
    canvas.alpha_composite(cap, ((SIZE - cap.width) // 2, top + c.height - overlap))
    return sticker_finish(canvas)


def save_pair(im, base):
    im.save(base + ".png", optimize=True)
    im.save(base + ".webp", "WEBP", quality=92, method=6)
    for ext in (".png", ".webp"):
        kb = os.path.getsize(base + ext) / 1024
        if kb > 500:
            print(f"WARNING {base}{ext} is {kb:.0f} KB (Telegram limit 512 KB)")


def contact_sheet(paths, out_path, cols=5, cell=300, label_h=34):
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (226, 228, 232))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGBA").resize((cell, cell), Image.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
        sheet.paste(im, (x, y + label_h), im)
        name = os.path.splitext(os.path.basename(p))[0].replace("_", " ")
        draw.text((x + 10, y + 8), name, fill=(16, 22, 41), font=font)
    sheet.save(out_path)


def main():
    captions = json.load(open(os.path.join(OUT, "captions.json"), encoding="utf-8"))
    os.makedirs(CAP_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT, "notext"), exist_ok=True)
    git_dir = os.path.join(ROOT, "renders", "stickers")
    os.makedirs(os.path.join(git_dir, "notext"), exist_ok=True)
    done = []
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".png"):
            continue
        key = fn[:-4]
        cap_png = os.path.join(CAP_DIR, key + ".png")
        render_caption(captions[key], cap_png)
        base = os.path.join(OUT, key)
        save_pair(compose(os.path.join(RAW, fn), cap_png), base)
        save_pair(compose(os.path.join(RAW, fn)), os.path.join(OUT, "notext", key))
        for ext in (".png", ".webp"):
            shutil.copy2(base + ext, os.path.join(git_dir, key + ext))
            shutil.copy2(os.path.join(OUT, "notext", key + ext), os.path.join(git_dir, "notext", key + ext))
        done.append(base + ".png")
        print("sticker", key)
    contact_sheet(done, os.path.join(ROOT, "renders", "stickers_sheet.png"))
    print("sheet renders/stickers_sheet.png", len(done))


if __name__ == "__main__":
    main()
