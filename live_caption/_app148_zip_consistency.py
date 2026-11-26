"""APP-148 §1b：**zip 与候选目录一致（不算哈希）**。

reviewer 原文：
* 用 `zipfile.ZipFile(...).infolist()` 读中央目录，和候选目录逐个比较
  **相对路径**和**原始大小**（`file_size`），报：**条目数**、
  **只在 zip 里的**、**只在目录里的**、**大小不同的**（三项都应为 0）；
* 另外跑一次 `ZipFile.testzip()`（用 zip 自带的 CRC 检查，**不另算哈希**）。

🔴 口径：**不做 SHA**（APP-145）⇒ 只用中央目录的相对路径 + `file_size` + CRC。
"""
import json
import os
import sys
import time
import zipfile

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2'
ZIP = r'C:\Users\Trekker-PLT_PLACEHOLDER'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app148_zip_consistency.json'


def scan_dir(root):
    """扫目录 ⇒ {相对路径(正斜杠): 文件大小}"""
    out = {}
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace('\\', '/')
            try:
                out[rel] = os.path.getsize(full)
            except OSError:
                pass
    return out


def main(zip_path=CAND + '.zip', cand=CAND):
    out = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'zip': zip_path, 'candidate_dir': cand,
           'method': 'zipfile.infolist() central directory vs directory walk '
                     '(relative path + file_size) + testzip() CRC (NO SHA)'}
    if not os.path.isfile(zip_path):
        print('zip 不存在：%s' % zip_path)
        return 2

    zf = zipfile.ZipFile(zip_path, 'r')
    zmap = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        zmap[info.filename.replace('\\', '/')] = info.file_size
    out['n_zip_entries'] = len(zmap)

    dmap = scan_dir(cand)
    out['n_dir_files'] = len(dmap)

    only_zip = sorted(set(zmap) - set(dmap))
    only_dir = sorted(set(dmap) - set(zmap))
    size_diff = sorted(k for k in (set(zmap) & set(dmap)) if zmap[k] != dmap[k])

    out['only_in_zip'] = {'count': len(only_zip), 'sample': only_zip[:20]}
    out['only_in_dir'] = {'count': len(only_dir), 'sample': only_dir[:20]}
    out['size_differs'] = {'count': len(size_diff), 'sample': size_diff[:20]}

    # zip 自带的 CRC 检查（**不另算哈希**）
    bad = zf.testzip()
    out['testzip_result'] = bad
    out['testzip_ok'] = (bad is None)
    zf.close()

    out['verdict'] = {
        'three_counts_zero': (len(only_zip) == 0 and len(only_dir) == 0
                              and len(size_diff) == 0),
        'crc_ok': out['testzip_ok'],
        'n_entries_equal': (len(zmap) == len(dmap)),
    }
    print('zip 条目数 = %d，目录文件数 = %d' % (len(zmap), len(dmap)))
    print('只在 zip 里 = %d；只在目录里 = %d；大小不同 = %d'
          % (len(only_zip), len(only_dir), len(size_diff)))
    for nm, lst in (('only_in_zip', only_zip), ('only_in_dir', only_dir),
                    ('size_differs', size_diff)):
        if lst:
            print('  %s sample: %s' % (nm, lst[:5]))
    print('testzip() = %s（None 表示 CRC 全部通过）' % bad)
    print('\n判定：%s' % json.dumps(out['verdict'], ensure_ascii=False))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('落盘 ->', OUT)
    ok = out['verdict']['three_counts_zero'] and out['verdict']['crc_ok']
    return 0 if ok else 1


if __name__ == '__main__':
    args = sys.argv[1:]
    z = args[0] if len(args) > 0 else (CAND + '.zip')
    c = args[1] if len(args) > 1 else CAND
    sys.exit(main(z, c))
