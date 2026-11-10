Write a NEW complete Blender 5.2 Python script `06_stickers.py` (one ```python fence). Run:
  blender.exe -b blend/mascot_rig.blend --python scripts/06_stickers.py -- <project_root> [--only 1,5,9] [--res 1024] [--samples 64]
It renders each sticker's CHARACTER LAYER (character + props, transparent background) to exports/stickers/raw/<NN>_<slug>.png (NN = 01..20). Captions and the white outline are added later by a separate Pillow script, NOT here.

Reuse existing code by importing sibling modules (their main() is guarded):
  rig05 = importlib (05_rig.py): rig05.reset_pose(), rig05.apply_hand_pose(side, name) (names: open_wave, ok_sign, thumbs_up, point, fist, hold), rig05.pose_hand(rig, side, pos, fingers_dir, palm_dir, hand_scale=1.0) (IK-places a hand at world pos; fingers_dir = where fingers point; palm_dir = where the palm faces), rig05.set_bone_world_location(rig, bone, pos), rig05.SHOULDER_Z, rig05.HIP_Z, rig05.BODY_TOP.
  face04 = importlib (04_face.py): face04.PRESETS (dict name -> controls), face04.CONTROLS. To apply a face: set every Face_Ctrl property in face04.CONTROLS to its default, then the preset's values, plus optional extra overrides (dict).
  lookdev = importlib (03_materials.py): lookdev.create_fleece(name, hex, sheen=..., pile_scale=..., velvet_strength=..., sheen_tint_mix=...), lookdev.create_satin(name, hex, angle_deg, aniso=...), lookdev.hex_lin(hex).
Rig object "Mascot_Rig" (props: lean_fwd, lean_side, twist, lid_tilt_x, lid_tilt_y, squash, foot_roll.L/R, ik_fk.L/R ...); pose bones include root, IK_foot.L/R. Hand prop sockets: empties "Socket_Hand.L", "Socket_Hand.R" bone-parented to the hands (they follow the hand); "Face_Ctrl" holds face controls. Character faces -Y, "R" = character's right = -X (the waving arm), "L" = +X. World facts: ground z=0, body x in [-0.5, 0.5], front surface y ~ -0.52, BODY_TOP ~1.674, SHOULDER_Z ~1.04, HIP_Z ~0.67, mouth ~z 1.0, logo ~z 0.75.

1. PROPS (simple stylised plush/felt toys, all made with bmesh/primitives, smooth shaded, Subdivision level 1/render 2 where it helps; every prop object name starts with "StkProp_"; build all props once, hidden (hide_render/hide_viewport True), and show only the ones a sticker needs). Felt material helper `felt(name, hex)` = lookdev.create_fleece(name, hex, sheen=0.5, pile_scale=150, velvet_strength=0.4, sheen_tint_mix=0.2).
   - "StkProp_Clipboard": board 0.30 x 0.40 x 0.02 (brown #8A5A2B felt) with rounded corners (bevel modifier), white paper 0.26 x 0.32 slightly in front (#F4F2EE), silver clip at the top (#B8BEC6 metallic 0.6 rough 0.35), 3 navy text lines (thin boxes #101629) on the paper. Local origin at the board's centre; board plane = local XZ (facing -Y).
   - "StkProp_ClipboardCheck": same but a big green check mark (#2DBE60) on the paper instead of lines (two thick boxes forming a tick).
   - "StkProp_Pen": cylinder r 0.012 length 0.18 (#1F3FB8) with a gold cap (#D5B268) and a cone tip.
   - "StkProp_Parcel": box 0.30 x 0.24 x 0.22 cardboard #C89B63 felt with a tape strip #E8D5A8 over the top and a small label (#F4F2EE).
   - "StkProp_Mug": cylinder r 0.06 h 0.12 white #F4F2EE with a handle (torus segment), coffee disc #4A2C1A at the top, three wavy steam strands above (thin curved tubes, white, alpha not needed).
   - "StkProp_Sun": yellow sphere r 0.13 #FFC93C with 10 cone rays (#FFB020) around it in the XZ plane, a tiny smile (black thin arc) — placed in the scene, not in a hand.
   - "StkProp_Magnifier": ring (torus major 0.09 minor 0.016, gold #D5B268), glass disc (light blue #CFEFFF, transmission 0.6 roughness 0.05), handle cylinder r 0.018 l 0.16 navy #101629 pointing down from the ring.
   - "StkProp_Question": a big "?" made from a 3D text object (bpy.data.curves.new(type='FONT'), body "?", size 0.45, extrude 0.03, bevel_depth 0.01, align center) in gold #D5B268, converted to mesh (new_from_object), placed in the scene.
   - "StkProp_Desk": desk top 1.2 x 0.55 x 0.06 (#C89B63 wood felt) at height 0.72 with four legs (r 0.03), front of the character; "StkProp_Laptop": base 0.36 x 0.25 x 0.02 dark grey #3A3F4A + screen 0.36 x 0.24 tilted 105 deg, screen face light blue #9FD3FF, a small gold Synergist circle (disc) on the lid back.
   - "StkProp_Envelope": red envelope 0.26 x 0.16 x 0.02 #D8262E with a gold #D5B268 flap triangle and a small gold circle seal.
   - "StkProp_Confetti": ~60 small flat pieces (0.03 x 0.012 x 0.002 boxes and small discs) in gold #D5B268, light gold #EED295, red #E2324F, blue #1F3FB8, white, randomly rotated, scattered around the upper body/head (x -0.9..0.9, y -0.9..-0.3, z 1.1..2.2), seeded random (random.seed(7)). One object (joined mesh) with several material slots.
   - "StkProp_Stars": 5 small gold stars (5-point, extruded 0.015, r 0.06-0.1) around the head, one object.
   Attach a prop to a hand by: obj.parent = bpy.data.objects["Socket_Hand.S"], obj.matrix_parent_inverse = identity, then obj.location/rotation_euler in the socket's local space (= the hand's space). Because hand space depends on the bone roll, instead place hand-held props in WORLD space after posing: compute the socket's world matrix (bpy.context.view_layer.update(); sock.matrix_world) and set prop.matrix_world = Matrix.Translation(sock world location + offset) @ world rotation you choose (e.g. facing the camera); this is simpler and good enough for stills.
2. STICKERS: a list of dicts (keep this exact list, numbers/slugs/captions):
   1 noted (caption "NOTED WITH THANKS"), 2 received ("RECEIVED!"), 3 thank_you ("អរគុណ|THANK YOU"), 4 hello ("HELLO!"), 5 okay ("OKAY!"), 6 good_morning ("GOOD MORNING"), 7 info_inquiry ("INFORMATION INQUIRY"), 8 in_meeting ("IN MEETING"), 9 yes ("ចាស!"), 10 paid ("PAID!"), 11 please_wait ("PLEASE WAIT!"), 12 good_afternoon ("GOOD AFTERNOON"), 13 sorry ("សុំទោស|SORRY"), 14 on_the_way ("កំពុងដឹកជញ្ជូន|ON THE WAY"), 15 order_confirmed ("បានបញ្ជាក់ការកុម្ម៉ង់|ORDER CONFIRMED"), 16 out_of_stock ("អស់ស្តុក|OUT OF STOCK"), 17 great_job ("ល្អណាស់|GREAT JOB!"), 18 see_you_tomorrow ("ជួបគ្នាថ្ងៃស្អែក|SEE YOU TOMORROW"), 19 congratulations ("សូមអបអរសាទរ|CONGRATULATIONS"), 20 happy_new_year ("សួស្តីឆ្នាំថ្មី|HAPPY NEW YEAR").
   Write the captions to exports/stickers/captions.json ({"NN_slug": "caption"}) for the Pillow step.
   Each sticker has: face preset name (+ optional overrides), props to show, and a pose function. Every pose starts with rig05.reset_pose() and hides all props. Hand placements use rig05.pose_hand with these tested conventions (SZ = SHOULDER_Z, HZ = HIP_Z, mirror X for the other side):
     - WAVE R: leave the R arm in FK (modelled raised wave) + apply_hand_pose("R","open_wave").
     - THUMBS-UP R: pose_hand(rig,"R",(-0.9,-0.28,SZ+0.12),(-0.72,0,0.70),(0,-1,0),1.35) + hand pose thumbs_up; THUMBS-UP L: pose_hand(rig,"L",(0.9,-0.28,SZ+0.12),(0.72,0,0.70),(0,-1,0),1.35).
     - OK R: pose_hand(rig,"R",(-0.88,-0.28,SZ+0.22),(0,0,1),(0,-1,0),1.35) + ok_sign.
     - PALM OUT (please wait) R: pose_hand(rig,"R",(-0.62,-0.62,SZ+0.12),(0,0,1),(0,-1,0),1.4) + open_wave.
     - REST L visible: pose_hand(rig,"L",(0.72,-0.2,HZ+0.06),(0,0,-1),(-1,0,0)) + hold pose relaxed.
     - HANDS TOGETHER (thank you / sorry): R (-0.07,-0.66,HZ+0.2) fingers (0,-0.15,1) palm (1,0,0); L (0.07,-0.66,HZ+0.2) fingers (0,-0.15,1) palm (-1,0,0); open_wave with spread 0 on both; rig["lean_fwd"]=0.35 (small bow).
     - HOLD IN FRONT (one hand): R (-0.32,-0.72,SZ-0.05) fingers (0.3,0,1) palm (1,0,0), pose "hold"; prop at the socket + offset, facing the camera.
     - TWO-HAND HOLD (envelope, parcel while running): R (-0.2,-0.72,HZ+0.25) fingers (0,-0.2,1) palm (1,0,0); L mirror; "hold"; prop centred between the sockets.
     - ARMS UP: R (-0.88,-0.15,BODY_TOP+0.22) fingers (-0.3,0,1) palm (0,-1,0) open_wave; L mirror.
     - SHRUG (out of stock): R (-0.82,-0.42,HZ+0.18) fingers (-1,-0.3,0.2) palm (0,0,1) open_wave spread 0.5; L mirror; rig["lid_tilt_y"] = 0.3.
     - TYPING at desk: R (-0.18,-0.86,0.80) fingers (0.1,-1,0) palm (0,0,-1); L mirror; "hold".
     - RUNNING: rig["lean_fwd"]=0.3; set_bone_world_location(rig,"IK_foot.R",(-0.2,-0.3,0.14)); set_bone_world_location(rig,"IK_foot.L",(0.2,0.25,0.0)); rig["foot_roll.L"]=0.4.
   Sticker recipes (face preset from face04.PRESETS; R/L poses from above; props):
     1 noted: Grateful; L holds Clipboard in front (hold-in-front mirrored to L), R holds Pen near the clipboard (pose_hand R (-0.05,-0.75,SZ-0.08) fingers (0.6,0,0.8) palm (0.4,-0.6,0)), pen at the R socket.
     2 received: Happy; L holds Parcel in front (two-hand-hold position but only L hand, parcel at L socket + (0,-0.1,0)); R THUMBS-UP.
     3 thank_you: Grateful; HANDS TOGETHER; no props.
     4 hello: Happy + override eye_wide 0.2; WAVE R; REST L.
     5 okay: Wink; OK R; REST L.
     6 good_morning: Sleepy + overrides m_small_smile 0.8, m_pout 0; R HOLD IN FRONT with Mug; Sun at (-0.75, 0.1, BODY_TOP+0.35); REST L.
     7 info_inquiry: Thinking; R holds Magnifier raised: pose_hand R (-0.7,-0.45,SZ+0.3) fingers (0,0,1) palm (1,0,0) "hold", magnifier ring centred 0.12 above the socket facing the camera; Question at (0.62, -0.2, BODY_TOP+0.25); REST L.
     8 in_meeting: Determined; Desk at (0,-0.85,0) + Laptop on the desk at (0,-0.95,0.75) screen facing the character; TYPING.
     9 yes: Proud; THUMBS-UP R; REST L.
     10 paid: Excited; R ARMS UP holding ClipboardCheck above the head (prop at R socket + (0,0,0.18), facing camera); L ARMS UP; Confetti.
     11 please_wait: Calm; PALM OUT R; REST L.
     12 good_afternoon: Happy; WAVE R; Sun at (0.8, 0.1, BODY_TOP+0.3); REST L.
     13 sorry: Embarrassed + override lid... use rig["lid_tilt_y"] = 0.4 and rig["lean_side"] = -0.2; HANDS TOGETHER.
     14 on_the_way: Determined; TWO-HAND HOLD with Parcel; RUNNING.
     15 order_confirmed: Proud; L holds ClipboardCheck in front (mirrored hold-in-front); R point at it: apply_hand_pose("R","point"), pose_hand R (-0.12,-0.75,SZ+0.0) fingers (1,-0.2,0.2) palm (0,-1,0).
     16 out_of_stock: Worried; SHRUG.
     17 great_job: Big laugh; THUMBS-UP R and THUMBS-UP L.
     18 see_you_tomorrow: Calm; WAVE R; REST L.
     19 congratulations: Excited; ARMS UP both; Confetti + Stars; rig root lifted 0.1: set_bone_world_location(rig,"root",(0,0,0.1)).
     20 happy_new_year: Love; TWO-HAND HOLD with Envelope; Confetti.
3. RENDER each sticker: scene.render.film_transparent = True; hide "Backdrop" and "Ground" from render; Cycles samples args.samples, resolution args.res x args.res, PNG RGBA. Camera "Camera": clear its constraints; direction: from the target toward (-0.17, -1.0, 0.05) normalised (near-front, ~10 deg toward the waving side); lens 50. Auto-frame: after posing, compute the world bounding box of all visible (not hide_render) mesh objects whose parent chain includes "Mascot_Root" plus visible StkProp_* objects (use the evaluated bound_box corners of each object: [obj.matrix_world @ Vector(c) for c in obj.bound_box]); target = bbox centre; distance so that the bbox (its max of width/height projected) fits within 88% of the frame: dist = (0.5 * max_extent / 0.88) / tan(fov/2) + 0.5*depth, fov from the camera's angle; set the camera location = target + dir * dist and rotation via a Track To-free method: rot = (target - cam).to_track_quat('-Z', 'Y').
   Print f"[06] {NN}_{slug} {seconds:.1f}s". Save blend/mascot_stickers.blend at the end (last pose is fine).
