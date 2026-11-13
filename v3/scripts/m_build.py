"""Synergist mascot v2: builds the whole character (meshes, materials, armature, face keys)."""
import math
import os

import bpy
from mathutils import Matrix, Vector

import m_face
from m_util import (ANKLE_Z, ARM_L, ARM_N, ARM_R, C_BLUE, C_NAVY, C_WHITE, HAND_S, HI, HIP_X, HIP_Z,
                    HOOPS, LEG_N, LEG_R, MB, R0, RIBS, RIM_R, ROOT, Z_BOT, Z_TOP, body_r, capsule_profile,
                    frame, hex_rgb, revolve, smoothstep, sphere_profile, surf, torus_profile)

SHOULDER_X, SHOULDER_Y, SHOULDER_Z = 0.47, -0.02, 0.96
FINGERS = [  # name, base (x, y) in hand space, fan angle, length, radius
    ("thumb", (0.076, 0.050), 62.0, 0.104, 0.041),
    ("index", (0.052, 0.135), 15.0, 0.114, 0.041),
    ("middle", (-0.010, 0.146), -5.0, 0.120, 0.042),
    ("pinky", (-0.070, 0.115), -32.0, 0.106, 0.039),
]
LOGO_ZC, LOGO_W, LOGO_XC = 1.012, 0.93, -0.012


# ---------------------------------------------------------------- materials
def _mat(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def _set(bsdf, **kw):
    for k, v in kw.items():
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = v


def fleece(name, hexcol, pile=1.0, sheen=0.35):
    m, nt, bsdf = _mat(name)
    N, Lk = nt.nodes.new, nt.links.new
    base = hex_rgb(hexcol)
    tc = N("ShaderNodeTexCoord")
    warp = N("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 26.0
    warp.inputs["Detail"].default_value = 2.0
    add = N("ShaderNodeVectorMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = (0.06, 0.06, 0.06)
    Lk(warp.outputs["Color"], add.inputs[0])
    Lk(tc.outputs["Object"], add.inputs[2])
    vor = N("ShaderNodeTexVoronoi")
    vor.feature = "SMOOTH_F1"
    vor.inputs["Scale"].default_value = 125.0 / pile
    Lk(add.outputs[0], vor.inputs["Vector"])
    fine = N("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 900.0 / pile
    fine.inputs["Detail"].default_value = 3.0
    Lk(tc.outputs["Object"], fine.inputs["Vector"])
    mix = N("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.55
    Lk(fine.outputs["Fac"], mix.inputs[0])
    Lk(vor.outputs["Distance"], mix.inputs[2])
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.0040 * pile
    Lk(mix.outputs[0], bump.inputs["Height"])
    Lk(bump.outputs["Normal"], bsdf.inputs["Normal"])
    # pile direction patches: slightly lighter / darker fleece
    var = N("ShaderNodeTexNoise")
    var.inputs["Scale"].default_value = 105.0 / pile
    var.inputs["Detail"].default_value = 4.0
    Lk(add.outputs[0], var.inputs["Vector"])
    ramp = N("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.3
    ramp.inputs["From Max"].default_value = 0.7
    Lk(var.outputs["Fac"], ramp.inputs["Value"])
    col = N("ShaderNodeMix")
    col.data_type = "RGBA"
    col.inputs["A"].default_value = tuple(c * 0.74 for c in base[:3]) + (1,)
    col.inputs["B"].default_value = tuple(min(1.0, c * 1.16 + 0.001) for c in base[:3]) + (1,)
    Lk(ramp.outputs["Result"], col.inputs["Factor"])
    Lk(col.outputs["Result"], bsdf.inputs["Base Color"])
    tint = tuple(min(1.0, 0.25 + 2.2 * c) for c in base[:3]) + (1,)
    _set(bsdf, Roughness=0.92, **{"Sheen Weight": sheen, "Sheen Roughness": 0.45, "Sheen Tint": tint,
                                  "Specular IOR Level": 0.12})
    m.diffuse_color = base
    m["kind"] = "fleece"
    m["hex"] = hexcol
    return m


def thread(name, hexcol, rough=0.5, angle=0.0, scale=340.0, strength=0.55, metallic=0.0, emit=0.0, sheen=0.3):
    m, nt, bsdf = _mat(name)
    N, Lk = nt.nodes.new, nt.links.new
    base = hex_rgb(hexcol)
    uv = N("ShaderNodeUVMap")
    mp = N("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, angle)
    Lk(uv.outputs["UV"], mp.inputs["Vector"])
    wave = N("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 1.2
    wave.inputs["Detail"].default_value = 1.0
    wave.inputs["Detail Scale"].default_value = 3.0
    Lk(mp.outputs["Vector"], wave.inputs["Vector"])
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.0018
    Lk(wave.outputs["Fac"], bump.inputs["Height"])
    Lk(bump.outputs["Normal"], bsdf.inputs["Normal"])
    _set(bsdf, Roughness=rough, Metallic=metallic, **{"Base Color": base, "Sheen Weight": sheen,
                                                       "Sheen Roughness": 0.4, "Specular IOR Level": 0.35})
    if emit:
        _set(bsdf, **{"Emission Color": base, "Emission Strength": emit})
    m.diffuse_color = base
    m["kind"] = "thread"
    m["hex"] = hexcol
    return m


def logo_material():
    m, nt, bsdf = _mat("M_Logo")
    N, Lk = nt.nodes.new, nt.links.new
    col = N("ShaderNodeTexImage")
    col.image = bpy.data.images.load(os.path.join(ROOT, "textures", "logo_color.png"), check_existing=True)
    col.extension = "CLIP"
    dat = N("ShaderNodeTexImage")
    dat.image = bpy.data.images.load(os.path.join(ROOT, "textures", "logo_data.png"), check_existing=True)
    dat.image.colorspace_settings.name = "Non-Color"
    dat.extension = "CLIP"
    sep = N("ShaderNodeSeparateColor")
    Lk(dat.outputs["Color"], sep.inputs["Color"])
    Lk(col.outputs["Color"], bsdf.inputs["Base Color"])
    Lk(col.outputs["Alpha"], bsdf.inputs["Alpha"])
    met = N("ShaderNodeMath")
    met.operation = "MULTIPLY"
    met.inputs[1].default_value = 0.25
    Lk(sep.outputs["Green"], met.inputs[0])
    Lk(met.outputs[0], bsdf.inputs["Metallic"])
    uv = N("ShaderNodeUVMap")
    wave = N("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 260.0
    wave.inputs["Distortion"].default_value = 1.0
    mp = N("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, 0.5)
    mp.inputs["Scale"].default_value = (1.0, 0.36, 1.0)
    Lk(uv.outputs["UV"], mp.inputs["Vector"])
    Lk(mp.outputs["Vector"], wave.inputs["Vector"])
    hsum = N("ShaderNodeMath")
    hsum.operation = "MULTIPLY_ADD"
    hsum.inputs[1].default_value = 0.10
    Lk(wave.outputs["Fac"], hsum.inputs[0])
    Lk(sep.outputs["Red"], hsum.inputs[2])
    bump = N("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 0.006
    Lk(hsum.outputs[0], bump.inputs["Height"])
    Lk(bump.outputs["Normal"], bsdf.inputs["Normal"])
    _set(bsdf, Roughness=0.42, **{"Sheen Weight": 0.3, "Specular IOR Level": 0.4})
    m["kind"] = "logo"
    return m


def make_materials():
    M = {}
    M["blue"] = fleece("M_Fleece_Blue", C_BLUE)
    M["navy"] = fleece("M_Fleece_Navy", C_NAVY, sheen=0.5)
    M["glove"] = fleece("M_Fleece_White", C_WHITE, pile=0.9, sheen=0.4)
    M["white"] = thread("M_Thread_White", "#F6F4EF", angle=0.3)
    M["black"] = thread("M_Thread_Black", "#050508", rough=0.6, angle=1.45, sheen=0.06)
    M["mouth"] = thread("M_Thread_Mouth", "#45454C", angle=0.0)
    M["tongue"] = thread("M_Thread_Tongue", "#F2F0EC", angle=1.2)
    M["edge"] = thread("M_Thread_Edge", "#E9E6E2", angle=1.0)
    M["blush"] = thread("M_Thread_Blush", "#F06C92", angle=0.0, strength=0.3)
    M["heart"] = thread("M_Thread_Heart", "#E8243C", angle=0.8)
    M["star"] = thread("M_Thread_Star", "#FFC62E", angle=0.8)
    M["tear"] = thread("M_Thread_Tear", "#8FD6FF", angle=1.57, rough=0.3)
    M["nose"] = fleece("M_Felt_Nose", "#08080B", pile=0.6, sheen=0.6)
    M["logo"] = logo_material()
    return M


# ---------------------------------------------------------------- body
def body_profile():
    rb = 0.034
    z_side0 = Z_BOT + rb
    a0 = math.radians(-55)
    zc = Z_TOP - RIM_R
    z_side1 = zc + RIM_R * math.sin(a0)
    rc = body_r(z_side1) - RIM_R * math.cos(a0)
    pts = [(0.0, Z_BOT - 0.004)]
    r_in = body_r(z_side0) - rb
    n_in = 10 if HI else 3
    for i in range(1, n_in + 1):
        r = r_in * i / n_in
        pts.append((r, Z_BOT - 0.004 * (1 - (r / r_in) ** 2)))
    n_c = 10 if HI else 4
    for i in range(1, n_c + 1):
        a = -math.pi / 2 + (math.pi / 2) * i / n_c
        pts.append((r_in + rb * math.cos(a), z_side0 + rb * math.sin(a)))
    if HI:
        n = int((z_side1 - z_side0) / 0.003)
        zs = [z_side0 + (z_side1 - z_side0) * i / n for i in range(1, n)]
    else:
        zs = set()
        for zf, amp, w in HOOPS + RIBS:
            for k in (-1.0, -0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9, 1.0):
                zs.add(round(zf + k * w, 4))
        z = z_side0
        while z < z_side1:
            zs.add(round(z, 4))
            z += 0.05
        zs = sorted(v for v in zs if z_side0 + 0.004 < v < z_side1 - 0.004)
    for z in zs:
        pts.append((body_r(z), z))
    n_r = 40 if HI else 14
    a1 = math.radians(212)
    for i in range(n_r + 1):
        a = a0 + (a1 - a0) * i / n_r
        pts.append((rc + RIM_R * math.cos(a), zc + RIM_R * math.sin(a)))
    r_lid = rc + RIM_R * math.cos(a1) - 0.014
    z_lid = Z_TOP - 0.050
    n_l = 14 if HI else 4
    for i in range(n_l):
        r = r_lid * (1 - i / n_l)
        pts.append((r, z_lid + 0.012 * (1 - (r / r_lid) ** 2)))
    pts.append((0.0, z_lid + 0.012))
    return pts


# ---------------------------------------------------------------- hands / shoes
def hand_matrix(sg):
    w = Vector((sg * (SHOULDER_X + ARM_L), SHOULDER_Y, SHOULDER_Z))
    return frame(w, x=(0, 0, HAND_S), y=(sg * HAND_S, 0, 0), z=(0, HAND_S, 0))


def finger_frame(base, ang):
    a = math.radians(ang)
    return frame((base[0], base[1], 0.0), x=(math.cos(a), -math.sin(a), 0), y=(0, 0, -1), z=(math.sin(a), math.cos(a), 0))


def add_hand(mb, sg, S):
    Mh = hand_matrix(sg)
    flip = sg < 0
    segs = 24 if HI else 12
    hw = {f"hand.{S}": 1.0}
    v, f, fuv = revolve(sphere_profile(16 if HI else 8), segs)
    xf = Mh @ Matrix.Translation((0.0, 0.085, 0.0)) @ Matrix.Diagonal((0.098, 0.095, 0.058, 1.0))
    mb.add(v, f, fuv=fuv, mat=1, weights=hw, xf=xf, flip=flip)
    v, f, fuv = revolve(torus_profile(0.068, 0.040, 16 if HI else 8), segs, closed=True)
    xf = Mh @ Matrix.Translation((0.0, -0.004, 0.0)) @ Matrix.Rotation(-math.pi / 2, 4, "X")
    mb.add(v, f, fuv=fuv, mat=1, weights=hw, xf=xf, flip=flip)
    fs = 18 if HI else 10
    for name, base, ang, ln, r in FINGERS:
        prof = capsule_profile(ln, r, r0=r * 0.92, rings=8 if HI else 4, cap=7 if HI else 4)
        v, f, fuv = revolve(prof, fs)
        ws = []
        for p in v:
            t = smoothstep(0.40, 0.62, p[2] / ln)
            ws.append({f"{name}1.{S}": 1 - t, f"{name}2.{S}": t})
        mb.add(v, f, fuv=fuv, mat=1, weights=ws, xf=Mh @ finger_frame(base, ang), flip=flip)


def shoe_point(p):
    x, y, z = p
    yy = y * (0.245 if y > 0 else 0.165) + 0.062
    zz = z * 0.115 * (1 + 0.20 * smoothstep(-0.3, 1.0, y)) - 0.080
    if zz < -0.165:
        zz = -0.165 - (-0.165 - zz) * 0.3
    xx = x * 0.160 * (1 + 0.08 * smoothstep(-0.2, 0.8, y))
    return (xx, yy, zz)


def add_shoe(mb, sg, S):
    xf = Matrix.Translation((sg * HIP_X, 0.0, ANKLE_Z)) @ Matrix.Rotation(math.pi, 4, "Z")
    w = {f"foot.{S}": 1.0}
    segs = 32 if HI else 14
    v, f, fuv = revolve(sphere_profile(20 if HI else 10), segs)
    mb.add([shoe_point(p) for p in v], f, fuv=fuv, mat=1, weights=w, xf=xf)
    v, f, fuv = revolve(torus_profile(0.068, 0.037, 14 if HI else 8), 24 if HI else 12, closed=True)
    mb.add(v, f, fuv=fuv, mat=1, weights=w, xf=xf @ Matrix.Translation((0.0, 0.0, 0.046)))
    if HI:  # piped sole seam
        ring = []
        for k in range(64):
            a = 2 * math.pi * k / 64
            ring.append(shoe_point((math.cos(a) * 0.80, math.sin(a) * 0.90, -0.42)))
        vv, ff = [], []
        for k, c in enumerate(ring):
            c = Vector(c)
            out = Vector((c.x, c.y - 0.06, 0)).normalized()
            for q in range(8):
                b = 2 * math.pi * q / 8
                vv.append(c + out * (0.002 + 0.004 * math.cos(b)) + Vector((0, 0, 0.004 * math.sin(b))))
        for k in range(64):
            for q in range(8):
                a, b = k * 8 + q, k * 8 + (q + 1) % 8
                c, d = ((k + 1) % 64) * 8 + (q + 1) % 8, ((k + 1) % 64) * 8 + q
                ff.append((a, d, c, b))
        mb.add(vv, ff, mat=1, weights=w, xf=xf)


def chain_weights(verts, length, n, prefix, S):
    ws = []
    for p in verts:
        u = min(1.0, max(0.0, p[2] / length)) * n - 0.5
        if u <= 0:
            ws.append({f"{prefix}0.{S}": 1.0})
        elif u >= n - 1:
            ws.append({f"{prefix}{n - 1}.{S}": 1.0})
        else:
            i = int(u)
            ws.append({f"{prefix}{i}.{S}": 1 - (u - i), f"{prefix}{i + 1}.{S}": u - i})
    return ws


def add_arm(mb, sg, S):
    rings, segs = (44, 20) if HI else (14, 10)
    prof = [(ARM_R, -0.03 + (ARM_L + 0.03) * i / rings) for i in range(rings + 1)]
    v, f, fuv = revolve(prof, segs)
    xf = frame((sg * SHOULDER_X, SHOULDER_Y, SHOULDER_Z), x=(0, 0, 1), y=(0, -sg, 0), z=(sg, 0, 0))
    mb.add(v, f, fuv=fuv, mat=0, weights=chain_weights(v, ARM_L, ARM_N, "arm", S), xf=xf)


def add_leg(mb, sg, S):
    rings, segs = (18, 20) if HI else (6, 10)
    ln = HIP_Z - ANKLE_Z
    prof = [(LEG_R, ln * i / rings) for i in range(rings + 1)]
    v, f, fuv = revolve(prof, segs)
    xf = frame((sg * HIP_X, 0.0, HIP_Z), x=(1, 0, 0), y=(0, -1, 0), z=(0, 0, -1))
    mb.add(v, f, fuv=fuv, mat=0, weights=chain_weights(v, ln, LEG_N, "leg", S), xf=xf)


# ---------------------------------------------------------------- armature
def bone_table():
    B = [("root", (0, 0, 0), (0, 0, 0.2), None), ("body", (0, 0, Z_BOT), (0, 0, 0.9), "root")]
    for S, sg in (("L", 1.0), ("R", -1.0)):
        s0 = Vector((sg * SHOULDER_X, SHOULDER_Y, SHOULDER_Z))
        d = Vector((sg, 0, 0))
        par = "body"
        for i in range(ARM_N):
            B.append((f"arm{i}.{S}", s0 + d * ARM_L * i / ARM_N, s0 + d * ARM_L * (i + 1) / ARM_N, par))
            par = f"arm{i}.{S}"
        w = s0 + d * ARM_L
        B.append((f"hand.{S}", w, w + d * 0.10, par))
        Mh = hand_matrix(sg)
        for name, base, ang, ln, r in FINGERS:
            Fm = Mh @ finger_frame(base, ang)
            p0, p1, p2 = Fm @ Vector((0, 0, 0)), Fm @ Vector((0, 0, ln * 0.5)), Fm @ Vector((0, 0, ln))
            B.append((f"{name}1.{S}", p0, p1, f"hand.{S}"))
            B.append((f"{name}2.{S}", p1, p2, f"{name}1.{S}"))
        h = Vector((sg * HIP_X, 0, HIP_Z))
        ln = HIP_Z - ANKLE_Z
        par = "body"
        for i in range(LEG_N):
            B.append((f"leg{i}.{S}", h - Vector((0, 0, ln * i / LEG_N)), h - Vector((0, 0, ln * (i + 1) / LEG_N)), par))
            par = f"leg{i}.{S}"
        a = Vector((sg * HIP_X, 0, ANKLE_Z))
        B.append((f"foot.{S}", a, a + Vector((0, -0.16, 0)), par))
    return B


def make_armature(coll):
    arm = bpy.data.armatures.new("MascotRig")
    ob = bpy.data.objects.new("MascotRig", arm)
    coll.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in bone_table():
        eb = arm.edit_bones.new(name)
        eb.head, eb.tail = Vector(head), Vector(tail)
        if parent:
            eb.parent = arm.edit_bones[parent]
        if name[:3] in ("arm", "leg", "han", "foo"):
            eb.inherit_scale = "NONE"
        eb.use_deform = name != "root"
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "STICK"
    ob.show_in_front = True
    return ob


# ---------------------------------------------------------------- assembly
def build(shape_keys=True):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.cameras, bpy.data.lights):
        for d in list(blk):
            blk.remove(d)
    coll = bpy.data.collections.new("Mascot")
    bpy.context.scene.collection.children.link(coll)
    M = make_materials()
    rig = make_armature(coll)
    objs = {}

    # barrel
    mb = MB()
    v, f, fuv = revolve(body_profile(), 192 if HI else 72)
    mb.add(v, f, fuv=fuv, weights={"body": 1.0})
    objs["body"] = mb.build("Mascot_Body", [M["blue"]], coll)

    # limbs
    mb = MB()
    for S, sg in (("L", 1.0), ("R", -1.0)):
        add_arm(mb, sg, S)
        add_leg(mb, sg, S)
        add_hand(mb, sg, S)
        add_shoe(mb, sg, S)
    objs["limbs"] = mb.build("Mascot_Limbs", [M["navy"], M["glove"]], coll)

    # face
    names = ["white", "black", "mouth", "tongue", "blush", "heart", "star", "tear", "nose", "edge"]
    faces, uvs, mats = m_face.topology()
    mb = MB()
    base = m_face.coords(m_face.BASE)
    mb.add(base, faces, uvs=uvs, weights={"body": 1.0})
    mb.fm = [names.index(m) for m in mats]
    v, f, fuv = revolve(sphere_profile(14 if HI else 8), 24 if HI else 12)
    nz = 1.406
    xf = Matrix.Translation(surf(-0.055, nz, 0.018)) @ Matrix.Diagonal((0.043, 0.034, 0.033, 1.0))
    mb.add(v, f, fuv=fuv, mat=names.index("nose"), weights={"body": 1.0}, xf=xf)
    face = mb.build("Mascot_Face", [M[n] for n in names], coll)
    face["n_param_verts"] = len(base)
    objs["face"] = face
    if shape_keys:
        face.shape_key_add(name="Basis", from_mix=False)
        nose = [tuple(p) for p in mb.v[len(base):]]
        for key in m_face.KEYS:
            kb = face.shape_key_add(name=key, from_mix=False)
            co = [tuple(p) for p in m_face.coords(m_face.params({key: 1.0}))] + nose
            kb.data.foreach_set("co", [c for p in co for c in p])
            kb.slider_min, kb.slider_max = 0.0, 1.5
            kb.value = 0.0

    # logo patch
    mb = MB()
    nx, ny = (260, 90) if HI else (220, 76)
    hh = LOGO_W * (700 / 2048) / 2
    v, uv, f = [], [], []
    for i in range(nx):
        for j in range(ny):
            x = LOGO_XC - LOGO_W / 2 + LOGO_W * i / (nx - 1)
            z = LOGO_ZC - hh + 2 * hh * j / (ny - 1)
            v.append(surf(x, z, 0.0085))
            uv.append((i / (nx - 1), j / (ny - 1)))
    # keep only the cells the artwork covers, so the logo also reads without textures (solid view)
    import numpy as np
    img = bpy.data.images.load(os.path.join(ROOT, "textures", "logo_color.png"), check_existing=True)
    iw, ih = img.size
    px = np.empty(iw * ih * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    alpha = px.reshape(ih, iw, 4)[:, :, 3]
    for i in range(nx - 1):
        x0, x1 = int(i / (nx - 1) * iw), int((i + 1) / (nx - 1) * iw)
        for j in range(ny - 1):
            y0, y1 = int(j / (ny - 1) * ih), int((j + 1) / (ny - 1) * ih)
            if alpha[max(0, y0 - 3):y1 + 4, max(0, x0 - 3):x1 + 4].max() < 0.02:
                continue
            a = i * ny + j
            f.append((a, a + ny, a + ny + 1, a + 1))
    used = sorted({k for q in f for k in q})
    remap = {k: n for n, k in enumerate(used)}
    v, uv = [v[k] for k in used], [uv[k] for k in used]
    f = [tuple(remap[k] for k in q) for q in f]
    mb.add(v, f, uvs=uv, weights={"body": 1.0})
    objs["logo"] = mb.build("Mascot_Logo", [M["logo"]], coll)
    objs["logo"].visible_shadow = False

    for ob in objs.values():
        ob.parent = rig
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
    objs["rig"] = rig
    if HI and os.environ.get("MASCOT_FUR", "0") == "1":
        add_all_fur(objs)
    return objs


def _fur(ob, name, count, length, slot, group=None, children=6):
    mod = ob.modifiers.new(name, "PARTICLE_SYSTEM")
    ps = mod.particle_system
    s = ps.settings
    s.type = "HAIR"
    s.count = count
    s.hair_length = length
    s.emit_from = "FACE"
    s.use_emit_random = True
    s.hair_step = 2
    s.render_step = 2
    s.display_step = 2
    s.child_type = "INTERPOLATED"
    s.rendered_child_count = children
    s.child_percent = 1
    s.child_length = 1.0
    s.roughness_1 = 0.004
    s.roughness_1_size = 0.4
    s.roughness_endpoint = 0.006
    s.roughness_2 = 0.004
    s.brownian_factor = 0.0015
    s.factor_random = 0.0008
    s.length_random = 0.4
    s.material = slot + 1
    s.root_radius = 0.9
    s.tip_radius = 0.35
    s.radius_scale = 0.0009
    if group:
        ps.vertex_group_density = group
    return ps


def add_all_fur(objs):
    """Short fleece pile so silhouettes and shading read as plush (render builds only)."""
    _fur(objs["body"], "Pile", 230000, 0.0030, 0, children=8)
    limbs = objs["limbs"]
    me = limbs.data
    sets = {0: set(), 1: set()}
    for p in me.polygons:
        sets[p.material_index].update(p.vertices)
    for idx, name in ((0, "fur_navy"), (1, "fur_white")):
        vg = limbs.vertex_groups.new(name=name)
        vg.add(sorted(sets[idx] - sets[1 - idx]), 1.0, "REPLACE")
    _fur(limbs, "PileNavy", 40000, 0.0030, 0, "fur_navy", children=8)
    _fur(limbs, "PileWhite", 120000, 0.0042, 1, "fur_white", children=8)


def set_face(face, weights=None):
    """Write an exact expression into the face mesh (use on builds without shape keys)."""
    co = m_face.coords(m_face.params(weights))
    me = face.data
    flat = [0.0] * (len(me.vertices) * 3)
    me.vertices.foreach_get("co", flat)
    for i, p in enumerate(co):
        flat[i * 3:i * 3 + 3] = p[:]
    me.vertices.foreach_set("co", flat)
    me.update()
