"""Light build -> exports/synergist-mascot-v3.glb (rig, face morph targets, tiling fabric normals).
Run with MASCOT_Q=glb."""
import math
import os
import sys

os.environ.setdefault("MASCOT_Q", "glb")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

import m_build
import m_pose
from m_util import ROOT, hex_rgb

TEX = os.path.join(ROOT, "textures")


def save_normal(name, height, strength):
    n = height.shape[0]
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * strength
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * strength
    nz = np.ones_like(height)
    ln = np.sqrt(dx * dx + dy * dy + 1)
    rgba = np.stack([(-dx / ln) * 0.5 + 0.5, (-dy / ln) * 0.5 + 0.5, (nz / ln) * 0.5 + 0.5, np.ones_like(height)], -1)
    img = bpy.data.images.new(name, n, n, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    img.filepath_raw = os.path.join(TEX, name + ".png")
    img.file_format = "PNG"
    img.save()
    return img


def fleece_height(n=512, seed=3):
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    out = np.zeros((n, n))
    for centre, width, gain in ((0.035, 0.02, 1.0), (0.12, 0.05, 0.5)):
        band = np.exp(-((r - centre) / width) ** 2)
        h = np.real(np.fft.ifft2(f * band))
        out += gain * h / h.std()
    return out


def thread_height(n=256, stripes=8, seed=5):
    rng = np.random.default_rng(seed)
    y = np.arange(n)[:, None] / n
    x = np.arange(n)[None, :] / n
    wob = 0.04 * np.sin(2 * math.pi * 3 * x)
    return np.sin(2 * math.pi * stripes * (y + wob)) + 0.15 * rng.standard_normal((n, n))


def simple(m, color, rough, normal_img=None, scale=(1, 1), rot=0.0, nstrength=0.6, sheen=0.0):
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    if sheen and "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = sheen
        b.inputs["Sheen Roughness"].default_value = 0.5
        b.inputs["Sheen Tint"].default_value = tuple(min(1.0, 0.04 + 1.6 * c) for c in color[:3]) + (1,)
    if normal_img is not None:
        uv = nt.nodes.new("ShaderNodeUVMap")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (scale[0], scale[1], 1)
        mp.inputs["Rotation"].default_value = (0, 0, rot)
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = normal_img
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = nstrength
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return b


objs = m_build.build(shape_keys=True)
m_pose.apply_pose(objs["rig"], m_pose.HERO)
fleece_n = save_normal("fleece_normal", fleece_height(), 2.2)
thread_n = save_normal("thread_normal", thread_height(), 1.6)
SCALES = {"M_Fleece_Blue": (38, 32), "M_Fleece_Navy": (5, 6), "M_Fleece_White": (4, 4), "M_Felt_Nose": (2, 2)}
for m in bpy.data.materials:
    kind = m.get("kind")
    if kind == "fleece":
        simple(m, hex_rgb(m["hex"]), 0.92, fleece_n, SCALES.get(m.name, (6, 6)), nstrength=0.7, sheen=0.35)
    elif kind == "thread":
        simple(m, hex_rgb(m["hex"]), 0.6, thread_n, (55, 55), rot=0.4, nstrength=0.5)
    elif kind == "logo":
        b = simple(m, (1, 1, 1, 1), 0.5)
        tex = m.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(TEX, "logo_color.png"), check_existing=True)
        m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        m.node_tree.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
        for attr, val in (("blend_method", "BLEND"), ("surface_render_method", "BLENDED")):
            try:
                setattr(m, attr, val)
            except Exception:
                pass

tris = 0
for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
print("GLB triangles", tris)

path = os.path.join(ROOT, "exports", "synergist-mascot-v3.glb")
want = dict(filepath=path, export_format="GLB", export_apply=False, export_skins=True, export_morph=True,
            export_morph_normal=False, export_animations=False, export_rest_position_armature=False,
            export_yup=True, export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True)
props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
bpy.ops.export_scene.gltf(**{k: v for k, v in want.items() if k in props})
print("GLB written", path, os.path.getsize(path))
