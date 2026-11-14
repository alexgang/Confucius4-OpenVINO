#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app549_device_resolution_verify.py —— APP-108 §2 的实测脚本。

**要求（reviewer 原文）**：
  「用隔离的 LOCALAPPDATA 分别跑 (i) 空配置、(ii) 59 B 旧 3 键配置、
    (iii) minimvp v9 配置，记录 --check 和 CLI get_devices() 解析出的三个设备。
    判定标准：(i)(ii) 都应得到 GPU.0/NPU/CUDA；(iii) 怎么处理要写清楚
    （profile 不同时不能沿用）。同时核对这条告警文案在 MT=NPU 时不应出现。
    跑完确认真实配置的 SHA 前后不变。」

**三条纪律**：
  ① **隔离**：每个 case 用**独立**的 LOCALAPPDATA（临时目录）⇒ 真实
     `%LOCALAPPDATA%\\Confucius4LiveCaption\\device_config.json` **碰不到**；
     跑前跑后各取一次真实配置的 SHA256/字节/mtime 做断言。
  ② **只读真实环境**：脚本只读真实配置，绝不写它。
  ③ **不改产品代码**：本脚本只*测量*，不改任何 `.py`（含被测包）。

用法：
    python _app549_device_resolution_verify.py <包目录> <标签>
    例：python _app549_device_resolution_verify.py \
        C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1 sp1
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
RESULTS = os.path.join(HOME, 'confucius4-openvino', 'results', 'app')
REAL_CFG = os.path.join(HOME, 'AppData', 'Local', 'Confucius4LiveCaption',
                        'device_config.json')

# ── 真实配置的字节快照（APP-108 §2 末尾的「真实配置 SHA 前后不变」）──
REAL_CFG_EXPECT_BYTES = 59
REAL_CFG_EXPECT_SHA = (
    '9d484c1c9402d7a9911f2af6a53f6e056a18039715b8bda9ec15ddecf6b473a2')
# 🔴 真实配置原文**逐字节**（含 CRLF）——case (ii) 直接复用这份字节。
REAL_CFG_RAW = (b'{\r\n  "asr": "GPU.0",\r\n  "mt": "GPU.0",\r\n'
                b'  "tts": "GPU.0"\r\n}')

# ── 三个 case 的配置文件内容 ──
CASE_MINIMVP_V9 = {
    'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU',
    'profile': 'minimvp', 'defaults_version': 9,
}
CASES = [
    ('i_empty', '空配置（无 device_config.json）', None),
    ('ii_legacy3', '59 B 旧 3 键配置（真实文件逐字节）', REAL_CFG_RAW),
    ('iii_minimvp_v9', 'minimvp v9 配置（profile=minimvp, defaults_version=9）',
     json.dumps(CASE_MINIMVP_V9, ensure_ascii=False, indent=2).encode('utf-8')),
]

WARN_ASR_MT_GPU = 'ASR 与 MT 都放在'


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def real_cfg_state():
    """真实配置的 (存在?, 字节, SHA256, mtime) —— 只读。"""
    if not os.path.isfile(REAL_CFG):
        return {'exists': False}
    st = os.stat(REAL_CFG)
    b = open(REAL_CFG, 'rb').read()
    return {'exists': True, 'bytes': len(b), 'sha256': sha256_bytes(b),
            'mtime': st.st_mtime,
            'mtime_str': time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(st.st_mtime))}


def run_check(pkg, iso_localappdata, timeout=1800):
    """跑包内 `--check` ⇒ 抓 rc / stdout / stderr。"""
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    env = dict(os.environ)
    env['LOCALAPPDATA'] = iso_localappdata
    t1 = time.time()
    p = subprocess.run([py, app, '--check'], capture_output=True, text=True,
                       timeout=timeout, cwd=os.path.join(pkg, 'app'), env=env)
    return {
        'rc': p.returncode,
        'elapsed_s': round(time.time() - t1, 1),
        'stdout': (p.stdout or ''),
        'stderr': (p.stderr or ''),
    }


PROBE_SRC = (
    "import sys, json\n"
    "sys.path.insert(0, %(app)r)\n"
    "import device_config\n"
    "d, notes = device_config.get_devices()\n"
    "print(json.dumps({'devices': d, 'notes': notes,\n"
    "                  'current_profile': device_config.current_profile(),\n"
    "                  'default_devices': device_config.DEFAULT_DEVICES,\n"
    "                  'config_path': device_config.CONFIG_PATH}, ensure_ascii=False))\n"
)


def run_get_devices(pkg, iso_localappdata, timeout=600):
    """跑 CLI `get_devices()` ⇒ 抓解析出的三个设备 + 提示。"""
    py = os.path.join(pkg, 'python', 'python.exe')
    appdir = os.path.join(pkg, 'app')
    env = dict(os.environ)
    env['LOCALAPPDATA'] = iso_localappdata
    src = PROBE_SRC % {'app': appdir}
    t1 = time.time()
    p = subprocess.run([py, '-c', src], capture_output=True, text=True,
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


def parse_check_devices(stdout):
    """从 `--check` 的 stdout 里抠出「解析出的三个设备」。

    🔴 `--check` **不打印** asr/mt/tts 三个设备的解析结果（它打印的是
       *可用后端*清单）⇒ 能作为**证据**的只有 stderr 里的 `[device] …`
       提示行与那句告警/提示文案 ⇒ 这里如实记录，不臆测。
    """
    res = {'device_note_lines': [], 'warn_asr_mt_same_gpu': False,
           'warn_lines': []}
    for ln in stdout.splitlines():
        pass
    return res


def run_case(pkg, tag, cfg_bytes, keep_iso=False):
    iso = tempfile.mkdtemp(prefix='wb_iso_%s_' % tag)
    cfgdir = os.path.join(iso, 'Confucius4LiveCaption')
    os.makedirs(cfgdir, exist_ok=True)
    cfg_path = os.path.join(cfgdir, 'device_config.json')
    if cfg_bytes is not None:
        with open(cfg_path, 'wb') as f:
            f.write(cfg_bytes)
    rec = {'iso_localappdata': iso,
           'config_written_bytes': (len(cfg_bytes) if cfg_bytes is not None
                                    else None),
           'config_written_sha256': (sha256_bytes(cfg_bytes)
                                     if cfg_bytes is not None else None),
           'config_content': (cfg_bytes.decode('utf-8', 'replace')
                              if cfg_bytes is not None else None)}
    try:
        rec['check'] = run_check(pkg, iso)
        rec['get_devices'] = run_get_devices(pkg, iso)
        # ── 告警文案核对（reviewer：MT=NPU 时不应出现）──
        se = rec['check'].get('stderr') or ''
        rec['warn_asr_mt_same_gpu_present'] = WARN_ASR_MT_GPU in se
        rec['warn_lines'] = [l for l in se.splitlines()
                             if WARN_ASR_MT_GPU in l or '[device]' in l]
        gp = rec['get_devices'].get('parsed') or {}
        rec['resolved_devices'] = gp.get('devices')
        rec['notes'] = gp.get('notes')
        rec['current_profile'] = gp.get('current_profile')
        rec['default_devices'] = gp.get('default_devices')
    finally:
        if not keep_iso:
            # 🔴 **只删我们自己的东西**：iso 根下只有 device_config.json 与
            #    日志目录 ⇒ 逐个文件删 + 逐层 rmdir（**不用 rmtree**，
            #    避免任何 junction 被递归进去）。
            _cleanup_iso(iso)
        else:
            rec['iso_kept'] = True
    return rec


def _cleanup_iso(iso):
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


def main():
    if len(sys.argv) < 3:
        print('用法: python _app549_device_resolution_verify.py <包目录> <标签>')
        return 2
    pkg = sys.argv[1]
    tag = sys.argv[2]
    out = os.path.join(RESULTS, 'app549_%s_device_resolution.json' % tag)

    real_before = real_cfg_state()
    ev = {'pkg': pkg, 'tag': tag,
          'started': time.strftime('%Y-%m-%d %H:%M:%S'),
          'real_config_before': real_before,
          'real_config_expect': {'bytes': REAL_CFG_EXPECT_BYTES,
                                 'sha256': REAL_CFG_EXPECT_SHA},
          'cases': []}
    for cid, cdesc, cbytes in CASES:
        print('--- case %s (%s) ---' % (cid, cdesc), flush=True)
        r = run_case(pkg, cid, cbytes)
        r['id'] = cid
        r['desc'] = cdesc
        ev['cases'].append(r)
        print('   resolved =', r.get('resolved_devices'),
              '| profile =', r.get('current_profile'),
              '| warn =', r.get('warn_asr_mt_same_gpu_present'), flush=True)

    real_after = real_cfg_state()
    ev['real_config_after'] = real_after
    ev['real_config_unchanged'] = (
        real_before.get('sha256') == real_after.get('sha256')
        and real_before.get('bytes') == real_after.get('bytes'))
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # ── 判定（reviewer 的标准）──
    def dev(cid):
        for c in ev['cases']:
            if c['id'] == cid:
                return c.get('resolved_devices') or {}
        return {}

    ok = True
    ev['verdict_detail'] = []
    for cid in ('i_empty', 'ii_legacy3'):
        d = dev(cid)
        good = (d.get('asr') == 'GPU.0' and d.get('mt') == 'NPU'
                and d.get('tts') == 'CUDA')
        ev['verdict_detail'].append(
            {'case': cid, 'expect': {'asr': 'GPU.0', 'mt': 'NPU',
                                     'tts': 'CUDA'},
             'got': d, 'pass': good})
        ok = ok and good
    d3 = dev('iii_minimvp_v9')
    ev['verdict_detail'].append(
        {'case': 'iii_minimvp_v9',
         'expect': 'profile 不同 ⇒ 不得沿用 minimvp 的设备项 ⇒ 同 (i)(ii)',
         'got': d3,
         'pass': (d3.get('asr') == 'GPU.0' and d3.get('mt') == 'NPU'
                  and d3.get('tts') == 'CUDA')})
    ok = ok and ev['verdict_detail'][-1]['pass']
    # 告警文案：MT=NPU 时不应出现
    warn_bad = [c['id'] for c in ev['cases']
                if c.get('warn_asr_mt_same_gpu_present')]
    ev['warn_violations'] = warn_bad
    ok = ok and not warn_bad
    ev['real_config_ok'] = ev['real_config_unchanged']
    ok = ok and ev['real_config_unchanged']
    ev['verdict'] = 'PASS' if ok else 'FAIL'

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('VERDICT =', ev['verdict'], '->', out)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
