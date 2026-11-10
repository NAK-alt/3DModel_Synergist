You are given 04_face.py (Blender 5.2; eyes + mouth sections merged and working). Write ONLY the code between `# >>> SECTION props` and `# <<< SECTION props` (one ```python fence, include both marker lines). Use what the file defines: FACE_X, EYE_Z, EYE_DX, EYE_W, EYE_H, MOUTH_TOP, hoop_z, eye_x(side), outline_patch(name, pts_uv, cx, cz, layer, mat), strip_patch(name, rows_uv, cx, cz, layer, mat), arc_rows, drive_hidden, RIG_MATERIAL_HOOKS, bpy, math. Don't change other code.

Expression props as hidden embroidered patches, each shown only when its Face_Ctrl switch is on. Create every patch with mat=None; materials come from a hook. Outline point lists are (u, v) relative to the given centre, closed, ~48-64 points, no duplicate end point.

Outline helpers (module level, underscore names):
- `_ellipse_pts(w, h, n=48)`.
- `_drop_pts(r, tip, n=48)`: teardrop pointing UP: a circle of radius r centred at (0, 0) whose top is replaced by a point at (0, tip): for angle a in [0, 2pi): if sin(a) > 0, blend toward the tip: x = r*cos(a)*(1 - s), y = r*sin(a) + (tip - r)*s where s = sin(a)**3 ... any smooth result is fine as long as it is a closed, non-self-intersecting teardrop with its point at the top.
- `_star_pts(r_out, r_in, points=5, per_edge=6)`: 5-point star starting at the top (angle 90 deg), straight edges subdivided into per_edge segments.
- `_heart_pts(size, n=64)`: classic parametric heart: x = 16 sin^3 t, y = 13 cos t - 5 cos 2t - 2 cos 3t - cos 4t, scaled so its width is `size`, centred at its bbox centre, point at the bottom.
- `_spiral_rows(r_max, turns, width, n=120)`: two rows for strip_patch (inner/outer edge of an Archimedean spiral band, radius from 0.012 to r_max).

`def build_props():` creates (names exactly) and returns the list of objects:
1. Blush: "Blush_Left" / "Blush_Right": _ellipse_pts(0.10, 0.05) at (FACE_X + 0.235, MOUTH_TOP - 0.02) / (FACE_X - 0.235, ...), layer 2. Visible when "blush > 0.5".
2. Sweat: "Prop_Sweat": _drop_pts(0.028, 0.075) at (FACE_X + 0.33, hoop_z(0.29) + 0.05), layer 3. Visible when "prop_sweat > 0.5".
3. Tears per side ("Prop_Tear_Left" / "_Right"): a stream running down from under the outer bottom of each eye: strip_patch with 3 rows of 16 points along a slightly wavy vertical path (u = outer * 0.03 + 0.006 sin(...)) from v = 0 down to v = -0.13, band width 0.032 (rows at -w/2, 0, +w/2 across), placed at (eye_x(side) + outer*0.06, EYE_Z - 0.13) where outer = +1 for Left, -1 for Right; plus a drop at its end "Prop_TearDrop_Left/Right": _drop_pts(0.022, 0.05) at the stream end (v = -0.15). Layer 3. Visible when "prop_tears > 0.5".
4. Stars per side "Prop_Star_Left/Right": _star_pts(0.105, 0.045) at the eye centre (eye_x(side), EYE_Z), layer 3. Visible when "prop_stars > 0.5".
5. Hearts per side "Prop_Heart_Left/Right": _heart_pts(0.2) at the eye centre, layer 3. Visible when "prop_hearts > 0.5".
6. Dizzy spirals per side "Prop_Dizzy_Left/Right": strip_patch(_spiral_rows(0.075, 2.5, 0.014)) at the eye centre, layer 3. Visible when "prop_dizzy > 0.5".
All visibility via drive_hidden(obj, "<control> <= 0.5", ["<control>"]).

`def _props_materials(lookdev, mats):` creates materials once with lookdev.create_satin(name, hex, angle, aniso=0.3) and assigns: Blush_* "MAT_Satin_Blush" "#F07C9A" angle 30; Prop_Sweat and Prop_TearDrop_* "MAT_Satin_Water" "#A8DDF5" angle 80; Prop_Tear_* the same water material angle 80; Prop_Star_* "MAT_Satin_Star" "#FFC93C" angle 45; Prop_Heart_* "MAT_Satin_Heart" "#E2324F" angle 45; Prop_Dizzy_* mats["MAT_Satin_Black"]. Then at module level: RIG_MATERIAL_HOOKS.append(_props_materials).
