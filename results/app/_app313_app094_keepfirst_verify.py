#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app313_app094_keepfirst_verify.py —— **APP-094① 的行为判据验证**。

## 判据（reviewer 的验收标准）

> 每个说话人在累计到 >=3 s 干净且已标注说话人的语音时注册他的**第一份**
> x-vector 参考，之后**一直沿用这份**，**不再在 8 s 升级/替换**。
> 做成可配置项，**默认 = "keep first"**；旧的升级行为作为可选项保留。
> 验收：在 STATUS 里报告**每个说话人的参考注册记录**
> （说话人、注册时刻、累计秒数）——**每个说话人恰好注册一次**，
> 没有第二次注册/升级。

## 🔴 本脚本怎么判（不能只测「没报错」）

**反证组必须能识破**：如果有人把闸门去掉（恢复旧的 8 s 升级），
本脚本**必须判 FAIL**。⇒ 所以脚本跑**两组**：

| 组 | `LIVECAP_XV_UPGRADE` | 期望 |
|---|---|---|
| **默认组** | 不设（⇒ 默认） | **恰好注册一次**（`count == 1`） |
| **反证组** | `=1`（⇒ 旧的升级行为） | **可以注册两次**（`count >= 2`）⇒ 证明闸门真的起作用 |

⚠️ **反证组必须能被识破** ⇒ 若反证组也只注册一次 ⇒ 说明升级路径根本没被触发
⇒ 判据无效（不能据此说「闸门有效」）。

## 用法

```
.venv/Scripts/python.exe results/app/_app313_app094_keepfirst_verify.py
```
"""
from __future__ import annotations

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

OUT = os.path.join(HERE, 'app313_app094_keepfirst_evidence.json')


def build_case(upgrade_env: bool):
    """造一个「同一说话人逐渐攒够 3 s → 8 s → 12 s」的场景。

    🔴 **用公开 API 构造**（`note_final` → `xv_reference_ticket`）⇒
    判的是**真代码路径**（合格段门槛、切换点守卫、连续时长都真实生效）。
    ⚠️ 第一版夹具直接塞私有表 ⇒ 状态机全程 'wait' ⇒ **判据无效**
    （已被自测识破 ⇒ 本版必须走公开 API）。
    """
    import speaker_voice

    sv = speaker_voice.SpeakerVoiceTable(on_event=lambda k, p: None)
    spk = 'S1'

    def feed(seg: int, a: float, b: float):
        """喂一段「干净 + 有标签 + 高置信」的语音（走 `note_final`）。"""
        sv.note_final(seg, spk, clean_ranges=[(a, b)], spk_conf=0.9)

    results = []

    # ── 阶段 1：攒到 3.2 s ⇒ 期望 'first' ──────────────────────
    feed(0, 0.0, 3.2)
    r1 = sv.xv_reference_ticket(spk)
    results.append({'stage': 'acc_3.2s', 'state': r1[3], 'total_s': r1[2]})
    if r1[3] == 'first':
        sv.mark_xv_registered(spk, r1[2], upgraded=False)
        sv._table[spk]['voice'] = 'clone'

    # ── 阶段 2：攒到 8.5 s（够升级门槛 8 s）────────────────────
    feed(1, 3.2, 8.5)
    r2 = sv.xv_reference_ticket(spk)
    results.append({'stage': 'acc_8.5s', 'state': r2[3], 'total_s': r2[2]})
    if r2[3] == 'upgrade':
        sv.mark_xv_registered(spk, r2[2], upgraded=True)
        sv._table[spk]['voice'] = 'clone'

    # ── 阶段 3：攒到 12 s ──────────────────────────────────────
    feed(2, 8.5, 12.0)
    r3 = sv.xv_reference_ticket(spk)
    results.append({'stage': 'acc_12s', 'state': r3[3], 'total_s': r3[2]})
    if r3[3] == 'upgrade':
        sv.mark_xv_registered(spk, r3[2], upgraded=True)
        sv._table[spk]['voice'] = 'clone'

    recs = sv.xv_registration_records()
    return {'stages': results, 'records': recs,
            'n_records': len(recs),
            'max_count': max([r['count'] for r in recs], default=0),
            'upgrade_flag': speaker_voice.XV_UPGRADE}


def run_group(upgrade_env: bool):
    """在**子进程**里跑（环境变量必须在 import 前设定）。"""
    import subprocess
    env = dict(os.environ)
    if upgrade_env:
        env['LIVECAP_XV_UPGRADE'] = '1'
    else:
        env.pop('LIVECAP_XV_UPGRADE', None)
    code = (
        "import json,sys,os;"
        "sys.path.insert(0, %r);"
        "sys.argv=['x'];"
        "import importlib.util;"
        "spec=importlib.util.spec_from_file_location('v', %r);"
        "m=importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(m);"
        "print(json.dumps(m.build_case(%r), ensure_ascii=False))"
        % (os.path.join(REPO, 'live_caption'), os.path.abspath(__file__),
           upgrade_env))
    p = subprocess.run([sys.executable, '-c', code], env=env,
                       capture_output=True, text=True, cwd=REPO)
    if p.returncode != 0:
        return {'error': p.stderr[-2000:], 'rc': p.returncode}
    line = [x for x in p.stdout.strip().split('\n') if x.startswith('{')]
    if not line:
        return {'error': 'no json output', 'stdout': p.stdout[-2000:]}
    return json.loads(line[-1])


def main():
    ev = {
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'correction': 'APP-094 (1)',
        'cases': {},
        'checks': [],
    }

    default = run_group(False)
    counter = run_group(True)
    ev['cases']['default_keep_first'] = default
    ev['cases']['counterexample_upgrade_on'] = counter

    def chk(name, cond, detail):
        ev['checks'].append({'name': name, 'pass': bool(cond), 'detail': detail})

    # ① 默认组：XV_UPGRADE 必须是 False
    chk('default_flag_is_keep_first',
        default.get('upgrade_flag') is False,
        'XV_UPGRADE=%r（期望 False）' % default.get('upgrade_flag'))

    # ② 默认组：每个说话人恰好注册一次
    chk('default_exactly_once',
        default.get('max_count') == 1 and default.get('n_records') == 1,
        'n_records=%r max_count=%r（期望 1 / 1）'
        % (default.get('n_records'), default.get('max_count')))

    # ③ 默认组：状态机全程 never 'upgrade'
    states = [s.get('state') for s in default.get('stages', [])]
    chk('default_no_upgrade_state', 'upgrade' not in states, 'states=%r' % states)

    # ④ 默认组：注册记录含「说话人 / 注册时刻 / 累计秒数」
    recs = default.get('records') or []
    has_fields = bool(recs) and all(
        r.get('spk') is not None and r.get('registered_at') is not None
        and r.get('total_s') is not None for r in recs)
    chk('default_record_fields', has_fields, 'records=%r' % recs)

    # ⑤ 🔴 反证组：升级开关打开后**必须能**注册两次
    #    （否则说明升级路径根本没被触发 ⇒ 判据无效）
    chk('counterexample_detects_upgrade',
        counter.get('max_count', 0) >= 2,
        'counter max_count=%r（期望 >=2 ⇒ 闸门真的起作用）'
        % counter.get('max_count'))

    ev['n_pass'] = sum(1 for c in ev['checks'] if c['pass'])
    ev['n_fail'] = sum(1 for c in ev['checks'] if not c['pass'])
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    for c in ev['checks']:
        print('[%s] %s — %s' % ('PASS' if c['pass'] else 'FAIL',
                                c['name'], c['detail']))
    print('verdict=%s (%d pass / %d fail) -> %s'
          % (ev['verdict'], ev['n_pass'], ev['n_fail'], OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
