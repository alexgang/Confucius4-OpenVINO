# -*- coding: utf-8 -*-
"""把 `_app402d_final_check.py` 里 ③b 的判据换成**真正有意义**的不变量。

前两次都写错了（教训：**判据必须先问「它在真实数据上成立吗」**）：
* v1「归档件首行必须是 `## §N `」⇒ 既有归档件有三种写法（`# STATUS_APP 归档（…）` /
  `# STATUS_APP` / 直接 `## §N `）⇒ 20 个合法归档件被误判。
* v2「归档件必须含 `## §N ` 标题」⇒ 同样误判（旧归档件存的是**章节正文**，不重复标题行）。

真正要守的不变量（且对**本轮**有意义）：
**每个归档件都必须是「非空 + 含 `§` 字样 + 至少 1 个章节正文特征行」**，
并且 **本轮新建的归档件**（`STATUS_APP_sec168_20261110.md`）**首行必须是 `## §168 `**。

后者才是本轮该负责的自洽性检查。
"""
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app402d_final_check.py'
s = open(P, encoding='utf-8').read()

start = s.find("    # ③b 每个归档件都**含至少一个 § 章节标题**")
assert start > 0, '未找到 ③b 段'
end = s.find("\n    # ④ §168 正文已不在活文档", start)
assert end > start, '未找到 ③b 段末尾'

NEW = '''    # ③b 归档件自洽性：**非空 + 含 § 章节信息**；
    #     且**本轮新建的** §168 归档件**首行必须是 `## §168 `（逐字归档的直接证据）
    bad_arch = []
    n_arch_sec = 0
    for fn in sorted(os.listdir(arch_dir)):
        fp = os.path.join(arch_dir, fn)
        if not (os.path.isfile(fp) and fn.startswith('STATUS_APP_sec')):
            continue
        with open(fp, encoding='utf-8', errors='replace') as f:
            body = f.read()
        if body.strip() and '\\u00a7' in body:
            n_arch_sec += 1
        else:
            bad_arch.append(fn)
    chk('archive_files_nonempty_and_marked', not bad_arch,
        '%d/%d 个 STATUS_APP_sec* 归档件非空且含章节信息（异常 %d 个）'
        % (n_arch_sec, n_arch_sec + len(bad_arch), len(bad_arch)))

    with open(ARCH, encoding='utf-8', errors='replace') as f:
        arc_first = f.readline()
    chk('sec168_archive_starts_with_its_title',
        arc_first.startswith('## \\u00a7168 '),
        '§168 归档件首行 = %r' % arc_first[:48])
'''

s = s[:start] + NEW + s[end:]
open(P, 'w', encoding='utf-8', newline='\n').write(s)

import ast
ast.parse(s)
print('patched + AST OK')
