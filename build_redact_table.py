r"""build_redact_table.py —— 生成 git-filter-repo 的 `--replace-text` 脱敏表（APP-006 第 2 步）。

目的
----
把「内部会议转写原文」从 git **全部历史**里替换掉，同时**保留数值骨架**
（WER / RTF / 时间轴 / 段数 / 文件结构），让 ASR 基线数据仍可追溯。

判定与替换口径
--------------
**A. 会议原文句子**（主体）
    从历史全部 blob 里定位「会议原文载体」文件：
      - `reports/**/transcript_*.txt`      定稿转写文本（`[start-end] 正文`）
      - `reports/**/segments_*.json`       逐句分段（`text` 字段）
      - `reports/cuda*/logs_stream/*.stdout`  流式日志里的逐段文本
      - `results/c134_replay/*.txt`        回放产物（定稿原文 / 译文）
      - `reports/**/spe_*.txt` / `*_offline*.txt`  离线转写文本
    从这些文件里抽出**句子**，去重、单行化，写成 `原文==>[REDACTED]`。

**B. 路径 / 示例字符串**（次要）
    `test_audio/<音频编号>_SPE_audio.wav` → `test_audio/<redacted>.wav`
    `<音频编号>_SPE_audio.wav`         → `<redacted>.wav`
    `<音频编号>_SPE`                  → `<redacted>`
    `our <规格> <代号>`              → `[REDACTED]`
    `<会议代号>`                        → `[REDACTED]`（大小写敏感变体也入表）

**不动的文件**（用户决策：保留数值型 summary.json）
    `summary.json` / `benchmark*.csv` / `*.md` 报告里的**纯数值**部分不动；
    只有含会议原文的载体文件才进替换表。

⚠️ **原文不出现在本脚本的输出里**（表文件本身在仓库外，且已 .gitignore）。
⚠️ 表文件**必须单行**（filter-repo 的 replace-text 是逐行精确匹配）。

用法
----
    python build_redact_table.py --repo . --out C:/Users/Trekker-PTL/git_backup/replace_text_c135.txt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# ── 会议原文载体文件的判定（相对仓库根，正则）─────────────────────────
CARRIER_PATTERNS = [
    re.compile(r'^reports/.*/transcript_.*\.txt$'),
    re.compile(r'^reports/.*/segments_.*\.json$'),
    re.compile(r'^reports/cuda[^/]*/logs_stream/.*\.stdout$'),
    re.compile(r'^results/c134_replay/.*\.txt$'),
    re.compile(r'^reports/.*/spe_.*\.txt$'),
    re.compile(r'^reports/.*/.*_offline.*\.txt$'),
    re.compile(r'^reports/.*/.*_stream\.txt$'),
]

# ── 路径 / 示例字符串的定点替换 ───────────────────────────────────────
LITERAL_REPLACEMENTS = [
    ('test_audio/' + '2609' + '02_SPE_audio.wav', 'test_audio/<redacted>.wav'),
    ('2609' + '02_SPE_audio.wav', '<redacted>.wav'),
    ('2609' + '02_SPE', '<redacted>'),
    ('our ' + '[REDACTED]', '[REDACTED]'),
    ('our ' + '52' + ' core', '[REDACTED]'),
    ('52' + ' core bl' + 'c b0', '[REDACTED]'),
]

# ── 关键词（大小写不敏感 ⇒ 生成所有实际出现的变体）────────────────────
KEYWORDS = ['Q' + 'GS', 'bl' + 'c b0', '52' + ' core']

# ── 句子切分 ──────────────────────────────────────────────────────────
# 会议转写里句子以 . ! ? ; 结束，或以换行结束。
SENT_SPLIT_RE = re.compile(r'(?<=[.!?;])\s+')

# 时间戳前缀 `[   0.0-   13.7] `
TS_PREFIX_RE = re.compile(r'^\s*\[\s*[\d.]+\s*-\s*[\d.]+\s*\]\s*')

# segments_*.json 里的 text 字段
JSON_TEXT_RE = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"')

MIN_SENT_LEN = 25          # 太短的片段容易误伤通用文本
MAX_SENT_LEN = 2000


def is_carrier(rel: str) -> bool:
    return any(p.match(rel) for p in CARRIER_PATTERNS)


def norm_line(s: str) -> str:
    """去掉时间戳前缀，统一空白。"""
    s = TS_PREFIX_RE.sub('', s)
    return re.sub(r'\s+', ' ', s).strip()


def extract_sentences(text: str):
    """从一段文本里抽句子（去时间戳前缀、切句、去重、过滤长度）。"""
    out = []
    for raw in text.splitlines():
        line = norm_line(raw)
        if not line:
            continue
        for piece in SENT_SPLIT_RE.split(line):
            piece = piece.strip()
            if len(piece) < MIN_SENT_LEN or len(piece) > MAX_SENT_LEN:
                continue
            out.append(piece)
    return out


def collect_blobs(repo: str, verbose=False):
    """遍历所有历史 commit 的所有 blob，返回 {relpath: [内容]} 的去重集合。

    ⚠️ 只取**当前 HEAD 可达**的历史 + `--all` 的所有 ref。
    """
    # 1) 列出历史上出现过的所有路径
    r = subprocess.run(['git', '-C', repo, 'log', '--all', '--name-only',
                        '--pretty=format:'], capture_output=True, timeout=600)
    paths = set()
    for line in r.stdout.decode('utf-8', errors='replace').splitlines():
        p = line.strip()
        if p:
            paths.add(p.replace('\\', '/'))
    if verbose:
        print(f'历史上出现过的路径数: {len(paths)}')

    carriers = sorted(p for p in paths if is_carrier(p))
    if verbose:
        print(f'会议原文载体文件数: {len(carriers)}')
    return carriers


def read_blob_at_all_commits(repo: str, rel: str, verbose=False):
    """读某个路径在**所有历史 commit** 里的内容（去重）。"""
    contents = []
    seen = set()
    r = subprocess.run(['git', '-C', repo, 'log', '--all', '--format=%H',
                        '--', rel], capture_output=True, timeout=600)
    revs = r.stdout.decode('utf-8', errors='replace').split()
    for rev in revs:
        b = subprocess.run(['git', '-C', repo, 'show', f'{rev}:{rel}'],
                           capture_output=True)
        if b.returncode != 0:
            continue
        h = hash(b.stdout)
        if h in seen:
            continue
        seen.add(h)
        contents.append(b.stdout.decode('utf-8', errors='replace'))
    return contents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--out', default=r'C:\Users\Trekker-PTL\git_backup\replace_text_c135.txt')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)

    print('=== 1) 定位会议原文载体文件 ===', flush=True)
    carriers = collect_blobs(repo, args.verbose)

    print('=== 2) 抽取会议原文句子 ===', flush=True)
    sentences = {}
    n_files = 0
    for rel in carriers:
        for content in read_blob_at_all_commits(repo, rel):
            n_files += 1
            if rel.endswith('.json'):
                for m in JSON_TEXT_RE.finditer(content):
                    s = m.group(1)
                    s = s.encode().decode('unicode_escape', errors='ignore')
                    s = norm_line(s)
                    if MIN_SENT_LEN <= len(s) <= MAX_SENT_LEN:
                        sentences[s] = sentences.get(s, 0) + 1
            else:
                for s in extract_sentences(content):
                    sentences[s] = sentences.get(s, 0) + 1
    print(f'  扫过 {n_files} 个历史版本，抽出 {len(sentences)} 条去重句子', flush=True)

    print('=== 3) 收集关键词变体 ===', flush=True)
    kw_variants = {}
    # ⚠️ `git grep` **没有** `--all` 选项 ⇒ 之前这里拿到 0 种。
    #    正确做法：对每个 ref 分别 grep（`--all-match` 也与本意不符）。
    refs = subprocess.run(['git', '-C', repo, 'for-each-ref',
                            '--format=%(refname)', 'refs/heads', 'refs/tags',
                            'refs/remotes'],
                           capture_output=True, timeout=120)
    ref_list = [r for r in refs.stdout.decode('utf-8', errors='replace').splitlines()
                if r.strip()]
    # 另外把「历史上出现过的所有 commit」也纳入（用 --all 的等价写法）
    revs = subprocess.run(['git', '-C', repo, 'rev-list', '--all'],
                          capture_output=True, timeout=300)
    rev_list = revs.stdout.decode('utf-8', errors='replace').split()
    pat = '|'.join(re.escape(k) for k in KEYWORDS)
    for rev in rev_list:
        r = subprocess.run(['git', '-C', repo, 'grep', '-oh', '-i', '-E', pat, rev],
                           capture_output=True, timeout=300)
        for tok in r.stdout.decode('utf-8', errors='replace').split('\n'):
            tok = tok.strip()
            if tok:
                kw_variants[tok] = kw_variants.get(tok, 0) + 1
    print(f'  关键词变体 {len(kw_variants)} 种（扫过 {len(rev_list)} 个 commit，'
          f'{len(ref_list)} 个 ref）', flush=True)

    print('=== 4) 生成替换表 ===', flush=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    lines = []
    # 长句优先（filter-repo 逐行精确匹配，长句含短句时先替换长的更稳）
    for s in sorted(sentences, key=len, reverse=True):
        lines.append(f'{s}=>[REDACTED]')
    for old, new in LITERAL_REPLACEMENTS:
        lines.append(f'{old}=>{new}')
    for tok in sorted(kw_variants, key=len, reverse=True):
        if tok in ('Q' + 'GS', 'qg' + 's', 'Q' + 'gs'):
            lines.append(f'{tok}=>[REDACTED]')
        else:
            lines.append(f'{tok}=>[REDACTED]')
    # 去重（保持顺序）
    seen = set()
    uniq = []
    for ln in lines:
        if ln in seen:
            continue
        seen.add(ln)
        uniq.append(ln)

    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(uniq))
        f.write('\n')

    print(f'  替换表已写入: {args.out}')
    print(f'  条目数: {len(uniq)}')
    print(f'  文件大小: {os.path.getsize(args.out):,} bytes')
    # 统计摘要（不含原文）
    print()
    print('摘要:')
    print(f'  会议原文句子 : {len(sentences)} 条')
    print(f'  路径/示例替换: {len(LITERAL_REPLACEMENTS)} 条')
    print(f'  关键词变体   : {len(kw_variants)} 种')
    print(f'  载体文件数   : {len(carriers)}')
    print()
    print('⚠️ 替换表含会议原文，**必须留在仓库外**（已在 .gitignore 的仓库外目录）')
    print('⚠️ 执行改写前请先让 reviewer 复核 §11.2 的清单（APP-006 第 2 步要求）')

    # 清单另存（不含原文，可进 STATUS）
    manifest = {
        'carrier_files': carriers,
        'sentence_count': len(sentences),
        'literal_count': len(LITERAL_REPLACEMENTS),
        'keyword_variants': sorted(kw_variants),
        'table_entries': len(uniq),
    }
    mpath = os.path.join(os.path.dirname(args.out), 'redact_manifest_c135.json')
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'清单（不含原文）已写入: {mpath}')


if __name__ == '__main__':
    sys.exit(main())
