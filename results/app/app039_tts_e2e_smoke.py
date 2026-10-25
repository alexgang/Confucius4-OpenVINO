#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-039：**TTS 语音输出端到端冒烟**（用户反馈「语音输出无法工作」的验收）。

🔴 要回答的问题：
   修完「移除 NVIDIA 选项 + 设备预检 + 精度真正生效 + 状态监视」之后，
   **语音输出到底能不能出声**？
   ⇒ 只证明「下拉里没有坏选项」是不够的，必须看到
      `ready` → `first_packet` → `played` 三件事**真的发生**。

判据（按顺序，全部要出现）：
  1. `TTSService.state == 'ready'`（7 个 IR 全部编过 ⇒ 引擎真起来了）；
  2. 收到 `first_packet`（首包延迟，说明**合成**真的出了音频）；
  3. 收到 `played`（说明**播放**链路通了）。

⚠️ 与 `app024_gui_smoke.py` 的分工：
   app024 验「**下拉内容**对不对」（纯构造，不加载模型）；
   本脚本验「**真加载 + 真合成 + 真播放**」（会占 GPU/CPU，必须持锁）。

🔴 必须用**客户包**的 python：
   `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\python.exe`
用法：
   `app039_tts_e2e_smoke.py --device GPU.0 --precision f16`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
APP_DIR = os.path.join(PKG, "app")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "app039_tts_e2e_smoke.json")

# 合成句（**不用真实语料**，守「写举例一律用合成句」铁律）
SENTENCE = "这是一次语音输出的自测，用来确认朗读功能可以正常工作。"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="GPU.0")
    ap.add_argument("--precision", default="f16")
    ap.add_argument("--voice", default="A")
    ap.add_argument("--timeout", type=float, default=1800.0,
                    help="等 ready 的上限（首帧编译慢，给足）")
    ap.add_argument("--play-timeout", type=float, default=180.0)
    ap.add_argument("--no-lock", action="store_true",
                    help="不取共享机器锁（仅调试用；正式测量必须持锁）")
    args = ap.parse_args()

    sys.path.insert(0, APP_DIR)
    from tts_service import TTSService

    if args.no_lock:
        return _run(args, TTSService)

    # 🔴 会占 GPU/CPU 做编译 + 推理 ⇒ 必须持共享机器锁（不污染其它模块计时）
    sys.path.insert(0, r"C:\Users\Trekker-PTL\confucius4-openvino")
    from machine_lock_app import LockHeld
    with LockHeld(module='app', timeout=1800, poll=20.0, verbose=True) as lk:
        print('[lock] 已持锁：%r' % (lk.payload,), flush=True)
        return _run(args, TTSService)


def _run(args, TTSService) -> int:
    print("被测 App 目录:", APP_DIR)
    print("设备=%s 精度=%s 音色=%s" % (args.device, args.precision, args.voice))
    print("合成句:", SENTENCE)
    print()

    logs = []

    def on_log(m):
        logs.append(str(m))
        print("  [log]", m)

    t0 = time.perf_counter()
    svc = TTSService(device=args.device, voice=args.voice,
                     precision=args.precision, on_log=on_log)
    try:
        # ── ① 等 ready ──
        print("=== ① 等引擎 ready ===")
        while time.perf_counter() - t0 < args.timeout:
            if svc.state == 'ready':
                break
            if svc.state == 'error':
                break
            time.sleep(1.0)
        load_s = round(time.perf_counter() - t0, 2)
        print("state=%s  加载耗时=%.1f s  err=%r"
              % (svc.state, load_s, svc.err))
        ready_ok = (svc.state == 'ready')

        result = {
            'device': args.device, 'precision': args.precision,
            'voice': args.voice, 'state': svc.state,
            'err': repr(svc.err), 'load_s': load_s,
            'ready': ready_ok, 'first_packet': None, 'played': False,
            'events': [], 'logs': logs,
        }
        if not ready_ok:
            print()
            print("!! 引擎没起来 ⇒ 语音输出**不可用**")
            _dump(result)
            return 1

        # ── ② 提交一句 + 等 first_packet / played ──
        print()
        print("=== ② 提交一句，等合成 + 播放 ===")
        t1 = time.perf_counter()
        svc.submit(SENTENCE, seg=0)
        got_first, got_played = None, False
        while time.perf_counter() - t1 < args.play_timeout:
            evs = svc.pop_outbox() or []
            for ev in evs:
                result['events'].append(ev)
                kind = ev.get('kind')
                print("  [event] %r" % (ev,))
                if kind == 'first_packet' and got_first is None:
                    got_first = ev.get('latency_s')
                elif kind == 'played':
                    got_played = True
            if got_first is not None and got_played:
                break
            time.sleep(0.5)

        result['first_packet'] = got_first
        result['played'] = got_played
        result['synth_s'] = round(time.perf_counter() - t1, 2)

        print()
        print("首包延迟 = %r s" % (got_first,))
        print("播放完成 = %s" % got_played)
        ok = (got_first is not None) and got_played
        print()
        print("=" * 60)
        print("TTS 端到端：", "PASS（语音输出真能用）" if ok else "FAIL")
        print("=" * 60)
        _dump(result)
        return 0 if ok else 1
    finally:
        try:
            svc.close()
        except Exception as e:
            print("close 异常（忽略）：%r" % (e,))


def _dump(result):
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("证据已落盘:", OUT)


if __name__ == "__main__":
    sys.exit(main())
