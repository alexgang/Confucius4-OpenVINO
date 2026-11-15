#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app574_verify_status_sec207.py —— **独立**复核 STATUS §207（不 import 写者）。

🔴 **为什么要独立复核**：§206 教训 —— 写者自检过了，独立复核仍能抓到问题。
  ⇒ 本脚本不复用写者逻辑，只用「磁盘上的字节」重新算一遍。

🔴 **复核脚本自己也要跑反证组**（§206 教训）：末尾会把副本改坏
  （灌字节／混 CR／改 last_ack／删正文块／篡改归档件…）⇒ 断言每种改坏都被抓到。

🔴 **2026-11-15 首次运行抓到的 6 个 FAIL 全是「复核脚本自己的判据错」**
  （§206 同款教训）：① 归档块不在**活文档**里（已被换成指针行）⇒ 该比**开工基线**；
  ② 指针行正则写成「§206 整块逐字归档」而实际文案是「本节正文已整块逐字归档」；
  ③ 「最近更新」块 SHA 的口径不一致（自述按**含末尾换行**算，复核按 rstrip 算）；
  ④ companion 的**完整正文**不在活文档里（活文档只有摘要）⇒ 该比**正文源文件**；
  ⑤ companion 指针正则漏了 `**`；⑥ 还原时多插了一个换行。
  ⇒ 本版逐条修正，并保留反证组以防再犯。

复核项：
  ① STATUS 限额（≤40 000 B／≤300 行）／纯 LF／无 BOM／`last_ack=APP-109`
  ② §207 是最后一节；§206 标题行仍在且唯一；两处指针行都在
  ③ 归档件：§206 正文块 ＋「最近更新」3 条块 **逐字命中开工基线**，块 SHA
     与**归档件自述**一致、且**活文档指针行声明**与之一致
  ④ companion：完整正文逐字命中**正文源文件**；活文档摘要里声明的字节/SHA
     == companion 实测
  ⑤ **还原式复核**：把本轮所有增量逐一逆向还原 ⇒ 与**开工基线**逐字节相同
"""
import hashlib
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec206_20261115.md')
RU_ARCHIVE = os.path.join(REPO, 'status', 'archive',
                           'STATUS_APP_recent_updates_20261115.md')
DETAIL = os.path.join(REPO, 'status', 'app',
                      'STATUS_APP_sec207_detail_20261115.md')
BODY_FILE = os.path.join(REPO, 'results', 'app', '_app571_sec207_body.txt')
BACKUP = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'),
                       '_app573_STATUS_backup_pre207.md')
MAXB, MAXL = 40000, 300

RESULTS = []


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _after(data, marker):
    """取归档件「---- 以下为原文，逐字 ----」之后的原文块（**不** rstrip）。"""
    txt = data.decode('utf-8')
    assert marker in txt, '归档件缺分隔行：%r' % marker
    return txt.split(marker, 1)[1]


def verify(status_bytes, archive_bytes, ru_bytes, detail_bytes, baseline):
    out = []
    t = status_bytes.decode('utf-8')
    bt = baseline.decode('utf-8')

    # ① 限额与基本形态
    out.append(('字节上限', len(status_bytes) <= MAXB, '%d B' % len(status_bytes)))
    out.append(('行数上限', status_bytes.count(b'\n') <= MAXL,
                '%d 行' % status_bytes.count(b'\n')))
    out.append(('纯 LF', b'\r' not in status_bytes, ''))
    out.append(('无 BOM', status_bytes[:3] != b'\xef\xbb\xbf', ''))
    out.append(('last_ack=APP-109', 'last_ack: APP-109' in t, ''))
    out.append(('无未填占位符', '__DETAIL' not in t, ''))

    # ② 结构
    titles = re.findall(r'^## §(\d+) ', t, flags=re.M)
    out.append(('§207 存在', '207' in titles, ''))
    out.append(('§207 标题行唯一', titles.count('207') == 1, ''))
    out.append(('§206 标题行仍在且唯一', titles.count('206') == 1, ''))
    out.append(('§207 是最后一节',
                t.rstrip('\n').rfind('## §207 ')
                == t.rstrip('\n').rfind('## §'), ''))
    out.append(('§206 指针行在', 'STATUS_APP_sec206_20261115.md' in t, ''))
    out.append(('「最近更新」归档指针行在',
                'STATUS_APP_recent_updates_20261115.md' in t, ''))
    out.append(('companion 指针行在',
                'STATUS_APP_sec207_detail_20261115.md' in t, ''))

    # ③ §206 归档块：逐字命中**开工基线** ＋ SHA 三方一致
    a_txt = archive_bytes.decode('utf-8')
    m = re.search(r'§206 正文块 SHA256（含标题行）：([0-9a-f]{64})（(\d+) B）',
                  a_txt)
    if m:
        d_sha, d_len = m.group(1), int(m.group(2))
        blk = _after(archive_bytes,
                     '---- 以下为 §206 原文，逐字 ----\n').rstrip('\n')
        out.append(('§206 归档块自洽（实测 SHA==自述）',
                    sha(blk.encode('utf-8')) == d_sha
                    and len(blk.encode('utf-8')) == d_len, ''))
        out.append(('§206 归档块逐字命中开工基线',
                    blk.encode('utf-8') in baseline, ''))
        p = re.search(r'本节正文已整块逐字归档[^`\n]*'
                      r'`status/archive/STATUS_APP_sec206_20261115\.md`'
                      r'（正文块 SHA256 `([0-9a-f]{64})`）', t)
        out.append(('活文档 §206 指针声明 == 归档实测',
                    bool(p) and p.group(1) == d_sha, ''))
    else:
        out.append(('§206 归档块自洽（实测 SHA==自述）', False, '找不到自述行'))
        out.append(('§206 归档块逐字命中开工基线', False, ''))
        out.append(('活文档 §206 指针声明 == 归档实测', False, ''))

    # ③b 「最近更新」归档块：口径 = 含末尾换行（与自述一致）
    r_txt = ru_bytes.decode('utf-8')
    m = re.search(r'块 SHA256：([0-9a-f]{64})（(\d+) B）', r_txt)
    if m:
        d_sha, d_len = m.group(1), int(m.group(2))
        blk = _after(ru_bytes, '---- 以下为原文，逐字 ----\n')
        out.append(('「最近更新」归档块自洽',
                    sha(blk.encode('utf-8')) == d_sha
                    and len(blk.encode('utf-8')) == d_len, ''))
        out.append(('「最近更新」归档块逐字命中开工基线',
                    blk.encode('utf-8') in baseline, ''))
        p = re.search(r'本节 3 条较旧「最近更新」条目[^\n]*?'
                      r'`status/archive/STATUS_APP_recent_updates_20261115\.md`'
                      r'（块 SHA256 `([0-9a-f]{64})`）', t)
        out.append(('活文档「最近更新」指针声明 == 归档实测',
                    bool(p) and p.group(1) == d_sha, ''))
    else:
        out.append(('「最近更新」归档块自洽', False, '找不到自述行'))
        out.append(('「最近更新」归档块逐字命中开工基线', False, ''))
        out.append(('活文档「最近更新」指针声明 == 归档实测', False, ''))

    # ④ companion：完整正文逐字命中**正文源文件**；活文档声明 == 实测
    d_txt = detail_bytes.decode('utf-8')
    if '---- 以下为 §207 完整正文，逐字 ----\n' in d_txt:
        blk = _after(detail_bytes,
                     '---- 以下为 §207 完整正文，逐字 ----\n').rstrip('\n')
        try:
            body = open(BODY_FILE, 'rb').read().decode('utf-8').rstrip('\n')
        except OSError:
            body = ''
        out.append(('companion 正文块 == 正文源文件',
                    bool(body) and blk == body, ''))
        p = re.search(r'正文块 \*\*(\d+) B\*\*／SHA256 `([0-9a-f]{64})`', t)
        out.append(('活文档声明的 companion 字节/SHA == 实测',
                    bool(p) and int(p.group(1)) == len(blk.encode('utf-8'))
                    and p.group(2) == sha(blk.encode('utf-8')), ''))
        out.append(('companion 正文块在活文档摘要里逐字命中（摘要行存在）',
                    ('> 🔴 **完整正文**' in t) and ('§207' in t), ''))
    else:
        out.append(('companion 正文块 == 正文源文件', False, '找不到分隔行'))
        out.append(('活文档声明的 companion 字节/SHA == 实测', False, ''))

    # ⑤ 还原式复核：把本轮所有增量逐一逆向还原 ⇒ 回到开工基线
    rest = t
    cut = rest.rfind('\n\n## §207 ')
    rest = rest[:cut] + '\n'
    # 还原 §206「标题行＋指针行」→ 原 §206 整块（归档块**含**标题行）
    p = re.search(r'^## §206 [^\n]*\n'
                  r'> 🔴 \*\*本节正文已整块逐字归档\*\* ⇒ '
                  r'`status/archive/STATUS_APP_sec206_20261115\.md`[^\n]*\n',
                  rest, flags=re.M)
    if p:
        blk = _after(archive_bytes,
                     '---- 以下为 §206 原文，逐字 ----\n').rstrip('\n')
        # ⚠️ 基线的 STATUS **末尾没有换行**（§205 起写入器的既有约定）
        #    ⇒ 还原时**不能**再加 '\n'（否则多 1 B ⇒ 假 FAIL）
        rest = rest[:p.start()] + blk + rest[p.end():]
    # 还原「最近更新」指针行 → 原 3 条（块**含**末尾换行 ⇒ 不要再加换行）
    p = re.search(r'^> 🔴 本节 3 条较旧「最近更新」条目[^\n]*\n',
                  rest, flags=re.M)
    if p:
        blk = _after(ru_bytes, '---- 以下为原文，逐字 ----\n')
        rest = rest[:p.start()] + blk + rest[p.end():]
    # 还原「最近更新」本轮新增行（指针行之前的第一行）
    ru = '## 最近更新\n'
    i = rest.index(ru) + len(ru)
    j = rest.find('\n', i)
    rest = rest[:i] + rest[j + 1:]
    # 还原头部时间戳
    ts_line = re.search(r'^更新时间: .*$', rest, flags=re.M)
    base_ts = re.search(r'^更新时间: .*$', bt, flags=re.M)
    if ts_line and base_ts:
        rest = (rest[:ts_line.start()] + base_ts.group(0)
                + rest[ts_line.end():])
    out.append(('还原式复核（逐字节回到开工基线）',
                rest.encode('utf-8') == baseline,
                '还原 %d B vs 基线 %d B'
                % (len(rest.encode('utf-8')), len(baseline))))
    return out


def main():
    status_bytes = open(STATUS, 'rb').read()
    archive_bytes = open(ARCHIVE, 'rb').read()
    ru_bytes = open(RU_ARCHIVE, 'rb').read()
    detail_bytes = open(DETAIL, 'rb').read()

    # 开工基线：git HEAD 的 blob（独立于我的 %TEMP% 备份）
    baseline = subprocess.run(
        ['git', '-C', REPO, 'cat-file', 'blob',
         'HEAD:status/app/STATUS_APP.md'],
        capture_output=True, check=True).stdout
    RESULTS.append(('开工基线取自 git HEAD blob', len(baseline) > 0,
                    '%d B' % len(baseline)))
    if os.path.isfile(BACKUP):
        bk = open(BACKUP, 'rb').read()
        RESULTS.append(('开工基线：git HEAD blob == %TEMP% 备份', bk == baseline,
                        'HEAD %d B / 备份 %d B' % (len(baseline), len(bk))))
        if bk != baseline:
            baseline = bk
    else:
        RESULTS.append(('开工基线：找到 %TEMP% 备份', False, '备份不存在'))

    for name, ok, extra in verify(status_bytes, archive_bytes, ru_bytes,
                                  detail_bytes, baseline):
        RESULTS.append((name, ok, extra))

    print('=== 独立复核（STATUS §207）===')
    n_fail = 0
    for name, ok, extra in RESULTS:
        print(('  [OK] ' if ok else '  [FAIL] ') + name
              + ('  ' + extra if extra else ''))
        if not ok:
            n_fail += 1
    print('\n复核: %d/%d PASS' % (len(RESULTS) - n_fail, len(RESULTS)))

    # ── 反证组：复核脚本自己也要能判 FAIL ──
    # ⚠️ §206 教训：**反证必须真的改坏被检的那部分**
    #    （第一版 3 个变异只改了归档件的**页眉**文字 ⇒ 被检的正文块没变
    #      ⇒ 判据「没抓到」是变异无效，不是判据弱）⇒ 下面按分隔行**只改正文块**。
    print('\n=== 反证组（改坏副本 ⇒ 必须被抓）===')
    mut_fail = 0

    def _tamper_tail(data, marker, old, new):
        """只篡改「---- 以下为原文 ----」**之后**的正文块。"""
        mb = marker.encode('utf-8')
        head, _, tail = data.partition(mb)
        assert tail, '归档件缺分隔行'
        ob = old.encode('utf-8') if isinstance(old, str) else old
        nb = new.encode('utf-8') if isinstance(new, str) else new
        assert ob in tail, '正文块里找不到待改字节'
        return head + mb + tail.replace(ob, nb, 1)

    mutants = [
        ('灌字节到 40 001 B',
         lambda s, a, r, d: (s + b'x' * (40001 - len(s)), a, r, d)),
        ('混入 CR',
         lambda s, a, r, d: (s.replace(b'## \xc2\xa7', b'## \xc2\xa7\r', 1), a, r, d)),
        ('改 last_ack',
         lambda s, a, r, d: (s.replace(b'last_ack: APP-109',
                                      b'last_ack: APP-110'), a, r, d)),
        ('删掉 §207 标题行',
         # ⚠️ '§' = U+00A7 ⇒ UTF-8 是 **C2 A7**（不是 E2 80 A7 ⇒ 那是连字符点，
         #    用错字节 ⇒ 正则永不匹配 ⇒ 变异是空操作 ⇒「没被抓」是变异无效，
         #    不是判据弱 —— §206 教训「反证构造自己会坏」）
         lambda s, a, r, d: (re.sub(b'## ' + b'\xc2\xa7' + b'207 [^\n]*\n',
                                    b'', s, count=1), a, r, d)),
        ('篡改 companion **正文块**',
         lambda s, a, r, d: (s, a, r,
                             _tamper_tail(d,
                                          '---- 以下为 §207 完整正文，逐字 ----\n',
                                          '§207'.encode('utf-8'),
                                          '§999'.encode('utf-8')))),
        ('篡改 §206 归档 **正文块**',
         lambda s, a, r, d: (s, _tamper_tail(a,
                                             '---- 以下为 §206 原文，逐字 ----\n',
                                             '§206'.encode('utf-8'),
                                             '§999'.encode('utf-8')), r, d)),
        ('篡改「最近更新」归档 **正文块**',
         lambda s, a, r, d: (s, a, _tamper_tail(r,
                                               '---- 以下为原文，逐字 ----\n',
                                               b'2026-11-14 20:52:02',
                                               b'2026-01-01 20:52:02'), d)),
        ('篡改活文档里的 companion SHA 声明',
         lambda s, a, r, d: (re.sub(b'SHA256 `[0-9a-f]{64}`',
                                    b'SHA256 `deadbeef`', s, count=1),
                             a, r, d)),
    ]
    for label, mut in mutants:
        s2, a2, r2, d2 = mut(status_bytes, archive_bytes, ru_bytes,
                             detail_bytes)
        res2 = verify(s2, a2, r2, d2, baseline)
        caught = any(not ok for _n, ok, _e in res2)
        if not caught:
            mut_fail += 1
        print('  %-34s %s' % (label, '被抓 ✔' if caught else '❌ 未被抓'))

    # 真身再复核一次（确认变异函数没有污染真身）
    res3 = verify(open(STATUS, 'rb').read(), open(ARCHIVE, 'rb').read(),
                  open(RU_ARCHIVE, 'rb').read(), open(DETAIL, 'rb').read(),
                  baseline)
    ok3 = all(ok for _n, ok, _e in res3)
    print('\n真身复核（变异后重跑）: %s' % ('PASS' if ok3 else 'FAIL'))
    if not ok3:
        mut_fail += 1

    print('\n=== 总结 ===')
    print('独立复核: %d/%d PASS ｜ 反证组未被抓 %d 个'
          % (len(RESULTS) - n_fail, len(RESULTS), mut_fail))
    return 0 if (n_fail == 0 and mut_fail == 0 and ok3) else 1


if __name__ == '__main__':
    sys.exit(main())
