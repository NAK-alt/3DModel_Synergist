```python
# >>> SECTION limbs
def build_limbs(mats):
    """Rubber-hose arms and legs: all-quad tubes with n-gon end caps."""
    ARM_R = ARM_RADIUS_BLOCKOUT * 1.3
    LEG_R = 0.04 * 1.3
    N_AROUND = 16

    def _catmull_rom(points, samples):
        """Centripetal Catmull-Rom spline through points, resampled by arc length."""
        pts = [Vector(p) for p in points]
        if len(pts) < 2:
            return pts
        # Phantom ends: duplicate first and last
        pts = [pts[0]] + pts + [pts[-1]]
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

    def _sweep_tube(name, path_pts, radius, n_around, mat,
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
        def cap_end(ring, tangent, reverse):
            """Close one end with two tapered rings and an n-gon."""
            # direction outward: reverse=True means -tangent (start), else +tangent
            out_dir = -tangent if reverse else tangent
            # First taper ring at 60% radius, 0.4*radius out
            ring1 = []
            center1 = ring[0].co + out_dir * 0.4 * radius
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
            center2 = ring[0].co + out_dir * 0.5 * radius
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
        cap_end(rings[0], tangents[0], reverse=True)
        # End cap (forward tangent)
        cap_end(rings[-1], tangents[-1], reverse=False)

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object_from_bmesh(name, bm, material=mat, smooth=True, parent=True)
        add_subsurf(obj, 1, 2)
        return obj

    # Arms
    arm_right = _sweep_tube(
        "Arm_Right",
        _catmull_rom(ARM_WAVE_POINTS, 25),
        ARM_R, N_AROUND, mats["M_Navy"],
        extend_start=0.04, extend_end=0.03,
    )
    arm_left = _sweep_tube(
        "Arm_Left",
        _catmull_rom(ARM_REST_POINTS, 25),
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
    leg_left = _sweep_tube(
        "Leg_Left",
        _catmull_rom(leg_points_left, 25),
        LEG_R, N_AROUND, mats["M_Navy"],
    )
    leg_right = _sweep_tube(
        "Leg_Right",
        _catmull_rom(leg_points_right, 25),
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
                factor = 0.006 * (1.0 - (dz / 0.012) ** 2) ** 2
                x *= 1.0 - factor
                y *= 1.0 - factor
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
```