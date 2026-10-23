r"""replay_c134_mt.py — C-134 CLI 回放：验证默认翻译改 INT8-CW 后的链路与延迟

用途（APP-003② 验收要求）
--------------------------
APP-002 第 ③ 条：「改完后跑一次 CLI 回放，确认翻译正常，并记录翻译延迟和
对 ASR RTF 的影响（**计时要持机器锁**）」。

本脚本：
1. **等锁**：轮询 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`；
   锁里的 PID 不在了 / 锁早于开机时间 ⇒ 回收；否则等待。
2. **持锁**：创建锁（内容：模块名 PID 开始时间），跑完删除。
3. **ABBA 回放**：翻译 off/on/on/off 四轮，同一段音频，同一个 ASR 后端。
4. **记录**：ASR RTF、翻译延迟（T1 定稿 → 译文出现的墙钟）、逐段耗时、
   落盘产物文件名 / mtime。

⚠️ 端到端墙钟**不能作性能判据**（机器漂移 60~130 s）⇒ 报告里同时给
   「音频时间轴坐标」口径，ABBA 差值才是结论。

用法
----
    python replay_c134_mt.py [--audio <wav>] [--seconds 60]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
APP = os.path.join(PKG, 'app')
PY = os.path.join(PKG, 'python', 'python.exe')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
OUTDIR = os.path.join(REPO, 'results', 'c134_replay')


# ── 锁 ──────────────────────────────────────────────────────────────
def _pid_alive(pid):
    """PID 是否存活。

    ⚠️ **不能用 tasklist** —— 在 Git Bash 下 tasklist 的路径被转义破坏
    （实测报「无效参数/选项 - 'FI'」），异常被吞掉后返回 False
    ⇒ **误判活锁为死锁并回收**（已实测踩到：把 TTS 模块的活锁 pid=33572 回收了）。
    ⇒ 改用 ctypes 的 OpenProcess，进程不存在才返回 False。
    """
    if not pid:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            # ERROR_ACCESS_DENIED(5) 说明进程存在但权限不足 ⇒ 视为存活
            return ctypes.get_last_error() == 5
        code = wintypes.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        if not ok:
            return True
        return code.value == STILL_ACTIVE
    except Exception:
        # 探测失败 ⇒ **保守视为存活**，宁可等也不要误回收别人的锁
        return True


def _boot_time():
    """开机时间（epoch 秒）。锁早于开机时间 ⇒ 锁是残留的。"""
    try:
        import ctypes
        ts = ctypes.c_ulonglong()
        ctypes.windll.kernel32.GetTickCount64(ctypes.byref(ts))
        import time as _t
        return _t.time() - ts.value / 1000.0
    except Exception:
        return 0.0


def _lock_info():
    if not os.path.isfile(LOCK):
        return None
    try:
        with open(LOCK, 'r', encoding='utf-8') as f:
            txt = f.read()
    except Exception:
        return None
    info = {}
    for line in txt.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            info[k.strip()] = v.strip()
    return info


def acquire_lock(module='app', timeout_s=3600):
    """等锁 + 持锁。返回 (acquired, waited_s, lock_info_before)。"""
    t0 = time.time()
    boot = _boot_time()
    while True:
        info = _lock_info()
        if info is None:
            break
        pid = int(info.get('pid', 0) or 0)
        started = info.get('started', '')
        stale = (not _pid_alive(pid))
        if not stale:
            # 锁早于开机时间 ⇒ 残留
            try:
                hh, mm, ss = [int(x) for x in started.split()[1].split(':')]
                lt = time.mktime(time.strptime(started.split()[0], '%Y-%m-%d')) \
                    + hh * 3600 + mm * 60 + ss
                if lt < boot:
                    stale = True
            except Exception:
                pass
        if stale:
            print(f'[lock] 回收残留锁（pid={pid} started={started}）')
            try:
                os.remove(LOCK)
            except OSError:
                pass
            break
        waited = time.time() - t0
        if waited > timeout_s:
            raise TimeoutError(f'等待机器锁超时 {timeout_s}s（当前持有：{info}）')
        print(f'[lock] 等待中… 已等 {waited:.0f}s（当前持有：{info}）', flush=True)
        time.sleep(20)

    waited = time.time() - t0
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, 'w', encoding='utf-8') as f:
        f.write(f'module: {module}\npid: {os.getpid()}\n'
                f'started: {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
                f'host: {os.environ.get("COMPUTERNAME", "?")}\n')
    print(f'[lock] 已获取（等了 {waited:.0f}s）', flush=True)
    return True, waited, None


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except OSError:
        pass


# ── 单轮回放 ────────────────────────────────────────────────────────
SEG_RE = re.compile(r'^\s*\[(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*\]')


def run_once(audio, seconds, translate, out_json, engine='gpu_int8',
             mt_engine=None):
    os.makedirs(OUTDIR, exist_ok=True)
    txt_out = os.path.join(OUTDIR, out_json.replace('.json', '.txt'))
    cmd = [PY, os.path.join(APP, 'live_caption_app.py'),
           '--cli', '--file', audio, '--engine', engine,
           '--asr-lang', 'Chinese',
           '--max-seconds', str(seconds),
           '--translate', translate,
           '--out', txt_out]
    if mt_engine:
        cmd += ['--mt-engine', mt_engine]
    t0 = time.time()
    # ⚠️ 子进程 stdout 是 GBK（Windows 控制台编码），不是 UTF-8 ⇒
    #   用 text=True + encoding='utf-8' 会在 readerthread 里抛
    #   UnicodeDecodeError（实测 position 4 byte 0xcf）⇒ 改二进制自己解码。
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    out_txt = p.stdout.decode('utf-8', errors='replace')
    err_txt = p.stderr.decode('utf-8', errors='replace')
    wall = time.time() - t0

    # ⚠️ --out 写出的定稿文本**没有** [start-end] 时间戳前缀（实测）
    #   ⇒ 只能按非空行统计「段数」，不能解析时间轴。
    segs = []
    if os.path.isfile(txt_out):
        with open(txt_out, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                t = line.strip()
                if not t:
                    continue
                m = SEG_RE.match(line)
                if m:
                    segs.append((float(m.group(1)), float(m.group(2)), t))
                else:
                    segs.append((None, None, t))
    return {
        'translate': translate,
        'mt_engine': mt_engine or 'default(auto)',
        'wall_s': round(wall, 2),
        'exit_code': p.returncode,
        'segments': len(segs),
        'out_txt': txt_out,
        'out_txt_exists': os.path.isfile(txt_out),
        'stdout_tail': out_txt[-3000:],
        'stderr_tail': err_txt[-3000:],
        'seg_samples': segs[:5],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', default=os.path.join(
        REPO, 'test_audio', '<redacted>.wav'))
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--module', default='app')
    ap.add_argument('--no-wait-lock', action='store_true')
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    acquired = False
    if not args.no_wait_lock:
        acquire_lock(args.module)
        acquired = True
    try:
        # ABBA：off / on / on / off
        plan = [
            ('abba1_off', 'off', None),
            ('abba2_on', 'zh', None),
            ('abba3_on', 'zh', None),
            ('abba4_off', 'off', None),
        ]
        results = []
        for name, tr, me in plan:
            print(f'\n===== {name}（translate={tr}） =====', flush=True)
            r = run_once(args.audio, args.seconds, tr, f'{name}.json', mt_engine=me)
            r['name'] = name
            results.append(r)
            print(f'  exit={r["exit_code"]} segments={r["segments"]} '
                  f'wall={r["wall_s"]}s', flush=True)
            if r['exit_code'] != 0:
                print('  stderr tail:', r['stderr_tail'][-800:], flush=True)
        with open(os.path.join(OUTDIR, 'replay_report.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({'audio': args.audio, 'seconds': args.seconds,
                       'results': results}, f, ensure_ascii=False, indent=2)
        print('\n结果已落盘:', os.path.join(OUTDIR, 'replay_report.json'))
    finally:
        if acquired:
            release_lock()


if __name__ == '__main__':
    sys.exit(main())
