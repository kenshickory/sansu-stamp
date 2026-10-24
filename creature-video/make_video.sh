#!/bin/bash
# 全工程: シーン作成 → 目盛り位置 → レンダリング → 音 → 合成
# 使い方: PY=path/to/python ./make_video.sh 作業フォルダ 出力.mp4 [解像度] [サンプル数]
set -e
PY=${PY:-python3}
WORK=$1; OUT=$2; RES=${3:-1280x720}; SAMPLES=${4:-16}
FONT=${FONT:-$WORK/NotoSansJP.ttf}
mkdir -p "$WORK"
cd "$(dirname "$0")"
[ -f "$WORK/scene.blend" ] || $PY scene.py --out "$WORK/scene.blend" --meta "$WORK/meta.json" --res "$RES" --samples "$SAMPLES"
[ -f "$WORK/points.json" ] || $PY project_points.py "$WORK/scene.blend" "$WORK/meta.json" "$WORK/points.json"
$PY render.py "$WORK/scene.blend" "$WORK/frames"
$PY audio.py "$WORK/meta.json" "$WORK/audio.wav"
$PY compose.py "$WORK/frames" "$WORK/meta.json" "$WORK/points.json" "$WORK/audio.wav" "$FONT" "$OUT"
