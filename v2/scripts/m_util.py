"""Synergist mascot v2: shared constants and mesh helpers (Blender 5.2, headless)."""
import math
import os

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUALITY = os.environ.get("MASCOT_Q", "render")  # "render" (dense) or "glb" (light)
HI = QUALITY == "render"

# ---------------------------------------------------------------- proportions
R0 = 0.5            # barrel radius
Z_BOT = 0.30        # barrel bottom
Z_TOP = 1.50        # top of the rolled rim
GROUND = 0.0
HOOPS = [(1.050, 0.017, 0.025), (0.612, 0.017, 0.025), (0.357, 0.017, 0.030)]  # z, amp, half width
RIBS = [(1.242, 0.0042, 0.031), (1.182, 0.0042, 0.031), (1.122, 0.0042, 0.031)]
RIM_R = 0.038
ARM_L = 0.45
ARM_R = 0.044
ARM_N = 10
LEG_R = 0.044
LEG_N = 3
HAND_S = 1.05
ANKLE_Z = 0.165
HIP_X = 0.2
HIP_Z = 0.36

# brand colours (sRGB hex)
C_BLUE = "#0A3AA0"
C_NAVY = "#0B0E1C"
C_WHITE = "#DEDBD6"
C_GOLD = "#D5B268"


def hex_rgb(h, alpha=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (lin[0], lin[1], lin[2], alpha)


def body_r(z):
    """Barrel side radius at height z (hoops are piped rolls, ribs are soft waves)."""
    r = R0 + 0.004 * math.sin(math.pi * min(1.0, max(0.0, (z - Z_BOT) / (Z_TOP - Z_BOT))))
    for zc, amp, w in HOOPS:
        t = abs(z - zc) / w
        if t < 1.0:
            r += amp * (1.0 - t * t) ** 0.5
    for zc, amp, w in RIBS:
        t = abs(z - zc) / w
        if t < 1.0:
            r += amp * 0.5 * (1.0 + math.cos(math.pi * t))
    return r


def surf(x, z, h=0.0):
    """Point on the barrel front. x = arc length from the face centre line, z = height."""
    phi = x / R0
    r = body_r(z) + h
    return Vector((r * math.sin(phi), -r * math.cos(phi), z))


# ---------------------------------------------------------------- mesh builder
class MB:
    def __init__(self):
        self.v, self.f, self.fuv, self.fm, self.w = [], [], [], [], []

    def add(self, verts, faces, uvs=None, fuv=None, mat=0, weights=None, xf=None, flip=False):
        base = len(self.v)
        for p in verts:
            p = Vector(p)
            self.v.append(xf @ p if xf is not None else p)
        n = len(verts)
        if weights is None:
            self.w += [None] * n
        elif isinstance(weights, dict):
            self.w += [weights] * n
        else:
            self.w += list(weights)
        for k, f in enumerate(faces):
            if fuv is not None:
                cu = list(fuv[k])
            elif uvs is not None:
                cu = [uvs[i] for i in f]
            else:
                cu = [(0.0, 0.0)] * len(f)
            idx = [base + i for i in f]
            if flip:
                idx.reverse()
                cu.reverse()
            self.f.append(idx)
            self.fuv.append(cu)
            self.fm.append(mat)
        return base, n

    def build(self, name, mats, collection=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        me.update()
        uvl = me.uv_layers.new(name="UVMap")
        flat = []
        for poly in me.polygons:
            cu = self.fuv[poly.index]
            for k in range(poly.loop_total):
                flat.extend(cu[k])
        uvl.data.foreach_set("uv", flat)
        me.polygons.foreach_set("material_index", self.fm)
        for m in mats:
            me.materials.append(m)
        me.shade_smooth()
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        groups = {}
        for i, w in enumerate(self.w):
            if not w:
                continue
            for g, val in w.items():
                if val > 1e-4:
                    groups.setdefault(g, []).append((i, val))
        for g, lst in groups.items():
            vg = ob.vertex_groups.new(name=g)
            for i, val in lst:
                vg.add([i], val, "REPLACE")
        return ob


def revolve(profile, segs, closed=False, a0=math.pi / 2):
    """Revolve (r, z) points about Z. Counter-clockwise profiles give outward normals.
    Returns verts, faces, per-corner uvs (u around, v along the profile)."""
    verts, rows = [], []
    lens = [0.0]
    for i in range(1, len(profile)):
        lens.append(lens[-1] + math.dist(profile[i], profile[i - 1]))
    total = lens[-1] or 1.0
    for (r, z) in profile:
        if r < 1e-6:
            rows.append([len(verts)] * segs)
            verts.append((0.0, 0.0, z))
        else:
            row = []
            for j in range(segs):
                a = a0 + 2 * math.pi * j / segs
                row.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rows.append(row)
    faces, fuv = [], []
    n = len(profile)
    last = n if closed else n - 1
    for i in range(last):
        i2 = (i + 1) % n
        v0, v1 = lens[i] / total, (lens[i + 1] / total if i + 1 < n else 1.0)
        for j in range(segs):
            j2 = (j + 1) % segs
            a, b, c, d = rows[i][j], rows[i][j2], rows[i2][j2], rows[i2][j]
            u0, u1 = j / segs, (j + 1) / segs
            quad = [(a, (u0, v0)), (b, (u1, v0)), (c, (u1, v1)), (d, (u0, v1))]
            seen, f, cu = set(), [], []
            for idx, uv in quad:
                if idx not in seen:
                    seen.add(idx)
                    f.append(idx)
                    cu.append(uv)
            if len(f) >= 3:
                faces.append(f)
                fuv.append(cu)
    return verts, faces, fuv


def capsule_profile(length, r, r0=None, rings=7, cap=7, bulge=0.06):
    """Finger-like profile along +Z: open base, rounded tip."""
    r0 = r if r0 is None else r0
    pts = []
    cyl = max(length - r, 0.001)
    for i in range(rings + 1):
        t = i / rings
        rr = r0 + (r - r0) * min(1.0, t * 2.2) + bulge * r * math.sin(math.pi * t) * 0.5
        pts.append((rr, cyl * t))
    for i in range(1, cap + 1):
        a = (math.pi / 2) * i / cap
        pts.append((max(r * math.cos(a), 0.0) if i < cap else 0.0, cyl + r * math.sin(a)))
    return pts


def sphere_profile(rings):
    return [((math.cos(-math.pi / 2 + math.pi * i / rings)) if 0 < i < rings else 0.0,
             math.sin(-math.pi / 2 + math.pi * i / rings)) for i in range(rings + 1)]


def torus_profile(major, minor, n):
    return [(major + minor * math.cos(2 * math.pi * i / n), minor * math.sin(2 * math.pi * i / n)) for i in range(n)]


def frame(origin, x=None, y=None, z=None):
    """4x4 from an origin and axis vectors (columns)."""
    m = Matrix.Identity(4)
    for c, a in enumerate((x, y, z)):
        a = Vector(a)
        for r in range(3):
            m[r][c] = a[r]
    for r in range(3):
        m[r][3] = origin[r]
    return m


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)
