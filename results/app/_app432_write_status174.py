# -*- coding: utf-8 -*-
"""🔴 §174 写入器：追加 `## §174` 章节到 `status/app/STATUS_APP.md`。

## 🔴 纪律（本脚本自带自检，写完不通过 ⇒ 源文件零改动）

1. **只追加**：新章节加在**文件末尾**；旧章节**一字未删**（写前把旧正文逐字节存快照）。
2. **归档件 write-once**：先写 `status/archive/STATUS_APP_sec174_20261111.md`（正文全文），
   **再**在活文档里放**指针 + 速查**（≤ 3 行的索引）⇒ 活文档体积受控。
   ⚠️ 归档件**一旦写出不再改**（本脚本只写一次）。
3. **头部定点改**：只动 `last_ack` / `更新时间` / `当前任务` / `阻塞` / `已压缩` 这几行。
4. **体积闸门**：≤ 40 000 B / ≤ 300 行（APP-052④）⇒ **写前自检**，超了 ⇒ 不写。
5. **行尾**：活文档**无裸 LF**（全 CRLF 或全 LF，与原文件一致 ⇒ 读入归一化、写回还原）。
6. **纠偏文件只读**：本脚本**绝不**打开 `status/app/CORRECTIONS_APP.md` 写入。
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec174_20261111.md')
BACKUP = os.path.join(REPO, 'results', 'app', '_app432_status_backup.md')

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    raw = open(STATUS, 'rb').read()
    eol = b'\r\n' if b'\r\n' in raw else b'\n'
    text = raw.decode('utf-8').replace('\r\n', '\n')
    before = text

    # ── ① 归档件（write-once，先写）────────────────────────────────
    if os.path.exists(ARCHIVE):
        print('!! 归档件已存在 ⇒ write-once，拒绝覆盖：%s' % ARCHIVE)
        return 2
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)

    # ── ② 头部定点改（只动这几行）──────────────────────────────────
    lines = text.split('\n')
    hdr_idx = {}
    for i, ln in enumerate(lines[:12]):
        for key in ('last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:',
                    '已压缩:'):
            if ln.startswith(key):
                hdr_idx[key] = i
                break
    need = ['last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:']
    miss = [k for k in need if k not in hdr_idx]
    if miss:
        print('!! 头部缺关键行：%s ⇒ 不写' % miss)
        return 2

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines[hdr_idx['last_ack:']] = 'last_ack: APP-098'
    lines[hdr_idx['更新时间:']] = '更新时间: %s' % now

    lines[hdr_idx['当前任务:']] = (
        '当前任务: **巡检无新纠偏**（`last_ack=APP-098`；纠偏文件仍是 97 条 / 最大 APP-097 ⇒ '
        '无编号更大的新条目）｜**本轮修掉 2 个 App 侧真缺陷**：**① 🔴 self_ref 克隆漏「克隆模式」闸门**'
        '（§168 ⑤ 实测 `--tts-voice A` 时 **78/78 句** `voice_kind=\'clone\'` ⇒ 用户选预设 A 却每句都在克隆'
        '⇒ 与 reviewer 2026-11-07 已定口径「preset voice selected => never register clone voices」**冲突**'
        '⇒ 已补闸门：GUI 用 `_clone_enabled`、CLI 用 `_want_clone`（**与姊妹闸门 98cf8fc 同源同口径**）'
        '⇒ **行为级判据 8/8 PASS**（含反证 2/2）｜**② 🔴 开发期 `assert_*.py` 闸门可能随包泄漏**'
        '（§173 ⑥ 下一轮必读项：`pkg_exclude` 只排 `_` 前缀 ⇒ `assert_sec_per_char_calibrated.py` 等 3 个'
        '开发闸门**不会被排除** ⇒ 内含开发机路径 ⇒ 已加 `APP_DEV_ONLY_ASSERT_RE` 排除规则'
        '（`assert_pkg_clean.py` **必须随包** ⇒ 白名单例外）⇒ **判据 13/13 PASS**（含反证 2/2）'
        '｜**既有闸门复跑全绿**（sec_per_char 27/27、app109 34/34、pkg_clean 对 v2.4 0 违规、window 同源 PASS）'
        '｜**未打包 v2.5、未同步任何客户包、未通知用户、未调 MiniMax、未占设备**｜结果见 §174｜'
        '**本条需等 reviewer 复核**')

    lines[hdr_idx['阻塞 / 待用户决定:']] = (
        '阻塞 / 待用户决定: 🔴 **GUI 布局缺陷修复仍未同步进客户包**（只在 dev 树 + 影子包）⇒ '
        '**v2.5 未打包、未同步任何客户包目录**（APP-055 须走打新版本号）⇒ **请 reviewer 裁定**：'
        '立刻修还是随 v2.5 一起出｜🔴 **该缺陷的历史影响「已定界」**（§171：D1 零交付物受影响／'
        '**D2 影响已交付的 rc5**）⇒ **不再是「未评估」**｜🔴 **§3.5 音色归属判据失效**'
        '（三人真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据｜🔴 **§3.6「切段真实发生时的设备开销」'
        '在本素材上结构性不可测**（质心恒 1）⇒ 需 reviewer 裁定是否调聚类阈值/换素材｜'
        '**APP-097 §2-4 的 `_SEC_PER_CHAR` 已由 §172 回填**（de .073／fr .070／es .085／pt .080／it .081／'
        'ru .083；zh/en/ja/ko 未动；守卫阈值只会变松）｜**倍率地板仍未裁定** ⇒ 等 reviewer｜'
        '🔴 **本轮 2 处修复待 reviewer 复核**：① self_ref 克隆闸门（**已改 dev 树**，客户包未动 ⇒ '
        '**已交付的 rc6/rc7 不受影响**——判据已证 `clone_voice.py` 不在包内 ⇒ 该路径为死代码）'
        '② `assert_*.py` 排除规则（**只改打包规则**，不改任何客户包目录）｜'
        '🔴 **C 盘 22.7 G 可用（99 %）** ⇒ v2.5 打包需 10–15 G（**本轮未删任何文件**）｜'
        '**未打包 v2.5、未通知用户**')

    text = '\n'.join(lines)

    # ── ③ 追加 §174 章节（正文全文进归档件，活文档放指针+速查）──────
    sec_body = open(os.path.join(REPO, 'results', 'app',
                                 '_app432_sec174_body.md'),
                    'rb').read().decode('utf-8').replace('\r\n', '\n')
    if not sec_body.startswith('## §174 '):
        print('!! §174 正文文件不以「## §174 」开头 ⇒ 不写')
        return 2

    # 归档件：正文全文（write-once）—— ⚠️ **先算 SHA，但此处不落盘**
    #   （落盘放在**全部自检通过之后** ⇒ 自检不过 ⇒ 归档件也不会被写出来）
    arch_bytes = sec_body.encode('utf-8')
    arch_sha = sha(arch_bytes)
    arch_len = len(arch_bytes)

    # 活文档：指针 + 速查（≤3 行的索引，APP-052④）—— **不含正文全文**
    #   （正文全文只进归档件 ⇒ 活文档体积受控；**与 §171/§172/§173 同一做法**）
    sec_head = sec_body.split('\n')[0]
    pointer = (
        sec_head + '\n'
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec174_20261111.md`'
        '（%d B／块 SHA256 `%s`）｜**归档件逐字节未动**（write-once）。\n'
        '> 🔴 **速查**：**无新 reviewer 纠偏**（97 条／最大 APP-097，SHA `36af1620…`／285 671 B，'
        '**SHA 零改动**、全程只读未改未提交；`last_ack` 仍是 APP-098）｜**修掉 2 个 App 侧真缺陷**：'
        '**① self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 78/78 句 clone ⇒ 补闸门：GUI `_clone_enabled`／'
        'CLI `_want_clone` ⇒ 判据 **8/8 PASS** 含反证 2/2）｜**② `assert_*.py` 可能随包泄漏**'
        '（§173 ⑥ 必读项 ⇒ 加 `APP_DEV_ONLY_ASSERT_RE`，`assert_pkg_clean.py` 白名单例外 ⇒ 判据 **13/13 PASS** '
        '含反证 2/2）｜**既有闸门复跑全绿**（27/27、34/34、0 违规、PASS）｜**16 包逐个只读扫描 ⇒ 已交付包零影响**'
        '（rc6/rc7 的 `clone_voice.py` 不在包内 ⇒ 该路径死代码）｜**未打包 v2.5、未改客户包、'
        '未通知用户、未调 MiniMax、未占设备**｜**本条需等 reviewer 复核**。\n'
        '> 🔴 **证据**：`results/app/app432_self_ref_clone_gate.json`（8/8）／'
        '`results/app/app433_pkg_dev_only_assert_gate.json`（13/13）／'
        '`_app432_self_ref_clone_gate.py`／`_app433_pkg_dev_only_assert_gate.py`／'
        '`status/archive/STATUS_APP_sec174_20261111.md`（§174 正文全文）。\n'
        '\n') % (arch_len, arch_sha)
    text = text.rstrip('\n') + '\n\n' + pointer

    # ── ③b 压缩 §173 活文档块（**正文全文已在归档件里** ⇒ 只留指针+速查）──
    #   🔴 **与 §170→§171→§172 同一做法**（APP-052④ 压缩索引）：
    #     旧章节的**正文**逐字留在 `status/archive/STATUS_APP_sec173_20261111.md`
    #     （**归档件逐字节不动**）⇒ 活文档只留「指针 + 速查」一行。
    #   ⚠️ **不删任何字节**：被移出的正文逐字在归档件里（可核对）。
    i173 = text.find('## §173 ')
    if i173 < 0:
        print('!! 找不到 §173 块 ⇒ 不写')
        return 2
    j173 = text.find('## §174 ')
    if j173 < 0:
        print('!! 找不到 §174 块 ⇒ 不写')
        return 2
    old173 = text[i173:j173]
    # 归档件已在磁盘上（write-once）⇒ 校验它与 §173 的 SHA 声明一致
    arc173 = os.path.join(REPO, 'status', 'archive',
                          'STATUS_APP_sec173_20261111.md')
    if not os.path.isfile(arc173):
        print('!! §173 归档件不在磁盘 ⇒ 不写')
        return 2
    if sha(open(arc173, 'rb').read()) not in old173:
        print('!! §173 归档件 SHA 与活文档声明不一致 ⇒ 不写')
        return 2
    # 压缩块 = 抬头 + 指针行 + 一行速查（**事实不删**：要点全部保留）
    head173 = old173.split('\n')[0]
    new173 = (
        head173 + '\n'
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec173_20261111.md`'
        '（10 835 B／块 SHA256 `2400cc27b26fba6b6ddb71d1cab64e9151fc8595b65a1369aef839e04a0de4a3`）'
        '｜**归档件逐字节未动**（write-once）｜**要点**：修掉头部 **H1–H4**（引用滞后／与 §172 自相矛盾／'
        '「历史影响未评估」而 §171 已定界／磁盘数过期）｜新增**「归档指针可核对性」判据**（32 指针 '
        'OK 25／FAIL 0／7 条早期行「从未声明 SHA」只记信息；反证 3/3 触发）｜既有闸门复跑全绿'
        '（27/27、34/34、0 违规、PASS）｜自踩 3 个判据坑（SHA 归属／「没写 SHA」≠「写了核对不上」／'
        '键名带修饰致假阴性）⇒ **教训：判据写完必须先跑反证组**｜**未打包 v2.5、未改生产代码、'
        '未改客户包、未通知用户、未调 MiniMax、未占设备**｜**本条需等 reviewer 复核**。\n\n')
    text = text[:i173] + new173 + text[j173:]

    # ── ④ 写前自检（体积 / 行数 / 旧正文逐字未变 / 无裸 LF）──────────
    out_bytes = text.encode('utf-8')
    if eol == b'\r\n':
        out_bytes = out_bytes.replace(b'\n', b'\r\n')
    n_lines = out_bytes.count(b'\n') + 1
    if len(out_bytes) > LIMIT_BYTES:
        print('!! 体积超限：%d B > %d B ⇒ **不写**（源文件零改动）'
              % (len(out_bytes), LIMIT_BYTES))
        return 2
    if n_lines > LIMIT_LINES:
        print('!! 行数超限：%d > %d ⇒ **不写**' % (n_lines, LIMIT_LINES))
        return 2
    # 旧正文逐字未变：除**头部定点行** + **§173 压缩块**外，原文必须完全保留
    #   🔴 **§173 压缩块是被允许的唯一例外**（APP-052④ 压缩索引）：
    #     其正文**逐字**在归档件里（SHA 已在上面校验过）⇒ 不是「删内容」。
    #   ⚠️ **不能用「逐行比对」**：压缩块**行数变了** ⇒ 后面所有行号都平移
    #     ⇒ 逐行比会误报一堆「被改动」⇒ 改成**分段比对**。
    old_body = before
    i_old = old_body.find('## §173 ')
    if i_old < 0:
        print('!! 旧文档找不到 §173 ⇒ 不写')
        return 2
    # 旧文档：§173 之前部分（逐字保留）；§173 之后部分（**旧文档里没有** ⇒ 空）
    old_head_part = old_body[:i_old]
    old_tail_part = ''      # §173 是旧文档最后一节
    new_i173 = text.find('## §173 ')
    new_i174 = text.find('## §174 ')
    if new_i173 < 0 or new_i174 < 0 or new_i174 < new_i173:
        print('!! 新文档章节顺序异常 ⇒ 不写')
        return 2
    new_head_part = text[:new_i173]
    new_tail_part = text[new_i174:]
    allowed = set(hdr_idx.values())

    def _diff_lines(a, b):
        """返回 a 中与 b 逐行不同的行号（长度不同则只比公共部分）。"""
        al, bl = a.split('\n'), b.split('\n')
        return [i for i in range(min(len(al), len(bl))) if al[i] != bl[i]]

    head_diff = _diff_lines(old_head_part, new_head_part)
    illegal = [i for i in head_diff if i not in allowed]
    if illegal:
        print('!! 旧正文（§173 之前）被改动（行 %s）⇒ **不写**' % illegal[:10])
        return 2
    # §173 之后：旧文档**没有** ⇒ 新文档多出来的部分必须**全部**是新章节
    if old_tail_part.strip():
        tail_diff = _diff_lines(old_tail_part, new_tail_part)
        if tail_diff:
            print('!! 旧正文尾部被改动 ⇒ **不写**')
            return 2
    # §173 压缩后**要点不丢**
    for kw in ('H1', 'H4', '归档指针可核对性', '反证', '未打包 v2.5'):
        if kw not in new173:
            print('!! §173 压缩块丢了要点「%s」⇒ **不写**' % kw)
            return 2
    # §173 的**正文全文**必须仍在归档件里（逐字）⇒ 不是「删内容」
    #   ⚠️ 归档件**不含**「本节正文已整块逐字归档」那一行（**自指行**：
    #     归档件里放这一行会形成自引用）⇒ 比对时**跳过该行**。
    arc_text = open(arc173, 'rb').read().decode('utf-8')
    missing = []
    for ln in old173.split('\n'):
        s = ln.strip()
        if not s or '已整块逐字归档' in s:
            continue
        if s not in arc_text:
            missing.append(s[:60])
    if missing:
        print('!! §173 原正文不在归档件里（%d 行）⇒ **不写**' % len(missing))
        for m in missing[:3]:
            print('     - %s' % m)
        return 2
    # 行尾必须与**原文件一致**（本文件是纯 LF ⇒ 输出也必须纯 LF）
    #   ⚠️ **真不变量** = 「与原文件同款」，不是「无裸 LF」（§172 教训：
    #   断言「CRLF 个数不变」是**伪不变量** ⇒ 把正确改动判成 FAIL）。
    n_crlf_out = out_bytes.count(b'\r\n')
    n_bare_out = out_bytes.count(b'\n') - n_crlf_out
    n_crlf_old = raw.count(b'\r\n')
    n_bare_old = raw.count(b'\n') - n_crlf_old
    if (n_crlf_out > 0) != (n_crlf_old > 0):
        print('!! 行尾风格与原文件不一致（旧 CRLF=%d，新 CRLF=%d）⇒ **不写**'
              % (n_crlf_old, n_crlf_out))
        return 2
    if n_crlf_old == 0 and n_bare_out == 0:
        print('!! 输出没有换行 ⇒ **不写**')
        return 2
    # 章节数不少
    n_sec_before = len(re.findall(r'(?m)^## §', before))
    n_sec_after = len(re.findall(r'(?m)^## §', text))
    if n_sec_after <= n_sec_before:
        print('!! 章节数未增加 ⇒ **不写**')
        return 2

    # ── ⑤ 落盘（**全部自检通过之后**才写 ⇒ 自检不过 ⇒ 零改动）──────
    #   归档件 write-once：已存在则**逐字节校验**一致才复用，绝不覆盖。
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    shutil.copy2(STATUS, BACKUP)
    if os.path.exists(ARCHIVE):
        got = open(ARCHIVE, 'rb').read()
        if got != arch_bytes:
            print('!! 归档件已存在但内容不同 ⇒ **不写**（write-once 不覆盖）')
            return 2
    else:
        with open(ARCHIVE, 'wb') as f:
            f.write(arch_bytes)
    with open(STATUS, 'wb') as f:
        f.write(out_bytes)

    print('[app432] §174 已写入：%d B／%d 行（限额 %d B／%d 行）'
          % (len(out_bytes), n_lines, LIMIT_BYTES, LIMIT_LINES))
    print('[app432] 归档件：%s（%d B／SHA256 %s）' % (ARCHIVE, arch_len, arch_sha))
    print('[app432] 头部定点改行号：%s；§173 之前改动行：%s（仅头部）'
          % (sorted(allowed), head_diff))
    print('[app432] 章节数 %d ⇒ %d' % (n_sec_before, n_sec_after))
    return 0


if __name__ == '__main__':
    sys.exit(main())
