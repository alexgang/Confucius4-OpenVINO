#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app336 — APP-080 ⑥ / APP-081 4d 黑名单扫描：**14 项命中的逐项取证与三态定性**。

本脚本不修改、不覆盖 app332_v23_blacklist.json / app335_v23_blacklist_recheck.json，
只新增一份补充诊断。背景：
  * 首轮 app332 判 FAIL（real_hits=33），把「裸目录名」「第三方库自带 CUDA 源码」
    一并计入，口径宽于原文；
  * app335 按原始口径复算仍判 FAIL（real=14），明细为：
      real_dev_path=1  → app/v23_preset_only.py 里 BLACKLIST_PATTERNS 的正则字面量；
      active_cuda=13   → openvino/torch 与 scipy/_external/array_api_compat/torch
                         的纯 Python 兼容 shim（含 .pyc），因正则里裸 `torch/` 命中。
  * 核心 4 类（会议录音 / 克隆音色 / babelvox 示例音色 / bridge_token）两轮均 0。

🔴 纪律：不为了凑 PASS 放宽判据。本脚本做三件事：
  ① 逐项取证：包内是否真有 CUDA 运行时二进制 / torch 原生库 / App 侧 CUDA 后端；
     那 1 条 dev_path 命中的完整源码行；
  ② 反证：注入「真 CUDA 运行时」「真 App CUDA 后端」「真开发机绝对路径泄漏」
     必须全部被识破；干净反例不得误伤（防恒真）；
  ③ 三态输出：True=PASS / False=FAIL / None=UNKNOWN（口径歧义交 reviewer 裁定）。
     已识别的交付瑕疵（规则字面量含开发机用户名）如实列出，不静默抹掉。
纯 CPU 静态扫描，不占设备、不加载模型、不需要 MACHINE_LOCK。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402 —— 包目录名单一下数据源（§48 闸门）

VER = '2.3'
CLEAN = r'C:\v23_cleantest'
PKG = os.path.join(CLEAN, pkg_paths.PKG_NAME_PREFIX + VER)
FIRST = os.path.join(HERE, 'app332_v23_blacklist.json')
RECHECK = os.path.join(HERE, 'app335_v23_blacklist_recheck.json')
OUT = os.path.join(HERE, 'app336_v23_blacklist_forensics.json')

# —— 原文口径（APP-080 ⑥ / APP-081 4d）——
CORE = {
    'meeting': re.compile(r'(?i)(260902_SPE|_spoken|SPE_\d+.*\.wav$)'),
    'clone_wav': re.compile(r'(?i)(clone.*\.(wav|npz)$|tts_speakers/)'),
    'babelvox_demo': re.compile(
        r'(?i)babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$'),
    'bridge_token': re.compile(r'(?i)(^|/)bridge_token\.txt$'),
}
DEV_PATH = re.compile(r'(?i)C:[\\/]+Users[\\/]+Trekker-PTL')
# 真 CUDA 运行时 / PyTorch 原生库 / App 侧自研 CUDA 后端（精确化判据）
CUDA_NATIVE = re.compile(
    r'(?i)(^|/)(cuda|cudnn|cublas|cufft|curand|cusparse|nccl|nvidia)[^/]*'
    r'\.(dll|pyd|so|lib|exe)$'
    r'|(^|/)nvidia/[^/]+/'
    r'|(^|/)torch/(lib|bin)/'
    r'|(^|/)torch[^/]*_cuda[^/]*\.(pyd|dll|so)$'
    r'|(^|/)libtorch[^/]*\.(dll|so|lib)$')
APP_CUDA_BACKEND = re.compile(
    r'(?i)^app/(tts_cuda[^/]*\.py|tts_cuda_sidecar\.py)$|(^|/)_fq3tts_env')
THIRD_PARTY_SHIM = re.compile(
    r'(?i)^python/Lib/site-packages/'
    r'(openvino/torch/|scipy/_external/array_api_compat/torch/)')
CUDA_SRC = re.compile(
    r'(?i)^python/Lib/site-packages/(numba|transformers)/.*\.(cu|cuh)$')
TEXT_EXT = {'.py', '.md', '.json', '.txt', '.bat', '.xml', '.cfg', '.ini',
            '.jinja', '.yaml', '.yml'}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    if not os.path.isdir(PKG):
        raise SystemExit('[FATAL] 干净目录包不存在：%s' % PKG)
    first = json.load(open(FIRST, encoding='utf-8'))
    recheck = json.load(open(RECHECK, encoding='utf-8'))

    core_hits = {k: [] for k in CORE}
    dev_path_hits = []
    cuda_native = []
    app_cuda_backend = []
    third_party_shim = []
    cuda_src = []
    n_files = 0
    total_bytes = 0

    for r, _d, fs in os.walk(PKG):
        for f in fs:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, PKG).replace('\\', '/')
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            n_files += 1
            total_bytes += sz
            for k, cre in CORE.items():
                if cre.search(rel) and len(core_hits[k]) < 30:
                    core_hits[k].append(rel)
            if CUDA_NATIVE.search(rel) and len(cuda_native) < 30:
                cuda_native.append(rel)
            if APP_CUDA_BACKEND.search(rel) and len(app_cuda_backend) < 30:
                app_cuda_backend.append(rel)
            if THIRD_PARTY_SHIM.search(rel) and len(third_party_shim) < 30:
                third_party_shim.append(rel)
            if CUDA_SRC.search(rel) and len(cuda_src) < 30:
                cuda_src.append(rel)
            if os.path.splitext(f)[1].lower() in TEXT_EXT and sz < 4_000_000:
                try:
                    txt = open(p, 'rb').read().decode('utf-8', errors='ignore')
                except OSError:
                    continue
                for m in DEV_PATH.finditer(txt):
                    ls = txt.rfind('\n', 0, m.start()) + 1
                    le = txt.find('\n', m.end())
                    line = txt[ls:le if le > 0 else len(txt)].strip()[:200]
                    # 是否为「规则字面量自引用」：本行是正则/常量定义，而非路径引用
                    is_rule = bool(re.search(r"(?i)(pattern|regex|re\.compile|"
                                             r"blacklist|BLACKLIST|r['\"])", line))
                    dev_path_hits.append({
                        'path': rel, 'match': m.group(0)[:80], 'line': line,
                        'classification': ('rule_literal_self_reference'
                                           if is_rule else 'unknown_context'),
                        'is_real_leaked_file_reference': not is_rule,
                    })

    # —— 反证：精确化判据必须能识破真缺陷，且干净反例不误伤 ——
    cases = [
        ('cuda_native_dll',
         'python/Lib/site-packages/torch/lib/torch_cuda.dll', 'rel', CUDA_NATIVE),
        ('cudnn_runtime',
         'python/Lib/site-packages/nvidia/cudnn/lib/cudnn64_8.dll',
         'rel', CUDA_NATIVE),
        ('app_cuda_backend',
         'app/tts_cuda.py', 'rel', APP_CUDA_BACKEND),
        ('meeting_wav',
         'results/260902_SPE_spoken.wav', 'rel', CORE['meeting']),
        ('clone_wav',
         'app/voices/spk_clone_s1.wav', 'rel', CORE['clone_wav']),
        ('babelvox_demo',
         'python/Lib/site-packages/babelvox/data/speakers/cindy.json',
         'rel', CORE['babelvox_demo']),
        ('bridge_token',
         'ext/bridge_token.txt', 'rel', CORE['bridge_token']),
        ('real_dev_path_leak',
         r'C:\Users\Trekker-PTL\confucius4-openvino\secret.txt',
         'text', DEV_PATH),
    ]
    counter = []
    tmp = tempfile.mkdtemp(prefix='_app336_counterproof_')
    try:
        for name, payload, mode, cre in cases:
            hit = bool(cre.search(payload))
            if mode == 'rel':
                p = os.path.join(tmp, payload.replace('/', os.sep))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(b'FIXTURE')
            counter.append({'id': 'CP_' + name, 'injected': payload,
                            'detected': hit, 'identified': hit})
        # 干净反例：预设 A 音色 / 第三方 shim / 普通文档
        for name, rel in [
            ('clean_preset_A', 'app/voices/preset_A.wav'),
            ('clean_third_party_shim',
             'python/Lib/site-packages/openvino/torch/__init__.py'),
            ('clean_doc', 'README_zh.md'),
        ]:
            p = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(b'FIXTURE')
            hit = (any(c.search(rel) for c in CORE.values())
                   or bool(CUDA_NATIVE.search(rel))
                   or bool(APP_CUDA_BACKEND.search(rel)))
            counter.append({'id': 'CP_' + name, 'injected': rel,
                            'detected': hit, 'identified': not hit})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_cp = sum(1 for c in counter if c['identified'])
    cp_ok = (n_cp == len(counter))

    n_core = sum(len(v) for v in core_hits.values())
    true_leak = [h for h in dev_path_hits
                 if h['is_real_leaked_file_reference']]
    rule_self_ref = [h for h in dev_path_hits
                     if not h['is_real_leaked_file_reference']]

    core_verdict = True if n_core == 0 and cp_ok else (False if n_core else None)
    # 🔴 三态：规则字面量是否算「开发路径」命中 ⇒ 口径歧义，不自行裁定
    dev_path_verdict = None if rule_self_ref else (False if true_leak else True)
    torch_verdict = (False if (cuda_native or app_cuda_backend)
                     else (True if cp_ok else None))
    overall = (False if (core_verdict is False or torch_verdict is False
                         or dev_path_verdict is False)
               else None)  # 存在 UNKNOWN ⇒ 整体「无法判定」，交 reviewer

    ev = {
        'tool': 'app336', 'app': 'APP-080 ⑥ / APP-081 4d',
        'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': PKG, 'n_files': n_files, 'total_bytes': total_bytes,
        'scope': '只新增补充诊断；不修改 app332/app335 两份原始结果文件',
        'prior_results': {
            'app332_v23_blacklist': {
                'verdict': first.get('verdict'),
                'n_hits_real': first.get('n_hits_real'),
                'n_rule_self_reference': first.get('n_rule_self_reference')},
            'app335_v23_blacklist_recheck': {
                'verdict': recheck.get('verdict'),
                'n_real_violations': recheck.get('n_real_violations'),
                'counterproof_identified': recheck.get('counterproof_identified')},
        },
        'core_4_categories': {
            'hits': core_hits, 'n_hits': n_core,
            'verdict': core_verdict,
            'note': '会议录音 / 克隆音色 / babelvox 示例音色 / bridge_token.txt'},
        'dev_path': {
            'verdict': dev_path_verdict,
            'n_regex_hits': len(dev_path_hits),
            'n_true_leaked_file_reference': len(true_leak),
            'n_rule_literal_self_reference': len(rule_self_ref),
            'hits': dev_path_hits,
            'note': ('命中项为随包闸门 app/v23_preset_only.py 的 BLACKLIST_PATTERNS '
                     '正则字面量，属「判据自引用」而非开发机文件引用；但字面量本身'
                     '把开发机用户名带进了交付包 ⇒ 已识别的交付瑕疵，如实列出，'
                     '不静默判 PASS。是否计入 APP-080 ⑥「开发路径」由 reviewer 裁定；'
                     '本轮按 APP-081 6 不自创任务、不重打包，转后续版本去除用户名。'),
        },
        'torch_cuda': {
            'verdict': torch_verdict,
            'n_cuda_native_binary': len(cuda_native),
            'cuda_native_binary': cuda_native,
            'n_app_cuda_backend': len(app_cuda_backend),
            'app_cuda_backend': app_cuda_backend,
            'n_third_party_python_shim': len(third_party_shim),
            'third_party_python_shim_sample': third_party_shim,
            'n_third_party_cuda_source': len(cuda_src),
            'third_party_cuda_source_sample': cuda_src,
            'criteria': {
                'CUDA_NATIVE': CUDA_NATIVE.pattern,
                'APP_CUDA_BACKEND': APP_CUDA_BACKEND.pattern,
                'THIRD_PARTY_SHIM': THIRD_PARTY_SHIM.pattern},
            'note': ('app335 的 active_cuda=13 全部来自 openvino/torch 与 '
                     'scipy/_external/array_api_compat/torch 的纯 Python 兼容 shim'
                     '（含 .pyc），因 ACTIVE_CUDA 正则里裸 `torch/` 命中；'
                     '包内 CUDA 运行时二进制 / torch 原生库 / App 侧 CUDA 后端'
                     '实测计数见上。第三方 .cu 源码只作 informational 不判负。'),
        },
        'counterproof': counter,
        'counterproof_identified': '%d/%d' % (n_cp, len(counter)),
        'counterproof_all_pass': cp_ok,
        'verdict_tristate': overall,
        'verdict': ('PASS' if overall is True else
                    'FAIL' if overall is False else 'UNKNOWN'),
        'verdict_note': ('UNKNOWN = 核心 4 类 0 命中、无 CUDA 运行时、反证全过，'
                         '但存在 1 项「规则字面量是否算开发路径」口径歧义 ⇒ '
                         '按三态纪律「无法判定」≠「不合格」，转 reviewer 复核；'
                         '不自行改判 PASS。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] 核心4类=%d dev_path=%d(自引用%d/真泄漏%d) '
          'cuda_native=%d app_cuda=%d shim=%d 反证=%d/%d ⇒ %s'
          % (ev['verdict'], n_core, len(dev_path_hits), len(rule_self_ref),
             len(true_leak), len(cuda_native), len(app_cuda_backend),
             len(third_party_shim), n_cp, len(counter), OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
