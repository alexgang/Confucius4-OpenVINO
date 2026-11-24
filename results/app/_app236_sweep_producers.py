#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 补充扫描：**按内容**找「证据文件的生产者脚本」。

初版只按「_appNNN_ 前缀约定 + 显式 producer 字段」找 ⇒ 只能覆盖一小部分。
本脚本改成：**扫全仓磁盘上的 .py，若其源码里出现某个已入库证据文件的名字**
        ⇒ 该脚本就是该证据的生产者 ⇒ 检查它是否入库。

这样不依赖命名约定，能覆盖 json / jsonl / csv 全部证据类型。
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def git_ls(*args):
    r = subprocess.run(['git', '-C', REPO] + list(args),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.stdout


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)
    tracked_py_base = {os.path.basename(f) for f in tracked if f.endswith('.py')}

    # 已入库的证据文件（results/app 下）
    ev_files = [f for f in tracked
                if f.startswith('results/app/')
                and os.path.splitext(f)[1] in ('.json', '.jsonl', '.csv')
                and not os.path.basename(f).startswith('_')]
    ev_basenames = {os.path.basename(f) for f in ev_files}
    print("committed evidence files (results/app, json/jsonl/csv) =", len(ev_files))

    # 磁盘上所有 .py（results/app + live_caption）
    disk_py = []
    for d in ('results/app', 'live_caption'):
        for root, dirs, files in os.walk(os.path.join(REPO, d)):
            dirs[:] = [x for x in dirs if x not in ('__pycache__', '.git', 'models')]
            for fn in files:
                if fn.endswith('.py'):
                    disk_py.append(os.path.relpath(os.path.join(root, fn), REPO))
    disk_py.sort()
    print("on-disk .py scanned =", len(disk_py))

    # 内容扫描：脚本里写了哪个证据文件名
    pairs = []          # (evidence, producer_rel)
    for p in disk_py:
        try:
            src = open(os.path.join(REPO, p), encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        # 只看「像输出路径」的引用：出现 'xxx.json' 字面量
        for m in re.finditer(r"""['"]([\w\-\.]+\.(?:json|jsonl|csv))['"]""", src):
            base = m.group(1)
            if base in ev_basenames:
                pairs.append((base, p))

    # 折叠：同一 evidence 可能有多个脚本提到，取「最像生产者」的（文件名含同前缀且
    # 含 json.dump / to_csv / write_text 等写出动作）
    WRITE_RE = re.compile(r'json\.dump|to_csv|write_text|\.write\(|csv\.writer|writerow')
    best = {}
    for ev, p in pairs:
        src = open(os.path.join(REPO, p), encoding='utf-8', errors='replace').read()
        score = 0
        if WRITE_RE.search(src):
            score += 2
        stem = os.path.splitext(ev)[0]
        if stem.lower() in os.path.basename(p).lower():
            score += 3
        cur = best.get(ev)
        if cur is None or score > cur[0]:
            best[ev] = (score, p)

    missing = []
    for ev, (score, p) in sorted(best.items()):
        base = os.path.basename(p)
        if base not in tracked_py_base:
            missing.append({'evidence': ev, 'producer': p,
                            'producer_basename': base,
                            'score': score,
                            'producer_committed': False})
    print()
    print("evidence files whose PRODUCER SCRIPT is on disk but NOT committed =", len(missing))
    for x in missing:
        print("    ", x['evidence'], "->", x['producer'], "(score %d)" % x['score'])

    outp = {'committed_evidence_files': len(ev_files),
            'disk_py_scanned': len(disk_py),
            'producer_pairs_found': len(best),
            'producer_not_committed': len(missing),
            'detail': missing}
    with open(os.path.join(REPO, 'results/app/app236_producer_sweep.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_producer_sweep.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())
