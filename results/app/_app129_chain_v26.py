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
| EXT 代码 | **源码仓** `live_dub_ext/`（工作树） | **包内** `<v2.6>/ext/bridge`（commit **4740b06** / v0.4.20） |
| App 运行时 | `EXT_APP_ROOT=<v2.5>` | `EXT_APP_ROOT=<v2.6>` |
| python | v2.5 包内 python | v2.6 包内 python |
| 媒体 | 30 s 片段 | **10 分钟固定片段**（bili_420.wav 拼接） |
| 臂 | 3 条 clone 臂 | **bgkeep off / on 各一轮** |

## 纪律

- **持共享机器锁**（整链占设备 ⇒ 不能与别的模块抢）；
- 桥接 **cwd = 臂目录**（⇒ `bridge_token.txt` 落在**包外**，包内不留污染）；
- `bgkeep_e2e.py` 用 **commit 4740b06** 的版本（🔴 **按 commit 取，不取工作树**——
  工作树已被 reviewer 改到 v0.4.21 在制品）；
- 每臂**单独起桥接**（reviewer 明文）；
- 桥接进程峰值内存用 `GetProcessMemoryInfo` 的 `PeakWorkingSetSize`（cmm）。
"""
from __future__ import annotations

import argparse
import ast
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
E2E_TOOL = os.path.join(tempfile.gettempdir(), 'bgkeep_e2e_0420.py')
#: 🔴🔴 **固定片段必须是 reviewer's e2e7 基线那一条**
#:   （`shared/bgkeep/e2e7/*/bgkeep_e2e.json` 的 `media` 字段 = 这个文件）
#:   ⇒ 只有同一条媒体 ⇒ dubs / dub_late 才能和 reviewer 引用的
#:     「off 123 句 / dub_late max 2.43 s」直接比。
#:   🔴 上一会话误用了 `shared/bgkeep/clips/bili_600s.wav`（B 站视频）
#:      ⇒ 那是**另一条**媒体（48 kHz 立体声、旁白密度不同）
#:      ⇒ dubs 只有 54、dub_late max 244 s ⇒ **与基线不可比**。
MEDIA_10MIN = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
#: 🔴 桥接端口（**可配**）⇒ reviewer 并发作业占用 8765 时可换端口，避免互杀
PORT = 8765


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
    """**reviewer e2e7 基线那一条固定片段**（不合成、不拼接）。

    🔴🔴 2026-11-24 12:4x 修正：上一会话把媒体换成了
    `shared/bgkeep/clips/bili_600s.wav`（B 站视频，48 kHz 立体声）
    ⇒ 那是**另一条**媒体 ⇒ dubs 只有 54、dub_late max 244 s
    ⇒ 与 reviewer 引用的 e2e7 基线（dubs 123 / max 2.43 s）**不可比**。
    ⇒ 改回 **reviewer e2e7 用的那一条**：
    `confucius4-openvino/test_audio/clip_10min_0_600.wav`
    （600.0 s / 单声道 / 16 kHz ⇒ 与 e2e7 的 `media` 字段逐字一致）。
    """
    if not os.path.isfile(MEDIA_10MIN):
        log('🔴 固定片段缺失：%s' % MEDIA_10MIN)
        return None
    with wave.open(MEDIA_10MIN, 'rb') as w:
        dur = w.getnframes() / float(w.getframerate())
    log('固定片段（reviewer e2e7 同一条）：%s（%.1f s / %d B）'
        % (MEDIA_10MIN, dur, os.path.getsize(MEDIA_10MIN)))
    return MEDIA_10MIN


def ensure_e2e_tool():
    """把 commit 4740b06 的 `tools/bgkeep_e2e.py` 取出来（不用工作树！）。"""
    # 🔴 文件名带 commit ⇒ **不会命中上一会话遗留的旧缓存**
    #   （上一会话缓的是 3573b2d 版；本轮要 4740b06 版 ⇒ 多出 `dubs.npz`）
    out = os.path.join(os.environ.get('TEMP', os.path.dirname(MEDIA_10MIN)),
                       'bgkeep_e2e_4740b06.py')
    p = subprocess.run(['git', '-C', EXT_REPO, 'show',
                        '4740b06:tools/bgkeep_e2e.py'], capture_output=True)
    if p.returncode != 0:
        log('🔴 取 bgkeep_e2e.py 失败：%s' % p.stderr[-500:])
        return None
    with open(out, 'wb') as f:
        f.write(p.stdout)
    log('bgkeep_e2e.py（4740b06）已取到：%s（%d B）'
        % (out, os.path.getsize(out)))
    return out


def ports_free():
    import socket
    for p in (PORT, PORT + 1):
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

    🔴 背景：`tools/bgkeep_e2e.py`（commit 4740b06）有一行
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


def run_arm(name, bg_off, media, tail_wait=45.0, timeout=1800, voice='A',
            spk_bypass=True):
    """跑一臂：单独起桥接 ⇒ 跑 e2e ⇒ 记录峰值内存 ⇒ 停桥接。

    🔴 **APP-131**：新增 `voice='clone'` 臂（保留背景音开）⇒
       报 `stats_full` 里的克隆相关计数。
    """
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
    # 🔴 `--token-file` 必须显式指到**包外**（臂目录）
    #   ⇒ 否则 EXT 的默认相对路径会落在 `<包根>/ext/bridge_token.txt`
    #      ⇒ **包内污染**（APP-129 §2 明文：包内不得有 bridge_token.txt）
    # 🔴 `--margin-out` ⇒ 桥接把**逐段余量 / 积压 / RTF** 落盘
    #   （reviewer §3.2 要的「语速 max / synth_rtf / 积压峰值与收尾积压」
    #    **不在** bgkeep_e2e.json 里 ⇒ 必须另落一份 margin.json）
    margin_out = os.path.join(out, 'margin.json')
    # 🔴 **口径开关**：说话人旁路会与 ASR/TTS **抢同一把设备锁**
    #   （实测 spk_gpu_lock_held_ms = 92036.7、shares_device_lock_with_asr = true）
    #   ⇒ reviewer 的 e2e7 基线（10 分钟 123 句 / dub_late max 2.43 s）是
    #   **旁路关** 的口径 ⇒ 本脚本两档都跑（`off`/`on` = 旁路开；
    #   `off_nb` = 旁路关 = 与基线同口径）。
    if spk_bypass:
        args.append('--spk-bypass')
    args = [PKG_PY, '-X', 'utf8', '-m', 'ext.bridge', '--real', '--pipeline',
            '--port', str(PORT), '--delay', '20', '--target-lang', 'zh',
            '--margin-out', margin_out,
            '--token-file', os.path.join(out, 'bridge_token.txt')]
    proc = subprocess.Popen(args, cwd=out, env=env, stdout=open(logf, 'wb'),
                            stderr=open(errf, 'wb'))
    log('桥接已起：pid=%d（cwd=%s）' % (proc.pid, out))

    rec = {'arm': name, 'bg_off': bool(bg_off), 'voice': voice,
           'spk_bypass': bool(spk_bypass),
           'pid': proc.pid,
           'media': media, 'pkg': PKG, 'ext_commit': '4740b06',
           'started': datetime.datetime.now().isoformat(timespec='seconds')}

    ready = False
    t0 = time.time()
    while time.time() - t0 < 420:
        if proc.poll() is not None:
            log('🔴 桥接提前退出 rc=%s' % proc.returncode)
            break
        try:
            txt = open(logf, encoding='utf-8', errors='replace').read()
            if ('ws://127.0.0.1:%d' % PORT) in txt:
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
        cmd = [PKG_PY, '-X', 'utf8', e2e, '--media', media, '--port', str(PORT),
               '--delay', '20', '--target-lang', 'zh', '--voice', voice,
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
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--media', default=MEDIA_10MIN)
    ap.add_argument('--merge', action='store_true',
                    help='把本轮臂**追加**进已有证据 json（不覆盖）')
    args = ap.parse_args()

    global PORT
    PORT = args.port

    if not os.path.isfile(PKG_PY):
        log('FAIL: 包内 python 不存在 %s' % PKG_PY)
        return 2
    media = build_media_10min()
    if not media:
        return 3
    ensure_e2e_tool()
    os.makedirs(OUT_ROOT, exist_ok=True)

    lock = B.acquire_lock('app bgkeep v2.6 chain')
    ev_path = os.path.join(RESULTS, 'app129_chain_v26_evidence.json')
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': PKG, 'ext_commit': '4740b06', 'media': media, 'arms': []}
    if args.merge and os.path.isfile(ev_path):
        try:
            old = json.load(open(ev_path, encoding='utf-8'))
            rep['arms'] = list(old.get('arms') or [])
            log('--merge：已载入 %d 条旧臂' % len(rep['arms']))
        except Exception as e:
            log('🔴 --merge 载入失败：%r' % (e,))
    try:
        for a in args.arms.split(','):
            a = a.strip()
            if not a:
                continue
            for _k in range(60):
                if ports_free():
                    break
                time.sleep(5)
            # 🔴 APP-131：`clone` 臂 = 保留背景音**开** ＋ voice=clone
            #   （reviewer：「另请加一臂 voice=clone（保留背景音开）」）
            if a == 'clone':
                rec = run_arm('bgkeep_clone', False, media, voice='clone')
            elif a == 'off_nb':
                # 🔴 与 reviewer e2e7 基线**同口径**：保留背景音关 ＋ 旁路关
                rec = run_arm('bgkeep_off_nb', True, media, spk_bypass=False)
            else:
                rec = run_arm('bgkeep_%s' % a, (a == 'off'), media)
            rec['metrics'] = read_metrics(rec)
            rep['arms'].append(rec)
            with open(ev_path, 'w', encoding='utf-8') as f:
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
    # 🔴🔴 **reviewer §3.2 要的「语速 max / synth_rtf / 积压峰值与收尾积压」
    #   **不在** bgkeep_e2e.json 里** ⇒ 从桥接落盘的 `margin.json` 取。
    #   （`margin.json` = `--margin-out` 的产物：逐段余量 + rtf_breakdown
    #     + sync_rootcause + adaptive_speed + per_segment）
    mp = os.path.join(OUT_ROOT, rec['arm'], 'margin.json')
    if os.path.isfile(mp):
        try:
            m = json.load(open(mp, encoding='utf-8'))
        except Exception as e:
            m = {}
            out['margin_parse_error'] = repr(e)
        if m:
            out['margin_file'] = mp
            out['margin_bytes'] = os.path.getsize(mp)
            mg = m.get('margin') or {}
            out['margin_summary'] = {
                'n_segments': mg.get('n_segments'),
                'n_negative': mg.get('n_negative'),
                'min': mg.get('min'), 'p50': mg.get('p50'),
                'p95': mg.get('p95'), 'max': mg.get('max'),
                'mean': mg.get('mean'),
                'last_segment_lag_sec': mg.get('last_segment_lag_sec'),
                'max_lag_sec': mg.get('max_lag_sec'),
                'lag_growth_slope_sec_per_sec': mg.get('lag_growth_slope_sec_per_sec'),
            }
            rae = m.get('margin', {}).get('ready_after_orig_end') or {}
            out['ready_after_orig_end'] = rae
            rb = m.get('rtf_breakdown') or {}
            out['rtf_breakdown'] = rb
            sc = m.get('sync_rootcause') or {}
            out['sync_rootcause'] = sc
            asp = m.get('adaptive_speed') or {}
            out['adaptive_speed'] = asp
            pl = m.get('pipeline') or {}
            out['pipeline_stage_wall_sec'] = pl.get('stage_wall_sec')
            ps = m.get('per_segment') or []
            out['n_per_segment'] = len(ps)
            # 逐段：语速（speed）与合成 RTF（reviewer 要「语速 max」）
            spd = [r.get('speed') for r in ps if isinstance(r, dict)
                   and isinstance(r.get('speed'), (int, float))]
            if spd:
                out['speed_max'] = max(spd)
                out['speed_avg'] = round(sum(spd) / len(spd), 4)
                out['speed_n'] = len(spd)
            # 🔴 EXT 的 `per_segment` 行**没有** `synth_rtf` 字段
            #   ⇒ 合成 RTF 按 EXT-034② 的口径自算：
            #      每段 RTF_out = tts_sec / speech_sec
            #   （与 `rtf_breakdown.RTF_out` 同一口径 ⇒ 可交叉核对）
            rtf = []
            for r in ps:
                if not isinstance(r, dict):
                    continue
                t_s = r.get('tts_sec')
                s_s = r.get('speech_sec')
                if (isinstance(t_s, (int, float)) and isinstance(s_s, (int, float))
                        and s_s > 0):
                    rtf.append(float(t_s) / float(s_s))
            if rtf:
                rtf_s = sorted(rtf)
                out['synth_rtf_n'] = len(rtf_s)
                out['synth_rtf_p50'] = round(rtf_s[len(rtf_s) // 2], 4)
                out['synth_rtf_p90'] = round(
                    rtf_s[min(len(rtf_s) - 1, int(len(rtf_s) * 0.9))], 4)
                out['synth_rtf_max'] = round(max(rtf_s), 4)
                out['synth_rtf_definition'] = (
                    'EXT-034② 口径 RTF_out：每段 tts_sec / speech_sec，'
                    '再取中位 / P90 / 最大；与 margin.json:rtf_breakdown.RTF_out 同口径')
            # 积压（EXT 侧：滞后）——峰值 = max_lag_sec，收尾 = last_segment_lag_sec
            out['backlog_peak_sec'] = mg.get('max_lag_sec')
            out['backlog_end_sec'] = mg.get('last_segment_lag_sec')
            out['backlog_definition'] = (
                'EXT 侧积压 = 排程余量的负值（max_lag_sec = 峰值滞后；'
                'last_segment_lag_sec = 末句滞后）；EXT 链路上 App 的 '
                'peak_backlog_s / backlog_end_s 不经 EXT 暴露 ⇒ 用同义的滞后口径')
            # 🔴 APP-131：克隆相关计数（tts_nearest_voice / gender_switch /
            #   gender_selfref）——**EXT v0.4.20 把它们存在
            #   `clone_voice._reasons`，只经日志行 `[spk] 标签来源统计：{…}`
            #   暴露**（不在 `stats_full` 里）⇒ 从桥接日志解析，
            #   并**如实注明来源**（不谎称来自 stats_full）。
            reasons = {}
            gender_switch_lines = []
            try:
                btxt = open(os.path.join(OUT_ROOT, rec['arm'], 'bridge.log'),
                            encoding='utf-8', errors='replace').read()
                for ln in btxt.splitlines():
                    if '标签来源统计' in ln:
                        frag = ln.split('标签来源统计：', 1)[-1].strip()
                        try:
                            d = ast.literal_eval(frag)
                            if isinstance(d, dict):
                                for k, v in d.items():
                                    reasons[k] = reasons.get(k, 0) + int(v)
                        except Exception:
                            pass
                    elif '性别守门' in ln:
                        gender_switch_lines.append(ln.strip()[:200])
            except Exception as e:
                out['clone_parse_error'] = repr(e)
            if reasons:
                out['clone_reasons'] = reasons
                out['clone_reasons_source'] = (
                    "EXT 桥接日志行 `[spk] 标签来源统计：{…}` 解析求和"
                    "（EXT v0.4.20 不把克隆计数放进 stats_full）")
                for k in ('tts_nearest_voice', 'gender_switch', 'gender_selfref',
                          'tts_nearest', 'gender_keep', 'self_ref'):
                    out['clone_%s' % k] = reasons.get(k, 0)
            out['gender_switch_log_lines'] = gender_switch_lines[:20]
    else:
        out['margin_file'] = None
    return out


if __name__ == '__main__':
    sys.exit(main())
