#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §5：**后台构建 v2.5 完整版客户包**（复制 → 定点同步 → 打包）。

纪律：
  · **不覆盖/不删除任何旧版本目录与 zip**（v2.4 原封不动）；
  · 复制先落到 **`.staging`** 再改名（⇒ 中断不会留下半个 v2.5）；
  · 定点同步（逐文件、唯一命中、SHA256 + ast.parse 复核）；
  · **持共享机器锁**（复制与压缩都是重 IO ⇒ 会干扰别的模块计时）；
  · 锁的存活判据用 ctypes `OpenProcess` + `GetExitCodeProcess`
    （**259 = STILL_ACTIVE = 活**；**探测失败 ⇒ 视为存活** ⇒ fail-closed）。

用法：
    python live_caption/_app116_build_v25.py            # 完整流程
    python live_caption/_app116_build_v25.py --stage copy   # 只复制+同步
    python live_caption/_app116_build_v25.py --stage pack   # 只打包
"""
import argparse
import ctypes
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')
STAGING = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5.staging')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5.zip')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
RESULTS = os.path.join(REPO, 'results', 'app')
LOG = os.path.join(RESULTS, 'app116_build_v25.log')


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def pid_alive(pid):
    """🔴 存活判据：**259 = STILL_ACTIVE = 活**；探测失败 ⇒ 视为存活。"""
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return k.GetLastError() != 87
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    try:
        raw = open(LOCK, encoding='utf-8').read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return {'raw': None, 'pid': None, 'unparsed': True}
    parts = raw.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p)
            break
    if pid is None:
        return {'raw': raw, 'pid': None, 'unparsed': True}
    return {'raw': raw, 'pid': pid, 'module': parts[0] if parts else '?'}


def acquire_lock(note):
    """排队等待 ⇒ 拿到锁写自己的内容。返回 lock_content 或 None。"""
    while True:
        own = lock_owner()
        if own is None:
            break
        pid = own.get('pid')
        if pid and pid == os.getpid():
            log('锁已经是自己的（pid=%d）' % pid)
            return own.get('raw')
        alive = pid_alive(pid) if pid else True
        if not alive:
            log('锁的持有者 pid=%s 已死 ⇒ 回收（fail-closed 反向：确认真死才回收）'
                % pid)
            try:
                os.remove(LOCK)
            except Exception:
                pass
            continue
        log('等机器锁（持有者 pid=%s 仍存活 ⇒ 不抢）' % pid)
        time.sleep(20)
    content = 'app %d %s %s' % (os.getpid(),
                                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                note)
    tmp = LOCK + '.tmp_app116'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp, LOCK)
    log('已取机器锁：%s' % content)
    return content


def release_lock(content):
    own = lock_owner()
    if own is None:
        return
    if own.get('raw') == content or (own.get('pid') == os.getpid()):
        try:
            os.remove(LOCK)
            log('已放机器锁')
        except Exception as e:
            log('放锁失败：%r' % (e,))
    else:
        log('🔴 锁内容已被别人改动（%r）⇒ **不删**（只删自己的）'
            % (own.get('raw'),))


def robocopy(src, dst):
    cmd = ['robocopy', src, dst, '/E', '/COPY:DAT', '/DCOPY:T',
           '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
    log('robocopy %s ⇒ %s' % (os.path.basename(src), os.path.basename(dst)))
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    # robocopy 的退出码 <8 = 成功
    if p.returncode >= 8:
        log('robocopy 退出码 %d（≥8 = 有错）\n%s\n%s'
            % (p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
        return False
    log('robocopy 完成（rc=%d）' % p.returncode)
    return True


def count_tree(root):
    n = 0
    total = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            n += 1
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return n, total


def stage_copy():
    if os.path.exists(DST):
        log('🔴 目标目录已存在：%s ⇒ **不覆盖**（旧版本目录不许覆盖）' % DST)
        return False
    if os.path.exists(STAGING):
        log('清掉上次的 staging 残留：%s' % STAGING)
        shutil.rmtree(STAGING, ignore_errors=True)
    t0 = time.time()
    if not robocopy(SRC, STAGING):
        return False
    n, total = count_tree(STAGING)
    log('复制完成：%d 文件 / %d B / %.1f s' % (n, total, time.time() - t0))
    os.rename(STAGING, DST)
    log('已改名：%s ⇒ %s' % (os.path.basename(STAGING), os.path.basename(DST)))
    return True


def stage_sync():
    py = sys.executable
    script = os.path.join(REPO, 'live_caption', '_app116_sync_to_v25.py')
    log('运行定点同步：%s' % os.path.basename(script))
    p = subprocess.run([py, script], capture_output=True, text=True,
                       timeout=1800, cwd=REPO)
    log(p.stdout[-6000:])
    if p.returncode != 0:
        log('🔴 同步失败 rc=%d\n%s' % (p.returncode, p.stderr[-3000:]))
        return False
    return True


def stage_pack():
    py = sys.executable
    packer = os.path.join(REPO, 'pack_v13.py')
    common = [py, packer, '--version', '2.5', '--pkg', DST, '--zip', ZIP,
              '--prefix', 'Confucius4_LiveCaption_v2.5',
              '--no-rename-pkg-dir', '--no-shortcut', '--no-lock']
    log('① dry-run（只读检查，不写 zip）')
    p = subprocess.run(common + ['--dry-run'], capture_output=True, text=True,
                       timeout=3600, cwd=REPO)
    log(p.stdout[-8000:])
    if p.stderr.strip():
        log('dry-run stderr: %s' % p.stderr[-2000:])
    log('② 正式打包')
    t0 = time.time()
    p = subprocess.run(common, capture_output=True, text=True,
                       timeout=10800, cwd=REPO)
    log(p.stdout[-12000:])
    if p.stderr.strip():
        log('pack stderr: %s' % p.stderr[-3000:])
    log('打包用时 %.1f s，rc=%d' % (time.time() - t0, p.returncode))
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='all',
                    choices=['all', 'copy', 'pack'])
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    log('=== APP-116 §5 构建 v2.5 开始（stage=%s）===' % args.stage)
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'src': SRC, 'dst': DST, 'zip': ZIP, 'stages': {}}

    if args.stage in ('all', 'copy'):
        content = acquire_lock('app116-build-v25')
        try:
            ok = stage_copy() and stage_sync()
        finally:
            release_lock(content)
        rep['stages']['copy_sync'] = ok
        if not ok:
            log('🔴 复制/同步失败 ⇒ 中止')
            return 1
    if args.stage in ('all', 'pack'):
        content = acquire_lock('app116-pack-v25')
        try:
            ok = stage_pack()
        finally:
            release_lock(content)
        rep['stages']['pack'] = ok
        if not ok:
            log('🔴 打包失败')
            return 1

    if os.path.isdir(DST):
        n, total = count_tree(DST)
        rep['pkg_files'] = n
        rep['pkg_bytes'] = total
    if os.path.isfile(ZIP):
        rep['zip_bytes'] = os.path.getsize(ZIP)
    out = os.path.join(RESULTS, 'app116_build_v25_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)
    log('=== 构建流程结束 ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
