"""Blender(bpy) 側の部品: 生き物オブジェクト・素材・骨・しぐさ・環境。"""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix

import sdf
from species import SPECIES

FPS = 24


# ------------------------------------------------------------------ 素材
def _node(nt, kind, loc, **inputs):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in inputs.items():
        n.inputs[k].default_value = v
    return n


def creature_material(name, mat):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = _node(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = _node(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    L(bsdf.outputs[0], out.inputs[0])
    col = _node(nt, "ShaderNodeAttribute", (-800, 200))
    col.attribute_name = "Col"
    rgh = _node(nt, "ShaderNodeAttribute", (-800, -100))
    rgh.attribute_name = "rough"
    tc = _node(nt, "ShaderNodeTexCoord", (-1200, 0))

    # 色むら
    noise = _node(nt, "ShaderNodeTexNoise", (-800, 450), Scale=3.0, Detail=6.0)
    L(tc.outputs["Object"], noise.inputs["Vector"])
    var = _node(nt, "ShaderNodeMapRange", (-550, 450))
    var.inputs["To Min"].default_value = 0.82
    var.inputs["To Max"].default_value = 1.15
    L(noise.outputs["Fac"], var.inputs["Value"])
    base = _node(nt, "ShaderNodeMix", (-300, 250))
    base.data_type = "RGBA"
    base.blend_type = "MULTIPLY"
    base.inputs["Factor"].default_value = 1.0
    L(col.outputs["Color"], base.inputs[6])
    L(var.outputs["Result"], base.inputs[7])
    color_out = base.outputs[2]

    pat = mat.get("pattern")
    if pat == "giraffe":
        vor = _node(nt, "ShaderNodeTexVoronoi", (-800, 800), Scale=mat.get("pattern_scale", 4.5))
        vor.feature = "DISTANCE_TO_EDGE"
        L(tc.outputs["Object"], vor.inputs["Vector"])
        n2 = _node(nt, "ShaderNodeTexNoise", (-1000, 800), Scale=8.0, Detail=3.0)
        L(tc.outputs["Object"], n2.inputs["Vector"])
        warp = _node(nt, "ShaderNodeMix", (-950, 1000))
        warp.data_type = "VECTOR"
        warp.inputs["Factor"].default_value = 0.08
        L(tc.outputs["Object"], warp.inputs[4])
        L(n2.outputs["Color"], warp.inputs[5])
        L(warp.outputs[1], vor.inputs["Vector"])
        edge = _node(nt, "ShaderNodeMapRange", (-550, 800))
        edge.inputs["From Min"].default_value = 0.035
        edge.inputs["From Max"].default_value = 0.06
        L(vor.outputs["Distance"], edge.inputs["Value"])
        # パターンの強さは頂点属性 pmask で制御(脚の先やお腹は薄く)
        pm = _node(nt, "ShaderNodeAttribute", (-550, 1000))
        pm.attribute_name = "pmask"
        mul = _node(nt, "ShaderNodeMath", (-300, 900), )
        mul.operation = "MULTIPLY"
        L(edge.outputs["Result"], mul.inputs[0])
        L(pm.outputs["Fac"], mul.inputs[1])
        mix = _node(nt, "ShaderNodeMix", (0, 500))
        mix.data_type = "RGBA"
        L(mul.outputs[0], mix.inputs["Factor"])
        L(color_out, mix.inputs[6])
        mix.inputs[7].default_value = (*mat["patch"], 1)
        mixc = _node(nt, "ShaderNodeMix", (150, 500))
        mixc.data_type = "RGBA"
        mixc.blend_type = "MULTIPLY"
        mixc.inputs["Factor"].default_value = 1.0
        L(mix.outputs[2], mixc.inputs[6])
        L(var.outputs["Result"], mixc.inputs[7])
        color_out = mixc.outputs[2]
    if pat == "stripes":
        wave = _node(nt, "ShaderNodeTexWave", (-800, 800), Scale=mat.get("pattern_scale", 3.0),
                     Distortion=6.0, Detail=2.0)
        wave.inputs["Detail Scale"].default_value = 1.5
        L(tc.outputs["Object"], wave.inputs["Vector"])
        ramp = _node(nt, "ShaderNodeMapRange", (-550, 800))
        ramp.inputs["From Min"].default_value = 0.45
        ramp.inputs["From Max"].default_value = 0.55
        L(wave.outputs["Fac"], ramp.inputs["Value"])
        pm = _node(nt, "ShaderNodeAttribute", (-550, 1000))
        pm.attribute_name = "pmask"
        mul = _node(nt, "ShaderNodeMath", (-300, 900))
        mul.operation = "MULTIPLY"
        L(ramp.outputs["Result"], mul.inputs[0])
        L(pm.outputs["Fac"], mul.inputs[1])
        mix = _node(nt, "ShaderNodeMix", (0, 500))
        mix.data_type = "RGBA"
        L(mul.outputs[0], mix.inputs["Factor"])
        L(color_out, mix.inputs[6])
        mix.inputs[7].default_value = (*mat["patch"], 1)
        color_out = mix.outputs[2]

    L(color_out, bsdf.inputs["Base Color"])
    L(rgh.outputs["Fac"], bsdf.inputs["Roughness"])

    # しわ / 毛並みのバンプ
    bump_h = None
    if mat.get("wrinkle", 0) > 0:
        w1 = _node(nt, "ShaderNodeTexVoronoi", (-800, -400), Scale=11.0)
        w1.feature = "DISTANCE_TO_EDGE"
        L(tc.outputs["Object"], w1.inputs["Vector"])
        w2 = _node(nt, "ShaderNodeTexNoise", (-800, -650), Scale=40.0, Detail=8.0, Roughness=0.6)
        L(tc.outputs["Object"], w2.inputs["Vector"])
        add = _node(nt, "ShaderNodeMath", (-550, -500))
        add.operation = "ADD"
        L(w1.outputs["Distance"], add.inputs[0])
        L(w2.outputs["Fac"], add.inputs[1])
        bump_h = add.outputs[0]
        strength = 0.25 * mat["wrinkle"]
        crease = _node(nt, "ShaderNodeMapRange", (-300, -300))
        crease.inputs["From Min"].default_value = 0.0
        crease.inputs["From Max"].default_value = 0.05
        crease.inputs["To Min"].default_value = 1.0 - 0.15 * min(mat["wrinkle"], 1.0)
        crease.inputs["To Max"].default_value = 1.0
        L(w1.outputs["Distance"], crease.inputs["Value"])
        cm = _node(nt, "ShaderNodeMix", (350, 300))
        cm.data_type = "RGBA"
        cm.blend_type = "MULTIPLY"
        cm.inputs["Factor"].default_value = 1.0
        L(bsdf.inputs["Base Color"].links[0].from_socket, cm.inputs[6])
        L(crease.outputs["Result"], cm.inputs[7])
        L(cm.outputs[2], bsdf.inputs["Base Color"])
        dist = 0.03
    if mat.get("fur", 0) > 0:
        f = _node(nt, "ShaderNodeTexNoise", (-800, -900), Scale=mat.get("fur_scale", 120.0),
                  Detail=4.0, Roughness=0.7)
        f.noise_dimensions = "3D"
        L(tc.outputs["Object"], f.inputs["Vector"])
        bump_h = f.outputs["Fac"]
        strength = 0.25 * mat["fur"]
        dist = 0.01
        bsdf.inputs["Sheen Weight"].default_value = 0.6 * mat["fur"]
        bsdf.inputs["Sheen Roughness"].default_value = 0.4
        bsdf.inputs["Sheen Tint"].default_value = (1, 1, 1, 1)
    if mat.get("mottle"):
        # クジラの肌のまだら模様
        msc, mcol, mamt = mat["mottle"]
        mn = _node(nt, "ShaderNodeTexNoise", (-800, -1600), Scale=msc, Detail=3.0, Roughness=0.6)
        L(tc.outputs["Object"], mn.inputs["Vector"])
        mr = _node(nt, "ShaderNodeMapRange", (-550, -1600))
        mr.inputs["From Min"].default_value = 0.55
        mr.inputs["From Max"].default_value = 0.68
        mr.inputs["To Max"].default_value = mamt
        L(mn.outputs["Fac"], mr.inputs["Value"])
        mm = _node(nt, "ShaderNodeMix", (500, 600))
        mm.data_type = "RGBA"
        L(mr.outputs["Result"], mm.inputs["Factor"])
        L(bsdf.inputs["Base Color"].links[0].from_socket, mm.inputs[6])
        mm.inputs[7].default_value = (*mcol, 1)
        L(mm.outputs[2], bsdf.inputs["Base Color"])
    if mat.get("dust"):
        dcol, dh = mat["dust"]
        sep = _node(nt, "ShaderNodeSeparateXYZ", (-800, -1200))
        L(tc.outputs["Object"], sep.inputs[0])
        dn = _node(nt, "ShaderNodeTexNoise", (-800, -1400), Scale=2.0, Detail=4.0)
        L(tc.outputs["Object"], dn.inputs["Vector"])
        zz = _node(nt, "ShaderNodeMath", (-550, -1250))
        zz.operation = "MULTIPLY_ADD"
        zz.inputs[1].default_value = dh * 0.6
        L(dn.outputs["Fac"], zz.inputs[0])
        L(sep.outputs["Z"], zz.inputs[2])
        dm = _node(nt, "ShaderNodeMapRange", (-350, -1250))
        dm.inputs["From Min"].default_value = dh * 1.3
        dm.inputs["From Max"].default_value = dh * 0.3
        L(zz.outputs[0], dm.inputs["Value"])
        dmix = _node(nt, "ShaderNodeMix", (450, 450))
        dmix.data_type = "RGBA"
        L(dm.outputs["Result"], dmix.inputs["Factor"])
        L(bsdf.inputs["Base Color"].links[0].from_socket, dmix.inputs[6])
        dmix.inputs[7].default_value = (*dcol, 1)
        L(dmix.outputs[2], bsdf.inputs["Base Color"])
    if mat.get("sss", 0) > 0:
        bsdf.inputs["Subsurface Weight"].default_value = mat["sss"]
        bsdf.inputs["Subsurface Radius"].default_value = (0.4, 0.2, 0.1)
        bsdf.inputs["Subsurface Scale"].default_value = 0.02
    if bump_h is not None:
        bump = _node(nt, "ShaderNodeBump", (300, -400), Strength=strength, Distance=dist)
        L(bump_h, bump.inputs["Height"])
        L(bump.outputs[0], bsdf.inputs["Normal"])
    return m


def eye_material():
    m = bpy.data.materials.get("Eye")
    if m:
        return m
    m = bpy.data.materials.new("Eye")
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.012, 0.008, 1)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["Coat Weight"].default_value = 1.0
    return m


# ------------------------------------------------------------------ 生き物
def make_creature(key, location=(0, 0, 0), rot_z=0.0, scale=1.0, frames=(1, 240),
                  seed=0, idle=True):
    spec = SPECIES[key]()
    prims = spec["prims"]
    verts, faces = sdf.build_mesh(prims, spec["voxel"])
    me = bpy.data.meshes.new(key)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    # 階段状のでこぼこをならし、ポリゴン数を減らしてから色などを計算する
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for _ in range(3):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(key, me)
    bpy.context.scene.collection.objects.link(ob)
    target = spec.get("polys", 70000)
    if len(me.polygons) > target:
        dec = ob.modifiers.new("dec", "DECIMATE")
        dec.ratio = target / len(me.polygons)
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        ob.modifiers.remove(dec)
        ob.data = me2
        bpy.data.meshes.remove(me)
        me = me2
        me.name = key
    me.shade_smooth()
    verts = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", verts)
    verts = verts.reshape(-1, 3)
    color, rough, fur, weights = sdf.vertex_attrs(prims, verts, spec["soft"], spec["bones"].keys())

    a = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    rgba = np.concatenate([color, np.ones((len(color), 1))], axis=1).astype(np.float32)
    lv = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", lv)
    a.data.foreach_set("color", rgba[lv].ravel())
    r = me.attributes.new("rough", "FLOAT", "POINT")
    r.data.foreach_set("value", rough.astype(np.float32))
    if "pmask" in spec:
        pm = me.attributes.new("pmask", "FLOAT", "POINT")
        pm.data.foreach_set("value", spec["pmask"](verts).astype(np.float32))
    me.materials.append(creature_material(key + "_mat", spec["mat"]))

    # 骨
    arm = bpy.data.armatures.new(key + "_rig")
    rig = bpy.data.objects.new(key + "_rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (h, t, parent) in spec["bones"].items():
        eb = arm.edit_bones.new(name)
        eb.head, eb.tail = Vector(h), Vector(t)
    for name, (h, t, parent) in spec["bones"].items():
        if parent:
            arm.edit_bones[name].parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for name, w in weights.items():
        vg = ob.vertex_groups.new(name=name)
        idx = np.nonzero(w > 0.01)[0]
        for i in idx:
            vg.add([int(i)], float(w[i]), "REPLACE")
    mod = ob.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    ob.parent = rig

    # 目
    em = eye_material()
    for pos, rad in spec.get("eyes", []):
        pos, _n = sdf.project_to_surface(prims, pos, sink=rad * 0.4)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rad, location=tuple(pos), segments=24, ring_count=12)
        e = bpy.context.active_object
        e.data.materials.append(em)
        e.data.shade_smooth()
        e.parent = rig
        e.parent_type = "BONE"
        e.parent_bone = spec.get("eye_bone", "head")
        pb = rig.pose.bones[e.parent_bone]
        e.matrix_parent_inverse = (rig.matrix_world @ pb.matrix
                                   @ Matrix.Translation((0, pb.length, 0))).inverted()
    if spec["mat"].get("hair"):
        vg = ob.vertex_groups.new(name="fur")
        for i in np.nonzero(fur > 0.01)[0]:
            vg.add([int(i)], float(min(fur[i], 1.0)), "REPLACE")
        add_fur(ob, spec["mat"]["hair"])
    rig.location = location
    rig.rotation_euler = (0, 0, math.radians(rot_z))
    rig.scale = (scale * spec.get("scale", 1.0),) * 3
    if idle:
        animate_idle(rig, spec, frames, seed)
    return rig, ob, spec


def hair_material(name, h):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = _node(nt, "ShaderNodeOutputMaterial", (600, 0))
    hb = _node(nt, "ShaderNodeBsdfHairPrincipled", (300, 0))
    hb.parametrization = "COLOR"
    hb.inputs["Roughness"].default_value = h.get("rough", 0.45)
    hb.inputs["Radial Roughness"].default_value = 0.6
    hb.inputs["Coat"].default_value = 0.1
    col = _node(nt, "ShaderNodeAttribute", (-400, 0))
    col.attribute_name = "Col"
    info = _node(nt, "ShaderNodeHairInfo", (-400, -250))
    # 根元を少し暗く
    mix = _node(nt, "ShaderNodeMix", (0, 0))
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    rr = _node(nt, "ShaderNodeMapRange", (-200, -250))
    rr.inputs["To Min"].default_value = 0.0
    rr.inputs["To Max"].default_value = 1.0
    nt.links.new(info.outputs["Intercept"], rr.inputs["Value"])
    inv = _node(nt, "ShaderNodeMath", (-100, -350))
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 0.35
    nt.links.new(rr.outputs[0], inv.inputs[1])
    clamp = _node(nt, "ShaderNodeClamp", (0, -350))
    nt.links.new(inv.outputs[0], clamp.inputs[0])
    nt.links.new(clamp.outputs[0], mix.inputs["Factor"])
    # 毛のレンダリングは色が淡く出るので、少し濃くしてから渡す
    gam = _node(nt, "ShaderNodeGamma", (-200, 100))
    gam.inputs["Gamma"].default_value = h.get("gamma", 1.6)
    nt.links.new(col.outputs["Color"], gam.inputs["Color"])
    nt.links.new(gam.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (0.25, 0.25, 0.25, 1)
    # 髪の Color 入力は「メラニン相当の色」なので少し彩度を残して渡す
    nt.links.new(mix.outputs[2], hb.inputs["Color"])
    nt.links.new(hb.outputs[0], out.inputs[0])
    return m


def add_fur(ob, h):
    """パーティクルの毛を生やす。h: length, count, children, radius ..."""
    ob.data.materials.append(hair_material(ob.name + "_hair", h))
    mod = ob.modifiers.new("fur", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    st = ps.settings
    st.type = "HAIR"
    st.count = h.get("count", 4000)
    st.hair_length = h["length"]
    st.hair_step = 4
    st.render_step = 4
    st.display_step = 2
    st.use_advanced_hair = True
    # advanced モードでは「初速 = 毛の長さ」になる
    L = h["length"]
    st.normal_factor = L * h.get("normal", 0.6)
    ax, ay, az = h.get("align", (-0.7, 0.0, -0.3))
    st.object_align_factor = (L * ax, L * ay, L * az)
    st.factor_random = L * h.get("random", 0.3)
    st.material = 2
    st.child_type = "INTERPOLATED"
    st.child_percent = 4
    st.rendered_child_count = h.get("children", 30)
    st.child_length = 1.0
    st.child_length_threshold = 0.2
    st.clump_factor = h.get("clump", 0.2)
    st.roughness_1 = h.get("rough1", 0.004)
    st.roughness_endpoint = h.get("rough_end", 0.01)
    st.root_radius = h.get("root", 0.4)
    st.tip_radius = 0.0
    st.radius_scale = h.get("radius", 0.0012)
    st.use_close_tip = True
    st.use_modifier_stack = False
    st.use_emit_random = True
    st.use_even_distribution = True
    ps.vertex_group_length = "fur"
    ps.vertex_group_density = "fur"
    ps.seed = 3
    return ps


def animate_idle(rig, spec, frames, seed):
    """sin 波の重ね合わせで、ゆったりしたしぐさをキーフレームにする。"""
    f0, f1 = frames
    step = 3
    rng = np.random.default_rng(seed)
    for bname, motions in spec.get("idle", {}).items():
        pb = rig.pose.bones.get(bname)
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        ph = rng.uniform(0, 6.28)
        for f in range(f0, f1 + 1, step):
            t = f / FPS
            e = [0.0, 0.0, 0.0]
            for axis, amp, period, phase in motions:
                i = "xyz".index(axis)
                e[i] += math.radians(amp) * (0.75 * math.sin(2 * math.pi * t / period + phase + ph)
                                             + 0.25 * math.sin(2 * math.pi * t / (period * 0.37) + ph))
            pb.rotation_euler = e
            pb.keyframe_insert("rotation_euler", frame=f)
    if "breath" in spec and "body" in rig.pose.bones:
        amp, period = spec["breath"]
        pb = rig.pose.bones["body"]
        ph = rng.uniform(0, 6.28)
        for f in range(f0, f1 + 1, step):
            s = 1 + amp * math.sin(2 * math.pi * f / FPS / period + ph)
            pb.scale = (s, 1.0, s)  # ボーンのローカルY = 骨の向き(縦)
            pb.keyframe_insert("scale", frame=f)


# ------------------------------------------------------------------ 環境
def setup_render(res=(1920, 1080), samples=64, fps=FPS):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_prefilter = "FAST"
    sc.cycles.denoising_quality = "BALANCED"
    # CPU だけで描くので、光の跳ね返りは少なめ + 簡易GI で時間を節約
    sc.cycles.max_bounces = 3
    sc.cycles.diffuse_bounces = 1
    sc.cycles.glossy_bounces = 1
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.use_fast_gi = True
    sc.cycles.fast_gi_method = "REPLACE"
    sc.cycles.ao_bounces_render = 1
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.film_transparent = False


def setup_sky(sun_elev=18.0, sun_rot=-35.0, strength=1.0):
    w = bpy.data.worlds.new("Sky")
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "NISHITA"):
        try:
            sky.sky_type = t
            break
        except TypeError:
            pass
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_rot)
    sky.altitude = 500
    try:
        sky.air_density = 1.2
        sky.aerosol_density = 1.6
    except AttributeError:
        pass
    sky.sun_disc = False
    bg.inputs["Strength"].default_value = strength
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    return sky
