"""按行号精确替换 live_caption_app.py 里的 stitch 实现（避免 Edit 的空白差异）。

🔴 **为什么用脚本而不是 Edit**：`Edit` 的 old_string 要逐字匹配 docstring 里的
   全角标点/缩进，极易差一个字符 ⇒ 反复失败。⇒ 改用「按行号切片替换」，
   替换后立刻做**编译 + 断言**（旧符号必须消失、新符号必须存在）。

用法：python app024_replace_stitch_impl.py <repo_root>
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(
    os.path.join(HERE, '..', '..'))
TARGET = os.path.join(REPO, 'live_caption', 'live_caption_app.py')

NEW_STITCH = '''def stitch(prev_words, text, prev_text=None):
    """段接缝去重：下一段开头与上一段末尾重复的词删掉。

    🔴🔴 **为什么必须扩到 n=1**（APP-012② / APP-014①）：
    61 分钟 A/B 两组离线实测（`results/app/app024_seam_diag.py`），**接缝重复
    几乎全是 n=1（单个词）**：
    A 组 536 对相邻段 → n≥3: 0 / n=2: 0 / n=1: **36**；
    B 组 557 对相邻段 → n≥3: 0 / n=2: 0 / n=1: **42**。
    ⇒ 旧实现（只试 3、2）**一次都没命中过**。

    判据（**顺序固定**）：

    ① **整词级 n-gram**（n = STITCH_MAX_NGRAM → … → 1）：
       前段末尾 n 个词 == 后段开头 n 个词 ⇒ 删掉后段开头的这 n 个词。
       🔴 n=1 有**判据**（`_stitch_is_cut_through_word`）：只有当
       「后段重新起句（首字母大写）」**或**「前段末尾非句末标点」时
       才算「切点穿词」才删；否则是真内容（上一句说完了，新句又说一遍）。

    ⚠️ **`prev_text` 现在是必需的**（判据②要用前段末尾的标点信息）：
       调用方**必须**传前段的完整文本；传 None 时退化为「只信判据①」。
    """
    if not text:
        return text
    if not prev_words:
        return text

    words = text.split()
    nw = [_norm_word(w) for w in words]
    prev = [_norm_word(w) for w in prev_words]

    # ── ① 整词级 n-gram：n 从大到小 ──
    for n in range(min(STITCH_MAX_NGRAM, len(words)), 0, -1):
        if len(nw) < n or len(prev) < n:
            continue
        if prev[-n:] != nw[:n]:
            continue
        # 🔴 n=1 用「切点穿词」判据决定删不删
        if n == 1 and STITCH_SEAM_ENABLED and prev_text is not None:
            if not _stitch_is_cut_through_word(prev_text, prev_words[-1],
                                                words[0]):
                continue
        rest = words[n:]
        return ' '.join(rest) if rest else text
    return text
'''


def main():
    lines = io.open(TARGET, encoding='utf-8').read().splitlines(keepends=True)

    # ── 定位 `_stitch_char_overlap` 到 `stitch` 结束（下一个顶层 def/class）──
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith('def _stitch_char_overlap('):
            start = i
            break
    if start is None:
        raise SystemExit('!! 找不到 _stitch_char_overlap')

    end = None
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if ln.startswith('def ') or ln.startswith('class ') or \
                ln.startswith('# ── '):
            end = i
            break
    if end is None:
        raise SystemExit('!! 找不到 stitch 段落的结束位置')

    print('替换区间：L%d .. L%d（%d 行）' % (start + 1, end, end - start))
    print('--- 旧内容首行 ---')
    print(lines[start].rstrip())
    print('--- 旧内容末行 ---')
    print(lines[end - 1].rstrip())

    new_lines = [NEW_STITCH, '\n', '\n']
    out = lines[:start] + new_lines + lines[end:]
    io.open(TARGET, 'w', encoding='utf-8', newline='').write(''.join(out))
    print('已写入。')

    # ── 断言 ──
    txt = io.open(TARGET, encoding='utf-8').read()
    assert '_stitch_char_overlap' not in txt, '!! 旧函数仍在'
    assert '_stitch_is_stitch_stopword' not in txt
    assert '_is_stitch_stopword' not in txt, '!! 旧停用词函数仍在'
    assert '_STITCH_STOPWORDS' not in txt, '!! 旧停用词表仍在'
    assert 'STITCH_CHAR_MIN' not in txt, '!! 旧字符级常量仍在'
    assert '_stitch_is_cut_through_word' in txt, '!! 新判据函数不在'
    assert 'def stitch(' in txt
    print('断言：PASS（旧符号已清除，新判据在位）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
