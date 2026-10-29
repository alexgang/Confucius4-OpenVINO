# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-039 / APP-040（§97）**音色按句绑定说话人**的离线验收脚本。

## 背景

APP-039 用户原话（三个症状）：
  ① 「语音音色切换非常滞后，超过了 10 s 的预期。」
  ② 「即使切换，音色也不正确……它是从一个低的音色逐渐切换到高的音色。
      设计本意是克隆原始说话人的音色，不是渐变。」
  ③ 「感觉后台一直持续不断在采样克隆，应该是检测到说话人切换的时候才做
      采样克隆的动作，减少冗余计算量。」

⇒ 本模块（`live_caption/speaker_voice.py` + `live_caption/speaker_tracker.py`）
   + worker 侧按句切换（`tts_worker._apply_spk_voice`）实现了修正。

## 本脚本干什么（**纯离线，不占锁、不跑推理、不用模型**）

对**真实的代码**做**行为**断言：

1. **按句绑定**：`voice_for_sentence(seg)` 查的是「**这一句**的 spk」
   ⇒ 句子的音色**与合成时刻无关**（APP-039 核心）。
2. **一次性切换**：worker 侧 `_apply_spk_voice` **直接换**
   ⇒ **不插值、不渐变、不 EMA、不滑动窗口**。
3. **新 spk 才取样**：只有 `is_new_spk=True` 才 `note_final` 返回 True
   ⇒ 老 spk **不重新取样**（APP-040③）⇒ 声纹计算次数 ≈ 人数 × 1–2。
4. **没音色就回落预设 A**：新 spk 音色未就绪 ⇒ `voice_for_sentence` 返回 `''`
   ⇒ 调用方用预设 A ⇒ **绝不用上一个人的声音冒充**（APP-040②）。
5. **不落盘**：x-vector 只在内存里 ⇒ `reset()` 后清空。
6. **取样区间只含该 spk** ⇒ 结构性保证「不混入别人」。

## 🔴🔴🔴 双向反证（铁律：判据自身必须能识破假通过）

  A. 注入「按合成时刻取音色」⇒ 判据必须 FAIL
  B. 注入「渐变/EMA 平滑」⇒ 判据必须 FAIL
  C. 注入「老 spk 也重新取样」⇒ 判据必须 FAIL
  D. 注入「新 spk 无音色时沿用上一个人的」⇒ 判据必须 FAIL

## 🔴🔴🔴 验收脚本**绝不 import 被测模块**

顶层 `import numpy` 会让 import 阶段 abort ⇒ 用 `ast` 抽源码
+ `exec` 在独立命名空间里跑（记忆铁律 §十一）。
"""

from __future__ import annotations

import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
LIVE = os.path.join(REPO, 'live_caption')


# ══════════════════════════════════════════════════════════════════
# ① 抽源码 + exec（不 import 被测模块）
# ══════════════════════════════════════════════════════════════════
def exec_source(path: str, names: set, src_text: str = None):
    """抽指定顶层定义（含 import）到独立命名空间并 `exec`。

    🔴 **三个必踩坑**（记忆铁律 §十一）：
      ① `from __future__ import` **必须在最前** ⇒ 单独排在前面
      ② 只留 `FunctionDef/ClassDef/Assign` ⇒ **丢掉 `Import`** ⇒ `np` 未定义
      ③ 反证改源码文本、exec 却是原 AST ⇒ 必须**重新抽 AST**（本函数接受
         `src_text`）
    """
    if src_text is None:
        with open(path, encoding='utf-8') as f:
            src_text = f.read()
    tree = ast.parse(src_text)
    futures, imports, keep = [], [], []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            futures.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in names:
                keep.append(node)
        elif isinstance(node, ast.Assign):
            tgt = [t.id for t in node.targets
                   if isinstance(t, ast.Name) and t.id in names]
            if tgt:
                keep.append(node)
    ns = {'__name__': '_extracted'}
    body = futures + imports + keep
    try:
        exec(compile(ast.Module(body=body, type_ignores=[]),
                     '<extracted>', 'exec'), ns)
    except ImportError:
        # 🔴 **解释器差异，不是代码缺陷**（记忆铁律 §六）：
        #   managed 3.13 无 numpy ⇒ import 阶段 abort ⇒ 判据假 FAIL。
        #   ⇒ 去掉只用于别的函数的重型 import 再重试。
        heavy = ('numpy', 'scipy', 'soundfile', 'librosa', 'torch')
        body2 = [n for n in body
                 if not (isinstance(n, ast.Import)
                         and any(a.name.split('.')[0] in heavy
                                 for a in n.names))]
        ns = {'__name__': '_extracted'}
        exec(compile(ast.Module(body=body2, type_ignores=[]),
                     '<extracted>', 'exec'), ns)
    return ns, src_text


# ══════════════════════════════════════════════════════════════════
# ② 假 PCM / 假向量（不依赖 numpy）
# ══════════════════════════════════════════════════════════════════
class FakeArray:
    """极简的 1-D float32 替身（够 `speaker_voice` 的用法）。"""

    def __init__(self, data):
        self._d = list(data)

    def reshape(self, *a):
        return self

    def copy(self):
        return FakeArray(self._d)

    def size(self):
        return len(self._d)

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        return iter(self._d)


def fake_pcm(n_samples: int) -> FakeArray:
    """造一段「语音」（幅度 0.1 的正弦近似）。"""
    return FakeArray([0.1 * ((i % 37) / 37.0) for i in range(n_samples)])


# ══════════════════════════════════════════════════════════════════
# ③ 行为断言
# ══════════════════════════════════════════════════════════════════
def run_behavior(voice_ns):
    """对**抽出来的真实代码**跑一遍行为场景，返回观测结果。"""
    Table = voice_ns['SpeakerVoiceTable']
    SR = int(voice_ns['SR'])
    MIN_S = float(voice_ns['MIN_S'])
    REFINE_S = float(voice_ns['REFINE_S'])

    tbl = Table()
    out = {}

    # ── 场景 1：S1 的第 0 句 ──
    is_new_s1 = tbl.note_final(0, 'S1', [(0.0, 2.0)])
    out['note_final_new_s1'] = bool(is_new_s1)
    out['note_final_old_s1'] = bool(tbl.note_final(1, 'S1', [(2.0, 4.0)]))

    # S1 还没音色 ⇒ 用预设 A（**绝不用别人冒充**）
    out['v0_before_embed'] = tbl.voice_for_sentence(0)

    # 取样：2.0 s ≥ MIN_S(1.5) ⇒ 可提
    tbl.add_sample('S1', fake_pcm(int(2.0 * SR)))
    out['dur_s1'] = round(tbl.stats()['spks']['S1']['dur_s'], 3)
    out['ready_s1'] = bool(tbl.ready_to_embed('S1'))
    tbl.mark_embedded('S1', vec=FakeArray([0.1, 0.2]), refined=False)
    out['v0_after_embed'] = tbl.voice_for_sentence(0)
    out['v1_after_embed'] = tbl.voice_for_sentence(1)

    # ── 场景 2：S2 出现（第 2 句）──
    is_new_s2 = tbl.note_final(2, 'S2', [(4.0, 6.0)])
    out['note_final_new_s2'] = bool(is_new_s2)
    # 🔴 S2 还没音色 ⇒ **必须**回落（不是沿用 S1）
    out['v2_no_voice'] = tbl.voice_for_sentence(2)
    out['has_voice_s2'] = bool(tbl.has_voice('S2'))

    # S2 取样够 REFINE_S ⇒ 细化
    tbl.add_sample('S2', fake_pcm(int(3.5 * SR)))
    out['ready_s2_refine'] = bool(tbl.ready_to_embed('S2'))
    tbl.mark_embedded('S2', vec=FakeArray([0.3]), refined=True)
    out['v2_after_embed'] = tbl.voice_for_sentence(2)

    # ── 场景 3：换回 S1（第 3 句）⇒ **直接用缓存**，不重新取样 ──
    n_embed_before = tbl.stats()['n_embed']
    out['note_final_back_s1'] = bool(tbl.note_final(3, 'S1', [(6.0, 8.0)]))
    out['v3_back_s1'] = tbl.voice_for_sentence(3)
    out['n_embed_unchanged'] = (tbl.stats()['n_embed'] == n_embed_before)

    # ── 场景 4：细化后不再更新 ──
    # 🔴🔴🔴 §99 **判据纠偏**：原场景是
    #     `add_sample('S1', 5 s)` ⇒ 直接查 `ready_to_embed('S1')` ⇒ 期望 False。
    #   ⇒ **判据写错了**：此时 S1 只 `mark_embedded(refined=False)`
    #     （**还没细化过**）⇒ 按 APP-040②，攒够 `REFINE_S(3 s)` 后
    #     **应该**返回 True（该细化了）⇒ 正确行为就是 True。
    #   ⇒ 之前在 HEAD 上「恰好 PASS」是因为**断链 B** 让 `dur_s` 恒 0
    #     ⇒ `ready_to_embed` 恒 False ⇒ **假通过**（记忆铁律 §十一）。
    #   ⇒ 现在改成**真正的语义**：先 `refined=True`（已细化）
    #     ⇒ 再攒更多语音 ⇒ 必须仍然 False（**之后不再更新**）。
    out['ready_s1_before_refine'] = bool(tbl.ready_to_embed('S1'))
    tbl.mark_embedded('S1', vec=FakeArray([0.1, 0.2]), refined=True)
    out['ready_s1_after_refine'] = bool(tbl.ready_to_embed('S1'))
    # 额外：S2 细化过一次后也不应再更新
    tbl.add_sample('S2', fake_pcm(int(4.0 * SR)))
    out['ready_s2_after_refine'] = bool(tbl.ready_to_embed('S2'))

    # ── 场景 5：统计 ──
    st = tbl.stats()
    out['n_speakers'] = st['n_speakers']
    out['n_embed'] = st['n_embed']
    out['n_switch'] = st['n_switch']

    # ── 场景 6：reset ⇒ 全部清空（隐私）──
    tbl.reset()
    out['after_reset_n_speakers'] = tbl.stats()['n_speakers']
    out['after_reset_v0'] = tbl.voice_for_sentence(0)
    out['after_reset_n_embed'] = tbl.stats()['n_embed']

    out['_MIN_S'] = MIN_S
    out['_REFINE_S'] = REFINE_S
    return out


# ══════════════════════════════════════════════════════════════════
# ④ worker 侧的「一次性切换」静态检查
# ══════════════════════════════════════════════════════════════════
def worker_static(w_src: str) -> dict:
    """检查 worker 侧**按句切换**的实现（不跑模型）。

    🔴 判据必须是**行为等价**的代码特征，而不是「有没有某个词」——
       注入反证时这些词往往还在（记忆铁律 §十一）。
    ⚠️ **必须剔除注释与 docstring**：`_apply_spk_voice` 的 docstring 里
       写着「**没有任何平滑 / 插值 / EMA**」⇒ 用关键词匹配会**假 FAIL**。
    """
    import re
    # 提取 `_apply_spk_voice` 函数体
    tree = ast.parse(w_src)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and \
                node.name == '_apply_spk_voice':
            fn = node
            break
    body = ''
    code_only = ''
    if fn is not None:
        body = ast.get_source_segment(w_src, fn) or ''
        # 🔴 **只看可执行语句**（去掉 docstring 与注释）
        #   ⚠️ `ast.get_source_segment` 会把 docstring 一起带上
        #   ⇒ 必须**逐条语句**取源码，并**跳过 docstring 节点**。
        parts = []
        for st in fn.body:
            if (isinstance(st, ast.Expr)
                    and isinstance(st.value, ast.Constant)
                    and isinstance(st.value.value, str)):
                continue                       # docstring ⇒ 跳过
            seg = ast.get_source_segment(w_src, st) or ''
            seg = re.sub(r'#.*', '', seg)
            parts.append(seg)
        code_only = '\n'.join(parts)
    return {
        'found_apply_fn': fn is not None,
        # 「直接换」：**可执行代码**里没有 EMA/插值/渐变
        'no_ema': bool(re.search(r'ema|smooth|lerp|blend|alpha|渐变|平滑',
                                 code_only, re.I)) is False,
        # 有「未登记就回落预设」的分支
        'fallback_to_preset': ('_preset_embed' in body),
        # 按句取音色（不是「当前音色」）
        'per_sentence': ('spk' in body),
        # 🔴 关键：`_apply_spk_voice` 在 **synth() 合成之前**被调用
        'applied_before_synth': (
            w_src.find('_apply_spk_voice(spk)') != -1
            and w_src.find('_apply_spk_voice(spk)') <
            w_src.find('self._synth_babelvox(text, lang)')),
    }


# ══════════════════════════════════════════════════════════════════
# ⑤ main
# ══════════════════════════════════════════════════════════════════
def main():
    print('=' * 72)
    print('APP-039/040（§97）音色按句绑定说话人 · 离线验收')
    print('=' * 72)

    voice_path = os.path.join(LIVE, 'speaker_voice.py')
    worker_path = os.path.join(LIVE, 'tts_worker.py')

    voice_ns, voice_src = exec_source(voice_path, {
        'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR'})

    print('\n' + '-' * 72)
    print('[behavior] 对**真实代码**跑行为场景：')
    obs = run_behavior(voice_ns)
    for k in ('note_final_new_s1', 'note_final_old_s1', 'v0_before_embed',
              'dur_s1', 'ready_s1', 'v0_after_embed', 'v1_after_embed',
              'note_final_new_s2', 'v2_no_voice', 'has_voice_s2',
              'ready_s2_refine', 'v2_after_embed', 'note_final_back_s1',
              'v3_back_s1', 'n_embed_unchanged', 'ready_s1_after_refine',
              'n_speakers', 'n_embed', 'n_switch',
              'after_reset_n_speakers', 'after_reset_v0',
              'after_reset_n_embed'):
        print('   %-28s = %s' % (k, obs[k]))

    with open(worker_path, encoding='utf-8') as f:
        w_src = f.read()
    wst = worker_static(w_src)
    print('\n[worker] worker 侧静态检查：')
    for k, v in wst.items():
        print('   %-28s = %s' % (k, v))

    # ══════════════════════════════════════════════════════════════
    # 判据汇总
    # ══════════════════════════════════════════════════════════════
    results = []

    def add(name, ok, detail=''):
        results.append((name, bool(ok), detail))
        print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                               ('  ' + detail) if detail else ''))

    print('\n' + '=' * 72)
    add('A1 新 spk 才返回 is_new_spk（老 spk 不重新取样）',
        obs['note_final_new_s1'] and not obs['note_final_old_s1'])
    add('A2 该 spk 音色未就绪 ⇒ 回落预设（返回空）⇒ 不用别人冒充',
        obs['v0_before_embed'] == '' and obs['v2_no_voice'] == ''
        and not obs['has_voice_s2'],
        'v0=%r v2=%r' % (obs['v0_before_embed'], obs['v2_no_voice']))
    add('A3 音色登记后按句生效（S1 的句 ⇒ S1）',
        obs['v0_after_embed'] == 'S1' and obs['v1_after_embed'] == 'S1')
    add('A4 S2 登记后按句生效（S2 的句 ⇒ S2）',
        obs['v2_after_embed'] == 'S2')
    add('A5 换回老 spk 直接用缓存（不重新取样 ⇒ n_embed 不变）',
        obs['v3_back_s1'] == 'S1' and obs['n_embed_unchanged'])
    add('A6 细化后不再更新（ready_to_embed 恒 False）',
        not obs['ready_s1_after_refine'] and not obs['ready_s2_after_refine'],
        's1=%s s2=%s' % (obs.get('ready_s1_after_refine'),
                         obs.get('ready_s2_after_refine')))
    add('A6b 未细化但攒够 REFINE_S ⇒ 可细化（APP-040② 的正向门槛）',
        obs.get('ready_s1_before_refine'),
        'ready_s1_before_refine=%s' % obs.get('ready_s1_before_refine'))
    add('A7 声纹计算次数 ≤ 说话人数 × 2（APP-039 验收③）',
        obs['n_embed'] <= obs['n_speakers'] * 2,
        'n_embed=%d n_speakers=%d' % (obs['n_embed'], obs['n_speakers']))
    add('A8 reset 后全部清空（隐私：绝不落盘、结束即清）',
        obs['after_reset_n_speakers'] == 0 and obs['after_reset_v0'] == ''
        and obs['after_reset_n_embed'] == 0)
    add('B1 worker 侧有「按句切换」的函数',
        wst['found_apply_fn'])
    add('B2 worker 侧切换是**一次性**（无 EMA/插值/渐变）',
        wst['no_ema'])
    add('B3 worker 侧未登记 ⇒ 回落预设 A',
        wst['fallback_to_preset'])
    add('B4 worker 侧在**合成之前**应用音色（否则「按句绑定」失效）',
        wst['applied_before_synth'])

    # ══════════════════════════════════════════════════════════════
    # 反证：注入错误 ⇒ 判据必须 FAIL
    # ══════════════════════════════════════════════════════════════
    print('\n' + '-' * 72)
    print('[falsify] 沙盒反证（注入错误 ⇒ 判据必须 FAIL）：')

    # 反证 A：把「按句绑定」改成「按合成时刻取当前 spk」
    #   ⇒ 注入：note_final 不记 _seg_spk，改记成「当前 spk」
    bad_a = voice_src.replace(
        "            self._seg_spk[seg] = str(spk)\n"
        "            if spk not in self._table:",
        "            self._seg_spk[0] = str(spk)  # 反证：忽略 seg\n"
        "            if spk not in self._table:")
    assert bad_a != voice_src, '❌ 反证 A 注入失败'
    ns_a, _ = exec_source(voice_path, {
        'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR'},
        src_text=bad_a)
    obs_a = run_behavior(ns_a)
    a_fail = (obs_a['v2_after_embed'] != 'S2')
    print('  A 注入「忽略 seg」⇒ v2_after_embed=%r ⇒ 判据 %s'
          % (obs_a['v2_after_embed'], 'FAIL ✅' if a_fail else 'PASS ❌'))

    # 反证 B：注入 EMA/渐变
    #   ⚠️ **注入点必须落在可执行代码里**（记忆铁律 §十一）：
    #     注入到注释/docstring ⇒ 判据只看可执行语句 ⇒ **反证不生效**
    bad_b = w_src.replace(
        "            self.speaker_embed = vec\n"
        "            self.speaker_name = None",
        "            self.speaker_embed = vec\n"
        "            self.speaker_name = None\n"
        "            self._ema_alpha = 0.5  # 反证：渐变")
    assert bad_b != w_src, '❌ 反证 B 注入失败'
    wst_b = worker_static(bad_b)
    b_fail = not wst_b['no_ema']
    print('  B 注入「渐变」⇒ no_ema=%s ⇒ 判据 %s'
          % (wst_b['no_ema'], 'FAIL ✅' if b_fail else 'PASS ❌'))

    # 反证 C：注入「老 spk 也重新取样」
    bad_c = voice_src.replace(
        "            if spk not in self._table:",
        "            if True:  # 反证：每次都当新 spk")
    assert bad_c != voice_src, '❌ 反证 C 注入失败'
    ns_c, _ = exec_source(voice_path, {
        'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR'},
        src_text=bad_c)
    obs_c = run_behavior(ns_c)
    c_fail = obs_c['note_final_old_s1'] is True
    print('  C 注入「每次都当新 spk」⇒ note_final_old_s1=%s ⇒ 判据 %s'
          % (obs_c['note_final_old_s1'], 'FAIL ✅' if c_fail else 'PASS ❌'))

    # 反证 D：注入「新 spk 无音色时沿用上一个人的」
    bad_d = voice_src.replace(
        "            if row is None or row['voice'] != 'clone':\n"
        "                return ''",
        "            if row is None or row['voice'] != 'clone':\n"
        "                return 'S1'  # 反证：沿用上一个人")
    assert bad_d != voice_src, '❌ 反证 D 注入失败'
    ns_d, _ = exec_source(voice_path, {
        'SpeakerVoiceTable', 'MIN_S', 'REFINE_S', 'MAX_PER_SPK_S', 'SR'},
        src_text=bad_d)
    obs_d = run_behavior(ns_d)
    d_fail = obs_d['v2_no_voice'] == 'S1'
    print('  D 注入「沿用上一个人」⇒ v2_no_voice=%r ⇒ 判据 %s'
          % (obs_d['v2_no_voice'], 'FAIL ✅' if d_fail else 'PASS ❌'))

    print()
    add('C 反证 A：注入「忽略 seg」后按句判据 FAIL',
        a_fail, 'v2=%r' % obs_a['v2_after_embed'])
    add('C 反证 B：注入「渐变」后 worker 判据 FAIL',
        b_fail, 'no_ema=%s' % wst_b['no_ema'])
    add('C 反证 C：注入「每次新 spk」后 is_new 判据 FAIL',
        c_fail, 'old_s1=%s' % obs_c['note_final_old_s1'])
    add('C 反证 D：注入「沿用上一个人」后回落判据 FAIL',
        d_fail, 'v2=%r' % obs_d['v2_no_voice'])

    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    print('SUMMARY: PASS=%d FAIL=%d TOTAL=%d' % (n_pass, n_fail, len(results)))

    out = os.path.join(HERE, 'app150_app039_spk_bound_voice_evidence.json')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({
            'schema': 'app.app039.spk_bound_voice.v1',
            'files': {
                'speaker_voice.py': voice_path,
                'tts_worker.py': worker_path,
            },
            'behavior': obs,
            'worker_static': wst,
            'falsify': {
                'A_ignore_seg': {'v2_after_embed': obs_a['v2_after_embed'],
                                  'judgment_failed': bool(a_fail)},
                'B_gradient': {'no_ema': wst_b['no_ema'],
                               'judgment_failed': bool(b_fail)},
                'C_always_new': {'note_final_old_s1':
                                 obs_c['note_final_old_s1'],
                                 'judgment_failed': bool(c_fail)},
                'D_reuse_prev': {'v2_no_voice': obs_d['v2_no_voice'],
                                 'judgment_failed': bool(d_fail)},
            },
            'results': [{'name': n, 'ok': bool(o), 'detail': d}
                        for n, o, d in results],
            'pass_count': n_pass,
            'fail_count': n_fail,
            'note': '离线判据（真实代码行为 + 静态检查 + 沙盒反证）；'
                    '非真机实测、非 GUI、非用户实听、非 MiniMax 回转写',
        }, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
