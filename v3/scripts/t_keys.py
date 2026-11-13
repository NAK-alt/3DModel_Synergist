"""Check the shape keys in the source build (before export)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m_build
import m_pose
import m_scene
from m_util import ROOT

objs = m_build.build(shape_keys=True)
m_pose.apply_pose(objs["rig"], m_pose.HERO)
kb = objs["face"].data.shape_keys.key_blocks
print("verts", len(objs["face"].data.vertices), "key verts", len(kb[1].data))
for name in ("happy_L", "happy_R", "smile_big", "blush"):
    kb[name].value = 1.0
m_scene.setup_render(res=700, samples=32)
m_scene.lights()
m_scene.camera(target=(0, 0, 1.12), dist=3.6, elev=6)
m_scene.render(os.path.join(ROOT, "tmp", "keys_src.png"))
