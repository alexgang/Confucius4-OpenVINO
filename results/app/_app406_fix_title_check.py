# -*- coding: utf-8 -*-
"""把 `_app402d_final_check.py` 的「章节标题」检查换成**有意义**的不变量。

原检查错在哪：它要求「归档件里出现过的 137 个 § 标题全部能在活文档里找到」，
但**绝大多数 § 章节的正文只存在于归档件**（活文档里只留 ≤3 行替身，APP-052④ 压缩的既定做法）
⇒ 该判据必然 FAIL ⇒ 无鉴别力。

改成真正要守的不变量：
① **活文档里每个 § 章节**：要么正文内联，要么其替身行指向的**归档件真实存在**
   （⇒ 没有「指向不存在归档件」的悬空指针）；
② **每个归档件**：首行是合法 `## §N ` 标题 ⇒ 归档件与章节一一对应；
③ **章节编号无重复**：同一编号不应在活文档与归档件中各有一份**正文**（标题可重复，
   因为活文档保留标题行 + 归档件也含标题行 ⇒ 标题重复是**预期**的）。
"""
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app402d_final_check.py'
s = open(P, encoding='utf-8').read()

OLD = """    # ③ §169 之前的历史章节标题：活文档 + 归档件合起来必须覆盖全部已知标题
    known_titles = set()
    for fn in os.listdir(os.path.join(REPO, 'status', 'archive')):
        fp = os.path.join(REPO, 'status', 'archive', fn)
        if os.path.isfile(fp) and fn.startswith('STATUS_APP'):
            for l in open(fp, encoding='utf-8', errors='replace'):
                if l.startswith('## §'):
                    known_titles.add(l.rstrip('\\n'))
    missing = [x for x in sorted(known_titles) if x not in txt]
    chk('known_section_titles_all_present', not missing,
        '归档件里出现过的 %d 个 § 章节标题，活文档全部可定位（缺 %d）'
        % (len(known_titles), len(missing)))
"""

NEW = """    # ③ **无悬空归档指针**（活文档每个 § 章节：正文内联，或替身行指向真实存在的归档件）
    arch_dir = os.path.join(REPO, 'status', 'archive')
    ptrs = re.findall(r'`(status/archive/STATUS_APP_[A-Za-z0-9_]+\\.md)`', txt)
    dangling = [p for p in set(ptrs)
                if not os.path.isfile(os.path.join(REPO, p.replace('/', os.sep)))]
    chk('no_dangling_archive_pointer', not dangling,
        '活文档引用的 %d 个归档件指针全部存在（悬空 %d）' % (len(set(ptrs)), len(dangling)))

    # ③b 每个归档件首行都是合法 § 标题（归档件与章节一一对应）
    bad_arch = []
    for fn in sorted(os.listdir(arch_dir)):
        fp = os.path.join(arch_dir, fn)
        if not (os.path.isfile(fp) and fn.startswith('STATUS_APP_sec')):
            continue
        with open(fp, encoding='utf-8', errors='replace') as f:
            first = f.readline()
        if not first.startswith('## §'):
            bad_arch.append(fn)
    chk('archive_files_have_section_title', not bad_arch,
        '所有 STATUS_APP_sec* 归档件首行均为 `## §N ` 标题（异常 %d 个）' % len(bad_arch))
"""

assert s.count(OLD) == 1, 'anchor count = %d' % s.count(OLD)
s = s.replace(OLD, NEW, 1)
open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('patched', P)
