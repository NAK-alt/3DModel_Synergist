"""Render every expression as a face close-up: renders/expressions/expr_<name>.png"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m_build
import m_face
import m_pose
import m_scene
from m_util import ROOT

res = int(os.environ.get("RES", "800"))
only = [s for s in os.environ.get("EXPRS", "").split(",") if s]
out = os.path.join(ROOT, os.environ.get("OUT", "renders/expressions"))
os.makedirs(out, exist_ok=True)
objs = m_build.build(shape_keys=False)
m_pose.apply_pose(objs["rig"], m_pose.HERO)
m_scene.setup_render(res=res, samples=int(os.environ.get("SAMPLES", "96")))
m_scene.lights()
m_scene.camera(target=(0, 0, 1.14), dist=2.75, elev=5)
for name in m_face.EXPRESSIONS:
    if only and name not in only:
        continue
    m_build.set_face(objs["face"], name)
    m_scene.render(os.path.join(out, "expr_" + name.replace(" ", "_") + ".png"))
