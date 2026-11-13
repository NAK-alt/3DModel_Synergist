"""Render the hero pose through a camera matched to the plush photo: tmp/match.png (1536 px)."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector

import m_build
import m_pose
import m_scene
from m_util import ROOT


def photo_camera():
    """Camera solved from the photo: about 9.8 barrel-widths away, 17 degrees above, long lens."""
    cam = m_scene.camera(name="PhotoCam")
    cam.data.lens = 166.0
    cam.location = Vector((-0.046, -9.8, 4.09))
    m_scene._aim(cam, (-0.046, 0.0, 0.942))
    return cam


if __name__ == "__main__":
    objs = m_build.build(shape_keys=False)
    m_pose.apply_pose(objs["rig"], m_pose.HERO)
    m_scene.setup_render(res=1536, samples=int(os.environ.get("SAMPLES", "48")))
    m_scene.lights()
    m_scene.shadow_floor()
    photo_camera()
    m_scene.render(os.path.join(ROOT, "tmp", "match.png"))
