#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MEMORY.md 第二轮压缩（**按行前缀**替换，fail-closed）。"""
import hashlib
import os
import shutil
import sys
import tempfile

P = r'C:\Users\Trekker-PTL\confucius4-openvino\.workbuddy\memory\MEMORY.md'
LIMIT = 9700

# (唯一前缀, 新整行)
LINES = [
    ('-🔴**复核三坑**：',
     '-🔴**复核三坑**：①判「只改一行」须**对写前备份逐行 diff**＋`numstat` 恰 1/1；②**已是 UTF-8 字节的串不可再 `.encode()`**⇒断言**假 FAIL**⇒复核按 UTF-8 **文本**比对；③自检别写伪不变量⇒FAIL 时源文件零改动。'),
    ('- 🔴🔴🔴**验收脚本必须走「产品同款调用路径」**',
     "- 🔴🔴🔴**验收脚本必须走「产品同款调用路径」**（2026-11-20 三个假 FAIL 都这么来的）：① `make_engine()` **没有 `voice` 参**（音色走 `speaker_embed`）② 喂引擎**必须用 `map_language()`**（`'zh'→'Chinese'`）⇒直传代号会**回落 language-agnostic** ③ `translate(text,tgt)` 的 `tgt` 要**代号** ④ `ext/bridge` 必须 **`-m ext.bridge`** ⑤ 反证组查**产品的闸**。"),
    ('- 🔴🔴🔴**计时类结论有效性（APP-115）**',
     '- 🔴🔴🔴**计时类结论有效性（APP-115）**：`timing_valid` ＝ **锁未被动过**＋**无外部大 IO**＋**逐句 `synth_rtf` P90≤0.75**；🔴**锁丢失 ⇒ 计时作废**（计数类仍成立）；🔴**外部 replay 作业污染计时**⇒计时臂须独占机器。🔴**「锁未被抢」≠「机器没被占」**⇒查**慢句是否 100 % 落在外部作业窗口内**。'),
    ('- 🔴🔴🔴`core.autocrlf=true`',
     '- 🔴🔴🔴`core.autocrlf=true` ＋ 无 `.gitattributes`⇒clone 与 HEAD 逐字节不同（LF→CRLF）⇒①比对须归一化行尾 ②clone 里字符串锚点恒 0⇒定点同步必失效 ③读入归一化、写回还原行尾；还原原字节用 `git cat-file blob HEAD:<path>`。🔴**`git status` 的 ` M` 可能是 autocrlf 假阳性**；🔴**`CORRECTIONS_APP.md` 的 ` M` 是 reviewer 真追加⇒永不 `git add`**。'),
    ('- 🔴🔴🔴**APP-113 §1 排队等待**',
     '- 🔴🔴🔴**APP-113 §1 排队等待**（`TtsReadyQueue`，GUI/CLI 共用）：TTS 未就绪⇒终稿**进队列**（参数冻结）⇒就绪后 FIFO 补发⇒**一句不丢**；🔴**APP-114 §2.1 已取消 120 s 溢出丢弃**⇒仅 worker 失败/退出才清空。'),
    ('- 🔴🔴**「包级闸门」两条（§203）**',
     '- 🔴🔴**「包级闸门」两条（§203）**：**枚举必须覆盖磁盘上全部客户包**＋ **缺 `app/tts_worker.py` 的目录不得静默丢弃**⇒单列 `SKIP_NO_TTS_WORKER`。'),
    ('> 逐字全文在 `MEMORY_MODULES.md`',
     '> 全文在 `MEMORY_MODULES.md`（模块号见该文件目录）；**§214/§215⇒`STATUS_APP_sec21{4,5}_detail_20261117.md`**；**§217⇒`STATUS_APP_sec217_detail_20261120.md`**；存档 `MEMORY_ARCHIVE_*.md`。'),
    ('- 🔴 **TTS-074/075（11-20；⇒MODULES 四十四）**',
     '- 🔴 **TTS-074/075（11-20；⇒MODULES 四十四）**：🔴 §100 复核：「交叉淡化」接法错 ⇒ **每块边界丢 50 ms 真实音频**（30 句丢 **12.85 s / 175.0 s = 7.3%**）⇒ **撤回「长度守恒」**；🟢 改回**直接拼接**后重跑 ⇒ 采样数 = n_frames×1920 全满足、**SNR 中位 30.2762 dB**、RTF 中位 0.7705、欠载 0；🔴「predictor 52.5 ms/帧」是 **TTS-073 的数字 ⇒ 撤回**；🔴 交付零变化/不进包/App 零动作；🔴 NPU 臂未做。🟢 **新铁律 R42**：**块间拼接前先确认「两块是否真的重叠」**；判据：① 采样数 = n_frames×1920 ② `dur_s/n_frames` 恒 = 0.08 ③ SNR ≥ ctx=25 基线。'),
    ('-🔴**目标机交付**：地址',
     '-🔴**目标机交付**：地址 **192.168.2.206**（.194 旧）⇒目录 `C:\\Users\\63446`／无真 Python／C: 仅 82 MB；🔴**凭据会话级**⇒**两端 SHA256 闭环不了**；🔴**大文件别走 SFTP**⇒HTTP(range)+`curl -C -`（73–89 MB/s）；🔴zip+解压 > 可用⇒**须先删 zip（用户授权）**；🔴目标 sm_89 vs 验收 sm_120⇒**须实机 `--check`**。'),
    ('-🔴`last_ack=APP-118`',
     '-🔴`last_ack=APP-118`（118 条；APP-116/117/118 **邮件与文件两源一致 ⇒ 只执行一次**）⇒ **v2.5 = 全集**（CUDA TTS＋Qwen3-ASR 0.6B＋EXT v0.4.18＋10 语种＋APP-096～117 修复）｜🔴**未打 zip**｜**24.26 GiB / 48 789 文件**。'),
    ('- 🔴🔴**闸门自己的判据也会错**',
     '- 🔴🔴**闸门自己的判据也会错**⇒写闸门前先问「真改生产代码会不会改坏」｜闸门须强制「**证据属于被检对象**」＋「**描述被检对象当前内容**」＋「**绑到包身份**」（§204/205/207）｜**精确字符串 ≠ 语义判据**（`PASS` 误杀「PASS（…）」）⇒证据带 `pkg_content`＋逐条重算。'),
    ('- 🔴🔴🔴**APP-086②「男声被配成女声」根因**',
     '- 🔴🔴🔴**APP-086②「男声被配成女声」根因**：`tts_worker.py` 的 `elif self._has_clone_voice():`→`_log_keep_last_clone()` **只改遥测不改音色**⇒收窄为 **`and not _bound`**。'),
    ('- 🔴🔴**探针/判据要能跑在旧包上**',
     '- 🔴🔴**探针/判据要能跑在旧包上**：直调新 API⇒旧包没有⇒**假 FAIL**⇒一律 `getattr` 兜底；**累计计数器不能求和**⇒取 max。'),
    ('- 🔴🔴A/B 两臂须在同一次持锁会话内连续跑',
     '- 🔴🔴A/B 两臂须在同一次持锁会话内连续跑；顺序对照 ≠ ABBA；「磁盘上存在」≠「已交付」（zip ⇄ 包目录逐字节一致才算）；zip 内有 `ACCEPTED.json`⇒先重签。'),
    ('-🔴完整版交付版 **v2.1**',
     '-🔴完整版交付版 **v2.1**（**v2.5 必须带收窄**）＋ MiniMVP 线（= **rc11**）；只打**新版本号**（新目录＋新 zip＋重签 ACCEPTED）；.lnk 版本号派生自包目录名；**旧目录/zip 不覆盖不删**。'),
    ('- 🔴🔴**出包闸门三条（§206–208）**',
     '- 🔴🔴**出包闸门三条（§206–208）**：绑了 X 却不在闸门侧重算 X→Y⇒**等于没绑**｜须**同时**绑「包身份」＋「包内容」＋接受 `PASS（…）`｜证据缺 `pkg_content`⇒**fail-closed**｜**判定先于产物落位**。'),
    ('-🔴测「功能开/关」而无独立开关',
     '-🔴测「功能开/关」而无独立开关⇒在**影子包**加**只读探针**（只加日志 + env 门控提前返回）⇒diff 落盘供 reviewer 核对；**开发树一字不改**。'),
    ('-🔴模板生成 + 占位符不动点迭代',
     '-🔴模板生成 + 占位符不动点迭代⇒自指大小须与磁盘实测一致⇒压缩后复核 ≤40 KB/≤300 行 ＋ 归档件逐字命中。'),
    ('-🟢**10 语种真跑 10/10 配音＋10/10 字幕**',
     '-🟢**10 语种真跑 10/10 配音＋10/10 字幕**（`app118_lang10_evidence.json`）｜🟢**EXT v0.4.18 冒烟 7/7**（`-m ext.bridge`＋`/health` `/status` `/pair`；**`--echo` ⇒ `--real` 未覆盖**）｜🟢**CUDA 档整链 PASS**（150==150／丢弃 0／RTF P90 0.6314）。'),
    ('-🔴**完整版出厂默认（ASR+MT+TTS 全 GPU.0）10 分钟整链 FAIL**',
     '-🔴**完整版出厂默认（ASR+MT+TTS 全 GPU.0）10 分钟整链 FAIL**（OV 集显 RTF≈4.4 ⇒ 积压 917 s）⇒ **既有局限，非 v2.5 回归**（历史整链臂全在 sp5/TTS=NPU）⇒ **等用户裁定**（改默认先问用户）。'),
    ('-🔴**「10 个带 APP-086·2a 缺陷包」',
     '-🔴**「10 个带 APP-086·2a 缺陷包」＝ AST 判分支②是否存在（不是 grep）**：grep 误报 14 个⇒v1.13／v2.0／v2.1 无分支② ＋ v1.5 无 `if spk:`⇒判据不适用。'),
    ('-🔴开工先拿租约',
     '-🔴开工先拿租约（`session_lease.py acquire <模块>`）⇒BUSY(10) 立即结束、一字不改、不碰锁；🔴**TAKEOVER⇒上会话已死⇒从断点继续**；TOKEN⇒每步 beat（>30 min ＝ 死会话）；LOST(11)⇒立即停止；收尾 `release`；🔴Git Bash 路径**必须正斜杠**。'),
    ('-🔴一条纠偏改三处',
     '-🔴一条纠偏改三处：① header `last_ack` ② 追加 `## §N` ③ 主报告＋交接单；追平后仍有未完成项⇒继续做。'),
    ('- 🔴🔴**§185 归档纪律**',
     '- 🔴🔴**§185 归档纪律**：新节触顶 40 KB⇒归档**老的整节**（逐字）＋ 活文档换**指针行**；🔴**先跑完自检再落盘**（fail-closed）；🔴复核「旧正文未变」**不按行号比**⇒用还原式复核。'),
]


def main():
    orig = open(P, encoding='utf-8').read()
    lines = orig.split('\n')
    new_lines = list(lines)
    for prefix, newline in LINES:
        hits = [i for i, l in enumerate(new_lines) if l.startswith(prefix)]
        if len(hits) != 1:
            print('ABORT: 前缀命中 %d 次 ⇒ %s' % (len(hits), prefix[:40]))
            return 1
        new_lines[hits[0]] = newline
    new = '\n'.join(new_lines)
    n = len(new)
    print('压缩：%d → %d 字符（限额 %d）' % (len(orig), n, LIMIT))
    if n > LIMIT:
        print('ABORT: 仍超限 ⇒ 源文件零改动')
        return 1
    keys = ['force push', 'os.replace', 'MACHINE_LOCK', '259 = STILL_ACTIVE',
            'session_lease.py acquire', 'last_ack', 'pkg_content',
            'EXECUTION_DEVICES', 'and not _bound', 'TtsReadyQueue', '1.70',
            'R42', 'core.autocrlf', 'write-once', '40 000 B', 'min_clean_ratio',
            '192.168.2.206', 'APP-118', 'map_language', 'v2.5', 'QQ 邮箱',
            'SKIP_NO_TTS_WORKER', 'timing_valid']
    miss = [k for k in keys if k not in new]
    if miss:
        print('ABORT: 关键条目丢失 %s ⇒ 源文件零改动' % miss)
        return 1
    print('关键条目存活：%d/%d' % (len(keys), len(keys)))

    bak = os.path.join(tempfile.gettempdir(), 'MEMORY.bak_compress2.md')
    shutil.copyfile(P, bak)
    tmp = P + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, P)
    back = open(P, encoding='utf-8').read()
    ok = (len(back) == n and all(k in back for k in keys))
    print('写后复核：%s（%d 字符／SHA %s）'
          % ('PASS' if ok else 'FAIL', len(back),
             hashlib.sha256(back.encode('utf-8')).hexdigest()[:16]))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
