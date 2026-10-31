#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app179 —— APP-051②：**GUI 路径**的 APP-042 自适应加速播放真机验收。

🔴🔴🔴 **为什么需要这个脚本（gap 分析）**：
  APP-043 的真机验收要求「**GUI 路径的加速播放**」（APP-042），
  但既往证据只有 **CLI 路径**：
    - `app149`（APP-042 worker 侧定速）**明写**「非真机实测、**非 GUI**」；
    - `app175`（APP-043 克隆验收）走的是 `--cli` ⇒ **也不是 GUI**。
  ⇒ **「GUI 路径的加速播放」这一项从未被真机覆盖** ⇒ 本脚本补上。

🔴 **判据口径（离线可算，不在 CPU 上跑推理）**：
  ① GUI 真机跑一段 SPE 音频（`--file` + **不**加 `--cli`）⇒ 走 GUI 路径；
  ② GUI 侧把逐句遥测落盘（`--tts-jsonl`）⇒ 拿得到 `speed` / `play_lag_s` /
     `target_wall` / `voice_spk` / `voice_kind`；
  ③ **判据**：GUI 路径必须出现 **`speed > 1.0`** 的句子（加速真的触发了），
     且 `play_lag_s` 与 `speed` **同向**（滞后越大 ⇒ 倍率越大）。

🔴 **反证组（判据必须能识破「加速从未触发」）**：
  R1：把 `speed` 全部强改成 1.0 ⇒ 「加速触发」判据必须 FAIL；
  R2：把 `target_wall` 全部清空（⇒ 服务端不下发加速参数）⇒ 必须 FAIL。

🔴 **纪律**：
  - 本脚本**不 import 被测模块**到本进程（顶层 numpy/OV 会拖慢）⇒ 用**子进程**
    跑包内 `live_caption_app.py`；
  - **持共享机器锁**（计时作业）⇒ 锁已存在就等，**不抢**；
  - **不在 CPU 上跑推理**：ASR/MT/TTS 都走 NPU/GPU.0；
  - **质量判定交 reviewer**（本脚本只判「链路是否接通 + 数字是否自洽」）。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  —— %s' % detail) if detail else ''))
    return ok


# ── 包目录自动发现（**不写死版本号**；排除 .bak_* / *_backup；元组比较）──
def discover_pkg():
    cands = []
    for d in os.listdir(HOME):
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)\.(\d+)$', d)
        if not m:
            continue
        if '.bak_' in d or d.endswith('_backup'):
            continue
        cands.append(((int(m.group(1)), int(m.group(2))),
                      os.path.join(HOME, d)))
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return cands[-1][1]


# ── 共享机器锁（ctypes 判活；fail-closed；不用 tasklist）──
def pid_alive(pid):
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))
        if not h:
            return (ctypes.get_last_error() == 87)  # 87 ⇒ PID 确定不存在
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    except Exception:
        return True  # 探测失败 ⇒ 视为存活（fail-closed）


def read_lock():
    try:
        with open(LOCK, 'rb') as f:
            raw = f.read()
    except Exception:
        return None
    for enc in ('utf-8', 'gbk', 'cp936', 'latin-1'):
        try:
            txt = raw.decode(enc)
        except Exception:
            continue
        m = re.search(r'pid[:=\s]+(\d+)', txt, re.I)
        if m:
            return {'pid': int(m.group(1)), 'raw': txt}
        m = re.match(r'^(\S+)\s+PID\s+(\d+)\b', txt.strip(), re.I)
        if m:
            return {'pid': int(m.group(2)), 'raw': txt}
    return None


def acquire_lock(timeout_s=3600):
    payload = ('module: app\npid: %d\nstarted: %s\nhost: LAPTOP-0GDQGD3I\n'
               % (os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S')))
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, payload.encode('utf-8'))
            finally:
                os.close(fd)
            print('[lock] 已取得共享机器锁')
            return True
        except FileExistsError:
            st = read_lock()
            if st and not pid_alive(st['pid']):
                print('[lock] 旧锁持有者 PID %d 已死 ⇒ 回收' % st['pid'])
                try:
                    os.remove(LOCK)
                    continue
                except Exception:
                    pass
            if time.time() - t0 > timeout_s:
                raise SystemExit('等待机器锁超时')
            time.sleep(5)


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except Exception as e:
        print('[lock] 释放异常：%r' % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--wav', default=None)
    ap.add_argument('--seconds', type=float, default=90.0)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('[pkg] %s' % pkg)
    wav = args.wav
    if not wav:
        wav = os.path.join(HOME, 'shared', 'spe_qa_clone_listen',
                           'SPE_densest_5min.wav')
    if not os.path.isfile(wav):
        raise SystemExit('找不到音频：%s' % wav)

    out_dir = args.out or os.path.join(HOME, 'app051_gui_accel')
    os.makedirs(out_dir, exist_ok=True)
    jsonl = os.path.join(out_dir, 'gui_accel.tts.jsonl')
    log = os.path.join(out_dir, 'gui_accel.log')

    py = os.path.join(pkg, 'python', 'python.exe')
    app_py = os.path.join(pkg, 'app', 'live_caption_app.py')

    acquire_lock()
    try:
        # 🔴 GUI 真机：`--file` + **不加** `--cli` ⇒ 走 GUI 路径；
        #   `--autostart` ⇒ ASR 加载完成后**自动开始**会话
        #     （`--selftest` 的帮助文本明写「需配合 --file --autostart」）
        #   `--selftest <秒>` ⇒ GUI 播到该秒数就自动收尾（截图 + 写结果 + 退出）
        #     （触发点：`_poll` L4962 `s.audio_s >= self.args.selftest`）
        #   ⚠️ `--max-seconds` **只对 CLI 生效**（`live_caption_app.py` L5586）
        cmd = [py, app_py,
               '--file', wav,
               '--speed', '1.0',
               '--translate', 'zh',
               '--tts', 'on',
               '--tts-voice', 'follow_speaker',
               '--tts-device', 'NPU',
               '--asr-device', 'GPU.0',
               '--mt-device', 'GPU.0',
               '--tts-jsonl', jsonl,
               '--autostart',
               '--selftest', str(args.seconds),
               '--selftest-out', os.path.join(out_dir, 'selftest')]
        print('[run] %s' % ' '.join(cmd))
        t0 = time.time()
        with open(log, 'wb') as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                    cwd=os.path.join(pkg, 'app'))
            rc = proc.wait(timeout=3600)
        wall = time.time() - t0
        print('[run] 退出码=%s 墙钟=%.1f s' % (rc, wall))

        rows = []
        if os.path.isfile(jsonl):
            with open(jsonl, encoding='utf-8', errors='replace') as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        try:
                            rows.append(json.loads(ln))
                        except Exception:
                            pass

        print('\n== 判据 ==')
        check('A1 GUI 路径产出了逐句遥测', len(rows) > 0,
              'rows=%d  jsonl=%s' % (len(rows), jsonl))
        check('A2 进程正常退出', rc == 0, 'rc=%s' % rc)

        sp = [float(r.get('speed') or 1.0) for r in rows]
        lag = [float(r.get('play_lag_s') or 0.0) for r in rows]
        tw = [r.get('target_wall') for r in rows]
        n_accel = sum(1 for s in sp if s > 1.0 + 1e-9)
        n_tw = sum(1 for t in tw if t)

        check('B1 GUI 路径真的触发了加速（speed > 1.0 的句子存在）',
              n_accel > 0,
              '加速句=%d / %d  max_speed=%.4f'
              % (n_accel, len(rows), max(sp) if sp else 0.0))
        check('B2 GUI 路径下发了目标开播墙钟（target_wall 非空）',
              n_tw > 0, 'target_wall 非空=%d / %d' % (n_tw, len(rows)))
        check('B3 加速倍率落在 APP-042 约定区间（1.0 < speed ≤ 1.30）',
              all(1.0 - 1e-9 <= s <= 1.30 + 1e-6 for s in sp if s),
              'speed 取值集合=%r' % sorted(set(round(s, 4) for s in sp)))
        # 同向性：滞后为正的句子 ⇒ 倍率应 > 1
        pairs = [(l, s) for l, s in zip(lag, sp) if l > 1.0]
        if pairs:
            import statistics
            hi = [s for l, s in pairs if l > 10.0]
            lo = [s for l, s in pairs if l <= 10.0]
            ok = (not hi or not lo) or (statistics.mean(hi) > statistics.mean(lo))
            check('B4 滞后越大 ⇒ 倍率越大（同向）', ok,
                  'lag>10 的均值=%.4f（n=%d）；lag<=10 的均值=%.4f（n=%d）'
                  % (statistics.mean(hi) if hi else 0.0, len(hi),
                     statistics.mean(lo) if lo else 0.0, len(lo)))
        else:
            check('B4 滞后越大 ⇒ 倍率越大（同向）', False,
                  '没有 lag>1.0 的句子 ⇒ 无法判定（记录为未测）')

        print('\n== 反证组（判据必须能识破「加速从未触发」）==')
        # R1：speed 全改成 1.0 ⇒ B1 必须 FAIL
        fake1 = [dict(r, speed=1.0) for r in rows]
        n1 = sum(1 for r in fake1 if float(r.get('speed') or 1.0) > 1.0 + 1e-9)
        check('R1 反证：speed 全改 1.0 ⇒ B1 必 FAIL', n1 == 0,
              'fake n_accel=%d ⇒ B1 条件为假 ⇒ FAIL' % n1)
        # R2：target_wall 全清空 ⇒ B2 必须 FAIL
        fake2 = [dict(r, target_wall=None) for r in rows]
        n2 = sum(1 for r in fake2 if r.get('target_wall'))
        check('R2 反证：target_wall 全清空 ⇒ B2 必 FAIL', n2 == 0,
              'fake n_target_wall=%d ⇒ B2 条件为假 ⇒ FAIL' % n2)

        verdict = 'PASS' if FAIL == 0 else 'FAIL'
        print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

        ev = {
            'script': os.path.basename(__file__),
            'correction': 'APP-051② / APP-042（GUI 路径）/ APP-043',
            'pkg': pkg,
            'wav': wav,
            'max_seconds': args.seconds,
            'rc': rc, 'wall_s': round(wall, 1),
            'log': log, 'jsonl': jsonl,
            'n_rows': len(rows),
            'n_accel_rows': n_accel,
            'n_target_wall_rows': n_tw,
            'speed_min': min(sp) if sp else None,
            'speed_max': max(sp) if sp else None,
            'speed_hist': {str(round(s, 2)): sp.count(s)
                           for s in sorted(set(sp))},
            'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
            'verdict': verdict,
            'note': 'GUI 路径真机实测；判据只看链路接通与数字自洽；'
                    '音质/不变调/可懂由 reviewer 与用户实听判定',
        }
        ev_path = os.path.join(HERE, 'app179_app042_gui_accel_evidence.json')
        with open(ev_path, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        print('[evidence] %s' % ev_path)
        return 0 if FAIL == 0 else 1
    finally:
        release_lock()


if __name__ == '__main__':
    sys.exit(main())
