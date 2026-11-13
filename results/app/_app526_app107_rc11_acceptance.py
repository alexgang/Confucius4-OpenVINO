# -*- coding: utf-8 -*-
r"""_app526 — **APP-107 rc11 包上验收**（在 **rc11 包目录**上跑，不是 dev 树）。

静态（不占设备）
 1. `models/mt/` 下**只有** `mt2-int8sym-cw-q`（**无** `mt2-int4sym-cw-q`），
    12 文件 / 1 812 121 487 B，且**逐文件 SHA256 与拷贝源一致**（独立重算，不信 MANIFEST）；
 2. MANIFEST 有 `mt/mt2-int8sym-cw-q` 条目：拷贝源路径 + config
    **hidden_size 2048 / num_hidden_layers 32** + 逐文件 SHA 一致；
 3. **行为级**：包内 `translator` 的 `DEFAULT_MODEL` / 「（默认）」/ `auto` label
    都是 **INT8-CW**，`MT_ENGINES` 里**没有** INT4 项；
 4. `app/` 里 `int4sym` 只剩注释/回退链（登记，不当默认值）；
 5. 出厂默认 = ASR=GPU.0 / MT=GPU.0 / TTS=NPU，`defaults_version`=9，profile=minimvp；
 6. 黑名单（bridge_token* / *.pid / *.log）= 0；`.pyc` = 0；bat 全 CRLF+ASCII；
 7. 三份 README：MT INT8-CW 已写明、设备表与出厂默认一致、组 1/组 2 在、
    `%LOCALAPPDATA%\` 有反斜杠、EXT 不可用已写明。

设备作业（持 MACHINE_LOCK）
 8. 包内 python `--check`（**不带设备参数**）⇒ exit 0，且**翻译后端默认是 INT8-CW**；
 9. **10 分钟整链**（`clip_10min_0_600.wav`，不带设备参数）⇒ 报
    ASR RTF、翻译延迟中位/P95、首字、tok/s、TTS 提交/播完/丢弃、
    `CL_OUT_OF_RESOURCES` / 崩溃；
10. GUI 截图（翻译下拉显示 INT8-CW）。

🔴 **A 上真实的 device_config 不能动**（APP-106 §1 / APP-107 §2）：
    探针一律用**临时 LOCALAPPDATA** ⇒ 该目录里的**编译缓存目录用 junction
    指向真目录**（129 GiB 缓存不用重编译），但 **device_config.json 是隔离的**。
    ⇒ 收尾会复核真配置 SHA 未变。

用法：
    python results/app/_app526_app107_rc11_acceptance.py
"""
from __future__ import annotations

import ctypes
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
PKG_NAME = os.path.basename(PKG)
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
OUTROOT = os.path.join(HERE, 'app526_app107_rc11_acceptance')
REPORT = os.path.join(HERE, 'app526_app107_rc11_acceptance.json')
#: 🔴 APP-107 §1.4 / APP-106 §2：README 的实测数字**只能**来自这个文件
MEAS_REPORT = os.path.join(HERE, 'app526_rc11_chain_measurements.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
GUI_SHOT = os.path.join(OUTROOT, 'rc11_gui.png')
GUI_JSON = os.path.join(OUTROOT, 'rc11_gui.json')
MT_SRC = os.path.join(HOME, 'hy_bench', 'ov', 'mt2-int8sym-cw-q')
MT_INT8 = 'mt2-int8sym-cw-q'
MT_INT4 = 'mt2-int4sym-cw-q'
NEW_DEFAULTS = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
EXPECT_INT8_BYTES = 1812121487

TTS_FINAL_RE = re.compile(r'\[TTS\] 最终统计（close 后）：提交\s*(\d+)\s+'
                          r'播完\s*(\d+)\s+丢弃\s*(\d+)')
RTF_RE = re.compile(r'RTF\(计算\)\s*([\d.]+)')
ASR_EXEC_RE = re.compile(r'\[asr06b-stateful\] EXECUTION_DEVICES：encoder=(\S+?)，'
                         r'decoder=(\S+?)（')
TTS_EXEC_RE = re.compile(r'\[tts_engine\] 实测执行设备：(\S+)')
TTS_PLACE_RE = re.compile(r'\[tts_engine\] 各组件落点：(.+)')
TTS_NPU_RE = re.compile(r'\[tts_engine\] 落点统计：NPU 上 (\d+) 个组件')
MT_LINE_RE = re.compile(r'翻译 target=(\S+) 后端=(\S+) 设备 (\S+) state=(\S+) '
                        r'句数 (\d+)\s+延迟中位 ([\d.]+) ms\s+P95 ([\d.]+) ms\s+'
                        r'TTFT ([\d.]+) ms\s+([\d.]+) tok/s')
MT_READY_RE = re.compile(r'\[翻译\] 翻译模型就绪（(.+?) · (\S+)，加载 ([\d.]+) s）')
CL_OUT_RE = re.compile(r'CL_OUT_OF_RESOURCES')

kernel32 = ctypes.windll.kernel32


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def sha256_file(path, buf=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(buf), b''):
            h.update(chunk)
    return h.hexdigest()


def child_env(localappdata=None):
    """🔴 `PYTHONDONTWRITEBYTECODE=1` ⇒ 包目录里不长 `.pyc`；
    `LOCALAPPDATA` 指到**隔离目录** ⇒ A 的真实 device_config 不被碰。"""
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
    if localappdata:
        env['LOCALAPPDATA'] = localappdata
    return env


# ── MACHINE_LOCK（ASCII：模块 PID 时间 用途）────────────────────────
def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('ascii'))
        os.close(fd)
        return payload
    except FileExistsError:
        return None


def release_own_lock(payload):
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                if f.read() == payload:
                    os.remove(LOCK)
                    return True
    except Exception:
        pass
    return False


def lock_is_stale():
    """锁存在但 PID 已死 ⇒ 只登记，**不抢**（fail-closed）。"""
    try:
        with open(LOCK, encoding='utf-8', errors='replace') as f:
            txt = f.read()
    except OSError:
        return None
    parts = txt.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return {'stale': True, 'reason': 'no_pid', 'raw': txt[:120]}
    pid = int(parts[1])
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return {'stale': True, 'reason': 'pid_dead', 'pid': pid,
                'raw': txt[:120]}
    code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return {'stale': code.value != 259, 'pid': pid, 'exit_code': code.value,
            'raw': txt[:120]}


# ── 隔离的 LOCALAPPDATA（缓存用 junction，配置独立）────────────────
def setup_isolated_localappdata():
    """建一个**隔离的** %LOCALAPPDATA%。

    🔴 目的（APP-106 §1 / APP-107 §2）：**不许碰 A 上真实的 device_config.json**；
       但 129 GiB 的编译缓存**不能重编译** ⇒ 缓存目录用 **junction** 指向真目录，
       `device_config.json` 则落在隔离目录里（真目录那份不会被写）。
    """
    real_base = os.path.join(os.environ['LOCALAPPDATA'], 'Confucius4LiveCaption')
    iso_root = os.path.join(OUTROOT, 'iso_localappdata')
    iso_app = os.path.join(iso_root, 'Confucius4LiveCaption')
    os.makedirs(iso_app, exist_ok=True)
    linked, plain, failed = [], [], []
    if os.path.isdir(real_base):
        for name in sorted(os.listdir(real_base)):
            src = os.path.join(real_base, name)
            dst = os.path.join(iso_app, name)
            if os.path.exists(dst):
                continue
            if os.path.isdir(src):
                r = subprocess.run(['cmd', '/c', 'mklink', '/J', dst, src],
                                   capture_output=True, text=True,
                                   errors='replace')
                if r.returncode == 0:
                    linked.append(name)
                else:
                    failed.append({'name': name, 'err': (r.stderr or '')[:120]})
                    os.makedirs(dst, exist_ok=True)
                    plain.append(name)
            else:
                os.makedirs(dst, exist_ok=True)
                plain.append(name)
    return {'iso_root': iso_root, 'iso_app': iso_app,
            'junctions': linked, 'real_dirs': plain, 'failed': failed}


# ── 静态检查 ────────────────────────────────────────────────────────
def check_static(ev):
    items = {}

    # ① models/mt：只有 INT8，且与拷贝源逐字节一致
    mt_dir = os.path.join(PKG, 'models', 'mt')
    names = sorted(os.listdir(mt_dir))
    files = []
    total = 0
    for nm in names:
        p = os.path.join(mt_dir, nm)
        if os.path.isdir(p):
            for dp, _dn, fn in os.walk(p):
                for f in sorted(fn):
                    fp = os.path.join(dp, f)
                    files.append((os.path.relpath(fp, p).replace('\\', '/'), fp))
        else:
            files.append((nm, p))
    for _rel, fp in files:
        total += os.path.getsize(fp)
    src_files = []
    for nm in sorted(os.listdir(MT_SRC)):
        sp = os.path.join(MT_SRC, nm)
        if os.path.isfile(sp):
            src_files.append((nm, sp))
    sha_rows = []
    for rel, fp in files:
        sp = os.path.join(MT_SRC, rel.replace('/', os.sep))
        row = {'name': rel, 'bytes': os.path.getsize(fp),
               'sha256': sha256_file(fp),
               'source_sha256': sha256_file(sp) if os.path.isfile(sp) else None}
        row['match'] = (row['source_sha256'] is not None
                        and row['sha256'] == row['source_sha256'])
        sha_rows.append(row)
    items['mt_int8_only'] = {
        'dirs': names, 'n_files': len(files), 'bytes': total,
        'int4_present': os.path.isdir(os.path.join(mt_dir, MT_INT4)),
        'bytes_match_expected': (total == EXPECT_INT8_BYTES),
        'n_source_files': len(src_files),
        'all_sha_match': all(r['match'] for r in sha_rows),
        'mismatches': [r for r in sha_rows if not r['match']][:5],
        'sha_rows_sample': sha_rows[:3],
        'pass': (names == [MT_INT8] and total == EXPECT_INT8_BYTES
                 and all(r['match'] for r in sha_rows)),
    }

    # ② MANIFEST 条目
    mp = os.path.join(PKG, 'app', 'MANIFEST.json')
    m = json.load(open(mp, encoding='utf-8'))
    e = (m.get('models') or {}).get('mt/' + MT_INT8) or {}
    e4 = (m.get('models') or {}).get('mt/' + MT_INT4) or {}
    cfg = e.get('config') or {}
    flat = {}
    for v in cfg.values():
        flat.update(v)
    items['manifest_int8'] = {
        'manifest_path': mp, 'n_models': m.get('n_models'),
        'all_match': m.get('all_match'), 'n_mismatches': m.get('n_mismatches'),
        'source_path': e.get('source_path'),
        'source_path_ok': str(e.get('source_path', '')).replace('/', '\\')
                         .lower().endswith('hy_bench\\ov\\' + MT_INT8),
        'hidden_size': flat.get('hidden_size'),
        'num_hidden_layers': flat.get('num_hidden_layers'),
        'n_files': len(e.get('files') or []),
        'all_files_match': all(f.get('match') for f in (e.get('files') or [])),
        'int4_entry': {'pkg_exists': e4.get('pkg_exists'),
                       'optional': e4.get('optional'),
                       'absent_in_package': e4.get('absent_in_package')},
        'pass': (m.get('all_match') is True
                 and flat.get('hidden_size') == 2048
                 and flat.get('num_hidden_layers') == 32
                 and all(f.get('match') for f in (e.get('files') or []))
                 and e4.get('pkg_exists') is False),
    }

    # ③ 行为级：默认 / auto = INT8-CW
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app')
    code = ('import json,os,translator;'
            'print(json.dumps({"default_model":str(translator.DEFAULT_MODEL),'
            '"default_quant":translator._default_quant_tag(),'
            '"auto_label":translator._AUTO_LABEL,'
            '"mt_engines":sorted(translator.MT_ENGINES.keys()),'
            '"bundled_int8":translator._is_bundled_q("mt2-int8sym-cw-q"),'
            '"bundled_int4":translator._is_bundled_q("mt2-int4sym-cw-q")},'
            'ensure_ascii=False))')
    r = subprocess.run([py, '-B', '-c', code], cwd=app, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=600,
                       env=child_env())
    j = {}
    if r.returncode == 0:
        m2 = re.search(r'\{.*\}', r.stdout, re.S)
        if m2:
            j = json.loads(m2.group(0))
    items['mt_default_behaviour'] = {
        'exit_code': r.returncode, 'data': j,
        'default_is_int8': (j.get('default_quant') == 'int8'
                            and 'int8sym' in str(j.get('default_model', '')).lower()),
        'auto_label_int8': ('INT8-CW' in str(j.get('auto_label', ''))),
        'no_int4_engine': (not any('int4' in k for k in (j.get('mt_engines') or []))),
        'bundled_int8': j.get('bundled_int8'),
        'bundled_int4': j.get('bundled_int4'),
        'pass': (r.returncode == 0 and j.get('default_quant') == 'int8'
                 and 'int8sym' in str(j.get('default_model', '')).lower()
                 and 'INT8-CW' in str(j.get('auto_label', ''))
                 and not any('int4' in k for k in (j.get('mt_engines') or []))),
    }

    # ④ app/ 里 int4sym 字面（登记：只应是注释/回退链）
    hits = []
    for dp, _dn, fn in os.walk(app):
        for f in sorted(fn):
            if not f.endswith('.py'):
                continue
            p = os.path.join(dp, f)
            for i, ln in enumerate(open(p, encoding='utf-8',
                                        errors='replace'), 1):
                if 'int4sym' in ln:
                    hits.append({'file': os.path.relpath(p, PKG).replace('\\', '/'),
                                 'line': i, 'text': ln.strip()[:140]})
    items['int4_literals_in_app'] = {
        'n_hits': len(hits), 'hits': hits[:20],
        'note': 'APP-107 §2：int4sym 只剩注释/回退链，**不再作为默认值**（判定见 mt_default_behaviour）',
    }

    # ⑤ 出厂默认
    code2 = ('import json,device_config;'
             'print(json.dumps({"default_devices":device_config.DEFAULT_DEVICES,'
             '"profile":__import__("package_profile").PROFILE,'
             '"defaults_version":getattr(device_config,"CONFIG_DEFAULTS_VERSION",None)},'
             'ensure_ascii=False))')
    r2 = subprocess.run([py, '-B', '-c', code2], cwd=app, capture_output=True,
                        text=True, encoding='utf-8', errors='replace', timeout=300,
                        env=child_env())
    d = {}
    if r2.returncode == 0:
        m3 = re.search(r'\{.*\}', r2.stdout, re.S)
        if m3:
            d = json.loads(m3.group(0))
    items['factory_defaults'] = {
        'data': d,
        'pass': (d.get('default_devices') == NEW_DEFAULTS
                 and d.get('defaults_version') == 9
                 and d.get('profile') == 'minimvp'),
    }

    # ⑥ 黑名单 / .pyc / bat
    import fnmatch
    bl = []
    n_pyc = 0
    bats = []
    for dp, _dn, fn in os.walk(PKG):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, PKG).replace('\\', '/')
            if f.endswith('.pyc'):
                n_pyc += 1
            nm = f.lower()
            for pat in ('bridge_token*', '*.pid', '*.log'):
                if fnmatch.fnmatch(nm, pat):
                    bl.append(rel)
            if f.lower().endswith('.bat'):
                b = open(p, 'rb').read()
                crlf = b.count(b'\r\n')
                bats.append({'file': rel, 'crlf': crlf,
                             'bare_lf': b.count(b'\n') - crlf,
                             'non_ascii': sum(1 for x in b if x > 127),
                             'pass': (crlf > 0 and b.count(b'\n') == crlf
                                      and all(x <= 127 for x in b))})
    items['hygiene'] = {
        'n_blacklist': len(bl), 'blacklist': bl[:10], 'n_pyc': n_pyc,
        'bats': bats, 'n_bat_fail': sum(1 for b in bats if not b['pass']),
        'pass': (not bl and n_pyc == 0
                 and all(b['pass'] for b in bats)),
    }

    # ⑦ README
    rd = {}
    for name in ('README_zh.md', 'README_en.md', 'README_perftest.txt'):
        p = os.path.join(PKG, name)
        t = open(p, encoding='utf-8', errors='replace').read()
        rd[name] = {
            'bytes': len(t.encode('utf-8')),
            'has_int8': ('INT8' in t),
            'has_int4_dir_literal': ('mt2-int4sym-cw-q' in t),
            'has_groups': (('组 1' in t and '组 2' in t) if name.endswith('txt')
                           else True),
            'has_localapp_backslash': ('%LOCALAPPDATA%\\Confucius4LiveCaption' in t),
            'has_ext_note': ('EXT' in t and ('不可用' in t or 'does NOT work' in t)),
            'has_measured_placeholder': ('待 A 机整链实测' in t
                                         or 'pending machine-A' in t),
            'has_measured_numbers': ('tok/s' in t and 'RTF' in t),
        }
    items['readmes'] = {
        'files': rd,
        'pass': (all(v['has_int8'] for v in rd.values())
                 and all(v['has_localapp_backslash'] for v in rd.values())
                 and all(v['has_ext_note'] for v in rd.values())),
    }

    ev['items'] = items
    ev['static_verdict'] = ('PASS' if all(it.get('pass', True)
                                          for it in items.values()) else 'FAIL')
    return items


def main():
    os.makedirs(OUTROOT, exist_ok=True)
    ev = {'at': now(), 'pkg': PKG, 'zip': ZIP,
          'correction': 'APP-107 (+APP-106 §2)',
          'items': {}, 'audio': AUDIO,
          'lock': {'module': 'app', 'pid': os.getpid(), 'started': None,
                   'ended': None, 'timing_valid': False}}

    # 🔴 A 上真实 device_config.json：**跑之前先记 SHA**
    real_cfg = os.path.join(os.environ['LOCALAPPDATA'],
                            'Confucius4LiveCaption', 'device_config.json')
    ev['real_device_config'] = {'path': real_cfg,
                                'sha256_before': sha256_file(real_cfg),
                                'bytes_before': os.path.getsize(real_cfg)}
    print('[static] 真配置 SHA(before) =', ev['real_device_config']['sha256_before'],
          flush=True)

    check_static(ev)
    print('[static] verdict =', ev['static_verdict'], flush=True)

    # ── 设备作业：持锁 ───────────────────────────────────────────────
    payload = acquire_lock('app107_rc11_acceptance')
    if not payload:
        st = lock_is_stale()
        ev['verdict'] = 'SKIPPED_LOCK_BUSY'
        ev['lock_state'] = st
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('!! 机器锁在位 ⇒ 本轮不做设备作业：%s' % st)
        return 1
    ev['lock']['started'] = now()
    try:
        iso = setup_isolated_localappdata()
        ev['isolated_localappdata'] = iso
        print('[iso] LOCALAPPDATA =', iso['iso_root'],
              '| junction 缓存目录 %d 个' % len(iso['junctions']), flush=True)
        env = child_env(iso['iso_root'])

        py = os.path.join(PKG, 'python', 'python.exe')
        app_py = os.path.join(PKG, 'app', 'live_caption_app.py')

        # ⑧ --check（不带设备参数；临时 LOCALAPPDATA ⇒ 不碰 A 的真配置）
        cp = os.path.join(OUTROOT, 'check.log')
        with open(cp, 'wb') as lf:
            p = subprocess.run([py, '-B', '-s', app_py, '--check'], cwd=PKG,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=1800,
                               env=env)
        cl = open(cp, 'rb').read().decode('utf-8', errors='replace')
        ready = MT_READY_RE.search(cl)
        # 🔴 APP-107 §2 的口径是「**翻译后端显示 INT8-CW 为默认且可用**」
        #   ⇒ 判据取 `--check` 的**「翻译后端」小节**本身：
        #     ① 有 `[ OK ] … INT8-CW（默认）` 行；
        #     ② 有 `[ OK ] 自动 · INT8-CW 模型（默认）` 行；
        #     ③ **所有** INT4-CW 行都必须标「本包不附带该量化版本」
        #        （不许出现 `[ OK ] … INT4-CW`）；
        #     ④ 翻译设备是 GPU.0。
        #   ⚠️ 「[翻译] 翻译模型就绪（…）」那句**只在整链里出现**（模型真加载时），
        #      `--check` 不加载模型 ⇒ 拿它当判据是**错判据**（第 1 轮验收踩过）。
        mt_lines = [ln for ln in cl.splitlines()
                    if ('INT8-CW' in ln or 'INT4-CW' in ln
                        or '自动 ·' in ln)]
        ok_int8_default = any(re.search(r'\[ OK \].*INT8-CW（默认）', ln)
                               for ln in mt_lines)
        ok_auto_int8 = any(re.search(r'\[ OK \].*自动 · INT8-CW 模型（默认）', ln)
                           for ln in mt_lines)
        int4_lines = [ln for ln in mt_lines if 'INT4-CW' in ln]
        int4_all_not_bundled = (bool(int4_lines)
                                and all('本包不附带' in ln for ln in int4_lines))
        mt_device_gpu0 = any('GPU.0' in ln for ln in mt_lines)
        ev['items']['10_pkg_check'] = {
            'exit_code': p.returncode, 'log': cp, 'log_bytes': len(cl),
            'n_ok_lines': len(re.findall(r'\[ OK \]', cl)),
            'mt_section_lines': mt_lines,
            'ok_int8_default': ok_int8_default,
            'ok_auto_int8': ok_auto_int8,
            'int4_lines': int4_lines,
            'int4_all_not_bundled': int4_all_not_bundled,
            'mt_device_gpu0': mt_device_gpu0,
            'mt_ready_line': (ready.group(0) if ready else None),
            'device_lines': [ln for ln in cl.splitlines()
                             if ('ASR' in ln or '翻译' in ln)
                             and ('GPU.0' in ln or 'NPU' in ln)][:14],
            'tail': cl[-1200:],
            'pass': (p.returncode == 0 and ok_int8_default and ok_auto_int8
                     and int4_all_not_bundled and mt_device_gpu0),
        }
        print('[10] --check exit=%s int8_default=%s auto_int8=%s '
              'int4_not_bundled=%s' %
              (p.returncode, ok_int8_default, ok_auto_int8,
               int4_all_not_bundled), flush=True)

        # ⑨ 10 分钟整链（不带设备参数 ⇒ 出厂默认）
        lp = os.path.join(OUTROOT, 'chain10min.log')
        tp = os.path.join(OUTROOT, 'chain10min.txt')
        cmd = [py, '-B', '-s', app_py, '--cli', '--file', AUDIO,
               '--max-seconds', '600', '--out', tp,
               '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A']
        ev['chain_cmd'] = cmd
        t0 = time.time()
        with open(lp, 'wb') as lf:
            cp2 = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                 stderr=subprocess.STDOUT, timeout=3000,
                                 env=env)
        lg = open(lp, 'rb').read().decode('utf-8', errors='replace')
        sub = (open(tp, encoding='utf-8', errors='replace').read().strip()
               if os.path.isfile(tp) else '')
        tf = TTS_FINAL_RE.search(lg)
        rt = RTF_RE.search(lg)
        ex = ASR_EXEC_RE.search(lg)
        tex = TTS_EXEC_RE.search(lg)
        tplace = TTS_PLACE_RE.search(lg)
        tnpu = TTS_NPU_RE.search(lg)
        mtl = MT_LINE_RE.search(lg)
        mready = MT_READY_RE.search(lg)
        asr_dev = ex.group(1) if ex else None
        tts_dev = tex.group(1) if tex else None
        n_cl = len(CL_OUT_RE.findall(lg))
        chain = {
            'exit_code': cp2.returncode, 'wall_s': round(time.time() - t0, 1),
            'log': lp, 'output': tp, 'output_chars': len(sub),
            'replacement_chars': sub.count('\ufffd'),
            'asr_rtf': float(rt.group(1)) if rt else None,
            'asr_exec_encoder': asr_dev,
            'asr_exec_decoder': ex.group(2) if ex else None,
            'tts_exec_devices': tts_dev,
            'tts_places': tplace.group(1) if tplace else None,
            'tts_npu_components': int(tnpu.group(1)) if tnpu else None,
            'tts_submitted': int(tf.group(1)) if tf else None,
            'tts_played': int(tf.group(2)) if tf else None,
            'tts_dropped': int(tf.group(3)) if tf else None,
            'cl_out_of_resources': n_cl,
            'mt_line': mtl.group(0) if mtl else None,
            'mt_target': mtl.group(1) if mtl else None,
            'mt_backend': mtl.group(2) if mtl else None,
            'mt_device': mtl.group(3) if mtl else None,
            'mt_state': mtl.group(4) if mtl else None,
            'mt_sentences': int(mtl.group(5)) if mtl else None,
            'mt_latency_median_ms': float(mtl.group(6)) if mtl else None,
            'mt_latency_p95_ms': float(mtl.group(7)) if mtl else None,
            'mt_ttft_ms': float(mtl.group(8)) if mtl else None,
            'mt_tok_per_s': float(mtl.group(9)) if mtl else None,
            'mt_ready_line': mready.group(0) if mready else None,
            'mt_ready_label': mready.group(1) if mready else None,
            'n_traceback': lg.count('Traceback (most recent call last)'),
        }
        chain['pass'] = bool(
            cp2.returncode == 0 and sub and '\ufffd' not in sub
            and tf and int(tf.group(2)) >= 1
            and asr_dev == 'GPU.0' and tts_dev is not None and 'NPU' in tts_dev
            and mtl is not None and n_cl == 0
            and chain['n_traceback'] == 0)
        ev['items']['12_chain_10min'] = chain
        print('[12] chain exit=%s rtf=%s mt=%s tts=%s played=%s cl=%s' %
              (cp2.returncode, chain['asr_rtf'], chain['mt_latency_median_ms'],
               tts_dev, chain['tts_played'], n_cl), flush=True)

        # ⑩ GUI 截图（不加载模型 ⇒ 不占设备）
        g = subprocess.run([py, '-B', '-s',
                            os.path.join(HERE, '_app525_app107_rc11_gui_shot.py'),
                            PKG, GUI_SHOT, GUI_JSON],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=900, env=env)
        gjson = {}
        if os.path.isfile(GUI_JSON):
            gjson = json.load(open(GUI_JSON, encoding='utf-8'))
        ev['items']['11_gui'] = {
            'exit_code': g.returncode, 'shot': GUI_SHOT,
            'shot_bytes': gjson.get('shot_bytes'),
            'verdict': gjson.get('verdict'),
            'checks': gjson.get('checks'),
            'mt_combo_labels': gjson.get('mt_combo_labels'),
            'mt_auto_label': gjson.get('mt_auto_label'),
            'default_devices': gjson.get('default_devices'),
            'device_notes': gjson.get('device_notes'),
            'stdout_tail': (g.stdout or '')[-800:],
            'stderr_tail': (g.stderr or '')[-800:],
            'pass': (g.returncode == 0 and gjson.get('verdict') == 'PASS'),
        }
        print('[11] GUI verdict=%s' % ev['items']['11_gui']['verdict'], flush=True)

    finally:
        ev['lock']['ended'] = now()
        ev['lock']['released'] = release_own_lock(payload)

    # 🔴 收尾复核：**A 上真实的 device_config.json 必须没被碰**
    ev['real_device_config']['sha256_after'] = sha256_file(real_cfg)
    ev['real_device_config']['bytes_after'] = os.path.getsize(real_cfg)
    ev['real_device_config']['unchanged'] = (
        ev['real_device_config']['sha256_after']
        == ev['real_device_config']['sha256_before'])

    # ── 写实测数据（README 的数字**只能**来自这里）────────────────────
    ch = ev['items'].get('12_chain_10min') or {}
    meas = {
        'at': now(), 'pkg': PKG, 'audio': AUDIO,
        'defaults': NEW_DEFAULTS,
        'mt_model': MT_INT8,
        'mt_quant': 'INT8-CW',
        'asr_rtf': ch.get('asr_rtf'),
        'asr_exec_encoder': ch.get('asr_exec_encoder'),
        'asr_exec_decoder': ch.get('asr_exec_decoder'),
        'mt_latency_median_ms': ch.get('mt_latency_median_ms'),
        'mt_latency_p95_ms': ch.get('mt_latency_p95_ms'),
        'mt_ttft_ms': ch.get('mt_ttft_ms'),
        'mt_tok_per_s': ch.get('mt_tok_per_s'),
        'mt_sentences': ch.get('mt_sentences'),
        'tts_submitted': ch.get('tts_submitted'),
        'tts_played': ch.get('tts_played'),
        'tts_dropped': ch.get('tts_dropped'),
        'tts_device': ch.get('tts_exec_devices'),
        'cl_out_of_resources': ch.get('cl_out_of_resources'),
        'n_traceback': ch.get('n_traceback'),
        'wall_s': ch.get('wall_s'),
        'source': 'app526_app107_rc11_acceptance/chain10min.log',
    }
    json.dump(meas, open(MEAS_REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    ev['measurements'] = meas

    # ── 总判定 ───────────────────────────────────────────────────────
    static_ok = (ev.get('static_verdict') == 'PASS')
    dev_items = [ev['items'].get(k) for k in
                 ('10_pkg_check', '11_gui', '12_chain_10min')]
    dev_ok = all(it and it.get('pass') for it in dev_items)
    real_ok = ev['real_device_config']['unchanged']
    ev['verdict'] = ('PASS' if (static_ok and dev_ok and real_ok) else 'FAIL')
    ev['verdict_detail'] = {'static': static_ok, 'device': dev_ok,
                            'real_config_untouched': real_ok,
                            'device_items': {k: (v or {}).get('pass')
                                             for k, v in
                                             ev['items'].items()}}
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('VERDICT', ev['verdict'], ev['verdict_detail'])
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
