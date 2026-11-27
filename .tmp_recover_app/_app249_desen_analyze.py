r"""_app249_desen_analyze.py —— 分析「补做脱敏」该怎么改才**既彻底又不误伤**（只读，不改文件）。

## 背景（§249 发现的真缺陷）

§248 登记「脱敏完成」，但它自己的证据 `app155_desens_verify.json` 的 `verdict` 当时是 **FAIL**。
根因：`app155_desens_ground_truth.json` 的 `hits` **每文件只记 14 行**，
`app155_desens_apply.py` **只遍历 hits 记到的行** ⇒ 每文件另外 ~45 行含会议原句的行**从未被替换**。

## 本脚本要回答的问题

补做时，**判据该多严**？

* **Tier-1（整句口径，= §248 的原算法）**：把行切成句子，剥掉日志前缀后
  若该句归一化 ∈ GT ⇒ 整句换成占位。
  ⇒ **安全**（不会误伤技术散文），但**可能漏**（句子里只嵌了 GT 片段时判不出）。
* **Tier-2（子串口径）**：行归一化后**包含**任一 GT 句 ⇒ 命中。
  ⇒ **彻底**，但 ⚠️ **会误伤**：GT 里含很多**短促的通用短语**
  （如 `moving forward` / `good morning` / `okay`），
  它们在技术散文里也正常出现 ⇒ 全量替换会**改坏正常文档**。

⇒ 本脚本给出：**Tier-1 全量补做后**的残留清单（按命中 GT 句的长度分档），
并打印每处的上下文 ⇒ 用来**实证**地定 Tier-2 的阈值，而不是拍脑袋。
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GTJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_ground_truth.json')
SCANJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_scan_full.json')
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_analysis.json')

PUNCT = r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]'
LOG_PREFIX_RE = re.compile(r'^(?:\[[^\]]{1,40}\]\s*)+')


def log(m):
    print(m, flush=True)


def norm(s):
    s = s.strip().lower()
    s = re.sub(r'[\s　]+', ' ', s)
    return re.sub(PUNCT, '', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


def strip_log_prefix(s):
    m = LOG_PREFIX_RE.match(s)
    if not m:
        return s, ''
    return s[m.end():], m.group(0)


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
    scan = json.load(open(SCANJSON, encoding='utf-8'))
    min_len = gt['min_len']
    sents = build_gt(gt)
    ordered = sorted(sents, key=len, reverse=True)
    log('GT 句子 %d 条' % len(sents))

    skip_suffix = ('.transcript.txt', '.mt.txt', '.tts.jsonl')
    reviewer_owned = set(gt['reviewer_owned'])

    tier1_fixed = 0
    residual = []          # Tier-1 之后仍命中的行
    buckets = {'lt20': 0, '20to39': 0, 'ge40': 0}
    samples = {'lt20': [], '20to39': [], 'ge40': []}

    for rel in sorted(scan['hits']):
        if rel in reviewer_owned:
            continue
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        lines = t.splitlines(keepends=True)

        # ── Tier-1：整句口径（全量行）─────────────────────────
        after_lines = []
        for raw in lines:
            m = re.match(r'^(.*?)((?:\r\n|\r|\n)*)$', raw, re.S)
            body, term = m.group(1), m.group(2)
            new_body = body
            for s in sentences(body):
                core, pre = strip_log_prefix(s)
                nc = norm(core)
                if len(nc) >= min_len and nc in sents:
                    target = pre + core
                    if target in new_body:
                        new_body = new_body.replace(target, pre + '[会议句 idx X]', 1)
            after_lines.append(new_body + term)

        # ── Tier-2 残留判定（子串口径）────────────────────────
        for i, body in enumerate(after_lines, 1):
            n = norm(body)
            if len(n) < min_len:
                continue
            hit = [s for s in ordered if s in n]
            if not hit:
                continue
            longest = max(hit, key=len)
            bucket = 'lt20' if len(longest) < 20 else ('20to39' if len(longest) < 40 else 'ge40')
            buckets[bucket] += 1
            if len(samples[bucket]) < 40:
                samples[bucket].append({
                    'file': rel, 'line': i,
                    'n_hit': len(hit), 'longest_len': len(longest),
                    'longest': longest[:100],
                    'ctx': body.strip()[:200],
                    'is_skip_suffix': rel.endswith(skip_suffix),
                })
            residual.append({'file': rel, 'line': i, 'n_hit': len(hit),
                             'longest_len': len(longest), 'longest': longest[:100],
                             'is_skip_suffix': rel.endswith(skip_suffix)})

    log('\nTier-1（全量行·整句口径）之后仍按子串口径命中的行：%d 处' % len(residual))
    for k in ('lt20', '20to39', 'ge40'):
        log('   命中句长度 %-6s : %d 处' % (k, buckets[k]))

    for k in ('lt20', '20to39', 'ge40'):
        log('\n===== 样本：%s =====' % k)
        for s in samples[k][:22]:
            log('  %s:%d  len=%d  skip=%s' % (s['file'], s['line'],
                                             s['longest_len'], s['is_skip_suffix']))
            log('      ctx: %s' % s['ctx'][:150])
            log('      gt : %s' % s['longest'])

    out = {
        'script': '_app249_desen_analyze.py',
        'n_gt_sentences': len(sents),
        'n_residual_lines': len(residual),
        'buckets': buckets,
        'samples': samples,
        'residual': residual[:4000],
    }
    tmp = OUTJSON + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUTJSON)
    log('\n证据 → %s' % OUTJSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
