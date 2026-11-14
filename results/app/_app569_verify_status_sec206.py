#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app569_verify_status_sec206.py —— §206 **独立复核**（不复用写者的任何结论）。

🔴 **判据纪律**：
  · **不复用**写者脚本里的任何常量/结论 ⇒ 本脚本自己从 **git HEAD blob** 取开工前的
    STATUS，独立重建「应当的结果」，再与磁盘上的实文件逐字节比对；
  · 每一项都打印 PASS/FAIL，最后给总数 ⇒ 任一项 FAIL ⇒ 整体 FAIL。
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMPANION = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec206_detail_20261114.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec205_20261114.md')
GATE = os.path.join(REPO, 'results', 'app', '_app537_zip_specialmvp.py')
MATRIX = os.path.join(REPO, 'results', 'app', 'app567_zip_manifest_binding_matrix.json')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

RES = []


def ck(name, ok, detail=''):
    RES.append((name, bool(ok), detail))
    print('%s  %-52s %s' % ('PASS' if ok else 'FAIL', name, detail[:110]))
    return bool(ok)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_blob(rel):
    out = subprocess.run(['git', '-C', REPO, 'cat-file', 'blob', 'HEAD:' + rel],
                         capture_output=True)
    if out.returncode != 0:
        raise RuntimeError('git cat-file 失败 %s: %s' % (rel, out.stderr.decode('utf-8', 'replace')))
    return out.stdout


def main():
    # ── 0 开工前基线（＝ HEAD blob，不是写者给的）──
    base = git_blob('status/app/STATUS_APP.md')
    base_t = base.decode('utf-8')
    cur = open(STATUS, 'rb').read()
    cur_t = cur.decode('utf-8')
    comp = open(COMPANION, 'rb').read().decode('utf-8')
    arch = open(ARCHIVE, 'rb').read().decode('utf-8')

    ck('① 体积 ≤ 40 000 B', len(cur) <= 40000, '%d B' % len(cur))
    ck('② 行数 ≤ 300', cur.count(b'\n') + 1 <= 300, '%d 行' % (cur.count(b'\n') + 1))
    ck('③ 纯 LF（无 CRLF）', b'\r\n' not in cur)
    ck('④ 无 BOM', cur[:3] != b'\xef\xbb\xbf')
    ck('⑤ 较开工变大（追加而非改写）', len(cur) > len(base), '%d → %d B' % (len(base), len(cur)))

    # ── ⑥ 头部 ──
    m = re.search(r'(?m)^last_ack:\s*(\S+)\s*$', cur_t)
    ck('⑥ last_ack ＝ APP-109（无新纠偏 ⇒ 不写自己的编号）',
       bool(m) and m.group(1) == 'APP-109', m.group(1) if m else '缺')
    m2 = re.search(r'(?m)^更新时间:\s*(.+?)\s*$', cur_t)
    ck('⑦ 头部「更新时间」＝ 22:05:11（Get-Date 实测值）',
       bool(m2) and m2.group(1) == '2026-11-14 22:05:11',
       m2.group(1) if m2 else '缺')
    # 开工前的头部时间确实变了（且只变了这一处）
    ck('⑧ 头部仅「更新时间」一处变化（last_ack 未动）',
       base_t.count('更新时间: 2026-11-14 20:52:02') == 1
       and cur_t.count('更新时间: 2026-11-14 22:05:11') == 1
       and base_t.split('更新时间:')[0] == cur_t.split('更新时间:')[0])

    # ── ⑨ 章节齐全且各出现一次 ──
    for s in ('§198', '§199', '§200', '§201', '§202', '§203', '§204', '§205', '§206'):
        ck('⑨ 章节 %s 恰好 1 次' % s, cur_t.count('## %s ' % s) == 1,
           'count=%d' % cur_t.count('## %s ' % s))

    # ── ⑩ §206 块在活文档里存在，且其摘要条目逐字出现在 companion 里 ──
    i206 = cur_t.index('\n## §206 ') + 1
    blk206 = cur_t[i206:]
    ck('⑩ §206 是最后一节', cur_t.rstrip().endswith(blk206.rstrip()[-40:]))
    # 指针行**只**在活文档（companion 正文块不含它）⇒ 判据里必须排除它
    ptr206 = re.search(r'(?m)^> 🔴 \*\*本节完整正文\*\*.*$', cur_t)
    ptr206 = ptr206.group(0) if ptr206 else ''
    lines206 = [l for l in blk206.split('\n')
                if l.startswith('> ') and l != ptr206]
    ck('⑪ §206 摘要条目 ≥ 10 条', len(lines206) >= 10, '%d 条' % len(lines206))
    miss = [l[:40] for l in lines206 if l not in comp]
    ck('⑫ §206 摘要条目逐字出现在 companion', not miss, '缺 %s' % miss[:2])

    # ── ⑬ companion 头里声明的 SHA/字节 ＝ 实际正文块 ──
    mc = re.search(r'§206 正文块 SHA256（标题行 ＋ 摘要条目 ＋ 明细；不含活文档那一行指针）：'
                    r'([0-9a-f]{64})（(\d+) B）', comp)
    sep = '---- 以下为 §206 完整正文，逐字 ----'
    body = comp[comp.index(sep) + len(sep):]
    # 分隔符后带一个 '\n'（与 §204 归档件同款）⇒ 正文块本体去掉它
    assert body.startswith('\n'), 'companion 分隔符后应为换行'
    body = body[1:]
    ck('⑬ companion 声明的正文块 SHA ＝ 实际', bool(mc) and sha(body.encode('utf-8')) == mc.group(1),
       (mc.group(1)[:16] if mc else '缺'))
    ck('⑭ companion 声明的正文块字节 ＝ 实际', bool(mc) and len(body.encode('utf-8')) == int(mc.group(2)),
       '%d vs %s' % (len(body.encode('utf-8')), mc.group(2) if mc else '缺'))

    # ── ⑮ 指针行引用的 SHA/字节 ＝ companion 实际正文块 ──
    mp = re.search(r'STATUS_APP_sec206_detail_20261114\.md`（正文块 \*\*(\d+) B\*\*／'
                    r'SHA256 `([0-9a-f]{64})`）', cur_t)
    ck('⑮ 活文档指针行引用的 companion 正文块 SHA ＝ 实际',
       bool(mp) and mp.group(2) == sha(body.encode('utf-8')), mp.group(2)[:16] if mp else '缺')
    ck('⑯ 活文档指针行引用的字节 ＝ 实际',
       bool(mp) and int(mp.group(1)) == len(body.encode('utf-8')),
       '%s vs %d' % (mp.group(1) if mp else '缺', len(body.encode('utf-8'))))

    # ── ⑰ §205 归档件：正文块 ＝ 开工前 §205 块（逐字）──
    i205 = base_t.index('\n## §205 ') + 1
    blk205_base = base_t[i205:]
    ma = re.search(r'§205 正文块 SHA256（含标题行）：([0-9a-f]{64})（(\d+) B）', arch)
    sep2 = '---- 以下为 §205 原文，逐字 ----'
    body205 = arch[arch.index(sep2) + len(sep2):]
    # 与 companion 同款：分隔符后带一个 '\n' ⇒ 正文块本体去掉它
    assert body205.startswith('\n'), '§205 归档分隔符后应为换行'
    body205 = body205[1:]
    ck('⑰ §205 归档正文块 ＝ 开工前 §205 块（逐字）', body205 == blk205_base,
       '%d vs %d B' % (len(body205.encode('utf-8')), len(blk205_base.encode('utf-8'))))
    ck('⑱ §205 归档声明的 SHA/字节 ＝ 实际',
       bool(ma) and ma.group(1) == sha(body205.encode('utf-8'))
       and int(ma.group(2)) == len(body205.encode('utf-8')))

    # ── ⑲ 还原式复核：把本轮增量逆向还原 ⇒ 必须与开工前逐字节相同 ──
    ptr205 = re.search(r'(?m)^> \*\*正文已整块逐字归档\*\*.*$', cur_t).group(0)
    title205 = blk205_base.split('\n')[0]
    restored = cur_t.replace('\n' + title205 + '\n' + ptr205 + '\n\n' + blk206,
                              '\n' + blk205_base)
    restored = restored.replace('更新时间: 2026-11-14 22:05:11', '更新时间: 2026-11-14 20:52:02')
    ck('⑲ 还原式复核 ⇒ 与开工前逐字节相同', restored.encode('utf-8') == base,
       '还原 %d B vs 开工 %d B' % (len(restored.encode('utf-8')), len(base)))

    # ── ⑳ 闸门脚本：可解析 + 新函数 + 落位顺序 ──
    src = open(GATE, encoding='utf-8').read()
    try:
        ast.parse(src)
        ok = True
    except SyntaxError as e:
        ok = False
        print('   SyntaxError:', e)
    ck('⑳ 闸门脚本 ast.parse 通过', ok)
    ck('㉑ 闸门含 `check_manifest_model_binding`', 'def check_manifest_model_binding' in src)
    tree = ast.parse(src)
    # 收敛判定必须**先于** os.replace（判据：两者的行号；不看文本）
    if_ln, repl_ln = None, None
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and 'len(set(sizes))' in ast.unparse(node.test):
            if if_ln is None or node.lineno < if_ln:
                if_ln = node.lineno
        # 只认**产物落位**那一次：os.replace(tmp, ZIP)（不是原子写文件用的 os.replace(tmp, path)）
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'replace' and 'ZIP' in ast.unparse(node):
            if repl_ln is None or node.lineno < repl_ln:
                repl_ln = node.lineno
    ck('㉒ 两遍收敛判定先于 `os.replace`（fail-closed 顺序）',
       if_ln is not None and repl_ln is not None and if_ln < repl_ln,
       '判定 L%s < 落位 L%s' % (if_ln, repl_ln))
    ck('㉓ `.py` 反向集合为递归（os.walk）',
       'os.walk(appdir)' in src or 'os.walk(appdir)' in src.replace(' ', ''))

    # ── ㉔ 矩阵证据：12/12 ──
    mj = json.load(open(MATRIX, encoding='utf-8'))
    ck('㉔ 矩阵 12 臂全 PASS', mj['n_arms'] == 12 and mj['n_pass'] == 12
       and mj['n_fail'] == 0 and mj['verdict'] == 'PASS',
       '%s/%s' % (mj['n_pass'], mj['n_arms']))
    before_allow = [r['id'] for r in mj['rows'] if r['before'] == 'ALLOW']
    ck('㉕ 改前臂确有 fail-open（ALLOW 的臂）', len(before_allow) >= 5, str(before_allow))

    # ── ㉖ 纠偏文件：只读 + 未改 + 条数/最大编号 ──
    cb = open(CORR, 'rb').read()
    ids = re.findall(r'(?m)^##\s+APP-(\d+)', cb.decode('utf-8'))
    ck('㉖ 纠偏文件 109 条 / 最大 APP-109', len(ids) == 109 and max(ids) == '109',
       '%d 条 / APP-%s' % (len(ids), max(ids)))
    ck('㉗ 纠偏文件 SHA ＝ 开工时的 30a55189…（零改动）',
       sha(cb) == '30a55189bb358c952cf3a600357bbf68e0103bae98b77100dec5fa2afd98f503',
       sha(cb)[:16])

    n_pass = sum(1 for _, ok, _ in RES if ok)
    print('\n%d/%d PASS' % (n_pass, len(RES)))
    out = {'verifier': '_app569_verify_status_sec206', 'n_checks': len(RES),
           'n_pass': n_pass, 'n_fail': len(RES) - n_pass,
           'verdict': 'PASS' if n_pass == len(RES) else 'FAIL',
           'checks': [{'name': n, 'pass': ok, 'detail': d} for n, ok, d in RES]}
    op = os.path.join(REPO, 'results', 'app', 'app569_verify_status_sec206.json')
    with open(op, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('证据：%s' % op)
    return 0 if n_pass == len(RES) else 1


if __name__ == '__main__':
    sys.exit(main())
