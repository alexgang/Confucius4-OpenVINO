#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_sec113_write_status.py —— 把 §113 追加进 status/app/STATUS_APP.md（**只追加 + 头部定点替换**）

🔴 纪律：
  ① 旧章节（§109…§112）**逐字不动**（只在末尾追加 §113）
  ② 头部字段替换**唯一命中**断言（count == 1）
  ③ **自指大小**用占位符重算（ASR-036 教训）⇒ 写盘前后双重断言
  ④ 纯 LF 写回（原文件行尾即 LF）⇒ 不做 split/join 全文件重写
  ⑤ `status/app/CORRECTIONS_APP.md` **绝不触碰**
"""

import hashlib
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SEC113 = os.path.join(REPO, 'results', 'app', '_sec113_body.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

NEW_TIME = '2026-10-30 22:28'

OLD_TASK = (
    '**§112 ✅ 客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）；'
    '抓出并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过**；'
    '本轮**无新纠偏条目**（`last_ack=APP-049` = 最大编号，第 31 次同一口径复核）⇒ '
    '按 APP-046 规则继续推进 ⇒ **APP-046…049 全部结清**；'
    '**APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做（守用户 11:30 指令「不通知不打包」）'
)

NEW_TASK = (
    '**§113 ✅ 修掉「版本标识在打包时复发」的路径：新增打包前闸门（`app170`，18 PASS / 0 FAIL）'
    '＋ 通用同步脚本 `sync_c172`（**不写死版本号**）＋ `pack_v13.py` 接入「升版后自动同步 + 打包前闸门」；'
    '顺手修掉 `app168` 写死包版本（§48 闸门本已 FAIL）**；'
    '本轮**无新纠偏条目**（`last_ack=APP-049` = 最大编号，第 32 次同一口径复核）⇒ '
    '按 APP-046 规则继续推进 ⇒ **APP-046…049 全部结清**；'
    '**APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做（守用户 11:30 指令「不通知不打包」）'
)

BLOCK_TAIL = (
    '；⑧ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / '
    '`sync_c172`「只改身份行不改内容」设计 / v1.13 改动说明排期）；'
    '⑨ 🔴 **v1.12 交付 zip 内 README/NOTICE 自称 v1.6**（11:20 生成的旧包）⇒ '
    '**该缺陷已修路径（自动同步 + 打包前闸门），但旧 zip 内容未改** ⇒ 需用户通知后重打包才真正闭合'
)

NEW_RECENT = (
    '- 2026-10-30 22:28 **§113 修掉「版本标识在打包时复发」的路径** ⇒ 新增打包前闸门 '
    '`results/app/app170_version_identity_gate.py`（**18 PASS / 0 FAIL**，BUG 组 D1~D5 全部命中 ⇒ 判据非恒真）'
    '＋ 通用同步脚本 `live_caption/sync_c172_version_identity_to_pkg.py`（**不写死版本号**）'
    '⇒ `pack_v13.py` 接入「升版后自动同步 + 打包前闸门」；'
    '🔴 实测 v1.12 交付 zip 内 README/NOTICE **自称 v1.6** ⇒ 根因（升版只改目录名 + MANIFEST）已修路径；'
    '顺手修掉 `app168` 写死包版本（§48 闸门本已 FAIL）。\n'
)

OLD_RECENT_POINTER = (
    '> 只保留最近 3 节（§109/§110/§111）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。'
)
NEW_RECENT_POINTER = (
    '> 保留最近章节 §109…§113；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。'
)

OLD_NUM_ROW = (
    '| 包目录代码同步（APP-048） | `live_caption_app.py` **330 336 B** / `gui_status.py` **8 320 B**，'
    '归一化行尾后**逐字节一致** | `live_caption/sync_c170_app048_to_pkg.py`（21 个替换块，唯一命中 + `ast.parse` 校验） |'
)
NEW_NUM_ROW = OLD_NUM_ROW + (
    '\n| 版本标识一致闸门 | **18 PASS / 0 FAIL**（REAL 组）；BUG 组（修复前副本）**D1~D5 全部命中 FAIL** ⇒ 判据非恒真 | '
    '`results/app/app170_version_identity_gate_evidence.json` → `pass` / `fail` / `verdict` |'
    '\n| 打包流水线 dry-run | §48 闸门 **0 处违规 / PASS** ｜ §113 闸门 **18 PASS / 0 FAIL** ｜ 内部素材 **0 命中** ｜ **结论 PASS（未写 zip）** | '
    '`pack_v13.py --dry-run --same-version` 本轮实测输出 |'
)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def replace_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, '§113 写入器：替换块「%s」命中 %d 次（要求恰好 1 次）' % (tag, n)
    return text.replace(old, new, 1)


def main():
    corr_sha_before = sha256_file(CORR)

    raw = open(STATUS, 'rb').read()
    assert b'\r\n' not in raw, '§113 写入器：原文件含 CRLF（预期纯 LF）'
    text = raw.decode('utf-8')
    old_bytes = len(raw)
    old_lines = len(text.split('\n'))
    old_sha = hashlib.sha256(raw).hexdigest()

    # ---- 切分：头部区（第一个「### §」之前） + 旧章节区 ----
    lines = text.split('\n')
    i_head = next(i for i, ln in enumerate(lines) if ln.startswith('### §'))
    head = '\n'.join(lines[:i_head])
    body = '\n'.join(lines[i_head:])          # §109…§112（旧正文，逐字保留）
    assert body.startswith('### §109'), '§113 写入器：旧正文起点异常'
    assert '`verdict=PASS`' in body.rstrip('\n')[-200:], '§113 写入器：旧正文尾部异常'

    # ---- 头部定点替换（全部在头部区） ----
    head = replace_once(head, '更新时间: 2026-10-30 20:41', '更新时间: ' + NEW_TIME, '更新时间')
    head = replace_once(head, '当前任务: ' + OLD_TASK, '当前任务: ' + NEW_TASK, '当前任务')
    # 阻塞栏：保留原内容，末尾追加两项
    m_blk = re.search(r'(?m)^阻塞 / 待用户决定: (.+)$', head)
    assert m_blk, '§113 写入器：未找到「阻塞 / 待用户决定」'
    head = replace_once(head, m_blk.group(0), m_blk.group(0) + BLOCK_TAIL, '阻塞 / 待用户决定')
    # 「最近更新」：在 §112 条目之后插入 §113 条目（保持倒序）
    head = replace_once(head,
                        '- 2026-10-30 20:41 **§112 客户包「运行时可加载性」独立验收**',
                        NEW_RECENT + '- 2026-10-30 20:41 **§112 客户包「运行时可加载性」独立验收**',
                        '最近更新插入点')
    head = replace_once(head, OLD_RECENT_POINTER, NEW_RECENT_POINTER, '最近章节指针')
    head = replace_once(head, OLD_NUM_ROW, NEW_NUM_ROW, '关键数字表')
    # 自指大小 → 占位符（稍后重算）
    head = replace_once(head, '**本文件 23520 B / 147 行**', '**本文件 @@@B@@ B / @@@L@@ 行**', '自指大小')

    # ---- 追加 §113 ----
    sec113 = open(SEC113, 'rb').read().decode('utf-8')
    sec113 = sec113.rstrip('\n')
    assert sec113.startswith('### §113'), '§113 写入器：草稿首行不是 §113'
    # 草稿里「三件」与实际 4 行表格不符 ⇒ 修正为「四件」
    sec113 = sec113.replace('#### ✅ 本轮产出（三件，均已落盘）',
                            '#### ✅ 本轮产出（四件，均已落盘）')

    new_body = body.rstrip('\n') + '\n\n\n' + sec113 + '\n'

    # ---- 自指大小重算（迭代至收敛） ----
    def build(b, l):
        return head.replace('@@@B@@', str(b)).replace('@@@L@@', str(l)) + '\n' + new_body

    b, l = 0, 0
    for _ in range(6):
        t = build(b, l)
        nb = len(t.encode('utf-8'))
        nl = len(t.split('\n'))
        if nb == b and nl == l:
            break
        b, l = nb, nl
    final = build(b, l)

    # ---- 写盘前断言 ----
    assert final.endswith('\n'), '§113 写入器：结尾缺换行'
    assert '\r\n' not in final, '§113 写入器：出现 CRLF'
    # 旧正文逐字未变
    for old_sec in re.split(r'(?m)^(?=### §)', body):
        if not old_sec.strip():
            continue
        assert old_sec in final, '§113 写入器：旧章节被改动（逐字校验失败）'
    # 章节号连续无重号
    secs = re.findall(r'(?m)^### §(\d+)', final)
    assert secs == [str(x) for x in range(109, 109 + len(secs))], '§113 写入器：章节号不连续 %s' % secs
    # 头部字段各只出现一次
    for key in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定', '已压缩'):
        c = len(re.findall(r'(?m)^' + re.escape(key) + r': ', final))
        assert c == 1, '§113 写入器：头部字段「%s」出现 %d 次' % (key, c)
    # 限额
    assert len(final.encode('utf-8')) <= 40 * 1024, '§113 写入器：超过 40 KB'
    assert len(final.split('\n')) <= 300, '§113 写入器：超过 300 行'
    # 每节 ≤ 60 行
    fl = final.split('\n')
    idx = [i for i, ln in enumerate(fl) if ln.startswith('### §')]
    idx.append(len(fl))
    for a, bb in zip(idx, idx[1:]):
        assert bb - a <= 60, '§113 写入器：某节超过 60 行（%d）' % (bb - a)

    # ---- 写盘 ----
    with open(STATUS, 'wb') as f:
        f.write(final.encode('utf-8'))

    # ---- 写盘后双重断言（独立重读） ----
    raw2 = open(STATUS, 'rb').read()
    t2 = raw2.decode('utf-8')
    assert len(raw2) == b and len(t2.split('\n')) == l, \
        '§113 写入器：写盘后自指大小不一致（%d B / %d 行 vs 声明 %d B / %d 行）' % (
            len(raw2), len(t2.split('\n')), b, l)
    assert sha256_file(CORR) == corr_sha_before, '§113 写入器：CORRECTIONS_APP.md 被改动！'

    print('✅ 写入完成')
    print('  旧: %d B / %d 行 / sha256 %s' % (old_bytes, old_lines, old_sha))
    print('  新: %d B / %d 行 / sha256 %s' % (len(raw2), len(t2.split('\n')), sha256_file(STATUS)))
    print('  章节: %s' % re.findall(r'(?m)^### §(\d+)', t2))
    print('  CORRECTIONS_APP.md 未改动: sha256 %s' % sha256_file(CORR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
