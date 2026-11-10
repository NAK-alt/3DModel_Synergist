You are given 01_blockout.py (Blender 5.2, runs headless and works). Return the COMPLETE updated script in one ```python block. Keep all existing helpers, the camera/lights/render/save code, file names, the --factory-startup/"--" argument handling and the Standard view transform unchanged unless listed below. Still a BLOCKOUT: simple primitives only.

Changes (measured from the real plush photo):

1. Body: BODY_H = 1.26 (diameter stays 1.0). Hoops at 29%, 44%, 76%, 97% from the top: HOOP_PERCENTS = [0.29, 0.44, 0.76, 0.97]; keep names Hoop_29, Hoop_44, Hoop_76, Hoop_97 (use round(pct*100)).

2. Stuffed-fabric bulge: replace the plain cylinder body with a lathe (revolve) mesh built with bmesh: 64 radial segments; profile from bottom to top, sampled every ~0.01 in Z. Radius r(z) = BODY_R at each hoop height and at the top/bottom edges, and between two consecutive boundaries bulges out as BODY_R + BULGE * sin(pi * t) where t goes 0..1 across that segment and BULGE = 0.015. Cap top and bottom with fans (or n-gons). Smooth shaded, keep the Bevel modifier off (not needed now). Name "Body". Make sure normals point outward (bmesh.ops.recalc_face_normals).

3. Lid: lid rim becomes a thick rolled torus: major radius 0.47, minor radius 0.055, centred at body_top_z + 0.02. Lid top: a slightly domed flat disc: UV sphere radius 0.5 scaled to (0.45, 0.45, 0.04)*2 full size i.e. use add_ellipsoid("Lid_Disc", (0.90, 0.90, 0.08), (0,0,body_top_z+0.03), mat_body).

4. Face (eyes fill the band between Hoop_29 and Hoop_44; band height = 0.15*BODY_H):
   - Eyes: big ovals. White sclera full size (0.15 wide, band height minus 0.01 tall, 0.04 deep), eye centres at x = +/-0.095, z = band centre. Black outline: a black ellipsoid 0.018 larger in width and height, placed 0.006 behind the white one (so it shows as a rim).
   - Pupils: large black ellipsoids 0.085 wide x 0.11 tall, shifted +0.022 in X (looking slightly to the viewer's right = +X) and 0.01 down, sitting in front of the sclera.
   - Brows: small arched brows just ABOVE Hoop_29: for each eye a half torus (major 0.05, minor 0.009, keep only the upper half like the existing Mouth bmesh trick but keep the TOP half), black, centred over each eye at z = hoop29_z + 0.035, rotated 90 deg about X so it faces front, on the barrel surface (use front_y).
   - Nose: small round black sphere, diameter 0.05, centred at x=0 sitting on Hoop_44 (z = hoop44_z, y just in front of the hoop's front surface: -(HOOP_MAJOR_R + HOOP_MINOR_R) - 0.005).
   - Mouth: open smile just under the nose: a dark (#2A0A0A, name M_MouthIn) half-disc 0.17 wide x 0.09 tall (flattened half ellipsoid or a half-cylinder slab, flat side up) with its flat top at hoop44_z - 0.035, on the barrel front. White upper teeth: a thin white slab 0.12 wide x 0.025 tall x 0.02 deep just under the flat top edge, slightly in front of the mouth. Remove the old torus Mouth.

5. Logo zone (centred between Hoop_44 and Hoop_76, total width ~80% of body diameter = 0.80 along the curved surface): keep add_front_panel but now build THREE gold pieces on the barrel surface (radius BODY_R + 0.004, follow the curve):
   - "Logo_Badge": a disc (circle badge) on the left (viewer's left = -X), diameter 0.26, as a short cylinder (depth 0.02) rotated to face front at angle position x=-0.25 (yaw to follow the curve like the eyes).
   - "Logo_Word1" and "Logo_Word2": two curved bars on the right made with add_front_panel: widths 0.48 and 0.48, heights 0.075 each, gap 0.03 between them, the pair vertically centred in the band, horizontally covering x from about -0.08 to +0.40 (add_front_panel currently centres on x=0; add a parameter x_center (as arc offset angle) so the panel can be shifted).
   Use gold #D5B268 for all three, and add a light gold #EED295 material "M_GoldLight" used for the badge.

6. Legs and shoes: LEG_LEN = 0.17 * BODY_H; SHOE_WIDTH = 0.34 (full width), keep SHOE_LENGTH 0.45, SHOE_HEIGHT 0.2, leg_x 0.19.

7. Arms: keep the same pose and helper but recompute from the new body_top_z (shoulder at 40% from top, hand of the right arm near 80%).

8. Hoop material: keep darker blue. Materials: add COL_GOLD_LIGHT = "#EED295" constant.

Do not change anything else. No new dependencies.
