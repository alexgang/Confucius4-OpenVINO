#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""APP-134 a / APP-137-3：**能排空（drain）的** e2e 客户端。

## 为什么需要它（reviewer APP-134 问题①，原话）
> 「丢句 0」「收尾积压 0.0」不成立。`stats_full.pipeline`：off 臂 n_submitted 121、
> n_emitted 94、**n_pending 27**；on 臂 121/89/**32**；clone 臂 168/113/**55**。
> 会话在媒体结束时就关了，没有排空，所以有 22%/26%/33% 的句子到最后也没配上音。
> `margin.last_segment_lag_sec` 为 111.99 / 138.35 / 183.57 s，正好等于 max_lag，
> 说明滞后一直在涨、没有回落。

⇒ 原来的 `bgkeep_e2e.py` 媒体播完只等 `--tail-wait`（默认 30 s）就关连接 ⇒
**测的是「播完那一刻」，不是「全部句都配完音」**。

## 本工具做三件事
1. **媒体结束后继续等**，直到 `stats_full.pipeline.n_pending == 0`（或等满
   `--drain-cap` 秒，默认 300 s）⇒ 记录**排空时刻**；
2. **记录排空前后的 `n_pending`**（媒体结束时一次、排空后一次）以及整条采样序列；
3. **记录每一句最终的 `dub_late`**（到达时刻 − 应播时刻），而不是只给 max/p90。

## 设计取舍（不 fork 整个 EXT 工具）
渲染（player_mix.wav / bg_only.wav / dubs.npz）逻辑**直接复用 EXT 的 `report()`**
⇒ 本文件只改「什么时候收」和「多报什么」，**不重复实现渲染** ⇒ 两边不会漂移。
本文件属于 **App 模块**（dev 树），不动 reviewer 的 `live_dub_ext` 仓库。

## 用法
```
<pkg>\python\python.exe live_caption\_app137_e2e_drain.py \
    --media <10min.wav> --token-file <pkg>\bridge_token.txt \
    --out <arm dir> --drain-cap 300
```
🔴 **必须用包内 python**（APP-120 血泪：判「包能否用」要用客户解释器）。
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: EXT 仓库的 `tools/` 目录（提供 `bgkeep_e2e.py`）—— 只读借用。
DEFAULT_EXT_TOOLS = r'C:\Users\Trekker-PTL\live_dub_ext\tools'


def load_ext(ext_tools: str):
    """加载 EXT 的 `bgkeep_e2e` 模块（借用其渲染与媒体解码）。"""
    if ext_tools not in sys.path:
        sys.path.insert(0, ext_tools)
    return importlib.import_module('bgkeep_e2e')


def _np(st):
    """stats 消息里的 pipeline 计数（老 bridge 可能没有这个字段）。"""
    if not isinstance(st, dict):
        return None, None, None
    p = st.get('pipeline')
    if not isinstance(p, dict):
        return None, None, None
    return p.get('n_pending'), p.get('n_emitted'), p.get('n_submitted')


async def run_drain(a, ext):
    """与 EXT `run()` 同流程，但媒体结束后**排空到 n_pending==0**。"""
    x48 = ext.load_media(a.media, a.ffmpeg)
    if a.max_sec:
        x48 = x48[:, :int(a.max_sec * 48000)]
    x16 = ext.to16k(x48)
    dur = x48.shape[1] / 48000.0
    token = ''
    if os.path.exists(a.token_file):
        with open(a.token_file, encoding='utf-8') as fh:
            token = fh.read().strip()

    got = {"tts": [], "bg": [], "bg_status": [], "stats": None, "shift": {}}
    url = f'ws://127.0.0.1:{a.port}/'
    # 🔴 `ext` 必须解析到**桥接进程用的那一棵树**（包内 ext 还是 EXT 仓库）
    #    ⇒ extension_id 必须与桥接一致，否则 hello 的 origin 对不上。
    #    两棵树的布局不同：
    #      * 客户包：`<pkg>/ext/bridge/extension_id.py`  ⇒ `ext.bridge.extension_id`
    #      * EXT 仓库：`<repo>/ext/extension_id.py`      ⇒ `ext.extension_id`
    ext_root = os.path.abspath(a.bridge_root)
    if ext_root not in sys.path:
        sys.path.insert(0, ext_root)
    deps = os.path.join(ext_root, 'ext', '.runtime_deps')
    if os.path.isdir(deps) and deps not in sys.path:
        sys.path.insert(0, deps)
    resolve_extension_id = None
    for modname in ('ext.bridge.extension_id', 'ext.extension_id'):
        try:
            resolve_extension_id = importlib.import_module(modname).resolve_extension_id
            got['extension_id_module'] = modname
            break
        except Exception:
            continue
    if resolve_extension_id is None:
        raise RuntimeError('resolve_extension_id 找不到：bridge_root=%s' % ext_root)
    origin = 'chrome-extension://' + str(resolve_extension_id())

    import websockets
    # 🔴🔴🔴 **keepalive 必须关掉**（`ping_interval=None`）：
    #   桥接是**单线程 asyncio** ⇒ NPU 合成一段要 10–16 s ⇒ 事件循环在这期间
    #   **完全不转** ⇒ 客户端默认的 `ping_interval=20 / ping_timeout=20`
    #   ⇒ 桥接来不及回 pong ⇒ **客户端主动发 1011 keepalive ping timeout**
    #   ⇒ 连接被断 ⇒ 排空阶段拿不到 stats（实测 10 分钟臂 rc=1）。
    #   ⇒ 本工具**主动轮询 stats**（自己就是心跳）⇒ 关掉协议层 ping 无风险。
    async with websockets.connect(url, max_size=None, open_timeout=30, origin=origin,
                                  ping_interval=None) as ws:
        await ws.send(json.dumps({
            "type": "hello", "token": token, "role": "uplink", "source": "player",
            "sample_rate": 16000, "delay_sec": a.delay, "target_lang": a.target_lang,
            "voice": a.voice, "bg_keep": not a.bg_off, "bg_sample_rate": 48000,
            "bg_channels": 2, "capture_mode": "tabCapture"}))

        t0 = None

        async def reader():
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                now = time.perf_counter()
                k = m.get('type')
                if k == 'hello_ack':
                    got['hello_ack'] = {x: m.get(x) for x in
                                        ('delay_sec', 'bg_supported', 'bg_model', 'bg', 'mode')}
                elif k == 'tts':
                    got['tts'].append({
                        "id": str(m.get('id')), "t_start": m.get('t_start'),
                        "t_end": m.get('t_end'), "sr": m.get('sample_rate', 24000),
                        "pcm": m.get('pcm24k'), "tgt": m.get('tgt'), "src": m.get('src'),
                        "arr": now - t0 if t0 else None})
                elif k == 'bg':
                    got['bg'].append({
                        "t_start": m.get('t_start'), "n": m.get('n_frames'),
                        "sr": m.get('sample_rate'), "pcm": m.get('pcm'),
                        "arr": now - t0 if t0 else None})
                elif k == 'dub_shift':
                    got['shift'][str(m.get('id'))] = (
                        float(m.get('t_start')), now - t0 if t0 else None)
                elif k == 'bg_status':
                    got['bg_status'].append({
                        **{x: m.get(x) for x in ('state', 'device', 'reason', 'rtf', 'lead_sec')},
                        "at": round(now - t0, 2) if t0 else None})
                elif k == 'stats':
                    got['stats'] = m
                elif k == 'margin_dumped':
                    got['margin_dumped'] = True
                    got['margin_dump_path'] = m.get('path')

        rd = asyncio.create_task(reader())
        await asyncio.sleep(1.0)
        t0 = time.perf_counter()
        n_frames = int(np.ceil(dur * 10))
        bg_on = not a.bg_off
        toggled_off = toggled_on = False
        for k in range(n_frames):
            target = t0 + k * 0.1
            d = target - time.perf_counter()
            if d > 0:
                await asyncio.sleep(d)
            ts = k * 0.1
            if a.toggle_off_at is not None and bg_on and not toggled_off and ts >= a.toggle_off_at:
                bg_on, toggled_off = False, True
                await ws.send(json.dumps({"type": "bg_keep", "on": False}))
            if a.toggle_on_at is not None and not bg_on and not toggled_on and not a.bg_off and ts >= a.toggle_on_at:
                bg_on, toggled_on = True, True
                await ws.send(json.dumps({"type": "bg_keep", "on": True}))
            p16 = (np.clip(x16[k * 1600:(k + 1) * 1600], -1, 1) * 32767).astype('<i2')
            await ws.send(json.dumps({
                "type": "pcm", "seq": k, "sample_index": k * 1600,
                "pcm": __import__('base64').b64encode(p16.tobytes()).decode()}))
            if bg_on:
                p48 = (np.clip(x48[:, k * 4800:(k + 1) * 4800], -1, 1).T * 32767).astype('<i2')
                await ws.send(json.dumps({
                    "type": "pcm_bg", "seq": k, "sample_index_bg": k * 4800, "rate": 48000,
                    "ch": 2, "pcm": __import__('base64').b64encode(p48.tobytes()).decode()}))
            if k % 50 == 0:
                await ws.send(json.dumps({"type": "stats"}))

        # ── 媒体结束：先 flush，再**抓一份「排空前」的口径 ──────────────
        await ws.send(json.dumps({"type": "flush"}))
        t_end = time.perf_counter()
        media_end_rel = t_end - t0
        await asyncio.sleep(a.settle_wait)
        await ws.send(json.dumps({"type": "stats"}))
        await asyncio.sleep(1.0)
        stats_at_media_end = got.get('stats')
        npend_end, nemit_end, nsub_end = _np(stats_at_media_end)

        # ── 排空：直到 n_pending == 0 或用满 drain_cap ───────────────────
        # 🔴 **连接断了也要如实记录**（不能一断就崩 ⇒ 丢已采到的数据）
        series = []
        drain_start = time.perf_counter()
        drained = False
        disconnected = None
        npend = npend_end
        while True:
            try:
                await ws.send(json.dumps({"type": "stats"}))
                await asyncio.sleep(a.poll_sec)
            except Exception as e:
                disconnected = repr(e)
                break
            st = got.get('stats')
            npend, nemit, nsub = _np(st)
            series.append({
                'rel_sec': round(time.perf_counter() - t0, 2),
                'n_pending': npend, 'n_emitted': nemit, 'n_submitted': nsub})
            if npend is not None and npend == 0:
                drained = True
                break
            if time.perf_counter() - drain_start >= a.drain_cap:
                break
        drain_elapsed = round(time.perf_counter() - drain_start, 2)
        drain_rel = round(time.perf_counter() - t0, 2)
        stats_after_drain = got.get('stats')
        npend_final, nemit_final, nsub_final = _np(stats_after_drain)

        # 排空期间可能还有句子到齐 ⇒ 再抓一次逐句最终状态
        await asyncio.sleep(0.5)

        # 让桥接把逐段余量表落盘（含 tts_sec / speech_sec）
        # 目的：算出 synth_rtf = Σtts_sec ÷ Σspeech_sec（EXT 的 RTF_out）。
        # stats 消息里只有汇总口径（rtf_out 在 sync_rootcause 里，
        # 而 bridge 只在 dump_margin 落盘时把逐段分子分母写全）
        # ⇒ 只能靠这个 dump 拿逐段数据。
        # 落盘路径在臂目录里 ⇒ 客户包一个字节都不动。
        try:
            await ws.send(json.dumps({"type": "dump_margin"}))
            got['margin_dump_sent'] = True
            for _ in range(60):
                await asyncio.sleep(0.5)
                if got.get('margin_dumped'):
                    break
        except Exception as e:
            got['margin_dump_error'] = repr(e)

        rd.cancel()

    got['drain'] = {
        'media_end_rel_sec': round(media_end_rel, 2),
        'drain_elapsed_sec': drain_elapsed,
        'drain_rel_sec': drain_rel,
        'drained_to_zero': drained,
        'drain_cap_sec': a.drain_cap,
        'poll_sec': a.poll_sec,
        'n_pending_at_media_end': npend_end,
        'n_emitted_at_media_end': nemit_end,
        'n_submitted_at_media_end': nsub_end,
        'n_pending_after_drain': npend_final,
        'n_emitted_after_drain': nemit_final,
        'n_submitted_after_drain': nsub_final,
        'n_pending_series': series,
        # 🔴 如实记录「连接断了」这件事（不静默）
        'disconnected': disconnected,
        'definition': 'n_pending = 管线里还没出配音的句子数；排空 = 等到它归零。',
    }
    return x48, dur, got


def ext_tools_dir(a):
    return a.ext_tools


def add_fields(a, ext, x48, dur, got):
    """在 EXT 的 `bgkeep_e2e.json` 基础上补「排空」与「逐句最终 dub_late」。"""
    path = os.path.join(a.out, 'bgkeep_e2e.json')
    with open(path, encoding='utf-8') as fh:
        out = json.load(fh)

    D = a.delay
    per = []
    for t in got['tts']:
        if t.get('arr') is None or t.get('t_start') is None:
            continue
        per.append({
            'id': t.get('id'),
            't_start': round(float(t['t_start']), 3),
            'arr_rel_sec': round(float(t['arr']), 3),
            'dub_late_sec': round(float(t['arr']) - (float(t['t_start']) + D), 3),
        })
    per.sort(key=lambda x: x['t_start'])
    lates = [p['dub_late_sec'] for p in per]
    out['dub_late_final_per_sentence'] = per
    out['dub_late_final_summary'] = {
        'n': len(lates),
        'max': round(max(lates), 3) if lates else None,
        'p90': round(float(np.percentile(lates, 90)), 3) if lates else None,
        'p50': round(float(np.median(lates)), 3) if lates else None,
        'n_late_gt_0': sum(1 for v in lates if v > 0),
        'definition': 'dub_late_sec = 该句配音**到达**时刻 − 应播时刻(t_start + delay)；正值 = 迟到。',
    }
    out['drain'] = got.get('drain')

    # ── synth_rtf（= EXT 的 RTF_out）：Σtts_sec ÷ Σspeech_sec ──────────
    # 🔴 分子分母**只取「有 TTS 的段」**（与 EXT `compute_rtf_breakdown`
    #    同一口径）⇒ 口径自洽；分母为 0 ⇒ 给 None（**不臆造 0 或 1**）。
    margin_path = os.path.join(a.out, 'margin.json')
    synth = {
        'definition': ('synth_rtf = Σtts_sec ÷ Σspeech_sec（EXT 的 RTF_out）'
                       '= TTS 自身的 RTF；只统计「有 TTS 的段」'),
        'margin_json': margin_path if os.path.isfile(margin_path) else None,
    }
    if os.path.isfile(margin_path):
        try:
            with open(margin_path, encoding='utf-8') as fh:
                mj = json.load(fh)
            # 🔴 EXT 的 `rtf_breakdown` 已直接给出 `RTF_out`（权威口径）
            rb = mj.get('rtf_breakdown') or {}
            rows = mj.get('per_segment') or []
            tts_sum = 0.0
            spk_sum = 0.0
            n = 0
            per = []
            for r in rows:
                tts_s = float(r.get('tts_sec') or 0.0)
                spk_s = float(r.get('speech_sec') or 0.0)
                if tts_s <= 0:
                    continue
                tts_sum += tts_s
                spk_sum += spk_s
                n += 1
                per.append({'id': r.get('id'),
                            'tts_sec': round(tts_s, 4),
                            'speech_sec': round(spk_s, 4),
                            'rtf': round(tts_s / spk_s, 4) if spk_s > 0 else None})
            synth['n_segments_with_tts'] = n
            synth['sum_tts_sec'] = round(tts_sum, 4)
            synth['sum_speech_sec'] = round(spk_sum, 4)
            # 🔴 自算值与 EXT 的 `RTF_out` 交叉核对（两者应当相等；
            #    不等 ⇒ 说明口径漂了 ⇒ 如实保留两个数，不强行取一个）
            synth['synth_rtf'] = rb.get('RTF_out')
            synth['synth_rtf_recomputed'] = round(tts_sum / spk_sum, 4) if spk_sum > 0 else None
            synth['ext_rtf_out'] = rb.get('RTF_out')
            synth['ext_speech_over_src'] = rb.get('speech_over_src')
            synth['ext_tts_over_src'] = rb.get('tts_over_src')
            synth['cross_check_ok'] = (
                synth['synth_rtf'] is not None
                and synth['synth_rtf_recomputed'] is not None
                and abs(float(synth['synth_rtf']) - float(synth['synth_rtf_recomputed'])) <= 0.01)
            synth['per_segment'] = per
        except Exception as e:
            synth['error'] = repr(e)
    else:
        synth['error'] = 'margin.json not found'
    out['synth_rtf'] = synth

    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--media', required=True)
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--delay', type=float, default=20.0)
    ap.add_argument('--target-lang', default='zh')
    ap.add_argument('--voice', default='A')
    ap.add_argument('--token-file', required=True)
    ap.add_argument('--ffmpeg', default='ffmpeg')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-sec', type=float, default=None)
    ap.add_argument('--drain-cap', type=float, default=300.0,
                    help='排空上限（秒）；默认 300（APP-134 a 口径）')
    ap.add_argument('--poll-sec', type=float, default=2.0)
    ap.add_argument('--settle-wait', type=float, default=2.0,
                    help='媒体结束后到「排空前」快照之间的等待（秒）')
    ap.add_argument('--bg-off', action='store_true')
    ap.add_argument('--toggle-off-at', type=float, default=None)
    ap.add_argument('--toggle-on-at', type=float, default=None)
    ap.add_argument('--ext-tools', default=DEFAULT_EXT_TOOLS)
    ap.add_argument('--bridge-root', default='',
                    help='桥接进程用的代码树根（包目录或 EXT 仓库）；决定 `ext` 包解析到哪棵树')
    a = ap.parse_args()
    if not a.bridge_root:
        a.bridge_root = os.path.dirname(os.path.abspath(a.ext_tools))

    os.makedirs(a.out, exist_ok=True)
    ext = load_ext(a.ext_tools)
    x48, dur, got = asyncio.run(run_drain(a, ext))
    ext.report(a, x48, dur, got)
    out = add_fields(a, ext, x48, dur, got)
    brief = {k: v for k, v in out.items() if k not in ('dub_items', 'stats_full',
                                                      'dub_late_final_per_sentence')}
    print(json.dumps(brief, ensure_ascii=False))
    d = out.get('drain') or {}
    print('[drain] drained_to_zero=%s n_pending_at_media_end=%s n_pending_after_drain=%s '
          'drain_elapsed_s=%s' % (d.get('drained_to_zero'), d.get('n_pending_at_media_end'),
                                  d.get('n_pending_after_drain'), d.get('drain_elapsed_sec')))
    return 0 if d.get('drained_to_zero') else 2


if __name__ == '__main__':
    sys.exit(main())
