#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：对「被 STATUS 引用但未入库」的候选做**入库前安全扫描**。

🔴 为什么必须扫：本轮发现 `results/app/_pkg_v25_runtime_token_20261121_0428.txt`
   与 `_pkg_v25_removed_bridge_token_20261121.txt` **是活的 bridge token**
   ⇒ 若有人 `git add .` 就会**把明文口令提交进仓库**（不可逆）。

本脚本把候选分成三类：
  SECRET   ⇒ 含疑似凭据 ⇒ **永不入库**，且应写进 .gitignore
  SAFE     ⇒ 无凭据特征 ⇒ 可入库
  RUNTIME  ⇒ 运行时产物（.log 等按 .gitignore 约定不入库）

🔴 反证组：
  R1 造一个含 token 的文件 ⇒ 必须判 SECRET
  R2 造一个干净的 json      ⇒ 必须判 SAFE
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: 明文凭据特征（宁可误报）
SECRET_PAT = re.compile(
    r'(?i)(bridge[_-]?token|access[_-]?token|refresh[_-]?token|api[_-]?key|'
    r'secret[_-]?key|client[_-]?secret|private[_-]?key|password|passwd|'
    r'ctk_[A-Za-z0-9_\-]{8,}|'
    r'\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}|'
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----)')


def git(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True).stdout.decode('utf-8', 'replace')


def scan_text(path):
    try:
        raw = open(path, 'rb').read()
    except Exception:
        return []
    hits = []
    # 文本扫
    try:
        txt = raw.decode('utf-8', errors='replace')
    except Exception:
        txt = ''
    for i, ln in enumerate(txt.split('\n'), 1):
        if SECRET_PAT.search(ln):
            hits.append('L%d: %s' % (i, ln.strip()[:100]))
    # 高熵裸串（长度 24+ 的 base64url 风格，且不是 json 键）
    if len(raw) < 4096 and not hits:
        s = txt.strip()
        if re.fullmatch(r'[A-Za-z0-9_\-]{24,}', s):
            hits.append('whole-file high-entropy token: %s…' % s[:12])
    return hits


def main():
    plan_path = os.path.join(REPO, 'results/app/app236_status_cited_scan.json')
    scan = json.load(open(plan_path, encoding='utf-8'))
    cands = scan['on_disk_gaps']

    secret, safe, runtime = [], [], []
    for rel in cands:
        p = os.path.join(REPO, rel)
        base = os.path.basename(rel)
        if base.endswith('.log'):
            runtime.append({'file': rel, 'why': '运行时日志（.gitignore 已约定 *.log 不入库）'})
            continue
        hits = scan_text(p)
        if hits:
            secret.append({'file': rel, 'hits': hits})
        else:
            safe.append(rel)

    print("候选（磁盘存在）= %d" % len(cands))
    print("  SECRET（永不入库）= %d" % len(secret))
    for s in secret:
        print("    🔴 %s" % s['file'])
        for h in s['hits'][:3]:
            print("         %s" % h)
    print("  RUNTIME（按约定不入库）= %d" % len(runtime))
    for r in runtime:
        print("    🟡 %s  (%s)" % (r['file'], r['why']))
    print("  SAFE（可入库）= %d" % len(safe))
    for s in safe:
        print("    🟢 %s" % s)

    print()
    print("--- counterproof ---")
    cp = []
    tmp1 = os.path.join(REPO, 'results/app/_app236_tmp_secret_probe.txt')
    tmp2 = os.path.join(REPO, 'results/app/_app236_tmp_clean_probe.json')
    try:
        with open(tmp1, 'w', encoding='utf-8') as fh:
            fh.write('bridge_token=abcdef0123456789abcdef\n')
        h1 = scan_text(tmp1)
        ok1 = len(h1) > 0
        cp.append({'name': 'R1_token_detected', 'expect': 'SECRET', 'ok': ok1})
        print("    R1 含 bridge_token 的文件 ⇒ 须判 SECRET ⇒ %s" % ('PASS' if ok1 else 'FAIL'))
        with open(tmp2, 'w', encoding='utf-8') as fh:
            json.dump({'a': 1, 'b': 'hello world'}, fh)
        h2 = scan_text(tmp2)
        ok2 = len(h2) == 0
        cp.append({'name': 'R2_clean_not_secret', 'expect': 'SAFE', 'ok': ok2})
        print("    R2 干净的 json ⇒ 须判 SAFE ⇒ %s" % ('PASS' if ok2 else 'FAIL'))
        # R3 高熵裸 token 也必须命中
        tmp3 = os.path.join(REPO, 'results/app/_app236_tmp_entropy_probe.txt')
        with open(tmp3, 'w', encoding='utf-8') as fh:
            fh.write('vXLN8S1m0lXRMlEGQcBG-nZ_pJRsV2Wa\n')
        h3 = scan_text(tmp3)
        ok3 = len(h3) > 0
        cp.append({'name': 'R3_high_entropy_token_detected', 'expect': 'SECRET', 'ok': ok3})
        print("    R3 高熵裸 token ⇒ 须判 SECRET ⇒ %s" % ('PASS' if ok3 else 'FAIL'))
    finally:
        for t in (tmp1, tmp2):
            if os.path.isfile(t):
                os.remove(t)
        tmp3 = os.path.join(REPO, 'results/app/_app236_tmp_entropy_probe.txt')
        if os.path.isfile(tmp3):
            os.remove(tmp3)
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'n_candidates': len(cands), 'secret': secret, 'runtime': runtime,
            'safe': safe, 'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_secret_scan.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_secret_scan.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
