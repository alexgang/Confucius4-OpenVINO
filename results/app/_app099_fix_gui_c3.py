#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§99：修复 GUI 侧断链 C（等 worker 回执才 mark_embedded）+ 修污染注释。

🔴 纪律：
  - bytes 级精确替换（文件是 CRLF）
  - 唯一命中断言（count == 1）
  - 写盘前先 `compile()` 校验（**编译不过就不写盘**）
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TARGET = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')

raw = open(TARGET, 'rb').read()
print('before: %d bytes' % len(raw))

# 污染行的**字节特征**（`§99` 后的 `\uff08` 是**字面反斜杠+u**）
_BAD_MARK = b'\\uff08\xe6\x96\xad\xe9\x93\xbe E'


def rep(old: str, new: str, count: int = 1):
    """bytes 级替换 + 唯一命中断言。"""
    global raw
    o = old.replace('\n', '\r\n').encode('utf-8')
    n = new.replace('\n', '\r\n').encode('utf-8')
    c = raw.count(o)
    assert c == count, '❌ 命中 %d 次（期望 %d）：\n%r' % (c, count, old[:150])
    raw = raw.replace(o, n)
    print('  OK  %d×  %s' % (c, old.strip().split('\n')[0][:70]))


def rep_bad_line(new_text: str, indent: int):
    """把**被 bytes 转义写坏的注释行**整行替换掉。

    🔴 为什么不用字符串匹配：那行的**原始字节已经不是合法 UTF-8**
       ⇒ 无法用解码后的字符串去 `raw.count()`。
    ⇒ 只能按**行 + 缩进**定位（两处污染的缩进不同：12 / 20 空格）。
    """
    global raw
    lines = raw.split(b'\r\n')
    hit = [i for i, l in enumerate(lines)
           if _BAD_MARK in l
           and (len(l) - len(l.lstrip(b' '))) == indent]
    assert len(hit) == 1, \
        '❌ 缩进 %d 命中 %d 行（期望 1）' % (indent, len(hit))
    nb = new_text.replace('\n', '\r\n').encode('utf-8')
    lines[hit[0]] = nb
    raw = b'\r\n'.join(lines)
    print('  OK  行 %d 污染注释已修（indent=%d）'
          % (hit[0] + 1, indent))


# ── ① 修污染注释（L3822 / L4615，非法 UTF-8）────────────────────
rep_bad_line(
    '            # \U0001F501 §99（断链 E）：'
    '传给缓冲起点，出口不对应全局时间轴。', indent=12)
rep_bad_line(
    '                    # \U0001F501 §99（断链 E）：'
    '缓冲起点：会话的全局时刻', indent=20)

# ── ② GUI __init__：新增 `_spk_voice_sent` ─────────────────────
rep(
    '        self._spk_pending_embed = []\n'
    '        # \U0001F534\U0001F534\U0001F534 APP-039/040：**已消费的源音频秒数**（最新值）',

    '        self._spk_pending_embed = []\n'
    '        # \U0001F534 §99（断链 C）：**已发出登记命令但尚未被 worker 确认**的 spk。\n'
    '        #   ⇒ 元素为 `(spk, refined)`；收到 worker 回执才 `mark_embedded`。\n'
    '        #   ⚠️ **绝不**在 `register_spk_voice()` 返回 True 的那一刻就标成功\n'
    '        #     （那只是「命令写出去了」，不是「worker 真的算出来了」）。\n'
    '        self._spk_voice_sent = set()\n'
    '        # \U0001F534\U0001F534\U0001F534 APP-039/040：**已消费的源音频秒数**（最新值）')

# ── ③ GUI pump：改造成「先查回执，再决定」──────────────────────
OLD_PUMP = '''        for seg, spk in pending:
            try:
                if not self._spk_voices.has_voice(spk):
                    # ── 先看能不能取到「该 spk 自己的干净语音」──
                    pcm = self._spk_pcm_for(spk, seg)
                    if pcm is None or pcm.size < int(speaker_voice.MIN_S * SR):
                        continue          # 还不够 ⇒ **等下一段**（不阻塞）
                    ok = self.tts.register_spk_voice(spk, pcm)
                    if not ok:
                        self._spk_voices.mark_fallback(spk, 'register_failed')
                        self._spk_pending_embed = [
                            (s, k) for (s, k) in self._spk_pending_embed
                            if k != spk]
                        continue
                    self._spk_voices.mark_embedded(spk, refined=False)
                    self._spk_pending_embed = [
                        (s, k) for (s, k) in self._spk_pending_embed
                        if k != spk]
                    self._ui_log('[spk] %s 已登记音色（≥%.1f s 干净语音）'
                                 % (spk, speaker_voice.MIN_S))
                else:
                    # ── 已登记：够 `REFINE_S` 就用**自己的段**重算一次 ──
                    if self._spk_voices.ready_to_embed(spk):
                        pcm = self._spk_pcm_for(spk, seg)
                        if pcm is not None and \\
                                pcm.size >= int(speaker_voice.REFINE_S * SR):
                            if self.tts.register_spk_voice(spk, pcm):
                                self._spk_voices.mark_embedded(spk,
                                                                refined=True)
                                self._spk_pending_embed = [
                                    (s, k) for (s, k)
                                    in self._spk_pending_embed if k != spk]
                                self._ui_log('[spk] %s 音色已细化'
                                             % spk)
            except Exception as e:
                self._ui_log('[spk] 取样失败（忽略）：%s' % e)
'''

NEW_PUMP = '''        # \U0001F534 §99（断链 C）：**先查 worker 回执**。
        #   ⇒ `register_spk_voice()` 返回 True 只代表「命令写进管道了」，
        #     **不代表 worker 真的算出了 x-vector**。
        #   ⇒ 旧实现在这里直接 `mark_embedded` ⇒ 登记失败仍被当成成功
        #     ⇒ 该 spk **永远**显示「已登记音色」，实际用的是**预设 A**。
        #   ⇒ 现在：**只有收到 worker 的 `ok=True` 回执**才标成功。
        for _sent in list(self._spk_voice_sent):
            _s, _refined = _sent
            try:
                _st = self.tts.spk_voice_status(_s)
            except Exception:
                _st = None
            if _st is None:
                continue          # worker 还没回 ⇒ 继续等（不阻塞）
            if _st.get('ok'):
                self._spk_voices.mark_embedded(_s, refined=_refined)
                self._spk_voice_sent.discard(_sent)
                self._spk_pending_embed = [
                    (s, k) for (s, k) in self._spk_pending_embed
                    if k != _s]
                if _refined:
                    self._ui_log('[spk] %s 音色已细化' % _s)
                else:
                    self._ui_log('[spk] %s 已登记音色（≥%.1f s 干净语音）'
                                 % (_s, speaker_voice.MIN_S))
            else:
                # \U0001F534 worker 明确失败 ⇒ 回落预设 A（**不用别人冒充**）
                self._spk_voices.mark_fallback(
                    _s, 'worker_failed:%s' % (_st.get('message') or ''))
                self._spk_voice_sent.discard(_sent)
                self._spk_pending_embed = [
                    (s, k) for (s, k) in self._spk_pending_embed
                    if k != _s]
                self._ui_log('[spk] %s 音色登记失败（回落预设 A）：%s'
                             % (_s, _st.get('message') or '未知原因'))
        for seg, spk in pending:
            try:
                # \U0001F534 §99：**已经在等回执** ⇒ 本轮不再重复发命令
                if any(s == spk for s, _r in self._spk_voice_sent):
                    continue
                if not self._spk_voices.has_voice(spk):
                    # ── 先看能不能取到「该 spk 自己的干净语音」──
                    pcm = self._spk_pcm_for(spk, seg)
                    if pcm is None or pcm.size < int(speaker_voice.MIN_S * SR):
                        continue          # 还不够 ⇒ **等下一段**（不阻塞）
                    ok = self.tts.register_spk_voice(spk, pcm)
                    if not ok:
                        self._spk_voices.mark_fallback(spk, 'register_failed')
                        self._spk_pending_embed = [
                            (s, k) for (s, k) in self._spk_pending_embed
                            if k != spk]
                        continue
                    # \U0001F534 §99（断链 C）：**不立即 mark_embedded**
                    #   ⇒ 等 worker 回执（见本函数开头）。
                    self._spk_voice_sent.add((spk, False))
                else:
                    # ── 已登记：够 `REFINE_S` 就用**自己的段**重算一次 ──
                    if self._spk_voices.ready_to_embed(spk):
                        pcm = self._spk_pcm_for(spk, seg)
                        if pcm is not None and \\
                                pcm.size >= int(speaker_voice.REFINE_S * SR):
                            if self.tts.register_spk_voice(spk, pcm):
                                # \U0001F534 §99（断链 C）：细化也等回执
                                self._spk_voice_sent.add((spk, True))
            except Exception as e:
                self._ui_log('[spk] 取样失败（忽略）：%s' % e)
'''

rep(OLD_PUMP, NEW_PUMP)

# ── ④ GUI clear()：清掉 `_spk_voice_sent` ──────────────────────
rep(
    '        try:\n'
    '            self._spk_pending_embed = []\n'
    '            self._seg_span.clear()\n'
    '        except Exception:\n'
    '            pass',

    '        try:\n'
    '            self._spk_pending_embed = []\n'
    '            self._spk_voice_sent = set()\n'
    '            self._seg_span.clear()\n'
    '        except Exception:\n'
    '            pass')

# ── 写盘 + 编译校验 ───────────────────────────────────────────
try:
    compile(raw, TARGET, 'exec')
except Exception as e:
    raise SystemExit('❌ COMPILE FAIL ⇒ 不写盘：%s' % e)
with open(TARGET, 'wb') as f:
    f.write(raw)
print('after : %d bytes  →  COMPILE OK' % len(raw))
