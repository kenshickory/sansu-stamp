"""BGM と環境音を numpy で合成する(著作権フリー、外部素材なし)。

    python audio.py meta.json out.wav
"""
import sys, json, wave
import numpy as np

meta = json.load(open(sys.argv[1]))
out = sys.argv[2]
SR = 48000
TM = meta["timing"]
n_land = len([i for i in meta["lineup"] if i["key"] != "blue_whale"])
DUR = meta["frames"] / meta["fps"] + 0.5
N = int(DUR * SR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def lowpass(x, cutoff):
    # 1 次の IIR ローパス(簡易)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):
        seg = x[i:i + 4096]
        from scipy.signal import lfilter
        ys, zf = lfilter([1 - a], [1, -a], seg, zi=[acc * a])
        y[i:i + 4096] = ys
        acc = ys[-1]
    return y


L = np.zeros(N)
R = np.zeros(N)

# --- パッド(ゆったりした和音) ---
prog = [[48, 55, 64, 71], [45, 52, 60, 67], [41, 48, 57, 64], [43, 50, 59, 62]]  # C Am F G
bar = 4.0
k = 0
s = 0.0
while s < DUR:
    chord = prog[k % 4]
    n = int((bar + 1.5) * SR)
    i0 = int(s * SR)
    i1 = min(N, i0 + n)
    tt = np.arange(i1 - i0) / SR
    e = env_adsr(i1 - i0, 1.2, 1.8)
    for j, m in enumerate(chord):
        f = midi(m)
        for det, pan in ((-0.12, 0.3), (0.12, 0.7)):
            ph = rng.uniform(0, 6.28)
            w = (np.sin(2 * np.pi * (f + det) * tt + ph) * 0.6
                 + np.sin(2 * np.pi * 2 * (f + det) * tt + ph) * 0.15)
            L[i0:i1] += w * e * 0.035 * (1 - pan)
            R[i0:i1] += w * e * 0.035 * pan
    k += 1
    s += bar

# --- やさしい分散和音(マリンバ風) ---
s = TM["intro"] - 1.0
k = 0
step = 0.5
while s < DUR - 3:
    chord = prog[int((s) / bar) % 4]
    m = chord[[0, 2, 1, 3, 2, 1, 3, 2][k % 8]] + 12
    i0 = int(s * SR)
    n = int(1.2 * SR)
    i1 = min(N, i0 + n)
    tt = np.arange(i1 - i0) / SR
    f = midi(m)
    w = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 4 * f * tt) * np.exp(-tt * 30))
    w *= np.exp(-tt * 4.5) * 0.05
    pan = 0.35 + 0.3 * ((k * 3) % 5) / 4
    L[i0:i1] += w * (1 - pan)
    R[i0:i1] += w * pan
    k += 1
    s += step

# --- 風(ピンクっぽいノイズ) ---
wind = np.cumsum(rng.normal(0, 1, N))
wind -= lowpass(wind, 0.5)
wind = wind / (np.abs(wind).max() + 1e-9)
mod = 0.6 + 0.4 * np.sin(2 * np.pi * t / 7.0) * np.sin(2 * np.pi * t / 3.1 + 1)
L += wind * mod * 0.05
R += np.roll(wind, 1200) * mod * 0.05

# --- 鳥のさえずり(最初だけ) ---
for c in rng.uniform(0.3, TM["intro"] + 6, 9):
    i0 = int(c * SR)
    n = int(0.12 * SR)
    tt = np.arange(n) / SR
    f = rng.uniform(2800, 4200) + 900 * np.sin(2 * np.pi * rng.uniform(18, 30) * tt)
    w = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2 * 0.03
    pan = rng.uniform(0.2, 0.8)
    for rep in range(int(rng.integers(2, 4))):
        j = i0 + rep * int(0.16 * SR)
        if j + n < N:
            L[j:j + n] += w * (1 - pan)
            R[j:j + n] += w * pan

# --- 生き物が出るたびの小さな「ポン」 ---
for i in range(n_land):
    c = TM["intro"] + i * TM["each"] + 0.35
    i0 = int(c * SR)
    n = int(0.4 * SR)
    tt = np.arange(n) / SR
    w = np.sin(2 * np.pi * (660 + 220 * (i % 3)) * tt) * np.exp(-tt * 14) * 0.06
    L[i0:i0 + n] += w
    R[i0:i0 + n] += w

# --- クジラ登場: ふくらむ音 + 低いブーン ---
tw = TM["intro"] + n_land * TM["each"]
i0, i1 = int((tw - 1.5) * SR), int((tw + 2.5) * SR)
tt = np.arange(i1 - i0) / SR
sw = rng.normal(0, 1, i1 - i0)
sw = lowpass(sw, 1500) * np.linspace(0, 1, i1 - i0) ** 2 * 0.12
L[i0:i1] += sw
R[i0:i1] += sw
i0 = int((tw + 2.2) * SR)
n = int(5 * SR)
tt = np.arange(n) / SR
boom = (np.sin(2 * np.pi * 45 * tt) + 0.5 * np.sin(2 * np.pi * 67.5 * tt)) * np.exp(-tt * 0.8) * 0.2
boom *= np.minimum(1, tt / 0.05)
L[i0:i0 + n] += boom
R[i0:i0 + n] += boom
# クジラの声(低くうねる音)
i0 = int((tw + 4.0) * SR)
n = int(3.5 * SR)
tt = np.arange(n) / SR
f = 180 - 60 * tt / tt[-1] + 15 * np.sin(2 * np.pi * 0.7 * tt)
song = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2 * 0.06
L[i0:i0 + n] += song
R[i0:i0 + n] += np.roll(song, 2400)

# 最後はフェードアウト
fo = int(2.0 * SR)
L[-fo:] *= np.linspace(1, 0, fo)
R[-fo:] *= np.linspace(1, 0, fo)
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L / peak * 0.8, R / peak * 0.8
data = (np.column_stack([L, R]) * 32767).astype(np.int16)
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(data.tobytes())
print("wrote", out, DUR)
