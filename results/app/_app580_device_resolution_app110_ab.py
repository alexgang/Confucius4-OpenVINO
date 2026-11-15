#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app580_device_resolution_app110_ab.py —— **APP-110 §0②(a)(b) 补测**。

**reviewer 原文（§0②）**：
  「还缺两项，都只要补测，不改代码就不用出新包：
    · (a) 正向对照：specialmvp 本代的用户手选必须保留。在隔离目录写
      {"asr":"GPU.0","mt":"GPU.0","tts":"CUDA","profile":"specialmvp",
      "defaults_version":10}，解析结果应为 mt=GPU.0（手选被保留），
      并且没有「已忽略旧配置」提示。
    · (b) `device_config.py` 是共用文件，这次改了 `current_profile()` 和
      `stale_device_keys()`。app552 只核对了三种形态的 DEFAULT_DEVICES 常量，
      没有跑忽略逻辑。要在 MiniMVP 形态（rc11 包，或 dev 树指定 profile=minimvp）
      下用隔离 LOCALAPPDATA 跑两例：minimvp v9 手选（如 mt=NPU）应保留；
      59 B 旧 3 键应被忽略，回到 GPU.0/GPU.0/NPU。完整版形态各跑一例同样的检查。」

🔴 **本脚本做什么**（三种形态 × 各 2 例，全部用**隔离 LOCALAPPDATA**）：
  ① **specialmvp** ⇒ **sp3 包**（真实包，APP-111 §2：「②a/②b 在 sp3 上补测即可」）
       · a1 本代手选（profile=specialmvp, defaults_version=10, mt=GPU.0）
         ⇒ 期望：mt=GPU.0（手选被保留）＋ **无**「已忽略旧配置」提示
  ② **minimvp** ⇒ **rc11 包**（reviewer 点名的 MiniMVP 包）**＋ dev 树形态**（新代码）
       · b1 minimvp v9 手选（mt=NPU）⇒ 期望：mt=NPU 被保留
       · b2 59 B 旧 3 键 ⇒ 期望：**被忽略** ⇒ 回到 GPU.0/GPU.0/NPU
  ③ **full** ⇒ **dev 树形态**（新代码）+ **v2.1 包**（当前交付的完整版，记录用）
       · b3 本代手选（profile=full, defaults_version=9, mt=NPU）⇒ 期望：mt=NPU 保留
       · b4 59 B 旧 3 键 ⇒ 期望：完整版**从不忽略**（旧行为）⇒ 解析=GPU.0/GPU.0/GPU.0
         （= 完整版出厂默认，**结果相同、机制不同** ⇒ 如实记录）

🔴 **纪律**：
  ① **隔离**：每个 case 用**独立**的 LOCALAPPDATA（临时目录）⇒ 真实
     `%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json` 碰不到；
     跑前跑后各取一次真实配置的 SHA256/字节/mtime 做断言。
  ② **只读真实环境**：脚本只读真实配置，绝不写它。
  ③ **不改产品代码**：本脚本只*测量*，不改任何 `.py`（含被测包）。
  ④ **dev 树形态** = 把 dev 树的 `device_config.py` + `package_profile.py` 复制到
     临时目录的 `app/` 下，并在**临时目录根部**放 `package_profile.json`
     ⇒ `package_profile.PKG_ROOT` = 临时目录 ⇒ 形态由标记文件决定（reviewer
     允许的「dev 树指定 profile=minimvp」）。**开发树本身一字不改**。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
RESULTS = os.path.join(REPO, 'results', 'app')
REAL_CFG = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                        'device_config.json')
OUT = os.path.join(RESULTS, 'app580_device_resolution_app110_ab.json')

SP3 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp3')
RC11 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
V21 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.1')

#: 🔴 真实配置原文**逐字节**（含 CRLF）——「59 B 旧 3 键」这一例直接复用。
REAL_CFG_RAW = (b'{\r\n  "asr": "GPU.0",\r\n  "mt": "GPU.0",\r\n'
                b'  "tts": "GPU.0"\r\n}')

NOTE_IGNORED = '已忽略旧配置'
WARN_ASR_MT_GPU = 'ASR 与 MT 都放在'


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def real_cfg_state():
    if not os.path.isfile(REAL_CFG):
        return {'exists': False}
    st = os.stat(REAL_CFG)
    return {'exists': True, 'bytes': st.st_size,
            'sha256': sha256_file(REAL_CFG), 'mtime': st.st_mtime,
            'mtime_str': time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(st.st_mtime))}


PROBE_SRC = (
    "import sys, json\n"
    "sys.path.insert(0, __APPDIR__)\n"
    "import device_config as dc\n"
    "d, notes = dc.get_devices()\n"
    "# 🔴 **判据要能跑在旧包上**：rc11 没有 `current_defaults_version`、\n"
    "#    v2.1 连 `current_profile` 都没有（都是 APP-104/108 之前的老代码）\n"
    "#    ⇒ 一律用 getattr 兜底，**缺字段不等于解析失败**。\n"
    "def _call(name):\n"
    "    fn = getattr(dc, name, None)\n"
    "    if fn is None:\n"
    "        return None\n"
    "    try:\n"
    "        return fn()\n"
    "    except Exception as e:\n"
    "        return 'ERR:%s' % e\n"
    "stale = None\n"
    "fn = getattr(dc, 'stale_device_keys', None)\n"
    "if fn is not None:\n"
    "    try:\n"
    "        stale = fn(dc.load_config())\n"
    "    except Exception as e:\n"
    "        stale = 'ERR:%s' % e\n"
    "print(json.dumps({'devices': d, 'notes': notes,\n"
    "                  'current_profile': _call('current_profile'),\n"
    "                  'default_devices': getattr(dc, 'DEFAULT_DEVICES', None),\n"
    "                  'defaults_version': _call('current_defaults_version'),\n"
    "                  'stale_keys': stale,\n"
    "                  'has_current_profile': hasattr(dc, 'current_profile'),\n"
    "                  'has_stale_device_keys': hasattr(dc, 'stale_device_keys'),\n"
    "                  'config_path': getattr(dc, 'CONFIG_PATH', None)},"
    " ensure_ascii=False))\n"
)


def run_probe(python, appdir, iso, timeout=600):
    env = dict(os.environ)
    env['LOCALAPPDATA'] = iso
    src = PROBE_SRC.replace('__APPDIR__', repr(appdir))
    t1 = time.time()
    p = subprocess.run([python, '-c', src], capture_output=True, text=True,
                       timeout=timeout, cwd=appdir, env=env)
    out = {'rc': p.returncode, 'elapsed_s': round(time.time() - t1, 1),
           'stdout': (p.stdout or ''), 'stderr': (p.stderr or '')}
    try:
        line = [l for l in (p.stdout or '').splitlines()
                if l.strip().startswith('{')][-1]
        out['parsed'] = json.loads(line)
    except Exception as e:
        out['parse_error'] = repr(e)
    return out


def run_check(python, appdir, iso, timeout=1800):
    env = dict(os.environ)
    env['LOCALAPPDATA'] = iso
    t1 = time.time()
    p = subprocess.run([python, os.path.join(appdir, 'live_caption_app.py'),
                        '--check'], capture_output=True, text=True,
                       timeout=timeout, cwd=appdir, env=env)
    return {'rc': p.returncode, 'elapsed_s': round(time.time() - t1, 1),
            'stdout': (p.stdout or ''), 'stderr': (p.stderr or '')}


def cleanup_iso(iso):
    for dp, dn, fn in os.walk(iso, topdown=False):
        for f in fn:
            try:
                os.remove(os.path.join(dp, f))
            except Exception:
                pass
        for d in dn:
            try:
                os.rmdir(os.path.join(dp, d))
            except Exception:
                pass
    try:
        os.rmdir(iso)
    except Exception:
        pass


def make_harness(profile):
    """建一个「dev 树形态」测试脚手架：<tmp>/app/*.py + <tmp>/package_profile.json。

    ⚠️ **开发树本身一字不改**（只复制出去）。
    """
    root = tempfile.mkdtemp(prefix='wb_harness_%s_' % profile)
    appdir = os.path.join(root, 'app')
    os.makedirs(appdir, exist_ok=True)
    for f in ('device_config.py', 'package_profile.py'):
        shutil.copy2(os.path.join(DEV, f), os.path.join(appdir, f))
    if profile == 'full':
        # 完整版**不带**标记文件 ⇒ package_profile 回落成 'full'
        pass
    else:
        marker = {'profile': profile, 'allow_cuda': (profile == 'specialmvp'),
                  'allow_clone_voice': (profile != 'minimvp'),
                  'target_langs': 10}
        with open(os.path.join(root, 'package_profile.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(marker, f, ensure_ascii=False, indent=1)
    return root, appdir


def run_case(tag, desc, python, appdir, cfg_bytes, expect, expect_note,
             form, source, with_check=True, extra=None):
    iso = tempfile.mkdtemp(prefix='wb_iso_%s_' % tag)
    cfgdir = os.path.join(iso, 'Confucius4LiveCaption')
    os.makedirs(cfgdir, exist_ok=True)
    cfg_path = os.path.join(cfgdir, 'device_config.json')
    if cfg_bytes is not None:
        with open(cfg_path, 'wb') as f:
            f.write(cfg_bytes)
    rec = {'id': tag, 'desc': desc, 'form': form, 'source': source,
           'iso_localappdata': iso,
           'config_written_bytes': (len(cfg_bytes) if cfg_bytes is not None
                                    else None),
           'config_written_sha256': (sha256_bytes(cfg_bytes)
                                     if cfg_bytes is not None else None),
           'config_content': (cfg_bytes.decode('utf-8', 'replace')
                              if cfg_bytes is not None else None),
           'expect': expect, 'expect_note': expect_note}
    try:
        rec['get_devices'] = run_probe(python, appdir, iso)
        if with_check:
            rec['check'] = run_check(python, appdir, iso)
        gp = rec['get_devices'].get('parsed') or {}
        rec['resolved_devices'] = gp.get('devices')
        rec['notes'] = gp.get('notes')
        rec['current_profile'] = gp.get('current_profile')
        rec['default_devices'] = gp.get('default_devices')
        rec['defaults_version'] = gp.get('defaults_version')
        rec['stale_keys'] = gp.get('stale_keys')
        notes = ' '.join(rec.get('notes') or [])
        rec['note_has_ignored'] = (NOTE_IGNORED in notes)
        se = ((rec.get('check') or {}).get('stderr') or '')
        rec['check_has_ignored_note'] = (NOTE_IGNORED in se)
        rec['check_warn_asr_mt_same_gpu'] = (WARN_ASR_MT_GPU in se)
        rec['check_stderr_tail'] = se[-800:]
        # ── 判定 ──
        got = rec['resolved_devices'] or {}
        rec['pass_devices'] = all(got.get(k) == v
                                  for k, v in (expect or {}).items())
        rec['pass_note'] = (rec['note_has_ignored'] == expect_note)
        rec['pass'] = bool(rec['pass_devices'] and rec['pass_note'])
    finally:
        cleanup_iso(iso)
    if extra:
        rec.update(extra)
    return rec


def main():
    ev = {'started': time.strftime('%Y-%m-%d %H:%M:%S'),
          'purpose': 'APP-110 §0②(a)(b) 补测：三种形态的「手选保留 / 旧配置忽略」',
          'real_config_before': real_cfg_state(), 'cases': []}

    sp3_py = os.path.join(SP3, 'python', 'python.exe')
    sp3_app = os.path.join(SP3, 'app')
    rc11_py = os.path.join(RC11, 'python', 'python.exe')
    rc11_app = os.path.join(RC11, 'app')
    v21_py = os.path.join(V21, 'python', 'python.exe')
    v21_app = os.path.join(V21, 'app')

    # ── ① specialmvp：sp3 真实包 ──
    cfg_a = json.dumps({'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'CUDA',
                        'profile': 'specialmvp', 'defaults_version': 10},
                       ensure_ascii=False, indent=2).encode('utf-8')
    ev['cases'].append(run_case(
        'a1_specialmvp_sp3_handselection', 'specialmvp 本代手选（sp3 包）',
        sp3_py, sp3_app, cfg_a,
        expect={'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'CUDA'},
        expect_note=False, form='specialmvp', source='pkg:sp3'))

    # ── ② minimvp：rc11 真实包 ──
    cfg_b1 = json.dumps({'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'NPU',
                         'profile': 'minimvp', 'defaults_version': 9},
                        ensure_ascii=False, indent=2).encode('utf-8')
    ev['cases'].append(run_case(
        'b1_minimvp_rc11_v9_handselection', 'minimvp v9 手选（rc11 包）',
        rc11_py, rc11_app, cfg_b1,
        expect={'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'NPU'},
        expect_note=False, form='minimvp', source='pkg:rc11'))
    ev['cases'].append(run_case(
        'b2_minimvp_rc11_legacy3', 'minimvp 59 B 旧 3 键（rc11 包）',
        rc11_py, rc11_app, REAL_CFG_RAW,
        expect={'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'},
        expect_note=True, form='minimvp', source='pkg:rc11'))

    # ── ②' minimvp：**dev 树形态**（新代码，改动面所在的代码）──
    h_root, h_app = make_harness('minimvp')
    try:
        ev['cases'].append(run_case(
            'b1b_minimvp_dev_v9_handselection', 'minimvp v9 手选（dev 树形态）',
            sp3_py, h_app, cfg_b1,
            expect={'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'NPU'},
            expect_note=False, form='minimvp', source='dev-harness',
            with_check=False))
        ev['cases'].append(run_case(
            'b2b_minimvp_dev_legacy3', 'minimvp 59 B 旧 3 键（dev 树形态）',
            sp3_py, h_app, REAL_CFG_RAW,
            expect={'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'},
            expect_note=True, form='minimvp', source='dev-harness',
            with_check=False))
    finally:
        cleanup_iso(h_root)

    # ── ③ full：**dev 树形态**（新代码）──
    cfg_c1 = json.dumps({'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'GPU.0',
                         'profile': 'full', 'defaults_version': 9},
                        ensure_ascii=False, indent=2).encode('utf-8')
    h_root, h_app = make_harness('full')
    try:
        ev['cases'].append(run_case(
            'b3_full_dev_handselection', '完整版本代手选（dev 树形态）',
            sp3_py, h_app, cfg_c1,
            expect={'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'GPU.0'},
            expect_note=False, form='full', source='dev-harness',
            with_check=False))
        ev['cases'].append(run_case(
            'b4_full_dev_legacy3', '完整版 59 B 旧 3 键（dev 树形态）',
            sp3_py, h_app, REAL_CFG_RAW,
            expect={'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0'},
            expect_note=False, form='full', source='dev-harness',
            with_check=False))
    finally:
        cleanup_iso(h_root)

    # ── ③' full：**v2.1 真实包**（当前交付的完整版，记录用）──
    ev['cases'].append(run_case(
        'b5_full_v21_handselection', '完整版本代手选（v2.1 包，记录用）',
        v21_py, v21_app, cfg_c1,
        expect={'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'GPU.0'},
        expect_note=False, form='full', source='pkg:v2.1'))
    ev['cases'].append(run_case(
        'b6_full_v21_legacy3', '完整版 59 B 旧 3 键（v2.1 包，记录用）',
        v21_py, v21_app, REAL_CFG_RAW,
        expect={'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0'},
        expect_note=False, form='full', source='pkg:v2.1'))

    after = real_cfg_state()
    ev['real_config_after'] = after
    ev['real_config_unchanged'] = (
        after.get('sha256') == ev['real_config_before'].get('sha256')
        and after.get('bytes') == ev['real_config_before'].get('bytes'))
    ev['n_cases'] = len(ev['cases'])
    ev['n_pass'] = sum(1 for c in ev['cases'] if c.get('pass'))
    ev['n_fail'] = ev['n_cases'] - ev['n_pass']
    ev['failed_cases'] = [c['id'] for c in ev['cases'] if not c.get('pass')]
    ev['verdict'] = 'PASS' if (ev['n_fail'] == 0 and ev['real_config_unchanged']) \
        else 'FAIL'
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    for c in ev['cases']:
        print('%-40s %-6s resolved=%s note_ignored=%s'
              % (c['id'], 'PASS' if c.get('pass') else 'FAIL',
                 c.get('resolved_devices'), c.get('note_has_ignored')))
    print('VERDICT=%s  %d/%d  real_cfg_unchanged=%s  -> %s'
          % (ev['verdict'], ev['n_pass'], ev['n_cases'],
             ev['real_config_unchanged'], OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
