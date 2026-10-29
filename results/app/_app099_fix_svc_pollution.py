#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§99：修 `tts_service.py` 的 **bytes 转义污染**（当前已不是合法 UTF-8）。

🔴 **为什么必须修**：上一轮的 bytes 级替换把中文注释写成了
   `\\uff08`（**字面反斜杠+u**），甚至写出**非法 UTF-8 字节**
   ⇒ `compile()` 直接 SyntaxError ⇒ **客户包一启动就崩**。

🔴 纪律：行级定位（**锚点 + 固定块长**）+ 唯一命中 + 写盘前 compile 校验。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TARGET = os.path.join(ROOT, 'live_caption', 'tts_service.py')

raw = open(TARGET, 'rb').read()
print('before: %d bytes' % len(raw))

_LIT_ESC = re.compile(rb'\\u[0-9a-fA-F]{4,6}')


def patch(anchor: bytes, block_len: int, new_lines, note: str,
          include_anchor: bool = False):
    """替换「anchor 行（可选）+ 其后 block_len-1 行」为 new_lines。"""
    global raw
    lines = raw.split(b'\r\n')
    hit = [i for i, l in enumerate(lines) if anchor in l]
    assert len(hit) == 1, \
        '❌ 锚点命中 %d 行（期望 1）：%r' % (len(hit), anchor[:70])
    i0 = hit[0] if include_anchor else hit[0] + 1
    nb = [x.replace('\n', '\r\n').encode('utf-8') for x in new_lines]
    assert len(nb) == block_len, \
        '❌ 块长不匹配：新 %d 行 vs 旧 %d 行' % (len(nb), block_len)
    lines[i0:i0 + block_len] = nb
    raw = b'\r\n'.join(lines)
    print('  OK  %s（行 %d 起 %d 行）' % (note, i0 + 1, block_len))


# ── ① __init__ 注释块 ─────────────────────────────────────────
patch(
    b'self._reader_threads: List = []',
    3,
    [
        '        # \U0001F501§99（断链 C）：**worker 的说话人音色登记结果**',
        '        #   主进程不能「发命令就算成功」，必须等 worker 确认。',
        '        #   而之前 **没有任何分派分支** ⇒ 已经发出去的命令也标成「成功」。',
    ],
    '__init__ 注释块')

# ── ② _handle_event 的 spk_voice 分支注释 ─────────────────────
patch(
    b"elif kind == 'spk_voice':",
    3,
    [
        '            # \U0001F501§99（断链 C）：worker 登记结果回执',
        '            #   → 主进程必须**等这个确认**才能标「已有音色」。',
        '            #   ok=True → 已成功；ok=False → 登记失败（回落预设 A）。',
    ],
    'spk_voice 分支注释')

# ── ③ on_log：字面转义 `\uff1a` → `：` ───────────────────────
patch(
    b'\xe8\xaf\x9d\xe9\x9f\xb3\xe4\xba\xba\xe9\x9f\xb3\xe8\x89\xb2\xe7\x99\xbb\xe8\xae\xb0 %s',   # 「说话人音色登记 %s」
    1,
    ["            self.on_log('[TTS] 说话人音色登记 %s：%s'"],
    'on_log 抬头',
    include_anchor=True)

patch(
    b"else '\xe5\xa4\xb1\xe8\xb4\xa5\\uff08%s\xef\xbc\x89'",   # 「else '失败\uff08%s）'」
    1,
    ["                           else '失败（%s）'"],
    'on_log 失败分支',
    include_anchor=True)

# ── ④ spk_voice_status 的 docstring ──────────────────────────
patch(
    b'def spk_voice_status(self, spk: str):',
    6,
    [
        '        """\U0001F501§99（断链 C）：**取用**已收到的说话人音色登记结果。',
        '',
        '        → 返回 `None` 表示「worker 还没回」；',
        '        → 返回 `dict(ok=..., dur_s=..., message=...)` 表示「已回」。',
        '        → **取出即消费**（一个 spk 只能被结算一次）。',
        '        """',
    ],
    'spk_voice_status docstring')

# ── 残留检查 ───────────────────────────────────────────────────
lines = raw.split(b'\r\n')
bad = [i for i, l in enumerate(lines) if _LIT_ESC.search(l)]
for i in bad:
    print('  ⚠️ 仍有字面转义 行%d: %r' % (i + 1, lines[i][:120]))
assert not bad, '❌ 仍有 %d 行字面转义 ⇒ 不写盘' % len(bad)

# ── UTF-8 合法性 ──────────────────────────────────────────────
try:
    raw.decode('utf-8')
except UnicodeDecodeError as e:
    raise SystemExit('❌ 仍有非法 UTF-8 ⇒ 不写盘：%s' % e)

# ── 写盘 + 编译校验 ───────────────────────────────────────────
try:
    compile(raw, TARGET, 'exec')
except Exception as e:
    raise SystemExit('❌ COMPILE FAIL ⇒ 不写盘：%s' % e)
with open(TARGET, 'wb') as f:
    f.write(raw)
print('after : %d bytes  →  UTF-8 OK + COMPILE OK' % len(raw))
