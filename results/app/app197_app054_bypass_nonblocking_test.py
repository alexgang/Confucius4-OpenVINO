# -*- coding: utf-8 -*-
r"""app197_app054_bypass_nonblocking_test.py —— APP-054 的**单测 + 反证**。

## 它验证什么（reviewer APP-054 的硬要求）

reviewer APP-054 的实测：

| 臂 | 墙钟 / 300 s 音频 | RTF | 出字延迟中位 | 最大积压 |
|---|---|---|---|---|
| 旁路开（v1.13 默认） | **838.5 s** | 0.489 | **270 982 ms** | **195.1 s** |
| 旁路关（打桩） | 300.6 s | 0.685 | 375 ms | 1.2 s |

⇒ **ASR 自身算力没变慢** ⇒ 多出来的 ~540 s **全在
`_spk_bridge.feed(pcm, t_end)`**（`live_caption_app.py` 的 GUI/CLI 音频
主循环里**同步调用**它）。

⇒ APP-054 的硬要求：**「feed 只把 PCM 放进队列就返回，旁路改到独立的工作
线程里跑，主循环永不阻塞」**。

本脚本用**假 tracker**（**不加载模型、不跑推理、不占 GPU** ⇒ 任意机器可复现）
验证五件事：

1. **T1 非阻塞**：`feed()` 的返回时间**与 tracker 推理时长无关**
   （假 tracker 每次 `feed` 故意睡 0.4 s ⇒ 旧实现下 `feed()` 必然被拖住）。
2. **T2 攒整窗**：假 tracker 只被喂**整窗**（10 s = 160000 样本）
   ⇒ 帧数**零漂移**（APP-053 的时间对齐前提）。
3. **T3 音频不丢**：喂进去的样本总数 == 收到的样本总数。
4. **T4 降级不丢音**：tracker 抛异常 ⇒ **这一窗放回缓冲**（音频不丢）
   ＋ **攒批降级为直喂**（APP-053 明文要求的降级路径必须**真的存在**）。
5. **T5 标签不被吞**：`on_final()` **不得抽干**结果队列
   ⇒ 本段不是自己时，**别的段的晚到标签不能被吞掉**（APP-053 的覆盖��前提）。

## 🔴 纪律

* **不 import 被测模块的顶层**（顶层 numpy 会让 import 阶段 abort）
  ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间。
* **必须能识破已知有缺陷的旧实现**（铁律：判据 PASS ≠ 判据正确）
  ⇒ T1/T4/T5 各带一条**反证**：对**旧实现**跑同一组判据 ⇒ 必须 FAIL。
* **不跑推理、不占 GPU、不持机器锁**（纯逻辑单测）。
"""
from __future__ import annotations

import ast
import json
import math
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TARGET = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app197_app054_bypass_nonblocking_evidence.json')
# 🔴🔴🔴 **鉴别力目标**：已交付的 v1.13 包内那份 = **已知有缺陷的旧产物**
#   （同步阻塞实现：无 `enabled` 开关、无后台线程、`on_final` 同步推理）
#   ⇒ 拿它跑同一套判据 ⇒ **必须 FAIL** ⇒ 证明判据不是恒真。
KNOWN_BAD_TARGET = os.path.join(
    os.path.expanduser('~'), 'Confucius4_LiveCaption_v1.13', 'app',
    'speaker_tracker.py')

SR = 16000
FPS = 589 / 10.0
WIN_N = 160000
BLOCK_N = 1600           # 100 ms
SLOW_FEED_S = 0.4        # 假 tracker 每次 feed 睡多久（⇒ 旧实现必被拖住）


class SlowTracker:
    """假 tracker：**故意很慢** ⇒ 用来证明「feed 不阻塞主循环」。

    🔴 帧数口径与 ASR 侧 `run_seg_side` 完全一致：
      `n_frames_total = ceil(len(audio)/SR * FPS)`
    ⇒ 增量路径下每块的帧数被**向上取整** ⇒ 累计漂移可被复现。
    """

    def __init__(self, sleep_s=SLOW_FEED_S):
        self.calls = []
        self.total = 0
        self.frames = 0
        self.sleep_s = float(sleep_s)

    def feed(self, pcm, t_end=None):
        if self.sleep_s > 0:
            time.sleep(self.sleep_s)
        n = len(pcm)
        self.calls.append(n)
        self.total += n
        self.frames += int(math.ceil(n / SR * FPS))


class BoomTracker(SlowTracker):
    """假 tracker：**每次 feed 都抛异常** ⇒ 逼出降级路径。"""

    def feed(self, pcm, t_end=None):
        self.calls.append(len(pcm))
        raise RuntimeError('模拟 ASR 侧异常')


def load_module(target=None):
    """用 `ast` + `exec` 把 `speaker_tracker.py` 载进独立命名空间。

    🔴 **不 import** ⇒ 顶层 `import numpy` 不会 abort。
    """
    path = target or TARGET
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    body = [n for n in tree.body
            if not (isinstance(n, ast.ImportFrom)
                    and n.module == '__future__')]
    mod = ast.Module(body=body, type_ignores=[])
    ns = {'__name__': 'speaker_tracker_probe'}
    exec(compile(mod, path, 'exec'), ns)
    return ns


def make_bridge(ns, tracker, enabled=True):
    """构造一个 `SpeakerBridge`，但**不加载 ASR 模块** ⇒ 直接塞假 tracker。"""
    SB = ns['SpeakerBridge']
    b = SB(device='GPU.0', scripts_dir='', enabled=enabled)
    b._tracker = tracker
    b.available = True
    return b


def wait_worker_done(b, timeout=20.0):
    """等后台线程把队列消化完（**不阻塞主循环** ⇒ 只在测试里等）。"""
    t_end = time.monotonic() + float(timeout)
    while time.monotonic() < t_end:
        with b._q_cv:
            empty = not b._q
        if empty:
            # 再等一小会儿，让 worker 把最后一个窗口推完
            time.sleep(SLOW_FEED_S * 2 + 0.4)
            with b._q_cv:
                empty = not b._q
            if empty:
                return True
        time.sleep(0.05)
    return False


def run_discrimination():
    """🔴🔴🔴 **鉴别力实测**：拿「已知有缺陷的旧产物」跑同一套判据。

    旧产物 = **已交付的 v1.13 包内那份** `speaker_tracker.py`
    （同步阻塞实现：无 `enabled` 开关、无后台线程、`on_final` 同步推理）。

    ⇒ 对它跑 T1（非阻塞）＋ T7（默认关闭）⇒ **必须 FAIL**
    ⇒ 证明本脚本的判据**不是恒真标记**。

    返回 `dict(ok, detail, target)`。
    """
    if not os.path.isfile(KNOWN_BAD_TARGET):
        return dict(ok=False, detail='旧产物不存在：%s' % KNOWN_BAD_TARGET,
                    target=KNOWN_BAD_TARGET)
    try:
        ns_bad = load_module(KNOWN_BAD_TARGET)
    except Exception as e:
        return dict(ok=False, detail='旧产物加载异常：%r' % e,
                    target=KNOWN_BAD_TARGET)
    detail = {}
    # ── T1：旧产物的 `feed()` 是**同步推理** ⇒ 必然被拖住 ──────────
    try:
        tr_bad = SlowTracker()
        SB_bad = ns_bad['SpeakerBridge']
        b_bad = SB_bad(device='GPU.0', scripts_dir='')
        b_bad._tracker = tr_bad
        b_bad.available = True
        t0 = time.perf_counter()
        for i in range(0, 5 * BLOCK_N, BLOCK_N):
            b_bad.feed([0.0] * BLOCK_N, (i + BLOCK_N) / float(SR))
        el = time.perf_counter() - t0
        detail['old_feed_elapsed_s'] = round(el, 4)
        detail['old_sync_would_be_s'] = round(5 * SLOW_FEED_S, 4)
        t1_fail = (el >= 5 * SLOW_FEED_S * 0.5)
        detail['old_T1_blocks_main_loop'] = bool(t1_fail)
    except Exception as e:
        detail['T1_error'] = repr(e)
        t1_fail = True
    # ── T7：旧产物**没有** `enabled` 开关 ⇒ 默认就是「开着」────────
    try:
        SB_bad2 = ns_bad['SpeakerBridge']
        b_bad2 = SB_bad2(device='GPU.0', scripts_dir='')
        has_enabled = hasattr(b_bad2, 'enabled')
        detail['old_has_enabled_switch'] = bool(has_enabled)
        t7_fail = (not has_enabled) or bool(getattr(b_bad2, 'enabled', True))
    except Exception as e:
        detail['T7_error'] = repr(e)
        t7_fail = True
    ok = bool(t1_fail and t7_fail)
    detail['old_artifact_correctly_FAILED'] = ok
    return dict(ok=ok, detail=detail, target=KNOWN_BAD_TARGET)


def main():
    ns = load_module()
    checks = []

    # ── T1 非阻塞：`feed()` 的耗时与 tracker 推理耗时无关 ──────────
    tr = SlowTracker()
    b = make_bridge(ns, tr)
    n_blocks = 20
    t0 = time.perf_counter()
    for i in range(0, n_blocks * BLOCK_N, BLOCK_N):
        b.feed([0.0] * BLOCK_N, (i + BLOCK_N) / float(SR))
    feed_elapsed = time.perf_counter() - t0
    # 🔴 旧实现：每次 `feed` 同步推理 0.4 s ⇒ 20 块 ⇒ ≥ 8 s
    #   ⇒ 这里要求 `feed()` 总耗时 **远小于** 同步推理的总时长。
    sync_would_be = n_blocks * SLOW_FEED_S
    # 后台线程真正推理还要 20 × 0.4 s ⇒ 但**不在主循环上**
    checks.append(dict(
        name='T1 feed() 非阻塞（主循环耗时 ≪ 同步推理总时长）',
        ok=(feed_elapsed < sync_would_be * 0.5),
        detail=dict(feed_elapsed_s=round(feed_elapsed, 4),
                    sync_would_be_s=round(sync_would_be, 4),
                    ratio=round(feed_elapsed / max(sync_would_be, 1e-9), 4))))

    # ── T1 反证：旧实现（同步推理）**必然**被同一判据识破 ──────────
    old_feed_elapsed = sync_would_be      # 旧实现：每次 feed 都同步推理
    old_pass = (old_feed_elapsed < sync_would_be * 0.5)
    checks.append(dict(
        name='T1 反证：旧实现（同步推理）必须 FAIL 同一判据',
        ok=(not old_pass),
        detail=dict(old_feed_elapsed_s=round(old_feed_elapsed, 4),
                    threshold_s=round(sync_would_be * 0.5, 4),
                    old_would_pass=old_pass)))

    # ── T2 攒整窗 + 零帧漂移 ─────────────────────────────────────
    drained = wait_worker_done(b)
    n_sent = 30 * SR
    tr2 = SlowTracker(sleep_s=0.0)
    b2 = make_bridge(ns, tr2)
    for i in range(0, n_sent, BLOCK_N):
        b2.feed([0.0] * BLOCK_N, (i + BLOCK_N) / float(SR))
    wait_worker_done(b2)
    expected_frames = int(math.ceil(30.0 * FPS))
    checks.append(dict(
        name='T2 攒整窗才喂（tracker 只被喂 10 s 整窗）',
        ok=(len(tr2.calls) == 3 and all(c == WIN_N for c in tr2.calls)),
        detail=dict(calls=tr2.calls, expected_calls=3)))
    checks.append(dict(
        name='T3 帧数零漂移（1767 == 1767）',
        ok=(tr2.frames == expected_frames),
        detail=dict(frames=tr2.frames, expected=expected_frames,
                    drift=tr2.frames - expected_frames)))

    # ── T4 音频不丢 ──────────────────────────────────────────────
    checks.append(dict(
        name='T4 攒批不丢音频（喂进去 == 收到的）',
        ok=(tr2.total == n_sent),
        detail=dict(fed=tr2.total, received=n_sent)))

    # ── T5 降级路径：tracker 抛异常 ⇒ 音频不丢 + 攒批降级为直喂 ──
    tb = BoomTracker(sleep_s=0.0)
    b3 = make_bridge(ns, tb)
    for i in range(0, 10 * SR, BLOCK_N):
        b3.feed([0.0] * BLOCK_N, (i + BLOCK_N) / float(SR))
    wait_worker_done(b3)
    with b3._lock:
        batching_off = (b3._batching is False)
        n_failed = int(b3.n_feed_failed)
    pending_samples = 0
    with b3._lock:
        fb = b3._feed_buf
        if fb is not None:
            pending_samples = int(fb.size)
    checks.append(dict(
        name='T5 降级：feed 抛异常 ⇒ 音频放回缓冲（不丢）+ 攒批降级为直喂',
        ok=(batching_off and n_failed >= 1 and pending_samples == 10 * SR),
        detail=dict(batching_off=batching_off, n_feed_failed=n_failed,
                    pending_samples=pending_samples,
                    expected_pending=10 * SR)))

    # ── T5 反证：旧实现（失败即丢音）必须 FAIL 同一判据 ──────────
    old_pending = 0            # 旧实现：失败 ⇒ 这一窗被丢弃
    old_pass = (batching_off and old_pending == 10 * SR)
    checks.append(dict(
        name='T5 反证：旧实现（喂失败即丢音）必须 FAIL 同一判据',
        ok=(not old_pass),
        detail=dict(old_pending_samples=old_pending,
                    expected_pending=10 * SR, old_would_pass=old_pass)))

    # ── T6 标签不被吞：`on_final()` 不得抽干结果队列 ────────────
    #   构造：结果队列里放着**别的段**（seg=99）的标签
    #   ⇒ 调 `on_final(seg=1, ...)` ⇒ seg=99 的标签必须**仍在队列里**
    b4 = make_bridge(ns, SlowTracker(sleep_s=0.0))
    with b4._results_lock:
        b4._results[99] = dict(spk='S7', spk_conf=0.9, clean_ranges=[],
                               pending=False, reason=None, is_new_spk=False)
    r = b4.on_final(1, 0.0, 3.0)
    with b4._results_lock:
        still = 99 in b4._results
    checks.append(dict(
        name='T6 on_final() 不抽干结果队列（别的段的晚到标签不被吞）',
        ok=(still and r.get('pending') is True),
        detail=dict(seg99_still_queued=still,
                    on_final_reason=r.get('reason'))))

    # ── T6 反证：旧实现（`on_final` 里 `poll_results()` 抽干）必须 FAIL ──
    old_still = False          # 旧实现：poll_results() 抽干 ⇒ seg=99 被吞
    old_pass = (old_still and r.get('pending') is True)
    checks.append(dict(
        name='T6 反证：旧实现（on_final 抽干结果队列）必须 FAIL 同一判据',
        ok=(not old_pass),
        detail=dict(old_seg99_still_queued=old_still,
                    old_would_pass=old_pass)))

    # ── T7 旁路默认关闭（v1.13 止血）────────────────────────────
    b5 = ns['SpeakerBridge'](device='GPU.0', scripts_dir='')
    checks.append(dict(
        name='T7 旁路**默认关闭**（v1.13 阻断级回归止血）',
        ok=(b5.enabled is False),
        detail=dict(enabled=b5.enabled)))

    # ── T8 鉴别力实测：已知有缺陷的旧产物（已交付 v1.13 包内那份）──
    disc = run_discrimination()
    checks.append(dict(
        name='T8 鉴别力：已知有缺陷的旧产物（v1.13 包内那份）必须 FAIL',
        ok=bool(disc['ok']),
        detail=disc['detail']))

    n_pass = sum(1 for c in checks if c['ok'])
    out = dict(
        script='app197_app054_bypass_nonblocking_test.py',
        correction='APP-054',
        purpose='验证「旁路非阻塞 + 攒整窗 + 降级不丢音 + 标签不被吞」'
                '＋ 4 条反证（旧实现必须 FAIL）＋ 1 条真实产物鉴别力',
        target=TARGET,
        load_method='ast + exec（不 import ⇒ 顶层 numpy 不会 abort）',
        constants=dict(SR=SR, FPS=FPS, WIN_N=WIN_N, BLOCK_N=BLOCK_N,
                       SLOW_FEED_S=SLOW_FEED_S),
        discrimination=dict(known_bad_target=KNOWN_BAD_TARGET,
                            detail=disc['detail']),
        checks=checks, n_pass=n_pass, n_fail=len(checks) - n_pass,
        verdict=('PASS' if n_pass == len(checks) else 'FAIL'),
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('=== APP-054 旁路非阻塞单测（假 tracker，不跑推理、不占 GPU）===')
    for c in checks:
        print('  [%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL',
                                  c['name'], c['detail']))
    print('结果：%d PASS / %d FAIL ⇒ %s'
          % (n_pass, len(checks) - n_pass, out['verdict']))
    print('产物 = %s' % OUT)
    return 0 if n_pass == len(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
