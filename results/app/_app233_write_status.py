#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 写 `status/app/STATUS_APP.md` 的 **§233** 章节 + 更新两处表行。

## 🔴 本轮性质
**待命轮 + TAKEOVER 接续**：六通道复核 ⇒ **无新 App 纠偏** ⇒ `last_ack` 仍 **APP-133**
（**值不变**）；但上一会话（token `b1933ada`）在「已核实 6 通道为空、已找到 4 处真缺陷、
正在核对事实」时**死掉**（last_beat 11-24 23:50:08，108 min 前）⇒ 本轮**从断点继续**。

## 🔴 写前真不变量（全部在内存新文本上跑；FAIL ⇒ 零改动）
1. `last_ack` 唯一且**值不变**（APP-133）；
2. 头部「更新时间」换成 **`Get-Date` 实测值**（本轮只取**一次**，写后复核不再取 ⇒ 避免跨秒假 FAIL）；
3. 旧章节（§135–§232）**逐字节不变**（只在文末追加 §233）；
4. 「最近更新」块**只插入一条**（旧的**下移未删**）；
5. 两处表行替换**各唯一命中**（先断言唯一，再替换）；
6. 写后仍 ≤ 40 000 B／≤ 300 行（APP-052④／APP-049 硬限额）；
7. **还原式复核**：把本轮的新增/替换**按编辑表反向撤销** ⇒ 逐字节等于写前文件。

## 🔴 写文件三件套
备份 → 写前真不变量＋还原式复核 → 临时文件 → `os.replace` ⇒ 写后**另起脚本**复核。
"""
from __future__ import annotations

import datetime
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMPANION = os.path.join(
    REPO, 'status', 'app', 'STATUS_APP_sec233_detail_20261125.md')

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    raw = open(STATUS, 'rb').read()
    print('[before] %d B / %d B；%d 行' % (len(raw), LIMIT_BYTES, raw.count(b'\n')))

    # ── 取「更新时间」实测值（**只取一次**）────────────────────────
    now = datetime.datetime.now()
    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    print('[stamp ] 更新时间 = %s（Get-Date 实测，只取一次）' % stamp)

    text = raw.decode('utf-8')

    # ══ 编辑表（每条都记 old/new，供还原式复核）══════════════════
    edits = []

    def rep(tag, old, new, count=1):
        """登记一处替换（唯一命中由调用方保证）。"""
        edits.append((tag, old, new))

    # ── E1：头部「更新时间」──────────────────────────────────────
    m = re.search(r'更新时间: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}',
                  text)
    assert m, '未找到「更新时间」行'
    old_ts = m.group(0)
    new_ts = '更新时间: ' + stamp
    assert text.count(old_ts) == 1, '「更新时间」不唯一'
    rep('E1 更新时间', old_ts, new_ts)

    # ── E2：「客户包目录」行：当前交付版 v2.1 ⇒ v2.6 ──────────────
    old_row23 = [l for l in text.split('\n')
                 if l.startswith('| 客户包目录 |')]
    assert len(old_row23) == 1, '「客户包目录」行不唯一：%d' % len(old_row23)
    old_row23 = old_row23[0]
    new_row23 = (
        '| 客户包目录 | 🟢 **当前交付版 = `Confucius4_LiveCaption_v2.6`**'
        '（**已签 `ACCEPTED.json`**：`version=2.6`／`accepted_at=2026-11-24 18:26:21`／'
        '`corrections=[APP-129,130,131,132,133,123]`／`ext=v0.4.21(b2a4978)`／'
        '`n_production_modules=33`／`code_fingerprint=1a3a849f…`）'
        '｜ 🔴 **v2.2 = 带 APP-086·2a 缺陷、不能交付**（reviewer 11-13 grep 复核 '
        '`Confucius4_LiveCaption_v2.4\\app\\tts_worker.py:1741` = '
        '`elif self._has_clone_voice():`，**缺 `and not _bound`** ⇒ 按句绑定 + 标签晚到会'
        '**沿用上一句克隆音色（串音）**；**目录保留不删**，作废还是标注**等用户决定**）'
        '｜ 🔴 **带缺陷的包共 10 个**：完整版 **v2.2／v2.3／v2.3_aborted／v2.4** ＋ '
        'MiniMVP **v1.0／rc1／rc2／rc3／rc4／rc5**（**目录一律保留不删**；'
        '本轮已**独立复核** v2.1／v2.5／v2.6 **不含**该 elif 行 ⇒ 判定成立）'
        '｜ 🔴 **v2.6 本轮如实登记 2 处包内缺陷（均已修开发树，未改包）**：'
        '① README 双标题（`## v2.6 改动说明` 出现 2 次）② `app/MANIFEST.json` 的 '
        '`version=2.5`（与目录名不符）⇒ 见本文件 §233 | '
        '`Confucius4_LiveCaption_v2.6/ACCEPTED.json` → `version` / `accepted_at` / '
        '`corrections` / `ext` / `n_production_modules`；'
        '缺陷判定见本文件 §191 ⑤（`results/app/app522_gate4_fallback_scope_evidence.json`）；'
        'v2.6 包内缺陷见本文件 §233 §3 |'
    )
    rep('E2 客户包目录行', old_row23, new_row23)

    # ── E3：「完整版 v2.5（本轮交付…）」行 ⇒ v2.6 ─────────────────
    old_row24 = [l for l in text.split('\n')
                 if l.startswith('| **完整版 v2.5（本轮交付，「全集」形态）** |')]
    assert len(old_row24) == 1, '「完整版 v2.5」行不唯一：%d' % len(old_row24)
    old_row24 = old_row24[0]
    new_row24 = (
        '| **完整版 v2.6（当前交付，「全集」形态）** | 🟢 **目录已出、已签 `ACCEPTED.json`、'
        '**未打 zip**（用户长期规则：**不通知 ⇒ 不打包**）：'
        'ASR＝R2T2 1.7B **＋** Qwen3-ASR 0.6B stateful INT8（可选）｜'
        'MT＝Hy-MT2 **INT8-CW**（默认，INT4 保留可选）｜TTS＝**OV（出厂默认，未改）＋ '
        'NVIDIA CUDA（手动选）**｜**10 语种**｜EXT **v0.4.21（`b2a4978`）**'
        '｜**保留背景音（bgkeep）＋ Demucs 分离模型**进完整版（默认分离设备 **GPU.0(FP32)**）'
        '｜`preset_A.wav` **在包**、**`preset_B.wav` 不在包**（等用户抽听点头，APP-116 §2；'
        '回转写 CER 0.0048／WER 0.0，与预设 A 逐项相等）｜**26 156 520 495 B / 48 792 文件**'
        '（本轮 python walk 实测）｜**不含**录音/同事音色/克隆音色/babelvox 样本｜'
        '🔴 **出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL**（OV 集显追不上）⇒ '
        '**等用户裁定**默认摆放 | '
        '`Confucius4_LiveCaption_v2.6/ACCEPTED.json` → `version=2.6` / `accepted_at` / '
        '`corrections` / `ext`；包规模＝本轮 python walk 实测（48 792 文件 / 26 156 520 495 B）；'
        '`results/app/app118_pkg_size.json`（v2.5 规模）；`app118_lang10_evidence.json` → '
        '`pass=10 fail=0`；`app118_ext_smoke_evidence.json` → `pass=7 fail=0`；本文件 §228 |'
    )
    rep('E3 完整版行', old_row24, new_row24)

    # ── E4：「客户包 zip」行：当前交付版仍是 v2.1 ⇒ 改为「完整版无 zip；发客户发 v1.1.1.zip」
    old_row25 = [l for l in text.split('\n') if l.startswith('| 客户包 zip |')]
    assert len(old_row25) == 1, '「客户包 zip」行不唯一：%d' % len(old_row25)
    old_row25 = old_row25[0]
    new_row25 = (
        '| 客户包 zip | 🔴 **完整版 v2.x 历来无 zip**（用户规则「不通知 ⇒ 不打包」）⇒ '
        '**v2.6 目录已签 ACCEPTED 但没有 zip**；**发客户的是 MiniMVP `v1.1.1.zip`**'
        '（**5 212 403 155 B**／2026-11-23 10:31／10 881 文件）'
        '（🔴 **旧 `v1.1.zip`（5 212 356 737 B／11-22 16:51）不自证** ⇒ **不要发旧的那个**）'
        '｜ 🔴 **v2.2 zip 不得再当候选交付**（**11 233 149 299 B**／SHA `ea5c5c85…`／'
        '2026-11-02 01:54:03／14 317 文件 ⇒ **带 APP-086·2a 缺陷**，见上行「客户包目录」）'
        '｜ **v2.1 zip 保留不删**（**2026-11-01 20:38:13** / **11 233 135 359 B** / '
        'SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）'
        '；**v2.0 首包（17:49 / SHA `8198924f…`）保留不删**'
        '｜ MiniMVP **rc10** zip `shared\\minimvp\\…rc10_perftest.zip` **5 926 048 165 B**'
        '（11-12 16:49:06）（reviewer 11-13 09:00–09:05 已独立复核通过 ⇒ 直接交 B 机） | '
        'v1.1.1 zip 磁盘实测（11-25 01:5x，`Confucius4_LiveCaption_MiniMVP_v1.1.1.zip`）；'
        '`results/app/DELIVERY_2.1.json` → `sha256` / `bytes` / `mtime`；'
        'rc10 zip 磁盘实测（11-13 09:29:32）；本文件 §191 ⑧ |'
    )
    rep('E4 客户包 zip 行', old_row25, new_row25)

    # ── E5：「最近更新」块插入一条（旧的**下移未删**）──────────────
    anchor = '> 🔴 2026-11-24 22:02:37 ｜ **待命轮：六通道复核 ⇒ 仍无新 App 纠偏**'
    assert text.count(anchor) == 1, '「最近更新」锚点不唯一'
    new_update = (
        '> 🔴 ' + stamp + ' ｜ **待命轮 ＋ TAKEOVER 接续**：六通道复核 ⇒ **仍无新 App 纠偏**'
        '（局域网 130 条／max APP-133／SHA `2db65bf1…`／440 181 B／mtime 11-24 13:56:42；'
        'QQ 收件箱最新 App 封仍 = **APP-133**＝已执行，其后仅 **H-028 [MT]**'
        '（10:11:12Z，正文明确「App 接入等本条验收后另发」⇒ **不据此动 App 代码**）；'
        'spam 0；trash 1（无关旧件）；根 `CORRECTIONS.md` max **C-135**；'
        '`shared/NOTICE*` 仍 ≤11-05；agent-mail `not_bound`；全库 `APP-134+` 命中 0）'
        '⇒ **`last_ack` 仍 APP-133**（值不变）｜🟢 **闭合上一会话遗留的 4 处真缺陷**'
        '（已逐条独立复核）：① **STATUS_APP.md 只剩 196 B 余量**⇒ 已压缩（39 804 → **24 998 B**，'
        '余量 **15 002 B**）② **v2.6 README 双标题** ⇒ 已修开发树 `sync_c172`（真包未动）'
        '③ **v2.6 `app/MANIFEST.json` 的 `version=2.5`** ⇒ 已修开发树 `sync_c172`'
        '（真包未动）④ **入库的 app170 证据与实包不符** ⇒ 已刷新（逐字节对齐）｜'
        '🔴 **如实登记**：`results/app/app231_pack_lock_events.jsonl` **不存在且未入库**'
        '（4 处把它当证据指针）⇒ 属**运行时产物**，**不伪造空文件**；'
        '`Confucius4_LiveCaption_v2.6.staging` 残留 **25 GB**（**未删**，删属破坏性⇒待授权）'
        '｜🟢 独立复核 **17/17 ＋ 16/16 ＋ 19/19 ＋ 23/23 全 PASS**（各含反证组）｜'
        '🟢 **未打包 zip**／未改任何客户包／未跑推理·计时（**未取 MACHINE_LOCK**）／'
        '未调 MiniMax／未连 B 机／**未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜'
        '**本条需等 reviewer 复核**\n'
    )
    rep('E5 最近更新', anchor, new_update + anchor)

    # ── E6：文末追加 §233 标题行 ＋ 指针行 ────────────────────────
    #    ⚠️ 标题行**不带**前导 `\n`（拼接时已加一个）⇒ 否则还原式复核会多 1 字节。
    sec233_title = (
        '## §233 待命轮（**六通道复核 ⇒ 无新 App 纠偏**，`last_ack` 仍 **APP-133**）'
        '｜🔴 **接续上一会话（TAKEOVER）并闭合其遗留的 4 处真缺陷**'
        '｜🟢 **修掉「STATUS 只剩 196 B 余量」这个结构性阻塞**'
        '｜🟢 **修掉 v2.6 包两处真缺陷（改开发树，真包未动）**'
        '｜🔴 **如实登记 3 处未修项**｜**本条需等 reviewer 复核**\n'
    )
    sec233_pointer = (
        '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec233_detail_20261125.md`**'
        '（含 §0 六通道逐通道证据、§1 TAKEOVER 交接、§2 四处真缺陷逐条根因与修法、'
        '§3 交付面只读复核、§4 未修项如实登记、§5 独立复核与反证组、§6 纪律自查、'
        '§7 下一轮）\n'
    )

    # ══ 应用编辑 ════════════════════════════════════════════════
    new_text = text
    for tag, old, new in edits:
        cnt = new_text.count(old)
        assert cnt == 1, '[%s] 命中 %d 次（应为 1）' % (tag, cnt)
        new_text = new_text.replace(old, new, 1)
    new_text = new_text.rstrip('\n') + '\n' + sec233_title + sec233_pointer
    new_raw = new_text.encode('utf-8')

    # ══ 写前真不变量 ════════════════════════════════════════════
    checks = []

    def chk(name, cond, detail=''):
        checks.append((name, bool(cond)))
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                               ('｜' + detail) if detail else ''))

    print('[pre-write] 真不变量：')
    # 1) last_ack 唯一且不变
    la_old = re.findall(r'last_ack:\s*APP-(\d+)', text)
    la_new = re.findall(r'last_ack:\s*APP-(\d+)', new_text)
    chk('last_ack 唯一且仍 = APP-133', la_old == la_new == ['133'],
        'old=%s new=%s' % (la_old, la_new))
    # 2) 旧章节逐字节不变：§135–§232 的标题行全部仍在，且旧正文块未被改
    old_secs = re.findall(r'^## §(\d+)', text, re.M)
    new_secs = re.findall(r'^## §(\d+)', new_text, re.M)
    chk('§135–§232 全在（未删任何旧节）',
        all(s in new_secs for s in old_secs), 'old=%d new=%d'
        % (len(old_secs), len(new_secs)))
    chk('新增的节号只有 233', set(new_secs) - set(old_secs) == {'233'},
        str(sorted(set(new_secs) - set(old_secs))))
    # 3) 写前备份里除 5 处编辑外，其余部分逐字保留
    chk('「最近更新」旧条目**下移未删**',
        text.count('2026-11-24 22:02:37 ｜ **待命轮：六通道复核 ⇒ 仍无新 App 纠偏**') == 1
        and new_text.count('2026-11-24 22:02:37 ｜ **待命轮：六通道复核 ⇒ 仍无新 App 纠偏**') == 1)
    # 4) 体积上限
    chk('≤ %d B' % LIMIT_BYTES, len(new_raw) <= LIMIT_BYTES, '%d B' % len(new_raw))
    chk('≤ %d 行' % LIMIT_LINES, new_raw.count(b'\n') <= LIMIT_LINES,
        '%d 行' % new_raw.count(b'\n'))
    # 5) 还原式复核：把 5 处编辑 + 追加**反向撤销** ⇒ 逐字节等于写前文件
    restored = new_text
    for tag, old, new in reversed(edits):
        assert restored.count(new) == 1, '[还原] %s 命中异常' % tag
        restored = restored.replace(new, old, 1)
    restored = restored.rstrip('\n')
    # 去掉追加的 §233（标题行＋指针行）
    restored = restored[:restored.rfind('\n## §233')]
    restored = restored + '\n'
    chk('还原式复核＝逐字节等于写前文件', restored == text,
        '%d vs %d B' % (len(restored.encode('utf-8')), len(raw)))
    # 6) 唯一命中断言（表行各 1 次）
    for tag, old, new in edits:
        chk('[%s] 写前唯一命中' % tag, text.count(old) == 1,
            'count=%d' % text.count(old))
    # 7) 不含控制字符
    chk('新文本无孤立控制字符',
        not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', new_text))
    # 8) 头部索引行仍在
    chk('头部「已压缩」索引仍存在', '已压缩' in new_text)

    if not all(c[1] for c in checks):
        print('[ABORT] 真不变量有 FAIL ⇒ 零改动')
        return 1

    # ══ 备份 → 写盘 ═════════════════════════════════════════════
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app233_sec233')
    shutil.copy2(STATUS, bak)
    print('[backup] %s（%d B）' % (bak, os.path.getsize(bak)))

    tmp = STATUS + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    print('[write ] %d B / %d B（余量 %d B）；%d 行'
          % (len(new_raw), LIMIT_BYTES, LIMIT_BYTES - len(new_raw),
             new_raw.count(b'\n')))
    print('SHA256 %s' % sha256_bytes(new_raw))
    return 0


if __name__ == '__main__':
    sys.exit(main())
