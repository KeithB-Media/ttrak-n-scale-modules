"""
Laser-cut plywood module boxes for the river-gap deck-girder bridge (river_bridge.py).

The same conventions as the Portal set (portal_laser.py), from the "Double 618 x 330 T Track
Module" laser template: 5 mm ply, 618 x 330 footprint, 70.09 mm (or 63.5 mm) module height,
the template finger-joint positions and colours (purple = outside cut, kerf OUT; green = inside
cut, kerf IN; red = engrave or delete).

One box design serves both modules: cut 2 sets and assemble module B (East) as a mirror image
(flip every part), exactly like the Portal transitions.

Module A, seen from the front (x = 0 is the outer end, x = 618 the joint with module B):
  * TRANSITION  x 0..100: full-depth track-level top plate + template standard end plate, so the
                outer end joins any T-TRAK module.  A cross plate at x 95..100 closes the box.
                x 100..146: the track runs on an embankment between two concrete wing walls to the
                abutment: backwall (face at 122.25), bridge seat plate, abutment face plate (142).
  * DROPPED SECTION x 142..618: the base plate is the river bed.  The printed piers stand on it,
                the printed deck girder spans sit on the piers and on the abutment seat.
                A low front apron holds the water pour.  Three cliff ribs and the joint end plate
                carry foam / plaster for the rock cliff; the back apron follows the cliff skyline.
  * The joint pier is split: each module's half stands on its own base plate at the module end.

The printed bridge parts are the same as in river_bridge.py (girders, handrails), except the
piers: they stand on the 5 mm base plate instead of in a printed socket, so this script also writes
pier STLs sized for each module height.

Run:  python river_laser.py
Output: ttrak_output/river_bridge/laser/<70mm_template | 63.5mm_2.5in>/
"""

import os
import math
import numpy as np

import portal_laser as pl
from portal_laser import edge, rect, circle, stadium, Panel, PURPLE, GREEN, RED
import river_bridge as rb

T = 5.0
L = 618.0
D = 330.0
TOP = 70.09                     # set per height in write_all()
HF = 16.0                       # low front apron (water is 3 mm on the base plate, top at 8)
SIDE_TAB = pl.SIDE_TAB          # template corner tab band (20.85 .. 43.54)
LONG_TABS = pl.LONG_TABS
END_TABS = pl.END_TABS
FOOT_D = pl.FOOT_D
FEET = [(24.5, 24.5), (L - 50.0, 24.5), (24.5, D - 24.5), (L - 24.5, D - 24.5)]  # front-right foot moved clear of the joint pier
C = 0.05                        # slot clearance per side

# transition
TR_TOP_X = 100.0                # full-depth top plate 0..100; cross plate 95..100
TOP_TABS_X = [(25.0, 55.0)]
W0, W1 = 11.0, 123.0            # wing walls: front wall y 11..16, back wall y 118..123
BACKWALL_X = rb.XA - rb.BEAR - 0.5      # 122.25 backwall face (girders start 0.5 mm after it)
XA = rb.XA                      # 142 abutment face
WALL_X1 = XA + 4.0              # wing wall noses stand 4 mm proud of the abutment face
CROSS_TOP_TABS = [(150.0, 200.0), (250.0, 300.0)]
CROSS_BOTTOM_TABS = [(40.0, 70.0), (140.0, 180.0), (240.0, 280.0)]
WALL_END_TAB = (20.0, 40.0)
WALL_TOP_TABS = [(104.0, 116.0)]
WALL_BOTTOM_TABS = [(103.0, 114.0), (124.0, 134.0)]
BW_TOP_TABS = [(35.0, 55.0), (79.0, 99.0)]
BW_BOTTOM_TABS = [(30.0, 50.0), (84.0, 104.0)]
BW_SIDE_TAB = (25.0, 45.0)
SEAT_SIDE_TAB = (125.0, 134.0)
ABUT_SIDE_TAB = (15.0, 30.0)
ABUT_BOTTOM_TABS = [(30.0, 50.0), (84.0, 104.0)]

# cliff
CLIFF = 40.0                    # back skyline rises this much above the track base
Y_BANK = 165.0                  # foot of the cliff (river bank) on the ribs
RIB_X = [230.0, 360.0, 490.0]
RIB_BOTTOM_TABS = [(200.0, 230.0), (270.0, 300.0)]
RIB_BACK_TAB = (20.0, 40.0)
JOINT_Y0 = rb.PIER_YC + (rb.PIER_W + 2 * rb.BATTER) / 2 + 2.0    # 123: joint end plate starts behind the half pier
JOINT_TABS = [(180.0, 215.0), (270.0, 300.0)]


def seat_z():
    return TOP + rb.SEAT_Z                       # top of the bridge seat (module coords)


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def cliff_h(x):
    """Smooth cliff height at the back edge (module coords, from the table)."""
    return TOP + CLIFF * smoothstep(TR_TOP_X, 230.0, x)


def rib_z(x, y):
    t = min(max((y - Y_BANK) / (D - T - Y_BANK), 0.0), 1.0)
    return T + (cliff_h(x) - T) * (1 - (1 - t) ** 2.8)


_noise = rb.ValueNoise(7)


def skyline(x):
    """Back apron top: the cliff with a rocky, irregular skyline (never below the ribs)."""
    bump = 3.0 + 3.0 * float(_noise.fbm(np.array(x), np.array(0.0), 40, 3))
    return cliff_h(x) + max(bump, 0.0) * smoothstep(TR_TOP_X + 10, 160, x)


def slot_x(x0, x1, y0, y1):
    return rect(x0 - C, y0 - C, x1 + C, y1 + C)


# ----------------------------------------------------------------------------
# Parts (module A coordinates)
# ----------------------------------------------------------------------------
def base_plate():
    p = []
    edge(p, "u", 0, 0, L, [(a, b, -T) for a, b in LONG_TABS], -1)          # front
    edge(p, "v", L, 0, D, [(a, b, -T) for a, b in JOINT_TABS], +1)         # joint end
    edge(p, "u", D, L, 0, [(a, b, -T) for a, b in LONG_TABS], +1)          # back
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)           # outer end
    holes = [circle(x, y, FOOT_D) for x, y in FEET]
    xc0 = TR_TOP_X - T
    holes += [slot_x(xc0, TR_TOP_X, a, b) for a, b in CROSS_BOTTOM_TABS]
    for yw in (W0, W1 - T):
        holes += [slot_x(a, b, yw, yw + T) for a, b in WALL_BOTTOM_TABS]
    holes += [slot_x(BACKWALL_X - T, BACKWALL_X, a, b) for a, b in BW_BOTTOM_TABS]
    holes += [slot_x(XA - T, XA, a, b) for a, b in ABUT_BOTTOM_TABS]
    for x in RIB_X:
        holes += [slot_x(x, x + T, a, b) for a, b in RIB_BOTTOM_TABS]
    # engraved guides: pier footprints, girder centre lines, river bank
    eng = []
    Lb, Wb = rb.PIER_T + 2 * rb.BATTER, rb.PIER_W + 2 * rb.BATTER
    for xc in rb.PIERS_XD:
        eng.append(stadium_y(xc, rb.PIER_YC, Lb, Wb))
    full = stadium_y(L, rb.PIER_YC, Lb, Wb)
    k = len(full) // 2
    eng.append([(min(q[0], L), q[1]) for q in full[k - 1:]] + [(L, full[k - 1][1])])   # joint half pier
    for yc in rb.TRACK_Y:
        eng.append([(BACKWALL_X, yc), (L, yc)])
    eng.append([(XA + 20, Y_BANK), (L, Y_BANK)])
    labels = [(380, 140, "RIVER BED - PIERS ON THE ENGRAVED OUTLINES", 6),
              (380, 250, "CLIFF (FOAM / PLASTER ON THE RIBS)", 6), (50, 200, "UNDER TOP PLATE", 5),
              (300, 12, "FRONT", 5)]
    return Panel("base_plate", p, "XY", 0.0, holes, eng, labels)


def stadium_y(xc, yc, Lx, Wy, n=12):
    """Pier outline in plan (round noses at +-y) as a closed polyline."""
    r = Lx / 2
    pts = []
    for i in range(n + 1):
        a = math.pi * i / n
        pts.append((xc + r * math.cos(a), yc + Wy / 2 - r + r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi + math.pi * i / n
        pts.append((xc + r * math.cos(a), yc - Wy / 2 + r + r * math.sin(a)))
    return pts


def top_plate():
    p = []
    edge(p, "u", 0, 0, TR_TOP_X, [(a, b, -T) for a, b in TOP_TABS_X], -1)              # front
    p += [(TR_TOP_X, 0), (TR_TOP_X, W0)]
    edge(p, "u", W0, TR_TOP_X, BACKWALL_X, [(a, b, -T) for a, b in WALL_TOP_TABS], -1)  # strip front
    edge(p, "v", BACKWALL_X, W0, W1, [(a, b, -T) for a, b in BW_TOP_TABS], +1)          # strip end
    edge(p, "u", W1, BACKWALL_X, TR_TOP_X, [(a, b, -T) for a, b in WALL_TOP_TABS], +1)  # strip back
    edge(p, "v", TR_TOP_X, W1, D, [(a, b, -T) for a, b in CROSS_TOP_TABS], +1)
    edge(p, "u", D, TR_TOP_X, 0, [(a, b, -T) for a, b in TOP_TABS_X], +1)               # back
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)                         # outer end
    holes = [circle(x, y, 2.8) for x in (15.0, 62.0) for y in rb.TRACK_Y]               # feeders / screws
    eng = [[(0, yc), (BACKWALL_X, yc)] for yc in rb.TRACK_Y]
    return Panel("top_plate", p, "XY", TOP - T, holes, eng, [(50, 220, "TOP", 6)])


def front_apron():
    p = []
    edge(p, "u", T, 0, L, [(a, b, T) for a, b in LONG_TABS], -1)
    p += [(L, T), (L, HF)]
    prof = [(TR_TOP_X + (TOP - T - HF), HF), (TR_TOP_X, TOP - T)]
    for a, b in sorted(TOP_TABS_X, reverse=True):
        prof += [(b, TOP - T), (b, TOP), (a, TOP), (a, TOP - T)]
    p += prof + [(0, TOP - T)]
    lo, hi = SIDE_TAB
    p += [(0, hi), (T, hi), (T, lo), (0, lo), (0, T)]
    holes = [rect(TR_TOP_X - T - C, SIDE_TAB[0] - C, TR_TOP_X + C, SIDE_TAB[1] + C)]
    return Panel("front_apron", p, "XZ", 0.0, holes, labels=[(380, 10.5, "FRONT APRON", 3.5)])


def back_apron():
    p = []
    edge(p, "u", T, 0, L, [(a, b, T) for a, b in LONG_TABS], -1)
    lo, hi = SIDE_TAB
    p += [(L, T), (L, lo), (L - T, lo), (L - T, hi), (L, hi)]
    x = L
    while x > TR_TOP_X + 0.01:
        p.append((x, skyline(x)))
        x -= 6.0
    p += [(TR_TOP_X, TOP), (TR_TOP_X, TOP - T)]
    for a, b in sorted(TOP_TABS_X, reverse=True):
        p += [(b, TOP - T), (b, TOP), (a, TOP), (a, TOP - T)]
    p += [(0, TOP - T), (0, hi), (T, hi), (T, lo), (0, lo), (0, T)]
    holes = [rect(TR_TOP_X - T - C, SIDE_TAB[0] - C, TR_TOP_X + C, SIDE_TAB[1] + C)]
    holes += [rect(x - C, RIB_BACK_TAB[0] - C, x + T + C, RIB_BACK_TAB[1] + C) for x in RIB_X]
    return Panel("back_apron_cliff", p, "XZ", D - T, holes, labels=[(380, 2 * T + 6, "BACK APRON - CLIFF SKYLINE", 5)])


def end_standard():
    pnl = pl.end_standard("standard_end_plate", 0.0)
    return pnl


def cross_plate():
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in CROSS_BOTTOM_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", TOP - T, D - T, T, [(a, b, T) for a, b in CROSS_TOP_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    holes = [rect(y - C, WALL_END_TAB[0] - C, y + T + C, WALL_END_TAB[1] + C) for y in (W0, W1 - T)]
    holes.append(stadium(200, 290, 15, 35))                                  # wiring
    return Panel("cross_plate", p, "YZ", TR_TOP_X - T, holes,
                 labels=[(230, TOP - 15, "CROSS PLATE - FOAM SLOPES ON THE RIVER SIDE", 3.5)])


def wing_wall(name, y_off):
    x0, x1 = TR_TOP_X, WALL_X1
    p = []
    edge(p, "u", T, x0, x1, [(a, b, T) for a, b in WALL_BOTTOM_TABS], -1)
    p += [(x1, TOP), (BACKWALL_X, TOP)]
    edge(p, "u", TOP - T, BACKWALL_X, x0, [(a, b, T) for a, b in WALL_TOP_TABS], +1)
    p += [(x0, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[0]), (x0, WALL_END_TAB[0])]
    sz = seat_z()
    holes = [rect(BACKWALL_X - T - C, BW_SIDE_TAB[0] - C, BACKWALL_X + C, BW_SIDE_TAB[1] + C),
             rect(SEAT_SIDE_TAB[0] - C, sz - T - C, SEAT_SIDE_TAB[1] + C, sz + C),
             rect(XA - T - C, ABUT_SIDE_TAB[0] - C, XA + C, ABUT_SIDE_TAB[1] + C)]
    eng = []                                              # board-formed concrete lines
    z = T + 6
    while z < TOP - 3:
        eng.append([(x0 + 1, z), (x1 - 1, z)])
        z += 5.5
    return Panel(name, p, "XZ", y_off, holes, eng, [((x0 + x1) / 2, 8, "WING WALL", 3)])


def backwall():
    y0, y1 = W0 + T, W1 - T
    p = []
    edge(p, "u", T, y0, y1, [(a, b, T) for a, b in BW_BOTTOM_TABS], -1)
    p += [(y1, BW_SIDE_TAB[0]), (W1, BW_SIDE_TAB[0]), (W1, BW_SIDE_TAB[1]), (y1, BW_SIDE_TAB[1])]
    edge(p, "u", TOP - T, y1, y0, [(a, b, T) for a, b in BW_TOP_TABS], +1)
    p += [(y0, BW_SIDE_TAB[1]), (W0, BW_SIDE_TAB[1]), (W0, BW_SIDE_TAB[0]), (y0, BW_SIDE_TAB[0])]
    return Panel("abutment_backwall", p, "YZ", BACKWALL_X - T, labels=[(67, 52, "BACKWALL", 4)])


def seat_plate():
    y0, y1 = W0 + T, W1 - T
    x0, x1 = BACKWALL_X, XA - T
    a, b = SEAT_SIDE_TAB
    p = [(x0, y0), (a, y0), (a, W0), (b, W0), (b, y0), (x1, y0), (x1, y1), (b, y1), (b, W1), (a, W1),
         (a, y1), (x0, y1)]
    return Panel("bridge_seat_plate", p, "XY", seat_z() - T, labels=[((x0 + x1) / 2, 67, "SEAT", 3)])


def abutment_face():
    y0, y1 = W0 + T, W1 - T
    sz = seat_z()
    p = []
    edge(p, "u", T, y0, y1, [(a, b, T) for a, b in ABUT_BOTTOM_TABS], -1)
    p += [(y1, ABUT_SIDE_TAB[0]), (W1, ABUT_SIDE_TAB[0]), (W1, ABUT_SIDE_TAB[1]), (y1, ABUT_SIDE_TAB[1]),
          (y1, sz), (y0, sz),
          (y0, ABUT_SIDE_TAB[1]), (W0, ABUT_SIDE_TAB[1]), (W0, ABUT_SIDE_TAB[0]), (y0, ABUT_SIDE_TAB[0])]
    eng = []
    z = T + 6
    while z < sz - 3:
        eng.append([(y0 + 1, z), (y1 - 1, z)])
        z += 5.5
    return Panel("abutment_face", p, "YZ", XA - T, engrave=eng, labels=[(67, 12, "ABUTMENT FACE", 3.5)])


def rib(i, x):
    ys = np.arange(Y_BANK, D - T + 0.01, 5.0)
    zs = [rib_z(x, y) for y in ys]
    y_front = next(y for y, z in zip(ys, zs) if z >= T + 6)
    p = []
    edge(p, "u", T, y_front, D - T, [(a, b, T) for a, b in RIB_BOTTOM_TABS], -1)
    p += [(D - T, RIB_BACK_TAB[0]), (D, RIB_BACK_TAB[0]), (D, RIB_BACK_TAB[1]), (D - T, RIB_BACK_TAB[1])]
    for y, z in reversed(list(zip(ys, zs))):
        if y >= y_front:
            p.append((y, z))
    p.append((y_front, T))
    return Panel("cliff_rib_%d" % (i + 1), p, "YZ", x, labels=[((y_front + D) / 2 + 20, T + 6, "RIB %d" % (i + 1), 4)])


def joint_end():
    p = []
    edge(p, "u", T, JOINT_Y0, D - T, [(a, b, T) for a, b in JOINT_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    y = D - T
    while y > Y_BANK - 0.01:
        p.append((y, max(rib_z(L, y), HF)))
        y -= 5.0
    p += [(JOINT_Y0, HF)]
    return Panel("joint_end_plate", p, "YZ", L - T, labels=[(260, T + 6, "JOINT END", 4)])


def module():
    return [base_plate(), top_plate(), front_apron(), back_apron(), end_standard(), cross_plate(),
            wing_wall("wing_wall_front", W0), wing_wall("wing_wall_back", W1 - T), backwall(),
            seat_plate(), abutment_face()] + [rib(i, x) for i, x in enumerate(RIB_X)] + [joint_end()]


# ----------------------------------------------------------------------------
# 3D check (manifold): parts must not overlap, and every slot / notch must be filled
# ----------------------------------------------------------------------------
def solid(pnl):
    from manifold3d import Manifold, CrossSection

    def cs(pts):
        return CrossSection([pts])
    s = cs(pnl.outline)
    for h in pnl.holes:
        s = s - cs(h)
    m = Manifold.extrude(s, T)
    if pnl.plane == "XY":
        return m.translate((0, 0, pnl.off))
    if pnl.plane == "XZ":          # (u,v,w) -> (u, w, v)
        return m.transform([[1, 0, 0, 0], [0, 0, 1, pnl.off], [0, 1, 0, 0]])
    return m.transform([[0, 0, 1, pnl.off], [1, 0, 0, 0], [0, 1, 0, 0]])   # YZ


def check(panels):
    from manifold3d import Manifold
    sols = [(p.name, solid(p)) for p in panels]
    worst = 0.0
    for i in range(len(sols)):
        for j in range(i + 1, len(sols)):
            v = (sols[i][1] ^ sols[j][1]).volume()
            if v > 0.5:
                print("   OVERLAP %s / %s: %.1f mm3" % (sols[i][0], sols[j][0], v))
            worst = max(worst, v)
    allp = Manifold.batch_boolean([s for _, s in sols], __import__("manifold3d").OpType.Add)
    bb = allp.bounding_box()
    # base plate notches + every slot must be filled by another part
    unfilled = 0
    base = next(s for n, s in sols if n == "base_plate")
    full = Manifold.cube((L, D, T))
    gaps = full - base
    feet = Manifold.batch_boolean([Manifold.cylinder(T + 2, FOOT_D / 2 + 0.5).translate((x, y, -1)) for x, y in FEET],
                                  __import__("manifold3d").OpType.Add)
    gaps = gaps - feet
    others = Manifold.batch_boolean([s for n, s in sols if n != "base_plate"], __import__("manifold3d").OpType.Add)
    empty = (gaps - others).volume()
    return worst, (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]), empty


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------
def pier_stls(d, label):
    """Piers re-sized to stand on the base plate (no socket) for this module height."""
    bed, sock = rb.BED, rb.SOCKET
    rb.BED, rb.SOCKET = -(TOP - T), 0.0
    try:
        rb.export(rb.pier(), os.path.join(d, "pier_full_on_ply_%s.stl" % label))
        rb.export(rb.pier(half=True), os.path.join(d, "pier_joint_half_on_ply_%s.stl" % label))
        h = rb.SEAT_Z - rb.BED
    finally:
        rb.BED, rb.SOCKET = bed, sock
    return h


def nest(panels_per_module, n_modules):
    import portal_nest as pn
    parts = []
    for i in range(n_modules):
        parts += [(("A", "B")[i], p) for p in panels_per_module]
    return pn.pack(parts)


def write_sheet(path, placed, n, m, label):
    import portal_nest as pn
    cut, inner, eng = [], [], []
    sw = 0.1
    for tag, p, x, y, rot in placed:
        f = pn.xf(p, x, y, rot)
        cut.append('<path id="%s_%s" d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                   % (tag, p.name, pn.d_of([f(q) for q in p.outline]), PURPLE, sw))
        for h in p.holes:
            inner.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                         % (pn.d_of([f(q) for q in h]), GREEN, sw))
        for e in p.engrave:
            eng.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                       % (pn.d_of([f(q) for q in e], close=len(e) > 2), RED, sw))
        u0, v0, u1, v1 = p.bbox()
        cx, cy = f(((u0 + u1) / 2, (v0 + v1) / 2))
        size = 4.0 if min(u1 - u0, v1 - v0) > 30 else 2.5
        rot_attr = ' transform="rotate(90 %.2f %.2f)"' % (cx, cy) if rot else ""
        eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" '
                   'text-anchor="middle" fill="%s"%s>%s %s</text>'
                   % (cx, cy, size, RED, rot_attr, tag, p.name.replace("_", " ")))
    note = ("River bridge pair - %s - sheet %d of %d - 600 x 3000 mm - 5mm ply. "
            "Purple: cut, kerf OUT. Green: inside cut, kerf IN. Red: engrave or delete. "
            "A = West module, B = East module (assemble B as a mirror image: flip every part)." % (label, n, m))
    eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="4" fill="%s">%s</text>'
               % (pn.MARGIN, pn.SHEET_H - 1.5, RED, note))
    svg = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">'
           % (pn.SHEET_W, pn.SHEET_H, pn.SHEET_W, pn.SHEET_H),
           '<g id="Cut_Outside_Purple">' + "".join(cut) + "</g>",
           '<g id="Cut_Inside_Green">' + "".join(inner) + "</g>",
           '<g id="Engrave_Red">' + "".join(eng) + "</g>", "</svg>"]
    with open(path, "w") as fh:
        fh.write("\n".join(svg))


def preview(svg_path):
    try:
        import cairosvg
    except ImportError:
        return None
    png = svg_path[:-4] + "_preview.png"
    cairosvg.svg2png(url=svg_path, write_to=png, output_width=2400, background_color="white")
    return png


def write_all():
    global TOP
    base = os.path.join(rb.OUT, "laser")
    report = []
    for label, top in (("70mm_template", 70.09), ("63.5mm_2.5in", 63.5)):
        TOP = top
        pl.TOP = top
        d = os.path.join(base, label)
        os.makedirs(os.path.join(d, "sheets_600x3000"), exist_ok=True)
        for sub in (d, os.path.join(d, "sheets_600x3000")):
            for f in os.listdir(sub):
                if f.endswith((".svg", ".png", ".stl")):
                    os.remove(os.path.join(sub, f))
        panels = module()
        worst, size, empty = check(panels)
        svg = os.path.join(d, "river_module_618x330_%s.svg" % label)
        pl.write_svg(svg, panels, "River-gap girder bridge - one module box (cut 2: West + East), module height %.2f mm"
                     % top, "cut 2 sets - assemble the East module as a mirror image (flip every part)")
        preview(svg)
        sheets = nest(panels, 2)
        for i, placed in enumerate(sheets):
            sp = os.path.join(d, "sheets_600x3000", "river_pair_sheet_%d_of_%d_%s.svg" % (i + 1, len(sheets), label))
            write_sheet(sp, placed, i + 1, len(sheets), "module height %.2f mm" % top)
            preview(sp)
        ph = pier_stls(d, label)
        report.append((label, size, worst, empty, len(sheets), [len(s) for s in sheets], ph))
    TOP = pl.TOP = 70.09
    return report


if __name__ == "__main__":
    for label, size, worst, empty, ns, counts, ph in write_all():
        print("%s: box %.1f x %.1f x %.1f mm | max overlap %.2f mm3 | unfilled base notches %.2f mm3 | "
              "%d sheet(s) %s | printed pier height %.1f mm" % (label, *size, worst, empty, ns, counts, ph))
