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
                 velvet_strength=0.25, velvet_scale=180,
                 pile_scale=35, sheen_tint_mix=0.3):
    """Create a fleece-like material with crushed velvet normal."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (1200, 0)

    # Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (900, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Base Color with variation
    base_color = hex_lin(hex_color)
    base_dark = tuple(c * 0.9 for c in base_color[:3]) + (1.0,)

    # Texture Coordinate and Noise for color variation (low freq)
    tex_coord = nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (-1200, 300)

    noise_low = nodes.new(type='ShaderNodeTexNoise')
    noise_low.location = (-1000, 300)
    noise_low.inputs['Scale'].default_value = pile_scale * 0.2
    noise_low.inputs['Detail'].default_value = 2
    noise_low.inputs['Roughness'].default_value = 0.65
    links.new(tex_coord.outputs['Object'], noise_low.inputs['Vector'])

    # Mix factor = noise * 0.5
    mix_factor = nodes.new(type='ShaderNodeMath')
    mix_factor.operation = 'MULTIPLY'
    mix_factor.location = (-800, 300)
    mix_factor.inputs[1].default_value = 0.5
    links.new(noise_low.outputs['Fac'], mix_factor.inputs[0])

    # Color mix
    mix_color = nodes.new(type='ShaderNodeMixRGB')
    mix_color.location = (-600, 0)
    mix_color.blend_type = 'MIX'
    mix_color.inputs['Color1'].default_value = base_dark
    mix_color.inputs['Color2'].default_value = base_color
    links.new(mix_factor.outputs['Value'], mix_color.inputs['Fac'])

    # ---- Crushed velvet pile pattern ----
    # Noise A (domain warp)
    noise_a = nodes.new(type='ShaderNodeTexNoise')
    noise_a.location = (-1200, -200)
    noise_a.inputs['Scale'].default_value = pile_scale
    noise_a.inputs['Detail'].default_value = 4
    noise_a.inputs['Roughness'].default_value = 0.55
    noise_a.inputs['Distortion'].default_value = 2.5
    links.new(tex_coord.outputs['Object'], noise_a.inputs['Vector'])

    # Vector Math: (Noise A color - 0.5) * 0.04
    subtract_vec = nodes.new(type='ShaderNodeVectorMath')
    subtract_vec.operation = 'SUBTRACT'
    subtract_vec.location = (-1000, -200)
    subtract_vec.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(noise_a.outputs['Color'], subtract_vec.inputs[0])

    scale_vec = nodes.new(type='ShaderNodeVectorMath')
    scale_vec.operation = 'SCALE'
    scale_vec.location = (-800, -200)
    scale_vec.inputs['Scale'].default_value = 0.04
    links.new(subtract_vec.outputs['Vector'], scale_vec.inputs[0])

    add_vec = nodes.new(type='ShaderNodeVectorMath')
    add_vec.operation = 'ADD'
    add_vec.location = (-600, -200)
    links.new(tex_coord.outputs['Object'], add_vec.inputs[0])
    links.new(scale_vec.outputs['Vector'], add_vec.inputs[1])

    # Noise B (warped high-frequency)
    noise_b = nodes.new(type='ShaderNodeTexNoise')
    noise_b.location = (-400, -200)
    noise_b.inputs['Scale'].default_value = pile_scale * 1.6
    noise_b.inputs['Detail'].default_value = 8
    noise_b.inputs['Roughness'].default_value = 0.6
    links.new(add_vec.outputs['Vector'], noise_b.inputs['Vector'])

    # Color Ramp for pile height
    ramp = nodes.new(type='ShaderNodeValToRGB')
    ramp.location = (-200, -200)
    ramp.color_ramp.interpolation = 'EASE'
    # Remove default two stops and add custom
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(noise_b.outputs['Fac'], ramp.inputs['Fac'])

    # Fine fibre noise
    noise_c = nodes.new(type='ShaderNodeTexNoise')
    noise_c.location = (-400, -500)
    noise_c.inputs['Scale'].default_value = 900
    noise_c.inputs['Detail'].default_value = 2
    links.new(tex_coord.outputs['Object'], noise_c.inputs['Vector'])

    mult_fibre = nodes.new(type='ShaderNodeMath')
    mult_fibre.operation = 'MULTIPLY'
    mult_fibre.location = (-200, -500)
    mult_fibre.inputs[1].default_value = 0.15
    links.new(noise_c.outputs['Fac'], mult_fibre.inputs[0])

    # Final pile = ramp + fibre
    add_pile = nodes.new(type='ShaderNodeMath')
    add_pile.operation = 'ADD'
    add_pile.location = (0, -200)
    links.new(ramp.outputs['Color'], add_pile.inputs[0])
    links.new(mult_fibre.outputs['Value'], add_pile.inputs[1])

    # Bump
    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (200, -200)
    bump.inputs['Strength'].default_value = velvet_strength
    bump.inputs['Distance'].default_value = 0.003
    links.new(add_pile.outputs['Value'], bump.inputs['Height'])
    if 'Normal' in bsdf.inputs:
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    # Pile modulates colour: darker in crushed areas
    # Factor = (1 - pile) * 0.6
    one_minus_pile = nodes.new(type='ShaderNodeMath')
    one_minus_pile.operation = 'SUBTRACT'
    one_minus_pile.location = (400, -100)
    one_minus_pile.inputs[0].default_value = 1.0
    links.new(add_pile.outputs['Value'], one_minus_pile.inputs[1])

    mult_dark = nodes.new(type='ShaderNodeMath')
    mult_dark.operation = 'MULTIPLY'
    mult_dark.location = (600, -100)
    mult_dark.inputs[1].default_value = 0.6
    links.new(one_minus_pile.outputs['Value'], mult_dark.inputs[0])

    # Darker base = base * 0.72
    dark_base = tuple(c * 0.72 for c in base_color[:3]) + (1.0,)
    mix_dark = nodes.new(type='ShaderNodeMixRGB')
    mix_dark.location = (800, 0)
    mix_dark.blend_type = 'MIX'
    mix_dark.inputs['Color1'].default_value = base_color  # will be replaced by mix_color output? Actually we want to mix between existing mix_color and dark_base
    mix_dark.inputs['Color2'].default_value = dark_base
    links.new(mix_color.outputs['Color'], mix_dark.inputs['Color1'])
    links.new(mult_dark.outputs['Value'], mix_dark.inputs['Fac'])
    links.new(mix_dark.outputs['Color'], bsdf.inputs['Base Color'])

    # Sheen Weight driven by pile: map range pile 0..1 -> sheen*0.7 .. sheen*1.2
    map_range = nodes.new(type='ShaderNodeMapRange')
    map_range.location = (400, -300)
    map_range.inputs['From Min'].default_value = 0.0
    map_range.inputs['From Max'].default_value = 1.0
    map_range.inputs['To Min'].default_value = sheen * 0.7
    map_range.inputs['To Max'].default_value = sheen * 1.2
    map_range.clamp = True
    links.new(add_pile.outputs['Value'], map_range.inputs['Value'])
    if 'Sheen Weight' in bsdf.inputs:
        links.new(map_range.outputs['Result'], bsdf.inputs['Sheen Weight'])

    # Sheen tint: mix base with white by sheen_tint_mix
    tint_mix = nodes.new(type='ShaderNodeMixRGB')
    tint_mix.location = (600, -400)
    tint_mix.blend_type = 'MIX'
    tint_mix.inputs['Color1'].default_value = base_color
    tint_mix.inputs['Color2'].default_value = (1, 1, 1, 1)
    tint_mix.inputs['Fac'].default_value = sheen_tint_mix
    if 'Sheen Tint' in bsdf.inputs:
        links.new(tint_mix.outputs['Color'], bsdf.inputs['Sheen Tint'])

    # Set Principled values
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
    if 'Sheen Roughness' in bsdf.inputs:
        bsdf.inputs['Sheen Roughness'].default_value = 0.3

    return mat

def create_satin(name, hex_color, angle_deg, stitch_scale=350, aniso=0.5):
    """Create satin/embroidery thread material."""
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

    # Base color
    base_color = hex_lin(hex_color)
    bsdf.inputs['Base Color'].default_value = base_color

    # Determine luminance for dark/light thread settings
    lum = 0.2126 * base_color[0] + 0.7152 * base_color[1] + 0.0722 * base_color[2]
    is_dark = lum < 0.05

    # Set BSDF parameters
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.8 if is_dark else 0.45
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = 0.5
    if 'Anisotropic Rotation' in bsdf.inputs:
        bsdf.inputs['Anisotropic Rotation'].default_value = angle_deg / 360.0
    if 'Sheen Weight' in bsdf.inputs:
        bsdf.inputs['Sheen Weight'].default_value = 0.12 if is_dark else 0.45
    if 'Sheen Tint' in bsdf.inputs:
        bsdf.inputs['Sheen Tint'].default_value = base_color
    if 'Sheen Roughness' in bsdf.inputs:
        bsdf.inputs['Sheen Roughness'].default_value = 0.35
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.2 if is_dark else 0.35

    # Stitch normal: Texture Coordinate -> Mapping -> Wave -> Power -> + fibre noise -> Bump
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
    wave.wave_profile = 'SIN'
    wave.inputs['Scale'].default_value = stitch_scale
    wave.inputs['Distortion'].default_value = 0.6
    wave.inputs['Detail'].default_value = 1
    wave.inputs['Detail Scale'].default_value = 1.0
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    # Power 0.5 for rounded thread cross-section
    power = nodes.new(type='ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (-200, 0)
    power.inputs[1].default_value = 0.5
    links.new(wave.outputs['Fac'], power.inputs[0])

    # Fibre detail noise
    noise_fibre = nodes.new(type='ShaderNodeTexNoise')
    noise_fibre.location = (-400, -300)
    noise_fibre.inputs['Scale'].default_value = 2500
    noise_fibre.inputs['Detail'].default_value = 1
    links.new(mapping.outputs['Vector'], noise_fibre.inputs['Vector'])

    mult_fibre = nodes.new(type='ShaderNodeMath')
    mult_fibre.operation = 'MULTIPLY'
    mult_fibre.location = (-200, -300)
    mult_fibre.inputs[1].default_value = 0.1
    links.new(noise_fibre.outputs['Fac'], mult_fibre.inputs[0])

    add_height = nodes.new(type='ShaderNodeMath')
    add_height.operation = 'ADD'
    add_height.location = (0, 0)
    links.new(power.outputs['Value'], add_height.inputs[0])
    links.new(mult_fibre.outputs['Value'], add_height.inputs[1])

    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (200, 0)
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = 0.0012
    links.new(add_height.outputs['Value'], bump.inputs['Height'])
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
    output.location = (1000, 0)

    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (700, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Metallic settings
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 1.0
    if 'Roughness' in bsdf.inputs:
        bsdf.inputs['Roughness'].default_value = 0.32
    if 'Anisotropic' in bsdf.inputs:
        bsdf.inputs['Anisotropic'].default_value = 0.6
    if 'Anisotropic Rotation' in bsdf.inputs:
        bsdf.inputs['Anisotropic Rotation'].default_value = angle_deg / 360.0

    # Texture Coordinate -> Mapping -> Wave (for color variation and bump)
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
    wave.wave_profile = 'SIN'
    wave.inputs['Scale'].default_value = 350
    wave.inputs['Distortion'].default_value = 0.6
    wave.inputs['Detail'].default_value = 1
    wave.inputs['Detail Scale'].default_value = 1.0
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    # Factor = wave^2 for color mix
    wave_sq = nodes.new(type='ShaderNodeMath')
    wave_sq.operation = 'POWER'
    wave_sq.location = (-200, 0)
    wave_sq.inputs[1].default_value = 2.0
    links.new(wave.outputs['Fac'], wave_sq.inputs[0])

    # Mix between two golds
    color1 = hex_lin("#B07E1A")  # input golds pre-compensated for AgX so the render reads ~#C9962E
    color2 = hex_lin("#D8B040")  # ... with highlights toward ~#F0D27A
    mix_color = nodes.new(type='ShaderNodeMixRGB')
    mix_color.location = (0, 0)
    mix_color.blend_type = 'MIX'
    mix_color.inputs['Color1'].default_value = color1
    mix_color.inputs['Color2'].default_value = color2
    links.new(wave_sq.outputs['Value'], mix_color.inputs['Fac'])
    links.new(mix_color.outputs['Color'], bsdf.inputs['Base Color'])

    # Raised stitch bump (same as satin but strength 0.9, distance 0.001)
    power = nodes.new(type='ShaderNodeMath')
    power.operation = 'POWER'
    power.location = (0, -200)
    power.inputs[1].default_value = 0.5
    links.new(wave.outputs['Fac'], power.inputs[0])

    noise_fibre = nodes.new(type='ShaderNodeTexNoise')
    noise_fibre.location = (-400, -300)
    noise_fibre.inputs['Scale'].default_value = 2500
    noise_fibre.inputs['Detail'].default_value = 1
    links.new(mapping.outputs['Vector'], noise_fibre.inputs['Vector'])

    mult_fibre = nodes.new(type='ShaderNodeMath')
    mult_fibre.operation = 'MULTIPLY'
    mult_fibre.location = (-200, -300)
    mult_fibre.inputs[1].default_value = 0.1
    links.new(noise_fibre.outputs['Fac'], mult_fibre.inputs[0])

    add_height = nodes.new(type='ShaderNodeMath')
    add_height.operation = 'ADD'
    add_height.location = (200, -200)
    links.new(power.outputs['Value'], add_height.inputs[0])
    links.new(mult_fibre.outputs['Value'], add_height.inputs[1])

    bump = nodes.new(type='ShaderNodeBump')
    bump.location = (400, -200)
    bump.inputs['Strength'].default_value = 0.9
    bump.inputs['Distance'].default_value = 0.001
    links.new(add_height.outputs['Value'], bump.inputs['Height'])
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
    for x in (-30.0, 30.0):  # wide enough that the 3/4 camera never sees an edge
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
    scene.cycles.filter_width = 1.5

    # Color management
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except:
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
    scene.view_settings.exposure = -0.5  # changed from -0.8

    # Resolution
    scene.render.resolution_x = args.res
    scene.render.resolution_y = args.res
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'

    # GPU device
    prefs = bpy.context.preferences.addons['cycles'].preferences
    gpu_found = False
    for backend in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type == backend  # enable every GPU of this backend, not the CPU
            if device.use:
                gpu_found = True
        if gpu_found:
            print(f"[03] Cycles backend {backend}: {[d.name for d in prefs.devices if d.use]}")
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

def _set(obj, attr, value):
    """Set obj.attr only if this Blender version has it (particle settings differ between versions)."""
    if hasattr(obj, attr):
        setattr(obj, attr, value)
    else:
        print(f"[03] note: {type(obj).__name__}.{attr} not available, skipped")


def setup_fur(enabled):
    """Create fur particle systems for plush objects if enabled."""
    if not enabled:
        return

    objects_for_fur = [
        "Body", "Lid_Top", "Lid_Rim",
        "Hoop_29", "Hoop_44", "Hoop_76", "Hoop_97",
        "Arm_Left", "Arm_Right", "Leg_Left", "Leg_Right",
        "Glove_Left_Palm", "Glove_Right_Palm",
        "Glove_Left_Cuff", "Glove_Right_Cuff",
        "Shoe_Left", "Shoe_Right"
    ]

    scene = bpy.context.scene

    for obj_name in objects_for_fur:
        if obj_name not in bpy.data.objects:
            continue
        obj = bpy.data.objects[obj_name]
        if obj.type != 'MESH':
            continue

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
        _set(settings, 'type', 'HAIR')

        # Compute area from polygons (local space, assuming scale=1)
        area_m2 = sum(p.area for p in obj.data.polygons)
        count = int(area_m2 * 9000)
        if count < 300:
            count = 300
        _set(settings, 'count', count)

        _set(settings, 'use_advanced_hair', True)
        _set(settings, 'emit_from', 'FACE')
        _set(settings, 'use_even_distribution', True)
        # random direction: factor_random is an absolute velocity, so keep it in mm
        _set(settings, 'factor_random', 0.0018)
        # hair_length is stored through normal_factor, so set it LAST (after any velocity settings)
        _set(settings, 'hair_length', 0.0045)

        _set(settings, 'child_type', 'INTERPOLATED')
        _set(settings, 'rendered_child_count', 20)
        _set(settings, 'child_length', 1.0)

        _set(settings, 'clump_factor', 0.45)
        _set(settings, 'clump_shape', -0.2)

        _set(settings, 'roughness_1', 0.002)
        _set(settings, 'roughness_1_size', 0.6)
        _set(settings, 'roughness_2', 0.0015)
        _set(settings, 'roughness_endpoint', 0.0008)

        _set(settings, 'root_radius', 0.00009)
        _set(settings, 'tip_radius', 0.00002)
        _set(settings, 'radius_scale', 1.0)

        _set(settings, 'display_step', 2)
        _set(settings, 'render_step', 3)

        # Material slot (object's only material, index 1)
        _set(settings, 'material', 1)

        # Ensure modifier is visible in render
        obj.modifiers["Fur"].show_render = True

    # Set scene hair settings if available
    if hasattr(scene.render, 'hair_type'):
        scene.render.hair_type = 'STRAND'
    if hasattr(scene.render, 'hair_subdiv'):
        scene.render.hair_subdiv = 2
    if hasattr(scene, 'cycles_curves'):
        scene.cycles_curves.shape = 'THICK'

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
    mat_body = create_fleece("MAT_Fleece_Blue", "#020B69", sheen=0.85,
                             pile_scale=35, velvet_strength=0.7,
                             sheen_tint_mix=0.05)
    mat_hoop = create_fleece("MAT_Fleece_Blue_Hoop", "#010858", sheen=0.85,
                             pile_scale=40, velvet_strength=0.7,
                             sheen_tint_mix=0.05)
    mat_navy = create_fleece("MAT_Fleece_Navy", "#101629", sheen=0.7,
                             pile_scale=45, velvet_strength=0.6,
                             sheen_tint_mix=0.3)
    mat_plush_white = create_fleece("MAT_Plush_White", "#F2EFEA", sheen=0.9,
                                    pile_scale=28, velvet_strength=0.8,
                                    sheen_tint_mix=0.3)

    # Satin materials
    satin_white = create_satin("MAT_Satin_White", "#F4F2EE", 35)
    satin_white_hl = create_satin("MAT_Satin_White_Highlight", "#F4F2EE", 80)
    satin_teeth = create_satin("MAT_Satin_White_Teeth", "#F4F2EE", 90)
    satin_black = create_satin("MAT_Satin_Black", "#0B0B0D", 90)
    satin_pupil = create_satin("MAT_Satin_Black_Pupil", "#0B0B0D", 20)
    satin_brow = create_satin("MAT_Satin_Black_Brow", "#0B0B0D", 0)
    satin_mouth_outline = create_satin("MAT_Satin_Black_MouthOutline", "#0B0B0D", 90)
    satin_mouth = create_satin("MAT_Satin_Mouth", "#4A1410", 10)
    satin_tongue = create_satin("MAT_Satin_Tongue", "#C0504D", 60)

    # Gold thread
    gold_wordmark = create_gold_thread("MAT_Gold_Wordmark", 0)
    gold_balls = create_gold_thread("MAT_Gold_Balls", 45)
    satin_badge_ring = create_satin("MAT_Satin_BadgeRing", "#F4F2EE", 90)

    # Nose felt
    mat_felt = create_fleece("MAT_Felt", "#0C0C0E", sheen=0.35,
                             pile_scale=220, velvet_strength=0.4,
                             sheen_tint_mix=0.3)

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
    for name in ["Eyelid_Left_Upper", "Eyelid_Left_Lower", "Eyelid_Right_Upper", "Eyelid_Right_Lower"]:
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
    # Fur setup (once, before rendering any views)
    # ------------------------------------------------------------------
    if not parsed.no_fur:
        print("Setting up fur...")
        setup_fur(True)

    # ------------------------------------------------------------------
    # Render views
    # ------------------------------------------------------------------
    views = [v.strip() for v in parsed.views.split(',') if v.strip()]
    total_start = time.perf_counter()

    for view in views:
        print(f"Rendering view: {view}")
        # Set camera
        set_camera_view(view)

        # Render
        scene = bpy.context.scene
        scene.render.filepath = os.path.join(render_dir, f"look_{view}.png")
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        end = time.perf_counter()
        print(f"[03] view {view} {end - start:.1f}s")

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
