You are given 02_model.py (Blender 5.2, headless; sections body, limbs, shoes merged and working). Write ONE new section block in one ```python fence:

# >>> SECTION gloves
...code...
SECTION_BUILDERS.append(("gloves", build_gloves))
# <<< SECTION gloves

Use only what the file already has: ARM_WAVE_POINTS, ARM_REST_POINTS, catmull_rom(points, samples), sweep_tube(name, path_pts, radius, n_around, mat, extend_start, extend_end) (returns an object that already has smooth shading + Subdivision; its ends are closed with tapered rings that read as rounded tips after subdivision), new_object_from_bmesh, add_subsurf, bridge_rings, bmesh, math, Vector, Matrix. Underscore-prefixed module-level helpers are fine. Do not change other code. All parts all-quad (except sweep_tube's own end n-gons), material mats["M_White"].

Goal: proper plush CARTOON GLOVES (Mickey style): puffy palm, a thumb + 3 chunky rounded fingers (plush-thick, no thin sticks), and a rolled cuff with a seam. Two hands:
- "Right" = the waving hand at the end of ARM_WAVE_POINTS: OPEN palm facing the camera (-Y world), fingers spread.
- "Left" = the resting hand at the end of ARM_REST_POINTS (hanging by the hip): relaxed, palm facing the body (-X world), fingers lightly curled.

1. `_hand_frame(arm_points, palm_hint, thumb_hint)`:
   path = catmull_rom(arm_points, 25); wrist = path[-1]; Z = (path[-1] - path[-2]).normalized() (direction the hand points);
   Y = palm normal = palm_hint orthogonalised against Z and normalised; X = Y.cross(Z).
   thumb_sign = 1 if X.dot(thumb_hint) > 0 else -1.
   Return wrist, Matrix 3x3 with columns X, Y, Z (so world = wrist + M @ local), thumb_sign.
   Calls: Right: palm_hint (0,-1,0), thumb_hint (+1,0,0) (thumb toward the body centre). Left: palm_hint (-1,0,0), thumb_hint (0,-1,0) (thumb forward).
   Local axes: x across the hand, y out of the palm front, z along the hand from wrist to finger tips.

2. Cuff "Glove_{side}_Cuff": rolled fabric ring around the wrist, built in local space then transformed: torus around the local z axis, 24 major x 12 minor segments, major radius 0.062, minor radius 0.026, centred at local z = 0.012; flare it slightly: the ring's minor cross-section is an ellipse 1.0 radial x 1.25 along z. Seam groove on the outermost equator (minor angle 0): inward 0.003 with falloff over +/-0.35 rad, use wrapped angle distance min(a, 2*pi - a). Quads only (bridge rings closed both ways). Smooth + add_subsurf(1,2).

3. Palm "Glove_{side}_Palm": all-quad cube-sphere (bmesh.ops.create_cube size 2, bmesh.ops.subdivide_edges cuts=5 use_grid_fill=True, normalise verts), scaled to local half-sizes (0.085 across x, 0.045 thick y, 0.080 along z), centred at local (0, 0, 0.085). Puffy: back of the hand (y < 0) pushed out an extra 15% in y; the palm front (y > 0) flattened to 85%. Transform to world, recalc normals, smooth, subsurf(1,2).

4. Three fingers "Glove_{side}_Finger1..3" with sweep_tube, radius 0.029 (chunky), n_around 12, extend_start 0.02 (into the palm), extend_end 0.0. Bases at the palm's top edge: local x = -0.050, 0.0, +0.050, y = 0.0, z = 0.135. Build each path as 4-6 local points, then transform to world, then pass catmull_rom(path_world, 12) to sweep_tube.
   - OPEN (Right): straight fingers, length 0.095 (middle) / 0.085 (sides), fanned in the local xz-plane at -16, 0, +16 degrees from +z, very slight backward arch (y -0.006 at the middle point).
   - RELAXED (Left): each finger follows a curl toward the palm front (+y): arc in the yz-plane with radius 0.07 curling through 75 degrees (middle finger) / 65 (sides), starting along +z; sides fanned +/-8 degrees.
5. Thumb "Glove_{side}_Thumb": sweep_tube radius 0.031, n_around 12, extend_start 0.025. Base at local (thumb_sign*0.070, 0.012, 0.070). Direction: outward thumb_sign*x tilted 50 deg up toward +z (OPEN) or 65 deg up toward +z and 25 deg toward +y (RELAXED); length 0.075; slight curve toward +z at the tip (3-4 points).
6. `build_gloves(mats)` builds both hands and returns the list of all objects.
