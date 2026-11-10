```python
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
                if abs(minor_angle) < 0.25:
                    dent = seam_depth * (1 - (minor_angle / 0.25) ** 2) ** 2
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
                diff = abs(a - ca)
                if diff > math.pi:
                    diff = 2 * math.pi - diff
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
        # Bottom/top edge adjustments
        if abs(z - (BODY_BOTTOM + 0.012)) < 1e-6:
            r -= 0.006
        elif abs(z - BODY_BOTTOM) < 1e-6:
            r -= 0.03
        if abs(z - (BODY_TOP - 0.012)) < 1e-6:
            r -= 0.006
        elif abs(z - BODY_TOP) < 1e-6:
            r -= 0.03
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
                r -= 0.005 * (1 - (da / 0.12) ** 2) ** 2
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
            n_minor=16,
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
        n_minor=16,
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
```