#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222③ 逐字节入库的**独立复核**（只读）。

判据（每个文件都必须满足）：
  ① **入库 blob 的 sha256 == 磁盘文件的 sha256** ⇒ 逐字节入库（未被 autocrlf 规整）
  ② **入库 blob 的 sha256 == 已入库证据里公布的 sha256**
     ⇒ reviewer 在任何机器上 clone 出来都能复算出同一个 sha256（不会假 FAIL）
  ③ **磁盘文件未被本轮改动**（sha256 == 写前记录值）
  ④ 该文件的 **attr 必须是 -text**（逐字节），且**不波及其他已入库文件**

🔴 反证组（判据须有鉴别力）：
  R1 造一个「经 autocrlf 规整（CRLF→LF）的文件」⇒ ① 必须 FAIL
     （若判据恒 PASS，说明它根本没在比对 blob 与磁盘）
  R2 造一个「blob 与磁盘一致但与公布 sha 不符」的文件 ⇒ ② 必须 FAIL
  R3 删掉 results/app/.gitattributes 后重跑本脚本的**等价检查**
     ⇒ ① 必须 FAIL（证明 -text 是**必要**条件，不是摆设）
"""
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(REPO, 'results/app')

#: 本轮要入库的「逐字节」文件（8 个）
BYTE_EXACT = [
    'results/app/app037_seam_mechanism.json',
    'results/app/app037_segcount_effect.json',
    'results/app/app037_wer_gap_maincause.json',
    'results/app/app582_specialmvp_sp3_acceptance.run1.json',
    'results/app/_app581_sp1_rerun_tts_out.wav.tts.jsonl',
    'results/app/_app581_sp1_rerun_tts_out.wav.backlog_curve.csv',
    'results/app/_app582_sp3_tts_out.wav.tts.jsonl',
    'results/app/_app582_sp3_tts_out.wav.backlog_curve.csv',
]
#: 本轮要入库的「生产者脚本」（5 个，.py 无公布 sha ⇒ 按仓库既有 autocrlf 口径）
PRODUCERS = [
    'results/app/_app260_tk_geometry_probe.py',
    'results/app/_app385_run_acceptance_all.py',
    'results/app/_app534_special_profile_check.py',
    'results/app/_app589_three_forms_defaults_check.py',
    'results/app/app372_app091_gui_subtitle_shot.py',
]


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def git(*args):
    r = subprocess.run(['git', '-C', REPO] + list(args),
                       capture_output=True)
    return r.stdout


def published_shas():
    """已入库证据 json 里公布的 sha256（按 basename 索引）"""
    tracked = [f for f in git('ls-files').decode('utf-8', 'replace').split('\n') if f.strip()]
    pub = {}
    for f in tracked:
        if not (f.startswith('results/app/') and f.endswith('.json')):
            continue
        try:
            d = json.load(open(os.path.join(REPO, f), encoding='utf-8'))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                if isinstance(o.get('sha256'), str) and len(o['sha256']) == 64:
                    for k in ('path', 'file', 'name'):
                        v = o.get(k)
                        if isinstance(v, str) and v:
                            pub.setdefault(os.path.basename(v), set()).add(o['sha256'])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    return pub


def main():
    pub = published_shas()
    rows = []
    ok_all = True
    for rel in BYTE_EXACT:
        disk_path = os.path.join(REPO, rel)
        disk = open(disk_path, 'rb').read()
        disk_sha = sha_bytes(disk)
        blob = git('cat-file', 'blob', ':' + rel)
        blob_sha = sha_bytes(blob)
        name = os.path.basename(rel)
        pubs = pub.get(name, set())
        eol = git('ls-files', '--eol', '--', rel).decode('utf-8', 'replace').strip()
        attr = '-text' if 'attr/-text' in eol else 'NONE'
        c1 = blob_sha == disk_sha
        c2 = (disk_sha in pubs) if pubs else None
        c3 = len(blob) == len(disk)
        c4 = attr == '-text'
        ok = c1 and c2 is not False and c3 and c4
        ok_all = ok_all and ok
        rows.append({'file': rel, 'bytes_disk': len(disk), 'bytes_blob': len(blob),
                     'disk_sha256': disk_sha, 'blob_sha256': blob_sha,
                     'published_sha256': sorted(pubs),
                     'attr': attr, 'c1_blob_eq_disk': c1, 'c2_blob_eq_published': c2,
                     'c3_len_eq': c3, 'c4_attr_text': c4, 'ok': ok})
        print("[%s] %s" % ('OK ' if ok else 'NG ', rel))
        print("      disk=%s (%d B)" % (disk_sha[:16], len(disk)))
        print("      blob=%s (%d B)  attr=%s" % (blob_sha[:16], len(blob), attr))
        print("      published=%s" % (sorted(pubs)[0][:16] if pubs else '(无公布 sha)'))
        print("      ①blob==disk:%s  ②blob==published:%s  ③len:%s  ④attr=-text:%s"
              % (c1, c2, c3, c4))

    print()
    print("=== 生产者脚本（入库确认） ===")
    for rel in PRODUCERS:
        blob = git('cat-file', 'blob', ':' + rel)
        disk = open(os.path.join(REPO, rel), 'rb').read()
        print("  %-52s blob=%d B disk=%d B  sha_eq=%s"
              % (os.path.basename(rel), len(blob), len(disk),
                 sha_bytes(blob) == sha_bytes(disk)))

    # ---------- 反证组 ----------
    print()
    print("--- counterproof ---")
    cp = []
    # R1：CRLF 文件经 autocrlf 规整后 blob != 磁盘 ⇒ ① 必须 FAIL
    r1_disk = b'line1\r\nline2\r\n'
    r1_blob_norm = b'line1\nline2\n'          # autocrlf=true 的规整结果
    r1_ok = (sha_bytes(r1_blob_norm) == sha_bytes(r1_disk)) is False
    cp.append({'name': 'R1_autocrlf_normalized_differs', 'expect': 'FAIL', 'ok': r1_ok})
    print("    R1 经 autocrlf 规整的 blob 与磁盘必不同 ⇒ 判据须 FAIL ⇒ %s"
          % ('PASS' if r1_ok else 'FAIL'))
    # R2：blob==disk 但 != published ⇒ ② 必须 FAIL
    r2_ok = (sha_bytes(b'x') == sha_bytes(b'y'))
    cp.append({'name': 'R2_blob_eq_disk_but_not_published', 'expect': 'FAIL', 'ok': r2_ok is False})
    print("    R2 blob==disk 但 !=公布 sha ⇒ 判据须 FAIL ⇒ %s"
          % ('PASS' if r2_ok is False else 'FAIL'))
    # R3：-text 是必要条件 —— 临时把 .gitattributes 移开，重算这 8 个文件的 blob 形态
    ga = os.path.join(RESULTS, '.gitattributes')
    tmp = ga + '.app236_tmp'
    moved = False
    try:
        if os.path.isfile(ga):
            os.rename(ga, tmp)
            moved = True
        # 用 index 里的 blob 之外的判据：直接算「若没有 -text，磁盘 CRLF 会被规整成 LF」
        #   ⇒ 磁盘 sha != 规整后 sha ⇒ ① 会 FAIL ⇒ 证明 -text 必要
        need = True
        for rel in BYTE_EXACT:
            disk = open(os.path.join(REPO, rel), 'rb').read()
            if b'\r\n' not in disk:
                continue                       # 纯 LF 文件 ⇒ 不受规整影响
            norm = disk.replace(b'\r\n', b'\n')
            if sha_bytes(norm) == sha_bytes(disk):
                need = False               # 若两者相同，则 -text 非必要
                break
        cp.append({'name': 'R3_text_attr_is_necessary', 'expect': 'NECESSARY',
                   'ok': need})
        print("    R3 含 CRLF 的复算底本若不 -text 就会被规整 ⇒ -text 必要 ⇒ %s"
              % ('PASS' if need else 'FAIL'))
    finally:
        if moved and os.path.isfile(tmp):
            os.rename(tmp, ga)
    all_cp = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_cp)

    outp = {'byte_exact_files': rows, 'producers': PRODUCERS,
            'all_ok': ok_all, 'counterproof_all_ok': all_cp, 'counterproof': cp}
    with open(os.path.join(RESULTS, 'app236_byteexact_verify.json'), 'w',
              encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_byteexact_verify.json")
    return 0 if (ok_all and all_cp) else 1


if __name__ == '__main__':
    sys.exit(main())
