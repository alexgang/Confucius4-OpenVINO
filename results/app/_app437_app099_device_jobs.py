#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app437_app099_device_jobs.py — APP-099 第 4 节 1/2 的设备作业（持 MACHINE_LOCK）。

## 本脚本要修掉的两个「假 PASS」
APP-099 §2a：rc6 六臂冒烟有 3 臂无效
  · mt_npu 臂没给 --tts-device ⇒ TTS 默认 NPU ⇒ 触发 APP-063「MT+TTS 同 NPU
    ⇒ MT 自动改到 GPU.0」⇒ MT·NPU 从来没有跑过；
  · tts_gpu / tts_npu 两臂没带 --translate ⇒ 没有译文送进 TTS ⇒ 提交 0 播完 0；
  · has_output 只看 ASR 文本 ⇒ 六臂都是同一份 418 B 英文转写。
⇒ 本脚本：MT 两臂显式 ``--tts off --tts-device GPU.0``；TTS 两臂显式
  ``--translate zh``；**按组件分开判定**，且日志出现「自动改到」即 FAIL。

## APP-098 §2.5 / APP-099 §4.2：A 机 GPU 同占复现
  · 臂 A：ASR gpu_int8 + MT GPU.0 + TTS NPU + --translate zh；
  · 对照臂 B：ASR NPU + MT GPU.0 + TTS NPU + --translate zh。
  · 每 2 s 采样 \GPU Process Memory(*)\Dedicated Usage / Shared Usage
    和被测进程工作集；报峰值、是否崩溃、崩溃时刻。

## APP-100（10:38 追加）长跑口径
「已下发、还没做完的纠偏（例如 APP-099）里的长跑，也按本条执行」。
🔴 **2026-11-11 13:5x 修正（§176）**：本脚本原先写的
「本机只有 ``SPE_0000_0500.wav``（300.0 s），无法直接取 0–600 s 原始片段
⇒ 改为 0–300 s 播 2 次」——**该前提经实测证伪**：
  · 全长 SPE 素材 **3671.189 s** 一直在本仓库 ``test_audio/260902_SPE_audio.wav``；
    ``shared/SPE_0000_0500.wav`` 只是它的**前 300 s 截断拷贝**（SHA256 实测相同）；
  · ASR 侧 canonical clip ``clip_10min_0_600.wav`` 实测 mtime **10:52:30**，
    比本作业开工（11:32:08）**早 40 分钟** ⇒ 当时就能拿到。
⇒ 现改为 APP-100 的 canonical 片段：**SPE 0.0–600.0 s 连续（不循环）**，
  起止秒 + payload/file SHA256 写进本脚本与结果 json（``_app455_app100_segment.py``
  是唯一事实来源）。

## 纪律
* 只用 ``machine_lock_app.acquire/release``（fail-closed、PID 判活、排队）；
* 不调 MiniMax；不打 rc8 / v2.5；不改任何默认值或判据；
* 每段持锁 ≤ 60 min（本脚本总时限 55 min）；
* 计时 json 里写锁记录（module/PID/起止）和 ``timing_valid``。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
import machine_lock_app as ML  # noqa: E402

OUTROOT = os.path.join(HERE, 'app437_app099_device')
REPORT = os.path.join(HERE, 'app437_app099_device.json')
SMOKE_AUDIO = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\smoke30.wav'
#: 🔴 APP-100 canonical 10 分钟片段（**唯一事实来源** ⇒ _app455_app100_segment.py）
sys.path.insert(0, HERE)
import _app455_app100_segment as SEG  # noqa: E402

LONG_AUDIO = SEG.CLIP_WAV
LONG_SEG_START_S = SEG.START_S            # 0.0
LONG_SEG_END_S = SEG.END_S                # 600.0
LONG_LOOPS = 1                            # **连续，不循环**（APP-100）
LONG_TIMELINE_S = (LONG_SEG_END_S - LONG_SEG_START_S) * LONG_LOOPS   # 600.0 s
SAMPLE_INTERVAL_S = 2.0
TOTAL_BUDGET_S = 55 * 60
#: 🔴 单臂 harness 超时（秒）。
#: §175 用的是 **1500 s** ⇒ 🔴 **B 臂被误杀**：实测 B 臂 ASR **已完成**
#:   （`[npu_int8] 音频 600.4s 墙钟 610.8s RTF 0.931 段 92` ⇒ 与 A 臂**同段数 92**），
#:   进程是在 **TTS drain 阶段**（146 句过期丢弃）拖到 1500 s 才被 harness 强杀
#:   ⇒ rc=-9 **不是**被测程序崩溃，也不是 ASR 没跑完。
#: ⇒ 提到 2700 s（45 min）：给 TTS drain 留够时间，同时 < TOTAL_BUDGET_S(55 min)。
ARM_TIMEOUT_S = 2700

#: 🔴 模块租约（APP-056）：长作业必须 addpid + 定期 beat
#:   否则 >30 min 没有 beat ⇒ 被视为死会话。
LEASE_PY = r'C:\Users\Trekker-PTL\shared\tools\session_lease.py'
LEASE_MOD = 'app'
#: token 由环境变量传入（不同轮次不同 token ⇒ 不能写死在脚本里）
LEASE_TOKEN = os.environ.get('LIVECAP_LEASE_TOKEN', '')


def _lease(argv):
    try:
        return subprocess.run([sys.executable, LEASE_PY] + list(argv),
                              capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception as e:
        return 'ERR %r' % e


_beat_stop = threading.Event()


def _start_lease_beat():
    def loop():
        while not _beat_stop.wait(300):     # 每 5 min
            print('[lease] %s' % _lease(
                ['beat', LEASE_MOD, LEASE_TOKEN,
                 'APP-099 设备作业持锁运行中']), flush=True)
    threading.Thread(target=loop, daemon=True).start()

#: APP-099 §4.1 六臂（在 rc6 六臂基础上补 --tts off / --translate）
ARMS = (
    ('asr_gpu', '--engine', 'gpu_int8', '--asr-device', 'GPU.0'),
    ('asr_npu', '--engine', 'npu_int8', '--asr-device', 'NPU'),
    # MT 两臂：显式关 TTS 且把 TTS 设备指到 GPU.0 ⇒ 不触发「自动改到」
    ('mt_gpu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--mt-device', 'GPU.0',
     '--tts', 'off', '--tts-device', 'GPU.0'),
    ('mt_npu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--mt-device', 'NPU',
     '--tts', 'off', '--tts-device', 'GPU.0'),
    # TTS 两臂：必须带 --translate，否则 0 句合成
    ('tts_gpu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A',
     '--tts-device', 'GPU.0'),
    ('tts_npu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A',
     '--tts-device', 'NPU'),
)

#: APP-099 §4.2 两臂（同一段固定 300 s ×2）
GPU_ARMS = (
    ('gpu_same_asr_mt', '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
     '--mt-device', 'GPU.0', '--tts-device', 'NPU',
     '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A'),
    ('gpu_control_asr_npu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--mt-device', 'GPU.0', '--tts-device', 'NPU',
     '--translate', 'zh', '--tts', 'on', '--tts-voice', 'A'),
)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── GPU / 内存采样（win32pdh，同进程，不每 2 s 起新进程）────────────────
def _pdh_sum(counter_name):
    import win32pdh
    path = r'\GPU Process Memory(*)\%s' % counter_name
    q = win32pdh.OpenQuery()
    try:
        hs = win32pdh.AddCounter(q, path)
        if not isinstance(hs, (list, tuple)):
            hs = [hs]
        win32pdh.CollectQueryData(q)
        time.sleep(0.05)
        win32pdh.CollectQueryData(q)
        total, n = 0.0, len(hs)
        for h in hs:
            try:
                _typ, val = win32pdh.GetFormattedCounterValue(
                    h, win32pdh.PDH_FMT_LARGE)
                total += float(val)
            except Exception:
                pass
        return total, n
    except Exception:
        return None, 0
    finally:
        try:
            win32pdh.CloseQuery(q)
        except Exception:
            pass


class Sampler:
    def __init__(self, get_pid, interval=SAMPLE_INTERVAL_S):
        self.get_pid = get_pid
        self.interval = interval
        self.rows = []
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True)
        self.t0 = None
        #: 🔴 §176：采样线程自己的失败（import 失败 / 其它异常）⇒ 判据可见
        self.error = None

    def _run(self):
        # 🔴 §176：采样线程**必须能报告自己的失败**。
        #   §175 的写法（`import psutil` 直接写在循环里）在本机系统 Python 上
        #   抛 ModuleNotFoundError ⇒ **线程静默死掉** ⇒ 采样行数为 0，
        #   而主流程照样往下跑 ⇒ 显存/RSS 峰值**悄悄丢失**。
        #   ⇒ 改成：import 失败就**记进 self.error 并停止采样**，
        #      且 `summary()` 把它带出来 ⇒ 判据能看见「没采到」。
        try:
            import psutil
        except Exception as e:
            self.error = 'psutil import failed: %r' % (e,)
            return
        while not self._stop.is_set():
            t = round(time.perf_counter() - self.t0, 2)
            ded, n1 = _pdh_sum('Dedicated Usage')
            sha, n2 = _pdh_sum('Shared Usage')
            rss = None
            pid = self.get_pid()
            if pid:
                try:
                    pr = psutil.Process(pid)
                    rss = sum(c.memory_info().rss for c in [pr] + pr.children(recursive=True))
                except Exception:
                    pass
            self.rows.append({'t_s': t, 'wall': now(),
                              'gpu_dedicated_bytes': ded,
                              'gpu_shared_bytes': sha,
                              'n_gpu_instances': max(n1, n2),
                              'proc_rss_bytes': rss})
            self._stop.wait(self.interval)

    def start(self):
        self.t0 = time.perf_counter()
        self._th.start()

    def stop(self):
        self._stop.set()
        self._th.join(timeout=10)

    def summary(self):
        def peak(k):
            vals = [r[k] for r in self.rows if r.get(k) is not None]
            return max(vals) if vals else None
        return {'n_samples': len(self.rows),
                'interval_s': self.interval,
                # 🔴 §176：采样线程失败 ⇒ 显式带出来（n_samples=0 时判据看得见）
                'sampler_error': self.error,
                'sampling_ok': (self.error is None and len(self.rows) > 0),
                'peak_gpu_dedicated_bytes': peak('gpu_dedicated_bytes'),
                'peak_gpu_shared_bytes': peak('gpu_shared_bytes'),
                'peak_proc_rss_bytes': peak('proc_rss_bytes'),
                'peak_gpu_dedicated_mb': (round(peak('gpu_dedicated_bytes') / 2 ** 20, 1)
                                          if peak('gpu_dedicated_bytes') is not None else None),
                'peak_gpu_shared_mb': (round(peak('gpu_shared_bytes') / 2 ** 20, 1)
                                       if peak('gpu_shared_bytes') is not None else None),
                'peak_proc_rss_mb': (round(peak('proc_rss_bytes') / 2 ** 20, 1)
                                     if peak('proc_rss_bytes') is not None else None)}


def read_txt(p):
    try:
        return open(p, 'r', encoding='utf-8', errors='replace').read().strip()
    except Exception:
        return ''


def judge_arm(name, opts, txt, log_path, out_path, wav_path, expect_dev):
    """APP-099 §4.1：**按组件分开判定**（不再只看 ASR 文本）。"""
    base = os.path.splitext(out_path)[0]
    mt_path = base + '.mt.txt'
    mt_txt = read_txt(mt_path)
    sub_txt = read_txt(out_path)
    exec_lines = [l.strip() for l in txt.splitlines() if 'EXECUTION_DEVICES' in l]
    rec = {
        'arm': name, 'opts': list(opts), 'log_path': log_path,
        'exit_code': None, 'seconds': None, 'log_bytes': len(txt.encode('utf-8', 'replace')),
        'n_exec_devices_lines': len(exec_lines), 'exec_devices_lines': exec_lines[:8],
        'auto_redirect': ('自动改到' in txt),
        'asr': {'text_chars': len(sub_txt), 'nonempty': bool(sub_txt),
                'exec_devices_present': bool(exec_lines), 'path': out_path},
        'mt': {'path': mt_path, 'text_chars': len(mt_txt), 'nonempty': bool(mt_txt),
               'differs_from_src': bool(mt_txt and mt_txt != sub_txt),
               'ready_lines': [],
               'requested_device': None, 'observed_device': None},
        'tts': {'wav_path': wav_path, 'wav_seconds': None,
                'n_submit': None, 'n_played': None},
        'checks': {}, 'pass': False,
    }
    # MT：日志里的「加载翻译模型（X）」/「翻译模型就绪 … · X」
    loads = re.findall(r'加载翻译模型[（(]\s*([^）)]+)\s*[）)]', txt)
    ready = [l.strip() for l in txt.splitlines() if '翻译模型就绪' in l]
    rec['mt']['load_lines'] = loads
    rec['mt']['ready_lines'] = ready[:4]
    devs = []
    for s in loads + ready:
        devs += re.findall(r'\b(?:GPU\.0|GPU\.1|NPU|CPU|CUDA)\b', s)
    rec['mt']['observed_device'] = devs[0] if devs else None
    for i, o in enumerate(opts):
        if o == '--mt-device':
            rec['mt']['requested_device'] = opts[i + 1]
    # TTS：提交/播完 + wav 时长
    ns = [int(x) for x in re.findall(r'提交[^0-9\n]{0,12}(\d+)', txt)]
    np = [int(x) for x in re.findall(r'播完[^0-9\n]{0,12}(\d+)', txt)]
    rec['tts']['n_submit'] = max(ns) if ns else None
    rec['tts']['n_played'] = max(np) if np else None
    if wav_path and os.path.isfile(wav_path):
        try:
            import soundfile as sf
            rec['tts']['wav_seconds'] = round(float(sf.info(wav_path).duration), 3)
        except Exception as e:
            rec['tts']['wav_error'] = repr(e)
    # 组件判定
    c = rec['checks']
    c['no_auto_redirect'] = not rec['auto_redirect']
    c['asr_nonempty'] = rec['asr']['nonempty']
    c['asr_exec_devices'] = rec['asr']['exec_devices_present']
    if name.startswith('mt_'):
        c['mt_nonempty'] = rec['mt']['nonempty']
        c['mt_differs'] = rec['mt']['differs_from_src']
        c['mt_on_requested_device'] = (
            rec['mt']['observed_device'] is not None and
            rec['mt']['requested_device'] is not None and
            rec['mt']['observed_device'].upper() == rec['mt']['requested_device'].upper())
    if name.startswith('tts_'):
        c['tts_submitted'] = bool(rec['tts']['n_submit'] and rec['tts']['n_submit'] > 0)
        c['tts_played'] = bool(rec['tts']['n_played'] and rec['tts']['n_played'] > 0)
        c['tts_wav_nonzero'] = bool(rec['tts']['wav_seconds'] and rec['tts']['wav_seconds'] > 0)
        c['tts_exec_devices'] = any('decoder=' in l or 'talker=' in l for l in exec_lines)
    rec['pass'] = all(c.values())
    return rec


def run_one(py, app, pkg, name, opts, audio, seconds, outroot,
            wav=False, loop=False, sampler=None):
    out_path = os.path.join(outroot, name + '.txt')
    log_path = os.path.join(outroot, name + '.log')
    wav_path = os.path.join(outroot, name + '.wav') if wav else None
    cmd = [py, '-s', app, '--cli', '--file', audio,
           '--max-seconds', str(seconds), '--out', out_path] + list(opts)
    if loop:
        cmd.append('--loop')
    if wav_path:
        cmd += ['--tts-out', wav_path]
    t0 = time.time()
    proc_holder = {}
    with open(log_path, 'wb') as lf:
        p = subprocess.Popen(cmd, cwd=pkg, stdout=lf, stderr=subprocess.STDOUT)
        proc_holder['pid'] = p.pid
        if sampler:
            sampler.get_pid = lambda: proc_holder.get('pid')
            sampler.start()
        try:
            rc = p.wait(timeout=ARM_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            p.kill(); rc = -9
    if sampler:
        sampler.stop()
    txt = read_txt(log_path)
    rec = judge_arm(name, opts, txt, log_path, out_path, wav_path, None)
    rec['exit_code'] = rc
    rec['seconds'] = round(time.time() - t0, 1)
    rec['cmd'] = cmd
    # 🔴 APP-099 判据修正：rc=-9 是本脚本 wait(timeout=1500) 后 p.kill()
    #    造成的「被测试框架强杀」，不是被测程序自己崩溃；两者必须分开记账。
    rec['pass_components_only'] = rec['pass']
    rec['terminated_by_harness'] = (rc == -9)
    rec['crash'] = (rc != 0 and rc != -9)
    rec['crash_at_s'] = rec['seconds'] if rec['crash'] else None
    rec['natural_exit'] = (rc == 0)
    # 🔴 组件 checks 全过 ≠ 该臂有效：非自然退出的臂一律不判 PASS
    rec['pass'] = bool(rec['pass'] and rc == 0)
    if sampler:
        rec['sampling'] = sampler.summary()
        rec['sampling']['rows_path'] = os.path.join(outroot, name + '_samples.jsonl')
        with open(rec['sampling']['rows_path'], 'w', encoding='utf-8') as f:
            for r in sampler.rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc7')
    ap.add_argument('--part', default='both', choices=['both', 'smoke', 'gpu'])
    ap.add_argument('--smoke-seconds', type=float, default=60.0)
    ap.add_argument('--long-seconds', type=float, default=LONG_TIMELINE_S)
    ap.add_argument('--no-lock', action='store_true')
    # 🔴 §176：产物目录/报告文件**可指定** ⇒ 重跑不覆盖 §175 的既有证据
    ap.add_argument('--outroot', default=OUTROOT)
    ap.add_argument('--report', default=REPORT)
    # 🔴 §177：**只跑指定臂**（逗号分隔）⇒ 补跑单臂时不重跑已完成的臂
    #    （A 臂已完成且自然退出 ⇒ 不重复消耗设备时间；B 臂单独重跑做对照）
    ap.add_argument('--only-arm', default='')
    args = ap.parse_args()
    only = [x.strip() for x in (args.only_arm or '').split(',') if x.strip()]
    # 🔴🔴🔴 §177：**产物目录必须转绝对路径**。
    #   本轮实测事故：`--outroot results/app/xxx`（相对路径）⇒
    #   被测程序以 `cwd=pkg` 运行 ⇒ `--out` / `--tts-out` 落进
    #   **rc7 包目录内**（`rc7/results/app/xxx/`）⇒
    #   ① 证据散落在客户包里（污染交付包）；
    #   ② 判据读 `out_path`（相对仓库根）读不到 ⇒ `asr_nonempty=False`
    #      ⇒ **假 FAIL**。
    # ⇒ 强制 `os.path.abspath` ⇒ 无论 cwd 在哪，产物都落回指定的证据目录。
    outroot = os.path.abspath(args.outroot)
    report = os.path.abspath(args.report)
    os.makedirs(outroot, exist_ok=True)
    py = os.path.join(args.pkg, 'python', 'python.exe')
    app = os.path.join(args.pkg, 'app', 'live_caption_app.py')
    for p in (py, app, SMOKE_AUDIO, LONG_AUDIO):
        if not os.path.isfile(p):
            print('!! 缺文件：%s' % p)
            return 2

    ev = {
        'task': 'APP-099 第 4 节 1/2：rc7 六臂冒烟 + A 机 GPU 同占复现',
        'created_at': now(), 'pkg': args.pkg,
        # 🔴 APP-100：片段口径的**完整**元信息（含 SHA256）写进结果 json
        'app100_segment': dict(SEG.segment_meta(LONG_AUDIO),
                               timeline_s=args.long_seconds),
        'smoke_seconds': args.smoke_seconds,
        'only_arm': only,
        'arms': [], 'gpu_arms': [], 'verdict': 'PENDING',
    }

    # ── 锁（fail-closed、排队、PID 判活）──────────────────────────────
    payload = None
    if not args.no_lock:
        ok, payload = ML.acquire(module='app', timeout=3600, poll=20.0)
        if not ok:
            ev['verdict'] = 'SKIPPED_LOCK_BUSY'
            ev['lock'] = {'error': str(payload)}
            json.dump(ev, open(report, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
            print('🔴 拿不到 MACHINE_LOCK ⇒ 不跑设备作业')
            return 1
        ev['lock'] = {'module': 'app', 'pid': os.getpid(),
                      'started': now(), 'payload': payload,
                      'ended': None, 'host': os.environ.get('COMPUTERNAME')}
        print('[lock] 已获取 %s' % payload)
    # 🔴 不预先写死 True；收尾按各臂 exit_code 重算，非自然退出臂 ⇒ timing_valid=False
    ev['timing_valid'] = None
    ev['timing_notes'] = []
    ev['lease'] = {
        'addpid': _lease(['addpid', LEASE_MOD, LEASE_TOKEN, str(os.getpid())]),
        'beat_interval_s': 300,
    }
    _start_lease_beat()

    t_start = time.time()
    try:
        if args.part in ('both', 'smoke'):
            print('=== 六臂冒烟（%s s / 臂）===' % args.smoke_seconds)
            for name, *opts in ARMS:
                if only and name not in only:
                    continue
                if time.time() - t_start > TOTAL_BUDGET_S:
                    ev['timing_notes'].append('总时限 55 min 到 ⇒ 提前停止')
                    break
                print('[arm] %s %s' % (name, ' '.join(opts)), flush=True)
                rec = run_one(py, app, args.pkg, name, opts, SMOKE_AUDIO,
                              args.smoke_seconds, outroot,
                              wav=name.startswith('tts_'), loop=True)
                ev['arms'].append(rec)
                print('   exit=%s %ss pass=%s checks=%s' % (
                    rec['exit_code'], rec['seconds'], rec['pass'],
                    rec['checks']), flush=True)
                json.dump(ev, open(report, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)

        if args.part in ('both', 'gpu'):
            print('=== A 机 GPU 同占复现（%s s 音频时间线 / 臂）===' % args.long_seconds)
            for name, *opts in GPU_ARMS:
                if only and name not in only:
                    continue
                if time.time() - t_start > TOTAL_BUDGET_S:
                    ev['timing_notes'].append('总时限 55 min 到 ⇒ 提前停止')
                    break
                print('[gpu-arm] %s %s' % (name, ' '.join(opts)), flush=True)
                s = Sampler(lambda: None)
                # 🔴 APP-100：canonical 片段 = **0–600 s 连续**（文件恰好 600.0 s）
                #    ⇒ **不需要 --loop**（加了会在 600 s 边界回卷第二遍，污染尾端）。
                #    仅当素材短于目标时长才循环。
                _need_loop = SEG.wav_info(LONG_AUDIO)['duration_s'] < args.long_seconds
                rec = run_one(py, app, args.pkg, name, opts, LONG_AUDIO,
                              args.long_seconds, outroot,
                              wav=True, loop=_need_loop, sampler=s)
                rec['app100_segment'] = ev['app100_segment']
                ev['gpu_arms'].append(rec)
                print('   exit=%s %ss crash=%s peak_ded_mb=%s pass=%s' % (
                    rec['exit_code'], rec['seconds'], rec['crash'],
                    rec['sampling']['peak_gpu_dedicated_mb'], rec['pass']), flush=True)
                json.dump(ev, open(report, 'w', encoding='utf-8'),
                          ensure_ascii=False, indent=1)
    finally:
        if payload is not None:
            ev['lock']['ended'] = now()
            try:
                ML.release(payload)
                ev['lock']['released'] = True
                print('[lock] 已释放')
            except Exception as e:
                ev['lock']['released'] = False
                ev['lock']['release_error'] = repr(e)
        ev['elapsed_s'] = round(time.time() - t_start, 1)
        all_arms = ev['arms'] + ev['gpu_arms']
        ok_arms = sum(1 for a in ev['arms'] if a['pass'] and a['exit_code'] == 0)
        ok_gpu = sum(1 for a in ev['gpu_arms'] if a['pass'] and a['exit_code'] == 0)
        ev['n_arms'] = len(ev['arms'])
        ev['n_arms_ok'] = ok_arms
        ev['n_gpu_arms'] = len(ev['gpu_arms'])
        ev['n_gpu_arms_ok'] = ok_gpu
        # 🔴 计时可比性：任一臂非自然退出 ⇒ 该臂与其余臂不可比
        non_natural = [a['arm'] for a in all_arms if a['exit_code'] != 0]
        ev['timing_valid'] = (len(non_natural) == 0)
        if non_natural:
            ev['timing_notes'].append(
                '非自然退出臂：%s ⇒ 这些臂的计时/显存曲线不可与自然退出臂对比'
                % ', '.join(non_natural))
        # 🔴 verdict 必须纳入 GPU 臂的退出状态，不能只数「臂数」
        # 🔴 §177：**期望臂数按本轮实际要跑的臂算** ⇒ 否则会**假阴性**：
        #    ① `--part gpu`（只跑 GPU 两臂）⇒ smoke 臂根本没跑 ⇒ 旧硬编码 6/2
        #       会把「两臂全绿」判成 PARTIAL；
        #    ② `--only-arm <单臂>`（补跑一臂）⇒ 同上。
        #    ⇒ 期望臂数 = 本轮**真的要跑**的臂数（受 --part 与 --only-arm 双重约束）。
        _smoke_ran = args.part in ('both', 'smoke')
        _gpu_ran = args.part in ('both', 'gpu')
        # 🔴🔴 臂元组是 `(name, *opts)` ⇒ **长度不定** ⇒ 解包必须写 `n, *_`
        #    （写 `n, _` ⇒ 「too many values to unpack」⇒ 收尾 json 写不出来）
        want_smoke = ([n for n, *_ in ARMS if not only or n in only]
                      if _smoke_ran else [])
        want_gpu = ([n for n, *_ in GPU_ARMS if not only or n in only]
                    if _gpu_ran else [])
        ev['want_arms'] = len(want_smoke)
        ev['want_gpu_arms'] = len(want_gpu)
        ev['want_arm_names'] = want_smoke + want_gpu
        ev['verdict'] = ('PASS' if ev['n_arms'] == len(want_smoke)
                         and ok_arms == len(want_smoke)
                         and ev['n_gpu_arms'] == len(want_gpu)
                         and ok_gpu == len(want_gpu)
                         and ev['timing_valid'] else 'PARTIAL')
        json.dump(ev, open(report, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    print('[done] verdict=%s arms=%d/%d gpu=%d elapsed=%ss' % (
        ev['verdict'], ok_arms, ev['n_arms'], ev['n_gpu_arms'], ev['elapsed_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
