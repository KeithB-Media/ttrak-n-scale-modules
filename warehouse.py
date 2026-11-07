"""
N-scale (1:160) modern distribution / fulfillment-center warehouse for T-TRAK,
generated in Blender. Generic design: no logos or trademarks; there's a blank sign
panel and accent band for your own decals.

Selective compression: a real fulfillment center is ~360 x 200 m (2.2 m long in N scale).
This model is a dock-wall section (450 x 140 x 84 mm by default) built from
bed-sized segments that glue together with built-in alignment tongues.

Printable parts (STL)
  * wh_seg_left   : left end, office with curtain-wall glass, entry canopy, sign panel
  * wh_seg_mid    : repeating dock segment (set MID_SEGMENTS for a longer building)
  * wh_seg_right  : right end
  * wh_roof_*     : drop-in roof plates with skylights, HVAC units and roof hatch
  * trailer_53ft  : 53' dry-van trailer (exported upside-down = print orientation)
  * delivery_van  : generic high-roof cargo van
Also builds "Module C" (a T-TRAK double module with truck court and parked trailers) for renders.

Run: blender -b -P warehouse.py   |   python warehouse.py [--no-render]   |   Blender Scripting tab
Needs ttrak_city.py in the same folder (shared helpers).
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
from ttrak_city import box, prism, cylinder, mesh_obj, solid, _boolean, collection, material

# ----------------------------------------------------------------------------
# PARAMETERS (mm, 1:160)
# ----------------------------------------------------------------------------
PANEL = 30.0           # tilt-up panel width (joint grooves; also the dock pitch)
SEG_L = 150.0          # segment length = 5 panels (fits a 250 mm bed)
MID_SEGMENTS = 1       # 0..n repeating dock segments between the ends
DEPTH = 140.0          # building depth (22 m, compressed)
H = 80.0               # roof level (12.8 m clear height)
PARAPET = 4.0
WALL = 1.6
CLEAR = tc.CLEAR
ROOF_T = 1.2
DOCK_Z = 7.5           # dock floor height (1.2 m)
DOOR_W, DOOR_H = 18.0, 20.0     # 2.9 x 3.2 m dock doors
OFFICE_W = 60.0        # office curtain-wall width at the left end
TRAILERS_AT_DOCKS = [1, 2, 4, 6, 7, 8, 10]   # dock indices with a parked trailer (render)

tc.COLORS.update({
    "tiltup": (0.78, 0.78, 0.76), "accent": (0.12, 0.22, 0.38), "glass_dark": (0.08, 0.12, 0.16),
    "trailer": (0.88, 0.88, 0.86), "van": (0.20, 0.30, 0.45), "asphalt": (0.16, 0.16, 0.16),
    "stripe": (0.9, 0.85, 0.3), "sky": (0.6, 0.7, 0.85),
})

TOP = H + PARAPET


# ----------------------------------------------------------------------------
# Building segments
# ----------------------------------------------------------------------------
def dock_centers(L, office):
    first = 2 if office else 0             # office occupies the first 2 panels
    return [PANEL * (i + 0.5) for i in range(first, int(L // PANEL))]


def seg_shell(name, L, has_left, has_right, office, coll):
    D = DEPTH
    adds = [box(0, 0, 0, L, WALL, TOP), box(0, D - WALL, 0, L, D, TOP)]
    if has_left:
        adds.append(box(0, 0, 0, WALL, D, TOP))
    if has_right:
        adds.append(box(L - WALL, 0, 0, L, D, TOP))
    cuts, adds2 = [], []

    # coping, accent band, base
    adds.append(box(0, -0.4, TOP - 1.0, L, 0.5, TOP))
    adds.append(box(0, -0.4, H - 12, L, 0.5, H - 6))                 # accent band (paint)
    adds.append(box(0, D - 0.5, H - 12, L, D + 0.4, H - 6))

    # panel joints: front, back, ends
    for k in range(int(L // PANEL) + 1):
        x = k * PANEL
        for (y0, y1) in ((-1, 0.4), (D - 0.4, D + 1)):
            cuts.append(box(x - 0.25, y0, -1, x + 0.25, y1, TOP + 1))
    for side_x, present in ((0, has_left), (L, has_right)):
        if present:
            for k in range(1, int(D // PANEL) + 1):
                y = k * PANEL
                cuts.append(box(side_x - 1 if side_x == 0 else L - 0.4, y - 0.25, -1,
                                0.4 if side_x == 0 else L + 1, y + 0.25, TOP + 1))
            # man door on each end
            x0, x1 = (-1, 0.6) if side_x == 0 else (L - 0.6, L + 1)
            cuts.append(box(x0, D * 0.7, 0, x1, D * 0.7 + 6, 13))

    # dock doors with seals, bumpers, lights
    for cx in dock_centers(L, office):
        x0, x1 = cx - DOOR_W / 2, cx + DOOR_W / 2
        cuts.append(box(x0, -1, DOCK_Z, x1, 0.8, DOCK_Z + DOOR_H))
        for z in range(1, 6):                                   # roll-up door slats
            zz = DOCK_Z + z * DOOR_H / 6
            adds2.append(box(x0, 0.6, zz - 0.15, x1, 0.9, zz + 0.15))
        adds2.append(box(x0 - 2, -1.2, DOCK_Z - 1.5, x0, 0.5, DOCK_Z + DOOR_H + 2))   # seals
        adds2.append(box(x1, -1.2, DOCK_Z - 1.5, x1 + 2, 0.5, DOCK_Z + DOOR_H + 2))
        adds2.append(box(x0 - 2, -1.2, DOCK_Z + DOOR_H, x1 + 2, 0.5, DOCK_Z + DOOR_H + 2))
        adds2.append(box(cx - 7, -1.0, DOCK_Z - 3, cx - 5, 0.5, DOCK_Z - 0.5))          # bumpers
        adds2.append(box(cx + 5, -1.0, DOCK_Z - 3, cx + 7, 0.5, DOCK_Z - 0.5))
        adds2.append(prism([(0.5, DOCK_Z + DOOR_H + 5), (-1.5, DOCK_Z + DOOR_H + 3),
                            (0.5, DOCK_Z + DOOR_H + 2.5)], "x", cx + DOOR_W / 2 + 3, cx + DOOR_W / 2 + 5))

    # clerestory ribbon windows (back wall too)
    for k in range(int(L // PANEL)):
        x0 = k * PANEL
        if office and k < 2:
            continue
        cuts.append(box(x0 + 3, -1, H - 22, x0 + PANEL - 3, 0.6, H - 17))
        cuts.append(box(x0 + 3, D - 0.6, H - 22, x0 + PANEL - 3, D + 1, H - 17))

    if office:
        # curtain wall glazing (recessed), mullions + transoms
        gx0, gx1, gz0, gz1 = 3, OFFICE_W - 3, 1.5, 52
        cuts.append(box(gx0, -1, gz0, gx1, 0.9, gz1))
        x = gx0
        while x <= gx1 + 0.01:
            adds2.append(box(x - 0.3, 0.0, gz0, x + 0.3, 1.0, gz1))
            x += (gx1 - gx0) / 9
        for z in (17.5, 35.0):
            adds2.append(box(gx0, 0.0, z - 0.3, gx1, 1.0, z + 0.3))
        # entry canopy on two columns (short bridges)
        adds2.append(box(14, -11, 0, 15.4, -9.6, 19))
        adds2.append(box(OFFICE_W - 15.4, -11, 0, OFFICE_W - 14, -9.6, 19))
        adds2.append(box(13, -11.5, 19, OFFICE_W - 13, 0.5, 20.4))
        # blank sign panel for your own decal
        adds2.append(box(6, -0.8, H - 4.5 - 20, OFFICE_W - 6, 0.5, H - 4.5 - 9))

    # roof support posts + alignment tongues into the next segment
    pz = H - ROOF_T
    for x in ([12, L / 2 - 1.5, L - 15]):
        for (y0, y1) in ((WALL - 0.3, WALL + 3), (D - WALL - 3, D - WALL + 0.3)):
            adds2.append(box(x, y0, 0, x + 3, y1, pz))
    for x in (20, L - 26):                 # hidden floor ties keep the walls square
        adds2.append(box(x, WALL - 0.3, 0, x + 4, D - WALL + 0.3, 1.2))
    if not has_right:
        for (ya, yb, yc, yd) in ((WALL - 0.3, WALL + 1.2, WALL + 0.1, WALL + 1.3),
                                 (D - WALL - 1.2, D - WALL + 0.3, D - WALL - 1.3, D - WALL - 0.1)):
            adds2.append(box(L - 6, ya, 6, L + 0.01, yb, TOP - 12))
            adds2.append(box(L, yc, 6, L + 6, yd, TOP - 12))
    return solid(name, adds, cuts, coll, "tiltup", adds2)


def seg_roof(name, L, has_left, has_right, coll):
    D = DEPTH
    x0 = WALL + CLEAR if has_left else 0.1
    x1 = L - WALL - CLEAR if has_right else L - 0.1
    y0, y1 = WALL + CLEAR, D - WALL - CLEAR
    adds = [box(0, 0, 0, x1 - x0, y1 - y0, ROOF_T)]
    T = ROOF_T
    w = x1 - x0
    for i in range(int(w // 30)):                       # skylights
        for j in range(3):
            sx, sy = 11 + i * 30, 20 + j * 40
            if sx + 5 < w and sy + 12 < y1 - y0:
                adds.append(box(sx, sy, T, sx + 5, sy + 12, T + 1.2))
    adds.append(box(w * 0.3, (y1 - y0) * 0.45, T, w * 0.3 + 9, (y1 - y0) * 0.45 + 13, T + 5.5))   # RTU
    adds.append(box(w * 0.7, (y1 - y0) * 0.3, T, w * 0.7 + 9, (y1 - y0) * 0.3 + 13, T + 5.5))
    adds.append(box(w * 0.5, (y1 - y0) * 0.8, T, w * 0.5 + 4, (y1 - y0) * 0.8 + 4, T + 2))         # hatch
    ob = solid(name, adds, [], coll, "roof")
    return ob, (x0, y0, H - ROOF_T)


# ----------------------------------------------------------------------------
# Vehicles
# ----------------------------------------------------------------------------
def wheel_y(cx, cz, r, y0, y1, seg=20):
    pts = [(cx + r * math.cos(2 * math.pi * i / seg), cz + r * math.sin(2 * math.pi * i / seg))
           for i in range(seg)]
    return prism(pts, "y", y0, y1)


def trailer(coll):
    """53' dry van: 101 x 16 x 25.6 mm. Local x=0 is the rear (dock) end."""
    L, Wd, z0, z1 = 101.0, 16.0, 7.8, 25.6
    adds = [box(0, 0, z0, L, Wd, z1)]
    cuts = [box(-1, Wd / 2 - 0.2, z0 + 0.8, 0.4, Wd / 2 + 0.2, z1 - 0.8)]       # rear door split
    for x in [3 + 4.8 * i for i in range(21)]:                                  # side posts
        adds.append(box(x, -0.3, z0, x + 0.6, 0.2, z1))
        adds.append(box(x, Wd - 0.2, z0, x + 0.6, Wd + 0.3, z1))
    for y in (2.5, 6.0, 10.0, 13.5):                                            # door hinges / bars
        adds.append(box(-0.4, y, z0 + 1, 0.2, y + 0.6, z1 - 1))
    adds.append(box(1, 3, 4.6, 2.5, 4, z0))                                     # rear bumper
    adds.append(box(1, 12, 4.6, 2.5, 13, z0))
    adds.append(box(0.6, 0.8, 3.6, 2.6, Wd - 0.8, 4.8))
    adds.append(box(6, 3, 5.6, 26, 13, z0))                                     # slider bogie
    for cx in (10.5, 18.0):
        adds.append(wheel_y(cx, 3.1, 3.1, 0.4, 5.2))
        adds.append(wheel_y(cx, 3.1, 3.1, 10.8, 15.6))
        adds.append(wheel_y(cx, 3.1, 1.0, 5.0, 11.0, 12))
    for y in (2.6, 12.2):                                                       # landing gear
        adds.append(box(70, y, 1.0, 71.4, y + 1.2, z0))
        adds.append(box(69.4, y - 0.3, 0, 72, y + 1.5, 1.0))
    return solid("trailer_53ft", adds, cuts, coll, "trailer")


def van(coll):
    """Generic high-roof cargo van: 37 x 12.5 x 16.5 mm. Front at +x."""
    prof = [(0, 1.6), (37, 1.6), (37, 7.6), (33.5, 9.8), (29, 16.5), (0.3, 16.5), (0, 16.0)]
    adds = [prism(prof, "y", 0.4, 12.1)]
    cuts = []
    for y0, y1 in ((-1, 0.7), (11.8, 13.5)):
        cuts.append(box(25.5, y0, 10.2, 30.5, y1, 14.6))          # cab side windows
        cuts.append(box(27, y0, 2.5, 27.4, y1, 10))               # cab door line
        cuts.append(box(14, y0, 2.5, 14.4, y1, 15))               # sliding door line
    cuts.append(prism([(33.7, 10.2), (36.5, 8.0), (36.5, 8.6), (33.7, 10.9)], "y", 1.2, 11.3))
    cuts.append(prism([(30.0, 15.6), (33.2, 10.6), (34.0, 10.6), (30.8, 15.6)], "y", 1.2, 11.3))
    cuts.append(box(-1, 6.1, 2.5, 0.3, 6.4, 15.5))                # rear door split
    for cx in (6.5, 29.5):
        cuts.append(wheel_y(cx, 2.2, 2.9, -1, 1.6))              # wheel arches (sides only)
        cuts.append(wheel_y(cx, 2.2, 2.9, 10.9, 13.5))
    adds2 = [wheel_y(cx, 2.2, 2.2, 0.2, 12.3) for cx in (6.5, 29.5)]
    adds2.append(box(36.6, 0.8, 2.2, 37.6, 11.7, 4.0))           # bumper
    return solid("delivery_van", adds, cuts, coll, "van", adds2)


# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------
def reset():
    old = bpy.data.collections.get("WAREHOUSE")
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


def export_flipped(obj, path, height):
    """Export upside-down (roof on the bed) without touching the scene object."""
    me = obj.data.copy()
    me.transform(Matrix.Translation((0, 0, height)) @ Matrix.Rotation(math.pi, 4, "X")
                 @ Matrix.Translation((0, 0, 0)))
    tmp = bpy.data.objects.new(obj.name + "_print", me)
    bpy.context.scene.collection.objects.link(tmp)
    tc.export_stl(tmp, path)
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)


def run(render=True):
    reset()
    out = os.path.join(tc.out_dir(), "warehouse")
    stl = os.path.join(out, "stl")
    os.makedirs(stl, exist_ok=True)
    for f in os.listdir(stl):
        if f.endswith(".stl"):
            os.remove(os.path.join(stl, f))

    root = collection("WAREHOUSE")
    lib = collection("WH_Print_Parts", root)
    mod = collection("Module_C_Distribution_Center", root)

    segs = [("left", True, False, True)] + [("mid", False, False, False)] * min(MID_SEGMENTS, 1) \
        + [("right", False, True, False)]
    parts = {}
    for key, hl, hr, off in segs:
        sh = seg_shell("wh_seg_" + key, SEG_L, hl, hr, off, lib)
        rf, ro = seg_roof("wh_roof_" + key, SEG_L, hl, hr, lib)
        parts[key] = (sh, rf, ro)
    tr = trailer(lib)
    vn = van(lib)

    # ---- Module C layout
    ox = 0.0
    tc.build_module_frame(mod, ox)
    tc.build_track(mod, ox)
    n_segs = 2 + MID_SEGMENTS
    total = n_segs * SEG_L
    bx = (tc.MODULE_W - total) / 2
    by = tc.MODULE_D - 4 - DEPTH
    pave_z = 1.0
    mesh_obj("pavement", box(0, tc.STREET_Y - 4, 0, tc.MODULE_W, tc.MODULE_D, pave_z), mod, "asphalt")
    order = ["left"] + ["mid"] * MID_SEGMENTS + ["right"]
    dock_global = []
    for i, key in enumerate(order):
        sh, rf, ro = parts[key]
        x = bx + i * SEG_L
        tc.place(sh, mod, (x, by, pave_z))
        tc.place(rf, mod, (x + ro[0], by + ro[1], pave_z + ro[2]))
        dock_global += [x + c for c in dock_centers(SEG_L, key == "left")]
        # render-only paint overlays (accent band, office glass)
        mesh_obj("paint_band", box(x, by - 0.5, pave_z + H - 12, x + SEG_L, by - 0.42, pave_z + H - 6),
                 mod, "accent")
        if key == "left":
            mesh_obj("paint_glass", box(x + 3, by + 0.8, pave_z + 1.5, x + OFFICE_W - 3, by + 0.88,
                                        pave_z + 52), mod, "glass_dark")
            mesh_obj("paint_sign", box(x + 6, by - 0.88, pave_z + H - 24.5, x + OFFICE_W - 6, by - 0.82,
                                       pave_z + H - 13.5), mod, "accent")
    rot = Matrix.Rotation(-math.pi / 2, 4, "Z")
    for k, cx in enumerate(dock_global):
        mesh_obj("stall", box(cx - 12.5, by - 100, pave_z, cx - 12, by - 2, pave_z + 0.05), mod, "stripe")
        if k in TRAILERS_AT_DOCKS:
            t = tr.copy()
            t.location = (cx - 8, by - 0.6, pave_z)
            t.rotation_euler = rot.to_euler()
            mod.objects.link(t)
    for i in range(3):                                   # vans by the office
        v = vn.copy()
        v.location = (8 + i * 22, by - 45, pave_z)
        v.rotation_euler = (0, 0, math.pi / 2)
        v.location.x += 12.5
        mod.objects.link(v)

    # ---- library layout for the parts render + exports
    x = 0
    for key in ("left", "mid", "right"):
        if key not in parts:
            continue
        sh, rf, _ = parts[key]
        sh.location = (x, -600, 0)
        rf.location = (x, -600 - DEPTH - 30, 0)
        x += SEG_L + 30
    tr.location = (x, -620, 0)
    vn.location = (x, -660, 0)

    rows = []
    for key, (sh, rf, _) in parts.items():
        for ob in (sh, rf):
            tc.export_stl(ob, os.path.join(stl, ob.name + ".stl"))
            q = (MID_SEGMENTS if key == "mid" else 1)
            rows.append((ob.name, q, *[round(v, 1) for v in ob.dimensions]))
    export_flipped(tr, os.path.join(stl, "trailer_53ft_print_upside_down.stl"), 25.6)
    rows.append(("trailer_53ft_print_upside_down", len(TRAILERS_AT_DOCKS), *[round(v, 1) for v in tr.dimensions]))
    tc.export_stl(vn, os.path.join(stl, "delivery_van.stl"))
    rows.append(("delivery_van", 3, *[round(v, 1) for v in vn.dimensions]))
    with open(os.path.join(out, "warehouse_parts.csv"), "w") as fh:
        fh.write("part,qty,x_mm,y_mm,z_mm\n")
        for r in rows:
            fh.write(",".join(str(v) for v in r) + "\n")

    # ---- render setup (daylight)
    sc = bpy.context.scene
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 4.0
    sun.angle = math.radians(5)
    so = bpy.data.objects.new("Sun", sun)
    root.objects.link(so)
    so.rotation_euler = (math.radians(48), math.radians(12), math.radians(-25))
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    bg = sc.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*tc.COLORS["sky"], 1)
    bg.inputs[1].default_value = 0.7
    mesh_obj("table", box(-600, -1000, -tc.MODULE_TOP_Z - 20, 1300, 800, -tc.MODULE_TOP_Z), root, "table")
    def cam(name, loc, target, lens):
        c = bpy.data.cameras.new(name)
        c.lens, c.clip_start, c.clip_end = lens, 5, 20000
        ob = bpy.data.objects.new(name, c)
        root.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    cams = {
        "overview": cam("WH_Cam_Overview", (720, -380, 330), (300, 230, 20), 28),
        "docks": cam("WH_Cam_Docks", (20, 50, 55), (190, 210, 35), 24),
        "parts": cam("WH_Cam_Parts", (330, -1250, 330), (330, -660, 20), 32),
    }
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "warehouse.blend"))
    if render:
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 48
        sc.cycles.use_denoising = True
        sc.render.resolution_x, sc.render.resolution_y = 1600, 900
        for name, cam in cams.items():
            lib.hide_render = name != "parts"
            mod.hide_render = name == "parts"
            sc.camera = cam
            sc.render.filepath = os.path.join(out, "render_warehouse_%s.png" % name)
            bpy.ops.render.render(write_still=True)
        lib.hide_render, mod.hide_render = True, False
    print("Warehouse: wrote STLs to", stl)


if __name__ == "__main__":
    run(render="--no-render" not in sys.argv)
