import bpy
import os
import sys
import math
import argparse
import importlib.util
import time

def hex_lin(hex_color):
    """Convert sRGB hex color to linear RGB tuple (r,g,b,1)."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    def srgb_to_linear(c):
        return math.pow(c, 2.2)  # approximation
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), 1.0)

def set_gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = (device.type == 'OPTIX')
    bpy.context.scene.cycles.device = 'GPU'

def aim(cam_loc, target):
    cam = bpy.data.objects.get("Camera")
    target_obj = bpy.data.objects.get("Look_Target")
    if cam is None or target_obj is None:
        raise RuntimeError("Camera or Look_Target not found")
    for c in cam.constraints:  # the saved camera may still track the model's Camera_Target
        if c.type == 'TRACK_TO':
            c.target = target_obj
    cam.location = cam_loc
    target_obj.location = target

def get_fcurves(obj):
    """Return list of fcurves from obj's animation_data.action, handling action layers/slots."""
    if not obj.animation_data or not obj.animation_data.action:
        return []
    action = obj.animation_data.action
    if hasattr(action, 'fcurves') and action.fcurves:
        return list(action.fcurves)
    try:
        layers = action.layers
        if layers:
            layer = layers[0]
            if layer.strips:
                strip = layer.strips[0]
                if action.slots:
                    slot = action.slots[0]
                    channelbag = strip.channelbag(slot)
                    if channelbag:
                        return list(channelbag.fcurves)
    except Exception:
        pass
    return []

def set_linear_interpolation(obj):
    for fcurve in get_fcurves(obj):
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'

def load_rig_module():
    script_dir = os.path.dirname(os.path.abspath(__file__))  # sys.argv[0] is blender.exe
    rig_path = os.path.join(script_dir, "05_rig.py")
    spec = importlib.util.spec_from_file_location("rig05", rig_path)
    rig05 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rig05)
    return rig05

def hero(project_root, hero_res, hero_samples, rig05):
    start_time = time.time()
    rig05.set_pose("wave")
    scene = bpy.context.scene
    scene.render.resolution_x = hero_res
    scene.render.resolution_y = hero_res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.cycles.samples = hero_samples
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.denoiser = 'OPTIX'
    scene.cycles.use_denoising = True

    cam = bpy.data.objects["Camera"]
    cam.data.lens = 50
    cam.data.type = 'PERSP'

    backdrop_obj = bpy.data.objects.get("Backdrop")
    world = bpy.data.worlds.get("Lookdev_World")
    mat = bpy.data.materials.get("MAT_Backdrop")
    bg_node = None
    if world and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == 'BACKGROUND':
                bg_node = node
                break

    # Save original states
    orig_backdrop_color = None
    if mat and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                orig_backdrop_color = node.inputs['Base Color'].default_value[:]
                break
    orig_world_color = bg_node.inputs['Color'].default_value[:] if bg_node else None
    orig_world_strength = bg_node.inputs['Strength'].default_value if bg_node else None
    orig_rim_energies = {}
    for light_name in ["Rim_Light_New"]:
        light = bpy.data.objects.get(light_name)
        if light and light.type == 'LIGHT':
            orig_rim_energies[light_name] = light.data.energy

    views = [
        {"name": "hero_front", "cam_loc": (-0.9, -6.3, 1.25), "target": (0, 0, 1.05)},
        {"name": "hero_threequarter", "cam_loc": (-4.3, -4.5, 1.35), "target": (0, 0, 1.05)},
        {"name": "hero_back", "cam_loc": (0.45, 4.4, 1.25), "target": (0, 0, 1.05), "lens": 50},  # wall is at y=5.5
    ]
    views.append({
        "name": "hero_front_navy",
        "cam_loc": (-0.9, -6.3, 1.25),
        "target": (0, 0, 1.05),
        "navy": True
    })

    hero_output_dir = os.path.join(project_root, "exports", "hero")
    os.makedirs(hero_output_dir, exist_ok=True)
    renders_output_dir = os.path.join(project_root, "renders")
    os.makedirs(renders_output_dir, exist_ok=True)

    for view in views:
        aim(view["cam_loc"], view["target"])
        cam.data.lens = view.get("lens", 70)  # character fills ~85% of the frame
        if view.get("navy"):
            navy_hex = "#101629"
            linear_navy = hex_lin(navy_hex)
            if mat and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Base Color'].default_value = linear_navy
                        break
            if bg_node:
                bg_node.inputs['Color'].default_value = linear_navy
                bg_node.inputs['Strength'].default_value = 0.25
            for light_name, orig_energy in orig_rim_energies.items():
                light = bpy.data.objects.get(light_name)
                if light and light.type == 'LIGHT':
                    light.data.energy = orig_energy * 2

        img_path = os.path.join(hero_output_dir, f"{view['name']}.png")
        scene.render.filepath = img_path
        bpy.ops.render.render(write_still=True)

        img = bpy.data.images.load(img_path)
        img.scale(1500, 1500)
        copy_path = os.path.join(renders_output_dir, f"{view['name']}.png")
        img.filepath_raw = copy_path
        img.file_format = 'PNG'
        img.save()
        bpy.data.images.remove(img)

        if view.get("navy"):
            if mat and mat.node_tree and orig_backdrop_color:
                for node in mat.node_tree.nodes:
                    if node.type == 'BSDF_PRINCIPLED':
                        node.inputs['Base Color'].default_value = orig_backdrop_color
                        break
            if bg_node and orig_world_color:
                bg_node.inputs['Color'].default_value = orig_world_color
                bg_node.inputs['Strength'].default_value = orig_world_strength
            for light_name, orig_energy in orig_rim_energies.items():
                light = bpy.data.objects.get(light_name)
                if light and light.type == 'LIGHT':
                    light.data.energy = orig_energy

    print(f"[08] hero {time.time()-start_time:.1f}s")

def turntable(project_root, tt_samples, rig05):
    start_time = time.time()
    rig05.reset_pose()
    rig05.set_pose("wave")
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 180
    scene.render.fps = 30
    scene.render.fps_base = 1

    mascot = bpy.data.objects.get("Mascot_Rig")
    if mascot is None:
        raise RuntimeError("Mascot_Rig not found")
    if not mascot.animation_data:
        mascot.animation_data_create()
    action = bpy.data.actions.new(name="MascotRotateAction")
    mascot.animation_data.action = action

    mascot.rotation_euler.z = 0.0
    mascot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    mascot.rotation_euler.z = 2 * math.pi
    mascot.keyframe_insert(data_path="rotation_euler", index=2, frame=181)
    set_linear_interpolation(mascot)

    aim((-0.9, -6.3, 1.25), (0, 0, 1.05))
    cam = bpy.data.objects["Camera"]
    cam.data.type = 'PERSP'
    cam.data.lens = 50

    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.cycles.samples = tt_samples
    scene.cycles.denoiser = 'OPTIX'
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True

    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'HIGH'
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.filepath = os.path.join(project_root, "exports", "turntable.mp4")

    bpy.ops.render.render(animation=True)

    scene.render.use_persistent_data = False
    print(f"[08] turntable {time.time()-start_time:.1f}s")

def ortho(project_root, rig05):
    start_time = time.time()
    rig05.reset_pose()
    scene = bpy.context.scene

    fur_modifiers = []
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM':
                fur_modifiers.append((mod, mod.show_render))
                mod.show_render = False

    backdrop = bpy.data.objects.get("Backdrop")
    if backdrop:
        backdrop.hide_render = True

    cam = bpy.data.objects["Camera"]
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2.6
    target = (0, 0, 1.15)

    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.cycles.samples = 32
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'

    ortho_output_dir = os.path.join(project_root, "exports", "ortho")
    os.makedirs(ortho_output_dir, exist_ok=True)

    views = [
        ("ortho_front", (0, -8, 1.15)),
        ("ortho_side", (8, 0, 1.15)),
        ("ortho_back", (0, 8, 1.15)),
    ]
    for name, cam_loc in views:
        aim(cam_loc, target)
        scene.render.filepath = os.path.join(ortho_output_dir, f"{name}.png")
        bpy.ops.render.render(write_still=True)

    for mod, show in fur_modifiers:
        mod.show_render = show

    if backdrop:
        backdrop.hide_render = False

    cam.data.type = 'PERSP'
    scene.render.film_transparent = False

    print(f"[08] ortho {time.time()-start_time:.1f}s")

def main():
    if "--" in sys.argv:
        args_list = sys.argv[sys.argv.index("--") + 1:]
    else:
        args_list = []
    parser = argparse.ArgumentParser(description="Blender final renders")
    parser.add_argument("project_root", help="Project root directory")
    parser.add_argument("--what", default="hero,turntable,ortho", help="Comma-separated list: hero,turntable,ortho")
    parser.add_argument("--hero-res", type=int, default=3840, help="Hero resolution (square)")
    parser.add_argument("--hero-samples", type=int, default=96, help="Hero cycles samples")
    parser.add_argument("--tt-samples", type=int, default=24, help="Turntable cycles samples")
    args = parser.parse_args(args_list)

    project_root = args.project_root
    os.makedirs(project_root, exist_ok=True)

    rig05 = load_rig_module()
    set_gpu()

    what = args.what.split(',')
    if 'hero' in what:
        hero(project_root, args.hero_res, args.hero_samples, rig05)
    if 'turntable' in what:
        turntable(project_root, args.tt_samples, rig05)
    if 'ortho' in what:
        ortho(project_root, rig05)

if __name__ == "__main__":
    main()
