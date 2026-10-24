"""保存した .blend を開き、各フレームで「高さの目印」が画面のどこに来るかを JSON に書き出す。

    python project_points.py scene.blend meta.json points.json
"""
import sys, json, math
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

blend, meta_path, out_path = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
cam = sc.camera
meta = json.load(open(meta_path))
W, H = sc.render.resolution_x, sc.render.resolution_y


def to_px(p):
    v = world_to_camera_view(sc, cam, Vector(p))
    return [v.x * W, (1 - v.y) * H, v.z]


frames = []
for f in range(1, meta["frames"] + 1):
    sc.frame_set(f)
    row = {}
    for item in meta["lineup"]:
        info = item["info"]
        if item["key"] == "blue_whale":
            rig = bpy.data.objects[item["rig"]]
            z = rig.location.z
            yaw = rig.rotation_euler.z
            half = item["length"] / 2
            dx, dy = math.cos(yaw) * half, math.sin(yaw) * half
            c = rig.location
            row[item["key"]] = dict(a=to_px((c.x + dx, c.y + dy, z + 2.6)),
                                   b=to_px((c.x - dx, c.y - dy, z + 2.6)),
                                   c=to_px((c.x, c.y, z)))
        else:
            h = info["mark"]
            x, y, hw = item["cx"], item["cy"], item["width"] * 0.5
            row[item["key"]] = dict(top=to_px((x, y, h)), ground=to_px((x, y, 0)),
                                   top_l=to_px((x - hw, y, h)), top_r=to_px((x + hw, y, h)))
    frames.append(row)
json.dump(dict(W=W, H=H, frames=frames), open(out_path, "w"))
print("wrote", out_path, len(frames))
