# -*- coding: utf-8 -*-
"""APP-030 **NPU 实测**：A/B 根因证明（改前 vs 改后）。

🔴🔴🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（`machine_lock_app`）。
🔴 **不在 CPU 上跑推理** —— 设备固定 **NPU**。

## 做什么（reviewer APP-030「### 4. 验收」A/B 项）

对每条测试句：
- **改前口径**：`language='English'`（旧实现的 `_guess_lang` 对纯假名句的判 en）
  ⇒ 复现原缺陷（分布外 ⇒ EOS 不稳 ⇒ 撞帧数上限）；
- **改后口径**：`language='Japanese'`（APP-030① 显式下传后的正确值）
  ⇒ 应当撞上限 = 0。

逐句记录：
    id / 文本 / 字数 / 估计帧 / 实际帧 / 结束原因(eos|cap) / 音频秒 / s/字 / 挂起秒

## 判据（reviewer 明文）

**改后**（Japanese）：
- 撞上限（`end_reason == 'cap'`）= **0**
- 挂起（单句耗时 > 预计时长 × 3 + 8 s）= **0**

**改前**（English）：
- 撞上限次数**如实报告**（用来证明根因）—— **不作为 FAIL**
  （失控是随机的，单次不够 ⇒ 每句 ×3 次）

## 用法

    <包内 python> results/app/app108_npu_ab.py --repeats 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'

# 🔴 **只用包内 python**（只有它有 babelvox；dev .venv 没有 ⇒ NPU 跑不了）
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
sys.path.insert(0, os.path.join(PKG_ROOT, 'app'))


def _lock_ctx():
    """取共享机器锁（失败 ⇒ 直接退出，绝不在无锁下跑推理）。"""
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--out', default=None)
    ap.add_argument('--limit', type=int, default=0,
                    help='只跑前 N 句（0 = 全部）')
    ap.add_argument('--lang', default='ja',
                    help='目标语言**代号**（生产路径口径：translator.TARGETS = zh/en/ja/ko）')
    ap.add_argument('--before-lang', default='en',
                    help='「改前」口径的语言代号（旧实现 _guess_lang 只分 zh/en）')
    ap.add_argument('--device', default='NPU')
    args = ap.parse_args()

    out_path = args.out or os.path.join(
        HOME, 'app030_npu_ab', 'npu_ab_report.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    sys.path.insert(0, HERE)
    from app108_ja_corpus import JA, ZH_SENTENCES, EN_SENTENCES

    sentences = list(JA)
    if args.limit:
        sentences = sentences[:args.limit]

    ml = _lock_ctx()
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=1800, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        # 🔴 安静窗口（机器上没有别的模块在算）
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                   timeout=900.0, verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出（不与他模块的计时作业抢）')
            return 4

        import numpy as np
        import tts_engine as TE
        import openvino as ov

        core = ov.Core()
        print('[env] available_devices=%r' % (core.available_devices,))
        if args.device not in core.available_devices:
            print('[env] !! 设备 %s 不可用 ⇒ 退出（不在别的设备上偷跑）'
                  % args.device)
            return 2

        print('[env] 加载引擎（device=%s）…' % args.device)
        t0 = time.perf_counter()
        eng = TE.make_engine(device=args.device, on_log=lambda m: None)
        print('[env] 引擎就绪，用时 %.1f s' % (time.perf_counter() - t0))

        rows = []

        def run_one(text, language, tag, rep):
            """跑一句，返回遥测行。

            🔴🔴 **口径纪律（§78 自查发现）**：
              `language` 传的是**语言代号**（`zh`/`en`/`ja`/`ko`）
              ⇒ 与生产路径（`translator.TARGETS`）**逐字一致**；
              但引擎侧要**全称**（`map_language(code)`）⇒ 这里分开传。
              ⚠️ **旧版脚本传的是全称**（`'Japanese'`）⇒ 与生产口径**不一致**
              ⇒ 连带把 `estimate_sec` 喂成了英文口径 ⇒ **产出了假的 hang 判定**。
            """
            lang_code = language
            est_frames = TE.estimate_frames(text, lang_code)
            est_sec = TE.estimate_sec(text, lang_code)
            mnt = TE.clamp_max_new_tokens(text, lang_code)
            engine_lang = TE.map_language(lang_code)
            got_sec = 0.0
            n_frames = 0
            reason = 'eos'
            t1 = time.perf_counter()
            try:
                for chunk, sr in TE.stream(
                        eng, text, language=engine_lang,
                        max_new_tokens=mnt, est_sec=est_sec,
                        on_log=lambda m: None):
                    arr = np.asarray(chunk, dtype=np.float32)
                    got_sec += len(arr) / float(sr)
                    n_frames += 1
                    if n_frames >= est_frames * 3 + 36:
                        reason = 'cap'
                        break
            except Exception as e:
                reason = 'error:%s' % (type(e).__name__,)
            wall = time.perf_counter() - t1
            n_chars = len([c for c in text if not c.isspace()])
            return dict(
                tag=tag, rep=rep, lang=lang_code, engine_lang=engine_lang,
                text=text, n_chars=n_chars,
                est_frames=int(est_frames), est_sec=round(est_sec, 3),
                max_new_tokens=int(mnt),
                chunks=n_frames, got_sec=round(got_sec, 3),
                s_per_char=round(wall / max(1, n_chars), 4),
                wall_s=round(wall, 3),
                end_reason=reason,
                hang=(wall > max(3 * est_sec, est_sec + 8.0)),
            )

        # ── A/B：改前（English）vs 改后（目标语言）────────────────
        print('\n=== A/B：改前 %s vs 改后 %s ==='
              % (args.before_lang, args.lang))
        for i, s in enumerate(sentences):
            for rep in range(args.repeats):
                row_b = run_one(s, args.before_lang, 'before', rep)
                row_a = run_one(s, args.lang, 'after', rep)
                rows.append(row_b)
                rows.append(row_a)
                print('  [%2d] rep%d 改前 %-11s est_f=%4d got=%6.2fs '
                      's/字=%.3f %s | 改后 %-9s est_f=%4d got=%6.2fs '
                      's/字=%.3f %s'
                      % (i, rep, row_b['end_reason'], row_b['est_frames'],
                         row_b['got_sec'], row_b['s_per_char'],
                         'HANG' if row_b['hang'] else '',
                         row_a['end_reason'], row_a['est_frames'],
                         row_a['got_sec'], row_a['s_per_char'],
                         'HANG' if row_a['hang'] else ''))

        # ── 中文/英文回归各 10 句（改后 vs 改前，帧数/s 字无回退）──
        print('\n=== 回归：中文/英文各 10 句 ===')
        for tag, lst in (('zh', ZH_SENTENCES), ('en', EN_SENTENCES)):
            for i, s in enumerate(lst):
                lang = 'zh' if tag == 'zh' else 'en'
                r = run_one(s, lang, 'reg_' + tag, 0)
                rows.append(r)
                print('  [%s %2d] est_f=%4d got=%6.2fs s/字=%.3f %s'
                      % (tag, i, r['est_frames'], r['got_sec'],
                         r['s_per_char'], r['end_reason']))

        # ── 汇总 ────────────────────────────────────────────────
        def agg(tag):
            rs = [r for r in rows if r['tag'] == tag]
            return dict(
                n=len(rs),
                cap=sum(1 for r in rs if r['end_reason'] == 'cap'),
                hang=sum(1 for r in rs if r['hang']),
                err=sum(1 for r in rs if r['end_reason'].startswith('error')),
                got_sec_med=(sorted(r['got_sec'] for r in rs)[len(rs) // 2]
                             if rs else 0),
                s_per_char_med=(sorted(r['s_per_char'] for r in rs)[len(rs) // 2]
                                if rs else 0),
            )

        summary = dict(before=agg('before'), after=agg('after'),
                       reg_zh=agg('reg_zh'), reg_en=agg('reg_en'))
        # 🔴 判据：改后 cap=0 且 hang=0
        ok = (summary['after']['cap'] == 0
              and summary['after']['hang'] == 0
              and summary['after']['err'] == 0)
        summary['verdict_after_clean'] = ok

        report = dict(summary=summary, rows=rows,
                      device=args.device, repeats=args.repeats,
                      ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                      note='NPU 实测；持机器锁；不在 CPU 上跑推理')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('\n' + '=' * 68)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print('verdict_after_clean =', ok)
        print('报告已写入：%s' % out_path)
        print('=' * 68)
        return 0 if ok else 1
    finally:
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
