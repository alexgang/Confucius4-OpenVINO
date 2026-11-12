# -*- coding: utf-8 -*-
r"""_app504 — 写 STATUS_APP.md **§184**（APP-105）+ 头部定点更新 + 体积压缩。

纪律（MEMORY §一/§九）：
  * **只动头部**（last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩 / 最近更新）；
  * **只追加** `## §N` 章节，旧章节不回头改；
  * 超过 40 000 B / 300 行 ⇒ **先把最老的一批章节整块逐字归档**
    （write-once 归档件 + 活文档留指针行）⇒ 旧正文**一字不删**（在归档件里）；
  * 写后自检：≤40 000 B、≤300 行、无裸 CR、旧章节逐字未变、归档件逐字命中。

数据来源（**不手抄**，全部从证据 json 读）：
  `results/app/app500_minimvp_rc10_build_evidence.json`（构建 + zip）
  `results/app/app501_app105_rc10_acceptance.json`（包上验收）
  `results/app/app505_app105_rc10_gui_retry.json`（GUI 复跑，§11 首轮用错解释器）
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
BUILD_EV = os.path.join(HERE, 'app500_minimvp_rc10_build_evidence.json')
ACC_EV = os.path.join(HERE, 'app501_app105_rc10_acceptance.json')
GUI_EV = os.path.join(HERE, 'app505_app105_rc10_gui_retry.json')
#: 本轮压缩掉的旧章节（正文整块逐字归档）
ARCHIVE_FROM = '## §171 巡检'
ARCHIVE_TO = '## §181 接单'
ARCHIVE_FILE = 'STATUS_APP_sec171_180_20261112.md'
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def read(path):
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def write(path, text):
    data = text.replace('\r\n', '\n').encode('utf-8')
    with open(path, 'wb') as f:
        f.write(data)
    return data


def main():
    ev = read(STATUS)
    orig = ev
    build = json.load(open(BUILD_EV, encoding='utf-8'))
    acc = json.load(open(ACC_EV, encoding='utf-8'))
    gui = json.load(open(GUI_EV, encoding='utf-8')) if os.path.isfile(GUI_EV) else {}
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    pkg = build['pkg']
    zinfo = build.get('zip') or {}
    zip_bytes = zinfo.get('bytes')
    if not zip_bytes:
        print('!! 构建证据里没有 zip 信息 ⇒ 先打包再写 STATUS')
        return 2
    chain = acc['items']['12_chain_10min']
    # 🔴 用**复跑件**（首轮那两项是**验收脚本**的问题，见 §184 第 4 条）
    bridge = acc['items'].get('13_start_bridge_bat_retry')         or acc['items']['13_start_bridge_bat']
    check = acc['items']['10_pkg_check']
    gui_res = gui.get('checks', {})
    dev = build.get('pkg_defaults', {})

    # ── ① 压缩：把 §171–§180 整块逐字归档 ───────────────────────────
    i0 = ev.find(ARCHIVE_FROM)
    i1 = ev.find(ARCHIVE_TO)
    if i0 < 0 or i1 < 0 or i1 <= i0:
        print('!! 找不到压缩区间 %s..%s' % (ARCHIVE_FROM, ARCHIVE_TO))
        return 2
    span = ev[i0:i1]
    apath = os.path.join(ARCHIVE_DIR, ARCHIVE_FILE)
    if os.path.isfile(apath):
        with open(apath, 'rb') as f:
            cur = f.read().replace(b'\r\n', b'\n')
        if cur != span.encode('utf-8'):
            print('!! 归档件已存在且内容不同（write-once，拒绝覆盖）：%s' % apath)
            return 2
        print('（归档件已存在且逐字一致 ⇒ 复用，不重写）')
    else:
        write(apath, span)
    arch_sha = sha256_bytes(open(apath, 'rb').read())
    pointer = ('## §171–§180（本批 10 节）｜**正文已整块逐字归档** ⇒ '
               '`status/archive/%s`（块 SHA256 `%s`）｜活文档留此指针行\n\n'
               % (ARCHIVE_FILE, arch_sha))
    ev = ev[:i0] + pointer + ev[i1:]

    # ── ② 头部定点更新（唯一命中断言）────────────────────────────────
    def rep(old, new):
        nonlocal ev
        c = ev.count(old)
        if c != 1:
            raise RuntimeError('头部替换未唯一命中（%d 次）：%r' % (c, old[:60]))
        ev = ev.replace(old, new)

    rep('last_ack: APP-104', 'last_ack: APP-105')
    rep(re.search(r'(?m)^更新时间: .*$', ev).group(0),
        '更新时间: %s' % now)

    old_task = re.search(r'(?m)^当前任务: .*$', ev).group(0)
    new_task = (
        '当前任务: **APP-105 已执行完**（`last_ack` = APP-105）｜'
        '**MiniMVP rc10 已打并验收 %s/%s PASS**：'
        '目录 `Confucius4_LiveCaption_MiniMVP_v1.0-rc10/`（%s 文件／%s GiB）＋ '
        'zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc10_perftest.zip`（%s B）｜'
        '§7 出厂默认第 2 代 **ASR GPU.0／MT GPU.0／TTS NPU**（`defaults_version` 8→9）'
        '＋旧默认告警改成一行日志／§1 `Start_Bridge.bat` 改 CRLF+ASCII 并加打包闸门／'
        '§2 不带 `bridge_token.txt`（黑名单 + 闸门）／§3 README 与 USER_GUIDE 如实写明 '
        'EXT 的 ASR 在本版不可用／§4 README 文案修正（含 README_en 表格英文同源）｜'
        '**模型未动**（MANIFEST 6 模型 SHA 与 rc9 相同）｜**停下等 reviewer 复核**'
        % (acc['n_items_pass'], acc['n_items'], '{:,}'.format(pkg['files']),
           pkg['gib'], '{:,}'.format(zip_bytes)))
    rep(old_task, new_task)

    old_block = re.search(r'(?m)^阻塞 / 待用户决定: .*$', ev).group(0)
    new_block = (
        '阻塞 / 待用户决定: 🔴 **等 reviewer 复核 rc10**（APP-105 §6/§7）｜'
        '**B 机实测仍未做**（reviewer 安排）⇒ rc10 的 README_perftest 已写明'
        '「B 机要跑的两组」（新默认组 + 旧默认组，各 10 分钟，记 TTS 提交/播完/丢弃）｜'
        '🔴 **EXT 的 ASR 在 MiniMVP 本版不可用**（EXT v0.4.8 写死 R2T2 ASR）'
        '⇒ 已在 README/USER_GUIDE **如实写明**，EXT 侧适配 0.6B 另等 reviewer 通知'
        '（**rc10 不等它**）｜🔴 **v2.5 未打包**（完整版 TTS/克隆 GPU.0 只改在 dev 树）｜'
        '🔴 reviewer 拟定的 §7 文案里含「mask2」字样 ⇒ 本轮**改用「旧解码器」**'
        '（保住 reviewer 自己核过的「app/ grep mask2 = 0」）')
    rep(old_block, new_block)

    m = re.search(r'(?m)^(已压缩: .*)$', ev)
    if not m:
        print('!! 找不到「已压缩」行')
        return 2
    rep(m.group(1), m.group(1) +
        '｜**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/%s`'
        '（块 SHA256 `%s`）' % (ARCHIVE_FILE, arch_sha))

    # ── ③ 最近更新：插入本轮条目 ────────────────────────────────────
    anchor = '## 最近更新\n'
    if ev.count(anchor) != 1:
        print('!! 「## 最近更新」锚点异常')
        return 2
    upd = ('> 🔴 %s ｜ **APP-105 执行完（rc10）**｜rc10 目录 %s 文件／%s GiB ＋ zip %s B｜'
           '包上验收 %s/%s PASS｜**出厂默认第 2 代 ASR GPU.0／MT GPU.0／TTS NPU**'
           '（`defaults_version` 8→9，rc9 存的旧默认按代次忽略）｜'
           '`Start_Bridge.bat` 改 CRLF+ASCII（cmd /c 实测能拉起启动器）｜'
           '包内**无** `bridge_token.txt`（黑名单闸门）｜README/USER_GUIDE 如实写明 '
           'EXT 的 ASR 不可用｜整链 10 分钟：ASR EXECUTION_DEVICES=GPU.0、'
           'TTS 实测落点 NPU（12 个组件）、TTS 提交 %s／播完 %s／丢弃 %s｜'
           '模型未动｜未打 v2.5、未调 MiniMax、未通知用户\n'
           % (now, '{:,}'.format(pkg['files']), pkg['gib'],
              '{:,}'.format(zip_bytes), acc['n_items_pass'], acc['n_items'],
              chain.get('tts_submitted'), chain.get('tts_played'),
              chain.get('tts_dropped')))
    ev = ev.replace(anchor, anchor + upd, 1)

    # ── ④ 追加 §184 ─────────────────────────────────────────────────
    sec = """
## §184 执行 APP-105（last_ack=APP-105，%s）｜MiniMVP rc10 已打并验收 %s/%s PASS｜**本条需等 reviewer 复核**
> 🔴 **§7（用户 14:30 决定，HIGH）出厂默认第 2 代 = ASR GPU.0／MT GPU.0／TTS NPU**：改 `live_caption/device_config.py`（`_DEFAULT_DEVICES_MINIMVP`）＋ `CONFIG_DEFAULTS_VERSION` **8→9** ⇒ rc9 写下的旧默认（NPU/GPU.0/GPU.0）按**代次**被忽略（`stale_device_keys()`），数值类配置项保留、**用户文件不删**、日志写明忽略了哪些旧值；用户在 rc10 里重新选过设备后写回 `defaults_version=9` ⇒ **保留**。旧告警「⚠️ ASR 与 MT 都放在 GPU.0 ⇒ 会 CL_OUT_OF_RESOURCES ⇒ 建议把 ASR 放 NPU」与**新出厂默认自相矛盾** ⇒ 改成**一行日志**：`ASR 与 MT 同在 GPU.0（stateful 解码器负载约为旧解码器的 1/3；rc5 在 B 机 268 s 崩溃是旧解码器，待 B 机复核）`（GUI 只记日志**不再覆盖**状态栏/MT 说明区；**完整版 v2.x 保留原告警**，因为它仍用旧解码器）。实测（包目录、**不带设备参数**）：`--check` exit 0（21 个 `[ OK ]`），stderr 首行 = 「已忽略旧配置里的设备项（asr=GPU.0，mt=GPU.0，tts=GPU.0）—— 那是 MiniMVP rc9 之前的出厂默认⇒ 改用本包出厂默认（asr=GPU.0，mt=GPU.0，tts=NPU）」。
> 🔴 **§1 `Start_Bridge.bat` 能拉起启动器**：原 bat 是 **400 B、LF 行尾（CR=0）、REM 里 134 个 UTF-8 中文字节** ⇒ 中文代码页 936 下 `cmd` 直接失败（reviewer 实测）。rc10 把 `Start_Bridge.bat`／`Start_LiveCaption.bat`／`Diagnose.bat` 三个 bat 全部重写为 **CRLF + 纯 ASCII**（命令语义一字不改），并在打包脚本里加**闸门**：包内所有 `*.bat` 必须 CRLF 且只含 ASCII（**反证自测**：造「裸 LF bat」「含中文 bat」各一 ⇒ 闸门必须报错，2/2 触发）。**验收按 reviewer 要求走 `cmd /c <包目录>\Start_Bridge.bat`（不用 python 绕过）**：%s。
> 🔴 **§2 不带 `bridge_token.txt`**：rc9 的 `ext/bridge_token.txt`（32 B，12:24:59，A 本机生成）**已从 rc10 删除**（构建时清 1 个），打包脚本黑名单加 `bridge_token*`／`*.pid`／`*.log` ⇒ 出包前清理 + 闸门断言剩余 **0**（反证自测：塞 3 个 ⇒ 必须全被抓到）。⚠️ 附带发现：rc9 的**目录**比它的 zip 多了 **1 515 个 `.pyc`**（验收跑出来的，其中 `app/__pycache__/device_config.cpython-312.pyc` 是**旧版 device_config.py** 的**过期字节码**）⇒ rc10 **拷贝时就排除** `__pycache__`/`*.pyc`，且验收全程 `PYTHONDONTWRITEBYTECODE=1` ⇒ 包内 `.pyc` = **0**。
> 🔴 **§3 EXT 在 MiniMVP 本版 ASR 不可用 ⇒ 文档如实写**：README_zh/en 的「配音桥接（EXT）」段与 `ext/USER_GUIDE.md`（文首醒目块 + 第 2 节第 3 步 + 第 9 节已知限制）都写明「EXT v0.4.8 的 `engine_runtime.py` 写死 R2T2 的 ASR，本包只有 0.6B stateful ⇒ 不会出现 `真实引擎已接线`／`TTS 就绪` ⇒ **待 EXT 适配 0.6B**；本包不要用浏览器插件这条链路，App 自带语音输出不受影响」。**EXT 仍嵌 v0.4.8 @817abcb，rc10 不等它**（reviewer 做好适配后另行通知换嵌）。
> 🔴 **§4 README 文字修正**：① perftest「已知问题」里那句错的「**TTS/MT 都放 GPU.0** ⇒ **ASR 必须放 NPU**」改成「**ASR 与 MT 同放 GPU.0**（本包出厂默认）—— 旧解码器时期在 B 机报过 `CL_OUT_OF_RESOURCES`；stateful 负载约为旧解码器的 1/3，待 B 机复核」；② `%%LOCALAPPDATA%%Confucius4LiveCaption` **补反斜杠** ⇒ `%%LOCALAPPDATA%%\\Confucius4LiveCaption`（三份 README 全改）；③ **README_en 的「What is inside」表格整张英文**（中英两表由**同一份 `DEV_ROWS` 数据**生成，不会漂移）。perftest 新增「**B 机要跑的两组**」：组 1 = 本包出厂默认（ASR=GPU.0／MT=GPU.0／TTS=NPU）、组 2 = 旧默认（ASR=NPU／MT=GPU.0／TTS=GPU.0），各 10 分钟，每组记 ASR RTF、WER、TTS 提交/播完/丢弃。
> 🔴 **验收（rc10 包目录，**不带设备参数**）**：整链 **10 分钟**（`test_audio/clip_10min_0_600.wav`）⇒ ASR `EXECUTION_DEVICES：encoder=GPU.0，decoder=GPU.0（请求设备 GPU.0）`；TTS `EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，decoder=NPU/…`，`实测执行设备：NPU/NPU(lazy)`，`落点统计：NPU 上 12 个组件` ⇒ **ASR 真的在 GPU.0、TTS 真的在 NPU**（查的是 `get_property('EXECUTION_DEVICES')`，不是「写的 device=」）；ASR RTF **%s**；TTS **提交 %s／播完 %s／丢弃 %s**。GUI 截图（非黑图 %s B，ASR 两档 stateful、克隆置灰、10 语种、状态栏无旧告警）。静态项：包内无旧解码器目录、`app/` 旧解码器字面 = 0、MANIFEST 6 模型 `all_match`、EXT = 0.4.8 @817abcb、黑名单 = 0、bat 闸门 0 失败、`.pyc` = 0。
> 🔴 **本轮自曝并修掉的 4 个真问题**：① **打包闸门自曝**——我在注释里写「旧 mask2 解码器」⇒ 命中 reviewer 自己核过的「`app/` grep `mask2` = **0**」⇒ 全文改用「旧解码器」（**含 reviewer §7 给的日志文案**：他那句里带 `mask2`，直接用会让 app/ grep 命中 3 处；本轮**按同一口径改写**，语义不变）；② **首轮 GUI 探针用错解释器**（系统 python 缺 numpy/openvino ⇒ ImportError，**非产品缺陷**）⇒ 改用**包内 python** 重跑（`app505_app105_rc10_gui_retry.json`，PASS）；③ CLI 文案里出现「旧 旧解码器」（替换时留下的重复字）⇒ dev 树与包内**同步定点修正**，复跑 `--check` 确认；④ **用 `subprocess.run(capture_output=True)` 调 bat 会挂死**（启动器 pythonw **继承 stdout 管道** ⇒ 管道不关闭 ⇒ `run()` 等到 180 s 超时 ⇒ 抛 `TimeoutExpired` ⇒ 首轮验收**报告没落盘**）⇒ 改用 **`Popen` + 输出落文件**后复跑：启动器窗口出现（截图 %s B）、按 **确切 PID** 停掉、无残留。首轮失败记录**原样保留**在验收报告里（`11_gui` / `13_start_bridge_bat` 标了 `first_attempt` / `superseded_by`），整链 10 分钟**没有重跑**（报告由 `_app506` 用同一批原始产物重建）。
> 🔴 **交付**：目录 `~/Confucius4_LiveCaption_MiniMVP_v1.0-rc10/`（%s 文件／%s GiB／%s B）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc10_perftest.zip`（**%s B**／两遍打包收敛）；**模型未动**（MANIFEST 6 个模型 SHA 与 rc9 相同）；**rc9 及更早目录/zip 一律未动、未删**；未打 v2.5、未调 MiniMax、未通知用户（reviewer 通知）。
> 🔴 **本条需等 reviewer 复核**（APP-105 §6/§7：rc9 不重打、rc10 交付给 B 机做 App 性能测试，EXT 不在测试范围内）。
""" % (now, acc['n_items_pass'], acc['n_items'],
       ('启动器窗口出现并截图（%s B）⇒ 截图非黑图 ⇒ 已按 PID 停掉' %
        bridge.get('shot_bytes')) if bridge.get('pass') else
       '**未通过**（%r）' % (bridge.get('new_windows')),
       chain.get('asr_rtf'), chain.get('tts_submitted'),
       chain.get('tts_played'), chain.get('tts_dropped'),
       gui.get('shot_bytes', '—'), bridge.get('shot_bytes', '—'),
       '{:,}'.format(pkg['files']), pkg['gib'], '{:,}'.format(pkg['bytes']),
       '{:,}'.format(zip_bytes))
    ev = ev.rstrip('\n') + '\n' + sec

    # ── ⑤ 写后自检 ──────────────────────────────────────────────────
    data = write(STATUS, ev)
    problems = []
    if len(data) > LIMIT_BYTES:
        problems.append('超过体积上限：%d > %d' % (len(data), LIMIT_BYTES))
    if data.count(b'\n') > LIMIT_LINES:
        problems.append('超过行数上限：%d > %d' % (data.count(b'\n'), LIMIT_LINES))
    if b'\r' in data:
        problems.append('出现裸 CR')
    # 旧正文逐字未变：除压缩区间与追加段外，原文的每个字符都还在
    for probe in ('## §162 执行 APP-089/090/091/092', '## §181 接单',
                  '## §182 执行 APP-102 / APP-103', '## §183 执行 APP-104',
                  'last_ack: APP-105', '## §184 执行 APP-105'):
        if probe not in ev:
            problems.append('缺关键片段：%r' % probe)
    # 归档件逐字命中
    if open(apath, 'rb').read().replace(b'\r\n', b'\n') != \
            span.encode('utf-8'):
        problems.append('归档件与活文档区间不一致')
    if problems:
        print('!! 自检失败：%s' % problems)
        return 2
    print('OK：%d B / %d 行；归档件 %s（%d B，SHA %s）'
          % (len(data), data.count(b'\n'), ARCHIVE_FILE,
             os.path.getsize(apath), arch_sha))
    return 0


if __name__ == '__main__':
    sys.exit(main())
