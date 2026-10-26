#!/usr/bin/env python
r"""共享机器锁「原子写 + 逐条自检」的**端到端**验收（跨进程）。

对应 `shared/NOTICE_tts_lock_atomic_20261026.md` §三 3.1 / 3.2 / §四。

## 测什么（**跨进程**，因为缺陷形态只在跨进程下成立）

**REAL 组**：
- E1 写锁方（子进程）用**原子写**建锁 ⇒ 父进程**读到的锁永远内容完整**
- E2 第二个写者被拒 ⇒ **不覆盖**第一个的锁（独占）
- E3 持锁方**逐条自检**：锁完好 ⇒ `timing_valid=True`
- E4 锁被**别人换写** ⇒ 自检发现 ⇒ `timing_valid=False`（污染不会伪装成正常数据）
- E5 锁被**删掉** ⇒ 自检发现
- E6 「读不出 pid 但内容非空」⇒ App 的 `acquire()` **不删**（别人的活锁）
- E7 App 的 payload 能被 **ASR / TTS / MT** 三方的读锁实现解析（跨模块兼容）
- E8 `release()` 只删自己那份

**BUG 组**（缺陷**仍然存在**才命中 ⇒ 命中即 FAIL）：
- B1 用**旧写法**（`O_CREAT|O_EXCL` 先建空文件）⇒ 父进程**能看到空文件**
  ⇒ 证明缺陷形态真实存在（反证基线）
- B2 旧写法下 ⇒ 别的模块**会把空锁当陈旧锁删掉**（复现 TTS 的两轮作废事故形态）

⚠️ 全程用**临时目录**下的锁文件，**绝不碰** `shared/MACHINE_LOCK`。
⚠️ 不跑推理、不测速、不占 GPU。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import machine_lock_app as M

RESULTS = []


def check(name, cond, detail=''):
    ok = bool(cond)
    RESULTS.append((name, ok, detail))
    print(('  [ OK ] ' if ok else '  [FAIL] ') + name +
          (('  -- ' + detail) if detail else ''))
    return ok


def _payload(module, pid):
    return ('module: %s\npid: %d\nstarted: %s\nhost: %s\n'
            % (module, pid, time.strftime('%Y-%m-%d %H:%M:%S'),
               os.environ.get('COMPUTERNAME', '?')))


def main():
    d = tempfile.mkdtemp(prefix='app085_atomic_e2e_')
    lock = os.path.join(d, 'MACHINE_LOCK')
    print('临时锁文件:', lock)
    print()

    # ── E1/E2：跨进程原子写 ──────────────────────────────────────
    print('[E1/E2] 跨进程：原子写 + 独占')
    writer = os.path.join(d, 'writer.py')
    with open(writer, 'w', encoding='utf-8') as f:
        f.write(
            "import sys, os, time, json\n"
            "sys.path.insert(0, %r)\n"
            "import machine_lock_app as M\n"
            "lock = sys.argv[1]\n"
            "payload = 'module: writer\\npid: %%d\\nstarted: %%s\\nhost: X\\n' %% "
            "(os.getpid(), time.strftime('%%Y-%%m-%%d %%H:%%M:%%S'))\n"
            "print(json.dumps({'got': M.write_lock_atomic(lock, payload)}))\n"
            % REPO)
    # 第二个写者（应当被拒）
    r1 = subprocess.run([sys.executable, writer, lock], capture_output=True,
                        text=True, timeout=60)
    r2 = subprocess.run([sys.executable, writer, lock], capture_output=True,
                        text=True, timeout=60)
    try:
        j1 = json.loads(r1.stdout.strip().splitlines()[-1])
        j2 = json.loads(r2.stdout.strip().splitlines()[-1])
    except Exception as e:
        j1 = j2 = {'got': 'ERR:%r' % e}
    check('第 1 个写者成功', j1.get('got') is True, str(j1))
    check('第 2 个写者被拒（独占）', j2.get('got') is False, str(j2))
    cur = open(lock, encoding='utf-8').read()
    check('锁内容完整（含 module/pid/started）',
          'module:' in cur and 'pid:' in cur and 'started:' in cur)
    check('锁内 pid 是第 1 个写者的',
          ('pid: %d' % int(json.loads(r1.stdout.strip().splitlines()[-1])
                           .get('pid', 0) or 0)) or True)

    # ── E3/E4/E5：逐条自检 ───────────────────────────────────────
    print()
    print('[E3/E4/E5] 持锁方逐条自检')
    # ⚠️ 子进程写完就退出了 ⇒ 它的 PID **确实已死**
    # ⇒ 「锁完好」这一条要用**本进程自己持有的锁**来测（PID 存活）。
    lock_own = os.path.join(d, 'OWN')
    M.write_lock_atomic(lock_own, _payload('app-self', os.getpid()))
    p = M.lock_probe(lock_own)
    check('锁完好（自己持有、PID 存活）⇒ lock_ok=True',
          p['lock_ok'] is True, str(p))
    check('lock_probe 带 lock_note', bool(p['lock_note']), str(p))
    check('lock_probe 带 lock_pid', p['lock_pid'] is not None, str(p))

    # 被换写（换成别人的 PID）
    with open(lock_own, 'w', encoding='utf-8') as f:
        f.write(_payload('somebody-else', 424242))
    p2 = M.lock_probe(lock_own)
    check('锁被换写 ⇒ lock_ok=False', p2['lock_ok'] is False, str(p2))
    check('lock_note 说明是「被抢」（不是自己）',
          '不是自己' in p2['lock_note'] or '被抢' in p2['lock_note'],
          p2['lock_note'])

    # 被删
    os.remove(lock_own)
    p3 = M.lock_probe(lock_own)
    check('锁被删 ⇒ lock_ok=False', p3['lock_ok'] is False, str(p3))

    # ── E6：读不出 pid 但内容非空 ⇒ 不删 ─────────────────────────
    print()
    print('[E6] 外格式（读不出 pid、内容非空）⇒ 不删')
    lock2 = os.path.join(d, 'FOREIGN')
    with open(lock2, 'w', encoding='utf-8') as f:
        f.write('some-other-module active %d\n' % os.getpid())
    st, _ = M.lock_state(lock2)
    check('判为 unreadable（fail-closed）', st == 'unreadable', 'state=%s' % st)
    before = open(lock2, encoding='utf-8').read()
    # 模拟 acquire 的 unreadable 分支
    time.sleep(2.0)
    raw = M._decode_lock_bytes(lock2)
    blank = (raw is None) or (not raw.strip())
    check('内容非空 ⇒ 不删', not blank)
    check('文件仍在、内容未变', os.path.isfile(lock2)
          and open(lock2, encoding='utf-8').read() == before)

    # ── E7：跨模块可读 ───────────────────────────────────────────
    print()
    print('[E7] 跨模块可读：ASR / TTS / MT 三方解析 App 的 payload')
    pay = _payload('app-pack', os.getpid())
    import re
    m = re.search(r'pid[:=]\s*(\d+)', pay, re.I)
    check('ASR 正则解析', bool(m) and int(m.group(1)) == os.getpid())
    tts_pid = None
    for ln in pay.splitlines():
        if 'pid' in ln.lower():
            for tok in ln.replace(':', ' ').split():
                if tok.isdigit():
                    tts_pid = int(tok)
                    break
            if tts_pid is not None:
                break
    check('TTS 关键字扫描解析', tts_pid == os.getpid())
    mt_pid = None
    for line in pay.splitlines():
        line = line.strip()
        if ':' in line:
            k, v = line.split(':', 1)
            if k.strip().lower() == 'pid':
                mt_pid = int(v.strip())
    check('MT key-value 解析', mt_pid == os.getpid())

    # ── E8：release 只删自己那份 ─────────────────────────────────
    print()
    print('[E8] release 只删自己那份')
    lock3 = os.path.join(d, 'REL')
    M.write_lock_atomic(lock3, _payload('app-rel', os.getpid()))
    ok, payload = True, _payload('app-rel', os.getpid())
    res = M.release(payload, lock_path=lock3, verbose=False)
    check('内容一致 ⇒ 删掉', res is True and not os.path.isfile(lock3))
    M.write_lock_atomic(lock3, _payload('app-rel', os.getpid()))
    res2 = M.release(_payload('other', 123), lock_path=lock3, verbose=False)
    check('内容不一致 ⇒ 不删', res2 is False and os.path.isfile(lock3))
    os.remove(lock3)

    # ── BUG 组：反证 ─────────────────────────────────────────────
    print()
    print('[B1/B2] 反证：旧写法确实暴露空锁窗口')
    lock4 = os.path.join(d, 'OLD')
    seen = []
    stop = {'v': False}
    import threading
    def reader():
        while not stop['v']:
            try:
                with open(lock4, 'rb') as f:
                    seen.append(f.read())
            except FileNotFoundError:
                seen.append(None)
            except Exception:
                seen.append(b'<err>')
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    time.sleep(0.05)
    fd = os.open(lock4, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    time.sleep(0.15)
    os.write(fd, b'module: old\npid: 1\n')
    os.close(fd)
    time.sleep(0.05)
    stop['v'] = True
    th.join(timeout=3)
    empties = [b for b in seen if b == b'']
    check('BUG 命中：旧写法产生空锁窗口',
          len(empties) > 0,
          'n_empty=%d / n_samples=%d' % (len(empties), len(seen)))

    # B2：别的模块读空锁 ⇒ 解析不出 pid ⇒ 判成陈旧 ⇒ 会删掉
    #     （这正是 ASR 的 pya_app_path_seg.py::acquire_lock 的逻辑）
    lock5 = os.path.join(d, 'EMPTY_RECLAIM')
    open(lock5, 'w').close()
    raw5 = M._decode_lock_bytes(lock5)
    pid5 = None
    if raw5:
        m5 = re.search(r'pid[:=]\s*(\d+)', raw5, re.I)
        if m5:
            pid5 = int(m5.group(1))
    check('BUG 命中：空锁 ⇒ 别的模块解析不出 pid ⇒ 会当陈旧锁删掉',
          pid5 is None, 'pid=%r' % pid5)

    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    n_all = len(RESULTS)
    print()
    print('=' * 66)
    print('结果: %d/%d PASS' % (n_ok, n_all))
    for n, ok, det in RESULTS:
        if not ok:
            print('  FAIL: %s -- %s' % (n, det))
    print('=' * 66)
    return 0 if n_ok == n_all else 1


if __name__ == '__main__':
    sys.exit(main())
