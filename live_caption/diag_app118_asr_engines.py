#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §1 验收：**v2.5 里 ASR 引擎族是否正确**。

## 背景（**真缺陷，不是假想**）
`active_asr_engines()` 的旧实现是
``return ENGINES_ASR06B if _asr06b_models_present() else ENGINES``
⇒ **「有 0.6B 模型就只用 0.6B」**（二选一）。
⇒ APP-118 把 0.6B 的模型**也放进完整版 v2.5** 之后，
   这行会**把完整版从 R2T2 翻成 0.6B** ⇒ **违反 APP-118 §1**
   （「保留 Confucius4-R2T2 1.7B … **完整版默认仍用它，默认值不变**；
   同时带上 Qwen3-ASR 0.6B … **作为可选项**」）。

## 本脚本查什么（**行为级**，不是 grep）
| # | 检查 | 口径 |
|---|---|---|
| A1 | v2.5 的 ASR 引擎表**同时**含 R2T2 与 0.6B 两族 | 真跑 `active_asr_engines()` |
| A2 | **默认**仍是 R2T2 | `default_asr_engine_for_device('GPU.0')` 的 kind |
| A3 | 0.6B 是**可选项**（不是唯一） | 表里两族都在 |
| A4 | GUI 下拉 **label 全唯一** | 真跑 `build_asr_options()` ⇒ 重复 label = 静默错档 |
| A5 | 0.6B 的 label **能分辨**（带 0.6B 标记） | 不能与 R2T2 撞 |
| A6 | `--check` 能列出两族 | 真跑 `_check_models()` |
| B1 | MT 默认 = **INT8-CW** | `translator.DEFAULT_MODEL` |
| B2 | MT **INT4 仍可选** | `MT_ENGINES` 里有 int4 |
| B3 | 目标语言 **10 种** | `translator.TARGETS` |
| C1 | 包形态标记 = **full** | `package_profile.describe()` |
| C2 | `allow_cuda` / `allow_clone_voice` = True | 同上 |
| D1 | **CUDA 档只在有 NVIDIA 卡时出现** | 真跑 `tts_extra_devices()` + 硬件探测 |

## 纪律
- **不加载任何模型** ⇒ 不占 GPU/NPU；
- 只 import + 跑纯函数。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

_PKG_APP = None
for _i, _a in enumerate(sys.argv):
    if _a == '--pkg' and _i + 1 < len(sys.argv):
        _PKG_APP = os.path.join(sys.argv[_i + 1], 'app')
        break
    if _a.startswith('--pkg='):
        _PKG_APP = os.path.join(_a.split('=', 1)[1], 'app')
        break
if _PKG_APP and os.path.isdir(_PKG_APP):
    sys.path.insert(0, _PKG_APP)
    print('[pkg] 用**客户包内**的代码做验收：%s' % _PKG_APP)
else:
    sys.path.insert(0, HERE)

RESULTS = os.path.join(REPO, 'results', 'app')
CHECKS = []


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  — ' + str(detail)) if detail else ''))
    return bool(ok)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    print('=== APP-118 §1 验收（ASR 引擎族 / MT / 语种 / profile / CUDA）===')
    try:
        import live_caption_app as A
    except Exception as e:
        print('FAIL: import live_caption_app 失败 %r' % (e,))
        return 2

    table = A.active_asr_engines()
    kinds = {k: c.get('kind') for k, c in table.items()}
    print('  引擎表：%s' % json.dumps(kinds, ensure_ascii=False))

    # ── A1/A3：两族都在 ──────────────────────────────────────
    n_ov = sum(1 for v in kinds.values() if v in ('ov', 'npu'))
    n_06b = sum(1 for v in kinds.values() if v == 'asr06b')
    check('A1 v2.5 的 ASR 引擎表**同时**含 R2T2 与 0.6B 两族',
          n_ov > 0 and n_06b > 0, 'R2T2=%d 0.6B=%d' % (n_ov, n_06b))
    check('A3 0.6B 是**可选项**而不是唯一引擎', n_06b > 0 and n_ov > 0,
          'R2T2=%d 0.6B=%d' % (n_ov, n_06b))

    # ── A2：默认仍是 R2T2 ────────────────────────────────────
    try:
        dev_key = A.default_asr_engine_for_device('GPU.0')
        dev_kind = table.get(dev_key, {}).get('kind')
    except Exception as e:
        dev_key, dev_kind = 'err:%r' % (e,), 'err'
    check('A2 ASR **默认**仍是 R2T2（非 stateful）',
          dev_kind in ('ov', 'npu'), 'key=%s kind=%s' % (dev_key, dev_kind))

    # ── A4/A5：GUI label 全唯一 ──────────────────────────────
    try:
        devs = ['GPU.0', 'NPU']
        opts = A.build_asr_options(devs)
        labels = [o['label'] for o in opts]
        dup = sorted({x for x in labels if labels.count(x) > 1})
        print('  GUI ASR 下拉：%s' % json.dumps(labels, ensure_ascii=False))
    except Exception as e:
        labels, dup = [], ['err:%r' % (e,)]
    check('A4 GUI ASR 下拉 label **全唯一**（重复 = 静默错档）', not dup, dup)
    check('A5 0.6B 的 label 能与 R2T2 **分辨**',
          any('0.6B' in x or 'stateful' in x for x in labels), labels)

    # ── A6：--check 能列两族 ────────────────────────────────
    try:
        models = A._check_models()
        listed = sorted(models.keys())
    except Exception as e:
        listed = ['err:%r' % (e,)]
    check('A6 `--check` 的模型自检能列出两族',
          any('asr06b' in k for k in listed) and len(listed) >= 3,
          listed)

    # ── B1/B2：MT ───────────────────────────────────────────
    try:
        import translator as T
        mt_default = os.path.basename(os.path.normpath(T.DEFAULT_MODEL)).lower()
        mt_keys = list(T.MT_ENGINES.keys())
    except Exception as e:
        mt_default, mt_keys = 'err:%r' % (e,), []
    check('B1 MT 默认 = INT8-CW', 'int8sym-cw' in mt_default, mt_default)
    check('B2 MT **INT4 仍可选**',
          any('int4' in k for k in mt_keys), mt_keys)

    # ── B3：10 语种 ─────────────────────────────────────────
    try:
        import translator as T
        langs = [k for k in T.TARGETS if k != 'off']
    except Exception as e:
        langs = []
    check('B3 目标语言 = 10 种', len(langs) == 10, '%d 种 %s'
          % (len(langs), langs))

    # ── C1/C2：profile 标记 ─────────────────────────────────
    try:
        import package_profile as P
        desc = P.describe()
    except Exception as e:
        desc = {'err': repr(e)}
    check('C1 包形态 = full', desc.get('profile') == 'full', desc)
    check('C2 allow_cuda / allow_clone_voice = True',
          desc.get('allow_cuda') is True and
          desc.get('allow_clone_voice') is True, desc)

    # ── D1：CUDA 档与 NVIDIA 硬件 ───────────────────────────
    try:
        import device_config as DC
        extra = DC.tts_extra_devices()
        has_nv = DC.has_nvidia_gpu() if hasattr(DC, 'has_nvidia_gpu') else None
    except Exception as e:
        extra, has_nv = [], 'err:%r' % (e,)
    check('D1 CUDA 档的出现与 NVIDIA 硬件一致',
          ('CUDA' in extra) == bool(has_nv),
          'extra=%s has_nvidia=%s' % (extra, has_nv))

    npass = sum(1 for c in CHECKS if c['ok'])
    nfail = len(CHECKS) - npass
    out = {'pass': npass, 'fail': nfail, 'checks': CHECKS,
           'engine_kinds': kinds, 'asr_labels': labels,
           'profile': desc, 'tts_extra_devices': extra,
           'has_nvidia_gpu': has_nv}
    op = os.path.join(RESULTS, 'app118_asr_engines_evidence.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结论：%d PASS / %d FAIL  →  %s' % (npass, nfail, op))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
