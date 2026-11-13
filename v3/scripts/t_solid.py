import os, sys, bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m_util import ROOT
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "exports", "synergist-mascot-v2.glb"))
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "MATERIAL"
sc.render.resolution_x = sc.render.resolution_y = 800
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam)
cam.location = (0, -7, 1.6); cam.rotation_euler = (1.45, 0, 0); cam.data.lens = 85; sc.camera = cam
sc.render.filepath = os.path.join(ROOT, "tmp", "glb_solid.png")
bpy.ops.render.render(write_still=True)
