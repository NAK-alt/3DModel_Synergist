"""Render a few Face_Ctrl states from blend/mascot_face.blend for quick review.

  blender -b blend/mascot_face.blend --python scripts/test_face_controls.py -- <out_dir> name:ctrl=val,ctrl=val ...
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
out_dir = args[0]
os.makedirs(out_dir, exist_ok=True)
scene = bpy.context.scene
scene.render.resolution_x = scene.render.resolution_y = 500
scene.cycles.samples = 48
ctrl = bpy.data.objects["Face_Ctrl"]
defaults = {k: ctrl[k] for k in ctrl.keys() if isinstance(ctrl[k], float)}
for spec in args[1:]:
    name, _, assigns = spec.partition(":")
    for k, v in defaults.items():
        ctrl[k] = 0.0
    for a in filter(None, assigns.split(",")):
        k, v = a.split("=")
        ctrl[k] = float(v)
    ctrl.update_tag()
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(out_dir, f"{name}.png")
    bpy.ops.render.render(write_still=True)
