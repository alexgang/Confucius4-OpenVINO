"""app071 — 复现「TTS worker 故障（error）」并抓真实原因。

## 背景

用户在「📖 离线朗读…」点开始朗读后看到：
```
TTS worker 故障（error）⇒ 朗读中止
```
这条是**我的**离线朗读器的判据 `svc.state == 'error'`，它只说明「worker 级错误」，
**不含原因**。worker 级 error 只有两处来源（`tts_worker.py`）：

| 行 | 场景 | 现象 |
|---|---|---|
| L339 | `播放设备打开失败`（**连系统默认设备都打不开**才报） | 一句都不出声 |
| L1067 | `模型加载失败：{e}`（`_safe_load` 兜底） | state=error |

而且 CUDA 后端有个**误导性回落链**（`load()` → `_try_load_babelvox`）：
边车起不来 ⇒ 只打一行「BabelVox 引擎不可用」 ⇒ 回落 `_try_load_ov` →
再回落 torch 参考实现（`import tts_model`）⇒ 那一步必然 ImportError
⇒ 最终报出来的却是「**模型加载失败：No module named 'tts_model'**」——
**与真实原因（边车）毫无关系**。所以必须看完整日志，不能只看最后一句。

## 本脚本

用**真实 `TTSService`**（与 GUI 完全同一条路径）起 worker，逐行打印 `on_log`，
再提交一句、等播放，最后落盘完整日志。**不 import 被测模块的重依赖**原则在这里
不适用：我们要的就是真实集成路径（且 tts_service 只依赖标准库）。

⚠️ 会真的加载模型（CUDA 边车 ≈20–30 s）并占用 GPU 显存；不测时间，不写 timing。

用法：
    <PKG>\\python\\python.exe results\\app\\app071_tts_worker_error_probe.py \\
        [--device CUDA] [--precision f16] [--seconds 90]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# 🔴🔴 2026-10-27 §62：**「真的出声」的唯一判据来源**（APP-021⑦ 的直接执行）
#   ⚠️ 旧判据 `n_played >= 1` 是 APP-021 点名**作废**的弱判据
#   （`played` 只表示「写进缓冲」⇒ 不代表出声；且探针随后 `close()` 会 kill worker
#     ⇒ 那句话可能整句还在缓冲里就被杀掉 ⇒ 什么都没证明）。
#   ⇒ 现在用 APP-021 明文指定的硬判据：**n_read 增量 ≥ 本句样本数** 且 **峰值 > 1e-2**。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_audible_criterion import (  # noqa: E402
    audible_verdict, describe_criterion, evaluate_audible,
    played_snapshot, sentence_played)

HOME = r'C:\Users\Trekker-PTL'


def discover_pkg() -> str:
    cands = []
    for name in os.listdir(HOME):
        if name.startswith('Confucius4_LiveCaption_v') and \
                os.path.isdir(os.path.join(HOME, name, 'app')):
            try:
                cands.append((float(name.rsplit('_v', 1)[1]),
                              os.path.join(HOME, name)))
            except Exception:
                pass
    if not cands:
        raise SystemExit('找不到客户包')
    return sorted(cands)[-1][1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='CUDA')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--voice', default='A')
    ap.add_argument('--seconds', type=float, default=120.0)
    ap.add_argument('--text', default='这是一次离线朗读测试，用来确认语音输出是否正常。')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    pkg = discover_pkg()
    app_dir = os.path.join(pkg, 'app')
    sys.path.insert(0, app_dir)
    os.environ.setdefault('LIVECAP_PKG', pkg)
    print(f'[probe] 客户包 = {pkg}')

    import tts_service
    import audio_source

    # 输出设备：与 GUI 完全一致（取默认输出端点的 WASAPI id）
    outs = audio_source.list_output_devices()
    oid = audio_source.default_output_device_id()
    print(f'[probe] 输出端点 id = {oid}')
    print(f'[probe] 可选输出 {len(outs)} 个；第一个 = {outs[0][1] if outs else "无"}')
    print(f'[probe] 参数 device={args.device} precision={args.precision} '
          f'voice={args.voice}')
    print('-' * 78, flush=True)

    t0 = time.time()
    lines = []

    def on_log(m):
        s = f'{time.time() - t0:7.2f}s {m}'
        print(s, flush=True)
        lines.append(s)

    svc = None
    try:
        svc = tts_service.TTSService(
            device=args.device, voice=args.voice, out_device=oid,
            precision=args.precision, on_log=on_log)
        # ── 等 ready / error ──
        t_end = time.time() + args.seconds
        submitted = False
        while time.time() < t_end:
            st = svc.stats()
            state = st.get('state')
            if state == 'error':
                break
            if state == 'ready' and not submitted:
                print(f'{time.time() - t0:7.2f}s >>> state=ready，提交一句', flush=True)
                # 🔴🔴 §62：**提交前**抓快照 ⇒ 后面用**相对增量**判「本句播完」
                #   （`n_played` 是累计计数 ⇒ 用常量阈值 `>= 1` 会把
                #    「历史上播过的别的句」当成本句的证据 ⇒ 假通过）。
                played_before, tel_id_before = played_snapshot(st)
                svc.submit(args.text, seg=0)
                submitted = True
                t_end = min(t_end, time.time() + 90)
            # 🔴🔴 2026-10-27 §62 修：**不再**用 `n_played >= 1` 当「已出声」判据。
            #   旧行为：见 played 就 break → 下面 finally 里 `svc.close()` 会 kill worker
            #   ⇒ **本句遥测还没落下来** ⇒ 什么硬数字都没拿到 ⇒ 什么都没证明。
            #   ⇒ 现在：**必须等到本句遥测齐了**才停（相对增量 + 新遥测）。
            if submitted:
                done, why = sentence_played(st, played_before, tel_id_before)
                if done:
                    print(f'{time.time() - t0:7.2f}s >>> 本句已播完（{why}）',
                          flush=True)
                    break
            time.sleep(0.3)

        st = svc.stats()
        print('-' * 78)
        print(f'[probe] 最终 state={st.get("state")} '
              f'played={st.get("n_played")} dropped={st.get("n_dropped")} '
              f'submitted={st.get("n_submitted")} '
              f'first_packet={st.get("first_packet_s")}')
        # 🔴🔴 2026-10-27 §62 修（APP-021⑦ 的**直接执行**）：
        #   APP-021 L256 明文：「app071 的判据改成：n_read 增量 ≥ 本句样本数，
        #   并且本句峰值 > 1e-2」+「不要用 played ≥ 1 宣称能出声」
        #   ⇒ 该要求**从未被执行** ⇒ 本轮补上（这是「ACK 了但没做完」的真实欠账）。
        tel = st.get('last_telemetry') or {}
        verdict = audible_verdict(tel)
        print('[probe] 判据原始字段：%s' % describe_criterion(tel))
        print(f'[probe] 判定：{verdict}')
        lines.append('[probe] 判据原始字段：%s' % describe_criterion(tel))
        lines.append(f'[probe] 判定：{verdict}')
    finally:
        if svc is not None:
            try:
                svc.close()
            except Exception:
                pass

    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'app', 'app071_tts_worker_probe.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'# app071 TTS worker 探测  {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'# pkg={pkg} device={args.device} precision={args.precision} '
                f'out_device={oid}\n')
        f.write('\n'.join(lines) + '\n')
    print(f'\n[probe] 日志已写 {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
