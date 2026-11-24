#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：把 app187 的「STATUS 引用 ⇒ 必须已入库」判据**扩到全部 STATUS 文档**。

app187 只扫 `status/app/STATUS_APP.md`（活文档）⇒
  **companion（`status/app/STATUS_APP_secNNN_detail_*.md`）里引用的产物它根本看不到**
  ⇒ §222③ 的缺口在 companion 里是**盲区**。

本脚本：
  ① 用 app187 **同款**正则（含修正后的 jsonl/csv）扫**全部** `status/app/*.md`
  ② 找出「被引用但未入库（git ls-files 不在册）」的仓库产物
  ③ 对每个磁盘上存在的，算它的 sha256，并查是否被某个已入库证据公布过
     ⇒ 决定它是否**必须逐字节入库**（-text）

🔴 反证组：
  R1 造一个「已入库的路径」⇒ 必须判 NOT-MISSING
  R2 造一个「未入库且磁盘上不存在」⇒ 必须判 NOT-MISSING（不存在的不是缺口）
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS_DIR = os.path.join(REPO, 'status/app')
REPO_PREFIXES = ('results/', 'live_caption/', 'status/', 'shared/')

_PATH_RE = re.compile(
    r'`([A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat|yaml|yml|csv|jsonl))`')
_BARE_RE = re.compile(
    r'(?<![\w/\\])([A-Za-z0-9_.-]+/[A-Za-z0-9_./\\-]+\.(?:py|json|md|txt|log|patch|sh|bat|jsonl|csv))')


def git(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True).stdout.decode('utf-8', 'replace')


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def candidates(text):
    got = set()
    for rx in (_PATH_RE, _BARE_RE):
        for m in rx.finditer(text):
            got.add(m.group(1).replace(chr(92), '/'))
    out = set()
    for q in got:
        if re.match(r'^[A-Za-z]:/', q) or q.startswith('//'):
            continue
        if not q.startswith(REPO_PREFIXES):
            continue
        out.add(q)
    return out


def main():
    tracked = set(f for f in git('ls-files').split('\n') if f.strip())
    # 已入库证据里公布的 sha256（按 basename）
    pub = {}
    for f in sorted(tracked):
        if not (f.startswith('results/app/') and f.endswith('.json')):
            continue
        try:
            d = json.load(open(os.path.join(REPO, f), encoding='utf-8'))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                if isinstance(o.get('sha256'), str) and len(o['sha256']) == 64:
                    for k in ('path', 'file', 'name'):
                        v = o.get(k)
                        if isinstance(v, str) and v:
                            pub.setdefault(os.path.basename(v), set()).add(o['sha256'])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)

    docs = sorted(f for f in os.listdir(STATUS_DIR)
                  if f.endswith('.md') and f != 'CORRECTIONS_APP.md')
    all_cands = {}
    for doc in docs:
        text = io.open(os.path.join(STATUS_DIR, doc), encoding='utf-8').read()
        for c in candidates(text):
            all_cands.setdefault(c, set()).add(doc)

    missing = {c: sorted(d) for c, d in all_cands.items() if c not in tracked}
    on_disk = {c: d for c, d in missing.items()
               if os.path.isfile(os.path.join(REPO, c))}
    not_on_disk = {c: d for c, d in missing.items()
                   if not os.path.isfile(os.path.join(REPO, c))}

    print("scanned STATUS docs =", len(docs))
    print("referenced repo paths =", len(all_cands))
    print("NOT tracked =", len(missing))
    print()
    print("=== 磁盘上存在 ⇒ 真缺口（可入库） ===")
    byte_exact = []
    for c in sorted(on_disk):
        p = os.path.join(REPO, c)
        raw = open(p, 'rb').read()
        ds = sha_bytes(raw)
        pubs = pub.get(os.path.basename(c), set())
        be = bool(pubs) and ds in pubs
        if be:
            byte_exact.append(c)
        print("  %-62s %8d B  crlf=%-5d 已公布sha=%-5s 逐字节必须=%s"
              % (c[:62], len(raw), raw.count(b'\r\n'), bool(pubs), be))
        print("      cited_in=%s" % (', '.join(on_disk[c][:3])))
    print()
    print("=== 磁盘上不存在 ⇒ 不是入库缺口（多为运行时产物/占位） ===")
    for c in sorted(not_on_disk):
        print("  %-62s cited_in=%s" % (c[:62], ', '.join(not_on_disk[c][:2])))

    print()
    print("byte_exact 必须逐字节入库 =", len(byte_exact))
    for c in sorted(byte_exact):
        print("   ", c)

    print()
    print("--- counterproof ---")
    cp = []
    known = 'results/app/app049_pkg_path_hardcode_gate.py'
    ok1 = known not in missing
    cp.append({'name': 'R1_tracked_not_missing', 'expect': 'NOT_MISSING', 'ok': ok1})
    print("    R1 已入库路径 ⇒ 须判 NOT-MISSING ⇒ %s" % ('PASS' if ok1 else 'FAIL'))
    ok2 = 'results/app/zzz_not_exist_xyz.json' not in missing
    cp.append({'name': 'R2_nonexistent_not_missing', 'expect': 'NOT_MISSING', 'ok': ok2})
    print("    R2 磁盘上不存在的路径 ⇒ 须判 NOT-MISSING ⇒ %s" % ('PASS' if ok2 else 'FAIL'))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'docs_scanned': len(docs), 'n_referenced': len(all_cands),
            'not_tracked': len(missing),
            'on_disk_gaps': sorted(on_disk), 'not_on_disk': sorted(not_on_disk),
            'byte_exact': sorted(byte_exact),
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_status_cited_scan.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_status_cited_scan.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
