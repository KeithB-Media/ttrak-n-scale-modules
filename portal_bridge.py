"""
Portal North Bridge (Hackensack River, NJ) — N-scale T-TRAK module set, generated in Blender.

The prototype: a two-track, fixed, high-level railroad bridge (opened March 2026) whose main
crossing is three 400 ft steel *network tied arches* (~86 ft tall, ~50 ft wide, 50 ft over the
water), with concrete approach viaducts across the Meadowlands.

The model (selective compression, 1:160):
  * 4 T-TRAK double modules:  West approach viaduct | Arch 1 | Arch 2 | Arch 3
  * each arch spans one double module (600 mm between bearings = 79% of the 762 mm full-scale length)
  * track deck sits at the standard T-TRAK track base, so Kato Unitrack joins the neighbours normally
  * river surface 62 mm below the track base (selectively compressed from 50 ft = 95 mm)

Printable parts (all print with no supports):
  * arch_rib_end / arch_rib_mid      flat-printed arch side panels: rib + tie girder + network hangers
                                     (each arch side = end + mid + end, joined with splice plates)
  * splice_tie / splice_rib          joint plates, glued on the outer face
  * arch_strut                       top lateral struts between the two arch ribs
  * arch_deck                        deck slab + floor beams; underside channel for a 20 x 3 mm
                                     aluminium flat bar (hidden) that carries the train load
  * pier_face                        4 mm hammerhead pier face, glued on the laser-cut ply pier core
  * pier_full                        free-standing approach-viaduct pier
  * abutment_seat                    carries the first approach span on the ply abutment
  * approach_span                    concrete box-girder viaduct span (prints standing on end)

Run: python portal_bridge.py [--no-render]  |  blender -b -P portal_bridge.py  (needs ttrak_city.py)
"""

import os
import sys
import math

try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    import bpy as _bpy
    _here = os.path.dirname(_bpy.data.filepath) if _bpy.data.filepath else os.getcwd()
if _here not in sys.path:
    sys.path.insert(0, _here)

import bpy
from mathutils import Matrix, Vector
import ttrak_city as tc
from ttrak_city import box, prism, mesh_obj, solid, _boolean, collection, material

# ----------------------------------------------------------------------------
# PARAMETERS (mm). z = 0 is the T-TRAK track base (top of a normal module).
# ----------------------------------------------------------------------------
MW = tc.MODULE_W                 # 618 double module
N_ARCH_MODULES = 3
SPAN = 600.0                     # arch bearing to bearing
X0 = (MW - SPAN) / 2             # 9: bearing position from module end
RISE = 150.0                     # arch rise above the tie (prototype ~86 ft = 164 mm)
RIB_D = 7.0                      # rib depth in elevation
PANEL_T = 3.0                    # rib/tie thickness (print height)
HANGER_W, HANGER_T = 0.9, 1.2
HANGER_STEP, HANGER_REACH = 20.0, 70.0
TIE_Z0, TIE_Z1 = -10.0, 6.0      # tie girder band
YC = (tc.FRONT_BALLAST_EDGE + tc.BALLAST_W / 2) + tc.TRACK_SPACING / 2   # 67: bridge centreline
HALF_IN = 45.0                   # rib inner face offset from centreline (90 mm clear)
DECK_T = 3.0
FLOOR_Z = -10.0
BAR_W, BAR_T = 20.4, 3.2         # channel for 20 x 3 mm aluminium flat bar
WATER_Z = -tc.MODULE_TOP_Z + 8   # -62
CAP_Z = -12.0                    # pier cap top (2 mm bearings carry the tie at -10)
PLY = 5.0                        # laser-cut ply (portal_laser.py): the end plates are the pier cores
PIER_T = X0 - PLY                # printed pier face thickness (4 mm) glued on the ply core
DEPTH = 330.0                    # module depth of the laser-cut boxes
BASE_TOP_Z = -tc.MODULE_TOP_Z + PLY
SPAN_PITCH = 206.0               # viaduct pier spacing (3 spans per double module)
TR_ABUT_FACE = 206.0             # transition module: abutment face / first viaduct span start
TR_TOP_X = 100.0                 # transition module: full-height track-level ground ends here
MODULES = [("W_Transition", "tw"), ("W_Viaduct", "v"), ("Arch_1", "a"), ("Arch_2", "a"),
           ("Arch_3", "a"), ("E_Transition", "te")]

tc.COLORS.update({
    "steel": (0.62, 0.66, 0.70), "concrete2": (0.66, 0.65, 0.62), "water": (0.05, 0.12, 0.12),
    "marsh": (0.36, 0.40, 0.18), "mud": (0.22, 0.20, 0.15), "train": (0.70, 0.72, 0.74),
    "sky": (0.6, 0.7, 0.85),
})


def rib_c(u):
    """Arch rib centreline height above the tie centre (parabola)."""
    return -2.0 + 4 * RISE * u * (SPAN - u) / SPAN ** 2


def rib_slope(u):
    return 4 * RISE * (SPAN - 2 * u) / SPAN ** 2


# ----------------------------------------------------------------------------
# Arch side panel, built in PRINT coordinates: x = along span (u), y = elevation, z = thickness.
# z = 0 is the inner (track-side) face; hangers are flush with it.
# ----------------------------------------------------------------------------
def strip(p0, p1, w, z0, z1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    return prism([(p0[0] + nx, p0[1] + ny), (p1[0] + nx, p1[1] + ny),
                  (p1[0] - nx, p1[1] - ny), (p0[0] - nx, p0[1] - ny)], "z", z0, z1)


def arch_panel(coll):
    n = 80
    outer, inner = [], []
    for i in range(n + 1):
        u = -6 + (SPAN + 12) * i / n
        c, s = rib_c(u), rib_slope(u)
        L = math.hypot(1, s)
        nx, ny = -s / L, 1 / L
        h = RIB_D / 2
        outer.append((u + nx * h, c + ny * h))
        inner.append((u - nx * h, c - ny * h))
    rib = prism(outer + inner[::-1], "z", 0, PANEL_T)
    adds = [box(-6, TIE_Z0, 0, SPAN + 6, TIE_Z1, PANEL_T), rib]
    # end knuckles where the rib meets the tie
    for u0, u1 in ((-6, 22), (SPAN - 22, SPAN + 6)):
        adds.append(prism([(u0, TIE_Z1 - 1), (u1, TIE_Z1 - 1), (u0 if u0 < 0 else u1, TIE_Z1 + 14)],
                          "z", 0, PANEL_T))
    # network hangers: two families of inclined hangers crossing each other
    u = 15.0
    while u < SPAN - 14:
        for d in (HANGER_REACH, -HANGER_REACH):
            ut = u + d
            if 12 < ut < SPAN - 12:
                top = rib_c(ut) - RIB_D / 2 + 1.0
                if top - TIE_Z1 > 12:
                    adds.append(strip((u, TIE_Z1 - 1.0), (ut, top), HANGER_W, 0, HANGER_T))
        u += HANGER_STEP
    # rivet-line detail on the tie (shallow grooves on the outer face)
    cuts = [box(-7, TIE_Z0 + 2.0, PANEL_T - 0.3, SPAN + 7, TIE_Z0 + 2.4, PANEL_T + 1),
            box(-7, TIE_Z1 - 2.4, PANEL_T - 0.3, SPAN + 7, TIE_Z1 - 2.0, PANEL_T + 1)]
    cuts.append(box(-50, TIE_Z0 - 50, -1, SPAN + 50, TIE_Z0, PANEL_T + 1))        # trim below tie
    return solid("arch_panel_full", adds, cuts, coll, "steel")


def split_panel(full, coll):
    parts = {}
    third = SPAN / 3
    for name, (a, b) in {"arch_rib_end": (-20, third), "arch_rib_mid": (third, 2 * third)}.items():
        me = full.data.copy()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        _boolean(ob, "INTERSECT", [box(a, -50, -1, b, 400, PANEL_T + 1)])
        parts[name] = ob
    return parts


# ----------------------------------------------------------------------------
# Other printable parts (built in MODULE coordinates of one arch module)
# ----------------------------------------------------------------------------
def pier_piece(coll, name, x0, x1, pedestal=True):
    """Hammerhead pier, profile in (y,z) extruded over x0..x1.
    pier_face: x 0..4 (glued on the 5 mm ply pier core).  pier_full: free-standing approach pier."""
    y0, y1 = YC - HALF_IN - 8, YC + HALF_IN + 8           # cap 14..120
    s0, s1 = YC - 30, YC + 30                               # shaft 37..97
    flare = (s0 - y0)
    prof = [(s0, BASE_TOP_Z), (s1, BASE_TOP_Z), (s1, CAP_Z - 6 - flare), (y1, CAP_Z - 6),
            (y1, CAP_Z), (y0, CAP_Z), (y0, CAP_Z - 6), (s0, CAP_Z - 6 - flare)]
    adds = [prism(prof, "x", x0, x1)]
    for yy in (YC - HALF_IN - 3, YC + HALF_IN):            # bearings under the ties
        adds.append(box(x0 + 0.5, yy, CAP_Z, x1 - 0.5, yy + 3, CAP_Z + 2))
    if pedestal:                                            # seat for the aluminium deck bar
        adds.append(box(x0 + 0.5, YC - 11, CAP_Z, x1 - 0.5, YC + 11, -DECK_T - 3.2))
    cuts = []
    z = WATER_Z + 6
    while z < CAP_Z - 8 - flare:                           # formwork lines
        cuts.append(box(x1 - 0.3, s0 - 1, z, x1 + 1, s1 + 1, z + 0.3))
        cuts.append(box(x0 - 1, s0 - 1, z, x0 + 0.3, s1 + 1, z + 0.3))
        z += 7
    return solid(name, adds, cuts, coll, "concrete2")


def abutment_seat(coll):
    """Glued to the abutment plate face; carries the first approach span."""
    return solid("abutment_seat", [box(0, YC - 27, CAP_Z - 6, 10, YC + 27, CAP_Z)], [], coll, "concrete2")


def arch_deck(coll, length):
    y0, y1 = YC - HALF_IN + 0.2, YC + HALF_IN - 0.2
    adds = [box(0, y0, -DECK_T, length, y1, 0)]
    for yy in (y0, y1 - 6):                                # walkway curbs
        adds.append(box(0, yy, 0, length, yy + 6, 1.2))
    x = 6.0
    while x < length - 2:                                  # floor beams
        adds.append(box(x - 1, y0, FLOOR_Z, x + 1, y1, -DECK_T + 0.1))
        x += 25.0
    adds.append(box(0, y0, FLOOR_Z, length, y0 + 2, -DECK_T + 0.1))     # edge stringers
    adds.append(box(0, y1 - 2, FLOOR_Z, length, y1, -DECK_T + 0.1))
    cuts = [box(-1, YC - BAR_W / 2, FLOOR_Z - 1, length + 1, YC + BAR_W / 2, -DECK_T)]
    return solid("arch_deck", adds, cuts, coll, "concrete2")


def arch_strut(coll):
    L = 2 * HALF_IN
    adds = [box(0, 0, 0, L, 5, 2.5), box(0, 0, 0, 4, 5, 4), box(L - 4, 0, 0, L, 5, 4)]
    for k in range(1, 6):                                   # lightening detail
        adds.append(box(L * k / 6 - 0.5, 0, 0, L * k / 6 + 0.5, 5, 3.2))
    return solid("arch_strut", adds, [], coll, "steel")


def splice(coll, name, w, h):
    return solid(name, [box(0, 0, 0, w, h, 0.8)], [], coll, "steel")


def approach_span(coll, length):
    y0, y1 = YC - HALF_IN, YC + HALF_IN
    prof = [(y0, 0), (y1, 0), (y1, -DECK_T), (y1 - 12, -DECK_T), (y1 - 20, CAP_Z),
            (y0 + 20, CAP_Z), (y0 + 12, -DECK_T), (y0, -DECK_T)]
    adds = [prism(prof, "x", 0, length)]
    for yy in (y0, y1 - 5):
        adds.append(box(0, yy, 0, length, yy + 5, 1.2))   # parapet curbs
    return solid("approach_span", adds, [], coll, "concrete2")


# ----------------------------------------------------------------------------
# Scene helpers
# ----------------------------------------------------------------------------
def inst(src, coll, mat_world, name=None):
    o = src.copy()
    o.name = name or src.name + "_inst"
    o.matrix_world = mat_world
    coll.objects.link(o)
    return o


def export_transformed(obj, path, M):
    me = obj.data.copy()
    me.transform(M)
    if M.determinant() < 0:          # mirrored part: keep normals pointing outwards
        me.flip_normals()
    # drop to the bed
    zmin = min(v.co.z for v in me.vertices)
    me.transform(Matrix.Translation((0, 0, -zmin)))
    tmp = bpy.data.objects.new(obj.name + "_print", me)
    bpy.context.scene.collection.objects.link(tmp)
    tc.export_stl(tmp, path)
    dims = tuple(round(v, 1) for v in tmp.dimensions)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return dims


def track(coll, ox):
    for yc in (tc.FRONT_BALLAST_EDGE + tc.BALLAST_W / 2,
               tc.FRONT_BALLAST_EDGE + tc.BALLAST_W / 2 + tc.TRACK_SPACING):
        x = -1.0
        for L in tc.TRACK_PIECES:
            prof = [(yc - tc.BALLAST_W / 2, 0), (yc + tc.BALLAST_W / 2, 0),
                    (yc + 9, tc.UNITRACK_H - 1.7), (yc - 9, tc.UNITRACK_H - 1.7)]
            mesh_obj("track", prism(prof, "x", ox + x + 0.2, ox + x + L - 0.2), coll, "ballast")
            for r in (-4.5, 4.5):
                mesh_obj("rail", box(ox + x, yc + r - 0.4, tc.UNITRACK_H - 1.7, ox + x + L, yc + r + 0.4,
                                     tc.UNITRACK_H), coll, "rail")
            x += L


def river_frame(coll, ox, kind):
    """The laser-cut ply box (portal_laser.py) + water / marsh scenery (render only).
    kind: 'a' arch (river), 'v' viaduct (marsh), 't' transition (marsh + embankment)."""
    import portal_laser as pl
    D = DEPTH
    panels = pl.transition_module() if kind == "t" else pl.arch_module()
    pl.to_blender(panels, coll, ox, -pl.TOP)
    wz0 = -pl.TOP + PLY
    if kind == "a":
        mesh_obj("water", box(ox + PLY, PLY, wz0, ox + MW - PLY, D - PLY, WATER_Z), coll, "water")
        mesh_obj("bank", box(ox + PLY, pl.BACK_Y0 - 30, WATER_Z, ox + MW - PLY, D - PLY, WATER_Z + 6),
                 coll, "marsh")
        return
    x0 = TR_TOP_X if kind == "t" else PLY
    mesh_obj("marsh", box(ox + x0, PLY, wz0, ox + MW - PLY, D - PLY, WATER_Z + 2), coll, "marsh")
    mesh_obj("creek", box(ox + 330, PLY, WATER_Z - 0.5, ox + 372, D - PLY, WATER_Z + 2.3), coll, "water")
    if kind == "t":                     # carved-foam slopes down from the track-level ground
        prof = [(ox + TR_TOP_X, WATER_Z + 2), (ox + TR_TOP_X + 60, WATER_Z + 2), (ox + TR_TOP_X, -PLY - 0.5)]
        mesh_obj("foam_slope_front", prism(prof, "y", PLY, 14), coll, "mud")
        mesh_obj("foam_slope_back", prism(prof, "y", 120, D - PLY), coll, "mud")
        mesh_obj("ground_cover", box(ox + PLY, PLY, 0.0, ox + TR_TOP_X, D - PLY, 0.5), coll, "marsh")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def run(render=True):
    if bpy.data.collections.get("PORTAL"):
        for o in list(bpy.data.collections["PORTAL"].all_objects):
            bpy.data.objects.remove(o)
    if bpy.app.background:
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"

    out = os.path.join(tc.out_dir(), "portal_bridge")
    stl = os.path.join(out, "stl")
    os.makedirs(stl, exist_ok=True)
    for f in os.listdir(stl):
        if f.endswith(".stl"):
            os.remove(os.path.join(stl, f))

    root = collection("PORTAL")
    lib = collection("Portal_Print_Parts", root)
    scene_c = collection("Portal_Modules", root)

    full = arch_panel(lib)
    segs = split_panel(full, lib)
    pier = pier_piece(lib, "pier_face", PLY, X0)
    pier_full = pier_piece(lib, "pier_full", -9.0, 9.0)
    seat = abutment_seat(lib)
    deck_len = MW / 3
    deck = arch_deck(lib, deck_len)
    strut = arch_strut(lib)
    sp_tie = splice(lib, "splice_tie", 24, 14)
    sp_rib = splice(lib, "splice_rib", 18, RIB_D)
    span_len = SPAN_PITCH - 0.3
    appr = approach_span(lib, span_len)

    # panel print coords -> module coords (front side): (x,y,z) -> (x+X0, YC-HALF_IN - z, y)
    T_front = Matrix.Translation((X0, YC - HALF_IN, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X")
    R_back = Matrix.Translation((MW / 2, YC, 0)) @ Matrix.Rotation(math.pi, 4, "Z") \
        @ Matrix.Translation((-MW / 2, -YC, 0))
    Mirror_u = Matrix.Translation((SPAN, 0, 0)) @ Matrix.Scale(-1, 4, (1, 0, 0))

    strut_us = [u for u in [SPAN * k / 8 for k in range(1, 8)] if rib_c(u) - RIB_D / 2 > 70]

    def viaduct(mc, ox, first_span_x, n_spans, mid_piers):
        for k in range(n_spans):
            inst(appr, mc, Matrix.Translation((ox + first_span_x + k * SPAN_PITCH + 0.15, 0, 0)))
        for xp in mid_piers:
            inst(pier_full, mc, Matrix.Translation((ox + xp, 0, 0)))

    MIRROR = Matrix.Translation((MW, 0, 0)) @ Matrix.Scale(-1, 4, (1, 0, 0))
    for m, (mname, kind) in enumerate(MODULES):
        ox = m * (MW + 2)
        mc = collection("Module_%d_%s" % (m + 1, mname), scene_c)
        if kind in ("tw", "te"):
            # build the west version at the origin, then mirror it for the east end
            river_frame(mc, 0.0, "t")
            track(mc, 0.0)
            viaduct(mc, 0.0, TR_ABUT_FACE, 2, [TR_ABUT_FACE + SPAN_PITCH])
            inst(pier, mc, MIRROR)
            inst(seat, mc, Matrix.Translation((TR_ABUT_FACE, 0, 0)))
            Mm = Matrix.Translation((ox, 0, 0)) @ (MIRROR if kind == "te" else Matrix.Identity(4))
            for o in mc.objects:
                o.matrix_world = Mm @ o.matrix_world
            continue
        river_frame(mc, ox, kind)
        track(mc, ox)
        inst(pier, mc, Matrix.Translation((ox, 0, 0)))
        inst(pier, mc, Matrix.Translation((ox + MW, 0, 0)) @ Matrix.Scale(-1, 4, (1, 0, 0)))
        if kind == "v":
            viaduct(mc, ox, 0.0, 3, [SPAN_PITCH, 2 * SPAN_PITCH])
            continue
        O = Matrix.Translation((ox, 0, 0))
        for side in ("front", "back"):
            B = R_back if side == "back" else Matrix.Identity(4)
            inst(segs["arch_rib_end"], mc, O @ B @ T_front)
            inst(segs["arch_rib_mid"], mc, O @ B @ T_front)
            inst(segs["arch_rib_end"], mc, O @ B @ T_front @ Mirror_u)
        for k in range(3):
            inst(deck, mc, Matrix.Translation((ox + k * deck_len, 0, 0)))
        for u in strut_us:
            c = rib_c(u)
            inst(strut, mc, Matrix.Translation((ox + X0 + u - 2.5, YC - HALF_IN, c - 1.25))
                 @ Matrix.Rotation(math.pi / 2, 4, "Z") @ Matrix.Translation((0, -5, 0)))
        mesh_obj("alu_bar", box(ox + 2, YC - 10, -DECK_T - 3, ox + MW - 2, YC + 10, -DECK_T), mc, "rail")

    # ---- stand-in train for scale (render only)
    tr = collection("Train_render_only", scene_c)
    yc = tc.FRONT_BALLAST_EDGE + tc.BALLAST_W / 2
    for i in range(8):
        x = 260 + i * 166
        mesh_obj("car", box(x, yc - 9, tc.UNITRACK_H + 1.5, x + 162, yc + 9, tc.UNITRACK_H + 25), tr, "train")

    # ---- library positions + exports
    rows = []
    n_arch = N_ARCH_MODULES

    def ex(obj, M, qty, name=None):
        dims = export_transformed(obj, os.path.join(stl, (name or obj.name) + ".stl"), M)
        rows.append(((name or obj.name), qty) + dims)

    I = Matrix.Identity(4)
    ex(segs["arch_rib_end"], I, 2 * n_arch, "arch_rib_end_L")
    ex(segs["arch_rib_end"], Mirror_u, 2 * n_arch, "arch_rib_end_R")
    ex(segs["arch_rib_mid"], I, 2 * n_arch)
    ex(sp_tie, I, 4 * n_arch)
    ex(sp_rib, I, 4 * n_arch)
    ex(strut, I, len(strut_us) * n_arch)
    ex(deck, Matrix.Rotation(math.pi, 4, "X"), 3 * n_arch, "arch_deck_print_upside_down")
    ex(pier, Matrix.Rotation(-math.pi / 2, 4, "Y"), 2 * n_arch + 2 + 2, "pier_face_4mm_print_flat")
    ex(pier_full, Matrix.Rotation(-math.pi / 2, 4, "Y"), 2 + 2, "pier_full_viaduct_print_flat")
    ex(seat, I, 2, "abutment_seat")
    ex(appr, Matrix.Rotation(-math.pi / 2, 4, "Y"), 3 + 2 * 2, "viaduct_span_print_on_end")
    with open(os.path.join(out, "portal_bridge_parts.csv"), "w") as fh:
        fh.write("part,qty_for_set,x_mm,y_mm,z_mm\n")
        for r in rows:
            fh.write(",".join(str(v) for v in r) + "\n")
    bpy.data.objects.remove(full)

    # library layout for the parts render
    x = 0
    for ob in (segs["arch_rib_end"], segs["arch_rib_mid"], deck, pier, pier_full, appr, seat, strut, sp_tie, sp_rib):
        xs = [v.co.x for v in ob.data.vertices]
        ys = [v.co.y for v in ob.data.vertices]
        zs = [v.co.z for v in ob.data.vertices]
        ob.location = (x - min(xs), -700 - min(ys), -min(zs))
        x += max(xs) - min(xs) + 25

    # ---- render setup
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy, sun.angle = 4.0, math.radians(4)
    so = bpy.data.objects.new("Sun", sun)
    root.objects.link(so)
    so.rotation_euler = (math.radians(50), math.radians(8), math.radians(-35))
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*tc.COLORS["sky"], 1)
    bg.inputs[1].default_value = 0.8
    wm = material("water").node_tree.nodes.get("Principled BSDF")
    wm.inputs["Roughness"].default_value = 0.08
    mesh_obj("table", box(-600, -1400, -tc.MODULE_TOP_Z - 20, 3200, 900, -tc.MODULE_TOP_Z), root, "table")

    def cam(name, loc, target, lens):
        c = bpy.data.cameras.new(name)
        c.lens, c.clip_start, c.clip_end = lens, 5, 30000
        ob = bpy.data.objects.new(name, c)
        root.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    total = len(MODULES) * (MW + 2)
    cams = {
        "overview": cam("PB_Overview", (total * 0.06, -1250, 820), (total * 0.52, 120, -10), 24),
        "arch": cam("PB_Arch", (MW * 2.5 + 5 + 240, -230, -45), (MW * 2.5 + 5, YC, 40), 22),
        "transition": cam("PB_Transition", (430, -300, 230), (150, 110, -25), 24),
        "parts": cam("PB_Parts", (x / 2, -1650, 600), (x / 2, -640, 20), 30),
    }
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "portal_bridge.blend"))
    if render:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 48
        sc.cycles.use_denoising = True
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900
        for name, cm in cams.items():
            lib.hide_render = name != "parts"
            scene_c.hide_render = name == "parts"
            sc.camera = cm
            sc.render.filepath = os.path.join(out, "render_portal_%s.png" % name)
            bpy.ops.render.render(write_still=True)
        lib.hide_render, scene_c.hide_render = True, False
    print("Portal bridge: wrote STLs to", stl)


if __name__ == "__main__":
    run(render="--no-render" not in sys.argv)
