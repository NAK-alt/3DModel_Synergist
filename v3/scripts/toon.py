"""2D cartoon version of the mascot: flat cel colours and ink outlines, drawn from the v2 character.
MODE env: hero, expr, stickers (comma list). Uses the v2 scripts without changing them."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT2D = os.path.join(os.path.dirname(HERE), "2d")
sys.path.insert(0, HERE)
import bpy

import m_build
import m_face
import m_pose
import m_props
import m_scene
from m_util import hex_rgb
from stickers_data import STICKERS

INK = "#0A1030"
PALETTE = {  # material name -> (base, shadow)
    "M_Fleece_Blue": ("#1B4FD6", "#1238A6"),
    "M_Fleece_Navy": ("#1B2242", "#10152E"),
    "M_Fleece_White": ("#FFFFFF", "#C8D4EE"),
    "M_Felt_Nose": ("#0A1030", "#0A1030"),
    "M_Thread_White": ("#FFFFFF", "#FFFFFF"),
    "M_Thread_Black": ("#0A1030", "#0A1030"),
    "M_Thread_Mouth": ("#4A4A55", "#4A4A55"),
    "M_Thread_Tongue": ("#FFFFFF", "#FFFFFF"),
    "M_Thread_Edge": ("#0A1030", "#0A1030"),
    "M_Thread_Blush": ("#FF7FA8", "#FF7FA8"),
    "M_Thread_Heart": ("#FF2E4D", "#FF2E4D"),
    "M_Thread_Star": ("#FFD23F", "#FFD23F"),
    "M_Thread_Tear": ("#8FD6FF", "#8FD6FF"),
}


def shade(c, f):
    return tuple(x * f for x in c[:3]) + (1,)


def toon(m, base, shadow, alpha=1.0):
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial")
    dif = N("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = N("ShaderNodeShaderToRGB")
    L(dif.outputs["BSDF"], s2r.inputs["Shader"])
    ramp = N("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = shadow
    ramp.color_ramp.elements[1].position = 0.30
    ramp.color_ramp.elements[1].color = base
    L(s2r.outputs["Color"], ramp.inputs["Fac"])
    em = N("ShaderNodeEmission")
    L(ramp.outputs["Color"], em.inputs["Color"])
    if alpha < 1.0:
        tr = N("ShaderNodeBsdfTransparent")
        mix = N("ShaderNodeMixShader")
        mix.inputs["Fac"].default_value = alpha
        L(tr.outputs["BSDF"], mix.inputs[1])
        L(em.outputs["Emission"], mix.inputs[2])
        L(mix.outputs["Shader"], out.inputs["Surface"])
    else:
        L(em.outputs["Emission"], out.inputs["Surface"])


def logo_flat(m):
    nt = m.node_tree
    img = next(n.image for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "color" in n.image.name)
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial")
    tex = N("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "CLIP"
    em = N("ShaderNodeEmission")
    L(tex.outputs["Color"], em.inputs["Color"])
    tr = N("ShaderNodeBsdfTransparent")
    mix = N("ShaderNodeMixShader")
    L(tex.outputs["Alpha"], mix.inputs["Fac"])
    L(tr.outputs["BSDF"], mix.inputs[1])
    L(em.outputs["Emission"], mix.inputs[2])
    L(mix.outputs["Shader"], out.inputs["Surface"])


def restyle():
    for m in bpy.data.materials:
        if m.name in PALETTE:
            b, s = PALETTE[m.name]
            toon(m, hex_rgb(b), hex_rgb(s))
        elif m.name == "M_Logo":
            logo_flat(m)
        elif m.name.startswith("P_") and not m.get("toon"):
            col = tuple(m.diffuse_color)
            a = m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value if "Principled BSDF" in m.node_tree.nodes else 1.0
            toon(m, col, shade(col, 0.72), alpha=a)
            m["toon"] = True


def setup(res, face_obj):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except Exception:
            continue
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    try:
        sc.eevee.taa_render_samples = 64
    except Exception:
        pass
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Strength"].default_value = 0.0
    sun = bpy.data.lights.new("ToonSun", "SUN")
    sun.energy = 3.14
    sun.angle = 0.01
    sun.use_shadow = False
    so = bpy.data.objects.new("ToonSun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(58), math.radians(-8), math.radians(-38))
    # ink lines
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    vl = bpy.context.view_layer
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(150)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    ink = bpy.data.collections.new("Ink")
    sc.collection.children.link(ink)
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob is not face_obj and ob.name != "Mascot_Logo":
            ink.objects.link(ob)
    for name, thick, kinds in (("outline", res * 0.0062, dict(select_silhouette=True, select_border=True, select_external_contour=True)),
                               ("detail", res * 0.0036, dict(select_crease=True))):
        ls = fs.linesets.new(name)
        for k in ("select_silhouette", "select_border", "select_crease", "select_external_contour", "select_contour",
                  "select_edge_mark", "select_material_boundary", "select_suggestive_contour", "select_ridge_valley"):
            setattr(ls, k, bool(kinds.get(k, False)))
        ls.select_by_collection = True
        ls.collection = ink
        ls.linestyle.color = hex_rgb(INK)[:3]
        ls.linestyle.thickness = thick
        ls.linestyle.caps = "ROUND"
    return ink


def hide_eye_halo(face):
    """The plush has a white ring outside the black one; the cartoon uses a single ink ring."""
    me = face.data
    off = 0
    hide = []
    for lay in m_face.layers(m_face.BASE):
        n = len(lay["pts"])
        if lay["name"].startswith("eye0"):
            hide.append((off, off + n))
        off += n
    for poly in me.polygons:
        v = poly.vertices[0]
        if any(a <= v < b for a, b in hide):
            poly.hide = True
    idx = [i for i, p in enumerate(me.polygons) if p.hide]
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in idx], context="FACES_ONLY")
    bm.to_mesh(me)
    bm.free()


modes = os.environ.get("MODE", "hero").split(",")
res = int(os.environ.get("RES", "1600"))
import m_util
m_util.RIBS[:] = []  # the soft ribs only make the cel shadow edge jagged in 2D
objs = m_build.build(shape_keys=False)
hide_eye_halo(objs["face"])
restyle()
ink = setup(res, objs["face"])
rig, face = objs["rig"], objs["face"]


def out(*p):
    path = os.path.join(ROOT2D, *p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


if "hero" in modes:
    m_pose.apply_pose(rig, m_pose.HERO)
    for name, azim, elev in (("front", 0, 10), ("threequarter", -32, 10)):
        m_scene.camera(target=(0, 0, 0.92), dist=7.6, elev=elev, azim=azim)
        m_scene.render(out("renders", f"mascot2d_{name}.png"))

if "expr" in modes:
    m_pose.apply_pose(rig, m_pose.HERO)
    m_scene.camera(target=(0, 0, 1.40), dist=2.75, elev=5)
    for name in m_face.EXPRESSIONS:
        m_build.set_face(face, name)
        m_scene.render(out("renders", "expressions", "expr_" + name.replace(" ", "_") + ".png"))
    m_build.set_face(face, "Happy")

if "stickers" in modes:
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    for st in STICKERS:
        if only and not any(st["slug"].startswith(o) for o in only):
            continue
        for ob in [o for o in ink.objects if o.name.startswith("box") or o.name.startswith("lathe")]:
            pass
        m_props.clear()
        m_pose.apply_pose(rig, st["pose"])
        m_build.set_face(face, st["expr"])
        D = m_pose.compute(st["pose"])["body"]
        for kind, loc, rot, scale in st.get("props", []):
            root = m_props.add(kind, (loc[0], loc[1], loc[2] + 0.12), rot, scale, body_D=D)
            for ch in root.children:
                ink.objects.link(ch)
        restyle()
        cam = st.get("cam", {})
        m_scene.camera(target=(0, -0.1, 0.98), dist=6.8, elev=cam.get("elev", 7), azim=cam.get("azim", 0))
        m_scene.render(out("exports", "stickers", "raw", st["slug"] + ".png"))
