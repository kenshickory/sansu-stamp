"""1種類の生き物を確認用にレンダリングする: python preview.py elephant out.png [yaw]"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import blender_lib as bl

key, out = sys.argv[1], sys.argv[2]
yaw = float(sys.argv[3]) if len(sys.argv) > 3 else 35.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bl.setup_render(res=(960, 540), samples=24)
bl.setup_sky(sun_elev=25, sun_rot=-60, strength=0.25)
bpy.context.scene.view_settings.exposure = -0.5
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.5
sun.data.angle = math.radians(1.0)
sun.rotation_euler = (math.radians(65), 0, math.radians(-150))
bpy.context.scene.collection.objects.link(sun)
bpy.ops.mesh.primitive_plane_add(size=200)
g = bpy.context.active_object
m = bpy.data.materials.new("g"); m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.28, 0.18, 1)
g.data.materials.append(m)
rig, ob, spec = bl.make_creature(key, idle=False)
bpy.context.view_layer.update()
import numpy as np
bb = np.array([ob.matrix_world @ Vector(c) for c in ob.bound_box])
lo, hi = bb.min(0), bb.max(0)
c = (lo + hi) / 2
size = max(hi[0]-lo[0], (hi[2]-lo[2]) * 1.78, 0.5)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
cam.data.lens = 50
bpy.context.scene.collection.objects.link(cam)
d = size * 1.9
a = math.radians(yaw)
cam.location = (c[0] + d * math.sin(a), c[1] - d * math.cos(a), c[2] + size * 0.15)
cam.rotation_euler = (Vector(c) - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = cam
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
