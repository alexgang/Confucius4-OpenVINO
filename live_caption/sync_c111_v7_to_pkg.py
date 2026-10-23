#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 C-111-V7（双通道）同步到**客户包**的 translator.py。

依据：STATUS_hy.md §46（C-111-V7 实施）+ §45（七臂评估，选定 V7）。

**V7 语义**（三处语义改动 + 一处初始化）：
  ① `fix`（跨段整句）译文写进**独立槽位 `done_fix`**，**不覆盖**显示槽位 `done`
     ⇒ 界面**无跨行重复**（实测 5 对 → 0）；
  ② `fix` 在 outbox 里**以 'final' 发出**
     ⇒ GUI（`_pump_tts` 只认 `kind=='final'`）与 CLI 都把**整句**提交给 TTS
     ⇒ **朗读完整 389 字**、只念一次、App 侧**零改动**；
  ③ `half` 行为不变（写 `done`、界面显示残句、以 'half' 发出不朗读）。

**纪律**（客户包 = 独立副本，**严禁整目录覆盖**）：
  - 精确字符串替换 + `assert count == 1`（每一处锚点必须唯一命中）；
  - 幂等：已经是目标状态 ⇒ 报 `ALREADY` 且不改文件；
  - 备份目录放**包外**（`_backup*` 会污染包）；
  - 自动发现客户包时**排除** `.bak` / `backup` / `_pre_` 目录；
  - 失败自动从备份还原。

用法：
  python sync_c111_v7_to_pkg.py [--pkg <包目录>] [--dry-run]
"""
import argparse
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = r'C:\Users\Trekker-PTL'
BACKUP_ROOT = os.path.join(PKG_ROOT, 'hy_bench', '_backup_c111_v7')
# 打包目标版本（APP-007：版本号单一数据源在 pack_v13.py 的 PKG_VERSION）
DEFAULT_PKG_VER = '1.4'


# ── 补丁 1：初始化 `done_fix` ──────────────────────────────────────────
P_INIT_OLD = """        self.done = OrderedDict()          # norm_key(sentence) -> 译文
"""
P_INIT_NEW = """        self.done = OrderedDict()          # norm_key(sentence) -> 译文
        self.done_fix = OrderedDict()      # ★ V7：fix（跨段整句）译文 —— 只朗读不显示
"""

# ── 补丁 2：换模型时清 `done_fix` ──────────────────────────────────────
P_CLEAR_OLD = """                    self.done.clear()
"""
P_CLEAR_NEW = """                    self.done.clear()
                    self.done_fix.clear()
"""

# ── 补丁 3：写入分支（核心）────────────────────────────────────────────
P_WRITE_OLD = """            if job.kind in ('final', 'half', 'fix'):
                # ★ C-111：'half'（段尾半句初翻）与 'fix'（补全后的修正）
                #   都写进同一个 key 槽位 —— 修正是**原地覆盖**，
                #   界面那一行译文直接被替换，不需要额外的对齐逻辑。
                #
                # ★ C-111-V3 已于 2026-10-23 16:xx 撤回：
                #   曾试过让 fix 只进 `done_fix`（只朗读不显示）以消除「相邻两行
                #   内容重叠」，但实测**界面显示字数丢失 26.8%**（560→410 字/12 段），
                #   链首段那行只剩残句（「那么，欢迎您」「谁」「那个」），
                #   用户反馈「翻译信息严重丢失」⇒ 恢复完整 C-111 的原地覆盖。
                svc.done[job.key] = r['text']
                while len(svc.done) > svc.CACHE_MAX:
                    svc.done.popitem(last=False)
"""
P_WRITE_NEW = """            if job.kind in ('final', 'half', 'fix'):
                # ★ C-111-V7（2026-10-23 21:xx，STATUS_hy §46）：**双通道**
                #
                #   'final' / 'half' → 写 `done`（**显示槽位**，界面 `mt_of_seg` 读它）
                #   'fix'            → 写 `done_fix`（**独立槽位**）
                #
                #   为什么 fix 不能进 `done`：
                #     fix 翻的是**跨段整句**（链首段半句 + 本段首句），
                #     它写进链首段的显示槽位 ⇒ 链首行含下一段首句内容，
                #     而下一段又单独翻了首句（head）⇒ **同一句话在相邻两行各出现一次**
                #     （实测 5 对跨行重复，最高 bigram 重叠 75%）。
                #
                #   为什么「不进 done」不等于「信息丢失」（§45.1 量化纠正）：
                #     改用**句级归属覆盖**看，V7 与完整 C-111 **完全相同（96%，24/25 句）**；
                #     完整 C-111 多出的 150 字里 **28.2% 的 bigram 是重复内容**。
                #     用户上一次看到的「翻译信息严重丢失」的真实来源是
                #     **行尾残句**（5 行 / 58 字），不是总字数。
                #
                #   ⇒ V7 的代价：链首段那行显示**半句残句**（不完整），
                #     完整句译文只在 `done_fix` 里，**供 TTS 朗读**。
                #     彻底解法（段级文案 + 整句文案并存、App 渲染层同一行二选一）
                #     属 App 渲染层，本轮未实施。
                if job.kind == 'fix':
                    svc.done_fix[job.key] = r['text']
                    while len(svc.done_fix) > svc.CACHE_MAX:
                        svc.done_fix.popitem(last=False)
                else:
                    svc.done[job.key] = r['text']
                    while len(svc.done) > svc.CACHE_MAX:
                        svc.done.popitem(last=False)
"""

# ── 补丁 4：outbox 里 fix 以 'final' 发出（GUI 也能朗读整句）──────────
P_OUT_OLD = """                # ★ outbox 的 kind 决定消费方怎么处理：
                #   'final' —— 完整句定稿译文 → 朗读
                #   'half'  —— 半句初翻译文   → **只显示，不朗读**
                #   'fix'   —— 补全后的修正译文 → 朗读（覆盖显示）
                svc.outbox.append((job.kind, job.key, r['text']))
"""
P_OUT_NEW = """                # ★ outbox 的 kind 决定消费方怎么处理：
                #   'final' —— 完整句定稿译文 → **朗读**（App GUI/CLI 都按 'final' 提交 TTS）
                #   'half'  —— 半句初翻译文   → **只显示，不朗读**
                #   'fix'   —— 补全后的整句译文 → **朗读**
                #
                #   ★ V7：fix 在 outbox 里**以 'final' 发出**。
                #     原因：GUI 侧 `_pump_tts()` 只提交 `kind == 'final'` 给 TTS
                #     （live_caption_app.py:2314），CLI 侧认 ('final','fix')。
                #     若 fix 仍以 'fix' 发出 ⇒ **GUI 不朗读整句**（只剩残句）。
                #     以 'final' 发出 ⇒ **App 侧零改动**，整句只朗读一次。
                #     （'half' 仍是 'half' ⇒ 残句不朗读，界面显示不受影响。）
                svc.outbox.append(('final' if job.kind == 'fix' else job.kind,
                                   job.key, r['text']))
"""

PATCHES = [
    ('① 初始化 done_fix', P_INIT_OLD, P_INIT_NEW),
    ('② 换模型清 done_fix', P_CLEAR_OLD, P_CLEAR_NEW),
    ('③ 写入分支（fix → done_fix）', P_WRITE_OLD, P_WRITE_NEW),
    ('④ outbox 里 fix 以 final 发出', P_OUT_OLD, P_OUT_NEW),
]

# 反向校验：V7 关键符号必须在位；旧 C-111 的「三者都写 done」形态必须消失
MUST_HAVE = [
    'self.done_fix = OrderedDict()',
    'self.done_fix.clear()',
    "svc.done_fix[job.key] = r['text']",
    "'final' if job.kind == 'fix' else job.kind",
]
MUST_GONE = [
    "svc.done[job.key] = r['text']\n                while len(svc.done) > svc.CACHE_MAX:",
]


def find_pkg(pkg_ver=None):
    """发现客户包目录 —— 排除 `.bak` / `backup` / `_pre_`。"""
    cands = []
    for name in sorted(os.listdir(PKG_ROOT)):
        if not name.startswith('Confucius4_LiveCaption'):
            continue
        low = name.lower()
        if '.bak' in low or 'backup' in low or '_pre_' in low:
            continue
        p = os.path.join(PKG_ROOT, name)
        if not os.path.isdir(p):
            continue
        if not os.path.isfile(os.path.join(p, 'app', 'translator.py')):
            continue
        if pkg_ver and not name.endswith('v' + pkg_ver):
            continue
        cands.append(p)
    if not cands:
        raise SystemExit('找不到客户包（pkg_ver=%s）' % pkg_ver)
    return cands[-1]


def apply_patch(text, name, old, new):
    c = text.count(old)
    if c != 1:
        raise RuntimeError('补丁 %s 的锚点命中 %d 次（期望 1）' % (name, c))
    return text.replace(old, new, 1)


def verify(text):
    miss = [s for s in MUST_HAVE if s not in text]
    if miss:
        raise RuntimeError('反向校验失败：缺少 %r' % miss)
    gone = [s for s in MUST_GONE if s in text]
    if gone:
        raise RuntimeError('反向校验失败：旧形态仍在 %r' % gone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现）')
    ap.add_argument('--pkg-ver', default=DEFAULT_PKG_VER)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    pkg = a.pkg or find_pkg(a.pkg_ver)
    tgt = os.path.join(pkg, 'app', 'translator.py')
    print('目标：%s' % tgt)
    if not os.path.isfile(tgt):
        raise SystemExit('目标不存在')

    with open(tgt, encoding='utf-8', newline='') as f:
        raw = f.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    text = raw.replace('\r\n', '\n')

    # 幂等判定：四块补丁的「新」都已在位 ⇒ 已是目标状态
    if all(new in text for _, _, new in PATCHES):
        print('ALREADY：客户包已是 C-111-V7 状态，未改动。')
        return 0

    todo = [(n, o, w) for n, o, w in PATCHES if o in text]
    skipped = [n for n, o, w in PATCHES if o not in text and w not in text]
    if skipped:
        raise SystemExit('以下补丁锚点未命中，无法安全替换：%s' % skipped)
    print('将应用 %d 处补丁：%s' % (len(todo), [n for n, _, _ in todo]))

    new = text
    for n, o, w in todo:
        new = apply_patch(new, n, o, w)
    verify(new)

    if a.dry_run:
        print('--dry-run：不写盘。')
        return 0

    # 备份（包外）
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    bk = os.path.join(BACKUP_ROOT,
                      'translator_pkg_%s_before_v7.py' % time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(tgt, bk)
    print('备份：%s' % bk)

    try:
        with open(tgt, 'w', encoding='utf-8', newline='') as f:
            f.write(new.replace('\n', nl))
    except Exception as e:
        shutil.copy2(bk, tgt)
        raise SystemExit('写盘失败，已从备份还原：%r' % e)

    # 回读校验
    with open(tgt, encoding='utf-8', newline='') as f:
        back = f.read()
    try:
        verify(back.replace('\r\n', '\n'))
    except Exception as e:
        shutil.copy2(bk, tgt)
        raise SystemExit('回读校验失败，已从备份还原：%r' % e)

    print('完成：%d 处补丁已应用并通过反向校验。' % len(todo))
    print('（包目录已改 ⇒ 需 App/打包模块重跑 pack_v13.py 生成新 zip）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
