#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app537_zip_specialmvp.py —— 给 Special MVP 打 zip（**新版本号，不覆盖旧包**）。

纪律：
  · **必须先有包上验收 PASS**（APP-107 §1.4 的同款 fail-closed）⇒ 否则拒绝出包；
  · **两遍打包**：第 1 遍量出 zip 字节数 ⇒ 回填 README（固定宽度 ⇒ 长度不变）
    ⇒ 第 2 遍体积应**完全一致**（收敛）⇒ 不一致就报错（rc11 的老坑）；
  · zip 内**不含** `.pyc` / 黑名单文件（打之前断言）。
"""
import json
import os
import sys
import time
import zipfile

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
DST_PKG = os.path.join(HOME, PKG_NAME)
ZIP = os.path.join(HOME, 'shared', 'specialmvp',
                   PKG_NAME + '.zip')
ACCEPT = os.path.join(RESULTS, 'app536_specialmvp_acceptance.json')
REPORT = os.path.join(RESULTS, 'app537_specialmvp_zip.json')
NUM_WIDTH = 18

ev = {'zip': ZIP, 'pkg': DST_PKG, 'actions': []}
t0 = time.time()

# ── ① 验收必须 PASS ──
if not os.path.isfile(ACCEPT):
    raise RuntimeError('缺包上验收证据，拒绝打包：%s' % ACCEPT)
acc = json.load(open(ACCEPT, encoding='utf-8'))
ev['accept_verdict'] = acc.get('verdict')
ev['accept_checks'] = acc.get('checks')
if acc.get('verdict') != 'PASS':
    raise RuntimeError('包上验收未通过（%s），拒绝打包'
                       % acc.get('verdict'))
if os.path.exists(ZIP):
    raise RuntimeError('zip 已存在（不覆盖旧版本，APP-055）：%s' % ZIP)
os.makedirs(os.path.dirname(ZIP), exist_ok=True)


def dir_stats(root):
    n = 0
    total = 0
    for dp, dn, fn in os.walk(root):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, total


def fmt_num(v):
    """固定宽度数字（⇒ README 长度不随数字变化 ⇒ 两遍 zip 收敛）。"""
    return ('%*s' % (NUM_WIDTH, format(int(v), ',')))


def readme_size_line(n_files, dir_bytes, zip_bytes):
    return ('* **包体积（实测）**：解压后 **%s 个文件 / %s B（%.3f GiB）**；'
            'zip **%s B**。'
            % ('{:,}'.format(n_files), fmt_num(dir_bytes),
               dir_bytes / 1024 ** 3, fmt_num(zip_bytes)))


def patch_readme(n_files, dir_bytes, zip_bytes):
    """只改「包体积（实测）」那一行（定点替换 + 唯一命中断言）。

    🔴 **不调用 rc11 的 write_readmes**（那会**重写整份 README** ⇒ 会抹掉
    本轮写入的 Special MVP 专有说明）。
    """
    line = readme_size_line(n_files, dir_bytes, zip_bytes)
    for rel in ('README_zh.md',):
        p = os.path.join(DST_PKG, rel)
        if not os.path.isfile(p):
            continue
        txt = open(p, encoding='utf-8').read()
        hits = [ln for ln in txt.splitlines() if ln.startswith('* **包体积（实测）**')]
        if len(hits) != 1:
            raise RuntimeError('%s 的「包体积」行命中 %d 次（应恰好 1 次）'
                               % (rel, len(hits)))
        txt = txt.replace(hits[0], line)
        open(p, 'w', encoding='utf-8', newline='\n').write(txt)
        ev['actions'].append('%s: 包体积行已回填（%s）' % (rel, line[:60]))
    return line


# ── ② 打 zip 前只**断言**（本机的安全删除 shim 把删除转回收站且会失败 ⇒ 不能删）──
sys.path.insert(0, RESULTS)
import importlib.util
spec = importlib.util.spec_from_file_location(
    '_app524', os.path.join(RESULTS, '_app524_build_minimvp_rc11.py'))
rc11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc11)
n_pyc = rc11.count_pyc(DST_PKG)
black = rc11.find_blacklist(DST_PKG)
n_empty_pyc = 0
for dp, dn, _fn in os.walk(DST_PKG):
    for d in dn:
        if d == '__pycache__':
            try:
                if not os.listdir(os.path.join(dp, d)):
                    n_empty_pyc += 1
            except OSError:
                pass
ev['pre_zip'] = {'n_pyc': n_pyc, 'n_blacklist': len(black),
                  'n_empty_pycache_dirs': n_empty_pyc,
                  'note': '🔴 本机安全删除 shim 把删除转回收站且会失败 ⇒ **不删**，'
                          '只断言；空的 __pycache__ 目录**不进 zip**'
                          '（zipfile 只写文件）⇒ 符合「包内禁 .pyc」纪律'}
if n_pyc:
    raise RuntimeError('打 zip 前仍有 %d 个 .pyc' % n_pyc)
if black:
    raise RuntimeError('打 zip 前仍有黑名单文件：%s' % [b['file'] for b in black[:5]])

# ── ③ 两遍打包 ──
sizes = []
n_files0, dir_bytes0 = dir_stats(DST_PKG)
# 第 1 遍：先把 README 的体积行按**当前目录实测**写好（zip 字节数先占位）
patch_readme(n_files0, dir_bytes0, 0)
for i in range(2):
    t1 = time.time()
    tmp = ZIP + '.tmp'
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_STORED,
                         allowZip64=True) as zf:
        for dp, _dn, fn in os.walk(DST_PKG):
            for f in fn:
                p = os.path.join(dp, f)
                arc = os.path.join(PKG_NAME, os.path.relpath(p, DST_PKG))
                zf.write(p, arc.replace('\\', '/'))
    sz = os.path.getsize(tmp)
    sizes.append(sz)
    n_files, dir_bytes = dir_stats(DST_PKG)
    line = patch_readme(n_files, dir_bytes, sz)
    ev['actions'].append('zip pass %d: %d B (%.1f s)' % (i + 1, sz,
                                                          time.time() - t1))
    if i == 0:
        os.remove(tmp)     # 第 1 遍只用来量体积
    else:
        os.replace(tmp, ZIP)

if len(set(sizes)) != 1:
    raise RuntimeError('zip 体积未收敛：%s' % sizes)

# ── ④ 复核 ──
n_files, dir_bytes = dir_stats(DST_PKG)
with zipfile.ZipFile(ZIP, 'r') as zf:
    names = zf.namelist()
    zpyc = [n for n in names if n.endswith('.pyc') or '__pycache__/' in n]
    zblack = [n for n in names if '/bridge_token' in n or n.endswith('.pid')]
    zint4 = [n for n in names if 'int4' in n.lower()]
ev['verify'] = {
    'n_files_dir': n_files, 'n_entries_zip': len(names),
    'n_files_match': len(names) == n_files,
    'pyc_in_zip': len(zpyc), 'blacklist_in_zip': len(zblack),
    'int4_in_zip': len(zint4),
    'zip_bytes': os.path.getsize(ZIP),
    'dir_bytes': dir_bytes,
}
if zpyc or zblack:
    raise RuntimeError('zip 内有 .pyc/黑名单：%s' % (zpyc[:3] + zblack[:3]))
if len(names) != n_files:
    raise RuntimeError('zip 条目数 %d != 目录文件数 %d' % (len(names), n_files))
ev['elapsed_s'] = round(time.time() - t0, 1)
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('zip：%s' % ZIP)
print('  bytes      : %d' % ev['verify']['zip_bytes'])
print('  文件数     : %d（zip 条目 %d，一致=%s）'
      % (n_files, len(names), ev['verify']['n_files_match']))
print('  .pyc/黑名单: %d / %d' % (len(zpyc), len(zblack)))
print('  两遍体积   : %s（收敛=%s）' % (sizes, len(set(sizes)) == 1))
