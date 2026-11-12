"""
Road-underpass T-TRAK double module: a depressed (lowered) scenery deck with the track
at the standard T-TRAK height, crossing a country road on a fill embankment through a
cast-concrete arch underpass (headwalls, arch ring and flared wingwalls).

     front view                          section through the road (looking along the track)
  ___________          ___________            ___ track at module top (TOP) ___
             \\  ____  /                       |  spine plate  |
              \\ |    | /    <- arch portal    | front | back  |
               \\|____|/                  slope| wall  | wall  | slope
                  road  (deck = TOP - 40)  ____|_______|_______|_______ road / depressed deck

Everything is generated from the numbers below:
  * laser-cut 5 mm ply box (same 618 x 330 footprint, end joints, finger-joint pitch and colour
    convention as the "Double 618 x 330 T Track Module" template / portal_laser.py)
  * one printable concrete arch culvert (barrel + both headwalls + four wingwalls in one piece)
  * a 3D assembly check (no overlapping parts, every notch filled) and preview renders

Run:  python underpass_module.py           (needs: numpy, shapely, trimesh, manifold3d, pillow)
      python underpass_module.py --no-render
Output: ttrak_output/underpass/
"""

import csv
import math
import os
import sys

import numpy as np
import shapely.geometry as sg
import trimesh
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portal_laser as pl                                       # noqa: E402
from portal_laser import Panel, edge, rect, circle, stadium   # noqa: E402
from portal_nest import MaxRects, xf, d_of                    # noqa: E402

# ----------------------------------------------------------------------------
# PARAMETERS (mm). x along the track (0..618), y front -> back (0..330), z above the table.
# ----------------------------------------------------------------------------
T = pl.T                    # 5 mm ply
L, D = pl.L, pl.D           # 618 x 330
TOP = 70.09                 # module top (track base). 63.5 is also generated.
DROP = 40.0                 # depressed deck (road surface) below the module top
ROAD_X = L / 2              # road centreline (crosses the module front to back)
ROAD_W = 25.0               # dirt road, ~4 m

# valley in the scenery: flat floor X_B..X_C, foam slopes up to the module top at X_A / X_D
X_A, X_B, X_C, X_D = 179.0, 249.0, 369.0, 439.0

# track spine (embankment top) - Kato Unitrack roadbed is 38..96, track centres 50.5 / 83.5
SP0, SP1 = 33.0, 101.0      # spine plate front / back edge; embankment walls sit under these edges
TRACK_Y = (50.5, 83.5)

# arch underpass (relative to the road surface, x relative to ROAD_X)
ARCH_HALF = 20.0            # 40 mm clear opening (6.4 m)
SPRING = 8.0                # straight wall height before the arch starts; crown = 28 mm (4.5 m)
BARREL_T = 2.5
NOTCH_CLR = 0.25            # clearance in the ply walls around the barrel
HEAD_HALF = 35.0            # headwall half-width
HEAD_T = 4.0
WING_LEN, WING_T, WING_ANGLE = 26.0, 3.0, 30.0
COPING = 1.4

# finger joints (template pitch where the template has them)
TOPF_L = [(45.0, 85.0), (115.0, 155.0)]                       # apron -> top plate (left section)
TOPF_R = [(L - b, L - a) for a, b in reversed(TOPF_L)]
DECK_EDGE_TABS = [(255.0, 285.0), (333.0, 363.0)]             # deck -> aprons (valley floor)
DECK_X_TABS = [(45.0, 85.0), (130.0, 170.0), (220.0, 260.0)]  # deck -> cross plates
CROSS_TOP_TABS = [(150.0, 200.0), (250.0, 300.0)]
CROSS_BOTTOM_TABS = [(40.0, 80.0), (140.0, 180.0), (240.0, 280.0)]
WALL_TOP_TABS = [(195.0, 235.0), (383.0, 423.0)]
WALL_BOT_TABS = [(200.0, 240.0), (378.0, 418.0)]
WALL_END_Z = (30.0, 15.0)   # wall end tab: TOP-30 .. TOP-15
SLOT = 0.05

PART_NAMES = {}


def floor_z():
    return TOP - DROP


def set_top(top):
    global TOP
    TOP = top
    pl.TOP = top


# ----------------------------------------------------------------------------
# Ply parts
# ----------------------------------------------------------------------------
def slot_rect(x0, y0, x1, y1):
    return rect(x0 - SLOT, y0 - SLOT, x1 + SLOT, y1 + SLOT)


def notches(tabs):
    return [(a, b, -T) for a, b in tabs]


def tabs_(tabs):
    return [(a, b, T) for a, b in tabs]


def base_plate():
    p = []
    edge(p, "u", 0, 0, L, notches(pl.LONG_TABS), -1)
    edge(p, "v", L, 0, D, notches(pl.END_TABS), +1)
    edge(p, "u", D, L, 0, notches(pl.LONG_TABS), +1)
    edge(p, "v", 0, D, 0, notches(pl.END_TABS), -1)
    holes = [circle(x, y, pl.FOOT_D) for x, y in pl.FEET]
    for x0 in (X_A - T, X_D):
        holes += [slot_rect(x0, a, x0 + T, b) for a, b in CROSS_BOTTOM_TABS]
    eng = [rect(X_B, 0, X_C, D), rect(ROAD_X - ROAD_W / 2, 0, ROAD_X + ROAD_W / 2, D)]
    return Panel("underpass_base_plate", p, "XY", 0.0, holes, eng,
                 [(L / 2, 200, "UNDERPASS BASE PLATE", 8), (L / 2, 150, "ROAD ABOVE - FRONT EDGE THIS SIDE", 5)])


def top_plate():
    """H-shaped: full depth at both ends, joined by the track spine over the valley."""
    p = []
    edge(p, "u", 0, 0, X_A, notches(TOPF_L), -1)
    p += [(X_A, 0), (X_A, SP0)]
    edge(p, "u", SP0, X_A, X_D, notches(WALL_TOP_TABS), -1)
    p += [(X_D, SP0), (X_D, 0)]
    edge(p, "u", 0, X_D, L, notches(TOPF_R), -1)
    edge(p, "v", L, 0, D, notches(pl.END_TABS), +1)
    edge(p, "u", D, L, X_D, notches(TOPF_R), +1)
    edge(p, "v", X_D, D, SP1, notches(CROSS_TOP_TABS), -1)
    edge(p, "u", SP1, X_D, X_A, notches(WALL_TOP_TABS), +1)
    edge(p, "v", X_A, SP1, D, notches(CROSS_TOP_TABS), +1)
    edge(p, "u", D, X_A, 0, notches(TOPF_L), +1)
    edge(p, "v", 0, D, 0, notches(pl.END_TABS), -1)
    holes = [circle(x, y, 2.8) for x in (15.0, 62.0, L - 62.0, L - 15.0) for y in TRACK_Y]
    eng = [[(0, y), (L, y)] for y in TRACK_Y]
    eng += [[(0, 38.0), (L, 38.0)], [(0, 96.0), (L, 96.0)]]     # Unitrack roadbed edges
    return Panel("underpass_top_plate", p, "XY", TOP - T, holes, eng,
                 [(X_A / 2, 200, "TOP L", 6), (L - X_A / 2 + T, 200, "TOP R", 6), (L / 2, 67, "TRACK SPINE", 5)])


def apron_profile():
    """Top edge of the front/back apron from u=L back to u=0: the valley the road runs in."""
    F = floor_z()
    pts = [(L, TOP - T)]
    for a, b in sorted(TOPF_R, reverse=True):
        pts += [(b, TOP - T), (b, TOP), (a, TOP), (a, TOP - T)]
    pts += [(X_D, TOP - T), (X_D, TOP), (X_C, F)]
    for a, b in sorted(DECK_EDGE_TABS, reverse=True):
        pts += [(b, F), (b, F - T), (a, F - T), (a, F)]
    pts += [(X_B, F), (X_A, TOP), (X_A, TOP - T)]
    for a, b in sorted(TOPF_L, reverse=True):
        pts += [(b, TOP - T), (b, TOP), (a, TOP), (a, TOP - T)]
    pts.append((0, TOP - T))
    return pts


def aprons():
    slots = [slot_rect(x0, pl.SIDE_TAB[0], x0 + T, pl.SIDE_TAB[1]) for x0 in (X_A - T, X_D)]
    return [pl.apron("underpass_front_apron", 0.0, apron_profile(), pl.SIDE_TAB, pl.SIDE_TAB, slots),
            pl.apron("underpass_back_apron", D - T, apron_profile(), pl.SIDE_TAB, pl.SIDE_TAB, slots)]


def deck_plate():
    F = floor_z()
    p = []
    edge(p, "u", T, X_A, X_D, tabs_(DECK_EDGE_TABS), -1)
    edge(p, "v", X_D, T, D - T, tabs_(DECK_X_TABS), +1)
    edge(p, "u", D - T, X_D, X_A, tabs_(DECK_EDGE_TABS), +1)
    edge(p, "v", X_A, D - T, T, tabs_(DECK_X_TABS), -1)
    holes = []
    for y0 in (SP0, SP1 - T):
        holes += [slot_rect(a, y0, b, y0 + T) for a, b in WALL_BOT_TABS]
    eng = [rect(ROAD_X - ROAD_W / 2, T, ROAD_X + ROAD_W / 2, D - T),
           arch_footprint_engrave()]
    return Panel("depressed_deck", p, "XY", F - T, holes, eng,
                 [(ROAD_X, 200, "DEPRESSED DECK", 6), (ROAD_X, 180, "ROAD", 5)])


def arch_footprint_engrave():
    """Outline of the printed culvert on the deck (glue position)."""
    y0, y1 = SP0 - HEAD_T, SP1 + HEAD_T
    h = HEAD_HALF
    return rect(ROAD_X - h, y0, ROAD_X + h, y1)


def cross_plate(name, x_off):
    F = floor_z()
    p = []
    edge(p, "u", T, T, D - T, tabs_(CROSS_BOTTOM_TABS), -1)
    p += [(D - T, pl.SIDE_TAB[0]), (D, pl.SIDE_TAB[0]), (D, pl.SIDE_TAB[1]), (D - T, pl.SIDE_TAB[1])]
    edge(p, "u", TOP - T, D - T, T, tabs_(CROSS_TOP_TABS), +1)
    p += [(T, pl.SIDE_TAB[1]), (0, pl.SIDE_TAB[1]), (0, pl.SIDE_TAB[0]), (T, pl.SIDE_TAB[0])]
    holes = [slot_rect(a, F - T, b, F) for a, b in DECK_X_TABS]
    z0, z1 = TOP - WALL_END_Z[0], TOP - WALL_END_Z[1]
    holes += [slot_rect(y, z0, y + T, z1) for y in (SP0, SP1 - T)]
    holes.append(stadium(200, 290, 7, 15))                      # wiring
    return Panel(name, p, "YZ", x_off, holes,
                 labels=[(220, TOP - 14, name.upper().replace("_", " ") + " - FOAM SLOPE ON VALLEY SIDE", 3.5)])


def emb_wall(name, y_off):
    """Embankment core wall under a spine edge, with the arch notch open at the bottom."""
    F = floor_z()
    nh = ARCH_HALF + BARREL_T + NOTCH_CLR
    xl, xr = ROAD_X - nh, ROAD_X + nh
    z0, z1 = TOP - WALL_END_Z[0], TOP - WALL_END_Z[1]
    p = []
    edge(p, "u", F, X_A, xl, [(a, b, T) for a, b in WALL_BOT_TABS if b < xl], -1)
    p += [(xl, F), (xl, F + SPRING)]
    for i in range(1, 48):
        a = math.pi - math.pi * i / 48
        p.append((ROAD_X + nh * math.cos(a), F + SPRING + nh * math.sin(a)))
    p += [(xr, F + SPRING), (xr, F)]
    edge(p, "u", F, xr, X_D, [(a, b, T) for a, b in WALL_BOT_TABS if a > xr], -1)
    p += [(X_D, z0), (X_D + T, z0), (X_D + T, z1), (X_D, z1)]
    edge(p, "u", TOP - T, X_D, X_A, tabs_(WALL_TOP_TABS), +1)
    p += [(X_A, z1), (X_A - T, z1), (X_A - T, z0), (X_A, z0)]
    return Panel(name, p, "XZ", y_off, labels=[(X_A + 50, F + 12, name.upper().replace("_", " "), 4)])


def module_panels():
    return ([base_plate(), top_plate()] + aprons() +
            [pl.end_standard("end_plate_L", 0.0), pl.end_standard("end_plate_R", L - T),
             deck_plate(),
             cross_plate("cross_plate_L", X_A - T), cross_plate("cross_plate_R", X_D),
             emb_wall("embankment_wall_front", SP0), emb_wall("embankment_wall_back", SP1 - T)])


# ----------------------------------------------------------------------------
# 3D
# ----------------------------------------------------------------------------
def extrude(poly2d, h):
    return trimesh.creation.extrude_polygon(poly2d, h)


def panel_mesh(pnl):
    poly = sg.Polygon(pnl.outline, [h for h in pnl.holes])
    if not poly.is_valid:
        raise ValueError("invalid outline: " + pnl.name)
    m = extrude(poly, T)
    M = np.eye(4)
    if pnl.plane == "XY":
        M[2, 3] = pnl.off
    elif pnl.plane == "XZ":           # (u, v, w) -> (u, off + w, v)
        M[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, 1, 0]]
        M[1, 3] = pnl.off
    else:                             # (u, v, w) -> (off + w, u, v)
        M[:3, :3] = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
        M[0, 3] = pnl.off
    m.apply_transform(M)
    return m


def arch_poly(half, spring, zbot, n=64):
    pts = [(-half, zbot), (half, zbot), (half, spring)]
    pts += [(half * math.cos(math.pi * i / n), spring + half * math.sin(math.pi * i / n)) for i in range(1, n)]
    pts.append((-half, spring))
    return sg.Polygon(pts)


def xz_extrude(poly, y0, y1):
    """Extrude a polygon drawn in (x, z) along +y from y0 to y1."""
    m = extrude(poly, y1 - y0)
    M = np.eye(4)
    M[:3, :3] = [[1, 0, 0], [0, 0, 1], [0, 1, 0]]
    M[1, 3] = y0
    m.apply_transform(M)
    return m


def union(meshes):
    return trimesh.boolean.union(meshes, engine="manifold")


def culvert():
    """Arch underpass in culvert coords: x about the road centre, y absolute, z above the road."""
    H = DROP
    y_f, y_b = SP0 - HEAD_T, SP1 + HEAD_T                      # 29 .. 105
    inner = arch_poly(ARCH_HALF, SPRING, -1.0)
    outer = arch_poly(ARCH_HALF + BARREL_T, SPRING, 0.0)
    parts = [xz_extrude(outer.difference(inner), y_f, y_b)]
    head = sg.box(-HEAD_HALF, 0, HEAD_HALF, H - COPING).difference(inner)
    ring = arch_poly(ARCH_HALF + 3.2, SPRING, 0.0).difference(inner)
    cop = sg.box(-HEAD_HALF - 1.2, H - COPING, HEAD_HALF + 1.2, H)
    panel = sg.box(-5.5, SPRING + ARCH_HALF + 4.2, 5.5, SPRING + ARCH_HALF + 8.2)    # date stone
    front = [xz_extrude(head, y_f, SP0), xz_extrude(ring, y_f - 0.6, y_f + 0.01),
             xz_extrude(cop, y_f - 1.2, SP0), xz_extrude(panel, y_f - 0.5, y_f + 0.01)]
    # wingwall (front-left): local (s along the wall, z), thickness toward the road
    wing2d = sg.Polygon([(-3.0, 0), (WING_LEN, 0), (WING_LEN, 7.0), (0, H - COPING), (-3.0, H - COPING)])
    w = extrude(wing2d, WING_T)                                 # (s, z, t)
    a = math.radians(WING_ANGLE)
    d = np.array([-math.sin(a), -math.cos(a), 0.0])             # forward and outward
    n = np.array([math.cos(a), -math.sin(a), 0.0])              # toward the road side
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = d, [0, 0, 1], n
    M[:3, 3] = [-HEAD_HALF, y_f, 0]
    w.apply_transform(M)
    wings = [w]
    mx = np.diag([-1.0, 1, 1, 1])
    wings.append(w.copy().apply_transform(mx))
    front += wings
    front_m = union(front)
    yc = (y_f + y_b) / 2
    my = np.eye(4)
    my[1, 1], my[1, 3] = -1, 2 * yc
    back_m = front_m.copy().apply_transform(my)
    return union(parts + [front_m, back_m])


def place_culvert(m):
    M = np.eye(4)
    M[0, 3], M[2, 3] = ROAD_X, floor_z()
    return m.copy().apply_transform(M)


# ----------------------------------------------------------------------------
# Assembly checks
# ----------------------------------------------------------------------------
def section_area(m, z):
    """Horizontal cross-section of a closed mesh as a shapely (multi)polygon."""
    from shapely.ops import polygonize
    segs = trimesh.intersections.mesh_plane(m, [0, 0, 1], [0, 0, z])
    faces = list(polygonize([sg.LineString(np.round(s[:, :2], 6)) for s in segs]))
    region = sg.Polygon()
    for f in faces:                      # XOR the faces so holes come out right
        region = region.symmetric_difference(f)
    return region


def check_assembly(panels, culv):
    meshes = [(p.name, panel_mesh(p)) for p in panels] + [("arch_culvert", culv)]
    report = []
    for name, m in meshes:
        if not m.is_watertight:
            report.append("NOT WATERTIGHT: " + name)
    worst = 0.0
    for i in range(len(meshes)):
        for j in range(i + 1, len(meshes)):
            a, b = meshes[i][1], meshes[j][1]
            if np.any(a.bounds[1] < b.bounds[0]) or np.any(b.bounds[1] < a.bounds[0]):
                continue
            v = trimesh.boolean.intersection([a, b], engine="manifold").volume
            worst = max(worst, v)
            if v > 0.5:
                report.append("OVERLAP %.2f mm3: %s / %s" % (v, meshes[i][0], meshes[j][0]))
    allm = trimesh.util.concatenate([m for _, m in meshes])
    ext = allm.bounds[1] - allm.bounds[0]
    report.append("assembly extents %.2f x %.2f x %.2f mm (worst pair overlap %.3f mm3)" % (tuple(ext) + (worst,)))
    # top layer must be solid ply wherever the top plate envelope is (every notch filled by a tab)
    env = sg.box(0, 0, L, D).difference(sg.box(X_A, 0, X_D, SP0)).difference(sg.box(X_A, SP1, X_D, D))
    holes_top = [sg.Polygon(h) for h in top_plate().holes]
    for z, label, target in ((TOP - T / 2, "top layer", env), (T / 2, "base layer", sg.box(0, 0, L, D))):
        polys = []
        for nm, m in meshes:
            if nm != "arch_culvert" and m.bounds[0][2] < z < m.bounds[1][2]:
                polys.append(section_area(m, z))
        u = unary_union(polys)
        expect = target
        if label == "top layer":
            expect = target.difference(unary_union(holes_top))
        else:
            expect = target.difference(unary_union([sg.Polygon(h) for h in base_plate().holes]))
        gap = expect.difference(u).area
        extra = u.difference(target).area
        report.append("%s: unfilled %.2f mm2, ply outside the plate envelope %.2f mm2%s"
                      % (label, gap, extra, " (apron tips where the valley slopes start)" if extra else ""))
    return report


# ----------------------------------------------------------------------------
# SVG output
# ----------------------------------------------------------------------------
def write_nested(path, panels, label):
    SHEET_W, SHEET_H, MARGIN, GAP = 3000.0, 600.0, 6.0, 4.0
    order = sorted(panels, key=lambda p: -(p.bbox()[2] - p.bbox()[0]) * (p.bbox()[3] - p.bbox()[1]))
    mr = MaxRects(SHEET_W - 2 * MARGIN + GAP, SHEET_H - 2 * MARGIN + GAP)
    placed = []
    for p in order:
        u0, v0, u1, v1 = p.bbox()
        r = mr.insert(u1 - u0 + GAP, v1 - v0 + GAP)
        if r is None:
            raise ValueError("does not fit: " + p.name)
        placed.append((p,) + r)
    cut, inner, eng = [], [], []
    used_x = 0.0
    for p, x, y, rot in placed:
        f = xf(p, x, y, rot)
        pts = [f(q) for q in p.outline]
        used_x = max(used_x, max(q[0] for q in pts))
        cut.append('<path id="%s" d="%s" stroke="%s" stroke-width="0.1" fill="none"/>'
                   % (p.name, d_of(pts), pl.PURPLE))
        for h in p.holes:
            inner.append('<path d="%s" stroke="%s" stroke-width="0.1" fill="none"/>'
                         % (d_of([f(q) for q in h]), pl.GREEN))
        for e in p.engrave:
            eng.append('<path d="%s" stroke="%s" stroke-width="0.1" fill="none"/>'
                       % (d_of([f(q) for q in e], close=len(e) > 2), pl.RED))
        u0, v0, u1, v1 = p.bbox()
        cx, cy = f(((u0 + u1) / 2, (v0 + v1) / 2 - (12 if p.plane == "XY" else 0)))
        rot_attr = ' transform="rotate(90 %.2f %.2f)"' % (cx, cy) if rot else ""
        eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="4" text-anchor="middle" '
                   'fill="%s"%s>U %s</text>' % (cx, cy, pl.RED, rot_attr, p.name.replace("_", " ")))
    note = ("Road underpass T-TRAK double module - %s - 600 x 3000 mm sheet (uses the first %.0f mm) - 5mm ply. "
            "Purple: cut, kerf OUT. Green: inside cut, kerf IN. Red: engrave or delete." % (label, used_x + 10))
    eng.append('<text x="%.2f" y="%.2f" font-family="Arial, sans-serif" font-size="4" fill="%s">%s</text>'
               % (MARGIN, SHEET_H - 1.5, pl.RED, note))
    svg = ['<?xml version="1.0" encoding="utf-8"?>',
           '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">'
           % (SHEET_W, SHEET_H, SHEET_W, SHEET_H),
           '<g id="Cut_Outside_Purple">' + "".join(cut) + "</g>",
           '<g id="Cut_Inside_Green">' + "".join(inner) + "</g>",
           '<g id="Engrave_Red">' + "".join(eng) + "</g>", "</svg>"]
    with open(path, "w") as fh:
        fh.write("\n".join(svg))


def svg_preview(svg_path, png_path, width_px):
    """Rasterise an SVG with the pre-installed Chromium (optional)."""
    import re
    import subprocess
    import tempfile
    with open(svg_path) as fh:
        svg = fh.read()
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = float(m.group(1)), float(m.group(2))
    hp = int(width_px * h / w)
    svg = re.sub(r'width="[\d.]+mm" height="[\d.]+mm"', 'width="%d" height="%d"' % (width_px, hp), svg, count=1)
    svg = svg.replace('stroke-width="0.1"', 'stroke-width="0.8"')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write('<html><body style="margin:0;background:#fff">%s</body></html>' % svg)
        html = fh.name
    js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
          "const p=await b.newPage({viewport:{width:%d,height:%d}});await p.goto('file://%s');"
          "await p.screenshot({path:'%s'});await b.close();})();" % (width_px, hp, html, png_path))
    try:
        subprocess.run(["node", "-e", js], check=True, timeout=120, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        os.unlink(html)


# ----------------------------------------------------------------------------
# Software renderer (z-buffer, flat shading) - no Blender needed
# ----------------------------------------------------------------------------
def render(items, path, cam, target, fov=34.0, size=(1600, 1000), ss=2, sky=True):
    W, H = size[0] * ss, size[1] * ss
    tris, cols, ids = [], [], []
    for gid, (m, c) in enumerate(items):
        tv = m.vertices[m.faces] if isinstance(m, trimesh.Trimesh) else m[0]
        tris.append(tv)
        cc = np.asarray(c, float) if isinstance(m, trimesh.Trimesh) else m[1]
        cols.append(np.broadcast_to(cc, (len(tv), 3)))
        ids.append(np.full(len(tv), gid))
    tv = np.concatenate(tris).astype(float)
    gids = np.concatenate(ids)
    tc_ = np.concatenate(cols).astype(float)
    cam, target = np.array(cam, float), np.array(target, float)
    f = target - cam
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    rel = tv - cam
    X, Y, Z = rel @ r, rel @ u, rel @ f
    keep = (Z > 5).all(axis=1)
    X, Y, Z, tv, tc_, gids = X[keep], Y[keep], Z[keep], tv[keep], tc_[keep], gids[keep]
    fp = (W / 2) / math.tan(math.radians(fov) / 2)
    sx = W / 2 + fp * X / Z
    sy = H / 2 - fp * Y / Z
    nrm = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
    nl = np.linalg.norm(nrm, axis=1)
    ok = nl > 1e-12
    nrm[ok] /= nl[ok, None]
    view = tv.mean(axis=1) - cam
    flip = (nrm * view).sum(1) > 0
    nrm[flip] *= -1
    light = np.array([-0.45, -0.6, 0.75])
    light /= np.linalg.norm(light)
    fill = np.array([0.6, 0.3, 0.4])
    fill /= np.linalg.norm(fill)
    inten = 0.38 + 0.62 * np.clip(nrm @ light, 0, 1) + 0.12 * np.clip(nrm @ fill, 0, 1)
    shade = np.clip(tc_ * inten[:, None], 0, 1)
    img = np.zeros((H, W, 3))
    if sky:
        g = np.linspace(0, 1, H)[:, None]
        img[:] = (np.array([0.55, 0.70, 0.88]) * (1 - g) + np.array([0.86, 0.91, 0.96]) * g)[:, None, :]
    else:
        img[:] = 0.96
    zb = np.zeros((H, W))                      # stores 1/z (bigger = closer)
    idb = np.full((H, W), -1)
    iz = 1.0 / Z
    for k in range(len(sx)):
        x0, x1 = int(max(0, math.floor(sx[k].min()))), int(min(W - 1, math.ceil(sx[k].max())))
        y0, y1 = int(max(0, math.floor(sy[k].min()))), int(min(H - 1, math.ceil(sy[k].max())))
        if x1 < x0 or y1 < y0:
            continue
        x_a, x_b, x_c = sx[k]
        y_a, y_b, y_c = sy[k]
        den = (y_b - y_c) * (x_a - x_c) + (x_c - x_b) * (y_a - y_c)
        if abs(den) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((y_b - y_c) * (gx - x_c) + (x_c - x_b) * (gy - y_c)) / den
        w1 = ((y_c - y_a) * (gx - x_c) + (x_a - x_c) * (gy - y_c)) / den
        w2 = 1 - w0 - w1
        ins = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not ins.any():
            continue
        z = w0 * iz[k, 0] + w1 * iz[k, 1] + w2 * iz[k, 2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m = ins & (z > sub)
        sub[m] = z[m]
        img[y0:y1 + 1, x0:x1 + 1][m] = shade[k]
        idb[y0:y1 + 1, x0:x1 + 1][m] = gids[k]
    # outlines: object boundaries and depth steps
    dep = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-12), 1e9)
    e = np.zeros((H, W), bool)
    for ax in (0, 1):
        a_id, b_id = idb, np.roll(idb, 1, axis=ax)
        a_d, b_d = dep, np.roll(dep, 1, axis=ax)
        e |= (a_id != b_id) | (np.abs(a_d - b_d) > 0.012 * np.minimum(a_d, b_d))
    e[0, :] = e[:, 0] = False
    img[e] *= 0.35
    from PIL import Image
    im = Image.fromarray((img * 255).astype(np.uint8))
    im = im.resize(size, Image.LANCZOS)
    im.save(path)


def terrain_mesh(step=1.25):
    """Finished-scenery proxy (foam + ground cover) for the renders."""
    F = floor_z()
    xs = np.arange(0, L + 0.01, step)
    ys = np.arange(0, D + 0.01, step)
    gx, gy = np.meshgrid(xs, ys)
    valley = np.interp(gx, [0, X_A, X_B, X_C, X_D, L], [TOP, TOP, F, F, TOP, TOP])
    emb = np.where(gy < SP0, TOP - 1.35 * (SP0 - gy), np.where(gy > SP1, TOP - 1.35 * (gy - SP1), TOP))
    h = np.maximum(valley, emb)
    yf, yb = SP0 - HEAD_T, SP1 + HEAD_T
    tan = math.tan(math.radians(WING_ANGLE))
    reach = WING_LEN * math.cos(math.radians(WING_ANGLE))
    carve = ((gy < yf) & (gy > yf - reach) & (np.abs(gx - ROAD_X) < HEAD_HALF - 1 + (yf - gy) * tan)) | \
            ((gy > yb) & (gy < yb + reach) & (np.abs(gx - ROAD_X) < HEAD_HALF - 1 + (gy - yb) * tan))
    h = np.where(carve, F, h) + 0.15
    ny, nx = h.shape
    V = np.stack([gx, gy, h], -1).reshape(-1, 3)
    idx = np.arange(nx * ny).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    faces = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    tv = V[faces]
    cen = tv.mean(1)
    grass = np.array([0.40, 0.58, 0.24])
    ballast = np.array([0.50, 0.47, 0.44])
    dirt = np.array([0.72, 0.58, 0.40])
    field = np.array([0.66, 0.52, 0.34])
    col = np.tile(grass, (len(tv), 1))
    cx, cy, cz = cen[:, 0], cen[:, 1], cen[:, 2]
    embz = np.where(cy < SP0, TOP - 1.35 * (SP0 - cy), np.where(cy > SP1, TOP - 1.35 * (cy - SP1), TOP))
    valz = np.interp(cx, [0, X_A, X_B, X_C, X_D, L], [TOP, TOP, F, F, TOP, TOP])
    on_emb = (embz > valz + 0.5) & (cz > F + 1.0)
    col[on_emb] = ballast
    col[(cy > 150) & (cz > TOP - 0.5) & (np.abs(cx - ROAD_X) > 200)] = field
    col[(np.abs(cx - ROAD_X) < ROAD_W / 2) & (cz < F + 0.5)] = dirt
    return tv, col


def track_meshes():
    items = []
    for yc in TRACK_Y:
        rb = trimesh.creation.box([L, 25.0, 5.6])
        rb.apply_translation([L / 2, yc, TOP + 2.8])
        items.append((rb, (0.42, 0.41, 0.40)))
        ties = []
        x = 2.0
        while x < L:
            t = trimesh.creation.box([1.6, 16.0, 0.8])
            t.apply_translation([x, yc, TOP + 6.0])
            ties.append(t)
            x += 4.3
        items.append((trimesh.util.concatenate(ties), (0.26, 0.20, 0.16)))
        for s in (-4.5, 4.5):
            rl = trimesh.creation.box([L, 0.7, 1.9])
            rl.apply_translation([L / 2, yc + s, TOP + 7.35])
            items.append((rl, (0.30, 0.27, 0.25)))
    return items


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def out_dir(*sub):
    d = os.path.join(HERE, "ttrak_output", "underpass", *sub)
    os.makedirs(d, exist_ok=True)
    return d


def run(do_render=True):
    log = []
    culv_local = culvert()
    stl_dir = out_dir("stl")
    # print upright: the road-level face on the bed
    culv_local.export(os.path.join(stl_dir, "arch_underpass_culvert_print_upright.stl"))
    ext = culv_local.bounds[1] - culv_local.bounds[0]
    with open(os.path.join(out_dir(), "underpass_parts.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["part", "qty", "x_mm", "y_mm", "z_mm", "material", "notes"])
        w.writerow(["arch_underpass_culvert_print_upright", 1] + ["%.1f" % e for e in ext] +
                   ["PLA/PETG/resin", "barrel + 2 headwalls + 4 wingwalls, one piece; print upright"])
        set_top(70.09)
        for p in module_panels():
            u0, v0, u1, v1 = p.bbox()
            w.writerow([p.name, 1, "%.1f" % (u1 - u0), "%.1f" % (v1 - v0), "%.1f" % T, "5 mm ply",
                        "laser (70.09 mm height version)"])
        w.writerow(["Kato Unitrack 248 mm straight (20-000)", 4, "", "", "", "", "2 per line"])
        w.writerow(["Kato Unitrack 124 mm straight (20-010)", 2, "", "", "", "", "1 per line"])
        w.writerow(["T-nut + M6 leveling bolt", 4, "", "", "", "", "9 mm holes in the base plate"])

    for label, top in (("70mm_template", 70.09), ("63.5mm_2.5in", 63.5)):
        set_top(top)
        panels = module_panels()
        culv = place_culvert(culv_local)
        log.append("[%s]" % label)
        log += ["  " + s for s in check_assembly(panels, culv)]
        d = out_dir("laser", label)
        title = "Road underpass T-TRAK module (depressed deck), module height %.2f mm" % top
        f1 = os.path.join(d, "underpass_module_618x330_%s.svg" % label)
        pl.write_svg(f1, panels, title, "cut 1 set")
        f2 = os.path.join(d, "underpass_module_sheet_600x3000_%s.svg" % label)
        write_nested(f2, panels, "module height %.2f mm" % top)
        if do_render:
            svg_preview(f1, f1.replace(".svg", "_preview.png"), 1100)

    if do_render:
        set_top(70.09)
        panels = module_panels()
        culv = place_culvert(culv_local)
        ply = (0.80, 0.66, 0.46)
        concrete = (0.86, 0.85, 0.80)
        pm = [(panel_mesh(p), ply) for p in panels]
        tint = {"underpass_top_plate": (0.88, 0.76, 0.56), "depressed_deck": (0.70, 0.56, 0.38)}
        exploded = []
        for p in panels:
            m = panel_mesh(p)
            if p.name == "underpass_top_plate":
                m.apply_translation([0, 0, 90])
            exploded.append((m, tint.get(p.name, ply)))
        tv, tcol = terrain_mesh()
        road_items = track_meshes()
        r = out_dir()
        render([((tv, tcol), None), (culv, concrete)] + road_items + pm,
               os.path.join(r, "render_underpass_scene.png"),
               cam=(ROAD_X - 170, -330, TOP + 110), target=(ROAD_X, 90, TOP - 25), fov=36)
        render([(culv, concrete)] + exploded, os.path.join(r, "render_underpass_box.png"),
               cam=(ROAD_X - 430, -470, TOP + 430), target=(ROAD_X, D / 2, 45), fov=42, sky=False)
        cm = culv_local.copy()
        render([(cm, concrete)], os.path.join(r, "render_underpass_culvert.png"),
               cam=(-120, -90, 85), target=(0, 67, 14), fov=40, size=(1200, 900), sky=False)
    set_top(70.09)
    return log


if __name__ == "__main__":
    for line in run("--no-render" not in sys.argv):
        print(line)
