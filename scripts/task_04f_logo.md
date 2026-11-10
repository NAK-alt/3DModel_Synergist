You are given 02_model.py (Blender 5.2, headless; sections body, limbs, shoes, gloves, face merged and working) and the header of trace_logo.py, which describes refs/logo_trace.json. Write ONE new section block in one ```python fence:

# >>> SECTION logo
...code...
SECTION_BUILDERS.append(("logo", build_logo))
# <<< SECTION logo

Use only what exists: PROJECT_ROOT, BODY_R, BULGE, BODY_H, hoop_z, bulge_radius, LOGO_X, new_object_from_bmesh, add_subsurf, bridge_rings, bmesh, bpy, math, os, Vector. Add `import json` inside the block. Underscore helpers allowed. Don't change other code. If refs/logo_trace.json is missing, print "[02_model] logo: refs/logo_trace.json missing, run scripts/trace_logo.py" and return [].

JSON (pixel coords, origin top-left, y DOWN): size [w, h]; word: list of closed curves {start:[x,y], segs:[{c1,c2,end} (cubic bezier) | {corner, end} (two straight lines start->corner->end)]}; balls: 3 x {cx, cy, r}; badge: {cx, cy, r_inner, r_outer}.

Layout (metres):
- S = 0.0006 m per pixel. BADGE_SCALE = 0.85: the badge ring radii AND the ball offsets/radii are scaled by 0.85 about the badge centre (cx, cy).
- Logo centre: compute the bounding box (in px) of all word curve points and of the scaled badge outer circle; the centre of that box maps to u = 0, v = 0. u = (x - cx_box) * S, v = -(y - cy_box) * S (flip y).
- Vertical centre of the logo on the body: LOGO_CZ = ((hoop_z(0.44) - 0.18) + (hoop_z(0.76) + 0.03)) / 2.
- `_conform(u, v, d)` -> Vector: wrap the flat logo plane onto the barrel front: z = LOGO_CZ + v; R = bulge_radius(z) + 0.0015 + d; angle = (LOGO_X + u) / (BODY_R + BULGE); return (R*sin(angle), -R*cos(angle), z). d is height above the fabric (outward).

1. Wordmark + flame "Logo_Wordmark" (mats["M_Gold"]):
   - Build ONE 2D curve datablock (bpy.data.curves.new(type='CURVE'), dimensions '2D', fill_mode 'BOTH', resolution_u 3, extrude 0.0008, bevel_depth 0.0003, bevel_resolution 1) containing one cyclic BEZIER spline per traced curve (holes are separate splines; 2D even-odd fill handles them).
   - Spline points = the 'end' of every segment, in order (the last end equals start). For a bezier seg from P(prev end) to E: prev point's handle_right = c1, E's handle_left = c2, both handle types 'FREE'. For a corner seg: insert TWO points: the corner C (both handles 'VECTOR') and the end E with handle_left 'VECTOR'. Set every point's handle types BEFORE assigning handle coordinates. Coordinates are (u, v, 0) in metres (use the u,v mapping above).
   - Link a temporary object, evaluate it (bpy.context.evaluated_depsgraph_get()), make a mesh with bpy.data.meshes.new_from_object(eval_obj), remove the temp curve object and curve datablock.
   - Conform every vertex: (x, y, zl) of the mesh -> _conform(x, y, zl + 0.0008) (zl is -0.0008..+0.0008 from the extrude, so d is 0..0.0016 plus bevel). Create the object with that mesh, parent to bpy.data.objects[ROOT_NAME], material, smooth shading OFF (flat letters with crisp edges) but add an Auto-smooth-free look: just leave flat. No subdivision.
2. Badge ring "Logo_Badge_Ring" (mats["M_White"]): a rolled fabric ring built in flat logo space then conformed: torus around the badge centre (u_b, v_b), 64 segments around x 12 around the tube, tube centre radius rc = (r_in + r_out)/2 and tube radius rt = (r_out - r_in)/2 (scaled px * S), cross-section ellipse: in-plane radius rt, height 0.45*rt. Vertex (u, v, d) with d = 0.45*rt*sin(phi) + 0.45*rt*0.6 (so it sits mostly above the fabric) -> _conform. Quads via bridge_rings(closed=True). Smooth, add_subsurf(1, 2).
3. Balls "Logo_Ball_1..3" (mats["M_Gold"]): slightly raised domes: all-quad cube-sphere (create_cube size 2, subdivide_edges cuts=4 use_grid_fill, normalise), radius rb = r * 0.85 * S; local (a, b, c) -> u = u_ball + rb*a, v = v_ball + rb*b, d = 0.35*rb*c + 0.25*rb (a raised dome, bottom slightly sunk). Smooth, add_subsurf(1, 2).
Return [wordmark, ring, ball1, ball2, ball3].
