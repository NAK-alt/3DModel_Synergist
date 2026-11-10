Write ONE complete Blender Python script (bpy) for Blender 5.2 LTS, run headless as:
  blender.exe -b --factory-startup --python 01_blockout.py -- <project_root>
<project_root> is the folder containing blend\ and renders\ (take it from sys.argv after "--"; default to the parent of the script's folder).

Goal: a ROUGH PROPORTION BLOCKOUT of a cartoon mascot: a blue oil-drum (barrel) character with rubber-hose limbs. No fine detail.

Scene setup
- Start by deleting all objects; units metric; Z is up; character stands on the ground at Z=0 facing -Y (front camera looks toward +Y).
- Put each part in its own named object; parent all parts to an Empty named "Mascot_Root".

Body (barrel)
- Cylinder, diameter 1.0, height 1.3, 48 verts, smooth shaded, with a Bevel modifier (width 0.03, 3 segments) for soft edges. Body bottom sits at the top of the legs (see legs) so total model stands on the ground.
- Lid rim: a torus on the top edge (major radius ~0.49, minor ~0.035) slightly raised, plus a slightly domed lid disc (flattened UV sphere, scale z ~0.08) inside it.
- 4 rolled hoops (torus, major radius 0.505, minor 0.025) at 30%, 45%, 75% and 95% of body height MEASURED FROM THE TOP of the body. Name them Hoop_30, Hoop_45, Hoop_75, Hoop_95.
- Face zone (between Hoop_30 and Hoop_45): two eyes on the front surface: white flattened spheres (sclera ~0.12 wide x 0.16 tall) with black pupils in front, spaced ~0.24 apart. Mouth: a simple dark flattened half-torus or flattened ellipsoid smile just below the eyes, still above Hoop_45 if it fits, else just under it.
- Logo zone (between Hoop_45 and Hoop_75): a gold placeholder plate, a thin curved panel that hugs the front of the cylinder (e.g. a cylinder segment / a thin scaled cylinder section, ~0.45 wide x ~0.25 tall), named "Logo_Placeholder".

Arms (thin noodle "rubber hose" arms, radius ~0.035), built as Bezier CURVE objects with bevel_depth so they are round tubes:
- Shoulders on the left and right sides of the barrel at about 40% from the top.
- Character's LEFT arm (on screen right in the front view, i.e. +X side) RAISED and waving: curve goes out and up so the hand is above and outside the barrel top.
- Character's RIGHT arm (-X side) hangs DOWN with the hand near the hip (about 80% from the top), slightly out from the body.
- Gloves: white cartoon glove blobs: a palm (flattened sphere ~0.14) + a cuff (short torus/cylinder ring, white) at the wrist, at each arm end. 4 stubby fingers are optional at this stage (simple small capsules ok).

Legs and shoes
- Two short legs, length about 15% of body height (~0.195), same noodle radius ~0.04, straight down from the body bottom, spaced ~0.25 apart.
- Shoes: big round white shoes, each ~0.35 wide (35% of body width), ~0.45 long front-to-back, ~0.2 tall, toe pushed forward (-Y) a bit; flattened spheres are fine. Shoe bottoms touch Z=0.

Materials (Principled BSDF, viewport display colour too), hex in sRGB -> convert to linear for base_color:
- Body + lid: #1F3FB8, roughness 0.8 (plush)
- Hoops and lid rim: same blue, slightly darker (multiply 0.85)
- Arms + legs: #101629
- Gloves, cuffs, shoes, eye whites: white #F2F2F2
- Pupils and mouth: near black #0A0A0A
- Logo placeholder: gold #D5B268, metallic 0.6, roughness 0.35

Render (EEVEE)
- Engine: use 'BLENDER_EEVEE' (Blender 5.x name); wrap in try/except and fall back to 'BLENDER_EEVEE_NEXT' then 'CYCLES'.
- Resolution 1024x1024, 100%, PNG. Film transparent = False; world background light grey (~0.8) with strength 1.
- Lighting: a 3-point setup (area lights: key front-left above, fill front-right, rim behind). Add a large ground plane (light grey) at Z=0.
- Camera: 50mm lens, aimed at the centre of the full character (track-to constraint on an Empty at the character's mid height). Distance so the whole character including the raised hand fits with margin.
- Render 4 views by moving the camera around the Z axis: front (camera at -Y), threequarter (45 degrees between front and the character's left/+X side), side (+X side), back (+Y). Save to <project_root>\renders\blockout_front.png, blockout_threequarter.png, blockout_side.png, blockout_back.png.
- Save the .blend to <project_root>\blend\mascot_blockout.blend (bpy.ops.wm.save_as_mainfile, use os.path paths).

Code style: plain functions (make_material, add_torus, add_noodle(points, radius, mat), etc.), constants at the top (BODY_D, BODY_H, LEG_H, ...), no external dependencies. Avoid bpy.ops where a data API exists, but bpy.ops.mesh.primitive_* is fine. Do not use any API removed in Blender 4.x/5.x (e.g. no bpy.context.scene.eevee.use_ssr, no 'use_auto_smooth'; use obj.data.shade_smooth() or bpy.ops.object.shade_smooth()). Return only the script in one ```python block.
