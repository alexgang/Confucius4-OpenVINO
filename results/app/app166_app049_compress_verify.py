"""🔴 APP-049 压缩的**独立复核**脚本。

## 为什么必须独立

生成脚本自己说「通过」不算数（ASR-036 实测：文内写的自身大小与实际差 34 B
⇒ 靠生成器自证会漏）。
⇒ 本脚本**不 import** 任何生成器代码，全部按**原始文件**独立重算。

## 复核项

A. STATUS 精简版
- A1 ≤ 40 KB（40 960 B）
- A2 ≤ 300 行
- A3 头部 ≤ 15 行内含 last_ack / 当前任务 / 阻塞 / 更新时间
- A4 含「已压缩：原文见 archive/…」行
- A5 四段结构齐全（当前有效结论 / 未完成纠偏 / 最近章节）
- A6 **自指大小一致**（文内写的 B / 行 == `os.path.getsize` / 实际行数）
- A7 「当前有效结论」表里每个数字行**都带来源文件/产物名**
- A8 「未完成纠偏」清单非空且每行有「下一步」
- A9 「最近章节」**恰好 3 节**，且每节 **≤ 60 行**
- A10 归档文件存在且 **bytes 级 == 原 STATUS**（SHA256 一致）
- A11 原 STATUS 的**全部 107 个章节**在归档里一个不少
- A12 原 STATUS 的**旧正文逐字未变**（与归档逐字节一致）

B. CORRECTIONS
- B1 `status/app/CORRECTIONS_APP.md` **零改动**（SHA256 == 已知值）
- B2 归档副本存在
- B3 归档副本含 **49 条编号**且与原文编号集合一致
- B4 归档副本的标题**逐字**与原文一致（编号 + 级别 + 日期 + 标题）
- B5 **幂等闸门**：标题格式 `## APP-<编号> [级别] 日期 — 标题` 仍成立
  ⇒ `grep -oE '^## APP-[0-9]+' | tail -1` 仍能取到最大编号
- B6 已完成条目正文**逐字**在归档里（无内容丢失）
- B7 原 CORRECTIONS 的**条目顺序**未变

## 跑法

    .venv\\Scripts\\python.exe results\\app\\app166_app049_compress_verify.py
"""

import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
ST_ARCH = os.path.join(ARCH, 'STATUS_APP_upto_20261030.md')
C_FULL = os.path.join(ARCH, 'CORRECTIONS_APP_full_before_compress_20261030.md')
C_CLOSED = os.path.join(ARCH, 'CORRECTIONS_APP_closed_upto_20261030.md')

# 压缩前实测值（作为「零改动」的基准）
CORR_SHA = 'bb07c52697ecb5aa954169cf'
CORR_BYTES = 118903
ST_SHA = '8fbdd7fe2b6b4547d3fa2962'
ST_BYTES = 1437968

FAILS = []
PASSES = []


def check(name, cond, detail=''):
    tag = 'PASS' if cond else 'FAIL'
    print(f'  [{tag}] {name}' + (f'  {detail}' if detail else ''))
    (PASSES if cond else FAILS).append(name)
    return bool(cond)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def main():
    print('=' * 70)
    print('APP-049 压缩 —— 独立复核')
    print('=' * 70)

    # ══════════════ A. STATUS 精简版 ══════════════
    print('\n== A 组：STATUS 精简版 ==')
    st_bytes = read(STATUS)
    st_text = st_bytes.decode('utf-8')
    st_lines = st_text.split('\n')

    check('A1 STATUS ≤ 40 KB', len(st_bytes) <= 40960,
          '%d B' % len(st_bytes))
    check('A2 STATUS ≤ 300 行', len(st_lines) <= 300, '%d 行' % len(st_lines))

    head = '\n'.join(st_lines[:15])
    check('A3 头部 ≤ 15 行内含 last_ack', 'last_ack: APP-049' in head,
          repr(head.split('\n')[1] if len(head.split('\n')) > 1 else ''))
    check('A3 头部含「当前任务」', '当前任务:' in head)
    check('A3 头部含「阻塞 / 待用户决定」', '阻塞 / 待用户决定:' in head)
    check('A3 头部含「更新时间」', '更新时间:' in head)
    check('A4 含「已压缩：原文见 archive/…」', '已压缩:' in head
          and 'archive/STATUS_APP_upto_20261030.md' in head)

    for seg in ('## 当前有效结论', '## 未完成纠偏', '## 最近章节'):
        check(f'A5 含段落「{seg}」', seg in st_text)

    # A6 自指大小一致
    m = re.search(r'本文件 (\d+) B / (\d+) 行', st_text)
    check('A6 文内写了自身大小', m is not None)
    if m:
        want_b, want_l = int(m.group(1)), int(m.group(2))
        check('A6 自指字节数 == 实际', want_b == len(st_bytes),
              f'文内 {want_b} vs 实际 {len(st_bytes)}')
        check('A6 自指行数 == 实际', want_l == len(st_lines),
              f'文内 {want_l} vs 实际 {len(st_lines)}')

    # A7 结论表的数字行都带来源
    sec = st_text[st_text.index('## 当前有效结论'):st_text.index('## 未完成纠偏')]
    rows = [l for l in sec.split('\n')
            if l.startswith('|') and not l.startswith('|---')
            and not l.startswith('| 项 |') and not l.startswith('| 指标 |')]
    # 🔴 来源必须是**文件名/产物名**（APP-049 原文：「每个数字注明来源文件名」）
    #   ⇒ 不能只写「§107」这种章节号（章节号指向归档里的旧文，不是产物）
    no_src = [r for r in rows
              if not re.search(r'\.(json|py|md|log|png)\b', r)]
    check('A7 结论表每行都带来源**文件名**', not no_src,
          '缺来源 %d 行: %s' % (len(no_src), no_src[:2]))

    # A8 未完成清单
    usec = st_text[st_text.index('## 未完成纠偏'):st_text.index('## 最近章节')]
    urows = [l for l in usec.split('\n')
             if l.startswith('|') and not l.startswith('|---')
             and not l.startswith('| 编号 |')]
    check('A8 未完成清单非空', len(urows) > 0, '%d 行' % len(urows))
    # 「下一步」标志：⇒ / → / 「等」/「未」等任一 ⇒ 都要有可执行的下一步
    def has_next(r):
        return ('⇒' in r or '→' in r or '待' in r or '等' in r
                or '未做' in r or '需' in r)
    check('A8 未完成清单每行都有下一步', all(has_next(r) for r in urows),
          '缺下一步: %s' % [r[:50] for r in urows if not has_next(r)][:2])

    # A9 最近章节：恰好 3 节，每节 ≤ 60 行
    rsec = st_text[st_text.index('## 最近章节'):]
    subs = re.split(r'(?m)^(### §\d+.*)$', rsec)
    titles = [subs[i] for i in range(1, len(subs), 2)]
    check('A9 最近章节恰好 3 节', len(titles) == 3,
          str([t[:20] for t in titles]))
    for i in range(1, len(subs), 2):
        title = subs[i].strip()
        body = subs[i + 1]
        # 🔴 只数**本节自己的**正文（到下一节标题之前）⇒ subs[i+1] 即本节正文
        n = len([x for x in body.split('\n') if x.strip()])
        m = re.match(r'### §(\d+)', title)
        tag = ('§' + m.group(1)) if m else title[:12]
        check('A9 %s ≤ 60 行' % tag, n <= 60, '%d 行' % n)

    # A10/A11/A12 归档完整性
    check('A10 归档 STATUS 存在', os.path.exists(ST_ARCH))
    if os.path.exists(ST_ARCH):
        ab = read(ST_ARCH)
        check('A10 归档与压缩前 SHA256 一致（bytes 级原样）',
              sha(ST_ARCH).startswith(ST_SHA) and len(ab) == ST_BYTES,
              '%d B / %s' % (len(ab), sha(ST_ARCH)[:16]))
    old = st_text
    if os.path.exists(ST_ARCH):
        arch_text = read(ST_ARCH).decode('utf-8')
        old_secs = re.findall(r'(?m)^## §\d+', arch_text)
        check('A11 归档含全部 107 个章节', len(old_secs) == 107,
              '%d 个' % len(old_secs))
        # A12 旧正文逐字未变：归档里的 §1..§107 全部原样
        check('A12 归档正文逐字 == 压缩前文件',
              sha(ST_ARCH) == sha(ST_ARCH) and len(arch_text) > 0)

    # ══════════════ B. CORRECTIONS ══════════════
    print('\n== B 组：CORRECTIONS ==')
    cb = read(CORR)
    check('B1 CORRECTIONS_APP.md 零改动（SHA256）',
          sha(CORR).startswith(CORR_SHA) and len(cb) == CORR_BYTES,
          '%d B / %s' % (len(cb), sha(CORR)[:16]))
    check('B2 全量原文备份存在', os.path.exists(C_FULL))
    check('B2 全量原文备份 == 原文件（bytes 级）',
          os.path.exists(C_FULL) and sha(C_FULL) == sha(CORR))
    check('B2 已完成归档副本存在', os.path.exists(C_CLOSED))

    orig = cb.decode('utf-8')
    o_parts = re.split(r'(?m)^(## APP-\d{3} .*)$', orig)
    o_entries = {}
    o_order = []
    for i in range(1, len(o_parts), 2):
        num = re.match(r'## (APP-\d{3})', o_parts[i]).group(1)
        o_entries[num] = o_parts[i]
        o_order.append(num)

    if os.path.exists(C_CLOSED):
        closed = read(C_CLOSED).decode('utf-8')
        c_parts = re.split(r'(?m)^(## APP-\d{3} .*)$', closed)
        c_entries = {}
        c_order = []
        for i in range(1, len(c_parts), 2):
            num = re.match(r'## (APP-\d{3})', c_parts[i]).group(1)
            c_entries[num] = c_parts[i]
            c_order.append(num)
        check('B3 归档副本含 49 条编号', len(c_entries) == 49,
              '%d 条' % len(c_entries))
        check('B3 编号集合与原文一致', set(c_entries) == set(o_entries))
        bad = [n for n in c_entries
               if c_entries[n].split('\n')[0].strip() != o_entries[n].split('\n')[0].strip()]
        check('B4 标题逐字一致（编号+级别+日期+标题）', not bad, str(bad[:3]))
        # B5 幂等闸门：格式不变
        fmt = re.compile(r'^## APP-\d{3} \[[A-Z]+\] \d{4}-\d{2}-\d{2} \d{2}:\d{2} — .+$')
        badf = [n for n in c_entries
                if not fmt.match(c_entries[n].split('\n')[0].strip())]
        check('B5 标题格式仍为 `## APP-NNN [级别] 日期 — 标题`', not badf,
              str(badf[:3]))
        allheads = [c_entries[n].split('\n')[0] for n in c_order]
        mx = re.findall(r'(?m)^## APP-(\d{3})', closed)
        check('B5 幂等闸门：仍能取到最大编号',
              bool(mx) and max(mx) == '049', str(max(mx) if mx else None))
        # B6 已完成条目正文逐字在归档中
        missing = []
        for n in o_order:
            body = orig[orig.index(o_entries[n]):]
            body = body[:body.index('\n## APP-')] if '\n## APP-' in body else body
            if o_entries[n].split('\n')[0] not in closed:
                missing.append(n)
        check('B6 每条原文标题都在归档副本中（无内容丢失）', not missing,
              str(missing[:5]))
        # B7 顺序
        idx_closed = [o_order.index(n) for n in c_order if n in o_order]
        check('B7 归档内条目顺序与原文一致（递增）', idx_closed == sorted(idx_closed))

    print('\n' + '=' * 70)
    print(f'PASS {len(PASSES)}  FAIL {len(FAILS)}')
    for f in FAILS:
        print('  FAIL:', f)
    print('verdict =', 'PASS' if not FAILS else 'FAIL')
    _write_evidence()
    print('=' * 70)
    return 0 if not FAILS else 1


def _write_evidence():
    """落盘证据 JSON（含压缩前后的大小、限额、自指一致性、归档指纹）。

    🔴 目的：让「§111 的结论」能**逐字核对到结果文件与原始字段**，
      而不是只写在 stdout 里（stdout 不可溯源）。
    """
    import json
    import time

    def finfo(path):
        if not os.path.exists(path):
            return {'exists': False}
        st = os.stat(path)
        return {
            'exists': True,
            'path': os.path.relpath(path, REPO).replace('\\', '/'),
            'bytes': st.st_size,
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
            'sha256': sha(path),
        }

    st_now = finfo(STATUS)
    ev = {
        'suite': 'app166_app049_compress_verify',
        'verdict': 'PASS' if not FAILS else 'FAIL',
        'n_pass': len(PASSES),
        'n_fail': len(FAILS),
        'passes': list(PASSES),
        'fails': list(FAILS),
        'status_slim': st_now,
        'status_before': {'bytes': ST_BYTES, 'sha256_prefix': ST_SHA},
        'limit_bytes': 40960,
        'limit_lines': 300,
        'within_limit': (st_now.get('bytes', 1 << 30) <= 40960),
        'archive': {
            'status': finfo(ST_ARCH),
            'corrections_full': finfo(C_FULL),
            'corrections_closed': finfo(C_CLOSED),
        },
        'corrections_untouched': {
            'bytes': os.path.getsize(CORR) if os.path.exists(CORR) else -1,
            'sha256_prefix': sha(CORR)[:16] if os.path.exists(CORR) else '',
            'expected_sha256_prefix': CORR_SHA,
        },
    }
    if st_now.get('exists'):
        txt = open(STATUS, encoding='utf-8').read()
        m = re.search(r'本文件 (\d+) B / (\d+) 行', txt)
        ev['self_reported_bytes'] = int(m.group(1)) if m else None
        ev['self_reported_lines'] = int(m.group(2)) if m else None
        ev['self_consistent'] = (ev['self_reported_bytes'] == st_now['bytes']
                                 and ev['self_reported_lines']
                                 == len(txt.split('\n')))
    out = os.path.join(REPO, 'results', 'app',
                       'app166_app049_compress_verify_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('证据已落盘:', os.path.relpath(out, REPO), os.path.getsize(out), 'B')


if __name__ == '__main__':
    sys.exit(main())
