# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119 §1 的迁移判据验收**（纯逻辑，不加载模型、不占设备）。

reviewer 要求（APP-119 §3 验收第 4 条）：「**迁移测试**：旧默认配置会被迁移，
用户自定义配置保持原样」。

本脚本覆盖：
  * 完整版（full）：旧出厂默认 ⇒ 迁移到 GPU.0/GPU.0/**NPU**；
    手动选过的 ⇒ **保持不变**（含迁移后手动选回 GPU.0 的情形）。
  * MiniMVP / Special MVP：**回归**（口径不变）。

产物：``results/app/app119_migration_test.json``
"""
import importlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import device_config          # noqa: E402
import package_profile        # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'results', 'app',
                   'app119_migration_test.json')

# 设备清单固定 ⇒ 结果不依赖本机有没有 NPU/GPU（**只测迁移判据**）
FAKE_AVAIL = ['NPU', 'GPU.0']


def _with_profile(prof):
    """切包形态并重载 device_config（DEFAULT_DEVICES 是导入期算出来的）。"""
    package_profile.PROFILE = prof
    importlib.reload(device_config)
    device_config.available_devices = lambda: list(FAKE_AVAIL)


def _set_saved(tmpdir, saved):
    device_config.CONFIG_PATH = os.path.join(tmpdir, 'device_config.json')
    if saved is None:
        try:
            os.remove(device_config.CONFIG_PATH)
        except OSError:
            pass
    else:
        with open(device_config.CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)


def _run(tmpdir, saved):
    _set_saved(tmpdir, saved)
    dev, notes = device_config.get_devices()
    return {
        'saved': saved,
        'stale': device_config.stale_device_keys(saved or {}),
        'note': device_config.stale_device_note(saved or {}),
        'resolved': dev,
        'notes': notes,
        'defaults_version': device_config.current_defaults_version(),
        'default_devices': dict(device_config.DEFAULT_DEVICES),
    }


def main() -> int:
    tmpdir = tempfile.mkdtemp(prefix='app119_mig_')
    cases = []
    fails = []

    def check(name, cond, detail=''):
        cases.append({'case': name, 'pass': bool(cond), 'detail': detail})
        if not cond:
            fails.append('%s :: %s' % (name, detail))

    # ── A. 完整版 ────────────────────────────────────────────────────
    _with_profile('full')
    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0',
                      'profile': 'full', 'defaults_version': 9})
    check('A1 旧出厂默认 ⇒ 只迁移 tts',
          r['stale'] == ['tts'] and r['resolved'] == {'asr': 'GPU.0',
                                                       'mt': 'GPU.0',
                                                       'tts': 'NPU'},
          json.dumps(r, ensure_ascii=False))
    check('A1b 迁移**写进提示**（日志/状态条口径）',
          ('APP-119' in r['note']) and ('GPU.0' in r['note']), r['note'])

    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                      'profile': 'full', 'defaults_version': 11})
    check('A2 新代次默认 ⇒ 不迁移、不提示',
          r['stale'] == [] and r['note'] == '' and
          r['resolved']['tts'] == 'NPU', json.dumps(r, ensure_ascii=False))

    r = _run(tmpdir, {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0',
                      'profile': 'full', 'defaults_version': 9})
    check('A3 手动改过（ASR=NPU）⇒ 保持不变',
          r['stale'] == [] and r['resolved']['asr'] == 'NPU' and
          r['resolved']['tts'] == 'GPU.0', json.dumps(r, ensure_ascii=False))

    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0',
                      'profile': 'full', 'defaults_version': 11})
    check('A4 迁移后手动选回 TTS=GPU.0 ⇒ 保持不变（不被改回 NPU）',
          r['stale'] == [] and r['resolved']['tts'] == 'GPU.0',
          json.dumps(r, ensure_ascii=False))

    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0'})
    check('A5 无代次信息的残留旧配置 ⇒ 迁移',
          r['stale'] == ['tts'] and r['resolved']['tts'] == 'NPU',
          json.dumps(r, ensure_ascii=False))

    r = _run(tmpdir, None)
    check('A6 无配置文件 ⇒ 用新出厂默认 GPU.0/GPU.0/NPU',
          r['resolved'] == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'},
          json.dumps(r, ensure_ascii=False))
    check('A6b 完整版出厂默认代次 = 11',
          r['defaults_version'] == 11, str(r['defaults_version']))

    # ── B. MiniMVP 回归 ──────────────────────────────────────────────
    _with_profile('minimvp')
    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                      'profile': 'minimvp', 'defaults_version': 9})
    check('B1 MiniMVP 当代配置 ⇒ 信任（不迁移）',
          r['stale'] == [] and r['resolved']['tts'] == 'NPU',
          json.dumps(r, ensure_ascii=False))
    r = _run(tmpdir, {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0',
                      'profile': 'minimvp', 'defaults_version': 8})
    check('B2 MiniMVP 旧代次 ⇒ 老口径（三个键全忽略）',
          r['stale'] == ['asr', 'mt', 'tts'], json.dumps(r, ensure_ascii=False))
    check('B2b MiniMVP 代次仍 = 9', r['defaults_version'] == 9,
          str(r['defaults_version']))
    check('B2c MiniMVP 出厂默认不变（GPU.0/GPU.0/NPU）',
          r['default_devices'] == {'asr': 'GPU.0', 'mt': 'GPU.0',
                                   'tts': 'NPU'},
          json.dumps(r['default_devices'], ensure_ascii=False))

    # ── C. Special MVP 回归 ─────────────────────────────────────────
    _with_profile('specialmvp')
    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'CUDA',
                      'profile': 'specialmvp', 'defaults_version': 10})
    check('C1 Special MVP 当代配置 ⇒ 信任',
          r['stale'] == [] and r['defaults_version'] == 10,
          json.dumps(r, ensure_ascii=False))
    r = _run(tmpdir, {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0',
                      'profile': 'full', 'defaults_version': 9})
    check('C2 Special MVP 看到别的形态的旧配置 ⇒ 忽略（老口径不变）',
          r['stale'] == ['asr', 'mt', 'tts'], json.dumps(r, ensure_ascii=False))
    check('C2b Special MVP 出厂默认不变（GPU.0/NPU/CUDA）',
          r['default_devices'] == {'asr': 'GPU.0', 'mt': 'NPU',
                                   'tts': 'CUDA'},
          json.dumps(r['default_devices'], ensure_ascii=False))

    out = {
        'app': 'APP-119',
        'section': '§1 迁移判据',
        'result': 'PASS' if not fails else 'FAIL',
        'n_cases': len(cases),
        'n_fail': len(fails),
        'fails': fails,
        'cases': cases,
        'note': '纯逻辑验收（不加载模型、不占 GPU/NPU）；'
                '设备清单固定为 NPU/GPU.0 ⇒ 结果与本机硬件无关。',
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    print('== APP-119 迁移判据 == %s（%d/%d 通过）'
          % (out['result'], len(cases) - len(fails), len(cases)))
    for c in cases:
        print('  %s %s' % ('PASS' if c['pass'] else 'FAIL', c['case']))
        if not c['pass']:
            print('       %s' % c['detail'][:400])
    print('产物：%s' % OUT)
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
