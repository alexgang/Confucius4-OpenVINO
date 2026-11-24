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


def _create_lock_exclusive(content):
    """🔴🔴🔴 **原子 + 独占**创建锁文件（APP-132 修法，2026-11-24）。

    **为什么不是 `os.replace(tmp, LOCK)`**（旧实现）：
      `os.replace` 会**覆盖**已存在的锁 ⇒ 两个进程都以为拿到了锁
      ⇒ 同时占机器（TOCTOU：都看到"不存在" ⇒ 都 replace ⇒ 后写者覆盖前者）。

    **为什么不是 `os.open(O_CREAT|O_EXCL)` 再写内容**：
      那是「先建空文件、之后才写内容」⇒ 存在一个「文件已存在、内容还是空的」
      时间窗口 ⇒ 别的模块在窗口里读锁 ⇒ **解析不出 pid** ⇒ 判成"陈旧锁"
      ⇒ `os.remove` **删掉我们的活锁** ⇒ 两个模块同时跑。
      （仓库根 `machine_lock_app.py` 第 405~413 行有逐字记录 + 实测事故。）

    ✅ **本实现**：先把内容**完整**写进 tmp ⇒ `os.link(tmp, LOCK)` 原子地
    建立硬链接 ⇒ 目标已存在时抛 `FileExistsError` ⇒ **独占**（绝不覆盖），
    且别的模块**永远看不到半成品锁**（内容要么完整、要么文件不存在）。
    依据：`shared/NOTICE_tts_lock_atomic_20261026.md`（与仓库根
    `machine_lock_app._write_lock_atomically` 同源同法）。

    返回 True = 拿到锁；False = 别人已持有（**不抢、不覆盖**）。
    """
    tmp = '%s.tmp_app116_%d' % (LOCK, os.getpid())
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, LOCK)
        except FileExistsError:
            return False            # 别人先拿到 ⇒ 独占失败
        except OSError as e:
            log('🔴 原子建锁失败（%r）⇒ 按 fail-closed 等待' % (e,))
            return False
        return True
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def acquire_lock(note):
    """排队等待 ⇒ 拿到锁写自己的内容。返回 lock_content 或 None。

    🔴🔴🔴 **APP-132 修法（2026-11-24）**：取锁走 **原子 + 独占**创建
    （`_create_lock_exclusive`）⇒ **绝不覆盖**别人的锁。
    旧实现用 `os.replace(tmp, LOCK)` ⇒ **不是原子创建** ⇒ 两个进程可同时
    "拿到"锁；且会把**别人刚建的锁覆盖掉**。
    ⇒ 本实现把"探测 ⇒ 创建"合并进**同一个 while 循环** ⇒ 中间没有 TOCTOU 窗口。
    """
    while True:
        own = lock_owner()
        if own is None:
            content = 'app %d %s %s' % (
                os.getpid(),
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                note)
            if _create_lock_exclusive(content):
                log('已取机器锁：%s' % content)
                _lock_event('acquired', content=content)
                start_lock_watchdog(content)
                return content
            # 🔴 探测之后、创建之前 ⇒ 被别人抢先建了锁
            #   ⇒ **不覆盖**（fail-closed）⇒ 回到循环顶部继续等
            log('🔴 取锁时锁已被别人抢先创建 ⇒ **不覆盖** ⇒ 继续等')
            time.sleep(5)
            continue
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
        # 🔴 轮询间隔取 **5 s**：别的模块是「跑一臂 ⇒ 放锁 ⇒ 下一臂」，
        #   臂与臂之间只有很短的空窗 ⇒ 20 s 的轮询容易整轮错过。
        time.sleep(5)


# 🔴🔴🔴 **锁看门狗**（APP-115 §3.3-2 已知缺陷的防御）：
#   reviewer 侧脚本的 `finally { Remove-Item $lock }` 是**无条件删**的
#   ⇒ 别的模块的作业结束时会把**我的**锁文件删掉 ⇒ 下一臂就能抢同一台机器
#   ⇒ 我的打包/验收就在别人的计时窗口里跑 ⇒ 两边都作废。
#   ⇒ 持锁期间每 20 s **把自己的锁内容写回去**（原子 os.replace）。
_LOCK_WD = {'thread': None, 'stop': False}


def start_lock_watchdog(content):
    """🔴 **锁看门狗**（APP-132 修法，2026-11-24）：**只自检、不盲写**。

    🔴 **旧实现的两处真缺陷**：
      ① 条件是 `own is None or own.get('pid') == os.getpid()`
         ⇒ 锁**被别人抢走**时**彻底放弃写回** ⇒ 链**继续跑但不再持锁**
         ⇒ 计时作废**且无人知晓**；
      ② 写回用 `os.replace(tmp, LOCK)` ⇒ **会覆盖**别人的锁（静默抢锁）。

    ✅ **新实现**：
      · 锁**被删**（reviewer 的 `finally { Remove-Item $lock }` 是无条件删）
        ⇒ **原子 + 独占地补建**（补不上 ⇒ 已被别人抢 ⇒ 记 `lock_lost`）；
      · 锁**被别人抢走** ⇒ 记 `lock_lost` 事件（**不再写回** ⇒ 绝不覆盖别人）；
      · 锁**仍是自己的** ⇒ 内容是静态的 ⇒ **不动文件**（少一次覆盖窗口）。
    ⇒ "链继续跑但不再持锁"从此**可审计**（事件 jsonl）。
    """
    import threading

    def _watch():
        while not _LOCK_WD['stop']:
            time.sleep(20)
            if _LOCK_WD['stop']:
                break
            own = lock_owner()
            if own is None:
                # 锁文件没了 ⇒ 补建（**独占** ⇒ 别人抢先就抢不到）
                if _create_lock_exclusive(content):
                    _lock_event('lock_recreated', why='file_missing')
                else:
                    _lock_event('lock_lost', why='file_missing_taken_by_other')
                continue
            if own.get('pid') != os.getpid():
                # 🔴 已被别人抢走 ⇒ 记事件（**绝不写回** ⇒ 绝不覆盖别人的锁）
                _lock_event('lock_lost', why='taken_by_other',
                            owner_raw=own.get('raw'))
                continue
            # 锁仍是自己的 ⇒ 内容静态 ⇒ 不动文件

    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    _LOCK_WD['thread'] = t
    log('锁看门狗已启动（每 20 s 自检持锁状态）')


def stop_lock_watchdog():
    _LOCK_WD['stop'] = True


_LOCK_EVENTS = os.path.join(RESULTS, 'app231_pack_lock_events.jsonl')


def _lock_event(kind, **kw):
    """🔴 锁状态变化**追加**落盘（JSONL，一行一条）⇒ 可审计。

    🔴 **只追加、绝不覆盖**；写失败**不抛异常**（不能让事件记录反过来打断作业）。
    """
    rec = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'event': kind, 'pid': os.getpid()}
    rec.update(kw)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(_LOCK_EVENTS, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:
        pass
    log('[lock] %s %s' % (kind, kw))


def release_lock(content):
    stop_lock_watchdog()
    own = lock_owner()
    if own is None:
        _lock_event('release_no_lock')
        return
    if own.get('raw') == content or (own.get('pid') == os.getpid()):
        try:
            os.remove(LOCK)
            _lock_event('released')
            log('已放机器锁')
        except Exception as e:
            _lock_event('release_error', error=repr(e))
            log('放锁失败：%r' % (e,))
    else:
        _lock_event('release_skipped_not_owner', owner_raw=own.get('raw'))
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
        # 🔴 目标目录已存在 ⇒ **不覆盖**；但要区分是「上一阶段已复制好」
        #   （本轮 v2.5）还是「别人的旧版本目录」（不许碰）。
        if os.path.isdir(os.path.join(DST, 'app')) and \
                os.path.isfile(os.path.join(DST, 'app', 'MANIFEST.json')):
            log('目标目录已存在且是本轮已复制的 v2.5 ⇒ 跳过复制（不覆盖）')
            return True
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
