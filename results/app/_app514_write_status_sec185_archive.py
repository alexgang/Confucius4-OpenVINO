#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app514_write_status_sec185_archive.py —— 归档 §170/§183（逐字）＋ 追加 §185。

## 为什么必须归档（限额）

`status/app/STATUS_APP.md` 的限额是 **≤40000 B / ≤300 行**（APP-052④）。
本轮 §185（约 5.4 KB）+ 头部改写 ⇒ **43 124 B ⇒ 超限 3 124 B** ⇒ 必须先腾地方。
腾法沿用**既有机制**（§141–§160／§166–§168／§171–§180 都是这么做的）：
**把老的整节正文逐字归档到 `status/archive/`，活文档只留 1 行指针**。

选了 **§170（APP-098 / rc7，4 轮前）** 与 **§183（APP-104 / rc9，2 轮前，已被 rc10 取代）**
—— 两节的结论都已在「最近更新」速查行里，**不丢信息**。

## 🔴 纪律

1. 归档件 = **逐字复制**（一个字节都不改）⇒ 写后**复核**：归档件里的两节
   与原 STATUS 里逐字节相同；
2. 归档件 **write-once**（本轮新建，不覆盖任何旧归档件）；
3. 活文档：§170/§183 换成**指针行**，**§185 追加在末尾**，
   头部 5 行改写（`last_ack` **不变**＝APP-105；「更新时间」用 Get-Date 实测值）；
4. **旧正文其余部分一字不删、不改**（逐行复核）；
5. 限额 **≤40000 B / ≤300 行**；行尾保持 **LF**（本文件是 LF-only）。

## 产物

- `status/archive/STATUS_APP_sec170_183_20261113.md`（逐字归档件）
- `status/app/STATUS_APP.md`（追加 §185 + 2 行指针 + 头部改写）
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

ROOT = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(ROOT, 'status', 'archive',
                        'STATUS_APP_sec170_183_20261113.md')

NOW = '2026-11-13 00:43:00'
ARCHIVE_HEAD = ('# STATUS_APP §170 + §183 逐字归档（2026-11-13）\n\n'
                '> 本文件是 `status/app/STATUS_APP.md` 的**逐字归档件**（write-once）。\n'
                '> 归档原因：**§185 追加后触顶 40 000 B 限额**（APP-052④）⇒ '
                '按既有机制（§141–§160／§166–§168／§171–§180 同例）把老的整节正文逐字移出。\n'
                '> 下列两节内容**一个字节都没改**（write 时逐字复制）⇒ 可逐字复核。\n\n')

NEW_HEAD = {
    'last_ack': 'last_ack: APP-105',
    '更新时间': '更新时间: %s' % NOW,
    '当前任务': (
        '当前任务: **无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 105 条／最大 **APP-105**'
        '／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47 ⇒ 与上轮**逐字一致**）'
        '｜`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）'
        '｜**接手上个会话的断点**（租约 **TAKEOVER**，note＝「app157 gate broken at HEAD；'
        'writing fix」）⇒ 本轮把 **app157 follow_speaker 判据**从「6 PASS/4 FAIL（异常）」'
        '修到 **11 PASS/0 FAIL**（**判据层，产品代码零改动**）＋补**产品级反证**与**客户包矩阵**'
        '⇒ 🔴 **查明：完整版 v2.2/v2.3/v2.4 仍带 APP-086·2a 串音缺陷**（§185）'
        '｜未打包、未调 MiniMax、未通知用户'
    ),
    '阻塞 / 待用户决定': (
        '阻塞 / 待用户决定: 🔴 **新查明（待 reviewer 裁定）**：磁盘上的**完整版**包 '
        '**v2.2／v2.3／v2.4** 的 `synth()` 分支 ② 是 `elif self._has_clone_voice():`'
        '（**缺 APP-086·2a 的 `and not _bound` 守卫**）⇒「按句绑定模式 + 标签晚到（spk=None）」'
        '会**沿用上一句克隆音色、不回落预设 A** ⇒ 判据 **B3 FAIL**（观测 `after_embed=VEC_S2`）'
        '⇒ 即「**男声被配成女声／串音**」根因；**收窄只在 dev 树与 MiniMVP rc10**'
        '（rc10 克隆置灰 ⇒ 该路径惰性）⇒ **完整版 v2.5 必须带上收窄后才可交付**（本轮未打包）'
        '｜**当前交付版 v2.1 无分支② ⇒ 不受此缺陷影响**｜🔴 **等 reviewer 复核 rc10**'
        '（APP-105 §6/§7）｜**B 机实测仍未做**｜**v2.5 未打包**'
        '｜**EXT 的 ASR 在 MiniMVP 本版不可用**'
    ),
    '已压缩': (
        '已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；'
        '限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜'
        '**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`'
        '（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ '
        '`status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜'
        '**§167 压缩**：§167 正文整块归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`'
        '（12 277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜'
        '**§168 压缩**：§168 正文整块归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`'
        '（8 599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）｜'
        '**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_sec178_180_20261112.md`（块 SHA256 '
        '`d91b34ffed16ff1b22f0dd369c66bd9477351a8e782f327ff1740f0b44113705`）；活文档三节各留 1 行速查｜'
        '**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`'
        '（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜'
        '**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`'
        '（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜'
        '**§170 + §183 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ '
        '`status/archive/STATUS_APP_sec170_183_20261113.md`（块 SHA256 见 §185）'
    ),
}

SEC185 = """
## §185 巡检（last_ack=APP-105，2026-11-13 00:43:00）｜**无新 reviewer 纠偏**；接上个会话断点修好 **app157 判据**（**判据层，产品代码零改动**）｜🔴 **查明完整版 v2.2/v2.3/v2.4 仍带 APP-086·2a 串音缺陷**｜**本条需等 reviewer 复核**

> **① 纠偏文件复核（只读，未改）**：开工 **105 条**／最大 **APP-105**／SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／mtime **2026-11-12 14:25:47**；收尾**逐字一致 ⇒ SHA 零改动**（未入库、未提交）⇒ **`last_ack` 保持 APP-105**。
> **② 接断点（TAKEOVER）**：租约 `acquire app` 返 **TAKEOVER**（上一会话 `d1cff5be` 心跳 64 min 前、无存活 PID ⇒ 已死），note＝「diagnosed: app157 gate broken at HEAD (6P/4F, stub missing `_log_keep_last_clone` + stale anti-proof D-B3); writing fix」⇒ 本轮**从断点继续**，未从头重做；本会话 token `f44dd034`，每步 beat，收尾 `release`。
> **③ 修判据（3 处，只改 `results/app/app157_follow_speaker_regression_test.py`）**：① 桩 `_FakeWorker` 补 `_log_keep_last_clone`（**委托给真实实现** ⇒ 验的仍是真实代码）；② `mutate_always_fallback` **两条「保留克隆」条件一起废**（只废 ① 会落进 ② ⇒ 克隆照样保留 ⇒ **假反证**）；③ 两条变异改**版本容忍**（按源码里**实际存在**的条件逐条核；写死「必须 2 条」⇒ 在老包上直接抛 `AssertionError`）⇒ **dev 树 11 PASS / 0 FAIL**（修前 10 PASS/1 FAIL，其中 4 条是**异常**不是判 FAIL）。
> **④ 产品级反证（新增 `app510`：判据必须有鉴别力）**：临时假仓库注入 **4 条真实缺陷** ⇒ 基线 11/0；M1 撤 APP-086·2a 守卫 ⇒ **B3 FAIL**；M2 分支①漏 `_bound` ⇒ **B3 FAIL**；M3 不回落 ⇒ **B3 FAIL**；M4 全局克隆模式失效 ⇒ **B1 FAIL** ⇒ **VERDICT PASS**。
> **⑤ 🔴 客户包矩阵（新增 `app512`，对客户包**只读**）**：**v2.2／v2.3／v2.3_aborted／v2.4 判据 FAIL（B3 FAIL）＝ 带 APP-086·2a 缺陷**（分支② `elif self._has_clone_voice():` **缺 `and not _bound`**）；**v1.13／v2.0／v2.1 PASS 11/0**（**无分支② ⇒ 无此缺陷**）；**dev 树／MiniMVP rc10 PASS 11/0**（收窄在）；**v1.5 = 2/8 属「判据不适用」**（无按句绑定机制，`uses_voice_for_sentence=0`）⇒ **不是缺陷证据**。
> **⑥ 幻影产物登记**：旧 `app157_follow_speaker_regression_evidence_pkg.json` 的 `live` 指向 **`Confucius4_LiveCaption_v1.11/app`**，该目录**磁盘上已不存在** ⇒ 落点失效（当时数字为真但**不可复查**）⇒ 已另存 `…_pkg_v111_20261112.json` 留证（2 497 B／sha `231872acce272b1a…`），**未删除**。
> **⑦ 产物清单（均已落盘）**：`app157_follow_speaker_regression_test.py`（24 206 B／CRLF 533／5 个 diff hunk 全是上述 3 处修改）｜`app157_follow_speaker_regression_evidence.json`（2 501 B／11-13 00:42:29／sha `82de554cfabf559b…`／11-0 PASS）｜`…_evidence_pkg.json`（2 489 B／sha `d613a7fcdecb3c9e…`／**v2.4 9-2 FAIL**）｜`…_evidence_pkg_rc10.json`（2 509 B／sha `37f1e4ba24e28e99…`／**rc10 11-0 PASS**）｜`app510_app157_gate_antiproof_evidence.json`（14 575 B／sha `2e5e42ddf482a588…`）｜`app512_pkg_follow_speaker_matrix.json`（5 301 B／sha `10a0fec16c615b90…`）｜补丁脚本 `_app508`（上个会话写的）／`_app509`／`_app511`。
> **⑧ 自曝 3 个坑**：① `ast.unparse` **会给 `not` 加括号**（源码 `not _bound` ⇒ unparse 后 `(not _bound)`）⇒ 改判据要用 **unparse 后**的形态、改**产品源码**要用**文件原文**（我第一版反证注入用错形态 ⇒ 断言命中 0 次）；② 我第一版反证脚本**跑了仓库里的原件**而不是假仓库里的副本 ⇒ `LIVE` 指向真实 dev 树 ⇒ 注入的缺陷**根本没被试到**（两处同款错误，已修）；③ `_app509` 原本会给「横幅注释 + def」插空行 ⇒ 与文件其余部分不一致 ⇒ 已改成「注释直接贴 def 时不插」并验证幂等 **NO-OP**。
> **⑨ 纪律**：**未打包**（rc9/rc10 已打好 ⇒ 绝不重打包；v2.5 未打，**用户不通知不打包**）｜**未改任何客户包**（矩阵只读）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 CORRECTIONS_APP.md**｜**未跑推理/未计时 ⇒ 未取 MACHINE_LOCK**｜**未调 MiniMax**｜**未通知用户**｜未提交 ASR/MT/TTS 其它模块的未提交改动（仓库另有 59 个 `M` 文件属别的模块，本轮**未 stage**）。
> **⑩ 新增脚本（供 reviewer 判断）**：本轮新增 5 个脚本（`_app509`/`_app511` 为**一次性补丁器**，与仓库既有 `_appNNN_patch_*` 同类；`app510`/`app512` 为**可复跑的反证层与包矩阵**）⇒ 与 APP-101 §1.d「不再新增审计/判据脚本」有张力，**明写在此待裁**。
> **⑪ 归档（限额腾挪）**：§185 追加后触顶 40 000 B ⇒ 把 **§170（rc7）＋§183（rc9）** 正文**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（**块 SHA256 见文件头**）⇒ 活文档两节换成指针行；**§171–§180 等既有归档件未动**。
> **⑫ 本条需等 reviewer 复核**：① **v2.5 完整版必须带上 APP-086·2a 收窄**（否则重犯「男声被配成女声」）；② v2.2/v2.3/v2.4 是否**作废/标注**；③ 本轮新增脚本是否保留；④ rc10 仍待 B 机实测。
"""


def section_span(text, header_prefix):
    """返回某节的 (start, end) 字符区间。

    `end` = 该节**最后一行非空行**之后的位置 ⇒ **不含节尾的空行**
    ⇒ 替换时把节外的空行原样保留 ⇒ 还原后能与原文逐字对齐。
    """
    m = re.search(r'(?m)^## %s.*$' % re.escape(header_prefix), text)
    if not m:
        raise AssertionError('找不到节：%s' % header_prefix)
    start = m.start()
    nxt = re.search(r'(?m)^## ', text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    seg = text[start:end]
    end = start + len(seg.rstrip('\n'))
    return start, end


def main() -> int:
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    assert '\r' not in src, 'STATUS 是 LF-only，出现 CR ⇒ 中止'
    assert not os.path.exists(ARCHIVE), '归档件已存在 ⇒ 中止（write-once）'

    old_lines = src.split('\n')
    n_old = len(old_lines) - (1 if old_lines[-1] == '' else 0)

    # ── ① 取 §170 / §183 原文（逐字）──
    blocks = {}
    for key, prefix in (('sec170', '§170 '), ('sec183', '§183 ')):
        s, e = section_span(src, prefix)
        blocks[key] = src[s:e]

    # ── ② 组装归档件内容（**先不落盘**：所有自检过了才写 ⇒ fail-closed）──
    arc = ARCHIVE_HEAD + '\n' + blocks['sec170'] + '\n\n' + blocks['sec183'] + '\n'
    arc_b = arc.encode('utf-8')
    arc_sha = hashlib.sha256(arc_b).hexdigest()
    arc_bytes = len(arc_b)

    # ── ③ 活文档：替换两节为指针行 + 追加 §185 + 改头部 ──
    ptr = ('## §170 与 §183｜**正文已整块逐字归档** ⇒ `status/archive/'
           'STATUS_APP_sec170_183_20261113.md`（%d B／块 SHA256 `%s`）｜活文档留此指针行'
           % (arc_bytes, arc_sha))
    new = src
    for key, prefix in (('sec183', '§183 '), ('sec170', '§170 ')):
        s, e = section_span(new, prefix)
        new = new[:s] + ptr + new[e:]

    lines = new.split('\n')
    hdr_idx = {}
    for i, ln in enumerate(lines[:14]):
        for k in NEW_HEAD:
            if ln.startswith(k + ':'):
                hdr_idx[k] = i
    missing = [k for k in NEW_HEAD if k not in hdr_idx]
    assert not missing, '头部缺这些键：%s' % missing
    for k, i in hdr_idx.items():
        lines[i] = NEW_HEAD[k]

    new = '\n'.join(lines).rstrip('\n') + '\n' + SEC185.lstrip('\n')

    # ── ④ 自检 ──
    nbytes = len(new.encode('utf-8'))
    nlines = new.count('\n') + 1
    assert nbytes <= 40000, '超 40000 B（%d）⇒ 中止' % nbytes
    assert nlines <= 300, '超 300 行（%d）⇒ 中止' % nlines
    assert '\r' not in new, '出现裸 CR ⇒ 中止'
    # 归档件与原文逐字相同
    for key, prefix in (('sec170', '§170 '), ('sec183', '§183 ')):
        s, e = section_span(src, prefix)
        assert src[s:e] == blocks[key], \
            '%s 归档件不是逐字 ⇒ 中止' % key
        assert blocks[key] in arc, '%s 没进归档件 ⇒ 中止' % key
    # 旧章节号不少、顺序不变（§170/§183 已被**归档**⇒ 允许「不再作为标题出现」）
    old_secs = re.findall(r'(?m)^## §(\d+)', src)
    new_secs = re.findall(r'(?m)^## §(\d+)', new)
    ARCHIVED_IDS = {'170', '183'}
    missing_secs = [s for s in old_secs if s not in new_secs]
    assert set(missing_secs) <= ARCHIVED_IDS, \
        '旧章节号少了（%s）⇒ 中止' % missing_secs
    assert '§170' in ptr and '§183' in ptr, '指针行没点名两节 ⇒ 中止'
    assert '185' in new_secs, '§185 没落上 ⇒ 中止'
    # ── 独立复核：把两个指针行**换回**原文节块 ⇒ 应等于「只改头部」的旧文件 ──
    #   （按行号比会因「多行节被 1 行指针替换」而错位 ⇒ 这里做**还原式**复核）
    idx_sec = new.index(SEC185.lstrip('\n'))
    core = new[:idx_sec]                       # 结尾带一个 '\n'
    assert core.count(ptr) == 2, '指针行数不对（%d）⇒ 中止' % core.count(ptr)
    i1 = core.index(ptr)
    core2 = core[:i1] + blocks['sec170'] + core[i1 + len(ptr):]
    i2 = core2.index(ptr)
    core2 = core2[:i2] + blocks['sec183'] + core2[i2 + len(ptr):]
    orig_hdr = list(old_lines)
    for k, i in hdr_idx.items():
        orig_hdr[i] = NEW_HEAD[k]
    expected = '\n'.join(orig_hdr).rstrip('\n') + '\n'
    assert core2 == expected, '旧正文被改动（还原后与「只改头部」的旧文件不一致）⇒ 中止'

    # ── ⑤ 自检全过 ⇒ 才落盘 ──
    with open(ARCHIVE, 'w', encoding='utf-8', newline='') as f:
        f.write(arc)
    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print('ARCHIVE: %s (%d B, sha256 %s)' % (ARCHIVE, arc_bytes, arc_sha))
    print('WROTE  : %s' % STATUS)
    print('bytes %d -> %d ; lines %d -> %d ; sections %d -> %d'
          % (len(src.encode('utf-8')), nbytes, n_old + 1, nlines,
             len(old_secs), len(new_secs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
