```python
# >>> SECTION mouth
def _mouth_outline(w, h, sag=0.0, lift=0.0, asym=0.0, r=0.5, dz=0.0, n=48):
    """Return list of n (u, v) points for a closed mouth outline, CCW.
    Top edge: k = 0..n/2 from right to left, bottom edge: k = 1..n/2-1 from left to right.
    """
    pts = []
    half = n // 2
    # Top edge (right to left)
    for k in range(half + 1):
        u = w / 2 - w * k / half
        s = 2 * u / w
        v = dz + lift * s * s - sag * (1 - s * s) + asym * 0.03 * s
        pts.append((u, v))
    # Bottom edge (left to right, excluding endpoints already included)
    for k in range(1, half):
        u = -w / 2 + w * k / half
        s = 2 * u / w
        v_top = dz + lift * s * s - sag * (1 - s * s) + asym * 0.03 * s
        v = v_top - h * max(1 - s * s, 0) ** r
        pts.append((u, v))
    return pts

MOUTH_SHAPES = {
    "rest": dict(w=MOUTH_W, h=MOUTH_H),
    "small_smile": dict(w=0.17, h=0.012, lift=0.025),
    "big_smile": dict(w=0.26, h=0.10, lift=0.03),
    "laugh": dict(w=0.26, h=0.15, lift=0.035),
    "O": dict(w=0.10, h=0.11, sag=-0.015),
    "flat": dict(w=0.16, h=0.010),
    "frown": dict(w=0.17, h=0.02, sag=-0.02, lift=-0.03),
    "smirk_L": dict(w=0.17, h=0.015, asym=1),
    "smirk_R": dict(w=0.17, h=0.015, asym=-1),
    "pout": dict(w=0.08, h=0.03, sag=-0.01, dz=-0.01),
    "shout": dict(w=0.24, h=0.17, sag=-0.01, lift=-0.005, r=0.3),
    "vA": dict(w=0.18, h=0.13, r=0.45),
    "vE": dict(w=0.22, h=0.06, lift=0.01, r=0.4),
    "vI": dict(w=0.20, h=0.035, lift=0.015),
    "vO": dict(w=0.11, h=0.10, sag=-0.012),
    "vU": dict(w=0.07, h=0.05, sag=-0.008),
    "vMBP": dict(w=0.15, h=0.006),
    "vFV": dict(w=0.16, h=0.025),
}

def _set_key(obj, key_name, coords):
    """Add a shape key to obj and set its vertices to the given world-space coords."""
    ensure_basis(obj)
    kb = obj.shape_key_add(name=key_name, from_mix=False)
    for i, coord in enumerate(coords):
        kb.data[i].co = coord
    kb.slider_min, kb.slider_max = 0.0, 1.0
    return kb

def _xyz(u, v, y=None):
    """Convert (u, v) relative to (FACE_X, MOUTH_TOP) to a Vector in world space.
    Default y uses front_y; provide y to override."""
    x = FACE_X + u
    z = MOUTH_TOP + v
    if y is None:
        y = front_y(x, z)
    return Vector((x, y, z))

def _mouth_outline_points(shape_name):
    """Return list of (u, v) points for a given MOUTH_SHAPES entry."""
    params = MOUTH_SHAPES[shape_name]
    w = params.get("w", MOUTH_W)
    h = params.get("h", MOUTH_H)
    sag = params.get("sag", 0.0)
    lift = params.get("lift", 0.0)
    asym = params.get("asym", 0.0)
    r = params.get("r", 0.5)
    dz = params.get("dz", 0.0)
    return _mouth_outline(w, h, sag, lift, asym, r, dz)

def _compute_lip_band_coords(shape_name):
    """Return two lists: inner loop coords and outer loop coords (world space) for the lip band."""
    pts = _mouth_outline_points(shape_name)
    n = len(pts)
    inner = []
    outer = []
    for i, (u, v) in enumerate(pts):
        # compute outward normal in XZ plane
        prev = pts[(i - 1) % n]
        next_ = pts[(i + 1) % n]
        du = next_[0] - prev[0]
        dv = next_[1] - prev[1]
        length = math.hypot(du, dv)
        if length < 1e-9:
            # degenerate, use perpendicular to line from center
            cx = sum(p[0] for p in pts) / n
            cz = sum(p[1] for p in pts) / n
            du, dv = u - cx, v - cz
            length = math.hypot(du, dv)
            if length < 1e-9:
                du, dv = 0.0, 1.0
                length = 1.0
        # tangent normalized
        tu, tv = du / length, dv / length
        # outward normal for CCW: (tv, -tu)
        nx, nz = tv, -tu
        inner.append(_xyz(u, v))
        outer.append(_xyz(u + 0.009 * nx, v + 0.009 * nz))
    return inner, outer

def _compute_cutter_loops(shape_name):
    """Return front and back loop coords (world space) for the cutter."""
    pts = _mouth_outline_points(shape_name)
    n = len(pts)
    # centroid
    cx = sum(p[0] for p in pts) / n
    cz = sum(p[1] for p in pts) / n
    front_y = -(bulge_radius(MOUTH_TOP) + 0.08)
    back_y = -(bulge_radius(MOUTH_TOP) - 0.035)
    front = []
    back = []
    for u, v in pts:
        front.append(_xyz(u, v, y=front_y))
        # scaled about centroid
        su = cx + 0.8 * (u - cx)
        sv = cz + 0.8 * (v - cz)
        back.append(_xyz(su, sv, y=back_y))
    return front, back

def _create_cube_sphere(radius_x, radius_y, radius_z, location):
    """Create a mesh object from a subdivided cube normalized to an ellipsoid."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=3, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized()
        v.co.x *= radius_x
        v.co.y *= radius_y
        v.co.z *= radius_z
    me = bpy.data.meshes.new("tmp_sphere")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("tmp_sphere_obj", me)
    obj.location = location
    # will be parented and renamed later
    return obj

def build_mouth():
    """Build the mouth lip, cutter, teeth, tongue, and cheek/fur effects. Returns list of new objects."""
    # Delete old objects
    for old_name in ("Mouth", "Mouth_Outline", "Teeth_Upper", "Tongue"):
        obj = bpy.data.objects.get(old_name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    # 1. Mouth_Lip
    lip_name = "Mouth_Lip"
    lip_obj = bpy.data.objects.new(lip_name, bpy.data.meshes.new(lip_name))
    bpy.context.scene.collection.objects.link(lip_obj)
    lip_obj.parent = bpy.data.objects[ROOT_NAME]
    # build mesh for rest shape (basis)
    inner_rest, outer_rest = _compute_lip_band_coords("rest")
    n = len(inner_rest)
    bm = bmesh.new()
    inner_verts = [bm.verts.new(co) for co in inner_rest]
    outer_verts = [bm.verts.new(co) for co in outer_rest]
    for k in range(n):
        bm.faces.new((inner_verts[k], inner_verts[(k+1)%n], outer_verts[(k+1)%n], outer_verts[k]))
    bm.normal_update()
    bm.to_mesh(lip_obj.data)
    bm.free()
    for p in lip_obj.data.polygons:
        p.use_smooth = True
    patch_modifiers(lip_obj, layer=1)
    # basis shape key
    ensure_basis(lip_obj)
    # add shape keys for other shapes
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        inner, outer = _compute_lip_band_coords(shape_name)
        coords = inner + outer  # inner first, then outer
        _set_key(lip_obj, f"S_{shape_name}", coords)
        # driver: control name matches shape_name (except some have prefix)
        control = shape_name  # e.g., "small_smile" -> "m_small_smile"? Actually mapping: m_small_smile -> small_smile
        # We need to map control name: m_small_smile -> small_smile, v_A -> vA, etc.
        # But the control names in CONTROLS are "m_small_smile", "m_big_smile", etc. So we need to find the control that maps to this shape.
        # The mapping is given: m_small_smile->small_smile, etc.
        # We can create a reverse mapping: from shape_name to control_name.
        control_map = {
            "small_smile": "m_small_smile",
            "big_smile": "m_big_smile",
            "laugh": "m_laugh",
            "O": "m_O",
            "flat": "m_flat",
            "frown": "m_frown",
            "smirk_L": "m_smirk_L",
            "smirk_R": "m_smirk_R",
            "pout": "m_pout",
            "shout": "m_shout",
            "vA": "v_A",
            "vE": "v_E",
            "vI": "v_I",
            "vO": "v_O",
            "vU": "v_U",
            "vMBP": "v_MBP",
            "vFV": "v_FV",
        }
        ctrl_name = control_map[shape_name]
        drive_key(lip_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])

    # 2. Mouth_Cutter
    cutter_name = "Mouth_Cutter"
    cutter_obj = bpy.data.objects.new(cutter_name, bpy.data.meshes.new(cutter_name))
    bpy.context.scene.collection.objects.link(cutter_obj)
    cutter_obj.parent = bpy.data.objects[ROOT_NAME]
    front_rest, back_rest = _compute_cutter_loops("rest")
    bm = bmesh.new()
    front_verts = [bm.verts.new(co) for co in front_rest]
    back_verts = [bm.verts.new(co) for co in back_rest]
    # side quads
    for k in range(n):
        bm.faces.new((front_verts[k], front_verts[(k+1)%n], back_verts[(k+1)%n], back_verts[k]))
    # front and back n-gons (normals outward)
    bm.faces.new(front_verts)
    bm.faces.new(list(reversed(back_verts)))  # reversed to face outward (back should face +Y? Actually cutter is inside, outward normals should point away from cavity)
    bm.normal_update()
    bm.to_mesh(cutter_obj.data)
    bm.free()
    cutter_obj.hide_render = True
    cutter_obj.display_type = 'WIRE'
    ensure_basis(cutter_obj)
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        front, back = _compute_cutter_loops(shape_name)
        coords = front + back
        _set_key(cutter_obj, f"S_{shape_name}", coords)
        ctrl_name = control_map[shape_name]
        drive_key(cutter_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])

    # 3. Mouth_Teeth
    teeth_name = "Mouth_Teeth"
    teeth_obj = _create_cube_sphere(0.075, 0.012, 0.016,
                                    (FACE_X, -(bulge_radius(MOUTH_TOP)) + 0.010, MOUTH_TOP - 0.020))
    teeth_obj.name = teeth_name
    bpy.context.scene.collection.objects.link(teeth_obj)
    teeth_obj.parent = bpy.data.objects[ROOT_NAME]
    teeth_obj.data.name = teeth_name
    for p in teeth_obj.data.polygons:
        p.use_smooth = True
    sub = teeth_obj.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    ensure_basis(teeth_obj)
    # store basis vertex coords for later scaling/translation
    basis_teeth_coords = [v.co.copy() for v in teeth_obj.data.vertices]
    # For each shape
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        params = MOUTH_SHAPES[shape_name]
        w = params.get("w", MOUTH_W)
        h = params.get("h", MOUTH_H)
        sag = params.get("sag", 0.0)
        lift = params.get("lift", 0.0)
        asym = params.get("asym", 0.0)
        r = params.get("r", 0.5)
        dz = params.get("dz", 0.0)
        # compute v_top(0) for this shape
        # v_top(s) = dz + lift*s^2 - sag*(1-s^2) + asym*0.03*s, at s=0 -> dz - sag
        v_top_mid = dz - sag
        # top z of teeth (basis): centre_z + 0.016
        centre_z = MOUTH_TOP - 0.020
        top_z_basis = centre_z + 0.016
        target_top_z = MOUTH_TOP + v_top_mid
        dz_trans = target_top_z - top_z_basis
        scale_x = w / MOUTH_W
        is_closed = h < 0.03
        push_y = 0.03 if is_closed else 0.0
        new_coords = []
        for v in basis_teeth_coords:
            nx = FACE_X + (v.x - FACE_X) * scale_x
            ny = v.y + push_y
            nz = v.z + dz_trans
            # For vFV, lower by 0.012
            if shape_name == "vFV":
                nz -= 0.012
            new_coords.append(Vector((nx, ny, nz)))
        _set_key(teeth_obj, f"S_{shape_name}", new_coords)
        ctrl_name = control_map[shape_name]
        drive_key(teeth_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])
    # Teeth_Show key
    show_coords = []
    top_z = centre_z + 0.016
    for v in basis_teeth_coords:
        nx = v.x
        ny = v.y - 0.008
        nz = top_z + (v.z - top_z) * 1.4
        show_coords.append(Vector((nx, ny, nz)))
    _set_key(teeth_obj, "Teeth_Show", show_coords)
    drive_key(teeth_obj, "Teeth_Show", "m_teeth", ["m_teeth"])

    # 4. Mouth_Tongue
    tongue_name = "Mouth_Tongue"
    tongue_obj = _create_cube_sphere(0.05, 0.02, 0.022,
                                     (FACE_X, -(bulge_radius(MOUTH_TOP)) + 0.018, MOUTH_TOP - 0.068))
    tongue_obj.name = tongue_name
    bpy.context.scene.collection.objects.link(tongue_obj)
    tongue_obj.parent = bpy.data.objects[ROOT_NAME]
    tongue_obj.data.name = tongue_name
    for p in tongue_obj.data.polygons:
        p.use_smooth = True
    sub = tongue_obj.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    ensure_basis(tongue_obj)
    basis_tongue_coords = [v.co.copy() for v in tongue_obj.data.vertices]
    # For each shape
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        params = MOUTH_SHAPES[shape_name]
        h = params.get("h", MOUTH_H)
        sag = params.get("sag", 0.0)
        dz = params.get("dz", 0.0)
        # v_top(0) = dz - sag
        v_top_mid = dz - sag
        v_bottom_mid = v_top_mid - h
        target_top_z = MOUTH_TOP + v_bottom_mid + 0.024  # top of tongue?
        # tongue top basis = centre_z + 0.022
        centre_z = MOUTH_TOP - 0.068
        top_z_basis = centre_z + 0.022
        dz_trans = target_top_z - top_z_basis
        is_closed = h < 0.03
        push_y = 0.045 if is_closed else 0.0
        new_coords = []
        for v in basis_tongue_coords:
            nx = v.x
            ny = v.y + push_y
            nz = v.z + dz_trans
            new_coords.append(Vector((nx, ny, nz)))
        _set_key(tongue_obj, f"S_{shape_name}", new_coords)
        ctrl_name = control_map[shape_name]
        drive_key(tongue_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])
    # Tongue_Out key
    out_coords = []
    cx = FACE_X
    cy = -(bulge_radius(MOUTH_TOP)) + 0.018
    cz = MOUTH_TOP - 0.068
    for v in basis_tongue_coords:
        nx = cx + (v.x - cx) * 0.9
        ny = cy + (v.y - cy) * 1.6 - 0.05
        nz = v.z - 0.035
        out_coords.append(Vector((nx, ny, nz)))
    _set_key(tongue_obj, "Tongue_Out", out_coords)
    drive_key(tongue_obj, "Tongue_Out", "m_tongue_out", ["m_tongue_out"])

    # 5. Cheek puff on Body
    body = bpy.data.objects.get("Body")
    if body:
        ensure_basis(body)
        # create CheekPuff shape key
        kb = body.shape_key_add(name="CheekPuff", from_mix=False)
        basis_body_coords = [v.co.copy() for v in body.data.vertices]
        cheek_centers = [(FACE_X + 0.17, MOUTH_TOP - 0.03), (FACE_X - 0.17, MOUTH_TOP - 0.03)]
        for i, v in enumerate(body.data.vertices):
            orig = basis_body_coords[i]
            x, y, z = orig
            new_x, new_y, new_z = x, y, z
            for cx, cz in cheek_centers:
                d2 = ((x - cx) / 0.08) ** 2 + ((z - cz) / 0.07) ** 2
                if d2 < 1:
                    factor = 0.014 * (1 - d2) ** 2
                    # outward direction in XY plane
                    length = math.hypot(x, y)
                    if length > 1e-9:
                        dir_x = x / length
                        dir_y = y / length
                    else:
                        dir_x, dir_y = 0.0, 0.0
                    new_x += dir_x * factor
                    new_y += dir_y * factor
            kb.data[i].co = Vector((new_x, new_y, new_z))
        kb.slider_min, kb.slider_max = 0.0, 1.0
        drive_key(body, "CheekPuff", "cheek_puff", ["cheek_puff"])

        # 6. Fur mask vertex group
        if "fur_density" not in body.vertex_groups:
            vg = body.vertex_groups.new(name="fur_density")
        else:
            vg = body.vertex_groups["fur_density"]
        for i, v in enumerate(body.data.vertices):
            x, y, z = v.co
            if y < 0:
                e2 = ((x - FACE_X) / 0.19) ** 2 + ((z - (MOUTH_TOP - 0.06)) / 0.13) ** 2
                dist = math.sqrt(e2)
                if dist < 1.0:
                    weight = 0.0
                elif dist > 1.3:
                    weight = 1.0
                else:
                    weight = (dist - 1.0) / (1.3 - 1.0)
            else:
                weight = 1.0
            vg.add([i], weight, 'REPLACE')

    return [lip_obj, cutter_obj, teeth_obj, tongue_obj]

def add_mouth_recess(lookdev, mats):
    """Add Boolean modifier to Body using Mouth_Cutter and assign cavity material."""
    body = bpy.data.objects.get("Body")
    cutter = bpy.data.objects.get("Mouth_Cutter")
    if not body or not cutter:
        return
    # Create cavity material
    cavity_mat = mats.get("MAT_Mouth_Cavity")
    if cavity_mat is None:
        cavity_mat = lookdev.create_satin("MAT_Mouth_Cavity", "#24070A", 10, aniso=0.2)
        mats["MAT_Mouth_Cavity"] = cavity_mat
    # Assign to cutter (clear and append)
    cutter.data.materials.clear()
    cutter.data.materials.append(cavity_mat)
    # Add Boolean modifier to Body
    bool_mod = body.modifiers.new("MouthRecess", 'BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    # Try MANIFOLD then EXACT solver
    try:
        bool_mod.solver = 'MANIFOLD'
    except TypeError:
        try:
            bool_mod.solver = 'EXACT'
        except TypeError:
            pass
    # Set material_mode if available
    if hasattr(bool_mod, "material_mode"):
        try:
            bool_mod.material_mode = 'TRANSFER'
        except TypeError:
            pass
    # Ensure Body has cavity material in a slot
    if cavity_mat.name not in [m.name for m in body.data.materials if m]:
        body.data.materials.append(cavity_mat)
    # Make Boolean last in stack
    if body.modifiers:
        # Move Boolean to end
        while body.modifiers[-1] != bool_mod:
            bpy.ops.object.modifier_move_down(modifier=bool_mod.name)

def _mouth_materials(lookdev, mats):
    """Assign materials to mouth objects."""
    lip = bpy.data.objects.get("Mouth_Lip")
    teeth = bpy.data.objects.get("Mouth_Teeth")
    tongue = bpy.data.objects.get("Mouth_Tongue")
    if lip:
        lip.data.materials.clear()
        lip.data.materials.append(mats["MAT_Satin_Black_MouthOutline"])
    if teeth:
        teeth.data.materials.clear()
        teeth.data.materials.append(mats["MAT_Satin_White_Teeth"])
    if tongue:
        tongue.data.materials.clear()
        tongue.data.materials.append(mats["MAT_Satin_Tongue"])

RIG_MATERIAL_HOOKS.append(_mouth_materials)
# <<< SECTION mouth
```