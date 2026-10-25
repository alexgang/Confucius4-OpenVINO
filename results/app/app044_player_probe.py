#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-044：播放链路探针 —— 定位「语音输出一点声音都没有」。

🔴 背景（用户 2026-10-25 19:00 反馈）：
   「语音输出无论 NPU/GPU 都听不到声音」。
   上一轮我把 `环形缓冲写入超时（已有 0，待写 138240）` 归因为「后台会话没有
   音频回调」—— **判错了**。本脚本用来把两件事分开：

   - **A. 容量约束**：`RingBuffer(capacity=sr*3)` = 72 000 样本（**3 s**），
     而 `write()` 是**整句原子写入**：`while count + n > cap` 才写。
     ⇒ 只要整句 **n > 72 000**（> 3 s 音频），`count + n > cap` **永远成立**
     ⇒ 等满 `timeout_s` 必然 `TimeoutError` ⇒ 该句「合成失败（已丢弃）」
     ⇒ **一声都不响**（与设备、精度、NPU/GPU 全都无关）。
     实测 BabelVox 一句 19 字 = **138 240 样本（5.76 s）** ⇒ 必然命中。

   - **B. 回调是否在跑**：写一段 **0.5 s**（12 000 样本，装得下）进真实 `Player`，
     然后看 `ring.level()` 是否被消费到 0。若被消费 ⇒ 设备与回调都正常，
     问题 100% 在 A。

判定：
   期望（修复前）  A = TIMEOUT（复现 bug）、B = 被消费（证明设备没问题）
   期望（修复后）  A = OK（整句写入成功）

用法（必须用**客户包** python）：
   `app044_player_probe.py`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5"
APP_DIR = os.path.join(PKG, "app")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app044_player_probe.json")

SR = 24000
CAP = SR * 3                     # 与前程一致：capacity=sr*3
SENT_N = 138240                  # 实测一句 19 字 BabelVox 输出（5.76 s）


def test_ring_only(timeout_s=2.0):
    """A：纯 RingBuffer，**没有消费者**。

    修复前：`TimeoutError 环形缓冲写入超时（容量 72000，已有 0，待写 138240）`
            —— 这是**容量约束**导致的必然失败（bug 本身）。
    修复后：`RuntimeError 播放回调没有消费音频…` —— 这是**明确的诊断报错**
            （没有消费者时本来就该报错，但不该伪装成「容量装不下」）。
    """
    import tts_worker as W
    rb = W.RingBuffer(capacity=CAP, timeout_s=timeout_s)
    t0 = time.perf_counter()
    res = {'name': 'A_ring_atomic_write', 'cap': CAP, 'n': SENT_N}
    try:
        rb.write([0.0] * SENT_N)
        res['ok'] = True
        res['sec'] = round(time.perf_counter() - t0, 2)
        res['note'] = '整句写入成功'
    except Exception as e:
        res['ok'] = False
        res['sec'] = round(time.perf_counter() - t0, 2)
        res['err'] = '%s: %s' % (type(e).__name__, e)
        res['is_capacity_bug'] = ('环形缓冲写入超时' in str(e))
        res['is_stall_diag'] = ('播放回调没有消费音频' in str(e))
    if res['ok']:
        print('  A 纯缓冲（无消费者）: OK  %.2fs（写入成功）' % res['sec'])
    else:
        kind = ('🔴 容量约束 bug' if res.get('is_capacity_bug')
                else ('✅ 明确的诊断报错（无消费者本应报错）'
                      if res.get('is_stall_diag') else '其它'))
        print('  A 纯缓冲（无消费者）: %.2fs  %s\n      %s'
              % (res['sec'], kind, res['err']))
    return res


def test_ring_with_consumer(timeout_s=3.0):
    """A2：有消费者（模拟音频回调按 1024/块消费）⇒ 长句**应该**能写进去。"""
    import threading
    import tts_worker as W
    rb = W.RingBuffer(capacity=CAP, timeout_s=timeout_s)
    stop = threading.Event()
    consumed = {'n': 0, 'cb': 0}

    def cb():
        while not stop.is_set():
            got = rb.read(1024)
            consumed['n'] += len(got)
            consumed['cb'] += 1
            time.sleep(1024.0 / SR)      # 真实播放节奏

    th = threading.Thread(target=cb, daemon=True)
    th.start()
    t0 = time.perf_counter()
    res = {'name': 'A2_ring_with_consumer', 'cap': CAP, 'n': SENT_N}
    try:
        rb.write([0.0] * SENT_N)
        res['ok'] = True
        res['write_s'] = round(time.perf_counter() - t0, 2)
    except Exception as e:
        res['ok'] = False
        res['write_s'] = round(time.perf_counter() - t0, 2)
        res['err'] = '%s: %s' % (type(e).__name__, e)
    # 等消费完
    t1 = time.perf_counter()
    while rb.level() > 0 and time.perf_counter() - t1 < 15:
        time.sleep(0.05)
    stop.set()
    res['consumed'] = consumed['n']
    res['callbacks'] = consumed['cb']
    print('  A2 有消费者: %s  写入 %.2fs  已消费 %d  回调 %d 次  %s'
          % ('OK' if res['ok'] else 'TIMEOUT', res['write_s'],
             res['consumed'], res['callbacks'], res.get('err', '')))
    return res


def test_real_player(short_ok=True):
    """B：真实 sounddevice 播放流 —— 证明设备能开、回调在消费。"""
    import tts_worker as W
    res = {'name': 'B_real_player'}
    try:
        p = W.Player(device=None, sr=SR)
    except Exception as e:
        res['ok'] = False
        res['err'] = '%s: %s' % (type(e).__name__, e)
        print('  B 真实播放流: 构造失败 %s' % res['err'])
        return res
    res['stream_open'] = p._stream is not None
    print('  B 真实播放流: stream=%s' % ('已打开' if p._stream else '未打开'))
    if p._stream is None:
        res['ok'] = False
        return res

    # 写一段 0.5 s（12 000 < 72 000，装得下）⇒ 看是否被消费
    n_short = SR // 2
    t0 = time.perf_counter()
    try:
        p.write([0.0] * n_short)
        res['short_write_ok'] = True
    except Exception as e:
        res['short_write_ok'] = False
        res['short_err'] = '%s: %s' % (type(e).__name__, e)
    lv0 = p.ring.level()
    time.sleep(1.2)
    lv1 = p.ring.level()
    res['level_after_write'] = lv0
    res['level_after_1_2s'] = lv1
    res['consumed'] = lv0 - lv1
    res['ok'] = (lv0 > 0 and lv1 < lv0)
    print('    0.5 s 写入: %s；写入后 level=%d，1.2 s 后 level=%d ⇒ 已消费 %d ⇒ %s'
          % ('OK' if res.get('short_write_ok') else 'FAIL', lv0, lv1,
             res['consumed'], '回调在工作' if res['ok'] else '🔴 回调没消费'))

    # 再写一句 5.76 s（整句 > 容量）⇒ 修复前必超时
    t1 = time.perf_counter()
    try:
        p.write([0.0] * SENT_N)
        res['long_write_ok'] = True
        res['long_write_s'] = round(time.perf_counter() - t1, 2)
        print('    5.76 s 整句写入: OK  %.2fs' % res['long_write_s'])
    except Exception as e:
        res['long_write_ok'] = False
        res['long_write_s'] = round(time.perf_counter() - t1, 2)
        res['long_err'] = '%s: %s' % (type(e).__name__, e)
        print('    5.76 s 整句写入: 🔴 %s  %.2fs'
              % (res['long_err'], res['long_write_s']))
    try:
        p.close()
    except Exception:
        pass
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-lock', action='store_true')
    ap.parse_args()
    sys.path.insert(0, APP_DIR)
    print('被测 App 目录:', APP_DIR)
    print('SR=%d  容量=%d 样本(%d s)  整句=%d 样本(%.2f s)'
          % (SR, CAP, CAP // SR, SENT_N, SENT_N / SR))
    print()

    # 设备清单（判断「有没有可用的输出设备」）
    try:
        import sounddevice as sd
        print('=== sounddevice 设备 ===')
        print('  default:', sd.default.device)
        for i, dd in enumerate(sd.query_devices()):
            if dd.get('max_output_channels', 0) > 0:
                print('  [%d] %s  out_ch=%d  sr=%s'
                      % (i, dd.get('name'), dd.get('max_output_channels'),
                         dd.get('default_samplerate')))
        print()
    except Exception as e:
        print('sounddevice 探测失败：%r' % (e,))

    print('=== A：整句原子写入的容量约束 ===')
    a = test_ring_only()
    print()
    print('=== A2：有消费者时能否写进长句 ===')
    a2 = test_ring_with_consumer()
    print()
    print('=== B：真实播放流 ===')
    b = test_real_player()

    res = {'sr': SR, 'cap': CAP, 'sent_n': SENT_N,
           'A_ring_no_consumer': a, 'A2_ring_with_consumer': a2,
           'B_real_player': b}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print()
    print('证据已落盘:', OUT)
    # 判定：A 是否复现「长句必然超时」；B 回调是否在消费
    print()
    print('=' * 60)
    print('A  无消费者时：', ('OK' if a['ok'] else
                            ('🔴 仍是容量约束 bug' if a.get('is_capacity_bug')
                             else '已改为明确诊断（正常）')))
    print('A2 有消费者时长句可写入？', 'YES' if a2['ok'] else 'NO（bug 在）')
    print('B  真实播放流回调在消费？', 'YES（设备正常）' if b.get('ok') else 'NO')
    print('B  5.76 s 整句可写入？',
          'YES' if b.get('long_write_ok') else 'NO（仍播不出声）')
    print('=' * 60)
    verdict = (not a.get('is_capacity_bug')) and a2['ok'] and b.get('ok') \
        and b.get('long_write_ok')
    print('总判定：', 'PASS（播放链路通）' if verdict else 'FAIL')
    res['verdict'] = bool(verdict)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return 0 if verdict else 1


if __name__ == '__main__':
    sys.exit(main())
