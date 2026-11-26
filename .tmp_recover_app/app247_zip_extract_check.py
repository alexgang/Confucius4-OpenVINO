#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§247（APP-147 自查条件 4）：**解压 zip 到临时目录并跑一次 `--check`**。

步骤：
1. `zipfile.extractall` 到 `shared\zipcheck_v12`（**不在交付目录里**）；
2. 核对解压出的文件数 == zip 中央目录条目数；
3. 用**解压出来的包内 python** 跑 `-s app\live_caption_app.py --check`（Diagnose 同款）；
4. 结论落盘 json；临时目录**不删**（本机有安全删除 shim，删不掉；路径写进证据，
   由用户/后续手工清）。

🔴 判据要点：跑的是**解压出来的那份**（不是源目录、不是开发树）。
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

HOME = r'C:\Users\Trekker-PTL'
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.zip')
TMP = os.path.join(HOME, 'shared', 'zipcheck_v12')
TOP = 'Confucius4_LiveCaption_MiniMVP_v1.2'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app247_zip_extract_check.json'


def main():
    if not os.path.isfile(ZIP):
        print('zip 不存在：%s' % ZIP)
        return 2

    with zipfile.ZipFile(ZIP, 'r') as zf:
        n_entries = len([i for i in zf.infolist() if not i.is_dir()])
        print('zip 条目数 = %d；开始解压 -> %s' % (n_entries, TMP), flush=True)
        t0 = time.time()
        os.makedirs(TMP, exist_ok=True)
        zf.extractall(TMP)
        print('解压完成 %.1f s' % (time.time() - t0), flush=True)

    pkg = os.path.join(TMP, TOP)
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    n_unpacked = sum(len(fns) for _, _, fns in os.walk(pkg))

    res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'zip': ZIP, 'extract_dir': TMP, 'pkg_dir': pkg,
           'n_zip_entries': n_entries, 'n_extracted_files': n_unpacked,
           'files_match': n_unpacked == n_entries}

    if not (os.path.isfile(py) and os.path.isfile(app)):
        res['check_ok'] = False
        res['check_reason'] = '解压后缺 python.exe 或 live_caption_app.py'
        print(res['check_reason'])
    else:
        env = dict(os.environ)
        env.update({'PYTHONNOUSERSITE': '1', 'PYTHONUTF8': '1',
                    'PYTHONPATH': '', 'PYTHONHOME': ''})
        t1 = time.time()
        p = subprocess.run([py, '-s', app, '--check'], cwd=pkg, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=1800)
        el = time.time() - t1
        text = p.stdout.decode('utf-8', errors='replace')
        res.update({'check_rc': p.returncode, 'check_elapsed_s': round(el, 1),
                    'check_stdout': text})
        # 关键地标（存在性判定，不猜语义）
        res['landmarks'] = {
            'has_设备': ('设备' in text),
            'has_ASR': ('ASR' in text),
            'has_MT': ('MT' in text) or ('翻译' in text),
            'has_TTS': ('TTS' in text),
            'has_包内_manifest': ('MANIFEST' in text or '包' in text),
            'traceback': ('Traceback' in text),
        }
        res['check_ok'] = (p.returncode == 0
                           and 'Traceback' not in text)
        print('--check rc=%s，耗时 %.1f s' % (p.returncode, el))
        print('---- --check 输出（尾部 40 行）----')
        print('\n'.join(text.splitlines()[-40:]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\n落盘 ->', OUT)
    ok = bool(res.get('check_ok')) and res['files_match']
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
