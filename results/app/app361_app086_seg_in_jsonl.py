"""APP-086(2) 补丁 4：逐句 TTS 遥测 JSONL **补上 `seg`**（ASR 段号）。

🔴 为什么必须补：
  APP-086② 的验收要算「**用对了说话人音色的句子占比**」⇒ 必须能把
  「逐句遥测行（voice_spk / voice_kind）」与「**这一句属于谁**」对上。
  现状：worker 的队列元组**已经带 `seg`**（APP-067①(b) 加的），
  但 JSONL 行里**没有 `seg`** ⇒ 只能靠行序/文本去猜 ⇒ 对不上就是错算。
  ⇒ 现在把 `seg` 记进行里（**纯附加** ⇒ 不影响任何既有字段/行为）。

用法：python app361_app086_seg_in_jsonl.py [apply|verify]
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
    ("S1 init _job_seg",
     "        self._spk_bind = {}            # seg -> (spk, spk_conf)\r\n",
     "        self._spk_bind = {}            # seg -> (spk, spk_conf)\r\n"
     "        # 🔴🔴🔳 APP-086(2)：jid -> seg（**纯附加**）\r\n"
     "        #   \u21d2 \u9010\u53e5\u9065\u6d4b JSONL \u884c\u91cc\u6709 `seg` \u21d2 reviewer \u80fd\u628a\r\n"
     "        #     \u300c\u9010\u53e5\u7684\u97f3\u8272\u300d\u4e0e\u300c\u8fd9\u53e5\u5c5e\u4e8e\u8c01\u300d\u5bf9\u4e0a\r\n"
     "        #     \u21d2 \u53ef\u7b97\u300c\u7528\u5bf9\u4e86\u8bf4\u8bdd\u4eba\u97f3\u8272\u7684\u53e5\u5b50\u5360\u6bd4\u300d\u3002\r\n"
     "        self._job_seg = {}\r\n"),

    ("S2 record job seg at submit",
     "                self._synth_q.put((jid, text, spk, spk_conf, lang, t_recv,\r\n"
     "                                   speed, target_wall, seg))\r\n",
     "                try:\r\n"
     "                    self._job_seg[jid] = seg\r\n"
     "                except Exception:\r\n"
     "                    pass\r\n"
     "                self._synth_q.put((jid, text, spk, spk_conf, lang, t_recv,\r\n"
     "                                   speed, target_wall, seg))\r\n"),

    ("S3 write seg into jsonl row",
     "        row = dict(id=jid, text=text,\r\n",
     "        # \U0001F534\U0001F534\U0001F533 APP-086(2)\uff1a**\u9010\u53e5\u5e26 `seg`**\r\n"
     "        #   \u21d2 reviewer \u53ef\u628a\u300c\u8fd9\u53e5\u7528\u4e86\u8c01\u7684\u97f3\u8272\u300d\u4e0e\u300c\u8fd9\u53e5\u5c5e\u4e8e\u8c01\u300d\u5bf9\u4e0a\u3002\r\n"
     "        try:\r\n"
     "            _seg_of = self._job_seg.get(jid)\r\n"
     "        except Exception:\r\n"
     "            _seg_of = None\r\n"
     "        row = dict(id=jid, text=text, seg=_seg_of,\r\n"),
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
