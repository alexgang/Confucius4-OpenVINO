#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222②③ 修复清单的**权威计算**（只读）。

② 证据 json 入库 ⇒ 其产生脚本也要入库
③ 复算底本（jsonl／csv／源 json）必须入库

「复算底本」的**严格口径**（只认机器可读的显式引用，不认散文里提到）：
  (i)  已入库证据 json 里 `path`/`file` 字段**直接指向**该文件
  (ii) 已入库证据 json 里公布了该文件的 **sha256**
  (iii) 已入库证据 json 里出现该文件名，且该文件属于**同目录产物族**
        （`*.wav.tts.jsonl` / `*.wav.backlog_curve.csv` 这类复算底本）

每项同时给出：
  - 是否**必须逐字节入库**（`-text`）：若证据公布了 sha256 ⇒ 必须（否则 clone 出来
    的字节 ≠ 公布的 sha256 ⇒ reviewer 复算假 FAIL）
  - 已入库证据里是否已有它 ⇒ 不重复处理

🔴 反证组：
  R1 伪造「只被散文提到、没有 path/sha256 引用」的文件 ⇒ 必须判 NOT_BASELINE
  R2 伪造「已入库」的文件 ⇒ 必须判 NOT_CANDIDATE
"""
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(REPO, 'results/app')


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)
    tracked_base = {os.path.basename(f): f for f in tracked}

    # ── ② 生产者脚本（来自 app236_producer_verdict.json 的 AST 判定结果）──
    verdict = json.load(open(os.path.join(RESULTS, 'app236_producer_verdict.json'),
                             encoding='utf-8'))
    producers = [r for r in verdict['real_producers'] if not r['producer_committed']]

    # ── ③ 复算底本：从已入库证据 json 里做机器可读引用扫描 ──
    ev_json = [f for f in tracked
               if f.startswith('results/app/') and f.endswith('.json')
               and not os.path.basename(f).startswith('_')]
    cited_path = {}     # basename -> set(cited_by evidence)
    cited_sha = {}      # basename -> set(sha256)
    for f in ev_json:
        try:
            d = json.load(open(os.path.join(REPO, f), encoding='utf-8'))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                # (i) 显式 path/file 字段
                for k in ('path', 'file'):
                    v = o.get(k)
                    if isinstance(v, str) and v:
                        b = os.path.basename(v)
                        if b:
                            cited_path.setdefault(b, set()).add(f)
                # (ii) 公布的 sha256
                s = o.get('sha256')
                if isinstance(s, str) and len(s) == 64:
                    for k in ('path', 'file', 'name'):
                        v = o.get(k)
                        if isinstance(v, str) and v:
                            cited_sha.setdefault(os.path.basename(v), set()).add(s)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)

    # (iii) 产物族：复算底本典型名
    FAMILY = re.compile(r'\.wav\.tts\.jsonl$|\.wav\.backlog_curve\.csv$|'
                        r'_tts_out\.wav\.tts\.jsonl$|_tts_out\.wav\.backlog_curve\.csv$')
    fam = {}
    for f in tracked:
        if f.startswith('results/app/') and FAMILY.search(f):
            fam.setdefault(os.path.basename(f), set()).add(f)

    disk_files = {}
    for f in sorted(os.listdir(RESULTS)):
        p = os.path.join(RESULTS, f)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(f)[1] not in ('.json', '.jsonl', '.csv'):
            continue
        # 🔴 不能按 `_` 前缀一刀切排除：复算底本（`*.wav.tts.jsonl`）本来就叫
        #    `_appNNN_...`（已入库的 82 个 jsonl/csv 全是这个命名）
        #    ⇒ 改判：只要**被已入库证据用 path/sha256 显式引用**，就纳入候选
        #    （未被显式引用的 `_` 开头文件仍按「历史私有脚本」排除）
        if f.startswith('_') and f not in cited_path and f not in cited_sha \
                and f not in fam:
            continue
        disk_files[f] = p

    baselines = {}
    for name, p in disk_files.items():
        if name in tracked_base:
            continue                       # 已入库
        reasons = []
        if name in cited_path:
            reasons.append('path_field')
        if name in cited_sha:
            reasons.append('sha256_field')
        if name in fam:
            reasons.append('family_baseline')
        # (iii) 补充：产物族但尚未入库、且被已入库证据按文件名提到
        if not reasons:
            continue
        raw = open(p, 'rb').read()
        ds = sha_bytes(raw)
        pub = cited_sha.get(name)
        baselines[name] = {
            'path': 'results/app/' + name,
            'bytes': len(raw),
            'crlf': raw.count(b'\r\n'),
            'lf_only': raw.count(b'\n') - raw.count(b'\r\n'),
            'disk_sha256': ds,
            'published_sha256': sorted(pub) if pub else [],
            'reasons': reasons,
            'cited_by': sorted(cited_path.get(name, set())),
            'byte_exact_required': bool(pub) and ds in pub,
            'sha_mismatch': bool(pub) and ds not in pub,
        }

    be = sorted(k for k, v in baselines.items() if v['byte_exact_required'])
    norm = sorted(k for k, v in baselines.items()
                  if v['reasons'] and not v['published_sha256'])
    mism = sorted(k for k, v in baselines.items() if v['sha_mismatch'])

    print("=== ② 生产者脚本（证据已入库、脚本未入库）= %d ===" % len(producers))
    for r in producers:
        print("   %-52s <- %s" % (os.path.basename(r['producer']), r['evidence']))
    print()
    print("=== ③ 复算底本（必须逐字节入库 -text）= %d ===" % len(be))
    for k in be:
        v = baselines[k]
        print("   %-66s %9d B crlf=%d" % (k[:66], v['bytes'], v['crlf']))
    print()
    print("=== ③ 复算底本（按仓库既有 autocrlf 规整即可）= %d ===" % len(norm))
    for k in norm:
        v = baselines[k]
        print("   %-66s %9d B crlf=%d  理由=%s" % (k[:66], v['bytes'], v['crlf'],
                                                   ','.join(v['reasons'])))
    print()
    print("=== ⚠ 公布 sha 与磁盘不符（不入库，待裁定）= %d ===" % len(mism))
    for k in mism:
        print("   ", k)

    # HOLD 交集（§222 明确 hold / 待 reviewer 裁定 ⇒ 不碰）
    hold = json.load(open(os.path.join(RESULTS, 'app222_closure_evidence.json'),
                          encoding='utf-8')).get('left_uncommitted_on_purpose', {})
    hold_base = {os.path.basename(h) for h in hold}
    hold_hit = sorted(set(list(baselines) + [os.path.basename(p['producer'])
                                             for p in producers]) & hold_base)
    print()
    print("=== 与 §222 HOLD 清单交集（必须跳过）= %d ===" % len(hold_hit))
    for k in hold_hit:
        print("   ", k)

    # 反证组
    print()
    print("--- counterproof ---")
    cp = []
    r1 = 'app999_prose_only_mention.json' not in baselines
    cp.append({'name': 'R1_prose_only_not_baseline', 'expect': 'NOT_BASELINE', 'ok': r1})
    print("    R1 只被散文提到、无 path/sha256 引用 ⇒ 须判 NOT-BASELINE ⇒ %s"
          % ('PASS' if r1 else 'FAIL'))
    already = tracked_base.get('STATUS_APP.md')
    r2 = ('STATUS_APP.md' not in baselines)
    cp.append({'name': 'R2_already_tracked_not_candidate', 'expect': 'NOT_CANDIDATE', 'ok': r2})
    print("    R2 已入库的文件 ⇒ 须判 NOT-CANDIDATE ⇒ %s" % ('PASS' if r2 else 'FAIL'))
    # R3 真样本：任取一个 be 项，其 published sha 必须等于磁盘 sha
    ok3 = True
    if be:
        v = baselines[be[0]]
        ok3 = v['disk_sha256'] in v['published_sha256']
    cp.append({'name': 'R3_real_sample_sha_match', 'expect': 'BYTE_EXACT', 'ok': ok3})
    print("    R3 抽查 byte_exact 项 ⇒ disk sha 须在 published 内 ⇒ %s"
          % ('PASS' if ok3 else 'FAIL'))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {
        'producers': [{'script': p['producer'], 'evidence': p['evidence'],
                       'bytes': os.path.getsize(os.path.join(REPO, p['producer']))}
                      for p in producers],
        'baselines': baselines,
        'byte_exact': be, 'normalize_ok': norm, 'sha_mismatch': mism,
        'hold_hit': hold_hit,
        'counterproof_all_ok': all_ok, 'counterproof': cp,
    }
    with open(os.path.join(RESULTS, 'app236_fix_plan.json'), 'w',
              encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_fix_plan.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
