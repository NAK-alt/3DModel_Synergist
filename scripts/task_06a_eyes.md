You are given 04_face.py (Blender 5.2). Write ONLY the code for the block between `# >>> SECTION eyes` and `# <<< SECTION eyes` (one ```python fence, include the two marker lines). Use only helpers/constants defined in the file: CONTROLS, EYE_Z, EYE_DX, EYE_W, EYE_H, PUPIL_OFFSET, HIGHLIGHT_OFFSET, BROW_CZ, FACE_X, hoop_z, eye_x(side), add_shape_key, drive_key, drive_hidden, xz_scale, xz_move, xz_rotate, strip_patch, arc_rows, bpy, math, Vector. Do not change anything else.

Define `def build_eyes():` that rigs the EXISTING eye/brow objects (made by 02_model.py) and creates two arc patches per eye. It returns a list of the new objects it created.

Existing objects per side in ("Left", "Right") (Left is at +X): Eye_{side}_Outline, Eye_{side}_White, Pupil_{side}, Highlight_{side}, Brow_{side}, Eyelid_{side}_Upper, Eyelid_{side}_Lower (eyelids are hidden half-ellipse patches 0.23 wide x 0.165 tall: the Upper one spans from the eye centre line z = EYE_Z UP to EYE_Z + 0.165; the Lower one from EYE_Z down to EYE_Z - 0.165).
Geometry facts: eye centre (cx, cz) = (eye_x(side), EYE_Z); pupil centre = (cx + PUPIL_OFFSET[0], cz + PUPIL_OFFSET[1]); highlight centre = (cx + HIGHLIGHT_OFFSET[0], cz + HIGHLIGHT_OFFSET[1]); eye top/bottom = cz +/- (EYE_H/2 + 0.01). Brow arc centre = (cx, BROW_CZ), arc radius ~0.083 spanning 30..150 degrees (so the brow's middle sits at about z = BROW_CZ + 0.083). "Inner" side of an eye = toward FACE_X: inner_sign = -1 for Left, +1 for Right.

Shape keys (all transforms are in the XZ plane) and their drivers (driver variables are named exactly like the Face_Ctrl properties; expressions must be valid Python, use max()/min()):
1. Eye_{side}_Outline and Eye_{side}_White:
   - "Wide": xz_scale(cx, cz, 1.10) ; driver "eye_wide".
   - "Squint": squash toward a line slightly above centre: z' = (cz + 0.02) + (z - (cz + 0.02)) * 0.45 for z below cz + 0.02, and * 0.8 above it; x unchanged ; driver f"squint_{S}" where S = "L" for Left, "R" for Right.
2. Pupil_{side} and Highlight_{side} (each object uses ITS OWN centre for scaling, but moves together):
   - "Look_Right": xz_move(+0.012, 0) ; driver "max(look_x, 0)".
   - "Look_Left": xz_move(-0.06, 0) ; driver "max(-look_x, 0)".
   - "Look_Up": xz_move(0, +0.045) ; driver "max(look_y, 0)".
   - "Look_Down": xz_move(0, -0.06) ; driver "max(-look_y, 0)".
   - "Big": for the pupil xz_scale(pupil centre, 1.3); for the highlight xz_move(-0.012, +0.012) (it stays on the bigger pupil) ; driver "max(pupil_size, 0)".
   - "Small": pupil xz_scale(pupil centre, 0.6); highlight xz_move(+0.01, -0.012) combined with xz_scale(own centre, 0.8) ; driver "max(-pupil_size, 0)".
   - "Wide": same as the eye ("eye_wide") but scaling about the EYE centre (cx, cz), so pupils move with the eye.
   - "Squint": same squash as the eye about the eye centre, driver f"squint_{S}".
3. Eyelid_{side}_Upper (blink lid, fabric-blue patch layered above the eye): two keys whose sum interpolates between "open" (a thin sliver at the eye top) and "closed" (covers the whole eye):
   - top = cz + 0.165. "Open": z' = top - (top - z) * 0.03 ; "Closed": z' = top - (top - z) * 2.05 (the lid's lower edge, which starts at cz, goes to ~cz - 0.173) and x scaled 1.04 about cx.
   - drivers: "Open" = f"1 - min(max(blink_{S}, 0), 1)"; "Closed" = f"min(max(blink_{S}, 0), 1)".
   - visibility: drive_hidden(lid, f"blink_{S} < 0.02 or happy_{S} > 0.5 or closed_smile > 0.5", [f"blink_{S}", f"happy_{S}", "closed_smile"]).
   Eyelid_{side}_Lower stays hidden (no drivers; set hide_render = hide_viewport = True).
4. Brow_{side} (pivot = brow middle (cx, BROW_CZ + 0.083)):
   - "Raise": xz_move(0, +0.035) ; driver f"brow_raise_{S}".
   - "Lower": xz_move(0, -0.02) ; driver "brow_lower".
   - "Angry": inner end down: xz_rotate(pivot, angle = inner_sign * -radians(18)) then xz_move(0, -0.012) (compose the two functions) ; driver "brow_angry".
   - "Sad": inner end up: xz_rotate(pivot, angle = inner_sign * radians(20)) then xz_move(0, +0.01) ; driver "brow_sad".
   Check the rotation sign: with angle positive, xz_rotate turns +x toward +z; for the Left eye (inner_sign -1) the inner end is at smaller x, so an angle of +18 deg moves the inner end DOWN. Make sure "Angry" lowers the inner end and "Sad" raises it for BOTH sides (verify with a quick numeric check in comments).
5. New arc patches (black satin later; create with mat=None) per side, built with strip_patch(name, arc_rows(...), cx, cz, layer, None):
   - f"EyeArc_{side}_Happy": "^"-shaped happy closed eye: arc_rows(radius=0.085, width=0.022, a0_deg=25, a1_deg=155), placed with its arc centre at (cx, cz - 0.05), layer 2.
   - f"EyeArc_{side}_Closed": content closed eye "u" curve: arc_rows(0.085, 0.022, 205, 335), arc centre at (cx, cz + 0.06), layer 2.
   - visibility: Happy shown only when happy_{S} > 0.5: drive_hidden(obj, f"happy_{S} <= 0.5", [f"happy_{S}"]); Closed: drive_hidden(obj, "closed_smile <= 0.5", ["closed_smile"]).
6. When an arc eye is shown, hide the open eye: for Eye_{side}_Outline, Eye_{side}_White, Pupil_{side}, Highlight_{side}: drive_hidden(obj, f"happy_{S} > 0.5 or closed_smile > 0.5 or prop_stars > 0.5 or prop_hearts > 0.5", [f"happy_{S}", "closed_smile", "prop_stars", "prop_hearts"]) — EXCEPT Pupil/Highlight which also hide when prop_dizzy > 0.5 (add "or prop_dizzy > 0.5" and the variable). Note: the outline and white stay visible under hearts/stars? No: hide them too (the star/heart overlay replaces the whole eye) — keep the expression above for all four, plus dizzy only for pupil/highlight.
Return the list of the four new arc objects.
