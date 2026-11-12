# -*- coding: utf-8 -*-
r"""_app505 — APP-105 rc10 **两项复跑**（GUI + Start_Bridge.bat）。

## 为什么要有这一轮

首轮（`_app501`）这两项**没跑成**，原因都在**验收脚本**（**不是产品缺陷**）：

  ① **GUI 探针用错了解释器**（系统 python ⇒ 缺 numpy/openvino ⇒ ImportError）；
     ⇒ 改用**包内 python** 重跑。
  ② **`cmd /c Start_Bridge.bat` 用 `subprocess.run(capture_output=True)`**
     ⇒ 启动器（pythonw）**继承了 stdout/stderr 管道** ⇒ 管道不关闭 ⇒
     `run()` 一直等到 180 s 超时 ⇒ 抛 `TimeoutExpired` ⇒ 后续窗口枚举/截图没跑。
     ⇒ 改用 **`Popen` + 输出落文件**（不建管道）⇒ `cmd` 立刻返回。

## 产物

  `results/app/app505_app105_rc10_gui_retry.json`
  `results/app/app505_app105_rc10_bridge_retry.json`
  `results/app/app505_app105_rc10_acceptance_merged.json`（把两项并回首轮报告）
"""
from __future__ import annotations

import ctypes
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc10')
OUTROOT = os.path.join(HERE, 'app501_app105_rc10_acceptance')
GUI_SHOT = os.path.join(OUTROOT, 'rc10_gui.png')
GUI_JSON = os.path.join(HERE, 'app505_app105_rc10_gui_retry.json')
BRIDGE_SHOT = os.path.join(OUTROOT, 'rc10_start_bridge.png')
BRIDGE_JSON = os.path.join(HERE, 'app505_app105_rc10_bridge_retry.json')
ACC_EV = os.path.join(HERE, 'app501_app105_rc10_acceptance.json')
MERGED = os.path.join(HERE, 'app505_app105_rc10_acceptance_merged.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                      ctypes.c_long)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def child_env():
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
    return env


def find_windows():
    out = []

    def cb(hwnd, _l):
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
            out.append({'hwnd': int(hwnd), 'title': title,
                        'pid': int(pid.value)})
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def pid_alive(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return code.value == 259


def kill_pid(pid):
    h = kernel32.OpenProcess(0x0001 | 0x0400, False, pid)
    if not h:
        return False
    ok = bool(kernel32.TerminateProcess(h, 1))
    kernel32.CloseHandle(h)
    return ok


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


def run_gui():
    py = os.path.join(PKG, 'python', 'python.exe')
    g = subprocess.run([py,
                        os.path.join(HERE, '_app503_app105_rc10_gui_shot.py'),
                        PKG, GUI_SHOT, GUI_JSON],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=900, env=child_env())
    out = {'at': now(), 'exit_code': g.returncode,
           'cmd': '包内 python %s <pkg> <png> <json>' %
                  os.path.basename('_app503_app105_rc10_gui_shot.py'),
           'stdout': (g.stdout or '')[-2000:], 'stderr': (g.stderr or '')[-2000:]}
    if os.path.isfile(GUI_JSON):
        gj = json.load(open(GUI_JSON, encoding='utf-8'))
        out['verdict'] = gj.get('verdict')
        out['checks'] = gj.get('checks')
        out['default_devices'] = gj.get('default_devices')
        out['device_notes'] = gj.get('device_notes')
        out['status_text'] = gj.get('status_text')
        out['shot'] = GUI_SHOT
        out['shot_bytes'] = gj.get('shot_bytes')
        out['shot_not_blank'] = gj.get('shot_not_blank')
        out['real_device_notes'] = gj.get('real_device_notes')
        out['stale_config_detected'] = gj.get('stale_config_detected')
    out['pass'] = (out.get('verdict') == 'PASS')
    json.dump(out, open(GUI_JSON, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=1)
    return out


def run_bridge():
    """`cmd /c <包目录>\Start_Bridge.bat`（**不用 python 绕过**）。

    🔴 **不用 `capture_output=True`**：启动器（pythonw）会**继承管道**
       ⇒ 管道不关闭 ⇒ `run()` 会等到超时。⇒ 输出**落文件**。
    """
    bat = os.path.join(PKG, 'Start_Bridge.bat')
    outp = os.path.join(OUTROOT, 'start_bridge_stdout.log')
    errp = os.path.join(OUTROOT, 'start_bridge_stderr.log')
    before = find_windows()
    t0 = time.time()
    with open(outp, 'wb') as fo, open(errp, 'wb') as fe:
        p = subprocess.Popen(['cmd', '/c', bat], cwd=PKG, stdout=fo,
                             stderr=fe, stdin=subprocess.DEVNULL,
                             env=child_env())
        rc = p.wait(timeout=120)
    cmd_return_s = round(time.time() - t0, 2)
    # 等窗口出现（最多 60 s）
    wins = []
    deadline = time.time() + 60
    while time.time() < deadline:
        wins = find_windows()
        new = [w for w in wins if w not in before]
        if new:
            break
        time.sleep(2)
    new_wins = [w for w in wins if w not in before]
    target = None
    for w in new_wins:
        if '配音' in w['title'] or '桥接' in w['title']:
            target = w
            break
    if target is None and new_wins:
        target = new_wins[0]
    shot_ok = False
    shot_bytes = 0
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
    time.sleep(1.5)
    still = [w['pid'] for w in new_wins if pid_alive(w['pid'])]
    out = {'at': now(), 'bat': bat, 'bat_bytes': os.path.getsize(bat),
           'cmd': 'cmd /c <pkg>\\Start_Bridge.bat', 'cmd_returncode': rc,
           'cmd_return_s': cmd_return_s,
           'stdout_log': outp, 'stderr_log': errp,
           'stdout': open(outp, 'rb').read().decode('utf-8', errors='replace')[-600:],
           'stderr': open(errp, 'rb').read().decode('utf-8', errors='replace')[-600:],
           'windows_before': before, 'windows_after': wins,
           'new_windows': new_wins, 'target_window': target,
           'shot': BRIDGE_SHOT, 'shot_ok': shot_ok, 'shot_bytes': shot_bytes,
           'killed_pids': killed, 'still_alive': still}
    out['pass'] = bool(target is not None and shot_ok and shot_bytes > 5000
                       and not still)
    json.dump(out, open(BRIDGE_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return out


def merge():
    """把两项复跑结果**并回**首轮验收报告（首轮记录**原样保留**）。"""
    acc = json.load(open(ACC_EV, encoding='utf-8'))
    gui = json.load(open(GUI_JSON, encoding='utf-8'))
    br = json.load(open(BRIDGE_JSON, encoding='utf-8'))
    items = acc.setdefault('items', {})
    old_gui = items.get('11_gui')
    if old_gui is not None:
        old_gui['superseded_by'] = 'app505_app105_rc10_gui_retry.json'
        old_gui['superseded_reason'] = (
            '首轮 GUI 探针用了**系统 python**（缺 numpy/openvino ⇒ ImportError）'
            '⇒ **验收脚本问题，不是产品缺陷**；改用**包内 python** 重跑见复跑件')
    old_br = items.get('13_start_bridge_bat')
    if old_br is not None:
        old_br['superseded_by'] = 'app505_app105_rc10_bridge_retry.json'
        old_br['superseded_reason'] = (
            '首轮 `subprocess.run(capture_output=True)` ⇒ 启动器继承 stdout 管道 '
            '⇒ 管道不关闭 ⇒ run() 等到 180 s 超时 ⇒ 窗口枚举/截图没跑到；'
            '改用 `Popen` + 输出落文件后重跑见复跑件')
    items['11_gui_retry'] = {
        'verdict': gui.get('verdict'), 'checks': gui.get('checks'),
        'default_devices': gui.get('default_devices'),
        'device_notes': gui.get('device_notes'),
        'status_text': gui.get('status_text'),
        'shot': gui.get('shot'), 'shot_bytes': gui.get('shot_bytes'),
        'shot_not_blank': gui.get('shot_not_blank'),
        'real_device_notes': gui.get('real_device_notes'),
        'stale_config_detected': gui.get('stale_config_detected'),
        'evidence': os.path.basename(GUI_JSON),
        'pass': gui.get('pass')}
    items['13_start_bridge_bat_retry'] = {
        'cmd': br.get('cmd'), 'cmd_returncode': br.get('cmd_returncode'),
        'cmd_return_s': br.get('cmd_return_s'),
        'new_windows': br.get('new_windows'),
        'target_window': br.get('target_window'),
        'shot': br.get('shot'), 'shot_ok': br.get('shot_ok'),
        'shot_bytes': br.get('shot_bytes'),
        'killed_pids': br.get('killed_pids'), 'still_alive': br.get('still_alive'),
        'stdout': br.get('stdout'), 'stderr': br.get('stderr'),
        'evidence': os.path.basename(BRIDGE_JSON),
        'pass': br.get('pass')}
    keys = sorted(k for k in items if k[:1].isdigit())
    # 有效项 = 复跑件**取代**首轮件
    effective = {}
    for k in keys:
        eff = k + '_retry'
        effective[k] = eff in items and items[eff].get('pass') or \
            (eff not in items and items[k].get('pass'))
    acc['n_items'] = len(keys)
    acc['n_items_pass'] = sum(1 for k in keys if effective[k])
    acc['effective_items'] = effective
    acc['retry_note'] = (
        '首轮 %s 两项**未跑成**（验收脚本问题：**GUI 探针用错解释器**、'
        '**`cmd /c` 的 stdout 管道被启动器继承**）⇒ 复跑见 '
        '`app505_app105_rc10_gui_retry.json` / `app505_app105_rc10_bridge_retry.json`；'
        '首轮记录**原样保留**（`11_gui` / `13_start_bridge_bat` 标了 superseded_by）。'
        % ('11_gui' if '11_gui' in items else '')
    )
    acc['verdict'] = ('PASS' if (acc['n_items_pass'] == acc['n_items']
                                 and acc.get('readme_ok', True))
                       else 'PARTIAL')
    json.dump(acc, open(MERGED, 'w', encoding='utf-8'), ensure_ascii=False,
              indent=1)
    return acc


def main():
    os.makedirs(OUTROOT, exist_ok=True)
    payload = acquire_lock('app105_rc10_retry')
    if not payload:
        print('!! 机器锁在位 ⇒ 本轮不做设备作业')
        return 1
    try:
        g = run_gui()
        print('[GUI retry] verdict=%s checks=%s'
              % (g.get('verdict'), json.dumps(g.get('checks', {}),
                                              ensure_ascii=False)), flush=True)
        b = run_bridge()
        print('[Bridge retry] 窗口=%s 截图=%s B=%s killed=%s still=%s'
              % (len(b.get('new_windows') or []), b.get('shot_ok'),
                 b.get('shot_bytes'), b.get('killed_pids'),
                 b.get('still_alive')), flush=True)
    finally:
        release_own_lock(payload)
    acc = merge()
    print('[merged] %d/%d ⇒ %s（写入 %s）'
          % (acc['n_items_pass'], acc['n_items'], acc['verdict'],
             os.path.basename(MERGED)))
    for k in sorted(acc['effective_items']):
        print('   %-28s %s' % (k, 'PASS' if acc['effective_items'][k] else 'FAIL'))
    return 0 if acc['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
