"""Synergist mascot - detailed model (step 4).

Run headless:
  blender.exe -b --factory-startup --python scripts/02_model.py -- <project_root> [sections]
sections: comma list of body,limbs,gloves,shoes,face,logo (default: all that exist).

Character faces -Y, Z up, stands on Z=0. Viewer's left = -X = character's RIGHT side.
Proportions come from the approved blockout v3 (01_blockout.py).
Each build_* section is drafted by Ollama and reviewed before it is merged here.
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector, Matrix

# ----------------------------------------------------------------------------
# Approved proportions (blockout v3)
# ----------------------------------------------------------------------------
BODY_R = 0.5
BODY_H = 1.26
BULGE = 0.015
SHOE_W, SHOE_L, SHOE_H = 0.34, 0.45, 0.20
SHOE_FORWARD = 0.10
LEG_LEN = 0.17 * BODY_H
LEG_X = 0.19
BODY_BOTTOM = SHOE_H + LEG_LEN
BODY_TOP = BODY_BOTTOM + BODY_H
HOOP_PCTS = [0.29, 0.44, 0.76, 0.97]
HOOP_MAJOR, HOOP_MINOR = 0.505, 0.025
LID_RIM_MAJOR, LID_RIM_MINOR = 0.47, 0.055
ARM_RADIUS_BLOCKOUT = 0.035
SHOULDER_FROM_TOP, HIP_FROM_TOP = 0.50, 0.80
FACE_X = 0.03
LOGO_X = 0.04


def hoop_z(pct):
    """World Z of a hoop given its fraction from the top of the body."""
    return BODY_TOP - pct * BODY_H


def bulge_radius(z):
    """Body radius at height z: BODY_R at hoops/top/bottom, bulging by BULGE between them."""
    bounds = sorted([BODY_BOTTOM, BODY_TOP] + [hoop_z(p) for p in HOOP_PCTS])
    for z0, z1 in zip(bounds, bounds[1:]):
        if z0 <= z <= z1 and z1 - z0 > 1e-9:
            return BODY_R + BULGE * math.sin(math.pi * (z - z0) / (z1 - z0))
    return BODY_R


SHOULDER_Z = BODY_TOP - SHOULDER_FROM_TOP * BODY_H
HIP_Z = BODY_TOP - HIP_FROM_TOP * BODY_H

# Arm paths from blockout v3 (bezier control points, AUTO handles)
ARM_WAVE_POINTS = [  # character's RIGHT arm (-X), waving, open palm
    (-(BODY_R - 0.02), -0.08, SHOULDER_Z),
    (-0.72, -0.02, SHOULDER_Z + 0.05),
    (-0.86, -0.05, SHOULDER_Z + 0.35),
    (-0.80, -0.10, BODY_TOP + 0.12),
]
ARM_REST_POINTS = [  # character's LEFT arm (+X), resting, hand at hip
    (BODY_R - 0.02, -0.08, SHOULDER_Z),
    (0.66, -0.02, SHOULDER_Z - 0.10),
    (0.68, -0.04, HIP_Z + 0.15),
    (0.62, -0.05, HIP_Z + 0.02),
]

# ----------------------------------------------------------------------------
# Materials (placeholders)
# ----------------------------------------------------------------------------
COLORS = {
    "M_Body": ("#1A3AAE", 0.85, 0.0),
    "M_Hoop": ("#1A3AAE", 0.85, 0.0),  # darkened below
    "M_Navy": ("#101629", 0.70, 0.0),
    "M_White": ("#F2F2F2", 0.75, 0.0),
    "M_Black": ("#0A0A0A", 0.60, 0.0),
    "M_Gold": ("#D5B268", 0.35, 0.6),
    "M_GoldLight": ("#EED295", 0.35, 0.6),
    "M_MouthIn": ("#4A1410", 0.80, 0.0),
    "M_Tongue": ("#C0504D", 0.60, 0.0),
    "M_Felt": ("#0A0A0A", 0.95, 0.0),
    "M_Ground": ("#8E9196", 0.90, 0.0),
}


def hex_to_linear(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], 1.0)


def make_materials():
    mats = {}
    for name, (hx, rough, metal) in COLORS.items():
        m = bpy.data.materials.new(name)
        if hasattr(m, "use_nodes") and not m.node_tree:
            m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        col = hex_to_linear(hx)
        if name == "M_Hoop":
            col = (col[0] * 0.85, col[1] * 0.85, col[2] * 0.85, 1.0)
        bsdf.inputs["Base Color"].default_value = col
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if metal == 0.0 and "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.2
        m.diffuse_color = col
        mats[name] = m
    return mats


# ----------------------------------------------------------------------------
# Shared helpers (sections may use these)
# ----------------------------------------------------------------------------
ROOT_NAME = "Mascot_Root"


def new_object_from_bmesh(name, bm, material=None, smooth=True, parent=True):
    """Write bm into a new mesh object, link it, parent to Mascot_Root, free bm."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if material is not None:
        me.materials.append(material)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if parent:
        obj.parent = bpy.data.objects[ROOT_NAME]
    return obj


def link_object(obj, parent=True):
    if obj.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(obj)
    if parent:
        obj.parent = bpy.data.objects[ROOT_NAME]
    return obj


def add_subsurf(obj, viewport=1, render=2):
    mod = obj.modifiers.new("Subdivision", "SUBSURF")
    mod.levels = viewport
    mod.render_levels = render
    return mod


def lathe_rings(bm, profile, segments, phase=0.0):
    """profile: list of (radius, z) bottom->top (or any order). Returns list of vertex rings.
    Vertex j of each ring is at angle phase + 2*pi*j/segments, measured from +X toward +Y."""
    rings = []
    for r, z in profile:
        ring = []
        for j in range(segments):
            a = phase + 2.0 * math.pi * j / segments
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    return rings


def bridge_rings(bm, rings, closed=False):
    """Quad faces between consecutive rings (each ring is a closed loop of equal length)."""
    n = len(rings[0])
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for j in range(n):
            k = (j + 1) % n
            bm.faces.new((a[j], a[k], b[k], b[j]))


# ----------------------------------------------------------------------------
# SECTIONS (each returns a list of created objects)
# ----------------------------------------------------------------------------
SECTION_BUILDERS = []  # (name, function), appended by each section block

# >>> SECTION body
def build_body(mats):
    """Build the plush oil-drum body, hoops, lid rim, and lid top (all-quad)."""
    # Local helpers ----------------------------------------------------------
    def make_tube_ring(name, major_r, minor_r, center_z, n_major, n_minor, z_scale, seam_depth, mat):
        """Create a rolled fabric tube (torus) with elliptical cross‑section and seam groove."""
        bm = bmesh.new()
        rings = []
        for i in range(n_major):
            major_angle = 2.0 * math.pi * i / n_major
            radial_dir = Vector((math.cos(major_angle), math.sin(major_angle), 0.0))
            ring = []
            for j in range(n_minor):
                minor_angle = 2.0 * math.pi * j / n_minor
                cross_radial = math.cos(minor_angle)
                cross_z = math.sin(minor_angle) * z_scale
                # Base torus point
                point = (
                    center_z * Vector((0, 0, 1))
                    + major_r * radial_dir
                    + minor_r * (cross_radial * radial_dir + cross_z * Vector((0, 0, 1)))
                )
                # Seam groove on outer equator (minor_angle = 0)
                da_seam = min(minor_angle, 2.0 * math.pi - minor_angle)
                if da_seam < 0.25:
                    dent = seam_depth * (1 - (da_seam / 0.25) ** 2) ** 2
                    point = point - dent * radial_dir
                v = bm.verts.new(point)
                ring.append(v)
            rings.append(ring)
        bridge_rings(bm, rings, closed=True)
        obj = new_object_from_bmesh(name, bm, material=mat, smooth=True, parent=True)
        add_subsurf(obj, 1, 2)
        return obj

    def quad_disk_cap(bm, ring, center_z, dome=0.0, inner_rings=4):
        """Close an open ring with an all‑quad cap that morphs circle → square → grid."""
        N = len(ring)
        assert N % 4 == 0, "Ring length must be divisible by 4"
        R = math.sqrt(ring[0].co.x ** 2 + ring[0].co.y ** 2)
        r_sq = 0.5 * R

        # Create intermediate rings morphing from circle to square (radial projection)
        all_rings = [ring]  # original circle
        for i in range(1, inner_rings + 1):
            t = i / inner_rings
            new_ring = []
            for v in ring:
                a = math.atan2(v.co.y, v.co.x)
                # Circle point
                cx, cy = R * math.cos(a), R * math.sin(a)
                # Square point (project onto square of radius r_sq)
                m = max(abs(math.cos(a)), abs(math.sin(a)))
                if m < 1e-8:
                    m = 1e-8
                sx, sy = r_sq * math.cos(a) / m, r_sq * math.sin(a) / m
                # Interpolate
                x = cx + t * (sx - cx)
                y = cy + t * (sy - cy)
                rho = math.sqrt(x * x + y * y)
                z = center_z + dome * (1 - (rho / R) ** 2)
                new_ring.append(bm.verts.new((x, y, z)))
            all_rings.append(new_ring)

        # Bridge between consecutive rings (original → first intermediate → … → square)
        for r1, r2 in zip(all_rings[:-1], all_rings[1:]):
            bridge_rings(bm, [r1, r2])  # not closed, just one strip

        # Now fill the square interior with a grid.
        # The last ring (all_rings[-1]) is the square border.
        square_ring = all_rings[-1]
        M = N // 4  # number of quads per side
        # Find corner indices (closest to 45°, 135°, 225°, 315°)
        corner_angles = [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]
        corner_indices = []
        for ca in corner_angles:
            best_idx = 0
            best_diff = 1e9
            for idx, v in enumerate(square_ring):
                a = math.atan2(v.co.y, v.co.x)
                diff = abs((a - ca + math.pi) % (2 * math.pi) - math.pi)  # wrapped angular distance
                if diff < best_diff:
                    best_diff = diff
                    best_idx = idx
            corner_indices.append(best_idx)

        # Reorder square_ring so that it starts at corner[0] and goes CCW
        start = corner_indices[0]
        ordered_ring = square_ring[start:] + square_ring[:start]

        # Split into four sides (each side includes both corners)
        # We need the indices of the other corners relative to the new order
        rel_corners = [(c - start) % N for c in corner_indices]
        rel_corners.sort()
        # Now rel_corners[0] = 0 (start), rel_corners[1], rel_corners[2], rel_corners[3]
        # Side lengths: between consecutive corners
        sides = []
        for i in range(4):
            c1 = rel_corners[i]
            c2 = rel_corners[(i + 1) % 4]
            if c2 > c1:
                side = ordered_ring[c1:c2 + 1]
            else:  # wrap around
                side = ordered_ring[c1:] + ordered_ring[:c2 + 1]
            sides.append(side)

        # Each side should have M+1 vertices (including corners)
        # We'll build a (M+1) x (M+1) grid of vertices, using border from sides.
        grid = [[None] * (M + 1) for _ in range(M + 1)]
        # Assign border vertices
        # sides[0] -> top row (i=0, j=0..M)
        # sides[1] -> right column (i=0..M, j=M)
        # sides[2] -> bottom row (i=M, j=0..M) reversed
        # sides[3] -> left column (i=0..M, j=0) reversed
        for j in range(M + 1):
            grid[0][j] = sides[0][j]  # top
        for i in range(M + 1):
            grid[i][M] = sides[1][i]  # right
        for j in range(M + 1):
            grid[M][M - j] = sides[2][j]  # bottom (reversed)
        for i in range(M + 1):
            grid[M - i][0] = sides[3][i]  # left (reversed)

        # Create interior vertices by bilinear interpolation using row/column averages
        for i in range(1, M):
            for j in range(1, M):
                # Row interpolation: between left (i,0) and right (i,M)
                left = grid[i][0].co
                right = grid[i][M].co
                row_point = left + (j / M) * (right - left)
                # Column interpolation: between top (0,j) and bottom (M,j)
                top = grid[0][j].co
                bottom = grid[M][j].co
                col_point = top + (i / M) * (bottom - top)
                # Average
                pos = (row_point + col_point) / 2.0
                rho_in = math.sqrt(pos.x * pos.x + pos.y * pos.y)
                pos.z = center_z + dome * (1 - (rho_in / R) ** 2)  # keep the dome inside the square
                grid[i][j] = bm.verts.new(pos)

        # Create quads
        for i in range(M):
            for j in range(M):
                v0 = grid[i][j]
                v1 = grid[i + 1][j]
                v2 = grid[i + 1][j + 1]
                v3 = grid[i][j + 1]
                bm.faces.new((v0, v1, v2, v3))

    # ------------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------------
    SEGMENTS = 64
    bm = bmesh.new()

    # Compute z list with uneven spacing and grooves
    body_bottom = BODY_BOTTOM
    body_top = BODY_TOP
    zone_start = BODY_TOP - 0.50 * BODY_H
    zone_end = BODY_TOP - 0.25 * BODY_H

    z_values = []
    # Region 1: bottom to zone_start
    length = zone_start - body_bottom
    steps = max(1, round(length / 0.02))
    for k in range(steps + 1):
        z_values.append(body_bottom + (zone_start - body_bottom) * k / steps)
    # Region 2: front face zone
    length = zone_end - zone_start
    steps = max(1, round(length / 0.0126))
    for k in range(steps + 1):
        z_values.append(zone_start + (zone_end - zone_start) * k / steps)
    # Region 3: zone_end to top
    length = body_top - zone_end
    steps = max(1, round(length / 0.02))
    for k in range(steps + 1):
        z_values.append(zone_end + (body_top - zone_end) * k / steps)

    # Remove duplicates (within 1e-6)
    z_values.sort()
    unique_z = []
    for z in z_values:
        if not unique_z or abs(z - unique_z[-1]) > 1e-6:
            unique_z.append(z)
    z_values = unique_z

    # Add groove extra rings
    hoop_heights = [hoop_z(pct) for pct in HOOP_PCTS]
    groove_centers = []
    for hz in hoop_heights:
        for s in (-1, 1):
            center = hz + s * HOOP_MINOR * 0.95
            groove_centers.append(center)
            z_values.append(center)
            z_values.append(center - 0.004)
            z_values.append(center + 0.004)

    # Add bottom/top edge rings
    z_values.append(BODY_BOTTOM + 0.012)
    z_values.append(BODY_BOTTOM)
    z_values.append(BODY_TOP - 0.012)
    z_values.append(BODY_TOP)

    # Sort and remove duplicates, but protect groove centers
    z_values.sort()
    final_z = []
    groove_center_set = set(round(gc, 6) for gc in groove_centers)
    for z in z_values:
        if not final_z or abs(z - final_z[-1]) > 0.0015:
            final_z.append(z)
        else:
            # If z is a groove center, we must keep it (replace previous if needed)
            if round(z, 6) in groove_center_set and abs(z - final_z[-1]) <= 0.0015:
                final_z[-1] = z  # keep the exact center
    z_list = final_z

    # Helper to compute body radius at a given z (with grooves and edge adjustments)
    def get_radius(z):
        r = bulge_radius(z)
        # Grooves
        for hz in hoop_heights:
            for s in (-1, 1):
                center = hz + s * HOOP_MINOR * 0.95
                d = z - center
                if abs(d) < 0.006:
                    depth = 0.006
                    r -= depth * (1 - (d / 0.006) ** 2) ** 2
        # Seam-rolled top/bottom edges: smooth inward roll over the last 0.02
        for d_edge in (z - BODY_BOTTOM, BODY_TOP - z):
            if d_edge < 0.02:
                r -= 0.03 * (1 - max(d_edge, 0.0) / 0.02) ** 2
        return r

    # Create rings (bottom to top)
    rings = []
    for z in z_list:
        ring = []
        r_base = get_radius(z)
        for j in range(SEGMENTS):
            a = -math.pi / 2 + 2.0 * math.pi * j / SEGMENTS
            # Back seam adjustment
            da = abs(a - math.pi / 2)
            if da > math.pi:
                da = 2 * math.pi - da
            r = r_base
            if da < 0.12:
                r -= 0.010 * (1 - (da / 0.12) ** 2) ** 2  # vertical back seam
            x = r * math.cos(a)
            y = r * math.sin(a)
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)

    # Bridge rings to form side surface
    bridge_rings(bm, rings)

    # Cap bottom and top
    quad_disk_cap(bm, rings[0], BODY_BOTTOM, dome=0.0, inner_rings=4)
    quad_disk_cap(bm, rings[-1], BODY_TOP, dome=0.0, inner_rings=4)

    # Recalculate normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    body_obj = new_object_from_bmesh("Body", bm, material=mats["M_Body"], smooth=True, parent=True)
    add_subsurf(body_obj, 1, 2)

    # ------------------------------------------------------------------------
    # Hoops
    # ------------------------------------------------------------------------
    hoops = []
    for pct in HOOP_PCTS:
        name = f"Hoop_{round(pct * 100)}"
        hoop_obj = make_tube_ring(
            name,
            major_r=HOOP_MAJOR,
            minor_r=HOOP_MINOR,
            center_z=hoop_z(pct),
            n_major=32,
            n_minor=24,
            z_scale=0.85,
            seam_depth=0.003,
            mat=mats["M_Hoop"],
        )
        hoops.append(hoop_obj)

    # ------------------------------------------------------------------------
    # Lid Rim
    # ------------------------------------------------------------------------
    lid_rim_obj = make_tube_ring(
        "Lid_Rim",
        major_r=LID_RIM_MAJOR,
        minor_r=LID_RIM_MINOR,
        center_z=BODY_TOP + 0.02,
        n_major=48,
        n_minor=24,
        z_scale=1.0,
        seam_depth=0.004,
        mat=mats["M_Hoop"],
    )

    # ------------------------------------------------------------------------
    # Lid Top
    # ------------------------------------------------------------------------
    bm_top = bmesh.new()
    ring_top = []
    top_radius = LID_RIM_MAJOR - 0.01
    top_z = BODY_TOP + 0.03
    for j in range(48):
        a = -math.pi / 2 + 2.0 * math.pi * j / 48
        x = top_radius * math.cos(a)
        y = top_radius * math.sin(a)
        ring_top.append(bm_top.verts.new((x, y, top_z)))
    quad_disk_cap(bm_top, ring_top, top_z, dome=0.035, inner_rings=6)
    bmesh.ops.recalc_face_normals(bm_top, faces=bm_top.faces)
    bm_top.normal_update()
    if sum(f.normal.z for f in bm_top.faces) < 0:  # open disc: make it face up
        bmesh.ops.reverse_faces(bm_top, faces=bm_top.faces)

    # Seam ring groove on lid top
    target_rho = 0.85 * top_radius
    for v in bm_top.verts:
        rho = math.sqrt(v.co.x ** 2 + v.co.y ** 2)
        diff = rho - target_rho
        if abs(diff) < 0.012:
            falloff = 0.004 * (1 - (diff / 0.012) ** 2) ** 2
            v.co.z -= falloff

    lid_top_obj = new_object_from_bmesh("Lid_Top", bm_top, material=mats["M_Body"], smooth=True, parent=True)
    # Solidify before Subdivision
    solidify_mod = lid_top_obj.modifiers.new("Solidify", 'SOLIDIFY')
    solidify_mod.thickness = 0.01
    solidify_mod.offset = -1
    add_subsurf(lid_top_obj, 1, 2)

    # ------------------------------------------------------------------------
    # Return all objects
    # ------------------------------------------------------------------------
    return [body_obj] + hoops + [lid_rim_obj, lid_top_obj]


SECTION_BUILDERS.append(("body", build_body))
# <<< SECTION body


# ----------------------------------------------------------------------------
# Scene, camera, lights, renders
# ----------------------------------------------------------------------------
VIEWS = [  # name, camera azimuth (0 = front at -Y, positive turns toward +X)
    ("front", 0.0),
    ("threequarter", -45.0),  # waving-arm side (viewer's left)
    ("side", 90.0),
    ("back", 180.0),
]


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for d in list(coll):
            coll.remove(d)


def setup_scene(mats):
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    root = bpy.data.objects.new(ROOT_NAME, None)
    scene.collection.objects.link(root)

    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    ground.data.materials.append(mats["M_Ground"])

    mid_z = (BODY_TOP + 0.35) / 2.0
    target = bpy.data.objects.new("Camera_Target", None)
    scene.collection.objects.link(target)
    target.location = (0, 0, mid_z)

    def area(name, loc, energy, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new(name, ld)
        scene.collection.objects.link(lo)
        lo.location = loc
        c = lo.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"

    area("Key_Light", (-2.5, -3.0, 3.2), 380, 2.5)
    area("Fill_Light", (2.8, -2.5, 1.8), 140, 3.0)
    area("Rim_Light", (0.5, 3.0, 2.8), 300, 2.0)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam)
    cam.data.lens = 50
    tc = cam.constraints.new("TRACK_TO")
    tc.target, tc.track_axis, tc.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    scene.camera = cam

    world = bpy.data.worlds.new("World")
    scene.world = world
    if hasattr(world, "use_nodes") and not world.node_tree:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.6, 0.6, 0.6, 1.0)
    bg.inputs["Strength"].default_value = 0.45

    r = scene.render
    r.resolution_x = r.resolution_y = 1024
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            r.engine = eng
            break
        except TypeError:
            continue
    return cam, target


def render_views(cam, target, render_dir, prefix):
    scene = bpy.context.scene
    mid_z = target.location.z
    dist = 4.4
    paths = []
    for name, az in VIEWS:
        a = math.radians(az)
        cam.data.lens = 50
        target.location = (0, 0, mid_z)
        cam.location = (dist * math.sin(a), -dist * math.cos(a), mid_z)
        scene.render.filepath = os.path.join(render_dir, f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        paths.append(scene.render.filepath)
    # face close-up
    face_z = (hoop_z(0.29) + hoop_z(0.44)) / 2.0
    target.location = (FACE_X, 0, face_z - 0.03)
    cam.data.lens = 50
    cam.location = (FACE_X + 0.25, -2.0, face_z + 0.10)
    scene.render.filepath = os.path.join(render_dir, f"{prefix}_face.png")
    bpy.ops.render.render(write_still=True)
    paths.append(scene.render.filepath)
    target.location = (0, 0, mid_z)
    cam.data.lens = 50
    return paths


def triangle_counts(objs):
    """(viewport, render) triangle counts of the evaluated mascot objects."""
    out = []
    for use_render in (False, True):
        saved = []
        for o in objs:
            for m in o.modifiers:
                if m.type == "SUBSURF":
                    saved.append((m, m.levels))
                    if use_render:
                        m.levels = m.render_levels
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        tris = 0
        for o in objs:
            if o.type not in {"MESH", "CURVE", "FONT"}:
                continue
            eo = o.evaluated_get(dg)
            me = eo.to_mesh()
            if me is not None:
                me.calc_loop_triangles()
                tris += len(me.loop_triangles)
                eo.to_mesh_clear()
        for m, lv in saved:
            m.levels = lv
        out.append(tris)
    return tuple(out)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    root_dir = os.path.abspath(argv[0]) if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wanted = set(argv[1].split(",")) if len(argv) > 1 else None
    blend_dir = os.path.join(root_dir, "blend")
    render_dir = os.path.join(root_dir, "renders")
    os.makedirs(blend_dir, exist_ok=True)
    os.makedirs(render_dir, exist_ok=True)

    clear_scene()
    mats = make_materials()
    cam, target = setup_scene(mats)

    built = []
    for name, fn in SECTION_BUILDERS:
        if wanted is None or name in wanted:
            objs = fn(mats) or []
            print(f"[02_model] section {name}: {len(objs)} objects")
            built.extend(objs)

    paths = render_views(cam, target, render_dir, "model")
    mascot = [o for o in bpy.data.objects if o.parent is not None and o.parent.name == ROOT_NAME]
    vp, rn = triangle_counts(mascot)
    print(f"[02_model] TRIANGLES viewport={vp} render={rn} objects={len(mascot)}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(blend_dir, "mascot_model.blend"))
    for p in paths:
        print(f"[02_model] render {p}")


if __name__ == "__main__":
    main()
