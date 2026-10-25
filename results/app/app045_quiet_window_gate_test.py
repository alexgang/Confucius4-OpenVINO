r"""app045_quiet_window_gate_test.py —— 「安静窗口闸门」的**离线验收**。

====================================================================
背景（MT 通知 10 §10.6 / TTS 通知「锁路径」）
====================================================================
🔴 **「我持锁」并不等于「机器空闲」** —— 别的模块可能**不取锁**就直接跑。

实测证据（2026-10-25 16:04，MT 侧记录）：
- MT **已持锁**（`shared/MACHINE_LOCK` = `module: mt / pid: 7592`）并在跑 `ts10_nopunct_r2`；
- 同时 ASR 的 `p3_int4_slice_decode.py --device GPU.0` **正在跑**（PID 15884 / 31756）
  ⇒ **GPU.0 上两个作业并行** ⇒ MT 这次计时被污染 ⇒ MT 主动停掉了重跑。

⇒ **要求**（MT 通知 10 §10.6 原文）：
  「请 App 侧照此加固：取锁 ≠ 空闲，**必须再加一道「安静窗口」检查**。」

====================================================================
本脚本测什么
====================================================================
REAL 组（命中 = 预期成立 ⇒ PASS）
  Q1  `machine_lock_app` 暴露了安静窗口 API（`wait_quiet_window` / `LockHeld.wait_quiet`）
  Q2  `list_processes()` 能枚举到进程（ctypes Win32 API，不经 shell）
  Q3  `external_python_pids()` **排除自己**，且能发现别的 python 进程
  Q4  有外部 python 进程时 ⇒ `wait_quiet_window` **不返回 True**（fail-closed）
  Q5  没有外部 python 进程时 ⇒ `wait_quiet_window` **返回 True**
  Q6  返回的 `info` 含可落盘的证据字段（n_samples / n_busy_samples / waited_s）
  Q7  `pack_v13.py` 真的调用了安静窗口（源码里能查到调用点）
  Q8  `publish_ftp.py` 真的调用了安静窗口（源码里能查到调用点）
  Q9  **绝不用 `tasklist /FI`**（Git Bash 下会被当路径）⇒ 源码里没有这个串
  Q10 **绝不用 psutil**（保持 stdlib only）⇒ 源码里没有这个 import
  Q11 安静窗口**不 kill** 别人的进程（源码里没有 kill/terminate 调用）

BUG 组（命中 = 缺陷**仍然存在** ⇒ FAIL；用于反证）
  B1  把「有外部进程」的场景伪造掉 ⇒ 断言 Q4 必然 FAIL（证明 Q4 有区分力）
  B2  伪造「超时」⇒ `wait_quiet_window` 必然返回 False（证明超时分支有效）

====================================================================
纪律
====================================================================
🔴 **不 import 被测的模型模块**（不 import numpy/openvino/torch）
🔴 **不跑推理 / 不测速 / 不占 GPU**
🔴 **不碰真实的 `shared/MACHINE_LOCK`**（本脚本只读它、从不写）
🔴 **不调 MiniMax**（质量判定交 reviewer）
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import machine_lock_app as M  # noqa: E402  （stdlib only，不 import numpy）

OUT = os.path.join(HERE, 'app045_quiet_window_gate_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': str(detail)[:400]})
    print('[%s] %s %s  %s' % (group, 'PASS' if ok else 'FAIL', name,
                               ('| ' + str(detail)[:160]) if detail else ''))
    return bool(ok)


def _src(rel):
    with open(os.path.join(REPO, rel), encoding='utf-8', errors='replace') as f:
        return f.read()


def _code_only(rel):
    """返回该文件的**真实代码**（剥掉注释与 docstring）。

    🔴 **为什么必须剥**：判据「绝不用 `tasklist /FI`」是针对**代码**的；
    但本模块的 docstring 里**正要点名**这个禁用串（警告读者）
    ⇒ 直接全文搜会**误报** ⇒ 必须只搜真正的可执行语句。
    """
    import ast
    import io
    import tokenize
    src = _src(rel)
    # ① 去掉所有注释（tokenize）
    try:
        out = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok)
        src = tokenize.untokenize(out)
    except Exception:
        pass
    # ② 去掉所有 docstring（ast）
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(node, 'body', None)
                if body and isinstance(body[0], ast.Expr) and \
                        isinstance(body[0].value, ast.Constant) and \
                        isinstance(body[0].value.value, str):
                    body.pop(0)
        src = ast.unparse(tree)
    except Exception:
        pass
    return src


# ══════════════════════════════════════════════════════════════════════
def run_real():
    # ── Q1 API 存在 ──────────────────────────────────────────────
    check('REAL', 'Q1 machine_lock_app 暴露安静窗口 API',
          hasattr(M, 'wait_quiet_window')
          and hasattr(M.LockHeld, 'wait_quiet')
          and hasattr(M, 'external_python_pids'),
          'wait_quiet_window=%s LockHeld.wait_quiet=%s'
          % (hasattr(M, 'wait_quiet_window'),
             hasattr(M.LockHeld, 'wait_quiet')))

    # ── Q2 进程枚举 ──────────────────────────────────────────────
    procs = M.list_processes()
    check('REAL', 'Q2 list_processes 能枚举进程（ctypes Win32 API）',
          len(procs) > 0, 'n_procs=%d' % len(procs))
    check('REAL', 'Q2 枚举结果含 (pid, exe_name) 元组',
          all(isinstance(p, tuple) and len(p) == 2 for p in procs),
          'sample=%r' % (procs[:2],))

    # ── Q3 排除自己 + 发现别的 python ────────────────────────────
    ext = M.external_python_pids()
    self_pid = os.getpid()
    check('REAL', 'Q3 external_python_pids 排除自己',
          self_pid not in ext, 'self=%d ext=%r' % (self_pid, ext[:10]))
    # 自己进程是 python.exe ⇒ 若不排除自己，ext 必然含 self_pid
    check('REAL', 'Q3 能发现别的 python 进程（本机实测非空）',
          len(ext) > 0, 'n_ext=%d' % len(ext))

    # ── Q4 有外部进程 ⇒ 不返回 True（fail-closed）────────────────
    ok_busy, info_busy = M.wait_quiet_window(
        quiet_seconds=1, timeout=6, poll=2, exclude_pids=(), verbose=False)
    check('REAL', 'Q4 有外部 python 进程 ⇒ 安静窗口不成立（fail-closed）',
          ok_busy is False, 'ok=%s n_busy_samples=%s'
          % (ok_busy, info_busy.get('n_busy_samples')))
    check('REAL', 'Q4 记录到有干扰的采样数 > 0',
          info_busy.get('n_busy_samples', 0) > 0,
          'n_busy_samples=%s' % info_busy.get('n_busy_samples'))

    # ── Q5 没有外部进程 ⇒ 返回 True ─────────────────────────────
    # 把**所有**已知 python PID 都排除掉 ⇒ 模拟「机器空闲」。
    allpy = [pid for pid, exe in M.list_processes()
             if (exe or '').lower().startswith(('python', 'pythonw'))]
    ok_clean, info_clean = M.wait_quiet_window(
        quiet_seconds=1, timeout=20, poll=1,
        exclude_pids=allpy, verbose=False)
    check('REAL', 'Q5 无外部 python 进程 ⇒ 安静窗口成立',
          ok_clean is True, 'ok=%s waited_s=%.1f'
          % (ok_clean, info_clean.get('waited_s', -1)))

    # ── Q6 证据字段 ──────────────────────────────────────────────
    need = ('n_samples', 'n_busy_samples', 'waited_s', 'quiet_seconds',
            'timeout')
    check('REAL', 'Q6 info 含可落盘的证据字段',
          all(k in info_clean for k in need),
          'keys=%r' % (sorted(info_clean.keys()),))

    # ── Q7/Q8 打包与发布真的接入了 ──────────────────────────────
    pack_src = _src('pack_v13.py')
    ftp_src = _src('publish_ftp.py')
    check('REAL', 'Q7 pack_v13.py 调用了安静窗口',
          'wait_quiet' in pack_src and 'quiet_seconds' in pack_src,
          'wait_quiet=%d hits' % pack_src.count('wait_quiet'))
    check('REAL', 'Q8 publish_ftp.py 调用了安静窗口',
          'wait_quiet' in ftp_src and 'quiet_seconds' in ftp_src,
          'wait_quiet=%d hits' % ftp_src.count('wait_quiet'))

    # ── Q9/Q10/Q11 纪律（只查**代码**，不看注释里的警告文字）──────
    lock_code = _code_only('machine_lock_app.py')
    check('REAL', 'Q9 代码里绝不用 tasklist /FI（Git Bash 下会被当路径）',
          'tasklist' not in lock_code, 'occurrences=%d'
          % lock_code.count('tasklist'))
    check('REAL', 'Q10 保持 stdlib only（不引入 psutil）',
          'psutil' not in lock_code, 'occurrences=%d'
          % lock_code.count('psutil'))
    bad = [w for w in ('os.kill', 'taskkill', 'TerminateProcess',
                       '.terminate()', '.kill()')
           if w in lock_code]
    check('REAL', 'Q11 安静窗口不 kill 别人的进程', not bad,
          'found=%r' % (bad,))


def run_bug():
    # ── B1 反证：把「有外部进程」的场景去掉 ⇒ Q4 的断言必然 FAIL ──
    #   （证明 Q4 真的有区分力，不是恒真）
    allpy = [pid for pid, exe in M.list_processes()
             if (exe or '').lower().startswith(('python', 'pythonw'))]
    ok_fake, _ = M.wait_quiet_window(
        quiet_seconds=1, timeout=20, poll=1,
        exclude_pids=allpy, verbose=False)
    check('BUG', 'B1 排除全部 python 后 ⇒ 「有干扰 ⇒ 不成立」断言必然 FAIL',
          ok_fake is True,
          'ok=%s（True ⇒ 该断言在无干扰时确实会 FAIL ⇒ 有区分力）' % ok_fake)

    # ── B2 反证：超时 ⇒ 必然返回 False ──────────────────────────
    ok_timeout, info_timeout = M.wait_quiet_window(
        quiet_seconds=999, timeout=3, poll=1, exclude_pids=(), verbose=False)
    check('BUG', 'B2 超时 ⇒ wait_quiet_window 必然返回 False',
          ok_timeout is False,
          'ok=%s waited_s=%.1f' % (ok_timeout, info_timeout.get('waited_s', -1)))


def main():
    t0 = time.time()
    print('=' * 68)
    print(' 安静窗口闸门 · 离线验收')
    print('=' * 68)
    run_real()
    print()
    run_bug()

    real = [r for r in _results if r['group'] == 'REAL']
    bug = [r for r in _results if r['group'] == 'BUG']
    rp = sum(1 for r in real if r['ok'])
    bh = sum(1 for r in bug if r['ok'])
    verdict = 'PASS' if (rp == len(real) and bh == len(bug)) else 'FAIL'

    ev = dict(
        task='App 侧「安静窗口闸门」离线验收（MT 通知 10 §10.6 / TTS 锁路径通知）',
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        discipline=dict(
            imports_only_stdlib_lock_module=True,
            no_inference=True, no_benchmark=True, no_gpu=True,
            no_machine_lock_write=True, no_minimax=True,
        ),
        summary=dict(real_total=len(real), real_pass=rp,
                     real_fail=len(real) - rp,
                     bug_total=len(bug), bug_hit=bh,
                     bug_miss=len(bug) - bh,
                     verdict=verdict, elapsed_s=round(time.time() - t0, 1)),
        results=_results,
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print()
    print('REAL %d/%d PASS | BUG %d/%d 命中 | verdict=%s'
          % (rp, len(real), bh, len(bug), verdict))
    print('证据 ->', OUT)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
