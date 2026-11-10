```python
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

    S = 0.0006
    BADGE_SCALE = 0.85
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

    LOGO_CZ = ((hoop_z(0.44) - 0.18) + (hoop_z(0.76) + 0.03)) / 2.0

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
    curve_data.extrude = 0.0008
    curve_data.bevel_depth = 0.0003
    curve_data.bevel_resolution = 1

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
        v.co = _conform(x, y, zl + 0.0008)

    word_obj = bpy.data.objects.new("Logo_Wordmark", me)
    bpy.context.scene.collection.objects.link(word_obj)
    word_obj.parent = bpy.data.objects[ROOT_NAME]
    me.materials.append(mats["M_Gold"])
    for p in me.polygons:
        p.use_smooth = False

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
```