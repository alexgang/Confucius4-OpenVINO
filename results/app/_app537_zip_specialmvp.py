#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app537_zip_specialmvp.py —— 给 Special MVP 打 zip（**新版本号，不覆盖旧包**）。

纪律：
  · **必须先有包上验收 PASS**（APP-107 §1.4 的同款 fail-closed）⇒ 否则拒绝出包；
  · **两遍打包**：第 1 遍量出 zip 字节数 ⇒ 回填 README（固定宽度 ⇒ 长度不变）
    ⇒ 第 2 遍体积应**完全一致**（收敛）⇒ 不一致就报错（rc11 的老坑）；
  · zip 内**不含** `.pyc` / 黑名单文件（打之前断言）。

🔴 **2026-11-14 §204 修订**（目标包参数化 + 闸门修正，见 STATUS §204）：
  · 原先把 `PKG_NAME`/`DST_PKG`/`ZIP`/`ACCEPT`/`REPORT` **全写死成 sp1**
    ⇒ 给 sp2 打 zip 必须改源码，最易漏改的正是 `ACCEPT` ⇒ **fail-closed
    闸门被架空**（拿 sp1 的验收结论放行 sp2）；现在改为**参数指定**，
    且闸门**强制「验收证据必须属于正在打包的那个包」**；
  · 验收 verdict 的判定由**精确字符串 `'PASS'`** 改为接受 reviewer 在 §202
    明文规定的口径 `'PASS'` 与 `'PASS（有 N 项未结：…）'`（未结项单列
    `open_issues`、不并入 PASS 判定）；其它写法一律拒绝；
  · 新增 `--check-only`：**只跑闸门、零写入**，可在用户通知打包前先验证就绪度。

🔴 **2026-11-14 §205 修订**（闸门再加一条：验收证据必须与**包内容**绑定）：
  · §204 修的是「**证据属于哪个包**」；但 Special MVP 的验收证据**一个 sha256 都没有**
    （只有 "28 个 .py，不一致 0 个" 这类计数）⇒ 闸门**对包内容 0 字节验证**
    ⇒ **验收后再改包照样能出包**；
  · 现在要求证据带 `pkg_content`（验收时逐文件 SHA256），闸门**逐条重算比对**，
    并做**反向集合校验**（包内 `app/*.py` 集合必须与证据一致 ⇒ 验收后新增 .py 也拦）；
  · 证据没有内容绑定 ⇒ **直接拒绝**（fail-closed，提示重跑包上验收）。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import zipfile

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')

# 🔴🔴 **2026-11-14 §204 重写**：原先 `PKG_NAME` / `DST_PKG` / `ZIP` / `ACCEPT`
#    / `REPORT` **全部写死成 sp1** ⇒ 要给 sp2 打 zip **必须改源码**，
#    而最容易被漏改的恰恰是 `ACCEPT`（验收证据）⇒ **fail-closed 闸门被架空**：
#    实测「只改 PKG_NAME、ACCEPT 仍指 sp1」⇒ 拿 **sp1 的验收结论**放行
#    **sp2**，闸门照样通过（详见 STATUS §204 ②）。
#    ⇒ 现在：目标包 / 验收证据 / zip / 报告 **都可参数指定**，
#      且闸门**强制「证据必须属于正在打包的那个包」**。
DEFAULT_PKG_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
DEFAULT_ACCEPT = 'app536_specialmvp_acceptance.json'
DEFAULT_REPORT = 'app537_specialmvp_zip.json'
NUM_WIDTH = 18

_ap = argparse.ArgumentParser(
    description='给 Special MVP 打 zip（新版本号，不覆盖旧包；§204 参数化）')
_ap.add_argument('--pkg-name', default=DEFAULT_PKG_NAME,
                 help='目标包目录名（sp2 ⇒ '
                      'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2）')
_ap.add_argument('--accept', default=DEFAULT_ACCEPT,
                 help='包上验收证据文件名（在 results/app/ 下）；'
                      '闸门会强制它**属于 --pkg-name**')
_ap.add_argument('--report', default=None,
                 help='zip 证据 json 路径（默认 results/app/<包名>_zip.json）')
_ap.add_argument('--zip', default=None,
                 help='输出 zip 路径（默认 shared/specialmvp/<包名>.zip）')
_ap.add_argument('--check-only', action='store_true',
                 help='只跑闸门并打印结论，**不写任何文件**'
                      '（不出 zip、不改 README）')
_args = _ap.parse_args()

PKG_NAME = _args.pkg_name
DST_PKG = os.path.join(HOME, PKG_NAME)
ZIP = _args.zip or os.path.join(HOME, 'shared', 'specialmvp',
                                PKG_NAME + '.zip')
ACCEPT = os.path.join(RESULTS, _args.accept)
if _args.report:
    REPORT = _args.report
elif PKG_NAME == DEFAULT_PKG_NAME:
    REPORT = os.path.join(RESULTS, DEFAULT_REPORT)
else:
    REPORT = os.path.join(
        RESULTS, PKG_NAME.replace('Confucius4_LiveCaption_', '') + '_zip.json')


def _norm_pkg(p):
    """归一化包目录路径（便于比较：大小写不敏感、去尾部分隔符）。"""
    return os.path.normcase(os.path.normpath(p)).rstrip('\\/').lower()


def _verdict_ok(v):
    """验收 verdict 是否算「通过」。

    🔴 **2026-11-14 §204**：原先是 `verdict != 'PASS'` **精确字符串**比较 ⇒
    reviewer 在 §202 明文规定的口径「**PASS（有 1 项未结：退出码异常）**」
    （未结项单列 `open_issues`、**不并入** PASS 判定）会被**误判为未通过**
    ⇒ 正确指向 sp2 自己的证据反而**打不出 zip**（假 FAIL）。
    ⇒ 现在接受 reviewer 口径的两种写法：'PASS' 与 'PASS（…）'／'PASS(…)'；
      其它任何写法（'FAIL'／空／缺字段）一律拒绝。
    """
    if not isinstance(v, str):
        return False
    return v == 'PASS' or v.startswith('PASS（') or v.startswith('PASS(')


def check_acceptance(pkg_dir, accept_path):
    """🔴 **fail-closed 验收闸门**（§204 重写）：任一条不满足 ⇒ 抛错拒绝出包。

    ① **证据存在**；
    ② **证据属于正在打包的那个包**（`acc['pkg']` 归一化后必须等于 `pkg_dir`）
       ⇒ 杜绝「拿 sp1 的验收结论放行 sp2」（§204 ② 实测的 fail-open）；
    ③ **verdict 算通过**（见 `_verdict_ok`）⇒ 其它写法一律拒绝。
    """
    if not os.path.isfile(accept_path):
        raise RuntimeError('缺包上验收证据，拒绝打包：%s' % accept_path)
    acc = json.load(open(accept_path, encoding='utf-8'))
    problems = []
    acc_pkg = acc.get('pkg')
    if not acc_pkg:
        problems.append('验收证据缺 pkg 字段，无法确认它属于哪个包')
    elif _norm_pkg(acc_pkg) != _norm_pkg(pkg_dir):
        problems.append('验收证据属于另一个包：证据 pkg=%r ≠ 目标包=%r'
                        % (acc_pkg, pkg_dir))
    if not _verdict_ok(acc.get('verdict')):
        problems.append('包上验收未通过（verdict=%r），拒绝打包'
                        % (acc.get('verdict'),))
    if problems:
        raise RuntimeError('；'.join(problems))
    return acc


def check_release_identity(pkg_dir, pkg_name):
    """🔴 包版本标识自洽：`release.json.version` 必须等于包目录名里的版本后缀。

    ⇒ 杜绝「目录名 sp2、内容自称 sp1」这类张冠李戴。
    ⚠️ SpecialMVP / MiniMVP 形态的 `app/MANIFEST.json` **没有** `version` 字段
       （只有完整版有）⇒ 版本标识**只**在 `release.json` 里 ⇒ 这里必须查。
    """
    rp = os.path.join(pkg_dir, 'release.json')
    if not os.path.isfile(rp):
        raise RuntimeError('包内缺 release.json，拒绝打包：%s' % rp)
    rel = json.load(open(rp, encoding='utf-8'))
    m = re.search(r'_v([0-9][0-9A-Za-z.\-+]*)$', pkg_name)
    if not m:
        raise RuntimeError('包目录名里解析不出版本号，拒绝打包：%r' % pkg_name)
    want, got = m.group(1), rel.get('version')
    if got != want:
        raise RuntimeError('版本标识不自洽：release.json.version=%r ≠ 目录名版本=%r'
                           % (got, want))
    return rel


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check_content_binding(pkg_dir, acc):
    """🔴🔴 **§205 新增：验收证据必须与包的「当前内容」绑定**（fail-closed）。

    🔴 **为什么 §204 之后还需要这一条（不同轴）**：§204 修的是「**证据属于哪个包**」
       （`acc['pkg']` 必须等于目标包目录）。但**验收证据本身不记任何哈希**
       （Special MVP 的验收证据里 **sha256 出现 0 次**，只有 "28 个 .py，不一致 0 个"
       这类计数）⇒ 闸门**对包内容一个字节都没验证** ⇒
       **验收之后再改包（同步新代码 / 手改文件），照样能出包**，
       而验收记录会（不实地）声称这份包已被验收过。

    ⇒ 现在要求证据里带 `pkg_content`（验收时逐文件 SHA256），
      并**逐条重算比对**；另做**反向集合校验**（包内 `app/*.py` 集合必须与证据
      记录一致 ⇒ 验收后**新增** .py 也会被抓住）。
    ⇒ 证据**没有**内容绑定 ⇒ 直接拒绝（fail-closed，提示重跑包上验收）。
    """
    pc = acc.get('pkg_content')
    if not isinstance(pc, dict):
        raise RuntimeError('验收证据没有内容绑定字段 `pkg_content` ⇒ 无法确认包内容'
                           '与验收时一致，拒绝打包（请重跑包上验收后再打包）')
    files = pc.get('files')
    if not isinstance(files, dict) or not files:
        raise RuntimeError('验收证据的 `pkg_content.files` 为空 ⇒ 拒绝打包')
    problems = []
    for rel, want in sorted(files.items()):
        p = os.path.join(pkg_dir, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            problems.append('缺 %s' % rel)
            continue
        got = sha256_file(p)
        if got != want:
            problems.append('内容已变 %s' % rel)
    # 反向集合：包内 app/*.py 必须与证据记录一致（防止验收后新增 .py）
    appdir = os.path.join(pkg_dir, 'app')
    now_py = set()
    if os.path.isdir(appdir):
        now_py = {'app/' + f for f in os.listdir(appdir) if f.endswith('.py')}
    bound_py = {r for r in files if r.startswith('app/') and r.endswith('.py')}
    if now_py - bound_py:
        problems.append('验收后新增 .py：%s' % sorted(now_py - bound_py)[:3])
    if bound_py - now_py:
        problems.append('证据里的 .py 不在包内：%s' % sorted(bound_py - now_py)[:3])
    if problems:
        raise RuntimeError('包内容与验收证据不一致（%d 项）：%s'
                           % (len(problems), '；'.join(problems[:5])))
    return pc


ev = {'zip': ZIP, 'pkg': DST_PKG, 'actions': []}
t0 = time.time()

# ── ① 验收必须 PASS（fail-closed；§204 重写：证据须属于本包；§205 加内容绑定）──
acc = check_acceptance(DST_PKG, ACCEPT)
ev['accept_verdict'] = acc.get('verdict')
ev['accept_checks'] = acc.get('checks')
ev['accept_pkg'] = acc.get('pkg')
ev['accept_open_issues'] = acc.get('open_issues')
rel = check_release_identity(DST_PKG, PKG_NAME)
ev['release_version'] = rel.get('version')
pc = check_content_binding(DST_PKG, acc)
ev['accept_content_binding'] = {'n_files': pc.get('n_files'),
                                 'tree_digest': pc.get('tree_digest')}
if os.path.exists(ZIP):
    raise RuntimeError('zip 已存在（不覆盖旧版本，APP-055）：%s' % ZIP)
if _args.check_only:
    ev['check_only'] = True
    print('闸门 PASS：验收 verdict=%r（证据属于 %s）'
          % (acc.get('verdict'), acc.get('pkg')))
    print('            release.json.version=%r（目录名 %s）'
          % (rel.get('version'), PKG_NAME))
    if acc.get('open_issues'):
        print('⚠️ 验收带未结项（已随证据带入 zip 报告）：%s'
              % [oi.get('id') for oi in acc['open_issues']])
    print('            内容绑定：%s 个文件，tree_digest=%s…'
          % (pc.get('n_files'), str(pc.get('tree_digest'))[:16]))
    print('check-only：**未写任何文件**（未出 zip、未改 README）')
    raise SystemExit(0)
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
        # 🔴 本机安全删除 shim 会把删除转回收站并可能失败 ⇒ 这里必须**报清楚**
        #   （否则脚本带着「已回填 README 的半成品包」死掉，磁盘还留着 13 GiB 临时文件）
        try:
            os.remove(tmp)     # 第 1 遍只用来量体积
        except OSError as e:
            raise RuntimeError('第 1 遍临时 zip 删除失败（%s）⇒ 请手工处理并确认磁盘：%s'
                               % (e, tmp))
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
