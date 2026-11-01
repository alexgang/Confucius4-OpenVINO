#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app204_app053_gui_shot.py —— 【APP-053 ③】GUI 侧「说话人标签」的**证据归集**。

## 采集方式（**不改产品代码**）

- 在**影子包**（`shared/app053054_shadow`，硬链接零拷贝）上起 GUI：
  `--source file --file <SPE 5 min 切片> --speaker on --engine gpu_int8 --asr-device GPU.0`
- 用 `root.after(...)` 调**真实的 `App.start()`**（不模拟点击）；
  🔴 **`start()` 在 `self.engine` 未就绪时静默 return** ⇒ 判据脚本必须**轮询重试**。
- 截图：按**本轮启动进程 PID** 过滤窗口，并取**面积最大**的那个（= 主 GUI）
  ⇒ 不会拍到**上一轮残留**的同名窗口（本轮实测踩到过）。

## 判据

| # | 内容 |
|---|---|
| C1 | 主 GUI 窗口存在且可截图（**本轮 PID** 归属） |
| C2 | ASR 状态行显示 **当前说话人**（`当前 S1`） |
| C3 | 日志出现 **`[spk] 标签补到：第 N 段 = Sx`**（晚到标签**回填**） |
| C4 | 语音输出区显示 **`说话人: Sx`**（音色**按句绑定**） |
| C5 | GUI 有 **「说话人识别」勾选框**且已勾选（APP-054① 的 GUI 开关） |
| C6 | 🔴 **转写区的正式行是否带 `[Sx]` 前缀** —— 实测**未取到**（见 `notes`）⇒ **记为未达成**，不粉饰 |

## 用法

    python results/app/app204_app053_gui_shot.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'app204_app053_gui_shot_evidence.json')
SHOT_DIR = os.path.join(os.path.expanduser('~'), 'shared', 'app_gui_spk')
LOG_DIR = os.path.join(os.path.expanduser('~'), 'AppData', 'Local',
                       'Confucius4LiveCaption')


def main():
    shot = os.path.join(SHOT_DIR, 'app204_gui_main.png')
    checks = []

    def chk(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))

    # ── C1 截图存在 ──
    ok_shot = os.path.isfile(shot)
    chk('C1 主 GUI 截图存在（本轮 PID 归属 ＋ 取面积最大的窗口）', ok_shot,
        dict(shot=shot, bytes=(os.path.getsize(shot) if ok_shot else None),
             mtime=(time.strftime('%Y-%m-%d %H:%M:%S',
                                  time.localtime(os.path.getmtime(shot)))
                    if ok_shot else None)))

    # ── 会话日志（App 自己落的证据链）──
    logs = []
    if os.path.isdir(LOG_DIR):
        for fn in os.listdir(LOG_DIR):
            if fn.startswith('session_') and fn.endswith('.log'):
                p = os.path.join(LOG_DIR, fn)
                logs.append((os.path.getmtime(p), p))
    logs.sort(reverse=True)
    body = ''
    log_path = logs[0][1] if logs else ''
    if log_path:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            body = f.read()

    spk_back = re.findall(r'\[spk\]\s*标签补到：第\s*(\d+)\s*段\s*=\s*(\S+)', body)
    spk_cur = re.findall(r'\[spk\]\s*当前说话人[:：]?\s*(\S+)', body)
    chk('C3 日志出现「[spk] 标签补到：第 N 段 = Sx」（晚到标签**回填**）',
        bool(spk_back), dict(n=len(spk_back), sample=spk_back[:6],
                             log=os.path.basename(log_path or '')))

    # ── C2 / C4 / C5 / C6：截图里没有 OCR ⇒ 用**可复核的文本证据**替代 ──
    #   ① 影子包 GUI 运行时的 `_spk_by_seg` 快照（由 runner 落盘）
    snap = os.path.join(SHOT_DIR, 'app204_gui_spk_snapshot.json')
    sp = {}
    if os.path.isfile(snap):
        with open(snap, 'r', encoding='utf-8') as f:
            sp = json.load(f)
    segs = sp.get('spk_by_seg') or {}
    chk('C2 ASR 状态行显示「当前 S1」（GUI 运行时的 `_spk_by_seg` 非空）',
        bool(segs), dict(n_segs_labeled=len(segs),
                         sample=dict(list(segs.items())[:6])))
    chk('C4 语音输出区显示「说话人: Sx」（音色**按句绑定**到该说话人）',
        bool(segs) and sp.get('tts_speaker') is not None,
        dict(tts_speaker=sp.get('tts_speaker')))
    chk('C5 GUI 有「说话人识别」勾选框且已勾选（APP-054① 的 GUI 开关）',
        sp.get('var_speaker') is True,
        dict(var_speaker=sp.get('var_speaker'),
             asr_status=sp.get('asr_status')))
    chk('C6 转写区正式行带 `[Sx]` 前缀', bool(sp.get('transcript_has_spk_label')),
        dict(render_lines=sp.get('render_lines'),
             blocks=sp.get('blocks'),
             note=sp.get('note')))

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = dict(script='app204_app053_gui_shot.py', correction='APP-053',
               purpose='GUI 侧说话人标签证据（影子包 ＋ 真实 start() ＋ 截图）',
               shot=shot, log=log_path,
               snapshot=snap if os.path.isfile(snap) else None,
               spk_backfilled_samples=spk_back[:12],
               checks=checks, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'PARTIAL',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for c in checks:
        print('  [%s] %s  %s'
              % ('PASS' if c['ok'] else 'FAIL', c['name'],
                 json.dumps(c['detail'], ensure_ascii=False)[:260]))
    print('结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, out['verdict']))
    print('[evidence] %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
