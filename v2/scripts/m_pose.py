"""Posing: rubber-hose arms and legs follow curves, hands and feet are placed directly."""
import math

import bpy
from mathutils import Matrix, Vector

from m_build import FINGERS, SHOULDER_X, SHOULDER_Y, SHOULDER_Z, finger_frame, hand_matrix
from m_util import ANKLE_Z, ARM_L, ARM_N, HIP_X, HIP_Z, LEG_N, Z_BOT

CURLS = {  # degrees per finger: (base joint, tip joint)
    "open": dict(thumb=(0, 0), index=(0, 0), middle=(0, 0), pinky=(0, 0)),
    "relax": dict(thumb=(12, 12), index=(22, 22), middle=(26, 26), pinky=(30, 28)),
    "fist": dict(thumb=(50, 60), index=(85, 80), middle=(85, 80), pinky=(85, 80)),
    "thumbsup": dict(thumb=(-18, -6), index=(88, 82), middle=(88, 82), pinky=(88, 82)),
    "point": dict(thumb=(50, 55), index=(0, 0), middle=(85, 80), pinky=(85, 80)),
    "ok": dict(thumb=(38, 48), index=(62, 62), middle=(4, 0), pinky=(0, 0)),
    "grip": dict(thumb=(28, 30), index=(48, 46), middle=(48, 46), pinky=(48, 46)),
    "flat": dict(thumb=(6, 4), index=(4, 2), middle=(4, 2), pinky=(4, 2)),
}


def _basis(x, y, z):
    m = Matrix.Identity(4)
    for c, a in enumerate((x, y, z)):
        for r in range(3):
            m[r][c] = a[r]
    return m


def _bez(p0, p1, p2, p3, t):
    u = 1 - t
    return p0 * (u ** 3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t ** 3)


def _curve(S, out, W, arr, k, samples=64):
    pts = [_bez(S, S + out * k, W - arr * k, W, i / samples) for i in range(samples + 1)]
    ln = sum((pts[i + 1] - pts[i]).length for i in range(samples))
    return pts, ln


def _resample(pts, n):
    acc = [0.0]
    for i in range(len(pts) - 1):
        acc.append(acc[-1] + (pts[i + 1] - pts[i]).length)
    out = []
    j = 0
    for k in range(n + 1):
        target = acc[-1] * k / n
        while j < len(acc) - 2 and acc[j + 1] < target:
            j += 1
        seg = acc[j + 1] - acc[j]
        f = (target - acc[j]) / seg if seg > 1e-9 else 0.0
        out.append(pts[j].lerp(pts[j + 1], f))
    return out


def hose(S, out, W, arr, length, n, k=None):
    """Curve from S to W with the given rest length when reachable (else it stretches)."""
    out, arr = out.normalized(), arr.normalized()
    lo, hi = 0.01, 2.5
    if k is not None:
        pts = _curve(S, out, W, arr, k * (W - S).length)[0]
    elif _curve(S, out, W, arr, lo)[1] >= length:
        pts = _curve(S, out, W, arr, 0.35 * (W - S).length)[0]
    else:
        for _ in range(40):
            mid = (lo + hi) / 2
            if _curve(S, out, W, arr, mid)[1] < length:
                lo = mid
            else:
                hi = mid
        pts = _curve(S, out, W, arr, (lo + hi) / 2)[0]
    return _resample(pts, n)


def chain_D(pts, rest_head, rest_d, rest_up, seg, end_up):
    n = len(pts) - 1
    tans = [(pts[i + 1] - pts[i]).normalized() for i in range(n)]
    ups = []
    up = rest_d.rotation_difference(tans[0]) @ rest_up
    for i in range(n):
        if i:
            up = tans[i - 1].rotation_difference(tans[i]) @ up
        ups.append(up.copy())
    twist = 0.0
    if end_up is not None:
        t = tans[-1]
        e = end_up - t * end_up.dot(t)
        if e.length > 1e-5:
            e.normalize()
            u = ups[-1]
            twist = math.atan2(t.dot(u.cross(e)), u.dot(e))
    rest_B = _basis(rest_d, rest_up, rest_d.cross(rest_up))
    Ds = []
    for i in range(n):
        t = tans[i]
        u = Matrix.Rotation(twist * (i + 1) / n, 3, t) @ ups[i]
        s = (pts[i + 1] - pts[i]).length / seg
        B = _basis(t, u, t.cross(u))
        h = rest_head + rest_d * seg * i
        Ds.append(Matrix.Translation(pts[i]) @ B @ Matrix.Diagonal((s, 1, 1, 1)) @ rest_B.inverted()
                  @ Matrix.Translation(-h))
    return Ds


def _rot_about(point, axis, deg):
    return Matrix.Translation(point) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-point)


def compute(pose):
    D = {}
    b = pose.get("body", {})
    piv = Vector(b.get("pivot", (0, 0, Z_BOT)))
    rx, ry, rz = (math.radians(a) for a in b.get("rot", (0, 0, 0)))
    R = Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(rx, 4, "X") @ Matrix.Rotation(ry, 4, "Y")
    sc = b.get("scale", (1, 1, 1))
    Db = (Matrix.Translation(Vector(b.get("loc", (0, 0, 0)))) @ Matrix.Translation(piv) @ R
          @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1)) @ Matrix.Translation(-piv))
    D["root"] = Matrix.Identity(4)
    D["body"] = Db
    for S, sg in (("L", 1.0), ("R", -1.0)):
        a = pose.get("arm" + S, {})
        s_rest = Vector((sg * SHOULDER_X, SHOULDER_Y, SHOULDER_Z))
        w_rest = s_rest + Vector((sg * ARM_L, 0, 0))
        W = Vector(a.get("wrist", (sg * 0.62, -0.05, 0.62)))
        f = Vector(a.get("fingers", (sg * 0.2, 0, -1))).normalized()
        n = Vector(a.get("palm", (-sg, 0, 0)))
        n = (n - f * n.dot(f)).normalized()
        arr = Vector(a.get("arrive", f))
        out = Vector(a.get("out", (sg, 0, 0)))
        xt = (f.cross(-n)) * sg
        pts = hose(s_rest, out, W, arr, ARM_L, ARM_N, a.get("k"))
        Ds = chain_D(pts, s_rest, Vector((sg, 0, 0)), Vector((0, 0, 1)), ARM_L / ARM_N, xt)
        for i, Di in enumerate(Ds):
            D[f"arm{i}.{S}"] = Db @ Di
        Bt = _basis(xt, f, -n)
        Br = _basis(Vector((0, 0, 1)), Vector((sg, 0, 0)), Vector((0, 1, 0)))
        Dh = Db @ Matrix.Translation(pts[-1]) @ Bt @ Br.inverted() @ Matrix.Translation(-w_rest)
        D[f"hand.{S}"] = Dh
        curl = a.get("curl", "relax")
        curl = CURLS[curl] if isinstance(curl, str) else curl
        Mh = hand_matrix(sg)
        palm_n = Vector((0, -1, 0))
        for name, base, ang, ln, r in FINGERS:
            Fm = Mh @ finger_frame(base, ang)
            axis = (Fm.to_3x3() @ Vector((1, 0, 0))).normalized()
            d0 = (Fm.to_3x3() @ Vector((0, 0, 1))).normalized()
            sign = 1.0 if (Matrix.Rotation(0.1, 3, axis) @ d0).dot(palm_n) > 0 else -1.0
            j1, j2 = Fm @ Vector((0, 0, 0)), Fm @ Vector((0, 0, ln * 0.5))
            c1, c2 = curl.get(name, (0, 0))
            R1 = _rot_about(j1, axis, sign * c1)
            R2 = _rot_about(j2, axis, sign * c2)
            D[f"{name}1.{S}"] = Dh @ R1
            D[f"{name}2.{S}"] = Dh @ R1 @ R2
        # leg
        lg = pose.get("leg" + S, {})
        h_rest = Vector((sg * HIP_X, 0, HIP_Z))
        a_rest = Vector((sg * HIP_X, 0, ANKLE_Z))
        ft = lg.get("foot", (sg * 0.23, 0.0))
        A = Vector((ft[0], ft[1], ft[2] if len(ft) > 2 else ANKLE_Z))
        Rf = (Matrix.Rotation(math.radians(sg * lg.get("yaw", 18.0)), 4, "Z")
              @ Matrix.Rotation(math.radians(lg.get("pitch", 0.0)), 4, "X")
              @ Matrix.Rotation(math.radians(lg.get("roll", 0.0)), 4, "Y"))
        Df = Matrix.Translation(A) @ Rf @ Matrix.Translation(-a_rest)
        D[f"foot.{S}"] = Df
        hip = Db @ h_rest
        down = (Db.to_3x3() @ Vector((0, 0, -1))).normalized()
        arrive = (Rf.to_3x3() @ Vector((0, 0, -1))).normalized()
        fwd = (Rf.to_3x3() @ Vector((0, -1, 0))).normalized()
        ln = HIP_Z - ANKLE_Z
        pts = hose(hip, down, A, arrive, ln, LEG_N)
        for i, Di in enumerate(chain_D(pts, h_rest, Vector((0, 0, -1)), Vector((0, -1, 0)), ln / LEG_N, fwd)):
            D[f"leg{i}.{S}"] = Di
    return D


def apply_pose(rig, pose):
    D = compute(pose)
    for bone in rig.data.bones:
        pb = rig.pose.bones[bone.name]
        d = D.get(bone.name)
        if d is None:
            d = D[bone.parent.name] if bone.parent else Matrix.Identity(4)
            D[bone.name] = d
        pb.matrix = d @ bone.matrix_local
        bpy.context.view_layer.update()


def merge(base, **over):
    out = {k: dict(v) for k, v in base.items()}
    for k, v in over.items():
        out[k] = dict(out.get(k, {}), **v)
    return out


HERO = dict(
    body=dict(),
    armR=dict(wrist=(-0.72, -0.06, 1.00), fingers=(-0.14, 0.0, 1.0), palm=(0.05, -1.0, 0.0), curl="open",
              arrive=(-0.25, 0.0, 1.0), out=(-1.0, -0.1, -0.35)),
    armL=dict(wrist=(0.635, -0.07, 0.66), fingers=(-0.38, -0.10, -1.0), palm=(-1.0, -0.25, 0.25), curl="relax",
              arrive=(-0.30, 0.0, -1.0), out=(1.0, -0.1, 0.35)),
    legL=dict(foot=(0.245, -0.03), yaw=24),
    legR=dict(foot=(-0.245, 0.0), yaw=24),
)
