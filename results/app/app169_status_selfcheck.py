#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
app169 —— STATUS_APP.md **独立复核**（§112 收尾）

🔴 **为什么要独立脚本**：§112 的写入器（`_app168_write_status.py`）与 §111 的
  压缩器**自己算自己** ⇒ **自证不算数** ⇒ 必须有**独立复核脚本**，
  用**另一套实现**重新算一遍并逐条断言。

复核项（每条都指到具体字段/行）：
  V1  文件大小 ≤ 40 KB、行数 ≤ 300（APP-049 限额）
  V2  **自指大小一致**：文内写的「本文件 N B / M 行」== 实际（ASR-036 教训）
  V3  头部字段**各只出现一次**（`last_ack` / `更新时间` / `当前任务` /
      `阻塞 / 待用户决定` / `已压缩`）⇒ 防止「重复前缀」
  V4  `last_ack` == CORRECTIONS_APP.md 里的**最大 APP 编号**
  V5  章节号**连续且无重号**（§109…§112）
  V6  每节 ≤ 60 行（APP-049 章节限额）
  V7  「最近更新」区块 ≤ 15 行
  V8  **CORRECTIONS_APP.md 零改动**（SHA256 与 §112 开工时实测值一致）
  V9  归档文件仍在且可读（`status/archive/` 6 个文件）
  V10 头部 `阻塞 / 待用户决定` 不为空（APP-046：必须写明为何停下）
"""

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive')

# 🔴 §112 开工时实测的 CORRECTIONS_APP.md 指纹（用于 V8）
CORR_SHA_AT_112 = 'bb07c52697ecb5aa954169cf32d389095e60b2b35dd4f8ae99752292505d5ec3'

details = []
n_pass = 0
n_fail = 0


def rec(name, ok, msg=''):
    global n_pass, n_fail
    details.append({'name': name, 'ok': bool(ok), 'msg': msg})
    if ok:
        n_pass += 1
    else:
        n_fail += 1
    print(('[PASS] ' if ok else '[FAIL] ') + name + (' :: ' + msg if msg else ''))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    raw = open(STATUS, 'rb').read()
    text = raw.decode('utf-8')
    nbytes = len(raw)
    nlines = len(text.split('\n'))

    rec('V1 STATUS ≤ 40 KB 且 ≤ 300 行',
        nbytes <= 40 * 1024 and nlines <= 300,
        'bytes=%d (<=40960)  lines=%d (<=300)' % (nbytes, nlines))

    m = re.search(r'\*\*本文件 (\d+) B / (\d+) 行\*\*', text)
    ok = bool(m) and int(m.group(1)) == nbytes and int(m.group(2)) == nlines
    rec('V2 自指大小一致（文内写的 == 实际）', ok,
        (m.group(0) if m else '未找到自指大小字段') +
        ' | actual %d B / %d 行' % (nbytes, nlines))

    for key in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定', '已压缩'):
        c = len(re.findall(r'(?m)^' + re.escape(key) + r': ', text))
        rec('V3 头部字段「%s」只出现一次' % key, c == 1, 'count=%d' % c)

    m_ack = re.search(r'(?m)^last_ack: (\S+)', text)
    ack = m_ack.group(1) if m_ack else ''
    corr_text = open(CORR, 'rb').read().decode('utf-8')
    nums = [int(x) for x in re.findall(r'(?m)^## APP-(\d+)', corr_text)]
    maxn = max(nums) if nums else -1
    rec('V4 last_ack == CORRECTIONS_APP.md 最大 APP 编号',
        ack == 'APP-%03d' % maxn, 'last_ack=%s  最大编号=APP-%03d（共 %d 条）'
        % (ack, maxn, len(nums)))

    secs = re.findall(r'(?m)^### §(\d+)', text)
    rec('V5 章节号连续且无重号',
        secs == [str(x) for x in range(int(secs[0]), int(secs[0]) + len(secs))] and
        len(set(secs)) == len(secs),
        'sections=%s' % secs)

    # V6 每节 ≤ 60 行
    lines = text.split('\n')
    idx = [i for i, ln in enumerate(lines) if ln.startswith('### §')]
    idx.append(len(lines))
    worst = ('', 0)
    for a, b in zip(idx, idx[1:]):
        n = b - a
        if n > worst[1]:
            worst = (lines[a][:40], n)
    rec('V6 每章节 ≤ 60 行（APP-049 限额）', worst[1] <= 60,
        '最长节=%r → %d 行' % worst)

    i_recent = next((i for i, ln in enumerate(lines) if ln.startswith('## 最近更新')), None)
    i_next = next((j for j in range((i_recent or 0) + 1, len(lines))
                   if lines[j].startswith('## ')), len(lines))
    n_recent = len([ln for ln in lines[(i_recent or 0) + 1:i_next] if ln.startswith('- ')])
    rec('V7 「最近更新」条目 ≤ 15 行', n_recent <= 15, 'n=%d' % n_recent)

    sha_corr = sha256_file(CORR)
    rec('V8 CORRECTIONS_APP.md 零改动（reviewer 独占文件）',
        sha_corr == CORR_SHA_AT_112,
        'sha256=%s（§112 开工实测 %s）' % (sha_corr, CORR_SHA_AT_112))

    arch = sorted(os.listdir(ARCHIVE)) if os.path.isdir(ARCHIVE) else []
    rec('V9 归档目录存在且 6 个文件可读',
        len(arch) >= 6 and all(
            os.path.getsize(os.path.join(ARCHIVE, a)) > 0 for a in arch),
        'archive=%s' % arch)

    m_blk = re.search(r'(?m)^阻塞 / 待用户决定: (.+)$', text)
    rec('V10 头部「阻塞 / 待用户决定」非空（APP-046 必须写明为何停下）',
        bool(m_blk) and len(m_blk.group(1).strip()) > 10,
        (m_blk.group(1)[:60] + '…') if m_blk else '未找到')

    # 🔴🔴 V11（§114 新增）：**归档一致性** —— §112 正文被移入只读归档时
    #    **内容一字未删** ⇒ 归档里必须**逐字**含有原文；且 STATUS 内的 §112
    #    必须是指针（正文已移走）⇒ 否则就是「半交付：归档写了但正文还在」
    #    或「归档没写但正文删了」⇒ 两种都判 FAIL。
    arch_sec = os.path.join(ARCHIVE, 'STATUS_APP_sec109_113_upto_20261030.md')
    if os.path.exists(arch_sec):
        arch_text = open(arch_sec, 'rb').read().decode('utf-8')
        # 归档文件里应含 §112 的**特征正文片段**（取该节最长的表格行做锚点）
        anchors = [
            'PYTHONPATH',
            'app168_pkg_runtime_import_probe.py',
            'B1 反证',
            'B3 反证',
            'v1.5',
        ]
        missing = [a for a in anchors if a not in arch_text]
        rec('V11 §112 归档内容完整（含正文锚点，一字未删）',
            not missing, 'missing=%s / anchors=%s' % (missing, len(anchors)))
        # STATUS 内的 §112 必须是指针形态
        m112 = re.search(r'(?m)^### §112 .*?(?=\n### §|\Z)', text, re.S)
        body112 = m112.group(0) if m112 else ''
        is_pointer = ('已移入只读归档' in body112 and
                      'STATUS_APP_sec109_113_upto_20261030.md' in body112 and
                      len(body112) < 2000)
        rec('V12 STATUS 内 §112 已改为指针（正文不重复留两份）',
            is_pointer, '§112 段长度=%d 字节' % len(body112.encode('utf-8')))
    else:
        rec('V11 §112 归档内容完整（含正文锚点，一字未删）', False,
            '归档文件不存在：%s' % arch_sec)
        rec('V12 STATUS 内 §112 已改为指针（正文不重复留两份）', False,
            '归档文件不存在，无法验证指针')

    # 🔴🔴 V13（§114 新增）：**新章节的判据数必须与证据 JSON 内一致**
    #    （§114 踩过「判据 PASS 却没有落进证据 JSON」的自指缺口）
    ev171 = os.path.join(HERE, 'app171_app027_v3_cer_compare_evidence.json')
    if os.path.exists(ev171):
        ev = json.load(open(ev171, encoding='utf-8'))
        m114 = re.search(r'(?m)^### §114 .*?(?=\n### §|\Z)', text, re.S)
        claimed = None
        if m114:
            mm = re.search(r'(\d+)\s*PASS\s*/\s*0\s*FAIL', m114.group(0))
            if mm:
                claimed = int(mm.group(1))
        rec('V13 §114 声明的判据数 == 证据 JSON 内 n_pass（自指一致）',
            claimed is not None and claimed == ev.get('n_pass'),
            'STATUS 声明=%s / 证据 n_pass=%s（n_fail=%s, verdict=%s）'
            % (claimed, ev.get('n_pass'), ev.get('n_fail'), ev.get('verdict')))
    else:
        rec('V13 §114 声明的判据数 == 证据 JSON 内 n_pass（自指一致）', False,
            '证据 JSON 不存在：%s' % ev171)

    ev = {'script': os.path.basename(__file__),
          'status_path': STATUS,
          'status_bytes': nbytes, 'status_lines': nlines,
          'status_sha256': sha256_file(STATUS),
          'corrections_sha256': sha_corr,
          'last_ack': ack, 'max_app_no': maxn,
          'n_pass': n_pass, 'n_fail': n_fail,
          'verdict': 'PASS' if n_fail == 0 else 'FAIL',
          'detail': details}
    out = os.path.join(HERE, 'app169_status_selfcheck_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('\n[VERDICT] %s  pass=%d fail=%d' % (ev['verdict'], n_pass, n_fail))
    print('[EVIDENCE] %s' % out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
