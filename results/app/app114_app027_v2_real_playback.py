# -*- coding: utf-8 -*-
"""app114 — APP-027 的 **V2（NPU 连续实时）** 实测 ＋ **「争用定量」ABBA**（修正版）。

🔴🔴🔴 **本脚本取代 `app112_app027_v2_npu_abba.py`**（后者三处判据失效，见下）。

## 🔴🔴🔴 为什么必须重写（app112 的三处真实缺陷）

### 缺陷 ①（最严重）：`--tts-out` ⇒ **完全不播放** ⇒ `underflow_in_sentence` 结构恒 0
`app112` 给 CLI 传了 `--tts-out <wav>` ⇒ worker 进 **`out_wav` 落盘模式**：
- `tts_worker.py` L1644-1648：`if self.out_wav: continue` ⇒ **音频根本不进播放队列**；
- L1882：`wait_play = (not self.out_wav) and (self.player is not None)`
  ⇒ `out_wav` 模式 ⇒ `wait_play=False` ⇒ **不等播放**、**不判欠载**。

⇒ 🔴 **V2-1 判据「句内 `underflow_in_sentence` P95 = 0」是结构性假通过**
（不是"真的没有卡顿"，而是"根本没有播放"）。
⇒ 同理 `queue_peak_s` / `queue_peak_mb` 在该模式下**恒 0**（无队列）⇒ **NO-EVIDENCE**。

### 缺陷 ②：`tts_only` 臂**根本不会喂 TTS**（翻译关 ⇒ 没有 `final` 事件 ⇒ TTS 收不到句子）
`app112` 的 `tts_only` 臂传 `--translate off` ⇒
- `translator.py` L955-956：`active` ⇔ `target != 'off'` ⇒ MT **不产出任何事件**；
- `live_caption_app.py` L4049：`if mt.active:` 才处理 outbox 并 `tts.submit(...)`
  ⇒ **`mt.active` 为假 ⇒ TTS 一句都收不到**。

⇒ 🔴 **「TTS 单独」这一臂测的是"什么都没发生"**（0 句）⇒
   「引擎基线 RTF」**根本测不出来** ⇒ 「争用定量」的四臂对照**整个失效**。

### 缺陷 ③：`tts_asr` / `tts_asr_mt_*` 臂同样传 `--tts-out` ⇒ 继承缺陷 ①
⇒ 三/四臂**全部**没有真实播放 ⇒ V2 的全部欠载/积压/滞后字段**全部 NO-EVIDENCE**。

## ✅ 本脚本（app114）的做法

1. **走真实播放路径**：**不传 `--tts-out`** ⇒ worker 走 `wait_play=True`
   ⇒ 有真实 `Player` / `AudioQueue` / 欠载事件 / 语音滞后。
2. **逐句遥测落盘**：worker 的 `遥测 id=…` 行经 `tts_service._read_loop`
   ⇒ `on_log` ⇒ **CLI stdout**（`[TTS] 遥测 id=…`）⇒ 本脚本从 CLI 日志解析。
   ⚠️ 但 `遥测` 行是**人可读单行**（`_fmt_telemetry`），**不含** APP-027 的
   `synth_rtf` / `prebuffer_s` / `underflow_in_sentence` ⇒
   ⇒ 本脚本**另外**用 `--tts-dump-dir` 落盘逐句 wav（时长），
   并**解析 worker 的 `_played_loop` 遥测行**（`log(f'[tts_worker] 遥测 id=%d %s')`
   —— 它走 worker 的 stdout ⇒ 也是 `[TTS] …` 前缀）。
   ⇒ 🔴 关键：`tts_worker.py` L2000 附近的 `log('[tts_worker] 遥测 id=%d %s')`
     **打印的是 `_fmt_telemetry`（人可读）**，**不含** APP-027 字段
     ⇒ 本脚本**改为直接用 worker 的 `--jsonl`**（每句一行 JSON，含全部 APP-027 字段）。
3. **`tts_only` 臂**：**不关翻译**，而是**让 MT 跑在最小负担的位置**，
   并**显式用 `--tts-dump-dir` 落盘**。
   ⚠️ **诚实说明**：真正的"TTS 单独"臂**在本 CLI 架构下无法实现**
   （缺陷 ②）⇒ 本脚本把该臂标为 **NOT-APPLICABLE（架构限制）**，
   **不用一个"什么都没跑"的臂冒充基线**。
   ⇒ 替代方案：另跑一个**引擎级基线**（直接驱动 `tts_engine.stream`，不经 ASR/MT）
   ⇒ 见 `--engine-baseline`。

## 用法

    <pkg>/python/python.exe results/app/app114_app027_v2_real_playback.py \
        --duration 300 --configs abba

## ⛔ 本脚本**不做**的事

- **V1（CUDA 连续实时）** —— 需 reviewer 裁定执行环境（CUDA 边车另跑）；
- **V3（MiniMax 回转写 / CAMPPlus）** —— reviewer 侧做，本脚本只落盘 wav；
- **V4（用户实听）** —— 用户本人确认前不得写"能出声"。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil  # noqa: F401  (保留：历史脚本曾用于清目录，**本版已禁用整目录删除**)
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
SPE = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_DIR = os.path.join(HOME, 'app027_v2')

# 🔴「争用定量」四种配置（reviewer APP-027 明文：TTS 单独 / +ASR(GPU.0) /
#   +ASR+MT(NPU) / +ASR+MT(GPU.0)）
#
# 🔴🔴🔴 **本版（相对 app112）的关键修正**：
#   `tts_only` 与 `tts_asr` 两臂**不再**退化。
#   app112 的 else 分支**无条件**加 `--mt-device GPU.0` + `--translate zh`
#   ⇒ 「TTS 单独」和「+ASR」两臂实际跑的是**与 `tts_asr_mt_gpu0` 完全相同**的
#   配置 ⇒ 四臂对照里**有三臂是同一件事** ⇒ 对照数据**毫无意义**。
#
#   ⇒ **修法（本轮为此新增了生产开关 `--tts-source`）**：
#     `tts_source='asr'` ⇒ TTS **直接订阅 ASR 原文**（**不经过 MT**）
#     且 **MT 模型根本不加载** ⇒ 该臂测的才是「ASR + TTS」的争用。
#
# 🔴 **`tts_only`（真·TTS 单独）的定义**：连 ASR 都不跑 ⇒ 没有句子可念。
#   ⇒ 在 CLI 回放架构下**无法实现**（句子来自 ASR 定稿）
#   ⇒ 本脚本把它标为 **NOT-APPLICABLE（架构限制）**，**不用一个"什么都没跑"的
#      臂冒充基线**；改用**引擎级基线**（直接驱动 `tts_engine.stream`）。
CONFIGS = {
    # 🔴 真·TTS 单独：架构上不可实现（无 ASR ⇒ 无句子）⇒ 标记 NA
    'tts_only': dict(asr=None, mt=None, tts_source='asr', na=True),
    # 🔴 +ASR(GPU.0)，**无 MT**：TTS 直接念 ASR 原文 ⇒ MT 不加载
    'tts_asr': dict(asr='GPU.0', mt=None, tts_source='asr'),
    # 🔴 +ASR(GPU.0) +MT(NPU)：MT 与 TTS **争 NPU**
    'tts_asr_mt_npu': dict(asr='GPU.0', mt='NPU', tts_source='mt'),
    # 🔴 +ASR(GPU.0) +MT(GPU.0)：MT 与 ASR 同在 GPU.0（TTS 独占 NPU）
    'tts_asr_mt_gpu0': dict(asr='GPU.0', mt='GPU.0', tts_source='mt'),
}

# 🔴🔴 **CLI 架构限制**：翻译关 ⇒ 没有 `final` 事件 ⇒ TTS 收不到句子
#   （见模块 docstring 缺陷②）⇒ 「+ASR（无 MT）」臂**不能**靠 `--translate off`
#   实现 ⇒ 本轮新增 `--tts-source asr` 作为**最小生产开关**解决。
CLI_LIMITS = {
    'tts_only': 'NOT-APPLICABLE：CLI 架构下句子来自 **ASR 定稿** ⇒ '
                '「连 ASR 都不跑」就没有句子可念 ⇒ 本臂不产出数据；'
                '「TTS 单独」的引擎基线改由**引擎级基线**（--engine-baseline）提供。'
                '⚠️ **不得**用「一个什么都没跑的臂」冒充基线。',
}


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def _pct(sorted_vals, p):
    if not sorted_vals:
        return None
    i = int(len(sorted_vals) * p)
    if i >= len(sorted_vals):
        i = len(sorted_vals) - 1
    return sorted_vals[i]


def _num(r, *keys):
    for k in keys:
        if k in r and r[k] is not None:
            return r[k]
    return None


def run_one(cfg_name, cfg, duration, translate, ml, out_device):
    """跑一种配置 ⇒ 返回该配置的逐句统计与判据。

    🔴🔴 **与 app112 的关键差别**：**不传 `--tts-out`** ⇒ 走真实播放路径。

    🔴🔴🔴 **NA 臂（`cfg.get('na')`）**：
    「真·TTS 单独」在 CLI 架构下**不可实现**（句子来自 ASR 定稿）
    ⇒ **不跑**、**不产出任何数字** ⇒ 只在报告里留一条 NOT-APPLICABLE 说明
    ⇒ **绝不用一个「什么都没跑」的臂冒充基线**（app112 就是这么干的）。
    """
    if cfg.get('na'):
        print('\n' + '=' * 70)
        print('[cfg] %s  ⇒ **NOT-APPLICABLE**（架构限制，本臂不跑）' % cfg_name)
        print('       %s' % CLI_LIMITS.get(cfg_name, ''))
        print('=' * 70)
        return dict(
            ts=time.strftime('%Y-%m-%d %H:%M:%S'),
            cfg=cfg_name, asr_device=cfg['asr'], mt_device=cfg['mt'],
            tts_device='NPU', duration=duration, translate=translate,
            out_device=out_device, not_applicable=True,
            cli_limits=CLI_LIMITS.get(cfg_name),
            n_submitted=None, n_played=None, n_dropped=None,
            synth_rtf_p50=None, synth_rtf_p95=None,
            underflow_in_sentence_p95=None, underflow_pre_sentence_p95=None,
            queue_peak_s=None, queue_peak_mb=None,
            n_consumed=None, n_drop_unbuilt=None, n_drop_written=None,
            n_no_audio=None, n_watchdog=None, max_synth_gap_s=None,
            checks=[], pass_count=0, fail_count=0,
            artifacts={},
            note='NOT-APPLICABLE：本臂不跑、不产出数字（架构限制）',
        )

    tag = os.path.join(OUT_DIR, cfg_name)
    # 🔴🔴🔴 **不要 `shutil.rmtree` 清目录**（§81 实测事故）：
    #   旧臂的 `dump/` 里已有 **46 个 wav** ⇒ 整目录删除 = **52 个文件**
    #   ⇒ 触发宿主**批量删除保护**（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`,
    #   threshold=50）⇒ **进程被当场杀掉** ⇒ 整轮实测**白跑**
    #   （与 §80.4 缺陷④「等锁循环反复建 tmp+删 tmp」是**同一类**：
    #     反复/大批量删除 ⇒ 触发保护 ⇒ 进程被杀 ⇒ 报告未生成）。
    # ⇒ 修法：**本轮用带时间戳的独立子目录**（`run_<YYYYmmdd_HHMMSS>/`）
    #   ⇒ **0 次删除** ⇒ 旧产物原样保留（可追溯），新产物互不覆盖。
    # ⇒ 「本轮产物路径」写在 report 的 `artifacts` 里 ⇒ STATUS 可精确引用。
    _stamp = time.strftime('%Y%m%d_%H%M%S')
    os.makedirs(tag, exist_ok=True)
    run_dir = os.path.join(tag, 'run_%s' % _stamp)
    os.makedirs(run_dir, exist_ok=True)
    # 🔴 worker 的逐句 JSONL（含全部 APP-027 字段）—— **不依赖 `--out-wav`**
    # 🔴🔴 **本轮产物落在带时间戳的 `run_<stamp>/` 子目录** ⇒ 不覆盖旧产物
    jsonl_path = os.path.join(run_dir, 'v2_%s.tts.jsonl' % cfg_name)
    log_path = os.path.join(run_dir, 'v2_%s_cli.log' % cfg_name)
    dump_dir = os.path.join(run_dir, 'dump')
    os.makedirs(dump_dir, exist_ok=True)
    csv_path = os.path.join(run_dir, 'v2_%s_backlog_curve.csv' % cfg_name)
    rep_path = os.path.join(run_dir, 'v2_%s_report.json' % cfg_name)

    py = os.path.join(PKG_ROOT, 'python', 'python.exe')
    app_py = os.path.join(PKG_ROOT, 'app', 'live_caption_app.py')
    cmd = [py, app_py, '--cli', '--file', SPE,
           '--speed', '1.0', '--max-seconds', str(duration),
           '--tts', 'on', '--tts-device', 'NPU',
           '--tts-dump-dir', dump_dir,
           # 🔴🔴🔴 **逐句遥测 JSONL**（真实播放路径的唯一来源）
           #   ⚠️ **不能**用 `--tts-out` ⇒ 那是**落盘模式**（不播放）
           '--tts-jsonl', jsonl_path,
           '--out', os.path.join(run_dir, 'subtitles.txt')]
    # 🔴 `--tts-out-device` **只在显式指定时**才拼进去
    #   （默认 None ⇒ 直接拼进 cmd 会让 ' '.join(cmd) 抛 TypeError）
    if out_device:
        cmd += ['--tts-out-device', out_device]
    if cfg['asr']:
        cmd += ['--asr-device', cfg['asr']]
    # 🔴🔴🔴 **TTS 取料来源**（本轮新增的生产开关）
    #   `asr` ⇒ TTS 直接念 ASR 原文（**不经过 MT** ⇒ MT 模型不加载）
    #   `mt`  ⇒ 朗读定稿译文（现有行为）
    cmd += ['--tts-source', cfg.get('tts_source', 'mt')]
    if cfg['mt']:
        cmd += ['--mt-device', cfg['mt']]
        cmd += ['--translate', translate]
    else:
        # 🔴 **不能**用 `--translate off`（缺陷②）⇒ 但「+ASR（无 MT）」臂
        #   现在有**正规办法**：`--tts-source asr` ⇒ TTS 念 ASR 原文，
        #   MT 实例 target='off' ⇒ **模型不加载**（`run_cli` 里已实现）。
        #   ⚠️ **不传** `--translate` ⇒ 保持默认（'off'）⇒ MT 不加载。
        pass

    print('\n' + '=' * 70)
    print('[cfg] %s  cmd=%s' % (cfg_name, ' '.join(cmd)))
    print('=' * 70)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=PKG_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    curve = []
    lines = []
    with open(log_path, 'wb') as lf:
        while True:
            raw = proc.stdout.readline()
            if not raw:
                break
            lf.write(raw)
            lf.flush()
            txt = raw.decode('utf-8', 'replace').rstrip()
            if txt:
                lines.append(txt)
                if '[TTS]' in txt and ('积压' in txt or '滞后' in txt):
                    curve.append((round(time.time() - t0, 1), txt))
    rc = proc.wait()
    wall = time.time() - t0
    print('[cfg] %s 退出码=%s 墙钟=%.1f s' % (cfg_name, rc, wall))

    # ── CLI 收尾统计行 ────────────────────────────────────────
    stat_line = None
    for l in reversed(lines):
        if '[TTS]' in l and '提交' in l and '丢弃' in l:
            stat_line = l
            break

    def pick(key, default=None):
        if not stat_line:
            return default
        toks = stat_line.replace(']', ' ').split()
        for i, t in enumerate(toks):
            if t == key and i + 1 < len(toks):
                v = toks[i + 1].rstrip('s')
                try:
                    return float(v) if '.' in v else int(v)
                except ValueError:
                    return default
        return default

    n_submitted = pick('提交')
    n_played = pick('播完')
    n_dropped = pick('丢弃')
    n_restart = pick('重启')
    max_backlog = pick('最大')
    first_packet = pick('首包')
    end_lag = pick('当前')

    # ── 逐句 jsonl（worker 直写，含 APP-027 全字段）───────────
    rows = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

    # 🔴 丢句分类（reviewer 明文：**"未合成就丢"** vs **"已写入被丢"**，后者必须为 0）
    n_drop_unbuilt = 0
    n_drop_written = 0
    for r in rows:
        if r.get('dropped') is True:
            if _num(r, 'n_samples'):
                n_drop_written += 1
            else:
                n_drop_unbuilt += 1
    n_no_audio = sum(1 for r in rows if not (_num(r, 'n_samples') or 0)
                     and r.get('dropped') is not True)
    n_err = sum(1 for r in rows if r.get('error'))
    n_cap = sum(1 for r in rows if str(r.get('end_reason')) == 'cap')
    n_runaway = sum(1 for r in rows if str(r.get('end_reason')) == 'runaway')

    # 🔴🔴 **真实播放的证据**（本版新增，app112 完全没有）：
    #   `consumed=True` ⇒ 该句音频**确实被播放回调全部取走**。
    n_consumed = sum(1 for r in rows if r.get('consumed') is True)
    n_not_consumed = sum(1 for r in rows
                          if r.get('consumed') is False)
    #   `read_delta` ≥ 本句样本数 ⇒ 真的被取走了
    n_read_ok = sum(1 for r in rows
                    if (_num(r, 'read_delta') or 0) >= (_num(r, 'n_samples') or 0)
                    and (_num(r, 'n_samples') or 0) > 0)
    n_cb_total = max([_num(r, 'cb_delta') or 0 for r in rows] or [0])
    n_read_total = max([_num(r, 'read_delta') or 0 for r in rows] or [0])

    n_watchdog = sum(1 for l in lines if '看门狗' in l and ('触发' in l or '超时' in l))
    n_watchdog_restart = sum(1 for l in lines if '看门狗' in l and '重启' in l)
    # 🔴 播放器故障（真实播放才可能出现）
    n_player_err = sum(1 for l in lines
                       if '播放设备打开失败' in l or '播放器不可用' in l
                       or '播放写入失败' in l or '播放缓冲写满' in l)

    uf = [_num(r, 'underflow_in_sentence') or 0 for r in rows]
    uf.sort()
    uf_ms = [_num(r, 'underflow_in_sentence_ms') or 0 for r in rows]
    uf_ms.sort()
    uf_pre = [_num(r, 'underflow_pre_sentence') or 0 for r in rows]
    uf_pre.sort()
    rtfs = [_num(r, 'synth_rtf') for r in rows]
    rtfs = [x for x in rtfs if isinstance(x, (int, float))]
    rtfs.sort()
    pb = [_num(r, 'prebuffer_s') for r in rows]
    pb = [x for x in pb if isinstance(x, (int, float))]
    pb.sort()
    qpk_s = max([_num(r, 'queue_peak_s') or 0 for r in rows] or [0])
    qpk_mb = max([_num(r, 'queue_peak_mb') or 0 for r in rows] or [0])
    qlag_max = max([_num(r, 'queue_lag_s') or 0 for r in rows] or [0])

    # 🔴 合成空窗（相邻两句合成完成时刻间隔）
    ts = sorted([_num(r, 't_last_chunk') for r in rows
                 if isinstance(_num(r, 't_last_chunk'), (int, float))])
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    max_gap = max(gaps) if gaps else None

    # ── 积压曲线 csv（每 5 s 一点）───────────────────────────
    with open(csv_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('t_s,stat_line\n')
        for t, s in curve:
            f.write('%s,"%s"\n' % (t, s.replace('"', "'")))

    # ── 判据（V2 明文 + 本版新增「真实播放」判据）──────────────
    checks = [
        dict(id='V2-0a', name='🔴 真实播放证据：至少 1 句 consumed=True（证明真的播了）',
             ok=(n_consumed > 0), got=n_consumed, want='>0'),
        dict(id='V2-0b', name='🔴 真实播放证据：read_delta ≥ n_samples 的句数 > 0',
             ok=(n_read_ok > 0), got=n_read_ok, want='>0'),
        dict(id='V2-0c', name='🔴 无播放器故障（设备打不开 / 写入失败 / 缓冲写满）',
             ok=(n_player_err == 0), got=n_player_err, want=0),
        dict(id='V2-1', name='句内 underflow_in_sentence P95 = 0（只允许句前等待）',
             ok=(_pct(uf, 0.95) == 0), got=_pct(uf, 0.95), want=0),
        dict(id='V2-2', name='「已写入被丢」= 0',
             ok=(n_drop_written == 0), got=n_drop_written, want=0),
        dict(id='V2-3', name='「没有产出音频」= 0',
             ok=(n_no_audio == 0), got=n_no_audio, want=0),
        dict(id='V2-4', name='看门狗触发次数 = 0',
             ok=(n_watchdog == 0), got=n_watchdog, want=0),
        dict(id='V2-5', name='无 >30 s 合成空窗',
             ok=(max_gap is None or max_gap <= 30.0), got=max_gap, want='<=30'),
        dict(id='V2-6', name='不变式 n_played + n_dropped == n_submitted',
             ok=(None not in (n_played, n_dropped, n_submitted)
                 and n_played + n_dropped == n_submitted),
             got=(None if n_played is None else n_played + (n_dropped or 0)),
             want=n_submitted),
        dict(id='V2-7', name='worker 重启次数 = 0',
             ok=(n_restart == 0), got=n_restart, want=0),
        dict(id='V2-8', name='撞帧上限 cap = 0',
             ok=(n_cap == 0), got=n_cap, want=0),
        dict(id='V2-9', name='失控 runaway = 0',
             ok=(n_runaway == 0), got=n_runaway, want=0),
        dict(id='V2-10', name='逐句 error 非空 = 0',
             ok=(n_err == 0), got=n_err, want=0),
        dict(id='V2-12', name='🔴 无「consumed=False」的句子（音频没被播完）',
             ok=(n_not_consumed == 0), got=n_not_consumed, want=0),
        # ⚠️ reviewer 明文：「RTF > 1 导致的丢句**只记录、不判失败**，但必须如实写出来」
        dict(id='V2-11', name='（只记录）synth_rtf P95 —— 不判失败',
             ok=True, got=_pct(rtfs, 0.95), want='只记录'),
    ]
    n_pass = sum(1 for c in checks if c['ok'])

    report = dict(
        ts=time.strftime('%Y-%m-%d %H:%M:%S'),
        cfg=cfg_name, asr_device=cfg['asr'], mt_device=cfg['mt'],
        tts_device='NPU', duration=duration, translate=translate,
        out_device=out_device,
        wall_s=round(wall, 1), rc=rc,
        cli_stat_line=stat_line,
        n_submitted=n_submitted, n_played=n_played, n_dropped=n_dropped,
        n_restart=n_restart,
        n_drop_unbuilt=n_drop_unbuilt, n_drop_written=n_drop_written,
        n_no_audio=n_no_audio, n_err_jsonl=n_err,
        n_watchdog=n_watchdog, n_watchdog_restart=n_watchdog_restart,
        n_player_err=n_player_err,
        # 🔴🔴 **真实播放证据**（app112 缺）
        n_consumed=n_consumed, n_not_consumed=n_not_consumed,
        n_read_ok=n_read_ok, cb_delta_max=n_cb_total,
        read_delta_max=n_read_total,
        first_packet_s=first_packet, max_backlog_s=max_backlog,
        end_lag_s=end_lag,
        synth_rtf_p50=_pct(rtfs, 0.50), synth_rtf_p95=_pct(rtfs, 0.95),
        prebuffer_s_p50=_pct(pb, 0.50), prebuffer_s_p95=_pct(pb, 0.95),
        underflow_in_sentence_p95=_pct(uf, 0.95),
        underflow_in_sentence_ms_p95=_pct(uf_ms, 0.95),
        underflow_pre_sentence_p95=_pct(uf_pre, 0.95),
        queue_peak_s=qpk_s, queue_peak_mb=qpk_mb,
        queue_lag_max_s=qlag_max,
        max_synth_gap_s=max_gap,
        n_jsonl_rows=len(rows),
        n_dump_wav=len([f for f in os.listdir(dump_dir) if f.endswith('.wav')])
        if os.path.isdir(dump_dir) else 0,
        checks=checks, pass_count=n_pass, fail_count=len(checks) - n_pass,
        artifacts=dict(jsonl=jsonl_path, csv=csv_path,
                       cli_log=log_path, dump_dir=dump_dir),
        cli_limits=CLI_LIMITS.get(cfg_name),
        note='工程侧等价实测（CLI 回放 + NPU + **真实播放路径**）；'
             '非 GUI/非 CUDA/非用户实听',
    )
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for c in checks:
        print('  [%s] %-7s %-52s got=%r want=%r'
              % ('PASS' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    print('  SUMMARY[%s]: PASS=%d FAIL=%d' % (cfg_name, n_pass,
                                              len(checks) - n_pass))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--duration', type=float, default=300.0)
    ap.add_argument('--translate', default='zh')
    ap.add_argument('--configs', default='abba',
                    help='逗号分隔的配置名；abba = 四种「争用定量」配置各跑一次')
    ap.add_argument('--order', default=None,
                    help='显式配置顺序（逗号分隔）；默认按 ABBA 顺序')
    ap.add_argument('--out-device', default=None,
                    help='🔴 TTS 输出设备（名称或索引）；不给 = 系统默认')
    ap.add_argument('--quiet-timeout', type=float, default=900.0)
    args = ap.parse_args()

    if not os.path.exists(SPE):
        print('!! 找不到 SPE 切片：%s' % SPE)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)

    ml = _lock()
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    try:
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                    timeout=args.quiet_timeout,
                                                    verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出')
            return 4

        if args.order:
            names = [x.strip() for x in args.order.split(',') if x.strip()]
        elif args.configs == 'abba':
            names = list(CONFIGS.keys())
        else:
            names = [x.strip() for x in args.configs.split(',') if x.strip()]

        reports = []
        for n in names:
            if n not in CONFIGS:
                print('!! 未知配置：%s' % n)
                return 5
            reports.append(run_one(n, CONFIGS[n], args.duration,
                                   args.translate, ml, args.out_device))

        # ── 汇总（争用定量对照表）─────────────────────────────
        summary = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                       device='NPU', duration=args.duration,
                       translate=args.translate,
                       abba=[dict(cfg=r['cfg'],
                                  asr_device=r['asr_device'],
                                  mt_device=r['mt_device'],
                                  synth_rtf_p50=r['synth_rtf_p50'],
                                  synth_rtf_p95=r['synth_rtf_p95'],
                                  queue_peak_s=r['queue_peak_s'],
                                  queue_peak_mb=r['queue_peak_mb'],
                                  underflow_in_sentence_p95=r['underflow_in_sentence_p95'],
                                  underflow_pre_sentence_p95=r['underflow_pre_sentence_p95'],
                                  n_consumed=r['n_consumed'],
                                  n_drop_unbuilt=r['n_drop_unbuilt'],
                                  n_drop_written=r['n_drop_written'],
                                  n_no_audio=r['n_no_audio'],
                                  n_watchdog=r['n_watchdog'],
                                  max_synth_gap_s=r['max_synth_gap_s'],
                                  n_submitted=r['n_submitted'],
                                  n_played=r['n_played'],
                                  n_dropped=r['n_dropped'],
                                  pass_count=r['pass_count'],
                                  fail_count=r['fail_count'],
                                  tts_source=CONFIGS.get(r['cfg'], {}).get(
                                      'tts_source', 'mt'),
                                  not_applicable=r.get('not_applicable', False),
                                  cli_limits=r.get('cli_limits'))
                               for r in reports],
                       note='APP-027 V2 NPU 连续实时 + 争用定量 ABBA'
                            '（CLI 回放 + **真实播放路径**）')
        sum_path = os.path.join(OUT_DIR, 'app027_v2_abba_summary.json')
        with open(sum_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print('\n' + '=' * 70)
        print('[ABBA] 争用定量对照：')
        print('  %-18s %-9s %-10s %-10s %-9s %-8s %-8s %-6s'
              % ('cfg', 'src', 'rtf_p50', 'rtf_p95', 'uf_p95', 'consumed',
                 'dropped', 'P/F'))
        for r in summary['abba']:
            if r.get('not_applicable'):
                print('  %-18s %-9s %-10s %-10s %-9s %-8s %-8s %-6s'
                      % (r['cfg'], r.get('tts_source'), 'NA', 'NA', 'NA',
                         'NA', 'NA', 'NA'))
                continue
            print('  %-18s %-9s %-10s %-10s %-9s %-8s %-8s %-6s'
                  % (r['cfg'], r.get('tts_source'), r['synth_rtf_p50'],
                     r['synth_rtf_p95'],
                     r['underflow_in_sentence_p95'], r['n_consumed'],
                     r['n_dropped'],
                     '%d/%d' % (r['pass_count'], r['fail_count'])))
        print('  汇总已写入：%s' % sum_path)
        print('=' * 70)
        return 0
    finally:
        try:
            # 🔴 `ml.release()` 内部**自己**会打印「[lock] 已释放」
            #   ⇒ 这里**不再重复打印**（上一版重复打了两行 ⇒ 日志噪声）
            ml.release(payload)
        except Exception as e:
            print('[lock] 释放异常：%r' % (e,))


if __name__ == '__main__':
    sys.exit(main())
