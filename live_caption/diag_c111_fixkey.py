#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C-111 回归：半句链闭合后 `self._half` 未清空 => 同一槽位被反复 fix。

用**假翻译引擎**（不进模型，秒级）+ 真实 C-109 定稿 72 段，检查：
  1) outbox 里 'fix' 事件的 key 是否重复（重复 = bug 仍在）
  2) 同一 key 的译文是否被反复改写成多个不同值
  3) (kind, key) 组合是否唯一

不加载模型、不计时、不需要机器锁。
用法：python diag_c111_fixkey.py
"""
import json
import os
import sys
import threading
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translator as T  # noqa: E402

RUNS = r'C:\Users\Trekker-PTL\hy_bench\runs\c109_minseg6\min6.0_cut0.8.json'
OUTP = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_fixkey.json'


class FakeTr:
    def __init__(self):
        self.calls = []

    def translate(self, text, target, ctx=None, glossary=None):
        self.calls.append(text)
        return dict(text='ZH:' + text.strip(), lat_ms=1.0, ttft_ms=0.5,
                    n_in=1, n_out=1, skipped=False)

    def close(self):
        pass


def new_svc():
    svc = T.TranslationService(target='zh', auto=False, on_log=lambda m: None)
    fake = FakeTr()
    svc._start = lambda: None
    threading.Thread(target=T._run_jobs, args=(svc, fake), daemon=True).start()
    return svc, fake


def drain(svc, timeout=30.0):
    end = time.perf_counter() + timeout
    out = []
    while time.perf_counter() < end:
        out.extend(svc.pop_outbox())
        if not svc.pending:
            break
        time.sleep(0.02)
    out.extend(svc.pop_outbox())
    return out


def main():
    with open(RUNS, 'r', encoding='utf-8') as f:
        data = json.load(f)
    finals = data['finals'] if isinstance(data, dict) and 'finals' in data else data
    print('=' * 74)
    print('C-111 fix-key 回归（假引擎 · 真实 %d 段）' % len(finals))
    print('=' * 74)

    svc, fake = new_svc()
    for i, t in enumerate(finals):
        svc.submit(t, seg=i)
    svc.flush()
    out = drain(svc)

    kinds = Counter(k for k, _, _ in out)
    print('\n【事件构成】%s   翻译调用 %d 次' % (dict(kinds), len(fake.calls)))

    fix_keys = [key for k, key, _ in out if k == 'fix']
    dup = {k: c for k, c in Counter(fix_keys).items() if c > 1}
    print('\n【fix key 重复检查】fix 事件 %d 次，唯一 key %d 个'
          % (len(fix_keys), len(set(fix_keys))))
    if dup:
        print('  ✗ 仍有重复 key（bug 未修好）：')
        for k, c in Counter(fix_keys).most_common(10):
            print('      %-58s %d 次' % (k[:56], c))
    else:
        print('  ✓ 无任何 key 被 fix 两次')

    # ★ 判据说明（v2，修正 v1 的错误判据）：
    #   `half` -> `fix` 的**两段历史**是 C-111 的设计意图（半句先占位、补全后整句覆盖），
    #   不是「反复改写」。真正的缺陷是：**终态（final/fix）之后又出现同 key 的事件**，
    #   或者同 key 出现**两个终态**（= 槽位被反复修正）。
    #   合法形态： [half] / [half, fix] / [final] / [fix]
    bykey = {}
    for k, key, txt in out:
        bykey.setdefault(key, []).append((k, txt))
    rewritten = []
    for key, lst in bykey.items():
        seq = [k for k, _ in lst]
        terminal = [k for k in seq if k in ('final', 'fix')]
        bad = False
        if len(terminal) > 1:                      # 两个终态 = 反复修正
            bad = True
        elif terminal and seq.index(terminal[0]) != len(seq) - 1:
            bad = True                             # 终态后还有事件
        elif seq and seq[0] != 'half' and len(seq) > 1:
            bad = True                             # 非 half 起头的多事件
        if bad:
            rewritten.append((key, lst))
    print('\n【事件序列合法性检查】%s'
          % ('✓ 每个 key 的事件序列均为 [half]/[half,fix]/[final]/[fix]'
             if not rewritten
             else '✗ %d 个 key 的事件序列异常' % len(rewritten)))
    for key, lst in rewritten[:8]:
        print('    key=%s' % key[:70])
        for k, t in lst:
            print('        %-5s %s' % (k, t[:80]))

    # 半句 → 整句的**内容递增**检查：fix 的译文必须包含 half 的原文（真的补全了）
    not_grown = []
    for key, lst in bykey.items():
        if len(lst) == 2 and lst[0][0] == 'half' and lst[1][0] == 'fix':
            def strip(t):
                return t[3:] if t.startswith('ZH:') else t
            src = strip(lst[0][1]).replace(' ', '')
            dst = strip(lst[1][1]).replace(' ', '')
            if not dst.startswith(src) or len(dst) <= len(src):
                not_grown.append((key, lst))
    print('\n【fix 是否为整句（含原半句）】%s'
          % ('✓ 全部为整句覆盖' if not not_grown
             else '✗ %d 个 fix 未覆盖原半句' % len(not_grown)))
    for key, lst in not_grown[:5]:
        print('    key=%s' % key[:70])
        for k, t in lst:
            print('        %-5s %s' % (k, t[:80]))

    combo = Counter((k, key) for k, key, _ in out)
    bad_combo = {c: n for c, n in combo.items() if n > 1}
    print('\n【(kind,key) 唯一性】%s'
          % ('✓ 全部唯一' if not bad_combo else '✗ %d 组重复' % len(bad_combo)))
    for c, n in list(bad_combo.items())[:10]:
        print('      %s x%d' % (str(c)[:78], n))

    ok = (not dup) and (not rewritten) and (not bad_combo) and (not not_grown)
    result = {
        'n_segments': len(finals),
        'translate_calls': len(fake.calls),
        'kinds': dict(kinds),
        'fix_key_total': len(fix_keys),
        'fix_key_unique': len(set(fix_keys)),
        'fix_key_dup': dup,
        'bad_sequence_keys': [k for k, _ in rewritten],
        'fix_not_whole_sentence': [k for k, _ in not_grown],
        'combo_dup': {str(k): v for k, v in bad_combo.items()},
        'pass': ok,
    }
    os.makedirs(os.path.dirname(OUTP), exist_ok=True)
    with open(OUTP, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('\n%s' % ('ALL PASS' if ok else 'FAIL'))
    print('已写 %s' % OUTP)


if __name__ == '__main__':
    main()
