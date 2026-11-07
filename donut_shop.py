"""
N-scale (1:160) modern donut & coffee shop with a drive-thru, styled after the current
single-storey Dunkin' store design: flat roof behind a parapet, a taller entry tower
with the sign, a wide glass storefront under a metal canopy, and a drive-thru window
on the side. Generated in Blender, like the rest of this repo.

The sign text is plain raised lettering in Blender's built-in font (set SIGN_TEXT).
The real logo, colours and typeface are not modelled: use a decal for an exact sign,
or set SIGN_TEXT = "" for blank sign panels.

Printable parts (STL)
  * donut_shell           : building walls, open bottom, windows cut through for LEDs (print upright)
  * donut_roof            : drop-in roof with rooftop units and a hatch
  * donut_site_base       : the lot: parking, drive-thru lane, curbs and sidewalks (print flat)
  * donut_pylon_sign      : roadside pylon sign (print flat, on its back)
  * donut_menu_board      : drive-thru menu board (print upright)

Run: blender -b -P donut_shop.py   |   python donut_shop.py [--no-render]   |   Blender Scripting tab
Needs ttrak_city.py in the same folder (shared helpers). Output: ttrak_output/donut_shop/
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
import bmesh
from mathutils import Matrix, Vector
import ttrak_city as tc
from ttrak_city import box, prism, cylinder, mesh_obj, solid, collection

# ----------------------------------------------------------------------------
# PARAMETERS (mm, 1:160)
# ----------------------------------------------------------------------------
SIGN_TEXT = "DUNKIN'"  # raised letters on the tower and pylon sign; "" = blank decal panels
W = 110.0              # building frontage (17.6 m)
D = 70.0               # building depth (11.2 m)
WALL = 1.6
CLEAR = tc.CLEAR
ROOF_T = 1.2
ROOF_Z = 28.0          # top of the drop-in roof (4.5 m)
TOP = 32.0             # parapet top (5.1 m)
TOWER_X = (6.0, 38.0)  # entry tower, left end of the front
TOWER_TOP = 42.0       # 6.7 m
TOWER_Y1 = 10.0        # tower back face (an inside wall carries it)
DOOR_H = 13.5          # 2.15 m
SF_Z = (3.0, 18.0)     # storefront glass sill / head
DT_Y = (38.0, 50.0)    # drive-thru window along the right wall
SITE_W, SITE_D = 175.0, 140.0
SITE_T = 2.0           # asphalt thickness
PAD_T = 1.0            # sidewalk / building pad above the asphalt
BX, BY = 18.0, 38.0    # building front-left corner on the site
LANE_W = 22.0          # drive-thru lane (3.5 m)
PYLON_X = SITE_W - 18.0   # pylon sign socket (front-right corner of the lot)
P_SOCKET = 2.4         # pylon tenon length into the base

tc.COLORS.update({
    "shop_wall": (0.90, 0.86, 0.80), "shop_orange": (0.95, 0.42, 0.10), "shop_pink": (0.88, 0.25, 0.50),
    "shop_brown": (0.30, 0.18, 0.12), "glass_dark": (0.08, 0.12, 0.16), "asphalt": (0.16, 0.16, 0.16),
    "concrete": (0.70, 0.70, 0.68), "stripe": (0.92, 0.92, 0.90), "sky": (0.6, 0.7, 0.85),
})


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def text_shape(text, size, depth, x0, x1, z0, z1, y_face, axis="front"):
    """Raised text as a (verts, faces) shape, centred in the box x0..x1 / z0..z1.
    axis='front': on a wall face at y=y_face facing -y (letters stand up in z).
    axis='top'  : on a flat face at z=y_face facing +z (letters lie in x/y; x0..x1, z0..z1 = x/y range)."""
    cu = bpy.data.curves.new("_txt", "FONT")
    cu.body = text
    cu.size = size
    cu.extrude = depth / 2
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.resolution_u = 4
    ob = bpy.data.objects.new("_txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    # fit to the panel (shrink if needed)
    s = min(1.0, (x1 - x0) / max(1e-6, max(xs) - min(xs)), (z1 - z0) / max(1e-6, max(ys) - min(ys)))
    cx0, cy0 = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    verts = []
    for v in me.vertices:
        tx, ty, tz = (v.co.x - cx0) * s, (v.co.y - cy0) * s, v.co.z + depth / 2   # tz: 0..depth
        if axis == "front":
            verts.append(((x0 + x1) / 2 + tx, y_face - tz + 0.2, (z0 + z1) / 2 + ty))
        else:
            verts.append(((x0 + x1) / 2 + tx, (z0 + z1) / 2 + ty, y_face + tz - 0.2))
    faces = [tuple(p.vertices) for p in me.polygons]
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)
    return verts, faces


def wedge_x(x0, x1, y_wall, out, z_top, t=1.0):
    """Canopy along a wall facing -y: 45-degree underside, so it prints with no supports."""
    return prism([(y_wall + 0.5, z_top - t - out), (y_wall - out, z_top - t), (y_wall - out, z_top),
                  (y_wall + 0.5, z_top)], "x", x0, x1)


def wedge_y(y0, y1, x_wall, out, z_top, t=1.0):
    """Same canopy on a wall facing +x."""
    return prism([(x_wall - 0.5, z_top - t - out), (x_wall + out, z_top - t), (x_wall + out, z_top),
                  (x_wall - 0.5, z_top)], "y", y0, y1)


def glazing(cuts, adds2, face, a0, a1, z0, z1, pitch, transom=None):
    """Cut-through window opening with mullions. face: 'front' | 'back' | 'left' | 'right'."""
    n = max(1, round((a1 - a0) / pitch))
    step = (a1 - a0) / n
    def B(a, b, za, zb, o0, o1):
        if face == "front":
            return box(a, o0, za, b, o1, zb)
        if face == "back":
            return box(a, D - o1, za, b, D - o0, zb)
        if face == "left":
            return box(o0, a, za, o1, b, zb)
        return box(W - o1, a, za, W - o0, b, zb)
    cuts.append(B(a0, a1, z0, z1, -1, WALL + 1))
    for i in range(n + 1):
        a = a0 + i * step
        adds2.append(B(a - 0.35, a + 0.35, z0 - 0.3, z1 + 0.3, 0.2, 1.0))
    if transom:
        adds2.append(B(a0, a1, transom - 0.3, transom + 0.3, 0.2, 1.0))
    adds2.append(B(a0 - 0.6, a1 + 0.6, z0 - 0.6, z0, -0.5, 1.0))     # sill


# ----------------------------------------------------------------------------
# Building
# ----------------------------------------------------------------------------
def shell(coll):
    tx0, tx1 = TOWER_X
    adds = [box(0, 0, 0, W, WALL, TOP), box(0, D - WALL, 0, W, D, TOP),
            box(0, 0, 0, WALL, D, TOP), box(W - WALL, 0, 0, W, D, TOP)]
    # entry tower: projects 2 mm, rises to TOWER_TOP, carried at the back by an inside wall
    adds.append(box(tx0, -2.0, 0, tx1, WALL, TOWER_TOP))
    # coping and coffee-brown accent band all round (front, sides, back)
    adds.append(box(-0.4, -0.4, TOP - 1.0, W + 0.4, D + 0.4, TOP))
    adds.append(box(-0.4, -0.4, TOP - 5.0, W + 0.4, D + 0.4, TOP - 2.0))
    # base / wainscot (stone or brick)
    adds.append(box(-0.5, -0.5, 0, W + 0.5, D + 0.5, 2.6))
    adds.append(box(tx0 - 0.5, -2.5, 0, tx1 + 0.5, 0, 2.6))

    cuts, adds2 = [], []
    # hollow out the cap/band/base rings
    cuts.append(box(WALL, WALL, -1, W - WALL, D - WALL, TOP + 1))
    # tower block above the roof line (an 8 mm bridge from the front wall to the inside wall),
    # the inside wall with a 22 mm bridged opening into the dining room, and the cap
    adds2.append(box(tx0, WALL - 0.1, ROOF_Z, tx1, TOWER_Y1 + WALL, TOWER_TOP))
    adds2.append(box(tx0, TOWER_Y1, 0, tx0 + 4, TOWER_Y1 + WALL, ROOF_Z + 0.1))
    adds2.append(box(tx1 - 4, TOWER_Y1, 0, tx1, TOWER_Y1 + WALL, ROOF_Z + 0.1))
    adds2.append(box(tx0 + 3.9, TOWER_Y1, 22, tx1 - 3.9, TOWER_Y1 + WALL, ROOF_Z + 0.1))
    adds2.append(box(tx0 - 0.5, -2.5, TOWER_TOP - 1.2, tx1 + 0.5, TOWER_Y1 + WALL + 0.5, TOWER_TOP))
    # tower: double glass doors with transom, and a sign panel
    door0, door1 = tx0 + 7, tx1 - 7
    cuts.append(box(door0, -3, 0, door1, WALL + 1, DOOR_H + 4))
    for x in (door0, (door0 + door1) / 2, door1):
        adds2.append(box(x - 0.4, -1.4, 0, x + 0.4, -0.6, DOOR_H + 4.3))
    adds2.append(box(door0, -1.4, DOOR_H - 0.3, door1, -0.6, DOOR_H + 0.3))
    adds2.append(box(door0 - 1, -2.6, DOOR_H + 4, door1 + 1, -1.6, DOOR_H + 5))   # door head trim
    adds2.append(wedge_x(tx0 + 2, tx1 - 2, -2.0, 4.0, DOOR_H + 9))               # entry canopy
    sign = (tx0 + 2.5, tx1 - 2.5, ROOF_Z + 0.5, TOWER_TOP - 3.0)
    adds2.append(box(sign[0], -2.8, sign[2], sign[1], -1.9, sign[3]))             # sign panel
    if SIGN_TEXT:
        adds2.append(text_shape(SIGN_TEXT, 6.0, 0.6, sign[0] + 1.5, sign[1] - 1.5,
                                sign[2] + 1.6, sign[3] - 1.6, -2.8))

    # front storefront right of the tower
    glazing(cuts, adds2, "front", tx1 + 4, W - 7, SF_Z[0], SF_Z[1], 9.0, transom=SF_Z[1] - 3.5)
    adds2.append(wedge_x(tx1 + 2, W - 1, 0.0, 4.0, SF_Z[1] + 6.0))              # metal canopy
    adds2.append(box(tx1 + 2, -0.6, SF_Z[1] + 5.9, W - 2, 0.2, TOP - 5.5))        # fascia panel
    # left side: dining-room windows
    glazing(cuts, adds2, "left", 16, 48, SF_Z[0], SF_Z[1], 8.0, transom=SF_Z[1] - 3.5)
    # right side: front windows, drive-thru window and its canopy
    glazing(cuts, adds2, "right", 6, 28, SF_Z[0], SF_Z[1], 7.5, transom=SF_Z[1] - 3.5)
    cuts.append(box(W - WALL - 1, DT_Y[0], 6.5, W + 1, DT_Y[1], 15.5))            # pass-through window
    adds2.append(box(W - 0.2, DT_Y[0] - 1, 5.5, W + 1.4, DT_Y[1] + 1, 6.5))       # counter ledge
    adds2.append(box(W - 0.6, (DT_Y[0] + DT_Y[1]) / 2 - 0.3, 6.5, W + 0.4,
                     (DT_Y[0] + DT_Y[1]) / 2 + 0.3, 15.5))                        # sliding sash
    adds2.append(wedge_y(DT_Y[0] - 6, DT_Y[1] + 6, W, 5.0, 23.0))                 # drive-thru canopy
    adds2.append(box(W - 0.6, DT_Y[0] - 6, 22.9, W + 0.4, DT_Y[1] + 6, TOP - 5.5))  # sign band above
    # back: service door, vents, utility box
    cuts.append(box(80, D - WALL - 1, 0, 88, D + 1, DOOR_H))
    adds2.append(box(79, D - 0.2, DOOR_H, 89, D + 1.0, DOOR_H + 1.0))
    for x in (30, 44):
        adds2.append(box(x, D - 0.2, 20, x + 6, D + 0.8, 24))                     # wall vents
    adds2.append(box(62, D - 0.2, 6, 70, D + 1.2, 16))                            # electrical panel

    # roof support posts (roof rests on them), clear of the windows
    pz = ROOF_Z - ROOF_T
    for (x0, y0) in ((WALL - 0.3, D - WALL - 3), (W - WALL - 3, D - WALL - 3),
                     (W - WALL - 3, WALL - 0.3), (55, D - WALL - 3), (WALL - 0.3, 54)):
        adds2.append(box(x0, y0, 0, x0 + 3.3, y0 + 3.3, pz))
    adds2.append(box(tx1, TOWER_Y1, 0, tx1 + 3, TOWER_Y1 + WALL + 2.5, pz))       # post at tower corner
    for x in (60.0, 96.0):                                                         # hidden floor ties
        adds2.append(box(x, WALL - 0.3, 0, x + 4, D - WALL + 0.3, 1.2))
    return solid("donut_shell", adds, cuts, coll, "shop_wall", adds2)


def roof(coll):
    """Drop-in roof plate with a notch around the tower block."""
    x0, y0 = WALL + CLEAR, WALL + CLEAR
    wi, di = W - 2 * WALL - 2 * CLEAR, D - 2 * WALL - 2 * CLEAR
    T = ROOF_T
    adds = [box(0, 0, 0, wi, di, T)]
    cuts = [box(TOWER_X[0] - CLEAR - x0, -1, -1, TOWER_X[1] + CLEAR - x0, TOWER_Y1 + WALL + CLEAR - y0, T + 1)]
    adds2 = []
    for (ux, uy) in ((58, 30), (78, 40)):                    # rooftop HVAC units
        adds2.append(box(ux, uy, T, ux + 11, uy + 8, T + 4.5))
        adds2.append(cylinder(ux + 5.5, uy + 4, 2.5, T + 4.5, T + 5.0, 16))
    adds2.append(box(20, 45, T, 25, 50, T + 1.6))            # hatch
    adds2.append(box(92, 12, T, 95, 15, T + 3.0))            # exhaust stack
    adds2.append(cylinder(36, 50, 1.2, T, T + 3.5, 12))      # vent pipe
    return solid("donut_roof", adds, cuts, coll, "roof", adds2), (x0, y0, ROOF_Z - T)


# ----------------------------------------------------------------------------
# Site and accessories
# ----------------------------------------------------------------------------
def site_base(coll):
    T, P = SITE_T, SITE_T + PAD_T
    bx1, by1 = BX + W, BY + D
    adds = [box(0, 0, 0, SITE_W, SITE_D, T)]
    # building pad + front and left sidewalks
    adds.append(box(BX - 6, BY - 10, 0, bx1 + 3, by1 + 3, P))
    # drive-thru island (raised curb) separating the lane from the lot edge
    lx0, lx1 = bx1 + 3, bx1 + 3 + LANE_W
    adds.append(box(lx1, BY + 10, 0, lx1 + 3, SITE_D - 3, P))
    adds.append(box(BX + 10, by1 + 3 + LANE_W, 0, lx1 + 3, by1 + 6 + LANE_W, P))
    cuts = []
    # locating pocket for the building shell (0.6 mm)
    cuts.append(box(BX - 0.8, BY - 0.8, P - 0.6, bx1 + 0.8, by1 + 0.8, P + 1))
    cuts.append(box(BX + TOWER_X[0] - 0.8, BY - 2.8, P - 0.6, BX + TOWER_X[1] + 0.8, BY, P + 1))
    # parking stall lines in front (engraved, paint white)
    sx = 4.0
    while sx < BX + W - 10:
        cuts.append(box(sx, 0.0 + 1.5, T - 0.3, sx + 0.5, BY - 12, T + 1))
        sx += 17.0                                                   # 2.7 m stalls
    # drive-thru lane arrows and "stop bar" at the window
    cuts.append(box(lx0 + 2, BY + DT_Y[0] - 3, T - 0.3, lx1 - 2, BY + DT_Y[0] - 2, T + 1))
    for yy in (BY + 70, BY + 25):
        cx = (lx0 + lx1) / 2
        cuts.append(prism([(cx - 3, yy + 4), (cx + 3, yy + 4), (cx, yy - 2)], "z", T - 0.3, T + 1))
        cuts.append(box(cx - 0.8, yy + 4, T - 0.3, cx + 0.8, yy + 10, T + 1))
    # sockets: pylon sign (front-right corner) and menu board (back of the lane)
    adds.append(box(PYLON_X - 4.4, 2, 0, PYLON_X + 7.6, 13.2, P + 1.5))   # planter at the pylon foot
    cuts.append(box(PYLON_X, 6, 0.6, PYLON_X + 3.2, 6 + 3.2, P + 2))     # pylon socket
    mb = (lx1 + 0.4, by1 - 6)
    return solid("donut_site_base", adds, cuts, coll, "asphalt"), mb


def pylon_sign(coll):
    """Pole sign drawn in x/z, 3 mm thick in y. Exported lying on its back (print flat)."""
    th = 3.0
    adds = [box(0, 0, -P_SOCKET, 3.0, th, 44)]                         # pole (tenon into the base)
    adds.append(box(-11.5, 0, 30, 14.5, th, 46))                        # sign cabinet
    adds.append(box(-4, 0, 0, 7, th, 4))                                # pole cover at the base
    adds2 = [box(-10.5, -0.4, 31, 13.5, 0.01, 45)]                      # sign face (decal area)
    if SIGN_TEXT:
        # letters on the front face (y=0 side, facing -y), stand up in z
        adds2.append(text_shape(SIGN_TEXT, 5.0, 0.5, -9.5, 12.5, 32.5, 43.5, -0.4))
    return solid("donut_pylon_sign", adds, [], coll, "shop_orange", adds2)




def menu_board(coll):
    """Drive-thru menu board on two posts, with a speaker post. Prints upright; glue to the island."""
    adds = [box(0, 0, 0, 1.0, 1.0, 8), box(0, 13, 0, 1.0, 14, 8)]
    adds.append(box(-0.2, -0.5, 4, 1.2, 14.5, 13))                      # board (faces -x)
    adds.append(box(-0.2, -1, 13, 1.4, 15, 14))                         # top hood
    adds2 = []
    for i in range(3):                                                   # menu panels
        y0 = 0.3 + i * 4.6
        adds2.append(box(-0.5, y0, 5, -0.1, y0 + 4.0, 12.2))
    adds2.append(box(-0.1, -6, 0, 0.9, -5, 6))                          # speaker post
    adds2.append(box(-0.6, -6.5, 6, 1.2, -4.5, 8.5))
    adds2.append(box(-0.1, -5.5, 0, 0.9, 0.2, 0.8))                     # base rail (keeps it one part)
    return solid("donut_menu_board", adds, [], coll, "shop_brown", adds2)


# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
def reset():
    old = bpy.data.collections.get("DONUT_SHOP")
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
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"


def export_transformed(obj, path, mat):
    me = obj.data.copy()
    me.transform(mat)
    tmp = bpy.data.objects.new(obj.name + "_print", me)
    bpy.context.scene.collection.objects.link(tmp)
    tc.export_stl(tmp, path)
    dims = tuple(round(v, 1) for v in tmp.dimensions)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return dims


def is_manifold(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return bad


def overlay(coll, name, shape, mat):
    """Render-only paint layer (not exported)."""
    return mesh_obj(name, shape, coll, mat)


def run(render=True):
    reset()
    out = os.path.join(tc.out_dir(), "donut_shop")
    stl = os.path.join(out, "stl")
    os.makedirs(stl, exist_ok=True)
    for f in os.listdir(stl):
        if f.endswith(".stl"):
            os.remove(os.path.join(stl, f))

    root = collection("DONUT_SHOP")
    lib = collection("Donut_Print_Parts", root)
    scene = collection("Donut_Site", root)

    sh = shell(lib)
    rf, ro = roof(lib)
    base, mb = site_base(lib)
    py = pylon_sign(lib)
    mn = menu_board(lib)

    # ---- assembled site
    P = SITE_T + PAD_T
    tc.place(base, scene, (0, 0, 0))
    z0 = P - 0.6
    tc.place(sh, scene, (BX, BY, z0))
    tc.place(rf, scene, (BX + ro[0], BY + ro[1], z0 + ro[2]))
    tc.place(py, scene, (PYLON_X + 0.1, 6 + 0.1, 0.6 + P_SOCKET))
    tc.place(mn, scene, (mb[0] + 0.6, mb[1], P))
    # render-only paint: orange/pink accents, brown band, glass, concrete, stripes
    ov = collection("Donut_Paint", scene)
    tx0, tx1 = TOWER_X
    overlay(ov, "p_tower", box(BX + tx0, BY - 2.05, z0 + DOOR_H + 5, BX + tx1, BY - 2.0, z0 + TOWER_TOP - 1.2), "shop_orange")
    overlay(ov, "p_sign", box(BX + tx0 + 2.5, BY - 2.85, z0 + ROOF_Z + 0.5, BX + tx1 - 2.5, BY - 2.82,
                              z0 + TOWER_TOP - 3), "shop_wall")
    overlay(ov, "p_band", box(BX - 0.45, BY - 0.45, z0 + TOP - 5, BX + W + 0.45, BY - 0.42, z0 + TOP - 2), "shop_brown")
    overlay(ov, "p_band_r", box(BX + W + 0.42, BY - 0.4, z0 + TOP - 5, BX + W + 0.45, BY + D, z0 + TOP - 2), "shop_brown")
    overlay(ov, "p_band_l", box(BX - 0.45, BY - 0.4, z0 + TOP - 5, BX - 0.42, BY + D, z0 + TOP - 2), "shop_brown")
    overlay(ov, "p_fascia", box(BX + tx1 + 2, BY - 0.65, z0 + SF_Z[1] + 5.9, BX + W - 2, BY - 0.62, z0 + TOP - 5.5), "shop_pink")
    overlay(ov, "p_dtband", box(BX + W + 0.42, BY + DT_Y[0] - 6, z0 + 23, BX + W + 0.45, BY + DT_Y[1] + 6, z0 + TOP - 6), "shop_orange")
    overlay(ov, "p_glass_f", box(BX + tx1 + 4, BY + 1.05, z0 + SF_Z[0], BX + W - 4, BY + 1.1, z0 + SF_Z[1]), "glass_dark")
    overlay(ov, "p_glass_d", box(BX + tx0 + 7, BY - 1.0, z0, BX + tx1 - 7, BY - 0.95, z0 + DOOR_H + 4), "glass_dark")
    overlay(ov, "p_glass_l", box(BX + 1.05, BY + 16, z0 + SF_Z[0], BX + 1.1, BY + 48, z0 + SF_Z[1]), "glass_dark")
    overlay(ov, "p_glass_r", box(BX + W - 1.1, BY + 6, z0 + SF_Z[0], BX + W - 1.05, BY + 28, z0 + SF_Z[1]), "glass_dark")
    overlay(ov, "p_walk", box(BX - 6, BY - 10, P + 0.001, BX + W + 3, BY - 2.6, P + 0.02), "concrete")
    overlay(ov, "p_island", box(BX + W + 3 + LANE_W, BY + 10, P + 0.001, BX + W + 6 + LANE_W, SITE_D - 3, P + 0.02), "concrete")
    sx = 4.0
    while sx < BX + W - 10:
        overlay(ov, "p_stall", box(sx, 1.5, SITE_T - 0.29, sx + 0.5, BY - 12, SITE_T + 0.005), "stripe")
        sx += 17.0
    overlay(ov, "p_pylon", box(PYLON_X + 0.1 - 10.5, 6.1 - 0.42, 0.6 + P_SOCKET + 31, PYLON_X + 0.1 + 13.5, 6.1 - 0.41,
                               0.6 + P_SOCKET + 45), "shop_wall")
    # a module-front strip of grass and the table for context
    mesh_obj("grass", box(-40, -30, -0.5, SITE_W + 40, SITE_D + 30, 0), scene, "grass")

    # ---- part checks and exports
    parts = [
        (sh, "donut_shell", 1, "upright, open bottom down", Matrix.Identity(4)),
        (rf, "donut_roof", 1, "flat, units up", Matrix.Identity(4)),
        (base, "donut_site_base", 1, "flat", Matrix.Identity(4)),
        (py, "donut_pylon_sign_print_flat", 1, "on its back (lettering up)",
         Matrix.Rotation(-math.pi / 2, 4, "X") @ Matrix.Translation((0, -3.0, 0))),
        (mn, "donut_menu_board", 1, "upright", Matrix.Identity(4)),
    ]
    rows = []
    for ob, fname, q, how, mat in parts:
        bad = is_manifold(ob)
        print("%-28s non-manifold edges: %d" % (ob.name, bad))
        dims = export_transformed(ob, os.path.join(stl, fname + ".stl"), mat)
        rows.append((fname, q, *dims, how))
    with open(os.path.join(out, "donut_shop_parts.csv"), "w") as fh:
        fh.write("part,qty,x_mm,y_mm,z_mm,print\n")
        for r in rows:
            fh.write(",".join(str(v) for v in r) + "\n")

    # parts layout for the parts render
    sh.location = (0, -300, 0)
    rf.location = (W + 20, -300, 0)
    py.location = (2 * W + 50, -300, P_SOCKET)
    mn.location = (2 * W + 80, -300, 0)
    base.location = (0, -300 - SITE_D - 30, 0)

    # ---- render setup (daylight)
    sc = bpy.context.scene
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 4.0
    sun.angle = math.radians(5)
    so = bpy.data.objects.new("Sun", sun)
    root.objects.link(so)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*tc.COLORS["sky"], 1)
    bg.inputs[1].default_value = 0.8
    mesh_obj("table", box(-600, -1200, -20, 1000, 800, -0.5), root, "table")

    def cam(name, loc, target, lens):
        c = bpy.data.cameras.new(name)
        c.lens, c.clip_start, c.clip_end = lens, 2, 20000
        ob = bpy.data.objects.new(name, c)
        root.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    cams = {
        "front": cam("DS_Cam_Front", (60, -130, 75), (95, 70, 18), 30),
        "drivethru": cam("DS_Cam_DriveThru", (300, 10, 90), (120, 85, 15), 35),
        "parts": cam("DS_Cam_Parts", (180, -720, 330), (180, -330, 0), 40),
    }
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "donut_shop.blend"))
    if render:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = int(os.environ.get("DS_SAMPLES", 48))
        sc.cycles.use_denoising = True
        sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
        for name, c in cams.items():
            lib.hide_render = name != "parts"
            scene.hide_render = name == "parts"
            sc.camera = c
            sc.render.filepath = os.path.join(out, "render_donut_%s.png" % name)
            bpy.ops.render.render(write_still=True)
        lib.hide_render, scene.hide_render = True, False
    print("Donut shop: wrote STLs to", stl)


if __name__ == "__main__":
    run(render="--no-render" not in sys.argv)
