#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
PY="C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe"
TAG="c077_lastlogit_multistep"
SECS="${1:-2400}"
"$PY" c058l_gpu_guard.py "$$" "$TAG" "$SECS" > "reports/c058_gpu_guard_${TAG}.log" 2>&1 &
GUARD=$!
echo "guard pid=$GUARD watching $$ for ${SECS}s"
C072_IR_LIST=qwen3-lm-int8sym-lastlogit-ov,qwen3-lm-int4sym-lastlogit-ov \
C072_DEV_LIST=CPU,GPU,NPU \
  "$PY" c072f_npuw_multistep.py 2>&1 | tee "reports/c077_lastlogit_multistep.log"
wait $GUARD
echo "guard exited cleanly"
