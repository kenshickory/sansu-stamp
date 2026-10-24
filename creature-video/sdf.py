"""符号付き距離関数(SDF)で生き物の形を作るための小さなライブラリ。

楕円体と「太さの変わるカプセル(round cone)」をなめらかに足し合わせ、
marching cubes でメッシュにする。bpy には依存しない。
"""
import math
import numpy as np
from skimage import measure


def euler_matrix(rx=0.0, ry=0.0, rz=0.0):
    """度数のオイラー角(XYZ順)から回転行列を作る。"""
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = (math.cos(rx), math.sin(rx), math.cos(ry),
                              math.sin(ry), math.cos(rz), math.sin(rz))
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


class Prim:
    """形の部品。geom=False のものは色だけを塗る「ペイント」になる。"""

    def __init__(self, kind, color, bone, k=0.05, geom=True, rough=0.75,
                 op="add", fur=1.0, **p):
        self.kind, self.color, self.bone, self.k = kind, np.array(color), bone, k
        self.geom, self.rough, self.op, self.p = geom, rough, op, p
        self.fur = fur  # 毛の長さの倍率(0 で毛なし)

    # --- 距離 ---
    def dist(self, P):
        if self.kind == "ell":
            c, r, m = self.p["c"], self.p["r"], self.p["m"]
            q = (P - c) @ m  # ワールド→ローカル
            k0 = np.linalg.norm(q / r, axis=1)
            k1 = np.linalg.norm(q / (r * r), axis=1)
            return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
        if self.kind == "cone":
            return _round_cone(P, self.p["a"], self.p["b"], self.p["r1"], self.p["r2"])
        raise ValueError(self.kind)

    def bbox(self):
        if self.kind == "ell":
            R = float(np.max(self.p["r"]))
            c = self.p["c"]
            return c - R, c + R
        a, b = self.p["a"], self.p["b"]
        R = max(self.p["r1"], self.p["r2"])
        return np.minimum(a, b) - R, np.maximum(a, b) + R


def _round_cone(P, a, b, r1, r2):
    """Inigo Quilez の sdRoundCone (任意2点版)。"""
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = P - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - np.outer(y, ba)
    x2 = np.einsum("ij,ij->i", xv, xv)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2
    out = (np.sqrt(x2 + z2) * il2 - r2)
    cond1 = np.sign(z) * a2 * z2 > k
    cond2 = np.sign(y) * a2 * y2 < k
    d_mid = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
    d_a = np.sqrt(x2 + y2) * il2 - r1
    res = np.where(cond1, out, np.where(cond2, d_a, d_mid))
    return res


def ell(c, r, color, bone, rot=(0, 0, 0), **kw):
    return Prim("ell", color, bone, c=np.array(c, float), r=np.array(r, float),
                m=euler_matrix(*rot), **kw)


def cone(a, b, r1, r2, color, bone, **kw):
    return Prim("cone", color, bone, a=np.array(a, float), b=np.array(b, float),
                r1=float(r1), r2=float(r2), **kw)


def chain(points, color, bone, k=0.05, **kw):
    """[(x,y,z,r), ...] を round cone でつなぐ。bone は文字列かリスト。"""
    out = []
    for i in range(len(points) - 1):
        b = bone[i] if isinstance(bone, (list, tuple)) else bone
        p0, p1 = points[i], points[i + 1]
        out.append(cone(p0[:3], p1[:3], p0[3], p1[3], color, b, k=k, **kw))
    return out


def spline(points, n=4):
    """[(x,y,z,r),...] を Catmull-Rom で補間して細かい点列にする。"""
    import numpy as _np
    P = _np.array(points, float)
    P = _np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(n):
            t = j / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return [tuple(p) for p in out]


def schain(points, color, bone, k=0.05, n=4, **kw):
    """なめらかな管(首・しっぽ・鼻など)。bone は元の区間ごとのリストでもよい。"""
    pts = spline(points, n)
    if isinstance(bone, (list, tuple)):
        bone = [bone[min(i // n, len(bone) - 1)] for i in range(len(pts) - 1)]
    return chain(pts, color, bone, k=k, **kw)


def mirror_y(prims_fn):
    """左右対称の部品を作る: prims_fn(sign, side) -> list"""
    return prims_fn(1, "L") + prims_fn(-1, "R")


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax_sub(a, b, k):
    """a から b を滑らかに引く。"""
    h = np.clip(0.5 - 0.5 * (b + a) / k, 0.0, 1.0)
    return a * (1 - h) + (-b) * h + k * h * (1 - h)


def build_mesh(prims, voxel):
    geom = [p for p in prims if p.geom]
    lo = np.min([p.bbox()[0] for p in geom], axis=0) - 4 * voxel
    hi = np.max([p.bbox()[1] for p in geom], axis=0) + 4 * voxel
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    xs = [lo[i] + np.arange(n[i]) * voxel for i in range(3)]
    D = np.full(tuple(n), 1e3, dtype=np.float32)
    for p in geom:
        b0, b1 = p.bbox()
        b0 = b0 - p.k - 2 * voxel
        b1 = b1 + p.k + 2 * voxel
        i0 = np.clip(np.floor((b0 - lo) / voxel).astype(int), 0, n - 1)
        i1 = np.clip(np.ceil((b1 - lo) / voxel).astype(int) + 1, 0, n)
        gx, gy, gz = np.meshgrid(xs[0][i0[0]:i1[0]], xs[1][i0[1]:i1[1]],
                                 xs[2][i0[2]:i1[2]], indexing="ij")
        P = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], axis=1)
        d = p.dist(P).reshape(gx.shape).astype(np.float32)
        sub = D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
        if p.op == "sub":
            D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] = smax_sub(sub, d, p.k)
        else:
            D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]] = smin(sub, d, p.k)
    verts, faces, _, _ = measure.marching_cubes(D, level=0.0, spacing=(voxel,) * 3)
    verts = verts + lo
    return verts, faces


def sdf_eval(prims, P):
    """点群 P での SDF 値(部品を順に合成したもの)。"""
    D = np.full(len(P), 1e3)
    for p in prims:
        if not p.geom:
            continue
        d = p.dist(P)
        D = smax_sub(D, d, p.k) if p.op == "sub" else smin(D, d, p.k)
    return D


def project_to_surface(prims, p, sink=0.0, iters=30):
    """点 p を表面へ寄せ、法線と一緒に返す。sink だけ内側に沈める。"""
    p = np.array(p, float)
    e = 1e-3
    for _ in range(iters):
        P = np.array([p, p + [e, 0, 0], p + [0, e, 0], p + [0, 0, e]])
        d = sdf_eval(prims, P)
        g = (d[1:] - d[0]) / e
        g /= np.linalg.norm(g) + 1e-12
        p = p - d[0] * g
        if abs(d[0]) < 1e-5:
            break
    return p - g * sink, g


def vertex_attrs(prims, verts, soft, bones):
    """頂点ごとの色・粗さ・ボーン重みを求める。"""
    geom = [p for p in prims if p.geom and p.op == "add"]
    D = np.stack([p.dist(verts) for p in geom], axis=1)
    dmin = D.min(axis=1, keepdims=True)
    W = np.exp(-(D - dmin) / soft)
    W /= W.sum(axis=1, keepdims=True)
    cols = np.stack([p.color for p in geom])
    rough = np.array([p.rough for p in geom])
    color = W @ cols
    rgh = W @ rough
    fur = W @ np.array([p.fur for p in geom])
    # ペイント(色だけの部品)を順に重ねる
    for p in prims:
        if p.geom:
            continue
        d = p.dist(verts)
        edge = p.k
        t = np.clip(0.5 - d / (2 * edge), 0, 1)
        t = t * t * (3 - 2 * t)
        color = color * (1 - t[:, None]) + p.color[None, :] * t[:, None]
        rgh = rgh * (1 - t) + p.rough * t
        if p.fur != 1.0:
            fur = fur * (1 - t) + p.fur * t
    # ボーン重みは少し鋭めのソフトミン
    Wb = np.exp(-(D - dmin) / (soft * 0.6))
    weights = {}
    for b in bones:
        idx = [i for i, p in enumerate(geom) if p.bone == b]
        if idx:
            weights[b] = Wb[:, idx].sum(axis=1)
    tot = sum(weights.values())
    for b in weights:
        weights[b] = weights[b] / tot
    return color, rgh, fur, weights
