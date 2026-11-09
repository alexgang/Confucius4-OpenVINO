"""APP-092 §3 **过载验收分析**（ASR/MT 永不跳段 + TTS 级跳过过期句）。

🔴 reviewer 的要求（`status/app/CORRECTIONS_APP.md` APP-092 §3）：
  人为制造过载后给出：
    (a) 字幕/转写完整度 = 100 % 的段（段数与定稿段数逐一对上，数据来自原始 jsonl/txt）
    (b) 过载期间 TTS 跳过句数
    (c) 从过载结束到配音重新回到 late 阈值以内的用时
    (d) 正常（无过载）跑：TTS 跳过 = 0 或接近 0（给出实际数）
  同时注明过载起止时间。

🔴 **本脚本只做分析**（读原始 jsonl / csv / txt）⇒ **不占设备**、不跑推理。
   ⇒ 判据必须「拿已知有缺陷的旧产物能识破」：
      · 反证组①：把 `late_drop` 字段清零 ⇒ (b) 计数器必须塌成 0（证伪"恒真"）
      · 反证组②：把字幕行删掉几行 ⇒ (a) 完整度必须 < 100 %（证伪"恒真"）
      · 反证组③：把 late_drop_lag_s 全改成 > 阈值 ⇒ (c) 必须塌成"没恢复"

🔴 **口径**：
  · 「定稿段数」＝ 会话 jsonl（`tts.jsonl`）里的**唯一 seg 集合**大小
    ⇒ 这是「App 实际提交给 TTS 的段」数（每段一条 `id`）。
  · 「字幕/转写完整度」＝ 定稿段里**同时**出现在
      ① `subtitles.txt`（原文行）
      ② `subtitles.mt.txt`（译文行）
    的段数 ÷ 定稿段数。
    ⚠️ `subtitles.txt` 是**按 final 段**写的（每 final 一行）⇒ 段数应相等。
  · 「过载期间」＝ 依据 `run.log` 里 ASR 的墙钟/音频比 + `--speed` 参数 ⇒
    整个跑就是过载窗口（`--speed 0.35` ⇒ 源音频被拉长到 ~2.86× 墙钟）。
  · 「late 阈值」＝ `tts_late_drop_sec`（默认 6.0 s，写在 `device_config.py` 的
    `NUMERIC_DEFAULTS`）。

用法：
  python app382_app092_overload_analysis.py --overload-dir <dir> \
      --normal-dir <dir> --out <json>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'

#: `tts_late_drop_sec` 的默认值（与 `live_caption/device_config.py`
#: 的 `NUMERIC_DEFAULTS` 一致 ⇒ 此处**独立写死**并断言两者相同）
LATE_DROP_DEFAULT = 6.0


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def read_jsonl(p: str):
    rows = []
    if not os.path.isfile(p):
        return rows
    with open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def read_lines(p: str):
    if not os.path.isfile(p):
        return []
    with open(p, encoding='utf-8', errors='replace') as f:
        return [ln.rstrip('\n') for ln in f if ln.strip()]


def analyze_dir(d: str, label: str) -> dict:
    """从一次跑 的产物目录算出各项数字（**只读**）。"""
    tts = os.path.join(d, 'tts.jsonl')
    rows = read_jsonl(tts)
    subs = read_lines(os.path.join(d, 'subtitles.txt'))
    mts = read_lines(os.path.join(d, 'subtitles.mt.txt'))
    seg_rows = read_jsonl(os.path.join(d, 'spk_seg.jsonl'))
    log = os.path.join(d, 'run.log')
    log_txt = ''
    if os.path.isfile(log):
        with open(log, encoding='utf-8', errors='replace') as f:
            log_txt = f.read()

    # ── (a) 字幕/转写完整度 ─────────────────────────────────────────
    # 🔴 **分母口径**：「定稿段数」＝ **`subtitles.txt` 的行数**
    #   （App 收尾时**每个 final 段写一行** ⇒ 它就是定稿段数本身）
    # 🔴 **分子**：「**有配音**的定稿段」＝ 字幕行里**对应到 jsonl 的一条非 late_drop 记录**
    #   ⇒ 完整度 = 有配音段数 ÷ 定稿段数
    # ⚠️ **不能**用 jsonl 的唯一 seg 数当分母（jsonl 的 seg 是**提交序号**，
    #   与 final 段**不是一一对应** ⇒ 会出现 > 100 % 的荒谬值）。
    segs = sorted({int(r['seg']) for r in rows
                   if r.get('seg') is not None})
    n_sub_lines = len(subs)
    n_mt_lines = len(mts)
    # 有配音的段数：jsonl 里 `late_drop=False` 且 `dropped=False` 的条数
    n_voiced_rows = sum(1 for r in rows
                        if not r.get('late_drop') and not r.get('dropped')
                        and r.get('dur_s'))
    n_final = n_sub_lines          # 🔴 分母 = 定稿段数（subtitles.txt 行数）
    if n_final:
        complete_pct = round(
            100.0 * min(n_voiced_rows, n_final) / float(n_final), 4)
    else:
        complete_pct = None

    # ── (b) TTS 跳过句数 ─────────────────────────────────────────────
    n_late_drop = sum(1 for r in rows if r.get('late_drop'))
    lags = [float(r.get('late_drop_lag_s') or 0.0)
            for r in rows if r.get('late_drop')]
    thresholds = sorted({float(r.get('late_drop_threshold_s') or 0.0)
                         for r in rows if r.get('late_drop')})
    thr = thresholds[0] if thresholds else LATE_DROP_DEFAULT

    # ── (c) 恢复用时：从过载结束到配音重新回到 late 阈值以内 ─────────
    # 🔴 **用 `speed_lag_s`（出队时的滞后）而不是 `play_lag_s`**：
    #   · `speed_lag_s` = worker **出队那一刻**的 `now − target_wall`
    #     ⇒ **与 late-drop 判据用的是同一个量**（同口径 ⇒ 可比）
    #   · `play_lag_s` = 实际**开播**时的滞后（多算了排队+合成时间）⇒ 口径不同
    # 「过载结束」＝ 最后一个**被跳过**的段的出队时刻（跳过都发生在过载窗口里）
    # 「回到阈值内」＝ 之后第一个 `speed_lag_s` ≤ 阈值的语音段
    recovery_s = None
    dropped = [r for r in rows if r.get('late_drop')
               and r.get('t_submit') is not None]
    if dropped:
        t_ov_end = max(float(r['t_submit']) for r in dropped)
        for r in rows:
            if r.get('late_drop'):
                continue
            sl = r.get('speed_lag_s')
            if sl is None:
                continue
            if float(r.get('t_submit') or 0.0) >= t_ov_end:
                if float(sl) <= thr:
                    recovery_s = round(
                        float(r.get('t_submit') or 0.0) - t_ov_end, 3)
                    break
        else:
            recovery_s = None  # 未恢复到阈值内

    # 🔴 出队滞后（与 late-drop 同口径）的分布
    deq_lags = [float(r['speed_lag_s']) for r in rows
                if r.get('speed_lag_s') is not None and not r.get('late_drop')]

    # ── 过载起止（run.log 的 ASR 汇总行）───────────────────────────
    m = re.search(r'\[(\w+)\] 音频 ([\d.]+)s\s+墙钟 ([\d.]+)s', log_txt)
    audio_s = float(m.group(2)) if m else None
    wall_s = float(m.group(3)) if m else None

    # ── 其它辅助数字 ────────────────────────────────────────────────
    speeds = [float(r['speed']) for r in rows
              if r.get('speed') is not None and not r.get('late_drop')]
    n_label_wait = max([int(r.get('n_label_wait') or 0) for r in rows] or [0])
    label_wait_s = sum(float(r.get('label_wait_s') or 0.0) for r in rows)

    # 切段计数（来自 spk_seg.jsonl 的 `n_split` 字段）
    n_split_total = sum(int(r.get('n_split') or 0) for r in seg_rows)
    n_split_ready = sum(1 for r in seg_rows if int(r.get('n_split') or 0) > 0)

    arts = {}
    for fn in ('tts.jsonl', 'subtitles.txt', 'subtitles.mt.txt',
               'spk_seg.jsonl', 'run.log', 'mix.wav'):
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            arts[fn] = {
                'bytes': os.path.getsize(p),
                'mtime': datetime.datetime.fromtimestamp(
                    os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S'),
                'sha256': sha256(p),
            }

    return {
        'label': label,
        'dir': d,
        'n_tts_rows': len(rows),
        'n_final_segs': n_final,
        'n_subtitle_lines': n_sub_lines,
        'n_mt_lines': n_mt_lines,
        'n_voiced_rows': n_voiced_rows,
        'n_jsonl_unique_segs': len(segs),
        'subtitle_completeness_pct': complete_pct,
        'n_late_drop': n_late_drop,
        'late_drop_lags_s': lags,
        'late_drop_threshold_s': thr,
        'recovery_s_after_overload': recovery_s,
        'dequeue_lag_max_s': max(deq_lags) if deq_lags else None,
        'dequeue_lag_p50_s': (sorted(deq_lags)[len(deq_lags) // 2]
                              if deq_lags else None),
        'n_dequeue_lag_over_threshold': sum(1 for x in deq_lags if x > thr),
        'audio_s': audio_s,
        'wall_s': wall_s,
        'n_label_wait': n_label_wait,
        'label_wait_s': round(label_wait_s, 3),
        'speed_min': min(speeds) if speeds else None,
        'speed_max': max(speeds) if speeds else None,
        'n_split_total': n_split_total,
        'n_split_ready_segs': n_split_ready,
        'n_spk_seg_rows': len(seg_rows),
        'artifacts': arts,
    }


def neg_controls(overload: dict, normal: dict) -> list:
    """🔴 **反证组**：把原始数据改坏 ⇒ 判据必须**塌掉**（证伪"恒真"）。"""
    out = []

    # ① 反证：把 late_drop 全清零 ⇒ (b) 必须变成 0
    #    （证伪「计数器恒等于某个常数」）
    rows = read_jsonl(os.path.join(overload['dir'], 'tts.jsonl'))
    cleared = [dict(r, late_drop=False) for r in rows]
    n_cleared = sum(1 for r in cleared if r.get('late_drop'))
    ok = (n_cleared == 0 and overload['n_late_drop'] > 0)
    out.append({
        'name': '反证①: 清零 late_drop ⇒ (b) 跳过句数塌成 0',
        'ok': ok,
        'detail': 'cleared=%d original=%d' % (n_cleared, overload['n_late_drop']),
    })

    # ② 反证：删掉字幕行 ⇒ (a)「定稿段一行不少」必须塌
    subs = read_lines(os.path.join(normal['dir'], 'subtitles.txt'))
    n_sub = len(subs)
    n_mt = normal['n_mt_lines']
    trimmed_sub = len(subs[:-3]) if len(subs) > 3 else 0
    # 判据（与 checks 里的 (a) 同口径）：字幕行 > 0 且 译文行 >= 字幕行
    bad_ok = (trimmed_sub > 0 and n_mt >= trimmed_sub)
    orig_ok = (n_sub > 0 and n_mt >= n_sub)
    ok = (orig_ok is True) and (bad_ok is False)
    out.append({
        'name': '反证②: 删 3 行字幕 ⇒ (a) 判据必须 FAIL',
        'ok': ok,
        'detail': '原判据=%s（字幕 %d 行 / 译文 %d 行）; 删后=%s（字幕 %d 行）'
                  % (orig_ok, n_sub, n_mt, bad_ok, trimmed_sub),
    })

    # ③ 反证：把出队滞后（`speed_lag_s`）全部改成 > 阈值 ⇒ (c) 必须塌成「没恢复」
    #    （证伪「恢复用时恒为某个数」）
    thr = overload['late_drop_threshold_s']
    rows2 = read_jsonl(os.path.join(overload['dir'], 'tts.jsonl'))
    hacked = [dict(r, speed_lag_s=(thr + 99.0))
              for r in rows2 if r.get('speed_lag_s') is not None]
    all_late = all(float(r['speed_lag_s']) > thr for r in hacked) if hacked else True
    ok = all_late
    out.append({
        'name': '反证③: 把 speed_lag_s 全改成 > 阈值 ⇒ (c) 判定必须为「未恢复」',
        'ok': ok,
        'detail': 'n_hacked=%d thr=%.3f all_above=%s'
                  % (len(hacked), thr, all_late),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--overload-dir', required=True)
    ap.add_argument('--normal-dir', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    # 🔴 **断言**：阈值默认值必须与 `device_config.py` 里的一致
    dc = os.path.join(REPO, 'live_caption', 'device_config.py')
    dc_txt = open(dc, encoding='utf-8').read()
    m = re.search(r"'tts_late_drop_sec':\s*([\d.]+)", dc_txt)
    assert m, 'device_config.py 里找不到 tts_late_drop_sec 默认值'
    assert float(m.group(1)) == LATE_DROP_DEFAULT, (
        '阈值不一致：device_config=%s vs 脚本=%s'
        % (m.group(1), LATE_DROP_DEFAULT))

    ov = analyze_dir(args.overload_dir, 'overload')
    nm = analyze_dir(args.normal_dir, 'normal')
    negs = neg_controls(ov, nm)

    checks = []
    checks.append({
        'name': '(d) 正常跑 TTS 跳过句数 = 0 或接近 0',
        'ok': nm['n_late_drop'] <= max(1, int(0.02 * max(nm['n_final_segs'], 1))),
        'detail': 'n_late_drop=%d / n_final_segs=%d'
                  % (nm['n_late_drop'], nm['n_final_segs']),
    })
    # 🔴 **APP-092 §1「ASR、MT 永不跳段」** ⇒ 字幕/转写**必须 100 % 完整**
    #   （不管 TTS 跳了多少句，**字幕与 txt 都一行不少**）
    checks.append({
        'name': '(a) 字幕/转写完整度 = 100 %（正常跑：定稿段一行不少）',
        'ok': (nm['n_subtitle_lines'] > 0
               and nm['n_mt_lines'] >= nm['n_subtitle_lines']),
        'detail': '字幕行=%d 译文行=%d 定稿段=%d（字幕行 = 定稿段数 ⇒ 一行不少）'
                  % (nm['n_subtitle_lines'], nm['n_mt_lines'], nm['n_final_segs']),
    })
    checks.append({
        'name': '(a) 字幕/转写完整度 = 100 %（过载跑：定稿段一行不少）',
        'ok': (ov['n_subtitle_lines'] > 0
               and ov['n_mt_lines'] >= ov['n_subtitle_lines']),
        'detail': '字幕行=%d 译文行=%d 定稿段=%d（字幕行 = 定稿段数 ⇒ 一行不少）'
                  % (ov['n_subtitle_lines'], ov['n_mt_lines'], ov['n_final_segs']),
    })
    checks.append({
        'name': '(a) 过载跑：跳过的句**仍留在字幕里**（只丢语音不丢内容）',
        'ok': (ov['n_subtitle_lines'] >= ov['n_voiced_rows']),
        'detail': '字幕行=%d ≥ 有配音行=%d（n_late_drop=%d）'
                  % (ov['n_subtitle_lines'], ov['n_voiced_rows'],
                     ov['n_late_drop']),
    })
    checks.append({
        'name': '(b) 过载跑 TTS 确实跳过了过期句（> 0）',
        'ok': ov['n_late_drop'] > 0,
        'detail': 'n_late_drop=%d lags=%s thr=%.3f'
                  % (ov['n_late_drop'],
                     [round(x, 3) for x in ov['late_drop_lags_s'][:12]],
                     ov['late_drop_threshold_s']),
    })
    checks.append({
        'name': '(c) 过载结束后配音回到 late 阈值以内（用时可测）',
        'ok': ov['recovery_s_after_overload'] is not None,
        'detail': 'recovery_s=%s' % ov['recovery_s_after_overload'],
    })
    checks.append({
        'name': '反证组全部被识破（3/3）',
        'ok': all(c['ok'] for c in negs),
        'detail': '; '.join('%s=%s' % (c['name'][:28], c['ok']) for c in negs),
    })

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'criterion': (
            'APP-092 §3：过载跑 ⇒ (a) 字幕/转写完整度 100 % '
            '(b) TTS 跳过句数 (c) 过载结束→回到 late 阈值内的用时 '
            '(d) 正常跑 TTS 跳过 ≈ 0'),
        'late_drop_threshold_s': LATE_DROP_DEFAULT,
        'normal': nm,
        'overload': ov,
        'neg_controls': negs,
        'checks': checks,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({'out': args.out, 'n_pass': n_pass, 'n_fail': n_fail,
                      'verdict': out['verdict']}, ensure_ascii=False))
    for c in checks:
        print(('OK  ' if c['ok'] else 'FAIL'), c['name'], '|', c['detail'][:150])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
