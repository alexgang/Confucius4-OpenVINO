"""增量替换 zip 内的指定文件（不重打 8.5 GB）。

做法：读出 zip 内所有条目到内存 → 替换目标文件 → 写新 zip。
8.5 GB 读写约需 2–3 分钟，比重新打包（15 分钟）快。

默认替换 README_zh.md / README_en.md；命令行可传任意包内相对路径，
例如：
    python patch_zip_readme.py app/translator.py
"""
import os
import shutil
import sys
import time
import zipfile

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3.zip'
PREFIX = 'Confucius4_LiveCaption_v1.3'
REPLACE = ['README_zh.md', 'README_en.md']


def main():
    t0 = time.time()
    tmp = ZIP + '.tmp'
    replaced = []

    # 命令行给的相对路径 → 形如 app/translator.py；默认用 README
    targets = list(REPLACE)
    if len(sys.argv) > 1:
        targets = [a.replace('\\', '/').lstrip('/') for a in sys.argv[1:]]

    with zipfile.ZipFile(ZIP, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zout:
        for item in zin.infolist():
            rel = item.filename[len(PREFIX) + 1:] if item.filename.startswith(PREFIX + '/') else None
            if rel in targets:
                # 用磁盘上的最新版替换
                with open(os.path.join(PKG, *rel.split('/')), 'rb') as f:
                    data = f.read()
                info = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = item.external_attr
                zout.writestr(info, data)
                replaced.append((rel, item.file_size, len(data)))
            else:
                zout.writestr(item, zin.read(item.filename))

    os.replace(tmp, ZIP)
    print('已替换：')
    for b, old, new in replaced:
        print(f'  {b}: {old:,} -> {new:,} bytes')
    print(f'新 zip: {os.path.getsize(ZIP):,} bytes  耗时 {time.time() - t0:.0f}s')

    # 校验
    with zipfile.ZipFile(ZIP, 'r') as z:
        print('testzip:', z.testzip() or 'Everything is Ok')
        for rel in targets:
            src = z.read(f'{PREFIX}/{rel}').decode('utf-8', 'replace')
            print(f'{rel}: {len(src):,} chars')
            if rel.endswith('translator.py'):
                print('  含小写 qs 条目:', "'qs':" in src)
                print('  含小写 es 条目:', "'es':" in src)
            elif rel == 'README_zh.md':
                print('  含术语表章节:', '术语表' in src)
                print('  含 --mt-glossary:', '--mt-glossary' in src)
            elif rel == 'README_en.md':
                print('  EN 含 Glossary:', 'Glossary' in src)
                print('  EN 含 --mt-glossary:', '--mt-glossary' in src)


if __name__ == '__main__':
    main()
