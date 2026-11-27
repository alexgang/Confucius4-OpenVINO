"""APP-157 §6：解压 zip 到**隔离路径**（与开发目录无父子/兄弟关系），跑包内 --check。
本机有安全删除 shim ⇒ 不删解压目录；路径写进证据，收尾由用户/后续手工清。
"""
import json
import os
import subprocess
import time
import zipfile

HOME = r'C:\Users\Trekker-PTL'
ZIP = os.path.join(HOME, 'LiveCaption_MiniMVP_v1.2.1.zip')
TMP = r'C:\Temp\verify_v121_app157'
TOP = 'LiveCaption_MiniMVP_v1.2.1'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_zip_extract_check.json'


def main():
    if not os.path.isfile(ZIP):
        print('zip 不存在：%s' % ZIP)
        return 2
    with zipfile.ZipFile(ZIP, 'r') as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        n_entries = len(infos)
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
        res['landmarks'] = {
            'has_ASR': 'ASR' in text, 'has_MT': ('MT' in text or '翻译' in text),
            'has_TTS': 'TTS' in text, 'has_MANIFEST': 'MANIFEST' in text,
            'traceback': 'Traceback' in text,
            'gui_title_v121': "_WINDOW_TITLE = '实时字幕 MiniMVP v1.2.1'" in
                              open(app, encoding='utf-8', errors='replace').read(),
        }
        res['check_ok'] = p.returncode == 0 and 'Traceback' not in text
        print('--check rc=%s，耗时 %.1f s' % (p.returncode, el))
        print('\n'.join(text.splitlines()[-30:]))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    ok = bool(res.get('check_ok')) and res['files_match']
    print('结论：%s -> %s' % ('PASS' if ok else 'FAIL', OUT))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
