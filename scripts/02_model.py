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
PROJECT_ROOT = None  # set in main(); sections read refs/ files relative to it


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

# Shared tube helpers (moved out of build_limbs so gloves can reuse them)
def catmull_rom(points, samples):
    """Centripetal Catmull-Rom spline through points, resampled by arc length."""
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return pts
    # Phantom ends by reflection (duplicating the end points would divide by zero)
    pts = [2 * pts[0] - pts[1]] + pts + [2 * pts[-1] - pts[-2]]
    # Dense sampling per segment (20)
    dense = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(20):
            t = j / 20.0
            # Centripetal parameterization
            t0 = 0.0
            t1 = t0 + (p1 - p0).length ** 0.5
            t2 = t1 + (p2 - p1).length ** 0.5
            t3 = t2 + (p3 - p2).length ** 0.5
            t = t1 + (t2 - t1) * t
            # Interpolate
            A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
            B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
            C = (t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2
            dense.append(C)
    # Add last point (exact)
    dense.append(pts[-2])
    # Arc length resample
    lengths = [0.0]
    for i in range(1, len(dense)):
        lengths.append(lengths[-1] + (dense[i] - dense[i - 1]).length)
    total = lengths[-1]
    if total == 0.0:
        return [dense[0]] * samples
    step = total / (samples - 1)
    resampled = [dense[0]]
    target = step
    idx = 1
    while len(resampled) < samples - 1:
        while idx < len(dense) and lengths[idx] < target:
            idx += 1
        if idx >= len(dense):
            idx = len(dense) - 1
        if idx == 0:
            resampled.append(dense[0])
        else:
            t = (target - lengths[idx - 1]) / (lengths[idx] - lengths[idx - 1])
            resampled.append(dense[idx - 1].lerp(dense[idx], t))
        target += step
    resampled.append(dense[-1])
    return resampled

def sweep_tube(name, path_pts, radius, n_around, mat,
                extend_start=0.0, extend_end=0.0):
    """Create an all-quad tube along a path with parallel transport frames."""
    bm = bmesh.new()
    pts = [Vector(p) for p in path_pts]

    # Extend path
    if extend_start != 0.0:
        tangent_start = (pts[1] - pts[0]).normalized()
        new_start = pts[0] - tangent_start * extend_start
        pts = [new_start] + pts
    if extend_end != 0.0:
        tangent_end = (pts[-1] - pts[-2]).normalized()
        new_end = pts[-1] + tangent_end * extend_end
        pts = pts + [new_end]

    # Tangents
    tangents = []
    for i in range(len(pts)):
        if i == 0:
            tang = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            tang = (pts[-1] - pts[-2]).normalized()
        else:
            tang = (pts[i + 1] - pts[i - 1]).normalized()
        tangents.append(tang)

    # Initial normal
    up = Vector((0, 0, 1))
    if abs(tangents[0].dot(up)) > 0.99:
        up = Vector((1, 0, 0))
    normal = tangents[0].cross(up).normalized()
    binormal = tangents[0].cross(normal)

    # Rings
    rings = []
    for i, (pt, tang) in enumerate(zip(pts, tangents)):
        if i > 0:
            rot = tangents[i - 1].rotation_difference(tang)
            normal = rot @ normal
            normal = (normal - normal.dot(tang) * tang).normalized()
            binormal = tang.cross(normal)
        ring = []
        for j in range(n_around):
            angle = 2.0 * math.pi * j / n_around
            direction = math.cos(angle) * normal + math.sin(angle) * binormal
            ring.append(bm.verts.new(pt + radius * direction))
        rings.append(ring)

    # Bridge rings
    bridge_rings(bm, rings)

    # End caps (start and end)
    def cap_end(ring, end_pt, tangent, reverse):
        """Close one end with two tapered rings and an n-gon."""
        # direction outward: reverse=True means -tangent (start), else +tangent
        out_dir = -tangent if reverse else tangent
        # First taper ring at 60% radius, 0.4*radius out
        ring1 = []
        center1 = end_pt + out_dir * 0.4 * radius
        for v in ring:
            vec = v.co - center1
            # project onto plane perpendicular to tangent and scale
            proj = vec - vec.dot(tangent) * tangent
            if proj.length > 1e-6:
                proj = proj.normalized() * (0.6 * radius)
            else:
                proj = Vector((0, 0, 0))
            ring1.append(bm.verts.new(center1 + proj))
        # Second taper ring at 20% radius, 0.5*radius out
        ring2 = []
        center2 = end_pt + out_dir * 0.5 * radius
        for v in ring:
            vec = v.co - center2
            proj = vec - vec.dot(tangent) * tangent
            if proj.length > 1e-6:
                proj = proj.normalized() * (0.2 * radius)
            else:
                proj = Vector((0, 0, 0))
            ring2.append(bm.verts.new(center2 + proj))
        # Bridge original ring -> ring1 -> ring2
        bridge_rings(bm, [ring, ring1])
        bridge_rings(bm, [ring1, ring2])
        # N-gon from ring2
        bm.faces.new(ring2)

    # Start cap (reverse tangent)
    cap_end(rings[0], pts[0], tangents[0], reverse=True)
    # End cap (forward tangent)
    cap_end(rings[-1], pts[-1], tangents[-1], reverse=False)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object_from_bmesh(name, bm, material=mat, smooth=True, parent=True)
    add_subsurf(obj, 1, 2)
    return obj


# >>> SECTION limbs
def build_limbs(mats):
    """Rubber-hose arms and legs: all-quad tubes with n-gon end caps."""
    ARM_R = ARM_RADIUS_BLOCKOUT * 1.3
    LEG_R = 0.04 * 1.3
    N_AROUND = 16

    # Arms
    arm_right = sweep_tube(
        "Arm_Right",
        catmull_rom(ARM_WAVE_POINTS, 25),
        ARM_R, N_AROUND, mats["M_Navy"],
        extend_start=0.04, extend_end=0.03,
    )
    arm_left = sweep_tube(
        "Arm_Left",
        catmull_rom(ARM_REST_POINTS, 25),
        ARM_R, N_AROUND, mats["M_Navy"],
        extend_start=0.04, extend_end=0.03,
    )

    # Legs
    leg_top_z = BODY_BOTTOM + 0.04
    leg_bot_z = SHOE_H - 0.03
    leg_mid_z = (leg_top_z + leg_bot_z) / 2.0
    leg_points_left = [
        (LEG_X, 0, leg_top_z),
        (LEG_X, -0.008, leg_mid_z),
        (LEG_X, 0, leg_bot_z),
    ]
    leg_points_right = [
        (-LEG_X, 0, leg_top_z),
        (-LEG_X, -0.008, leg_mid_z),
        (-LEG_X, 0, leg_bot_z),
    ]
    leg_left = sweep_tube(
        "Leg_Left",
        catmull_rom(leg_points_left, 25),
        LEG_R, N_AROUND, mats["M_Navy"],
    )
    leg_right = sweep_tube(
        "Leg_Right",
        catmull_rom(leg_points_right, 25),
        LEG_R, N_AROUND, mats["M_Navy"],
    )

    return [arm_right, arm_left, leg_left, leg_right]


SECTION_BUILDERS.append(("limbs", build_limbs))
# <<< SECTION limbs

# >>> SECTION shoes
def build_shoes(mats):
    """Big plush cartoon shoes: all-quad cube-sphere base, deformed."""
    def _quad_ball(cuts):
        """Create an all-quad cube-sphere by subdividing a cube and normalizing."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.subdivide_edges(
            bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True
        )
        for v in bm.verts:
            v.co.normalize()
        return bm

    def _shape_shoe(bm):
        """Transform unit sphere vertices into shoe shape, bottom at z=0."""
        sole_level = -SHOE_H / 2.0 + 0.035
        z_seam = -SHOE_H / 2.0 + 0.045
        for v in bm.verts:
            x_u, y_u, z_u = v.co.x, v.co.y, v.co.z
            # Base ellipsoid
            x = x_u * SHOE_W / 2.0
            y = y_u * SHOE_L / 2.0
            z = z_u * SHOE_H / 2.0
            if z > 0:
                z *= 1.3  # puffier plush top; the flat sole takes height off the bottom
            # Toe bulge (front half, y < 0)
            if y_u < 0:
                t = -y_u  # 0..1
                t = t * t * (3.0 - 2.0 * t)  # smoothstep
                x *= 1.0 + 0.18 * t
                z *= 1.0 + 0.18 * t
                if z > 0:
                    z += 0.02 * t
            # Flat sole
            if z < sole_level:
                z = sole_level + (z - sole_level) * 0.15
            # Sole seam groove
            dz = z - z_seam
            if abs(dz) < 0.012:
                dent = 0.006 * (1.0 - (dz / 0.012) ** 2) ** 2  # absolute inward depth
                rho = max(math.hypot(x, y), 1e-6)
                x *= 1.0 - dent / rho
                y *= 1.0 - dent / rho
            v.co = Vector((x, y, z))
        # Translate lowest point to z=0
        min_z = min(v.co.z for v in bm.verts)
        for v in bm.verts:
            v.co.z -= min_z

    shoes = []
    for side, sign in (("Left", 1.0), ("Right", -1.0)):
        bm = _quad_ball(8)
        _shape_shoe(bm)
        # Apply placement: center, rotation
        center = Vector((sign * (LEG_X + 0.01), -SHOE_FORWARD, 0.0))
        angle = math.radians(8.0 * sign)  # +8 for left, -8 for right
        rot = Matrix.Rotation(angle, 3, 'Z')
        for v in bm.verts:
            v.co = rot @ v.co + center
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object_from_bmesh(
            f"Shoe_{side}", bm, material=mats["M_White"], smooth=True, parent=True
        )
        add_subsurf(obj, 1, 2)
        shoes.append(obj)
    return shoes


SECTION_BUILDERS.append(("shoes", build_shoes))
# <<< SECTION shoes

# >>> SECTION gloves
def build_gloves(mats):
    """Build plush cartoon gloves: puffy palm, thumb + 3 fingers, rolled cuff."""
    # Local helper: hand frame
    def _hand_frame(arm_points, palm_hint, thumb_hint):
        path = catmull_rom(arm_points, 25)
        wrist = path[-1]
        Z = (path[-1] - path[-2]).normalized()
        Y = palm_hint.copy()
        Y = (Y - Y.dot(Z) * Z).normalized()
        X = Y.cross(Z)
        thumb_sign = 1 if X.dot(thumb_hint) > 0 else -1
        M = Matrix((X, Y, Z)).transposed()  # columns X,Y,Z
        return wrist, M, thumb_sign

    # Helper to transform local point to world
    def to_world(local, wrist, M):
        return wrist + M @ Vector(local)

    # Build cuff in local space then transform
    def build_cuff(name, wrist, M):
        bm = bmesh.new()
        major_r = 0.062
        minor_r_radial = 0.026
        minor_r_z = 0.026 * 1.25
        center_z = 0.012
        n_major = 24
        n_minor = 12
        rings = []
        for i in range(n_major):
            m_angle = 2 * math.pi * i / n_major
            radial_dir = Vector((math.cos(m_angle), math.sin(m_angle), 0))
            ring = []
            for j in range(n_minor):
                a = 2 * math.pi * j / n_minor
                # Ellipse cross-section
                radial_offset = minor_r_radial * math.cos(a)
                z_offset = minor_r_z * math.sin(a)
                point = (
                    Vector((0, 0, center_z)) +
                    radial_dir * (major_r + radial_offset) +
                    Vector((0, 0, z_offset))
                )
                # Seam groove on outermost equator (a=0)
                da = min(abs(a), 2 * math.pi - abs(a))
                if da < 0.35:
                    dent = 0.003 * (1 - (da / 0.35) ** 2) ** 2
                    point -= dent * radial_dir
                # Transform to world
                world_pt = to_world(point, wrist, M)
                v = bm.verts.new(world_pt)
                ring.append(v)
            rings.append(ring)
        bridge_rings(bm, rings, closed=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object_from_bmesh(name, bm, material=mats["M_White"], smooth=True, parent=True)
        add_subsurf(obj, 1, 2)
        return obj

    # Build palm
    def build_palm(name, wrist, M):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=5, use_grid_fill=True)
        for v in bm.verts:
            v.co.normalize()
        # Scale and deform
        for v in bm.verts:
            x, y, z = v.co.x, v.co.y, v.co.z
            # Scale to local half-sizes
            x *= 0.085
            y *= 0.045
            z *= 0.080
            # Puffy back (y<0)
            if y < 0:
                y *= 1.15
            else:
                y *= 0.85
            # Centre lower than drafted (0.085) so the palm fills the cuff opening
            z += 0.072
            local_pt = Vector((x, y, z))
            world_pt = to_world(local_pt, wrist, M)
            v.co = world_pt
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object_from_bmesh(name, bm, material=mats["M_White"], smooth=True, parent=True)
        add_subsurf(obj, 1, 2)
        return obj

    # Wrist plug: fills the cuff opening so no dark gap shows between cuff and palm
    def build_plug(name, wrist, M):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
        for v in bm.verts:
            u = v.co.normalized()
            v.co = to_world(Vector((u.x * 0.052, u.y * 0.048, 0.035 + u.z * 0.045)), wrist, M)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object_from_bmesh(name, bm, material=mats["M_White"], smooth=True, parent=True)
        add_subsurf(obj, 1, 2)
        return obj
    # Build a finger or thumb using sweep_tube
    def build_tube_part(name, wrist, M, local_path, radius, n_around, extend_start=0.0, extend_end=0.0):
        # Transform local path to world
        world_path = [to_world(p, wrist, M) for p in local_path]
        # Resample with catmull_rom
        resampled = catmull_rom(world_path, 12)
        # Sweep tube
        obj = sweep_tube(name, resampled, radius, n_around, mats["M_White"],
                         extend_start=extend_start, extend_end=extend_end)
        return obj

    # Define local finger paths for right hand (open)
    def finger_paths_open():
        # Base positions: x = -0.050, 0.0, +0.050; y=0; z=0.135
        bases = [(-0.050, 0.0, 0.135), (0.0, 0.0, 0.135), (0.050, 0.0, 0.135)]
        lengths = [0.085, 0.095, 0.085]
        angles = [-16, 0, 16]  # degrees from +z in xz-plane
        paths = []
        for base, length, angle_deg in zip(bases, lengths, angles):
            angle = math.radians(angle_deg)
            # Direction in xz-plane
            dir_x = math.sin(angle)
            dir_z = math.cos(angle)
            # Path: base, mid, tip with slight arch (y -0.006 at mid)
            p0 = Vector(base)
            mid = Vector((
                base[0] + dir_x * length * 0.5,
                -0.006,
                base[2] + dir_z * length * 0.5,
            ))
            tip = Vector((
                base[0] + dir_x * length,
                0.0,
                base[2] + dir_z * length,
            ))
            paths.append([p0, mid, tip])
        return paths

    def finger_paths_relaxed():
        # Curled fingers: arc in yz-plane, radius 0.07, angles: middle 75, sides 65
        bases = [(-0.050, 0.0, 0.135), (0.0, 0.0, 0.135), (0.050, 0.0, 0.135)]
        curl_angles = [65, 75, 65]  # degrees
        side_angles = [-8, 0, 8]  # fan in xz-plane
        paths = []
        for base, curl_deg, side_deg in zip(bases, curl_angles, side_angles):
            curl = math.radians(curl_deg)
            side = math.radians(side_deg)
            # Starting direction along +z, then curl toward +y
            # We'll create 5 points along arc
            points = []
            for t in [0, 0.25, 0.5, 0.75, 1.0]:
                angle = curl * t
                # Arc in yz-plane: start at (0,0,z_base+radius), then rotate toward +y
                # Actually we need to start from base and curl forward.
                # Define arc: center at (x_base, 0, z_base - radius)?? Simpler: use parametric.
                # We'll place points along a circle of radius 0.07 in yz-plane, starting at base (y=0, z=0.135) and curving toward +y and decreasing z.
                # Parametric: angle from vertical (z-axis) in yz-plane.
                # At t=0: y=0, z=base_z + radius? Actually start at base, then move along circle.
                # Let's define circle center at (base_x, 0, base_z + radius). Then point at angle theta from vertical: y = radius*sin(theta), z = base_z + radius - radius*cos(theta). This gives at theta=0: y=0,z=base_z, good.
                theta = curl * t
                # arc that starts heading along +z and curls toward the palm front (+y)
                y = 0.07 * (1.0 - math.cos(theta))
                z = base[2] + 0.07 * math.sin(theta)
                # Add side fan: rotate around z? We'll add x offset proportional to t?
                x = base[0] + math.sin(side) * (0.07 * math.sin(theta))  # fan sideways with forward progress
                points.append(Vector((x, y, z)))
            paths.append(points)
        return paths

    # Thumb paths
    def thumb_path_open(thumb_sign):
        # Base at (thumb_sign*0.070, 0.012, 0.070)
        base = (thumb_sign * 0.070, 0.012, 0.070)
        # Direction: outward thumb_sign*x tilted 50 deg up toward +z
        tilt = math.radians(50)
        # Vector in xz-plane: x = thumb_sign*sin(tilt), z = cos(tilt)
        dir_vec = Vector((thumb_sign * math.sin(tilt), 0, math.cos(tilt)))
        length = 0.075
        # Slight curve toward +z at tip
        p0 = Vector(base)
        p1 = p0 + dir_vec * length * 0.5
        p2 = p0 + dir_vec * length + Vector((0, 0, 0.01))  # slight upward
        return [p0, p1, p2]

    def thumb_path_relaxed(thumb_sign):
        # Base at (thumb_sign*0.070, 0.012, 0.070)
        base = (thumb_sign * 0.070, 0.012, 0.070)
        # Direction: outward thumb_sign*x tilted 65 deg up toward +z and 25 deg toward +y
        tilt_z = math.radians(65)
        tilt_y = math.radians(25)
        # Build direction vector: start with x = thumb_sign, then rotate toward z and y.
        # We can construct: dir = (thumb_sign*cos(tilt_y)*sin(tilt_z), sin(tilt_y), cos(tilt_y)*cos(tilt_z))
        dir_vec = Vector((
            thumb_sign * math.cos(tilt_y) * math.sin(tilt_z),
            math.sin(tilt_y),
            math.cos(tilt_y) * math.cos(tilt_z),
        ))
        length = 0.075
        # Slight curve toward +z at tip
        p0 = Vector(base)
        p1 = p0 + dir_vec * length * 0.5
        p2 = p0 + dir_vec * length + Vector((0, 0, 0.015))
        return [p0, p1, p2]

    # Build both gloves
    gloves_objects = []
    # Right hand (waving, open)
    wrist_R, M_R, thumb_sign_R = _hand_frame(ARM_WAVE_POINTS, Vector((0, -1, 0)), Vector((1, 0, 0)))
    # Cuff
    cuff_R = build_cuff("Glove_Right_Cuff", wrist_R, M_R)
    # Palm
    palm_R = build_palm("Glove_Right_Palm", wrist_R, M_R)
    plug_R = build_plug("Glove_Right_Wrist", wrist_R, M_R)
    # Fingers
    finger_paths = finger_paths_open()
    fingers_R = []
    for i, path in enumerate(finger_paths, start=1):
        fingers_R.append(build_tube_part(f"Glove_Right_Finger{i}", wrist_R, M_R, path, 0.029, 12, extend_start=0.02))
    # Thumb
    thumb_path = thumb_path_open(thumb_sign_R)
    thumb_R = build_tube_part("Glove_Right_Thumb", wrist_R, M_R, thumb_path, 0.031, 12, extend_start=0.025)

    # Left hand (resting, relaxed)
    wrist_L, M_L, thumb_sign_L = _hand_frame(ARM_REST_POINTS, Vector((-1, 0, 0)), Vector((0, -1, 0)))
    # Cuff
    cuff_L = build_cuff("Glove_Left_Cuff", wrist_L, M_L)
    # Palm
    palm_L = build_palm("Glove_Left_Palm", wrist_L, M_L)
    plug_L = build_plug("Glove_Left_Wrist", wrist_L, M_L)
    # Fingers
    finger_paths = finger_paths_relaxed()
    fingers_L = []
    for i, path in enumerate(finger_paths, start=1):
        fingers_L.append(build_tube_part(f"Glove_Left_Finger{i}", wrist_L, M_L, path, 0.029, 12, extend_start=0.02))
    # Thumb
    thumb_path = thumb_path_relaxed(thumb_sign_L)
    thumb_L = build_tube_part("Glove_Left_Thumb", wrist_L, M_L, thumb_path, 0.031, 12, extend_start=0.025)

    gloves_objects = [cuff_R, palm_R, plug_R] + fingers_R + [thumb_R] + [cuff_L, palm_L, plug_L] + fingers_L + [thumb_L]
    return gloves_objects

SECTION_BUILDERS.append(("gloves", build_gloves))
# <<< SECTION gloves

# >>> SECTION face

# ----------------------------------------------------------------------------
# Outline helpers (module-level, reused by patches)
# ----------------------------------------------------------------------------
def _ellipse(w, h):
    """Closed CCW ellipse outline in (u,v): u = w/2 cos, v = h/2 sin."""
    def outline(t):
        a = 2.0 * math.pi * t
        return (w / 2.0 * math.cos(a), h / 2.0 * math.sin(a))
    return outline

def _d_shape(w, h):
    """Closed CCW D-shape: flat top edge at v=0, half-ellipse below (depth h)."""
    def outline(t):
        if t < 0.25:
            # top edge right-to-left: (w/2,0) -> (-w/2,0)
            frac = t / 0.25
            u = w / 2.0 - w * frac
            v = 0.0
        else:
            # bottom half-ellipse: theta from pi to 2pi (v negative)
            frac = (t - 0.25) / 0.75
            theta = math.pi + frac * math.pi
            u = w / 2.0 * math.cos(theta)
            v = h * math.sin(theta)
        return (u, v)
    return outline

def _superellipse(w, h, exponent=4):
    """Closed CCW superellipse (rounded rectangle) with given exponent."""
    n = float(exponent)
    def outline(t):
        a = 2.0 * math.pi * t
        cos_a = math.cos(a)
        sin_a = math.sin(a)
        u = w / 2.0 * math.copysign(1.0, cos_a) * abs(cos_a) ** (2.0 / n)
        v = h / 2.0 * math.copysign(1.0, sin_a) * abs(sin_a) ** (2.0 / n)
        return (u, v)
    return outline

def _brow_outline(r_inner, r_outer, angle_start_deg=30, angle_end_deg=150):
    """
    Closed CCW outline of a band between two concentric arcs.
    Angles measured from +v axis, clockwise positive.
    Outer arc traversed counterclockwise (end->start), inner arc clockwise (start->end).
    Radial connectors at both ends.
    """
    start = math.radians(angle_start_deg)
    end = math.radians(angle_end_deg)

    def outline(t):
        # Four segments: outer arc (end->start), radial outer->inner at start,
        # inner arc (start->end), radial inner->outer at end.
        if t < 0.45:
            # outer arc: angle from end to start (decreasing)
            frac = t / 0.45
            theta = end - frac * (end - start)
            r = r_outer
        elif t < 0.50:
            # radial from outer start to inner start
            frac = (t - 0.45) / 0.05
            r = r_outer + frac * (r_inner - r_outer)
            theta = start
        elif t < 0.95:
            # inner arc: angle from start to end (increasing)
            frac = (t - 0.50) / 0.45
            theta = start + frac * (end - start)
            r = r_inner
        else:
            # radial from inner end to outer end
            frac = (t - 0.95) / 0.05
            r = r_inner + frac * (r_outer - r_inner)
            theta = end
        u = r * math.cos(theta)  # arch: angle measured from +u so 30..150 deg is the top arc
        v = r * math.sin(theta)
        return (u, v)
    return outline


# ----------------------------------------------------------------------------
# build_face section
# ----------------------------------------------------------------------------
def build_face(mats):
    """Embroidered facial features: shrinkwrapped patches + felt nose."""
    # ------------------------------------------------------------------------
    # Proxy radius function: fabric surface with soft bumps at hoop locations
    # ------------------------------------------------------------------------
    hoop_heights = [hoop_z(p) for p in HOOP_PCTS]

    def proxy_radius(z):
        r = bulge_radius(z)
        bump_max = 0.0
        for hz in hoop_heights:
            bump = BODY_R + 0.034 * math.exp(-((z - hz) / 0.045) ** 2)  # wide, gentle drape over the hoop
            if bump > bump_max:
                bump_max = bump
        return max(r, bump_max)

    # ------------------------------------------------------------------------
    # Face_Proxy (hidden shrinkwrap target)
    # ------------------------------------------------------------------------
    z_min = hoop_z(0.60)   # lower
    z_max = hoop_z(0.20)   # higher
    z_step = 0.005
    profile = []
    z = z_min
    while z <= z_max + 1e-9:
        profile.append((proxy_radius(z), z))
        z += z_step
    # Ensure at least two rings
    if len(profile) < 2:
        profile = [(proxy_radius(z_min), z_min), (proxy_radius(z_max), z_max)]

    bm_proxy = bmesh.new()
    rings_proxy = lathe_rings(bm_proxy, profile, segments=64, phase=0.0)
    bridge_rings(bm_proxy, rings_proxy)  # open tube, no caps
    proxy_obj = new_object_from_bmesh(
        "Face_Proxy", bm_proxy, material=None, smooth=False, parent=False
    )
    proxy_obj.hide_render = True
    proxy_obj.display_type = 'WIRE'
    # Do NOT hide in viewport, keep evaluable for Shrinkwrap.

    # ------------------------------------------------------------------------
    # Internal patch builder
    # ------------------------------------------------------------------------
    def _patch(name, outline_uv, z_center, x_center, layer, mat, n=32, inner=4):
        """
        Create an all-quad flat patch that follows the proxy surface.
        outline_uv: t -> (u,v) in [0,1), CCW, metres.
        layer: integer stacking order (affects shrinkwrap offset).
        """
        # Sample outline points
        pts_local = [outline_uv(i / n) for i in range(n)]

        # Compute centroid and extents
        centroid_u = sum(p[0] for p in pts_local) / n
        centroid_v = sum(p[1] for p in pts_local) / n
        max_u = max(abs(p[0] - centroid_u) for p in pts_local)
        max_v = max(abs(p[1] - centroid_v) for p in pts_local)
        min_extent = min(max_u, max_v)
        square_half = 0.35 * min_extent

        # Corner-by-index quad disk: the inner square ring is parametrised by vertex index,
        # so its four corners always land on indices k45 + j*n/4 and each side has n/4+1 verts.
        k45 = min(range(n), key=lambda k: abs((math.atan2(pts_local[k][1] - centroid_v,
                                                         pts_local[k][0] - centroid_u)
                                              - math.pi / 4 + math.pi) % (2 * math.pi) - math.pi))
        sq_corners = [(square_half, square_half), (-square_half, square_half),
                      (-square_half, -square_half), (square_half, -square_half)]

        def sq_point(k):
            s4 = (((k - k45) % n) / n) * 4.0
            side_i = int(s4) % 4
            f = s4 - int(s4)
            ca, cb = sq_corners[side_i], sq_corners[(side_i + 1) % 4]
            return (centroid_u + ca[0] + f * (cb[0] - ca[0]), centroid_v + ca[1] + f * (cb[1] - ca[1]))

        all_rings_local = [pts_local]
        for i in range(1, inner + 1):
            t_interp = i / inner
            ring = []
            for k, p in enumerate(pts_local):
                su, sv = sq_point(k)
                ring.append((p[0] + t_interp * (su - p[0]), p[1] + t_interp * (sv - p[1])))
            all_rings_local.append(ring)

        bm = bmesh.new()
        world_rings = []
        for ring_local in all_rings_local:
            ring_verts = []
            for (u, v) in ring_local:
                x = x_center + u
                z = z_center + v
                r = proxy_radius(z)
                y = -math.sqrt(max(r * r - x * x, 0.0)) - 0.03  # just in front of the proxy
                ring_verts.append(bm.verts.new((x, y, z)))
            world_rings.append(ring_verts)
        for i in range(len(world_rings) - 1):
            bridge_rings(bm, [world_rings[i], world_rings[i + 1]])

        N = n
        M = N // 4
        square_ring = world_rings[-1]
        ordered_ring = square_ring[k45:] + square_ring[:k45]
        sides = [ordered_ring[j * M:(j + 1) * M + 1] if j < 3 else ordered_ring[3 * M:] + ordered_ring[:1]
                 for j in range(4)]
        # Build (M+1)x(M+1) grid, assign borders
        grid = [[None] * (M + 1) for _ in range(M + 1)]
        for j in range(M + 1):
            grid[0][j] = sides[0][j]          # top row
        for i in range(M + 1):
            grid[i][M] = sides[1][i]          # right column
        for j in range(M + 1):
            grid[M][M - j] = sides[2][j]      # bottom row (reversed)
        for i in range(M + 1):
            grid[M - i][0] = sides[3][i]      # left column (reversed)

        # Create interior vertices by bilinear interpolation
        for i in range(1, M):
            for j in range(1, M):
                left = grid[i][0].co
                right = grid[i][M].co
                row_point = left + (j / M) * (right - left)
                top = grid[0][j].co
                bottom = grid[M][j].co
                col_point = top + (i / M) * (bottom - top)
                pos = (row_point + col_point) / 2.0
                # Adjust y to stay on proxy surface (approx)
                r = proxy_radius(pos.z)
                y = -math.sqrt(max(r * r - pos.x * pos.x, 0.0)) - 0.03
                pos.y = y
                grid[i][j] = bm.verts.new(pos)

        # Create quads
        for i in range(M):
            for j in range(M):
                v0 = grid[i][j]
                v1 = grid[i + 1][j]
                v2 = grid[i + 1][j + 1]
                v3 = grid[i][j + 1]
                bm.faces.new((v0, v1, v2, v3))

        # Recalculate normals and ensure they face -Y (front)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        avg_y = sum(f.normal.y for f in bm.faces) / len(bm.faces)
        if avg_y > 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)

        obj = new_object_from_bmesh(
            name, bm, material=mat, smooth=True, parent=True
        )

        # Modifiers: Shrinkwrap -> Solidify -> Subdivision
        _face_modifiers(obj, layer)
        return obj

    def _face_modifiers(obj, layer):
        # Project straight back along Y so outlines keep their front-view shape over the hoop bump
        shrink = obj.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
        shrink.target = proxy_obj
        shrink.wrap_method = 'PROJECT'
        shrink.use_project_y = True
        shrink.use_negative_direction = True
        shrink.use_positive_direction = True
        shrink.wrap_mode = 'OUTSIDE_SURFACE'
        # layers 4 mm apart, each patch 1.5 mm thick: no overlap, no z-fighting
        shrink.offset = 0.002 + 0.004 * layer

        solidify = obj.modifiers.new("Solidify", 'SOLIDIFY')
        solidify.thickness = 0.0032  # thicker patch; subdivision rounds the rim into a puffy stitched edge
        solidify.offset = 1.0
        solidify.use_even_offset = True

        add_subsurf(obj, 1, 2)

        return obj

    # ------------------------------------------------------------------------
    # Eyes
    # ------------------------------------------------------------------------
    eye_objects = []
    eye_z = hoop_z(0.29) + 0.025 - 0.15
    for side, sx in (("Left", +1.0), ("Right", -1.0)):
        eye_x = FACE_X + sx * 0.14

        # Outline (black)
        outline_fn = _ellipse(0.22, 0.32)
        obj = _patch(
            f"Eye_{side}_Outline",
            outline_fn,
            eye_z, eye_x,
            layer=0, mat=mats["M_Black"],
            n=32, inner=4
        )
        eye_objects.append(obj)

        # White
        white_fn = _ellipse(0.20, 0.30)
        obj = _patch(
            f"Eye_{side}_White",
            white_fn,
            eye_z, eye_x,
            layer=1, mat=mats["M_White"],
            n=32, inner=4
        )
        eye_objects.append(obj)

        # Pupil (offset)
        pupil_fn = _ellipse(0.11, 0.15)
        pupil_x = eye_x + 0.03
        pupil_z = eye_z - 0.02
        obj = _patch(
            f"Pupil_{side}",
            pupil_fn,
            pupil_z, pupil_x,
            layer=2, mat=mats["M_Black"],
            n=32, inner=4
        )
        eye_objects.append(obj)

        # Highlight
        highlight_fn = _ellipse(0.035, 0.045)
        highlight_x = eye_x + 0.005
        highlight_z = eye_z + 0.025
        obj = _patch(
            f"Highlight_{side}",
            highlight_fn,
            highlight_z, highlight_x,
            layer=3, mat=mats["M_White"],
            n=32, inner=4
        )
        eye_objects.append(obj)

        # Eyelids (hidden)
        # Upper half-ellipse
        def upper_eyelid_fn(t):
            # half ellipse from angle 0 to pi (v >= 0)
            a = math.pi * t  # t in [0,1) -> a in [0, pi)
            u = 0.23 / 2.0 * math.cos(a)
            v = 0.33 / 2.0 * math.sin(a)
            # close by adding straight line at v=0? Actually the outline needs to be closed.
            # We'll define a piecewise: half-ellipse then straight line back.
            if t < 0.5:
                frac = t / 0.5
                a = math.pi * frac
                u = 0.23 / 2.0 * math.cos(a)
                v = 0.33 / 2.0 * math.sin(a)
            else:
                frac = (t - 0.5) / 0.5
                u = -0.23 / 2.0 + 0.23 * frac  # close back from (-0.115,0) to (0.115,0)
                v = 0.0
            return (u, v)

        obj = _patch(
            f"Eyelid_{side}_Upper",
            upper_eyelid_fn,
            eye_z, eye_x,
            layer=4, mat=mats["M_Body"],
            n=32, inner=4
        )
        obj.hide_render = True
        obj.hide_viewport = True
        eye_objects.append(obj)

        # Lower half-ellipse
        def lower_eyelid_fn(t):
            if t < 0.5:
                frac = t / 0.5
                a = math.pi + math.pi * frac  # pi to 2pi
                u = 0.23 / 2.0 * math.cos(a)
                v = 0.33 / 2.0 * math.sin(a)
            else:
                frac = (t - 0.5) / 0.5
                u = 0.23 / 2.0 - 0.23 * frac  # close back from (0.115,0) to (-0.115,0)
                v = 0.0
            return (u, v)

        obj = _patch(
            f"Eyelid_{side}_Lower",
            lower_eyelid_fn,
            eye_z, eye_x,
            layer=4, mat=mats["M_Body"],
            n=32, inner=4
        )
        obj.hide_render = True
        obj.hide_viewport = True
        eye_objects.append(obj)

    # ------------------------------------------------------------------------
    # Brows
    # ------------------------------------------------------------------------
    brow_objects = []
    brow_z_center = hoop_z(0.29) + 0.008  # arch ends clear the eye outline, top ~0.10 above the hoop
    for side, sx in (("Left", +1.0), ("Right", -1.0)):
        brow_x = FACE_X + sx * 0.14
        # arched strip of quads (a disk fill folds on this concave shape)
        bmb = bmesh.new()
        rows = []
        for rr in (0.075, 0.083, 0.091):
            row = []
            for k in range(17):
                th = math.radians(30 + 120 * k / 16)
                bx, bz = brow_x + rr * math.cos(th), brow_z_center + rr * math.sin(th)
                rb = proxy_radius(bz)
                row.append(bmb.verts.new((bx, -math.sqrt(max(rb * rb - bx * bx, 0.0)) - 0.03, bz)))
            rows.append(row)
        for r0, r1 in zip(rows, rows[1:]):
            for k in range(16):
                bmb.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
        bmesh.ops.recalc_face_normals(bmb, faces=bmb.faces)
        bmb.normal_update()
        if sum(fc.normal.y for fc in bmb.faces) > 0:
            bmesh.ops.reverse_faces(bmb, faces=bmb.faces)
        obj = new_object_from_bmesh(f"Brow_{side}", bmb, material=mats["M_Black"], smooth=True, parent=True)
        _face_modifiers(obj, 1)
        brow_objects.append(obj)

    # ------------------------------------------------------------------------
    # Mouth
    # ------------------------------------------------------------------------
    # mouth lowered (review v2) so it clears the eye outlines; eye-outline bottom is hoop44 - 0.096
    mouth_top_z = hoop_z(0.44) - 0.108
    mouth_x = FACE_X
    mouth_objects = []

    # Outline (larger D, top edge 0.0075 higher)
    outline_fn = _d_shape(0.235, 0.095)
    obj = _patch(
        "Mouth_Outline",
        outline_fn,
        mouth_top_z + 0.0075, mouth_x,
        layer=0, mat=mats["M_Black"],
        n=32, inner=4
    )
    mouth_objects.append(obj)

    # Inside (dark)
    inside_fn = _d_shape(0.22, 0.085)  # shallower so the mouth clears the wordmark below
    obj = _patch(
        "Mouth",
        inside_fn,
        mouth_top_z, mouth_x,
        layer=1, mat=mats["M_MouthIn"],
        n=32, inner=4
    )
    mouth_objects.append(obj)

    # Teeth (superellipse rounded rectangle)
    teeth_fn = _superellipse(0.16, 0.03, exponent=4)
    teeth_z = mouth_top_z - 0.017
    obj = _patch(
        "Teeth_Upper",
        teeth_fn,
        teeth_z, mouth_x,
        layer=2, mat=mats["M_White"],
        n=32, inner=4
    )
    mouth_objects.append(obj)

    # Tongue (ellipse)
    tongue_fn = _ellipse(0.09, 0.035)
    tongue_z = mouth_top_z - 0.062
    obj = _patch(
        "Tongue",
        tongue_fn,
        tongue_z, mouth_x,
        layer=2, mat=mats["M_Tongue"],
        n=32, inner=4
    )
    mouth_objects.append(obj)

    # ------------------------------------------------------------------------
    # Nose (felt ball)
    # ------------------------------------------------------------------------
    bm_nose = bmesh.new()
    bmesh.ops.create_cube(bm_nose, size=2.0)
    bmesh.ops.subdivide_edges(
        bm_nose, edges=bm_nose.edges[:], cuts=4, use_grid_fill=True
    )
    for v in bm_nose.verts:
        v.co.normalize()  # unit sphere
    # Scale and translate
    nose_radius = 0.036  # review v3: a bit bigger again
    nose_x = FACE_X
    nose_z = mouth_top_z + 0.036  # sits just above the mouth, between the lower eye curves
    nose_y = -(bulge_radius(nose_z) + 0.025)
    for v in bm_nose.verts:
        v.co = v.co * nose_radius
        v.co += Vector((nose_x, nose_y, nose_z))
    bmesh.ops.recalc_face_normals(bm_nose, faces=bm_nose.faces)
    nose_obj = new_object_from_bmesh(
        "Nose", bm_nose, material=mats["M_Felt"], smooth=True, parent=True
    )
    add_subsurf(nose_obj, 1, 2)

    # ------------------------------------------------------------------------
    # Return all created objects (excluding Face_Proxy)
    # ------------------------------------------------------------------------
    return eye_objects + brow_objects + mouth_objects + [nose_obj]


SECTION_BUILDERS.append(("face", build_face))
# <<< SECTION face

# >>> SECTION logo
def build_logo(mats):
    """Gold wordmark + flame, badge ring and three gold balls from refs/logo_trace.json."""
    import json

    trace_path = os.path.join(PROJECT_ROOT, "refs", "logo_trace.json")
    if not os.path.exists(trace_path):
        print("[02_model] logo: refs/logo_trace.json missing, run scripts/trace_logo.py")
        return []

    with open(trace_path, encoding="utf-8") as f:
        trace = json.load(f)

    S = 0.0006 * 1.15  # wordmark ~15% taller (review 2026-11-10); badge may touch the hoop seams
    BADGE_SCALE = 0.80  # review 2: smaller badge so the logo can sit 2 cm lower
    badge = trace["badge"]
    badge_cx = badge["cx"]
    badge_cy = badge["cy"]
    r_in_s = badge["r_inner"] * BADGE_SCALE * S
    r_out_s = badge["r_outer"] * BADGE_SCALE * S

    # Scaled ball positions and radii (about badge centre)
    scaled_balls = []
    for ball in trace["balls"]:
        dx = (ball["cx"] - badge_cx) * BADGE_SCALE
        dy = (ball["cy"] - badge_cy) * BADGE_SCALE
        scaled_balls.append({
            "cx": badge_cx + dx,
            "cy": badge_cy + dy,
            "r": ball["r"] * BADGE_SCALE * S,
        })

    # Bounding box: all word curve points + scaled badge outer circle
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = -float("inf"), -float("inf")

    def _add_px(x, y):
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    for curve in trace["word"]:
        _add_px(*curve["start"])
        for seg in curve["segs"]:
            if "c1" in seg:
                _add_px(*seg["c1"])
                _add_px(*seg["c2"])
                _add_px(*seg["end"])
            else:
                _add_px(*seg["corner"])
                _add_px(*seg["end"])

    _add_px(badge_cx - r_out_s / S, badge_cy - r_out_s / S)  # convert r_out_s metres to px
    _add_px(badge_cx + r_out_s / S, badge_cy + r_out_s / S)

    cx_box = (min_x + max_x) / 2.0
    cy_box = (min_y + max_y) / 2.0

    def _cv(px, py):
        u = (px - cx_box) * S
        v = -(py - cy_box) * S
        return (u, v, 0.0)

    LOGO_CZ = ((hoop_z(0.44) - 0.18) + (hoop_z(0.76) + 0.03)) / 2.0 - 0.02  # room for bigger mouths

    def _conform(u, v, d):
        z = LOGO_CZ + v
        R = bulge_radius(z) + 0.0015 + d
        angle = (LOGO_X + u) / (BODY_R + BULGE)
        return (R * math.sin(angle), -R * math.cos(angle), z)

    # ------------------------------------------------------------------------
    # 1. Wordmark + flame
    # ------------------------------------------------------------------------
    curve_data = bpy.data.curves.new("Logo_Wordmark_Curve", type="CURVE")
    curve_data.dimensions = "2D"
    curve_data.fill_mode = "BOTH"
    curve_data.resolution_u = 3
    curve_data.extrude = 0.0012
    curve_data.bevel_depth = 0.0008  # small rounded bevel on the letter edges
    curve_data.bevel_resolution = 2

    for curve in trace["word"]:
        segments = curve["segs"]
        if not segments:
            continue

        spline = curve_data.splines.new("BEZIER")
        start_meta = {
            "co": _cv(*curve["start"]),
            "left_type": None,
            "right_type": None,
            "hl": None,
            "hr": None,
        }
        points_meta = [start_meta]
        prev = start_meta

        # Process all segments except the closing one
        for seg in segments[:-1]:
            if "c1" in seg:
                # cubic Bezier segment
                end_meta = {
                    "co": _cv(*seg["end"]),
                    "left_type": "FREE",
                    "right_type": None,  # will be set by next segment
                    "hl": _cv(*seg["c2"]),
                    "hr": None,
                }
                prev["right_type"] = "FREE"
                prev["hr"] = _cv(*seg["c1"])
                points_meta.append(end_meta)
                prev = end_meta
            else:
                # corner segment: add corner and end
                corner_meta = {
                    "co": _cv(*seg["corner"]),
                    "left_type": "VECTOR",
                    "right_type": "VECTOR",
                    "hl": None,
                    "hr": None,
                }
                prev["right_type"] = "VECTOR"
                prev["hr"] = prev["co"]
                points_meta.append(corner_meta)
                end_meta = {
                    "co": _cv(*seg["end"]),
                    "left_type": "VECTOR",
                    "right_type": None,
                    "hl": None,
                    "hr": None,
                }
                corner_meta["right_type"] = "VECTOR"
                corner_meta["hr"] = corner_meta["co"]
                points_meta.append(end_meta)
                prev = end_meta

        # Closing segment
        closing = segments[-1]
        if "c1" in closing:
            prev["right_type"] = "FREE"
            prev["hr"] = _cv(*closing["c1"])
            start_meta["left_type"] = "FREE"
            start_meta["hl"] = _cv(*closing["c2"])
        else:
            # corner closing: add corner point before start
            corner_meta = {
                "co": _cv(*closing["corner"]),
                "left_type": "VECTOR",
                "right_type": "VECTOR",
                "hl": None,
                "hr": None,
            }
            prev["right_type"] = "VECTOR"
            prev["hr"] = prev["co"]
            points_meta.append(corner_meta)
            corner_meta["right_type"] = "VECTOR"
            corner_meta["hr"] = corner_meta["co"]
            start_meta["left_type"] = "VECTOR"
            start_meta["hl"] = start_meta["co"]

        # Create spline points
        spline.bezier_points.add(len(points_meta) - 1)
        for i, meta in enumerate(points_meta):
            bp = spline.bezier_points[i]
            bp.handle_left_type = meta["left_type"] if meta["left_type"] is not None else "AUTO"
            bp.handle_right_type = meta["right_type"] if meta["right_type"] is not None else "AUTO"
            bp.co = meta["co"]
            if meta["hl"] is not None:
                bp.handle_left = meta["hl"]
            else:
                bp.handle_left = meta["co"]
            if meta["hr"] is not None:
                bp.handle_right = meta["hr"]
            else:
                bp.handle_right = meta["co"]
        spline.use_cyclic_u = True

    # Evaluate curve to mesh, conform, create final object
    temp_obj = bpy.data.objects.new("Logo_Wordmark_Temp", curve_data)
    bpy.context.scene.collection.objects.link(temp_obj)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    eval_obj = temp_obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eval_obj)
    bpy.data.objects.remove(temp_obj, do_unlink=True)
    bpy.data.curves.remove(curve_data)

    for v in me.vertices:
        x, y, zl = v.co
        v.co = _conform(x, y, zl + 0.002)  # zl spans -(extrude+bevel)..+(extrude+bevel)

    word_obj = bpy.data.objects.new("Logo_Wordmark", me)
    bpy.context.scene.collection.objects.link(word_obj)
    word_obj.parent = bpy.data.objects[ROOT_NAME]
    me.materials.append(mats["M_Gold"])
    for p in me.polygons:
        p.use_smooth = True
    # smooth letter faces (the wrap made flat facets) but keep crisp edges at the bevel
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(35))

    # ------------------------------------------------------------------------
    # 2. Badge ring (rolled fabric)
    # ------------------------------------------------------------------------
    u_b, v_b, _ = _cv(badge_cx, badge_cy)
    rc = (r_in_s + r_out_s) / 2.0
    rt = (r_out_s - r_in_s) / 2.0
    n_major, n_minor = 64, 12

    bm_ring = bmesh.new()
    rings = []
    for i in range(n_major):
        theta = 2.0 * math.pi * i / n_major
        radial_dir = (math.cos(theta), math.sin(theta))
        ring = []
        for j in range(n_minor):
            phi = 2.0 * math.pi * j / n_minor
            local_r = rc + rt * math.cos(phi)
            u = u_b + local_r * radial_dir[0]
            v = v_b + local_r * radial_dir[1]
            d = 0.45 * rt * math.sin(phi) + 0.45 * rt * 0.6
            ring.append(bm_ring.verts.new(_conform(u, v, d)))
        rings.append(ring)
    bridge_rings(bm_ring, rings, closed=True)
    bmesh.ops.recalc_face_normals(bm_ring, faces=bm_ring.faces)
    ring_obj = new_object_from_bmesh(
        "Logo_Badge_Ring", bm_ring, material=mats["M_White"], smooth=True, parent=True
    )
    add_subsurf(ring_obj, 1, 2)

    # ------------------------------------------------------------------------
    # 3. Three gold balls
    # ------------------------------------------------------------------------
    ball_objs = []
    for idx, ball in enumerate(scaled_balls, start=1):
        rb = ball["r"]
        u_ball, v_ball, _ = _cv(ball["cx"], ball["cy"])

        bm_ball = bmesh.new()
        bmesh.ops.create_cube(bm_ball, size=2.0)
        bmesh.ops.subdivide_edges(
            bm_ball, edges=bm_ball.edges[:], cuts=4, use_grid_fill=True
        )
        for vert in bm_ball.verts:
            vert.co.normalize()
            a, b, c = vert.co
            u = u_ball + rb * a
            v = v_ball + rb * b
            d = 0.35 * rb * c + 0.25 * rb
            vert.co = _conform(u, v, d)
        bmesh.ops.recalc_face_normals(bm_ball, faces=bm_ball.faces)

        ball_obj = new_object_from_bmesh(
            f"Logo_Ball_{idx}", bm_ball, material=mats["M_Gold"], smooth=True, parent=True
        )
        add_subsurf(ball_obj, 1, 2)
        ball_objs.append(ball_obj)

    return [word_obj, ring_obj] + ball_objs


SECTION_BUILDERS.append(("logo", build_logo))
# <<< SECTION logo


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
    cam.data.lens = 75
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
    global PROJECT_ROOT
    PROJECT_ROOT = root_dir
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
