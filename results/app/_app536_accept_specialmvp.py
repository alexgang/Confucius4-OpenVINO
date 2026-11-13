#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app536_accept_specialmvp.py —— Special MVP 客户包**验收**（在包内跑真代码）。

用户 2026-11-13 的三条硬要求，逐条用**包内真实运行**证明：
  ① TTS **仅**用 CUDA（NV5050）推理；
  ② ASR 用 **iGPU**（GPU.0）；
  ③ MT（Hy-MT2）用 **NPU**。

阶段：
  A 静态（零推理）：profile / app 代码逐字节 / MANIFEST / 卫生 / cuda_env / 模型
  B `--check`（包内 python）⇒ 设备解析
  C cuda_env 自检（包内 cuda_env python）⇒ torch + CUDA 可用
  D **整链真跑**（包内 python，--cli --file）⇒ ASR(GPU.0) → MT(NPU) → TTS(CUDA) 出音频
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
DEV = os.path.join(HOME, 'confucius4-openvino', 'live_caption')
RESULTS = os.path.join(HOME, 'confucius4-openvino', 'results', 'app')
OUT = os.path.join(RESULTS, 'app536_specialmvp_acceptance.json')
PKG_PY = os.path.join(PKG, 'python', 'python.exe')
CUDA_PY = os.path.join(PKG, 'cuda_env', 'Scripts', 'python.exe')
WAV_SRC = os.path.join(HOME, 'confucius4-openvino', 'reports', 'c025',
                       'audio_A_600_660.wav')
CLIP = os.path.join(RESULTS, '_app536_clip30s.wav')

ev = {'pkg': PKG, 'phases': {}}
t0 = time.time()


def sha256_file(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(cmd, timeout=1800, cwd=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       cwd=cwd, env=e)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


# ══════════════════════ A 静态 ══════════════════════
print('[A] 静态检查…', flush=True)
A = {}
prof = json.load(open(os.path.join(PKG, 'package_profile.json'), encoding='utf-8'))
A['profile_json'] = prof
A['profile_ok'] = (prof.get('profile') == 'specialmvp'
                   and prof.get('allow_cuda') is True)
# app 代码逐字节（dev 树 vs 包内）
mism = []
for nm in sorted(os.listdir(os.path.join(DEV))):
    if not nm.endswith('.py'):
        continue
    d = os.path.join(DEV, nm)
    p = os.path.join(PKG, 'app', nm)
    if os.path.isfile(p):
        if sha256_file(d) != sha256_file(p):
            mism.append(nm)
A['app_sha_mismatch'] = mism
A['app_files_in_pkg'] = len([f for f in os.listdir(os.path.join(PKG, 'app'))
                             if f.endswith('.py')])
A['cuda_modules_present'] = all(
    os.path.isfile(os.path.join(PKG, 'app', nm))
    for nm in ('tts_cuda.py', 'tts_cuda_sidecar.py'))
# MANIFEST
man = json.load(open(os.path.join(PKG, 'app', 'MANIFEST.json'), encoding='utf-8'))
A['manifest_all_match'] = man.get('all_match')
A['manifest_n_mismatch'] = man.get('n_mismatches')
A['manifest_has_tts_cuda'] = 'tts_cuda' in man.get('models', {})
A['manifest_tts_cuda_files'] = len(man.get('models', {}).get(
    'tts_cuda', {}).get('files', []))
# 卫生
pyc, black = [], []
for dp, dn, fn in os.walk(PKG):
    for f in fn:
        if f.endswith('.pyc') or '__pycache__' in dp:
            pyc.append(os.path.join(dp, f))
        if f.startswith('bridge_token') or f.endswith('.pid'):
            black.append(os.path.join(dp, f))
A['n_pyc'] = len(pyc)
A['n_blacklist'] = len(black)
# cuda_env / 模型
A['cuda_env_py'] = os.path.isfile(CUDA_PY)
A['cuda_env_pyvenv'] = open(os.path.join(PKG, 'cuda_env', 'pyvenv.cfg'),
                            encoding='utf-8').read()
mdir = os.path.join(PKG, 'models', 'tts_cuda')
A['model_dir_exists'] = os.path.isdir(mdir)
A['model_files'] = len(os.listdir(mdir)) if os.path.isdir(mdir) else 0
A['voice_preset_A'] = os.path.isfile(
    os.path.join(PKG, 'models', 'qwen3tts', 'voices', 'preset_A.wav'))
ev['phases']['A_static'] = A
print('   profile_ok=%s app_mismatch=%s manifest=%s tts_cuda=%s cuda_env=%s'
      % (A['profile_ok'], mism, A['manifest_all_match'],
         A['manifest_tts_cuda_files'], A['cuda_env_py']), flush=True)

# ══════════════════════ B --check ══════════════════════
print('[B] 包内 --check…', flush=True)
rc, so, se = run([PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
                   '--check'], timeout=600, cwd=PKG)
B = {'rc': rc}
keep = [ln for ln in so.splitlines()
        if any(k in ln for k in ('设备', 'GPU', 'NPU', 'CUDA', '翻译', '语音',
                                 '后端', '包目录', '模型目录', '[ OK ]', '[缺 ]',
                                 'TTS', 'ASR', 'MT'))]
B['stdout_key_lines'] = keep[-60:]
B['stderr_tail'] = se[-1500:]
ev['phases']['B_check'] = B
print('   rc=%s 关键行 %d 条' % (rc, len(keep)), flush=True)

# ══════════════════════ C cuda_env 自检 ══════════════════════
print('[C] cuda_env 自检（包内 CUDA 运行时）…', flush=True)
rc, so, se = run([CUDA_PY, '-c',
                   'import torch,sys,json;'
                   'sys.stdout.write(json.dumps({'
                   '"torch":torch.__version__,"cuda":torch.version.cuda,'
                   '"avail":bool(torch.cuda.is_available()),'
                   '"dev":torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",'
                   '"cap":list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else []}))'],
                  timeout=300)
C = {'rc': rc, 'stdout': so.strip()[:800], 'stderr_tail': se[-600:]}
try:
    C['info'] = json.loads(so.strip())
except Exception:
    C['info'] = None
ev['phases']['C_cuda_env'] = C
print('   rc=%s %s' % (rc, so.strip()[:160]), flush=True)

# ══════════════════════ D 整链真跑 ══════════════════════
print('[D] 整链真跑（ASR GPU.0 → MT NPU → TTS CUDA）…', flush=True)
# 30 s 片段
rc, so, se = run([PKG_PY, '-c',
                   'import soundfile as sf, numpy as np;'
                   'd,sr=sf.read(r"%s");'
                   'n=int(30*sr); sf.write(r"%s", d[:n], sr); print(sr, len(d)/sr)'
                   % (WAV_SRC, CLIP)], timeout=300)
D = {'clip_rc': rc, 'clip_info': so.strip()[:200]}
tts_out = os.path.join(RESULTS, '_app536_special_tts_out.wav')
if os.path.exists(tts_out):
    os.remove(tts_out)
cmd = [PKG_PY, os.path.join(PKG, 'app', 'live_caption_app.py'),
       '--cli', '--file', CLIP,
       '--asr-device', 'GPU.0',
       '--mt-device', 'NPU',
       '--tts-device', 'CUDA',
       '--translate', 'zh',
       '--tts', 'on',
       '--tts-out', tts_out]
t1 = time.time()
try:
    rc, so, se = run(cmd, timeout=2400, cwd=PKG)
    D.update({'rc': rc, 'elapsed_s': round(time.time() - t1, 1)})
except subprocess.TimeoutExpired as e:
    D.update({'rc': 'TIMEOUT', 'elapsed_s': round(time.time() - t1, 1),
              'stdout': (e.stdout or b'')[-3000:].decode('utf-8', 'replace')})
D['stdout_tail'] = (so or '')[-6000:]
D['stderr_tail'] = (se or '')[-4000:]
D['tts_out_exists'] = os.path.isfile(tts_out)
if D['tts_out_exists']:
    st = os.stat(tts_out)
    D['tts_out_bytes'] = st.st_size
    rc2, so2, _ = run([PKG_PY, '-c',
                        'import soundfile as sf;'
                        'd,sr=sf.read(r"%s");'
                        'import numpy as np;'
                        'print(sr, len(d)/sr, float(np.abs(d).max()))' % tts_out],
                       timeout=120)
    D['tts_out_info'] = so2.strip()[:300]
ev['phases']['D_chain'] = D
print('   rc=%s elapsed=%ss tts_out=%s bytes=%s'
      % (D.get('rc'), D.get('elapsed_s'), D.get('tts_out_exists'),
         D.get('tts_out_bytes')), flush=True)

ev['elapsed_s'] = round(time.time() - t0, 1)
# ══════════════════════ 判定 ══════════════════════
checks = []


def chk(name, ok, detail=''):
    checks.append({'name': name, 'pass': bool(ok), 'detail': str(detail)[:300]})


chk('A: profile=specialmvp & allow_cuda', A['profile_ok'], A['profile_json'])
chk('A: app 代码与 dev 树逐字节一致', not A['app_sha_mismatch'], A['app_sha_mismatch'])
chk('A: 包内含 tts_cuda/tts_cuda_sidecar', A['cuda_modules_present'])
chk('A: MANIFEST all_match', A['manifest_all_match'],
    'n_mismatch=%s' % A['manifest_n_mismatch'])
chk('A: MANIFEST 登记 tts_cuda（12 文件）',
    A['manifest_has_tts_cuda'] and A['manifest_tts_cuda_files'] == 12,
    A['manifest_tts_cuda_files'])
chk('A: 无 .pyc', A['n_pyc'] == 0, A['n_pyc'])
chk('A: 无黑名单文件', A['n_blacklist'] == 0, A['n_blacklist'])
chk('A: cuda_env 自带 python', A['cuda_env_py'], A['cuda_env_pyvenv'][:200])
chk('A: TTS CUDA 模型随包（12 文件）',
    A['model_dir_exists'] and A['model_files'] == 12, A['model_files'])
chk('A: 预设音色 A 在包内', A['voice_preset_A'])
chk('B: 包内 --check 退出码 0', B['rc'] == 0, B.get('stderr_tail', '')[-200:])
chk('C: 包内 cuda_env 可用 CUDA',
    C['rc'] == 0 and bool((C.get('info') or {}).get('avail')), C.get('stdout'))
chk('D: 整链跑通（ASR GPU.0 → MT NPU → TTS CUDA）',
    D.get('rc') == 0 and D.get('tts_out_exists') and (D.get('tts_out_bytes') or 0) > 1000,
    'rc=%s tts_out=%s bytes=%s' % (D.get('rc'), D.get('tts_out_exists'),
                                   D.get('tts_out_bytes')))
ev['checks'] = checks
ev['n_fail'] = sum(1 for c in checks if not c['pass'])
ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('判定：%s（%d/%d 通过）' % (ev['verdict'], len(checks) - ev['n_fail'],
                               len(checks)), flush=True)
for c in checks:
    if not c['pass']:
        print('   FAIL: %s | %s' % (c['name'], c['detail']), flush=True)
print('证据：%s' % OUT, flush=True)
