#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：app187 闸门的**候选提取**扩展探针（只读）。

问题：app187 的 `_PATH_RE` / `_BARE_RE` **不认识 `.jsonl`** ⇒
  `results/app/app231_pack_lock_events.jsonl` 被**截断成** `...json`
  ⇒ 闸门去查一个**从来不存在**的文件名 ⇒ 报 MISSING（假 FAIL）。

本脚本对比：
  current  = 现用正则（不含 jsonl）
  extended = 加了 jsonl/csv 的正则
并列出两种口径下「被引用但未入库」的差集。

🔴 反证组：造一个 `.jsonl` 路径 ⇒ 现用正则**必须**截断（复现缺陷），
          扩展正则**必须**完整命中。
"""
import io
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BS = chr(92)
STATUS = os.path.join(REPO, 'status/app/STATUS_APP.md')
GATE = os.path.join(REPO, 'results/app/app187_repo_artifact_in_repo_gate.py')
REPO_PREFIXES = ('results/', 'live_caption/', 'status/', 'shared/')


def load_regexes():
    src = io.open(GATE, encoding='utf-8').read()
    ns = {'re': re}
    for name in ('_PATH_RE', '_BARE_RE'):
        m = re.search(name + r" = re\.compile\(.*?\)\n", src, re.S)
        exec(compile(m.group(0), '<x>', 'exec'), ns)
    return ns['_PATH_RE'], ns['_BARE_RE']


def candidates(text, P, B):
    got = set()
    for rx in (P, B):
        for m in rx.finditer(text):
            got.add(m.group(1).replace(BS, '/'))
    out = set()
    for q in got:
        if re.match(r'^[A-Za-z]:/', q) or q.startswith('//'):
            continue
        if not q.startswith(REPO_PREFIXES):
            continue
        out.add(q)
    return out


def main():
    text = io.open(STATUS, encoding='utf-8').read()
    P, B = load_regexes()
    P2 = re.compile(r'`([A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat|yaml|yml|csv|jsonl))`')
    B2 = re.compile(r'(?<![\w/\\])([A-Za-z0-9_.-]+/[A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat|jsonl|csv))')

    tracked = set(f for f in subprocess.run(
        ['git', '-C', REPO, 'ls-files'], capture_output=True, text=True).stdout.split('\n') if f.strip())

    cur = candidates(text, P, B)
    ext = candidates(text, P2, B2)
    cur_missing = sorted(c for c in cur if c not in tracked)
    ext_missing = sorted(c for c in ext if c not in tracked)
    print("current  regex: candidates=%d  missing=%d" % (len(cur), len(cur_missing)))
    for c in cur_missing:
        print("    MISSING ", c)
    print("extended regex: candidates=%d  missing=%d" % (len(ext), len(ext_missing)))
    for c in ext_missing:
        print("    MISSING ", c)

    print()
    print("=== 反证组 ===")
    cp = []
    sample = 'results/app/app231_pack_lock_events.jsonl'
    got_cur = [m.group(1) for rx in (P, B) for m in rx.finditer(sample)]
    got_ext = [m.group(1) for rx in (P2, B2) for m in rx.finditer(sample)]
    ok1 = got_cur == ['results/app/app231_pack_lock_events.json']
    cp.append({'name': 'R1_current_truncates_jsonl', 'expect': 'TRUNCATED',
               'got': got_cur, 'ok': ok1})
    print("    R1 现用正则对 .jsonl 必须截断 ⇒ 复现缺陷 ⇒ %s (%s)"
          % ('PASS' if ok1 else 'FAIL', got_cur))
    ok2 = got_ext == [sample]
    cp.append({'name': 'R2_extended_full_match', 'expect': 'FULL',
               'got': got_ext, 'ok': ok2})
    print("    R2 扩展正则必须完整命中 ⇒ %s (%s)" % ('PASS' if ok2 else 'FAIL', got_ext))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'current_candidates': len(cur), 'current_missing': cur_missing,
            'extended_candidates': len(ext), 'extended_missing': ext_missing,
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_app187_ext_probe.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_app187_ext_probe.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    import json
    sys.exit(main())
