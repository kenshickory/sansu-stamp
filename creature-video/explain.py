"""「計算してみよう」解説パートのカード(重さ・食べる量・水・フン・長さ・高さ)。

数字はすべて「1頭あたりの目安 × 頭数」で計算し、仮定は画面に書く。
herd_compose.py から呼ばれる。
"""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
N = 415_000

# 1頭あたりの目安と、くらべるもの
STATS = [
    dict(key="intro", dur=3.0),
    dict(key="weight", dur=8.0, no="①", title="ぜんぶの重さ", icon="🐘",
         per="1頭 平均 約3トン", total=N * 3, unit="トン", disp="約125万トン",
         comp=dict(icon="🗼", each=4000, label="東京タワー（約4,000トン）の 約310本分"),
         note="※子どもやメスもふくめた平均を約3トンと仮定（大人のオスは約6トン）"),
    dict(key="food", dur=10.0, no="②", title="1日に食べる量", icon="🌿",
         per="1頭 1日 約150kg", total=N * 0.15, unit="トン", disp="約6.2万トン",
         comp=dict(icon="🚚", each=10, label="10トントラック 約6,200台分", per_icon=100, per_label="100台"),
         year=dict(total=N * 0.15 * 365, rice=7_345_000, disp="約2,270万トン", rice_disp="約735万トン"),
         note="※大人は1日に150〜300kgの草や木の葉を食べる。平均150kgで計算"),
    dict(key="water", dur=7.5, no="③", title="1日に飲む水", icon="💧",
         per="1頭 1日 約150L", total=N * 0.15, unit="トン", disp="約6.2万トン",
         comp=dict(icon="🏊", each=2500, label="50mプール（約2,500トン）約25杯分"),
         note="※1日に120〜300リットル飲むとされる。平均150リットルで計算"),
    dict(key="dung", dur=7.0, no="④", title="1日に出るフン", icon="💩",
         per="1頭 1日 約100kg", total=N * 0.1, unit="トン", disp="約4.2万トン",
         comp=dict(icon="🚚", each=10, label="10トントラック 約4,200台分", per_icon=100, per_label="100台"),
         note="※大人は1日に150kgほどとも言われる。子どももふくめ平均100kgで計算"),
    dict(key="row", dur=8.0, no="⑤", title="1列にならべると", icon="🐘",
         per="1頭の長さ 約6m", total=N * 6 / 1000, unit="km", disp="約2,500km", bar=dict(ref=3000, label="日本列島 約3,000km"),
         note="※鼻の先からしっぽまでを約6mとして計算"),
    dict(key="stack", dur=8.0, no="⑥", title="上に積み上げると", icon="🐘",
         per="肩の高さ 約3m", total=N * 3 / 1000, unit="km", disp="約1,250km", tower=dict(ref=400, label="国際宇宙ステーション 高さ約400km"),
         note="※肩の高さ約3mで計算（もちろん本当は積めません）"),
]
TOTAL = sum(s["dur"] for s in STATS)

WHITE = (255, 255, 255)
ACCENT = (255, 196, 64)
SOFT = (255, 236, 200)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


class Painter:
    def __init__(self, W, H, font_path):
        self.W, self.H = W, H
        self.S = W / 1920.0
        self.font_path = font_path
        self._fonts = {}
        self._emoji = {}

    def font(self, size, weight=700):
        k = (size, weight)
        if k not in self._fonts:
            f = ImageFont.truetype(self.font_path, int(size * self.S))
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
            self._fonts[k] = f
        return self._fonts[k]

    def emoji(self, ch, px):
        """カラー絵文字を px の大きさの画像にする(フォントは 109px 固定なので縮小)。"""
        k = (ch, int(px))
        if k not in self._emoji:
            f = ImageFont.truetype(EMOJI_FONT, 109)
            im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((0, 0), ch, font=f, embedded_color=True)
            im = im.crop(im.getbbox() or (0, 0, 1, 1))
            s = px / max(im.size)
            self._emoji[k] = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        return self._emoji[k]

    def text(self, d, xy, s, size, fill=WHITE, anchor="la", weight=700, stroke=3):
        d.text(xy, s, font=self.font(size, weight), fill=fill, anchor=anchor,
               stroke_width=int(stroke * self.S), stroke_fill=(0, 0, 0, 170))


def jp_num(v, unit):
    """124万5000 → 「約125万」のように読みやすく丸める。"""
    if v >= 1e4:
        man = v / 1e4
        if man >= 100:
            return f"約{man:,.0f}万{unit}"
        return f"約{man:.1f}万{unit}".replace(".0万", "万")
    return f"約{v:,.0f}{unit}"


def background(bg, t, dur):
    """背景: レンダリング済みの1枚を、ぼかして暗くし、ゆっくりズーム。"""
    W, H = bg.size
    z = 1.0 + 0.08 * (t / dur)
    w, h = int(W / z), int(H / z)
    im = bg.crop(((W - w) // 2, (H - h) // 2, (W - w) // 2 + w, (H - h) // 2 + h)).resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(6 * W / 1920))
    dark = Image.new("RGBA", (W, H), (8, 10, 16, 170))
    return Image.alpha_composite(im.convert("RGBA"), dark)


def draw(P, st, t, bg):
    """解説カード1枚分(時刻 t は、そのカードの始まりからの秒)。"""
    W, H, S = P.W, P.H, P.S
    img = background(bg, t, st["dur"])
    d = ImageDraw.Draw(img)
    a_in = ease(t / 0.5)
    if st["key"] == "intro":
        y = H * 0.40
        P.text(d, (W / 2, y), "41万5000頭のゾウが 1日くらすと…？", 52, anchor="mm", stroke=5)
        P.text(d, (W / 2, y + 95 * S), "計算してみよう", 84, fill=ACCENT, anchor="mm", weight=800, stroke=6)
        return img

    # 見出し
    x0 = 120 * S
    tw = d.textlength(f"計算してみよう {st['no']}", font=P.font(30))
    d.rounded_rectangle([x0, 70 * S, x0 + tw + 36 * S, 118 * S], radius=int(24 * S), fill=ACCENT)
    d.text((x0 + 18 * S, 94 * S), f"計算してみよう {st['no']}", font=P.font(30), fill=(30, 20, 0), anchor="lm")
    P.text(d, (x0, 140 * S), st["title"], 76, weight=800, stroke=5)

    # 式: [アイコン] 1頭 ◯◯ × 41万5000頭
    ya = 300 * S
    if t > 0.4:
        a = ease((t - 0.4) / 0.4)
        ic = P.emoji(st["icon"], 96 * S)
        img.alpha_composite(ic, (int(x0), int(ya - ic.height / 2)))
        P.text(d, (x0 + 120 * S, ya), st["per"], 50, anchor="lm", stroke=4)
        pw = d.textlength(st["per"], font=P.font(50))
        if t > 1.0:
            P.text(d, (x0 + 140 * S + pw, ya), "×  41万5000頭", 50, fill=SOFT, anchor="lm", stroke=4)
    # 答え(数字がふえていく)
    yb = 430 * S
    if t > 1.6:
        u = ease_out((t - 1.6) / 1.3)
        val = st["total"] * u
        P.text(d, (x0, yb), "＝", 70, fill=WHITE, anchor="lm", stroke=5)
        P.text(d, (x0 + 90 * S, yb), st["disp"] if u >= 0.999 else jp_num(val, st["unit"]), 110, fill=ACCENT, anchor="lm", weight=800, stroke=6)

    yc = 560 * S
    t2 = t - 3.2
    if "comp" in st and t2 > 0:
        c = st["comp"]
        n_real = st["total"] / c["each"]
        per_icon = c.get("per_icon", 1)
        n_icons = int(round(n_real / per_icon))
        P.text(d, (x0, yc), c["label"], 46, fill=WHITE, anchor="lm", stroke=4)
        if per_icon > 1:
            ic_s = P.emoji(c["icon"], 34 * S)
            img.alpha_composite(ic_s, (int(x0), int(yc + 52 * S - ic_s.height / 2)))
            P.text(d, (x0 + 44 * S, yc + 52 * S), f"1つ = {c['per_label']}", 28, fill=SOFT, anchor="lm")
        # アイコンをならべる(右側のエリアに、順にポンポン出す)
        area_x0, area_x1 = W * 0.6, W - 90 * S
        area_y0, area_y1 = 250 * S, H - 120 * S
        cols = max(1, int(math.ceil(math.sqrt(n_icons * (area_x1 - area_x0) / (area_y1 - area_y0)))))
        rows = int(math.ceil(n_icons / cols))
        cell = min((area_x1 - area_x0) / cols, (area_y1 - area_y0) / rows)
        ic = P.emoji(c["icon"], cell * 0.86)
        shown = int(n_icons * ease(t2 / 2.2))
        for i in range(shown):
            r, q = divmod(i, cols)
            img.alpha_composite(ic, (int(area_x0 + q * cell), int(area_y0 + r * cell)))
    if "year" in st and t > 6.0:
        y = st["year"]
        a = ease((t - 6.0) / 0.5)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.rounded_rectangle([x0 - 20 * S, 660 * S, W * 0.5, 900 * S], radius=int(20 * S), fill=(0, 0, 0, 150))
        P.text(dl, (x0, 700 * S), f"1年では {y['disp']}", 46, fill=ACCENT, anchor="lm", stroke=4)
        P.text(dl, (x0, 770 * S), f"日本で1年にとれるお米（{y['rice_disp']}）の", 34, anchor="lm")
        P.text(dl, (x0, 830 * S), f"約{y['total'] / y['rice']:.0f}倍！", 56, fill=ACCENT, anchor="lm", weight=800,
               stroke=5)
        bowl = P.emoji("🍚", 70 * S)
        for i in range(int(round(y["total"] / y["rice"]))):
            lay.alpha_composite(bowl, (int(x0 + 250 * S + i * 85 * S), int(800 * S)))
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
        img = Image.alpha_composite(img, lay)
        d = ImageDraw.Draw(img)

    if "bar" in st and t2 > 0:
        b = st["bar"]
        bx0, bx1, by = x0, W - 140 * S, 700 * S
        full = bx1 - bx0
        ref_w = full
        val_w = full * st["total"] / b["ref"] * ease_out(t2 / 2.5)
        d.rounded_rectangle([bx0, by, bx0 + ref_w, by + 40 * S], radius=int(20 * S), fill=(255, 255, 255, 60),
                            outline=(255, 255, 255), width=int(2 * S))
        P.text(d, (bx0 + ref_w, by - 14 * S), b["label"], 34, anchor="rd")
        d.rounded_rectangle([bx0, by + 70 * S, bx0 + max(val_w, 10), by + 110 * S], radius=int(20 * S), fill=ACCENT)
        ic = P.emoji("🐘", 60 * S)
        img.alpha_composite(ic, (int(bx0 + val_w - 10 * S), int(by + 60 * S)))
        if t2 > 2.6:
            P.text(d, (bx0, by + 170 * S), f"日本列島の 約{st['total'] / b['ref'] * 10:.0f}割の長さ！", 50,
                   fill=ACCENT, anchor="lm", weight=800, stroke=5)

    if "tower" in st and t2 > 0:
        tw_ = st["tower"]
        top, bot = 230 * S, H - 120 * S
        x = W * 0.70
        scale_max = 1400
        ypos = lambda km: bot - (bot - top) * km / scale_max
        d.line([(x - 120 * S, bot), (x + 300 * S, bot)], fill=WHITE, width=int(3 * S))
        P.text(d, (x + 310 * S, bot), "地面", 28, anchor="lm")
        yiss = ypos(tw_["ref"])
        d.line([(x - 160 * S, yiss), (x + 300 * S, yiss)], fill=(160, 210, 255), width=int(3 * S))
        sat = P.emoji("🛰", 70 * S)
        img.alpha_composite(sat, (int(x + 140 * S), int(yiss - 80 * S)))
        P.text(d, (x - 170 * S, yiss), "宇宙ステーション 約400km", 28, fill=(180, 220, 255), anchor="rm")
        h = st["total"] * ease_out(t2 / 2.5)
        d.rounded_rectangle([x, ypos(h), x + 70 * S, bot], radius=int(10 * S), fill=ACCENT)
        ic = P.emoji("🐘", 70 * S)
        img.alpha_composite(ic, (int(x), int(ypos(h) - 70 * S)))
        if t2 > 2.6:
            P.text(d, (x0, 580 * S), f"宇宙ステーションの 約{st['total'] / tw_['ref']:.0f}倍の高さ！", 50,
                   fill=ACCENT, anchor="lm", weight=800, stroke=5)

    # 仮定の注意書き
    P.text(d, (x0, H - 60 * S), st["note"], 26, fill=(225, 225, 225), anchor="lm", weight=500, stroke=2)
    return img
