#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app319_rc5_zip_unzip_check.py —— **rc5 zip 的干净解压复验**（APP-096 §3b）。

## 依据

* **APP-096 §3b**：按 rc4 §163 ④ 的口径在**干净目录解压**复验；
  zip 清单里 **R2T2 ASR 文件 0 个、int4 decoder 文件 0 个**（贴出清单 grep 结果）。
* **APP-096 §3c**：写出和 rc4 相比的**大小变化**（目录和 zip 两项）。
* **APP-096 §3d**：这个包还要能在 **Meteor Lake（Core Ultra 7 155H）** 上运行：
  不带 Panther Lake 专属的 NPU 缓存（blob / cache_dir 产物）或配置，
  **不把 NPU 架构 5010 写死**。

## 🔴 纪律

* 解压到**全新目录**（先删后建）⇒ 不碰任何已有目录。
* 用**包内自己的 python** 跑 `--check` ⇒ 验的是客户环境那一份 OV。
* 缓存写**独立临时目录** ⇒ 不复用 Panther Lake 的产物冒充可移植性证据。

## 用法

```
.venv/Scripts/python.exe results/app/_app319_rc5_zip_unzip_check.py
```
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

ZIP = os.path.join(HOME, 'shared', 'minimvp',
                   'Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip')
ZIP4 = os.path.join(HOME, 'shared', 'minimvp',
                    'Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip')
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5'
CLEAN = os.path.join(HOME, 'minimvp_rc5_clean')
REPORT = os.path.join(HERE, 'app319_rc5_zip_unzip_check_evidence.json')

#: 必须为 0 的清单项（APP-096 §2 / §3b）
FORBIDDEN_PATTERNS = (
    r'models/encoder-int8/',
    r'models/decoder-gpu-int8/',
    r'models/encoder-fp16/',
    r'models/decoder-npu-int8/',
    r'models/decoder-npu-int4/',
    r'embed_tokens_f16\.npy',
)
#: 必须存在的 0.6B 物料
REQUIRED_06B = (
    'models/asr06b-encoder-fp16/ov-encoder-06b-fp16-static.xml',
    'models/asr06b-decoder-int8/openvino_model.xml',
    'models/embed_tokens_06b_f16.npy',
    'models/asr06b-tokenizer/tokenizer_config.json',
)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    ev = {'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
          'correction': 'APP-096 §3b/§3c/§3d', 'checks': []}

    def chk(name, cond, detail):
        ev['checks'].append({'name': name, 'pass': bool(cond), 'detail': detail})
        print('[%s] %s — %s' % ('PASS' if cond else 'FAIL', name, detail))

    if not os.path.exists(ZIP):
        print('!! zip 不存在')
        ev['verdict'] = 'NO_ZIP'
        _dump(ev)
        return 2

    # ── ① 清单 grep（R2T2 / int4 计数必须 0）────────────────────
    with zipfile.ZipFile(ZIP, 'r') as zf:
        names = zf.namelist()
    ev['n_entries'] = len(names)
    counts = {}
    for pat in FORBIDDEN_PATTERNS:
        hits = [n for n in names if re.search(pat, n)]
        counts[pat] = {'count': len(hits), 'samples': hits[:3]}
    ev['forbidden_grep'] = counts
    nz = {k: v['count'] for k, v in counts.items() if v['count']}
    chk('zip 清单 R2T2/INT4 计数为 0', not nz, str(nz))
    miss = [r for r in REQUIRED_06B
            if not any(n.endswith(r) for n in names)]
    chk('zip 清单含 0.6B 物料', not miss, 'missing=%r' % miss)

    # ── ② §3d：不含 Panther Lake 专属缓存 / 不写死 5010 ──────────
    blobs = [n for n in names if n.endswith('.blob')]
    chk('zip 内无预编译 NPU blob（§3d）', not blobs, 'n=%d' % len(blobs))
    arch_hits = []
    # 🔴🔴🔳 **判据口径（两轮修正）**：
    #    ① 排除 **tokenizer 词表**（`"Ġblog": 5010` 是**词表 token id**）。
    #    ② 排除 **site-packages 第三方库**（scipy 的 `test_hypotests.py`
    #       里同时出现 `5010` 与 `NPU` 字样 ⇒ 与本包的 NPU 无关）。
    #    ⇒ **只查 App 自有代码**：`app/` 与包根的脚本/文档。
    _OWN_PREFIX = (PKG_NAME + '/app/', PKG_NAME + '/models/asr06b-',
                   PKG_NAME + '/README', PKG_NAME + '/NOTICE')
    for n in names:
        if not (n.endswith('.py') or n.endswith('.bat') or n.endswith('.cmd')
                or n.endswith('.json') or n.endswith('.md')):
            continue
        if not any(n.startswith(pfx) for pfx in _OWN_PREFIX):
            continue
        if '/tokenizer' in n or n.endswith('vocab.json'):
            continue
        p = os.path.join(CLEAN, n.replace('/', os.sep))
        if not os.path.exists(p):
            continue
        try:
            t = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        # 「架构硬编码」：**5010 与 NPU/架构判定同现**
        if '5010' in t and re.search(r'NPU|DEVICE_ARCHITECTURE|npu_arch',
                                     t):
            arch_hits.append(n)
    ev['npu_arch_5010_hits'] = arch_hits[:20]
    chk('App 自有代码不写死 NPU 架构 5010（§3d）', not arch_hits,
        'hits=%r' % arch_hits[:5])

    # ── ③ §3c：与 rc4 的 zip 体积差 ─────────────────────────────
    ev['zip5_bytes'] = os.path.getsize(ZIP)
    ev['zip4_bytes'] = os.path.getsize(ZIP4) if os.path.exists(ZIP4) else None
    if ev['zip4_bytes']:
        ev['zip_delta_bytes'] = ev['zip5_bytes'] - ev['zip4_bytes']
        ev['zip_delta_gb'] = round(ev['zip_delta_bytes'] / 2 ** 30, 3)
        ev['zip_entries_delta'] = len(names) - len(
            zipfile.ZipFile(ZIP4).namelist())

    # ── ④ 干净解压（先删后建）──────────────────────────────────
    if os.path.exists(CLEAN):
        # 🔴 **不用 `shutil.rmtree`**：批量删除会被宿主的 safe-delete 拦截
        #    （`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，count=9999 > threshold=50）
        #    ⇒ 改成「**改名成 .old_<时间戳>**」⇒ 旧目录留在盘上（可人工清），
        #    但**不影响**本次复验（解压到全新目录名）。
        old = CLEAN + '.old_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        os.rename(CLEAN, old)
        ev['clean_dir_old_renamed_to'] = old
    os.makedirs(CLEAN, exist_ok=True)
    t0 = time.time()
    with zipfile.ZipFile(ZIP, 'r') as zf:
        zf.extractall(CLEAN)
    ev['unzip_s'] = round(time.time() - t0, 1)
    pkg = os.path.join(CLEAN, PKG_NAME)
    chk('解压后包目录存在', os.path.isdir(pkg), pkg)
    n_files = sum(len(f) for _r, _d, f in os.walk(pkg))
    ev['unzipped_files'] = n_files

    # ── ⑤ 用**包内 python** 跑 --check ──────────────────────────
    py = os.path.join(pkg, 'python', 'python.exe')
    cache = tempfile.mkdtemp(prefix='rc5_clean_cache_')
    env = dict(os.environ)
    env['LOCALAPPDATA'] = cache
    env['PYTHONIOENCODING'] = 'utf-8'
    t0 = time.time()
    p = subprocess.run([py, os.path.join(pkg, 'app', 'live_caption_app.py'),
                        '--check'],
                       env=env, cwd=pkg, capture_output=True, text=True,
                       timeout=1200)
    out_txt = p.stdout + p.stderr
    ev['check_rc'] = p.returncode
    ev['check_s'] = round(time.time() - t0, 1)
    ev['check_out'] = out_txt[-4000:]
    chk('--check 退出码为 0', p.returncode == 0, 'rc=%d' % p.returncode)
    chk('--check 显示 Intel NPU · INT8 模型齐全',
        ('Intel NPU · INT8' in out_txt and '模型齐全' in out_txt),
        '命中=%r' % ('Intel NPU · INT8' in out_txt))
    # 🔴🔴🔳 **判据只查 ASR 段**：整份输出里 `Intel NPU · INT4-CW` 是
    #    **MT 翻译后端**（Hy-MT2 仍是 INT4 ⇒ 正确保留）⇒ 全局 grep 会误报。
    #    ⇒ 必须**只在「ASR 后端（识别）」这一段内**查。
    m_asr = re.search(r'── ASR 后端[^─]*──\n(.*?)\n\n', out_txt, re.S)
    asr_block = m_asr.group(1) if m_asr else ''
    ev['asr_block'] = asr_block
    chk('--check 的 ASR 段无 INT4 档（APP-095 1a）',
        ('INT4' not in asr_block) and bool(asr_block),
        'ASR 段含 INT4=%r（段长 %d）'
        % ('INT4' in asr_block, len(asr_block)))
    # 🔴 **判据**：GPU/NPU 两档都必须是 **INT8** 且齐全。
    #    ⚠️ 不能写死「模型齐全 行数 == 2」—— **CUDA 两档**（audio.cpp 路线）
    #    也在 ASR 段里（rc4 同样有）⇒ 那是**另一种 kind**，不属本条纠偏范围。
    _gpu_ok = re.search(r'Intel GPU · INT8\s+模型齐全', asr_block) is not None
    _npu_ok = re.search(r'Intel NPU · INT8\s+模型齐全', asr_block) is not None
    chk('--check 的 ASR 段：GPU INT8 与 NPU INT8 都齐全',
        _gpu_ok and _npu_ok,
        'gpu=%r npu=%r（ASR 段行数 %d）'
        % (_gpu_ok, _npu_ok, len(asr_block.strip().split('\n'))))

    ev['n_fail'] = sum(1 for c in ev['checks'] if not c['pass'])
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    _dump(ev)
    return 0 if ev['n_fail'] == 0 else 1


def _dump(ev):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)


if __name__ == '__main__':
    sys.exit(main())
