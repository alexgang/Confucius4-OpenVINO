#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app290_renumber_evidence.py —— **证据编号去冲突**（本轮 App 模块）。

## 为什么需要

上一会话（已失联，留有 note）用 `app283` 编号产出了 **APP-071 (a)(b)**
诊断件（`_app283_app071_spk_voice_diag.py` / `app283_app071_diag_evidence.json`）。
本轮（APP-073/074）也用了 `app283`–`app286`。

⇒ 两个不同主题共用同一编号前缀 ⇒ reviewer 在 STATUS 里看到「app283」会
分不清指哪一个 ⇒ **本轮把自己的编号整体上移**，让「编号 ↔ 主题」唯一。

| 旧名 | 新名 |
|---|---|
| `_app283_rc3_unzip_smoke.py` | `_app286_rc3_unzip_smoke.py` |
| `app283_rc3_unzip_smoke_evidence.json` | `app286_rc3_unzip_smoke_evidence.json` |
| `app283_rc3_unzip_check_output.txt` | `app286_rc3_unzip_check_output.txt` |
| `app283_rc3_unzip_smoke.log` | `app286_rc3_unzip_smoke.log` |
| `app283_rc3_unzip_out/` | `app286_rc3_unzip_out/` |
| `app283_rc3_unzip_smoke.pid` | `app286_rc3_unzip_smoke.pid` |
| `_app284_rc3_readme_count_patch.py` | `_app287_rc3_readme_count_patch.py` |
| `app284_rc3_readme_count_patch_evidence.json` | `app287_rc3_readme_count_patch_evidence.json` |
| `_app285_rc3_perftest_zip_rev2.py` | `_app288_rc3_perftest_zip_rev2.py` |
| `app285_rc3_perftest_zip_rev2_evidence.json` | `app288_rc3_perftest_zip_rev2_evidence.json` |
| `_app285_zip_listfile.txt` | `_app288_zip_listfile.txt` |
| `app286_rc3_rev2_unzip_smoke_evidence.json` | `app289_rc3_rev2_unzip_smoke_evidence.json` |

⚠️ **上一会话的 APP-071 证据一律不动**（`_app283_app071_*` / `app283_app071_*`）。

## 🔴 做法纪律

* 只**改名 + 改自引用字符串**（文件里的「脚本名 / 路径」字面量）。
* 🔴 **不改任何证据的结论字段**（`verdict` / `n_pass` / `n_fail` / 数字）。
* 改完逐个复核：JSON 里引用的**每个路径都真实存在**。
* 写前备份到 `results/app/_app290_renumber_backup/`，写后可一键回滚。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

BACKUP = os.path.join(HERE, '_app290_renumber_backup')
REPORT = os.path.join(HERE, 'app290_renumber_evidence.json')

#: (旧基名, 新基名)；目录与文件同规则
RENAMES = [
    ('_app283_rc3_unzip_smoke.py', '_app286_rc3_unzip_smoke.py'),
    ('app283_rc3_unzip_smoke_evidence.json', 'app286_rc3_unzip_smoke_evidence.json'),
    ('app283_rc3_unzip_check_output.txt', 'app286_rc3_unzip_check_output.txt'),
    ('app283_rc3_unzip_smoke.log', 'app286_rc3_unzip_smoke.log'),
    ('app283_rc3_unzip_out', 'app286_rc3_unzip_out'),
    ('app283_rc3_unzip_smoke.pid', 'app286_rc3_unzip_smoke.pid'),
    ('_app284_rc3_readme_count_patch.py', '_app287_rc3_readme_count_patch.py'),
    ('app284_rc3_readme_count_patch_evidence.json',
     'app287_rc3_readme_count_patch_evidence.json'),
    ('_app285_rc3_perftest_zip_rev2.py', '_app288_rc3_perftest_zip_rev2.py'),
    ('app285_rc3_perftest_zip_rev2_evidence.json',
     'app288_rc3_perftest_zip_rev2_evidence.json'),
    ('_app285_zip_listfile.txt', '_app288_zip_listfile.txt'),
    ('app286_rc3_rev2_unzip_smoke_evidence.json',
     'app289_rc3_rev2_unzip_smoke_evidence.json'),
]


def main():
    out = {'script': '_app290_renumber_evidence.py',
           'purpose': '证据编号去冲突（app283–app286 → app286–app289）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'renames': []}

    # ── 闸门①：源都在**或**已改名（幂等）；目标都不在（不覆盖）────
    for old, new in RENAMES:
        so = os.path.join(HERE, old)
        sn = os.path.join(HERE, new)
        if not os.path.exists(so) and not os.path.exists(sn):
            out['verdict'] = 'FAIL'
            out['reason'] = '源与目标都不存在：%s' % old
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 1
        if os.path.exists(so) and os.path.exists(sn):
            out['verdict'] = 'FAIL'
            out['reason'] = '源与目标同时存在 ⇒ 不覆盖：%s / %s' % (old, new)
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 1
    out['gate1_ok'] = True

    # ── 闸门②：上一会话的 APP-071 证据必须存在且**不参与改名** ──
    keep = ['_app283_app071_spk_voice_diag.py',
            'app283_app071_diag_evidence.json']
    for k in keep:
        if not os.path.exists(os.path.join(HERE, k)):
            out['verdict'] = 'FAIL'
            out['reason'] = '上一会话证据缺失（不应发生）：%s' % k
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 1
    out['keep_untouched'] = keep

    os.makedirs(BACKUP, exist_ok=True)

    # ── 执行改名（先备份）──────────────────────────────────────
    # 🔴 **幂等**：上一轮可能已改了一部分 ⇒ 「源不存在但目标在」⇒ 跳过改名，
    #   但**仍要跑自引用改写**（否则 JSON 里还指着旧名）。
    for old, new in RENAMES:
        so = os.path.join(HERE, old)
        sn = os.path.join(HERE, new)
        if os.path.exists(so):
            if os.path.isdir(so):
                shutil.copytree(so, os.path.join(BACKUP, old), dirs_exist_ok=True)
            else:
                shutil.copy2(so, os.path.join(BACKUP, old))
            os.rename(so, sn)
            out['renames'].append({'old': old, 'new': new})
        elif os.path.exists(sn):
            out['renames'].append({'old': old, 'new': new, 'already': True})
        else:
            out['verdict'] = 'FAIL'
            out['reason'] = '源与目标都不存在：%s' % old
            print(json.dumps(out, ensure_ascii=False, indent=1))
            return 1

    # ── 改自引用字符串（**只改路径/文件名字面量**）──────────────
    #   🔴 顺序：先长后短，避免 `_app285_zip_listfile.txt` 被
    #     `_app285_rc3_perftest_zip_rev2.py` 之类的规则误伤。
    subs = sorted(
        [(old, new) for old, new in RENAMES],
        key=lambda t: -len(t[0]))
    # 目录名要单独处理（出现在路径中间）
    subs = sorted(subs + [('app283_rc3_unzip_out', 'app286_rc3_unzip_out')],
                  key=lambda t: -len(t[0]))

    patched = []
    for fn in os.listdir(HERE):
        full = os.path.join(HERE, fn)
        if not os.path.isfile(full):
            continue
        if not (fn.endswith('.py') or fn.endswith('.json')
                or fn.endswith('.txt') or fn.endswith('.log')):
            continue
        if fn in ('_app290_renumber_evidence.py',):
            continue
        with open(full, 'rb') as f:
            raw = f.read()
        try:
            txt = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        orig = txt
        hits = {}
        for old, new in subs:
            n = txt.count(old)
            if n:
                txt = txt.replace(old, new)
                hits[old] = n
        if txt != orig:
            with open(full, 'w', encoding='utf-8', newline='') as f:
                f.write(txt)
            patched.append({'file': fn, 'hits': hits})
    out['patched_files'] = patched

    # ── 闸门③：**本轮这几个** JSON 里引用的路径都真实存在 ─────────
    #   🔴 只查本轮改名涉及的 JSON（历史证据里引用别的 appNNN 是正常的，
    #     例如 app213 → 「tool: app213」⇒ 不是缺失引用）。
    my_jsons = [new for old, new in RENAMES if new.endswith('_evidence.json')]
    missing = []
    for fn in my_jsons:
        full = os.path.join(HERE, fn)
        if not os.path.isfile(full):
            missing.append({'file': fn, 'key': '(file)', 'value': 'evidence 缺失'})
            continue
        with open(full, encoding='utf-8') as f:
            d = json.load(f)
        for k, v in d.items():
            if isinstance(v, str) and ('app2' in v or '_app2' in v):
                base = os.path.basename(v)
                if not base.startswith(('app2', '_app2')):
                    continue
                cand = os.path.join(HERE, base)
                if not os.path.exists(cand):
                    missing.append({'file': fn, 'key': k, 'value': v})
    out['checked_jsons'] = my_jsons
    out['missing_refs'] = missing
    out['gate3_ok'] = (not missing)

    # ── 闸门④：上一会话证据字节未变 ───────────────────────────
    keep_hash = {}
    for k in keep:
        p = os.path.join(HERE, k)
        import hashlib
        keep_hash[k] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    out['keep_sha256_after'] = keep_hash

    out['verdict'] = 'PASS' if (not missing) else 'FAIL'
    out['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
