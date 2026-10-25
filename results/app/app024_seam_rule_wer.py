"""验证「段接缝 n=1 去重」的**最终判据**（含误删代价）—— 用独立参照算 WER。

🔴 **要比较的档**（同一素材、同一参照、同一判据）：
  ① 旧 stitch（只试 n=3,2）—— **现状**
  ② 在制品（n=3→1 + 停用词安全阀）—— 方向错了（漏掉一半真缺陷）
  ③ 候选 A（n=3→1，**无任何安全阀**）—— 最激进
  ④ 候选 B（n=3→1 + **大小写/标点判据**）—— 本轮推荐
  ⑤ 候选 C（n=3→1 + 只用「后段首词大写」判据）

判据：语料级**配对** bootstrap（per-block 错误向量按参照 token 归位，K=40，5000 次）
      ⇒ **只看「Δ 的 CI 上界 < 0 才算改善/不劣化」这一条**，不报 p 值。
      ⇒ 绝对值不同口径（参照不同）⇒ **只对话 Δ**。
"""
from __future__ import annotations

import difflib
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
AB_DIR = os.path.join(REPO, 'reports', 'asr004_ab')
REF_TXT = os.path.join(REPO, 'reports', 'c048_61min_adaptive',
                       'transcript_adaptive.txt')
N_BOOT = 5000
K_BLOCK = 40


def norm_word(w):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (w or '').lower())


def norm_tokens(text):
    out = []
    for ln in (text or '').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r'^\[\s*[0-9.]+\s*-\s*[0-9.]+\s*\]\s*', '', ln)
        ln = re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', ' ', ln).lower()
        out.extend(ln.split())
    return out


def tail_punct(text):
    t = (text or '').rstrip()
    return bool(t) and t[-1] in '.?!。！？'


def is_cap(w):
    return bool(w) and w[0].isupper()


def wer_counts(ref, hyp):
    r, h = list(ref), list(hyp)
    if not r:
        return (len(h), 0)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    err = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        err += max(i2 - i1, j2 - j1)
    return err, len(r)


def per_block_errors(ref, hyp, K):
    blk = [0] * K
    sm = difflib.SequenceMatcher(a=list(ref), b=list(hyp), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        err = max(i2 - i1, j2 - j1)
        if i2 == i1:
            blk[i1 % K] += err
            continue
        n = i2 - i1
        base, extra = divmod(err, n)
        for k, pos in enumerate(range(i1, i2)):
            blk[pos % K] += base + (1 if k < extra else 0)
    return blk


def make_stitch(mode, stopwords=None, char_min=2, char_max=24):
    """mode: 'old' | 'guard' | 'none' | 'case_punct' | 'case_only'"""
    sw = stopwords or frozenset()

    def _char_overlap(prev_text, text):
        a = (prev_text or '').rstrip()
        b = (text or '').lstrip()
        if not a or not b:
            return 0
        al, bl = a.lower(), b.lower()
        for k in range(min(len(a), len(b), char_max), char_min - 1, -1):
            if al[-k:] == bl[:k]:
                return k
        return 0

    def stitch(prev_words, text, prev_text=None):
        if not text:
            return text
        if prev_text:
            k = _char_overlap(prev_text, text)
            if k and len(prev_text) > k:
                prev_text = prev_text[:-k]
                if prev_words:
                    pw = prev_text.split()
                    prev_words = pw[-3:] if pw else []
        if not prev_words:
            return text
        words = text.split()
        nw = [norm_word(w) for w in words]
        prev = [norm_word(w) for w in prev_words]
        for n in range(min(3, len(words)), 0, -1):
            if len(nw) < n or len(prev) < n:
                continue
            if prev[-n:] != nw[:n]:
                continue
            if n == 1:
                if mode == 'guard' and norm_word(words[0]) in sw:
                    continue
                if mode == 'case_punct':
                    # 判据：后段首词大写开头（后段重新起句）**或** 前段末尾无句末标点
                    if not (is_cap(words[0]) and not is_cap(prev_words[-1])) \
                            and tail_punct(prev_text or ''):
                        continue
                elif mode == 'case_only':
                    if not (is_cap(words[0]) and not is_cap(prev_words[-1])):
                        continue
            rest = words[n:]
            return ' '.join(rest) if rest else text
        return text

    return stitch


def stitch_old(prev_words, text):
    if not prev_words or not text:
        return text
    words = text.split()
    nw = [norm_word(w) for w in words]
    prev = [norm_word(w) for w in prev_words]
    for n in (3, 2):
        if len(nw) >= n and len(prev) >= n and prev[-n:] == nw[:n]:
            rest = words[n:]
            return ' '.join(rest) if rest else text
    return text


def build_hyp(segs, fn, use_pt):
    outs = []
    pw, pt = [], ''
    for s in segs:
        txt = s.get('text') or ''
        if not txt.strip():
            continue
        out = fn(pw, txt, pt) if use_pt else fn(pw, txt)
        outs.append(out)
        pw = out.split()[-3:] if out.split() else []
        pt = out
    return '\n'.join(outs)


def load_stopwords():
    import ast
    src = open(os.path.join(REPO, 'live_caption', 'live_caption_app.py'),
               encoding='utf-8').read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_STITCH_STOPWORDS':
                    ns = {}
                    exec(compile(ast.Module(body=[node], type_ignores=[]),
                                 '<sw>', 'exec'), ns)
                    return ns['_STITCH_STOPWORDS']
    return frozenset()


def main():
    ref = norm_tokens(open(REF_TXT, encoding='utf-8').read())
    sw = load_stopwords()

    variants = [
        ('① 旧 stitch（只试 n=3,2）—— 现状', stitch_old, False),
        ('② 在制品（+停用词安全阀）', make_stitch('guard', sw), True),
        ('③ 无安全阀（最激进）', make_stitch('none'), True),
        ('④ 大小写/标点判据（推荐）', make_stitch('case_punct'), True),
        ('⑤ 只用「后段首词大写」', make_stitch('case_only'), True),
    ]

    for gname in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % gname)
        if not os.path.exists(p):
            continue
        segs = json.load(open(p, encoding='utf-8'))['segments']
        print('═══ %s 组 ═══' % gname)
        hyp_by = {}
        for label, fn, use_pt in variants:
            h = norm_tokens(build_hyp(segs, fn, use_pt))
            hyp_by[label] = h
            e, rl = wer_counts(ref, h)
            print('  %-28s 词数 %5d  WER = %.3f%%  (err=%d)'
                  % (label, len(h), 100.0 * e / rl, e))
        print()

        base = variants[0][0]
        blk_ref = [0] * K_BLOCK
        for i in range(len(ref)):
            blk_ref[i % K_BLOCK] += 1
        e0, rl = wer_counts(ref, hyp_by[base])
        for label, _, _ in variants[1:]:
            b0 = per_block_errors(ref, hyp_by[base], K_BLOCK)
            b1 = per_block_errors(ref, hyp_by[label], K_BLOCK)
            ds = []
            rnd = random.Random(20261025)
            for _ in range(N_BOOT):
                idx = [rnd.randrange(K_BLOCK) for _ in range(K_BLOCK)]
                num = sum(b1[i] - b0[i] for i in idx)
                den = sum(blk_ref[i] for i in idx)
                ds.append(100.0 * num / den if den else 0.0)
            ds.sort()
            lo = ds[int(0.025 * N_BOOT)]
            hi = ds[min(N_BOOT - 1, int(0.975 * N_BOOT))]
            e1, _ = wer_counts(ref, hyp_by[label])
            delta = 100.0 * (e1 - e0) / rl
            print('  Δ(%s − ①) = %+.3f pp   CI [%+.3f, %+.3f]  ⇒ %s'
                  % (label[:2], delta, lo, hi,
                     '改善' if hi < 0 else ('劣化' if lo > 0 else '无显著差异')))
        print()

    op = os.path.join(HERE, 'app024_seam_rule_wer.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump({'note': '见 stdout；判据=语料级配对 bootstrap K=40 5000次'},
                  f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
