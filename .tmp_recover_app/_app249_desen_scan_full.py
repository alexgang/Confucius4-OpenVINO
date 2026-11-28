r"""_app249_desen_scan_full.py —— APP-155 脱敏的**完整扫描（子串粒度）**（只读，不改文件）。

## 为什么必须重扫（§249 发现的真缺陷）

`app155_desens_ground_truth.json` 的 `hits` **每文件只记了 14 行**，
而 `app155_desens_apply.py` 只遍历 `hits` 里记到的行 ⇒
**同一文件里另外 45 行含会议原句的行从未被访问、从未被替换**。
⇒ §248 登记的「812 处替换 / 76 个文件；穷尽重扫仍命中 0 个文件」**不成立**：
`app155_desens_verify.json` 的 `verdict` 当时就是 **FAIL**（§248 没写这一条）。

🔴 为什么原来的穷尽重扫没抓到：**它按「整句」切**（`sentences()`），
而漏掉的那些句是**嵌在更大的句子里**（例如 `So, the [会议句 idx 6].`
⇒ 切出来是 `So, the [会议句 idx 6]` ⇒ 归一化后**不等于** GT 里的 `[会议句 idx 6]`
⇒ 判不出命中）⇒ **只查整句 ⇒ 漏**。

## 本脚本的判据（**子串粒度**）

`GT 句` = ground truth 里的归一化句子集合（571 条）。
对每个**受控文本文件**的**每一行**：
    该行归一化后，若**包含**任一 GT 句（子串）⇒ 该行命中。

⇒ 比「整句相等」**更严** ⇒ 不会漏。
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GTJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_ground_truth.json')
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_scan_full.json')

PUNCT = r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]'


def log(m):
    print(m, flush=True)


def norm(s):
    s = s.strip().lower()
    s = re.sub(r'[\s　]+', ' ', s)
    return re.sub(PUNCT, '', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


def build_gt(gt):
    sents = set()
    for rel in gt['gt_files']:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        if rel.endswith('.jsonl'):
            for line in t.splitlines():
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                for k in ('text', 'tgt', 'src', 'zh', 'en'):
                    if isinstance(o.get(k), str):
                        sents.add(norm(o[k]))
            continue
        for s in sentences(t):
            sents.add(norm(s))
    return {s for s in sents if len(s) >= gt['min_len']}


def main():
    gt = json.load(open(GTJSON, encoding='utf-8'))
    sents = build_gt(gt)
    log('GT 句子 %d 条（len>=%d）' % (len(sents), gt['min_len']))
    # 长句优先（子串判定时，短句会被长句包含 ⇒ 先判长句，避免重复计数）
    ordered = sorted(sents, key=len, reverse=True)

    r = subprocess.run(['git', '-C', REPO, 'ls-files'], capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    tracked = [x for x in r.stdout.splitlines() if x.strip()]
    reviewer_owned = set(gt['reviewer_owned'])

    TEXT_EXT = ('.md', '.json', '.txt', '.tsv', '.csv', '.jsonl')
    SKIP_SUFFIX = ('.transcript.txt', '.mt.txt', '.tts.jsonl')

    hits = {}
    for rel in tracked:
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        rows = []
        for i, line in enumerate(t.splitlines(), 1):
            n = norm(line)
            if len(n) < gt['min_len']:
                continue
            hit_sents = [s for s in ordered if s in n]
            if hit_sents:
                rows.append({'line': i,
                             'n_gt': len(hit_sents),
                             'longest': max(hit_sents, key=len),
                             'text': line.strip()[:160]})
        if rows:
            hits[rel] = rows

    n_lines = sum(len(v) for v in hits.values())
    log('命中文件 %d 个 / 命中行 %d 处' % (len(hits), n_lines))

    # 旧 hits（§248 的）与新扫描的对比
    old_hits = gt['hits']
    cmp = []
    for rel in sorted(set(hits) | set(old_hits)):
        old_lines = set(r['line'] for r in old_hits.get(rel, []))
        new_lines = set(r['line'] for r in hits.get(rel, []))
        cmp.append({'file': rel,
                    'n_old_lines': len(old_lines),
                    'n_new_lines': len(new_lines),
                    'n_missing': len(new_lines - old_lines),
                    'is_reviewer_owned': rel in reviewer_owned,
                    'is_skip_suffix': rel.endswith(SKIP_SUFFIX)})
    n_missing_total = sum(c['n_missing'] for c in cmp)
    log('🔴 旧 hits 漏掉的行数合计：%d' % n_missing_total)
    for c in cmp:
        if c['n_missing']:
            log('   %-70s 旧 %d → 新 %d（漏 %d）%s%s'
                % (c['file'], c['n_old_lines'], c['n_new_lines'], c['n_missing'],
                   ' [reviewer独占]' if c['is_reviewer_owned'] else '',
                   ' [逐句产物]' if c['is_skip_suffix'] else ''))

    out = {
        'script': '_app249_desen_scan_full.py',
        'method': '子串粒度：行归一化后包含任一 GT 句即命中（比整句相等更严）',
        'n_gt_sentences': len(sents),
        'n_files_with_hits': len(hits),
        'n_hit_lines': n_lines,
        'n_missing_vs_old': n_missing_total,
        'hits': hits,
        'compare': cmp,
    }
    tmp = OUTJSON + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUTJSON)
    log('\n证据 → %s' % OUTJSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
