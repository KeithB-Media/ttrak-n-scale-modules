"""Renders for river_bridge.py (needs bpy: pip install bpy, or run inside Blender).
Imports the assembled STLs from ttrak_output/river_bridge/_assembly and renders preview PNGs.
Run on its own:  python river_bridge_render.py   (after python river_bridge.py --no-render)"""

import os
import sys
import math
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import river_bridge as rb


def _mat(name, color, rough=0.8, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def terrain_material():
    m = bpy.data.materials.new("terrain")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.95
    geo = N.new("ShaderNodeNewGeometry")
    sep_n = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sep_n.inputs[0])
    sep_p = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep_p.inputs[0])
    tex = N.new("ShaderNodeTexCoord")
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.06
    noise.inputs["Detail"].default_value = 6
    L.new(tex.outputs["Object"], noise.inputs["Vector"])
    fol = N.new("ShaderNodeValToRGB")          # autumn foliage
    cr = fol.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.38, (0.05, 0.09, 0.02, 1)
    cr.elements[1].position, cr.elements[1].color = 0.66, (0.42, 0.30, 0.05, 1)
    e = cr.elements.new(0.5)
    e.color = (0.14, 0.20, 0.04, 1)
    e = cr.elements.new(0.75)
    e.color = (0.40, 0.14, 0.03, 1)
    L.new(noise.outputs["Fac"], fol.inputs[0])
    steep = N.new("ShaderNodeMapRange")         # normal z 0.55..0.8 -> rock..foliage
    steep.inputs["From Min"].default_value = 0.62
    steep.inputs["From Max"].default_value = 0.85
    L.new(sep_n.outputs["Z"], steep.inputs["Value"])
    mix1 = N.new("ShaderNodeMix")
    mix1.data_type = "RGBA"
    mix1.inputs[6].default_value = (0.30, 0.28, 0.26, 1)          # rock
    L.new(steep.outputs[0], mix1.inputs["Factor"])
    L.new(fol.outputs["Color"], mix1.inputs[7])
    low = N.new("ShaderNodeMapRange")           # river bed below the water line
    low.inputs["From Min"].default_value = rb.WATER - 1
    low.inputs["From Max"].default_value = rb.WATER + 1.5
    L.new(sep_p.outputs["Z"], low.inputs["Value"])
    mix2 = N.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    mix2.inputs[6].default_value = (0.20, 0.17, 0.12, 1)
    L.new(low.outputs[0], mix2.inputs["Factor"])
    L.new(mix1.outputs[2], mix2.inputs[7])
    flat = N.new("ShaderNodeMapRange")          # track-level ground: grass / ballast
    flat.inputs["From Min"].default_value = -0.6
    flat.inputs["From Max"].default_value = -0.2
    L.new(sep_p.outputs["Z"], flat.inputs["Value"])
    up = N.new("ShaderNodeMath")
    up.operation = "GREATER_THAN"
    up.inputs[1].default_value = 0.98
    L.new(sep_n.outputs["Z"], up.inputs[0])
    hi = N.new("ShaderNodeMath")
    hi.operation = "LESS_THAN"
    hi.inputs[1].default_value = 1.2
    L.new(sep_p.outputs["Z"], hi.inputs[0])
    f2 = N.new("ShaderNodeMath")
    f2.operation = "MULTIPLY"
    L.new(flat.outputs[0], f2.inputs[0])
    L.new(up.outputs[0], f2.inputs[1])
    f3 = N.new("ShaderNodeMath")
    f3.operation = "MULTIPLY"
    L.new(f2.outputs[0], f3.inputs[0])
    L.new(hi.outputs[0], f3.inputs[1])
    mix3 = N.new("ShaderNodeMix")
    mix3.data_type = "RGBA"
    L.new(f3.outputs[0], mix3.inputs["Factor"])
    L.new(mix2.outputs[2], mix3.inputs[6])
    mix3.inputs[7].default_value = (0.20, 0.24, 0.10, 1)
    L.new(mix3.outputs[2], bsdf.inputs["Base Color"])
    return m


def box(name, x0, y0, z0, x1, y1, z1, mat, coll):
    me = bpy.data.meshes.new(name)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f)
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    coll.objects.link(ob)
    return ob


def wedge(name, xa, xb, y0, y1, za, zb, mat, coll):
    """Triangular slope: height za at x = xa falling to zb at x = xb (render only)."""
    from manifold3d import Manifold
    import numpy as np
    pts = [(xa, y0, zb), (xb, y0, zb), (xa, y0, za), (xa, y1, zb), (xb, y1, zb), (xa, y1, za)]
    mm = Manifold.hull_points(pts).to_mesh()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v[:3]) for v in np.array(mm.vert_properties)], [],
                   [tuple(int(i) for i in t) for t in np.array(mm.tri_verts)])
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    coll.objects.link(ob)
    return ob


def imp(path, mat, coll, loc=(0, 0, 0)):
    bpy.ops.wm.stl_import(filepath=path)
    ob = bpy.context.selected_objects[0]
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    ob.data.materials.clear()
    if ob.data.has_custom_normals:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    ob.data.shade_flat()
    ob.data.materials.append(mat)
    ob.location = loc
    return ob


def render(out, asm):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 0.001
    coll = bpy.data.collections.new("RiverBridge")
    sc.collection.children.link(coll)
    parts_c = bpy.data.collections.new("Parts")
    sc.collection.children.link(parts_c)

    M = {
        "terrain": terrain_material(),
        "steel": _mat("steel", (0.16, 0.10, 0.07), 0.7),           # weathered dark brown steel
        "concrete": _mat("concrete", (0.62, 0.56, 0.47), 0.9),
        "ballast": _mat("ballast", (0.33, 0.30, 0.27), 1.0),
        "rail": _mat("rail", (0.35, 0.28, 0.22), 0.5, 0.6),
        "train": _mat("train", (0.72, 0.73, 0.75), 0.35, 0.6),
        "nose": _mat("nose", (0.10, 0.18, 0.40), 0.4),
        "window": _mat("window", (0.04, 0.05, 0.07), 0.2),
        "table": _mat("table", (0.30, 0.22, 0.15), 0.6),
        "part": _mat("part", (0.80, 0.38, 0.10), 0.5),
    }
    w = _mat("water", (0.04, 0.08, 0.07), 0.04)
    M["water"] = w

    M["ply"] = _mat("ply", (0.78, 0.62, 0.42), 0.7)
    M["grass"] = _mat("grass", (0.20, 0.30, 0.08), 1.0)
    M["rock"] = _mat("rock", (0.40, 0.37, 0.33), 0.9)
    M["wheel"] = _mat("wheel", (0.08, 0.08, 0.08), 0.6)
    import river_laser as rl
    top = rb.HEIGHTS["70mm_template"]
    rl.set_height(top)
    for which in ("A", "B"):
        for name, mat in (("ply", "ply"), ("plyconcrete", "concrete"), ("footblocks", "rock"), ("feet", "wheel"),
                          ("girder", "steel"), ("rail", "steel"), ("pier", "concrete")):
            imp(os.path.join(asm, "%s_%s.stl" % (name, which)), M[mat], coll)
    total = 2 * rb.MW + rb.GAP
    zbase = -rl.BOX + rb.PLY
    mirror = lambda x: total - x
    for ox, f in ((0.0, lambda x: x), (0.0, mirror)):
        # water between the abutment and the joint, and grass + foam slopes beside the embankment
        x0, x1 = sorted((f(rb.XA - 5), f(rb.MW - 0.01)))
        box("water", x0, rb.PLY, zbase, x1, rb.MD - rb.PLY, zbase + rb.WATER, M["water"], coll)
        a0, a1 = sorted((f(rb.PLY), f(rl.TR_TOP_X)))
        box("grass_top", a0, rb.PLY, -0.4, a1, rb.MD - rb.PLY, 0.3, M["grass"], coll)
        for y0, y1 in ((rb.PLY, rl.W0), (rl.W1, rb.MD - rb.PLY)):
            xa, xb = f(rl.TR_TOP_X), f(rl.TR_TOP_X + (rl.BOX - rb.PLY - rb.WATER) * 0.9)
            wedge("foam_slope", xa, xb, y0, y1, -rb.PLY, zbase + rb.WATER, M["grass"], coll)
    zt = -top
    box("table", -900, -900, zt - 25, total + 900, rb.MD + 300, zt, M["table"], coll)
    box("neighbour_L", -620, 0, zt + rb.FOOT_NOM, -2, rb.MD, -0.5, M["grass"], coll)
    box("neighbour_R", total + 2, 0, zt + rb.FOOT_NOM, total + 620, rb.MD, -0.5, M["grass"], coll)

    # Unitrack placeholders
    for yc in rb.TRACK_Y:
        for ox in (-620.0, 0.0, rb.MW + rb.GAP, total + rb.GAP):
            x = ox - 1.0
            for Lp in rb.TRACK_PIECES:
                box("roadbed", x + 0.2, yc - 12.5, 0, x + Lp - 0.2, yc + 12.5, rb.UNITRACK_H - 1.7,
                    M["ballast"], coll)
                for r in (-4.5, 4.5):
                    box("rail", x, yc + r - 0.4, rb.UNITRACK_H - 1.7, x + Lp, yc + r + 0.4,
                        rb.UNITRACK_H, M["rail"], coll)
                x += Lp

    # generic stand-in passenger train for scale (render only)
    yc = rb.TRACK_Y[0]
    z0 = rb.UNITRACK_H + 1.0
    x = 120.0
    for i in range(7):
        Lc = 120.0 if i < 2 else 135.0
        hgt = 26.0 if i < 2 else 30.0
        box("car", x, yc - 9.5, z0, x + Lc, yc + 9.5, z0 + hgt, M["train"], coll)
        box("band", x + 4, yc - 9.6, z0 + hgt * 0.62, x + Lc - 4, yc + 9.6, z0 + hgt * 0.78, M["window"], coll)
        if i == 0:
            box("nose", x - 3, yc - 9.6, z0 + 2, x + 30, yc + 9.6, z0 + hgt - 2, M["nose"], coll)
        x += Lc + 3

    # printed-parts layout (parts render)
    stl = os.path.join(out, "stl")
    px = 0.0
    for name in ("deck_girder_span_print_upside_down", "handrail_print_flat",
                 "70mm_template/pier_full_print_upside_down", "70mm_template/pier_joint_half_print_upside_down",
                 "foot_nut_block_rock", "foot_thumbwheel"):
        ob = imp(os.path.join(stl, name + ".stl"), M["part"], parts_c, (px, 3000, 0))
        px += ob.dimensions.x + 25

    # light + world
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy, sun.angle = 4.5, math.radians(3)
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(55), math.radians(0), math.radians(-125))
    sc.world = bpy.data.worlds.new("World")
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.72, 0.88, 1)
    bg.inputs[1].default_value = 0.9

    def cam(name, loc, target, lens):
        c = bpy.data.cameras.new(name)
        c.lens, c.clip_start, c.clip_end = lens, 5, 40000
        ob = bpy.data.objects.new(name, c)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    cams = {
        "along_bridge": cam("C_along", (40, -160, -5), (720, 150, -40), 26),
        "overview": cam("C_over", (300, -900, 650), (650, 170, -40), 26),
        "transition": cam("C_trans", (330, -230, 120), (110, 120, -30), 24),
        "feet": cam("C_feet", (650, -130, -62), (590, 60, -64), 30),
        "parts": cam("C_parts", (px / 2, 2550, 300), (px / 2, 3050, 10), 32),
    }
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    quick = os.environ.get("RB_QUICK")
    sc.cycles.samples = 8 if quick else 40
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = (800, 450) if quick else (1600, 900)
    for name, cm in cams.items():
        coll.hide_render = name == "parts"
        parts_c.hide_render = name != "parts"
        sc.camera = cm
        sc.render.filepath = os.path.join(out, "render_river_%s.png" % name)
        bpy.ops.render.render(write_still=True)
        print("rendered", name)


if __name__ == "__main__":
    render(rb.OUT, os.path.join(rb.OUT, "_assembly"))
