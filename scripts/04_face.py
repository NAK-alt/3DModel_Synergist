"""Synergist mascot - face system (step 6).

Run on the detailed model (built by 02_model.py):
  blender.exe -b blend/mascot_model.blend --python scripts/04_face.py -- <project_root>
        [--presets Happy,Sad,...] [--res 800] [--samples 128] [--no-render]

What it does:
  1. builds the face rig: a "Face_Ctrl" empty whose custom properties drive shape keys
     and visibility of the face patches (eyes, brows, pupils, mouth, props);
  2. applies the look-dev from 03_materials.py (materials, studio, fur);
  3. cuts the mouth recess (Boolean driven by the mouth cutter's shape keys);
  4. saves blend/mascot_face.blend and renders one face close-up per preset plus a sheet.

Character faces -Y, Z up. Viewer's left = -X = the character's RIGHT side, so "Left" objects
(Eye_Left, Brow_Left, ...) sit at +X. Face patches project along Y onto the hidden Face_Proxy,
so shape keys only need to move vertices in X and Z.
Section functions are drafted by Ollama and reviewed before they are merged.
"""
import argparse
import importlib.util
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------
# Geometry constants (must match 02_model.py)
# ----------------------------------------------------------------------------
BODY_R = 0.5
BODY_H = 1.26
BULGE = 0.015
BODY_TOP = 0.2 + 0.17 * BODY_H + BODY_H
HOOP_PCTS = [0.29, 0.44, 0.76, 0.97]
HOOP_MAJOR, HOOP_MINOR = 0.505, 0.025
FACE_X = 0.03


def hoop_z(p):
    return BODY_TOP - p * BODY_H


BODY_BOTTOM = BODY_TOP - BODY_H
EYE_Z = hoop_z(0.29) + 0.025 - 0.15          # eye centre height
EYE_DX = 0.14                                  # eye centre offset from FACE_X
EYE_W, EYE_H = 0.20, 0.30                      # eye white size (outline is +0.02)
PUPIL_OFFSET = (0.03, -0.02)                   # pupil centre relative to eye centre
HIGHLIGHT_OFFSET = (0.005, 0.025)              # highlight centre relative to eye centre
BROW_CZ = hoop_z(0.29) + 0.008                 # centre of the brow arcs (radius ~0.083)
MOUTH_TOP = hoop_z(0.44) - 0.108               # flat top edge of the resting mouth
MOUTH_W, MOUTH_H = 0.22, 0.085


def eye_x(side):
    """Eye centre x for "Left" (+X) or "Right" (-X)."""
    return FACE_X + (EYE_DX if side == "Left" else -EYE_DX)


def bulge_radius(z):
    bounds = sorted([BODY_BOTTOM, BODY_TOP] + [hoop_z(p) for p in HOOP_PCTS])
    for z0, z1 in zip(bounds, bounds[1:]):
        if z0 <= z <= z1 and z1 - z0 > 1e-9:
            return BODY_R + BULGE * math.sin(math.pi * (z - z0) / (z1 - z0))
    return BODY_R


def proxy_radius(z):
    """Radius of the Face_Proxy surface (fabric + soft bump over each hoop), as in 02_model.py."""
    r = bulge_radius(z)
    bump = max(BODY_R + 0.034 * math.exp(-((z - hoop_z(p)) / 0.045) ** 2) for p in HOOP_PCTS)
    return max(r, bump)


def front_y(x, z, offset=0.03):
    """A y just in front of the proxy surface (patches are projected back onto it)."""
    r = proxy_radius(z)
    return -math.sqrt(max(r * r - x * x, 0.0)) - offset


ROOT_NAME = "Mascot_Root"
CTRL_NAME = "Face_Ctrl"

# ----------------------------------------------------------------------------
# Controls: name -> (default, min, max). Presets set these; drivers read them.
# ----------------------------------------------------------------------------
CONTROLS = {
    # eyes
    "blink_L": (0.0, 0.0, 1.0), "blink_R": (0.0, 0.0, 1.0),
    "eye_wide": (0.0, 0.0, 1.0),
    "squint_L": (0.0, 0.0, 1.0), "squint_R": (0.0, 0.0, 1.0),
    "happy_L": (0.0, 0.0, 1.0), "happy_R": (0.0, 0.0, 1.0),      # ^ ^ arcs
    "closed_smile": (0.0, 0.0, 1.0),                               # content closed eyes (u u)
    "pupil_size": (0.0, -1.0, 1.0),
    "look_x": (0.0, -1.0, 1.0), "look_y": (0.0, -1.0, 1.0),
    # brows
    "brow_raise_L": (0.0, 0.0, 1.0), "brow_raise_R": (0.0, 0.0, 1.0),
    "brow_lower": (0.0, 0.0, 1.0), "brow_angry": (0.0, 0.0, 1.0), "brow_sad": (0.0, 0.0, 1.0),
    # mouth shapes
    "m_small_smile": (0.0, 0.0, 1.0), "m_big_smile": (0.0, 0.0, 1.0), "m_laugh": (0.0, 0.0, 1.0),
    "m_O": (0.0, 0.0, 1.0), "m_flat": (0.0, 0.0, 1.0), "m_frown": (0.0, 0.0, 1.0),
    "m_smirk_L": (0.0, 0.0, 1.0), "m_smirk_R": (0.0, 0.0, 1.0), "m_pout": (0.0, 0.0, 1.0),
    "m_teeth": (0.0, 0.0, 1.0), "m_tongue_out": (0.0, 0.0, 1.0), "m_shout": (0.0, 0.0, 1.0),
    # visemes
    "v_A": (0.0, 0.0, 1.0), "v_E": (0.0, 0.0, 1.0), "v_I": (0.0, 0.0, 1.0), "v_O": (0.0, 0.0, 1.0),
    "v_U": (0.0, 0.0, 1.0), "v_MBP": (0.0, 0.0, 1.0), "v_FV": (0.0, 0.0, 1.0),
    # cheeks + props (props are 0/1 visibility switches)
    "cheek_puff": (0.0, 0.0, 1.0), "blush": (0.0, 0.0, 1.0),
    "prop_sweat": (0.0, 0.0, 1.0), "prop_tears": (0.0, 0.0, 1.0), "prop_stars": (0.0, 0.0, 1.0),
    "prop_hearts": (0.0, 0.0, 1.0), "prop_dizzy": (0.0, 0.0, 1.0),
}


def make_controls():
    ctrl = bpy.data.objects.get(CTRL_NAME)
    if ctrl is None:
        ctrl = bpy.data.objects.new(CTRL_NAME, None)
        bpy.context.scene.collection.objects.link(ctrl)
        ctrl.empty_display_type = "CIRCLE"
        ctrl.location = (FACE_X, -0.9, EYE_Z)
        ctrl.parent = bpy.data.objects.get(ROOT_NAME)
    for name, (default, lo, hi) in CONTROLS.items():
        ctrl[name] = float(default)
        ui = ctrl.id_properties_ui(name)
        ui.update(min=lo, max=hi, soft_min=lo, soft_max=hi, default=default)
    return ctrl


# ----------------------------------------------------------------------------
# Driver + shape key helpers
# ----------------------------------------------------------------------------
def _add_driver(id_block, data_path, expr, props, index=-1):
    """Driver on id_block.data_path = expr, with one SINGLE_PROP variable per Face_Ctrl property
    (the variable is named exactly like the property)."""
    ctrl = bpy.data.objects[CTRL_NAME]
    fc = id_block.driver_add(data_path, index) if index >= 0 else id_block.driver_add(data_path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for v in list(drv.variables):
        drv.variables.remove(v)
    for p in props:
        var = drv.variables.new()
        var.name = p
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = ctrl
        var.targets[0].data_path = f'["{p}"]'
    drv.expression = expr
    return fc


def ensure_basis(obj):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    return obj.data.shape_keys.key_blocks["Basis"]


def add_shape_key(obj, key_name, fn):
    """New shape key whose vertex i = fn(basis co i) (a Vector -> Vector function, world = local)."""
    basis = ensure_basis(obj)
    kb = obj.shape_key_add(name=key_name, from_mix=False)
    for i, bp in enumerate(basis.data):
        kb.data[i].co = fn(bp.co.copy())
    kb.slider_min, kb.slider_max = 0.0, 1.0
    return kb


def drive_key(obj, key_name, expr, props):
    kb = obj.data.shape_keys.key_blocks[key_name]
    return _add_driver(kb, "value", expr, props)


def drive_hidden(obj, expr, props):
    """Drive hide_render AND hide_viewport with a boolean-valued expression (True = hidden)."""
    _add_driver(obj, "hide_render", expr, props)
    _add_driver(obj, "hide_viewport", expr, props)


# simple 2D transforms in the XZ face plane (y untouched)
def xz_scale(cx, cz, sx, sz=None):
    sz = sx if sz is None else sz
    return lambda co: Vector((cx + (co.x - cx) * sx, co.y, cz + (co.z - cz) * sz))


def xz_move(dx, dz):
    return lambda co: Vector((co.x + dx, co.y, co.z + dz))


def xz_rotate(cx, cz, angle):
    c, s = math.cos(angle), math.sin(angle)
    return lambda co: Vector((cx + (co.x - cx) * c - (co.z - cz) * s, co.y,
                              cz + (co.x - cx) * s + (co.z - cz) * c))


# ----------------------------------------------------------------------------
# Patch helpers (same construction as the face patches in 02_model.py)
# ----------------------------------------------------------------------------
def patch_modifiers(obj, layer, thickness=0.0032, subsurf=True):
    """Project onto Face_Proxy along Y, thicken, subdivide. Layers are 4 mm apart."""
    sw = obj.modifiers.new("Shrinkwrap", "SHRINKWRAP")
    sw.target = bpy.data.objects["Face_Proxy"]
    sw.wrap_method = "PROJECT"
    sw.use_project_y = True
    sw.use_negative_direction = True
    sw.use_positive_direction = True
    sw.wrap_mode = "OUTSIDE_SURFACE"
    sw.offset = 0.002 + 0.004 * layer
    so = obj.modifiers.new("Solidify", "SOLIDIFY")
    so.thickness = thickness
    so.offset = 1.0
    so.use_even_offset = True
    if subsurf:
        sd = obj.modifiers.new("Subdivision", "SUBSURF")
        sd.levels, sd.render_levels = 1, 2


def _finish(name, bm, mat, layer, subsurf=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if sum(f.normal.y for f in bm.faces) > 0:     # make the patch face the camera (-Y)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = bpy.data.objects[ROOT_NAME]
    if mat is not None:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    patch_modifiers(obj, layer, subsurf=subsurf)
    return obj


def outline_patch(name, pts_uv, cx, cz, layer, mat, subsurf=True, grid=0.01):
    """Filled patch from a closed outline [(u, v), ...] around (cx, cz).
    subsurf=True: one n-gon face (fine for round shapes, the subdivision smooths it).
    subsurf=False (sharp props: stars, hearts, drops): constrained Delaunay triangulation with
    interior points on a `grid` lattice, so the patch bends smoothly over the curved body
    instead of creasing like folded paper and the thickening never spikes."""
    from mathutils.geometry import delaunay_2d_cdt
    bm = bmesh.new()
    if subsurf:
        verts = [bm.verts.new((cx + u, front_y(cx + u, cz + v), cz + v)) for u, v in pts_uv]
        bm.faces.new(verts)
        return _finish(name, bm, mat, layer, subsurf)
    n = len(pts_uv)
    us = [p[0] for p in pts_uv]
    vs = [p[1] for p in pts_uv]
    pts2 = [Vector((u, v)) for u, v in pts_uv]
    k = 0
    u0 = min(us) + grid / 2
    while u0 < max(us):
        v0 = min(vs) + grid / 2
        while v0 < max(vs):
            pts2.append(Vector((u0 + (grid * 0.5 if k % 2 else 0.0) * 0.0, v0)))
            v0 += grid
        u0 += grid
        k += 1
    edges = [(i, (i + 1) % n) for i in range(n)]
    out = delaunay_2d_cdt(pts2, edges, [list(range(n))], 1, 1e-6)  # 1 = triangles inside the outline
    verts_out, faces_out = out[0], out[2]
    verts = [bm.verts.new((cx + p.x, front_y(cx + p.x, cz + p.y), cz + p.y)) for p in verts_out]
    for f in faces_out:
        try:
            bm.faces.new([verts[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    return _finish(name, bm, mat, layer, subsurf)

def strip_patch(name, rows_uv, cx, cz, layer, mat, subsurf=True):
    """Quad strip between parallel polylines rows_uv = [[(u, v), ...], [(u, v), ...], ...]
    (all rows the same length), e.g. arcs, tear streams, spirals."""
    bm = bmesh.new()
    rows = [[bm.verts.new((cx + u, front_y(cx + u, cz + v), cz + v)) for u, v in row] for row in rows_uv]
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(len(r0) - 1):
            bm.faces.new((r0[k], r0[k + 1], r1[k + 1], r1[k]))
    return _finish(name, bm, mat, layer, subsurf)


def arc_rows(radius, width, a0_deg, a1_deg, n=24, rows=3):
    """Rows for strip_patch: an arc band (angles in degrees, 0 = +u, 90 = +v)."""
    out = []
    for i in range(rows):
        rr = radius - width / 2 + width * i / (rows - 1)
        out.append([(rr * math.cos(math.radians(a0_deg + (a1_deg - a0_deg) * k / n)),
                     rr * math.sin(math.radians(a0_deg + (a1_deg - a0_deg) * k / n))) for k in range(n + 1)])
    return out


# ----------------------------------------------------------------------------
# SECTIONS (Ollama drafts; each is a function taking the materials dict `M`)
# ----------------------------------------------------------------------------
# >>> SECTION eyes
def build_eyes():
    new_objects = []
    for side in ("Left", "Right"):
        S = side[0]  # "L" or "R"
        cx = eye_x(side)
        cz = EYE_Z
        inner_sign = -1 if side == "Left" else 1

        # Existing objects
        outline = bpy.data.objects.get(f"Eye_{side}_Outline")
        white = bpy.data.objects.get(f"Eye_{side}_White")
        pupil = bpy.data.objects.get(f"Pupil_{side}")
        highlight = bpy.data.objects.get(f"Highlight_{side}")
        brow = bpy.data.objects.get(f"Brow_{side}")
        eyelid_upper = bpy.data.objects.get(f"Eyelid_{side}_Upper")
        eyelid_lower = bpy.data.objects.get(f"Eyelid_{side}_Lower")

        # --- Eye outline and white ---
        # Wide
        add_shape_key(outline, "Wide", xz_scale(cx, cz, 1.10))
        drive_key(outline, "Wide", "eye_wide", ["eye_wide"])
        add_shape_key(white, "Wide", xz_scale(cx, cz, 1.10))
        drive_key(white, "Wide", "eye_wide", ["eye_wide"])

        # Squint (custom squash about line z = cz + 0.02)
        squash_fn = lambda co: Vector((co.x, co.y,
                                       (cz + 0.02) + (co.z - (cz + 0.02)) * (0.45 if co.z < cz + 0.02 else 0.8)))
        add_shape_key(outline, "Squint", squash_fn)
        drive_key(outline, "Squint", f"squint_{S}", [f"squint_{S}"])
        add_shape_key(white, "Squint", squash_fn)
        drive_key(white, "Squint", f"squint_{S}", [f"squint_{S}"])

        # --- Pupil and Highlight ---
        pcx, pcz = cx + PUPIL_OFFSET[0], cz + PUPIL_OFFSET[1]
        hcx, hcz = cx + HIGHLIGHT_OFFSET[0], cz + HIGHLIGHT_OFFSET[1]

        for obj, own_cx, own_cz in ((pupil, pcx, pcz), (highlight, hcx, hcz)):
            # Look directions
            add_shape_key(obj, "Look_Right", xz_move(0.012, 0))
            drive_key(obj, "Look_Right", "max(look_x, 0)", ["look_x"])
            add_shape_key(obj, "Look_Left", xz_move(-0.06, 0))
            drive_key(obj, "Look_Left", "max(-look_x, 0)", ["look_x"])
            add_shape_key(obj, "Look_Up", xz_move(0, 0.045))
            drive_key(obj, "Look_Up", "max(look_y, 0)", ["look_y"])
            add_shape_key(obj, "Look_Down", xz_move(0, -0.06))
            drive_key(obj, "Look_Down", "max(-look_y, 0)", ["look_y"])

            # Pupil size (different for pupil and highlight)
            if obj == pupil:
                add_shape_key(obj, "Big", xz_scale(pcx, pcz, 1.3))
                drive_key(obj, "Big", "max(pupil_size, 0)", ["pupil_size"])
                add_shape_key(obj, "Small", xz_scale(pcx, pcz, 0.6))
                drive_key(obj, "Small", "max(-pupil_size, 0)", ["pupil_size"])
            else:  # highlight
                add_shape_key(obj, "Big", xz_move(-0.012, 0.012))
                drive_key(obj, "Big", "max(pupil_size, 0)", ["pupil_size"])
                small_fn = lambda co: xz_move(0.01, -0.012)(xz_scale(hcx, hcz, 0.8)(co))
                add_shape_key(obj, "Small", small_fn)
                drive_key(obj, "Small", "max(-pupil_size, 0)", ["pupil_size"])

            # Wide and Squint follow the eye
            add_shape_key(obj, "Wide", xz_scale(cx, cz, 1.10))
            drive_key(obj, "Wide", "eye_wide", ["eye_wide"])
            add_shape_key(obj, "Squint", squash_fn)
            drive_key(obj, "Squint", f"squint_{S}", [f"squint_{S}"])

        # --- Blink: squash the open eye toward a line just below centre; partial = sleepy lid.
        # At full blink the open eye hides and the embroidered closed-eye curve shows instead.
        # (The blue eyelid patches from 02_model.py read badly as a cut-out shape; they stay hidden.)
        line_z = cz - 0.04
        blink_fn = lambda co: Vector((cx + (co.x - cx) * 0.96, co.y, line_z + (co.z - line_z) * 0.06))
        for obj in (outline, white, pupil, highlight):
            add_shape_key(obj, "Blink", blink_fn)
            drive_key(obj, "Blink", f"blink_{S}", [f"blink_{S}"])
        for lid in (eyelid_upper, eyelid_lower):
            lid.hide_render = True
            lid.hide_viewport = True
        # --- Brow ---
        px, pz = cx, BROW_CZ + 0.083
        # Raise
        add_shape_key(brow, "Raise", xz_move(0, 0.035))
        drive_key(brow, "Raise", f"brow_raise_{S}", [f"brow_raise_{S}"])
        # Lower
        add_shape_key(brow, "Lower", xz_move(0, -0.02))
        drive_key(brow, "Lower", "brow_lower", ["brow_lower"])
        # Angry (inner down)
        angle_angry = inner_sign * -math.radians(32)  # review: 18 deg was too subtle on the arched brow
        angry_fn = lambda co: xz_move(0, -0.022)(xz_rotate(px, pz, angle_angry)(co))
        add_shape_key(brow, "Angry", angry_fn)
        drive_key(brow, "Angry", "brow_angry", ["brow_angry"])
        # Sad (inner up)
        angle_sad = inner_sign * math.radians(28)
        sad_fn = lambda co: xz_move(0, 0.01)(xz_rotate(px, pz, angle_sad)(co))
        add_shape_key(brow, "Sad", sad_fn)
        drive_key(brow, "Sad", "brow_sad", ["brow_sad"])

        # --- Hide open eye when replaced by arcs/props ---
        vis_expr = (f"happy_{S} > 0.5 or closed_smile > 0.5 or blink_{S} > 0.9"
                    " or prop_stars > 0.5 or prop_hearts > 0.5")
        vis_vars = [f"happy_{S}", "closed_smile", f"blink_{S}", "prop_stars", "prop_hearts"]
        for obj in (outline, white):
            drive_hidden(obj, vis_expr, vis_vars)
        for obj in (pupil, highlight):
            expr = vis_expr + " or prop_dizzy > 0.5"
            vars = vis_vars + ["prop_dizzy"]
            drive_hidden(obj, expr, vars)

        # --- New arc patches ---
        happy_arc = strip_patch(f"EyeArc_{side}_Happy",
                                arc_rows(0.085, 0.022, 25, 155),
                                cx, cz - 0.05, 2, None)
        closed_arc = strip_patch(f"EyeArc_{side}_Closed",
                                 arc_rows(0.085, 0.022, 205, 335),
                                 cx, cz + 0.06, 2, None)
        # Visibility for arcs
        drive_hidden(happy_arc, f"happy_{S} <= 0.5", [f"happy_{S}"])
        drive_hidden(closed_arc, f"closed_smile <= 0.5 and blink_{S} <= 0.9 or happy_{S} > 0.5", ["closed_smile", f"blink_{S}", f"happy_{S}"])

        new_objects.extend([happy_arc, closed_arc])

    return new_objects
# <<< SECTION eyes

def assign_rig_materials(lookdev, mats):
    """Materials for objects the rig creates (look-dev materials come from 03_materials.py)."""
    black = mats.get("MAT_Satin_Black")
    for side in ("Left", "Right"):
        for kind in ("Happy", "Closed"):
            o = bpy.data.objects.get(f"EyeArc_{side}_{kind}")
            if o is not None:
                o.data.materials.clear()
                o.data.materials.append(black)
    for fn in RIG_MATERIAL_HOOKS:
        fn(lookdev, mats)


RIG_MATERIAL_HOOKS = []  # later sections append (lookdev, mats) -> None callbacks


# >>> SECTION mouth
def _mouth_outline(w, h, sag=0.0, lift=0.0, asym=0.0, r=0.5, dz=0.0, n=48):
    """Return list of n (u, v) points for a closed mouth outline, CCW.
    Top edge: k = 0..n/2 from right to left, bottom edge: k = 1..n/2-1 from left to right.
    """
    pts = []
    half = n // 2
    # Top edge (right to left)
    for k in range(half + 1):
        u = w / 2 - w * k / half
        s = 2 * u / w
        v = dz + lift * s * s - sag * (1 - s * s) + asym * 0.03 * s
        pts.append((u, v))
    # Bottom edge (left to right, excluding endpoints already included)
    for k in range(1, half):
        u = -w / 2 + w * k / half
        s = 2 * u / w
        v_top = dz + lift * s * s - sag * (1 - s * s) + asym * 0.03 * s
        v = v_top - h * max(1 - s * s, 0) ** r
        pts.append((u, v))
    return pts

# Limits (review): the wordmark starts ~0.099 below MOUTH_TOP and the nose sits right on MOUTH_TOP,
# so every shape keeps its bottom above -0.092 and its top edge at or below 0; open shapes grow wider.
MOUTH_SHAPES = {
    "rest": dict(w=MOUTH_W, h=MOUTH_H),
    "small_smile": dict(w=0.17, h=0.012, lift=0.025, dz=-0.012),
    "big_smile": dict(w=0.25, h=0.085, lift=0.03),
    "laugh": dict(w=0.27, h=0.09, lift=0.035, r=0.4),
    "O": dict(w=0.09, h=0.075, sag=-0.012, dz=-0.015),
    "flat": dict(w=0.16, h=0.010, dz=-0.01),
    "frown": dict(w=0.17, h=0.02, lift=-0.03, dz=-0.01),
    "smirk_L": dict(w=0.17, h=0.015, asym=1, dz=-0.012),
    "smirk_R": dict(w=0.17, h=0.015, asym=-1, dz=-0.012),
    "pout": dict(w=0.08, h=0.03, sag=-0.008, dz=-0.02),
    "shout": dict(w=0.24, h=0.09, r=0.3),
    "vA": dict(w=0.18, h=0.088, r=0.45),
    "vE": dict(w=0.22, h=0.05, lift=0.01, r=0.4),
    "vI": dict(w=0.20, h=0.03, lift=0.015),
    "vO": dict(w=0.11, h=0.08, sag=-0.01, dz=-0.012),
    "vU": dict(w=0.07, h=0.05, sag=-0.008, dz=-0.02),
    "vMBP": dict(w=0.15, h=0.006, dz=-0.005),
    "vFV": dict(w=0.16, h=0.025, dz=-0.005),
}

def _set_key(obj, key_name, coords):
    """Add a shape key to obj and set its vertices to the given world-space coords."""
    ensure_basis(obj)
    kb = obj.shape_key_add(name=key_name, from_mix=False)
    for i, coord in enumerate(coords):
        kb.data[i].co = coord
    kb.slider_min, kb.slider_max = 0.0, 1.0
    return kb

def _xyz(u, v, y=None):
    """Convert (u, v) relative to (FACE_X, MOUTH_TOP) to a Vector in world space.
    Default y uses front_y; provide y to override."""
    x = FACE_X + u
    z = MOUTH_TOP + v
    if y is None:
        y = front_y(x, z)
    return Vector((x, y, z))

def _mouth_outline_points(shape_name):
    """Return list of (u, v) points for a given MOUTH_SHAPES entry."""
    params = MOUTH_SHAPES[shape_name]
    w = params.get("w", MOUTH_W)
    h = params.get("h", MOUTH_H)
    sag = params.get("sag", 0.0)
    lift = params.get("lift", 0.0)
    asym = params.get("asym", 0.0)
    r = params.get("r", 0.5)
    dz = params.get("dz", 0.0)
    return _mouth_outline(w, h, sag, lift, asym, r, dz)

def _compute_lip_band_coords(shape_name):
    """Return two lists: inner loop coords and outer loop coords (world space) for the lip band."""
    pts = _mouth_outline_points(shape_name)
    n = len(pts)
    inner = []
    outer = []
    for i, (u, v) in enumerate(pts):
        # compute outward normal in XZ plane
        prev = pts[(i - 1) % n]
        next_ = pts[(i + 1) % n]
        du = next_[0] - prev[0]
        dv = next_[1] - prev[1]
        length = math.hypot(du, dv)
        if length < 1e-9:
            # degenerate, use perpendicular to line from center
            cx = sum(p[0] for p in pts) / n
            cz = sum(p[1] for p in pts) / n
            du, dv = u - cx, v - cz
            length = math.hypot(du, dv)
            if length < 1e-9:
                du, dv = 0.0, 1.0
                length = 1.0
        # tangent normalized
        tu, tv = du / length, dv / length
        # outward normal for CCW: (tv, -tu)
        nx, nz = tv, -tu
        inner.append(_xyz(u, v))
        outer.append(_xyz(u + 0.009 * nx, v + 0.009 * nz))
    return inner, outer

def _compute_cutter_loops(shape_name):
    """Return front and back loop coords (world space) for the cutter."""
    pts = _mouth_outline_points(shape_name)
    n = len(pts)
    # centroid
    cx = sum(p[0] for p in pts) / n
    cz = sum(p[1] for p in pts) / n
    front_y = -(bulge_radius(MOUTH_TOP) + 0.08)
    back_y = -(bulge_radius(MOUTH_TOP) - 0.035)
    front = []
    back = []
    for u, v in pts:
        front.append(_xyz(u, v, y=front_y))
        # scaled about centroid
        su = cx + 0.8 * (u - cx)
        sv = cz + 0.8 * (v - cz)
        back.append(_xyz(su, sv, y=back_y))
    return front, back

def _create_cube_sphere(radius_x, radius_y, radius_z, location):
    """Create a mesh object from a subdivided cube normalized to an ellipsoid."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    loc = Vector(location)
    for v in bm.verts:
        u = v.co.normalized()
        # bake the location into the vertices: shape keys here work in world = local space
        v.co = loc + Vector((u.x * radius_x, u.y * radius_y, u.z * radius_z))
    me = bpy.data.meshes.new("tmp_sphere")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("tmp_sphere_obj", me)
    # will be parented and renamed later
    return obj

def build_mouth():
    """Build the mouth lip, cutter, teeth, tongue, and cheek/fur effects. Returns list of new objects."""
    # Delete old objects
    for old_name in ("Mouth", "Mouth_Outline", "Teeth_Upper", "Tongue"):
        obj = bpy.data.objects.get(old_name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    # 1. Mouth_Lip
    lip_name = "Mouth_Lip"
    lip_obj = bpy.data.objects.new(lip_name, bpy.data.meshes.new(lip_name))
    bpy.context.scene.collection.objects.link(lip_obj)
    lip_obj.parent = bpy.data.objects[ROOT_NAME]
    # build mesh for rest shape (basis)
    inner_rest, outer_rest = _compute_lip_band_coords("rest")
    n = len(inner_rest)
    bm = bmesh.new()
    inner_verts = [bm.verts.new(co) for co in inner_rest]
    outer_verts = [bm.verts.new(co) for co in outer_rest]
    for k in range(n):
        bm.faces.new((inner_verts[k], inner_verts[(k+1)%n], outer_verts[(k+1)%n], outer_verts[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if sum(f.normal.y for f in bm.faces) > 0:  # face the camera (-Y) like the other patches
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(lip_obj.data)
    bm.free()
    for p in lip_obj.data.polygons:
        p.use_smooth = True
    patch_modifiers(lip_obj, layer=1)
    # basis shape key
    ensure_basis(lip_obj)
    # add shape keys for other shapes
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        inner, outer = _compute_lip_band_coords(shape_name)
        coords = inner + outer  # inner first, then outer
        _set_key(lip_obj, f"S_{shape_name}", coords)
        # driver: control name matches shape_name (except some have prefix)
        control = shape_name  # e.g., "small_smile" -> "m_small_smile"? Actually mapping: m_small_smile -> small_smile
        # We need to map control name: m_small_smile -> small_smile, v_A -> vA, etc.
        # But the control names in CONTROLS are "m_small_smile", "m_big_smile", etc. So we need to find the control that maps to this shape.
        # The mapping is given: m_small_smile->small_smile, etc.
        # We can create a reverse mapping: from shape_name to control_name.
        control_map = {
            "small_smile": "m_small_smile",
            "big_smile": "m_big_smile",
            "laugh": "m_laugh",
            "O": "m_O",
            "flat": "m_flat",
            "frown": "m_frown",
            "smirk_L": "m_smirk_L",
            "smirk_R": "m_smirk_R",
            "pout": "m_pout",
            "shout": "m_shout",
            "vA": "v_A",
            "vE": "v_E",
            "vI": "v_I",
            "vO": "v_O",
            "vU": "v_U",
            "vMBP": "v_MBP",
            "vFV": "v_FV",
        }
        ctrl_name = control_map[shape_name]
        drive_key(lip_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])

    # 2. Mouth_Cutter
    cutter_name = "Mouth_Cutter"
    cutter_obj = bpy.data.objects.new(cutter_name, bpy.data.meshes.new(cutter_name))
    bpy.context.scene.collection.objects.link(cutter_obj)
    cutter_obj.parent = bpy.data.objects[ROOT_NAME]
    front_rest, back_rest = _compute_cutter_loops("rest")
    bm = bmesh.new()
    front_verts = [bm.verts.new(co) for co in front_rest]
    back_verts = [bm.verts.new(co) for co in back_rest]
    # side quads
    for k in range(n):
        bm.faces.new((front_verts[k], front_verts[(k+1)%n], back_verts[(k+1)%n], back_verts[k]))
    # front and back n-gons (normals outward)
    bm.faces.new(front_verts)
    bm.faces.new(list(reversed(back_verts)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # closed cutter: consistent outward normals
    bm.normal_update()
    bm.to_mesh(cutter_obj.data)
    bm.free()
    cutter_obj.hide_render = True
    cutter_obj.display_type = 'WIRE'
    ensure_basis(cutter_obj)
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        front, back = _compute_cutter_loops(shape_name)
        coords = front + back
        _set_key(cutter_obj, f"S_{shape_name}", coords)
        ctrl_name = control_map[shape_name]
        drive_key(cutter_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])

    # 3. Mouth_Teeth
    teeth_name = "Mouth_Teeth"
    teeth_obj = _create_cube_sphere(0.075, 0.012, 0.016,
                                    (FACE_X, -(bulge_radius(MOUTH_TOP)) + 0.024, MOUTH_TOP - 0.020))  # front face ~1 cm inside the fabric
    teeth_obj.name = teeth_name
    bpy.context.scene.collection.objects.link(teeth_obj)
    teeth_obj.parent = bpy.data.objects[ROOT_NAME]
    teeth_obj.data.name = teeth_name
    for p in teeth_obj.data.polygons:
        p.use_smooth = True
    sub = teeth_obj.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    ensure_basis(teeth_obj)
    # store basis vertex coords for later scaling/translation
    basis_teeth_coords = [v.co.copy() for v in teeth_obj.data.vertices]
    # For each shape
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        params = MOUTH_SHAPES[shape_name]
        w = params.get("w", MOUTH_W)
        h = params.get("h", MOUTH_H)
        sag = params.get("sag", 0.0)
        lift = params.get("lift", 0.0)
        asym = params.get("asym", 0.0)
        r = params.get("r", 0.5)
        dz = params.get("dz", 0.0)
        # compute v_top(0) for this shape
        # v_top(s) = dz + lift*s^2 - sag*(1-s^2) + asym*0.03*s, at s=0 -> dz - sag
        v_top_mid = dz - sag
        # top z of teeth (basis): centre_z + 0.016
        centre_z = MOUTH_TOP - 0.020
        top_z_basis = centre_z + 0.016
        target_top_z = MOUTH_TOP + v_top_mid
        dz_trans = target_top_z - top_z_basis
        scale_x = w / MOUTH_W
        is_closed = h < 0.03
        push_y = 0.03 if is_closed else 0.0
        new_coords = []
        for v in basis_teeth_coords:
            nx = FACE_X + (v.x - FACE_X) * scale_x
            ny = v.y + push_y
            nz = v.z + dz_trans
            # For vFV, lower by 0.012
            if shape_name == "vFV":
                nz -= 0.012
            new_coords.append(Vector((nx, ny, nz)))
        _set_key(teeth_obj, f"S_{shape_name}", new_coords)
        ctrl_name = control_map[shape_name]
        drive_key(teeth_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])
    # Teeth_Show key
    show_coords = []
    top_z = centre_z + 0.016
    for v in basis_teeth_coords:
        nx = v.x
        ny = v.y - 0.008
        nz = top_z + (v.z - top_z) * 1.4
        show_coords.append(Vector((nx, ny, nz)))
    _set_key(teeth_obj, "Teeth_Show", show_coords)
    drive_key(teeth_obj, "Teeth_Show", "m_teeth", ["m_teeth"])

    # 4. Mouth_Tongue
    tongue_name = "Mouth_Tongue"
    tongue_obj = _create_cube_sphere(0.05, 0.02, 0.022,
                                     (FACE_X, -(bulge_radius(MOUTH_TOP)) + 0.032, MOUTH_TOP - 0.068))  # inside the cavity
    tongue_obj.name = tongue_name
    bpy.context.scene.collection.objects.link(tongue_obj)
    tongue_obj.parent = bpy.data.objects[ROOT_NAME]
    tongue_obj.data.name = tongue_name
    for p in tongue_obj.data.polygons:
        p.use_smooth = True
    sub = tongue_obj.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    ensure_basis(tongue_obj)
    basis_tongue_coords = [v.co.copy() for v in tongue_obj.data.vertices]
    # For each shape
    for shape_name in MOUTH_SHAPES:
        if shape_name == "rest":
            continue
        params = MOUTH_SHAPES[shape_name]
        h = params.get("h", MOUTH_H)
        sag = params.get("sag", 0.0)
        dz = params.get("dz", 0.0)
        # v_top(0) = dz - sag
        v_top_mid = dz - sag
        v_bottom_mid = v_top_mid - h
        target_top_z = MOUTH_TOP + v_bottom_mid + 0.024  # top of tongue?
        # tongue top basis = centre_z + 0.022
        centre_z = MOUTH_TOP - 0.068
        top_z_basis = centre_z + 0.022
        dz_trans = target_top_z - top_z_basis
        is_closed = h < 0.03
        push_y = 0.045 if is_closed else 0.0
        new_coords = []
        for v in basis_tongue_coords:
            nx = v.x
            ny = v.y + push_y
            nz = v.z + dz_trans
            new_coords.append(Vector((nx, ny, nz)))
        _set_key(tongue_obj, f"S_{shape_name}", new_coords)
        ctrl_name = control_map[shape_name]
        drive_key(tongue_obj, f"S_{shape_name}", ctrl_name, [ctrl_name])
    # Tongue_Out key
    out_coords = []
    cx = FACE_X
    cy = -(bulge_radius(MOUTH_TOP)) + 0.032
    cz = MOUTH_TOP - 0.068
    for v in basis_tongue_coords:
        nx = cx + (v.x - cx) * 0.9
        ny = cy + (v.y - cy) * 1.6 - 0.065  # out past the lip
        nz = v.z - 0.02           # small drop; the wordmark sits just below
        out_coords.append(Vector((nx, ny, nz)))
    _set_key(tongue_obj, "Tongue_Out", out_coords)
    drive_key(tongue_obj, "Tongue_Out", "m_tongue_out", ["m_tongue_out"])

    # 5. Cheek puff on Body
    body = bpy.data.objects.get("Body")
    if body:
        ensure_basis(body)
        # create CheekPuff shape key
        kb = body.shape_key_add(name="CheekPuff", from_mix=False)
        basis_body_coords = [v.co.copy() for v in body.data.vertices]
        cheek_centers = [(FACE_X + 0.17, MOUTH_TOP - 0.03), (FACE_X - 0.17, MOUTH_TOP - 0.03)]
        for i, v in enumerate(body.data.vertices):
            orig = basis_body_coords[i]
            x, y, z = orig
            new_x, new_y, new_z = x, y, z
            for cx, cz in cheek_centers:
                if y >= 0:  # front of the barrel only
                    continue
                d2 = ((x - cx) / 0.08) ** 2 + ((z - cz) / 0.07) ** 2
                if d2 < 1:
                    factor = 0.014 * (1 - d2) ** 2
                    # outward direction in XY plane
                    length = math.hypot(x, y)
                    if length > 1e-9:
                        dir_x = x / length
                        dir_y = y / length
                    else:
                        dir_x, dir_y = 0.0, 0.0
                    new_x += dir_x * factor
                    new_y += dir_y * factor
            kb.data[i].co = Vector((new_x, new_y, new_z))
        kb.slider_min, kb.slider_max = 0.0, 1.0
        drive_key(body, "CheekPuff", "cheek_puff", ["cheek_puff"])

        # 6. Fur mask vertex group
        if "fur_density" not in body.vertex_groups:
            vg = body.vertex_groups.new(name="fur_density")
        else:
            vg = body.vertex_groups["fur_density"]
        for i, v in enumerate(body.data.vertices):
            x, y, z = v.co
            if y < 0:
                e2 = ((x - FACE_X) / 0.19) ** 2 + ((z - (MOUTH_TOP - 0.06)) / 0.13) ** 2
                dist = math.sqrt(e2)
                if dist < 1.0:
                    weight = 0.0
                elif dist > 1.3:
                    weight = 1.0
                else:
                    weight = (dist - 1.0) / (1.3 - 1.0)
            else:
                weight = 1.0
            vg.add([i], weight, 'REPLACE')

    return [lip_obj, cutter_obj, teeth_obj, tongue_obj]

def add_mouth_recess(lookdev, mats):
    """Add Boolean modifier to Body using Mouth_Cutter and assign cavity material."""
    body = bpy.data.objects.get("Body")
    cutter = bpy.data.objects.get("Mouth_Cutter")
    if not body or not cutter:
        return
    # Create cavity material
    cavity_mat = mats.get("MAT_Mouth_Cavity")
    if cavity_mat is None:
        cavity_mat = lookdev.create_satin("MAT_Mouth_Cavity", "#24070A", 10, aniso=0.2)
        mats["MAT_Mouth_Cavity"] = cavity_mat
    # Assign to cutter (clear and append)
    cutter.data.materials.clear()
    cutter.data.materials.append(cavity_mat)
    # Add Boolean modifier to Body
    bool_mod = body.modifiers.new("MouthRecess", 'BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    # Try MANIFOLD then EXACT solver
    try:
        bool_mod.solver = 'MANIFOLD'
    except TypeError:
        try:
            bool_mod.solver = 'EXACT'
        except TypeError:
            pass
    # Set material_mode if available
    if hasattr(bool_mod, "material_mode"):
        try:
            bool_mod.material_mode = 'TRANSFER'
        except TypeError:
            pass
    # Ensure Body has cavity material in a slot
    if cavity_mat.name not in [m.name for m in body.data.materials if m]:
        body.data.materials.append(cavity_mat)
    # modifiers.new appends, so the Boolean is already last (after Subdivision and the fur particles)
    print("[04] Body modifiers:", [m.type for m in body.modifiers], "solver:", bool_mod.solver)

def _mouth_materials(lookdev, mats):
    """Assign materials to mouth objects."""
    lip = bpy.data.objects.get("Mouth_Lip")
    teeth = bpy.data.objects.get("Mouth_Teeth")
    tongue = bpy.data.objects.get("Mouth_Tongue")
    if lip:
        lip.data.materials.clear()
        lip.data.materials.append(mats["MAT_Satin_Black_MouthOutline"])
    if teeth:
        teeth.data.materials.clear()
        teeth.data.materials.append(mats["MAT_Satin_White_Teeth"])
    if tongue:
        tongue.data.materials.clear()
        tongue.data.materials.append(mats["MAT_Satin_Tongue"])

RIG_MATERIAL_HOOKS.append(_mouth_materials)
# <<< SECTION mouth

# >>> SECTION props
def _ellipse_pts(w, h, n=48):
    """Return n points on an ellipse centered at origin, full width w, height h."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((w / 2 * math.cos(a), h / 2 * math.sin(a)))
    return pts

def _drop_pts(r, tip, n=48):
    """Teardrop pointing UP: circle of radius r with top pulled to point at (0, tip)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s = math.sin(a)
        blend = s ** 3 if s > 0 else 0.0
        x = r * math.cos(a) * (1 - blend)
        y = r * s + (tip - r) * blend
        pts.append((x, y))
    return pts

def _star_pts(r_out, r_in, points=5, per_edge=6):
    """5-point star starting at top (90°), edges subdivided into per_edge segments."""
    base = []
    for i in range(points):
        ang_out = math.radians(90 + i * (360 / points))
        ang_in = ang_out + math.radians(180 / points)
        base.append((r_out * math.cos(ang_out), r_out * math.sin(ang_out)))
        base.append((r_in * math.cos(ang_in), r_in * math.sin(ang_in)))
    # base now has 2*points vertices alternating outer, inner
    total_edges = 2 * points
    pts = []
    for i in range(total_edges):
        start = base[i]
        end = base[(i + 1) % total_edges]
        for j in range(per_edge):
            t = j / per_edge
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            pts.append((x, y))
    return pts

def _heart_pts(size, n=64):
    """Classic parametric heart, point at bottom, scaled to width `size`, centered."""
    pts_raw = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
        pts_raw.append((x, y))
    # compute bounding box
    xs = [p[0] for p in pts_raw]
    ys = [p[1] for p in pts_raw]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width_raw = max_x - min_x
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    scale = size / width_raw
    pts = [((x - center_x) * scale, (y - center_y) * scale) for x, y in pts_raw]
    return pts

def _spiral_rows(r_max, turns, width, n=120):
    """Two rows (inner and outer) of an Archimedean spiral band, radius 0.012 to r_max."""
    inner = []
    outer = []
    for i in range(n + 1):
        t = i / n
        theta = 2 * math.pi * turns * t
        r = 0.012 + (r_max - 0.012) * t
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        # inner edge radius
        r_inner = max(0.001, r - width / 2)
        xi = r_inner * math.cos(theta)
        yi = r_inner * math.sin(theta)
        # outer edge radius
        r_outer = r + width / 2
        xo = r_outer * math.cos(theta)
        yo = r_outer * math.sin(theta)
        inner.append((xi, yi))
        outer.append((xo, yo))
    return [inner, outer]

def build_props():
    new_objects = []
    # Blush
    for side in ("Left", "Right"):
        cx = FACE_X + (0.235 if side == "Left" else -0.235)
        cz = MOUTH_TOP - 0.02
        obj = outline_patch(f"Blush_{side}", _ellipse_pts(0.10, 0.05), cx, cz, 2, None)
        drive_hidden(obj, "blush <= 0.5", ["blush"])
        new_objects.append(obj)
    # Sweat drop
    cx = FACE_X + 0.33
    cz = hoop_z(0.29) + 0.05
    obj = outline_patch("Prop_Sweat", _drop_pts(0.028, 0.075), cx, cz, 3, None, subsurf=False)
    drive_hidden(obj, "prop_sweat <= 0.5", ["prop_sweat"])
    new_objects.append(obj)
    # Tears
    for side in ("Left", "Right"):
        outer = 1 if side == "Left" else -1
        cx = eye_x(side) + outer * 0.06
        cz = EYE_Z - 0.13
        # stream rows
        rows = []
        for offset in (-0.016, 0.0, 0.016):
            row = []
            for i in range(16):
                v = -0.13 * (i / 15)
                u_base = outer * 0.03 + 0.006 * math.sin(v * 20)
                row.append((u_base + offset, v))
            rows.append(row)
        stream = strip_patch(f"Prop_Tear_{side}", rows, cx, cz, 3, None)
        drive_hidden(stream, "prop_tears <= 0.5", ["prop_tears"])
        new_objects.append(stream)
        # drop at end
        drop_cx = cx + outer * 0.03  # under the stream, which runs at u = outer*0.03
        drop_cz = cz - 0.15
        drop = outline_patch(f"Prop_TearDrop_{side}", _drop_pts(0.022, 0.05),
                              drop_cx, drop_cz, 3, None, subsurf=False)
        drive_hidden(drop, "prop_tears <= 0.5", ["prop_tears"])
        new_objects.append(drop)
    # Stars and hearts and dizzy per eye
    for side in ("Left", "Right"):
        cx = eye_x(side)
        cz = EYE_Z
        star = outline_patch(f"Prop_Star_{side}", _star_pts(0.105, 0.045), cx, cz, 3, None, subsurf=False)  # keep the points sharp
        drive_hidden(star, "prop_stars <= 0.5", ["prop_stars"])
        new_objects.append(star)
        heart = outline_patch(f"Prop_Heart_{side}", _heart_pts(0.2), cx, cz, 3, None, subsurf=False)
        drive_hidden(heart, "prop_hearts <= 0.5", ["prop_hearts"])
        new_objects.append(heart)
        dizzy = strip_patch(f"Prop_Dizzy_{side}", _spiral_rows(0.075, 2.5, 0.014),
                            cx, cz, 3, None)
        drive_hidden(dizzy, "prop_dizzy <= 0.5", ["prop_dizzy"])
        new_objects.append(dizzy)
    return new_objects

def _props_materials(lookdev, mats):
    """Assign materials to all prop objects, creating them if necessary."""
    def get_mat(name, hex, angle, aniso=0.3):
        mat = mats.get(name)
        if mat is None:
            mat = lookdev.create_satin(name, hex, angle, aniso=aniso)
            mats[name] = mat
        return mat

    mapping = {
        "Blush_Left": ("MAT_Satin_Blush", "#F07C9A", 30),
        "Blush_Right": ("MAT_Satin_Blush", "#F07C9A", 30),
        "Prop_Sweat": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Tear_Left": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Tear_Right": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_TearDrop_Left": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_TearDrop_Right": ("MAT_Satin_Water", "#A8DDF5", 80),
        "Prop_Star_Left": ("MAT_Satin_Star", "#FFC93C", 45),
        "Prop_Star_Right": ("MAT_Satin_Star", "#FFC93C", 45),
        "Prop_Heart_Left": ("MAT_Satin_Heart", "#E2324F", 45),
        "Prop_Heart_Right": ("MAT_Satin_Heart", "#E2324F", 45),
        "Prop_Dizzy_Left": ("MAT_Satin_Black", None, None),
        "Prop_Dizzy_Right": ("MAT_Satin_Black", None, None),
    }
    for obj_name, (mat_name, hex, angle) in mapping.items():
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            continue
        if mat_name == "MAT_Satin_Black":
            mat = mats.get("MAT_Satin_Black")
            if mat is None:
                # Should have been created by lookdev; fallback
                mat = lookdev.create_satin("MAT_Satin_Black", "#000000", 0, aniso=0.3)
                mats["MAT_Satin_Black"] = mat
        else:
            mat = get_mat(mat_name, hex, angle)
        obj.data.materials.clear()
        obj.data.materials.append(mat)

RIG_MATERIAL_HOOKS.append(_props_materials)
# <<< SECTION props

PRESETS = {}  # filled by the presets section: name -> {control: value}

# >>> SECTION presets
# Expression presets (authored in review): Face_Ctrl values; unlisted controls stay at default.
PRESETS.update({
    "Happy": dict(m_big_smile=0.7, m_teeth=0.3, eye_wide=0.1, brow_raise_L=0.3, brow_raise_R=0.3, cheek_puff=0.2),
    "Big laugh": dict(m_laugh=1.0, m_teeth=0.6, happy_L=1, happy_R=1, brow_raise_L=0.5, brow_raise_R=0.5, cheek_puff=0.4),
    "Wink": dict(blink_L=1.0, m_smirk_L=0.8, brow_raise_R=0.4, look_x=0.4),
    "Grateful": dict(closed_smile=1, m_small_smile=1.0, brow_sad=0.4, blush=1, cheek_puff=0.3),
    "Excited": dict(prop_stars=1, m_laugh=0.8, m_teeth=0.5, brow_raise_L=0.7, brow_raise_R=0.7),
    "Love": dict(prop_hearts=1, m_big_smile=0.8, blush=1, brow_raise_L=0.3, brow_raise_R=0.3),
    "Proud": dict(closed_smile=1, m_smirk_L=0.7, brow_raise_L=0.3, brow_raise_R=0.3, cheek_puff=0.2),
    "Surprised": dict(eye_wide=1.0, pupil_size=-0.4, brow_raise_L=1.0, brow_raise_R=1.0, m_O=0.8),
    "Shocked": dict(eye_wide=1.0, pupil_size=-1.0, brow_raise_L=1.0, brow_raise_R=1.0, m_shout=1.0, m_teeth=0.3),
    "Thinking": dict(look_x=-1.0, look_y=1.0, brow_raise_L=0.9, brow_lower=0.3, m_smirk_R=0.6, m_flat=0.3),
    "Confused": dict(prop_dizzy=1, brow_raise_L=0.8, brow_sad=0.3, m_smirk_R=0.5, m_O=0.3),
    "Shy": dict(blush=1, look_x=-0.8, look_y=-0.6, pupil_size=0.3, brow_sad=0.4, m_small_smile=0.8),
    "Embarrassed": dict(prop_sweat=1, blush=0.6, m_big_smile=0.4, m_teeth=1.0, brow_sad=0.6, squint_L=0.2, squint_R=0.2),
    "Worried": dict(brow_sad=1.0, m_frown=0.6, eye_wide=0.3, look_x=0.5, pupil_size=-0.3),
    "Sad": dict(brow_sad=1.0, m_frown=1.0, look_y=-1.0, blink_L=0.3, blink_R=0.3, pupil_size=0.4),
    "Crying": dict(prop_tears=1, brow_sad=1.0, squint_L=0.8, squint_R=0.8, m_shout=0.6, look_y=-0.5),
    "Annoyed": dict(blink_L=0.45, blink_R=0.45, brow_angry=0.5, m_flat=1.0, look_x=0.7),
    "Determined": dict(brow_angry=0.9, squint_L=0.4, squint_R=0.4, m_smirk_L=0.5, m_flat=0.5, cheek_puff=0.1),
    "Sleepy": dict(blink_L=0.7, blink_R=0.7, brow_sad=0.3, m_pout=0.6, look_y=-0.3),
    "Calm": dict(closed_smile=1, m_small_smile=0.7),
})
# <<< SECTION presets


# ----------------------------------------------------------------------------
# Presets, look-dev, rendering
# ----------------------------------------------------------------------------
def apply_preset(name):
    ctrl = bpy.data.objects[CTRL_NAME]
    for k, (default, _lo, _hi) in CONTROLS.items():
        ctrl[k] = float(default)
    for k, v in PRESETS[name].items():
        if k not in CONTROLS:
            raise KeyError(f"preset {name}: unknown control {k}")
        ctrl[k] = float(v)
    ctrl.update_tag()
    bpy.context.view_layer.update()


def load_lookdev_module(script_dir):
    spec = importlib.util.spec_from_file_location("lookdev", os.path.join(script_dir, "03_materials.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("project_root", nargs="?", default=None)
    ap.add_argument("--presets", default="")
    ap.add_argument("--res", type=int, default=800)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-fur", action="store_true")
    args = ap.parse_args(argv)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(args.project_root or os.path.dirname(script_dir))
    render_dir = os.path.join(root, "renders")
    lookdev = load_lookdev_module(script_dir)

    # 1. rig (shape keys, drivers, props) on the bare model
    make_controls()
    built = {}
    for name in ("build_eyes", "build_mouth", "build_props"):
        fn = globals().get(name)
        if fn is not None:
            built[name] = fn
    # sections create their own materials later; first build geometry with mats=None
    pending_mats = []
    for name, fn in built.items():
        t = time.perf_counter()
        pending_mats.extend(fn() or [])
        print(f"[04] {name} {time.perf_counter() - t:.1f}s")

    # 2. look-dev (materials, studio, fur, render settings)
    ld_args = argparse.Namespace(samples=args.samples, res=args.res, no_fur=args.no_fur,
                                 views="face", project_root=root)
    mats = lookdev.apply_lookdev(ld_args)
    # 3. materials for rig objects + the mouth recess Boolean (after fur so hair ignores the cut)
    for fn_name in ("assign_rig_materials", "add_mouth_recess"):
        fn = globals().get(fn_name)
        if fn is not None:
            fn(lookdev, mats)

    bpy.context.scene.render.use_stamp = False
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(root, "blend", "mascot_face.blend"))
    print("[04] saved blend/mascot_face.blend")
    if args.no_render:
        return

    lookdev.set_camera_view("face")
    # tighter framing than the look-dev face view: brows to mouth, logo cropped
    cz = (EYE_Z + MOUTH_TOP) / 2.0 + 0.04
    bpy.data.objects["Look_Target"].location = (FACE_X, 0.0, cz)
    cam = bpy.data.objects["Camera"]
    cam.location = (FACE_X + 0.12, -1.95, cz + 0.04)
    cam.data.lens = 72
    names = [n for n in (args.presets.split(",") if args.presets else PRESETS.keys()) if n]
    done = []
    t_all = time.perf_counter()
    for name in names:
        apply_preset(name)
        out = os.path.join(render_dir, f"expr_{name.replace(' ', '_')}.png")
        bpy.context.scene.render.filepath = out
        t = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        print(f"[04] expr {name} {time.perf_counter() - t:.1f}s")
        done.append((out, name))
    print(f"[04] expressions total {time.perf_counter() - t_all:.1f}s")


if __name__ == "__main__":
    main()
