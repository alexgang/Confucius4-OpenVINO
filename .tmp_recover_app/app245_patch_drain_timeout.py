#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""§245 定点补丁：`_app137_e2e_drain.drain_until_zero` —— 单次 stats 超时不再中止排空。

## 根因（19:14 三轮实测）
排空在 `drain_elapsed_sec=10.02` 就退出，`drain.disconnected` =
`TimeoutError('stats 未在 10.0 s 内返回（桥接可能卡住）')`，
`n_pending_after_drain` = 8 / 26 / 47 ⇒ `drained_to_zero` 恒 False ⇒ APP-150 §2 门禁败。
但 `bridge.log` 显示**同一时刻桥接仍在出段**（18:51:23 一次性补出剩余 10 段），
`dubs` 最终 = `n_submitted`（123）。⇒ 桥接没卡死，是**片尾清 backlog 时 stats 应答慢于 10 s**，
旧逻辑把「一次超时」当断连 ⇒ 整段排空放弃。

## 改法
* 单次 stats 超时 ⇒ **如实记录**（`drain_timeout_events` / `stats_timeout_count`）后**继续排空**；
* 墙钟硬上限（`drain_cap + stats_timeout + 2`，APP-143 b ②）**仍然兜底** ⇒ 真卡死仍能退出；
* 真断连（非 TimeoutError）⇒ 立刻退出（原行为不变）；
* 排空成功时 `disconnected` 保持 None（不把「中途超时」误报成断连）。

## 纪律
备份 → 内存里跑真不变量 → 临时文件 → `os.replace`；写后另起脚本复核。
"""
import ast
import hashlib
import io
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(REPO, 'live_caption', '_app137_e2e_drain.py')
BACKUP = os.path.join(REPO, '.tmp_recover_app', '_app137_e2e_drain.py.bak_app245')

# ── 唯一锚点（逐字取自源文件）──────────────────────────────────────────
A_DOC = ("    ③ 超时/断连 ⇒ **如实记录**（`disconnected` / `stats_timeout_count`）后**退出**。")
A_DOC_NEW = ("    ③ 超时/断连 ⇒ **如实记录**（`disconnected` / `stats_timeout_count` /\n"
             "       `drain_timeout_events`）；🔴 **单次 stats 超时不退出**（继续排空，\n"
             "       墙钟硬上限兜底），**真断连才退出**（§245 实测根因见文件头注释）。")

A_INIT = ("    drained = False\n"
          "    disconnected = None\n"
          "    npend = npend_end")
A_INIT_NEW = ("    drained = False\n"
              "    disconnected = None\n"
              "    last_timeout = None\n"
              "    npend = npend_end")

A_EXC = ("            if isinstance(e, asyncio.TimeoutError):\n"
         "                n_timeouts += 1\n"
         "                disconnected = repr(e)\n"
         "                got['stats_timeout_count'] = n_timeouts\n"
         "                break")
A_EXC_NEW = ("            if isinstance(e, asyncio.TimeoutError):\n"
             "                n_timeouts += 1\n"
             "                last_timeout = repr(e)\n"
             "                got['stats_timeout_count'] = n_timeouts\n"
             "                # 🔴 §245：**单次 stats 超时 ≠ 桥接卡死**。19:14 三轮实测：\n"
             "                #   片尾清 backlog 时 NPU TTS 把 WS 应答压在 10 s 之外\n"
             "                #   （bridge.log 同刻仍在出段、dubs 最终 = n_submitted）\n"
             "                #   ⇒ 旧逻辑把「一次超时」当断连 ⇒ 排空整段放弃\n"
             "                #   ⇒ n_pending 停在 8/26/47、drained_to_zero 恒 False。\n"
             "                #   现在：如实记录后**继续排空**；墙钟硬上限\n"
             "                #   （APP-143 b ②）仍然兜底 ⇒ 真卡死最迟 hard_cap 秒退出。\n"
             "                got.setdefault('drain_timeout_events', []).append({\n"
             "                    'rel_sec': round(time.perf_counter() - t0, 2),\n"
             "                    'elapsed_in_drain_sec': round(\n"
             "                        time.perf_counter() - drain_start, 2),\n"
             "                    'msg': repr(e)})\n"
             "                if time.perf_counter() - drain_start >= hard_cap:\n"
             "                    got['drain_hard_cap_hit'] = True\n"
             "                    disconnected = last_timeout\n"
             "                    break\n"
             "                await asyncio.sleep(a.poll_sec)\n"
             "                continue")

A_FIELD = ("        'stats_timeout_count': got.get('stats_timeout_count', 0),\n"
           "        'drain_hard_cap_sec': hard_cap,")
A_FIELD_NEW = ("        'stats_timeout_count': got.get('stats_timeout_count', 0),\n"
               "        # 🔴 §245：每次超时的时刻/位置（排空成功也可能有，不代表失败）\n"
               "        'drain_timeout_events': got.get('drain_timeout_events', []),\n"
               "        'drain_hard_cap_sec': hard_cap,")

PATCHES = [('docstring ③', A_DOC, A_DOC_NEW),
           ('init last_timeout', A_INIT, A_INIT_NEW),
           ('except 分支', A_EXC, A_EXC_NEW),
           ('drain 字段', A_FIELD, A_FIELD_NEW)]


def cnt(text, sub):
    return text.count(sub)


def main():
    with io.open(TARGET, encoding='utf-8', newline='') as fh:
        old = fh.read()

    # ── 写前：唯一命中断言 ────────────────────────────────────────────
    problems = []
    for name, a, _b in PATCHES:
        c = cnt(old, a)
        if c != 1:
            problems.append('%s：锚点命中 %d 次（应为 1）' % (name, c))
    if problems:
        print('FAIL（写前判据）: ' + '；'.join(problems))
        return 2

    new = old
    for _name, a, b in PATCHES:
        new = new.replace(a, b, 1)

    # ── 写前：真不变量（在内存里）────────────────────────────────────
    inv = []
    old_nl, new_nl = old.count('\n'), new.count('\n')
    inv.append(('行尾仍纯 LF（CRLF=0）',
                old.count('\r') == 0 and new.count('\r') == 0))
    inv.append(('无 TAB 引入', ('\t' in new) == ('\t' in old)))
    inv.append(('行数增加 = +%d（实测 %+d）' % (new_nl - old_nl, new_nl - old_nl),
                new_nl > old_nl))
    inv.append(('旧锚点已全部消失',
                all(cnt(new, a) == 0 for _n, a, _b in PATCHES)))
    inv.append(('新锚点各 1 次',
                all(cnt(new, b) == 1 for _n, _a, b in PATCHES)))
    inv.append(('文件头/模块 docstring 未动',
                old.split('"""')[0] == new.split('"""')[0]))
    try:
        ast.parse(new)
        inv.append(('ast.parse(new) OK', True))
    except SyntaxError as e:
        inv.append(('ast.parse(new) OK（%s）' % e, False))
    # 反证：把新逻辑再改回「break」⇒ 必须检出差异（证明判据承重）
    rev = new.replace(A_EXC_NEW, A_EXC, 1)
    inv.append(('反证组：还原成超时即 break ⇒ 文本不同',
                rev != new and cnt(rev, A_EXC) == 1))

    bad = [n for n, ok in inv if not ok]
    for n, ok in inv:
        print('  [%s] %s' % ('OK' if ok else 'FAIL', n))
    if bad:
        print('FAIL（写前不变量）⇒ 零改动')
        return 3

    # ── 备份 + 原子写 ────────────────────────────────────────────────
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    shutil.copy2(TARGET, BACKUP)
    tmp = TARGET + '.app245.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(new)
    os.replace(tmp, TARGET)

    with io.open(TARGET, encoding='utf-8', newline='') as fh:
        after = fh.read()
    print('\n写后：bytes %d -> %d，行数 %d -> %d'
          % (len(old.encode()), len(after.encode()), old_nl, new_nl))
    print('sha256 after = %s' % hashlib.sha256(after.encode()).hexdigest())
    print('备份 = %s' % BACKUP)
    print('PASS' if after == new else 'FAIL（写后与内存不一致）')
    return 0 if after == new else 4


if __name__ == '__main__':
    sys.exit(main())
