"""Parametric embroidered face. Every feature is a small grid patch evaluated from a parameter
set and wrapped onto the barrel, so shape keys and exact expressions come from the same code."""
import math

from m_util import HI, surf

EX = 0.125          # eye centre offset from the face centre line
EZ = 1.190          # eye centre height
EA, EB = 0.042, 0.072   # inner white half sizes
RING1, RING0 = 0.012, 0.024  # black ring, outer white ring
PA, PB = 0.033, 0.056   # pupil half sizes
BZ = 1.338          # brow height
BL = 0.052          # brow half length
MZ = 0.985          # mouth centre height

H = dict(eye0=0.0045, eye1=0.0070, eye2=0.0095, pupil=0.0120, hl=0.0140, brow=0.0065,
         m0=0.0050, m1=0.0075, tongue=0.0095, teeth=0.0110, tout=0.0125, blush=0.0035,
         tear=0.0100, fx=0.0165)

SIDES = (("L", 1.0), ("R", -1.0))  # L = character's left (+X, viewer's right)

BASE = dict(eye_sx=1.0, eye_sy=1.0, hl=1.0,
            mx=0.0, my=0.0, hw=0.082, smile=0.030, up=0.012, dn=0.050, eu=1.0, ed=0.6,
            skew=0.0, wavy=0.0, lw=0.0078, teeth=0.017, tongue=0.024, tw=0.62, tout=0.0,
            blush=0.0, hearts=0.0, stars=0.0, tears=0.0, sweat=0.0)
for _s, _sg in SIDES:
    BASE.update({f"uh_{_s}": 1.25, f"uc_{_s}": 0.0, f"ut_{_s}": 0.0,
                 f"lh_{_s}": -1.25, f"lc_{_s}": 0.0, f"lt_{_s}": 0.0,
                 f"px_{_s}": -0.005 * _sg, f"py_{_s}": -0.004, f"ps_{_s}": 1.0,
                 f"br_{_s}": 0.0, f"bt_{_s}": 0.0, f"ba_{_s}": 0.016})


def _both(**kw):
    out = {}
    for k, v in kw.items():
        out[k + "_L"] = v
        out[k + "_R"] = v
    return out


_CLOSED = dict(up=0.0, dn=0.0, teeth=0.0, tongue=0.0)
KEYS = {
    # eyes
    "blink_L": dict(uh_L=-0.05, uc_L=-0.28, lh_L=-0.05, lc_L=-0.28),
    "blink_R": dict(uh_R=-0.05, uc_R=-0.28, lh_R=-0.05, lc_R=-0.28),
    "happy_L": dict(uh_L=-0.28, uc_L=0.55, lh_L=-0.28, lc_L=0.55),
    "happy_R": dict(uh_R=-0.28, uc_R=0.55, lh_R=-0.28, lc_R=0.55),
    "eyes_wide": dict(eye_sx=1.07, eye_sy=1.13),
    "eyes_squint": _both(uh=0.30, uc=0.28, lh=-0.30, lc=-0.28),
    "lids_angry": _both(uh=0.50, ut=0.50),
    "lids_sad": _both(uh=0.50, ut=-0.50),
    "lids_half": _both(uh=0.12, uc=0.10),
    # pupils
    "look_left": dict(px_L=-0.019, px_R=-0.009),
    "look_right": dict(px_L=0.009, px_R=0.019),
    "look_up": _both(py=0.018),
    "look_down": _both(py=-0.026),
    "pupil_small": _both(ps=0.60),
    "pupil_big": _both(ps=1.22),
    # brows
    "brow_up_L": dict(br_L=0.030),
    "brow_up_R": dict(br_R=0.030),
    "brow_down": _both(br=-0.022),
    "brow_angry": _both(bt=-0.034, br=-0.014, ba=0.006),
    "brow_sad": _both(bt=0.034, br=0.004, ba=0.010),
    # mouth
    "smile_closed": dict(_CLOSED, hw=0.086, smile=0.032),
    "smile_big": dict(hw=0.105, smile=0.044, up=0.034, dn=0.078, teeth=0.021, tongue=0.036, my=0.004),
    "mouth_o": dict(hw=0.040, smile=0.0, up=0.044, dn=0.044, eu=0.5, ed=0.5, teeth=0.0, tongue=0.014, my=-0.010),
    "frown": dict(_CLOSED, hw=0.070, smile=-0.030, my=0.012),
    "flat": dict(_CLOSED, hw=0.060, smile=0.0),
    "smirk_L": dict(_CLOSED, hw=0.060, smile=0.016, skew=0.020, mx=0.016),
    "smirk_R": dict(_CLOSED, hw=0.060, smile=0.016, skew=-0.020, mx=-0.016),
    "shout": dict(hw=0.074, smile=0.0, up=0.030, dn=0.088, eu=0.6, ed=0.5, teeth=0.018, tongue=0.042, my=0.004),
    "pout": dict(hw=0.020, smile=-0.004, up=0.007, dn=0.007, eu=0.5, ed=0.5, teeth=0.0, tongue=0.0),
    "wavy": dict(_CLOSED, hw=0.076, smile=0.0, wavy=0.011),
    "tongue_out": dict(tout=0.036),
    "grin": dict(hw=0.096, smile=0.040, up=0.038, dn=0.034, ed=0.8, teeth=0.090, tongue=0.0),
    "wail": dict(hw=0.082, smile=-0.032, up=0.050, dn=0.022, eu=0.7, ed=0.5, teeth=0.0, tongue=0.020, my=0.010),
    # visemes
    "vis_A": dict(hw=0.060, smile=0.005, up=0.020, dn=0.062, eu=0.6, ed=0.5, teeth=0.014, tongue=0.030),
    "vis_E": dict(hw=0.086, smile=0.012, up=0.016, dn=0.030, teeth=0.016, tongue=0.012),
    "vis_I": dict(hw=0.090, smile=0.016, up=0.014, dn=0.016, teeth=0.060, tongue=0.0),
    "vis_O": dict(hw=0.038, smile=0.0, up=0.042, dn=0.042, eu=0.5, ed=0.5, teeth=0.0, tongue=0.016, my=-0.012),
    "vis_U": dict(hw=0.021, smile=0.0, up=0.019, dn=0.019, eu=0.5, ed=0.5, teeth=0.0, tongue=0.0, my=-0.006),
    "vis_MBP": dict(_CLOSED, hw=0.050, smile=0.005),
    "vis_FV": dict(hw=0.060, smile=0.004, up=0.012, dn=0.009, teeth=0.016, tongue=0.0),
    # extras
    "blush": dict(blush=1.0),
    "fx_hearts": dict(hearts=1.0, hl=0.0, **_both(ps=0.0)),
    "fx_stars": dict(stars=1.0, hl=0.0, **_both(ps=0.0)),
    "fx_tears": dict(tears=1.0),
    "fx_sweat": dict(sweat=1.0),
}

EXPRESSIONS = {
    "Happy": {},
    "Big laugh": {"happy_L": 1, "happy_R": 1, "smile_big": 1, "brow_up_L": 0.7, "brow_up_R": 0.7},
    "Wink": {"happy_L": 1, "smile_big": 0.55, "brow_up_R": 0.7},
    "Grateful": {"happy_L": 1, "happy_R": 1, "smile_closed": 1, "blush": 1, "brow_up_L": 0.3, "brow_up_R": 0.3},
    "Excited": {"fx_stars": 1, "smile_big": 1, "brow_up_L": 1, "brow_up_R": 1},
    "Love": {"fx_hearts": 1, "blush": 1, "smile_big": 0.35, "brow_up_L": 0.5, "brow_up_R": 0.5},
    "Proud": {"blink_L": 1, "blink_R": 1, "smirk_L": 1, "brow_up_L": 0.6, "brow_up_R": 0.6},
    "Surprised": {"eyes_wide": 1, "pupil_small": 0.6, "mouth_o": 1, "brow_up_L": 1, "brow_up_R": 1},
    "Shocked": {"eyes_wide": 1, "pupil_small": 1, "shout": 1, "brow_up_L": 1.2, "brow_up_R": 1.2},
    "Thinking": {"look_up": 0.9, "look_right": 0.8, "brow_up_L": 1, "brow_down": 0.5, "smirk_R": 1},
    "Confused": {"brow_up_L": 1, "brow_angry": 0.5, "wavy": 1, "look_left": 0.7, "pupil_small": 0.35, "lids_half": 0.25},
    "Shy": {"blush": 1, "look_down": 0.9, "look_left": 0.7, "smile_closed": 1, "brow_sad": 0.7},
    "Embarrassed": {"happy_L": 1, "happy_R": 1, "grin": 1, "blush": 1, "fx_sweat": 1, "brow_sad": 1},
    "Worried": {"eyes_wide": 0.5, "pupil_small": 0.7, "brow_sad": 1, "wavy": 1, "fx_sweat": 1},
    "Sad": {"lids_sad": 1, "look_down": 0.9, "brow_sad": 1, "frown": 1},
    "Crying": {"blink_L": 1, "blink_R": 1, "fx_tears": 1, "wail": 1, "brow_sad": 1.1},
    "Annoyed": {"lids_angry": 0.9, "brow_angry": 1, "flat": 1, "look_left": 0.6},
    "Determined": {"lids_angry": 0.45, "brow_angry": 1, "smirk_L": 1},
    "Sleepy": {"lids_half": 1.25, "look_down": 0.5, "mouth_o": 0.75, "brow_sad": 0.4},
    "Calm": {"blink_L": 1, "blink_R": 1, "smile_closed": 1},
}


def params(weights=None):
    """Blend shape-key weights (or an expression name) into one parameter set."""
    if isinstance(weights, str):
        weights = EXPRESSIONS[weights]
    P = dict(BASE)
    for key, w in (weights or {}).items():
        for name, val in KEYS[key].items():
            P[name] += w * (val - BASE[name])
    return P


# ------------------------------------------------------------------ primitives
def _lens(name, mat, x0, x1, top, bot, nx, ny, h, hedge=None):
    hedge = h - 0.0035 if hedge is None else hedge
    xc, hw = (x0 + x1) / 2, (x1 - x0) / 2
    pts = []
    for i in range(nx):
        u = -1 + 2 * i / (nx - 1)
        x = xc + hw * math.sin(u * math.pi / 2)
        t, b = top(x), bot(x)
        if b > t:
            t = b = (t + b) / 2
        k = min(1.0, (t - b) / 0.006)
        for j in range(ny):
            edge = min(i, nx - 1 - i, j, ny - 1 - j) == 0
            pts.append((x, b + (t - b) * j / (ny - 1), hedge if edge else hedge + (h - hedge) * k))
    return dict(name=name, mat=mat, kind="lens", nx=nx, ny=ny, pts=pts)


def _fan(name, mat, c, boundary, nr, h, scale=1.0, hedge=None):
    hedge = h - 0.0035 if hedge is None else hedge
    pts = [(c[0], c[1], h if scale > 0 else hedge)]
    for k in range(1, nr + 1):
        f = scale * k / nr
        for (bx, by) in boundary:
            pts.append((c[0] + f * bx, c[1] + f * by, hedge if (k == nr or scale <= 0) else h))
    return dict(name=name, mat=mat, kind="fan", nr=nr, ns=len(boundary), pts=pts)


def _ell(x, cx, a, b):
    t = (x - cx) / a
    return b * math.sqrt(max(0.0, 1 - t * t))


def _res(hi, lo):
    return hi if HI else lo


# ------------------------------------------------------------------ the face
def layers(P):
    L = []
    enx, eny = _res(48, 20), _res(46, 18)
    for sn, sg in SIDES:
        cx, cy = sg * EX, EZ
        a, b = EA * P["eye_sx"], EB * P["eye_sy"]
        uh, uc, ut = P[f"uh_{sn}"], P[f"uc_{sn}"], P[f"ut_{sn}"]
        lh, lc, lt = P[f"lh_{sn}"], P[f"lc_{sn}"], P[f"lt_{sn}"]

        def lid_u(x, a=a, b=b, cx=cx, sg=sg, h=uh, c=uc, t=ut):
            u = sg * (x - cx) / a
            return EZ + b * (h + c * (1 - u * u) + t * u)

        def lid_l(x, a=a, b=b, cx=cx, sg=sg, h=lh, c=lc, t=lt):
            u = sg * (x - cx) / a
            return EZ + b * (h + c * (1 - u * u) + t * u)

        for lname, grow, pad, mat, hh in (("eye0", RING0, 0.0135, "white", H["eye0"]),
                                          ("eye1", RING1, 0.0065, "black", H["eye1"]),
                                          ("eye2", 0.0, 0.0, "white", H["eye2"])):
            aa, bb = a + grow, b + grow
            L.append(_lens(f"{lname}_{sn}", mat, cx - aa, cx + aa,
                           lambda x, aa=aa, bb=bb, cx=cx, pad=pad, lu=lid_u: min(cy + _ell(x, cx, aa, bb), lu(x) + pad),
                           lambda x, aa=aa, bb=bb, cx=cx, pad=pad, ll=lid_l: max(cy - _ell(x, cx, aa, bb), ll(x) - pad),
                           enx, eny, hh))
        # pupil and highlight, clipped by the white and the lids
        ps = max(P[f"ps_{sn}"], 0.0)
        pcx, pcy = cx + P[f"px_{sn}"], cy + P[f"py_{sn}"]
        pa, pb = PA * ps + 1e-5, PB * ps + 1e-5
        ia, ib = a - 0.0015, b - 0.0015

        def clip_top(x, f, cx=cx, ia=ia, ib=ib, lu=lid_u):
            return min(f(x), cy + _ell(x, cx, ia, ib), lu(x))

        def clip_bot(x, f, cx=cx, ia=ia, ib=ib, ll=lid_l):
            return max(f(x), cy - _ell(x, cx, ia, ib), ll(x))

        L.append(_lens(f"pupil_{sn}", "black", pcx - pa, pcx + pa,
                       lambda x, ct=clip_top, pcx=pcx, pcy=pcy, pa=pa, pb=pb: ct(x, lambda q: pcy + _ell(q, pcx, pa, pb)),
                       lambda x, cb=clip_bot, pcx=pcx, pcy=pcy, pa=pa, pb=pb: cb(x, lambda q: pcy - _ell(q, pcx, pa, pb)),
                       _res(30, 14), _res(22, 12), H["pupil"]))
        hs = ps * max(P["hl"], 0.0)
        hx, hy = pcx - 0.011 * ps, pcy + 0.021 * ps
        ha, hb = 0.0105 * hs + 1e-5, 0.0135 * hs + 1e-5
        L.append(_lens(f"hl_{sn}", "white", hx - ha, hx + ha,
                       lambda x, ct=clip_top, hx=hx, hy=hy, ha=ha, hb=hb: ct(x, lambda q: hy + _ell(q, hx, ha, hb)),
                       lambda x, cb=clip_bot, hx=hx, hy=hy, ha=ha, hb=hb: cb(x, lambda q: hy - _ell(q, hx, ha, hb)),
                       _res(14, 8), _res(10, 6), H["hl"], H["hl"] - 0.002))
        # brow
        bcx, bcy = sg * EX, BZ + P[f"br_{sn}"]
        bt, ba = P[f"bt_{sn}"], P[f"ba_{sn}"]

        def brow_c(x, bcx=bcx, bcy=bcy, sg=sg, bt=bt, ba=ba):
            u = sg * (x - bcx) / BL
            return bcy + ba * (1 - u * u) - bt * u, 0.0070 * (1 - 0.6 * u * u)

        L.append(_lens(f"brow_{sn}", "black", bcx - BL, bcx + BL,
                       lambda x, f=brow_c: f(x)[0] + f(x)[1],
                       lambda x, f=brow_c: f(x)[0] - f(x)[1],
                       _res(32, 14), _res(7, 4), H["brow"]))

    # mouth
    mcx, mcy = P["mx"], MZ + P["my"]
    hw, lw = max(P["hw"], 0.004), P["lw"]
    up, dn = max(P["up"], 0.0), max(P["dn"], 0.0)

    def spine(x):
        t = (x - mcx) / hw
        return mcy + P["smile"] * t * t + P["skew"] * t + P["wavy"] * math.sin(2.5 * math.pi * t)

    def m_top(x):
        t = min(1.0, abs((x - mcx) / hw))
        return spine(x) + up * (1 - t * t) ** P["eu"]

    def m_bot(x):
        t = min(1.0, abs((x - mcx) / hw))
        return spine(x) - dn * (1 - t * t) ** P["ed"]

    def outline(x, sign):
        xc = min(mcx + hw, max(mcx - hw, x))
        over = (abs(x - mcx) - hw) / lw
        k = math.sqrt(max(0.0, 1 - over * over)) if over > 0 else 1.0
        return (m_top(xc) + lw * k) if sign > 0 else (m_bot(xc) - lw * k)

    mnx = _res(64, 28)
    L.append(_lens("mouth0", "black", mcx - hw - lw, mcx + hw + lw,
                   lambda x: outline(x, 1), lambda x: outline(x, -1), mnx, _res(14, 8), H["m0"]))
    L.append(_lens("mouth1", "mouth", mcx - hw, mcx + hw, m_top, m_bot, mnx, _res(14, 8), H["m1"]))
    tw = P["tw"]

    def tongue_top(x):
        t = (x - mcx) / (hw * tw)
        return min(m_bot(x) + max(P["tongue"], 0.0) * math.sqrt(max(0.0, 1 - t * t)), m_top(x))

    L.append(_lens("tongue", "tongue", mcx - hw * tw, mcx + hw * tw, tongue_top, m_bot,
                   _res(36, 16), _res(8, 5), H["tongue"]))

    def teeth_bot(x):
        t = min(1.0, abs((x - mcx) / hw))
        return max(m_bot(x), m_top(x) - max(P["teeth"], 0.0) * (1 - t * t) ** 0.35)

    L.append(_lens("teeth", "white", mcx - hw, mcx + hw, m_top, teeth_bot,
                   _res(48, 20), _res(8, 5), H["teeth"]))
    tout, tow = max(P["tout"], 0.0), 0.030

    def tout_bot(x):
        t = (x - mcx) / tow
        return m_bot(x) - tout * math.sqrt(max(0.0, 1 - t * t))

    L.append(_lens("tongue_out", "tongue", mcx - tow, mcx + tow,
                   lambda x: m_bot(x) + min(0.010, tout * 0.4) * math.sqrt(max(0.0, 1 - ((x - mcx) / tow) ** 2)),
                   tout_bot, _res(24, 12), _res(10, 6), H["tout"]))

    # extras (scaled from nothing)
    ns = 40
    circle = [(math.cos(2 * math.pi * k / ns), math.sin(2 * math.pi * k / ns)) for k in range(ns)]
    for sn, sg in SIDES:
        s = P["blush"]
        L.append(_fan(f"blush_{sn}", "blush", (sg * 0.232, 1.098), [(0.040 * x, 0.021 * y) for x, y in circle],
                      _res(5, 3), H["blush"], s, hedge=0.0005))
        heart = []
        for k in range(ns):
            t = -2 * math.pi * k / ns
            heart.append((0.058 * 16 * math.sin(t) ** 3 / 17,
                          0.058 * ((13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17 + 0.12)))
        L.append(_fan(f"heart_{sn}", "heart", (sg * EX, EZ), heart, _res(6, 3), H["fx"], P["hearts"]))
        star = []
        for k in range(ns):
            ang = math.pi / 2 + 2 * math.pi * k / ns
            tt = abs((k % 8) - 4) / 4
            rad = 0.026 + (0.066 - 0.026) * tt
            star.append((rad * math.cos(ang), rad * math.sin(ang)))
        L.append(_fan(f"star_{sn}", "star", (sg * EX, EZ), star, _res(6, 3), H["fx"], P["stars"]))
        tc, tww, y0 = sg * (EX + 0.012), 0.019, EZ - EB - 0.012
        tl = 0.150 * max(P["tears"], 0.0)
        L.append(_lens(f"tear_{sn}", "tear", tc - tww, tc + tww,
                       lambda x, y0=y0: y0,
                       lambda x, tc=tc, y0=y0, tl=tl, tww=tww: y0 - tl * (0.72 + 0.28 * math.sqrt(max(0.0, 1 - ((x - tc) / tww) ** 2))),
                       _res(16, 8), _res(34, 20), H["tear"]))
    drop = []
    for k in range(ns):
        ang = 2 * math.pi * k / ns
        rad = 0.030 * (1 + 1.25 * max(0.0, math.sin(ang)) ** 3)
        drop.append((rad * math.cos(ang), rad * math.sin(ang)))
    L.append(_fan("sweat", "tear", (0.262, 1.318), drop, _res(6, 3), H["tear"], P["sweat"]))
    return L


def topology(P=None):
    """Faces, per-vertex uvs and material names for the face mesh (constant for all params)."""
    faces, uvs, mats, off = [], [], [], 0
    for lay in layers(P or BASE):
        n = len(lay["pts"])
        if lay["kind"] == "lens":
            nx, ny = lay["nx"], lay["ny"]
            for i in range(nx - 1):
                for j in range(ny - 1):
                    a = off + i * ny + j
                    faces.append((a, a + ny, a + ny + 1, a + 1))
                    mats.append(lay["mat"])
        else:
            nr, ns = lay["nr"], lay["ns"]
            for m in range(ns):
                m2 = (m + 1) % ns
                faces.append((off, off + 1 + m, off + 1 + m2))
                mats.append(lay["mat"])
                for k in range(1, nr):
                    a, b = off + 1 + (k - 1) * ns, off + 1 + k * ns
                    faces.append((a + m, b + m, b + m2, a + m2))
                    mats.append(lay["mat"])
        uvs += [(p[0], p[1]) for p in lay["pts"]]
        off += n
    return faces, uvs, mats


def coords(P):
    out = []
    for lay in layers(P):
        for (x, z, h) in lay["pts"]:
            out.append(surf(x, z, h))
    return out
