#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§64 —— 更新 STATUS_APP.md 的头部字段 + 追加 §64 章节。

🔴🔴 纪律（`MEMORY.md` + §62 教训）：
  - **头部切片用「首个章节锚点」**（`## §1 ` 的下标）⇒ `lines[i_s1:]` 原样保留
    ⇒ **不要**用「最后一个 §N」（否则 §1~§N 全丢）。
  - 新章节**追加在文件末尾**（`out = head + body + [''] + new_body`）
    ⇒ **不能**插到 §1 前面。
  - `set_field` 拼接时 value **不得**含 key 前缀（否则写两遍）。
  - 「最近更新」≤ 15 行是硬约束 ⇒ 拼接后先断言再写盘。
  - STATUS 是 **LF** 换行 ⇒ 用 `newline=''` 读写。
  - 写盘前必须 `cp` 备份。
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'status', 'app', 'STATUS_APP.md')
NEW_SECTION = os.path.join(HERE, '_app064_status_section.md')
BACKUP = os.path.join(HERE, '_app064_status_backup.md')

NOW = '2026-10-27 10:48'   # 🔴 Get-Date 实测值，禁止推算
LAST_ACK = 'APP-023'          # 🔴 APP-024 只做了 ①，②③④ 未做 ⇒ 不进 last_ack

RECENT = [
    '10:48 §64 🔴 **巡检：本轮 3 条新条目**（APP-023 / APP-024 / APP-025）⇒ `CORRECTIONS_APP.md` SHA `32991dc9bd3a4f35…` / 59 279 B / mtime 09:06:18 ⇒ 最大 **APP-025**；该文件**只读零修改**',
    '10:48 §64 ✅ **独立核实**并发会话的 APP-023①③④ / APP-025（**不采信 §63 自述**）⇒ 边车 std 句柄 / worker 解释器 / 旧引擎回落删除 / 测试音不依赖 worker / 报错人话 / 按钮置灰 —— **全部真实落盘**',
    '10:48 §64 🔴🔴 **真实缺陷 —— 打包自检被「自己的新验收脚本」拦下**：`app093`/`app096` 写死包路径 ⇒ §48 闸门 FAIL ⇒ 改用 `pkg_paths` 单一数据源 ⇒ `app093` 19/19 + `app096` 13/13 + `--dry-run` **PASS**',
    '10:48 §64 ✅ **APP-024① 首包拆两段**：`queued_s`（主进程 `t_sent − t_submit`）+ `synth_s`（worker `t_first − t_dequeue`）⇒ 🔴 **跨进程 `perf_counter()` 不可比** ⇒ 各自算、不可相减；验收 `app097` REAL **20/20** + BUG **3/3**（基线固定 `0d1be9d`）',
    '10:48 §64 ✅ **交付代差闭环**（§61 四步）：复核报 zip 缺 **5 个修复** ⇒ 持锁 `app-pack` 重打 **14 min 7 s** ⇒ `verify_pkg_zip.py` **PASS**（13986 逐字节 + 22/22）⇒ FTP 重发 ⇒ **三方 SHA256 一致** `c7f60bca…` / **11 216 287 107 B**',
    '10:48 §64 ✅ **APP-018② 第三方素材在 zip 内真清零**：babelvox speakers **0** + scipy 测试 wav **0** + 音色只剩 `preset_A.wav` **1** 个（散包目录仍有 8+22 ⇒ 靠 `pkg_exclude` 规则覆盖）；🔴 FTP 服务仍关闭',
    '10:48 §64 ✅ **回归全绿**：`app092` 24/24 + `app093` 19/19 + `app096` 13/13 + `app097` 20/20 + TTS 记账 5 套件 + `test_tts_*` **19 个 PASS**；⚠️ `test_tts_cmp_orig.py` 失败=**环境缺失非回归**（`_orig_mod/` **从未入 git**）',
    '10:48 §64 ⛔ **停在 §63 的 L4（等用户）**：请双击桌面「Confucius4 实时字幕」⇒ ① 测试声音 ② CUDA 朗读 ③ NPU 朗读 ⇒ **用户亲口确认前不得写「能出声」**；🔴 APP-024②③④ 未做',
]

TASK = ('**§64 🔴 巡检（APP-023 / APP-024 / APP-025 = 3 条新条目）** + ✅ **APP-024① 首包拆两段**'
        '（`queued_s` 主进程口径 + `synth_s` worker 口径；🔴 跨进程 `perf_counter()` 不可比）'
        ' + ✅ **修掉「打包自检被自己的新验收脚本拦下」**（§48 闸门写死包路径 ⇒ 改用 `pkg_paths`）'
        ' + ✅ **交付代差闭环**（zip 缺 5 个修复 ⇒ 持锁重打 14 min 7 s ⇒ 独立复核 PASS ⇒ FTP 重发 ⇒ 三方 SHA256 一致 `c7f60bca…`）'
        ' + ✅ **APP-018② 第三方素材在 zip 内真清零**'
        ' ⇒ ⛔ **停在 §63 的 L4 等用户实测**（桌面快捷方式 ⇒ 测试声音 → CUDA → NPU）'
        ' ⇒ 🔴 **APP-024②③④ 未做**（§63 明文「APP-023 验收通过后再做」）⇒ **`last_ack` 保持 APP-023**')

BLOCK = ('① 🔴 **§63 的 L4 等用户实测**（需人）：桌面快捷方式 →「🔊 测试声音」→ CUDA 朗读一句 → NPU 朗读一句 ⇒ '
         '反馈听到/听不到 + `%LOCALAPPDATA%\\Confucius4LiveCaption\\session_*.log` 路径 ⇒ **用户亲口确认前不得写「能出声」**；'
         '② 🔴 **APP-022 集成需等 ASR-013 + TTS-019 交付**（§55 只做接口预留，**未集成**）；'
         '③ 🔴 **APP-024②③④ 未做**（加载期句子单独列 / 按 BRIEF 素材持锁重跑 ABBA / 「加载期攒句是否按 8 s 丢」——'
         'reviewer 明文「**不要自己改**，写进待用户决定」）⇒ **`last_ack` 保持 APP-023**；'
         '④ ✅ **§64 已闭环**：交付 zip **11 216 287 107 B** / SHA256 `c7f60bca…` / 13986 条目 / mtime 10:28 ⇒ '
         '`verify_pkg_zip.py` 独立复核 **PASS**（[1] 13986 逐字节 + [2] HEAD⇄包 **22/22**）⇒ FTP 副本 SHA256 一致 ⇒ **三方闭环**；'
         '⑤ ✅ **APP-018② 已真闭环**（zip 内 babelvox speakers **0** + scipy 测试 wav **0** + 音色只剩 `preset_A.wav`）'
         '⇒ 🔴 **散包目录**仍有 8+22（是打包源，靠 `pkg_exclude` 规则覆盖）；'
         '⑥ 🔴 **术语表 / `packaging` 默认值待用户决定**（MT 通知 14 建议已被用户 09:01 **作废** ⇒ App 不改术语表）；'
         '⑦ 🔴 **§50.5 需 TTS 模块配合**（App 不代跑尺子）；'
         '⑧ 🔴 **§45.6①–⑤ / §44 `MAX_SEG_SPAN=2` / §46.5 / §42.3 / MT 通知 13 回复** ⇒ 等 reviewer 裁定；'
         '⑨ ⛔ **FTP 服务仍关闭**（守 APP-009③）；'
         '⑩ ⛔ OV 的 CUDA plugin 不引入（§39.5）；'
         '⑪ ⛔ 包体优化未做（用户已接受）；'
         '⑫ ⛔ V7 残句代价待确认；'
         '⑬ 🔴 **§56.9**：TTS-019 `single` 臂 / TTS-017① `A_CPU` 臂是否重跑由 TTS 自行决定；'
         '⑭ 🔴 **§56.2**：ASR/TTS 侧锁写法的**独占性**待其自评；'
         '⑮ 🔴 **§57**：历史遗留未跟踪文件（`sync_c148b_to_pkg.py` / `sync_c150_to_pkg.py` / `app073*` / `app074*` 等）**归属未判定** ⇒ 本轮**未提交**；'
         '⑯ 🔴 **§64.6**：`test_tts_cmp_orig.py` 因 `_orig_mod/` **从未入 git** 而无法运行 ⇒ **环境缺失非回归**（基线须用固定 commit SHA）')


def set_field(lines, key, value):
    """替换 `key: value` 行。value **不得**含 key 前缀。"""
    prefix = key + ': '
    assert not str(value).startswith(prefix), \
        'value 已含 key 前缀 ⇒ 会写两遍: %r' % value
    hit = 0
    for i, ln in enumerate(lines):
        if ln.startswith(prefix):
            lines[i] = prefix + value
            hit += 1
    assert hit == 1, '字段 %r 命中 %d 次（应为 1）' % (key, hit)
    return lines


def main():
    shutil.copy2(STATUS, BACKUP)
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    lines = text.split('\n')

    # ── 找首个章节锚点 ────────────────────────────────────────────────
    i_s1 = None
    for i, ln in enumerate(lines):
        if ln.startswith('## §1 '):
            i_s1 = i
            break
    assert i_s1 is not None, '找不到 "## §1 " 锚点'
    head = lines[:i_s1]
    body = lines[i_s1:]
    print('头部行数 =', len(head), ' 正文行数 =', len(body))

    # ── 头部字段 ──────────────────────────────────────────────────────
    set_field(head, 'last_ack', LAST_ACK)
    set_field(head, '更新时间', NOW)
    set_field(head, '当前任务', TASK)
    set_field(head, '阻塞 / 待用户决定', BLOCK)

    # ── 「最近更新」区块 ──────────────────────────────────────────────
    i_rec = None
    for i, ln in enumerate(head):
        if ln.strip() == '## 最近更新':
            i_rec = i
            break
    assert i_rec is not None, '找不到「## 最近更新」'
    # 🔴🔴 不能用 `re.search(r'## 最近更新\n(.*?)$', ..., re.S|re.M)`：
    #    `$` 在 MULTILINE 下匹配**行尾** ⇒ `.*?` 最短只吃 1 行 ⇒ 旧的 29 行全丢。
    #    正解 = **按行切片**：从 `## 最近更新` 的下一行起，直到第一个 `## §` 标题行之前。
    end_rec = i_rec + 1
    while end_rec < len(head) and not head[end_rec].startswith('## §'):
        end_rec += 1
    old_rec = [x for x in head[i_rec + 1:end_rec] if x.strip()]
    assert len(old_rec) >= 5, '「最近更新」只抓到 %d 行 ⇒ 切片有误' % len(old_rec)
    merged = RECENT + old_rec
    # 🔴 硬约束 ≤ 15 行 ⇒ 裁掉**最旧的**
    merged = merged[:15]
    assert len(merged) <= 15, '最近更新 %d 行 > 15' % len(merged)
    print('最近更新：旧 %d 行 + 新 %d 行 ⇒ 保留 %d 行' %
          (len(old_rec), len(RECENT), len(merged)))

    keep = head[end_rec:]
    new_head = head[:i_rec + 1] + merged + [''] + keep

    # ── 新章节 ────────────────────────────────────────────────────────
    with io.open(NEW_SECTION, 'r', encoding='utf-8', newline='') as f:
        new_sec = f.read()
    new_sec = new_sec.replace('\r\n', '\n').rstrip('\n')

    out = new_head + body + [''] + new_sec.split('\n') + ['']
    out_text = '\n'.join(out)

    # ── 写盘前断言 ────────────────────────────────────────────────────
    # 🔴🔴 只数**章节标题行**（`^## §\d+`）⇒ 正文里引用 `## §61` 等不算章节
    #    （上一版用子串 `count('## §')` ⇒ 正文引用多出 10 个 ⇒ 误判）
    n_old = len(re.findall(r'^## §\d+', text, re.M))
    n_new = len(re.findall(r'^## §\d+', out_text, re.M))
    assert n_new == n_old + 1, \
        '章节数不对: %d → %d' % (n_old, n_new)
    print('章节数（标题行）: %d → %d' % (n_old, n_new))
    for old_sec in ('## §62 ', '## §63 ', '## §61 '):
        assert old_sec in out_text, '旧章节 %s 丢失' % old_sec
    assert 'last_ack: APP-023' in out_text
    # 🔴 只数**头部字段行**（行首精确匹配）⇒ 正文里引用字段名不算
    for key in ('last_ack: ', '更新时间: ', '当前任务: ', '阻塞 / 待用户决定: '):
        n = sum(1 for ln in out_text.split('\n') if ln.startswith(key))
        assert n == 1, '%s 出现 %d 次（应为 1）' % (key, n)
    # 🔴 最近更新 ≤ 15 行（写盘后再核一次）
    assert sum(1 for ln in new_head if ln.startswith('- ')) <= 15

    with io.open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(out_text)
    print('已写盘:', STATUS, os.path.getsize(STATUS), 'B')


if __name__ == '__main__':
    main()
