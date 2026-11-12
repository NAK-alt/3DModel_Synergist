"""Simple soft-toy style props for the stickers. Every prop faces -Y (the camera) and stands along +Z."""
import math

import bpy
from mathutils import Euler, Matrix, Vector

from m_util import hex_rgb, revolve, torus_profile

_MATS = {}


def mat(hexcol, rough=0.7, alpha=1.0, metallic=0.0):
    key = (hexcol, rough, alpha, metallic)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new("P_" + hexcol.lstrip("#"))
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = hex_rgb(hexcol)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Alpha"].default_value = alpha
    if "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = 0.25
    m.diffuse_color = hex_rgb(hexcol)
    _MATS[key] = m
    return m


def _obj(name, verts, faces, material, parent, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.materials.append(material)
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def box(parent, size, loc, hexcol, rot=(0, 0, 0), bevel=0.012, rough=0.7, name="box"):
    sx, sy, sz = (s / 2 for s in size)
    v = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
         (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = _obj(name, v, f, mat(hexcol, rough), parent)
    ob.location = loc
    ob.rotation_euler = Euler([math.radians(a) for a in rot])
    if bevel:
        b = ob.modifiers.new("bevel", "BEVEL")
        b.width = min(bevel, min(size) * 0.45)
        b.segments = 3
        ob.data.shade_smooth()
        ob.modifiers.new("wn", "WEIGHTED_NORMAL")
    return ob


def lathe(parent, profile, loc, hexcol, rot=(0, 0, 0), segs=40, rough=0.6, closed=False, alpha=1.0, metallic=0.0, name="lathe"):
    v, f, _ = revolve(profile, segs, closed=closed)
    ob = _obj(name, v, f, mat(hexcol, rough, alpha, metallic), parent, smooth=True)
    ob.location = loc
    ob.rotation_euler = Euler([math.radians(a) for a in rot])
    return ob


def clipboard(parent, check=False):
    box(parent, (0.27, 0.018, 0.36), (0, 0, 0), "#9A6A3C")
    box(parent, (0.225, 0.008, 0.295), (0, -0.012, -0.012), "#FBFAF6", bevel=0.004)
    box(parent, (0.10, 0.022, 0.045), (0, -0.016, 0.158), "#B9BEC8", bevel=0.008, rough=0.35)
    if check:
        g = "#22B455"
        box(parent, (0.052, 0.012, 0.115), (-0.052, -0.02, -0.045), g, rot=(0, -42, 0), bevel=0.006)
        box(parent, (0.052, 0.012, 0.215), (0.030, -0.02, -0.005), g, rot=(0, 36, 0), bevel=0.006)
    else:
        for k in range(4):
            w = 0.17 if k < 3 else 0.10
            box(parent, (w, 0.006, 0.016), (-(0.17 - w) / 2, -0.017, 0.085 - k * 0.05), "#27304F", bevel=0.003)


def pen(parent):
    lathe(parent, [(0.0, -0.11), (0.006, -0.085), (0.013, -0.06), (0.013, 0.10), (0.0, 0.105)], (0, 0, 0), "#D5B268", rough=0.4, segs=16)
    lathe(parent, [(0.0135, -0.03), (0.0135, 0.07)], (0, 0, 0), "#101629", segs=16)


def parcel(parent):
    box(parent, (0.38, 0.28, 0.27), (0, 0, 0), "#C89A62", bevel=0.014)
    box(parent, (0.07, 0.284, 0.274), (0, 0, 0), "#E7CFA0", bevel=0.004)
    box(parent, (0.12, 0.006, 0.075), (-0.105, -0.142, -0.05), "#FBFAF6", bevel=0.003)


def cup(parent):
    lathe(parent, [(0.0, 0.0), (0.052, 0.0), (0.056, 0.012), (0.074, 0.19), (0.0, 0.19)], (0, 0, 0), "#FBFAF6", segs=32)
    lathe(parent, [(0.0625, 0.055), (0.0705, 0.135)], (0, 0, 0), "#101629", segs=32)
    lathe(parent, [(0.0, 0.215), (0.050, 0.215), (0.060, 0.205), (0.080, 0.200), (0.080, 0.186), (0.0, 0.186)][::-1], (0, 0, 0), "#D5B268", segs=32, rough=0.45)


def magnifier(parent):
    lathe(parent, torus_profile(0.115, 0.017, 12), (0, 0, 0), "#D5B268", rot=(90, 0, 0), closed=True, rough=0.35, metallic=0.3)
    lathe(parent, [(0.0, 0.0), (0.112, 0.0)], (0, 0, 0), "#BFE6FF", rot=(90, 0, 0), alpha=0.38, rough=0.1)
    lathe(parent, [(0.0, 0.0), (0.022, 0.004), (0.024, 0.20), (0.0, 0.206)], (0, 0, -0.335), "#101629", segs=16)


def desk(parent):
    box(parent, (1.75, 0.62, 0.07), (0, 0, 0), "#B9824A", bevel=0.02)
    box(parent, (1.60, 0.04, 0.62), (0, -0.25, -0.34), "#A06C3A", bevel=0.01)
    for sx in (-0.80, 0.80):
        box(parent, (0.07, 0.54, 0.66), (sx, 0, -0.36), "#8D5E31", bevel=0.01)


def laptop(parent):
    box(parent, (0.50, 0.32, 0.022), (0, 0, 0), "#C9CED6", bevel=0.008, rough=0.4)
    box(parent, (0.50, 0.020, 0.33), (0, -0.165, 0.17), "#DCE0E6", rot=(-14, 0, 0), bevel=0.008, rough=0.4)
    lathe(parent, [(0.0, 0.0), (0.045, 0.0), (0.045, 0.004), (0.0, 0.004)], (0, -0.218, 0.19), "#D5B268", rot=(76, 0, 0), rough=0.4)


def envelope(parent):
    box(parent, (0.21, 0.014, 0.31), (0, 0, 0), "#D81E2C", bevel=0.006)
    box(parent, (0.214, 0.016, 0.05), (0, -0.001, 0.105), "#B5121F", bevel=0.004)
    box(parent, (0.085, 0.012, 0.085), (0, -0.008, -0.02), "#F2C94C", rot=(0, 45, 0), bevel=0.006, rough=0.4)


def phone(parent):
    box(parent, (0.13, 0.016, 0.25), (0, 0, 0), "#101629", bevel=0.012, rough=0.3)
    box(parent, (0.112, 0.006, 0.20), (0, -0.008, 0.004), "#6FC3FF", bevel=0.004, rough=0.2)


KINDS = dict(clipboard=clipboard, clipboard_check=lambda p: clipboard(p, True), pen=pen, parcel=parcel, cup=cup,
             magnifier=magnifier, desk=desk, laptop=laptop, envelope=envelope, phone=phone)


def add(kind, loc, rot=(0, 0, 0), scale=1.0, body_D=None):
    root = bpy.data.objects.new("Prop_" + kind, None)
    bpy.context.scene.collection.objects.link(root)
    KINDS[kind](root)
    M = (Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4()
         @ Matrix.Diagonal((scale, scale, scale, 1)))
    root.matrix_world = (body_D @ M) if body_D is not None else M
    return root


def clear():
    for ob in [o for o in bpy.data.objects if o.name.startswith("Prop_") or (o.parent and o.parent.name.startswith("Prop_"))]:
        bpy.data.objects.remove(ob, do_unlink=True)
