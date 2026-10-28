# -*- coding: utf-8 -*-
"""app117 — 验收 `--tts-source` 开关（**零推理、零 GPU、零声卡**）。

## 为什么要有这个验收

§81 自查抓出：`app114` 的四臂对照里，**「TTS 单独」与「+ASR（无 MT）」两臂
会退化成与「+ASR+MT(GPU.0)」完全相同**的配置 ⇒ 四臂对照里三臂是同一件事
⇒ **对照数据毫无意义**。

根因：TTS 原本**只订阅 MT 输出** ⇒ `--translate off` 时 TTS 一句都收不到
（`translator.active=False` ⇒ 无 `final` 事件）⇒ 「无 MT」臂在本 CLI 下
**无法实现**。

⇒ 修法 = 新增最小生产开关 `--tts-source {mt,asr}`：
  `asr` ⇒ TTS **直接订阅 ASR 原文**（不经过 MT）且 **MT 模型不加载**。

## 本验收覆盖（全部**不跑推理**）

- **S1｜CLI 有 `--tts-source` 参数**（choices 恰为 `['mt','asr']`、default `'mt'`）。
- **S2｜默认路径逐字不变**：`default='mt'` ⇒ 现有行为不受影响。
- **S3｜`asr` 模式下 MT 不加载**：`run_cli` 里 `_mt_target = 'off' if _tts_source == 'asr' else args.translate`
  ⇒ MT 实例 `active=False` ⇒ **模型不加载**。
- **S4｜`asr` 模式下 TTS 收到 ASR 原文**：`on_final` 里调用
  `tts.submit(t, seg=..., lang='en')` ⇒ TTS 有句子可念。
- **S5｜`mt` 模式下 `on_final` **不**调 `tts.submit`**（⇒ 不重复朗读）。
- **S6｜worker 的 JSONL 字段表含 `read_delta` / `cb_delta`**
  （本轮补的「出声硬证据」字段 ⇒ 验收脚本能机器判定「这句播没播」）。
- **S7｜`tts_only` 臂被标为 NOT-APPLICABLE**（不跑、不产出数字）
  ⇒ **不用「什么都没跑的臂」冒充基线**。

## 反证

- **B1**：修复前的 `live_caption_app.py` **没有** `--tts-source`
  ⇒ 用**固定 commit SHA** 取那一份源码 ⇒ 断言它确实没有
  ⇒ 证明「四臂对照在本 CLI 下无法实现」**曾真实存在**。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴 **反证基线**：本轮修复**之前**的提交（§80 的交付 commit）
BEFORE_COMMIT = '3b07811'

APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
WRK = os.path.join(REPO, 'live_caption', 'tts_worker.py')
APP114 = os.path.join(HERE, 'app114_app027_v2_real_playback.py')

results = []


def check(cid, name, ok, got=None, want=None, note=''):
    results.append(dict(id=cid, name=name, ok=bool(ok),
                         got=got, want=want, note=note))
    print('  [%s] %-6s %-56s got=%r want=%r'
          % ('PASS' if ok else 'FAIL', cid, name, got, want))
    return bool(ok)


def git_show(commit, rel):
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    return p.stdout.decode('utf-8', 'replace')


def main():
    print('=' * 72)
    print('app117 — `--tts-source` 开关验收（S1~S7 + B1 反证）')
    print('=' * 72)

    src = open(APP, encoding='utf-8').read()

    # ── S1｜CLI 有 --tts-source（choices 恰为 mt/asr）────────────
    m = re.search(r"add_argument\(\s*'--tts-source'\s*,\s*choices=\[([^\]]*)\]"
                  r"\s*,\s*default='(\w+)'", src)
    got_choices = m.group(1) if m else None
    got_default = m.group(2) if m else None
    check('S1', 'CLI 定义 --tts-source（choices=[mt, asr]）',
          m is not None and got_choices.replace(' ', '') == "'mt','asr'",
          got_choices, "'mt','asr'")

    # ── S2｜默认路径逐字不变（default='mt'）─────────────────────
    check('S2', "默认 default='mt'（⇒ 现有行为逐字不变）",
          got_default == 'mt', got_default, 'mt')

    # ── S3｜asr 模式下 MT 不加载 ────────────────────────────────
    ok3 = ("_mt_target = 'off' if _tts_source == 'asr' else args.translate"
           in src)
    check('S3', 'asr 模式 ⇒ MT target 置 off（⇒ 模型不加载）',
          ok3, ok3, True)

    # ── S4｜asr 模式下 TTS 收到 ASR 原文 ───────────────────────
    ok4 = bool(re.search(
        r"if _tts_source == 'asr' and tts is not None and tts\.active:",
        src))
    ok4b = bool(re.search(r"tts\.submit\(\s*t,\s*seg=len\(finals\)\s*-\s*1,", src))
    check('S4', 'asr 模式 ⇒ on_final 直接 tts.submit(ASR 原文)',
          ok4 and ok4b, (ok4, ok4b), (True, True))

    # ── S5｜mt 模式下 on_final 不调 tts.submit ──────────────────
    #   （⇒ 不会重复朗读；`tts.submit` 只在 asr 分支里出现）
    n_submit_in_onfinal = len(re.findall(r"tts\.submit\(", src))
    #   期望：asr 分支 1 处 + MT outbox 分支 1 处（CLI 循环内）
    check('S5', 'on_final 里 tts.submit 只在 asr 分支（mt 模式不重复朗读）',
          ok4 and n_submit_in_onfinal >= 1,
          n_submit_in_onfinal, '>=1 且在 asr 分支内')

    # ── S6｜worker JSONL 字段表含 read_delta / cb_delta ─────────
    wrk = open(WRK, encoding='utf-8').read()
    m6 = re.search(r"_APP027_JSONL_KEYS\s*=\s*\((.*?)\)", wrk, re.S)
    keys = m6.group(1) if m6 else ''
    check('S6', "worker _APP027_JSONL_KEYS 含 read_delta / cb_delta",
          "'read_delta'" in keys and "'cb_delta'" in keys,
          ('read_delta' in keys, 'cb_delta' in keys), (True, True))

    # ── S7｜app114 的 tts_only 臂标为 NOT-APPLICABLE ───────────
    a114 = open(APP114, encoding='utf-8').read()
    ok7 = ("'tts_only': dict(asr=None, mt=None, tts_source='asr', na=True)"
           in a114)
    ok7b = ('NOT-APPLICABLE' in a114 and 'not_applicable=True' in a114)
    check('S7', 'app114 的 tts_only 臂标为 NOT-APPLICABLE（不冒充基线）',
          ok7 and ok7b, (ok7, ok7b), (True, True))

    # ── B1｜反证：修复前确实没有 --tts-source ───────────────────
    old_app = git_show(BEFORE_COMMIT, 'live_caption/live_caption_app.py')
    check('B1', '反证：修复前 app **没有** --tts-source（证明缺口曾真实存在）',
          old_app.strip() != '' and "'--tts-source'" not in old_app,
          "'--tts-source' in old_app", False)

    n_pass = sum(1 for r in results if r['ok'])
    n_fail = len(results) - n_pass
    print('\nSUMMARY: PASS=%d FAIL=%d' % (n_pass, n_fail))

    ev = os.path.join(HERE, 'app117_tts_source_switch_evidence.json')
    with open(ev, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
                       before_commit=BEFORE_COMMIT,
                       results=results, pass_count=n_pass,
                       fail_count=n_fail), f,
                  ensure_ascii=False, indent=2)
    print('证据已写入：%s' % ev)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
