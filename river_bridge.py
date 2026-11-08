"""
River-gap deck-girder bridge: two fully 3D-printed N-scale T-TRAK double modules.

Inspired by a classic double-track railroad crossing of a rocky river gap: steel deck plate
girder spans on tall, round-nosed concrete piers, a wooded rock cliff rising behind the river.
No real logos, signs or trains are modelled.

The pair, seen from the front:

    | Module A (West)                         | Module B (East)                         |
    | std end | transition | dropped river ...|... dropped river | transition | std end |
    |  track  | embankment + abutment  pier  pier  joint pier  pier  pier  abutment     |

  * Each double module (618 x 355 mm, 70 mm to the track base) has a TRANSITION at its outer
    end: full T-TRAK height for 40 mm (joins any standard module), then the track runs out on
    an embankment between concrete wing walls to a concrete abutment, while the ground drops
    away in front and behind.
  * The rest of each module is the DROPPED SECTION: a river bed 62 mm below the track base
    (8 mm above the table), with a rock cliff rising behind it to 42 mm above the track.
  * Three deck girder spans per track per module (164 mm, ~86 ft prototype) on two full piers
    and a split pier at the module joint (one half belongs to each module, so the modules come
    apart for transport like any other T-TRAK modules).
  * Kato Unitrack (248 + 248 + 124 mm per line) sits on the embankment and on the girder decks.

Everything prints with no supports.  The module itself is split into 6 bed-sized tiles
(206 x 177.5 mm) that are glued together and locked with printed bow-tie keys underneath.

Run:  python river_bridge.py [--no-render]
Needs: numpy, manifold3d, trimesh  (pip install numpy manifold3d trimesh); renders need bpy.
Output: ttrak_output/river_bridge/
"""

import os
import sys
import math
import csv
import numpy as np
import trimesh
from manifold3d import Manifold, Mesh, CrossSection, JoinType, OpType, set_circular_segments

set_circular_segments(48)

# ----------------------------------------------------------------------------
# PARAMETERS (mm).  z = 0 is the T-TRAK track base (top of a normal module).
# Module-local x runs along the track; y = 0 is the FRONT edge.
# xd = "design x" = distance from the module's OUTER end (0) to the joint end (618).
# ----------------------------------------------------------------------------
MW, MD = 618.0, 355.0            # double module
TOP = 70.0                       # track base above table
ZB = -TOP                        # table / module bottom
GAP = 2.0                        # Unitrack is 620 per module, so modules sit 2 mm apart
GRID = 1.0                       # terrain resolution

BED = -62.0                      # river bed (8 mm above table)
WATER = -59.0                    # top of a 3 mm resin / acrylic-gel water pour
CLIFF_TOP = 42.0                 # back edge rock cliff, above track base
FLAT_END = 40.0                  # standard-height strip at the outer end

# track (same as the rest of the repo)
FRONT_BALLAST_EDGE, BALLAST_W, TRACK_SPACING = 38.0, 25.0, 33.0
TRACK_Y = (FRONT_BALLAST_EDGE + BALLAST_W / 2, FRONT_BALLAST_EDGE + BALLAST_W / 2 + TRACK_SPACING)
TRACK_PIECES = (248.0, 248.0, 124.0)
UNITRACK_H = 7.0

# abutment / embankment
WING_IN0, WING_IN1 = 16.0, 118.0     # inside faces of the wing walls (corridor between them)
WING_T = 4.0
WING_X0 = 96.0                       # wing walls start
XA = 142.0                           # abutment front face
FILL_SLOPE = 1.5                     # embankment side slope (vertical per horizontal)

# bridge
PIER_T, PIER_W = 40.0, 104.0         # pier top (under the coping): along track x across track
PIER_YC = (TRACK_Y[0] + TRACK_Y[1]) / 2          # 67
BATTER = 2.0                         # pier grows by this much on every side, top to bottom
SOCKET = 1.5                         # pier peg depth into the river bed
GIRDER_D = 16.0                      # deck top to bottom flange (span/9)
SHOE = 1.6                           # bearing shoes under the girder ends
SEAT_Z = -GIRDER_D - SHOE            # -17.6: pier and abutment seat
DECK_W = 27.0                        # girder deck (Unitrack roadbed is 25)
WEB_HALF = 12.9                      # girder webs near the deck edge (faces flush with it)
STIFF_STEP = 5.0                     # web stiffener spacing (~0.8 m)
RAIL_H = 7.0                         # walkway handrail height above the deck (~1.1 m)
LIFT = 3.0                           # pier pour-line spacing
END_GAP = 1.5                        # expansion gap between girder ends over a pier
BEAR = PIER_T / 2 - END_GAP / 2      # 19.25: girder length resting on each support
JOINT_PIER_X = MW - PIER_T / 2       # 598: face of the joint half pier (centre on the module end)
CLEAR = (JOINT_PIER_X - XA - 2 * PIER_T) / 3      # 125.3 mm clear opening
PIERS_XD = [XA + CLEAR + PIER_T / 2, XA + 2 * CLEAR + 1.5 * PIER_T]   # 287.3, 452.7 (centres)
GIRDER_L = CLEAR + 2 * BEAR                       # 163.8 (~86 ft)
BACKWALL_X = XA - BEAR - 0.5                      # abutment backwall face (0.5 mm behind the girder end)
SPANS_XD = [XA - BEAR, PIERS_XD[0] + PIER_T / 2 - BEAR, PIERS_XD[1] + PIER_T / 2 - BEAR]

# tiles and keys
TILE_X = (0.0, 206.0, 412.0, MW)
TILE_Y = (0.0, MD / 2, MD)
KEY_L, KEY_W, KEY_NECK, KEY_D, KEY_CLR = 32.0, 16.0, 7.0, 3.0, 0.15

SEED = {"A": 11, "B": 23}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttrak_output", "river_bridge")


# ----------------------------------------------------------------------------
# Noise
# ----------------------------------------------------------------------------
class ValueNoise:
    def __init__(self, seed, size=512):
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
        return v / tot * 2          # about -1..1


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------
# Terrain height field
# ----------------------------------------------------------------------------
def terrain(xd, y, gx, which):
    """Ground height for design x (xd), y, at global x (gx) for module 'A' or 'B'."""
    nz = ValueNoise(SEED[which])
    gnoise = ValueNoise(5)                    # shared noise, continuous across the joint

    # 1. ground in front of / behind the embankment drops from track level to the river
    ground = BED + (0 - BED) * (1 - smoothstep(FLAT_END, XA + 8, xd))

    # 2. embankment fill between and around the wing walls
    w0, w1 = WING_IN0 - WING_T, WING_IN1 + WING_T          # 12 .. 122
    dy = np.maximum(np.maximum(w0 - y, y - w1), 0)
    dx = np.maximum(xd - XA, 0) * 2.5                       # steep riprap end past the abutment
    outside = (y < w0) | (y > w1)
    fill = np.where(outside, -FILL_SLOPE * np.hypot(dx, dy), -1e3)
    fill = np.where(~outside & (xd <= BACKWALL_X), 0.0, fill)

    # 3. rock cliff behind the river (shared noise -> matches across the joint)
    bank = 172 + 9 * gnoise.fbm(gx, 0 * gx, 120, 2)
    t = np.clip((y - bank) / (MD - bank), 0, 1)
    top = CLIFF_TOP * smoothstep(10, 150, xd)              # fades to track level at the outer end
    cliff = BED + (top - BED) * (1 - (1 - t) ** 2.8)
    # rock strata: partly terrace the cliff into ledges
    step = 7.0 + 2 * gnoise.fbm(gx, y, 200, 1)
    q = np.floor(cliff / step) * step
    fr = (cliff - q) / step
    terr = q + step * smoothstep(0.55, 1.0, fr)
    cliff = 0.55 * cliff + 0.45 * terr
    cliff_mask = smoothstep(0.0, 0.08, t)
    cliff = np.where(t > 0, cliff, -1e3)

    z = np.maximum(np.maximum(ground, fill), cliff)
    flat = np.abs(z) < 0.01

    # 4. surface texture: big rock noise on the cliff, smaller on slopes, tiny on the bed
    slope_mask = smoothstep(0, 6, -z) * smoothstep(0, 6, z - BED)
    rock = (gnoise.fbm(gx, y, 22, 4) * 4.0 + gnoise.fbm(gx + 300, y, 70, 3) * 7.0) * cliff_mask \
        + nz.fbm(gx, y, 9, 3) * 1.4 * slope_mask
    rock = np.where(flat, 0.0, rock)
    z = z + rock
    bed = z < BED + 0.8
    z = np.where(bed, BED + 0.4 + 0.4 * nz.fbm(gx, y, 15, 2), z)

    # 5. rocks, rock ledges and grassy islands in the river (global positions, so A and B differ)
    rocks = {"A": [(232, 46, 15, 6.0), (248, 34, 8, 4.0), (540, 18, 9, 3.5)],
             "B": [(905, 28, 17, 5.5), (888, 50, 7, 3.5), (700, 132, 12, 3.8)]}
    for (rx, ry, r, h) in rocks[which]:
        d = np.hypot(gx - rx, (y - ry) * 1.3) / r
        bump = BED + h * np.clip(1 - d * d, 0, 1) ** 0.7 + 1.5 * nz.fbm(gx, y, 4, 2) * (d < 1)
        z = np.maximum(z, bump)
    # long, low rock ledges just breaking the surface: (x, y, half-length, half-width, angle, height)
    ledges = {"A": [(195, 140, 45, 4, 20, 4.2), (370, 8, 40, 3.5, -12, 3.6), (530, 152, 50, 4.5, 8, 4.2),
                    (365, 138, 30, 3, -25, 3.8)],
              "B": [(700, 9, 40, 3.5, 12, 3.6), (870, 150, 45, 4.5, -18, 4.2), (1075, 140, 40, 4, 25, 4.0)]}
    for (rx, ry, a, b, ang, h) in ledges[which]:
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        u, v = (gx - rx) * c + (y - ry) * s_, -(gx - rx) * s_ + (y - ry) * c
        d = np.hypot(u / a, v / b)
        bump = BED + h * np.clip((1 - d ** 3) * 2.5, 0, 1) + 0.8 * nz.fbm(gx, y, 3, 2) * (d < 1)
        z = np.maximum(z, bump)
    # flat-topped grassy islands
    islands = {"A": [(420, 155, 34, 11, 6, 6.0)], "B": [(1000, 154, 30, 10, -6, 6.0)]}
    for (rx, ry, a, b, ang, h) in islands[which]:
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        u, v = (gx - rx) * c + (y - ry) * s_, -(gx - rx) * s_ + (y - ry) * c
        d = np.hypot(u / a, v / b) + 0.15 * nz.fbm(gx, y, 12, 2)
        bump = BED + h * smoothstep(1.0, 0.7, d) + 0.6 * nz.fbm(gx, y, 5, 2) * (d < 0.85)
        z = np.maximum(z, bump)

    # 6. low lip along the front edge of the river so the water pour can't run out
    lip = (y < 2.5) & (z < WATER + 2.0)
    z = np.where(lip, WATER + 2.0, z)

    # 7. abutment area is built from solids; keep the field low there
    abut = (xd > BACKWALL_X) & (xd <= XA + 1) & (y >= WING_IN0) & (y <= WING_IN1)
    z = np.where(abut, BED, z)
    return z


# ----------------------------------------------------------------------------
# Mesh helpers
# ----------------------------------------------------------------------------
def heightfield(xs, ys, Z, zbot):
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    top = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    tris = [np.column_stack([a.ravel(), b.ravel(), c.ravel()]),
            np.column_stack([a.ravel(), c.ravel(), d.ravel()])]
    per = list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0])
    per = np.array(per)
    n = len(top)
    bot = top[per].copy()
    bot[:, 2] = zbot
    centre = np.array([[xs.mean(), ys.mean(), zbot]])
    verts = np.vstack([top, bot, centre])
    bi = n + np.arange(len(per))
    ci = n + len(per)
    t_i, t_j = per, np.roll(per, -1)
    b_i, b_j = bi, np.roll(bi, -1)
    tris += [np.column_stack([t_i, b_i, b_j]), np.column_stack([t_i, b_j, t_j]),
             np.column_stack([np.full(len(per), ci), b_j, b_i])]
    m = Mesh(vert_properties=verts.astype(np.float32), tri_verts=np.vstack(tris).astype(np.uint32))
    out = Manifold(m)
    assert out.status().name == "NoError", out.status()
    return out


def cube(x0, y0, z0, x1, y1, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def pier_plan(L, W):
    """Pier plan centred at the origin: L along x (track), W along y, with semicircular
    noses at +-y (the river flows along y)."""
    r = L / 2
    return CrossSection.hull(CrossSection.circle(r).translate((0, W / 2 - r)) +
                             CrossSection.circle(r).translate((0, -(W / 2 - r))))


def union(parts):
    return Manifold.batch_boolean(list(parts), OpType.Add) if parts else Manifold()


def to_trimesh(m):
    mm = m.to_mesh()
    return trimesh.Trimesh(vertices=np.array(mm.vert_properties)[:, :3], faces=np.array(mm.tri_verts),
                           process=False)


def export(m, path, rot=None):
    """Export to STL, optionally rotated (degrees xyz), dropped onto the bed at the origin."""
    if rot:
        m = m.rotate(rot)
    m = m.simplify(0.02)                    # merge coplanar triangles (flat ground, faces)
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    m = m.translate((-lo[0], -lo[1], -lo[2]))
    to_trimesh(m).export(path)
    return tuple(round(hi[i] - lo[i], 1) for i in range(3))


# ----------------------------------------------------------------------------
# Printed bridge parts (built in place for module A / track centre y=0 where noted)
# ----------------------------------------------------------------------------
def deck_girder(L=GIRDER_L):
    """Single-track deck plate girder span, built with x along the span, track centre at y=0,
    deck top at z=0.  The girder faces are flush with the deck edge, with closely spaced
    stiffeners like the prototype.  Prints upside down (deck on the bed)."""
    h = DECK_W / 2
    tw, ft, fw = 1.2, 1.2, 3.0
    p = [cube(0, -h, -1.6, L, h, 0)]                                       # deck plate
    for s in (-1, 1):
        yc = s * WEB_HALF
        p.append(cube(0, yc - tw / 2, -GIRDER_D, L, yc + tw / 2, -1.6))     # web
        p.append(cube(0, yc - fw / 2, -GIRDER_D, L, yc + fw / 2, -GIRDER_D + ft))   # bottom flange
        p.append(cube(0, yc - fw / 2, -1.6 - ft, L, yc + fw / 2, -1.6))     # top flange
        # vertical stiffeners on both faces of the web; heavier bearing stiffeners at the ends
        x = 1.5
        while x < L - 1:
            end = x < 10 or x > L - 10
            w = 1.0 if end else 0.6
            for o in (-1, 1):
                p.append(cube(x - w / 2, yc + o * tw / 2 - (0.9 if o < 0 else 0), -GIRDER_D + ft,
                              x + w / 2, yc + o * tw / 2 + (0.9 if o > 0 else 0), -1.6 - ft))
            x += 3.0 if end else STIFF_STEP
        # bearing shoes
        for x0 in (1.5, L - 8.5):
            p.append(cube(x0, yc - 2.0, SEAT_Z, x0 + 7, yc + 2.0, -GIRDER_D))
    # cross frames (diaphragms) between the girders
    nb = max(2, int(round(L / 30)))
    for k in range(nb + 1):
        x = 1.0 + (L - 2.0) * k / nb
        p.append(cube(x - 0.5, -WEB_HALF, -GIRDER_D + 2, x + 0.5, WEB_HALF, -1.6))
    return union(p)


def handrail(L=GIRDER_L):
    """Walkway handrail for the outer edge of a girder span (built in place against the top
    flange edge).  The 3 mm tab glues to the deck edge and top flange.  Prints flat."""
    t = 0.8
    p = [cube(0, 0, -3.0, L, t, 0.0),                      # glue tab on the deck edge
         cube(0, 0, RAIL_H - 0.8, L, t, RAIL_H),          # top rail
         cube(0, 0, RAIL_H * 0.5 - 0.4, L, t, RAIL_H * 0.5 + 0.4)]   # mid rail
    n = int(round(L / 12.0))
    for k in range(n + 1):
        x = 0.4 + (L - 0.8) * k / n
        p.append(cube(x - 0.4, 0, -3.0, x + 0.4, t, RAIL_H))   # posts
    return union(p).translate((0, WEB_HALF + 1.5, 0))     # against the top flange edge


def pier(half=False):
    """Round-nosed, battered concrete pier with closely spaced pour (lift) lines and a thin
    coping, centre at (0, PIER_YC), base in the socket.  The round noses face up- and
    downstream (+-y), the flat faces face along the track.
    half=True keeps only x <= 0 (the joint half, flat face on x = 0)."""
    z0 = BED - SOCKET
    H = SEAT_Z - 1.5 - z0                   # shaft height below the 1.5 mm coping
    Lb, Wb = PIER_T + 2 * BATTER, PIER_W + 2 * BATTER
    sc = (PIER_T / Lb, PIER_W / Wb)
    shaft_cs = pier_plan(Lb, Wb)
    shaft = Manifold.extrude(shaft_cs, H, scale_top=sc).translate((0, 0, z0))
    core = Manifold.extrude(pier_plan(Lb - 0.7, Wb - 0.7), H, scale_top=sc).translate((0, 0, z0))
    slabs = []
    z = BED + 3.0
    while z < SEAT_Z - 4:                   # pour lines all round the pier
        slabs.append(cube(-80, -80, z, 80, 80, z + 0.4))
        z += LIFT
    shaft = shaft - (union(slabs) - core)
    top_cs = pier_plan(PIER_T, PIER_W)
    cap = Manifold.extrude(pier_plan(PIER_T + 1.6, PIER_W + 1.6), 1.5).translate((0, 0, SEAT_Z - 1.5))
    chamfer = Manifold.extrude(top_cs, 0.7, scale_top=((PIER_T + 1.2) / PIER_T, (PIER_W + 1.2) / PIER_W)) \
        .translate((0, 0, SEAT_Z - 2.1))       # ~45 deg under the coping, overlaps it by 0.1
    p = (shaft + cap + chamfer).translate((0, PIER_YC, 0))
    if half:
        p = p ^ cube(-80, -10, -80, 0, 200, 10)
    return p


def pier_footprint(xc, half=False, clr=0.0):
    Lb, Wb = PIER_T + 2 * BATTER, PIER_W + 2 * BATTER
    cs = pier_plan(Lb + 2 * clr, Wb + 2 * clr)
    return Manifold.extrude(cs, SOCKET + 1.5).translate((xc, PIER_YC, BED - SOCKET))


def bowtie(clr=0.0):
    """Bow-tie key outline, long axis along x, centred at the origin."""
    a, b, n = KEY_L / 2 + clr, KEY_W / 2 + clr, KEY_NECK / 2 + clr
    return CrossSection([[(-a, -b), (0, -n), (a, -b), (a, b), (0, n), (-a, b)]])


# ----------------------------------------------------------------------------
# Module
# ----------------------------------------------------------------------------
def build_module(which):
    """Return (module solid in its own local frame x 0..618, list of tile solids)."""
    xs = np.arange(0, MW + 1e-6, GRID)
    ys = np.arange(0, MD + 1e-6, GRID)
    X, Y = np.meshgrid(xs, ys)
    if which == "A":
        xd, gx, mx = X, X, (lambda v: v)
    else:                                   # B: local x 0 = joint end
        xd, gx, mx = MW - X, MW + GAP + X, (lambda v: MW - v)
    Z = terrain(xd, Y, gx, which)
    body = heightfield(xs, ys, Z, ZB)

    def bx(xa, y0, z0, xb, y1, z1):          # box given in design x
        a, b = sorted((mx(xa), mx(xb)))
        return cube(a, y0, z0, b, y1, z1)

    adds = [
        bx(BACKWALL_X, WING_IN0, ZB, XA, WING_IN1, SEAT_Z),                        # bridge seat
        bx(BACKWALL_X - 12, WING_IN0, ZB, BACKWALL_X, WING_IN1, 0.0),              # backwall
        bx(WING_X0, WING_IN0 - WING_T, ZB, XA, WING_IN0, 0.8),                     # wing walls
        bx(WING_X0, WING_IN1, ZB, XA, WING_IN1 + WING_T, 0.8),
    ]
    # board-formed lines on the abutment face
    cuts = []
    z = BED + 4
    while z < SEAT_Z - 2:
        cuts.append(bx(XA - 0.35, WING_IN0 + 0.01, z, XA + 1, WING_IN1 - 0.01, z + 0.4))
        z += 5.5
    # pier sockets
    for xc in PIERS_XD:
        cuts.append(pier_footprint(mx(xc), clr=0.25))
    jx = mx(MW)                              # joint pier centre = module end
    cuts.append(pier_footprint(jx, clr=0.25))
    body = union([body] + adds) - union(cuts)
    body = body ^ cube(0, 0, ZB, MW, MD, 200)

    # bow-tie key pockets on the underside across every tile seam
    pockets = []
    for xsx in TILE_X[1:-1]:
        for j in range(len(TILE_Y) - 1):
            y0, y1 = TILE_Y[j], TILE_Y[j + 1]
            for f in (0.27, 0.73):
                pockets.append(Manifold.extrude(bowtie(KEY_CLR), KEY_D + 0.2)
                               .translate((xsx, y0 + f * (y1 - y0), ZB - 0.1)))
    for ysx in TILE_Y[1:-1]:
        for i in range(len(TILE_X) - 1):
            xc = (TILE_X[i] + TILE_X[i + 1]) / 2
            for f in (-0.25, 0.25):
                pockets.append(Manifold.extrude(bowtie(KEY_CLR), KEY_D + 0.2).rotate((0, 0, 90))
                               .translate((xc + f * (TILE_X[i + 1] - TILE_X[i]), ysx, ZB - 0.1)))
    body = body - union(pockets)

    tiles = []
    for j in range(len(TILE_Y) - 1):
        for i in range(len(TILE_X) - 1):
            t = body ^ cube(TILE_X[i], TILE_Y[j], ZB - 1, TILE_X[i + 1], TILE_Y[j + 1], 300)
            row = "front" if j == 0 else "back"
            # name by design position: 1 = outer (transition) end, 3 = joint end
            col = (i + 1) if which == "A" else (3 - i)
            tiles.append(("%s_tile_%s_%d" % (which, row, col), t, (TILE_X[i], TILE_Y[j])))
    return body, tiles


def bridge_in_module(which, girder, rail, pier_full, pier_half):
    """Bridge parts placed in the module's local frame (for renders)."""
    mx = (lambda v: v) if which == "A" else (lambda v: MW - v)
    parts = []
    for x0 in SPANS_XD:
        for yc in TRACK_Y:
            g = girder.translate((x0, yc, 0))
            if which == "B":
                g = g.mirror((1, 0, 0)).translate((MW, 0, 0))
            parts.append(("girder", g))
            if yc == TRACK_Y[1]:                      # walkway handrail on the back side
                r = rail.translate((x0, yc, 0))
                if which == "B":
                    r = r.mirror((1, 0, 0)).translate((MW, 0, 0))
                parts.append(("girder", r))
    for xc in PIERS_XD:
        parts.append(("pier", pier_full.translate((mx(xc), 0, 0))))
    h = pier_half.translate((MW, 0, 0)) if which == "A" else pier_half.mirror((1, 0, 0))
    parts.append(("pier", h))
    return parts


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main(render=True):
    stl = os.path.join(OUT, "stl")
    os.makedirs(stl, exist_ok=True)
    for f in os.listdir(stl):
        if f.endswith(".stl"):
            os.remove(os.path.join(stl, f))
    rows = []

    def ex(m, name, qty, rot=None, note=""):
        dims = export(m, os.path.join(stl, name + ".stl"), rot)
        rows.append((name, qty) + dims + (note,))
        print("  %-34s x%-3d %6.1f x %6.1f x %6.1f" % ((name, qty) + dims))

    girder = deck_girder()
    rail = handrail()
    pier_full = pier()
    pier_half = pier(half=True)
    key = Manifold.extrude(bowtie(), KEY_D * 2 - 0.4)

    scene = {}
    for which in ("A", "B"):
        print("Module", which)
        body, tiles = build_module(which)
        scene[which] = (body, bridge_in_module(which, girder, rail, pier_full, pier_half))
        for name, t, _ in tiles:
            ex(t, name, 1, note="print upright, lightning/gyroid infill")
    print("Bridge parts")
    ex(girder, "deck_girder_span_print_upside_down", 12, rot=(180, 0, 0), note="6 per module")
    ex(pier_full, "pier_full", 4, note="2 per module, print upright")
    ex(pier_half, "pier_joint_half", 2, note="1 per module (B: same part turned 180 deg)")
    ex(rail, "handrail_print_flat", 6, rot=(90, 0, 0), note="3 per module, glue on the back edge of the back-track spans")
    ex(key, "bowtie_key", 28, note="14 per module, glue into the underside pockets")

    with open(os.path.join(OUT, "river_bridge_parts.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["part", "qty_for_pair", "x_mm", "y_mm", "z_mm", "notes"])
        w.writerows(rows)

    # assembled scene meshes for the renders
    asm = os.path.join(OUT, "_assembly")
    os.makedirs(asm, exist_ok=True)
    for which, (body, parts) in scene.items():
        ox = 0.0 if which == "A" else MW + GAP
        to_trimesh(body.translate((ox, 0, 0))).export(os.path.join(asm, "terrain_%s.stl" % which))
        g = union([m for k, m in parts if k == "girder"]).translate((ox, 0, 0))
        p = union([m for k, m in parts if k == "pier"]).translate((ox, 0, 0))
        to_trimesh(g).export(os.path.join(asm, "girders_%s.stl" % which))
        to_trimesh(p).export(os.path.join(asm, "piers_%s.stl" % which))
    if render:
        import river_bridge_render
        river_bridge_render.render(OUT, asm)


if __name__ == "__main__":
    main(render="--no-render" not in sys.argv)
