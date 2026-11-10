"""Sticker captions rendered by headless Chrome/Edge so Khmer shapes correctly.

  python scripts/sticker_text.py "សូមអបអរសាទរ|CONGRATULATIONS" out.png

Lines are separated by "|". Khmer lines use Kantumruy Pro Bold, Latin lines Fredoka Bold
(both OFL, downloaded to refs/fonts/). Style: white fill, thick navy #101629 outline,
gold #D5B268 offset shadow as the accent. Output: transparent PNG trimmed to the text.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "refs", "fonts").replace("\\", "/")
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
NAVY, GOLD = "#101629", "#D5B268"
WIDTH = 1024


def is_khmer(text):
    return any("\u1780" <= ch <= "\u17ff" for ch in text)


def build_html(lines):
    rows = []
    for text in lines:
        cls = "km" if is_khmer(text) else "en"
        # two stacked copies: outline-only underneath, fill on top. A single copy with paint-order
        # strokes glyph by glyph, so a thick outline paints over the previous letter (thin "I" vanished)
        rows.append(f'<div class="line {cls}"><span class="stroke">{text}</span><span class="fill">{text}</span></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: KH; src: url("file:///{FONT_DIR}/KantumruyPro.ttf"); font-weight: 100 900; }}
@font-face {{ font-family: FR; src: url("file:///{FONT_DIR}/Fredoka.ttf"); font-weight: 300 700; }}
html, body {{ margin: 0; background: transparent; }}
.wrap {{ width: {WIDTH}px; padding: 70px 0 40px; text-align: center; }}
.line {{ display: inline-block; position: relative; white-space: nowrap; font-weight: 700; line-height: 1.12; letter-spacing: 3px; }}
.stroke {{ color: {NAVY}; -webkit-text-stroke: 16px {NAVY}; filter: drop-shadow(0 7px 0 {GOLD}); }}
.fill {{ position: absolute; left: 0; top: 0; color: #fff; }}
.km {{ font-family: KH, sans-serif; font-size: 112px; line-height: 1.45; }}  /* Khmer stacks above/below */
.en {{ font-family: FR, sans-serif; font-size: 104px; letter-spacing: 10px; }}  /* tight pairs like IV merged */
.km + .en {{ font-size: 78px; }}
</style></head><body><div class="wrap">{"<br>".join(rows)}</div>
<script>
// shrink any line wider than the canvas
document.fonts.ready.then(() => {{
  for (const el of document.querySelectorAll('.line')) {{
    let size = parseFloat(getComputedStyle(el).fontSize);
    while (el.getBoundingClientRect().width > {WIDTH - 60} && size > 30) {{
      size -= 2; el.style.fontSize = size + 'px';
    }}
  }}
  document.body.setAttribute('data-ready', '1');
}});
</script></body></html>"""


def render_caption(caption, out_png):
    lines = [s.strip() for s in caption.split("|") if s.strip()]
    browser = next(b for b in BROWSERS if os.path.exists(b))
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "caption.html")
        with open(html, "w", encoding="utf-8") as f:
            f.write(build_html(lines))
        shot = os.path.join(tmp, "shot.png")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--allow-file-access-from-files", "--default-background-color=00000000",
                        "--virtual-time-budget=4000", f"--window-size={WIDTH},700",
                        f"--screenshot={shot}", "file:///" + html.replace("\\", "/")],
                       check=True, capture_output=True, timeout=120)
        im = Image.open(shot).convert("RGBA")
        bbox = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        im = im.crop(bbox) if bbox else im
        im.save(out_png)
    return out_png


if __name__ == "__main__":
    print(render_caption(sys.argv[1], sys.argv[2]))
