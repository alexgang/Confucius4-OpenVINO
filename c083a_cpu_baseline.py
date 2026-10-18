"""c083a_cpu_baseline.py — 回答「无GPU 机器能否用 NPU+CPU 做流式ASR」的CPU 基线。

背景：C-082 已把 NPU 阶段的 5 格矩阵定稿，但没回答一个部署问题 ——
    如果目标机是台式机 / 无独显，只有 CPU + NPU，能不能跑流式任务？

要回答它必须先有 CPU 侧的真实数字，仓库里此前没有。本脚本测**全 CPU**
（enc@CPU + dec@CPU）的端到端流式，作为「无 GPU 机器」的纯 CPU 基线，
再与已有的 NPU / GPU 数据对照。

测三组，全部用同一份真实音频、同一段切片、同一个Session 内多步中位口径
（C-069 已确立：每 chunk 新建 InferRequest+reset_state 会多带一倍开销，
交付性能一律用会话内多步中位）：

  cpu_int8 : OVBackend(models/ov-int8-past,   device=CPU)   ← 交付INT8 变体
  cpu_fp16 : OVBackend(models/ov-fp16-past,   device=CPU)   ← 精度基线
  gpu_int8 : OVBackend(models/ov-int8-past,   device=GPU.0) ← 同 IR 上GPU 对照

只跑 3 分钟切片（720–900 s），CPU 上 INT8 decoder 可能很慢，先测长度决定是否续跑。
输出：reports/c083a_cpu_baseline.json
"""
import json
import os
import subprocess
import sys
import time

# 注意：这里**不能**设USE_TORCH=0 —— backends.py 依赖 transformers 的
# GenerationMixin（OVBackend 的 tokenizer 路径）。c080b把「计时」放到子进程里做，
# 父进程才设 USE_TORCH=0；本脚本直接在同进程跑，故保留 transformers 可用。
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from backends import OVBackend
from seg_stream import SegmentedStreamer, _make_segment_state

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000
START_SEC = 720# 12 min，与 c081b 的 GPU 采样切片同起点
SEG_SEC = float(os.environ.get('C083A_SEG_SEC', '180'))
OUT = 'reports/c083a_cpu_baseline.json'

CFGS = [
    ('cpu_int8', 'models/ov-int8-past', 'CPU'),
    ('cpu_fp16', 'models/ov-fp16-past', 'CPU'),
    ('gpu_int8', 'models/ov-int8-past', 'GPU.0'),
]


def run_one(tag, model_dir, device, audio):
    rec = {'tag': tag, 'model_dir': model_dir, 'device': device}
    t0 = time.perf_counter()
    try:
        be = OVBackend(model_dir=model_dir, device=device, precision='f16')
    except Exception as e:
        rec['status'] = 'compile_failed'
        rec['error'] = str(e)[:400]
        print(f'[{tag}] 编译失败: {e}', flush=True)
        return rec
    rec['compile_s'] = round(time.perf_counter() - t0, 1)
    rec['status'] = 'ok'
    print(f'[{tag}] {model_dir} @ {device} 编译 {rec["compile_s"]}s', flush=True)

    state = _make_segment_state(be, unfixed_chunk_num=0, unfixed_token_num=5,
                                chunk_size_sec=0.64, force_language=None,
                                context='')
    streamer = SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio)
    wall = time.perf_counter() - t0

    rec['audio_sec'] = round(len(audio) / SR, 2)
    rec['wall_s'] = round(wall, 2)
    rec['rtf'] = round(wall / (len(audio) / SR), 4)
    rec['n_chunks'] = int(segs[0]['n_chunks']) if segs else 0
    rec['looks_like_speech'] = bool(
        any(c.isalpha() for c in text) and len(text) > 20)
    for k in ('enc_ms', 'prefill_ms', 'decode_ms'):
        v = getattr(be, 'probe', {}).get(k) if hasattr(be, 'probe') else None
        if v:
            rec[k + '_median'] = round(float(np.median(v)), 1)
            rec[k + '_n'] = len(v)
    rec['text_head'] = text[:400]
    print(f'[{tag}] RTF={rec["rtf"]} wall={rec["wall_s"]}s '
          f'人话={rec["looks_like_speech"]}', flush=True)
    print('   ', text[:200].replace('\n', ' '), flush=True)
    return rec


def main():
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR
    a = audio[SR * START_SEC:SR * (START_SEC + int(SEG_SEC))]
    print(f'[c083a] 切片 {START_SEC}s起 {len(a)/SR:.0f}s  CPU 基线测量', flush=True)

    rep = {'note': 'C-082 后的部署问题：无 GPU 机器（NPU+CPU）的 CPU 侧基线。'
                   '会话内多步中位口径（不用每chunk 新建 request）。',
           'cpu': os.environ.get('PROCESSOR_IDENTIFIER', '?'),
           'physical_cores': os.environ.get('NUMBER_OF_PROCESSORS', '?'),
           'seg_start_sec': START_SEC,
           'seg_dur_s': SEG_SEC,
           'runs': {}}
    for tag, md, dev in CFGS:
        rep['runs'][tag] = run_one(tag, md, dev, a)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
