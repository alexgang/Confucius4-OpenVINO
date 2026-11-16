#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app587_build_specialmvp_sp4.py —— 构建 **Special MVP sp4**（APP-113 的改码版）。

🔴 **reviewer 原文（APP-113 §4）**：
  「sp3 冻结，改动**出 sp4**（基于 sp3 复制）。三种形态共用代码要核 MiniMVP/完整版
    默认值是否随之生效。」
  「**zip 等验收通过后再打**，现在不打 sp4 zip。」

⇒ 本脚本**从 sp3 复制**（**sp3 目录一个字都不动**），
  只把 APP-113 改动面（§1 排队不丢句／§2 并行加载／§3 非中文语速上限 2.0×）
  涉及的 **5 个 .py** 定点同步进包。

🔴 **纪律**：
  · **不覆盖、不删除** sp1 / sp2 / sp3 的目录与 zip（APP-055）；
  · **仓库 ⇄ 客户包 = 两份独立副本** ⇒ 代码**只做定点同步**
    （逐文件比对 + 唯一命中断言），**绝不整目录覆盖**；
  · 本机**安全删除 shim** 把删除转回收站且会失败 ⇒ **构建脚本一律不删**：
    拷贝时排除（`robocopy /XF *.pyc /XD __pycache__`）⇒ `.pyc` 天然 0；
  · 🔴 **本轮不生成 zip**（用户级纪律：**用户不通知 ⇒ 不主动打包**）。
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
SP3_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp3'
SP4_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp4'
SP3 = os.path.join(HOME, SP3_NAME)
SP4 = os.path.join(HOME, SP4_NAME)
VERSION = '1.0-sp4'
REPORT = os.path.join(RESULTS, 'app587_specialmvp_sp4_build.json')

#: 🔴 **本轮随 sp4 同步进包的文件**（APP-113 的改动面）
#:   `live_caption_app.py` ⇒ §1 就绪前排队（`TtsReadyQueue`）＋ §2 并行加载
#:   `time_stretch.py`     ⇒ §3 `SPEED_MAX` 1.30 → 2.00（非中文上限）
#:   `tts_worker.py`       ⇒ §3 兜底上限 1.30 → 2.00
#:   `tts_service.py`      ⇒ §3 注释同步（行为经 time_stretch 统一）
#:   `device_config.py`    ⇒ §3 注释/口径同步（上限取模块常量，不新增键）
SYNC_FILES = ['live_caption_app.py', 'time_stretch.py', 'tts_worker.py',
              'tts_service.py', 'device_config.py']

BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']
NUM_WIDTH = 18

ev = {'pkg': SP4, 'from_pkg': SP3, 'version': VERSION,
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


# ── ① fail-closed：sp4 目录必须不存在（不覆盖旧版本）──
RESUME = os.path.isdir(SP4)
if not os.path.isdir(SP3):
    raise RuntimeError('源包 sp3 不存在：%s' % SP3)
if RESUME:
    n_sp3, b_sp3 = dir_stats(SP3)
    n_sp4, b_sp4 = dir_stats(SP4)
    if n_sp4 != n_sp3:
        raise RuntimeError('续跑前置检查失败：sp4 文件数 %d ≠ sp3 %d（拷贝不完整）'
                           % (n_sp4, n_sp3))
    ev['actions'].append('RESUME: sp4 已存在（文件数 %d = sp3）⇒ 跳过拷贝，从断点继续'
                          % n_sp4)
    ev['resume'] = {'n_files_sp3': n_sp3, 'n_files_sp4': n_sp4}
else:
    ev['actions'].append('precondition: sp4 目录不存在 + sp3 存在 ✔')

# ── ② 拷贝 sp3 → sp4（**不删任何东西**；排除 .pyc / __pycache__）──
if not RESUME:
    cmd = ['robocopy', SP3, SP4, '/E', '/XF', '*.pyc', '/XD', '__pycache__',
           '/R:1', '/W:1', '/MT:16', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    rc = p.returncode
    if rc >= 8:
        raise RuntimeError('robocopy 失败 rc=%d\n%s\n%s' % (rc, p.stdout, p.stderr))
    ev['actions'].append('robocopy rc=%d（1 = 有复制成功）' % rc)
n1, b1 = dir_stats(SP4)
ev['after_copy'] = {'n_files': n1, 'bytes': b1,
                    'elapsed_s': round(time.time() - t0, 1)}

# ── ③ cuda_env/pyvenv.cfg：**重定位**到 sp4 ──
pv = os.path.join(SP4, 'cuda_env', 'pyvenv.cfg')
raw = open(pv, encoding='utf-8').read()
if raw.count(SP4) == 4 and raw.count(SP3) == 0:
    ev['actions'].append('cuda_env/pyvenv.cfg：已是 sp4 路径（续跑，跳过重定位）')
elif raw.count(SP3) == 4:
    with open(pv, 'w', encoding='utf-8', newline='\n') as f:
        f.write(raw.replace(SP3, SP4))
    ev['actions'].append('cuda_env/pyvenv.cfg：sp3 路径 → sp4（4 处）')
else:
    raise RuntimeError('cuda_env/pyvenv.cfg 里 sp3 路径 %d 次 / sp4 路径 %d 次'
                       '（预期 4 / 0 或 0 / 4）' % (raw.count(SP3), raw.count(SP4)))
ev['pyvenv_cfg_after'] = open(pv, encoding='utf-8').read()

# ── ③b app/MANIFEST.json：`pkg_models_root` → **sp4 自己的** models 目录 ──
mpath = os.path.join(SP4, 'app', 'MANIFEST.json')
mtxt = open(mpath, encoding='utf-8', newline='').read()
man = json.loads(mtxt)
cur_root = man.get('pkg_models_root')
want_root = os.path.join(SP4, 'models')
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
        raise RuntimeError('MANIFEST 改动范围超出预期（实际多了 %s）'
                           % sorted(diff_keys - {'pkg_models_root'}))
    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(raw2)
    if open(mpath, encoding='utf-8', newline='').read() != raw2:
        raise RuntimeError('MANIFEST 写盘后逐字节不一致')
    ev['actions'].append('app/MANIFEST.json: pkg_models_root sp3 → sp4')
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'raw_hits': n_hit}
else:
    ev['manifest_repoint'] = {'from': cur_root, 'to': want_root,
                              'note': '已是 sp4 自己的 models 目录'}

# ── ④ app 代码定点同步：**只同步 SYNC_FILES 这 5 个** ──
appdir = os.path.join(SP4, 'app')
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
        raise RuntimeError('包内 %s 与 dev 不同，但它不在本轮 SYNC_FILES=%s 内'
                           ' ⇒ 中止（避免夹带改动）' % (f, SYNC_FILES))
    shutil.copy2(src, dst)
    synced.append({'file': f, 'sha256': sha256_file(dst),
                   'bytes': os.path.getsize(dst)})
ev['app_sync'] = {'sync_files_declared': SYNC_FILES, 'synced': synced,
                  'n_same': len(same), 'n_no_dev_counterpart': no_dev}
synced_names = [x['file'] for x in synced]
missing = [f for f in SYNC_FILES
           if f not in synced_names and f not in same]
if missing:
    raise RuntimeError('本轮应当同步的文件既没被同步、也没与 dev 一致：%s' % missing)
ev['actions'].append('app 代码同步：%d 个文件被改写（%s）；其余与 dev 逐字相同 %d 个'
                     % (len(synced), ', '.join(synced_names) or '(无)', len(same)))

# ── ⑤ release.json：版本 + 纠偏编号 + sp4 变更说明 ──
rel = os.path.join(SP4, 'release.json')
r = json.load(open(rel, encoding='utf-8'))
r['version'] = VERSION
for c in ('APP-113',):
    if c not in r.get('corrections', []):
        r['corrections'].append(c)
r['sp4_changes'] = [
    "APP-113 §1（用户 2026-11-16 决定，方案 B）：**TTS 就绪前不再跳句** ⇒ "
    "定稿译文**进队列等待**，就绪后按 FIFO 原样补发（`TtsReadyQueue`）"
    "⇒ **不丢句**（取代 APP-069④/070② A 的「未就绪即丢弃」）。"
    "⚠️ 队列有**上限保护**：120 s 仍未就绪 ⇒ 按最旧优先丢弃并计数 "
    "`n_drop_not_ready_overflow`（GUI/日志明示）；正常冷启动（≤60 s）一句不丢。",
    "APP-113 §2（用户 2026-11-16 决定）：**ASR 与 TTS 并行加载** ⇒ "
    "TTS 档位为 **CUDA**（本包出厂默认）时，**启动时同时拉起 CUDA 边车**"
    "（独立进程；不与 ASR 抢 GPU.0），MT 照旧。"
    "⚠️ **只并行 CUDA 边车这一路**：TTS 档位是 GPU.0/NPU（非 CUDA）时"
    "**保持原来的串行顺序**（沿用「auto=False 防 GPU 编译死锁」）。",
    "APP-113 §3（用户 2026-11-16 决定）：**非中文目标语言的语速上限 "
    "1.30× → 2.0×** ⇒ 与中文目标一致（`time_stretch.SPEED_MAX = 2.00`）。"
    "⚠️ **只放开上限**：滞后→倍率的增益曲线不变（死区 3.0 s / 每秒 0.025 / "
    "滞回 2.0 s / 步长 ±0.1 全部照旧）；非中文目标的下限仍是 1.00。",
    "APP-113 §4：sp3 **冻结**（本包基于 sp3 复制，**sp3 目录一字未动**）；"
    "sp4 的 zip **等验收通过后再打**（本轮只出包目录）。",
]
with open(rel, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(r, f, ensure_ascii=False, indent=1)
ev['actions'].append('release.json：version=%s；corrections += APP-113；'
                     '新增 sp4_changes（%d 条）' % (VERSION, len(r['sp4_changes'])))

# ── ⑥ README：标题 + 体积行（**定点替换 + 唯一命中断言**）──
n_files, dir_bytes = dir_stats(SP4)
zh = os.path.join(SP4, 'README_zh.md')
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
txt = txt.replace('**Special MVP 1.0-sp3**', '**Special MVP %s**' % VERSION)
with open(zh, 'w', encoding='utf-8', newline='\n') as f:
    f.write(txt)
ev['readme_zh'] = {'old_size_line': old_line, 'new_size_line': new_line}

en = os.path.join(SP4, 'README_en.md')
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

# ── ⑦ 闸门（**只断言，不 purge**）──
n_pyc = count_pyc(SP4)
black = find_blacklist(SP4)
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
prof = json.load(open(os.path.join(SP4, 'package_profile.json'), encoding='utf-8'))
n_files2, dir_bytes2 = dir_stats(SP4)
ev['gates'] = {
    'n_pyc': n_pyc,
    'n_blacklist': len(black),
    'blacklist': black[:20],
    'app_files_mismatch_vs_dev': mismatch,
    'pyvenv_cfg_has_sp3_path': (SP3 in pv_txt),
    'pyvenv_cfg_has_sp4_path': (SP4 in pv_txt),
    'profile': prof.get('profile'),
    'allow_cuda': prof.get('allow_cuda'),
    'n_files': n_files2,
    'dir_bytes': dir_bytes2,
}
ok = (n_pyc == 0 and not black and not mismatch
      and SP3 not in pv_txt and SP4 in pv_txt
      and prof.get('profile') == 'specialmvp')

# ── ⑦b **APP-113 三项改动**在包内确实生效（**行为级**读包内代码）──
app_txt = open(os.path.join(appdir, 'live_caption_app.py'), encoding='utf-8').read()
ts_txt = open(os.path.join(appdir, 'time_stretch.py'), encoding='utf-8').read()
tw_txt = open(os.path.join(appdir, 'tts_worker.py'), encoding='utf-8').read()
ev['param_check'] = {
    # §1 排队不丢句
    'app_has_TtsReadyQueue': 'class TtsReadyQueue' in app_txt,
    'app_has_pending_queue': 'self._tts_pending_q = TtsReadyQueue' in app_txt,
    'app_has_overflow_counter': 'n_drop_not_ready_overflow' in app_txt,
    'app_no_longer_skips': ('本句**不排队**' not in app_txt),
    'app_cli_queues_not_skips': ('_skip_nr += 1' not in app_txt),
    # §2 并行加载
    'app_has_parallel_boot': '_boot_tts_parallel' in app_txt,
    'app_parallel_only_cuda': ("_tts_dev.upper().startswith('CUDA')" in app_txt),
    # §3 非中文上限 2.0
    'time_stretch.SPEED_MAX==2.00': 'SPEED_MAX = 2.00' in ts_txt,
    'time_stretch.ZH_SPEED_MAX==2.00': 'ZH_SPEED_MAX = 2.00' in ts_txt,
    'worker_fallback_2.00': 'return (1.0, 2.00)' in tw_txt,
    'worker_bounds_fallback_2.00': '_lo, _hi = 1.0, 2.00' in tw_txt,
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
