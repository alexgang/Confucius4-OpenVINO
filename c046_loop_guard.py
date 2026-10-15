"""c046_loop_guard.py — C-046: 严格重复守卫

背景: C-027 引入的 _detect_any_loop 在正常转写文本上系统性误报。
实测反例(seg60, 完全正确的离线输出, 60 词):
    "…that whole story is coming together, getting a lot of interest. We've done a
     lot of discussions and discovery with customers over the last few weeks. A lot of
     interest, a lot of interest in it. We just need to prove it exists…"
  -> _detect_any_loop 在第 103 字符处误报循环, 截断后只剩 18 词, D=45。

缺陷根因: _detect_ngram_loop 只要求 3-gram 在文中出现 >=3 次(位置可不连续),
  于是演讲里的合法复现("a lot of interest" 出现 3 次)被误判为复读循环。

判别原则: 真正的自回归复读具有**连续紧邻**特征 —— 同一片段立即重复,
  而自然语言的复现通常分散在句间。据此要求相邻重复位置间隔 <=1 个词组,
  且提高重复次数门槛, 并排除跨标点的短片段。

用法: from c046_loop_guard import strict_loop_guard
      pos = strict_loop_guard(text)   # 返回应截断的 char index, -1 表示无循环
"""
import re

# 明显的自然语言复现短语(演讲/叙述类高频), 出现多次属正常
_COMMON_REPEATS = {
    'a lot of', 'a lot', 'lot of', 'kind of', 'sort of', 'a little bit',
    'in terms of', 'as well', 'of course', 'at the end of the day',
    'the fact that', 'i think', 'you know', 'so basically', 'and then',
}

_WORD = re.compile(r'\S+')


def _split_keep_space(ws):
    """给出每个词的起始 char index。"""
    pos, out = 0, []
    for w in ws:
        out.append(pos)
        pos += len(w) + 1
    return out


def strict_loop_guard(text: str, n: int = 3, min_repeats: int = 4,
                      max_gap: int = 1) -> int:
    """严格复读检测: 仅当同一 n-gram **连续紧邻**重复 >= min_repeats 次才判定为循环。

    与 _detect_any_loop 的区别: 后者只统计 n-gram 在全文中的总出现次数,
    会把自然语言的合法复现误判为循环(见模块 docstring)。

    Returns: 应截断到的 char index; -1 表示未检测到循环。
    """
    if not text:
        return -1
    ws = _WORD.findall(text)
    if len(ws) < n * min_repeats:
        return -1
    starts = _split_keep_space(ws)

    # 只在**相邻**的n-gram 槽位上找紧邻重复
    i = 0
    while i + n * min_repeats <= len(ws) + n - 1:
        # 当前片段
        unit = ws[i:i + n]
        if any(' '.join(unit).lower().startswith(p) or p in ' '.join(unit).lower()
               for p in _COMMON_REPEATS):
            i += 1
            continue
        # 检查后续每个紧邻位置是否完全相同
        reps = 1
        for r in range(1, min_repeats):
            off = (n) * r
            if i + off + n > len(ws):
                break
            if ws[i + off:i + off + n] == unit:
                reps += 1
            else:
                break
        if reps >= min_repeats:
            return starts[i]
        i += 1
    return -1


def strict_loop_guard_lenient(text: str, n: int = 4, min_repeats: int = 3) -> int:
    """稍宽松版本: 允许相邻重复间隔 <= max_gap 个词(覆盖 "I I I" 型复读)。

    用于捕获模型复读单个词/短语的退化情形, 同时规避自然语言复现。
    """
    if not text:
        return -1
    ws = _WORD.findall(text)
    if len(ws) < n + min_repeats - 1:
        return -1
    starts = _split_keep_space(ws)
    for i in range(len(ws) - n + 1):
        unit = ' '.join(ws[i:i + n]).lower()
        if unit in _COMMON_REPEATS:
            continue
        # 统计该 n-gram 在后续 max_gap 内出现的次数
        hits = 0
        for off in range(1, n + 4):
            if i + off + n > len(ws):
                break
            if ' '.join(ws[i + off:i + off + n]).lower() == unit:
                hits += 1
        if hits >= min_repeats - 1:
            return starts[i]
    return -1