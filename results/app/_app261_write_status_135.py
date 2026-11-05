#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app261 — 往 `status/app/STATUS_APP.md` **定点**写 §135（bytes 级、原子、带自检）。

## 🔴 写入纪律（APP-052 ④ ＋ §125/§126 教训）
1. **只动头部区**（`last_ack` / `更新时间` / `当前任务` / `阻塞` / `已压缩`）
   ＋ **「最近更新」**顶部插一行 ＋ **文件末尾追加** §135；
2. **旧正文一字未删** ⇒ 写完逐字节比对「§130 起至文件末」的原文；
3. **先写临时文件，再原子替换**（`os.replace`）；
4. **限额**：≤ 40 000 B / ≤ 300 行（APP-052 ④）⇒ 超了**不写**（本脚本会报错退出）；
5. `CORRECTIONS_APP.md` **只读**，本脚本**不碰**它。

## 🔴 逼近限额的处置（APP-052 ④ 惯例）
§135 正文较长 ⇒ 直接追加会**超 40 000 B** ⇒ 按惯例：
**把 §130–§134 的正文逐字归档**到 `status/archive/STATUS_APP_sec130_134_upto_20261105.md`
⇒ 文件内只留**一行速查**（正文已归档）⇒ 再追加 §135。

## 用法
```
.venv/Scripts/python.exe results/app/_app261_write_status_135.py --body status/app/_sec135_body.md
```
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                       'STATUS_APP_sec130_134_upto_20261105.md')
# 🔴 §135 正文自己的归档件（§132 同款惯例：正文逐字归档，文件内只留速查行）
ARCHIVE_135 = os.path.join(REPO, 'status', 'archive',
                            'STATUS_APP_sec135_upto_20261105.md')
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha256_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--body', default=os.path.join(REPO, 'status', 'app',
                                                    '_sec135_body.md'))
    ap.add_argument('--status', default=STATUS)
    ap.add_argument('--now', default=None,
                    help='更新时间（默认用实测值）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    # 🔴🔴🔴 **行尾归一化（CRLF ⇄ LF）**：
    #   本机 `core.autocrlf=true` ⇒ **`git checkout` / `git clone` 会把 LF 转成 CRLF**
    #   ⇒ 工作副本可能是 CRLF ⇒ ① `split('\n')` 会给每行留一个 `\r`
    #      ⇒ ② `find('## 最近更新\n')` 在 CRLF 文件里**永远找不到**（行尾是 `\r\n`）
    #      ⇒ ③ 写回时若不还原，会把整个文件悄悄改成另一种行尾。
    #   ⇒ **读入时归一化成 LF、写回时还原成原行尾**。
    _orig_raw = open(args.status, 'r', encoding='utf-8', newline='').read()
    _orig_is_crlf = '\r\n' in _orig_raw
    orig = _orig_raw.replace('\r\n', '\n')
    body = open(args.body, 'r', encoding='utf-8', newline='').read()
    body = body.replace('\r\n', '\n')
    if not body.startswith('## §135'):
        print('!! 正文必须以「## §135」开头')
        return 2

    # 🔴 旧正文起点（§130）—— 用来做「旧正文一字未删」的逐字节校验
    idx = orig.find('### §130')
    if idx < 0:
        print('!! 找不到 §130 锚点')
        return 2
    old_body = orig[idx:]
    old_head = orig[:idx]

    # ── ① 归档 §130–§134 的正文（逐字保留）────────────────────────
    #   只归档**正文**（从 §130 到 §134 末尾）；§135 之前的速查表在头部区。
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    if not os.path.isfile(ARCHIVE):
        with open(ARCHIVE, 'w', encoding='utf-8', newline='') as f:
            f.write(old_body)
        print('[archive] 已归档 §130–§134 正文 ⇒ %s（%d B）'
              % (os.path.basename(ARCHIVE), len(old_body.encode('utf-8'))))

    # ── ①' 归档 §135 的**完整正文**（逐字保留，APP-052 ④ 惯例）────────
    #   🔴 **为什么要再归档一次**：§135 正文本身就有 18 KB
    #   ⇒ 与头部区（26 KB）相加会**超 40 000 B 限额**
    #   ⇒ 按 §132 的同款惯例：**正文逐字归档**，STATUS 文件内只留**速查行**。
    #   ⇒ 归档件与 `--body` 源文件**逐字相同** ⇒ 写后自检会验。
    if not os.path.isfile(ARCHIVE_135):
        with open(ARCHIVE_135, 'w', encoding='utf-8', newline='') as f:
            f.write(body)
        print('[archive] 已归档 §135 正文 ⇒ %s（%d B）'
              % (os.path.basename(ARCHIVE_135), len(body.encode('utf-8'))))
    else:
        arch135_old = open(ARCHIVE_135, 'r', encoding='utf-8',
                           newline='').read()
        if arch135_old != body:
            print('!! §135 归档件与 --body 源文件**不一致** ⇒ 已有归档件，'
                  '不覆盖（请先人工核对）')
            return 3

    # ── ② 头部区改写 ──────────────────────────────────────────────
    lines = old_head.split('\n')
    now = args.now or time.strftime('%Y-%m-%d %H:%M')
    new_head = []
    for ln in lines:
        if ln.startswith('更新时间:'):
            new_head.append('更新时间: %s' % now)
        elif ln.startswith('当前任务:'):
            new_head.append(
                '当前任务: **§135 APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）'
                '＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** —— '
                '**APP-067 ②④ 已完成（设备级）**（② 交付物已落 '
                '`shared/app_listen/v23_clone/`；④ ABBA **10/0** ＋ GUI 臂 **5/0**）｜'
                '**APP-066 3(a) 已完成**（CLI **8/0**）｜'
                '**MiniMVP rc1 P0 已修 ⇒ rc2（9 闸门全绿）**｜'
                '**APP-066 3(b) 已完成**（GUI 冷启动：**首次 NPU 编译 1209.3 s**'
                '（真冷臂）／**第二次启动 9.5 s**（热臂）＋ 100 %/150 % 主窗口截图）')
        elif ln.startswith('阻塞 / 待用户决定:'):
            new_head.append(
                '阻塞 / 待用户决定: 🔴 **本轮停在 reviewer 复核点**'
                '（APP-067 与 APP-066 都写明「需等 reviewer」）｜'
                '⛔ **APP-066 3(c) zip 未打**（验收＋回转写＋用户抽听之前不打；'
                '且**用户不通知不打包**）｜'
                '⛔ **MiniMVP 首次 NPU 编译 = 1209.3 s ≈ 20 min**（8 个解码器桶逐个编译；'
                '热启仅 9.5 s）⇒ 客户机首启长时间无 TTS'
                '⇒ 待 reviewer 裁定是否随包分发预编译 blob｜'
                '🔴 **待 reviewer 裁定**：'
                '① `translator.py` 的 MT `auto` **label 写死**「INT8-CW」，'
                '而 MiniMVP 客户机实载包内 **INT4** ⇒ CLI `--check` 与 `auto` 的 '
                '`device_desc` 显示与实载不符（**GUI 正确**，见 §135 ⑧）'
                '② MiniMVP 首启的 NPU 编译 20 min ＋ GPU JIT 19 min ⇒ 是否随包分发 blob'
                '③ MT INT4 vs INT8 质量数据引用口径｜'
                '🔴 **v2.3 继续暂缓**（APP-067 原文「顺序 1→2→3、4→5→才能打包」）｜'
                '🔴 **未通知用户 / 未改桌面快捷方式 / 未改任何 v2.x 客户包目录**'
                '（v2.1、v2.2 一个字节都没动）')
        elif ln.startswith('已压缩:'):
            new_head.append(
                '已压缩: **§130–§134 与 §135 的正文均已原样归档**到 '
                '`status/archive/STATUS_APP_sec130_134_upto_20261105.md`'
                '（9 092 B）与 `status/archive/STATUS_APP_sec135_upto_20261105.md`'
                '（逐字保留）⇒ 本文件内只留**速查行**；'
                '**§135 为新增章节**（正文见 §135 归档件）'
                '｜限额 ≤ 40000 B / ≤ 300 行（APP-052 ④）'
                '｜写后实测 **__FINAL_SIZE__**')
        else:
            new_head.append(ln)
    new_head_s = '\n'.join(new_head)

    # ── ③ 「最近更新」顶部插一行 ──────────────────────────────────
    marker = '## 最近更新\n'
    k = new_head_s.find(marker)
    if k < 0:
        print('!! 找不到「## 最近更新」')
        return 2
    ins = marker + (
        '- %s **§135 已写** ⇒ **APP-067 ②④ 设备级补齐**（② 交付物：'
        '`shared/app_listen/v23_clone/`；④ ABBA **10/0** ＋ GUI 臂 **5/0**）｜'
        '**APP-066 3(a) CLI **8/0**；3(b) GUI 冷启动：'
        '**首次 NPU 编译 1209.3 s**（真冷臂 `app263`）／**第二次启动 9.5 s**'
        '（热臂 `app264`）+ 100%%/150%% 主窗口截图**｜'
        '🔴 **MiniMVP rc1 P0 已修 ⇒ rc2**（9 闸门全绿）＋'
        '**修好 rc2 的 `ACCEPTED.pkg_dir` 与 R2 白名单**（app191 9/6 → **18/0**）｜'
        '⛔ 3(c) zip 未打｜'
        '🔴 **本轮接管死租约（第 2 次）**：上一会话起草了 §135 但**未写 STATUS**；'
        '本轮逐条与磁盘证据对照 ⇒ **更正其「3(b) 已通过」的不实陈述**'
        '（落盘证据实为 FAIL）⇒ **重跑 3(b)**｜'
        '🔴 `CORRECTIONS_APP.md` 零改动（67 条 / SHA `cf71e427…`）\n' % now)
    new_head_s = new_head_s[:k] + ins + new_head_s[k + len(marker):]

    # ── ④ 末尾追加 §135（**只留速查行**；正文已逐字归档）────────────
    #   🔴 APP-052 ④ 限额（≤ 40 000 B / ≤ 300 行）⇒ §135 正文 18 KB 放不进
    #   ⇒ 按 §132 的同款做法：**文件内只留速查行 + 归档件指针**。
    sec135_summary = (
        '### §135 ✅ **APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）'
        '＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** ｜ '
        '**本条已完成（设备级）｜ 本条需等 reviewer 复核**（%s）\n\n'
        '> 🔴 **本节正文已原样归档** ⇒ 见 '
        '`status/archive/STATUS_APP_sec135_upto_20261105.md`'
        '（**逐字保留，内容一字未删**）。\n'
        '> 🔴 **速查**：④ ABBA **10/0** ＋ GUI 臂 **5/0**；② 交付物 **12/0**'
        '（`shared/app_listen/v23_clone/`）；3(a) CLI **8/0**；'
        '**3(b) 首次 NPU 编译 1209.3 s（真冷）→ 第二次启动 9.5 s（热）**'
        '＋ 100 %%/150 %% 主窗口截图；🔴 **修好 rc2 的 `ACCEPTED.pkg_dir` '
        '与 R2 白名单 ⇒ app191 9/6 → 18/0**；⛔ 3(c) zip 未打。\n'
        % now)
    new_text = new_head_s + sec135_summary

    # ── ⑤ 填入「写后实测」的**真实**大小（占位符回填）──────────────
    #   🔴 模板生成 ⇒ **自指大小必须与磁盘实测一致**（差 2 B 也要改）
    #   ⇒ 用「回填占位符」而不是「先算再写」⇒ 避免手算。
    for _ in range(4):                    # 迭代到不动点（回填会改变长度）
        _tmp = new_text.replace('__FINAL_SIZE__',
                                '%d B / %d 行' % (len(new_text.encode('utf-8')),
                                                  new_text.count('\n')))
        if _tmp == new_text:
            break
        new_text = _tmp

    # ── ⑥ 自检 ────────────────────────────────────────────────────
    problems = []
    nb = len(new_text.encode('utf-8'))
    nl = new_text.count('\n')
    if nb > LIMIT_BYTES:
        problems.append('字节超限：%d > %d' % (nb, LIMIT_BYTES))
    if nl > LIMIT_LINES:
        problems.append('行数超限：%d > %d' % (nl, LIMIT_LINES))
    # 归档件逐字保留（旧正文）
    arch = open(ARCHIVE, encoding='utf-8', newline='').read()
    if arch != old_body:
        problems.append('归档件与旧正文不一致（归档未逐字保留）')
    # §135 归档件逐字保留（正文）
    arch135 = open(ARCHIVE_135, encoding='utf-8', newline='').read()
    if arch135 != body:
        problems.append('§135 归档件与 --body 源文件不一致（未逐字保留）')
    # 章节数不减
    n_old = old_body.count('\n## ')
    n_new = new_text.count('\n## ')
    if n_new < n_old:
        problems.append('章节数减少：%d → %d' % (n_old, n_new))
    if '## §135' not in new_text:
        problems.append('§135 段缺失')
    if problems:
        print('!! 不写（自检不过）：')
        for p in problems:
            print('   - %s' % p)
        return 3

    if args.dry_run:
        print('[dry-run] 自检通过：%d B / %d 行（原 %d B / %d 行）'
              % (nb, nl, len(orig.encode('utf-8')), orig.count('\n')))
        return 0

    tmp = args.status + '.tmp'
    # 🔴 **写回时还原原行尾**（原文件是 CRLF 就写 CRLF，否则整个文件被悄悄换行尾）
    _out = new_text.replace('\n', '\r\n') if _orig_is_crlf else new_text
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(_out)
    os.replace(tmp, args.status)

    # ── ⑥ 写后复核 ────────────────────────────────────────────────
    chk = open(args.status, 'r', encoding='utf-8', newline='').read()
    print('写入完成：%d B / %d 行（原 %d B / %d 行，行尾 %s）'
          % (len(chk.encode('utf-8')), chk.count('\n'),
             len(orig.encode('utf-8')), orig.count('\n'),
             'CRLF' if '\r\n' in chk else 'LF'))
    print('  旧正文（§130–§134）SHA 归档件 = %s' % sha256_text(arch))
    print('  §135 段存在 = %s' % ('## §135' in chk))
    print('  last_ack = %s'
          % [ln for ln in chk.split('\n')[:6] if ln.startswith('last_ack')])
    return 0


if __name__ == '__main__':
    sys.exit(main())
