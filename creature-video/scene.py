"""本番シーンを組み立てる。

    python scene.py --out scene.blend          # .blend を保存
    python scene.py --test 300 test.png         # 指定フレームを1枚だけ試し描き

サバンナの夕方に、世界の生き物を背の低い順に一列に並べる。
カメラは列に沿って横へ進み、最後に空へ引いてシロナガスクジラを見せる。
"""
import sys, os, math, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from mathutils import Vector

import blender_lib as bl
from blender_lib import _node
from species import SPECIES
import sdf

FPS = bl.FPS

# 並び順(背の低い順)と、となりとのすき間[m]
LINEUP = ["capybara", "panda", "polar_bear", "hippo", "human", "kangaroo", "bison",
          "ostrich", "elephant", "giraffe"]
GAP = {"capybara": 0.9, "panda": 1.0, "polar_bear": 1.2, "hippo": 1.4, "human": 0.9,
       "kangaroo": 1.2, "bison": 1.6, "ostrich": 1.6, "elephant": 2.4, "giraffe": 2.0}
YAW = 200.0   # 生き物の向き(+X 向きの体を回す)。少しカメラ側を向く
WHALE_POS = (0.0, 30.0, 9.0)   # x は列の中央に合わせて後で決める
WHALE_FROM = (150.0, 260.0, 120.0)  # 空の遠くからやってくる

# 時間割(秒)
T_INTRO = 5.0          # 最初のカピバラのアップ
T_EACH = 3.2           # 1種類あたり
T_WHALE = 9.0          # クジラ
T_OUTRO = 5.0          # 全体を見渡す
DURATION = T_INTRO + T_EACH * len(LINEUP) + T_WHALE + T_OUTRO


def frame(t):
    return int(round(t * FPS)) + 1


# ------------------------------------------------------------------ 地面と草
def make_ground():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=600,
                                    location=(40, 120, 0))
    g = bpy.context.active_object
    g.name = "ground"
    # なだらかな起伏(手前の列のあたりは平ら)
    v = np.zeros(len(g.data.vertices) * 3)
    g.data.vertices.foreach_get("co", v)
    v = v.reshape(-1, 3)
    wx, wy = v[:, 0] + 40, v[:, 1] + 120
    flat = np.clip((np.abs(wy - 3) - 10) / 60, 0, 1)
    h = (np.sin(wx * 0.021) * np.cos(wy * 0.017) * 2.5 + np.sin(wx * 0.053 + 1) * 1.2
         + np.cos(wy * 0.041 + 2) * 1.5)
    v[:, 2] = h * flat * flat
    g.data.vertices.foreach_set("co", v.ravel())
    g.data.update()
    g.data.shade_smooth()

    m = bpy.data.materials.new("ground")
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = _node(nt, "ShaderNodeOutputMaterial", (900, 0))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (600, 0), Roughness=0.95)
    L(b.outputs[0], out.inputs[0])
    tc = _node(nt, "ShaderNodeTexCoord", (-1000, 0))
    n1 = _node(nt, "ShaderNodeTexNoise", (-700, 200), Scale=0.08, Detail=8.0, Roughness=0.65)
    n2 = _node(nt, "ShaderNodeTexNoise", (-700, -100), Scale=1.5, Detail=10.0, Roughness=0.7)
    for n in (n1, n2):
        L(tc.outputs["Object"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-400, 200)
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.35, (0.16, 0.11, 0.06, 1)   # 土
    e[1].position, e[1].color = 0.62, (0.42, 0.33, 0.17, 1)   # 枯れ草
    e.new(0.5).color = (0.30, 0.23, 0.11, 1)
    mixf = _node(nt, "ShaderNodeMath", (-550, 200))
    mixf.operation = "MULTIPLY_ADD"
    mixf.inputs[1].default_value = 0.5
    L(n1.outputs["Fac"], mixf.inputs[0])
    L(n2.outputs["Fac"], mixf.inputs[2])
    sub = _node(nt, "ShaderNodeMath", (-480, 50))
    sub.operation = "SUBTRACT"
    L(mixf.outputs[0], sub.inputs[0])
    sub.inputs[1].default_value = 0.25
    L(sub.outputs[0], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = _node(nt, "ShaderNodeBump", (300, -200), Strength=0.4, Distance=0.05)
    n3 = _node(nt, "ShaderNodeTexNoise", (-700, -400), Scale=12.0, Detail=12.0)
    L(tc.outputs["Object"], n3.inputs["Vector"])
    L(n3.outputs["Fac"], bump.inputs["Height"])
    L(bump.outputs[0], b.inputs["Normal"])
    g.data.materials.append(m)
    return g


def grass_material():
    m = bpy.data.materials.new("grass")
    nt = m.node_tree
    nt.nodes.clear()
    out = _node(nt, "ShaderNodeOutputMaterial", (700, 0))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (400, 0), Roughness=0.6)
    b.inputs["Transmission Weight"].default_value = 0.0
    b.inputs["Subsurface Weight"].default_value = 0.0
    nt.links.new(b.outputs[0], out.inputs[0])
    obj = _node(nt, "ShaderNodeObjectInfo", (-600, 0))
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-300, 0)
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (0.30, 0.22, 0.08, 1)
    e[1].position, e[1].color = 1.0, (0.62, 0.50, 0.25, 1)
    e.new(0.55).color = (0.42, 0.36, 0.14, 1)
    e.new(0.8).color = (0.28, 0.30, 0.10, 1)
    nt.links.new(obj.outputs["Random"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def make_grass_blades(n_variants=6):
    """草のかたまり(数本の細い葉)のメッシュをいくつか作る。"""
    rng = np.random.default_rng(1)
    coll = bpy.data.collections.new("grass_src")
    bpy.context.scene.collection.children.link(coll)
    mat = grass_material()
    for vi in range(n_variants):
        verts, faces = [], []
        for _ in range(rng.integers(10, 18)):
            h = rng.uniform(0.15, 0.5)
            w = rng.uniform(0.006, 0.012)
            ang = rng.uniform(0, 2 * math.pi)
            lean = rng.uniform(0.05, 0.4)
            ox, oy = rng.normal(0, 0.05, 2)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx
            base = len(verts)
            segs = 4
            for s in range(segs + 1):
                t = s / segs
                ww = w * (1 - t) + 0.0005
                cx = ox + dx * lean * h * t * t
                cy = oy + dy * lean * h * t * t
                cz = h * t - lean * 0.3 * h * t * t
                verts.append((cx - px * ww, cy - py * ww, cz))
                verts.append((cx + px * ww, cy + py * ww, cz))
            for s in range(segs):
                a = base + 2 * s
                faces.append((a, a + 1, a + 3, a + 2))
        me = bpy.data.meshes.new(f"grass{vi}")
        me.from_pydata(verts, [], faces)
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"grass{vi}", me)
        coll.objects.link(ob)
    coll.hide_render = True
    lc = bpy.context.view_layer.layer_collection.children[coll.name]
    lc.exclude = True
    return coll


def scatter(name, src_coll, area, count, seed, keepout=None, scale=(0.7, 1.3), ground=True):
    """草や木を点として置き、インスタンスとして並べる(頂点に面を持たせる方式)。"""
    rng = np.random.default_rng(seed)
    (x0, x1), (y0, y1) = area
    pts = np.column_stack([rng.uniform(x0, x1, count), rng.uniform(y0, y1, count)])
    if keepout is not None:
        pts = pts[~keepout(pts)]
    objs = list(src_coll.objects)
    made = []
    for i, ob in enumerate(objs):
        sel = pts[i::len(objs)]
        if len(sel) == 0:
            continue
        # 1 種類ごとに「点の雲」を作って、頂点インスタンスで複製する
        me = bpy.data.meshes.new(f"{name}_pts{i}")
        z = ground_height(sel) if ground else np.zeros(len(sel))
        me.from_pydata(np.column_stack([sel, z]).tolist(), [], [])
        holder = bpy.data.objects.new(f"{name}_pts{i}", me)
        bpy.context.scene.collection.objects.link(holder)
        mod = holder.modifiers.new("inst", "NODES")
        mod.node_group = instance_nodes(ob, scale, seed + i)
        made.append(holder)
    return made


def ground_height(xy):
    wx, wy = xy[:, 0], xy[:, 1]
    flat = np.clip((np.abs(wy - 3) - 10) / 60, 0, 1)
    h = (np.sin(wx * 0.021) * np.cos(wy * 0.017) * 2.5 + np.sin(wx * 0.053 + 1) * 1.2
         + np.cos(wy * 0.041 + 2) * 1.5)
    return h * flat * flat


_inst_cache = {}


def sock(node, name, typ):
    return next(s for s in node.inputs if s.name == name and s.type == typ)


def instance_nodes(src, scale, seed):
    key = (src.name, scale, seed)
    if key in _inst_cache:
        return _inst_cache[key]
    ng = bpy.data.node_groups.new(f"inst_{src.name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi = n.new("NodeGroupInput")
    go = n.new("NodeGroupOutput")
    m2p = n.new("GeometryNodeMeshToPoints")
    inst = n.new("GeometryNodeInstanceOnPoints")
    oi = n.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = src
    oi.transform_space = "ORIGINAL"
    rv = n.new("FunctionNodeRandomValue")
    rv.data_type = "FLOAT_VECTOR"
    sock(rv, "Min", "VECTOR").default_value = (0, 0, 0)
    sock(rv, "Max", "VECTOR").default_value = (0.15, 0.15, 6.283)
    rv.inputs["Seed"].default_value = seed
    rs = n.new("FunctionNodeRandomValue")
    rs.data_type = "FLOAT"
    sock(rs, "Min", "VALUE").default_value = scale[0]
    sock(rs, "Max", "VALUE").default_value = scale[1]
    rs.inputs["Seed"].default_value = seed + 7
    L = ng.links.new
    L(gi.outputs[0], m2p.inputs["Mesh"])
    L(m2p.outputs[0], inst.inputs["Points"])
    L(oi.outputs["Geometry"], inst.inputs["Instance"])
    L(rv.outputs["Value"], inst.inputs["Rotation"])
    L(next(o for o in rs.outputs if o.type == "VALUE" and o.enabled), inst.inputs["Scale"])
    L(inst.outputs[0], go.inputs[0])
    _inst_cache[key] = ng
    return ng


# ------------------------------------------------------------------ 木・山
def make_acacia(seed):
    """アカシアの木: 幹と枝は SDF、平たい樹冠は葉のかたまり。"""
    rng = np.random.default_rng(seed)
    bark = (0.18, 0.13, 0.09)
    h = rng.uniform(5.0, 7.5)
    P = sdf.schain([(0, 0, 0, 0.28), (0.2, 0, h * 0.35, 0.2), (0.1, 0, h * 0.55, 0.17)], bark, "t", k=0.2)
    tops = []
    for i in range(rng.integers(3, 5)):
        a = rng.uniform(0, 2 * math.pi) + i * 1.7
        r = rng.uniform(1.5, 3.2)
        top = (math.cos(a) * r, math.sin(a) * r, h + rng.uniform(-0.3, 0.4))
        P += sdf.schain([(0.1, 0, h * 0.55, 0.15), (top[0] * 0.5, top[1] * 0.5, h * 0.8, 0.1),
                         (top[0], top[1], top[2] - 0.2, 0.05)], bark, "t", k=0.1)
        tops.append(top)
    v, f = sdf.build_mesh(P, 0.06)
    me = bpy.data.meshes.new(f"acacia{seed}")
    me.from_pydata(v.tolist(), [], f.tolist())
    me.shade_smooth()
    mb = bpy.data.materials.get("bark") or bpy.data.materials.new("bark")
    mb.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*bark, 1)
    mb.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    me.materials.append(mb)
    tree = bpy.data.objects.new(f"acacia{seed}", me)
    # 樹冠: 平たい楕円体を数個。葉っぽさはボロノイで穴をあけたアルファで出す
    mc = canopy_material()
    for t in tops + [(0, 0, h + 0.3)]:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
        c = bpy.context.active_object
        c.scale = (rng.uniform(2.2, 3.4), rng.uniform(2.2, 3.4), rng.uniform(0.45, 0.7))
        c.location = (t[0], t[1], t[2] + 0.2)
        c.data.materials.append(mc)
        c.data.shade_smooth()
        bpy.context.scene.collection.objects.unlink(c)
        c.parent = tree
        _tree_parts.append(c)
    return tree


_tree_parts = []


def canopy_material():
    m = bpy.data.materials.get("canopy")
    if m:
        return m
    m = bpy.data.materials.new("canopy")
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = _node(nt, "ShaderNodeOutputMaterial", (800, 0))
    mix = _node(nt, "ShaderNodeMixShader", (600, 0))
    tr = _node(nt, "ShaderNodeBsdfTransparent", (400, 150))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (300, -100), Roughness=0.7)
    b.inputs["Subsurface Weight"].default_value = 0.0
    tc = _node(nt, "ShaderNodeTexCoord", (-700, 0))
    vor = _node(nt, "ShaderNodeTexVoronoi", (-400, 200), Scale=9.0)
    vor.feature = "F1"
    L(tc.outputs["Object"], vor.inputs["Vector"])
    noi = _node(nt, "ShaderNodeTexNoise", (-400, -100), Scale=3.0, Detail=4.0)
    L(tc.outputs["Object"], noi.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-150, 200)
    ramp.color_ramp.elements[0].position = 0.40
    ramp.color_ramp.elements[1].position = 0.47
    L(vor.outputs["Distance"], ramp.inputs["Fac"])
    cr = nt.nodes.new("ShaderNodeValToRGB")
    cr.location = (-150, -100)
    cr.color_ramp.elements[0].color = (0.06, 0.09, 0.025, 1)
    cr.color_ramp.elements[1].color = (0.20, 0.22, 0.06, 1)
    L(noi.outputs["Fac"], cr.inputs["Fac"])
    L(cr.outputs["Color"], b.inputs["Base Color"])
    L(ramp.outputs["Color"], mix.inputs["Fac"])
    L(b.outputs[0], mix.inputs[1])
    L(tr.outputs[0], mix.inputs[2])
    L(mix.outputs[0], out.inputs[0])
    return m


def make_trees():
    coll = bpy.data.collections.new("trees_src")
    bpy.context.scene.collection.children.link(coll)
    for s in range(4):
        t = make_acacia(s)
        coll.objects.link(t)
        for c in list(_tree_parts):
            coll.objects.link(c)
        _tree_parts.clear()
    lc = bpy.context.view_layer.layer_collection.children[coll.name]
    lc.exclude = True
    return coll


def make_mountains():
    """遠くの山(キリマンジャロ風の台形の山 + 低い丘)。"""
    # 遠くの山は空気でかすんで見えるので、かすみ色を混ぜる
    m = bpy.data.materials.new("mountain")
    nt = m.node_tree
    nt.nodes.clear()
    out = _node(nt, "ShaderNodeOutputMaterial", (600, 0))
    b = _node(nt, "ShaderNodeBsdfPrincipled", (0, 100), Roughness=1.0)
    b.inputs["Base Color"].default_value = (0.16, 0.14, 0.13, 1)
    em = _node(nt, "ShaderNodeEmission", (0, -150), Strength=1.0)
    em.inputs["Color"].default_value = (0.50, 0.52, 0.58, 1)
    mx = _node(nt, "ShaderNodeMixShader", (300, 0))
    mx.inputs["Fac"].default_value = 0.6
    nt.links.new(b.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    specs = [((60, 900, -5), 380, 75, 12), ((-250, 800, -5), 260, 45, 6), ((380, 820, -5), 300, 55, 8)]
    for i, (loc, r, h, cr) in enumerate(specs):
        bpy.ops.mesh.primitive_cone_add(vertices=128, radius1=r, radius2=cr * 4, depth=h, location=loc)
        c = bpy.context.active_object
        c.location.z = h / 2 - 5
        mod = c.modifiers.new("sub", "SUBSURF")
        mod.levels = mod.render_levels = 3
        tex = bpy.data.textures.new(f"mt{i}", "CLOUDS")
        tex.noise_scale = 60
        d = c.modifiers.new("disp", "DISPLACE")
        d.texture = tex
        d.strength = 18
        d.texture_coords = "GLOBAL"
        c.data.materials.append(m)
        c.data.shade_smooth()


# ------------------------------------------------------------------ 組み立て
def build(out_blend=None, res=(1920, 1080), samples=48, grass_count=220000):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    bl.setup_render(res=res, samples=samples)
    sc.frame_start = 1
    sc.frame_end = frame(DURATION)
    sc.view_settings.exposure = -1.0

    # 太陽: 夕方の光(左手前から)
    elev, az = 22.0, -40.0
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 5.0
    sun.data.color = (1.0, 0.82, 0.62)
    sun.data.angle = math.radians(0.8)
    sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(az))
    sc.collection.objects.link(sun)
    # 空の太陽の位置をライトに合わせる(空は「経度」を +X から測る)
    th = math.radians(90 - elev)
    sx, sy = math.sin(math.radians(az)) * math.sin(th), -math.cos(math.radians(az)) * math.sin(th)
    bl.setup_sky(sun_elev=elev, sun_rot=math.degrees(math.atan2(sy, sx)), strength=0.22)

    make_ground()
    make_mountains()

    # 生き物を並べる
    frames = (1, sc.frame_end)
    placed = []
    x = 0.0
    for i, key in enumerate(LINEUP):
        spec = SPECIES[key]()
        verts, _ = sdf.build_mesh([p for p in spec["prims"]], spec["voxel"] * 2)
        verts = verts * spec.get("scale", 1.0)
        lo, hi = verts.min(0), verts.max(0)
        # 回転後の X 方向の幅でならべる
        c, s_ = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
        corners = np.array([[a, b] for a in (lo[0], hi[0]) for b in (lo[1], hi[1])])
        rx = corners[:, 0] * c - corners[:, 1] * s_
        ry = corners[:, 0] * s_ + corners[:, 1] * c
        x += GAP[key] - rx.min()
        rig, ob, spec = bl.make_creature(key, location=(x, 0, 0), rot_z=YAW, frames=frames, seed=i)
        placed.append(dict(key=key, x=x, cx=x + float(rx.min() + rx.max()) / 2,
                           cy=float(ry.min() + ry.max()) / 2, width=float(rx.max() - rx.min()),
                           depth=float(ry.max() - ry.min()), top=float(hi[2]),
                           length=float(hi[0] - lo[0]), info=spec["info"], rig=rig.name,
                           mesh=ob.name))
        x += rx.max()
    lineup_end = x
    seg = segments(placed)

    # クジラ: 空の遠くから降りてきて、列のうしろにうかぶ
    wx = lineup_end * 0.5 + 4
    W0 = Vector((wx, WHALE_POS[1], WHALE_POS[2]))
    W1 = Vector((wx + WHALE_FROM[0], WHALE_FROM[1], WHALE_FROM[2]))
    rig, ob, spec = bl.make_creature("blue_whale", location=W0, rot_z=180 + 8, frames=frames, seed=99)
    ta, tb = seg["whale"][0] - 0.5, seg["whale"][0] + 4.5
    for f in range(1, sc.frame_end + 1, 2):
        tt = (f - 1) / FPS
        u = 1 - (1 - smooth((tt - ta) / (tb - ta))) ** 2
        p = W1.lerp(W0, u)
        p.z += 0.5 * math.sin(tt * 2 * math.pi / 9.0)
        rig.location = p
        rig.rotation_euler.z = math.radians(180 + 8 + 25 * (1 - u))
        rig.rotation_euler.y = math.radians(-12 * (1 - u))
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_euler", frame=f)
    placed.append(dict(key="blue_whale", x=wx, cx=wx, y=W0.y, z=W0.z, top=W0.z + 2.0, length=28.0,
                       info=spec["info"], rig=rig.name, mesh=ob.name))

    # 毛は重いので、画面に映るあいだだけ描く
    for i, p in enumerate(placed[:-1]):
        mod = bpy.data.objects[p["mesh"]].modifiers.get("fur")
        if mod is None:
            continue
        on = [(seg["land"][max(0, i - 1)][0] - 0.6, seg["land"][min(len(placed) - 2, i + 1)][1] + 0.6),
              (seg["whale"][0] - 0.2, DURATION + 1)]
        if i <= 2:
            on.append((-1, T_INTRO + 0.5))
        state = None
        for f in range(1, sc.frame_end + 1):
            tt = (f - 1) / FPS
            v = any(a <= tt <= b for a, b in on)
            if v != state:
                mod.show_render = v
                mod.keyframe_insert("show_render", frame=f)
                state = v

    # 草と木
    grass = make_grass_blades()
    # 草は3段: 生き物のまわり(短くまばら) / その外側(ふつう) / 遠く(大きめ・まばら)
    x0, x1 = -8.0, lineup_end + 6
    lane = lambda p: (p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > -16) & (p[:, 1] < 4.5)
    scatter("grass_lane", grass, ((x0, x1), (-16, 4.5)), int(grass_count * 0.25), 2, scale=(0.25, 0.6))
    scatter("grass_near", grass, ((-40, lineup_end + 40), (-60, 34)), grass_count, 3,
            keepout=lane, scale=(0.6, 1.3))
    scatter("grass_mid", grass, ((-130, lineup_end + 130), (-150, 34)), int(grass_count * 0.5), 5,
            keepout=lambda p: (p[:, 0] > -40) & (p[:, 0] < lineup_end + 40) & (p[:, 1] > -60),
            scale=(1.2, 2.2))
    scatter("grass_far", grass, ((-200, 300), (34, 300)), int(grass_count * 0.5), 4, scale=(1.4, 2.6),
            ground=True)
    trees = make_trees()
    rng = np.random.default_rng(11)
    tp = np.column_stack([rng.uniform(-120, 220, 40), rng.uniform(45, 320, 40)])
    tp = np.vstack([tp, [[-14, 18], [lineup_end + 14, 22], [22, 40]]])
    for i, (px, py) in enumerate(tp):
        tree_src = [o for o in trees.objects if o.parent is None][i % 4]
        inst = bpy.data.objects.new(f"tree{i}", None)
        inst.instance_type = "COLLECTION"
        sub = bpy.data.collections.get(f"tree_c{i % 4}")
        if sub is None:
            sub = bpy.data.collections.new(f"tree_c{i % 4}")
            sub.objects.link(tree_src)
            for ch in tree_src.children:
                sub.objects.link(ch)
        inst.instance_collection = sub
        inst.location = (px, py, float(ground_height(np.array([[px, py]]))[0]) - 0.2)
        inst.rotation_euler.z = rng.uniform(0, 6.28)
        s = rng.uniform(0.8, 1.25)
        inst.scale = (s, s, s)
        sc.collection.objects.link(inst)

    cam = make_camera(placed, lineup_end)
    sc.camera = cam
    meta = dict(fps=FPS, frames=sc.frame_end, lineup=placed, res=list(res),
                timing=dict(intro=T_INTRO, each=T_EACH, whale=T_WHALE, outro=T_OUTRO))
    if out_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend))
    return meta


# ------------------------------------------------------------------ カメラ
def segments(placed):
    """各生き物・クジラの見せ場の時間(秒)。"""
    land = []
    t = T_INTRO
    for _ in [p for p in placed if p["key"] != "blue_whale"]:
        land.append((t, t + T_EACH))
        t += T_EACH
    return dict(land=land, whale=(t, t + T_WHALE), outro=(t + T_WHALE, DURATION))


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def make_camera(placed, lineup_end):
    sc = bpy.context.scene
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 35
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 8.0
    cam.data.clip_end = 3000
    target = bpy.data.objects.new("cam_target", None)
    sc.collection.objects.link(target)
    tc = cam.constraints.new("TRACK_TO")
    tc.target = target
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"
    focus = bpy.data.objects.new("cam_focus", None)
    sc.collection.objects.link(focus)
    cam.data.dof.focus_object = focus

    # キーとなる構図: (時刻, カメラ位置, 注視点)
    seg = segments(placed)
    keys = []
    first = placed[0]
    keys.append((0.0, (first["cx"] - 2.4, -1.4, 0.32), (first["cx"] + 2.5, 3.5, 0.6)))
    keys.append((T_INTRO * 0.55, (first["cx"] - 1.8, -2.2, 0.42), (first["cx"] + 0.5, 0.8, 0.45)))
    for p, (t0, t1) in zip(placed[:-1], seg["land"]):
        hgt = p["top"]
        dist = max(2.6, p["width"] * 1.3, hgt * 2.5) + p["depth"] * 0.5
        camz = hgt * 0.5 + 0.15
        cx = p["cx"] - 0.06 * dist
        keys.append((t0 + 0.6, (cx - 0.07 * dist, p["cy"] - dist, camz), (cx, p["cy"], hgt * 0.47)))
        keys.append((t1 - 0.6, (cx + 0.07 * dist, p["cy"] - dist, camz), (cx, p["cy"], hgt * 0.47)))
    w = placed[-1]
    g = placed[-2]
    tw0, tw1 = seg["whale"]
    keys.append((tw0 + 1.2, (g["cx"] + 3, -15, 3.0), (g["cx"] + 10, 30, 14.0)))
    keys.append((tw0 + 4.8, (w["cx"] - 4, -36, 5.0), (w["cx"], 20, 8.5)))
    keys.append((tw1 - 0.3, (w["cx"] + 3, -44, 8.0), (w["cx"], 15, 6.5)))
    mid = (placed[0]["cx"] + placed[-2]["cx"]) / 2
    keys.append((DURATION, (mid - 4, -66, 13.0), (mid, 12, 5.0)))

    # 区間ごとに止まらないよう、単調3次補間(PCHIP)で全体をなめらかにつなぐ
    from scipy.interpolate import PchipInterpolator
    T = np.array([k[0] for k in keys])
    cp = PchipInterpolator(T, np.array([k[1] for k in keys]), axis=0)
    ap = PchipInterpolator(T, np.array([k[2] for k in keys]), axis=0)
    for f in range(1, sc.frame_end + 1):
        tt = min(max((f - 1) / FPS, T[0]), T[-1])
        cam.location = Vector(cp(tt))
        target.location = Vector(ap(tt))
        cam.keyframe_insert("location", frame=f)
        target.keyframe_insert("location", frame=f)
        u = smooth((tt - T_INTRO * 0.8) / (T_INTRO * 0.4))
        focus.location = Vector((first["cx"], first["cy"], 0.35)).lerp(target.location, u)
        focus.keyframe_insert("location", frame=f)
    return cam


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--meta")
    ap.add_argument("--test", nargs=2, help="フレーム番号(カンマ区切り) 出力先の接頭辞")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--grass", type=int, default=220000)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    res = tuple(int(v) for v in a.res.split("x"))
    meta = build(a.out, res=res, samples=a.samples, grass_count=a.grass)
    if a.meta:
        json.dump(meta, open(a.meta, "w"), ensure_ascii=False, indent=1)
    if a.test:
        sc = bpy.context.scene
        for fr in a.test[0].split(","):
            sc.frame_set(int(fr))
            sc.render.filepath = os.path.abspath(f"{a.test[1]}{int(fr):04d}.png")
            bpy.ops.render.render(write_still=True)
