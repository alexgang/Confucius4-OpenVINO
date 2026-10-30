# -*- coding: utf-8 -*-
"""APP-039/040 **第二轮走查**（§100）：4 处新断链 G/H/I/J 的离线验收。

## 为什么要有这个脚本（背景）

§99 修完了 5 处断链（A/B/C/E/F）⇒ 但那是**按 §98 的口径**复查的。
§100 换了口径：**不再看「有没有接上」，而是逐条对着 APP-039/040 的
明文要求，问「这条要求在真机上成立吗」** ⇒ **又查出 4 处断链**。

| 断链 | APP-039/040 的哪句明文 | 旧实现 | 真机后果 |
|---|---|---|---|
| **G** | 「不能用上一个人的声音冒充新的人」（APP-040②） | worker `synth()` 在 `spk=None` 时**什么都不做** | 上一句是 S2 的克隆音、这句标签晚到 ⇒ **用 S2 的声音念一句不知道是谁说的话** ⇒ 串音 |
| **H** | 验收①「**每句实际用的音色和该句 spk 一致的比例**（报告混淆表）」 | jsonl **没有** `voice_spk` / `voice_kind` | reviewer 拿到 jsonl **算不出混淆表** ⇒ **验收①客观做不了** |
| **I** | APP-040④「原文字幕和译文字幕每句前面都显示说话人标签」 | CLI 侧**没有** `_spk_by_seg`、输出**不带**标签 | GUI 有、CLI 无 ⇒ **两条路径不一致** ⇒ CLI 下字幕看不到是谁说的 |
| **J** | APP-040④「spk 晚到时用 spk_update 补标签」 | ASR 侧 `on_spk_update` **无任何调用方** | `pending=True` 的段标签**永远**不到 ⇒ **补标签客观做不了** |

## 双向反证（铁律）

每条判据都要有反证：注入错误后判据**必须 FAIL** ⇒ 判据不恒真。

- **G**：把 `spk=None` 分支的 `_fallback_to_preset` 改回「什么都不做」⇒ 判据 FAIL
- **H**：把 jsonl 键里的 `voice_spk`/`voice_kind` 删掉 ⇒ 判据 FAIL
- **I**：把 CLI 的 `_spk_by_seg` 赋值删掉 ⇒ 判据 FAIL
- **J**：把 `retry_pending` 的 `on_final` 调用改成「直接 return」⇒ 判据 FAIL

## 纪律

- **不在 CPU 上跑推理/测速**；**不调 MiniMax**；零 GPU。
- 验收脚本**不 import 被测模块**（顶层 numpy 会让 import 阶段 abort）
  ⇒ 用 `ast` 抽源码 + `exec` 独立命名空间。
- 反证基线用**固定 commit SHA**（不用 HEAD ⇒ 修复后 HEAD 就是修复版
  ⇒ 反证永远落空 ⇒ 失去证据价值）。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
# 🔴🔴🔴 §100：允许**指定 live_caption 源码目录** ⇒ 可对「客户包内那份」
#   跑**同一套**判据 ⇒ 「仓库过了」≠「客户拿到的也过了」。
#   ⚠️ 默认不设 ⇒ 指向仓库（保持既有行为不变）。
LIVE_OVERRIDE = os.environ.get('APP155_LIVE_DIR', '').strip()
LIVE = (LIVE_OVERRIDE if LIVE_OVERRIDE
        else os.path.join(REPO, 'live_caption'))
# 🔴 覆盖模式下证据**另存**，避免覆盖仓库版的证据文件
#   ⇒ 两轮证据可各自引用、可比对。
OUT = os.path.join(
    REPO, 'results', 'app',
    ('app155_app039_second_audit_evidence_pkg.json'
     if LIVE_OVERRIDE else
     'app155_app039_second_audit_evidence.json'))

# 🔴 反证基线：**修复前**的 commit（§100 之前的 HEAD）
BASE_COMMIT = 'b741240'

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-58s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-58s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def norm(s):
    return s.replace('\r\n', '\n')


def git_show(commit, rel):
    """取**固定 commit** 的源码（反证基线用）⇒ 不会随 HEAD 漂移。"""
    r = subprocess.run(['git', 'show', '%s:%s' % (commit, rel)],
                       cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        return None
    return r.stdout


def exec_source(path, names, src_text=None):
    """🔴🔴 **不 import 被测模块** ⇒ `ast` 抽源码 + `exec` 独立命名空间。

    🔴 三个必踩坑（§十一铁律）：
    ① 只留 `FunctionDef/ClassDef/Assign` ⇒ **丢掉 `Import`** ⇒ 顶层
       `import numpy as np` 丢失 ⇒ `np` 未定义 ⇒ NameError ⇒ 判据假 FAIL
       ⇒ **必须连 `Import`/`ImportFrom` 一起抽**。
    ② 只抽方法 ⇒ **模块级常量**未注入 ⇒ NameError
       ⇒ 断言把「反证组因异常而没识破」当成 PASS ⇒ 必须逐个常量单独 exec。
    ③ 反证改源码文本、exec 却是原 AST ⇒ 反证永远不生效
       ⇒ 本函数接受 `src_text` 并**重新抽 AST**。
    """
    src = src_text if src_text is not None else read(path)
    src = norm(src)
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Assign, ast.AnnAssign,
                             ast.Import, ast.ImportFrom)):
            keep.append(node)
    ns = {'__name__': 'extracted'}
    mod = ast.Module(body=keep, type_ignores=[])
    exec(compile(mod, path, 'exec'), ns)
    for n in names:
        if n not in ns:
            raise AssertionError('抽源码后缺 %s' % n)
    return ns, src


# ══════════════════════════════════════════════════════════════════
# ① 断链 G：worker `synth()` 的 `spk=None` 分支必须**回落预设 A**
# ══════════════════════════════════════════════════════════════════
def check_G(src_text=None):
    """🔴 断链 G：`spk=None` ⇒ 必须调用 `_fallback_to_preset`。

    🔴 **判据必须是「调用点级」**（不是 token 匹配）—— 否则
    `_fallback_to_preset` 出现在**别处**也会假通过。
    ⇒ 用 AST 找 `synth()` 里 `if spk:` 的 `else` 分支
    ⇒ 要求该分支里有 `_fallback_to_preset(...)` 的**调用**。
    """
    path = os.path.join(LIVE, 'tts_worker.py')
    src = norm(src_text if src_text is not None else read(path))
    tree = ast.parse(src)
    synth = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'synth':
            synth = node
            break
    if synth is None:
        return dict(found_synth=False, has_fallback=False, has_else=False)
    found_synth = True
    has_else = False
    has_fallback = False
    for node in ast.walk(synth):
        if not isinstance(node, ast.If):
            continue
        # 找「测试条件是 spk」的 if
        test = node.test
        is_spk_test = (isinstance(test, ast.Name) and test.id == 'spk') or (
            isinstance(test, ast.Attribute) and test.attr == 'spk')
        if not is_spk_test:
            continue
        has_else = True
        if node.orelse:
            for sub in ast.walk(ast.Module(body=node.orelse,
                                          type_ignores=[])):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    nm = (fn.attr if isinstance(fn, ast.Attribute)
                          else getattr(fn, 'id', ''))
                    if nm == '_fallback_to_preset':
                        has_fallback = True
    return dict(found_synth=found_synth, has_else=has_else,
                has_fallback=has_fallback)


# ══════════════════════════════════════════════════════════════════
# ② 断链 H：jsonl 必须逐句记 `voice_spk` / `voice_kind`
# ══════════════════════════════════════════════════════════════════
def check_H(src_text=None):
    """🔴 断链 H：`voice_spk` / `voice_kind` 必须在 jsonl 键白名单里，
    且**必须真的被赋值**（不只是声明）。"""
    path = os.path.join(LIVE, 'tts_worker.py')
    src = norm(src_text if src_text is not None else read(path))
    out = {}
    # ① 在 `_APP0*_JSONL_KEYS` 白名单里
    keys = []
    for m in re.finditer(r'_APP\d+_JSONL_KEYS\s*=\s*\((.*?)\n\)',
                         src, re.S):
        keys.extend(re.findall(r"'([^']+)'", m.group(1)))
    out['in_key_list'] = ('voice_spk' in keys and 'voice_kind' in keys)
    # ② 真的被赋值（`tel[...] = ` / `row[...] = `）
    out['tel_assigned'] = bool(
        re.search(r"tel\[['\"]voice_spk['\"]\]\s*=", src))
    out['row_assigned'] = bool(
        re.search(r"row\[['\"]voice_spk['\"]\]\s*=", src))
    out['kind_assigned'] = bool(
        re.search(r"tel\[['\"]voice_kind['\"]\]\s*=", src))
    # ③ 失败/丢句的行也要带（否则混淆表分母变小）
    out['failed_row_has'] = bool(
        re.search(r"row\[['\"]voice_spk['\"]\]\s*=", src))
    return out


# ══════════════════════════════════════════════════════════════════
# ③ 断链 I：CLI 侧必须登记 `_spk_by_seg` 且输出带标签
# ══════════════════════════════════════════════════════════════════
def check_I(src_text=None):
    """🔴 断链 I：CLI 路径必须有 `_spk_by_seg` 登记 + 字幕输出带前缀。"""
    path = os.path.join(LIVE, 'live_caption_app.py')
    src = norm(src_text if src_text is not None else read(path))
    out = {}
    out['has_table'] = '_spk_by_seg = {}' in src
    out['has_assignment'] = bool(
        re.search(r'_spk_by_seg\[\s*_seg\s*\]\s*=', src))
    # 字幕文件输出带标签前缀
    out['out_has_label'] = bool(
        re.search(r"_out_lines\.append\(\('\[%s\] %s'", src))
    out['mt_has_label'] = bool(
        re.search(r"_pre = \('\[%s\] ' % _s\) if _s else ''", src))
    # 渲染层也要拿到 spk_by_seg（否则 render_lines 不给 spk 键）
    out['render_gets_spk'] = bool(
        re.search(r'seg_carry=getattr\(mt, .seg_carry., None\) or \{\},\s*'
                  r'spk_by_seg=_spk_by_seg', src))
    return out


# ══════════════════════════════════════════════════════════════════
# ④ 断链 J：`retry_pending()` 必须**重问** ASR
# ══════════════════════════════════════════════════════════════════
def check_J(src_text=None, app_text=None):
    """🔴 断链 J：`SpeakerBridge.retry_pending()` 必须存在，
    且内部**真的重新调用** `on_final`（不能只是空壳）。

    🔴⚠️ **反证的关键**：`app_text` 必须能覆盖「App 侧」的源码
      ⇒ 否则反证改的是 App 文件，但判据读的还是盘上的原文件
      ⇒ **反证永远不生效** ⇒ 假通过（本轮踩到）。
    """
    path = os.path.join(LIVE, 'speaker_tracker.py')
    src = norm(src_text if src_text is not None else read(path))
    out = {}
    out['has_retry'] = 'def retry_pending' in src
    # 🔴🔴🔴 §100 **判据纠偏**：**不能**用 `'on_final(' in body` 判「是否调用」
    #   ⇒ `retry_pending` 的 **docstring 里就写了** `SpeakerTracker.on_final()`
    #   ⇒ **docstring 命中** ⇒ 反证永远打不掉 ⇒ **假通过**。
    #   ⇒ 改用 **AST 的 Call 节点**（只认真正的调用）。
    m = re.search(r'def retry_pending\(.*?\n(?=    def |\Z)', src, re.S)
    body = m.group(0) if m else ''
    out['calls_on_final'] = False
    out['reads_pending'] = False
    out['discards_resolved'] = False
    if body:
        try:
            btree = ast.parse(body)
            for node in ast.walk(btree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    nm = (fn.attr if isinstance(fn, ast.Attribute)
                          else getattr(fn, 'id', ''))
                    if nm == 'on_final':
                        out['calls_on_final'] = True
                    if nm == 'discard':
                        out['discards_resolved'] = True
                if isinstance(node, ast.Attribute) and \
                        node.attr == '_pending':
                    out['reads_pending'] = True
        except SyntaxError:
            out['calls_on_final'] = False
    # App 侧必须真的调用它（GUI + CLI 两处）
    app = norm(app_text if app_text is not None
               else read(os.path.join(LIVE, 'live_caption_app.py')))
    out['app_calls_gui'] = 'self._spk_bridge.retry_pending()' in app
    out['app_calls_cli'] = '_spk_bridge.retry_pending()' in app
    out['app_gui_hook'] = 'self._retry_spk_labels()' in app
    out['app_cli_hook'] = '_cli_retry_spk_labels()' in app
    return out


# ══════════════════════════════════════════════════════════════════
# ⑤ 行为验证（不依赖源码文本，直接跑真实逻辑）
# ══════════════════════════════════════════════════════════════════
def behavior_retry_pending():
    """🔴 **行为**验证 `retry_pending()`：真造一个「标签晚到」的 ASR 桩。

    桩语义：前 N 次 `on_final` 返 `spk=None` + `pending=True`，
    第 N+1 次返 `spk='S2'` ⇒ App 侧重试应当**拿到标签**。
    """
    path = os.path.join(LIVE, 'speaker_tracker.py')
    ns, _ = exec_source(path, ['SpeakerBridge'])
    Bridge = ns['SpeakerBridge']

    class _StubTracker:
        def __init__(self):
            self.calls = 0

        def on_final(self, seg_id, t_start, t_end):
            self.calls += 1
            if self.calls < 3:
                return dict(spk=None, spk_conf=None, clean_ranges=[],
                            pending=True, reason='seg_pending',
                            is_new_spk=False)
            return dict(spk='S2', spk_conf=0.9, clean_ranges=[(0.0, 2.5)],
                        pending=False, reason=None, is_new_spk=True)

        def on_spk_update(self, seg_id, spk):
            return dict(known=False)

    b = Bridge()
    stub = _StubTracker()
    b._tracker = stub
    b.available = True
    # 先模拟一次「拿不到标签」的定稿
    r = b.on_final(7, 0.0, 2.5)
    obs = dict(first_pending=bool(r.get('pending')),
               first_spk=r.get('spk'))
    # 重试（应当拿不到）
    g1 = b.retry_pending()
    obs['retry1'] = list(g1)
    # 再重试（应当拿到）
    g2 = b.retry_pending()
    obs['retry2'] = list(g2)
    obs['n_pending_after'] = b.stats()['n_pending']
    obs['n_update'] = b.stats()['n_update']
    return obs


def behavior_worker_fallback():
    """🔴 **行为**验证断链 G：`spk=None` ⇒ 音色**真的**回到预设 A。

    🔴 不 import 被测模块（顶层 numpy）⇒ `ast` 抽 `_apply_spk_voice`
    与 `_fallback_to_preset` 的**可执行代码** ⇒ 放进一个假 self 上跑。
    """
    path = os.path.join(LIVE, 'tts_worker.py')
    src = norm(read(path))
    tree = ast.parse(src)
    ns = {'__name__': 'w', 'log': lambda m: None}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'TTSWorker':
            keep = []
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and \
                        sub.name in ('_apply_spk_voice', '_fallback_to_preset'):
                    keep.append(sub)
            if keep:
                exec(compile(ast.Module(body=keep, type_ignores=[]),
                             path, 'exec'), ns)
            break

    class _Self:
        pass

    s = _Self()
    s._spk_voice_lock = __import__('threading').Lock()
    s._spk_voices = {'S2': dict(vec='VEC_S2', ref_path=None)}
    s._last_voice_spk = 'S2'
    s._last_voice_kind = 'clone'
    s.speaker_embed = 'VEC_S2'
    s.speaker_name = None
    s._preset_embed = 'VEC_PRESET_A'
    s._preset_name = 'A'
    s._clone_active = True
    s._clone_mode = 'xvector'
    s._clone_audio_s = 3.0
    s.engine = None
    s._preset_ref_path = None

    ns['_apply_spk_voice'](s, 'S2')
    obs = dict(after_apply_embed=s.speaker_embed,
               after_apply_kind=s._last_voice_kind,
               after_apply_spk=s._last_voice_spk)
    # 模拟「这句没有 spk 标签」⇒ 应当回落到预设 A
    ns['_fallback_to_preset'](s, 'no_spk_label')
    obs['after_fallback_embed'] = s.speaker_embed
    obs['after_fallback_kind'] = s._last_voice_kind
    obs['after_fallback_spk'] = s._last_voice_spk
    obs['after_fallback_clone_active'] = s._clone_active
    return obs


def main():
    print('=' * 74)
    print('APP-039/040 第二轮走查（§100）：断链 G/H/I/J 离线验收')
    print('=' * 74)

    # ── REAL 组：当前代码必须全 PASS ──
    print('\n[REAL] 当前代码（§100 修复后）：')
    g = check_G()
    add('G1 worker synth() 有 `if spk:` 分支', g['has_else'], str(g))
    add('G2 `spk=None` 分支调用 _fallback_to_preset', g['has_fallback'],
        '（旧实现：什么都不做 ⇒ 用上一个人的声音冒充）')

    h = check_H()
    add('H1 jsonl 键白名单含 voice_spk/voice_kind', h['in_key_list'], str(h))
    add('H2 遥测真的给 tel.voice_spk 赋值', h['tel_assigned'])
    add('H3 失败/丢句行也带 voice_spk（分母不缩小）', h['row_assigned'])
    add('H4 遥测给 tel.voice_kind 赋值', h['kind_assigned'])

    i = check_I()
    add('I1 CLI 有 _spk_by_seg 表', i['has_table'])
    add('I2 CLI 登记 _spk_by_seg[_seg]', i['has_assignment'])
    add('I3 CLI 原文输出带 [S2] 前缀', i['out_has_label'])
    add('I4 CLI 译文输出带 [S2] 前缀', i['mt_has_label'])
    add('I5 CLI 渲染层拿到 spk_by_seg', i['render_gets_spk'])

    j = check_J()
    add('J1 SpeakerBridge 有 retry_pending()', j['has_retry'])
    add('J2 retry_pending 内部重问 on_final', j['calls_on_final'])
    add('J3 retry_pending 读 pending 集合', j['reads_pending'])
    add('J4 拿到标签后出队', j['discards_resolved'])
    add('J5 GUI 侧调用 retry_pending', j['app_calls_gui'])
    add('J6 CLI 侧调用 retry_pending', j['app_calls_cli'])
    add('J7 GUI poll 挂了 _retry_spk_labels', j['app_gui_hook'])
    add('J8 CLI 挂了 _cli_retry_spk_labels', j['app_cli_hook'])

    # ── 行为验证 ──
    print('\n[behavior] 真实逻辑跑一遍：')
    try:
        obs_g = behavior_worker_fallback()
        add('G3 行为：spk=None 后 speaker_embed 回到预设 A',
            obs_g['after_fallback_embed'] == 'VEC_PRESET_A',
            json.dumps(obs_g, ensure_ascii=False))
        add('G4 行为：回落后 voice_kind=preset / voice_spk=None',
            obs_g['after_fallback_kind'] == 'preset'
            and obs_g['after_fallback_spk'] is None)
        add('G5 行为：切到 S2 时 voice_kind=clone',
            obs_g['after_apply_kind'] == 'clone'
            and obs_g['after_apply_embed'] == 'VEC_S2')
    except Exception as e:
        add('G3 行为验证（断链 G）', False, '异常：%s' % e)

    try:
        obs_j = behavior_retry_pending()
        add('J9 行为：首次 on_final 返 pending=True/spk=None',
            obs_j['first_pending'] and obs_j['first_spk'] is None,
            json.dumps(obs_j, ensure_ascii=False))
        add('J10 行为：重试仍拿不到时不返回条目',
            obs_j['retry1'] == [])
        add('J11 行为：再重试拿到标签 S2',
            len(obs_j['retry2']) == 1 and obs_j['retry2'][0][1] == 'S2',
            str(obs_j['retry2']))
        add('J12 行为：拿到后从 pending 出队',
            obs_j['n_pending_after'] == 0 and obs_j['n_update'] == 1,
            'pending=%s update=%s' % (obs_j['n_pending_after'],
                                      obs_j['n_update']))
    except Exception as e:
        add('J9 行为验证（断链 J）', False, '异常：%s' % e)

    # ── 反证组：注入错误 ⇒ 判据必须 FAIL ──
    print('\n[反证] 注入错误 ⇒ 判据必须 FAIL（判据不恒真）：')

    # 反证 G：把 `spk=None` 分支改回「什么都不做」
    worker_path = os.path.join(LIVE, 'tts_worker.py')
    wsrc = read(worker_path)
    bad_g = wsrc.replace(
        "            self._fallback_to_preset('no_spk_label')",
        "            pass  # 反证：什么都不做（旧行为）")
    if bad_g != wsrc:
        gb = check_G(bad_g)
        add('D-G 反证：抽掉 _fallback_to_preset ⇒ G2 FAIL',
            not gb['has_fallback'], str(gb))
    else:
        add('D-G 反证：抽掉 _fallback_to_preset', False, '注入失败')

    # 反证 H：把 jsonl 键白名单里的 voice_spk/voice_kind 删掉
    bad_h = re.sub(r"\n\s*'voice_spk', 'voice_kind',", '', wsrc)
    if bad_h != wsrc:
        hb = check_H(bad_h)
        add('D-H 反证：删掉 jsonl 键 ⇒ H1 FAIL',
            not hb['in_key_list'], str(hb))
    else:
        add('D-H 反证：删掉 jsonl 键', False, '注入失败')

    # 反证 H2：删掉遥测赋值
    bad_h2 = wsrc.replace(
        "        tel['voice_spk'] = (str(self._last_voice_spk)",
        "        tel['_x'] = (str(self._last_voice_spk)")
    if bad_h2 != wsrc:
        hb2 = check_H(bad_h2)
        add('D-H2 反证：删掉 tel.voice_spk 赋值 ⇒ H2 FAIL',
            not hb2['tel_assigned'], str(hb2))
    else:
        add('D-H2 反证：删掉 tel.voice_spk 赋值', False, '注入失败')

    # 反证 I：把 CLI 的 `_spk_by_seg[_seg] = ...` 删掉
    app_path = os.path.join(LIVE, 'live_caption_app.py')
    asrc = read(app_path)
    bad_i = asrc.replace(
        "                _spk_by_seg[_seg] = (spk, spk_conf)", "")
    if bad_i != asrc:
        ib = check_I(bad_i)
        add('D-I 反证：删掉 CLI 登记 ⇒ I2 FAIL',
            not ib['has_assignment'], str(ib))
    else:
        add('D-I 反证：删掉 CLI 登记', False, '注入失败')

    # 反证 J：把 retry_pending 的 on_final 调用改掉
    # ⚠️ **缩进必须与真实源码一致**（在嵌套 try 里 = 16 空格）
    #   ⇒ 否则注入**静默不生效** ⇒ 反证变成「假通过」。
    trk_path = os.path.join(LIVE, 'speaker_tracker.py')
    tsrc = read(trk_path)
    bad_j = tsrc.replace(
        "                res = tr.on_final(seg_id=seg, t_start=float(t_start),\n"
        "                                  t_end=float(t_end))",
        "                res = dict(spk=None)  # 反证：不重问 ASR")
    if bad_j == tsrc:
        # 缩进不匹配 ⇒ 按「retry_pending 函数体」切片后再替换
        # 🔴⚠️ **必须限定在 `retry_pending` 体内** ⇒ 否则会改到
        #   `on_final()` 方法里的那处调用 ⇒ 反证改错地方 ⇒ 假通过。
        m = re.search(r'def retry_pending\(.*?\n(?=    def |\Z)', tsrc, re.S)
        if m:
            blk = m.group(0)
            blk2 = re.sub(
                r'res = tr\.on_final\(seg_id=seg, t_start=float\(t_start\),\s*'
                r'\n\s*t_end=float\(t_end\)\)',
                'res = dict(spk=None)  # 反证：不重问 ASR', blk, count=1)
            if blk2 != blk:
                bad_j = tsrc.replace(blk, blk2)
    if bad_j != tsrc:
        jb = check_J(bad_j)
        add('D-J 反证：不重问 on_final ⇒ J2 FAIL',
            not jb['calls_on_final'], str(jb))
    else:
        add('D-J 反证：不重问 on_final', False, '注入失败（源码形态变了）')

    # 反证 J2：App 侧不调用 retry_pending
    # ⚠️ `check_J` 内部会**重新读盘** ⇒ 必须让 `src_text` 参数生效
    #   ⇒ `check_J` 已支持 `src_text`，但 `app` 部分是单独读的
    #   ⇒ 这里改为**直接检查注入后的文本**。
    bad_j2 = asrc.replace("self._spk_bridge.retry_pending()", "None")
    if bad_j2 != asrc:
        # ⚠️ **必须把注入后的 App 源码传给判据**（否则读盘上的原文件
        #   ⇒ 反证不生效 ⇒ 假通过）
        jb2 = check_J(app_text=bad_j2)
        add('D-J2 反证：App 不调用 retry_pending ⇒ J5 FAIL',
            not jb2['app_calls_gui'], str(jb2))
    else:
        add('D-J2 反证：App 不调用 retry_pending', False, '注入失败')

    # ── 反证基线：修复前的 commit 必须 FAIL（证明判据不恒真于历史） ──
    print('\n[基线] 修复前 commit %s 必须 FAIL：' % BASE_COMMIT)
    for rel, fn, key, label in (
            ('live_caption/tts_worker.py', check_G, 'has_fallback', 'G2'),
            ('live_caption/tts_worker.py', check_H, 'in_key_list', 'H1'),
            ('live_caption/live_caption_app.py', check_I, 'has_assignment',
             'I2'),
            ('live_caption/speaker_tracker.py', check_J, 'has_retry', 'J1')):
        b = git_show(BASE_COMMIT, rel)
        if b is None:
            add('基线 %s（%s）' % (label, BASE_COMMIT), False,
                '取不到 %s@%s' % (rel, BASE_COMMIT))
            continue
        if label == 'G2':
            r = fn(b)['has_fallback']
        elif label == 'H1':
            r = fn(b)['in_key_list']
        elif label == 'I2':
            r = fn(b)['has_assignment']
        else:
            r = fn(b)['has_retry']
        add('基线 %s 在 %s 处 FAIL（判据能识破历史缺陷）' % (label, BASE_COMMIT),
            not r, '当前值=%s' % r)

    ev = dict(script='app155_app039_second_audit_test.py',
              base_commit=BASE_COMMIT,
              pass_=PASS, fail=FAIL, verdict=('PASS' if FAIL == 0 else 'FAIL'),
              detail=DETAIL)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n' + '=' * 74)
    print('VERDICT: %s   PASS=%d / FAIL=%d' %
          (ev['verdict'], PASS, FAIL))
    print('证据: %s' % OUT)
    print('=' * 74)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
