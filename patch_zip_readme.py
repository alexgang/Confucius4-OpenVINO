"""只替换 zip 里的 README_zh.md / README_en.md（增量更新，不重打 8.5 GB）。

做法：读出 zip 内所有条目到内存 → 替换两个 README → 写新 zip。
8.5 GB 读写约需 2–3 分钟，比重新打包（15 分钟）快。
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

    with zipfile.ZipFile(ZIP, 'r') as zin, \
         zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as zout:
        for item in zin.infolist():
            base = item.filename.split('/')[-1]
            if base in REPLACE and item.filename.startswith(PREFIX + '/'):
                # 用磁盘上的最新版替换
                with open(os.path.join(PKG, base), 'rb') as f:
                    data = f.read()
                info = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = item.external_attr
                zout.writestr(info, data)
                replaced.append((base, item.file_size, len(data)))
            else:
                zout.writestr(item, zin.read(item.filename))
            if zin.fp.tell() % (1 << 30) < 1 << 20:
                pass

    os.replace(tmp, ZIP)
    print('已替换：')
    for b, old, new in replaced:
        print(f'  {b}: {old:,} -> {new:,} bytes')
    print(f'新 zip: {os.path.getsize(ZIP):,} bytes  耗时 {time.time() - t0:.0f}s')

    # 校验
    with zipfile.ZipFile(ZIP, 'r') as z:
        print('testzip:', z.testzip() or 'Everything is Ok')
        src = z.read(f'{PREFIX}/README_zh.md').decode('utf-8')
        print('含术语表章节:', '术语表' in src)
        print('含 --mt-glossary:', '--mt-glossary' in src)
        src_en = z.read(f'{PREFIX}/README_en.md').decode('utf-8')
        print('EN 含 Glossary:', 'Glossary' in src_en)
        print('EN 含 --mt-glossary:', '--mt-glossary' in src_en)


if __name__ == '__main__':
    main()
