"""APP-086(2) 补丁 3：给 worker 侧的「沿用上一句音色收窄」补上说明性注释。

纯注释改动（不改语义）⇒ 用「精确字符串替换 + 唯一命中断言」。
用法：python app359_app086_clone_policy_comment.py [apply|verify]
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')

OLD = (
    "            elif self._has_clone_voice() and not _bound:\r\n"
    "                # \U0001F534\U0001F534\U0001F534 APP-061\u2464c\uff1a"
    "**\u5df2\u6709\u514b\u9686\u97f3\u8272 \u21d2 \u6cbf\u7528\u4e0a\u4e00\u53e5"
    "\u7684\u514b\u9686\u97f3\u8272**\u3002\r\n")

NEW = (
    "            elif self._has_clone_voice() and not _bound:\r\n"
    "                # \U0001F534\U0001F534\U0001F534 APP-061\u2464c\uff1a"
    "**\u5df2\u6709\u514b\u9686\u97f3\u8272 \u21d2 \u6cbf\u7528\u4e0a\u4e00\u53e5"
    "\u7684\u514b\u9686\u97f3\u8272**\u3002\r\n"
    "                #   \u26a0\ufe0f\U0001F534\U0001F534\U0001F534 "
    "**APP-086\u00b72a\uff082026-11-09\uff09\u6536\u7a84**\uff1a"
    "**\u53ea\u5728\u300c\u975e\u6309\u53e5\u7ed1\u5b9a\u300d\u6a21\u5f0f**\r\n"
    "                #     \uff08`_bound` \u4e3a\u7a7a \u21d2 worker "
    "\u6ca1\u62ff\u5230\u4efb\u4f55\u6309\u53e5\u97f3\u8272\uff09"
    "\u624d\u6cbf\u7528\u3002\r\n"
    "                #   \u21d2 \u6309\u53e5\u7ed1\u5b9a\u6a21\u5f0f"
    "\uff08App GUI/CLI \u7684\u5e38\u6001\uff09\u4e0b `spk=None` "
    "\u21d2 **\u56de\u843d\u9884\u8bbe A**\r\n"
    "                #     \u21d2 **\u7edd\u4e0d\u6cbf\u7528\u4e0a\u4e00\u53e5"
    "\u7684\u514b\u9686\u97f3\u8272**\r\n"
    "                #     \uff08= \u300c\u7537\u58f0\u88ab\u914d\u6210\u5973\u58f0"
    "\u300d\u7684\u4e3b\u56e0\uff0cAPP-086\u00b72a \u660e\u6587\uff09"
    "\u3002\r\n"
    "                #   \u26a0\ufe0f \u4e0e\u672c\u51fd\u6570\u4e0a\u65b9 "
    "1696\u20131713 \u7684\u6ce8\u91ca\u53e3\u5f84**\u4e00\u81f4**\r\n"
    "                #     \uff08\u90a3\u91cc\u5199\u7684\u5c31\u662f\u300cspk "
    "\u4e3a None \u21d2 \u5fc5\u987b\u56de\u843d\u9884\u8bbe A\u300d"
    "\uff09\u3002\r\n")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    src = open(WRK, encoding='utf-8', newline='').read()
    rep = {'hits_old': src.count(OLD), 'hits_new': src.count(NEW)}
    if mode == 'verify':
        rep['ok'] = rep['hits_old'] == 1
        print(json.dumps(rep, ensure_ascii=False))
        return 0 if rep['ok'] else 1
    assert rep['hits_old'] == 1, rep
    src = src.replace(OLD, NEW)
    ast.parse(src)
    open(WRK, 'w', encoding='utf-8', newline='').write(src)
    rep['applied'] = True
    rep['sha256_after'] = hashlib.sha256(open(WRK, 'rb').read()).hexdigest()
    rep['bytes_after'] = len(src.encode('utf-8'))
    rep['crlf'] = src.count('\r\n') > src.count('\n') // 2
    print(json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
