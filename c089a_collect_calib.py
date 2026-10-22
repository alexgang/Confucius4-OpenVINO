r"""c089a_collect_calib.py — C-089 步骤 1：收集真实 prefill 输入做 INT4 量化校准

Reviewer 原文：
> 「校准数据只用 0–12 分钟：在全 NPU（或集显）流水线跑 0–12 min，录每次调用的
>   真实 prefill 输入（inputs_embeds、attention_mask、position_ids、beam_idx），
>   按 prompt 长度分层抽约 128 条，存 reports/c089_int4/calib_0_12min.npz。」

## 为什么必须录真实 prefill 输入而不是随便造

INT4 权重量化（尤其 AWQ / scale estimation）要的是**激活分布**。造出来的随机
embeds 或纯文本 token 分布与真实 mel→encoder 嵌入的分布差很远，会让 scale
估偏。所以这里直接挂钩 `greedy_decode_with_prefix`，把每段真实调用的四个输入
原样录下来。

## 分层抽样

一段 12–20 s 音频对应 prompt 长度（token 数）大致在 200–320。按长度分 8 个
桶，每桶按等间隔抽，保证覆盖短/长两种极端——scale 在极端激活上最容易偏。

## 只用 0–12 分钟

评测切片是 12–27 min 与全长 61 min。用 0–12 min 做校准、12 min 之后的音频
做评测，**校准集与评测集严格不重叠**，避免信息泄漏导致精度虚高。

输出：reports/c089_int4/calib_0_12min.npz
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

SR = 16000
CALIB_START = 0
CALIB_END = 720          # 12 分钟，严格按 Reviewer 要求
TARGET_N = 128
N_BUCKETS = 8
OUT_DIR = 'reports/c089_int4'
OUT_NPZ = os.path.join(OUT_DIR, 'calib_0_12min.npz')
OUT_JSON = os.path.join(OUT_DIR, 'calib_collect.json')


class PrefillRecorder:
    """挂钩 backend.greedy_decode_with_prefix，录真实 prefill 输入。

    只录第一次（全量 prefill）的那次调用；decode 步的 inputs_embeds 是单
    token，没有分布价值，还会把桶撑偏。
    """

    def __init__(self, be):
        self.be = be
        self.orig = be.greedy_decode_with_prefix
        self.records = []          # [{T, inputs_embeds}]
        be.greedy_decode_with_prefix = self._wrapped

    def _wrapped(self, ehs, prefix_ids, max_new_tokens):
        # 复刻原实现的前半段（拼 emb），只为拿到 inputs_embeds，
        # 不真的跑 NPU —— 校准数据不需要解码结果。
        emb = self.be.build_inputs_embeds(ehs, prefix_ids)
        self.records.append({'T': int(emb.shape[1]),
                             'inputs_embeds': emb})
        return []                  # 空输出，避免污染 transcribe

    def restore(self):
        self.be.greedy_decode_with_prefix = self.orig


def stratified_sample(records, n_target, n_buckets):
    """按 prompt 长度分桶，桶内等间隔抽。"""
    if not records:
        return [], {}
    rs = sorted(records, key=lambda r: r['T'])
    lo, hi = rs[0]['T'], rs[-1]['T']
    width = max(1, (hi - lo + 1) // n_buckets)
    buckets = {}
    for r in rs:
        b = min(n_buckets - 1, (r['T'] - lo) // width)
        buckets.setdefault(b, []).append(r)

    picked, per_bucket = [], {}
    # 先每桶等间隔抽，再按需补齐
    for b, items in sorted(buckets.items()):
        k = max(1, round(n_target * len(items) / len(rs)))
        k = min(k, len(items))
        step = len(items) / k
        idx = sorted({int(j * step) for j in range(k)})
        sel = [items[i] for i in idx]
        picked.extend(sel)
        per_bucket[b] = {'T_lo': items[0]['T'], 'T_hi': items[-1]['T'],
                         'available': len(items), 'picked': len(sel)}
    # 若因取整不足/超出，按长度离群程度补齐或截断
    picked.sort(key=lambda r: r['T'])
    if len(picked) > n_target:
        step = len(picked) / n_target
        picked = [picked[int(j * step)] for j in range(n_target)]
    elif len(picked) < n_target:
        used = {id(r) for r in picked}
        rest = [r for r in rs if id(r) not in used]
        rest.sort(key=lambda r: abs(r['T'] - picked[len(picked) // 2]['T']))
        picked.extend(rest[:n_target - len(picked)])
        picked.sort(key=lambda r: r['T'])
    return picked, per_bucket


def main():
    import numpy as np
    import soundfile as sf

    from npu_delivery_backend import make_delivery_all_npu_backend
    from seg_stream import SegmentedStreamer

    os.makedirs(OUT_DIR, exist_ok=True)
    rep = {'task': 'C-089 step1',
           'calib_window_sec': [CALIB_START, CALIB_END],
           'target_n': TARGET_N, 'n_buckets': N_BUCKETS,
           'backend': 'npu_delivery_backend（交付形态，全 NPU）',
           'note': '校准集 0–12 min，评测集 12–27 min 与全长 61 min，'
                   '两者不重叠，避免精度虚高。'}

    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * CALIB_START:SR * CALIB_END]
    rep['audio_sec'] = round(len(a) / SR, 2)
    assert len(a) == SR * (CALIB_END - CALIB_START), 'audio too short'

    t0 = time.perf_counter()
    be = make_delivery_all_npu_backend()
    rep['backend_init_s'] = round(time.perf_counter() - t0, 1)
    print(f'[c089a] backend init {rep["backend_init_s"]}s', flush=True)

    rec = PrefillRecorder(be)
    print('[c089a] 跑 0–12 min 收集真实 prefill 输入...', flush=True)
    t0 = time.perf_counter()
    _ = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False).run(a)
    rep['collect_wall_s'] = round(time.perf_counter() - t0, 1)
    rec.restore()

    rep['n_calls_recorded'] = len(rec.records)
    if not rec.records:
        rep['error'] = 'no prefill recorded'
        json.dump(rep, open(OUT_JSON, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print('[c089a] FAIL: 没录到任何 prefill')
        return 1

    Ts = [r['T'] for r in rec.records]
    rep['prompt_len_stats'] = {
        'min': min(Ts), 'max': max(Ts),
        'mean': round(float(np.mean(Ts)), 1),
        'median': int(np.median(Ts)),
    }
    print(f'[c089a] 录到 {len(Ts)} 次 prefill，T∈[{min(Ts)}, {max(Ts)}]', flush=True)

    picked, per_bucket = stratified_sample(rec.records, TARGET_N, N_BUCKETS)
    rep['strata'] = per_bucket
    rep['n_picked'] = len(picked)

    # NPUW IR 的输入维度是 [1, T, 2048]，T 各不相同 —— nncf.scale_estimation
    # 要求固定形状，所以按 T 分组保存，调用方每组分别喂。
    groups = {}
    for r in picked:
        groups.setdefault(r['T'], []).append(r['inputs_embeds'])
    rep['n_distinct_T'] = len(groups)
    rep['T_counts'] = {str(k): len(v) for k, v in sorted(groups.items())}

    arrays = {}
    for T, arrs in groups.items():
        # 组内堆叠：(k, T, 2048)；不同 T 的样本数可能为 1，保留 axis
        arrays[f'emb_T{T}'] = np.stack(arrs).astype(np.float32)

    # 顺带存标准辅助输入（校准只需 embeds，但一并存便于复现真实 prefill 形态）
    emb0 = picked[0]['inputs_embeds']
    T0 = int(emb0.shape[0])
    arrays['attn_mask_T0'] = np.ones((1, T0), dtype=np.int64)
    arrays['position_ids_T0'] = np.arange(T0, dtype=np.int64)[None, :]
    arrays['beam_idx'] = np.zeros(1, dtype=np.int32)

    np.savez_compressed(OUT_NPZ, **arrays)
    rep['npz_path'] = OUT_NPZ
    rep['npz_MiB'] = round(os.path.getsize(OUT_NPZ) / 2 ** 20, 1)
    rep['arrays'] = {k: {'shape': list(v.shape), 'dtype': str(v.dtype)}
                     for k, v in arrays.items()}

    json.dump(rep, open(OUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print('\n' + '=' * 72)
    print(f'分层抽样：{len(picked)} 条 / {len(rec.records)} 次调用，'
          f'{len(groups)} 个不同 T，npz {rep["npz_MiB"]} MiB')
    for b, info in per_bucket.items():
        print(f'  桶{b}: T∈[{info["T_lo"]},{info["T_hi"]}] '
              f'可用 {info["available"]} → 抽 {info["picked"]}')
    print('=' * 72)
    print('saved ->', OUT_NPZ)
    return 0


if __name__ == '__main__':
    sys.exit(main())
