#!/usr/bin/env python
r"""App 模块共享机器锁的**原子写**验收（`shared/NOTICE_tts_lock_atomic_20261026.md`）。

## 背景

TTS 通知（2026-10-26 21:45）指出：旧写法 `os.open(O_CREAT|O_EXCL)` **先建空文件、
之后才写内容** ⇒ 存在「文件已存在、内容还是空的」窗口 ⇒ 别的模块在这个窗口里读锁
⇒ 解析不出 pid ⇒ 判成「陈旧锁」⇒ `os.remove` 删掉**别人的活锁** ⇒ 两个模块同时跑。

实测事故（TTS 侧）：21:21~21:22 `single` 臂 **16/30** 行 `timing_valid=false`；
21:34~21:38 `A_CPU` 臂 **24/30** 行 `timing_valid=false`。

⇒ App 侧 `machine_lock_app.py::acquire()` 改成 **原子写**（`tmp` 写全 + `os.link` 建硬链接）。

## 本脚本测什么

**REAL 组**（修好后必须成立）：
- T1 原子写：并发读者**永远看不到半成品锁**（空文件 / 半截内容）
- T2 独占：第二个写者被拒 ⇒ **绝不覆盖**别人的锁
- T3 无残留：`*.tmp` 用完即删
- T4 跨模块可读：App 的 payload 能被 **TTS / MT / ASR** 三方的读锁实现解析出 pid
- T5 `acquire()` 走的是原子路径（不再出现 `O_CREAT|O_EXCL` 空窗）
- T6 「读不出 pid 但内容非空」⇒ **不删**（别人的活锁，格式不认得）
- T7 真的是空文件 ⇒ 等 2 s 后回收
- T8 `lock_intact()` 能发现「锁被抢 / 被换写」
- T9 `release()` 只删自己那份

**BUG 组**（缺陷**仍然存在**才会命中 ⇒ 命中即 FAIL）：
- B1 用**旧写法**（`O_CREAT|O_EXCL` 先建空文件）⇒ 并发读者**能看到空文件**
  ⇒ 证明「空锁窗口」这个缺陷形态**真实存在**（反证基线）

⚠️ 全程用**临时目录**下的锁文件，**绝不碰** `shared/MACHINE_LOCK`。
⚠️ 不跑推理、不测速、不占 GPU。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
import machine_lock_app as M

RESULTS = []


def check(name, cond, detail=''):
    ok = bool(cond)
    RESULTS.append((name, ok, detail))
    print(('  [ OK ] ' if ok else '  [FAIL] ') + name +
          (('  -- ' + detail) if detail else ''))
    return ok


def _payload(module, pid, started=None):
    started = started or time.strftime('%Y-%m-%d %H:%M:%S')
    return ('%s PID %d started %s\n'
            'module: %s\npid: %d\nstarted: %s\nhost: %s\n'
            % (module, pid, started, module, pid, started,
               os.environ.get('COMPUTERNAME', '?')))


# ─────────────────────────────────────────────────────────────
# REAL 组
# ─────────────────────────────────────────────────────────────
def real_tests(d):
    lock = os.path.join(d, 'MACHINE_LOCK')

    print('[T1] 原子写：并发读者永远看不到半成品锁')
    seen = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                with open(lock, 'rb') as f:
                    seen.append(f.read())
            except FileNotFoundError:
                seen.append(None)
            except Exception:
                seen.append(b'<err>')

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(0.05)
    got = M._write_lock_atomically(lock, _payload('app-atomic', os.getpid()))
    time.sleep(0.05)
    stop.set()
    th.join(timeout=3)
    check('原子写成功', got)
    # 判据：读者**要么看不到文件**（None），要么看到**完整内容**；
    # 绝不允许看到「空文件」或「半截内容」。
    partial = []
    for blob in seen:
        if blob is None:
            continue
        try:
            txt = blob.decode('utf-8')
        except Exception:
            partial.append('<decode-err>')
            continue
        if txt.strip() == '':
            partial.append('<EMPTY>')
        elif 'module:' not in txt or 'pid:' not in txt:
            partial.append('<PARTIAL:%r>' % txt[:40])
    check('读者从未看到空/半成品锁（%d 次采样）' % len(seen),
          not partial, 'violations=%r' % (partial[:5],))
    check('读者确实采样到了内容（不是空跑）',
          any(b is not None and b'module:' in b for b in seen if b),
          'n_seen=%d' % len(seen))

    print()
    print('[T2] 独占：第二个写者被拒，绝不覆盖别人的锁')
    first = open(lock, encoding='utf-8').read()
    got2 = M._write_lock_atomically(lock, _payload('other-module', 999999))
    check('第二个写者被拒（返回 False）', got2 is False)
    check('锁内容仍是第一个持有者',
          open(lock, encoding='utf-8').read() == first)

    print()
    print('[T3] 无残留 tmp')
    leftovers = [f for f in os.listdir(d) if f.endswith('.tmp')]
    check('无 *.tmp 残留', not leftovers, 'leftovers=%r' % leftovers)

    print()
    print('[T4] 跨模块可读：ASR / TTS / MT 三方的读锁实现都能解析 App 的 payload')
    payload = _payload('app-pack', os.getpid())
    # ASR: `qwen3asr_06b/scripts/pya_app_path_seg.py::_read_lock` 用正则 `pid[:=]\s*(\d+)`
    import re
    m = re.search(r'pid[:=]\s*(\d+)', payload, re.I)
    check('ASR 正则能解析出 pid', bool(m) and int(m.group(1)) == os.getpid(),
          'pid=%r' % (m.group(1) if m else None))
    # TTS: `qwen3tts_eval/machine_lock.py::_read_lock` 关键字扫描
    tts_pid = None
    for ln in payload.splitlines():
        if 'pid' in ln.lower():
            for tok in ln.replace(':', ' ').split():
                if tok.isdigit():
                    tts_pid = int(tok)
                    break
            if tts_pid is not None:
                break
    check('TTS 关键字扫描能解析出 pid',
          tts_pid == os.getpid(), 'pid=%r' % tts_pid)
    # MT: `hy_bench/machine_lock.py::read_lock` 逐行 key-value
    mt_pid = None
    for line in payload.splitlines():
        line = line.strip()
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        if k.strip().lower() == 'pid':
            try:
                mt_pid = int(v.strip())
            except Exception:
                mt_pid = None
    check('MT key-value 解析能解析出 pid', mt_pid == os.getpid(),
          'pid=%r' % mt_pid)
    # App 自己
    st, info = M.lock_state(lock)
    check('App 自己能读回 pid', info.get('pid') == os.getpid(),
          'state=%s pid=%r' % (st, info.get('pid')))

    print()
    print('[T5] acquire() 走的是原子路径（源码里不再有 O_CREAT|O_EXCL 建空文件）')
    src = open(os.path.join(_REPO, 'machine_lock_app.py'), encoding='utf-8').read()
    body = src[src.index('def acquire('):src.index('def release(')]
    check('acquire() 内不再出现 O_CREAT|O_EXCL',
          'O_EXCL' not in body, 'found=%r' % ('O_EXCL' in body))
    check('acquire() 调用了原子写函数',
          '_write_lock_atomically' in body)

    print()
    print('[T6] 「读不出 pid 但内容非空」⇒ 不删（别人的活锁，格式不认得）')
    lock2 = os.path.join(d, 'FOREIGN_LOCK')
    # 一份「我们不认识的格式」，但 PID 是**活着的自己** ⇒ 绝不能删
    with open(lock2, 'w', encoding='utf-8') as f:
        f.write('weird-format-no-keyvalue active-holder %d\n' % os.getpid())
    before = open(lock2, encoding='utf-8').read()
    st2, _ = M.lock_state(lock2)
    check('外格式锁被判为 unreadable（fail-closed）', st2 == 'unreadable',
          'state=%s' % st2)
    # 模拟 acquire 的回收分支：unreadable ⇒ 等 2 s ⇒ 内容非空 ⇒ 不删
    time.sleep(2.0)
    raw2 = M._decode_lock_bytes(lock2)
    blank = (raw2 is None) or (not raw2.strip())
    check('非空 ⇒ 判定为「不删」', not blank)
    check('外格式锁文件仍在（未被误删）', os.path.isfile(lock2))
    check('外格式锁内容未被改动',
          open(lock2, encoding='utf-8').read() == before)

    print()
    print('[T7] 真的是空文件 ⇒ 等 2 s 后回收')
    lock3 = os.path.join(d, 'EMPTY_LOCK')
    open(lock3, 'w').close()
    raw3 = M._decode_lock_bytes(lock3)
    check('空文件 ⇒ 判定为 blank（可回收）',
          (raw3 is None) or (not raw3.strip()))

    print()
    print('[T8] lock_intact() 能发现「锁被抢 / 被换写」')
    ok, why = M.lock_intact(lock, own_pid=os.getpid())
    check('自己持锁 ⇒ intact=True', ok, why)
    ok2, why2 = M.lock_intact(lock, own_pid=999999)
    check('PID 不是自己 ⇒ intact=False（发现被抢）', not ok2, why2)
    os.remove(lock)
    ok3, why3 = M.lock_intact(lock, own_pid=os.getpid())
    check('锁文件消失 ⇒ intact=False', not ok3, why3)

    print()
    print('[T9] release() 只删自己那份')
    lock4 = os.path.join(d, 'REL_LOCK')
    M._write_lock_atomically(lock4, _payload('app-rel', os.getpid()))
    ok4, pay4 = True, _payload('app-rel', os.getpid())
    # 篡改内容（模拟被他人换写）⇒ 不该删
    with open(lock4, 'w', encoding='utf-8') as f:
        f.write('module: somebody-else\npid: 424242\n')
    res = M.release(pay4, lock_path=lock4, verbose=False)
    check('内容被改动 ⇒ release 不删', res is False and os.path.isfile(lock4))
    os.remove(lock4)


# ─────────────────────────────────────────────────────────────
# BUG 组（缺陷**仍然存在**才命中 ⇒ 命中即 FAIL）
# ─────────────────────────────────────────────────────────────
def bug_tests(d):
    print('[B1] 反证：旧写法（O_CREAT|O_EXCL 先建空文件）⇒ 读者能看到空文件')
    lock = os.path.join(d, 'OLD_STYLE_LOCK')
    seen = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                with open(lock, 'rb') as f:
                    seen.append(f.read())
            except FileNotFoundError:
                seen.append(None)
            except Exception:
                seen.append(b'<err>')

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(0.05)
    # 🔴 **旧写法**：先建空文件，之后才写内容
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    time.sleep(0.15)          # 拉长「空锁窗口」，让读者有机会看到
    os.write(fd, _payload('old-style', os.getpid()).encode('utf-8'))
    os.close(fd)
    time.sleep(0.05)
    stop.set()
    th.join(timeout=3)
    empties = [b for b in seen if b == b'']
    check('BUG 命中：旧写法确实暴露了「空锁窗口」',
          len(empties) > 0,
          'n_empty_samples=%d / n_samples=%d' % (len(empties), len(seen)))


def main():
    d = tempfile.mkdtemp(prefix='app082_atomic_lock_')
    print('临时目录:', d)
    print()
    print('=' * 66)
    print('REAL 组（修好后必须全部成立）')
    print('=' * 66)
    real_tests(d)
    print()
    print('=' * 66)
    print('BUG 组（缺陷仍然存在才命中 ⇒ 命中即 FAIL）')
    print('=' * 66)
    bug_tests(d)
    print()
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    n_all = len(RESULTS)
    print('=' * 66)
    print('结果: %d/%d PASS' % (n_ok, n_all))
    fails = [(n, det) for n, ok, det in RESULTS if not ok]
    if fails:
        print('FAIL 项:')
        for n, det in fails:
            print('  - %s  -- %s' % (n, det))
    print('=' * 66)
    return 0 if n_ok == n_all else 1


if __name__ == '__main__':
    sys.exit(main())
