#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app431_trim_memory.py —— 把 MEMORY.md 压回自述预算（≤ 9 500 字符）。

🔴 **做法**：按**行首前缀断言**定位 ⇒ 不会误伤别的行；逐行替换为**更短**的版本
   （脚本断言每行确实变短 ⇒ 不会假装修正）。
🔴 **纪律**：12 节标题与**全部 🔴 条目逐条保留**、**事实不删**（只压从句与重复表述）；
   §12 三轮的**逐字明细**在 `status/app/STATUS_APP.md` §171/§172/§173（该节抬头已声明
   「明细以 `status/app/STATUS_APP.md` 为准」）；压缩前逐字全文在 `MEMORY_MODULES.md` 二十一。
"""
import os
import re
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '.workbuddy', 'memory', 'MEMORY.md')

s = open(P, encoding='utf-8').read()
before = len(s)
lines = s.split('\n')
n_sec_before = s.count('\n## ')
n_bul_before = len(re.findall(r'(?m)^- ', s))

REPL = [
    # ── 十节 APP-076/077 ──
    ('- 🔴🔴 APP-076：',
     '- 🔴🔴 APP-076：`min_clean_ratio` 0.8→0.6 同步进 dev + 下一版包；🔴 克隆登记**不放宽**；'
     '环境变量 `LIVECAP_SPK_MIN_CLEAN_RATIO`，默认值来自 ASR `DEFAULT_MIN_CLEAN_RATIO`（不互相 import）。'
     'APP-077：EXT 的 `bridge_token.txt` 是**固定值** ⇒ 以后的包**不带**，改首次启动在用户目录随机生成；'
     '旧包不原地改；桥接快捷方式用 pythonw 无日志 ⇒ 新包须弹框。'),

    # ── 十节 交付纪律 ──
    ('- 🔴 交付版 v2.1；候选 v2.2',
     '- 🔴 交付版 v2.1；候选 v2.2（待用户抽听＋reviewer 复核）。今后只打 v2.3+ 新版本号（新目录＋新 zip＋'
     '新 MANIFEST＋重签 ACCEPTED），永不 `--same-version`、永不原地改旧版；.lnk 版本号由目标包目录名派生。'
     '口径 A 已作废 ⇒ 唯一口径 = 口径 B 7/12 = 58.33 % ⇒ 不得为凑 60 % 调阈值。APP-066 MiniMVP 独立版本线 ⇒ '
     '不覆盖/删旧目录与 zip。'),

    # ── 二节 租约行 ──
    ('- 🔴 巡检开工先拿租约',
     '- 🔴 巡检开工先拿租约（`session_lease.py acquire <模块>`）⇒ BUSY(10) 立即结束本轮、一字不改、不碰 '
     'MACHINE_LOCK；TOKEN ⇒ 每步＋耗时前后 beat（>30 min 视为死会话）；LOST(11) ⇒ 立即停止、不再写文件；'
     '收尾 `release`。租约管同模块单会话，锁管跨模块不共占设备。'),

    # ── 十节 D1 行 ──
    ('- 🔴 D1 = 5 s 唯一事实来源',
     '- 🔴 D1 = 5 s 唯一事实来源 `asr_spk_window.WIN_S`（5.0）⇒ App 同源跟随（不写第二份默认值）；🔴 但'
     '「唯一事实来源」被改 ≠ 下游都读它 ⇒ 跨模块常量须核对所有下游。改 dev 树 ⇒ 必须复跑既有回归套件 ⇒ '
     '输出另存。'),

    # ── 一节 仓库⇄客户包 ──
    ('- 🔴 仓库 ⇄ 客户包 = 两份独立副本',
     '- 🔴 仓库 ⇄ 客户包 = 两份独立副本 ⇒ 只用「difflib 替换块＋唯一命中断言＋`ast.parse`＋逐字节复核」；'
     '禁整目录覆盖／手写待插源码；验收脚本不 `import` 被测模块 ⇒ `ast`＋`exec`。'),

    # ── 一节 heredoc 行 ──
    ('- 🔴 含 `\\` 正文不用 bash heredoc',
     '- 🔴 含 `\\` 正文不用 bash heredoc ⇒ Write＋`python -c` 替换；CRLF 副本多行匹配串须带 `\\r\\n`；'
     'docstring 改 raw 后用 `ast` 常量比对证值未变。'),

    # ── 九节 自检伪不变量 ──
    ('- 🔴 写 STATUS 的自检别写',
     '- 🔴 写 STATUS 的自检别写「CRLF 个数不变」这类**伪不变量**（新注释行数不同 ⇒ 个数本就会变 ⇒ '
     '把正确改动判成 FAIL）⇒ 用真不变量「**无裸 LF**」；写前自检 FAIL ⇒ 源文件零改动。'),

    # ── 二节 存活判据 ──
    ('- 🔴 **存活判据的坑**',
     '- 🔴 **存活判据的坑**：`OpenProcess` 成功 ⇒ 再看 `GetExitCodeProcess` ⇒ **259 = STILL_ACTIVE ⇒ 活**'
     '（**只有 0 才是死**）⇒ 把 259 当死会误抢活锁（实测过一次）。'),

    # ── 二节 后台长作业 ──
    ('- 🔴 后台长作业只用 `run_in_background: true`',
     '- 🔴 后台长作业只用 `run_in_background: true`（`nohup …&` 随 shell 退出被杀 ⇒ 留孤儿锁）⇒ 立刻 '
     '`addpid`；被杀后先以 err==87 确证死再回收；等锁先探测。'),
]

hits = 0
total_saved = 0
for prefix, new_line in REPL:
    idx = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(idx) != 1:
        print('SKIP (hits=%d): %s' % (len(idx), prefix[:40]))
        continue
    old = len(lines[idx[0]])
    if len(new_line) >= old:
        print('NO-SHORTEN (old=%d new=%d): %s' % (old, len(new_line), prefix[:30]))
        continue
    lines[idx[0]] = new_line
    hits += 1
    total_saved += old - len(new_line)
    print('  L%-3d %4d -> %4d (-%d)  %s' % (idx[0] + 1, old, len(new_line),
                                           old - len(new_line), prefix[:26]))

s = '\n'.join(lines)
open(P, 'w', encoding='utf-8', newline='\n').write(s)

after = len(s)
print('MEMORY.md chars: %d -> %d (target 9500) ; lines=%d ; saved=%d'
      % (before, after, hits, total_saved))
print('sections: %d -> %d ; bullets: %d -> %d'
      % (n_sec_before, s.count('\n## '), n_bul_before, len(re.findall(r'(?m)^- ', s))))
print('within budget:', after <= 9500)
sys.exit(0 if after <= 9500 else 1)
