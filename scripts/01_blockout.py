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
BODY_H = 1.26         # height (updated)

LEG_LEN = 0.17 * BODY_H  # updated
LEG_RADIUS = 0.04
SHOE_HEIGHT = 0.2
SHOE_WIDTH = 0.34        # updated (full width)
SHOE_LENGTH = 0.45
SHOE_FORWARD = 0.1    # shift toe forward (-Y)

ARM_RADIUS = 0.035
SHOULDER_FROM_TOP = 0.4  # 40% from top
HIP_FROM_TOP = 0.8       # 80% from top

# Hoop positions (measured from top) - updated percentages
HOOP_PERCENTS = [0.29, 0.44, 0.76, 0.97]
HOOP_MAJOR_R = 0.505
HOOP_MINOR_R = 0.025

# Lid
LID_RIM_MAJOR_R = 0.47   # updated
LID_RIM_MINOR_R = 0.055  # updated
LID_DISC_RADIUS = 0.48   # unused? we use ellipsoid
LID_DISC_SCALE_Z = 0.08  # unused? we use ellipsoid

# Face
EYE_SPACING = 0.24      # center to center (old, but we override with new values)
EYE_SCLERA_WIDTH = 0.12 # old, will be overridden
EYE_SCLERA_HEIGHT = 0.16 # old
EYE_FLATTEN_Y = 0.02
PUPIL_SCALE = 0.4
MOUTH_WIDTH = 0.2
MOUTH_HEIGHT = 0.05
MOUTH_FLATTEN_Y = 0.02

# Logo placeholder (old, will be replaced with three pieces)
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
COL_GOLD_LIGHT = "#EED295"  # added
COL_MOUTH_IN = "#2A0A0A"    # added

BULGE = 0.015          # body bulge amount

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

def front_y(x, offset=0.0):
    """Y of the barrel's front surface at a given X (front faces -Y).
    Uses the bulged radius so face/logo parts sit on the stuffed fabric."""
    r = BODY_R + BULGE
    return -math.sqrt(max(r * r - x * x, 0.0)) - offset

def add_half_disc(name, width, height, depth, location, material=None, segments=24):
    """Half-ellipse slab, flat side up, front face toward -Y. location = centre of the flat top edge."""
    import bmesh
    bm = bmesh.new()
    verts = []
    for i in range(segments + 1):
        a = math.pi * i / segments              # 0..pi along the lower half
        verts.append(bm.verts.new((-(width / 2.0) * math.cos(a), 0.0, -height * math.sin(a))))
    f = bm.faces.new(verts)
    f.normal_update()
    if f.normal.y > 0:
        f.normal_flip()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    sol = obj.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = depth
    sol.offset = 0.0
    if material:
        me.materials.append(material)
    return obj

def add_ellipsoid(name, size, location, material=None):
    """UV sphere sized by full width/depth/height (x, y, z)."""
    return add_sphere(name, radius=0.5, location=location, scale=size, material=material)

def add_front_panel(name, width, height, z_center, radius, material=None, thickness=0.012, x_center=0.0):
    """Thin curved panel hugging the front of the barrel (cylinder section).
       x_center: angular offset (radians) to shift panel along the curve.
    """
    import bmesh
    half_ang = (width / 2.0) / radius
    seg = 24
    bm = bmesh.new()
    rows = []
    for zz in (z_center - height / 2.0, z_center + height / 2.0):
        row = []
        for i in range(seg + 1):
            a = x_center - half_ang + 2 * half_ang * i / seg
            row.append(bm.verts.new((radius * math.sin(a), -radius * math.cos(a), zz)))
        rows.append(row)
    for i in range(seg):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    sol = obj.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = thickness
    sol.offset = 1.0
    if material:
        me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    return obj

def add_glove(side, arm_points, mat):
    """Cuff ring + palm blob + 4 stubby fingers at the end of an arm curve."""
    end = mathutils.Vector(arm_points[-1])
    d = (end - mathutils.Vector(arm_points[-2])).normalized()
    rot = d.to_track_quat('Z', 'Y').to_euler()
    objs = []
    cuff = add_torus(f"Glove_{side}_Cuff", major_radius=0.055, minor_radius=0.025,
                     location=end, rotation_euler=rot, material=mat)
    objs.append(cuff)
    palm_c = end + d * 0.09
    palm = add_sphere(f"Glove_{side}_Palm", radius=0.5, location=palm_c,
                      scale=(0.17, 0.10, 0.15), rotation_euler=rot, material=mat)
    objs.append(palm)
    # fingers fan out along the arm direction
    side_v = d.cross(mathutils.Vector((0, 1, 0)))
    if side_v.length < 1e-4:
        side_v = mathutils.Vector((1, 0, 0))
    side_v.normalize()
    for i, off in enumerate((-0.054, -0.018, 0.018, 0.054)):
        tip = palm_c + d * 0.075 + side_v * off
        f = add_sphere(f"Glove_{side}_Finger{i+1}", radius=0.5, location=tip,
                       scale=(0.04, 0.04, 0.08), rotation_euler=rot, material=mat)
        objs.append(f)
    return objs

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

def add_lathe_body(name, profile_z_radii, segments=64, material=None):
    """Create a lathe (revolved) mesh from a list of (z, radius) points.
       profile_z_radii: list of (z, radius) from bottom to top.
    """
    import bmesh
    bm = bmesh.new()
    # create rings of vertices
    rings = []
    for z, r in profile_z_radii:
        ring = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    # create side faces (quads)
    for i in range(len(rings) - 1):
        ring0 = rings[i]
        ring1 = rings[i + 1]
        for j in range(segments):
            j_next = (j + 1) % segments
            bm.faces.new((ring0[j], ring0[j_next], ring1[j_next], ring1[j]))
    # cap bottom (fan)
    if rings:
        bottom_center = bm.verts.new((0, 0, profile_z_radii[0][0]))
        bottom_ring = rings[0]
        for j in range(segments):
            j_next = (j + 1) % segments
            bm.faces.new((bottom_center, bottom_ring[j], bottom_ring[j_next]))
    # cap top (fan)
    if rings:
        top_center = bm.verts.new((0, 0, profile_z_radii[-1][0]))
        top_ring = rings[-1]
        for j in range(segments):
            j_next = (j + 1) % segments
            bm.faces.new((top_center, top_ring[j_next], top_ring[j]))
    # ensure normals point outward
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    if material:
        me.materials.append(material)
    # smooth shade
    for p in me.polygons:
        p.use_smooth = True
    return obj

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
    mat_gold_light = make_material("M_GoldLight", COL_GOLD_LIGHT, roughness=0.35, metallic=0.6)
    mat_mouth_in = make_material("M_MouthIn", COL_MOUTH_IN, roughness=0.5)

    # ---- Body positions ----
    shoe_top_z = SHOE_HEIGHT  # 0.2
    leg_bottom_z = shoe_top_z  # leg connects to shoe top
    leg_top_z = leg_bottom_z + LEG_LEN  # 0.2 + (0.17*1.26) = 0.2 + 0.2142 = 0.4142
    body_bottom_z = leg_top_z
    body_top_z = body_bottom_z + BODY_H  # 0.4142 + 1.26 = 1.6742

    # ---- Body (lathe mesh with bulge) ----
    # Generate profile points (z, radius) from bottom to top.
    # Boundaries include bottom, top, and hoop z positions.
    hoop_z_list = [body_top_z - pct * BODY_H for pct in HOOP_PERCENTS]  # top to bottom order
    # sort all boundaries ascending (bottom to top)
    boundaries = sorted([body_bottom_z, body_top_z] + hoop_z_list)
    # create profile points every ~0.01
    z = body_bottom_z
    profile = []
    step = 0.01
    while z <= body_top_z + 1e-6:
        # find segment index
        seg_idx = 0
        for i in range(len(boundaries)-1):
            if boundaries[i] <= z <= boundaries[i+1]:
                seg_idx = i
                break
        z0 = boundaries[seg_idx]
        z1 = boundaries[seg_idx+1]
        if z1 - z0 < 1e-6:
            t = 0.0
        else:
            t = (z - z0) / (z1 - z0)
        r = BODY_R + BULGE * math.sin(math.pi * t)
        profile.append((z, r))
        z += step
    # ensure top point included
    if abs(profile[-1][0] - body_top_z) > 1e-4:
        profile.append((body_top_z, BODY_R))

    body = add_lathe_body("Body", profile, segments=64, material=mat_body)
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

    # ---- Lid disc (domed flat disc) ----
    lid_disc = add_ellipsoid(
        "Lid_Disc",
        (0.90, 0.90, 0.08),   # full size
        (0, 0, body_top_z + 0.03),
        mat_body
    )
    parent_to_root(lid_disc)

    # ---- Hoops ----
    for pct in HOOP_PERCENTS:
        z = body_top_z - pct * BODY_H
        hoop = add_torus(
            f"Hoop_{round(pct*100)}",  # names: 29, 44, 76, 97
            major_radius=HOOP_MAJOR_R,
            minor_radius=HOOP_MINOR_R,
            location=(0, 0, z),
            material=mat_hoop
        )
        parent_to_root(hoop)

    # ---- Face zone (between Hoop_29 and Hoop_44) ----
    hoop29_z = body_top_z - 0.29 * BODY_H
    hoop44_z = body_top_z - 0.44 * BODY_H
    band_height = 0.15 * BODY_H  # height between hoops

    # Eyes: white sclera with black outline behind, pupils shifted
    eye_width = 0.15
    eye_height = band_height - 0.01  # 0.15*1.26 - 0.01 = 0.189 - 0.01 = 0.179
    eye_depth = 0.04
    eye_z = (hoop29_z + hoop44_z) / 2.0
    eye_x = 0.095

    for side, sx in (("Left", 1), ("Right", -1)):   # character's left = +X
        x = sx * eye_x
        yaw = math.atan2(x, BODY_R)
        # Black outline (slightly larger, placed behind)
        outline = add_ellipsoid(
            f"Eye_{side}_Outline",
            (eye_width + 0.018, eye_depth + 0.006, eye_height + 0.018),
            (x, front_y(x, -0.006), eye_z),
            mat_black
        )
        outline.rotation_euler = (0, 0, yaw)
        parent_to_root(outline)
        # White sclera
        sclera = add_ellipsoid(
            f"Eye_{side}_Sclera",
            (eye_width, eye_depth, eye_height),
            (x, front_y(x, 0.0), eye_z),
            mat_white
        )
        sclera.rotation_euler = (0, 0, yaw)
        parent_to_root(sclera)
        # Pupil (shifted +X and down)
        pupil_x = x + 0.022  # shifted to viewer's right (+X)
        pupil_z = eye_z - 0.01
        pupil = add_ellipsoid(
            f"Pupil_{side}",
            (0.085, eye_depth - 0.01, 0.11),
            (pupil_x, front_y(pupil_x, 0.012), pupil_z),
            mat_black
        )
        pupil.rotation_euler = (0, 0, yaw)
        parent_to_root(pupil)

    # Brows: half torus (top half) above each eye
    brow_major = 0.05
    brow_minor = 0.009
    brow_z = hoop29_z + 0.035
    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * eye_x
        brow = add_torus(
            f"Brow_{side}",
            major_radius=brow_major,
            minor_radius=brow_minor,
            location=(x, front_y(x, 0.004), brow_z - 0.005),
            rotation_euler=(math.radians(90), 0, math.atan2(x, BODY_R)),  # ring faces front
            material=mat_black
        )
        # keep only the top half: local +Y maps to world +Z after the 90 deg X rotation
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(brow.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -1e-4], context='VERTS')
        bm.to_mesh(brow.data)
        bm.free()
        parent_to_root(brow)

    # Nose: small round black sphere on Hoop_44
    nose_diameter = 0.05
    nose = add_sphere(
        "Nose",
        radius=nose_diameter / 2.0,
        location=(0, -(HOOP_MAJOR_R + HOOP_MINOR_R) - 0.005, hoop44_z),
        material=mat_black
    )
    parent_to_root(nose)

    # Mouth: open smile, a dark half-ellipse slab with its flat top just under the nose
    mouth_width = 0.17
    mouth_height = 0.09
    mouth_top_z = hoop44_z - 0.035
    mouth = add_half_disc("Mouth", mouth_width, mouth_height, 0.03,
                          (0, front_y(0, 0.0), mouth_top_z), mat_mouth_in)
    parent_to_root(mouth)

    # White upper teeth: thin slab just under the flat top edge, slightly in front
    teeth_width, teeth_height, teeth_depth = 0.12, 0.025, 0.02
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, front_y(0, 0.012), mouth_top_z - teeth_height / 2.0 - 0.004))
    teeth = bpy.context.active_object
    teeth.name = "Teeth_Upper"
    teeth.scale = (teeth_width, teeth_depth, teeth_height)
    teeth.data.materials.append(mat_white)
    parent_to_root(teeth)

    # ---- Logo zone (three gold pieces) ----
    logo_center_z = (hoop44_z + (body_top_z - 0.76 * BODY_H)) / 2.0  # between hoop44 and hoop76
    # Actually hoop76_z = body_top_z - 0.76 * BODY_H
    hoop76_z = body_top_z - 0.76 * BODY_H
    logo_center_z = (hoop44_z + hoop76_z) / 2.0

    # Badge: disc on left (-X), diameter 0.26, short cylinder rotated to face front
    badge_diameter = 0.26
    badge_radius = badge_diameter / 2.0
    badge_x = -0.25
    badge_yaw = math.atan2(badge_x, BODY_R)
    badge = add_cylinder(
        "Logo_Badge",
        radius=badge_radius,
        depth=0.035,
        location=(badge_x, front_y(badge_x, -0.012), logo_center_z),  # pressed in so the flat disc follows the curve
        rotation_euler=(math.radians(90), 0, badge_yaw),  # axis to Y, then yaw
        material=mat_gold_light
    )
    parent_to_root(badge)

    # Word bars on right: two curved panels with gap
    word_width = 0.48
    word_height = 0.075
    gap = 0.03
    radius_panel = BODY_R + BULGE + 0.002  # sit on the bulged fabric
    # Calculate angular positions to cover x from -0.08 to +0.40 approx.
    # We'll set x_center for first panel so its left edge is near -0.08
    left_angle = math.asin(-0.08 / radius_panel)  # approx -0.159 rad
    half_ang = (word_width / 2.0) / radius_panel  # approx 0.476 rad
    x_center1 = left_angle + half_ang  # approx 0.317 rad
    # second panel center = x_center1 + (word_width + gap) / radius_panel
    # two-line wordmark: same horizontal position, stacked vertically
    word1 = add_front_panel(
        "Logo_Word1",
        word_width,
        word_height,
        logo_center_z + (word_height + gap) / 2.0,
        radius_panel,
        material=mat_gold,
        thickness=0.012,
        x_center=x_center1
    )
    parent_to_root(word1)
    word2 = add_front_panel(
        "Logo_Word2",
        word_width,
        word_height,
        logo_center_z - (word_height + gap) / 2.0,
        radius_panel,
        material=mat_gold,
        thickness=0.012,
        x_center=x_center1
    )
    parent_to_root(word2)

    # ---- Arms (Bezier curves) ----
    shoulder_z = body_top_z - SHOULDER_FROM_TOP * BODY_H  # 40% from top
    hip_z = body_top_z - HIP_FROM_TOP * BODY_H            # 80% from top

    # Character's LEFT arm (+X), raised and waving: hand above/outside the lid
    left_arm_points = [
        (BODY_R - 0.02, 0.0, shoulder_z),
        (0.72, -0.02, shoulder_z + 0.05),
        (0.86, -0.05, shoulder_z + 0.35),
        (0.80, -0.08, body_top_z + 0.12),
    ]
    parent_to_root(add_bezier_curve("Arm_Left", left_arm_points, ARM_RADIUS, mat_arms_legs))

    # Character's RIGHT arm (-X), hanging down, hand near the hip
    right_arm_points = [
        (-(BODY_R - 0.02), 0.0, shoulder_z),
        (-0.66, -0.02, shoulder_z - 0.10),
        (-0.68, -0.04, hip_z + 0.15),
        (-0.62, -0.05, hip_z + 0.02),
    ]
    parent_to_root(add_bezier_curve("Arm_Right", right_arm_points, ARM_RADIUS, mat_arms_legs))

    # ---- Gloves (cuff + palm + 4 stubby fingers) ----
    for o in add_glove("Left", left_arm_points, mat_white) + add_glove("Right", right_arm_points, mat_white):
        parent_to_root(o)

    # ---- Legs (Bezier curves, straight down) ----
    # Legs are spread a bit wider than 0.25 so the 0.34-wide shoes do not overlap.
    leg_x = 0.19
    for side, sx in (("Left", 1), ("Right", -1)):
        leg = add_bezier_curve(f"Leg_{side}",
                               [(sx * leg_x, 0, leg_top_z + 0.05), (sx * leg_x, 0, leg_bottom_z - 0.03)],
                               LEG_RADIUS, mat_arms_legs)
        parent_to_root(leg)

    # ---- Shoes (big round white shoes, bottoms on Z=0) ----
    for side, sx in (("Left", 1), ("Right", -1)):
        shoe = add_ellipsoid(f"Shoe_{side}", (SHOE_WIDTH, SHOE_LENGTH, SHOE_HEIGHT),
                             (sx * (leg_x + 0.01), -SHOE_FORWARD, SHOE_HEIGHT / 2.0), mat_white)
        shoe.rotation_euler = (0, 0, sx * math.radians(8))   # toes slightly out
        parent_to_root(shoe)

    # ---- Ground plane ----
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0,0,0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground_mat = make_material("M_Ground", "#8E9196", roughness=0.9)
    ground.data.materials.append(ground_mat)

    # ---- Camera target (character centre) ----
    max_z = body_top_z + 0.35  # raised glove sits above the lid
    mid_z = max_z / 2.0
    target = bpy.data.objects.new("Camera_Target", None)
    bpy.context.collection.objects.link(target)
    target.location = (0, 0, mid_z)

    # ---- Lighting: 3-point area lights aimed at the character ----
    def add_area(name, loc, energy, size):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        c = lo.constraints.new('TRACK_TO')
        c.target = target
        c.track_axis = 'TRACK_NEGATIVE_Z'
        c.up_axis = 'UP_Y'
        return lo
    add_area("Key_Light", (-2.5, -3.0, 3.2), 380, 2.5)   # front-left, above
    add_area("Fill_Light", (2.8, -2.5, 1.8), 140, 3.0)   # front-right
    add_area("Rim_Light", (0.5, 3.0, 2.8), 300, 2.0)     # behind

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
    cam_dist = 4.4
    cam_obj.location = (0, -cam_dist, mid_z)

    scene.camera = cam_obj

    # ---- World background ----
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        bg = world.node_tree.nodes.new('ShaderNodeBackground')
        world.node_tree.links.new(bg.outputs['Background'], world.node_tree.nodes['World Output'].inputs['Surface'])
    bg.inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs['Strength'].default_value = 0.45
    scene.world = world

    # ---- Render settings ----
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    # Standard view transform so placeholder colours match their hex values
    scene.view_settings.view_transform = 'Standard'

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
