#!/bin/bash
# 全種類を確認用にレンダリング
S=${S:-/tmp/creature-preview}; PY=${PY:-python3}
mkdir -p $S
for k in "$@"; do $PY preview.py $k $S/$k.png 2>&1 | grep -iE "error|Trace|line [0-9]" ; done
