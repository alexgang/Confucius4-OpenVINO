#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app579_build_specialmvp_sp3.py —— 构建 **Special MVP sp3**（APP-111 的改码版）。

🔴 **为什么要有 sp3**（reviewer 原话，APP-111 §2）：
   「sp2 已冻结（APP-110 §0②），所以这次改动**出 sp3**（基于 sp2 复制，sp2 目录不动）。」
   ⇒ 本脚本**从 sp2 复制**（不是从 sp1），**sp2 目录一个字都不动**。
   ⇒ 本轮改动只有两处参数（`tts_late_drop_sec` 6.0→0.0、`tts_speed_max_zh` 1.50→2.00）
     ⇒ 只同步这两个文件所在的 4 个 .py（device_config / time_stretch / tts_worker / tts_service）。

🔴 **与 _app550（sp2 构建脚本）的关系**：**骨架完全相同**，只改常量与文案
   （SP2→SP3、源包 sp1→sp2、版本号、release.json 的变更说明）⇒
   「代码骨架等价校验后升级基底」的定点做法，不另起炉灶。

🔴 **纪律**：
  · **不覆盖、不删除** sp1 / sp2 的目录与 zip（APP-055）；
  · **仓库 ⇄ 客户包 = 两份独立副本** ⇒ 代码**只做定点同步**（逐文件比对 +
    唯一命中断言），**绝不整目录覆盖**；
  · 本机**安全删除 shim** 把删除转回收站且会失败 ⇒ **构建脚本一律不删**：
    拷贝时排除（`robocopy /XF *.pyc /XD __pycache__`）⇒ `.pyc` 天然 0；
  · 🔴 **本轮不生成 zip**（APP-111 §2：「zip 等验收通过后再打」；用户级纪律：
    **用户不通知 ⇒ 不主动打包**）⇒ README 的 zip 体积字段留**占位**。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
RESULTS = os.path.join(REPO, 'results', 'app')
SP2_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2'
SP3_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp3'
SP2 = os.path.join(HOME, SP2_NAME)
SP3 = os.path.join(HOME, SP3_NAME)
VERSION = '1.0-sp3'
REPORT = os.path.join(RESULTS, 'app579_specialmvp_sp3_build.json')

#: 🔴 **本轮随 sp3 同步进包的文件**（APP-111 §1 只改了这两处参数）。
#:   `device_config.py`  ⇒ `NUMERIC_DEFAULTS`（tts_late_drop_sec / tts_speed_max_zh）
#:   `time_stretch.py`   ⇒ `ZH_SPEED_MAX`（1.50 → 2.00）
#:   `tts_worker.py`     ⇒ 阈值读取 + late_drop 守卫 + `--late-drop-sec` 默认
#:   `tts_service.py`    ⇒ 把阈值传给 worker（`--late-drop-sec`）
SYNC_FILES = ['device_config.py', 'time_stretch.py', 'tts_worker.py',
              'tts_service.py']

BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']
NUM_WIDTH = 18

ev = {'pkg': SP3, 'from_pkg': SP2, 'version': VERSION,
      'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'actions': [],
      'gates': {}}
t0 = time.time()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root):
    n, total = 0, 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, total


def _blacklist_hit(rel):
    import fnmatch
    for pat in BLACKLIST_PATTERNS:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(
                os.path.basename(rel), pat):
            return pat
    return None


def find_blacklist(root):
    hits = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), root).replace('\\', '/')
            pat = _blacklist_hit(rel)
            if pat:
                hits.append({'file': rel, 'pattern': pat})
    hits.sort(key=lambda h: h['file'])
    return hits


def count_pyc(root):
    n = 0
    for dp, _dn, fn in os.walk(root):
        n += sum(1 for f in fn if f.endswith('.pyc'))
    return n


# ── ① fail-closed：sp3 目录**必须不存在**（不覆盖旧版本）──
#   ⚠️ **可续跑**：本机安全删除 shim 让「删 4 万个文件」不可行 ⇒ 上一次构建
#      中途失败时**不能删 sp3 重来** ⇒ 允许「sp3 已存在 ⇒ 跳过拷贝、从断点继续」，
#      但**必须先核验拷贝完整性**（文件数与 sp2 一致、pyvenv/MANIFEST 已重定位）。
RESUME = os.path.isdir(SP3)
if not os.path.isdir(SP2):
    raise RuntimeError('源包 sp2 不存在：%s' % SP2)
if RESUME:
    n_sp2, b_sp2 = dir_stats(SP2)
    n_sp3, b_sp3 = dir_stats(SP3)
    if n_sp3 != n_sp2:
        raise RuntimeError('续跑前置检查失败：sp3 文件数 %d ≠ sp2 %d（拷贝不完整）'
                           % (n_sp3, n_sp2))
    ev['actions'].append('RESUME: sp3 已存在（文件数 %d = sp2）⇒ 跳过拷贝，从断点继续'
                          % n_sp3)
    ev['resume'] = {'n_files_sp2': n_sp2, 'n_files_sp3': n_sp3}
else:
    ev['actions'].append('precondition: sp3 目录不存在 + sp2 存在 ✔')

# ── ② 拷贝 sp2 → sp3（**不删任何东西**；排除 .pyc / __pycache__）──
if not RESUME:
    cmd = ['robocopy', SP2, SP3, '/E', '/XF', '*.pyc', '/XD', '__pycache__',
           '/R:1', '/W:1', '/MT:16', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    rc = p.returncode
    # robocopy: 0=无改动 1=有复制成功 2=额外文件 3=有更新+额外 … ≥8 = 失败
    if rc >= 8:
        raise RuntimeError('robocopy 失败 rc=%d\n%s\n%s' % (rc, p.stdout, p.stderr))
    ev['actions'].append('robocopy rc=%d（%d = 有复制成功）' % (rc, rc))
n1, b1 = dir_stats(SP3)
ev['after_copy'] = {'n_files': n1, 'bytes': b1,
                    'elapsed_s': round(time.time() - t0, 1)}

# ── ③ cuda_env/pyvenv.cfg：**重定位**到 sp3（否则边车会去用 sp2 的 python）──
pv = os.path.join(SP3, 'cuda_env', 'pyvenv.cfg')
raw = open(pv, encoding='utf-8').read()
if raw.count(SP3) == 4 and raw.count(SP2) == 0:
    ev['actions'].append('cuda_env/pyvenv.cfg：已是 sp3 路径（续跑，跳过重定位）')
elif raw.count(SP2) == 4:
    with open(pv, 'w', encoding='utf-8', newline='\n') as f:
        f.write(raw.replace(SP2, SP3))
    ev['actions'].append('cuda_env/pyvenv.cfg：sp2 路径 → sp3（4 处）')
else:
    raise RuntimeError('cuda_env/pyvenv.cfg 里 sp2 路径 %d 次 / sp3 路径 %d 次'
                       '（预期 4 / 0 或 0 / 4）' % (raw.count(SP2), raw.count(SP3)))
ev['pyvenv_cfg_after'] = open(pv, encoding='utf-8').read()

# ── ③b app/MANIFEST.json：`pkg_models_root` 必须指向 **sp3 自己的** models 目录 ──
#   （§205 的构建期修法：转义形态定点替换 + 唯一命中断言 + 写盘后逐字节复核）
mpath = os.path.join(SP3, 'app', 'MANIFEST.json')
mtxt = open(mpath, encoding='utf-8', newline='').read()
man = json.loads(mtxt)
cur_root = man.get('pkg_models_root')
want_root = os.path.join(SP3, 'models')
if cur_root != want_root:
    if not cur_root:
        raise RuntimeError('MANIFEST 缺 pkg_models_root 字段')
    esc_old = json.dumps(cur_root)[1:-1]
    esc_new = json.dumps(want_root)[1:-1]
    n_hit = mtxt.count(esc_old)
    if n_hit != 1:
        raise RuntimeError('MANIFEST 里 pkg_models_root 的转义形态出现 %d 次'
                           '（预期 1）' % n_hit)
    raw2 = mtxt.replace(esc_old, esc_new)
    m2 = json.loads(raw2)
    if m2.get('pkg_models_root') != want_root:
        raise RuntimeError('替换后 pkg_models_root 仍不对')
    diff_keys = {k for k in set(man) | set(m2) if man.get(k) != m2.get(k)}
    if diff_keys - {'pkg_models_root'}:
        raise RuntimeError('MANIFEST 改动范围超出预期（只允许 pkg_models_root，'
                           '实际多了 %s）' % sorted(diff_keys - {'pkg_models_root'}))
    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(raw2)
    if open(mpath, encoding='utf-8', newline='').read() != raw2:
        raise RuntimeError('MANIFEST 写盘后逐字节不一致')
    ev['actions'].append('app/MANIFEST.json: pkg_models_root sp2 → sp3'
                         '（%s）' % want_root)
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'raw_hits': n_hit}
else:
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'note': '已是 sp3 自己的 models 目录，无需改'}

# ── ④ app 代码定点同步：**只同步 SYNC_FILES 这 4 个**（APP-111 §1 改动面）──
#   ⚠️ 不是「全部 .py 都覆盖」⇒ 其余文件保持 sp2 原样（sp2 目录不动、sp3 逐字继承）。
appdir = os.path.join(SP3, 'app')
synced, same, no_dev = [], [], []
for f in sorted(os.listdir(appdir)):
    if not f.endswith('.py'):
        continue
    src = os.path.join(DEV, f)
    dst = os.path.join(appdir, f)
    if not os.path.isfile(src):
        no_dev.append(f)
        continue
    if sha256_file(src) == sha256_file(dst):
        same.append(f)
        continue
    if f not in SYNC_FILES:
        # 🔴 **不在本轮改动面里的文件若与 dev 不同 ⇒ 停下来报 reviewer**
        #    （不允许「顺手」把别的改动带进 sp3）。
        raise RuntimeError('包内 %s 与 dev 不同，但它不在本轮 SYNC_FILES=%s 内'
                           ' ⇒ 中止（避免夹带改动）' % (f, SYNC_FILES))
    shutil.copy2(src, dst)
    synced.append({'file': f,
                   'sha256': sha256_file(dst),
                   'bytes': os.path.getsize(dst)})
ev['app_sync'] = {'sync_files_declared': SYNC_FILES, 'synced': synced,
                  'n_same': len(same), 'n_no_dev_counterpart': no_dev}
# ⚠️ `synced` 里装的是 **dict** ⇒ 判「是否已同步」要看 `file` 字段，不能用 `in`。
synced_names = [x['file'] for x in synced]
missing = [f for f in SYNC_FILES
           if f not in synced_names and f not in same]
if missing:
    raise RuntimeError('本轮应当同步的文件既没被同步、也没与 dev 一致（可疑）：%s'
                       % missing)
ev['actions'].append('app 代码同步：%d 个文件被改写（%s）；其余与 dev 逐字相同 %d 个'
                     % (len(synced), ', '.join(synced_names) or '(无)', len(same)))

# ── ⑤ release.json：版本 + 纠偏编号 + sp3 变更说明 ──
rel = os.path.join(SP3, 'release.json')
r = json.load(open(rel, encoding='utf-8'))
r['version'] = VERSION
for c in ('APP-110', 'APP-111'):
    if c not in r.get('corrections', []):
        r['corrections'].append(c)
r['sp3_changes'] = [
    "APP-111 §1（用户 2026-11-15 决定）：**TTS 跳句阈值 6.0 s → 0.0 s** ⇒ "
    "语义是「**0 = 关闭跳句，一句都不丢**」（取代 APP-092 §2 的 6.0 s 阈值）。"
    "⚠️ 实现侧保证「阈值 ≤ 0 ⇒ 绝不跳句」（`tts_worker` 的 "
    "`self._late_drop_sec > 0.0` 守卫短路），**不是**「晚 >0 s 就跳」。",
    "APP-111 §1（用户 2026-11-15 决定）：**自适应语速上限 1.5× → 2.0×**"
    "（中文目标；`tts_speed_max_zh` 与 `time_stretch.ZH_SPEED_MAX`）。"
    "⚠️ **只放开上限**：滞后→倍率的增益曲线不变"
    "（死区 3.0 s / 每秒 0.025 / 滞回 2.0 s / 步长 ±0.1 全部照旧）；"
    "**非中文目标**仍是 1.0–1.30×（10-29 原口径，不变）。",
    "APP-110 §0：sp2 **冻结**（本包基于 sp2 复制，**sp2 目录一字未动**）；"
    "sp3 的 zip **等验收通过后再打**（本轮只出包目录）。",
]
with open(rel, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(r, f, ensure_ascii=False, indent=1)
ev['actions'].append('release.json：version=%s；corrections += APP-110/APP-111；'
                     '新增 sp3_changes（%d 条）' % (VERSION, len(r['sp3_changes'])))

# ── ⑥ README：标题 + 体积行（**定点替换 + 唯一命中断言**）──
n_files, dir_bytes = dir_stats(SP3)
zh = os.path.join(SP3, 'README_zh.md')
txt = open(zh, encoding='utf-8').read()
hits = [ln for ln in txt.splitlines() if ln.startswith('* **包体积（实测）**')]
if len(hits) != 1:
    raise RuntimeError('README_zh.md 的「包体积」行命中 %d 次（应恰好 1 次）'
                       % len(hits))
old_line = hits[0]
new_line = ('* **包体积（实测）**：解压后 **%s 个文件 / %s B（%.3f GiB）**；'
            'zip **待打包**（本版**只出包目录**；zip 须**用户通知后**才生成）。'
            % ('{:,}'.format(n_files),
               ('%*s' % (NUM_WIDTH, format(int(dir_bytes), ','))),
               dir_bytes / 1024 ** 3))
txt = txt.replace(old_line, new_line)
txt = txt.replace('**Special MVP 1.0-sp2**', '**Special MVP %s**' % VERSION)
with open(zh, 'w', encoding='utf-8', newline='\n') as f:
    f.write(txt)
ev['readme_zh'] = {'old_size_line': old_line, 'new_size_line': new_line}

en = os.path.join(SP3, 'README_en.md')
if os.path.isfile(en):
    txt = open(en, encoding='utf-8').read()
    hits = [ln for ln in txt.splitlines()
            if ln.startswith('* **Package size (measured)**')]
    if len(hits) == 1:
        old_line = hits[0]
        new_line = ('* **Package size (measured)**: unpacked **%s files / %s B'
                    ' (%.3f GiB)**; zip **to be built** (this build ships the'
                    ' **package directory** only; the zip requires explicit'
                    ' user approval).'
                    % ('{:,}'.format(n_files),
                       ('%*s' % (NUM_WIDTH, format(int(dir_bytes), ','))),
                       dir_bytes / 1024 ** 3))
        txt = txt.replace(old_line, new_line)
        with open(en, 'w', encoding='utf-8', newline='\n') as f:
            f.write(txt)
        ev['readme_en'] = {'old_size_line': old_line, 'new_size_line': new_line}
    else:
        ev['readme_en'] = {'skipped': '命中 %d 次' % len(hits)}

# ── ⑦ 闸门（**只断言，不 purge**；本机安全删除 shim 会失败）──
n_pyc = count_pyc(SP3)
black = find_blacklist(SP3)
mismatch = []
for f in sorted(os.listdir(appdir)):
    if not f.endswith('.py'):
        continue
    src = os.path.join(DEV, f)
    if not os.path.isfile(src):
        continue
    if sha256_file(src) != sha256_file(os.path.join(appdir, f)):
        mismatch.append(f)
pv_txt = open(pv, encoding='utf-8').read()
prof = json.load(open(os.path.join(SP3, 'package_profile.json'),
                      encoding='utf-8'))
n_files2, dir_bytes2 = dir_stats(SP3)
ev['gates'] = {
    'n_pyc': n_pyc,
    'n_blacklist': len(black),
    'blacklist': black[:20],
    'app_files_mismatch_vs_dev': mismatch,
    'pyvenv_cfg_has_sp2_path': (SP2 in pv_txt),
    'pyvenv_cfg_has_sp3_path': (SP3 in pv_txt),
    'profile': prof.get('profile'),
    'allow_cuda': prof.get('allow_cuda'),
    'n_files': n_files2,
    'dir_bytes': dir_bytes2,
}
ok = (n_pyc == 0 and not black and not mismatch
      and SP2 not in pv_txt and SP3 in pv_txt
      and prof.get('profile') == 'specialmvp')

# ── ⑦b **本轮两处参数**在包内确实生效（**行为级**读包内代码）──
dc_txt = open(os.path.join(appdir, 'device_config.py'), encoding='utf-8').read()
ts_txt = open(os.path.join(appdir, 'time_stretch.py'), encoding='utf-8').read()
tw_txt = open(os.path.join(appdir, 'tts_worker.py'), encoding='utf-8').read()
sv_txt = open(os.path.join(appdir, 'tts_service.py'), encoding='utf-8').read()
ev['param_check'] = {
    'device_config.tts_late_drop_sec==0.0':
        "'tts_late_drop_sec': 0.0" in dc_txt,
    'device_config.tts_speed_max_zh==2.00':
        "'tts_speed_max_zh': 2.00" in dc_txt,
    'time_stretch.ZH_SPEED_MAX==2.00':
        'ZH_SPEED_MAX = 2.00' in ts_txt,
    'worker_guard_late_drop_sec_gt_0':
        'self._late_drop_sec > 0.0' in tw_txt,
    'worker_env_default_0.0':
        "'LIVECAP_TTS_LATE_DROP_SEC', '') or 0.0" in tw_txt,
    'service_get_numeric_default_0.0':
        "get_numeric('tts_late_drop_sec', 0.0)" in sv_txt,
}
for k, v in ev['param_check'].items():
    if not v:
        ok = False
ev['verdict'] = 'PASS' if ok else 'FAIL'
ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
ev['elapsed_s'] = round(time.time() - t0, 1)
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('VERDICT=%s  n_files=%d  bytes=%d  synced=%d  -> %s'
      % (ev['verdict'], n_files2, dir_bytes2, len(synced), REPORT))
if not ok:
    print(json.dumps(ev['gates'], ensure_ascii=False, indent=1))
    print(json.dumps(ev['param_check'], ensure_ascii=False, indent=1))
sys.exit(0 if ok else 1)
