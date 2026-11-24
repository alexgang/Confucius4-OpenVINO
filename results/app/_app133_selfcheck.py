#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：从**本轮**三臂的 `bridge.err` 里抽 **APP-130 自检**证据。

## 为什么

§229 companion 的 §3「A 机实测」在**上一会话**留的是**空白**
（原文：「本轮未取到自检日志 ⇒ **如实留空**，未取到的数字不写「已通过」」）。

⇒ 本轮三臂的 `bridge.err` 里**有**自检日志 ⇒ 可以**从原始日志**抽出来
⇒ 填进 §229（**只填实测到的**，一条不编）。

## 判据（**从日志原文抽，不重算**）

- `cp_prefill: NPU 自检通过（耗时 X s，用例 [...]）` ⇒ 正则取耗时与逐用例余弦；
- `cp_decode: NPU 自检通过（耗时 X s，用例 [...]）` ⇒ 同上；
- `EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，…`
  ⇒ 取落点；
- `落点统计：NPU 上 N 个组件` ⇒ 取 NPU/CPU 组件数。

## 反证组

**故意**把一份日志里的「自检通过」改成「自检失败」⇒ 判据必须**不再**报「通过」
⇒ 证明判据承重（不是「日志里没有失败就等于通过」）。

## 纪律

- **只读**臂目录的 `bridge.err`；不写、不改任何包内文件；
- 证据落 `results/app/app133_selfcheck_evidence.json`。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.path.dirname(REPO)
OUT_ROOT = os.path.join(HOME, 'shared', 'bgkeep', 'e2e_v26_r2')
RESULTS = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RESULTS, 'app133_selfcheck_evidence.json')

ARMS = ('bgkeep_off', 'bgkeep_on', 'bgkeep_clone')

RE_PASS = re.compile(
    r'^(?P<name>cp_prefill|cp_decode): NPU 自检通过'
    r'（耗时 (?P<elapsed>[\d.]+) s，用例 \[(?P<cases>[^\]]*)\]）')
RE_COS = re.compile(r'\((?P<amp>[\d.]+), (?P<cos>[\d.]+)\)')
RE_DEV = re.compile(r'EXECUTION_DEVICES (?P<dev>.+)')
RE_LAND = re.compile(r'落点统计：NPU 上 (?P<npu>\d+) 个组件')


def parse(text):
    """从一份 bridge.err 文本里抽自检证据。"""
    out = {'selfcheck_pass': {}, 'selfcheck_fail': {},
           'execution_devices': None, 'landing': None}
    for line in text.splitlines():
        m = RE_PASS.match(line.split('] ')[-1].strip())
        if m:
            cos = [float(c.group('cos'))
                   for c in RE_COS.finditer(m.group('cases'))]
            out['selfcheck_pass'][m.group('name')] = {
                'ok': True,
                'elapsed_s': float(m.group('elapsed')),
                'cosines': cos,
                'raw_case_str': m.group('cases'),
                'line': line.strip()[-220:],
            }
        if '自检失败' in line and ('cp_prefill' in line or 'cp_decode' in line):
            name = 'cp_prefill' if 'cp_prefill' in line else 'cp_decode'
            out['selfcheck_fail'][name] = line.strip()[-220:]
        m = RE_DEV.search(line)
        if m and out['execution_devices'] is None:
            out['execution_devices'] = m.group('dev').strip()
        m = RE_LAND.search(line)
        if m:
            out['landing'] = {'npu_n': int(m.group('npu'))}
    return out


def main():
    rep = {'ts': __import__('datetime').datetime.now().strftime(
        '%Y-%m-%d %H:%M:%S'), 'out_root': OUT_ROOT, 'arms': {}}
    for arm in ARMS:
        p = os.path.join(OUT_ROOT, arm, 'bridge.err')
        if not os.path.isfile(p):
            rep['arms'][arm] = {'error': 'bridge.err 不存在'}
            continue
        raw = open(p, 'rb').read()
        text = raw.decode('utf-8', errors='replace')
        rec = parse(text)
        rec['err_file'] = p
        rec['err_bytes'] = len(raw)
        rec['err_sha256'] = hashlib.sha256(raw).hexdigest()
        # 逐项检查
        checks = []
        for k in ('cp_prefill', 'cp_decode'):
            p_ = rec['selfcheck_pass'].get(k) or {}
            checks.append({'name': '%s 自检有「通过」记录' % k,
                           'ok': bool(p_.get('ok')),
                           'detail': p_.get('line', '无')})
            checks.append({'name': '%s 自检耗时 < 1.0 s' % k,
                           'ok': (p_.get('elapsed_s') is not None
                                  and p_.get('elapsed_s') < 1.0),
                           'detail': str(p_.get('elapsed_s'))})
            cos = p_.get('cosines') or []
            checks.append({'name': '%s 逐用例余弦全 ≥ 0.99' % k,
                           'ok': bool(cos) and min(cos) >= 0.99,
                           'detail': str(cos)})
            checks.append({'name': '%s 无「自检失败」记录（反证组）' % k,
                           'ok': k not in rec['selfcheck_fail'],
                           'detail': rec['selfcheck_fail'].get(k, '无')})
        dev = rec.get('execution_devices') or ''
        checks.append({'name': 'cp_prefill 落点仍是 NPU',
                       'ok': 'cp_prefill=NPU' in dev, 'detail': dev})
        checks.append({'name': 'cp_decode 落点仍是 NPU',
                       'ok': 'cp_decode=NPU' in dev, 'detail': dev})
        rec['checks'] = checks
        rec['all_pass'] = all(c['ok'] for c in checks)
        rep['arms'][arm] = rec

    # ── 反证组：把「自检通过」改成「自检失败」⇒ 必须不再报通过 ──
    sample = os.path.join(OUT_ROOT, 'bgkeep_off', 'bridge.err')
    if os.path.isfile(sample):
        txt = open(sample, encoding='utf-8', errors='replace').read()
        # 🔴 **改的是「实际被抽到的那一行」** ⇒ 先找出第一个「NPU 自检通过」
        #   出现在哪个组件名上，再针对**那个**组件做反证
        #   （上一版固定改第一处 ⇒ 实际改到 `cp_decode`，却去查
        #    `cp_prefill` ⇒ **假 FAIL**：判据其实是对的）。
        m0 = RE_PASS.search(txt)
        target = m0.group('name') if m0 else 'cp_prefill'
        bad = txt.replace('%s: NPU 自检通过' % target,
                          '%s: NPU 自检失败' % target, 1)
        with tempfile.TemporaryDirectory() as td:
            bp = os.path.join(td, 'bridge.err')
            with open(bp, 'w', encoding='utf-8') as f:
                f.write(bad)
            r = parse(open(bp, encoding='utf-8', errors='replace').read())
        detected = (target not in r['selfcheck_pass']
                    and target in r['selfcheck_fail'])
        rep['counterfactual'] = {
            'mutation': '把 %s 的一行「自检通过」改成「自检失败」' % target,
            'target': target,
            'judgement_detects': detected,
            'load_bearing': detected,
        }
    else:
        rep['counterfactual'] = {'skipped': '无样本文件'}

    rep['all_ok'] = all((a.get('all_pass') for a in rep['arms'].values()))
    with open(EVID, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    for arm, v in rep['arms'].items():
        print('%-14s all_pass=%s' % (arm, v.get('all_pass')))
        for k in ('cp_prefill', 'cp_decode'):
            p_ = (v.get('selfcheck_pass') or {}).get(k) or {}
            print('    %-11s ok=%s elapsed=%s cos=%s'
                  % (k, p_.get('ok'), p_.get('elapsed_s'), p_.get('cosines')))
        print('    devices:', v.get('execution_devices'))
    print('反证组：%s' % json.dumps(rep.get('counterfactual'), ensure_ascii=False))
    print('证据：%s' % EVID)
    return 0 if rep['all_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
