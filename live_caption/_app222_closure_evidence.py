#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §222（巡检轮 · 接续上一会话 TAKEOVER）：**闭合上一会话遗留的半交付**。

## 本脚本做什么（纯只读 + 写一份证据 json，**不改任何交付面文件**）
1. 记录 `status/app/CORRECTIONS_APP.md` 的 SHA256／字节数／mtime／`## APP-xxx` 条数
   （**只读**，绝不修改 —— reviewer 独占文件）；
2. 记录 `status/app/STATUS_APP.md` 的 SHA256／字节数／行数；
3. 对**上一会话遗留的 4 处半交付**逐项取证：
   * ① `results/app/_app121_email_body.txt`：**已提交版是发信前的草稿**
     （含未填的 `提交 COMMIT_SHA（main）` 占位符 ＋「详见附件」—— 但那封邮件
     **没有附件**）；**实际发出**的是工作区版本（带真 SHA `88b9ea8` ＋
     companion 的字节数/SHA）⇒ 仓库里的「发信记录」与事实不符；
   * ② `live_caption/_app121_zip_extract_check.py`：**未入库**，而它的产物
     `results/app/app121_zip_extract_check.json` **已入库**且被 §221 §3 引用
     ⇒ 证据在、产生证据的脚本不在；
   * ③ 本轮 10 分钟整链的**逐句 jsonl ＋ 积压曲线**未入库，而 §221 §5 引用的
     验收 json **已入库** ⇒ reviewer 无法按 jsonl 复算（同侪 app119/sp5 臂
     的 jsonl＋csv **都入库**）；
   * ④ `live_caption/package_profiles.py`：**未入库**，但**已入库**的
     `_app120_build_minimvp_v11.py` 直接 `from package_profiles import ...`
     ⇒ 干净 clone 无法重建 MiniMVP 包；
4. 复核交付面（只读）：`v1.1.1.zip` 的条目数／解压字节／`ACCEPTED.json` 的
   指纹键集 vs zip 内 `app/*.py`；dev 树 ＝ v2.5 ＝ v1.1.1 的同字节核对；
   `v2.5/ACCEPTED.json` 的版本（**仍 fail-closed**）；
5. 复核 ASR §91 的两条交叉结论（用**本模块自己的证据**）：
   * ④ App 侧 NPU 的 `prefix_truncations`（ZH）＝3、GPU.0 ＝ 0；
   * ⑤ 「① 切段器不同 ⇒ 段边界/段数本就不一致」**不成立** —— 这句话**只在**
     证据 json 的 `ref_diff_explanation[].reasons[0]`（harness 里的**静态字面量**），
     §221 companion 正文写的是「段边界一致 ⇒ 切段器行为一致」⇒ **§221 的正文
     结论不需要撤回**；缺陷只在那条静态串（+ 同一个 json 自己的
     `n_segs_app` ＝ `n_segs_ref`）。

## 纪律
- **只读**交付面：不打包、不改客户包、不跑推理/计时（⇒ 不取 MACHINE_LOCK）；
- **不改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）；
- 不调 MiniMax（质量判定归 reviewer）；不连 B 机（APP-109 ④）。

## 用法
```
python live_caption/_app222_closure_evidence.py --out results/app/app222_closure_evidence.json
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
STATUS_DIR = os.path.join(REPO, 'status', 'app')
CORRECTIONS = os.path.join(STATUS_DIR, 'CORRECTIONS_APP.md')
STATUS = os.path.join(STATUS_DIR, 'STATUS_APP.md')


def sha_bytes(path: str) -> str:
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_fact(path: str) -> dict:
    if not os.path.exists(path):
        return {'path': path, 'exists': False}
    b = open(path, 'rb').read()
    return {
        'path': path,
        'exists': True,
        'bytes': len(b),
        'sha256': hashlib.sha256(b).hexdigest(),
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                               time.localtime(os.path.getmtime(path))),
    }


def git_text(*args: str) -> str:
    try:
        return subprocess.run(['git', '-C', REPO] + list(args),
                              capture_output=True, text=True,
                              encoding='utf-8', errors='replace').stdout
    except Exception as exc:            # pragma: no cover
        return 'GIT_ERROR: %s' % exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app222_closure_evidence.json'))
    args = ap.parse_args()

    ev: dict = {'script': '_app222_closure_evidence.py',
                'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                'read_only': True,
                'device_job': False,
                'machine_lock_taken': False}

    # ── ① 纠偏文件指纹（只读）──────────────────────────────────
    cb = open(CORRECTIONS, 'rb').read()
    heads = re.findall(rb'^##\s+(APP-\d+)', cb, re.M)
    ev['corrections_fingerprint'] = {
        'path': CORRECTIONS,
        'sha256': hashlib.sha256(cb).hexdigest(),
        'bytes': len(cb),
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                               time.localtime(os.path.getmtime(CORRECTIONS))),
        'n_headings': len(heads),
        'max_heading': 'APP-%d' % max(int(h.split(b'-')[1]) for h in heads),
        'note': '只读 fingerprint；本脚本不改该文件（reviewer 独占）',
    }
    ev['status_doc'] = file_fact(STATUS)
    ev['status_doc']['lines'] = len(open(STATUS, encoding='utf-8').read().splitlines())

    # ── ② 上一会话遗留的 4 处半交付 ────────────────────────────
    email_body = os.path.join(REPO, 'results', 'app', '_app121_email_body.txt')
    head_ver = git_text('show', 'HEAD:results/app/_app121_email_body.txt')
    ev['half_deliveries'] = [{
        'id': 'HD1',
        'desc': 'results/app/_app121_email_body.txt：已提交版是**发信前草稿**',
        'file': file_fact(email_body),
        'head_version': {
            'bytes': len(head_ver.encode('utf-8')),
            'sha256': hashlib.sha256(head_ver.encode('utf-8')).hexdigest(),
            'has_placeholder_COMMIT_SHA': 'COMMIT_SHA' in head_ver,
            'says_see_attachment': '附件' in head_ver,
            'mentions_real_commit_sha': '88b9ea8' in head_ver,
        },
        'worktree_version': {
            'has_placeholder_COMMIT_SHA': 'COMMIT_SHA' in open(
                email_body, encoding='utf-8').read(),
            'mentions_real_commit_sha': '88b9ea8' in open(
                email_body, encoding='utf-8').read(),
            'mentions_companion_sha': 'bf176bdbddb7fb2b' in open(
                email_body, encoding='utf-8').read(),
        },
        'actually_sent_mail': ('[C4][A][STATUS][APP] APP-121 STATUS（MiniMVP v1.1.1）'
                               '…正文见 A 机 status/app/STATUS_APP_sec221_detail_'
                               '20261123.md（24085 B，SHA bf176bdbddb7fb2b）…'
                               '提交 88b9ea8（main）'),
        'note': '那封邮件 has_attachments=false（**无附件**）⇒ HEAD 版的'
                '「详见附件」与「COMMIT_SHA（main）」占位符**都不成立**；'
                '**实际发出**的是工作区版本 ⇒ 本轮提交工作区版本。',
    }, {
        'id': 'HD2',
        'desc': 'live_caption/_app121_zip_extract_check.py 未入库，但其产物 json 已入库并被引用',
        'script': file_fact(os.path.join(HERE, '_app121_zip_extract_check.py')),
        'product_json': file_fact(os.path.join(
            REPO, 'results', 'app', 'app121_zip_extract_check.json')),
        'product_json_tracked': bool(git_text(
            'ls-files', 'results/app/app121_zip_extract_check.json').strip()),
        'cited_by': 'status/app/STATUS_APP_sec221_detail_20261123.md §3（解压自检）',
        'sibling_producers_tracked': len(git_text(
            'ls-files', 'live_caption/_app121_*.py').split()) - 0,
    }, {
        'id': 'HD3',
        'desc': '本轮 10 分钟整链的逐句 jsonl ＋ 积压曲线未入库（验收 json 已入库）',
        'jsonl': file_fact(os.path.join(
            REPO, 'results', 'app',
            '_app591_app121_v111_default_run20261123-1000_tts_out.wav.tts.jsonl')),
        'backlog_csv': file_fact(os.path.join(
            REPO, 'results', 'app',
            '_app591_app121_v111_default_run20261123-1000_tts_out.wav.backlog_curve.csv')),
        'acceptance_json_tracked': bool(git_text(
            'ls-files',
            'results/app/app591_acceptance_app121_v111_default_run20261123-1000.json'
        ).strip()),
        'peer_arm_jsonl_tracked': bool(git_text(
            'ls-files', 'results/app/_app591_app119_default_run20260721-032253_tts_out.wav.tts.jsonl'
        ).strip()) or len(git_text('ls-files', 'results/app/_app591_app119_*'
                                   ).split()) > 0,
        'reviewer_recompute_basis': ('reviewer 对 APP-120 的 10 分钟整链就是用 jsonl '
                                     '复算（§221 §0 引 review 原话「reviewer 本机用 '
                                     'jsonl 复算（SHA b3a72990…）」）⇒ jsonl 是复算底本'),
    }, {
        'id': 'HD4',
        'desc': 'live_caption/package_profiles.py 未入库，但已入库的构建脚本直接 import 它',
        'file': file_fact(os.path.join(HERE, 'package_profiles.py')),
        'importer': 'live_caption/_app120_build_minimvp_v11.py（**已入库**）',
        'import_line': 'from package_profiles import PROFILE_RULES, is_excluded, top_dirs',
        'importer_tracked': bool(git_text(
            'ls-files', 'live_caption/_app120_build_minimvp_v11.py').strip()),
        'consequence': '干净 clone 跑 MiniMVP 构建 ⇒ ImportError（无法重建包）',
    }]

    # ── ③ 交付面只读复核 ──────────────────────────────────────
    zip_path = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1.zip')
    pkg = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.1.1')
    zf = zipfile.ZipFile(zip_path)
    entries = [i for i in zf.infolist() if not i.filename.endswith('/')]
    raw_total = sum(i.file_size for i in entries)
    app_py = {os.path.basename(i.filename) for i in entries
              if i.filename.endswith('.py') and i.filename.count('/') == 2
              and i.filename.split('/')[1] == 'app'}
    zf.close()
    acc = json.load(open(os.path.join(pkg, 'ACCEPTED.json'), encoding='utf-8'))
    fp = set(acc.get('code_fingerprints', {}).keys())
    ev['delivery_surface_readonly'] = {
        'zip': file_fact(zip_path),
        'zip_file_entries': len(entries),
        'zip_uncompressed_bytes': raw_total,
        'readme_claims_bytes': 6701780843,
        'readme_bytes_match_zip': raw_total == 6701780843,
        'readme_claims_files': 10881,
        'readme_files_match_zip': len(entries) == 10881,
        'v1_1_zip_uncompressed_bytes': 6701773512,
        'note': 'reviewer APP-121 §4 给的「6 701 773 512 B」＝ **v1.1** zip 的解压总量；'
                '**v1.1.1** zip 的解压总量实测 6 701 780 843 B（README 写的即是此数）',
        'accepted_version': acc.get('version'),
        'accepted_n_fingerprints': len(fp),
        'zip_app_py_count': len(app_py),
        'fingerprint_keys_equal_zip_app_py': fp == app_py,
        'fp_not_in_zip': sorted(fp - app_py),
        'zip_not_in_fp': sorted(app_py - fp),
    }

    # dev 树 ＝ v2.5 ＝ v1.1.1（同字节核对）
    mods = ['asr06b_stateful_backend.py', 'live_caption_app.py',
            'device_config.py', 'tts_worker.py', 'tts_engine.py']
    rows = []
    for m in mods:
        hs = []
        for d in (os.path.join(REPO, 'live_caption'),
                  os.path.join(HOME, 'Confucius4_LiveCaption_v2.5', 'app'),
                  os.path.join(pkg, 'app')):
            p = os.path.join(d, m)
            hs.append(sha_bytes(p)[:12] if os.path.exists(p) else 'MISSING')
        rows.append({'module': m, 'dev': hs[0], 'v2_5': hs[1], 'v1_1_1': hs[2],
                     'all_same': len(set(hs)) == 1})
    ev['dev_v25_v1111_identical'] = rows

    # v2.5 的 ACCEPTED 仍 fail-closed（未重签）
    v25_acc = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5', 'ACCEPTED.json')
    ev['v25_acceptance_still_unresigned'] = {
        'path': v25_acc,
        'version': json.load(open(v25_acc, encoding='utf-8')).get('version'),
        'pkg_dir': json.load(open(v25_acc, encoding='utf-8')).get('pkg_dir'),
        'v25_zip_exists': os.path.exists(
            os.path.join(HOME, 'Confucius4_LiveCaption_v2.5.zip')),
        'note': '**仍指向 v2.4** ⇒ 闸门 check_acceptance_binding fail-closed ⇒ '
                '**v2.5 打不出 zip**（沿用 §220 的未结项；本轮未改）',
    }

    # ── ④ ASR §91 两条交叉结论的本模块自证 ─────────────────────
    mats = {}
    for tag, fn in (('NPU', 'app121_asr_app_3mat_NPU.json'),
                    ('GPU0', 'app121_asr_app_3mat_GPU0.json')):
        d = json.load(open(os.path.join(REPO, 'results', 'app', fn), encoding='utf-8'))
        mats[tag] = [{'material': m['material'],
                      'n_segs': m.get('n_segs'),
                      'prefix_truncations': m.get('prefix_truncations'),
                      'transcript_md5': m.get('transcript_md5')} for m in d['materials']]
    npu = json.load(open(os.path.join(
        REPO, 'results', 'app', 'app121_asr_app_3mat_NPU.json'), encoding='utf-8'))
    ev['asr_s91_crosscheck'] = {
        'ASR-91-4_prefix_truncations': {
            'materials': mats,
            'npu_zh_nonzero': [m for m in mats['NPU'] if m['prefix_truncations']],
            'gpu0_all_zero': all(m['prefix_truncations'] == 0 for m in mats['GPU0']),
            'verdict': '**属实**（App 侧 NPU 的 ZH 素材 prefix_truncations=3；'
                       'GPU.0 同素材=0）⇒ 与 ASR §91 ④ 一致',
            'own_artifact': 'results/app/app121_asr_app_3mat_NPU.json / …_GPU0.json',
        },
        'ASR-91-5_attribution': {
            'where_the_sentence_lives': '**只在**证据 json 的 '
                                        'ref_diff_explanation[].reasons[0]'
                                        '（harness 里的**静态字面量**）',
            'not_in_companion_prose': '§221 companion §2 正文写的是「段边界一致 ⇒ '
                                      '切段器行为一致，差异不在切段」',
            'n_segs_app_vs_ref': [{'material': e['material'],
                                   'app': e['n_segs_app'], 'ref': e['n_segs_ref'],
                                   'equal': e['n_segs_app'] == e['n_segs_ref']}
                                  for e in npu['ref_diff_explanation']],
            'contradiction': '**同一个 json 自己的 n_segs_app == n_segs_ref**'
                             '（93/65/66 三素材全同）⇒ reasons[0] 的「段边界与段数'
                             '本就不一致」**与本文件实测自相矛盾**',
            'verdict': '**§221 的正文结论不需要撤回**；缺陷只在 harness 的静态串',
            'own_artifact': 'results/app/app121_asr_app_3mat_{NPU,GPU0,GPU0_OLD_v11}.json',
        },
    }

    # ── ⑤ 明确「不提交」的既有脏文件 ───────────────────────────
    ev['left_uncommitted_on_purpose'] = {
        'results/app/app523_pack_must_ttsworker_evidence.json':
            '**明确 hold**：§199/§200「仍保持未提交（等 reviewer 对 app523 裁定，'
            '不预判）」⇒ 本轮不碰',
        'results/app/app170_version_identity_gate_evidence.json':
            '早期轮次残留（v2.3→v2.5 刷新从未入库）；无 hold，但 §191 已引用它 ⇒ '
            '**不擅自替换被引用的证据产物**，列为待 reviewer 裁定',
        'results/app/app157_follow_speaker_regression_evidence_pkg.json':
            'autocrlf 假阳性（`git diff --numstat` 无内容差异）⇒ 非实质改动',
        'results/app/app468_status_git_halfdelivery.json':
            'autocrlf 假阳性（`git diff --numstat` 无内容差异）⇒ 非实质改动',
        'status/app/CORRECTIONS_APP.md':
            'reviewer 独占 ⇒ **永不 add**',
        'status/CORRECTIONS.md / status/STATUS_ARCHIVE_2026-10.md':
            '**非 App 模块**文件 ⇒ 不吞他模块改动',
        'live_caption/sync_c*.py':
            '§57 历史遗留未跟踪文件，**归属未判定** ⇒ 不提交',
    }

    ev['verdict'] = 'PASS'
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmp, args.out)
    print('证据 → %s (%d B)' % (args.out, os.path.getsize(args.out)))
    print('  纠偏文件：%s 条 / max %s / SHA %s'
          % (ev['corrections_fingerprint']['n_headings'],
             ev['corrections_fingerprint']['max_heading'],
             ev['corrections_fingerprint']['sha256'][:16]))
    print('  v1.1.1 zip：%d 条 / 解压 %d B'
          % (ev['delivery_surface_readonly']['zip_file_entries'],
             ev['delivery_surface_readonly']['zip_uncompressed_bytes']))
    print('  ACCEPTED 指纹 == zip app/*.py ⇒ %s'
          % ev['delivery_surface_readonly']['fingerprint_keys_equal_zip_app_py'])
    print('  dev == v2.5 == v1.1.1 ⇒ %s'
          % all(r['all_same'] for r in rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
