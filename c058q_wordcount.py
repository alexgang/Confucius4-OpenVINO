"""c058q_wordcount.py — 统一的计词函数与转写落盘（C-061#5）

reviewer 指出：`c058k` 的 `total_words`（FP16）= **11042**，而 `c048`/`c057f`
同配置是 **11248**，差 206 ≈ 段数（226）。根因是 `c058k` 用了裸
`len(text.split())`，而 `c058c` 用的是带正规化的 `words()`：
裸 split 在**段与段之间没有分隔符**时会把上一段末尾和下一段开头粘成一个 token，
每粘一次就少算一个词，226 段 → 少算约 206 个。

`c058k` 当时**没有保存转写**，所以无法证明流水线的确定性，只能推测。

本模块提供：
  - `words(s)`：唯一的计词口径（小写 → 去标点 → 压缩空白 → split）。
    所有计时脚本必须改用它。
  - `save_transcript(segs, path)`：把逐段转写落盘。
    **没有转写就无法核对任何计数/精度结论**，计时作业一律要存。

用法：
  from c058q_wordcount import words, save_transcript, count_words
  total = count_words(segs)
  save_transcript(segs, 'reports/xxx/transcript_yyy.txt')
"""
import os
import re

# 与 c058m_bootstrap_crosscheck.py 的 norm() 保持一致的口径：
# 小写、弯引号归一、只保留字母数字和单引号
_PUNCT = re.compile(r"[^a-z0-9' ]+")
_WS = re.compile(r'\s+')


def words(s):
    """唯一的计词口径。小写 → 去标点 → 压缩空白 → split。

    ⚠️ 不要用裸 `text.split()`：段间无分隔符时会把相邻段的词粘成一个，
    导致每段少算一个词（c058k 曾因此少算 206 个）。
    """
    if not s:
        return []
    s = s.lower().replace('’', "'")
    s = _PUNCT.sub(' ', s)
    return [w for w in _WS.sub(' ', s).strip().split() if w]


def count_words(segs, field='text'):
    """对一串 segment dict 或 (start, end, text) 三元组计词。

    兼容 `SegmentedStreamer.run()` 返回的 dict 列表
    （{'start_s','end_s','text','rtf',...}）和旧的 tuple 形式。
    """
    total = []
    for s in segs:
        if isinstance(s, dict):
            total.extend(words(s.get(field, '') or ''))
        elif isinstance(s, (list, tuple)):
            total.extend(words(s[-1] or ''))
    return len(total)


def save_transcript(segs, path):
    """把逐段转写写到 `path`，返回写出的路径。

    格式与既有 transcript_*.txt 一致：`[start-end] text`
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    lines = []
    for s in segs:
        if isinstance(s, dict):
            st, en = s.get('start_s', 0.0), s.get('end_s', 0.0)
            tx = s.get('text', '') or ''
        else:
            st, en, tx = s[0], s[1], s[-1]
        lines.append(f'[{st:.2f}-{en:.2f}] {tx}')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path
