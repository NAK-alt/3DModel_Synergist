"""Render the sticker poses (transparent): exports/stickers/raw/<slug>.png"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m_build
import m_pose
import m_props
import m_scene
from m_util import ROOT
from stickers_data import STICKERS

res = int(os.environ.get("RES", "1100"))
only = [s for s in os.environ.get("ONLY", "").split(",") if s]
out = os.path.join(ROOT, os.environ.get("OUT", "exports/stickers/raw"))
os.makedirs(out, exist_ok=True)
objs = m_build.build(shape_keys=False)
m_scene.setup_render(res=res, samples=int(os.environ.get("SAMPLES", "128")))
m_scene.lights()
for st in STICKERS:
    if only and not any(st["slug"].startswith(o) for o in only):
        continue
    m_props.clear()
    m_pose.apply_pose(objs["rig"], st["pose"])
    m_build.set_face(objs["face"], st["expr"])
    D = m_pose.compute(st["pose"])["body"]
    for kind, loc, rot, scale in st.get("props", []):
        m_props.add(kind, loc, rot, scale, body_D=D)
    cam = st.get("cam", {})
    m_scene.camera(target=(0, -0.1, 0.86), dist=6.4, elev=cam.get("elev", 7), azim=cam.get("azim", 0))
    m_scene.render(os.path.join(out, st["slug"] + ".png"))
