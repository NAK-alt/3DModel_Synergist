```python
# >>> SECTION props
def _ellipse_pts(w, h, n=48):
    """Return n points on an ellipse centered at origin, full width w, height h."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((w / 2 * math.cos(a), h / 2 * math.sin(a)))
    return pts

def _drop_pts(r, tip, n=48):
    """Teardrop pointing UP: circle of radius r with top pulled to point at (0, tip)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s = math.sin(a)
        blend = s ** 3 if s > 0 else 0.0
        x = r * math.cos(a) * (1 - blend)
        y = r * s + (tip - r) * blend
        pts.append((x, y))
    return pts

def _star_pts(r_out, r_in, points=5, per_edge=6):
    """5-point star starting at top (90°), edges subdivided into per_edge segments."""
    base = []
    for i in range(points):
        ang_out = math.radians(90 + i * (360 / points))
        ang_in = ang_out + math.radians(180 / points)
        base.append((r_out * math.cos(ang_out), r_out * math.sin(ang_out)))
        base.append((r_in * math.cos(ang_in), r_in * math.sin(ang_in)))
    # base now has 2*points vertices alternating outer, inner
    total_edges = 2 * points
    pts = []
    for i in range(total_edges):
        start = base[i]
        end = base[(i + 1) % total_edges]
        for j in range(per_edge):
            t = j / per_edge
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            pts.append((x, y))
    return pts

def _heart_pts(size, n=64):
    """Classic parametric heart, point at bottom, scaled to width `size`, centered."""
    pts_raw = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
        pts_raw.append((x, y))
    # compute bounding box
    xs = [p[0] for p in pts_raw]
    ys = [p[1] for p in pts_raw]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width_raw = max_x - min_x
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    scale = size / width_raw
    pts = [((x - center_x) * scale, (y - center_y) * scale) for x, y in pts_raw]
    return pts

def _spiral_rows(r_max, turns, width, n=120):
    """Two rows (inner and outer) of an Archimedean spiral band, radius 0.012 to r_max."""
    inner = []
    outer = []
    for i in range(n + 1):
        t = i / n
        theta = 2 * math.pi * turns * t
        r = 0.012 + (r_max - 0.012) * t
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        # inner edge radius
        r_inner = max(0.001, r - width / 2)
        xi = r_inner * math.cos(theta)
        yi = r_inner * math.sin(theta)
        # outer edge radius
        r_outer = r + width / 2
        xo = r_outer * math.cos(theta)
        yo = r_outer * math.sin(theta)
        inner.append((xi, yi))
        outer.append((xo, yo))
    return [inner, outer]

def build_props():
    new_objects = []
    # Blush
    for side in ("Left", "Right"):
        cx = FACE_X + (0.235 if side == "Left" else -0.235)
        cz = MOUTH_TOP - 0.02
        obj = outline_patch(f"Blush_{side}", _ellipse_pts(0.10, 0.05), cx, cz, 2, None)
        drive_hidden(obj, "blush <= 0.5", ["blush"])
        new_objects.append(obj)
    # Sweat drop
    cx = FACE_X + 0.33
    cz = hoop_z(0.29) + 0.05
    obj = outline_patch("Prop_Sweat", _drop_pts(0.028, 0.075), cx, cz, 3, None)
    drive_hidden(obj, "prop_sweat <= 0.5", ["prop_sweat"])
    new_objects.append(obj)
    # Tears
    for side in ("Left", "Right"):
        outer = 1 if side == "Left" else -1
        cx = eye_x(side) + outer * 0.06
        cz = EYE_Z - 0.13
        # stream rows
        rows = []
        for offset in (-0.016, 0.0, 0.016):
            row = []
            for i in range(16):
                v = -0.13 * (i / 15)
                u_base = outer * 0.03 + 0.006 * math.sin(v * 20)
                row.append((u_base + offset, v))
            rows.append(row)
        stream = strip_patch(f"Prop_Tear_{side}", rows, cx, cz, 3, None)
        drive_hidden(stream, "prop_tears <= 0.5", ["prop_tears"])
        new_objects.append(stream)
        # drop at end
        drop_cx = cx
        drop_cz = cz - 0.15
        drop = outline_patch(f"Prop_TearDrop_{side}", _drop_pts(0.022, 0.05),
                              drop_cx, drop_cz, 3, None)
        drive_hidden(drop, "prop_tears <= 0.5", ["prop_tears"])
        new_objects.append(drop)
    # Stars and hearts and dizzy per eye
    for side in ("Left", "Right"):
        cx = eye_x(side)
        cz = EYE_Z
        star = outline_patch(f"Prop_Star_{side}", _star_pts(0.105, 0.045), cx, cz, 3, None)
        drive_hidden(star, "prop_stars <= 0.5", ["prop_stars"])
        new_objects.append(star)
        heart = outline_patch(f"Prop_Heart_{side}", _heart_pts(0.2), cx, cz, 3, None)
        drive_hidden(heart, "prop_hearts <= 0.5", ["prop_hearts"])
        new_objects.append(heart)
        dizzy = strip_patch(f"Prop_Dizzy_{side}", _spiral_rows(0.075, 2.5, 0.014),
                            cx, cz, 3, None)
        drive_hidden(dizzy, "prop_dizzy <= 0.5", ["prop_dizzy"])
        new_objects.append(dizzy)
    return new_objects

def _props_materials(lookdev, mats):
    """Assign materials to all prop objects, creating them if necessary."""
    def get_mat(name, hex, angle, aniso=0.3):
        mat = mats.get(name)
        if mat is None:
            mat = lookdev.create_satin(name, hex, angle, aniso=aniso)
            mats[name] = mat
        return mat

    mapping = {
        "Blush_Left": ("MAT_Satin_Blush", "#F07C9A", 30),
        "Blush_Right": ("MAT_Satin_Blush", "#F07C9A", 30),
        "Prop_Sweat": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Tear_Left": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Tear_Right": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_TearDrop_Left": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_TearDrop_Right": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Star_Left": ("MAT_Satin_Star", "#FFC93C", 45),
        "Prop_Star_Right": ("MAT_Satin_Star", "#FFC93C", 45),
        "Prop_Heart_Left": ("MAT_Satin_Heart", "#E2324F", 45),
        "Prop_Heart_Right": ("MAT_Satin_Heart", "#E2324F", 45),
        "Prop_Dizzy_Left": ("MAT_Satin_Black", None, None),
        "Prop_Dizzy_Right": ("MAT_Satin_Black", None, None),
    }
    for obj_name, (mat_name, hex, angle) in mapping.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue
        if mat_name == "MAT_Satin_Black":
            mat = mats.get("MAT_Satin_Black")
            if mat is None:
                # Should have been created by lookdev; fallback
                mat = lookdev.create_satin("MAT_Satin_Black", "#000000", 0, aniso=0.3)
                mats["MAT_Satin_Black"] = mat
        else:
            mat = get_mat(mat_name, hex, angle)
        obj.data.materials.clear()
        obj.data.materials.append(mat)

RIG_MATERIAL_HOOKS.append(_props_materials)
# <<< SECTION props
```