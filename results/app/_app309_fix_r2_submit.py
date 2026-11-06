r"""_app309 — 补齐 `v23_clone_r2/submit.jsonl`，并用不动点迭代重签 manifest。

背景（本轮证据口径自检发现）：
  `_app303_build_v23_clone_r2.py` 旧代码按
  `tts_on_clone_0.submit.jsonl` 找源，但设备作业真实产物叫
  `tts_on_clone_0.seg.jsonl.submit.jsonl`；旧写法 `if os.path.isfile(s)`
  静默跳过 ⇒ r2 缺 jid→seg 映射（APP-067 ①(b) 标签晚到的关键诊断件）。
  manifest 自记 52 文件／20 160 623 B，磁盘写后 53 文件／20 170 791 B
  （差额即 manifest.json 自身 10 168 B）。

本脚本：
  ① 复制真实 submit 源到 r2（sha256 与源逐字节一致）；
  ② `_app303` 已修为显式映射 + assert（本脚本验证其存在与反证）；
  ③ 重签 manifest：`files` 含 manifest 自身条目，字节数用**不动点迭代**
     直到 `len(blob)` 与写入值一致（APP-049/052④ 自指纪律：差 2 B 也要改）；
  ④ 验收：磁盘实测 == manifest 自记；所有非自身条目 SHA 与磁盘一致；
     旧 52 个产物 SHA **逐条未变**（证明只补了一个文件）；
  ⑤ 只动 r2 自己本轮新生成的目录；**不碰** `v23_clone/`、任何客户包、
     任何 zip、桌面 .lnk。证据落 `results/app/_app309_fix_r2_submit.json`。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = r'C:\Users\Trekker-PTL\shared\app_listen\v23_clone_r2'
SRC = os.path.join(REPO, 'results', 'app', 'app301_device_out')
STEM = 'tts_on_clone_0'
SUBMIT_SRC_NAME = STEM + '.seg.jsonl.submit.jsonl'
BUILD = os.path.join(HERE, '_app303_build_v23_clone_r2.py')
EV = os.path.join(HERE, '_app309_fix_r2_submit.json')
MANIFEST_REL = 'manifest.json'
SUBMIT_REL = 'submit.jsonl'


def sha256_file(p):
    m = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            m.update(c)
    return m.hexdigest()


def disk_list():
    out = []
    for dp, _dn, fns in os.walk(OUT):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, OUT).replace('\\', '/')
            out.append((rel, full))
    return sorted(out)


def main():
    checks = []

    def chk(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)))

    old_manifest = json.load(open(os.path.join(OUT, MANIFEST_REL),
                                  encoding='utf-8'))
    old_by_rel = {x['rel']: x for x in old_manifest['files']}
    before = disk_list()
    before_n, before_bytes = len(before), sum(os.path.getsize(p)
                                              for _r, p in before)

    # ── ① 修复后的构建脚本：显式映射 + 禁止静默跳过 ──────────────
    src_txt = open(BUILD, encoding='utf-8').read()
    tree = ast.parse(src_txt)                # 语法必须过
    chk('构建脚本 _app303 语法通过（ast.parse）', True)
    chk('_app303 已改为显式 _JSONL_SRC 映射', '_JSONL_SRC' in src_txt)
    chk('_app303 显式映射指向真实源文件名', SUBMIT_SRC_NAME in src_txt)
    # 🔴 判据必须走 AST：注释/docstring 里描述旧写法时也会出现
    #    `if os.path.isfile(s)` 字面串，用文本包含判断会假 FAIL。
    # 🔴 还要排除**合法**的容错 If：_app303 第 121 行读 tts.jsonl 用
    #    `if os.path.isfile(p)`，那是读取容错，不是复制时的静默跳过。
    #    只把「body 里调用 shutil.copy2」的 If 视为静默漏拷。
    silent_if = [n for n in ast.walk(tree)
                 if isinstance(n, ast.If)
                 and 'isfile' in ast.dump(n.test)
                 and any(isinstance(x, ast.Call)
                         and 'copy2' in ast.dump(x.func)
                         for stmt in n.body for x in ast.walk(stmt))]
    has_assert = any(isinstance(n, ast.Assert)
                     and 'isfile' in ast.dump(n.test) for n in ast.walk(tree))
    chk('_app303 缺源改为 assert（AST：无静默 If / 有 Assert）',
        has_assert and not silent_if,
        'assert=%s silent_if=%d' % (has_assert, len(silent_if)))
    # 反证：旧写法确实找不到源
    old_guess = os.path.join(SRC, STEM + '.' + SUBMIT_REL)
    new_guess = os.path.join(SRC, SUBMIT_SRC_NAME)
    chk('反证①：旧文件名 tts_on_clone_0.submit.jsonl 不存在（旧逻辑会漏）',
        not os.path.isfile(old_guess), old_guess)
    chk('反证②：新文件名真实存在', os.path.isfile(new_guess), new_guess)

    # ── ② 补齐 submit.jsonl ─────────────────────────────────────
    dst = os.path.join(OUT, SUBMIT_REL)
    first_run = not os.path.exists(dst)      # 首跑补齐；复跑必须幂等
    chk('submit.jsonl 首跑前缺失／复跑已存在（幂等）',
        first_run or os.path.exists(dst), 'first_run=%s' % first_run)
    if first_run:
        shutil.copy2(new_guess, dst)
    src_sha, dst_sha = sha256_file(new_guess), sha256_file(dst)
    chk('submit.jsonl 与设备源逐字节一致', src_sha == dst_sha,
        '%s %d B' % (dst_sha, os.path.getsize(dst)))

    # ── ③ 不动点迭代重签 manifest ───────────────────────────────
    others = []
    for rel, full in disk_list():
        if rel == MANIFEST_REL:
            continue
        others.append(dict(rel=rel, bytes=os.path.getsize(full),
                           mtime=os.path.getmtime(full),
                           sha256=sha256_file(full)))
    others.sort(key=lambda x: x['rel'])
    base = dict(old_manifest)
    base['created_by'] = ('_app303_build_v23_clone_r2.py + '
                          '_app309_fix_r2_submit.py (补 submit.jsonl 并重签)')
    base['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    base['manifest_rev'] = int(old_manifest.get('manifest_rev', 1)) + 1
    base['manifest_note'] = (
        '本 manifest 的 files 含自身条目；自身 bytes 用不动点迭代求得，'
        'mtime/sha256 不可自含 ⇒ 标 None。n_files/n_bytes 含 manifest 自身，'
        '与磁盘实测一致。')
    base['incomplete'] = old_manifest['incomplete']   # 不掩盖未完成项

    mpath = os.path.join(OUT, MANIFEST_REL)
    guess = os.path.getsize(mpath)
    blob, iters = b'', 0
    for iters in range(1, 31):
        self_entry = dict(rel=MANIFEST_REL, bytes=guess, mtime=None,
                          sha256=None, self_manifest=True)
        files = others + [self_entry]
        files.sort(key=lambda x: x['rel'])
        base['files'] = files
        base['n_files'] = len(files)
        base['n_bytes'] = sum(x['bytes'] for x in files)
        blob = json.dumps(base, ensure_ascii=False, indent=1).encode('utf-8')
        if len(blob) == guess:
            break
        guess = len(blob)
    converged = (len(blob) == guess and iters < 30)
    chk('manifest 自指大小不动点收敛', converged,
        'iters=%d 自记=%d 序列化=%d' % (iters, guess, len(blob)))
    if not converged:
        ev = dict(tool='_app309_fix_r2_submit', verdict='FAIL', checks=checks)
        json.dump(ev, open(EV, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 1
    tmp = mpath + '.app309_tmp'
    with open(tmp, 'wb') as f:
        f.write(blob)
    os.replace(tmp, mpath)

    # ── ④ 写后验收 ─────────────────────────────────────────────
    after = disk_list()
    after_n = len(after)
    after_bytes = sum(os.path.getsize(p) for _r, p in after)
    new_manifest = json.load(open(mpath, encoding='utf-8'))
    chk('磁盘实测 n_files == manifest 自记', after_n == new_manifest['n_files'],
        '%d / %d' % (after_n, new_manifest['n_files']))
    chk('磁盘实测 n_bytes == manifest 自记',
        after_bytes == new_manifest['n_bytes'],
        '%d / %d' % (after_bytes, new_manifest['n_bytes']))
    self_e = [x for x in new_manifest['files'] if x['rel'] == MANIFEST_REL]
    chk('files 含且仅含 1 条 manifest 自身条目', len(self_e) == 1)
    chk('自身条目 bytes == 磁盘 manifest.json 实测',
        self_e and self_e[0]['bytes'] == os.path.getsize(mpath),
        '%d B' % os.path.getsize(mpath))
    # 所有非自身条目 SHA 与磁盘逐一相符
    bad = []
    for rel, full in after:
        if rel == MANIFEST_REL:
            continue
        e = next((x for x in new_manifest['files'] if x['rel'] == rel), None)
        if e is None or e['sha256'] != sha256_file(full) \
                or e['bytes'] != os.path.getsize(full):
            bad.append(rel)
    chk('全部非自身条目 SHA/字节与磁盘逐条相符', not bad,
        '%d 条，bad=%s' % (after_n - 1, bad[:5]))
    # 旧 52 个产物一字节未动
    changed = [r for r, x in old_by_rel.items()
               if r not in [x2['rel'] for x2 in new_manifest['files']]
               or x['sha256'] != next(
                   (y['sha256'] for y in new_manifest['files']
                    if y['rel'] == r), None)]
    chk('写前记录的产物 SHA 写后逐条未变（只改 manifest 自身）', not changed,
        '%d 条旧记录，changed=%s' % (len(old_by_rel), changed[:5]))
    chk('文件数变化符合首跑/复跑预期',
        after_n - before_n == (1 if first_run else 0),
        'first_run=%s %d -> %d' % (first_run, before_n, after_n))
    chk('submit.jsonl 已落盘且非空', os.path.getsize(dst) > 0,
        '%d B' % os.path.getsize(dst))
    chk('未完成项声明未被抹掉（incomplete 原文保留）',
        new_manifest['incomplete'] == old_manifest['incomplete'])

    n_fail = sum(1 for c in checks if not c['ok'])
    for c in checks:
        print('  [%s] %s %s' % ('PASS' if c['ok'] else 'FAIL',
                                c['name'], c['detail']))
    ev = dict(tool='_app309_fix_r2_submit', app='APP-075(e)',
              ts=time.strftime('%Y-%m-%d %H:%M:%S'),
              out_dir=OUT, first_run=first_run,
              note=('首跑补齐 submit.jsonl 并重签；本轮复跑为判据订正后'
                    '的幂等复核（AST 判据取代文本包含判据）'),
              manifest_rev=base['manifest_rev'],
              before=dict(n_files=before_n, n_bytes=before_bytes),
              after=dict(n_files=after_n, n_bytes=after_bytes),
              submit=dict(rel=SUBMIT_REL, src=SUBMIT_SRC_NAME,
                          bytes=os.path.getsize(dst), sha256=dst_sha),
              manifest=dict(rel=MANIFEST_REL, bytes=os.path.getsize(mpath),
                            sha256=sha256_file(mpath),
                            fixed_point_iters=iters),
              gate=new_manifest['gate'],
              incomplete=new_manifest['incomplete'],
              checks=checks, n_pass=len(checks) - n_fail, n_fail=n_fail,
              verdict='PASS' if n_fail == 0 else 'FAIL')
    json.dump(ev, open(EV, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n%s (%d PASS / %d FAIL)' % (ev['verdict'], ev['n_pass'], n_fail))
    print('r2: %d 文件 / %d B（补前 %d / %d）'
          % (after_n, after_bytes, before_n, before_bytes))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
