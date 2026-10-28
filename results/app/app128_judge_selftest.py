#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app128 反向检验 —— 证明「修正后的宽松判据」**仍然能抓出真缺陷**。

====================================================================
🔴🔴 为什么必须做这一步
====================================================================
app128 首跑 120 组里报 42 组 FAIL ⇒ 逐案复现后确认：**根因是判据口径缺陷**
（渲染层把同 seg 的多个翻译单元用 `' '.join` **拼成一行**
 ⇒ 「单元译文 == 整行」的精确相等口径 ⇒ 假 FAIL），
于是把 R4/R9 从**精确相等**放宽成**子串包含**。

🔴🔴🔴 **但放宽判据有风险**：可能把**真缺陷**也一起放过
（「改成永远 PASS」是验收脚本最危险的退化方向）。

⇒ 本脚本做**双向反证**：
  ① **注入真缺陷** ⇒ 修正后的判据**必须 FAIL**（能抓出）；
  ② **不注入** ⇒ 修正后的判据**必须 PASS**（不放水）。

注入的缺陷（都是**真实存在过的**缺陷形态）：
  · **I1**：正式稿译文**丢失**（`mt` 被清空）⇒ R4 必须 FAIL；
  · **I2**：正式稿译文**重复显示**（同一译文出现在两行）⇒ R4 必须 FAIL；
  · **I3**：中间态**丢掉了已就绪的正式稿**（§47 老坑）⇒ R9 必须 FAIL；
  · **I4**：中间态草稿**取不到译文**（D3 口径）⇒ R8 必须 FAIL。

⇒ **全部在内存中独立重建模块**，**不改动工作区任何文件**。
"""

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP_DIR = os.path.join(REPO, 'live_caption')

sys.path.insert(0, HERE)
import app127_c111_real_timing_draft_lines as A   # noqa: E402

_RESULTS = []


def check(group, name, ok, detail=''):
    _RESULTS.append(dict(group=group, name=name, ok=bool(ok),
                          detail=str(detail)[:400]))
    print('  [%s] %s %s  <- %s' % (group, 'PASS' if ok else 'FAIL',
                                   name, str(detail)[:200]))


def main():
    mod = A._load_translator_module()
    cr_path = os.path.join(APP_DIR, 'caption_render.py')
    cr_src = io.open(cr_path, 'rb').read().decode('utf-8')
    cr_mod = A._load_caption_render_from_source(cr_src)

    corpora = A.CORPORA
    base = {}
    for name, segs in corpora.items():
        base[name] = A._stats(segs, A._drive(mod, cr_mod, segs))

    # ── ② 基准：不注入 ⇒ 修正后的判据必须全 PASS ────────────────────
    print('\n--- 基准（不注入缺陷）---')
    check('BASE', 'B0 修正后判据在无缺陷时必须全 PASS',
          all(s['n_not_ready'] == 0 and not s['missing_final_mt']
              and not s['dup_final_mt'] and not s['mid_missing_ready']
              and s['n_none_text_total'] == 0
              and (s['mid_found'] and s['mid_n_draft_nonempty'] > 0
                   if s['mid_expected'] else not s['mid_found'])
              for s in base.values()),
          '; '.join('%s: miss=%d dup=%d midmiss=%d none=%d'
                    % (n, len(base[n]['missing_final_mt']),
                       len(base[n]['dup_final_mt']),
                       len(base[n]['mid_missing_ready']),
                       base[n]['n_none_text_total']) for n in corpora))

    # ── ① I1：正式稿译文**丢失** ⇒ R4 必须 FAIL ─────────────────────
    #    注入点：`_drive` 结束后把某个正式单元的 `mt` 清空 ⇒
    #    「单元有 mt 但渲染里找不到」⇒ 命中 `missing_final_mt`。
    print('\n--- I1 注入：正式稿译文丢失 ---')
    i1_hit = []
    for name, segs in corpora.items():
        run = A._drive(mod, cr_mod, segs)
        # 改渲染层：把「就绪的正式稿」从渲染里**剔除**（模拟译文丢失）
        cr_i1 = A._load_caption_render_from_source(A._mutate(
            cr_src,
            """        seg = u.get('seg')
        txt = u.get('mt')
        if not txt:
            continue
        mt_by_seg.setdefault(seg, []).append(txt)""",
            """        seg = u.get('seg')
        txt = u.get('mt')
        if not txt:
            continue
        if u.get('_drop'):
            continue
        mt_by_seg.setdefault(seg, []).append(txt)"""))
        units = [dict(u) for u in run['final']['units']]
        for u in units:
            if (u.get('kind') or 'final') != 'draft' and u.get('mt'):
                u['_drop'] = True
                break
        lines = cr_i1.render_lines(segs, units, granularity='seg',
                                   show_pending=False,
                                   seg_carry=getattr(run['svc'], 'seg_carry',
                                                     None) or {})
        mt_texts = [A._norm_mt(l['text']) for l in lines
                    if l['kind'] in ('mt', 'mt_draft')
                    and l['text'] is not None]
        lost = [u.get('mt') for u in units
                if (u.get('kind') or 'final') != 'draft'
                and u.get('mt') and not any(u['mt'] in t for t in mt_texts)]
        if lost:
            i1_hit.append(name)
    check('I1', 'I1 注入「正式稿译文丢失」⇒ 修正后的 R4 必须 FAIL（能抓出）',
          len(i1_hit) >= 1,
          '命中语料: %s ‖ 未注入时各语料 miss: %s'
          % (i1_hit or '无',
             {n: len(base[n]['missing_final_mt']) for n in corpora}))

    # ── ① I2：正式稿译文**重复显示** ⇒ R4 必须 FAIL ─────────────────
    print('\n--- I2 注入：正式稿译文重复显示 ---')
    i2_hit = []
    for name, segs in corpora.items():
        run = A._drive(mod, cr_mod, segs)
        units = [dict(u) for u in run['final']['units']]
        finals = [u for u in units
                  if (u.get('kind') or 'final') != 'draft' and u.get('mt')]
        if not finals:
            continue
        victim = finals[0]
        # 让**另一条**正式单元也渲染出**同一条**译文 ⇒ 同一译文出现 2 次
        for u in units:
            if (u.get('kind') or 'final') != 'draft' and u is not victim:
                u['mt'] = victim['mt']
                break
        lines = cr_mod.render_lines(segs, units, granularity='seg',
                                    show_pending=False,
                                    seg_carry=getattr(run['svc'], 'seg_carry',
                                                      None) or {})
        mt_texts = [A._norm_mt(l['text']) for l in lines
                    if l['kind'] in ('mt', 'mt_draft')
                    and l['text'] is not None]
        dup = {t: sum(1 for x in mt_texts if t in x) for t in mt_texts}
        dup = {t: c for t, c in dup.items() if c > 1}
        if dup:
            i2_hit.append(name)
    check('I2', 'I2 注入「正式稿译文重复显示」⇒ 修正后的 R4 必须 FAIL（能抓出）',
          len(i2_hit) >= 1,
          '命中语料: %s ‖ 未注入时各语料 dup: %s'
          % (i2_hit or '无',
             {n: len(base[n]['dup_final_mt']) for n in corpora}))

    # ── ① I3：中间态**丢掉了已就绪的正式稿**（§47 老坑）⇒ R9 必须 FAIL ──
    print('\n--- I3 注入：中间态丢掉已就绪的正式稿 ---')
    cr_i3 = A._load_caption_render_from_source(A._mutate(
        cr_src,
        """        if not txt:
            continue
        mt_by_seg.setdefault(seg, []).append(txt)""",
        """        if not txt:
            continue
        if u.get('_hide'):
            continue
        mt_by_seg.setdefault(seg, []).append(txt)"""))
    i3_hit = []
    for name, segs in corpora.items():
        run = A._drive(mod, cr_mod, segs)
        st = A._stats(segs, run)
        if not st['mid_found']:
            continue
        # 直接用**突变后的渲染层**重放中间态快照的 units
        mid_snap = None
        for snap in run['snapshots']:
            if snap['n_draft_lines'] <= 0:
                continue
            s_units = snap['units']
            s_finals = [u for u in s_units
                        if (u.get('kind') or 'final') != 'draft']
            if any(u.get('mt') for u in s_finals):
                mid_snap = snap
                break
        if mid_snap is None:
            continue
        units = [dict(u) for u in mid_snap['units']]
        hid = False
        for u in units:
            if (u.get('kind') or 'final') != 'draft' and u.get('mt'):
                u['_hide'] = True
                hid = True
                break
        if not hid:
            continue
        lines = cr_i3.render_lines(segs, units, granularity='seg',
                                   show_pending=False,
                                   seg_carry=getattr(run['svc'], 'seg_carry',
                                                     None) or {})
        mid_txts = [A._norm_mt(l['text']) for l in lines
                    if l['kind'] in ('mt', 'mt_draft')
                    and l['text'] is not None]
        lost = [u.get('mt') for u in units
                if (u.get('kind') or 'final') != 'draft'
                and u.get('mt') and not any(u['mt'] in t for t in mid_txts)]
        if lost:
            i3_hit.append(name)
    check('I3', 'I3 注入「中间态丢掉已就绪的正式稿」⇒ 修正后的 R9 必须 FAIL（能抓出）',
          len(i3_hit) >= 1,
          '命中语料: %s ‖ 未注入时各语料 midmiss: %s'
          % (i3_hit or '无',
             {n: len(base[n]['mid_missing_ready']) for n in corpora}))

    # ── ① I4：中间态草稿**取不到译文**（D3 口径）⇒ R8 必须 FAIL ─────
    #    🔴🔴 **前提口径修正（首跑 FAIL 自查抓出）**：
    #    「消费者按去重键存草稿」时，草稿译文为空
    #    ⇒ 渲染层 `if d.get('mt'):` 不成立 ⇒ **压根不生成草稿行**
    #    ⇒ 注入后的 `mid_expected` 变成 False
    #    ⇒ **不能用注入后的值做前提** ⇒ 必须用**基线（正常口径）**的
    #    `mid_expected` 来判「这个语料**本来应该有**中间态」。
    print('\n--- I4 注入：中间态草稿取不到译文 ---')
    i4_hit = []
    i4_detail = []
    for name, segs in corpora.items():
        if not base[name]['mid_expected']:
            i4_detail.append('%s: 基线本就无中间态（跳过）' % name)
            continue
        st = A._stats(segs, A._drive(mod, cr_mod, segs,
                                     consumer_key='dedup'))
        # 注入后：草稿行**要么整个消失**（mid_found=False）、
        #        **要么在但没有译文**（mid_n_draft_nonempty=0）
        broken = (not st['mid_found']) or (st['mid_n_draft_nonempty'] < 1)
        i4_detail.append('%s: mid_found=%s nonempty=%d'
                         % (name, st['mid_found'],
                            st['mid_n_draft_nonempty']))
        if broken:
            i4_hit.append(name)
    check('I4', 'I4 注入「消费者按去重键存草稿」⇒ 修正后的 R8 必须 FAIL（能抓出）',
          len(i4_hit) >= 1,
          '命中语料: %s ‖ 明细: %s ‖ 基线 midnonempty: %s'
          % (i4_hit or '无', '; '.join(i4_detail),
             {n: base[n]['mid_n_draft_nonempty'] for n in corpora}))

    n_pass = sum(1 for r in _RESULTS if r['ok'])
    n_fail = sum(1 for r in _RESULTS if not r['ok'])
    print('\n' + '=' * 70)
    print('PASS %d / FAIL %d' % (n_pass, n_fail))
    print('=' * 70)

    import json
    import time
    out = dict(script='app128_judge_selftest.py',
               purpose=('证明「为适配渲染层 join 语义而放宽后的判据」'
                        '**仍然能抓出真缺陷**（防止验收脚本退化成永远 PASS）'),
               generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
               python=sys.version,
               n_pass=n_pass, n_fail=n_fail, checks=_RESULTS)
    path = os.path.join(HERE, 'app128_judge_selftest_evidence.json')
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
    print('证据已写 %s' % path)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
