#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130 定点补丁：CUDA 路线「回落预设」**必须换回参考音频**（否则串音）。

🔴 **只改开发版 `live_caption/tts_worker.py`**（客户包一个字节都不动）。
🔴 **定点替换**：唯一命中断言 ＋ `ast.parse` ＋ 写后逐字节复核 ＋ 行尾保持 CRLF。
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'live_caption', 'tts_worker.py')

# ── 补丁 1：新增共用出口 `_fallback_to_preset_ref_cuda` ──────────────────
OLD_HELPER_ANCHOR = """    def _has_ref_audio(self) -> bool:
"""

NEW_HELPER = '''    def _fallback_to_preset_ref_cuda(self, why: str = '') -> None:
        """🔴🔴🔴 §130：**CUDA 路线的「回落预设 A」统一出口**。

        🔴 **为什么必须有这个共用出口**（§130 实测出的真缺陷）：
          CUDA 路线（`USES_REF_AUDIO`）**没有 x-vector** ⇒ `speaker_embed` 恒为 None
          ⇒ 真正决定「播谁的音色」的是**边车里的参考音频**。
          ⇒ **只改 `speaker_embed`/`speaker_name` 是不够的**：边车里**仍然是上一个
          说话人的克隆参考音频** ⇒ 实播**串音**（听到的是上一个人的声音），
          且逐句遥测写 `voice_kind='preset'` **与实际不符** ⇒ **矛盾字段**。

        🔴 **改前的两条「回落预设」出口行为不一致**：
          - `_fallback_to_preset()` 的 CUDA 分支 ⇒ **有** `eng.set_ref_audio(ref)`
          - `_apply_spk_voice()` 的 `row is None` 分支 ⇒ **没有**（本轮修的就是它）
          ⇒ 现在**两条都收敛到这里** ⇒ 以后再漏就会很明显。

        ⚠️ **不改变任何既有语义**：
          - 只在 CUDA 路线（`USES_REF_AUDIO`）下生效
          - **不清空 `speaker_name`**（清了就报「没有可用的音色」⇒ APP-061① 回归）
          - BabelVox 路线**完全不受影响**（`_apply_spk_voice` 的 else 分支原样保留）
        """
        eng = self.engine
        if eng is None or not getattr(eng, 'USES_REF_AUDIO', False):
            return
        # 🔴 CUDA 路线：音色名保持 'A'（**不能**清空 ⇒ 见 APP-061①）
        self.speaker_embed = None
        self.speaker_name = self._preset_name or 'A'
        ref = self._preset_ref_path
        if not ref:
            log('[tts_worker] 🔴 回落预设 A：CUDA 边车没有预设参考音频')
            return
        try:
            eng.set_ref_audio(ref)
            log('[tts_worker] 🔴 ⇒ 已回落预设 A（已换回参考音频）'
                + (f'（原因：{why}）' if why else ''))
        except Exception as e:
            log('[tts_worker] 🔴 回落预设 A 时换参考音频失败：%s' % e)

    def _has_ref_audio(self) -> bool:
'''

# ── 补丁 2：`_apply_spk_voice` 的 `row is None` 分支 ⇒ 也要换 ref ────────
OLD_ROW_NONE = """        if row is None:
            # 🔴 没有这个 spk 的音色 ⇒ 预设 A（**不冒充**）
            self._last_voice_spk = None
            self._last_voice_kind = 'preset'
            self.speaker_embed = self._preset_embed
            self.speaker_name = self._preset_name
            return 'preset'
"""

NEW_ROW_NONE = """        if row is None:
            # 🔴 没有这个 spk 的音色 ⇒ 预设 A（**不冒充**）
            self._last_voice_spk = None
            self._last_voice_kind = 'preset'
            # 🔴🔴🔴 §130：CUDA 路线**必须换回预设 A 的参考音频**
            #   ⇒ 否则边车里仍是上一个说话人的克隆音频 ⇒ **串音**
            #   ⇒ 且遥测写 `voice_kind='preset'` 与实际不符 ⇒ 矛盾字段。
            #   （BabelVox 路线**不受影响** ⇒ 下面照旧换回预设向量。）
            self._fallback_to_preset_ref_cuda('spk 未登记音色')
            self.speaker_embed = self._preset_embed
            self.speaker_name = self._preset_name
            if getattr(self.engine, 'USES_REF_AUDIO', False):
                # 🔴 CUDA 路线：`speaker_embed` 恒为 None、`speaker_name` 保持 'A'
                self.speaker_embed = None
                self.speaker_name = self._preset_name or 'A'
            return 'preset'
"""

# ── 补丁 3：`_apply_spk_voice` 的「CUDA 下该 spk 没有 ref」分支 ──────────
OLD_NO_REF = """        if eng is not None and getattr(eng, 'USES_REF_AUDIO', False):
            if not ref:
                self._last_voice_spk = None
                self._last_voice_kind = 'preset'
                return 'preset'
"""

NEW_NO_REF = """        if eng is not None and getattr(eng, 'USES_REF_AUDIO', False):
            if not ref:
                self._last_voice_spk = None
                self._last_voice_kind = 'preset'
                # 🔴🔴🔴 §130：同上 ⇒ 回落预设时**换回预设参考音频**
                self._fallback_to_preset_ref_cuda('该 spk 没有参考音频')
                return 'preset'
"""

# ── 补丁 4：`set_ref_audio` 抛异常 ⇒ 也回落预设 ⇒ 同样要换 ref ──────────
OLD_EXC = """            try:
                eng.set_ref_audio(ref)
            except Exception as e:
                log(f'[tts_worker] 🔴 切换到 {spk} 的参考音频失败：{e}')
                self._last_voice_spk = None
                self._last_voice_kind = 'preset'
                return 'preset'
"""

NEW_EXC = """            try:
                eng.set_ref_audio(ref)
            except Exception as e:
                log(f'[tts_worker] 🔴 切换到 {spk} 的参考音频失败：{e}')
                self._last_voice_spk = None
                self._last_voice_kind = 'preset'
                # 🔴🔴🔴 §130：切换失败 ⇒ 边车里可能还是**上一个**说话人的音频
                #   ⇒ 必须换回预设 A 的参考音频 ⇒ 否则**串音**
                self._fallback_to_preset_ref_cuda('切换参考音频失败')
                return 'preset'
"""

# ── 补丁 5：`_fallback_to_preset` 的 CUDA 分支 ⇒ 收敛到共用出口 ──────────
OLD_FALLBACK = """            self.speaker_embed = None
            self.speaker_name = self._preset_name or 'A'
            ref = self._preset_ref_path
            if ref:
                try:
                    eng.set_ref_audio(ref)
                except Exception as e:
                    log('[tts_worker] 🔴 回落预设 A 时换参考音频失败：%s' % e)
            else:
                log('[tts_worker] 🔴 回落预设 A：CUDA 边车没有预设参考音频')
"""

NEW_FALLBACK = """            # 🔴🔴🔴 §130：**收敛到共用出口**（与 `_apply_spk_voice` 同一处）
            #   ⇒ 两条「回落预设」出口行为**一致** ⇒ 以后再漏就会很明显。
            self._fallback_to_preset_ref_cuda(why)
"""

PATCHES = [
    ('新增共用出口 _fallback_to_preset_ref_cuda', OLD_HELPER_ANCHOR, NEW_HELPER),
    ('_apply_spk_voice: row is None 也要换 ref', OLD_ROW_NONE, NEW_ROW_NONE),
    ('_apply_spk_voice: CUDA 无 ref 也要换 ref', OLD_NO_REF, NEW_NO_REF),
    ('_apply_spk_voice: 切换失败也要换 ref', OLD_EXC, NEW_EXC),
    ('_fallback_to_preset: 收敛到共用出口', OLD_FALLBACK, NEW_FALLBACK),
]


def main():
    with open(TARGET, 'rb') as f:
        raw = f.read()
    before_sha = hashlib.sha256(raw).hexdigest()
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n')
    use_crlf = bool(crlf) and crlf == lf
    # 🔴 **行尾归一化**：补丁片段用 \n 写 ⇒ 先统一成 \n 再匹配，最后还原原文行尾
    text = raw.decode('utf-8')
    if use_crlf:
        text = text.replace('\r\n', '\n')

    added_lines = 0
    for name, old, new in PATCHES:
        n = text.count(old)
        if n != 1:
            print('[FAIL] %s ⇒ 命中 %d 次（须恰好 1 次）' % (name, n))
            return 2
        text = text.replace(old, new, 1)
        added_lines += new.count('\n') - old.count('\n')
        print('[OK] %s（净增 %d 行）' % (name, new.count('\n') - old.count('\n')))

    # 🔴 语法校验（改前）
    try:
        ast.parse(text)
    except SyntaxError as e:
        print('[FAIL] ast.parse 失败：%s' % e)
        return 3

    if use_crlf:
        text = text.replace('\n', '\r\n')
    out = text.encode('utf-8')
    with open(TARGET, 'wb') as f:
        f.write(out)
    with open(TARGET, 'rb') as f:
        check = f.read()
    # 🔴 写后逐字节复核
    assert check == out, '写后复核失败'
    # 🔴 行尾复核：**不能**出现裸 LF（CRLF 计数必须等于 LF 计数）
    #   ⇒ 补丁新增的行也必须是 CRLF
    assert check.count(b'\r\n') == check.count(b'\n'), \
        '行尾被破坏：CRLF=%d LF=%d（出现裸 LF）' % (check.count(b'\r\n'),
                                              check.count(b'\n'))
    if use_crlf:
        assert check.count(b'\r\n') == crlf + added_lines, \
            'CRLF 增量与新增行数不符：%d vs %d' % (check.count(b'\r\n') - crlf,
                                          added_lines)
    print('\n写入完成')
    print('  bytes  %d → %d（+%d）' % (len(raw), len(check), len(check) - len(raw)))
    print('  sha256 %s → %s' % (before_sha, hashlib.sha256(check).hexdigest()))
    print('  CRLF   %d → %d（新增 %d 行，全部 CRLF）'
          % (crlf, check.count(b'\r\n'), check.count(b'\r\n') - crlf))
    return 0


if __name__ == '__main__':
    sys.exit(main())
