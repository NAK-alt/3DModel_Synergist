"""Final stills, orthographic views, turntable frames and the master .blend.
STEPS env: comma list of hero, ortho, turn, blend."""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import m_build
import m_face
import m_pose
import m_scene
from m_util import ROOT

steps = os.environ.get("STEPS", "hero,ortho,turn,blend").split(",")
keys = "blend" in steps and len(steps) == 1
objs = m_build.build(shape_keys=keys)
rig = objs["rig"]
m_pose.apply_pose(rig, m_pose.HERO)
m_scene.lights()
floor = m_scene.shadow_floor()

if "hero" in steps:
    res = int(os.environ.get("HERO_RES", "3840"))
    m_scene.setup_render(res=res, samples=int(os.environ.get("HERO_SAMPLES", "220")))
    out = os.path.join(ROOT, "exports", "hero")
    os.makedirs(out, exist_ok=True)
    for name, azim in (("front", 0), ("threequarter", -36), ("back", 180), ("side", 90)):
        m_scene.camera(target=(0, 0, 0.80), dist=8.4, elev=12, azim=azim)
        m_scene.render(os.path.join(out, f"hero_{name}.png"))
    m_scene.camera(target=(0, 0, 1.12), dist=3.5, elev=6)
    m_scene.render(os.path.join(out, "hero_face.png"))
    m_scene.camera(target=(0, 0, 0.80), dist=2.9, elev=4)
    m_scene.render(os.path.join(out, "hero_logo.png"))

if "ortho" in steps:
    m_scene.setup_render(res=1400, samples=96)
    out = os.path.join(ROOT, "exports", "ortho")
    os.makedirs(out, exist_ok=True)
    floor.hide_render = True
    for name, azim in (("front", 0), ("side", 90), ("back", 180)):
        cam = m_scene.camera(target=(0, 0, 0.80), dist=9, elev=0, azim=azim)
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 2.35
        m_scene.render(os.path.join(out, f"ortho_{name}.png"))
        cam.data.type = "PERSP"
    floor.hide_render = False

if "turn" in steps:
    n = int(os.environ.get("TURN_FRAMES", "180"))
    m_scene.setup_render(res=1080, samples=int(os.environ.get("TURN_SAMPLES", "72")))
    m_scene.camera(target=(0, 0, 0.80), dist=8.6, elev=11)
    out = os.path.join(ROOT, "tmp", "turn")
    os.makedirs(out, exist_ok=True)
    for i in range(n):
        rig.rotation_euler = (0, 0, 2 * math.pi * i / n)
        m_scene.render(os.path.join(out, f"f_{i:04d}.png"))
    rig.rotation_euler = (0, 0, 0)

if "blend" in steps:
    m_scene.setup_render(res=1500, samples=160)
    m_scene.camera(target=(0, 0, 0.80), dist=8.4, elev=12)
    face = objs["face"]
    face["expressions"] = json.dumps(m_face.EXPRESSIONS)
    txt = bpy.data.texts.new("README_mascot_v2")
    txt.write("""Synergist mascot v2
- MascotRig: pose the bones (arm0..9, hand, fingers, leg0..2, foot, body). Arms and legs are rubber hoses.
- Mascot_Face: shape keys drive the face (blink, happy, look, brows, mouth, visemes, hearts, stars, tears, sweat).
- Run the text block 'apply_expression' to set one of the 20 named expressions.
""")
    code = bpy.data.texts.new("apply_expression")
    code.write("""import bpy, json
NAME = "Big laugh"   # change me: see bpy.data.objects["Mascot_Face"]["expressions"]
face = bpy.data.objects["Mascot_Face"]
presets = json.loads(face["expressions"])
for kb in face.data.shape_keys.key_blocks[1:]:
    kb.value = presets[NAME].get(kb.name, 0.0)
""")
    path = os.path.join(ROOT, "blend", "mascot_v2.blend")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        print("pack failed", e)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("saved", path)
