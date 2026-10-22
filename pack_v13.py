"""打包客户包 v1.3 并校验。

步骤：zip → testzip() → 抽查关键文件（MT2 模型、translator.py、MANIFEST、README）。
"""
import hashlib
import os
import sys
import time
import zipfile

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3.zip'
PREFIX = 'Confucius4_LiveCaption_v1.3'

# 必须存在于 zip 内的关键文件（相对 PREFIX/）
MUST = [
    'app/translator.py',
    'app/live_caption_app.py',
    'app/MANIFEST.json',
    'README_zh.md',
    'README_en.md',
    'THIRD_PARTY.md',
    'Start_LiveCaption.bat',
    'Diagnose.bat',
    'models/mt/mt2-int4sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int4sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int4sym-cw-q/config.json',
    'models/mt/mt2-int4sym-cw-q/chat_template.jinja',
]

# 必须**不存在**于 zip 内的路径（旧的 Instruct 产物 / 备份文件 / v1.3 已移除的 INT8）
MUST_NOT = [
    'app/translator.py.bak_instruct_20261022',
    'models/mt/int4sym-cw-q/openvino_model.bin',
    'models/mt/int8sym-cw-q/openvino_model.bin',
    # v1.3 只附带 INT4 —— INT8 必须不在包内
    'models/mt/mt2-int8sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int8sym-cw-q/openvino_model.bin',
]


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    t0 = time.time()
    print('=' * 70)
    print(f'打包 {PREFIX}')
    print('=' * 70)
    print('源目录:', PKG)
    print('输出  :', ZIP)
    print()

    if os.path.exists(ZIP):
        os.remove(ZIP)

    n_files = 0
    total_raw = 0
    with zipfile.ZipFile(ZIP, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zf:
        for dirpath, dirnames, filenames in os.walk(PKG):
            dirnames.sort()
            for fn in sorted(filenames):
                full = os.path.join(dirpath, fn)
                if os.path.islink(full) and not os.path.exists(full):
                    continue
                rel = os.path.relpath(full, PKG).replace('\\', '/')
                arc = f'{PREFIX}/{rel}'
                zf.write(full, arc)
                n_files += 1
                total_raw += os.path.getsize(full)
                if n_files % 2000 == 0:
                    print(f'  ... {n_files} 文件')

    sz = os.path.getsize(ZIP)
    print()
    print(f'文件数     : {n_files}')
    print(f'原始字节   : {total_raw}')
    print(f'压缩后字节 : {sz}  ({sz / 1024 ** 3:.2f} GB)')
    print(f'压缩率     : {sz / total_raw * 100:.1f}%')
    print(f'耗时       : {time.time() - t0:.0f}s')
    print()

    print('-' * 70)
    print('testzip() 校验…')
    with zipfile.ZipFile(ZIP, 'r') as zf:
        bad = zf.testzip()
        if bad is None:
            print('  Everything is Ok')
        else:
            print('  !!! 损坏条目:', bad)
            return 1

        names = set(zf.namelist())
        print()
        print('关键文件抽查：')
        missing = []
        for rel in MUST:
            arc = f'{PREFIX}/{rel}'
            ok = arc in names
            if not ok:
                missing.append(rel)
            size = zf.getinfo(arc).file_size if ok else 0
            print(f'  [{"OK" if ok else "缺"}] {rel}  ({size:,} bytes)')

        print()
        print('旧产物应已移除：')
        stale = []
        for rel in MUST_NOT:
            arc = f'{PREFIX}/{rel}'
            ok = arc not in names
            if not ok:
                stale.append(rel)
            print(f'  [{"已移除" if ok else "仍在"}] {rel}')

        # MANIFEST 版本
        import json
        man = json.loads(zf.read(f'{PREFIX}/app/MANIFEST.json').decode('utf-8'))
        print()
        print(f'MANIFEST version = {man["version"]}  files={man["files"]}  bytes={man["bytes"]}')

        # translator.py 关键符号抽查
        src = zf.read(f'{PREFIX}/app/translator.py').decode('utf-8')
        syms = ['mt2-int4sym-cw-q', '_TRANSLATE_INSTR', 'Default Translation',
                'stop_strings = set()', 'split_sentences']
        print()
        print('translator.py 符号抽查：')
        for s in syms:
            print(f'  [{"有" if s in src else "缺"}] {s}')

        # 翻译模型目录清单：v1.3 只允许 INT4
        mt_dirs = sorted({n[len(f'{PREFIX}/models/mt/'):].split('/')[0]
                           for n in names
                           if n.startswith(f'{PREFIX}/models/mt/') and '/' in n[len(f'{PREFIX}/models/mt/'):]})
        print()
        print(f'包内翻译模型目录: {mt_dirs}')
        only_int4 = mt_dirs == ['mt2-int4sym-cw-q']
        print(f'  [{"符合" if only_int4 else "不符"}] v1.3 只附带 INT4')

    print()
    if missing or stale or not only_int4:
        print('结论：FAIL')
        return 1
    print(f'结论：PASS  md5={md5(ZIP)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
