"""
Laser-cut plywood module boxes for the Portal North Bridge T-TRAK set.

Based on the "Double 618 x 330 T Track Module" laser template:
  - 5 mm ply (or 1/4" ply, 0.22" actual)
  - same 618 x 330 footprint, 70.09 mm module height, 61.6 mm finger-joint pitch on the
    long sides, end tabs at 66-132 / 198-264, corner tabs 20.85-43.54 mm above the table
  - same colour convention: purple = outside cut (kerf OUT), green = inside cut (kerf IN),
    red = engrave or delete (reference only)

Two module types (lowered "river" scene; the track deck is the printed bridge):
  * ARCH module (cut 3)     : base plate (river bed), full-height back apron, low front apron,
                              and at each end a pier-shaped end plate (the plywood IS the pier core;
                              a 4 mm printed pier face glues on) plus a back end plate.
  * APPROACH module (cut 1) : as above, plus a short top plate + standard end plate at the
                              left end (joins a normal T-TRAK module) and an abutment cross plate.

Run:  python portal_laser.py            -> writes SVGs to ttrak_output/portal_bridge/laser/
The geometry is also used by portal_bridge.py to show the plywood boxes in the renders.
"""

import math
import os

T = 5.0                    # ply thickness
TOP = 70.09                # table -> module top surface (template value)
L = 618.0                  # module length
D = 330.0                  # module depth (template value)
HF = 16.0                  # low front apron height
SIDE_TAB = (20.85, 43.54)  # template corner tab height band
FRONT_TAB = (8.0, 13.0)    # low front apron <-> pier end plate tab
LONG_TABS = [(61.6, 123.2), (184.8, 246.4), (371.6, 433.2), (494.8, 556.4)]   # template pitch
END_TABS = [(66.0, 132.0), (198.0, 264.0)]                                     # template
FEET = [(24.5, 24.5), (L - 24.5, 24.5), (24.5, D - 24.5), (L - 24.5, D - 24.5)]
FOOT_D = 9.0               # same as the template bracket hole (T-nut + leveling bolt)

# bridge geometry (must match portal_bridge.py)
YC, HALF_IN = 67.0, 45.0
CAP_DROP = 12.0            # pier cap top below module top
CAP_Y0, CAP_Y1 = YC - HALF_IN - 8, YC + HALF_IN + 8     # 14 .. 120
SHAFT_Y0, SHAFT_Y1 = YC - 30, YC + 30                   # 37 .. 97
PIER_TABS = [(12.0, 30.0), (50.0, 85.0)]
BACK_Y0 = 260.0
BACK_TABS = [(275.0, 305.0)]
WATER = T + 3.0            # water surface (3 mm pour on the base plate)

# approach module
TOP_PLATE_X = 80.0         # short top plate covers 0..80 (abutment under 75..80)
TOP_TABS_X = [(25.0, 55.0)]
ABUT_X = 75.0
ABUT_BOTTOM_TABS = [(80.0, 120.0), (200.0, 240.0)]

PURPLE, GREEN, RED = "#70299C", "#3D805E", "#EA3627"


# ----------------------------------------------------------------------------
# 2D helpers
# ----------------------------------------------------------------------------
def edge(pts, axis, fixed, a, b, feats, out):
    """Append a straight edge running from a to b along `axis` ('u' or 'v') at the
    other coordinate `fixed`.  feats = [(s0, s1, delta)], delta>0 moves the edge by
    delta in direction `out` (+1/-1) of the fixed coordinate (tab) / delta<0 (notch)."""
    rev = b < a
    fs = sorted(feats, key=lambda f: f[0], reverse=rev)

    def P(s, f):
        return (s, f) if axis == "u" else (f, s)

    pts.append(P(a, fixed))
    for s0, s1, d in fs:
        if rev:
            s0, s1 = s1, s0
        pts += [P(s0, fixed), P(s0, fixed + d * out), P(s1, fixed + d * out), P(s1, fixed)]
    pts.append(P(b, fixed))


def clean(pts):
    out = []
    for p in pts:
        p = (round(p[0], 4), round(p[1], 4))
        if out and p == out[-1]:
            continue
        out.append(p)
    if out[0] == out[-1]:
        out.pop()
    # drop collinear points
    res = []
    n = len(out)
    for i in range(n):
        a, b, c = out[i - 1], out[i], out[(i + 1) % n]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            res.append(b)
    return res


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, d, n=36):
    return [(cx + d / 2 * math.cos(2 * math.pi * i / n), cy + d / 2 * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def stadium(u0, u1, v0, v1, n=12):
    r = (v1 - v0) / 2
    cy = (v0 + v1) / 2
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((u1 - r + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi / 2 + math.pi * i / n
        pts.append((u0 + r + r * math.cos(a), cy + r * math.sin(a)))
    return pts


class Panel:
    """A flat ply part. outline/holes in local (u,v); plane + offset place it in 3D:
       'XY': (u,v)->(X,Y), thickness along Z from `off`
       'XZ': (u,v)->(X,Z), thickness along Y from `off`
       'YZ': (u,v)->(Y,Z), thickness along X from `off`"""

    def __init__(self, name, outline, plane, off, holes=(), engrave=(), labels=(), qty=1):
        self.name, self.outline, self.plane, self.off = name, clean(outline), plane, off
        self.holes = [h for h in holes]
        self.engrave = list(engrave)        # polylines (reference only)
        self.labels = list(labels)          # (u, v, text, size)
        self.qty = qty

    def bbox(self):
        us = [p[0] for p in self.outline]
        vs = [p[1] for p in self.outline]
        return min(us), min(vs), max(us), max(vs)


# ----------------------------------------------------------------------------
# Parts
# ----------------------------------------------------------------------------
def base_plate(left_tabs, right_tabs, slots=(), name="base_plate"):
    """River bed. Notches receive the bottom tabs of aprons and end plates."""
    p = []
    edge(p, "u", 0, 0, L, [(a, b, -T) for a, b in LONG_TABS], -1)          # front (notch inward = +v)
    edge(p, "v", L, 0, D, [(a, b, -T) for a, b in right_tabs], +1)         # right end
    edge(p, "u", D, L, 0, [(a, b, -T) for a, b in LONG_TABS], +1)          # back
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in left_tabs], -1)          # left end
    holes = [circle(x, y, FOOT_D) for x, y in FEET] + list(slots)
    eng = [rect(0, YC - HALF_IN - 3, L, YC + HALF_IN + 3),                # bridge deck footprint
           rect(T, SHAFT_Y0, T + 4, SHAFT_Y1), rect(L - T - 4, SHAFT_Y0, L - T, SHAFT_Y1)]
    labels = [(L / 2, YC, "DECK ABOVE - FRONT EDGE THIS SIDE", 6), (L / 2, 200, name.upper().replace("_", " "), 8)]
    return Panel(name, p, "XY", 0.0, holes, eng, labels)


def apron(name, y_off, top_profile, left_notch, right_notch, slots=()):
    """Long side. top_profile = list of (u, v) points from u=L back to u=0 along the top."""
    p = []
    edge(p, "u", T, 0, L, [(a, b, T) for a, b in LONG_TABS], -1)           # bottom tabs down into base
    lo, hi = right_notch
    p += [(L, T), (L, lo), (L - T, lo), (L - T, hi), (L, hi)]
    p += top_profile
    lo, hi = left_notch
    p += [(0, hi), (T, hi), (T, lo), (0, lo), (0, T)]
    lab = (L * 0.6, 8.5, name.upper().replace("_", " "), 3.5) if "front" in name else \
        (L / 2, 2 * T + 4, name.upper().replace("_", " "), 5)
    return Panel(name, p, "XZ", y_off, slots, labels=[lab])


def end_pier(name, x_off):
    """Pier-shaped end plate: the plywood core of the pier at each module joint."""
    zc = TOP - CAP_DROP                     # 58.09 cap top
    flare = SHAFT_Y0 - CAP_Y0               # 45-degree flare
    p = []
    edge(p, "u", T, T, SHAFT_Y1, [(a, b, T) for a, b in PIER_TABS], -1)
    p += [(SHAFT_Y1, zc - 6 - flare), (CAP_Y1, zc - 6), (CAP_Y1, zc), (CAP_Y0, zc), (CAP_Y0, zc - 6),
          (SHAFT_Y0, zc - 6 - flare), (SHAFT_Y0, HF), (T, HF),
          (T, FRONT_TAB[1]), (0, FRONT_TAB[1]), (0, FRONT_TAB[0]), (T, FRONT_TAB[0])]
    eng = [[(SHAFT_Y0, zc - 6 - flare), (SHAFT_Y1, zc - 6 - flare)]]
    return Panel(name, p, "YZ", x_off, engrave=eng, labels=[(YC, 40, "PIER", 5)])


def end_back(name, x_off):
    p = []
    edge(p, "u", T, BACK_Y0, D - T, [(a, b, T) for a, b in BACK_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1]),
          (D - T, TOP), (BACK_Y0, TOP)]
    return Panel(name, p, "YZ", x_off, labels=[((BACK_Y0 + D) / 2, 55, "BACK", 5)])


def end_standard(name, x_off):
    """Template-style end plate with bottom tabs added (joins a normal T-TRAK module)."""
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in END_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", TOP - T, D - T, T, [(a, b, T) for a, b in END_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    holes = [stadium(120.4, 209.8, 18.2, 46.2)]             # wiring hole, as in the template
    return Panel(name, p, "YZ", x_off, holes, labels=[(D / 2, 10, name.upper().replace("_", " "), 5)])


def abutment(name, x_off):
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in ABUT_BOTTOM_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", TOP - T, D - T, T, [(a, b, T) for a, b in END_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    holes = [stadium(140, 190, 20, 40)]
    return Panel(name, p, "YZ", x_off, holes, labels=[(D / 2, 52, "ABUTMENT", 5)])


def top_plate_short():
    p = []
    edge(p, "u", 0, 0, TOP_PLATE_X, [(a, b, -T) for a, b in TOP_TABS_X], -1)
    edge(p, "v", TOP_PLATE_X, 0, D, [(a, b, -T) for a, b in END_TABS], +1)
    edge(p, "u", D, TOP_PLATE_X, 0, [(a, b, -T) for a, b in TOP_TABS_X], +1)
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)
    holes = [circle(x, y, 2.8) for x in (15.0, 62.0) for y in (50.5, 83.5)]   # feeder/screw holes
    eng = [[(0, 50.5), (TOP_PLATE_X, 50.5)], [(0, 83.5), (TOP_PLATE_X, 83.5)]]
    return Panel("top_plate_short", p, "XY", TOP - T, holes, eng, [(40, 200, "TOP", 6)])


# ----------------------------------------------------------------------------
# Module sets
# ----------------------------------------------------------------------------
def arch_module():
    flat_top = [(L, TOP), (0, TOP)]
    low_top = [(L, HF), (0, HF)]
    end_t = PIER_TABS + BACK_TABS
    return [
        base_plate(end_t, end_t, name="arch_base_plate"),
        apron("arch_front_apron_low", 0.0, low_top, FRONT_TAB, FRONT_TAB),
        apron("arch_back_apron", D - T, flat_top, SIDE_TAB, SIDE_TAB),
        end_pier("pier_end_plate_L", 0.0), end_pier("pier_end_plate_R", L - T),
        end_back("back_end_plate_L", 0.0), end_back("back_end_plate_R", L - T),
    ]


# ---------------------------------------------------------------------------- transition module
TR_TOP_X = 100.0                  # full-depth track-level top plate 0..100
TR_ABUT_X = 201.0                 # abutment plate 201..206; viaduct spans start at 206
STRIP_Y0, STRIP_Y1 = 14.0, 120.0  # embankment between retaining walls (same width as the pier caps)
CROSS_TOP_TABS = [(150.0, 200.0), (250.0, 300.0)]
CROSS_BOTTOM_TABS = [(140.0, 180.0), (240.0, 280.0)]
WALL_TOP_TABS = [(120.0, 150.0), (165.0, 195.0)]
WALL_BOTTOM_TABS = [(115.0, 145.0), (160.0, 190.0)]
WALL_END_TAB = (20.0, 40.0)       # wall -> cross plate (through slot)
ABUT_SIDE_TAB = (25.0, 45.0)      # abutment -> walls
ABUT_TOP_TABS = [(40.0, 95.0)]
ABUT_BOT_TABS = [(50.0, 85.0)]


def tr_top_plate():
    p = []
    edge(p, "u", 0, 0, TR_TOP_X, [(a, b, -T) for a, b in TOP_TABS_X], -1)              # front
    p += [(TR_TOP_X, 0), (TR_TOP_X, STRIP_Y0)]
    edge(p, "u", STRIP_Y0, TR_TOP_X, TR_ABUT_X + T, [(a, b, -T) for a, b in WALL_TOP_TABS], -1)
    edge(p, "v", TR_ABUT_X + T, STRIP_Y0, STRIP_Y1, [(a, b, -T) for a, b in ABUT_TOP_TABS], +1)
    edge(p, "u", STRIP_Y1, TR_ABUT_X + T, TR_TOP_X, [(a, b, -T) for a, b in WALL_TOP_TABS], +1)
    edge(p, "v", TR_TOP_X, STRIP_Y1, D, [(a, b, -T) for a, b in CROSS_TOP_TABS], +1)
    edge(p, "u", D, TR_TOP_X, 0, [(a, b, -T) for a, b in TOP_TABS_X], +1)              # back
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)                        # left end
    holes = [circle(x, y, 2.8) for x in (15.0, 62.0, 150.0) for y in (50.5, 83.5)]
    eng = [[(0, 50.5), (TR_ABUT_X + T, 50.5)], [(0, 83.5), (TR_ABUT_X + T, 83.5)]]
    return Panel("transition_top_plate", p, "XY", TOP - T, holes, eng, [(50, 200, "TOP", 6)])


def cross_plate():
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in CROSS_BOTTOM_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", TOP - T, D - T, T, [(a, b, T) for a, b in CROSS_TOP_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    holes = [rect(y - 0.05, WALL_END_TAB[0] - 0.05, y + T + 0.05, WALL_END_TAB[1] + 0.05)
             for y in (STRIP_Y0, STRIP_Y1 - T)]
    holes.append(stadium(200, 290, 15, 35))
    return Panel("ground_cross_plate", p, "YZ", TR_TOP_X - T, holes,
                 labels=[(220, TOP - 15, "CROSS PLATE - FOAM SLOPE IN FRONT", 4)])


def retaining_wall(name, y_off):
    p = []
    x0, x1 = TR_TOP_X, TR_ABUT_X + T
    edge(p, "u", T, x0, x1, [(a, b, T) for a, b in WALL_BOTTOM_TABS], -1)
    p += [(x1, ABUT_SIDE_TAB[0]), (x1 - T, ABUT_SIDE_TAB[0]), (x1 - T, ABUT_SIDE_TAB[1]), (x1, ABUT_SIDE_TAB[1])]
    edge(p, "u", TOP - T, x1, x0, [(a, b, T) for a, b in WALL_TOP_TABS], +1)
    p += [(x0, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[0]), (x0, WALL_END_TAB[0])]
    eng = []                                              # precast retaining-wall panel joints
    z = T + 12
    while z < TOP - T - 4:
        eng.append([(x0 + 1, z), (x1 - 6, z)])
        z += 12
    x = x0 + 15
    while x < x1 - 8:
        eng.append([(x, T + 1), (x, TOP - T - 3)])
        x += 15
    return Panel(name, p, "XZ", y_off, engrave=eng, labels=[((x0 + x1) / 2, 10, "RETAINING WALL", 3.5)])


def tr_abutment():
    p = []
    y0, y1 = STRIP_Y0 + T, STRIP_Y1 - T
    edge(p, "u", T, y0, y1, [(a, b, T) for a, b in ABUT_BOT_TABS], -1)
    p += [(y1, ABUT_SIDE_TAB[0]), (STRIP_Y1, ABUT_SIDE_TAB[0]), (STRIP_Y1, ABUT_SIDE_TAB[1]), (y1, ABUT_SIDE_TAB[1])]
    edge(p, "u", TOP - T, y1, y0, [(a, b, T) for a, b in ABUT_TOP_TABS], +1)
    p += [(y0, ABUT_SIDE_TAB[1]), (STRIP_Y0, ABUT_SIDE_TAB[1]), (STRIP_Y0, ABUT_SIDE_TAB[0]), (y0, ABUT_SIDE_TAB[0])]
    return Panel("viaduct_abutment", p, "YZ", TR_ABUT_X, labels=[(YC, 52, "ABUTMENT", 4)])


def transition_module():
    tt = list(TOP_TABS_X)
    cx = (TR_TOP_X - T - 0.05, TR_TOP_X + 0.05)
    side_slot = rect(cx[0], SIDE_TAB[0] - 0.05, cx[1], SIDE_TAB[1] + 0.05)
    front_top = [(L, HF), (TR_TOP_X + (TOP - T - HF), HF), (TR_TOP_X, TOP - T)]
    back_top = [(L, TOP), (TR_TOP_X, TOP), (TR_TOP_X, TOP - T)]
    for prof in (front_top, back_top):
        for a, b in sorted(tt, reverse=True):
            prof += [(b, TOP - T), (b, TOP), (a, TOP), (a, TOP - T)]
        prof.append((0, TOP - T))
    slots = [rect(cx[0], a - 0.05, cx[1], b + 0.05) for a, b in CROSS_BOTTOM_TABS]
    for yw in (STRIP_Y0, STRIP_Y1 - T):
        slots += [rect(a - 0.05, yw - 0.05, b + 0.05, yw + T + 0.05) for a, b in WALL_BOTTOM_TABS]
    slots += [rect(TR_ABUT_X - 0.05, a - 0.05, TR_ABUT_X + T + 0.05, b + 0.05) for a, b in ABUT_BOT_TABS]
    return [
        base_plate(END_TABS, PIER_TABS + BACK_TABS, slots, name="transition_base_plate"),
        tr_top_plate(),
        apron("transition_front_apron", 0.0, front_top, SIDE_TAB, FRONT_TAB, [side_slot]),
        apron("transition_back_apron", D - T, back_top, SIDE_TAB, SIDE_TAB, [side_slot]),
        end_standard("standard_end_plate", 0.0),
        cross_plate(),
        retaining_wall("retaining_wall_front", STRIP_Y0),
        retaining_wall("retaining_wall_back", STRIP_Y1 - T),
        tr_abutment(),
        end_pier("pier_end_plate_R", L - T),
        end_back("back_end_plate_R", L - T),
    ]


# ----------------------------------------------------------------------------
# SVG output
# ----------------------------------------------------------------------------
def write_svg(path, panels, title, note_qty):
    gap = 6.0
    sheet_w = L + 2 * gap
    placed = []          # (panel, ox, oy) in sheet mm; v flipped
    y = gap + 40
    row = []
    row_h = 0
    x = gap

    def flush():
        nonlocal y, row, row_h, x
        for pnl, px in row:
            placed.append((pnl, px, y))
        y += row_h + gap
        row, row_h, x = [], 0, gap

    order = sorted(panels, key=lambda p: -(p.bbox()[2] - p.bbox()[0]) * (p.bbox()[3] - p.bbox()[1]))
    for pnl in order:
        u0, v0, u1, v1 = pnl.bbox()
        w, h = u1 - u0, v1 - v0
        if x + w > sheet_w - gap + 0.01:
            flush()
        row.append((pnl, x))
        x += w + gap
        row_h = max(row_h, h)
    flush()
    sheet_h = y + gap

    def tr(pnl, ox, oy, pt):
        u0, v0, u1, v1 = pnl.bbox()
        return (ox + pt[0] - u0, oy + (v1 - pt[1]))

    def pathd(pts, close=True):
        d = "M" + " L".join("%.3f,%.3f" % p for p in pts)
        return d + (" Z" if close else "")

    sw = 0.1
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" '
           'viewBox="0 0 %.2f %.2f">' % (sheet_w, sheet_h, sheet_w, sheet_h)]
    g_cut, g_in, g_red = [], [], []
    for pnl, ox, oy in placed:
        g_cut.append('<path id="%s" d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                     % (pnl.name, pathd([tr(pnl, ox, oy, p) for p in pnl.outline]), PURPLE, sw))
        for h in pnl.holes:
            g_in.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                        % (pathd([tr(pnl, ox, oy, p) for p in h]), GREEN, sw))
        for e in pnl.engrave:
            g_red.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                         % (pathd([tr(pnl, ox, oy, p) for p in e], close=len(e) > 2), RED, sw))
        for (u, v, text, size) in pnl.labels:
            px, py = tr(pnl, ox, oy, (u, v))
            g_red.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" '
                         'text-anchor="middle" fill="%s">%s</text>' % (px, py, size, RED, text))
    notes = [title, "5mm Material or 1/4\" Ply 0.22\" Actual   -   %s" % note_qty,
             "Purple... Adjust Kerf OUT    Green... Adjust Kerf IN    Red... Engrave or Delete, do not cut."]
    for i, t in enumerate(notes):
        g_red.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" fill="%s">%s</text>'
                     % (gap, gap + 10 + i * 9, 8 if i == 0 else 6, RED, t))
    out.append('<g id="Cut_Outside_Purple">' + "".join(g_cut) + "</g>")
    out.append('<g id="Cut_Inside_Green">' + "".join(g_in) + "</g>")
    out.append('<g id="Engrave_Red">' + "".join(g_red) + "</g>")
    out.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    return sheet_w, sheet_h


def out_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, "ttrak_output", "portal_bridge", "laser")
    os.makedirs(d, exist_ok=True)
    return d


# ----------------------------------------------------------------------------
# Blender builder (used by portal_bridge.py for renders)
# ----------------------------------------------------------------------------
def to_blender(panels, coll, ox, oz, mat="ply"):
    """Extrude each panel 5 mm and place it in module coords (z shifted by oz)."""
    import ttrak_city as tc
    from ttrak_city import prism, _boolean, mesh_obj
    objs = []
    for pnl in panels:
        if pnl.plane == "XY":
            sh = prism([(u + ox, v) for u, v in pnl.outline], "z", pnl.off + oz, pnl.off + oz + T)
            hs = [prism([(u + ox, v) for u, v in h], "z", pnl.off + oz - 1, pnl.off + oz + T + 1)
                  for h in pnl.holes]
        elif pnl.plane == "XZ":
            sh = prism([(u + ox, v + oz) for u, v in pnl.outline], "y", pnl.off, pnl.off + T)
            hs = [prism([(u + ox, v + oz) for u, v in h], "y", pnl.off - 1, pnl.off + T + 1) for h in pnl.holes]
        else:
            sh = prism([(u, v + oz) for u, v in pnl.outline], "x", pnl.off + ox, pnl.off + ox + T)
            hs = [prism([(u, v + oz) for u, v in h], "x", pnl.off + ox - 1, pnl.off + ox + T + 1)
                  for h in pnl.holes]
        concrete = any(k in pnl.name for k in ("retaining", "abutment", "pier"))
        o = mesh_obj("ply_" + pnl.name, sh, coll, "concrete2" if concrete else mat)
        _boolean(o, "DIFFERENCE", hs)
        objs.append(o)
    return objs


def write_all():
    global TOP
    base = out_dir()
    done = []
    for label, top in (("70mm_template", 70.09), ("63.5mm_2.5in", 63.5)):
        TOP = top
        d = os.path.join(base, label)
        os.makedirs(d, exist_ok=True)
        h = "module height %.2f mm" % top
        write_svg(os.path.join(d, "portal_lowered_box_618x330_%s.svg" % label), arch_module(),
                  "Portal North Bridge - lowered box (3 ARCH + 1 VIADUCT module), " + h,
                  "cut 4 sets")
        write_svg(os.path.join(d, "portal_transition_618x330_%s.svg" % label), transition_module(),
                  "Portal North Bridge - TRANSITION module (west + east), " + h,
                  "cut 2 sets - assemble the east one as a mirror image (flip every part)")
        done.append(d)
    TOP = 70.09
    return done


if __name__ == "__main__":
    print("\n".join(write_all()))
