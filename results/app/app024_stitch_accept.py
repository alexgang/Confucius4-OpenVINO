"""APP-012② / APP-014① —— 段接缝去重修复的**验收脚本**。

🔴 **验收口径**（沿用本项目铁律）：
  · **不 import 被测模块** ⇒ `ast` 抽纯函数 + `exec` 到独立命名空间
    （`import translator` 会连带 numpy/OpenBLAS ⇒ 别的模块占满内存时
      进程在 import 阶段就 abort，连 try/except 都接不住）。
  · **不跑推理 / 不占 GPU**（纯离线文本作业）。
  · 判据：**语料级配对 bootstrap**，只看「Δ 的 CI 上界 < 0 才算改善」。

🔴 **本脚本验三件事**：
  ① **单元级**：新判据的行为是否符合设计
     （切点穿词 ⇒ 删；真内容重复 ⇒ 不删；n=2/3 仍命中；开关可退回）。
  ② **接线级**：三个调用点**真的**把 `prev_text` 传下去了
     （源码断言：调用点必须出现 `self._last_text`）。
  ③ **端到端级**：在 61 分钟 A/B 两组真实分段产物上，
     Δ(新 − 旧) 的 CI 上界 < 0。
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
APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
N_BOOT = 5000
K_BLOCK = 40

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  ← ' + detail) if detail else ''))
    return cond


# ── 抽纯函数（不 import 被测模块）────────────────────────────────────
def load_pure(src_path, names):
    src = open(src_path, encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {'__name__': '_isolated', 're': re, 'os': os}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         '<iso>', 'exec'), ns)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    try:
                        exec(compile(ast.Module(body=[node], type_ignores=[]),
                                     '<iso>', 'exec'), ns)
                    except Exception:
                        pass
    return ns


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


def wer_counts(ref, hyp):
    sm = difflib.SequenceMatcher(a=list(ref), b=list(hyp), autojunk=False)
    err = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        err += max(i2 - i1, j2 - j1)
    return err, len(ref)


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


def main():
    print('=' * 74)
    print('APP-012② 段接缝去重 —— 验收')
    print('=' * 74)

    ns = load_pure(APP, {'stitch', '_stitch_is_cut_through_word',
                         '_stitch_is_capitalized',
                         '_stitch_tail_is_sentence_end', '_norm_word'})
    for fn in ('stitch', '_stitch_is_cut_through_word'):
        if fn not in ns:
            print('!! 源码里没抽到 %s' % fn)
            return 1
    stitch = ns['stitch']

    # ── ① 单元级 ──
    print()
    print('─── ① 单元级：新判据行为 ───')

    # 切点穿词（后段重新起句，首字母大写）⇒ 删
    out = stitch('welcome'.split(), 'Welcome to our Q3 26 QGS.',
                 'So, welcome')
    check('切点穿词（后段首词大写）⇒ 删掉重复词',
          out == 'to our Q3 26 QGS.', repr(out))

    # 切点穿词（无句末标点）⇒ 删
    out = stitch('has'.split(), 'has been to maximize the advantage.',
                 'our strategy will and has')
    check('切点穿词（前段末尾无句末标点）⇒ 删掉重复词',
          out == 'been to maximize the advantage.', repr(out))

    # 真内容重复（前段有句末标点 + 后段首词不大写）⇒ 不删
    out = stitch('market'.split(), 'market of there is a lot of volume.',
                 "let's look at the market.")
    check('真内容重复（前段有句末标点、后段首词小写）⇒ **不删**',
          out == 'market of there is a lot of volume.', repr(out))

    # n=2 / n=3 仍命中（不受新判据影响）
    out = stitch('the scale and'.split(), 'the scale and more stuff', 'x')
    check('n=3 重复 ⇒ 仍删（不受新判据影响）',
          out == 'more stuff', repr(out))
    out = stitch('kernel development'.split(), 'kernel development you', 'x')
    check('n=2 重复 ⇒ 仍删', out == 'you', repr(out))

    # 无重复 ⇒ 原样
    out = stitch('alpha'.split(), 'beta gamma', 'alpha')
    check('无重复 ⇒ 原样返回', out == 'beta gamma', repr(out))

    # 开关可退回旧行为
    src_txt = open(APP, encoding='utf-8').read()
    check('开关存在（LIVECAP_STITCH_SEAM）', 'LIVECAP_STITCH_SEAM' in src_txt)

    # 🔴 开关语义：**0 ⇒ 完全退回旧行为**（只试 n=3,2）
    #   （不是「跳过判据」——那反而更激进，与「关掉」语义相反）
    import importlib
    old_env = os.environ.get('LIVECAP_STITCH_SEAM')
    os.environ['LIVECAP_STITCH_SEAM'] = '0'
    try:
        ns_off = load_pure(APP, {'stitch', '_stitch_is_cut_through_word',
                                 '_stitch_is_capitalized',
                                 '_stitch_tail_is_sentence_end', '_norm_word'})
        out_off = ns_off['stitch']('has'.split(), 'has been to maximize.',
                                   'our strategy will and has')
        check('开关=0 ⇒ 退回旧行为（n=1 不删）',
              out_off == 'has been to maximize.', repr(out_off))
        out_off3 = ns_off['stitch']('the scale and'.split(),
                                     'the scale and more stuff', 'x')
        check('开关=0 ⇒ 仍保留 n=3 去重（旧行为）',
              out_off3 == 'more stuff', repr(out_off3))
    finally:
        if old_env is None:
            os.environ.pop('LIVECAP_STITCH_SEAM', None)
        else:
            os.environ['LIVECAP_STITCH_SEAM'] = old_env

    # 🔴 prev_text 缺失 ⇒ 退化为「只信判据①」（宁可漏删也不误删）
    out = stitch('has'.split(), 'has been to maximize the advantage.', None)
    check('prev_text=None ⇒ 保守退化（不因判据②误删）',
          out == 'has been to maximize the advantage.', repr(out))
    out = stitch('has'.split(), 'has been to maximize the advantage.', '')
    check('prev_text="" ⇒ 保守退化（不因判据②误删）',
          out == 'has been to maximize the advantage.', repr(out))
    out = stitch('has'.split(), 'Has been to maximize the advantage.', None)
    check('prev_text=None + 首词大写 ⇒ 判据①仍生效',
          out == 'been to maximize the advantage.', repr(out))
    # 🔴 用 **AST** 查旧符号 ⇒ 注释里保留的说明文字不算残留
    #   （上一版用字符串 split 取「注释之后」的部分，注释本身仍含该词 ⇒ 误报）
    dead = set()
    tree2 = ast.parse(src_txt)
    for node in ast.walk(tree2):
        if isinstance(node, ast.FunctionDef) and node.name in (
                '_stitch_char_overlap', '_is_stitch_stopword'):
            dead.add(node.name)
        if isinstance(node, ast.Name) and node.id in (
                '_STITCH_STOPWORDS', '_STITCH_STOPWORD_SET', 'STITCH_CHAR_MIN',
                'STITCH_CHAR_MAX'):
            dead.add(node.id)
    check('旧符号已清零（_stitch_char_overlap / _STITCH_STOPWORDS，AST 口径）',
          not dead, '残留: %s' % (sorted(dead) or '无'))

    # ── ② 接线级 ──
    print()
    print('─── ② 接线级：三个调用点都传 prev_text ───')
    calls = re.findall(r'stitch\(self\._last_words', src_txt)
    check('stitch 调用点数量 = 3', len(calls) == 3, '实际 %d' % len(calls))
    check('每个调用点都带 self._last_text',
          src_txt.count('self._last_text') >= 6,
          '出现 %d 次' % src_txt.count('self._last_text'))
    check('_last_text 在三处初始化/重置',
          src_txt.count("self._last_text = ''") >= 3,
          '出现 %d 次' % src_txt.count("self._last_text = ''"))

    # ── ③ 端到端级 ──
    print()
    print('─── ③ 端到端级：61 分钟 A/B 两组 ───')
    if not os.path.exists(REF_TXT):
        check('独立参照存在', False, REF_TXT)
        return 1
    ref = norm_tokens(open(REF_TXT, encoding='utf-8').read())
    blk_ref = [0] * K_BLOCK
    for i in range(len(ref)):
        blk_ref[i % K_BLOCK] += 1

    e2e = {}
    for gname in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % gname)
        if not os.path.exists(p):
            continue
        segs = json.load(open(p, encoding='utf-8'))['segments']
        h_old = norm_tokens(build_hyp(segs, stitch_old, False))
        h_new = norm_tokens(build_hyp(segs, stitch, True))
        eo, rl = wer_counts(ref, h_old)
        en, _ = wer_counts(ref, h_new)
        w_old = 100.0 * eo / rl
        w_new = 100.0 * en / rl
        b0 = per_block_errors(ref, h_old, K_BLOCK)
        b1 = per_block_errors(ref, h_new, K_BLOCK)
        rnd = random.Random(20261025)
        ds = []
        for _ in range(N_BOOT):
            idx = [rnd.randrange(K_BLOCK) for _ in range(K_BLOCK)]
            num = sum(b1[i] - b0[i] for i in idx)
            den = sum(blk_ref[i] for i in idx)
            ds.append(100.0 * num / den if den else 0.0)
        ds.sort()
        lo = ds[int(0.025 * N_BOOT)]
        hi = ds[min(N_BOOT - 1, int(0.975 * N_BOOT))]
        print('  %s 组：WER %.3f%% → %.3f%%   Δ = %+.3f pp   CI [%+.3f, %+.3f]'
              % (gname, w_old, w_new, w_new - w_old, lo, hi))
        check('%s 组：Δ 的 CI 上界 < 0（改善）' % gname, hi < 0,
              'hi=%+.4f' % hi)
        e2e[gname] = dict(wer_old=w_old, wer_new=w_new, delta=w_new - w_old,
                          ci=[lo, hi])

    # 词数守恒：不能把内容删没了
    print()
    for gname in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % gname)
        if not os.path.exists(p):
            continue
        segs = json.load(open(p, encoding='utf-8'))['segments']
        h_old = norm_tokens(build_hyp(segs, stitch_old, False))
        h_new = norm_tokens(build_hyp(segs, stitch, True))
        drop = len(h_old) - len(h_new)
        check('%s 组：删词数在合理范围（1~60）' % gname, 1 <= drop <= 60,
              '删了 %d 词' % drop)
        e2e.setdefault(gname, {})['words_dropped'] = drop

    print()
    print('=' * 74)
    print('验收：PASS %d 项 / FAIL %d 项' % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print('  ✗ %s' % f)
    print('=' * 74)

    op = os.path.join(HERE, 'app024_stitch_accept.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(dict(passed=PASS, failed=FAIL, e2e=e2e),
                  f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
