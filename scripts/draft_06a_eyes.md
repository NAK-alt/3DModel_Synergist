```python
# >>> SECTION eyes
def build_eyes():
    new_objects = []
    for side in ("Left", "Right"):
        S = side[0]  # "L" or "R"
        cx = eye_x(side)
        cz = EYE_Z
        inner_sign = -1 if side == "Left" else 1

        # Existing objects
        outline = bpy.data.objects.get(f"Eye_{side}_Outline")
        white = bpy.data.objects.get(f"Eye_{side}_White")
        pupil = bpy.data.objects.get(f"Pupil_{side}")
        highlight = bpy.data.objects.get(f"Highlight_{side}")
        brow = bpy.data.objects.get(f"Brow_{side}")
        eyelid_upper = bpy.data.objects.get(f"Eyelid_{side}_Upper")
        eyelid_lower = bpy.data.objects.get(f"Eyelid_{side}_Lower")

        # --- Eye outline and white ---
        # Wide
        add_shape_key(outline, "Wide", xz_scale(cx, cz, 1.10))
        drive_key(outline, "Wide", "eye_wide", ["eye_wide"])
        add_shape_key(white, "Wide", xz_scale(cx, cz, 1.10))
        drive_key(white, "Wide", "eye_wide", ["eye_wide"])

        # Squint (custom squash about line z = cz + 0.02)
        squash_fn = lambda co: Vector((co.x, co.y,
                                       (cz + 0.02) + (co.z - (cz + 0.02)) * (0.45 if co.z < cz + 0.02 else 0.8)))
        add_shape_key(outline, "Squint", squash_fn)
        drive_key(outline, "Squint", f"squint_{S}", [f"squint_{S}"])
        add_shape_key(white, "Squint", squash_fn)
        drive_key(white, "Squint", f"squint_{S}", [f"squint_{S}"])

        # --- Pupil and Highlight ---
        pcx, pcz = cx + PUPIL_OFFSET[0], cz + PUPIL_OFFSET[1]
        hcx, hcz = cx + HIGHLIGHT_OFFSET[0], cz + HIGHLIGHT_OFFSET[1]

        for obj, own_cx, own_cz in ((pupil, pcx, pcz), (highlight, hcx, hcz)):
            # Look directions
            add_shape_key(obj, "Look_Right", xz_move(0.012, 0))
            drive_key(obj, "Look_Right", "max(look_x, 0)", ["look_x"])
            add_shape_key(obj, "Look_Left", xz_move(-0.06, 0))
            drive_key(obj, "Look_Left", "max(-look_x, 0)", ["look_x"])
            add_shape_key(obj, "Look_Up", xz_move(0, 0.045))
            drive_key(obj, "Look_Up", "max(look_y, 0)", ["look_y"])
            add_shape_key(obj, "Look_Down", xz_move(0, -0.06))
            drive_key(obj, "Look_Down", "max(-look_y, 0)", ["look_y"])

            # Pupil size (different for pupil and highlight)
            if obj == pupil:
                add_shape_key(obj, "Big", xz_scale(pcx, pcz, 1.3))
                drive_key(obj, "Big", "max(pupil_size, 0)", ["pupil_size"])
                add_shape_key(obj, "Small", xz_scale(pcx, pcz, 0.6))
                drive_key(obj, "Small", "max(-pupil_size, 0)", ["pupil_size"])
            else:  # highlight
                add_shape_key(obj, "Big", xz_move(-0.012, 0.012))
                drive_key(obj, "Big", "max(pupil_size, 0)", ["pupil_size"])
                small_fn = lambda co: xz_move(0.01, -0.012)(xz_scale(hcx, hcz, 0.8)(co))
                add_shape_key(obj, "Small", small_fn)
                drive_key(obj, "Small", "max(-pupil_size, 0)", ["pupil_size"])

            # Wide and Squint follow the eye
            add_shape_key(obj, "Wide", xz_scale(cx, cz, 1.10))
            drive_key(obj, "Wide", "eye_wide", ["eye_wide"])
            add_shape_key(obj, "Squint", squash_fn)
            drive_key(obj, "Squint", f"squint_{S}", [f"squint_{S}"])

        # --- Eyelid Upper ---
        top = cz + 0.165
        # Open: thin sliver at top
        open_fn = lambda co: Vector((co.x, co.y, top - (top - co.z) * 0.03))
        add_shape_key(eyelid_upper, "Open", open_fn)
        drive_key(eyelid_upper, "Open", f"1 - min(max(blink_{S}, 0), 1)", [f"blink_{S}"])

        # Closed: cover eye, scale x about cx
        closed_fn = lambda co: Vector((cx + (co.x - cx) * 1.04, co.y,
                                       top - (top - co.z) * 2.05))
        add_shape_key(eyelid_upper, "Closed", closed_fn)
        drive_key(eyelid_upper, "Closed", f"min(max(blink_{S}, 0), 1)", [f"blink_{S}"])

        # Visibility: hide when happy/closed_smile or blink very low
        drive_hidden(eyelid_upper,
                     f"blink_{S} < 0.02 or happy_{S} > 0.5 or closed_smile > 0.5",
                     [f"blink_{S}", f"happy_{S}", "closed_smile"])

        # Eyelid Lower stays hidden permanently
        eyelid_lower.hide_render = True
        eyelid_lower.hide_viewport = True

        # --- Brow ---
        px, pz = cx, BROW_CZ + 0.083
        # Raise
        add_shape_key(brow, "Raise", xz_move(0, 0.035))
        drive_key(brow, "Raise", f"brow_raise_{S}", [f"brow_raise_{S}"])
        # Lower
        add_shape_key(brow, "Lower", xz_move(0, -0.02))
        drive_key(brow, "Lower", "brow_lower", ["brow_lower"])
        # Angry (inner down)
        angle_angry = inner_sign * -math.radians(18)
        angry_fn = lambda co: xz_move(0, -0.012)(xz_rotate(px, pz, angle_angry)(co))
        add_shape_key(brow, "Angry", angry_fn)
        drive_key(brow, "Angry", "brow_angry", ["brow_angry"])
        # Sad (inner up)
        angle_sad = inner_sign * math.radians(20)
        sad_fn = lambda co: xz_move(0, 0.01)(xz_rotate(px, pz, angle_sad)(co))
        add_shape_key(brow, "Sad", sad_fn)
        drive_key(brow, "Sad", "brow_sad", ["brow_sad"])

        # --- Hide open eye when replaced by arcs/props ---
        vis_expr = f"happy_{S} > 0.5 or closed_smile > 0.5 or prop_stars > 0.5 or prop_hearts > 0.5"
        vis_vars = [f"happy_{S}", "closed_smile", "prop_stars", "prop_hearts"]
        for obj in (outline, white):
            drive_hidden(obj, vis_expr, vis_vars)
        for obj in (pupil, highlight):
            expr = vis_expr + " or prop_dizzy > 0.5"
            vars = vis_vars + ["prop_dizzy"]
            drive_hidden(obj, expr, vars)

        # --- New arc patches ---
        happy_arc = strip_patch(f"EyeArc_{side}_Happy",
                                arc_rows(0.085, 0.022, 25, 155),
                                cx, cz - 0.05, 2, None)
        closed_arc = strip_patch(f"EyeArc_{side}_Closed",
                                 arc_rows(0.085, 0.022, 205, 335),
                                 cx, cz + 0.06, 2, None)
        # Visibility for arcs
        drive_hidden(happy_arc, f"happy_{S} <= 0.5", [f"happy_{S}"])
        drive_hidden(closed_arc, "closed_smile <= 0.5", ["closed_smile"])

        new_objects.extend([happy_arc, closed_arc])

    return new_objects
# <<< SECTION eyes
```