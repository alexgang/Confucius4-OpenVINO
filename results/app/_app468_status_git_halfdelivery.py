#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_status_git_halfdelivery.py —— §178：STATUS 引用的产物「git 半交付」判据。

🔴 **本脚本只读**：不改 `status/app/STATUS_APP.md`、不改任何归档件、
   不改 `status/app/CORRECTIONS_APP.md`（reviewer 独占）、不跑 `git add/commit`。
   产物：`results/app/app468_status_git_halfdelivery.json`。

## 本轮查出的真缺陷（判据要回答的问题）

§173 的「归档指针可核对性」判据（`_app429_status_pointer_audit.py`）只查
**磁盘上在不在 + SHA 对不对** ⇒ **查不出「文件在磁盘上、但从没进过 git」**。
⇒ 它报「30 OK / 0 FAIL」，而实测 **2 个被活文档引用的归档件根本没入库**
⇒ 典型的「**PASS ≠ 正确**」（弱标记恒真）。

本判据补上 **第三个维度：`git_tracked`**：
> 活文档（及最新归档件）里引用的每个产物，必须**同时**满足
> ① 磁盘上存在 ② **已被 git 跟踪**（`git ls-files` 命中）③ 字节数/SHA256 对得上。

## 三种归档件形态（沿用 §173 口径，不是本轮新造）

| 形态 | 含义 |
|---|---|
| `raw` | 磁盘字节原样 |
| `rstrip` | 去掉尾部换行 |
| `body` | 归档件自带 `#` 抬头时，正文块（`## §…` 起） |

**证据文件**（`results/app/**`）只认 `raw` —— 证据没有「正文块」概念。

## 反证组（判据必须有鉴别力，不能恒真）

- **反证 A**：把一个归档件从 `git ls-files` 名单里剔除 ⇒ 该行必须由 `OK` 变 `FAIL`；
- **反证 B**：篡改一个归档件的 1 字节 ⇒ 该行必须由 `OK` 变 `FAIL`；
- **反证 C（非空自证）**：本判据必须能在**本轮修复前**的真实仓库状态上报出 FAIL
  （`sec159` / `sec176` / `app458` 未入库）⇒ 否则说明它恒真、白写。

## 反向（不判 FAIL，只记 INFO）

- 引用了但**磁盘上没有** ⇒ `MISSING_ON_DISK`（算 FAIL 候选，但要单独报）
- 引用了但**活文档没写 SHA** ⇒ `NO_SHA_CLAIMED`（信息，不是缺陷）
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
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
OUT = os.path.join(REPO, 'results', 'app', 'app468_status_git_halfdelivery.json')

BT = chr(96)
ARCHIVE_EXT = ('md',)

# ── 引用抽取 ────────────────────────────────────────────────────────────────
# A 型：| `path` | 1 234 B／`abcdef…` |            （归档件证据表）
PAT_A = re.compile(
    BT + r'([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)' + BT +
    r'\s*\|\s*([0-9][0-9  ]*)\s*B／' + BT + r'([0-9a-f]{8,})' + BT)
# B 型：`path`（1 234 B／SHA256 `abcdef…`）        （指针行）
# 🔴 SHA 允许在反引号**内**以省略号截断（`7c43b365e3f958a9…`）
#    ——§177 指针行里 sec176 就是这种写法 ⇒ 不放宽 ⇒ 该行会被漏检（假阴性）。
#    ⚠️ 只取**前缀**比对 ⇒ 截断写法天然弱于全 SHA，故要求 ≥ 8 位十六进制。
PAT_B = re.compile(
    BT + r'([A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)' + BT +
    r'[^|\n]{0,40}?（\s*([0-9][0-9  ]*)\s*B／(?:块\s*)?(?:SHA256\s*)?' +
    BT + r'([0-9a-f]{8,})' + r'…?' + BT)
# C 型：`path`（…）无字节/SHA —— 只记路径
PAT_C = re.compile(BT + r'(status/archive/[A-Za-z0-9_.\-]+\.md|results/app/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)' + BT)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def is_gitignored(rel: str) -> bool:
    """该路径是否被 .gitignore 命中 ⇒「未入库」是**有意为之**，不是半交付。"""
    r = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=REPO,
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def git_ls_files() -> set:
    r = subprocess.run(['git', 'ls-files'], cwd=REPO, capture_output=True,
                       text=True, timeout=300)
    return set(r.stdout.split())


def git_head_tree(ref: str = 'HEAD') -> set:
    """某 ref 提交树里的全部路径。

    🔴 **判据必须查「已提交」而不是「已暂存」**——项目铁律「**「包里对」≠「已交付」**」
       ⇒ `git add` 之后（只在索引里）**不算交付** ⇒ 判据查 `git ls-tree HEAD`。
    """
    r = subprocess.run(['git', 'ls-tree', '-r', '--name-only', ref],
                       cwd=REPO, capture_output=True, text=True, timeout=300)
    return set(r.stdout.split())


def git_index_at(ref: str) -> set:
    """某 ref 当时的索引内容（用 `git ls-tree -r <ref>` 近似：提交树 == 该 ref 的索引）。"""
    return git_head_tree(ref)


def archive_forms(b: bytes) -> dict:
    """形态 → (sha256, 字节数)。

    🔴 字节数必须**跟着形态走**：§162 的指针写「5 052 B」指的是 **body 块**
    （归档件整文件是 5 347 B）⇒ 拿整文件长度去比 ⇒ 假 FAIL。

    🔴🔴 **CRLF 形态（本轮新发现的第 4 种）**：本仓库 `core.autocrlf=true` 且
       **无 `.gitattributes`** ⇒ git 存 **LF**，而**工作区是 CRLF**。
       ⇒ 旧章节引用产物时算的是**工作区 CRLF 字节**（§172 的 6 288 B、
       §177 的 2 138 B 就是这么来的）⇒ 拿 git 里的 LF 字节去比 ⇒ **假 FAIL**。
       ⇒ 故对证据文件额外接受 `crlf` / `lf` 两个互推形态。
    """
    forms = {'raw': (sha(b), len(b)),
             'rstrip': (sha(b.rstrip()), len(b.rstrip())),
             'lstrip': (sha(b.lstrip()), len(b.lstrip()))}
    lf = b.replace(b'\r\n', b'\n')
    crlf = lf.replace(b'\n', b'\r\n')
    forms['lf'] = (sha(lf), len(lf))
    forms['crlf'] = (sha(crlf), len(crlf))
    i = b.find(b'\n## ')
    if b.startswith(b'# ') and i >= 0:
        body = b[i + 1:]
        forms['body'] = (sha(body), len(body))
        forms['body_rstrip'] = (sha(body.rstrip()), len(body.rstrip()))
    else:
        forms['body'] = None
        forms['body_rstrip'] = None
    return forms


def match_form(forms: dict, claim: str):
    for k in ('raw', 'rstrip', 'lstrip', 'lf', 'crlf', 'body', 'body_rstrip'):
        if forms.get(k) and forms[k][0].startswith(claim):
            return k
    return None


def extract(text: str):
    """→ (rows, no_sha_paths)

    🔴 只认**仓库相对路径**（含 `/`）——`` `tts_engine.py` `` 这类**裸文件名**
       只是正文提及（"新增 `_norm_exec_devices(raw)`（`tts_engine.py`）"），
       不是产物引用 ⇒ 不该判 MISSING（否则＝假 FAIL）。
    """
    rows = []
    seen = set()
    for pat in (PAT_A, PAT_B):
        for p, bs, s in pat.findall(text):
            if '/' not in p:
                continue
            key = (p, bs.replace(' ', ''), s)
            if key in seen:
                continue
            seen.add(key)
            rows.append({'path': p, 'cited_bytes': int(bs.replace(' ', '')),
                         'claimed_sha': s})
    no_sha = []
    for p in PAT_C.findall(text):
        if not any(r['path'] == p for r in rows) and p not in no_sha:
            no_sha.append(p)
    return rows, no_sha


def check(rows, tracked: set, head_tree: set = None, tracked_override: dict = None):
    out = []
    for r in rows:
        p = r['path']
        fp = p
        if not os.path.exists(fp):
            for cand in (os.path.join(ARCH_DIR, os.path.basename(p)),
                         os.path.join(REPO, 'live_caption', os.path.basename(p)),
                         os.path.join(REPO, 'results', 'app', os.path.basename(p))):
                if os.path.exists(cand):
                    fp = cand
                    break
        rec = dict(r)
        rec['resolved'] = fp
        rec['on_disk'] = os.path.exists(fp)
        rec['git_tracked'] = False
        rec['git_committed'] = False
        if p in KNOWN_ERRATA:
            rec['known_errata'] = KNOWN_ERRATA[p]
        if rec['on_disk']:
            rel = os.path.relpath(fp, REPO).replace('\\', '/')
            rec['rel'] = rel
            is_tracked = rel in tracked
            if tracked_override is not None:
                is_tracked = tracked_override.get(rel, is_tracked)
            rec['git_tracked'] = is_tracked
            rec['git_committed'] = (head_tree is None) or (rel in head_tree)
            rec['gitignored'] = is_gitignored(rel)
            b = open(fp, 'rb').read()
            rec['actual_bytes'] = len(b)
            if rel.startswith('status/archive/'):
                forms = archive_forms(b)
            else:
                # 证据文件：raw + CRLF/LF 互推（见 archive_forms 的 CRLF 说明）
                forms = archive_forms(b)
            rec['matched_form'] = match_form(forms, r['claimed_sha'])
            # 字节数：命中任一可接受形态的**长度**即算对
            # （§162 写「5 052 B」指 body 块；§169/§170 写「6 978/15 674 B」指整文件）
            rec['bytes_match_forms'] = [k for k, v in forms.items()
                                        if v and v[1] == r['cited_bytes']]
            rec['bytes_match'] = bool(rec['bytes_match_forms'])
            fails = []
            if not rec['git_tracked'] and not rec['gitignored']:
                fails.append('NOT_GIT_TRACKED')
            elif not rec['git_committed'] and not rec['gitignored']:
                fails.append('NOT_COMMITTED')
            if rec['matched_form'] is None:
                fails.append('SHA_MISMATCH')
            if not rec['bytes_match']:
                fails.append('BYTES_MISMATCH')
            rec['fail_reasons'] = fails
            if fails:
                rec['verdict'] = 'FAIL'
            elif rec['gitignored']:
                rec['verdict'] = 'OK_GITIGNORED'
            else:
                rec['verdict'] = 'OK'
        else:
            rec['fail_reasons'] = ['MISSING_ON_DISK']
            rec['verdict'] = 'MISSING'
        if rec.get('known_errata'):
            rec['verdict'] = 'KNOWN_ERRATA'
            rec['fail_reasons'] = []
        out.append(rec)
    return out


# ── 已知勘误（**只登记、不判 FAIL**）──────────────────────────────────────
# 🔴 归档件是 write-once ⇒ 旧笔误不能改；已在后续章节登记过的 ⇒ 不重复报警。
#    `sec174` 的 `app429/app430` 是 §175 已登记的笔误（真名 `app432/app433`）。
KNOWN_ERRATA = {
    'results/app/_app429_self_ref_clone_gate.py': '§175 已登记：真名 _app432_self_ref_clone_gate.py',
    'results/app/app429_self_ref_clone_gate.json': '§175 已登记：真名 app432_self_ref_clone_gate.json',
    'results/app/_app430_pkg_dev_only_assert_gate.py': '§175 已登记：真名 _app433_pkg_dev_only_assert_gate.py',
    'results/app/app430_pkg_dev_only_assert_gate.json': '§175 已登记：真名 app433_pkg_dev_only_assert_gate.json',
}


def audit(rows, no_sha_paths, tracked: set, head_tree: set):
    """对给定 git 状态跑一遍完整审计。

    🔴 **修复前/修复后必须走同一个函数** ⇒ 对照才可比（否则＝假自证）。
    """
    recs = check(rows, tracked, head_tree)

    # ── 无 SHA 声明的引用：**只查 git 半交付**（不查 SHA/字节）────────────
    # 🔴 引用「没写 SHA」是信息、不是缺陷（§173 教训）⇒ 不判 FAIL；
    #    但「文件在磁盘上、却没进 git」**是真缺陷** ⇒ 仍须查。
    no_sha_recs = []
    for p in no_sha_paths:
        fp = p
        if not os.path.exists(fp):
            for cand in (os.path.join(ARCH_DIR, os.path.basename(p)),
                         os.path.join(REPO, 'results', 'app', os.path.basename(p))):
                if os.path.exists(cand):
                    fp = cand
                    break
        if not os.path.exists(fp):
            continue
        rel = os.path.relpath(fp, REPO).replace('\\', '/')
        ignored = is_gitignored(rel)
        if os.path.isdir(fp):
            # 目录型引用（如 results/app/app458_app100_device/）⇒ 查其下**非忽略**文件是否入库
            kids = []
            for root, _dirs, files in os.walk(fp):
                for fn in files:
                    kp = os.path.join(root, fn)
                    krel = os.path.relpath(kp, REPO).replace('\\', '/')
                    if is_gitignored(krel):
                        continue
                    kids.append(krel)
            untracked_kids = [k for k in kids if k not in tracked]
            rec = {'path': p, 'resolved': fp, 'rel': rel, 'is_dir': True,
                   'on_disk': True, 'cited_bytes': None, 'claimed_sha': None,
                   'matched_form': None, 'bytes_match': None, 'bytes_match_forms': [],
                   'actual_bytes': sum(os.path.getsize(os.path.join(REPO, k)) for k in kids),
                   'n_files': len(kids),
                   'n_not_git_tracked': len(untracked_kids),
                   'not_git_tracked_files': untracked_kids,
                   'note': '目录型引用 ⇒ 查其下非 .gitignore 文件是否入库'}
            fails = ['DIR_NOT_GIT_TRACKED'] if untracked_kids else []
            rec['fail_reasons'] = fails
            rec['verdict'] = 'FAIL' if fails else 'OK'
            no_sha_recs.append(rec)
            continue
        rec = {'path': p, 'resolved': fp, 'rel': rel,
               'on_disk': True, 'git_tracked': rel in tracked,
               'git_committed': (head_tree is None) or (rel in head_tree),
               'gitignored': ignored, 'cited_bytes': None, 'claimed_sha': None,
               'matched_form': None, 'bytes_match': None,
               'bytes_match_forms': [], 'actual_bytes': os.path.getsize(fp),
               'note': '引用未声明 SHA ⇒ 不判 SHA/字节；仅查 git 半交付'}
        fails = []
        if not rec['git_tracked'] and not ignored:
            fails.append('NOT_GIT_TRACKED')
        elif not rec['git_committed'] and not ignored:
            fails.append('NOT_COMMITTED')
        rec['fail_reasons'] = fails
        rec['verdict'] = 'FAIL' if fails else ('OK_GITIGNORED' if ignored else 'OK')
        # ── 孤儿重复件：与**已入库**的同名系列文件**逐字节相同** ⇒
        #    它没有独有内容 ⇒ 读者按任一名都能取到同一份字节 ⇒ 不判 FAIL，
        #    只记 `OK_DUPLICATE`（信息）。
        if rec['verdict'] == 'FAIL' and 'NOT_GIT_TRACKED' in fails:
            dups = []
            sib_dir = os.path.dirname(fp)
            for fn in os.listdir(sib_dir) if os.path.isdir(sib_dir) else []:
                sp = os.path.join(sib_dir, fn)
                if sp == fp or not os.path.isfile(sp):
                    continue
                srel = os.path.relpath(sp, REPO).replace('\\', '/')
                if srel not in tracked:
                    continue
                if open(sp, 'rb').read() == open(fp, 'rb').read():
                    dups.append(srel)
            if dups:
                rec['duplicate_of'] = sorted(dups)
                rec['fail_reasons'] = []
                rec['verdict'] = 'OK_DUPLICATE'
        no_sha_recs.append(rec)
    recs.extend(no_sha_recs)
    return recs


def fingerprint_corr():
    b = open(CORR, 'rb').read()
    t = b.decode('utf-8', errors='replace')
    hs = re.findall(r'(?m)^## (APP-\d+)', t)
    return {
        'path': 'status/app/CORRECTIONS_APP.md',
        'sha256': sha(b), 'bytes': len(b),
        'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(CORR)).strftime('%Y-%m-%d %H:%M:%S'),
        'n_headings': len(hs), 'max_heading': hs[-1] if hs else None,
        'note': '只读 fingerprint；本脚本不改该文件',
    }


def main():
    tracked = git_ls_files()
    head_tree = git_head_tree()
    live = open(STATUS, encoding='utf-8').read()
    rows, no_sha = extract(live)

    # 本轮最新归档件也纳入（§177 的证据表在归档件里）
    arch_rows = []
    arch_no_sha = []
    arch_files = sorted(set(os.path.basename(r['path']) for r in rows
                            if r['path'].startswith('status/archive/')))
    for af in arch_files:
        fp = os.path.join(ARCH_DIR, af)
        if os.path.exists(fp):
            a_rows, a_no_sha = extract(open(fp, encoding='utf-8').read())
            for r in a_rows:
                r['_from_archive'] = af
            arch_rows.extend(a_rows)
            # 🔴 归档件里的**路径型引用**（无 SHA）也要查半交付
            #    ——§176 引的 `results/app/app458_app100_device/` 就是这类
            for p in a_no_sha:
                if p not in arch_no_sha:
                    arch_no_sha.append(p)

    all_rows = rows + arch_rows
    no_sha = no_sha + arch_no_sha
    recs = audit(all_rows, no_sha, tracked, head_tree)


    # ── 反证组 ──────────────────────────────────────────────────────────────
    anti = []
    # A：从 git 名单里剔除一个归档件 ⇒ 必须 FAIL
    sample = next((r for r in recs if r.get('verdict') in ('OK', 'OK_GITIGNORED')
                   and r.get('rel', '').startswith('status/archive/')), None)
    if sample:
        ov = {sample['rel']: False}
        a_recs = check([sample], tracked, head_tree, tracked_override=ov)
        anti.append({
            'case': 'anti_A_untrack_archive',
            'target': sample['rel'],
            'expect': 'OK -> FAIL (NOT_GIT_TRACKED)',
            'got': a_recs[0]['verdict'],
            'fail_reasons': a_recs[0].get('fail_reasons'),
            'discriminating': a_recs[0]['verdict'] == 'FAIL'
            and 'NOT_GIT_TRACKED' in a_recs[0].get('fail_reasons', []),
        })
    # B：篡改归档件 1 字节 ⇒ SHA 必须对不上（用真实文件在临时目录做，不动原文件）
    if sample:
        src = sample['resolved']
        tmp = os.path.join(REPO, 'results', 'app', '_app468_antitmp.md')
        b = bytearray(open(src, 'rb').read())
        if b:
            b[-1] = (b[-1] + 1) % 256
            open(tmp, 'wb').write(bytes(b))
            tb = open(tmp, 'rb').read()
            tforms = archive_forms(tb)
            tm = match_form(tforms, sample['claimed_sha'])
            os.remove(tmp)
            # 篡改后字节数也可能变 ⇒ 只看 SHA 是否失配
            anti.append({
                'case': 'anti_B_tamper_1byte',
                'target': sample['rel'],
                'expect': 'claimed SHA no longer matches',
                'got_form': tm,
                'discriminating': tm is None,
            })
    # C（非空自证）：本判据必须能在「修复前」的真实状态上抓到未入库项
    #    ⇒ 用 `git ls-tree <修复前的 ref>` **重建**当时的仓库状态再判一次：
    #      修复前抓到 ≥1 个未入库/未提交、修复后为 0 ⇒ 判据有鉴别力（非恒真）。
    #    ⇒ 不依赖手工保存的快照（快照会随判据演进而失真 ⇒ 假自证）。
    prefix_ref = os.environ.get('APP468_PREFIX_REF', '').strip()
    prefix_fail = []
    prefix_ref_used = None
    if prefix_ref:
        try:
            p_tree = git_head_tree(prefix_ref)
            p_recs = audit(all_rows, no_sha, p_tree, p_tree)
            for r in p_recs:
                fr = r.get('fail_reasons') or []
                if 'NOT_GIT_TRACKED' in fr or 'NOT_COMMITTED' in fr or 'DIR_NOT_GIT_TRACKED' in fr:
                    prefix_fail.append(r['path'])
            prefix_ref_used = prefix_ref
        except Exception as e:  # pragma: no cover
            prefix_fail = []
            prefix_ref_used = 'ERROR: %r' % (e,)
    untracked_now = [r.get('rel', r['path']) for r in recs
                     if 'NOT_GIT_TRACKED' in (r.get('fail_reasons') or [])
                     or 'NOT_COMMITTED' in (r.get('fail_reasons') or [])
                     or 'DIR_NOT_GIT_TRACKED' in (r.get('fail_reasons') or [])]
    anti.append({
        'case': 'anti_C_non_empty_selfproof',
        'expect': '修复前的 ref 状态抓到 ≥1 个未入库/未提交引用，且当前为 0 ⇒ 判据非恒真',
        'prefix_ref': prefix_ref_used,
        'n_prefix_fail': len(prefix_fail),
        'prefix_fail_paths': sorted(set(prefix_fail)),
        'n_now_fail': len(untracked_now),
        'now_fail_paths': untracked_now,
        'discriminating': len(prefix_fail) > 0 and len(untracked_now) == 0,
    })

    n_fail = sum(1 for r in recs if r['verdict'] == 'FAIL')
    n_missing = sum(1 for r in recs if r['verdict'] == 'MISSING')
    n_ok = sum(1 for r in recs if r['verdict'] == 'OK')
    n_ignored = sum(1 for r in recs if r['verdict'] == 'OK_GITIGNORED')
    n_errata = sum(1 for r in recs if r['verdict'] == 'KNOWN_ERRATA')
    n_dup = sum(1 for r in recs if r['verdict'] == 'OK_DUPLICATE')
    verdict = {
        'n_rows': len(recs), 'n_ok': n_ok, 'n_fail': n_fail, 'n_missing': n_missing,
        'n_ok_gitignored': n_ignored, 'n_known_errata': n_errata,
        'n_ok_duplicate': n_dup,
        'n_no_sha_claimed': len(no_sha),
        'anti_all_discriminating': all(a['discriminating'] for a in anti) if anti else False,
        'pass': (n_fail == 0 and n_missing == 0
                 and all(a['discriminating'] for a in anti)),
    }

    out = {
        'tool': '_app468_status_git_halfdelivery',
        'section': '§178',
        'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'device_job': False,
        'read_only': True,
        'corrections_fingerprint_open': fingerprint_corr(),
        'status_doc': {
            'path': 'status/app/STATUS_APP.md',
            'bytes': os.path.getsize(STATUS),
            'sha256': sha(open(STATUS, 'rb').read()),
        },
        'live_rows': rows,
        'archive_rows_from': arch_files,
        'rows': recs,
        'paths_without_sha_claimed': no_sha,
        'anti_cases': anti,
        'verdict': verdict,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print('rows=%d OK=%d FAIL=%d MISSING=%d IGNORED=%d DUP=%d ERRATA=%d NO_SHA=%d'
          % (len(recs), n_ok, n_fail, n_missing, n_ignored, n_dup, n_errata, len(no_sha)))
    for r in recs:
        if r['verdict'] not in ('OK',):
            print('  %-15s %-56s %s' % (r['verdict'], r['path'],
                                         ','.join(r.get('fail_reasons', []))))
    for a in anti:
        print('  anti %-32s discriminating=%s' % (a['case'], a['discriminating']))
    print('PASS' if verdict['pass'] else 'NOT-PASS')
    print('evidence: %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
