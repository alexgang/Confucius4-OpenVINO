#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-136 ⑤：给仓库根 `.gitignore` 追加「含 ASR/MT 文本的结果文件」类别规则。

🔴 为什么必须用**字节层**追加（而不是 Edit 工具）：
   本仓 `core.autocrlf=true` 且仓库根**无** `.gitattributes` ⇒ `.gitignore`
   本身是**混合行尾**（实测 96 CRLF + 113 LF）。Edit 工具会把整份文件统一
   规整成 LF ⇒ 违反「行尾风格不变」+「旧正文逐字未变」⇒ 必须字节层重建。

写入三件套（MEMORY 一）：
   ① 备份（`.overwritten_app136`）
   ② 写前在**内存新文本**上跑真不变量（行尾风格不变 / 旧正文逐字未变 /
      字节等长增量 / 行数增量 == 新增行数）
   ③ 临时文件 → `os.replace` ⇒ 写后**另起脚本**复核 + `numstat`
"""
import io
import os
import shutil
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GITIGNORE = os.path.join(REPO, '.gitignore')
BACKUP = os.path.join(REPO, '.gitignore.overwritten_app136')
EVIDENCE = os.path.join(REPO, 'results', 'app', 'app136_gitignore_rules.json')

# 🔴 新增块：**只用 LF**（与本文件末尾风格一致 —— 末尾 17 行全是 LF）。
BLOCK = """
# APP-136（2026-11-25）：**含 ASR/MT 文本的结果文件** —— 绝不能进仓库。
#   起因：§236 的 94f95f6 把两份「10 分钟内部会议片段逐句中文译文全文」的
#   `.tts.jsonl` 推到了 GitHub ⇒ 用户决定改写历史抹掉（APP-136 ①，已执行）。
#   🔴 实测：**同一份内部会议译文不止那两份** —— 用 `git grep -F` 拿译文里的
#   特征句做探针，在 **21 个已入库文件**里命中（`*_mt.txt` / `*.tts.jsonl` /
#   `app273_*.tsv` / `app273_*_evidence.json` 等）⇒ 本规则按**类别**兜底，
#   不是只堵那两份。
#   ⚠️ 已入库的同类文件**仍然被跟踪**（.gitignore 只挡新增、不动存量）⇒
#   存量是否一并清理**须由 reviewer 单独裁定**（见 STATUS_APP.md §237）。
# ── 逐句译文/合成时间线（.tts.jsonl）──────────────────────────────────
*.tts.jsonl
# ── MT 译文正文（*.mt.txt）────────────────────────────────────────────
*.mt.txt
# ── 通用转写正文 ─────────────────────────────────────────────────────
*.transcript.txt
# ── 已知携带会议译文的**一次性**产物（存量已跟踪；此处只挡新增/重新入库）──
results/app/app273_mt_int4_vs_int8.tsv
results/app/app273_mt_int4_vs_int8_evidence.json
results/app/app312_rc5_out/npu/transcript.mt.txt
results/app/app458_app100_device/gpu_control_asr_npu.mt.txt
results/app/app461_app100_device/gpu_control_asr_npu.mt.txt
results/app/app501_app105_rc10_acceptance/chain10min.mt.txt
results/app/_app551_*.mt.txt
results/app/_app591_*.tts.jsonl
results/app/app458_app100_device/*.tts.jsonl
results/app/app461_app100_device/*.tts.jsonl
""".encode('utf-8')


def main():
    old = open(GITIGNORE, 'rb').read()
    # ① 备份
    if not os.path.exists(BACKUP):
        shutil.copy2(GITIGNORE, BACKUP)
    assert open(BACKUP, 'rb').read() == old, 'backup mismatch'

    old_crlf = old.count(b'\r\n')
    old_lf = old.count(b'\n')
    old_lines = old.split(b'\n')

    new = old + BLOCK
    new_crlf = new.count(b'\r\n')
    new_lf = new.count(b'\n')
    new_lines = new.split(b'\n')

    # ② 写前真不变量（在**内存新文本**上跑）
    checks = []

    def chk(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print('%-38s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        return ok

    chk('old_bytes_unchanged_prefix', new.startswith(old),
        'new[:len(old)] == old')
    chk('crlf_count_unchanged', new_crlf == old_crlf,
        '%d -> %d' % (old_crlf, new_crlf))
    chk('lf_delta_equals_block_lf', (new_lf - old_lf) == BLOCK.count(b'\n'),
        'delta=%d block_lf=%d' % (new_lf - old_lf, BLOCK.count(b'\n')))
    chk('old_lines_prefix_verbatim', new_lines[:len(old_lines)] == old_lines,
        'first %d lines verbatim' % len(old_lines))
    chk('byte_delta_equals_block_len', (len(new) - len(old)) == len(BLOCK),
        'delta=%d block=%d' % (len(new) - len(old), len(BLOCK)))
    chk('block_has_no_crlf', b'\r\n' not in BLOCK, 'block uses LF only')
    chk('block_ends_with_lf', BLOCK.endswith(b'\n'), '')
    chk('no_duplicate_rule',
        len(set(l for l in BLOCK.split(b'\n') if l and not l.startswith(b'#'))) ==
        len([l for l in BLOCK.split(b'\n') if l and not l.startswith(b'#')]),
        'no duplicate pattern lines')

    if not all(c['ok'] for c in checks):
        print('\n❌ 写前不变量 FAIL ⇒ 零改动')
        return 1

    # ③ 临时文件 → os.replace（原子）
    tmp = GITIGNORE + '.app136.tmp'
    with open(tmp, 'wb') as fh:
        fh.write(new)
        fh.flush()
        os.fsync(fh.fileno())
    assert open(tmp, 'rb').read() == new, 'tmp write mismatch'
    os.replace(tmp, GITIGNORE)

    # 写后**自检**（同一脚本内立即复核一遍，不依赖外部脚本）
    after = open(GITIGNORE, 'rb').read()
    ok_after = (after == new and after.startswith(old) and
                after.count(b'\r\n') == old_crlf and
                len(after) - len(old) == len(BLOCK))
    print('\n写后自检:', 'PASS' if ok_after else 'FAIL')
    if not ok_after:
        shutil.copy2(BACKUP, GITIGNORE)
        print('已回滚到备份')
        return 1

    import json
    out = {
        'file': '.gitignore',
        'bytes_before': len(old),
        'bytes_after': len(after),
        'crlf_before': old_crlf,
        'crlf_after': after.count(b'\r\n'),
        'lf_before': old_lf,
        'lf_after': after.count(b'\n'),
        'block_bytes': len(BLOCK),
        'backup': os.path.relpath(BACKUP, REPO),
        'backup_sha256': __import__('hashlib').sha256(old).hexdigest(),
        'after_sha256': __import__('hashlib').sha256(after).hexdigest(),
        'patterns_added': [l.decode('utf-8') for l in BLOCK.split(b'\n')
                           if l and not l.startswith(b'#')],
        'pre_write_invariants': checks,
        'post_write_selfcheck_ok': ok_after,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    with io.open(EVIDENCE, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print('wrote', os.path.relpath(EVIDENCE, REPO))
    return 0


if __name__ == '__main__':
    sys.exit(main())
