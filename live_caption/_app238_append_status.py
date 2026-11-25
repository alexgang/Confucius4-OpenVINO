#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app238_append_status.py — **§238 追加进 `STATUS_APP.md`**（字节层重建）。

## 本轮做两件事

1. **追加** `## §238`（含指针行）—— 只在**文末**追加；
2. 🔴 **修掉 APP-134 问题⑦ 的过时结论**：
   > 活文档「当前有效结论」里那句「出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL
   > ⇒ 等用户裁定默认摆放」已经过时（v2.6 的 `_DEFAULT_DEVICES_FULL` 是 GPU.0/GPU.0/NPU），
   > **删掉或者注明是哪一版、哪次测的**。

   ⇒ 本脚本**不删整句**（那是旧正文），而是**就地标注**：
   把 `🔴 **出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL**（OV 集显追不上）⇒ **等用户裁定**默认摆放`
   改成
   `🔴 **【§238 已更正】**「出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL」**这句已过时**：
   v2.6 的 `_DEFAULT_DEVICES_FULL` 实为 **GPU.0/GPU.0/NPU**（不是全 GPU.0）⇒ 该 FAIL 结论**不适用 v2.6**；
   **v2.6 的真实排空口径见 §238 §1.2–§1.5**（TTS=NPU 臂 收尾积压 292.77 s／AUTO 臂 4.01 s）`

   🔴 **「当前有效结论」是活文档**（不是归档章节）⇒ 在这里就地标注是合规的；
   **归档章节（§N 正文）一字不动**。

## 🔴 真不变量（写前先在**内存新文本**上跑，全 PASS 才落盘）

1. **旧正文逐字未变**（除下面两处**白名单定点替换**外）；
2. **行尾风格不变**（CRLF 计数不变）；
3. **行数变化 == 预期**（追加 2 行 ＋ 定点替换不换行）；
4. **章节数 +1**；
5. **头部 `last_ack` 与「更新时间」被替换**（且**只有这两行**变）；
6. **`last_ack` 唯一**；
7. 落盘用 **临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app238_append_status.py --apply
```
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BACKUP = STATUS + '.bak_app238_sec238'
RESULT = os.path.join(REPO, 'results', 'app', 'app238_status_verify.json')

#: 追加块（**§238 索引行 + 指针行**）
BLOCK = (
    "## §238 执行 **APP-137**（last_ack=APP-136 → **APP-137**）＋ **APP-134 a** ＋ **APP-135 §1–§3**｜🟢 **APP-134 a 两臂全 PASS**（rc=0／`lock_lost` **0**）：**TTS=NPU 臂**媒体结束 `n_pending`=**49**（40.5%）⇒ 排空 **292.77 s** ⇒ 滞后末值 **279.12 s**／斜率 **−0.534 s/s**（r²=0.943，**线性不回落**）／`synth_rtf`=**1.2792**；**AUTO 臂**（＝ `Start_Bridge` 实际配置）`n_pending`=**1**（0.8%）⇒ 排空 **4.01 s** ⇒ 滞后 **0.0 s**／斜率 −0.0015／`synth_rtf`=**0.5907**｜🔴 **口径更正**：「丢句 0／收尾积压 0」**不成立**（正确表述：**不是丢句，是迟到**；排空后 `n_pending` **确实归 0**、`dubs`=123＝`n_emitted`、`dup_dropped`=0）｜🔴 **APP-134 问题② 实证**：AUTO 档实测 **MT=NPU ＋ TTS=CUDA 边车**（RTX 5050，端到端启动 45.3 s）⇒ **与 App 出厂默认 GPU.0/GPU.0/NPU 不是同一档**｜🟢 **APP-137 §1 dev 树 profile 改造**（MiniMVP v1.2：并入 EXT 全部功能＋音色克隆／**c13 不进 MiniMVP**）**行为级 18/18 PASS**（含 2 组反证组）｜🟢 **§2 候选目录已建**（**10 891 文件 / 6.360 GiB**，**不打 zip、不签 ACCEPTED**）｜🟢 **§3 包内容核对 22/22 PASS**（模型权重 SHA 逐文件对源／克隆音色目录**只有 `preset_A.wav`**／**媒体文件违规 0 个**／**无 CUDA DLL**／profile 语义正确）｜🟢 **APP-135 §1–§3**：dev 树 MT2→**MT3**（**`LIVECAP_MT_VARIANT=mt2` 可切回**，默认 mt3；INT4 档仍指 MT2——**仓库无 MT3 的 INT4 产物**）＋ 🔴 **实测确认 `LLMPipeline.get_generation_config()` 确实吃到模型默认值**（`do_sample=true`/0.7/20/0.8）⇒ **逐项显式覆盖**（贪心 + `temperature`/`top_k`/`top_p` 中性值）＋ **单测真跑 ALL PASS**（含反证组 FAIL）｜🔴 **未完成**：APP-137 §3 后半（A 上三轮＋缺模型降级）、APP-134 b/c、APP-135 §4–§5｜🟢 **未打包 zip**／未改任何客户包／未调 MiniMax／未连 B 机｜🟢 **未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜**本条需等 reviewer 复核**\n"
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec238_detail_20261125.md`**（含 §0 本轮顺序与暂停事件、§1 APP-134 a 两臂完整数据＋**口径更正**＋**问题② 实证**＋给用户裁定的数据、§2 APP-137 §1–§3、§3 APP-135 §1–§3（含 GenAI 默认值实测）、§4 本轮新学的 3 个判据坑、§5 未完成/待裁定 6 项、§6 纪律自查、§7 下一轮）\n"
)

#: 🔴 **定点替换**（白名单；每处必须**唯一命中**）
FIXES = [
    (
        'app134_outdated_default_fail',
        '🔴 **出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL**（OV 集显追不上）⇒ **等用户裁定**默认摆放',
        '🔴 **【§238 已更正】**「出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL」'
        '**这句已过时**：v2.6 的 `_DEFAULT_DEVICES_FULL` 实为 **GPU.0/GPU.0/NPU**'
        '（不是全 GPU.0）⇒ 该 FAIL 结论**不适用 v2.6**；'
        '**v2.6 的真实排空口径见 §238 §1.2–§1.5**'
        '（TTS=NPU 臂收尾积压 **292.77 s**／AUTO 臂 **4.01 s**）'
        '｜🔴 **等用户裁定**默认摆放（两档对照数据见 §238 §1.5）',
    ),
]


def getdate() -> str:
    """用 PowerShell 的 `Get-Date` 取实测值（**不推算**）。"""
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         '[DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm:ss")'],
        capture_output=True, text=True)
    v = (r.stdout or '').strip().splitlines()
    if not v:
        raise RuntimeError('Get-Date 取值失败：%r %r' % (r.stdout, r.stderr))
    return v[0].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as fh:
        old = fh.read()
    old_text = old.decode('utf-8')

    m_ack = m_ts = None
    for i, line in enumerate(old_text.split('\n')[:12]):
        if line.startswith('last_ack:'):
            m_ack = i
        elif line.startswith('更新时间:'):
            m_ts = i
    if m_ack is None or m_ts is None:
        print('FAIL: 找不到 last_ack / 更新时间 头部行')
        return 2
    old_ack = old_text.split('\n')[m_ack]
    old_ts = old_text.split('\n')[m_ts]
    new_ack = 'last_ack: APP-137'
    new_ts = '更新时间: %s' % getdate()
    print('old_ack = %r  →  new_ack = %r' % (old_ack, new_ack))
    print('old_ts  = %r  →  new_ts  = %r（Get-Date 实测）' % (old_ts, new_ts))

    lines = old_text.split('\n')
    lines[m_ack] = new_ack
    lines[m_ts] = new_ts
    work = '\n'.join(lines)

    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    # ── 定点替换（**先在原件上验唯一命中**） ───────────────────────
    for tag, o, n in FIXES:
        cnt = old_text.count(o)
        chk('unique_hit_%s' % tag, cnt == 1, '命中 %d 次（要求 1 次）' % cnt)
    if not all(c['ok'] for c in checks):
        for c in checks:
            print('  %-44s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                      c['detail']))
        print('FAIL: 唯一命中不通过 ⇒ 零改动')
        return 3
    for tag, o, n in FIXES:
        work = work.replace(o, n, 1)

    # ── 追加块 ────────────────────────────────────────────────────
    new_text = work + BLOCK
    new = new_text.encode('utf-8')

    # ── 真不变量 ──────────────────────────────────────────────────
    chk('crlf_count_unchanged', new.count(b'\r\n') == old.count(b'\r\n'),
        '%d -> %d' % (old.count(b'\r\n'), new.count(b'\r\n')))
    chk('line_delta_expected',
        (new.count(b'\n') - old.count(b'\n')) == BLOCK.count('\n'),
        '实际 %d / 预期 %d' % (new.count(b'\n') - old.count(b'\n'),
                               BLOCK.count('\n')))
    chk('section_count_plus_one',
        new_text.count('\n## §') == old_text.count('\n## §') + 1,
        '%d -> %d' % (old_text.count('\n## §'), new_text.count('\n## §')))
    chk('last_ack_unique',
        new_text.count('\nlast_ack:') + (1 if new_text.startswith('last_ack:') else 0) == 1,
        'last_ack 字段出现 1 次')
    chk('last_ack_value_correct', new_ack in new_text, new_ack)
    chk('block_has_no_crlf', b'\r\n' not in BLOCK.encode('utf-8'), '追加块全 LF')
    chk('block_ends_with_newline', BLOCK.endswith('\n'), '')
    # 🔴 旧正文除白名单外逐字未变（**还原式反推**）
    back = new_text
    for tag, o, n in FIXES:
        back = back.replace(n, o, 1)
    back_lines = back.split('\n')
    back_lines[m_ack] = old_ack
    back_lines[m_ts] = old_ts
    back = '\n'.join(back_lines)
    back = back[:len(back) - len(BLOCK)] if back.endswith(BLOCK) else back
    chk('reverse_reconstruct_old_body', back == old_text,
        '还原后 %d B vs 原 %d B' % (len(back), len(old_text)))
    # 反证：篡改定点替换 ⇒ 还原式复核必须 FAIL
    bad = new_text.replace(FIXES[0][1], FIXES[0][2], 1)
    bad_lines = bad.split('\n')
    bad_lines[m_ack] = old_ack
    bad_lines[m_ts] = old_ts
    bad = '\n'.join(bad_lines)
    bad = bad[:len(bad) - len(BLOCK)] if bad.endswith(BLOCK) else bad
    chk('counterexample_detected', bad != old_text,
        '篡改定点替换后还原式复核 FAIL ⇒ 判据有鉴别力')

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-44s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    shutil.copy2(STATUS, BACKUP)
    tmp = STATUS + '.tmp_app238'
    with open(tmp, 'wb') as fh:
        fh.write(new)
    os.replace(tmp, STATUS)

    # ── 写后复核（另起一遍读） ────────────────────────────────────
    with open(STATUS, 'rb') as fh:
        now = fh.read()
    with open(BACKUP, 'rb') as fh:
        bakb = fh.read()
    post = [
        {'name': 'bytes_equal_expected', 'ok': now == new, 'detail': '%d B' % len(now)},
        {'name': 'crlf_preserved', 'ok': now.count(b'\r\n') == bakb.count(b'\r\n'),
         'detail': '%d -> %d' % (bakb.count(b'\r\n'), now.count(b'\r\n'))},
        {'name': 'bak_sha_matches_old',
         'ok': hashlib.sha256(bakb).hexdigest() == hashlib.sha256(old).hexdigest(),
         'detail': hashlib.sha256(bakb).hexdigest()[:16]},
        {'name': 'last_ack_is_app137', 'ok': 'last_ack: APP-137' in now.decode('utf-8'),
         'detail': ''},
        {'name': 'section_238_present', 'ok': '## §238' in now.decode('utf-8'), 'detail': ''},
        {'name': 'outdated_fixed',
         'ok': '【§238 已更正】' in now.decode('utf-8'), 'detail': ''},
    ]
    ev = {
        'script': '_app238_append_status.py',
        'task': 'APP-137/APP-134a/APP-135 §238 追加 ＋ 修掉 APP-134 问题⑦ 的过时结论',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'status_path': STATUS,
        'backup': BACKUP,
        'bytes_before': len(old), 'bytes_after': len(now),
        'crlf_before': old.count(b'\r\n'), 'crlf_after': now.count(b'\r\n'),
        'lines_before': old.count(b'\n'), 'lines_after': now.count(b'\n'),
        'old_ack': old_ack, 'new_ack': new_ack,
        'old_timestamp': old_ts, 'new_timestamp': new_ts,
        'point_fixes': [{'tag': t, 'old_len': len(o), 'new_len': len(n)}
                        for t, o, n in FIXES],
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
    }
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    tmp2 = RESULT + '.tmp'
    with open(tmp2, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp2, RESULT)

    print('--- 写后复核 ---')
    for p in post:
        print('  %-44s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('STATUS_APP.md: %d -> %d B（CRLF %d -> %d）'
          % (len(old), len(now), old.count(b'\r\n'), now.count(b'\r\n')))
    print('证据：%s' % RESULT)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
