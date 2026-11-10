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


def outline_patch(name, pts_uv, cx, cz, layer, mat, subsurf=True):
    """Filled patch from a closed outline [(u, v), ...] around (cx, cz): one n-gon face.
    Works for concave shapes (stars, hearts); Blender tessellates the n-gon."""
    bm = bmesh.new()
    verts = [bm.verts.new((cx + u, front_y(cx + u, cz + v), cz + v)) for u, v in pts_uv]
    bm.faces.new(verts)
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
        angle_angry = inner_sign * -math.radians(18)
        angry_fn = lambda co: xz_move(0, -0.012)(xz_rotate(px, pz, angle_angry)(co))
        add_shape_key(brow, "Angry", angry_fn)
        drive_key(brow, "Angry", "brow_angry", ["brow_angry"])
        # Sad (inner up)
        angle_sad = inner_sign * math.radians(20)
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
# <<< SECTION mouth

# >>> SECTION props
# <<< SECTION props

PRESETS = {}  # filled by the presets section: name -> {control: value}

# >>> SECTION presets
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


def make_sheet(paths_and_labels, out_path, cols=5, cell=400):
    """5x4 labelled grid using Blender's own image API (no PIL inside Blender)."""
    rows = math.ceil(len(paths_and_labels) / cols)
    label_h = 0  # labels are burned in by the stamp option when rendering
    w, h = cols * cell, rows * (cell + label_h)
    sheet = bpy.data.images.new("expressions_sheet", w, h, alpha=False)
    px = [0.16] * (w * h * 4)
    for idx, (path, _label) in enumerate(paths_and_labels):
        img = bpy.data.images.load(path)
        img.scale(cell, cell)
        src = list(img.pixels)
        col, row = idx % cols, rows - 1 - idx // cols
        for y in range(cell):
            dst0 = ((row * cell + y) * w + col * cell) * 4
            src0 = y * cell * 4
            px[dst0:dst0 + cell * 4] = src[src0:src0 + cell * 4]
        bpy.data.images.remove(img)
    sheet.pixels = px
    sheet.filepath_raw = out_path
    sheet.file_format = "PNG"
    sheet.save()


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
