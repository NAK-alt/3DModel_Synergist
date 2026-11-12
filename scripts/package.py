"""Build the deliverables zip(s) for Nak: python scripts/package.py

exports/Synergist_Mascot_Deliverables.zip with GLB (+ baked textures), master blend (textures
packed), 4K heroes, turntable, model sheet, expressions sheet + per-expression PNGs, stickers.
If it is over 95 MB, the .blend goes into its own zip (..._Blend.zip). Never includes refs/.
"""
import os
import shutil
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "exports")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
LIMIT = 95 * 1024 * 1024


def j(*p):
    return os.path.join(ROOT, *p)


def packed_blend():
    """Copy of mascot_rig.blend with all external images packed (no refs/ files are referenced)."""
    out = j("exports", "Synergist_Mascot_master.blend")
    expr = ("import bpy; bpy.ops.file.pack_all(); "
            f"bpy.ops.wm.save_as_mainfile(filepath=r'{out}', copy=True, compress=True)")
    subprocess.run([BLENDER, "-b", j("blend", "mascot_rig.blend"), "--python-expr", expr],
                   check=True, capture_output=True)
    return out


def entries():
    files = [(j("exports", "synergist-mascot.glb"), "GLB/synergist-mascot.glb")]
    for f in sorted(os.listdir(j("exports", "glb_textures"))):
        files.append((j("exports", "glb_textures", f), f"GLB/textures/{f}"))
    for f in sorted(os.listdir(j("exports", "hero"))):
        files.append((j("exports", "hero", f), f"Renders_4K/{f}"))
    files.append((j("exports", "turntable.mp4"), "Turntable/turntable.mp4"))
    files.append((j("renders", "model_sheet_final.png"), "Model_Sheet/model_sheet_final.png"))
    files.append((j("renders", "expressions_sheet.png"), "Expressions/expressions_sheet.png"))
    for f in sorted(os.listdir(j("renders"))):
        if f.startswith("expr_") and f.endswith(".png"):
            files.append((j("renders", f), f"Expressions/{f}"))
    for sub, label in (("", "with_text"), ("notext", "no_text")):
        d = j("exports", "stickers", sub)
        for f in sorted(os.listdir(d)):
            if f.endswith((".png", ".webp")) and os.path.isfile(os.path.join(d, f)):
                files.append((os.path.join(d, f), f"Stickers/{label}/{f}"))
    return files


def write_zip(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, arc in files:
            z.write(src, arc)
    return os.path.getsize(path)


def main():
    blend = packed_blend()
    files = entries()
    for src, _ in files:
        assert "refs" not in os.path.relpath(src, ROOT).split(os.sep)[0], src
    main_zip = j("exports", "Synergist_Mascot_Deliverables.zip")
    size = write_zip(main_zip, files + [(blend, "Blender/Synergist_Mascot_master.blend")])
    out = [main_zip]
    if size > LIMIT:
        # split: part 1 = GLB, turntable, sheets, expressions, stickers; part 2 = 4K renders + .blend
        big = [(s, a) for s, a in files if a.startswith("Renders_4K/")]
        rest = [(s, a) for s, a in files if not a.startswith("Renders_4K/")]
        write_zip(main_zip, rest)
        out.append(j("exports", "Synergist_Mascot_Deliverables_4K_and_Blend.zip"))
        write_zip(out[-1], big + [(blend, "Blender/Synergist_Mascot_master.blend")])
    for p in out:
        print(p, f"{os.path.getsize(p) / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
