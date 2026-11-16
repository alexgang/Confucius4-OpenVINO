#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app586_queue_selftest.py —— APP-113 §1 `TtsReadyQueue` 的**行为级**自测。

纪律（对齐记忆里的判据工程）：
  - **不 import 被测模块**（开发树缺 openvino/torch ⇒ import 会假 FAIL）
    ⇒ 用 `ast` 从源码里**抽出类定义**，`exec` 后真跑被测函数；
  - **反证组**：故意改坏「等待时长 / 溢出阈值」后必须被抓到；
  - 断言写在**结果文件**里（可复核）。
"""
import ast
import hashlib
import json
import os
import sys
import time

SRC = (r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
       r'\live_caption_app.py')
OUT = (r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'
       r'\app586_tts_ready_queue_selftest.json')


def load_class(src_path, cls_name, extra_names=()):
    """用 AST 抽出类定义（+ 依赖的模块级常量）⇒ exec 后真跑。"""
    src = open(src_path, encoding='utf-8').read()
    tree = ast.parse(src)
    wanted = {cls_name}
    wanted.update(extra_names)
    chunks = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in wanted:
            chunks.append(ast.get_source_segment(src, node))
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Name) and tgt.id in wanted
                        and isinstance(node.value, ast.Constant)):
                    chunks.append(ast.get_source_segment(src, node))
    assert chunks, 'AST 里没找到 %s' % (sorted(wanted),)
    ns = {'time': time, 'threading': __import__('threading')}
    exec('\n\n'.join(chunks), ns)
    return ns


def run_case(ns, wait_before_ready_s=0.0, overflow_s=120.0,
             n_push=5, lag_after=1.0):
    """跑一轮：推 n_push 句 → （可选）等 wait_before_ready_s → 就绪 → 补发。

    🔴 **模拟真实播放**：补发后，把 `n_played` 推进到「已补发的句数都播了」
      ⇒ 这样「两道闸」判据（play_lag_s<2 **且** 就绪后已播 ≥ 已补发）才可能成立。
    """
    Q = ns['TtsReadyQueue']
    logs = []
    q = Q(overflow_s=overflow_s, on_log=lambda m: logs.append(m))
    order = []
    for i in range(n_push):
        q.push(lambda i=i: order.append(i), meta={'seg': i})
    q.poll(False, lag_s=None, n_played=0)   # 未就绪
    if wait_before_ready_s:
        time.sleep(wait_before_ready_s)
    q.poll(True, lag_s=99.0, n_played=0)    # 就绪（积压还很大）
    items = q.take_ready()
    for _t, fn, _m in items:
        fn()
    # 补发的都播完了，滞后回落 ⇒ 允许记「积压已清空」
    q.poll(True, lag_s=lag_after, play_lag_s=lag_after,
           n_played=len(items))
    return q.stats(), order, logs


def main():
    ns = load_class(SRC, 'TtsReadyQueue',
                    extra_names=('_TTS_QUEUE_OVERFLOW_S',
                                 '_TTS_BACKLOG_CLEAR_S'))
    ev = {'source': SRC, 'cases': [], 'verdict': 'PASS'}

    # ── 用例 1：正常冷启动（等待 1 s）⇒ 一句不丢、顺序不变 ──
    st, order, logs = run_case(ns, wait_before_ready_s=1.0, n_push=5)
    c1 = {
        'name': '正常等待后补发：一句不丢 + FIFO 顺序不变',
        'n_queued_before_ready': st['n_queued_before_ready'],
        'n_drop_not_ready_overflow': st['n_drop_not_ready_overflow'],
        'n_flushed': st['n_flushed'],
        'order': order,
        'ready_at_set': st['ready_at'] is not None,
        'backlog_cleared_rel_s': st['backlog_cleared_rel_s'],
        'pass': (st['n_queued_before_ready'] == 5
                 and st['n_drop_not_ready_overflow'] == 0
                 and st['n_flushed'] == 5
                 and order == [0, 1, 2, 3, 4]
                 and st['ready_at'] is not None
                 and st['backlog_cleared_rel_s'] is not None),
    }
    ev['cases'].append(c1)

    # ── 用例 2：溢出保护（阈值 0.2 s ⇒ 等 1 s 后队首超期）⇒ 只丢队首 ──
    st2, order2, logs2 = run_case(ns, wait_before_ready_s=1.0,
                                  overflow_s=0.2, n_push=5)
    c2 = {
        'name': '溢出保护：超过阈值仍未就绪 ⇒ 按最旧优先丢弃 + 计数',
        'n_queued_before_ready': st2['n_queued_before_ready'],
        'n_drop_not_ready_overflow': st2['n_drop_not_ready_overflow'],
        'n_flushed': st2['n_flushed'],
        'order': order2,
        'log_has_overflow': any('丢弃' in m for m in logs2),
        'pass': (st2['n_drop_not_ready_overflow'] >= 1
                 and st2['n_flushed'] + st2['n_drop_not_ready_overflow']
                 == st2['n_queued_before_ready']
                 and 0 not in order2          # 队首被丢
                 and any('丢弃' in m for m in logs2)),
    }
    ev['cases'].append(c2)

    # ── 反证组：**把阈值改成极大** ⇒ 溢出必须**不再**触发 ──
    st3, order3, _logs3 = run_case(ns, wait_before_ready_s=0.3,
                                   overflow_s=100000.0, n_push=3)
    c3 = {
        'name': '反证组：阈值放大 ⇒ 溢出丢弃必须 = 0（证明用例 2 不是恒真）',
        'n_drop_not_ready_overflow': st3['n_drop_not_ready_overflow'],
        'pass': st3['n_drop_not_ready_overflow'] == 0
        and st3['n_flushed'] == 3,
    }
    ev['cases'].append(c3)

    # ── 反证组：**积压判据放宽** ⇒ 积压清空时刻必须**不出现** ──
    Q = ns['TtsReadyQueue']
    q = Q(overflow_s=120.0)
    q.push(lambda: None)
    q.poll(True, lag_s=99.0)
    q.take_ready()
    q.poll(True, lag_s=50.0)      # 滞后 50 s ⇒ 远大于 2 s 判据
    c4 = {
        'name': '反证组：滞后 50 s ⇒ 不得记「积压清空」',
        'backlog_cleared_at': q.stats()['backlog_cleared_at'],
        'pass': q.stats()['backlog_cleared_at'] is None,
    }
    ev['cases'].append(c4)

    # ── 用例 5：`play_lag_s` 口径（APP-113 §4 实测后修正）────────────
    #   **积压清空**必须按 **worker 回报的 `play_lag_s`**（实际开播 − 目标开播）
    #   ⇒ service 的 `lag_s`（未播音频时长）**不得**单独触发「已清空」。
    Q = ns['TtsReadyQueue']
    q5 = Q(overflow_s=120.0)
    q5.push(lambda: None)
    q5.poll(True, lag_s=99.0, n_played=0)
    q5.take_ready()
    # 🔴 反证：`lag_s=0.0`（刚开始合成，未播音频时长为 0）但
    #   `play_lag_s=48.0`（真实滞后 48 s）⇒ **不得**记「积压清空」。
    q5.poll(True, lag_s=0.0, play_lag_s=48.0, n_played=1)
    c5 = {
        'name': '口径反证：lag_s=0 但 play_lag_s=48 ⇒ 不得记「积压清空」'
                '（证明判据用的是 play_lag_s，不是未播音频时长）',
        'backlog_cleared_at': q5.stats()['backlog_cleared_at'],
        'backlog_cleared_lag_kind': q5.stats()['backlog_cleared_lag_kind'],
        'pass': q5.stats()['backlog_cleared_at'] is None,
    }
    ev['cases'].append(c5)

    # ── 用例 6：**两道闸**——`play_lag_s<2` 且「就绪后已播 ≥ max(1,已补发)」
    q6 = Q(overflow_s=120.0)
    q6.push(lambda: None)
    q6.push(lambda: None)
    q6.poll(True, lag_s=99.0, n_played=0)     # 就绪：n_played 基准 = 0
    q6.take_ready()                          # 补发 2 句
    q6.poll(True, lag_s=0.0, play_lag_s=0.1, n_played=0)   # 还没播出来 ⇒ 不许清空
    c6a = {
        'name': '两道闸反证：play_lag_s=0.1 但**一句都还没播** ⇒ 不得记清空',
        'backlog_cleared_at': q6.stats()['backlog_cleared_at'],
        'pass': q6.stats()['backlog_cleared_at'] is None,
    }
    ev['cases'].append(c6a)
    q6.poll(True, lag_s=0.0, play_lag_s=0.1, n_played=2)   # 2 句都播了 ⇒ 允许清空
    st6 = q6.stats()
    c6b = {
        'name': '两道闸正例：play_lag_s=0.1 且已播 2 句(=已补发) ⇒ 记「积压清空」',
        'backlog_cleared_at_is_set': st6['backlog_cleared_at'] is not None,
        'backlog_cleared_lag_kind': st6['backlog_cleared_lag_kind'],
        'backlog_cleared_played_delta': st6['backlog_cleared_played_delta'],
        'pass': (st6['backlog_cleared_at'] is not None
                 and st6['backlog_cleared_lag_kind'] == 'play_lag_s'
                 and st6['backlog_cleared_played_delta'] == 2),
    }
    ev['cases'].append(c6b)

    # ── 反证组：**没有 `play_lag_s`** ⇒ 一律**不记**（不回落 `lag_s`）
    q7 = Q(overflow_s=120.0)
    q7.push(lambda: None)
    q7.poll(True, lag_s=99.0, n_played=0)
    q7.take_ready()
    q7.poll(True, lag_s=0.5, n_played=5)     # 无 play_lag_s ⇒ 不许清空
    c7 = {
        'name': '口径反证：无 play_lag_s ⇒ **不回落** lag_s ⇒ 不得记「积压清空」',
        'backlog_cleared_at': q7.stats()['backlog_cleared_at'],
        'pass': q7.stats()['backlog_cleared_at'] is None,
    }
    ev['cases'].append(c7)

    ev['n_fail'] = sum(1 for c in ev['cases'] if not c['pass'])
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    for c in ev['cases']:
        print('[%s] %s' % ('PASS' if c['pass'] else 'FAIL', c['name']))
    print('VERDICT=%s -> %s' % (ev['verdict'], OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
