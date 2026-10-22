"""c087a_int4_npu_check.py — C-087#1：直接复验「NPU 能否跑 INT4」。

## 为什么要重验（而不是直接引用 C-080/C-081的结论）

C-080f 已经用 dummy prompt 证明 INT4@NPU 确定性输出 `yay`，C-081 据此在 **IR 层面**
排除了 INT4。但按本项目硬性约束，**dummy prompt 的贪心 token 分叉不能作量化精度判据**。
所以这里用**真实音频 prompt + 端到端转写**重跑一遍，回答用户的直接问题
「NPU 能否跑 INT4」。

## 三方对照设计（唯一变量 = 精度 × 设备）

| 组 | decoder IR | 设备 | 用途 |
|---|---|---|---|
| int4_npu | `qwen3-lm-int4sym-cleanie-ov` | NPU | 待验组 |
| int4_cpu | 同上 | CPU | 排除「INT4 权重本身坏」 |
| int8_npu | `qwen3-lm-int8sym-cleanie-ov` | NPU | 现行生产配置作阳性对照 |

encoder 全部固定 @NPU（用 c085a 的 make_all_npu_backend，只换 decoder），
保证 encoder 不是变量。

## 判定

- 若 int4_npu 输出乱码而 int4_cpu 正常 → 「INT4 权重 × NPU 执行」的组合失败（C-081 结论）
- 若 int4_npu 正常 → C-081 的排除需要推翻

输出：reports/c087_int4_npu/{summary.json, transcript_*.txt}
"""
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START_SEC = 720# 与 C-085/C-086 同一起点
SEG_SEC = 40.0                    # 取40 s：够长到能看出乱码，又不跑太久
OUT_DIR = 'reports/c087_int4_npu'
ENC_DIR = 'models/ov-encoder-segment-reviewer'
AUX_DIR = 'models/ov-int8-past'
DIRS = {
    'int4_npu': ('models/qwen3-lm-int4sym-cleanie-ov', 'NPU'),
    'int4_cpu': ('models/qwen3-lm-int4sym-cleanie-ov', 'CPU'),
    'int8_npu': ('models/qwen3-lm-int8sym-cleanie-ov', 'NPU'),
}


def ascii_ratio(s):
    """可打印 ASCII 占比—— 英文转写应≈1；乱码/中文会明显偏低。"""
    if not s:
        return 0.0
    ok = sum(1 for c in s if 32 <= ord(c) < 127)
    return ok / len(s)


def looks_like_gibberish(text):
    """粗判：连续重复、或可打印比例低、或 token 化后无空格结构。"""
    t = text.strip()
    if len(t) < 20:
        return True
    if ascii_ratio(t) < 0.90:
        return True
    words = t.split()
    if len(words) >= 6:
        c4 = {}
        for i in range(len(words) - 3):
            k = tuple(words[i:i + 4])
            c4[k] = c4.get(k, 0) + 1
        if max(c4.values()) >= 4:          # 同一4-gram 重复 4 次以上
            return True
        if len(set(words)) / len(words) < 0.45:   # 词重复率过高
            return True
    return False


def build_backend(dec_dir, dec_device):
    """复用 c085a 的 make_all_npu_backend（enc@NPU），只把 decoder 换到目标设备。"""
    import openvino as ov
    from c085a_smoke_all_npu import make_all_npu_backend

    be = make_all_npu_backend(ENC_DIR, dec_dir, aux_dir=AUX_DIR)
    if dec_device == 'NPU':
        return be                      # make_all_npu_backend 已经把 dec 编到 NPU

    core = ov.Core()
    core.set_property({'CACHE_DIR': './reports/npu_cache'})
    t0 = time.perf_counter()
    be.dec = core.compile_model(
        os.path.join(dec_dir, 'openvino_model.xml'), 'CPU')
    be.npu_compile_s = round(time.perf_counter() - t0, 1)
    return be


def main():
    from seg_stream import SegmentedStreamer
    from c058q_wordcount import save_transcript

    audio, _ = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * START_SEC:SR * (START_SEC + int(SEG_SEC))]
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f'[c087a] 真实音频切片 {len(a)/SR:.1f}s（{START_SEC}–'
          f'{START_SEC + int(SEG_SEC)} s）', flush=True)

    rep = {'note': 'C-087「NPU 能否跑 INT4」直接复验：真实音频 prompt + 端到端转写，'
                   '三方对照（INT4@NPU / INT4@CPU / INT8@NPU），encoder 固定 @NPU。',
           'slice': [START_SEC, START_SEC + int(SEG_SEC)],
           'seg_dur_s': SEG_SEC,
           'enc_device': 'NPU（固定，非变量）',
           'judgement_basis': '真实音频端到端转写（非 dummy prompt token 分叉）',
           'runs': {}}

    for name, (dec_dir, dev) in DIRS.items():
        print(f'\n=== {name}（{dec_dir}@{dev}）', flush=True)
        t0 = time.perf_counter()
        be = build_backend(dec_dir, dev)
        init_s = time.perf_counter() - t0

        for k in ('prefill_ms', 'decode_ms', 'out_tokens', 'enc_ms'):
            be.probe[k].clear()
        t0 = time.perf_counter()
        text, segs = SegmentedStreamer(
            be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
            chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
            max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
            enable_hallucination_reset=False).run(a)
        wall = time.perf_counter() - t0
        tp = save_transcript(segs, f'{OUT_DIR}/transcript_{name}.txt')
        pr = be.probe
        gib = looks_like_gibberish(text)
        d = {
            'decoder_dir': dec_dir, 'decoder_device': dev,
            'backend_init_s': round(init_s, 1),
            'compile_s': be.npu_compile_s,
            'wall_s': round(wall, 2),
            'rtf': round(wall / (len(a) / SR), 4),
            'n_segs': len(segs),
            'n_generate_calls': len(pr['prefill_ms']),
            'words': len(text.split()),
            'ascii_ratio': round(ascii_ratio(text), 4),
            'unique_word_ratio': round(
                len(set(text.split())) / max(1, len(text.split())), 4),
            'prefill_median_ms': round(float(np.median(pr['prefill_ms'])), 1)
            if pr['prefill_ms'] else None,
            'decode_median_ms': round(float(np.median(pr['decode_ms'])), 1)
            if pr['decode_ms'] else None,
            'looks_like_gibberish': bool(gib),
            'transcript_path': tp,
            'text_head': text[:500],
        }
        rep['runs'][name] = d
        print(f'  RTF={d["rtf"]}  segs={d["n_segs"]}  words={d["words"]}  '
              f'ascii={d["ascii_ratio"]}  uniq={d["unique_word_ratio"]}  '
              f'乱码={gib}', flush=True)
        print('  TEXT:', text[:300], flush=True)

    r = rep['runs']
    int4_npu_bad = r['int4_npu']['looks_like_gibberish']
    int4_cpu_ok = not r['int4_cpu']['looks_like_gibberish']
    int8_npu_ok = not r['int8_npu']['looks_like_gibberish']
    rep['verdict'] = {
        'int4_npu_gibberish': bool(int4_npu_bad),
        'int4_cpu_ok': bool(int4_cpu_ok),
        'int8_npu_ok': bool(int8_npu_ok),
        'npu_can_run_int4': bool(not int4_npu_bad),
        'conclusion': (
            'INT4 在 NPU 上输出乱码、同一 IR 在 CPU 上正常、INT8 在 NPU 上正常'
            '→ 失败定位在「INT4 权重 × NPUW 执行」这个组合，C-081 的排除成立。'
            if (int4_npu_bad and int4_cpu_ok and int8_npu_ok)
            else '本次结果与 C-081 记录不一致，需要重新审视排除结论。'),
        'int4_rtf_comparison': {
            'int4_npu': r['int4_npu']['rtf'], 'int4_cpu': r['int4_cpu']['rtf'],
            'int8_npu': r['int8_npu']['rtf'],
            'note': 'RTF 仅供性能参考；int4_npu 的输出不可用，RTF 再低也没有意义。',
        },
    }
    print('\n' + '=' * 70)
    print(rep['verdict']['conclusion'])
    print('=' * 70, flush=True)

    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', f'{OUT_DIR}/summary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
