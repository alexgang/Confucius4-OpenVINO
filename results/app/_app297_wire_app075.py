# -*- coding: utf-8 -*-
"""APP-075(a)(b)：把 `live_caption_app.py` 的 **GUI + CLI 两条路径**接到
**登记门槛**（`registration_ticket` / `mark_registered` / `spk_conf`）。

🔴 **纪律**（记忆铁律）：
  · 只做**定点替换**（精确字符串 + **唯一命中断言**）⇒ 禁整目录覆盖；
  · 改完必须 `ast.parse` + 逐处复核；
  · 行尾保持 **LF**（本仓库工作副本是 LF ⇒ 用 `newline=''` 读写）。

## 改什么（5 处）

| # | 位置 | 改动 |
|---|---|---|
| ① | GUI `_retry_spk_labels()` L4833 | `note_final(..., spk_conf=spk_conf)` |
| ② | GUI `_on_final()` L4917 | `note_final(..., spk_conf=spk_conf)` |
| ③ | GUI `_spk_pcm_for()` | 改用 `registration_ticket()` 的合格段 |
| ④ | GUI `_pump_spk_voices()` | 登记成功后 `mark_registered()`；无合格段 ⇒ 回落预设 A + 日志 |
| ⑤ | CLI 三处 | 同 ①②③④（CLI 版） |

## 🔴🔴🔳 APP-075(b) 的三条语义（在 App 层的落点）
  · **无合格段 ⇒ 回落预设 A ＋ 记日志**，**不得**用不合格段登记；
  · **有合格段后升级登记**（覆盖旧登记）⇒ `mark_registered` 记录已用段，
    下次只有「更长」的合格段才重发；
  · **门槛只用于「选哪段音频登记」** ⇒ **绝不**因为首段 conf 低就不播
    （`voice_for_sentence()` 的回落逻辑保持不变）。
"""
from __future__ import annotations

import ast
import io
import os
import sys

PATH = os.path.join(r'C:\Users\Trekker-PTL\confucius4-openvino',
                    'live_caption', 'live_caption_app.py')

REPLACEMENTS = []


def rep(old, new, tag, count=1):
    REPLACEMENTS.append((old, new, tag, count))


# ── ① GUI `_retry_spk_labels()`：note_final 带 spk_conf ────────────
rep(
    """                _is_new = self._spk_voices.note_final(seg, spk, clean_ranges)""",
    """                # 🔴🔴🔳 APP-075(a)：**必须把 `spk_conf` 一起传进去**
                #   ⇒ 登记门槛（`REG_CONF_MIN`）才有依据
                #   ⇒ 旧签名只有 `clean_ranges` ⇒ 「这一段有多确信」
                #     **根本没进来** ⇒ 门槛无从谈起（APP-075 原话）。
                _is_new = self._spk_voices.note_final(
                    seg, spk, clean_ranges, spk_conf=spk_conf)""",
    'GUI-retry-note_final', 1)

# ── ② GUI `_on_final()`：note_final 带 spk_conf ────────────────────
rep(
    """                _is_new = self._spk_voices.note_final(
                    seg, spk, _res.get('clean_ranges'))""",
    """                # 🔴🔴🔳 APP-075(a)：**必须把 `spk_conf` 一起传进去**
                #   ⇒ 登记门槛（`REG_CONF_MIN`）才有依据。
                _is_new = self._spk_voices.note_final(
                    seg, spk, _res.get('clean_ranges'),
                    spk_conf=_res.get('spk_conf', spk_conf))""",
    'GUI-on_final-note_final', 1)

# ── ③ GUI `_spk_pcm_for()`：改用合格段 ─────────────────────────────
rep(
    '''    def _spk_pcm_for(self, spk: str, seg: int):
        """🔴 按 `clean_ranges` 切出**该 spk 自己的**干净 PCM。

        ⚠️ **区间只含该 spk** ⇒ 结构性保证「不渐变、不混入别人」。
        """
        try:
            with self._spk_pcm_lock:
                buf = self._spk_pcm_buf
            rngs = self._spk_voices.clean_ranges_of(spk)
            if not rngs:
                return None
            # 🔁 §99（断链 E）：传给缓冲起点，出口不对应全局时间轴。
            return self._spk_bridge.pcm_for_ranges(
                rngs, keep=buf, max_s=10.0, keep_t0=self._spk_pcm_t0)
        except Exception:
            return None''',
    '''    def _spk_pcm_for(self, spk: str, seg: int):
        """🔴🔴🔳 APP-075(a)：**按「合格登记段」**切出该 spk 的干净 PCM。

        ## 🔴🔴🔳 为什么不能再用 `clean_ranges_of(spk)`（旧行为）
        旧行为取该 spk 的**全部**干净区间 ⇒ **包含切换边界那一段**
        ⇒ 拿**边界那一段**（可能属于**上一个人**）去登记
        ⇒ 克隆音色串音（APP-071 现象）。

        ## 现在
        ① `registration_ticket()` 给出**唯一一段**合格音频
           （`spk_conf ≥ REG_CONF_MIN` ＋ 落在 `clean_ranges` 内
            ＋ 挖掉切换点前后 `SWITCH_GUARD_S`
            ＋ 连续 ≥ `REG_MIN_CONT_S` ＋ **取最长的那段**）；
        ② **没有合格段 ⇒ 返回 `None`**
           ⇒ 调用方**不得**用不合格段登记（APP-075(b)）
           ⇒ **回落预设 A ＋ 记日志**。

        ⚠️ **区间只含该 spk** ⇒ 结构性保证「不渐变、不混入别人」。
        """
        try:
            rngs, _key = self._spk_voices.registration_ticket(spk)
            if not rngs:
                return None
            with self._spk_pcm_lock:
                buf = self._spk_pcm_buf
            # 🔁 §99（断链 E）：传给缓冲起点，出口不对应全局时间轴。
            return self._spk_bridge.pcm_for_ranges(
                rngs, keep=buf, max_s=10.0, keep_t0=self._spk_pcm_t0)
        except Exception:
            return None''',
    'GUI-pcm_for', 1)

# ── ④ CLI `_cli_retry_spk_labels()`：note_final 带 spk_conf ────────
rep(
    """                _is_new = _spk_voices.note_final(seg, spk, clean_ranges)""",
    """                # 🔴🔴🔳 APP-075(a)：**必须把 `spk_conf` 一起传进去**
                #   ⇒ 登记门槛（`REG_CONF_MIN`）才有依据（同 GUI 侧口径）。
                _is_new = _spk_voices.note_final(
                    seg, spk, clean_ranges, spk_conf=spk_conf)""",
    'CLI-retry-note_final', 1)

# ── ⑤ CLI `on_final`：note_final 带 spk_conf ───────────────────────
rep(
    """            _is_new = _spk_voices.note_final(_seg, spk,
                                             _res.get('clean_ranges'))""",
    """            # 🔴🔴🔳 APP-075(a)：**必须把 `spk_conf` 一起传进去**
            #   ⇒ 登记门槛（`REG_CONF_MIN`）才有依据（同 GUI 侧口径）。
            _is_new = _spk_voices.note_final(
                _seg, spk, _res.get('clean_ranges'),
                spk_conf=_res.get('spk_conf', spk_conf))""",
    'CLI-on_final-note_final', 1)

# ── ⑥ GUI `_pump_spk_voices()`：mark_registered + 回落日志 ─────────
rep(
    """                if not self._spk_voices.has_voice(spk):
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
                    # 🔴 §99（断链 C）：**不立即 mark_embedded**
                    #   ⇒ 等 worker 回执（见本函数开头）。
                    self._spk_voice_sent.add((spk, False))""",
    """                if not self._spk_voices.has_voice(spk):
                    # ── 先看能不能取到「该 spk 自己的**合格**干净语音」──
                    #   🔴🔴🔳 APP-075(a)(b)：`_spk_pcm_for` 现在**只认合格段**
                    #   ⇒ 没有合格段 ⇒ 返回 `None` ⇒ **不得**用不合格段登记。
                    pcm = self._spk_pcm_for(spk, seg)
                    if pcm is None or pcm.size < int(speaker_voice.MIN_S * SR):
                        # 🔴🔴🔳 APP-075(b)：**回落预设 A ＋ 记日志**（不静默）。
                        #   ⚠️ **不是「不播」** ⇒ `voice_for_sentence()` 回落
                        #   ⇒ 该句照播，只是用预设 A（**不用错人的音色**）。
                        self._spk_voices.mark_fallback(
                            spk, 'no_qualified_run')
                        if spk not in self._spk_reason_seen:
                            self._spk_reason_seen.add(spk)
                            _g = self._spk_voices.gate_stats().get(spk) or {}
                            self._ui_log(
                                '[spk] %s 暂无合格登记段（回落预设 A）：'
                                '合格段数=%d 最长=%.1fs 门槛 conf≥%.2f 连续≥%.1fs'
                                % (spk, _g.get('n_qualified', 0),
                                   _g.get('longest_s', 0.0),
                                   speaker_voice.REG_CONF_MIN,
                                   speaker_voice.REG_MIN_CONT_S))
                        continue          # 还不够 ⇒ **等下一段**（不阻塞）
                    ok = self.tts.register_spk_voice(spk, pcm)
                    if not ok:
                        self._spk_voices.mark_fallback(spk, 'register_failed')
                        self._spk_pending_embed = [
                            (s, k) for (s, k) in self._spk_pending_embed
                            if k != spk]
                        continue
                    # 🔴🔴🔳 APP-075(b)：**记下这一段** ⇒ 下次只有「更长」的
                    #   合格段才重发（覆盖旧登记 ⇒ 升级登记）。
                    _rr, _kk = self._spk_voices.registration_ticket(spk)
                    if _rr:
                        self._spk_voices.mark_registered(
                            spk, _rr[0][0], _rr[0][1])
                    # 🔴 §99（断链 C）：**不立即 mark_embedded**
                    #   ⇒ 等 worker 回执（见本函数开头）。
                    self._spk_voice_sent.add((spk, False))""",
    'GUI-pump-mark_registered', 1)

# ── ⑦ CLI `_cli_pump_spk_voices()`：合格段 + mark_registered ───────
rep(
    """                if not _spk_voices.has_voice(spk):
                    rngs = _spk_voices.clean_ranges_of(spk)
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf
                    pcm = _spk_bridge.pcm_for_ranges(
                        rngs, keep=buf, max_s=10.0, keep_t0=_spk_pcm_t0[0])
                    if pcm is None or pcm.size < int(speaker_voice.MIN_S * SR):
                        continue
                    if not tts.register_spk_voice(spk, pcm):
                        _spk_voices.mark_fallback(spk, 'register_failed')
                        _spk_pending_embed = [
                            (x, k) for (x, k) in _spk_pending_embed if k != spk]
                        continue
                    # 🔴 §99（断链 C）：**不立即 mark_embedded** ⇒ 等 worker 回执
                    _spk_voice_sent.add((spk, False))""",
    """                if not _spk_voices.has_voice(spk):
                    # 🔴🔴🔳 APP-075(a)(b)：**只认合格段**（同 GUI 侧口径）
                    #   ⇒ 没有合格段 ⇒ **不得**用不合格段登记 ⇒ 回落预设 A。
                    rngs, _key = _spk_voices.registration_ticket(spk)
                    if not rngs:
                        _spk_voices.mark_fallback(spk, 'no_qualified_run')
                        if spk not in _cli_spk_reason_seen:
                            _cli_spk_reason_seen.add(spk)
                            _g = _spk_voices.gate_stats().get(spk) or {}
                            print(f'  [spk] {spk} 暂无合格登记段（回落预设 A）：'
                                  f'合格段数={_g.get("n_qualified", 0)} '
                                  f'最长={_g.get("longest_s", 0.0):.1f}s '
                                  f'门槛 conf>={speaker_voice.REG_CONF_MIN} '
                                  f'连续>={speaker_voice.REG_MIN_CONT_S}s',
                                  flush=True)
                        continue
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf
                    pcm = _spk_bridge.pcm_for_ranges(
                        rngs, keep=buf, max_s=10.0, keep_t0=_spk_pcm_t0[0])
                    if pcm is None or pcm.size < int(speaker_voice.MIN_S * SR):
                        continue
                    if not tts.register_spk_voice(spk, pcm):
                        _spk_voices.mark_fallback(spk, 'register_failed')
                        _spk_pending_embed = [
                            (x, k) for (x, k) in _spk_pending_embed if k != spk]
                        continue
                    # 🔴🔴🔳 APP-075(b)：**记下这一段** ⇒ 变长才升级
                    _spk_voices.mark_registered(spk, rngs[0][0], rngs[0][1])
                    # 🔴 §99（断链 C）：**不立即 mark_embedded** ⇒ 等 worker 回执
                    _spk_voice_sent.add((spk, False))""",
    'CLI-pump-mark_registered', 1)

# ── ⑧ CLI 细化路径：也改用合格段 ─────────────────────────────────
rep(
    """                elif _spk_voices.ready_to_embed(spk):
                    rngs = _spk_voices.clean_ranges_of(spk)
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf""",
    """                elif _spk_voices.ready_to_embed(spk):
                    # 🔴🔴🔳 APP-075(a)：细化也**只认合格段**
                    rngs, _key2 = _spk_voices.registration_ticket(spk)
                    if not rngs:
                        continue
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf""",
    'CLI-refine-qualified', 1)

# ── ⑨ GUI 细化路径：也改用合格段 ─────────────────────────────────
rep(
    """                    if self._spk_voices.ready_to_embed(spk):
                        pcm = self._spk_pcm_for(spk, seg)
                        if pcm is not None and \\
                                pcm.size >= int(speaker_voice.REFINE_S * SR):
                            if self.tts.register_spk_voice(spk, pcm):
                                # 🔴 §99（断链 C）：细化也等回执
                                self._spk_voice_sent.add((spk, True))""",
    """                    if self._spk_voices.ready_to_embed(spk):
                        pcm = self._spk_pcm_for(spk, seg)
                        if pcm is not None and \\
                                pcm.size >= int(speaker_voice.REFINE_S * SR):
                            if self.tts.register_spk_voice(spk, pcm):
                                # 🔴🔴🔳 APP-075(b)：**记下这一段**（升级登记）
                                _rr2, _kk2 = \\
                                    self._spk_voices.registration_ticket(spk)
                                if _rr2:
                                    self._spk_voices.mark_registered(
                                        spk, _rr2[0][0], _rr2[0][1])
                                # 🔴 §99（断链 C）：细化也等回执
                                self._spk_voice_sent.add((spk, True))""",
    'GUI-refine-qualified', 1)


def main():
    with io.open(PATH, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    orig_len = len(src)
    for old, new, tag, cnt in REPLACEMENTS:
        n = src.count(old)
        assert n == cnt, '[%s] 命中 %d 次（期望 %d）⇒ 定位失败' % (tag, n, cnt)
        src = src.replace(old, new, cnt)
        print('[OK] %-28s 替换 %d 处' % (tag, cnt))
    # 🔴 语法校验
    ast.parse(src)
    print('[ast] 解析通过')
    with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
        f.write(src)
    print('[完成] %d -> %d 字节' % (orig_len, len(src)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
