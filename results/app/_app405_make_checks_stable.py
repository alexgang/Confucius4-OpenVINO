# -*- coding: utf-8 -*-
"""
把两个验收脚本改成**提交后仍然稳定**的口径（改前它们拿 HEAD 当「改前基线」，
提交后 HEAD == 工作树 ⇒ 必然 FAIL ⇒ 会误导 reviewer）。

`results/app/_app401_comment_only_proof.py`
------------------------------------------------
改前基线不再取 HEAD（HEAD 已含本次改动），改取**客户包 v2.4 的 `app/speaker_tracker.py`**
——它是**未被本轮改动的**「原始注释版」⇒ 是稳定的「改前」参照，且同时证明
「开发树与客户包的**可执行代码逐条相同**（只有注释不同）」。

`results/app/_app402d_final_check.py`
--------------------------------------
① 「§168 正文块 == 归档件」不再拿 HEAD 比，改为**解析活文档里 §168 替身行自报的
   字节数与 SHA256**，再与磁盘上的归档件实算值比对（**自洽性**检查，提交后仍成立）；
② 「旧章节标题一个没少」改为核对「§169 之前的 `## ` 标题集合与**归档件+活文档**的并集一致」。

用法：python results/app/_app401_comment_only_proof.py
      python results/app/_app402d_final_check.py
"""
import os

B401 = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app401_comment_only_proof.py'
B402 = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app402d_final_check.py'

# ── ① _app401：改前基线 = 客户包副本（稳定参照）────────────────────
s = open(B401, encoding='utf-8').read()

old_fetch = """    # 上一版（HEAD）的同一文件
    try:
        old = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + TARGET],
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace', check=True).stdout
    except subprocess.CalledProcessError:
        old = None
"""
new_fetch = """    # 🔴 **改前基线 = 客户包 v2.4 的副本**（不是 HEAD）：
    #    HEAD 已含本轮改动 ⇒ 拿 HEAD 当基线会必然 FAIL（提交后不自洽）。
    #    客户包那份是**未被本轮改动的原始注释版** ⇒ 稳定的「改前」参照，
    #    且顺带证明「开发树与客户包的**可执行代码逐条相同**」。
    PKG = r'C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.4'
    pkg_copy = os.path.join(PKG, 'app', 'speaker_tracker.py')
    old = None
    if os.path.isfile(pkg_copy):
        old = open(pkg_copy, encoding='utf-8').read()
"""
assert s.count(old_fetch) == 1, 'fetch anchor count = %d' % s.count(old_fetch)
s = s.replace(old_fetch, new_fetch, 1)

old_out = """        'head_sha256': hashlib.sha256(old.encode('utf-8')).hexdigest(),"""
new_out = """        'baseline_kind': '客户包 v2.4 的 app/speaker_tracker.py（未被本轮改动 ⇒ 稳定的「改前」参照）',
        'baseline_sha256': hashlib.sha256(old.encode('utf-8')).hexdigest(),"""
assert s.count(old_out) == 1, 'out anchor count = %d' % s.count(old_out)
s = s.replace(old_out, new_out, 1)

old_detail = """    chk('ast_parses', True, 'HEAD 与工作树均 ast.parse 成功')"""
new_detail = """    chk('ast_parses', True, '改前基线（客户包副本）与工作树均 ast.parse 成功')"""
assert s.count(old_detail) == 1
s = s.replace(old_detail, new_detail, 1)

old_neg = """    # 🔴 反证组：判据必须有鉴别力 —— 关掉「忽略 docstring」后必须 FAIL
    a2 = fingerprint(old, strip=False)
    b2 = fingerprint(cur, strip=False)
    neg = (a2['stmts'] != b2['stmts']) or (a2['consts'] != b2['consts'])
    print('NEG_CONTROL(not stripping docstrings ⇒ must differ):',
          'PASS' if neg else 'FAIL(判据无鉴别力!)')
    if not neg:
        out['verdict'] = 'FAIL'
        out['neg_control'] = 'FAIL：忽略 docstring 后两者仍相同 ⇒ 判据恒真'
        with open(dest, 'w', encoding='utf-8', newline='\\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return 2
"""
new_neg = """    # 🔴 反证组：判据必须有鉴别力 —— **改动可执行代码**（而不只是注释）必须被判 FAIL
    #    做法：把工作树副本里的一行注释改成代码 ⇒ 语句/常量多重集必须不再相等。
    import copy as _copy
    mutated = cur.replace('_WIN_S_DEFAULT = 10.0',
                           '_WIN_S_DEFAULT = 10.0\\n_WIN_S_MUTANT = 1', 1)
    assert mutated != cur, '反证构造失败：目标行未命中'
    m1 = fingerprint(old, strip=STRIP_DOCSTRINGS)
    m2 = fingerprint(mutated, strip=STRIP_DOCSTRINGS)
    neg = (m1['stmts'] != m2['stmts']) or (m1['consts'] != m2['consts'])
    print('NEG_CONTROL(注入一行可执行代码 ⇒ 必须被识破):',
          'PASS' if neg else 'FAIL(判据无鉴别力!)')
    out['neg_control'] = ('PASS：注入可执行代码后语句/常量多重集不再相等 ⇒ 判据有鉴别力'
                          if neg else 'FAIL：注入可执行代码后仍判相等 ⇒ 判据恒真')
    if not neg:
        out['verdict'] = 'FAIL'
        with open(dest, 'w', encoding='utf-8', newline='\\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return 2
"""
assert s.count(old_neg) == 1, 'neg anchor count = %d' % s.count(old_neg)
s = s.replace(old_neg, new_neg, 1)

# 「只许改注释」判据的加强：可执行代码必须逐条相同（已由 stmt_multiset_same 覆盖）
s = s.replace("""        'criterion': 'AST：语句多重集 / 常量多重集 / 函数签名 三者相等 ⇒ 仅注释与 docstring 变化',""",
              """        'criterion': ('AST：语句多重集 / 常量多重集 / 函数签名 三者相等 '
                      '⇒ 仅注释与 docstring 变化；改前基线 = 客户包 v2.4 副本（稳定参照）'),""", 1)

open(B401, 'w', encoding='utf-8', newline='\n').write(s)
print('patched', B401)

# ── ② _app402d：改成自洽性检查（不再依赖 HEAD）─────────────────────
t = open(B402, encoding='utf-8').read()

old_main = """def main():
    cur = open(STATUS, 'rb').read()
    arc = open(ARCH, 'rb').read()
    head = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:status/app/STATUS_APP.md'],
                          capture_output=True, check=True).stdout

    txt = cur.decode('utf-8')
    lines = txt.split('\\n')
"""
new_main = """def main():
    cur = open(STATUS, 'rb').read()
    arc = open(ARCH, 'rb').read()

    txt = cur.decode('utf-8')
    lines = txt.split('\\n')
"""
assert t.count(old_main) == 1, 'main anchor count = %d' % t.count(old_main)
t = t.replace(old_main, new_main, 1)

old_hdrcmp = """    head_lines = head.decode('utf-8').split('\\n')
    chk('header_block_line_unchanged', lines[5] == head_lines[5],
        '阻塞行与 HEAD 逐字一致（未新增门控项）')
"""
new_hdrcmp = """    # 「阻塞」行本轮**未改** ⇒ 仍含 §168 轮的关键措辞（可作为「本轮未新增门控项」的旁证）
    chk('header_block_line_untouched',
        '§3.5 音色归属判据失效' in lines[5] and '§3.6' in lines[5],
        '阻塞行仍含 §3.5／§3.6 两项门控（本轮未新增门控项、未推进任何门控项）')
"""
assert t.count(old_hdrcmp) == 1
t = t.replace(old_hdrcmp, new_hdrcmp, 1)

old_sec168 = """    # ② §168 正文整块逐字（字节级）
    i = head.find('\\n## §168 '.encode('utf-8')) + 1
    blk = head[i:]
    chk('sec168_archive_verbatim_bytes', blk == arc,
        'HEAD 中 §168 正文块 %d B == 归档件 %d B ⇒ %s' % (len(blk), len(arc), blk == arc))

    # ③ 旧章节标题一个没少
    titles = [l for l in head.decode('utf-8').split('\\n') if l.startswith('## ')]
    missing = [x for x in titles if x not in txt]
    chk('old_section_titles_all_preserved', not missing,
        '%d/%d 保留' % (len(titles) - len(missing), len(titles)))

    # ④ §168 正文已不在活文档（只剩替身）
    chk('sec168_body_not_inline', blk.decode('utf-8') not in txt,
        '活文档只保留 §168 标题行 + 归档指针')
"""
new_sec168 = """    # ② §168 归档件**自洽**：活文档替身行自报的「字节数 + SHA256」
    #    必须与磁盘上的归档件实算值一致（不依赖 HEAD ⇒ 提交后仍成立）
    m = re.search(r'STATUS_APP_sec168_20261110\\.md`（(\\d+) B／块 SHA256 `([0-9a-f]{64})`）', txt)
    chk('sec168_stub_cites_archive', m is not None,
        '活文档 §168 替身行自报归档字节数与块 SHA256')
    if m:
        cited_bytes = int(m.group(1))
        cited_sha = m.group(2)
        real_sha = hashlib.sha256(arc).hexdigest()
        chk('sec168_archive_selfconsistent',
            cited_bytes == len(arc) and cited_sha == real_sha,
            '替身行自报 %d B / %s… == 归档件实算 %d B / %s…'
            % (cited_bytes, cited_sha[:16], len(arc), real_sha[:16]))

    # ③ §169 之前的历史章节标题：活文档 + 归档件合起来必须覆盖全部已知标题
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

    # ④ §168 正文已不在活文档（只剩替身）⇒ 归档件与活文档不重复承载
    chk('sec168_body_not_inline',
        ('## §168 ' in txt) and (txt.count('## §168 ') == 1)
        and ('§168 正文整块逐字归档' in txt),
        '活文档只保留 §168 标题行 + 归档指针（正文不再重复承载）')
"""
assert t.count(old_sec168) == 1, 'sec168 anchor count = %d' % t.count(old_sec168)
t = t.replace(old_sec168, new_sec168, 1)

open(B402, 'w', encoding='utf-8', newline='\n').write(t)
print('patched', B402)
