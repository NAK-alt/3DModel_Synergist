```python
import bpy
import math
import mathutils
import os
import sys

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
BODY_D = 1.0          # diameter
BODY_R = BODY_D / 2.0 # radius = 0.5
BODY_H = 1.3          # height

LEG_LEN = 0.195       # 15% of body height
LEG_RADIUS = 0.04
SHOE_HEIGHT = 0.2
SHOE_WIDTH = 0.35
SHOE_LENGTH = 0.45
SHOE_FORWARD = 0.1    # shift toe forward (-Y)

ARM_RADIUS = 0.035
SHOULDER_FROM_TOP = 0.4  # 40% from top
HIP_FROM_TOP = 0.8       # 80% from top

# Hoop positions (measured from top)
HOOP_PERCENTS = [0.30, 0.45, 0.75, 0.95]
HOOP_MAJOR_R = 0.505
HOOP_MINOR_R = 0.025

# Lid
LID_RIM_MAJOR_R = 0.49
LID_RIM_MINOR_R = 0.035
LID_DISC_RADIUS = 0.48
LID_DISC_SCALE_Z = 0.08

# Face
EYE_SPACING = 0.24      # center to center
EYE_SCLERA_WIDTH = 0.12
EYE_SCLERA_HEIGHT = 0.16
EYE_FLATTEN_Y = 0.02    # thickness along Y
PUPIL_SCALE = 0.4       # relative to sclera
MOUTH_WIDTH = 0.2
MOUTH_HEIGHT = 0.05
MOUTH_FLATTEN_Y = 0.02

# Logo placeholder
LOGO_WIDTH = 0.45
LOGO_HEIGHT = 0.25
LOGO_FLATTEN_Y = 0.05

# Materials (hex sRGB)
COL_BODY = "#1F3FB8"
COL_HOOP = "#1F3FB8"     # will be multiplied by 0.85
COL_ARMS_LEGS = "#101629"
COL_WHITE = "#F2F2F2"
COL_BLACK = "#0A0A0A"
COL_GOLD = "#D5B268"

# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------
def srgb_to_linear(hex_color):
    """Convert hex sRGB to linear RGB (approx)."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    def conv(c):
        if c <= 0.04045:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    return (conv(r), conv(g), conv(b), 1.0)

def make_material(name, hex_color, roughness=0.5, metallic=0.0):
    """Create or get material with Principled BSDF."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is None:
            bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
            mat.node_tree.links.new(bsdf.outputs['BSDF'], mat.node_tree.nodes['Material Output'].inputs['Surface'])
        bsdf.inputs['Base Color'].default_value = srgb_to_linear(hex_color)
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
        # viewport display color (sRGB expected, but we use linear anyway)
        mat.diffuse_color = srgb_to_linear(hex_color)
    return mat

def add_cylinder(name, radius, depth, location=(0,0,0), rotation_euler=(0,0,0), material=None, smooth=True, bevel_width=0.0, bevel_segments=0):
    """Create a cylinder, origin at bottom center, with optional bevel."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation_euler
    )
    obj = bpy.context.active_object
    obj.name = name
    if smooth:
        bpy.ops.object.shade_smooth()
    if material:
        obj.data.materials.append(material)
    if bevel_width > 0:
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = bevel_width
        mod.segments = bevel_segments
        mod.limit_method = 'ANGLE'
        mod.angle_limit = math.radians(30)
    return obj

def add_torus(name, major_radius, minor_radius, location=(0,0,0), rotation_euler=(0,0,0), material=None, major_segments=48, minor_segments=16):
    """Create a torus."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=major_segments,
        minor_segments=minor_segments,
        location=location,
        rotation=rotation_euler
    )
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    if material:
        obj.data.materials.append(material)
    return obj

def add_sphere(name, radius, location=(0,0,0), scale=(1,1,1), rotation_euler=(0,0,0), material=None):
    """Create a UV sphere, scale and position."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        location=location,
        rotation=rotation_euler
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.shade_smooth()
    if material:
        obj.data.materials.append(material)
    return obj

def add_bezier_curve(name, points, radius, material=None):
    """Create a 3D bezier curve with bevel_depth (tube)."""
    curve_data = bpy.data.curves.new(name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = radius
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for i, pt in enumerate(points):
        bp = spline.bezier_points[i]
        bp.co = pt
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj

def parent_to_root(obj):
    """Parent object to Mascot_Root empty."""
    obj.parent = bpy.data.objects['Mascot_Root']

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    # ---- Parse arguments ----
    argv = sys.argv
    if "--" in argv:
        idx = argv.index("--")
        project_root = argv[idx+1] if idx+1 < len(argv) else None
    else:
        project_root = None
    if project_root is None:
        # default to parent of script folder
        script_path = os.path.realpath(__file__)
        script_dir = os.path.dirname(script_path)
        project_root = os.path.dirname(script_dir)
    project_root = os.path.abspath(project_root)
    blend_dir = os.path.join(project_root, "blend")
    render_dir = os.path.join(project_root, "renders")
    os.makedirs(blend_dir, exist_ok=True)
    os.makedirs(render_dir, exist_ok=True)

    # ---- Clear scene ----
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # ---- Units ----
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'

    # ---- Root empty ----
    root = bpy.data.objects.new("Mascot_Root", None)
    bpy.context.collection.objects.link(root)
    root.location = (0, 0, 0)

    # ---- Materials ----
    mat_body = make_material("M_Body", COL_BODY, roughness=0.8)
    mat_hoop = make_material("M_Hoop", COL_HOOP, roughness=0.8)
    # Darken hoop: multiply base color by 0.85
    mat_hoop.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = tuple(c * 0.85 for c in srgb_to_linear(COL_HOOP)[:3]) + (1.0,)
    mat_arms_legs = make_material("M_ArmsLegs", COL_ARMS_LEGS, roughness=0.6)
    mat_white = make_material("M_White", COL_WHITE, roughness=0.5)
    mat_black = make_material("M_Black", COL_BLACK, roughness=0.3)
    mat_gold = make_material("M_Gold", COL_GOLD, roughness=0.35, metallic=0.6)

    # ---- Body positions ----
    shoe_top_z = SHOE_HEIGHT  # 0.2
    leg_bottom_z = shoe_top_z  # leg connects to shoe top
    leg_top_z = leg_bottom_z + LEG_LEN  # 0.2 + 0.195 = 0.395
    body_bottom_z = leg_top_z
    body_top_z = body_bottom_z + BODY_H  # 0.395 + 1.3 = 1.695

    # ---- Body (cylinder) ----
    body = add_cylinder(
        "Body",
        radius=BODY_R,
        depth=BODY_H,
        location=(0, 0, body_bottom_z),
        material=mat_body,
        bevel_width=0.03,
        bevel_segments=3
    )
    parent_to_root(body)

    # ---- Lid rim (torus) ----
    rim = add_torus(
        "Lid_Rim",
        major_radius=LID_RIM_MAJOR_R,
        minor_radius=LID_RIM_MINOR_R,
        location=(0, 0, body_top_z + 0.02),
        material=mat_hoop
    )
    parent_to_root(rim)

    # ---- Lid disc (flattened sphere) ----
    lid_disc = add_sphere(
        "Lid_Disc",
        radius=LID_DISC_RADIUS,
        location=(0, 0, body_top_z - 0.01),
        scale=(1, 1, LID_DISC_SCALE_Z),
        material=mat_body
    )
    parent_to_root(lid_disc)

    # ---- Hoops ----
    for pct in HOOP_PERCENTS:
        z = body_top_z - pct * BODY_H
        hoop = add_torus(
            f"Hoop_{int(pct*100)}",
            major_radius=HOOP_MAJOR_R,
            minor_radius=HOOP_MINOR_R,
            location=(0, 0, z),
            material=mat_hoop
        )
        parent_to_root(hoop)

    # ---- Face zone (between Hoop_30 and Hoop_45) ----
    # Eyes: two white spheres, flattened in Y, positioned on front (-Y)
    eye_z = body_top_z - 0.35 * BODY_H  # ~35% from top
    eye_offset_y = -BODY_R - 0.01  # slightly outside barrel surface
    eye_x = EYE_SPACING / 2.0  # 0.12
    # Left eye (character's left = -X)
    left_eye = add_sphere(
        "Eye_Left",
        radius=1.0,
        location=(-eye_x, eye_offset_y, eye_z),
        scale=(EYE_SCLERA_WIDTH, EYE_FLATTEN_Y, EYE_SCLERA_HEIGHT),
        material=mat_white
    )
    parent_to_root(left_eye)
    # Right eye
    right_eye = add_sphere(
        "Eye_Right",
        radius=1.0,
        location=(eye_x, eye_offset_y, eye_z),
        scale=(EYE_SCLERA_WIDTH, EYE_FLATTEN_Y, EYE_SCLERA_HEIGHT),
        material=mat_white
    )
    parent_to_root(right_eye)

    # Pupils (black, slightly in front)
    pupil_offset_y = eye_offset_y - 0.005  # further outward
    pupil_scale = PUPIL_SCALE * EYE_SCLERA_WIDTH  # relative to sclera width
    left_pupil = add_sphere(
        "Pupil_Left",
        radius=1.0,
        location=(-eye_x, pupil_offset_y, eye_z),
        scale=(pupil_scale, EYE_FLATTEN_Y * 0.8, pupil_scale * (EYE_SCLERA_HEIGHT/EYE_SCLERA_WIDTH)),
        material=mat_black
    )
    parent_to_root(left_pupil)
    right_pupil = add_sphere(
        "Pupil_Right",
        radius=1.0,
        location=(eye_x, pupil_offset_y, eye_z),
        scale=(pupil_scale, EYE_FLATTEN_Y * 0.8, pupil_scale * (EYE_SCLERA_HEIGHT/EYE_SCLERA_WIDTH)),
        material=mat_black
    )
    parent_to_root(right_pupil)

    # Mouth: flattened dark ellipsoid (placeholder smile)
    mouth_z = body_top_z - 0.40 * BODY_H  # between eyes and 45% hoop
    mouth = add_sphere(
        "Mouth",
        radius=1.0,
        location=(0, eye_offset_y - 0.01, mouth_z),
        scale=(MOUTH_WIDTH, MOUTH_FLATTEN_Y, MOUTH_HEIGHT),
        material=mat_black
    )
    parent_to_root(mouth)

    # ---- Logo placeholder (between Hoop_45 and Hoop_75) ----
    logo_z = body_top_z - 0.60 * BODY_H  # 60% from top
    logo = add_sphere(
        "Logo_Placeholder",
        radius=1.0,
        location=(0, -BODY_R - 0.01, logo_z),
        scale=(LOGO_WIDTH, LOGO_FLATTEN_Y, LOGO_HEIGHT),
        material=mat_gold
    )
    parent_to_root(logo)

    # ---- Arms (Bezier curves) ----
    shoulder_z = body_top_z - SHOULDER_FROM_TOP * BODY_H  # 40% from top

    # Left arm (character's left = +X side, raised)
    left_arm_points = [
        (BODY_R, 0, shoulder_z),                     # shoulder at surface
        (0.9, 0, shoulder_z + 0.2),
        (1.2, 0, shoulder_z + 0.5),
        (1.3, 0, body_top_z + 0.3)                   # hand above and outside
    ]
    left_arm = add_bezier_curve("Arm_Left", left_arm_points, ARM_RADIUS, mat_arms_legs)
    parent_to_root(left_arm)

    # Right arm (character's right = -X side, hanging)
    hip_z = body_top_z - HIP_FROM_TOP * BODY_H  # 80% from top
    right_arm_points = [
        (-BODY_R, 0, shoulder_z),
        (-0.7, 0, shoulder_z - 0.1),
        (-0.7, 0, hip_z),
        (-0.6, 0, hip_z - 0.05)  # slightly out and down
    ]
    right_arm = add_bezier_curve("Arm_Right", right_arm_points, ARM_RADIUS, mat_arms_legs)
    parent_to_root(right_arm)

    # ---- Gloves (white palm + cuff) ----
    # Left glove (raised)
    left_hand_pos = left_arm_points[-1]
    left_palm = add_sphere(
        "Glove_Left_Palm",
        radius=0.14,
        location=left_hand_pos,
        scale=(1,1,1),
        material=mat_white
    )
    parent_to_root(left_palm)
    # Cuff: small torus around wrist, just before hand
    left_cuff = add_torus(
        "Glove_Left_Cuff",
        major_radius=0.04,
        minor_radius=0.015,
        location=(left_hand_pos[0]*0.9, 0, left_hand_pos[2] - 0.1),
        material=mat_white
    )
    parent_to_root(left_cuff)

    # Right glove (hanging)
    right_hand_pos = right_arm_points[-1]
    right_palm = add_sphere(
        "Glove_Right_Palm",
        radius=0.14,
        location=right_hand_pos,
        scale=(1,1,1),
        material=mat_white
    )
    parent_to_root(right_palm)
    right_cuff = add_torus(
        "Glove_Right_Cuff",
        major_radius=0.04,
        minor_radius=0.015,
        location=(right_hand_pos[0]*0.9, 0, right_hand_pos[2] + 0.1),
        material=mat_white
    )
    parent_to_root(right_cuff)

    # ---- Legs (Bezier curves, straight down) ----
    leg_x = 0.125  # spacing 0.25 -> ±0.125
    left_leg = add_bezier_curve(
        "Leg_Left",
        [(-leg_x, 0, leg_top_z), (-leg_x, 0, leg_bottom_z)],
        LEG_RADIUS,
        mat_arms_legs
    )
    parent_to_root(left_leg)
    right_leg = add_bezier_curve(
        "Leg_Right",
        [(leg_x, 0, leg_top_z), (leg_x, 0, leg_bottom_z)],
        LEG_RADIUS,
        mat_arms_legs
    )
    parent_to_root(right_leg)

    # ---- Shoes (flattened spheres, white) ----
    shoe_scale = (SHOE_WIDTH, SHOE_LENGTH, SHOE_HEIGHT)
    left_shoe = add_sphere(
        "Shoe_Left",
        radius=1.0,
        location=(-leg_x, -SHOE_FORWARD, SHOE_HEIGHT/2.0),
        scale=shoe_scale,
        material=mat_white
    )
    parent_to_root(left_shoe)
    right_shoe = add_sphere(
        "Shoe_Right",
        radius=1.0,
        location=(leg_x, -SHOE_FORWARD, SHOE_HEIGHT/2.0),
        scale=shoe_scale,
        material=mat_white
    )
    parent_to_root(right_shoe)

    # ---- Ground plane ----
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0,0,0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground_mat = make_material("M_Ground", "#CCCCCC", roughness=0.9)
    ground.data.materials.append(ground_mat)
    parent_to_root(ground)

    # ---- Lighting ----
    # Key light (front-left above)
    bpy.ops.object.light_add(type='AREA', location=(-2, -3, 3))
    key_light = bpy.context.active_object
    key_light.name = "Key_Light"
    key_light.data.energy = 300
    key_light.data.size = 2
    key_light.rotation_euler = (math.radians(45), 0, math.radians(45))

    # Fill light (front-right)
    bpy.ops.object.light_add(type='AREA', location=(2, -3, 2))
    fill_light = bpy.context.active_object
    fill_light.name = "Fill_Light"
    fill_light.data.energy = 150
    fill_light.data.size = 2

    # Rim light (behind)
    bpy.ops.object.light_add(type='AREA', location=(0, 3, 2))
    rim_light = bpy.context.active_object
    rim_light.name = "Rim_Light"
    rim_light.data.energy = 200
    rim_light.data.size = 1.5

    # ---- Camera and target ----
    # Compute mid height for camera target
    max_z = body_top_z + 0.5  # raised hand might be higher
    min_z = 0.0
    mid_z = (min_z + max_z) / 2.0

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,mid_z))
    target = bpy.context.active_object
    target.name = "Camera_Target"

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 50
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Add track-to constraint
    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    # Set initial position (front)
    cam_dist = 6.0
    cam_obj.location = (0, -cam_dist, mid_z)
    cam_obj.rotation_euler = (0, 0, 0)

    scene.camera = cam_obj

    # ---- World background ----
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new('ShaderNodeBackground')
        world.node_tree.links.new(bg.outputs['Background'], world.node_tree.nodes['World Output'].inputs['Surface'])
    bg.inputs['Color'].default_value = (0.8, 0.8, 0.8, 1.0)
    bg.inputs['Strength'].default_value = 1.0
    scene.world = world

    # ---- Render settings ----
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False

    # Engine selection
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except:
        try:
            scene.render.engine = 'BLENDER_EEVEE_NEXT'
        except:
            scene.render.engine = 'CYCLES'

    # ---- Render views ----
    views = [
        ("front", 0.0),
        ("threequarter", math.radians(45)),
        ("side", math.radians(90)),
        ("back", math.radians(180))
    ]

    for name, angle in views:
        # Position camera around Z axis
        cam_obj.location = (
            cam_dist * math.sin(angle),
            -cam_dist * math.cos(angle),
            mid_z
        )
        cam_obj.rotation_euler = (0, 0, angle)  # maintain up
        # Update scene
        bpy.context.view_layer.update()
        # Set output path
        scene.render.filepath = os.path.join(render_dir, f"blockout_{name}.png")
        # Render
        bpy.ops.render.render(write_still=True)

    # ---- Save blend ----
    blend_path = os.path.join(blend_dir, "mascot_blockout.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    print(f"Blockout completed. Blend saved to {blend_path}, renders in {render_dir}")

if __name__ == "__main__":
    main()
```