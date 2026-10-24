"""解説パートを入れたときの時間割(音づくり用)を meta に追加する。

    python extend_meta.py meta.json meta_ext.json
"""
import sys, json
import explain as EX

meta = json.load(open(sys.argv[1]))
T = {}
for k, v in meta["timing"].items():
    if k == "past":
        T["explain"] = EX.TOTAL
    T[k] = v
cues, t = [], sum(v for k, v in meta["timing"].items() if k not in ("past", "outro"))
for st in EX.STATS:
    cues.append(t)
    t += st["dur"]
meta["timing"] = T
meta["frames"] += int(round(EX.TOTAL * meta["fps"]))
meta["cues"] = cues
json.dump(meta, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
print(meta["frames"], cues)
