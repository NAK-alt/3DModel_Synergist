"""Build the Telegram stickers from the raw renders (system Python + Pillow + headless Chrome).
Captions and 2D decorations are laid out in HTML so Khmer shapes correctly; Pillow adds the white
sticker outline and writes 512 px PNG + WEBP, with text and without."""
import math
import os
import random
import subprocess
import sys
import tempfile

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stickers_data import STICKERS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, os.environ.get("RAW", "exports/stickers/raw"))
OUT = os.path.join(ROOT, os.environ.get("OUT", "exports/stickers"))
FONTS = os.path.join(ROOT, "refs", "fonts").replace("\\", "/")
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
NAVY, GOLD, YELLOW = "#101629", "#D5B268", "#FFD43B"
S = 1024


def is_khmer(t):
    return any("\u1780" <= c <= "\u17ff" for c in t)


# ------------------------------------------------------------------ decorations (SVG)
def deco_svg(spec):
    kind, args = spec.split(":")
    x, y, size = (float(v) for v in args.split(","))
    r = size / 2
    st = f'stroke="{NAVY}" stroke-width="{max(5, size * 0.07):.1f}" stroke-linejoin="round" stroke-linecap="round"'
    if kind == "sparkle":
        p = " ".join(f"{x + (r if k % 2 == 0 else r * 0.3) * math.cos(math.pi / 4 * k - math.pi / 2):.1f},"
                     f"{y + (r if k % 2 == 0 else r * 0.3) * math.sin(math.pi / 4 * k - math.pi / 2):.1f}" for k in range(8))
        return f'<polygon points="{p}" fill="{YELLOW}" {st}/>'
    if kind == "heart":
        return (f'<path transform="translate({x - r},{y - r}) scale({size / 100})" fill="#FF4D6D" stroke="{NAVY}" stroke-width="7" '
                f'stroke-linejoin="round" d="M50 88 C 10 58 2 36 14 20 C 26 6 44 10 50 26 C 56 10 74 6 86 20 C 98 36 90 58 50 88 Z"/>')
    if kind == "sun":
        rays = "".join(f'<line x1="{x + r * 0.72 * math.cos(a):.1f}" y1="{y + r * 0.72 * math.sin(a):.1f}" '
                       f'x2="{x + r * math.cos(a):.1f}" y2="{y + r * math.sin(a):.1f}" stroke="{NAVY}" stroke-width="{size * 0.16:.1f}" stroke-linecap="round"/>'
                       f'<line x1="{x + r * 0.72 * math.cos(a):.1f}" y1="{y + r * 0.72 * math.sin(a):.1f}" '
                       f'x2="{x + r * math.cos(a):.1f}" y2="{y + r * math.sin(a):.1f}" stroke="#FFB020" stroke-width="{size * 0.08:.1f}" stroke-linecap="round"/>'
                       for a in [2 * math.pi * k / 10 for k in range(10)])
        return rays + f'<circle cx="{x}" cy="{y}" r="{r * 0.52:.1f}" fill="{YELLOW}" {st}/>'
    if kind == "waves":
        d = size  # direction: -1 opens to the left, 1 to the right
        out = ""
        for k, rr in enumerate((58, 92)):
            a0, a1 = (math.radians(205), math.radians(155)) if d < 0 else (math.radians(-25), math.radians(25))
            x0, y0 = x + rr * math.cos(a0), y + rr * math.sin(a0)
            x1, y1 = x + rr * math.cos(a1), y + rr * math.sin(a1)
            sweep = 0 if d < 0 else 1
            for col, w in ((NAVY, 20), ("#FFFFFF", 9)):
                out += f'<path d="M{x0:.1f} {y0:.1f} A {rr} {rr} 0 0 {sweep} {x1:.1f} {y1:.1f}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>'
        return out
    if kind == "steam":
        out = ""
        for dx in (-0.35, 0.35):
            px = x + dx * size
            d = f"M{px:.1f} {y:.1f} c -18 -22 18 -38 0 -62 c -14 -20 12 -32 2 -52"
            for col, w in ((NAVY, 18), ("#FFFFFF", 8)):
                out += f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>'
        return out
    if kind == "question":
        return (f'<text x="{x}" y="{y + size * 0.36:.1f}" font-family="FR" font-weight="700" font-size="{size}" text-anchor="middle" '
                f'fill="{YELLOW}" stroke="{NAVY}" stroke-width="{size * 0.16:.1f}" stroke-linejoin="round" paint-order="stroke">?</text>')
    if kind == "clock":
        return (f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="#FFFFFF" {st}/>'
                f'<circle cx="{x}" cy="{y}" r="{r * 0.80:.1f}" fill="none" stroke="{GOLD}" stroke-width="{size * 0.05:.1f}"/>'
                f'<path d="M{x} {y - r * 0.55:.1f} L{x} {y} L{x + r * 0.42:.1f} {y + r * 0.22:.1f}" fill="none" stroke="{NAVY}" '
                f'stroke-width="{size * 0.085:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    if kind == "coin":
        return (f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{YELLOW}" {st}/>'
                f'<text x="{x}" y="{y + size * 0.26:.1f}" font-family="FR" font-weight="700" font-size="{size * 0.72:.0f}" text-anchor="middle" fill="{NAVY}">$</text>')
    if kind == "speed":
        out = ""
        for k, (dy, ln) in enumerate(((-0.42, 0.9), (0.0, 1.25), (0.42, 0.8))):
            for col, w in ((NAVY, 22), ("#FFFFFF", 10)):
                out += (f'<line x1="{x - ln * r:.1f}" y1="{y + dy * size:.1f}" x2="{x + r:.1f}" y2="{y + dy * size:.1f}" '
                        f'stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>')
        return out
    if kind == "emptybox":
        w = size
        return (f'<g transform="translate({x - w / 2:.1f},{y - w / 2:.1f}) scale({w / 100})" stroke="{NAVY}" stroke-width="6" stroke-linejoin="round">'
                f'<path d="M12 42 L88 42 L82 92 L18 92 Z" fill="#C89A62"/><path d="M12 42 L2 22 L40 26 L50 42 Z" fill="#E7CFA0"/>'
                f'<path d="M88 42 L98 22 L60 26 L50 42 Z" fill="#E7CFA0"/>'
                f'<path d="M38 60 L62 80 M62 60 L38 80" fill="none" stroke="#D81E2C" stroke-width="8" stroke-linecap="round"/></g>')
    if kind == "moon":
        return (f'<path transform="translate({x - r:.1f},{y - r:.1f}) scale({size / 100})" fill="{YELLOW}" stroke="{NAVY}" stroke-width="7" '
                f'stroke-linejoin="round" d="M62 8 A44 44 0 1 0 92 66 A36 36 0 0 1 62 8 Z"/>'
                + deco_svg(f"sparkle:{x + r * 0.9:.0f},{y - r * 0.5:.0f},{size * 0.3:.0f}"))
    if kind == "confetti":
        rnd = random.Random(7)
        cols = ["#FF4D6D", YELLOW, "#34C3FF", "#22B455", GOLD, "#FFFFFF"]
        out = ""
        for _ in range(46):
            px, py = rnd.uniform(60, 964), rnd.uniform(40, 700)
            if 300 < px < 724 and 180 < py < 640:
                continue
            w, h, a = rnd.uniform(18, 34), rnd.uniform(10, 16), rnd.uniform(0, 180)
            out += (f'<rect x="{-w / 2:.1f}" y="{-h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="3" fill="{rnd.choice(cols)}" '
                    f'stroke="{NAVY}" stroke-width="4" transform="translate({px:.1f},{py:.1f}) rotate({a:.0f})"/>')
        return out
    if kind == "firework":
        out = ""
        cols = ["#FF4D6D", YELLOW, "#34C3FF"]
        for k in range(12):
            a = 2 * math.pi * k / 12
            x0, y0 = x + r * 0.35 * math.cos(a), y + r * 0.35 * math.sin(a)
            x1, y1 = x + r * math.cos(a), y + r * math.sin(a)
            out += f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{NAVY}" stroke-width="18" stroke-linecap="round"/>'
        for k in range(12):
            a = 2 * math.pi * k / 12
            x0, y0 = x + r * 0.35 * math.cos(a), y + r * 0.35 * math.sin(a)
            x1, y1 = x + r * math.cos(a), y + r * math.sin(a)
            out += f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{cols[k % 3]}" stroke-width="8" stroke-linecap="round"/>'
        return out
    return ""


# ------------------------------------------------------------------ page
def page(st, char_path, cw, ch, with_text):
    lines = st["text"] if with_text else []
    fill = YELLOW if st.get("yellow") else "#FFFFFF"
    rows = []
    for i, t in enumerate(lines):
        cls = "km" if is_khmer(t) else "en"
        if i > 0 and is_khmer(lines[0]) and not is_khmer(t):
            cls += " sub"
        col = fill if i == 0 else "#FFFFFF"
        rows.append(f'<div class="row"><div class="line {cls}"><span class="stroke">{t}</span>'
                    f'<span class="fill" style="color:{col}">{t}</span></div></div>')
    n = len(lines)
    khm = n and is_khmer(lines[0])
    text_h = 0 if not n else (250 if n == 1 else (350 if khm else 370))
    pad = 34
    box_h = S - 2 * pad - text_h
    box_w = S - 2 * pad
    sc = min(box_w / cw, box_h / ch)
    w, h = cw * sc, ch * sc
    cx = (S - w) / 2 + st.get("dx", 0)
    top = st.get("pos", "top") == "top"
    cy = (pad + text_h + (box_h - h)) if top else pad + st.get("dy", 0)
    ty = pad if top else S - pad - text_h
    deco = "".join(deco_svg(d) for d in st.get("deco", [])) if with_text else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: KH; src: url("file:///{FONTS}/KantumruyPro.ttf"); font-weight: 100 900; }}
@font-face {{ font-family: FR; src: url("file:///{FONTS}/Fredoka.ttf"); font-weight: 300 700; }}
html, body {{ margin: 0; background: transparent; width: {S}px; height: {S}px; overflow: hidden; }}
img.c {{ position: absolute; left: {cx:.1f}px; top: {cy:.1f}px; width: {w:.1f}px; height: {h:.1f}px; }}
svg {{ position: absolute; left: 0; top: 0; }}
.cap {{ position: absolute; left: 0; top: {ty}px; width: {S}px; height: {text_h}px; display: flex; flex-direction: column;
        justify-content: center; align-items: center; transform: rotate(-2.5deg); }}
.row {{ display: flex; justify-content: center; }}
.line {{ position: relative; white-space: nowrap; font-weight: 700; line-height: 1.02; }}
.stroke {{ color: {NAVY}; -webkit-text-stroke: 30px {NAVY}; filter: drop-shadow(0 9px 0 #060a1a); }}
.fill {{ position: absolute; left: 0; top: 0; }}
.en {{ font-family: FR, sans-serif; font-size: {190 if n == 1 else 150}px; letter-spacing: 6px; }}
.km {{ font-family: KH, sans-serif; font-size: {170 if n == 1 else 150}px; line-height: 1.38; }}
.sub {{ font-size: 96px; letter-spacing: 5px; }}
.sub .stroke {{ -webkit-text-stroke: 24px {NAVY}; }}
</style></head><body>
<svg width="{S}" height="{S}" viewBox="0 0 {S} {S}">{deco}</svg>
<img class="c" src="file:///{char_path.replace(os.sep, '/')}">
<div class="cap">{''.join(rows)}</div>
<script>
document.fonts.ready.then(() => {{
  for (const el of document.querySelectorAll('.line')) {{
    let size = parseFloat(getComputedStyle(el).fontSize);
    while (el.getBoundingClientRect().width > {S - 110} && size > 30) {{ size -= 3; el.style.fontSize = size + 'px'; }}
  }}
}});
</script></body></html>"""


def shoot(html, out_png):
    browser = next(b for b in BROWSERS if os.path.exists(b))
    with tempfile.TemporaryDirectory() as tmp:
        hp = os.path.join(tmp, "p.html")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(html)
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                        f"--user-data-dir={os.path.join(tmp, 'prof')}", "--default-background-color=00000000",
                        f"--window-size={S},{S}", "--virtual-time-budget=4000", "--force-device-scale-factor=1",
                        f"--screenshot={out_png}", "file:///" + hp.replace(os.sep, "/")],
                       check=True, capture_output=True, timeout=120)


def finish(png, out_base):
    im = Image.open(png).convert("RGBA")
    a = im.getchannel("A")
    grow = a.filter(ImageFilter.GaussianBlur(9)).point(lambda v: 255 if v > 26 else 0).filter(ImageFilter.GaussianBlur(1.6))
    shadow = grow.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.30))
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (10, 14, 30, 0))
    sh.putalpha(shadow)
    canvas.alpha_composite(sh, (0, 8))
    white = Image.new("RGBA", im.size, (255, 255, 255, 0))
    white.putalpha(grow)
    canvas.alpha_composite(white)
    canvas.alpha_composite(im)
    final = canvas.resize((512, 512), Image.LANCZOS)
    final.save(out_base + ".png", optimize=True)
    final.save(out_base + ".webp", quality=92, method=6)


def main():
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    os.makedirs(os.path.join(OUT, "notext"), exist_ok=True)
    tmp = os.path.join(ROOT, "tmp", "compose")
    os.makedirs(tmp, exist_ok=True)
    for st in STICKERS:
        if only and not any(st["slug"].startswith(o) for o in only):
            continue
        raw = Image.open(os.path.join(RAW, st["slug"] + ".png")).convert("RGBA")
        box = raw.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        char = raw.crop(box)
        cp = os.path.join(tmp, st["slug"] + "_char.png")
        char.save(cp)
        for with_text, base in ((True, os.path.join(OUT, st["slug"])), (False, os.path.join(OUT, "notext", st["slug"]))):
            shot = os.path.join(tmp, st["slug"] + ("_t.png" if with_text else "_n.png"))
            shoot(page(st, cp, char.width, char.height, with_text), shot)
            finish(shot, base)
        print("sticker", st["slug"])


if __name__ == "__main__":
    main()
