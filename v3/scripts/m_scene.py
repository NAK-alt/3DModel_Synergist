"""Studio lighting, camera and render settings."""
import math

import bpy
from mathutils import Vector


def _aim(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_render(res=1500, samples=128, engine="CYCLES", transparent=True, res_y=None):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x = res
    sc.render.resolution_y = res_y or res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if engine == "CYCLES":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    break
            except Exception:
                continue
        for d in prefs.devices:
            d.use = d.type == prefs.compute_device_type
        sc.cycles.device = "GPU"
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        try:
            sc.cycles.denoiser = "OPTIX"
        except Exception:
            pass
        sc.cycles.max_bounces = 6
        sc.cycles.transparent_max_bounces = 8
    return sc


def lights(strength=0.27):
    sc = bpy.context.scene
    specs = [("Key", (-2.6, -3.6, 3.6), 3.0, 1000), ("Fill", (3.6, -2.8, 1.6), 4.0, 200),
             ("Rim", (2.0, 3.4, 3.2), 2.5, 620), ("Top", (0.0, -0.5, 5.0), 4.0, 260),
             ("Bounce", (0.0, -3.2, -0.6), 4.0, 240)]
    out = []
    for name, loc, size, power in specs:
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape = "DISK"
        ld.size = size
        ld.energy = power * strength
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        sc.collection.objects.link(ob)
        _aim(ob, (0, 0, 0.9))
        out.append(ob)
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.9, 0.9, 0.92, 1)
        bg.inputs["Strength"].default_value = 0.42 * strength
    return out


def shadow_floor():
    me = bpy.data.meshes.new("Floor")
    s = 12
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Floor", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.is_shadow_catcher = True
    return ob


def camera(target=(0, 0, 0.82), dist=7.2, elev=9.0, azim=0.0, lens=85.0, name="Camera"):
    """azim 0 = straight on the face; positive turns toward the viewer's right."""
    sc = bpy.context.scene
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_width = 36
    e, a = math.radians(elev), math.radians(azim)
    t = Vector(target)
    cam.location = t + Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))
    _aim(cam, t)
    sc.camera = cam
    return cam


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
