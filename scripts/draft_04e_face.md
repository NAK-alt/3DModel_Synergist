```python

# >>> SECTION face
import bmesh
import math
from mathutils import Vector, Matrix

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
        u = r * math.sin(theta)
        v = r * math.cos(theta)
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
            bump = BODY_R + 0.034 * math.exp(-((z - hz) / 0.028) ** 2)
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

        # Build all rings in local (u,v), then convert to world
        all_rings_local = [pts_local]  # ring 0 = original outline
        for i in range(1, inner + 1):
            t_interp = i / inner
            ring = []
            for p in pts_local:
                # angle from centroid
                a = math.atan2(p[1] - centroid_v, p[0] - centroid_u)
                m = max(abs(math.cos(a)), abs(math.sin(a)))
                if m < 1e-8:
                    m = 1e-8
                sq_u = centroid_u + square_half * math.cos(a) / m
                sq_v = centroid_v + square_half * math.sin(a) / m
                new_u = p[0] + t_interp * (sq_u - p[0])
                new_v = p[1] + t_interp * (sq_v - p[1])
                ring.append((new_u, new_v))
            all_rings_local.append(ring)

        # Last ring is square border; we'll fill its interior with a grid later.
        square_ring_local = all_rings_local[-1]

        # Convert all rings to world coordinates and create bmesh vertices
        bm = bmesh.new()
        world_rings = []  # list of lists of bm verts
        for ring_local in all_rings_local:
            ring_verts = []
            for (u, v) in ring_local:
                x = x_center + u
                z = z_center + v
                r = proxy_radius(z)
                # y just in front of proxy surface (negative y is front)
                y = -math.sqrt(max(r * r - x * x, 0.0)) - 0.03
                ring_verts.append(bm.verts.new((x, y, z)))
            world_rings.append(ring_verts)

        # Bridge between consecutive rings (outline -> intermediates -> square)
        for i in range(len(world_rings) - 1):
            bridge_rings(bm, [world_rings[i], world_rings[i + 1]])

        # Fill square interior with grid (same as quad_disk_cap)
        N = n
        M = N // 4  # quads per side
        square_ring = world_rings[-1]
        # Find corner indices (closest to 45, 135, 225, 315 degrees from centroid)
        corner_angles = [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]
        corner_indices = []
        for ca in corner_angles:
            best_idx = 0
            best_diff = 1e9
            for idx, v in enumerate(square_ring):
                # world coords of vertex; compute angle from centroid in x-z plane
                a = math.atan2(v.co.z - z_center, v.co.x - x_center)
                diff = abs((a - ca + math.pi) % (2 * math.pi) - math.pi)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = idx
            corner_indices.append(best_idx)

        # Reorder square_ring to start at corner[0]
        start = corner_indices[0]
        ordered_ring = square_ring[start:] + square_ring[:start]
        rel_corners = [(c - start) % N for c in corner_indices]
        rel_corners.sort()

        # Split into four sides
        sides = []
        for i in range(4):
            c1 = rel_corners[i]
            c2 = rel_corners[(i + 1) % 4]
            if c2 > c1:
                side = ordered_ring[c1:c2 + 1]
            else:  # wrap around
                side = ordered_ring[c1:] + ordered_ring[:c2 + 1]
            sides.append(side)

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
        shrink = obj.modifiers.new("Shrinkwrap", 'SHRINKWRAP')
        shrink.target = proxy_obj
        shrink.wrap_method = 'NEAREST_SURFACEPOINT'
        shrink.wrap_mode = 'OUTSIDE_SURFACE'
        shrink.offset = 0.0015 + 0.0015 * layer

        solidify = obj.modifiers.new("Solidify", 'SOLIDIFY')
        solidify.thickness = 0.0018
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
                u = 0.23 / 2.0 - 0.23 * frac  # from (0.115,0) to (-0.115,0)
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
                u = -0.23 / 2.0 + 0.23 * frac  # from (-0.115,0) to (0.115,0)
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
    brow_z_center = hoop_z(0.29) + 0.035 - 0.065
    for side, sx in (("Left", +1.0), ("Right", -1.0)):
        brow_x = FACE_X + sx * 0.14
        brow_fn = _brow_outline(0.075, 0.075 + 0.016, 30, 150)
        obj = _patch(
            f"Brow_{side}",
            brow_fn,
            brow_z_center, brow_x,
            layer=1, mat=mats["M_Black"],
            n=32, inner=4
        )
        brow_objects.append(obj)

    # ------------------------------------------------------------------------
    # Mouth
    # ------------------------------------------------------------------------
    mouth_top_z = hoop_z(0.44) - 0.05
    mouth_x = FACE_X
    mouth_objects = []

    # Outline (larger D, top edge 0.0075 higher)
    outline_fn = _d_shape(0.235, 0.12)
    obj = _patch(
        "Mouth_Outline",
        outline_fn,
        mouth_top_z + 0.0075, mouth_x,
        layer=0, mat=mats["M_Black"],
        n=32, inner=4
    )
    mouth_objects.append(obj)

    # Inside (dark)
    inside_fn = _d_shape(0.22, 0.11)
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
    tongue_fn = _ellipse(0.10, 0.045)
    tongue_z = mouth_top_z - 0.085
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
    nose_radius = 0.04
    nose_x = FACE_X
    nose_z = hoop_z(0.44)
    nose_y = -(HOOP_MAJOR + HOOP_MINOR) - 0.03
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
```