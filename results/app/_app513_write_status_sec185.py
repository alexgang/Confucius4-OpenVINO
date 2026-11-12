#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app513_write_status_sec185.py —— 在 `status/app/STATUS_APP.md` **追加** §185（定点写入）。

## 纪律（🔴 逐条自检，写后必验）

1. **只动头部 4 行**（`last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`）
   ＋ **末尾追加** `## §185 …`；**旧正文一字不删、不改**；
2. `last_ack` **不变**（本轮**无新 reviewer 纠偏** ⇒ 仍是 APP-105）
   ⇒ 绝不把 `last_ack` 写成 APP-106（那是 reviewer 的编号，不是我的）；
3. 「更新时间」用 **Get-Date 实测值**（`2026-11-13 00:43:00`），禁止推算；
4. 限额 **≤40000 B / ≤300 行**（APP-052④）⇒ 写后自检；
5. 行尾保持 **LF**（本文件是 LF-only）⇒ 写后自检「无裸 CR」；
6. **不碰** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。

## 写后自检（全部过才写盘）

- 旧正文（除头部 4 行外）**逐字节相同**；
- §N 章节数**不少**（§164…§184 全部还在）；
- 字节数 ≤40000、行数 ≤300；
- 无裸 CR。
"""

from __future__ import annotations

import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'

NOW = '2026-11-13 00:43:00'

NEW_HEAD = {
    'last_ack': 'last_ack: APP-105',
    '更新时间': '更新时间: %s' % NOW,
    '当前任务': (
        '当前任务: **无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 105 条／最大 **APP-105**'
        '／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47 ⇒ 与上一轮**逐字一致**）'
        '｜`last_ack` 保持 **APP-105**（不变）｜**接手上一个会话的断点**（TAKEOVER，note='
        '「app157 gate broken at HEAD；writing fix」）⇒ 本轮把 **app157 follow_speaker 判据**'
        '从「6 PASS/4 FAIL（异常）」修到 **11 PASS/0 FAIL**（**判据层，产品代码零改动**）'
        '＋新增**产品级反证**与**客户包矩阵** ⇒ 🔴 **查出：完整版 v2.2/v2.3/v2.4 仍带 '
        'APP-086·2a 串音缺陷**（详见 §185）｜未打包、未调 MiniMax、未通知用户'
    ),
    '阻塞 / 待用户决定': (
        '阻塞 / 待用户决定: 🔴 **新查明（待 reviewer 裁定）**：磁盘上的**完整版**包 '
        '**v2.2／v2.3／v2.4** 的 `synth()` 分支 ② 是 `elif self._has_clone_voice():`'
        '（**缺 APP-086·2a 的 `and not _bound` 守卫**）⇒ 「按句绑定模式 + 标签晚到（spk=None）」'
        '会**沿用上一句克隆音色、不回落预设 A** ⇒ 判据 **B3 FAIL**（观测 `after_embed=VEC_S2`）'
        '⇒ 即「**男声被配成女声／串音**」根因；**收窄只在 dev 树与 MiniMVP rc10**'
        '（rc10 克隆置灰 ⇒ 该路径惰性）⇒ **完整版 v2.5 必须带上收窄后才可交付**'
        '（**本轮未打包**）｜**当前交付版 v2.1 不带分支 ② ⇒ 不受此缺陷影响**'
        '｜🔴 **等 reviewer 复核 rc10**（APP-105 §6/§7）｜**B 机实测仍未做**'
        '｜**v2.5 未打包**｜**EXT 的 ASR 在 MiniMVP 本版不可用**'
    ),
}

SEC = """
## §185 巡检（last_ack=APP-105，2026-11-13 00:43:00）｜**无新 reviewer 纠偏**；接上一会话断点修好 **app157 判据**（**判据层，产品代码零改动**）｜🔴 **查出完整版 v2.2/v2.3/v2.4 仍带 APP-086·2a 串音缺陷**｜**本条需等 reviewer 复核**

> **① 纠偏文件复核（只读，未改）**：开工 105 条／最大 **APP-105**／SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／mtime **2026-11-12 14:25:47**；收尾**逐字一致 ⇒ SHA 零改动**（未入库、未提交）⇒ **`last_ack` 保持 APP-105**（不写 APP-106：那是 reviewer 的编号）。
> **② 接断点（TAKEOVER）**：租约 `acquire app` 返 **TAKEOVER**（上一会话 `d1cff5be` 心跳 64 min 前、无存活 PID ⇒ 已死），note＝「diagnosed: app157 gate broken at HEAD (6P/4F, stub missing `_log_keep_last_clone` + stale anti-proof D-B3); writing fix」⇒ 本轮**从断点继续**，未从头重做；本会话 token `f44dd034`，每步 beat，收尾 `release`。
> **③ 修判据（3 处，全部只改 `results/app/app157_follow_speaker_regression_test.py`）**：① 桩 `_FakeWorker` 补 `_log_keep_last_clone`（**委托给真实实现** ⇒ 验的仍是真实代码）；② `mutate_always_fallback` **两条「保留克隆」条件一起废**（只废 ① 会落进 ② ⇒ 克隆照样保留 ⇒ **假反证**）；③ 两条变异改**版本容忍**（按源码里**实际存在**的条件逐条核；写死「必须 2 条」⇒ 在老包上直接抛 `AssertionError`）。⇒ **结果：dev 树 11 PASS / 0 FAIL**（修前 10 PASS/1 FAIL，其中 4 条是异常不是判 FAIL）。
> **④ 产品级反证（新增 `app510`，判据必须有鉴别力）**：临时假仓库里注入 **4 条真实缺陷** ⇒ 基线 11/0；M1 撤 APP-086·2a 守卫 ⇒ **B3 FAIL**；M2 分支①漏 `_bound` ⇒ **B3 FAIL**；M3 不回落 ⇒ **B3 FAIL**；M4 全局克隆模式失效 ⇒ **B1 FAIL** ⇒ **VERDICT PASS**（`app510_app157_gate_antiproof_evidence.json` 14 575 B／sha `2e5e42ddf482a588…`）。
> **⑤ 🔴 客户包矩阵（新增 `app512`，只读客户包）**：**v2.2 / v2.3 / v2.3_aborted / v2.4 判据 FAIL（B3 FAIL）＝ 带 APP-086·2a 缺陷**（分支② `elif self._has_clone_voice():` **缺 `and not _bound`**）；**v1.13 / v2.0 / v2.1 PASS 11/0**（**无分支② ⇒ 无此缺陷**）；**dev 树 / MiniMVP rc10 PASS 11/0**（收窄在）；**v1.5 = 2/8 属「判据不适用」**（无按句绑定机制，`uses_voice_for_sentence=0`），**不是缺陷证据**。
> **⑥ 幻影产物登记**：旧 `app157_follow_speaker_regression_evidence_pkg.json` 的 `live` 指向 **`Confucius4_LiveCaption_v1.11/app`**，该目录**磁盘上已不存在** ⇒ 落点失效（当时数字为真但**不可复查**）⇒ 已另存为 `…_pkg_v111_20261112.json` 留证（2 497 B／sha `231872acce272b1a…`），未删除。
> **⑦ 产物清单**（均已落盘）：`results/app/app157_follow_speaker_regression_test.py`（24 206 B／CRLF 533／sha `…`，5 个 diff hunk 全是上述 3 处修改）｜`app157_follow_speaker_regression_evidence.json`（2 501 B／11-13 00:42:29／sha `82de554cfabf559b…`／11-0 PASS）｜`…_evidence_pkg.json`（2 489 B／sha `d613a7fcdecb3c9e…`／**v2.4 9-2 FAIL**）｜`…_evidence_pkg_rc10.json`（2 509 B／sha `37f1e4ba24e28e99…`／**rc10 11-0 PASS**）｜`app510_app157_gate_antiproof_evidence.json`（14 575 B）｜`app512_pkg_follow_speaker_matrix.json`（5 301 B／sha `10a0fec16c615b90…`）｜补丁脚本 `_app508`（上一会话写的）／`_app509`／`_app511`。
> **⑧ 自曝 3 个坑**：① `ast.unparse` **会给 `not` 加括号**（源码里是 `not _bound`、unparse 后是 `(not _bound)`）⇒ 改判据时**必须用 unparse 后的形态**、改**产品源码**时必须用**文件原文**（我第一版反证注入用错了形态 ⇒ 断言命中 0 次）；② 我第一版反证脚本**跑了仓库里的原件**而不是假仓库里的副本 ⇒ `LIVE` 指向真实 dev 树 ⇒ 注入的缺陷**根本没被试到**（两处同款错误，已修）；③ `_app509` 原本会给「横幅注释 + def」插空行 ⇒ 与文件其余部分不一致 ⇒ 已改成「注释直接贴 def 时不插」并验证幂等 **NO-OP**。
> **⑨ 纪律**：**未打包**（rc9/rc10 已打好 ⇒ 绝不重打包；v2.5 未打，**用户不通知不打包**）｜**未改任何客户包**（矩阵只读）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 CORRECTIONS_APP.md**｜**未跑推理/未计时 ⇒ 未取 MACHINE_LOCK**｜**未调 MiniMax**｜**未通知用户**｜未提交 ASR/MT/TTS 其它模块的未提交改动（仓库另有 59 个 `M` 文件属别的模块，本轮**未 stage**）。
> **⑩ 新增脚本说明（供 reviewer 判断）**：本轮新增 5 个脚本（`_app509`/`_app511` 为**一次性补丁器**，与仓库既有 `_appNNN_patch_*` 同类；`app510`/`app512` 为**可复跑的反证层与包矩阵**）⇒ 与 APP-101 §1.d「不再新增审计/判据脚本」有张力，**明写在此待裁**。
> **⑪ 本条需等 reviewer 复核**：① **v2.5 完整版必须带上 APP-086·2a 收窄**（否则重犯「男声被配成女声」）；② v2.2/v2.3/v2.4 是否**作废/标注**；③ 本轮新增脚本是否保留；④ rc10 仍待 B 机实测。
"""


def main() -> int:
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    assert '\r' not in src, 'STATUS 是 LF-only 文件，出现 CR ⇒ 中止'

    lines = src.split('\n')
    old_body = list(lines)

    # ── ① 改头部 4 行 ──
    hdr_idx = {}
    for i, ln in enumerate(lines[:12]):
        for key in NEW_HEAD:
            if ln.startswith(key + ':'):
                hdr_idx[key] = i
    missing = [k for k in NEW_HEAD if k not in hdr_idx]
    assert not missing, '头部缺这些键：%s' % missing
    for k, i in hdr_idx.items():
        lines[i] = NEW_HEAD[k]

    # ── ② 追加 §185 ──
    body = '\n'.join(lines).rstrip('\n')
    new = body + '\n' + SEC.lstrip('\n')

    # ── ③ 自检 ──
    new_lines = new.split('\n')
    hdr_lo = min(hdr_idx.values())
    hdr_hi = max(hdr_idx.values())
    # 头部**之前**逐行相同
    assert new_lines[:hdr_lo] == old_body[:hdr_lo], '头部之前被改动 ⇒ 中止'
    # 头部**之后**到旧文件末尾，逐行相同（新增内容只允许出现在最末尾）
    # 🔴 old_body 末元素是「文件末尾换行」切分产生的 '' ⇒ 比时**两端都去掉**
    n_old = len(old_body) - (1 if old_body[-1] == '' else 0)
    assert new_lines[hdr_hi + 1:n_old] == old_body[hdr_hi + 1:n_old], \
        '旧正文被改动 ⇒ 中止'
    # 头部 4 行是新值
    for k, i in hdr_idx.items():
        assert new_lines[i] == NEW_HEAD[k], '头部 %s 没写成新值 ⇒ 中止' % k
    # 新增内容只出现在末尾（§185 块）
    tail_new = new_lines[n_old:]
    assert any(l.startswith('## §185') for l in tail_new), '末尾没接上 §185 ⇒ 中止'
    # §N 章节不少
    old_secs = re.findall(r'^## §(\d+)', src, re.M)
    new_secs = re.findall(r'^## §(\d+)', new, re.M)
    assert new_secs[:len(old_secs)] == old_secs, '旧章节顺序/数量变了 ⇒ 中止'
    assert '185' in new_secs, '§185 没落上 ⇒ 中止'
    # 限额
    nbytes = len(new.encode('utf-8'))
    nlines = new.count('\n') + 1
    assert nbytes <= 40000, '超出 40000 B 限额（%d）⇒ 中止' % nbytes
    assert nlines <= 300, '超出 300 行限额（%d）⇒ 中止' % nlines
    assert '\r' not in new, '出现裸 CR ⇒ 中止'

    with open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print('WROTE %s' % STATUS)
    print('bytes %d -> %d ; lines %d -> %d ; sections %d -> %d'
          % (len(src.encode('utf-8')), nbytes, src.count('\n') + 1, nlines,
             len(old_secs), len(new_secs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
