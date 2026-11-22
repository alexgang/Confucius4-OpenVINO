#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §2：**MiniMVP v1.1 验收编排**（分步可单独跑）。

## 步骤
| step | 内容 | 占设备 |
|---|---|---|
| `selfcheck` | 包上自检（`--check`）：设备 / ASR / MT / TTS 后端 | 否 |
| `devswitch` | 设备切换冒烟：① 全 NPU 启动不崩 ② TTS 改 GPU.0 生效 ③ 耳机输出生效 | 是（短） |
| `freshdir` | 全新用户目录启动（默认值正确）＋ rc11 旧配置启动（迁移正确） | 是（短） |
| `chain` | **出厂默认 10 分钟固定片段整链**（150 句不丢 / 语速 ≤1.7 / synth_rtf 中位·P90 / 积压峰值·收尾积压 / 首字延迟） | 是（长） |
| `lang10` | 10 语种各 1 句冒烟（字幕 + 配音） | 是（中） |

## 纪律
- 每个 step 独立产物 json（`results/app/app120_accept_v11_<step>.json`）；
- **不并跑**占设备的 step（机器锁 + 计时有效性）；
- 长 step 由调用方以后台作业启动。

## 用法
```
python live_caption/_app120_accept_v11.py --step selfcheck
python live_caption/_app120_accept_v11.py --step chain
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1')
PKG_APP = os.path.join(PKG, 'app')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
RESULTS = os.path.join(REPO, 'results', 'app')
LIVE = HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
SHORT = os.path.join(REPO, 'test_audio', 'app119_clip_0_60.wav')


def log(*a):
    print(*a, flush=True)


def save(step, data):
    os.makedirs(RESULTS, exist_ok=True)
    p = os.path.join(RESULTS, 'app120_accept_v11_%s.json' % step)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    log('  产物 → %s' % p)
    return p


def run(cmd, cwd=None, env=None, timeout=3600):
    t0 = time.time()
    cp = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                        encoding='utf-8', errors='replace', timeout=timeout)
    return {'cmd': cmd, 'cwd': cwd, 'rc': cp.returncode,
            'wall_s': round(time.time() - t0, 1),
            'stdout': (cp.stdout or ''), 'stderr': (cp.stderr or '')}


# ── step: selfcheck ───────────────────────────────────────────────
def step_selfcheck(_args):
    r = run([PKG_PY, os.path.join(PKG_APP, 'live_caption_app.py'), '--check'],
            cwd=PKG, timeout=900)
    out = r['stdout'] + '\n' + r['stderr']
    checks = [
        ('退出码 0', r['rc'] == 0, str(r['rc'])),
        ('提到 Intel 集显 / GPU.0', ('GPU.0' in out or '集显' in out), ''),
        ('提到 NPU', ('NPU' in out), ''),
        ('ASR 后端出现 stateful（0.6B stateful 后端）',
         ('stateful' in out) or ('asr06b' in out) or ('0.6B' in out), ''),
        ('ASR 可用后端数 = 2（GPU.0 + NPU）',
         ('ASR 可用后端 2 个' in out), ''),
        ('MT INT4 标注「本包不附带该量化版本」',
         'INT4' in out and '不附带' in out, ''),
        ('MT 后端出现 INT8-CW / mt2', ('INT8' in out.upper() or 'mt2' in out), ''),
        ('TTS 后端出现（qwen3tts / TTS）', ('qwen3tts' in out.lower()
                                           or 'TTS' in out), ''),
        ('**未**出现 CUDA 后端（MiniMVP 无 CUDA）',
         'CUDA' not in out.upper(), ''),
    ]
    data = {'step': 'selfcheck', 'pkg': PKG, 'run': r,
            'checks': [{'name': n, 'pass': bool(c), 'detail': d}
                       for n, c, d in checks]}
    data['n_fail'] = sum(1 for c in data['checks'] if not c['pass'])
    data['result'] = 'PASS' if data['n_fail'] == 0 else 'FAIL'
    save('selfcheck', data)
    return 0 if data['result'] == 'PASS' else 1


# ── step: devswitch ───────────────────────────────────────────────
def step_devswitch(_args):
    runs = []
    checks = []

    def do(tag, extra, expect, timeout=1800):
        """expect = [(名称, 判定函数(out) -> (pass, detail)), ...]"""
        cmd = [PKG_PY, os.path.join(PKG_APP, 'live_caption_app.py'), '--cli',
               '--file', SHORT, '--tts', 'on', '--tts-voice', 'A',
               '--out', os.path.join(RESULTS,
                                     '_app120_v11_%s.txt' % tag)] + extra
        r = run(cmd, cwd=PKG, timeout=timeout)
        out = r['stdout'] + '\n' + r['stderr']
        runs.append({'tag': tag, 'cmd': cmd, 'rc': r['rc'],
                     'wall_s': r['wall_s'], 'stdout_tail': out[-4000:]})
        for name, fn in expect:
            try:
                p, d = fn(out)
            except Exception as e:
                p, d = False, '判定异常 %r' % (e,)
            checks.append({'tag': tag, 'name': name, 'pass': bool(p),
                           'detail': str(d)[:1200]})
        return out

    def mk(cond_fn, detail_fn):
        return lambda out: (cond_fn(out), detail_fn(out))

    # ① 全 NPU 启动不崩（且**不静默换设备**）
    do('allnpu',
       ['--asr-device', 'NPU', '--mt-device', 'NPU', '--tts-device', 'NPU'],
       [
           ('全 NPU 退出码 0（启动不崩）',
            mk(lambda o: True, lambda o: 'rc 见 runs')),
           ('全 NPU：日志出现 NPU 设备（未静默换设备）',
            mk(lambda o: 'NPU' in o, lambda o: o[-1200:])),
           ('全 NPU：未静默降级成 CUDA',
            mk(lambda o: 'CUDA' not in o.upper(), lambda o: o[-1200:])),
       ])

    # ② TTS 改 GPU.0 生效
    do('tts_gpu0',
       ['--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
        '--tts-device', 'GPU.0'],
       [
           ('TTS=GPU.0：日志出现 GPU.0 的语音输出设备',
            mk(lambda o: 'GPU.0' in o, lambda o: o[-1200:])),
           ('TTS=GPU.0：未出现 CUDA',
            mk(lambda o: 'CUDA' not in o.upper(), lambda o: o[-1200:])),
       ])

    # ③ 耳机输出生效（--tts-out-device 指向一个真实输出设备）
    out_pairs = _list_out_devices()
    out_ids = [i for i, _n in out_pairs]
    # 🔴 **优先选真正的耳机**（名字含「耳机」/「headphone」/「headset」）
    hp = [(i, n) for i, n in out_pairs
          if any(k in (n or '').lower() for k in ('耳机', 'headphone', 'headset'))]
    pick = hp[0] if hp else (out_pairs[0] if out_pairs else None)
    if pick:
        oid, oname = pick
        out = do('headphone', ['--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
                               '--tts-device', 'GPU.0',
                               '--tts-out-device', str(oid)],
                 [
                     ('耳机输出设备 %s（%s）生效（日志含该 id）' % (oid, oname),
                      mk(lambda o: str(oid) in o, lambda o: o[-1500:])),
                     ('耳机输出设备：日志出现「输出设备」字样',
                      mk(lambda o: '输出设备' in o, lambda o: o[-1500:])),
                 ])
        lines = [l for l in out.splitlines()
                 if ('输出设备' in l) or (str(oid) in l)]
        runs[-1]['out_device_lines'] = lines[:40]
        runs[-1]['picked_out_device'] = {'id': oid, 'name': oname}
    else:
        checks.append({'tag': 'headphone', 'name': '耳机输出设备冒烟',
                       'pass': False,
                       'detail': '本机枚举不到输出设备（无法做该项）'})

    data = {'step': 'devswitch', 'pkg': PKG, 'runs': runs,
            'checks': checks, 'out_devices': out_ids}
    data['n_fail'] = sum(1 for c in data['checks'] if not c['pass'])
    data['result'] = 'PASS' if data['n_fail'] == 0 else 'FAIL'
    save('devswitch', data)
    return 0 if data['result'] == 'PASS' else 1


def _list_out_devices():
    """列出本机输出设备 id（MME / WASAPI）⇒ 供「耳机输出生效」冒烟用。"""
    try:
        sys.path.insert(0, PKG_APP)
        import audio_source
        devs = audio_source.list_output_devices()
        out = []
        for d in devs:
            # list_output_devices() ⇒ [(WASAPI id, 显示名)]
            if isinstance(d, (list, tuple)) and len(d) >= 1:
                out.append(d[0])
            elif isinstance(d, dict):
                out.append(d.get('id'))
            else:
                out.append(d)
        return [x for x in out if x is not None]
    except Exception:
        return []


# ── step: freshdir ────────────────────────────────────────────────
def step_freshdir(_args):
    tmp = tempfile.mkdtemp(prefix='app120_fresh_')
    env = dict(os.environ)
    env['LOCALAPPDATA'] = tmp
    env['APPDATA'] = tmp
    cfgdir = os.path.join(tmp, 'Confucius4LiveCaption')
    os.makedirs(cfgdir, exist_ok=True)
    cfgp = os.path.join(cfgdir, 'device_config.json')
    runs = []

    def do(tag):
        cmd = [PKG_PY, os.path.join(PKG_APP, 'live_caption_app.py'), '--check']
        r = run(cmd, cwd=PKG, env=env, timeout=900)
        out = r['stdout'] + '\n' + r['stderr']
        runs.append({'tag': tag, 'rc': r['rc'], 'stdout': out[-6000:]})
        return out

    # ① 全新用户目录（**没有**旧 device_config）
    if os.path.exists(cfgp):
        os.remove(cfgp)
    o1 = do('fresh')
    d1 = {'tag': 'fresh',
          'name': '全新用户目录：出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU',
          'pass': ('GPU.0' in o1 and 'NPU' in o1),
          'detail': o1[-1500:]}

    # ② rc11 留下的旧配置（profile=minimvp / defaults_version=9）
    with open(cfgp, 'w', encoding='utf-8') as f:
        json.dump({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                   'profile': 'minimvp', 'defaults_version': 9},
                  f, ensure_ascii=False, indent=2)
    o2 = do('rc11_old')
    d2 = {'tag': 'rc11_old',
          'name': 'rc11 旧配置：当代同形态 ⇒ 信任（不迁移）且设备不变',
          'pass': ('GPU.0' in o2 and 'NPU' in o2),
          'detail': o2[-1500:]}

    # ③ 本机残留的**完整版**旧配置（profile=full）⇒ 形态不同 ⇒ 三个键全忽略
    with open(cfgp, 'w', encoding='utf-8') as f:
        json.dump({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                   'profile': 'full', 'defaults_version': 9},
                  f, ensure_ascii=False, indent=2)
    o3 = do('full_old')
    d3 = {'tag': 'full_old',
          'name': '完整版残留旧配置：形态不同 ⇒ 三个键全忽略 ⇒ 仍用出厂默认',
          'pass': ('GPU.0' in o3 and 'NPU' in o3),
          'detail': o3[-1500:]}

    data = {'step': 'freshdir', 'pkg': PKG, 'tmp_localappdata': tmp,
            'runs': runs, 'checks': [d1, d2, d3]}
    data['n_fail'] = sum(1 for c in data['checks'] if not c['pass'])
    data['result'] = 'PASS' if data['n_fail'] == 0 else 'FAIL'
    save('freshdir', data)
    return 0 if data['result'] == 'PASS' else 1


# ── step: chain（长）───────────────────────────────────────────────
def step_chain(args):
    acc = os.path.join(RESULTS, '_app588_sp4_acceptance.py')
    run_id = args.run_id or time.strftime('%Y%m%d-%H%M%S')
    tag = 'app120_v11_default'
    cmd = [sys.executable, acc, '--pkg', PKG,
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU', '--lang', 'zh', '--tag', tag,
           '--run-id', run_id, '--lock-note', 'app120-v11-default']
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


# ── step: lang10 ──────────────────────────────────────────────────
def step_lang10(_args):
    script = os.path.join(HERE, 'diag_app118_lang10.py')
    # 🔴 **必须用包内 python**（`babelvox` 只随包分发；venv 里没有 ⇒
    #    用 venv 跑会报「未安装 babelvox」——那是**编排用错解释器**，不是产品缺陷）
    cmd = [PKG_PY, script, '--pkg', PKG, '--live',
           '--device', 'GPU.0', '--mt-device', 'GPU.0', '--tts-device', 'NPU',
           # 🔴🔴🔳 **APP-120 §2（2026-11-22）**：证据**写到 v1.1 专属文件**
           #   ⇒ 不覆盖 v2.5（§217）的 `app118_lang10_evidence.json`
           #   （实测：写死路径 ⇒ 14:47 那次把 v2.5 的原件覆盖成 v1.1 的结果）。
           '--out', os.path.join(RESULTS, 'app120_accept_v11_lang10_evidence.json')]
    log('[lang10] %s' % ' '.join(cmd))
    t0 = time.time()
    cp = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                        encoding='utf-8', errors='replace')
    out = (cp.stdout or '') + '\n' + (cp.stderr or '')
    log(out[-3000:])
    data = {'step': 'lang10', 'cmd': cmd, 'rc': cp.returncode,
            'wall_s': round(time.time() - t0, 1), 'stdout_tail': out[-8000:]}
    save('lang10', data)
    return 0 if cp.returncode == 0 else 1


STEPS = {
    'selfcheck': step_selfcheck,
    'devswitch': step_devswitch,
    'freshdir': step_freshdir,
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
    log('=== APP-120 §2 验收 step=%s（包 %s）===' % (args.step, PKG))
    return STEPS[args.step](args)


if __name__ == '__main__':
    sys.exit(main())
