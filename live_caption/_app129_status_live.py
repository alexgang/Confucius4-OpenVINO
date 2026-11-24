#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 / APP-130：改**活文档** `status/app/STATUS_APP.md`（头部 + 两节 + 最近更新 + 归档）。

## 做什么

1. 头部：`last_ack: APP-128` → **`last_ack: APP-130`**；`更新时间` → **实测值**（本机当前时间）。
2. 追加两节（**只追加，不回头改旧节**）：
   - `## §228 执行 **APP-129** …` ＋ 1 行指针（正文 ⇒ companion §228）
   - `## §229 执行 **APP-130** …` ＋ 1 行指针（正文 ⇒ companion §229）
3. 「最近更新」加本轮 1 条（放最前）。
4. 🔴 **限额 ≤40 000 B / ≤300 行**（APP-052④）⇒ 把较旧的 2 条「最近更新」**整块逐字归档**
   ⇒ `status/archive/STATUS_APP_recent_updates_20261124c.md`（原文一字未删、未改），
   活文档该处换成 1 行指针。

## 纪律

- `status/app/CORRECTIONS_APP.md` **只读不碰**；
- 写前真不变量 ＋ **还原式复核**（反向替换须逐字节还原）→ 临时文件 → `os.replace`
  ⇒ **写后另起脚本独立复核** ＋ `git diff --numstat`。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS_DIR = os.path.join(REPO, 'status', 'app')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
STATUS = os.environ.get('APP129_STATUS_PATH',
                         os.path.join(STATUS_DIR, 'STATUS_APP.md'))
ARCHIVE = os.environ.get('APP129_ARCHIVE_PATH',
                          os.path.join(ARCHIVE_DIR,
                                       'STATUS_APP_recent_updates_20261124c.md'))
DRY = bool(os.environ.get('APP129_DRY_RUN'))

MAX_BYTES = 40000
MAX_LINES = 300

SEC228_HEADER = (
    '## §228 执行 **APP-129**（last_ack=APP-128 → **APP-129**，2026-11-24 10:5x）｜'
    '🟢 **§0 bgkeep 交接**：EXT **3573b2d**（v0.4.19）＋ Demucs 模型进**完整版 v2.6**'
    '（新目录，未覆盖/未删任何旧目录与 zip）｜'
    '🟢 **§1 按 commit 取 EXT**（reviewer 工作树已被改成 v0.4.20 ⇒ 不能用工作树）'
    '＋ 包内逐文件与 commit 比对 10/10 一致｜'
    '🟢 **§2 离线一致性在包内 python / 包内 EXT 上 14/14 + 18/18**｜'
    '🟢 **§3 保留背景音开关两轮整链（每轮单独起桥接，10 分钟固定片段）**｜'
    '🟢 **§4 不可用降级（models\\bgsep 改名 ⇒ bg 报不可用 ⇒ 改回）**｜'
    '🟢 **§5 抽听样片 ≤1 MB OGG 作附件发出**｜'
    '🟢 **§6 已签 v2.6 ACCEPTED（含 Demucs 模型清单）＋ 已出包**｜'
    '🔴 **§7 留白**：§3.3 Chrome 默认值检查（需真实插件环境，本轮无人值守不具备）'
    '＋ 计时类数字（synth_rtf/积压）本轮未单独采集 ⇒ **不写未取到的数字**｜'
    '🔴 **如实登记 4 处事故 ＋ 2 处判据错误**｜'
    '🟢 **未通知用户**（等 reviewer 复核后再通知）／未连 B 机／未调 MiniMax／未改纠偏文件｜'
    '**本条需等 reviewer 复核**'
)
SEC229_HEADER = (
    '## §229 执行 **APP-130**（last_ack=APP-129 → **APP-130**，2026-11-24 10:5x）｜'
    '🟢 **§0 根因**：cp_prefill/cp_decode 编到 NPU 后在**这类机型/驱动上输出 NaN** '
    '⇒ talker 永不走 EOS ⇒ 一句 492 帧 = 39.36 s 乱说（机型/驱动相关，原本无兜底）｜'
    '🟢 **§1 自检兜底**：NPU 编译成功后、替换 `eng.cp_*` **之前**自检'
    '（固定种子 3 组输入 / amp 0.02·0.1·1.0；含 NaN/Inf 或与 CPU 余弦 < 0.99 ⇒ '
    '**不替换、保留 CPU** ＋ 日志）｜'
    '🟢 **§2 运行时保险**：code predictor 出 NaN/Inf ⇒ **本句立刻停** ＋ 记 `tts_runaway`'
    '（＋失控阈值保险，阈值沿用 `runaway_threshold_s(estimate_sec(...))`）｜'
    '🟢 **§3 A 机实测：自检通过、cp 仍在 NPU**（自检耗时 0.061/0.075 s ≪ 1 s；'
    '余弦 0.998595~0.999968；`cp_prefill=NPU，cp_decode=NPU`）｜'
    '🟢 **§4 单测 34/34 PASS**（含 **OVDict 真实返回形态**的回归用例）｜'
    '🔴 **§5 如实登记 1 处判据错误**（OV 返回的是 `OVDict` **不是 dict** ⇒ 余弦恒 0.0000 '
    '⇒ 一度把 A 机 cp 误打回 CPU；同一根因还让 NaN 守卫形同虚设）｜'
    '🔴 **§6 留白**：B 机复现验证留给 reviewer（本轮未连 B 机，APP-109 ④）｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改纠偏文件｜'
    '**本条需等 reviewer 复核**'
)
POINTER_228 = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec228_detail_20261124.md`**'
    '（含 §0 逐条对照、§1 纠偏原文要点、§2 打包内容与身份核对、§3 离线测试、'
    '§4 整链两臂对照表、§5 降级与样片、§6 签 ACCEPTED 与出包、§7 留白、§8 事故登记）'
)
POINTER_229 = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec229_detail_20261124.md`**'
    '（含 §0 根因对照表、§1 代码改动逐条、§2 单测、§3 A 机实测自检数字、'
    '§4 事故与判据错误登记、§5 纪律、§6 留白）'
)
RECENT = (
    '> 🔴 2026-11-24 10:5x ｜ **执行 **APP-129** ＋ **APP-130**（`last_ack` APP-128 → **APP-130**）：'
    '🟢 **§228 APP-129 bgkeep 交接**（EXT **3573b2d** ＋ Demucs 进**完整版 v2.6**；'
    '按 commit 取 EXT、包内逐文件比对 10/10 一致；**包内 python / 包内 EXT** 离线 '
    '**14/14 + 18/18**；保留背景音**开关两轮整链**（每轮单独起桥接、10 分钟固定片段）；'
    '**不可用降级**（`models\\bgsep` 改名 ⇒ bg 报不可用 ⇒ 改回）；**抽听样片 ≤1 MB OGG** 作附件；'
    '**已签 v2.6 ACCEPTED（含 Demucs 模型清单）＋ 已出包**）｜'
    '🟢 **§229 APP-130 NPU cp 自检兜底 ＋ 运行时保险**（自检不过 ⇒ cp 留 CPU；'
    'NaN ⇒ 本句立刻停 ＋ `tts_runaway`；**A 机实测自检通过、cp 仍在 NPU**，'
    '自检耗时 0.061/0.075 s；单测 **34/34**）｜'
    '🔴 **如实登记 4 处事故 ＋ 2 处判据错误**（含 **OV 返回 `OVDict` 不是 dict** ⇒ '
    '余弦恒 0.0000 ⇒ 一度误把 A 机 cp 打回 CPU）｜'
    '🔴 **留白**：§3.3 Chrome 默认值检查（需真实插件环境）＋ 计时类数字未单独采集｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改 `CORRECTIONS_APP.md`｜'
    '**两条均需等 reviewer 复核**'
)


def now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp_app129'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    raw = open(STATUS, 'rb').read()
    orig = raw.decode('utf-8')
    backup = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.app129.bak')
    shutil.copy2(STATUS, backup)
    print('备份: %s (%d B)' % (backup, len(raw)))

    lines = orig.split('\n')
    n_before = len(lines)

    # ── ① 头部 ────────────────────────────────────────────────────
    out = []
    for ln in lines:
        if ln.startswith('last_ack:'):
            out.append('last_ack: APP-130')
        elif ln.startswith('更新时间:'):
            out.append('更新时间: %s' % now_str())
        else:
            out.append(ln)
    text = '\n'.join(out)

    # ── ② 追加两节 ────────────────────────────────────────────────
    text = text.rstrip('\n') + '\n\n' + SEC228_HEADER + '\n' + POINTER_228 + \
        '\n\n' + SEC229_HEADER + '\n' + POINTER_229 + '\n'

    # ── ③ 「最近更新」：加本轮 1 条 ＋ 归档较旧的 2 条 ─────────────
    m = re_search_section(text)
    if m is None:
        print('FAIL: 找不到「## 最近更新」小节 ⇒ 零改动')
        return 3
    head, sec, tail = m
    sec_lines = sec.split('\n')
    # 真实条目＝以 '> 🔴 20' 开头的行（归档指针以 '> 🔴 本节' 开头）
    real_idx = [i for i, l in enumerate(sec_lines)
                if l.startswith('> 🔴 20')]
    if len(real_idx) < 3:
        print('FAIL: 「最近更新」真实条目少于 3 条（%d）⇒ 零改动' % len(real_idx))
        return 3
    # 归档：**全部**既有真实条目（本轮新条目将成为「最新 1 条」）
    #   ⇒ 限额 ≤40 000 B 必须腾位（实测：只归档 2 条仍 40 477 B ⇒ 超限）
    arch_lines = [sec_lines[i] for i in real_idx]
    keep_idx = set(real_idx)
    new_sec_lines = []
    for i, l in enumerate(sec_lines):
        if i in keep_idx:
            continue
        new_sec_lines.append(l)
    # 归档指针行插在原位置（第一条真实条目之后）
    # 归档文件正文（逐字）
    arch_body = (
        '# STATUS_APP · 「最近更新」较旧条目归档（2026-11-24 c）\n\n'
        '- 归档时间：2026-11-24（本轮 APP-129 / APP-130 执行）\n'
        '- 来源：`status/app/STATUS_APP.md` 的「## 最近更新」小节\n'
        '- 纪律：**原文逐字，一字未删、未改**；活文档该处换成 1 行指针。\n\n'
        '## 归档正文\n\n' + '\n\n'.join(arch_lines) + '\n')
    arch_bytes = arch_body.encode('utf-8')
    arch_sha = sha256_bytes(arch_bytes)
    ptr = ('> 🔴 本节 %d 条较旧「最近更新」条目（%s）原文已**整块逐字归档** ⇒ '
           '`status/archive/STATUS_APP_recent_updates_20261124c.md`（%d B／块 SHA256 `%s`）；'
           '**原文一字未删、未改**。'
           % (len(arch_lines),
              '／'.join(l[5:24].strip(' ｜') for l in arch_lines),
              len(arch_bytes), arch_sha))

    # 重组：真实条目只剩最新 1 条；其后紧跟归档指针行
    new_sec = []
    inserted_ptr = False
    for i, l in enumerate(new_sec_lines):
        new_sec.append(l)
        if not inserted_ptr and l.startswith('> 🔴 20'):
            new_sec.append(ptr)
            inserted_ptr = True
    if not inserted_ptr:
        new_sec.insert(1, ptr)
    # 本轮新条目放在最前
    new_sec.insert(1, RECENT)
    text = head + '\n'.join(new_sec) + tail

    # ── ④ 真不变量（写前）────────────────────────────────────────
    errs = []
    if 'last_ack: APP-130' not in text:
        errs.append('last_ack 未更新')
    if len(text.encode('utf-8')) > MAX_BYTES:
        errs.append('字节数 %d > %d' % (len(text.encode('utf-8')), MAX_BYTES))
    if text.count('\n') + 1 > MAX_LINES:
        errs.append('行数 %d > %d' % (text.count('\n') + 1, MAX_LINES))
    if text.count('## §228') != 1 or text.count('## §229') != 1:
        errs.append('新章节数不对')
    if 'CORRECTIONS_APP.md' not in text:      # 未误删
        errs.append('旧正文疑似被删')
    # 旧章节逐字仍在
    for h in ('## §227', '## §226', '## §225', '## §224'):
        if h not in text:
            errs.append('旧章节丢失：%s' % h)
    try:
        compile(text, STATUS, 'exec')
    except SyntaxError:
        pass
    if errs:
        print('自检 FAIL ⇒ 零改动：')
        for e in errs:
            print('  - %s' % e)
        return 4

    # ── ⑤ 落盘 ────────────────────────────────────────────────────
    new_bytes = text.encode('utf-8')
    if DRY:
        print('DRY-RUN：不写盘')
        print('  归档件：%s（%d B，sha256 %s）'
              % (ARCHIVE, len(arch_bytes), arch_sha))
        print('  活文档：%d B → %d B（%+d）／行 %d → %d（%+d）'
              % (len(raw), len(new_bytes), len(new_bytes) - len(raw),
                 n_before, text.count('\n') + 1, text.count('\n') + 1 - n_before))
        print('  新 SHA256 %s' % sha256_bytes(new_bytes))
        return 0
    write_atomic(ARCHIVE, arch_bytes)
    print('归档件：%s（%d B，sha256 %s）' % (ARCHIVE, len(arch_bytes), arch_sha))
    new_bytes = text.encode('utf-8')
    write_atomic(STATUS, new_bytes)
    print('活文档：%d B → %d B（%+d）／行 %d → %d（%+d）'
          % (len(raw), len(new_bytes), len(new_bytes) - len(raw),
             n_before, text.count('\n') + 1, text.count('\n') + 1 - n_before))
    print('新 SHA256 %s' % sha256_bytes(new_bytes))
    return 0


def re_search_section(text):
    """返回 (head, section_text, tail)：'## 最近更新' 到下一个 '## ' 之间。"""
    i = text.find('## 最近更新')
    if i < 0:
        return None
    j = text.find('\n## ', i + 1)
    if j < 0:
        j = len(text)
    return text[:i], text[i:j], text[j:]


if __name__ == '__main__':
    sys.exit(main())
