"""
T-TRAK N-scale (1:160) city modules + 3D-printable buildings, generated in Blender.
Version 2 — dense, lit "Main Street" look (street right behind the tracks,
low shops in front, continuous 5-6 storey mansard apartment blocks behind,
low-relief high-rises along the back edge).

What it builds
  * Two T-TRAK DOUBLE modules (618 x 355 mm) with Kato Unitrack placeholders,
    plywood frame, printable street tiles and the city layout.
      - Module A "Main Street"   : continuous street parallel to the tracks.
      - Module B "Cross Street"  : same street + a side street to the back edge.
  * A library of parametric, print-ready buildings: hollow open-bottom shells
    (print upright, no supports) + drop-in flat roofs or mansard roofs.
    Windows are cut through for interior LED lighting.
  * STL export of every printable part, parts list CSV, .blend and night renders.

How to run
  * Blender GUI : Scripting workspace > Open > ttrak_city.py > Run Script
  * Headless    : blender -b -P ttrak_city.py            (add  -- --no-render)
  * Python bpy  : python ttrak_city.py [--no-render]     (pip install bpy)
  Output goes to ./ttrak_output next to this script (or next to the saved .blend).

Units: 1 Blender unit = 1 mm. Check the T-TRAK numbers against your club's standard.
"""

import bpy
import bmesh
import math
import os
import csv
import random

# ----------------------------------------------------------------------------
# PARAMETERS
# ----------------------------------------------------------------------------
SCALE = 160.0

# T-TRAK double module (verify with your club / the NTRAK T-TRAK standard)
MODULE_W = 618.0
MODULE_D = 355.0
MODULE_TOP_Z = 70.0
PLY_T = 6.0
TRACK_LEN = 620.0
TRACK_PIECES = (248.0, 248.0, 124.0)   # Kato 248 + 248 + 124 per line
FRONT_BALLAST_EDGE = 38.0
BALLAST_W = 25.0
TRACK_SPACING = 33.0
UNITRACK_H = 7.0

# Street (y from module front edge)
STREET_Y = 100.0                   # rear roadbed edge is at 96
CURB_STRIP = 3.0                   # raised curb on the track side
ROAD_W = 47.0                      # ~7.5 m
SIDEWALK_W = 12.0                  # ~1.9 m
ROAD_T = 1.2
SIDEWALK_T = 2.1
CROSS_STREET_X = 274.0             # module B side street (left edge)
CROSS_W = 10.0 + ROAD_W + 10.0

# Printing
WALL = 1.6
RECESS = 0.6
WINDOWS_THROUGH = True             # open windows for interior lighting
ROOF_T = 1.2
CLEAR = 0.15
PLUG_H = 2.0                       # mansard locating plug
PRINT_BED = (250.0, 250.0, 250.0)
MAX_TILE = 210.0

ROW1_Y = STREET_Y + CURB_STRIP + ROAD_W + SIDEWALK_W   # 162 front building line
ROW2_Y = 210.0
CITY_Z = SIDEWALK_T

# ----------------------------------------------------------------------------
# BUILDING LIBRARY
# floors: per-floor window style list, bottom -> top:
#   "shop" storefront | "plain" | "frame" | "pediment" | "arch" | "hood"
# roof: "flat" (+ items) or "mansard"
# ----------------------------------------------------------------------------
def apt(W, color, styles, D=56, mansard=True, items=(), bay=11, **kw):
    s = dict(W=W, D=D, gh=26, fh=20, bay=bay, win_w=5.4, win_h=10.5, styles=styles,
             color=color, cornice=1.2, dentils=True, rusticate=True, bands=True,
             awnings=False, roof="mansard" if mansard else "flat", items=list(items))
    s.update(kw)
    return s


def shop(W, color, styles, D=44, **kw):
    s = dict(W=W, D=D, gh=25, fh=20, bay=12, win_w=6.0, win_h=11, styles=styles,
             color=color, cornice=1.0, dentils=True, rusticate=False, bands=True,
             awnings=True, roof="flat", items=["hvac"])
    s.update(kw)
    return s


BUILDINGS = {
    # back row: continuous apartment blocks (front-only windows -> party walls)
    "apt_pink":   apt(66, "pink",   ["shop", "pediment", "frame", "frame", "hood"]),
    "apt_cream":  apt(54, "cream",  ["shop", "arch", "frame", "frame", "plain"], bay=9),
    "apt_white":  apt(60, "white",  ["shop", "pediment", "pediment", "frame", "frame"]),
    "apt_peach":  apt(48, "peach",  ["shop", "frame", "frame", "frame", "hood"], mansard=False,
                      items=["billboard", "chimney"], parapet=3.0),
    "apt_ochre":  apt(72, "ochre",  ["shop", "arch", "frame", "frame", "frame", "hood"]),
    "apt_rose":   apt(50, "rose",   ["shop", "hood", "hood", "hood", "hood"], mansard=False,
                      items=["tank"], parapet=3.0),
    # front row: low commercial
    "shop_brick": shop(50, "brick_dark", ["shop", "arch"], gh=26, fh=22),
    "shop_teal":  shop(40, "teal", ["shop", "frame"], awnings=False, signband=True),
    "theater":    shop(44, "cream2", ["shop", "frame"], gh=30, fh=24, awnings=False,
                       marquee=True, blade="left", items=["billboard"]),
    "hotel":      shop(50, "rose2", ["shop", "frame", "frame", "hood"], side_windows=True,
                       blade="left", items=["tank"], parapet=3.0),
    "corner_turret_R": shop(56, "brick", ["shop", "frame", "frame"], fh=21,
                            turret="right", side_windows=True, items=["hvac", "chimney"]),
    "corner_turret_L": shop(56, "brick", ["shop", "frame", "frame"], fh=21,
                            turret="left", side_windows=True, items=["hvac", "chimney"]),
    # back edge: low-relief high-rises (skyline)
    "highrise_a": apt(70, "stone", ["shop"] + ["frame"] * 7, D=26, mansard=False,
                      items=["billboard"], parapet=3.0, rusticate=False, bay=10),
    "highrise_b": apt(56, "white2", ["shop"] + ["hood"] * 6, D=26, mansard=False,
                      items=["tank"], parapet=3.0, rusticate=False, bay=8, win_w=5.0),
}

# Rows: list of segments (x_start, [building | "gap:<mm>", ...]) packed left->right.
LAYOUT = {
    "Module_A_Main_Street": dict(
        cross_street=False,
        row1=[(2, ["corner_turret_L", "shop_brick", "theater", "shop_teal", "gap:28",
                   "shop_brick", "hotel", "shop_teal", "gap:22", "shop_brick", "corner_turret_R"])],
        row2=[(20, ["apt_pink", "apt_cream", "apt_white", "apt_peach", "apt_ochre",
                    "apt_rose", "apt_pink", "apt_cream", "apt_white", "apt_peach"])],
        row3=[(30, ["highrise_a", "gap:120", "highrise_b", "gap:150", "highrise_a"])],
    ),
    "Module_B_Cross_Street": dict(
        cross_street=True,
        row1=[(60, ["shop_teal", "shop_brick", "theater", "gap:4", "corner_turret_R"]),
              (CROSS_STREET_X + CROSS_W + 2, ["corner_turret_L", "shop_brick", "hotel", "gap:20",
                                               "shop_teal", "theater"])],
        row2=[(2, ["apt_ochre", "apt_pink", "apt_cream", "apt_peach"]),
              (CROSS_STREET_X + CROSS_W + 2, ["apt_white", "apt_rose", "apt_ochre", "apt_pink"])],
        row3=[(40, ["highrise_b", "gap:80", "highrise_a"]),
              (CROSS_STREET_X + CROSS_W + 60, ["highrise_a", "gap:40", "highrise_b"])],
    ),
}

COLORS = {
    "pink": (0.78, 0.50, 0.48), "cream": (0.85, 0.74, 0.55), "white": (0.86, 0.84, 0.80),
    "peach": (0.86, 0.58, 0.40), "ochre": (0.82, 0.62, 0.30), "rose": (0.66, 0.30, 0.30),
    "brick": (0.45, 0.14, 0.10), "brick_dark": (0.30, 0.11, 0.09), "teal": (0.30, 0.42, 0.40),
    "cream2": (0.80, 0.72, 0.60), "rose2": (0.72, 0.42, 0.42), "stone": (0.60, 0.58, 0.54),
    "white2": (0.75, 0.75, 0.73),
    "roof": (0.12, 0.12, 0.13), "slate": (0.16, 0.17, 0.19), "road": (0.10, 0.10, 0.11),
    "ply": (0.70, 0.55, 0.36), "ballast": (0.30, 0.28, 0.26), "rail": (0.35, 0.30, 0.27),
    "grass": (0.12, 0.20, 0.08), "base": (0.30, 0.30, 0.30), "fascia": (0.03, 0.03, 0.03),
    "table": (0.06, 0.06, 0.07), "metal": (0.10, 0.10, 0.10),
}

# ----------------------------------------------------------------------------
# Geometry helpers  (shape = (verts, faces))
# ----------------------------------------------------------------------------
_BOX_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def box(x0, y0, z0, x1, y1, z1):
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return v, _BOX_F


def tapered(x0, y0, x1, y1, z0, z1, inset):
    """Box whose top rectangle is shrunk by `inset` on every side (mansard)."""
    i = inset
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0 + i, y0 + i, z1), (x1 - i, y0 + i, z1), (x1 - i, y1 - i, z1), (x0 + i, y1 - i, z1)]
    return v, _BOX_F


def prism(profile, axis, a0, a1):
    """Extrude a 2D polygon. axis='x': profile (y,z); 'y': (x,z); 'z': (x,y)."""
    n = len(profile)

    def P(p, a):
        return (a, p[0], p[1]) if axis == "x" else (p[0], a, p[1]) if axis == "y" else (p[0], p[1], a)

    v = [P(p, a0) for p in profile] + [P(p, a1) for p in profile]
    f = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    f += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return v, f


def frustum(cx, cy, r0, r1, z0, z1, seg=20, rot=0.0):
    ang = [rot + 2 * math.pi * i / seg for i in range(seg)]
    v = [(cx + r0 * math.cos(a), cy + r0 * math.sin(a), z0) for a in ang]
    v += [(cx + max(r1, 1e-3) * math.cos(a), cy + max(r1, 1e-3) * math.sin(a), z1) for a in ang]
    f = [tuple(range(seg)), tuple(range(2 * seg - 1, seg - 1, -1))]
    f += [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    return v, f


def cylinder(cx, cy, r, z0, z1, seg=20):
    return frustum(cx, cy, r, r, z0, z1, seg)


def arch_profile(cx, z_spring, r, z_bottom, seg=12):
    """Window with round top, profile in (x,z)."""
    pts = [(cx - r, z_bottom), (cx + r, z_bottom)]
    pts += [(cx + r * math.cos(math.pi * i / seg), z_spring + r * math.sin(math.pi * i / seg))
            for i in range(seg + 1)]
    return pts


# ----------------------------------------------------------------------------
# Blender helpers
# ----------------------------------------------------------------------------
_SOLVERS = [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items]
SOLVER = "MANIFOLD" if "MANIFOLD" in _SOLVERS else "EXACT"
MATERIALS = {}


def material(key, emission=None, strength=0.0):
    if key not in MATERIALS:
        m = bpy.data.materials.new("ttrak_" + key)
        rgb = COLORS.get(key, emission or (1, 1, 1))
        m.diffuse_color = (*rgb, 1.0)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.8
            if emission:
                bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
                bsdf.inputs["Emission Strength"].default_value = strength
        MATERIALS[key] = m
    return MATERIALS[key]


def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def mesh_obj(name, shape, coll, mat=None):
    verts, faces = shape
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat:
        me.materials.append(mat if isinstance(mat, bpy.types.Material) else material(mat))
    return ob


def _boolean(base, op, shapes):
    if not shapes:
        return
    c = collection("_bool_ops")
    for i, s in enumerate(shapes):
        mesh_obj("_op%d" % i, s, c)
    mod = base.modifiers.new("b", "BOOLEAN")
    mod.operation = op
    mod.operand_type = "COLLECTION"
    mod.collection = c
    mod.solver = SOLVER
    dg = bpy.context.evaluated_depsgraph_get()
    new_me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
    base.modifiers.remove(mod)
    old = base.data
    base.data = new_me
    new_me.name = old.name
    bpy.data.meshes.remove(old)
    for o in list(c.objects):
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    bpy.data.collections.remove(c)


def solid(name, adds, cuts, coll, mat, adds2=()):
    """((union adds) - cuts) + adds2  -> one manifold object."""
    base = mesh_obj(name, adds[0], coll)
    _boolean(base, "UNION", adds[1:])
    _boolean(base, "DIFFERENCE", list(cuts))
    _boolean(base, "UNION", list(adds2))
    base.data.materials.clear()
    base.data.materials.append(material(mat))
    return base


def place(obj, coll, loc):
    d = obj.copy()                  # linked duplicate: shares the mesh
    d.location = loc
    coll.objects.link(d)
    return d


# ----------------------------------------------------------------------------
# Buildings
# ----------------------------------------------------------------------------
def floors_of(s):
    return len(s["styles"])


def roof_z_of(s):
    return s["gh"] + s["fh"] * (floors_of(s) - 1)


def top_of(s):
    return roof_z_of(s) + (0.0 if s["roof"] == "mansard" else s.get("parapet", 4.0))


def make_shell(name, s, coll):
    W, D, gh, fh = s["W"], s["D"], s["gh"], s["fh"]
    n = floors_of(s)
    roof_z, top = roof_z_of(s), top_of(s)
    mansard = s["roof"] == "mansard"
    adds, cuts, adds2 = [box(0, 0, 0, W, D, top)], [], []
    cuts.append(box(WALL, WALL, -1, W - WALL, D - WALL, top + 1))

    # roof supports: corner posts
    pz = roof_z - (PLUG_H + 0.2 if mansard else ROOF_T)
    p = 3.0
    for (x0, x1) in ((WALL - 0.3, WALL + p), (W - WALL - p, W - WALL + 0.3)):
        for (y0, y1) in ((WALL - 0.3, WALL + p), (D - WALL - p, D - WALL + 0.3)):
            adds2.append(box(x0, y0, 0, x1, y1, pz))

    sides = ["front"] + (["left", "right"] if s.get("side_windows") else [])
    length = {"front": W, "left": D, "right": D}

    def F(side, a0, a1, z0, z1, out, inn):
        """Box on a facade: a = position along facade, out = protrusion, inn = depth into wall."""
        if side == "front":
            return box(a0, -out, z0, a1, inn, z1)
        if side == "left":          # a runs along +y
            return box(-out, a0, z0, inn, a1, z1)
        return box(W - inn, a0, z0, W + out, a1, z1)

    def Fprism(side, prof_az, out, inn):
        """Prism on a facade from a profile in (a, z)."""
        if side == "front":
            return prism(prof_az, "y", -out, inn)
        if side == "left":
            return prism(prof_az, "x", -out, inn)
        return prism(prof_az, "x", W - inn, W + out)

    rec = WALL + 1.0 if WINDOWS_THROUGH else RECESS

    # cornice, dentils, floor bands
    c = s.get("cornice", 0.0)
    for side in sides:
        L = length[side]
        if c > 0:
            adds.append(F(side, 0, L, top - 2.5, top, c, 0.5))
            if s.get("dentils"):
                k = int(L // 1.8)
                for i in range(k):
                    a = 0.5 + i * 1.8
                    if a + 0.8 < L:
                        adds.append(F(side, a, a + 0.8, top - 3.3, top - 2.5, 0.6, 0.5))
        if s.get("bands"):
            for i in range(1, n):
                z = gh + fh * (i - 1)
                adds.append(F(side, 0, L, z - 0.5, z + 0.5, 0.4, 0.5))
        if s.get("rusticate") and side == "front":
            z = 3.0
            while z < gh - 2:
                cuts.append(F(side, -1, L + 1, z, z + 0.35, 1, 0.3))
                z += 2.6

    # windows, storefronts
    for side in sides:
        L = length[side]
        bays = max(1, int(L // s["bay"]))
        bw = L / bays
        for fl, style in enumerate(s["styles"]):
            fb = 0 if fl == 0 else gh + fh * (fl - 1)
            fht = gh if fl == 0 else fh
            if style == "shop":
                if side != "front":
                    continue
                nb = max(1, int(L // 16))
                sbw = L / nb
                o_top = gh - 6
                for i in range(nb):
                    cx = sbw * (i + 0.5)
                    a0, a1 = cx - sbw / 2 + 1.8, cx + sbw / 2 - 1.8
                    cuts.append(F(side, a0, a1, 2.5, o_top, 1, WALL + 1 if WINDOWS_THROUGH else 1.0))
                    adds2.append(F(side, a0 - 0.2, a1 + 0.2, 2.5, 2.9, 0.0, 0.8))      # sill
                    for m in (1 / 3, 2 / 3):                                           # mullions
                        mx = a0 + (a1 - a0) * m
                        adds2.append(F(side, mx - 0.4, mx + 0.4, 2.5, o_top, -0.3, 0.9))
                    if s.get("awnings"):
                        zt = o_top + 2.2
                        d = 3.5
                        prof = [(0.5, zt), (-d, zt - d), (-d, zt - d - 0.9), (0.5, zt - 1.4)]
                        adds2.append(prism(prof, "x", a0 - 0.6, a1 + 0.6))
                if s.get("signband"):
                    adds2.append(F(side, 1, L - 1, gh - 4.6, gh - 1.6, 0.6, 0.5))
                if s.get("marquee"):
                    zt, d = gh - 1.5, 6.0
                    prof = [(0.5, zt), (-d, zt - d), (-d, zt - d - 1.5), (0.5, zt - 2.5)]
                    adds2.append(prism(prof, "x", L * 0.15, L * 0.85))
                continue
            ww, wh = s["win_w"], s["win_h"]
            if side == "front" and fl == n - 1 and s.get("turret"):
                pass
            sill = fb + (fht - wh) / 2 + 0.8
            for i in range(bays):
                cx = bw * (i + 0.5)
                if s.get("turret") and side == "front":
                    tx = W - 8 if s["turret"] == "right" else 8
                    if abs(cx - tx) < 8:
                        continue
                if style == "arch":
                    r = ww / 2
                    zs = sill + wh - r
                    adds.append(Fprism(side, arch_profile(cx, zs, r + 0.8, sill - 0.2), 0.4, 0.5))
                    cuts.append(Fprism(side, arch_profile(cx, zs, r, sill), 1, rec))
                else:
                    if style in ("frame", "pediment"):
                        adds.append(F(side, cx - ww / 2 - 0.8, cx + ww / 2 + 0.8,
                                      sill - 0.8, sill + wh + 0.8, 0.4, 0.5))
                    if style == "pediment":
                        zb = sill + wh + 0.8
                        prof = [(cx - ww / 2 - 1.2, zb), (cx + ww / 2 + 1.2, zb), (cx, zb + 2.2)]
                        adds.append(Fprism(side, prof, 0.7, 0.5))
                    if style == "hood":
                        adds.append(F(side, cx - ww / 2 - 0.8, cx + ww / 2 + 0.8,
                                      sill + wh + 0.4, sill + wh + 1.4, 0.8, 0.5))
                    cuts.append(F(side, cx - ww / 2, cx + ww / 2, sill, sill + wh, 1, rec))
                adds.append(F(side, cx - ww / 2 - 0.6, cx + ww / 2 + 0.6, sill - 0.7, sill, 0.5, 0.5))

    # projecting blade sign (45-degree underside, prints without support)
    if s.get("blade"):
        x = 3.0 if s["blade"] == "left" else W - 4.2
        z0, z1 = gh + 2, min(top - 4, gh + 2 + 30)
        prof = [(0.5, z0), (-7, z0 + 7), (-7, z1), (0.5, z1)]
        adds2.append(prism(prof, "x", x, x + 1.2))

    # corner turret on a 45-degree corbel, conical cap
    if s.get("turret"):
        r = 6.0
        tx = W - r - 1 if s["turret"] == "right" else r + 1
        ty = -2.5
        adds2.append(frustum(tx, ty, 0.6, r, gh - 5.5, gh, seg=8, rot=math.pi / 8))
        adds2.append(frustum(tx, ty, r, r, gh, top + 3, seg=8, rot=math.pi / 8))
        adds2.append(frustum(tx, ty, r + 0.6, 0.3, top + 3, top + 15, seg=8, rot=math.pi / 8))
        adds2.append(frustum(tx, ty, r + 0.6, r + 0.6, top + 2.4, top + 3.0, seg=8, rot=math.pi / 8))
    shell = solid(name + "_shell", adds, cuts, coll, s["color"], adds2)
    if s.get("turret"):   # turret windows
        r, tx = 6.0, (W - 7 if s["turret"] == "right" else 7)
        tc = []
        for fl in range(1, n):
            fb = gh + fh * (fl - 1)
            sill = fb + (fh - s["win_h"]) / 2 + 0.8
            tc.append(box(tx - 2, -2.5 - r - 1, sill, tx + 2, -2.5 - r + 1.4, sill + s["win_h"]))
        _boolean(shell, "DIFFERENCE", tc)
    return shell


def make_flat_roof(name, s, coll):
    Wi = s["W"] - 2 * WALL - 2 * CLEAR
    Di = s["D"] - 2 * WALL - 2 * CLEAR
    T = ROOF_T
    adds, cuts = [box(0, 0, 0, Wi, Di, T)], []
    for item in s.get("items", []):
        if item == "hvac":
            adds.append(box(Wi * 0.55, Di * 0.4, T, Wi * 0.55 + 10, Di * 0.4 + 8, T + 5))
        elif item == "chimney":
            adds.append(box(Wi * 0.12, Di * 0.7, T, Wi * 0.12 + 4, Di * 0.7 + 6, T + 10))
        elif item == "tank":
            cx, cy = Wi * 0.65, Di * 0.6
            adds.append(box(cx - 4.5, cy - 4.5, T, cx + 4.5, cy + 4.5, T + 3))
            adds.append(cylinder(cx, cy, 4.2, T + 3, T + 12))
            adds.append(frustum(cx, cy, 4.2, 0.6, T + 12, T + 15))
        elif item == "billboard":     # panel bridges between two posts
            bw = min(30.0, Wi - 6)
            x0, y0 = (Wi - bw) / 2, min(Di * 0.55, Di - 6)
            adds.append(box(x0, y0, T, x0 + 2, y0 + 3, T + 6))
            adds.append(box(x0 + bw - 2, y0, T, x0 + bw, y0 + 3, T + 6))
            adds.append(box(x0, y0, T + 6, x0 + bw, y0 + 1.2, T + 22))
    return solid(name + "_roof", adds, cuts, coll, "roof"), (WALL + CLEAR, WALL + CLEAR, -T)


def make_mansard(name, s, coll):
    """Mansard roof: hollow (so the building's LEDs light the dormers),
    45-degree internal chamfer so the ceiling bridge stays short."""
    W, D = s["W"], s["D"]
    h, inset = 14.0, 3.6
    P = PLUG_H
    i0 = WALL + CLEAR
    adds = [tapered(0, 0, W, D, P, P + h, inset),
            box(i0, i0, 0, W - i0, D - i0, P + 0.5)]
    c0 = i0 + 1.6
    ztop = P + h - 1.4
    span_in = min((W - 2 * c0), (D - 2 * c0)) / 2 - 3
    ci = min(ztop + 1, span_in)
    cuts = [tapered(c0, c0, W - c0, D - c0, -1, ztop, ci)]
    adds2 = []
    bays = max(1, int(W // s["bay"]))
    bw = W / bays
    dw, dh = s["win_w"] + 2.4, s["win_h"] * 0.75
    zd = P + 1.5
    yf = inset * 0.15
    for i in range(bays):
        cx = bw * (i + 0.5)
        adds2.append(box(cx - dw / 2, yf, zd, cx + dw / 2, yf + 9, zd + dh))
        prof = [(cx - dw / 2 - 0.4, zd + dh), (cx + dw / 2 + 0.4, zd + dh), (cx, zd + dh + dw * 0.45)]
        adds2.append(prism(prof, "y", yf - 0.4, yf + 9))
    # chimneys sit on the solid outer band, not on the bridged ceiling
    for cx in (inset + 2.5, W - inset - 6.5):
        adds2.append(box(cx, D * 0.45, P + h - 0.5, cx + 4, D * 0.45 + 6, P + h + 7))
    roof = solid(name + "_roof", adds, cuts, coll, "slate", adds2)
    wc = []
    for i in range(bays):       # dormer windows tunnel into the hollow roof
        cx = bw * (i + 0.5)
        wc.append(box(cx - s["win_w"] / 2 + 0.6, yf - 1, zd + 1.2, cx + s["win_w"] / 2 - 0.6,
                      yf + 12, zd + dh - 0.8))
    _boolean(roof, "DIFFERENCE", wc)
    return roof, (0.0, 0.0, -P)


def make_roof(name, s, coll):
    return make_mansard(name, s, coll) if s["roof"] == "mansard" else make_flat_roof(name, s, coll)


# ----------------------------------------------------------------------------
# Road tiles
# ----------------------------------------------------------------------------
def road_tile(name, w, d, sidewalks, grooves, coll):
    adds = [box(0, 0, 0, w, d, ROAD_T)]
    adds += [box(x0, y0, 0, x1, y1, SIDEWALK_T) for (x0, y0, x1, y1) in sidewalks]
    cuts = [box(x0, y0, ROAD_T - 0.3, x1, y1, ROAD_T + 1) for (x0, y0, x1, y1) in grooves]
    return solid(name, adds, cuts, coll, "road")


def dashes(g0, length, c, dash=12.0, gap=18.0, axis="x"):
    out, period = [], dash + gap
    x = math.floor(g0 / period) * period
    while x < g0 + length:
        a, b = max(x, g0), min(x + dash, g0 + length)
        if b - a > 2:
            out.append((a - g0, c - 0.3, b - g0, c + 0.3) if axis == "x" else (c - 0.3, a - g0, c + 0.3, b - g0))
        x += period
    return out


def split_lengths(x0, x1):
    L = x1 - x0
    k = max(1, math.ceil(L / MAX_TILE))
    return [(x0 + L * i / k, x0 + L * (i + 1) / k) for i in range(k)]


STREET_D = CURB_STRIP + ROAD_W + SIDEWALK_W


def main_street_tiles(prefix, segments, coll):
    tiles = []
    for (sx0, sx1) in segments:
        for (a, b) in split_lengths(sx0, sx1):
            w = b - a
            sw = [(0, 0, w, CURB_STRIP), (0, STREET_D - SIDEWALK_W, w, STREET_D)]
            gr = dashes(a, w, CURB_STRIP + ROAD_W / 2)
            name = "%s_street_x%03d" % (prefix, int(round(a)))
            tiles.append((road_tile(name, w, STREET_D, sw, gr, coll), (a, STREET_Y)))
    return tiles


def cross_street_tiles(prefix, x0, coll):
    w = CROSS_W
    tiles = []
    sw = [(0, 0, w, CURB_STRIP), (0, STREET_D - SIDEWALK_W, 10, STREET_D),
          (w - 10, STREET_D - SIDEWALK_W, w, STREET_D)]
    tiles.append((road_tile(prefix + "_intersection", w, STREET_D, sw, [], coll), (x0, STREET_Y)))
    d2 = MODULE_D - ROW1_Y
    sw = [(0, 0, 10, d2), (w - 10, 0, w, d2)]
    gr = dashes(0, d2 - 20, w / 2, axis="y")
    gr = [(a, b + 20, c, d + 20) for (a, b, c, d) in gr]
    xx = 12.0
    while xx + 3 <= w - 12:
        gr.append((xx, 3, xx + 3, 14))
        xx += 6
    tiles.append((road_tile(prefix + "_cross_street", w, d2, sw, gr, coll), (x0, ROW1_Y)))
    return tiles


# ----------------------------------------------------------------------------
# Module frame, track, scenery helpers (reference / render only)
# ----------------------------------------------------------------------------
def add(coll, name, shape, mat, ox):
    o = mesh_obj(name, shape, coll, mat)
    o.location.x += ox
    return o


def build_module_frame(coll, ox):
    W, D, T, H = MODULE_W, MODULE_D, PLY_T, MODULE_TOP_Z
    ah = 50.0
    add(coll, "top", box(0, 0, -T, W, D, 0), "ply", ox)
    add(coll, "fascia", box(0, -T, -ah, W, 0, 0), "fascia", ox)
    add(coll, "apron_back", box(0, D - T, -ah, W, D, -T), "ply", ox)
    add(coll, "apron_l", box(0, T, -ah, T, D - T, -T), "ply", ox)
    add(coll, "apron_r", box(W - T, T, -ah, W, D - T, -T), "ply", ox)
    for (fx, fy) in [(30, 30), (W - 30, 30), (30, D - 30), (W - 30, D - 30)]:
        add(coll, "leg", cylinder(fx, fy, 6, -H, -ah, 16), "metal", ox)


def build_track(coll, ox):
    for t, yc in enumerate([FRONT_BALLAST_EDGE + BALLAST_W / 2,
                            FRONT_BALLAST_EDGE + BALLAST_W / 2 + TRACK_SPACING]):
        x = -(TRACK_LEN - MODULE_W) / 2
        for k, L in enumerate(TRACK_PIECES):
            prof = [(yc - BALLAST_W / 2, 0), (yc + BALLAST_W / 2, 0),
                    (yc + 9, UNITRACK_H - 1.7), (yc - 9, UNITRACK_H - 1.7)]
            add(coll, "track", prism(prof, "x", x + 0.2, x + L - 0.2), "ballast", 0).location.x += ox
            for r in (-4.5, 4.5):
                add(coll, "rail", box(x, yc + r - 0.4, UNITRACK_H - 1.7, x + L, yc + r + 0.4, UNITRACK_H),
                    "rail", ox)
            x += L
    add(coll, "grass", box(0, 0, 0, MODULE_W, FRONT_BALLAST_EDGE, 0.6), "grass", ox)
    add(coll, "grass", box(0, FRONT_BALLAST_EDGE + TRACK_SPACING + BALLAST_W, 0, MODULE_W, STREET_Y, 0.8),
        "grass", ox)


LIGHT_TINTS = [(1.0, 0.72, 0.38), (1.0, 0.82, 0.55), (1.0, 0.9, 0.75), (0.95, 0.6, 0.3)]


def interior_light(coll, s, loc, rng):
    """Render-only glowing box inside a shell (stands in for LED strips)."""
    tint = rng.randrange(len(LIGHT_TINTS))
    mat = material("light%d" % tint, LIGHT_TINTS[tint], 6.0)
    W, D = s["W"], s["D"]
    o = mesh_obj("interior_light", box(WALL + 2, WALL + 2, 1, W - WALL - 2, D - WALL - 2,
                                       roof_z_of(s) + (PLUG_H + 6 if s["roof"] == "mansard" else -1.5)),
                 coll, mat)
    o.location = loc
    o.visible_shadow = False


def street_lamps(coll, ox, xs):
    lamp_mat = material("lamp", (1.0, 0.85, 0.6), 30.0)
    for x in xs:
        y = ROW1_Y - 2.5
        add(coll, "lamp_post", cylinder(x, y, 0.5, CITY_Z, CITY_Z + 30, 8), "metal", ox)
        add(coll, "lamp_arm", box(x - 0.3, y - 6, CITY_Z + 29, x + 0.3, y, CITY_Z + 30), "metal", ox)
        add(coll, "lamp_head", box(x - 1.2, y - 7, CITY_Z + 28, x + 1.2, y - 4.5, CITY_Z + 29.2), lamp_mat, ox)
        ld = bpy.data.lights.new("lamp", "POINT")
        ld.energy = 900
        ld.color = (1.0, 0.8, 0.55)
        ld.shadow_soft_size = 1.5
        lo = bpy.data.objects.new("lamp_light", ld)
        coll.objects.link(lo)
        lo.location = (ox + x, y - 5.5, CITY_Z + 26.5)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def out_dir():
    if bpy.data.filepath:
        return os.path.join(os.path.dirname(bpy.data.filepath), "ttrak_output")
    f = globals().get("__file__")
    if f and os.path.isfile(f):
        return os.path.join(os.path.dirname(os.path.abspath(f)), "ttrak_output")
    return os.path.join(os.path.expanduser("~"), "ttrak_output")


def reset_scene():
    old = bpy.data.collections.get("TTRAK")
    if old:
        stack = [old]
        while stack:
            c = stack.pop()
            stack.extend(c.children)
            for o in list(c.objects):
                bpy.data.objects.remove(o)
            bpy.data.collections.remove(c)
    if bpy.app.background:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"


def export_stl(obj, path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    loc = obj.location.copy()
    obj.location = (0, 0, 0)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0,
                          use_scene_unit=False, apply_modifiers=True)
    obj.location = loc
    obj.select_set(False)


def pack(segments):
    """Expand row segments into (building, x) placements."""
    out = []
    for x, names in segments:
        for nm in names:
            if nm.startswith("gap:"):
                x += float(nm[4:])
                continue
            out.append((nm, x))
            x += BUILDINGS[nm]["W"]
    return out


def run(render=True):
    reset_scene()
    out = out_dir()
    for kind in ("buildings", "roads"):
        d = os.path.join(out, "stl", kind)
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):          # clear STLs from earlier runs
            if f.endswith(".stl"):
                os.remove(os.path.join(d, f))
    rng = random.Random(7)

    root = collection("TTRAK")
    lib = collection("Print_Parts_Library", root)
    parts, roof_off = {}, {}

    used = set()
    for lay in LAYOUT.values():
        for row in ("row1", "row2", "row3"):
            used.update(nm for nm, _ in pack(lay.get(row, [])))

    lib_x = 0.0
    for bname, spec in BUILDINGS.items():
        if bname not in used:
            continue
        sh = make_shell(bname, spec, lib)
        rf, off = make_roof(bname, spec, lib)
        roof_off[bname] = off
        parts[sh.name] = [sh, 0, "buildings"]
        parts[rf.name] = [rf, 0, "buildings"]
        sh.location = (lib_x, -500, 0)
        rf.location = (lib_x, -500 - spec["D"] - 30, 0)
        lib_x += spec["W"] + 25

    for mi, (mname, lay) in enumerate(LAYOUT.items()):
        ox = mi * (MODULE_W + 2.0)
        mc = collection(mname, root)
        fx = collection(mname + "_render_only", mc)
        build_module_frame(fx, ox)
        build_track(fx, ox)
        prefix = "A" if mi == 0 else "B"
        rc = collection(mname + "_roads", mc)
        if lay["cross_street"]:
            cx0, cx1 = CROSS_STREET_X, CROSS_STREET_X + CROSS_W
            tiles = main_street_tiles(prefix, [(0, cx0), (cx1, MODULE_W)], rc)
            tiles += cross_street_tiles(prefix, cx0, rc)
            bases = [(0, cx0), (cx1, MODULE_W)]
        else:
            tiles = main_street_tiles(prefix, [(0, MODULE_W)], rc)
            bases = [(0, MODULE_W)]
        for t, (tx, ty) in tiles:
            parts[t.name] = [t, 1, "roads"]
            t.location = (tx + ox, ty, 0)
        for (b0, b1) in bases:
            add(fx, "city_base", box(b0, ROW1_Y, 0, b1, MODULE_D, CITY_Z), "base", ox)
        lamp_xs = [x for x in range(30, int(MODULE_W), 75)
                   if not (lay["cross_street"] and CROSS_STREET_X - 4 < x < CROSS_STREET_X + CROSS_W + 4)]
        street_lamps(fx, ox, lamp_xs)

        for row in ("row1", "row2", "row3"):
            for bname, x in pack(lay.get(row, [])):
                spec = BUILDINGS[bname]
                y = {"row1": ROW1_Y, "row2": ROW2_Y, "row3": MODULE_D - 2 - spec["D"]}[row]
                if x + spec["W"] > MODULE_W - 1:
                    print("WARNING: %s at x=%.0f runs past the end of %s" % (bname, x, mname))
                if lay["cross_street"] and x < CROSS_STREET_X + CROSS_W and x + spec["W"] > CROSS_STREET_X:
                    print("WARNING: %s at x=%.0f sits in the cross street on %s" % (bname, x, mname))
                sh = parts[bname + "_shell"][0]
                rf = parts[bname + "_roof"][0]
                place(sh, mc, (ox + x, y, CITY_Z))
                o = roof_off[bname]
                place(rf, mc, (ox + x + o[0], y + o[1], CITY_Z + roof_z_of(spec) + o[2]))
                interior_light(fx, spec, (ox + x, y, CITY_Z), rng)
                parts[sh.name][1] += 1
                parts[rf.name][1] += 1

    rows = []
    for name, (obj, qty, kind) in parts.items():
        export_stl(obj, os.path.join(out, "stl", kind, name + ".stl"))
        dx, dy, dz = (round(v, 1) for v in obj.dimensions)
        fits = dx <= PRINT_BED[0] and dy <= PRINT_BED[1] and dz <= PRINT_BED[2]
        rows.append([kind, name, qty, dx, dy, dz, "yes" if fits else "NO - too big"])
    with open(os.path.join(out, "parts_list.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "part", "qty_in_layout", "x_mm", "y_mm", "z_mm", "fits_bed"])
        w.writerows(rows)

    lib.hide_render = True
    setup_render_scene()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "ttrak_city.blend"))
    if render:
        do_renders(out)
    print("T-TRAK city: wrote %d printable parts to %s" % (len(parts), out))
    return out


# ----------------------------------------------------------------------------
# Lighting / cameras / renders
# ----------------------------------------------------------------------------
def _cam(name, loc, target, lens=35):
    from mathutils import Vector
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 5
    cam.clip_end = 20000
    ob = bpy.data.objects.new(name, cam)
    bpy.data.collections["TTRAK"].objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def parts_center_x():
    xs = [o.location.x + o.dimensions.x / 2 for o in bpy.data.collections["Print_Parts_Library"].objects]
    return (min(xs) + max(xs)) / 2 if xs else 300.0


def setup_render_scene():
    sc = bpy.context.scene
    root = bpy.data.collections["TTRAK"]
    moon = bpy.data.lights.new("Moon", "SUN")
    moon.energy = 0.08
    moon.color = (0.6, 0.7, 1.0)
    mo = bpy.data.objects.new("Moon", moon)
    root.objects.link(mo)
    mo.rotation_euler = (math.radians(45), math.radians(10), math.radians(-30))
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.01, 0.03, 0.04, 1)
        bg.inputs[1].default_value = 1.0
    mesh_obj("table", box(-400, -900, -MODULE_TOP_Z - 20, 1700, 800, -MODULE_TOP_Z), root, "table")
    mesh_obj("backdrop", box(-400, MODULE_D + 40, -MODULE_TOP_Z, 1700, MODULE_D + 50, 500), root, "teal")
    # (left in for a day-time parts shot)
    sun = bpy.data.lights.new("PartsSun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("PartsSun", sun)
    root.objects.link(so)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    so.hide_render = True
    sc.camera = _cam("Cam_Overview", (-180, -520, 560), (520, 210, 0), 26)
    _cam("Cam_Street", (930, 70, 60), (760, 230, 45), 22)
    cx = parts_center_x()
    _cam("Cam_Parts", (cx, -1750, 520), (cx, -600, 40), 30)


def do_renders(out):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    lib = bpy.data.collections["Print_Parts_Library"]
    mods = [c for c in bpy.data.collections if c.name in LAYOUT]
    bg = sc.world.node_tree.nodes.get("Background")
    for cam, parts_shot in (("Cam_Overview", False), ("Cam_Street", False), ("Cam_Parts", True)):
        lib.hide_render = not parts_shot
        for c in mods:
            c.hide_render = parts_shot
        bpy.data.objects["PartsSun"].hide_render = not parts_shot
        bpy.data.objects["backdrop"].hide_render = parts_shot
        bg.inputs[0].default_value = (0.7, 0.75, 0.8, 1) if parts_shot else (0.01, 0.03, 0.04, 1)
        sc.camera = bpy.data.objects[cam]
        sc.render.filepath = os.path.join(out, "render_%s.png" % cam[4:].lower())
        bpy.ops.render.render(write_still=True)
    lib.hide_render = True
    for c in mods:
        c.hide_render = False
    bpy.data.objects["PartsSun"].hide_render = True
    bpy.data.objects["backdrop"].hide_render = False
    bg.inputs[0].default_value = (0.01, 0.03, 0.04, 1)
    sc.camera = bpy.data.objects["Cam_Overview"]


if __name__ == "__main__":
    import sys
    run(render="--no-render" not in sys.argv)
