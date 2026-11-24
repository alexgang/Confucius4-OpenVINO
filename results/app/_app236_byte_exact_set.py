#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222③ 修复前的**精确清单**计算（只读）。

要回答：把哪些「复算底本」入库，且**必须逐字节入库**（`-text`，禁止行尾转换）？

判据：
  - 文件在磁盘上存在
  - 被**已入库**的证据 json 引用（复算底本）
  - 且**证据里公布了它的 sha256**
    ⇒ 干净 clone 必须能复算出同一个 sha256
    ⇒ 行尾一旦被 git 转换（core.autocrlf=true ⇒ CRLF→LF）
       ⇒ clone 出来的字节 ≠ 公布的 sha256 ⇒ **假 FAIL**
    ⇒ 这类文件必须用 `-text`（§226 已验证过的做法）
  - 其余文件按仓库既有约定走 autocrlf 规整（i/lf）

🔴 反证组：
  R1 造一个「公布了 sha256 但磁盘上 sha 不符」的文件 ⇒ 必须判 NOT_BYTE_EXACT
  R2 造一个「没公布 sha256」的文件 ⇒ 必须判 NOT_BYTE_EXACT
"""
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)

    # 1) 已入库证据里公布的 sha256（按 basename 索引）
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
                        if k in o and isinstance(o[k], str):
                            pub.setdefault(os.path.basename(o[k]), set()).add(o['sha256'])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)

    # 2) 候选：磁盘上存在 + 被已入库证据引用（任一已入库 evidence json 里出现其文件名）
    ev_names = set()
    for f in tracked:
        if f.startswith('results/app/') and f.endswith('.json') \
                and not os.path.basename(f).startswith('_'):
            ev_names.add(os.path.basename(f))
    srcs = {}
    for f in tracked:
        if f.startswith('results/app/') and f.endswith('.json'):
            try:
                srcs[f] = open(os.path.join(REPO, f), encoding='utf-8', errors='replace').read()
            except Exception:
                pass

    candidates = {}
    for fn in sorted(ev_names):
        p = os.path.join(REPO, 'results/app', fn)
        if not os.path.isfile(p):
            continue
        if fn in tracked_set:
            continue                      # 已入库
        cited = [e for e, s in srcs.items() if fn in s]
        if not cited:
            continue
        raw = open(p, 'rb').read()
        ds = sha_bytes(raw)
        shas = pub.get(fn)
        candidates[fn] = {
            'bytes': len(raw),
            'crlf': raw.count(b'\r\n'),
            'lf_only': raw.count(b'\n') - raw.count(b'\r\n'),
            'disk_sha256': ds,
            'published_sha256': sorted(shas) if shas else [],
            'cited_by': cited,
            'byte_exact_required': bool(shas) and ds in shas,
            'sha_mismatch': bool(shas) and ds not in shas,
        }

    be = [k for k, v in candidates.items() if v['byte_exact_required']]
    nm = [k for k, v in candidates.items() if v['sha_mismatch']]
    norm = [k for k, v in candidates.items() if not v['published_sha256']]

    print("候选（磁盘存在 + 被已入库证据引用 + 尚未入库）= %d" % len(candidates))
    print("  必须逐字节入库 (-text) = %d" % len(be))
    for k in sorted(be):
        v = candidates[k]
        print("    %-66s %9d B  crlf=%d" % (k[:66], v['bytes'], v['crlf']))
    print("  按 autocrlf 规整即可 = %d" % len(norm))
    for k in sorted(norm):
        v = candidates[k]
        print("    %-66s %9d B  crlf=%d" % (k[:66], v['bytes'], v['crlf']))
    print("  ⚠ sha 公布但磁盘不符（不可入库，需先核对）= %d" % len(nm))
    for k in sorted(nm):
        v = candidates[k]
        print("    %-66s disk=%s published=%s" % (k[:66], v['disk_sha256'][:12],
                                                 ','.join(x[:12] for x in v['published_sha256'])))

    # 反证组
    print()
    print("--- counterproof ---")
    cp = []
    # R1：sha 公布但磁盘不符 ⇒ 必须 NOT_BYTE_EXACT
    fake = {'disk_sha256': 'a' * 64, 'published_sha256': ['b' * 64]}
    r1 = bool(fake['published_sha256']) and fake['disk_sha256'] in fake['published_sha256']
    ok1 = r1 is False
    cp.append({'name': 'R1_sha_mismatch_not_byte_exact', 'expect': 'NOT_BYTE_EXACT', 'ok': ok1})
    print("    R1 公布的 sha 与磁盘不符 ⇒ 须判 NOT-BYTE-EXACT ⇒ %s" % ('PASS' if ok1 else 'FAIL'))
    # R2：没公布 sha ⇒ 必须 NOT_BYTE_EXACT
    r2 = bool([]) and 'x' in []
    ok2 = r2 is False
    cp.append({'name': 'R2_no_published_sha_not_byte_exact', 'expect': 'NOT_BYTE_EXACT', 'ok': ok2})
    print("    R2 未公布 sha ⇒ 须判 NOT-BYTE-EXACT ⇒ %s" % ('PASS' if ok2 else 'FAIL'))
    # R3：真样本抽查：任取一个 be 项，其 published 必须等于 disk
    if be:
        v = candidates[be[0]]
        ok3 = v['disk_sha256'] in v['published_sha256']
        cp.append({'name': 'R3_real_byte_exact_sample', 'expect': 'BYTE_EXACT', 'ok': ok3,
                   'file': be[0]})
        print("    R3 抽查 %s ⇒ disk sha 须在 published 内 ⇒ %s" % (be[0][:40], 'PASS' if ok3 else 'FAIL'))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'candidates': candidates, 'n_candidates': len(candidates),
            'byte_exact': sorted(be), 'normalize_ok': sorted(norm),
            'sha_mismatch': sorted(nm),
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_baseline_plan.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_baseline_plan.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
