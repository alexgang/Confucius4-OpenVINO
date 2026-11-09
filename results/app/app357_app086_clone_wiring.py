"""APP-086(2)：把克隆策略层（a–f）接进 App 主循环（GUI + CLI）。

🔴 口径（与 §159 的「接线口径裁定」对应）：
  * **复用 App 既有的那一份** `SpeakerBridge` / `SpeakerVoiceTable`
    ⇒ 不新建旁路 ⇒ **不可能双旁路**（上一版 `clone_voice.CloneVoices` 自带旁路
    ⇒ 与 App 自己的 `_spk_voices` 并存 ⇒ 双跑 wespeaker + pyannote ⇒ 抢设备）。
  * **策略层不做音色登记** ⇒ 登记仍走 `_pump_spk_voices()` / `_cli_pump_spk_voices()`
    ⇒ 不产生第二条登记路径 ⇒ 不会双登记。
  * APP-086②a 落地两处（缺一不可）：
      ① App 侧：合成前用「最近已登记说话人」（cos ≥ 0.25）替无标签句选音色；
      ② worker 侧：按句绑定模式下 `spk=None` ⇒ **回落预设 A**（绝不沿用上一句音色）。

用法：
    python app357_app086_clone_wiring.py apply     # 打补丁
    python app357_app086_clone_wiring.py verify    # 只校验（不写）
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
CLN = os.path.join(ROOT, 'live_caption', 'clone_voice.py')


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ── live_caption_app.py 的 9 处定点替换 ──────────────────────────────
APP_EDITS = [
    ("P1 import clone_voice",
     "import speaker_tracker\r\nimport speaker_voice\r\n",
     "import speaker_tracker\r\nimport speaker_voice\r\n"
     "# 🔴🔴🔴 APP-086(2)：克隆**策略层**（a–f）——**复用上面那份旁路与音色表**\r\n"
     "#   ⇒ 全程**只有一份** `SpeakerBridge` / `SpeakerVoiceTable`\r\n"
     "#   ⇒ **不可能双旁路**（§159 的接线口径隐患就此消除）。\r\n"
     "import clone_voice\r\n"),

    ("P3 GUI policy",
     "        self._seg_span = {}\r\n",
     "        self._seg_span = {}\r\n"
     "        # 🔴🔴🔳 APP-086(2)：克隆**策略层**（a–f）\r\n"
     "        #   ⇒ **注入既有的旁路与音色表** ⇒ 不新建旁路（不双跑 wespeaker）。\r\n"
     "        #   ⚠️ 本层**不做音色登记** ⇒ 登记仍走 `_pump_spk_voices()`\r\n"
     "        #   ⇒ 不会双登记、不会互相覆盖。\r\n"
     "        self._clone_pol = clone_voice.CloneVoices(\r\n"
     "            on_log=lambda m: self._ui_log(m),\r\n"
     "            bridge=self._spk_bridge, table=self._spk_voices,\r\n"
     "            pcm_getter=lambda: (self._spk_pcm_buf, self._spk_pcm_t0),\r\n"
     "            span_getter=lambda seg: self._seg_span.get(seg))\r\n"),

    ("P4 GUI on_final",
     "                self._seg_span[seg] = (_t0, _t1)\r\n",
     "                self._seg_span[seg] = (_t0, _t1)\r\n"
     "                # 🔴🔴🔳 APP-086(2) b：定稿即请求「最近质心」⇒ 临时标签\r\n"
     "                #   ⇒ ASR/音频线程**只入队**；嵌入在策略线程里算（f）。\r\n"
     "                try:\r\n"
     "                    self._clone_pol.on_segment(seg, _t0, _t1, text)\r\n"
     "                except Exception:\r\n"
     "                    pass\r\n"),

    ("P5 GUI submit",
     "                                        spk=(self._spk_voices.voice_for_sentence(\r\n"
     "                                            ev['seg']) or None),\r\n",
     "                                        # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                                        #   ⇒ 无标签 ⇒ 最近**已登记**说话人（cos ≥ 0.25）\r\n"
     "                                        #   ⇒ 有标签但还没音色 ⇒ 预设 A（绝不用别人的）\r\n"
     "                                        spk=_resolve_clone_spk(\r\n"
     "                                            self._clone_pol,\r\n"
     "                                            self._spk_voices, ev['seg']),\r\n"),

    ("P6 CLI policy",
     "    _spk_voices = speaker_voice.SpeakerVoiceTable(\r\n"
     "        on_event=lambda k, p: print(f'  [spk] {k} {p}', flush=True))\r\n",
     "    _spk_voices = speaker_voice.SpeakerVoiceTable(\r\n"
     "        on_event=lambda k, p: print(f'  [spk] {k} {p}', flush=True))\r\n"
     "    # 🔴🔴🔳 APP-086(2)：CLI 侧**每段的时间区间**（策略层算最近质心要用）\r\n"
     "    _spk_span = {}\r\n"
     "    # 🔴🔴🔳 APP-086(2)：克隆**策略层**（a–f）——与 GUI 侧**同一份实现**\r\n"
     "    #   ⇒ **注入既有的旁路与音色表** ⇒ 不新建旁路（不双跑 wespeaker）。\r\n"
     "    #   ⚠️ 本层**不做音色登记** ⇒ 登记仍走 `_cli_pump_spk_voices()`。\r\n"
     "    _clone_pol = clone_voice.CloneVoices(\r\n"
     "        on_log=lambda m: print(f'  [spk] {m}', flush=True),\r\n"
     "        bridge=_spk_bridge, table=_spk_voices,\r\n"
     "        pcm_getter=lambda: (_spk_pcm_buf, _spk_pcm_t0[0]),\r\n"
     "        span_getter=lambda seg: _spk_span.get(seg))\r\n"),

    ("P7 CLI on_final",
     "            _spk_seg_note(_seg, t0=_t0, t1=_t1)\r\n",
     "            _spk_seg_note(_seg, t0=_t0, t1=_t1)\r\n"
     "            _spk_span[_seg] = (_t0, _t1)\r\n"
     "            # 🔴🔴🔳 APP-086(2) b：定稿即请求「最近质心」⇒ 临时标签\r\n"
     "            #   ⇒ ASR/音频线程**只入队**；嵌入在策略线程里算（f）。\r\n"
     "            try:\r\n"
     "                _clone_pol.on_segment(_seg, _t0, _t1, t)\r\n"
     "            except Exception:\r\n"
     "                pass\r\n"),

    ("P8a CLI submit asr",
     "                       spk=(_spk_voices.voice_for_sentence(\r\n"
     "                           len(finals) - 1) or None),\r\n",
     "                       # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                       spk=_resolve_clone_spk(\r\n"
     "                           _clone_pol, _spk_voices, len(finals) - 1),\r\n"),

    ("P8b CLI submit mt",
     "                                   spk=(_spk_voices.voice_for_sentence(\r\n"
     "                                       ev['seg']) or None),\r\n",
     "                                   # 🔴🔴🔳 APP-086(2)a：**无标签句不许沿用上一句音色**\r\n"
     "                                   spk=_resolve_clone_spk(\r\n"
     "                                       _clone_pol, _spk_voices, ev['seg']),\r\n"),

    ("P9 resolver",
     "def main():\r\n",
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
     "def main():\r\n"),
]

# ── tts_worker.py 的 1 处定点替换（结构性兜底）──────────────────────
WRK_EDITS = [
    ("W1 keep-last-clone 收窄为「非按句绑定模式」",
     "            elif self._has_clone_voice():\r\n",
     "            elif self._has_clone_voice() and not _bound:\r\n"),
]


def apply_file(path, edits):
    src = open(path, encoding='utf-8', newline='').read()
    before = src
    applied = []
    for label, old, new in edits:
        n = src.count(old)
        assert n == 1, "%s: expected 1 hit, got %d" % (label, n)
        src = src.replace(old, new)
        applied.append(label)
    ast.parse(src)
    open(path, 'w', encoding='utf-8', newline='').write(src)
    return applied, len(before.encode('utf-8')), len(src.encode('utf-8'))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    out = {'mode': mode, 'files': {}}
    for path, edits in ((APP, APP_EDITS), (WRK, WRK_EDITS)):
        src = open(path, encoding='utf-8', newline='').read()
        info = {'path': path, 'bytes': len(src.encode('utf-8')),
                'sha256': _sha(src.encode('utf-8')),
                'crlf': src.count('\r\n') > src.count('\n') // 2,
                'anchors': []}
        for label, old, new in edits:
            info['anchors'].append({
                'label': label, 'hits': src.count(old),
                'already_applied': src.count(new) > 0 and src.count(old) == 0})
        out['files'][os.path.basename(path)] = info

    if mode == 'apply':
        applied = {}
        for path, edits in ((APP, APP_EDITS), (WRK, WRK_EDITS)):
            names, b, a = apply_file(path, edits)
            applied[os.path.basename(path)] = {
                'applied': names, 'bytes_before': b, 'bytes_after': a,
                'sha256_after': _sha(open(path, 'rb').read())}
        out['applied'] = applied
        for path, edits in ((APP, APP_EDITS), (WRK, WRK_EDITS)):
            src = open(path, encoding='utf-8', newline='').read()
            ast.parse(src)
            out['files'][os.path.basename(path)]['sha256_after'] = _sha(
                src.encode('utf-8'))
            out['files'][os.path.basename(path)]['bytes_after'] = len(
                src.encode('utf-8'))
            out['files'][os.path.basename(path)]['crlf_after'] = (
                src.count('\r\n') > src.count('\n') // 2)

    # clone_voice.py 也要能 parse
    ast.parse(open(CLN, encoding='utf-8').read())
    out['clone_voice_sha256'] = _sha(open(CLN, 'rb').read())
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
