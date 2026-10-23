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
