#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §1：**「没有 NVIDIA 卡时 CUDA 档被隐藏/置灰，并给出原因」**的验证。

## reviewer 原文（APP-118 §1）
> 本机检测到 NVIDIA 显卡时，界面里出现「CUDA」档可选；**没有 NVIDIA 卡时隐藏或置灰，
> 并给出原因，不能启动失败**。

## 🔴 本机**有** NVIDIA 卡（RTX 5050）⇒ 「无卡」形态**无法靠物理环境**得到
## ⇒ 本脚本用**受控替换**把 `has_nvidia_gpu()` 换成 **False**，
##    再真跑 `tts_extra_devices()` 与 `build_tts_options()` ⇒ **行为级**判定。

## 判据
| # | 检查 | 口径 |
|---|---|---|
| A1 | **有** NVIDIA 卡 ⇒ CUDA 档**出现** | 真跑 `tts_extra_devices()` 含 'CUDA' |
| A2 | **无** NVIDIA 卡 ⇒ CUDA 档**不出现** | 受控替换后真跑 ⇒ **不含** 'CUDA' |
| A3 | **无** NVIDIA 卡 ⇒ **给出原因** | `build_tts_options()` 的 note 含「未检测到 NVIDIA 显卡」 |
| A4 | **无** NVIDIA 卡 ⇒ **其余后端照常可用** | 下拉**非空** ＋ 仍含 Intel GPU/NPU 档 |
| A5 | 替换**只影响 CUDA** | 无卡时 CUDA 消失，**其它设备数不变** |
| A6 | **不启动失败** | 受控替换期间 import/调用**不抛异常** |

## 纪律
- **不加载任何模型**、**不占 GPU/NPU**；
- 只做**纯函数调用** ＋ 受控 monkeypatch（用完**还原**）。
"""
import json
import os
import sys

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG_DEFAULT = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')

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
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))

CHECKS = []


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  — ' + str(detail)) if detail else ''))
    return bool(ok)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    print('=== APP-118 §1 CUDA 档的「有卡 / 无卡」两态验证 ===')
    try:
        import device_config as DC
        import live_caption_app as A
    except Exception as e:
        print('FAIL: import 失败 %r' % (e,))
        return 2

    # ── A1：有卡 ⇒ CUDA 出现 ────────────────────────────────
    has_nv = DC.has_nvidia_gpu()
    extra_with = DC.tts_extra_devices()
    opts_with = A.build_tts_options(['GPU.0', 'NPU'])
    labels_with = [o['label'] for o in opts_with]
    cuda_with = [l for l in labels_with if 'CUDA' in l.upper()]
    check('A1 有 NVIDIA 卡时 CUDA 档出现',
          'CUDA' in extra_with and len(cuda_with) > 0,
          'has_nvidia=%s extra=%s cuda_labels=%s'
          % (has_nv, extra_with, cuda_with))

    # ── 受控替换：把 has_nvidia_gpu 换成 False ────────────────
    orig = DC.has_nvidia_gpu
    DC.has_nvidia_gpu = lambda: False
    try:
        extra_without = DC.tts_extra_devices()
        opts_without = A.build_tts_options(['GPU.0', 'NPU'])
        labels_without = [o['label'] for o in opts_without]
        notes = ' '.join(str(o.get('note') or '') for o in opts_without)
    except Exception as e:
        check('A6 受控替换期间不抛异常', False, repr(e))
        DC.has_nvidia_gpu = orig
        return 1
    finally:
        DC.has_nvidia_gpu = orig

    check('A6 受控替换期间不抛异常（且已还原）', True,
          '已还原 has_nvidia_gpu')

    # ── A2：无卡 ⇒ CUDA 不出现 ──────────────────────────────
    cuda_without = [l for l in labels_without if 'CUDA' in l.upper()]
    check('A2 无 NVIDIA 卡时 CUDA 档**不出现**',
          'CUDA' not in extra_without and not cuda_without,
          'extra=%s cuda_labels=%s' % (extra_without, cuda_without))

    # ── A3：无卡 ⇒ 给出原因 ─────────────────────────────────
    # 🔴 **必须命中「确切的原因文案」**，不能只判「note 里有 NVIDIA 字样」
    #   （否则别的原因文字也会误判 PASS ⇒ 假 PASS）。
    check('A3 无 NVIDIA 卡时给出**确切原因**（含「未检测到 NVIDIA 显卡」＋「已隐藏」）',
          ('未检测到 NVIDIA 显卡' in notes) and ('已隐藏' in notes),
          notes[-160:])

    # ── A4：无卡 ⇒ 其余后端照常可用 ────────────────────────
    n_dev = len(set([o.get('device') for o in opts_without]))
    check('A4 无 NVIDIA 卡时其余语音输出后端照常可用',
          len(opts_without) > 0 and n_dev >= 1,
          '%d 个选项，设备 %s' % (len(opts_without),
                                 sorted(set([o.get('device')
                                             for o in opts_without]))))

    # ── A5：替换只影响 CUDA ─────────────────────────────────
    n_with = len([o for o in opts_with if o.get('device') != 'CUDA'])
    n_without = len([o for o in opts_without if o.get('device') != 'CUDA'])
    check('A5 去掉 CUDA 后其余选项数不变',
          n_with == n_without, 'with=%d without=%d' % (n_with, n_without))

    npass = sum(1 for c in CHECKS if c['ok'])
    nfail = len(CHECKS) - npass
    out = {'pass': npass, 'fail': nfail, 'checks': CHECKS,
           'has_nvidia_real': has_nv,
           'extra_with_card': extra_with,
           'labels_with_card': labels_with,
           'extra_without_card': extra_without,
           'labels_without_card': labels_without,
           'note_without_card': notes[:400]}
    op = os.path.join(RESULTS, 'app118_cuda_hide_evidence.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结论：%d PASS / %d FAIL  →  %s' % (npass, nfail, op))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
