#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app143c_email_body.py — **生成 §237–§239 的 STATUS 邮件正文**（APP-143 c）。

## reviewer APP-143 c 原文
> 马上补发一封 `[C4][A][STATUS][APP] §237–§239` 邮件（每节 3–5 行，
> 写上数字和提交号）；以后每一节都发。

## 🔴 纪律
* 正文**由脚本生成** ⇒ 落盘文件与实发**逐字节相同**（入库件 = 实发件）；
* **不引用会议原文或译文**（APP-143 第 4 项 ＋ APP-144 ① 第 6 项）
  ⇒ 只写文件名、行号、编号；
* **不贴长表** ⇒ 每节 3–5 行；长表在 STATUS 正文里；
* **不建附件**（base64 人工转写必错 ⇒ 走文件读取，但本邮件**不需要附件**）。

## 用法
```
python live_caption/_app143c_email_body.py
```
"""
from __future__ import annotations

import io
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(HERE, '_app143c_email_body.txt')

SUBJECT = ('[C4][A][STATUS][APP] §237–§239 STATUS —— '
           'APP-136 GitHub 历史抹除属实（只含 2 份 jsonl，已复核）＋ '
           'APP-134 a 两臂数字复算一致 ＋ APP-134 b 按原判据通过（ABBA 四臂）＋ '
           'APP-137 MiniMVP v1.2 候选目录（MT2 口径，未出 zip）＋ '
           'APP-135 MT3 显式贪心单测通过；'
           '并更正 §239 对作废那轮 ABBA 的归因（根因＝轮询阻塞无超时）；'
           'last_ack=APP-137')

BODY = """# §237–§239 STATUS —— App 模块（Confucius4 LiveCaption）

**模块**：App（`C:\\Users\\Trekker-PTL\\confucius4-openvino`）
**本机时间**：{ts} (GMT+8)
**当前 last_ack**：**APP-137**（本轮执行到 APP-134 c；APP-138–145 已读，队列按 APP-142/143 执行）

## §237（APP-136）—— GitHub 历史抹除属实
- 两份含内部会议译文的 jsonl 已从 `origin/main` 抹掉并强推（改写前 04358d3 → 改写后 721346c）；`live-dub-ext` 逐字未动。
- 本轮 10 项独立复核全 PASS（按精确 git blob SHA 逐个验：两个旧 blob 均 ABSENT；`git log --all` 为空；远端已无旧对象）。
- `v2.6.staging` 已删；`.gitignore` 落 12 条类别级规则（`*.tts.jsonl` / `*.mt.txt` / `*.transcript.txt` ＋ 9 条已知路径）。
- 🔴 **如实登记**：另有 13 个**存量**文件带同一份会议译文（早于 94f95f6，不在 APP-136① 点名范围）⇒ 本轮**只登记、未擅自处理** ⇒ 待 reviewer 裁定。**（APP-144① 后续已按用户决定抹掉，见下）**

## §238（APP-137 §1–§3 ＋ APP-134 a ＋ APP-135 §1–§3）
- **APP-134 a 两臂全 PASS**（rc=0，`lock_lost` 0）：TTS=NPU 臂媒体结束 `n_pending`=**49**（40.5%）⇒ 排空 **292.77 s** ⇒ 末句滞后 **279.12 s**／斜率 **−0.534 s/s**（r²=0.943，线性不回落）／`synth_rtf`=**1.2792**；AUTO 臂（＝ `Start_Bridge` 实际配置）`n_pending`=**1**（0.8%）⇒ 排空 **4.01 s** ⇒ 滞后 **0.0 s**／`synth_rtf`=**0.5907**。
- 🔴 **口径更正**：「丢句 0／收尾积压 0」**不成立**。正确表述：**不是丢句，是迟到**（排空后 `n_pending` 确实归 0、dubs=123=n_emitted、`dup_dropped`=0）。
- 🔴 **APP-134 问题② 实证**：AUTO 档实测 **MT=NPU ＋ TTS=CUDA 边车**（RTX 5050，端到端启动 45.3 s）⇒ 与 App 出厂默认 GPU.0/GPU.0/NPU **不是同一档**。
- **APP-137**：dev 树 profile 改造（并入 EXT 全部功能＋音色克隆／c13 不进 MiniMVP）**行为级 18/18 PASS**；v1.2 候选目录已建（**10 891 文件 / 6.360 GiB**，**不打 zip、不签 ACCEPTED**）；**包内容核对 22/22 PASS**（克隆音色目录只有 preset_A.wav、无媒体文件、无 CUDA DLL、profile 语义正确）。
- **APP-135 §1–§3**：dev 树 MT2→**MT3**（`LIVECAP_MT_VARIANT=mt2` 可切回）；🔴 **实测确认** `LLMPipeline.get_generation_config()` 确实吃到模型自带默认值 ⇒ **逐项显式覆盖**（贪心 + 中性采样参数）；**单测真跑 ALL PASS**（含反证组）。

## §239（APP-134 b）—— 按原判据通过 ＋ 🔴 **归因更正**
- **ABBA 四臂全 rc=0**（on→off→off→on，锁 18:16:19–19:13:05，`lock_lost` **0**）：守卫开两臂均值 vs 关两臂均值 ⇒ `synth_rtf` 中位**快 5.9%**、P90**慢 4.1–4.3%**、`max_lag` **少 18.7%** ⇒ 只有 P90 一项方向变差且幅度 ≤5% ⇒ **按原条款「差值 ≤5% 算不变差」通过**。cp 自检数字已写进 §229 §3。
- 🔴 **本条更正 §239 的归因**：reviewer 指出「臂目录名冲突」**解释不了**那次卡住（arm3 在 arm2 结束 3 s 后才起）⇒ **根因是「一次 stats 轮询阻塞了 65 分钟，而客户端没有接收超时」**（`drain_elapsed` 3924 s vs `drain_cap` 300 s）⇒ 臂名冲突只是**附带问题**（导致 bridge.log 被覆盖）。**已按 APP-143 b 修**：stats 接收超时 ＋ 墙钟硬上限 ＋ `timing_valid`（媒体送入 >1.2×片长即标 false）。
- 🔴 **超时的反证**（reviewer 要求）：人为让 stats 不回 ⇒ 驱动器 **10.0 s** 退出并如实报告超时（上限 cap+10 s）；去掉超时判定的旧版**确实挂死** ⇒ 判据有鉴别力。

## 提交号（main）
- `0f00e2d` §238 前批（APP-136/137/135）｜`6986632` §238｜`00a9df1` APP-135 §4
- `2c74f62` §239｜`ec7ab50`/`08a1da0`/`d1ae06a` APP-134 c｜`d5bf3e5` 候选起不来的真缺陷
- `bbe2a78` **APP-144①**：按用户决定改写历史，抹掉剩余 **14 个**含会议译文的文件（12 个转写/译文产物**整份去掉** ＋ 2 个说明/证据文件**只替换句子**）⇒ 改写后 `origin/main` 全历史 grep **0 命中**；`live-dub-ext` SHA **未变**（b2a4978）
- `22a4c28` **APP-143 b**：stats 超时 ＋ 墙钟硬上限 ＋ timing_valid ＋ 超时反证

## 🔴 待 reviewer 裁定 / 未完成
1. **APP-134 b 的 5% 判据**：按原条款已通过（只有 P90 一项方向变差、幅度 ≤5%）。
2. **APP-134 c**：三臂口径全部核对通过（c13 开／c13 关／TTS=GPU.0）；🔴 **TTS 不能放 GPU.0**（`synth_rtf` 22.24＝NPU 的 21 倍 ⇒ 触发失控闸 ⇒ 33 句被中止、82 句排不空）；**18 段抽听片段**已落 `results/app/app123_listen/`（每臂 6 段，取自 `player_mix.wav`＝播放端真正听到的混音）；**只切片段、不做音质判定**，质量请 reviewer 抽听。
3. **队列**：按 APP-142/143 ⇒ 接下来 **APP-135+138（MT3 进 dev 树与 EXT）→ APP-139（turbo）→ 候选目录换成最终配置 → 最终配置三轮**。
4. **未完成**：候选目录换 MT3、`--check` 自检、最终配置三轮、APP-138 的 EXT v0.4.22（由本线程单独提交）、APP-135 §5。
5. **未打包 zip**／未改任何客户包／未调 MiniMax／未连 B 机／未改 `CORRECTIONS_APP.md`。

**本轮起每一节都发 STATUS 邮件**（APP-143 c）。
"""


def main():
    body = BODY.format(ts=time.strftime('%Y-%m-%d %H:%M'))
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(body)
    with io.open(OUT.replace('.txt', '_subject.txt'), 'w', encoding='utf-8',
                 newline='\n') as fh:
        fh.write(SUBJECT)
    print('正文已生成：%s（%d B）' % (OUT, len(body.encode('utf-8'))))
    print('主题已生成：%s（%d B）' % (OUT.replace('.txt', '_subject.txt'),
                                     len(SUBJECT.encode('utf-8'))))
    print('行数：%d' % len(body.split('\n')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
