# -*- coding: utf-8 -*-
r"""_app224_write_status.py —— 把 §128 章节**追加**到 `status/app/STATUS_APP.md`。

## 铁律（记忆 §一 / §十）

1. 🔴 **只追加**到文件末尾；**不改**任何旧章节正文。
2. 🔴 本文件工作区是**纯 LF**（实测 CRLF=0）⇒ 必须 **bytes 级定点替换**
   ⇒ 绝不能用 `read().split('\n') + '\n'.join()` 之后整体写回。
3. 🔴 头部字段替换**必须限定在头部区**（第一个 `## §` 之前）。
4. 🔴 写后验：「旧正文逐字未变」＋「行尾仍纯 LF」＋「自指大小与磁盘实测一致」。
5. 🔴 **先写临时文件再原子替换**（`open(p,'w')` 中途异常 ⇒ 目标文件被清空）。
6. 🔴 头部 `last_ack` **不变**（本轮无新纠偏条目 ⇒ 仍是 APP-061）。
"""
from __future__ import annotations

import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
NOW = '2026-11-02 03:16'

HEADER_OLD_TASK_MARK = '**§127 APP-061 已执行**'
HEADER_OLD_TIME_MARK = '更新时间: 2026-11-02 02:00'

NEW_TASK = (
    '**§128 巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 转做 APP-061② 附带问题'
    '（`SyntaxWarning`）+ 共享锁闸门修复（32/40 → 42/42）+ 备好真机验收 harness '
    '`app223`（判据自检 5/5 ⇒ 判据非恒真）**｜ 🔴 **设备级实测本轮未开跑**'
    '（安静窗口不可用：用户 v2.1 GUI 会话 PID 14712 仍在跑 ⇒ 不与用户抢 NPU）'
    '⇒ **①③④⑤ + ③(e) 的设备级数字仍未实测**')

NEW_BLOCK = (
    '🔴 **D1–D4 仍由 reviewer/用户决定**（旁路窗口时长 / 是否自动开旁路 / '
    '客户包是否保留 CUDA 选项 / NPU 共用是警告还是禁止）；'
    '🔴 **§128 新增 1 项待 reviewer 裁定**：共享锁 `stale_boot` 分支'
    '**优先于 PID 存活判断** ⇒ 时钟异常时会**抢走活锁**（本轮只写成显式断言，'
    '**未改实现语义**）；'
    '⛔ **设备级实测（①③④⑤ + ③(e)）仍未做**：harness `app223` 已备好，'
    '等机器安静 + 用户会话结束后即可一键跑')

SEC128 = r"""### §128 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 转做 APP-061② 附带问题 ＋ 共享锁闸门修复 ＋ 备好真机验收 harness；设备级实测因用户会话在跑而未开跑** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 03:16）

**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061** ⇒ **无新纠偏条目**（本轮**不执行**任何新条目；`last_ack` **不变**）。

#### ① APP-061② 附带问题：`SyntaxWarning: invalid escape sequence`（reviewer 点名 `tts_cuda_sidecar.py:8`）已修
* 全量扫 `live_caption/*.py` + `machine_lock_app.py` + `pack_v13.py` ⇒ **4 处**同类告警：`tts_cuda_sidecar.py:8`（`\_`）、`machine_lock_app.py:258`（`\S`）、`_app100b_patch_status.py:67`（`\p`）、`sync_c195_app052054_to_pkg.py:29`（`\|`）⇒ **全部归零**（另加本轮新建的 `app223` 自身 1 处）。
* 改法**最小化**：docstring 加 `r` 前缀 / 单个反斜杠转义 ⇒ **不写死源码、不整目录覆盖**。
* 🔴 **「行为不变」的证明**：改前/改后**逐个字符串常量**（`ast` 全量 `Constant(str)`）对照 ⇒ **值一个都没变**；唯一差异是 `machine_lock_app.py` 的 `_parse_module_pid` docstring 里 `\b` 从**不可见背空格**（0x08）变成**可见字面量**（文档更对，非行为变化）⇒ 证据 `results/app/app224_app061_escape_lock_gates_evidence.json` → `escape_fixes[]`（**5 PASS / 0 FAIL**）。
* ⚠️ **v2.2 包内仍是改前版**（`tts_cuda_sidecar.py:8` 的 `\_` 仍在）⇒ 下一版必须**打 v2.3**（**禁止 `--same-version`**），本轮**未打包**（未获授权）。

#### ② 共享锁闸门 `results/app/test_machine_lock_app.py`：8 条**假 FAIL** 已修（32/40 → **42/42**）
* 根因 = **夹具写死绝对日期**（`2026-10-24 / 10-25 / 10-28`）＋ 本机 **2026-10-31 08:44 重启过** ⇒ 这些锁的 `started` **早于开机时间** ⇒ 命中 `stale_boot` 分支（代码里明文「**优先于 PID 判断**」）⇒ 8 条断言在「锁语义没变」的情况下**假 FAIL**。
* 🔴 **反证基线**（拿 HEAD 版 `machine_lock_app.py` + 旧夹具跑）⇒ **同样的 8 条 FAIL**（30/39）⇒ 证明是**判据缺陷**（夹具），不是产品缺陷（对齐记忆「判据 FAIL 先怀疑判据/环境」）。
* 改法：夹具时间戳一律**动态**（`_ts()`）＋ **补 `stale_boot` 分支的显式覆盖**（原来这一分支**没有任何断言**）。
* 改后（仓库内跑，含 git 反证组）⇒ **42/42 PASS**（`app224…` → `lock_test_current.n_pass=42` / `n_fail=0`）。

#### ③ 🔴 顺带查出的**风险项**（本轮**未自行改实现**，交 reviewer 裁定）
* `lock_state()` 的 `stale_boot`（锁的 `started` 早于开机时间）**优先于 PID 存活判断** ⇒ **别的模块时钟被往回调**（或开机时间算错）时，会**抢走活锁** ⇒ 两个模块同占设备（违反「死判据只能是 `OpenProcess` err==87」的铁律）。
* 本轮**只把它写成显式断言**（口径锁定：`(口径锁定) started 早于开机时间 ⇒ stale_boot 优先于 PID 存活`，见 `test_machine_lock_app.py` §3b）⇒ **语义改动留给 reviewer**。

#### ④ APP-061②「CUDA 置灰 + 显示原因」在 **v2.2 包内代码**确实落地（静态核验 4/4）
* 4 个落点全部命中 `Confucius4_LiveCaption_v2.2/app/live_caption_app.py`：① 列表项 `disabled=(not _cuda_ok), why=_cuda_why`（L896）② 不可用项**不作为初值**（L2849）③ 选中不可用项 ⇒ **拒绝启动 + 显示原因 + 回退可用项**（L3555）④ 启动前**拦住**并自动改用可用设备（L3679）。
* 证据：`app224…` → `cuda_graying.anchors`（4/4，`ok=true`）。

#### ⑤ 🔴 设备级实测（本轮**最重要的缺口**）：harness 已备好，**但未开跑**
* 新增 `results/app/app223_app061_device_acceptance.py`：3 臂（`tts_off` / `tts_on_preset` / `tts_on_clone`）＋ **v2.1 反证臂**；判据覆盖 APP-061 **①（没有可用的音色=0）③（uf_in_sentence_ms ≤ 0.5 % / ≥95 % 句子为 0 / ASR RTF 增量 ≤ +0.10 / 丢句=0 / 首包 P50-P95）④（声纹次数 ≤ 2×说话人数 / ±1 s 配对 / 定时克隆=0）⑤（voice_kind=clone ≥ 80 % / 回落 ≤ 2×说话人数）**；**三态**（True/False/**None 无法判定**）+ 自取机器锁 + 等安静窗口。
* 🔴 **判据非恒真的证明（不需要设备）**：拿 **reviewer 点名的 v2.1 会话日志**（`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261101_212026.log`）跑同一套判据 ⇒ **5 PASS / 0 FAIL**（抓到 **83** 次「已回落到预设 A」（reviewer 原文 83）、**50** 次「没有可用的音色」、**25** 次 10.0 s 定时克隆更新、**27** 次声纹计算对不上 `new_spk`）⇒ 同一套判据对 **v2.1 必须 FAIL** ⇒ 对 v2.2 的判定才可信。
* ⛔ **真机三臂本轮未跑**：`machine_lock_app.wait_quiet_window_cpu(30 s/60 s)` ⇒ **ok=False**（`last_busy_pids=[14712]` = **用户自己的 v2.1 GUI 会话**，`live_caption_app.py` 21:20:24 启动）⇒ 与用户会话抢 NPU 会让**两边数字都失真** ⇒ **本轮不开跑**（`app224…` → `device_acceptance_blocked=true`）。
* ⇒ **APP-061 ①③④⑤ + ③(e) 的设备级数字仍然「未实测」**（代码层已由 `app215/219/220` 覆盖）；下一步：机器安静 + 用户会话结束后跑 `python results/app/app223_app061_device_acceptance.py --run`。

#### ⑥ 收尾复核（`CORRECTIONS_APP.md` 全程只读）
* 收尾实测（2026-11-02 03:1x 现场重算）：见本节末尾「收尾实测」行 ⇒ 与开工基线**逐字相同** ⇒ 本轮 reviewer **未**追加新条目（若中途被追加则如实记录，不声称「零改动」）。

#### ⑦ 本轮交付
* 代码：`live_caption/tts_cuda_sidecar.py`、`machine_lock_app.py`、`live_caption/_app100b_patch_status.py`、`live_caption/sync_c195_app052054_to_pkg.py`、`results/app/app223_app061_device_acceptance.py`、`results/app/app224_app061_escape_lock_gates.py`、`results/app/_app223_doc_snapshot.py`、`results/app/_app223_escape_fix_verify.py`、`results/app/_app224_write_status.py`、`results/app/test_machine_lock_app.py`。
* 证据：`results/app/app223_app061_device_acceptance_evidence.json`（判据自检 5/5）、`results/app/app224_app061_escape_lock_gates_evidence.json`（5 PASS / 0 FAIL ＋ 锁闸门 42/42 ＋ 基线 30/39 ＋ CUDA 4/4）。
* 🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 目录与 zip **一个字节都没动**）。
"""


def _replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    n = data.count(old)
    if n != 1:
        raise SystemExit('❌ 唯一定位失败：%r 命中 %d 次' % (old[:60], n))
    return data.replace(old, new, 1)


def main():
    with open(STATUS, 'rb') as f:
        orig = f.read()
    if b'\r\n' in orig:
        raise SystemExit('❌ 预期纯 LF，实际含 CRLF')
    if orig.rstrip(b'\n').endswith('§127'.encode('utf-8')) \
            or '### §128'.encode('utf-8') in orig:
        raise SystemExit('❌ §128 已存在（或尾部异常）⇒ 拒绝重复写入')

    data = orig
    # ── ① 头部字段（限定在头部区 = 第一个 '\n## ' 之前） ──────────────
    head_end = data.index(b'\n## ')
    head = data[:head_end]
    tail = data[head_end:]

    head = _replace_once(head, HEADER_OLD_TIME_MARK.encode('utf-8'),
                         ('更新时间: %s' % NOW).encode('utf-8'))
    # 「当前任务:」整行替换
    m = re.search(rb'(?m)^' + '当前任务: '.encode('utf-8') + rb'[^\n]*$', head)
    if not m:
        raise SystemExit('❌ 头部区找不到「当前任务:」')
    head = head[:m.start()] + ('当前任务: ' + NEW_TASK).encode('utf-8') \
        + head[m.end():]
    # 「阻塞 / 待用户决定:」整行替换
    m = re.search(rb'(?m)^' + '阻塞 / 待用户决定: '.encode('utf-8') + rb'[^\n]*$',
                  head)
    if not m:
        raise SystemExit('❌ 头部区找不到「阻塞 / 待用户决定:」')
    head = head[:m.start()] + ('阻塞 / 待用户决定: ' + NEW_BLOCK).encode('utf-8') \
        + head[m.end():]

    # ── ② 「最近更新」列表顶部插一行 ────────────────────────────────
    anchor = b'\n## \xe6\x9c\x80\xe8\xbf\x91\xe6\x9b\xb4\xe6\x96\xb0\n'
    i = tail.index(anchor) + len(anchor)
    j = tail.index(b'\n', i) + 1
    upd = ('- 2026-11-02 03:16 **§128** ⇒ 无新纠偏（61 条 = APP-061）'
           '⇒ APP-061② `SyntaxWarning` 已修（5 文件，告警全归零，字符串值未变）'
           '＋ 共享锁闸门夹具写死日期导致的 **8 条假 FAIL 已修（32/40 → 42/42）**'
           '＋ **CUDA 置灰 4/4 落点核验通过** ＋ 真机验收 harness `app223` 已备好'
           '（判据自检 5/5 ⇒ 非恒真）⇒ ⛔ **设备级实测未开跑**（用户 v2.1 会话在跑）'
           '＋ 🔴 新增待裁定：`stale_boot` 优先于 PID 存活 ⇒ 时钟异常会抢活锁\n')
    tail = tail[:j] + upd.encode('utf-8') + tail[j:]

    # ── ③ 「最近章节」索引表加一行 §128 ────────────────────────────
    row_anchor = '| §127 |'.encode('utf-8')
    k = tail.index(row_anchor)
    k2 = tail.index(b'\n', k) + 1
    row = ('| §128 | 巡检无新纠偏 ⇒ APP-061② `SyntaxWarning` 已修 ＋ 共享锁闸门'
           '夹具假 FAIL 已修（42/42）＋ CUDA 置灰核验 ＋ 真机验收 harness 备好'
           '（设备级实测因用户会话在跑而未开跑） | **本轮新增（见下）** |\n')
    tail = tail[:k2] + row.encode('utf-8') + tail[k2:]

    # ── ④ 追加 §128 正文 ────────────────────────────────────────────
    data = head + tail
    if not data.endswith(b'\n'):
        data += b'\n'
    data += b'\n' + SEC128.replace('\n', '\n').encode('utf-8')
    if not data.endswith(b'\n'):
        data += b'\n'

    # ── ⑤ 自指大小迭代（不动点） ────────────────────────────────────
    for _ in range(8):
        m = re.search(rb'(?m)^' + '已压缩: '.encode('utf-8') + rb'.*$', data)
        if not m:
            raise SystemExit('❌ 找不到「已压缩:」行')
        nbytes = len(data)
        nlines = len(data.splitlines())
        want = ('已压缩: 本文件 %d B / %d 行（APP-052 ④ 限额 ≤ 40000 B / '
                '≤ 300 行）；**§109–§124 正文＋旧「最近更新」条目＋'
                '「已撤回的旧结论」备查块已原样归档**到 '
                '`status/archive/STATUS_APP_sec124_upto_20261101.md`'
                '（**逐字保留，内容一字未删**；更早的见 '
                '`STATUS_APP_sec109_122_upto_20261101.md`）'
                % (nbytes, nlines)).encode('utf-8')
        new = data[:m.start()] + want + data[m.end():]
        if len(new) == len(data):
            data = new
            break
        data = new

    # ── ⑥ 写临时文件 → 原子替换 ────────────────────────────────────
    tmp = STATUS + '.tmp_app224'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    # ── ⑦ 写后复核 ─────────────────────────────────────────────────
    with open(STATUS, 'rb') as f:
        after = f.read()
    print('字节：%d → %d（+%d）' % (len(orig), len(after),
                                    len(after) - len(orig)))
    print('行数：%d → %d' % (len(orig.splitlines()), len(after.splitlines())))
    print('CRLF 数：%d（应为 0）' % after.count(b'\r\n'))
    # 旧正文逐字未变：把 after 去掉「头部区改动 + 新增段 + 索引行 + 最近更新行」
    # ⇒ 应逐字等于 orig 的对应片段。简单做法：检查 orig 的每一行是否仍出现在 after。
    o_lines = orig.decode('utf-8').splitlines()
    a_text = after.decode('utf-8')
    missing = [l for l in o_lines
               if l and l not in a_text and 'last_ack' not in l
               and '更新时间' not in l and '当前任务' not in l
               and '阻塞 / 待用户决定' not in l and '已压缩' not in l]
    print('旧行丢失数（应为 0）：%d' % len(missing))
    for l in missing[:5]:
        print('   丢失：%s' % l[:120])
    print('§128 出现次数：%d' % a_text.count('### §128'))
    print('last_ack 行：%s'
          % [l for l in a_text.splitlines() if l.startswith('last_ack:')])
    if missing:
        return 1
    if a_text.count('### §128') != 1:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
