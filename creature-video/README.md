# 世界の生き物 大きさくらべ（Blender 3D 動画）

「もしも世界中の生き物を1か所に集めたら？」を、Blender で作った3D映像で見せる約50秒の動画です。
サバンナの夕方に、背の低い順に生き物が並び、カメラが横に進みながら1種類ずつ紹介します。
最後にシロナガスクジラが空から降りてきて、全員と長さをくらべます。

| 順番 | 生き物 | 地域 | 高さの目安 |
|---|---|---|---|
| 1 | カピバラ | 南アメリカ | 0.6 m |
| 2 | ジャイアントパンダ | アジア（中国） | 0.75 m |
| 3 | ホッキョクグマ | 北極 | 1.5 m |
| 4 | カバ | アフリカ | 1.5 m |
| 5 | ヒト（模型） | 世界中 | 1.7 m |
| 6 | アカカンガルー | オーストラリア | 1.8 m |
| 7 | アメリカバイソン | 北アメリカ | 1.9 m |
| 8 | ダチョウ | アフリカ | 2.5 m |
| 9 | アフリカゾウ | アフリカ | 3.3 m |
| 10 | キリン | アフリカ | 5.5 m |
| 最後 | シロナガスクジラ | 世界中の海 | 体長 約30 m |

数値は代表的な成体（おもにオス）のおおよその値です。

## しくみ

外部の3Dモデルや画像・音源は使っていません。すべてスクリプトから作っています。

- **形**: 楕円体と「太さの変わるカプセル」をなめらかにつなぐ SDF（符号付き距離関数）で各生き物を実物大で組み立て、marching cubes でメッシュにします（`sdf.py`, `species.py`）。
- **毛**: パーティクルの毛を生やし、部位ごとに長さを変えています（顔は短く、バイソンの肩は長く、など）。
- **動き**: 骨（アーマチュア）を自動で入れ、鼻・耳・しっぽ・首がゆっくり動き、呼吸で体がふくらみます。
- **舞台**: 起伏のある地面、数十万本の草、アカシアの木、遠くの山、物理ベースの空。
- **文字・目盛り**: レンダリング後に Python(Pillow) で、名前カード・高さの矢印・「高さくらべ」グラフを重ねます（`compose.py`）。
- **音**: BGM・風・鳥・クジラの声も numpy で合成しています（`audio.py`）。

## 作り方

Blender 5.2 の Python モジュール（`pip install bpy==5.2.3`、Python 3.13）と `numpy scipy scikit-image pillow`、`ffmpeg` が必要です。
フォントは Noto Sans JP（Google Fonts、OFL）を使っています。

```bash
python -m venv venv && ./venv/bin/pip install bpy==5.2.3 numpy scipy scikit-image pillow
# フォントを作業フォルダに置く
curl -L -o work/NotoSansJP.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
PY=./venv/bin/python ./make_video.sh work out.mp4 1280x720 16
```

1つの生き物だけ確認したいときは `python preview.py elephant elephant.png` です。

CPU だけ（4コア）で 1280×720・16サンプルだと 1コマ 約25秒、全1225コマで 8〜9時間かかります。
`render.py` は途中から再開でき、`render.py scene.blend frames 1 1225 2` のように1コマおきに描いて下書きを先に作れます。

| ファイル | 中身 |
|---|---|
| `sdf.py` | 形を作る SDF とメッシュ化、頂点の色・毛の長さ・骨の重み |
| `species.py` | 生き物ごとの形・色・骨・しぐさ・解説文 |
| `blender_lib.py` | 素材（皮ふのしわ・模様・毛）、骨、しぐさ、レンダリング設定、空 |
| `scene.py` | サバンナの舞台・並べ方・カメラワーク・時間割 |
| `render.py` | 連番 PNG にレンダリング（再開可） |
| `project_points.py` | 高さの目印が画面のどこに来るかを計算 |
| `audio.py` | BGM と効果音の合成 |
| `compose.py` | 文字・目盛り・グラフを重ねて mp4 に |
| `make_video.sh` | 上の全部を順に実行 |
