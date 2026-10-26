#!/usr/bin/env python
r"""校验 App 侧各计时脚本的取锁改写是否**语义正确**（不只看语法）。

「语法对」≠「改对了」——上一轮 regex 改写就踩过：
① payload 里模块名写成了**字面量** `'module: module'`（变量没替换）；
② `print` 丢了 `% LOCK`；
③ **成功路径的 `return True` 被吞掉**（只留下失败分支）⇒ 调用方永远拿不到「拿到了锁」。

⇒ 本脚本逐项断言这些**语义**，并对比 HEAD 确认没有别处被改动。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = [
    'results/app/app056_tts_streaming_gap.py',
    'results/app/app059_tts_streaming_e2e.py',
    'results/app/app061_tts_npu_contention.py',
    'results/app/app062_cp_decode_device_ab.py',
    'results/app/app065_precision_hint_ab.py',
    'results/app/app067_ruler_same_day_recheck.py',
    'live_caption/diag_c111_e2e.py',
    'live_caption/replay_c134_mt.py',
]

RESULTS = []


def check(name, cond, detail=''):
    ok = bool(cond)
    RESULTS.append((name, ok, detail))
    print(('  [ OK ] ' if ok else '  [FAIL] ') + name +
          (('  -- ' + detail) if detail else ''))
    return ok


def _acquire_func(tree, src):
    """取 acquire_lock 函数节点 + 源码。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'acquire_lock':
            return node, ast.get_source_segment(src, node)
    return None, None


def main():
    for rel in FILES:
        path = os.path.join(REPO, rel)
        with open(path, encoding='utf-8') as f:
            src = f.read()
        print('[%s]' % rel)
        tree = ast.parse(src)
        fn, fsrc = _acquire_func(tree, src)
        check('能解析出 acquire_lock', fn is not None)
        if fn is None:
            continue

        # ① 已改用原子写
        check('acquire_lock 内调用 write_lock_atomic',
              'write_lock_atomic' in fsrc)
        # ② **不再**有「先建空文件」的写法
        check('acquire_lock 内不再出现 O_CREAT|O_EXCL',
              'O_EXCL' not in fsrc)
        # ③ payload 里的模块名是**变量**而不是字面量
        mm = re.search(r"% \(([A-Za-z_][A-Za-z_0-9]*), os\.getpid\(\)", fsrc)
        check('payload 的 module 用的是变量（不是字面量）',
              mm is not None, 'var=%s' % (mm.group(1) if mm else '??'))
        # ④ 成功路径必须 return（布尔或元组）
        rets = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
        rets_src = [ast.get_source_segment(src, n) or '' for n in rets]
        has_true = any('True' in r for r in rets_src)
        check('成功路径有 return True（没被吞掉）', has_true,
              'returns=%r' % rets_src)
        # ⑤ 失败路径必须返回「假」
        has_false = any('False' in r for r in rets_src)
        check('失败路径有 return False', has_false,
              'returns=%r' % rets_src)
        # ⑥ import 存在且路径正确
        check('已 import machine_lock_app', 'import machine_lock_app' in src)
        # ⑦ 换行风格未变（与 HEAD 一致）
        head = subprocess.run(['git', 'show', 'HEAD:' + rel],
                              cwd=REPO, capture_output=True).stdout
        cur = open(path, 'rb').read()
        head_crlf = head.count(b'\r\n') > 0
        cur_crlf = cur.count(b'\r\n') > 0
        check('换行风格与 HEAD 一致', head_crlf == cur_crlf,
              'HEAD_crlf=%s now_crlf=%s' % (head_crlf, cur_crlf))
        # ⑧ 改动规模合理（不该是整文件重写）
        d = subprocess.run(['git', 'diff', '--numstat', '--', rel],
                           cwd=REPO, capture_output=True).stdout.decode()
        add, dele = (d.split()[0], d.split()[1]) if d.strip() else ('?', '?')
        n_add, n_del = int(add), int(dele)
        check('改动规模合理（+≤40 / -≤20）', n_add <= 40 and n_del <= 20,
              '+%s/-%s' % (add, dele))
        print()

    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    n_all = len(RESULTS)
    print('=' * 66)
    print('结果: %d/%d PASS' % (n_ok, n_all))
    for n, ok, det in RESULTS:
        if not ok:
            print('  FAIL: %s -- %s' % (n, det))
    print('=' * 66)
    return 0 if n_ok == n_all else 1


if __name__ == '__main__':
    sys.exit(main())
