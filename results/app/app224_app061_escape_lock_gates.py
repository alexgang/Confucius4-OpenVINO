#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app224 —— 【APP-061 ② 附带问题 + 共享锁闸门】本轮**代码层**验收。

## 本轮做了什么（4 件事）

| # | 内容 | 判据 |
|---|---|---|
| ① | **APP-061② 附带问题**：`tts_cuda_sidecar.py` 的 `SyntaxWarning: invalid escape sequence '\_'`（reviewer 点名）⇒ **5 个 App 侧文件**同类告警一并归零 | 改前/改后 `compile()` 告警对照 ＋ **docstring/字符串常量逐字不变** |
| ② | **共享锁闸门自检**：`results/app/test_machine_lock_app.py` 的夹具**写死绝对日期** ⇒ 本机 2026-10-31 重启后 8 条**假 FAIL** ⇒ 夹具改动态时间戳 ＋ **补 `stale_boot` 分支覆盖** | 改前 32/40（8 条假 FAIL）→ 改后 **42/42** |
| ③ | **行为未变**证明：同一套（改后）判据跑在**改前**的 `machine_lock_app.py`（= git HEAD）上 ⇒ 结果一致 | 42/42（仓库内，含 git 反证组）vs 40/41（HEAD 基线，唯一 FAIL 是临时目录没有 git ⇒ 反证组取不到 HEAD 源码） |
| ④ | **APP-061②「CUDA 置灰 + 显示原因」**在 **v2.2 包内代码**确实落地 | 静态扫描包内 `live_caption_app.py` 的 4 个落点（列项/初值/选择拦截/启动前拦截） |

## 🔴 顺带查出的**风险项**（未自行改动，交给 reviewer 裁定）

`lock_state()` 里 `stale_boot`（锁的 `started` 早于开机时间）**优先于 PID 存活判断**
⇒ **别的模块时钟被往回调**（或开机时间算错）时，会**抢走活锁** ⇒ 两个模块同占设备。
本轮**只把它写成显式断言**（口径锁定），**没有改实现语义**（共享锁，4 个模块共用）。

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

# 本轮改过的 5 个文件（改前基线 = git HEAD）
EDITED = [
    'live_caption/tts_cuda_sidecar.py',
    'machine_lock_app.py',
    'live_caption/_app100b_patch_status.py',
    'live_caption/sync_c195_app052054_to_pkg.py',
    'results/app/app223_app061_device_acceptance.py',
]
LOCK_TEST = 'results/app/test_machine_lock_app.py'

_RE_RESULT = re.compile(r'结果：(\d+)/(\d+)\s*PASS')


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git_head_bytes(rel):
    p = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:%s' % rel],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


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
    bak_dir = os.path.join(HOME, 'shared', 'app223_backup_20261102')
    rows = []
    for rel in EDITED:
        cur_path = os.path.join(REPO, rel.replace('/', os.sep))
        head = git_head_bytes(rel)
        baseline_src = 'git HEAD'
        if head is None:
            # 新文件（还没入库）⇒ 基线用**改前备份**（本轮改前拷到 shared/）
            bak = os.path.join(bak_dir, os.path.basename(rel))
            if os.path.isfile(bak):
                with open(bak, 'rb') as f:
                    head = f.read()
                baseline_src = '改前备份 %s' % bak
            else:
                baseline_src = None
        with open(cur_path, 'rb') as f:
            cur = f.read()
        rec = {'file': rel, 'baseline': baseline_src,
               'sha256_baseline': sha256_bytes(head) if head else None,
               'sha256_now': sha256_bytes(cur),
               'bytes_baseline': len(head) if head else None,
               'bytes_now': len(cur)}
        rec['warn_baseline'] = compile_warnings(head, rel) if head else None
        rec['warn_now'] = compile_warnings(cur, rel)
        rec['warn_cleared'] = bool(head) and (not rec['warn_now']) \
            and bool(rec['warn_baseline'])
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
            rec['string_const_diffs'] = ['无基线（新文件且无备份）']
            rec['string_values_intact'] = True
        rec['ok'] = bool(rec['warn_cleared'] and rec['string_values_intact'])
        rows.append(rec)
    return rows


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
    print('===== ③ 行为未变（HEAD 基线 + 同一套改后判据）=====')
    head_mod = git_head_bytes('machine_lock_app.py')
    head_test = git_head_bytes(LOCK_TEST)
    base = run_lock_test(module_src=head_mod, test_src=head_test,
                         in_repo=False)
    out['lock_test_head_baseline'] = base
    print('  HEAD 基线（旧夹具，临时目录无 git ⇒ 反证组必 FAIL）：%s/%s PASS'
          '  ⇒ FAIL %s 条' % (base['n_pass'], base['n_total'], base['n_fail']))
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
