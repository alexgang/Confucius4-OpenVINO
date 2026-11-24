#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-132/APP-133：v2.6 整链**一次持锁到底**重跑（EXT v0.4.21 / b2a4978）。

## 本轮（APP-132/133）相对上一轮（`_app129_chain_v26.py`）的三处真改动

| # | 上一轮的做法 | 🔴 缺陷 | 本轮改法 |
|---|---|---|---|
| **①** | `B.acquire_lock()` 用 `os.replace(tmp, LOCK)` 写锁 | **不是原子创建** ⇒ reviewer 的 CreateNew 在 12:44:18 成功 ⇒ 我方其实**没在持锁** | 用 `_app132_lock.MachineLock`（**`O_CREAT|O_EXCL` 原子创建** ＋ 10 s 看门狗复核） |
| **②** | 看门狗一旦发现锁被别人抢就**放弃写回** | 锁被抢后链**继续跑但不再持锁** ⇒ 计时作废且无人知晓 | 看门狗把「丢锁」记成**事件**（`app132_lock_events.jsonl`）＋ `lk.lost=True` ⇒ **每臂结束都核一次** |
| **③** | 只跑 `bgkeep_off / bgkeep_on / bgkeep_clone` | reviewer APP-131/133 还要 **clone 臂的 `stats_full.clone_reasons` / `n_gender_splits`**；且 APP-133 要求 EXT = **b2a4978** | EXT 换成 **b2a4978（v0.4.21）** ＋ clone 臂**额外抽 clone 计数** |

## 顺带补齐 reviewer §3.2 要的数字（上一轮**没采到**的）

reviewer APP-129 §3.2 明文要报：
> dubs、丢句（须 0）、语速 max、dub_late max/p90/n_late、
> bg_blocks / bg_late_blocks / fallback_to_orig_s、**synth_rtf**、
> **配音积压峰值与收尾积压**；**桥接进程峰值内存开关差值**

上一轮 `bgkeep_e2e.json` 里 **synth_rtf / speed_max / peak_backlog_s /
backlog_end_s 全是 `null`** ⇒ 因为 EXT 桥接的 `stats` 消息**不**带这些字段
（它们在 `margin.json` 里，而 `margin.json` 要客户端**主动发 `dump_margin`
请求**才会落盘；上一轮的 e2e 工具没发 ⇒ 桥接被 terminate ⇒ `finally` 不执行
⇒ `margin.json` 从未落盘）。

⇒ 本轮：**在 e2e 跑完后、发 `dump_margin` 之前**追加一条自造请求 ——
用**包内 EXT 的同一个 ws 协议**发 `{"type":"dump_margin"}` ⇒ 桥接立刻落盘
`margin.json`（含 `margin_summary` / `per_segment` / `rtf_breakdown` /
`sync_rootcause` …）⇒ 于是 **synth_rtf / 语速 max / 积压峰值 / 收尾积压**
都能从**原始字段**里取。

🔴 **纪律**：不改动 EXT 任何代码；只在**客户端侧**多发一条协议消息
（协议本来就支持，见 `ext/bridge.py` 的 `dump_margin` 分支）。

## 纪律

- **一次持锁到底**（`MachineLock` 原子创建），**中途不删**；
- 每臂结束**当场复核**持锁状态（`lk.check()`）⇒ 被抢过就**如实标注作废**；
- 每臂**单独起桥接**（reviewer 明文）；
- `bgkeep_e2e.py` / EXT 源码**按 commit b2a4978 取**（不用工作树）；
- 桥接 cwd = 臂目录 ⇒ `bridge_token.txt` 落在**包外**；
- `--margin-out` ⇒ `margin.json` 落在**臂目录**（包外）。

## 用法

    python results/app/_app133_chain_v26.py --arms off,on,clone
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
sys.path.insert(0, HERE)

from _app132_lock import MachineLock  # noqa: E402

PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
EXT_REPO = os.path.join(HOME, 'live_dub_ext')
CLIPS = os.path.join(HOME, 'shared', 'bgkeep', 'clips')
OUT_ROOT = os.path.join(HOME, 'shared', 'bgkeep', 'e2e_v26_r2')
RESULTS = os.path.join(REPO, 'results', 'app')
MEDIA_10MIN = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
EXT_COMMIT = 'b2a4978'

PORT = 8775


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, 'app133_chain_v26.log'), 'a',
                  encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# 桥接峰值内存（GetProcessMemoryInfo.PeakWorkingSetSize）
# ═══════════════════════════════════════════════════════════════════
class _PMC(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


def peak_ws_mb(pid):
    """进程峰值工作集（MB）。取不到 ⇒ None（**不臆造**）。"""
    try:
        k = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        h = k.OpenProcess(0x1000 | 0x0400, 0, int(pid))
        if not h:
            return None
        c = _PMC()
        c.cb = ctypes.sizeof(_PMC)
        ok = psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
        k.CloseHandle(h)
        if not ok:
            return None
        return round(c.PeakWorkingSetSize / 1048576.0, 1)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════════
def git_show(relpath):
    p = subprocess.run(['git', '-C', EXT_REPO, 'show',
                        '%s:%s' % (EXT_COMMIT, relpath)],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('git show %s:%s 失败：%s'
                           % (EXT_COMMIT, relpath,
                              (p.stderr or b'').decode('utf-8', 'replace')[-300:]))
    return p.stdout


def ensure_e2e_tool():
    """按 commit b2a4978 取 `tools/bgkeep_e2e.py`（**不用工作树**）。"""
    out = os.path.join(os.environ.get('TEMP', os.path.dirname(MEDIA_10MIN)),
                       'bgkeep_e2e_%s.py' % EXT_COMMIT)
    data = git_show('tools/bgkeep_e2e.py')
    with open(out, 'wb') as f:
        f.write(data)
    log('bgkeep_e2e.py（%s）已取到：%s（%d B）'
        % (EXT_COMMIT, out, os.path.getsize(out)))
    return out


def make_ext_shim():
    """包内布局垫片（只扩展 `ext.__path__`，不改 EXT 代码）。"""
    shim = os.path.join(OUT_ROOT, '_extshim')
    extdir = os.path.join(shim, 'ext')
    os.makedirs(extdir, exist_ok=True)
    init = (
        '# 🔴 包内布局垫片（打包侧加，不改 EXT 代码）：\n'
        'import os as _os\n'
        '_PKG = %r\n'
        '__path__.append(_os.path.join(_PKG, "ext"))\n'
        '__path__.append(_os.path.join(_PKG, "ext", "bridge"))\n' % PKG)
    with open(os.path.join(extdir, '__init__.py'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write(init)
    return shim


def make_dump_margin_client():
    """🔴 客户端侧补一条 `dump_margin` 请求（**不改 EXT 代码**）。

    EXT 的 `ext/bridge.py` 明确支持 `{"type":"dump_margin"}` ⇒ 服务端立刻把
    `margin.json` 落盘（含 `margin_summary` / `per_segment` /
    `rtf_breakdown` / `sync_rootcause` …）。

    **为什么必须补**：上一轮 `margin.json` 从未落盘 ⇒ `synth_rtf` /
    语速 max / 积压峰值 / 收尾积压 全部拿不到 ⇒ reviewer §3.2 要的数字空着。
    （桥接被 `terminate()` ⇒ Python `finally` 不执行 ⇒ 退出路径也不落盘。）
    """
    src = os.path.join(os.environ.get('TEMP', OUT_ROOT),
                       'app133_dump_margin.py')
    code = (
        '# -*- coding: utf-8 -*-\n'
        '"""客户端侧补发 dump_margin（协议本来就支持；不改 EXT 代码）。"""\n'
        'import asyncio, json, os, sys, time\n'
        'import websockets\n'
        '\n'
        'async def main():\n'
        '    port = int(sys.argv[1])\n'
        '    token_file = sys.argv[2]\n'
        '    out_dir = sys.argv[3]\n'
        '    pkg = sys.argv[4]\n'
        '    token = open(token_file, encoding="utf-8").read().strip() \\\n'
        '        if os.path.exists(token_file) else ""\n'
        '    sys.path.insert(0, pkg)\n'
        '    from ext.extension_id import resolve_extension_id\n'
        '    origin = "chrome-extension://" + str(resolve_extension_id())\n'
        '    url = "ws://127.0.0.1:%d/" % port\n'
        '    async with websockets.connect(url, max_size=None, open_timeout=30,\n'
        '                                  origin=origin) as ws:\n'
        '        await ws.send(json.dumps({"type": "hello", "token": token,\n'
        '            "role": "uplink", "source": "player",\n'
        '            "sample_rate": 16000, "delay_sec": 20,\n'
        '            "target_lang": "zh", "voice": "A",\n'
        '            "bg_keep": False, "bg_sample_rate": 48000,\n'
        '            "bg_channels": 2, "capture_mode": "tabCapture"}))\n'
        '        await asyncio.sleep(2.0)\n'
        '        await ws.send(json.dumps({"type": "dump_margin"}))\n'
        '        deadline = time.time() + 60\n'
        '        async for raw in ws:\n'
        '            try:\n'
        '                m = json.loads(raw)\n'
        '            except Exception:\n'
        '                continue\n'
        '            if m.get("type") == "margin_dumped":\n'
        '                print(json.dumps(m, ensure_ascii=False))\n'
        '                return 0\n'
        '            if time.time() > deadline:\n'
        '                break\n'
        '    print(json.dumps({"type": "margin_dumped", "dumped": False,\n'
        '                      "why": "timeout"}))\n'
        '    return 1\n'
        '\n'
        'sys.exit(asyncio.run(main()))\n')
    with open(src, 'w', encoding='utf-8', newline='\n') as f:
        f.write(code)
    return src


def ports_free():
    import socket
    for p in (PORT, PORT + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1', p))
            return True
        except OSError:
            return False
        finally:
            s.close()
    return True


def port_listening(port):
    """端口**真的在监听**（而不是「日志里出现过地址」）。

    🔴 判据工程：上一版用「日志出现横幅」当就绪判据 ⇒ **假 PASS** ⇒
    e2e 立刻 `ConnectionRefusedError` ⇒ 三臂全废（本轮首跑踩到）。
    ⇒ 判据必须是**行为级**：能不能真的建连。
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(('127.0.0.1', int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


# ═══════════════════════════════════════════════════════════════════
# 跑一臂
# ═══════════════════════════════════════════════════════════════════
def run_arm(name, bg_off, media, tool, dump_client, voice='A',
            spk_bypass=True, timeout=1800, tail_wait=45.0):
    out = os.path.join(OUT_ROOT, name)
    os.makedirs(out, exist_ok=True)
    log('=== 臂 %s（bgkeep %s，voice=%s，旁路%s）开始 ==='
        % (name, 'OFF' if bg_off else 'ON', voice,
           '开' if spk_bypass else '关'))

    env = dict(os.environ)
    env['EXT_APP_ROOT'] = PKG
    env['EXT_APP_SEARCH_ROOT'] = PKG
    env['PYTHONPATH'] = make_ext_shim() + os.pathsep + PKG + \
        os.pathsep + os.path.join(PKG, '.runtime_deps')
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('EXT_BG_DEVICE', None)      # ⇒ 默认 GPU.0（reviewer §1 定）
    # reviewer §3.2 明文：「出厂默认：ASR/MT GPU.0、TTS NPU」
    env['EXT_MT_DEVICE'] = 'GPU.0'
    env['EXT_TTS_DEVICE'] = 'NPU'

    logf = os.path.join(out, 'bridge.log')
    errf = os.path.join(out, 'bridge.err')
    margin_out = os.path.join(out, 'margin.json')

    args = [PKG_PY, '-X', 'utf8', '-m', 'ext.bridge', '--real', '--pipeline',
            '--port', str(PORT), '--delay', '20', '--target-lang', 'zh',
            '--margin-out', margin_out,
            '--token-file', os.path.join(out, 'bridge_token.txt')]
    if spk_bypass:
        args.append('--spk-bypass')
    proc = subprocess.Popen(args, cwd=out, env=env, stdout=open(logf, 'wb'),
                            stderr=open(errf, 'wb'))
    log('桥接已起：pid=%d（cwd=%s）' % (proc.pid, out))

    rec = {'arm': name, 'bg_off': bool(bg_off), 'voice': voice,
           'spk_bypass': bool(spk_bypass), 'pid': proc.pid,
           'media': media, 'pkg': PKG, 'ext_commit': EXT_COMMIT,
           'started': datetime.datetime.now().isoformat(timespec='seconds')}

    try:
        # ── 等桥接就绪 ──────────────────────────────────────────
        # 🔴🔴 **就绪判据必须与「端口真的在监听」一致**：
        #   上一版（本轮首跑）用「日志里出现『实时配音桥接』/『引擎预热完成』」
        #   ⇒ **判据错误**：横幅在**开始监听之前**就打出来 ⇒ e2e 立刻
        #   `ConnectionRefusedError`（WinError 1225）⇒ 三臂全废。
        #   ⇒ 改用**旧脚本的正确判据**：日志里出现**监听地址**
        #   （`ws://127.0.0.1:<port>`）**且**该端口**真的能建连**。
        ready = False
        t_ready = time.time()
        while time.time() - t_ready < 420:
            if proc.poll() is not None:
                log('🔴 桥接提前退出 rc=%s' % proc.returncode)
                break
            try:
                txt = open(logf, encoding='utf-8', errors='replace').read()
            except Exception:
                txt = ''
            if ('ws://127.0.0.1:%d' % PORT) in txt and port_listening(PORT):
                ready = True
                break
            time.sleep(5)
        rec['bridge_ready'] = ready
        rec['bridge_ready_s'] = round(time.time() - t_ready, 1)
        log('桥接就绪=%s（%.1f s）' % (ready, rec['bridge_ready_s']))
        if not ready:
            rec['error'] = 'bridge not ready'

        # ── 跑 e2e ──────────────────────────────────────────────
        cmd = [PKG_PY, '-X', 'utf8', tool, '--media', media,
               '--port', str(PORT), '--delay', '20', '--target-lang', 'zh',
               '--voice', voice,
               '--token-file', os.path.join(out, 'bridge_token.txt'),
               '--out', out, '--tail-wait', str(tail_wait),
               '--max-sec', '600']
        if bg_off:
            cmd.append('--bg-off')
        log('e2e：%s' % ' '.join(cmd))
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=out, env=env)
            rec['e2e_rc'] = p.returncode
            with open(os.path.join(out, 'e2e_stdout.txt'), 'w',
                      encoding='utf-8') as f:
                f.write((p.stdout or '') + (p.stderr or ''))
            log('e2e 结束 rc=%s 用时 %.1f s' % (p.returncode, time.time() - t1))
        except subprocess.TimeoutExpired:
            rec['e2e_rc'] = 'TIMEOUT'
            rec['e2e_s'] = round(time.time() - t1, 1)
            log('🔴 e2e 超时（%d s）' % timeout)

        # ── 🔴 补发 dump_margin ⇒ 让 margin.json 落盘 ────────────
        rec['margin_dumped'] = False
        try:
            dm = subprocess.run(
                [PKG_PY, '-X', 'utf8', dump_client, str(PORT),
                 os.path.join(out, 'bridge_token.txt'), out, PKG],
                capture_output=True, text=True, timeout=120, cwd=out, env=env)
            log('dump_margin：rc=%s out=%s' % (dm.returncode,
                                               (dm.stdout or '').strip()[:200]))
            rec['dump_margin_out'] = (dm.stdout or '').strip()[:400]
            rec['margin_dumped'] = os.path.isfile(margin_out)
        except Exception as e:
            log('🔴 dump_margin 失败：%r' % (e,))
            rec['dump_margin_error'] = repr(e)
        log('margin.json 落盘=%s' % rec['margin_dumped'])
    finally:
        peak = peak_ws_mb(proc.pid)
        rec['peak_ws_mb'] = peak
        log('桥接峰值工作集：%s MB' % peak)
        try:
            txt = open(logf, encoding='utf-8', errors='replace').read()
            rec['bridge_log_tail'] = txt[-4000:]
            for key in ('cp_prefill:', 'cp_decode:', 'EXECUTION_DEVICES'):
                hits = [l for l in txt.splitlines() if key in l]
                if hits:
                    rec.setdefault('log_lines', {})[key] = hits[-4:]
        except Exception:
            pass
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


# ═══════════════════════════════════════════════════════════════════
# 指标抽取（**只报文件里真有的原始字段**）
# ═══════════════════════════════════════════════════════════════════
def read_metrics(rec):
    """从臂目录抽 reviewer §3.2 要的数字。

    🔴 **不臆造**：文件里没有的字段一律留 `None` ＋ 记 `missing`。
    """
    out = {'missing': []}
    outdir = os.path.join(OUT_ROOT, rec['arm'])

    p = os.path.join(outdir, 'bgkeep_e2e.json')
    if os.path.isfile(p):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception as e:
            out['missing'].append('bgkeep_e2e.json 解析失败：%r' % (e,))
            d = {}
        for k in ('duration_s', 'dubs', 'bg_blocks', 'bg_late_blocks',
                  'bg_contiguous', 'bg_covered_s', 'fallback_to_orig_s',
                  'dub_late_vs_play_s', 'dub_shift_msgs', 'dub_shift_applied',
                  'bg_status_last'):
            out[k] = d.get(k)
        sf = d.get('stats_full') or {}
        out['stats_bg'] = {k: v for k, v in sf.items()
                           if k.startswith(('bg_', 'sep_'))}
        out['stats_misc'] = {k: sf.get(k) for k in
                             ('n_frames', 'n_dropped', 'proc_cpu_pct',
                              'igpu_pct', 'npu_pct', 'rss_mb')}
        # 🔴 APP-131/133：**克隆相关计数**
        out['clone_counts'] = {
            'clone_reasons': sf.get('clone_reasons'),
            'spk_reason_hist': sf.get('spk_reason_hist'),
            'n_gender_splits': sf.get('n_gender_splits'),
            'tts_nearest_voice': sf.get('tts_nearest_voice'),
            'gender_switch': sf.get('gender_switch'),
            'gender_selfref': sf.get('gender_selfref'),
        }
        out['stats_full_keys'] = sorted(sf.keys())
        # 丢句 / 自适应加速（EXT 自带口径）
        ad = sf.get('adaptive_speed') or {}
        out['n_dropped_dub'] = ad.get('n_dropped_dub')
        out['adaptive_speed'] = ad
        # 🔴 积压曲线在 `adaptive_speed.lag_curve` 里（EXT 自适应加速统计）
        lc0 = ad.get('lag_curve') or {}
        out.setdefault('lag_curve_start_sec', lc0.get('start_sec'))
        out.setdefault('lag_curve_peak_sec', lc0.get('peak_sec'))
        out.setdefault('lag_curve_end_sec', lc0.get('end_sec'))
        out.setdefault('lag_curve_peak_at_t_start', lc0.get('peak_at_t_start'))
        if out.get('dubs') is None:
            out['missing'].append('dubs')
        if out.get('n_dropped_dub') is None:
            out['missing'].append('n_dropped_dub（EXT stats_full.adaptive_speed）')
    else:
        out['missing'].append('bgkeep_e2e.json 不存在')

    # ── margin.json（synth_rtf / 语速 / 积压）──────────────────
    mp = os.path.join(outdir, 'margin.json')
    if os.path.isfile(mp):
        try:
            m = json.load(open(mp, encoding='utf-8'))
        except Exception as e:
            out['missing'].append('margin.json 解析失败：%r' % (e,))
            m = {}
        out['margin_file'] = {'path': mp,
                              'bytes': os.path.getsize(mp)}
        ms = m.get('margin_summary') or {}
        out['margin_summary'] = ms
        out['n_segments'] = ms.get('n_segments')
        out['n_negative'] = ms.get('n_negative')
        out['cumulative_lag_sec'] = ms.get('cumulative_lag_sec')
        out['peak_lag_sec'] = ms.get('peak_lag_sec')
        out['lag_p50'] = ms.get('p50')
        out['lag_p95'] = ms.get('p95')
        out['lag_max'] = ms.get('max')
        out['lag_min'] = ms.get('min')
        out['lag_mean'] = ms.get('mean')
        out['max_lag_sec'] = ms.get('max_lag_sec')
        # 🔴 逐段：语速 max / 积压
        segs = m.get('per_segment') or []
        speeds = [s.get('speed') for s in segs
                  if isinstance(s.get('speed'), (int, float))]
        out['speed_max'] = max(speeds) if speeds else None
        out['speed_n'] = len(speeds)
        adapt = [s.get('adapt_speed') for s in segs
                 if isinstance(s.get('adapt_speed'), (int, float))]
        out['adapt_speed_max'] = max(adapt) if adapt else None
        # 🔴 synth_rtf：EXT 的 `rtf_breakdown` 三个口径分列（EXT-034②）
        #   RTF_out        = TTS 自身 RTF（输出语音 vs 耗时）★ reviewer 要的 synth_rtf
        #   speech_over_src= 译文长度比
        #   tts_over_src   = 端到端占用率
        rb = m.get('rtf_breakdown') or {}
        out['rtf_breakdown'] = rb
        out['synth_rtf'] = rb.get('RTF_out')
        out['rtf_speech_over_src'] = rb.get('speech_over_src')
        out['rtf_tts_over_src'] = rb.get('tts_over_src')
        out['n_segments_with_tts'] = rb.get('n_segments_with_tts')
        # 积压：lag_decomposition / sync_rootcause
        ld = m.get('lag_decomposition') or {}
        out['lag_decomposition'] = ld
        src = m.get('sync_rootcause') or {}
        out['sync_rootcause'] = src
        # 收尾积压：lag_curve 在 `adaptive_speed` 里（EXT 的自适应加速统计）
        lc = (m.get('adaptive_speed') or {}).get('lag_curve') or {}
        out['lag_curve_end_sec'] = lc.get('end_sec')
        out['lag_curve_peak_sec'] = lc.get('peak_sec')
        out['lag_curve_start_sec'] = lc.get('start_sec')
        out['lag_curve_peak_at_t_start'] = lc.get('peak_at_t_start')
        if out.get('speed_max') is None:
            out['missing'].append('speed_max（margin.json per_segment）')
        if out.get('synth_rtf') is None:
            out['missing'].append('synth_rtf（margin.json rtf_breakdown.RTF_out）')
    else:
        out['missing'].append('margin.json 不存在（dump_margin 未成功）')
    return out


# ═══════════════════════════════════════════════════════════════════
# APP-129 §3.3 默认值检查（**纯 node 单测** ⇒ 不占设备）
# ═══════════════════════════════════════════════════════════════════
def run_defaults_check():
    """跑 `_app129_defaults_check.py`（在包内 popup.js 的**真实表达式**上执行）。

    🔴 口径（脚本自带声明）：本机**无可控的 Chrome 自动化环境** ⇒ 覆盖的是
    「存储初态 ⇒ 默认值/文案」这一层；**浏览器端 UI 交互本身由 reviewer 复核**。
    """
    p = os.path.join(HERE, '_app129_defaults_check.py')
    if not os.path.isfile(p):
        return {'ok': False, 'error': '脚本不存在：%s' % p}
    outp = os.path.join(RESULTS, 'app129_defaults_evidence.json')
    cmd = [sys.executable, p, '--pkg', PKG]
    log('默认值检查（§3.3）：%s' % ' '.join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        return {'ok': False, 'error': repr(e)}
    rec = {'rc': r.returncode, 'out': outp,
           'stdout_tail': (r.stdout or '')[-2000:]}
    try:
        d = json.load(open(outp, encoding='utf-8'))
        rec['all_ok'] = d.get('all_ok')
        rec['scenarios'] = [
            {k: s.get(k) for k in ('scenario', 'expected_bgKeep', 'got_bgKeep',
                                   'popup_display', 'ok')}
            for s in (d.get('scenarios') or [])]
        rec['popup_js_sha256'] = d.get('popup_js_sha256')
        rec['limitation'] = d.get('limitation')
        rec['ok'] = bool(d.get('all_ok'))
    except Exception as e:
        rec['ok'] = False
        rec['error'] = repr(e)
    log('默认值检查：ok=%s rc=%s' % (rec.get('ok'), rec.get('rc')))
    return rec


# ═══════════════════════════════════════════════════════════════════
# APP-129 §3.4 降级 + §3.5 抽听样片（**在同一次持锁窗口内**）
# ═══════════════════════════════════════════════════════════════════
def run_clips():
    """跑 `_app129_clips_v26.py --no-lock`（锁由整链脚本统一持）。"""
    p = os.path.join(HERE, '_app129_clips_v26.py')
    if not os.path.isfile(p):
        return {'ok': False, 'error': '脚本不存在：%s' % p}
    cmd = [sys.executable, p, '--no-lock']
    log('降级检查＋抽听样片（§3.4/§3.5）：%s' % ' '.join(cmd))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400)
    except Exception as e:
        return {'ok': False, 'error': repr(e)}
    outp = os.path.join(RESULTS, 'app129_clips_v26_evidence.json')
    rec = {'rc': r.returncode, 'stdout_tail': (r.stdout or '')[-3000:]}
    try:
        d = json.load(open(outp, encoding='utf-8'))
        rec['clips'] = d.get('clips')
        rec['degradation'] = d.get('degradation')
        rec['ok'] = (r.returncode == 0)
    except Exception as e:
        rec['ok'] = False
        rec['error'] = repr(e)
    log('降级＋抽听：rc=%s clips=%d'
        % (rec.get('rc'), len(rec.get('clips') or [])))
    return rec


# ═══════════════════════════════════════════════════════════════════
def main():
    global PORT
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', default='off,on,clone')
    ap.add_argument('--port', type=int, default=PORT)
    args = ap.parse_args()
    PORT = args.port

    if not os.path.isfile(PKG_PY):
        log('FAIL: 包内 python 不存在 %s' % PKG_PY)
        return 2
    if not os.path.isfile(MEDIA_10MIN):
        log('FAIL: 固定片段不存在 %s' % MEDIA_10MIN)
        return 3

    tool = ensure_e2e_tool()
    dump_client = make_dump_margin_client()
    os.makedirs(OUT_ROOT, exist_ok=True)

    # 🔴🔴 **一次持锁到底**（APP-132）：原子创建 ＋ 全程不删
    lk = MachineLock('app bgkeep v2.6 chain (APP-132 一次持锁到底)')
    log('等机器锁（原子创建；不抢别人的）…')
    if not lk.acquire(timeout_s=7200):
        log('🔴 拿不到机器锁 ⇒ 本轮结束（不做任何测量）')
        return 4
    log('已持机器锁：%s' % lk.content)

    ev_path = os.path.join(RESULTS, 'app133_chain_v26_evidence.json')
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': PKG, 'ext_commit': EXT_COMMIT,
           'lock': {'note': lk.note, 'started': lk.started},
           'arms': []}
    try:
        for a in args.arms.split(','):
            a = a.strip()
            if not a:
                continue
            for _k in range(120):
                if ports_free():
                    break
                time.sleep(5)
            if a == 'clone':
                rec = run_arm('bgkeep_clone', False, MEDIA_10MIN, tool,
                              dump_client, voice='clone')
            elif a == 'off_nb':
                rec = run_arm('bgkeep_off_nb', True, MEDIA_10MIN, tool,
                              dump_client, spk_bypass=False)
            else:
                rec = run_arm('bgkeep_%s' % a, (a == 'off'), MEDIA_10MIN,
                              tool, dump_client)
            rec['metrics'] = read_metrics(rec)
            # 🔴 **当场复核持锁**（APP-132）：被抢过 ⇒ 该臂计时作废
            rec['lock_held_after_arm'] = lk.check()
            rec['lock_lost_overall'] = lk.lost
            if lk.lost:
                rec['timing_valid'] = False
                rec['timing_invalid_why'] = (
                    '持锁期间锁被抢/被删 ⇒ 计时作废（APP-132）')
            else:
                rec['timing_valid'] = True
            rep['arms'].append(rec)
            with open(ev_path, 'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)

        # ── 🔴 APP-132：**默认值检查（§3.3）＋ 降级（§3.4）＋ 抽听（§3.5）**
        #    也**在同一次持锁窗口内**跑完（reviewer 明文：「整条链（所有臂、
        #    默认值检查、抽听样片）一次持锁到底」）
        #    ⇒ 抽听脚本用 `--no-lock`（否则它会**再取一次**锁 ⇒ 死等自己）
        rep['defaults_check'] = run_defaults_check()
        rep['lock_held_after_defaults'] = lk.check()
        rep['clips'] = run_clips()
        rep['lock_held_after_clips'] = lk.check()
    finally:
        rep['lock']['ended'] = lk.ended or datetime.datetime.now().strftime(
            '%Y-%m-%d %H:%M:%S')
        rep['lock']['lost'] = lk.lost
        with open(ev_path, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        lk.release()
    log('证据：%s' % ev_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
