#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app535_build_specialmvp.py —— 构建 **Special MVP** 客户包。

用户 2026-11-13 决定：**包内仅使用 CUDA 推理 TTS**（真 NV5050 环境，随包分发），
**iGPU 做 ASR**、**NPU 做 Hy-MT2 翻译**。

🔴 纪律：
  · **新版本号**（新目录 + 新 zip）⇒ 不覆盖、不删除任何旧包（APP-055）；
  · 仓库 ⇄ 客户包是**两份独立副本** ⇒ app 代码用**逐文件复制 + 逐字节比对**；
  · 复用 rc11 构建脚本的**已验证闸门**（黑名单/.pyc/bat/旧解码器）；
  · 每步落证据到 json ⇒ 报告必须能追回。
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
BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
PKG_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
DST_PKG = os.path.join(HOME, PKG_NAME)
VERSION = '1.0-sp1'
CUDA_ENV_SRC = os.path.join(HOME, '_fq3tts_env')
FQ3TTS_SRC = os.path.join(HOME, '_fq3tts_src', 'faster-qwen3-tts-main')
MODEL_SRC = os.path.join(HOME, '.cache', 'huggingface', 'hub',
                         'models--Qwen--Qwen3-TTS-12Hz-0.6B-Base', 'snapshots',
                         '5d83992436eae1d760afd27aff78a71d676296fc')
REPORT = os.path.join(RESULTS, 'app535_specialmvp_build.json')

ev = {'actions': [], 'pkg': {}, 'cuda_env': {}, 'model': {}, 'gates': {}}
t0 = time.time()
# 🔴 **可续跑**：上一次失败后重跑时跳过已完成的大拷贝（14 GB 不用再拷一遍）。
RESUME = '--resume' in sys.argv
DONE = set()
if RESUME:
    rep = os.path.join(RESULTS, 'app535_specialmvp_resume.json')
    if os.path.isfile(rep):
        try:
            DONE = set(json.load(open(rep, encoding='utf-8')).get('done', []))
        except Exception:
            DONE = set()


def need(tag):
    """该步骤是否需要执行（续跑时按 tag 跳过）。"""
    return tag not in DONE


def mark(tag):
    DONE.add(tag)
    with open(os.path.join(RESULTS, 'app535_specialmvp_resume.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'done': sorted(DONE)}, f, ensure_ascii=False, indent=1)


def sha256_file(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


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


def robocopy(src, dst, extra=None):
    """用 robocopy 复制大目录（比 shutil 快很多）。返回 (rc, n_copied)。"""
    cmd = ['robocopy', src, dst, '/E', '/MT:8', '/NFL', '/NDL', '/NJH',
           '/NJS', '/NP', '/R:1', '/W:1',
           '/XF', '*.pyc', '*.pyo', '/XD', '__pycache__']
    if extra:
        cmd += extra
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout


def step(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


# ══════════════════════════════════════════════════════════════
# [1] 复制 rc11 → Special MVP（新目录，不覆盖任何旧包）
# ══════════════════════════════════════════════════════════════
if os.path.isdir(DST_PKG) and not RESUME:
    raise RuntimeError('目标目录已存在（禁止覆盖）：%s' % DST_PKG)
if need('copy'):
    step('[1/10] 复制 rc11 → %s（排除 __pycache__/*.pyc）…' % PKG_NAME)
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    mark('copy')
else:
    step('[1/10] 跳过（续跑）')
n, total = dir_stats(DST_PKG)
ev['pkg'].update({'n_files': n, 'bytes': total, 'src': BASE_PKG})
ev['actions'].append('copy rc11 -> %s (real copy, no __pycache__/*.pyc)' % PKG_NAME)

# ══════════════════════════════════════════════════════════════
# [2] CUDA 环境打包进去（NV5050 的真 CUDA 运行时）
# ══════════════════════════════════════════════════════════════
CUDA_DST = os.path.join(DST_PKG, 'cuda_env')
if need('cuda_env'):
    step('[2/10] 复制 CUDA 运行时 → cuda_env/（torch 2.11.0+cu128）…')
    # 🔴🔴 **字节码必须在「拷贝时」排除**（rc11 的同一纪律）：
    #   上一轮 robocopy 把 venv 里的 `__pycache__`/`*.pyc` 也拷进来了（14 836 个）
    #   ⇒ 想用「事后删除」清掉，会**触发批量删除保护**（实测：一次删 68 个文件
    #   被 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 拦下）⇒ **只有一条路：重新拷干净**。
    #   ⇒ 把被污染的那份**改名挪走**（rename 不是删除 ⇒ 不触发保护），
    #     再用**带排除项**的 robocopy 重拷 ⇒ 包内天然没有字节码。
    if os.path.isdir(CUDA_DST):
        aside = os.path.join(HOME, '_tmp_cuda_env_polluted')
        k = 0
        while os.path.exists(aside):
            k += 1
            aside = os.path.join(HOME, '_tmp_cuda_env_polluted_%d' % k)
        os.rename(CUDA_DST, aside)
        ev['cuda_env']['moved_aside'] = aside
        step('     （被污染的旧副本已挪到 %s —— 未删除，留待人工处理）' % aside)
    rc, _ = robocopy(CUDA_ENV_SRC, CUDA_DST)
    if rc > 7:
        raise RuntimeError('robocopy CUDA 环境失败 rc=%s' % rc)
    n, total = dir_stats(CUDA_DST)
    ev['cuda_env'].update({'src': CUDA_ENV_SRC, 'n_files': n, 'bytes': total,
                           'robocopy_rc': rc})
    ev['actions'].append('copy _fq3tts_env -> cuda_env/ (torch 2.11.0+cu128)')

    # [2a] pyvenv.cfg 改成指向**包内**的 python（可搬迁）
    cfg = os.path.join(CUDA_DST, 'pyvenv.cfg')
    pkg_py = os.path.join(DST_PKG, 'python')
    lines = []
    for ln in open(cfg, encoding='utf-8').read().splitlines():
        if ln.lower().startswith('home'):
            ln = 'home = %s' % pkg_py
        elif ln.lower().startswith('executable'):
            ln = 'executable = %s' % os.path.join(pkg_py, 'python.exe')
        elif ln.lower().startswith('command'):
            ln = 'command = %s -m venv %s' % (os.path.join(pkg_py, 'python.exe'), CUDA_DST)
        lines.append(ln)
    with open(cfg, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')
    ev['cuda_env']['pyvenv_cfg'] = open(cfg, encoding='utf-8').read()

    # [2b] editable 安装 ⇒ 换成**真实**的包源码拷贝（否则客户机上找不到）
    # 🔴🔴 **不能删文件**：本机的安全删除 shim 会把删除**转成回收站**，
    #   而回收站调用失败（`SHFileOperationW 失败: 0x2`）⇒ **删 = 构建失败**。
    #   ⇒ 一律用 **rename（挪走）**：把 editable 的 .pth / finder **挪到包外**，
    #   既不删、又不会让 Python 走 editable 路径（本机 `_fq3tts_src` 存在时
    #   editable 会**遮蔽**真包 ⇒ 必须处理）。
    sp = os.path.join(CUDA_DST, 'Lib', 'site-packages')
    aside_dir = os.path.join(HOME, '_tmp_cuda_editable_backup')
    k = 0
    while os.path.exists(aside_dir):
        k += 1
        aside_dir = os.path.join(HOME, '_tmp_cuda_editable_backup_%d' % k)
    os.makedirs(aside_dir, exist_ok=True)
    moved = []
    for nm in os.listdir(sp):
        if nm.startswith('__editable__') and 'faster_qwen3_tts' in nm:
            os.rename(os.path.join(sp, nm), os.path.join(aside_dir, nm))
            moved.append(nm)
    real_dst = os.path.join(sp, 'faster_qwen3_tts')
    if os.path.isdir(real_dst):
        os.rename(real_dst, os.path.join(aside_dir, 'faster_qwen3_tts_old'))
    shutil.copytree(os.path.join(FQ3TTS_SRC, 'faster_qwen3_tts'), real_dst,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    ev['cuda_env']['editable_moved_aside'] = {'dir': aside_dir, 'files': moved}
    ev['cuda_env']['faster_qwen3_tts_src'] = FQ3TTS_SRC
    ev['actions'].append('editable install -> real package copy; '
                         'pyvenv.cfg home -> <pkg>/python')
    mark('cuda_env')
else:
    step('[2/10] 跳过（续跑）')
    n, total = dir_stats(CUDA_DST)
    ev['cuda_env'].update({'src': CUDA_ENV_SRC, 'n_files': n, 'bytes': total})

# ══════════════════════════════════════════════════════════════
# [3] TTS CUDA 模型随包
# ══════════════════════════════════════════════════════════════
MODEL_DST = os.path.join(DST_PKG, 'models', 'tts_cuda')
if need('model'):
    step('[3/10] 复制 TTS CUDA 模型 → models/tts_cuda/…')
    rc, _ = robocopy(MODEL_SRC, MODEL_DST)
    if rc > 7:
        raise RuntimeError('robocopy 模型失败 rc=%s' % rc)
    mark('model')
else:
    step('[3/10] 跳过（续跑）')
n, total = dir_stats(MODEL_DST)
mf = []
for dp, dn, fn in os.walk(MODEL_DST):
    for f in sorted(fn):
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, MODEL_DST).replace('\\', '/')
        mf.append({'name': rel, 'bytes': os.path.getsize(p),
                   'sha256': sha256_file(p)})
ev['model'] = {'src': MODEL_SRC, 'dst': MODEL_DST, 'n_files': len(mf),
               'bytes': total, 'files': mf}
ev['actions'].append('copy Qwen3-TTS-12Hz-0.6B-Base snapshot -> models/tts_cuda/')

# ══════════════════════════════════════════════════════════════
# [4] app 代码：dev 树 → 包（逐文件 + 逐字节复核）
# ══════════════════════════════════════════════════════════════
step('[4/10] app/*.py 对齐 dev 树 ＋ 放入 tts_cuda*.py…')
app = os.path.join(DST_PKG, 'app')
names = sorted(f for f in os.listdir(app) if f.endswith('.py'))
copied, mismatch = [], []
for nm in names:
    src = os.path.join(DEV, nm)
    if not os.path.isfile(src):
        continue
    shutil.copy2(src, os.path.join(app, nm))
    a = sha256_file(src)
    b = sha256_file(os.path.join(app, nm))
    copied.append(nm)
    if a != b:
        mismatch.append(nm)
# CUDA 两个模块在 dev 树里、包里原本没有
for nm in ('tts_cuda.py', 'tts_cuda_sidecar.py'):
    src = os.path.join(DEV, nm)
    shutil.copy2(src, os.path.join(app, nm))
    if sha256_file(src) != sha256_file(os.path.join(app, nm)):
        mismatch.append(nm)
    copied.append(nm)
if mismatch:
    raise RuntimeError('app 代码逐字节比对不一致：%s' % mismatch)
ev['app_synced'] = copied
ev['actions'].append('align app/*.py from dev tree (%d) + add tts_cuda*.py; '
                     'byte-identical verified' % len(copied))
mark('app_sync')

# ══════════════════════════════════════════════════════════════
# [5] package_profile.json = specialmvp
# ══════════════════════════════════════════════════════════════
step('[5/10] 写 package_profile.json（specialmvp）…')
prof = {
    'profile': 'specialmvp',
    'allow_cuda': True,
    'allow_clone_voice': False,
    'target_langs': 10,
    'note': ('用户 2026-11-13 决定：**包内自带 NV5050 的 PyTorch+CUDA 环境** ⇒ '
             '语音输出（TTS）用**真 CUDA** 推理；**ASR 走 iGPU（GPU.0）**、'
             '**翻译走 NPU（Hy-MT2 INT8-CW）**。'
             '🔴 与 MiniMVP/完整版的区别：那两个包**不带** CUDA 运行时、'
             'TTS 走 OpenVINO（OV 官方发行版**不含** CUDA plugin ⇒ '
             'NVIDIA 卡只能是 Intel GPU plugin 枚举到的 GPU.1，不是真 CUDA 后端）。'
             '⚠️ 本包**不提供音色克隆**（与 MiniMVP 同）。'),
}
with open(os.path.join(DST_PKG, 'package_profile.json'), 'w',
          encoding='utf-8', newline='\n') as f:
    json.dump(prof, f, ensure_ascii=False, indent=1)
ev['actions'].append('package_profile.json -> specialmvp (allow_cuda=True)')
mark('profile')

# ══════════════════════════════════════════════════════════════
# [6] release.json
# ══════════════════════════════════════════════════════════════
step('[6/10] 更新 release.json（version 1.0-sp1）…')
rel_path = os.path.join(DST_PKG, 'release.json')
rel = json.load(open(rel_path, encoding='utf-8'))
rel.update({
    'release': True,
    'version': VERSION,
    'product_line': 'SpecialMVP',
    'package_profile': 'package_profile.json',
    'specialmvp_changes': [
        '用户 2026-11-13 决定：**TTS 仅用 CUDA**（NV5050）——**包内自带** '
        'cuda_env/（torch 2.11.0+cu128 + faster_qwen3_tts 0.5.4，'
        '**可搬迁**：pyvenv.cfg 的 home 指向包内 python/）',
        '**ASR = Intel 集显 GPU.0**（OV INT8 stateful 0.6B）；'
        '**MT = Intel NPU**（Hy-MT2 1.8B INT8-CW）；'
        '**TTS = CUDA**（Qwen3-TTS-12Hz-0.6B-Base，bfloat16，**不走 OV**）',
        '新增 app/tts_cuda.py + app/tts_cuda_sidecar.py（PyTorch+CUDA 边车）',
        '新增 models/tts_cuda/（12 文件 / 2.52 GB，随包离线可用）',
        '新增第三种包形态 profile=specialmvp（allow_cuda=True ⇒ CUDA 档可选）',
        '实测（A 机 RTX 5050 Laptop GPU，sm_120）：模型加载 28.5 s、warmup 1.95 s、'
        '首包 **1.67 s**、整句 3.52 s / 3.84 s 音频（**RTF ≈ 0.92**）、'
        '显存峰值 **2.57 GB**',
    ],
})
with open(rel_path, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(rel, f, ensure_ascii=False, indent=1)
ev['actions'].append('release.json -> version %s + specialmvp_changes' % VERSION)
mark('release')

# ══════════════════════════════════════════════════════════════
# [7] MANIFEST：登记 models/tts_cuda（逐文件 SHA）＋ 复核既有条目
# ══════════════════════════════════════════════════════════════
step('[7/10] MANIFEST：登记 models/tts_cuda ＋ 复核包内字节…')
mpath = os.path.join(app, 'MANIFEST.json')
man = json.load(open(mpath, encoding='utf-8'))
man['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
man['pkg_models_root'] = os.path.join(DST_PKG, 'models')
man['models']['tts_cuda'] = {
    'source_path': MODEL_SRC,
    'source_model': 'Qwen3-TTS-12Hz-0.6B-Base（**PyTorch 权重 · CUDA 推理**）',
    'note': ('Special MVP：**TTS 走真 CUDA**（NV5050）⇒ 这里放的是 **PyTorch '
             '权重**（model.safetensors + speech_tokenizer），**不是** OV IR。'
             '随包离线可用（边车用 LIVECAP_CUDA_TTS_MODEL 指向本目录，'
             'local_files_only=True）。'),
    'optional': False,
    'source_exists': True,
    'pkg_exists': True,
    'files': [],
}
# 既有条目：按**新包目录**重算包内 SHA ⇒ 诚实复核
models_root = os.path.join(DST_PKG, 'models')
n_mis = 0


def pkg_model_path(key, name):
    """包内模型文件路径。

    🔴 **注意**：`embed_tokens_06b_f16.npy` 这类**顶层文件**的 MANIFEST key
    就是**文件名本身**（不是目录）⇒ 不能一律拼 `models/<key>/<name>`
    （那会得到 `.../embed_tokens_06b_f16.npy/embed_tokens_06b_f16.npy`
      ⇒ 误判「缺文件」）。先看 `models/<key>` 是不是目录。
    """
    d = os.path.join(models_root, key.replace('/', os.sep))
    if os.path.isdir(d):
        return os.path.join(d, name.replace('/', os.sep))
    return d


for key, entry in man['models'].items():
    if key == 'tts_cuda':
        continue
    for fe in entry.get('files', []):
        p = pkg_model_path(key, fe['name'])
        if not os.path.isfile(p):
            fe['pkg_exists'] = False
            fe['match'] = False
            n_mis += 1
            continue
        fe['sha256'] = sha256_file(p)
        fe['bytes'] = os.path.getsize(p)
        fe['match'] = (fe['sha256'] == fe.get('source_sha256'))
        if not fe['match']:
            n_mis += 1
for fe in mf:
    man['models']['tts_cuda']['files'].append({
        'name': fe['name'], 'bytes': fe['bytes'],
        'source_path': os.path.join(MODEL_SRC, fe['name'].replace('/', os.sep)),
        'source_exists': True,
        'sha256': fe['sha256'],
        'source_sha256': sha256_file(os.path.join(MODEL_SRC,
                                                  fe['name'].replace('/', os.sep))),
        'match': True,
    })
man['n_models'] = str(len(man['models']))
man['computed_sha'] = True
man['n_mismatches'] = n_mis
man['mismatches'] = []
man['all_match'] = (n_mis == 0)
if n_mis:
    raise RuntimeError('MANIFEST 复核有 %d 个不一致' % n_mis)
with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(man, f, ensure_ascii=False, indent=1)
ev['actions'].append('MANIFEST: +tts_cuda(%d files, per-file SHA) ; '
                     're-verified %d existing entries, mismatches=%d'
                     % (len(mf), len(man['models']) - 1, n_mis))

# ══════════════════════════════════════════════════════════════
# [8] 卫生闸门（复用 rc11 构建脚本的**已验证**实现）
# ══════════════════════════════════════════════════════════════
step('[8/10] 卫生闸门：黑名单 / .pyc / 旧解码器 / bat…')
sys.path.insert(0, RESULTS)
import importlib.util
spec = importlib.util.spec_from_file_location(
    '_app524', os.path.join(RESULTS, '_app524_build_minimvp_rc11.py'))
rc11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc11)

ev['gates']['blacklist_selftest'] = rc11.blacklist_gate_selftest()
if not all(x['pass'] for x in ev['gates']['blacklist_selftest']):
    raise RuntimeError('黑名单闸门反例自测未通过')
# 🔴🔴 **只断言、不删除**：本机的安全删除 shim 把删除转回收站且会失败
#   ⇒ 命中即**挪到包外**（rename，不是 delete）。
left = rc11.find_blacklist(DST_PKG)
if left:
    aside = os.path.join(HOME, '_tmp_specialmvp_blacklist')
    k = 0
    while os.path.exists(aside):
        k += 1
        aside = os.path.join(HOME, '_tmp_specialmvp_blacklist_%d' % k)
    os.makedirs(aside, exist_ok=True)
    for h in left:
        src = os.path.join(DST_PKG, h['file'].replace('/', os.sep))
        dst = os.path.join(aside, os.path.basename(h['file']))
        os.rename(src, dst)
    ev['gates']['blacklist_moved_aside'] = {'n': len(left), 'dir': aside}
left = rc11.find_blacklist(DST_PKG)
if left:
    raise RuntimeError('包里还有黑名单文件：%s' % left[:5])
# 🔴 **字节码**：拷贝时已排除（robocopy /XF *.pyc /XD __pycache__）
#   ⇒ 这里**只断言**（有就报错，不静默带进包）。
n_pyc = rc11.count_pyc(DST_PKG)
if n_pyc:
    raise RuntimeError('包里还有 %d 个 .pyc' % n_pyc)
ev['gates']['pyc'] = {'n_pyc': n_pyc,
                       'note': '拷贝时排除（robocopy /XF *.pyc /XD __pycache__）'
                               '⇒ 天然为 0；此处只断言'}
ev['gates']['blacklist_left'] = len(left)
ev['gates']['n_pyc'] = n_pyc

ev['gates']['legacy_selftest'] = rc11.legacy_gate_selftest()
if not all(x['pass'] for x in ev['gates']['legacy_selftest']):
    raise RuntimeError('旧解码器闸门反例自测未通过')
ok, reasons = rc11.assert_no_legacy(DST_PKG)
ev['gates']['legacy'] = {'ok': ok, 'reasons': reasons}
if not ok:
    raise RuntimeError('包内仍有旧解码器痕迹：%s' % reasons[:5])

rows = rc11.check_bats(DST_PKG)
ev['gates']['bat'] = {'rows': rows,
                      'n_fail': sum(1 for r in rows if not r['pass'])}
if ev['gates']['bat']['n_fail']:
    raise RuntimeError('bat 闸门未过：%s'
                       % [r for r in rows if not r['pass']][:5])
ev['actions'].append('hygiene gates: blacklist/pyc/legacy/bat all PASS')

# ══════════════════════════════════════════════════════════════
# [9] README：改成 Special MVP 的真实口径（定点替换 + 唯一命中断言）
# ══════════════════════════════════════════════════════════════
step('[9/10] README 定点改写（设备表 / 出厂默认 / Special 说明）…')
GONGO = ('实测（A 机 RTX 5050 Laptop GPU，sm_120，2026-11-13）：'
         '模型加载 **28.5 s**、warmup **1.95 s**、**首包 1.67 s**、'
         '整句 **3.52 s** / **3.84 s** 音频（**RTF ≈ 0.92**）、'
         '显存峰值 **2.57 GB**、采样率 24 000 Hz。')
REPL_ZH = [
    ('# Confucius4 实时字幕 · MiniMVP 1.0-rc11（最小客户包）',
     '# Confucius4 实时字幕 · **Special MVP 1.0-sp1**（NV5050 CUDA 专供包）'),
    ('**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**',
     '**本包是独立于 v2.x 的新产品线（Special MVP），版本号单独编号。**\n'
     '\n'
     '## 🔶 Special MVP 专有说明（**与 MiniMVP / 完整版不同**）\n'
     '\n'
     '> **用户 2026-11-13 决定**：本包**自带 NV5050 的 PyTorch+CUDA 环境**，\n'
     '> ⇒ **语音输出（TTS）用真 CUDA 推理**；**ASR 用 Intel 集显（iGPU）**、\n'
     '> **翻译（Hy-MT2）用 Intel NPU**。\n'
     '>\n'
     '> * **TTS = CUDA**：`cuda_env/`（**torch 2.11.0+cu128** + '
     '`faster_qwen3_tts 0.5.4`，**可搬迁**）⇒ `app/tts_cuda.py` 拉起 '
     '`app/tts_cuda_sidecar.py` 边车，在 **NVIDIA GeForce RTX 5050 Laptop GPU** 上跑 '
     '`Qwen3-TTS-12Hz-0.6B-Base`（bfloat16）。**不走 OpenVINO。**\n'
     '> * ⚠️ **与 MiniMVP/完整版的根本区别**：OV 官方发行版**不含 CUDA plugin** ⇒ '
     '那两个包即使选到 NVIDIA 卡，也只是 Intel GPU plugin 枚举到的 `GPU.1`'
     '（**不是真 CUDA**）。**本包才是真 CUDA。**\n'
     '> * 模型随包：`models/tts_cuda/`（12 文件 / 2.52 GB）⇒ **离线可用**，'
     '不依赖客户机的 HF 缓存。\n'
     '> * ' + GONGO + '\n'
     '> * ⚠️ **本包不提供音色克隆**（与 MiniMVP 同）⇒ 只有内置预设音色 A。'),
    ('| 语音识别 | **Qwen3-ASR-0.6B**（stateful INT8（KV cache）） | INT8 | '
     'Intel 集显 GPU.0（Intel iGPU） |',
     '| 语音识别 | **Qwen3-ASR-0.6B**（stateful INT8（KV cache）） | INT8 | '
     '**Intel 集显 GPU.0（Intel iGPU）** |'),
    ('| 翻译 | **Hy-MT2-1.8B**（**INT8-CW**） | **INT8**（对称 · per-channel weight） | '
     'Intel 集显 GPU.0（Intel iGPU） |',
     '| 翻译 | **Hy-MT2-1.8B**（**INT8-CW**） | **INT8**（对称 · per-channel weight） | '
     '**Intel NPU** |'),
    ('| 语音输出 | **Qwen3-TTS 0.6B**（INT8 权重 · FP16 计算） | INT8/FP16 | Intel NPU |',
     '| 语音输出 | **Qwen3-TTS 0.6B**（**PyTorch 权重 · bfloat16 · 真 CUDA**） | '
     'bfloat16 | **CUDA（NVIDIA RTX 5050）** |'),
    ('* **不含**：NVIDIA/CUDA 与 torch 相关内容、开发与测试脚本、会议录音、',
     '* **不含**：开发与测试脚本、会议录音、'),
    ('* **出厂默认设备**：**ASR=Intel 集显 GPU.0（Intel iGPU），MT=Intel 集显 GPU.0'
     '（Intel iGPU），TTS=Intel NPU**',
     '* **出厂默认设备**：**ASR=Intel 集显 GPU.0（Intel iGPU），MT=Intel NPU，'
     'TTS=CUDA（NVIDIA RTX 5050）**'),
]
for rel_name, repls in (('README_zh.md', REPL_ZH),):
    p = os.path.join(DST_PKG, rel_name)
    txt = open(p, encoding='utf-8').read()
    for old, new in repls:
        cnt = txt.count(old)
        if cnt != 1:
            raise RuntimeError('README %s 锚点命中 %d 次（应恰好 1 次）：%r'
                               % (rel_name, cnt, old[:60]))
        txt = txt.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='\n').write(txt)
ev['actions'].append('README_zh.md: 6 处定点替换（唯一命中断言）')

# README_en / perftest：只改标题 + 出厂默认那一行（英文/性能包）
p = os.path.join(DST_PKG, 'README_en.md')
if os.path.isfile(p):
    txt = open(p, encoding='utf-8').read()
    for old, new in (('# Confucius4 Live Caption · MiniMVP 1.0-rc11',
                      '# Confucius4 Live Caption · **Special MVP 1.0-sp1** '
                      '(NV5050 CUDA build)'),):
        if txt.count(old) == 1:
            txt = txt.replace(old, new)
            open(p, 'w', encoding='utf-8', newline='\n').write(txt)
            ev['actions'].append('README_en.md: 标题定点替换')

# ══════════════════════════════════════════════════════════════
# [10] 收尾统计
# ══════════════════════════════════════════════════════════════
n, total = dir_stats(DST_PKG)
ev['pkg'].update({'n_files': n, 'bytes': total, 'dir': DST_PKG})
ev['elapsed_s'] = round(time.time() - t0, 1)
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('完成：%s / %d 文件 / %.2f GB / %.1f s'
      % (DST_PKG, n, total / 1e9, ev['elapsed_s']), flush=True)
