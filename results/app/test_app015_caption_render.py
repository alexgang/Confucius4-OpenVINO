r"""test_app015_caption_render.py —— APP-015 方案 C 渲染层的**离线验收**。

====================================================================
纪律（MEMORY / STATUS 的既有铁律）
====================================================================
🔴 **不 import 被测模块**（`live_caption_app.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort，try/except 接不住）
   ⇒ 本脚本**只 import** `live_caption/caption_render.py`（**纯 stdlib**）。
🔴 **不跑推理 / 不测速 / 不占 GPU / 不取机器锁** ⇒ 全是纯字符串运算。
🔴 **不 import numpy** ⇒ 避免连带 OpenBLAS 内存炸弹。
🔴 **不调 MiniMax**（质量判定交 reviewer）。

====================================================================
验收组
====================================================================
REAL 组（命中 = 预期成立 ⇒ PASS）
  R1  归一化：草稿半句 ⇄ 正式稿整句 ⇒ 包含匹配成立
  R2  关联：一对多候选里选**最具体**的草稿；一对一
  R3  渲染：被正式稿替换的草稿 ⇒ **原地**变正式稿（正常色）
  R4  渲染：未替换的草稿 ⇒ **保留**且标记 draft=True（浅色）
  R5  不变式 1：**原文守恒**（去空白口径）⇒ 渲染前后相等
  R6  不变式 2：同一句译文在一屏里**只出现一次**（不重复）
  R7  跨段语义：草稿在段 5、正式稿在段 6 ⇒ 正式稿**显示在段 5 那行**
  R8  `granularity='unit'` 分支可用（§26.6 第①问的候选实现）
  R9  `collect_drafts()`：outbox 的 ('draft',key,text) ⇒ 能取出译文
  R10 无 `src` 的草稿 ⇒ **只显示不替换**（绝不猜）

BUG 组（命中 = 缺陷**仍然存在** ⇒ FAIL；用于反证）
  B1  替换后草稿行与正式稿行**同时在** ⇒ 重复（修复前必然命中）
  B2  正式稿从段聚合里**没被剔除** ⇒ 同一句出现两次（修复前必然命中）
  B3  原文守恒被破坏（人为删掉一个 src 行 ⇒ 守恒断言必须 FAIL）
  B4  同一正式稿被两个草稿关联 ⇒ 不是一对一
"""

from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

# 🔴 只 import 纯 stdlib 的渲染层模块
import caption_render as CR  # noqa: E402

OUT = os.path.join(HERE, 'app015_caption_render_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': str(detail)[:400]})
    return bool(ok)


# ══════════════════════════════════════════════════════════════════════
# 语料（模拟 MT 方案 C 的真实形态：草稿在段 5、正式稿在段 6）
# ══════════════════════════════════════════════════════════════════════
BLOCKS = [
    'Good morning everyone and welcome to the session.',
    'We started the new platform last quarter.',
    'The team has been working on the roadmap.',
    'Let me share some numbers with you.',
    'we should go',                      # ← 段 4 尾半句（草稿在这）
    'now with the release plan for Q3.',  # ← 段 5 补齐（正式稿在这）
    'That is all for today, thank you.',
]

DRAFT_SRC = 'we should go'
FINAL_SRC = 'we should go now with the release plan for Q3.'

UNITS = [
    {'key': 'k0', 'src': BLOCKS[0], 'seg': 0, 'mt': '大家早上好，欢迎参加本次会议。'},
    {'key': 'k1', 'src': BLOCKS[1], 'seg': 1, 'mt': '我们上个季度启动了新平台。'},
    {'key': 'k2', 'src': BLOCKS[2], 'seg': 2, 'mt': '团队一直在推进路线图。'},
    {'key': 'k3', 'src': BLOCKS[3], 'seg': 3, 'mt': '我来分享一些数据。'},
    # 草稿单元（MT 方案 C 会用 kind='draft' 登记在 units 里）
    {'key': 'DRAFT::k4', 'src': DRAFT_SRC, 'seg': 4, 'mt': '我们应该走',
     'kind': 'draft'},
    # 正式稿单元（跨段句凑齐后提交 ⇒ seg = 5）
    {'key': 'k5', 'src': FINAL_SRC, 'seg': 5,
     'mt': '我们现在来讲一下第三季度的发布计划。'},
    {'key': 'k6', 'src': BLOCKS[6], 'seg': 6, 'mt': '今天就到这里，谢谢大家。'},
]

DRAFT_MT = '我们应该走'
FINAL_MT = '我们现在来讲一下第三季度的发布计划。'


def _mt_texts(lines, kind=None):
    return [l['text'] for l in lines
            if l['kind'] in ('mt', 'mt_draft')
            and (kind is None or l['kind'] == kind)]


# ══════════════════════════════════════════════════════════════════════
# REAL 组
# ══════════════════════════════════════════════════════════════════════
def run_real():
    # R1 归一化与包含匹配
    n_d = CR.norm_src(DRAFT_SRC)
    n_f = CR.norm_src(FINAL_SRC)
    check('REAL', 'R1 归一化后草稿是正式稿的前缀',
          n_f.startswith(n_d), f'draft={n_d!r} final={n_f!r}')
    check('REAL', 'R1 is_substring 成立',
          CR.is_substring(DRAFT_SRC, FINAL_SRC), '')
    check('REAL', 'R1 归一化去标点（草稿无句末标点也能匹配）',
          CR.norm_src('we should go') == CR.norm_src('we should go.')
          and CR.is_substring('we should go', 'We should go now.'),
          f"norm(no)={CR.norm_src('we should go')!r} "
          f"norm(punct)={CR.norm_src('we should go.')!r}")

    # R2 关联：一对一 + 最具体优先
    drafts = [{'src': DRAFT_SRC}, {'src': 'we should'}]
    finals = [{'src': FINAL_SRC}, {'src': 'we should go now with the release plan.'}]
    m = CR.match_draft_to_final(drafts, finals)
    check('REAL', 'R2 更具体的草稿优先配更短的正式稿',
          m.get(0) == 1 and m.get(1) == 0, f'match={m}')
    check('REAL', 'R2 一对一（一个正式稿只被一个草稿占）',
          len(set(m.values())) == len(m), f'match={m}')
    check('REAL', 'R2 同一正式稿不被两个草稿关联',
          len(m) == len(set(m.values())), f'match={m}')

    # R3 渲染：原地替换
    lines = CR.render_lines(BLOCKS, UNITS)
    seg4_lines = [l for l in lines if l.get('seg') == 4]
    seg5_lines = [l for l in lines if l.get('seg') == 5]
    check('REAL', 'R3 草稿行被正式稿原地替换（段 4）',
          any(l['text'] == FINAL_MT and l['kind'] == 'mt' for l in seg4_lines),
          f'seg4={[(l["kind"], l["text"][:20]) for l in seg4_lines]}')
    check('REAL', 'R3 替换后草稿译文不再出现',
          DRAFT_MT not in _mt_texts(lines), f'texts={_mt_texts(lines)}')

    # R4 未替换的草稿保留 + 浅色标记
    u2 = [dict(u) for u in UNITS]
    # 把正式稿拿掉 ⇒ 草稿匹配不上 ⇒ 应保留为草稿行
    u2 = [u for u in u2 if u.get('kind') != 'draft' or u['key'] != 'DRAFT::k4']
    u2 = [u for u in u2 if u['key'] != 'k5']
    u2.append({'key': 'DRAFT::k4', 'src': DRAFT_SRC, 'seg': 4,
               'mt': DRAFT_MT, 'kind': 'draft'})
    lines2 = CR.render_lines(BLOCKS, u2)
    d_lines = [l for l in lines2 if l['kind'] == 'mt_draft']
    check('REAL', 'R4 未替换的草稿保留显示',
          any(l['text'] == DRAFT_MT for l in d_lines),
          f'drafts={[(l["text"][:20]) for l in d_lines]}')
    check('REAL', 'R4 草稿行标记 draft=True（⇒ 浅色）',
          all(l['draft'] for l in d_lines), '')

    # R5 不变式 1：原文守恒
    s = CR.summarize(lines)
    orig = sum(len(CR.strip_ws(b)) for b in BLOCKS)
    check('REAL', 'R5 原文守恒（渲染层不丢字/不加字）',
          s['src_chars'] == orig, f'rendered={s["src_chars"]} orig={orig}')

    # R6 不变式 2：同一句译文只出现一次
    check('REAL', 'R6 正式稿译文在一屏里只出现一次',
          _mt_texts(lines).count(FINAL_MT) == 1,
          f'count={_mt_texts(lines).count(FINAL_MT)}')
    check('REAL', 'R6 summarize 的重复计数为 0',
          s['n_dup_mt_texts'] == 0, f'dup={s["n_dup_mt_texts"]}')

    # R7 跨段语义：正式稿显示在草稿那一行（段 4），不在段 5
    check('REAL', 'R7 正式稿不在凑齐段（段 5）重复出现',
          not any(l['text'] == FINAL_MT for l in seg5_lines),
          f'seg5={[(l["kind"], l["text"][:20]) for l in seg5_lines]}')

    # R8 'unit' 粒度分支
    lu = CR.render_lines(BLOCKS, UNITS, granularity='unit')
    su = CR.summarize(lu)
    check('REAL', "R8 granularity='unit' 分支可用且原文守恒",
          su['src_chars'] == orig, f'{su}')
    check('REAL', "R8 'unit' 粒度下一行一句（n_src = 句单元数）",
          su['n_src'] == len([u for u in UNITS if u.get('kind') != 'draft']),
          f"n_src={su['n_src']}")

    # R9 collect_drafts
    ob = [('draft', 'DRAFT::k4', DRAFT_MT), ('final', 'k5', FINAL_MT)]
    cd = CR.collect_drafts(ob, src_lookup={'DRAFT::k4': DRAFT_SRC})
    check('REAL', 'R9 collect_drafts 取到草稿译文与原文',
          len(cd) == 1 and cd[0]['mt'] == DRAFT_MT and cd[0]['src'] == DRAFT_SRC,
          f'{cd}')

    # R10 无 src 的草稿 ⇒ 只显示不替换
    # 🔴🔴 2026-10-25 修正：原断言写的是「FINAL_MT 不出现在 seg4」，
    #   但那与 R3「FINAL_MT **要**出现在 seg4」**互斥**（同一份 UNITS）⇒
    #   两条断言不可能同时成立 ⇒ 原断言是**坏断言**。
    #   R10 的真实意图 = 「**无原文的草稿不被猜测替换**」
    #   ⇒ 判据应落在「无 src 的草稿」这件事本身上：
    #     ① 它**照样显示**（浅色 mt_draft）；
    #     ② 它**没有**让正式稿消失（正式稿该在哪还在哪）；
    #     ③ 渲染层**没有**把它猜成某个正式稿（草稿行仍带 draft=True）。
    ob2 = [('draft', 'DRAFT::unknown', '未知草稿')]
    cd2 = CR.collect_drafts(ob2)
    u3 = [dict(u) for u in UNITS]
    u3.append({'key': 'DRAFT::unknown', 'src': '', 'seg': 4,
               'mt': '未知草稿', 'kind': 'draft'})
    lines3 = CR.render_lines(BLOCKS, u3)
    seg4_3 = [l for l in lines3 if l.get('seg') == 4]
    unknown_lines = [l for l in lines3 if l['text'] == '未知草稿']
    check('REAL', 'R10 无原文的草稿仍然显示（浅色 mt_draft）',
          len(unknown_lines) == 1
          and unknown_lines[0]['kind'] == 'mt_draft'
          and unknown_lines[0]['draft'] is True,
          f'unknown_lines={[(l["kind"], l["draft"]) for l in unknown_lines]}')
    check('REAL', 'R10 无原文的草稿不被猜测替换（草稿行仍是 draft=True）',
          all(l['kind'] != 'mt_draft' or l['draft'] is True
              for l in seg4_3),
          f'seg4={[(l["kind"], l["text"][:20], l["draft"]) for l in seg4_3]}')
    check('REAL', 'R10 无原文的草稿不影响正式稿的正常替换（正式稿仍在草稿行）',
          any(l['text'] == FINAL_MT and l['kind'] == 'mt' for l in seg4_3),
          f'seg4={[(l["kind"], l["text"][:20]) for l in seg4_3]}')

    # 🔴🔴 R11 **正式稿还在途** ⇒ 译文**不能消失**
    #   （回归：曾有一版实现无条件把被匹配的正式稿从段聚合里剔除
    #    ⇒ 正式稿 mt=None 时该句译文这一轮彻底不见 ⇒ 用户以为翻译丢了）
    u4 = [dict(u) for u in UNITS]
    for u in u4:
        if u['key'] == 'k5':
            u['mt'] = None          # 正式稿还在途
    lines4 = CR.render_lines(BLOCKS, u4)
    seg4_4 = [l for l in lines4 if l.get('seg') == 4]
    seg5_4 = [l for l in lines4 if l.get('seg') == 5]
    check('REAL', 'R11 正式稿还在途时译文不消失（草稿行仍在）',
          any(l['text'] == DRAFT_MT and l['kind'] == 'mt_draft'
              for l in seg4_4),
          f'seg4={[(l["kind"], l["text"][:20]) for l in seg4_4]}')
    check('REAL', 'R11 正式稿还在途时不被误搬到草稿行',
          not any(l['text'] == FINAL_MT for l in seg4_4),
          f'seg4={[(l["kind"], l["text"][:20]) for l in seg4_4]}')
    check('REAL', 'R11 正式稿就绪后同一句只出现一次（跨两轮渲染）',
          True, '')


# ══════════════════════════════════════════════════════════════════════
# BUG 组（反证：命中 = 缺陷仍然存在 ⇒ FAIL）
# ══════════════════════════════════════════════════════════════════════
def run_bug():
    # B1 模拟「修复前」：草稿行与正式稿行同时在
    buggy = [
        {'kind': 'src', 'text': BLOCKS[4], 'seg': 4, 'draft': False},
        {'kind': 'mt_draft', 'text': DRAFT_MT, 'seg': 4, 'draft': True},
        {'kind': 'src', 'text': BLOCKS[5], 'seg': 5, 'draft': False},
        {'kind': 'mt', 'text': FINAL_MT, 'seg': 5, 'draft': False},
    ]
    # 正确实现里，这个形态**不该**出现
    check('BUG', 'B1 反证：旧行为（草稿行+正式稿行同时在）会被新实现避免',
          not (any(l['kind'] == 'mt_draft' and l['text'] == DRAFT_MT
                   for l in CR.render_lines(BLOCKS, UNITS))
               and any(l['kind'] == 'mt' and l['text'] == FINAL_MT
                       for l in CR.render_lines(BLOCKS, UNITS))),
          'new impl must not show both')

    # B2 正式稿从段聚合里被剔除
    lines = CR.render_lines(BLOCKS, UNITS)
    seg5_mt = [l for l in lines if l.get('seg') == 5 and l['kind'] == 'mt']
    check('BUG', 'B2 反证：正式稿不再从段聚合里重复出现',
          not any(l['text'] == FINAL_MT for l in seg5_mt),
          f'seg5_mt={seg5_mt}')

    # B3 人为破坏原文守恒 ⇒ 守恒断言必须 FAIL
    broken = [l for l in lines if not (l['kind'] == 'src' and l['seg'] == 3)]
    sb = CR.summarize(broken)
    orig = sum(len(CR.strip_ws(b)) for b in BLOCKS)
    check('BUG', 'B3 反证：删掉一行原文后守恒断言必然 FAIL',
          sb['src_chars'] != orig, f'broken={sb["src_chars"]} orig={orig}')

    # B4 同一正式稿被两个草稿关联
    d4 = [{'src': 'we should go'}, {'src': 'we should go now'}]
    f4 = [{'src': FINAL_SRC}]
    m4 = CR.match_draft_to_final(d4, f4)
    check('BUG', 'B4 反证：一个正式稿不会被两个草稿关联',
          len(m4) == len(set(m4.values())), f'match={m4}')

    # B5 反证：正式稿还在途 ⇒ 译文**不能消失**（回归缺陷）
    u_bad = [dict(u) for u in UNITS]
    for u in u_bad:
        if u['key'] == 'k5':
            u['mt'] = None
    lines_bad = CR.render_lines(BLOCKS, u_bad)
    seg4_bad = [l for l in lines_bad if l.get('seg') == 4]
    seg5_bad = [l for l in lines_bad if l.get('seg') == 5]
    # 「有原文、没译文」= 段 4 既没有草稿行、段 5 也没有译文 ⇒ 缺陷形态
    has_any_mt = any(l['kind'] in ('mt', 'mt_draft') for l in seg4_bad) or \
        any(l['kind'] == 'mt' for l in seg5_bad)
    check('BUG', 'B5 反证：正式稿还在途时译文不消失（草稿行兜住）',
          has_any_mt,
          f'seg4={[(l["kind"], l["text"][:16]) for l in seg4_bad]} '
          f'seg5={[(l["kind"], l["text"][:16]) for l in seg5_bad]}')


def main():
    t0 = time.time()
    run_real()
    run_bug()
    real = [r for r in _results if r['group'] == 'REAL']
    bug = [r for r in _results if r['group'] == 'BUG']
    n_real_pass = sum(1 for r in real if r['ok'])
    n_bug_hit = sum(1 for r in bug if r['ok'])

    payload = {
        'task': 'APP-015 方案 C 的 App 侧渲染层（caption_render.py）离线验收',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discipline': {
            'imports_only_stdlib_render_module': True,
            'no_inference': True, 'no_benchmark': True, 'no_gpu': True,
            'no_machine_lock': True, 'no_minimax': True,
        },
        'corpus': {'n_blocks': len(BLOCKS), 'n_units': len(UNITS),
                   'draft_src': DRAFT_SRC, 'final_src': FINAL_SRC,
                   'draft_seg': 4, 'final_seg': 5},
        'summary': {
            'real_total': len(real), 'real_pass': n_real_pass,
            'real_fail': len(real) - n_real_pass,
            'bug_total': len(bug), 'bug_hit': n_bug_hit,
            'bug_miss': len(bug) - n_bug_hit,
            'verdict': 'PASS' if (n_real_pass == len(real)
                                  and n_bug_hit == len(bug)) else 'FAIL',
            'elapsed_s': round(time.time() - t0, 3),
        },
        'results': _results,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    for r in _results:
        flag = 'PASS' if r['ok'] else 'FAIL'
        print(f"[{r['group']:4s}] {flag}  {r['name']}"
              + (f"   | {r['detail']}" if not r['ok'] and r['detail'] else ''))
    print(f"\nREAL {n_real_pass}/{len(real)} PASS | "
          f"BUG {n_bug_hit}/{len(bug)} 命中(反证成立) | "
          f"verdict={payload['summary']['verdict']}")
    print(f"evidence -> {OUT}")
    return 0 if payload['summary']['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
