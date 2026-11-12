"""Turn the brand logo PNG into embroidery textures (run with system Python + Pillow).
textures/logo_color.png: RGBA thread colours. textures/logo_data.png: R = puff height, G = gold mask."""
import os

from PIL import Image, ImageChops, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 2048, 700

src = Image.open(os.path.join(ROOT, "refs", "logo.png")).convert("RGBA")
alpha = src.getchannel("A")
box = alpha.point(lambda a: 255 if a > 16 else 0).getbbox()
bw, bh = box[2] - box[0], box[3] - box[1]
cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
cw = max(bw * 1.05, bh * 1.10 * W / H)
ch = cw * H / W
crop = src.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.LANCZOS)
r, g, b, a = crop.split()
hsv = crop.convert("RGB").convert("HSV")
sat = hsv.getchannel("S")
gold = sat.point(lambda s: 255 if s > 60 else 0).filter(ImageFilter.GaussianBlur(1.2))
a = a.point(lambda v: min(255, int(v * 1.6)))
# white ring: flat thread white; gold parts keep the artwork's gradient, slightly deepened
white = Image.new("RGB", (W, H), (244, 241, 236))
lum = crop.convert("RGB").convert("L")
RAMP = [(0.30, (138, 92, 24)), (0.62, (205, 160, 70)), (0.80, (226, 188, 104)), (0.97, (247, 226, 150))]


def ramp(v, ch):
    x = v / 255
    if x <= RAMP[0][0]:
        return RAMP[0][1][ch]
    for (x0, c0), (x1, c1) in zip(RAMP, RAMP[1:]):
        if x <= x1:
            return int(c0[ch] + (c1[ch] - c0[ch]) * (x - x0) / (x1 - x0))
    return RAMP[-1][1][ch]


rgb = Image.merge("RGB", [lum.point(lambda v, ch=ch: ramp(v, ch)) for ch in range(3)])
rgb = Image.composite(rgb, white, gold)
out = rgb.convert("RGBA")
out.putalpha(a)
os.makedirs(os.path.join(ROOT, "textures"), exist_ok=True)
out.save(os.path.join(ROOT, "textures", "logo_color.png"))
height = a.filter(ImageFilter.GaussianBlur(5))
gmask = ImageChops.multiply(gold, a)
Image.merge("RGB", (height, gmask, Image.new("L", (W, H), 0))).save(os.path.join(ROOT, "textures", "logo_data.png"))
prev = Image.new("RGBA", (W, H), (18, 51, 168, 255))
prev.alpha_composite(out)
prev.convert("RGB").save(os.path.join(ROOT, "tmp", "logo_preview.png"))
print("logo bbox", box, "crop", cw, ch)
