"""ゾウの群れの動画に、文字・カウンター・目盛りを重ねて mp4 にする。

    python herd_compose.py frames/ meta.json camera.json pts.npy audio.wav font.ttf out.mp4
STILLS=フォルダ を付けると、ある分のフレームだけ PNG に書き出す(確認用)。
"""
import sys, os, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

frames_dir, meta_path, cam_path, pts_path, audio, font_path, out = sys.argv[1:8]
meta = json.load(open(meta_path))
camj = json.load(open(cam_path))
pts = np.load(pts_path)
W, H = camj["W"], camj["H"]
S = W / 1920.0
FPS = meta["fps"]
T = meta["timing"]
N = meta["n"]
SX, SY = meta["size"]
CELL = meta["cell"]
DOME = meta["dome_pos"]
DOME_SIDE = math.sqrt(meta["dome_area"])
SIDE_1979 = math.sqrt(meta["pop_1979"] * CELL[0] * CELL[1])
AREA = N * CELL[0] * CELL[1] / 1e6


def tstart(name):
    t = 0.0
    for k, v in T.items():
        if k == name:
            return t
        t += v


END = sum(T.values())


def font(size, weight=700):
    f = ImageFont.truetype(font_path, int(size * S))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


F_TITLE = font(84, 800)
F_TITLE2 = font(46, 600)
F_NAME = font(60, 800)
F_STAT = font(34, 600)
F_NOTE = font(28, 500)
F_COUNT = font(96, 800)
F_COUNT_L = font(30, 700)
F_LABEL = font(34, 800)
F_SRC = font(20, 500)
WHITE = (255, 255, 255)
ACCENT = (255, 196, 64)
PAST = (255, 120, 90)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def fade(t, t0, t1, fin=0.4, fout=0.4):
    if t < t0 or t > t1:
        return 0.0
    return min(ease((t - t0) / fin), ease((t1 - t) / fout))


def text(d, xy, s, f, fill=WHITE, anchor="la", stroke=3):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=int(stroke * S),
           stroke_fill=(0, 0, 0, 170))


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def paste(base, lay, a):
    if a <= 0.001:
        return base
    if a < 0.999:
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    return Image.alpha_composite(base, lay)


# ------------------------------------------------------------------ 投影
MATS = [np.linalg.inv(np.array(m)) for m in camj["matrices"]]
FOC = camj["lens"] / camj["sensor"]


def project(f, P):
    """世界座標 (n,3) → 画面ピクセル (n,2)、カメラの前にあるか (n,)"""
    P = np.atleast_2d(np.asarray(P, float))
    q = (MATS[f - 1] @ np.column_stack([P, np.ones(len(P))]).T).T
    z = -q[:, 2]
    ok = z > 0.1
    zz = np.where(ok, z, 1)
    x = W / 2 + FOC * q[:, 0] / zz * W
    y = H / 2 - FOC * q[:, 1] / zz * W
    return np.column_stack([x, y]), ok


def polyline(d, f, P, fill, width, dashed=False, steps=60):
    """3D の折れ線を、細かく分けて投影して描く(カメラの後ろは描かない)。"""
    P = np.asarray(P, float)
    for a, b in zip(P[:-1], P[1:]):
        seg = a + (b - a) * np.linspace(0, 1, steps)[:, None]
        xy, ok = project(f, seg)
        for i in range(steps - 1):
            if ok[i] and ok[i + 1] and (not dashed or (i // 2) % 2 == 0):
                d.line([tuple(xy[i]), tuple(xy[i + 1])], fill=fill, width=width)


def square(cx, cy, sx, sy, z=0.5):
    return [(cx - sx / 2, cy - sy / 2, z), (cx + sx / 2, cy - sy / 2, z), (cx + sx / 2, cy + sy / 2, z),
            (cx - sx / 2, cy + sy / 2, z), (cx - sx / 2, cy - sy / 2, z)]


# 画面に映っているゾウの数(フレームごと)
print("counting...", flush=True)
P3 = np.column_stack([pts, np.full(len(pts), 1.5)])
COUNT = []
for f in range(1, meta["frames"] + 1):
    xy, ok = project(f, P3)
    inside = ok & (xy[:, 0] >= 0) & (xy[:, 0] < W) & (xy[:, 1] >= 0) & (xy[:, 1] < H)
    COUNT.append(int(inside.sum()))
print("counted", flush=True)


def jp_big(n):
    man, rest = divmod(n, 10000)
    return f"{man}万{rest:04d}".replace("万0000", "万") if man else f"{n:,}"


def card(base, t, t0, t1, tag, title, lines, tagcol=ACCENT):
    a = fade(t, t0, t1)
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    off = (1 - ease((t - t0) / 0.5)) * -40 * S
    x, y = 70 * S + off, H - (250 + 50 * len(lines)) * S
    grad = Image.new("L", (int(1000 * S), int((300 + 50 * len(lines)) * S)))
    gd = ImageDraw.Draw(grad)
    for i in range(grad.width):
        gd.line([(i, 0), (i, grad.height)], fill=int(160 * (1 - i / grad.width) ** 1.5))
    sh = Image.new("RGBA", grad.size, (0, 0, 0, 0))
    sh.putalpha(grad)
    lay.alpha_composite(sh, (0, H - grad.height))
    if tag:
        tw = d.textlength(tag, font=F_NOTE)
        d.rounded_rectangle([x, y, x + tw + 30 * S, y + 42 * S], radius=int(21 * S), fill=tagcol)
        d.text((x + 15 * S, y + 21 * S), tag, font=F_NOTE, fill=(30, 20, 0), anchor="lm")
    text(d, (x, y + 55 * S), title, F_NAME)
    for i, ln in enumerate(lines):
        text(d, (x, y + (140 + 48 * i) * S), ln, F_STAT if i == 0 else F_NOTE,
             fill=(255, 236, 200) if i == 0 else (235, 235, 235))
    return paste(base, lay, a)


def center_text(base, lines, a, y=0.3):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    yy = H * y
    for s, f, col in lines:
        text(d, (W / 2, yy), s, f, fill=col, anchor="mm", stroke=5)
        yy += f.size * 1.35
    return paste(base, lay, a)


def counter(base, f, a, final=False):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    n = COUNT[f - 1]
    x, y = W - 70 * S, 70 * S
    text(d, (x, y), "画面に映っているゾウ", F_COUNT_L, anchor="ra")
    s = f"約{jp_big(415000)}頭" if final else f"{n:,}頭"
    text(d, (x, y + 45 * S), s, F_COUNT, fill=ACCENT, anchor="ra", stroke=5)
    return paste(base, lay, a)


def herd_outline(base, f, a, labels=True):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    polyline(d, f, square(0, 0, SX, SY, 2), ACCENT, int(4 * S))
    if labels:
        for p, s in (((0, -SY / 2 - 60, 0), f"約{SX / 1000:.1f} km"), ((SX / 2 + 60, 0, 0), f"約{SY / 1000:.1f} km")):
            xy, ok = project(f, [p])
            if ok[0]:
                text(d, tuple(xy[0]), s, F_LABEL, fill=ACCENT, anchor="mm", stroke=4)
    return paste(base, lay, a)


def dome_grid(base, f, a, grow):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    n = int(SX // DOME_SIDE)
    col = (255, 255, 255, 150)
    k = max(1, int(grow * (n + 1)))
    for i in range(1, min(k, n + 1)):
        x = -SX / 2 + i * DOME_SIDE
        polyline(d, f, [(x, -SY / 2, 2), (x, SY / 2, 2)], col, max(1, int(2 * S)), steps=24)
    m = int(SY // DOME_SIDE)
    for j in range(1, min(int(grow * (m + 1)), m + 1)):
        y = -SY / 2 + j * DOME_SIDE
        polyline(d, f, [(-SX / 2, y, 2), (SX / 2, y, 2)], col, max(1, int(2 * S)), steps=24)
    # ドームの印
    xy, ok = project(f, [DOME[:2] + [60], DOME[:2] + [520]])
    if ok.all():
        d.line([tuple(xy[0]), tuple(xy[1])], fill=WHITE, width=int(3 * S))
        text(d, (xy[1][0], xy[1][1] - 8 * S), "東京ドーム", F_LABEL, anchor="md", stroke=4)
    return paste(base, lay, a)


def past_square(base, f, a, grow):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    side_x = SX + (SIDE_1979 - SX) * grow
    side_y = SY + (SIDE_1979 - SY) * grow
    polyline(d, f, square(0, 0, side_x, side_y, 3), PAST, int(5 * S), dashed=True, steps=80)
    if grow > 0.95:
        xy, ok = project(f, [(0, -side_y / 2 - 150, 0)])
        if ok[0]:
            text(d, tuple(xy[0]), f"1979年: 一辺 約{SIDE_1979 / 1000:.1f} km", F_LABEL, fill=PAST,
                 anchor="mm", stroke=4)
    return paste(base, lay, a)


STILLS = os.environ.get("STILLS")
EXPLAIN = os.environ.get("EXPLAIN", "1") == "1"   # 「計算してみよう」パートを入れるか
import explain as EX
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
       "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
ff = None if STILLS else subprocess.Popen(cmd, stdin=subprocess.PIPE)
tp, tt_, td, tpa, to = (tstart(k) for k in ("pull", "top", "dome", "past", "outro"))
_last = [None]


def src_path(f):
    path = os.path.join(frames_dir, f"{f:04d}.png")
    if not os.path.exists(path):
        path = _last[0]   # 1コマおきの下書きは、直前のコマで埋める
    _last[0] = path
    return path


def render_frame(f):
    """レンダリング済みのコマ f に、文字や目盛りを重ねる。"""
    img = Image.open(src_path(f)).convert("RGBA")
    t = (f - 1) / FPS
    img = center_text(img, [("世界中のアフリカゾウを", F_TITLE2, WHITE),
                            ("ぜんぶ1か所に集めたら？", F_TITLE, ACCENT)],
                      fade(t, 0.5, T["intro"] - 0.3, 0.8, 0.6), y=0.2)
    img = card(img, t, tstart("one") + 0.2, tp + 0.6, "アフリカ", "アフリカゾウ",
               ["肩の高さ 約3.3 m ｜ 体重 約6トン（大人のオス）",
                "いま地球にいるのは 推定 約41万5000頭"])
    img = counter(img, f, fade(t, tp - 0.2, tt_ + 0.5, 0.5, 0.4))
    img = counter(img, f, fade(t, tt_ + 0.5, td + 0.3, 0.3, 0.5), final=True)
    img = herd_outline(img, f, fade(t, tt_ + 0.3, tpa + T["past"] - 0.2, 0.6, 0.5), labels=t < td + 0.8)
    img = card(img, t, tt_ + 0.8, td - 0.1, "1頭あたり 6m×3m で計算", f"約{jp_big(415000)}頭",
               [f"一辺 約{SX / 1000:.1f} km の正方形 ／ 広さ 約{AREA:.1f} km²"])
    img = dome_grid(img, f, fade(t, td + 1.0, tpa - 0.1, 0.5, 0.5), ease((t - td - 1.5) / 2.5))
    img = card(img, t, td + 2.0, tpa - 0.1, "広さくらべ", f"東京ドーム 約{AREA * 1e6 / meta['dome_area']:.0f}個分",
               [f"千代田区（約11.7 km²）の 約{AREA / 11.66 * 100:.0f}%",
                "東京ドームの建築面積 約4.7ヘクタールで計算"])
    img = past_square(img, f, fade(t, tpa + 0.5, to + T["outro"], 0.4, 0.6), ease((t - tpa - 1.0) / 3.0))
    img = card(img, t, tpa + 1.0, to - 0.1, "むかしは", "1979年 推定 約130万頭",
               [f"広さは 約{meta['pop_1979'] * CELL[0] * CELL[1] / 1e6:.0f} km²（今の 約3倍）",
                "それから約40年で、3分の1以下に減った"], tagcol=PAST)
    img = center_text(img, [("減ったおもな理由", F_STAT, (255, 236, 200)),
                            ("象牙をねらった密猟 と すみかの減少", F_TITLE2, WHITE)],
                      fade(t, to + 0.2, END + 1, 0.6, 0.6), y=0.22)
    lay = layer()
    d = ImageDraw.Draw(lay)
    text(d, (W - 30 * S, H - 52 * S),
         "数値: IUCN African Elephant Status Report 2016 (約41.5万頭) / 1979年の大陸調査 (約130万頭) / 1頭6m×3mは見せ方のための仮定",
         F_SRC, fill=(230, 230, 230), anchor="rd", stroke=2)
    text(d, (W - 30 * S, H - 24 * S),
         "食べる量・水・フン・重さは動物園や保護団体の資料の目安から平均値を仮定 / お米: 農林水産省 令和6年産水稲の収穫量 (約735万トン)",
         F_SRC, fill=(230, 230, 230), anchor="rd", stroke=2)
    img = paste(img, lay, fade(t, to + 0.5, END + 1, 0.6, 0.6))
    k = ease((t - (END - 0.8)) / 0.8)
    rgb = img.convert("RGB")
    if k > 0:
        rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (0, 0, 0)), k)
    return rgb


def emit(rgb, n):
    if STILLS:
        if n % 12 == 0:
            rgb.save(os.path.join(STILLS, f"c{n:04d}.png"))
        return
    ff.stdin.write(rgb.tobytes())


n = 0
f_cut = int(round(tpa * FPS)) + 1        # ここ(1979年の場面の前)に解説パートを差しこむ
for f in range(1, f_cut):
    if STILLS and not os.path.exists(os.path.join(frames_dir, f"{f:04d}.png")):
        continue
    n += 1
    last_rgb = render_frame(f)
    emit(last_rgb, n)
if EXPLAIN:
    P = EX.Painter(W, H, font_path)
    # 背景に使うコマ(場面ごとに変える)
    bg_frames = dict(intro=int((tt_ + 2) * FPS), weight=130, food=230, water=320, dung=420,
                     row=int((tt_ + 1) * FPS), stack=int((td + 4) * FPS))
    first = True
    for st in EX.STATS:
        bf = bg_frames[st["key"]]
        bg = Image.open(src_path(bf)).convert("RGBA")
        nf = int(round(st["dur"] * FPS))
        for k in range(nf):
            t = k / FPS
            img = EX.draw(P, st, t, bg).convert("RGB")
            # 場面の切りかわりは 0.4 秒のクロスフェード
            if k < 10 and last_rgb is not None:
                img = Image.blend(last_rgb, img, ease((k + 1) / 10))
            n += 1
            emit(img, n)
        last_rgb = img
    fade_from = last_rgb
else:
    fade_from = None
for i, f in enumerate(range(f_cut, meta["frames"] + 1)):
    if STILLS and not os.path.exists(os.path.join(frames_dir, f"{f:04d}.png")):
        continue
    rgb = render_frame(f)
    if fade_from is not None and i < 10:
        rgb = Image.blend(fade_from, rgb, ease((i + 1) / 10))
    n += 1
    emit(rgb, n)
if ff:
    ff.stdin.close()
    ff.wait()
print("done", out, n, "frames")
