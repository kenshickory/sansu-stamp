"""ゾウの群れの動画の音: BGM・風・ゾウの低い声・場面の切りかわりの音を numpy で合成する。

    python herd_audio.py meta.json out.wav
"""
import sys, json, wave
import numpy as np
from scipy.signal import lfilter

meta = json.load(open(sys.argv[1]))
out = sys.argv[2]
SR = 48000
T = meta["timing"]
DUR = meta["frames"] / meta["fps"] + 0.5
N = int(DUR * SR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)
L, R = np.zeros(N), np.zeros(N)


def ts(name):
    s = 0.0
    for k, v in T.items():
        if k == name:
            return s
        s += v


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    return lfilter([1 - a], [1, -a], x)


def add(sig, at, pan=0.5, gain=1.0):
    i0 = int(at * SR)
    n = min(len(sig), N - i0)
    if n <= 0:
        return
    L[i0:i0 + n] += sig[:n] * (1 - pan) * gain
    R[i0:i0 + n] += sig[:n] * pan * gain


# パッド: Am - F - C - G をゆっくり(壮大さと少しのさびしさ)
prog = [[45, 52, 60, 64], [41, 48, 57, 60], [48, 55, 64, 67], [43, 50, 59, 62]]
bar = 4.0
k = 0
s = 0.0
while s < DUR:
    n = int((bar + 2) * SR)
    tt = np.arange(n) / SR
    env = np.minimum(1, tt / 1.5) * np.minimum(1, (tt[-1] - tt) / 2.0)
    sig = np.zeros(n)
    for m in prog[k % 4]:
        for det in (-0.15, 0.15):
            sig += np.sin(2 * np.pi * (midi(m) + det) * tt + rng.uniform(0, 6.28)) * 0.5
            sig += np.sin(2 * np.pi * 2 * (midi(m) + det) * tt) * 0.12
    add(sig * env * 0.03, s, pan=0.5)
    k += 1
    s += bar

# 引きの場面から入る、ゆっくりした高音のアルペジオ
s = ts("pull")
k = 0
while s < DUR - 3:
    chord = prog[int(s / bar) % 4]
    m = chord[[0, 1, 2, 3, 2, 1][k % 6]] + 24
    n = int(1.5 * SR)
    tt = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * midi(m) * tt) + 0.3 * np.sin(2 * np.pi * 2 * midi(m) * tt)) * np.exp(-tt * 3)
    add(sig * 0.035, s, pan=0.3 + 0.4 * ((k * 3) % 5) / 4)
    k += 1
    s += 0.5

# 風
w = np.cumsum(rng.normal(0, 1, N))
w -= lowpass(w, 0.4)
w /= np.abs(w).max()
mod = 0.6 + 0.4 * np.sin(2 * np.pi * t / 6.0) * np.sin(2 * np.pi * t / 2.7 + 1)
L += w * mod * 0.05
R += np.roll(w, 1500) * mod * 0.05

# ゾウの低い声(ランブル)と、短い鳴き声
for at, dur in ((1.0, 2.5), (5.5, 2.0)):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f0 = 22 + 6 * np.sin(np.pi * tt / dur)
    sig = sum(np.sin(2 * np.pi * np.cumsum(f0 * h) / SR) / h for h in (1, 2, 3, 4, 5))
    add(sig * np.sin(np.pi * tt / dur) ** 2 * 0.12, at)
n = int(1.1 * SR)
tt = np.arange(n) / SR
f = 450 + 250 * np.sin(np.pi * tt / 1.1) + 30 * np.sin(2 * np.pi * 9 * tt)
tr = sum(np.sin(2 * np.pi * np.cumsum(f * h) / SR) / h for h in (1, 2, 3, 4, 6))
tr = lowpass(tr + 0.3 * rng.normal(0, 1, n), 2500) * np.sin(np.pi * tt / 1.1) ** 0.5 * np.exp(-tt * 1.2)
add(tr * 0.05, 2.6, pan=0.35)

# 引きの場面: だんだん大きくなるうねり
i0, i1 = int(ts("pull") * SR), int(ts("top") * SR)
sw = lowpass(rng.normal(0, 1, i1 - i0), 900) * np.linspace(0, 1, i1 - i0) ** 2.5 * 0.25
L[i0:i1] += sw
R[i0:i1] += sw
# 場面の切りかわりで、やわらかい鐘
for name in ("top", "dome", "past"):
    n = int(3 * SR)
    tt = np.arange(n) / SR
    sig = sum(np.sin(2 * np.pi * midi(m) * tt) * np.exp(-tt * (1.5 + i)) for i, m in enumerate((69, 76, 81)))
    add(sig * 0.06, ts(name) + 0.3)
# 低いブーン(全体が見えた瞬間)
n = int(4 * SR)
tt = np.arange(n) / SR
add((np.sin(2 * np.pi * 40 * tt) + 0.5 * np.sin(2 * np.pi * 60 * tt)) * np.exp(-tt) * np.minimum(1, tt / 0.05) * 0.2,
    ts("top"))

fo = int(2.5 * SR)
L[-fo:] *= np.linspace(1, 0, fo)
R[-fo:] *= np.linspace(1, 0, fo)
peak = max(np.abs(L).max(), np.abs(R).max())
data = (np.column_stack([L, R]) / peak * 0.8 * 32767).astype(np.int16)
with wave.open(out, "wb") as wv:
    wv.setnchannels(2)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes(data.tobytes())
print("wrote", out)
