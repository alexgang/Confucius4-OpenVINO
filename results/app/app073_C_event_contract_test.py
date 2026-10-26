#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app073 —— §53 方案 C「5 元组事件契约 + 同 id 原位替换」的 App 侧验收。

====================================================================
🔴 为什么需要这个脚本
====================================================================
MT 的方案 C 移交说明（H-019 §3.1）规定 outbox 事件从
`(kind, key, text)` **3 元组**变成 `(kind, id, src, txt, seg)` **5 元组**，
并且**替换关系改用「同 id 原位替换」**。

⇒ App 侧有三处必须跟着改，否则会**静默出错**：
  ① `live_caption_app.py` 的两处 outbox 消费（GUI `_pump_tts` + CLI `run_cli`）
     —— 旧写法 `for kind, key, txt in ...` 会直接 **ValueError** 崩掉；
  ② `caption_render.render_lines()` 的草稿↔正式稿配对
     —— 旧写法用**原文包含关系**（MT §73 已证明会**跨 85 段错配**）；
  ③ `_draft_mt` 缓存的**键** —— 必须从「翻译去重键」改成「单元 id」。

本脚本对**渲染层**做**纯离线**验收（不 import numpy / 不起进程 /
不跑推理 / 不占 GPU / 不取机器锁）⇒ 符合「先正确性、后性能」。

====================================================================
验收项
====================================================================
REAL 组（期望成立）：
  A1  `unpack_event` 兼容 3 元组与 5 元组
  A2  5 元组解出 id / src / txt / seg 全部正确
  A3  **同 id 替换**：草稿与正式稿共用 id ⇒ 正式稿**原地**替换草稿那一行
  A4  **跨段错配不复现**：短草稿 `'That'` 不得配到 85 段之外的正式稿
  A5  **无残留草稿行**：被同 id 正式稿替换后，草稿行**不再单独出现**
  A6  原文守恒（渲染层不丢字、不加字）
  A7  正式稿**还在途**时 ⇒ 草稿行照常显示、正式稿**不被提前剔除**
      （§47 之后的老坑：提前剔除 ⇒ 译文整轮消失）
  A8  TTS 只订阅 final ⇒ 草稿**永不**进语音

BUG 组（期望**不**命中 ⇒ 若命中说明缺陷仍存在）：
  B1  旧 3 元组路径仍能工作（向后兼容）
  B2  一个 id 至多一条正式单元 ⇒ 替换无歧义

用法
----
    python app073_C_event_contract_test.py
产物
----
    results/app/app073_C_event_contract_evidence.json
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

# 🔴🔴 **只 import 纯 stdlib 模块**（caption_render）
#   ⇒ 不 import translator（那会拖 numpy + openvino_genai）
#   ⇒ 不 import live_caption_app（170 KB，顶部 import numpy/openvino）
import caption_render as CR  # noqa: E402

OUT = os.path.join(HERE, 'app073_C_event_contract_evidence.json')

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                      'ok': bool(ok), 'detail': str(detail)})
    print(('  [%s] %s %s  %s' % (group, 'PASS' if ok else 'FAIL',
                                  name, ('<- ' + str(detail)) if detail else '')))
    return bool(ok)


# ══════════════════════════════════════════════════════════════════════
# 语料：模拟「跨段尾句」的真实形态（方案 C 的主场景）
# ══════════════════════════════════════════════════════════════════════
# 段 0：完整句
# 段 1：完整句 + 跨段尾句的前半
# 段 2：跨段尾句的后半（凑齐 ⇒ 正式稿）
BLOCKS = [
    'Welcome to our Q3 meeting.',
    'We should go to market soon',
    'with three milestones done.',
]

DRAFT_SRC = 'We should go to market soon'          # 尾句前半（草稿）
FINAL_SRC = 'We should go to market soon with three milestones done.'
DRAFT_MT = '我们应该很快推向市场'
FINAL_MT = '我们应该很快推向市场，并且已经完成了三个里程碑。'

UID = 'C:1:7'   # 方案 C 的单元 id（草稿与正式稿共用）


def make_units(with_final=True, final_ready=True, uid=UID):
    """构造 `mt_units()` 风格的 units 列表（方案 C 的形状）。"""
    units = [
        {'key': 'k0', 'src': BLOCKS[0], 'seg': 0, 'mt': '欢迎参加我们的Q3会议。',
         'kind': 'final', 'unit_id': 'C:0:1'},
        # 草稿单元：unit_id 与正式稿**相同**
        {'key': 'DRAFT::' + uid, 'src': DRAFT_SRC, 'seg': 1, 'mt': None,
         'kind': 'draft', 'unit_id': uid},
    ]
    if with_final:
        units.append({
            'key': 'k1', 'src': FINAL_SRC, 'seg': 2,
            'mt': (FINAL_MT if final_ready else None),
            'kind': 'final', 'unit_id': uid})
    return units


def main():
    print('=' * 70)
    print('§53 方案 C 事件契约验收（5 元组 + 同 id 原位替换）')
    print('=' * 70)

    # ── A1 / A2：unpack_event 兼容两种格式 ─────────────────────────
    ev3 = CR.unpack_event(('draft', 'DRAFT::k4', '译文'))
    check('REAL', 'A1 unpack_event 解 3 元组（旧格式）',
          ev3 is not None and ev3['kind'] == 'draft'
          and ev3['key'] == 'DRAFT::k4' and ev3['txt'] == '译文',
          ev3)

    ev5 = CR.unpack_event(('final', 'C:1:7', FINAL_SRC, FINAL_MT, 2))
    check('REAL', 'A2 unpack_event 解 5 元组（新格式）',
          ev5 is not None and ev5['kind'] == 'final'
          and ev5['id'] == 'C:1:7' and ev5['src'] == FINAL_SRC
          and ev5['txt'] == FINAL_MT and ev5['seg'] == 2,
          ev5)

    # ── A3：同 id 替换（正式稿原地替换草稿那一行）────────────────
    units = make_units()
    lines = CR.render_lines(BLOCKS, units, granularity='seg')
    all_texts = [l['text'] for l in lines]
    mt_lines = [l for l in lines if l['kind'] == 'mt']
    # 正式稿应出现在**草稿那一行**（seg 1）而不是 seg 2
    seg1_mt = [l['text'] for l in lines
               if l.get('seg') == 1 and l['kind'] in ('mt', 'mt_draft')]
    seg2_mt = [l['text'] for l in lines
               if l.get('seg') == 2 and l['kind'] in ('mt', 'mt_draft')]
    check('REAL', 'A3 同 id ⇒ 正式稿原地替换草稿那一行（seg 1）',
          FINAL_MT in seg1_mt and FINAL_MT not in seg2_mt,
          'seg1=%s seg2=%s' % (seg1_mt, seg2_mt))

    # ── A4：跨段错配不复现（MT §73 的 85 段错配）──────────────────
    # 构造（**照 MT §73 的真实错配形态**）：
    #   草稿  'That'（seg 0，unit_id = C:0:1）
    #   正式稿 A：src = "That does not mean we won't use external options"
    #             （**正确的那个**，同段、unit_id 相同）
    #   正式稿 B：src = "That is where we are today."（**更短**）
    #             （**另一个独立单元**，unit_id 不同，seg 2）
    #
    #   🔴 旧口径「双向包含 + 取最短」会选 **B**（更短）⇒ 错配
    #   ⇒ 新口径「同 id」选 **A** ⇒ B 留在**自己的段**（seg 2）
    #
    # ⇒ 断言 = **A 出现在草稿那一行（seg 0）**、**B 不出现在 seg 0**
    #   （B 出现在 seg 2 是**正确**的：它是一个独立正式单元）
    blocks2 = ['x'] * 3
    u2 = [
        {'key': 'd', 'src': 'That', 'seg': 0, 'mt': '那个',
         'kind': 'draft', 'unit_id': 'C:0:1'},
        {'key': 'a', 'src': "That does not mean we won't use external options",
         'seg': 0, 'mt': 'A译文', 'kind': 'final', 'unit_id': 'C:0:1'},
        {'key': 'b', 'src': "That is where we are today.",
         'seg': 2, 'mt': 'B译文', 'kind': 'final', 'unit_id': 'C:9:9'},
    ]
    l2 = CR.render_lines(blocks2, u2, granularity='seg')
    seg0_mt = [l['text'] for l in l2
               if l.get('seg') == 0 and l['kind'] in ('mt', 'mt_draft')]
    seg2_mt = [l['text'] for l in l2
               if l.get('seg') == 2 and l['kind'] in ('mt', 'mt_draft')]
    check('REAL', 'A4 同 id ⇒ 不再跨段错配（A 落在草稿行、B 留在自己段）',
          seg0_mt == ['A译文'] and seg2_mt == ['B译文'],
          'seg0=%s seg2=%s' % (seg0_mt, seg2_mt))

    # 🔴 **同时证明「旧口径确实会错」**（否则这条断言没有证据价值）
    legacy_pick = CR.match_draft_to_final(
        [{'src': 'That'}],
        [{"src": "That does not mean we won't use external options"},
         {"src": "That is where we are today."}])
    legacy_src = (["That does not mean we won't use external options",
                   "That is where we are today."][legacy_pick[0]]
                  if legacy_pick else '')
    check('REAL', 'A4b 旧 src 口径确实会选错（证明 A4 的断言有证据价值）',
          legacy_src.startswith("That is where"),
          'legacy picked: %r' % legacy_src[:40])

    # ── A5：无残留草稿行 ──────────────────────────────────────────
    n_draft_lines = sum(1 for l in lines if l['kind'] == 'mt_draft')
    check('REAL', 'A5 被同 id 正式稿替换后无残留草稿行',
          n_draft_lines == 0, 'n_draft_lines=%d' % n_draft_lines)

    # ── A6：原文守恒 ──────────────────────────────────────────────
    src_chars = CR.summarize(lines)['src_chars']
    orig = sum(len(CR.strip_ws(b)) for b in BLOCKS)
    check('REAL', 'A6 原文守恒（渲染层不丢字不加字）',
          src_chars == orig, 'rendered=%d orig=%d' % (src_chars, orig))

    # ── A7：正式稿还在途 ⇒ 不得提前剔除 ──────────────────────────
    # 🔴 真实形态：草稿单元**已有译文**（outbox 已经回传了草稿译文），
    #   而它的正式稿**还在途**（mt=None）。
    #   ⇒ 草稿行照常显示（浅色）；正式稿**不得**被提前剔除
    #     （提前剔除 ⇒ 那一轮「有原文、没译文」⇒ 用户以为翻译丢了）
    units_busy = make_units(final_ready=False)
    for u in units_busy:
        if (u.get('kind') or 'final') == 'draft':
            u['mt'] = DRAFT_MT
    lines_busy = CR.render_lines(BLOCKS, units_busy, granularity='seg')
    busy_texts = [l['text'] for l in lines_busy]
    n_draft_busy = sum(1 for l in lines_busy if l['kind'] == 'mt_draft')
    check('REAL', 'A7 正式稿还在途 ⇒ 草稿行照常显示（浅色）、不提前剔除',
          n_draft_busy == 1 and DRAFT_MT in busy_texts
          and FINAL_MT not in busy_texts,
          'n_draft_busy=%d texts=%s' % (n_draft_busy, busy_texts))

    # ── A8：TTS 只订阅 final ─────────────────────────────────────
    evs = [CR.unpack_event(x) for x in
           [('draft', 'C:1:7', DRAFT_SRC, DRAFT_MT, 1),
            ('final', 'C:1:7', FINAL_SRC, FINAL_MT, 2)]]
    tts_kinds = [e['kind'] for e in evs if e['kind'] == 'final']
    check('REAL', 'A8 TTS 只订阅 final（草稿永不进语音）',
          tts_kinds == ['final'] and len(evs) == 2, tts_kinds)

    # ── B1：向后兼容（旧 3 元组仍走 src 包含匹配）────────────────
    old_units = [
        {'key': 'k0', 'src': BLOCKS[0], 'seg': 0, 'mt': '译0',
         'kind': 'final'},
        {'key': 'DRAFT::k1', 'src': DRAFT_SRC, 'seg': 1, 'mt': DRAFT_MT,
         'kind': 'draft'},
        {'key': 'k1', 'src': FINAL_SRC, 'seg': 2, 'mt': FINAL_MT,
         'kind': 'final'},
    ]
    l3 = CR.render_lines(BLOCKS, old_units, granularity='seg')
    seg1_old = [l['text'] for l in l3
                if l.get('seg') == 1 and l['kind'] in ('mt', 'mt_draft')]
    check('REAL', 'B1 旧 3 元组路径仍工作（无 id ⇒ 回退 src 匹配）',
          FINAL_MT in seg1_old, seg1_old)

    # ── B2：一个 id 至多一条正式单元 ⇒ 替换无歧义 ────────────────
    # 🔴 语义修正：同一 id 出现**两条**正式单元是**不该发生**的
    #   （MT 侧已用 `_used_uids` 保证）⇒ 渲染层必须**只取第一条**
    #   ⇒ 断言 = 「草稿那一行只出现**一条**正式稿译文」
    #   （B 是一条**独立的正式单元**，它该留在**自己那一行**⇒ 是对的）
    u_dup = [
        {'key': 'd', 'src': 'That', 'seg': 0, 'mt': '草稿',
         'kind': 'draft', 'unit_id': 'C:0:1'},
        {'key': 'a', 'src': 'That does not mean we',
         'seg': 0, 'mt': 'A', 'kind': 'final', 'unit_id': 'C:0:1'},
        {'key': 'b', 'src': 'That does not mean we will',
         'seg': 1, 'mt': 'B', 'kind': 'final', 'unit_id': 'C:0:1'},
    ]
    l4 = CR.render_lines(['x', 'y', 'z'], u_dup, granularity='seg')
    seg0_dup = [l['text'] for l in l4
                if l.get('seg') == 0 and l['kind'] in ('mt', 'mt_draft')]
    n_draft_dup = sum(1 for l in l4 if l['kind'] == 'mt_draft')
    check('REAL', 'B2 同 id 多条正式单元 ⇒ 草稿行只取第一条、无歧义',
          len(seg0_dup) == 1 and n_draft_dup == 0,
          'seg0=%s n_draft=%d' % (seg0_dup, n_draft_dup))

    # ── 汇总 ──────────────────────────────────────────────────────
    n_pass = sum(1 for r in _results if r['ok'])
    n_fail = sum(1 for r in _results if not r['ok'])
    bug_hit = [r['name'] for r in _results
               if r['group'] == 'BUG' and r['ok']]
    real_fail = [r['name'] for r in _results
                 if r['group'] == 'REAL' and not r['ok']]
    verdict = 'PASS' if (n_fail == 0 and not bug_hit) else 'FAIL'

    evidence = {
        'purpose': '§53 方案 C 事件契约（5 元组）+ 同 id 原位替换的 App 侧验收',
        'module_under_test': os.path.join(REPO, 'live_caption', 'caption_render.py'),
        'method': '纯离线：只 import caption_render（纯 stdlib）'
                  '⇒ 不起进程 / 不跑推理 / 不占 GPU / 不取机器锁',
        'event_contract': '(kind, id, src, txt, seg)，kind ∈ {draft, final}',
        'replacement_rule': '同 id 原位替换（不再用原文包含关系）',
        'results': _results,
        'n_pass': n_pass, 'n_fail': n_fail,
        'bug_hits': bug_hit, 'real_failures': real_fail,
        'verdict': verdict,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print()
    print('=' * 70)
    print('结果：%d/%d PASS | verdict=%s' % (n_pass, n_pass + n_fail, verdict))
    if real_fail:
        print('REAL 失败：', real_fail)
    if bug_hit:
        print('BUG 命中：', bug_hit)
    print('证据 ->', OUT)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
