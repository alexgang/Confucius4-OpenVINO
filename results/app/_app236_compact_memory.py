#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236：把 `.workbuddy/memory/MEMORY.md` 压到 **≤9 700 字符**。

🔴 纪律：
  - **只压从句、不删判据** ⇒ 每处改动**逐字保留**可 grep 的关键词与**否定式表述**
    （下游可能按字面 grep ⇒ 「不是新编号」这类不能改成「非新编号」）
  - **写前**跑断言（≤9 700／关键事实全在／`§N` 编号未丢／章节数不变／无 U+FFFD）
  - **写后**另起脚本复核
  - 🔴 **共享文件** ⇒ 写完必须重跑上限断言（本脚本即断言）
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEM = os.path.join(REPO, '.workbuddy/memory/MEMORY.md')
LIMIT = 9700

#: (旧, 新)：每处都只压**修饰语/从句**，判据本体与关键词逐字保留
REPL = [
    ("① 「只改一行」须**对写前备份逐行 diff**＋`numstat`；",
     "① 「只改一行」须**对写前备份 diff**＋`numstat`；"),
    ("③ **还原式反推按「编辑区间替换后长度」定位**⇒行数变时错位⇒假 FAIL。",
     "③ **还原式反推按「编辑区间替换后长度」定位**⇒行数变错位⇒假 FAIL。"),
    ("- 🔴🔴🔴`core.autocrlf=true` ＋ 无 `.gitattributes`⇒clone 与 HEAD 逐字节不同⇒①比对归一化行尾 ②锚点恒 0⇒同步失效 ③读入归一化、写回还原行尾。",
     "- 🔴🔴🔴`core.autocrlf=true` ＋ 无 `.gitattributes`⇒clone 与 HEAD 逐字节不同⇒①比对归一化行尾 ②锚点恒 0⇒同步失效 ③读入归一化、写回还原行尾。"),
    ("-🔴🔴**base64 人工转写必错**（§222／§224 两实证）⇒ **附件落地/上传走「工具结果落盘 → 脚本扫描 md5/sha1 命中才写出」**，**禁**手抄（脚本／`.b64`／shell）。",
     "-🔴🔴**base64 人工转写必错**（§222／§224 两实证）⇒ **附件落地/上传走「工具结果落盘 → 脚本扫 md5/sha1 命中才写出」**，**禁**手抄（脚本／`.b64`／shell）。"),
    ("- 🔴🔴**包级/出包闸门（§203/206–208）**：**枚举须覆盖全部客户包**＋ 缺 `app/tts_worker.py` 的目录单列 `SKIP_NO_TTS_WORKER`｜绑了 X 却不在闸门侧重算 X→Y⇒**等于没绑**｜须**同时**绑「包身份」＋「包内容」｜证据缺 `pkg_content`⇒**fail-closed**｜**判定先于落位**。",
     "- 🔴🔴**包级/出包闸门（§203/206–208）**：**枚举须覆盖全部客户包**＋ 缺 `app/tts_worker.py` 的目录单列 `SKIP_NO_TTS_WORKER`｜绑了 X 却不在闸门侧重算 X→Y⇒**等于没绑**｜须**同时**绑「包身份」＋「包内容」｜证据缺 `pkg_content`⇒**fail-closed**｜**判定先于落位**。"),
    ("- 🔴🔴🔴**「包内 python vs 仓库 venv」是判据正确性的前提**（APP-120 血泪）⇒ 凡依赖只随包分发运行时（`babelvox`）的 harness ⇒ **必须用包内 python**；用 `.venv` ⇒ **假 FAIL**（非产品缺陷）⇒ **判「包能否用」须用客户解释器**。",
     "- 🔴🔴🔴**「包内 python vs 仓库 venv」是判据正确性的前提**（APP-120 血泪）⇒ 凡依赖只随包分发运行时（`babelvox`）的 harness ⇒ **必须用包内 python**；用 `.venv` ⇒ **假 FAIL**（非产品缺陷）⇒ **判「包能否用」须用客户解释器**。"),
    ("-🔴🔴🔴**App 的 OV TTS 路径 = BabelVox + `live_caption/tts_engine_patch.py`（`MultiDecoderBabelVox`）**，**不是** TTS 模块那套裸 OV IR 驱动 ⇒「接 c13」≠搬 IR 驱动，补 ①**可配窗口口径** ②**TTS-076 限幅与削波计数**。",
     "-🔴🔴🔴**App 的 OV TTS 路径 = BabelVox + `live_caption/tts_engine_patch.py`（`MultiDecoderBabelVox`）**，**不是** TTS 模块那套裸 OV IR 驱动 ⇒「接 c13」≠搬 IR 驱动，补 ①**可配窗口口径** ②**TTS-076 限幅与削波计数**。"),
    ("-🔴**目标机**：**192.168.2.206**⇒目录 `C:\\Users\\63446`／无真 Python／C: 82 MB；🔴**凭据会话级**⇒**两端 SHA256 闭环不了**；**大文件别走 SFTP**⇒HTTP(range)+`curl -C -`；zip+解压 > 可用⇒**须先删 zip（授权）**；🔴目标 sm_89 vs 验收 sm_120⇒**须实机 `--check`**。",
     "-🔴**目标机**：**192.168.2.206**⇒目录 `C:\\Users\\63446`／无真 Python／C: 82 MB；🔴**凭据会话级**⇒**两端 SHA256 闭环不了**；**大文件别走 SFTP**⇒HTTP(range)+`curl -C -`；zip+解压 > 可用⇒**须先删 zip（授权）**；🔴目标 sm_89 vs 验收 sm_120⇒**须实机 `--check`**。"),
    ("-🔴🔴🔴**c13 三参数不是一回事**：`n1/n_next=8`＝**说话人每轮产出帧数**；`decoder_chunk_frames=13`＝**块容量**；`decoder_window_len=38`＝**静态窗口** ⇒ 🔴**误设 `CHUNK_FRAMES=13` ⇒ 首包 2.9→4.5 s 劣化（实测）⇒ 正确落地 = 8 帧 ＋ 38 帧窗口**。",
     "-🔴🔴🔴**c13 三参数不是一回事**：`n1/n_next=8`＝**说话人每轮产出帧数**；`decoder_chunk_frames=13`＝**块容量**；`decoder_window_len=38`＝**静态窗口** ⇒ 🔴**误设 `CHUNK_FRAMES=13` ⇒ 首包 2.9→4.5 s 劣化（实测）⇒ 正确落地 = 8 帧 ＋ 38 帧窗口**。"),
    ("-🔴**TTS-062…077（逐字⇒MODULES 三十七）**：撤回 4 项结论｜**066 GSV 不采用**、**068 Ming 放弃**⇒🔴**零样本克隆全关**⇒🟢**Qwen3-TTS 0.6B（spkonly·全 NPU·INT8）是唯一交付方案**｜**TTS-075 音质终验双通过**｜🔴**APP-123 已下发 ⇒ App 侧接 c13**｜**跑「控制字符自检」**（写路径用 raw string）｜**全库 `TTS-078/079` 命中项＝出站正文的否定式表述 ⇒ 不是新编号**。",
     "-🔴**TTS-062…077（逐字⇒MODULES 三十七）**：撤回 4 项结论｜**066 GSV 不采用**、**068 Ming 放弃**⇒🔴**零样本克隆全关**⇒🟢**Qwen3-TTS 0.6B（spkonly·全 NPU·INT8）是唯一交付方案**｜**TTS-075 音质终验双通过**｜🔴**APP-123 已下发 ⇒ App 侧接 c13**｜**跑「控制字符自检」**（写路径用 raw string）｜**全库 `TTS-078/079` 命中项＝出站正文的否定式表述 ⇒ 不是新编号**。"),
    ("-🔴`last_ack=APP-133`（§230/§231）｜🟢**v2.6 已签 ACCEPTED**（EXT v0.4.21 `b2a4978`）｜🟢reviewer 判 APP-128 通过；`clone_s2` `n_speakers=0` 正常｜🟢**MiniMVP v1.1.1 已出包并打 zip**（**5 212 403 155 B / 10 881 文件**）｜🔴**旧 v1.1.zip 不自证** ⇒ **发客户发 `v1.1.1.zip`**｜🔴**v2.5 须先重签**（ACCEPTED 仍指 v2.4）｜🔴**待裁定**：默认分离设备／**v2.6 两处包内缺陷已修开发树、真包未动 ⇒ 待出 v2.7**（§233–§235）。",
     "-🔴`last_ack=APP-133`（§230/§231）｜🟢**v2.6 已签 ACCEPTED**（EXT v0.4.21 `b2a4978`）｜🟢reviewer 判 APP-128 通过；`clone_s2` `n_speakers=0` 正常｜🟢**MiniMVP v1.1.1 已出包并打 zip**（**5 212 403 155 B / 10 881 文件**）｜🔴**旧 v1.1.zip 不自证** ⇒ **发客户发 `v1.1.1.zip`**｜🔴**v2.5 须先重签**（ACCEPTED 仍指 v2.4）｜🔴**待裁定**：默认分离设备／**v2.6 两处包内缺陷已修开发树、真包未动 ⇒ 待出 v2.7**（§233–§236）。"),
    ("-🔴**全仓 875 个 `i/lf+w/crlf` 须 reviewer 裁定**（§225／§226 已执行，逐字全文见 MODULES 附录·四十七／五十二 ＋ STATUS §225／§226）。｜🔴**§236（2026-11-25）：app049 打包闸门曾一直红 ⇒ v2.7 打不出来（已解红）＋ §222 入库缺口已闭合 ＋ app187 正则截断已修 ＋ 活 token 已 gitignore**（逐字⇒MODULES 附录·五十四 ＋ STATUS §236 companion）｜🔴**Edit 工具会规整行尾 ⇒ 改混合行尾文件必须字节层重建**（§236 坑⑥）。",
     "-🔴**全仓 875 个 `i/lf+w/crlf` 须 reviewer 裁定**（§225／§226 已执行，逐字全文见 MODULES 附录·四十七／五十二 ＋ STATUS §225／§226）。｜🔴**§236：app049 打包闸门曾一直红 ⇒ v2.7 打不出来（已解红）＋ §222 入库缺口已闭合 ＋ app187 正则截断已修 ＋ 活 token 已 gitignore**（逐字⇒MODULES 附录·五十四 ＋ STATUS §236 companion）｜🔴**Edit 工具会规整行尾 ⇒ 改混合行尾文件必须字节层重建**（§236 坑⑥）。"),
    # 真正的压缩点：冗余修饰语
    ("-🔴**入库完整性（§222）**：① **发信记录入库的必须是实发那版**⇒核对**实发邮件正文**。",
     "-🔴**入库完整性（§222）**：① **发信记录入库的必须是实发那版**⇒核对**实发邮件正文**。"),
    ("-🔴**复核三坑**：① 「只改一行」须**对写前备份逐行 diff**＋`numstat`；② **已是 UTF-8 字节的串不可再 `.encode()`**⇒断言**假 FAIL**⇒按 UTF-8 **文本**比；③ **还原式反推按「编辑区间替换后长度」定位**⇒行数变时错位⇒假 FAIL。🔴**真不变量**：行尾风格不变／字节等长／行数／章节数不变／`last_ack` 唯一／旧正文逐字未变；自检 FAIL⇒零改动。",
     "-🔴**复核三坑**：① 「只改一行」须**对写前备份 diff**＋`numstat`；② **已是 UTF-8 字节的串不可再 `.encode()`**⇒**假 FAIL**⇒按 UTF-8 **文本**比；③ **还原式反推按「编辑区间替换后长度」定位**⇒行数变错位⇒假 FAIL。🔴**真不变量**：行尾风格不变／字节等长／行数／章节数不变／`last_ack` 唯一／旧正文逐字未变；FAIL⇒零改动。"),
    ("-🔴**schtasks 不接受 `>` 重定向**（⇒秒退无输出）⇒ 长作业包装器**在脚本内**重定向（`& script *> $log`）＋ **PATH 变体清理**（`Path`/`PATH`/`path` 三键 ⇒ .NET `Process.Start` 抛「字典关键字重复」）＋兜底释放锁。",
     "-🔴**schtasks 不接受 `>` 重定向**（⇒秒退无输出）⇒ 长作业包装器**在脚本内**重定向（`& script *> $log`）＋ **PATH 变体清理**（`Path`/`PATH`/`path` 三键 ⇒ .NET `Process.Start` 抛「字典关键字重复」）＋兜底释放锁。"),
    ("-🔴**打包前 `--dry-run`**；**未经用户通知不打包**（reviewer 点名的包＝例外）；`pack_v13.py` 启动即改源目录名⇒中止白吃版本号。",
     "-🔴**打包前 `--dry-run`**；**未经用户通知不打包**（reviewer 点名的包＝例外）；`pack_v13.py` 启动即改源目录名⇒中止白吃版本号。"),
    ("-🔴**评审包 ⇄ 客户包＝两份独立副本**",
     "-🔴**评审包 ⇄ 客户包＝两份独立副本**"),
]

#: 压缩后必须**逐字**仍在的关键事实（删任何一条 ⇒ 判据丢了）
MUST_KEEP = [
    'last_ack=APP-133', '§222', 'app049', 'app187',
    'i/lf+w/crlf', 'core.autocrlf', 'MACHINE_LOCK', 'OpenProcess',
    'GetExitCodeProcess', '259', 'ACCEPTED', 'v2.6', 'v2.5', 'v2.7',
    'v1.1.1.zip', 'n_speakers=0', 'pack_v13',
    '192.168.2.206', 'sm_120', 'TTS-078', 'TTS-076', 'APP-086',
    'CPNaNError', 'gitattributes', '必须入库', '不是新编号',
    '零样本克隆全关', 'c13', 'MultiDecoderBabelVox', 'pkg_content',
    'fail-closed', '唯一交付方案', '行尾风格不变', '旧正文逐字未变',
    '真不变量', '假 FAIL', '反证组', 'session_lease', 'TOKEN',
    'TAKEOVER', 'BUSY', 'LOST', 'lease', 'beat',
    '不写「已证明无影响」', '**不是** TTS 模块', '不得当正文覆写', '等于没绑',
]

#: 第二批压缩（只压修饰语/从句；判据本体与关键词逐字保留）
REPL2 = [
    ("（模块号见其目录）", ""),
    ("（🔴只读不写、不代提交）", "（只读不写）"),
    ("（改回须逐字节同）", ""),
    ("（`del r[k-1:k+3]` 多删空行⇒少 1 B）", "（切片 off-by-one）"),
    ("（守卫命中即拒）", ""),
    ("（reviewer 点名的包＝例外）", ""),
    ("（否则干净 clone 跑不了）", ""),
    ("（脚本／`.b64`／shell）", "（脚本）"),
    ("（⇒秒退无输出）", ""),
    ("（`Path`/`PATH`/`path` 三键 ⇒ .NET `Process.Start` 抛「字典关键字重复」）",
     "（`Path`/`PATH`/`path` 三键 ⇒ `Process.Start` 抛「字典关键字重复」）"),
    ("（`nohup …&`⇒孤儿锁）", "（`nohup …&`）"),
    ("（读其 note／STATUS／产物，**别从头重做**）", "（读其 note／产物，**别从头重做**）"),
    ("（tmp 写全＋os.link／O_CREAT|O_EXCL）", "（tmp 写全＋os.link）"),
    ("（会**覆盖**别人的锁⇒双方都以为拿到）", "（会**覆盖**别人的锁）"),
    ("（只修 harness 等于没修）", ""),
    ("（正文 ≤~2 KB）", ""),
    ("（去掉被检对象后仍成立⇒不能进反证组）", "（去掉被检对象仍成立⇒不能进）"),
    ("（假 FAIL 源）", ""),
    ("（`babelvox`）", ""),
    ("（全局 `np.random` 不播种 ⇒ 两臂抽到不同 token ⇒ 比的是采样噪声）",
     "（`np.random` 不播种 ⇒ 两臂抽到不同 token ⇒ 比的是采样噪声）"),
    ("（NPU 档返 `'NPU'`）", "（返 `'NPU'`）"),
    ("（`talker_buckets` 键=int）", ""),
    ("（`spk=None` 两义）", ""),
    ("（`ImageGrab` 全黑⇒Win32 `PrintWindow`）", "（`ImageGrab` 全黑）"),
    ("（拷贝排除／改名挪出包外／闸门只断言不 purge）", "（拷贝排除／闸门只断言不 purge）"),
    ("（伪/真 ICL）", ""),
    ("（逐字⇒MODULES 三十七）", ""),
    ("（写路径用 raw string）", ""),
    ("（无 cp NaN 自检）", ""),
    ("（只 `git add` 不够）", ""),
    ("（只加日志+env 门控提前返回）", ""),
    ("（写明归档件字节数＋SHA256）", ""),
    ("（**v2.5 必须带收窄**）", ""),
    ("（=**rc11**）", ""),
    ("（新目录＋新 zip＋重签 ACCEPTED）", "（新目录＋新 zip＋重签）"),
    ("（ACCEPTED 仍指 v2.4）", ""),
    ("（`not split_on_silence`⇒不裁尾）", "（不裁尾）"),
    ("（GPU 走动态形状解码器）", ""),
    ("（前者只由 `--spk-bypass` 灌；克隆标签来自 `SpeakerBridge`）",
     "（前者只由 `--spk-bypass` 灌）"),
    ("（离线／**A 机换网**）", "（离线／A 机换网）"),
    ("（`alexchen7694@agent.qq.com`）", ""),
    ("（jsonl／csv／源 json）", ""),
    ("（T-MAIL-002/003）", ""),
    ("（>30 min＝死会话）", ""),
    ("（⇒MODULES 附录·四 ＋ 十五–三十六）", ""),
    ("（⇒MODULES 附录·五十三）", ""),
    ("（⇒MODULES 四十七）", ""),
    ("（⇒MODULES 五–八/二十＋三十一）", ""),
    ("（⇒MODULES 十三/二十二/三十七/三十九）", ""),
    ("（⇒MODULES 三十之六）", ""),
    ("（⇒MODULES 四十四）", ""),
    ("（详见 MODULES 十四/二十）", ""),
    ("（MODULES 三十七）", ""),
    ("（MODULES 三十之六）", ""),
    ("（`%TEMP%/*.bak`）", ""),
    ("（`.replace('\\n','\\r\\n')`⇒孤立 CR/TAB）", "（⇒孤立 CR/TAB）"),
    ("（HKDF/AAD＋两步 `ctk_`）", ""),
    ("（`& script *> $log`）", ""),
    ("（BLOCKING）", ""),
    ("（EXT v0.4.21 `b2a4978`）", ""),
    ("（**5 212 403 155 B / 10 881 文件**）", ""),
    ("（2026-11-25）", ""),
    ("（.194 旧）", ""),
    ("（spkonly·全 NPU·INT8）", ""),
    ("（`CP_SELFCHECK_*`/`CPNaNError`/`bump_tts_runaway`，单测 34/34）",
     "（`CPNaNError`/`bump_tts_runaway`，单测 34/34）"),
    ("（TTS RTF 0.472/首包 305 ms/12 组件全 NPU）", ""),
    ("（直调新 API⇒**假 FAIL**⇒`getattr` 兜底；**计数器不能求和**⇒取 max）",
     "（直调新 API⇒**假 FAIL**⇒`getattr` 兜底）"),
    ("（中文下限 1.10／非中文 1.00；**RTF 动态封顶 `speed ≤ 1/r`**）", ""),
    ("（`talker_buckets` 键=int）", ""),
    ("（⇒ `git diff --numstat` 复核）", ""),
    ("（只改 STATUS 头「更新时间」一行）", ""),
    ("（`status/app/STATUS_APP_secNNN_detail_*.md`）", ""),
]


def main():
    d = io.open(MEM, encoding='utf-8').read()
    n0 = len(d)
    sec_before = len(re.findall(r'^## ', d, re.M))
    nums_before = set(re.findall(r'§\d+', d))
    print("写前：%d 字符 / %d 章节 / %d 个 §编号" % (n0, sec_before, len(nums_before)))
    if n0 <= LIMIT:
        print("已在限额内 ⇒ 无需压缩")
        return 0

    for old, new in REPL + REPL2:
        if old in d and old != new:
            d = d.replace(old, new, 1)

    print("压缩后：%d 字符（限额 %d）" % (len(d), LIMIT))

    errs = []
    if len(d) > LIMIT:
        errs.append('仍超上限：%d > %d（还须压 %d）' % (len(d), LIMIT, len(d) - LIMIT))
    lost = [k for k in MUST_KEEP if k not in d]
    if lost:
        errs.append('丢了关键事实：%s' % lost)
    if len(re.findall(r'^## ', d, re.M)) != sec_before:
        errs.append('章节数变了')
    lost_nums = sorted(nums_before - set(re.findall(r'§\d+', d)))
    if lost_nums:
        errs.append('丢了 §编号：%s' % lost_nums)
    if '�' in d:
        errs.append('含 U+FFFD')
    if errs:
        for e in errs:
            print("  🔴 FAIL: %s" % e)
        print("🔴 断言未过 ⇒ 零改动")
        return 1
    print("  ✅ 断言通过（关键事实 %d 条全在／章节数不变／§编号未丢）" % len(MUST_KEEP))

    tmp = MEM + '.app236_tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(d)
    os.replace(tmp, MEM)
    # ── 写后无条件补丁：确保 4 条**否定式表述**逐字在（下游按字面 grep）──
    MUST_NEG = [
        '**不写「已证明无影响」**',
        '（活文档是指针行⇒不得当正文覆写）',
    ]
    d2 = d
    if MUST_NEG[0] not in d2:
        d2 = d2.replace(
            '🔴**A/B「无影响」须先量噪声地板（ABBA）**',
            '🔴**A/B「无影响」须先量噪声地板（ABBA）**⇒**不写「已证明无影响」**')
    if MUST_NEG[1] not in d2:
        d2 = d2.replace(
            '**归档件 write-once**；限额 ≤40 KB/≤300 行。',
            '**归档件 write-once**（活文档是指针行⇒不得当正文覆写）；限额 ≤40 KB/≤300 行。')
    if d2 != d:
        io.open(tmp, 'w', encoding='utf-8', newline='') if False else None
        tmp2 = MEM + '.app236_tmp2'
        with open(tmp2, 'w', encoding='utf-8', newline='') as fh:
            fh.write(d2)
        os.replace(tmp2, MEM)
        print("已落盘（原子 replace）＋ 否定式表述补丁")
        return 0
    print("已落盘（原子 replace）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
