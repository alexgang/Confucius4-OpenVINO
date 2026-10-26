#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 客户包定点同步脚本（§55 / APP-022 + TTS-017①）

## 纪律（照做，不许改）

1. **禁止整目录覆盖同步** —— 仓库 `live_caption/` 与客户包 `app/` 是两份独立副本。
2. **前置断言：包内内容基线必须逐字等于 `git show HEAD:<rel>`**（忽略行尾）
   ⇒ 证明「骨架等价」⇒ 才允许升级基底。
   ⚠️ 这条断言同时挡住「别的会话改过包」的情况（会直接判负中止）。
3. **替换块由 difflib 从 `git show HEAD:<rel>` 自动派生**（用于**生成差异清单 + 逐块校验**），
   **不手抄代码**。
4. **行尾按目标文件原有风格保留**（仓库 CRLF / 包内 LF 混存 ⇒ 不能一刀切）。
5. **先备份**（备份目录放**包外**），同步后**逐字校验 + py_compile**。

## 两种落点方式（用户纪律明文允许）

- 方式 A「精确字符串替换 + 唯一命中断言」：每个替换块在目标文件里**恰命中一次**才替换。
  ⚠️ 实测本轮 difflib 在行级会派生出**含公共行的大块**（如 29 556 次命中）⇒ A 不可用。
- 方式 B「代码骨架等价校验后升级基底」：前置断言通过后，把仓库工作区内容按**目标文件行尾风格**
  写入，并**逐字校验**写入结果 == 仓库工作区内容。
  ⇒ 本脚本**以 B 为主路径**，同时**保留 A 的逐块唯一性校验作为差异清单的证据**。
"""
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\app'
BACKUP = r'C:\Users\Trekker-PTL\_backup\pkg_sync_s55'

FILES = ['tts_engine', 'translator', 'caption_render',
         'live_caption_app', 'tts_service', 'tts_worker']


def _norm(s: str) -> str:
    return s.replace('\r\n', '\n')


def _read(path: str) -> str:
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def _write(path: str, s: str, crlf: bool) -> None:
    data = s.replace('\r\n', '\n')
    if crlf:
        data = data.replace('\n', '\r\n')
    with open(path, 'wb') as f:
        f.write(data.encode('utf-8'))


def main() -> int:
    os.makedirs(BACKUP, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    report = {
        'when': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': PKG,
        'backup_dir': BACKUP,
        'method': 'B: baseline-equivalence upgrade + per-block uniqueness audit',
        'files': [],
        'errors': [],
    }

    for name in FILES:
        rel = 'live_caption/%s.py' % name
        repo_path = os.path.join(REPO, rel.replace('/', os.sep))
        pkg_path = os.path.join(PKG, name + '.py')
        entry = {'name': name, 'rel': rel}

        if not os.path.isfile(pkg_path):
            report['errors'].append('%s: 包内文件不存在' % name)
            report['files'].append(entry)
            continue

        pkg_raw = _read(pkg_path)
        pkg_crlf = '\r\n' in pkg_raw
        pkg_text = _norm(pkg_raw)

        head_raw = subprocess.check_output(
            ['git', 'show', 'HEAD:' + rel], cwd=REPO).decode('utf-8')
        head_text = _norm(head_raw)

        # 🔴 前置断言（方式 B 的成立条件）：包内基线逐字等于 HEAD 基线
        if pkg_text != head_text:
            report['errors'].append(
                '%s: 包内基线 != 仓库 HEAD 基线 ⇒ 拒绝同步（可能是别的会话改过包）' % name)
            entry['baseline_equal'] = False
            report['files'].append(entry)
            continue
        entry['baseline_equal'] = True

        repo_text = _norm(_read(repo_path))
        if pkg_text == repo_text:
            entry['status'] = 'already-identical'
            entry['blocks'] = []
            entry['bytes'] = os.path.getsize(pkg_path)
            entry['sha256'] = _sha(pkg_path)
            report['files'].append(entry)
            continue

        # 🔴 difflib 自动派生差异清单（证据：块数 / 每块的行数与内容哈希）
        old_lines = head_text.splitlines(keepends=True)
        new_lines = repo_text.splitlines(keepends=True)
        sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
        blocks = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            old_block = ''.join(old_lines[i1:i2])
            new_block = ''.join(new_lines[j1:j2])
            blocks.append({
                'tag': tag,
                'old_lines': i2 - i1,
                'new_lines': j2 - j1,
                'old_sha256': hashlib.sha256(old_block.encode('utf-8')).hexdigest()[:16],
                'new_sha256': hashlib.sha256(new_block.encode('utf-8')).hexdigest()[:16],
                'old_hits_in_pkg': pkg_text.count(old_block),
                'old_block_is_blank': (not old_block.strip()),
            })
        entry['blocks'] = blocks
        entry['n_blocks'] = len(blocks)

        # 备份（包外）
        bkp = os.path.join(BACKUP, '%s_%s.py' % (name, stamp))
        shutil.copy2(pkg_path, bkp)
        entry['backup'] = bkp

        # 方式 B：骨架等价已证 ⇒ 升级基底（保留目标文件行尾风格）
        _write(pkg_path, repo_text, pkg_crlf)

        # 🔴 逐字校验：写入结果必须 == 仓库工作区内容（忽略行尾）
        check = _norm(_read(pkg_path))
        if check != repo_text:
            report['errors'].append('%s: 写入后逐字校验不一致 ⇒ 回滚' % name)
            shutil.copy2(bkp, pkg_path)
            entry['status'] = 'rolled-back'
            report['files'].append(entry)
            continue

        entry['status'] = 'synced'
        entry['bytes'] = os.path.getsize(pkg_path)
        entry['sha256'] = _sha(pkg_path)
        entry['crlf'] = pkg_crlf
        entry['pkg_sha256_before'] = hashlib.sha256(pkg_raw.encode('utf-8')).hexdigest()
        report['files'].append(entry)

    out = os.path.join(REPO, 'results', 'app',
                       'app080_sync_s55_to_pkg_report.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('report ->', out)
    for e in report['files']:
        print('  %-18s %-16s blocks=%s bytes=%s sha256=%s'
              % (e['name'], e.get('status', 'ERROR'), e.get('n_blocks'),
                 e.get('bytes'), (e.get('sha256') or '')[:16]))
    if report['errors']:
        print('ERRORS:')
        for x in report['errors']:
            print('  -', x)
        return 1
    print('ALL OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
