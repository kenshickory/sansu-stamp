"""レンダリングした連番画像に文字・目盛り・グラフを重ね、音をつけて mp4 にする。

    python compose.py frames/ meta.json points.json audio.wav font.ttf out.mp4
"""
import sys, os, json, math, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

frames_dir, meta_path, pts_path, audio, font_path, out = sys.argv[1:7]
meta = json.load(open(meta_path))
pts = json.load(open(pts_path))
W, H = pts["W"], pts["H"]
S = W / 1920.0  # 1080p 基準の倍率
FPS = meta["fps"]
TM = meta["timing"]
items = meta["lineup"]
land = [it for it in items if it["key"] != "blue_whale"]
whale = [it for it in items if it["key"] == "blue_whale"][0]


def font(size, weight=700):
    f = ImageFont.truetype(font_path, int(size * S))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


F_TITLE = font(84, 800)
F_TITLE2 = font(46, 600)
F_NAME = font(64, 800)
F_STAT = font(34, 600)
F_NOTE = font(28, 500)
F_TAG = font(24, 700)
F_MARK = font(36, 800)
F_CHART = font(19, 600)
F_CHART_T = font(22, 800)

WHITE = (255, 255, 255)
ACCENT = (255, 196, 64)
SHADOW = (0, 0, 0)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def fade(t, t0, t1, fin=0.35, fout=0.35):
    """t0〜t1 の間だけ表示。前後はフェード。"""
    if t < t0 or t > t1:
        return 0.0
    return min(ease((t - t0) / fin), ease((t1 - t) / fout))


def text(d, xy, s, f, fill=WHITE, anchor="la", stroke=3):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=int(stroke * S),
           stroke_fill=(0, 0, 0, 160))


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def paste(base, lay, alpha):
    if alpha <= 0.001:
        return base
    if alpha < 0.999:
        a = lay.getchannel("A").point(lambda v: int(v * alpha))
        lay.putalpha(a)
    return Image.alpha_composite(base, lay)


def dashed(d, p0, p1, fill, width, dash=14, gap=9):
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    s = 0.0
    while s < L:
        e = min(s + dash * S, L)
        d.line([(x0 + ux * s, y0 + uy * s), (x0 + ux * e, y0 + uy * e)], fill=fill, width=width)
        s = e + gap * S


def card(base, t, it, t0, t1, slide=True):
    """左下の説明カード。"""
    a = fade(t, t0, t1)
    if a <= 0:
        return base
    info = it["info"]
    lay = layer()
    d = ImageDraw.Draw(lay)
    off = (1 - ease((t - t0) / 0.5)) * -40 * S if slide else 0
    x, y = 70 * S + off, H - 300 * S
    # 背景のグラデーション
    grad = Image.new("L", (int(900 * S), int(300 * S)))
    gd = ImageDraw.Draw(grad)
    for i in range(grad.width):
        gd.line([(i, 0), (i, grad.height)], fill=int(150 * (1 - i / grad.width) ** 1.5))
    shade = Image.new("RGBA", grad.size, (0, 0, 0, 0))
    shade.putalpha(grad)
    lay.alpha_composite(shade, (0, int(H - 330 * S)))
    tw = d.textlength(info["region"], font=F_TAG)
    d.rounded_rectangle([x, y, x + tw + 30 * S, y + 40 * S], radius=int(20 * S), fill=ACCENT)
    d.text((x + 15 * S, y + 20 * S), info["region"], font=F_TAG, fill=(30, 20, 0), anchor="lm")
    text(d, (x, y + 52 * S), info["name"], F_NAME)
    text(d, (x, y + 140 * S), info["size"] + "　｜　" + info["weight"], F_STAT, fill=(255, 236, 200))
    text(d, (x, y + 192 * S), info["note"], F_NOTE, fill=(230, 230, 230))
    return paste(base, lay, a)


def height_marker(base, t, it, p, t0, t1):
    a = fade(t, t0, t1, 0.5, 0.4)
    if a <= 0 or p["top"][2] <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    (tx, ty, _), (gx, gy, _) = p["top"], p["ground"]
    lx = min(p["top_l"][0], p["top_r"][0]) - 40 * S
    rx = max(p["top_l"][0], p["top_r"][0]) + 40 * S
    grow = ease((t - t0) / 0.8)
    # 地面から上へ伸びる矢印
    ax = rx + 30 * S
    cur = gy + (ty - gy) * grow
    d.line([(ax, gy), (ax, cur)], fill=ACCENT, width=int(5 * S))
    d.line([(ax - 14 * S, gy), (ax + 14 * S, gy)], fill=ACCENT, width=int(5 * S))
    if grow > 0.98:
        d.polygon([(ax, ty - 4 * S), (ax - 12 * S, ty + 18 * S), (ax + 12 * S, ty + 18 * S)], fill=ACCENT)
        dashed(d, (lx, ty), (ax, ty), (255, 255, 255, 230), int(3 * S))
        label = it["info"]["mark_label"]
        text(d, (ax + 18 * S, ty), label, F_MARK, fill=ACCENT, anchor="lm", stroke=4)
    return paste(base, lay, a)


def chart(base, t, upto, alpha):
    """左上の「高さくらべ」グラフ。登場した生き物だけ棒が伸びる。"""
    if alpha <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    x0, y0 = 50 * S, 40 * S
    rowh = 27 * S
    d.rounded_rectangle([x0 - 20 * S, y0 - 14 * S, x0 + 440 * S, y0 + 46 * S + rowh * len(land)],
                        radius=int(16 * S), fill=(0, 0, 0, 120))
    d.text((x0, y0), "高さくらべ", font=F_CHART_T, fill=WHITE)
    maxh = max(it["info"]["mark"] for it in land)
    barw = 230 * S
    for i, it in enumerate(land):
        y = y0 + 40 * S + i * rowh
        info = it["info"]
        cur = i == upto
        col = ACCENT if cur else (255, 255, 255, 220)
        if i > upto:
            col = (255, 255, 255, 70)
        d.text((x0, y + rowh / 2), info["short"], font=F_CHART, fill=col, anchor="lm")
        if i <= upto:
            g = ease((t - it["_t0"]) / 0.8) if cur else 1.0
            w = barw * info["mark"] / maxh * g
            d.rounded_rectangle([x0 + 120 * S, y + 6 * S, x0 + 120 * S + max(w, 4 * S), y + rowh - 6 * S],
                                radius=int(5 * S), fill=col)
            d.text((x0 + 128 * S + w, y + rowh / 2), f'{info["mark"]:g} m', font=F_CHART, fill=col,
                   anchor="lm")
    return paste(base, lay, alpha)


def whale_bracket(base, t, p, t0, t1):
    a = fade(t, t0, t1, 0.6, 0.5)
    if a <= 0 or p["a"][2] <= 0 or p["b"][2] <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    (ax, ay, _), (bx, by, _) = p["a"], p["b"]
    grow = ease((t - t0) / 1.2)
    mx, my = (ax + bx) / 2, (ay + by) / 2
    pa = (mx + (ax - mx) * grow, my + (ay - my) * grow)
    pb = (mx + (bx - mx) * grow, my + (by - my) * grow)
    d.line([pa, pb], fill=ACCENT, width=int(5 * S))
    for q in (pa, pb):
        d.line([(q[0], q[1] - 16 * S), (q[0], q[1] + 16 * S)], fill=ACCENT, width=int(5 * S))
    if grow > 0.95:
        text(d, (mx, my - 14 * S), whale["info"]["mark_label"], F_MARK, fill=ACCENT, anchor="md", stroke=4)
    return paste(base, lay, a)


def center_text(base, lines, a, y=0.32):
    if a <= 0:
        return base
    lay = layer()
    d = ImageDraw.Draw(lay)
    yy = H * y
    for s, f, col in lines:
        text(d, (W / 2, yy), s, f, fill=col, anchor="mm", stroke=5)
        yy += f.size * 1.35
    return paste(base, lay, a)


# 時間割
t = TM["intro"]
for it in land:
    it["_t0"] = t
    t += TM["each"]
T_WHALE0 = t
T_OUT0 = t + TM["whale"]
T_END = T_OUT0 + TM["outro"]

cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
       "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out]
# STILLS=フォルダ を指定すると、ある分のフレームだけ合成して PNG で書き出す(確認用)
STILLS = os.environ.get("STILLS")
ff = None if STILLS else subprocess.Popen(cmd, stdin=subprocess.PIPE)
n = meta["frames"]
last_path = None
for f in range(1, n + 1):
    path = os.path.join(frames_dir, f"{f:04d}.png")
    if not os.path.exists(path):
        if STILLS:
            continue
        # 下書き(1コマおきレンダリング)のときは、直前のコマで埋める
        path = last_path
    last_path = path
    img = Image.open(path).convert("RGBA")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    tt = (f - 1) / FPS
    P = pts["frames"][f - 1]

    img = center_text(img, [("もしも 世界中の生き物を", F_TITLE2, WHITE),
                            ("1か所に集めたら？", F_TITLE, ACCENT)],
                      fade(tt, 0.6, TM["intro"] - 0.6, 0.8, 0.6))
    upto = -1
    for i, it in enumerate(land):
        t0 = it["_t0"]
        if tt >= t0:
            upto = i
        img = height_marker(img, tt, it, P[it["key"]], t0 + 0.3, t0 + TM["each"] - 0.1)
        img = card(img, tt, it, t0 + 0.35, t0 + TM["each"] - 0.15)
    img = chart(img, tt, upto, fade(tt, TM["intro"], T_WHALE0 + 0.5, 0.5, 0.5))
    img = card(img, tt, whale, T_WHALE0 + 2.2, T_OUT0 - 0.2)
    img = whale_bracket(img, tt, P["blue_whale"], T_WHALE0 + 2.5, T_OUT0 + 1.5)
    img = center_text(img, [("シロナガスクジラ 1頭 ＝ ヒト 約18人分の長さ", F_TITLE2, WHITE),
                            ("地球の生き物は、こんなに大きさがちがう", F_STAT, (255, 236, 200))],
                      fade(tt, T_OUT0 + 0.3, T_END + 1, 0.6, 0.6), y=0.16)
    # 最後は黒へフェードアウト
    k = ease((tt - (T_END - 0.8)) / 0.8)
    rgb = img.convert("RGB")
    if k > 0:
        rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (0, 0, 0)), k)
    if STILLS:
        rgb.save(os.path.join(STILLS, f"c{f:04d}.png"))
        continue
    ff.stdin.write(rgb.tobytes())
    if f % 100 == 0:
        print("composed", f, "/", n, flush=True)
if ff:
    ff.stdin.close()
    ff.wait()
print("done", out)
