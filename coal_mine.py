"""
T-TRAK N-scale coal mine: a 3-module track plan (Triple | Double | Triple) built from Kato Unitrack.

Theme: a drift / shaft mine with a 4-track tipple, run the way real tipples were worked:

    EMPTIES  ->  under the tipple (loading)  ->  LOADS
    left yard      middle module                 right yard

  * Module A (triple, 928 mm) EMPTY RECEIVING YARD: a #4 turnout on main 2 starts a 15 deg
    Kato-style ladder that fans out into the mine lead and 4 yard tracks.
  * Module B (double, 618 mm) TIPPLE: all 4 yard tracks pass under the tipple (the loading
    tracks).  The mine lead runs in front as the runaround / bypass.  A #4 crossover
    between main 1 and main 2 lets trains on either main reach the mine.
  * Module C (triple, 928 mm) LOADED TRAIN YARD: the mirror image of module A.  The lead and
    the 4 tracks ladder back into main 2.

The two mains stay standard T-TRAK (front track centre 50.5 mm from the front edge, 33 mm
spacing, 620/930 mm of track per double/triple), so the outer ends join any T-TRAK module.
The set always runs together in this order (like the Portal bridge set), so the yard tracks
also cross the two inside joints.

Geometry used (Kato Unitrack, nominal):
  #4 turnout EP481-15 L/R: 126 mm long, diverging route = R481 15 deg arc from the points.
  #4 + #4 (or #4 + R481-15) reversed = 32.8 mm offset  -> Kato's 33 mm parallel spacing.
  #4 turnouts butted end to end on a 15 deg lead = a ladder with 32.6 mm track spacing.

Run:  python coal_mine.py          (pure Python, no Blender needed)
Output: ttrak_output/coal_mine/
    coal_mine_trackplan.svg / .png   whole set, 1:1 mm units
    coal_mine_module_A/B/C.png       close-ups (PNG needs Node + Playwright; the SVG doesn't)
    coal_mine_track_parts.csv        every Unitrack piece, per module and track
    coal_mine_turnouts.csv           turnout list (hand, position, what it does)

Set EXTRA_YARD_DOUBLES = 1 to put a plain double between A and B and between B and C
(5 modules, ~12 more cars of yard capacity per side).
"""

import csv
import itertools
import math
import os
import shutil
import subprocess

# ----------------------------------------------------------------------------
# PARAMETERS (check against your club's T-TRAK standard)
# ----------------------------------------------------------------------------
TRIPLE, DOUBLE = 930.0, 620.0       # track length per line (module boxes are 928 / 618)
EXTRA_YARD_DOUBLES = 0               # plain doubles added on each side of the tipple module
DEPTH = 355.0                        # module depth
MAIN1_Y, MAIN2_Y = 50.5, 83.5        # front edge -> track centre (38 mm to roadbed edge + 12.5)
ROADBED_W = 25.0
GAUGE = 9.0

R4, A4, L4 = 481.0, 15.0, 126.0      # Kato #4 turnout
CAR_LEN = 102.0                      # N-scale 100 t 3-bay hopper over the couplers (~4 in)
CLEAR = 45.0                         # fouling-point clearance from the end of a ladder turnout

STRAIGHTS = [248.0, 186.0, 124.0, 64.0, 62.0, 45.5, 29.0]   # Kato straights used for filling
EXPANSION = (78.0, 108.0)            # Kato expansion track S78-108
TOL = 0.6                            # accepted fill error per run (Unitrack joint play)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ttrak_output", "coal_mine")

D = R4 * (1 - math.cos(math.radians(A4)))          # 16.39  offset of one #4 diverging arc
AX = R4 * math.sin(math.radians(A4))               # 124.49 length of one #4 diverging arc (x)
LDX = L4 * math.cos(math.radians(A4))              # 121.71 ladder step in x
LDY = L4 * math.sin(math.radians(A4))              # 32.61  ladder step in y = track spacing
LEAD_Y = MAIN2_Y + 2 * D                           # mine lead / runaround (first ladder track)
Y_TRACKS = [LEAD_Y + (k + 1) * LDY for k in range(4)]     # yard / loading tracks 1..4

MODS = ([("A", "Triple", TRIPLE, "Empty receiving yard")]
        + [("A%d" % (i + 1), "Double", DOUBLE, "Empty yard extension") for i in range(EXTRA_YARD_DOUBLES)]
        + [("B", "Double", DOUBLE, "Tipple / loading tracks")]
        + [("C%d" % (i + 1), "Double", DOUBLE, "Loaded yard extension") for i in range(EXTRA_YARD_DOUBLES)]
        + [("C", "Triple", TRIPLE, "Loaded train yard")])
JOINTS = [0.0]
for m in MODS:
    JOINTS.append(JOINTS[-1] + m[2])
TOTAL = JOINTS[-1]
B_IDX = 1 + EXTRA_YARD_DOUBLES
B_X0 = JOINTS[B_IDX]
CENTER = TOTAL / 2


# ----------------------------------------------------------------------------
# Straight filling
# ----------------------------------------------------------------------------
def _combos():
    best = {}
    for counts in itertools.product(range(4), range(3), range(3), range(3), range(3), range(3), range(3)):
        s = round(sum(c * l for c, l in zip(counts, STRAIGHTS)), 2)
        n = sum(counts)
        if n and (s not in best or n < sum(best[s])):
            best[s] = counts
    return sorted(best.items())


COMBOS = _combos()


def fill(gap):
    """Best set of Kato straights for a straight gap. Returns (pieces, error, uses_expansion)."""
    if gap < TOL:
        return [], gap, False
    cand = min(COMBOS, key=lambda c: (abs(c[0] - gap), sum(c[1])))
    if abs(cand[0] - gap) <= TOL:
        return _pieces(cand[1]), cand[0] - gap, False
    # an expansion track (78-108) takes up the odd length
    best = None
    for s, counts in [(0.0, (0,) * 7)] + COMBOS:
        rest = gap - s
        if EXPANSION[0] <= rest <= EXPANSION[1]:
            key = (sum(counts), -s)
            if best is None or key < best[0]:
                best = (key, counts, rest)
    if best:
        return _pieces(best[1]) + ["S78-108 expansion @ %.1f" % best[2]], 0.0, True
    return _pieces(cand[1]), cand[0] - gap, False


def _pieces(counts):
    out = []
    for c, l in zip(counts, STRAIGHTS):
        out += ["S%g" % l] * c
    return out


def piece_len(p):
    return float(p.split()[0][1:]) if not p.startswith("S78") else float(p.split("@")[1])


# ----------------------------------------------------------------------------
# Choose positions so every straight run fills with stock Unitrack
# ----------------------------------------------------------------------------
def yard_starts(p):
    """x where the lead and tracks 1-4 become straight, for a ladder whose main-2 turnout is at p."""
    qx = p + AX                         # first ladder turnout, on the 15 deg diagonal
    return [qx + AX + k * LDX for k in range(4)] + [qx + 4 * LDX + AX]


def choose_left():
    """Main 2 turnout position on module A so every straight run fills with stock pieces."""
    xa_end = JOINTS[1]
    best = None
    for p10 in range(290, 2000):
        p = p10 / 10.0
        gaps = [p, xa_end - p - L4] + [xa_end - x for x in yard_starts(p)]
        if any(g < 29 - TOL for g in gaps):
            continue
        errs = [fill(g) for g in gaps]
        e = max(abs(x[1]) for x in errs) + 0.2 * sum(x[2] for x in errs)
        key = (round(e, 2), p)                  # then the smallest p = longest yard
        if best is None or key < best[0]:
            best = (key, p)
    return best[1]


def choose_main_xo():
    """Main 1 -> main 2 crossover, centred on the tipple module as nearly as the fill allows."""
    best = None
    for c10 in range(0, int((DOUBLE - 2 * AX - L4 + L4) * 10)):
        c = c10 / 10.0                                   # main 1 points, from module B start
        gaps = [c, DOUBLE - c - L4, c + 2 * AX - L4, DOUBLE - c - 2 * AX]
        if any(g < -0.01 or 0.5 < g < 29 - TOL for g in gaps):
            continue
        e = max(abs(fill(g)[1]) + 0.2 * fill(g)[2] for g in gaps)
        key = (round(e, 2), abs(c + AX - DOUBLE / 2))
        if best is None or key < best[0]:
            best = (key, c)
    return best[1]


P_XO = choose_left()
STARTS = yard_starts(P_XO)
C_MXO = choose_main_xo()


# ----------------------------------------------------------------------------
# Geometry: paths are lists of (x, y, heading_deg) samples
# ----------------------------------------------------------------------------
def straight(x, y, h, length):
    r = math.radians(h)
    return [(x, y, h), (x + length * math.cos(r), y + length * math.sin(r), h)]


def arc(x, y, h, radius, ang, left, n=24):
    s = 1 if left else -1
    r = math.radians(h)
    cx, cy = x - s * radius * math.sin(r), y + s * radius * math.cos(r)
    pts = []
    for i in range(n + 1):
        hh = h + s * ang * i / n
        rr = math.radians(hh)
        pts.append((cx + s * radius * math.sin(rr), cy - s * radius * math.cos(rr), hh))
    return pts


def mirror(path):
    return [(TOTAL - x, y, 180 - h) for x, y, h in path]


TRACKS = []       # dict(paths, kind, label, module, joints)
TURNOUTS = []     # dict(id, hand, x, y, heading, role, module)
PIECES = []       # (module, track, piece)


def module_of(x):
    for i, m in enumerate(MODS):
        if JOINTS[i] - 0.01 <= x < JOINTS[i + 1] - 0.01:
            return m[0]
    return MODS[-1][0]


def add_turnout(x, y, h, hand, role, track, mirrored=False):
    left = hand == "L"
    paths = [straight(x, y, h, L4), arc(x, y, h, R4, A4, left)]
    if mirrored:
        paths = [mirror(p) for p in paths]
        hand = "R" if left else "L"
        x = TOTAL - x
    TRACKS.append(dict(paths=paths, kind="turnout"))
    TURNOUTS.append(dict(hand=hand, x=x, y=y, role=role, module=module_of(x if not mirrored else x - 0.02),
                         track=track, pts=paths[0][0]))
    PIECES.append((module_of(x - (0.02 if mirrored else 0)), track, "#4 turnout EP481-15%s" % hand))
    return paths


def add_curve(x, y, h, left, track, mirrored=False):
    p = arc(x, y, h, R4, A4, left)
    if mirrored:
        p = mirror(p)
    TRACKS.append(dict(paths=[p], kind="curve"))
    PIECES.append((module_of(p[0][0]), track, "R481-15 curve"))


def add_run(y, x0, x1, track, bumper_at=None):
    """Straight run from x0 to x1, split at module joints, filled with stock pieces."""
    cuts = [x0] + [j for j in JOINTS if x0 + 0.01 < j < x1 - 0.01] + [x1]
    for a, b in zip(cuts, cuts[1:]):
        pcs, err, _ = fill(b - a)
        mod = module_of(a)
        joints, x = [], a
        for pc in pcs:
            PIECES.append((mod, track, pc))
            x += piece_len(pc)
            joints.append(x)
        TRACKS.append(dict(paths=[straight(a, y, 0, b - a)], kind="straight", joints=joints[:-1], err=err,
                           module=mod, track=track, pieces=pcs, gap=b - a))
    if bumper_at is not None:
        PIECES.append((module_of(bumper_at + 0.01), track, "end bumper"))


def build_half(mirrored):
    m = mirrored
    side = "right" if m else "left"
    add_turnout(P_XO, MAIN2_Y, 0, "L", "%s ladder, main 2 -> mine" % side, "Main 2", m)
    x, y = P_XO + AX, MAIN2_Y + D
    names = ["lead", "track 1", "track 2", "track 3"]
    for k in range(4):
        add_turnout(x, y, A4, "R", "%s ladder -> %s" % (side, names[k]), "Ladder", m)
        x, y = x + LDX, y + LDY
    add_curve(x, y, A4, False, "Ladder", m)


build_half(False)
build_half(True)

# main crossover on the tipple module
c = B_X0 + C_MXO
add_turnout(c, MAIN1_Y, 0, "L", "main 1 -> main 2 crossover, on main 1", "Main 1")
add_turnout(c + 2 * AX, MAIN2_Y, 180, "L", "main 1 -> main 2 crossover, on main 2", "Main 2")

# straight runs
add_run(MAIN1_Y, 0, c, "Main 1")
add_run(MAIN1_Y, c + L4, TOTAL, "Main 1")
add_run(MAIN2_Y, 0, P_XO, "Main 2")
add_run(MAIN2_Y, P_XO + L4, c + 2 * AX - L4, "Main 2")
add_run(MAIN2_Y, c + 2 * AX, TOTAL - P_XO - L4, "Main 2")
add_run(MAIN2_Y, TOTAL - P_XO, TOTAL, "Main 2")
add_run(LEAD_Y, STARTS[0], TOTAL - STARTS[0], "Lead")
for k, y in enumerate(Y_TRACKS):
    s_ = STARTS[k + 1]
    add_run(y, s_, TOTAL - s_, "Track %d" % (k + 1))

# number the turnouts left to right, front to back
TURNOUTS.sort(key=lambda t: (round(t["x"] / 40), t["y"]))
for i, t in enumerate(TURNOUTS):
    t["id"] = "T%d" % (i + 1)

# ----------------------------------------------------------------------------
# Structures (footprints only, for planning) and capacities
# ----------------------------------------------------------------------------
TIPPLE_W = 130.0
TIP_X0, TIP_X1 = CENTER - TIPPLE_W / 2, CENTER + TIPPLE_W / 2
TIP_Y0, TIP_Y1 = Y_TRACKS[0] - 18, Y_TRACKS[-1] + 18
STRUCTS = [
    # x0, y0, x1, y1, label, style
    (TIP_X0, TIP_Y0, TIP_X1, TIP_Y1, "TIPPLE|4 loading tracks", "tipple"),
    (TIP_X0 - 150, 270, TIP_X0 + 10, 278, "", "conveyor"),
    (B_X0 + 10, 285, B_X0 + 110, 345, "MINE PORTAL|(in hillside)", "hill"),
    (TIP_X0 - 150, 300, TIP_X0 - 20, 345, "conveyor from|portal to tipple", "label"),
    (TIP_X1 + 30, 280, TIP_X1 + 140, 345, "prep plant /|coal silo", "bldg"),
    (JOINTS[1] - 330, 290, JOINTS[1] - 210, 340, "bathhouse &|mine office", "bldg"),
    (JOINTS[1] - 185, 290, JOINTS[1] - 125, 340, "supply|house", "bldg"),
    (60, 285, 300, 345, "hillside / trees", "hill"),
    (JOINTS[-2] + 140, 285, JOINTS[-2] + 360, 345, "refuse (gob) pile", "gob"),
    (TOTAL - 330, 290, TOTAL - 230, 340, "scale house", "bldg"),
    (TOTAL - 200, 285, TOTAL - 50, 345, "hillside / trees", "hill"),
]


def capacity():
    rows = []
    for k, s in enumerate(STARTS[1:]):
        e_len = TIP_X0 - (s + CLEAR)
        l_len = (TOTAL - s - CLEAR) - TIP_X1
        rows.append(("Track %d" % (k + 1), e_len, int(e_len // CAR_LEN), l_len, int(l_len // CAR_LEN)))
    return rows


CAP = capacity()


# ----------------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------------
M_L, M_T, M_B = 30.0, 70.0, 150.0
W_SVG, H_SVG = TOTAL + 2 * M_L, DEPTH + M_T + M_B


def P(x, y):
    return x + M_L, M_T + DEPTH - y


def poly(path, off=0.0):
    pts = []
    for x, y, h in path:
        r = math.radians(h)
        pts.append("%.2f,%.2f" % P(x - off * math.sin(r), y + off * math.cos(r)))
    return " ".join(pts)


HALO = 'paint-order="stroke" stroke="#ffffff" stroke-width="3" stroke-linejoin="round"'


def text(x, y, s, size=9, anchor="start", weight="normal", fill="#222", extra=""):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return ('<text x="%.1f" y="%.1f" font-size="%g" text-anchor="%s" font-weight="%s" fill="%s" %s>%s</text>'
            % (x, y, size, anchor, weight, fill, extra, s))


def build_svg():
    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" width="%.0fmm" height="%.0fmm" '
             'font-family="Helvetica, Arial, sans-serif">' % (W_SVG, H_SVG, W_SVG, H_SVG))
    o.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    o.append(text(M_L, 26, "T-TRAK N-scale coal mine set: %s" % " | ".join(
        "%s %s" % (m[1], m[0]) for m in MODS), 20, weight="bold"))
    o.append(text(M_L, 48, "Kato Unitrack, #4 turnouts (EP481-15). %d turnouts, 1 square = 100 mm. "
                  "Empties arrive on the left, are loaded under the tipple and leave as loads on the right."
                  % len(TURNOUTS), 11, fill="#555"))
    # module boxes
    for i, m in enumerate(MODS):
        x0, x1 = JOINTS[i] + 1, JOINTS[i + 1] - 1
        a, b = P(x0, DEPTH)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#dfe6cf" stroke="#6b5a3e" '
                 'stroke-width="2.5" rx="2"/>' % (a, b, x1 - x0, DEPTH))
    # grid
    for gx in range(0, int(TOTAL) + 1, 100):
        a, b = P(gx, 0)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000" stroke-opacity="0.06"/>'
                 % (a, b, a, b - DEPTH))
    for gy in range(0, int(DEPTH) + 1, 100):
        a, b = P(0, gy)
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#000" stroke-opacity="0.06"/>'
                 % (a, b, a + TOTAL, b))
    # coal-dust ballast area of the yard
    yd0, yd1 = LEAD_Y - 18, Y_TRACKS[-1] + 18
    if True:
        pts = [P(STARTS[0] - 60, yd0), P(TOTAL - STARTS[0] + 60, yd0), P(TOTAL - STARTS[-1] + 40, yd1),
               P(STARTS[-1] - 40, yd1)]
        o.append('<polygon points="%s" fill="#8d8a86" fill-opacity="0.35"/>'
                 % " ".join("%.1f,%.1f" % p for p in pts))
    # structures under the track (hills etc.)
    styles = {"tipple": ("#6e4b2a", 0.55, "#fff"), "conveyor": ("#7a6a58", 0.8, "#222"),
              "hill": ("#7d9a5c", 0.55, "#1f3310"), "bldg": ("#b98a5e", 0.7, "#2a1a0a"),
              "gob": ("#3b3835", 0.65, "#eee"), "label": ("#ffffff", 0.0, "#4a3b2a")}
    for x0, y0, x1, y1, lab, st in STRUCTS:
        if st == "tipple":
            continue
        col, op, tc = styles[st]
        a, b = P(x0, y1)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" fill-opacity="%g" rx="4"/>'
                 % (a, b, x1 - x0, y1 - y0, col, op))
        lines = lab.split("|")
        cy = b + (y1 - y0) / 2 - (len(lines) - 1) * 5.5 + 3.5
        for i, ln in enumerate(lines):
            o.append(text(a + (x1 - x0) / 2, cy + i * 11, ln, 9.5, "middle", "bold", tc))
    # track: roadbed, ties, rails
    all_paths = [p for t in TRACKS for p in t["paths"]]
    for p in all_paths:
        o.append('<polyline points="%s" fill="none" stroke="#a7a39d" stroke-width="%g"/>' % (poly(p), ROADBED_W))
    for p in all_paths:
        o.append('<polyline points="%s" fill="none" stroke="#4a3f36" stroke-width="16" '
                 'stroke-dasharray="1.6 2.6"/>' % poly(p))
    for p in all_paths:
        for s in (-GAUGE / 2, GAUGE / 2):
            o.append('<polyline points="%s" fill="none" stroke="#c9ccd1" stroke-width="1.1"/>' % poly(p, s))
    # piece joints on straight runs and bumpers
    for t in TRACKS:
        if t["kind"] != "straight":
            continue
        y = t["paths"][0][0][1]
        for jx in t.get("joints", []):
            a, b = P(jx + t["paths"][0][0][0] - t["paths"][0][0][0], y)
        x0 = t["paths"][0][0][0]
        acc = x0
        for pc in t.get("pieces", [])[:-1]:
            acc += piece_len(pc)
            a, b = P(acc, y)
            o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#e8e2d6" stroke-width="1.4"/>'
                     % (a, b - 12.5, a, b + 12.5))
        if "bumper" in t:
            a, b = P(t["bumper"], y)
            o.append('<rect x="%.1f" y="%.1f" width="5" height="14" fill="#c0392b"/>' % (a - 2.5, b - 7))
    # turnout ends
    for t in TRACKS:
        if t["kind"] in ("turnout", "curve"):
            for p in t["paths"]:
                for (x, y, h) in (p[0], p[-1]):
                    r = math.radians(h)
                    a1 = P(x - 12.5 * math.sin(r), y + 12.5 * math.cos(r))
                    a2 = P(x + 12.5 * math.sin(r), y - 12.5 * math.cos(r))
                    o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#e8e2d6" '
                             'stroke-width="1.4"/>' % (a1 + a2))
    # tipple on top of the tracks
    for x0, y0, x1, y1, lab, st in STRUCTS:
        if st != "tipple":
            continue
        a, b = P(x0, y1)
        o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#6e4b2a" fill-opacity="0.72" '
                 'stroke="#3d2814" stroke-width="2" rx="2"/>' % (a, b, x1 - x0, y1 - y0))
        for yt in Y_TRACKS:
            c1, c2 = P(x0 + 18, yt)
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="#1c1c1c" rx="1.5"/>'
                     % (c1, c2 - 3, x1 - x0 - 36))
        o.append(text(a + (x1 - x0) / 2, b - 16, "TIPPLE", 14, "middle", "bold", "#3d2814"))
        o.append(text(a + (x1 - x0) / 2, b - 4, "4 loading chutes", 9, "middle", "normal", "#3d2814"))
    # turnout labels
    for t in TURNOUTS:
        x, y = t["pts"][0], t["pts"][1]
        a, b = P(x, y)
        o.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#d35400" stroke="#fff" stroke-width="0.8"/>' % (a, b))
        if t["y"] < 70 or t["track"] == "Main 2":
            o.append(text(a, b + 22 if t["y"] < 70 else b + 24, "%s %s" % (t["id"], t["hand"]), 9, "middle",
                          "bold", "#a04000", extra=HALO))
        else:                       # ladder: label below/outside the diagonal
            right = t["x"] > CENTER
            o.append(text(a + (-12 if right else 12), b + 16, "%s %s" % (t["id"], t["hand"]), 9,
                          "end" if right else "start", "bold", "#a04000", extra=HALO))
    # track labels
    lx = STARTS[0] - 75
    for name, y in [("Main 1", MAIN1_Y), ("Main 2", MAIN2_Y)]:
        a, b = P(4, y)
        o.append(text(a, b - 14, name, 9, "start", "bold", "#333"))
    def lab_x(k):          # just past the point where the next track leaves the diagonal
        return STARTS[k + 1] + 20 if k + 1 < len(STARTS) else STARTS[k] + 40
    a, b = P(lab_x(0), LEAD_Y)
    o.append(text(a, b - 14, "Mine lead / runaround (bypasses the tipple)", 9, "start", "bold", "#333", extra=HALO))
    for k, y in enumerate(Y_TRACKS):
        a, b = P(lab_x(k + 1), y)
        o.append(text(a, b - 14, "Track %d  EMPTIES  \u2192" % (k + 1), 9, "start", "bold", "#1f4e79", extra=HALO))
        a, b = P(TOTAL - lab_x(k + 1), y)
        o.append(text(a, b - 14, "\u2192  LOADS  Track %d" % (k + 1), 9, "end", "bold", "#7b241c", extra=HALO))
    # module captions
    for i, m in enumerate(MODS):
        x0, x1 = JOINTS[i], JOINTS[i + 1]
        a, b = P((x0 + x1) / 2, 0)
        box = "928" if m[1] == "Triple" else "618"
        o.append(text(a, b + 26, "Module %s: %s" % (m[0], m[3]), 15, "middle", "bold"))
        o.append(text(a, b + 44, "%s, %s x %g mm box, %g mm of track per line" % (m[1], box, DEPTH, m[2]),
                      10.5, "middle", "normal", "#555"))
        if i:
            a, b = P(x0, 0)
            o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c0392b" stroke-width="1.2" '
                     'stroke-dasharray="6 4"/>' % (a, b + 4, a, b - DEPTH - 6))
    # capacity table
    ty = M_T + DEPTH + 72
    tot_e = sum(r[2] for r in CAP)
    tot_l = sum(r[4] for r in CAP)
    o.append(text(M_L, ty, "Capacity (%g mm hoppers): " % CAR_LEN + ",  ".join(
        "%s %d empty + %d loaded" % (r[0], r[2], r[4]) for r in CAP)
        + ".   Total %d empties + %d loads under/around the tipple." % (tot_e, tot_l), 11, fill="#333"))
    o.append(text(M_L, ty + 18, "Track spacing: mains 33 mm (T-TRAK), lead and tracks 1-4 at Kato's #4 ladder "
                  "spacing (32.6-32.8 mm). Track 4 centre is %.0f mm from the front edge, leaving %.0f mm "
                  "of scenery at the back." % (Y_TRACKS[-1], DEPTH - Y_TRACKS[-1] - 12.5), 11, fill="#333"))
    o.append(text(M_L, ty + 36, "Orange dots = turnout points (L/R = Kato hand).  Light ticks = Unitrack joints.  "
                  "Red dashed lines = module joints (yard tracks cross them).",
                  11, fill="#333"))
    o.append(text(M_L, ty + 54, "Structures are footprints for planning only.  FRONT EDGE (viewer side) "
                  "is at the bottom.", 11, fill="#333"))
    o.append("</svg>")
    return "\n".join(o)


# ----------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------
def write_csvs():
    order = [m[0] for m in MODS]
    counts = {}
    for mod, trk, pc in PIECES:
        name = pc.split(" @")[0]
        counts[(mod, trk, name)] = counts.get((mod, trk, name), 0) + 1
    with open(os.path.join(OUT, "coal_mine_track_parts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["module", "track", "piece", "qty"])
        for (mod, trk, pc), n in sorted(counts.items(), key=lambda k: (order.index(k[0][0]), k[0][1], k[0][2])):
            w.writerow([mod, trk, pc, n])
        w.writerow([])
        w.writerow(["TOTAL (whole set)", "", "piece", "qty"])
        tot = {}
        for (mod, trk, pc), n in counts.items():
            tot[pc] = tot.get(pc, 0) + n
        for pc, n in sorted(tot.items()):
            w.writerow(["", "", pc, n])
    with open(os.path.join(OUT, "coal_mine_turnouts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "module", "kato_turnout", "points_x_from_set_left_mm",
                    "points_x_from_module_left_mm", "track_y_from_front_mm", "role"])
        for t in TURNOUTS:
            mi = [m[0] for m in MODS].index(t["module"])
            w.writerow([t["id"], t["module"], "#4 EP481-15" + t["hand"], "%.1f" % t["x"],
                        "%.1f" % (t["x"] - JOINTS[mi]), "%.1f" % t["y"], t["role"]])
    return tot


def render_png(svg_path):
    node = shutil.which("node")
    if not node:
        print("node not found; skipping PNG export (the SVG is complete)")
        return
    shots = [("coal_mine_trackplan.png", 0, TOTAL, 1.0)]
    for i, m in enumerate(MODS):
        shots.append(("coal_mine_module_%s.png" % m[0], JOINTS[i] - 10, JOINTS[i + 1] + 10, 2.0))
    js = """
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const svg = fs.readFileSync(%r, 'utf8');
  const b = await chromium.launch();
  const shots = %s;
  for (const [name, x0, x1, s] of shots) {
    const vb = [x0 + %f, 0, x1 - x0, %f];
    const doc = svg.replace(/viewBox="[^"]*" width="[^"]*" height="[^"]*"/,
      `viewBox="${vb.join(' ')}" width="${vb[2]}" height="${vb[3]}"`);
    const p = await b.newPage({ viewport: { width: Math.ceil(vb[2]), height: Math.ceil(vb[3]) },
                                deviceScaleFactor: s });
    await p.setContent('<html><body style="margin:0">' + doc + '</body></html>');
    await p.screenshot({ path: %r + '/' + name });
    await p.close();
  }
  await b.close();
})();
""" % (svg_path, [list(s) for s in shots], M_L - (0 if True else 0), H_SVG, OUT)
    js = js.replace("x0 + %f" % M_L, "x0 + %f" % M_L)
    tmp = os.path.join(OUT, "_render.js")
    with open(tmp, "w") as f:
        f.write(js)
    try:
        subprocess.run([node, tmp], check=True)
    except Exception as e:
        print("PNG export failed (%s); the SVG is complete" % e)
    finally:
        os.remove(tmp)


def report():
    print("Modules:", " | ".join("%s %s %g" % (m[0], m[1], m[2]) for m in MODS), "= %g mm" % TOTAL)
    print("Ladder turnout on main 2 at x=%.1f, main crossover %.1f into module B" % (P_XO, C_MXO))
    print("Track y:", ["%.1f" % y for y in [MAIN1_Y, MAIN2_Y, LEAD_Y] + Y_TRACKS])
    bad = [t for t in TRACKS if t["kind"] == "straight" and "err" in t and abs(t["err"]) > TOL]
    for t in TRACKS:
        if t["kind"] == "straight" and "gap" in t:
            print("  %-8s %-3s gap %7.2f  -> %-55s err %+.2f" % (t["track"], t["module"], t["gap"],
                                                                 " + ".join(t["pieces"]), t["err"]))
    print("runs outside tolerance:", len(bad))
    for r in CAP:
        print("  %s: empties %.0f mm (%d cars), loads %.0f mm (%d cars)" % r)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    svg_path = os.path.join(OUT, "coal_mine_trackplan.svg")
    with open(svg_path, "w") as f:
        f.write(build_svg())
    tot = write_csvs()
    report()
    print("Totals:", tot)
    render_png(svg_path)
    print("wrote", OUT)
