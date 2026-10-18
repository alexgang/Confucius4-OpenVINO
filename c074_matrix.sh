#!/usr/bin/env bash
# C-074 #4: wrap the multi-precision multistep matrix in the GPU guard.
# The guard is started as a child and is waited on cleanly (c058l only writes its
# json on a clean exit -- never kill it).
set -u
cd "$(dirname "$0")"
PY="C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe"
TAG="c072_multistep_matrix"
SECS="${1:-2400}"

"$PY" c058l_gpu_guard.py "$$" "$TAG" "$SECS" > "reports/c058_gpu_guard_${TAG}.log" 2>&1 &
GUARD=$!
echo "guard pid=$GUARD watching $$ for ${SECS}s"

C072_IR_LIST=qwen3-lm-int4sym-ov,qwen3-lm-int8sym-ov \
C072_DEV_LIST=CPU,GPU,NPU \
  "$PY" c072f_npuw_multistep.py 2>&1 | tee "reports/c072f_matrix.log"

wait $GUARD
echo "guard exited cleanly"
