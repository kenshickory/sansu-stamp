"""保存した .blend の、各フレームのカメラ(位置・向き・レンズ)を JSON に書き出す。

    python export_camera.py scene.blend camera.json
文字や目盛りを重ねるとき、3D の点を画面の位置に変換するのに使う。
"""
import sys, json
import bpy

blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
cam = sc.camera
rows = []
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    m = cam.matrix_world
    rows.append([list(r) for r in m])
json.dump(dict(W=sc.render.resolution_x, H=sc.render.resolution_y, lens=cam.data.lens,
               sensor=cam.data.sensor_width, matrices=rows), open(out, "w"))
print("wrote", out, len(rows))
