"""App 模块共享机器锁的**安全性**自测（不碰真实共享锁）。

测 4 件事：
  1. 原子创建：两个 LockHeld 并抢 ⇒ 只有一个能拿到（O_CREAT|O_EXCL）
  2. **fail-closed**：锁里的 PID 是**活着的**（本进程）⇒ 状态必须是 'held'，
     第二个进程必须**等待**而**不能回收**
  3. **fail-closed**：PID 不存在 ⇒ 状态 'stale_pid' ⇒ 可回收
  4. 释放只删自己那份（内容被他人改动时不删）

⚠️ 全程用**临时目录**下的锁文件，绝不碰 `shared/MACHINE_LOCK`。
"""
import os
import subprocess
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
import machine_lock_app as M

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('  [ OK ] ' if cond else '  [FAIL] ') + name +
          (('  -- ' + detail) if detail else ''))
    return bool(cond)


def main():
    tmp = tempfile.mkdtemp(prefix='lock_app_test_')
    lock = os.path.join(tmp, 'MACHINE_LOCK')
    print('临时锁文件:', lock)
    print()

    print('[1] 原子创建 + 释放')
    lk = M.LockHeld(lock_path=lock, module="app-test", verbose=False, timeout=5, poll=0.3)
    ok = lk.acquire()
    check('第 1 次取锁成功', ok)
    check('锁文件已创建', os.path.isfile(lock))
    st, info = M.lock_state(lock)
    check('状态 = held', st == 'held', 'state=%s module=%s pid=%s'
          % (st, info.get('module'), info.get('pid')))
    check('锁内容含 module/pid/started',
          all(k in (info.get('raw') or '') for k in ('module:', 'pid:', 'started:')),
          repr(info.get('raw'))[:120])

    print()
    print('[2] fail-closed：活锁不可被回收')
    # 第二个 LockHeld 拿不到（必须等），且**不能**删掉第一个的锁
    lk2 = M.LockHeld(lock_path=lock, module='app-test2', timeout=3, poll=0.5,
                     verbose=False)
    ok2 = lk2.acquire()
    check('第 2 次取锁失败（等待超时）', not ok2)
    check('第一个的锁仍在（未被误回收）', os.path.isfile(lock))
    st2, _ = M.lock_state(lock)
    check('状态仍是 held（fail-closed）', st2 == 'held', 'state=%s' % st2)
    check('锁内容未被改动（仍是第一个持有者）',
          'module: app-test\n' in (open(lock, encoding='utf-8').read()))

    print()
    print('[3] fail-closed：PID 不存在 ⇒ stale_pid 可回收')
    with open(lock, 'w', encoding='utf-8') as f:
        f.write('module: app-dead\npid: 999999\nstarted: 2026-10-24 03:00:00\n')
    st3, info3 = M.lock_state(lock)
    check('状态 = stale_pid', st3 == 'stale_pid',
          'state=%s pid=%s' % (st3, info3.get('pid')))

    print()
    print('[4] 释放：只删内容与自己一致的文件')
    lk3 = M.LockHeld(lock_path=lock, module='app-test3', verbose=False, timeout=5, poll=0.3)
    lk3.acquire()
    # 模拟别人改写了锁内容
    with open(lock, 'w', encoding='utf-8') as f:
        f.write('module: someone-else\npid: 12345\nstarted: 2026-10-24 03:00:00\n')
    released = lk3.release()
    check('内容不一致时不删除', (not released) and os.path.isfile(lock))
    os.remove(lock)

    print()
    print('[5] 子进程并发抢锁：只有一个能拿到')
    lock2 = os.path.join(tmp, 'LOCK2')
    script = (
        "import sys, os\n"
        "sys.path.insert(0, %r)\n"
        "import machine_lock_app as M\n"
        "lk = M.LockHeld(lock_path=%r, module='sub-'+sys.argv[1], timeout=1,\n"
        "                 poll=0.2, verbose=False)\n"
        "print('got' if lk.acquire() else 'nope')\n"
    ) % (_REPO, lock2)
    p1 = subprocess.Popen([sys.executable, '-c', script, 'a'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen([sys.executable, '-c', script, 'b'],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o1 = p1.communicate()[0].decode('utf-8', 'replace').strip()
    o2 = p2.communicate()[0].decode('utf-8', 'replace').strip()
    got = [x for x in (o1, o2) if x == 'got']
    check('两个子进程只有一个拿到锁', len(got) == 1, '%r / %r' % (o1, o2))

    print()
    print('[6] README_LOCK.md 单行格式（MT 通知 2 的事故形态）：'
          '`asr PID 14644 started ...`')
    # 🔴 事故形态：别的模块按 README_LOCK.md 写锁（单行）⇒ 旧版 App 解析不出 PID
    #    ⇒ lock_state 返回 'unreadable' ⇒ fail-closed 永久等待（MT 实测空等 14 分钟）。
    lock3 = os.path.join(tmp, 'LOCK3')
    with open(lock3, 'w', encoding='utf-8') as f:
        f.write('asr PID 999999 started 2026-10-24 15:13:06\n')
    info6 = M._read_lock(lock3)
    check('README 格式能解析出 module/pid/started_ts',
          info6.get('module') == 'asr' and info6.get('pid') == 999999
          and info6.get('started_ts') is not None,
          'module=%s pid=%s started_ts=%s' % (info6.get('module'),
                                              info6.get('pid'),
                                              info6.get('started_ts')))
    st6, _ = M.lock_state(lock3)
    check('README 格式 + PID 已死 ⇒ stale_pid（可回收）',
          st6 == 'stale_pid', 'state=%s' % st6)
    with open(lock3, 'w', encoding='utf-8') as f:
        f.write('tts PID %d started 2026-10-25 03:00:00\n' % os.getpid())
    st6b, _ = M.lock_state(lock3)
    check('README 格式 + PID 存活 ⇒ held（必须等，fail-closed）',
          st6b == 'held', 'state=%s' % st6b)
    os.remove(lock3)

    print()
    print('[7] GBK 编码的锁（别的模块用 Windows ANSI 写）')
    lock4 = os.path.join(tmp, 'LOCK4')
    with open(lock4, 'w', encoding='gbk') as f:
        f.write('会议 PID %d started 2026-10-25 03:00:00\n' % os.getpid())
    info7 = M._read_lock(lock4)
    check('GBK 锁能解析出 pid/started_ts',
          info7.get('pid') == os.getpid() and info7.get('started_ts') is not None,
          'module=%r pid=%r' % (info7.get('module'), info7.get('pid')))
    os.remove(lock4)

    print()
    print('[8] App 自己写出的 payload ⇒ 两种格式都能被解析（自洽）')
    lock5 = os.path.join(tmp, 'LOCK5')
    ok8, payload8 = M.acquire(lock_path=lock5, module='app-selftest',
                              timeout=5, verbose=False)
    info8 = M._read_lock(lock5) if ok8 else {}
    st8, _ = M.lock_state(lock5) if ok8 else ('none', {})
    check('双格式 payload 自解析一致',
          ok8 and info8.get('module') == 'app-selftest'
          and info8.get('pid') == os.getpid() and st8 == 'held',
          'ok=%s module=%s pid=%s state=%s' % (ok8, info8.get('module'),
                                               info8.get('pid'), st8))
    check('payload 同时含 README 单行与 key-value 两套字段',
          ' PID ' in (payload8 or '') and 'module:' in (payload8 or '')
          and 'pid:' in (payload8 or '') and 'started:' in (payload8 or ''),
          repr(payload8)[:160])
    M.release(payload8, lock_path=lock5, verbose=False)
    check('释放后锁文件已删除', not os.path.exists(lock5))

    print()
    print('=' * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(' 结果：%d/%d PASS' % (passed, total))
    if passed != total:
        for n, ok, d in results:
            if not ok:
                print('   - %s  (%s)' % (n, d))
    print('=' * 60)

    try:
        os.remove(lock2)
    except Exception:
        pass
    try:
        os.rmdir(tmp)
    except Exception:
        pass
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
