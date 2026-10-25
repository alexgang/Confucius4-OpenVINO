"""APP-012② / APP-014① —— 离线量化「段接缝重复词消除」的收益。

🔴🔴 **为什么必须离线先验**：APP-012② 说 App 实时路径 WER 比交付基准
   差 **+2.6pp**，根因是 **rule1 切点穿过一个词** ⇒ 前后两段都转写出来。
   修复动的是**接缝去重**（`live_caption_app.py::stitch`）⇒ 必须先在
   **已有的 61 分钟 A/B 分段产物**上离线复算，确认：
     ① 旧 stitch（只试 n=3,2）到底命中几次；
     ② 新 stitch（n=3→1 + 字符级重叠）命中几次、消掉多少词；
     ③ 对 WER 的**估计收益**（按插入/删除词数算）。

⚠️ **口径纪律**（沿用本项目铁律）：
  · **不 import 被测模块** ⇒ `import translator` 会连带 numpy/OpenBLAS
    ⇒ 别的模块占满内存时进程在 import 阶段就 abort（连 try/except 都接不住）
    ⇒ 改用 `ast` 抽取源码 + `exec` 到独立命名空间。
  · 只做**离线文本**处理，**不跑推理/不占 GPU**。
  · 参照必须**独立**（用官方 transcript 作参照，不拿自己当自己）。

素材：`reports/asr004_ab/segments_{A,B}.json`（ASR 模块的 A/B 两组分段产物，
      段边界由**真实 `live_caption_app.Segmenter`** 判定 ⇒ 与 App 实时路径逐点一致）。
参照：`reports/asr004_ab/transcript_{A,B}.txt`（对应组的完整转写，作为「段拼接后」的对照）。
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
AB_DIR = os.path.join(REPO, 'reports', 'asr004_ab')


# ── 从源码抽取 stitch 相关纯函数（**不 import 被测模块**）────────────
def load_stitch_from_source(src_path: str):
    """用 ast 抽 ``stitch`` / ``_stitch_char_overlap`` / ``_norm_word``
    等**纯函数**，exec 到独立命名空间。

    🔴 **为什么不用 import**：`live_caption_app.py` 顶层 import 了
       `device_config` / `translator` 等模块 ⇒ 连带 numpy / OpenBLAS ⇒
       在别的模块占满内存时**进程在 import 阶段就 abort**（try/except 接不住）。
       ⇒ 只取纯函数源码，**零依赖**。
    """
    src = open(src_path, encoding='utf-8').read()
    tree = ast.parse(src)

    want_funcs = {'_norm_word', 'stitch', '_stitch_char_overlap',
                  '_is_stitch_stopword'}
    want_consts = {'STITCH_MAX_NGRAM', 'STITCH_CHAR_MIN', 'STITCH_CHAR_MAX',
                   'STITCH_SEAM_ENABLED', '_STITCH_STOPWORDS'}

    ns = {'__name__': '_stitch_isolated', 're': re, 'os': os}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in want_funcs:
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         '<stitch>', 'exec'), ns)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in want_consts:
                    exec(compile(ast.Module(body=[node], type_ignores=[]),
                                 '<stitch>', 'exec'), ns)
    missing = want_funcs - set(ns.keys())
    if missing:
        raise SystemExit('!! 源码里没抽到这些函数：%s' % sorted(missing))
    return ns


def load_stitch_reference():
    """**修复前**的旧 stitch（只试 n=3,2）—— 用作对照基线。"""
    ns = {'__name__': '_stitch_old', 're': re}

    def _norm_word(w):
        return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (w or '').lower())

    def stitch(prev_words, text):
        if not prev_words or not text:
            return text
        words = text.split()
        nw = [_norm_word(w) for w in words]
        prev = [_norm_word(w) for w in prev_words]
        for n in (3, 2):
            if len(nw) >= n and len(prev) >= n and prev[-n:] == nw[:n]:
                rest = words[n:]
                return ' '.join(rest) if rest else text
        return text

    ns['_norm_word'] = _norm_word
    ns['stitch'] = stitch
    return ns


# ── 文本工具 ─────────────────────────────────────────────────────────
def words_of(s: str):
    return (s or '').split()


def count_tokens(s: str) -> int:
    """按「去空白字符数」口径计字数（沿用本项目「原文守恒」口径）。"""
    return len(re.sub(r'\s+', '', s or ''))


def norm_text(s: str) -> str:
    """归一化：去标点、小写、压空白（用于词级比较）。"""
    s = re.sub(r'[^0-9a-z\u4e00-\u9fff]+', ' ', (s or '').lower())
    return re.sub(r'\s+', ' ', s).strip()


def ref_tokens(s: str):
    return norm_text(s).split()


# ── 核心：跑一遍分段产物，统计接缝去重效果 ─────────────────────────
def run_group(segs, new_ns, old_ns):
    """把分段按顺序拼起来（App 实时路径的 stitch 逻辑），统计效果。"""
    stats = dict(
        n_segs=0,
        n_pairs=0,                 # 相邻段对数
        old_hit=0,                 # 旧 stitch 命中次数
        new_hit=0,                 # 新 stitch 命中次数
        new_hit_word=0,            # 新 stitch 消掉的词数（整词级）
        new_hit_char=0,            # 新 stitch 消掉的字符数（字符级）
        chars_before=0,            # 拼接前总字数
        chars_after_old=0,         # 旧 stitch 拼接后字数
        chars_after_new=0,         # 新 stitch 拼接后字数
        samples=[],                # 命中样例
    )
    prev_words = []
    prev_text = ''
    for s in segs:
        txt = s.get('text') or ''
        if not txt.strip():
            continue
        stats['n_segs'] += 1
        stats['chars_before'] += count_tokens(txt)

        # ── 旧 stitch ──
        old_out = old_ns['stitch'](prev_words, txt)
        # ── 新 stitch（带 prev_text，字符级生效）──
        new_out = new_ns['stitch'](prev_words, txt, prev_text)

        stats['chars_after_old'] += count_tokens(old_out)
        stats['chars_after_new'] += count_tokens(new_out)

        if prev_words:
            stats['n_pairs'] += 1
            # 旧 stitch 是否真的删了东西
            if count_tokens(old_out) < count_tokens(txt):
                stats['old_hit'] += 1
            if count_tokens(new_out) < count_tokens(txt):
                stats['new_hit'] += 1
                dw = count_tokens(txt) - count_tokens(new_out)
                # 整词级 vs 字符级：整词级删的是完整词
                n_word = 0
                w_prev = words_of(prev_text)[-3:]
                w_cur = words_of(txt)
                for n in (3, 2, 1):
                    if len(w_prev) >= n and len(w_cur) >= n and \
                            [new_ns['_norm_word'](x) for x in w_prev[-n:]] == \
                            [new_ns['_norm_word'](x) for x in w_cur[:n]]:
                        n_word = n
                        break
                if n_word:
                    stats['new_hit_word'] += n_word
                else:
                    stats['new_hit_char'] += dw
                if len(stats['samples']) < 12:
                    stats['samples'].append(dict(
                        rule=s.get('rule'),
                        prev=prev_text[-90:],
                        cur=txt[:90],
                        removed=dw,
                        kind='word' if n_word else 'char',
                    ))

        # 更新前段状态（与 App 一致：取末尾 3 个词）
        prev_words = new_out.split()[-3:] if new_out.split() else []
        prev_text = new_out

    return stats


def main():
    src = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
    new_ns = load_stitch_from_source(src)
    old_ns = load_stitch_reference()

    print('=' * 74)
    print('APP-012② 段接缝重复词消除 —— 离线量化（61 分钟 A/B 两组分段产物）')
    print('=' * 74)
    print()
    print('素材：reports/asr004_ab/segments_{A,B}.json')
    print('      （段边界由真实 live_caption_app.Segmenter 判定 ⇒ 与 App 实时路径逐点一致）')
    print('源码：live_caption/live_caption_app.py（ast 抽取纯函数，**不 import 被测模块**）')
    print()

    result = {}
    for name in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % name)
        if not os.path.exists(p):
            print('!! 缺素材：%s' % p)
            continue
        d = json.load(open(p, encoding='utf-8'))
        segs = d['segments']
        st = run_group(segs, new_ns, old_ns)

        print('─── %s 组（%s）───' % (name, d.get('engine', '?')))
        print('  段数 %d，相邻段对 %d' % (st['n_segs'], st['n_pairs']))
        print('  旧 stitch（只试 n=3,2）命中：%d 次' % st['old_hit'])
        print('  新 stitch（n=3→1 + 字符级）命中：%d 次' % st['new_hit'])
        print('    其中整词级消词 %d 个 / 字符级消字 %d 个'
              % (st['new_hit_word'], st['new_hit_char']))
        print('  字数（去空白口径）：拼接前 %d ⇒ 旧 %d ⇒ 新 %d'
              % (st['chars_before'], st['chars_after_old'], st['chars_after_new']))
        removed = st['chars_before'] - st['chars_after_new']
        print('  ⇒ 新 stitch 共消掉 %d 个字符' % removed)
        if st['n_pairs']:
            print('  ⇒ 平均每 100 对相邻段消掉 %.2f 个字符'
                  % (removed * 100.0 / st['n_pairs']))
        print()
        if st['samples']:
            print('  命中样例：')
            for smp in st['samples'][:6]:
                print('   [%s/%s] ...%s | %s...  (-%d)'
                      % (smp['rule'], smp['kind'], smp['prev'], smp['cur'],
                         smp['removed']))
            print()
        result[name] = st

    # ── 与参照 transcript 比对 ──
    print('─── 与参照 transcript 的偏差 ───')
    for name in ('A', 'B'):
        tp = os.path.join(AB_DIR, 'transcript_%s.txt' % name)
        if not os.path.exists(tp):
            continue
        ref = open(tp, encoding='utf-8').read()
        ref_chars = count_tokens(ref)
        st = result.get(name)
        if not st:
            continue
        # 参照 transcript 本身就是「拼接后」的产物 ⇒ 用它当「旧 stitch」那一档
        print('  %s 组：参照 transcript %d 字 / 新 stitch 拼接后 %d 字 ⇒ 差 %+d'
              % (name, ref_chars, st['chars_after_new'],
                 st['chars_after_new'] - ref_chars))
    print()

    # ── 落盘 ──
    out = os.path.join(HERE, 'app024_stitch_offline.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
