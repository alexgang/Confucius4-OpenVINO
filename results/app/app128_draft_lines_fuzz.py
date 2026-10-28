#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app128 —— app127 的**随机语料模糊测试**加固（MT notice 15 §3.4 同一条验收项）。

====================================================================
🔴 为什么要单独一个脚本
====================================================================
`app127` 用**三组手写语料**覆盖三种典型形态（链自然闭合 / 跨段强制切出 /
末段由 `flush()` 收尾）。三组语料全绿只能说明「这三种形态没问题」。

⇒ 本脚本用**固定随机种子**生成 **N 组随机语料**，覆盖
  · 随机段长（含单字符短句、极长句）
  · 随机标点分布（句中/句末/无标点）
  · 随机段数（1 ~ 12）
  · 随机是否触发 `PEND_MAX_SEGS` / `PEND_MAX_CHARS` 强制切出
⇒ 每一组都跑**真实时序**（真 `TranslationService` + 真工作线程 + 真 outbox）
⇒ 判据与 app127 的 R1/R2/R4/R5/R6/R7/R8/R9/R10 完全一致。

====================================================================
🔴🔴 口径纪律
====================================================================
· **不加载任何模型**（`StubTranslator`）⇒ 不跑推理、不占 GPU/NPU、**不取机器锁**；
· **不修改工作区任何文件**（只读仓库 `live_caption/translator.py` 与
  `live_caption/caption_render.py`）；
· **不调 MiniMax**（质量判定归 reviewer）；
· 随机种子**写死**（`SEED`）⇒ 结论可复现；
· 证据落盘 `app128_draft_lines_fuzz_evidence.json`。
"""

import io
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP_DIR = os.path.join(REPO, 'live_caption')

sys.path.insert(0, HERE)
import app127_c111_real_timing_draft_lines as A   # noqa: E402

SEED = 20261028
N_CASES = 120

# 随机语料的片段素材（英文，够长能触发切分；含无标点尾巴）
_WORDS = ('market expansion region budget hiring timeline '
          'engineering executive board quarterly review agenda '
          'numbers detail strategy priorities alignment').split()

_PUNCT = ['.', '?', '!', '', ',']


def _rand_case(rnd):
    """生成一组随机语料：返回 (语料名, segments 列表)。"""
    n_seg = rnd.randint(1, 12)
    segs = []
    for _ in range(n_seg):
        n_w = rnd.choice([1, 2, 3, 5, 8, 12, 18, 25])
        txt = ' '.join(rnd.choice(_WORDS) for _ in range(n_w))
        # 句尾标点：60% 有标点，40% 无（无标点的尾巴会由 flush() 收尾）
        if rnd.random() < 0.6:
            txt += rnd.choice(_PUNCT[:3])
        segs.append(txt)
    return 'case_%03d' % rnd.randint(0, 999), segs


def main():
    t0 = time.time()
    rnd = random.Random(SEED)

    mod = A._load_translator_module()
    cr_mod = A._load_caption_render_from_source(
        io.open(os.path.join(APP_DIR, 'caption_render.py'),
                'rb').read().decode('utf-8'))

    cases = []
    bad = []
    max_draft_lines = 0
    for i in range(N_CASES):
        name, segs = _rand_case(rnd)
        try:
            run = A._drive(mod, cr_mod, segs, consumer_key='id', delay_s=0.002)
            st = A._stats(segs, run)
        except Exception as e:                                   # noqa: BLE001
            bad.append(dict(case=name, i=i, error=repr(e)))
            continue

        # ── 与 app127 同一套判据（本处只看硬指标）────────────────────
        errs = []
        if st['n_not_ready'] != 0:
            errs.append('final_not_ready=%d' % st['n_not_ready'])
        if st['n_draft_lines'] != 0:
            errs.append('final_draft_lines=%d' % st['n_draft_lines'])
        if st['missing_final_mt']:
            errs.append('missing_final_mt=%d' % len(st['missing_final_mt']))
        if st['dup_final_mt']:
            errs.append('dup_final_mt=%d' % len(st['dup_final_mt']))
        if st['residual_draft_mt']:
            errs.append('residual_draft_mt=%d' % len(st['residual_draft_mt']))
        if not st['same_id_ok']:
            errs.append('same_id_ok=False')
        if st['n_draft_uids_matched'] != st['n_draft_uids']:
            errs.append('draft_uid_mismatch=%d/%d'
                        % (st['n_draft_uids_matched'], st['n_draft_uids']))
        if not st['src_ok']:
            errs.append('src_not_conserved')
        if not st['ev_src_ok']:
            errs.append('ev_src_not_conserved')
        if st['n_none_text_total'] != 0:
            errs.append('none_text=%d' % st['n_none_text_total'])
        # 🔴 **中间态判据是「条件式」的**：
        #    只有**该语料确实出现过带草稿行的快照**时，「中间态草稿可见」才
        #    是硬要求；否则（例如只有 1 段、立即成稿）**压根没有草稿单元**
        #    ⇒ 「找不到中间态」是**语料形态**决定的、不是缺陷。
        if st['mid_expected']:
            if not st['mid_found']:
                errs.append('no_mid_snapshot')
            elif st['mid_n_draft_nonempty'] < 1:
                errs.append('mid_draft_not_visible')
        if st['mid_missing_ready']:
            errs.append('mid_lost_ready=%d' % len(st['mid_missing_ready']))

        max_draft_lines = max(max_draft_lines, st['n_draft_lines'])
        rec = dict(case=name, i=i, n_segments=len(segs),
                   n_units=st['n_units'], n_finals=st['n_finals'],
                   n_drafts=st['n_drafts'], n_draft_lines=st['n_draft_lines'],
                   n_none_text_total=st['n_none_text_total'],
                   mid_expected=st['mid_expected'],
                   mid_found=st['mid_found'],
                   mid_n_draft_nonempty=st['mid_n_draft_nonempty'],
                   ok=(not errs), errs=errs)
        cases.append(rec)
        if errs:
            bad.append(rec)

    n_ok = sum(1 for c in cases if c['ok'])
    out = dict(
        script='app128_draft_lines_fuzz.py',
        purpose=('MT notice 15 §3.4「真实时序下不残留草稿行」的随机语料'
                 '模糊测试加固（app127 的三组手写语料之外的补充）'),
        generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        python=sys.version,
        seed=SEED,
        n_cases=N_CASES,
        n_pass=len(cases) - len(bad),
        n_fail=len(bad),
        max_draft_lines=max_draft_lines,
        elapsed_s=round(time.time() - t0, 2),
        no_model_loaded=True,
        no_machine_lock=True,
        failures=bad,
        cases=cases,
    )
    path = os.path.join(HERE, 'app128_draft_lines_fuzz_evidence.json')
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))

    print('cases=%d  PASS=%d  FAIL=%d  max_draft_lines=%d  (%.1fs)'
          % (len(cases), out['n_pass'], out['n_fail'],
             max_draft_lines, out['elapsed_s']))
    if bad:
        for b in bad[:10]:
            print('  FAIL:', json.dumps(b, ensure_ascii=False))
    print('证据已写', path)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
