"""「世界中のアフリカゾウを全部1か所に集めたら？」のシーン。

    python herd_scene.py --out herd.blend --meta herd_meta.json [--test 1,200 prefix] [--res 1280x720]

推定 約41万5000頭(IUCN アフリカゾウ現状報告 2016)のゾウを、
1頭あたり 6m×3m の区画にぎっしり並べる。ポーズ違いのゾウを数種類作り、
Geometry Nodes のインスタンスで全頭を置く。
"""
import sys, os, math, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from mathutils import Vector

import blender_lib as bl
from blender_lib import _node
import scene as lineup   # 木・草・山の部品を流用

FPS = bl.FPS
N_TOTAL = 415_000
CELL_X, CELL_Y = 6.0, 3.0         # 1頭ぶんの区画[m](体の向き × 横)
NX = 455                           # 体の向きにならぶ数
NY = 912                           # 横にならぶ数 (455×912 = 41万4960頭)
SIZE_X, SIZE_Y = NX * CELL_X, NY * CELL_Y
POP_1979 = 1_300_000
DOME_AREA = 46_755.0               # 東京ドームの建築面積[m²]
DOME_POS = (SIZE_X / 2 + 450, -SIZE_Y / 2 + 400, 0)

# 時間割(秒)
T = dict(intro=5.0, one=4.5, pull=12.0, top=5.5, dome=8.5, past=8.5, outro=5.0)
DURATION = sum(T.values())


def tstart(name):
    t = 0.0
    for k, v in T.items():
        if k == name:
            return t
        t += v
    raise KeyError(name)


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ かすみ(空気遠近)
FOG_COLOR = (0.62, 0.72, 0.86)
FOG_STRENGTH = 1.0
FOG_DIST = 40000.0


def add_fog(mat, dist=FOG_DIST):
    """カメラからの距離に応じて、かすみ色に溶け込ませる。"""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    if not out.inputs["Surface"].links:
        return
    src = out.inputs["Surface"].links[0].from_socket
    cam = _node(nt, "ShaderNodeCameraData", (out.location.x - 600, out.location.y - 300))
    div = _node(nt, "ShaderNodeMath", (out.location.x - 400, out.location.y - 300))
    div.operation = "DIVIDE"
    div.inputs[1].default_value = -dist
    nt.links.new(cam.outputs["View Distance"], div.inputs[0])
    ex = _node(nt, "ShaderNodeMath", (out.location.x - 250, out.location.y - 300))
    ex.operation = "EXPONENT"
    nt.links.new(div.outputs[0], ex.inputs[0])
    inv = _node(nt, "ShaderNodeMath", (out.location.x - 100, out.location.y - 300))
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(ex.outputs[0], inv.inputs[1])
    em = _node(nt, "ShaderNodeEmission", (out.location.x - 250, out.location.y - 150))
    em.inputs["Color"].default_value = (*FOG_COLOR, 1)
    em.inputs["Strength"].default_value = FOG_STRENGTH
    mix = _node(nt, "ShaderNodeMixShader", (out.location.x - 100, out.location.y))
    nt.links.new(inv.outputs[0], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    # かすみの発光は「光源」として扱わない(全部のゾウが光源になって極端に遅くなるため)
    mat.cycles.emission_sampling = "NONE"


# ------------------------------------------------------------------ 地面
def make_ground():
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    g = bpy.context.active_object
    g.name = "ground"
    g.scale = (200000, 200000, 1)
    m = bpy.data.materials.new("ground")
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = _node(nt, "ShaderNodeOutputMaterial", (900, 0))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (600, 0), Roughness=0.95)
    L(b.outputs[0], out.inputs[0])
    tc = _node(nt, "ShaderNodeTexCoord", (-1200, 0))
    # 近く(数m)・中くらい(数十m)・遠く(数km)の3段の色むら
    n1 = _node(nt, "ShaderNodeTexNoise", (-900, 300), Scale=0.6, Detail=3.0, Roughness=0.65)
    n2 = _node(nt, "ShaderNodeTexNoise", (-900, 0), Scale=0.02, Detail=4.0, Roughness=0.6)
    n3 = _node(nt, "ShaderNodeTexNoise", (-900, -300), Scale=0.0004, Detail=4.0, Roughness=0.55)
    for n in (n1, n2, n3):
        L(tc.outputs["Object"], n.inputs["Vector"])
    a = _node(nt, "ShaderNodeMath", (-650, 150))
    a.operation = "MULTIPLY_ADD"
    a.inputs[1].default_value = 0.35
    L(n1.outputs["Fac"], a.inputs[0])
    L(n2.outputs["Fac"], a.inputs[2])
    c = _node(nt, "ShaderNodeMath", (-500, 0))
    c.operation = "MULTIPLY_ADD"
    c.inputs[1].default_value = 0.6
    L(n3.outputs["Fac"], c.inputs[0])
    L(a.outputs[0], c.inputs[2])
    sub = _node(nt, "ShaderNodeMath", (-350, 0))
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = 0.55
    L(c.outputs[0], sub.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-150, 0)
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.25, (0.17, 0.12, 0.07, 1)
    e[1].position, e[1].color = 0.75, (0.42, 0.34, 0.18, 1)
    e.new(0.45).color = (0.30, 0.24, 0.12, 1)
    e.new(0.6).color = (0.26, 0.25, 0.11, 1)
    L(sub.outputs[0], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = _node(nt, "ShaderNodeBump", (300, -200), Strength=0.5, Distance=0.05)
    n4 = _node(nt, "ShaderNodeTexNoise", (-900, -600), Scale=8.0, Detail=2.0)
    L(tc.outputs["Object"], n4.inputs["Vector"])
    L(n4.outputs["Fac"], bump.inputs["Height"])
    L(bump.outputs[0], b.inputs["Normal"])
    g.data.materials.append(m)
    # オブジェクト座標が m 単位になるよう、スケールを適用
    bpy.ops.object.transform_apply(scale=True)
    add_fog(m)
    return g


# ------------------------------------------------------------------ ゾウの群れ
def make_variants(n=5):
    """ポーズ違いのゾウのメッシュを作る(骨で動かした形を、目もいっしょに固定)。"""
    import bmesh
    coll = bpy.data.collections.new("elephant_variants")
    bpy.context.scene.collection.children.link(coll)
    rig, ob, spec = bl.make_creature("elephant", frames=(1, 400), seed=1)
    eyes = [c for c in rig.children if c is not ob]
    sc = bpy.context.scene
    out = []
    for i in range(n):
        sc.frame_set(1 + i * 37)
        dg = bpy.context.evaluated_depsgraph_get()
        bm = bmesh.new()
        body = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        body.transform(ob.matrix_world)
        bm.from_mesh(body)
        for e in eyes:
            em = bpy.data.meshes.new_from_object(e.evaluated_get(dg))
            em.transform(e.matrix_world)
            n0 = len(bm.faces)
            bm.from_mesh(em)
            bm.faces.ensure_lookup_table()
            for f in bm.faces[n0:]:
                f.material_index = 1
            bpy.data.meshes.remove(em)
        bm.to_mesh(body)
        bm.free()
        body.materials.clear()
        body.materials.append(ob.data.materials[0])
        body.materials.append(bl.eye_material())
        body.name = f"elephant_v{i}"
        v = bpy.data.objects.new(f"elephant_v{i}", body)
        coll.objects.link(v)
        out.append(v)
    sc.frame_set(1)
    for o in set([rig, ob] + eyes):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.layer_collection.children[coll.name].exclude = True
    for m in out[0].data.materials:
        add_fog(m)
    return coll, spec, out


TILE_X, TILE_Y = 5, 8          # 1タイル = 5×8 = 40頭
NEAR_R = 70.0                  # 主役のまわりは1頭ずつの精細なゾウにする


def lod_arrays(variants, ratio_polys=2500):
    """遠景用に、ポーズ違いのゾウを軽いメッシュ(頂点・面の配列)にする。"""
    out = []
    for v in variants:
        tmp = bpy.data.objects.new("tmp", v.data.copy())
        bpy.context.scene.collection.objects.link(tmp)
        # 目(素材1)は遠景では見えないので除く
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(tmp.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 1], context="FACES")
        bm.to_mesh(tmp.data)
        bm.free()
        d = tmp.modifiers.new("dec", "DECIMATE")
        d.ratio = ratio_polys / max(len(tmp.data.polygons), 1)
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
        me.calc_loop_triangles()
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", V)
        F = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", F)
        out.append((V.reshape(-1, 3), F.reshape(-1, 3)))
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(me)
    return out


def far_material():
    """遠くのゾウ用の軽い素材(しわ・土ぼこりのバンプなし)。"""
    m = bpy.data.materials.new("elephant_far")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.8
    oi = _node(nt, "ShaderNodeObjectInfo", (-600, 300))
    # 同じタイルの中でも1頭ずつ色を変えるため、位置からも乱数を作る
    tc = _node(nt, "ShaderNodeTexCoord", (-800, 100))
    wn = _node(nt, "ShaderNodeTexWhiteNoise", (-600, 100))
    wn.noise_dimensions = "2D"
    mp = _node(nt, "ShaderNodeMapping", (-700, 100))
    mp.inputs["Scale"].default_value = (1 / 6.0, 1 / 3.0, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    fl = _node(nt, "ShaderNodeVectorMath", (-650, 0))
    fl.operation = "FLOOR"
    nt.links.new(mp.outputs[0], fl.inputs[0])
    nt.links.new(fl.outputs[0], wn.inputs["Vector"])
    ad = _node(nt, "ShaderNodeMath", (-450, 200))
    ad.operation = "ADD"
    nt.links.new(oi.outputs["Random"], ad.inputs[0])
    nt.links.new(wn.outputs["Value"], ad.inputs[1])
    fr = _node(nt, "ShaderNodeMath", (-350, 200))
    fr.operation = "FRACT"
    nt.links.new(ad.outputs[0], fr.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-250, 200)
    ramp.color_ramp.elements[0].color = (0.17, 0.15, 0.135, 1)
    ramp.color_ramp.elements[1].color = (0.30, 0.25, 0.21, 1)
    nt.links.new(fr.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    add_fog(m)
    return m


def make_tiles(lods, mat, n_var=6, seed=3):
    """40頭ぶんを1つのメッシュに焼き込んだタイルを数種類作る。"""
    rng = np.random.default_rng(seed)
    coll = bpy.data.collections.new("herd_tiles")
    bpy.context.scene.collection.children.link(coll)
    for k in range(n_var):
        Vs, Fs, off = [], [], 0
        for i in range(TILE_X):
            for j in range(TILE_Y):
                V, F = lods[rng.integers(len(lods))]
                yaw = rng.normal(0, 0.25) if rng.random() > 0.12 else rng.uniform(-math.pi, math.pi)
                r = rng.random()
                sc = (rng.uniform(0.42, 0.62) if r < 0.18 else rng.uniform(0.78, 0.9) if r < 0.72
                      else rng.uniform(0.92, 1.05))
                c, s_ = math.cos(yaw), math.sin(yaw)
                R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]]) * sc
                px = (i + 0.5) * CELL_X - TILE_X * CELL_X / 2 + rng.normal(0, 0.35)
                py = (j + 0.5) * CELL_Y - TILE_Y * CELL_Y / 2 + rng.normal(0, 0.25)
                Vs.append(V @ R.T + [px, py, 0])
                Fs.append(F + off)
                off += len(V)
        me = bpy.data.meshes.new(f"tile{k}")
        me.from_pydata(np.vstack(Vs).tolist(), [], np.vstack(Fs).tolist())
        me.shade_smooth()
        # 頂点色(Col)は素材が使うので、ゾウの平均の灰色で埋める
        a = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        col = np.tile([0.24, 0.21, 0.19, 1.0], len(me.loops)).astype(np.float32)
        a.data.foreach_set("color", col)
        rr = me.attributes.new("rough", "FLOAT", "POINT")
        rr.data.foreach_set("value", np.full(len(me.vertices), 0.75, np.float32))
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"tile{k}", me)
        coll.objects.link(ob)
    bpy.context.view_layer.layer_collection.children[coll.name].exclude = True
    return coll


def herd_points(seed=0):
    rng = np.random.default_rng(seed)
    ix, iy = np.meshgrid(np.arange(NX), np.arange(NY), indexing="ij")
    x = (ix.ravel() + 0.5) * CELL_X - SIZE_X / 2 + rng.normal(0, 0.35, ix.size)
    y = (iy.ravel() + 0.5) * CELL_Y - SIZE_Y / 2 + rng.normal(0, 0.25, ix.size)
    n = x.size
    # 向き: ほとんどは同じ向き(+X)、少しずつばらつき、一部は好きな方向
    yaw = rng.normal(0, 0.25, n)
    free = rng.random(n) < 0.12
    yaw[free] = rng.uniform(-math.pi, math.pi, free.sum())
    # 大きさ: 子ども・メス・オスがまざる
    r = rng.random(n)
    scale = np.where(r < 0.18, rng.uniform(0.42, 0.62, n),
                     np.where(r < 0.72, rng.uniform(0.78, 0.9, n), rng.uniform(0.92, 1.05, n)))
    var = rng.integers(0, 5, n)
    return np.column_stack([x, y]), yaw, scale, var


def make_herd(coll, pts, yaw, scale, var, name="herd"):
    me = bpy.data.meshes.new(name + "_pts")
    me.from_pydata(np.column_stack([pts, np.zeros(len(pts))]).tolist(), [], [])
    a = me.attributes.new("yaw", "FLOAT", "POINT")
    a.data.foreach_set("value", yaw.astype(np.float32))
    a = me.attributes.new("scl", "FLOAT", "POINT")
    a.data.foreach_set("value", scale.astype(np.float32))
    a = me.attributes.new("var", "INT", "POINT")
    a.data.foreach_set("value", var.astype(np.int32))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)

    ng = bpy.data.node_groups.new(name + "_inst", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    L = ng.links.new
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True

    def named(name, typ):
        n = N.new("GeometryNodeInputNamedAttribute")
        n.data_type = typ
        n.inputs["Name"].default_value = name
        return n
    ny, ns, nv = named("yaw", "FLOAT"), named("scl", "FLOAT"), named("var", "INT")
    comb = N.new("ShaderNodeCombineXYZ")
    L(ny.outputs["Attribute"], comb.inputs["Z"])
    L(gi.outputs[0], m2p.inputs["Mesh"])
    L(m2p.outputs[0], inst.inputs["Points"])
    L(ci.outputs[0], inst.inputs["Instance"])
    L(nv.outputs["Attribute"], inst.inputs["Instance Index"])
    L(comb.outputs[0], inst.inputs["Rotation"])
    L(ns.outputs["Attribute"], inst.inputs["Scale"])
    L(inst.outputs[0], go.inputs[0])
    ob.modifiers.new("inst", "NODES").node_group = ng
    return ob


def tint_by_instance(mat):
    """1頭ずつ少しだけ色を変える(遠くから見たときの自然なむら)。"""
    nt = mat.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = b.inputs["Base Color"].links[0].from_socket
    oi = _node(nt, "ShaderNodeObjectInfo", (b.location.x - 600, b.location.y + 600))
    mr = _node(nt, "ShaderNodeMapRange", (b.location.x - 400, b.location.y + 600))
    mr.inputs["To Min"].default_value = 0.78
    mr.inputs["To Max"].default_value = 1.2
    nt.links.new(oi.outputs["Random"], mr.inputs["Value"])
    mx = _node(nt, "ShaderNodeMix", (b.location.x - 200, b.location.y + 600))
    mx.data_type = "RGBA"
    mx.blend_type = "MULTIPLY"
    mx.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mx.inputs[6])
    nt.links.new(mr.outputs["Result"], mx.inputs[7])
    nt.links.new(mx.outputs[2], b.inputs["Base Color"])


# ------------------------------------------------------------------ 東京ドーム(大きさの目安)
def make_dome():
    """建築面積 46,755m²、高さ約56m の白い屋根の建物(形は単純化)。"""
    r = math.sqrt(DOME_AREA / math.pi)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=r, depth=24, location=(0, 0, 12))
    wall = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.0, location=(0, 0, 24))
    roof = bpy.context.active_object
    roof.scale = (r * 0.98, r * 0.98, 32)
    mw = bpy.data.materials.new("dome_wall")
    mw.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.56, 1)
    mr = bpy.data.materials.new("dome_roof")
    b = mr.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.85, 0.86, 0.86, 1)
    b.inputs["Roughness"].default_value = 0.35
    wall.data.materials.append(mw)
    roof.data.materials.append(mr)
    for o in (wall, roof):
        o.data.shade_smooth()
    root = bpy.data.objects.new("tokyo_dome", None)
    bpy.context.scene.collection.objects.link(root)
    for o in (wall, roof):
        o.parent = root
    root.location = DOME_POS
    add_fog(mw)
    add_fog(mr)
    return root


# ------------------------------------------------------------------ 木
def make_tree_field():
    trees = lineup.make_trees()
    for o in trees.objects:
        for s in o.material_slots:
            if s.material and not s.material.get("fogged"):
                add_fog(s.material)
                s.material["fogged"] = True
    rng = np.random.default_rng(5)
    n = 6000
    p = rng.uniform(-14000, 14000, (n, 2))
    # 群れのまわり(少し余白)には置かない
    keep = ~((np.abs(p[:, 0]) < SIZE_X / 2 + 60) & (np.abs(p[:, 1]) < SIZE_Y / 2 + 60))
    p = p[keep]
    near = rng.uniform(-2600, 2600, (900, 2))
    near = near[~((np.abs(near[:, 0]) < SIZE_X / 2 + 60) & (np.abs(near[:, 1]) < SIZE_Y / 2 + 60))]
    p = np.vstack([p, near])
    me = bpy.data.meshes.new("tree_pts")
    me.from_pydata(np.column_stack([p, np.zeros(len(p))]).tolist(), [], [])
    a = me.attributes.new("var", "INT", "POINT")
    a.data.foreach_set("value", rng.integers(0, 4, len(p)).astype(np.int32))
    ob = bpy.data.objects.new("trees", me)
    bpy.context.scene.collection.objects.link(ob)
    # 木の親(幹)だけを1本ずつのコレクションにまとめ直す
    tc = bpy.data.collections.new("tree_variants")
    for i, t in enumerate([o for o in trees.objects if o.parent is None]):
        sub = bpy.data.collections.new(f"tree_v{i}")
        sub.objects.link(t)
        for ch in t.children:
            sub.objects.link(ch)
        tc.children.link(sub)
    ng = bpy.data.node_groups.new("tree_inst", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N = ng.nodes
    L = ng.links.new
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    ci = N.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = tc
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    inst = N.new("GeometryNodeInstanceOnPoints")
    inst.inputs["Pick Instance"].default_value = True
    nv = N.new("GeometryNodeInputNamedAttribute")
    nv.data_type = "INT"
    nv.inputs["Name"].default_value = "var"
    rv = N.new("FunctionNodeRandomValue")
    rv.data_type = "FLOAT_VECTOR"
    lineup.sock(rv, "Min", "VECTOR").default_value = (0, 0, 0)
    lineup.sock(rv, "Max", "VECTOR").default_value = (0, 0, 6.28)
    rs = N.new("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    lineup.sock(rs, "Min", "VALUE").default_value = 0.8
    lineup.sock(rs, "Max", "VALUE").default_value = 1.4
    L(gi.outputs[0], m2p.inputs["Mesh"])
    L(m2p.outputs[0], inst.inputs["Points"])
    L(ci.outputs[0], inst.inputs["Instance"])
    L(nv.outputs["Attribute"], inst.inputs["Instance Index"])
    L(rv.outputs["Value"], inst.inputs["Rotation"])
    L(next(o for o in rs.outputs if o.type == "VALUE" and o.enabled), inst.inputs["Scale"])
    L(inst.outputs[0], go.inputs[0])
    ob.modifiers.new("inst", "NODES").node_group = ng
    return ob


def make_far_mountains():
    m = bpy.data.materials.new("mountain")
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.16, 0.14, 0.13, 1)
    b.inputs["Roughness"].default_value = 1.0
    add_fog(m, dist=14000)
    rng = np.random.default_rng(2)
    for i in range(9):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(26000, 40000)
        r = rng.uniform(5000, 11000)
        h = rng.uniform(900, 2600)
        bpy.ops.mesh.primitive_cone_add(vertices=96, radius1=r, radius2=r * 0.12, depth=h,
                                        location=(math.cos(a) * d, math.sin(a) * d, h / 2 - 50))
        c = bpy.context.active_object
        mod = c.modifiers.new("sub", "SUBSURF")
        mod.levels = mod.render_levels = 3
        tex = bpy.data.textures.new(f"mt{i}", "CLOUDS")
        tex.noise_scale = 2500
        dsp = c.modifiers.new("disp", "DISPLACE")
        dsp.texture = tex
        dsp.strength = h * 0.35
        dsp.texture_coords = "GLOBAL"
        c.data.materials.append(m)
        c.data.shade_smooth()


# ------------------------------------------------------------------ カメラ
HERO = (0.0, 0.0)


def make_camera():
    sc = bpy.context.scene
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 35
    cam.data.clip_start = 0.5
    cam.data.clip_end = 120000
    tgt = bpy.data.objects.new("cam_target", None)
    sc.collection.objects.link(tgt)
    tc = cam.constraints.new("TRACK_TO")
    tc.target = tgt
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"
    hx, hy = HERO
    keys = []
    # 1頭のアップ(少しずつ回り込む)
    keys.append((0.0, (hx + 7.5, hy - 5.0, 6.5), (hx + 1.2, hy, 2.6)))
    keys.append((tstart("one"), (hx + 6.0, hy - 7.5, 7.0), (hx + 0.8, hy, 2.2)))
    keys.append((tstart("pull") - 0.3, (hx + 3.5, hy - 10.0, 10.0), (hx, hy, 1.5)))
    # 真上へ引いていく(高さは指数的に)
    t0, dur = tstart("pull"), T["pull"]
    for i in range(1, 13):
        u = i / 12
        h = 9.0 * (4600 / 9.0) ** u
        keys.append((t0 + dur * u, (hx + h * 0.08, hy - h * 0.32, h), (hx, hy + h * 0.02, 0.0)))
    # 真上から全体
    keys.append((tstart("top") + T["top"], (h * 0.03, -h * 0.30, h * 1.02), (0, h * 0.02, 0)))
    # ななめから: 東京ドームとくらべる
    dx, dy, _ = DOME_POS
    keys.append((tstart("dome") + 3.0, (dx + 900, dy - 2600, 1500), (dx - 700, dy + 700, 0)))
    keys.append((tstart("dome") + T["dome"] - 0.5, (dx + 500, dy - 2300, 1200), (dx - 900, dy + 900, 0)))
    # 1979年の広さ: 大きく引く
    keys.append((tstart("past") + 4.0, (2500, -9500, 5200), (0, 0, 0)))
    keys.append((tstart("past") + T["past"], (1500, -10500, 5600), (0, 300, 0)))
    keys.append((DURATION, (-800, -9000, 4200), (0, 800, 0)))

    from scipy.interpolate import PchipInterpolator
    tt = np.array([k[0] for k in keys])
    # 高さは対数でつなぐと、引きの速さが自然になる
    P = np.array([k[1] for k in keys])
    A = np.array([k[2] for k in keys])
    lp = PchipInterpolator(tt, np.column_stack([P[:, 0], P[:, 1], np.log(P[:, 2])]), axis=0)
    la = PchipInterpolator(tt, A, axis=0)
    rows = []
    for f in range(1, int(round(DURATION * FPS)) + 1):
        t = min((f - 1) / FPS, tt[-1])
        p = lp(t)
        cam.location = (p[0], p[1], math.exp(p[2]))
        tgt.location = Vector(la(t))
        cam.keyframe_insert("location", frame=f)
        tgt.keyframe_insert("location", frame=f)
    return cam


# ------------------------------------------------------------------ 組み立て
def build(out=None, res=(1280, 720), samples=16):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bl.setup_render(res=res, samples=samples)
    sc.frame_start, sc.frame_end = 1, int(round(DURATION * FPS))
    sc.view_settings.exposure = -1.0
    elev, az = 38.0, -35.0
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.5
    sun.data.color = (1.0, 0.9, 0.78)
    sun.data.angle = math.radians(0.6)
    sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(az))
    sc.collection.objects.link(sun)
    th = math.radians(90 - elev)
    sx, sy = math.sin(math.radians(az)) * math.sin(th), -math.cos(math.radians(az)) * math.sin(th)
    bl.setup_sky(sun_elev=elev, sun_rot=math.degrees(math.atan2(sy, sx)), strength=0.22)

    make_ground()
    make_far_mountains()
    coll, spec, variants = make_variants()
    pts, yaw, scale, var = herd_points()
    tiles = make_tiles(lod_arrays(variants), far_material())
    # タイルの中心
    tx = (np.arange(NX // TILE_X) + 0.5) * TILE_X * CELL_X - SIZE_X / 2
    ty = (np.arange(NY // TILE_Y) + 0.5) * TILE_Y * CELL_Y - SIZE_Y / 2
    TX, TY = np.meshgrid(tx, ty, indexing="ij")
    tc = np.column_stack([TX.ravel(), TY.ravel()])
    near_tile = np.hypot(tc[:, 0] - HERO[0], tc[:, 1] - HERO[1]) < NEAR_R
    rng = np.random.default_rng(9)
    far = tc[~near_tile]
    make_herd(tiles, far, rng.integers(0, 2, len(far)) * math.pi, np.ones(len(far)),
              rng.integers(0, 6, len(far)), name="herd_far")
    # 近くのタイルに入る区画は、1頭ずつ精細なゾウで置く
    half = np.array([TILE_X * CELL_X / 2, TILE_Y * CELL_Y / 2])
    in_near = np.zeros(len(pts), bool)
    for c in tc[near_tile]:
        in_near |= np.all(np.abs(pts - c) <= half + 1e-6, axis=1)
    hero_i = int(np.argmin(np.hypot(pts[:, 0] - HERO[0], pts[:, 1] - HERO[1])))
    sel = in_near.copy()
    sel[hero_i] = False   # 真ん中の1頭は、骨で動く「主役」に置きかえる
    make_herd(coll, pts[sel], yaw[sel], scale[sel], var[sel], name="herd_near")
    rig, ob, _ = bl.make_creature("elephant", location=(HERO[0], HERO[1], 0), rot_z=-22,
                                  frames=(1, sc.frame_end), seed=7)
    for m in {s.material for o in [ob] + list(rig.children) for s in o.material_slots if s.material}:
        if m.name != "Eye":
            add_fog(m)
    tint_by_instance(variants[0].data.materials[0])
    make_dome()
    make_tree_field()
    cam = make_camera()
    sc.camera = cam
    meta = dict(fps=FPS, frames=sc.frame_end, timing=T, n=int(len(pts)), nx=NX, ny=NY,
                cell=[CELL_X, CELL_Y], size=[SIZE_X, SIZE_Y], dome_pos=list(DOME_POS),
                dome_area=DOME_AREA, pop_1979=POP_1979, res=list(res))
    np.save(os.path.splitext(out or "herd")[0] + "_pts.npy", pts.astype(np.float32))
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out))
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--meta")
    ap.add_argument("--test", nargs=2)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--samples", type=int, default=16)
    a = ap.parse_args()
    res = tuple(int(v) for v in a.res.split("x"))
    meta = build(a.out, res=res, samples=a.samples)
    if a.meta:
        json.dump(meta, open(a.meta, "w"), ensure_ascii=False, indent=1)
    if a.test:
        sc = bpy.context.scene
        for fr in a.test[0].split(","):
            sc.frame_set(int(fr))
            sc.render.filepath = os.path.abspath(f"{a.test[1]}{int(fr):04d}.png")
            bpy.ops.render.render(write_still=True)
