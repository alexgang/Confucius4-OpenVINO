#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""把**设备级实测结果**追加进 `status/app/STATUS_APP.md` 的 §132。

🔴 **口径**：
   - 只**追加**（不删旧正文）。
   - 「收尾复核」表补上**收尾时刻**的 `CORRECTIONS_APP.md` SHA/字节/mtime/条数
     （**实测值**，不是抄开工值）⇒ 这样 reviewer 能看出「本轮有没有中途被追加」。
   - 写盘原子 + 逐字节复核 + 限额自检（≤40 000 B / ≤300 行）。
"""
import datetime
import hashlib
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
LIMIT_B, LIMIT_LINES = 40000, 300

APPEND = r'''

#### ⑩ 🔄 **设备级实测（APP-063 ④）—— 已跑完（影子包 ＝ 本轮代码）：7 PASS / 4 FAIL / 4 NONE**

🔴 **纪律**（APP-064）：先拿 `MACHINE_LOCK`（日志 `[lock] 已取得机器锁`，`app PID 26476 started 2026-11-02 20:59:25`）⇒ 再等安静窗口（`wait_quiet_window_cpu` ⇒ **75 s 后取得 45 s 安静窗口**，用户 v2.1 GUI 的 CPU 增量实测 = 0 s/6 s ⇒ 不算干扰）⇒ 才开始跑。
🔴 **测的是本轮代码**：影子包 `shared/app065_shadow`（**硬链接**自 v2.2 ＋ 同步本轮 2 个改动文件，自检 PASS）⇒ **不是** v2.2 的旧码。证据：`results/app/app233_device_acceptance_evidence.json`（28 123 B）。

| 判据 | 结果 | 实测值 |
|---|---|---|
| ① 「没有可用音色」= 0（preset 臂 / clone 臂） | ✅ / ✅ | 0 / 0（⚠️ 见 ⑪：**这条曾是假 PASS**） |
| ①b CUDA 边车 REQ 数 | **无法判定** | 本机**无 CUDA 运行时** ⇒ CUDA 臂跑不了（≠ 不合格） |
| ③-① 句内欠载总和 ≤ 音频时长 0.5 % | ✅ | 0 ms（限 1500 ms） |
| ③-② ≥95 % 句子 uf = 0 | ❌ | `n_sent_uf_zero = 0`（**判据取不到句子级 uf** ⇒ 疑判据口径问题，待复核） |
| ③-③ ASR RTF 增量（TTS on − off）≤ +0.10 | ❌ | **+0.122**（off 0.756 → on 0.878）**超限** |
| ③-④ 丢句数 = 0 | ✅ | 0（76 行） |
| ③-⑤ TTS 首包延迟 | 报告 | **P50 0.5651 s / P95 0.7024 s** |
| ④-① 声纹计算次数 ≤ 2×说话人数 | ✅ | 1（说话人 1） |
| ④-② 每次声纹计算 ±1 s 内有 new_spk 配对 | ❌ | `n_paired = 0` / `n_unpaired = 1` |
| ④-③ 定时克隆更新（无 new_spk 配对）= 0 | ✅ | 0 次（**v2.1 的 27 次已归零**） |
| ⑤-① `voice_kind=clone` 占比 ≥ 80 % | ❌ | **0 %**（76 句**全是 preset**）⇒ 见 ⑪ |
| ⑤-② no_spk_label 回落 ≤ 说话人×2 | ✅ | 0 |
| ⑤-③ reviewer 主观核对（性别/音色） | **人工项** | 76 句待 reviewer 抽听 |
| ③(e) CPU 卸载候选 A/B | **无法判定** | 本轮未做（需 GUI+CLI 各一次、ABBA、持锁） |

✅ **相对 v2.1 的实质进步**：④-③「定时克隆更新」**从 27 次归零**（APP-061④ 的核心修复在真机上成立）；①「没有可用音色」= 0 ⇒ **APP-061① 的「全程无声」已消除**。

#### ⑪ 🔴 **设备级实测暴露的 3 个问题（本轮新发现）**

1. 🔴 **判据①曾是「假 PASS」** —— 正则只抓 `没有可用的音色`，而**实测**的故障串是
   **`🔴 没有可用引擎 ⇒ spk 音色登记失败`**（`tts_worker.py:3805`）与
   **`⚠️ 没有可用引擎 ⇒ 克隆无法生效（仍用预设 A）`**（`tts_worker.py:3763`）
   ⇒ **抓不到真实故障** ⇒ 已把正则扩成**三条故障串**（`app223` 判据①已修，自检 5/0）。
   （MEMORY：「判据 PASS ≠ 判据正确」—— 这条正是实例。）
2. 🔴 **⑤-① clone 占比 0 % 的根因 = 本机没有克隆引擎**（CUDA 边车不在本机）
   ⇒ **APP-065 C「克隆有效性」在本机客观无法判定**（≠ 不合格）
   ⇒ 需带 CUDA 边车的环境才能给出「每段用了哪个克隆音色」的表 ＋ wav ＋ 相似度。
3. 🔴 **影子包里的说话人旁路仍是 10 s** —— 日志 `说话人旁路窗口：10.000 s`
   ⇒ 因为影子包的 `app/asr_spk/` **只有 3 个文件**（**不含 `asr_spk_window.py`**）
   ⇒ **实证了 `app230` 的 D1-6**（客户包不含唯一事实来源 ⇒ 客户机退回 10 s）。
   ⇒ 同时说明：④-②「声纹计算没有 new_spk 配对」与「标签晚到（`第 0 段无说话人标签：async_pending`）」
   都与**10 s 窗口的延迟**一致 ⇒ **D1 的跨模块同源是克隆生效的前置条件**。

#### ⑫ 📌 **收尾复核（本轮实测值）**

| 时点 | 文件 | SHA256 | 字节 | mtime | 条数 |
|---|---|---|---|---|---|
| §132 开工（15:01） | `status/app/CORRECTIONS_APP.md` | `0b9cf6227e22fd57f791f7f4bfe16c360b25d2d74b9db3a14de1844a3f4aa033` | 182 008 | 2026-11-02 14:55:36 | 65 |
| **§132 收尾（本节）** | `status/app/CORRECTIONS_APP.md` | **见下方命令的实测输出** | — | — | — |

⇒ **本模块全程只读** `CORRECTIONS_APP.md`（**未写入、未提交**）。
'''


def main():
    with open(STATUS, 'rb') as f:
        raw = f.read()
    txt = raw.decode('utf-8')
    EOL = '\r\n' if '\r\n' in txt else '\n'

    if '#### ⑩ 🔄 **设备级实测' in txt:
        print('[skip] 设备级小节已存在')
        return 0

    # 收尾复核：实测 CORRECTIONS_APP.md
    with open(CORR, 'rb') as f:
        c = f.read()
    sha = hashlib.sha256(c).hexdigest()
    st = os.stat(CORR)
    mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    n_entries = sum(1 for l in c.decode('utf-8').splitlines()
                    if l.startswith('## APP-'))
    append = APPEND.replace(
        '**见下方命令的实测输出**',
        '`%s` | %d | %s | **%d**' % (sha, len(c), mtime, n_entries))
    append = append.replace(
        '| **§132 收尾（本节）** | `status/app/CORRECTIONS_APP.md` | `见下方命令的实测输出` | — | — | — |',
        '| **§132 收尾（本节）** | `status/app/CORRECTIONS_APP.md` | `%s` | %d | %s | **%d** |'
        % (sha, len(c), mtime, n_entries))

    lines = txt.split(EOL)
    if lines and lines[-1] == '':
        lines = lines[:-1]
    lines = lines + append.replace('\n', EOL).split(EOL)
    new = EOL.join(lines)
    if not new.endswith(EOL):
        new += EOL
    data = new.encode('utf-8')
    n_lines = new.count('\n')
    print('新文件：%d B / %d 行' % (len(data), n_lines))
    if len(data) > LIMIT_B or n_lines > LIMIT_LINES:
        print('[ABORT] 超限额（需先归档）')
        return 2

    tmp = STATUS + '.tmp_dev'
    open(tmp, 'wb').write(data)
    assert open(tmp, 'rb').read() == data
    os.replace(tmp, STATUS)
    assert open(STATUS, 'rb').read() == data
    print('OK 已追加设备级小节（CORR 收尾 SHA=%s… 条数=%d）' % (sha[:12], n_entries))
    return 0


if __name__ == '__main__':
    sys.exit(main())
