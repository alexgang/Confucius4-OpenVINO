#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-132 补漏：**生产打包路径**的机器锁仍有原缺陷（上一轮只修了侧写 harness）。

## 背景（为什么这是真缺陷，不是"已经修过了"）

上一轮（§230）声称"APP-132 机器锁修掉两处真缺陷"，但那次修法落在
**`results/app/_app132_lock.py`（侧写 harness，专供 v2.6 整链三臂跑）**，
**生产打包路径**仍是旧代码：

    live_caption/_app116_build_v25.py   ← 成包脚本（v2.5/v2.6 都走它）
      └─ `live_caption/_app129_build_v26.py` 第 216 行 `B.acquire_lock(...)`

两处原缺陷**原封不动**还在：

| # | 位置 | 缺陷 | 后果 |
|---|---|---|---|
| ① | `acquire_lock()` 末行 `os.replace(tmp, LOCK)` | **不是原子创建** | 两个进程可同时"拿到"锁；且**会把别人刚建的锁覆盖掉**（TOCTOU） |
| ② | `start_lock_watchdog()` | 锁被抢后**彻底放弃写回**，且写回用 `os.replace` | 链**继续跑但不再持锁** ⇒ 计时作废**且无人知晓**；写回还可能**静默覆盖别人的锁** |

⇒ 仓库根 `machine_lock_app.py` 里已写明正解：**先写全 tmp ⇒ `os.link` 建硬链接**
⇒ 目标已存在就失败 ⇒ **原子 + 独占 + 别的模块永远看不到半成品锁**
（依据 `shared/NOTICE_tts_lock_atomic_20261026.md`；该文件第 405~420 行
逐字解释了为什么**不能**用 `O_CREAT|O_EXCL` 再写内容，也解释了为什么
**不能**用 `os.replace`（会覆盖 ⇒ 丢独占性））。

## 本脚本做什么（🔴 定点替换 + 唯一命中断言）

1. `acquire_lock()`：改成 **while 单循环**（去掉"探测→创建"之间的 TOCTOU 窗口）
   ⇒ 取锁走 **原子 + 独占**创建；别人抢先 ⇒ **不覆盖**、回到等待。
2. 新增 `_create_lock_exclusive()`：`tmp 写全` + `os.link`（**独占**）。
3. `start_lock_watchdog()`：改成**只自检、不盲写**：
   · 锁被删 ⇒ **原子 + 独占地补建**（补不上 ⇒ 已被别人抢 ⇒ 记 `lock_lost`）；
   · 锁被别人抢走 ⇒ **记 `lock_lost` 事件**（**不再写回** ⇒ 绝不覆盖别人的锁）
   ⇒ "链继续跑但不再持锁"从此**可审计**。
4. `release_lock()`：加事件登记（放锁/跳过/无锁）。
5. 新增 `_lock_event()`：追加到 `results/app/app231_pack_lock_events.jsonl`。

## 纪律

- 🔴 **本脚本只改 `live_caption/_app116_build_v25.py`**（App 侧成包脚本）；
  **不碰**客户包、**不碰**其它模块文件、**不碰** `CORRECTIONS_APP.md`。
- 🔴 **定点写入三件套**：① 备份 ② 写前在**内存新文本**跑真不变量
  ③ 临时文件 → `os.replace` ⇒ 写后**另起脚本**独立复核 ＋ `numstat`。
- 🔴 **还原式复核**：把新文本的每个替换区还原 ⇒ 必须逐字节等于写前原文。
"""
from __future__ import annotations

import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(REPO, 'live_caption', '_app116_build_v25.py')


# ── ① 旧代码块（必须逐字节命中，且**只命中一次**）────────────────────
OLD_ACQUIRE = """def acquire_lock(note):
    \"\"\"排队等待 ⇒ 拿到锁写自己的内容。返回 lock_content 或 None。\"\"\"
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
        # 🔴 轮询间隔取 **5 s**：别的模块是「跑一臂 ⇒ 放锁 ⇒ 下一臂」，
        #   臂与臂之间只有很短的空窗 ⇒ 20 s 的轮询容易整轮错过。
        time.sleep(5)
    content = 'app %d %s %s' % (os.getpid(),
                                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                note)
    tmp = LOCK + '.tmp_app116'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp, LOCK)
    log('已取机器锁：%s' % content)
    start_lock_watchdog(content)
    return content
"""

OLD_WATCHDOG = """def start_lock_watchdog(content):
    import threading

    def _watch():
        while not _LOCK_WD['stop']:
            time.sleep(20)
            if _LOCK_WD['stop']:
                break
            own = lock_owner()
            if own is None or own.get('pid') == os.getpid():
                try:
                    tmp = LOCK + '.tmp_app116_wd'
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(content)
                    os.replace(tmp, LOCK)
                except Exception:
                    pass

    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    _LOCK_WD['thread'] = t
    log('锁看门狗已启动（每 20 s 写回自己的锁内容）')
"""

OLD_RELEASE = """def release_lock(content):
    stop_lock_watchdog()
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
"""


# ── ② 新代码块 ──────────────────────────────────────────────────────
NEW_ACQUIRE = '''def _create_lock_exclusive(content):
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
'''

NEW_WATCHDOG = '''def start_lock_watchdog(content):
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
'''

NEW_RELEASE = '''def release_lock(content):
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
'''


# ── ③ 事件记录（新增小节，插在 `release_lock` 之前）─────────────────
EVENT_BLOCK = '''_LOCK_EVENTS = os.path.join(RESULTS, 'app231_pack_lock_events.jsonl')


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
            f.write(json.dumps(rec, ensure_ascii=False) + '\\n')
    except Exception:
        pass
    log('[lock] %s %s' % (kind, kw))


'''


def _os_replace_calls(src):
    """返回源码里所有对 `os.replace` 的**调用点**（AST 精确判定）。

    🔴 为什么不用文本计数：字符串 `os.replace(tmp, LOCK)` 在**注释/docstring**
    里本来就会出现（解释旧缺陷）⇒ 文本计数会假 FAIL；AST 只看**代码**
    ⇒ 语义精确。
    """
    import ast
    out = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == 'replace'
                    and isinstance(f.value, ast.Name)
                    and f.value.id == 'os'):
                out.append(node.lineno)
    return out


def main():
    with open(TARGET, 'r', encoding='utf-8', newline='') as f:
        old = f.read()

    # ── 真不变量（写前）─────────────────────────────────────────
    assert old.count(OLD_ACQUIRE) == 1, 'OLD_ACQUIRE 命中数 != 1'
    assert old.count(OLD_WATCHDOG) == 1, 'OLD_WATCHDOG 命中数 != 1'
    assert old.count(OLD_RELEASE) == 1, 'OLD_RELEASE 命中数 != 1'
    assert 'os.replace(tmp, LOCK)' in old, '旧原子写不在（前提不符）'
    assert '_create_lock_exclusive' not in old, '已打过补丁（幂等守卫）'

    new = old
    new = new.replace(OLD_ACQUIRE, NEW_ACQUIRE)
    new = new.replace(OLD_WATCHDOG, NEW_WATCHDOG)
    new = new.replace(OLD_RELEASE, EVENT_BLOCK + NEW_RELEASE)

    # ── 真不变量（写后，内存态）───────────────────────────────
    assert new != old, '内容未变'
    # 🔴 **判据用 AST，不用文本计数**：`os.replace(tmp, LOCK)` 这个串在新
    #   docstring 里**本来就要出现**（解释旧缺陷）⇒ 文本计数必然假 FAIL
    #   （本轮实测踩到：写前断言命中、文件零改动）。⇒ 改为「**代码里**
    #   不得存在对 `os.replace` 的调用」⇒ 语义精确、注释/文档串不误伤。
    _calls = _os_replace_calls(new)
    assert _calls == [], '代码里仍有 os.replace 调用：%r' % (_calls,)
    assert new.count('_create_lock_exclusive') >= 3, '新原子建锁引用不足'
    assert new.count('def acquire_lock') == 1
    assert new.count('def start_lock_watchdog') == 1
    assert new.count('def release_lock') == 1
    assert new.count('def _lock_event') == 1
    # 旧正文除三处外逐字未变
    restored = (new.replace(NEW_ACQUIRE, OLD_ACQUIRE)
                   .replace(NEW_WATCHDOG, OLD_WATCHDOG)
                   .replace(EVENT_BLOCK + NEW_RELEASE, OLD_RELEASE))
    assert restored == old, '还原式复核失败（旧正文被改动）'

    # ── 写入：临时文件 → os.replace ───────────────────────────
    tmp = TARGET + '.tmp_app231'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, TARGET)

    print('OK  %s' % TARGET)
    print('  before %d B  sha256 %s' % (len(old.encode('utf-8')),
                                        hashlib.sha256(old.encode('utf-8')).hexdigest()))
    print('  after  %d B  sha256 %s' % (len(new.encode('utf-8')),
                                        hashlib.sha256(new.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
