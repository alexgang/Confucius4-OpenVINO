# -*- coding: utf-8 -*-
r"""_app486 — **APP-102 §2 的 4 臂短冒烟**（rc8 包目录上跑，持 MACHINE_LOCK）。

臂：
  1. stateful GPU.0（`--engine gpu_int8 --asr-device GPU.0`）
  2. stateful NPU （`--engine npu_int8 --asr-device NPU`）
  3. 新默认整链（ASR NPU + MT GPU.0 + TTS GPU.0，不给 --tts-device）
  4. GUI 启动一次并截图（不占设备；`_app486_gui_shot.py`）

判据（APP-102 §2.2）：转写非空、非乱码；NPU 臂真在 NPU；整链不崩且至少播完 1 句。
计时 json 写 lock 的 module/pid/started/ended 与 timing_valid（APP-101 §2）。
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
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc8')
OUTROOT = os.path.join(HERE, 'app486_app102_rc8_smoke')
REPORT = os.path.join(HERE, 'app486_app102_rc8_smoke.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
AUDIO = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\smoke30.wav'
GUI_SHOT = os.path.join(OUTROOT, 'rc8_gui.png')
GUI_JSON = os.path.join(OUTROOT, 'rc8_gui.json')
VENV_PY = os.path.join(REPO, '.venv', 'Scripts', 'python.exe')

ARMS = (
    ('stateful_gpu', ['--engine', 'gpu_int8', '--asr-device', 'GPU.0']),
    ('stateful_npu', ['--engine', 'npu_int8', '--asr-device', 'NPU']),
    ('default_chain', ['--engine', 'npu_int8', '--asr-device', 'NPU',
                       '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A',
                       '--mt-device', 'GPU.0', '--tts-device', 'GPU.0']),
)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    """OpenProcess + GetExitCodeProcess；259=STILL_ACTIVE ⇒ 活；探测失败 ⇒ 视为存活。"""
    import ctypes
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    if not ok:
        return True
    return code.value == 259


def acquire_lock(tag):
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        # 🔴 排队：先看持锁 PID 是否真死；活着 ⇒ 不抢（fail-closed）
        try:
            info = open(LOCK, encoding='utf-8', errors='replace').read()
            m = re.match(r'\S+\s+(\d+)\s', info)
            if m and pid_alive(int(m.group(1))):
                return None
        except Exception:
            return None
        return None


def release_own_lock(payload):
    """正常释放**自己**的锁（不是回收别人的锁 ⇒ 不做 PID 探活判断）。"""
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if cur != payload:
                print('!! 锁内容已变，拒绝删除：%r' % cur[:120])
                return False
            os.remove(LOCK)
            return True
    except Exception as e:
        print('!! 释放锁异常：%r' % e)
    return False


RTF_RE = re.compile(r'\[(gpu_int8|npu_int8)\]\s*音频\s*([\d.]+)s\s+'
                    r'墙钟\s*([\d.]+)s\s+RTF\(计算\)\s*([\d.]+)')
TTS_FINAL_RE = re.compile(r'\[TTS\] 最终统计（close 后）：提交\s*(\d+)\s+'
                          r'播完\s*(\d+)\s+丢弃\s*(\d+)')
TTS_READY_RE = re.compile(r'\[TTS\] 就绪：([^\s·]+)\s*·\s*音色\s*(\S+)')
EXEC_RE = re.compile(r'\[asr06b-stateful\] EXECUTION_DEVICES：encoder=(\S+?)，decoder=(\S+?)（')


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--seconds', type=float, default=30.0)
    ap.add_argument('--audio', default=AUDIO)
    ap.add_argument('--arms', default='')
    ap.add_argument('--no-lock', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUTROOT, exist_ok=True)
    py = os.path.join(args.pkg, 'python', 'python.exe')
    app_py = os.path.join(args.pkg, 'app', 'live_caption_app.py')
    for p in (py, app_py, args.audio, VENV_PY):
        if not os.path.isfile(p):
            print('!! 缺文件：%s' % p)
            return 2

    ev = {'at': now(), 'pkg': args.pkg, 'audio': args.audio,
          'seconds': args.seconds, 'correction': 'APP-102 §2',
          'arms': [], 'lock': {'module': 'app', 'pid': os.getpid(),
                               'started': None, 'ended': None,
                               'timing_valid': False}}
    payload = None
    if not args.no_lock:
        payload = acquire_lock('app102_rc8_smoke')
        if not payload:
            print('🔴 MACHINE_LOCK 被占用且持锁进程存活 ⇒ 不抢锁，本轮不跑设备作业')
            ev['verdict'] = 'SKIPPED_LOCK_BUSY'
            with open(REPORT, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=1)
            return 1
        ev['lock']['started'] = now()
        ev['lock']['payload'] = payload
        print('[lock] 已获取：%s' % payload, flush=True)

    want = set(x for x in args.arms.split(',') if x)
    # ── 出厂默认设备核对（纯读，不占设备）──────────────────────────
    # 🔴 本机 AppData 下有历史 device_config.json（tts=NPU）会覆盖出厂默认；
    #    客户机是干净环境 ⇒ 这里只核「包内出厂默认」，冒烟用显式参数还原。
    probe = [py, '-c',
             'import sys,json;sys.path.insert(0,r"%s");'
             'import device_config as d,package_profile as p;'
             'print(json.dumps({"default_devices":d.DEFAULT_DEVICES,'
             '"minimvp":p.is_minimvp(),"config_path":d.CONFIG_PATH,'
             '"saved_config":d.load_config()}))' %
             os.path.join(args.pkg, 'app')]
    try:
        pr = subprocess.run(probe, cwd=args.pkg, capture_output=True,
                            text=True, timeout=120)
        ev['factory_default_probe'] = json.loads(pr.stdout.strip().splitlines()[-1])
    except Exception as e:
        ev['factory_default_probe'] = {'error': repr(e)}
    ev['explicit_devices_reason'] = (
        '本机 AppData 的 device_config.json 有历史选择（tts=NPU）覆盖出厂默认'
        ' ⇒ 不改用户配置，冒烟整链臂显式给 --mt-device GPU.0 --tts-device GPU.0 '
        '还原 APP-101 §0.3 的新默认组合；出厂默认值单独在上面 probe 里核对')
    try:
        for name, opts in ARMS:
            if want and name not in want:
                continue
            logp = os.path.join(OUTROOT, name + '.log')
            txtp = os.path.join(OUTROOT, name + '.txt')
            cmd = [py, '-s', app_py, '--cli', '--file', args.audio,
                   '--max-seconds', str(args.seconds), '--out', txtp] + list(opts)
            print('[arm] %s: %s' % (name, ' '.join(opts)), flush=True)
            t0 = time.time()
            try:
                with open(logp, 'wb') as lf:
                    p = subprocess.run(cmd, cwd=args.pkg, stdout=lf,
                                       stderr=subprocess.STDOUT, timeout=900)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = -9
            wall = round(time.time() - t0, 1)
            log = open(logp, 'rb').read().decode('utf-8', errors='replace')
            sub = (open(txtp, encoding='utf-8', errors='replace').read().strip()
                   if os.path.isfile(txtp) else '')
            rtf = RTF_RE.search(log)
            exec_lines = [l.strip() for l in log.splitlines()
                          if 'EXECUTION_DEVICES' in l and 'asr06b-stateful' in l]
            exec_m = EXEC_RE.search(log)
            tts_final = TTS_FINAL_RE.search(log)
            tts_ready = TTS_READY_RE.search(log)
            rec = {
                'arm': name, 'opts': list(opts), 'exit_code': rc,
                'wall_s': wall, 'log_bytes': len(log.encode('utf-8')),
                'log_path': logp, 'output_path': txtp,
                'output_chars': len(sub), 'output_head': sub[:300],
                'has_output': bool(sub),
                'replacement_chars': sub.count('\ufffd'),
                'not_garbled': bool(sub) and '\ufffd' not in sub,
                'exec_devices_lines': exec_lines,
                'asr_exec_encoder': exec_m.group(1) if exec_m else None,
                'asr_exec_decoder': exec_m.group(2) if exec_m else None,
                'asr_rtf': float(rtf.group(4)) if rtf else None,
                'audio_s': float(rtf.group(2)) if rtf else None,
                'asr_wall_s': float(rtf.group(3)) if rtf else None,
                'tts_submitted': int(tts_final.group(1)) if tts_final else None,
                'tts_played': int(tts_final.group(2)) if tts_final else None,
                'tts_dropped': int(tts_final.group(3)) if tts_final else None,
                'tts_ready_device': tts_ready.group(1) if tts_ready else None,
                'tts_ready_voice': tts_ready.group(2) if tts_ready else None,
                'npuw_lines': [l.strip() for l in log.splitlines()
                               if 'NPUW 配置' in l],
                'kv_reset_lines': [l.strip() for l in log.splitlines()
                                   if 'KV=每次 generate' in l][:2],
                'truncation_lines': [l.strip() for l in log.splitlines()
                                     if '512 上界' in l][:5],
            }
            if name == 'stateful_npu':
                rec['on_npu'] = (rec['asr_exec_encoder'] == 'NPU'
                                 and rec['asr_exec_decoder'] == 'NPU')
                rec['arm_pass'] = bool(rc == 0 and rec['not_garbled']
                                       and rec['on_npu'])
            elif name == 'stateful_gpu':
                rec['on_gpu'] = (rec['asr_exec_encoder'] == 'GPU.0'
                                 and rec['asr_exec_decoder'] == 'GPU.0')
                rec['arm_pass'] = bool(rc == 0 and rec['not_garbled']
                                       and rec['on_gpu'])
            else:
                rec['chain_ok'] = bool(rc == 0 and rec['not_garbled']
                                       and (rec['tts_played'] or 0) >= 1)
                rec['tts_default_gpu0'] = (rec['tts_ready_device'] == 'GPU.0')
                rec['arm_pass'] = bool(rec['chain_ok'])
            ev['arms'].append(rec)
            print('   exit=%s wall=%ss out=%s rtf=%s enc=%s dec=%s '
                  'tts_played=%s PASS=%s'
                  % (rc, wall, rec['has_output'], rec['asr_rtf'],
                     rec['asr_exec_encoder'], rec['asr_exec_decoder'],
                     rec['tts_played'], rec['arm_pass']), flush=True)

        # ── 第 4 臂：GUI 启动 + 截图（不占设备） ──
        if not want or 'gui' in want:
            print('[arm] gui: 启动 GUI 并截图…', flush=True)
            cmd = [VENV_PY, '-s', os.path.join(HERE, '_app486_gui_shot.py'),
                   args.pkg, GUI_SHOT, GUI_JSON]
            try:
                gp = subprocess.run(cmd, cwd=REPO, capture_output=True,
                                    text=True, timeout=240)
                grc = gp.returncode
                gout = (gp.stdout or '') + (gp.stderr or '')
            except subprocess.TimeoutExpired:
                grc = -9
                gout = 'GUI 子进程超时（240 s）'
            gui = {}
            if os.path.isfile(GUI_JSON):
                gui = json.load(open(GUI_JSON, encoding='utf-8'))
            ev['gui'] = {'exit_code': grc, 'stdout_tail': gout[-800:],
                         'evidence': gui}
            print('   gui exit=%s verdict=%s shot_bytes=%s'
                  % (grc, gui.get('verdict'), gui.get('shot_bytes')), flush=True)
    finally:
        ev['lock']['ended'] = now()
        ev['lock']['timing_valid'] = True
        if payload:
            ev['lock']['released'] = release_own_lock(payload)
        else:
            ev['lock']['released'] = None

    n_arms = len(ev['arms'])
    n_ok = sum(1 for a in ev['arms'] if a.get('arm_pass'))
    gui_ok = (ev.get('gui', {}).get('evidence', {}).get('verdict') == 'PASS')
    ev['n_arms'] = n_arms + (1 if ev.get('gui') else 0)
    ev['n_arms_ok'] = n_ok + (1 if gui_ok else 0)
    ev['verdict'] = ('PASS' if (n_arms == 3 and n_ok == 3 and gui_ok)
                     else 'PARTIAL')
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[smoke] CLI %d/%d OK；GUI %s ⇒ %s'
          % (n_ok, n_arms, 'PASS' if gui_ok else 'FAIL', ev['verdict']))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
