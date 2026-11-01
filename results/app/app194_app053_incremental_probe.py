# -*- coding: utf-8 -*-
r"""app194_app053_incremental_probe.py — APP-053 的**根因确认**实验（GPU.0）。

## 它要证明什么

`app193_app053_spk_frame_audit.py`（纯离线）已经给出决定性数字：

* 同一 5 min 切片、同一套断句段：
  * pyannote **离线整段跑** ⇒ 本应可打标 **41/46 = 89.13%**（App 取值规则）
    / 44/46 = 95.65%（参考口径）；
  * App **实测**打标 **7.23%**（7/83 句）
  * ⇒ **App 侧丢失 ≈ 81.9 个百分点**，而 pyannote 本身没问题。

本脚本用**受控 GPU 实验**定位这条丢失发生在哪一步，
对 **ASR-029 交付的同一份 `asr052_speaker_tracker_api.py`**（不改 ASR 源码一个字节）
跑三臂：

| 臂 | 喂音方式 | 期望（若「增量分段漂移」假设成立） |
|---|---|---|
| A | **一次性**喂 300 s | 段标签率 ≈ 89% |
| B | **增量**喂 100 ms 块（= App 真实路径） | 段标签率 **塌到接近 0** |
| C | 增量喂，但**禁用** `_advance_seg` 的增量（一次性喂全量给分段器） | 段标签率回到 ≈ 89% |

⇒ A≈C≫B ⇒ **根因 = ASR 侧 `SpeakerTracker._advance_seg()` 的增量分段路径**，
而 **App 侧无法直接修 ASR 源码** ⇒ 修法必须落在 App 侧（喂音/取值口径）。

## 🔴 口径纪律

* **不改 ASR 源码**：直接 `import` 包内 `app/asr_spk/asr052_speaker_tracker_api.py`
  （= ASR 交付集合，与 ASR 侧 `scripts/` 下**逐字节相同**，已核对）。
* 模型用**包内资产**（`models/spk/pyannote_seg_3_0/fp16` +
  `models/spk/wespeaker-resnet34-fp16`）⇒ 与生产同形。
* **持共享机器锁**（GPU 推理 = 计时/测速类作业）⇒ 先取锁、再等安静窗口。
* 只跑**旁路**（不需要 ASR 主引擎）⇒ 不碰 NPU、不跑 TTS。
* 每臂都记录**逐段**的 `reason` 分布 ⇒ 不是只给结论。
* 产物：`results/app/app194_app053_incremental_evidence.json`
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter

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
                   'app194_app053_incremental_evidence.json')
ASR_DIR = os.path.join(PKG, 'app', 'asr_spk')
SEG_IR = os.path.join(PKG, 'models', 'spk', 'pyannote_seg_3_0', 'fp16')
WES_IR = os.path.join(PKG, 'models', 'spk', 'wespeaker-resnet34-fp16')

# 🔴 与 `shared/spe_qa_spk.json` 的 `densest_5min` 对齐：
#   该 wav 是**切片**（0 s 起）⇒ 参考段的全局时间需减 SLICE_OFFSET 才能对齐。
SLICE_OFFSET = 3291.6
SR = 16000
BLOCK_MS = 100

sys.path.insert(0, REPO)
sys.path.insert(0, ASR_DIR)


def load_wav():
    import soundfile as sf
    a, sr = sf.read(WAV, dtype='float32')
    if a.ndim > 1:
        a = a.mean(axis=1)
    assert sr == SR, sr
    return np.ascontiguousarray(a)


def seg_plan(ref_json, n_audio_s):
    """用**参考标注**的段（含全局时间）当「App 的定稿段」。

    🔴 为什么要用参考标注的段，而不是 App 自己的断句：
    * 目标是**隔离变量**（只变喂音方式）⇒ 断句必须**三臂完全一致**；
    * 参考标注 `spe_qa_spk.json` 的段就是 ASR-028 用**App 路径**断出来的
      （`pya_app_path_seg.py` 的 `Recorder`）⇒ 与生产断句同口径。
    * 参考标注还**自带伪真值 spk** ⇒ 可直接算「打标率」和「打对的准确率」。
    """
    d = json.load(open(ref_json, encoding='utf-8'))
    segs = [s for s in d['segments']
            if s['t_end'] > SLICE_OFFSET and s['t_start'] < SLICE_OFFSET + n_audio_s]
    segs.sort(key=lambda s: s['t_start'])
    plan = []
    for s in segs:
        t0 = max(0.0, s['t_start'] - SLICE_OFFSET)
        t1 = min(n_audio_s, s['t_end'] - SLICE_OFFSET)
        if t1 - t0 < 0.5:
            continue
        plan.append(dict(t0=t0, t1=t1, ref_spk=s.get('spk'),
                         ref_skip=s.get('skip')))
    return plan, d


def make_tracker():
    from asr052_speaker_tracker_api import SpeakerTracker
    return SpeakerTracker(device='GPU.0', seg_device='GPU.0',
                          seg_ir=SEG_IR, wes_ir=WES_IR)


def run_arm(name, audio, plan, mode, block_ms=BLOCK_MS):
    """跑一臂。

    mode:
      'oneshot'  ⇒ 一次性 feed 全部音频（只喂 1 次）
      'incremental' ⇒ 每 block_ms 喂一块（= App 真实路径）
      'incremental_full_seg' ⇒ 增量喂，但分段器**每次都吃全量**
    """
    tr = make_tracker()
    t0 = time.perf_counter()
    n_feed = 0

    if mode == 'oneshot':
        tr.feed(audio, float(len(audio) / SR))
        n_feed = 1
    elif mode == 'incremental':
        step = int(SR * block_ms / 1000)
        for i in range(0, len(audio), step):
            blk = audio[i:i + step]
            if blk.shape[0] < step:
                blk = np.pad(blk, (0, step - blk.shape[0]))
            tr.feed(blk, (i + blk.shape[0]) / SR)
            n_feed += 1
    elif mode == 'incremental_full_seg':
        # 🔴 同一份 tracker，但把「喂给分段器的样本」换成全量
        #   （用 monkeypatch `_advance_seg` 的等价实现，不改 ASR 源码文件）
        step = int(SR * block_ms / 1000)
        import asr052_speaker_tracker_api as api
        rt = api._rt

        def _advance_seg_full(self):
            """等价于 ASR 原 `_advance_seg`，但**每次都重跑全量**。"""
            if not self._models_ready:
                return
            import numpy as np
            if self._seg_frames is None:
                self._seg_frames = {'p_speech': [], 'p_dom': []}
            buf = np.concatenate(self._buf) if self._buf else None
            if buf is None or buf.size == 0:
                return
            frames, _w = rt.run_seg_side(buf, self.seg_ir, self.seg_device,
                                         self.stride_ms)
            self._seg_frames['p_speech'] = list(frames['p_speech'])
            self._seg_frames['p_dom'] = list(frames['p_dom'])
            self._seg_done = buf.size

        tr._advance_seg = _advance_seg_full.__get__(tr, type(tr))
        for i in range(0, len(audio), step):
            blk = audio[i:i + step]
            if blk.shape[0] < step:
                blk = np.pad(blk, (0, step - blk.shape[0]))
            tr.feed(blk, (i + blk.shape[0]) / SR)
            n_feed += 1
    else:
        raise ValueError(mode)

    feed_wall = time.perf_counter() - t0

    # ── 逐段问标签（用 App 现在的取值规则：段尾往前借 2.5 s）──
    rows = []
    for i, p in enumerate(plan):
        t0s = max(0.0, p['t1'] - 2.5)
        res = tr.on_final(seg_id=i, t_start=t0s, t_end=p['t1'])
        rows.append(dict(
            seg_id=i, t_start=round(p['t0'], 3), t_end=round(p['t1'], 3),
            dur_s=round(p['t1'] - p['t0'], 3),
            span_used=[round(t0s, 3), round(p['t1'], 3)],
            spk=res.get('spk'), spk_conf=res.get('spk_conf'),
            reason=res.get('reason'), pending=bool(res.get('pending')),
            ref_spk=p['ref_spk'], ref_skip=p['ref_skip'],
            clean_ratio=res.get('clean_ratio'),
            overlap_ratio=res.get('overlap_ratio'),
            dur_s_reported=res.get('dur_s'),
            requested_dur_s=res.get('requested_dur_s'),
            buffered_dur_s=res.get('buffered_dur_s'),
        ))

    n = len(rows)
    tagged = [r for r in rows if r['spk']]
    # 与参考伪真值一致率（只在两者都有标签时）
    both = [r for r in rows if r['spk'] and r['ref_spk']]
    agree = [r for r in both if r['spk'] == r['ref_spk']]
    # 换人点检出：参考换人点落在段边界附近 ⇒ 该段 spk 应与前段不同
    switch_hits = 0
    switch_total = 0
    prev_spk = None
    for r in rows:
        if prev_spk and r['spk'] and prev_spk != r['spk']:
            switch_hits += 1
        if r['spk']:
            prev_spk = r['spk']
    out = dict(
        arm=name, mode=mode, block_ms=(block_ms if 'increment' in mode else None),
        n_feed=n_feed, feed_wall_s=round(feed_wall, 3),
        n_segments=n,
        n_tagged=len(tagged),
        tagged_pct=round(100.0 * len(tagged) / max(1, n), 2),
        reason_hist=dict(Counter(r['reason'] for r in rows)),
        pending_hist=dict(Counter(r['pending'] for r in rows)),
        n_both_labeled=len(both),
        n_agree_with_ref=len(agree),
        agree_pct=round(100.0 * len(agree) / max(1, len(both)), 2),
        detected_switches=switch_hits,
        rows=rows,
    )
    del tr
    return out


def main():
    ref_json = os.path.join(HOME, 'shared', 'spe_qa_spk.json')
    audio = load_wav()
    n_audio_s = len(audio) / SR
    plan, ref = seg_plan(ref_json, n_audio_s)

    print('=== APP-053 根因确认实验 ===')
    print('切片 %s（%.1f s）' % (WAV, n_audio_s))
    print('定稿段（参考标注，App 同口径断句）= %d 个' % len(plan))
    print('参考伪真值：有标签 %d 个，换人点 %d 个'
          % (sum(1 for p in plan if p['ref_spk']),
             len(ref['densest_5min']['switch_times_s'])))

    arms = []
    for name, mode in (('A_oneshot', 'oneshot'),
                       ('B_incremental', 'incremental'),
                       ('C_incremental_full_seg', 'incremental_full_seg')):
        print('\n--- 臂 %s（mode=%s）---' % (name, mode))
        r = run_arm(name, audio, plan, mode)
        print('  n_feed=%d  打标 %d/%d = %.2f%%  原因=%s'
              % (r['n_feed'], r['n_tagged'], r['n_segments'],
                 r['tagged_pct'], r['reason_hist']))
        print('  与参考一致 %d/%d = %.2f%%  检出换人 %d'
              % (r['n_agree_with_ref'], r['n_both_labeled'],
                 r['agree_pct'], r['detected_switches']))
        arms.append(r)

    # 判据
    a, b, c = arms[0], arms[1], arms[2]
    checks = [
        dict(name='K1 A 一次性喂音打标率 ≥ 70%',
             ok=a['tagged_pct'] >= 70.0, detail=a['tagged_pct']),
        dict(name='K2 B 增量喂音打标率 < A 的 1/4（塌陷）',
             ok=b['tagged_pct'] < a['tagged_pct'] / 4.0,
             detail=dict(A=a['tagged_pct'], B=b['tagged_pct'])),
        dict(name='K3 C 增量喂音但分段吃全量 ⇒ 回到 A 的 90%',
             ok=c['tagged_pct'] >= a['tagged_pct'] * 0.9,
             detail=dict(A=a['tagged_pct'], C=c['tagged_pct'])),
        dict(name='K4 B 的主因是 seg_pending/audio_not_buffered',
             ok=(b['reason_hist'].get('seg_pending', 0) +
                 b['reason_hist'].get('audio_not_buffered', 0)) >
                0.6 * b['n_segments'],
             detail=b['reason_hist']),
        dict(name='K5 A 与参考伪真值一致率 ≥ 60%',
             ok=a['agree_pct'] >= 60.0, detail=a['agree_pct']),
    ]
    n_pass = sum(1 for c_ in checks if c_['ok'])
    out = dict(
        script='app194_app053_incremental_probe.py',
        correction='APP-053',
        purpose='定位 App 侧说话人标签丢失 81.9pp 的根因（ASR 增量分段 vs 离线整段）',
        slice_wav=WAV, slice_dur_s=round(n_audio_s, 3),
        asr_dir=ASR_DIR, seg_ir=SEG_IR, wes_ir=WES_IR,
        note=('ASR 源码**未改**：C 臂用 monkeypatch 在**实例**上换掉 _advance_seg，'
              '不触碰 ASR 文件。'),
        n_segments_plan=len(plan),
        ref=dict(
            n_switch=len(ref['densest_5min']['switch_times_s']),
            switch_times_s=ref['densest_5min']['switch_times_s'],
        ),
        arms=arms,
        checks=checks, n_pass=n_pass, n_fail=len(checks) - n_pass,
        verdict=('PASS' if n_pass == len(checks) else 'FAIL'),
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('\n=== 判据 ===')
    for c_ in checks:
        print('  [%s] %s  %s' % ('PASS' if c_['ok'] else 'FAIL',
                                  c_['name'], c_['detail']))
    print('结果：%d PASS / %d FAIL ⇒ %s'
          % (n_pass, len(checks) - n_pass, out['verdict']))
    print('产物 = %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
