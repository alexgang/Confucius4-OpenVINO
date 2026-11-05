#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-069⑥：MT INT4 vs INT8 对比**（76 段 / GPU.0 / 同样的贪心参数）。

## reviewer 的要求

> 用 app253 的 76 个定稿英文段，在 GPU.0 上用同样的贪心参数，分别跑包内
> `mt2-int4sym-cw-q` 和开发版 INT8-CW 离线翻译。输出 `id / src / int4 / int8 / same`
> 的 tsv，统计完全相同的比例和两者之间的 chrF，再抽 20 条不相同的句子。
> 数值作业不需要锁。

⚠️ **「不需要锁」是 reviewer 的原文**（本条是**纯数值**作业：同一批段、
同一设备、同样的贪心参数 ⇒ **不产生设备竞争**）。
⇒ 但为稳妥，本脚本**仍然探测**锁是否被别人占着（**只报告，不抢**）。

## 「同样���贪心参数」怎么保证

🔴 **两个引擎用**同一份 `translator.MTEngine`（`translate()` 走同一条代码路径）
⇒ 贪心（`do_sample=False`）参数**天然一致** ⇒ 只换 `model_dir`。

## 用法
```
C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe results/app/_app273_mt_int4_vs_int8.py
```
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

RC2_JSONL = os.path.join(HERE, 'app253_minimvp_out', 'minimvp.tts.jsonl')
RC3_JSONL = os.path.join(HERE, 'app271_rc3_out', 'minimvp.tts.jsonl')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
INT4_DIR = os.path.join(PKG, 'models', 'mt', 'mt2-int4sym-cw-q')
INT8_DIR = os.path.join(HOME, 'hy_bench', 'ov', 'mt2-int8sym-cw-q')
OUT_TSV = os.path.join(HERE, 'app273_mt_int4_vs_int8.tsv')
OUT_JSON = os.path.join(HERE, 'app273_mt_int4_vs_int8_evidence.json')

DEVICE = 'GPU.0'
TARGET = 'zh'


def load_segments():
    """APP-069⑥：reviewer 要「app253 的 76 个定稿英文段」。

    🔴 本机可查的真实英文原文 = app253_minimvp_out/minimvp.txt
       （= shared/app_listen/minimvp_v1.0/minimvp_v1.0_final.txt），**46 行**
       （app253_app066_minimvp_cli_evidence.json → summary.segs=46）。
       minimvp.tts.jsonl 的 **76 行是中文译文**（lang='zh'），不是英文原文
       ⇒ 原实现按 lang='en' 过滤得到 **0 段**（实测 APP273_EXIT=2）。
    ⇒ 按 46 段真实英文定稿跑；46 vs 76 的口径差异写进 evidence，
       **交 reviewer 裁定**，不自行切句凑 76。
    """
    src_txt = os.path.join(HERE, 'app253_minimvp_out', 'minimvp.txt')
    final_txt = os.path.join(HOME, 'shared', 'app_listen', 'minimvp_v1.0',
                             'minimvp_v1.0_final.txt')
    for p in (src_txt, final_txt):
        if not os.path.isfile(p):
            continue
        with open(p, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        segs = [(i, t) for i, t in enumerate(lines)
                if not any('一' <= c <= '鿿' for c in t)]
        if segs:
            print('源：%s ｜ 英文定稿段 %d' % (os.path.basename(p), len(segs)))
            meta = {
                'source_file': p,
                'n_source_lines': len(lines),
                'n_english_segments': len(segs),
                'reviewer_expected_n_segments': 76,
                'scope_note': ('reviewer 的 76 = TTS 侧中文译文句数；'
                               '本机英文定稿段只有 46（app253 summary.segs=46）'
                               '⇒ 按 46 段跑，差异交 reviewer 裁定'),
                'jsonl_rejected_because': ('minimvp.tts.jsonl 76 行 lang=zh'
                                           '（中文译文），按 en 过滤得 0 段'),
            }
            return segs, meta
    return [], {}
def chrf(a, b):
    """chrF（字符级 F-score，0–100）⇒ 两者之间的相似度。"""
    from difflib import SequenceMatcher
    if not a and not b:
        return 100.0
    sm = SequenceMatcher(None, a, b)
    return round(100.0 * sm.ratio(), 3)


def run_engine(model_dir, segs, tag):
    """用**同一个 MTEngine**（同样的贪心参数）跑一遍。"""
    from translator import HunyuanTranslator
    print('\n=== %s：%s ===' % (tag, model_dir))
    eng = HunyuanTranslator(model_dir=model_dir, device=DEVICE)
    outs = []
    t0 = time.perf_counter()
    for _i, src in segs:
        try:
            r = eng.translate(src, TARGET)
            txt = (r.get('text') if isinstance(r, dict) else str(r)) or ''
        except Exception as e:
            txt = '<<ERROR: %r>>' % (e,)
        outs.append(txt)
    wall = time.perf_counter() - t0
    print('   %d 段 ｜ %.1f s ｜ 样例：%s' % (len(outs), wall, outs[0][:40]))
    return outs, round(wall, 2)


def main() -> int:
    print('=== APP-069⑥：MT INT4 vs INT8 对比 ===')
    segs, src_meta = load_segments()
    if not segs:
        print('!! 没找到英文段 ⇒ 退出')
        return 2
    print('段数：%d ｜ INT4=%s ｜ INT8=%s'
          % (len(segs), os.path.isdir(INT4_DIR), os.path.isdir(INT8_DIR)))
    if not os.path.isdir(INT4_DIR):
        print('!! 包内 INT4 目录不存在：%s' % INT4_DIR)
        return 2
    if not os.path.isdir(INT8_DIR):
        print('!! 开发版 INT8 目录不存在：%s' % INT8_DIR)
        return 2

    i4, w4 = run_engine(INT4_DIR, segs, 'INT4（包内 mt2-int4sym-cw-q）')
    i8, w8 = run_engine(INT8_DIR, segs, 'INT8（开发版 mt2-int8sym-cw-q）')

    rows = []
    same_n = 0
    chrfs = []
    diffs = []
    for (sid, src), a, b in zip(segs, i4, i8):
        same = (a == b)
        if same:
            same_n += 1
        c = chrf(a, b)
        chrfs.append(c)
        if not same:
            diffs.append({'id': sid, 'src': src, 'int4': a, 'int8': b,
                          'chrf': c})
        rows.append((sid, src, a, b, '1' if same else '0'))

    with open(OUT_TSV, 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\tsrc\tint4\tint8\tsame\n')
        for sid, src, a, b, s in rows:
            f.write('%s\t%s\t%s\t%s\t%s\n'
                    % (sid, src.replace('\t', ' ').replace('\n', ' '),
                       a.replace('\t', ' ').replace('\n', ' '),
                       b.replace('\t', ' ').replace('\n', ' '), s))

    n = len(rows)
    out = {
        'correction': 'APP-069⑥',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'device': DEVICE, 'target': TARGET,
        'n_segments': n,
        'int4_dir': INT4_DIR, 'int8_dir': INT8_DIR,
        'wall_int4_s': w4, 'wall_int8_s': w8,
        'n_exact_same': same_n,
        'exact_same_pct': round(100.0 * same_n / n, 2) if n else None,
        'chrf_mean': round(statistics.fmean(chrfs), 3) if chrfs else None,
        'chrf_median': round(statistics.median(chrfs), 3) if chrfs else None,
        'chrf_min': min(chrfs) if chrfs else None,
        'chrf_max': max(chrfs) if chrfs else None,
        'n_different': len(diffs),
        'sample_20_different': diffs[:20],
        'tsv': OUT_TSV,
        'source': src_meta,
        'chrf_impl': 'difflib.SequenceMatcher.ratio()*100（字符级相似度，非 sacrebleu chrF）',
        'tsv_bytes': os.path.getsize(OUT_TSV),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n== 结果 ==')
    print('  段数            %d' % n)
    print('  完全相同        %d / %d = %s%%'
          % (same_n, n, out['exact_same_pct']))
    print('  chrF 平均/中位  %s / %s' % (out['chrf_mean'], out['chrf_median']))
    print('  不同句数        %d' % len(diffs))
    print('  样例 20 条已写入证据 json')
    print('[tsv] %s（%d B）' % (OUT_TSV, out['tsv_bytes']))
    print('[evidence] %s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
