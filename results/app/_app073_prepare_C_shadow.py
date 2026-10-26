#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§53 —— 为「方案 C 补丁」准备**影子副本**并应用补丁（不碰工作区）。

为什么用影子目录：
  补丁必须先验证能干净应用；而 `git apply` 会直接改工作区文件
  ⇒ 一旦补丁不适用就会污染真实工作区（translator.py 归 App，
  改坏了要手工恢复）。
  ⇒ 影子目录里跑一次，能应用才动真文件。

流程：
  1. `git show HEAD:live_caption/translator.py` ⇒ 归一化成 LF（与补丁同格式）
  2. `git apply` 到影子目录
  3. 打印结果（成功/失败）+ 影子文件 SHA256
"""
import hashlib
import os
import shutil
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
SHADOW = r'C:\Users\Trekker-PTL\AppData\Local\Temp\cshadow'
PATCH = r'C:\Users\Trekker-PTL\shared\mt_C_translator.patch'
REL = 'live_caption/translator.py'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    if os.path.isdir(SHADOW):
        shutil.rmtree(SHADOW)
    os.makedirs(os.path.join(SHADOW, 'live_caption'), exist_ok=True)

    raw = subprocess.run(['git', 'show', 'HEAD:' + REL], cwd=REPO,
                         capture_output=True, check=True).stdout.decode('utf-8')
    lf = raw.replace('\r\n', '\n')
    tgt = os.path.join(SHADOW, REL)
    with open(tgt, 'w', encoding='utf-8', newline='\n') as f:
        f.write(lf)
    print('shadow %s  bytes=%d  sha256=%s' % (REL, len(lf), sha256_file(tgt)))
    print('HEAD  %s  bytes=%d' % (REL, len(raw)))

    r = subprocess.run(['git', 'apply', '--ignore-whitespace', '-v', PATCH],
                       cwd=SHADOW, capture_output=True)
    print('--- git apply rc=%d ---' % r.returncode)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    err = (r.stderr or b'').decode('utf-8', 'replace')
    if out.strip():
        print(out.strip())
    if err.strip():
        print('STDERR:', err.strip())
    if r.returncode != 0:
        print('RESULT: FAIL —— 补丁不能干净应用')
        return 1
    new = open(tgt, 'rb').read()
    print('patched bytes=%d  sha256=%s' % (len(new), sha256_file(tgt)))
    # 语法自检（不 import，只编译）
    import py_compile
    try:
        py_compile.compile(tgt, doraise=True, cfile=os.path.join(SHADOW, '_t.pyc'))
        print('RESULT: PASS —— 补丁干净应用且语法正确')
    except Exception as e:
        print('RESULT: FAIL —— 语法错误:', e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
