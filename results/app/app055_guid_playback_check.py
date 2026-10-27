#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-055：**决定性验证** —— 用 GUI 真实传的那种「WASAPI 端点 id」驱动播放层，
看它到底能不能出声（§42.3 的修复）。

背景：GUI 的「语音输出 → 输出设备」传的是 `soundcard` 的 `s.id`
（= `IMMDevice::GetId()` = `{0.0.0.00000000}.{guid}`），而 `sounddevice` 只认
int 索引或设备名子串 ⇒ 旧实现 `Player` 直接透传 ⇒
`ValueError: No output device matching` ⇒ 播放流打不开 ⇒ **一句都不出声**。

本脚本做三件事（**不加载任何模型、不占 GPU、不取机器锁**）：
  1. **对照组**：直接把 GUID 交给 `sd.OutputStream(device=…)` ⇒ 预期 `ValueError`（复现旧行为）；
  2. **实验组**：`Player(device=<GUID>)` ⇒ 预期流能打开，日志出现「实际输出: …」；
  3. 写 0.5 s 正弦进环形缓冲 ⇒ 等回调消费 ⇒ 断言 `n_cb>0` 且缓冲被取空
     （= ① 层判据：PortAudio 回调真的在消费）。

🔴 纪律：**不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino）
  ⇒ 用 `ast` 抽出 `RingBuffer` / `Player` / `resolve_out_device` /
  `_match_output_index` / `_describe_out` 原文，`exec` 到独立命名空间，
  并补齐它们依赖的 `log` / `emit` / `SR` / `CHUNK_SAMPLES`。

用法（客户包 python）：
    python results/app/app055_guid_playback_check.py            # 用真实默认端点 id
    python results/app/app055_guid_playback_check.py --sec 1.0
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
OUT = os.path.join(HERE, 'app055_guid_playback_check.json')

WANT = ('RingBuffer', 'Player', '_match_output_index', 'resolve_out_device',
        '_describe_out')


def load_nodes(path, names, extra=None):
    """抽指定顶层 ClassDef / FunctionDef 的原文并 exec（不 import 被测模块）。

    🔴 必须给抽出的小模块补一行 `from __future__ import annotations`：
       原文有它 ⇒ 注解是**惰性字符串**；抽出来单独编译就没有了 ⇒
       `Optional[str]` 之类会在 def 时**求值** ⇒ NameError。补上即等价。
    🔴 `extra` 用来预先补上被抽代码在**类体/默认参数**里就用到的模块级常量
       （实测 `RingBuffer.__init__(capacity=SR*3)` 会在类体求值 ⇒ 必须先有 `SR`）。
    """
    src = io.open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {'threading': __import__('threading'), 'time': __import__('time'),
          'deque': __import__('collections').deque}
    ns.update(extra or {})
    future = ast.ImportFrom(module='__future__',
                            names=[ast.alias(name='annotations')], level=0)
    found = []
    for node in tree.body:
        nm = getattr(node, 'name', None)
        if nm in names and isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            mod = ast.Module(body=[future, node], type_ignores=[])
            ast.fix_missing_locations(mod)   # 手工构造的 ImportFrom 没有 lineno
            exec(compile(mod, '<%s:%s>' % (path, nm), 'exec'), ns)
            found.append(nm)
    return ns, found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--sec', type=float, default=0.5, help='写入时长（秒）')
    args = ap.parse_args()

    import soundcard as sc
    import sounddevice as sd

    ns, found = load_nodes(SRC, WANT, extra={
        'SR': 22050, 'CHUNK_SAMPLES': 1024, 'Optional': None,
    })
    missing = [n for n in WANT if n not in found]
    if missing:
        print('🔴 抽不到：%s（源码改名了？）' % missing)
        return 2
    # 补齐被抽函数依赖的模块级符号（运行期用到的）
    logs = []
    ns['log'] = lambda m: (logs.append(m), print('    ' + m))[0]
    ns['emit'] = lambda o: logs.append('EMIT %s' % o)
    Player = ns['Player']

    spk = sc.default_speaker()
    guid = spk.id
    print('✅ 已抽出：%s（未 import tts_worker）' % ', '.join(found))
    print('soundcard 默认端点：%s\n   id = %s' % (spk.name, guid))

    rec = {'guid': guid, 'speaker': spk.name}

    # ── ① 对照组：旧行为（把 GUID 直接交给 sounddevice）────────────────
    print('\n=== ① 对照组：sd.OutputStream(device=<GUID>)  ← 旧实现的做法 ===')
    try:
        st = sd.OutputStream(samplerate=22050, channels=1, dtype='float32',
                             device=guid)
        st.start()
        st.stop()
        st.close()
        print('  ⚠️ 竟然打开了（说明本机 sounddevice 接受了 GUID）')
        rec['control_error'] = None
    except Exception as e:
        print('  ✅ 复现旧故障：%s: %s' % (type(e).__name__, e))
        rec['control_error'] = '%s: %s' % (type(e).__name__, e)

    # ── ② 实验组：修复后的 Player（GUID → 索引）──────────────────────
    print('\n=== ② 实验组：Player(device=<GUID>)  ← 修复后的实现 ===')
    ok = False
    try:
        p = Player(device=guid, sr=22050)
        print('  dev=%-6r  %s' % (p.out_sd_device, p.out_how))
        if p._stream is None:
            print('  🔴 播放流仍未打开')
        else:
            n = int(args.sec * 22050)
            wav = [0.25 * math.sin(2 * math.pi * 440.0 * i / 22050.0)
                   for i in range(n)]
            print('  ③ 写入 %.2f s 正弦…' % args.sec)
            p.write(wav)
            time.sleep(args.sec + 0.6)          # 等回调把缓冲吃空
            lvl = p.ring.level()
            cb = p.n_cb
            print('  回调次数 n_cb = %d；缓冲剩余 = %d 样本' % (cb, lvl))
            ok = cb > 0 and lvl == 0
            print('  %s' % ('✅ ① 层通过：回调在消费、缓冲被吃空（真出声）'
                            if ok else '🔴 回调没跑或缓冲没被消费'))
            rec.update({'resolved_dev': p.out_sd_device, 'how': p.out_how,
                        'out_desc': p.out_desc, 'n_cb': cb, 'ring_left': lvl})
            p.close()
    except Exception as e:
        print('  🔴 异常：%s: %s' % (type(e).__name__, e))
        rec['player_error'] = '%s: %s' % (type(e).__name__, e)

    rec['verdict'] = bool(ok)
    # 🔴🔴 2026-10-27 §62 修：**撤回「⇒ 能出声」的过度断言**（APP-021 的口径）。
    #   本脚本只验了 **Player 链路**（GUID→索引、回调在消费、缓冲被吃空）
    #   ⇒ 它**不能**证明「TTS 合成 + 整句链路出声」⇒ 也不能证明「用户听得见」。
    rec['verdict_note'] = (
        '修复有效：GUID 被解析成播放索引，回调在消费 '
        '⇒ **Player 链路级通**（⚠️ 不代表 TTS 整句出声，更不代表用户听得见）'
        if ok else
        '仍未通过：见 player_error / 回调次数')
    io.open(OUT, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结论：%s — %s' % ('PASS' if ok else 'FAIL', rec['verdict_note']))
    print('结果：', OUT)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
