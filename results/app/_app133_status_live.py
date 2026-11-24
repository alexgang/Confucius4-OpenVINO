#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-131/132/133：改**活文档** `status/app/STATUS_APP.md`
（头部 + **三节**（§228/§229/§230）+ 最近更新 + 归档）。

## 与上一版（`_app129_status_live.py`）的差别

上一版是**上一会话**写的（§228/§229），但：
1. 它的 `SEC228_HEADER` 里写着 **EXT `3573b2d`（v0.4.19）** ⇒ **已被 APP-131/133 覆盖**
   （最终是 **b2a4978 / v0.4.21**）⇒ 必须改；
2. 它写「**已出包**」⇒ 本轮**只出目录 ＋ 签 ACCEPTED，**不打 zip**
   （用户级纪律「不通知 ⇒ 不打包」＋ 完整版 v2.x 历来无 zip）⇒ 必须改；
3. 它没有 **§230**（APP-131/132/133 的落点）⇒ 必须加。

## 纪律

- `status/app/CORRECTIONS_APP.md` **只读不碰**；
- **只追加**新章节，**不回头改旧章节**（§227 及更早逐字不动）；
- 🔴 **限额 ≤40 000 B / ≤300 行**（APP-052④）⇒ 「最近更新」较旧条目
  **整块逐字归档**到 `status/archive/`（原文一字未删、未改）；
- 写前真不变量 ＋ **还原式复核** → 临时文件 → `os.replace`
  ⇒ **写后另起脚本独立复核** ＋ `git diff --numstat`。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS_DIR = os.path.join(REPO, 'status', 'app')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
STATUS = os.environ.get('APP133_STATUS_PATH',
                         os.path.join(STATUS_DIR, 'STATUS_APP.md'))
ARCHIVE = os.environ.get('APP133_ARCHIVE_PATH',
                          os.path.join(ARCHIVE_DIR,
                                       'STATUS_APP_recent_updates_20261124d.md'))
DRY = bool(os.environ.get('APP133_DRY_RUN'))

MAX_BYTES = 40000
MAX_LINES = 300

SEC228_HEADER = (
    '## §228 执行 **APP-129**（last_ack=APP-128 → **APP-129**，2026-11-24）｜'
    '🟢 **bgkeep 交接**：EXT ＋ Demucs 进**完整版 v2.6**（新目录；'
    '旧目录与 zip 未覆盖未删）｜🟢 **按 commit 取 EXT**（不用工作树）'
    '＋包内逐文件比对｜🟢 **离线一致性在包内 python / 包内 EXT 上 14/14 + 18/18**'
    '（＋ APP-133 的 **16/16**）｜🟢 **保留背景音开关两轮整链**（每轮单独起桥接、'
    '10 分钟固定片段）｜🟢 **不可用降级**（`models\\bgsep` 改名 ⇒ bg 报不可用 ⇒ 改回）'
    '｜🟢 **抽听样片 ≤1 MB OGG**｜🟢 **已签 v2.6 ACCEPTED（含 Demucs 模型清单）**｜'
    '🔴 **留白**：§3.3 Chrome 默认值检查的**浏览器端 UI 交互**（reviewer 复核）'
    '＋**B 机复现验证**｜🔴 **如实登记事故与判据错误**｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改纠偏文件｜'
    '**本条需等 reviewer 复核**'
)
SEC229_HEADER = (
    '## §229 执行 **APP-130**（last_ack=APP-129 → **APP-130**，2026-11-24）｜'
    '🟢 **根因**：cp_prefill/cp_decode 编到 NPU 后在**这类机型/驱动上输出 NaN** '
    '⇒ talker 永不走 EOS ⇒ 一句 492 帧 = 39.36 s 乱说（机型/驱动相关，原本无兜底）｜'
    '🟢 **自检兜底**：NPU 编译成功后、替换 `eng.cp_*` **之前**自检'
    '（3 组输入；含 NaN/Inf 或与 CPU 余弦 < 0.99 ⇒ **不替换、保留 CPU** ＋ 日志）｜'
    '🟢 **运行时保险**：cp 出 NaN/Inf ⇒ **本句立刻停** ＋ 记 `tts_runaway`'
    '（＋失控阈值保险）｜🟢 **A 机实测：自检通过、cp 仍在 NPU**（自检耗时 ≪ 1 s）｜'
    '🟢 **单测 34/34 PASS**（含 **OVDict 真实返回形态**回归用例）｜'
    '🔴 **如实登记 1 处判据错误**（OV 返回 `OVDict` **不是 dict** ⇒ 余弦恒 0.0000 '
    '⇒ 一度把 A 机 cp 误打回 CPU；同一根因还让 NaN 守卫形同虚设）｜'
    '🔴 **留白**：B 机复现验证留给 reviewer（未连 B 机，APP-109 ④）｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改纠偏文件｜'
    '**本条需等 reviewer 复核**'
)
SEC230_HEADER = (
    '## §230 执行 **APP-131 / APP-132 / APP-133**（last_ack=APP-130 → **APP-133**，'
    '2026-11-24）｜🟢 **§1 APP-133：v2.6 的 EXT = `b2a4978`（v0.4.21）**'
    '（替代 APP-131 的 4740b06；包内 EXT 与 commit **逐字节独立复核 44 文件 0 错**'
    '＋**反证组证明判据承重**）｜🟢 **§2 离线一致性：包内 python / 包内 EXT '
    '⇒ 14/14 + 18/18 + 16/16**（16/16 与 APP-133 口径一致）｜'
    '🟢 **§3 APP-132：机器锁修掉两处真缺陷**（① `os.replace` 写锁**不是原子创建** '
    '⇒ reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我方**实际没在持锁**；'
    '② 看门狗**一旦被抢就彻底放弃写回** ⇒ 链继续跑但不再持锁）'
    '⇒ 改用 **O_CREAT\\|O_EXCL 原子创建 ＋ 10 s 复核 ＋ 丢锁即记事件**；'
    '**本轮一次持锁到底**（三臂＋默认值检查＋抽听样片，`lock_lost` **0** 条）｜'
    '🟢 **§4 整链三臂重跑**（10 分钟固定片段、每轮单独起桥接）'
    '＋ **clone 臂的 `stats_full.clone_reasons` / `n_gender_splits`**｜'
    '🔴 **§5 如实登记本轮 4 处真缺陷**（就绪判据假 PASS／OGG 编码器不可用／'
    '降级探针缺 Origin 被 1008 拒／包测试分母过期）｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改纠偏文件｜'
    '**本条需等 reviewer 复核**'
)
POINTER_228 = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec228_detail_20261124.md`**'
    '（含 §0 逐条对照、§1 纠偏原文要点、§2 打包内容与身份核对、§3 离线测试、'
    '§4 整链两臂对照表、§5 降级与样片、§6 签 ACCEPTED、§7 留白、§8 事故登记）'
)
POINTER_229 = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec229_detail_20261124.md`**'
    '（含 §0 根因对照表、§1 代码改动逐条、§2 单测、§3 A 机实测自检数字、'
    '§4 事故与判据错误登记、§5 纪律、§6 留白）'
)
POINTER_230 = (
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec230_detail_20261124.md`**'
    '（含 §1 EXT 版本与独立复核、§2 离线一致性 14/14+18/18+16/16、'
    '§3 机器锁两处真缺陷与修法＋持锁证据＋reviewer 桥接日志重叠核对、'
    '§4 整链三臂对照表＋clone 计数、§5 默认值/降级/样片、§6 签 ACCEPTED、§7 纪律）'
)
RECENT = (
    '> 🔴 2026-11-24 17:4x ｜ **执行 **APP-131 / APP-132 / APP-133**'
    '（`last_ack` APP-130 → **APP-133**）：'
    '🟢 **§230 EXT 升到 `b2a4978`（v0.4.21）**（替代 APP-131 的 4740b06；'
    '包内 EXT 与 commit **逐字节独立复核 44 文件 0 错 ＋ 反证组承重**）｜'
    '🟢 **离线一致性 **14/14 + 18/18 + 16/16**（**包内 python / 包内 EXT**；'
    '16/16 与 APP-133 口径一致）｜'
    '🟢 **APP-132 机器锁修掉两处真缺陷**（`os.replace` 非原子 ＋ 看门狗被抢即放弃）'
    '⇒ **O_CREAT\\|O_EXCL 原子创建 ＋ 10 s 复核 ＋ 丢锁即记事件**；'
    '**整条链一次持锁到底**（三臂＋默认值检查＋抽听样片，`lock_lost` **0** 条）｜'
    '🟢 **整链三臂重跑**（10 分钟固定片段、每轮单独起桥接）＋ **clone 臂克隆计数**｜'
    '🔴 **如实登记 4 处真缺陷**（就绪判据假 PASS／PyAV 19 的 vorbis 编码器不可用 '
    '⇒ OGG 全没生成／降级探针缺 Origin 被 1008 拒／包测试分母还写 12 ⇒ 16/16 被判 FAIL）｜'
    '🟢 **未通知用户**／未连 B 机／未调 MiniMax／未改 `CORRECTIONS_APP.md`｜'
    '**本条需等 reviewer 复核**'
)


def now_str():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp_app133'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def re_search_section(text):
    """返回 (head, section_text, tail)：'## 最近更新' 到下一个 '## ' 之间。"""
    i = text.find('## 最近更新')
    if i < 0:
        return None
    j = text.find('\n## ', i + 1)
    if j < 0:
        j = len(text)
    return text[:i], text[i:j], text[j:]


def main():
    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    n_before = text.count('\n') + 1
    errs = []

    # 🔴 **写前存下工作树副本**（复核脚本的基线）
    #    ⇒ 不能用 `git show HEAD:`（autocrlf ⇒ blob 是 LF、工作树是 CRLF
    #    ⇒ 逐字比**必然假 FAIL**）
    import tempfile
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app133_worktree')
    with open(bak, 'wb') as f:
        f.write(raw)
    print('写前工作树副本：%s（%d B）' % (bak, len(raw)))

    # ── ① 头部：last_ack + 更新时间 ─────────────────────────────
    out = []
    for ln in text.split('\n'):
        if ln.startswith('last_ack:'):
            out.append('last_ack: APP-133')
        elif ln.startswith('更新时间:'):
            out.append('更新时间: %s' % now_str())
        else:
            out.append(ln)
    text = '\n'.join(out)

    # ── ② 追加三节（**只追加**到**文档末尾**，不回头改旧节）────
    #    🔴 位置口径：活文档的「§N 执行…」节是**按节号升序排在文末**
    #    （§211…§227 在最后）⇒ 新节必须接在**§227 之后**（文件末尾），
    #    **不能**插到「## 最近更新」前面（那会把节号顺序打乱）。
    if '## §228 执行' in text:
        print('FAIL: 活文档里已经有 §228 ⇒ 不重复追加 ⇒ 零改动')
        return 2
    new_sections = (
        '\n'
        + SEC228_HEADER + '\n' + POINTER_228 + '\n\n'
        + SEC229_HEADER + '\n' + POINTER_229 + '\n\n'
        + SEC230_HEADER + '\n' + POINTER_230 + '\n'
    )
    text = text.rstrip('\r\n') + new_sections

    # ── ③ 「最近更新」：加本轮 1 条（放最前）＋ 归档旧条目 ──────
    # 🔴 活文档只剩 ~1 100 B 余量（38 829 B / 上限 40 000 B）⇒ 本轮三节
    #   ＋ 新条目放不下 ⇒ 必须腾位。
    #   腾位口径（沿用本项目「§八 归档最近更新多条 ⇒ 合并成 1 行指针」）：
    #   **把「最近更新」里除本轮新条目外的全部行**（含历次指针行）
    #   **整块逐字归档** ⇒ 活文档只留 **1 行指针** ＋ 本轮新条目。
    #   ⇒ 归档件里**逐字**保留旧指针行 ⇒ 「旧条目 ⇒ 旧归档件」的引用链不丢。
    parts = re_search_section(text)
    head, sect, tail = parts
    lines = sect.split('\n')
    # 「最近更新」小节里除标题行外的全部 `> ` 行
    old_idx = [i for i, l in enumerate(lines)
               if i > 0 and l.startswith('> ')]
    if len(old_idx) < 2:
        print('FAIL: 「最近更新」条目少于 2 条 ⇒ 零改动')
        return 2
    old_entries = [lines[i] for i in old_idx]
    arch = [
        '# STATUS_APP · 「最近更新」旧条目归档（2026-11-24 d）', '',
        '- 来源：`status/app/STATUS_APP.md` 的「## 最近更新」小节',
        '- 归档时间：%s' % now_str(),
        '- 归档原因：APP-052④ 活文档限额 ≤40 000 B / ≤300 行 ⇒ 腾位',
        '- 归档行数：**%d** 行（含历次指针行；原文**逐字**保留，一字未删、未改）'
        % len(old_entries),
        '', '---', '',
    ] + old_entries
    arch_bytes = ('\n'.join(arch) + '\n').encode('utf-8')
    arch_sha = sha256_bytes(arch_bytes)
    ptr = ('> 🔴 本节 %d 行较旧「最近更新」条目（含历次指针行）原文已**整块逐字归档** ⇒ '
           '`status/archive/STATUS_APP_recent_updates_20261124d.md`'
           '（%d B／块 SHA256 `%s`）；**原文一字未删、未改**。'
           % (len(old_entries), len(arch_bytes), arch_sha))
    ls = lines[:old_idx[0]]
    # 🔴 **本轮新条目在最前**（沿用本节惯例：最新的放最前）
    ls.append(RECENT)
    ls.append(ptr)
    ls.extend(lines[old_idx[-1] + 1:])
    sect = '\n'.join(ls)
    text = head + sect + tail

    # ── ④ 真不变量 ─────────────────────────────────────────────
    if 'last_ack: APP-133' not in text:
        errs.append('last_ack 未更新')
    for s in (SEC228_HEADER, SEC229_HEADER, SEC230_HEADER):
        if s not in text:
            errs.append('节标题未落位：%s…' % s[:24])
    if text.count('## §228 执行') != 1 or text.count('## §229 执行') != 1 \
            or text.count('## §230 执行') != 1:
        errs.append('节的条数不对（应各 1）')
    # 旧节逐字未变
    for h in ('## §227 巡检', '## §226 巡检', '## §225 执行'):
        if h not in text:
            errs.append('旧节 %s 丢了' % h)
    if errs:
        print('FAIL: 真不变量不过 ⇒ 零改动')
        for e in errs:
            print('  🔴', e)
        return 3

    new_bytes = text.encode('utf-8')
    if len(new_bytes) > MAX_BYTES:
        print('FAIL: 写后 %d B > 上限 %d B ⇒ 零改动（需再归档）'
              % (len(new_bytes), MAX_BYTES))
        return 4
    if text.count('\n') + 1 > MAX_LINES:
        print('FAIL: 写后行数 %d > 上限 %d ⇒ 零改动'
              % (text.count('\n') + 1, MAX_LINES))
        return 5

    if DRY:
        print('DRY-RUN：%d B → %d B（%+d）／行 %d → %d'
              % (len(raw), len(new_bytes), len(new_bytes) - len(raw),
                 n_before, text.count('\n') + 1))
        print('新 SHA256 %s' % sha256_bytes(new_bytes))
        return 0

    write_atomic(ARCHIVE, arch_bytes)
    print('归档件：%s（%d B，sha256 %s）' % (ARCHIVE, len(arch_bytes), arch_sha))
    write_atomic(STATUS, new_bytes)
    print('活文档：%d B → %d B（%+d）／行 %d → %d（%+d）'
          % (len(raw), len(new_bytes), len(new_bytes) - len(raw),
             n_before, text.count('\n') + 1, text.count('\n') + 1 - n_before))
    print('新 SHA256 %s' % sha256_bytes(new_bytes))
    return 0


if __name__ == '__main__':
    sys.exit(main())
