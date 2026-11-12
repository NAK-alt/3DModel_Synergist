"""Quick look at the bind pose."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m_build
import m_scene
from m_util import ROOT

objs = m_build.build(shape_keys=False)
m_scene.setup_render(res=900, samples=48)
m_scene.lights()
m_scene.shadow_floor()
m_scene.camera(dist=9.5)
m_scene.render(os.path.join(ROOT, "tmp", "rest_front.png"))
m_scene.camera(target=(0, 0, 1.1), dist=4.2, elev=6)
m_scene.render(os.path.join(ROOT, "tmp", "rest_face.png"))
