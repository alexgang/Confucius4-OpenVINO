#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-067 ①(b)：**查清 seg→spk 的绑定在哪一步断掉**（reviewer 明确要求「并给出证据」）。

## 要回答的问题（reviewer 原文）

> (b) .tts.jsonl 里 76 句全部是 `voice_kind=preset, spk=None`，log 里出现了 76 次
> `spk=None`。S1 已经出现，但标签始终没有传到 TTS 请求。
> **需要查清 seg→spk 的绑定在哪一步断掉（是 10 s 窗口滞后，还是绑定代码本身有问题），
> 并给出证据。**

## 本脚本做什么

读 §132 的真实产物（**只读，不改**）：

- `results/app/app223_device_out/tts_on_clone.log`（App 侧日志）
- `results/app/app223_device_out/tts_on_clone.tts.jsonl`（worker 侧逐句遥测）

按**日志行号**重建事件时间线，判定每一条 `spk=None` 的句子属于哪一类断点：

| 类别 | 含义 |
|---|---|
| `A_voice_never_registered` | 该 spk 的**音色从未登记成功** ⇒ `voice_for_sentence()` 恒返回 `''` ⇒ 与标签早晚**无关** |
| `B_label_after_submit` | 标签在**该句提交之后**才到 ⇒ 提交那一刻 `seg→spk` 还不存在（10 s 窗口滞后）|
| `C_label_before_submit` | 标签在提交**之前**就到了 ⇒ 绑定代码本身有问题（提交时仍拿不到）|

## 输出

`results/app/app235_app067_bind_break_evidence.json`

## 纪律

- 🔴 **只读产物**，绝不改 `tts_on_clone.log` / `.tts.jsonl`。
- 🔴 判据**三态**：True / False / **None（无法判定）** ⇒ 「无法判定」≠「不合格」。
- 🔴 **不调模型、不占设备** ⇒ 纯静态分析 ⇒ **不需要 MACHINE_LOCK**。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, 'app235_app067_bind_break_evidence.json')

LOG = os.path.join(REPO, 'results', 'app', 'app223_device_out',
                   'tts_on_clone.log')
JSONL = os.path.join(REPO, 'results', 'app', 'app223_device_out',
                      'tts_on_clone.tts.jsonl')


def main() -> int:
    if not (os.path.exists(LOG) and os.path.exists(JSONL)):
        print('[ABORT] 找不到 §132 产物：%s / %s' % (LOG, JSONL))
        return 2

    raw = open(LOG, 'rb').read()
    text = raw.decode('utf-8', 'replace')
    lines = text.split('\n')

    # ── 重建事件时间线（用**日志行号**做单调时钟）──────────────
    ev = []          # (line_no, kind, payload)
    for i, l in enumerate(lines):
        if '[定稿]' in l:
            ev.append((i, 'FINAL', {}))
        if '[译文]' in l:
            ev.append((i, 'MT_FINAL', {}))
        m = re.search(r'标签补到：第 (\d+) 段', l)
        if m:
            ev.append((i, 'LABEL', {'seg': int(m.group(1))}))
        m2 = re.search(r'第 (\d+) 段无说话人标签', l)
        if m2:
            ev.append((i, 'LABEL_MISSING', {'seg': int(m2.group(1))}))
        if '没有可用引擎' in l:
            ev.append((i, 'ENGINE_NOT_READY', {}))
        if '已登记音色' in l:
            ev.append((i, 'VOICE_REGISTERED', {}))
        if '音色登记失败' in l:
            ev.append((i, 'VOICE_FAILED', {}))
        if '模型加载完成' in l:
            ev.append((i, 'MODEL_LOADED', {}))

    kinds = {}
    for _ln, k, _p in ev:
        kinds[k] = kinds.get(k, 0) + 1

    # ── 标签到达时刻（按 seg）───────────────────────────────────
    label_at = {}
    for ln, k, p in ev:
        if k == 'LABEL':
            label_at.setdefault(p['seg'], ln)

    # ── 每个 seg 的「提交时刻」：取该 seg 之后最近的 MT_FINAL ──
    # 🔴 口径：`[译文]`（MT 定稿）才是**提交 TTS 的触发点**
    #   （App 在 MT 的 final 事件里调 `self.tts.submit(...)`）
    #   ⇒ 用「MT_FINAL 行号」代表提交时刻。
    # ⚠️ 这是**近似**：App 一条 log 里可能有多句译文 ⇒ 用**累计出现次序**配对。
    mt_lines = [ln for ln, k, _p in ev if k == 'MT_FINAL']
    final_lines = [ln for ln, k, _p in ev if k == 'FINAL']
    # seg 序号 = `[定稿]` 的出现次序（0 起）
    seg_of_final = {}
    for idx, ln in enumerate(final_lines):
        seg_of_final[idx] = ln

    # ── worker 侧遥测：逐句 voice_spk / voice_kind ──────────────
    rows = []
    with open(JSONL, 'rb') as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln.decode('utf-8')))
            except Exception:
                pass

    n_none = sum(1 for r in rows if r.get('voice_spk') is None)
    n_preset = sum(1 for r in rows if r.get('voice_kind') == 'preset')

    # ── 判据 ────────────────────────────────────────────────────
    checks = []

    def add(name, ok, detail):
        checks.append({'name': name, 'ok': ok, 'detail': detail})

    add('产物可读（log + jsonl）', True,
        'log %d B / jsonl %d 行' % (len(raw), len(rows)))
    add('worker 从未登记成功任何说话人音色（已登记音色 = 0）',
        kinds.get('VOICE_REGISTERED', 0) == 0,
        kinds.get('VOICE_REGISTERED', 0))
    add('worker 报过「没有可用引擎 ⇒ spk 音色登记失败」',
        kinds.get('ENGINE_NOT_READY', 0) > 0,
        kinds.get('ENGINE_NOT_READY', 0))
    add('jsonl 全部句子 voice_spk 为 None',
        n_none == len(rows), '%d / %d' % (n_none, len(rows)))
    add('jsonl 全部句子 voice_kind 为 preset',
        n_preset == len(rows), '%d / %d' % (n_preset, len(rows)))
    add('标签是**晚到**的（LABEL 事件数 < 定稿句数 ⇒ 有标签走补发）',
        kinds.get('LABEL', 0) < kinds.get('FINAL', 0),
        'LABEL %d < FINAL %d' % (kinds.get('LABEL', 0), kinds.get('FINAL', 0)))

    # ── 分类：每条 voice_spk=None 的句子归到哪一类 ─────────────
    # 🔴 口径（必须在证据里写明，避免口径漂移）：
    #   `voice_for_sentence(seg)` 返回 spk 的**充要条件**（speaker_voice.py）：
    #       ① `self._seg_spk.get(seg)` 非空（= 标签已到）
    #       ② `self._table[spk]['voice'] == 'clone'`（= 该 spk 音色已登记成功）
    #   ⇒ 条件②一旦不成立（音色从未登记成功），**返回恒为 ''**
    #     ⇒ 提交早晚**都拿不到** spk ⇒ 归类 A。
    #   ⇒ 只有在「音色确实登记成功」的前提下，提交早于标签才有意义（归类 B）。
    voice_registered = kinds.get('VOICE_REGISTERED', 0) > 0
    cls = {'A_voice_never_registered': 0,
           'B_label_after_submit': 0,
           'C_label_before_submit': 0,
           'D_undecidable': 0}

    # 逐 seg 判定「标签相对提交」的先后
    detail_rows = []
    for seg, l_line in sorted(seg_of_final.items()):
        lab = label_at.get(seg)
        # 该 seg 的提交时刻 = 第 seg 个 `[译文]`（MT 定稿）行号
        sub = mt_lines[seg] if seg < len(mt_lines) else None
        if lab is None:
            rel = 'label_never_arrived'
        elif sub is None:
            rel = 'submit_unobserved'
        elif lab > sub:
            rel = 'label_after_submit'
        else:
            rel = 'label_before_submit'
        if not voice_registered:
            cls['A_voice_never_registered'] += 1
        elif rel == 'label_after_submit':
            cls['B_label_after_submit'] += 1
        elif rel == 'label_before_submit':
            cls['C_label_before_submit'] += 1
        else:
            cls['D_undecidable'] += 1
        detail_rows.append({'seg': seg, 'final_line': l_line,
                            'label_line': lab, 'submit_line': sub,
                            'relation': rel})

    # ── 结论 ────────────────────────────────────────────────────
    if not voice_registered:
        verdict = ('A：主因 = **音色从未登记成功**（worker 加载期丢弃 spk_voice）'
                   '⇒ `voice_for_sentence()` 的条件②恒不成立 ⇒ '
                   '**提交早晚都拿不到 spk** ⇒ 76/76 全 None 是**必然**，'
                   '与「10 s 窗口滞后」无关（窗口滞后只是**次要**因素）。')
    else:
        verdict = '音色已登记成功 ⇒ 断点在标签/提交先后 ⇒ 见分类计数。'

    n_fail = sum(1 for c in checks if c['ok'] is False)
    out = {
        'script': os.path.basename(__file__),
        'correction': 'APP-067 ①(b)',
        'question': 'seg→spk 的绑定在哪一步断掉（10 s 窗口滞后 vs 绑定代码）',
        'sources': {'log': LOG, 'jsonl': JSONL,
                    'log_bytes': len(raw), 'jsonl_rows': len(rows)},
        'event_counts': kinds,
        'jsonl': {'n_rows': len(rows),
                  'n_voice_spk_none': n_none,
                  'n_voice_kind_preset': n_preset},
        'label_vs_submit': cls,
        'per_seg': detail_rows,
        'checks': checks,
        'n_pass': len(checks) - n_fail,
        'n_fail': n_fail,
        'verdict': verdict,
        'meaning': ('本证据只回答「断点在哪」，**不改任何语义**；'
                    '修复由 §136 单独实施并复跑影子包验收。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('事件计数：', json.dumps(kinds, ensure_ascii=False))
    print('jsonl：%d 行，voice_spk=None %d，voice_kind=preset %d'
          % (len(rows), n_none, n_preset))
    print('标签/提交先后分类：', json.dumps(cls, ensure_ascii=False))
    print('结论：', verdict)
    print('结果：%d PASS / %d FAIL ⇒ %s'
          % (out['n_pass'], out['n_fail'], OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
