"""Post-process the final renders and package the deliverables (system Python + Pillow + ffmpeg)."""
import glob
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda *p: os.path.join(ROOT, *p)
STUDIO, NAVY = (230, 226, 223), (16, 22, 41)


def over(path, col):
    im = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", im.size, col + (255,))
    base.alpha_composite(im)
    return base.convert("RGB")


os.makedirs(R("exports", "hero_4k"), exist_ok=True)
os.makedirs(R("renders", "stickers", "notext"), exist_ok=True)
for path in sorted(glob.glob(R("exports", "hero", "hero_*.png"))):
    name = os.path.basename(path)
    full = over(path, STUDIO)
    full.save(R("exports", "hero_4k", name))
    full.resize((1500, 1500), Image.LANCZOS).save(R("renders", name))
    if name == "hero_front.png":
        navy = over(path, NAVY)
        navy.save(R("exports", "hero_4k", "hero_front_navy.png"))
        navy.resize((1500, 1500), Image.LANCZOS).save(R("renders", "hero_front_navy.png"))
    print("hero", name)

py = sys.executable
exprs = sorted(glob.glob(R("renders", "expressions", "expr_*.png")))
items = [os.path.basename(p)[5:-4].replace("_", " ") + "::" + p for p in exprs]
subprocess.run([py, R("scripts", "sheet.py"), R("renders", "expressions_sheet.png"), "5", "480", "E6E2DF"] + items, check=True)
for sub in ("", "notext"):
    for p in glob.glob(R("exports", "stickers", sub, "*.png")) + glob.glob(R("exports", "stickers", sub, "*.webp")):
        shutil.copy2(p, R("renders", "stickers", sub, os.path.basename(p)))
stk = sorted(glob.glob(R("exports", "stickers", "*.png")))
subprocess.run([py, R("scripts", "sheet.py"), R("renders", "stickers_sheet.png"), "5", "420", "C9CDD6"]
               + [os.path.basename(p)[:-4].replace("_", " ") + "::" + p for p in stk], check=True)
subprocess.run([py, R("scripts", "model_sheet.py")], check=True)

frames = R("tmp", "turn", "f_%04d.png")
mp4 = R("exports", "turntable_v2.mp4")
if os.path.exists(R("tmp", "turn", "f_0000.png")):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xE6E2DF:s=1080x1080:r=30",
                    "-framerate", "30", "-i", frames, "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-movflags", "+faststart", mp4], check=True)
    os.makedirs(R("media"), exist_ok=True)
    shutil.copy2(mp4, R("media", "turntable_v2.mp4"))
    print("turntable", os.path.getsize(mp4))
os.makedirs(R("models"), exist_ok=True)
shutil.copy2(R("exports", "synergist-mascot-v2.glb"), R("models", "synergist-mascot-v2.glb"))


def zipdir(zf, folder, arc, exts=None):
    for base, _, files in os.walk(folder):
        for f in sorted(files):
            if exts and not f.lower().endswith(exts):
                continue
            full = os.path.join(base, f)
            zf.write(full, os.path.join(arc, os.path.relpath(full, folder)))


main = R("exports", "Synergist_Mascot_v2.zip")
with zipfile.ZipFile(main, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(R("exports", "synergist-mascot-v2.glb"), "3d-model/synergist-mascot-v2.glb")
    if os.path.exists(mp4):
        zf.write(mp4, "video/turntable_v2.mp4")
    for p in sorted(glob.glob(R("renders", "hero_*.png"))) + [R("renders", "model_sheet_v2.png"),
                                                              R("renders", "expressions_sheet.png"), R("renders", "stickers_sheet.png")]:
        zf.write(p, "renders/" + os.path.basename(p))
    zipdir(zf, R("renders", "expressions"), "expressions")
    zipdir(zf, R("renders", "stickers"), "stickers")
    zf.write(R("README.md"), "README.md")
big = R("exports", "Synergist_Mascot_v2_4K_and_Blend.zip")
with zipfile.ZipFile(big, "w", zipfile.ZIP_DEFLATED) as zf:
    zipdir(zf, R("exports", "hero_4k"), "hero_4k")
    if os.path.exists(R("blend", "mascot_v2.blend")):
        zf.write(R("blend", "mascot_v2.blend"), "blender/mascot_v2.blend")
print("zips", os.path.getsize(main), os.path.getsize(big))
