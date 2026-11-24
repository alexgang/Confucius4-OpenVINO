#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 §3.2：**v2.6 整链**（保留背景音 开 / 关 各一轮，每轮单独起桥接）。

## reviewer 的验收口径（APP-129 §3.2）

> 10 分钟固定片段整链（出厂默认：ASR/MT GPU.0、TTS NPU，EXT 默认设备；分离 GPU.0），
> 保留背景音 **开 / 关各一轮，每轮单独起桥接**：
> dubs、丢句（须 0）、语速 max、dub_late max/p90/n_late、
> bg_blocks / bg_late_blocks / fallback_to_orig_s、synth_rtf、
> 配音积压峰值与收尾积压；
> **桥接进程峰值内存开关差值**（reviewer 实测约 +1.9 GB，作对照）。

## 本脚本与 reviewer 的 `run_bgkeep_v9_spk.ps1` 的差别（都是**包内**跑）

| | reviewer v9（e2e9） | 本脚本（e2e_v26） |
|---|---|---|
| EXT 代码 | **源码仓** `live_dub_ext/`（工作树） | **包内** `<v2.6>/ext/bridge`（commit 3573b2d） |
| App 运行时 | `EXT_APP_ROOT=<v2.5>` | `EXT_APP_ROOT=<v2.6>` |
| python | v2.5 包内 python | v2.6 包内 python |
| 媒体 | 30 s 片段 | **10 分钟固定片段**（bili_420.wav 拼接） |
| 臂 | 3 条 clone 臂 | **bgkeep off / on 各一轮** |

## 纪律

- **持共享机器锁**（整链占设备 ⇒ 不能与别的模块抢）；
- 桥接 **cwd = 臂目录**（⇒ `bridge_token.txt` 落在**包外**，包内不留污染）；
- `bgkeep_e2e.py` 用 **commit 3573b2d** 的版本（源码仓工作树已被 reviewer 改成 v0.4.20）；
- 每臂**单独起桥接**（reviewer 明文）；
- 桥接进程峰值内存用 `GetProcessMemoryInfo` 的 `PeakWorkingSetSize`（cmm）。
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.dirname(REPO)
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import _app116_build_v25 as B  # noqa: E402  （锁 / robocopy helper）

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
EXT_REPO = os.path.join(HOME, 'live_dub_ext')
CLIPS = os.path.join(HOME, 'shared', 'bgkeep', 'clips')
OUT_ROOT = os.path.join(HOME, 'shared', 'bgkeep', 'e2e_v26')
RESULTS = os.path.join(REPO, 'results', 'app')
E2E_TOOL = os.path.join(tempfile.gettempdir(), 'bgkeep_e2e_0419.py')
MEDIA_10MIN = os.path.join(CLIPS, 'bili_600s.wav')


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, 'app129_chain_v26.log'), 'a',
                  encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ── 峰值工作集（GetProcessMemoryInfo.PeakWorkingSetSize）──────────────
class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


def peak_ws_mb(pid: int):
    """取进程的峰值工作集（MB）。取不到 ⇒ None（**不猜**）。"""
    try:
        k = ctypes.windll.kernel32
        ps = ctypes.windll.psapi
        c = _PROCESS_MEMORY_COUNTERS()
        c.cb = ctypes.sizeof(c)
        h = k.OpenProcess(0x1000 | 0x0400, 0, int(pid))
        if not h:
            return None
        try:
            if not ps.GetProcessMemoryInfo(h, ctypes.byref(c),
                                           ctypes.sizeof(c)):
                return None
        finally:
            k.CloseHandle(h)
        return round(c.PeakWorkingSetSize / (1024.0 * 1024.0), 1)
    except Exception:
        return None


def build_media_10min():
    """把 `bili_420.wav` 拼成 **600 s**（10 分钟）固定片段。"""
    src = os.path.join(CLIPS, 'bili_420.wav')
    if os.path.isfile(MEDIA_10MIN):
        with wave.open(MEDIA_10MIN, 'rb') as w:
            dur = w.getnframes() / float(w.getframerate())
        if dur >= 595:
            log('10 分钟媒体已存在：%s（%.1f s）' % (MEDIA_10MIN, dur))
            return MEDIA_10MIN
    if not os.path.isfile(src):
        log('🔴 源媒体缺失：%s' % src)
        return None
    with wave.open(src, 'rb') as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    need = int(600 * sr)
    reps = (need // n) + 2
    with wave.open(MEDIA_10MIN, 'wb') as o:
        o.setnchannels(ch)
        o.setsampwidth(sw)
        o.setframerate(sr)
        written = 0
        for _ in range(reps):
            o.writeframes(data)
            written += n
            if written >= need:
                break
    with wave.open(MEDIA_10MIN, 'rb') as w:
        dur = w.getnframes() / float(w.getframerate())
    log('10 分钟媒体已生成：%s（%.1f s / %d B）'
        % (MEDIA_10MIN, dur, os.path.getsize(MEDIA_10MIN)))
    return MEDIA_10MIN


def ensure_e2e_tool():
    """把 commit 3573b2d 的 `tools/bgkeep_e2e.py` 取出来（不用工作树！）。"""
    out = os.path.join(os.environ.get('TEMP', os.path.dirname(MEDIA_10MIN)),
                       'bgkeep_e2e_0419.py')
    if os.path.isfile(out):
        return out
    p = subprocess.run(['git', '-C', EXT_REPO, 'show',
                        '3573b2d:tools/bgkeep_e2e.py'], capture_output=True)
    if p.returncode != 0:
        log('🔴 取 bgkeep_e2e.py 失败：%s' % p.stderr[-500:])
        return None
    with open(out, 'wb') as f:
        f.write(p.stdout)
    log('bgkeep_e2e.py（3573b2d）已取到：%s（%d B）'
        % (out, os.path.getsize(out)))
    return out


def ports_free():
    import socket
    for p in (8765, 8766):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', p))
        except OSError:
            return False
        finally:
            s.close()
    return True


def make_ext_shim():
    """建一个 `ext` 垫片包：`__path__` 追加 `<pkg>/ext` 与 `<pkg>/ext/bridge`。

    🔴 背景：`tools/bgkeep_e2e.py`（commit 3573b2d）有一行
       `from ext.extension_id import resolve_extension_id`
       —— 源码仓里 `ext/extension_id.py` 是 `ext/` 的**同级**模块；
       包内它实际在 `ext/bridge/` 下
       ⇒ 纯 `PYTHONPATH=<pkg>` 时 `ext.extension_id` **找不到**。
    ⇒ 垫片只做**路径扩展**，不改任何 EXT 代码。
    """
    shim = os.path.join(OUT_ROOT, '_extshim')
    extdir = os.path.join(shim, 'ext')
    os.makedirs(extdir, exist_ok=True)
    init = (
        '# 🔴 包内布局垫片（打包侧加，不改 EXT 代码）：\n'
        '#   把包内 `ext/bridge/` 的模块也暴露到 `ext.*` 下\n'
        '#   ⇒ 源码仓的 `from ext.extension_id import ...` 在包内原样可用。\n'
        'import os as _os\n'
        '_PKG = %r\n'
        '__path__.append(_os.path.join(_PKG, "ext"))\n'
        '__path__.append(_os.path.join(_PKG, "ext", "bridge"))\n' % PKG)
    with open(os.path.join(extdir, '__init__.py'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write(init)
    return shim


def run_arm(name, bg_off, media, tail_wait=45.0, timeout=1800):
    """跑一臂：单独起桥接 ⇒ 跑 e2e ⇒ 记录峰值内存 ⇒ 停桥接。"""
    out = os.path.join(OUT_ROOT, name)
    os.makedirs(out, exist_ok=True)
    log('=== 臂 %s（bgkeep %s）开始 ==='
        % (name, 'OFF' if bg_off else 'ON'))

    env = dict(os.environ)
    env['EXT_APP_ROOT'] = PKG
    env['EXT_APP_SEARCH_ROOT'] = PKG
    env['PYTHONPATH'] = PKG + os.pathsep + os.path.join(PKG, '.runtime_deps')
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('EXT_BG_DEVICE', None)          # ⇒ 默认 GPU.0（reviewer 定）
    # 🔴🔴 设备口径：**reviewer 明文「出厂默认：ASR/MT GPU.0、TTS NPU」**
    #   ⇒ 而 EXT 源码仓 `ext/config.py` 的默认是
    #      `DEVICE_TTS = EXT_TTS_DEVICE or "AUTO"`、`DEVICE_MT = ... "AUTO"`
    #      ⇒ AUTO 在本机会解析成 **MT=NPU / TTS=CUDA 边车**
    #      （与 App 完整版默认档 `device_config` 的 **GPU.0 / GPU.0 / NPU** 不同）
    #   ⇒ 必须显式钉死，否则跑的不是 reviewer 要的那条口径，
    #      也**跑不到 App 的 OV TTS 路径**（APP-130 的 cp 自检就在那条路径上）。
    env['EXT_MT_DEVICE'] = 'GPU.0'
    env['EXT_TTS_DEVICE'] = 'NPU'
    # 🔴 e2e 工具需要 `ext.extension_id`（源码仓里是 `ext/` 顶层模块，
    #   包内实际在 `ext/bridge/` 下）⇒ 加**路径垫片**（不改 EXT 代码）
    shim = make_ext_shim()
    env['PYTHONPATH'] = shim + os.pathsep + env['PYTHONPATH']

    logf = os.path.join(out, 'bridge.log')
    errf = os.path.join(out, 'bridge.err')
    args = [PKG_PY, '-X', 'utf8', '-m', 'ext.bridge', '--real', '--pipeline',
            '--port', '8765', '--delay', '20', '--target-lang', 'zh',
            '--spk-bypass']
    proc = subprocess.Popen(args, cwd=out, env=env, stdout=open(logf, 'wb'),
                            stderr=open(errf, 'wb'))
    log('桥接已起：pid=%d（cwd=%s）' % (proc.pid, out))

    rec = {'arm': name, 'bg_off': bool(bg_off), 'pid': proc.pid,
           'media': media, 'pkg': PKG, 'ext_commit': '3573b2d',
           'started': datetime.datetime.now().isoformat(timespec='seconds')}

    ready = False
    t0 = time.time()
    while time.time() - t0 < 420:
        if proc.poll() is not None:
            log('🔴 桥接提前退出 rc=%s' % proc.returncode)
            break
        try:
            txt = open(logf, encoding='utf-8', errors='replace').read()
            if 'ws://127.0.0.1:8765' in txt:
                ready = True
                break
        except Exception:
            pass
        time.sleep(5)
    rec['bridge_ready'] = ready
    rec['bridge_ready_s'] = round(time.time() - t0, 1)
    log('桥接就绪=%s（%.1f s）' % (ready, rec['bridge_ready_s']))

    peak = None
    if ready:
        e2e = ensure_e2e_tool()
        cmd = [PKG_PY, '-X', 'utf8', e2e, '--media', media, '--port', '8765',
               '--delay', '20', '--target-lang', 'zh', '--voice', 'A',
               '--token-file', os.path.join(out, 'bridge_token.txt'),
               '--out', out, '--tail-wait', str(tail_wait),
               '--max-sec', '600']
        if bg_off:
            cmd.append('--bg-off')
        log('e2e：%s' % ' '.join(cmd[3:]))
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=out, env=env)
            rec['e2e_rc'] = p.returncode
            rec['e2e_s'] = round(time.time() - t1, 1)
            with open(os.path.join(out, 'e2e_stdout.txt'), 'w',
                      encoding='utf-8') as f:
                f.write((p.stdout or '') + (p.stderr or ''))
            log('e2e 结束 rc=%s 用时 %.1f s' % (p.returncode, rec['e2e_s']))
        except subprocess.TimeoutExpired:
            rec['e2e_rc'] = 'TIMEOUT'
            rec['e2e_s'] = round(time.time() - t1, 1)
            log('🔴 e2e 超时（%d s）' % timeout)
        # 峰值内存（跑完之后进程可能已退 ⇒ 期间取不到就记 None）
        peak = peak_ws_mb(proc.pid)
        rec['peak_ws_mb'] = peak
        log('桥接峰值工作集：%s MB' % peak)
        # 桥接日志里的关键证据（APP-130 自检 / 分离设备 / 引擎设备）
        try:
            txt = open(logf, encoding='utf-8', errors='replace').read()
            rec['bridge_log_tail'] = txt[-4000:]
            for key in ('cp_prefill:', 'cp_decode:', 'EXECUTION_DEVICES',
                        '自检'):
                hits = [l for l in txt.splitlines() if key in l]
                if hits:
                    rec.setdefault('log_lines', {})[key] = hits[-4:]
        except Exception:
            pass

    # 停桥接（只停自己的）
    try:
        proc.terminate()
        proc.wait(timeout=20)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    rec['ended'] = datetime.datetime.now().isoformat(timespec='seconds')
    log('=== 臂 %s 结束 ===' % name)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='off,on')
    ap.add_argument('--media', default=MEDIA_10MIN)
    args = ap.parse_args()

    if not os.path.isfile(PKG_PY):
        log('FAIL: 包内 python 不存在 %s' % PKG_PY)
        return 2
    media = build_media_10min()
    if not media:
        return 3
    ensure_e2e_tool()
    os.makedirs(OUT_ROOT, exist_ok=True)

    lock = B.acquire_lock('app bgkeep v2.6 chain')
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': PKG, 'ext_commit': '3573b2d', 'media': media, 'arms': []}
    try:
        for a in args.arms.split(','):
            a = a.strip()
            if not a:
                continue
            for _k in range(60):
                if ports_free():
                    break
                time.sleep(5)
            rec = run_arm('bgkeep_%s' % a, (a == 'off'), media)
            rec['metrics'] = read_metrics(rec)
            rep['arms'].append(rec)
            with open(os.path.join(RESULTS, 'app129_chain_v26_evidence.json'),
                      'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)
    finally:
        B.release_lock(lock)
    log('证据：results/app/app129_chain_v26_evidence.json')
    return 0


def read_metrics(rec):
    """从臂目录的 `bgkeep_e2e.json` 抽 reviewer 要的数字。"""
    out = {}
    p = os.path.join(OUT_ROOT, rec['arm'], 'bgkeep_e2e.json')
    if not os.path.isfile(p):
        return out
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception as e:
        out['parse_error'] = repr(e)
        return out
    out['duration_s'] = d.get('duration_s')
    out['dubs'] = d.get('dubs')
    out['bg_blocks'] = d.get('bg_blocks')
    out['bg_late_blocks'] = d.get('bg_late_blocks')
    out['bg_contiguous'] = d.get('bg_contiguous')
    out['bg_covered_s'] = d.get('bg_covered_s')
    out['fallback_to_orig_s'] = d.get('fallback_to_orig_s')
    out['dub_late_vs_play_s'] = d.get('dub_late_vs_play_s')
    out['dub_shift_msgs'] = d.get('dub_shift_msgs')
    out['dub_shift_applied'] = d.get('dub_shift_applied')
    out['bg_status_last'] = d.get('bg_status_last')
    sb = d.get('stats_bg') or {}
    out['stats_bg'] = {k: sb.get(k) for k in
                       ('bg_keep', 'bg_state', 'bg_blocks_sent', 'sep_device',
                        'sep_rtf', 'bg_late_blocks', 'bg_fallback_s')}
    sf = d.get('stats_full') or {}
    out['stats_full'] = {k: sf.get(k) for k in
                         ('n_frames', 'n_dropped', 'buffered_sec', 'bg_keep',
                          'bg_state', 'n_dubs', 'synth_rtf', 'n_sentences',
                          'n_lost', 'peak_backlog_s', 'backlog_end_s',
                          'speed_max', 'speed_avg', 'peak_mem_mb')}
    out['stats_full_raw_keys'] = sorted(sf.keys())
    sm = d.get('stats_misc') or {}
    out['stats_misc'] = sm
    return out


if __name__ == '__main__':
    sys.exit(main())
