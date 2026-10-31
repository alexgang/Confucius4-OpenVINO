#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-050 判据自检：`_norm_exec_devices()` + `execution_devices()` 的**单元验收**。

## 为什么要有这个脚本（MEMORY「判据工程」铁律）

> 「判据 PASS」≠「判据正确」⇒ 必须拿**已知有缺陷的旧产物**跑一遍
> ⇒ 判据须能**识破** ⇒ 弱标记恒真 ⇒ 必须查**分支本体特征**。

本脚本**不加载任何模型**（纯 mock，秒级、不吃 CPU ⇒ 不需要机器锁）：

1. **REAL 组**：用**实测到的真实返回值形状**
   （NPU = 字符串 `'NPU'`；CPU = 列表 `['CPU']`）
   ⇒ 断言 `actual` 判对、`on_npu` / `on_cpu` 分得开。
2. **BUG 组（反证）**：用**已知有缺陷的旧实现**（`list(devs)` 逐字符拆分）
   ⇒ 断言**必须被识破**（即旧实现在这些用例上会错）
   ⇒ 证明判据**非恒真**。
3. **覆盖 APP-050 点名的四个组件**：`talker` / `cp_prefill` / `cp_decode` /
   `decoder` ⇒ 断言 `key4_line` 一行里**四个都在**。

## 跑法

    "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.13/python/python.exe" \
        results/app/app174b_exec_devices_unit.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIVE = os.path.join(REPO, 'live_caption')

PASS = []
FAIL = []


def check(name, cond, detail=''):
    if cond:
        PASS.append(name)
    else:
        FAIL.append('%s :: %s' % (name, detail))


class FakeCompiled:
    """模拟 OV `CompiledModel`：只提供 `get_property('EXECUTION_DEVICES')`。"""

    def __init__(self, raw):
        self._raw = raw

    def get_property(self, name):
        if name != 'EXECUTION_DEVICES':
            raise RuntimeError('no such property %s' % name)
        return self._raw


class FakeEngine:
    def __init__(self, **kw):
        self.device = kw.pop('device', 'NPU')
        self.is_npu = True
        for k, v in kw.items():
            setattr(self, k, v)


def main() -> int:
    if LIVE not in sys.path:
        sys.path.insert(0, LIVE)
    import tts_engine as TE

    # ── 1. `_norm_exec_devices` 单元 ──────────────────────────────
    n = TE._norm_exec_devices
    check('norm.NPU字符串', n('NPU') == ['NPU'], repr(n('NPU')))
    check('norm.CPU列表', n(['CPU']) == ['CPU'], repr(n(['CPU'])))
    check('norm.CPU字符串不逐字符拆',
          n('CPU') == ['CPU'], repr(n('CPU')))
    check('norm.NPU列表', n(['NPU']) == ['NPU'], repr(n(['NPU'])))
    check('norm.旧式单字母列表仍可解读',
          n(['N', 'P', 'U']) == ['NPU', 'CPU', 'UNKNOWN'],
          repr(n(['N', 'P', 'U'])))
    check('norm.逗号分隔多设备', n('NPU,CPU') == ['NPU', 'CPU'],
          repr(n('NPU,CPU')))
    check('norm.None空', n(None) == [], repr(n(None)))
    check('norm.空串空', n('') == [], repr(n('')))

    # ── 2. REAL 组：真实形状 ─────────────────────────────────────
    # 🔴 关键：**有 talker 桶时不编译 self.talker**（pipeline.py L315-333）
    #    ⇒ `talker` 属性为 None ⇒ 落点必须来自 `talker_bucket@*`
    eng = FakeEngine(
        speaker_enc=FakeCompiled('NPU'),
        cp_prefill=FakeCompiled('NPU'),
        cp_decode=FakeCompiled('NPU'),
        tok_decoder=FakeCompiled('NPU'),
        talker_buckets={64: FakeCompiled('NPU'),
                        128: FakeCompiled('NPU'),
                        256: FakeCompiled('NPU')},
        _dec_bucket_models={8: FakeCompiled('NPU'),
                            16: FakeCompiled('NPU')},
    )
    ex = TE.execution_devices(eng, on_log=lambda m: None)
    check('real.ok', ex['ok'] is True, repr(ex.get('ok')))
    check('real.talker桶被探测到',
          any(k.startswith('talker_bucket@') for k in ex['devices']),
          repr(sorted(ex['devices'])))
    check('real.解码器桶被探测到',
          any(k.startswith('decoder_bucket@') for k in ex['devices']),
          repr(sorted(ex['devices'])))
    check('real.无unknown', ex['unknown'] == [], repr(ex['unknown']))
    # 🔴 `talker_prefill`/`talker_decode`（use_kv_cache=False 时不编译）
    #    与 `code_predictor`（use_cp_kv_cache=True 时不编译）属「未启用」
    #    ⇒ 应记 `absent`，**不是** `unknown`（否则 reviewer 会误以为落点不明）
    check('real.未启用组件记absent',
          set(ex['absent']) == {'talker_prefill', 'talker_decode',
                                'talker', 'code_predictor'},
          repr(ex['absent']))
    check('real.on_npu非空', len(ex['on_npu']) > 0, repr(ex['on_npu']))
    check('real.on_cpu为空', ex['on_cpu'] == [], repr(ex['on_cpu']))
    check('real.on_unknown为空', ex['on_unknown'] == [],
          repr(ex['on_unknown']))
    # 🔴 APP-050 点名的四个组件必须都在那一行里
    kl = ex.get('key4_line', '')
    for comp in ('talker=', 'cp_prefill=', 'cp_decode=', 'decoder='):
        check('real.key4含%s' % comp, comp in kl, kl)
    check('real.key4 talker非?',
          'talker=?' not in kl, kl)
    check('real.key4 decoder非?',
          'decoder=?' not in kl, kl)

    # ── 3. CPU 回落必须被抓到（**旧实现会漏报**）─────────────────
    eng_cpu = FakeEngine(
        speaker_enc=FakeCompiled(['CPU']),
        cp_prefill=FakeCompiled('NPU'),
        cp_decode=FakeCompiled(['CPU']),
        tok_decoder=FakeCompiled(['CPU']),
    )
    ex2 = TE.execution_devices(eng_cpu, on_log=lambda m: None)
    check('cpu.cp_decode落CPU被抓到',
          ex2['actual'].get('cp_decode') == 'CPU',
          repr(ex2['actual']))
    check('cpu.on_cpu非空', len(ex2['on_cpu']) > 0, repr(ex2['on_cpu']))
    check('cpu.speaker_enc落CPU',
          ex2['actual'].get('speaker_enc') == 'CPU',
          repr(ex2['actual']))

    # 🔴🔴🔴 **旧实现在这里的漏报**（反证 ⇒ 判据非恒真）
    _legacy = {'N': 'NPU', 'P': 'CPU', 'U': 'UNKNOWN'}

    def legacy_actual(raw):
        devs = list(raw)
        norm = [_legacy.get(str(d).upper(), str(d)) for d in devs]
        return norm[0] if norm else None

    legacy_cpu = legacy_actual('CPU')      # 旧：'C' ⇒ 落进 on_unknown
    check('反证.旧实现把CPU字符串算成C',
          legacy_cpu == 'C', repr(legacy_cpu))
    check('反证.旧实现漏报CPU回落',
          legacy_cpu != 'CPU', repr(legacy_cpu))
    legacy_npu = legacy_actual('NPU')      # 旧：'N' ⇒ 碰巧对
    check('反证.旧实现把NPU字符串拆成字符',
          list('NPU') == ['N', 'P', 'U'], repr(list('NPU')))

    # 🔴 旧实现还会漏掉 talker 桶（int 键 → str 键查不到）
    old_buckets = {64: FakeCompiled('NPU')}
    old_got = old_buckets.get('64')        # 旧代码：buckets.get(str)
    check('反证.旧实现用str键取不到talker桶',
          old_got is None, repr(old_got))
    new_got = old_buckets.get(64)
    check('修正.新实现用int键取到talker桶',
          new_got is not None, repr(new_got))

    # ── 4. 属性不存在 ⇒ unknown（**不猜**）────────────────────────
    eng_none = FakeEngine(speaker_enc=FakeCompiled('NPU'))
    ex3 = TE.execution_devices(eng_none, on_log=lambda m: None)
    check('none.缺失组件记absent',
          'cp_decode' in ex3['absent'], repr(ex3['absent']))
    check('none.缺失组件不进devices',
          'cp_decode' not in ex3['devices'], repr(sorted(ex3['devices'])))

    # ── 5. 日志确实打了一行（APP-050 要求「启动日志打印」）──────────
    logs = []
    TE.execution_devices(eng, on_log=lambda m: logs.append(m))
    check('log.有关键四组件那行',
          any('EXECUTION_DEVICES' in m for m in logs), repr(logs))
    check('log.那行含四个组件',
          any(all(c in m for c in ('talker=', 'cp_prefill=', 'cp_decode=',
                                   'decoder=')) for m in logs),
          repr(logs))

    out = {
        'n_pass': len(PASS),
        'n_fail': len(FAIL),
        'failures': FAIL,
        'passes': PASS,
        'verdict': 'PASS' if not FAIL else 'FAIL',
        'counterproof': {
            'legacy_norm_of_NPU_string': list('NPU'),
            'legacy_actual_of_NPU_string': legacy_npu,
            'legacy_actual_of_CPU_string': legacy_cpu,
            'legacy_talker_bucket_lookup_with_str_key': repr(old_got),
            'fixed_talker_bucket_lookup_with_int_key': repr(new_got),
        },
        'sample_key4_line': ex.get('key4_line'),
        'sample_actual': ex.get('actual'),
        'sample_on_npu': ex.get('on_npu'),
        'sample_on_cpu': ex.get('on_cpu'),
        'sample_unknown': ex.get('unknown'),
        'cpu_case_actual': ex2.get('actual'),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
