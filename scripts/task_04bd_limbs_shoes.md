You are given 02_model.py (Blender 5.2, headless; section "body" already merged and working). Write TWO new section blocks, returned in ONE ```python fence, in this exact form:

# >>> SECTION limbs
...code...
SECTION_BUILDERS.append(("limbs", build_limbs))
# <<< SECTION limbs
# >>> SECTION shoes
...code...
SECTION_BUILDERS.append(("shoes", build_shoes))
# <<< SECTION shoes

Use only what the file already has (constants ARM_WAVE_POINTS, ARM_REST_POINTS, ARM_RADIUS_BLOCKOUT, LEG_X, BODY_BOTTOM, SHOE_W, SHOE_L, SHOE_H, SHOE_FORWARD, helpers new_object_from_bmesh, add_subsurf, bridge_rings, bmesh, math, Vector, Matrix). Module-level helper functions are allowed inside the blocks (prefix them with an underscore). Do not change other code. Everything ALL-QUAD.

SECTION limbs: `build_limbs(mats) -> list`
- Helper `_catmull_rom(points, samples)`: centripetal Catmull-Rom spline through the given 3D points (duplicate the first and last point as phantom ends), returning `samples` points evenly spaced by ARC LENGTH (resample: first densely sample ~20 per segment, then pick points at equal arc length).
- Helper `_sweep_tube(name, path_pts, radius, n_around, mat, extend_start=0.0, extend_end=0.0)`: optionally extends the path straight out at both ends along the end tangents by the given lengths, then builds rings of n_around vertices around the path using PARALLEL-TRANSPORT frames (start with any normal perpendicular to the first tangent, then rotate it each step by the rotation between consecutive tangents, Vector.rotation_difference). Bridge consecutive rings with quads (bridge_rings). Close each end like this: add one ring at 60% radius pushed 0.4*radius past the end along the end tangent, then a final ring at 20% radius pushed 0.5*radius past the end, and close that last small ring with ONE n-gon face (it is tiny and always hidden inside the body, glove or shoe; these two n-gons are the only allowed non-quads).
  Smooth shading, then add_subsurf(obj, 1, 2). Return the object.
- Arms: rubber-hose tubes 1.3x thicker than the blockout: ARM_R = ARM_RADIUS_BLOCKOUT * 1.3. Path = _catmull_rom(points, 25) (so ~24 segments along the length; the ring loops are evenly spaced for bending). n_around = 16. "Arm_Right" from ARM_WAVE_POINTS (mats["M_Navy"]), "Arm_Left" from ARM_REST_POINTS. extend_start = 0.04 (sinks into the body), extend_end = 0.03 (into the glove cuff).
- Legs: "Leg_Left" at x = +LEG_X, "Leg_Right" at x = -LEG_X: straight paths from z = BODY_BOTTOM + 0.04 down to z = SHOE_H - 0.03 at y = 0, with a very slight forward curve: 3 control points (x, 0, top), (x, -0.008, mid), (x, 0, bottom). radius 0.04*1.3, 25 samples, n_around 16, mats["M_Navy"].
- Return [arm_right, arm_left, leg_left, leg_right].

SECTION shoes: `build_shoes(mats) -> list`
- Helper `_quad_ball(cuts)`: bmesh cube (bmesh.ops.create_cube size 2), subdivide all edges with bmesh.ops.subdivide_edges(edges=..., cuts=cuts, use_grid_fill=True), then normalise every vertex to the unit sphere (this gives an all-quad "cube sphere"). Return bm.
- `_shape_shoe(bm, side_sign)`: transform the unit cube-sphere vertices into a big round plush cartoon shoe, in local shoe space (x across, y along the foot with toe at -y, z up), sizes: full width SHOE_W, full length SHOE_L, full height SHOE_H:
  * base ellipsoid: x*SHOE_W/2, y*SHOE_L/2, z*SHOE_H/2.
  * toe bulge: for vertices with y < 0 (front half), scale x and z by (1 + 0.18 * t) where t = (-y_unit) clamped 0..1 smoothstep, and push z up by 0.02*t for z>0 so the toe is fatter and rounder than the heel.
  * flat sole: any vertex with z below sole level -SHOE_H/2 + 0.035 gets z = soft clamp toward that level (z = sole + (z - sole) * 0.15) so the bottom is almost flat.
  * sole seam: a groove running all round the shoe at height z_seam = -SHOE_H/2 + 0.045: vertices with |z - z_seam| < 0.012 move inward toward the shoe's vertical axis by 0.006 * (1 - (dz/0.012)^2)^2 (scale x,y components).
  * finally translate so the lowest point is at z = 0 in world.
- Shoes: "Shoe_Left" centred at x = +(LEG_X + 0.01), "Shoe_Right" at x = -(LEG_X + 0.01), y = -SHOE_FORWARD, rotated about Z by +8 deg (left) / -8 deg (right) so toes point slightly out; use cuts=8 for the cube sphere; apply rotation/translation directly to vertex coords with a Matrix (object transform stays identity). mats["M_White"], smooth, bmesh.ops.recalc_face_normals, add_subsurf(1, 2).
- Return [shoe_left, shoe_right].
