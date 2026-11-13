# Synergist Lubricants mascot, v3 (matched to the plush)

v3 takes the v2 model and matches it to the plush photo as closely as possible. v1, v2 and the first 2D set are untouched in their own folders.

## How it was matched

The camera of the plush photo was solved from the picture (about 17 degrees above, long lens), the model was rendered through that same camera, and each part was adjusted until the two images lined up: barrel height, hoops and ribs, face position and size, eye shape, pupils, nose, mouth, logo size and place, arm length and thickness, hands, leg length, and shoes. `renders/match_side.png` shows the photo next to the result.

Changes from v2: taller barrel on longer legs, face higher up, logo in the middle band, shorter and thicker arms, bigger shoes, plain white eyes with large pupils (no black ring), grey mouth with a white tongue, deeper royal blue, off-centre nose.

## What is here

- `models/synergist-mascot-v3.glb`: rigged model, 50 bones, 45 face shapes, about 3 MB.
- `media/turntable_v3.mp4`: 360 degree spin.
- `renders/`: hero renders (including `hero_plush_angle.png`, the same angle as the photo), model sheet, 20 expressions, stickers.
- `renders/stickers/`: 20 Telegram stickers, PNG and WEBP, with and without text.
- `2d/`: the cartoon version redrawn from this model (hero art, 20 expressions, 20 stickers).
- `scripts/`: the code. `t_match.py` and `compare.py` do the photo comparison; the rest works as in v2.

The 4K renders and `mascot_v3.blend` are in `exports/` and `blend/` on KTPC, outside git.

## Not exact

It is a rebuilt model, not a scan. The fleece is a shader, so it has less of the plush's fine crushed texture, and seams and stitching are simplified.
