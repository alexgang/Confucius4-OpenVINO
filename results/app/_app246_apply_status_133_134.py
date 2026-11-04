# -*- coding: utf-8 -*-
"""APP-067/066 的 STATUS 定点写入（§133 + §134）。

纪律：
* 只动：① 头部区（last_ack/更新时间/当前任务/阻塞/已压缩）②「最近更新」追加一行
  ③「最近章节」索引追加两行 ④ 追加 §133 + §134 两节；
* §132 的正文**逐字已在** status/archive/STATUS_APP_sec132_upto_20261103.md
  ⇒ 文件内按 APP-052 ④ 惯例收成 3 行速查（**归档件逐字不动**）；
* 写后校验：旧章节一个不少 + 归档件命中 + 字节/行数在限额内 + 行尾未破。
"""
import io
import os
import re
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SEC = os.path.join(HERE, '_app133_134_status_section.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec132_upto_20261103.md')

LIMIT_B, LIMIT_L = 40000, 300

TASK = (
    '当前任务: **§133 APP-067（①克隆 0 % 根因 / ②APP-065 C 交付物 / '
    '③D4 界面 / ④设备验收 / ⑤D1 5 s 窗口）＋ §134 APP-066'
    '（MiniMVP 最小客户包 rc1）—— 代码层与构建层已执行** —— '
    '① **APP-067 ①③⑤ 已完成（设备级）**：`app243` **9 PASS / 0 FAIL**'
    '（clone **41/42 = 97.62 %**、带 spk 句 36/42 = 85.71 %、'
    '「没有可用引擎」= 0、加载期排队补登记、5.000 s 窗口 45 次）'
    '＋ 4 条反证全被抓住 ｜ ② **APP-066 v1.0 的 6 处硬缺陷（含 P0 '
    '无法启动）已修** ⇒ 新目录 **`MiniMVP_v1.0-rc1`**（**7 个构建闸门'
    '全绿**、10 507 文件 / 6 843.9 MB = v2.2 的 **52.41 %**）')

BLOCK = (
    '阻塞 / 待用户决定: 🔴 **本轮停在 reviewer 复核点**（APP-067 与 '
    'APP-066 都写明「需等 reviewer」）｜⛔ **APP-067 ②④ 的设备级部分'
    '未做**（② 每段音色表 ＋ 男/女各 3 段 wav ＋ 原声参考；④ ABBA / '
    'GUI 臂 / ASR RTF +0.122 复测）⇒ 需持 `MACHINE_LOCK`（本轮 '
    '**ASR 模块持锁**，pid 49688，20:34:25 ⇒ 未抢锁、未占设备）｜'
    '⛔ **APP-066 3(a)(b)(c) 未做**（CLI 5 分钟片段指标 ＋ 配音 wav；'
    'GUI 冷启动 ＋ 100 %/150 % 截图；**zip 未生成** ⇒ 验收后再打）｜'
    '🔴 **待 reviewer 裁定**：① APP-066「不能 import torch」字面口径'
    '（包内 app/ 3 处，均在 `backends.py` 的 torch/hybrid 后端 ⇒ '
    '运行不可达；改开发版会波及 v2.x）② MT INT4 质量数据引用口径 ｜'
    '🔴 **v2.3 继续暂缓**（APP-067 原文「顺序 1→2→3、4→5→才能打包」）'
    '｜🔴 **未通知用户 / 未改桌面快捷方式 / 未改任何 v2.x 客户包目录**'
    '（v2.1、v2.2 一个字节都没动）')

RECENT = (
    '- 2026-11-04 21:12 **§133 + §134 已写** ⇒ **APP-067 ①③⑤ 已完成'
    '（设备级，`app243` 9/0 + 4 反证）**｜**APP-066 v1.0 的 6 处硬缺陷（含 P0 '
    '无法启动）已修** ⇒ **`MiniMVP_v1.0-rc1`**（7 闸门全绿 / 52.41 % 体积）'
    '｜⛔ ②④ 与 (a)(b)(c) 未做（等锁）｜🔴 `CORRECTIONS_APP.md` 零改动'
    '（67 条 / SHA `cf71e427…`）\n')

INDEX = (
    '\n| §133 | **APP-067**：①克隆 0 % 根因（加载期排队 + seg→spk 绑定）'
    '＋ ③D4 界面 ＋ ④按钮/高级组截图 ＋ ⑤D1 5 s 窗口 ⇒ **①③⑤ 设备级已完成**；'
    '②④ 设备级未做（等锁） | **本轮新增（见下）** |\n'
    '| §134 | **APP-066**：MiniMVP 最小包 v1.0 的 **6 处硬缺陷（含 P0 无法启动）**'
    '已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 构建闸门全绿 / 52.41 % 体积）；'
    '(a)(b)(c) 设备级未做 | **本轮新增（见下）** |')

SEC132_STUB = (
    '### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律'
    ' ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层 ＋ 设备级）** ｜ '
    '**本条需等 reviewer 复核**（2026-11-03 00:05）\n\n'
    '> 🔴 **本节正文已原样归档** ⇒ 见 '
    '`status/archive/STATUS_APP_sec132_upto_20261103.md`'
    '（**逐字保留，内容一字未删**）。\n\n')


def must(cond, msg):
    if not cond:
        raise SystemExit('ABORT: ' + msg)


def set_line(text, key, value):
    pat = re.compile(r'^' + re.escape(key) + r'.*$', re.M)
    must(pat.search(text), '找不到行：' + key)
    return pat.sub(lambda m: value, text, count=1)


def main():
    old = io.open(P, encoding='utf-8', newline='').read()
    body_new = io.open(SEC, encoding='utf-8', newline='').read()

    # ── ① 收 §132 正文（归档件已逐字留存） ────────────────
    i132 = old.index('### §132 ')
    new = old[:i132] + SEC132_STUB + body_new

    # ── ② 头部区 ────────────────────────────────────────
    must('last_ack: APP-067' in new, 'last_ack 应已是 APP-067')
    new = re.sub(r'^更新时间: .*$', '更新时间: 2026-11-04 21:12', new,
                 count=1, flags=re.M)
    new = set_line(new, '当前任务:', TASK)
    new = set_line(new, '阻塞 / 待用户决定:', BLOCK)
    new = set_line(new, '已压缩:',
                   '已压缩: 本文件 __SIZE__（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；'
                   '**§132 正文已原样归档**到 '
                   '`status/archive/STATUS_APP_sec132_upto_20261103.md`（逐字保留）'
                   '⇒ 文件内只留速查行（**本轮新增 §133/§134 为同一惯例**）')

    # ── ③ 最近更新：追加一行 ───────────────────────────
    anchor = '## 最近更新\n'
    must(anchor in new, '最近更新锚点缺失')
    new = new.replace(anchor, anchor + RECENT, 1)

    # ── ④ 最近章节：追加两行索引 ─────────────────────────
    m = re.search(r'^\| §132 \|.*$', new, re.M)
    must(m, '§132 索引行缺失')
    new = new[:m.end()] + INDEX + new[m.end():]

    # ── ⑤ 填体积（自指大小必须与磁盘实测一致） ────────────
    size_txt = '%d B / %d 行' % (len(new.encode('utf-8')), new.count('\n') + 1)
    new = new.replace('__SIZE__', size_txt, 1)

    # ── ⑥ 写前校验 ─────────────────────────────────────
    for tag in ('§130', '§131', '§132', '§133', '§134'):
        must(('### ' + tag) in new, '缺章节 ' + tag)
    must(os.path.isfile(ARCH), '§132 归档件缺失')
    must(new.count('\r\n') == 0, '行尾被破坏')

    # ── ⑦ 原子写入 ─────────────────────────────────────
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(P), suffix='.tmp')
    os.close(fd)
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    shutil.move(tmp, P)

    # ── ⑧ 写后校验 ─────────────────────────────────────
    chk = io.open(P, encoding='utf-8', newline='').read()
    b = len(chk.encode('utf-8'))
    l = chk.count('\n') + 1
    for tag in ('§130', '§131', '§132', '§133', '§134'):
        must(('### ' + tag) in chk, '写后缺章节 ' + tag)
    must(chk.count('\r\n') == 0, '写后行尾被破坏')
    print('写后：%d B / %d 行（限额 %d B / %d 行）' % (b, l, LIMIT_B, LIMIT_L))
    must(b <= LIMIT_B and l <= LIMIT_L, '超限额！')
    print('OK')


if __name__ == '__main__':
    main()
