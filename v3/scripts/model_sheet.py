"""Model sheet: orthographic front / side / back, colour swatches and proportions (system Python + Pillow)."""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = (236, 233, 229)
INK = (16, 22, 41)
W, H = 3000, 1700
sheet = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(sheet)


def font(size, bold=True):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf", size)
    except Exception:
        return ImageFont.load_default()


d.text((70, 50), "Synergist Lubricants mascot - model sheet v3 (matched to the plush)", fill=INK, font=font(64))
cell = 900
for k, (name, label) in enumerate((("front", "Front"), ("side", "Side"), ("back", "Back"))):
    im = Image.open(os.path.join(ROOT, "exports", "ortho", f"ortho_{name}.png")).convert("RGBA").resize((cell, cell), Image.LANCZOS)
    x = 70 + k * (cell + 40)
    tile = Image.new("RGBA", (cell, cell), BG + (255,))
    tile.alpha_composite(im)
    sheet.paste(tile.convert("RGB"), (x, 180))
    d.text((x + cell / 2 - d.textlength(label, font=font(40)) / 2, 1090), label, fill=INK, font=font(40))
swatches = [("Barrel blue (render)", "#1135A0"), ("Arms and legs navy", "#0B0E1C"), ("Gloves and shoes", "#F2EFEA"),
            ("Brand gold", "#D5B268"), ("Light gold", "#EED295"), ("Brand navy", "#101629"),
            ("Eye white", "#F6F4EF"), ("Mouth", "#45454C")]
x0, y0 = 70, 1190
d.text((x0, y0), "Colours", fill=INK, font=font(40))
for k, (label, hx) in enumerate(swatches):
    x = x0 + (k % 4) * 470
    y = y0 + 70 + (k // 4) * 190
    col = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
    d.rounded_rectangle((x, y, x + 130, y + 130), 22, fill=col, outline=INK, width=3)
    d.text((x + 150, y + 22), label, fill=INK, font=font(32))
    d.text((x + 150, y + 68), hx, fill=(70, 76, 100), font=font(30, False))
x1 = 2010
d.text((x1, y0), "Proportions", fill=INK, font=font(40))
notes = ["Barrel height = 1.27 x barrel width",
         "Total height = 1.74 x barrel width",
         "Hoops at 42 %, 75 % and 98 % from the top",
         "Three soft ribs behind the eyes",
         "Hand = 0.3 x barrel width, 3 fingers + thumb",
         "Rig: 50 bones, rubber-hose arms and legs",
         "Face: 45 shapes, 20 ready expressions"]
for k, t in enumerate(notes):
    d.text((x1, y0 + 72 + k * 54), "-  " + t, fill=INK, font=font(32, False))
out = os.path.join(ROOT, "renders", "model_sheet_v3.png")
sheet.save(out)
print("model sheet", out)
