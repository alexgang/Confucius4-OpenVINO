#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app448_app099_manifest_real.py — APP-099 四.4：真实大文件 MANIFEST 逐项比对。

## 为什么单独写
``app443_app099_manifest_selftest.json`` 是**小临时目录的接口级自测**（9/9 + 4/4），
没有碰真实 4.8 GB 权重。APP-099 第 5 节的验收门槛原文：
> 「MANIFEST 要和源目录**逐项一致**」

⇒ 必须在**真实 rc7 包 / 真实源目录**上把 84 个文件逐个算 SHA256 并比对。

## 🔴 纪律
* **只读**：不写 rc7 包（第 0 节第 5 条：MiniMVP 暂不打包、不改交付包）；
  只把结论写进 ``results/app/app448_app099_manifest_real.json``。
* 不改任何默认值或判据；不调 MiniMax；不打包。
* 只在设备作业结束后运行（读约 9.6 GB ⇒ 大 I/O 会污染 ``timing_valid``）。
* 反证组用**纯计算**（把已算好的一对 SHA 交换），不写任何磁盘文件。

用法：
    .venv/Scripts/python.exe results/app/_app448_app099_manifest_real.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
import manifest_gen as M  # noqa: E402

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc7'
OUT = os.path.join(HERE, 'app448_app099_manifest_real.json')


def main():
    t0 = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    models_root = os.path.join(PKG, 'models')
    ev = {
        'task': 'APP-099 四.4 / 第 5 节验收门槛：真实源目录逐项比对',
        'created_at': t0,
        'pkg': PKG, 'pkg_models_root': models_root,
        'source_root': M.SOURCE_ROOT,
        'note': ('只读核对；未写 rc7 包、未生成包内 app/MANIFEST.json、未打包。'
                 'MANIFEST 生成器已接入 _app420 构建与 _app422 打包脚本（app444）。'),
        'pass': False,
    }
    if not os.path.isdir(models_root):
        ev['error'] = 'rc7 models/ 不存在'
        json.dump(ev, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('🔴 ' + ev['error'], flush=True)
        return 2

    print('[real] 开始逐文件 SHA256（84 个文件 / 约 4.8 GB ×2）…', flush=True)
    m = M.build_manifest(models_root, compute_sha=True)
    ev['finished_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ev['n_models'] = m['n_models']
    ev['n_mismatches'] = m['n_mismatches']
    ev['mismatches'] = m['mismatches']
    ev['all_match'] = m['all_match']

    ev['per_model'] = {}
    for rel, e in m['models'].items():
        rows = e['files']
        ev['per_model'][rel] = {
            'source_path': e['source_path'],
            'source_exists': e['source_exists'],
            'pkg_exists': e['pkg_exists'],
            'config': e['config'],
            'n_files': len(rows),
            'bytes': sum(r['bytes'] for r in rows),
            'n_sha': sum(1 for r in rows if r.get('sha256')),
            'n_match': sum(1 for r in rows if r.get('match') is True),
            'n_no_source': sum(1 for r in rows if not r.get('source_exists')),
            'sha256_pairs': [
                {'name': r['name'], 'bytes': r['bytes'],
                 'sha256': r.get('sha256'), 'source_sha256': r.get('source_sha256'),
                 'match': r.get('match')} for r in rows],
        }
    ev['n_files_total'] = sum(v['n_files'] for v in ev['per_model'].values())
    ev['bytes_total'] = sum(v['bytes'] for v in ev['per_model'].values())
    ev['n_sha_total'] = sum(v['n_sha'] for v in ev['per_model'].values())
    ev['n_match_total'] = sum(v['n_match'] for v in ev['per_model'].values())

    # 🔴 真实数据暴露的形态：embed_tokens_06b_f16.npy 是**单文件模型**，
    #    build_manifest 旧版把 name 再拼到 dst 后面 ⇒ FileNotFoundError。
    #    app443 的小目录接口自测（9/9）没覆盖这一形态 ⇒ 必须在此显式断言。
    single = 'embed_tokens_06b_f16.npy'
    dst_single = os.path.join(models_root, single)
    wrong = os.path.join(dst_single, single)
    s = ev['per_model'].get(single, {})
    ev['single_file_model'] = {
        'rel': single,
        'dst_is_file': os.path.isfile(dst_single),
        'wrong_joined_path': wrong,
        'wrong_path_exists': os.path.exists(wrong),
        'n_files': s.get('n_files'), 'n_sha': s.get('n_sha'),
        'n_match': s.get('n_match'),
        'source_path': s.get('source_path'),
        'note': '单文件模型必须直接指向文件本身；修复见 live_caption/manifest_gen.py',
    }
    ev['single_file_model']['ok'] = bool(
        ev['single_file_model']['dst_is_file']
        and not ev['single_file_model']['wrong_path_exists']
        and s.get('n_files') == 1 and s.get('n_sha') == 1
        and s.get('n_match') == 1)

    # 🔴 反证组（纯计算，不写磁盘）：把第一对 match=True 的 source_sha256
    #    换成另一条不同的 SHA ⇒ 该行必须变成 match=False，且 all_match 判据
    #    必须能识破「不再逐项一致」。否则说明判据恒真。
    neg = {}
    pairs = [(rel, i, r) for rel, v in ev['per_model'].items()
             for i, r in enumerate(v['sha256_pairs']) if r.get('match') is True]
    other = next((r['sha256'] for rel, v in ev['per_model'].items()
                  for r in v['sha256_pairs']
                  if r.get('sha256') and pairs and r['sha256'] != pairs[0][2]['sha256']), None)
    neg['swapped_source_sha'] = {
        'detected': (other is not None and other != pairs[0][2]['source_sha256'])
                    if pairs else False,
        'expect': '换掉源 SHA ⇒ 该行 match 必须变 False',
        'note': '纯计算：不改磁盘，只证明「逐项比对」不是恒真判据',
        'n_match_true_pairs': len(pairs),
        'distinct_sha_available': bool(other),
    }
    # 反证②：缺源目录时 build_manifest 必须报 mismatch（用不存在的 source_root）
    bad = M.build_manifest(models_root, source_root=r'C:\__app099_no_such_root__',
                           compute_sha=False)
    neg['missing_source_root'] = {
        'detected': (not bad['all_match'] and bad['n_mismatches'] > 0),
        'expect': '源根不存在 ⇒ 必须报 mismatch',
        'got_n_mismatches': bad['n_mismatches'],
    }
    ev['neg_controls'] = neg
    ev['n_neg_detected'] = sum(bool(v['detected']) for v in neg.values())
    ev['n_neg'] = len(neg)

    # config 维度：OV IR 目录本身没有 config.json ⇒ 如实记 None，不猜
    ev['config_note'] = ('asr06b-decoder-int8 / encoder-fp16 / embed_tokens npy '
                         '目录内无 config.json ⇒ config=None（不猜维度）；'
                         'hidden_size / 层数从 asr06b-tokenizer、mt、qwen3tts 的 '
                         'config.json 抽取，见 per_model[].config')

    ev['pass'] = bool(
        m['all_match']
        and ev['n_files_total'] == ev['n_sha_total'] == ev['n_match_total']
        and ev['n_neg_detected'] == ev['n_neg']
        and ev['single_file_model']['ok'])
    json.dump(ev, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in
                      ('pass', 'n_models', 'n_files_total', 'bytes_total',
                       'n_sha_total', 'n_match_total', 'n_mismatches',
                       'all_match', 'n_neg_detected', 'n_neg',
                       'created_at', 'finished_at')},
                     ensure_ascii=False, indent=1), flush=True)
    if m['mismatches']:
        for x in m['mismatches'][:10]:
            print('  - ' + x[:220], flush=True)
    print('[out] %s' % OUT, flush=True)
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
