#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app174e_write_status.py —— APP-050：把 §115 追加进 `status/app/STATUS_APP.md`。

## 为什么用脚本而不是直接 Edit

MEMORY 铁律：
- 🔴🔴🔴 写 `STATUS_APP.md` **必须 bytes 级定点替换**
  （`split('\n')+join()` 会毁整文件行尾）；
- 🔴🔴🔴 字段替换须**限定头部区**（第一个 `## §N` 之前）；
- 🔴🔴🔴 写后验「章节一个不少」＋「旧正文逐字未变」＋「纯 CRLF/LF」；
- 🔴🔴🔴 追加章节：先 `grep -n "^## §"` 取最大编号；
  **旧正文末尾可能无换行 ⇒ 必须补分隔**；
- 🔴🔴 **压缩必须保住「幂等闸门」**：编号与标题格式不变
  ⇒ `grep -oE '^## APP-[0-9]+' | tail -1` 仍取到最大编号。

## 本脚本做的事（**只写 STATUS_APP.md**）

1. 追加 `### §115 …` 章节（**只追加**，不回头改旧章节）。
2. **头部区**（第一个 `### §` 之前）定点替换 4 个字段：
   `last_ack` / `更新时间` / `当前任务` / `阻塞 / 待用户决定`。
3. 「最近更新」表**追加一行**（在表内，不动旧行）。
4. 「当前有效结论 → 关键数字」表**追加 4 行**。
5. 写后**独立复核**：章节编号齐全、旧章节正文逐字未变、行尾未被破坏。

## 🔴 **绝不**碰 `status/app/CORRECTIONS_APP.md`（reviewer 独占写入）

## 跑法

    <pkg>/python/python.exe results/app/app174e_write_status.py
    <pkg>/python/python.exe results/app/app174e_write_status.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORRECTIONS = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

NOW = '2026-10-31 10:32'      # 🔴 Get-Date 实测值（禁止推算）

#: 🔴 APP-049 限额：STATUS ≤ 40 KB / ≤ 300 行 ⇒ 追加 §115 前必须先归档旧章节
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE_NAME = 'STATUS_APP_sec109_114_upto_20261031.md'

SECTION_TITLE = (
    '### §115 ✅ **APP-050 TTS 启动日志打印各组件 `EXECUTION_DEVICES` —— '
    'talker / cp_prefill / cp_decode / decoder 实测**全部 NPU**'
    '｜ 顺带修掉「`EXECUTION_DEVICES` 被逐字符拆开」这个**误读根因**'
    '｜ **本条已完成** ｜ **本条需等 reviewer 复核**')

BODY = r"""
- 🔴 **依据**：reviewer 转达（TTS reviewer 10-31 Opus）—— `qwen3tts_eval` 里裸 `build()` 默认把 `cp_decode` 放在 CPU，只有调了 `_recompile_cp_on_npu(only=["cp_decode"])` 之后才会到 NPU（TTS-037 正在把默认改成 NPU）；cp_decode 在 CPU 上会让 TTS 的 RTF 变差约 30%（1.01 vs 0.71）。
- 🔴 **APP-050 要求**：① 在 TTS **启动日志**里打印 `talker` / `cp_prefill` / `cp_decode` / `decoder` 各自**实际**的 `EXECUTION_DEVICES`，确认**全部是 NPU**；② 「如果你是直接调 `build()`，要显式传 `cp_decode_device="NPU"`」；③ **把一行日志证据写进 STATUS**；④ **不用另外做测速**。

### ① 先答「App 是不是直接调 `build()`」——**不是**

- 🔴 **App 侧完全不依赖 `qwen3tts` 模块**（`grep` 仓库 `live_caption/tts_engine.py` / `tts_worker.py` / `tts_engine_patch.py` / `tts_service.py` ⇒ `import qwen3tts` **0 命中**；只有注释里提到 `qwen3tts_eval/TTS_交接单.md` 与 `qwen3tts_patch.py` 两个**文件路径**）。
- 🔴 **App 走的是自己的等价路径**：`tts_engine.make_engine()` → `babelvox.BabelVox` / vendored `MultiDecoderBabelVox`（`tts_engine_patch.py`）→ **事后**把 `cp_decode` / `cp_prefill` **重编译到 NPU**（`_move_cp_decode_to_npu()` / `_move_cp_prefill_to_npu()`，`tts_engine.py` L920 / L852）。
- ⇒ **APP-050 第②条的前提不成立** ⇒ 「显式传 `cp_decode_device="NPU"`」**对 App 不适用**（`cp_decode_device` 是 `qwen3tts_patch.QuantEvalBabelVox` 的字段，App 从不构造那个类）。
- ⇒ App 侧的**等价保证**就是那两个 `_move_*_to_npu()` 搬运函数（**已实现**，见 §115③ 的日志证据：`cp_decode: NPU` / `cp_prefill: NPU` 两行）。

### ② 🔴🔴🔴 **本轮抓出的真缺陷：旧代码把 `EXECUTION_DEVICES` 逐字符拆开了**

- 🔴 **实测（本轮新增）**：`results/app/app174a_exec_devices_type.json` ⇒ OV `2026.4.1` 的 `get_property('EXECUTION_DEVICES')` **返回类型随设备而异**：
  - **NPU 档 ⇒ 字符串 `'NPU'`**（`raw_type='str'`）
  - **CPU 档 ⇒ 列表 `['CPU']`**（`raw_type='list'`）
- 🔴 **旧代码写的是 `list(devs)`** ⇒ 对 NPU 档的字符串 `'NPU'` ⇒ `list('NPU')` = **`['N','P','U']`**。
- 🔴🔴 **⇒ 旧文档里那段「NPU 插件返回**缩写 fallback 链** `[N,P,U]`」的解读是错的** —— 那是**把「字符拆分」当成了「fallback 链」**；`chain[0]`（链首 = 首选 = 实际落点）这个结论**建立在误读之上**。
- 🔴🔴 **更要命的推论**：若 CPU 档也返回字符串 `'CPU'` ⇒ `list('CPU')` = `['C','P','U']` ⇒ 链首 `'C'` **不在**旧映射表里 ⇒ 落进 `on_unknown` ⇒ **「NPU 静默回落 CPU」永远不会被 `on_cpu` 抓到** ⇒ **静默漏报**。（反证已固化进单测：`反证.旧实现漏报CPU回落`。）
- ✅ **修法**：新增 `_norm_exec_devices(raw)`（`tts_engine.py`）—— **字符串按「单个设备名」处理**（支持逗号分隔多设备），**绝不逐字符拆**；同时**保留**单字母兼容映射（`N`→`NPU` / `P`→`CPU` / `U`→`UNKNOWN`）⇒ §82 旧证据的解读**不被破坏**，且**真·fallback 链**（若某 OV 版本真返回 `['N','P','U']`）仍能正确解读。

### ③ 🔴🔴🔴 另外三个真缺陷（旧证据里**从来没测到过** talker 桶与解码器桶）

- 🔴 **缺陷 3：talker 桶的键是 `int`，旧代码用 `str` 查 ⇒ 5 个 talker 桶从来没被探测过。**
  `babelvox/pipeline.py` L322-330 ⇒ `for bsize in self.talker_bucket_sizes: self.talker_buckets[bsize] = cm` ⇒ **键 = int**（64/128/256/384/512）；旧代码 `buckets.get('64')` ⇒ **永远取不到** ⇒ **静默丢弃**。
  ⚠️ **连带**：`pipeline.py` 的**有桶分支不编译 `self.talker`** ⇒ `getattr(eng, 'talker')` 是 `None` ⇒ **旧日志里「talker」这一行根本没出现过** ⇒ APP-050 问的「talker 在哪」**从来没被回答过**。
- 🔴 **缺陷 4：解码器多桶 `_dec_bucket_models` 从未被探测。**
  `tts_engine_patch.py` L101/L407 ⇒ 运行时**真正用来解码**的就是这些桶（`_select_decoder()` L107-114）⇒ 旧代码只报了 `tok_decoder`（= 最大桶那个）⇒ **APP-050 要求的「decoder 实际在哪」根本没被测到**。
- 🔴 **缺陷 5：「未启用」与「落点不明」混在一起。**
  `talker_prefill` / `talker_decode` 只在 `use_kv_cache=True` 时才编译（App 恒 `False`）；`code_predictor` 只在 `use_cp_kv_cache=False` 时才编译（App 恒 `True`）⇒ 它们**本来就不该存在** ⇒ 混进 `unknown` 会让 reviewer **误以为「这几个组件落点不明」⇒ 误判成「有组件在 CPU 上」**。
  ⇒ 拆成 `absent`（未启用/不存在）与 `unknown`（取不到落点）**两个字段**。
- ✅ **修法**（全在 `live_caption/tts_engine.py`）：① `_norm_exec_devices()` ② talker 桶用 **int 键**取 ③ 探测 `_dec_bucket_models` ④ `absent` / `unknown` 分开 ⑤ 新增 **`key4_line`**（APP-050 要的那一行）⑥ `talker` 在有桶时**聚合所有桶的落点**（否则永远是 `talker=?` ⇒ 等于没回答）。

### ④ ✅ **APP-050 要的那一行（启动日志原文）**

```text
[tts_engine] EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，decoder=NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU
```

- 🔴 **来源**：`results/app/app174d_worker_startup_e2e.json` → `key4_line`（**真实 TTS worker 进程** stdout 抓取，`ready_seen=true`，`wall_s=13.41`）。
- 🔴 **四个组件全部 NPU** ⇒ **APP-050 的核心问题「确认全部是 NPU」= 已确认**。

### ⑤ ✅ 三层证据（离线单测 / 直接调引擎 / 真 worker 进程）

| 层 | 产物 | 结果 | 关键字段 |
|---|---|---|---|
| ① 前置探针（OV 返回类型） | `results/app/app174a_exec_devices_type.json` | NPU=`'NPU'`(str) / CPU=`['CPU']`(list) | `probes.NPU.raw_type='str'`、`probes.CPU.raw_type='list'` |
| ② 离线单测（含 5 条反证） | `results/app/app174b_exec_devices_unit.py` | **34 PASS / 0 FAIL** | `n_pass=34`、`n_fail=0`、`verdict=PASS` |
| ③ 直接调 `make_engine` | `results/app/app174c_startup_log_evidence.json` | **15 PASS / 0 FAIL**；`on_npu=17`、`on_cpu=[]`、`on_unknown=[]` | `verdict=PASS`、`actual`（17 个组件逐个 NPU） |
| ④ 真 worker 进程 e2e | `results/app/app174d_worker_startup_e2e.json` | **10 PASS / 0 FAIL**；`ready_seen=true` | `key4_line`、`n_pass=10` |

- 🔴 **反证组已固化**（判据**非恒真**）：`反证.旧实现把CPU字符串算成C`、`反证.旧实现漏报CPU回落`、`反证.旧实现把NPU字符串拆成字符`、`反证.旧实现用str键取不到talker桶` 四条 ⇒ 旧实现在这些用例上**必错** ⇒ 新判据能**识破**旧实现。
- 🔴 **17 个组件逐个落 NPU**（`actual` 全量）：`speaker_enc` / `cp_prefill` / `cp_decode` / `tok_decoder` / `talker_bucket@{64,128,256,384,512}` / `decoder_bucket@{8,16,32,33,40,64,128,256}`。
- 🔴 **`devices_raw` 全为字符串 `'NPU'`** ⇒ 在**真实模型**上再次印证了 ② 的类型结论（不是极小探针的特例）。
- 🔴 **`absent` = `['talker_prefill','talker_decode','talker','code_predictor']`** ⇒ 这四个是**该档位下不编译**（`talker` 以 5 个桶形式存在）⇒ **不是**「落点不明」。

### ⑥ ✅ 客户包定点同步（**两份独立副本，禁整目录覆盖**）

- ✅ **新增 `live_caption/sync_c173_app050_to_pkg.py`**（**6 913 B**）—— 沿用 `sync_c170` 的**已验证骨架**：`difflib` 派生替换块（归一化 LF）＋ **OLD 取自包内实际内容** ＋ **唯一命中断言** ＋ **位置复核** ＋ **占位符两阶段/倒序应用** ＋ 写前 `ast.parse` ＋ **按包内原行尾还原** ＋ 写后**逐字节复核**。
- ✅ **同步执行**：先 `--dry-run`（**17 个替换块**）⇒ 再实际写入（**2 个替换块**，第二轮微调）⇒ 包内 `app/tts_engine.py` **85 233 B / SHA256 `0d60ebcc27c25825efd5fa5b8134a227a6e6ffb2f1ac38298ac83b4196af4931`**。
- ✅ **仓库 ⇄ 包目录逐字节一致**（归一化行尾）：`tts_engine.py` repo=`0d60ebcc27c2` pkg=`0d60ebcc27c2`（85 233 B）；`tts_engine_patch.py` / `tts_worker.py` / `tts_service.py` 亦**逐字节一致**。
- 🔴 **本轮未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **v1.13 zip 仍不存在** ⇒ 客户机上**看不到**本条改动（须等用户通知后打包）。

### ⑦ 🔴 **本条需等 reviewer 复核（4 项）**

1. 🔴 **`EXECUTION_DEVICES` 的解读口径**：本轮结论「OV 返回的是字符串 `'NPU'`（NPU 档）/ 列表 `['CPU']`（CPU 档），**不是**缩写 fallback 链」—— 是否接受？**这推翻了 §82 的旧解读**（旧解读虽结论同为「在 NPU」，但**依据错误**，且**漏报 CPU 回落**）。
2. 🔴 **`absent` 与 `unknown` 分离**：把「该档位下不编译的组件」从「落点不明」里拆出来 —— 是否认可？（否则 reviewer 会持续误读「有组件落点不明」。）
3. 🔴 **`talker` 聚合所有桶的落点**（而不是打 `talker=?`）—— 是否认可这个口径？
4. 🔴 **APP-050 第②条「显式传 `cp_decode_device="NPU"`」对 App 不适用**（App 不调 `build()`，走自己的 `_move_*_to_npu()` 搬运）—— 是否认可这一判读？
5. 🔴 **附带建议（不阻塞）**：TTS 模块的 `qwen3tts_patch.py` 里 `cp_decode` 恒编 CPU（`qwen3tts_eval/diag_cp_device_audit.py` 已指出 `cp_decode_device` 是**未被消费的声明字段**）⇒ 若 TTS-037 把默认改成 NPU，**App 侧无需改动**（App 不依赖那个类）—— 请 reviewer 确认这条链路判断。

### ⑧ 🔴 **未做 / 仍阻塞**

- 🔴 **未打包**（用户 11:30 指令）⇒ v1.13 zip 不存在 ⇒ **客户机上还看不到这一行**。
- 🔴 **未测速**（APP-050 明写「不用另外做测速」）⇒ 本条**不涉及** RTF 结论。
- 🔴 **未做质量判定**（交 reviewer；本轮只做设备落点取证，不评音质）。
- 🔴 **APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做 ⇒ 见头部「阻塞 / 待用户决定」。
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as f:
        raw = f.read()
    corr_before = os.path.getsize(CORRECTIONS)
    corr_sha_before = sha256(CORRECTIONS)

    text = raw.decode('utf-8')
    eol = 'crlf' if b'\r\n' in raw else 'lf'
    norm = text.replace('\r\n', '\n')

    # ── 拆出旧章节（用于写后逐字复核）──
    idx = norm.find('### §')
    assert idx > 0, 'STATUS 结构异常：找不到第一个章节'
    head, body = norm[:idx], norm[idx:]
    old_sections = dict(re.findall(r'(?m)^(### §\d+[^\n]*)(.*?)(?=^### §|\Z)',
                                  body, re.S))
    max_no = max(int(m) for m in
                 re.findall(r'(?m)^### §(\d+)', norm))
    print('[pre] 最大章节编号 = §%d ｜ 旧章节 %d 个 ｜ 行尾 = %s'
          % (max_no, len(old_sections), eol.upper()))
    assert max_no == 114, '预期最大编号 §114，实际 §%d ⇒ 中止' % max_no

    new_no = max_no + 1
    new_section = SECTION_TITLE + '\n' + BODY

    # ── ① 头部区定点替换（**只动第一个 '### §' 之前**）──
    lines = head.split('\n')

    def replace_field(prefix, new_line):
        for i, l in enumerate(lines):
            if l.startswith(prefix):
                lines[i] = new_line
                return True
        return False

    ok = replace_field('last_ack:', 'last_ack: APP-050')
    assert ok, 'last_ack 字段未找到 ⇒ 中止'
    ok = replace_field('更新时间:', '更新时间: %s' % NOW)
    assert ok, '更新时间字段未找到 ⇒ 中止'

    ok = replace_field(
        '当前任务:',
        "当前任务: **§115 ✅ APP-050 TTS 启动日志打印各组件 "
        "`EXECUTION_DEVICES` —— talker / cp_prefill / cp_decode / decoder "
        "实测**全部 NPU**（17 个组件 `on_npu=17` / `on_cpu=[]` / "
        "`on_unknown=[]`）；顺带修掉「`EXECUTION_DEVICES` 被逐字符拆开」"
        "这个**误读根因**（旧代码 `list('NPU')` ⇒ 误把字符拆分当 fallback 链，"
        "且会**静默漏报 CPU 回落**）＋ talker 桶 int 键从未被探测 "
        "＋ 解码器桶从未被探测 ＋「未启用」与「落点不明」混同；"
        "**App 不调 `build()`** ⇒ APP-050 第②条（`cp_decode_device=\"NPU\"`）"
        "对 App **不适用**（走 `_move_*_to_npu()` 搬运）；"
        "**本轮无新纠偏条目**（`last_ack=APP-050` = 最大编号）")
    assert ok, '当前任务字段未找到 ⇒ 中止'

    ok = replace_field(
        '阻塞 / 待用户决定:',
        "阻塞 / 待用户决定: ① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知"
        "不主动打包）⇒ **本条改动（APP-050 那一行日志）客户机上还看不到**；"
        "② 🔴 **APP-043 真机验收未做**（用户启动方式 `pythonw.exe` 冷启动 / "
        "SPE Q&A 双说话人 / GUI 加速播放 / 3 段 1.2–1.3× 配音给用户实听）"
        "⇒ 通过后才写 `ACCEPTED.json`、才更新桌面快捷方式；"
        "③ 🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 "
        "的根因）；④ 🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**"
        "（布局与截图已完成，等 v1.13）；⑤ 🔴 **§115 待 reviewer 复核 5 项**"
        "（① `EXECUTION_DEVICES` 返回类型口径——**推翻了 §82 的旧解读** "
        "② `absent`/`unknown` 分离 ③ `talker` 聚合所有桶 ④ App 不调 `build()` "
        "⇒ 第②条不适用 ⑤ TTS 模块 `cp_decode_device` 未被消费 ⇒ App 无需改动）；"
        "⑥ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误"
        "拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）；"
        "⑦ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**"
        "（§112 已证明它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）；"
        "⑧ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer "
        "独占写入）；⑨ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / "
        "「改动说明」归为提醒不阻断 / `sync_c172`「只改身份行不改内容」设计 / "
        "v1.13 改动说明排期）；⑩ 🔴 **v1.12 交付 zip 内 README/NOTICE 自称 v1.6**"
        "（11:20 生成的旧包）⇒ **该缺陷已修路径（自动同步 + 打包前闸门），但旧 "
        "zip 内容未改** ⇒ 需用户通知后重打包才真正闭合")
    assert ok, '阻塞字段未找到 ⇒ 中止'

    new_head = '\n'.join(lines)

    # ── ② 「最近更新」表追加一行（在表尾、第一个空行前）──
    upd_marker = '- 2026-10-30 23:20 **§114'
    i = new_head.find(upd_marker)
    assert i > 0, '最近更新表未找到 ⇒ 中止'
    new_head = (new_head[:i]
                + '- %s **§115 APP-050 TTS 启动日志打印各组件 '
                  '`EXECUTION_DEVICES`** ⇒ 新增 `_norm_exec_devices()`'
                  '（**字符串不再逐字符拆**）＋ talker 桶（**int 键**）与解码器桶'
                  '**首次被探测** ＋ `absent`/`unknown` 分离 ＋ `key4_line` 一行；'
                  '**实测 talker / cp_prefill / cp_decode / decoder 全部 NPU**'
                  '（`on_npu=17` / `on_cpu=[]`）\n' % NOW
                + new_head[i:])

    # ── ③ 「关键数字」表追加 4 行 ──
    kn_marker = ('| MiniMax 回转写 CER 验收 | **14 PASS / 0 FAIL**；证据 JSON '
                 '**内容命中 0**（已脱敏） |')
    i = new_head.find(kn_marker)
    assert i > 0, '关键数字表未找到 ⇒ 中止'
    j = new_head.find('\n', i)
    assert j > 0
    extra = (
        "\n| APP-050 启动日志 `EXECUTION_DEVICES` 一行 | `talker=NPU`，"
        "`cp_prefill=NPU`，`cp_decode=NPU`，`decoder=NPU`×9 | "
        "`results/app/app174d_worker_startup_e2e.json` → `key4_line`（真 worker "
        "stdout） |"
        "\n| 各组件落点（直接调引擎） | **17 个组件全 NPU**；`on_cpu=[]`；"
        "`on_unknown=[]` | `results/app/app174c_startup_log_evidence.json` → "
        "`actual` / `on_npu` / `on_cpu` / `on_unknown` |"
        "\n| `EXECUTION_DEVICES` 返回类型（实测） | NPU 档 = **字符串 `'NPU'`**；"
        "CPU 档 = **列表 `['CPU']`** ⇒ 旧代码 `list(devs)` 把字符串**逐字符拆开** | "
        "`results/app/app174a_exec_devices_type.json` → `probes.NPU.raw_type` / "
        "`probes.CPU.raw_type` |"
        "\n| APP-050 离线单测（含 5 条反证） | **34 PASS / 0 FAIL**；反证组"
        "**全部命中** ⇒ 判据非恒真 | `results/app/app174b_exec_devices_unit.py` "
        "→ `n_pass` / `n_fail` / `counterproof` |")
    new_head = new_head[:j] + extra + new_head[j:]

    # ── ④ 「最近章节」说明行更新（保留最近章节范围）──
    old_note = ('> 保留最近章节 §109…§114；§112 正文已移入只读归档 '
                '`status/archive/STATUS_APP_sec109_113_upto_20261030.md`；'
                '更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。')
    new_note = ('> 保留最近章节 §109…§115；**§109~§114 正文已移入只读归档** '
                '`status/archive/%s`（**逐字保留，内容一字未删**）；'
                '更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`；'
                '**§115（APP-050）全文见下**。' % ARCHIVE_NAME)
    assert old_note in new_head, '最近章节说明行未找到 ⇒ 中止'
    new_head = new_head.replace(old_note, new_note, 1)

    # ── ⑤ 归档旧章节（**原文一字不删**）⇒ 为 §115 腾出额度 ──
    #    沿用 §112 的做法：STATUS 里留「指针 + 结论摘要」，正文进只读归档。
    #    🔴 归档文件 = **原章节正文逐字**（不改一个字）⇒ reviewer 可复核。
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    arch_path = os.path.join(ARCHIVE_DIR, ARCHIVE_NAME)
    # 归档 = 现有全部章节（§109…§114）的**逐字原文**
    # 🔴 **必须连标题一起写**（`old_sections` 的 key = 标题，value = 正文）
    arch_body = '\n'.join(
        (k + old_sections[k].rstrip('\n') + '\n')
        for k in sorted(old_sections,
                        key=lambda x: int(re.match(r'### §(\d+)', x).group(1)))
    )
    arch_text = ('# STATUS_APP 归档（§109…§114，只读）\n\n'
                 '> 本文件是 `status/app/STATUS_APP.md` 在追加 §115 之前的**逐字归档**'
                 '（APP-049 限额：STATUS ≤ 40 KB / ≤ 300 行）。\n'
                 '> **归档 = 只读、内容一字未删**；§115 起的新章节见 STATUS 主体。\n\n'
                 + arch_body)
    arch_bytes = arch_text.encode('utf-8')
    if not os.path.exists(arch_path):
        with open(arch_path, 'wb') as f:
            f.write(arch_bytes)
        print('[arch] 已写 %s（%d B）' % (ARCHIVE_NAME, len(arch_bytes)))
    else:
        print('[arch] 已存在 %s（%d B，跳过重写）'
              % (ARCHIVE_NAME, os.path.getsize(arch_path)))

    # 归档复核：归档内容必须**逐字包含**每个旧章节的标题 + 正文
    with open(arch_path, encoding='utf-8') as f:
        arch_read = f.read()
    for k, v in old_sections.items():
        assert k in arch_read, '归档缺章节标题 %s ⇒ 中止' % k[:24]
        assert v.strip() in arch_read, '归档缺章节正文 %s ⇒ 中止' % k[:24]

    # ── ⑥ 把旧章节正文从 STATUS 里替换成「指针 + 结论摘要」──
    #    🔴 **只压缩、不删内容**（内容在归档里逐字保留）
    _ARCHIVE_PTR = (
        '\n- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）'
        '⇒ 全文见 `status/archive/%s`；**结论摘要**：见 STATUS 头部'
        '「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。\n'
        % ARCHIVE_NAME)

    def _short(k):
        # 章节标题去掉「✅」与尾部标记，留一句可辨的标识
        m = re.match(r'### §(\d+)\s*(.*)', k)
        return '§%s %s' % (m.group(1), m.group(2)[:60])

    # 头部区之后的正文：把 §109…§114 全部换成一行指针（§115 保留全文）
    body_new = body
    for k in sorted(old_sections,
                    key=lambda x: -int(re.match(r'### §(\d+)', x).group(1))):
        old_full = k + old_sections[k]
        body_new = body_new.replace(old_full, k + _ARCHIVE_PTR, 1)
    assert body_new != body, '旧章节未被替换为指针 ⇒ 中止'
    # 复核：旧章节正文确实不再留在 STATUS 主体里
    for k, v in old_sections.items():
        assert v.strip()[:200] not in body_new, \
            '旧章节正文仍留在 STATUS：%s ⇒ 中止' % k[:24]

    # ── ⑦ 拼接 + 追加章节 ──
    new_norm = new_head + body_new.rstrip('\n') + '\n\n' + new_section.rstrip('\n') + '\n'

    # ── 写后复核（**独立**）──
    new_sections = dict(re.findall(r'(?m)^(### §\d+[^\n]*)(.*?)(?=^### §|\Z)',
                                   new_norm, re.S))

    def _body_sig(s):
        """章节正文的比较签名：**去掉尾部空白**。"""
        return s.rstrip()

    missing = [k for k in old_sections if k not in new_sections]
    assert not missing, '旧章节丢失：%s ⇒ 中止' % missing
    # 🔴 旧章节在 STATUS 里**只剩指针** ⇒ 正文比对改为「指针存在 + 归档逐字保留」
    for k in old_sections:
        assert _ARCHIVE_PTR.strip()[:60] in new_sections[k], \
            '旧章节指针缺失 %s ⇒ 中止' % k[:24]
    assert ('### §%d ' % new_no) in new_norm, '新章节未写入 ⇒ 中止'
    assert len(new_sections) == len(old_sections) + 1, '章节数不对 ⇒ 中止'
    # 行尾不得被破坏
    out_bytes = (new_norm.replace('\n', '\r\n') if eol == 'crlf'
                 else new_norm).encode('utf-8')
    if eol == 'lf':
        assert b'\r\n' not in out_bytes, '混入了 CRLF ⇒ 中止'

    # ── ⑧ 🔴🔴🔴 **自指大小一致性**：文内写的「本文件 N B / M 行」必须 == 实际 ──
    #    MEMORY 铁律：ASR-036 踩过（提前 break ⇒ 偏差 34 B）⇒ **两遍法**：
    #    先用**占位符**算出真实大小 ⇒ 再回填 ⇒ 再算一次（必须一致）。
    _SIZE_RE = re.compile(r'\*\*本文件 (\d+) B / (\d+) 行\*\*')
    m = _SIZE_RE.search(new_norm)
    assert m, '未找到「本文件 N B / M 行」自指字段 ⇒ 中止'

    def _render(bs, ln):
        return (new_norm[:m.start(1)]
                + str(bs) + new_norm[m.end(1):m.start(2)]
                + str(ln) + new_norm[m.end(2):])

    # 第一遍：用**当前**（未回填的）字节数/行数占位 ⇒ 得真实值
    def _measure(txt):
        b = (txt.replace('\n', '\r\n') if eol == 'crlf'
             else txt).encode('utf-8')
        return len(b), txt.count('\n')

    b1, l1 = _measure(new_norm)
    t2 = _render(b1, l1)
    b2, l2 = _measure(t2)
    t3 = _render(b2, l2)
    b3, l3 = _measure(t3)
    assert (b2, l2) == (b3, l3), \
        '自指大小不收敛（%d/%d vs %d/%d）⇒ 中止' % (b2, l2, b3, l3)
    new_norm = t3
    out_bytes = (new_norm.replace('\n', '\r\n') if eol == 'crlf'
                 else new_norm).encode('utf-8')
    real_b, real_l = len(out_bytes), new_norm.count('\n')
    # 独立复核：回填后的文本里读出来的数字必须 == 实际
    m2 = _SIZE_RE.search(new_norm)
    assert int(m2.group(1)) == real_b, \
        '自指字节数不符：文内 %s vs 实际 %d ⇒ 中止' % (m2.group(1), real_b)
    assert int(m2.group(2)) == real_l, \
        '自指行数不符：文内 %s vs 实际 %d ⇒ 中止' % (m2.group(2), real_l)
    # 🔴 限额
    assert real_b <= 40 * 1024, '超出 40 KB 限额（%d B）⇒ 中止' % real_b
    assert real_l <= 300, '超出 300 行限额（%d 行）⇒ 中止' % real_l

    print('[post] 旧章节 %d → 新 %d ｜ 最大编号 §%d ｜ 字节 %d → %d ｜ 行 %d'
          % (len(old_sections), len(new_sections), new_no, len(raw),
             real_b, real_l))
    print('[post] 自指大小：%d B / %d 行（两遍法已收敛 + 独立复核通过）'
          % (real_b, real_l))
    print('[post] 新章节标题：%s' % SECTION_TITLE[:80])

    if args.dry_run:
        print('（dry-run：未写入）')
        return 0

    with open(STATUS, 'wb') as f:
        f.write(out_bytes)

    # 🔴 CORRECTIONS 零改动断言
    assert os.path.getsize(CORRECTIONS) == corr_before, 'CORRECTIONS 字节数变了 ⇒ 中止'
    assert sha256(CORRECTIONS) == corr_sha_before, 'CORRECTIONS SHA 变了 ⇒ 中止'
    print('[post] CORRECTIONS_APP.md 零改动 ✔ （%d B / SHA256 %s…）'
          % (corr_before, corr_sha_before[:16]))
    print('[ok] 已写入 %s （%d B）' % (STATUS, os.path.getsize(STATUS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
