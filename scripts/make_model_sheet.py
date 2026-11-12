"""Final model sheet: python scripts/make_model_sheet.py -> renders/model_sheet_final.png

Front / side / back orthographic renders (exports/ortho/, from 08_finals.py --what ortho) on one
sheet, with height/width proportion guides and the key colour swatches.
Ortho camera: ortho_scale 2.6 m across 1200 px, centred at z = 1.15 m.
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORTHO = os.path.join(ROOT, "exports", "ortho")
OUT = os.path.join(ROOT, "renders", "model_sheet_final.png")

# model facts (02_model.py)
BODY_R, BODY_H = 0.5, 1.26
SHOE_H, LEG_LEN = 0.20, 0.17 * 1.26
BODY_BOTTOM = SHOE_H + LEG_LEN
BODY_TOP = BODY_BOTTOM + BODY_H
HOOPS = [0.29, 0.44, 0.76, 0.97]
SCALE_M, PX, CZ = 2.6, 1200, 1.15     # ortho camera

NAVY, GOLD, BG, INK = (16, 22, 41), (213, 178, 104), (236, 233, 230), (40, 46, 64)
SWATCHES = [
    ("Body fleece (target)", "#1A3AAE"), ("Body rendered (lit)", "#1E3CB0"),
    ("Navy limbs", "#101629"), ("Warm white plush", "#F2EFEA"),
    ("Gold thread", "#D5B268"), ("Light gold", "#EED295"),
    ("Mouth inside", "#4A1410"), ("Tongue", "#C0504D"), ("Studio backdrop", "#E8E3E0"),
]


def font(size, bold=True):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def z_to_px(z, top):
    return top + (PX / 2) - (z - CZ) * PX / SCALE_M


def main():
    cell = PX
    W, H = 3 * cell + 420, cell + 520
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((60, 30), "SYNERGIST MASCOT  -  MODEL SHEET", fill=NAVY, font=font(56))
    d.text((60, 100), "Plush oil-drum mascot  |  orthographic, rest pose  |  units: body diameter = 1.0",
           fill=INK, font=font(28, False))
    top = 170
    for i, name in enumerate(("front", "side", "back")):
        im = Image.open(os.path.join(ORTHO, f"ortho_{name}.png")).convert("RGBA")
        x0 = 80 + i * cell
        sheet.paste(im, (x0, top), im)
        d.text((x0 + cell // 2 - 60, top + cell - 60), name.upper(), fill=NAVY, font=font(40))
    # proportion guides on the front view
    x_left = 80 + PX / 2 - BODY_R * PX / SCALE_M
    x_right = 80 + PX / 2 + BODY_R * PX / SCALE_M
    guides = [("ground 0", 0.0), ("body bottom", BODY_BOTTOM), ("body top", BODY_TOP)]
    guides += [(f"hoop {round(p * 100)}%", BODY_TOP - p * BODY_H) for p in HOOPS]
    for label, z in guides:
        y = z_to_px(z, top)
        d.line([(60, y), (3 * cell + 120, y)], fill=(170, 170, 178), width=2)
        dy = 10 if label == "body bottom" else (-26 if label == "hoop 97%" else -14)  # these two are 1.5 cm apart
        d.text((3 * cell + 135, y + dy), label, fill=INK, font=font(24, False))
    yb, yt = z_to_px(BODY_BOTTOM, top), z_to_px(BODY_TOP, top)
    d.line([(30, yb), (30, yt)], fill=GOLD, width=6)
    d.text((44, yt - 64), "body height = 1.26 x D", fill=NAVY, font=font(26))
    ywid = z_to_px(BODY_TOP, top) - 70  # above the lid, clear of the arms and legs
    d.line([(x_left, ywid), (x_right, ywid)], fill=GOLD, width=5)
    d.text(((x_left + x_right) / 2 - 95, ywid - 36), "diameter D = 1.0", fill=NAVY, font=font(26))
    notes = ("Legs visible: 0.17 x body height   |   Shoes: 0.34 x D wide each   |   Eyes: 0.20 x 0.30 D, "
             "fill the 29-44% band   |   Logo: centred in the 44-76% band")
    d.text((60, top + cell + 10), notes, fill=INK, font=font(24, False))
    # swatches
    sy = top + cell + 70
    sw = (W - 120) // len(SWATCHES)
    for i, (label, hx) in enumerate(SWATCHES):
        x = 60 + i * sw
        rgb = tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))
        d.rounded_rectangle([x, sy, x + sw - 24, sy + 150], radius=18, fill=rgb, outline=(190, 190, 196), width=2)
        d.text((x, sy + 162), hx, fill=NAVY, font=font(26))
        d.text((x, sy + 196), label, fill=INK, font=font(20, False))
    sheet.save(OUT)
    print(OUT, sheet.size)


if __name__ == "__main__":
    main()
