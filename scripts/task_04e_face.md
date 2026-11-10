You are given 02_model.py (Blender 5.2, headless; sections body, limbs, shoes, gloves merged and working). Write ONE new section block in one ```python fence:

# >>> SECTION face
...code...
SECTION_BUILDERS.append(("face", build_face))
# <<< SECTION face

Use only what the file has: BODY_R, BULGE, BODY_TOP, BODY_BOTTOM, BODY_H, HOOP_PCTS, hoop_z, bulge_radius, HOOP_MAJOR, HOOP_MINOR, FACE_X, new_object_from_bmesh, add_subsurf, lathe_rings, bridge_rings, bmesh, math, Vector, Matrix, bpy, ROOT_NAME. Underscore module-level helpers allowed. Don't change other code. The character faces -Y. All patches all-quad.

Face parts are thin EMBROIDERY PATCHES that follow the fabric via a Shrinkwrap modifier, and the nose is a felt ball.

1. Hidden shrinkwrap target "Face_Proxy": a lathe (64 around, rings every 0.005 in z, only from hoop_z(0.60) up to hoop_z(0.20), open ends, no caps) whose radius is
   r(z) = max(bulge_radius(z), max over hoops of (BODY_R + 0.034 * exp(-((z - hz)/0.028)**2)))
   i.e. the fabric surface with a soft bump where each rolled hoop is, so patches drape smoothly OVER a hoop. Create it with new_object_from_bmesh(..., parent=False); then hide_render = True, display_type = 'WIRE', and also obj.hide_set(True) is NOT allowed (keep it evaluable); do NOT parent it to the root.

2. `_patch(name, outline_uv, z_center, x_center, layer, mat, n=32, inner=4)`: an all-quad flat patch:
   - outline_uv: a function t -> (u, v) for t in [0, 1) giving the closed outline (u across, v up, metres, CCW), sampled at n points (n divisible by 4);
   - fill: `inner` rings morphing from the outline toward a square of half-size 0.35*min(extent) centred at the outline centroid, then an (n/4)x(n/4) quad grid inside the square (same "quad disk" idea as quad_disk_cap in build_body: corners at the square's 45/135/225/315 deg points, find them with a WRAPPED angle distance abs((a - ca + pi) % (2*pi) - pi), sides of n/4+1 verts, interior by bilinear interpolation of the borders).
   - place: world x = x_center + u, z = z_center + v, y = -sqrt(max(r(z)^2 - x^2, 0)) - 0.03 (just in front of the proxy; r as in 1).
   - modifiers in order: Shrinkwrap (target Face_Proxy, wrap_method 'NEAREST_SURFACEPOINT', wrap_mode 'OUTSIDE_SURFACE', offset = 0.0015 + 0.0015*layer), Solidify (thickness 0.0018, offset 1.0, use_even_offset True), Subdivision (add_subsurf(obj, 1, 2)).
   - parented to the root (new_object_from_bmesh default), smooth, normals facing -Y (recalc, then reverse faces if the average normal has y > 0).
   Helper outlines: `_ellipse(w, h)` -> t -> (w/2 cos 2pi t, h/2 sin 2pi t); `_d_shape(w, h)` -> a "D" smile: flat top edge then a half-ellipse below (top straight segment for t in [0, 0.25) going right-to-left... any correct closed CCW D outline with the flat side up, width w, depth h, top edge at v = 0).

3. Eyes (sizes approved in the blockout): for side, sx in (("Left", +1), ("Right", -1)): x = FACE_X + sx*0.14, eye_z = hoop_z(0.29) + 0.025 - 0.15.
   - "Eye_{side}_Outline": ellipse 0.22 x 0.32, layer 0, mats["M_Black"].
   - "Eye_{side}_White": ellipse 0.20 x 0.30, layer 1, mats["M_White"].
   - "Pupil_{side}": ellipse 0.11 x 0.15 at (x + 0.03, eye_z - 0.02), layer 2, mats["M_Black"].
   - "Highlight_{side}": ellipse 0.035 x 0.045 at (x + 0.005, eye_z + 0.025), layer 3, mats["M_White"].
   - Eyelids for future blinks, hidden: "Eyelid_{side}_Upper" = the upper half of a 0.23 x 0.33 ellipse (outline: half-ellipse arc v >= 0 closed by the straight line at v = 0) at the eye centre, layer 4, mats["M_Body"]; "Eyelid_{side}_Lower" = the lower half, same. Set hide_render = True and hide_viewport = True on both.
4. Brows "Brow_{side}": thin arched strip, layer 1, mats["M_Black"]: outline = the band between two concentric arcs (radius 0.075 and 0.075 + 0.016, from 30 to 150 degrees), as one closed CCW outline (outer arc left->right... any correct closed loop), centred at x, with the arc centre at z = hoop_z(0.29) + 0.035 - 0.065 (so the arch top sits ~0.05 above the hoop).
5. Mouth (centred at x = FACE_X, top edge at z = hoop_z(0.44) - 0.05):
   - "Mouth_Outline": D-shape 0.235 x 0.12, layer 0, mats["M_Black"], top edge 0.0075 higher.
   - "Mouth": D-shape 0.22 x 0.11, layer 1, mats["M_MouthIn"] (the dark inside of the open mouth).
   - "Teeth_Upper": a rounded rectangle 0.16 x 0.03 (ellipse with superellipse exponent 4: u = w/2*sign(c)*|c|^(2/4), v likewise) just under the top edge (centre at top - 0.017), layer 2, mats["M_White"].
   - "Tongue": ellipse 0.10 x 0.045 centred at top - 0.085, layer 2, mats["M_Tongue"].
6. Nose "Nose": felt ball: all-quad cube-sphere (create_cube size 2, subdivide_edges cuts=4 use_grid_fill, normalise), radius 0.04, centred at x = FACE_X, z = hoop_z(0.44), y = -(HOOP_MAJOR + HOOP_MINOR) - 0.03; mats["M_Felt"]; smooth + subsurf(1,2).
7. Return all created mascot objects (not the proxy).
