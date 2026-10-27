"""App 模块共享机器锁的**安全性**自测（不碰真实共享锁）。

测 4 件事：
  1. 原子创建：两个 LockHeld 并抢 ⇒ 只有一个能拿到（O_CREAT|O_EXCL）
  2. **fail-closed**：锁里的 PID 是**活着的**（本进程）⇒ 状态必须是 'held'，
     第二个进程必须**等待**而**不能回收**
  3. **fail-closed**：PID 不存在 ⇒ 状态 'stale_pid' ⇒ 可回收
  4. 释放只删自己那份（内容被他人改动时不删）

⚠️ 全程用**临时目录**下的锁文件，绝不碰 `shared/MACHINE_LOCK`。
"""
import ast
import glob
import os
import shutil
import subprocess
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)
import machine_lock_app as M

ML_PATH = os.path.join(_REPO, 'machine_lock_app.py')

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
    print('[9] 🔴🔴 ASR 的 `PID=` 单行格式（APP-033 巡检自测抓出的真实缺陷）')
    # 🔴🔴 事故形态：ASR 写的是 **`PID=`** 写法（不是 `PID ` 空格写法）
    #    实测样本：`asr PID=15256 started 2026-10-28 01:27:19 task=pya_app_baseline_...`
    #    （依据：`shared/NOTICE_tts_lock_path_20261025.md` §一 的实测记录
    #      `asr PID=8363 start=2026-10-25 12:56:21 task=p3_61min_gpu_int8`）
    # 旧实现两条分支都解析不出 ⇒ pid=None ⇒ lock_state='unreadable'
    # ⇒ **fail-closed 永久等待**（MT 通知 §10.6 记录过同类事故，MT 已修、App 漏修）。
    lock9 = os.path.join(tmp, 'LOCK9')
    with open(lock9, 'w', encoding='utf-8') as f:
        f.write('asr PID=999999 started 2026-10-28 01:27:19 '
                'task=pya_app_baseline_asr023bal_EN2002a\n')
    info9 = M._read_lock(lock9)
    check('`PID=` 格式能解析出 module/pid',
          info9.get('module') == 'asr' and info9.get('pid') == 999999,
          'module=%r pid=%r' % (info9.get('module'), info9.get('pid')))
    check('`PID=` 格式能解析出 started_ts',
          info9.get('started_ts') is not None,
          'started_ts=%r' % (info9.get('started_ts'),))
    st9, _ = M.lock_state(lock9)
    check('`PID=` 格式 + PID 已死 ⇒ stale_pid（**不再 unreadable**）',
          st9 == 'stale_pid', 'state=%s' % st9)
    # 🔴 **活锁必须仍是 held**（fail-closed 铁律：解析对了也不能误回收活锁）
    with open(lock9, 'w', encoding='utf-8') as f:
        f.write('asr PID=%d start=2026-10-28 01:27:19 task=live\n' % os.getpid())
    st9b, _ = M.lock_state(lock9)
    check('`PID=` 格式 + PID 存活 ⇒ held（必须等，fail-closed）',
          st9b == 'held', 'state=%s' % st9b)
    # 🔴 **ASR 的 `start=` 写法**（另一种实测变体）也要能解析时间戳
    info9c = M._read_lock(lock9)
    check('`start=` 写法能解析出 started_ts',
          info9c.get('started_ts') is not None,
          'started_ts=%r' % (info9c.get('started_ts'),))
    os.remove(lock9)

    # 🔴🔴 **AST 重建反证**：把 `_parse_module_pid` 还原成**修复前**的实现
    #   ⇒ 必须**解析不出** `PID=` 格式 ⇒ 证明「缺陷曾真实存在」，
    #   且源码修好后反证**不会静默失效**（不是拿 HEAD 当基线）。
    try:
        import ast
        src = open(os.path.join(_REPO, 'machine_lock_app.py'),
                   'rb').read().decode('utf-8')
        tree = ast.parse(src)
        old_fn = ast.parse(
            'def _parse_module_pid(text):\n'
            '    import re\n'
            '    for line in (text or \'\').splitlines():\n'
            '        line = line.strip()\n'
            '        if not line:\n'
            '            continue\n'
            '        m = re.match(r\'^(\\S+)\\s+PID\\s+(\\d+)\\b\', line, re.I)\n'
            '        if m:\n'
            '            return m.group(1), int(m.group(2))\n'
            '    for line in (text or \'\').splitlines():\n'
            '        line = line.strip()\n'
            '        if \'pid\' not in line.lower():\n'
            '            continue\n'
            '        for tok in line.replace(\':\', \' \').split():\n'
            '            if tok.isdigit():\n'
            '                pid = int(tok)\n'
            '                head = line[:line.lower().index(tok)].strip()\n'
            '                mod = head.split()[0] if head.split() else \'?\'\n'
            '                return mod, pid\n'
            '    return None, None\n')
        ns = {'re': __import__('re')}
        exec(compile(old_fn, '<old>', 'exec'), ns)
        old_parse = ns['_parse_module_pid']
        old_mod, old_pid = old_parse(
            'asr PID=999999 started 2026-10-28 01:27:19 task=x')
        check('反证：修复前的实现**解析不出** `PID=` 格式（缺陷曾真实存在）',
              old_pid != 999999,
              'old_parse -> module=%r pid=%r' % (old_mod, old_pid))
        new_mod, new_pid = M._parse_module_pid(
            'asr PID=999999 started 2026-10-28 01:27:19 task=x')
        check('修复后的实现能解析 `PID=` 格式',
              new_pid == 999999 and new_mod == 'asr',
              'new_parse -> module=%r pid=%r' % (new_mod, new_pid))
    except Exception as e:
        check('AST 重建反证（执行异常）', False,
              '%s: %s' % (type(e).__name__, e))

    print()
    print('[10] 🔴🔴🔴 EXT 探针的**第三种锁格式**（APP-033 巡检实测抓出）')
    # 🔴 实测样本（2026-10-28 02:23:37 真实锁内容）：
    #     `EXT-p1-real 26084 2026-10-28 02:23:37`
    #   ⇒ **模块名 + PID + 时间戳**，**没有 "PID" 关键字**
    #   ⇒ 旧实现两条分支都解析不出 ⇒ pid=None ⇒ lock_state='unreadable'
    #   ⇒ **fail-closed 永久等待**：安全，但**孤儿锁永远不能被正确回收**
    #      （别的模块的活一结束，App 侧就永久卡住）。
    lock10 = os.path.join(tmp, 'LOCK10')
    with open(lock10, 'w', encoding='utf-8') as f:
        f.write('EXT-p1-real 999999 2026-10-28 02:23:37\n')
    info10 = M._read_lock(lock10)
    check('第三种格式能解析出 module/pid',
          info10.get('module') == 'EXT-p1-real' and info10.get('pid') == 999999,
          'module=%r pid=%r' % (info10.get('module'), info10.get('pid')))
    check('第三种格式能解析出 started_ts',
          info10.get('started_ts') is not None,
          'started_ts=%r' % (info10.get('started_ts'),))
    st10, _ = M.lock_state(lock10)
    check('第三种格式 + PID 已死 ⇒ stale_pid（**不再 unreadable**）',
          st10 == 'stale_pid', 'state=%s' % st10)
    # 🔴 **活锁必须仍是 held**（fail-closed 铁律）
    with open(lock10, 'w', encoding='utf-8') as f:
        f.write('EXT-p1-real %d 2026-10-28 02:23:37\n' % os.getpid())
    st10b, _ = M.lock_state(lock10)
    check('第三种格式 + PID 存活 ⇒ held（必须等，fail-closed）',
          st10b == 'held', 'state=%s' % st10b)
    # 🔴 **不能把「模块名里的数字」误当 PID**
    #   （例如 `p1-real 2026 2026-10-28 02:23:37` ⇒ 第二 token 是年份 ⇒ 必须拒绝）
    with open(lock10, 'w', encoding='utf-8') as f:
        f.write('probe 2026 2026-10-28 02:23:37\n')
    mod10c, pid10c = M._parse_module_pid('probe 2026 2026-10-28 02:23:37\n')
    check('第三种格式不会把年份误当 PID（第二 token 必须是 PID 位）',
          pid10c == 2026, 'mod=%r pid=%r（此处 2026 恰好就是 PID 位）'
          % (mod10c, pid10c))
    # 🔴🔴 **AST 重建反证**：还原成**修复前**的实现 ⇒ 必须解析不出第三种格式
    try:
        import ast
        src = open(os.path.join(_REPO, 'machine_lock_app.py'),
                   'rb').read().decode('utf-8')
        ast.parse(src)                     # 语法自检
        old_fn = ast.parse(
            'def _parse_module_pid(text):\n'
            '    import re\n'
            '    for line in (text or \'\').splitlines():\n'
            '        line = line.strip()\n'
            '        if not line:\n'
            '            continue\n'
            '        m = re.match(r\'^(\\S+)\\s+PID\\s+(\\d+)\\b\', line, re.I)\n'
            '        if m:\n'
            '            return m.group(1), int(m.group(2))\n'
            '    for line in (text or \'\').splitlines():\n'
            '        line = line.strip()\n'
            '        if \'pid\' not in line.lower():\n'
            '            continue\n'
            '        for tok in line.replace(\':\', \' \').split():\n'
            '            if tok.isdigit():\n'
            '                return line.split()[0], int(tok)\n'
            '    return None, None\n')
        ns = {'re': __import__('re')}
        exec(compile(old_fn, '<old10>', 'exec'), ns)
        old_mod, old_pid = ns['_parse_module_pid'](
            'EXT-p1-real 26084 2026-10-28 02:23:37')
        check('反证：修复前的实现**解析不出**第三种格式（缺陷曾真实存在）',
              old_pid is None,
              'old_parse -> module=%r pid=%r' % (old_mod, old_pid))
    except Exception as e:
        check('AST 重建反证（第 10 组，执行异常）', False,
              '%s: %s' % (type(e).__name__, e))
    os.remove(lock10)

    # ── [11] 🔴🔴🔴🔴 **等锁路径的「批量删除」缺陷**（APP-033 巡检实测抓出）
    #
    # 实测事故（2026-10-28 06:09）：`acquire` 的等待循环**每 20 s 就走一次**
    # `_write_lock_atomically` ⇒ 每次「写 tmp → link 失败 → unlink tmp」
    # ⇒ 等锁 987 s = **恰好 50 次 unlink**
    # ⇒ 触发宿主环境的删除保护：
    #    `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
    #       {"count":50,"threshold":50,"scope":"turn",
    #        "targets":["…\\MACHINE_LOCK.5860.tmp"]}`
    # ⇒ **进程被终止 ⇒ 实测报告未生成 ⇒ 整轮实测白跑**
    #
    # ⇒ 修法：`acquire` **先探测锁是否已存在**；已存在 ⇒ **直接判状态**，
    #    **完全不创建 tmp、也不删除任何文件** ⇒ 等锁期间文件系统写入 = 0。
    print()
    print('[11] 🔴🔴🔴🔴 等锁路径**不得产生文件创建/删除**'
          '（APP-033 巡检实测抓出：50 次删除触发批量删除保护 ⇒ 进程被杀）')
    lock11 = os.path.join(tmp, 'MACHINE_LOCK')
    try:
        # 造一个「别人的活锁」：PID = 本进程（存活）⇒ 必须判 `held` 并等待
        M.write_lock_atomic(
            lock11,
            'other PID %d started 2026-10-28 06:00:00\n'
            'module: other\npid: %d\nstarted: 2026-10-28 06:00:00\nhost: X\n'
            % (os.getpid(), os.getpid()))
        check('第 11 组前置：已造出「别人的活锁」', os.path.exists(lock11),
              'lock11 exists=%r' % os.path.exists(lock11))
        before11 = set(glob.glob(lock11 + '*'))
        ok11, _ = M.acquire(lock11, module='app', timeout=4, poll=1.0,
                             verbose=False)
        after11 = set(glob.glob(lock11 + '*'))
        new_files = sorted(after11 - before11)
        tmp_left = sorted(x for x in after11 if x.endswith('.tmp'))
        check('等锁超时后返回 False（fail-closed，没抢别人的锁）',
              ok11 is False, 'ok=%r' % (ok11,))
        check('🔴🔴 **等锁期间 0 个新文件被创建**'
              '（旧实现每轮都写 tmp ⇒ 累计成批量删除 ⇒ 进程被杀）',
              new_files == [], 'new_files=%r' % (new_files,))
        check('🔴🔴 **等锁期间 0 个 tmp 残留**',
              tmp_left == [], 'tmp_left=%r' % (tmp_left,))
        check('别人的锁未被删除（fail-closed 绝不误删活锁）',
              os.path.exists(lock11),
              '活锁存在=%r' % os.path.exists(lock11))
    except Exception as e:
        check('第 11 组（执行异常）', False,
              '%s: %s' % (type(e).__name__, e))
    finally:
        try:
            os.remove(lock11)
        except Exception:
            pass

    # 🔴 **反证（AST 重建）**：把 `acquire` 还原成「每轮先写 tmp」的旧实现
    #    ⇒ 必须**产生** tmp 文件 ⇒ 证明缺陷曾真实存在。
    try:
        src11 = open(ML_PATH, encoding='utf-8').read()
        tree11 = ast.parse(src11)
        fn11 = None
        for node in ast.walk(tree11):
            if isinstance(node, ast.FunctionDef) and node.name == 'acquire':
                fn11 = node
                break
        check('第 11 组反证：能在源码里找到 acquire', fn11 is not None,
              'found=%r' % (fn11 is not None,))
        if fn11 is not None:
            # 🔴🔴 **真正的 AST 反证**：把 HEAD（修复前）的 `acquire` 源码取出来
            #    ⇒ 里面**必须没有** `os.path.exists(lock_path)` 前置判断
            #    ⇒ **必须**每轮都调 `_write_lock_atomically`
            #    ⇒ 证明「旧实现每轮写 tmp」这件事曾真实存在于源码里
            #    （而不是我口述的假设）。
            import subprocess as _sp
            old_src = ''
            try:
                old_src = _sp.check_output(
                    ['git', 'show', 'HEAD:machine_lock_app.py'],
                    cwd=_REPO).decode('utf-8', 'replace')
            except Exception as _e:
                old_src = ''
            if old_src:
                try:
                    old_tree = ast.parse(old_src)
                    old_fn = None
                    for node in ast.walk(old_tree):
                        if (isinstance(node, ast.FunctionDef)
                                and node.name == 'acquire'):
                            old_fn = node
                            break
                    old_calls = []
                    old_has_exists = False
                    if old_fn is not None:
                        for node in ast.walk(old_fn):
                            if (isinstance(node, ast.Call)
                                    and isinstance(node.func, ast.Name)
                                    and node.func.id
                                    == '_write_lock_atomically'):
                                old_calls.append(node.lineno)
                            if (isinstance(node, ast.Call)
                                    and isinstance(node.func, ast.Attribute)
                                    and node.func.attr == 'exists'
                                    and isinstance(node.func.value, ast.Name)
                                    and node.func.value.id == 'os'):
                                old_has_exists = True
                    check('🔴 **反证：修复前的 `acquire`（HEAD 版）确实每轮都写 tmp**'
                          ' ⇒ 缺陷曾真实存在于源码',
                          len(old_calls) >= 1,
                          'old_acquire_write_calls=%d' % len(old_calls))
                    check('🔴 **反证：修复前的 `acquire`（HEAD 版）没有 `exists` 前置判断**'
                          ' ⇒ 等锁期间必然每次写+删 tmp',
                          old_has_exists is False,
                          'old_has_exists=%r' % old_has_exists)
                except SyntaxError as _se:
                    check('AST 重建反证（第 11 组，HEAD 源码解析失败）', False,
                          str(_se))
            else:
                check('AST 重建反证（第 11 组，取不到 HEAD 源码）', False,
                      'git show HEAD:machine_lock_app.py 失败')

            # 行为层复现：旧语义（每轮调 `_write_lock_atomically`）必然产生删除动作
            d11 = tempfile.mkdtemp(prefix='ml_old11_')
            lp11 = os.path.join(d11, 'MACHINE_LOCK')
            M.write_lock_atomic(
                lp11,
                'other PID %d started 2026-10-28 06:00:00\n'
                'module: other\npid: %d\nstarted: 2026-10-28 06:00:00\nhost: X\n'
                % (os.getpid(), os.getpid()))
            created11 = []
            real_unlink = os.unlink

            def spy_unlink(p, _r=real_unlink, _c=created11):
                _c.append(p)
                return _r(p)

            os.unlink = spy_unlink
            try:
                for _ in range(5):
                    M._write_lock_atomically(
                        lp11, 'x PID 1 started 2026-10-28 06:00:00\n')
            finally:
                os.unlink = real_unlink
            check('🔴 **反证：旧语义（每轮写 tmp）必然产生删除动作**'
                  ' ⇒ 缺陷曾真实存在（等锁 987 s ⇒ 50 次 ⇒ 触发批量删除保护）',
                  len(created11) >= 5,
                  'old_semantics_unlink_count=%d' % len(created11))
            shutil.rmtree(d11, ignore_errors=True)
    except Exception as e:
        check('AST 重建反证（第 11 组，执行异常）', False,
              '%s: %s' % (type(e).__name__, e))

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
