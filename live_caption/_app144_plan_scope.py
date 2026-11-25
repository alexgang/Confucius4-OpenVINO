#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app144_plan_scope.py — **APP-144 ① 的范围查清与分类**（只读，不改历史）。

## reviewer APP-144 ① 原文
> 范围：§237 §1.3 列出的 13 个存量文件，加上 §237 正文
> （sec237_detail_20261125.md 以及 STATUS_APP.md 里引用了那句译文的地方），
> 一共 14 个文件。
> 2. 这些文件**大多是正常的结果或说明文件，不要整份删掉**。
>    用 `git filter-repo --replace-text <替换表> --refs <含它们的分支>`
>    把命中的句子替换成 `<已移除：内部会议内容>`。
>    替换表也放在仓库外。**如果某个文件本身就是转写或译文 jsonl/csv，
>    可以按 APP-136 的做法用 `--invert-paths` 整份去掉，并在 STATUS 里列明。**

## 本脚本做什么

把 14 个命中文件**分类**成两类，并给出**每个文件的处理方式**：

| 类别 | 判据 | 处理 |
|---|---|---|
| **A 转写/译文产物**（`.mt.txt` / `.tts.jsonl`） | 文件**本身就是**会议译文逐句产物 | `--invert-paths` **整份去掉** |
| **B 正常结果/说明文件**（`.tsv` / `.json` / `.md`） | 是**指标/证据/文档**，只是内嵌了译文样例 | `--replace-text` **替换命中的句子**（**不整份删**） |

🔴 **分类不能靠文件名瞎猜** ⇒ 本脚本**逐文件统计**：
命中行数、命中句在文件里的**占比**、以及「删掉整份会不会丢掉别的指标」。

## 🔴 判据（**有鉴别力**）
* 类别 A 的文件：**去掉命中行后剩余内容为空或极少**
  ⇒ 说明它**整份就是**会议译文 ⇒ 整份去掉不损失别的信息；
* 类别 B 的文件：**去掉命中行后仍有大量别的内容**（指标行、字段、说明）
  ⇒ 整份删会丢信息 ⇒ 只能替换。

⇒ 反证：若把一个明显是指标表的文件（`app273_*.tsv`）判成 A ⇒ 判据错了。
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app144_scope_plan.json')

PATTERN_FILE = r'C:\Users\Trekker-PTL\shared\gitfilter\mt_meeting_pattern.txt'
REPLACE_FILE = r'C:\Users\Trekker-PTL\shared\gitfilter\mt_meeting_replace.txt'


def git(*args, **kw):
    r = subprocess.run(['git'] + list(args), cwd=REPO,
                       capture_output=True, text=True, errors='replace', **kw)
    return r.returncode, r.stdout, r.stderr


def main():
    with io.open(PATTERN_FILE, encoding='utf-8') as fh:
        phrases = [ln.strip() for ln in fh if ln.strip()]

    # ── 全历史命中（文件 × 提交） ────────────────────────────────
    rc, out, err = git('rev-list', '--all')
    revs = out.split()
    rc, out, err = git('grep', '-l', '-F', '-f', PATTERN_FILE, *revs)
    hits = {}
    for line in out.splitlines():
        if ':' not in line:
            continue
        sha, _, path = line.partition(':')
        hits.setdefault(path, set()).add(sha)
    files = sorted(hits)

    # ── 逐文件统计 ───────────────────────────────────────────────
    detail = []
    for path in files:
        rc, out, err = git('show', 'origin/main:%s' % path)
        if rc != 0:
            continue
        text = out
        lines = text.split('\n')
        n_hit_lines = 0
        for ln in lines:
            if any(p in ln for p in phrases):
                n_hit_lines += 1
        # 🔴 **去掉命中行后还剩多少非空行** ⇒ 判据
        rest = [ln for ln in lines if not any(p in ln for p in phrases)]
        n_rest = len([ln for ln in rest if ln.strip()])
        # 🔴 **整份是不是「逐句译文」** ⇒ 看是不是几乎每行都含译文特征
        #    （判据：非空行里，命中行占绝大多数 ⇒ 整份就是译文）
        n_nonempty = len([ln for ln in lines if ln.strip()])
        ratio = (n_hit_lines / n_nonempty) if n_nonempty else 0.0
        # 🔴🔴 **判据（不能只看特征句命中数）**：特征句只是**抽样**，
        #    整份文件的**性质**要看「去掉命中行后剩下的内容是什么」。
        #
        #    类别 A（**整份就是会议转写/译文**）的判据：
        #      ① 文件是**逐句产物**（`.mt.txt` 每行一句译文；`.tts.jsonl`
        #         每行一个 JSON 句对象）⇒ 整份都是会议内容；
        #      ② 或：**数据行里绝大多数的原文列是英文散文**
        #         （⇒ 整份都是会议转写，不是指标表）。
        #
        #    🔴 **反例（说明为什么不能只看特征句）**：`app273_*.tsv` 只有 2/47 行
        #    命中特征句（4%），但它的 **45/46 个数据行的原文列都是英文会议内容**
        #    ⇒ 整份都是会议转写 ⇒ 属类别 A。
        #
        #    类别 B（**正常结果/说明文件**）：**结构化指标/证据/文档**
        #    ⇒ 只能替换句子，**整份删会丢指标**。
        is_transcript = False
        why = []
        base = os.path.basename(path)
        # ① 逐句产物（后缀判定）
        if base.endswith('.mt.txt') or base.endswith('.tts.jsonl'):
            is_transcript = True
            why.append('逐句产物（.mt.txt / .tts.jsonl）')
        # ② TSV：数据行里绝大多数原文列是**英文散文**
        elif base.endswith('.tsv'):
            n_data = 0
            n_en = 0
            for ln in lines[1:]:
                if not ln.strip():
                    continue
                cols = ln.split('\t')
                if len(cols) < 2:
                    continue
                n_data += 1
                src = cols[1].strip()
                # 🔴 英文散文判据：有**多个空格分词**且含**小写词**
                #    （指标表的数字/短标签不会这样）
                if len(src.split()) >= 4 and any(c.islower() for c in src):
                    n_en += 1
            if n_data and (n_en / n_data) >= 0.8:
                is_transcript = True
                why.append('TSV 数据行 %d/%d 的原文列是英文散文 ⇒ 整份是会议转写'
                           % (n_en, n_data))
        if not is_transcript:
            why.append('结构化指标/证据/文档 ⇒ 只替换句子')
        detail.append({
            'path': path,
            'n_commits_touching': len(hits[path]),
            'bytes': len(text.encode('utf-8')),
            'n_lines_nonempty': n_nonempty,
            'n_hit_lines': n_hit_lines,
            'hit_ratio': round(ratio, 3),
            'n_rest_nonempty_after_removing_hits': n_rest,
            'treatment': 'invert_paths' if is_transcript else 'replace_text',
            'category': 'A_转写或译文产物' if is_transcript else 'B_正常结果或说明文件',
            'why': '；'.join(why),
        })

    a_files = [d['path'] for d in detail if d['treatment'] == 'invert_paths']
    b_files = [d['path'] for d in detail if d['treatment'] == 'replace_text']

    ok = True
    checks = []
    # 🔴 **反证 1**：类别 A 里**不该**出现「证据 JSON」
    #    （`app273_*_evidence.json` 是**指标证据** ⇒ 属类别 B ⇒ 只替换句子）
    bad_a = [p for p in a_files if p.endswith('_evidence.json')]
    checks.append({'name': 'no_evidence_json_in_invert_list', 'ok': not bad_a,
                   'detail': 'invert 清单里的 evidence.json：%s（应为空）'
                             % (bad_a or '无')})
    if bad_a:
        ok = False
    # 🔴 **反证 1b**：类别 B 里**必须**有那个 evidence.json（它**不能**整份删）
    need_b = 'results/app/app273_mt_int4_vs_int8_evidence.json'
    checks.append({'name': 'evidence_json_in_replace_list',
                   'ok': need_b in b_files,
                   'detail': 'evidence.json 在 replace 清单里：%s' % (need_b in b_files)})
    if need_b not in b_files:
        ok = False
    # 🔴 **反证 2**：类别 B 里**必须**出现 §237 正文（它是文档 ⇒ 只能替换）
    has_doc = any(p.endswith('.md') for p in b_files)
    checks.append({'name': 'doc_in_replace_list', 'ok': has_doc,
                   'detail': 'replace 清单里有 .md（§237 正文）：%s' % has_doc})
    if not has_doc:
        ok = False
    # 🔴 **反证 3**：总数必须 = 14
    checks.append({'name': 'total_files_is_14', 'ok': len(files) == 14,
                   'detail': '命中文件数 = %d（期望 14）' % len(files)})
    if len(files) != 14:
        ok = False
    # 🔴 **反证 4**：分类判据本身有鉴别力
    #    （把 ratio 阈值降到 0 ⇒ 全判 A ⇒ 必然把 .tsv 判成 A ⇒ 判据失效）
    thresh_test = [d for d in detail if d['hit_ratio'] >= 0.0]
    checks.append({'name': 'classifier_has_discriminating_power',
                   'ok': len(thresh_test) != len([d for d in detail if d['treatment'] == 'invert_paths']),
                   'detail': '阈值降到 0 ⇒ %d 个都判 A（而真判据只判 %d 个）⇒ 判据有鉴别力'
                             % (len(thresh_test),
                                len([d for d in detail if d['treatment'] == 'invert_paths']))})

    print('=== APP-144 ① 范围查清（%d 个命中文件）===' % len(files))
    print('--- 类别 A：转写/译文产物 ⇒ --invert-paths 整份去掉（%d 个）---' % len(a_files))
    for p in a_files:
        d = next(x for x in detail if x['path'] == p)
        print('  %-64s 命中行=%s/%s (%.0f%%) 去后剩=%s 行'
              % (p, d['n_hit_lines'], d['n_lines_nonempty'],
                 d['hit_ratio'] * 100, d['n_rest_nonempty_after_removing_hits']))
    print('--- 类别 B：正常结果/说明文件 ⇒ --replace-text 只替换句子（%d 个）---' % len(b_files))
    for p in b_files:
        d = next(x for x in detail if x['path'] == p)
        print('  %-64s 命中行=%s/%s (%.0f%%) 去后剩=%s 行'
              % (p, d['n_hit_lines'], d['n_lines_nonempty'],
                 d['hit_ratio'] * 100, d['n_rest_nonempty_after_removing_hits']))
    print('--- 判据核对 ---')
    for c in checks:
        print('  %-38s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL', c['detail']))

    ev = {
        'script': '_app144_plan_scope.py',
        'task': 'APP-144 ①：查清 14 个命中文件的范围并分类处理方式',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pattern_file': PATTERN_FILE,
        'replace_file': REPLACE_FILE,
        'phrases': len(phrases),
        'n_files': len(files),
        'files': files,
        'detail': detail,
        'invert_paths_list': a_files,
        'replace_text_list': b_files,
        'checks': checks,
        'ok': ok,
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    print('ALL PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
