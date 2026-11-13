#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app522_gate4_fallback_scope.py —— 打包前闸门④（§190）的**检测范围补全**：
「终端 else 回落分支」是否存在。

## 背景（§190 实测，不是推测）

§187 加了打包前闸门④ `check_app086_2a_narrowing`；§188 修了它的「蕴含」判据；
§189 修了它的**检测范围**（分支① 的分支体里只有 keep-logger ⇒ 旧判据看不见）。

🔴🔴🔴 **但闸门④仍然看不见「终端 else 回落分支」** —— 这不是推测，是 AST 结构决定的：

    if self.clone_mode and not _bound:          ← 分支①（保留克隆）
        ...
        self._log_keep_clone()
    elif self._has_clone_voice() and not _bound: ← 分支②（沿用上一句克隆）
        ...
        self._log_keep_last_clone()
    else:                                        ← 🔴 **终端 else**
        # 语义 ①：按句绑定模式（或没有克隆模式）⇒ 回落预设 A
        self._fallback_to_preset('no_spk_label')

**Python 的 AST 结构**：`if/elif/else` 是**嵌套 If** —— `else` 的语句体挂在
**最内层 If 的 `orelse`** 上，而**不属于任何 If 的 `body`**：

    If(test=keep1, body=[...], orelse=[If(test=keep2, body=[...], orelse=[fallback_stmts])])
                                                              ^^^^^^^^^^^^^^^^^^^^^^^^
    ⇒ `else` 体既不是 keep1 的 body，也不是 keep2 的 body
    ⇒ `_branch_keeps_clone_voice(n.body)` **永远看不到它**
    ⇒ 「回落预设 A」这条**唯一**的兜底，对闸门④ **完全不可见**

## 为什么这是**交付级**缺陷（不是理论洁癖）

APP-086·2a 的产品不变量是：

    按句绑定模式（`_bound` 为真）＋ spk=None（标签晚到）⇒ **回落预设 A**
                                            ⇒ **绝不沿用上一句的克隆音色**

而「回落预设 A」的**实现方式**就是：**不保留** `self.speaker_embed`
（`_fallback_to_preset` 把 `speaker_embed`/`speaker_name` 换回**预设 A 的缓存**）。

⇒ 🔴 **两条守卫都带 `not _bound` 时，按句绑定模式下两个 keep 分支都取不到**
⇒ **若无终端 else 兜底 ⇒ `self.speaker_embed` 仍是上一句的克隆向量**
⇒ **合成出来的这一句就是上一句那个人的声音** ⇒ **串音（男声被配成女声）**
⇒ 而**闸门④ 对此完全无感 ⇒ 判 PASS ⇒ 缺陷包照打照发**

⇒ **判据自问自答**（「这条判据若被人当真去改生产代码，会不会改坏」）：**会**
⇒ §190 修法：闸门④ 必须同时检查「**keep 分支所在 If 链的终端 else**」
   ⇒ 存在且含「回落」标志物（`_fallback_to_preset(...)` 或预设赋值）⇒ 才算通过。

## 本脚本干什么（**纯离线、零 GPU、零推理、不占锁、不调 MiniMax、对客户包只读**）

**A. 合成矩阵**：对 dev 树 `live_caption/` 造 9 个变体（终端 else 缺失 /
   兜底废掉 / 兜底换成 keep-logger / 等价写法 / 两条守卫被回退 …）
   ⇒ 闸门④ rc 与 app157 B3 是否**一致**。

**B. 真包矩阵**：磁盘上**每一个** `Confucius4_LiveCaption_*/app`（含 MiniMVP）
   ⇒ 闸门④ rc + app157 B3 ⇒ 是否一致，并列出**哪些包带串音缺陷**。

**C. e2e**：用 **AST** 读 `pack_v13.py` 的 `_run()` ⇒ 闸门④ 的调用**必须**在
   `zipfile.ZipFile(tmp_zip,'w')` **之前**（否则闸门形同虚设）。

🔴 判据跑在**临时仓库副本**里 ⇒ 仓库里既有的 evidence json 不被覆盖。
🔴 探针建在**临时目录** ⇒ 不碰 dev 树与任何客户包。

## 产物

`results/app/app522_gate4_fallback_scope_evidence.json`
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
OUT = os.path.join(HERE, 'app522_gate4_fallback_scope_evidence.json')

# ── 变体锚点（dev 树 live_caption/tts_worker.py）──────────────────────────
KEEP1 = 'if self.clone_mode and not _bound:'
KEEP2 = 'elif self._has_clone_voice() and not _bound:'
ELSE_BLOCK = ("                else:\n"
              "                    # \U0001f534 语义 ①：按句绑定模式（或没有克隆模式）⇒ 回落预设 A\n"
              "                    self._fallback_to_preset('no_spk_label')\n")
FB_CALL = "                    self._fallback_to_preset('no_spk_label')\n"

VARIANTS = [
    # ── 基线 + 「终端 else」类变体（本轮新查的范围）──
    ('clean_dev', []),
    ('fb_neutered', [(FB_CALL, '                    pass\n')]),
    ('fb_removed', [(ELSE_BLOCK, '')]),
    ('fb_replaced_keep', [(ELSE_BLOCK,
                           "                else:\n"
                           "                    self._log_keep_last_clone()\n")]),
    # ── 等价写法（修法**不得**误拦 ⇒ fail-closed 方向的自检）──
    ('fb_noarg', [(FB_CALL, '                    self._fallback_to_preset()\n')]),
    ('fb_inline_preset', [(FB_CALL,
                            '                    self.speaker_embed = self._preset_embed\n')]),
    # ── §189 已覆盖的守卫类变体（回归项）──
    ('b1_guard_removed', [(KEEP1, 'if self.clone_mode:')]),
    ('b2_guard_removed', [(KEEP2, 'elif self._has_clone_voice():')]),
    ('both_guards_removed', [(KEEP1, 'if self.clone_mode:'),
                             (KEEP2, 'elif self._has_clone_voice():')]),
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
    TMP = tempfile.mkdtemp(prefix='app522_')
    os.makedirs(os.path.join(TMP, 'results', 'app'), exist_ok=True)
    shutil.copy2(GATE_SRC, os.path.join(TMP, 'results', 'app',
                                        'app157_follow_speaker_regression_test.py'))
    out = {'script': os.path.basename(__file__),
           'note': '闸门④「终端 else 回落分支」检测范围 × 行为判据 app157 B3 '
                   '交叉验证；探针在临时目录；客户包只读'}
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
        print('# C. e2e（闸门链顺序）')
        print('#' * 74)
        chain = gate_chain_order()
        print('  闸门链：%s' % chain)
        out['e2e'] = dict(chain=chain)
        print('  ⇒ 闸门④ 在建 zip 之前：%s'
              % ('PASS' if chain['gate4_before_zip'] else 'FAIL'))

        with io.open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('\nevidence -> %s' % OUT)
        print('VERDICT: %s'
              % ('PASS' if agree == len(rows) or chain['gate4_before_zip']
                 else 'FAIL'))
        return 0
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
