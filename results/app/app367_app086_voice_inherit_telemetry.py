"""APP-086(2) 补丁 5：逐句遥测补两个字段 ⇒ **让「是否继承了上一句音色」机器可判定**。

🔴 为什么必须补（读码结论）：
  现状 jsonl 里 `voice_spk` = **实际使用的克隆音色**；标签晚到而回落预设 A 时
  它写 `null` ⇒ **与「本来就没标签」在遥测里不可区分** ⇒ reviewer **无法机器判定**
  「这句是不是继承了上一句的音色」⇒ 也就无法验证 APP-086②a 的修复真的生效。

⇒ 补两个字段（**纯附加**，不改任何行为）：
  * `spk_label`     = 这一句**解析出来的说话人**（`_last_spk`，即命令里/绑定的 spk）
  * `voice_inherited` = 本句**是否沿用了上一句的克隆音色**（`True/False`）
    ⇒ `True` ⇒ 命中了「沿用上一句音色」这条路（= APP-086②a 要消灭的行为）

用法：python app367_app086_voice_inherit_telemetry.py [apply|verify]
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')

EDITS = [
    ("T1 init flag",
     "        self._last_voice_spk = None\r\n        self._last_voice_kind = None\r\n",
     "        self._last_voice_spk = None\r\n        self._last_voice_kind = None\r\n"
     "        # \U0001F534\U0001F534\U0001F533 APP-086(2)：**本句是否沿用了上一句的克隆音色**\r\n"
     "        #   \u21d2 \u9010\u53e5\u9065\u6d4b\u91cc\u53ef\u673a\u68c0\u5224\uff08\u4e0d\u53ea\u80fd\u9760\u65e5\u5fd7\u6587\u5b57\uff09\u3002\r\n"
     "        self._voice_inherited = False\r\n"),

    ("T2 reset per sentence",
     "        self._last_spk, self._last_spk_conf = spk, spk_conf\r\n",
     "        self._last_spk, self._last_spk_conf = spk, spk_conf\r\n"
     "        # \U0001F534\U0001F534\U0001F533 APP-086(2)\uff1a\u6bcf\u53e5\u91cd\u7f6e\u300c\u662f\u5426\u6cbf\u7528\u4e0a\u4e00\u53e5\u97f3\u8272\u300d\r\n"
     "        #   \u21d2 \u53ea\u6709\u771f\u6b63\u8d70\u4e86\u300c\u6cbf\u7528\u300d\u90a3\u6761\u8def\u624d\u4f1a\u7f6e True\u3002\r\n"
     "        self._voice_inherited = False\r\n"),

    ("T3 set on keep-last-clone",
     "        self._last_voice_spk = None\r\n        self._last_voice_kind = 'clone'\r\n"
     "        log('[tts_worker] spk_pending\u21d2keep_last'\r\n",
     "        self._last_voice_spk = None\r\n        self._last_voice_kind = 'clone'\r\n"
     "        # \U0001F534\U0001F534\U0001F533 APP-086(2)\uff1a**\u6b64\u53e5\u6cbf\u7528\u4e86\u4e0a\u4e00\u53e5\u7684\u514b\u9686\u97f3\u8272**\r\n"
     "        #   \u21d2 \u9010\u53e5\u9065\u6d4b\u5199 `voice_inherited=true`\r\n"
     "        #   \u21d2 reviewer \u53ef\u4ee5\u673a\u68c0\u5224\u300c\u662f\u5426\u4ecd\u5728\u6cbf\u7528\u4e0a\u4e00\u53e5\u97f3\u8272\u300d\u3002\r\n"
     "        self._voice_inherited = True\r\n"
     "        log('[tts_worker] spk_pending\u21d2keep_last'\r\n"),

    ("T4 write row fields",
     "        row = dict(id=jid, text=text, seg=_seg_of,\r\n",
     "        row = dict(id=jid, text=text, seg=_seg_of,\r\n"
     "                   # \U0001F534\U0001F534\U0001F533 APP-086(2)\uff1a`spk_label` = \u8fd9\u4e00\u53e5**\u89e3\u6790\u51fa\u6765\u7684\u8bf4\u8bdd\u4eba**\r\n"
     "                   #   \u21d2 \u4e0e `voice_spk`\uff08**\u5b9e\u9645\u4f7f\u7528\u7684\u514b\u9686\u97f3\u8272**\uff09\u4e0d\u540c\uff1a\r\n"
     "                   #   \u6709\u6807\u7b7e\u4f46\u56de\u843d\u9884\u8bbe A \u65f6 `voice_spk=null` \u4e14 `spk_label=S2`\r\n"
     "                   #   \u21d2 \u4e24\u8005\u4e00\u8d77\u624d\u80fd\u533a\u5206\u300c\u65e0\u6807\u7b7e\u300d\u4e0e\u300c\u56de\u843d\u300d\u3002\r\n"
     "                   spk_label=(str(self._last_spk)\r\n"
     "                             if self._last_spk else None),\r\n"
     "                   # \U0001F534\U0001F534\U0001F533 APP-086(2)\uff1a**\u672c\u53e5\u662f\u5426\u6cbf\u7528\u4e86\u4e0a\u4e00\u53e5\u7684\u514b\u9686\u97f3\u8272**\r\n"
     "                   voice_inherited=bool(self._voice_inherited),\r\n"),
]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    src = open(WRK, encoding='utf-8', newline='').read()
    rep = {'mode': mode, 'edits': []}
    ok = True
    for label, old, new in EDITS:
        n = src.count(old)
        rep['edits'].append({'label': label, 'hits': n})
        if n != 1:
            ok = False
    rep['all_unique'] = ok
    if mode == 'verify':
        print(json.dumps(rep, ensure_ascii=False))
        return 0 if ok else 1
    assert ok, rep
    for label, old, new in EDITS:
        assert src.count(old) == 1, label
        src = src.replace(old, new)
    ast.parse(src)
    open(WRK, 'w', encoding='utf-8', newline='').write(src)
    rep['applied'] = [e[0] for e in EDITS]
    rep['sha256_after'] = hashlib.sha256(open(WRK, 'rb').read()).hexdigest()
    rep['bytes_after'] = len(src.encode('utf-8'))
    rep['crlf'] = src.count('\r\n') > src.count('\n') // 2
    print(json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
