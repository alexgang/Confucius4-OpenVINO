#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_verify_player_ufffd.py —— §251：**独立**复核 player.js 的 U+FFFD 修复。

🔴 **不复用修法脚本的自证** ⇒ 另起脚本、用**不同的方法**重算：
   ① 与备份逐字节 diff ⇒ 只有那 9→3 字节变了（且**行数不变**）
   ② U+FFFD 计数归零（整文件）
   ③ 整文件是合法 UTF-8（不靠 errors='replace'）
   ④ 复原后的句子在**正确位置**（前后锚点）
   ⑤ **反证组**：把修好的文件里的 `出` 改回 3×U+FFFD ⇒ 闸门必须 FAIL
      （证明闸门对这个缺陷**有鉴别力**，不是「反正都过」）
   ⑥ 拿修好的文件当 `--pkg` 跑一次真实闸门 ⇒ PASS
   ⑦ **反证组（反向）**：故意在副本里重新注入 U+FFFD ⇒ 闸门必须 FAIL
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EXT = r'C:\Users\Trekker-PTL\live_dub_ext'
TARGET = os.path.join(EXT, 'extension', 'player.js')
BAK = os.path.join(EXT, '.tmp', 'app251', 'player.js.bak_app251_ufffd')
GATE = os.path.join(REPO, 'check_internal_material.py')

PASS = []
FAIL = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)


def run_gate(pkg):
    r = subprocess.run([sys.executable, GATE, '--pkg', pkg],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=900, cwd=REPO)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    print('=' * 72)
    print('§251 独立复核：player.js U+FFFD 修复（换方法重算，不采信修法脚本自证）')
    print('=' * 72)

    new = io.open(TARGET, 'rb').read()
    old = io.open(BAK, 'rb').read()

    # ① 逐字节 diff：只有一处变了，且行数不变
    i = 0
    while i < min(len(old), len(new)) and old[i] == new[i]:
        i += 1
    j = 0
    while j < min(len(old), len(new)) - i and old[len(old) - 1 - j] == new[len(new) - 1 - j]:
        j += 1
    old_span = old[i:len(old) - j]
    new_span = new[i:len(new) - j]
    check('① 差异只有一处（old=%d B → new=%d B）' % (len(old_span), len(new_span)),
          len(old_span) == 9 and len(new_span) == 3
          and old_span == b'\xef\xbf\xbd' * 3 and new_span == '出'.encode('utf-8'),
          'old=%r new=%r' % (old_span[:12], new_span))
    check('①b 行数不变（改的是行内，不增删行）',
          old.count(b'\n') == new.count(b'\n'),
          '%d vs %d' % (old.count(b'\n'), new.count(b'\n')))
    check('①c 文件行尾风格不变（CRLF/LF 计数相等）',
          old.count(b'\r\n') == new.count(b'\r\n'),
          'crlf %d vs %d' % (old.count(b'\r\n'), new.count(b'\r\n')))

    # ② U+FFFD 归零
    check('② 整文件 U+FFFD = 0', new.count(b'\xef\xbf\xbd') == 0,
          'count=%d' % new.count(b'\xef\xbf\xbd'))

    # ③ 合法 UTF-8
    try:
        t = new.decode('utf-8')
        ok = True
    except UnicodeDecodeError as e:
        t, ok = '', False
        print('   decode error:', e)
    check('③ 整文件是合法 UTF-8（严格解码）', ok)

    # ④ 句子在正确位置
    check('④ 复原后的完整句子在正确位置',
          '每段配音都要能算出同步误差' in t
          and 'EXT-034 ①：**每段配音都要能算出同步误差**（不靠 onset 配对）' in t)

    tmp = tempfile.mkdtemp(prefix='app251_verify_')
    try:
        # ⑥ 真实闸门：把修好的文件放进一个临时包 ⇒ 必须 PASS
        pkg_ok = os.path.join(tmp, 'pkg_fixed')
        os.makedirs(os.path.join(pkg_ok, 'ext', 'extension'))
        with io.open(os.path.join(pkg_ok, 'ext', 'extension', 'player.js'), 'wb') as f:
            f.write(new)
        rc, out = run_gate(pkg_ok)
        check('⑥ 修好的文件 ⇒ 内部素材闸门 PASS（rc=0）', rc == 0,
              'rc=%r' % rc)

        # ⑦ 反证组：把 U+FFFD 重新注入副本 ⇒ 闸门必须 FAIL（判据有鉴别力）
        pkg_bad = os.path.join(tmp, 'pkg_bad')
        os.makedirs(os.path.join(pkg_bad, 'ext', 'extension'))
        with io.open(os.path.join(pkg_bad, 'ext', 'extension', 'player.js'), 'wb') as f:
            f.write(old)          # 旧文件（带 U+FFFD）
        rc2, out2 = run_gate(pkg_bad)
        check('⑦ 反证组：注入 U+FFFD 的副本 ⇒ 闸门 FAIL（rc=1）', rc2 == 1,
              'rc=%r' % rc2)
        check('⑦b 闸门确实点名了 player.js（不是别的理由 FAIL）',
              'player.js' in out2 and 'U+FFFD' in out2,
              (out2.strip().splitlines()[-1] if out2.strip() else ''))

        # ⑤ 反证组：把修好的文件里的「出」改回 3×U+FFFD ⇒ 闸门必须 FAIL
        pkg_anti = os.path.join(tmp, 'pkg_anti')
        os.makedirs(os.path.join(pkg_anti, 'ext', 'extension'))
        mutated = t.replace('每段配音都要能算出同步误差',
                            '每段配音都要能算' + '�' * 3 + '同步误差')
        with io.open(os.path.join(pkg_anti, 'ext', 'extension', 'player.js'), 'wb') as f:
            f.write(mutated.encode('utf-8'))
        rc3, out3 = run_gate(pkg_anti)
        check('⑤ 反证组：把「出」改回 U+FFFD ⇒ 闸门 FAIL（rc=1）', rc3 == 1,
              'rc=%r' % rc3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 72)
    print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：%s' % FAIL)
    verdict = 'PASS' if not FAIL else 'FAIL'
    print('总判定：%s' % verdict)
    print('=' * 72)

    ev = os.path.join(HERE, 'app251_player_ufffd_verify.json')
    with io.open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(
            target=TARGET,
            backup=BAK,
            bytes_before=len(old), bytes_after=len(new),
            sha256_before=hashlib.sha256(old).hexdigest(),
            sha256_after=hashlib.sha256(new).hexdigest(),
            old_span_hex=old_span.hex(), new_span_hex=new_span.hex(),
            pass_list=PASS, fail_list=FAIL, verdict=verdict),
            f, ensure_ascii=False, indent=1)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
