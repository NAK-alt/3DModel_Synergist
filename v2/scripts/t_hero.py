"""Quick hero-pose look-dev renders (tmp/)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m_build
import m_pose
import m_scene
from m_util import ROOT

res = int(os.environ.get("RES", "1000"))
objs = m_build.build(shape_keys=False)
m_pose.apply_pose(objs["rig"], m_pose.HERO)
m_scene.setup_render(res=res, samples=64)
m_scene.lights()
m_scene.shadow_floor()
m_scene.camera(target=(0, 0, 0.80), dist=8.6, elev=13)
m_scene.render(os.path.join(ROOT, "tmp", "hero_front.png"))
if os.environ.get("MORE"):
    m_scene.camera(target=(0, 0, 1.12), dist=3.6, elev=6)
    m_scene.render(os.path.join(ROOT, "tmp", "hero_face.png"))
    m_scene.camera(target=(-0.72, 0, 1.12), dist=2.6, elev=6)
    m_scene.render(os.path.join(ROOT, "tmp", "hero_hand.png"))
    m_scene.camera(target=(0, 0, 0.80), dist=8.6, elev=13, azim=-38)
    m_scene.render(os.path.join(ROOT, "tmp", "hero_34.png"))
