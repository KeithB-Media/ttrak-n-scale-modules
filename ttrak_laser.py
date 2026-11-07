"""
Laser-cut T-TRAK module boxes built on the "Double 618 x 330 T Track Module" template
(and the two-piece "End Cap 732 x 365" template).

Same construction as the templates:
  - 5 mm ply (or 1/4" ply, 0.22" actual), module top 70.09 mm above the table
  - finger joints: top plate drops onto tabs on the aprons and end plates; end plates
    have corner tabs (20.85-43.54 mm above the table) that lock into notches in the aprons
  - 4 corner leveling brackets (9 mm hole for a T-nut + leveling bolt) that slot through
    both walls 20.85 mm above the table; 5 mm access holes in the top plate above each bolt
  - colours: purple = outside cut (kerf OUT), green = inside cut (kerf IN),
    red = engrave or delete (reference only, do not cut)

Modules written to ttrak_output/laser_modules/:
  endcap_one_piece_732x365.svg     180 degree end loop (R315 + R282), ONE top plate, ONE box
  double_raised_bed_618x330.svg    double with a raised track bed (low ground in front and behind)
  double_raised_bed_to_edge_618x330.svg   double with the raised bed running out to the front edge
  triple_928x330.svg               regular (flat) triple module

Run:  python ttrak_laser.py          (also writes *_preview.png if Playwright is available)
      python ttrak_laser.py --check  (3D voxel check: no parts overlap, faces are closed)
"""

import math
import os
import sys

from portal_laser import edge, clean, rect, circle, stadium

T = 5.0                     # ply thickness
TOP = 70.09                 # table -> top of the track surface (template)
SIDE_TAB = (20.85, 43.54)   # end plate corner tab band (template)
BRK_Z = 20.85               # bottom of the corner leveling brackets (template)
BRK_SLOT_Z = (20.8, 25.9)   # bracket tab slots in the walls (template)
BRK_SLOT = (29.35, 49.45)   # bracket tab slot, measured from the module corner
FOOT_HOLE = 9.0             # bracket hole (T-nut + leveling bolt)
ACCESS = (24.5, 5.0)        # access hole in the top above each leveling bolt (inset, dia)
WIRE = (18.2, 46.2)         # end plate wiring hole height band (template)
TRACK_F, TRACK_R = 50.5, 83.5   # track centres from the front edge (T-TRAK)
RB = 12.5                   # half width of Unitrack roadbed
SCREW = 2.8                 # track screw/nail holes, 18 mm in from each track section end

# raised-bed doubles
DROP = 25.4                 # ground level below the top of the track bed (1 inch)
LOW_SIDE_TAB = (12.0, 32.0) # corner tab band on the raised modules (walls are only ~40 mm tall)
LOW_WIRE = (10.0, 32.0)     # end plate wiring hole band on the raised modules
STRIP = (25.0, 110.0)       # raised bed front/back edge (version 1); version 2 runs from 0
STRIP_TAB = (40.0, 95.0)    # end plate tab into the raised track plate
GROUND_TAB = (55.0, 80.0)   # ground plate tab through the end plate, under the raised bed
LOW_END_TABS = [(150.0, 210.0), (250.0, 300.0)]   # end plate tabs into the ground plate

# cross braces (triple and end cap): hang 40 mm below the top plate
BRACE_H = 40.0
BRACE_SIDE_TAB = (35.0, 55.0)

PURPLE, GREEN, RED = "#70299C", "#3D805E", "#EA3627"

# template parts
DOUBLE_LONG_TABS = [(61.6, 123.2), (184.8, 246.4), (371.6, 433.2), (494.8, 556.4)]
DOUBLE_END_TABS = [(66.0, 132.0), (198.0, 264.0)]
ENDCAP_END_TABS = [(73.0, 146.0), (219.0, 292.0)]
BRACKET = [(50, 23.71), (50, 3.5), (48, 0), (30, 0), (30, 5.6), (5.6, 5.6), (5.6, 30),
           (0, 30), (0, 48), (3.5, 50), (23.71, 50)]


class Panel:
    """A flat ply part. outline/holes in local (u,v); plane + off place it in 3D:
       'XY': (u,v)->(X,Y), thickness along Z from off
       'XZ': (u,v)->(X,Z), thickness along Y from off
       'YZ': (u,v)->(Y,Z), thickness along X from off"""

    def __init__(self, name, outline, plane, off, holes=(), engrave=(), labels=()):
        self.name, self.outline, self.plane, self.off = name, clean(outline), plane, off
        self.holes = list(holes)
        self.engrave = list(engrave)      # (points, closed)
        self.labels = list(labels)        # (u, v, text, size)

    def bbox(self):
        us = [p[0] for p in self.outline]
        vs = [p[1] for p in self.outline]
        return min(us), min(vs), max(us), max(vs)


def tabs_for(length, pitch=61.6):
    """Symmetric finger pattern: split into an odd number of ~pitch segments, every odd one is a tab."""
    n = int(length // pitch)
    cands = [k for k in (n - 1, n, n + 1, n + 2) if k % 2 == 1 and k >= 3]
    n = min(cands, key=lambda k: abs(length / k - pitch))
    p = length / n
    return [(round(i * p, 1), round((i + 1) * p, 1)) for i in range(1, n, 2)]


def srect(u0, v0, u1, v1, c=0.05):
    """Slot with 0.05 mm clearance each side (same as the template's 20.1 x 5.1 slots)."""
    return rect(u0 - c, v0 - c, u1 + c, v1 + c)


def stadium_at(cx, cy, length, width, ang, n=12):
    """Rotated stadium (feeder hole), centre, overall length, width, direction angle (rad)."""
    r = width / 2
    a = length / 2 - r
    pts = []
    for i in range(n + 1):
        t = -math.pi / 2 + math.pi * i / n
        pts.append((a + r * math.cos(t), r * math.sin(t)))
    for i in range(n + 1):
        t = math.pi / 2 + math.pi * i / n
        pts.append((-a + r * math.cos(t), r * math.sin(t)))
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


# ----------------------------------------------------------------------------
# Walls
# ----------------------------------------------------------------------------
def apron(name, y_off, L, H, top_tabs, slots=(), label_v=None, side_tab=SIDE_TAB):
    """Long side wall, 0..L, table to H-T with top tabs up to H; template corner notches."""
    st = side_tab
    p = [(0, 0), (L, 0), (L, st[0]), (L - T, st[0]), (L - T, st[1]), (L, st[1])]
    edge(p, "u", H - T, L, 0, [(a, b, T) for a, b in top_tabs], +1)
    p += [(0, st[1]), (T, st[1]), (T, st[0]), (0, st[0])]
    holes = [srect(BRK_SLOT[0], BRK_SLOT_Z[0] + 0.05, BRK_SLOT[1], BRK_SLOT_Z[1] - 0.05),
             srect(L - BRK_SLOT[1], BRK_SLOT_Z[0] + 0.05, L - BRK_SLOT[0], BRK_SLOT_Z[1] - 0.05)]
    holes += list(slots)
    lab = (L / 2, label_v if label_v else 8, name.upper().replace("_", " "), 5)
    return Panel(name, p, "XZ", y_off, holes, labels=[lab])


def end_plate(name, x_off, D, top_profile, slots=(), wire=WIRE, side_tab=SIDE_TAB):
    """End wall between the aprons, 0..D with corner tabs. top_profile = points from u=D-T
    back to u=T along the top (including any tabs)."""
    st = side_tab
    p = [(T, 0), (D - T, 0), (D - T, st[0]), (D, st[0]), (D, st[1]), (D - T, st[1])]
    p += top_profile
    p += [(T, st[1]), (0, st[1]), (0, st[0]), (T, st[0])]
    holes = [srect(BRK_SLOT[0], BRK_SLOT_Z[0] + 0.05, BRK_SLOT[1], BRK_SLOT_Z[1] - 0.05),
             srect(D - BRK_SLOT[1], BRK_SLOT_Z[0] + 0.05, D - BRK_SLOT[0], BRK_SLOT_Z[1] - 0.05)]
    if wire:
        holes.append(stadium(D / 2 - 44.7, D / 2 + 44.7, wire[0], wire[1]))
    holes += list(slots)
    return Panel(name, p, "YZ", x_off, holes, labels=[(D / 2, min(9, wire[0] - 5), name.upper().replace("_", " "), 4.5)])


def flat_end_top(D, tabs, h=None):
    h = TOP if h is None else h
    p = []
    edge(p, "u", h - T, D - T, T, [(a, b, T) for a, b in tabs], +1)
    return p


def brace(name, x_off, D, top_tabs):
    """Cross brace under the top plate. Side tabs go through slots in the aprons."""
    z0, z1 = TOP - T - BRACE_H, TOP - T
    p = [(T, z0), (D - T, z0), (D - T, BRACE_SIDE_TAB[0]), (D, BRACE_SIDE_TAB[0]),
         (D, BRACE_SIDE_TAB[1]), (D - T, BRACE_SIDE_TAB[1])]
    edge(p, "u", z1, D - T, T, [(a, b, T) for a, b in top_tabs], +1)
    p += [(T, BRACE_SIDE_TAB[1]), (0, BRACE_SIDE_TAB[1]), (0, BRACE_SIDE_TAB[0]), (T, BRACE_SIDE_TAB[0])]
    holes = [stadium(D / 2 - 45, D / 2 + 45, z0 + 8, z0 + 30)]
    return Panel(name, p, "YZ", x_off, holes, labels=[(D / 2, z1 - 4, name.upper().replace("_", " "), 4)])


def brace_slots_apron(xs):
    return [srect(x, BRACE_SIDE_TAB[0], x + T, BRACE_SIDE_TAB[1]) for x in xs]


def brackets(L, D):
    """Four corner leveling brackets (template shape) in module coordinates."""
    out = []
    for i, (sx, sy) in enumerate(((1, 1), (-1, 1), (1, -1), (-1, -1))):
        ox = 0.0 if sx > 0 else L
        oy = 0.0 if sy > 0 else D
        pts = [(ox + sx * (u - 0.6), oy + sy * (v - 0.6)) for u, v in BRACKET]
        hole = circle(ox + sx * ACCESS[0], oy + sy * ACCESS[0], FOOT_HOLE)
        out.append(Panel("leveling_bracket_%d" % (i + 1), pts, "XY", BRK_Z, [hole]))
    return out


# ----------------------------------------------------------------------------
# Track engraving
# ----------------------------------------------------------------------------
def straight_tracks(L, front_secs, rear_secs, y_off=0.0):
    """Roadbed outlines, section joints, screw holes and one feeder hole per track.
    Sections are laid from x = -1 (1 mm overhang each end, as on every T-TRAK module)."""
    eng, holes, labels = [], [], []
    for yc, secs in ((TRACK_F - y_off, front_secs), (TRACK_R - y_off, rear_secs)):
        assert abs(sum(secs) - (L + 2)) < 0.01, (secs, L)
        eng.append(([(0, yc - RB), (L, yc - RB)], False))
        eng.append(([(0, yc + RB), (L, yc + RB)], False))
        eng.append(([(0, yc), (L, yc)], False))
        x = -1.0
        joints, pins = [], []
        for s in secs:
            pins += [x + 18, x + s - 18]
            labels.append((x + s / 2, yc + RB - 5.5, "%dmm  KATO %s" % (s, KATO[s]), 3.5))
            x += s
            if x < L - 1:
                joints.append(x)
                eng.append(([(x, yc - RB), (x, yc + RB)], False))
        # feeder: on the joint nearest the middle
        j = min(joints, key=lambda q: abs(q - L / 2))
        side = -1 if yc == TRACK_F - y_off else 1
        fc = j + side * 5.5
        holes.append(Feeder(stadium(fc - 14, fc + 14, yc - 8, yc + 8)))
        holes += [circle(px, yc, SCREW) for px in pins if abs(px - fc) > 14 + 2]
    return eng, holes, labels


class Feeder(list):
    feeder = True


KATO = {248: "20-000", 186: "20-010", 124: "20-020"}


def arc_pts(cx, cy, r, a0, a1, n=90):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


# ----------------------------------------------------------------------------
# Plain box (double / triple)
# ----------------------------------------------------------------------------
def top_plate(name, L, D, long_tabs, end_tabs, slots=(), eng=(), holes=(), labels=()):
    p = []
    edge(p, "u", 0, 0, L, [(a, b, -T) for a, b in long_tabs], -1)
    edge(p, "v", L, 0, D, [(a, b, -T) for a, b in end_tabs], +1)
    edge(p, "u", D, L, 0, [(a, b, -T) for a, b in long_tabs], +1)
    edge(p, "v", 0, D, 0, [(a, b, -T) for a, b in end_tabs], -1)
    hs = [circle(x, y, ACCESS[1]) for x in (ACCESS[0], L - ACCESS[0]) for y in (ACCESS[0], D - ACCESS[0])]
    labs = list(labels) + [(L / 2, D - 40, name.upper().replace("_", " ") + "  -  FRONT EDGE IS THE TRACK SIDE", 6)]
    return Panel(name, p, "XY", TOP - T, hs + list(holes) + list(slots), list(eng), labs)


def triple_module():
    L, D = 928.0, 330.0
    lt = tabs_for(L)
    bx = [L / 3 - T / 2, 2 * L / 3 - T / 2]
    eng, th, tl = straight_tracks(L, [186, 248, 248, 248], [248, 248, 248, 186])
    slots = [srect(x, a, x + T, b) for x in bx for a, b in DOUBLE_END_TABS]
    return [
        top_plate("triple_top_plate", L, D, lt, DOUBLE_END_TABS, slots, eng, th, tl),
        apron("front_apron", 0.0, L, TOP, lt, brace_slots_apron(bx)),
        apron("back_apron", D - T, L, TOP, lt, brace_slots_apron(bx)),
        end_plate("end_plate_L", 0.0, D, flat_end_top(D, DOUBLE_END_TABS)),
        end_plate("end_plate_R", L - T, D, flat_end_top(D, DOUBLE_END_TABS)),
        brace("cross_brace_1", bx[0], D, DOUBLE_END_TABS),
        brace("cross_brace_2", bx[1], D, DOUBLE_END_TABS),
    ] + brackets(L, D), (L, D)


# ----------------------------------------------------------------------------
# One-piece end cap (180 degree loop)
# ----------------------------------------------------------------------------
def endcap_module():
    """X runs along the edge that butts against the module ends (0..732), Y is depth (0..365).
    Track centre radii 315 (outer, joins the front tracks) and 282 (inner, joins the rear
    tracks), centred 1 mm outside the joining edge so the track overhangs 1 mm, as in the template."""
    L, D = 732.0, 365.0
    lt = tabs_for(L)
    cx, cy = L / 2, -1.0
    bx = [L / 2 - T / 2]
    eng, holes, labels = [], [], []
    for rc, kato in ((315.0, "20-120 R315-45"), (282.0, "20-110 R282-45")):
        for r in (rc - RB + 0.1, rc, rc + RB - 0.1):
            a0 = math.asin(1.0 / r)
            eng.append((arc_pts(cx, cy, r, a0, math.pi - a0), False))
        for k in range(1, 4):                       # 4 x 45 degree sections, joints at 45/90/135
            a = k * math.pi / 4
            eng.append(([(cx + (rc - RB) * math.cos(a), cy + (rc - RB) * math.sin(a)),
                         (cx + (rc + RB) * math.cos(a), cy + (rc + RB) * math.sin(a))], False))
        for k in range(4):
            a = (k + 0.5) * math.pi / 4
            holes.append(circle(cx + rc * math.cos(a), cy + rc * math.sin(a), SCREW))
        labels.append((cx, cy + rc - 7, "4x KATO " + kato, 4))
        fa = math.pi / 4 if rc > 300 else 3 * math.pi / 4   # feeders on the 45 / 135 degree joints
        holes.append(stadium_at(cx + rc * math.cos(fa), cy + rc * math.sin(fa), 28, 16, fa + math.pi / 2))
    slots = [srect(x, a, x + T, b) for x in bx for a, b in ((60.0, 120.0), (180.0, 240.0))]
    labels.append((L / 2, 120, "END CAP TOP - THIS EDGE JOINS THE MODULE ENDS", 6))
    top = top_plate("endcap_top_plate", L, D, lt, ENDCAP_END_TABS, slots, eng, holes, labels)
    top.labels = [lb for lb in top.labels if "FRONT EDGE" not in lb[2]]
    return [
        top,
        apron("joining_side_apron", 0.0, L, TOP, lt, brace_slots_apron(bx)),
        apron("back_apron", D - T, L, TOP, lt, brace_slots_apron(bx)),
        end_plate("end_plate_L", 0.0, D, flat_end_top(D, ENDCAP_END_TABS)),
        end_plate("end_plate_R", L - T, D, flat_end_top(D, ENDCAP_END_TABS)),
        brace("centre_brace", bx[0], D, [(60.0, 120.0), (180.0, 240.0)]),
    ] + brackets(L, D), (L, D)


# ----------------------------------------------------------------------------
# Raised track bed doubles
# ----------------------------------------------------------------------------
def raised_module(to_edge):
    """The track runs on a raised bed at standard T-TRAK height; the ground plate is DROP lower.
    to_edge=False: low ground strip in front of the bed (embankment look).
    to_edge=True : the bed runs out to the front edge; low ground behind it only."""
    L, D = 618.0, 330.0
    lt = DOUBLE_LONG_TABS
    y0 = 0.0 if to_edge else STRIP[0]
    y1 = STRIP[1]
    G = TOP - DROP                               # ground surface
    tag = "raised_to_edge" if to_edge else "raised_bed"

    # --- end plates: high under the bed, low elsewhere
    def end_profile():
        p = []
        edge(p, "u", G - T, D - T, y1, [(a, b, T) for a, b in LOW_END_TABS], +1)
        p += [(y1, TOP - T)]
        edge(p, "u", TOP - T, y1, max(y0, T), [(STRIP_TAB[0], STRIP_TAB[1], T)], +1)
        if y0 > T:
            p += [(y0, G - T), (T, G - T)]
        return p

    end_slots = [srect(GROUND_TAB[0], G - T, GROUND_TAB[1], G)]

    # --- ground plate at G
    g = []
    if to_edge:
        edge(g, "u", T, T, L - T, [(a, b, T) for a, b in lt], -1)     # tabs into front apron slots
        g += [(L - T, T)]
    else:
        edge(g, "u", 0, 0, L, [(a, b, -T) for a, b in lt], -1)        # notches for front apron tabs
        g += [(L, y0), (L - T, y0)]
    edge(g, "v", L - T, max(y0, T), y1, [(GROUND_TAB[0], GROUND_TAB[1], T)], +1)
    g += [(L - T, y1), (L, y1)]
    edge(g, "v", L, y1, D, [(a, b, -T) for a, b in LOW_END_TABS], +1)
    edge(g, "u", D, L, 0, [(a, b, -T) for a, b in lt], +1)
    edge(g, "v", 0, D, y1, [(a, b, -T) for a, b in LOW_END_TABS], -1)
    g += [(0, y1), (T, y1)]
    edge(g, "v", T, y1, max(y0, T), [(GROUND_TAB[0], GROUND_TAB[1], T)], -1)
    if not to_edge:
        g += [(T, y0), (0, y0)]
    risers_y = ([] if to_edge else [y0]) + [y1 - T]
    riser_tabs = lt
    g_slots = [srect(a, y, b, y + T) for y in risers_y for a, b in riser_tabs]
    g_holes = [circle(x, y, ACCESS[1]) for x in (ACCESS[0], L - ACCESS[0]) for y in (D - ACCESS[0],)]
    if not to_edge:
        g_holes += [circle(x, ACCESS[0], ACCESS[1]) for x in (ACCESS[0], L - ACCESS[0])]
    # feeder pass-through below the track feeders
    eng, th, tl = straight_tracks(L, [124, 248, 248], [248, 248, 124], 0.0)
    g_holes += [h for h in th if getattr(h, "feeder", False)]
    ground = Panel("%s_ground_plate" % tag, g, "XY", G - T, g_holes + g_slots,
                   labels=[(L / 2, (y1 + D) / 2, "GROUND PLATE - %.1f MM (1 IN) BELOW TRACK" % DROP, 6)])

    # --- raised track plate y0..y1
    t = []
    if to_edge:
        edge(t, "u", 0, 0, L, [(a, b, -T) for a, b in lt], -1)         # front apron tabs
    else:
        edge(t, "u", y0, 0, L, [(a, b, -T) for a, b in riser_tabs], -1)
    edge(t, "v", L, y0, y1, [(STRIP_TAB[0], STRIP_TAB[1], -T)], +1)
    edge(t, "u", y1, L, 0, [(a, b, -T) for a, b in riser_tabs], +1)
    edge(t, "v", 0, y1, y0, [(STRIP_TAB[0], STRIP_TAB[1], -T)], -1)
    track = Panel("%s_track_plate" % tag, t, "XY", TOP - T, th, eng,
                  tl + [(L / 2, y0 + 7, "RAISED TRACK BED - FRONT EDGE THIS SIDE", 4)])

    # --- risers (walls under the bed edges), stand on the ground plate
    def riser(name, y):
        p = []
        edge(p, "u", G, T, L - T, [(a, b, T) for a, b in riser_tabs], -1)
        edge(p, "u", TOP - T, L - T, T, [(a, b, T) for a, b in riser_tabs], +1)
        return Panel(name, p, "XZ", y, labels=[(L / 2, G + 3, name.upper().replace("_", " "), 3.5)])

    parts = [ground, track]
    if to_edge:
        fa_slots = [srect(a, G - T, b, G) for a, b in lt]
        parts.append(apron("front_apron_full_height", 0.0, L, TOP, lt, fa_slots, side_tab=LOW_SIDE_TAB))
    else:
        parts.append(apron("front_apron_low", 0.0, L, G, lt, label_v=30, side_tab=LOW_SIDE_TAB))
        parts.append(riser("bed_riser_front", y0))
    parts.append(riser("bed_riser_back", y1 - T))
    parts.append(apron("back_apron_low", D - T, L, G, lt, label_v=34, side_tab=LOW_SIDE_TAB))
    for nm, xo in (("end_plate_L", 0.0), ("end_plate_R", L - T)):
        parts.append(end_plate(nm, xo, D, end_profile(), end_slots, LOW_WIRE, LOW_SIDE_TAB))
    return parts + brackets(L, D), (L, D)


# ----------------------------------------------------------------------------
# SVG output
# ----------------------------------------------------------------------------
def write_svg(path, panels, title, notes):
    gap = 6.0
    order = sorted(panels, key=lambda p: -(p.bbox()[2] - p.bbox()[0]) * (p.bbox()[3] - p.bbox()[1]))
    sheet_w = max(p.bbox()[2] - p.bbox()[0] for p in panels) + 2 * gap
    placed, row, row_h, x, y = [], [], 0.0, gap, gap + 14 + 9 * (3 + len(notes))

    def flush():
        nonlocal y, row, row_h, x
        for pnl, px in row:
            placed.append((pnl, px, y))
        y += row_h + gap
        row, row_h, x = [], 0.0, gap

    for pnl in order:
        u0, v0, u1, v1 = pnl.bbox()
        if x + (u1 - u0) > sheet_w - gap + 0.01:
            flush()
        row.append((pnl, x))
        x += (u1 - u0) + gap
        row_h = max(row_h, v1 - v0)
    flush()
    sheet_h = y

    def tr(pnl, ox, oy, pt):
        u0, v0, u1, v1 = pnl.bbox()
        return (ox + pt[0] - u0, oy + (v1 - pt[1]))

    def pathd(pts, close=True):
        return "M" + " L".join("%.3f,%.3f" % p for p in pts) + (" Z" if close else "")

    sw = 0.1
    g_cut, g_in, g_red = [], [], []
    for pnl, ox, oy in placed:
        g_cut.append('<path id="%s" d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                     % (pnl.name, pathd([tr(pnl, ox, oy, p) for p in pnl.outline]), PURPLE, sw))
        for h in pnl.holes:
            g_in.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                        % (pathd([tr(pnl, ox, oy, p) for p in h]), GREEN, sw))
        for pts, closed in pnl.engrave:
            g_red.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none"/>'
                         % (pathd([tr(pnl, ox, oy, p) for p in pts], closed), RED, sw))
        for (u, v, text, size) in pnl.labels:
            px, py = tr(pnl, ox, oy, (u, v))
            g_red.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" '
                         'text-anchor="middle" fill="%s">%s</text>' % (px, py, size, RED, text))
    lines = [title, "5mm Material or 1/4\" Ply 0.22\" Actual",
             "Purple... Adjust Kerf OUT    Green... Adjust Kerf IN    Red... Engrave or Delete, do not cut."] + notes
    for i, t in enumerate(lines):
        g_red.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="%.1f" fill="%s">%s</text>'
                     % (gap, gap + 8 + i * 9, 8 if i == 0 else 6, RED, t))
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" '
           'viewBox="0 0 %.2f %.2f">' % (sheet_w, sheet_h, sheet_w, sheet_h),
           '<g id="Cut_Outside_Purple">' + "".join(g_cut) + "</g>",
           '<g id="Cut_Inside_Green">' + "".join(g_in) + "</g>",
           '<g id="Engrave_Red">' + "".join(g_red) + "</g>", "</svg>"]
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    return sheet_w, sheet_h


MODULES = [
    ("endcap_one_piece_732x365", endcap_module,
     "End Cap 732 x 365 - ONE PIECE (180 deg loop, Kato R315 + R282)",
     ["One top plate, one box. Needs a laser bed of at least 744 x 377 mm for the long parts.",
      "The long edge with the 1 mm track overhang butts against the ends of the two module rows."]),
    ("double_raised_bed_618x330", lambda: raised_module(False),
     "Double 618 x 330 - RAISED TRACK BED",
     ["Track at standard T-TRAK height on a raised bed (y 25-110); ground plate %.1f mm (1 in) lower in front and behind." % DROP]),
    ("double_raised_bed_to_edge_618x330", lambda: raised_module(True),
     "Double 618 x 330 - RAISED TRACK BED TO THE FRONT EDGE",
     ["Raised bed runs from the front edge back to y 110; ground plate %.1f mm (1 in) lower behind it." % DROP]),
    ("triple_928x330", triple_module,
     "Triple 928 x 330 - regular module (track 930 mm per line: 3 x 248 + 186)",
     ["Needs a laser bed of at least 940 x 342 mm for the top plate and aprons.",
      "Two cross braces hang under the top plate at the thirds."]),
]


def out_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttrak_output", "laser_modules")
    os.makedirs(d, exist_ok=True)
    return d


# ----------------------------------------------------------------------------
# 3D voxel check
# ----------------------------------------------------------------------------
def voxel_check(panels, size, step=0.5):
    import numpy as np
    from matplotlib.path import Path
    L, D = size
    off = 0.13
    nx, ny, nz = int((L + 2) / step), int((D + 2) / step), int((TOP + 2) / step)
    grid = np.zeros((nx, ny, nz), np.uint8)
    xs = np.arange(nx) * step - 1 + off
    ys = np.arange(ny) * step - 1 + off
    zs = np.arange(nz) * step - 1 + off
    axes = {"XY": (xs, ys, zs), "XZ": (xs, zs, ys), "YZ": (ys, zs, xs)}
    for pnl in panels:
        au, av, aw = axes[pnl.plane]
        U, V = np.meshgrid(au, av, indexing="ij")
        pts = np.column_stack([U.ravel(), V.ravel()])
        m = Path(pnl.outline + [pnl.outline[0]]).contains_points(pts)
        for h in pnl.holes:
            m &= ~Path(h + [h[0]]).contains_points(pts)
        m = m.reshape(U.shape)
        w = (aw > pnl.off) & (aw < pnl.off + T)
        if pnl.plane == "XY":
            grid += (m[:, :, None] & w[None, None, :]).astype(np.uint8)
        elif pnl.plane == "XZ":
            grid += (m[:, None, :] & w[None, :, None]).astype(np.uint8)
        else:
            grid += (w[:, None, None] & m[None, :, :]).astype(np.uint8)
    over = int((grid > 1).sum())
    occ = np.argwhere(grid > 0)
    lo = occ.min(0) * step - 1 + off
    hi = occ.max(0) * step - 1 + off
    return over, lo, hi, grid, (xs, ys, zs)


def face_report(grid, axes, size, name, d):
    """Images of the outside faces so open notches would show up as holes."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs, ys, zs = axes
    L, D = size
    occ = grid > 0
    fig, axs = plt.subplots(4, 1, figsize=(14, 12))
    views = [("top (looking down)", occ.any(2).T, (xs, ys)),
             ("front face (y 0-5)", occ[:, (ys > 0) & (ys < T), :].any(1).T, (xs, zs)),
             ("back face", occ[:, (ys > D - T) & (ys < D), :].any(1).T, (xs, zs)),
             ("left end face (x 0-5)", occ[(xs > 0) & (xs < T), :, :].any(0).T, (ys, zs))]
    for ax, (t, img, (a, b)) in zip(axs, views):
        ax.imshow(img, origin="lower", extent=(a[0], a[-1], b[0], b[-1]), cmap="Greys", aspect="equal")
        ax.set_title(t)
    fig.tight_layout()
    fig.savefig(os.path.join(d, name + "_check.png"), dpi=80)
    plt.close(fig)


def render_previews(paths):
    """PNG previews via Playwright/Chromium if available."""
    import subprocess
    import json
    js = r"""
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const b=await chromium.launch();
for(const [f,o] of JSON.parse(process.argv[process.argv.length-1])){let s=fs.readFileSync(f,'utf8');
const m=s.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);const W=1600,H=Math.round(1600*m[2]/m[1]);
s=s.replace(/width="[^"]*mm" height="[^"]*mm"/,'width="'+W+'" height="'+H+'"').replace(/stroke-width="0.1"/g,'stroke-width="0.6"');
const p=await b.newPage({viewport:{width:W,height:H}});
await p.setContent('<body style="margin:0;background:#fff">'+s.replace(/<\?xml[^>]*>/,'')+'</body>');
await p.screenshot({path:o});await p.close();}
await b.close();})();
"""
    try:
        jobs = [[p, p[:-4] + "_preview.png"] for p in paths]
        subprocess.run(["node", "-e", js, json.dumps(jobs)], check=True, capture_output=True, timeout=300)
        return True
    except Exception as e:      # noqa: BLE001
        print("preview skipped:", e)
        return False


def main():
    d = out_dir()
    paths = []
    for name, fn, title, notes in MODULES:
        panels, size = fn()
        path = os.path.join(d, name + ".svg")
        w, h = write_svg(path, panels, title, notes)
        paths.append(path)
        print("%-45s %d parts, sheet %.0f x %.0f mm" % (name + ".svg", len(panels), w, h))
        if "--check" in sys.argv:
            over, lo, hi, grid, axes = voxel_check(panels, size)
            print("    overlap voxels: %d   assembled extent x %.1f..%.1f  y %.1f..%.1f  z %.1f..%.1f"
                  % (over, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
            face_report(grid, axes, size, name, os.environ.get("CHECK_DIR", d))
    if "--no-preview" not in sys.argv:
        render_previews(paths)


if __name__ == "__main__":
    main()
