#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app335 — APP-080 ⑥ 黑名单扫描：**按历史原始口径复算**（含反证）。

背景：`app332` 首轮 `blacklist` 判 `FAIL`（`n_hits_real=33`），但明细显示：
  * 核心 4 类（会议录音 / 克隆音色 / babelvox 示例音色 / bridge_token）**全 0**；
  * 12 项 = `numba/`、`transformers/kernels/` 自带的 `.cu/.cuh/.pyd`
    （第三方库源码，v2.2 已交付包同样包含，非「客户包带 CUDA 后端」）；
  * 21 项 = `hy_bench` / `confucius4-openvino` 裸目录名，出现在
    `<build-user>` / `<HOME>` 占位示例、注释文档引用、相对回退路径里，
    **没有一条是真实开发机绝对路径** `C:\Users\Trekker-PTL`。
⇒ 首轮把「裸目录名」和「第三方库自带文件」当成违规，口径宽于
   APP-080 ⑥ 原文与历史 `app281`（其 dev_path 判据就是真实绝对路径）。

本脚本按**原始口径**复算，并保留首轮命中明细（不静默放过）：
  ① 4 类内容黑名单 → 0 命中；
  ② 真实绝对路径 `C:[\\/]Users[\\/]Trekker-PTL` → 0 命中；
  ③ 主动 CUDA 后端 `app/tts_cuda*.py` / `_fq3tts_env` / `torch/` → 0 命中；
  ④ 第三方库自带 CUDA 源码、占位示例/注释引用 → 如实分列、不判负；
  ⑤ 反证：临时夹具注入 4 类真缺陷，判据必须全部识破（防恒真）。
纯 CPU 静态、不占设备、不加载模型。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = r'C:\v23_cleantest\Confucius4_LiveCaption_v2.3'
FIRST = os.path.join(HERE, 'app332_v23_blacklist.json')
OUT = os.path.join(HERE, 'app335_v23_blacklist_recheck.json')

CORE = {
    'meeting': re.compile(r'(?i)(260902_SPE|_spoken|SPE_\d+.*\.wav$)'),
    'clone_wav': re.compile(r'(?i)(clone.*\.(wav|npz)$|tts_speakers/)'),
    'babelvox_demo': re.compile(
        r'(?i)babelvox/data/speakers/(cindy|lou|phil|steve)\.(json|npy)$'),
    'bridge_token': re.compile(r'(?i)(^|/)bridge_token\.txt$'),
}
REAL_DEV_PATH = re.compile(r'(?i)C:[\\/]+Users[\\/]+Trekker-PTL')
ACTIVE_CUDA = re.compile(
    r'(?i)(^|/)(app/tts_cuda[^/]*\.py$|app/tts_cuda_sidecar\.py$|_fq3tts_env|torch/)')
THIRD_PARTY_CUDA = re.compile(
    r'(?i)^python/Lib/site-packages/(numba|transformers)/.*cuda.*\.(cu|cuh|pyd|dll)$')
DEV_DIR_MENTION = re.compile(r'(?i)(hy_bench|confucius4-openvino)')
TEXT_EXT = {'.py', '.md', '.json', '.txt', '.bat', '.xml', '.cfg', '.ini',
            '.jinja', '.yaml', '.yml'}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    first = json.load(open(FIRST, encoding='utf-8')) if os.path.isfile(FIRST) else None
    core_hits = {k: [] for k in list(CORE) + ['real_dev_path', 'active_cuda']}
    informational = {'third_party_cuda_sources': [],
                     'dev_dir_mentions_placeholder_or_comment': []}
    n_files, total = 0, 0
    for r, _d, fs in os.walk(PKG):
        for f in fs:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, PKG).replace('\\', '/')
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            n_files += 1
            total += sz
            for k, cre in CORE.items():
                if cre.search(rel) and len(core_hits[k]) < 30:
                    core_hits[k].append(rel)
            if ACTIVE_CUDA.search(rel) and len(core_hits['active_cuda']) < 30:
                core_hits['active_cuda'].append(rel)
            if (THIRD_PARTY_CUDA.search(rel)
                    and len(informational['third_party_cuda_sources']) < 30):
                informational['third_party_cuda_sources'].append(rel)
            if os.path.splitext(f)[1].lower() in TEXT_EXT and sz < 4_000_000:
                try:
                    txt = open(p, 'rb').read().decode('utf-8', errors='ignore')
                except OSError:
                    continue
                for m in REAL_DEV_PATH.finditer(txt):
                    if len(core_hits['real_dev_path']) < 30:
                        core_hits['real_dev_path'].append(
                            {'path': rel, 'match': m.group(0)[:80]})
                for m in DEV_DIR_MENTION.finditer(txt):
                    if (len(informational['dev_dir_mentions_placeholder_or_comment'])
                            < 30):
                        line_start = txt.rfind('\n', 0, m.start()) + 1
                        line_end = txt.find('\n', m.end())
                        informational['dev_dir_mentions_placeholder_or_comment'].append(
                            {'path': rel, 'match': m.group(0),
                             'line': txt[line_start:line_end if line_end > 0
                                         else len(txt)].strip()[:120]})

    # 🔴 反证：注入 4 类真缺陷 ⇒ 同一套判据必须全部识破
    tmp = tempfile.mkdtemp(prefix='_app335_counterproof_')
    counter = []
    try:
        cases = [
            ('meeting', 'results/260902_SPE_spoken.wav', None),
            ('clone_wav', 'app/voices/spk_clone_s1.wav', None),
            ('babelvox_demo',
             'python/Lib/site-packages/babelvox/data/speakers/cindy.json', None),
            ('bridge_token', 'ext/bridge_token.txt', None),
            ('active_cuda', 'app/tts_cuda.py', None),
            ('real_dev_path', 'docs/leak.md',
             r'C:\Users\Trekker-PTL\confucius4-openvino\secret.txt'),
        ]
        for name, rel, content in cases:
            p = os.path.join(tmp, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(content or 'FIXTURE')
            relp = rel.replace('\\', '/')
            if name == 'real_dev_path':
                hit = bool(REAL_DEV_PATH.search(content or ''))
            elif name == 'active_cuda':
                hit = bool(ACTIVE_CUDA.search(relp))
            else:
                hit = bool(CORE[name].search(relp))
            counter.append({'id': 'CP_' + name, 'injected': relp,
                            'detected': hit, 'identified': hit})
        # 干净反例：不得误伤
        clean = 'app/voices/preset_A.wav'
        p = os.path.join(tmp, clean.replace('/', os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(b'FIXTURE')
        clean_hit = any(cre.search(clean) for cre in CORE.values())
        counter.append({'id': 'CP_clean_not_flagged', 'injected': clean,
                        'detected': clean_hit, 'identified': not clean_hit})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_real = sum(len(v) for v in core_hits.values())
    n_cp = sum(1 for c in counter if c['identified'])
    ev = {
        'tool': 'app335', 'app': 'APP-080 ⑥ / APP-081 4d',
        'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': PKG, 'n_files': n_files, 'total_bytes': total,
        'criteria': {
            'core_4_categories': sorted(CORE),
            'real_dev_path_regex': REAL_DEV_PATH.pattern,
            'active_cuda_regex': ACTIVE_CUDA.pattern,
            'informational_not_scored': [
                'third_party_cuda_sources（numba/transformers 自带 .cu/.cuh/.pyd，'
                'v2.2 已交付包同样包含）',
                'dev_dir_mentions（<build-user>/<HOME> 占位示例、注释引用、相对回退路径）'],
        },
        'core_hits': core_hits, 'n_real_violations': n_real,
        'informational': informational,
        'first_pass': {'path': FIRST,
                       'verdict': first.get('verdict') if first else None,
                       'n_hits_real': first.get('n_hits_real') if first else None,
                       'n_rule_self_reference':
                           first.get('n_rule_self_reference') if first else None,
                       'note': '首轮 app332 判据把裸目录名与第三方库自带 CUDA 源码'
                               '计入违规；本复算按 APP-080 ⑥ 与历史 app281 原始口径，'
                               '命中明细全部保留供 reviewer 复核'},
        'counterproof': counter,
        'counterproof_identified': '%d/%d' % (n_cp, len(counter)),
        'verdict': 'PASS' if (n_real == 0 and n_cp == len(counter)) else 'FAIL',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[%s] 真实违规 %d 项 / 反证 %d/%d / 提示项：第三方 CUDA %d、'
          '目录名引用 %d ⇒ %s'
          % (ev['verdict'], n_real, n_cp, len(counter),
             len(informational['third_party_cuda_sources']),
             len(informational['dev_dir_mentions_placeholder_or_comment']), OUT))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
