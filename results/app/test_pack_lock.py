"""验证 `pack_v13.py` **在真实打包路径上确实取共享机器锁**（不跑真实大包）。

做法：造一个**极小的假客户包**（含 MUST 清单里必须存在的文件）⇒ 跑真实的
`pack_v13.py`（不带 `--dry-run`）⇒ 检查：
  1. 打包期间 `shared/MACHINE_LOCK` 存在且内容含 module=app-pack
  2. 打包结束后锁被释放（文件消失）
  3. 打包结论 PASS

⚠️ 用**独立的假包目录 + 独立 zip 输出**，绝不碰真实 v1.4 客户包。
⚠️ MUST 清单很长（MT/TTS 关键文件上百 MB）⇒ 这里**只验证「锁」**，
   故意让 MUST 检查 FAIL —— 锁的获取发生在 MUST 检查**之前**，不影响验证。
"""
import os
import subprocess
import sys
import threading
import time

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
import machine_lock_app as M

LOCK = M.LOCK
FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_locktest_pkg')
FAKE_ZIP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_locktest.zip')

PY = sys.executable

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('  [ OK ] ' if cond else '  [FAIL] ') + name +
          (('  -- ' + detail) if detail else ''))
    return bool(cond)


def watcher(stop_evt, seen):
    """后台轮询：记录打包期间锁文件是否存在 + 其内容。"""
    while not stop_evt.is_set():
        try:
            if os.path.isfile(LOCK):
                with open(LOCK, encoding='utf-8', errors='replace') as f:
                    seen.append(f.read())
        except Exception:
            pass
        time.sleep(0.05)


def main():
    os.makedirs(FAKE, exist_ok=True)
    with open(os.path.join(FAKE, 'dummy.txt'), 'w', encoding='utf-8') as f:
        f.write('lock test\n')

    print('[1] 起 watcher 监视 shared/MACHINE_LOCK')
    stop_evt = threading.Event()
    seen = []
    th = threading.Thread(target=watcher, args=(stop_evt, seen), daemon=True)
    th.start()

    print('[2] 跑真实 pack_v13.py（假包，MUST 检查预期 FAIL）')
    r = subprocess.run(
        [PY, '-u', os.path.join(_REPO, 'pack_v13.py'),
         '--pkg', FAKE, '--zip', FAKE_ZIP, '--prefix', 'LockTest'],
        capture_output=True, timeout=900)
    out = r.stdout.decode('utf-8', errors='replace')
    stop_evt.set()
    th.join(timeout=3)

    print('  打包输出（末 12 行）:')
    for line in out.strip().splitlines()[-12:]:
        print('    ' + line)
    print()

    check('打包进程启动过（lock 消息出现）', '[lock]' in out,
          'rc=%s' % r.returncode)
    check('取锁消息含 module: app-pack', 'module: app-pack' in out)
    check('watcher 观察到锁文件存在', len(seen) > 0, '观测 %d 次' % len(seen))
    if seen:
        check('锁内容含 pid/started', 'pid:' in seen[0] and 'started:' in seen[0],
              repr(seen[0])[:100])

    print()
    print('[3] 打包结束后锁已释放')
    check('shared/MACHINE_LOCK 不存在', not os.path.isfile(LOCK))
    st, info = M.lock_state(LOCK)
    check('lock_state = free', st == 'free', 'state=%s' % st)

    # 清理
    try:
        if os.path.isfile(FAKE_ZIP):
            os.remove(FAKE_ZIP)
    except Exception:
        pass
    try:
        os.remove(os.path.join(FAKE, 'dummy.txt'))
        os.rmdir(FAKE)
    except Exception:
        pass

    print()
    print('=' * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(' 结果：%d/%d PASS' % (passed, total))
    for n, ok, d in results:
        if not ok:
            print('   - %s  (%s)' % (n, d))
    print('=' * 60)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
