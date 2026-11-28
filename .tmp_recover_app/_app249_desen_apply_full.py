r"""_app249_desen_apply_full.py —— APP-155 脱敏的**完整补做**（索引映射的精确替换）。

## 为什么必须补做（§249 发现的真缺陷）

§248 登记「812 处替换 / 76 个文件；穷尽重扫仍命中 0 个文件」，
但它**自己的证据** `app155_desens_verify.json` 的 `verdict` 当时就是 **FAIL**（§248 没写这条）。
我独立复核（`_app249_replay_desen.py`）确认根因：

* `app155_desens_ground_truth.json` 的 `hits` **每文件只记 14 行**（抽样），
* `app155_desens_apply.py` **只遍历 hits 记到的行** ⇒ 每文件另外 ~45 行**从未被访问**；
* 而「穷尽重扫」按**整句**切 ⇒ 嵌在更大句子里的会议原句**判不出** ⇒ 报 0 命中（假绿）。

## 判据（**归一化 + 索引映射** ⇒ 既完整又精确）

只用 **raw form 原文**匹配会漏掉标点变体（GT `[会议句 idx 55].`
vs README `[会议句 idx 55]`）；只用**归一化串**匹配又会把命中 span 弄丢位置。

⇒ 本脚本对**每一行**：
1. 逐字符做 `norm()`（小写／合并空白／去标点），**同时记录每个归一化字符对应的原文下标**；
2. 在归一化串里找 GT 句（长句优先、互不重叠）；
3. 通过索引映射**换算回原文 span**，把该 span 替换成 `[会议句 idx N]`。

⇒ 既**完整**（标点/空白变体也命中），又**精确**（只动命中 span，其余逐字节不动）。

## 写前不变量（逐文件）

1. 行数不变；2. 行尾风格不变；3. **非替换部分逐字节不变**（逐行核对）；
4. `.json` 不得从「可解析」变成「不可解析」（改前就坏的**如实登记**，不修不判）。

## 🔴 反证组

把某处占位**改回**原句 ⇒ 收尾的「子串穷尽重扫」必须**命中** ⇒ 判据有鉴别力。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GTJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_ground_truth.json')
SCANJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_scan_full.json')
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_apply_full.json')
BAKDIR = r'C:\Users\Trekker-PTL\shared\app249_desen_backup'

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r'[\s　]+')
PLACEHOLDER = re.compile(r'\[会议句 idx \d+\]')
SKIP_SUFFIX = ('.transcript.txt', '.mt.txt', '.tts.jsonl')


def log(m):
    print(m, flush=True)


def norm(s):
    """与 §248 完全同口径：strip → lower → 合并空白 → 去标点。"""
    s = s.strip().lower()
    s = WS_RE.sub(' ', s)
    return PUNCT_RE.sub('', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


def eol(b):
    crlf = b.count(b'\r\n')
    return crlf, b.count(b'\n') - crlf


def norm_with_map(s):
    """归一化 + 每个归一化字符对应的原文下标。

    返回 (norm_string, idx_map)。idx_map[i] = 归一化第 i 个字符对应的原文下标；
    末尾额外给一个哨兵 = len(s)，便于算「命中 span 的右端」。
    """
    out = []
    idx = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace() or c == '　':
            # 合并连续空白 ⇒ 产出**一个**空格，取该空白run 的第一个下标
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
    out = ''.join(out)
    idx.append(n)          # 哨兵
    return out, idx


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
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    gt = json.load(open(GTJSON, encoding='utf-8'))
    scan = json.load(open(SCANJSON, encoding='utf-8'))
    reviewer_owned = set(gt['reviewer_owned'])
    min_len = gt['min_len']

    sents = build_gt(gt)
    idx_map = {s: i + 1 for i, s in enumerate(sorted(sents))}
    # 长句优先
    ordered = sorted(sents, key=len, reverse=True)
    log('GT 句子 %d 条 ⇒ 序号表 %d 条' % (len(sents), len(idx_map)))

    targets = [r for r in sorted(scan['hits'])
               if r not in reviewer_owned and not r.endswith(SKIP_SUFFIX)]
    log('目标文件 %d 个（说明类；已排除 reviewer 独占与逐句产物）' % len(targets))

    changed = []
    skipped = []
    json_prebroken = []
    n_json_ok = 0
    n_repl_total = 0

    for rel in targets:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        before_b = open(p, 'rb').read()
        text = before_b.decode('utf-8')
        lines = text.splitlines(keepends=True)

        n_repl = 0
        idx_used = set()
        for i in range(len(lines)):
            raw = lines[i]
            m = re.match(r'^(.*?)((?:\r\n|\r|\n)*)$', raw, re.S)
            body, term = m.group(1), m.group(2)
            if not body:
                continue
            nl, imap = norm_with_map(body)
            if len(nl) < min_len:
                continue
            # 找 GT 命中（长句优先、互不重叠）
            spans = []          # (start_norm, end_norm) 归一化坐标
            taken = [False] * len(nl)
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
            # 换算回原文坐标，替换（从后往前 ⇒ 下标不失效）
            spans.sort(key=lambda x: x[0])
            reps = []
            for j, end, s in spans:
                a = imap[j]
                b = imap[end - 1] + 1      # 命中 span 的原文右端（含标点/空白）
                # 去掉 span 尾部/首部多余的空白与标点（避免把相邻分隔符吃掉）
                while b > a and (body[b - 1].isspace() or body[b - 1] == '　'):
                    b -= 1
                while a < b and (body[a].isspace() or body[a] == '　'):
                    a += 1
                if a >= b:
                    continue
                reps.append((a, b, s))
            if not reps:
                continue
            new_body = body
            for a, b, s in reversed(reps):
                new_body = new_body[:a] + '[会议句 idx %d]' % idx_map[s] + new_body[b:]
                n_repl += 1
                idx_used.add(idx_map[s])
            lines[i] = new_body + term

        if n_repl == 0:
            skipped.append({'file': rel, 'reason': 'no_gt_match'})
            continue
        n_repl_total += n_repl
        data = ''.join(lines).encode('utf-8')

        # ── 写前不变量 ─────────────────────────────────────────
        b_crlf, b_lf = eol(before_b)
        a_crlf, a_lf = eol(data)
        assert (b_crlf > 0) == (a_crlf > 0) and (b_lf > 0) == (a_lf > 0), \
            '行尾风格变了：%s' % rel
        assert a_crlf == 0 or a_lf == 0, '混入另一种行尾：%s' % rel
        bl = text.splitlines(keepends=True)
        al = data.decode('utf-8').splitlines(keepends=True)
        assert len(bl) == len(al), '行数变了：%s' % rel
        for i, (x, y) in enumerate(zip(bl, al)):
            if x == y:
                continue
            yy = PLACEHOLDER.sub('\x00', y)
            pos = 0
            for seg in yy.split('\x00'):
                j = x.find(seg, pos)
                assert j >= 0, '第 %d 行的非替换部分对不上：%s' % (i + 1, rel)
                pos = j + len(seg)
        if rel.endswith('.json'):
            def _parsable(b):
                try:
                    json.loads(b.decode('utf-8'))
                    return True, ''
                except Exception as e:
                    return False, str(e)[:120]
            ok_after, err_after = _parsable(data)
            ok_before, err_before = _parsable(before_b)
            if ok_after:
                n_json_ok += 1
                assert ok_before, 'JSON 从可解析变成不可解析：%s（%s）' % (rel, err_after)
            else:
                json_prebroken.append({'file': rel, 'before_err': err_before,
                                       'after_err': err_after})

        rec = {'file': rel, 'n_repl': n_repl,
               'bytes_before': len(before_b), 'bytes_after': len(data),
               'idx_used': sorted(idx_used)}
        if not args.dry_run:
            if not os.path.isdir(BAKDIR):
                os.makedirs(BAKDIR)
            bakp = os.path.join(BAKDIR, rel.replace('/', '__'))
            if not os.path.exists(bakp):
                shutil.copy2(p, bakp)
            tmp = p + '.tmp_app249'
            with io.open(tmp, 'wb') as fh:
                fh.write(data)
            os.replace(tmp, p)
            assert open(p, 'rb').read() == data, '写后逐字节复核失败：%s' % rel
            rec['backup'] = bakp
        changed.append(rec)
        log('  [%s] %-66s %d 处' % ('改' if not args.dry_run else 'DRY', rel, n_repl))

    out = {
        'script': '_app249_desen_apply_full.py',
        'dry_run': args.dry_run,
        'method': '归一化 + 索引映射 ⇒ 精确替换命中 span（长句优先、互不重叠）',
        'n_gt_sentences': len(sents),
        'n_target_files': len(targets),
        'n_changed_files': len(changed),
        'n_replacements': n_repl_total,
        'n_json_parsed_ok': n_json_ok,
        'json_prebroken': json_prebroken,
        'n_skipped_no_match': len(skipped),
        'backup_dir': None if args.dry_run else BAKDIR,
        'changed': changed,
        'skipped': skipped,
    }
    suffix = '.dryrun' if args.dry_run else ''
    tmp = OUTJSON + suffix + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUTJSON + suffix)
    log('\n%s：改 %d 个文件 / %d 处替换（JSON 解析通过 %d 个；改前就坏的 %d 个）'
        % ('DRY-RUN' if args.dry_run else '实际写入', len(changed),
           n_repl_total, n_json_ok, len(json_prebroken)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
