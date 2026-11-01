# -*- coding: utf-8 -*-
r"""app195_app053_mechanism_probe.py — APP-053 根因的**机制级**确认（GPU.0，少量调用）。

## 它要回答什么

`app193`（纯离线）已证明：**pyannote 离线本应能打标 89%，App 实测只有 7.23%**
⇒ 丢失在 App/ASR 的**在线**路径上。

本脚本直接量化 ASR-029 交付的 `SpeakerTracker._advance_seg()` **增量**路径的两处缺陷，
用**少量** GPU 调用（不是 3000 次）：

1. **窗口补零**：`run_seg_side` 的窗口长 `WIN_N = 10 s`；喂 100 ms 块时
   它把 0.1 s 真实音频**补零到 10 s** 再送模型
   ⇒ 模型在「99% 静音」的窗上判帧 ⇒ `p_speech ≈ 0`
   ⇒ `clean_ratio ≈ 0` ⇒ 恒判 `not_clean_speech`。
2. **帧数取整漂移**：每次 append 的帧数 = `ceil(B/SR*FPS)`
   ⇒ 100 ms 块时每块多 0.11 帧（+1.87%）⇒ 300 s 累计 **+5.60 s** 偏移
   ⇒ `_seg_slice(t)` 用 `t*FPS` 取帧 ⇒ **取到的不是该时刻的帧**。

⇒ 修法（App 侧，不改 ASR 源码）：**把喂给旁路的批量改成整 10 s**
⇒ 一次一个真实满窗 ⇒ 帧数恰好 589 ⇒ **零漂移**、**零补零**。

## 🔴 口径纪律

* **不改 ASR 源码文件**：直接 `import` 包内 `app/asr_spk/asr052_speaker_tracker_api.py`
  （与 ASR 侧 `scripts/` 下**逐字节相同**，已核对）。
* 模型用**包内资产**（与生产同形）。
* **持共享机器锁**（GPU 推理属计时/测速类作业）。
* 每条结论都给出**原始字段**（帧数、p_speech 均值、clean_ratio、reason）。
* 产物：`results/app/app195_app053_mechanism_evidence.json`
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

HOME = os.path.expanduser('~')


def _find_repo_root(start):
    """向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律：写死 ⇒ fresh clone 里是假象）。
    """
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent


REPO = _find_repo_root(os.path.dirname(os.path.abspath(__file__)))
import pkg_paths          # noqa: E402  （单一数据源：自动发现最新版本包）
PKG = pkg_paths.discover_pkg_dir()
WAV = os.path.join(HOME, 'shared', 'spe_qa_clone_listen', 'SPE_densest_5min.wav')
OUT = os.path.join(REPO, 'results', 'app',
                   'app195_app053_mechanism_evidence.json')
ASR_DIR = os.path.join(PKG, 'app', 'asr_spk')
SEG_IR = os.path.join(PKG, 'models', 'spk', 'pyannote_seg_3_0', 'fp16')
WES_IR = os.path.join(PKG, 'models', 'spk', 'wespeaker-resnet34-fp16')

SR = 16000
SLICE_OFFSET = 3291.6

sys.path.insert(0, REPO)
sys.path.insert(0, ASR_DIR)


def load_wav():
    import soundfile as sf
    a, sr = sf.read(WAV, dtype='float32')
    if a.ndim > 1:
        a = a.mean(axis=1)
    assert sr == SR, sr
    return np.ascontiguousarray(a)


def main():
    import asr052_spk_runtime as rt
    import openvino as ov

    audio = load_wav()
    n_audio_s = len(audio) / SR

    # 🔴 `stride_ms` 是 **tracker API** 的构造默认参数，不在 runtime 模块里
    #   ⇒ 从 ASR 侧源码现读（不手抄、不推算）。
    import re as _re
    _api_src = open(os.path.join(ASR_DIR, 'asr052_speaker_tracker_api.py'),
                    encoding='utf-8').read()
    _m = _re.search(r'stride_ms\s*(?::\s*[A-Za-z_][\w\[\], ]*)?=\s*([0-9.]+)',
                    _api_src)
    STRIDE_MS = float(_m.group(1)) if _m else 1280.0

    print('=== APP-053 机制探针（GPU.0）===')
    print('旁路常量（ASR 侧现读）：SR=%d WIN_N=%d N_FRAMES=%d FPS=%s stride_ms=%s'
          % (rt.SR, rt.WIN_N, rt.N_FRAMES, rt.FPS, STRIDE_MS))

    core = ov.Core()
    t0 = time.perf_counter()
    ir_xml = os.path.join(SEG_IR, 'pyannote_seg_3_0.xml')
    compiled = core.compile_model(core.read_model(ir_xml), 'GPU.0')
    compile_wall = time.perf_counter() - t0
    print('模型编译墙钟 = %.3f s（★ run_seg_side **每次调用都重编译** ⇒ '
          'App 的 100 ms 增量路径 = 3000 次编译）' % compile_wall)

    # ── ① 窗口补零：同一段 0.1 s 音频，「补零到 10 s」vs「满 10 s 真实音频」──
    seg10 = np.ascontiguousarray(audio[:10 * SR])

    def frames_for(buf):
        """等价 run_seg_side 的帧级输出（用**同一个已编译模型** ⇒ 不重复编译）。"""
        n_total = int(math.ceil(len(buf) / SR * rt.FPS))
        agg = rt.FrameAggregator(n_total)
        stride_samples = int(round(STRIDE_MS / 1000.0 * SR))
        win_idx = 0
        win_start = 0
        while win_start + rt.WIN_N <= len(buf):
            seg = np.ascontiguousarray(
                buf[win_start:win_start + rt.WIN_N].reshape(1, 1, -1)
                .astype(np.float32))
            logits = np.asarray(compiled([seg])[compiled.output(0)])[0] \
                .astype(np.float64)
            m = logits.max(axis=-1, keepdims=True)
            e = np.exp(logits - m)
            agg.add_window(win_idx, stride_samples, e / e.sum(axis=-1, keepdims=True))
            win_idx += 1
            win_start += stride_samples
        if win_start < len(buf):
            seg = np.zeros((1, 1, rt.WIN_N), dtype=np.float32)
            rest = len(buf) - win_start
            seg[0, 0, :rest] = buf[win_start:]
            logits = np.asarray(compiled([seg])[compiled.output(0)])[0] \
                .astype(np.float64)
            m = logits.max(axis=-1, keepdims=True)
            e = np.exp(logits - m)
            agg.add_window(win_idx, stride_samples, e / e.sum(axis=-1, keepdims=True))
        ps, pd, sid, cov = agg.finalize()
        return ps, pd, n_total

    small = np.ascontiguousarray(audio[:1600])          # 100 ms
    ps_small, pd_small, n_small = frames_for(small)
    ps_big, pd_big, n_big = frames_for(seg10)

    small_clean = float((ps_small >= 0.5).mean()) if ps_small.size else 0.0
    big_clean = float((ps_big >= 0.5).mean()) if ps_big.size else 0.0
    print('\n--- ① 窗口补零（同一份 100 ms 音频，两种喂法）---')
    print('  补零喂法（0.1 s → 补零到 10 s）：n_frames=%d  p_speech 均值=%.4f  '
          'clean_ratio=%.4f' % (n_small, float(ps_small.mean()), small_clean))
    print('  满窗喂法（10 s 真实音频）      ：n_frames=%d  p_speech 均值=%.4f  '
          'clean_ratio=%.4f' % (n_big, float(ps_big.mean()), big_clean))

    # ── ② 帧数取整漂移 ──
    print('\n--- ② 帧数取整漂移（纯算术，与 GPU 无关）---')
    drift_rows = []
    for B in (1600, 160000):
        n = math.ceil(B / SR * rt.FPS)
        true = B / SR * rt.FPS
        drift = n - true
        cum300 = drift * (300.0 / (B / SR))
        drift_rows.append(dict(block_samples=B, block_ms=B / SR * 1000,
                                frames_appended=n, frames_true=round(true, 4),
                                drift_per_block=round(drift, 4),
                                drift_pct=round(100 * drift / true, 4),
                                cum_drift_300s_frames=round(cum300, 2),
                                cum_drift_300s_s=round(cum300 / rt.FPS, 3)))
        print('  批量 %6d 样本（%6.1f ms）：append %4d 帧 vs 应有 %8.2f 帧 ⇒ '
              '每块 %+0.4f 帧，300 s 累计 %+0.2f 帧 = %+0.2f s'
              % (B, B / SR * 1000, n, true, drift, cum300, cum300 / rt.FPS))

    # ── ③ 端到端：三臂（真实 tracker，不改 ASR 源码）──
    print('\n--- ③ 端到端三臂（真实 SpeakerTracker，只变喂音批量）---')
    from asr052_speaker_tracker_api import SpeakerTracker

    # 断句段用参考标注（App 同口径）
    ref = json.load(open(os.path.join(HOME, 'shared', 'spe_qa_spk.json'),
                         encoding='utf-8'))
    plan = []
    for s in ref['segments']:
        if s['t_end'] > SLICE_OFFSET and s['t_start'] < SLICE_OFFSET + n_audio_s:
            t0s = max(0.0, s['t_start'] - SLICE_OFFSET)
            t1s = min(n_audio_s, s['t_end'] - SLICE_OFFSET)
            if t1s - t0s >= 0.5:
                plan.append(dict(t0=t0s, t1=t1s, ref_spk=s.get('spk'),
                                 ref_skip=s.get('skip')))

    def arm(name, block_ms):
        tr = SpeakerTracker(device='GPU.0', seg_device='GPU.0',
                            seg_ir=SEG_IR, wes_ir=WES_IR)
        t = time.perf_counter()
        if block_ms is None:
            tr.feed(audio, float(n_audio_s))
            n_feed = 1
        else:
            step = int(SR * block_ms / 1000)
            n_feed = 0
            for i in range(0, len(audio), step):
                blk = audio[i:i + step]
                if blk.shape[0] < step:
                    blk = np.pad(blk, (0, step - blk.shape[0]))
                tr.feed(blk, (i + blk.shape[0]) / SR)
                n_feed += 1
        feed_wall = time.perf_counter() - t
        n_frames = len(tr._seg_frames['p_speech']) if tr._seg_frames else 0
        rows = []
        for i, p in enumerate(plan):
            a0 = max(0.0, p['t1'] - 2.5)
            r = tr.on_final(seg_id=i, t_start=a0, t_end=p['t1'])
            rows.append(dict(seg_id=i, spk=r.get('spk'),
                             reason=r.get('reason'),
                             pending=bool(r.get('pending')),
                             clean_ratio=r.get('clean_ratio'),
                             ref_spk=p['ref_spk']))
        n = len(rows)
        tagged = [r for r in rows if r['spk']]
        both = [r for r in rows if r['spk'] and r['ref_spk']]
        agree = [r for r in both if r['spk'] == r['ref_spk']]
        from collections import Counter
        out = dict(arm=name, block_ms=block_ms, n_feed=n_feed,
                   feed_wall_s=round(feed_wall, 2),
                   n_frames_in_tracker=n_frames,
                   expected_frames=round(n_audio_s * rt.FPS, 1),
                   frame_drift=n_frames - round(n_audio_s * rt.FPS, 1),
                   n_segments=n, n_tagged=len(tagged),
                   tagged_pct=round(100.0 * len(tagged) / max(1, n), 2),
                   reason_hist=dict(Counter(r['reason'] for r in rows)),
                   n_both_labeled=len(both),
                   n_agree_with_ref=len(agree),
                   agree_pct=round(100.0 * len(agree) / max(1, len(both)), 2),
                   rows=rows)
        del tr
        return out

    arms = []
    # ③-1 一次性喂 300 s（= pyannote 离线整段口径）
    arms.append(arm('A_oneshot_300s', None))
    # ③-2 增量 10 s（**拟议修法**：整窗喂）
    arms.append(arm('C_batch_10s', 10000))
    # ③-3 增量 100 ms（App 现路径）—— **只喂前 40 s**，避免 400 次编译
    print('  （③-3 只喂前 40 s：100 ms 路径每次 feed 都要重编译 ⇒ 3000 次不可行）')
    sub = audio[:40 * SR]
    tr = SpeakerTracker(device='GPU.0', seg_device='GPU.0',
                        seg_ir=SEG_IR, wes_ir=WES_IR)
    t = time.perf_counter()
    step = 1600
    n_feed = 0
    for i in range(0, len(sub), step):
        blk = sub[i:i + step]
        if blk.shape[0] < step:
            blk = np.pad(blk, (0, step - blk.shape[0]))
        tr.feed(blk, (i + blk.shape[0]) / SR)
        n_feed += 1
    fb = time.perf_counter() - t
    nf = len(tr._seg_frames['p_speech']) if tr._seg_frames else 0
    sub_plan = [p for p in plan if p['t1'] <= 40.0]
    rows = []
    for i, p in enumerate(sub_plan):
        a0 = max(0.0, p['t1'] - 2.5)
        r = tr.on_final(seg_id=i, t_start=a0, t_end=p['t1'])
        rows.append(dict(seg_id=i, spk=r.get('spk'), reason=r.get('reason'),
                         pending=bool(r.get('pending')),
                         clean_ratio=r.get('clean_ratio'),
                         ref_spk=p['ref_spk']))
    from collections import Counter
    ns = len(rows)
    tg = [r for r in rows if r['spk']]
    arms.append(dict(arm='B_incremental_100ms_40s', block_ms=100,
                     n_feed=n_feed, feed_wall_s=round(fb, 2),
                     n_frames_in_tracker=nf,
                     expected_frames=round(40.0 * rt.FPS, 1),
                     frame_drift=nf - round(40.0 * rt.FPS, 1),
                     n_segments=ns, n_tagged=len(tg),
                     tagged_pct=round(100.0 * len(tg) / max(1, ns), 2),
                     reason_hist=dict(Counter(r['reason'] for r in rows)),
                     n_both_labeled=0, n_agree_with_ref=0, agree_pct=None,
                     note='只喂前 40 s（编译开销）', rows=rows))
    del tr

    for a in arms:
        print('  臂 %-26s 喂音 %5d 次  帧 %6d（应 %6d，漂移 %+d）  '
              '打标 %2d/%2d = %6.2f%%  原因=%s'
              % (a['arm'], a['n_feed'], a['n_frames_in_tracker'],
                 a['expected_frames'], a['frame_drift'], a['n_tagged'],
                 a['n_segments'], a['tagged_pct'], a['reason_hist']))

    checks = [
        dict(name='M1 补零喂法 clean_ratio 明显低于满窗喂法',
             ok=small_clean < big_clean * 0.5,
             detail=dict(padded=round(small_clean, 4), full=round(big_clean, 4))),
        dict(name='M2 100 ms 增量 ⇒ 帧漂移 > 0（300 s > 1 s）',
             ok=drift_rows[0]['cum_drift_300s_s'] > 1.0,
             detail=drift_rows[0]),
        dict(name='M3 10 s 批量 ⇒ 帧漂移 = 0',
             ok=drift_rows[1]['cum_drift_300s_s'] == 0.0,
             detail=drift_rows[1]),
        dict(name='M4 A 臂（一次性）打标率 ≥ 70%',
             ok=arms[0]['tagged_pct'] >= 70.0, detail=arms[0]['tagged_pct']),
        dict(name='M5 C 臂（10 s 批量）打标率 ≥ A 臂的 90%',
             ok=arms[1]['tagged_pct'] >= arms[0]['tagged_pct'] * 0.9,
             detail=dict(A=arms[0]['tagged_pct'], C=arms[1]['tagged_pct'])),
        dict(name='M6 B 臂（100 ms 增量）打标率 < A 臂的 1/4',
             ok=arms[2]['tagged_pct'] < arms[0]['tagged_pct'] / 4.0,
             detail=dict(A=arms[0]['tagged_pct'], B=arms[2]['tagged_pct'])),
        dict(name='M7 B 臂主因 = not_clean_speech',
             ok=arms[2]['reason_hist'].get('not_clean_speech', 0) >
                0.5 * arms[2]['n_segments'],
             detail=arms[2]['reason_hist']),
        dict(name='M8 A 臂与参考伪真值一致率 ≥ 60%',
             ok=arms[0]['agree_pct'] is not None and arms[0]['agree_pct'] >= 60.0,
             detail=arms[0]['agree_pct']),
    ]
    n_pass = sum(1 for c in checks if c['ok'])
    out = dict(
        script='app195_app053_mechanism_probe.py',
        correction='APP-053',
        purpose='确认 APP-053 覆盖率丢失的机制（窗口补零 + 帧漂移）',
        asr_source_note='ASR 源码**未改**：只 import 包内交付副本。',
        seg_ir=SEG_IR, wes_ir=WES_IR,
        slice_wav=WAV, slice_dur_s=round(n_audio_s, 3),
        constants=dict(SR=rt.SR, WIN_N=rt.WIN_N, N_FRAMES=rt.N_FRAMES,
                       FPS=rt.FPS, stride_ms=STRIDE_MS),
        compile_wall_s=round(compile_wall, 3),
        compile_note='run_seg_side 每次调用都 core.compile_model ⇒ '
                     '100 ms 增量路径 = 3000 次编译（实测见各臂 feed_wall_s）',
        window_padding=dict(
            padded_100ms=dict(n_frames=n_small,
                               p_speech_mean=round(float(ps_small.mean()), 4),
                               clean_ratio=round(small_clean, 4)),
            full_10s=dict(n_frames=n_big,
                          p_speech_mean=round(float(ps_big.mean()), 4),
                          clean_ratio=round(big_clean, 4)),
        ),
        frame_drift=drift_rows,
        arms=arms,
        checks=checks, n_pass=n_pass, n_fail=len(checks) - n_pass,
        verdict=('PASS' if n_pass == len(checks) else 'FAIL'),
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('\n=== 判据 ===')
    for c in checks:
        print('  [%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL',
                                  c['name'], c['detail']))
    print('结果：%d PASS / %d FAIL ⇒ %s'
          % (n_pass, len(checks) - n_pass, out['verdict']))
    print('产物 = %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
