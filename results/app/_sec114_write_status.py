#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_sec114_write_status.py —— 把 §114 追加进 status/app/STATUS_APP.md

🔴 纪律（沿用 §113 写入器的安全模式）：
  ① 旧章节（§109…§113）**逐字不动**（只在末尾追加 §114）
  ② 头部字段替换**唯一命中**断言（count == 1）
  ③ **自指大小**用占位符重算（ASR-036 教训）⇒ 写盘前后双重断言
  ④ 纯 LF 写回（原文件行尾即 LF）⇒ 不做 split/join 全文件重写
  ⑤ `status/app/CORRECTIONS_APP.md` **绝不触碰**
  ⑥ 🔴🔴 **APP-049 限额**：追加 §114 会突破 40 KB ⇒ **必须先把 §112 正文
     移入只读归档**（内容一字未删）⇒ STATUS 内只留一行指针
"""

import hashlib
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
SEC114 = os.path.join(REPO, 'results', 'app', '_sec114_body.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_sec109_113_upto_20261030.md')

NEW_TIME = '2026-10-30 23:20'

OLD_TASK_HEAD = '**§113 ✅ 修掉「版本标识在打包时复发」的路径：'
NEW_TASK_HEAD = ('**§114 ✅ APP-027 V3(a) MiniMax 回转写 CER 对比（克隆 vs 预设 A）完成：'
                 '**14 PASS / 0 FAIL**，Δ(克隆−预设A) = **+0.0657 pp**、95% CI '
                 '**[−0.7961, +0.9302] 含 0 ⇒ 未构成明显劣化**；真发音错误口径 '
                 'Δ = +0.4602 pp、CI [−0.2611, +1.3441] 亦含 0；反证组已证伪「判据恒真」**；'
                 '（起因 = 用户 22:44 指令「你自己完成 MiniMax 回转写错误率对比」⇒ '
                 '覆盖 APP-033 第 1 条默认禁令，**仅限本条**）｜'
                 '本轮**无新纠偏条目**（`last_ack=APP-049` = 最大编号，第 33 次同一口径复核）⇒ '
                 '**APP-046…049 全部结清**；'
                 '**APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做'
                 '（守用户 11:30 指令「不通知不打包」）；'
                 '**APP-027 V3(b) CAMPPlus 余弦相似度**仍未做')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def replace_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, '§114 写入器：替换块「%s」命中 %d 次（要求恰好 1 次）' % (tag, n)
    return text.replace(old, new, 1)


def main():
    corr_sha_before = sha256_file(CORR)

    raw = open(STATUS, 'rb').read()
    assert b'\r\n' not in raw, '§114 写入器：原文件含 CRLF（预期纯 LF）'
    text = raw.decode('utf-8')
    old_bytes = len(raw)
    old_lines = len(text.split('\n'))
    old_sha = hashlib.sha256(raw).hexdigest()

    # ---- 切分：头部区（第一个「### §」之前） + 旧章节区 ----
    lines = text.split('\n')
    i_head = next(i for i, ln in enumerate(lines) if ln.startswith('### §'))
    head = '\n'.join(lines[:i_head])
    body = '\n'.join(lines[i_head:])          # §109…§113（旧正文，逐字保留）
    assert body.startswith('### §109'), '§114 写入器：旧正文起点异常'

    # ---- 🔴 APP-049 限额：把 §112 正文移入只读归档（内容一字未删）----
    sec_parts = re.split(r'(?m)^(?=### §)', body)
    idx112 = None
    for i, p in enumerate(sec_parts):
        if p.startswith('### §112'):
            idx112 = i
            break
    assert idx112 is not None, '§114 写入器：未找到 §112 章节'
    sec112_body = sec_parts[idx112].rstrip('\n')

    # 归档文件：**只在内存构造**，全部断言通过后才落盘（避免「归档已写、STATUS 未写」的半交付）
    arch_new = None
    if os.path.exists(ARCHIVE):
        arch = open(ARCHIVE, 'rb').read().decode('utf-8')
        if sec112_body in arch:
            # 幂等：上一轮已归档过（半交付恢复）⇒ 直接复用现有归档内容
            arch_new = arch
        else:
            arch_new = arch.rstrip('\n') + '\n\n\n' + sec112_body + '\n'
    else:
        arch_new = (
            '# STATUS_APP 归档（§109…§113 章节正文，只读）\n\n'
            '> 本文件是 `status/app/STATUS_APP.md` 的**只读归档**（内容一字未删）。\n'
            '> 归档原因：**APP-049 限额**（STATUS ≤ 40 KB / ≤ 300 行 / 每节 ≤ 60 行）'
            '⇒ §114 追加前把 §112 正文移到这里。\n'
            '> 归档时间：2026-10-30 23:20｜归档时 STATUS = %d B / %d 行 / SHA256 %s\n\n'
            % (old_bytes, old_lines, old_sha)
        ) + sec112_body + '\n'

    # STATUS 内 §112 换成指针（一行，内容不丢 ⇒ 在归档里）
    ptr = ('### §112 ✅ **客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）｜ '
           '发现并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过** ｜ **本条已完成** ｜ '
           '**本条需等 reviewer 复核**\n\n'
           '- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §114 前压缩）⇒ '
           '全文见 `status/archive/STATUS_APP_sec109_113_upto_20261030.md`；'
           '**结论摘要**：R1~R9 **9 项 PASS**（包内自带 python 3.12.10 可真实 import 包内模块、'
           '`asr_spk/` 3 资产在真实加载路径下可 import、`EMBED_RANGE_LO/HI == [100,2048]`、'
           '包内 `sys.path` **无宿主污染**）；B1/B2/B3 **3 条反证全部命中** ⇒ 判据非恒真；'
           '对旧包 **v1.5** 跑同一套 ⇒ **12 FAIL** ⇒ 有鉴别力；'
           '🔴 **抓出真缺陷**：宿主 `PYTHONPATH` 被继承进包内 python ⇒ `import torch` 假阳性 ⇒ '
           '已置空 `PYTHONPATH`/`PYTHONHOME` 并新增 R9+B3。\n')

    # 用占位符替换（顺序不变）：§112 段落 → 指针段
    body_new = body.replace(sec112_body, '@@@SEC112_PTR@@@')
    body_new = body_new.replace('@@@SEC112_PTR@@@', ptr.rstrip('\n'))

    # ---- 头部定点替换（全部在头部区） ----
    head = replace_once(head, '更新时间: 2026-10-30 22:28', '更新时间: ' + NEW_TIME, '更新时间')
    m_task = re.search(r'(?m)^当前任务: (.+)$', head)
    assert m_task, '§114 写入器：未找到「当前任务」'
    old_task = m_task.group(1)
    assert old_task.startswith(OLD_TASK_HEAD), '§114 写入器：「当前任务」起始文本异常'
    head = replace_once(head, '当前任务: ' + old_task, '当前任务: ' + NEW_TASK_HEAD, '当前任务')

    # 阻塞栏：替换掉已完成的 MiniMax 项，其余保留
    m_blk = re.search(r'(?m)^阻塞 / 待用户决定: (.+)$', head)
    assert m_blk, '§114 写入器：未找到「阻塞 / 待用户决定」'
    blk = m_blk.group(1)
    old_minimax = '⑤ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
    assert old_minimax in blk, '§114 写入器：阻塞栏未找到 MiniMax 项（文本已变？）'
    new_minimax = ('⑤ 🔴 **MiniMax 回转写 CER 对比已完成**（§114，14 PASS / 0 FAIL，'
                   'CI 含 0 ⇒ 未构成明显劣化）**但本条需等 reviewer 复核 4 项**'
                   '（判据口径 / 写法差异拆分规则 / 多 3 句真错误是否提示用户 / 是否重跑）；'
                   '**APP-027 V3(b) CAMPPlus 余弦相似度仍未做**；')
    blk_new = blk.replace(old_minimax, new_minimax)
    # 追加 §114 复核项
    blk_new = blk_new.rstrip()
    assert blk_new.endswith('需用户通知后重打包才真正闭合'), '§114 写入器：阻塞栏尾部异常'
    blk_new += '；⑩ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）'
    head = replace_once(head, m_blk.group(0), '阻塞 / 待用户决定: ' + blk_new, '阻塞 / 待用户决定')

    # 「最近更新」：在 §113 条目之后插入 §114 条目（保持倒序）
    head = replace_once(
        head,
        '- 2026-10-30 22:28 **§113 修掉「版本标识在打包时复发」的路径**',
        '- 2026-10-30 23:20 **§114 APP-027 V3(a) MiniMax 回转写 CER 对比（克隆 vs 预设 A）** '
        '⇒ 新增 `results/app/app171_app027_v3_cer_compare.py`（**14 PASS / 0 FAIL**）'
        '⇒ 三臂 76 句配对：预设A **3.0243%** vs 克隆 **3.0901%** ⇒ '
        'Δ = **+0.0657 pp**、95% CI **[−0.7961, +0.9302] 含 0** ⇒ **未构成明显劣化**；'
        '真错误口径 Δ = **+0.4602 pp**、CI [−0.2611, +1.3441] 亦含 0；'
        '🔴 反证组（预设臂整体错位）Δ = **−125.2465 pp** ⇒ **判据非恒真已证实**；'
        '🔴 修掉**脱敏完全失效**的坑（bytes 与 str 的 `\\b` 语义不同 ⇒ 自检用 bytes、脱敏用 str ⇒ 必然漏检）。\n'
        '- 2026-10-30 22:28 **§113 修掉「版本标识在打包时复发」的路径**',
        '最近更新插入点')
    head = replace_once(
        head,
        '> 保留最近章节 §109…§113；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。',
        '> 保留最近章节 §109…§114；§112 正文已移入只读归档 '
        '`status/archive/STATUS_APP_sec109_113_upto_20261030.md`；'
        '更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。',
        '最近章节指针')

    # 「关键数字」表：追加 §114 的行
    old_num = ('| 打包流水线 dry-run | §48 闸门 **0 处违规 / PASS** ｜ §113 闸门 **18 PASS / 0 FAIL** ｜ '
               '内部素材 **0 命中** ｜ **结论 PASS（未写 zip）** | '
               '`pack_v13.py --dry-run --same-version` 本轮实测输出 |')
    assert old_num in head, '§114 写入器：关键数字表未找到打包流水线行'
    new_num = old_num + (
        '\n| MiniMax 回转写 CER（预设 A） | **3.0243%**（ed 46 / ref 1521 字符） | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_preset.total_cer_pct` |'
        '\n| MiniMax 回转写 CER（克隆） | **3.0901%**（ed 47 / ref 1521 字符） | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_clone.total_cer_pct` |'
        '\n| 克隆 − 预设A 的 Δ | **+0.0657 pp**，95% CI **[−0.7961, +0.9302]**（**含 0** ⇒ 未构成明显劣化） | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → '
        '`pair_cuda_preset_vs_clone.bootstrap.delta_pp` / `ci_lo_pp` / `ci_hi_pp` |'
        '\n| 真发音错误口径 Δ | **+0.4602 pp**，95% CI **[−0.2611, +1.3441]**（含 0） | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → `pair_cuda_preset_vs_clone.true_error_counts` |'
        '\n| 判据非恒真（反证组） | 预设臂整体错位 ⇒ Δ = **−125.2465 pp**，CI **[−140.8994, −112.9758]** ⇒ 必判 FAIL | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → `counterproof.swap_arms_bootstrap` |'
        '\n| MiniMax 回转写 CER 验收 | **14 PASS / 0 FAIL**；证据 JSON **内容命中 0**（已脱敏） | '
        '`results/app/app171_app027_v3_cer_compare_evidence.json` → `n_pass` / `n_fail` / `verdict` |')
    head = replace_once(head, old_num, new_num, '关键数字表')

    # 自指大小 → 占位符（稍后重算）
    head = replace_once(head, '**本文件 33971 B / 204 行**', '**本文件 @@@B@@ B / @@@L@@ 行**', '自指大小')

    # ---- 追加 §114 ----
    sec114 = open(SEC114, 'rb').read().decode('utf-8')
    sec114 = sec114.rstrip('\n')
    assert sec114.startswith('### §114'), '§114 写入器：草稿首行不是 §114'

    body_final = body_new.rstrip('\n') + '\n\n\n' + sec114 + '\n'

    # ---- 自指大小重算（迭代至收敛） ----
    def build(b, l):
        return head.replace('@@@B@@', str(b)).replace('@@@L@@', str(l)) + '\n' + body_final

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
    assert final.endswith('\n'), '§114 写入器：结尾缺换行'
    assert '\r\n' not in final, '§114 写入器：出现 CRLF'
    # 旧章节（除已归档的 §112）逐字未变
    for old_sec in re.split(r'(?m)^(?=### §)', body):
        if not old_sec.strip() or old_sec.startswith('### §112'):
            continue
        assert old_sec.rstrip('\n') in final, \
            '§114 写入器：旧章节被改动（逐字校验失败）: %s' % old_sec[:40]
    # 章节号连续无重号
    secs = re.findall(r'(?m)^### §(\d+)', final)
    assert secs == [str(x) for x in range(109, 109 + len(secs))], \
        '§114 写入器：章节号不连续 %s' % secs
    # 头部字段各只出现一次
    for key in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定', '已压缩'):
        c = len(re.findall(r'(?m)^' + re.escape(key) + r': ', final))
        assert c == 1, '§114 写入器：头部字段「%s」出现 %d 次' % (key, c)
    # 限额
    assert len(final.encode('utf-8')) <= 40 * 1024, \
        '§114 写入器：超过 40 KB（%d）' % len(final.encode('utf-8'))
    assert len(final.split('\n')) <= 300, '§114 写入器：超过 300 行'
    # 每节 ≤ 60 行
    fl = final.split('\n')
    idx = [i for i, ln in enumerate(fl) if ln.startswith('### §')]
    idx.append(len(fl))
    for a, bb in zip(idx, idx[1:]):
        assert bb - a <= 60, '§114 写入器：某节超过 60 行（%d）' % (bb - a)
    # §112 指针必须在、且指向归档
    assert 'STATUS_APP_sec109_113_upto_20261030.md' in final, '§114 写入器：缺 §112 归档指针'

    # ---- 写盘（归档先落盘，再落 STATUS；两者都已在内存构造完毕）----
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(ARCHIVE, 'wb') as f:
        f.write(arch_new.encode('utf-8'))
    with open(STATUS, 'wb') as f:
        f.write(final.encode('utf-8'))

    # ---- 写盘后双重断言（独立重读） ----
    raw2 = open(STATUS, 'rb').read()
    t2 = raw2.decode('utf-8')
    assert len(raw2) == b and len(t2.split('\n')) == l, \
        '§114 写入器：写盘后自指大小不一致（%d B / %d 行 vs 声明 %d B / %d 行）' % (
            len(raw2), len(t2.split('\n')), b, l)
    assert sha256_file(CORR) == corr_sha_before, '§114 写入器：CORRECTIONS_APP.md 被改动！'

    print('✅ 写入完成')
    print('  旧: %d B / %d 行 / sha256 %s' % (old_bytes, old_lines, old_sha))
    print('  新: %d B / %d 行 / sha256 %s' % (len(raw2), len(t2.split('\n')), sha256_file(STATUS)))
    print('  章节: %s' % re.findall(r'(?m)^### §(\d+)', t2))
    print('  归档: %s（%d B）' % (os.path.basename(ARCHIVE), os.path.getsize(ARCHIVE)))
    print('  CORRECTIONS_APP.md 未改动: sha256 %s' % sha256_file(CORR))
    return 0


if __name__ == '__main__':
    sys.exit(main())
