import bpy, math
from mathutils import Vector
sc = bpy.context.scene; cam = sc.camera; tgt = bpy.data.objects["Camera_Target"]
for name, part, off in (("hand_wave", "Glove_Right_Palm", (0.25, -1.0, 0.05)), ("hand_rest", "Glove_Left_Palm", (0.55, -0.9, 0.1))):
    o = bpy.data.objects[part]
    c = sum((o.matrix_world @ Vector(b) for b in o.bound_box), Vector()) / 8
    tgt.location = c; cam.data.lens = 85
    cam.location = c + Vector(off)
    sc.render.filepath = r"C:\Users\Admin\AppData\Local\Temp\claude\c9c4ad4fffb32629\dcc34b81-d58c-5e4f-9e76-9a5246ffe9bd\scratchpad\%s.png" % name
    bpy.ops.render.render(write_still=True)
