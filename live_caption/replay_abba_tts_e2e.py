r"""replay_abba_tts_e2e.py — 端到端 ABBA：TTS 语音输出 off/on/on/off

为什么需要这个脚本
------------------
APP-001 检查点 3 的验收要求：

    「ABBA（tts off/on/on/off）报告 ASR RTF 增量（≤+0.10）、语音输出延迟
      P50/P95、积压和丢句数；--tts-out 输出的 wav 交给 reviewer 回转写。」

§13.7 第 1 条一直挂着「端到端 ABBA ⏸ 未做」⇒ **v1.4 重打包的前置没闭环**。

本脚本做什么
------------
1. **等锁 + 持锁**（复用 `replay_c134_mt.py` 的 `_pid_alive` / `acquire_lock`
   / `release_lock` —— **不自写**探测逻辑，§12.8 踩坑记录：自写 ctypes 探测
   设了 `restype` 反而返回 `err=87`）。
2. **ABBA 四轮**（off / on / on / off），同一段音频、同一套 ASR/MT 配置，
   唯一变量是 **TTS 语音输出开/关**。
3. **每轮采集**（全部来自 CLI stdout 的原始字段 + 落盘 jsonl）：
   - ASR：RTF、出字延迟中位、段数
   - MT：延迟中位 / P95 / TTFT / tok/s（翻译始终开，才能比较 TTS 的净影响）
   - TTS：首包延迟、积压（当前/最大）、提交/播完/丢弃句数、worker 重启次数
   - TTS 逐句时间线：`<out>.tts.jsonl` 里的 `t_first_packet` ⇒ **语音输出延迟
     P50/P95**（每句的「入队→首包」）
4. **落盘** `abba_report.json` + 每轮产物，**一律写到仓库外**（APP-005①）。

产物目录（仓库外）
------------------
    C:\Users\Trekker-PTL\abba_out\e2e\<run>\

🔴 纪律
--------
- **产物写仓库外**（APP-005①：回放产物一律不落仓库）。
- **不贴内部会议原文**：素材是自造的 TTS 语音（见 `gen_audio.py`），
  报告里只贴**计数与统计量**。
- **不自己判定音质**：质量归 reviewer 用 MiniMax 回转写。
- 计时类作业 ⇒ **必须持共享机器锁**。

用法
----
    python replay_abba_tts_e2e.py [--audio <wav>] [--seconds 60]
                                 [--asr-device GPU.0] [--mt-device GPU.0]
                                 [--tts-device NPU] [--tts-voice A]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 🔴 复用现有实现，**不自写** PID 探测 / 锁逻辑。
from replay_c134_mt import (          # noqa: E402
    LOCK, acquire_lock, release_lock,
)

# 客户包 Python（唯一带 babelvox 的解释器）
# 🔴 2026-10-26 §48：指向 **v1.5**（旧值 v1.3 早已不存在 ⇒ 脚本直接崩）。
#   ⚠️ **不写死版本号** ⇒ 用「扫主目录挑版本号最大」的方式发现
#      （与 `sync_s48_to_pkg.py::discover_pkg()` 同一口径）。
def _discover_pkg():
    import re as _re
    home = r'C:\Users\Trekker-PTL'
    cands = []
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        m = _re.search(r'_v(\d+(?:\.\d+)+)', name)
        if not m:
            continue
        if not os.path.isdir(os.path.join(home, name, 'app')):
            continue
        cands.append((tuple(int(x) for x in m.group(1).split('.')),
                      os.path.join(home, name)))
    if not cands:
        raise SystemExit('!! 找不到客户包目录')
    cands.sort()
    return cands[-1][1]


PKG = _discover_pkg()
PY = os.path.join(PKG, 'python', 'python.exe')

# 🔴 2026-10-26 §48：**直接用客户包内的 app/**（不再用陈旧的 abba_stage）
#   理由：ABBA 要测的是**客户实际拿到的代码** ⇒ 必须跑包内那份；
#   旧的 `abba_stage/app` 是 2026-10-23 的拷贝（含大量 diag 脚本，
#   且 `models` 还指向 v1.3）⇒ 测的不是交付物。
STAGE_APP = os.path.join(PKG, 'app')
STAGE = PKG

# 🔴 APP-005①：产物一律写仓库外
OUTROOT = r'C:\Users\Trekker-PTL\abba_out\e2e'

# ── stdout 字段解析 ────────────────────────────────────────────────────
# CLI 收尾会打这些行（原文见 live_caption_app.py::run_cli 末尾）：
#   [gpu_int8] 音频 20.4s  墙钟 20.9s  RTF(计算) 0.728  出字延迟中位 489 ms
#              最大积压 1.3s  段 4
#   [gpu_int8] 翻译 target=zh 后端=auto 设备 GPU.0 state=ready 句数 8
#              延迟中位 510.9 ms  P95 696.8 ms  TTFT 222.6 ms  36.5 tok/s
#   [TTS] 首包 0.83s  积压 当前 0.00s / 最大 1.20s  提交 8  播完 8  丢弃 0  重启 0
RE_ASR = re.compile(
    r'音频\s+(?P<audio_s>[\d.]+)s\s+墙钟\s+(?P<wall>[\d.]+)s\s+'
    r'RTF\(计算\)\s+(?P<rtf>[\d.]+)\s+出字延迟中位\s+(?P<lag>[\d]+)\s*ms\s+'
    r'最大积压\s+(?P<backlog>[\d.]+)s\s+段\s+(?P<segs>\d+)')
RE_MT = re.compile(
    r'翻译\s+target=(?P<target>\S+)\s+后端=(?P<engine>\S+)\s+设备\s+(?P<device>\S+)\s+'
    r'state=(?P<state>\S+)\s+句数\s+(?P<n>\d+)\s+延迟中位\s+(?P<lat>[\d.]+)\s*ms\s+'
    r'P95\s+(?P<p95>[\d.]+)\s*ms\s+TTFT\s+(?P<ttft>[\d.]+)\s*ms\s+(?P<tok>[\d.]+)\s+tok/s')
RE_TTS = re.compile(
    r'首包\s+(?P<first>[\d.]+)s\s+积压\s+当前\s+(?P<bl>[\d.]+)s\s*/\s*最大\s+'
    r'(?P<blmax>[\d.]+)s\s+提交\s+(?P<sub>\d+)\s+播完\s+(?P<played>\d+)\s+'
    r'丢弃\s+(?P<dropped>\d+)\s+重启\s+(?P<restart>\d+)')


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_stdout(text):
    """从 CLI stdout 里抠出统计字段（**只抠数字，不回传原文**）。"""
    out = {}
    m = RE_ASR.search(text)
    if m:
        out.update(asr_audio_s=_f(m.group('audio_s')),
                   asr_wall_s=_f(m.group('wall')),
                   asr_rtf=_f(m.group('rtf')),
                   asr_lag_ms=_i(m.group('lag')),
                   asr_max_backlog_s=_f(m.group('backlog')),
                   asr_segs=_i(m.group('segs')))
    m = RE_MT.search(text)
    if m:
        out.update(mt_target=m.group('target'), mt_engine=m.group('engine'),
                   mt_device=m.group('device'), mt_state=m.group('state'),
                   mt_n=_i(m.group('n')), mt_lat_med_ms=_f(m.group('lat')),
                   mt_lat_p95_ms=_f(m.group('p95')), mt_ttft_ms=_f(m.group('ttft')),
                   mt_tok_s=_f(m.group('tok')))
    m = RE_TTS.search(text)
    if m:
        out.update(tts_first_packet_s=_f(m.group('first')),
                   tts_backlog_s=_f(m.group('bl')),
                   tts_max_backlog_s=_f(m.group('blmax')),
                   tts_n_submitted=_i(m.group('sub')),
                   tts_n_played=_i(m.group('played')),
                   tts_n_dropped=_i(m.group('dropped')),
                   tts_n_restart=_i(m.group('restart')))
    return out


def read_jsonl(path):
    """读 TTS 逐句时间线 ⇒ 语音输出延迟分布（P50/P95）。"""
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def latency_stats(rows):
    """每句「入队 → 首包」的延迟分布（ms）。

    ⚠️ 只统计**有首包**的句子；被丢弃的句子单独计数。
    """
    fp = [r['t_first_packet'] for r in rows
          if r.get('t_first_packet') is not None]
    dropped = sum(1 for r in rows if r.get('dropped'))
    err = sum(1 for r in rows if r.get('error'))
    dur = [r['dur_s'] for r in rows if r.get('dur_s') is not None]
    out = {'n_rows': len(rows), 'n_with_first_packet': len(fp),
           'n_dropped': dropped, 'n_error': err,
           'speech_duration_s': round(sum(dur), 3) if dur else None}
    if fp:
        fp_ms = sorted(x * 1000.0 for x in fp)
        out.update(first_packet_p50_ms=round(statistics.median(fp_ms), 1),
                   first_packet_p95_ms=round(_pct(fp_ms, 95), 1),
                   first_packet_min_ms=round(fp_ms[0], 1),
                   first_packet_max_ms=round(fp_ms[-1], 1))
    return out


def _pct(sorted_vals, pct):
    """线性插值分位数（与 numpy.percentile 默认口径一致）。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def count_lines(path):
    if not os.path.isfile(path):
        return None, None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = [ln.strip() for ln in f]
    nonempty = sum(1 for ln in lines if ln)
    return len(lines), nonempty


def run_once(audio, seconds, tts_on, outdir, name, asr_device, mt_device,
             tts_device, tts_voice, tts_precision, asr_lang, mt_engine=None):
    """跑一轮 CLI 回放，返回结构化结果（只含计数与统计量）。"""
    os.makedirs(outdir, exist_ok=True)
    out_txt = os.path.join(outdir, f'{name}.txt')
    out_wav = os.path.join(outdir, f'{name}.tts.wav')

    cmd = [PY, os.path.join(STAGE_APP, 'live_caption_app.py'),
           '--cli', '--file', audio,
           '--engine', 'gpu_int8',
           '--asr-lang', asr_lang,
           '--max-seconds', str(seconds),
           # 🔴 翻译**始终开启**：这样 TTS 才有输入，才能比较 TTS 的净影响
           '--translate', 'zh',
           '--out', out_txt,
           '--asr-device', asr_device,
           '--mt-device', mt_device,
           '--tts', 'on' if tts_on else 'off',
           '--tts-device', tts_device,
           '--tts-voice', tts_voice,
           '--tts-precision', tts_precision,
           '--tts-out', out_wav]
    if mt_engine:
        cmd += ['--mt-engine', mt_engine]

    t0 = time.time()
    # ⚠️ Windows 子进程 stdout 是 GBK ⇒ capture_output 拿 bytes 自己解码
    p = subprocess.run(cmd, capture_output=True, timeout=3600)
    wall = time.time() - t0
    out_txt_s = p.stdout.decode('utf-8', errors='replace')
    err_txt = p.stderr.decode('utf-8', errors='replace')

    res = parse_stdout(out_txt_s)
    res.update(name=name, tts_on=bool(tts_on), exit_code=p.returncode,
               proc_wall_s=round(wall, 2), cmd=' '.join(cmd))
    jsonl = out_wav + '.tts.jsonl'
    res['tts_jsonl'] = jsonl if os.path.isfile(jsonl) else None
    res['tts_jsonl_stats'] = latency_stats(read_jsonl(jsonl))
    res['tts_wav'] = out_wav if os.path.isfile(out_wav) else None
    res['tts_wav_bytes'] = (os.path.getsize(out_wav)
                            if os.path.isfile(out_wav) else None)
    n, ne = count_lines(out_txt)
    res['out_txt_lines_total'] = n
    res['out_txt_lines_nonempty'] = ne
    # 译文文件（句数 ↔ 行数对应关系）
    mt_txt = os.path.splitext(out_txt)[0] + '.mt.txt'
    res['mt_txt'] = mt_txt if os.path.isfile(mt_txt) else None
    mn, mne = count_lines(mt_txt)
    res['mt_txt_lines_total'] = mn
    res['mt_txt_lines_nonempty'] = mne
    # 存 stdout/stderr 全文（仓库外），供 reviewer 复核
    with open(os.path.join(outdir, f'{name}.stdout.txt'), 'w',
              encoding='utf-8') as f:
        f.write(out_txt_s)
    with open(os.path.join(outdir, f'{name}.stderr.txt'), 'w',
              encoding='utf-8') as f:
        f.write(err_txt)
    # 只留错误尾部进报告（不进原文）
    res['stderr_tail'] = err_txt[-1500:]
    return res


def summarize(results):
    """ABBA 判读：off 组 vs on 组。"""
    off = [r for r in results if not r['tts_on']]
    on = [r for r in results if r['tts_on']]

    def m(rs, key):
        vals = [r[key] for r in rs if r.get(key) is not None]
        return (sum(vals) / len(vals)) if vals else None

    def rng(rs, key):
        vals = [r[key] for r in rs if r.get(key) is not None]
        return (max(vals) - min(vals)) if vals else None

    s = {}
    for tag, rs in (('off', off), ('on', on)):
        if not rs:
            continue
        s[tag] = {
            'n': len(rs),
            'asr_rtf_mean': m(rs, 'asr_rtf'),
            'asr_rtf_range': rng(rs, 'asr_rtf'),
            'asr_lag_ms_mean': m(rs, 'asr_lag_ms'),
            'asr_segs_mean': m(rs, 'asr_segs'),
            'mt_lat_med_ms_mean': m(rs, 'mt_lat_med_ms'),
            'mt_lat_p95_ms_mean': m(rs, 'mt_lat_p95_ms'),
            'mt_tok_s_mean': m(rs, 'mt_tok_s'),
        }
    if s.get('off') and s.get('on') and s['off']['asr_rtf_mean'] is not None:
        delta = s['on']['asr_rtf_mean'] - s['off']['asr_rtf_mean']
        s['asr_rtf_delta'] = round(delta, 4)
        s['asr_rtf_delta_ok'] = (delta <= 0.10)
        # 组内噪声：off 组自身极差（同配置两次跑）
        s['asr_rtf_noise_off_range'] = s['off']['asr_rtf_range']
    # TTS 侧汇总
    drops = [r.get('tts_n_dropped') for r in on if r.get('tts_n_dropped') is not None]
    p50 = [r['tts_jsonl_stats'].get('first_packet_p50_ms') for r in on
           if r.get('tts_jsonl_stats', {}).get('first_packet_p50_ms') is not None]
    p95 = [r['tts_jsonl_stats'].get('first_packet_p95_ms') for r in on
           if r.get('tts_jsonl_stats', {}).get('first_packet_p95_ms') is not None]
    blm = [r.get('tts_max_backlog_s') for r in on
           if r.get('tts_max_backlog_s') is not None]
    s['tts'] = {
        'n_runs': len(on),
        'n_dropped_total': sum(drops) if drops else None,
        'n_dropped_max': max(drops) if drops else None,
        'first_packet_p50_ms_mean': m(on, 'tts_first_packet_s') and
            (sum(p50) / len(p50) if p50 else None),
        'first_packet_p95_ms_mean': (sum(p95) / len(p95)) if p95 else None,
        'max_backlog_s_max': max(blm) if blm else None,
    }
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', default=r'C:\Users\Trekker-PTL\abba_out\abba_input_16k.wav')
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--asr-device', default='GPU.0')
    ap.add_argument('--mt-device', default='GPU.0')
    ap.add_argument('--tts-device', default='NPU')
    ap.add_argument('--tts-voice', default='A')
    ap.add_argument('--tts-precision', default='f16', choices=['f32', 'f16'])
    ap.add_argument('--asr-lang', default='English')
    ap.add_argument('--mt-engine', default=None)
    ap.add_argument('--module', default='app')
    ap.add_argument('--run-name', default=None)
    ap.add_argument('--no-wait-lock', action='store_true')
    args = ap.parse_args()

    run_name = args.run_name or time.strftime('%Y%m%d_%H%M%S')
    outdir = os.path.join(OUTROOT, run_name)
    os.makedirs(outdir, exist_ok=True)

    acquired = False
    if not args.no_wait_lock:
        acquire_lock(args.module)
        acquired = True
    try:
        plan = [
            ('abba1_off', False),
            ('abba2_on', True),
            ('abba3_on', True),
            ('abba4_off', False),
        ]
        results = []
        for name, tts_on in plan:
            print(f'\n===== {name}（tts={"on" if tts_on else "off"}） =====',
                  flush=True)
            r = run_once(args.audio, args.seconds, tts_on, outdir, name,
                         args.asr_device, args.mt_device, args.tts_device,
                         args.tts_voice, args.tts_precision, args.asr_lang,
                         args.mt_engine)
            results.append(r)
            print(f'  exit={r["exit_code"]} rtf={r.get("asr_rtf")} '
                  f'segs={r.get("asr_segs")} wall={r.get("asr_wall_s")}s '
                  f'proc_wall={r["proc_wall_s"]}s', flush=True)
            print(f'  MT: lat_med={r.get("mt_lat_med_ms")} '
                  f'P95={r.get("mt_lat_p95_ms")} tok/s={r.get("mt_tok_s")}',
                  flush=True)
            if tts_on:
                jl = r.get('tts_jsonl_stats') or {}
                print(f'  TTS: 首包={r.get("tts_first_packet_s")}s '
                      f'积压max={r.get("tts_max_backlog_s")}s '
                      f'提交={r.get("tts_n_submitted")} '
                      f'播完={r.get("tts_n_played")} '
                      f'丢弃={r.get("tts_n_dropped")}', flush=True)
                print(f'  TTS 首包延迟 P50={jl.get("first_packet_p50_ms")}ms '
                      f'P95={jl.get("first_packet_p95_ms")}ms '
                      f'(有首包 {jl.get("n_with_first_packet")}/'
                      f'{jl.get("n_rows")})', flush=True)
            if r['exit_code'] != 0:
                print('  stderr tail:', r['stderr_tail'][-800:], flush=True)

        summary = summarize(results)
        report = {
            'run_name': run_name,
            'outdir': outdir,
            'audio': os.path.basename(args.audio),
            'seconds': args.seconds,
            'asr_lang': args.asr_lang,
            'devices': {'asr': args.asr_device, 'mt': args.mt_device,
                        'tts': args.tts_device},
            'tts_voice': args.tts_voice,
            'tts_precision': args.tts_precision,
            'plan': [n for n, _ in plan],
            'summary': summary,
            'results': results,
        }
        rp = os.path.join(outdir, 'abba_report.json')
        with open(rp, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('\n===== ABBA 判读 =====', flush=True)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        print('\n报告已落盘:', rp, flush=True)
    finally:
        if acquired:
            release_lock()


if __name__ == '__main__':
    main()
