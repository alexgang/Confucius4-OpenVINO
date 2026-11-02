#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""追加**设备级实测**小节到 §132（**紧凑版**）＋ 必要时压缩 §132 的 ②③④⑥。

🔴 **限额**：≤ 40 000 B / ≤ 300 行（APP-052 ④）。
"""
import datetime
import hashlib
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
LIMIT_B, LIMIT_LINES = 40000, 300

APPEND = r'''

#### ⑩ 🔄 **设备级实测（APP-063 ④）—— 已跑完（影子包 ＝ 本轮代码）：7 PASS / 4 FAIL / 4 NONE**

🔴 **纪律**（APP-064）：先拿 `MACHINE_LOCK`（`app PID 26476 started 2026-11-02 20:59:25`）⇒ 再等安静窗口（**75 s 后取得 45 s 安静**；用户 v2.1 GUI 的 CPU 增量实测 **0 s/6 s** ⇒ 不算干扰）⇒ 才开始。
🔴 **测的是本轮代码**：影子包 `shared/app065_shadow`（硬链接自 v2.2 ＋ 同步本轮 2 个改动文件，自检 PASS）。证据 `results/app/app233_device_acceptance_evidence.json`（28 123 B）。

| 判据 | 结果 | 实测 |
|---|---|---|
| ①「没有可用音色」= 0（preset / clone 臂） | ✅✅ | 0 / 0（⚠️ 见 ⑪：**曾是假 PASS**） |
| ①b CUDA 边车 REQ 数 | 无法判定 | 本机**无 CUDA 运行时** ⇒ CUDA 臂跑不了（≠ 不合格） |
| ③-① 句内欠载总和 ≤ 0.5 % | ✅ | 0 ms（限 1500） |
| ③-② ≥95 % 句子 uf = 0 | ❌ | `n_sent_uf_zero=0`（**取不到句子级 uf** ⇒ 疑口径问题） |
| ③-③ ASR RTF 增量 ≤ +0.10 | ❌ | **+0.122**（0.756→0.878）**超限** |
| ③-④ 丢句 = 0 | ✅ | 0（76 行） |
| ③-⑤ TTS 首包延迟 | 报告 | **P50 0.5651 s / P95 0.7024 s** |
| ④-① 声纹计算 ≤ 2×说话人 | ✅ | 1（说话人 1） |
| ④-② 声纹计算 ±1 s 内有 new_spk 配对 | ❌ | `n_paired=0` / `n_unpaired=1` |
| ④-③ 定时克隆更新 = 0 | ✅ | **0 次（v2.1 的 27 次已归零）** |
| ⑤-① `voice_kind=clone` 占比 ≥ 80 % | ❌ | **0 %**（76 句全 preset）⇒ 见 ⑪ |
| ⑤-② no_spk_label 回落 ≤ 2×说话人 | ✅ | 0 |
| ⑤-③ reviewer 主观核对 | 人工项 | 76 句待抽听 |
| ③(e) CPU 卸载候选 A/B | 无法判定 | 本轮未做（需 GUI+CLI 各一次、ABBA、持锁） |

✅ **相对 v2.1 的实质进步**：④-③ 定时克隆更新 **27 次 → 0**；①「没有可用音色」= 0 ⇒ **APP-061① 的「全程无声」已消除**。

#### ⑪ 🔴 **设备级实测暴露的 3 个问题（本轮新发现）**

1. 🔴 **判据①曾是「假 PASS」** —— 正则只抓 `没有可用的音色`，而**实测**故障串是 **`🔴 没有可用引擎 ⇒ spk 音色登记失败`**（`tts_worker.py:3805`）与 **`⚠️ 没有可用引擎 ⇒ 克隆无法生效`**（`:3763`）⇒ **抓不到真实故障** ⇒ 已把正则扩成**三条**（`app223` 已修，自检 5/0）。
2. 🔴 **⑤-① clone 占比 0 % 的根因 = 本机没有克隆引擎**（CUDA 边车不在本机）⇒ **APP-065 C「克隆有效性」在本机客观无法判定**（≠ 不合格）⇒ 需带 CUDA 边车的环境才能出「每段用了哪个克隆音色」的表 ＋ wav ＋ 相似度。
3. 🔴 **影子包旁路仍是 10 s**（日志 `说话人旁路窗口：10.000 s`）⇒ 因影子包 `app/asr_spk/` **只有 3 个文件**（**不含 `asr_spk_window.py`**）⇒ **实证 `app230` 的 D1-6**（客户包不含唯一事实来源 ⇒ 客户机退回 10 s）；且 ④-②「声纹无 new_spk 配对」与「`第 0 段无说话人标签：async_pending`」都与**10 s 窗口延迟**一致 ⇒ **D1 跨模块同源是克隆生效的前置条件**。

#### ⑫ 📌 **收尾复核（本轮实测）**

| 文件 | SHA256 | 字节 | mtime | 条数 |
|---|---|---|---|---|
| `status/app/CORRECTIONS_APP.md` | `SHA_RECV` | 182 008 | 2026-11-02 14:55:36 | **65** |

⇒ **本模块全程只读** `CORRECTIONS_APP.md`（未写入、未提交）⇒ **与开工基线逐字相同**（SHA 未变）。
'''


def main():
    raw = open(STATUS, 'rb').read()
    txt = raw.decode('utf-8')
    EOL = '\r\n' if '\r\n' in txt else '\n'
    if '#### ⑩ 🔄 **设备级实测' in txt:
        print('[skip] 已存在')
        return 0

    c = open(CORR, 'rb').read()
    sha = hashlib.sha256(c).hexdigest()
    mtime = datetime.datetime.fromtimestamp(
        os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    n = sum(1 for l in c.decode('utf-8').splitlines() if l.startswith('## APP-'))
    append = APPEND.replace('SHA_RECV', sha).replace('182 008 | 2026-11-02 14:55:36',
                                                    '%d | %s' % (len(c), mtime))

    lines = txt.split(EOL)
    if lines and lines[-1] == '':
        lines = lines[:-1]
    lines += append.replace('\n', EOL).split(EOL)
    new = EOL.join(lines)
    if not new.endswith(EOL):
        new += EOL
    data = new.encode('utf-8')
    print('追加后：%d B / %d 行' % (len(data), new.count('\n')))
    if len(data) > LIMIT_B or new.count('\n') > LIMIT_LINES:
        print('[ABORT] 仍超限额 ⇒ 需再压缩 §132')
        return 2
    tmp = STATUS + '.tmp_dev2'
    open(tmp, 'wb').write(data)
    assert open(tmp, 'rb').read() == data
    os.replace(tmp, STATUS)
    assert open(STATUS, 'rb').read() == data
    print('OK 已追加 ⑩⑪⑫（CORR 收尾 SHA=%s… %d B %d 条）' % (sha[:12], len(c), n))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
