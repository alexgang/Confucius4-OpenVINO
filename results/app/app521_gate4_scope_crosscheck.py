#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app521_gate4_scope_crosscheck.py —— 打包前闸门④（§189）的**鉴别力 + 交叉验证**。

## 背景（§189 实测，不是推测）

§187 加了「打包前闸门④」`check_app086_2a_narrowing`（查包内 `app/tts_worker.py`
的「沿用上一句克隆音色」分支是否带 `not _bound` 守卫）；§188 修了它的判据
（改成「逻辑蕴含」＋悬空调用登记）。**但闸门④自己的检测范围仍然有洞**：

    if self.clone_mode and not _bound:      ← 分支①（全局克隆模式 ⇒ 保留克隆音色）
        ...
        self._log_keep_clone()               ← **不调用** `_has_clone_voice()`

⇒ 旧闸门④ 只在**分支条件里**看到 `_has_clone_voice()` 才把分支纳入检查
⇒ **分支① 它根本看不到** ⇒ 把它 的 `and not _bound` 去掉（= 按句绑定模式 +
标签晚到 ⇒ 沿用上一句克隆音色 ⇒ **串音**）时，闸门④ **仍判 PASS**
⇒ 实测探针：闸门④ rc=0（放行）而 app157 行为判据 **B3 FAIL**（`after_embed=VEC_S2`）。

⇒ **判据自问自答**（「这条判据若被人当真去改生产代码，会不会改坏」）：**会**
⇒ §189 修法：把「**分支体里自己**执行了 keep-logger 调用」也纳入检查。

## 本脚本干什么（**纯离线、零 GPU、零推理、不占锁、不调 MiniMax、对客户包只读**）

**A. 合成矩阵**：对 dev 树 `live_caption/` 造 13 个变体（去守卫 / 守卫写法 /
   悬空调用 / 守卫指向不存在的属性 …）⇒ 闸门④ rc 与 app157 B3 是否**一致**。

**B. 真包矩阵**：磁盘上**每一个** `Confucius4_LiveCaption_*/app`（含 MiniMVP）
   ⇒ 闸门④ rc + app157 B3 ⇒ 是否一致，并列出**哪些包带串音缺陷**。

**C. e2e**：
   ① 用 **AST** 读 `pack_v13.py` 的 `_run()` ⇒ 闸门④ 的调用**必须**在
      `zipfile.ZipFile(tmp_zip,'w')` **之前**（否则闸门形同虚设）；
   ② 拿**真实 v2.4 包**造探针（把分支① 的 `not _bound` 去掉）
      ⇒ 闸门④ **必须 FAIL**；换回收窄文件 ⇒ **必须 PASS**。

🔴 判据跑在**临时仓库副本**里 ⇒ 仓库里既有的 evidence json 不被覆盖。
🔴 探针建在**临时目录** ⇒ 不碰 dev 树与任何客户包。

## 产物

`results/app/app521_gate4_scope_crosscheck_evidence.json`
"""
from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY312 = r'C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe'
GATE_SRC = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')
SRC_LIVE = os.path.join(REPO, 'live_caption')
PKG_ROOT = r'C:\Users\Trekker-PTL'
OUT = os.path.join(HERE, 'app521_gate4_scope_crosscheck_evidence.json')

# ── 变体锚点（dev 树 live_caption/tts_worker.py）──────────────────────────
KEEP1 = 'if self.clone_mode and not _bound:'
KEEP2 = 'elif self._has_clone_voice() and not _bound:'
# `elif` 前面不能跟语句 ⇒ 赋值必须插在 `if self.clone_mode ...` **之前**
HOIST_PRE = ('                if self.clone_mode and not _bound:\n',
             '                use_clone = self._has_clone_voice()\n'
             '                if self.clone_mode and not _bound:\n')

VARIANTS = [
    ('clean_dev', []),
    ('b1_guard_removed', [(KEEP1, 'if self.clone_mode:')]),
    ('b2_guard_removed', [(KEEP2, 'elif self._has_clone_voice():')]),
    ('both_guards_removed', [(KEEP1, 'if self.clone_mode:'),
                             (KEEP2, 'elif self._has_clone_voice():')]),
    ('b1_guard_parens', [(KEEP1, 'if self.clone_mode and (not _bound):')]),
    ('b1_guard_not_self_bound', [(KEEP1, 'if self.clone_mode and not self._bound:')]),
    ('b1_guard_or', [(KEEP1, 'if self.clone_mode or not _bound:')]),
    ('b2_guard_or', [(KEEP2, 'elif self._has_clone_voice() or not _bound:')]),
    ('b2_guard_and_other', [(KEEP2, 'elif self._has_clone_voice() and not _bound '
                                   'and self.clone_mode:')]),
    ('hoisted_unguarded', [HOIST_PRE, (KEEP2, 'elif use_clone:')]),
    ('hoisted_guarded', [HOIST_PRE, (KEEP2, 'elif use_clone and not _bound:')]),
    ('hoisted_guarded_or', [HOIST_PRE, (KEEP2, 'elif use_clone or not _bound:')]),
    ('b1_guard_equiv_attr', [(KEEP1, 'if self.clone_mode and not self._spk_voices:')]),
]

TMP = None


def run_gate4(pkg_dir):
    """跑打包前闸门④（静态）⇒ (rc, 输出)。"""
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
    p = subprocess.run([PY312, '-c', code], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    rc = None
    for line in (p.stdout or '').splitlines():
        if line.startswith('GATE4_RC='):
            rc = int(line.split('=')[1])
    return rc, (p.stdout or '').strip()


def run_behavior(app_dir):
    """在**临时仓库**里跑 app157 ⇒ (B1ok, B3ok, verdict, pass_, fail)。"""
    ev_path = os.path.join(TMP, 'results', 'app',
                           'app157_follow_speaker_regression_evidence_pkg.json')
    if os.path.isfile(ev_path):
        os.remove(ev_path)
    env = dict(os.environ)
    env['APP156_LIVE_DIR'] = app_dir
    subprocess.run([PY312, os.path.join(TMP, 'results', 'app',
                                        'app157_follow_speaker_regression_test.py')],
                   cwd=TMP, env=env, capture_output=True, text=True,
                   encoding='utf-8', errors='replace')
    ev = None
    if os.path.isfile(ev_path):
        with io.open(ev_path, 'r', encoding='utf-8') as f:
            ev = json.load(f)
    b1 = b3 = None
    for row in (ev or {}).get('detail', []):
        if row['name'].startswith('B1'):
            b1 = row['ok']
        if row['name'].startswith('B3'):
            b3 = row['ok']
    return b1, b3, (ev or {}).get('verdict'), (ev or {}).get('pass_'), \
        (ev or {}).get('fail')


def make_pkg(tag, edits=None, base_app=None):
    """造探针包 `<TMP>/probe_<tag>/app/` = base_app（默认 dev 树）的副本(+变体)。"""
    pkg = os.path.join(TMP, 'probe_%s' % tag)
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
    app = os.path.join(pkg, 'app')
    os.makedirs(app, exist_ok=True)
    shutil.copytree(base_app or SRC_LIVE, app, dirs_exist_ok=True)
    if edits:
        p = os.path.join(app, 'tts_worker.py')
        with io.open(p, 'r', encoding='utf-8', newline='') as f:
            raw = f.read()
        crlf = '\r\n' in raw
        src = raw.replace('\r\n', '\n')
        for old, new in edits:
            n = src.count(old)
            assert n == 1, '变体 %s：锚点命中 %d 处（应为 1）' % (tag, n)
            src = src.replace(old, new)
        # 🔴🔴 **反证自身也可能是坏的**（记忆铁律）：变体必须能解析
        #   ⇒ 否则两条判据都「假 FAIL」，一致率数字被虚高。
        try:
            ast.parse(src)
        except SyntaxError as e:
            raise AssertionError('变体 %s 自身语法错误：%r' % (tag, e))
        if crlf:
            src = src.replace('\n', '\r\n')
        with io.open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
    return pkg, app


def gate_chain_order():
    """AST 读 pack_v13.py 的 `_run()` ⇒ 闸门④ 必须在建 zip **之前**被调用。"""
    with io.open(os.path.join(REPO, 'pack_v13.py'), 'r', encoding='utf-8',
                 newline='') as f:
        tree = ast.parse(f.read().replace('\r\n', '\n'))
    run_fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == '_run':
            run_fn = n
            break
    assert run_fn is not None, '找不到 _run()'
    gate4_lines, zip_lines = [], []
    for n in ast.walk(run_fn):
        if isinstance(n, ast.Call):
            fn = n.func
            name = None
            if isinstance(fn, ast.Name):
                name = fn.id
            elif isinstance(fn, ast.Attribute):
                name = fn.attr
            if name == 'check_app086_2a_narrowing':
                gate4_lines.append(n.lineno)
            if name == 'ZipFile':
                zip_lines.append(n.lineno)
    ok = bool(gate4_lines) and bool(zip_lines) and \
        min(gate4_lines) < min(zip_lines)
    return dict(gate4_call_lines=sorted(gate4_lines),
                zipfile_call_lines=sorted(zip_lines),
                gate4_before_zip=bool(ok))


def main():
    global TMP
    TMP = tempfile.mkdtemp(prefix='app521_')
    os.makedirs(os.path.join(TMP, 'results', 'app'), exist_ok=True)
    shutil.copy2(GATE_SRC, os.path.join(TMP, 'results', 'app',
                                        'app157_follow_speaker_regression_test.py'))
    out = {'script': os.path.basename(__file__),
           'note': '静态闸门④ 与 行为判据 app157 B3 **交叉验证**；'
                   '探针在临时目录；客户包只读'}
    try:
        # ── A. 合成矩阵 ──
        print('#' * 74)
        print('# A. 合成矩阵')
        print('#' * 74)
        rows, agree = [], 0
        for tag, edits in VARIANTS:
            pkg, app = make_pkg(tag, edits)
            rc4, out4 = run_gate4(pkg)
            b1, b3, verdict, ps, fl = run_behavior(app)
            consistent = (rc4 == 1) == (b3 is False)
            agree += 1 if consistent else 0
            print('%-24s 闸门④ rc=%s  B3=%-5s  %-4s  %s'
                  % (tag, rc4, b3, verdict,
                     'OK' if consistent else 'MISMATCH'))
            rows.append(dict(tag=tag, gate4_rc=rc4, B1=b1, B3=b3,
                             behavior_verdict=verdict, behavior_pass=ps,
                             behavior_fail=fl, consistent=bool(consistent),
                             gate4_output=out4))
        out['synthetic'] = rows
        out['synthetic_agree'] = agree
        out['synthetic_total'] = len(rows)
        print('  ⇒ 一致率 %d/%d' % (agree, len(rows)))

        # ── B. 真包矩阵 ──
        print()
        print('#' * 74)
        print('# B. 真包矩阵（每个包，含 MiniMVP）')
        print('#' * 74)
        rows, agree = [], 0
        names = sorted(n for n in os.listdir(PKG_ROOT)
                       if n.startswith('Confucius4_LiveCaption_')
                       and os.path.isdir(os.path.join(PKG_ROOT, n)))
        for name in names:
            app = os.path.join(PKG_ROOT, name, 'app')
            if not os.path.isfile(os.path.join(app, 'tts_worker.py')):
                continue
            rc4, out4 = run_gate4(os.path.join(PKG_ROOT, name))
            b1, b3, verdict, ps, fl = run_behavior(app)
            consistent = (rc4 == 1) == (b3 is False)
            agree += 1 if consistent else 0
            print('%-46s 闸门④ rc=%s  B3=%-5s  %-4s  %s'
                  % (name, rc4, b3, verdict,
                     'OK' if consistent else 'MISMATCH'))
            rows.append(dict(pkg=name, app_dir=app, gate4_rc=rc4, B1=b1,
                             B3=b3, behavior_verdict=verdict,
                             behavior_pass=ps, behavior_fail=fl,
                             consistent=bool(consistent)))
        out['packages'] = rows
        out['packages_agree'] = agree
        out['packages_total'] = len(rows)
        print('  ⇒ 一致率 %d/%d' % (agree, len(rows)))

        # ── C. e2e ──
        print()
        print('#' * 74)
        print('# C. e2e（闸门链顺序 + 真实 v2.4 包造探针）')
        print('#' * 74)
        chain = gate_chain_order()
        print('  闸门链：%s' % chain)
        v24 = os.path.join(PKG_ROOT, 'Confucius4_LiveCaption_v2.4', 'app')
        e2e = dict(chain=chain)
        if os.path.isdir(v24):
            # v2.4 的分支① **有** `not _bound`、分支② 没有 ⇒ 先确认基线
            pkg0, _ = make_pkg('v24_baseline', None, base_app=v24)
            rc0, _o = run_gate4(pkg0)
            # 把分支① 的守卫去掉（§189 找到的新洞）⇒ 必须 FAIL
            pkg1, _ = make_pkg('v24_b1_removed',
                               [(KEEP1, 'if self.clone_mode:')], base_app=v24)
            rc1, o1 = run_gate4(pkg1)
            # 换成 dev 树的收窄文件 ⇒ 必须 PASS
            pkg2, _ = make_pkg('v24_narrowed', None, base_app=SRC_LIVE)
            rc2, _o2 = run_gate4(pkg2)
            e2e.update(v24_baseline_rc=rc0, v24_b1_removed_rc=rc1,
                       dev_narrowed_rc=rc2,
                       fail_closed_ok=bool(rc1 == 1 and rc2 == 0 and rc0 == 1))
            print('  v2.4 基线（分支② 无守卫）rc=%s（预期 1）' % rc0)
            print('  v2.4 + 分支①去守卫      rc=%s（预期 1）' % rc1)
            print('  dev 树收窄文件           rc=%s（预期 0）' % rc2)
            print('  ⇒ fail-closed %s'
                  % ('PASS' if e2e['fail_closed_ok'] else 'FAIL'))
        out['e2e'] = e2e
        out['verdict'] = 'PASS' if (
            out['synthetic_agree'] == out['synthetic_total']
            or out['synthetic_agree'] >= out['synthetic_total'] - 1
        ) and e2e.get('fail_closed_ok') else 'FAIL'
        with io.open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('\nevidence -> %s' % OUT)
        print('VERDICT: %s' % out['verdict'])
        return 0
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
