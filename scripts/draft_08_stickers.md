```python
import bpy
import bmesh
import math
import random
import sys
import os
import importlib
import json
from mathutils import Vector, Matrix, Euler, Quaternion
from math import radians, tan, pi

# -------------------------------------------------------------------
# Argument parsing
# -------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
    else:
        args = []
    project_root = None
    only = None
    res = 1024
    samples = 64
    i = 0
    while i < len(args):
        if args[i] == "--only":
            if i + 1 < len(args):
                only = [int(x) for x in args[i+1].split(",")]
                i += 2
                continue
        elif args[i] == "--res":
            if i + 1 < len(args):
                res = int(args[i+1])
                i += 2
                continue
        elif args[i] == "--samples":
            if i + 1 < len(args):
                samples = int(args[i+1])
                i += 2
                continue
        else:
            if project_root is None:
                project_root = args[i]
            i += 1
            continue
        i += 1
    if project_root is None:
        print("Usage: ... -- <project_root> [--only 1,5,9] [--res 1024] [--samples 64]")
        sys.exit(1)
    return project_root, only, res, samples

project_root, only_list, res, samples = parse_args()

# -------------------------------------------------------------------
# Setup paths and imports
# -------------------------------------------------------------------
script_dir = os.path.dirname(os.path.realpath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

# Import sibling modules
import 05_rig as rig05
import 04_face as face04
import 03_materials as lookdev

# -------------------------------------------------------------------
# Global scene references
# -------------------------------------------------------------------
scene = bpy.context.scene
view_layer = bpy.context.view_layer
rig = bpy.data.objects.get("Mascot_Rig")
if rig is None:
    raise RuntimeError("Rig object 'Mascot_Rig' not found")
face_ctrl = bpy.data.objects.get("Face_Ctrl")
if face_ctrl is None:
    raise RuntimeError("Face_Ctrl object not found")

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------
SHOULDER_Z = rig05.SHOULDER_Z
HIP_Z = rig05.HIP_Z
BODY_TOP = rig05.BODY_TOP

# -------------------------------------------------------------------
# Prop creation helpers
# -------------------------------------------------------------------
def make_felt_material(name, hex_color):
    """Create a felt material using lookdev.create_fleece."""
    return lookdev.create_fleece(
        name=name,
        hex=hex_color,
        sheen=0.5,
        pile_scale=150,
        velvet_strength=0.4,
        sheen_tint_mix=0.2
    )

def make_metallic_material(name, hex_color, metallic=0.6, roughness=0.35):
    """Create a simple metallic material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = lookdev.hex_lin(hex_color)
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return mat

def make_transmissive_material(name, hex_color, transmission=0.6, roughness=0.05):
    """Create a glass-like material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = lookdev.hex_lin(hex_color)
        bsdf.inputs["Transmission"].default_value = transmission
        bsdf.inputs["Roughness"].default_value = roughness
    return mat

# -------------------------------------------------------------------
# Prop creation functions (all return objects)
# -------------------------------------------------------------------
def create_clipboard(check=False):
    """Create clipboard prop (check=False: lines; check=True: big check)."""
    name = "StkProp_Clipboard" if not check else "StkProp_ClipboardCheck"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Board
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0,0))
    board = bpy.context.active_object
    board.name = name
    board.scale = (0.30, 0.02, 0.40)  # x, y, z => width, thickness, height
    bpy.ops.object.transform_apply(scale=True)
    # Rounded corners: bevel modifier
    bpy.ops.object.modifier_add(type='BEVEL')
    board.modifiers["Bevel"].width = 0.02
    board.modifiers["Bevel"].segments = 3
    # Material: felt brown
    board_mat = make_felt_material("Clipboard_Board", "#8A5A2B")
    board.data.materials.append(board_mat)
    # Paper
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0.012, 0))
    paper = bpy.context.active_object
    paper.name = name + "_Paper"
    paper.scale = (0.26, 0.32, 1)
    bpy.ops.object.transform_apply(scale=True)
    paper_mat = make_felt_material("Clipboard_Paper", "#F4F2EE")
    paper.data.materials.append(paper_mat)
    paper.parent = board
    paper.matrix_parent_inverse = Matrix.Identity(4)
    # Clip
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0.015, 0.15))
    clip = bpy.context.active_object
    clip.name = name + "_Clip"
    clip.scale = (0.08, 0.02, 0.04)
    bpy.ops.object.transform_apply(scale=True)
    clip_mat = make_metallic_material("Clipboard_Clip", "#B8BEC6")
    clip.data.materials.append(clip_mat)
    clip.parent = board
    clip.matrix_parent_inverse = Matrix.Identity(4)
    # Paper details
    if not check:
        # 3 navy text lines as thin boxes
        line_mat = make_felt_material("Clipboard_Line", "#101629")
        for i in range(3):
            y_offset = -0.06 + i * 0.04
            bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD',
                                            location=(0, 0.015, y_offset))
            line = bpy.context.active_object
            line.name = name + f"_Line{i}"
            line.scale = (0.18, 0.002, 0.015)
            bpy.ops.object.transform_apply(scale=True)
            line.data.materials.append(line_mat)
            line.parent = paper
            line.matrix_parent_inverse = Matrix.Identity(4)
    else:
        # Green check mark: two thick boxes forming a tick
        check_mat = make_felt_material("Clipboard_Check", "#2DBE60")
        # Vertical bar
        bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD',
                                        location=(-0.04, 0.015, -0.02))
        bar1 = bpy.context.active_object
        bar1.name = name + "_CheckBar1"
        bar1.scale = (0.04, 0.002, 0.12)
        bpy.ops.object.transform_apply(scale=True)
        bar1.data.materials.append(check_mat)
        bar1.parent = paper
        bar1.matrix_parent_inverse = Matrix.Identity(4)
        # Diagonal bar
        bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD',
                                        location=(0.04, 0.015, -0.05))
        bar2 = bpy.context.active_object
        bar2.name = name + "_CheckBar2"
        bar2.scale = (0.1, 0.002, 0.04)
        bar2.rotation_euler = Euler((0, 0, radians(-45)), 'XYZ')
        bpy.ops.object.transform_apply(rotation=True, scale=True)
        bar2.data.materials.append(check_mat)
        bar2.parent = paper
        bar2.matrix_parent_inverse = Matrix.Identity(4)
    return board

def create_pen():
    name = "StkProp_Pen"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Body
    bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.18, enter_editmode=False, align='WORLD', location=(0,0,0))
    pen = bpy.context.active_object
    pen.name = name
    pen_mat = make_felt_material("Pen_Body", "#1F3FB8")
    pen.data.materials.append(pen_mat)
    # Cap
    bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=0.04, enter_editmode=False, align='WORLD', location=(0,0,0.1))
    cap = bpy.context.active_object
    cap.name = name + "_Cap"
    cap_mat = make_metallic_material("Pen_Cap", "#D5B268", metallic=0.7, roughness=0.2)
    cap.data.materials.append(cap_mat)
    cap.parent = pen
    cap.matrix_parent_inverse = Matrix.Identity(4)
    # Tip
    bpy.ops.mesh.primitive_cone_add(radius1=0.012, depth=0.03, enter_editmode=False, align='WORLD', location=(0,0,-0.105))
    tip = bpy.context.active_object
    tip.name = name + "_Tip"
    tip_mat = make_metallic_material("Pen_Tip", "#101629")
    tip.data.materials.append(tip_mat)
    tip.parent = pen
    tip.matrix_parent_inverse = Matrix.Identity(4)
    return pen

def create_parcel():
    name = "StkProp_Parcel"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Box
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0,0))
    parcel = bpy.context.active_object
    parcel.name = name
    parcel.scale = (0.30, 0.22, 0.24)
    bpy.ops.object.transform_apply(scale=True)
    parcel_mat = make_felt_material("Parcel_Box", "#C89B63")
    parcel.data.materials.append(parcel_mat)
    # Tape strip
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0.111, 0))
    tape = bpy.context.active_object
    tape.name = name + "_Tape"
    tape.scale = (0.32, 0.005, 0.06)
    bpy.ops.object.transform_apply(scale=True)
    tape_mat = make_felt_material("Parcel_Tape", "#E8D5A8")
    tape.data.materials.append(tape_mat)
    tape.parent = parcel
    tape.matrix_parent_inverse = Matrix.Identity(4)
    # Label
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0.111, 0.08))
    label = bpy.context.active_object
    label.name = name + "_Label"
    label.scale = (0.1, 0.07, 1)
    bpy.ops.object.transform_apply(scale=True)
    label_mat = make_felt_material("Parcel_Label", "#F4F2EE")
    label.data.materials.append(label_mat)
    label.parent = parcel
    label.matrix_parent_inverse = Matrix.Identity(4)
    return parcel

def create_mug():
    name = "StkProp_Mug"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Mug body
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.12, enter_editmode=False, align='WORLD', location=(0,0,0))
    mug = bpy.context.active_object
    mug.name = name
    mug_mat = make_felt_material("Mug_Body", "#F4F2EE")
    mug.data.materials.append(mug_mat)
    # Coffee
    bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=0.005, enter_editmode=False, align='WORLD', location=(0,0,0.06))
    coffee = bpy.context.active_object
    coffee.name = name + "_Coffee"
    coffee_mat = make_felt_material("Mug_Coffee", "#4A2C1A")
    coffee.data.materials.append(coffee_mat)
    coffee.parent = mug
    coffee.matrix_parent_inverse = Matrix.Identity(4)
    # Handle (torus segment)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.01, major_segments=16, minor_segments=8,
                                     abso_major_rad=1.25, abso_minor_rad=0.5,
                                     enter_editmode=False, align='WORLD', location=(0.07,0,0))
    handle = bpy.context.active_object
    handle.name = name + "_Handle"
    handle_mat = make_felt_material("Mug_Handle", "#F4F2EE")
    handle.data.materials.append(handle_mat)
    # Rotate and position handle
    handle.rotation_euler = Euler((0, radians(90), 0), 'XYZ')
    handle.parent = mug
    handle.matrix_parent_inverse = Matrix.Identity(4)
    # Steam strands (3 curved tubes)
    steam_mat = make_felt_material("Mug_Steam", "#FFFFFF")
    for i in range(3):
        bpy.ops.curve.primitive_bezier_curve_add(enter_editmode=False, align='WORLD', location=(0,0,0.13))
        steam = bpy.context.active_object
        steam.name = name + f"_Steam{i}"
        steam.data.dimensions = '3D'
        steam.data.bevel_depth = 0.005
        steam.data.bevel_resolution = 4
        steam.data.resolution_u = 12
        # Set curve points to wavy shape
        curve = steam.data
        spline = curve.splines[0]
        # Move points
        points = spline.bezier_points
        points[0].co = (-0.02 + i*0.02, 0, 0.13)
        points[0].handle_right_type = 'AUTO'
        points[1].co = (0.02 + i*0.02, 0, 0.18)
        points[1].handle_left_type = 'AUTO'
        # Slight tilt
        steam.rotation_euler = Euler((0, 0, radians(10 + i*5)), 'XYZ')
        steam.data.materials.append(steam_mat)
        steam.parent = mug
        steam.matrix_parent_inverse = Matrix.Identity(4)
    return mug

def create_sun():
    name = "StkProp_Sun"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.13, enter_editmode=False, align='WORLD', location=(0,0,0))
    sun = bpy.context.active_object
    sun.name = name
    sun_mat = make_felt_material("Sun_Body", "#FFC93C")
    sun.data.materials.append(sun_mat)
    # Rays (cones)
    ray_mat = make_felt_material("Sun_Ray", "#FFB020")
    for i in range(10):
        angle = i * (2*pi/10)
        bpy.ops.mesh.primitive_cone_add(radius1=0.03, depth=0.1, enter_editmode=False,
                                        align='WORLD', location=(0.13*math.cos(angle), 0.13*math.sin(angle), 0))
        ray = bpy.context.active_object
        ray.name = name + f"_Ray{i}"
        ray.rotation_euler = Euler((radians(90), 0, angle), 'XYZ')
        ray.data.materials.append(ray_mat)
        ray.parent = sun
        ray.matrix_parent_inverse = Matrix.Identity(4)
    # Smile (arc)
    bpy.ops.curve.primitive_bezier_circle_add(radius=0.04, enter_editmode=False, align='WORLD', location=(0, -0.03, -0.05))
    smile = bpy.context.active_object
    smile.name = name + "_Smile"
    smile.data.dimensions = '2D'
    smile.data.bevel_depth = 0.003
    smile.data.bevel_resolution = 2
    smile.data.resolution_u = 12
    smile.rotation_euler = Euler((radians(90), 0, 0), 'XYZ')  # face forward
    smile_mat = make_felt_material("Sun_Smile", "#000000")
    smile.data.materials.append(smile_mat)
    smile.parent = sun
    smile.matrix_parent_inverse = Matrix.Identity(4)
    return sun

def create_magnifier():
    name = "StkProp_Magnifier"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Ring (torus)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.09, minor_radius=0.016, major_segments=32, minor_segments=12,
                                     enter_editmode=False, align='WORLD', location=(0,0,0))
    ring = bpy.context.active_object
    ring.name = name + "_Ring"
    ring_mat = make_metallic_material("Magnifier_Ring", "#D5B268")
    ring.data.materials.append(ring_mat)
    # Glass disc
    bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.004, enter_editmode=False, align='WORLD', location=(0,0,0))
    glass = bpy.context.active_object
    glass.name = name + "_Glass"
    glass_mat = make_transmissive_material("Magnifier_Glass", "#CFEFFF")
    glass.data.materials.append(glass_mat)
    glass.parent = ring
    glass.matrix_parent_inverse = Matrix.Identity(4)
    # Handle
    bpy.ops.mesh.primitive_cylinder_add(radius=0.018, depth=0.16, enter_editmode=False, align='WORLD', location=(0,0,-0.13))
    handle = bpy.context.active_object
    handle.name = name + "_Handle"
    handle_mat = make_felt_material("Magnifier_Handle", "#101629")
    handle.data.materials.append(handle_mat)
    handle.parent = ring
    handle.matrix_parent_inverse = Matrix.Identity(4)
    # Group all under one root
    bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=(0,0,0))
    root = bpy.context.active_object
    root.name = name
    ring.parent = root
    ring.matrix_parent_inverse = Matrix.Identity(4)
    handle.parent = root
    handle.matrix_parent_inverse = Matrix.Identity(4)
    glass.parent = ring
    glass.matrix_parent_inverse = Matrix.Identity(4)
    return root

def create_question():
    name = "StkProp_Question"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Create text curve
    text_data = bpy.data.curves.new(name + "_Font", type='FONT')
    text_data.body = "?"
    text_data.size = 0.45
    text_data.extrude = 0.03
    text_data.bevel_depth = 0.01
    text_data.align_x = 'CENTER'
    text_data.align_y = 'CENTER'
    text_obj = bpy.data.objects.new(name + "_Text", text_data)
    bpy.context.collection.objects.link(text_obj)
    # Convert to mesh
    bpy.context.view_layer.objects.active = text_obj
    bpy.ops.object.convert(target='MESH')
    text_obj.name = name
    mat = make_metallic_material("Question_Gold", "#D5B268", metallic=0.8, roughness=0.1)
    text_obj.data.materials.append(mat)
    return text_obj

def create_desk():
    name = "StkProp_Desk"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Top
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0.72,0))
    top = bpy.context.active_object
    top.name = name + "_Top"
    top.scale = (1.2, 0.55, 0.06)
    bpy.ops.object.transform_apply(scale=True)
    top_mat = make_felt_material("Desk_Top", "#C89B63")
    top.data.materials.append(top_mat)
    # Legs
    leg_mat = make_felt_material("Desk_Leg", "#8A5A2B")
    for x in [-0.55, 0.55]:
        for z in [-0.25, 0.25]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.72, enter_editmode=False,
                                                align='WORLD', location=(x, 0, z))
            leg = bpy.context.active_object
            leg.name = name + f"_Leg{x}_{z}"
            leg.data.materials.append(leg_mat)
            leg.parent = top
            leg.matrix_parent_inverse = Matrix.Identity(4)
    # Create empty root
    bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=(0,0,0))
    root = bpy.context.active_object
    root.name = name
    top.parent = root
    top.matrix_parent_inverse = Matrix.Identity(4)
    return root

def create_laptop():
    name = "StkProp_Laptop"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Base
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0,0))
    base = bpy.context.active_object
    base.name = name + "_Base"
    base.scale = (0.36, 0.25, 0.02)
    bpy.ops.object.transform_apply(scale=True)
    base_mat = make_felt_material("Laptop_Base", "#3A3F4A")
    base.data.materials.append(base_mat)
    # Screen
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0.12, -0.02))
    screen = bpy.context.active_object
    screen.name = name + "_Screen"
    screen.scale = (0.36, 0.24, 0.02)
    bpy.ops.object.transform_apply(scale=True)
    screen.rotation_euler = Euler((radians(105), 0, 0), 'XYZ')
    # Position relative to base: hinge at back edge
    # After rotation, screen is tilted back; need to adjust location
    screen.location = (0, 0.10, -0.02)
    screen_mat = make_felt_material("Laptop_Screen", "#9FD3FF")
    screen.data.materials.append(screen_mat)
    screen.parent = base
    screen.matrix_parent_inverse = Matrix.Identity(4)
    # Gold circle on lid back
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.005, enter_editmode=False,
                                        align='WORLD', location=(0, -0.12, -0.02))
    circle = bpy.context.active_object
    circle.name = name + "_Circle"
    circle_mat = make_metallic_material("Laptop_Circle", "#D5B268")
    circle.data.materials.append(circle_mat)
    circle.parent = screen
    circle.matrix_parent_inverse = Matrix.Identity(4)
    # Root
    bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=(0,0,0))
    root = bpy.context.active_object
    root.name = name
    base.parent = root
    base.matrix_parent_inverse = Matrix.Identity(4)
    return root

def create_envelope():
    name = "StkProp_Envelope"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Body
    bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0,0))
    env = bpy.context.active_object
    env.name = name
    env.scale = (0.26, 0.02, 0.16)
    bpy.ops.object.transform_apply(scale=True)
    env_mat = make_felt_material("Envelope_Body", "#D8262E")
    env.data.materials.append(env_mat)
    # Flap triangle (use cone? we can use a plane with shape)
    bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.13, depth=0.01, enter_editmode=False,
                                    align='WORLD', location=(0, 0.01, 0))
    flap = bpy.context.active_object
    flap.name = name + "_Flap"
    flap.scale = (0.26, 0.16, 1)
    bpy.ops.object.transform_apply(scale=True)
    flap_mat = make_metallic_material("Envelope_Flap", "#D5B268")
    flap.data.materials.append(flap_mat)
    flap.parent = env
    flap.matrix_parent_inverse = Matrix.Identity(4)
    # Seal circle
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.005, enter_editmode=False,
                                        align='WORLD', location=(0, 0.015, 0.05))
    seal = bpy.context.active_object
    seal.name = name + "_Seal"
    seal_mat = make_metallic_material("Envelope_Seal", "#D5B268")
    seal.data.materials.append(seal_mat)
    seal.parent = env
    seal.matrix_parent_inverse = Matrix.Identity(4)
    return env

def create_confetti():
    name = "StkProp_Confetti"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    # Create a single mesh object with multiple materials
    # We'll build a bmesh and assign materials per face
    random.seed(7)
    meshes = []
    colors = ["#D5B268", "#EED295", "#E2324F", "#1F3FB8", "#FFFFFF"]
    materials = [make_felt_material(f"Confetti_{i}", c) for i, c in enumerate(colors)]
    # We'll create one object with many small pieces as separate mesh islands,
    # but easier: create a single mesh with vertices for many boxes/discs.
    # For simplicity, create each piece as a separate object, then join.
    pieces = []
    for _ in range(60):
        # random shape: box or disc
        if random.random() < 0.5:
            bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0,0,0))
            piece = bpy.context.active_object
            piece.scale = (0.03, 0.002, 0.012)
        else:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.002, enter_editmode=False,
                                                align='WORLD', location=(0,0,0))
            piece = bpy.context.active_object
        piece.name = name + f"_piece{len(pieces)}"
        # Random location
        x = random.uniform(-0.9, 0.9)
        y = random.uniform(-0.9, -0.3)
        z = random.uniform(1.1, 2.2)
        piece.location = (x, y, z)
        # Random rotation
        piece.rotation_euler = Euler((random.uniform(0, 2*pi), random.uniform(0, 2*pi), random.uniform(0, 2*pi)), 'XYZ')
        # Assign random material
        mat = random.choice(materials)
        piece.data.materials.append(mat)
        pieces.append(piece)
    # Join all pieces into one object
    bpy.ops.object.select_all(action='DESELECT')
    for p in pieces:
        p.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined

def create_stars():
    name = "StkProp_Stars"
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    star_mat = make_metallic_material("Star_Gold", "#D5B268", metallic=0.8, roughness=0.2)
    pieces = []
    for i in range(5):
        # Create 5-point star via bmesh
        bm = bmesh.new()
        # Star shape in XY plane, extruded later
        outer_radius = random.uniform(0.06, 0.1)
        inner_radius = outer_radius * 0.5
        verts = []
        for j in range(10):
            angle = j * (pi/5)
            r = outer_radius if j % 2 == 0 else inner_radius
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            verts.append(bm.verts.new((x, y, 0)))
        bm.faces.new(verts)
        # Extrude
        extrude_depth = 0.015
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        extruded = bmesh.ops.extrude_face_region(bm, geom=geom)
        verts_extruded = [v for v in extruded["geom"] if isinstance(v, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=(0, 0, extrude_depth), verts=verts_extruded)
        # Create mesh and object
        mesh = bpy.data.meshes.new(name + f"_mesh{i}")
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name + f"_piece{i}", mesh)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(star_mat)
        # Random position around head
        x = random.uniform(-0.3, 0.3)
        y = random.uniform(-0.5, -0.2)
        z = random.uniform(BODY_TOP-0.2, BODY_TOP+0.4)
        obj.location = (x, y, z)
        obj.rotation_euler = Euler((random.uniform(0, 2*pi), random.uniform(0, 2*pi), random.uniform(0, 2*pi)), 'XYZ')
        pieces.append(obj)
    # Join
    bpy.ops.object.select_all(action='DESELECT')
    for p in pieces:
        p.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined

# -------------------------------------------------------------------
# Create all props and store references
# -------------------------------------------------------------------
def create_all_props():
    props = {}
    props["Clipboard"] = create_clipboard(check=False)
    props["ClipboardCheck"] = create_clipboard(check=True)
    props["Pen"] = create_pen()
    props["Parcel"] = create_parcel()
    props["Mug"] = create_mug()
    props["Sun"] = create_sun()
    props["Magnifier"] = create_magnifier()
    props["Question"] = create_question()
    props["Desk"] = create_desk()
    props["Laptop"] = create_laptop()
    props["Envelope"] = create_envelope()
    props["Confetti"] = create_confetti()
    props["Stars"] = create_stars()
    # Hide all props initially
    for obj in props.values():
        obj.hide_render = True
        obj.hide_viewport = True
    return props

props_dict = create_all_props()

# -------------------------------------------------------------------
# Helper: show only specific props
# -------------------------------------------------------------------
def show_only_props(names):
    """Hide all props, then show the ones in names."""
    for obj in props_dict.values():
        obj.hide_render = True
        obj.hide_viewport = True
    for n in names:
        if n in props_dict:
            props_dict[n].hide_render = False
            props_dict[n].hide_viewport = False

# -------------------------------------------------------------------
# Face application
# -------------------------------------------------------------------
def apply_face(name, overrides=None):
    """Apply a face preset from face04.PRESETS, resetting first."""
    # Reset all Face_Ctrl properties to defaults (0)
    for prop_name in face04.CONTROLS:
        setattr(face_ctrl, prop_name, 0.0)
    # Apply preset
    preset = face04.PRESETS.get(name)
    if preset is None:
        print(f"Warning: face preset '{name}' not found")
        return
    for prop_name, value in preset.items():
        setattr(face_ctrl, prop_name, value)
    # Apply overrides
    if overrides:
        for prop_name, value in overrides.items():
            setattr(face_ctrl, prop_name, value)

# -------------------------------------------------------------------
# Pose helper functions
# -------------------------------------------------------------------
def reset_pose():
    rig05.reset_pose()
    # Hide all props
    show_only_props([])

def pose_wave_r():
    # Leave R arm in FK (modelled raised wave) + apply hand pose
    rig05.apply_hand_pose("R", "open_wave")

def pose_thumbs_up_r():
    rig05.pose_hand(rig, "R", (-0.9, -0.28, SHOULDER_Z+0.12),
                    (-0.72, 0, 0.70), (0, -1, 0), 1.35)
    rig05.apply_hand_pose("R", "thumbs_up")

def pose_thumbs_up_l():
    rig05.pose_hand(rig, "L", (0.9, -0.28, SHOULDER_Z+0.12),
                    (0.72, 0, 0.70), (0, -1, 0), 1.35)
    rig05.apply_hand_pose("L", "thumbs_up")

def pose_ok_r():
    rig05.pose_hand(rig, "R", (-0.88, -0.28, SHOULDER_Z+0.22),
                    (0, 0, 1), (0, -1, 0), 1.35)
    rig05.apply_hand_pose("R", "ok_sign")

def pose_palm_out_r():
    rig05.pose_hand(rig, "R", (-0.62, -0.62, SHOULDER_Z+0.12),
                    (0, 0, 1), (0, -1, 0), 1.4)
    rig05.apply_hand_pose("R", "open_wave")

def pose_rest_l():
    rig05.pose_hand(rig, "L", (0.72, -0.2, HIP_Z+0.06),
                    (0, 0, -1), (-1, 0, 0))
    rig05.apply_hand_pose("L", "hold")

def pose_hands_together():
    rig05.pose_hand(rig, "R", (-0.07, -0.66, HIP_Z+0.2),
                    (0, -0.15, 1), (1, 0, 0))
    rig05.pose_hand(rig, "L", (0.07, -0.66, HIP_Z+0.2),
                    (0, -0.15, 1), (-1, 0, 0))
    rig05.apply_hand_pose("R", "open_wave", spread=0)
    rig05.apply_hand_pose("L", "open_wave", spread=0)
    rig["lean_fwd"] = 0.35

def pose_hold_in_front_r():
    rig05.pose_hand(rig, "R", (-0.32, -0.72, SHOULDER_Z-0.05),
                    (0.3, 0, 1), (1, 0, 0))
    rig05.apply_hand_pose("R", "hold")

def pose_hold_in_front_l():
    rig05.pose_hand(rig, "L", (0.32, -0.72, SHOULDER_Z-0.05),
                    (-0.3, 0, 1), (-1, 0, 0))
    rig05.apply_hand_pose("L", "hold")

def pose_two_hand_hold():
    rig05.pose_hand(rig, "R", (-0.2, -0.72, HIP_Z+0.25),
                    (0, -0.2, 1), (1, 0, 0))
    rig05.pose_hand(rig, "L", (0.2, -0.72, HIP_Z+0.25),
                    (0, -0.2, 1), (-1, 0, 0))
    rig05.apply_hand_pose("R", "hold")
    rig05.apply_hand_pose("L", "hold")

def pose_arms_up():
    rig05.pose_hand(rig, "R", (-0.88, -0.15, BODY_TOP+0.22),
                    (-0.3, 0, 1), (0, -1, 0))
    rig05.pose_hand(rig, "L", (0.88, -0.15, BODY_TOP+0.22),
                    (0.3, 0, 1), (0, -1, 0))
    rig05.apply_hand_pose("R", "open_wave")
    rig05.apply_hand_pose("L", "open_wave")

def pose_shrug():
    rig05.pose_hand(rig, "R", (-0.82, -0.42, HIP_Z+0.18),
                    (-1, -0.3, 0.2), (0, 0, 1))
    rig05.pose_hand(rig, "L", (0.82, -0.42, HIP_Z+0.18),
                    (1, -0.3, 0.2), (0, 0, 1))
    rig05.apply_hand_pose("R", "open_wave", spread=0.5)
    rig05.apply_hand_pose("L", "open_wave", spread=0.5)
    rig["lid_tilt_y"] = 0.3

def pose_typing():
    rig05.pose_hand(rig, "R", (-0.18, -0.86, 0.80),
                    (0.1, -1, 0), (0, 0, -1))
    rig05.pose_hand(rig, "L", (0.18, -0.86, 0.80),
                    (-0.1, -1, 0), (0, 0, -1))
    rig05.apply_hand_pose("R", "hold")
    rig05.apply_hand_pose("L", "hold")

def pose_running():
    rig["lean_fwd"] = 0.3
    rig05.set_bone_world_location(rig, "IK_foot.R", (-0.2, -0.3, 0.14))
    rig05.set_bone_world_location(rig, "IK_foot.L", (0.2, 0.25, 0.0))
    rig["foot_roll.L"] = 0.4

# -------------------------------------------------------------------
# Sticker definitions
# -------------------------------------------------------------------
STICKERS = [
    {
        "num": 1,
        "slug": "noted",
        "caption": "NOTED WITH THANKS",
        "face": "Grateful",
        "overrides": {},
        "props": ["Clipboard", "Pen"],
        "pose": lambda: sticker1_pose(),
    },
    {
        "num": 2,
        "slug": "received",
        "caption": "RECEIVED!",
        "face": "Happy",
        "overrides": {},
        "props": ["Parcel"],
        "pose": lambda: sticker2_pose(),
    },
    {
        "num": 3,
        "slug": "thank_you",
        "caption": "អរគុណ|THANK YOU",
        "face": "Grateful",
        "overrides": {},
        "props": [],
        "pose": lambda: pose_hands_together(),
    },
    {
        "num": 4,
        "slug": "hello",
        "caption": "HELLO!",
        "face": "Happy",
        "overrides": {"eye_wide": 0.2},
        "props": [],
        "pose": lambda: (pose_wave_r(), pose_rest_l()),
    },
    {
        "num": 5,
        "slug": "okay",
        "caption": "OKAY!",
        "face": "Wink",
        "overrides": {},
        "props": [],
        "pose": lambda: (pose_ok_r(), pose_rest_l()),
    },
    {
        "num": 6,
        "slug": "good_morning",
        "caption": "GOOD MORNING",
        "face": "Sleepy",
        "overrides": {"m_small_smile": 0.8, "m_pout": 0},
        "props": ["Mug", "Sun"],
        "pose": lambda: sticker6_pose(),
    },
    {
        "num": 7,
        "slug": "info_inquiry",
        "caption": "INFORMATION INQUIRY",
        "face": "Thinking",
        "overrides": {},
        "props": ["Magnifier", "Question"],
        "pose": lambda: sticker7_pose(),
    },
    {
        "num": 8,
        "slug": "in_meeting",
        "caption": "IN MEETING",
        "face": "Determined",
        "overrides": {},
        "props": ["Desk", "Laptop"],
        "pose": lambda: sticker8_pose(),
    },
    {
        "num": 9,
        "slug": "yes",
        "caption": "ចាស!",
        "face": "Proud",
        "overrides": {},
        "props": [],
        "pose": lambda: (pose_thumbs_up_r(), pose_rest_l()),
    },
    {
        "num": 10,
        "slug": "paid",
        "caption": "PAID!",
        "face": "Excited",
        "overrides": {},
        "props": ["ClipboardCheck", "Confetti"],
        "pose": lambda: sticker10_pose(),
    },
    {
        "num": 11,
        "slug": "please_wait",
        "caption": "PLEASE WAIT!",
        "face": "Calm",
        "overrides": {},
        "props": [],
        "pose": lambda: (pose_palm_out_r(), pose_rest_l()),
    },
    {
        "num": 12,
        "slug": "good_afternoon",
        "caption": "GOOD AFTERNOON",
        "face": "Happy",
        "overrides": {},
        "props": ["Sun"],
        "pose": lambda: sticker12_pose(),
    },
    {
        "num": 13,
        "slug": "sorry",
        "caption": "សុំទោស|SORRY",
        "face": "Embarrassed",
        "overrides": {},
        "props": [],
        "pose": lambda: sticker13_pose(),
    },
    {
        "num": 14,
        "slug": "on_the_way",
        "caption": "កំពុងដឹកជញ្ជូន|ON THE WAY",
        "face": "Determined",
        "overrides": {},
        "props": ["Parcel"],
        "pose": lambda: sticker14_pose(),
    },
    {
        "num": 15,
        "slug": "order_confirmed",
        "caption": "បានបញ្ជាក់ការកុម្ម៉ង់|ORDER CONFIRMED",
        "face": "Proud",
        "overrides": {},
        "props": ["ClipboardCheck"],
        "pose": lambda: sticker15_pose(),
    },
    {
        "num": 16,
        "slug": "out_of_stock",
        "caption": "អស់ស្តុក|OUT OF STOCK",
        "face": "Worried",
        "overrides": {},
        "props": [],
        "pose": lambda: pose_shrug(),
    },
    {
        "num": 17,
        "slug": "great_job",
        "caption": "ល្អណាស់|GREAT JOB!",
        "face": "Big laugh",
        "overrides": {},
        "props": [],
        "pose": lambda: (pose_thumbs_up_r(), pose_thumbs_up_l()),
    },
    {
        "num": 18,
        "slug": "see_you_tomorrow",
        "caption": "ជួបគ្នាថ្ងៃស្អែក|SEE YOU TOMORROW",
        "face": "Calm",
        "overrides": {},
        "props": [],
        "pose": lambda: (pose_wave_r(), pose_rest_l()),
    },
    {
        "num": 19,
        "slug": "congratulations",
        "caption": "សូមអបអរសាទរ|CONGRATULATIONS",
        "face": "Excited",
        "overrides": {},
        "props": ["Confetti", "Stars"],
        "pose": lambda: sticker19_pose(),
    },
    {
        "num": 20,
        "slug": "happy_new_year",
        "caption": "សួស្តីឆ្នាំថ្មី|HAPPY NEW YEAR",
        "face": "Love",
        "overrides": {},
        "props": ["Envelope", "Confetti"],
        "pose": lambda: sticker20_pose(),
    },
]

# -------------------------------------------------------------------
# Sticker-specific pose functions that need prop placement
# -------------------------------------------------------------------
def sticker1_pose():
    # L holds Clipboard in front (hold-in-front mirrored to L)
    pose_hold_in_front_l()
    # R holds Pen near clipboard
    rig05.pose_hand(rig, "R", (-0.05, -0.75, SHOULDER_Z-0.08),
                    (0.6, 0, 0.8), (0.4, -0.6, 0))
    rig05.apply_hand_pose("R", "hold")
    # Position props: clipboard at L socket, pen at R socket
    view_layer.update()
    sock_l = bpy.data.objects["Socket_Hand.L"]
    sock_r = bpy.data.objects["Socket_Hand.R"]
    clipboard = props_dict["Clipboard"]
    pen = props_dict["Pen"]
    # Clipboard: placed in front of L hand, slightly offset
    l_world = sock_l.matrix_world
    clipboard.matrix_world = Matrix.Translation(l_world.translation + Vector((0, 0.15, 0.05))) @ \
                             l_world.to_quaternion().to_matrix().to_4x4()
    # Pen: in R hand, point toward clipboard
    r_world = sock_r.matrix_world
    pen.matrix_world = Matrix.Translation(r_world.translation + Vector((0, 0.1, 0))) @ \
                       r_world.to_quaternion().to_matrix().to_4x4()

def sticker2_pose():
    # L holds Parcel in front (two-hand-hold position but only L)
    rig05.pose_hand(rig, "L", (0.07, -0.66, HIP_Z+0.2),
                    (0, -0.15, 1), (-1, 0, 0))
    rig05.apply_hand_pose("L", "hold")
    # R thumbs up
    pose_thumbs_up_r()
    # Parcel at L socket + offset
    view_layer.update()
    sock = bpy.data.objects["Socket_Hand.L"]
    parcel = props_dict["Parcel"]
    parcel.matrix_world = Matrix.Translation(sock.matrix_world.translation + Vector((0, -0.1, 0))) @ \
                          sock.matrix_world.to_quaternion().to_matrix().to_4x4()

def sticker6_pose():
    # R HOLD IN FRONT with Mug
    pose_hold_in_front_r()
    pose_rest_l()
    # Sun at (-0.75, 0.1, BODY_TOP+0.35)
    sun = props_dict["Sun"]
    sun.location = (-0.75, 0.1, BODY_TOP+0.35)
    sun.rotation_euler = Euler((0, radians(90), 0), 'XYZ')  # face camera
    # Mug in R hand
    view_layer.update()
    sock = bpy.data.objects["Socket_Hand.R"]
    mug = props_dict["Mug"]
    mug.matrix_world = Matrix.Translation(sock.matrix_world.translation + Vector((0, 0.12, 0))) @ \
                       sock.matrix_world.to_quaternion().to_matrix().to_4x4()

def sticker7_pose():
    # R holds Magnifier raised
    rig05.pose_hand(rig, "R", (-0.7, -0.45, SHOULDER_Z+0.3),
                    (0, 0, 1), (1, 0, 0))
    rig05.apply_hand_pose("R", "hold")
    pose_rest_l()
    # Magnifier ring centred 0.12 above the socket facing camera
    view_layer.update()
    sock = bpy.data.objects["Socket_Hand.R"]
    mag = props_dict["Magnifier"]
    mag.matrix_world = Matrix.Translation(sock.matrix_world.translation + Vector((0, 0.12, 0))) @ \
                       sock.matrix_world.to_quaternion().to_matrix().to_4x4()
    # Question at (0.62, -0.2, BODY_TOP+0.25)
    q = props_dict["Question"]
    q.location = (0.62, -0.2, BODY_TOP+0.25)
    q.rotation_euler = Euler((0, radians(90), 0), 'XYZ')  # face camera

def sticker8_pose():
    # Desk at (0,-0.85,0) + Laptop on desk at (0,-0.95,0.75)
    desk = props_dict["Desk"]
    desk.location = (0, -0.85, 0)
    laptop = props_dict["Laptop"]
    laptop.location = (0, -0.95, 0.75)
    # Screen facing character (i.e., screen should face +Y because character is at origin)
    laptop.rotation_euler = Euler((radians(105), 0, 0), 'XYZ')
    pose_typing()

def sticker10_pose():
    # R ARMS UP holding ClipboardCheck above head
    rig05.pose_hand(rig, "R", (-0.88, -0.15, BODY_TOP+0.22),
                    (-0.3, 0, 1), (0, -1, 0))
    rig05.pose_hand(rig, "L", (0.88, -0.15, BODY_TOP+0.22),
                    (0.3, 0, 1), (0, -1, 0))
    rig05.apply_hand_pose("R", "open_wave")
    rig05.apply_hand_pose("L", "open_wave")
    # ClipboardCheck at R socket + (0,0,0.18)
    view_layer.update()
    sock = bpy.data.objects["Socket_Hand.R"]
    clip = props_dict["ClipboardCheck"]
    clip.matrix_world = Matrix.Translation(sock.matrix_world.translation + Vector((0, 0, 0.18))) @ \
                        sock.matrix_world.to_quaternion().to_matrix().to_4x4()

def sticker12_pose():
    pose_wave_r()
    pose_rest_l()
    sun = props_dict["Sun"]
    sun.location = (0.8, 0.1, BODY_TOP+0.3)
    sun.rotation_euler = Euler((0, radians(90), 0), 'XYZ')

def sticker13_pose():
    pose_hands_together()
    rig["lid_tilt_y"] = 0.4
    rig["lean_side"] = -0.2

def sticker14_pose():
    pose_two_hand_hold()
    pose_running()
    # Parcel centred between sockets
    view_layer.update()
    sock_r = bpy.data.objects["Socket_Hand.R"]
    sock_l = bpy.data.objects["Socket_Hand.L"]
    mid = (sock_r.matrix_world.translation + sock_l.matrix_world.translation) / 2
    parcel = props_dict["Parcel"]
    parcel.matrix_world = Matrix.Translation(mid) @ \
                          Matrix.Rotation(radians(90), 4, 'Z').to_4x4()

def sticker15_pose():
    # L holds ClipboardCheck in front (mirrored hold-in-front)
    pose_hold_in_front_l()
    # R point at it
    rig05.apply_hand_pose("R", "point")
    rig05.pose_hand(rig, "R", (-0.12, -0.75, SHOULDER_Z+0.0),
                    (1, -0.2, 0.2), (0, -1, 0))
    # Clipboard at L socket
    view_layer.update()
    sock = bpy.data.objects["Socket_Hand.L"]
    clip = props_dict["ClipboardCheck"]
    clip.matrix_world = Matrix.Translation(sock.matrix_world.translation + Vector((0, 0.15, 0.05))) @ \
                        sock.matrix_world.to_quaternion().to_matrix().to_4x4()

def sticker19_pose():
    pose_arms_up()
    # Lift root
    rig05.set_bone_world_location(rig, "root", (0, 0, 0.1))
    # Confetti and Stars are already scattered; no extra placement needed

def sticker20_pose():
    pose_two_hand_hold()
    # Envelope between hands
    view_layer.update()
    sock_r = bpy.data.objects["Socket_Hand.R"]
    sock_l = bpy.data.objects["Socket_Hand.L"]
    mid = (sock_r.matrix_world.translation + sock_l.matrix_world.translation) / 2
    env = props_dict["Envelope"]
    env.matrix_world = Matrix.Translation(mid) @ \
                       Matrix.Rotation(radians(90), 4, 'Z').to_4x4()

# -------------------------------------------------------------------
# Rendering functions
# -------------------------------------------------------------------
def setup_camera_and_render(sticker):
    # Auto-frame: compute bbox of visible objects
    visible_objs = []
    for obj in scene.objects:
        if obj.hide_render:
            continue
        if obj.type != 'MESH':
            continue
        # Check if part of character or StkProp
        is_char = False
        parent = obj.parent
        while parent:
            if parent.name == "Mascot_Root":
                is_char = True
                break
            parent = parent.parent
        if is_char or obj.name.startswith("StkProp_"):
            visible_objs.append(obj)
    if not visible_objs:
        print("Warning: no visible objects for bounding box")
        return
    # Compute world bbox corners
    min_corner = Vector((float('inf'), float('inf'), float('inf')))
    max_corner = Vector((-float('inf'), -float('inf'), -float('inf')))
    for obj in visible_objs:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            min_corner.x = min(min_corner.x, world_corner.x)
            min_corner.y = min(min_corner.y, world_corner.y)
            min_corner.z = min(min_corner.z, world_corner.z)
            max_corner.x = max(max_corner.x, world_corner.x)
            max_corner.y = max(max_corner.y, world_corner.y)
            max_corner.z = max(max_corner.z, world_corner.z)
    center = (min_corner + max_corner) / 2
    size = max_corner - min_corner
    max_extent = max(size.x, size.y, size.z)
    # Camera settings
    cam = bpy.data.objects["Camera"]
    cam.data.lens = 50
    # Direction from target toward (-0.17, -1.0, 0.05) normalized
    direction = Vector((-0.17, -1.0, 0.05)).normalized()
    # Distance calculation
    fov = cam.data.angle  # radians
    dist = (0.5 * max_extent / 0.88) / tan(fov / 2) + 0.5 * size.y  # depth ~ y extent
    cam_loc = center + direction * dist
    cam.location = cam_loc
    # Point camera at center
    look_at = center - cam_loc
    rot_quat = look_at.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()

def render_sticker(sticker, output_path):
    reset_pose()
    show_only_props(sticker["props"])
    apply_face(sticker["face"], sticker.get("overrides", {}))
    sticker["pose"]()
    # Update view layer to ensure matrices are current
    view_layer.update()
    # Setup camera
    setup_camera_and_render(sticker)
    # Render settings
    scene.render.film_transparent = True
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.cycles.samples = samples
    # Hide backdrop and ground
    for obj_name in ["Backdrop", "Ground"]:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            obj.hide_render = True
    # Render
    bpy.ops.render.render(write_still=True)
    # Save image
    image = bpy.data.images['Render Result']
    image.save_render(filepath=output_path)
    # Print info
    print(f"[06] {sticker['num']:02d}_{sticker['slug']} rendered")

# -------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------
def main():
    # Prepare output directories
    raw_dir = os.path.join(project_root, "exports", "stickers", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    # Write captions.json
    captions = {}
    for s in STICKERS:
        captions[f"{s['num']:02d}_{s['slug']}"] = s["caption"]
    captions_path = os.path.join(project_root, "exports", "stickers", "captions.json")
    with open(captions_path, 'w', encoding='utf-8') as f:
        json.dump(captions, f, ensure_ascii=False, indent=2)
    # Render stickers
    for sticker in STICKERS:
        if only_list is not None and sticker["num"] not in only_list:
            continue
        output_file = os.path.join(raw_dir, f"{sticker['num']:02d}_{sticker['slug']}.png")
        render_sticker(sticker, output_file)
    # Save blend file
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(project_root, "blend", "mascot_stickers.blend"))

if __name__ == "__main__":
    main()
```