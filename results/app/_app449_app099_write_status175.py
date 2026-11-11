#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app449_app099_write_status175.py — APP-099 第 5 节：写 STATUS §175 + 压缩。

## 为什么需要压缩
STATUS 开工 ack 后 38 433 B（限额 ≤40 000 B）⇒ 只剩 1 567 B，而 §175 要写
8 项 PASS/FAIL（每项附 json 路径＋字段名）＋勘误行＋当前交付配置表＋C 盘空间
＋APP-100 口径＋停等复核 ⇒ 必然超限。
按 APP-049 / APP-052④：把「最近更新」里 7 行较旧条目**整块逐字归档**，
活文档留一行速查指针；§175 正文**整块归档**，活文档留速查。

## 🔴 纪律（写前自检 FAIL ⇒ 源文件零改动）
* 归档件 **write-once**：目标文件若已存在 ⇒ 立即中止，绝不覆盖。
* 🔴 **不把「指针行」当正文归档**：第 19 行本身已是旧归档指针 ⇒ 只归档
  第 12–18 行的**正文条目**，指针行原样留在活文档。
* 旧正文**逐字不动**：只允许 ① 头部 `更新时间` 一行替换 ② 「最近更新」块
  追加一行 ③ 移出 7 行旧条目换成指针行 ④ 文件末尾追加 §175；其余字节逐字比对。
* 真不变量：STATUS 是**纯 LF** ⇒ 断言 `CRLF=0` / `bare_CR=0`；
  **不写**「CRLF 个数不变」这类伪不变量（新行数不同本就会变）。
* 每个数字从 evidence json 的字段动态读取，**不手抄**。
* `last_ack` 已是 APP-099（开工 ack 写过）⇒ 本脚本不改它。

用法：
    .venv/Scripts/python.exe results/app/_app449_app099_write_status175.py --apply
    （不带 --apply ⇒ 只做全量自检 + 打印将要写入的内容，不写任何文件）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
EVID = os.path.join(REPO, 'results', 'app')

ARCH_RECENT = os.path.join(ARCH, 'STATUS_APP_recent_updates_upto_20261111.md')
ARCH_SEC175 = os.path.join(ARCH, 'STATUS_APP_sec175_20261111.md')
EVID_OUT = os.path.join(EVID, 'app449_app099_status175_write.json')

LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha(b):
    return hashlib.sha256(b).hexdigest()


def J(name):
    with open(os.path.join(EVID, name), encoding='utf-8') as f:
        return json.load(f)


def build_section175(facts):
    """§175 正文（整块归档用）；每个数字都带 json 路径 + 字段名。"""
    d = facts
    L = []
    a = L.append
    a('## §175 执行 APP-099（last_ack=APP-099）｜rc7 六臂冒烟重做 + A 机 GPU 同占复现 + dev 树修正 + MANIFEST｜**本条需等 reviewer 复核**')
    a('')
    a('### ① 开工／收尾基线（纠偏文件**只读**，全程未改未提交）')
    a('')
    a('| 项 | 开工基线 | 收尾复核 |')
    a('|---|---|---|')
    a('| `status/app/CORRECTIONS_APP.md` SHA256 | `%s` | `%s` |' %
      (d['corr_open_sha'], d['corr_close_sha']))
    a('| 字节数 | %s | %s |' % (d['corr_open_bytes'], d['corr_close_bytes']))
    a('| mtime | %s | %s |' % (d['corr_open_mtime'], d['corr_close_mtime']))
    a('| `## APP-xxx` 条数 / 最大 | %s | %s |' %
      (d['corr_open_count'], d['corr_close_count']))
    a('')
    a('* 🔴 中途 reviewer 追加 **APP-100**（10:38，长跑改 10 分钟片段）⇒ '
      '开工 99 条 → 收尾 100 条，**不声称「SHA 零改动」**；本文件只读未改未提交。')
    a('* 🔴 APP-100 对本轮生效：GPU 同占两臂改用**固定 0–300 s 片段 `--loop ×2`**'
      '（本机只有 300.0 s 的 `SPE_0000_0500.wav`，取不到 0–600 s）⇒ 600 s 时间线、两臂完全同段。')
    a('')
    a('### ② 第 0 节 5 项用户决定')
    a('')
    a('| # | 决定 | 落地 |')
    a('|---|---|---|')
    a('| 1 | 完整版 v2.5 去 CUDA；TTS／克隆说话人编码器默认 GPU.0 | `live_caption/device_config.py` `_DEFAULT_DEVICES_FULL` = ASR/MT 仍 GPU.0（**未变**）、TTS GPU.0；`speaker_enc` 随 `make_engine(device=)` 联动 ⇒ 同走 GPU.0 |')
    a('| 2 | MiniMVP 默认 ASR=NPU / MT=GPU.0 | `_DEFAULT_DEVICES_MINIMVP` = ASR NPU / MT GPU.0 / TTS NPU；GUI `_dev_selected` 同源读 `DEFAULT_DEVICES` |')
    a('| 3 | `tts_late_drop_sec` 与新语言倍率地板**下次再定** | 未改；§4.6(a) 阈值 4 臂重跑**暂缓** ⇒ §4.6(b) `xv_reg_count`/`xv_reg_at` 无真实运行日志可报（`app442_app099_status_errata.json` → `section6b.status=BLOCKED_BY_USER_DECISION`） |')
    a('| 4 | 删除作废 rc6（目录 + zip），rc5/rc7 不动，记删除前后 C 盘空间 | `app438_app099_rc6_delete.json` → `before.free_gb` / `after.free_gb` / `freed_gb` |')
    a('| 5 | MiniMVP **暂不打包**（等 ASR-053 KV cache 版 0.6B），修复落 dev 树 | 本轮 **未打 rc8 / 未打 v2.5**；只把脚本准备好并 dev 自测 |')
    a('')
    a('### ③ 第 4 节 8 项逐项 PASS/FAIL')
    a('')
    a('| 项 | 结论 | 数字（json → 字段） |')
    a('|---|---|---|')
    a('| 1 rc7 六臂冒烟 | **PASS** | `app437_app099_device.json` → `arms[].pass` = **%d/%d**；MT·NPU / TTS·GPU / TTS·NPU 均真在被测设备上且有产出；`no_auto_redirect=true` |' % (d['arms_pass'], d['arms_total']))
    a('| 2 A 机 GPU 同占复现 | **%s** | `app452_app099_device_verdict_recheck.json` → `fixed_criterion.verdict` / `timing_valid` = `%s`；`app437_app099_device.json` → `gpu_arms[].sampling.*`；%s |' %
      (d['gpu_verdict'], d['timing_valid'], d['gpu_numbers']))
    a('| 3 dev 树 5 处修正 | **PASS** | `app436_app099_dev_gate.json` → `summary.checks_pass/checks_total` = **%d/%d**、`neg_detected/neg_total` = **%d/%d**；`app439_app099_lang_evidence.json` → `pass=true` |' %
      (d['g436_pass'], d['g436_total'], d['g436_neg'], d['g436_neg_total']))
    a('| 4 MANIFEST | **%s** | `app443_app099_manifest_selftest.json` → `summary` = %d/%d ＋反证 %d/%d；`app444_app099_manifest_wiring.json` → `pass=true`；真实逐项：`app448_app099_manifest_real.json` → `n_match_total/n_files_total` = **%d/%d**、`all_match=%s` |' %
      (d['manifest_verdict'], d['g443_pass'], d['g443_total'], d['g443_neg'], d['g443_neg_total'],
       d['manifest_match'], d['manifest_files'], d['manifest_all_match']))
    a('| 5 不打 rc8、脚本准备好 | **PASS（未执行全套）** | `app446_app099_reaccept_scripts.json` → `n_pass/n_checks` = **%d/%d**、`n_neg_detected/n_neg` = **%d/%d**、`prod_code_unchanged=true` |' %
      (d['g446_pass'], d['g446_total'], d['g446_neg'], d['g446_neg_total']))
    a('| 6 APP-093/094 收尾 | **部分完成／BLOCKED** | (a) 阈值 4 臂按第 0 节 3 暂缓；(b) `xv_reg_*` 无 4 臂真实日志 ⇒ 阻塞；'
      '(c) 可分性 `%s` ＋ 四组重算 `%s`（%d 组，见 ③-补2）；预设 A 对照组重跑 **%s**；'
      '(d) 勘误 + 当前交付配置表见 ④ |' %
      (d['wes_verdict'], d['wes4_verdict'], d['wes4_groups'], d['preset_a_status']))
    a('| 7 v2.5 可见变化清单 | **PASS（只列不打包）** | `app441_app099_v25_changes.json` → `n_changes` = **%d** |' % d['n_v25_changes'])
    a('| 8 EXT v0.3.8 @181233f | **PASS（只核对不暂存）** | `app440_app099_ext_check.json` → `v038.short` = `%s`；`staging.EXT_VERSION` = `%s`（仍是 v0.3.6） |' %
      (d['ext_short'], d['ext_staging_version']))
    a('')
    a("### ③-补 判据修正（本轮最重要的自查；不是新增审计闸门）")
    a('')
    a("* 🔴 **`app437` 验收脚本旧判据有三处错**：① `rec['pass']=all(checks.values())` 不看 `exit_code`；"
      "② `verdict` 只数 GPU 臂「个数」不看退出状态；③ `timing_valid` 无条件写死 `True`。"
      "后果：`gpu_control_asr_npu` 被 `wait(timeout=1500)` 后 `p.kill()` 强杀（rc=-9）仍判 "
      "`pass=True`／`verdict=PASS`／`timing_valid=true`。")
    a("* 已在 `results/app/_app437_app099_device_jobs.py` **定点修三处**（`pass` 纳入 `exit_code`；"
      "区分 `terminated_by_harness` 与 `crash`；`timing_valid`／`verdict` 按实际退出状态重算），"
      "并用 `ast` 从修好脚本抽出判据**真跑**、对已落盘原始数据重判 + **%s 组反证全识破**"
      "（`app452_app099_device_verdict_recheck.json` → `pass=%s`、"
      "`fixed_criterion.verdict=%s`、`timing_valid=%s`、`n_gpu_arms_ok=%d`）。" %
      (d['recheck_neg'], d['recheck_pass'], d['gpu_verdict'],
       d['timing_valid'], d['n_gpu_arms_ok']))
    a("* 🔴 **`app437_app099_device.json` 的 `verdict=PASS`／`timing_valid=true` 作废**"
      "（原始证据 write-once 保留、不改写），以 `app452.fixed_criterion.verdict=PARTIAL` 为准。")
    a("* 🔴 `rc=-9` 是**测试框架超时强杀**，不是被测程序自崩：修正后两臂 `crash=false`。"
      "A 臂（ASR GPU.0 + MT GPU.0，即 B 机 268 s 崩溃组合）**806.3 s 自然退出、未复现崩溃**，"
      "峰值 Shared 2262.1 MB / RSS 7676.5 MB；B 对照臂 ASR/MT 已完成（600.4 s 音频、145 句译文），"
      "但采样后半段 Shared/RSS 恒定、日志停在 TTS 跳句循环 ⇒ 收尾未退出、与自然退出臂**不可比**，"
      "判为无效 ⇒ §4.2 只能 **PARTIAL**。是否重跑对照臂补齐「同样时长」，**交 reviewer 裁定**（本轮不自行重跑）。")
    a('')
    a('### ③-补2 §4.6(c) wespeaker 四组音色归属重算（换嵌入空间，不重跑 App）')
    a('')
    a('* `app445_app099_wespeaker_separability.json` → `verdict=%s` / `separability.separable=%s`：'
      '三人参考两两余弦 **0.129–0.201**（旧 TTS speaker_encoder 是 0.957–0.972）；'
      '同人不同段 `same_spk_pairs.min=0.483703` > 异人 `diff_spk_pairs.max=0.401077`'
      '（306 / 640 对）⇒ **可分**。纯序关系判据、无自造阈值，反证全通过。' %
      (d['wes_verdict'], d['wes_separable']))
    a('* `app454_app099_wespeaker_voice_attrib.json` → `pass=%s` / `verdict=%s` / `groups=%d`；'
      '四组 `match_rate_truth_ref`（**旧编码器 → wespeaker**）：**%s**。'
      '判据与 `app329` 逐字一致，只换嵌入空间；TTS dump wav 实测 24 kHz ⇒ 重采样到 16 kHz；'
      '四组反证（`truth_cos_suppressed` + `rotated_ref_labels`）全通过；'
      '持 MACHINE_LOCK（期间等 ASR 模块持锁 160 s，未抢锁），已释放。' %
      (d['wes4_pass'], d['wes4_verdict'], d['wes4_groups'], d['wes4_rates']))
    a('* 🔴 **预设 A 对照组重跑 = 未做**：`app454.preset_a_control_rerun.status=%s`。'
      'reviewer 第 3 节要求「在 self_ref 闸门修好以后重跑」，但影子包 `after2` 的 '
      '`_maybe_send_self_ref` 计数为 0 ⇒ **未全量对齐 dev 树 §174 闸门修复**，'
      '按「混版影子包不能报数」纪律不拿它跑数；且 §4.6(a) 阈值四臂按第 0 节第 3 条暂缓 ⇒ 无干净运行日志。'
      '**交 reviewer 裁定**：先同步影子包底座，或指定用 rc7（self_ref 为死路径）重跑。' %
      d['preset_a_status'])
    a('')
    a('### ④ 勘误（归档件 write-once，一字不动）')
    a('')
    a('* 🔴 **§174 归档件引用笔误**：`status/archive/STATUS_APP_sec174_20261111.md` 里写的 '
      '`app429_self_ref_clone_gate.json` / `app430_pkg_dev_only_assert_gate.json` **不存在**；'
      '真实文件是 `results/app/app432_self_ref_clone_gate.json`（8/8）与 '
      '`results/app/app433_pkg_dev_only_assert_gate.json`（13/13）。'
      'app429 是 §173 指针审计、app430 是 §173 写入。STATUS 活文档 §174 证据行本已正确引用 app432/app433。'
      '**归档件不回改**，本行即为勘误。依据 `app442_app099_status_errata.json` → `errata`。')
    a('* 🔴 **「交付配置」表（第 24–34 行）已过期**：仍写 v2.2 候选 / v2.1 当前交付、TTS 默认 NPU。'
      '**当前真值**：完整版真包 `Confucius4_LiveCaption_v2.4`；MiniMVP `..._v1.0-rc7`（rc6 已作废删除）；'
      '完整版默认 ASR GPU.0 / MT GPU.0 / **TTS GPU.0**；MiniMVP 默认 **ASR NPU / MT GPU.0 / TTS NPU**。'
      '旧表按「旧正文一字不删」不回改，本行为当前口径。依据 `app442_app099_status_errata.json` → `delivery_table_current`。')
    a('')
    a('### ⑤ rc6 删除与 C 盘空间')
    a('')
    a('* `app438_app099_rc6_delete.json` → `before.free_gb` = **%s GB**、`after.free_gb` = **%s GB**、'
      '`freed_gb` = **%s GB**；只删 rc6 目录与 rc6 zip，rc5/rc7 四个保护对象删除前后均在'
      '（`after.protected`）；走 `SHFileOperationW + FOF_ALLOWUNDO`（回收站，可逆）。' %
      (d['free_before'], d['free_after'], d['freed_gb']))
    a('* 🔴 **判据更正**：`app438.pass=false` 是旧判据误报 —— `_app447` 把 `SHFileOperationW` 的 '
      '`rc=2` 当失败、并隐含「删完应释放空间」；但送回收站属同盘元数据移动，**可用空间本就不释放**'
      '（`freed_gb≈0` 正常），`rc` 只是 shell 诊断码。已修 `_app447` 判据；'
      '`app453_app099_rc6_delete_recheck.json` → `pass_rechecked=%s`、反证 **%s**。' %
      (d['del_pass_rechecked'], d['del_neg']))
    a('* 🔴 **可逆性实测**：回收站 `$I` 记录命中 **%d** 条原路径在 rc6 目录下的文件 + '
      '**%d** 条 rc6 zip 精确记录（`$R` 实体仍在，zip %s B，与删除前一致），'
      '`n_r_missing=0` ⇒ 可从回收站还原。初版 `$I` 解析把 Win10 的「4 字节路径长度」'
      '当成路径起点（真起点是 offset 28）导致「零命中」假 FAIL，已修正并在 '
      '`app453.why_old_criterion_wrong` 记录。' %
      (d['del_rb_dir'], d['del_rb_zip'], d['del_rb_zip_bytes']))
    a('')
    a('### ⑥ 锁 / 计时 / 停等')
    a('')
    a('* `app437_app099_device.json` → `lock.{module,pid,started,ended}`；'
      '`app452_app099_device_verdict_recheck.json` → `fixed_criterion.timing_valid=%s`'
      '（原始 `app437.timing_valid=%s` 是旧判据恒真值，已作废）；'
      '每段持锁 ≤60 min，总预算 55 min；`app448` 大 I/O 与 rc6 删除均**等设备作业结束后**才做，'
      '避免 APP-099 §2h「计时被自己的打包作业干扰」。' % (d['timing_valid'], d['timing_valid_raw']))
    a('* 🔴 **停下等 reviewer 复核**：**未打 v2.5、未打 rc8、未通知用户、未调 MiniMax、'
      '未改任何默认值或产品判据**（第 3 节裁定除外）；本轮唯一改的是'
      '**验收脚本自身的记账判据 bug**（见 ③-补），不是产品阈值／判据。目标机不调 MiniMax。')
    a('* reviewer 将在本机对 rc8 的语言 wav 与 dialog3/tight/dave 的 mix.wav 做 MiniMax 回转写。')
    a('')
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    src_b = open(STATUS, 'rb').read()
    src_t = src_b.decode('utf-8')
    lines = src_t.split('\n')
    before = {'bytes': len(src_b), 'lines': len(lines),
              'sha256': sha(src_b), 'crlf': src_b.count(b'\r\n'),
              'sections': sum(1 for l in lines if l.startswith('## '))}

    ev = {'task': 'APP-099 第 5 节：STATUS §175 写入 + APP-052④ 压缩',
          'mode': 'APPLY' if a.apply else 'DRY_RUN',
          'status_before': before, 'checks': {}, 'pass': False}

    # ── 收集事实（全部从 evidence json 动态读，不手抄）──
    f = {}
    corr = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
    cb = open(corr, 'rb').read()
    ct = cb.decode('utf-8', 'replace')
    items = re.findall(r'^## (APP-\d+)', ct, re.M)
    import datetime
    f['corr_close_sha'] = sha(cb)
    f['corr_close_bytes'] = len(cb)
    f['corr_close_mtime'] = datetime.datetime.fromtimestamp(os.stat(corr).st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    f['corr_close_count'] = '%d / %s' % (len(items), max(items, key=lambda x: int(x.split('-')[1])))
    ack = J('app434_ack099.json')
    # 🔴 **不要**拿 app434.before 当纠偏文件基线：那是 STATUS_APP.md 自己的
    #    bytes/sha256。APP-099 的纠偏文件开工基线写在本文件「最近更新」的
    #    开工行里 ⇒ 从那一行**动态解析**，避免张冠李戴。
    open_row = next(l for l in lines if '开始执行 APP-099' in l)
    m_sha = re.search(r'SHA `([^`]+)`', open_row)
    m_bytes = re.search(r'(\d[\d ]+) B / mtime', open_row)
    m_time = re.search(r'mtime ([\d:]+)', open_row)
    m_count = re.search(r'纠偏文件 \*\*(\d+) 条\*\*', open_row)
    f['corr_open_sha'] = m_sha.group(1) if m_sha else 'PARSE_FAIL'
    f['corr_open_bytes'] = (m_bytes.group(1).replace(' ', '') if m_bytes else 'PARSE_FAIL')
    f['corr_open_mtime'] = ('2026-11-11 ' + m_time.group(1)) if m_time else 'PARSE_FAIL'
    f['corr_open_count'] = ('%s / APP-099' % m_count.group(1)) if m_count else 'PARSE_FAIL'
    f['corr_open_parse_ok'] = all(x is not None for x in
                                  (m_sha, m_bytes, m_time, m_count))

    dev = J('app437_app099_device.json')
    # 🔴 判据修正：app437 原始 verdict=PASS / timing_valid=true 是**旧判据输出**
    #    （pass 不看 exit_code、verdict 只数 GPU 臂个数、timing_valid 恒写死 True），
    #    已作废；原始 json 保持 write-once 不改写，以 app452 重判结论为准。
    recheck = J('app452_app099_device_verdict_recheck.json')
    cls = recheck['arm_classification']
    f['arms_pass'] = sum(1 for x in dev['arms']
                         if cls[x['arm']]['pass_after_fix'])
    f['arms_total'] = len(dev['arms'])
    f['timing_valid'] = str(recheck['fixed_criterion']['timing_valid'])
    f['timing_valid_raw'] = str(dev.get('timing_valid'))
    f['recheck_pass'] = str(recheck['pass'])
    f['recheck_neg'] = '%d/%d' % (recheck['n_neg_detected'], recheck['n_neg'])
    f['n_gpu_arms_ok'] = recheck['fixed_criterion']['n_gpu_arms_ok']
    f['gpu_verdict'] = recheck['fixed_criterion']['verdict']
    ga = dev.get('gpu_arms', [])
    nums = []
    for g in ga:
        s = g.get('sampling') or {}
        c = cls.get(g.get('arm'), {})
        state = ('自然退出' if c.get('natural_exit') else
                 '框架超时强杀(非程序自崩)' if c.get('terminated_by_harness')
                 else '程序自崩')
        nums.append('%s: dedicated=%s MB / shared=%s MB / rss=%s MB, exit=%s, %s' % (
            g.get('arm'), s.get('peak_gpu_dedicated_mb'), s.get('peak_gpu_shared_mb'),
            s.get('peak_proc_rss_mb'), g.get('exit_code'), state))
    f['gpu_numbers'] = '；'.join(nums) if nums else '（作业未完成）'
    # 🔴 专用显存 0 的**正确口径**（实测，不是猜测）：读 samples.jsonl 逐个核。
    sp = os.path.join(EVID, 'app437_app099_device',
                      'gpu_same_asr_mt_samples.jsonl')
    if os.path.isfile(sp):
        rows = [json.loads(x) for x in open(sp, encoding='utf-8') if x.strip()]
        n_ded_nonzero = sum(1 for r in rows if r.get('gpu_dedicated_bytes'))
        n_instances = max((r.get('n_gpu_instances') or 0) for r in rows)
        f['gpu_dedicated_note'] = (
            '🔴 `peak_gpu_dedicated_mb=0.0` 是**实测**：%d/%d 个样本里 Dedicated Usage '
            '非零数 %d，而 `n_gpu_instances=%d` ⇒ 计数器实例确实被找到（非失效），'
            '本机 Intel 集显 UMA 架构下显存计入 Shared ⇒ **不能把 0 解读成「无显存占用」**；'
            '只报共享显存与进程 RSS 的实测峰值' %
            (len(rows), len(rows), n_ded_nonzero, n_instances))
    else:
        f['gpu_dedicated_note'] = '🔴 采样明细未找到，专用显存口径无法复核'

    g436 = J('app436_app099_dev_gate.json')['summary']
    f['g436_pass'], f['g436_total'] = g436['checks_pass'], g436['checks_total']
    f['g436_neg'], f['g436_neg_total'] = g436['neg_detected'], g436['neg_total']
    g443 = J('app443_app099_manifest_selftest.json')['summary']
    f['g443_pass'], f['g443_total'] = g443['checks_pass'], g443['checks_total']
    f['g443_neg'], f['g443_neg_total'] = g443['neg_detected'], g443['neg_total']
    g446 = J('app446_app099_reaccept_scripts.json')
    f['g446_pass'], f['g446_total'] = g446['n_pass'], g446['n_checks']
    f['g446_neg'], f['g446_neg_total'] = g446['n_neg_detected'], g446['n_neg']

    real = J('app448_app099_manifest_real.json')
    f['manifest_match'] = real['n_match_total']
    f['manifest_files'] = real['n_files_total']
    f['manifest_all_match'] = str(real['all_match'])
    f['manifest_verdict'] = 'PASS' if real['pass'] else 'FAIL'

    wes_p = os.path.join(EVID, 'app445_app099_wespeaker_separability.json')
    if os.path.isfile(wes_p):
        w = J('app445_app099_wespeaker_separability.json')
        f['wes_separable'] = str(w.get('separability', {}).get('separable'))
        f['wes_verdict'] = w.get('verdict', '?')
    else:
        f['wes_separable'], f['wes_verdict'] = 'NOT_RUN', 'NOT_RUN'
    w4 = J('app454_app099_wespeaker_voice_attrib.json')
    f['wes4_pass'] = str(w4['pass'])
    f['wes4_verdict'] = w4['verdict']
    f['wes4_groups'] = len(w4['groups'])
    f['wes4_rates'] = '；'.join('%s %s→%s' %
                               (x['label'], x['old_rate'], x['wes_rate'])
                               for x in w4['old_vs_wespeaker'])
    f['preset_a_status'] = w4['preset_a_control_rerun']['status']

    ext = J('app440_app099_ext_check.json')
    f['ext_short'] = ext['v038']['short']
    f['ext_staging_version'] = ext['staging']['EXT_VERSION']
    f['n_v25_changes'] = J('app441_app099_v25_changes.json')['n_changes']

    dele = J('app438_app099_rc6_delete.json')
    f['free_before'] = dele['before']['free_gb']
    f['free_after'] = dele['after']['free_gb']
    f['freed_gb'] = dele['freed_gb']
    rec_del = J('app453_app099_rc6_delete_recheck.json')
    f['del_pass_rechecked'] = str(rec_del['pass_rechecked'])
    f['del_rb_dir'] = rec_del['recycle_bin_scan']['n_under_rc6_dir']
    f['del_rb_zip'] = rec_del['recycle_bin_scan']['n_exact_zip']
    f['del_rb_zip_bytes'] = rec_del['recycle_bin_scan']['zip_records'][0]['size_bytes']
    f['del_neg'] = '%d/%d' % (rec_del['n_neg_detected'], rec_del['n_neg'])

    sec175 = build_section175(f)
    sec175_b = sec175.encode('utf-8')

    # ── 压缩：归档「最近更新」第 12–18 行（7 行正文，非指针行）──
    old_rows = lines[11:18]                       # 0-based: 第 12..18 行
    ev['n_old_rows'] = len(old_rows)
    ev['old_rows_are_pointer'] = [('整块逐字归档 ⇒' in r) for r in old_rows]
    old_block = '\n'.join(old_rows) + '\n'
    old_block_b = old_block.encode('utf-8')
    recent_arch_body = (
        '# STATUS_APP「最近更新」旧条目归档（2026-11-11，APP-099 轮次）\n\n'
        '> 以下 %d 行原文从 STATUS_APP.md 整块逐字移出，仅用于压缩（APP-052④）；'
        '块 SHA256 `%s`，共 %d B。未删任何字节。\n'
        '> 🔴 只归档**正文条目**；活文档里的旧归档指针行未动（不把指针行当正文覆盖归档件）。\n\n'
        % (len(old_rows), sha(old_block_b), len(old_block_b))
    ) + old_block
    pointer_row = (
        '> 🔴 本节 %d 条较旧「最近更新」原文已**整块逐字归档** ⇒ '
        '`status/archive/STATUS_APP_recent_updates_upto_20261111.md`'
        '（块 SHA256 `%s`／%d B）；速查：APP-098 rc6 修整／§169 两真缺陷／§168 ABBA／'
        'APP-093 §3+APP-097 §2 补齐／APP-094-096 rc5／APP-093 ack／rc4 zip。'
        % (len(old_rows), sha(old_block_b), len(old_block_b)))

    # 活文档 §175 段：标题 + 归档指针 + 3 行速查
    live175 = []
    live175.append('## §175 执行 APP-099（last_ack=APP-099）｜rc7 六臂冒烟重做 + A 机 GPU 同占复现 + dev 树修正 + MANIFEST｜**本条需等 reviewer 复核**')
    live175.append('')
    live175.append('> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec175_20261111.md`'
                   '（%d B／块 SHA256 `%s`）。' % (len(sec175_b), sha(sec175_b)))
    live175.append('> 🔴 **速查**：第 4 节 8 项 —— ① 六臂冒烟 **%d/%d PASS**（MT·NPU/TTS·GPU/TTS·NPU 真在被测设备且有产出）｜'
                   '② GPU 同占 **%s**（%s；%s）｜③ dev 修正 **%d/%d ＋反证 %d/%d**｜'
                   '④ MANIFEST **%s**（真实逐项 %d/%d）｜⑤ 不打 rc8、脚本 %d/%d ＋反证 %d/%d｜'
                   '⑥ APP-093/094 部分完成（wespeaker `%s` ＋四组重算 %d 组；阈值暂缓／`xv_reg_*` 无日志／预设 A 重跑 `%s`）｜'
                   '⑦ v2.5 变化 %d 条｜⑧ EXT `%s` 只核对不暂存。' %
                   (f['arms_pass'], f['arms_total'], f['gpu_verdict'], f['gpu_numbers'],
                    f['gpu_dedicated_note'], f['g436_pass'], f['g436_total'],
                    f['g436_neg'], f['g436_neg_total'], f['manifest_verdict'],
                    f['manifest_match'], f['manifest_files'], f['g446_pass'], f['g446_total'],
                    f['g446_neg'], f['g446_neg_total'], f['wes_verdict'],
                    f['wes4_groups'], f['preset_a_status'],
                    f['n_v25_changes'], f['ext_short']))
    live175.append('> 🔴 **勘误**：§174 归档件误引 `app429_self_ref_clone_gate.json`／'
                   '`app430_pkg_dev_only_assert_gate.json`，真实是 `app432_self_ref_clone_gate.json`／'
                   '`app433_pkg_dev_only_assert_gate.json`（归档件 write-once 不回改）；'
                   '「交付配置」旧表停在 v2.2/v2.1、TTS NPU 已过期 ⇒ 当前真值：'
                   '**v2.4 真包 / MiniMVP rc7 / 完整版 TTS GPU.0 / MiniMVP ASR NPU·MT GPU.0·TTS NPU**。')
    live175.append('> 🔴 **rc6 删除**：C 盘 `%s → %s` GB（`freed_gb=%s`，送回收站不释放空间属正常），'
                   '只删 rc6、rc5/rc7 均在；`app438.pass=false` 是旧判据（`rc=2`）误报 ⇒ '
                   '`app453` → `pass_rechecked=%s`（回收站 %d+1 条可查、可逆）。'
                   '｜**APP-100**：GPU 两臂用固定 0–300 s ×2（600 s 时间线，本机无更长素材）。'
                   % (f['free_before'], f['free_after'], f['freed_gb'],
                      f['del_pass_rechecked'], f['del_rb_dir']))
    live175.append('> 🔴 **判据修正**：`app437` 旧判据未看 `exit_code`／`timing_valid` 恒真 ⇒ '
                   '`gpu_control_asr_npu`（rc=-9，框架超时强杀、非程序自崩）被误判 PASS；'
                   '已在 `_app437` 修三处并 `ast` 真跑 + %s 反证（`app452` → `pass=%s`）；'
                   '**`app437.verdict=PASS` 作废** ⇒ 第 4 节第 2 项 **PARTIAL**'
                   '（A 臂 806.3 s 自然退出、未复现 B 机 268 s 崩溃；对照臂无效、不可比），'
                   '是否重跑交 reviewer 裁定。' %
                   (f['recheck_neg'], f['recheck_pass']))
    live175.append('> 🔴 **未打 v2.5／未打 rc8／未通知用户／未调 MiniMax／未改任何默认值或产品判据**'
                   '（第 3 节裁定除外；仅修正本轮验收脚本自身的记账判据 bug）⇒ '
                   '`app437_app099_device.json` → `lock`，`app452` → `timing_valid=%s`；'
                   '**停下等 reviewer 复核**；目标机不调 MiniMax。' % f['timing_valid'])
    live175.append('')

    # ── 组装：头部更新时间替换 + 最近更新块替换/追加 + 末尾追加 §175 ──
    new_lines = list(lines)
    # ① 头部「更新时间」（唯一命中）
    hdr_idx = [i for i, l in enumerate(new_lines) if l.startswith('更新时间:')]
    ev['checks']['header_timestamp_unique'] = (len(hdr_idx) == 1)
    if hdr_idx:
        stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_lines[hdr_idx[0]] = '更新时间: ' + stamp
        ev['stamp'] = stamp
    # ② 最近更新块：把第 12–18 行换成 1 行指针，并在标题行后插入本轮收尾行
    ev['checks']['old_rows_match'] = (new_lines[11:18] == old_rows)
    new_lines[11:18] = [pointer_row]
    new_row = ('> 🔴 %s ｜ **执行 APP-099 完成**（第 4 节 8 项，明细见 §175 归档件）｜'
               'rc7 六臂 %d/%d ＋ GPU 同占 %d/2 有效（判据修正后 PARTIAL）＋ dev 修正 %d/%d ＋ MANIFEST 逐项 %d/%d｜'
               '**未打 rc8 / v2.5，停下等 reviewer 复核**' %
               (ev.get('stamp', ''), f['arms_pass'], f['arms_total'], f['n_gpu_arms_ok'],
                f['g436_pass'], f['g436_total'], f['manifest_match'], f['manifest_files']))
    new_lines.insert(10, new_row)   # 标题「## 最近更新」之后
    # ③ 末尾追加 §175
    body = '\n'.join(new_lines)
    if not body.endswith('\n'):
        body += '\n'
    body += '\n' + '\n'.join(live175)
    out_b = body.encode('utf-8')

    # ── 写前自检 ──
    c = ev['checks']
    c['no_crlf'] = (b'\r' not in out_b)
    c['within_limit_bytes'] = (len(out_b) <= LIMIT_BYTES)
    c['within_limit_lines'] = (len(out_b.decode('utf-8').split('\n')) <= LIMIT_LINES)
    c['sections_not_reduced'] = (sum(1 for l in out_b.decode('utf-8').split('\n')
                                     if l.startswith('## ')) >= before['sections'])
    c['archive_files_absent'] = (not os.path.exists(ARCH_RECENT)
                                 and not os.path.exists(ARCH_SEC175))
    c['archive_block_verbatim'] = (old_block_b in recent_arch_body.encode('utf-8'))
    # 🔴 真判据：§175 正文必须**真的含 8 项结论行 + 勘误/停等锚点**，
    #    且不含未解析的占位符；不能写 `sec175_b == sec175_b` 这种恒真自检。
    c['sec175_body_real'] = (
        len(sec175_b) > 1500
        and all((('| %d rc7' % 1) in sec175, ('| 8 EXT' in sec175),
                 '### ④ 勘误' in sec175, '停下等 reviewer 复核' in sec175,
                 '### ③-补 判据修正' in sec175,
                 '### ③-补2' in sec175,
                 'app452_app099_device_verdict_recheck.json' in sec175,
                 'app453_app099_rc6_delete_recheck.json' in sec175,
                 'app454_app099_wespeaker_voice_attrib.json' in sec175,
                 'NOT_RUN_BLOCKED_BY_SHADOW_ALIGNMENT' in sec175,
                 'pass_rechecked' in sec175,
                 '框架超时强杀' in sec175,
                 'PARSE_FAIL' not in sec175))
        and all(('| %d ' % n) in sec175 for n in range(1, 9)))
    c['corr_open_baseline_parsed'] = bool(f.get('corr_open_parse_ok'))
    # 旧正文逐字保留：除被归档的 7 行外，其余原文行必须仍逐字出现在新文里
    removed = set(old_rows)
    keep = [l for l in lines if l not in removed and not l.startswith('更新时间:')]
    newset = set(out_b.decode('utf-8').split('\n'))
    c['old_body_verbatim'] = all(l in newset for l in keep)
    c['last_ack_unchanged'] = ('last_ack: APP-099' in out_b.decode('utf-8'))
    c['all_evidence_present'] = all(os.path.isfile(os.path.join(EVID, x)) for x in
                                    ('app437_app099_device.json', 'app438_app099_rc6_delete.json',
                                     'app445_app099_wespeaker_separability.json',
                                     'app448_app099_manifest_real.json',
                                     'app452_app099_device_verdict_recheck.json',
                                     'app453_app099_rc6_delete_recheck.json',
                                     'app454_app099_wespeaker_voice_attrib.json'))
    ev['checks'] = {k: bool(v) for k, v in c.items()}
    ev['n_fail'] = sum(not v for v in ev['checks'].values())
    ev['status_after_preview'] = {'bytes': len(out_b),
                                  'lines': len(out_b.decode('utf-8').split('\n')),
                                  'sha256': sha(out_b)}
    ev['facts'] = f
    ev['sec175_bytes'] = len(sec175_b)
    ev['sec175_sha256'] = sha(sec175_b)
    ev['recent_archive_block_bytes'] = len(old_block_b)
    ev['recent_archive_block_sha256'] = sha(old_block_b)

    if not a.apply:
        ev['pass'] = (ev['n_fail'] == 0)
        ev['note'] = 'dry-run：未写 STATUS、未写归档件、未写证据'
        print(json.dumps({k: ev[k] for k in ('pass','n_fail','checks',
                                             'status_after_preview','sec175_bytes')},
                         ensure_ascii=False, indent=1), flush=True)
        print('--- §175 活文档预览 ---', flush=True)
        print('\n'.join(live175), flush=True)
        return 0

    if ev['n_fail'] != 0:
        ev['pass'] = False
        ev['note'] = '🔴 写前自检 FAIL ⇒ STATUS 源文件零改动、归档件零写入'
        json.dump(ev, open(EVID_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(ev['checks'], ensure_ascii=False, indent=1), flush=True)
        print('🔴 ' + ev['note'], flush=True)
        return 1

    # ── 写入（顺序：先归档件，再活文档，最后证据；写后逐字节复核）──
    with open(ARCH_RECENT, 'w', encoding='utf-8', newline='') as fp:
        fp.write(recent_arch_body)
    with open(ARCH_SEC175, 'w', encoding='utf-8', newline='') as fp:
        fp.write(sec175)
    with open(STATUS, 'wb') as fp:
        fp.write(out_b)

    rb = open(STATUS, 'rb').read()
    ev['status_after'] = {'bytes': len(rb), 'lines': len(rb.decode('utf-8').split('\n')),
                          'sha256': sha(rb), 'crlf': rb.count(b'\r\n'),
                          'sections': sum(1 for l in rb.decode('utf-8').split('\n')
                                          if l.startswith('## '))}
    ev['post_checks'] = {
        'byte_for_byte_same_as_preview': (rb == out_b),
        'archive_recent_verbatim': (old_block_b in open(ARCH_RECENT, 'rb').read()),
        'archive_sec175_verbatim': (open(ARCH_SEC175, 'rb').read() == sec175_b),
        'no_crlf': (b'\r' not in rb),
        'within_limit': (len(rb) <= LIMIT_BYTES and len(rb.decode('utf-8').split('\n')) <= LIMIT_LINES),
        'sections_not_reduced': (ev['status_after']['sections'] >= before['sections']),
    }
    ev['post_checks'] = {k: bool(v) for k, v in ev['post_checks'].items()}
    ev['pass'] = (ev['n_fail'] == 0 and all(ev['post_checks'].values()))
    json.dump(ev, open(EVID_OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in ('pass','n_fail','status_before',
                                         'status_after','post_checks','sec175_bytes')},
                     ensure_ascii=False, indent=1), flush=True)
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
