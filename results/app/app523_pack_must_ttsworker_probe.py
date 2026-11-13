#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app523_pack_must_ttsworker_probe.py —— §190 第二处修法的证据脚本：
「包内缺 `app/tts_worker.py`」在**改前**会不会被打包流水线放行。

## 背景（§190 实测，不是推测）

🔴 **改前**（`git cat-file blob HEAD:pack_v13.py` 可核）的三处事实：

1. **MUST 清单里没有 `app/tts_worker.py`**（39 条，只有 `app/translator.py` /
   `app/live_caption_app.py` / `app/MANIFEST.json` 三个 `app/` 条目）
   ⇒ zip 校验（`_verify_and_report`）与 dry-run（`do_dry_run`）的
   「关键文件缺失」判定**都不会提到它**；
2. **闸门③（APP-081）对 v2.4 / v2.5 不查 `app/` 里的生产模块**
   （`verify_source` 那段只在 `cur == (2, 3)` 跑）⇒ 不查 `tts_worker.py`；
3. **闸门④（§187）遇到「包内无 app/tts_worker.py」打印
   `[SKIP] ⇒ 本闸门不适用` 并 `return 0`** ⇒ **rc=0 放行**。

⇒ 三处叠加 ⇒ **打包流水线全程绿灯** ⇒ 交付一个**没有 TTS worker** 的包
⇒ 客户装完 TTS 全程无声（**静默**缺陷：客户看不出来，打包方也看不出来）。

## 本脚本干什么（**纯离线、零 GPU、零推理、不占锁、不调 MiniMax、对客户包只读**）

**A. 改前事实**：从 `git cat-file blob HEAD:pack_v13.py` 取**已提交**版本
   ⇒ 断言 MUST 里**没有** `app/tts_worker.py`、且闸门④ 缺文件分支是
   `[SKIP] ⇒ return 0`（⇒ 缺口确实存在于**已提交**代码，不是本轮臆想）。

**B. 改后探针**：造一个「MUST 条目**全部**存在、**只缺** `app/tts_worker.py`」
   的最小包目录 ⇒
   ① `check_app086_2a_narrowing` ⇒ **rc=1** 且输出「拒绝打包」；
   ② `do_dry_run` ⇒ **rc=1**，且「关键文件检查」里**只有**
      `app/tts_worker.py` 标「缺」、其余 **38 条全 OK**（⇒ 不误伤）；
   ③ 把 dev 树的收窄 `tts_worker.py` 补进去 ⇒ 闸门④ **rc=0**（⇒ 不是一律拦）。

**C. 回归**：磁盘上**每一个** `Confucius4_LiveCaption_*/app` ⇒ 新增的 3 个
   MUST 条目**全部存在**（记文件大小）⇒ **不误伤任何现存包**。

**D. e2e（AST）**：`_verify_and_report` 的 FAIL 条件**包含** `missing`
   ⇒ zip 校验对缺关键文件** fail-closed**（旧 zip 保持完好、不改名）。

🔴 探针建在**临时目录** ⇒ 不碰 dev 树与任何客户包。

## 产物

`results/app/app523_pack_must_ttsworker_evidence.json`
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY312 = r'C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe'
PKG_ROOT = r'C:\Users\Trekker-PTL'
SRC_LIVE = os.path.join(REPO, 'live_caption')
OUT = os.path.join(HERE, 'app523_pack_must_ttsworker_evidence.json')
NEW_MUST = ('app/tts_worker.py', 'app/tts_service.py', 'app/tts_engine.py')


def head_pack_v13():
    """取**已提交**（HEAD）版 pack_v13.py 的源码文本。"""
    p = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:pack_v13.py'],
                       cwd=REPO, capture_output=True)
    return p.stdout.decode('utf-8')


def must_list(src):
    tree = ast.parse(src.replace('\r\n', '\n'))
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and \
                any(getattr(t, 'id', None) == 'MUST' for t in n.targets):
            return [e.value for e in n.value.elts]
    return []


def run_child(code):
    p = subprocess.run([PY312, '-c', code], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return p.stdout or '', p.stderr or ''


def run_gate4(pkg_dir):
    code = (
        'import sys, io, contextlib\n'
        'sys.path.insert(0, %r)\n'
        'import pack_v13\n'
        'buf = io.StringIO()\n'
        'with contextlib.redirect_stdout(buf):\n'
        '    rc = pack_v13.check_app086_2a_narrowing(%r)\n'
        'sys.stdout.write(buf.getvalue())\n'
        'print("GATE4_RC=%%d" %% rc)\n'
    ) % (REPO, pkg_dir)
    out, err = run_child(code)
    rc = None
    for line in out.splitlines():
        if line.startswith('GATE4_RC='):
            rc = int(line.split('=')[1])
    return rc, out.strip()


def run_dry_run(pkg_dir):
    code = (
        'import sys, io, contextlib\n'
        'sys.path.insert(0, %r)\n'
        'import pack_v13\n'
        'buf = io.StringIO()\n'
        'with contextlib.redirect_stdout(buf):\n'
        '    rc = pack_v13.do_dry_run(%r, "PROBE")\n'
        'sys.stdout.write(buf.getvalue())\n'
        'print("DRYRUN_RC=%%d" %% rc)\n'
    ) % (REPO, pkg_dir)
    out, err = run_child(code)
    rc = None
    for line in out.splitlines():
        if line.startswith('DRYRUN_RC='):
            rc = int(line.split('=')[1])
    # 抽「关键文件检查」小节
    sec = ''
    if '关键文件检查：' in out:
        sec = out.split('关键文件检查：', 1)[1]
        for stop in ('内部会议内容检查', '结论：'):
            if stop in sec:
                sec = sec.split(stop, 1)[0]
    ok = re.findall(r'\[OK\] (\S+)', sec)
    miss = re.findall(r'\[缺\] (\S+)', sec)
    return rc, ok, miss, out


def build_probe(root, skip_worker=True):
    """造一个「MUST 条目全在、只缺 app/tts_worker.py」的最小包目录。"""
    sys.path.insert(0, REPO)
    import pack_v13
    pkg = os.path.join(root, 'probe')
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
    for rel in pack_v13.MUST:
        if skip_worker and rel == 'app/tts_worker.py':
            continue
        p = os.path.join(pkg, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if rel.endswith('.json'):
            with io.open(p, 'w', encoding='utf-8') as f:
                f.write('{}')
        else:
            with io.open(p, 'wb') as f:
                f.write(b'probe')
    return pkg


def main():
    out = {'script': os.path.basename(__file__),
           'note': '「包内缺 app/tts_worker.py」在改前是否被放行；'
                   '探针在临时目录；客户包只读'}
    tmp = tempfile.mkdtemp(prefix='app523_')
    try:
        # ── A. 改前事实（已提交版）──
        head = head_pack_v13()
        head_must = must_list(head)
        pre = dict(
            head_must_count=len(head_must),
            head_has_tts_worker=('app/tts_worker.py' in head_must),
            head_gate4_missing_file_is_skip=(
                '[SKIP] 包内无 app/tts_worker.py' in head),
            head_gate4_missing_file_returns_0=(
                re.search(r"无 app/tts_worker\.py[^\n]*\n\s*return 0",
                          head) is not None),
        )
        out['prefix_facts'] = pre
        print('#' * 74)
        print('# A. 改前事实（已提交版 pack_v13.py）')
        print('#' * 74)
        print('  MUST 条数                 : %d' % pre['head_must_count'])
        print('  MUST 含 app/tts_worker.py : %s'
              % ('是' if pre['head_has_tts_worker'] else '*** 否（缺口属实）***'))
        print('  闸门④ 缺文件分支是 SKIP   : %s'
              % ('是（⇒ rc=0 放行）' if pre['head_gate4_missing_file_is_skip']
                 else '否'))
        pre_ok = (not pre['head_has_tts_worker']
                  and pre['head_gate4_missing_file_is_skip']
                  and pre['head_gate4_missing_file_returns_0'])
        out['prefix_facts_ok'] = bool(pre_ok)
        print('  ⇒ 改前确实放行：%s' % ('是' if pre_ok else '否'))

        # ── B. 改后探针 ──
        print()
        print('#' * 74)
        print('# B. 改后探针（缺 app/tts_worker.py 的最小包）')
        print('#' * 74)
        pkg = build_probe(tmp, skip_worker=True)
        rc4, out4 = run_gate4(pkg)
        drc, ok_list, miss_list, dout = run_dry_run(pkg)
        b = dict(
            gate4_rc=rc4,
            gate4_refuses=('拒绝打包' in out4),
            dryrun_rc=drc,
            dryrun_must_ok=len(ok_list),
            dryrun_must_missing=miss_list,
            dryrun_missing_exactly_worker=(miss_list == ['app/tts_worker.py']),
            gate4_output=out4,
        )
        # 对照：把 dev 树的收窄 tts_worker.py 补进去 ⇒ 闸门④ 应 PASS
        shutil.copy2(os.path.join(SRC_LIVE, 'tts_worker.py'),
                     os.path.join(pkg, 'app', 'tts_worker.py'))
        rc4b, out4b = run_gate4(pkg)
        drc_b, ok_b, miss_b, _ = run_dry_run(pkg)
        b.update(gate4_rc_with_worker=rc4b,
                 dryrun_must_missing_with_worker=miss_b,
                 dryrun_rc_with_worker=drc_b)
        out['probe'] = b
        print('  缺 app/tts_worker.py：闸门④ rc=%s（预期 1）｜输出含「拒绝打包」=%s'
              % (rc4, b['gate4_refuses']))
        print('                   dry-run rc=%s（预期 1）｜MUST 缺 %s（预期只有 worker）'
              % (drc, miss_list))
        print('  补上 dev 收窄文件：闸门④ rc=%s（预期 0）｜dry-run MUST 缺 %s'
              % (rc4b, miss_b))

        # ── C. 回归：全部真包 ──
        print()
        print('#' * 74)
        print('# C. 回归（每个真包的新 MUST 条目齐全性）')
        print('#' * 74)
        rows, all_ok = [], True
        names = sorted(n for n in os.listdir(PKG_ROOT)
                       if n.startswith('Confucius4_LiveCaption_')
                       and os.path.isdir(os.path.join(PKG_ROOT, n)))
        for name in names:
            app = os.path.join(PKG_ROOT, name, 'app')
            if not os.path.isdir(app):
                continue
            ent = {}
            for rel in NEW_MUST:
                p = os.path.join(app, os.path.basename(rel))
                ent[rel] = os.path.getsize(p) if os.path.isfile(p) else None
            ok = all(v is not None for v in ent.values())
            all_ok = all_ok and ok
            rows.append(dict(pkg=name, files=ent, all_present=bool(ok)))
            print('  %-46s %s' % (name, '齐全' if ok else '*** 缺 ***'))
        out['packages'] = rows
        out['packages_total'] = len(rows)
        out['packages_all_present'] = bool(all_ok)
        print('  ⇒ %d/%d 个包全部含这 3 个文件（新增 MUST 条目不误伤）'
              % (len(rows), len(rows)) if all_ok else '  ⇒ 有包缺失！')

        # ── D. e2e（AST）：zip 校验对缺关键文件 fail-closed ──
        with io.open(os.path.join(REPO, 'pack_v13.py'), 'r', encoding='utf-8',
                     newline='') as f:
            tree = ast.parse(f.read().replace('\r\n', '\n'))
        fail_cond = None
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == '_verify_and_report':
                for x in ast.walk(n):
                    if isinstance(x, ast.If) and \
                            isinstance(x.test, ast.BoolOp):
                        src_txt = ast.unparse(x.test)
                        if 'missing' in src_txt:
                            fail_cond = src_txt
                            break
        out['e2e'] = dict(verify_fail_condition=fail_cond,
                          zip_verify_fail_closed=bool(
                              fail_cond and 'missing' in fail_cond))
        print()
        print('#' * 74)
        print('# D. e2e（zip 校验对「关键文件缺失」fail-closed）')
        print('#' * 74)
        print('  _verify_and_report 的 FAIL 条件含 missing：%s'
              % ('是' if out['e2e']['zip_verify_fail_closed'] else '否'))

        out['verdict'] = 'PASS' if (
            pre_ok
            and b['gate4_rc'] == 1 and b['gate4_refuses']
            and b['dryrun_rc'] == 1 and b['dryrun_missing_exactly_worker']
            and b['gate4_rc_with_worker'] == 0
            and all_ok
            and out['e2e']['zip_verify_fail_closed']
        ) else 'FAIL'
        with io.open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('\nevidence -> %s' % OUT)
        print('VERDICT: %s' % out['verdict'])
        return 0 if out['verdict'] == 'PASS' else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
