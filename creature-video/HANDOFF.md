# 引き継ぎメモ（Codex 向け）

## 1. やりたいこと（依頼者の意図）

YouTube 向けのシリーズ動画「**世界中の〇〇を ぜんぶ1か所に集めたら？**」を作る。

- 1本の動画で **1種類の生き物** にフォーカスする。
- その種の **推定される全個体数** を、Blender の 3D 空間に実際に並べる。
- 1頭のアップ → 上空へ引いて全体 → 身近なものと広さをくらべる → 「計算してみよう」で
  重さ・食べる量・水・フン・1列の長さ・積み上げた高さなど、**計算できることを全部解説** → 昔の頭数とくらべる、という構成。
- 見た目は Blender でできるだけリアルに。文字は日本語、子どもにも分かる言葉で。
- 依頼者の反応：「むっちゃ面白いし見やすい！」（解説入り版まで完成済み）

最初は「いろいろな生き物を1列にならべて大きさくらべ」を作ったが、依頼者の意図は上のとおり
「1種類を全頭集める」だったので、そちらに方向転換した。1列版のスクリプトも残っている（後述）。

## 2. いまの状態

| もの | 状態 |
|---|---|
| アフリカゾウ編 49秒版 `output/elephants.mp4` | 完成（1280×720・24fps） |
| アフリカゾウ編 解説入り 1分40秒版 `output/elephants_explained.mp4` | **完成・最新**。依頼者に渡し済み |
| 下書き `output/elephants_draft.mp4` | 1コマおき版。git 管理外 |
| 次の生き物 | 未着手（候補：パンダ約1,900頭／キリン約11.7万頭／ライオン約2〜2.5万頭／シロナガスクジラ約1〜2.5万頭／ヒト約82億人） |

### ⚠ GitHub に push できていない

- ブランチ `claude/global-creatures-3d-video-562sq1`（リポジトリ `kenshickory/sansu-stamp`）に
  ローカルコミットが6件あるが、push は **403**（Claude の GitHub App がこのリポジトリに書き込めない）。
- 依頼者がアクセス設定を直すまで、コードは同梱の zip（`creature-video-code.zip`）で受け渡す。
- `sansu-stamp` 自体は小学生向け算数アプリのリポジトリで、動画とは無関係。動画用に別リポジトリを作るのが本来はよい。

## 3. 動画の中身（アフリカゾウ編）

| 時間 | 場面 | 内容 |
|---|---|---|
| 0–5秒 | intro | 群れの中の1頭（骨で動く主役）。タイトル |
| 5–9.5秒 | one | 名前カード（肩高約3.3m・体重約6t・推定約41万5000頭） |
| 9.5–21.5秒 | pull | カメラが高さ約9m→約4.6kmへ指数的に上昇。右上に「画面に映っているゾウ」カウンター |
| 21.5–27秒 | top | 真上から全体。一辺約2.7km・約7.5km² |
| 27–35.5秒 | dome | 東京ドーム大の格子（約160個分）、千代田区の約64% |
| 35.5–87秒 | 計算してみよう | ①重さ ②食べる量（1年分とお米の比較）③水 ④フン ⑤1列の長さ ⑥積み上げた高さ |
| 87–100秒 | past / outro | 1979年（約130万頭）の広さを赤い点線で表示 → 減った理由 → 出典 |

### 数字と仮定（画面にも注記あり）

| 項目 | 値 | 根拠 |
|---|---|---|
| 頭数 | 約41万5000頭 | IUCN African Elephant Status Report 2016 |
| 1979年 | 約130万頭 | 1979年の大陸規模調査（Douglas-Hamilton） |
| 1頭の区画 | 6m×3m | **見せ方のための仮定**（455列×912頭=414,960頭） |
| 平均体重 | 3トン | 仮定（子ども・メス込み。大人のオス約6t） |
| 食べる量 | 150kg/日 | 資料により150〜300kg。平均として仮定 |
| 水 | 150L/日 | 資料により120〜300L。平均として仮定 |
| フン | 100kg/日 | 大人は約150kgとも。平均として仮定 |
| 体長・肩高 | 6m・3m | 1列・積み上げの計算用 |
| くらべるもの | 東京ドーム建築面積46,755m²／千代田区11.66km²／東京タワー約4,000t／10tトラック／50mプール2,500t／お米 令和6年産 約734.5万t／日本列島約3,000km／ISS高度約400km | |

食べる量・水・フン・東京タワーの重さは、Web 上の動物園・保護団体・一般記事の目安で、論文ではない。
厳密にするなら一次資料で確認すること。

## 4. ファイル構成（`creature-video/`）

**アフリカゾウ編（今の本流）**

| ファイル | 役割 |
|---|---|
| `herd_scene.py` | シーン生成。地面・遠くの山・群れ（タイル方式）・主役のゾウ・東京ドーム・木・カメラ・かすみ。時間割 `T` もここ |
| `export_camera.py` | 各フレームのカメラ行列を JSON に（文字を3D位置に合わせるため） |
| `render.py` | 連番 PNG にレンダリング。**途中再開可**、`開始 終了 間引き` で1コマおきの下書きも作れる |
| `herd_compose.py` | レンダリング画像に文字・カウンター・格子・点線を重ね、解説パートを差しこんで ffmpeg で mp4 に |
| `explain.py` | 「計算してみよう」カードのデータ（`STATS`）と描画。**別の生き物ではここの数字を差しかえる** |
| `extend_meta.py` | 解説パートを入れたときの時間割を作る（音用） |
| `herd_audio.py` | BGM・風・ゾウの声・効果音を numpy で合成 |

**共通ライブラリ**

| ファイル | 役割 |
|---|---|
| `sdf.py` | 楕円体と round cone を smooth union した SDF → marching cubes でメッシュ化。頂点色・毛の長さ・骨の重み |
| `species.py` | 生き物ごとの形・色・骨・しぐさ・解説文（ゾウ、カピバラ、パンダ、ヒト模型、ホッキョクグマ、カバ、カンガルー、バイソン、ダチョウ、キリン、シロナガスクジラ） |
| `blender_lib.py` | 素材（しわ・模様・まだら・土ぼこり）、パーティクルの毛、骨と待機モーション、レンダリング設定、空 |
| `preview.py` / `batch_preview.sh` | 1種類だけ確認用レンダリング |

**1列にならべる版（最初の方向。今は使っていない）**：`scene.py`, `project_points.py`, `compose.py`, `audio.py`, `make_video.sh`

## 5. 作り方

```bash
python3 -m venv venv
./venv/bin/pip install bpy==5.2.3 numpy scipy scikit-image pillow   # bpy 5.2.3 は Python 3.13 用
# フォント: Noto Sans JP（OFL）。絵文字は /usr/share/fonts/truetype/noto/NotoColorEmoji.ttf を使用
curl -L -o work/NotoSansJP.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"

PY=./venv/bin/python; W=work
$PY herd_scene.py --out $W/herd.blend --meta $W/meta.json --samples 10   # herd_pts.npy も出る
$PY export_camera.py $W/herd.blend $W/camera.json
$PY render.py $W/herd.blend $W/frames 1 1176 2      # まず1コマおき（下書き）
$PY render.py $W/herd.blend $W/frames 2 1176 2      # 残りを埋める
$PY extend_meta.py $W/meta.json $W/meta_ext.json
$PY herd_audio.py $W/meta_ext.json $W/audio_ext.wav
$PY herd_compose.py $W/frames $W/meta.json $W/camera.json $W/herd_pts.npy \
    $W/audio_ext.wav $W/NotoSansJP.ttf output/elephants_explained.mp4
# EXPLAIN=0 で解説なし版、STILLS=フォルダ で確認用の静止画だけ書き出し
```

所要時間（GPUなし・4コアCPU・1280×720・10サンプル）：
アップ約25秒/コマ、上空約12〜15秒/コマ、全1176コマで約5時間。合成は数分。
レンダリングは長いので `nohup setsid ... &` で切り離して動かし、別のループで完了を待つとよい。

## 6. ハマりどころ（重要）

1. **かすみ（発光シェーダー）を混ぜた素材は `mat.cycles.emission_sampling = "NONE"` にする。**
   しないと全部のゾウが光源扱いになり、1コマ100秒近くかかった。
2. **41万個のインスタンスは重い** → 遠くは「40頭を1メッシュに焼いたタイル（6種類）」を約1万個並べ、
   主役の半径70mだけ1頭ずつの精細インスタンスにした。遠景用の素材（`far_material`）はバンプなしで軽量化。
3. ノイズテクスチャの Detail を上げすぎると遅い（2〜4程度に）。
4. Cycles 設定：bounces少なめ + Fast GI（AO置き換え）+ OIDN（prefilter FAST / quality BALANCED）+ persistent data。
5. パーティクルの毛に頂点色を渡すには、色属性を **BYTE_COLOR / CORNER** で持つ（FLOAT_COLOR/POINT だと毛が黒くなる）。
   advanced hair では「初速 = 毛の長さ」なので速度を長さで掛ける。
6. 引きのカメラは高さを対数で補間（`PchipInterpolator`）すると速さが自然。
7. カウンターは `herd_pts.npy` の全点をフレームごとに投影して「画面内の数」を数えている（隠れているものも数える）。
8. `bpy` モジュールでは EEVEE/Workbench は使えない（GPUなし）。Cycles CPU のみ。

## 7. 次にやるとよいこと

- 依頼者に次の生き物を決めてもらう（候補は2章）。`herd_scene.py` の頭数・区画・比較物、
  `explain.py` の `STATS`、`herd_compose.py` の文言を差しかえれば同じ流れで作れる。
  形は `species.py` に追加（パンダ・キリン・クジラ・ヒト模型は既にある）。
- 品質向上の候補：近くのゾウのポーズの種類を増やす、上空から見た群れに陰影のむらを足す、
  ナレーション、縦型ショート版、1080p 化。
- GitHub のアクセスが直ったら push する。
