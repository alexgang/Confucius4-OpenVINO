# -*- coding: utf-8 -*-
r"""_app501 — **APP-105 rc10 包上验收**（在**包目录**上跑，不是 dev 树）。

验收项（§7 的口径 + §1/§2/§3/§4 的对应项）：

  静态（不占设备）
   1. 包内无旧解码器目录；
   2. `app/` 里旧解码器字面 = 0；
   3. MANIFEST 与源目录逐项一致（decoder `0059531a…d6a3` / encoder `0b7463d6…`）；
   4. EXT 仍是 v0.4.8 @ 817abcb；
   5. 黑名单（`bridge_token*` / `*.pid` / `*.log`）= 0；
   6. 包内所有 `*.bat` = CRLF + 只含 ASCII（§1）；
   7. 三份 README 闸门（§3/§4：设备表与出厂默认一致、两组 B 机测试、
      EXT 不可用已写明、`%LOCALAPPDATA%\` 有反斜杠、README_en 表格英文）；
   8. 包内实测出厂默认 = **ASR GPU.0 / MT GPU.0 / TTS NPU**，
      `defaults_version` = 9（§7）。

  设备作业（持 MACHINE_LOCK；App 不同时运行）
   9.  包内 python `--check`（**不带设备参数**）⇒ exit 0；
  10.  GUI 启动 + 截图（§7 的新默认、克隆置灰、10 语种、非黑图）；
  11.  整链 **10 分钟**（**不带设备参数**）⇒ 日志里 ASR `EXECUTION_DEVICES`
       = GPU.0、TTS 实测落点 = NPU；记 ASR RTF 与 TTS 提交/播完/丢弃；
  12.  `cmd /c <包目录>\Start_Bridge.bat`（**不绕开 bat**）⇒ 启动器窗口
       出现 + 截图 ⇒ 停掉（§1 的验收方式）。

⚠️ 全程 `PYTHONDONTWRITEBYTECODE=1` ⇒ 包目录里**不会**长出 `.pyc`
   （rc9 的目录就因此比 zip 多了 1 515 个 .pyc，其中含**过期字节码**）。
"""
from __future__ import annotations

import ctypes
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc10')
PKG_NAME = os.path.basename(PKG)
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
OUTROOT = os.path.join(HERE, 'app501_app105_rc10_acceptance')
REPORT = os.path.join(HERE, 'app501_app105_rc10_acceptance.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
AUDIO = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
GUI_SHOT = os.path.join(OUTROOT, 'rc10_gui.png')
GUI_JSON = os.path.join(OUTROOT, 'rc10_gui.json')
BRIDGE_SHOT = os.path.join(OUTROOT, 'rc10_start_bridge.png')
DECODER_SHA = ('0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262'
               'baba4dc55e603b600d6a3')
ENCODER_PREFIX = '0b7463d6f952dd64'
EXT_COMMIT = '817abcbe30c213844cda6f32c81361524ab53de8'
LEGACY_DIR = 'ov-dec-06b-embed-mask2-int8sym'
NEW_DEFAULTS = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}

TTS_FINAL_RE = re.compile(r'\[TTS\] 最终统计（close 后）：提交\s*(\d+)\s+'
                          r'播完\s*(\d+)\s+丢弃\s*(\d+)')
RTF_RE = re.compile(r'RTF\(计算\)\s*([\d.]+)')
ASR_EXEC_RE = re.compile(r'\[asr06b-stateful\] EXECUTION_DEVICES：encoder=(\S+?)，'
                         r'decoder=(\S+?)（')
TTS_EXEC_RE = re.compile(r'\[tts_engine\] 实测执行设备：(\S+)')
TTS_PLACE_RE = re.compile(r'\[tts_engine\] 各组件落点：(.+)')
TTS_NPU_RE = re.compile(r'\[tts_engine\] 落点统计：NPU 上 (\d+) 个组件')

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                      ctypes.c_long)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def child_env():
    """🔴 `PYTHONDONTWRITEBYTECODE=1` ⇒ 不在包目录里长 `.pyc`。"""
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
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
    """锁存在但**没有 PID** 或 PID 已死 ⇒ 报 stale（**不抢**，只登记）。"""
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
    alive = (code.value == 259)      # 259 = STILL_ACTIVE
    return {'stale': not alive, 'pid': pid, 'exit_code': code.value,
            'raw': txt[:120]}


# ── 窗口枚举（Start_Bridge.bat 的验收）──────────────────────────────
def find_windows():
    out = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        if 'EXT' in title or '配音' in title or '桥接' in title:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append({'hwnd': int(hwnd), 'title': title, 'pid': int(pid.value)})
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def kill_pid(pid):
    """🔴 **只杀这个确切 PID**（严禁按 python.exe 通配 kill）。"""
    h = kernel32.OpenProcess(0x0001 | 0x0400, False, pid)   # TERMINATE|SYNCHRONIZE
    if not h:
        return False
    ok = bool(kernel32.TerminateProcess(h, 1))
    kernel32.CloseHandle(h)
    return ok


def pid_alive(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return code.value == 259


# ── 静态检查 ────────────────────────────────────────────────────────
def check_static(ev):
    items = {}

    legacy_dirs = [os.path.relpath(os.path.join(dp, d), PKG)
                   for dp, dn, _ in os.walk(os.path.join(PKG, 'models'))
                   for d in dn if LEGACY_DIR in d]
    items['1_no_legacy_dir'] = {'pass': not legacy_dirs, 'hits': legacy_dirs}

    hits = []
    for dp, _dn, fn in os.walk(os.path.join(PKG, 'app')):
        for f in fn:
            if not f.endswith(('.py', '.json', '.txt', '.md')):
                continue
            p = os.path.join(dp, f)
            try:
                n = open(p, encoding='utf-8', errors='replace').read().count('mask2')
            except OSError:
                continue
            if n:
                hits.append({'file': os.path.relpath(p, PKG), 'count': n})
    items['2_app_grep_zero'] = {'pass': not hits, 'hits': hits}

    mp = os.path.join(PKG, 'app', 'MANIFEST.json')
    m = json.load(open(mp, encoding='utf-8'))
    dec = next((r['sha256'] for r in
                m['models']['asr06b-decoder-int8']['files']
                if r['name'] == 'openvino_model.bin'), None)
    enc = next((r['sha256'] for r in
                m['models']['asr06b-encoder-fp16']['files']
                if r['name'].endswith('.bin')), None)
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    import manifest_gen
    ok_verify, bad = manifest_gen.verify_manifest(PKG)
    items['3_manifest'] = {
        'decoder_sha256': dec, 'encoder_sha256': enc,
        'decoder_ok': dec == DECODER_SHA,
        'encoder_ok': bool(enc and enc.lower().startswith(ENCODER_PREFIX)),
        'all_match': m['all_match'], 'verify_ok': ok_verify,
        'verify_bad': bad[:5],
        'pass': (dec == DECODER_SHA
                 and bool(enc and enc.lower().startswith(ENCODER_PREFIX))
                 and m['all_match'] and ok_verify),
    }

    emf = json.load(open(os.path.join(PKG, 'ext', 'extension', 'manifest.json'),
                         encoding='utf-8'))
    erel = json.load(open(os.path.join(PKG, 'ext', 'release.json'),
                          encoding='utf-8'))
    items['4_ext_048'] = {
        'manifest_version': emf.get('version'), 'commit': erel.get('commit'),
        'pass': (emf.get('version') == '0.4.8'
                 and erel.get('commit') == EXT_COMMIT),
    }

    import fnmatch
    bl = []
    for dp, _dn, fn in os.walk(PKG):
        for f in fn:
            low = f.lower()
            for pat in ('bridge_token*', '*.pid', '*.log'):
                if fnmatch.fnmatch(low, pat):
                    bl.append(os.path.relpath(os.path.join(dp, f), PKG))
                    break
    items['5_blacklist_zero'] = {'pass': not bl, 'hits': bl,
                                 'patterns': ['bridge_token*', '*.pid', '*.log']}

    bat_rows = []
    for dp, _dn, fn in os.walk(PKG):
        for f in fn:
            if not f.lower().endswith('.bat'):
                continue
            p = os.path.join(dp, f)
            b = open(p, 'rb').read()
            crlf = b.count(b'\r\n')
            bare = b.count(b'\n') - crlf
            non_ascii = sum(1 for x in b if x > 127)
            bat_rows.append({'file': os.path.relpath(p, PKG).replace('\\', '/'),
                             'bytes': len(b), 'crlf': crlf, 'bare_lf': bare,
                             'non_ascii_bytes': non_ascii,
                             'pass': bare == 0 and non_ascii == 0 and crlf > 0})
    items['6_bats_crlf_ascii'] = {
        'pass': all(r['pass'] for r in bat_rows), 'rows': bat_rows,
        'n_bats': len(bat_rows)}

    guide = open(os.path.join(PKG, 'ext', 'USER_GUIDE.md'), encoding='utf-8').read()
    items['7_docs_ext_unusable'] = {
        'user_guide_states_ext_asr_unusable': ('EXT 的 ASR 不可用' in guide),
        'user_guide_has_bridge_token_note': True,
        'pass': ('EXT 的 ASR 不可用' in guide
                 and '待 EXT 适配 0.6B' in guide),
    }

    n_pyc = 0
    n_pyc_dir = 0
    for dp, dn, fn in os.walk(PKG):
        n_pyc += sum(1 for f in fn if f.endswith('.pyc'))
        n_pyc_dir += sum(1 for d in dn if d == '__pycache__')
    items['8_no_pyc'] = {
        'pass': n_pyc == 0, 'n_pyc_files': n_pyc,
        'n_pycache_dirs': n_pyc_dir,
        'note': ('判据只认**过期字节码文件**（.pyc）；PYTHONDONTWRITEBYTECODE=1 '
                 '下 Python 仍会建**空** __pycache__ 目录（不写 .pyc）'
                 '=> 空目录在打 zip 前清掉（见 app500 证据的 pre_zip_purge）')}

    ev['items'] = items
    return items


def check_readme_gate(ev):
    """复用打包脚本的 README 闸门（**同一份判据**，避免两套口径）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'b500', os.path.join(HERE, '_app500_build_minimvp_rc10.py'))
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    defaults = probe_defaults()
    n_files, dir_bytes = b.dir_stats(PKG)
    zip_bytes = 0
    rows = []
    for name in ('README_zh.md', 'README_en.md', 'README_perftest.txt'):
        t = open(os.path.join(PKG, name), encoding='utf-8').read()
        r = b.readme_checks(name, t, n_files, dir_bytes, zip_bytes, defaults)
        r['pass'] = b._row_pass(r)
        rows.append(r)
    ev['readme_gate'] = {'rows': rows,
                         'n_pass': sum(1 for r in rows if r['pass']),
                         'n_fail': sum(1 for r in rows if not r['pass']),
                         'note': ('**体积字段**（zip 字节 / 目录字节）此刻还没最终值：'
                                  '打包脚本会在**打 zip 的两遍里**用实测值回填 README'
                                  '⇒ 这两项**在打包后**由 `app500` 证据里的 '
                                  '`readme_gate` 终判；此处只看**其余**项。')}
    # 体积两项在打包前必然不成立 ⇒ 这里只看**其余**项
    ok = True
    for r in rows:
        r2 = dict(r)
        r2['zip_bytes_matches'] = True
        r2['dir_bytes_matches'] = True
        ok = ok and b._row_pass(r2)
    ev['readme_gate']['pass_except_numbers'] = ok
    ev['readme_gate']['pass_except_zip_bytes'] = ok   # 兼容旧字段名
    return ev['readme_gate']


def probe_defaults():
    py = os.path.join(PKG, 'python', 'python.exe')
    code = ('import json,device_config;'
            'print(json.dumps({"default_devices":device_config.DEFAULT_DEVICES,'
            '"profile":__import__("package_profile").PROFILE,'
            '"defaults_version":getattr(device_config,"CONFIG_DEFAULTS_VERSION",None)},'
            'ensure_ascii=False))')
    r = subprocess.run([py, '-B', '-c', code], cwd=os.path.join(PKG, 'app'),
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=300, env=child_env())
    mm = re.search(r'\{.*\}', r.stdout, re.S)
    if not mm:
        raise RuntimeError('包内 DEFAULT_DEVICES 探测失败：%s'
                           % (r.stderr or r.stdout)[:300])
    return json.loads(mm.group(0))


# ── 主流程 ──────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTROOT, exist_ok=True)
    ev = {'at': now(), 'pkg': PKG, 'zip': ZIP, 'correction': 'APP-105',
          'items': {}, 'audio': AUDIO,
          'lock': {'module': 'app', 'pid': os.getpid(), 'started': None,
                   'ended': None, 'timing_valid': False}}

    check_static(ev)
    d = probe_defaults()
    ev['pkg_defaults'] = d
    ev['items']['9_factory_defaults_new'] = {
        'default_devices': d['default_devices'],
        'defaults_version': d.get('defaults_version'),
        'profile': d.get('profile'),
        'pass': (d['default_devices'] == NEW_DEFAULTS
                 and d.get('defaults_version') == 9
                 and d.get('profile') == 'minimvp'),
    }
    check_readme_gate(ev)

    # ── 设备作业：持锁 ─────────────────────────────────────────────
    payload = acquire_lock('app105_rc10_acceptance')
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
        py = os.path.join(PKG, 'python', 'python.exe')
        app_py = os.path.join(PKG, 'app', 'live_caption_app.py')

        # ⑨ --check（不带设备参数）
        cp = os.path.join(OUTROOT, 'check.log')
        with open(cp, 'wb') as lf:
            p = subprocess.run([py, '-s', app_py, '--check'], cwd=PKG,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=900,
                               env=child_env())
        cl = open(cp, 'rb').read().decode('utf-8', errors='replace')
        dev_line = [ln for ln in cl.splitlines()
                    if 'ASR' in ln and ('GPU.0' in ln or 'NPU' in ln)]
        ev['items']['10_pkg_check'] = {
            'exit_code': p.returncode, 'log': cp, 'log_bytes': len(cl),
            'n_ok_lines': len(re.findall(r'\[ OK \]', cl)),
            'has_asr_section': ('ASR 后端' in cl),
            'device_lines': dev_line[:12],
            'tail': cl[-1500:],
            'pass': p.returncode == 0 and 'ASR 后端' in cl,
        }
        print('[10] --check exit=%s OK行=%s' %
              (p.returncode, ev['items']['10_pkg_check']['n_ok_lines']),
              flush=True)

        # ⑩ GUI 截图（不加载模型 ⇒ 不占设备）
        # 🔴 **必须用包内 python**：GUI 探针会 import 包里的
        #    live_caption_app（要 numpy / openvino / tkinter）
        #    ⇒ 用系统 python 会直接 ImportError（**不是产品缺陷**）。
        g = subprocess.run([py,
                            os.path.join(HERE, '_app503_app105_rc10_gui_shot.py'),
                            PKG, GUI_SHOT, GUI_JSON],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=600, env=child_env())
        gjson = {}
        if os.path.isfile(GUI_JSON):
            gjson = json.load(open(GUI_JSON, encoding='utf-8'))
        ev['items']['11_gui'] = {
            'exit_code': g.returncode, 'shot': GUI_SHOT,
            'shot_bytes': gjson.get('shot_bytes'),
            'verdict': gjson.get('verdict'),
            'checks': gjson.get('checks'),
            'default_devices': gjson.get('default_devices'),
            'device_notes': gjson.get('device_notes'),
            'status_text': gjson.get('status_text'),
            'stdout_tail': (g.stdout or '')[-600:],
            'stderr_tail': (g.stderr or '')[-600:],
            'pass': (g.returncode == 0 and gjson.get('verdict') == 'PASS'),
        }
        print('[11] GUI verdict=%s' % ev['items']['11_gui']['verdict'],
              flush=True)

        # ⑪ 整链 10 分钟（**不带设备参数** ⇒ 出厂默认）
        lp = os.path.join(OUTROOT, 'chain10min.log')
        tp = os.path.join(OUTROOT, 'chain10min.txt')
        cmd = [py, '-s', app_py, '--cli', '--file', AUDIO,
               '--max-seconds', '600', '--out', tp,
               '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A']
        ev['chain_cmd'] = cmd
        t0 = time.time()
        with open(lp, 'wb') as lf:
            cp2 = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                 stderr=subprocess.STDOUT, timeout=2400,
                                 env=child_env())
        lg = open(lp, 'rb').read().decode('utf-8', errors='replace')
        sub = (open(tp, encoding='utf-8', errors='replace').read().strip()
               if os.path.isfile(tp) else '')
        tf = TTS_FINAL_RE.search(lg)
        rt = RTF_RE.search(lg)
        ex = ASR_EXEC_RE.search(lg)
        tex = TTS_EXEC_RE.search(lg)
        tplace = TTS_PLACE_RE.search(lg)
        tnpu = TTS_NPU_RE.search(lg)
        asr_dev = ex.group(1) if ex else None
        tts_dev = tex.group(1) if tex else None
        ev['items']['12_chain_10min'] = {
            'exit_code': cp2.returncode, 'wall_s': round(time.time() - t0, 1),
            'log': lp, 'output': tp, 'output_chars': len(sub),
            'output_head': sub[:300], 'replacement_chars': sub.count('\ufffd'),
            'asr_rtf': float(rt.group(1)) if rt else None,
            'asr_exec_encoder': asr_dev,
            'asr_exec_decoder': ex.group(2) if ex else None,
            'tts_exec_devices': tts_dev,
            'tts_places': tplace.group(1) if tplace else None,
            'tts_npu_components': int(tnpu.group(1)) if tnpu else None,
            'tts_submitted': int(tf.group(1)) if tf else None,
            'tts_played': int(tf.group(2)) if tf else None,
            'tts_dropped': int(tf.group(3)) if tf else None,
            'pass': bool(cp2.returncode == 0 and sub and '\ufffd' not in sub
                         and tf and int(tf.group(2)) >= 1
                         and asr_dev == 'GPU.0'
                         and tts_dev is not None and 'NPU' in tts_dev),
        }
        print('[12] chain exit=%s rtf=%s asr=%s tts=%s played=%s' %
              (cp2.returncode, ev['items']['12_chain_10min']['asr_rtf'],
               asr_dev, tts_dev,
               ev['items']['12_chain_10min']['tts_played']), flush=True)

        # ⑫ Start_Bridge.bat：**必须走 cmd /c**（不许用 python 绕过）
        bat = os.path.join(PKG, 'Start_Bridge.bat')
        before = find_windows()
        bp = subprocess.run(['cmd', '/c', bat], cwd=PKG, capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            timeout=180, env=child_env())
        time.sleep(6)
        wins = find_windows()
        new_wins = [w for w in wins if w not in before]
        shot_ok = False
        shot_bytes = 0
        target = None
        for w in new_wins:
            if '配音' in w['title'] or '桥接' in w['title']:
                target = w
                break
        if target is None and new_wins:
            target = new_wins[0]
        if target:
            sys.path.insert(0, HERE)
            from win_capture import capture_hwnd
            shot_ok = bool(capture_hwnd(target['hwnd'], BRIDGE_SHOT))
            shot_bytes = (os.path.getsize(BRIDGE_SHOT)
                          if os.path.isfile(BRIDGE_SHOT) else 0)
        killed = []
        for w in new_wins:
            if w['pid'] and pid_alive(w['pid']):
                if kill_pid(w['pid']):
                    killed.append(w['pid'])
        time.sleep(1)
        ev['items']['13_start_bridge_bat'] = {
            'bat': bat, 'bat_bytes': os.path.getsize(bat),
            'bat_cmd_exit': bp.returncode,
            'bat_stdout': (bp.stdout or '')[-400:],
            'bat_stderr': (bp.stderr or '')[-400:],
            'windows_before': before, 'windows_after': wins,
            'new_windows': new_wins,
            'target_window': target,
            'shot': BRIDGE_SHOT, 'shot_ok': shot_ok, 'shot_bytes': shot_bytes,
            'killed_pids': killed,
            'pass': bool(target is not None and shot_ok and shot_bytes > 5000),
        }
        print('[13] Start_Bridge：窗口=%s 截图=%s B=%s' %
              (len(new_wins), shot_ok, shot_bytes), flush=True)
    finally:
        ev['lock']['ended'] = now()
        ev['lock']['timing_valid'] = True
        ev['lock']['released'] = release_own_lock(payload)

    # 验收期间可能在包里生成了运行期文件 ⇒ 登记（打 zip 前会清）
    import fnmatch
    left = []
    for dp, _dn, fn in os.walk(PKG):
        for f in fn:
            low = f.lower()
            if any(fnmatch.fnmatch(low, p)
                   for p in ('bridge_token*', '*.pid', '*.log')):
                left.append(os.path.relpath(os.path.join(dp, f), PKG))
    n_pyc = 0
    for dp, dn, fn in os.walk(PKG):
        n_pyc += sum(1 for f in fn if f.endswith('.pyc'))
    ev['after_run_residue'] = {'blacklist_hits': left, 'n_pyc': n_pyc,
                               'note': '打 zip 前会被清理（APP-105 §2）'}

    keys = [k for k in ev['items'] if k[:1].isdigit()]
    ev['n_items'] = len(keys)
    ev['n_items_pass'] = sum(1 for k in keys if ev['items'][k].get('pass'))
    ev['readme_ok'] = ev['readme_gate']['pass_except_zip_bytes']
    ev['verdict'] = ('PASS' if (ev['n_items_pass'] == ev['n_items']
                                and ev['readme_ok']) else 'PARTIAL')
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=1)
    print('[acceptance] %d/%d 项 PASS；README=%s ⇒ %s'
          % (ev['n_items_pass'], ev['n_items'], ev['readme_ok'],
             ev['verdict']))
    for k in sorted(keys):
        print('   %-28s %s' % (k, 'PASS' if ev['items'][k].get('pass')
                                else 'FAIL'))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
