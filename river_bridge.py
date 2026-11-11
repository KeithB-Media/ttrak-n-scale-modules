"""
River-crossing deck-girder bridge: two N-scale T-TRAK double modules.
Printed bridge parts that snap together, for the laser-cut plywood boxes in river_laser.py.

Inspired by a classic double-track river crossing: steel deck plate girder spans with close
stiffeners and a walkway handrail, on tall round-nosed concrete piers with pour lines.
No real logos, signs or trains are modelled.

The pair, seen from the front:

    | Module A (West)                                | Module B (East)                              |
    | std end | embankment + abutment | river, 2 piers, half pier || half pier, 2 piers | abutment ...

Snap-together printed parts (no glue needed on the bridge itself):
  * pier_full / pier_joint_half : two split, barbed pegs under the pier snap through 7 mm holes in
                                  the plywood base.  Holes in the pier cap take the girder pins.
  * deck_girder_span            : one part for every span and both tracks.  2 mm pins under the
                                  bearing shoes drop into the pier caps / the abutment seat plate.
                                  Walkway brackets on one side (the front-track spans are turned
                                  round so the brackets face out on both tracks).
  * handrail                    : pegs press into the walkway brackets.
  * feeder wires                : a slot in each girder end, a bore down every pier, holes in the
                                  seat and base plates: wires run hidden from the rails to under the module.
  * foot_nut_block_rock         : glued on top of the base over each foot hole; traps an M6 nut.
                                  Boulder-shaped, so the two in the river look like river rocks.
  * foot_thumbwheel             : holds the head of an M6 x 20 bolt.  Turn it to level the module.

Run:  python river_bridge.py [--no-render]
Needs: numpy, manifold3d, trimesh (pip install numpy manifold3d trimesh); renders need bpy.
Output: ttrak_output/river_bridge/  (STLs, parts list, renders) + laser files (river_laser.py)
"""

import os
import sys
import csv
import math
import numpy as np
import trimesh
from manifold3d import Manifold, Mesh, CrossSection, OpType, set_circular_segments

set_circular_segments(48)

# ----------------------------------------------------------------------------
# PARAMETERS (mm).  z = 0 is the T-TRAK track base (top of the module top plate).
# Module-local x runs along the track (0 = outer end of module A); y = 0 is the FRONT edge.
# ----------------------------------------------------------------------------
MW, MD = 618.0, 330.0            # double module (laser template footprint)
GAP = 2.0                        # Unitrack is 620 per module, so modules sit 2 mm apart
PLY = 5.0                        # laser-cut ply
HEIGHTS = {"70mm_template": 70.09, "63.5mm_2.5in": 63.5}     # table -> track base

# feet: the box is built FOOT_NOM shorter; the adjustable feet make up the rest
WHEEL_H = 6.0                    # thumbwheel thickness
FOOT_NOM = 12.0                  # table -> underside of the base at the nominal setting
BOLT_L = 20.0                    # M6 x 20 hex bolt
NUT_AF, NUT_H = 10.0, 5.0        # M6 nut
BLOCK_BORE = 11.5                # bolt clearance bore inside the nut block (above the base)
M6_CLEAR = 6.6


def box_h(top):
    """Height of the plywood box (underside of the base -> track base)."""
    return top - FOOT_NOM


def foot_range():
    """(min, max) table -> base underside, from the bolt-tip and nut-engagement limits."""
    g_min = BOLT_L - PLY - BLOCK_BORE              # bolt tip at the top of the bore
    g_max = BOLT_L - PLY - NUT_H                   # bolt tip just through the nut
    return WHEEL_H + g_min, WHEEL_H + g_max


# track (same as the rest of the repo)
FRONT_BALLAST_EDGE, BALLAST_W, TRACK_SPACING = 38.0, 25.0, 33.0
TRACK_Y = (FRONT_BALLAST_EDGE + BALLAST_W / 2, FRONT_BALLAST_EDGE + BALLAST_W / 2 + TRACK_SPACING)
TRACK_PIECES = (248.0, 248.0, 124.0)
UNITRACK_H = 7.0
WATER = 3.0                      # pour depth on the base plate

XA = 142.0                       # abutment face

# bridge
PIER_T, PIER_W = 40.0, 104.0     # pier top (under the coping): along track x across track
PIER_YC = (TRACK_Y[0] + TRACK_Y[1]) / 2          # 67
BATTER = 2.0                     # pier grows by this much on every side, top to bottom
LIFT = 3.0                       # pour-line spacing
GIRDER_D = 16.0                  # deck top to bottom flange
SHOE = 1.6
SEAT_Z = -GIRDER_D - SHOE        # -17.6: pier cap / abutment seat
DECK_W = 27.0
WEB_HALF = 12.9                  # girder faces flush with the deck edge
STIFF_STEP = 5.0
END_GAP = 1.5                    # gap between girder ends over a pier
BEAR = PIER_T / 2 - END_GAP / 2  # 19.25
JOINT_PIER_X = MW - PIER_T / 2   # 598
CLEAR = (JOINT_PIER_X - XA - 2 * PIER_T) / 3     # 125.3
PIERS_XD = [XA + CLEAR + PIER_T / 2, XA + 2 * CLEAR + 1.5 * PIER_T]   # 287.3, 452.7
GIRDER_L = CLEAR + 2 * BEAR                       # 163.8 (~86 ft)
SPANS_XD = [XA - BEAR, PIERS_XD[0] + PIER_T / 2 - BEAR, PIERS_XD[1] + PIER_T / 2 - BEAR]
BACKWALL_X = XA - BEAR - 0.5                      # 122.25

# snap / locating features
PIN_D, PIN_L, PIN_HOLE_D, PIN_HOLE_DEPTH = 2.0, 2.5, 2.4, 3.0
SHOE_X = 5.0                     # shoe / pin centre from the girder end
PIN_DY = (-WEB_HALF, WEB_HALF)   # pins under both webs
PEG_D, PEG_BARB_D, PEG_HOLE_D, PEG_SLOT = 6.6, 7.6, 7.0, 1.8
PEG_DY = 25.0                    # pier pegs at PIER_YC +- 25
HALF_PEG_X = -10.0               # joint half pier pegs (pier centre = module end)
BRACKET_STEP, BRACKET_X0 = 24.0, 6.0
RAIL_T, RAIL_H = 1.0, 7.0        # handrail thickness / height (~1.1 m)
RAIL_Y = WEB_HALF + 2.7          # 15.6: handrail centre plane (outside the top flange)
RAIL_PEG = (1.6, 1.0, 2.8)       # peg x, y, length
RAIL_HOLE = (1.8, 1.2)
# feeder wires: slot in the girder deck -> between the webs -> bore down the pier / abutment -> under the base
FEED_X = 12.0                    # slot centre from each girder end (over the pier / seat)
FEED_SLOT = (2.5, 16.0)          # slot size x, y (under the track centre; drill the roadbed over it)
FEED_BORE = 4.5                  # vertical wire bore in the piers, holes in the seat and base plates
FEED_DX = END_GAP / 2 + FEED_X   # 12.75: bore offset from a pier centre

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttrak_output", "river_bridge")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
class ValueNoise:
    def __init__(self, seed, size=256):
        self.r = np.random.default_rng(seed).random((size, size))
        self.n = size

    def __call__(self, x, y):
        xi, yi = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - xi, y - yi
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        n, r = self.n, self.r
        a, b = r[yi % n, xi % n], r[yi % n, (xi + 1) % n]
        c, d = r[(yi + 1) % n, xi % n], r[(yi + 1) % n, (xi + 1) % n]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    def fbm(self, x, y, scale, octaves=4):
        v, amp, tot = 0.0, 1.0, 0.0
        for o in range(octaves):
            f = 2 ** o / scale
            v = v + amp * (self(x * f + 37 * o, y * f + 91 * o) - 0.5)
            tot += amp
            amp *= 0.5
        return v / tot * 2


def heightfield(xs, ys, Z, zbot):
    """Watertight solid between a height field Z(ys, xs) and a flat bottom."""
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    top = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    tris = [np.column_stack([a.ravel(), b.ravel(), c.ravel()]),
            np.column_stack([a.ravel(), c.ravel(), d.ravel()])]
    per = np.array(list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0]))
    n = len(top)
    bot = top[per].copy()
    bot[:, 2] = zbot
    verts = np.vstack([top, bot, [[xs.mean(), ys.mean(), zbot]]])
    bi = n + np.arange(len(per))
    ci = n + len(per)
    t_i, t_j, b_i, b_j = per, np.roll(per, -1), bi, np.roll(bi, -1)
    tris += [np.column_stack([t_i, b_i, b_j]), np.column_stack([t_i, b_j, t_j]),
             np.column_stack([np.full(len(per), ci), b_j, b_i])]
    return Manifold(Mesh(vert_properties=verts.astype(np.float32), tri_verts=np.vstack(tris).astype(np.uint32)))


def cube(x0, y0, z0, x1, y1, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cyl(x, y, z0, z1, d0, d1=None, n=32):
    return Manifold.cylinder(z1 - z0, d0 / 2, (d1 if d1 is not None else d0) / 2, n).translate((x, y, z0))


def pier_plan(L, W):
    """Pier plan centred at the origin: L along x (track), W along y, semicircular noses at +-y."""
    r = L / 2
    return CrossSection.hull(CrossSection.circle(r).translate((0, W / 2 - r)) +
                             CrossSection.circle(r).translate((0, -(W / 2 - r))))


def union(parts):
    parts = list(parts)
    return Manifold.batch_boolean(parts, OpType.Add) if parts else Manifold()


def to_trimesh(m):
    mm = m.to_mesh()
    return trimesh.Trimesh(vertices=np.array(mm.vert_properties)[:, :3], faces=np.array(mm.tri_verts), process=False)


def export(m, path, rot=None):
    """Export to STL, optionally rotated (degrees xyz), dropped onto the bed at the origin."""
    if rot:
        m = m.rotate(rot)
    bb = m.bounding_box()
    m = m.translate((-bb[0], -bb[1], -bb[2]))
    to_trimesh(m).export(path)
    return tuple(round(bb[i + 3] - bb[i], 1) for i in range(3))


# ----------------------------------------------------------------------------
# Printed parts
# ----------------------------------------------------------------------------
def bracket_xs(L=GIRDER_L):
    xs, x = [], BRACKET_X0
    while x < L - 4:
        xs.append(x)
        x += BRACKET_STEP
    return xs


def deck_girder(L=GIRDER_L):
    """Single-track deck plate girder span: x along the span, track centre at y = 0, deck top at
    z = 0.  Locating pins under the shoes, walkway brackets on the +y side.  Prints upside down."""
    h = DECK_W / 2
    tw, ft, fw = 1.2, 1.2, 3.0
    p = [cube(0, -h, -1.6, L, h, 0)]                                       # deck plate
    for s in (-1, 1):
        yc = s * WEB_HALF
        p.append(cube(0, yc - tw / 2, -GIRDER_D, L, yc + tw / 2, -1.6))     # web
        p.append(cube(0, yc - fw / 2, -GIRDER_D, L, yc + fw / 2, -GIRDER_D + ft))
        p.append(cube(0, yc - fw / 2, -1.6 - ft, L, yc + fw / 2, -1.6))
        x = 1.5
        while x < L - 1:                                                   # stiffeners
            end = x < 10 or x > L - 10
            w = 1.0 if end else 0.6
            for o in (-1, 1):
                p.append(cube(x - w / 2, yc + o * tw / 2 - (0.9 if o < 0 else 0), -GIRDER_D + ft,
                              x + w / 2, yc + o * tw / 2 + (0.9 if o > 0 else 0), -1.6 - ft))
            x += 3.0 if end else STIFF_STEP
        for xc in (SHOE_X, L - SHOE_X):                                    # shoes + tapered pins
            p.append(cube(xc - 3.5, yc - 2.0, SEAT_Z, xc + 3.5, yc + 2.0, -GIRDER_D))
            p.append(cyl(xc, yc, SEAT_Z - PIN_L, SEAT_Z + 0.01, PIN_D * 0.8, PIN_D, 20))
    nb = max(2, int(round(L / 30)))
    for k in range(nb + 1):                                                # diaphragms
        x = 1.0 + (L - 2.0) * k / nb
        p.append(cube(x - 0.5, -WEB_HALF, -GIRDER_D + 2, x + 0.5, WEB_HALF, -1.6))
    cuts = [cube(xf - FEED_SLOT[0] / 2, -FEED_SLOT[1] / 2, -3, xf + FEED_SLOT[0] / 2, FEED_SLOT[1] / 2, 1)
            for xf in (FEED_X, L - FEED_X)]                               # feeder wire slots
    for xc in bracket_xs(L):                                               # walkway brackets
        p.append(cube(xc - 2.0, h - 0.01, -3.0, xc + 2.0, RAIL_Y + 2.0, 0))
        cuts.append(cube(xc - RAIL_HOLE[0] / 2, RAIL_Y - RAIL_HOLE[1] / 2, -4,
                         xc + RAIL_HOLE[0] / 2, RAIL_Y + RAIL_HOLE[1] / 2, 1))
    return union(p) - union(cuts)


def handrail(L=GIRDER_L):
    """Walkway handrail, built in place on a girder (centre plane y = RAIL_Y).  Prints flat."""
    y0, y1 = RAIL_Y - RAIL_T / 2, RAIL_Y + RAIL_T / 2
    p = [cube(0.5, y0, 0, L - 0.5, y1, 0.8),                    # toe rail
         cube(0.5, y0, RAIL_H - 0.8, L - 0.5, y1, RAIL_H),       # top rail
         cube(0.5, y0, RAIL_H / 2 - 0.4, L - 0.5, y1, RAIL_H / 2 + 0.4)]
    x = BRACKET_X0
    while x < L - 1:
        p.append(cube(x - 0.4, y0, 0, x + 0.4, y1, RAIL_H))      # posts every 12 mm
        x += BRACKET_STEP / 2
    pw, pt, pl = RAIL_PEG
    for xc in bracket_xs(L):
        p.append(cube(xc - pw / 2, RAIL_Y - pt / 2, -pl, xc + pw / 2, RAIL_Y + pt / 2, 0.01))
    return union(p)


def snap_peg(x, y, zb):
    """Split, barbed peg pointing down from the pier underside (z = zb) through the 5 mm ply."""
    shank = cyl(x, y, zb - PLY - 0.2, zb + 0.01, PEG_D)
    barb = cyl(x, y, zb - PLY - 2.2, zb - PLY - 0.2, PEG_D - 1.6, PEG_BARB_D)
    slot = cube(x - PEG_SLOT / 2, y - 5, zb - PLY - 3, x + PEG_SLOT / 2, y + 5, zb - 0.3)
    return (shank + barb) - slot


def pier(top, half=False):
    """Round-nosed battered concrete pier standing on the base plate of a module of height `top`.
    Snap pegs below, girder pin holes in the cap.  half=True keeps x <= 0 (joint half pier)."""
    zb = -(box_h(top) - PLY)                                     # base plate top
    H = SEAT_Z - 1.5 - zb
    Lb, Wb = PIER_T + 2 * BATTER, PIER_W + 2 * BATTER
    sc = (PIER_T / Lb, PIER_W / Wb)
    shaft = Manifold.extrude(pier_plan(Lb, Wb), H, scale_top=sc).translate((0, 0, zb))
    core = Manifold.extrude(pier_plan(Lb - 0.7, Wb - 0.7), H, scale_top=sc).translate((0, 0, zb))
    slabs = []
    z = zb + WATER + 2.0
    while z < SEAT_Z - 4:                                        # pour lines
        slabs.append(cube(-80, -80, z, 80, 80, z + 0.4))
        z += LIFT
    shaft = shaft - (union(slabs) - core)
    top_cs = pier_plan(PIER_T, PIER_W)
    cap = Manifold.extrude(pier_plan(PIER_T + 1.6, PIER_W + 1.6), 1.5).translate((0, 0, SEAT_Z - 1.5))
    chamfer = Manifold.extrude(top_cs, 0.7, scale_top=((PIER_T + 1.2) / PIER_T, (PIER_W + 1.2) / PIER_W)) \
        .translate((0, 0, SEAT_Z - 2.1))
    p = (shaft + cap + chamfer).translate((0, PIER_YC, 0))
    holes = []
    for sx in ((-1,) if half else (-1, 1)):
        for yt in TRACK_Y:
            for dy in PIN_DY:
                holes.append(cyl(sx * (END_GAP / 2 + SHOE_X), yt + dy, SEAT_Z - PIN_HOLE_DEPTH, SEAT_Z + 1,
                                 PIN_HOLE_D, PIN_HOLE_D, 20))
            holes.append(cyl(sx * FEED_DX, yt, zb - 1, SEAT_Z + 1, FEED_BORE, FEED_BORE, 24))   # feeder bore
    p = p - union(holes)
    if half:
        p = p ^ cube(-80, -10, -100, 0, 200, 10)
        pegs = [snap_peg(HALF_PEG_X, PIER_YC + s * PEG_DY, zb) for s in (-1, 1)]
    else:
        pegs = [snap_peg(0, PIER_YC + s * PEG_DY, zb) for s in (-1, 1)]
    return p + union(pegs)


def feeder_points():
    """(x, y) of every feeder wire path through the base plate (module A coordinates)."""
    xs = [XA - BEAR + FEED_X]                                   # abutment seat (first span)
    for xc in PIERS_XD:
        xs += [xc - FEED_DX, xc + FEED_DX]
    xs.append(MW - FEED_DX)                                     # joint half pier
    return [(x, y) for x in xs for y in TRACK_Y]


def foot_nut_block():
    """Boulder-shaped nut block, glued on the base plate over a foot hole.  M6 nut trap from below,
    bolt bore above it.  Origin = hole centre on the base plate top.  Prints as is."""
    a, b = 14.0, 12.0
    xs = np.arange(-a, a + 1e-6, 0.5)
    ys = np.arange(-b, b + 1e-6, 0.5)
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X / a, Y / b)
    nz = ValueNoise(3)
    Z = 1.5 + (BLOCK_BORE + 1.6 - 1.5) * np.sqrt(np.clip(1 - r ** 3, 0, 1)) \
        + 1.0 * nz.fbm(X + 50, Y + 50, 6, 3) * (r < 0.9)
    Z = np.maximum(Z, 1.2)
    Z = np.where(r < 0.35, np.maximum(Z, BLOCK_BORE + 1.4), Z)       # solid roof over the bore
    rock = heightfield(xs, ys, Z, 0.0)
    rock = rock ^ Manifold.extrude(CrossSection.circle(1.0, 64).scale((a, b)), 40)
    nut = Manifold.extrude(CrossSection.circle(NUT_AF / math.sqrt(3) + 0.1, 6), NUT_H + 0.2).translate((0, 0, -0.01))
    bore = cyl(0, 0, -0.01, BLOCK_BORE, M6_CLEAR)
    return rock - nut - bore


def foot_thumbwheel():
    """Knurled thumbwheel: the M6 bolt head sits in the hex pocket, shank up.  Prints as is."""
    r = 12.0
    w = cyl(0, 0, 0, WHEEL_H, 2 * r, 2 * r, 64)
    knurl = [cyl(r * math.cos(2 * math.pi * k / 20), r * math.sin(2 * math.pi * k / 20), -1, WHEEL_H + 1, 2.0, 2.0, 12)
             for k in range(20)]
    head = Manifold.extrude(CrossSection.circle(NUT_AF / math.sqrt(3) + 0.1, 6), 4.3).translate((0, 0, WHEEL_H - 4.3))
    return w - union(knurl) - head


# ----------------------------------------------------------------------------
# Assembly (checks + renders), module A coordinates; B = mirror about x = MW + GAP/2
# ----------------------------------------------------------------------------
def bridge_parts(top, which="A"):
    g, rail = deck_girder(), handrail()
    pf, ph = pier(top), pier(top, half=True)
    out = {"girder": [], "rail": [], "pier": []}
    for x0 in SPANS_XD:
        for i, yc in enumerate(TRACK_Y):
            if i == 1:          # back track: brackets face the back
                out["girder"].append(g.translate((x0, yc, 0)))
                out["rail"].append(rail.translate((x0, yc, 0)))
            else:               # front track: the same span turned round, brackets face the front
                out["girder"].append(g.rotate((0, 0, 180)).translate((x0 + GIRDER_L, yc, 0)))
                out["rail"].append(rail.rotate((0, 0, 180)).translate((x0 + GIRDER_L, yc, 0)))
    for xc in PIERS_XD:
        out["pier"].append(pf.translate((xc, 0, 0)))
    out["pier"].append(ph.translate((MW, 0, 0)))
    if which == "B":
        for k in out:
            out[k] = [m.mirror((1, 0, 0)).translate((2 * MW + GAP, 0, 0)) for m in out[k]]
    return out


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main(render=True):
    import river_laser as rl
    stl = os.path.join(OUT, "stl")
    os.makedirs(stl, exist_ok=True)
    for root, _, files in os.walk(stl):
        for f in files:
            if f.endswith(".stl"):
                os.remove(os.path.join(root, f))
    rows = []

    def ex(m, rel, qty, rot=None, note=""):
        path = os.path.join(stl, rel + ".stl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        dims = export(m, path, rot)
        rows.append((rel, qty) + dims + (note,))
        print("  %-52s x%-3d %6.1f x %6.1f x %6.1f" % ((rel, qty) + dims))

    ex(deck_girder(), "deck_girder_span_print_upside_down", 12, rot=(180, 0, 0),
       note="6 per module; front-track spans are turned round so the brackets face out")
    ex(handrail(), "handrail_print_flat", 12, rot=(90, 0, 0), note="1 per span; leave the front ones off if you prefer")
    ex(foot_nut_block(), "foot_nut_block_rock", 8, note="4 per module; M6 nut in the pocket, glue over the foot hole")
    ex(foot_thumbwheel(), "foot_thumbwheel", 8, note="4 per module; M6 x 20 hex bolt head in the pocket")
    for label, top in HEIGHTS.items():
        ex(pier(top), "%s/pier_full_print_upside_down" % label, 4, rot=(180, 0, 0), note="2 per module")
        ex(pier(top, half=True), "%s/pier_joint_half_print_upside_down" % label, 2, rot=(180, 0, 0),
           note="1 per module (module B: same part, turned round)")
    with open(os.path.join(OUT, "river_bridge_parts.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["part", "qty_for_pair", "x_mm", "y_mm", "z_mm", "notes"])
        w.writerows(rows)
    lo, hi = foot_range()
    print("Feet: base underside %.1f .. %.1f mm above the table (nominal %.1f)" % (lo, hi, FOOT_NOM))

    for r in rl.write_all():
        print("  laser %s: box %.1f x %.1f x %.1f | overlap %.2f | unfilled %.2f | %d sheet(s) %s"
              % (r[0], *r[1], r[2], r[3], r[4], r[5]))

    asm = os.path.join(OUT, "_assembly")
    os.makedirs(asm, exist_ok=True)
    top = HEIGHTS["70mm_template"]
    for which in ("A", "B"):
        for k, ms in bridge_parts(top, which).items():
            to_trimesh(union(ms)).export(os.path.join(asm, "%s_%s.stl" % (k, which)))
        for k, m in rl.assembly(top, which).items():
            to_trimesh(m).export(os.path.join(asm, "%s_%s.stl" % (k, which)))
    if render:
        import river_bridge_render
        river_bridge_render.render(OUT, asm)


if __name__ == "__main__":
    main(render="--no-render" not in sys.argv)
