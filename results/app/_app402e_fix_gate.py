# -*- coding: utf-8 -*-
"""重写 `live_caption/assert_status_citations.py` 的 `scan()` 函数（修缩进 + 加 documented 分类）。"""
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\live_caption\assert_status_citations.py'
s = open(P, encoding='utf-8').read()

NEW = '''    def scan(file_list):
        """返回 (per_file, ok, bad, known, placeholder, abs_paths, external, documented)。"""
        per_file = []
        ok, bad, known, placeholder, abs_paths, external = [], [], [], [], [], []
        documented = []
        for fp in file_list:
            raw = open(fp, 'rb').read()
            text = raw.decode('utf-8', errors='replace')
            cited = collect(text)
            pf = {'file': os.path.relpath(fp, REPO).replace('\\\\', '/'),
                  'bytes': len(raw), 'sha256': sha256_of(fp), 'n_cited': len(cited)}
            f_bad = []
            for p in sorted(cited):
                norm = p.replace('\\\\', '/')
                if ABSPATH_RE.match(norm):
                    abs_paths.append(p)
                    continue
                if PLACEHOLDER_RE.search(norm):
                    placeholder.append(p)
                    continue
                if any(os.path.exists(c) for c in candidate_roots(norm)):
                    ok.append(p)
                    continue
                if norm in KNOWN_PHANTOM:
                    known.append({'path': p, 'note': KNOWN_PHANTOM[norm],
                                  'file': pf['file']})
                    continue
                hits = idx.get(os.path.basename(norm), [])
                in_repo = [h for h in hits if h.lower().startswith(REPO.lower())]
                if in_repo:
                    actual_rel = [os.path.relpath(h, REPO).replace('\\\\', '/')
                                  for h in in_repo[:3]]
                    item = {'path': p, 'note': '同名文件在别处', 'file': pf['file'],
                            'actual': actual_rel}
                    if _is_documented_correction(text, p, actual_rel):
                        item['note'] = ('同名文件在别处（**同一行已给出正确路径 '
                                        '⇒ 属「已如实记录的错误引用」**）')
                        documented.append(item)
                    else:
                        bad.append(item)
                        f_bad.append(p)
                elif hits:
                    external.append({'path': p,
                                     'note': '在仓库树之外（如客户包 / 其它模块目录）',
                                     'file': pf['file'], 'actual': hits[:3]})
                else:
                    bad.append({'path': p, 'note': '磁盘上找不到', 'file': pf['file'],
                                'actual': []})
                    f_bad.append(p)
            pf['n_bad'] = len(f_bad)
            pf['bad'] = f_bad
            per_file.append(pf)
        return (per_file, ok, bad, known, placeholder, abs_paths, external, documented)
'''

lines = s.split('\n')
start = None
for i, ln in enumerate(lines):
    if ln.strip().startswith('def scan(file_list):'):
        start = i
        break
assert start is not None

end = None
for j in range(start, len(lines)):
    if 'return per_file, ok, bad, known, placeholder, abs_paths, external, documented' in lines[j]:
        end = j
        break
assert end is not None, '未找到 scan 的 return'

new_lines = lines[:start] + NEW.rstrip('\n').split('\n') + lines[end + 1:]
out = '\n'.join(new_lines)
open(P, 'w', encoding='utf-8', newline='\n').write(out)
print('rewrote scan(): lines %d..%d' % (start + 1, end + 1))
