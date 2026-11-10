"""
05_rig.py - Full body rig for the Synergist mascot.

Adds an armature, vertex weights, constraints/drivers, eye target hook,
saves mascot_rig.blend and renders test poses.

Run:
  blender.exe -b blend/mascot_face.blend --python scripts/05_rig.py -- <project_root> [--poses wave,thumbs_up,ok_sign,jump] [--res 1024] [--samples 64] [--no-render]
"""
import argparse
import importlib.util
import math
import os
import sys
import time

import bpy
from mathutils import Vector, Matrix

# ----------------------------------------------------------------------
# Load constants and helpers from 02_model.py (import only, no execution)
# ----------------------------------------------------------------------
def load_model02():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("model02", os.path.join(script_dir, "02_model.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

model02 = load_model02()

BODY_R = model02.BODY_R
BODY_TOP = model02.BODY_TOP
BODY_BOTTOM = model02.BODY_BOTTOM
BODY_H = model02.BODY_H
SHOE_H = model02.SHOE_H
SHOE_L = model02.SHOE_L
SHOE_FORWARD = model02.SHOE_FORWARD
LEG_X = model02.LEG_X
ARM_WAVE_POINTS = model02.ARM_WAVE_POINTS
ARM_REST_POINTS = model02.ARM_REST_POINTS
catmull_rom = model02.catmull_rom

FACE_X = 0.03
EYE_Z = (BODY_TOP - 0.29 * BODY_H) + 0.025 - 0.15

# Deform bone names
DEFORM_BONES = [
    "spine_lower", "spine_upper", "lid",
    "upper_arm.L", "forearm.L", "hand.L",
    "index_1.L", "index_2.L", "middle_1.L", "middle_2.L",
    "ring_1.L", "ring_2.L", "thumb_1.L", "thumb_2.L",
    "upper_arm.R", "forearm.R", "hand.R",
    "index_1.R", "index_2.R", "middle_1.R", "middle_2.R",
    "ring_1.R", "ring_2.R", "thumb_1.R", "thumb_2.R",
    "thigh.L", "shin.L", "foot.L",
    "thigh.R", "shin.R", "foot.R",
]

# ----------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------
def smoothstep(edge0, edge1, x):
    """Smoothstep function."""
    t = (x - edge0) / (edge1 - edge0)
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def add_driver(target, data_path, index, expression, variables, target_object=None):
    """Add a driver to a property. Variables are dicts: {'name': str, 'type': str, 'targets': [..]}.
    target_object is optional object to use for SINGLE_PROP variable target (if not provided, uses
    bpy.data.objects.get('Mascot_Rig'))."""
    if target_object is None:
        target_object = bpy.data.objects.get("Mascot_Rig")
    fc = target.driver_add(data_path, index) if index >= 0 else target.driver_add(data_path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    # Remove existing variables
    for v in list(drv.variables):
        drv.variables.remove(v)
    for var in variables:
        new_var = drv.variables.new()
        safe = var['name'].replace('.', '_')  # driver variables must be valid identifiers
        expression = expression.replace(var['name'], safe)
        new_var.name = safe
        new_var.type = var['type']
        for i, t in enumerate(var['targets']):
            if t['id_type'] == 'OBJECT':
                new_var.targets[i].id_type = 'OBJECT'
                new_var.targets[i].id = t['id']
                new_var.targets[i].data_path = t['data_path']
                if 'transform_space' in t:
                    new_var.targets[i].transform_space = t['transform_space']
            elif t['id_type'] == 'SINGLE_PROP':
                new_var.targets[i].id_type = 'SINGLE_PROP'
                new_var.targets[i].id = t['id']
                new_var.targets[i].data_path = t['data_path']
    drv.expression = expression
    return fc

# ----------------------------------------------------------------
# Build Armature
# ----------------------------------------------------------------
_EMPTY_POSITIONS = {}


def build_armature():
    """Create armature object, parent Mascot_Root, and build bones."""
    # Delete existing armature if any
    if "Mascot_Rig" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Mascot_Rig"], do_unlink=True)

    # Create armature object
    bpy.ops.object.armature_add(enter_editmode=False, location=(0, 0, 0))
    rig = bpy.context.active_object
    rig.name = "Mascot_Rig"
    rig.data.name = "Mascot_Rig"

    # Parent Mascot_Root to armature (keep transform)
    root_empty = bpy.data.objects.get("Mascot_Root")
    if root_empty:
        # Save world matrix
        mat_world = root_empty.matrix_world.copy()
        root_empty.parent = rig
        root_empty.matrix_parent_inverse = rig.matrix_world.inverted()
        root_empty.matrix_world = mat_world

    # Enter edit mode
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = rig.data.edit_bones
    for b in list(edit_bones):  # armature_add creates a default "Bone"
        edit_bones.remove(b)

    # --- Root ---
    root_bone = edit_bones.new("root")
    root_bone.head = (0, 0, 0)
    root_bone.tail = (0, -0.35, 0)
    root_bone.use_deform = False

    # --- Body ---
    body = edit_bones.new("body")
    body.head = (0, 0, BODY_BOTTOM)
    body.tail = (0, 0, BODY_BOTTOM + 0.2)
    body.parent = root_bone
    body.use_deform = False

    # --- Spine lower/upper ---
    spine_lower = edit_bones.new("spine_lower")
    spine_lower.head = (0, 0, BODY_BOTTOM)
    spine_lower.tail = (0, 0, BODY_BOTTOM + BODY_H * 0.5)
    spine_lower.parent = body

    spine_upper = edit_bones.new("spine_upper")
    spine_upper.head = spine_lower.tail
    spine_upper.tail = (0, 0, BODY_TOP - 0.05)
    spine_upper.parent = spine_lower
    spine_upper.use_connect = True

    lid = edit_bones.new("lid")
    lid.head = spine_upper.tail
    lid.tail = (0, 0, BODY_TOP + 0.12)
    lid.parent = spine_upper
    lid.use_connect = True

    # --- Arms ---
    for side, points in [("L", ARM_REST_POINTS), ("R", ARM_WAVE_POINTS)]:
        P = catmull_rom(points, 25)
        shoulder = P[0]
        wrist = P[-1]
        # Compute arc length and elbow point at half length
        total_len = 0.0
        lengths = []
        for i in range(len(P) - 1):
            seg_len = (P[i+1] - P[i]).length
            lengths.append(seg_len)
            total_len += seg_len
        half_len = total_len / 2.0
        acc = 0.0
        elbow = None
        for i, seg_len in enumerate(lengths):
            if acc + seg_len >= half_len:
                t = (half_len - acc) / seg_len
                elbow = P[i].lerp(P[i+1], t)
                break
            acc += seg_len
        if elbow is None:
            elbow = P[-2]

        # Hand direction
        hand_dir = (P[-1] - P[-2]).normalized()

        # Arm bones
        upper = edit_bones.new(f"upper_arm.{side}")
        upper.head = shoulder
        upper.tail = elbow
        upper.parent = spine_upper
        upper.bbone_segments = 10
        upper.bbone_easein = 1.0
        upper.bbone_easeout = 1.0

        forearm = edit_bones.new(f"forearm.{side}")
        forearm.head = elbow
        forearm.tail = wrist
        forearm.parent = upper
        forearm.use_connect = True
        forearm.bbone_segments = 10
        forearm.bbone_easein = 1.0
        forearm.bbone_easeout = 1.0

        hand = edit_bones.new(f"hand.{side}")
        hand.head = wrist
        hand.tail = wrist + hand_dir * 0.12
        hand.parent = forearm
        hand.use_connect = True

        # Roll alignment for arm/hand/finger bones: palm normal
        palm_normal = (0, -1, 0) if side == "R" else (-1, 0, 0)
        for bone in (upper, forearm, hand):
            bone.align_roll(palm_normal)

        # Finger bones (build after glove meshes exist? Actually we need to compute from meshes)
        # We'll do finger bones later after we have access to glove meshes, but we can compute now
        # using object data from scene (objects already exist). We'll compute here.
        for finger_name, bone_base in [
            ("Finger1", "index"),
            ("Finger2", "middle"),
            ("Finger3", "ring"),
            ("Thumb", "thumb")
        ]:
            side_name = "Left" if side == "L" else "Right"
            finger_obj = bpy.data.objects.get(f"Glove_{side_name}_{finger_name}")
            palm_obj = bpy.data.objects.get(f"Glove_{side_name}_Palm")
            if finger_obj and palm_obj:
                # Compute root/tip from vertices
                palm_center = sum((v.co for v in palm_obj.data.vertices), Vector((0,0,0))) / len(palm_obj.data.vertices)
                palm_center_world = palm_obj.matrix_world @ palm_center
                verts_world = [finger_obj.matrix_world @ v.co for v in finger_obj.data.vertices]
                # Sort by distance to palm center
                dists = [(v, (v - palm_center_world).length) for v in verts_world]
                dists.sort(key=lambda x: x[1])
                n = len(dists)
                n_root = max(1, int(n * 0.15))
                n_tip = max(1, int(n * 0.15))
                root_pts = [v for v, d in dists[:n_root]]
                tip_pts = [v for v, d in dists[-n_tip:]]
                root = sum(root_pts, Vector((0,0,0))) / n_root
                tip = sum(tip_pts, Vector((0,0,0))) / n_tip
                mid = (root + tip) / 2.0

                bone1 = edit_bones.new(f"{bone_base}_1.{side}")
                bone1.head = root
                bone1.tail = mid
                bone1.parent = hand
                bone1.align_roll(palm_normal)

                bone2 = edit_bones.new(f"{bone_base}_2.{side}")
                bone2.head = mid
                bone2.tail = tip
                bone2.parent = bone1
                bone2.use_connect = True
                bone2.align_roll(palm_normal)

        # IK control bones (not deform)
        ik_hand = edit_bones.new(f"IK_hand.{side}")
        ik_hand.head = wrist
        ik_hand.tail = wrist + hand_dir * 0.1
        ik_hand.parent = root_bone
        ik_hand.use_deform = False

        pole_arm = edit_bones.new(f"pole_arm.{side}")
        outward = (1, 0, 0) if side == "L" else (-1, 0, 0)
        pole_arm.head = elbow + Vector((outward[0]*0.35, 0.25, 0))
        pole_arm.tail = pole_arm.head + Vector((0, 0, 0.05))
        pole_arm.parent = root_bone
        pole_arm.use_deform = False

        # Prop socket empties
        socket_name = f"Socket_Hand.{side}"
        if socket_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[socket_name], do_unlink=True)
        socket = bpy.data.objects.new(socket_name, None)
        bpy.context.scene.collection.objects.link(socket)
        socket.parent = rig
        socket.parent_type = 'BONE'
        socket.parent_bone = f"hand.{side}"
        _EMPTY_POSITIONS[socket_name] = palm_center_world.copy()

    # --- Legs ---
    for side, x_sign in [("L", 1), ("R", -1)]:
        x_leg = x_sign * LEG_X
        x_shoe = x_sign * (LEG_X + 0.01)

        thigh = edit_bones.new(f"thigh.{side}")
        thigh.head = (x_leg, 0, BODY_BOTTOM + 0.03)
        thigh.tail = (x_leg, -0.006, (BODY_BOTTOM + SHOE_H) / 2 + 0.02)
        thigh.parent = body

        shin = edit_bones.new(f"shin.{side}")
        shin.head = thigh.tail
        shin.tail = (x_leg, 0, SHOE_H * 0.55)
        shin.parent = thigh
        shin.use_connect = True

        foot = edit_bones.new(f"foot.{side}")
        foot.head = shin.tail
        foot.tail = (x_shoe, -SHOE_FORWARD - SHOE_L * 0.35, SHOE_H * 0.35)
        foot.parent = None  # will be parented to foot_roll later
        foot.use_connect = False
        foot.use_deform = True

        # Reverse foot controls
        ik_foot = edit_bones.new(f"IK_foot.{side}")
        ik_foot.head = (x_shoe, 0.06, 0.0)
        ik_foot.tail = (x_shoe, -0.12, 0.0)
        ik_foot.parent = root_bone
        ik_foot.use_deform = False

        foot_roll = edit_bones.new(f"foot_roll.{side}")
        foot_roll.head = (x_shoe, -SHOE_FORWARD - SHOE_L * 0.5, 0.0)
        foot_roll.tail = foot_roll.head + Vector((0, 0, 0.06))
        foot_roll.parent = ik_foot
        foot_roll.use_deform = False

        ankle_target = edit_bones.new(f"ankle_target.{side}")
        ankle_target.head = (x_leg, 0, SHOE_H * 0.55)
        ankle_target.tail = ankle_target.head + Vector((0, 0, 0.05))
        ankle_target.parent = foot_roll
        ankle_target.use_deform = False

        pole_leg = edit_bones.new(f"pole_leg.{side}")
        pole_leg.head = (x_leg, -0.5, (BODY_BOTTOM + SHOE_H) / 2)
        pole_leg.tail = pole_leg.head + Vector((0, 0, 0.05))
        pole_leg.parent = root_bone
        pole_leg.use_deform = False

        # Parent foot to foot_roll
        foot.parent = foot_roll

    # --- Eye target empty (bone parent to spine_upper) ---
    if "Eye_Target" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Eye_Target"], do_unlink=True)
    eye_target = bpy.data.objects.new("Eye_Target", None)
    bpy.context.scene.collection.objects.link(eye_target)
    eye_target.empty_display_type = 'SPHERE'
    eye_target.empty_display_size = 0.05
    eye_target.parent = rig
    eye_target.parent_type = 'BONE'
    eye_target.parent_bone = "spine_upper"
    _EMPTY_POSITIONS["Eye_Target"] = Vector((FACE_X, -1.6, EYE_Z))

    # Exit edit mode, then put the bone-parented empties at their world positions
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    for name, pos in _EMPTY_POSITIONS.items():
        o = bpy.data.objects[name]
        o.matrix_world = Matrix.Translation(pos)
    return rig

# ----------------------------------------------------------------
# Add constraints, custom properties, drivers
# ----------------------------------------------------------------
def add_constraints_and_drivers(rig):
    """Add custom properties, constraints, and drivers."""
    # Custom properties on rig object
    defaults = {
        "ik_fk.L": 0.0,
        "ik_fk.R": 0.0,
        "foot_roll.L": 0.0,
        "foot_roll.R": 0.0,
        "squash": 0.0,
        "lean_fwd": 0.0,
        "lean_side": 0.0,
        "twist": 0.0,
        "lid_tilt_x": 0.0,
        "lid_tilt_y": 0.0,
        "curl_index.L": 0.0, "curl_middle.L": 0.0, "curl_ring.L": 0.0, "curl_thumb.L": 0.0,
        "spread.L": 0.0,
        "curl_index.R": 0.0, "curl_middle.R": 0.0, "curl_ring.R": 0.0, "curl_thumb.R": 0.0,
        "spread.R": 0.0,
        "use_eye_target": 0.0,
    }
    for prop, val in defaults.items():
        rig[prop] = val
        # Set UI limits
        if prop.startswith("ik_fk"):
            ui = rig.id_properties_ui(prop)
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
        elif prop.startswith("foot_roll"):
            ui = rig.id_properties_ui(prop)
            ui.update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0)
        elif prop == "squash":
            ui = rig.id_properties_ui(prop)
            ui.update(min=-0.5, max=0.5, soft_min=-0.5, soft_max=0.5)
        elif prop in ("lean_fwd", "lean_side", "twist", "lid_tilt_x", "lid_tilt_y"):
            ui = rig.id_properties_ui(prop)
            ui.update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0)
        elif prop.startswith("curl"):
            ui = rig.id_properties_ui(prop)
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
        elif prop.startswith("spread"):
            ui = rig.id_properties_ui(prop)
            ui.update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0)
        elif prop == "use_eye_target":
            ui = rig.id_properties_ui(prop)
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)

    pose_bones = rig.pose.bones

    # --- Arm IK ---
    for side in ("L", "R"):
        forearm = pose_bones[f"forearm.{side}"]
        hand = pose_bones[f"hand.{side}"]

        # IK constraint
        ik = forearm.constraints.new('IK')
        ik.name = "ArmIK"
        ik.target = rig
        ik.subtarget = f"IK_hand.{side}"
        ik.pole_target = rig
        ik.pole_subtarget = f"pole_arm.{side}"
        ik.pole_angle = math.radians(-90)
        ik.chain_count = 2
        # Driver on influence
        add_driver(ik, "influence", -1,
                   f'ik_fk.{side}',
                   [{'name': f'ik_fk.{side}', 'type': 'SINGLE_PROP',
                     'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["ik_fk.{side}"]'}]}],
                   target_object=rig)

        # Copy rotation on hand
        cr = hand.constraints.new('COPY_ROTATION')
        cr.name = "HandCopyRot"
        cr.target = rig
        cr.subtarget = f"IK_hand.{side}"
        cr.target_space = 'WORLD'
        cr.owner_space = 'WORLD'
        add_driver(cr, "influence", -1,
                   f'ik_fk.{side}',
                   [{'name': f'ik_fk.{side}', 'type': 'SINGLE_PROP',
                     'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["ik_fk.{side}"]'}]}],
                   target_object=rig)

    # --- Leg IK ---
    for side in ("L", "R"):
        shin = pose_bones[f"shin.{side}"]
        ik = shin.constraints.new('IK')
        ik.name = "LegIK"
        ik.target = rig
        ik.subtarget = f"ankle_target.{side}"
        ik.pole_target = rig
        ik.pole_subtarget = f"pole_leg.{side}"
        ik.pole_angle = math.radians(-90)
        ik.chain_count = 2

    # --- Foot roll driver ---
    for side in ("L", "R"):
        foot_roll_bone = pose_bones[f"foot_roll.{side}"]
        foot_roll_bone.rotation_mode = 'XYZ'
        add_driver(foot_roll_bone, "rotation_euler", 0,
                   f'foot_roll.{side} * radians(35)',
                   [{'name': f'foot_roll.{side}', 'type': 'SINGLE_PROP',
                     'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["foot_roll.{side}"]'}]}],
                   target_object=rig)

    # --- Squash/stretch ---
    body_bone = pose_bones["body"]
    body_bone.rotation_mode = 'XYZ'
    # Scale driver: scale[1] = 1 + squash, scale[0] = scale[2] = 1/sqrt(1+squash)
    add_driver(body_bone, "scale", 1,
               '1 + squash',
               [{'name': 'squash', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["squash"]'}]}],
               target_object=rig)
    add_driver(body_bone, "scale", 0,
               '1/sqrt(1 + squash)',
               [{'name': 'squash', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["squash"]'}]}],
               target_object=rig)
    add_driver(body_bone, "scale", 2,
               '1/sqrt(1 + squash)',
               [{'name': 'squash', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["squash"]'}]}],
               target_object=rig)

    # --- Lean ---
    add_driver(body_bone, "rotation_euler", 0,
               'lean_fwd * radians(15)',
               [{'name': 'lean_fwd', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["lean_fwd"]'}]}],
               target_object=rig)
    add_driver(body_bone, "rotation_euler", 2,
               'lean_side * radians(12)',
               [{'name': 'lean_side', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["lean_side"]'}]}],
               target_object=rig)

    # --- Twist ---
    spine_upper_bone = pose_bones["spine_upper"]
    spine_upper_bone.rotation_mode = 'XYZ'
    add_driver(spine_upper_bone, "rotation_euler", 1,
               'twist * radians(25)',
               [{'name': 'twist', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["twist"]'}]}],
               target_object=rig)

    # --- Lid tilt ---
    lid_bone = pose_bones["lid"]
    lid_bone.rotation_mode = 'XYZ'
    add_driver(lid_bone, "rotation_euler", 0,
               'lid_tilt_x * radians(20)',
               [{'name': 'lid_tilt_x', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["lid_tilt_x"]'}]}],
               target_object=rig)
    add_driver(lid_bone, "rotation_euler", 2,
               'lid_tilt_y * radians(20)',
               [{'name': 'lid_tilt_y', 'type': 'SINGLE_PROP',
                 'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': '["lid_tilt_y"]'}]}],
               target_object=rig)

    # --- Finger curls and spread ---
    finger_map = {
        "index": 12,
        "middle": 0,
        "ring": -12,
        "thumb": 15,
    }
    for side in ("L", "R"):
        for finger, spread_angle in finger_map.items():
            bone1 = pose_bones[f"{finger}_1.{side}"]
            bone2 = pose_bones[f"{finger}_2.{side}"]
            bone1.rotation_mode = 'XYZ'
            bone2.rotation_mode = 'XYZ'

            # Curl drivers
            add_driver(bone1, "rotation_euler", 0,
                       f'curl_{finger}.{side} * radians(70)',
                       [{'name': f'curl_{finger}.{side}', 'type': 'SINGLE_PROP',
                         'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["curl_{finger}.{side}"]'}]}],
                       target_object=rig)
            add_driver(bone2, "rotation_euler", 0,
                       f'curl_{finger}.{side} * radians(80)',
                       [{'name': f'curl_{finger}.{side}', 'type': 'SINGLE_PROP',
                         'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["curl_{finger}.{side}"]'}]}],
                       target_object=rig)
            # Spread + sideways bend on the first bone, sideways bend on the second.
            # Bone Z = palm normal: negative side bends the finger toward the thumb (+X of the hand).
            rig[f"side_{finger}.{side}"] = 0.0
            rig.id_properties_ui(f"side_{finger}.{side}").update(min=-1.0, max=1.0, soft_min=-1.0, soft_max=1.0)
            side_var = {'name': f'side_{finger}.{side}', 'type': 'SINGLE_PROP',
                        'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["side_{finger}.{side}"]'}]}
            spread_var = {'name': f'spread.{side}', 'type': 'SINGLE_PROP',
                          'targets': [{'id_type': 'OBJECT', 'id': rig, 'data_path': f'["spread.{side}"]'}]}
            add_driver(bone1, "rotation_euler", 2,
                       f'spread.{side} * radians({spread_angle}) + side_{finger}.{side} * radians(55)',
                       [spread_var, side_var], target_object=rig)
            add_driver(bone2, "rotation_euler", 2,
                       f'side_{finger}.{side} * radians(75)', [side_var], target_object=rig)

    # --- Hand poses data ---
    # HAND_POSES defined later; no need here

# ----------------------------------------------------------------
# Vertex weighting
# ----------------------------------------------------------------
def get_path_points(side):
    """Return the arm path points for side."""
    points = ARM_REST_POINTS if side == "L" else ARM_WAVE_POINTS
    return catmull_rom(points, 25)

def nearest_on_path(point, path_points):
    """Return (closest_point, arc_length_fraction) for point relative to path."""
    best_dist = float('inf')
    best_point = None
    best_a = 0.0
    total_len = 0.0
    # Precompute segment lengths
    seg_lengths = [(path_points[i+1] - path_points[i]).length for i in range(len(path_points)-1)]
    total_len = sum(seg_lengths)
    acc = 0.0
    for i, seg_len in enumerate(seg_lengths):
        p0 = path_points[i]
        p1 = path_points[i+1]
        # Closest point on segment
        seg = p1 - p0
        t = (point - p0).dot(seg) / (seg.length_squared) if seg.length_squared > 0 else 0.0
        t = clamp(t, 0.0, 1.0)
        closest = p0 + seg * t
        dist = (point - closest).length
        if dist < best_dist:
            best_dist = dist
            best_point = closest
            a = (acc + t * seg_len) / total_len
            best_a = a
        acc += seg_len
    return best_point, best_a

def weight_all(rig):
    """Create vertex groups and assign weights to all deformable meshes."""
    # Determine objects to rig
    body_region_names = ["Body", "Lid_Top", "Lid_Rim", "Hoop_29", "Hoop_44", "Hoop_76", "Hoop_97",
                         "Face_Proxy", "Mouth_Cutter"]
    body_region_prefixes = ["Eye", "Pupil_", "Highlight_", "Brow_", "Mouth_", "Nose", "Logo_",
                            "Blush_", "Prop_", "Eyelid_"]
    arm_names = ["Arm_Left", "Arm_Right"]
    glove_prefixes = ["Glove_"]
    leg_names = ["Leg_Left", "Leg_Right"]
    shoe_names = ["Shoe_Left", "Shoe_Right"]
    skip_names = ["Backdrop", "Ground", "Mascot_Rig", "Face_Ctrl", "Eye_Target",
                  "Socket_Hand.L", "Socket_Hand.R"]

    # Gather objects to process
    objects_to_rig = []
    for obj in bpy.data.objects:
        if obj.name in skip_names or obj.type != 'MESH':
            continue
        if obj.name in body_region_names or any(obj.name.startswith(p) for p in body_region_prefixes):
            objects_to_rig.append(("body", obj))
        elif obj.name in arm_names:
            objects_to_rig.append(("arm", obj))
        elif any(obj.name.startswith(p) for p in glove_prefixes):
            # Determine if it's cuff/wrist/palm or finger
            if "Cuff" in obj.name or "Wrist" in obj.name or "Palm" in obj.name:
                objects_to_rig.append(("glove_hand", obj))
            elif "Finger" in obj.name or "Thumb" in obj.name:
                objects_to_rig.append(("glove_finger", obj))
        elif obj.name in leg_names:
            objects_to_rig.append(("leg", obj))
        elif obj.name in shoe_names:
            objects_to_rig.append(("shoe", obj))

    # Create Armature modifier and move to index 0
    for _, obj in objects_to_rig:
        if "Rig" not in obj.modifiers:
            mod = obj.modifiers.new("Rig", 'ARMATURE')
            mod.object = rig
            mod.use_vertex_groups = True
            # Move to index 0
            try:
                obj.modifiers.move(len(obj.modifiers)-1, 0)
            except:
                try:
                    with bpy.context.temp_override(object=obj):
                        bpy.ops.object.modifier_move_to_index(modifier="Rig", index=0)
                except:
                    pass

    # Weight body region (only body-region meshes; keep other groups such as Body's fur_density)
    def _vg(o, name):
        return o.vertex_groups.get(name) or o.vertex_groups.new(name=name)

    for kind, obj in objects_to_rig:
        if kind != "body":
            continue
        vg_lower = _vg(obj, "spine_lower")
        vg_upper = _vg(obj, "spine_upper")
        vg_lid = _vg(obj, "lid")

        if obj.name in ["Lid_Top", "Lid_Rim"]:
            # 100% lid
            for i in range(len(obj.data.vertices)):
                vg_lid.add([i], 1.0, 'REPLACE')
            continue

        for i, v in enumerate(obj.data.vertices):
            z = (obj.matrix_world @ v.co).z
            # spine blend
            mid_z = BODY_BOTTOM + BODY_H * 0.5
            t = (z - mid_z) / 0.25
            t = clamp(t, -1.0, 1.0)
            s = smoothstep(-1.0, 1.0, t)
            w_lower = 1.0 - s
            w_upper = s
            # lid blend
            if z > BODY_TOP - 0.06:
                lid_factor = smoothstep(BODY_TOP - 0.06, BODY_TOP + 0.01, z)
            else:
                lid_factor = 0.0
            w_lower *= (1.0 - lid_factor)
            w_upper *= (1.0 - lid_factor)
            w_lid = lid_factor
            total = w_lower + w_upper + w_lid
            if total > 0:
                w_lower /= total
                w_upper /= total
                w_lid /= total
            vg_lower.add([i], w_lower, 'REPLACE')
            vg_upper.add([i], w_upper, 'REPLACE')
            vg_lid.add([i], w_lid, 'REPLACE')

    # Weight arms
    for _, obj in objects_to_rig:
        if obj.name in arm_names:
            side = "L" if obj.name.endswith("Left") else "R"
            path_points = get_path_points(side)
            # Clear groups
            obj.vertex_groups.clear()
            vg_upper = obj.vertex_groups.new(name=f"upper_arm.{side}")
            vg_forearm = obj.vertex_groups.new(name=f"forearm.{side}")
            vg_hand = obj.vertex_groups.new(name=f"hand.{side}")
            for i, v in enumerate(obj.data.vertices):
                world_co = obj.matrix_world @ v.co
                _, a = nearest_on_path(world_co, path_points)
                a = clamp(a, 0.0, 1.0)
                # Upper/forearm blend
                if a <= 0.42:
                    w_upper = 1.0
                    w_forearm = 0.0
                elif a >= 0.58:
                    w_upper = 0.0
                    w_forearm = 1.0
                else:
                    u = smoothstep(0.42, 0.58, a)
                    w_upper = 1.0 - u
                    w_forearm = u
                # Hand blend for wrist area
                if a >= 0.98:
                    hand_weight = smoothstep(0.98, 1.0, a)
                else:
                    hand_weight = 0.0
                w_upper *= (1.0 - hand_weight)
                w_forearm *= (1.0 - hand_weight)
                total = w_upper + w_forearm + hand_weight
                if total > 0:
                    w_upper /= total
                    w_forearm /= total
                    hand_weight /= total
                vg_upper.add([i], w_upper, 'REPLACE')
                vg_forearm.add([i], w_forearm, 'REPLACE')
                vg_hand.add([i], hand_weight, 'REPLACE')

    # Weight gloves (hand and fingers)
    for _, obj in objects_to_rig:
        if "Glove_" in obj.name:
            side = "L" if ".L" in obj.name or "Left" in obj.name else "R"
            obj.vertex_groups.clear()
            # Determine type
            if "Cuff" in obj.name or "Wrist" in obj.name or "Palm" in obj.name:
                vg_hand = obj.vertex_groups.new(name=f"hand.{side}")
                for i in range(len(obj.data.vertices)):
                    vg_hand.add([i], 1.0, 'REPLACE')
            else:
                # Finger object
                finger_name_map = {
                    "Finger1": "index",
                    "Finger2": "middle",
                    "Finger3": "ring",
                    "Thumb": "thumb",
                }
                finger_base = None
                for key, val in finger_name_map.items():
                    if key in obj.name:
                        finger_base = val
                        break
                if finger_base is None:
                    continue
                vg_bone1 = obj.vertex_groups.new(name=f"{finger_base}_1.{side}")
                vg_bone2 = obj.vertex_groups.new(name=f"{finger_base}_2.{side}")
                vg_hand = obj.vertex_groups.new(name=f"hand.{side}")
                # Compute root/tip axis from vertices
                palm_obj = bpy.data.objects.get(f"Glove_{'Left' if side == 'L' else 'Right'}_Palm")
                if not palm_obj:
                    continue
                palm_center_world = palm_obj.matrix_world @ (sum((v.co for v in palm_obj.data.vertices), Vector((0,0,0))) / len(palm_obj.data.vertices))
                verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]
                dists = [(v, (v - palm_center_world).length) for v in verts_world]
                dists.sort(key=lambda x: x[1])
                n = len(dists)
                n_root = max(1, int(n * 0.15))
                n_tip = max(1, int(n * 0.15))
                root = sum((v for v, d in dists[:n_root]), Vector((0,0,0))) / n_root
                tip = sum((v for v, d in dists[-n_tip:]), Vector((0,0,0))) / n_tip
                axis = tip - root
                axis_len = axis.length
                if axis_len < 1e-6:
                    continue
                axis_dir = axis / axis_len
                for i, v in enumerate(obj.data.vertices):
                    world_co = obj.matrix_world @ v.co
                    s = (world_co - root).dot(axis_dir) / axis_len
                    if s < 0.05:
                        # Inside palm, 50/50 with hand
                        w_hand = 0.5
                        w_bone1 = 0.5
                        w_bone2 = 0.0
                    else:
                        w_bone1 = 1.0 - smoothstep(0.4, 0.6, s)
                        w_bone2 = 1.0 - w_bone1
                        w_hand = 0.0
                    vg_hand.add([i], w_hand, 'REPLACE')
                    vg_bone1.add([i], w_bone1, 'REPLACE')
                    vg_bone2.add([i], w_bone2, 'REPLACE')

    # Weight legs
    for _, obj in objects_to_rig:
        if obj.name in leg_names:
            side = "L" if obj.name.endswith("Left") else "R"
            obj.vertex_groups.clear()
            vg_thigh = obj.vertex_groups.new(name=f"thigh.{side}")
            vg_shin = obj.vertex_groups.new(name=f"shin.{side}")
            knee_z = (BODY_BOTTOM + SHOE_H) / 2 + 0.02
            for i, v in enumerate(obj.data.vertices):
                z = (obj.matrix_world @ v.co).z
                w_thigh = 1.0 - smoothstep(knee_z - 0.03, knee_z + 0.03, z)
                w_shin = 1.0 - w_thigh
                vg_thigh.add([i], w_thigh, 'REPLACE')
                vg_shin.add([i], w_shin, 'REPLACE')

    # Weight shoes
    for _, obj in objects_to_rig:
        if obj.name in shoe_names:
            side = "L" if obj.name.endswith("Left") else "R"
            obj.vertex_groups.clear()
            vg_foot = obj.vertex_groups.new(name=f"foot.{side}")
            for i in range(len(obj.data.vertices)):
                vg_foot.add([i], 1.0, 'REPLACE')

# ----------------------------------------------------------------
# Hook Eye Target into existing drivers
# ----------------------------------------------------------------
def hook_eye_target(rig):
    """Look drivers on Pupil_*/Highlight_* also follow Eye_Target when rig["use_eye_target"] = 1."""
    eye_target = bpy.data.objects.get("Eye_Target")
    if not eye_target:
        return
    for obj_name in ["Pupil_Left", "Pupil_Right", "Highlight_Left", "Highlight_Right"]:
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.data.shape_keys is None or obj.data.shape_keys.animation_data is None:
            continue
        for fc in obj.data.shape_keys.animation_data.drivers:
            drv = fc.driver
            if "look_x" not in drv.expression and "look_y" not in drv.expression:
                continue
            for name, chan in (("tx", "LOC_X"), ("tz", "LOC_Z")):
                v = drv.variables.new()
                v.name = name
                v.type = "TRANSFORMS"
                v.targets[0].id = eye_target
                v.targets[0].transform_type = chan
                v.targets[0].transform_space = "WORLD_SPACE"
            v = drv.variables.new()
            v.name = "use_eye_target"
            v.type = "SINGLE_PROP"
            v.targets[0].id_type = "OBJECT"
            v.targets[0].id = rig
            v.targets[0].data_path = '["use_eye_target"]'
            expr = drv.expression
            expr = expr.replace("look_x", "(look_x + use_eye_target * max(min((tx - 0.03) / 0.35, 1), -1))")
            expr = expr.replace("look_y", f"(look_y + use_eye_target * max(min((tz - {EYE_Z:.4f}) / 0.25, 1), -1))")
            drv.expression = expr


# ----------------------------------------------------------------
# Hand poses and pose definitions
# ----------------------------------------------------------------
HAND_POSES = {
    "open_wave": {
        "index": (0.0, 0.6),
        "middle": (0.0, 0.6),
        "ring": (0.0, 0.6),
        "thumb": (0.0, 0.0),  # thumb curl, spread not used for thumb
    },
    "ok_sign": {  # palm to camera: index and thumb bend sideways into a circle that faces the camera
        "index": (0.15, 0.3, -1.0),
        "middle": (0.05, 0.3),
        "ring": (0.1, 0.3),
        "thumb": (0.1, 0.0, -1.0),
    },
    "thumbs_up": {
        "index": (1.0, 0.0),
        "middle": (1.0, 0.0),
        "ring": (1.0, 0.0),
        "thumb": (0.0, 0.0),
    },
    "point": {
        "index": (0.0, 0.0),
        "middle": (1.0, 0.0),
        "ring": (1.0, 0.0),
        "thumb": (0.8, 0.0),
    },
    "fist": {
        "index": (1.0, 0.0),
        "middle": (1.0, 0.0),
        "ring": (1.0, 0.0),
        "thumb": (0.8, 0.0),
    },
    "hold": {
        "index": (0.55, 0.0),
        "middle": (0.55, 0.0),
        "ring": (0.55, 0.0),
        "thumb": (0.45, 0.0),
    },
}

def apply_hand_pose(side, pose_name):
    """Set rig properties for a hand pose."""
    rig = bpy.data.objects["Mascot_Rig"]
    if pose_name not in HAND_POSES:
        return
    pose = HAND_POSES[pose_name]
    for finger, values in pose.items():
        curl, spread = values[0], values[1]
        rig[f"side_{finger}.{side}"] = values[2] if len(values) > 2 else 0.0
        # Set curl
        rig[f"curl_{finger}.{side}"] = curl
        # Set spread (only for non-thumb)
        if finger != "thumb":
            rig[f"spread.{side}"] = spread

def reset_pose():
    """Reset all rig properties and pose bone transforms to defaults."""
    rig = bpy.data.objects["Mascot_Rig"]
    # Reset custom properties
    for prop in rig.keys():
        if prop.startswith("ik_fk"):
            rig[prop] = 0.0
        elif prop.startswith("foot_roll"):
            rig[prop] = 0.0
        elif prop == "squash":
            rig[prop] = 0.0
        elif prop in ("lean_fwd", "lean_side", "twist", "lid_tilt_x", "lid_tilt_y"):
            rig[prop] = 0.0
        elif prop.startswith("curl"):
            rig[prop] = 0.0
        elif prop.startswith("spread") or prop.startswith("side_"):
            rig[prop] = 0.0
        elif prop == "use_eye_target":
            rig[prop] = 0.0
    # Reset pose bones to identity
    for pb in rig.pose.bones:
        pb.location = (0,0,0)
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0,0,0)
        pb.scale = (1,1,1)
    # Reset Face_Ctrl properties
    face_ctrl = bpy.data.objects.get("Face_Ctrl")
    if face_ctrl:
        for key in face_ctrl.keys():
            if isinstance(face_ctrl[key], float):
                face_ctrl[key] = 0.0
    # Force update
    bpy.context.view_layer.update()

SHOULDER_Z = model02.SHOULDER_Z
HIP_Z = model02.HIP_Z


def place_ik_hand(rig, side, pos, local_axis=None, angle_deg=0.0, hand_scale=1.0):
    """Switch the arm to IK and put the hand at `pos` (world) with the hand's REST orientation,
    optionally turned by angle_deg about one of the hand bone's own axes (local_axis, e.g. (0, 0, 1)
    = palm normal, (0, 1, 0) = along the fingers). The hand copies IK_hand's rotation in IK mode."""
    rig[f"ik_fk.{side}"] = 1.0
    rest = rig.data.bones[f"hand.{side}"].matrix_local.copy()
    rot = rest.to_3x3()
    if local_axis is not None and angle_deg:
        axis = (rot @ Vector(local_axis)).normalized()
        rot = Matrix.Rotation(math.radians(angle_deg), 3, axis) @ rot
    m = rot.to_4x4()
    m.translation = Vector(pos)
    bpy.context.view_layer.update()
    rig.pose.bones[f"IK_hand.{side}"].matrix = m
    if hand_scale != 1.0:
        rig.pose.bones[f"hand.{side}"].scale = (hand_scale,) * 3
    bpy.context.view_layer.update()


def pose_hand(rig, side, pos, fingers_dir, palm_dir, hand_scale=1.0):
    """IK-place a hand at world `pos` aimed by world directions: fingers_dir = where the fingers
    point (hand bone Y), palm_dir = where the palm faces (hand bone Z = palm normal).
    Examples (R = character right, -X): wave/please-wait palm to camera = fingers (0,0,1), palm (0,-1,0);
    thumbs-up R = fingers (-0.82,0,0.57), palm (0,-1,0) (mirror X for L); palms up = palm (0,0,1)."""
    y = Vector(fingers_dir).normalized()
    z = Vector(palm_dir)
    z = (z - z.dot(y) * y).normalized()
    x = y.cross(z)
    rot = Matrix((x, y, z)).transposed()  # columns X, Y, Z
    rig[f"ik_fk.{side}"] = 1.0
    m = rot.to_4x4()
    m.translation = Vector(pos)
    bpy.context.view_layer.update()
    rig.pose.bones[f"IK_hand.{side}"].matrix = m
    rig.pose.bones[f"hand.{side}"].scale = (hand_scale,) * 3
    bpy.context.view_layer.update()


def rest_arm_visible(rig, root_z=0.0):
    """Sticker poses: bring the resting left hand out from behind the body."""
    place_ik_hand(rig, "L", (0.72, -0.2, HIP_Z + 0.06 + root_z))


def set_bone_world_location(rig, bone_name, world_pos):
    """Move a pose bone so its head sits at world_pos (armature at the origin, so armature space = world)."""
    pb = rig.pose.bones[bone_name]
    bpy.context.view_layer.update()
    m = pb.matrix.copy()
    m.translation = Vector(world_pos)
    pb.matrix = m


OK_TWIST_DEG = 90.0
THUMB_TURN_DEG = 55.0  # tuned by close-up renders: 90 tilts the thumb ~40 deg outward, 125 lays it flat


def set_pose(name):
    """Apply a test pose by name."""
    rig = bpy.data.objects["Mascot_Rig"]
    reset_pose()
    if name == "wave":
        apply_hand_pose("R", "open_wave")
        rig["lean_side"] = 0.15
        rest_arm_visible(rig)
        face_ctrl = bpy.data.objects.get("Face_Ctrl")
        face_ctrl["m_big_smile"] = 0.8
        face_ctrl["brow_raise_L"] = 0.4
        face_ctrl["brow_raise_R"] = 0.4
    elif name == "thumbs_up":
        apply_hand_pose("R", "thumbs_up")
        # fist held out at shoulder height; turning 90 deg about the palm normal makes the thumb
        # (which points toward the body in the wave pose) point straight up, palm toward the camera
        place_ik_hand(rig, "R", (-0.9, -0.28, SHOULDER_Z + 0.12), (0, 0, 1), THUMB_TURN_DEG, hand_scale=1.35)
        rest_arm_visible(rig)
        face_ctrl = bpy.data.objects.get("Face_Ctrl")
        face_ctrl["m_smirk_L"] = 0.9
        face_ctrl["blink_L"] = 1.0
    elif name == "ok_sign":
        apply_hand_pose("R", "ok_sign")
        place_ik_hand(rig, "R", (-0.88, -0.28, SHOULDER_Z + 0.22), hand_scale=1.35)
        rest_arm_visible(rig)
        face_ctrl = bpy.data.objects.get("Face_Ctrl")
        face_ctrl["closed_smile"] = 1.0
        face_ctrl["m_small_smile"] = 1.0
    elif name == "jump":
        rig["squash"] = 0.18
        # Move root up
        root_bone = rig.pose.bones["root"]
        root_bone.location.z = 0.35
        # Lift IK feet further
        rig["foot_roll.L"] = -0.4
        rig["foot_roll.R"] = -0.4
        # Arms up: the right arm is already raised; the resting left arm switches to IK and its
        # target goes above and outside the shoulder (root moved up 0.35, so add that)
        rig["ik_fk.L"] = 1.0
        set_bone_world_location(rig, "IK_hand.L", (0.80, -0.12, BODY_TOP + 0.12 + 0.35))
        apply_hand_pose("L", "open_wave")
        apply_hand_pose("R", "open_wave")
        face_ctrl = bpy.data.objects.get("Face_Ctrl")
        face_ctrl["m_laugh"] = 1.0
        face_ctrl["happy_L"] = 1.0
        face_ctrl["happy_R"] = 1.0
        face_ctrl["brow_raise_L"] = 1.0
        face_ctrl["brow_raise_R"] = 1.0
        face_ctrl["brow_short"] = 1.0
    bpy.context.view_layer.update()

# ----------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------
def render_pose(name, args):
    """Set camera and render pose."""
    # Camera settings
    cam = bpy.data.objects["Camera"]
    look_target = bpy.data.objects["Look_Target"]
    # the saved blend's camera may still track the model's Camera_Target; aim it at Look_Target
    for c in cam.constraints:
        if c.type == 'TRACK_TO':
            c.target = look_target
    if name == "jump":
        look_target.location = (0, 0, 1.35)
    else:
        look_target.location = (-0.08, 0, 1.05)
    # sticker camera: mostly front, body turned ~10 deg toward the waving side, whole character in frame
    cam.location = (-1.05, -5.9, 1.3)
    cam.data.lens = 50
    bpy.context.scene.render.resolution_x = args.res
    bpy.context.scene.render.resolution_y = args.res
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.cycles.samples = args.samples
    out_path = os.path.join(args.project_root, "renders", f"pose_{name}.png")
    bpy.context.scene.render.filepath = out_path
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    print(f"[05] pose {name} {time.perf_counter()-t:.1f}s")

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", nargs="?", default=None)
    parser.add_argument("--poses", default="wave,thumbs_up,ok_sign,jump")
    parser.add_argument("--res", type=int, default=1024)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(argv)
    if args.project_root is None:
        args.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    else:
        args.project_root = os.path.abspath(args.project_root)

    # Ensure renders dir exists
    os.makedirs(os.path.join(args.project_root, "renders"), exist_ok=True)

    # Build armature and parent root
    print("[05] Building armature...")
    rig = build_armature()
    # Add constraints and drivers
    print("[05] Adding constraints and drivers...")
    add_constraints_and_drivers(rig)
    # Weight meshes
    print("[05] Weighting meshes...")
    weight_all(rig)
    # Hook eye target
    print("[05] Hooking eye target...")
    hook_eye_target(rig)
    # Save blend (rest pose)
    reset_pose()
    blend_path = os.path.join(args.project_root, "blend", "mascot_rig.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"[05] saved {blend_path}")

    if not args.no_render:
        pose_names = [p.strip() for p in args.poses.split(",") if p.strip()]
        for name in pose_names:
            if name not in ["wave", "thumbs_up", "ok_sign", "jump"]:
                print(f"Warning: unknown pose {name}, skipping")
                continue
            print(f"[05] applying pose {name}")
            set_pose(name)
            print(f"[05] rendering {name}")
            render_pose(name, args)
            reset_pose()  # Reset after render

if __name__ == "__main__":
    main()
