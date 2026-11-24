#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 验收：从**整链实跑**的桥接 stderr 里抽出 code predictor 自检证据。

reviewer APP-130「验收」明文：

> A 机（NPU 正常机型）：自检通过、cp 仍在 NPU，10 分钟整链数字与上一轮同口径
> （不得变差）；**报自检耗时**。

## 为什么单独一个脚本

🔴 **自检日志在 `bridge.err`（stderr）里**，不在 `bridge.log`（stdout）——
   上一版链脚本只从 stdout 抓关键字 ⇒ **自检证据会漏**。
⇒ 本脚本**专门**扫每个臂目录的 `bridge.err`，抽出：

- `cp_prefill: NPU 自检通过（耗时 X s，用例 [...]）` ⇒ 耗时 + 逐用例余弦
- `cp_decode:  NPU 自检通过（耗时 X s，用例 [...]）`
- `EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，…` ⇒ 落点
- `落点统计：NPU 上 N 个组件 [...]；CPU 上 M 个组件 [...]` ⇒ cp 是否留在 NPU
- 自检失败分支（若有）：`NPU 自检失败（原因）⇒ 留在 CPU`

## 判据（真不变量，不是「看着像」）

1. 自检**通过** ⇒ 必须有「NPU 自检通过」行 **且** 三个用例余弦都 ≥ 0.99；
2. 自检**耗时** < 1 s（reviewer：「应在 1 s 内」）；
3. `cp_prefill` / `cp_decode` 的落点**仍是 NPU**（⇒ 没被打回 CPU）；
4. 落点统计里 **CPU 上组件数 == 0**；
5. **反证组**：脚本同时扫 `NPU 自检失败` 分支 ⇒ 一旦出现就判 FAIL
   （防「只抓到通过行」的假 PASS）。

## 用法

    python results/app/_app129_selfcheck_evidence.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
ARM_ROOT = os.path.join(HOME, 'shared', 'bgkeep', 'e2e_v26')

#: reviewer 明文：与 CPU 的余弦下限
COS_MIN = 0.99
#: reviewer 明文：自检耗时「应在 1 s 内」
MAX_ELAPSED_S = 1.0

#: 🔴 原文用的是**全角**括号（（ ））⇒ 正则必须照抄全角，否则恒不匹配
RE_OK = re.compile(r'cp_(prefill|decode):\s*NPU 自检通过（耗时\s*([0-9.]+)\s*s'
                   r'[，,]\s*用例\s*\[(.*?)\]）')
RE_FAIL = re.compile(r'cp_(prefill|decode):\s*NPU 自检失败（(.*?)）⇒ 留在 CPU')
RE_COS = re.compile(r'\(([0-9.]+),\s*([0-9.]+)\)')
#: 🔴 **抓整行**（原版用非贪婪 + `，` 结尾 ⇒ 只截到第一个逗号 ⇒ 假 FAIL）
RE_EXEC = re.compile(r'EXECUTION_DEVICES\s*([^\r\n]+)')
RE_LAND = re.compile(r'落点统计：NPU 上 (\d+) 个组件 (\[.*?\])；CPU 上 (\d+) 个组件 (\[.*?\])')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


def scan_arm(arm_dir):
    err = os.path.join(arm_dir, 'bridge.err')
    if not os.path.isfile(err):
        return None
    txt = open(err, encoding='utf-8', errors='replace').read()
    rec = {'err_file': err, 'err_bytes': os.path.getsize(err),
           'err_sha256': sha256(err)}
    # ── 通过分支 ──────────────────────────────────────────────────
    ok = {}
    for m in RE_OK.finditer(txt):
        # 🔴🔴 **组号坑**：正则里 `cp_(prefill|decode)` 的 group(1) 只是
        #   `prefill` / `decode`（**不含 `cp_` 前缀**）⇒ 首版直接拿 group(1)
        #   当键 ⇒ `ok.get('cp_prefill')` 永远 None ⇒ **假 FAIL**。
        #   ⇒ 统一补回前缀（键名与 reviewer 文案一致：cp_prefill / cp_decode）。
        which = 'cp_' + m.group(1)
        elapsed, cases = float(m.group(2)), m.group(3)
        cos = [float(c[1]) for c in RE_COS.findall(cases)]
        ok[which] = {'ok': True, 'elapsed_s': elapsed,
                     'cosines': cos, 'raw_case_str': cases,
                     'line': m.group(0).strip()}
    rec['selfcheck_pass'] = ok
    # ── 失败分支（反证组）─────────────────────────────────────────
    fail = {}
    for m in RE_FAIL.finditer(txt):
        fail['cp_' + m.group(1)] = {'reason': m.group(2),
                                    'line': m.group(0).strip()}
    rec['selfcheck_fail'] = fail
    # ── 设备落点 ──────────────────────────────────────────────────
    me = RE_EXEC.search(txt)
    rec['execution_devices'] = me.group(1).strip() if me else None
    ml = RE_LAND.search(txt)
    if ml:
        rec['landing'] = {'npu_n': int(ml.group(1)),
                          'npu_list': ml.group(2),
                          'cpu_n': int(ml.group(3)),
                          'cpu_list': ml.group(4)}
    else:
        rec['landing'] = None
    # ── 判定 ──────────────────────────────────────────────────────
    checks = []
    for which in ('cp_prefill', 'cp_decode'):
        s = ok.get(which)
        checks.append({
            'name': '%s 自检有「通过」记录' % which,
            'ok': bool(s), 'detail': (s or {}).get('line', '无')})
        if s:
            checks.append({'name': '%s 自检耗时 < %.1f s' % (which, MAX_ELAPSED_S),
                           'ok': s['elapsed_s'] < MAX_ELAPSED_S,
                           'detail': '%.3f s' % s['elapsed_s']})
            checks.append({'name': '%s 逐用例余弦全 ≥ %.2f' % (which, COS_MIN),
                           'ok': bool(s['cosines']) and all(c >= COS_MIN for c in s['cosines']),
                           'detail': str(s['cosines'])})
        checks.append({'name': '%s 无「自检失败」记录（反证组）' % which,
                       'ok': which not in fail,
                       'detail': (fail.get(which) or {}).get('line', '无')})
    ed = rec.get('execution_devices') or ''
    for which in ('cp_prefill', 'cp_decode'):
        checks.append({'name': '%s 落点仍是 NPU' % which,
                       'ok': ('%s=NPU' % which) in ed.replace(' ', ''),
                       'detail': ed or '未取到'})
    land = rec.get('landing')
    checks.append({'name': '落点统计 CPU 上组件数 == 0',
                   'ok': bool(land) and land['cpu_n'] == 0,
                   'detail': (('NPU %d 个 / CPU %d 个' % (land['npu_n'], land['cpu_n']))
                              if land else '未取到')})
    rec['checks'] = checks
    rec['all_pass'] = all(c['ok'] for c in checks)
    return rec


def main():
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'arm_root': ARM_ROOT, 'arms': {}, 'criteria': {
               'cos_min': COS_MIN, 'max_elapsed_s': MAX_ELAPSED_S}}
    arms = []
    if os.path.isdir(ARM_ROOT):
        arms = sorted(d for d in os.listdir(ARM_ROOT)
                      if os.path.isdir(os.path.join(ARM_ROOT, d))
                      and d.startswith('bgkeep_'))
    any_ok = False
    for a in arms:
        r = scan_arm(os.path.join(ARM_ROOT, a))
        if r:
            rep['arms'][a] = r
            log('臂 %s：自检 %s（%d 项判据）'
                % (a, 'PASS' if r['all_pass'] else 'FAIL', len(r['checks'])))
            for c in r['checks']:
                log('   [%s] %s — %s' % ('PASS' if c['ok'] else 'FAIL',
                                          c['name'], c['detail']))
            any_ok = any_ok or r['all_pass']
    rep['any_arm_pass'] = bool(any_ok)
    outp = os.path.join(RESULTS, 'app129_selfcheck_evidence.json')
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % outp)
    log('总结：%s' % ('PASS' if any_ok else 'FAIL（未取到自检通过记录）'))
    return 0 if any_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
