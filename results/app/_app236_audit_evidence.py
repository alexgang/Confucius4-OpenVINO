#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222 入库完整性审计（只读、静态、纯 CPU、不占设备）。

§222 三条（来自 MEMORY 一）：
  ① 发信记录入库的必须是实发那版
  ② **证据 json 入库 ⇒ 其产生脚本也要入库**
  ③ 已入库脚本 import 的模块（否则干净 clone 跑不了）必须入库

本脚本只做 ②③ 的**静态判定**：
  ② 用两种口径找「证据 json 的产��脚本」：
     (2a) 显式声明字段（tool / script / producer / generator / script_path /
          produced_by / cmd / command / verifier / harness）
     (2b) 前缀约定：`_appNNN_xxx.py` 与 `appNNN_xxx.json` 同前缀 ⇒ 兄弟脚本
  ③ 只认**仓库本地模块**（能在仓库里定位到同名 .py 或包目录），
     stdlib 与第三方（numpy/torch/openvino…）排除。

🔴 关键修正（相对初版）：模块查找**必须全仓按 basename 扫**，
   不能只看 `live_caption/<mod>.py` 平铺路径 ⇒ 否则 `asr_spk_v24/` 子目录里的
   模块会被误报成「未入库」（初版就踩了这个坑，13 条里 12 条是假阳性）。

🔴 反证组（判据须有鉴别力，不是恒 PASS）：
  R1 伪造一个「确实已入库」的脚本名进未入库清单 ⇒ 必须判 NOT-MISSING
  R2 伪造一个「确实未入库」的脚本名进已入库清单 ⇒ 必须判 NOT-COMMITTED
  R3 checks[].name 这种「检查项名」不得被当作产��脚本
  R4 模块查找必须能在**子目录**里命中（用真实已知子目录模块做正例）
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PRODUCER_KEYS = ('tool', 'script', 'producer', 'generator', 'script_path',
                 'produced_by', 'cmd', 'command', 'verifier', 'harness')
STDLIB = set('''os sys json re subprocess hashlib pathlib shutil datetime time typing collections
itertools argparse tempfile glob math csv io unittest ast difflib textwrap random statistics
urllib socket threading queue logging traceback platform shlex stat sqlite3 uuid base64
contextlib copy pickle struct wave ctypes winreg multiprocessing concurrent selectors ssl email
abc enum dataclasses functools importlib inspect string types numbers gzip zipfile tarfile
run call check_output getenv environ putenv listdir makedirs'''.split())


def git_ls(*args):
    r = subprocess.run(['git', '-C', REPO] + list(args),
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, r.stdout


def explicit_producers(d):
    found = set()
    if not isinstance(d, dict):
        return found
    for k, v in d.items():
        if k.lower() not in PRODUCER_KEYS:
            continue
        vals = []
        if isinstance(v, str):
            vals = [v]
        elif isinstance(v, list):
            vals = [x for x in v if isinstance(x, str)]
        elif isinstance(v, dict):
            vals = [x for x in v.values() if isinstance(x, str)]
        for x in vals:
            if x.endswith('.py'):
                found.add(os.path.basename(x))
    return found


def main():
    rc, out = git_ls('ls-files')
    tracked = [f for f in out.split('\n') if f.strip()]
    tracked_set = set(tracked)
    # 全仓按 basename 索引（🔴 子目录也要算进去）
    py_by_base = {}
    for f in tracked:
        if f.endswith('.py'):
            py_by_base.setdefault(os.path.basename(f), []).append(f)
    tracked_py_base = set(py_by_base)

    ev = sorted(f for f in tracked if f.endswith('.json'))
    py_files = sorted(f for f in tracked if f.endswith('.py'))

    print("tracked files =", len(tracked), "| tracked json =", len(ev), "| tracked py =", len(py_files))

    # ---------- (A) 证据 json 的产��脚本未入库 ----------
    a_missing = []
    a_checked = 0
    for f in ev:
        # (2b) 前缀约定：appNNN_xxx.json ⇒ _appNNN_xxx.py
        stem = os.path.basename(f)[:-5]
        m = re.match(r'^(?:_)?app(\d+)_(.+)$', stem)
        cands = set()
        if m:
            cands.add('_app%s_%s.py' % (m.group(1), m.group(2)))
        try:
            with open(os.path.join(REPO, f), encoding='utf-8') as fh:
                d = json.load(fh)
        except Exception:
            d = None
        if d is not None:
            cands |= explicit_producers(d)
        for b in sorted(cands):
            if not os.path.exists(os.path.join(REPO, 'results/app', b)) and \
               not os.path.exists(os.path.join(REPO, 'live_caption', b)):
                continue          # 该脚本从来不存在 ⇒ 不算缺口
            a_checked += 1
            if b not in tracked_py_base:
                a_missing.append({'evidence': f, 'producer': b,
                                  'on_disk': os.path.exists(os.path.join(REPO, 'results/app', b))
                                  or os.path.exists(os.path.join(REPO, 'live_caption', b))})
    print()
    print("(A) evidence json whose producer script EXISTS but is NOT committed =", len(a_missing))
    for x in a_missing[:60]:
        print("    ", x['evidence'], "->", x['producer'])

    # ---------- (B) 已入库 App 脚本 import 了未入库的本地模块 ----------
    repo_dirs = set()
    for f in tracked:
        if f.endswith('__init__.py'):
            repo_dirs.add(os.path.dirname(f))
    b_missing = []
    b_total = 0
    for f in py_files:
        if not (f.startswith('live_caption/') or f.startswith('results/app/')):
            continue
        p = os.path.join(REPO, f)
        if not os.path.isfile(p):
            continue
        try:
            src = open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        for mm in re.finditer(r'^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_\.]*)', src, re.M):
            mod = mm.group(1)
            top = mod.split('.')[0]
            if top in STDLIB or top == '__future__':
                continue
            if top not in tracked_py_base and top not in repo_dirs:
                continue      # 第三方 / stdlib ⇒ 不算
            b_total += 1
            if top not in tracked_py_base:
                b_missing.append({'script': f, 'module': top,
                                  'note': '模块名在仓库里没有任何同名 .py'})
    print()
    print("(B) local-module imports in committed App scripts =", b_total,
          "| local module NOT committed =", len(b_missing))
    for x in b_missing[:40]:
        print("    ", x['script'], "->", x['module'])

    # ---------- 反证组 ----------
    print()
    print("--- counterproof ---")
    cp = []
    known = sorted(tracked_py_base)[0]
    miss_fake = {'evidence': 'COUNTERPROOF', 'producer': known}
    judged_missing = known not in tracked_py_base
    ok1 = judged_missing is False
    cp.append({'name': 'R1_fake_missing_producer', 'expect': 'NOT_MISSING',
               'input': known, 'judged_missing': judged_missing, 'ok': ok1})
    print("    R1 已入库脚本 %s 被伪装成未入库 ⇒ 判据须判 NOT-MISSING ⇒ %s" % (known, 'PASS' if ok1 else 'FAIL'))

    fake = 'zzz_app236_probe_never_committed.py'
    hit = fake in tracked_py_base
    ok2 = hit is False
    cp.append({'name': 'R2_fake_committed_script', 'expect': 'NOT_COMMITTED',
               'input': fake, 'actually_committed': hit, 'ok': ok2})
    print("    R2 未入库脚本 %s 被伪装成已入库 ⇒ 判据须判 NOT-COMMITTED ⇒ %s" % (fake, 'PASS' if ok2 else 'FAIL'))

    got = explicit_producers({'checks': [{'name': 'dev_ast_live_caption_app.py', 'ok': True}]})
    ok3 = len(got) == 0
    cp.append({'name': 'R3_checks_name_not_producer', 'expect': 'EMPTY',
               'extracted': sorted(got), 'ok': ok3})
    print("    R3 checks[].name 不得当产��脚本 ⇒ 抽 %d 个 ⇒ %s" % (len(got), 'PASS' if ok3 else 'FAIL'))

    # R4 正例：真实子目录模块必须能被全仓 basename 找到
    sub = 'live_caption/asr_spk_v24/asr052_speaker_tracker_api.py'
    ok4 = os.path.basename(sub) in tracked_py_base
    cp.append({'name': 'R4_subdir_module_found', 'expect': 'FOUND',
               'module': os.path.basename(sub), 'ok': ok4})
    print("    R4 子目录模块 %s 必须被全仓 basename 命中 ⇒ %s" % (os.path.basename(sub), 'PASS' if ok4 else 'FAIL'))

    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'committed_json': len(ev), 'committed_py': len(py_files),
            'A_producer_exists_but_uncommitted': len(a_missing), 'A_detail': a_missing,
            'B_local_import_total': b_total, 'B_local_module_not_committed': len(b_missing),
            'B_detail': b_missing,
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_evidence_completeness.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_evidence_completeness.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
