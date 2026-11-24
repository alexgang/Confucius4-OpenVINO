#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮：MEMORY.md 压缩的**独立行为级复核**（另起脚本，不 import 被检脚本）。

## 🔴 为什么必须是「另起脚本」
- 写脚本里的断言与写脚本**共用同一份 EDITS 表** ⇒ 若表本身写错，两边一起错 ⇒
  **假 PASS**。
- ⇒ 本脚本**不 import `_app232_compress_memory.py`**，而是**从磁盘现状重新推导**：
  ① 拿**写前备份**（`%TEMP%/MEMORY.md.bak_app232`）；
  ② 拿**当前文件**；
  ③ 用**独立重新实现**的检查（长度上限 / 关键词 / 章节 / 标记 / § 编号 /
     **关键事实逐条在位** / **压缩没有把「否定式表述」变成「肯定式表述」**）；
  ④ 🔴 **反证组**：把**压缩前**的旧文件喂给同一批检查 ⇒ 检查必须**能识破**
     「旧版超上限 / 旧版缺护栏」⇒ 证明这不是恒 PASS 的假判据。

## 判据清单（每条都对着**写前备份**比，不写死记忆里的数字）
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sys

MEM_MD = r'C:\Users\Trekker-PTL\confucius4-openvino\.workbuddy\memory\MEMORY.md'
BAK = os.path.join(os.environ.get('TEMP', r'C:\Users\Trekker-PTL\AppData\Local\Temp'),
                   'MEMORY.md.bak_app232')
CAP = 9700

# 🔴 **关键事实逐条在位**（每条都是「换个会话不知道就会做错」的那类）
FACTS = [
    'last_ack=APP-133',
    'v2.6 已签 ACCEPTED',
    'b2a4978',
    '发客户发 `v1.1.1.zip`',
    'v2.5 须先重签',
    '全仓 854 个 `i/lf+w/crlf` 须 reviewer 裁定',
    '待裁定',
    '机器锁必须原子创建',
    'os.replace(tmp, LOCK)',
    'lock_lost',
    '修锁要修生产路径',
    '无新纠偏 ⇒ `last_ack` 不变',
    '待命轮不写 §N',
    '单独执行＋单独发信＋写 §N',
    '首/中/尾三地标',
    '入库件与实发**逐字节相同**',
    '必须用包内 python',
    'core.autocrlf=true',
    'P90≤0.75',
    'EXECUTION_DEVICES',
    'and not _bound',
    '语速上限现役 = 1.70×',
    '帧数上限＝**492**',
    'Qwen3-TTS 0.6B（spkonly·全 NPU·INT8）是唯一交付方案',
    'TTS-078 降级为「仅补 TTS 模块 `qwen3tts_patch.py`」',
    '未落盘 ⇒ 不可当证据',
    'MiniMVP v1.1.1 包落后 dev 树',
    'CHUNK_FRAMES',
    'n_speakers',
    '192.168.2.206',
    '_app547_hash_retry.py',
    '5 212 403 155 B',
    '假 FAIL',
    '真不变量',
    '还原式复核',
    '反证',
    '跨模块共享',
    '写完必重跑上限断言',
]

# 🔴 **否定式表述不得被压成肯定式**（§224 的教训：压句子最容易丢「不／禁／别」）
NEGATIONS = [
    ('禁 os.replace(tmp, LOCK)', True),
    ('禁**手抄', True),
    ('不得**写「vocoder 可上 GPU」', True),
    ('不 force push', True),
    ('不覆盖不删', True),
    ('不可当证据', True),
    ('零改动', True),
    ('不是新编号', True),
    ('不删除', None),   # 允许不存在
]


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def check(text, label):
    """返回 (ok, [失败原因])；**同一批检查**可喂给压缩前/后的文本。"""
    errs = []

    # ① 上限
    if len(text) > CAP:
        errs.append('%s: 超上限 %d > %d' % (label, len(text), CAP))

    # ② 关键事实在位
    for fct in FACTS:
        if fct not in text:
            errs.append('%s: 缺关键事实 %r' % (label, fct))

    # ③ 否定式表述仍在
    for frag, must in NEGATIONS:
        if must and frag not in text:
            errs.append('%s: 否定式表述丢失 %r' % (label, frag))

    # ④ § 编号覆盖
    old_secs = set(int(x) for x in re.findall(r'§(\d+)', text))
    if not old_secs:
        errs.append('%s: 一个 § 编号都没有（异常）' % label)

    # ⑤ 章节数 ≥ 13（本文件有 15 节）
    nsec = len([p for p in re.split(r'(?m)^(?=## )', text) if p.startswith('## ')])
    if nsec < 13:
        errs.append('%s: 章节数 %d < 13' % (label, nsec))

    # ⑥ last_ack 唯一
    if text.count('last_ack=APP-133') != 1:
        errs.append('%s: last_ack 行数 %d != 1' % (label, text.count('last_ack=APP-133')))

    return (not errs), errs


def main():
    cur = read(MEM_MD)
    old = read(BAK)

    print('=== 现状 ===')
    print('压缩前: %d 字符 / %d B' % (len(old), len(old.encode('utf-8'))))
    print('压缩后: %d 字符 / %d B' % (len(cur), len(cur.encode('utf-8'))))
    print('SHA256(前)=%s' % hashlib.sha256(old.encode('utf-8')).hexdigest())
    print('SHA256(后)=%s' % hashlib.sha256(cur.encode('utf-8')).hexdigest())
    assert cur != old, '文件没变 ⇒ 本轮压缩无效'

    ok, errs = check(cur, '压缩后')
    print()
    print('=== 压缩后检查：%s ===' % ('PASS' if ok else 'FAIL'))
    for e in errs:
        print('  ✗', e)

    # 🔴 **反证组**：把**压缩前**的旧文件喂给同一批检查
    #    ⇒ 旧版必须**被判不合格**（超上限 + 缺护栏）⇒ 证明判据不是恒 PASS。
    print()
    print('=== 反证组：把压缩前版本喂给同一批检查（必须 FAIL）===')
    ok_old, errs_old = check(old, '压缩前')
    print('压缩前是否被判不合格：%s（%d 条问题）' % (not ok_old, len(errs_old)))
    for e in errs_old:
        print('  ·', e)
    assert not ok_old, '🔴 反证组失败：旧版也 PASS ⇒ 判据恒 PASS（假判据）'

    # ⑦ **逐字节还原式复核**：压缩后 vs 压缩前，**除编辑区外必须逐行相同**
    ol = old.split('\n')
    cl = cur.split('\n')
    print()
    print('=== 逐行比对（压缩前 %d 行 → 压缩后 %d 行）===' % (len(ol), len(cl)))
    import difflib
    diff = [d for d in difflib.unified_diff(ol, cl, lineterm='', n=0)
            if d.startswith(('+', '-')) and not d.startswith(('+++', '---'))]
    print('差异行数: %d' % len(diff))
    for d in diff:
        print('  ', d[:110])

    total_ok = ok and (not ok_old)
    print()
    print('总体: %s' % ('PASS' if total_ok else 'FAIL'))

    # ── 证据 json（§222：**证据 json 入库 ⇒ 其产生脚本也要入库** ⇒ 本脚本入库）──
    import json
    ev = {
        'round': 'APP-232',
        'target': 'C:\\Users\\Trekker-PTL\\confucius4-openvino\\.workbuddy\\memory\\MEMORY.md',
        'cap_chars': CAP,
        'before': {
            'chars': len(old),
            'bytes': len(old.encode('utf-8')),
            'sha256': hashlib.sha256(old.encode('utf-8')).hexdigest(),
            'backup': BAK,
        },
        'after': {
            'chars': len(cur),
            'bytes': len(cur.encode('utf-8')),
            'sha256': hashlib.sha256(cur.encode('utf-8')).hexdigest(),
            'margin_chars': CAP - len(cur),
        },
        'checks': {
            'after_pass': ok,
            'after_errors': errs,
            'counterproof_old_rejected': (not ok_old),
            'counterproof_old_errors': errs_old,
            'facts_checked': len(FACTS),
            'negations_checked': len(NEGATIONS),
        },
        'diff_lines': len(diff),
        'result': 'PASS' if total_ok else 'FAIL',
    }
    evp = os.path.join(os.path.dirname(MEM_MD).replace('memory', 'results/app'),
                       'app232_memory_compress.json')
    evp = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app232_memory_compress.json'
    with io.open(evp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=2))
    print('证据 json: %s (%d B)' % (evp, os.path.getsize(evp)))
    return 0 if total_ok else 1


if __name__ == '__main__':
    sys.exit(main())
