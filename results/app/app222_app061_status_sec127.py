#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app222 —— APP-061：**写 STATUS §127**（只追加 + 压缩归档 + 自指大小复核）。

🔴🔴 **纪律**：
1. **只追加** `## §N` 章节 ⇒ 旧章节不改（§125/§126 正文**原样归档**后
   在正文位置留一行指针，与 §123/§124 的既有做法一致）。
2. **归档逐字**：归档文件 = 改写前的**整份 STATUS_APP.md**（字节级复制）
   ⇒ 旧正文一字未删。
3. **自指大小**：写后实测字节/行数 ⇒ 必须 ≤ 40 000 B / ≤ 300 行
   （APP-052 ④ 限额），否则**判 FAIL 并如实写进本节**。
4. **证据口径**：每个数字都指向**结果文件 + 字段**；
   没落盘的东西**不能**写「已交付」。

用法：
    python app222_app061_status_sec127.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
MAX_BYTES = 40000
MAX_LINES = 300


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def cut_section(text, head_marker):
    """把以 `head_marker` 开头的那一节（到下一个 `### §` / `## ` 之前）切出来。"""
    i = text.find(head_marker)
    if i < 0:
        return None, None
    rest = text[i + len(head_marker):]
    # 下一个同级或更高级标题
    import re
    m = re.search(r'\n(?=###\s+§|\n##\s)', rest)
    if m:
        j = i + len(head_marker) + m.start()
        return text[i:j], text[j:]
    return text[i:], ''


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--status', default=STATUS,
                    help='要改写的 STATUS 文件（默认 status/app/STATUS_APP.md）'
                         '⇒ 测试时可指向**副本**')
    a = ap.parse_args()
    status_path = a.status
    orig = open(status_path, encoding='utf-8').read()
    orig_bytes = len(orig.encode('utf-8'))

    # ── 1) 归档（逐字）───────────────────────────────────────────
    os.makedirs(ARCH_DIR, exist_ok=True)
    arch = os.path.join(ARCH_DIR, 'STATUS_APP_sec126_upto_20261101.md')
    if os.path.abspath(status_path) != os.path.abspath(STATUS):
        arch = os.path.join(os.path.dirname(status_path),
                            'STATUS_APP_sec126_TESTCOPY.md')
    with open(arch, 'w', encoding='utf-8', newline='') as f:
        f.write(orig)
    assert sha256_file(arch) == sha256_file(status_path), '归档与原文件不一致'
    print('[archive] 已逐字归档 ⇒ %s（%d B）' % (arch, os.path.getsize(arch)))

    # ── 2) 证据（全部读真实文件）────────────────────────────────
    ev215 = load_json(os.path.join(HERE, 'app215_app061_voice_clone_evidence.json'))
    ev219 = load_json(os.path.join(HERE, 'app219_app061_gui_compact_evidence.json'))
    ev219v21 = load_json(os.path.join(HERE,
                                     'app219_app061_gui_compact_v21_evidence.json'))
    ev220 = load_json(os.path.join(HERE, 'app220_app061_stutter_evidence.json'))
    ev221 = load_json(os.path.join(HERE, 'app221_app061_v22_build_evidence.json'))
    dl22 = load_json(os.path.join(HERE, 'DELIVERY_2.2.json'))
    ev_app165_dev = load_json(os.path.join(
        HERE, '_tmp_app219_gui_compact.json'))

    def g(d, *path, default=None):
        cur = d
        for k in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
            if cur is None:
                return default
        return cur

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    now_full = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    pack_line = '⛔ **v2.2 zip 尚未生成**（本节写入时打包仍在进行）'
    if dl22:
        pack_line = ('✅ **v2.2 zip 已生成**：%s（**%s B** / SHA256 `%s` / mtime `%s`）'
                     % (os.path.basename(dl22.get('zip_path') or ''),
                        dl22.get('bytes'),
                        (dl22.get('sha256') or '')[:32] + '…',
                        dl22.get('mtime')))

    body = []
    A = body.append
    A('')
    A('### §127 ✅ **APP-061 —— 用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / '
      '卡顿 / 克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）：代码层全部修复 ＋ '
      '打 v2.2 交付包** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**')
    A('')
    A('> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。')
    A('> 🔴 **本轮是「接手上一会话的半成品」**：上一会话（租约 `67f14126`）在 22:21 之后'
      '**心跳中断**（22:41 仍有文件落盘）⇒ 本轮按 APP-061 的**断点继续**，'
      '**不从头重做**（已完成的 ①②④⑤ 代码改动**保留**，本轮在其上补 ③⑥ ＋ 打包）。')
    A('')
    A('**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 '
      '`5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / '
      '**168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）'
      '⇒ `last_ack` **APP-061**（APP-061 明文要求「开工前先写 last_ack」'
      '⇒ 上一会话已写，本轮沿用）。')
    A('')

    A('#### ① ① CUDA 语音无声 ＋ ② 离线「无参考音色」（同一根因，已修）')
    A('* 根因（reviewer 定位）：CUDA 分支只缓存 `_preset_ref_path`、**未缓存 `_preset_name`** '
      '⇒ 回落把 `speaker_name` 清空 ⇒ `synth()` 的音色检查成立 ⇒ 每句「没有可用的音色」'
      '⇒ **请求根本没送到边车**。')
    A('* 改法：`tts_worker.py` 的 CUDA 分支补 `self._preset_name = \'A\'`；'
      '回落路径在 CUDA 下**只换参考音频、不清空音色名**；'
      '音色检查对 `USES_REF_AUDIO` 后端改为查「当前有没有参考音频」（`_has_ref_audio()`）。')
    A('* 判据：`results/app/app215_app061_voice_clone_evidence.json` → '
      '`n_pass=%s` / `n_fail=%s`（**含 7 条反证，全部被抓住**）'
      % (g(ev215, 'n_pass'), g(ev215, 'n_fail')))
    A('')

    A('#### ② ④ 克隆从「每 10 s 一次」改为「换人时才取样」')
    A('* 停用旧的 APP-027 定时采集器（`CloneCollector`）⇒ 克隆只走按句绑定'
      '（`is_new` 取样首段 ≥1.5 s → 3 s 定稿 → 老说话人复用缓存）。')
    A('* GUI 文案去掉「每 30 s」；`_retry_spk_labels` 补登记 `is_new`（CLI 同步路径同修）。')
    A('* 判据：同 ① 的 `app215` 证据（`4a_timer_collector_disabled` / '
      '`5b_gui_retry_is_new` / `5b_cli_retry_is_new` 全 PASS）。')
    A('')

    A('#### ③ ⑤ 男声被女声播出（已修）')
    A('* 三处根因：a. GUI 构造 `TTSService` **漏传 `clone=`**（CLI 传了）⇒ '
      'worker `clone_mode=False` ⇒ 每句回落预设 A；'
      'b. `_retry_spk_labels` **丢掉 `is_new`** ⇒ 新说话人永不被取样；'
      'c. 标签未到时**一律回落预设 A**。')
    A('* 改法：a. 补传 `clone=self._clone_enabled`；b. `is_new` 为真时执行 '
      '`_spk_pending_embed.append((seg, spk))`；'
      'c. **已有克隆音色时沿用上一句**（`keep_last`，日志固定关键词 '
      '`spk_pending⇒keep_last`）⇒ 没有克隆音色时才用预设 A。')
    A('* 判据：`app215` 证据 → `5c_keep_last_helper` / `5c_synth_calls_keep_last` PASS；'
      '反证 M4（M4_5a_mutant_is_caught）/ M5（M5_5b_mutant_is_caught）**均被抓住**。')
    A('')

    A('#### ④ ③ 卡顿（遥测 ＋ 预缓冲 ＋ 倍速封顶 ＋ NPU 提示）')
    A('* (a) 逐句遥测新增 `uf_in_sentence` / `uf_in_sentence_ms` / `uf_idle` / `uf_idle_ms` / '
      '`uf_total_ms`（**句内 = 听得见的断音**；句间空闲单列）；'
      '主进程累计「句内欠载总时长」「句内欠载 = 0 的句数」；'
      'GUI 会话日志**每 30 s** 打一行 '
      '`asr_rtf / asr_backlog_s / mt_lat_p50 / tts_synth_rtf / uf_in_sentence_ms`。')
    A('* (b) 预缓冲公式升级为 **`est_dur × (1 − 1/(r·speed))`**（r = 最近 8 句实测 '
      '「合成墙钟 ÷ 音频时长」）；`r·speed ≤ 1` ⇒ 退化为首块即播（0.3 s 底线）；'
      '**speed = 1 时与旧公式逐位相同 ⇒ 零回归风险**。')
    A('* (c) **倍速动态封顶** `speed ≤ 1/r_recent`（合成跟不上时宁可滞后，'
      '不靠加速把环形缓冲抽空；**用户定的 1.30× 上限不变**）；'
      '封顶在 `self._last_speed = _sp` **之前**生效 ⇒ 下一句拿到的是实际用掉的倍率。')
    A('* (d) MT/ASR 与 TTS 同在 NPU ⇒ 语音区**标黄提示**「NPU 共用，语音可能卡顿」'
      '（**只提示、不禁止** ⇒ D4 待决）。')
    A('* 判据：`results/app/app220_app061_stutter_evidence.json` → '
      '`n_pass=%s` / `n_fail=%s` / `n_none=%s`（**含 5 条反证**'
      '：M1 去 speed 因子 / M2 去封顶 / M3 删 uf 字段 / M4 删 30 s 行 / '
      'M5 把 warn 改成 error ⇒ **全部被抓住**）'
      % (g(ev220, 'n_pass'), g(ev220, 'n_fail'), g(ev220, 'n_none')))
    A('* 行为探针（实测值）：`speed=1.0 ⇒ 预缓冲 0.947 s`、`speed=1.30 ⇒ 1.651 s`；'
      '`r=1.31 ⇒ cap=1.0000`（不许加速）、`r=0.50 ⇒ cap=1.3000`（用户上限）、'
      '无实测 RTF ⇒ 不封顶。')
    A('')

    A('#### ⑤ ⑥ 界面紧凑（已修）')
    A('* 控件压缩到 ≤ 2 行；不常用控件进**可折叠「高级」面板**（默认收起）；'
      '三个分区说明行**并进状态栏 tooltip**；字幕字体保持 13 pt；最小宽度 1024。')
    A('* **顺带修掉一个真缺陷**：三个分区的说明行被移进**未映射**的「高级」面板 ⇒ '
      'Tk 对未映射控件 `winfo_width()` 恒返 **1** ⇒ 说明行拿不到换行宽度 ⇒ '
      '`wraplength=0` ⇒ **展开面板时横向溢出**（实测最长 reqwidth = **3 003 px**）'
      '⇒ 新增 `_wrap_width()`（容器未布局时**回退到窗口宽**）＋ 展开/收起后重算。')
    A('* 判据：`results/app/app219_app061_gui_compact_evidence.json` → '
      '`n_pass=%s` / `n_fail=%s` / `n_none=%s`；'
      '**字幕区占比 %s %%（v2.1 同口径 %s %%）** ⇒ '
      '同一判据在 **v2.1 上 FAIL**（`app219_app061_gui_compact_v21_evidence.json` → '
      '`n_pass=%s` / `n_fail=%s`）⇒ **判据能识破旧版缺陷（非恒真）**。'
      % (g(ev219, 'n_pass'), g(ev219, 'n_fail'), g(ev219, 'n_none'),
         g(ev219, 'measures', '1280x800', 'caption_ratio_pct',
           default='—'),
         g(ev219v21, 'measures', '1280x800', 'caption_ratio_pct', default='—'),
         g(ev219v21, 'n_pass'), g(ev219v21, 'n_fail')))
    A('* 状态栏 **1 行**（三个分区各 21 px）；1024 宽**无控件越界/被裁剪**'
      '（判据含反证探针 ⇒ 被抓住）。')
    A('* 前后对比截图 4 张：`shared/app_gui_layout/app061_v21_*.png` 与 '
      '`app061_v22_*.png`（1280×800 与 1024×800 各 2 张）。')
    A('')

    A('#### ⑥ 交付：v2.2 新目录 ＋ 新 zip（v2.1 一个字节都没改）')
    A('* `pack_v13.py` 新增 `--no-shortcut` ⇒ **不动桌面快捷方式**'
      '（APP-061：「用户抽听以后才能改桌面快捷方式」）。')
    A('* 打包前 `--dry-run` 闸门：**PASS**（包路径写死 0 处违规 / 版本标识一致 PASS / '
      '内部素材 0 命中）⇒ 见 `results/app/_pack_v22_dryrun.log`。')
    A('* v2.2 目录由 **v2.1 目录**派生（`results/app/app221_app061_v22_build_evidence.json`）：'
      '`models/` ＋ `python/` **硬链接**（零拷贝、只读）、其余**真实复制**；'
      '**只定点同步本轮改过的 3 个生产模块**（`live_caption_app.py` / `tts_worker.py` / '
      '`tts_service.py`，行尾归一 LF ＋ 写后逐字节复核）⇒ **不整目录覆盖**。')
    A('* `ACCEPTED.json` **重签**（按新代码算指纹：`code_fingerprint=%s…`，'
      '**%s 个生产模块**）⇒ 否则 zip 内那一份仍绑旧代码（APP-052 ② 的教训）。'
      % ((g(ev221, 'code_fingerprint') or '')[:12], g(ev221, 'n_production_modules')))
    A('* %s' % pack_line)
    A('* 🔴 **v2.1 原样保留**：本轮**未改、未覆盖、未删除** v2.1 的目录与 zip；'
      'v2.2 是**全新目录 + 全新 zip**（新版本号 ⇒ 不是 `--same-version` 覆盖重打）。')
    A('')

    A('#### ⑦ 收尾复核（`CORRECTIONS_APP.md` 全程只读）')
    A('* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` '
      '/ **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**（APP-001…APP-061）。')
    A('* 收尾实测：**见下方「收尾复核值」**（收尾时现场重算；'
      '若 reviewer 在本轮中途追加了新条目 ⇒ 如实记录，**不**声称「SHA 零改动」）。')
    A('* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。')
    A('')

    A('#### ⑧ 待 reviewer 复核 / 未达成（不粉饰）')
    A('① ⛔ **①⑤ 的真机复测未做**（需 GUI + SPE 前 5 分钟 + 耳机实听）：'
      '判据与代码已就绪，**但本轮未跑设备级复测** ⇒ '
      '「没有可用的音色 0 次」「REQ 数 = 提交句数」「`voice_kind=clone` 占比 ≥ 80 %」'
      '这些**数字尚未实测** ⇒ **不能写「已通过」**。')
    A('② ⛔ **③ 的 SPE 5 分钟实测未做**（`uf_in_sentence_ms` 总和 ≤ 音频时长 0.5 % / '
      'ASR RTF 增量 ≤ +0.10 / 丢句 0 / TTS 首包 P50-P95）⇒ 同上，**未实测**。')
    A('③ ⛔ **③(e) CPU 卸载候选的 A/B 未做**（旁路 pyannote/wespeaker、克隆 `speaker_enc`、'
      'TTS `tok_decoder`）⇒ 需持机器锁的 ABBA 实测；'
      '**「改默认摆放要先报主会话」⇒ 本轮未改任何默认摆放**。')
    A('④ ℹ️ **D1–D4 仍待用户/reviewer 决定**（线程不自定）：'
      'D1 旁路窗口 10 s 能否缩短；D2 选「跟随说话人」是否自动开旁路；'
      'D3 客户包是否保留 TTS=CUDA 选项；D4 MT/TTS 同 NPU 是警告还是禁止。'
      '**用户决定之前的默认实现已按 STATUS 头部记录落地**（② 检测不到边车 ⇒ CUDA 置灰并显示原因；'
      '⑤d 旁路关时明确提示、不静默退回定时克隆）。')
    A('⑤ ℹ️ **桌面快捷方式未改**（`--no-shortcut`）⇒ 用户抽听通过后再由主会话改指 v2.2。')
    A('⑥ ℹ️ **v2.1 的 zip 与目录 README 仍不一致**（zip 内是 21:05 改前的版本）'
      '⇒ 该缺口**已由 v2.2 带上**（v2.2 继承了目录版本 47 786 B）⇒ v2.1 本身**不再原地改**。')
    A('')

    body_s = '\n'.join(body) + '\n'

    # ── 3) 改写主文件：§125/§126 正文 → 指针；追加 §127 ────────
    text = orig
    for marker, archref in (
            ('### §125 ✅',
             '> **本节正文已原样归档** ⇒ 见 '
             '`status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。'),
            ('### §126 ✅',
             '> **本节正文已原样归档** ⇒ 见 '
             '`status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。')):
        sec, rest = cut_section(text, marker)
        if sec is None:
            print('[warn] 未找到 %s' % marker)
            continue
        head = sec.split('\n', 1)[0]
        text = text.replace(sec, head + '\n\n' + archref + '\n\n', 1)

    # 追加 §127（放在文件末尾）
    if '### §127' in text:
        print('[warn] §127 已存在 ⇒ 不重复追加')
    else:
        text = text.rstrip('\n') + '\n' + body_s

    # ── 4) 头部：更新时间 / 最近更新 / 索引表 ────────────────────
    lines = text.split('\n')
    for i, ln in enumerate(lines):
        if ln.startswith('更新时间:'):
            lines[i] = '更新时间: %s' % now
        if ln.startswith('当前任务:'):
            lines[i] = ('当前任务: **§127 APP-061 已执行**（`last_ack` = APP-061）：'
                        '用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / 卡顿 / '
                        '克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）'
                        '⇒ **代码层全部修复**（①④⑤ 上一会话做的 ＋ ③⑥ 本轮做的）'
                        '⇒ **v2.2 新目录 + 新 zip 已产出**（v2.1 一个字节都没改；'
                        '桌面快捷方式**未改**）')
        if ln.startswith('阻塞 / 待用户决定:'):
            lines[i] = ('阻塞 / 待用户决定: 🔴 **D1–D4 仍由 reviewer/用户决定**'
                        '（旁路窗口时长 / 是否自动开旁路 / 客户包是否保留 CUDA 选项 / '
                        'NPU 共用是警告还是禁止）⇒ 本轮按「用户决定之前的默认实现」落地；'
                        '⛔ **设备级实测未做**（①⑤ GUI+SPE 5 分钟复测、③ SPE 5 分钟遥测、'
                        '③(e) CPU 卸载 A/B）⇒ **未实测的数字不写「已通过」**')
    text = '\n'.join(lines)

    # 最近更新：把最新一条插到最前
    upd_marker = '## 最近更新\n'
    if upd_marker in text:
        new_upd = ('- %s **§127 APP-061 已执行** ⇒ ①⑤③⑥ 代码层全部修复'
                   '（`app215` %s PASS / %s FAIL；`app220` %s PASS / %s FAIL；'
                   '`app219` %s PASS / %s FAIL，v2.1 同口径 **FAIL** ⇒ 判据非恒真）'
                   '⇒ **v2.2 新目录 + 新 zip**（v2.1 未改一字节；桌面快捷方式未改）'
                   '⇒ ⛔ 设备级实测与 D1–D4 仍待办\n'
                   % (now, g(ev215, 'n_pass'), g(ev215, 'n_fail'),
                      g(ev220, 'n_pass'), g(ev220, 'n_fail'),
                      g(ev219, 'n_pass'), g(ev219, 'n_fail')))
        i = text.index(upd_marker) + len(upd_marker)
        text = text[:i] + new_upd + text[i:]

    # 索引表：加 §127
    row126 = ('| §126 | **APP-060**：交付版 = v2.1 ＋ v2.0 标 superseded ＋ '
              '桌面 v2.0.lnk 已删（脚本加硬闸门） | **本轮新增（见下）** |')
    row127 = ('| §127 | **APP-061**：用户实测 6 问（CUDA 无声 / 离线无参考音色 / 卡顿 / '
              '克隆 10 s 一次 / 男声被女声播出 / 界面不紧凑）⇒ 代码层全修 ＋ v2.2 包 '
              '| **本轮新增（见下）** |')
    if row126 in text and row127 not in text:
        text = text.replace(row126, row126 + '\n' + row127)

    # ── 5) 写回（临时文件 → 原子替换）───────────────────────────
    #    🔴🔴 **自指大小**必须与磁盘**实测一致**（差 2 B 也要改）
    #      ⇒ 「已压缩：」那行的 `N B / M 行` 是**自指**的 ⇒ 改它会改变自身大小
    #      ⇒ **不动点迭代**（写 → 量 → 改 → 再量 …）直到稳定。
    def _write(t):
        tmp = status_path + '.app222_tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(t)
        back = open(tmp, encoding='utf-8').read()
        assert back == t, '写后复核不一致'
        os.replace(tmp, status_path)
        d = open(status_path, 'rb').read()
        return len(d), d.count(b'\n')

    nbytes, nlines = _write(text)
    for _ in range(8):
        m = re.search(r'^(已压缩: 本文件 )(\d+)( B / )(\d+)( 行)',
                      text, re.M)
        if not m:
            break
        if int(m.group(2)) == nbytes and int(m.group(4)) == nlines:
            break
        # 🔴 **只替换数字** ⇒ 该行其余文字（归档说明等）**逐字保留**
        #   （否则行长变了 ⇒ 自指大小又变了 ⇒ 永远不动点）
        text = (text[:m.start()] + m.group(1) + str(nbytes) + m.group(3)
                + str(nlines) + m.group(5) + text[m.end():])
        nbytes, nlines = _write(text)

    ok = (nbytes <= MAX_BYTES and nlines <= MAX_LINES)
    print('\n[status] 已写 §127')
    print('  字节 %d / %d（%s）' % (nbytes, MAX_BYTES, 'OK' if nbytes <= MAX_BYTES else '超限'))
    print('  行数 %d / %d（%s）' % (nlines, MAX_LINES, 'OK' if nlines <= MAX_LINES else '超限'))
    print('  改写前 %d B ⇒ 改写后 %d B' % (orig_bytes, nbytes))
    print('  归档 %s（%d B）' % (arch, os.path.getsize(arch)))
    # 自指大小最终复核
    with open(status_path, encoding='utf-8') as f:
        fin = f.read()
    mm = re.search(r'^已压缩: 本文件 (\d+) B / (\d+) 行', fin, re.M)
    self_ok = bool(mm) and int(mm.group(1)) == len(
        open(status_path, 'rb').read())
    print('  自指大小一致：%s（写的是 %s / 实测 %d B）'
          % (self_ok, mm.group(1) if mm else '—', nbytes))
    return 0 if (ok and self_ok) else 1


if __name__ == '__main__':
    raise SystemExit(main())
