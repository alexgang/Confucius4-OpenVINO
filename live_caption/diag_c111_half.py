#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C-111：翻译层「段尾半句当段即翻 + 补全后修正」的状态机验证。

用**假翻译引擎**（不进模型）验证纯逻辑，可秒级跑完：
  - 段尾半句是否当段就翻、译文是否归本段
  - 半句被下一段补全后是否重翻并**原地覆盖**旧译文
  - 段 N 的译文是否还缺自己那半句（旧机制的核心缺陷）
  - outbox 的 kind 是否正确区分 final / half / fix（决定 TTS 是否重复朗读）

用法：python diag_c111_half.py
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translator as T


class FakeTr:
    """假翻译器：把英文翻成「ZH:原文」，只关心**调用次数与覆盖顺序**。"""

    def __init__(self):
        self.calls = []

    def translate(self, text, target, ctx=None, glossary=None):
        self.calls.append(text)
        return dict(text='ZH:' + text.strip(), lat_ms=1.0, ttft_ms=0.5,
                    n_in=1, n_out=1, skipped=False)

    def close(self):
        pass


def new_svc():
    """起一个用假引擎的 TranslationService（后台线程跑真实调度逻辑）。"""
    svc = T.TranslationService(target='zh', auto=False, on_log=lambda m: None)
    fake = FakeTr()
    # 直接接管工作线程：跑真实的 _run_jobs 调度，但用假引擎
    svc._start = lambda: None
    th = threading.Thread(target=T._run_jobs, args=(svc, fake), daemon=True)
    th.start()
    svc._fake = fake
    return svc, fake


def drain(svc, timeout=5.0):
    """等队列排空并取走 outbox。"""
    import time
    end = time.perf_counter() + timeout
    out = []
    while time.perf_counter() < end:
        out.extend(svc.pop_outbox())
        if not svc.pending:
            break
        time.sleep(0.02)
    out.extend(svc.pop_outbox())
    return out


def case(title, fn):
    print('=' * 72)
    print('CASE:', title)
    fn()
    print()


def c_basic():
    """基本流程：段0 有完整句 + 段尾半句；段1 补全半句。"""
    svc, fake = new_svc()
    segs = [
        (0, 'Good morning everyone. Let us start.'),
        (0, 'So welcome'),                     # 段0 尾半句
        (1, 'to our Q3 meeting. Then we cover AI.'),   # 段1 补全 + 新句
    ]
    # 段0 一次定稿（含半句）
    svc.submit('Good morning everyone. Let us start. So welcome', seg=0)
    out0 = drain(svc)
    print('  段0 定稿后 outbox:', [(k, t) for k, _, t in out0])
    print('  段0 seg_keys:', svc.seg_keys.get(0))
    print('  段0 mt_of_seg(0):', svc.mt_of_seg(0))
    assert any(k == 'half' for k, _, _ in out0), '段尾半句应当当段就翻（half）'
    assert svc.mt_of_seg(0), '段0 译文不应为空'
    assert 'So welcome' in (svc.mt_of_seg(0) or ''), \
        '★ 段0 译文应含自己的半句（旧机制这里会缺）'
    print('  ✓ 半句当段即翻且归本段')

    svc.submit('to our Q3 meeting. Then we cover AI.', seg=1)
    out1 = drain(svc)
    print('  段1 定稿后 outbox:', [(k, t) for k, _, t in out1])
    print('  段0 mt_of_seg(0):', svc.mt_of_seg(0))
    print('  段1 mt_of_seg(1):', svc.mt_of_seg(1))
    fixes = [(k, t) for k, _, t in out1 if k == 'fix']
    assert fixes, '半句补全后应发出 fix 事件'
    assert 'So welcome to our Q3 meeting.' in fixes[0][1], \
        f'fix 文本应是被补全的完整句，实际: {fixes[0][1]}'
    print('  ✓ 补全后重翻并发出 fix 事件')

    # 段0 的译文应已被**原地覆盖**成修正版
    assert 'So welcome to our Q3 meeting.' in (svc.mt_of_seg(0) or ''), \
        f'★ 段0 译文应原地更新为修正版，实际: {svc.mt_of_seg(0)}'
    print('  ✓ 原地覆盖旧译文（段0 不再缺字）')
    print('  翻译调用序列:', fake.calls)


def c_no_carry_attr():
    """旧的 _carry 属性必须消失（避免残留代码误用）。"""
    svc, _ = new_svc()
    assert not hasattr(svc, '_carry'), '_carry 应已被 _half 取代'
    print('  ✓ 无残留 _carry')


def c_speech_only():
    """整段都是半句（段0 只有半句）。"""
    svc, fake = new_svc()
    svc.submit('And that is why we', seg=0)
    out = drain(svc)
    print('  outbox:', [(k, t) for k, _, t in out])
    print('  seg_keys[0]:', svc.seg_keys.get(0))
    print('  mt_of_seg(0):', svc.mt_of_seg(0))
    assert svc.mt_of_seg(0), '整段半句也应立刻有译文'
    assert 'And that is why we' in svc.mt_of_seg(0)
    print('  ✓ 整段半句也当段即翻')
    print('  翻译调用序列:', fake.calls)


def c_growing_half():
    """半句连续两段都没闭合 → **每段各翻自己那段**（链上各归各段）。

    ★ C-111 设计：半句链上的每一段都保留自己那份译文（各归各段），
      不把整条链的译文都推到闭合的那一段 —— 否则中间的段界面上
      一个字都没有（实测段7/段8 的 seg_keys 全空）。
    """
    svc, fake = new_svc()
    svc.submit('Let me explain', seg=0)
    drain(svc)
    svc.submit('the reason in detail', seg=1)
    out = drain(svc)
    print('  outbox:', [(k, t) for k, _, t in out])
    print('  seg_keys[0]:', svc.seg_keys.get(0))
    print('  seg_keys[1]:', svc.seg_keys.get(1))
    print('  翻译调用序列:', fake.calls)
    assert len(fake.calls) == 2, f'应翻两次（每段一次），实际 {len(fake.calls)}'
    # 每段翻的是**自己那部分**原文
    assert fake.calls[0] == 'Let me explain'
    assert fake.calls[1] == 'the reason in detail'
    # 两段各自都有译文
    assert svc.mt_of_seg(0), '段0 应有自己的译文'
    assert svc.mt_of_seg(1), '段1 应有自己的译文'
    print('  ✓ 半句链上每段各留一份译文')


def c_flush():
    """收尾 flush：最后半句应作为 final 交出。"""
    svc, fake = new_svc()
    svc.submit('The final unfinished', seg=0)
    drain(svc)
    keys = svc.flush(seg=0)
    out = drain(svc)
    print('  flush keys:', keys)
    print('  outbox:', [(k, t) for k, _, t in out])
    assert any(k == 'final' for k, _, _ in out), 'flush 后应发出 final'
    print('  ✓ flush 把最后半句交为 final')


def c_cross_seg_fix():
    """跨段整句：闭合时**原地覆盖**上一段的半句槽位（用户要的「修正」）。"""
    svc, fake = new_svc()
    svc.submit('Alpha one. Partial tail', seg=0)
    drain(svc)
    print('  段0 译文:', svc.mt_of_seg(0))
    svc.submit('continues here. Beta one.', seg=1)
    out = drain(svc)
    print('  outbox:', [(k, t) for k, _, t in out])
    print('  段0 译文:', svc.mt_of_seg(0))
    print('  段1 译文:', svc.mt_of_seg(1))
    fixes = [(k, t) for k, _, t in out if k == 'fix']
    assert fixes, '应有 fix 事件'
    # 段0 的半句槽位被**整句译文原地覆盖**
    assert 'Alpha one.' in (svc.mt_of_seg(0) or '')
    assert 'Partial tail continues here.' in (svc.mt_of_seg(0) or ''), \
        f'段0 应含修正后的整句，实际: {svc.mt_of_seg(0)}'
    # 段1 自己也有首半句的译文
    assert svc.mt_of_seg(1), '段1 应有自己的译文'
    assert 'Beta one.' in (svc.mt_of_seg(1) or '')
    print('  ✓ 跨段整句：上一段原地修正 + 本段保留自己那份')


def c_tts_no_dup():
    """★ TTS 语义：'half' 不朗读，'final'/'fix' 朗读 ⇒ 同一句不会被念两遍。"""
    svc, fake = new_svc()
    svc.submit('Alpha one. Partial tail', seg=0)
    out0 = drain(svc)
    svc.submit('continues here. Beta one.', seg=1)
    out1 = drain(svc)
    spoken = [(k, t) for k, _, t in out0 + out1 if k in ('final', 'fix')]
    halves = [(k, t) for k, _, t in out0 + out1 if k == 'half']
    print('  朗读的（final/fix）:', spoken)
    print('  不朗读的（half）:', halves)
    assert halves, '应有 half 事件'
    # 'fix' 的译文 = 修正后的整句；初翻的 half 译文与它不同 → 不会念两遍
    half_txt = halves[0][1]
    fix_txt = [t for k, t in spoken if k == 'fix']
    assert fix_txt, '应有 fix'
    assert half_txt not in fix_txt, '修正译文不应等于半句初译（否则会重复朗读）'
    print('  ✓ half 只显示不朗读，fix 才朗读 → 无重复朗读')


def c_overlap_guard():
    """★ 关键回归：段 N 的译文不得包含下一段的字（防止越界串段）。"""
    svc, fake = new_svc()
    svc.submit('Alpha one. Alpha two. Partial tail', seg=0)
    drain(svc)
    svc.submit('continues here. Beta one.', seg=1)
    drain(svc)
    m0 = svc.mt_of_seg(0) or ''
    m1 = svc.mt_of_seg(1) or ''
    print('  段0:', m0)
    print('  段1:', m1)
    assert 'Beta one' not in m0, '★ 段0 译文不应含段1 的内容'
    assert 'Alpha' not in m1, '★ 段1 译文不应含段0 的内容'
    print('  ✓ 段间无越界串词')


def c_len_cap():
    """半句补全后超长 → 整句修正 + 本段首半句单独翻。

    ★ 注：整句（fix）与本段首半句（half）内容**有重叠** —— 这是
      用户要求的「定稿翻一次 + 完整句再翻一次」设计的必然结果：
      定稿时翻半句（立刻可见），闭合时再翻整句（修正）。
      重叠部分 = 上一段那半句，它在闭合时被整句译文覆盖。
    """
    svc, fake = new_svc()
    long_tail = ' '.join(f'w{i}' for i in range(15))
    svc.submit('Prefix sentence is here. ' + long_tail, seg=0)
    drain(svc)
    svc.submit('more words to make it long and then some more here.', seg=1)
    out = drain(svc)
    print('  outbox kinds:', [k for k, _, _ in out])
    print('  翻译调用序列:', fake.calls)
    print('  段0 译文:', svc.mt_of_seg(0))
    print('  段1 译文:', svc.mt_of_seg(1))
    assert any(k == 'fix' for k, _, _ in out), '应有整句修正'
    assert svc.mt_of_seg(0) and svc.mt_of_seg(1), '两段都应有译文'
    print('  ✓ 超长句：整句修正 + 本段首半句单独归本段')


def c_dedup():
    """同一段文本重复提交不应重复翻译。"""
    svc, fake = new_svc()
    svc.submit('Repeated sentence here.', seg=0)
    drain(svc)
    n1 = len(fake.calls)
    svc.submit('Repeated sentence here.', seg=1)
    drain(svc)
    print('  翻译调用数:', len(fake.calls), '（第一次后 =', n1, '）')
    assert len(fake.calls) == n1, '重复句子不应重复翻译'
    print('  ✓ 去重正常')


def main():
    for fn in (c_basic, c_no_carry_attr, c_speech_only, c_growing_half,
               c_flush, c_cross_seg_fix, c_tts_no_dup,
               c_overlap_guard, c_len_cap, c_dedup):
        case(fn.__doc__.split('\n')[0], fn)
    print('ALL PASS')


if __name__ == '__main__':
    main()
