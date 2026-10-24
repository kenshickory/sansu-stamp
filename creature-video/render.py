"""保存した .blend を連番 PNG にレンダリングする(途中から再開できる)。

    python render.py scene.blend frames/ [開始] [終了] [間引き]
"""
import sys, os, time
import bpy

blend, out = sys.argv[1], sys.argv[2]
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
sc = bpy.context.scene
f0 = int(sys.argv[3]) if len(sys.argv) > 3 else sc.frame_start
f1 = int(sys.argv[4]) if len(sys.argv) > 4 else sc.frame_end
step = int(sys.argv[5]) if len(sys.argv) > 5 else 1
os.makedirs(out, exist_ok=True)
sc.render.use_persistent_data = True
for f in range(f0, f1 + 1, step):
    path = os.path.join(out, f"{f:04d}.png")
    if os.path.exists(path):
        continue
    t = time.time()
    sc.frame_set(f)
    sc.render.filepath = path + ".tmp.png"
    bpy.ops.render.render(write_still=True)
    os.replace(path + ".tmp.png", path)
    print(f"RENDERED {f} {time.time() - t:.1f}s", flush=True)
