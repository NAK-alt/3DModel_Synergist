"""Trace the gold wordmark + flame of refs/synergist-logo.png into Bezier outlines.

Run with system Python (needs Pillow, numpy, potracer):
  python scripts/trace_logo.py
Writes refs/logo_trace.json (kept out of git with the other refs). Coordinates are in
logo pixels, origin top-left, y down. Format:
  {"size": [w, h],
   "word": [ [ {"start": [x, y], "segs": [ {"c1": [x,y], "c2": [x,y], "end": [x,y]} |
                                            {"corner": [x,y], "end": [x,y]} ... ]} ... ] ],
   "balls": [ {"cx": x, "cy": y, "r": r} x3 ],
   "badge": {"cx": x, "cy": y, "r_outer": r, "r_inner": r} }
"word" is a list of closed curves; holes are separate curves (use even-odd fill).
"""
import json
import os

import numpy as np
import potrace
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "refs", "synergist-logo.png")
OUT = os.path.join(ROOT, "refs", "logo_trace.json")
WORD_X0 = 480  # wordmark + flame start right of the badge

img = np.asarray(Image.open(SRC).convert("RGBA")).astype(np.float32) / 255.0
r, g, b, a = img[..., 0], img[..., 1], img[..., 2], img[..., 3]
mx, mn = img[..., :3].max(axis=2), img[..., :3].min(axis=2)
sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
gold = (a > 0.5) & (sat > 0.18)
h, w = gold.shape

# --- wordmark + flame -------------------------------------------------------
word_mask = gold.copy()
word_mask[:, :WORD_X0] = False
# pad by PAD px: the last 'S' touches the image edge, which otherwise merges it with a frame curve
PAD = 8
padded = np.pad(word_mask, PAD, constant_values=False)
paths = potrace.Bitmap(padded).trace(turdsize=6, alphamax=1.0, opticurve=True, opttolerance=0.2)


def p(pt):
    return [round(float(pt.x) - PAD, 2), round(float(pt.y) - PAD, 2)]


word = []
for curve in paths:
    segs = []
    for s in curve.segments:
        if s.is_corner:
            segs.append({"corner": p(s.c), "end": p(s.end_point)})
        else:
            segs.append({"c1": p(s.c1), "c2": p(s.c2), "end": p(s.end_point)})
    xs = [q[0] for s in segs for q in s.values()]
    if max(xs) - min(xs) > 0.9 * w:  # potracer also emits the bitmap frame; drop it
        continue
    word.append({"start": p(curve.start_point), "segs": segs})

# --- balls: three gold blobs left of WORD_X0 ----------------------------------
ball_mask = gold.copy()
ball_mask[:, WORD_X0:] = False
ys, xs = np.nonzero(ball_mask)
cy_all = ys.mean()
groups = {
    "top": (ys < cy_all - 10),
    "left": (ys >= cy_all - 10) & (xs < xs.mean()),
    "right": (ys >= cy_all - 10) & (xs >= xs.mean()),
}
balls = []
for key in ("top", "left", "right"):
    sel = groups[key]
    n = int(sel.sum())
    balls.append({"cx": float(xs[sel].mean()), "cy": float(ys[sel].mean()), "r": float(np.sqrt(n / np.pi))})

# --- badge ring: circle around the three balls --------------------------------
bcx = sum(bb["cx"] for bb in balls) / 3.0
bcy = sum(bb["cy"] for bb in balls) / 3.0
reach = max(np.hypot(bb["cx"] - bcx, bb["cy"] - bcy) + bb["r"] for bb in balls)
badge = {"cx": bcx, "cy": bcy, "r_inner": float(reach * 1.12), "r_outer": float(reach * 1.12 + 26)}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"size": [w, h], "word": word, "balls": balls, "badge": badge}, f)
print(f"{OUT}: {len(word)} curves, {sum(len(c['segs']) for c in word)} segments, balls={balls}, badge={badge}")
