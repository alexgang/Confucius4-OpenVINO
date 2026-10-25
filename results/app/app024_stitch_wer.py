"""APP-012② / APP-014① —— 用**独立参照**量化「段接缝重复词消除」的 WER 收益。

🔴🔴 **判据纪律**（本项目铁律）：
  · **参照必须独立** ⇒ 用 `reports/c048_61min_adaptive/transcript_adaptive.txt`
    （ASR 模块用同一份 method_b 代码**精确复现 7.798%** 的那一份，n_ref=11067 词）
    ⇒ **不拿自己的产物当参照**（否则循环论证）。
  · **配对 bootstrap**（语料级配对）⇒ CI；**只报「Δ 的 CI 上界 < 0 才算劣化」**
    这**一条** verdict；**不报 p 值**。
  · **不 import 被测模块** ⇒ `ast` 抽纯函数 + `exec` 到独立命名空间。
  · **不跑推理 / 不占 GPU**（纯离线文本作业 ⇒ 不需要机器锁）。

🔴 **本脚本回答的问题**：
  APP-012② 说 App 实时路径 WER 比基准差 **+2.6pp**，根因是 rule1 切点
  **穿过一个词** ⇒ 前后两段都转写出来。
  ⇒ 「在接缝处去重」能挽回多少？（这是 APP-014① 要求先做的事）

  对比三档：
    ① **旧 stitch**（只试 n=3,2）—— 现状
    ② **工作区在制品**（n=3→1 + 停用词安全阀 + 字符级）
    ③ **候选改进档**（n=3→1 + 更准的判据，无停用词表）
"""
from __future__ import annotations

import ast
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


# ── WER 计算（词级 Levenshtein）───────────────────────────────────────
def wer_counts(ref, hyp):
    """返回 (errors, ref_len)。标准词级 Levenshtein。

    🔴 入参是**已归一化的 token 列表**（不是字符串）。
    🔴 **实现选择**：纯 Python 的 O(n·m) DP 在 11.7k × 11.9k 上要跑
       1.4 亿次内层循环 ⇒ 单次要几十秒（实测被 SIGTERM 打断）。
       ⇒ 改用 `difflib.SequenceMatcher` 的编辑脚本：
         · `get_opcodes()` 给出 replace/delete/insert 的**区间**；
         · 编辑距离 = Σ(max(i2-i1, j2-j1))（replace 按长度差算，
           不足的部分算替换）—— 这与 Levenshtein 等价；
       ⇒ C 实现，1.4 亿次降到毫秒级。
    """
    r = list(ref) if not isinstance(ref, str) else ref.split()
    h = list(hyp) if not isinstance(hyp, str) else hyp.split()
    if not r:
        return (len(h), 0)
    sm = difflib.SequenceMatcher(a=r, b=h, autojunk=False)
    err = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        err += max(i2 - i1, j2 - j1)
    return err, len(r)


def norm_tokens(text):
    """归一化：去时间戳前缀、去标点、小写。

    🔴 参照与候选文本格式不同（参照是「[起-止] 文本」一行一句段，
       候选是逐段转写）⇒ 必须统一到**纯文本**再比。
    """
    out = []
    for ln in (text or '').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        # 去掉行首的 [  0.0-   13.7] 时间戳
        ln = re.sub(r'^\[\s*[0-9.]+\s*-\s*[0-9.]+\s*\]\s*', '', ln)
        ln = re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', ' ', ln).lower()
        out.extend(ln.split())
    return out


def bootstrap_ci(delta_samples, alpha=0.05):
    """配对 bootstrap 的 CI（对 Δ 的分布重采样）。"""
    n = len(delta_samples)
    if n < 2:
        return (float('nan'), float('nan'))
    rnd = random.Random(20261025)     # 固定种子 ⇒ 可复现
    means = []
    for _ in range(N_BOOT):
        s = 0.0
        for _ in range(n):
            s += delta_samples[rnd.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(alpha / 2 * N_BOOT)]
    hi = means[min(N_BOOT - 1, int((1 - alpha / 2) * N_BOOT))]
    return lo, hi


# ── stitch 实现（离线复刻，不 import 被测模块）────────────────────────
def norm_word(w):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (w or '').lower())


def make_stitch(stopwords, use_stop_guard, char_min=2, char_max=24):
    """构造一个 stitch 实现。

    use_stop_guard=True  ⇒ 工作区在制品的判据（n=1 停用词不删）
    use_stop_guard=False ⇒ 候选改进档（n=1 一律按「切点穿词」处理）
    """
    sw = stopwords or frozenset()

    def _is_sw(w):
        return norm_word(w) in sw

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
            if n == 1 and use_stop_guard and _is_sw(words[0]):
                continue
            rest = words[n:]
            return ' '.join(rest) if rest else text
        return text

    return stitch


def stitch_old(prev_words, text):
    """修复前：只试 n=3,2。"""
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


def load_stopwords():
    src = open(os.path.join(REPO, 'live_caption', 'live_caption_app.py'),
               encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_STITCH_STOPWORDS':
                    exec(compile(ast.Module(body=[node], type_ignores=[]),
                                 '<sw>', 'exec'), ns)
    return ns.get('_STITCH_STOPWORDS', frozenset())


def per_block_errors(ref, hyp, K):
    """把编辑距离**按参照 token 的位置**归位到 K 个块。

    🔴 **为什么要归位**：语料级配对 bootstrap 需要**配对**的 per-block
       统计量 ⇒ 每个错误必须能指回参照里的某个 token 区间
       ⇒ 用 SequenceMatcher 的 opcodes 把每个 replace/delete 区间
         按「ref 区间落在哪个块」摊派。

    返回：长度 K 的列表，每项 = 该块上的错误数。
    """
    blk = [0] * K
    sm = difflib.SequenceMatcher(a=list(ref), b=list(hyp), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        a = i2 - i1
        b = j2 - j1
        err = max(a, b)
        if i2 == i1:
            # 纯插入（ref 侧为空）⇒ 摊到 i1 所在块
            blk[i1 % K] += err
            continue
        # replace/delete：按 ref 区间长度摊到覆盖到的块
        n_blk = len(set(range(i1, i2)))
        base, extra = divmod(err, n_blk)
        for k, pos in enumerate(range(i1, i2)):
            blk[pos % K] += base + (1 if k < extra else 0)
    return blk


def build_hyp(segs, stitch_fn, use_prev_text):
    """按 App 的 stitch 逻辑把分段拼成完整转写。"""
    outs = []
    prev_words = []
    prev_text = ''
    for s in segs:
        txt = s.get('text') or ''
        if not txt.strip():
            continue
        if use_prev_text:
            out = stitch_fn(prev_words, txt, prev_text)
        else:
            out = stitch_fn(prev_words, txt)
        outs.append(out)
        prev_words = out.split()[-3:] if out.split() else []
        prev_text = out
    return '\n'.join(outs)


def main():
    if not os.path.exists(REF_TXT):
        print('!! 缺参照：%s' % REF_TXT)
        return 1
    ref_tokens = norm_tokens(open(REF_TXT, encoding='utf-8').read())
    print('独立参照（c048 adaptive，精确复现 7.798%%）：%d 词' % len(ref_tokens))
    print()

    sw = load_stopwords()
    stop_guard = make_stitch(sw, use_stop_guard=True)
    no_guard = make_stitch(sw, use_stop_guard=False)

    variants = [
        ('① 旧 stitch（只试 n=3,2）—— 现状', stitch_old, False),
        ('② 在制品（n=3→1 + 停用词安全阀 + 字符级）', stop_guard, True),
        ('③ 候选改进（n=3→1，无停用词表 + 字符级）', no_guard, True),
    ]

    results = {}
    for gname in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % gname)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        segs = d['segments']
        print('═══ %s 组（%s）═══' % (gname, d.get('engine', '?')))

        hyp_tokens = {}
        for label, fn, use_pt in variants:
            hyp = build_hyp(segs, fn, use_pt)
            toks = norm_tokens(hyp)
            hyp_tokens[label] = toks
            err, rl = wer_counts(ref_tokens, toks)
            pct = 100.0 * err / rl if rl else 0.0
            print('  %s' % label)
            print('      词数 %d / 参照 %d   WER = %.3f%%  (errors=%d)'
                  % (len(toks), rl, pct, err))
            results.setdefault(gname, {})[label] = dict(
                n_words=len(toks), wer_pct=pct, errors=err)

        # ── 配对 bootstrap：③ vs ①（候选改进 vs 现状）──
        base = variants[0][0]
        cand = variants[2][0]
        d1 = results[gname][base]['wer_pct']
        d2 = results[gname][cand]['wer_pct']
        print('  ⇒ Δ(③ − ①) = %+.3f pp' % (d2 - d1))
        print()

    # ── 语料级配对 bootstrap（A+B 合并）──
    if 'A' in results and 'B' in results:
        base = variants[0][0]
        cand = variants[2][0]
        # ── 语料级配对 bootstrap ──
        # 🔴 **方法**：把编辑距离按**参照 token 的位置**归位到 K 个块
        #   （用 SequenceMatcher 的 opcodes 把 ref 区间映射到块），
        #   每块单独算「这一块的错误数」⇒ 得到**配对**的 per-block 错误向量
        #   （两个候选共享同一套参照分块）⇒ 对块**重采样**求 Δ 的分布。
        #   ⇒ 这才是「语料级配对 bootstrap」；不做分块的全局重采样是错的。
        print('─── 语料级配对 bootstrap（③ vs ①）───')
        K = 40
        for gname in ('A', 'B'):
            segs_p = os.path.join(AB_DIR, 'segments_%s.json' % gname)
            d = json.load(open(segs_p, encoding='utf-8'))
            segs = d['segments']
            h1 = norm_tokens(build_hyp(segs, stitch_old, False))
            h3 = norm_tokens(build_hyp(segs, no_guard, True))
            e1, rl = wer_counts(ref_tokens, h1)
            e3, _ = wer_counts(ref_tokens, h3)
            w1 = 100.0 * e1 / rl
            w3 = 100.0 * e3 / rl
            print('  %s 组：WER %.3f%% → %.3f%%   Δ = %+.3f pp'
                  % (gname, w1, w3, w3 - w1))

            # per-block 错误数（配对）
            blk1 = per_block_errors(ref_tokens, h1, K)
            blk3 = per_block_errors(ref_tokens, h3, K)
            # 每块的「参照词数」⇒ per-block WER
            blk_ref = [0] * K
            for i in range(len(ref_tokens)):
                blk_ref[i % K] += 1

            ds = []
            rnd = random.Random(20261025)
            for _ in range(N_BOOT):
                idx = [rnd.randrange(K) for _ in range(K)]
                num = sum(blk3[i] - blk1[i] for i in idx)
                den = sum(blk_ref[i] for i in idx)
                ds.append(100.0 * num / den if den else 0.0)
            ds.sort()
            lo = ds[int(0.025 * N_BOOT)]
            hi = ds[min(N_BOOT - 1, int(0.975 * N_BOOT))]
            print('    per-block 配对 bootstrap CI（K=%d, %d 次）= [%+.3f, %+.3f] pp'
                  % (K, N_BOOT, lo, hi))
            print('    ⇒ CI 上界 %s 0 ⇒ %s'
                  % ('<' if hi < 0 else '≥',
                     '**改善（不劣化）**' if hi < 0 else '**不能判定改善**'))
            print()
            results.setdefault(gname, {})['ci_3_vs_1'] = [lo, hi]
            results.setdefault(gname, {})['delta_3_vs_1_pp'] = w3 - w1

    op = os.path.join(HERE, 'app024_stitch_wer.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print()
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
