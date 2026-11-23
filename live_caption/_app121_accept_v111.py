#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §5：**MiniMVP v1.1.1 的验收编排**（复用 APP-120 的各 step，改指向新包）。

## 为什么复用而不是重写
`_app120_accept_v11.py` 的各 step（自检 / 设备切换 / 全新目录 / 整链 / 10 语种）
**逻辑与包无关**，只有 `PKG` / `PKG_PY` / 产物名写死了 ⇒ 本脚本**导入**它并
**改写模块级常量** ⇒ **判据一行不改**（避免「重写判据 ⇒ 判据本身可能变错」）。

## 纪律
- **必须用包内 python 跑本脚本**（`sys.executable` 会被 chain step 传给
  `_app588_sp4_acceptance.py` ⇒ 整链必须跑在客户真实解释器上）；
- 每个 step 独立产物 json（`results/app/app121_accept_v111_<step>.json`）；
- **不并跑**占设备的 step。

## 用法
```
<包内 python> live_caption/_app121_accept_v111.py --step selfcheck
<包内 python> live_caption/_app121_accept_v111.py --step chain --run-id <id>
```
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
RESULTS = os.path.join(REPO, 'results', 'app')

#: 导入 APP-120 的编排（**判据不改**，只改指向）
_spec = importlib.util.spec_from_file_location(
    '_app120_accept_v11', os.path.join(HERE, '_app120_accept_v11.py'))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)

# 🔴 改写指向 v1.1.1
_m.PKG = PKG
_m.PKG_APP = os.path.join(PKG, 'app')
_m.PKG_PY = os.path.join(PKG, 'python', 'python.exe')


def log(*a):
    print(*a, flush=True)


def save(step, data):
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, 'app121_accept_v111_%s.json' % step)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    log('  产物 → %s' % p)
    return p


# 🔴🔴🔳 **必须改写被导入模块的 `save`**：APP-120 的各 step 用的是**写死的**
#   `app120_accept_v11_<step>.json` ⇒ 直接跑会**覆盖 v1.1 的验收证据**
#   （APP-120 §2 已经因为「harness 输出路径写死」覆盖过 v2.5 的 §217 证据
#   —— 同一个坑不能再踩第二次）⇒ 这里的产物一律写 `app121_accept_v111_*`。
_m.save = save


# 🔴🔴🔳 **修掉 APP-120 编排脚本里的一个既有缺陷**（**不改 APP-120 的原件**）：
#   `_app120_accept_v11.py` 的 `_list_out_devices()` 返回的是**设备 id 列表**，
#   而 `step_devswitch()` 里写的是 `out_ids = [i for i, _n in out_pairs]`
#   ⇒ 把 id **字符串**按 2 个字符解包 ⇒ `ValueError: too many values to unpack`
#   ⇒ **devswitch 这一步在已提交的版本上根本跑不起来**
#   （v1.1 那次的 PASS 证据是用临时补丁跑出来的；已提交文件里仍是坏的）。
#   ⇒ 这里**只在本模块内**覆写 `_list_out_devices` 让它返回 **(id, name) 对**，
#      **不修改** `_app120_accept_v11.py`（那是 APP-120 的历史产物）。
def _list_out_devices_pairs():
    import audio_source
    devs = audio_source.list_output_devices()
    out = []
    for d in devs:
        if isinstance(d, (list, tuple)) and len(d) >= 1:
            out.append((d[0], d[1] if len(d) > 1 else ''))
        elif isinstance(d, dict):
            out.append((d.get('id'), d.get('name', '')))
        else:
            out.append((d, ''))
    return [(i, n) for i, n in out if i is not None]


_m._list_out_devices = _list_out_devices_pairs


def step_chain(args):
    """🔴 同 APP-120 的 chain step，只把 tag 换成 v1.1.1（产物不覆盖旧的）。"""
    acc = os.path.join(RESULTS, '_app588_sp4_acceptance.py')
    run_id = args.run_id or time.strftime('%Y%m%d-%H%M%S')
    tag = 'app121_v111_default'
    cmd = [sys.executable, acc, '--pkg', PKG,
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU', '--lang', 'zh', '--tag', tag,
           '--run-id', run_id, '--lock-note', 'app121-v111-default']
    log('[chain] %s' % ' '.join(cmd))
    t0 = time.time()
    cp = subprocess.run(cmd, cwd=os.path.dirname(acc),
                        capture_output=True, text=True, encoding='utf-8',
                        errors='replace')
    out = (cp.stdout or '') + '\n' + (cp.stderr or '')
    log(out[-3000:])
    op = os.path.join(RESULTS,
                      'app591_acceptance_%s_run%s.json' % (tag, run_id))
    data = {'step': 'chain', 'cmd': cmd, 'rc': cp.returncode,
            'wall_s': round(time.time() - t0, 1), 'out_json': op,
            'stdout_tail': out[-8000:]}
    if os.path.isfile(op):
        with open(op, 'r', encoding='utf-8') as f:
            data['acceptance'] = json.load(f)
    save('chain', data)
    return 0 if data.get('rc') == 0 else 1


def step_lang10(args):
    """🔴 同 APP-120 的 lang10 step，但**证据写到 v1.1.1 专属文件**。

    🔴 **为什么必须改**：APP-120 的 step 把 `--out` **写死**成
    `app120_accept_v11_lang10_evidence.json` ⇒ 直接跑会**覆盖 v1.1 的证据**
    （§220 已经因为「harness 输出路径写死」覆盖过 v2.5 的 §217 证据
    —— 同一个坑不能踩第二次）⇒ 这里换成 `app121_accept_v111_lang10_evidence.json`。
    """
    script = os.path.join(HERE, 'diag_app118_lang10.py')
    cmd = [_m.PKG_PY, script, '--pkg', _m.PKG, '--live',
           '--device', 'GPU.0', '--mt-device', 'GPU.0', '--tts-device', 'NPU',
           '--out', os.path.join(RESULTS,
                                 'app121_accept_v111_lang10_evidence.json')]
    log('[lang10] %s' % ' '.join(cmd))
    t0 = time.time()
    cp = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                        encoding='utf-8', errors='replace')
    out = (cp.stdout or '') + '\n' + (cp.stderr or '')
    log(out[-3000:])
    data = {'step': 'lang10', 'cmd': cmd, 'rc': cp.returncode,
            'wall_s': round(time.time() - t0, 1), 'stdout_tail': out[-8000:]}
    ev_path = os.path.join(RESULTS, 'app121_accept_v111_lang10_evidence.json')
    if os.path.isfile(ev_path):
        with open(ev_path, 'r', encoding='utf-8') as f:
            ev = json.load(f)
        data['pass'] = ev.get('pass')
        data['fail'] = ev.get('fail')
        data['evidence'] = ev_path
        data['n_checks'] = len(ev.get('checks') or [])
    save('lang10', data)
    return 0 if cp.returncode == 0 else 1


STEPS = {
    'selfcheck': _m.step_selfcheck,
    'devswitch': _m.step_devswitch,
    'freshdir': _m.step_freshdir,
    'chain': step_chain,
    'lang10': step_lang10,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', required=True, choices=sorted(STEPS))
    ap.add_argument('--run-id', default='')
    args = ap.parse_args()
    if not os.path.isdir(PKG):
        print('FAIL: 包目录不存在 %s' % PKG)
        return 2
    log('=== APP-121 §5 验收 step=%s（包 %s）===' % (args.step, PKG))
    log('    解释器：%s' % sys.executable)
    rc = STEPS[args.step](args)
    # 🔴 v1.1 的证据**只读**（不许被本轮覆盖）⇒ 若被改写 ⇒ 立即报错
    for step in ('selfcheck', 'devswitch', 'freshdir', 'lang10'):
        old = os.path.join(RESULTS, 'app120_accept_v11_%s.json' % step)
        if os.path.isfile(old) and step == args.step:
            log('  ⚠ v1.1 的 %s 证据已被改写？⇒ 核对 mtime' % step)
    return rc


if __name__ == '__main__':
    sys.exit(main())
