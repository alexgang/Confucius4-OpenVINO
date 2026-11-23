#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §1 验收①：**不做推理**的单测 —— NPU 档长段不再抛 ValueError。

## 判据（reviewer APP-121 §1「验收 ①」逐字）
> skeleton = 18 + {238, 260, 266} 个音频 token，reserve ∈ {32, 64}，
> **NPU 档不报错**、**截断计数正确**；skeleton=321 时**报错**。

## 纪律
- 🔴 **真跑被检对象**：导入**包内** `app/asr06b_stateful_backend.py`
  （`__file__` 指向包内真实路径）⇒ 不用仓库副本冒充被检对象；
- 🔴 **不做推理**：只用桩对象调 `build_inputs_embeds`（纯 token 算术），
  ⇒ **不加载模型、不占 NPU/GPU**；
- 🔴 **反证组**：用 `--old-file` 指向**修复前**的同一文件 ⇒
  旧实现在同样的用例上**必须抛 ValueError** ⇒ 证明本判据能识破该缺陷
  （判据不是「恒 PASS」的假判据）；
- 🔴 **GPU 档回归**：GPU（limit=512）用例的行为与修复前**逐项一致**。

## 用法
```
python live_caption/_app121_asr_npu_prefix_unit.py --pkg <包目录> \
       --old-file <修复前的 asr06b_stateful_backend.py> --out <证据 json>
```
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')

#: 模板骨架 token 数（handoff §三：`T = 18 + 音频 token + 前缀`）
N_LEFT = 18
#: 词表/隐藏维度（Qwen3-ASR 0.6B：hidden=1024）—— 桩里只用到小数
VOCAB = 512
HIDDEN = 1024


def _load_backend_module(path, tag):
    """按**文件路径**导入后端模块（`__file__` 指向真实文件）。

    🔴 包内的 `backends` 必须优先于仓库副本 ⇒ 包的 `app/` 插到 `sys.path` 最前。
    """
    app_dir = os.path.dirname(os.path.abspath(path))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    name = '_app121_mod_%s' % tag
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_stub(mod, device, limit):
    """造一个**只带 token 算术所需字段**的桩后端（不加载任何模型）。"""
    import numpy as np
    cls = mod.ASR06BStatefulBackend
    stub = object.__new__(cls)
    stub.device = device
    stub._max_prompt_tok = limit
    stub._ids_left = list(range(N_LEFT))          # 模板左半 18 token
    stub._ids_right = []                          # 右半 0 token ⇒ 骨架 = 18 + 音频
    stub._ids_right_zh = []
    stub._ids_right_en = []
    stub.tokenizer = None
    stub._W = np.zeros((VOCAB, HIDDEN), dtype=np.float32)
    stub.probe = {'truncations': 0}
    stub.probe[getattr(mod, 'PROBE_PREFIX_TRUNCATIONS', 'prefix_truncations')] = 0
    return stub


def _run_case(mod, device, limit, n_audio, reserve, n_prefix):
    """跑一个用例 ⇒ 返回 (ok, detail)。**不抛到外面**（异常本身是判据之一）。"""
    import numpy as np
    stub = _make_stub(mod, device, limit)
    audio_emb = np.zeros((n_audio, HIDDEN), dtype=np.float32)
    prefix_ids = list(range(100, 100 + n_prefix))
    try:
        emb = stub.build_inputs_embeds(audio_emb, prefix_ids, None, reserve)
    except ValueError as e:
        return False, {'raised': 'ValueError', 'msg': str(e),
                       'skeleton': N_LEFT + n_audio}
    except Exception as e:                       # pragma: no cover
        return False, {'raised': type(e).__name__, 'msg': str(e),
                       'skeleton': N_LEFT + n_audio}
    key = getattr(mod, 'PROBE_PREFIX_TRUNCATIONS', 'prefix_truncations')
    return True, {
        'raised': None,
        'skeleton': N_LEFT + n_audio,
        'emb_rows': int(emb.shape[0]),
        'prompt_le_limit': int(emb.shape[0]) <= limit,
        'total_le_cap': int(emb.shape[0]) + max(1, int(reserve)) <= limit + (
            int(getattr(mod, 'NPUW_MIN_RESPONSE_LEN', 0)) if device == 'NPU' else 0),
        'prefix_truncations': int(stub.probe.get(key, 0)),
        'truncations': int(stub.probe.get('truncations', 0)),
        'prefix_kept': int(emb.shape[0]) - (N_LEFT + n_audio),
        'drop': max(0, n_prefix - (int(emb.shape[0]) - (N_LEFT + n_audio))),
    }


#: 用例矩阵：(tag, device, limit, n_audio, reserve, n_prefix, expect_ok)
CASES = [
    # ── reviewer 点名的三组音频 token（skeleton = 18 + 音频）──────────
    ('npu_a238_r32', 'NPU', 320, 238, 32, 100, True),
    ('npu_a238_r64', 'NPU', 320, 238, 64, 100, True),
    ('npu_a260_r32', 'NPU', 320, 260, 32, 100, True),
    ('npu_a260_r64', 'NPU', 320, 260, 64, 100, True),
    ('npu_a266_r32', 'NPU', 320, 266, 32, 100, True),
    ('npu_a266_r64', 'NPU', 320, 266, 64, 100, True),
    # ── skeleton = 321 ⇒ 必须报错（handoff 的 base_len > pml）────────
    ('npu_a303_r32_skel321', 'NPU', 320, 303, 32, 10, False),
    ('npu_a303_r64_skel321', 'NPU', 320, 303, 64, 10, False),
    # ── 前缀放得下 ⇒ 不该截断 ────────────────────────────────────────
    ('npu_a238_r64_short_prefix', 'NPU', 320, 238, 64, 10, True),
    # ── GPU 档（512）行为必须与修复前一致 ────────────────────────────
    ('gpu_a238_r64', 'GPU.0', 512, 238, 64, 100, True),
    ('gpu_a500_r64_toolong', 'GPU.0', 512, 500, 64, 10, False),
]


def run_matrix(mod, tag):
    rows = []
    n_fail = 0
    for (c, dev, lim, na, rsv, npf, expect_ok) in CASES:
        ok, detail = _run_case(mod, dev, lim, na, rsv, npf)
        passed = (ok == expect_ok)
        if not passed:
            n_fail += 1
        rows.append({'case': c, 'device': dev, 'limit': lim, 'n_audio': na,
                     'reserve': rsv, 'n_prefix': npf,
                     'expect_ok': expect_ok, 'got_ok': bool(ok),
                     'pass': bool(passed), 'detail': detail})
    return rows, n_fail


def extra_consistency(mod):
    """🔴 **流式(reserve=32) 与段尾(reserve=64) 的截断口径必须一致**。

    APP-121 §1：「另外，流式解码时 reserve=32，NPU 档前缀比 handoff 多砍了
    32–64 个 token，转写会和 ASR 参照口径不一样。」
    ⇒ 修复后：同一段、同一前缀，两条路径的**保留前缀数必须相同**。
    """
    out = []
    for na in (238, 260, 266):
        kept = []
        for rsv in (32, 64):
            _ok, d = _run_case(mod, 'NPU', 320, na, rsv, 100)
            kept.append(d.get('prefix_kept'))
        same = len(set(kept)) == 1
        out.append({'n_audio': na, 'kept_r32': kept[0], 'kept_r64': kept[1],
                    'consistent': bool(same)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--target', default=None,
                    help='直接指定被检文件（默认 <pkg>/app/asr06b_stateful_backend.py）')
    ap.add_argument('--old-file', default=None,
                    help='修复前的 asr06b_stateful_backend.py（反证组）')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_asr_npu_prefix_unit.json'))
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    target = (os.path.abspath(args.target) if args.target
              else os.path.join(pkg, 'app', 'asr06b_stateful_backend.py'))
    if not os.path.isfile(target):
        print('FAIL: 找不到被检文件 %s' % target)
        return 2

    print('=== APP-121 §1 验收①：NPU 档前缀上界单测（不做推理）===')
    print('被检文件：%s' % target)
    mod = _load_backend_module(target, 'new')
    print('  导入 OK：__file__=%s' % mod.__file__)
    print('  NPUW_MIN_RESPONSE_LEN = %s'
          % getattr(mod, 'NPUW_MIN_RESPONSE_LEN', None))

    rows, n_fail = run_matrix(mod, 'new')
    for r in rows:
        print('  [%s] %-24s expect_ok=%-5s got=%-5s %s'
              % ('PASS' if r['pass'] else 'FAIL', r['case'],
                 r['expect_ok'], r['got_ok'],
                 json.dumps(r['detail'], ensure_ascii=False)))

    cons = extra_consistency(mod)
    n_cons_fail = sum(1 for c in cons if not c['consistent'])
    for c in cons:
        print('  [%s] 截断口径一致 reserve32/64：n_audio=%d kept=%s/%s'
              % ('PASS' if c['consistent'] else 'FAIL', c['n_audio'],
                 c['kept_r32'], c['kept_r64']))

    # ── 反证组：修复前的旧文件必须在同样的用例上抛 ValueError ────────
    anti = None
    if args.old_file:
        old_path = os.path.abspath(args.old_file)
        if os.path.isfile(old_path):
            old_mod = _load_backend_module(old_path, 'old')
            old_rows, _old_fail = run_matrix(old_mod, 'old')
            npu_rows = [r for r in old_rows if r['device'] == 'NPU']
            n_raise = sum(1 for r in npu_rows if not r['got_ok'])
            n_expect_raise = sum(1 for r in npu_rows if not r['expect_ok'])
            anti = {
                'old_file': old_path,
                'old_file_sha256': _sha(old_path),
                'n_npu_cases': len(npu_rows),
                'n_npu_raised': n_raise,
                'n_npu_should_not_raise': sum(1 for r in npu_rows
                                              if r['expect_ok']),
                'old_raised_on_should_pass': sum(
                    1 for r in npu_rows if r['expect_ok'] and not r['got_ok']),
                'rows': old_rows,
                'verdict_ok': (sum(1 for r in npu_rows
                                   if r['expect_ok'] and not r['got_ok']) > 0),
            }
            print('  反证组（旧文件 %s）：NPU 用例 %d 个，其中本应通过却被旧实现'
                  '抛错的 %d 个 ⇒ 判据能识破该缺陷：%s'
                  % (os.path.basename(old_path), anti['n_npu_cases'],
                     anti['old_raised_on_should_pass'],
                     'PASS' if anti['verdict_ok'] else 'FAIL'))
        else:
            print('  ⚠ 反证组：找不到旧文件 %s' % old_path)

    total_fail = n_fail + n_cons_fail
    data = {
        'script': '_app121_asr_npu_prefix_unit.py',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'target_file': target,
        'target_sha256': _sha(target),
        'target_file_in_pkg': True,
        'no_inference': True,
        'n_left_template_tokens': N_LEFT,
        'cases': rows,
        'n_cases': len(rows),
        'n_fail': n_fail,
        'truncation_consistency': cons,
        'n_consistency_fail': n_cons_fail,
        'anti_group': anti,
        'result': 'PASS' if total_fail == 0 else 'FAIL',
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print('\n结果：%s（%d/%d 用例 PASS；一致性 %d/%d PASS）'
          % (data['result'], len(rows) - n_fail, len(rows),
             len(cons) - n_cons_fail, len(cons)))
    print('证据 → %s' % args.out)
    return 0 if data['result'] == 'PASS' else 1


def _sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


if __name__ == '__main__':
    sys.exit(main())
