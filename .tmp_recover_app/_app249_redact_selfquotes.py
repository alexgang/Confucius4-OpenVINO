r"""_app249_redact_selfquotes.py —— 清掉**本轮自己产出的文件**里引用的会议原句（APP-155／RULES §0）。

## 为什么必须清（自我审查发现的自伤）

APP-155 明文：「今后 STATUS 和邮件里**不摘抄测试片段（SPE/QGS 内部会议）的原句、译文或内部代号**，
只写段号 / 时间点和错误类别（RULES §0，11-27）」。

🔴 本轮我**自己**在下列文件里**引用了会议原句**（举例说明判据用）⇒ **违反同一条纪律**。

## 做法（**归一化 + 索引映射**，与主 apply 同一套 ⇒ 已验证不会漏）

对每一行：逐字符归一化并记录原文下标 ⇒ 在归一化串里找 GT 句 ⇒ 换算回原文 span ⇒
把该 span 换成 `<会议原句 len=N sha256=xxxxxxxx>`（**不含任何原文片段**，不可复原）。

🔴 只用「原文形态逐个 replace」会漏（标点/大小写变体）⇒ 必须走归一化索引映射。

## 写前不变量

行数不变、行尾风格不变、JSON 仍可解析、**非命中部分逐字节不变**。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GTJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_ground_truth.json')

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r'[\s　]+')


def log(m):
    print(m, flush=True)


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(' ', s)
    return PUNCT_RE.sub('', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


def norm_with_map(s):
    out = []
    idx = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace() or c == '　':
            j = i
            while j < n and (s[j].isspace() or s[j] == '　'):
                j += 1
            out.append(' ')
            idx.append(i)
            i = j
            continue
        if PUNCT_RE.match(c):
            i += 1
            continue
        out.append(c.lower())
        idx.append(i)
        i += 1
    idx.append(n)
    return ''.join(out), idx


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


def eol(b):
    crlf = b.count(b'\r\n')
    return crlf, b.count(b'\n') - crlf


def main():
    gt = json.load(open(GTJSON, encoding='utf-8'))
    sents = build_gt(gt)
    ordered = sorted(sents, key=len, reverse=True)

    TARGETS = [
        'results/app/app249_desen_analysis.json',
        'results/app/app249_desen_final_verify.json',
        'results/app/app249_desen_scan_full.json',
        'results/app/_app249_status_email_body.txt',
        'status/app/STATUS_APP_sec249_detail_20261127.md',
    ]

    for rel in TARGETS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            log('  [跳过] %s' % rel)
            continue
        before = open(p, 'rb').read()
        text = before.decode('utf-8')
        lines = text.splitlines(keepends=True)

        n_fix = 0
        for i, ln in enumerate(lines):
            m = re.match(r'^(.*?)((?:\r\n|\r|\n)*)$', ln, re.S)
            body, term = m.group(1), m.group(2)
            if not body:
                continue
            nl, imap = norm_with_map(body)
            if len(nl) < 12:
                continue
            taken = [False] * len(nl)
            spans = []
            for s in ordered:
                pos = 0
                while True:
                    j = nl.find(s, pos)
                    if j < 0:
                        break
                    end = j + len(s)
                    if not any(taken[j:end]):
                        for k in range(j, end):
                            taken[k] = True
                        spans.append((j, end, s))
                    pos = j + 1
            if not spans:
                continue
            reps = []
            for j, end, s in spans:
                a = imap[j]
                b = imap[end - 1] + 1
                while b > a and (body[b - 1].isspace() or body[b - 1] == '　'):
                    b -= 1
                while a < b and (body[a].isspace() or body[a] == '　'):
                    a += 1
                if a >= b:
                    continue
                reps.append((a, b, s))
            new_body = body
            for a, b, s in reversed(reps):
                desc = ('<会议原句 len=%d sha256=%s>'
                        % (len(s), hashlib.sha256(s.encode('utf-8')).hexdigest()[:8]))
                new_body = new_body[:a] + desc + new_body[b:]
                n_fix += 1
            lines[i] = new_body + term

        data = ''.join(lines).encode('utf-8')
        if n_fix == 0:
            log('  [无改动] %s' % rel)
            continue

        b_crlf, b_lf = eol(before)
        a_crlf, a_lf = eol(data)
        assert (b_crlf > 0) == (a_crlf > 0) and (b_lf > 0) == (a_lf > 0), \
            '行尾风格变了：%s' % rel
        assert a_crlf == 0 or a_lf == 0, '混入另一种行尾：%s' % rel
        assert len(data.decode('utf-8').splitlines()) == len(text.splitlines()), \
            '行数变了：%s' % rel
        if rel.endswith('.json'):
            json.loads(data.decode('utf-8'))

        tmp = p + '.tmp_app249'
        with io.open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, p)
        assert open(p, 'rb').read() == data, '写后逐字节复核失败：%s' % rel
        log('  [清] %-52s %d 处' % (rel, n_fix))

    print('\n=== 终检：目标文件里 GT 原句残留 ===')
    bad = 0
    for rel in TARGETS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        n = norm(t)
        hits = [s for s in ordered if s in n]
        if hits:
            bad += len(hits)
            log('  🔴 %s：%d 句残留 例 %r' % (rel, len(hits), hits[0][:50]))
        else:
            log('  ✔ %s：0' % rel)
    log('\n残留合计：%d' % bad)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
