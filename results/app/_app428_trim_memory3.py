# -*- coding: utf-8 -*-
"""_app428c —— MEMORY.md 瘦身第三轮：把**低价值整条**压成一行，压到注入预算（≤ 9 500 字符）内。

纪律：逐条**唯一命中**替换；压缩前全文在 `MEMORY_MODULES.md` 二十（逐字）⇒ 细节可查。
写后复核：字符数 ≤ 预算 ＋ 逐字节复核 ＋ 章节数/条目数不减少。
"""
from __future__ import annotations

import os
import re
import shutil
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
BUDGET = 9500

REPS = [
    # 头部：预算口径写准
    ("> 🔴 只留「换个会话不知道就会做错」的判据（注入预算 ≈ 9 800 字符 ⇒ 本文件 ≤ ~9 000 字符）。",
     "> 🔴 只留「换个会话不知道就会做错」的判据（注入预算 ≈ 9 800 字符 ⇒ 本文件须 ≤ 9 500 字符）。"),
    # 七：TTS-055/056 压成一行
    ("- 🔴 **TTS-055/056**：自导出 iGPU 量化 IR 三档数值崩塌（判据 ≥0.99；仅 fp16 PASS）；`babelvox INT8` 同判据也 FAIL ⇒ §73.5「崩塌⇒不值得」是**判据口径问题**（0.999/0.99 为 fp16 判据，不适用 INT8 weight-only）⇒ **撤回该因果表述**、交 reviewer 定口径。",
     "- 🔴 **TTS-055/056**：§73.5「崩塌⇒不值得」是**判据口径问题**（0.999/0.99 为 fp16 判据，不适用 INT8 weight-only）⇒ **撤回该因果表述**、交 reviewer 定口径。"),
    # 七：TTS-060 压紧
    ("- 🔴 **TTS-060（11-10）**：用户决定「OV 2026.5 等正式版发布后再继续」⇒ **OV 2026.5 方向暂停**；改后结论 =「talker 不推翻；vocoder 部分推翻（仅 microbench）—— 未验证」⇒ **不得**写成「vocoder 可上 GPU」或任何交付建议。",
     "- 🔴 **TTS-060（11-10）**：「OV 2026.5 等正式版发布后再继续」⇒ **OV 2026.5 方向暂停**；结论 =「talker 不推翻；vocoder 部分推翻（仅 microbench）—— 未验证」⇒ **不得**写成「vocoder 可上 GPU」或任何交付建议。"),
    # 八：编号纪律压紧
    ("- 🔴 编号纪律：`TTS-046`/`TTS-061` **不是** reviewer 纠偏编号（自拟工作编号）⇒ 判定新纠偏只认 `status/CORRECTIONS_TTS.md` 的 `^## TTS-` 条目。",
     "- 🔴 编号纪律：`TTS-046`/`TTS-061` 是**自拟工作编号、非 reviewer 纠偏编号** ⇒ 判定新纠偏只认 `status/CORRECTIONS_TTS.md` 的 `^## TTS-` 条目。"),
    # 十：APP-076/077 压紧
    ("- 🔴🔴 APP-076：`min_clean_ratio` 0.8→0.6 同步进 dev + 下一版包；🔴 克隆登记**不放宽**；环境变量 `LIVECAP_SPK_MIN_CLEAN_RATIO`，默认值必须来自 ASR 的 `DEFAULT_MIN_CLEAN_RATIO`（不互相 import）。APP-077：EXT 的 `bridge_token.txt` 是**固定值** ⇒ 以后的包**不带**，改首次启动在用户目录随机生成；旧包不原地改，只在 STATUS 列包名＋SHA；桥接快捷方式用 pythonw 无日志 ⇒ 新包须「启动失败弹提示框」。",
     "- 🔴🔴 APP-076：`min_clean_ratio` 0.8→0.6 同步进 dev + 下一版包；🔴 克隆登记**不放宽**；环境变量 `LIVECAP_SPK_MIN_CLEAN_RATIO`，默认值来自 ASR 的 `DEFAULT_MIN_CLEAN_RATIO`（不互相 import）。APP-077：EXT 的 `bridge_token.txt` 是**固定值** ⇒ 以后的包**不带**，改首次启动在用户目录随机生成；旧包不原地改；桥接快捷方式用 pythonw 无日志 ⇒ 新包须「启动失败弹提示框」。"),
    # 四：反证构造压紧
    ("- 🔴🔴 反证构造也会坏：删行致 `if` 块空 ⇒ `SyntaxError` ⇒ 静默「无法判定」⇒ 改成把那行替换成 `pass`；多调用点须破坏全部。`ast`+`exec` 坑：丢 `Import` ⇒ NameError；**漏抽被测函数依赖的常量/函数（如 `map_language`/`LANG_MAP`）⇒ 落 except ⇒ 假 FAIL**；丢模块级常量 ⇒ 反证组没识破；反证须改「被测的那个对象」。",
     "- 🔴🔴 反证构造也会坏：删行致 `if` 块空 ⇒ `SyntaxError` ⇒ 静默「无法判定」⇒ 改成把那行替换成 `pass`；多调用点须破坏全部。`ast`+`exec` 坑：丢 `Import` ⇒ NameError；**漏抽被测函数依赖的常量/函数（如 `map_language`/`LANG_MAP`）⇒ 落 except ⇒ 假 FAIL**；反证须改「被测的那个对象」。"),
    # 四：闸门判据条压紧
    ("- 🔴🔴 **闸门自己的判据也会是错的**（2026-11-10 实例）：「兜底 == ASR 当前默认值」这个判据本身错（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）⇒ 正确判据是「**兜底窗长 == IR 兜底窗长**」⇒ **写闸门前先问「这条判据若被人当真去改生产代码，会不会改坏」**。",
     "- 🔴🔴 **闸门自己的判据也会是错的**（2026-11-10 实例）：「兜底 == ASR 当前默认值」这个判据本身错（会诱导把兜底 10.0 改成 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ **旁路静默降级、零标签**）⇒ 正确判据是「**兜底窗长 == IR 兜底窗长**」⇒ **写闸门前先问「这条判据若被人当真去改生产代码，会不会改坏」**。"),
    # 六：遥测条压紧
    ("- 🔴 **遥测语义**：`voice_spk` ＝ **实际使用的克隆音色**（非下传的 spk）；标签晚到回落预设 A 时写 `null` ⇒ 与「无标签」不可区分 ⇒ 已补 `spk_label`＋`voice_inherited`＋逐句 `seg`。",
     "- 🔴 **遥测语义**：`voice_spk` ＝ **实际使用的克隆音色**（非下传的 spk）；标签晚到回落预设 A 时写 `null` ⇒ 与「无标签」不可区分 ⇒ 已补 `spk_label`＋`voice_inherited`＋`seg`。"),
    # 九：末条压紧
    ("- 🔴 写 STATUS 的自检别写「CRLF 个数不变」这类**伪不变量**（新注释行数不同 ⇒ 个数本就会变 ⇒ 把正确改动判成 FAIL）⇒ 用真不变量「**无裸 LF**」；写前自检 FAIL ⇒ **源文件必须零改动**。",
     "- 🔴 写 STATUS 的自检别写「CRLF 个数不变」这类**伪不变量**（新注释行数不同 ⇒ 个数本就会变 ⇒ 把正确改动判成 FAIL）⇒ 用真不变量「**无裸 LF**」；写前自检 FAIL ⇒ 源文件零改动。"),
    # 十二：新发现条压紧
    ("- 🔴 **新发现（只报不改）**：`--tts-voice A`＋说话人识别开 ⇒ **78/78 句仍用 self_ref 克隆音色** ⇒ 与 v2.4 验收口径冲突 ⇒ 根因 = `_maybe_send_self_ref` 缺 `_want_clone` 闸门。",
     "- 🔴 **新发现（只报不改）**：`--tts-voice A`＋说话人识别开 ⇒ **78/78 句仍用 self_ref 克隆音色** ⇒ 与 v2.4 验收口径冲突 ⇒ 根因 = `_maybe_send_self_ref` 缺 `_want_clone` 闸门。"),
    # 五：设备归属条压紧
    ("- 🔴🔴 App 实际解码器是 `_dec_bucket_models`（`talker_buckets` 键是 int）⇒ 只报 `tok_decoder` 会漏；「未启用」≠「落点不明」⇒ 须分 `absent`/`unknown`；App 不调 `build()` ⇒ `cp_decode_device` 不适用。",
     "- 🔴🔴 App 实际解码器是 `_dec_bucket_models`（`talker_buckets` 键是 int）⇒ 只报 `tok_decoder` 会漏；「未启用」≠「落点不明」⇒ 须分 `absent`/`unknown`；App 不调 `build()` ⇒ `cp_decode_device` 不适用。"),
    # 二：待裁定条压紧
    ("- 🔴 待裁定：`lock_state()` 的 `stale_boot` 优先于 PID 存活 ⇒ 别模块时钟回调会抢活锁 ⇒ 两模块同占设备。",
     "- 🔴 待裁定：`lock_state()` 的 `stale_boot` 优先于 PID 存活 ⇒ 别模块时钟回调会抢活锁。"),
    # 三：报数条压紧
    ("- 🔴 报数要指到「配置＋结果文件＋字段」；没落盘不能写「已交付」。",
     "- 🔴 报数要指到「配置＋结果文件＋字段」；没落盘不能写「已交付」。"),
]


def main() -> None:
    t = open(MEM, encoding='utf-8').read()
    before = len(t)
    n_sec_before = len(re.findall(r'^## ', t, re.M))
    n_bul_before = len(re.findall(r'^- ', t, re.M))
    for a, b in REPS:
        n = t.count(a)
        if n != 1:
            print('MISS(%d) %s' % (n, a[:44]))
            continue
        t = t.replace(a, b, 1)
    after = len(t)
    n_sec = len(re.findall(r'^## ', t, re.M))
    n_bul = len(re.findall(r'^- ', t, re.M))
    ok = (after <= BUDGET and n_sec == n_sec_before and n_bul == n_bul_before)
    print('chars %d -> %d (budget %d) sections %d->%d bullets %d->%d %s'
          % (before, after, BUDGET, n_sec_before, n_sec, n_bul_before, n_bul,
             'OK' if ok else 'NOT OK'))
    if ok:
        bak = MEM + '.bak_pre_slim_20261111_%s' % time.strftime('%H%M%S')
        shutil.copy2(MEM, bak)
        tmp = MEM + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(t)
        os.replace(tmp, MEM)
        assert open(MEM, encoding='utf-8').read() == t, 'byte verify failed'
        print('WROTE %s (%d bytes)' % (MEM, os.path.getsize(MEM)))


if __name__ == '__main__':
    main()
