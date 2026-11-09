"""APP-086(2) 补丁 2：把「最近说话人」改走**既有 `spk_update` 通道**，并撤回
app357 里会**挡住官方晚到标签**的提交期改法。

🔴🔴🔳 **为什么要改**（实测读码结论，非推测）：
  `tts_worker.py` 的晚到标签通道是
      `if not spk and seg is not None:  spk = self._spk_bind.get(seg)`
  ⇒ **只有命令里 `spk` 为空时**，旁路后来的**官方标签**才生效。
  ⇒ app357 把「最近说话人」直接塞进提交命令的 `spk` ⇒ **官方标签被挡住**
  ⇒ 那一句可能用**错的**说话人 ⇒ **比回落预设 A 更糟**。

⇒ 改法（复用**已存在且已被 APP-029/067 验证过**的通道，零新协议）：
  ① 官方标签：仍走 `_spk_push_update`（不变）；
  ② 最近说话人：策略层算出后 ⇒ `tts.spk_update_seg(seg, spk, conf)`
     ⇒ 同样进 `_spk_bind` ⇒ **后写覆盖先写** ⇒ 官方标签后到时**自动胜出**；
  ③ 提交命令的 `spk` **保持原样**（`voice_for_sentence(...) or None`）
     ⇒ 无标签句仍是 `None` ⇒ 官方晚到标签照常生效；
  ④ worker 侧结构性兜底（app357 W1，已落地）：按句绑定模式下 `spk=None`
     ⇒ **回落预设 A** ⇒ **绝不沿用上一句的克隆音色**。

用法：python app358_app086_clone_wiring_fix.py [apply|verify]
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')
CLN = os.path.join(ROOT, 'live_caption', 'clone_voice.py')

EDITS = [
    # ── R1：撤回 GUI 提交期改法 ────────────────────────────────────
    ("R1 revert GUI submit",
     "                                        # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                                        #   ⇒ 无标签 ⇒ 最近**已登记**说话人（cos ≥ 0.25）\r\n"
     "                                        #   ⇒ 有标签但还没音色 ⇒ 预设 A（绝不用别人的）\r\n"
     "                                        spk=_resolve_clone_spk(\r\n"
     "                                            self._clone_pol,\r\n"
     "                                            self._spk_voices, ev['seg']),\r\n",
     "                                        # 🔴🔴🔳 APP-086(2)a：**提交时 `spk` 仍留空**\r\n"
     "                                        #   ⇒ worker 的晚到标签通道（`_spk_bind`）\r\n"
     "                                        #     才有生效的机会（`if not spk`）。\r\n"
     "                                        #   ⇒ 「最近说话人」改由策略层**补发**\r\n"
     "                                        #     （`_clone_nearest` → `spk_update`）。\r\n"
     "                                        spk=(self._spk_voices.voice_for_sentence(\r\n"
     "                                            ev['seg']) or None),\r\n"),

    # ── R2：撤回 CLI 提交期改法（asr 源）───────────────────────────
    ("R2 revert CLI submit asr",
     "                       # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                       spk=_resolve_clone_spk(\r\n"
     "                           _clone_pol, _spk_voices, len(finals) - 1),\r\n",
     "                       # 🔴🔴🔳 APP-086(2)a：提交时 `spk` 仍留空\r\n"
     "                       #   ⇒ 晚到的官方标签才有生效机会。\r\n"
     "                       spk=(_spk_voices.voice_for_sentence(\r\n"
     "                           len(finals) - 1) or None),\r\n"),

    # ── R3：撤回 CLI 提交期改法（mt 源）────────────────────────────
    ("R3 revert CLI submit mt",
     "                                   # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                                   spk=_resolve_clone_spk(\r\n"
     "                                       _clone_pol, _spk_voices, ev['seg']),\r\n",
     "                                   # 🔴🔴🔳 APP-086(2)a：提交时 `spk` 仍留空\r\n"
     "                                   #   ⇒ 晚到的官方标签才有生效机会。\r\n"
     "                                   spk=(_spk_voices.voice_for_sentence(\r\n"
     "                                       ev['seg']) or None),\r\n"),

    # ── R4：撤回模块级解析函数 ────────────────────────────────────
    ("R4 remove resolver",
     "# 🔴🔴🔳 APP-086(2)a：**合成前解析这一句该用谁的音色**（GUI/CLI 共用一份口径）。\r\n"
     "#\r\n"
     "# ① 有**确认标签**且该 spk 已登记音色 ⇒ 用它（APP-039 按句绑定）。\r\n"
     "# ② 有**确认标签**但该 spk 还没音色 ⇒ `None` ⇒ 回落**预设 A**\r\n"
     "#    ⇒ **绝不用别人的音色**（APP-086②a 明文）。\r\n"
     "# ③ **没有标签** ⇒ 最近**已登记**说话人（cos ≥ 0.25）\r\n"
     "#    ⇒ 找不到就 `None` ⇒ 回落**预设 A**。\r\n"
     "#    🔴 **不再沿用上一句的音色**（= 「男声被配成女声」的主因）。\r\n"
     "def _resolve_clone_spk(pol, table, seg):\r\n"
     "    try:\r\n"
     "        spk = table.voice_for_sentence(seg)\r\n"
     "        if spk:\r\n"
     "            return spk\r\n"
     "        if table.spk_of(seg):\r\n"
     "            return None\r\n"
     "        return pol.nearest_registered(seg)\r\n"
     "    except Exception:\r\n"
     "        return None\r\n"
     "\r\n"
     "\r\n"
     "def main():\r\n",
     "def main():\r\n"),

    # ── G1：GUI 策略层接上回调 ────────────────────────────────────
    ("G1 GUI policy callback",
     "        self._clone_pol = clone_voice.CloneVoices(\r\n"
     "            on_log=lambda m: self._ui_log(m),\r\n"
     "            bridge=self._spk_bridge, table=self._spk_voices,\r\n"
     "            pcm_getter=lambda: (self._spk_pcm_buf, self._spk_pcm_t0),\r\n"
     "            span_getter=lambda seg: self._seg_span.get(seg))\r\n",
     "        self._clone_pol = clone_voice.CloneVoices(\r\n"
     "            on_log=lambda m: self._ui_log(m),\r\n"
     "            bridge=self._spk_bridge, table=self._spk_voices,\r\n"
     "            pcm_getter=lambda: (self._spk_pcm_buf, self._spk_pcm_t0),\r\n"
     "            span_getter=lambda seg: self._seg_span.get(seg),\r\n"
     "            on_nearest=self._clone_nearest)\r\n"
     "\r\n"
     "    def _clone_nearest(self, seg, spk, sim):\r\n"
     "        \"\"\"🔴🔴🔳 APP-086(2)a：**无标签句 ⇒ 最近已登记说话人**（cos ≥ 0.25）。\r\n"
     "\r\n"
     "        🔴 **走既有的 `spk_update` 通道**（不是提交命令的 `spk`）\r\n"
     "        ⇒ worker 侧 `_spk_bind` 后写覆盖先写\r\n"
     "        ⇒ **官方标签晚到时自动胜出**（不会用错的人）。\r\n"
     "        🔴 **已有官方标签 ⇒ 一律不推**（官方优先）。\r\n"
     "        \"\"\"\r\n"
     "        try:\r\n"
     "            if self._spk_voices.spk_of(seg):\r\n"
     "                return\r\n"
     "            if self.tts is None or not getattr(self.tts, 'active', False):\r\n"
     "                return\r\n"
     "            if self.tts.spk_update_seg(seg, spk, None):\r\n"
     "                self._ui_log('[spk] 第 %d 段无标签 ⇒ 取最近说话人 %s'\r\n"
     "                             '（cos %.3f）' % (seg, spk, sim))\r\n"
     "        except Exception as e:\r\n"
     "            self._ui_log('[spk] 最近说话人补发失败（忽略）：%s' % e)\r\n"),

    # ── G2：GUI 周期泵里重算最近说话人 ────────────────────────────
    ("G2 GUI pump",
     "        if not getattr(self, '_clone_enabled', False):\r\n"
     "            return\r\n",
     "        if not getattr(self, '_clone_enabled', False):\r\n"
     "            return\r\n"
     "        # 🔴🔴🔳 APP-086(2)a：质心长出来之后**零成本重算**最近说话人\r\n"
     "        #   （嵌入已缓存 ⇒ 这里只做余弦比较）\r\n"
     "        #   ⇒ 该说话人已登记音色时 ⇒ 通过 `spk_update` 补发给 worker。\r\n"
     "        try:\r\n"
     "            self._clone_pol.pump()\r\n"
     "        except Exception:\r\n"
     "            pass\r\n"),

    # ── C1：CLI 策略层接上回调 ────────────────────────────────────
    ("C1 CLI policy callback",
     "    _clone_pol = clone_voice.CloneVoices(\r\n"
     "        on_log=lambda m: print(f'  [spk] {m}', flush=True),\r\n"
     "        bridge=_spk_bridge, table=_spk_voices,\r\n"
     "        pcm_getter=lambda: (_spk_pcm_buf, _spk_pcm_t0[0]),\r\n"
     "        span_getter=lambda seg: _spk_span.get(seg))\r\n",
     "    _clone_pol = clone_voice.CloneVoices(\r\n"
     "        on_log=lambda m: print(f'  [spk] {m}', flush=True),\r\n"
     "        bridge=_spk_bridge, table=_spk_voices,\r\n"
     "        pcm_getter=lambda: (_spk_pcm_buf, _spk_pcm_t0[0]),\r\n"
     "        span_getter=lambda seg: _spk_span.get(seg),\r\n"
     "        on_nearest=_cli_clone_nearest)\r\n"
     "\r\n"
     "    def _cli_clone_nearest(seg, spk, sim):\r\n"
     "        \"\"\"🔴🔴🔳 APP-086(2)a：**无标签句 ⇒ 最近已登记说话人**（CLI 侧）。\r\n"
     "\r\n"
     "        🔴 与 GUI 侧**同一口径**：走既有 `spk_update` 通道\r\n"
     "        ⇒ 官方标签晚到时自动胜出（不会用错的人）。\r\n"
     "        \"\"\"\r\n"
     "        try:\r\n"
     "            if _spk_voices.spk_of(seg):\r\n"
     "                return\r\n"
     "            if tts is None or not getattr(tts, 'active', False):\r\n"
     "                return\r\n"
     "            if tts.spk_update_seg(seg, spk, None):\r\n"
     "                print(f'  [spk] 第 {seg} 段无标签 ⇒ 取最近说话人 {spk}'\r\n"
     "                      f'（cos {sim:.3f}）', flush=True)\r\n"
     "        except Exception as e:\r\n"
     "            print(f'  [spk] 最近说话人补发失败（忽略）：{e}', flush=True)\r\n"),

    # ── C2：CLI 周期泵里重算最近说话人 ────────────────────────────
    ("C2 CLI pump",
     "    def _cli_pump_spk_voices():\r\n"
     "        \"\"\"🔴 APP-039/040：给新 spk 取样 + 登记音色（只在新 spk 时做事）。\"\"\"\r\n",
     "    def _cli_pump_spk_voices():\r\n"
     "        \"\"\"🔴 APP-039/040：给新 spk 取样 + 登记音色（只在新 spk 时做事）。\"\"\"\r\n"
     "        # 🔴🔴🔳 APP-086(2)a：质心长出来之后**零成本重算**最近说话人\r\n"
     "        #   （嵌入已缓存 ⇒ 这里只做余弦比较）\r\n"
     "        try:\r\n"
     "            _clone_pol.pump()\r\n"
     "        except Exception:\r\n"
     "            pass\r\n"),
]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    src = open(APP, encoding='utf-8', newline='').read()
    report = {'mode': mode, 'edits': []}
    ok = True
    for label, old, new in EDITS:
        n = src.count(old)
        report['edits'].append({'label': label, 'hits': n})
        if n != 1:
            ok = False
    if mode == 'verify':
        report['all_unique'] = ok
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if ok else 1

    assert ok, "anchors not unique: %s" % report
    b = len(src.encode('utf-8'))
    for label, old, new in EDITS:
        assert src.count(old) == 1, label
        src = src.replace(old, new)
    ast.parse(src)
    open(APP, 'w', encoding='utf-8', newline='').write(src)
    report['applied'] = [e[0] for e in EDITS]
    report['bytes_before'] = b
    report['bytes_after'] = len(src.encode('utf-8'))
    report['sha256_after'] = hashlib.sha256(
        open(APP, 'rb').read()).hexdigest()
    report['crlf'] = src.count('\r\n') > src.count('\n') // 2
    ast.parse(open(CLN, encoding='utf-8').read())
    report['clone_voice_sha256'] = hashlib.sha256(
        open(CLN, 'rb').read()).hexdigest()
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
