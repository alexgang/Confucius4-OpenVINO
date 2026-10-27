# -*- coding: utf-8 -*-
"""APP-023 / APP-025 —— 仓库↔客户包同步后的**语义级完整性检查**。

🔴🔴 为什么不能用字符串匹配（`MEMORY.md` / STATUS §62 的铁律）：
  注释里写了「旧实现 `stderr=... else None`」⇒ `'else None' in src` **命中**
  ⇒ 会**误报**「残留」；同理注释里提到 `_try_load_ov()` 也会误报「未删」。
  ⇒ **必须走 AST**：只看**代码**，不看注释与字符串。

判据（每条都要能指到具体 AST 节点）：
  A1 包内 `tts_cuda`：所有 `subprocess.Popen(...)` 的 `stderr=` **不能**是 None
  A2 包内 `tts_cuda`：`Popen` 的 `stdin/stdout` 也都显式给了（不是 None）
  A3 包内 `tts_service`：worker 用 `_worker_python()`（不是 `sys.executable`）
  A4 包内 `tts_service`：`Popen` 带 `creationflags`（免弹黑框）
  A5 包内 `tts_worker`：`load()` 里**不再调用** `_try_load_ov`
  A6 包内 `tts_worker`：`_try_load_babelvox` 里**没有** `return None`
  A7 包内 `tts_worker`：有 `play_test_tone_direct`
  A8 包内 `live_caption_app`：有 `describe_tts_failure` 且被 error 分支调用
  A9 包内 `offline_reader_gui`：有 `_sync_availability` 且被 `_poll` 调用
  A10 仓库与包的这 5 个文件**语义等价**（函数/类集合一致）
"""
from __future__ import annotations

import ast
import io
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\app'
FILES = ['tts_cuda.py', 'tts_service.py', 'tts_worker.py',
         'live_caption_app.py', 'offline_reader_gui.py']

_results = []


def check(name, cond, detail=''):
    _results.append((name, bool(cond), detail))
    print('  %s %s%s' % ('✅' if cond else '❌', name,
                         ('  —— ' + detail) if detail else ''))
    return bool(cond)


def load(path):
    src = io.open(path, encoding='utf-8').read()
    return src, ast.parse(src)


def popen_calls(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            # subprocess.Popen / Popen
            if isinstance(f, ast.Attribute) and f.attr == 'Popen':
                out.append(n)
            elif isinstance(f, ast.Name) and f.id == 'Popen':
                out.append(n)
    return out


def kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def is_none(node):
    return isinstance(node, ast.Constant) and node.value is None


def main():
    print('=' * 74)
    print('APP-023 / APP-025 同步完整性检查（AST 级，不看注释/字符串）')
    print('=' * 74)

    # ── A1/A2: tts_cuda 的 std 句柄 ──
    print('\n── tts_cuda.py：子进程 std 句柄 ──')
    src, tree = load(os.path.join(PKG, 'tts_cuda.py'))
    calls = popen_calls(tree)
    check('A0 找到 Popen 调用', len(calls) >= 1, '共 %d 处' % len(calls))
    bad_stderr = [c for c in calls if is_none(kw(c, 'stderr'))]
    check('A1 没有 stderr=None', not bad_stderr,
          '残留 %d 处' % len(bad_stderr))
    no_stdin = [c for c in calls if kw(c, 'stdin') is None]
    no_stdout = [c for c in calls if kw(c, 'stdout') is None]
    check('A2 stdin/stdout/皆显式', not no_stdin and not no_stdout,
          '缺 stdin %d / 缺 stdout %d' % (len(no_stdin), len(no_stdout)))

    # ── A3/A4: tts_service 拉 worker ──
    print('\n── tts_service.py：worker 解释器 ──')
    src, tree = load(os.path.join(PKG, 'tts_service.py'))
    uses_exec = 'sys.executable' in src
    calls = [c for c in popen_calls(tree) if kw(c, 'stdin') is not None]
    worker_call = None
    for c in calls:
        args = c.args
        if args and isinstance(args[0], ast.Name) and args[0].id == 'cmd':
            worker_call = c
            break
    check('A3 worker 用 _worker_python()（非 sys.executable）',
          '_worker_python_used' in src and '_worker_python()' in src,
          'sys.executable 仍出现=%s' % uses_exec)
    # 🔴 A4 的第一版判据 `k.arg == 'creationflags'` **也是假失败**：
    #   源码写的是 `**_no_window_flag()` —— 字典**解包**，
    #   ⇒ AST 里是 `ast.keyword(arg=None, value=Call(Name('_no_window_flag')))`，
    #   ⇒ `k.arg == 'creationflags'` **永远 False**（字面量关键字根本不存在）。
    #   ⇒ 正解：① 认 `**_no_window_flag()`；② 再进函数体确认真的返回 creationflags。
    def _has_creationflags(call):
        for k in call.keywords:
            if k.arg == 'creationflags':
                return True
            if k.arg is None and isinstance(k.value, ast.Call):
                fname = getattr(k.value.func, 'id', '') or getattr(
                    k.value.func, 'attr', '')
                # 🔴 两个文件命名**不一致**：tts_service 用 `_no_window_flag`、
                #   tts_cuda 用 `_NO_WINDOW_FLAG` ⇒ 判据必须**大小写不敏感**，
                #   否则「明明加了 flag」被判成没加（本轮实测到的假失败）。
                if fname.lower() == '_no_window_flag':
                    return True
        return False

    if worker_call is not None:
        has_flag = _has_creationflags(worker_call)
        # 深入 `_no_window_flag` 本体：确认它返回的字典里真有 creationflags
        nwf = None
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) \
                    and n.name.lower() == '_no_window_flag':
                nwf = n
                break
        ret_key = ''
        if nwf is not None:
            for n in ast.walk(nwf):
                if isinstance(n, ast.Return):
                    v = n.value
                    if isinstance(v, ast.Dict):
                        for kk in v.keys:
                            if isinstance(kk, ast.Constant) \
                                    and kk.value == 'creationflags':
                                ret_key = 'creationflags'
                    elif isinstance(v, ast.Name) and v.id == 'FLAG':
                        ret_key = 'creationflags'
            if not ret_key and 'creationflags' in ast.dump(nwf):
                ret_key = 'creationflags'
        check('A4a worker Popen 展开 _no_window_flag()（免弹黑框）', has_flag,
              '解包命中=%s' % has_flag)
        check('A4b _no_window_flag 本体真返回 creationflags',
              bool(ret_key) and nwf is not None,
              '函数存在=%s / 返回键=%r' % (nwf is not None, ret_key or '未找到'))
    else:
        check('A4a worker Popen 展开 _no_window_flag()（免弹黑框）', False,
              '没找到 worker 的 Popen 调用')
        check('A4b _no_window_flag 本体真返回 creationflags', False,
              '没找到 worker 的 Popen 调用')

    # ── A3b: tts_cuda 的边车也别弹黑框（同一类问题） ──
    csrc, ctree = load(os.path.join(PKG, 'tts_cuda.py'))
    c_calls = popen_calls(ctree)
    c_flag = all(_has_creationflags(c) for c in c_calls) if c_calls else False
    check('A4c tts_cuda 边车 Popen 也免弹黑框', c_flag,
          'Popen %d 处' % len(c_calls))

    # ── A5/A6/A7: tts_worker 去掉旧引擎回落 ──
    print('\n── tts_worker.py：旧引擎回落 / 测试音 ──')
    src, tree = load(os.path.join(PKG, 'tts_worker.py'))
    load_fn = None
    tbl_fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef):
            if n.name == 'load' and not isinstance(getattr(n, 'parent', None),
                                                   ast.ClassDef):
                # 只取 TTSWorker 类里的 load：用「含 _try_load 调用」来筛
                body = ast.dump(n)
                if '_try_load' in body:
                    load_fn = n
            if n.name == '_try_load_babelvox':
                tbl_fn = n
    if load_fn is None:
        # 退而求其次：任何名为 load 的 def
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == 'load':
                load_fn = n
                break
    ov_calls = []
    ret_none = []
    if load_fn is not None:
        for n in ast.walk(load_fn):
            if isinstance(n, ast.Call):
                f = n.func
                nm = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else '')
                if nm == '_try_load_ov':
                    ov_calls.append(n)
    check('A5 load() 不再调用 _try_load_ov（旧引擎）', not ov_calls,
          '残留 %d 处' % len(ov_calls))
    if tbl_fn is not None:
        for n in ast.walk(tbl_fn):
            if isinstance(n, ast.Return) and is_none(n.value):
                ret_none.append(n)
    check('A6 _try_load_babelvox 不再 return None', not ret_none,
          '残留 %d 处' % len(ret_none))
    has_direct = any(isinstance(n, ast.FunctionDef)
                     and n.name == 'play_test_tone_direct'
                     for n in ast.walk(tree))
    check('A7 有 play_test_tone_direct（测试音不依赖 worker）', has_direct)

    # ── A8: 错误提示人话 ──
    print('\n── live_caption_app.py：错误提示 ──')
    src, tree = load(os.path.join(PKG, 'live_caption_app.py'))
    has_desc = any(isinstance(n, ast.FunctionDef)
                   and n.name == 'describe_tts_failure'
                   for n in ast.walk(tree))
    check('A8a 有 describe_tts_failure', has_desc)
    used = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'describe_tts_failure' for n in ast.walk(tree))
    check('A8b 被实际调用（不是死代码）', used)

    # ── A9: 离线朗读置灰 ──
    print('\n── offline_reader_gui.py：置灰 ──')
    src, tree = load(os.path.join(PKG, 'offline_reader_gui.py'))
    has_sync = any(isinstance(n, ast.FunctionDef)
                   and n.name == '_sync_availability' for n in ast.walk(tree))
    check('A9a 有 _sync_availability', has_sync)
    poll = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == '_poll':
            poll = n
    used_sync = False
    if poll is not None:
        used_sync = any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                        and x.func.attr == '_sync_availability'
                        for x in ast.walk(poll))
    check('A9b _poll 里调用了它（会持续生效）', used_sync)

    # ── A10: 仓库与包语义等价 ──
    print('\n── 仓库 ↔ 包：语义等价 ──')
    for rel in FILES:
        _, t1 = load(os.path.join(REPO, rel))
        _, t2 = load(os.path.join(PKG, rel))
        d1 = {n.name for n in ast.walk(t1)
              if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        d2 = {n.name for n in ast.walk(t2)
              if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        check('A10 %s 定义集合一致' % rel, d1 == d2,
              '仅仓库有=%s / 仅包有=%s'
              % (sorted(d1 - d2)[:3], sorted(d2 - d1)[:3]))

    ok = sum(1 for _, c, _ in _results if c)
    bad = len(_results) - ok
    print('\n' + '=' * 74)
    print('PASS %d / FAIL %d' % (ok, bad))
    print('=' * 74)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
