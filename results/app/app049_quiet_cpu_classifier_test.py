r"""app049_quiet_cpu_classifier_test.py —— 安静窗口「在等锁 vs 在算」分类器的**离线验收**。

====================================================================
背景（MT 通知 12 §12.5，2026-10-25 23:50）
====================================================================
MT 侧实测事故：安静窗口闸门把**锁包装器**判成干扰源 ⇒ 两批各跑 2222 s
却全部被写成 `timing_valid=false` ⇒ **整批永久作废**。
根因（MT §12.5）：
  旧判据要求「**有 CPU 历史** 且 CPU 增量 ≈ 0」才判「在等锁」
  ⇒ `monitor.reset()` 之后**第一次采样必然没有历史**
  ⇒ **必然把锁包装器判成 dirty 一次** ⇒ `contaminated` 置 True ⇒ 整批拉黑。

MT 点名要求三方（App / ASR / TTS）自查。**App 侧**的对应实现是
`machine_lock_app.py` 的安静窗口闸门（`pack_v13.py` / `publish_ftp.py` 用）。

====================================================================
App 侧的真实缺陷
====================================================================
🔴 老 `wait_quiet_window()` 的判据是「**存在外部 python 进程** ⇒ 有干扰」
   ⇒ 别的模块的脚本**在等锁时也是活着的 python 进程**
   ⇒ 协作方（正是因为在等**你**才存在）被误判成干扰源
   ⇒ **必然互等死锁**（MT 侧实测白等 **1 h 41 min**）。

====================================================================
本轮修法
====================================================================
`machine_lock_app.py` 新增：
  ① `classify_external_python()` —— 用 **CPU 时间增量**（`GetProcessTimes`）
     把外部 python 进程分成：
       - `busy`   ：增量显著 ⇒ **真在算** ⇒ 干扰源
       - `idle`   ：增量 ≈ 0 ⇒ **在等锁 / 在睡** ⇒ **放行**
       - `unknown`：**读不到 CPU / 首次采样无历史** ⇒ **fail-closed** ⇒ 算干扰
  ② `wait_quiet_window_cpu()` —— 安静窗口（分类器版）
  ③ `LockHeld.wait_quiet()` **默认切到分类器版**（`use_cpu_classifier=True`）

🔴 **首次采样只建基线、不下结论** ⇒ 解决 MT §12.5 的「第一次必然判 dirty」。

====================================================================
本脚本测什么
====================================================================
REAL 组（命中 = 预期成立 ⇒ PASS）
  R1  `machine_lock_app` 暴露了分类器 API
  R2  `GetProcessTimes` 能读到**本进程**的 CPU 秒数（> 0）
  R3  真实机器上存在「等锁型」进程（`pack_v13.py` 挂着等锁，CPU 增量 ≈ 0）
      ⇒ 分类器把它判为 **idle**（放行），**不判 busy**
  R4  伪造 `prev_cpu`（把基线往前挪 5 s）⇒ 同一进程被判为 **busy**（干扰源）
  R5  CPU **读不到** ⇒ 归 `unknown` ⇒ **fail-closed**（算干扰）
  R6  `wait_quiet_window_cpu()` 在**排除全部 python** 时返回 True（可进窗口）
  R7  `wait_quiet_window_cpu()` 的 `info` 含可落盘证据字段
  R8  `pack_v13.py` / `publish_ftp.py` 走的 `wait_quiet` **默认用分类器**
  R9  老版 `wait_quiet_window()` **仍然可用**（不回归）
  R10 代码里绝不用 `tasklist /FI`、绝不 import `psutil`、绝不 kill 别人进程

BUG 组（命中 = 缺陷**仍然存在** ⇒ FAIL；用于反证）
  B1  老判据（只看进程存在）在有协作方时**必然**判「有干扰」⇒ 证明老判据有区分力
      且**证明本轮修法是必要的**（老版会把等锁的协作方也判成 busy）
  B2  `wait_quiet_window_cpu()` 超时 ⇒ 必然返回 False

====================================================================
纪律
====================================================================
🔴 **不 import 被测的模型模块**（不 import numpy/openvino/torch）
🔴 **不跑推理 / 不测速 / 不占 GPU**
🔴 **不碰真实的 `shared/MACHINE_LOCK`**（本脚本只读它、从不写）
🔴 **不烧 CPU 造「在算」进程**（用**伪造 prev_cpu** 达成同一断言）
   ⇒ 避免污染**别的模块正在进行的计时作业**
🔴 **不调 MiniMax**（质量判定交 reviewer）
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import time
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import machine_lock_app as M  # noqa: E402  （stdlib only，不 import numpy）

OUT = os.path.join(HERE, 'app049_quiet_cpu_classifier_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': str(detail)[:400]})
    print('[%s] %s %s  %s' % (group, 'PASS' if ok else 'FAIL', name,
                               (' | ' + str(detail)[:160]) if detail else ''))
    return bool(ok)


def _src(rel):
    with open(os.path.join(REPO, rel), encoding='utf-8', errors='replace') as f:
        return f.read()


def _code_only(rel):
    """返回该文件的**真实代码**（剥掉注释与 docstring）。

    🔴 判据「绝不用 tasklist /FI」是针对**代码**的；
      但本模块的 docstring 里**正要点名**这个禁用串（警告读者）
      ⇒ 直接全文搜会**误报** ⇒ 必须只搜真正的可执行语句。
    """
    src = _src(rel)
    try:
        out = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok)
        src = tokenize.untokenize(out)
    except Exception:
        pass
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


def _all_python_pids():
    try:
        return [pid for pid, exe in M.list_processes()
                if (exe or '').lower().startswith(('python', 'pythonw'))]
    except Exception:
        return []


def run_real():
    # ── R1 API 存在 ──────────────────────────────────────────────
    check('REAL', 'R1 machine_lock_app 暴露分类器 API',
          hasattr(M, 'classify_external_python')
          and hasattr(M, 'wait_quiet_window_cpu')
          and hasattr(M, '_process_cpu_seconds'),
          'classify=%s wait_quiet_cpu=%s'
          % (hasattr(M, 'classify_external_python'),
             hasattr(M, 'wait_quiet_window_cpu')))

    # ── R2 能读到自己的 CPU 秒数 ─────────────────────────────────
    my_cpu = M._process_cpu_seconds(os.getpid())
    check('REAL', 'R2 GetProcessTimes 能读到本进程 CPU 秒数',
          my_cpu is not None and my_cpu > 0,
          'cpu_s=%s' % (round(my_cpu, 3) if my_cpu is not None else None))

    # ── R3/R4 用**自己控制的**「在睡」进程做分类对象 ──────────────
    #   🔴 为什么自己造：本机此刻可能有别的模块在**真跑**作业
    #   ⇒ 不能拿它们的进程当「在等锁」的样本（那是真在算 ⇒ 必然判 busy）。
    #   ⇒ 造一个**只 sleep、几乎不烧 CPU** 的子进程 ⇒ 它就是「在等锁」的等价物。
    #   ⚠️ 该子进程**几乎不耗 CPU** ⇒ 不构成对他模块计时的污染。
    import subprocess
    sleeper = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(120)'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # 🔴 **必须等它启动完成**再取基线：python 解释器**冷启动**本身要烧
        #   ~0.15 s CPU ⇒ 若基线取在启动中途，后面这次采样会看到
        #   「增量 ≈ 0.15 s」⇒ 被判成 busy（**假阳性**）。
        #   ⇒ 等 2 s 让启动彻底结束 ⇒ 之后增量才真��是「在睡」。
        #   （这正是 MT 通知 12 §12.5 说的「首次采样必然没有历史」的另一面：
        #   基线必须取在**作业已经进入稳态**之后。）
        time.sleep(2.0)
        ext = M.external_python_pids()
        check('REAL', 'R3 机器上存在外部 python 进程（可作分类对象）',
              len(ext) > 0, 'n_ext=%d pids=%r' % (len(ext), ext[:8]))

        # 第一次采样：只建基线 ⇒ 该进程必然落在 unknown（无历史）
        busy1, idle1, unk1, prev = M.classify_external_python()
        check('REAL', 'R3 第一次采样不下结论（建基线）⇒ 落在 unknown',
              sleeper.pid in unk1,
              'sleeper=%d unk1=%r idle1=%r busy1=%r'
              % (sleeper.pid, unk1[:8], idle1[:8], busy1[:8]))

        time.sleep(3.0)
        busy2, idle2, unk2, prev2 = M.classify_external_python(prev_cpu=prev)
        check('REAL', 'R3 第二次采样起「在睡」进程被判 idle（放行）',
              sleeper.pid in idle2,
              'sleeper=%d idle2=%r busy2=%r unk2=%r'
              % (sleeper.pid, idle2[:8], busy2[:8], unk2[:8]))
        check('REAL', 'R3 「在睡」进程**不**被误判成 busy（干扰源）',
              sleeper.pid not in busy2,
              'busy2=%r' % (busy2[:8],))

        # ── R4 伪造 prev_cpu ⇒ 同一进程判 busy（不烧 CPU）────────────
        #   把基线往前挪 5 s ⇒ 增量 ≈ 5 s ≫ idle_eps ⇒ 必判 busy。
        prev_fake = {}
        for pid in ext:
            cpu = M._process_cpu_seconds(pid)
            if cpu is not None:
                prev_fake[pid] = cpu - 5.0
        b_fake, i_fake, u_fake, _ = M.classify_external_python(prev_cpu=prev_fake)
        check('REAL', 'R4 伪造基线 ⇒ 同一进程被判 busy（干扰源）',
              sleeper.pid in b_fake,
              'sleeper=%d busy=%r idle=%r unknown=%r'
              % (sleeper.pid, b_fake[:8], i_fake[:8], u_fake[:8]))
        check('REAL', 'R4 「在算」与「在等锁」可区分（同一进程、两种结论）',
              (sleeper.pid in b_fake) and (sleeper.pid in idle2),
              'fake_busy=%s real_idle=%s' % (sleeper.pid in b_fake,
                                             sleeper.pid in idle2))
    finally:
        try:
            sleeper.kill()
            sleeper.wait(timeout=5)
        except Exception:
            pass

    # ── R5 CPU 读不到 ⇒ fail-closed ──────────────────────────────
    #   ① 直接验证 `_process_cpu_seconds` 对**不存在的 PID** 返回 None；
    #   ② 用**被排除**的 PID 制造「枚举不到 ⇒ 走 unknown」的等价场景：
    #      分类器里 CPU 读不到的进程一律进 unknown ⇒ fail-closed。
    none_cpu = M._process_cpu_seconds(0x7FFFFFF0)
    check('REAL', 'R5 CPU 读不到 ⇒ 返回 None（上层据此 fail-closed）',
          none_cpu is None, 'cpu_s=%s' % none_cpu)

    #   ③ 关键性质：**unknown 计入干扰**（不放松 fail-closed）
    #      ⇒ 构造一个「CPU 读不到」的进程：用一个**已退出**的 PID 不行
    #      （枚举不到）⇒ 直接检查分类器源码里 unknown 的处理。
    cls_src = _src('machine_lock_app.py')
    check('REAL', 'R5 unknown 被计入干扰（fail-closed 不放松）',
          'blockers = list(busy) + list(unknown)' in cls_src,
          '源码里 unknown 与 busy 合并为 blockers')

    # ── R6 排除全部 python ⇒ 安静窗口成立 ───────────────────────
    allpy = _all_python_pids()
    ok, info = M.wait_quiet_window_cpu(quiet_seconds=1, timeout=25, poll=1,
                                       exclude_pids=allpy, verbose=False)
    check('REAL', 'R6 排除全部 python ⇒ 安静窗口成立（分类器版）',
          ok is True, 'ok=%s waited_s=%.1f' % (ok, info.get('waited_s', -1)))

    # ── R7 证据字段 ─────────────────────────────────────────────
    need = ('n_samples', 'n_busy_samples', 'n_idle_samples',
            'n_unknown_samples', 'waited_s', 'classifier',
            'last_busy_pids', 'last_idle_pids')
    check('REAL', 'R7 info 含可落盘的证据字段',
          all(k in info for k in need),
          'keys=%r' % (sorted(info.keys()),))

    # ── R8 打包/发布走的 wait_quiet 默认用分类器 ──────────────────
    lock_src = _src('machine_lock_app.py')
    check('REAL', 'R8 LockHeld.wait_quiet 默认切到 CPU 分类器',
          'use_cpu_classifier: bool = True' in lock_src
          and 'wait_quiet_window_cpu(' in lock_src,
          'use_cpu_classifier hits=%d'
          % lock_src.count('use_cpu_classifier'))
    pack_src = _src('pack_v13.py')
    ftp_src = _src('publish_ftp.py')
    check('REAL', 'R8 pack_v13.py / publish_ftp.py 调用了 wait_quiet',
          'wait_quiet' in pack_src and 'wait_quiet' in ftp_src,
          'pack=%d ftp=%d' % (pack_src.count('wait_quiet'),
                              ftp_src.count('wait_quiet')))

    # ── R9 老版仍在（不回归）────────────────────────────────────
    check('REAL', 'R9 老版 wait_quiet_window 仍然可用',
          hasattr(M, 'wait_quiet_window'),
          'has=%s' % hasattr(M, 'wait_quiet_window'))

    # ── R10 纪律（只查**代码**）──────────────────────────────────
    code = _code_only('machine_lock_app.py')
    check('REAL', 'R10 代码里绝不用 tasklist /FI',
          'tasklist' not in code, 'occurrences=%d' % code.count('tasklist'))
    check('REAL', 'R10 保持 stdlib only（不引入 psutil）',
          'psutil' not in code, 'occurrences=%d' % code.count('psutil'))
    bad = [w for w in ('os.kill', 'taskkill', 'TerminateProcess',
                       '.terminate()', '.kill()')
           if w in code]
    check('REAL', 'R10 闸门不 kill 别人的进程', not bad, 'found=%r' % (bad,))


def run_bug():
    # ── B1 反证：老判据「只看进程存在」在有协作方时必然判有干扰 ──
    #   🔴 用**自己控制的「在睡」进程**当协作方 ⇒ 它 CPU 增量 ≈ 0
    #   ⇒ 老判据必然判「有干扰」（**假阴性**：等锁的协作方被当成干扰源）
    #   ⇒ 这正是 MT 侧白等 1 h 41 min 的机理。
    import subprocess
    sleeper = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(60)'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2.0)   # 等解释器冷启动结束（见 R3 的注释）
        # 🔴 反证 1：**只留协作方一个**（它 CPU 增量 ≈ 0 ⇒ 真的在等锁）
        #   ⇒ 老判据「只看进程存在」必然判「有干扰」⇒ 证明老判据有区分力，
        #   同时证明**本轮修法是必要的**（老版会把等锁的协作方判成干扰源）。
        others = [p for p in _all_python_pids() if p != sleeper.pid]
        ok_old2, info_old2 = M.wait_quiet_window(
            quiet_seconds=1, timeout=8, poll=1,
            exclude_pids=others, verbose=False)
        check('BUG', 'B1 老判据：协作方在等锁（CPU≈0）⇒ 仍被判「有干扰」',
              ok_old2 is False,
              'ok=%s n_busy_samples=%s（False ⇒ 老判据把等锁方误判为干扰）'
              % (ok_old2, info_old2.get('n_busy_samples')))

        # 🔴 反证 2：**排除全部 python** ⇒ 老判据应判「安静」
        #   ⇒ 证明上面那条不是恒真（老判据本身有区分力）。
        ok_old, info_old = M.wait_quiet_window(
            quiet_seconds=1, timeout=12, poll=1,
            exclude_pids=_all_python_pids(), verbose=False)
        check('BUG', 'B1 老判据有区分力（排除全部 python 后判「安静」）',
              ok_old is True,
              'ok=%s（True ⇒ 老判据在无干扰时成立 ⇒ 上面不是恒真）'
              % ok_old)
    finally:
        try:
            sleeper.kill()
            sleeper.wait(timeout=5)
        except Exception:
            pass

    # ── B2 反证：超时 ⇒ 必然返回 False ──────────────────────────
    ok_to, info_to = M.wait_quiet_window_cpu(
        quiet_seconds=999, timeout=4, poll=1, exclude_pids=(), verbose=False)
    check('BUG', 'B2 超时 ⇒ wait_quiet_window_cpu 必然返回 False',
          ok_to is False, 'ok=%s waited_s=%.1f'
          % (ok_to, info_to.get('waited_s', -1)))


def main():
    t0 = time.time()
    print('=' * 68)
    print(' 安静窗口分类器（在等锁 vs 在算）· 离线验收')
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
        task='安静窗口「在等锁 vs 在算」分类器的离线验收（MT 通知 12 §12.5）',
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        discipline=dict(
            imports_only_stdlib_lock_module=True,
            no_inference=True, no_benchmark=True, no_gpu=True,
            no_machine_lock_write=True, no_minimax=True,
            no_cpu_burner_spawned=True,
            note='「在算」分支用伪造 prev_cpu 达成 ⇒ 不烧 CPU ⇒ 不污染他模块计时',
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
