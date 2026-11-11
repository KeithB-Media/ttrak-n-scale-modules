"""
Laser-cut plywood module boxes (bases) for the river-crossing deck-girder bridge (river_bridge.py).

The same conventions as the Portal set (portal_laser.py), from the "Double 618 x 330 T Track
Module" laser template: 5 mm ply, 618 x 330 footprint, the template finger-joint positions and
colours (purple = outside cut, kerf OUT; green = inside cut, kerf IN; red = engrave or delete).

One box design serves both modules: cut 2 sets and assemble module B (East) as a mirror image
(flip every part), like the Portal transitions.

Module A, seen from the front (x = 0 is the outer end, x = 618 the joint with module B):
  * TRANSITION  x 0..100: full-depth track-level top plate + template standard end plate, so the
                outer end joins any T-TRAK module.  A cross plate at x 95..100 closes the box.
                x 100..146: the track runs on an embankment between two concrete wing walls to the
                abutment: backwall (face at 122.25), bridge seat plate, abutment face (142).
  * RIVER x 142..618: the base plate is the river bed.  Low front and back aprons (16 mm) hold the
                water and leave the river open to view from both sides.  The printed piers snap into
                the base plate; the printed girders pin into the pier caps and the seat plate.
  * FEET        4 x M6: the bolt goes up through a 6.6 mm hole in the base into a printed nut block
                glued on top.  The box is built FOOT_NOM (12 mm) lower than the module height, and
                the thumbwheel feet make up the difference and level the module.

Run:  python river_laser.py   (also run by river_bridge.py)
Output: ttrak_output/river_bridge/laser/<70mm_template | 63.5mm_2.5in>/
"""

import os
import math

import portal_laser as pl
from portal_laser import edge, rect, circle, stadium, Panel, PURPLE, GREEN, RED
import river_bridge as rb

T = 5.0
L = rb.MW
D = rb.MD
BOX = 58.09                     # box height (underside of base -> track base); set per module height
HF = 16.0                       # low aprons along the river (3 mm water on the base plate)
LOW_TAB = (8.0, 13.0)           # joint end plate <-> back apron tab band
SIDE_TAB = pl.SIDE_TAB          # template corner tab band (20.85 .. 43.54)
LONG_TABS = pl.LONG_TABS
END_TABS = pl.END_TABS
C = 0.05                        # slot clearance per side

FEET = [(24.5, 24.5), (565.0, 22.0), (24.5, D - 24.5), (L - 24.5, D - 24.5)]
FOOT_ROCK = (14.0, 12.0)        # nut block half sizes (engraved outline)

# transition
TR_TOP_X = 100.0
TOP_TABS_X = [(25.0, 55.0)]
W0, W1 = 11.0, 123.0            # wing walls: front y 11..16, back y 118..123
BACKWALL_X = rb.BACKWALL_X      # 122.25
XA = rb.XA                      # 142
WALL_X1 = XA + 4.0
CROSS_TOP_TABS = [(150.0, 200.0), (250.0, 300.0)]
CROSS_BOTTOM_TABS = [(40.0, 70.0), (140.0, 180.0), (240.0, 280.0)]
WALL_END_TAB = (20.0, 40.0)
WALL_TOP_TABS = [(104.0, 116.0)]
WALL_BOTTOM_TABS = [(103.0, 114.0), (124.0, 134.0)]
BW_TOP_TABS = [(35.0, 55.0), (79.0, 99.0)]
BW_BOTTOM_TABS = [(30.0, 50.0), (84.0, 104.0)]
BW_SIDE_TAB = (25.0, 40.0)
SEAT_SIDE_TAB = (125.0, 134.0)
ABUT_SIDE_TAB = (12.0, 24.0)
ABUT_BOTTOM_TABS = [(30.0, 50.0), (84.0, 104.0)]

JOINT_Y0 = rb.PIER_YC + (rb.PIER_W + 2 * rb.BATTER) / 2 + 2.0    # 123: joint end plate starts behind the half pier
JOINT_TABS = [(180.0, 215.0), (270.0, 300.0)]


def seat_z():
    return BOX + rb.SEAT_Z                       # top of the bridge seat (box coords)


def slot_x(x0, x1, y0, y1):
    return rect(x0 - C, y0 - C, x1 + C, y1 + C)


def ellipse(cx, cy, a, b, n=36):
    return [(cx + a * math.cos(2 * math.pi * i / n), cy + b * math.sin(2 * math.pi * i / n)) for i in range(n)]


def pier_outline(xc, n=16):
    """Pier footprint on the base plate (round noses at +-y)."""
    Lb, Wb = rb.PIER_T + 2 * rb.BATTER, rb.PIER_W + 2 * rb.BATTER
    r, yc = Lb / 2, rb.PIER_YC
    pts = [(xc + r * math.cos(math.pi * i / n), yc + Wb / 2 - r + r * math.sin(math.pi * i / n)) for i in range(n + 1)]
    pts += [(xc + r * math.cos(math.pi + math.pi * i / n), yc - Wb / 2 + r + r * math.sin(math.pi + math.pi * i / n))
            for i in range(n + 1)]
    return pts


# ----------------------------------------------------------------------------
# Parts (module A coordinates, z from the underside of the base)
# ----------------------------------------------------------------------------
def base_plate():
    p = []
    edge(p, "u", 0, 0, L, [(a, b, -T) for a, b in LONG_TABS], -1)          # front
    edge(p, "v", L, 0, D, [(a, b, -T) for a, b in JOINT_TABS], +1)         # joint end
    edge(p, "u", D, L, 0, [(a, b, -T) for a, b in LONG_TABS], +1)          # back
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)           # outer end
    holes = [circle(x, y, rb.M6_CLEAR, 24) for x, y in FEET]                # M6 foot bolts
    holes += [slot_x(TR_TOP_X - T, TR_TOP_X, a, b) for a, b in CROSS_BOTTOM_TABS]
    for yw in (W0, W1 - T):
        holes += [slot_x(a, b, yw, yw + T) for a, b in WALL_BOTTOM_TABS]
    holes += [slot_x(BACKWALL_X - T, BACKWALL_X, a, b) for a, b in BW_BOTTOM_TABS]
    holes += [slot_x(XA - T, XA, a, b) for a, b in ABUT_BOTTOM_TABS]
    for xc in rb.PIERS_XD:                                                  # pier snap pegs
        holes += [circle(xc, rb.PIER_YC + s * rb.PEG_DY, rb.PEG_HOLE_D, 24) for s in (-1, 1)]
    holes += [circle(L + rb.HALF_PEG_X, rb.PIER_YC + s * rb.PEG_DY, rb.PEG_HOLE_D, 24) for s in (-1, 1)]
    holes += [circle(x, y, rb.FEED_BORE, 20) for x, y in rb.feeder_points()]   # feeder wires
    eng = [pier_outline(xc) for xc in rb.PIERS_XD]
    half = pier_outline(L)
    eng.append([(min(x, L), y) for x, y in half])
    eng += [[(BACKWALL_X, yc), (L, yc)] for yc in rb.TRACK_Y]              # track centre lines
    eng += [ellipse(x, y, *FOOT_ROCK) for x, y in FEET]                    # nut blocks
    labels = [(380, 200, "RIVER BED", 8), (380, 180, "PIERS SNAP INTO THE 7 MM HOLES", 5),
              (380, 165, "4.5 MM HOLES: FEEDER WIRES", 4),
              (50, 200, "UNDER TOP PLATE", 5), (300, 12, "FRONT", 5)]
    return Panel("base_plate", p, "XY", 0.0, holes, eng, labels)


def top_plate():
    p = []
    edge(p, "u", 0, 0, TR_TOP_X, [(a, b, -T) for a, b in TOP_TABS_X], -1)
    p += [(TR_TOP_X, 0), (TR_TOP_X, W0)]
    edge(p, "u", W0, TR_TOP_X, BACKWALL_X, [(a, b, -T) for a, b in WALL_TOP_TABS], -1)
    edge(p, "v", BACKWALL_X, W0, W1, [(a, b, -T) for a, b in BW_TOP_TABS], +1)
    edge(p, "u", W1, BACKWALL_X, TR_TOP_X, [(a, b, -T) for a, b in WALL_TOP_TABS], +1)
    edge(p, "v", TR_TOP_X, W1, D, [(a, b, -T) for a, b in CROSS_TOP_TABS], +1)
    edge(p, "u", D, TR_TOP_X, 0, [(a, b, -T) for a, b in TOP_TABS_X], +1)
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in END_TABS], -1)
    holes = [circle(x, y, 2.8) for x in (15.0, 62.0) for y in rb.TRACK_Y]   # feeders / screws
    eng = [[(0, yc), (BACKWALL_X, yc)] for yc in rb.TRACK_Y]
    return Panel("top_plate", p, "XY", BOX - T, holes, eng, [(50, 220, "TOP", 6)])


def apron(name, y_off, joint_notch):
    p = []
    edge(p, "u", T, 0, L, [(a, b, T) for a, b in LONG_TABS], -1)
    if joint_notch:
        lo, hi = LOW_TAB
        p += [(L, T), (L, lo), (L - T, lo), (L - T, hi), (L, hi), (L, HF)]
    else:
        p += [(L, T), (L, HF)]
    prof = [(TR_TOP_X + (BOX - T - HF), HF), (TR_TOP_X, BOX - T)]
    for a, b in sorted(TOP_TABS_X, reverse=True):
        prof += [(b, BOX - T), (b, BOX), (a, BOX), (a, BOX - T)]
    p += prof + [(0, BOX - T)]
    lo, hi = SIDE_TAB
    p += [(0, hi), (T, hi), (T, lo), (0, lo), (0, T)]
    holes = [rect(TR_TOP_X - T - C, SIDE_TAB[0] - C, TR_TOP_X + C, SIDE_TAB[1] + C)]
    return Panel(name, p, "XZ", y_off, holes, labels=[(380, 10.5, name.upper().replace("_", " "), 3.5)])


def cross_plate():
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in CROSS_BOTTOM_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", BOX - T, D - T, T, [(a, b, T) for a, b in CROSS_TOP_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    holes = [rect(y - C, WALL_END_TAB[0] - C, y + T + C, WALL_END_TAB[1] + C) for y in (W0, W1 - T)]
    holes.append(stadium(200, 290, 12, 18 + min(14.0, BOX - T - 30)))       # wiring
    return Panel("cross_plate", p, "YZ", TR_TOP_X - T, holes,
                 labels=[(230, BOX - 12, "CROSS PLATE - FOAM SLOPES ON THE RIVER SIDE", 3.5)])


def wing_wall(name, y_off):
    x0, x1 = TR_TOP_X, WALL_X1
    p = []
    edge(p, "u", T, x0, x1, [(a, b, T) for a, b in WALL_BOTTOM_TABS], -1)
    p += [(x1, BOX), (BACKWALL_X, BOX)]
    edge(p, "u", BOX - T, BACKWALL_X, x0, [(a, b, T) for a, b in WALL_TOP_TABS], +1)
    p += [(x0, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[1]), (x0 - T, WALL_END_TAB[0]), (x0, WALL_END_TAB[0])]
    sz = seat_z()
    holes = [rect(BACKWALL_X - T - C, BW_SIDE_TAB[0] - C, BACKWALL_X + C, BW_SIDE_TAB[1] + C),
             rect(SEAT_SIDE_TAB[0] - C, sz - T - C, SEAT_SIDE_TAB[1] + C, sz + C),
             rect(XA - T - C, ABUT_SIDE_TAB[0] - C, XA + C, ABUT_SIDE_TAB[1] + C)]
    eng = []
    z = T + 6
    while z < BOX - 3:                                    # board-formed concrete lines
        eng.append([(x0 + 1, z), (x1 - 1, z)])
        z += 5.5
    return Panel(name, p, "XZ", y_off, holes, eng, [((x0 + x1) / 2, 8, "WING WALL", 3)])


def backwall():
    y0, y1 = W0 + T, W1 - T
    p = []
    edge(p, "u", T, y0, y1, [(a, b, T) for a, b in BW_BOTTOM_TABS], -1)
    p += [(y1, BW_SIDE_TAB[0]), (W1, BW_SIDE_TAB[0]), (W1, BW_SIDE_TAB[1]), (y1, BW_SIDE_TAB[1])]
    edge(p, "u", BOX - T, y1, y0, [(a, b, T) for a, b in BW_TOP_TABS], +1)
    p += [(y0, BW_SIDE_TAB[1]), (W0, BW_SIDE_TAB[1]), (W0, BW_SIDE_TAB[0]), (y0, BW_SIDE_TAB[0])]
    return Panel("abutment_backwall", p, "YZ", BACKWALL_X - T, labels=[(67, BOX - 14, "BACKWALL", 4)])


def seat_plate():
    y0, y1 = W0 + T, W1 - T
    x0, x1 = BACKWALL_X, XA - T
    a, b = SEAT_SIDE_TAB
    p = [(x0, y0), (a, y0), (a, W0), (b, W0), (b, y0), (x1, y0), (x1, y1), (b, y1), (b, W1), (a, W1),
         (a, y1), (x0, y1)]
    xp = XA - rb.BEAR + rb.SHOE_X                           # 127.75: girder pins
    holes = [circle(xp, yt + dy, rb.PIN_HOLE_D, 16) for yt in rb.TRACK_Y for dy in rb.PIN_DY]
    holes += [circle(XA - rb.BEAR + rb.FEED_X, yt, rb.FEED_BORE, 20) for yt in rb.TRACK_Y]   # feeder wires
    return Panel("bridge_seat_plate", p, "XY", seat_z() - T, holes, labels=[(131, 67, "SEAT", 3)])


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
    return Panel("abutment_face", p, "YZ", XA - T, engrave=eng, labels=[(67, sz - 6, "ABUTMENT FACE", 3.5)])


def joint_end():
    """Low end plate behind the joint half pier: holds the water, open view across the river."""
    p = []
    edge(p, "u", T, JOINT_Y0, D - T, [(a, b, T) for a, b in JOINT_TABS], -1)
    p += [(D - T, LOW_TAB[0]), (D, LOW_TAB[0]), (D, LOW_TAB[1]), (D - T, LOW_TAB[1]), (D - T, HF), (JOINT_Y0, HF)]
    return Panel("joint_end_plate", p, "YZ", L - T, labels=[(230, 10, "JOINT END", 4)])


def end_standard():
    """Template-style end plate (joins any T-TRAK module), wiring hole kept clear of the top plate."""
    p = []
    edge(p, "u", T, T, D - T, [(a, b, T) for a, b in END_TABS], -1)
    p += [(D - T, SIDE_TAB[0]), (D, SIDE_TAB[0]), (D, SIDE_TAB[1]), (D - T, SIDE_TAB[1])]
    edge(p, "u", BOX - T, D - T, T, [(a, b, T) for a, b in END_TABS], +1)
    p += [(T, SIDE_TAB[1]), (0, SIDE_TAB[1]), (0, SIDE_TAB[0]), (T, SIDE_TAB[0])]
    v1 = min(46.2, BOX - T - 6)
    holes = [stadium(120.4, 209.8, v1 - 22, v1)]
    return Panel("standard_end_plate", p, "YZ", 0.0, holes, labels=[(D / 2, 10, "STANDARD END PLATE", 5)])


def module():
    return [base_plate(), top_plate(), apron("front_apron", 0.0, False), apron("back_apron", D - T, True),
            end_standard(), cross_plate(),
            wing_wall("wing_wall_front", W0), wing_wall("wing_wall_back", W1 - T), backwall(),
            seat_plate(), abutment_face(), joint_end()]


def set_height(top):
    global BOX
    BOX = rb.box_h(top)
    pl.TOP = BOX                    # the template end plate is built to the box height


# ----------------------------------------------------------------------------
# 3D (manifold): parts as solids, checks, assembly for the renders
# ----------------------------------------------------------------------------
def solid(pnl):
    from manifold3d import Manifold, CrossSection
    s = CrossSection([pnl.outline])
    for h in pnl.holes:
        s = s - CrossSection([h])
    m = Manifold.extrude(s, T)
    if pnl.plane == "XY":
        return m.translate((0, 0, pnl.off))
    if pnl.plane == "XZ":
        return m.transform([[1, 0, 0, 0], [0, 0, 1, pnl.off], [0, 1, 0, 0]])
    return m.transform([[0, 0, 1, pnl.off], [1, 0, 0, 0], [0, 1, 0, 0]])


def check(panels):
    """Max pairwise overlap, assembled size, and base-plate notch volume not filled by other parts."""
    from manifold3d import Manifold
    sols = [(p.name, solid(p)) for p in panels]
    worst = 0.0
    for i in range(len(sols)):
        for j in range(i + 1, len(sols)):
            v = (sols[i][1] ^ sols[j][1]).volume()
            if v > 0.5:
                print("   OVERLAP %s / %s: %.1f mm3" % (sols[i][0], sols[j][0], v))
            worst = max(worst, v)
    allp = rb.union(s for _, s in sols)
    bb = allp.bounding_box()
    base = sols[0][1]
    gaps = Manifold.cube((L, D, T)) - base
    gaps = gaps - rb.union(rb.cyl(x, y, -1, T + 1, rb.M6_CLEAR + 1) for x, y in FEET)
    gaps = gaps - rb.union(rb.cyl(x, rb.PIER_YC + s * rb.PEG_DY, -1, T + 1, rb.PEG_HOLE_D + 1)
                           for x in list(rb.PIERS_XD) + [L + rb.HALF_PEG_X] for s in (-1, 1))
    gaps = gaps - rb.union(rb.cyl(x, y, -1, T + 1, rb.FEED_BORE + 1) for x, y in rb.feeder_points())
    empty = (gaps - rb.union(s for _, s in sols[1:])).volume()
    return worst, (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]), empty


CONCRETE = ("wing_wall", "abutment", "bridge_seat")


def assembly(top, which="A"):
    """Ply box, concrete parts, foot nut blocks and feet in track coordinates (z = 0 track base)."""
    set_height(top)
    panels = module()
    dz = -BOX
    ply = rb.union(solid(p) for p in panels if not p.name.startswith(CONCRETE)).translate((0, 0, dz))
    conc = rb.union(solid(p) for p in panels if p.name.startswith(CONCRETE)).translate((0, 0, dz))
    blk = rb.foot_nut_block()
    blocks = rb.union(blk.translate((x, y, T + dz)) for x, y in FEET)
    wheel = rb.foot_thumbwheel()
    zt = -top                                                  # table
    g = rb.FOOT_NOM - rb.WHEEL_H
    feet = rb.union(wheel.translate((x, y, zt)) + rb.cyl(x, y, zt + rb.WHEEL_H, zt + rb.WHEEL_H + rb.BOLT_L, 6.0)
                    for x, y in FEET)
    out = {"ply": ply, "plyconcrete": conc, "footblocks": blocks, "feet": feet}
    if which == "B":
        out = {k: m.mirror((1, 0, 0)).translate((2 * L + rb.GAP, 0, 0)) for k, m in out.items()}
    return out


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------
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
    note = ("River crossing pair - %s - sheet %d of %d - 600 x 3000 mm - 5mm ply. "
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
    import portal_nest as pn
    base = os.path.join(rb.OUT, "laser")
    report = []
    for label, top in rb.HEIGHTS.items():
        set_height(top)
        d = os.path.join(base, label)
        sd = os.path.join(d, "sheets_600x3000")
        os.makedirs(sd, exist_ok=True)
        for sub in (d, sd):
            for f in os.listdir(sub):
                if f.endswith((".svg", ".png", ".stl")):
                    os.remove(os.path.join(sub, f))
        panels = module()
        worst, size, empty = check(panels)
        lo, hi = rb.foot_range()
        svg = os.path.join(d, "river_module_base_618x330_%s.svg" % label)
        pl.write_svg(svg, panels,
                     "River crossing - module base (cut 2: West + East). Module height %.2f mm with the feet at %.0f mm "
                     "(adjust %.1f to %.1f); plywood box %.2f mm" % (top, rb.FOOT_NOM, lo, hi, BOX),
                     "cut 2 sets - assemble the East module as a mirror image (flip every part)")
        preview(svg)
        sheets = pn.pack([(("A", "B")[i], p) for i in range(2) for p in panels])
        for i, placed in enumerate(sheets):
            sp = os.path.join(sd, "river_pair_sheet_%d_of_%d_%s.svg" % (i + 1, len(sheets), label))
            write_sheet(sp, placed, i + 1, len(sheets), "module height %.2f mm" % top)
            preview(sp)
        report.append((label, size, worst, empty, len(sheets), [len(s) for s in sheets]))
    set_height(rb.HEIGHTS["70mm_template"])
    return report


if __name__ == "__main__":
    for r in write_all():
        print("%s: box %.1f x %.1f x %.1f mm | max overlap %.2f mm3 | unfilled base notches %.2f mm3 | %d sheet(s) %s"
              % (r[0], *r[1], r[2], r[3], r[4], r[5]))
