# -*- coding: utf-8 -*-
"""APP-075(a)(b)(c) 登记门槛的**离线自检**（纯 CPU / 只读，不加载模型、不占设备）。

## 目的
证明四件事：
1. **门槛会挡住「切换边界那一段」**（APP-075(a)）⇒ 不会用错人的音频登记；
2. **判据非恒真**（拿**已知有缺陷的旧行为**跑 ⇒ 必须 FAIL）；
3. **低 conf 不阻塞该说话人**（APP-075(b)）⇒ 有合格段后仍能登记（升级）；
4. **登记稳定期**（`REG_SETTLE_S`）能让**流式**下也选到**对的人**（APP-075(c)）。

## 🔴🔴🔳 数据来源（**真实故障数据**，不是构造夹具）
`results/app/_app293_label_overlap.json`（app293 设备实测：逐段 spk / conf / 实测 F0）

## 🔴🔴🔳 为什么「最长合格段」是**唯一**能选对人的策略（实测硬证据）
同一标签 `S2` 的 conf 与守卫**都挡不住**女声：

| 段 | 时间 | `spk_conf` | 切换点守卫 | 真实性别（F0） |
|---|---|---|---|---|
| seg1 | 9.6–19.2 | 0.1292 | ✗ 被挡 | 女 197.53 Hz |
| seg2 | 19.2–25.6 | **0.8996** | ✗ **挡不住** | **女 175.82 Hz** |
| seg3 | 25.6–32.0 | **0.9104** | ✗ **挡不住** | **女 188.24 Hz** |
| seg5 | 38.4–44.8 | 0.4016 | ✗ 挡不住 | 男 108.84 Hz |
| seg6–seg14 | 44.8–102.4 | 0.73–0.95 | ✗ 挡不住 | **男 100–135 Hz** |

⇒ 切换点在 **9.6 s**（S1→S2）⇒ seg2/seg3（19.2–32.0 s）**远离**切换点
⇒ **conf 门槛与守卫都拦不住它们** ⇒ 「先来先登记」⇒ 登记到**女声**
⇒ 之后所有该标签句子（含真男声）都用女声播出 ⇒ **这就是 APP-071 现象**。
⇒ **只有「最长合格段」（男声 57.6 s vs 女声 12.8 s）能选对人**。

## 🔴🔴🔳 但「最长」在**流式**下不够 ⇒ 必须加「登记稳定期」
流式下 seg6 到手时，最长合格段**仍是**女声的 12.8 s ⇒ 仍会登记女声
⇒ 必须**等合格段集合不再增长**（`REG_SETTLE_S`）⇒ 再取当时的最长。

## 用法
```
python results/app/_app294_gate_selftest.py
```
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import speaker_voice as sv                                  # noqa: E402

EV = os.path.join(HERE, '_app293_label_overlap.json')
OUT = os.path.join(HERE, '_app294_gate_selftest.json')

# 🔴 判据常量（全部来自 APP-075(a) 原文 + 自拟的稳定期）
REG_CONF_MIN = sv.REG_CONF_MIN
REG_MIN_CONT_S = sv.REG_MIN_CONT_S
SWITCH_GUARD_S = sv.SWITCH_GUARD_S


def load_rows():
    d = json.load(open(EV, encoding='utf-8'))
    rows = []
    for r in d['per_seg']:
        rows.append(dict(seg=int(r['seg']), t0=float(r['t0']), t1=float(r['t1']),
                         spk=str(r['app_spk']), conf=float(r['app_conf']),
                         f0=float(r['measured_f0_median']),
                         cls=r.get('measured_class')))
    rows.sort(key=lambda r: (r['t0'], r['seg']))
    return rows, d


def build_table(rows, use_conf=True, use_guard=True):
    """按**旧行为**或**新门槛**建表。

    🔴 `use_conf=False` / `use_guard=False` ⇒ 模拟**改前**的行为
    ⇒ 用它做**反证**（判据必须能识破旧缺陷）。

    🔴🔴🔳 **`use_conf=False` 的语义必须精确**：
    旧行为是「**完全不看 conf**」⇒ 那一段的 conf **不是低**，而是
    「**没有这个概念**」⇒ 本脚本用 `spk_conf=None` 表达。
    ⇒ 🔴 **注意**：`_qualified_runs_locked` 对 `conf is None` 的段
      **一律拒绝**（无法判定 ⇒ 不许登记）⇒ 所以「无 conf」组会**全军覆没**，
      **不能**用来当反证（它证明的是「缺信息 ⇒ 不登记」，不是「旧行为更差」）。
    ⇒ 反证必须用「**有 conf 门槛、但没有边界守卫**」这一档
      （只拆**一个**变量 ⇒ 反证组才可能命中真实的旧缺陷）。
    """
    t = sv.SpeakerVoiceTable()
    for r in rows:
        conf = float(r['conf']) if use_conf else None
        t.note_final(r['seg'], r['spk'], [(r['t0'], r['t1'])], conf)
    if not use_guard:
        # 模拟「没有边界守卫」：把切换点清空
        with t._lock:
            del t._switch_points[:]
    return t


def runs_of(t, spk):
    return t.qualified_runs(spk)


def f0_of_used(rows, segs):
    f0s = [r['f0'] for r in rows if r['seg'] in segs]
    if not f0s:
        return None, None, None
    s = sorted(f0s)
    return round(s[len(s) // 2], 2), round(max(s), 2), round(min(s), 2)


def main():
    rows, raw = load_rows()
    out = {'script': os.path.basename(__file__),
           'correction': 'APP-075(a)(b)(c) 登记门槛自检',
           'criteria': {
               'reg_conf_min': REG_CONF_MIN,
               'reg_min_cont_s': REG_MIN_CONT_S,
               'switch_guard_s': SWITCH_GUARD_S,
           },
           'input': {'path': EV, 'n_seg': len(rows)}}

    # ── ① 新门槛：每个 spk 的合格段 ─────────────────────────────
    t_new = build_table(rows, use_conf=True, use_guard=True)
    new_runs = {}
    for spk in sorted(set(r['spk'] for r in rows)):
        rr = runs_of(t_new, spk)
        segs = set()
        for x in rr:
            segs.update(x['segs'])
        med, mx, mn = f0_of_used(rows, segs)
        new_runs[spk] = {
            'n_runs': len(rr),
            'runs': rr,
            'segs_used': sorted(segs),
            'f0_median_of_used': med, 'f0_max_of_used': mx, 'f0_min_of_used': mn,
        }
    out['new_gate'] = new_runs

    # ── ② 反证组：**有 conf 门槛、无边界守卫**（只拆一个变量）──
    t_ng = build_table(rows, use_conf=True, use_guard=False)
    noguard_runs = {}
    for spk in sorted(set(r['spk'] for r in rows)):
        rr = runs_of(t_ng, spk)
        segs = set()
        for x in rr:
            segs.update(x['segs'])
        med, mx, mn = f0_of_used(rows, segs)
        noguard_runs[spk] = {
            'n_runs': len(rr), 'segs_used': sorted(segs),
            'f0_median_of_used': med, 'f0_max_of_used': mx,
        }
    out['counterproof_no_guard'] = noguard_runs

    # ── ③ 「旧行为」参照组（完全不看 conf）────────────────────
    t_old = build_table(rows, use_conf=False, use_guard=False)
    old_runs = {}
    for spk in sorted(set(r['spk'] for r in rows)):
        rr = runs_of(t_old, spk)
        segs = set()
        for x in rr:
            segs.update(x['segs'])
        old_runs[spk] = {'n_runs': len(rr), 'segs_used': sorted(segs)}
    out['old_behavior_no_conf'] = old_runs

    # ── ④ 判据 ────────────────────────────────────────────────
    checks = []

    def add(name, verdict, detail):
        checks.append(dict(name=name, verdict=bool(verdict), detail=detail))

    # 判据①：**S2 的合格段不得包含 seg1**（conf 0.1292 ⇒ 被 conf 门槛挡）
    s2_segs = set(new_runs['S2']['segs_used'])
    bad1 = s2_segs & {1}
    add('S2 合格段不含 seg1（conf=0.1292 被 conf 门槛挡住）',
        not bad1,
        {'used': sorted(s2_segs), 'forbidden_hit': sorted(bad1)})

    # 判据②：**S2 合格段不得包含 seg4/seg5**（conf 0.3757/0.4016 < 0.5）
    bad2 = s2_segs & {4, 5}
    add('S2 合格段不含 seg4/seg5（conf 0.3757/0.4016 < REG_CONF_MIN=0.5）',
        not bad2,
        {'used': sorted(s2_segs), 'forbidden_hit': sorted(bad2)})

    # 判据③：**登记票选中的段必须是男声**（F0 全部 < 160 Hz）
    #   🔴 这才是「有没有用错人的音频登记」的**直接判据**
    #   （判据①只挡 seg1；seg2/seg3 的女声**只能靠择段策略**挡住）
    t_tk = build_table(rows, use_conf=True, use_guard=True)
    tk_ranges, tk_key = t_tk.registration_ticket('S2')
    tk_segs = set()
    for r in runs_of(t_tk, 'S2'):
        if (r['a'], r['b']) == tuple(tk_ranges[0]) if tk_ranges else False:
            tk_segs.update(r['segs'])
    tk_med, tk_mx, tk_mn = f0_of_used(rows, tk_segs)
    add('【核心】S2 登记票选中的段实测 F0 全部 < 160 Hz（= 男声，不是女声）',
        bool(tk_ranges) and tk_mx is not None and tk_mx < 160.0,
        {'ticket': tk_ranges, 'ticket_key': tk_key,
         'ticket_segs': sorted(tk_segs),
         'f0_median': tk_med, 'f0_max': tk_mx, 'f0_min': tk_mn})

    # 判据④：**反证**：去掉「最长择段」（改回「先来先登记」）必须 FAIL
    #   🔴 反证构造：**只拆一个变量** ⇒ 把择段策略换回「最早的那段」
    #   ⇒ 若判据③仍 PASS ⇒ 判据恒真 ⇒ 无效。
    t_first = build_table(rows, use_conf=True, use_guard=True)
    rr_all = runs_of(t_first, 'S2')
    first_seg = set(rr_all[0]['segs']) if rr_all else set()
    f_med, f_mx, f_mn = f0_of_used(rows, first_seg)
    add('【反证】「先来先登记」会选中女声段 ⇒ 判据③能识破旧缺陷（非恒真）',
        bool(rr_all) and f_mx is not None and f_mx >= 160.0,
        {'first_run': rr_all[0] if rr_all else None,
         'first_segs': sorted(first_seg),
         'f0_median': f_med, 'f0_max': f_mx,
         'note': 'f0_max ≥ 160 ⇒ 「先来先登记」用错人 ⇒ 判据③ FAIL ⇒ 非恒真'})

    # 判据⑤：**S2 仍然能登记**（APP-075(b)：门槛不能把说话人彻底挡住）
    add('S2 仍有合格段 ⇒ 可登记（不被门槛彻底挡住）',
        new_runs['S2']['n_runs'] > 0,
        {'n_runs': new_runs['S2']['n_runs']})

    # 判据⑥：**S1/S3/S4 仍能登记**（其它说话人不受门槛误伤）
    add('S1/S3/S4 仍有合格段',
        new_runs['S1']['n_runs'] > 0 and new_runs['S3']['n_runs'] > 0
        and new_runs['S4']['n_runs'] > 0,
        {k: new_runs[k]['n_runs'] for k in ('S1', 'S2', 'S3', 'S4')})

    # 判据⑦：**没有合格段 ⇒ ticket 为空**（APP-075(b)：不得用不合格段登记）
    t_empty = sv.SpeakerVoiceTable()
    t_empty.note_final(0, 'S9', [(0.0, 9.0)], 0.01)     # 极低 conf
    rr, kk = t_empty.registration_ticket('S9')
    add('【APP-075(b)】无合格段 ⇒ registration_ticket 为空（⇒ 回落预设 A）',
        rr == [] and kk is None, {'ranges': rr, 'key': kk})

    # 判据⑧：**升级语义**（APP-075(b)）：登记过的 spk 遇到**更长的**合格段
    #   ⇒ ticket 必须换成更长的那段（覆盖旧登记）
    #   🔴 构造：必须**从空表开始**，先只喂 early 段 ⇒ 再喂 late 段
    #   （若先喂全部 rows，最长段从一开始就是 late ⇒ 测不到升级）。
    t_up = sv.SpeakerVoiceTable()
    early = [r for r in rows if r['spk'] == 'S2' and r['seg'] in (2, 3)]
    for r in early:
        t_up.note_final(r['seg'], r['spk'], [(r['t0'], r['t1'])], r['conf'])
    rr0, k0 = t_up.registration_ticket('S2')
    if rr0:
        t_up.mark_registered('S2', rr0[0][0], rr0[0][1])
    late = [r for r in rows if r['spk'] == 'S2' and r['seg'] in (6, 7, 8)]
    for r in late:
        t_up.note_final(r['seg'], r['spk'], [(r['t0'], r['t1'])], r['conf'])
    rr1, k1 = t_up.registration_ticket('S2')
    old_reg = t_up.reg_run_of('S2')
    add('【升级】出现更长的合格段 ⇒ 登记票随之升级（覆盖旧登记）',
        bool(rr0) and bool(rr1) and (rr1[0][1] - rr1[0][0]) > (rr0[0][1] - rr0[0][0]),
        {'early': rr0, 'early_key': k0, 'late': rr1, 'late_key': k1,
         'prev_reg_run': old_reg})

    # 判据⑧b：**没有更长合格段 ⇒ 不给票**（避免反复重登记 ⇒ 算力不受控）
    t_no = sv.SpeakerVoiceTable()
    for r in early:
        t_no.note_final(r['seg'], r['spk'], [(r['t0'], r['t1'])], r['conf'])
    rx, kx = t_no.registration_ticket('S2')
    if rx:
        t_no.mark_registered('S2', rx[0][0], rx[0][1])
    rx2, kx2 = t_no.registration_ticket('S2')     # 同一批段再问一次
    add('【幂等】已登记且合格段没变长 ⇒ 不再给票（不重复登记）',
        bool(rx) and rx2 == [] and kx2 is None,
        {'first': rx, 'first_key': kx, 'second': rx2, 'second_key': kx2})

    # 判据⑨：**流式升级路径**（APP-075(b)）：逐段喂入（流式），
    #   每段都问「现在该登记哪一段」；登记后 `mark_registered`。
    #   🔴 关键：登记票**必须最终指向男声**（= 男声那段最长）
    #   ⇒ 这验证「最长优先 + 变长即升级」在**流式**下也能收敛到对的人。
    t_stream = sv.SpeakerVoiceTable()
    trace = []
    for r in rows:
        t_stream.note_final(r['seg'], r['spk'], [(r['t0'], r['t1'])], r['conf'])
        rng, key = t_stream.registration_ticket('S2')
        if r['spk'] != 'S2' or not rng:
            continue
        segs = set()
        for x in runs_of(t_stream, 'S2'):
            if (x['a'], x['b']) == tuple(rng[0]):
                segs.update(x['segs'])
        med, mx, mn = f0_of_used(rows, segs)
        trace.append(dict(seg=r['seg'], ticket=rng, segs=sorted(segs),
                          f0_max=mx, f0_median=med))
        # 模拟生产：登记成功 ⇒ 记下这一段
        t_stream.mark_registered('S2', rng[0][0], rng[0][1])
    out['stream_trace'] = trace
    last = trace[-1] if trace else None
    add('【流式】流式喂入 ⇒ 登记票最终指向**男声**段（F0 < 160 Hz）',
        last is not None and last.get('f0_max') is not None
        and last['f0_max'] < 160.0,
        {'n_tickets': len(trace),
         'first_ticket': trace[0] if trace else None,
         'last_ticket': last,
         'all_tickets': trace})

    # 判据⑩：**升级必须发生**（流式下男声段出现时票要换）
    #   ⇒ 若全程只有一张票 ⇒ 说明「变长即升级」没生效 ⇒ 判据⑨是假通过。
    add('【升级·流式】出现更长合格段时票会更换（≥2 张不同的票）',
        len(trace) >= 2 and trace[0]['ticket'] != trace[-1]['ticket'],
        {'n_tickets': len(trace),
         'distinct': sorted({str(x['ticket']) for x in trace})})

    out['checks'] = checks
    out['n_pass'] = sum(1 for c in checks if c['verdict'])
    out['n_fail'] = sum(1 for c in checks if not c['verdict'])
    out['verdict'] = 'PASS' if out['n_fail'] == 0 else 'FAIL'

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for c in checks:
        print('[%s] %s  %s' % ('PASS' if c['verdict'] else 'FAIL',
                               c['name'],
                               json.dumps(c['detail'], ensure_ascii=False)[:400]))
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (out['n_pass'], out['n_fail'], out['verdict']))
    print('[evidence] %s' % OUT)
    return 0 if out['n_fail'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
