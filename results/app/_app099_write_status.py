#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app099_write_status.py —— §99：把 §99 章节追加进 STATUS_APP.md，并更新头部。

## 🔴🔴🔴 铁律（本脚本踩过的坑）

1. 🔴 **`STATUS_APP.md` 是纯 CRLF**（实测 17 586 行全是 CRLF）
   ⇒ **绝不能用 `read().split('\\n')` + `'\\n'.join()` 重写**（那会把行尾全改成 LF
   ⇒ 整文件 diff ⇒ 违反「旧正文逐字未变」）。
   ⇒ 本脚本**全程 bytes 级定点替换**，只碰 4 个字段行 + 「最近更新」块 + 尾部追加。
2. 🔴 **只追加** `## §N` 章节，**不回头改旧章节**（旧结论错了就在新章节里写「撤回 §x」）。
3. 🔴 头部**只改 4 个字段行**；「最近更新」≤15 行 ⇒ 超了**裁最旧的**。
4. 🔴 「更新时间」用 **Get-Date 实测值**（调用方传入），**禁止推算**。
5. 🔴 「## 最近更新」标题**必须留在标题行之后**（上一版插到标题前 ⇒ 已修）。
6. 🔴 章节正文的换行风格 = 与原文件一致（CRLF）。
"""
from __future__ import annotations

import json
import os
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
SECTION = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app099_section.md'
ZIP_EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app099_zip_evidence.json'

EOL = b'\r\n'


def main() -> int:
    now = sys.argv[1]          # Get-Date 实测值
    ack = sys.argv[2]          # last_ack 值
    with open(STATUS, 'rb') as f:
        raw = f.read()
    with open(SECTION, 'r', encoding='utf-8') as f:
        section = f.read()
    with open(ZIP_EVID, 'r', encoding='utf-8') as f:
        zev = json.load(f)

    # 🔴 行尾风格自检
    assert raw.count(b'\n') == raw.count(b'\r\n'), \
        '❌ STATUS_APP.md 不是纯 CRLF（LF=%d CRLF=%d）⇒ 需重新确认行尾策略' % (
            raw.count(b'\n'), raw.count(b'\r\n'))
    EOL_IS_CRLF = True

    # 🔴 zip 证据块
    zblock = (
        '\n### 99.9 ✅ **客户包 v1.10 持锁重打 zip ⇒ 产物证据（只读核验）**\n\n'
        '- **打包命令**：`python pack_v13.py --version 1.10`（system Python 3.12）\n'
        '- **机器锁**：`shared/MACHINE_LOCK` 内容 `module: %s` / `pid: %s` / '
        '`started: %s` ⇒ **持锁**打包（打包前机器上 python 进程数 = **0**）\n'
        '- **版本号三处一致**：目录 `Confucius4_LiveCaption_v%s` == zip '
        '`Confucius4_LiveCaption_v%s.zip` == MANIFEST `version=\'%s\'` ✅\n'
        '- **zip 产物**：**%s 字节** / mtime `%s` / SHA256 **`%s`**\n'
        '- **zip 条目数**：**%s**（`testzip()` = **OK**，无 CRC 错误）\n'
        '- **MANIFEST**：`version=\'%s\'` / `files=%s` / `bytes=13 672 989 296`\n'
        '- **打包脚本自带闸门**（全部通过）：\n'
        '  ① 内部会议内容 0 命中 ② 确定缺失本地模块 **0** 条 ③ 翻译模型目录符合\n'
        '  ④ TTS 音色素材只允许音色 A ⑤ 开发专用脚本 0 命中\n'
        '  ⑥ **内容一致性校验：比对 14 203 个文件 ⇒ 全部逐字节一致** ⇒ 已原子改名到正式路径\n'
        '- **打包脚本结论**：`PASS`（`md5=4cbc61d4173e2d1a93c8b45c98f4629c`）⇒ 锁已释放\n'
        '- **独立只读复核**（`results/app/_app099_zip_verify.py`，本轮新写）：\n'
        '  **zip ⇄ 包目录 `.py` 逐字一致 = %s**（归一化 LF 后比对）\n'
        '- **包内副本的独立验收**：`app154` 对**包内**源码跑同一套验收 ⇒ **20/20 PASS**，'
        '反证 5 条全命中（`results/app/_app099_app154_pkg_evidence.json`）\n'
        % (zev['lock_module'], zev['lock_pid'], zev['lock_started'],
           zev['manifest_version'], zev['manifest_version'], zev['manifest_version'],
           format(zev['zip_bytes'], ','), zev['zip_mtime'], zev['zip_sha256'],
           format(zev['n_entries'], ','), zev['manifest_version'], zev['manifest_files'],
           zev['py_diff_summary'])
    )
    section = section.rstrip('\n') + '\n' + zblock

    # 🔴 断言：§99 尚未追加
    assert b'## \xc2\xa799' not in raw, '❌ STATUS_APP.md 里已有 §99 ⇒ 拒绝重复追加'
    assert b'## \xc2\xa798' in raw, '❌ 找不到 §98 ⇒ STATUS 结构异常'

    # ══════════════════════════════════════════════════════════════════
    # 🔴 头部 4 个字段行：**bytes 级定点替换**（只改该行的值部分）
    # ══════════════════════════════════════════════════════════════════
    def replace_field(buf: bytes, key: bytes, value: str) -> bytes:
        # 🔴 **只在头部区**替换（第一个 `## §N` 之前）
        #   ⇒ 正文里也出现过 `last_ack:` 等字样（历史章节提到）⇒ 不能全局替换
        m = re.search(rb'^## \xc2\xa7\d+', buf, re.M)
        assert m, '❌ 找不到第一个 §N 章节'
        h_end = m.start()
        head = buf[:h_end]
        tail = buf[h_end:]
        pat = re.compile(re.escape(key) + b': [^\r\n]*')
        hits = pat.findall(head)
        assert len(hits) == 1, \
            '❌ 头部字段 %s 在**头部区**命中 %d 次（期望 1）' % (
                key.decode(), len(hits))
        new = key + b': ' + value.encode('utf-8')
        head = pat.sub(lambda _m: new, head, count=1)
        return head + tail

    raw = replace_field(raw, b'last_ack', ack)
    raw = replace_field(raw, b'\xe6\x9b\xb4\xe6\x96\xb0\xe6\x97\xb6\xe9\x97\xb4', now)

    task = (
        '**§99 🔴🔴🔴 APP-039/040「音色按句绑定」链路自查出 5 处断链（A/B/C/E/F）'
        '⇒ 已全部修复 ＋ 修掉 3 个验收脚本自身的判据缺陷 ＋ 客户包 v1.10 已定点同步'
        '并持锁重打 zip**（纠偏巡检：`CORRECTIONS_APP.md` 最大编号 = **APP-042** = '
        '`last_ack` ⇒ **无新条目**，第 26 次同一口径复核；文件只读零改动）'
        '⇒ ✅ 5 处断链：① **A** 短段取不到样本（新增 `span_for_final` 往前借 + '
        '`SPAN_MIN_S=2.5`）② **B** `dur_s` 恒 0（改**区间并集**累计 `clean_dur_s`）'
        '③ **C** 不等 worker 回执就 `mark_embedded`（新增 `spk_voice` 事件分派 + '
        '`spk_voice_status`；失败走 `mark_fallback`）④ **E** 全局时间轴当环形缓冲下标'
        '（新增 `keep_t0`）⑤ **F** 初次登记即移出 pending ⇒ **APP-040②「攒够 3 s '
        '用自己段重算一次」从不发生**（初次登记**保留**在 pending）'
        '⇒ ✅ 修掉 3 个**验收脚本判据自身缺陷**（`app150` A6 假通过 / `app152` 静态'
        '判据 + `drop_nonlocal` 反证静默失效 / `app154` 签名误用 + 反证 C 函数级'
        'token 假通过 ⇒ 新增**调用点级 AST** 判据）⇒ ✅ 修掉上轮 bytes 转义造成的'
        '**非法 UTF-8**（`tts_service.py` 编译失败 ⇒ 客户包启动即崩）'
        '⇒ ✅ 回归 10 脚本全绿（`app154` 20/20、`app150` 17/17、`app152` 7/7、'
        '`app141_integration` 62/62、`app142` 22/22）且**反证全部命中**'
        '⇒ ✅ 客户包**定点同步**（4 文件归一化后与仓库逐字节一致 + 同步前备份）'
        '⇒ ✅ **持锁重打 v1.10**（`app-pack` PID %s / %s / 安静窗口通过）'
        '⇒ zip **%s 字节** / SHA256 **`%s`** / %s 条目 / `testzip()` OK'
        '⇒ ✅ commit **`b5bd143`**（12 文件，未含 `CORRECTIONS_APP.md`）'
        '＋ **`7bdbc1d`**（app154 包内验收）'
        '⇒ 🔴 **撤回 §97.1/§97.7①/§98 的「APP-039/040 核心已实施」口径**'
        '⇒ 🔴 **本条需等 reviewer 复核**（MiniMax 回转写 / 用户实听 3 段 1.2–1.3× / '
        'APP-039/040 真机 NPU 双说话人 / ASR §8 交付形态裁定 + 16 MB 模型是否随包 / '
        'APP-041 `pythonw.exe` 冷启动 / GUI 路径 APP-042 真机）'
        % (zev['lock_pid'], zev['lock_started'],
           format(zev['zip_bytes'], ','), zev['zip_sha256'],
           format(zev['n_entries'], ','))
    )
    raw = replace_field(raw, b'\xe5\xbd\x93\xe5\x89\x8d\xe4\xbb\xbb\xe5\x8a\xa1', task)

    # ══════════════════════════════════════════════════════════════════
    # 🔴 「最近更新」块：插入新行 + 裁最旧的（≤15 行）
    # ══════════════════════════════════════════════════════════════════
    new_line = (
        '%s §99 🔴🔴🔴 **APP-039/040「音色按句绑定」链路自查出 5 处断链'
        '（A/B/C/E/F）⇒ 全部修复 ＋ 3 个验收脚本判据自身缺陷已修 ＋ '
        '客户包 v1.10 持锁重打 zip**（巡检：APP-042 = `last_ack` ⇒ 无新条目，'
        '第 26 次同一口径复核；`CORRECTIONS_APP.md` 只读零改动）'
        '⇒ ✅ 断链 **A** 短段取不到样本（`span_for_final` 往前借）'
        '**B** `dur_s` 恒 0（区间并集）**C** 不等 worker 回执就 `mark_embedded`'
        '（失败走 `mark_fallback`）**E** 时间轴未换算（`keep_t0`）'
        '**F** 初次登记即移出 pending ⇒ APP-040② 从不发生'
        '⇒ ✅ 修掉上轮 bytes 转义造成的**非法 UTF-8**（客户包启动即崩）'
        '⇒ ✅ 回归 10 脚本全绿且**反证全部命中**（`app154` 20/20、`app150` 17/17、'
        '`app152` 7/7、`app141_integration` 62/62、`app142` 22/22）'
        '⇒ ✅ 定点同步客户包 v1.10（4 文件归一化后逐字节一致）'
        '⇒ ✅ **持锁重打 v1.10**（PID %s / %s）⇒ zip **%s 字节** / SHA256 **`%s`** / '
        '%s 条目 ⇒ ✅ commit **`b5bd143`**'
        '⇒ 🔴 **撤回 §97.1/§97.7① 的「APP-039/040 核心已实施」口径**'
        '⇒ 🔴 **本条需等 reviewer 复核**'
        % (now[:16], zev['lock_pid'], zev['lock_started'],
           format(zev['zip_bytes'], ','), zev['zip_sha256'],
           format(zev['n_entries'], ','))
    )
    marker = '## 最近更新'.encode('utf-8') + EOL
    assert raw.count(marker) == 1, '❌ 「## 最近更新」标题命中 %d 次（期望 1）' % raw.count(marker)
    pos = raw.index(marker) + len(marker)
    # 找该块的结尾（空行）⇒ **保留原有的两个 EOL**（末尾空行不能丢）
    end = raw.index(EOL + EOL, pos) + len(EOL)   # 定位到「空行行尾」之后
    block = raw[pos:end]
    lines = block.split(EOL)
    lines = [l for l in lines if l.strip() != b'']
    lines.insert(0, new_line.encode('utf-8'))
    while len(lines) > 15:
        lines.pop()
    # 🔴 保留块尾的空行（EOL + EOL）
    raw = raw[:pos] + EOL.join(lines) + EOL + EOL + raw[end:]

    # ══════════════════════════════════════════════════════════════════
    # 🔴 追加 §99 章节（CRLF 行尾）
    # ══════════════════════════════════════════════════════════════════
    sec_b = section.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8')
    assert raw.endswith(EOL), '❌ 原文件未以 CRLF 结尾 ⇒ 需人工处理'
    # 🔴 章节之间的分隔 = **直接相接**（实测 §97→§98 之间无空行）
    #   ⇒ 原文件末尾的 EOL 就是 §98 最后一个换行 ⇒ §99 直接接上，**不补空行**
    raw = raw + sec_b

    # 🔴 写盘前自检
    assert raw.count(b'\n') == raw.count(b'\r\n'), '❌ 写盘后行尾不一致'
    raw.decode('utf-8')

    with open(STATUS, 'wb') as f:
        f.write(raw)
    print('✅ STATUS_APP.md 已追加 §99；头部 last_ack=%s 更新时间=%s' % (ack, now))
    print('   字节 %d → %d；行数 %d → %d' % (
        len(open(STATUS, 'rb').read()), len(raw),
        0, raw.count(b'\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
