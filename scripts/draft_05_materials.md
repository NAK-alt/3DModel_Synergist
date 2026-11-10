```python
import bpy
import os
import sys
import math
import time
import argparse
from mathutils import Vector, Euler

# Constants
BODY_TOP = 1.6742
BODY_H = 1.26
FACE_X = 0.03

def hz(p):
    """Hoop z coordinate for fraction p from top."""
    return BODY_TOP - p * BODY_H

def hex_lin(h):
    """Convert sRGB hex color to linear RGBA tuple."""
    h = h.lstrip('#')
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {h}")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    # sRGB to linear
    def srgb_to_lin(c):
        if c <= 0.04045:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4
    return (srgb_to_lin(r), srgb_to_lin(g), srgb_to_lin(b), 1.0)

# ----------------------------------------------------------------------
# Material creation helpers
# ----------------------------------------------------------------------

def create_fleece(name, hex_color, sheen=0.6, rough=0.9,
                 velvet_strength=0.25, velvet_scale=180):
    """Create a fleece-like material with crushed velvet normal."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (600, 0)

    # Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Base Color with variation
    base_color = hex_lin(hex_color)
    base_dark = tuple(c * 0.9 for c in base_color[:3]) + (1.0,)

    # Texture Coordinate and Noise for color variation (low freq)
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 200)

    noise_low = nodes.new(type='ShaderNodeTexNoise')
    noise_low.location = (-600, 200)
    noise_low.inputs['Scale'].default_value = velvet_scale * 0.2
    noise_low.inputs['Detail'].default_value = 2
    noise_low.inputs['Roughness'].default_value = 0.65
    links.new(tex_coord.outputs['Object'], noise_low.inputs['Vector'])

    # Mix factor = noise * 0.5
    mix_factor = nodes.new(type='ShaderNodeMath')
    mix_factor.operation = 'MULTIPLY'
    mix_factor.location = (-400, 200)
    mix_factor.inputs[1].default_value = 0.5
    links.new(noise_low.outputs['Fac'], mix_factor.inputs[0])

    # Color mix
    mix_color = nodes.new(type='ShaderNodeMixRGB')
    mix_color.location = (-200, 0)
    mix_color.blend_type = 'MIX'
    mix_color.inputs['Color1'].default_value = base_dark
    mix_color.inputs['Color2'].default_value = base_color
    links.new(mix_factor.outputs['Value'], mix_color.inputs['Fac'])
    links.new(mix_color.outputs['Color'], bsdf.inputs['Base Color'])

    # Sheen tint: mix base with white 70% toward white
    tint_mix = nodes.new(type='ShaderNodeMixRGB')
    tint_mix.location = (-200, -300)
    tint_mix.blend_type = 'MIX'
    tint_mix.inputs['Color1'].default_value = base_color
    tint_mix.inputs['Color2'].default_value = (1, 1, 1, 1)
    tint_mix.inputs['Fac'].default_value = 0.7
    links.new(tint_mix.outputs['Color'], bsdf.inputs['Sheen Tint'])

    # Set Principled values
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.25
    if 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = sheen
    if 'Sheen Roughness' in bsdf.inputs:
        bsdf.inputs['Sheen Roughness'].default_value = 0.4

    # Crushed velvet normal: two noises multiplied -> bump
    noise_high = nodes.new(type='ShaderNodeTexNoise')
    noise_high.location = (-600, -200)
    noise_high.inputs['Scale'].default_value = velvet_scale
    noise_high.inputs['Detail'].default_value = 6
    noise_high.inputs['Roughness'].default_value = 0.65
    links.new(tex_coord.outputs['Object'], noise_high.inputs['Vector'])

    noise_low2 = nodes.new(type='ShaderNodeTexNoise')
    noise_low2.location = (-600, -400)
    noise_low2.inputs['Scale'].default_value = velvet_scale * 0.2
    noise_low2.inputs['Detail'].default_value = 2
    noise_low2.inputs['Roughness'].default_value = 0.65
    links.new(tex_coord.outputs['Object'], noise_low2.inputs['Vector'])

    mult = nodes.new(type='ShaderNodeMath')
    mult.operation = 'MULTIPLY'
    mult.location = (-400, -200)
    links.new(noise_high.outputs['Fac'], mult.inputs[0])
    links.new(noise_low2.outputs['Fac'], mult.inputs[1])

    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (0, -200)
    bump.inputs['Strength'].default_value = velvet_strength
    bump.inputs['Distance'].default_value = 0.0015
    links.new(mult.outputs['Value'], bump.inputs['Height'])
    if 'Normal' in bsdf.inputs:
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat

def create_satin(name, hex_color, angle_deg, stitch_scale=550, aniso=0.6):
    """Create satin/embroidery thread material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (600, 0)

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Base color
    base_color = hex_lin(hex_color)
    bsdf.inputs['Base Color'].default_value = base_color

    # Roughness, anisotropic, sheen
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.35
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = aniso
    if 'Anisotropic Rotation' in bsdf.inputs:
        bsdf.inputs['Anisotropic Rotation'].default_value = angle_deg / 360.0
    if 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = 0.3

    # Stitch normal: Texture Coordinate -> Mapping -> Wave -> Bump -> Normal
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-600, 0)
    mapping.inputs['Rotation'].default_value = (0, math.radians(angle_deg), 0)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    wave = nodes.new(type='ShaderNodeTexWave')
    wave.location = (-400, 0)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = stitch_scale
    wave.inputs['Distortion'].default_value = 1.5
    wave.inputs['Detail'].default_value = 2
    wave.inputs['Detail Scale'].default_value = 1.0
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (0, 0)
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.0008
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    if 'Normal' in bsdf.inputs:
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat

def create_gold_thread(name, angle_deg):
    """Create gold thread material with metallic and color variation."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (800, 0)

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (500, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Metallic
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 1.0
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.3
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = 0.7
    if 'Anisotropic Rotation' in bsdf.inputs:
        bsdf.inputs['Anisotropic Rotation'].default_value = angle_deg / 360.0

    # Texture Coordinate -> Mapping -> Wave (for color variation)
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-600, 200)

    mapping = nodes.new(type='ShaderNodeMapping')
    mapping.location = (-400, 200)
    mapping.inputs['Rotation'].default_value = (0, math.radians(angle_deg), 0)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    wave = nodes.new(type='ShaderNodeTexWave')
    wave.location = (-200, 200)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 550
    wave.inputs['Distortion'].default_value = 1.5
    wave.inputs['Detail'].default_value = 2
    wave.inputs['Detail Scale'].default_value = 1.0
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    # Mix between two golds
    color1 = hex_lin("#D5B268")
    color2 = hex_lin("#EED295")
    mix_color = nodes.new(type='ShaderNodeMixRGB')
    mix_color.location = (0, 0)
    mix_color.blend_type = 'MIX'
    mix_color.inputs['Color1'].default_value = color1
    mix_color.inputs['Color2'].default_value = color2
    links.new(wave.outputs['Fac'], mix_color.inputs['Fac'])
    links.new(mix_color.outputs['Color'], bsdf.inputs['Base Color'])

    # Also add stitch normal (similar to satin)
    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (200, -200)
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.0008
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    if 'Normal' in bsdf.inputs:
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat

# ----------------------------------------------------------------------
# Material assignment helper
# ----------------------------------------------------------------------

def assign_material(obj_name, mat):
    """Replace all material slots of object with given material."""
    if obj_name in bpy.data.objects:
        obj = bpy.data.objects[obj_name]
        if obj.type == 'MESH':
            # Clear existing slots and append new
            obj.data.materials.clear()
            obj.data.materials.append(mat)
        else:
            print(f"Warning: {obj_name} is not a mesh, skipping material assignment")
    else:
        print(f"Warning: object {obj_name} not found")

# ----------------------------------------------------------------------
# Studio setup
# ----------------------------------------------------------------------

def create_backdrop():
    """Create seamless backdrop mesh."""
    # Profile points: start at (y=-6, z=0) to (y=3, z=0), quarter circle to (y=5.5, z=2.5), then vertical to z=8
    # We'll generate 40 segments along profile, plus two rows across x.
    profile_points = []
    segments = 40
    # Floor part: from y=-6 to y=3
    floor_y_start = -6.0
    floor_y_end = 3.0
    floor_segments = int(segments * (floor_y_end - floor_y_start) / (8.0 + 2.5*math.pi/2 + 5.5))  # approximate
    # We'll just generate uniformly along profile using parameter t from 0 to 1.
    # Profile length: floor length = 9, quarter circle arc = 2.5*pi/2 ≈ 3.927, vertical length = 5.5.
    # Total length ≈ 18.427. We'll approximate.
    total_length = 9.0 + (2.5 * math.pi / 2) + 5.5
    for i in range(segments + 1):
        t = i / segments  # 0 to 1
        dist = t * total_length
        if dist <= 9.0:
            # Floor
            y = -6.0 + dist
            z = 0.0
        elif dist <= 9.0 + 2.5 * math.pi / 2:
            # Quarter circle from (3,0) to (5.5,2.5) center (3,2.5)
            angle = (dist - 9.0) / 2.5  # angle in radians from -pi/2 to 0
            angle_actual = -math.pi/2 + angle
            y = 3.0 + 2.5 * math.cos(angle_actual)
            z = 2.5 + 2.5 * math.sin(angle_actual)
        else:
            # Vertical wall
            vert_dist = dist - (9.0 + 2.5 * math.pi / 2)
            y = 5.5
            z = 2.5 + vert_dist
        profile_points.append((y, z))

    # Create mesh
    mesh = bpy.data.meshes.new("Backdrop_Mesh")
    obj = bpy.data.objects.new("Backdrop", mesh)
    bpy.context.collection.objects.link(obj)

    # Create vertices: two rows at x=-10 and x=10
    verts = []
    for x in (-10.0, 10.0):
        for (y, z) in profile_points:
            verts.append((x, y, z))

    # Faces: quads between rows
    num_profile = len(profile_points)
    faces = []
    for i in range(num_profile - 1):
        v0 = i
        v1 = i + 1
        v2 = num_profile + i + 1
        v3 = num_profile + i
        faces.append((v0, v1, v2, v3))

    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # Smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Create material
    mat = bpy.data.materials.new("MAT_Backdrop")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = hex_lin("#E8E3E0")
    bsdf.inputs['Roughness'].default_value = 0.85
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    obj.data.materials.append(mat)

    return obj

def setup_world():
    """Set world background."""
    world = bpy.data.worlds.new("Lookdev_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = hex_lin("#E8E3E0")
    bg.inputs['Strength'].default_value = 0.25
    output = nodes.new(type='ShaderNodeOutputWorld')
    links.new(bg.outputs['Background'], output.inputs['Surface'])

def setup_lights():
    """Create studio lights and Look_Target empty."""
    # Look_Target empty
    target = bpy.data.objects.new("Look_Target", None)
    bpy.context.collection.objects.link(target)
    target.location = (0, 0, 1.0)
    target.empty_display_type = 'PLAIN_AXES'

    # Helper to create area light with track to target
    def create_area_light(name, location, size, energy, color, shape='RECTANGLE'):
        light_data = bpy.data.lights.new(name=name, type='AREA')
        light_data.shape = shape
        if shape == 'RECTANGLE':
            light_data.size = size[0]
            light_data.size_y = size[1]
        else:  # DISK
            light_data.size = size
        light_data.energy = energy
        light_data.color = color

        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = location

        # Track to target
        constraint = light_obj.constraints.new(type='TRACK_TO')
        constraint.target = target
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
        constraint.up_axis = 'UP_Y'
        return light_obj

    # Key light
    create_area_light("Key_Light_New", (-3.2, -3.6, 3.6), (3.0, 3.0), 1400,
                      (1.0, 0.96, 0.92), 'RECTANGLE')
    # Fill light
    create_area_light("Fill_Light_New", (3.8, -2.6, 2.0), (4.0, 4.0), 450,
                      (0.93, 0.96, 1.0), 'RECTANGLE')
    # Top light
    create_area_light("Top_Light_New", (0, 0.5, 5.5), (3.0, 3.0), 600,
                      (1.0, 1.0, 1.0), 'RECTANGLE')
    # Rim light
    create_area_light("Rim_Light_New", (1.5, 3.5, 3.0), (2.0, 2.0), 700,
                      (1.0, 1.0, 1.0), 'RECTANGLE')

def remove_old_elements():
    """Hide Ground, delete old lights."""
    if "Ground" in bpy.data.objects:
        bpy.data.objects["Ground"].hide_render = True
    for name in ["Key_Light", "Fill_Light", "Rim_Light"]:
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

# ----------------------------------------------------------------------
# Render settings
# ----------------------------------------------------------------------

def set_render_settings(args):
    """Configure Cycles render settings."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = args.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPTIX'
    except:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'

    scene.cycles.max_bounces = 8
    scene.cycles.film_filter_type = 'BOX'
    scene.cycles.film_filter_width = 1.5

    # Color management
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except:
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0

    # Resolution
    scene.render.resolution_x = args.res
    scene.render.resolution_y = args.res
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'

    # GPU device
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    gpu_found = False
    for device in prefs.devices:
        if device.type == 'OPTIX' and device.use:
            gpu_found = True
            break
    if not gpu_found:
        # Fallback to CUDA
        prefs.compute_device_type = 'CUDA'
        prefs.get_devices()
        for device in prefs.devices:
            if device.type == 'CUDA' and device.use:
                gpu_found = True
                break
    if not gpu_found:
        # Fallback to CPU
        prefs.compute_device_type = 'CPU'
        prefs.get_devices()
        print("No GPU found, using CPU")
    else:
        scene.cycles.device = 'GPU'
        print("Using GPU for rendering")

# ----------------------------------------------------------------------
# Camera views
# ----------------------------------------------------------------------

def set_camera_view(view_name):
    """Configure camera for a given view."""
    scene = bpy.context.scene
    camera = bpy.data.objects["Camera"]
    target = bpy.data.objects["Look_Target"]

    # Clear existing constraints
    for c in camera.constraints:
        camera.constraints.remove(c)

    # Add track to target
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = target
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    # Set camera data
    cam_data = camera.data
    if view_name == 'front':
        target.location = (0, 0, 0.98)
        camera.location = (0, -5.6, 1.05)
        cam_data.lens = 60
    elif view_name == 'threequarter':
        target.location = (0, 0, 0.98)
        camera.location = (-3.95, -3.95, 1.25)
        cam_data.lens = 60
    elif view_name == 'face':
        face_z = (hz(0.29) + hz(0.44)) / 2
        target.location = (FACE_X, 0, face_z - 0.03)
        camera.location = (FACE_X + 0.3, -2.4, face_z + 0.12)
        cam_data.lens = 85
    elif view_name == 'logo':
        # Find Logo_Wordmark bounding box
        if "Logo_Wordmark" in bpy.data.objects:
            logo_obj = bpy.data.objects["Logo_Wordmark"]
            # Get world bounding box center
            bbox_corners = [logo_obj.matrix_world @ Vector(corner) for corner in logo_obj.bound_box]
            min_z = min(corner.z for corner in bbox_corners)
            max_z = max(corner.z for corner in bbox_corners)
            logo_z = (min_z + max_z) / 2
        else:
            logo_z = 1.0  # fallback
        target.location = (0.04, 0, logo_z)
        camera.location = (0.18, -2.6, logo_z + 0.18)
        cam_data.lens = 100
    else:
        print(f"Warning: unknown view {view_name}")

# ----------------------------------------------------------------------
# Fur setup
# ----------------------------------------------------------------------

def setup_fur(enabled):
    """Enable or disable fur for close-up views."""
    objects_for_fur = ["Body", "Lid_Top", "Hoop_29", "Hoop_44", "Hoop_76", "Hoop_97"]
    try:
        for obj_name in objects_for_fur:
            if obj_name not in bpy.data.objects:
                continue
            obj = bpy.data.objects[obj_name]
            # Check if particle system already exists
            psys = None
            for mod in obj.modifiers:
                if mod.type == 'PARTICLE_SYSTEM':
                    psys = mod.particle_system
                    break
            if psys is None:
                # Create new particle system
                obj.modifiers.new("Fur", type='PARTICLE_SYSTEM')
                psys = obj.modifiers["Fur"].particle_system
                psys.settings = bpy.data.particles.new("FurSettings")
                settings = psys.settings
                settings.type = 'HAIR'
                settings.count = 60000 if obj_name in ["Body", "Lid_Top"] else 8000
                settings.hair_length = 0.0025
                settings.use_advanced_hair = True
                settings.child_type = 'INTERPOLATED'
                settings.rendered_child_count = 12
                settings.child_length = 1.0
                settings.roughness_2 = 0.004
                settings.root_radius = 0.00012
                settings.tip_radius = 0.0
                # Assign material (the object's own material)
                if obj.data.materials:
                    settings.material = len(obj.data.materials) - 1
            # Toggle render visibility
            obj.modifiers["Fur"].show_render = enabled
        # Set curves shape if available
        if hasattr(bpy.context.scene, 'cycles_curves'):
            bpy.context.scene.cycles_curves.shape = 'THICK'
    except Exception as e:
        print(f"Warning: could not set up fur particles: {e}")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    # Parse arguments after '--'
    argv = sys.argv
    if '--' in argv:
        args_start = argv.index('--') + 1
        args = argv[args_start:]
    else:
        args = []

    parser = argparse.ArgumentParser(description="Look-dev script for mascot")
    parser.add_argument('project_root', nargs='?', default=None,
                        help='Project root directory')
    parser.add_argument('--views', type=str, default='front,threequarter,face,logo',
                        help='Comma-separated list of views to render')
    parser.add_argument('--res', type=int, default=1500,
                        help='Render resolution (square)')
    parser.add_argument('--samples', type=int, default=384,
                        help='Cycles samples')
    parser.add_argument('--no-fur', action='store_true',
                        help='Disable fur rendering')
    parsed = parser.parse_args(args)

    # Determine project root
    if parsed.project_root is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
    else:
        project_root = parsed.project_root

    blend_dir = os.path.join(project_root, 'blend')
    render_dir = os.path.join(project_root, 'renders')
    os.makedirs(render_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Build materials and assign
    # ------------------------------------------------------------------
    print("Creating materials...")
    # Fleece materials
    mat_body = create_fleece("MAT_Fleece_Blue", "#1A3AAE")
    mat_hoop = create_fleece("MAT_Fleece_Blue_Hoop", "#16329A", velvet_strength=0.2)
    mat_navy = create_fleece("MAT_Fleece_Navy", "#101629", sheen=0.5)
    mat_plush_white = create_fleece("MAT_Plush_White", "#F2EFEA", sheen=0.8, rough=0.95,
                                    velvet_strength=0.4, velvet_scale=120)

    # Satin materials
    satin_white = create_satin("MAT_Satin_White", "#F4F2EE", 35)
    satin_white_hl = create_satin("MAT_Satin_White_Highlight", "#F4F2EE", 80)
    satin_teeth = create_satin("MAT_Satin_White_Teeth", "#F4F2EE", 90)
    satin_black = create_satin("MAT_Satin_Black", "#0B0B0D", 90)
    satin_pupil = create_satin("MAT_Satin_Black_Pupil", "#0B0B0D", 20)
    satin_brow = create_satin("MAT_Satin_Black_Brow", "#0B0B0D", 0)
    satin_mouth_outline = create_satin("MAT_Satin_Black_MouthOutline", "#0B0B0D", 90)
    satin_mouth = create_satin("MAT_Satin_Mouth", "#4A1410", 10, aniso=0.3)
    satin_tongue = create_satin("MAT_Satin_Tongue", "#C0504D", 60, aniso=0.3)

    # Gold thread
    gold_wordmark = create_gold_thread("MAT_Gold_Wordmark", 0)
    gold_balls = create_gold_thread("MAT_Gold_Balls", 45)
    satin_badge_ring = create_satin("MAT_Satin_BadgeRing", "#F4F2EE", 90)

    # Nose felt
    mat_felt = create_fleece("MAT_Felt", "#0C0C0E", sheen=0.35, rough=1.0,
                             velvet_strength=0.35, velvet_scale=260)

    # Assign materials to objects
    print("Assigning materials...")
    # Body and Lid_Top
    assign_material("Body", mat_body)
    assign_material("Lid_Top", mat_body)
    # Hoops and Lid_Rim
    for name in ["Hoop_29", "Hoop_44", "Hoop_76", "Hoop_97", "Lid_Rim"]:
        assign_material(name, mat_hoop)
    # Navy parts
    for name in ["Arm_Left", "Arm_Right", "Leg_Left", "Leg_Right"]:
        assign_material(name, mat_navy)
    # White parts
    for name in ["Glove_Left_Cuff", "Glove_Right_Cuff", "Glove_Left_Palm",
                 "Glove_Right_Palm", "Glove_Left_Wrist", "Glove_Right_Wrist",
                 "Glove_Left_Finger1", "Glove_Right_Finger1",
                 "Glove_Left_Finger2", "Glove_Right_Finger2",
                 "Glove_Left_Finger3", "Glove_Right_Finger3",
                 "Glove_Left_Thumb", "Glove_Right_Thumb",
                 "Shoe_Left", "Shoe_Right"]:
        assign_material(name, mat_plush_white)
    # Eye whites and highlights
    for name in ["Eye_Left_White", "Eye_Right_White"]:
        assign_material(name, satin_white)
    for name in ["Highlight_Left", "Highlight_Right"]:
        assign_material(name, satin_white_hl)
    assign_material("Teeth_Upper", satin_teeth)
    # Eye outlines and pupils
    for name in ["Eye_Left_Outline", "Eye_Right_Outline"]:
        assign_material(name, satin_black)
    for name in ["Pupil_Left", "Pupil_Right"]:
        assign_material(name, satin_pupil)
    for name in ["Brow_Left", "Brow_Right"]:
        assign_material(name, satin_brow)
    assign_material("Mouth_Outline", satin_mouth_outline)
    assign_material("Mouth", satin_mouth)
    assign_material("Tongue", satin_tongue)
    # Nose
    assign_material("Nose", mat_felt)
    # Logo parts
    assign_material("Logo_Wordmark", gold_wordmark)
    for i in range(1, 4):
        assign_material(f"Logo_Ball_{i}", gold_balls)
    assign_material("Logo_Badge_Ring", satin_badge_ring)
    # Eyelids (hidden) get body material
    for name in ["Eyelid_Left", "Eyelid_Right"]:
        assign_material(name, mat_body)

    # ------------------------------------------------------------------
    # Studio setup
    # ------------------------------------------------------------------
    print("Setting up studio...")
    remove_old_elements()
    create_backdrop()
    setup_world()
    setup_lights()

    # ------------------------------------------------------------------
    # Render settings
    # ------------------------------------------------------------------
    print("Configuring render settings...")
    set_render_settings(parsed)

    # ------------------------------------------------------------------
    # Render views
    # ------------------------------------------------------------------
    views = [v.strip() for v in parsed.views.split(',') if v.strip()]
    total_start = time.perf_counter()

    for view in views:
        print(f"Rendering view: {view}")
        # Set camera
        set_camera_view(view)
        # Fur toggling: only for face and logo, unless --no-fur
        if not parsed.no_fur and view in ['face', 'logo']:
            setup_fur(True)
        else:
            setup_fur(False)

        # Render
        scene = bpy.context.scene
        scene.render.filepath = os.path.join(render_dir, f"look_{view}.png")
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        end = time.perf_counter()
        print(f"[03] view {view} {end - start:.1f}s")

        # Disable fur after rendering close-ups
        if not parsed.no_fur and view in ['face', 'logo']:
            setup_fur(False)

    total_end = time.perf_counter()
    print(f"[03] total {total_end - total_start:.1f}s")

    # ------------------------------------------------------------------
    # Save blend file
    # ------------------------------------------------------------------
    blend_path = os.path.join(blend_dir, "mascot_lookdev.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"Saved {blend_path}")

if __name__ == "__main__":
    main()
```