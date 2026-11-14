#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app566_verify_status_sec205.py —— **独立**复核 §205 写入结果（不复用写盘脚本的逻辑）。

🔴 **为什么要独立复核**：写盘脚本自己的自检只能证明「它自己认为写对了」；
   本脚本从**磁盘现状**重新推导（重新算 SHA／重新做还原式复原／重新数条目／
   重新比对客户包足迹），任何一条不过 ⇒ 报 FAIL。

🔴 **只读**：本脚本**不写任何文件**（连证据 JSON 也不写 ⇒ 结果只打屏）。
"""
import hashlib
import json
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec204_20261114.md')
DETAIL = os.path.join(REPO, 'status', 'app',
                      'STATUS_APP_sec205_detail_20261114.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
PRE = os.path.join(REPO, 'results', 'app', '_app565_backup',
                   'STATUS_APP_pre205.md')
HOME = r'C:\Users\Trekker-PTL'
SP2 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2')
SP1 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
RC11 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
import datetime
ROUND_START = datetime.datetime(2026, 11, 14, 20, 40).timestamp()   # 本轮开工时刻
MAXB, MAXL = 40000, 300
TS = '2026-11-14 20:52:02'

rows = []


def chk(name, ok, extra=''):
    rows.append({'name': name, 'pass': bool(ok), 'extra': str(extra)[:200]})
    print('  [%s] %s%s' % ('OK' if ok else 'FAIL', name,
                           ('  ' + str(extra)[:160]) if extra else ''))
    return bool(ok)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    return sha_bytes(open(p, 'rb').read())


cur = open(STATUS, 'rb').read()
txt = cur.decode('utf-8')
pre = open(PRE, 'rb').read()

# ── 1. 基本形态 ──
chk('STATUS ≤ 40 000 B', len(cur) <= MAXB, '%d B' % len(cur))
chk('STATUS ≤ 300 行', cur.count(b'\n') <= MAXL, '%d 行' % cur.count(b'\n'))
chk('纯 LF（无 CR）', b'\r' not in cur, 'CR=%d' % cur.count(b'\r'))
chk('无 BOM', cur[:3] != b'\xef\xbb\xbf', '')

# ── 2. 头部 ──
chk('last_ack = APP-109', 'last_ack: APP-109' in txt, '')
chk('更新时间 = Get-Date 实测值', ('更新时间: ' + TS) in txt, TS)
chk('更新时间行唯一', len([l for l in txt.split('\n')
                           if l.startswith('更新时间: ')]) == 1, '')

# ── 3. §204 / §205 结构 ──
t204 = [l for l in txt.split('\n') if l.startswith('## §204 ')]
t205 = [l for l in txt.split('\n') if l.startswith('## §205 ')]
chk('§204 标题行存在且唯一', len(t204) == 1, '')
chk('§205 标题行存在且唯一', len(t205) == 1, '')
chk('§205 是最后一节', txt.rstrip('\n').rfind('## §205 ')
    > txt.rstrip('\n').rfind('## §204 '), '')
ptr = [l for l in txt.split('\n') if 'STATUS_APP_sec204_20261114.md' in l]
chk('§204 指针行存在且唯一', len(ptr) == 1, '')
chk('companion 指针行存在且唯一',
    len([l for l in txt.split('\n')
         if 'STATUS_APP_sec205_detail_20261114.md' in l]) == 1, '')

# ── 4. §204 归档件（逐字）──
arch = open(ARCHIVE, encoding='utf-8').read()
i204 = pre.decode('utf-8').index('## §204 ')
block204 = pre.decode('utf-8')[i204:].rstrip('\n')
sha204 = sha_bytes(block204.encode('utf-8'))
chk('归档件含 §204 正文块逐字', block204 in arch, '')
chk('归档件记录的 §204 SHA 命中', sha204 in arch, sha204[:16])
chk('归档件声明的块字节数命中',
    '（%d B）' % len(block204.encode('utf-8')) in arch, '')

# ── 5. §205 companion（逐字）──
det = open(DETAIL, encoding='utf-8').read()
full = open(os.path.join(REPO, 'results', 'app',
                          '_app565_sec205_body.txt'), encoding='utf-8').read().rstrip('\n')
sha_full = sha_bytes(full.encode('utf-8'))
chk('companion 含 §205 完整正文逐字', full in det, '')
chk('companion 记录的正文 SHA 命中', sha_full in det, sha_full[:16])
chk('活文档摘要里写了 companion 的字节数与 SHA',
    ('**%d B**' % len(full.encode('utf-8'))) in txt
    and sha_full in txt, '%d B' % len(full.encode('utf-8')))

# ── 6. 还原式复核：从**当前**文件逆向还原 ⇒ 必须逐字节回到开工备份 ──
rest = txt
cut = rest.rindex('\n\n## §205 ')
rest = rest[:cut] + '\n'
rest = rest.replace(t204[0] + '\n\n' + ptr[0] + '\n',
                    pre.decode('utf-8')[i204:])
ru = '## 最近更新\n'
rec = [l for l in txt.split('\n') if l.startswith('> 🔴 %s ｜' % TS)]
chk('最近更新新条目存在且唯一', len(rec) == 1, '')
rest = rest.replace(ru + rec[0] + '\n', ru)
rest = rest.replace('更新时间: ' + TS, '更新时间: 2026-11-14 19:38:17')
chk('还原式复核：逐字节回到开工备份', rest.encode('utf-8') == pre,
    '还原 %d B vs 开工 %d B' % (len(rest.encode('utf-8')), len(pre)))

# ── 7. 开工备份本身 = HEAD 的 blob（未被中途篡改）──
p = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:status/app/STATUS_APP.md'],
                   cwd=REPO, capture_output=True)
chk('开工备份 == HEAD blob（status/app/STATUS_APP.md）', p.stdout == pre,
    'HEAD %d B / 备份 %d B' % (len(p.stdout), len(pre)))

# ── 8. 纠偏文件零改动（只读）──
cb = open(CORR, 'rb').read()
chk('CORRECTIONS_APP.md SHA256 未变',
    sha_bytes(cb).startswith('30a55189'), sha_bytes(cb)[:16])
chk('CORRECTIONS_APP.md 字节数未变', len(cb) == 360842, '%d B' % len(cb))
chk('CORRECTIONS_APP.md 条目数 = 109',
    len([1 for l in cb.decode('utf-8').split('\n') if l.startswith('## APP-')]) == 109, '')

# ── 9. sp2 的 MANIFEST 已自洽（真缺陷① 已修）──
man = json.load(open(os.path.join(SP2, 'app', 'MANIFEST.json'), encoding='utf-8'))
chk('sp2 MANIFEST.pkg_models_root = sp2 自己的 models',
    man.get('pkg_models_root') == os.path.join(SP2, 'models'),
    man.get('pkg_models_root'))
chk('sp2 MANIFEST 已不含 sp1 路径',
    'SpecialMVP_v1.0-sp1' not in
    open(os.path.join(SP2, 'app', 'MANIFEST.json'), encoding='utf-8').read(), '')
for tag, pkg in (('sp1', SP1), ('rc11', RC11)):
    mm = json.load(open(os.path.join(pkg, 'app', 'MANIFEST.json'), encoding='utf-8'))
    chk('%s MANIFEST.pkg_models_root 仍指向自己（回归）' % tag,
        mm.get('pkg_models_root') == os.path.join(pkg, 'models'),
        mm.get('pkg_models_root'))

# ── 10. 验收证据带内容绑定（真缺陷② 已修）──
acc = json.load(open(os.path.join(REPO, 'results', 'app',
                                  'app553_specialmvp_sp2_acceptance.json'),
                     encoding='utf-8'))
pc = acc.get('pkg_content') or {}
chk('验收证据带 pkg_content（逐文件 SHA256）',
    isinstance(pc.get('files'), dict) and pc.get('n_files', 0) >= 28,
    'n_files=%s' % pc.get('n_files'))
chk('验收证据带 tree_digest', bool(pc.get('tree_digest')),
    str(pc.get('tree_digest'))[:16])
chk('验收 verdict 未变（PASS（有 1 项未结：退出码异常））',
    acc.get('verdict') == 'PASS（有 1 项未结：退出码异常）', acc.get('verdict'))
chk('验收 n_fail = 0 / n_checks = 9',
    acc.get('n_fail') == 0 and acc.get('n_checks') == 9, '')
chk('验收记录了 MANIFEST 重定向', bool(acc.get('manifest_repointed')),
    (acc.get('manifest_repointed') or {}).get('method', ''))

# ── 11. 鉴别力矩阵 ──
mat = json.load(open(os.path.join(REPO, 'results', 'app',
                                  'app563_zip_content_binding_matrix.json'),
                     encoding='utf-8'))
chk('鉴别力矩阵 verdict = PASS', mat.get('verdict') == 'PASS', mat.get('verdict'))
chk('鉴别力矩阵 12/12', mat.get('n_pass') == 12 and mat.get('n_rows') == 12,
    '%s/%s' % (mat.get('n_pass'), mat.get('n_rows')))
t1 = [r for r in mat.get('rows', []) if r.get('id') == 'T1']
chk('T1（改前臂对不存在的目录 ALLOW）成立',
    bool(t1) and t1[0].get('got') == 'ALLOW', '')

# ── 12. 客户包写入足迹 + 未打包 ──
touched = []
for n in sorted(os.listdir(HOME)):
    if not n.startswith('Confucius4_LiveCaption_'):
        continue
    p2 = os.path.join(HOME, n)
    if not os.path.isdir(p2):
        continue
    for dp, _dn, fn in os.walk(p2):
        for f in fn:
            fp = os.path.join(dp, f)
            try:
                if os.path.getmtime(fp) > ROUND_START:
                    touched.append(os.path.relpath(fp, p2))
            except OSError:
                pass
chk('本轮客户包写入只有 sp2/app/MANIFEST.json',
    touched == [os.path.join('app', 'MANIFEST.json')], touched[:5])
zdir = os.path.join(HOME, 'shared', 'specialmvp')
zips = sorted(os.listdir(zdir))
chk('sp2 仍未打包（shared/specialmvp/ 无 sp2 zip）',
    not any('sp2' in z for z in zips), zips)

n_pass = sum(1 for r in rows if r['pass'])
print('\n%d/%d PASS' % (n_pass, len(rows)))
if n_pass != len(rows):
    sys.exit(1)
print('✅ 独立复核全过')
