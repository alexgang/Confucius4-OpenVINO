#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app223 —— 【APP-061 ①③④⑤ + ③(e)】**真机验收** harness（设备级）。

## 为什么有这个脚本

APP-061 的代码层修复已在 §127 完成（`app215` 29/0、`app220` 39/0、`app219` 13/0），
但 **APP-061 的验收标准全部是「设备级实测」**：

| 编号 | reviewer 原文验收 | 判据来源 |
|---|---|---|
| ① | 「没有可用的音色」出现 **0 次**；`tts_cuda_trace.log` 里 `REQ` 数 = 提交句数 | 会话日志 / 边车 trace |
| ③ | `uf_in_sentence_ms` 总和 ≤ 音频总时长 **0.5 %**，且 ≥ **95 %** 的句子为 0；ASR RTF 相对 **TTS off** 增量 ≤ **+0.10**；**丢句 = 0**；报 TTS 首包 P50/P95 | 逐句 jsonl + CLI 汇总行 |
| ④ | 声纹计算次数 ≤ **2 × 说话人数**；每次声纹计算前后 1 s 内有对应 `new_spk`/refine 记录；**「克隆音色已更新…10.0 s」这类定时更新 0 次** | 会话日志 |
| ⑤ | 逐句 jsonl 里 `voice_kind=clone` 占比 ≥ **80 %**；`no_spk_label` 回落次数 ≤ 说话人数 × 2 | 逐句 jsonl + 会话日志 |

⇒ §127⑧ 的 ⛔「未实测」就是这些 ⇒ 本脚本把它们**变成可一键复跑的判据**。

## 🔴 三条纪律

1. 🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（仓库根 `machine_lock_app`，fail-closed）。
2. 🔴 **必须等安静窗口** ⇒ 用户自己正在测的会话在跑时**不开跑**
   （§128 实测：安静窗口被用户 v2.1 GUI 会话 PID 14712 挡住 ⇒ 90 s 超时 ⇒ 退出 4）。
3. 🔴 **判据三态** True / False / **None（无法判定）** ⇒ 「无法判定」≠「不合格」
   ⇒ **None 既不重建、也不改动**，只报告。

## 🔴 判据非恒真（反证）

`--self-test` 模式**不需要设备**：拿 **reviewer 点名的那份 v2.1 会话日志**
（`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261101_212026.log`）跑同一套判据
⇒ 必须 **FAIL**（83 次回落预设 A / 50 次「没有可用的音色」/ 54 次定时克隆更新 /
声纹计算与 `new_spk` 对不上）⇒ 证明判据**能识破旧版缺陷**，不是恒真。

## 用法

```bat
:: ① 不需要设备的自检（反证：判据能识破 v2.1 缺陷）
python results/app/app223_app061_device_acceptance.py --self-test

:: ② 真机验收（需机器空闲 + 安静窗口）
python results/app/app223_app061_device_acceptance.py --run

:: ③ 只打印命令不跑
python results/app/app223_app061_device_acceptance.py --dry-run
```

## 产物

`results/app/app223_app061_device_acceptance_evidence.json`
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
PKG_V22 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
PKG_V21 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.1')
HIST_LOG = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                        'session_20261101_212026.log')
OUT_JSON = os.path.join(HERE, 'app223_app061_device_acceptance_evidence.json')
OUT_DIR = os.path.join(HERE, 'app223_device_out')


# ══════════════════════════════════════════════════════════════════════
# 解析层
# ══════════════════════════════════════════════════════════════════════
# 🔴 汇总行是 CLI 自己打的（`live_caption_app.py` L6077-6078）：
#   `[gpu_int8] 音频 300.0s  墙钟 300.6s  RTF(计算) 0.685
#                出字延迟中位 375 ms  最大积压 1.2s  段 46`
# ⇒ 与 app199（APP-054 ③）**同一口径**，不另立标准。
_RE_SUMMARY = re.compile(
    r'\[(?P<engine>[^\]]+)\]\s*音频\s+(?P<audio>[0-9.]+)s\s*'
    r'墙钟\s+(?P<wall>[0-9.]+)s\s*'
    r'RTF\(计算\)\s+(?P<rtf>[0-9.]+)\s*'
    r'出字延迟中位\s+(?P<lat>[0-9.]+|None)\s*ms\s*'
    r'最大积压\s+(?P<backlog>[0-9.]+)s\s*'
    r'段\s+(?P<segs>[0-9]+)')

# 🔴 会话日志行首时间戳：`21:21:05 [TTS] ...`
_RE_TS = re.compile(r'^\s*(\d{2}):(\d{2}):(\d{2})\b')

_RE_LABEL_BACKFILL = re.compile(r'标签补到[：:]\s*第\s*(\d+)\s*段\s*=\s*'
                                r'(S\d+)')
_RE_NEW_SPK_HINT = re.compile(r'新说话人|音色已细化|已登记音色')
_RE_EMBEDDING = re.compile(r'speaker embedding 就绪')
_RE_CLONE_UPDATE = re.compile(
    r'克隆音色已更新(?:（BabelVox x-vector|（CUDA 边车 ref_audio)?'
    r'[（(]?[^)）]*?[，,]\s*([0-9]+(?:\.[0-9]+)?)\s*s')
_RE_KEEP_LAST = re.compile(r'spk_pending⇒keep_last')
_RE_FALLBACK_PRESET = re.compile(r'已回落到预设 A')
# 🔴🔴🔴 APP-063 复盘（2026-11-02 21:0x）：**判据①曾是假 PASS** ——
#   实测日志里的真实故障串是 **`没有可用引擎`**（`tts_worker.py:3763/3805`）
#   与 **`spk 音色登记失败`**，而旧正则只抓 `没有可用的音色`
#   （**另一条**故障：语音没送到边车）⇒ **抓不到真实故障**。
#   ⇒ 现在三条**都**算「没有可用音色」。
_RE_NO_VOICE = re.compile(
    r'没有可用的音色|没有可用引擎|spk 音色登记失败')


def _log_ts(line):
    """行首 `HH:MM:SS` ⇒ 当天秒数（float）；没有就 None。"""
    m = _RE_TS.match(line)
    if not m:
        return None
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60
            + int(m.group(3)))


def parse_log(text):
    """解析会话日志 ⇒ 逐条计数 + 时间戳（判据的原料）。"""
    out = {
        'bytes': len(text.encode('utf-8', 'replace')),
        'n_lines': len(text.splitlines()),
        'n_no_voice_error': len(_RE_NO_VOICE.findall(text)),
        'n_fallback_preset': len(_RE_FALLBACK_PRESET.findall(text)),
        'n_keep_last': len(_RE_KEEP_LAST.findall(text)),
        'n_embedding': len(_RE_EMBEDDING.findall(text)),
        'clone_updates': [],
        'embedding_ts': [],
        'new_spk_ts': [],
        'spk_ids': [],
    }
    seen_spk = set()
    for line in text.splitlines():
        ts = _log_ts(line)
        # ① 克隆更新（定时 vs 按句绑定：靠「时长」和「有没有 new_spk 配对」区分）
        m = _RE_CLONE_UPDATE.search(line)
        if m:
            try:
                dur = float(m.group(1))
            except (TypeError, ValueError):
                dur = None
            out['clone_updates'].append({'ts': ts, 'dur_s': dur,
                                         'line': line.strip()[:160]})
        if _RE_EMBEDDING.search(line):
            out['embedding_ts'].append(ts)
        # ② 说话人事件：标签补到（首次出现的 spk）或「新说话人/已细化/已登记」
        m = _RE_LABEL_BACKFILL.search(line)
        if m:
            spk = m.group(2)
            out['spk_ids'].append(spk)
            if spk not in seen_spk or _RE_NEW_SPK_HINT.search(line):
                seen_spk.add(spk)
                out['new_spk_ts'].append(ts)
        elif _RE_NEW_SPK_HINT.search(line) and ts is not None:
            out['new_spk_ts'].append(ts)
    out['n_clone_updates'] = len(out['clone_updates'])
    out['n_speakers'] = len(set(out['spk_ids']))
    out['n_new_spk_events'] = len(out['new_spk_ts'])
    # ③ 声纹计算与 new_spk/refine 的 ±1 s 配对
    paired = []
    for ts in out['embedding_ts']:
        hit = None
        if ts is not None:
            for mts in out['new_spk_ts']:
                if mts is None:
                    continue
                if abs(mts - ts) <= 1.0:
                    hit = mts
                    break
        paired.append(hit is not None)
    out['n_embedding_paired'] = sum(1 for x in paired if x)
    out['n_embedding_unpaired'] = sum(1 for x in paired if not x)
    # ④ 定时克隆更新（没有 new_spk/refine 配对的克隆更新）
    out['clone_updates_unpaired'] = [
        c for c in out['clone_updates'] if not _paired(c['ts'],
                                                        out['new_spk_ts'])]
    out['n_clone_updates_unpaired'] = len(out['clone_updates_unpaired'])
    out['n_clone_updates_10s'] = sum(
        1 for c in out['clone_updates']
        if c['dur_s'] is not None and c['dur_s'] >= 9.9)
    return out


def _paired(ts, markers):
    if ts is None:
        return False
    for m in markers:
        if m is None:
            continue
        if abs(m - ts) <= 1.0:
            return True
    return False


def parse_jsonl(path):
    """逐句 jsonl ⇒ 句级遥测统计（③⑤ 的原料）。"""
    out = {'exists': False, 'path': path}
    if not path or not os.path.isfile(path):
        return out
    out['exists'] = True
    out['bytes'] = os.path.getsize(path)
    rows = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    out['n_rows'] = len(rows)
    ok_rows = [r for r in rows if not r.get('dropped')]
    out['n_dropped'] = sum(1 for r in rows if r.get('dropped'))
    out['n_error'] = sum(1 for r in rows if r.get('error'))

    def _num(r, k):
        v = r.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    ufs = [_num(r, 'uf_in_sentence_ms') for r in ok_rows]
    ufs = [v for v in ufs if v is not None]
    out['n_uf_known'] = len(ufs)
    out['uf_in_sentence_ms_total'] = sum(ufs)
    out['uf_in_sentence_ms_max'] = max(ufs) if ufs else None
    out['n_sent_uf_zero'] = sum(1 for v in ufs if v <= 0)
    out['n_sent_uf_nonzero'] = sum(1 for v in ufs if v > 0)
    out['pct_sent_uf_zero'] = (
        round(100.0 * out['n_sent_uf_zero'] / len(ufs), 3) if ufs else None)

    # ⑤ voice_kind 占比
    kinds = {}
    for r in ok_rows:
        k = r.get('voice_kind') or 'unknown'
        kinds[k] = kinds.get(k, 0) + 1
    out['voice_kind_counts'] = kinds
    out['pct_voice_kind_clone'] = (
        round(100.0 * kinds.get('clone', 0) / len(ok_rows), 3)
        if ok_rows else None)
    out['voice_spk_ids'] = sorted({str(r.get('voice_spk'))
                                   for r in ok_rows if r.get('voice_spk')})

    # ③ TTS 首包延迟 P50/P95（t_first_packet = t_first_packet − t_submit）
    fps = [_num(r, 't_first_packet') for r in ok_rows]
    fps = [v for v in fps if v is not None]
    fps.sort()
    out['n_first_packet_known'] = len(fps)
    if fps:
        def _pct(p):
            if len(fps) == 1:
                return round(fps[0], 4)
            k = (len(fps) - 1) * p
            lo = int(k)
            hi = min(lo + 1, len(fps) - 1)
            return round(fps[lo] + (fps[hi] - fps[lo]) * (k - lo), 4)
        out['first_packet_p50_s'] = _pct(0.50)
        out['first_packet_p95_s'] = _pct(0.95)
    else:
        out['first_packet_p50_s'] = None
        out['first_packet_p95_s'] = None

    rtfs = [_num(r, 'synth_rtf') for r in ok_rows]
    rtfs = [v for v in rtfs if v is not None]
    out['synth_rtf_mean'] = round(statistics.fmean(rtfs), 4) if rtfs else None
    out['synth_rtf_p95'] = (round(sorted(rtfs)[int(0.95 * (len(rtfs) - 1))], 4)
                            if rtfs else None)
    out['synth_rtf_n'] = len(rtfs)
    return out


def parse_summary(text):
    """CLI 汇总行 ⇒ 墙钟 / RTF / 出字延迟 / 最大积压 / 段数。"""
    out = {'summary_found': False}
    for k in ('engine', 'audio_s', 'wall_s', 'rtf', 'first_char_latency_ms',
              'max_backlog_s', 'n_segs'):
        out[k] = None
    m = _RE_SUMMARY.search(text)
    if m:
        out['summary_found'] = True
        out['engine'] = m.group('engine')
        out['audio_s'] = float(m.group('audio'))
        out['wall_s'] = float(m.group('wall'))
        out['rtf'] = float(m.group('rtf'))
        lat = m.group('lat')
        out['first_char_latency_ms'] = (None if lat == 'None'
                                        else float(lat))
        out['max_backlog_s'] = float(m.group('backlog'))
        out['n_segs'] = int(m.group('segs'))
    # 丢句计数（CLI 第二条汇总：`丢弃 N  重启 M`）
    m2 = re.search(r'丢弃\s+(\d+)', text)
    out['n_dropped_reported'] = int(m2.group(1)) if m2 else None
    return out


# ══════════════════════════════════════════════════════════════════════
# 判据层（三态）
# ══════════════════════════════════════════════════════════════════════
def _checks():
    return []


def add(checks, name, verdict, detail, why=''):
    """verdict ∈ True / False / None（无法判定）。"""
    checks.append(dict(name=name, verdict=verdict, detail=detail, why=why))
    return checks


def judge(arms, cfg):
    """按 APP-061 原文逐条判定。`arms` = {arm_name: parsed_result}。"""
    checks = _checks()
    off = arms.get('tts_off')
    preset = arms.get('tts_on_preset')
    clone = arms.get('tts_on_clone')

    # ── ① 「没有可用的音色」= 0 ──────────────────────────────────
    for nm, arm in (('tts_on_preset', preset), ('tts_on_clone', clone)):
        if not arm:
            add(checks, '①「没有可用的音色」= 0（%s）' % nm, None,
                {'arm': nm}, '该臂未跑（无数据）⇒ 无法判定')
            continue
        lv = arm['log']
        add(checks, '①「没有可用的音色」= 0（%s）' % nm,
            lv['n_no_voice_error'] == 0,
            {'n_no_voice_error': lv['n_no_voice_error'],
             'n_fallback_preset': lv['n_fallback_preset']},
            'APP-061①：每句都报「没有可用的音色」⇒ 请求没送到边车 ⇒ 全程无声')

    # ── ①b CUDA 的 REQ 数 = 提交句数 ─────────────────────────────
    add(checks, '①b CUDA 边车 REQ 数 = 提交句数', None,
        {'cuda_trace': None},
        '本机**无 CUDA 运行时**（§78.6）⇒ CUDA 臂无法在本机跑 ⇒ 无法判定'
        '（≠ 不合格）；CUDA 路径的**代码层**由 `app215` 29/0 覆盖')

    # ── ③ 句内欠载 ≤ 0.5 %，≥95 % 句子为 0 ──────────────────────
    if clone and clone['jsonl']['exists']:
        j = clone['jsonl']
        audio_s = (clone['summary'].get('audio_s')
                   or cfg.get('duration', 300.0))
        limit_ms = audio_s * 1000.0 * 0.005
        tot = j.get('uf_in_sentence_ms_total')
        add(checks, '③-① uf_in_sentence_ms 总和 ≤ 音频时长的 0.5 %',
            (tot is not None and tot <= limit_ms),
            {'uf_in_sentence_ms_total': tot, 'limit_ms': round(limit_ms, 1),
             'audio_s': audio_s},
            'APP-061③：句内欠载 = **听得见的断音**')
        add(checks, '③-② ≥ 95 % 的句子 uf = 0',
            (j.get('pct_sent_uf_zero') is not None
             and j['pct_sent_uf_zero'] >= 95.0),
            {'pct_sent_uf_zero': j.get('pct_sent_uf_zero'),
             'n_sent_uf_zero': j.get('n_sent_uf_zero'),
             'n_sent_uf_nonzero': j.get('n_sent_uf_nonzero')},
            'APP-061③：绝大多数句子不得有句内欠载')
    else:
        add(checks, '③-① uf_in_sentence_ms 总和 ≤ 音频时长的 0.5 %', None,
            {}, 'clone 臂未跑 ⇒ 无法判定')
        add(checks, '③-② ≥ 95 % 的句子 uf = 0', None, {},
            'clone 臂未跑 ⇒ 无法判定')

    # ── ③ ASR RTF 相对 TTS off 的增量 ≤ +0.10 ────────────────────
    if off and clone and off['summary'].get('rtf') is not None \
            and clone['summary'].get('rtf') is not None:
        d = round(clone['summary']['rtf'] - off['summary']['rtf'], 4)
        add(checks, '③-③ ASR RTF 增量（TTS on − TTS off）≤ +0.10',
            d <= 0.10,
            {'rtf_off': off['summary']['rtf'],
             'rtf_on': clone['summary']['rtf'], 'delta': d, 'limit': 0.10},
            'APP-061③：TTS 上 NPU 不许把 ASR 拖慢')
    else:
        add(checks, '③-③ ASR RTF 增量（TTS on − TTS off）≤ +0.10', None, {},
            '缺 TTS off 臂或汇总行 ⇒ 无法判定')

    # ── ③ 丢句 = 0 ───────────────────────────────────────────────
    if clone:
        j = clone['jsonl']
        n_drop = j.get('n_dropped')
        add(checks, '③-④ 丢句数 = 0', (n_drop == 0),
            {'n_dropped': j.get('n_dropped'),
             'n_dropped_reported':
                 clone['summary'].get('n_dropped_reported'),
             'n_rows': j.get('n_rows')},
            'APP-061③：丢句 = 0')
        add(checks, '③-⑤ 报 TTS 首包延迟 P50/P95', None,
            {'p50_s': j.get('first_packet_p50_s'),
             'p95_s': j.get('first_packet_p95_s')},
            'reviewer 只要求**报告** P50/P95（无阈值）⇒ 只报数不判定')
    else:
        add(checks, '③-④ 丢句数 = 0', None, {}, 'clone 臂未跑 ⇒ 无法判定')

    # ── ④ 克隆时机（声纹计算次数 / 配对 / 定时更新） ─────────────
    if clone:
        lv = clone['log']
        n_spk = max(lv['n_speakers'], 1)
        add(checks, '④-① 声纹计算次数 ≤ 2 × 说话人数',
            lv['n_embedding'] <= 2 * n_spk,
            {'n_embedding': lv['n_embedding'], 'n_speakers': lv['n_speakers'],
             'limit': 2 * n_spk},
            'APP-061④：只有换人才取样 ⇒ 声纹计算次数 ≈ 说话人数 × 1–2')
        add(checks, '④-② 每次声纹计算 ±1 s 内有 new_spk/refine 记录',
            (lv['n_embedding'] > 0
             and lv['n_embedding_unpaired'] == 0),
            {'n_embedding': lv['n_embedding'],
             'n_paired': lv['n_embedding_paired'],
             'n_unpaired': lv['n_embedding_unpaired']},
            'APP-061④：每次声纹计算都要能对上「谁在什么时候换了人」')
        add(checks, '④-③ 定时克隆更新（无 new_spk 配对）= 0 次',
            lv['n_clone_updates_unpaired'] == 0,
            {'n_clone_updates': lv['n_clone_updates'],
             'n_unpaired': lv['n_clone_updates_unpaired'],
             'n_10s': lv['n_clone_updates_10s'],
             'samples': [c['line'] for c in
                         lv['clone_updates_unpaired'][:5]]},
            'APP-061④：「克隆音色已更新…10.0 s」这类定时更新必须 0 次')
    else:
        for n in ('④-① 声纹计算次数 ≤ 2 × 说话人数',
                  '④-② 每次声纹计算 ±1 s 内有 new_spk/refine 记录',
                  '④-③ 定时克隆更新（无 new_spk 配对）= 0 次'):
            add(checks, n, None, {}, 'clone 臂未跑 ⇒ 无法判定')

    # ── ⑤ 克隆音色占比 / 回落次数 ────────────────────────────────
    if clone:
        j = clone['jsonl']
        lv = clone['log']
        pct = j.get('pct_voice_kind_clone')
        add(checks, '⑤-① voice_kind=clone 占比 ≥ 80 %',
            (pct is not None and pct >= 80.0),
            {'pct_voice_kind_clone': pct,
             'voice_kind_counts': j.get('voice_kind_counts')},
            'APP-061⑤：用户抱怨的「男声被女声播出」就是 clone 占比太低')
        n_spk = max(lv['n_speakers'], 1)
        add(checks, '⑤-② no_spk_label 回落次数 ≤ 说话人数 × 2',
            lv['n_fallback_preset'] <= 2 * n_spk,
            {'n_fallback_preset': lv['n_fallback_preset'],
             'n_speakers': lv['n_speakers'], 'limit': 2 * n_spk,
             'n_keep_last': lv['n_keep_last']},
            'APP-061⑤：回落太多 = 克隆没生效')
        add(checks, '⑤-③ reviewer 主观核对（性别/音色）', None,
            {'n_sent_for_review': j.get('n_rows')},
            '**人工项**（reviewer 抽 10 句）⇒ 本脚本不代判')
    else:
        add(checks, '⑤-① voice_kind=clone 占比 ≥ 80 %', None, {},
            'clone 臂未跑 ⇒ 无法判定')
        add(checks, '⑤-② no_spk_label 回落次数 ≤ 说话人数 × 2', None, {},
            'clone 臂未跑 ⇒ 无法判定')

    # ── ③(e) CPU 卸载候选 A/B ────────────────────────────────────
    add(checks, '③(e) CPU 卸载候选 A/B（旁路/克隆 speaker_enc/'
                'TTS tok_decoder）', None, {},
        '本轮未做（需 GUI+CLI 各一次、ABBA、持机器锁）⇒ 无法判定')
    return checks


# ══════════════════════════════════════════════════════════════════════
# 自检（反证：不需要设备）
# ══════════════════════════════════════════════════════════════════════
def self_test():
    """拿 reviewer 点名的 v2.1 会话日志跑同一套判据 ⇒ 必须 FAIL。"""
    res = {'log': HIST_LOG, 'exists': os.path.isfile(HIST_LOG)}
    if not res['exists']:
        res['verdict'] = 'NONE'
        res['why'] = '找不到历史日志 ⇒ 无法做反证'
        return res
    with open(HIST_LOG, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    lv = parse_log(text)
    res['parsed'] = {k: lv[k] for k in (
        'n_lines', 'n_no_voice_error', 'n_fallback_preset', 'n_embedding',
        'n_clone_updates', 'n_clone_updates_10s', 'n_clone_updates_unpaired',
        'n_speakers', 'n_new_spk_events', 'n_embedding_paired',
        'n_embedding_unpaired', 'n_keep_last')}
    res['clone_update_samples'] = [c['line'] for c in
                                   lv['clone_updates'][:5]]
    # 期望（reviewer 原文）：
    #   「已回落到预设 A（不静默）（原因：no_spk_label）」83 次
    #   「克隆音色已更新…」定时更新多次（10.0 s）
    #   声纹计算与 new_spk 对不上（4 次 new_spk 在 21:23:25 之后）
    exp_fallback = 83
    exp_10s = lv['n_clone_updates_10s']
    checks = [
        ('解析器抓到「已回落到预设 A」83 次（reviewer 原文）',
         lv['n_fallback_preset'] == exp_fallback, lv['n_fallback_preset']),
        ('解析器抓到「没有可用的音色」> 0（reviewer 原文 50 次）',
         lv['n_no_voice_error'] > 0, lv['n_no_voice_error']),
        ('解析器抓到 10.0 s 定时克隆更新 > 0', exp_10s > 0, exp_10s),
        ('判据④-③ 在 v2.1 上必须 FAIL（有未配对的定时克隆更新）',
         lv['n_clone_updates_unpaired'] > 0, lv['n_clone_updates_unpaired']),
        ('判据④-② 在 v2.1 上必须 FAIL（声纹计算对不上 new_spk）',
         lv['n_embedding_unpaired'] > 0, lv['n_embedding_unpaired']),
    ]
    res['checks'] = [dict(name=n, ok=bool(ok), detail=d) for n, ok, d in checks]
    res['n_pass'] = sum(1 for c in res['checks'] if c['ok'])
    res['n_fail'] = len(res['checks']) - res['n_pass']
    res['verdict'] = 'PASS' if res['n_fail'] == 0 else 'FAIL'
    res['meaning'] = ('PASS = 判据在**已知有缺陷的旧产物**上能识破缺陷 '
                      '⇒ 判据非恒真；此时它对 v2.2 的判定才可信')
    return res


# ══════════════════════════════════════════════════════════════════════
# 真机跑臂
# ══════════════════════════════════════════════════════════════════════
ARMS = {
    # name: (tts, voice, speaker, note)
    'tts_off': ('off', 'A', 'off', '基线：只要 ASR+MT（供 ③-③ 比对 RTF）'),
    'tts_on_preset': ('on', 'A', 'off', '①：预设 A，验「没有可用的音色」= 0'),
    'tts_on_clone': ('on', 'follow_speaker', 'on',
                     '③④⑤：跟随说话人 + 开旁路'),
}


def arm_cmd(pkg, arm, wav, out_wav, out_jsonl, out_txt, duration):
    tts, voice, speaker, _ = ARMS[arm]
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    return [py, app,
            '--cli', '--file', wav, '--engine', 'gpu_int8',
            '--translate', 'zh',
            '--tts', tts,
            '--tts-voice', voice,
            '--speaker', speaker,
            '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
            '--tts-device', 'NPU',
            '--max-seconds', str(duration),
            '--tts-out', out_wav,
            '--tts-jsonl', out_jsonl,
            '--out', out_txt]


def _ensure_out_dir():
    """建输出目录，并放一个**自带的 `.gitignore`**（`*`）。

    🔴 §129：产物目录在**仓库内** ⇒ `.wav`/`.log` 被根 `.gitignore` 命中，
      但 **`.jsonl` / `.txt` 不会被忽略** ⇒ 真机跑完会留下一堆未跟踪文件。
    ⇒ 在**产物目录内部**放一个 `.gitignore`（内容 `*`）⇒ 全部产物自动被忽略，
      **不用改仓库根的 `.gitignore`**（那是全仓库共享文件，不该由本模块改）。
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    gi = os.path.join(OUT_DIR, '.gitignore')
    if not os.path.isfile(gi):
        with open(gi, 'w', encoding='utf-8') as f:
            f.write('*\n')


def run_arm(pkg, arm, wav, duration, tag=''):
    _ensure_out_dir()
    stem = os.path.join(OUT_DIR, '%s%s' % (arm, tag))
    out_wav = stem + '.wav'
    out_jsonl = stem + '.tts.jsonl'
    out_txt = stem + '.txt'
    log_path = stem + '.log'
    cmd = arm_cmd(pkg, arm, wav, out_wav, out_jsonl, out_txt, duration)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)     # §112：宿主 PYTHONPATH 会污染包内 python
    env.pop('PYTHONHOME', None)
    env['LIVECAP_PKG'] = pkg
    t0 = time.perf_counter()
    with open(log_path, 'wb') as lf:
        proc = subprocess.run(cmd, env=env, stdout=lf,
                              stderr=subprocess.STDOUT)
    wall = time.perf_counter() - t0
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    res = {
        'arm': arm, 'pkg': pkg, 'cmd': cmd, 'rc': proc.returncode,
        'runner_wall_s': round(wall, 2),
        'log_path': log_path, 'log_bytes': os.path.getsize(log_path),
        'wav_path': out_wav, 'jsonl_path': out_jsonl, 'txt_path': out_txt,
        'summary': parse_summary(text),
        'log': parse_log(text),
        'jsonl': parse_jsonl(out_jsonl),
    }
    for p in (out_wav, out_jsonl, out_txt, log_path):
        if os.path.isfile(p):
            res.setdefault('artifacts', []).append(
                dict(path=p, bytes=os.path.getsize(p),
                     mtime=time.strftime('%Y-%m-%d %H:%M:%S',
                                         time.localtime(os.path.getmtime(p)))))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true',
                    help='不需要设备的反证自检（判据能否识破 v2.1 缺陷）')
    ap.add_argument('--run', action='store_true', help='真机跑三臂')
    ap.add_argument('--dry-run', action='store_true', help='只打印命令')
    ap.add_argument('--pkg', default=PKG_V22)
    ap.add_argument('--counterproof-pkg', default=PKG_V21)
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--arms', default='tts_off,tts_on_preset,tts_on_clone')
    ap.add_argument('--skip-quiet', action='store_true',
                    help='跳过安静窗口（⚠️ 会与用户自己的会话抢设备）')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': 'app223_app061_device_acceptance.py',
           'correction': 'APP-061',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args)}

    # ── 自检（不需要设备） ───────────────────────────────────────
    st = self_test()
    out['self_test'] = st
    print('===== 自检（反证：判据能否识破 v2.1 缺陷）=====')
    if st.get('checks'):
        for c in st['checks']:
            print('  [%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL',
                                     c['name'], c['detail']))
        print('结果：%d PASS / %d FAIL ⇒ %s'
              % (st['n_pass'], st['n_fail'], st['verdict']))
    else:
        print('  自检无法进行：%s' % st.get('why'))

    # ── 只打印命令（`--dry-run`）：**不跑设备、不写证据文件** ──────
    # 🔴🔴 §129 修掉的真缺陷：原实现先判 `if not args.run:` 就 return
    #   ⇒ `--dry-run` 单独用时**永远走不到**下面的 dry-run 分支
    #   ⇒ 文档里写的「③ 只打印命令不跑」**根本跑不出来**（实测：只跑了自检）。
    if args.dry_run and not args.run:
        for arm in [a.strip() for a in args.arms.split(',') if a.strip()]:
            print(' '.join(arm_cmd(args.pkg, arm.strip(), SPE, 'X.wav',
                                   'X.jsonl', 'X.txt', args.duration)))
        print('（--dry-run：只打印命令，**没有跑任何设备作业**，也没有写证据文件）')
        return 0

    if not args.run:
        out['verdict'] = 'SELFTEST_ONLY'
        # 🔴🔴 §129：**自检结果另存新文件**，**绝不覆盖**设备级证据
        #   （原实现 `--self-test` 会把 `app223_app061_device_acceptance_evidence.json`
        #    覆盖成 SELFTEST_ONLY ⇒ **真机跑出来的证据被自检冲掉**）。
        selftest_out = args.out.replace('.json', '.selftest.json')
        out['selftest_only'] = True
        with open(selftest_out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % selftest_out)
        print('（自检结果**另存**；设备级证据 %s **未被覆盖**）' % args.out)
        return 0 if st.get('verdict') == 'PASS' else 1

    # ── 真机跑 ───────────────────────────────────────────────────
    if not os.path.isfile(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2
    if args.dry_run:
        for arm in args.arms.split(','):
            print(' '.join(arm_cmd(args.pkg, arm.strip(), SPE, 'X.wav',
                                   'X.jsonl', 'X.txt', args.duration)))
        return 0

    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        out['verdict'] = 'LOCK_BUSY'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        if not args.skip_quiet:
            ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=900.0, verbose=True)
            out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
            print('[lock] 安静窗口 ok=%s' % ok_q)
            if not ok_q:
                print('[lock] !! 没有安静窗口 ⇒ 不开跑（用户可能在测）')
                out['verdict'] = 'NO_QUIET_WINDOW'
                with open(args.out, 'w', encoding='utf-8') as f:
                    json.dump(out, f, ensure_ascii=False, indent=1)
                return 4
        arms = {}
        for arm in [a.strip() for a in args.arms.split(',') if a.strip()]:
            print('\n===== 臂 %s 开始（%s）=====' % (arm,
                                                  time.strftime('%H:%M:%S')))
            arms[arm] = run_arm(args.pkg, arm, SPE, args.duration)
            print('  rc=%s wall=%s s  rtf=%s  rows=%s'
                  % (arms[arm]['rc'], arms[arm]['runner_wall_s'],
                     arms[arm]['summary'].get('rtf'),
                     arms[arm]['jsonl'].get('n_rows')))
        out['arms'] = arms
        # 反证臂：同一套判据跑在 v2.1 上 ⇒ **必须 FAIL**
        # 🔴🔴 §129 修掉的真缺陷：原实现只把反证臂**存进 out**，
        #   **从不判它** ⇒ 「v2.1 必须 FAIL」这句话**没有任何强制力**
        #   ⇒ 万一 v2.1 也 PASS，闸门照样报 PASS ⇒ 判据失去鉴别力。
        if os.path.isdir(args.counterproof_pkg):
            cp = run_arm(args.counterproof_pkg, 'tts_on_clone', SPE,
                         min(args.duration, 120.0), tag='_v21')
            out['counterproof_v21'] = cp
            print('\n===== 反证臂（v2.1 同判据）=====')
            print('  rc=%s rows=%s fallback=%s clone_upd=%s'
                  % (cp['rc'], cp['jsonl'].get('n_rows'),
                     cp['log'].get('n_fallback_preset'),
                     cp['log'].get('n_clone_updates')))
            # 🔴 用**同一套判据**判 v2.1 ⇒ 至少要有 1 条 FAIL
            cp_checks = judge({'tts_on_clone': cp}, {'duration': args.duration})
            cp_fail = [c for c in cp_checks if c['verdict'] is False]
            cp_none = [c for c in cp_checks if c['verdict'] is None]
            out['counterproof_v21_checks'] = cp_checks
            out['counterproof_v21_n_fail'] = len(cp_fail)
            print('  v2.1 同判据：%d 条 FAIL / %d 条无法判定 / 共 %d 条'
                  % (len(cp_fail), len(cp_none), len(cp_checks)))
            for c in cp_fail:
                print('    [FAIL] %s' % c['name'])
        checks = judge(arms, {'duration': args.duration})
        out['checks'] = checks
        n_pass = sum(1 for c in checks if c['verdict'] is True)
        n_fail = sum(1 for c in checks if c['verdict'] is False)
        n_none = sum(1 for c in checks if c['verdict'] is None)
        out['n_pass'] = n_pass
        out['n_fail'] = n_fail
        out['n_none'] = n_none
        out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
        # 🔴🔴 **反证臂必须 FAIL**（§129）：v2.1 用同一套判据**一条都不 FAIL**
        #   ⇒ 说明这套判据**鉴别不出**新旧版本 ⇒ 本轮判定不可信
        #   ⇒ **整轮判 FAIL**（不是「无法判定」）。
        if 'counterproof_v21_n_fail' in out:
            out['counterproof_enforced'] = (
                out['counterproof_v21_n_fail'] > 0)
            if not out['counterproof_enforced']:
                print('\n[反证] !! v2.1 用同一套判据 **0 条 FAIL**'
                      ' ⇒ 判据鉴别不出新旧版本 ⇒ 本轮结果不可信 ⇒ 判 FAIL')
                out['verdict'] = 'FAIL'
                n_fail += 1
                out['n_fail'] = n_fail
        print('\n===== 验收判据 =====')
        for c in checks:
            print('  [%s] %s  %s'
                  % ({True: 'PASS', False: 'FAIL', None: 'NONE'}[c['verdict']],
                     c['name'], json.dumps(c['detail'], ensure_ascii=False)))
        print('结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
              % (n_pass, n_fail, n_none, out['verdict']))
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % args.out)
    return 0 if out.get('n_fail', 0) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
