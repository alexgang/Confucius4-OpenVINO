# -*- coding: utf-8 -*-
r"""_app490 — **APP-104 §1 行为级验证**：`device_config` 的「旧出厂默认迁移」。

判据原则（沿用 §173/§178 的教训）：
  * **行为级真跑**（不是正则、不是字面存在性）⇒ 真的调 `get_devices()`；
  * **反证组必须能被识破**（否则判据恒真）；
  * 被测函数的依赖（`package_profile` / `available_devices`）**显式注入**，
    不用「缺依赖 ⇒ 静默 except ⇒ 假 FAIL」的老路；
  * 「读旧配置」这件事**不许改用户的文件** ⇒ 核对读前/读后 SHA 相同。

跑法：
    python results/app/_app490_app104_config_migration.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEV = os.path.join(REPO, 'live_caption')
REPORT = os.path.join(HERE, 'app490_app104_config_migration.json')


def _sha(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def _install_fake_profile(tmp):
    """造一个 `package_profile`（is_minimvp 可切换）⇒ 放 sys.path 最前。"""
    d = os.path.join(tmp, 'fake_pkg')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'package_profile.py'), 'w', encoding='utf-8') as f:
        f.write("# -*- coding: utf-8 -*-\n"
                "MINIMVP = True\n"
                "def is_minimvp():\n"
                "    return MINIMVP\n"
                "def allow_cuda():\n"
                "    return False\n"
                "def allow_clone_voice():\n"
                "    return False\n")
    sys.path.insert(0, d)
    return d


def main():
    tmp = tempfile.mkdtemp(prefix='app490_')
    cases = []
    try:
        _install_fake_profile(tmp)
        if DEV not in sys.path:
            sys.path.insert(1, DEV)   # 位置 1 ⇒ 假 package_profile 仍在前面
        import device_config as dc

        # 设备探测与迁移逻辑无关 ⇒ 显式桩掉（避免依赖本机 OV 设备）
        dc.available_devices = lambda: ['NPU', 'GPU.0', 'CPU']
        dc.CONFIG_DIR = tmp
        cfg = os.path.join(tmp, 'device_config.json')
        dc.CONFIG_PATH = cfg

        def write_cfg(obj):
            with open(cfg, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)

        def read_cfg():
            with open(cfg, encoding='utf-8') as f:
                return json.load(f)

        # ── 用例 1：残留旧出厂默认（rc5/rc7 时期）⇒ 必须被忽略 ──────────
        stale = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                 'tts_speed_min_zh': 1.25, 'tts_late_drop_sec': 7.5}
        write_cfg(stale)
        sha_before = _sha(cfg)
        devs, notes = dc.get_devices()
        sha_after = _sha(cfg)
        note_text = ' | '.join(notes)
        cases.append({
            'case': 'stale_residual_config_is_ignored',
            'expect': {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'},
            'got': devs,
            'note_has_ignored_values': ('已忽略旧配置里的设备项' in note_text
                                        and 'asr=GPU.0' in note_text
                                        and 'mt=GPU.0' in note_text
                                        and 'tts=NPU' in note_text),
            'numeric_preserved': {
                'tts_speed_min_zh': dc.get_numeric('tts_speed_min_zh'),
                'tts_late_drop_sec': dc.get_numeric('tts_late_drop_sec'),
            },
            'numeric_expect': {'tts_speed_min_zh': 1.25, 'tts_late_drop_sec': 7.5},
            'file_untouched_by_read': (sha_before == sha_after),
            'pass': (devs == {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'}
                     and '已忽略旧配置里的设备项' in note_text
                     and 'asr=GPU.0' in note_text
                     and dc.get_numeric('tts_speed_min_zh') == 1.25
                     and dc.get_numeric('tts_late_drop_sec') == 7.5
                     and sha_before == sha_after),
        })

        # ── 反证 A：新格式（profile + defaults_version=8）⇒ 尊重用户选择 ──
        write_cfg({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                   'profile': 'minimvp', 'defaults_version': 8})
        devs, notes = dc.get_devices()
        cases.append({
            'case': 'counterexample_new_format_keeps_user_choice',
            'expect': {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'},
            'got': devs,
            'no_migration_note': ('已忽略旧配置里的设备项' not in ' | '.join(notes)),
            'pass': (devs == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
                     and '已忽略旧配置里的设备项' not in ' | '.join(notes)),
        })

        # ── 反证 B：defaults_version 比 rc8 旧（7）⇒ 必须忽略 ────────────
        write_cfg({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                   'profile': 'minimvp', 'defaults_version': 7})
        devs, notes = dc.get_devices()
        cases.append({
            'case': 'counterexample_older_version_is_ignored',
            'expect': {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'},
            'got': devs,
            'pass': (devs == {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'}
                     and '已忽略旧配置里的设备项' in ' | '.join(notes)),
        })

        # ── 反证 C：有 profile 但缺 defaults_version ⇒ 必须忽略 ─────────
        write_cfg({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
                   'profile': 'minimvp'})
        devs, notes = dc.get_devices()
        cases.append({
            'case': 'counterexample_missing_version_is_ignored',
            'expect': {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'},
            'got': devs,
            'pass': (devs == {'asr': 'NPU', 'mt': 'GPU.0', 'tts': 'GPU.0'}
                     and '已忽略旧配置里的设备项' in ' | '.join(notes)),
        })

        # ── 用例 2：save_config 写新字段 ⇒ 下次启动保留用户选择 ──────────
        write_cfg({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'})
        ok = dc.save_config({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'})
        saved = read_cfg()
        devs2, notes2 = dc.get_devices()
        cases.append({
            'case': 'save_config_writes_profile_and_version_then_keeps_choice',
            'saved_keys': sorted(saved.keys()),
            'saved_profile': saved.get('profile'),
            'saved_defaults_version': saved.get('defaults_version'),
            'save_ok': ok,
            'got_after_restart': devs2,
            'pass': (ok and saved.get('profile') == 'minimvp'
                     and saved.get('defaults_version') == dc.CONFIG_DEFAULTS_VERSION
                     and devs2 == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
                     and '已忽略旧配置里的设备项' not in ' | '.join(notes2)),
        })

        # ── 反证 D：完整版（profile != minimvp）⇒ 不做迁移（规则只针对 MiniMVP）
        import package_profile as pp
        pp.MINIMVP = False
        write_cfg({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'})
        devs3, notes3 = dc.get_devices()
        pp.MINIMVP = True
        cases.append({
            'case': 'counterexample_full_profile_not_migrated',
            'expect': {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'},
            'got': devs3,
            'pass': (devs3 == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
                     and '已忽略旧配置里的设备项' not in ' | '.join(notes3)),
        })

        ev = {
            'at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
            'correction': 'APP-104 §1',
            'dev_file': os.path.join('live_caption', 'device_config.py'),
            'config_defaults_version': dc.CONFIG_DEFAULTS_VERSION,
            'default_devices': dc.DEFAULT_DEVICES,
            'cases': cases,
            'n_pass': sum(1 for c in cases if c['pass']),
            'n_fail': sum(1 for c in cases if not c['pass']),
        }
        ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        print(json.dumps(ev, ensure_ascii=False, indent=1))
        return 0 if ev['verdict'] == 'PASS' else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
