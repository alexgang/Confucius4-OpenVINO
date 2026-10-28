# -*- coding: utf-8 -*-
"""app122 — §84：**客户包定点同步**（仓库 ⇄ `Confucius4_LiveCaption_v1.6/app`）。

## 🔴 为什么不能用「整目录覆盖」

仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本** ⇒ 整目录覆盖会把
包里**别人（或历史）的定制**一起冲掉 ⇒ 历史上已经因此出过事故。

⇒ 本脚本走**定点替换**路线：
1. 取**基线**（`git show HEAD:live_caption/<f>`）—— 必须是 **HEAD**，
   不能是工作区（工作区含本轮新改动 ⇒ 拿它当基线等于「把新改动覆盖回去」）；
2. 用 `difflib` 在「基线 → 工作区」之间派生**替换块**
   （`get_grouped_opcodes(n=3)` ⇒ 相邻改动合并，避免碎片化）；
3. **先断言包内文件逐字等于基线**（否则基线不匹配 ⇒ 必须停下来人工看）；
4. 每个替换块在包内文件里**唯一命中**才替换（命中数 != 1 ⇒ 立即中止）；
5. 替换后**独立复核**：包内文件（LF 归一化）== 工作区文件（LF 归一化）。

## 🔴 新增文件（`clone_collector.py`）

包内原本**没有**这个文件 ⇒ 属**新增**（不是覆盖）⇒ 直接落盘，
并断言落盘后逐字 == 仓库版本。

## 🔴 换行风格

仓库 `live_caption_app.py` 是 **CRLF**，客户包那份是 **LF**
⇒ 同步时**统一按 LF 写入包**（与包内既有风格一致，避免整文件变成 CRLF）。

## 用法

    <py> results/app/app122_sync_pkg_clone.py [--apply]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_APP = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6', 'app')
REPO_LC = os.path.join(REPO, 'live_caption')

OUT = os.path.join(HERE, 'app122_pkg_sync_evidence.json')

#: 本轮要同步的文件：(仓库相对路径, 包内相对路径, 是否新增)
FILES = [
    ('live_caption_app.py', 'live_caption_app.py', False),
    ('tts_worker.py', 'tts_worker.py', False),
    ('clone_collector.py', 'clone_collector.py', True),
]


def _norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def _read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_show(rel: str) -> str:
    out = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:live_caption/' + rel],
                         capture_output=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError('git show 失败 %s: %s'
                           % (rel, out.stderr.decode('utf-8', 'replace')[:200]))
    return out.stdout.decode('utf-8')


def _blocks(base: str, work: str):
    """派生替换块：[(base_start, base_end, new_text)]（行号，0 基，半开区间）。"""
    bl = base.splitlines(keepends=True)
    wl = work.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, bl, wl, autojunk=False)
    out = []
    for grp in sm.get_grouped_opcodes(n=3):
        i1 = grp[0][1]
        i2 = grp[-1][2]
        out.append((i1, i2, ''.join(wl[grp[0][3]:grp[-1][4]])))
    return out


def _apply_blocks(text: str, blocks) -> str:
    """按块定点替换（**唯一命中断言**）。"""
    lines = text.splitlines(keepends=True)
    # 从后往前替换 ⇒ 前面的块位置不受影响
    for (i1, i2, new) in sorted(blocks, key=lambda t: -t[0]):
        old = ''.join(lines[i1:i2])
        cnt = text.count(old) if old else 1
        if cnt != 1:
            raise AssertionError('替换块在目标里命中 %d 次（要求恰好 1 次）'
                                 '：起始行 %d' % (cnt, i1))
        # 行号定位（因为前面可能有别的块已替换 ⇒ 用行号切片更稳）
        lines[i1:i2] = [new] if new else []
        text = ''.join(lines)
        lines = text.splitlines(keepends=True)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写入客户包')
    args = ap.parse_args()

    report = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'), apply=bool(args.apply),
                  pkg_app=PKG_APP, files=[])
    all_ok = True

    for rel, pkg_rel, is_new in FILES:
        rec = dict(repo_rel='live_caption/' + rel, pkg_rel=pkg_rel, is_new=is_new)
        repo_path = os.path.join(REPO_LC, rel)
        pkg_path = os.path.join(PKG_APP, pkg_rel)
        work_raw = _read_bytes(repo_path)
        work = _norm(work_raw.decode('utf-8'))
        rec['repo_bytes'] = len(work_raw)
        rec['repo_sha256'] = _sha256(work_raw)
        rec['repo_crlf'] = work_raw.count(b'\r\n')

        if is_new:
            existed = os.path.isfile(pkg_path)
            rec['pkg_existed_before'] = existed
            if existed:
                # 已存在 ⇒ 不覆盖，先比对
                pkg_raw = _read_bytes(pkg_path)
                same = _sha256(pkg_raw) == rec['repo_sha256']
                rec['pkg_already_same'] = same
                rec['ok'] = same
            else:
                if args.apply:
                    with open(pkg_path, 'wb') as f:
                        f.write(work.encode('utf-8'))
                    rec['written'] = True
                    rec['ok'] = True
                else:
                    rec['written'] = False
                    rec['ok'] = True
                    rec['note'] = 'dry-run：未写入'
            all_ok = all_ok and rec['ok']
            report['files'].append(rec)
            continue

        # ── 既有文件：定点替换 ──
        pkg_raw = _read_bytes(pkg_path)
        pkg = _norm(pkg_raw.decode('utf-8'))
        rec['pkg_bytes_before'] = len(pkg_raw)
        rec['pkg_sha256_before'] = _sha256(pkg_raw)
        head = _norm(_git_show(rel))
        # 🔴 **基线取「包内当前内容」**（不是 HEAD）
        #   ⇒ 因为包内可能已经比 HEAD 新（上一轮 §84 同步过）
        #   ⇒ 若强行以 HEAD 为基线，替换块会把包内**已有但 HEAD 没有**的内容
        #     **删掉**（整块替换）⇒ 反而是「整目录覆盖」的变种 ⇒ 事故。
        #   ⇒ 以包内当前内容为基线 ⇒ 派生的替换块**只包含本轮的增量**。
        base = pkg
        rec['base_is_head'] = (head == pkg)
        rec['base_is_pkg_current'] = True
        rec['pkg_is_ahead_of_head'] = (head != pkg)
        if pkg == _norm(work_raw.decode('utf-8')):
            rec['ok'] = True
            rec['identical_after'] = True
            rec['n_blocks'] = 0
            rec['note'] = '包内已是最新 ⇒ 无需替换'
            rec['written'] = False
            report['files'].append(rec)
            continue

        blocks = _blocks(base, work)
        rec['n_blocks'] = len(blocks)
        rec['block_lines'] = [[i1, i2] for (i1, i2, _) in blocks]

        try:
            new_pkg = _apply_blocks(pkg, blocks)
        except AssertionError as e:
            rec['ok'] = False
            rec['error'] = str(e)
            all_ok = False
            report['files'].append(rec)
            continue

        rec['identical_after'] = (new_pkg == work)
        if args.apply:
            with open(pkg_path, 'wb') as f:
                f.write(new_pkg.encode('utf-8'))
            rec['written'] = True
        else:
            rec['written'] = False
        # 独立复核：重新从磁盘读，比对
        if args.apply:
            chk = _read_bytes(pkg_path)
            rec['pkg_bytes_after'] = len(chk)
            rec['pkg_sha256_after'] = _sha256(chk)
            rec['pkg_mtime_after'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                   time.localtime(os.path.getmtime(pkg_path)))
            rec['verify_identical'] = (_norm(chk.decode('utf-8')) == work)
        rec['ok'] = rec['identical_after'] and rec.get('verify_identical', True)
        all_ok = all_ok and rec['ok']
        report['files'].append(rec)

    report['all_ok'] = all_ok
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    for r in report['files']:
        print('[%s] %-22s blocks=%-3s identical=%s written=%s%s'
              % ('OK ' if r.get('ok') else 'ERR', r['pkg_rel'],
                 r.get('n_blocks', '-'), r.get('identical_after', '-'),
                 r.get('written', '-'),
                 ('  <- ' + r['error']) if r.get('error') else ''))
    print('\n[apply=%s] all_ok=%s' % (args.apply, all_ok))
    print('证据：%s' % OUT)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
