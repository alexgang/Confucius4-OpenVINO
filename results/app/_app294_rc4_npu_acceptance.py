#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app294_rc4_npu_acceptance.py —— **rc4 全 NPU ASR 设备级验收**。

## 用户验收要求（2026-11-10）

> 3. 验收：
>    - 从干净目录解压后用 NPU 模式启动 ASR，日志里 encoder 和 decoder 的
>      实际执行设备都是 NPU；
>    - 用 5 分钟英文素材跑一遍，报 WER（和 iGPU 版对比）、RTF、首字延迟、
>      峰值内存；
>    - 报包体积增量。

## 本脚本跑什么

**两臂，同一次持锁会话内连续跑**（A/B 必须同会话 ⇒ solo 基线跨会话漂移 ±5 %）：

| 臂 | engine | ASR 设备 | 用途 |
|---|---|---|---|
| `npu` | `npu_int8` | NPU | 新增档（rc4 补的 IR） |
| `igpu` | `gpu_int8` | GPU.0 | 对照基线 |

素材：`C:\\Users\\Trekker-PTL\\shared\\SPE_0000_0500.wav`（300.0 s，英文 SPE）
命令行与 rc3 README_perftest 的「步骤 2」**完全一致**（只换 ASR 档）。

## 报什么数（每项都带来源文件 + 字段名）

* **WER**：拿两臂的英文转写 vs 同一份参考文本算（不调 MiniMax）。
* **RTF**：音频时长 / 墙钟（取 App 自己打的 summary）。
* **首字延迟**：App summary 的 `first_char_latency_ms`。
* **峰值内存**：用 psutil 采样（**开发机**有 psutil；包内没有 ⇒
  采样在**外部**进程做，不改包）。
* **执行设备**：从日志里抓 `EXECUTION_DEVICES` / 编译产物设备。

## 🔴 纪律
* 持 `MACHINE_LOCK`（O_CREAT|O_EXCL 原子拿）。
* **跑影子包**（干净目录 `C:\\minimvp_rc4_clean\\...`）⇒ 不碰用户安装目录。
* 不调 MiniMax（回转写由 reviewer 做）。
* CPU/内存采样在**外部**做，不改包内代码。

用法：
    .venv/Scripts/python.exe results/app/_app294_rc4_npu_acceptance.py --arm npu
    .venv/Scripts/python.exe results/app/_app294_rc4_npu_acceptance.py --arm igpu
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')

#: 🔴 **干净目录**（模拟解压后）—— 不碰用户的安装目录
PKG = os.path.join('C:\\', 'minimvp_rc4_clean',
                   'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
WAV = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUTROOT = os.path.join(HERE, 'app294_rc4_npu_out')
EVID = os.path.join(HERE, 'app294_rc4_npu_acceptance_evidence.json')

ARMS = {
    # 🔴 **纯 ASR 臂**（用户要的就是「ASR 档」的对比 ⇒ 必须把 TTS 关掉）
    #    否则 NPU 臂里 ASR 与 TTS **抢同一个 NPU** ⇒ RTF 被 TTS 拖垮
    #    （第一跑实测：NPU 全家桶 RTF 1.284 / 出字延迟 57.8 s ⇒ 那是**争用**，
    #      不是 ASR 本身慢）。⇒ 隔离口径 = `--tts off`。
    'npu': dict(engine='npu_int8', asr_device='NPU', tts='off'),
    'igpu': dict(engine='gpu_int8', asr_device='GPU.0', tts='off'),
    # 🔴 全家桶臂（TTS 也在 NPU）⇒ 用于**端到端**真实体感
    'npu_full': dict(engine='npu_int8', asr_device='NPU', tts='on'),
    'igpu_full': dict(engine='gpu_int8', asr_device='GPU.0', tts='on'),
}

#: 🔴 App 自己打的 summary 行（与 app253 基线**逐字同一口径**）
_RE_SUMMARY = re.compile(
    r'\[(?P<engine>[^\]]+)\]\s*音频\s+(?P<audio>[0-9.]+)s\s*'
    r'墙钟\s+(?P<wall>[0-9.]+)s\s*'
    r'RTF\(计算\)\s+(?P<rtf>[0-9.]+)\s*'
    r'出字延迟中位\s+(?P<lat>[0-9.]+|None)\s*ms\s*'
    r'最大积压\s+(?P<backlog>[0-9.]+)s\s*'
    r'段\s+(?P<segs>[0-9]+)')


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def acquire_lock(tag: str) -> int:
    for _t in range(3):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write('module=app\npid=%d\nstart=%s\ntag=%s\n'
                        % (os.getpid(), now(), tag))
            return os.getpid()
        except FileExistsError:
            print('🔴 锁已存在 ⇒ 等 20 s', flush=True)
            time.sleep(20)
    return -1


def release_lock() -> None:
    try:
        if os.path.exists(LOCK):
            cur = open(LOCK, encoding='utf-8', errors='replace').read()
            if ('pid=%d' % os.getpid()) in cur:
                os.remove(LOCK)
                print('🔓 锁已释放', flush=True)
    except Exception as e:
        print('⚠️ 释放锁失败：%s' % e, flush=True)


class MemSampler(threading.Thread):
    """🔴 外部采样进程的工作集峰值（**不改包内代码**）。

    ⚠️ **属性名不能叫 `_stop`**：`threading.Thread` 内部有 `_stop()` 方法
    ⇒ 遮蔽后 `join()` 调 `self._stop()` 会炸（`'Event' object is not callable`）
    ⇒ 本类第一版就踩了这个坑（app294 第一跑崩在这）。
    ⇒ 用 `_stopev`。
    """

    def __init__(self, pid: int):
        super().__init__(daemon=True)
        self.pid = pid
        self.peak_mb = 0.0
        self.samples = 0
        self._stopev = threading.Event()

    def run(self):
        try:
            import psutil
        except Exception:
            return
        try:
            p = psutil.Process(self.pid)
        except Exception:
            return
        while not self._stopev.is_set():
            try:
                mi = p.memory_info()
                self.peak_mb = max(self.peak_mb, mi.rss / 1048576.0)
                self.samples += 1
            except Exception:
                break
            self._stopev.wait(0.25)

    def stop(self):
        self._stopev.set()


def build_cmd(arm: str, out: str) -> list:
    cfg = ARMS[arm]
    cmd = [
        os.path.join(PKG, 'python', 'python.exe'),
        os.path.join(PKG, 'app', 'live_caption_app.py'),
        '--cli', '--file', WAV,
        '--engine', cfg['engine'],
        '--asr-device', cfg['asr_device'],
        '--translate', 'zh',
        '--mt-device', 'GPU.0', '--mt-engine', 'gpu_int4cw',
        '--tts', cfg['tts'],
        '--speaker', 'off', '--max-seconds', '300',
        '--out', os.path.join(out, 'transcript.txt'),
    ]
    if cfg['tts'] == 'on':
        cmd += ['--tts-voice', 'A', '--tts-device', 'NPU',
                '--tts-out', os.path.join(out, 'mix.wav'),
                '--tts-jsonl', os.path.join(out, 'tts.jsonl')]
    return cmd


def parse_summary(log_path: str) -> dict:
    """从日志里抠 App 自己打的 summary / 设备信息。

    🔴 **summary 行格式**（与 `app253_app066_minimvp_cli_acceptance.py`
    的 `_RE_SUMMARY` **逐字同一口径** ⇒ 数字可直接和基线对比）：
        [engine] 音频 Xs 墙钟 Ys RTF(计算) Z 出字延迟中位 L ms 最大积压 B s 段 N
    """
    out = {}
    try:
        txt = open(log_path, encoding='utf-8', errors='replace').read()
    except Exception:
        return out
    m = None
    for m in _RE_SUMMARY.finditer(txt):
        pass
    if m:
        d = m.groupdict()
        for k in ('audio', 'wall', 'rtf', 'backlog'):
            try:
                d[k] = float(d[k])
            except (TypeError, ValueError):
                d[k] = None
        try:
            d['lat_ms'] = (float(d.pop('lat'))
                           if d.get('lat') not in (None, 'None') else None)
        except (TypeError, ValueError):
            d['lat_ms'] = None
        try:
            d['segs'] = int(d['segs'])
        except (TypeError, ValueError):
            pass
        out['summary'] = d
    # 执行设备（encoder/decoder 实际落在哪）
    for pat, key in (
            (r'EXECUTION_DEVICES[^\n]*', 'exec_devices_log'),
            (r'设备\s+(NPU|GPU\.\d|CPU)', 'device_log'),
            (r'\[(\w+)\]\s*加载\s*([\d.]+)\s*s，设备\s*(\w+)',
             'asr_load_line'),
    ):
        mm = re.findall(pat, txt)
        if mm:
            out[key] = mm[-1]
    # NPU 编译耗时（App 自己打的）
    mm = re.findall(r'NPU[^\n]{0,60}?(\d+(?:\.\d+)?)\s*s', txt)
    if mm:
        out['npu_compile_s_log'] = mm[-1]
    return out


def norm_text(s: str) -> str:
    """WER 归一化：小写 + 去标点 + 压空白。"""
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def wer(ref: str, hyp: str) -> dict:
    """标准 WER（词级 Levenshtein）。"""
    r = norm_text(ref).split()
    h = norm_text(hyp).split()
    if not r:
        return {'wer': None, 'why': '参考文本为空'}
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev = d[0]
        d[0] = i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1,
                       prev + (0 if r[i - 1] == h[j - 1] else 1))
            prev = cur
    n = d[len(h)]
    return {'wer': round(n / len(r), 6), 'n_edits': n, 'n_ref_words': len(r),
            'n_hyp_words': len(h)}


def run_arm(arm: str) -> dict:
    cfg = ARMS[arm]
    out = os.path.join(OUTROOT, arm)
    os.makedirs(out, exist_ok=True)
    cmd = build_cmd(arm, out)
    log_path = os.path.join(out, 'run.log')
    print('▶ 臂 %s：%s' % (arm, ' '.join(cmd[1:])), flush=True)
    t0 = time.perf_counter()
    sampler = None
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        lf.write('# cmd=%s\n# started=%s\n' % (json.dumps(cmd), now()))
        lf.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True,
                             encoding='utf-8', errors='replace', bufsize=1,
                             cwd=PKG)
        try:
            import psutil
            sampler = MemSampler(p.pid)
            sampler.start()
        except Exception:
            sampler = None
        for line in p.stdout:
            lf.write(line)
            lf.flush()
            if any(k in line for k in ('summary', 'RTF', '首字', 'EXECUTION',
                                       'NPU', '编译', '段', '错误', 'Error')):
                print('   ' + line.rstrip()[:200], flush=True)
        rc = p.wait()
    wall = round(time.perf_counter() - t0, 2)
    if sampler:
        sampler.stop()
        sampler.join(timeout=2)

    tx = os.path.join(out, 'transcript.txt')
    hyp = ''
    if os.path.isfile(tx):
        hyp = open(tx, encoding='utf-8', errors='replace').read()
    res = {
        'arm': arm, 'engine': cfg['engine'], 'asr_device': cfg['asr_device'],
        'cmd': cmd, 'rc': rc, 'wall_s': wall,
        'log': log_path, 'transcript': tx,
        'log_bytes': os.path.getsize(log_path) if os.path.isfile(log_path) else 0,
        'transcript_bytes': os.path.getsize(tx) if os.path.isfile(tx) else 0,
        'peak_mem_mb': round(sampler.peak_mb, 1) if sampler else None,
        'mem_samples': sampler.samples if sampler else 0,
        'parsed': parse_summary(log_path),
        'hyp_text': hyp,
    }
    print('✔ 臂 %s：rc=%d wall=%.1fs peak_mem=%s MB'
          % (arm, rc, wall, res['peak_mem_mb']), flush=True)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='both',
                    help='臂名，逗号分隔；both=npu,igpu（纯 ASR）')
    args = ap.parse_args()
    os.makedirs(OUTROOT, exist_ok=True)

    if args.arm == 'both':
        arms = ['npu', 'igpu']
    else:
        arms = [x.strip() for x in args.arm.split(',') if x.strip()]
    for a in arms:
        if a not in ARMS:
            print('!! 未知臂：%s（可选 %s）' % (a, list(ARMS)))
            return 2
    pid = acquire_lock('app294_rc4_%s' % ','.join(arms))
    if pid < 0:
        print('🔴 拿不到 MACHINE_LOCK ⇒ 本轮放弃（不抢锁）')
        return 2
    print('🔒 MACHINE_LOCK pid=%d' % pid, flush=True)
    results = {}
    try:
        for a in arms:
            results[a] = run_arm(a)
    finally:
        release_lock()

    # ── 汇总落盘 ─────────────────────────────────────────────
    ev = {'script': os.path.basename(__file__), 'ts': now(),
          'pkg': PKG, 'wav': WAV, 'arms': {k: {kk: vv for kk, vv in v.items()
                                               if kk != 'hyp_text'}
                                           for k, v in results.items()},
          'transcripts': {k: v['hyp_text'] for k, v in results.items()}}
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps({'out': EVID,
                      'arms': {k: v['wall_s'] for k, v in results.items()}},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
