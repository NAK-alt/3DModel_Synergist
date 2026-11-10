You are given 01_blockout.py (Blender 5.2, works headless). Return the COMPLETE updated script in one ```python block. Keep every helper, the lathe body, hoops, lid, camera/lights/world/render/save code, file names and arguments unchanged unless listed here. Still a blockout (simple primitives). Character faces -Y; viewer's left = -X = the character's RIGHT side.

1. ARMS mirrored and re-attached.
   - Shoulders on both body sides at 50% of body height from the top, pushed slightly forward: shoulder point (+/-(BODY_R - 0.02), -0.08, shoulder_z).
   - WAVING arm is now on -X (viewer's left, character's right): mirror the old raised-arm points in X and use the new shoulder (keep the hand above/outside the lid, about x=-0.80, z=body_top_z+0.12, y=-0.10). Name it "Arm_Right".
   - RESTING arm is now on +X (viewer's right, character's left): mirror the old hanging arm, hand near the hip (80% from top). Name it "Arm_Left".
   - Waving hand = OPEN PALM facing the camera with fingers spread: new helper add_open_hand(side, arm_points, mat): white cuff torus at the wrist (oriented along the arm direction as before), palm = ellipsoid full size (0.17 wide, 0.06 deep, 0.16 tall) facing -Y (no yaw to the arm, flat side toward camera) centred 0.10 beyond the wrist along the arm direction; 4 fingers = capsule-like ellipsoids (0.045 x 0.04 x 0.10 full size) fanned upward from the palm's top edge at angles -30, -10, 10, 30 degrees from vertical (rotate about Y), plus a thumb (0.045 x 0.04 x 0.08) pointing out sideways at 70 degrees toward the outside. The resting hand keeps the existing add_glove.

2. EYES much bigger (all sizes full size):
   - EYE_W = 0.20 wide, EYE_H = 0.30 tall, depth 0.06. Eye centre x = FACE_X +/- 0.14 where FACE_X = +0.03 (whole face shifted slightly to viewer's right).
   - Eye top sits 0.025 above Hoop_29 (so the eye overlaps that hoop slightly): eye_z = hoop29_z + 0.025 - EYE_H/2.
   - Place eyes far enough forward to cover the hoop: y = front_y(x, 0.02). Keep yaw following the barrel curve.
   - Black outline ellipsoid 0.02 larger in width and height, 0.008 behind.
   - Pupils: 0.11 wide x 0.15 tall x 0.04 deep, shifted +0.03 in x and -0.02 in z, in front of the sclera (y offset +0.035 relative to the sclera centre, i.e. front_y(px, 0.055)).
3. BROWS: thin arcs (torus minor radius 0.007, major 0.07), top half only, fully above Hoop_29: arc base at hoop29_z + 0.05 so the lowest point clears the hoop (hoop minor radius is 0.025) — but they must sit above the eye top too, so base at max(hoop29_z + 0.05, eye_top + 0.02). Centred over each eye x.
4. NOSE: black sphere, diameter 0.08, centred at x = FACE_X, z = hoop44_z, y in front of the hoop: -(HOOP_MAJOR_R + HOOP_MINOR_R) - 0.03.
5. MOUTH: D-shaped open smile, width 0.22, height 0.11, flat top at hoop44_z - 0.05, centred at x = FACE_X (add_half_disc already exists; add an optional x location). Inside colour dark red-brown #4A1410 (rename M_MouthIn colour). Teeth: white slab 0.16 x 0.02 deep x 0.03 tall under the flat top. Tongue hint: small ellipsoid #C0504D (material M_Tongue), 0.10 wide x 0.02 deep x 0.04 tall, at the bottom inside of the mouth (z = mouth_top_z - 0.085), slightly in front of the mouth slab.
6. LOGO between Hoop_44 and Hoop_76, centred slightly right (LOGO_X = +0.04), and below the mouth: logo_center_z = middle of the space between (mouth_top_z - 0.11 - 0.02) and hoop76_z + 0.03.
   - Badge on the left (x = LOGO_X - 0.25): WHITE ring = torus major 0.11, minor 0.018, rotated to face front (90 deg about X + yaw for the curve), mat_white; inside it three gold spheres (radius 0.035) in a triangle (one top centre, two bottom), mat_gold, on the surface.
   - Wordmark: the two stacked curved bars, left edge at about x = LOGO_X - 0.10, width 0.46, heights 0.07, gap 0.03.
   - Remove the old solid Logo_Badge disc. Keep M_GoldLight (use it for the top bar).
7. BODY colour COL_BODY = "#1A3AAE", roughness 0.85, and lower its specular: set the Principled input "Specular IOR Level" to 0.2 if that input exists (guard with `if "Specular IOR Level" in bsdf.inputs`). Hoops keep the 0.85 darker version of the new colour.
