#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§99：修 **CLI 侧断链 C** + **断链 F（细化分支死代码）**。

## 断链 F（本轮新发现）

GUI/CLI 的 pump 在**首次登记成功**后就把该 spk 从 `_spk_pending_embed` 里
**移除** ⇒ pump 下一轮再也看不到这个 spk ⇒ `else:` 分支
（「已登记：够 `REFINE_S` 就用**自己的段**重算一次」）**永远进不去**
⇒ **APP-040②「攒够 3 s 用自己的段重算一次」从不发生**。

⇒ 修法：**初次登记确认后，把 spk 重新放回 pending**（继续观察它有没有攒够
   `REFINE_S`）⇒ 细化分支才有机会触发。
⇒ ⚠️ `speaker_voice.ready_to_embed()` 在 `voice=='clone' and refined` 时
   返回 False ⇒ **不会重复细化**（APP-040②「之后不再更新」）。

## 断链 C（CLI 侧）

CLI 的 `mark_embedded` 是**无条件**调用（命令写出去就算成功）
⇒ 改成与 GUI 侧一致：**等 worker 的 `spk_voice` 回执**。

🔴 纪律：bytes 级精确替换 + 唯一命中断言 + 写盘前 compile 校验。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
TARGET = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')

raw = open(TARGET, 'rb').read()
print('before: %d bytes' % len(raw))


def rep(old: str, new: str, count: int = 1):
    global raw
    o = old.replace('\n', '\r\n').encode('utf-8')
    n = new.replace('\n', '\r\n').encode('utf-8')
    c = raw.count(o)
    assert c == count, '❌ 命中 %d 次（期望 %d）：\n%r' % (c, count, old[:160])
    raw = raw.replace(o, n)
    print('  OK  %d×  %s' % (c, old.strip().split('\n')[0][:70]))


# ══════════════════════════════════════════════════════════════
# ① CLI 闭包变量：新增 `_spk_voice_sent`
# ══════════════════════════════════════════════════════════════
rep(
    '    _spk_pending_embed = []\n'
    '    _spk_audio_end = [0.0]          # [0] = 已消费秒数（闭包内可变）',

    '    _spk_pending_embed = []\n'
    '    # \U0001F534 §99（断链 C）：**已发出登记命令但尚未被 worker 确认**的 spk。\n'
    '    #   ⇒ 元素为 `(spk, refined)`；收到 worker 回执才 `mark_embedded`。\n'
    '    _spk_voice_sent = set()\n'
    '    _spk_audio_end = [0.0]          # [0] = 已消费秒数（闭包内可变）')

# ══════════════════════════════════════════════════════════════
# ② CLI pump：等回执 + 细化分支可达
# ══════════════════════════════════════════════════════════════
OLD = '''    def _cli_pump_spk_voices():
        """🔴 APP-039/040：给新 spk 取样 + 登记音色（只在新 spk 时做事）。"""
        # 🔴🔴🔴 §97 **修真实缺陷**：本函数**重绑**了 `_spk_pending_embed`
        #   ⇒ Python 静态判定它是**本函数的局部变量** ⇒ 第 4601 行
        #     `for seg, spk in list(_spk_pending_embed)` 读取时**未赋值**
        #   ⇒ `UnboundLocalError` ⇒ **CLI 启动即崩**（run4 实测死因）。
        #   ⇒ **必须显式 `nonlocal`**。
        nonlocal _spk_pending_embed
        if tts is None or not getattr(tts, 'active', False):
            return
        for seg, spk in list(_spk_pending_embed):
            try:
                if not _spk_voices.has_voice(spk):
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
                    _spk_voices.mark_embedded(spk, refined=False)
                    _spk_pending_embed = [
                        (x, k) for (x, k) in _spk_pending_embed if k != spk]
                    print(f'  [spk] {spk} 已登记音色', flush=True)
                elif _spk_voices.ready_to_embed(spk):
                    rngs = _spk_voices.clean_ranges_of(spk)
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf
                    pcm = _spk_bridge.pcm_for_ranges(
                        rngs, keep=buf, max_s=10.0, keep_t0=_spk_pcm_t0[0])
                    if pcm is not None and \\
                            pcm.size >= int(speaker_voice.REFINE_S * SR):
                        if tts.register_spk_voice(spk, pcm):
                            _spk_voices.mark_embedded(spk, refined=True)
                            _spk_pending_embed = [
                                (x, k) for (x, k)
                                in _spk_pending_embed if k != spk]
                            print(f'  [spk] {spk} 音色已细化', flush=True)
            except Exception as e:
                print(f'  [spk] 取样失败（忽略）：{e}', flush=True)
'''

NEW = '''    def _cli_pump_spk_voices():
        """🔴 APP-039/040：给新 spk 取样 + 登记音色（只在新 spk 时做事）。"""
        # 🔴🔴🔴 §97 **修真实缺陷**：本函数**重绑**了 `_spk_pending_embed`
        #   ⇒ Python 静态判定它是**本函数的局部变量** ⇒ 第 4601 行
        #     `for seg, spk in list(_spk_pending_embed)` 读取时**未赋值**
        #   ⇒ `UnboundLocalError` ⇒ **CLI 启动即崩**（run4 实测死因）。
        #   ⇒ **必须显式 `nonlocal`**。
        # 🔴 §99：`_spk_voice_sent` 也要 `nonlocal`（下面有 `.add()`/`.discard()`
        #   ⇒ 只读不写不触发 UnboundLocalError，但 `.add()` 是**方法调用**
        #   ⇒ 不算绑定 ⇒ 安全；这里仍显式声明以免歧义）。
        nonlocal _spk_pending_embed, _spk_voice_sent
        if tts is None or not getattr(tts, 'active', False):
            return
        # 🔴🔴🔴 §99（断链 C）：**先查 worker 回执**。
        #   ⇒ `register_spk_voice()` 返回 True 只代表「命令写进管道了」，
        #     **不代表 worker 真的算出了 x-vector**。
        for _sent in list(_spk_voice_sent):
            _s, _refined = _sent
            try:
                _st = tts.spk_voice_status(_s)
            except Exception:
                _st = None
            if _st is None:
                continue          # worker 还没回 ⇒ 继续等（不阻塞）
            if _st.get('ok'):
                _spk_voices.mark_embedded(_s, refined=_refined)
                _spk_voice_sent.discard(_sent)
                if _refined:
                    _spk_pending_embed = [
                        (x, k) for (x, k) in _spk_pending_embed if k != _s]
                    print(f'  [spk] {_s} 音色已细化', flush=True)
                else:
                    # 🔴🔴🔴 §99（断链 F）：**不要**把 spk 从 pending 移除！
                    #   ⇒ 否则「攒够 REFINE_S 再用自己的段重算一次」
                    #     （APP-040②）**永远不会发生**。
                    #   ⇒ 保留在 pending 里，继续观察它有没有攒够 3 s。
                    print(f'  [spk] {_s} 已登记音色', flush=True)
            else:
                # 🔴 worker 明确失败 ⇒ 回落预设 A（**不用别人冒充**）
                _spk_voices.mark_fallback(
                    _s, 'worker_failed:%s' % (_st.get('message') or ''))
                _spk_voice_sent.discard(_sent)
                _spk_pending_embed = [
                    (x, k) for (x, k) in _spk_pending_embed if k != _s]
                print(f'  [spk] {_s} 音色登记失败（回落预设 A）：'
                      f'{_st.get("message") or "未知原因"}', flush=True)
        for seg, spk in list(_spk_pending_embed):
            try:
                # 🔴 §99：**已经在等回执** ⇒ 本轮不再重复发命令
                if any(s == spk for s, _r in _spk_voice_sent):
                    continue
                if not _spk_voices.has_voice(spk):
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
                    _spk_voice_sent.add((spk, False))
                elif _spk_voices.ready_to_embed(spk):
                    rngs = _spk_voices.clean_ranges_of(spk)
                    with _spk_pcm_lock:
                        buf = _spk_pcm_buf
                    pcm = _spk_bridge.pcm_for_ranges(
                        rngs, keep=buf, max_s=10.0, keep_t0=_spk_pcm_t0[0])
                    if pcm is not None and \\
                            pcm.size >= int(speaker_voice.REFINE_S * SR):
                        if tts.register_spk_voice(spk, pcm):
                            # 🔴 §99（断链 C）：细化也等回执
                            _spk_voice_sent.add((spk, True))
            except Exception as e:
                print(f'  [spk] 取样失败（忽略）：{e}', flush=True)
'''

rep(OLD, NEW)

# ══════════════════════════════════════════════════════════════
# ③ GUI 侧同步修断链 F：初次登记确认后**不**移出 pending
# ══════════════════════════════════════════════════════════════
rep(
    '''            if _st.get('ok'):
                self._spk_voices.mark_embedded(_s, refined=_refined)
                self._spk_voice_sent.discard(_sent)
                self._spk_pending_embed = [
                    (s, k) for (s, k) in self._spk_pending_embed
                    if k != _s]
                if _refined:
                    self._ui_log('[spk] %s 音色已细化' % _s)
                else:
                    self._ui_log('[spk] %s 已登记音色（≥%.1f s 干净语音）'
                                 % (_s, speaker_voice.MIN_S))''',
    '''            if _st.get('ok'):
                self._spk_voices.mark_embedded(_s, refined=_refined)
                self._spk_voice_sent.discard(_sent)
                if _refined:
                    # 🔴 §99（断链 F）：细化完成 ⇒ 这条路走完了 ⇒ 移出 pending
                    self._spk_pending_embed = [
                        (s, k) for (s, k) in self._spk_pending_embed
                        if k != _s]
                    self._ui_log('[spk] %s 音色已细化' % _s)
                else:
                    # 🔴🔴🔴 §99（断链 F）：**不要**把 spk 从 pending 移除！
                    #   ⇒ 否则「攒够 REFINE_S 再用自己的段重算一次」
                    #     （APP-040②）**永远不会发生**。
                    #   ⇒ 保留在 pending 里，继续观察它有没有攒够 3 s。
                    self._ui_log('[spk] %s 已登记音色（≥%.1f s 干净语音）'
                                 % (_s, speaker_voice.MIN_S))''')

# ── 写盘 + 编译校验 ───────────────────────────────────────────
try:
    compile(raw, TARGET, 'exec')
except Exception as e:
    raise SystemExit('❌ COMPILE FAIL ⇒ 不写盘：%s' % e)
with open(TARGET, 'wb') as f:
    f.write(raw)
print('after : %d bytes  →  COMPILE OK' % len(raw))
