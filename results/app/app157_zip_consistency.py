"""APP-157/APP-148 §1b：zip 中央目录 vs 包目录逐个比相对路径+原始大小，并跑 testzip() CRC。
不做 SHA（APP-145）。执行时 zip 必须已打完。
"""
import json
import os
import time
import zipfile

CAND = r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1'
ZIP = CAND + '.zip'
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app157_zip_consistency.json'


def scan_dir(root):
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


def main():
    out = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'zip': ZIP, 'candidate_dir': CAND,
           'method': 'zipfile.infolist() central directory vs directory walk '
                     '(relative path + file_size) + testzip() CRC (NO SHA)'}
    if not os.path.isfile(ZIP):
        print('zip 不存在：%s' % ZIP)
        return 2
    zf = zipfile.ZipFile(ZIP, 'r')
    prefix = os.path.basename(os.path.normpath(CAND)) + '/'
    zmap, no_prefix = {}, []
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace('\\', '/')
        if name.startswith(prefix):
            name = name[len(prefix):]
        else:
            no_prefix.append(name)
        zmap[name] = info.file_size
    out['n_zip_entries'] = len(zmap)
    out['top_prefix'] = prefix
    out['entries_without_prefix'] = {'count': len(no_prefix), 'sample': sorted(no_prefix)[:20]}
    dmap = scan_dir(CAND)
    out['n_dir_files'] = len(dmap)
    only_zip = sorted(set(zmap) - set(dmap))
    only_dir = sorted(set(dmap) - set(zmap))
    size_diff = sorted(k for k in (set(zmap) & set(dmap)) if zmap[k] != dmap[k])
    out['only_in_zip'] = {'count': len(only_zip), 'sample': only_zip[:20]}
    out['only_in_dir'] = {'count': len(only_dir), 'sample': only_dir[:20]}
    out['size_differs'] = {'count': len(size_diff), 'sample': size_diff[:20]}
    out['bak_entries'] = [k for k in zmap if '.bak' in k.lower()]
    out['stale_readme_entries'] = [k for k in zmap if k.startswith('README')
                                   and k.endswith('.bak_app154_docclean')]
    bad = zf.testzip()
    out['testzip_result'] = bad
    out['testzip_ok'] = (bad is None)
    zf.close()
    out['verdict'] = {
        'three_counts_zero': not (only_zip or only_dir or size_diff),
        'all_entries_have_top_prefix': not no_prefix,
        'crc_ok': out['testzip_ok'],
        'n_entries_equal': len(zmap) == len(dmap),
        'no_bak_entries': not out['bak_entries'],
    }
    print('zip=%d 目录=%d；只在zip=%d 只在目录=%d 大小不同=%d；testzip=%s；bak条目=%d' %
          (len(zmap), len(dmap), len(only_zip), len(only_dir), len(size_diff),
           bad, len(out['bak_entries'])))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    ok = all(out['verdict'].values())
    print('判定 %s -> %s' % ('PASS' if ok else 'FAIL', OUT))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
