# -*- coding: utf-8 -*-
"""app118 — APP-027「争用定量」的**第四臂：真·TTS 单独**（引擎级基线）。

🔴🔴🔴 **为什么必须单独写这个脚本（app114 的已知缺口）**

`app114_app027_v2_real_playback.py` 的四臂里，`tts_only` 被标成
**NOT-APPLICABLE（架构限制）**，理由是：

> 「CLI 回放架构下，句子来自 **ASR 定稿** ⇒ 连 ASR 都不跑就没有句子可念」

⇒ 于是 `app027_v2_abba_summary.json` 里那一臂是 `not_applicable: true`、
`synth_rtf_p50: null` ⇒ **四臂对照只有三臂有数字** ⇒
「ASR/MT 是否在跟 TTS 抢 NPU」这个结论**缺基线**。

🔴 **本脚本补的正是这一臂**：
**不跑 ASR、不跑 MT、不跑播放器**，直接驱动**生产路径的同一套引擎接口**
（`tts_engine.make_engine` + `tts_engine.stream`）⇒
测到的 RTF 就是「TTS 独占 NPU 时的引擎基线」。

🔴🔴🔴 **纪律**（与 app113 / app114 一致）：
- **持共享机器锁**（`machine_lock_app.acquire`）⇒ 没锁**绝不**跑推理；
- **等安静窗口**（`wait_quiet_window_cpu`）⇒ 不与他模块的计时作业抢；
- **不跑 MiniMax**（质量判定交 reviewer）⇒ 本脚本只出**工程数字**；
- **零 CPU 推理** ⇒ 设备固定 **NPU**（`make_engine(device='NPU')`）；
- **只落盘、不改生产代码**。

🔴 **口径对齐**（让四臂可比）：
- 语料 = **SPE 前 5 分钟切片的 ASR 定稿句**（与 app114 各臂**同一批句子**）
  ⇒ 从 `app027_v2/tts_asr/v2_tts_asr.tts.jsonl` 读 `text` 字段
  （该 jsonl 是 app114 真实播放路径落盘的，**含逐句原文**）；
- 语言 = **English**（SPE 是英文演讲；app114 的 `tts_asr` 臂同样是 ASR 原文）；
- 合成 = **走 `tts_engine.stream`**（与 `tts_worker._synth_babelvox` 同一函数）
  ⇒ 包含 `normalize_zh_numbers` / `split_long_text` / `chunk_frames` /
  `max_new_tokens` / `est_sec` 的**全部生产规则**；
- 计时 = **每句**从 `stream()` 调用到最后一个 chunk 返回（`perf_counter`）
  ⇒ RTF = 墙钟 / 音频秒数。

⚠️ **与 app114 各臂的差异（必须写进 STATUS）**：
本臂**不经过声卡播放** ⇒ 没有 `underflow_in_sentence` / `queue_peak_s` /
`consumed` 等**播放侧**字段 ⇒ 那些字段在本臂**结构性为 0/None（NO-EVIDENCE）**，
**不能**用来与 app114 的臂直接比大小；**只可比 `synth_rtf`（合成侧）**。

## 用法

    <pkg>/python/python.exe results/app/app118_engine_baseline_tts_only.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
OUT_DIR = os.path.join(HOME, 'app027_v2')
SRC_JSONL = os.path.join(OUT_DIR, 'tts_asr', 'v2_tts_asr.tts.jsonl')
REPORT = os.path.join(OUT_DIR, 'tts_only_engine_baseline.json')
JSONL_OUT = os.path.join(OUT_DIR, 'tts_only_engine_baseline.tts.jsonl')


def _pct(vals, p):
    if not vals:
        return None
    i = int(len(vals) * p)
    if i >= len(vals):
        i = len(vals) - 1
    return vals[i]


def _write_report(rows, device, load_s=None, device_desc=None):
    """从逐句 jsonl 聚合出报告（**唯一权威口径**）。

    🔴🔴 **抽成独立函数** ⇒ 「跑推理」与「出报告」两条路径**共用同一份聚合逻辑**
    ⇒ 报告生成阶段再出 bug 时，**用 `--report-only` 重算即可**，不必重跑推理。
    """
    rtfs = sorted(r['synth_rtf'] for r in rows if r.get('synth_rtf'))
    walls = sorted(r['wall_s'] for r in rows if r.get('wall_s') is not None)
    auds = sorted(r['audio_s'] for r in rows if r.get('audio_s') is not None)
    n_err = sum(1 for r in rows if r.get('error'))
    n_cap = sum(1 for r in rows if r.get('end_reason') == 'cap')
    n_runaway = sum(1 for r in rows if r.get('end_reason') == 'runaway')

    checks = [
        dict(id='E0-a', name='语料非空（真的跑了 N 句）',
             ok=(len(rows) > 0), got=len(rows), want='>0'),
        dict(id='E0-b', name='逐句都有音频产出（audio_s > 0）',
             ok=sum(1 for r in rows if (r.get('audio_s') or 0) > 0) == len(rows),
             got=sum(1 for r in rows if (r.get('audio_s') or 0) > 0),
             want=len(rows)),
        dict(id='E0-c', name='逐句 error = 0',
             ok=(n_err == 0), got=n_err, want=0),
        dict(id='E0-d', name='撞帧上限 cap = 0',
             ok=(n_cap == 0), got=n_cap, want=0),
        dict(id='E0-e', name='失控 runaway = 0',
             ok=(n_runaway == 0), got=n_runaway, want=0),
    ]
    n_pass = sum(1 for c in checks if c['ok'])

    report = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        cfg='tts_only_engine_baseline',
        device=device, device_desc=device_desc, load_s=load_s,
        n_sentences=len(rows), n_err=n_err, n_cap=n_cap, n_runaway=n_runaway,
        synth_rtf_p50=_pct(rtfs, 0.50), synth_rtf_p95=_pct(rtfs, 0.95),
        synth_rtf_min=rtfs[0] if rtfs else None,
        synth_rtf_max=rtfs[-1] if rtfs else None,
        wall_p50=_pct(walls, 0.50), wall_p95=_pct(walls, 0.95),
        audio_p50=_pct(auds, 0.50), audio_total=round(sum(auds), 2),
        wall_total=round(sum(walls), 2),
        checks=checks, pass_count=n_pass, fail_count=len(checks) - n_pass,
        artifacts=dict(jsonl=JSONL_OUT, source_corpus=SRC_JSONL),
        note='**引擎级基线**（真·TTS 单独）：不跑 ASR / 不跑 MT / 不跑声卡播放 '
             '⇒ 播放侧字段（underflow / queue_peak / consumed）'
             '**结构性 NO-EVIDENCE** ⇒ **只可与 app114 各臂比 synth_rtf**；'
             '非 GUI / 非用户实听 / 未调 MiniMax。',
    )
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for c in checks:
        print('  [%s] %-7s %-44s got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('  SUMMARY: PASS=%d FAIL=%d' % (n_pass, len(checks) - n_pass))
    print('  报告：%s' % REPORT)
    return 0 if n_pass == len(checks) else 1


def _report_only(args):
    """**只从已落盘 jsonl 重算报告**（不跑推理、不取锁）。"""
    if not os.path.exists(JSONL_OUT):
        print('!! 找不到逐句 jsonl：%s' % JSONL_OUT)
        return 2
    rows = []
    with open(JSONL_OUT, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    print('[report-only] 从 %s 读入 %d 行（不跑推理）'
          % (JSONL_OUT, len(rows)))
    return _write_report(rows, args.device, load_s=None, device_desc=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--max-sentences', type=int, default=0,
                    help='0 = 全部（默认用 app114 的 tts_asr 臂的逐句原文）')
    ap.add_argument('--quiet-timeout', type=float, default=1800.0)
    ap.add_argument('--lock-timeout', type=float, default=3600.0)
    ap.add_argument('--report-only', action='store_true',
                    help='🔴 只从已落盘的逐句 jsonl **重算报告**（不跑推理、'
                         '不取锁）⇒ 报告阶段出 bug 时不必重跑 46 句算力')
    args = ap.parse_args()

    if not os.path.exists(SRC_JSONL):
        print('!! 找不到语料 jsonl：%s' % SRC_JSONL)
        return 2

    # ── 语料：从 app114 的真实播放 jsonl 取逐句原文 ─────────────
    texts = []
    with open(SRC_JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            t = (r.get('text') or '').strip()
            if t and not r.get('dropped') and not r.get('error'):
                texts.append(t)
    if args.max_sentences:
        texts = texts[:args.max_sentences]
    print('[corpus] %d 句（来源：%s）' % (len(texts), SRC_JSONL))
    if not texts:
        print('!! 语料为空')
        return 2

    # 🔴🔴🔴 **`--report-only`**：**只从已落盘的 jsonl 重算报告**，不跑推理。
    #   ⇒ 用途：报告生成阶段崩了（例如引擎对象缺属性）时，
    #   **不必重跑 46 句推理**（实测：46 句 ≈ 244 s 算力）
    #   ⇒ 逐句 jsonl 是**权威产物**，报告只是它的**聚合视图**。
    # ⚠️ 报告里的 `load_s` / `device_desc` 在该模式下**取不到** ⇒ 写 None。
    if args.report_only:
        return _report_only(args)

    # ── 锁 ───────────────────────────────────────────────────────
    sys.path.insert(0, REPO)
    sys.path.insert(0, os.path.join(PKG_ROOT, 'app'))
    import machine_lock_app as ml

    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=args.lock_timeout,
                                   poll=20, verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=args.quiet_timeout,
                                                    verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出')
            return 4

        import tts_engine as TE

        t0 = time.time()
        print('[engine] 加载引擎（device=%s）…' % args.device)
        eng = TE.make_engine(device=args.device,
                             on_log=lambda m: print('[engine] %s' % m,
                                                    flush=True))
        load_s = time.time() - t0
        print('[engine] 加载完成 %.1f s' % load_s)

        wav = TE.preset_voice_path()
        spk = TE.speaker_embedding(eng, wav, on_log=lambda m: None)
        print('[engine] speaker_embed=%s' % ('ready' if spk is not None
                                             else 'None(用内置 speaker)'))

        rows = []
        jf = open(JSONL_OUT, 'w', encoding='utf-8', newline='\n')
        try:
            for i, t in enumerate(texts):
                parts = TE.split_long_text(t)
                total_audio = 0.0
                total_wall = 0.0
                n_chunks = 0
                err = None
                reason = 'eos'
                for p in parts:
                    mnt = TE.clamp_max_new_tokens(p, 'en')
                    est = TE.estimate_sec(p, 'en')
                    t1 = time.perf_counter()
                    try:
                        for chunk, sr in TE.stream(
                                eng, p, language='English',
                                speaker_embed=spk, speaker=None,
                                max_new_tokens=int(mnt), est_sec=float(est)):
                            total_audio += len(chunk) / float(sr or 24000)
                            n_chunks += 1
                    except Exception as e:
                        err = '%s: %s' % (type(e).__name__, e)
                        reason = 'error'
                        break
                    total_wall += time.perf_counter() - t1
                er = getattr(eng, '_last_end_reason', None)
                if er in ('cap', 'runaway'):
                    reason = er
                rtf = (total_wall / total_audio) if total_audio > 0 else None
                row = dict(id=i, text=t, lang='en',
                           n_chars=len(t), n_parts=len(parts),
                           n_chunks=n_chunks,
                           wall_s=round(total_wall, 4),
                           audio_s=round(total_audio, 4),
                           synth_rtf=round(rtf, 4) if rtf else None,
                           end_reason=reason, error=err)
                rows.append(row)
                jf.write(json.dumps(row, ensure_ascii=False) + '\n')
                jf.flush()
                print('  [%3d] rtf=%-8s wall=%-8s audio=%-8s chunks=%-3d %s'
                      % (i, row['synth_rtf'], row['wall_s'], row['audio_s'],
                         n_chunks, (t[:38] + '…') if len(t) > 38 else t))
        finally:
            jf.close()

        return _write_report(rows, args.device,
                             load_s=round(load_s, 1),
                             device_desc=(getattr(eng, 'device_desc', None)
                                          or getattr(eng, 'device', None)
                                          or args.device))
        return 0 if n_pass == len(checks) else 1
    finally:
        try:
            ml.release(payload)
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
