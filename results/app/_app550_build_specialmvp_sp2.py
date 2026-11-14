#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app550_build_specialmvp_sp2.py —— 构建 **Special MVP sp2**（APP-108 §2 的修复版）。

🔴 **为什么要有 sp2**（reviewer 原话）：
   「如果需要改代码，就出 **sp2**，不能原地改 sp1 目录或 zip。」
   ⇒ 实测确证 sp1 有**真缺陷**（`results/app/app549_sp1_device_resolution.json`
   ⇒ 残留旧配置会把 Special MVP 的出厂默认 MT=NPU **覆盖成 GPU.0**）
   ⇒ 必须**新版本号**：新目录 + 新 release.json + 新 README 体积行。

🔴 **纪律**：
  · **不覆盖、不删除** sp1 的目录与 zip（APP-055）；
  · **仓库 ⇄ 客户包 = 两份独立副本** ⇒ 代码**只做定点同步**（逐文件比对 +
    唯一命中断言），**绝不整目录覆盖**；
  · 本机**安全删除 shim** 把删除转回收站且会失败 ⇒ **构建脚本一律不删**：
    拷贝时排除（`robocopy /XF *.pyc /XD __pycache__`）⇒ `.pyc` 天然 0；
  · 🔴 **本轮不生成 zip**（用户级纪律：**用户不通知 ⇒ 不主动打包**）
    ⇒ README 的 zip 体积字段留**占位**（仍是固定前缀 ⇒ 日后 zip 脚本可整行替换）。
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
SP1_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
SP2_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2'
SP1 = os.path.join(HOME, SP1_NAME)
SP2 = os.path.join(HOME, SP2_NAME)
VERSION = '1.0-sp2'
REPORT = os.path.join(RESULTS, 'app550_specialmvp_sp2_build.json')

BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']
NUM_WIDTH = 18

ev = {'pkg': SP2, 'from_pkg': SP1, 'version': VERSION,
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


def replace_once(path, old, new, what):
    """**定点替换 + 唯一命中断言**（不匹配 / 命中多处 ⇒ 抛错，零改动）。"""
    txt = open(path, encoding='utf-8').read()
    n = txt.count(old)
    if n != 1:
        raise RuntimeError('%s：%s 命中 %d 次（应恰好 1 次）' % (path, what, n))
    out = txt.replace(old, new)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)
    return out


# ── ① fail-closed：sp2 目录**必须不存在**（不覆盖旧版本）──
if os.path.exists(SP2):
    raise RuntimeError('sp2 目录已存在（不覆盖旧版本，APP-055）：%s' % SP2)
ev['actions'].append('precondition: sp2 目录不存在 ✔')

# ── ② 拷贝 sp1 → sp2（**不删任何东西**；排除 .pyc / __pycache__）──
cmd = ['robocopy', SP1, SP2, '/E', '/XF', '*.pyc', '/XD', '__pycache__',
       '/R:1', '/W:1', '/MT:16', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
rc = p.returncode
# robocopy: 0=无改动 1=有复制成功 2=额外文件 3=有更新+额外 … ≥8 = 失败
if rc >= 8:
    raise RuntimeError('robocopy 失败 rc=%d\n%s\n%s' % (rc, p.stdout, p.stderr))
ev['actions'].append('robocopy rc=%d（%d = 有复制成功）' % (rc, rc))
n1, b1 = dir_stats(SP2)
ev['after_copy'] = {'n_files': n1, 'bytes': b1,
                    'elapsed_s': round(time.time() - t0, 1)}

# ── ③ cuda_env/pyvenv.cfg：**重定位**到 sp2（否则边车会去用 sp1 的 python）──
pv = os.path.join(SP2, 'cuda_env', 'pyvenv.cfg')
raw = open(pv, encoding='utf-8').read()
n_sp1 = raw.count(SP1)
if n_sp1 != 4:
    raise RuntimeError('cuda_env/pyvenv.cfg 里 sp1 路径出现 %d 次（预期 4）'
                       % n_sp1)
with open(pv, 'w', encoding='utf-8', newline='\n') as f:
    f.write(raw.replace(SP1, SP2))
ev['actions'].append('cuda_env/pyvenv.cfg：sp1 路径 → sp2（4 处）')
ev['pyvenv_cfg_after'] = open(pv, encoding='utf-8').read()

# ── ③b app/MANIFEST.json：`pkg_models_root` 必须指向 **sp2 自己的** models 目录 ──
# 🔴🔴 **2026-11-14 §205 修掉的真缺陷（构建期根因）**：上面的 robocopy 把 sp1 的
#    MANIFEST **原样**带过来 ⇒ `pkg_models_root` 仍指向 **sp1** 的 models 目录
#    （§202 的验收脚本本想重定向，但那段是**死代码**：`SP1 in mtxt` 在**裸 JSON
#    文本**里找**未转义**路径 ⇒ 恒 False ⇒ 从未执行）
#    ⇒ sp2 的 MANIFEST **自相矛盾**（指向不在包内的另一个包的 models 目录）＋
#    泄漏构建机家目录字面量到交付包。
#    这里在**构建期**就改对：转义形态定点替换 + 唯一命中断言 + 写盘后逐字节复核
#    （只动 `pkg_models_root` 一个键）。
mpath = os.path.join(SP2, 'app', 'MANIFEST.json')
mtxt = open(mpath, encoding='utf-8', newline='').read()
man = json.loads(mtxt)
cur_root = man.get('pkg_models_root')
want_root = os.path.join(SP2, 'models')
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
    ev['actions'].append('app/MANIFEST.json: pkg_models_root sp1 → sp2'
                         '（%s）' % want_root)
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'raw_hits': n_hit}
else:
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'note': '已是 sp2 自己的 models 目录，无需改'}

# ── ④ app 代码定点同步：逐文件比对，**只改不同的** ──
appdir = os.path.join(SP2, 'app')
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
    shutil.copy2(src, dst)
    synced.append({'file': f,
                   'sha256': sha256_file(dst),
                   'bytes': os.path.getsize(dst)})
ev['app_sync'] = {'synced': synced, 'n_same': len(same),
                  'n_no_dev_counterpart': no_dev}

# ── ⑤ release.json：版本 + 纠偏编号 + sp2 变更说明 ──
rel = os.path.join(SP2, 'release.json')
r = json.load(open(rel, encoding='utf-8'))
r['version'] = VERSION
for c in ('APP-108', 'APP-109'):
    if c not in r.get('corrections', []):
        r['corrections'].append(c)
r['sp2_changes'] = [
    "APP-108 §2 **真缺陷修复**：`device_config.current_profile()` 原来只返回 "
    "'minimvp'/'full' ⇒ **Special MVP 被当成完整版** ⇒ `stale_device_keys()` "
    "从不忽略旧配置里的设备项 ⇒ 客户机上残留的 59 B 旧 3 键配置"
    "（asr/mt/tts 全 GPU.0）**覆盖了出厂默认的 MT=NPU**（实测：sp1 上 "
    "`get_devices()` 解析出 GPU.0/GPU.0/GPU.0，并打印「ASR 与 MT 都放在 "
    "GPU.0」告警）。⇒ 现在如实返回 'specialmvp'，并按 **profile + 代次**"
    "（specialmvp = 第 10 代）判定「旧配置」⇒ profile 不同 ⇒ **不沿用**。",
    "APP-108 §2：`save_config()` 写 `defaults_version` 时改用**当前包形态的代次**"
    "（specialmvp=10／minimvp=9）⇒ 不会把 specialmvp 的选择盖成 minimvp 的代次。",
    "APP-108 §2：「ASR 与 MT 同在 GPU」那句文案改按**是否 stateful 解码器**判定"
    "（specialmvp 与 minimvp 都是 stateful ⇒ 旧「会 CL_OUT_OF_RESOURCES」"
    "文案对 specialmvp 同样不成立）⇒ `device_config.uses_stateful_asr_decoder()`。",
    "APP-109 ①：Special MVP **允许带 CUDA TTS 路径**（用户 11-13/11-14 决定）"
    "⇒ 本包的 `allow_cuda=True` 保留，**其余打包规则不变**。",
    "APP-109 ②：**APP-108 §1（GitHub 上的明文口令）已被 reviewer 撤回** ⇒ "
    "本版**未改动**任何含口令的文件。",
    "README_en.md 的「Package size (measured)」行原是 **MiniMVP rc11 的数字**"
    "（10,629 files / 6,694,657,456 B / zip 6,697,683,352 B）—— 与本包无关 "
    "⇒ 本版**按实测值改正**（zip 字段待打包后回填）。",
]
with open(rel, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(r, f, ensure_ascii=False, indent=1)
ev['actions'].append('release.json：version=%s；corrections += APP-108/APP-109；'
                     '新增 sp2_changes（%d 条）' % (VERSION, len(r['sp2_changes'])))

# ── ⑥ README：标题 + 体积行（**定点替换 + 唯一命中断言**）──
n_files, dir_bytes = dir_stats(SP2)
zh = os.path.join(SP2, 'README_zh.md')
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
txt = txt.replace('**Special MVP 1.0-sp1**', '**Special MVP %s**' % VERSION)
with open(zh, 'w', encoding='utf-8', newline='\n') as f:
    f.write(txt)
ev['readme_zh'] = {'old_size_line': old_line, 'new_size_line': new_line}

en = os.path.join(SP2, 'README_en.md')
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

# ── ⑦ 闸门 ──
n_pyc = count_pyc(SP2)
black = find_blacklist(SP2)
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
prof = json.load(open(os.path.join(SP2, 'package_profile.json'),
                      encoding='utf-8'))
n_files2, dir_bytes2 = dir_stats(SP2)
ev['gates'] = {
    'n_pyc': n_pyc,
    'n_blacklist': len(black),
    'blacklist': black[:20],
    'app_files_mismatch_vs_dev': mismatch,
    'pyvenv_cfg_has_sp1_path': (SP1 in pv_txt),
    'pyvenv_cfg_has_sp2_path': (SP2 in pv_txt),
    'profile': prof.get('profile'),
    'allow_cuda': prof.get('allow_cuda'),
    'n_files': n_files2,
    'dir_bytes': dir_bytes2,
}
ok = (n_pyc == 0 and not black and not mismatch
      and SP1 not in pv_txt and SP2 in pv_txt
      and prof.get('profile') == 'specialmvp')
ev['verdict'] = 'PASS' if ok else 'FAIL'
ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
ev['elapsed_s'] = round(time.time() - t0, 1)
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('VERDICT=%s  n_files=%d  bytes=%d  synced=%d  -> %s'
      % (ev['verdict'], n_files2, dir_bytes2, len(synced), REPORT))
if not ok:
    print(json.dumps(ev['gates'], ensure_ascii=False, indent=1))
sys.exit(0 if ok else 1)
