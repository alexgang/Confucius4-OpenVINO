# -*- coding: utf-8 -*-
r"""_app424_compress_sec170.py —— **把 §170 正文整块归档，活文档留指针 + 速查**。

## 为什么（APP-052④）

STATUS 硬限额 **≤ 40000 B / ≤ 300 行**。
`_app416_write_status170.py` 写入 §170 后实测 **43 483 B / 307 行 ⇒ 超限**。
⇒ 按 §166/§167/§168/§169 **同一做法**：**正文整块逐字归档**（write-once），
活文档只留 **一行指针 + 一段速查**。

## 纪律

* 🔴 **只替换 §170 这一块**（旧章节标题一个不动；§169 及以前的正文一字未动）；
* 🔴 **归档件 write-once**：已存在 ⇒ 报错退出（不覆盖）；
* 🔴 **逐字节复核**：落盘归档块 == 被替换的块；
* 🔴 **头部只动 `更新时间` / `当前任务` 两行**（`last_ack` 已是 APP-098，不动）；
* 🔴 写后自证：①归档块逐字节一致 ②旧章节标题全在 ③≤40000 B / ≤300 行
  ④**速查行里的关键数字与归档块中的原文一致**（防速查行写错）。

用法：
```
.venv/Scripts/python.exe results/app/_app424_compress_sec170.py
```
"""
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec170_20261111.md')
REPORT = os.path.join(HERE, 'app424_status170_compress.json')

LIM_BYTES = 40000
LIM_LINES = 300

#: 速查行里出现的关键数字 —— **必须逐个能在归档块原文中命中**（自证用）
KEY_FACTS = [
    '290b9b2e83d41da1',
    '76b400e40f95fd21',
    '4 420 655 883',
    '10 466',
    '3c39bdfae8d1398d',
    '291b076a95c807d7',
    'app423_rc6_dir_rollback.json',
    'app420_minimvp_rc7_build_evidence.json',
    'app422_rc7_zip_evidence.json',
    'app413b_rc6_gui_shots',
    'app414_rc6_smoke.json',
    'app417_rc6_model_identity.json',
    'app419_rc6_langs_summary.json',
]


def sha256_text(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def main():
    ev = {'script': '_app424_compress_sec170.py',
          'status': STATUS, 'archive': ARCHIVE}

    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    text = raw.replace('\r\n', '\n')

    old_titles = re.findall(r'^## (§\d+)', text, re.M)
    ev['old_section_titles'] = old_titles

    # ── ① 定位 §170 块（必须是最后一个章节）─────────────────────
    m = re.search(r'^## §170 .*$', text, re.M)
    if not m:
        print('!! 找不到 §170')
        return 2
    start = m.start()
    block = text[start:].rstrip('\n')
    ev['sec170_block_bytes'] = len(block.encode('utf-8'))
    ev['sec170_block_sha256'] = sha256_text(block)
    ev['block_is_last_section'] = (
        '## §169' in text[:start] and text[:start].rfind('## §') <
        text[:start].rfind('## §169'))

    # ── ② write-once 归档 ───────────────────────────────────────
    if os.path.exists(ARCHIVE):
        print('🔴 归档件已存在（write-once，不覆盖）：%s' % ARCHIVE)
        return 2
    with open(ARCHIVE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(block + '\n')
    with open(ARCHIVE, 'r', encoding='utf-8') as f:
        got = f.read().rstrip('\n')
    if got != block:
        print('🔴 归档件与原块不一致 ⇒ 中止')
        os.remove(ARCHIVE)
        return 2
    ev['archive_bytes'] = os.path.getsize(ARCHIVE)
    ev['archive_sha256'] = sha256_text(got)
    ev['archive_matches_block'] = True

    # ── ③ 速查行（数字必须能在归档块里命中）────────────────────
    missing = [k for k in KEY_FACTS if k not in block]
    ev['key_facts_missing_in_block'] = missing
    if missing:
        print('🔴 速查数字在归档块中找不到：%s' % missing)
        os.remove(ARCHIVE)
        return 2

    stub = (
        '> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/'
        'STATUS_APP_sec170_20261111.md`（%d B／块 SHA256 `%s`）。\n'
        '> 🔴 **速查**：**交付包 = MiniMVP rc7**'
        '（`Confucius4_LiveCaption_MiniMVP_v1.0-rc7`，'
        'zip **4 420 655 883 B／SHA256 `290b9b2e83d41da1…`／10 466 条目／CRC 全对**）｜'
        '**一、界面和后端 9 项全 PASS**（三后端无 NVIDIA/CUDA、只留 Intel GPU/NPU 两档、'
        'MT 默认指向包内实有的 INT4-CW、下拉无灰「缺」、克隆音色置灰＋提示、'
        'CLI `follow_speaker` 回落 A 并打日志、目标语言 10 种、'
        '未知语言码报错不回英文）｜'
        '**二、rc5 五个实测问题全修**（编码崩溃／`models/tokenizer` 残留／'
        'ASR 不打印 `EXECUTION_DEVICES`／ASR+MT 同占 GPU 崩溃／README 自相矛盾）｜'
        '**三、验收 5 项全 PASS**（GUI 截图 6/6、`--check` 无 NVIDIA/CUDA/缺、'
        '6 臂 60 s 冒烟 6/6、10 语种 10/10、模型身份 PASS）｜'
        "**🔴 本轮另查出并修掉 1 个 GUI 真缺陷**（`kind=='asr06b'` 未被识别 ⇒ "
        '两个 ASR 档 label 完全相同 ⇒ GUI 靠 label 反查 ⇒ **静默错档**）｜'
        '**🔴 本轮自查出一次自违规**（验收时在 rc6 目录就地改了代码 ⇒ '
        '**已回滚 rc6 目录**，rc6 zip 一字未动 ⇒ rc6 zip 登记为「含缺陷、未交付」）｜'
        '**三处如实登记的不足**（MT 无 `EXECUTION_DEVICES` 直证／'
        'App 链路 de·zh 的 TTS wav 被 6 s 过期闸丢弃／`app415 summary.json` 的 '
        '`translations` 字段自相矛盾）｜**未打包 v2.5、未通知用户、未调 MiniMax**。'
        % (ev['archive_bytes'], ev['archive_sha256']))

    title170 = m.group(0)
    text = text[:start] + title170 + '\n\n' + stub + '\n'

    # ── ④ 头部定点更新（只动两行）──────────────────────────────
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    text = re.sub(r'^更新时间: .*$', '更新时间: ' + stamp, text, count=1, flags=re.M)
    text = re.sub(r'^当前任务: .*$', NEW_TASK_LINE, text, count=1, flags=re.M)
    ev['stamp'] = stamp

    out = text.replace('\n', nl) if nl != '\n' else text
    tmp = STATUS + '.tmp424'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    # ── ⑤ 写后自证 ─────────────────────────────────────────────
    with open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    after_t = after.replace('\r\n', '\n')
    ev['after_bytes'] = len(after.encode('utf-8'))
    ev['after_lines'] = after.count('\n')
    ev['within_limits'] = (ev['after_bytes'] <= LIM_BYTES
                            and ev['after_lines'] <= LIM_LINES)
    new_titles = re.findall(r'^## (§\d+)', after_t, re.M)
    ev['new_section_titles'] = new_titles
    ev['old_titles_preserved'] = all(t in new_titles for t in old_titles)
    ev['sec170_present'] = '## §170' in after_t
    ev['archive_pointer_present'] = 'STATUS_APP_sec170_20261111.md' in after_t
    # 速查行的数字必须都在归档块里
    ev['stub_key_facts_all_in_block'] = all(k in block for k in KEY_FACTS)

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in (
        'after_bytes', 'after_lines', 'within_limits',
        'old_titles_preserved', 'sec170_present', 'archive_pointer_present',
        'archive_matches_block', 'stub_key_facts_all_in_block',
        'key_facts_missing_in_block', 'archive_bytes', 'archive_sha256',
        'sec170_block_bytes', 'sec170_block_sha256')},
        ensure_ascii=False, indent=1))
    return 0 if (ev['within_limits'] and ev['old_titles_preserved']
                 and ev['archive_matches_block']) else 1


NEW_TASK_LINE = (
    '当前任务: **执行 APP-098**（`last_ack=APP-098`；纠偏文件仍是 97 条 / 最大 APP-097 '
    '⇒ **APP-098 由 reviewer 口头下达，未落 `CORRECTIONS_APP.md`**）｜'
    '**MiniMVP rc7 修整**：三后端去 NVIDIA/CUDA＋只留 Intel GPU/NPU 两档、'
    '克隆音色置灰、目标语言扩 10 种、rc5 五个实测问题（编码崩溃／R2T2 残留／'
    '设备不打印／ASR+MT 同占 GPU 崩溃／README 自相矛盾）'
    '⇒ 代码改在 dev 树 `live_caption/`，**MiniMVP 与 v2.5 共用部分只改一处**｜'
    "**本轮另查出并修掉 1 个 GUI 真缺陷**（`kind=='asr06b'` 落进「遍历设备」分支 "
    '⇒ 两个 ASR 档 label 完全相同 ⇒ GUI 靠 label 反查会静默取错档）｜'
    '**本轮自查出一次自违规**（验收时在 rc6 目录就地改了代码 ⇒ 已回滚 rc6 目录，'
    'rc6 zip 一字未动）｜'
    '**交付包 = rc7**（4 420 655 883 B／SHA256 `290b9b2e83d41da1…`）｜结果见 §170｜'
    '**本条需等 reviewer 复核**')


if __name__ == '__main__':
    sys.exit(main())
