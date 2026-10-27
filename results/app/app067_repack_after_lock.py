#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§67 —— 等锁 → 持锁重打 zip → 只读本地一致性检查（**不跑全量复核、不跑 FTP**）。

🔴🔴 【2026-10-27 11:05 用户新口径】
  **以后不做一致性校验（`verify_pkg_zip.py`）、不开 FTP 服务**
  ⇒ 本脚本**不**跑 `verify_pkg_zip.py`（那要 4 min 42 s 全量 SHA256）
  ⇒ 本脚本**不**跑 `publish_ftp.py`、**不**开 FTP 服务
  ⇒ 替代的**只读本地**检查（秒级）：
     ① 「zip ⇄ 包目录 `.py` 逐字节 diff 计数 = 0」
     ② 「`HEAD` ⇄ 包目录 关键 `.py` 归一化后一致」
  ⇒ 「已交付」口径 = **包目录 + zip 已含最新代码，且该代码已入库（`HEAD`）**

🔴 锁纪律：
  - 锁路径**硬编码绝对路径** `C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK`；
  - **绝不删活锁**（唯一「死」判据 = `GetLastError()==87`）；
  - 探测失败**一律视为存活**。

用法：
    python app067_repack_after_lock.py [--max-wait 7200] [--dry-run]
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
LOG = os.path.join(HERE, '_app067_repack.log')


def log(msg: str) -> None:
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        with io.open(LOG, 'a', encoding='utf-8', newline='') as f:
            f.write(line + '\n')
    except Exception:
        pass


def lock_state():
    """返回 (存在?, 活?, 描述)。🔴 **绝不删活锁**。"""
    if not os.path.exists(LOCK):
        return False, False, '无锁'
    try:
        txt = io.open(LOCK, encoding='utf-8', errors='replace').read()
    except Exception as e:
        return True, True, '锁读不出(%s) ⇒ 视为活锁' % str(e)[:40]
    m = re.search(r'pid\s*[:=]\s*(\d+)', txt, re.I)
    if not m:
        return True, True, '锁 PID 读不出 ⇒ 视为活锁'
    pid = int(m.group(1))
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        err = ctypes.windll.kernel32.GetLastError()
        if err == 87:
            return True, False, '锁 PID %d 已死(err=87) ⇒ 孤儿锁' % pid
        return True, True, '锁 PID %d 探测失败(err=%d) ⇒ 视为活锁' % (pid, err)
    c = ctypes.c_ulong()
    if not k.GetExitCodeProcess(h, ctypes.byref(c)):
        k.CloseHandle(h)
        return True, True, 'GetExitCodeProcess 失败 ⇒ 视为活锁'
    k.CloseHandle(h)
    return True, c.value == 259, ('锁 PID %d exit=%s ⇒ %s'
                                 % (pid, c.value,
                                    '活锁' if c.value == 259 else '孤儿锁'))


def wait_idle(max_wait_s: float, poll_s: float = 15.0):
    t0 = time.time()
    last = None
    while time.time() - t0 < max_wait_s:
        exists, alive, desc = lock_state()
        if desc != last:
            log(desc)
            last = desc
        if not exists:
            log('✅ 锁已释放 ⇒ 可以持锁打包')
            return True
        if exists and not alive:
            log('🧹 孤儿锁（PID 已死）⇒ 回收')
            try:
                os.remove(LOCK)
                log('   已删除')
            except Exception as e:
                log('   ⚠️ 回收失败: %s' % str(e)[:80])
        time.sleep(poll_s)
    log('🔴 等待超时（%.0fs）⇒ 放弃' % max_wait_s)
    return False


def local_consistency(pkg: str, zip_path: str):
    """🔴 只读本地检查（**替代** `verify_pkg_zip.py` 的全量复核）。

    ① zip ⇄ 包目录 `.py` 逐字节 diff 计数
    ② HEAD ⇄ 包目录 关键 `.py` 归一化后一致
    """
    res = {'py_diff': None, 'head_match': None, 'n_py': 0, 'mismatch': []}
    if not zipfile.is_zipfile(zip_path):
        res['py_diff'] = -1
        res['err'] = 'zip 不可读：%s' % zip_path
        return res
    pkg_app = os.path.join(pkg, 'app')
    pkg_py = {}
    for root, _dirs, files in os.walk(pkg_app):
        for fn in files:
            if fn.endswith('.py'):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, pkg).replace(os.sep, '/')
                pkg_py[rel] = full
    res['n_py'] = len(pkg_py)

    diff = 0
    mismatch = []
    skipped_dev = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        for rel, full in pkg_py.items():
            # 🔴 `_` 前缀 = 开发期专用脚本 ⇒ `pkg_exclude.is_app_dev_only`
            #    **本来就不该进包** ⇒ 「zip 内缺失」是**正确行为**，不算差异。
            fn = os.path.basename(rel)
            if fn.startswith('_'):
                skipped_dev.append(rel)
                continue
            # zip 内顶层目录名 = 包目录名（Confucius4_LiveCaption_v1.5）
            cand = [n for n in names if n.endswith('/' + rel) or n == rel]
            if not cand:
                diff += 1
                mismatch.append('%s: zip 内缺失' % rel)
                continue
            zn = cand[0]
            zdata = zf.read(zn)
            with open(full, 'rb') as f:
                pdata = f.read()
            if zdata != pdata:
                diff += 1
                mismatch.append('%s: 内容不一致（zip %d B vs 包 %d B）'
                                % (rel, len(zdata), len(pdata)))
    res['py_diff'] = diff
    res['mismatch'] = mismatch[:20]
    res['skipped_dev'] = skipped_dev

    # ② HEAD ⇄ 包目录
    head_files = []
    try:
        out = subprocess.run(['git', 'ls-tree', '--name-only', 'HEAD', 'live_caption/'],
                             cwd=REPO, capture_output=True).stdout.decode('utf-8')
        head_files = [x.strip() for x in out.splitlines() if x.strip().endswith('.py')]
    except Exception as e:
        res['head_match'] = -1
        res['err'] = str(e)[:80]
        return res
    same = tot = 0
    bad = []
    norm = lambda b: b.replace(b'\r\n', b'\n')
    for rel in head_files:
        fn = os.path.basename(rel)
        pkg_f = os.path.join(pkg_app, fn)
        if not os.path.exists(pkg_f):
            continue
        tot += 1
        g = subprocess.run(['git', 'show', 'HEAD:%s' % rel],
                           cwd=REPO, capture_output=True).stdout
        with open(pkg_f, 'rb') as f:
            p = f.read()
        if norm(g) == norm(p):
            same += 1
        else:
            bad.append(fn)
    res['head_match'] = '%d/%d' % (same, tot)
    res['head_bad'] = bad
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-wait', type=float, default=7200.0)
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, REPO)
    sys.path.insert(0, HERE)
    import pkg_paths
    pkg = args.pkg or pkg_paths.discover_pkg_dir()
    zip_path = pkg + '.zip'

    log('=' * 70)
    log('§67 等锁 → 持锁重打 zip（**不跑全量复核 / 不跑 FTP**）')
    log('包目录 = %s' % pkg)
    log('zip    = %s' % zip_path)
    log('模式   = %s' % ('DRY-RUN' if args.dry_run else '实际打包'))

    if args.dry_run:
        r = local_consistency(pkg, zip_path)
        log('（当前 zip 的只读本地检查）%s' % r)
        return 0

    if not wait_idle(args.max_wait):
        log('🔴 未拿到锁 ⇒ 本轮不打包')
        return 1

    # 🔴 打包脚本**自带** `machine_lock_app.LockHeld(module='app-pack')` 守门
    #    ⇒ 这里不再自己写锁文件（避免两个写者互相覆盖）。
    log('🔒 启动 pack_v13.py（自带取锁 + 安静窗口双闸门）…')
    t0 = time.time()
    p = subprocess.run([sys.executable, 'pack_v13.py', '--pkg', pkg,
                        '--zip', zip_path],
                       cwd=REPO, capture_output=True)
    dt = time.time() - t0
    tail = p.stdout.decode('utf-8', 'replace')[-4000:]
    log('打包退出码 = %d / 耗时 %.1f s' % (p.returncode, dt))
    log('--- pack_v13.py 输出尾部 ---')
    for ln in tail.splitlines()[-40:]:
        log('   ' + ln)
    if p.returncode != 0:
        log('🔴🔴 打包失败 ⇒ 不做任何交付结论')
        return p.returncode

    # 只读本地检查
    r = local_consistency(pkg, zip_path)
    log('--- 只读本地一致性检查（**替代** verify_pkg_zip.py）---')
    log('  zip ⇄ 包目录 `.py` diff 计数 = %s（共 %d 个 .py）'
        % (r['py_diff'], r['n_py']))
    for m in r.get('mismatch', []):
        log('    ✗ ' + m)
    log('  HEAD ⇄ 包目录 关键 .py = %s' % r['head_match'])
    for b in r.get('head_bad', []):
        log('    ✗ ' + b)

    st = os.stat(zip_path)
    sha = hashlib.sha256()
    with open(zip_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            sha.update(chunk)
    log('zip 指纹: %d B / SHA256 %s / mtime %s'
        % (st.st_size, sha.hexdigest(),
           time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))))

    ok = (r['py_diff'] == 0 and isinstance(r['head_match'], str)
          and r['head_match'].split('/')[0] == r['head_match'].split('/')[1])
    log('结论: %s' % ('PASS（zip 已含最新代码且已入库）' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
