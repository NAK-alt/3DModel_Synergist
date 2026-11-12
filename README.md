# Synergist Lubricants mascot (3D)

Plush oil-drum mascot built procedurally in Blender 5.2 (headless Python scripts).

**Download everything:** see the [v1.0 release](https://github.com/NAK-alt/3DModel_Synergist/releases/tag/v1.0)
- `Synergist_Mascot_Deliverables.zip`: GLB (web/AR/phone) + baked textures, turntable video, model sheet, expressions, 20 Telegram stickers (PNG + WEBP, with and without text)
- `Synergist_Mascot_Deliverables_4K_and_Blend.zip`: 4K hero renders (3840 px) + master `.blend` (rigged, face controls, look-dev)

In this repo:
- `models/synergist-mascot.glb`: rigged low-poly model (~59k tris, 2048 baked textures, 36 face morph targets: blinks, smiles, open mouth, O, frown, brows, visemes, pupils)
- `media/turntable.mp4`: 360° turntable, 6 s, 1080 px
- `renders/`: hero renders (1500 px), model sheet, expressions sheet, stickers, pose tests

Pipeline (`scripts/`): `01_blockout` → `02_model` → `03_materials` → `04_face` (face rig + expressions) → `05_rig` (body rig) → `06_stickers` (+ `sticker_text`, `sticker_compose`) → `07_export` (GLB) → `08_finals` (heroes, turntable, ortho) → `package`.
Logo/reference images and fonts (`refs/`), working `.blend` files and `exports/` are kept out of git.
