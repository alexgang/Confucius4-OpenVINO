# -*- coding: utf-8 -*-
r"""_app489 — 写 STATUS §182（APP-102/103 执行完），含写前/写后自检。

纪律：只改头部 4 行 + 交付配置表 3 行（APP-101 §1.b 允许「当前有效结论」改写），
在「最近更新」插入 1 条，末尾追加 §182（≤3 行速查）；§141–§181 章节正文**逐字不动**，
旧结论错在新章节写「撤回 §181」。写前自检 FAIL ⇒ 源文件零改动。
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
REPORT = os.path.join(HERE, 'app489_app103_write_status182.json')
TS = '2026-11-12 10:44:44'      # PowerShell Get-Date 实测

HEAD_AFTER = {
    'last_ack: ': (
        'last_ack: APP-102'),
    '更新时间: ': (
        '更新时间: ' + TS),
    '当前任务: ': (
        '当前任务: **APP-102 已执行完**（APP-103 裁定：本会话持锁做完、`last_ack` 写 APP-102）｜'
        '**MiniMVP rc8 已打并验收 6/6 PASS**：目录 `Confucius4_LiveCaption_MiniMVP_v1.0-rc8/`'
        '（10 541 文件／5.515 GiB）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc8_perftest.zip`'
        '（5 924 663 034 B／10:40）｜stateful 后端接入、4 臂短冒烟 4/4、10 语种 MT/TTS 30/30、包上 6 项全 PASS｜'
        '**停下等 reviewer 复核**（B 机实测由 reviewer 安排）'),
    '阻塞 / 待用户决定: ': (
        '阻塞 / 待用户决定: 🔴 **等 reviewer 复核 rc8**（APP-102 §5）｜**rc8 后补**（APP-102 §4）：'
        'APP-101 §4.4 的 10 分钟片段 4 臂配对 WER/RTF ＋ 整链一臂、§1/§2 小修正、预设 A 对照组'
        '（dev 树 dialog3 一臂）；计时 json 本轮已带锁 `ended`／`timing_valid`｜'
        '🔴 本机 `AppData\\Local\\Confucius4LiveCaption\\device_config.json` 存有历史 `tts=NPU` 会覆盖出厂默认，'
        '客户机干净环境无此文件 ⇒ rc8 整链冒烟显式给 `--tts-device GPU.0` 还原新默认，'
        '出厂 `DEFAULT_DEVICES` 实测 `NPU/GPU.0/GPU.0`｜🔴 **v2.5 未打包**，完整版 TTS/克隆 GPU.0 只改在 dev 树'),
}

TABLE_AFTER = {
    '| 语音输出设备 |': (
        '| 语音输出设备 | 🔴 **APP-101 §0.3 / APP-102 §0（用户 11-12 决定）**：完整版 TTS 与克隆'
        '（说话人编码器／x-vector）→ **GPU.0**；MiniMVP TTS → **GPU.0**（克隆置灰）｜'
        '**MiniMVP rc8 已进包**（出厂默认实测 `NPU/GPU.0/GPU.0`）；**完整版 v2.5 未打包** | '
        '`live_caption/device_config.py:69-74`；`app486_app102_rc8_smoke.json` → '
        '`factory_default_probe.default_devices`；`app488_app102_rc8_acceptance.json` |'),
    '| MiniMVP 默认设备（新） |': (
        '| MiniMVP 默认设备（新） | ASR **NPU** / MT **GPU.0** / TTS **GPU.0**；'
        '`device_config.DEFAULT_DEVICES` 为唯一事实来源，GUI `_dev_selected` 与 CLI `get_devices()` 同源'
        '（无第二份字面量）｜**rc8 包内实测** `NPU/GPU.0/GPU.0` | `live_caption/device_config.py:69-74`；'
        '`_DEFAULT_DEVICES_FULL` 三档仍全 GPU.0；`app486_app102_rc8_smoke.json` → '
        '`factory_default_probe` |'),
    '| 磁盘最新 MiniMVP 包 |': (
        '| 磁盘最新 MiniMVP 包 | 🔴 **rc8 已打**：`Confucius4_LiveCaption_MiniMVP_v1.0-rc8/`'
        '（10 541 文件／5.515 GiB）＋ `~/shared/minimvp/…rc8_perftest.zip`（5 924 663 034 B／10:40）；'
        '**包上验收 6/6 PASS**；rc7 及更早目录/zip 全部保留未删；rc6 已按 APP-099 移入回收站（可逆） | '
        '`results/app/app484_minimvp_rc8_build_evidence.json`；'
        '`app488_app102_rc8_acceptance.json` → `verdict=PASS` / `zip_check.counts_equal=true` |'),
}

NEW_UPDATE = (
    '> 🔴 2026-11-12 10:44:44 ｜ **APP-102 执行完（APP-103 裁定本会话做完）**｜'
    'MiniMVP **rc8** 目录（10 541 文件／5.515 GiB）＋ zip `~/shared/minimvp/'
    'Confucius4_LiveCaption_MiniMVP_v1.0-rc8_perftest.zip`（**5 924 663 034 B**／10:40）｜'
    '**包上验收 6/6 PASS**（`app488_app102_rc8_acceptance.json`）：无旧解码器目录／`app/` grep `mask2`=0／'
    'MANIFEST decoder `0059531a…d6a3`＋encoder `0b7463d6…` 与源一致／EXT 0.4.8 @`817abcb`／'
    '包内 python `--check` exit=0（21 个 OK 行）／包目录整链 exit=0、ASR RTF **0.544**、播完 **2** 句｜'
    '**4 臂短冒烟 4/4 PASS**（`app486_app102_rc8_smoke.json`）：stateful GPU.0 **0.397**／NPU **0.538**'
    '（`EXECUTION_DEVICES` encoder+decoder 均 NPU）／新默认整链 **0.573**／GUI 截图 42 549 B 非空白、'
    'ASR 两档 stateful、克隆置灰、10 语种｜**10 语种 MT 30/30 ＋ TTS 30/30**（30 个 wav 落盘、'
    '撞上限 0 次、`_patch_app_langs` 新增键 **0**，`app487_app102_10lang_smoke.json`）｜'
    '**停下等 reviewer 复核**；未打 v2.5、未调 MiniMax、未通知用户')

SEC182 = (
    '## §182 执行 APP-102 / APP-103（2026-11-12 10:44:44）｜rc8 已打并验收 6/6 PASS；'
    '撤回 §181 的「未做／等裁定」结论\n'
    '> 🔴 **已做**（证据 `app484…json` / `app486…json` / `app487…json` / `app488…json`）：'
    'stateful 后端照 B-kit `bk_run.py`（NPUW_LLM、每次 generate 新建 InferRequest＋`reset_state`、'
    'eos/pad 用导出 id、512 上界截最旧前缀且实测截断 0 次）；旧无 KV 基线只在 dev 树，'
    '包内旧目录/字面 0（打包闸门反例自测 2/2 能识破）；rc8 目录＋zip 落盘，验收 6/6、'
    '4 臂短冒烟 4/4、10 语种 30/30，`last_ack=APP-102`（APP-103 裁定）。\n'
    '> 🔴 **rc8 后补**（APP-102 §4）：10 分钟片段 4 臂配对 WER/RTF ＋ 整链一臂、预设 A 对照组、'
    '交付配置表细项；计时 json 已带锁 `ended` 与 `timing_valid`（`app486/487/488`）。'
    '**做完即停，等 reviewer 复核**（B 机实测由 reviewer 安排）；v2.5 未打、未调 MiniMax。\n')


def main():
    raw = open(STATUS, 'rb').read()
    t = raw.decode('utf-8')
    ev = {'at': TS, 'checks': [], 'before': {
        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
        'lines': len(t.splitlines())}}
    old_sections = t[t.index('## §141'):]

    def chk(name, ok, detail=''):
        ev['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})
        return bool(ok)

    # ── 写前自检 ──
    good = True
    for prefix in list(HEAD_AFTER) + list(TABLE_AFTER):
        lines = [x for x in t.splitlines() if x.startswith(prefix)]
        good &= chk('anchor_unique:' + prefix, len(lines) == 1,
                    'hits=%d' % len(lines))
    good &= chk('recent_update_anchor', t.count('\n## 最近更新\n') == 1)
    good &= chk('no_sec182_yet', '## §182' not in t)
    good &= chk('size_before', len(raw) <= 40000 and len(t.splitlines()) <= 300,
                '%d B / %d lines' % (len(raw), len(t.splitlines())))
    good &= chk('no_bare_CR', b'\r' not in raw)
    n_sec_before = len(re.findall(r'^## §\d+', t, re.M))
    if not good:
        print('!! 写前自检 FAIL ⇒ 源文件零改动')
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 2

    # ── 应用：头部 4 行 + 表格 3 行（整行替换） ──
    lines = t.splitlines(keepends=False)
    repl = dict(HEAD_AFTER)
    repl.update(TABLE_AFTER)
    n_repl = 0
    for i, ln in enumerate(lines):
        for prefix, new in repl.items():
            if ln.startswith(prefix):
                lines[i] = new
                n_repl += 1
                break
    good &= chk('n_replaced', n_repl == 7, 'n=%d' % n_repl)
    nt = '\n'.join(lines) + '\n'

    # 最近更新：在 '## 最近更新' 后插入 1 条
    anchor = '\n## 最近更新\n'
    nt = nt.replace(anchor, anchor + NEW_UPDATE + '\n', 1)
    # 追加 §182（末尾）
    if not nt.endswith('\n'):
        nt += '\n'
    nt += '\n' + SEC182

    # ── 写后自检 ──
    data = nt.encode('utf-8')
    n_sec_after = len(re.findall(r'^## §\d+', nt, re.M))
    good &= chk('sections_not_lost', n_sec_after == n_sec_before + 1,
                '%d -> %d' % (n_sec_before, n_sec_after))
    good &= chk('old_sections_verbatim', nt[nt.index('## §141'):].startswith(old_sections.rstrip('\n')))
    good &= chk('head_last_ack', '\nlast_ack: APP-102\n' in nt)
    good &= chk('head_timestamp', ('\n更新时间: ' + TS + '\n') in nt)
    good &= chk('size_after', len(data) <= 40000 and len(nt.splitlines()) <= 300,
                '%d B / %d lines' % (len(data), len(nt.splitlines())))
    good &= chk('no_bare_CR_after', b'\r' not in data)
    good &= chk('sec182_three_lines', len(SEC182.rstrip('\n').splitlines()) == 3)
    if not good:
        print('!! 写后自检 FAIL ⇒ 源文件零改动')
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 2

    with open(STATUS, 'wb') as f:
        f.write(data)
    again = open(STATUS, 'rb').read()
    good &= chk('byte_verify_after_write', again == data)
    ev['after'] = {'sha256': hashlib.sha256(again).hexdigest(),
                   'bytes': len(again), 'lines': len(again.decode('utf-8').splitlines())}
    ev['verdict'] = 'PASS' if good else 'FAIL'
    json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('写前 %d 项 / 写后 %d 项自检：%s' %
          (sum(1 for c in ev['checks'][:9] if c['ok']),
           sum(1 for c in ev['checks'][9:] if c['ok']), ev['verdict']))
    print('STATUS %d B / %d 行 → %d B / %d 行' %
          (ev['before']['bytes'], ev['before']['lines'],
           ev['after']['bytes'], ev['after']['lines']))
    return 0 if good else 2


if __name__ == '__main__':
    sys.exit(main())
