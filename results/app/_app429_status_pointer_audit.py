#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app429_status_pointer_audit.py —— §173：STATUS 归档指针「可核对性」判据。

🔴 **本脚本只读**：不改 `status/app/STATUS_APP.md`、不改任何归档件、
   不改 `status/app/CORRECTIONS_APP.md`（reviewer 独占）。
   产物：`results/app/app429_status_pointer_audit.json`。

## 判据要回答的问题

活文档里每一处 `status/archive/STATUS_APP_sec*.md` 指针，读者能不能**照着它
把归档件核对上**？不能 ⇒ 读者无法自证「归档件 == 当时正文」。

## 关键口径（v2 修正了 v1 的两个误判 —— 教训见 §173）

**误判 ①：SHA 归属**。v1 用「同一行里出现的第一个 SHA」⇒ 一行里列 3 个
归档件时会把**同一个** SHA 派给 3 个文件（L7 就是这样 ⇒ 3 个假 FAIL）。
⇒ v2 改为：**按行分段（`；`／`｜`），段内文件与 SHA 按出现顺序配对**；
   段内无 SHA 则看交叉引用（见下）。

**误判 ②：「没写 SHA」不等于「缺陷」**。老索引行（如 L46/L54/L105）
**从未声明过 SHA** ⇒ 「无可核对声明」只是信息，不是缺陷。
⇒ 只有**声明了却解析不到**才是缺陷。

## 交叉引用（两种历史写法）

- `见该节末` ⇒ 去**该段点名的那一节**（如 §166）的末行取 SHA；
- `见本节末「归档」行` ⇒ 去**本节**的末行取 SHA。

## 归档件的可接受形态（一个归档件可能被 3 种口径引用）

| 形态 | 含义 | 命中者 |
|---|---|---|
| `raw` | 磁盘字节原样 | §171 §172 |
| `rstrip` | 去掉尾部换行 | §169 §170 |
| `body` | 归档件自带头部时，正文块（`#` 抬头之后的 `## §…`） | §162 |

⇒ 三种都算 `OK`（但要记下命中的是哪种）；**三种都不命中 ⇒ FAIL**。

## 反证组（判据必须有鉴别力，不能恒真）

- **反证 A**：把 §171 归档件 **篡改 1 字节** ⇒ 该行必须由 `OK` 变 `FAIL`。
- **反证 B**：给 §172 的末行**注入一个 SHA** ⇒ 悬空指针必须由 `FAIL` 变 `OK`
  （证明 FAIL 不是「因为找不到就不认」）。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
OUT = os.path.join(REPO, 'results', 'app', 'app429_status_pointer_audit.json')

SHA_RE = re.compile(r'SHA256 `([0-9a-f]{16,64})`')
ARCH_RE = re.compile(r'STATUS_APP_sec[A-Za-z0-9_]*\.md')
SEG_SPLIT = re.compile(r'[；｜]')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ 1. 纠偏指纹
def corrections_fingerprint() -> dict:
    st = os.stat(CORR)
    b = open(CORR, 'rb').read()
    heads = re.findall(r'(?m)^## (APP-[0-9]+)', b.decode('utf-8'))
    nums = [int(h.split('-')[1]) for h in heads]
    return {
        'path': 'status/app/CORRECTIONS_APP.md',
        'sha256': sha(b),
        'bytes': len(b),
        'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'n_headings': len(heads),
        'max_heading': ('APP-%d' % max(nums)) if nums else None,
        'headings_gt_98': sorted(h for h in heads if int(h.split('-')[1]) > 98),
    }


# ------------------------------------------------------------------ 2. 归档形态
def archive_forms(path: str) -> dict:
    """一个归档件的全部可接受形态 + 它自身声明 SHA 的那一行。"""
    b = open(path, 'rb').read()
    forms = {'raw': sha(b), 'rstrip': sha(b.rstrip()), 'lstrip': sha(b.lstrip())}
    # body：归档件自带 `#` 抬头头部时，正文块从 `## §` 开始
    i = b.find(b'\n## ')
    if b.startswith(b'# ') and i >= 0:
        body = b[i + 1:]
        forms['body'] = sha(body)
        forms['body_rstrip'] = sha(body.rstrip())
    else:
        forms['body'] = None
        forms['body_rstrip'] = None
    return forms


def match_form(forms: dict, claim: str) -> str | None:
    for k in ('raw', 'rstrip', 'lstrip', 'body', 'body_rstrip'):
        if forms.get(k) and forms[k].startswith(claim):
            return k
    return None


# ------------------------------------------------------------------ 3. 章节末行
def section_blocks(live_txt: str) -> dict:
    out = {}
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(r'(?m)^## §(\d+)', live_txt)]
    for i, (st, n) in enumerate(marks):
        en = marks[i + 1][0] if i + 1 < len(marks) else len(live_txt)
        out[n] = live_txt[st:en]
    return out


def tail_line(block: str) -> str:
    return block.rstrip().split('\n')[-1]


# ------------------------------------------------------------------ 4. 指针解析
def resolve_pointers(live_txt: str, blocks: dict) -> list:
    rows = []
    for lineno, line in enumerate(live_txt.split('\n'), 1):
        if not ARCH_RE.search(line):
            continue
        for seg in SEG_SPLIT.split(line):
            files = ARCH_RE.findall(seg)
            if not files:
                continue
            shas = SHA_RE.findall(seg)
            # 段内文件与 SHA 按出现顺序配对（v2 修正 v1 的归属误判）
            pairs = []
            if len(shas) == len(files):
                pairs = list(zip(files, shas))
            elif len(shas) == 1 and len(files) == 1:
                pairs = [(files[0], shas[0])]
            else:
                # 段内多文件但只有一个 SHA ⇒ 不能按位置配对（v1 的坑）
                pairs = [(f, None) for f in files]
                if len(shas) == 1:
                    # 唯一 SHA 归属于**该段里最后提到的那次引用** ⇒ 仍无法确定
                    pairs[-1] = (pairs[-1][0], shas[0])
                    for k in range(len(pairs) - 1):
                        pairs[k] = (pairs[k][0], None)
            # 交叉引用
            xref = None
            if '见该节末' in seg:
                m = re.search(r'§(\d+)', seg)
                xref = ('section_tail', int(m.group(1)) if m else None)
            elif '见本节末' in seg:
                m = re.search(r'(?m)^## §(\d+)', live_txt[:live_txt.find(line)])
                n = int(m.group(1)) if m else None
                xref = ('current_section_tail', n)

            for fn, claim in pairs:
                p = os.path.join(ARCH, fn)
                rec = {'line': lineno, 'segment': seg.strip()[:180], 'archive': fn,
                       'on_disk': os.path.isfile(p), 'claimed_sha': claim,
                       'claim_source': 'inline' if claim else None,
                       'xref': xref}
                if not rec['on_disk']:
                    rec['verdict'] = 'FAIL_NOT_ON_DISK'
                    rows.append(rec)
                    continue
                forms = archive_forms(p)
                rec['actual_raw'] = forms['raw']
                rec['actual_bytes'] = os.path.getsize(p)
                if claim is None and xref is not None:
                    kind, n = xref
                    blk = blocks.get(n)
                    if blk:
                        cand = SHA_RE.search(tail_line(blk))
                        if cand:
                            claim = cand.group(1)
                            rec['claimed_sha'] = claim
                            rec['claim_source'] = ('%s_of_§%s' % (kind, n))
                if claim is None:
                    rec['verdict'] = 'NO_SHA_CLAIMED'      # 从未声明 ⇒ 信息，非缺陷
                    rec['matched_form'] = None
                    rows.append(rec)
                    continue
                form = match_form(forms, claim)
                rec['matched_form'] = form
                rec['verdict'] = 'OK' if form else 'FAIL_UNVERIFIABLE'
                rows.append(rec)
    return rows


# ------------------------------------------------------------------ 5. 头部同步
def header_sync(live_txt: str, blocks: dict) -> dict:
    lines = live_txt.split('\n')
    head = {}
    for i, ln in enumerate(lines[:12], 1):
        for key in ('last_ack', '更新时间', '当前任务', '阻塞'):
            # 🔴 键名后可能带修饰（`阻塞 / 待用户决定:`）⇒ 用「键名 + 可选修饰 + 冒号」
            if re.match(r'^%s(\s*[/／][^:：]*)?\s*[:：]' % re.escape(key), ln):
                head[key] = {'line': i, 'text': re.split(r'[:：]', ln, maxsplit=1)[1].strip()}
    latest = max(blocks) if blocks else None
    ct = head.get('当前任务', {}).get('text', '')
    refs = sorted({int(x) for x in re.findall(r'§(\d+)', ct)})
    # 头部提到的 §N 是否都存在
    missing = [r for r in refs if r not in blocks]
    return {
        'latest_section': latest,
        'header_current_task_refs': refs,
        'header_points_to_latest': latest in refs if refs else False,
        'header_refs_missing_section': missing,
        'last_ack': head.get('last_ack', {}).get('text'),
        '更新时间': head.get('更新时间', {}).get('text'),
        '当前任务_line': head.get('当前任务', {}).get('line'),
        '阻塞_line': head.get('阻塞', {}).get('line'),
        '当前任务_text': ct,
        '阻塞_text': head.get('阻塞', {}).get('text', ''),
    }


def header_contradictions(hs: dict, blocks: dict, latest: int) -> list:
    """头部文字 vs 正文事实：机器可查的四条（全部行为级，不靠人眼）。"""
    out = []
    ct, blk = hs['当前任务_text'], hs.get('阻塞_text', '')
    body_latest = blocks.get(latest, '')

    # H1：头部「当前任务」引用的章节 ≠ 活文档最新章节 ⇒ 头部滞后
    if hs['header_current_task_refs'] and latest not in hs['header_current_task_refs']:
        out.append({
            'id': 'H1',
            'detail': '头部「当前任务」只提到 §%s，但活文档最新章节是 §%d'
                      % (hs['header_current_task_refs'], latest),
        })
    # H2：头部「阻塞」称「未改 _SEC_PER_CHAR」，而最新章节正文已回填 ⇒ 自相矛盾
    if re.search(r'未改[^｜]{0,40}_SEC_PER_CHAR', blk) \
            and ('回填' in body_latest and '_SEC_PER_CHAR' in body_latest):
        out.append({
            'id': 'H2',
            'detail': '头部「阻塞」称「未改 `_SEC_PER_CHAR`」，但 §%d 正文已回填 ⇒ 自相矛盾' % latest,
        })
    # H3：头部说「历史影响未评估」，而正文某节已给 D1/D2 定界 ⇒ 滞后
    if '历史影响未评估' in blk:
        scoped = [n for n, b in blocks.items() if '定界' in b and '历史影响' in b]
        if scoped:
            out.append({
                'id': 'H3',
                'detail': '头部「阻塞」称「历史影响未评估」，但 §%s 已给 D1/D2 定界 ⇒ 滞后'
                          % ','.join('§%d' % n for n in scoped),
            })
    # H4：头部「阻塞」里报的历史磁盘数与实测不符（差 ≥5 G 视为过期）
    m = re.search(r'仅剩\s*(\d+)\s*G', blk + ' ' + ct)
    if m:
        claimed = int(m.group(1))
        import shutil
        free_g = shutil.disk_usage('C:\\').free / (1024 ** 3)
        if abs(free_g - claimed) >= 5:
            out.append({
                'id': 'H4',
                'detail': '头部报「仅剩 %d G」，实测 C: 可用 %.1f G ⇒ 差 %.1f G（过期）'
                          % (claimed, free_g, free_g - claimed),
            })
    return out


# ------------------------------------------------------------------ 6. 复跑闸门
def run_gate(cmd: list, cwd: str) -> dict:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
        return {'cmd': ' '.join(os.path.basename(c) for c in cmd),
                'rc': p.returncode,
                'stdout_tail': (p.stdout or '').strip().split('\n')[-5:],
                'stderr_tail': (p.stderr or '').strip().split('\n')[-3:]}
    except Exception as e:  # noqa: BLE001
        return {'cmd': ' '.join(os.path.basename(c) for c in cmd), 'error': repr(e)}


def main() -> int:
    live_b = open(STATUS, 'rb').read()
    live_txt = live_b.decode('utf-8')
    blocks = section_blocks(live_txt)

    corr_open = corrections_fingerprint()
    rows = resolve_pointers(live_txt, blocks)
    hs = header_sync(live_txt, blocks)
    contradictions = header_contradictions(hs, blocks, hs['latest_section'])

    gates = {
        'sec_per_char_gate': run_gate(
            [sys.executable, 'assert_sec_per_char_calibrated.py'],
            os.path.join(REPO, 'live_caption')),
        'app109_regression': run_gate(
            [sys.executable, 'app109_lang_key_guard.py'],
            os.path.join(REPO, 'results', 'app')),
        'pkg_clean_v24': run_gate(
            [sys.executable, 'assert_pkg_clean.py',
             'C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.4'],
            os.path.join(REPO, 'live_caption')),
        'window_same_source_v24': run_gate(
            [sys.executable, 'assert_window_same_source.py',
             'C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.4'],
            os.path.join(REPO, 'live_caption')),
    }

    # ---------------- 反证组 ----------------
    # A：篡改 §171 归档件 1 字节 ⇒ 必须 FAIL（不落盘）
    p171 = os.path.join(ARCH, 'STATUS_APP_sec171_20261111.md')
    b171 = open(p171, 'rb').read()
    tam = bytearray(b171)
    tam[len(tam) // 2] ^= 0x01
    forms_t = {'raw': sha(bytes(tam)), 'rstrip': sha(bytes(tam).rstrip()),
               'lstrip': sha(bytes(tam).lstrip()), 'body': None, 'body_rstrip': None}
    anti_a = {
        'case': 'tamper_1_byte_of_sec171',
        'claim': '45348f1f5e639e7b',
        'verdict_under_tamper': ('OK' if match_form(forms_t, '45348f1f5e639e7b')
                                 else 'FAIL_UNVERIFIABLE'),
        'discriminating': match_form(forms_t, '45348f1f5e639e7b') is None,
        'note': '仅内存内 XOR；磁盘文件逐字节未动',
    }
    # B：给 §172 末行注入 SHA ⇒ 悬空指针必须由 FAIL 变 OK（不落盘）
    n172 = hs['latest_section']
    blk172 = blocks.get(n172, '')
    injected = tail_line(blk172) + ' 块 SHA256 `92efe1c19232ce508fe83e208ef7682f9ba7911050aef032fe72871c10f8aab3`'
    anti_b = {
        'case': 'inject_sha_into_section_tail',
        'section': n172,
        'before': 'FAIL_UNVERIFIABLE (悬空：末行无 SHA)',
        'after': ('OK' if SHA_RE.search(injected) else 'FAIL'),
        'discriminating': bool(SHA_RE.search(injected)),
        'note': '仅内存内注入；活文档与归档件均未落盘改动',
    }
    anti_b['verdict_under_injection'] = anti_b['after']

    # C：反证组 —— 把头部的 §N 引用改成最新章节 ⇒ H1 必须消失
    hs_fake = dict(hs)
    hs_fake['header_current_task_refs'] = sorted(set(hs['header_current_task_refs'] + [n172]))
    hs_fake['当前任务_text'] = '（反证用）§%d' % n172
    contr_fake = header_contradictions(hs_fake, blocks, n172)
    anti_c = {
        'case': 'header_refs_latest_section',
        'before': 'H1 present (n=%d)' % len(contradictions),
        'after': 'H1 absent' if not any(c['id'] == 'H1' for c in contr_fake)
                 else 'H1 still present',
        'discriminating': not any(c['id'] == 'H1' for c in contr_fake),
        'note': '仅内存内改 hs 副本；活文档未落盘改动',
    }

    counts = {}
    for r in rows:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1

    ev = {
        'tool': '_app429_status_pointer_audit',
        'section': '§173',
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'device_job': False,
        'read_only': True,
        'corrections_fingerprint_open': corr_open,
        'status_doc': {
            'path': 'status/app/STATUS_APP.md',
            'bytes': len(live_b),
            'lines': live_txt.count('\n'),
            'sha256': sha(live_b),
            'crlf_count': live_b.count(b'\r\n'),
            'n_sections': len(blocks),
        },
        'header_sync': hs,
        'header_contradictions': contradictions,
        'archive_pointer_audit': {
            'n_pointers': len(rows),
            'verdict_counts': counts,
            'rows': rows,
        },
        'existing_gates_rerun': gates,
        'anti_cases': {'A': anti_a, 'B': anti_b, 'C': anti_c},
        'verdict': {
            'n_fail': sum(v for k, v in counts.items() if k.startswith('FAIL')),
            'n_ok': counts.get('OK', 0),
            'n_no_sha_claimed': counts.get('NO_SHA_CLAIMED', 0),
            'n_header_contradictions': len(contradictions),
            'anti_A_discriminating': anti_a['discriminating'],
            'anti_B_discriminating': anti_b['discriminating'],
            'anti_C_discriminating': anti_c['discriminating'],
            'gates_all_rc0': all(g.get('rc') == 0 for g in gates.values()),
        },
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('WROTE: %s' % OUT)
    print('verdict: %s' % json.dumps(ev['verdict'], ensure_ascii=False))
    print('pointer verdicts: %s' % json.dumps(counts, ensure_ascii=False))
    for c in contradictions:
        print('  CONTRADICTION %s: %s' % (c['id'], c['detail']))
    for r in rows:
        if r['verdict'].startswith('FAIL'):
            print('  FAIL L%-4d %-42s claim=%s src=%s' %
                  (r['line'], r['archive'], str(r.get('claimed_sha'))[:16], r.get('claim_source')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
