"""Re-import the GLB into an empty scene, report its contents and render a check image."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import m_scene
from m_util import ROOT

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "exports", "synergist-mascot-v3.glb"))
tris = 0
for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.data.calc_loop_triangles()
        t = len(ob.data.loop_triangles)
        tris += t
        keys = len(ob.data.shape_keys.key_blocks) - 1 if ob.data.shape_keys else 0
        print("MESH", ob.name, "tris", t, "morphs", keys, "materials", len(ob.data.materials))
        if keys:
            kb = ob.data.shape_keys.key_blocks
            for name, val in (("happy_L", 1.0), ("happy_R", 1.0), ("smile_big", 1.0), ("blush", 1.0)):
                if name in kb:
                    kb[name].value = val
    elif ob.type == "ARMATURE":
        print("ARMATURE", ob.name, "bones", len(ob.data.bones))
print("TOTAL tris", tris)
m_scene.setup_render(res=1000, samples=64)
m_scene.lights()
m_scene.camera(target=(0, 0, 0.92), dist=9.4, elev=12)
m_scene.render(os.path.join(ROOT, "renders", "glb_check.png"))
