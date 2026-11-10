```python
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
            # Center at local (0,0,0.085)
            z += 0.085
            local_pt = Vector((x, y, z))
            world_pt = to_world(local_pt, wrist, M)
            v.co = world_pt
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
                y = 0.07 * math.sin(theta)
                z = base[2] + 0.07 - 0.07 * math.cos(theta)  # base_z + radius*(1-cos)
                # Add side fan: rotate around z? We'll add x offset proportional to t?
                x = base[0] + math.sin(side) * (0.07 * math.sin(theta))  # simple
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
    # Fingers
    finger_paths = finger_paths_relaxed()
    fingers_L = []
    for i, path in enumerate(finger_paths, start=1):
        fingers_L.append(build_tube_part(f"Glove_Left_Finger{i}", wrist_L, M_L, path, 0.029, 12, extend_start=0.02))
    # Thumb
    thumb_path = thumb_path_relaxed(thumb_sign_L)
    thumb_L = build_tube_part("Glove_Left_Thumb", wrist_L, M_L, thumb_path, 0.031, 12, extend_start=0.025)

    gloves_objects = [cuff_R, palm_R] + fingers_R + [thumb_R] + [cuff_L, palm_L] + fingers_L + [thumb_L]
    return gloves_objects

SECTION_BUILDERS.append(("gloves", build_gloves))
# <<< SECTION gloves
```