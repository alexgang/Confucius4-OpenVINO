#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app571 —— §208 **完整版（`pack_v13.py`）出包闸门「验收绑定」的鉴别力矩阵**。

🔴🔴🔴 **这个脚本要证明什么**
--------------------------
`pack_v13.py`（**完整版**形态，即下一版 **v2.5** 要用的那个打包脚本）
此前**完全没有验收闸门**：

  ① `ACCEPTED.json` 全仓**只有** `shortcut_update.py` 读它
     ⇒ 而它是在 **zip 已经写完之后**才跑的，只决定「要不要改桌面快捷方式」；
  ② 真正会查漂移的 `app191_acceptance_code_binding_gate.py`
     **从未被 `pack_v13.py` 调用**（仓库内无任何调用点）；
  ⇒ 验收证据**不参与出包决策** ⇒ **验收后改包照样能出包**
     （交付包 ≠ 被验收过的包）。

⇒ 与 §204（Special MVP）／§207（MiniMVP）修掉的是**同一类 fail-open**，
  只是**完整版这一形态从来没被审过**。

🔴 **鉴别力设计（两条腿都要站得住）**
------------------------------------
**A 腿 · 行为级真跑**（主证据）
  * **改前臂** = `git cat-file blob HEAD:pack_v13.py`（**逐字原文**，字节级取自 HEAD）
  * **改后臂** = 工作区的 `pack_v13.py`
  * 两臂都在**临时假包**上**真跑 `_run()`**（不是 import、不是看代码）
  * **两臂用完全相同的桩**（把 ① 路径写死 ② 版本标识 ③ APP-081 洁净度
    ④ APP-086·2a 收窄 ＋ 内部素材 ＋ zip 内容校验 ＋ 交付指纹落盘 全部打桩）
    ⇒ **唯一变量 = 验收绑定闸门**
  * 观测口径 = **真的产出了 zip 没有**（不是看打印）
  * ⚠️ **零写客户包**（假包与 zip 全在临时目录）／**不出正式 zip**／
    **不碰交付指纹落盘**（打桩）／**不跑推理**（不占 GPU）／**不取机器锁**

**B 腿 · AST 直读表**（辅证）
  * 直接读两臂 `_run()` 的 AST，列出**出包前实际调用的闸门**
  * 证明改前臂的闸门集合里**没有任何一个**会读 `ACCEPTED.json`

**C 腿 · 真包只读复验**（防假 FAIL）
  * 改后臂的 `check_acceptance_binding` 对**真 v2.1／v2.2／v2.4** 三个包
    **只读**复验 ⇒ 必须 PASS（否则就是「闸门把好包拦了」的假 FAIL）
  * 同一真包的**临时副本**上改一个字 ⇒ 必须 BLOCK
    ⇒ **真包零写入**

**纪律**：纯离线（只读真包 + 临时假包）⇒ **不占机器锁**、不跑推理、不碰 GPU。
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(REPO, 'pack_v13.py')
OUT = os.path.join(REPO, 'results', 'app',
                   'app571_ful_version_acceptance_gate_matrix.json')
FAKE_VER = '9.9'


# ══════════════════════════════════════════════════════════════════════
# 取两臂源码
# ══════════════════════════════════════════════════════════════════════
#: 🔴 **改前臂钉在固定 commit**（= 本轮修闸门**之前**的那个 HEAD）
#: ⇒ 本轮提交之后 **HEAD 已含修复** ⇒ 若还用 HEAD 当「改前臂」，
#:    重跑矩阵会得到「改前 == 改后」⇒ **看不出 fail-open** ⇒ 结论失真。
BASE_REV = '39c503a'


def head_blob_bytes():
    """**改前臂** = 钉定 commit 里的 pack_v13.py（逐字原文，字节级）。"""
    for ref in ('%s:pack_v13.py' % BASE_REV, 'HEAD:pack_v13.py'):
        r = subprocess.run(['git', 'cat-file', 'blob', ref],
                           cwd=REPO, capture_output=True)
        if r.returncode == 0:
            if ref.startswith('HEAD'):
                print('[warn] ⚠️ 钉定 commit %s 取不到 ⇒ 回退 HEAD；'
                      '若 HEAD 已含修复，**改前臂不再是「改前」** ⇒ 结论失真。'
                      % BASE_REV)
            return r.stdout
    raise RuntimeError('git cat-file 失败：%r' % r.stderr[:200])


def worktree_bytes():
    with open(PACK, 'rb') as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════
# AST 直读表：出包前实际调用的闸门
# ══════════════════════════════════════════════════════════════════════
def gates_in_run(src_bytes):
    """读 `_run()` 的 AST ⇒ 列出它在打包前调用的 `check_*` 闸门。"""
    src = src_bytes.decode('utf-8')
    tree = ast.parse(src)
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == '_run':
            fn = n
            break
    if fn is None:
        return None, []
    gates = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            nm = n.func.id
            if nm.startswith('check_') and nm not in gates:
                gates.append(nm)
    return fn, gates


def acceptance_touching_gates(src_bytes):
    """闸门里**有没有**读 `ACCEPTED.json` / `code_fingerprints` 的。"""
    src = src_bytes.decode('utf-8')
    tree = ast.parse(src)
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.FunctionDef):
            continue
        body_src = ast.unparse(n)
        if ('ACCEPTED.json' in body_src
                or 'code_fingerprints' in body_src
                or 'check_acceptance' in body_src):
            hits.append(n.name)
    return sorted(set(hits))


# ══════════════════════════════════════════════════════════════════════
# 建臂：exec 源码（**不 import** ⇒ 不跑模块主体副作用）
# ══════════════════════════════════════════════════════════════════════
def build_arm(src_bytes):
    """把一臂的源码 exec 成一个命名空间，并打上**两臂完全相同**的桩。"""
    src = src_bytes.decode('utf-8')
    ns = {'__name__': 'pack_arm', '__file__': PACK}
    exec(compile(src, PACK, 'exec'), ns)          # 模块顶层无写操作（已核）
    ns['PKG_VERSION'] = FAKE_VER

    # ── 桩：与「验收绑定」正交的闸门一律放行（**两臂同款**）──
    stubs = {
        'check_pkg_path_hardcode': lambda *a, **k: 0,
        'check_version_identity': lambda *a, **k: 0,
        'check_v23_pkg_gate': lambda *a, **k: 0,
        'check_app086_2a_narrowing': lambda *a, **k: 0,
        'check_internal_material': lambda *a, **k: 0,
    }
    for name, fn in stubs.items():
        if name in ns:
            ns[name] = fn

    # zip 内容校验 ⇒ 放行（聚焦「闸门」这一个变量）
    ns['_verify_and_report'] = lambda *a, **k: True

    # 🔴 交付指纹落盘会写**仓库** `results/app/DELIVERY_*.json` ⇒ 打桩
    #    （矩阵跑完仓库里不该多出任何文件）
    ns['write_delivery_manifest'] = lambda *a, **k: '<stubbed>'
    return ns


# ══════════════════════════════════════════════════════════════════════
# 假包
# ══════════════════════════════════════════════════════════════════════
def make_fake_pkg(td, name='Confucius4_LiveCaption_v%s' % FAKE_VER,
                  accepted=True, version=FAKE_VER, pkg_dir=None,
                  with_binding=True, modules=None, aggregate=None):
    pkg = os.path.join(td, name)
    app = os.path.join(pkg, 'app')
    os.makedirs(app, exist_ok=True)
    mods = modules if modules is not None else {'a.py': 'x = 1\n',
                                                'b.py': 'y = 2\n'}
    for fn, txt in mods.items():
        with open(os.path.join(app, fn), 'w', encoding='utf-8') as f:
            f.write(txt)
    if accepted is not None:
        fps = {}
        for fn in mods:
            data = open(os.path.join(app, fn), 'rb').read()
            data = data.replace(b'\r\n', b'\n')
            fps[fn] = hashlib.sha256(data).hexdigest()
        h = hashlib.sha256()
        for fn in sorted(fps):
            h.update(fn.encode('utf-8'))
            h.update(b'\0')
            h.update(bytes.fromhex(fps[fn]))
        acc = {
            'accepted': True,
            'version': version,
            'pkg_dir': pkg_dir or ('<HOME>\\' + name),
            'accepted_at': '2026-11-15 00:00:00',
            'binding_gate': 'app191',
            'code_fingerprint': aggregate if aggregate is not None
            else h.hexdigest(),
            'code_fingerprints': fps if with_binding else {},
        }
        if accepted is False:
            acc['accepted'] = False
        with open(os.path.join(pkg, 'ACCEPTED.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(acc, f, ensure_ascii=False, indent=2)
    return pkg


def make_args(pkg, zip_path, prefix):
    class A(object):
        pass
    a = A()
    a.pkg = pkg
    a.zip = zip_path
    a.prefix = prefix
    a.dry_run = False
    a.same_version = True
    a.rename_pkg_dir = False
    a.no_shortcut = True          # 🔴 绝不动桌面快捷方式
    a.no_verify_content = True
    a.level = 1
    a.no_lock = True              # 🔴 本矩阵不跑设备作业
    a.lock_timeout = 1
    a.quiet_seconds = 0
    a.quiet_timeout = 1
    a.skip_quiet = True
    a.changelog_zh = None
    a.changelog_en = None
    a.self_test_acceptance = False
    a.version = FAKE_VER
    return a


def run_arm(ns, pkg, td, tag):
    """在假包上真跑该臂的 `_run()` ⇒ 返回 (rc, 是否产出 zip, stdout 摘要)。"""
    zip_path = os.path.join(td, 'out_%s.zip' % tag)
    prefix = 'Confucius4_LiveCaption_v%s' % FAKE_VER
    args = make_args(pkg, zip_path, prefix)
    import io
    import contextlib
    buf = io.StringIO()
    rc = None
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            rc = ns['_run'](args)
    except SystemExit as e:
        rc = e.code
    except Exception as e:                       # pragma: no cover
        err = repr(e)
    out = buf.getvalue()
    reason = None
    for line in out.splitlines():
        if '验收绑定闸门未通过：' in line:
            reason = line.split('验收绑定闸门未通过：', 1)[1].strip()
            break
    return {
        'rc': rc,
        'error': err,
        'zip_created': os.path.isfile(zip_path),
        'zip_bytes': (os.path.getsize(zip_path)
                      if os.path.isfile(zip_path) else 0),
        'acceptance_reason': reason,
        'tail': out.strip().splitlines()[-6:],
    }


# ══════════════════════════════════════════════════════════════════════
# 矩阵
# ══════════════════════════════════════════════════════════════════════
def build_cases():
    """每个 case = (名称, 造包函数, 改后臂期望 blocked, 改前臂期望 blocked)。"""
    def c(name, expect_after, expect_before, builder):
        return {'case': name, 'expect_after_blocked': expect_after,
                'expect_before_blocked': expect_before, 'builder': builder}

    cases = [
        c('T1_no_accepted_marker', True, False,
          lambda td: make_fake_pkg(td, accepted=None)),
        c('T2_version_mismatch', True, False,
          lambda td: make_fake_pkg(td, version='8.8')),
        c('T3_code_changed_after_acceptance', True, False,
          lambda td: make_fake_pkg(td)),
        c('T4_valid_accepted', False, False,
          lambda td: make_fake_pkg(td)),
    ]
    return cases


def run_matrix(arm_ns, tag, cases):
    rows = []
    for case in cases:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            pkg = case['builder'](td)
            if case['case'] == 'T3_code_changed_after_acceptance':
                # 验收后**改一个字** ⇒ 内容绑定必须抓到
                with open(os.path.join(pkg, 'app', 'a.py'), 'w',
                          encoding='utf-8') as f:
                    f.write('x = 999\n')
            res = run_arm(arm_ns, pkg, td, tag)
            res['case'] = case['case']
            res['expect_after_blocked'] = case['expect_after_blocked']
            res['expect_before_blocked'] = case['expect_before_blocked']
            rows.append(res)
    return rows


def judge(rows, side):
    """`side` ∈ {'after','before'} ⇒ 按该臂的期望判定。"""
    npass = nfail = 0
    for r in rows:
        blocked = (r['rc'] != 0)
        expect = r['expect_%s_blocked' % side]
        ok = (blocked == expect)
        # 额外判据：**放行 ⇒ 必须真的产出了 zip**（行为级，不是看打印）
        if ok and not expect:
            ok = bool(r['zip_created'])
        r['%s_judge_pass' % side] = ok
        if ok:
            npass += 1
        else:
            nfail += 1
    return {'n_pass': npass, 'n_fail': nfail}


def real_pkg_readonly(after_ns):
    """C 腿：真包**只读**复验（零写入）。"""
    rows = []
    base = r'C:\Users\Trekker-PTL'
    for name in ('Confucius4_LiveCaption_v2.1',
                 'Confucius4_LiveCaption_v2.2',
                 'Confucius4_LiveCaption_v2.4'):
        pkg = os.path.join(base, name)
        if not os.path.isdir(pkg):
            rows.append({'pkg': name, 'skipped': 'NOT_PRESENT'})
            continue
        ver = name.rsplit('_v', 1)[-1]
        ok, reason, detail = after_ns['check_acceptance_binding'](pkg,
                                                                  expect_version=ver)
        rows.append({'pkg': name, 'blocked': (not ok), 'reason': reason,
                     'n_current': detail.get('n_current'),
                     'n_registered': detail.get('n_registered'),
                     'accepted_version': detail.get('accepted_version'),
                     'expect_pass': True})
    return rows


def real_pkg_mutation(after_ns):
    """C 腿：在真包的**临时副本**上改一个字 ⇒ 必须 BLOCK（真包零写入）。"""
    rows = []
    base = r'C:\Users\Trekker-PTL'
    src = os.path.join(base, 'Confucius4_LiveCaption_v2.1')
    if not os.path.isdir(src):
        return [{'skipped': 'NOT_PRESENT'}]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        dst = os.path.join(td, 'Confucius4_LiveCaption_v2.1')
        import shutil
        shutil.copytree(src, dst)
        ok0, reason0, d0 = after_ns['check_acceptance_binding'](dst,
                                                                expect_version='2.1')
        target = None
        app = os.path.join(dst, 'app')
        for fn in sorted(os.listdir(app)):
            if fn.endswith('.py'):
                target = os.path.join(app, fn)
                break
        changed = False
        if target:
            with open(target, 'a', encoding='utf-8') as f:
                f.write('# mutated by app571\n')
            changed = True
        ok1, reason1, d1 = after_ns['check_acceptance_binding'](dst,
                                                                expect_version='2.1')
        rows.append({
            'pkg': 'Confucius4_LiveCaption_v2.1 (临时副本)',
            'before_mutation_blocked': (not ok0), 'before_mutation_reason': reason0,
            'mutated_file': (os.path.basename(target) if target else None),
            'mutated': changed,
            'after_mutation_blocked': (not ok1), 'after_mutation_reason': reason1,
            'expect_before': 'PASS', 'expect_after': 'BLOCK',
            'pass': ((not ok0) is False) and ((not ok1) is True),
        })
    return rows


def selftest_judge():
    """**矩阵自己的反证组**（§204／§207 教训：「独立复核脚本自己也会判错」
    ⇒ **复核脚本也要跑反证组**；且「反证变异必须真的改坏被检的那部分」）。

    M1 判据把「本该拦却没拦」判成 PASS 吗？ ⇒ 必须判 FAIL
    M2 判据把「放行但没真的产出 zip」判成 PASS 吗？ ⇒ 必须判 FAIL
    M3 **把闸门废掉**（变异真的改坏 `check_acceptance_binding`）
       ⇒ 矩阵必须报 FAIL（证明矩阵**不是摆设**）
    """
    out = []

    def _case(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:                     # pragma: no cover
            ok, detail = False, repr(e)
        out.append({'case': name, 'pass': bool(ok), 'detail': detail})

    def _m1():
        rows = [{'case': 'x', 'rc': 0, 'zip_created': True,
                 'expect_after_blocked': True, 'expect_before_blocked': True}]
        j = judge(rows, 'after')
        return (j['n_fail'] == 1 and j['n_pass'] == 0, j)

    def _m2():
        rows = [{'case': 'x', 'rc': 0, 'zip_created': False,
                 'expect_after_blocked': False, 'expect_before_blocked': False}]
        j = judge(rows, 'after')
        return (j['n_fail'] == 1 and j['n_pass'] == 0, j)

    def _m3():
        src = worktree_bytes().decode('utf-8')
        target = "        return (False, 'NO_ACCEPTED', detail)"
        if src.count(target) != 1:
            return (False, {'error': '变异锚点命中 %d 次（变异无效 ⇒ 不能当反证）'
                             % src.count(target)})
        mutated = src.replace(target, "        return (True, 'OK', detail)")
        ns = build_arm(mutated.encode('utf-8'))
        rows = run_matrix(ns, 'mut', build_cases())
        j = judge(rows, 'after')
        # 闸门被废掉 ⇒ T1/T2/T3 不再被拦 ⇒ 矩阵必须判 FAIL
        return (j['n_fail'] >= 1 and j['n_pass'] < 4,
                {'judge': j,
                 'blocked_flags': [r['rc'] != 0 for r in rows],
                 'n_cases': len(rows)})

    _case('M1_should_block_but_allowed_is_judged_FAIL', _m1)
    _case('M2_allowed_without_zip_is_judged_FAIL', _m2)
    _case('M3_neutered_gate_makes_matrix_FAIL', _m3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--self-test-judge', action='store_true',
                    help='只跑矩阵自身的反证组（不跑矩阵本体）')
    args = ap.parse_args()

    if args.self_test_judge:
        rows = selftest_judge()
        bad = [r for r in rows if not r.get('pass')]
        for r in rows:
            print('  [%s] %-46s %s'
                  % ('PASS' if r.get('pass') else 'FAIL', r.get('case'),
                     json.dumps(r.get('detail'), ensure_ascii=False)[:160]))
        print('矩阵反证组：%d/%d PASS' % (len(rows) - len(bad), len(rows)))
        return 0 if not bad else 1

    before_src = head_blob_bytes()
    after_src = worktree_bytes()

    ev = {
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'script': os.path.relpath(os.path.abspath(__file__), REPO),
        'purpose': ('§208 完整版（pack_v13.py）出包闸门「验收绑定」的鉴别力矩阵；'
                    '改前臂 = HEAD 逐字原文，改后臂 = 工作区'),
        'discipline': ('零写客户包／不出正式 zip／交付指纹落盘打桩／'
                       '不跑推理／不取机器锁'),
        'arms': {
            'before': {'source': 'git cat-file blob %s:pack_v13.py' % BASE_REV,
                       'bytes': len(before_src),
                       'sha256': hashlib.sha256(before_src).hexdigest()},
            'after': {'source': '工作区 pack_v13.py',
                      'bytes': len(after_src),
                      'sha256': hashlib.sha256(after_src).hexdigest()},
        },
    }

    # ── B 腿 · AST 直读表 ──
    fn_b, gates_b = gates_in_run(before_src)
    fn_a, gates_a = gates_in_run(after_src)
    ev['ast'] = {
        'before_gates_in_run': gates_b,
        'after_gates_in_run': gates_a,
        'acceptance_touching_funcs_before': acceptance_touching_gates(before_src),
        'acceptance_touching_funcs_after': acceptance_touching_gates(after_src),
        'before_has_acceptance_gate': ('check_acceptance_binding' in gates_b),
        'after_has_acceptance_gate': ('check_acceptance_binding' in gates_a),
    }

    # ── A 腿 · 行为级真跑 ──
    cases = build_cases()
    before_ns = build_arm(before_src)
    after_ns = build_arm(after_src)
    before_rows = run_matrix(before_ns, 'before', cases)
    after_rows = run_matrix(after_ns, 'after', cases)
    ev['before_rows'] = before_rows
    ev['after_rows'] = after_rows
    ev['before_judge'] = judge(before_rows, 'before')
    ev['after_judge'] = judge(after_rows, 'after')

    # ── C 腿 · 真包只读复验 ──
    ev['real_pkg_readonly'] = real_pkg_readonly(after_ns)
    ev['real_pkg_mutation'] = real_pkg_mutation(after_ns)

    # ── 矩阵自身的反证组（写进证据 ⇒ 复核者不用重跑）──
    st_rows = selftest_judge()
    ev['judge_selftest'] = st_rows

    n_pass = (ev['after_judge']['n_pass'] + ev['before_judge']['n_pass'])
    n_fail = (ev['after_judge']['n_fail'] + ev['before_judge']['n_fail'])
    for r in st_rows:
        if r.get('pass'):
            n_pass += 1
        else:
            n_fail += 1
    for r in ev['real_pkg_readonly']:
        if r.get('skipped'):
            continue
        if r.get('blocked'):
            n_fail += 1
        else:
            n_pass += 1
    for r in ev['real_pkg_mutation']:
        if r.get('skipped'):
            continue
        if r.get('pass'):
            n_pass += 1
        else:
            n_fail += 1
    ev['n_pass'] = n_pass
    ev['n_fail'] = n_fail
    ev['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print(json.dumps({'out': args.out, 'n_pass': n_pass, 'n_fail': n_fail,
                      'verdict': ev['verdict'],
                      'before_judge': ev['before_judge'],
                      'after_judge': ev['after_judge']},
                     ensure_ascii=False, indent=2))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
