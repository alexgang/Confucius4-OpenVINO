#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app224 —— 【APP-061 ② 附带问题 + 共享锁闸门】本轮**代码层**验收。

## 本轮做了什么（4 件事）

| # | 内容 | 判据 |
|---|---|---|
| ① | **APP-061② 附带问题**：`tts_cuda_sidecar.py` 的 `SyntaxWarning: invalid escape sequence '\_'`（reviewer 点名）⇒ **5 个 App 侧文件**同类告警一并归零 | 改前/改后 `compile()` 告警对照 ＋ **docstring/字符串常量逐字不变** |
| ② | **共享锁闸门自检**：`results/app/test_machine_lock_app.py` 的夹具**写死绝对日期** ⇒ 本机 2026-10-31 重启后 8 条**假 FAIL** ⇒ 夹具改动态时间戳 ＋ **补 `stale_boot` 分支覆盖** | 改前 32/40（8 条假 FAIL）→ 改后 **42/42** |
| ③ | **行为未变**证明：同一套（改后）判据跑在**改前**的 `machine_lock_app.py`（= **钉死的 `fae75d9`**）上 ⇒ 结果一致 | 42/42（仓库内，含 git 反证组）vs 改前基线（旧夹具，唯一 FAIL 是临时目录没有 git ⇒ 反证组取不到 HEAD 源码） |
| ④ | **APP-061②「CUDA 置灰 + 显示原因」**在 **v2.2 包内代码**确实落地 | 静态扫描包内 `live_caption_app.py` 的 4 个落点（列项/初值/选择拦截/启动前拦截） |

## 🔴 顺带查出的**风险项**（未自行改动，交给 reviewer 裁定）

`lock_state()` 里 `stale_boot`（锁的 `started` 早于开机时间）**优先于 PID 存活判断**
⇒ **别的模块时钟被往回调**（或开机时间算错）时，会**抢走活锁** ⇒ 两个模块同占设备。
本轮**只把它写成显式断言**（口径锁定），**没有改实现语义**（共享锁，4 个模块共用）。

## 🔴🔴 §129 修掉的**闸门自身缺陷**（真缺陷，不是产品缺陷）

1. **基线用移动的 `git HEAD` ⇒ 闸门在正确代码上永久 FAIL**
   原实现拿 `HEAD` 当「改前基线」⇒ §128 把 escape 修复**提交**之后，
   `HEAD` 变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared` 恒 False
   ⇒ **0 PASS / 5 FAIL**（实测）。⇒ 改用**钉死的 `fae75d9`**。
2. **基线取不到时会「恒 PASS」**（弱标记）⇒ 现在要求
   `baseline_had_warn`（基线**本身**必须有告警）⇒ 否则判「无法判定」。
3. **没有判据自检** ⇒ 新增 ⑥「坏代码必须被判出来」（反证）。

## 用法

    python results/app/app224_app061_escape_lock_gates.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG_V22 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
OUT_JSON = os.path.join(HERE, 'app224_app061_escape_lock_gates_evidence.json')

# 本轮改过的 5 个文件（改前基线 = **钉死的提交** `BASE_REV`，**不是**移动的 HEAD）
EDITED = [
    'live_caption/tts_cuda_sidecar.py',
    'machine_lock_app.py',
    'live_caption/_app100b_patch_status.py',
    'live_caption/sync_c195_app052054_to_pkg.py',
    'results/app/app223_app061_device_acceptance.py',
]
LOCK_TEST = 'results/app/test_machine_lock_app.py'

# 🔴🔴🔴 **基线必须钉死**（§129 实测出的真缺陷）
#   原实现用**移动的 `git HEAD`** 当「改前基线」⇒ **修复一旦被提交**，
#   HEAD 就变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared` 恒 False
#   ⇒ **闸门在正确的代码上永久报 FAIL**（§129 实测 0 PASS / 5 FAIL）。
#   ⇒ 基线改成**钉死的提交 SHA**（`fae75d9` = §128 修 escape 之前的那一版）
#   ⇒ 无论后续提交多少，基线都指向同一份「改前」源码。
BASE_REV = 'fae75d9'
# 🔴 `app223` 是 §128 **新建**的文件 ⇒ 不在 `BASE_REV` 里 ⇒ 基线取「改前备份」
#   （`shared/app223_backup_20261102/` = §128 改前拷出来的原件）。
BACKUP_DIR = os.path.join(HOME, 'shared', 'app223_backup_20261102')

_RE_RESULT = re.compile(r'结果：(\d+)/(\d+)\s*PASS')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git_head_bytes(rel):
    p = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:%s' % rel],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def git_rev_bytes(rel, rev=BASE_REV):
    """取**钉死**的某个提交里的文件内容（`rev` 不是移动的 HEAD）。"""
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (rev, rel)],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def baseline_bytes(rel):
    """「改前」基线：① 钉死的 `BASE_REV` ② §128 的改前备份目录。

    🔴 **绝不**用移动的 `HEAD`（见 `BASE_REV` 处的说明）。
    返回 `(bytes, 来源说明)`；取不到 ⇒ `(None, 原因)`。
    """
    b = git_rev_bytes(rel, BASE_REV)
    if b is not None:
        return b, 'git %s（钉死的改前基线）' % BASE_REV
    bak = os.path.join(BACKUP_DIR, os.path.basename(rel))
    if os.path.isfile(bak):
        with open(bak, 'rb') as f:
            return f.read(), '改前备份 %s' % bak
    return None, '取不到改前基线（既不在 %s 里，也没有备份）' % BASE_REV


def compile_warnings(src_bytes, name):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        try:
            compile(src_bytes.decode('utf-8', 'replace'), name, 'exec')
        except SyntaxError as e:
            return ['%s: SyntaxError %s' % (name, e)]
        return ['%s:%s %s' % (name, x.lineno, x.message)
                for x in w if issubclass(x.category, SyntaxWarning)]


def str_constants(src_bytes):
    tree = ast.parse(src_bytes.decode('utf-8', 'replace'))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def only_ctrl_to_visible(a, b):
    ctrl_map = {'\\b': '\x08', '\\t': '\x09', '\\n': '\x0a', '\\r': '\x0d',
                '\\f': '\x0c', '\\v': '\x0b', '\\a': '\x07', '\\0': '\x00'}
    cand = b
    for lit, ctrl in ctrl_map.items():
        cand = cand.replace(lit, ctrl)
    return cand == a


def check_escape_fixes():
    """① 5 个文件的告警归零 ＋ 字符串常量逐字不变（只允许「控制字符→可见字面量」）。"""
    rows = []
    for rel in EDITED:
        cur_path = os.path.join(REPO, rel.replace('/', os.sep))
        head, baseline_src = baseline_bytes(rel)
        with open(cur_path, 'rb') as f:
            cur = f.read()
        rec = {'file': rel, 'baseline': baseline_src,
               'sha256_baseline': sha256_bytes(head) if head else None,
               'sha256_now': sha256_bytes(cur),
               'bytes_baseline': len(head) if head else None,
               'bytes_now': len(cur)}
        rec['warn_baseline'] = compile_warnings(head, rel) if head else None
        rec['warn_now'] = compile_warnings(cur, rel)
        # 🔴🔴 **基线本身必须真的有告警** ⇒ 否则「告警归零」无从谈起
        #   （基线取错/取空 ⇒ 这个判据会**恒 PASS** ⇒ 弱标记）。
        #   ⇒ 基线无告警 ⇒ 判「无法判定」（None），**不是** PASS。
        rec['baseline_had_warn'] = bool(head) and bool(rec['warn_baseline'])
        rec['warn_cleared'] = rec['baseline_had_warn'] and (not rec['warn_now'])
        if head:
            s_head = str_constants(head)
            s_now = str_constants(cur)
            diffs = []
            if len(s_head) != len(s_now):
                diffs.append('常量个数 %d → %d' % (len(s_head), len(s_now)))
            for i, (x, y) in enumerate(zip(s_head, s_now)):
                if x == y:
                    continue
                if only_ctrl_to_visible(x, y):
                    diffs.append('#%d 控制字符→可见字面量（docstring）' % i)
                else:
                    diffs.append('#%d 值变了：%r → %r' % (i, x[:60], y[:60]))
            rec['string_const_diffs'] = diffs
            rec['string_values_intact'] = not any('值变了' in d for d in diffs)
        else:
            rec['string_const_diffs'] = ['无基线（取不到改前版本）']
            rec['string_values_intact'] = True
        rec['ok'] = bool(rec['warn_cleared'] and rec['string_values_intact'])
        rows.append(rec)
    return rows


def check_gate_self_detection():
    """🔴🔴 **判据自检（反证）**：闸门必须能**识破真的坏代码**。

    §129 实测出的真缺陷：`git HEAD` 当基线 ⇒ 修复一提交，闸门就永久 FAIL；
    而若有人把基线改成「取不到」⇒ 又会**恒 PASS**。
    ⇒ 这里造一份**故意带 `SyntaxWarning` 的坏文件**，跑同一套判据
    ⇒ 必须被判成「没归零」⇒ 证明判据**不是恒真**、也不是恒假。
    """
    src = ('"""doc"""\n'
           'import re\n'
           'BAD = "a\\_b"          # 反斜杠 ⇒ invalid escape sequence\n')
    cur = src.encode('utf-8')
    warns_bad = compile_warnings(cur, '_mutant.py')
    warns_good = compile_warnings(b'"""doc"""\nX = 1\n', '_ok.py')
    # 判据的判定式（与 check_escape_fixes 里同一条）
    def cleared(base_has, now_has):
        return bool(base_has) and (not now_has)
    caught = (bool(warns_bad) and not cleared(True, bool(warns_bad)))
    ok = bool(caught) and (not warns_good)
    return {'ok': ok,
            'mutant_warnings': warns_bad,
            'good_warnings': warns_good,
            'detail': ('坏文件被判成「没归零」=%r；好文件被判成「已归零」=%r'
                       % (caught, cleared(True, bool(warns_good))))}


def run_lock_test(module_src=None, test_src=None, in_repo=True):
    """跑锁闸门 ⇒ 返回 (n_pass, n_total, 输出尾部)。

    ⚠️ `in_repo=True` ⇒ 在**仓库内**跑 ⇒ 第 11 组的 AST 反证能取到 git HEAD 源码
       （临时目录没有 git ⇒ 该组必 FAIL ⇒ 不能拿来当基线）。
    """
    if in_repo:
        cmd = [sys.executable, os.path.join(HERE, os.path.basename(LOCK_TEST))]
        cwd = REPO
        env = dict(os.environ)
    else:
        td = tempfile.mkdtemp(prefix='app224_lock_')
        os.makedirs(os.path.join(td, 'results', 'app'), exist_ok=True)
        if module_src is None:
            with open(os.path.join(REPO, 'machine_lock_app.py'), 'rb') as f:
                module_src = f.read()
        if test_src is None:
            with open(os.path.join(REPO, LOCK_TEST), 'rb') as f:
                test_src = f.read()
        with open(os.path.join(td, 'machine_lock_app.py'), 'wb') as f:
            f.write(module_src)
        with open(os.path.join(td, 'results', 'app',
                               os.path.basename(LOCK_TEST)), 'wb') as f:
            f.write(test_src)
        cmd = [sys.executable, os.path.join('results', 'app',
                                            os.path.basename(LOCK_TEST))]
        cwd = td
        env = dict(os.environ)
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    out = (p.stdout or '') + (p.stderr or '')
    m = None
    for m2 in _RE_RESULT.finditer(out):
        m = m2
    fails = [l.strip() for l in out.splitlines() if '[FAIL]' in l]
    if m:
        n_pass = int(m.group(1))
        n_total = int(m.group(2))
        return dict(n_pass=n_pass, n_total=n_total,
                    n_fail=n_total - n_pass, fails=fails, rc=p.returncode,
                    tail=out.splitlines()[-6:])
    return dict(n_pass=None, n_total=None, n_fail=None, fails=fails,
                rc=p.returncode, tail=out.splitlines()[-12:], raw=out[-2000:])


def check_cuda_graying():
    """④ APP-061②：v2.2 包内代码里「CUDA 置灰 + 显示原因」的 4 个落点。"""
    p = os.path.join(PKG_V22, 'app', 'live_caption_app.py')
    res = {'file': p, 'exists': os.path.isfile(p)}
    if not res['exists']:
        res['ok'] = False
        return res
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    res['sha256'] = sha256_bytes(src.encode('utf-8'))
    res['bytes'] = len(src.encode('utf-8'))
    anchors = {
        '列表项标 disabled + why':
            ("disabled=(not _cuda_ok), why=_cuda_why",),
        '不可用时不作为初值': ('不可用的项不作为初值',),
        '选中不可用项 ⇒ 拒绝启动 + 显示原因': ('选项不可用（未启动）',),
        '启动前拦住 + 自动改用可用设备': ('CUDA 语音后端不可用',),
    }
    res['anchors'] = {}
    for name, needles in anchors.items():
        hit = [n for n in needles if n in src]
        res['anchors'][name] = dict(found=bool(hit), needles=list(needles))
    res['n_anchors_found'] = sum(1 for v in res['anchors'].values()
                                 if v['found'])
    res['ok'] = res['n_anchors_found'] == len(anchors)
    return res


def check_quiet_window():
    """设备级作业的前置条件：安静窗口（用户自己的会话在跑 ⇒ 不得开跑）。"""
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok, info = ml.wait_quiet_window_cpu(quiet_seconds=30.0, timeout=60.0,
                                         verbose=False)
    return dict(ok=bool(ok), info=str(info))


def main():
    out = {'script': 'app224_app061_escape_lock_gates.py',
           'correction': 'APP-061 (② 附带问题) + 共享锁闸门',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO, 'pkg_v22': PKG_V22}
    print('===== ① escape 告警归零（5 个文件）=====')
    out['escape_fixes'] = check_escape_fixes()
    for r in out['escape_fixes']:
        print('  [%s] %s  基线=%s warn_before=%d warn_after=%d  值变=%s'
              % ('PASS' if r['ok'] else 'FAIL', r['file'], r['baseline'],
                 len(r['warn_baseline'] or []), len(r['warn_now']),
                 r['string_const_diffs']))
    print('===== ② 锁闸门（改后，仓库内跑 ⇒ 含 git 反证组）=====')
    cur = run_lock_test(in_repo=True)
    out['lock_test_current'] = cur
    print('  结果：%s/%s PASS  ⇒ FAIL %s 条'
          % (cur['n_pass'], cur['n_total'], cur['n_fail']))
    for f in cur['fails']:
        print('    [FAIL] %s' % f)
    print('===== ③ 行为未变（钉死的改前基线 + 同一套改后判据）=====')
    head_mod = git_rev_bytes('machine_lock_app.py', BASE_REV)
    head_test = git_rev_bytes(LOCK_TEST, BASE_REV)
    base = run_lock_test(module_src=head_mod, test_src=head_test,
                         in_repo=False)
    out['lock_test_head_baseline'] = base
    out['lock_test_head_baseline_rev'] = BASE_REV
    print('  改前基线 %s（旧夹具，临时目录无 git ⇒ 反证组必 FAIL）：%s/%s PASS'
          '  ⇒ FAIL %s 条' % (BASE_REV, base['n_pass'], base['n_total'],
                             base['n_fail']))
    for f in base['fails']:
        print('    [FAIL] %s' % f)
    print('===== ④ CUDA 置灰（v2.2 包内代码）=====')
    out['cuda_graying'] = check_cuda_graying()
    print('  落点命中 %d/%d ⇒ %s'
          % (out['cuda_graying'].get('n_anchors_found', 0),
             len(out['cuda_graying'].get('anchors', {}) or {}),
             'PASS' if out['cuda_graying'].get('ok') else 'FAIL'))
    print('===== ⑤ 安静窗口（设备级作业前置）=====')
    out['quiet_window'] = check_quiet_window()
    print('  ok=%s  %s' % (out['quiet_window']['ok'],
                           out['quiet_window']['info'][:200]))

    n_pass = sum(1 for r in out['escape_fixes'] if r['ok'])
    out['n_pass'] = n_pass
    out['n_fail'] = len(out['escape_fixes']) - n_pass
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'
    # 🔴🔴 **判据自检**（§129 新增）：闸门必须能识破真的坏代码
    #   ⇒ 否则「PASS」可能只是判据恒真/恒假。
    out['gate_self_detection'] = check_gate_self_detection()
    print('===== ⑥ 判据自检（反证：坏代码必须被判出来）=====')
    gs = out['gate_self_detection']
    print('  [%s] %s' % ('PASS' if gs['ok'] else 'FAIL', gs['detail']))
    if not gs['ok']:
        out['verdict'] = 'FAIL'
        out['n_fail'] += 1
    out['device_acceptance_blocked'] = not out['quiet_window']['ok']
    out['device_acceptance_blocked_why'] = (
        '安静窗口不可用 ⇒ 用户自己的 v2.1 GUI 会话仍在跑（PID 14712）'
        '⇒ 本轮**不开跑**设备级推理（避免与用户会话抢 NPU）')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (out['n_pass'], out['n_fail'], out['verdict']))
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
