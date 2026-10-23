r"""diag_c111_own.py — C-111 翻译层归属对照（**不需要翻译模型**，秒级）

★ 切段规则不动 ⇒ ASR 侧不变 ⇒ 直接复用 C-109 的定稿产物
  （72 段真实 12 分钟演讲），只对比**翻译层的段-译归属**。

★ 判据设计（关键：不能用「原文自然句边界」当判据）
  一句横跨两段时（段0 尾「So, welcome」+ 段1 首「to our Q3 meeting.」），
  两种机制都必须把两段拼成一句翻，**这句话只归属一段**：
    旧机制（C-099① 挂起）→ 归**下一段**（段1）：段0 引入的词被推迟显示
    新机制（C-111）      → 归**产生它的那段**（段0），补全后原地修正
  所以「某段缺字」不是缺陷本身；真正的缺陷是
  **本段引入的内容被推到了后面的段才显示**（延迟 + 顺序错乱）。

指标：
  1. 推迟词数：某段引入的词，最早在**更晚**的段才显示 → 旧机制的核心缺陷
  2. 提前词数：某段引入的词，最早在**更早**的段显示（新机制，跨段句归前段）
  3. 丢失词数：所有段的译文加起来仍覆盖不到的词（应当两机制都为 0）
  4. 逐段明细：段 N 的原文是否当段就有归属

用法：
  python diag_c111_own.py
"""
from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import translator as T

RUNS = r'C:/Users/Trekker-PTL/hy_bench/runs/c109_minseg6'


class OldCarry:
    """C-099① 旧挂起机制的段归属复刻（只算 key 归属，不翻译）。"""

    def __init__(self):
        self.carry = ''
        self.seg_keys = {}
        self.seg_carry = {}
        self._seen = set()

    def submit(self, sentence, seg=None):
        text = (sentence or '').strip()
        if not text:
            return []
        if self.carry:
            text = self.carry + ' ' + text
            self.carry = ''
            carried_in = True
        else:
            carried_in = False
        sents = T.split_sentences(text)
        has_carry = False
        if sents and not T.ends_sentence(sents[-1]):
            self.carry = sents[-1]
            sents = sents[:-1]
            has_carry = True
        keys = []
        for s in sents:
            k = T.norm_key(s)
            if not k or k in self._seen:
                continue
            self._seen.add(k)
            keys.append(k)
        if seg is not None:
            self.seg_keys[seg] = keys
            self.seg_carry[seg] = has_carry or carried_in
        return keys

    def flush(self, seg=None):
        if not self.carry:
            return []
        s, self.carry = self.carry, ''
        k = T.norm_key(s)
        if k and k not in self._seen:
            self._seen.add(k)
            if seg is not None:
                self.seg_keys.setdefault(seg, [])
                if k not in self.seg_keys[seg]:
                    self.seg_keys[seg].append(k)
        return [k] if k else []


def analyze(seg_keys, finals):
    """统计每个词的最早归属段 vs 引入段。

    ★ 注意：「跨段句」的特殊性 ——
      段0 尾「So, welcome」+ 段1 首「Welcome to our Q3 26 [REDACTED].」
      合起来是一句「So, welcome Welcome to our Q3 26 [REDACTED].」。
      无论旧机制（归段1）还是新机制（归段1）都只能归属**一段**。
      所以「段0 的词出现在段1」在两种机制下都成立，
      **不能**用来评价优劣 —— 那是跨段句的固有归属，不是缺陷。

    ★ 真正要看的指标是下面两个（在 main 里算）：
      - own_cover：本段原文的词，有多少能在**本段**的 key 列表里找到
      - delayed：本段引入的词，最早在**更晚**的段才出现
    """
    owner = {}
    for seg, keys in (seg_keys or {}).items():
        for k in keys or []:
            owner[k] = min(owner.get(k, seg), seg)
    delayed = []
    early = []
    lost = []
    for i, src in enumerate(finals):
        for w in src.split():
            ks = [k for k in owner if w in k.split()]
            if not ks:
                lost.append((i, w))
                continue
            first = min(owner[k] for k in ks)
            if first > i:
                delayed.append((i, first, w))
            elif first < i:
                early.append((i, first, w))
    return delayed, early, lost


def own_cover(seg_keys, finals):
    """本段原文的词，有多少能在**本段**的 key 列表里找到（覆盖度）。"""
    hit = miss = 0
    miss_detail = []
    for i, src in enumerate(finals):
        keys = seg_keys.get(i) or []
        kw = set()
        for k in keys:
            kw.update(k.split())
        for w in src.split():
            if w in kw:
                hit += 1
            else:
                miss += 1
                miss_detail.append((i, w))
    return hit, miss, miss_detail


def main():
    with open(os.path.join(RUNS, 'min6.0_cut0.8.json'), encoding='utf-8') as f:
        c109 = json.load(f)
    finals = c109['finals']
    n = len(finals)

    # ── A) 旧机制 ──
    old = OldCarry()
    for i, txt in enumerate(finals):
        old.submit(txt, seg=i)
    old.flush(seg=n - 1)

    # ── B) 新机制（真实 TranslationService 的归属逻辑，但不入队）──
    svc = T.TranslationService(target='zh', auto=False, on_log=lambda m: None)
    svc.state = 'ready'
    real_put = svc.q.put
    svc.q.put = lambda *a, **k: None
    try:
        for i, txt in enumerate(finals):
            svc.submit(txt, seg=i)
        svc.flush(seg=n - 1)
    finally:
        svc.q.put = real_put

    d_a, e_a, l_a = analyze(old.seg_keys, finals)
    d_b, e_b, l_b = analyze(svc.seg_keys, finals)
    h_a, ms_a, det_a = own_cover(old.seg_keys, finals)
    h_b, ms_b, det_b = own_cover(svc.seg_keys, finals)

    print('=' * 74)
    print('C-111 翻译层归属对照（真实 C-109 定稿 · %d 段 · 12 分钟演讲）' % n)
    print('=' * 74)

    print('\n【核心指标】本段原文的词在本段译文里能找到的覆盖率')
    print('  [A] 旧机制  命中 %4d / 缺失 %4d  (%.1f%%)'
          % (h_a, ms_a, 100.0 * h_a / max(1, h_a + ms_a)))
    print('  [B] 新机制  命中 %4d / 缺失 %4d  (%.1f%%)'
          % (h_b, ms_b, 100.0 * h_b / max(1, h_b + ms_b)))
    print('  → 缺失词 %d → %d   (%s)'
          % (ms_a, ms_b,
             '完全消除' if not ms_b else '降低 %.1f%%'
             % (100.0 * (ms_a - ms_b) / max(1, ms_a))))

    print('\n【次要指标】归属段 vs 引入段')
    print('  [A] 旧机制  推迟 %4d   提前 %4d   丢失 %4d'
          % (len(d_a), len(e_a), len(l_a)))
    print('  [B] 新机制  推迟 %4d   提前 %4d   丢失 %4d'
          % (len(d_b), len(e_b), len(l_b)))
    print('  ★ 说明：跨段的那一句只能归属一段，两种机制都会有「提前/推迟」，'
          '\n    这是跨段句的固有归属，不是缺陷 —— 核心指标是上面的覆盖率。')

    # 逐段：段 N 的尾半句是否归自己
    def tail_own(seg_keys):
        own = 0
        tot = 0
        for i, src in enumerate(finals):
            ss = T.split_sentences(src)
            if not ss or T.ends_sentence(ss[-1]):
                continue
            k = T.norm_key(ss[-1])
            if not k:
                continue
            tot += 1
            keys = seg_keys.get(i) or []
            if any(k in x or x in k for x in keys):
                own += 1
        return own, tot

    o_a, t_a = tail_own(old.seg_keys)
    o_b, t_b = tail_own(svc.seg_keys)
    print('\n【段尾半句归本段】旧 %d/%d，新 %d/%d'
          % (o_a, t_a, o_b, t_b))

    if det_a:
        print('\n旧机制缺失样例（段, 缺的词）：')
        for i, w in det_a[:10]:
            print(f'    段{i:3d}  「{w}」')
    if det_b:
        print('\n新机制仍缺失样例：')
        for i, w in det_b[:10]:
            print(f'    段{i:3d}  「{w}」')

    out_dir = r'C:/Users/Trekker-PTL/hy_bench/runs/c111_half'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'c111_ownership.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(n_seg=n,
                       old=dict(own_hit=h_a, own_miss=ms_a,
                                delayed=len(d_a), early=len(e_a),
                                lost=len(l_a), tail_own=o_a, tail_total=t_a),
                       new=dict(own_hit=h_b, own_miss=ms_b,
                                delayed=len(d_b), early=len(e_b),
                                lost=len(l_b), tail_own=o_b, tail_total=t_b),
                       old_missing=[[i, w] for i, w in det_a],
                       new_missing=[[i, w] for i, w in det_b]),
                  f, ensure_ascii=False, indent=1)
    print(f'\n已写 {out_dir}/c111_ownership.json')


if __name__ == '__main__':
    main()
