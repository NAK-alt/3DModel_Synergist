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
SHOULDER_FROM_TOP = 0.5  # updated to 50% from top
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

# Face - updated dimensions
FACE_X = 0.03            # whole face shifted slightly to viewer's right
EYE_W = 0.20
EYE_H = 0.30
EYE_DEPTH = 0.06
EYE_SPACING = 0.14       # distance from FACE_X to eye centre (full size)
EYE_FLATTEN_Y = 0.02     # not used directly, but kept for reference
PUPIL_W = 0.11
PUPIL_H = 0.15
PUPIL_DEPTH = 0.04
MOUTH_WIDTH = 0.22
MOUTH_HEIGHT = 0.11
MOUTH_FLATTEN_Y = 0.02   # not used
TEETH_WIDTH = 0.16
TEETH_HEIGHT = 0.03
TEETH_DEPTH = 0.02
TONGUE_W = 0.10
TONGUE_H = 0.04
TONGUE_DEPTH = 0.02

# Logo
LOGO_X = 0.04            # centred slightly right
LOGO_WIDTH = 0.46        # word bar width
LOGO_HEIGHT = 0.07       # word bar height
LOGO_GAP = 0.03          # gap between stacked bars
BADGE_MAJOR_R = 0.11
BADGE_MINOR_R = 0.018
BADGE_SPHERE_R = 0.035

# Materials (hex sRGB)
COL_BODY = "#1A3AAE"     # updated
COL_HOOP = "#1A3AAE"     # will be multiplied by 0.85
COL_ARMS_LEGS = "#101629"
COL_WHITE = "#F2F2F2"
COL_BLACK = "#0A0A0A"
COL_GOLD = "#D5B268"
COL_GOLD_LIGHT = "#EED295"  # added
COL_MOUTH_IN = "#4A1410"    # updated dark red-brown
COL_TONGUE = "#C0504D"      # added

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

def add_open_hand(side, arm_points, mat):
    """Open palm with spread fingers, facing camera (-Y)."""
    end = mathutils.Vector(arm_points[-1])
    d = (end - mathutils.Vector(arm_points[-2])).normalized()
    # Cuff torus oriented along arm direction
    rot_cuff = d.to_track_quat('Z', 'Y').to_euler()
    cuff = add_torus(f"Glove_{side}_Cuff", major_radius=0.055, minor_radius=0.025,
                     location=end, rotation_euler=rot_cuff, material=mat)
    objs = [cuff]
    # Palm centre: 0.10 beyond wrist along arm direction
    palm_c = end + d * 0.10
    # Palm ellipsoid, full size (0.17 wide, 0.06 deep, 0.16 tall), facing -Y (no yaw to arm)
    palm = add_ellipsoid(f"Glove_{side}_Palm", (0.17, 0.06, 0.16), palm_c, mat)
    objs.append(palm)
    # Fingers: capsule-like ellipsoids, fanned upward from palm's top edge
    # Angles from vertical (rotate about Y): -30, -10, 10, 30 degrees
    finger_angles = [-math.radians(30), -math.radians(10), math.radians(10), math.radians(30)]
    for i, ang in enumerate(finger_angles):
        # Base at top of palm: palm centre z + palm height/2
        base_z = palm_c.z + 0.08  # half of 0.16
        # Offset along X from palm centre based on angle and spacing
        # Use approximate: fingers positioned at palm top edge, spread horizontally
        # We'll place them along the top edge with offsets: -0.06, -0.02, 0.02, 0.06
        x_off = -0.06 + i * 0.04
        # Position finger base at (palm_c.x + x_off, palm_c.y, base_z)
        finger_base = mathutils.Vector((palm_c.x + x_off, palm_c.y, base_z))
        # Rotate about Y by ang: direction vector initially +Z, rotate about Y
        dir_vec = mathutils.Vector((0, 0, 1))
        rot_mat = mathutils.Matrix.Rotation(ang, 4, 'Y')
        dir_vec = rot_mat @ dir_vec
        # Finger centre = base + dir_vec * (finger length/2)
        finger_len = 0.10  # full size
        finger_centre = finger_base + dir_vec * (finger_len / 2.0)
        # Finger ellipsoid: (0.045, 0.04, 0.10) but oriented? We'll set rotation to align with dir_vec.
        # Use rotation_euler from a quaternion that rotates +Z to dir_vec
        quat = mathutils.Vector((0,0,1)).rotation_difference(dir_vec).to_euler()
        finger = add_ellipsoid(f"Glove_{side}_Finger{i+1}", (0.045, 0.04, finger_len), finger_centre, mat)
        finger.rotation_euler = quat
        objs.append(finger)
    # Thumb: (0.045 x 0.04 x 0.08) pointing out sideways at 70 degrees toward the outside
    # Outside depends on side: for left hand (character's left, +X) outside is +X? Actually thumb points outward, away from palm.
    # We'll assume side "Left" means +X side, "Right" means -X side.
    if side == "Left":
        outward_sign = 1
    else:
        outward_sign = -1
    # Thumb base at side of palm, lower part: palm_c.x + outward_sign * (palm_width/2), z near palm bottom
    thumb_base = mathutils.Vector((palm_c.x + outward_sign * 0.08, palm_c.y, palm_c.z - 0.05))
    # Angle 70 degrees from vertical, rotated about Y: direction vector initially (1,0,0) rotated about Y by 70 deg? Or from vertical?
    # "pointing out sideways at 70 degrees toward the outside" - likely from vertical, rotated outward.
    # We'll create direction vector: start with +Z, rotate about Y by 70 degrees, then also rotate about Z to point outward? Simpler: use quaternion from +Z to direction that is mostly +Z with some X component.
    # We'll define direction as (outward_sign * sin(70°), 0, cos(70°))
    dir_vec_thumb = mathutils.Vector((outward_sign * math.sin(math.radians(70)), 0, math.cos(math.radians(70))))
    thumb_len = 0.08
    thumb_centre = thumb_base + dir_vec_thumb * (thumb_len / 2.0)
    quat_thumb = mathutils.Vector((0,0,1)).rotation_difference(dir_vec_thumb).to_euler()
    thumb = add_ellipsoid(f"Glove_{side}_Thumb", (0.045, 0.04, thumb_len), thumb_centre, mat)
    thumb.rotation_euler = quat_thumb
    objs.append(thumb)
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
    mat_body = make_material("M_Body", COL_BODY, roughness=0.85)  # updated roughness
    # Lower specular if input exists
    if "Specular IOR Level" in mat_body.node_tree.nodes["Principled BSDF"].inputs:
        mat_body.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.2

    mat_hoop = make_material("M_Hoop", COL_HOOP, roughness=0.8)
    # Darken hoop: multiply base color by 0.85
    mat_hoop.node_tree.nodes["Principled BSDF"].inputs['Base Color'].default_value = tuple(c * 0.85 for c in srgb_to_linear(COL_HOOP)[:3]) + (1.0,)
    mat_arms_legs = make_material("M_ArmsLegs", COL_ARMS_LEGS, roughness=0.6)
    mat_white = make_material("M_White", COL_WHITE, roughness=0.5)
    mat_black = make_material("M_Black", COL_BLACK, roughness=0.3)
    mat_gold = make_material("M_Gold", COL_GOLD, roughness=0.35, metallic=0.6)
    mat_gold_light = make_material("M_GoldLight", COL_GOLD_LIGHT, roughness=0.35, metallic=0.6)
    mat_mouth_in = make_material("M_MouthIn", COL_MOUTH_IN, roughness=0.5)
    mat_tongue = make_material("M_Tongue", COL_TONGUE, roughness=0.4)

    # ---- Body positions ----
    shoe_top_z = SHOE_HEIGHT  # 0.2
    leg_bottom_z = shoe_top_z  # leg connects to shoe top
    leg_top_z = leg_bottom_z + LEG_LEN  # 0.2 + (0.17*1.26) = 0.2 + 0.2142 = 0.4142
    body_bottom_z = leg_top_z
    body_top_z = body_bottom_z + BODY_H  # 0.4142 + 1.26 = 1.6742

    # ---- Body (lathe mesh with bulge) ----
    hoop_z_list = [body_top_z - pct * BODY_H for pct in HOOP_PERCENTS]  # top to bottom order
    boundaries = sorted([body_bottom_z, body_top_z] + hoop_z_list)
    z = body_bottom_z
    profile = []
    step = 0.01
    while z <= body_top_z + 1e-6:
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

    # Eyes: much bigger
    eye_z = hoop29_z + 0.025 - EYE_H / 2.0   # top of eye 0.025 above hoop29
    eye_x_left = FACE_X + EYE_SPACING        # character's left = +X
    eye_x_right = FACE_X - EYE_SPACING       # character's right = -X

    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * EYE_SPACING + FACE_X   # eye centre x
        yaw = math.atan2(x, BODY_R)
        # Black outline (0.02 larger in width/height, 0.008 behind)
        outline = add_ellipsoid(
            f"Eye_{side}_Outline",
            (EYE_W + 0.02, EYE_DEPTH + 0.006, EYE_H + 0.02),
            (x, front_y(x, -0.008), eye_z),
            mat_black
        )
        outline.rotation_euler = (0, 0, yaw)
        parent_to_root(outline)
        # White sclera
        sclera = add_ellipsoid(
            f"Eye_{side}_Sclera",
            (EYE_W, EYE_DEPTH, EYE_H),
            (x, front_y(x, 0.02), eye_z),
            mat_white
        )
        sclera.rotation_euler = (0, 0, yaw)
        parent_to_root(sclera)
        # Pupil (shifted +0.03 in x, -0.02 in z, in front)
        pupil_x = x + 0.03
        pupil_z = eye_z - 0.02
        pupil = add_ellipsoid(
            f"Pupil_{side}",
            (PUPIL_W, PUPIL_DEPTH, PUPIL_H),
            (pupil_x, front_y(pupil_x, 0.055), pupil_z),
            mat_black
        )
        pupil.rotation_euler = (0, 0, yaw)
        parent_to_root(pupil)

    # Brows: thin arcs, top half only
    brow_major = 0.07
    brow_minor = 0.007
    eye_top = eye_z + EYE_H / 2.0
    brow_base_z = max(hoop29_z + 0.05, eye_top + 0.02)
    for side, sx in (("Left", 1), ("Right", -1)):
        x = sx * EYE_SPACING + FACE_X
        brow = add_torus(
            f"Brow_{side}",
            major_radius=brow_major,
            minor_radius=brow_minor,
            location=(x, front_y(x, 0.004), brow_base_z - 0.005),
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

    # Nose: black sphere, diameter 0.08
    nose_diameter = 0.08
    nose = add_sphere(
        "Nose",
        radius=nose_diameter / 2.0,
        location=(FACE_X, -(HOOP_MAJOR_R + HOOP_MINOR_R) - 0.03, hoop44_z),
        material=mat_black
    )
    parent_to_root(nose)

    # Mouth: D-shaped open smile
    mouth_top_z = hoop44_z - 0.05
    mouth = add_half_disc("Mouth", MOUTH_WIDTH, MOUTH_HEIGHT, 0.03,
                          (FACE_X, front_y(0, 0.0), mouth_top_z), mat_mouth_in)
    parent_to_root(mouth)

    # White upper teeth: thin slab under flat top edge
    bpy.ops.mesh.primitive_cube_add(size=1, location=(FACE_X, front_y(0, 0.012), mouth_top_z - TEETH_HEIGHT / 2.0 - 0.004))
    teeth = bpy.context.active_object
    teeth.name = "Teeth_Upper"
    teeth.scale = (TEETH_WIDTH, TEETH_DEPTH, TEETH_HEIGHT)
    teeth.data.materials.append(mat_white)
    parent_to_root(teeth)

    # Tongue hint
    tongue_z = mouth_top_z - 0.085
    tongue = add_ellipsoid(
        "Tongue",
        (TONGUE_W, TONGUE_DEPTH, TONGUE_H),
        (FACE_X, front_y(0, 0.02), tongue_z),  # slightly in front of mouth slab
        mat_tongue
    )
    parent_to_root(tongue)

    # ---- Logo zone ----
    hoop76_z = body_top_z - 0.76 * BODY_H
    mouth_bottom = mouth_top_z - MOUTH_HEIGHT
    logo_lower_z = mouth_bottom - 0.02
    logo_upper_z = hoop76_z + 0.03
    logo_center_z = (logo_lower_z + logo_upper_z) / 2.0

    # Badge: white ring with three gold spheres
    badge_x = LOGO_X - 0.25
    badge_yaw = math.atan2(badge_x, BODY_R)
    badge_ring = add_torus(
        "Logo_Badge_Ring",
        major_radius=BADGE_MAJOR_R,
        minor_radius=BADGE_MINOR_R,
        location=(badge_x, front_y(badge_x, 0.010), logo_center_z),  # forward enough that the flat ring's edges clear the curve
        rotation_euler=(math.radians(90), 0, badge_yaw),
        material=mat_white
    )
    parent_to_root(badge_ring)

    # Three gold spheres inside ring (triangle: top centre, two bottom)
    sphere_positions = [
        (badge_x, logo_center_z + 0.04),
        (badge_x - 0.04, logo_center_z - 0.04),
        (badge_x + 0.04, logo_center_z - 0.04)
    ]
    for i, (sx, sz) in enumerate(sphere_positions):
        sphere = add_sphere(
            f"Logo_Badge_Sphere_{i+1}",
            radius=BADGE_SPHERE_R,
            location=(sx, front_y(sx, 0.01), sz),
            material=mat_gold
        )
        parent_to_root(sphere)

    # Wordmark: two stacked curved bars, left edge at about LOGO_X - 0.10
    word_width = LOGO_WIDTH
    word_height = LOGO_HEIGHT
    gap = LOGO_GAP
    radius_panel = BODY_R + BULGE + 0.002
    left_x = LOGO_X - 0.10
    left_angle = math.asin(left_x / radius_panel)
    half_ang = (word_width / 2.0) / radius_panel
    x_center1 = left_angle + half_ang
    # Top bar: mat_gold_light, bottom bar: mat_gold
    word1 = add_front_panel(
        "Logo_Word1",
        word_width,
        word_height,
        logo_center_z + (word_height + gap) / 2.0,
        radius_panel,
        material=mat_gold_light,
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
    shoulder_z = body_top_z - SHOULDER_FROM_TOP * BODY_H  # 50% from top
    hip_z = body_top_z - HIP_FROM_TOP * BODY_H            # 80% from top

    # Character's RIGHT arm (-X), waving, open palm
    right_arm_points = [
        (-(BODY_R - 0.02), -0.08, shoulder_z),   # shoulder point
        (-0.72, -0.02, shoulder_z + 0.05),
        (-0.86, -0.05, shoulder_z + 0.35),
        (-0.80, -0.10, body_top_z + 0.12),       # hand above/outside lid
    ]
    parent_to_root(add_bezier_curve("Arm_Right", right_arm_points, ARM_RADIUS, mat_arms_legs))

    # Character's LEFT arm (+X), resting, glove
    left_arm_points = [
        (BODY_R - 0.02, -0.08, shoulder_z),      # shoulder point
        (0.66, -0.02, shoulder_z - 0.10),
        (0.68, -0.04, hip_z + 0.15),
        (0.62, -0.05, hip_z + 0.02),
    ]
    parent_to_root(add_bezier_curve("Arm_Left", left_arm_points, ARM_RADIUS, mat_arms_legs))

    # ---- Hands ----
    # Waving arm: open palm (Arm_Right)
    for o in add_open_hand("Right", right_arm_points, mat_white):
        parent_to_root(o)
    # Resting arm: glove (Arm_Left)
    for o in add_glove("Left", left_arm_points, mat_white):
        parent_to_root(o)

    # ---- Legs (Bezier curves, straight down) ----
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
