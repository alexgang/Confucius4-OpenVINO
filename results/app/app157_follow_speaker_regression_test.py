# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-039/040 走查第 3 轮（§101）：**`follow_speaker` 模式回归**的独立验收。

## 为什么要有这个脚本（背景）

§99 修了 5 处断链（A/B/C/E/F）；§100 的在制品又修了 4 处（G/H/I/J），
其中 **G** = 「worker `synth()` 在 `spk=None` 时**什么都不做**
⇒ 下一句仍用**上一个人的声音** ⇒ 冒充（APP-040② 明文禁止）」。

§100 的修法：**`spk=None` ⇒ 显式 `_fallback_to_preset()` ⇒ 回落预设 A**。

🔴🔴🔴 **但这会打死 APP-027⑤ 的旧「跟随说话人（克隆）」模式**：

| 事实 | 位置 |
|---|---|
| ① `clone_collector` **周期性**调 `svc.set_clone_pcm()` ⇒ worker 的**全局** `speaker_embed` 被换成克隆向量 | `clone_collector.py:227` → `tts_worker.py:3541` |
| ② 但主进程 `tts.submit(..., spk=...)` 在**没有说话人旁路**时**恒传 `None`** | `live_caption_app.py:3554` / `4817` / `4876` |
| ③ ⇒ `follow_speaker` 模式下 **`spk` 恒为 `None` 是常态**，不是「标签晚到」的例外 | ①② |

⇒ **每一句**都把克隆音色打回预设 A ⇒ 用户勾了「跟随说话人（克隆）」但听到的是预设 A。

🔴 **§100 的 `app155` 判据 G3 没能抓住它**：`behavior_worker_fallback()` 造的场景是
「**按句绑定**模式下标签晚到」⇒ 该场景回落预设 A **是对的**；
⇒ 判据**前提成立但覆盖面不足** ⇒ 漏掉了另一条产品路径（§99 教训的反面）。

## 本脚本干什么（**纯离线，零 GPU、零推理、不占锁、不调 MiniMax**）

- **绝不 import 被测模块**（顶层 `numpy` 会让 import 阶段 abort）⇒ 用 `ast` 抽源码 + `exec`。
- **决策逻辑来自真实源码 AST**（不是手抄）⇒ 从 `synth()` 里用 `ast` 定位
  `if spk:` 那个分支 ⇒ `ast.unparse` 成可执行片段 ⇒ 在独立命名空间里 exec。
  ⇒ **代码改了，本脚本自动跟着改** ⇒ 不会测一份「抄下来的旧逻辑」。
- **双向反证**（铁律：判据自身必须能识破假通过）：
  - **D-G6 反证**：把 `else` 分支改成「什么都不做」⇒ 判据 G6 **必须 FAIL**。
  - **D-G7 反证**：把回落改成**无条件回落**（不管 `spk` 有没有值）⇒ 判据 G7 **必须 FAIL**。

## 解释器

**必须用带 numpy 的 system 3.12**
（`C:\\Users\\Trekker-PTL\\AppData\\Local\\Programs\\Python\\Python312\\python.exe`）
—— managed 3.13 **无 numpy** ⇒ 判据假 FAIL（记忆铁律 §98）。
"""

from __future__ import annotations

import ast
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LIVE = os.environ.get('APP156_LIVE_DIR', '').strip() or os.path.join(
    REPO, 'live_caption')
OUT = os.path.join(
    REPO, 'results', 'app',
    ('app157_follow_speaker_regression_evidence_pkg.json'
     if os.environ.get('APP156_LIVE_DIR', '').strip()
     else 'app157_follow_speaker_regression_evidence.json'))

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-56s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-56s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def norm(s):
    return s.replace('\r\n', '\n').replace('\r', '\n')


# ══════════════════════════════════════════════════════════════════
# ① 从真实源码抽出「按句绑定音色的决策分支」
# ══════════════════════════════════════════════════════════════════
def extract_worker(live_dir: str):
    """返回 (ns, decision_src, synth_src)。

    `decision_src` = `synth()` 里 `if spk:` 那个分支的可执行源码
    （由 `ast` 定位 ⇒ **不是手抄** ⇒ 代码改了自动跟着改）。
    """
    path = os.path.join(live_dir, 'tts_worker.py')
    src = norm(read(path))
    tree = ast.parse(src)

    ns = {'__name__': 'w', 'log': lambda m: None}
    synth_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'synth':
            synth_node = node
            break
    if synth_node is None:
        return None, None, src

    # 抽 TTSWorker 的相关方法
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'TTSWorker':
            keep = [s for s in node.body
                    if isinstance(s, ast.FunctionDef) and s.name in
                    ('_apply_spk_voice', '_fallback_to_preset',
                     '_log_keep_clone')]
            exec(compile(ast.Module(body=keep, type_ignores=[]),
                         path, 'exec'), ns)
            break

    # 定位 synth() 里的 `if spk:` 分支（决策点）
    decision_src = None
    for node in ast.walk(synth_node):
        if isinstance(node, ast.If):
            try:
                test_src = ast.unparse(node.test)
            except Exception:
                continue
            if test_src.strip() == 'spk':
                decision_src = ast.unparse(node)
                break
    synth_src = ast.get_source_segment(src, synth_node) or ''
    return ns, decision_src, synth_src


class _FakeWorker:
    """最小可用的 worker 替身（只带决策路径要碰的字段）。"""

    def __init__(self, ns):
        self._ns = ns
        self._spk_voice_lock = threading.Lock()
        self._spk_voices = {}
        self._last_voice_spk = None
        self._last_voice_kind = None
        self.speaker_embed = None
        self.speaker_name = None
        self._preset_embed = 'VEC_PRESET_A'
        self._preset_name = 'A'
        self._clone_active = False
        self._clone_mode = None
        self._clone_audio_s = 0.0
        self.engine = None
        self._preset_ref_path = None
        # 🔴 §101：worker 启动参数 `--clone` ⇒「跟随说话人（克隆）」模式标志
        self.clone_mode = False

    def _log_keep_clone(self):
        """§101：保留全局克隆音色时的一致日志。

        ⚠️ **委托给真实实现**（从源码 AST 抽出的 `_log_keep_clone`）
        ⇒ 判据验的是**真实代码的行为**，不是手抄的桩。
        """
        fn = self._ns.get('_log_keep_clone')
        if fn is not None:
            return fn(self)
        self._last_voice_kind = ('clone' if self._clone_active else 'preset')
        return None

    def _apply_spk_voice(self, spk):
        return self._ns['_apply_spk_voice'](self, spk)

    def _fallback_to_preset(self, why=''):
        return self._ns['_fallback_to_preset'](self, why)


def build_decider(decision_src: str, ns: dict):
    """把抽出来的决策分支包成可调用函数 `decide(self, spk)`。"""
    if not decision_src:
        return None
    code = 'def decide(self, spk):\n'
    for ln in decision_src.splitlines():
        code += ('    ' + ln) + '\n'
    g = {'__name__': 'w', 'log': lambda m: None}
    exec(code, g)
    return g['decide']


def run_scenario(live_dir: str, mutate=None, mode: str = 'follow_speaker',
                  spk_value=None):
    """跑一遍场景，返回观测字典。

    `mode`：
      - `'follow_speaker'`  —— 旧模式：主进程**恒传** `spk=None`（没有说话人旁路）
      - `'bound'`          —— 新模式（APP-039/040 按句绑定）：`spk` **有值**

    `mutate` = 可选的源码改写函数（用于反证）。
    """
    ns, decision_src, _ = extract_worker(live_dir)
    if ns is None or not decision_src:
        return None
    if mutate is not None:
        decision_src = mutate(decision_src)
        if not decision_src:
            return None
    decide = build_decider(decision_src, ns)
    if decide is None:
        return None

    w = _FakeWorker(ns)
    if mode == 'follow_speaker':
        # 模拟 follow_speaker：clone_collector 刚设了全局克隆音色
        w.speaker_embed = 'VEC_CLONE_FROM_FOLLOW_SPEAKER'
        w.speaker_name = None
        w._clone_active = True
        w._clone_mode = 'xvector'
        w._clone_audio_s = 3.0
        # 🔴 §101：worker 以 `--clone` 启动 ⇒「跟随说话人（克隆）」模式
        w.clone_mode = True
        # 主进程恒传 spk=None（没有说话人旁路）
        decide(w, None)
    elif mode == 'bound_no_spk':
        # 🔴 §101：**按句绑定模式**（worker 已登记 spk 音色）但这句**标签晚到**
        #   ⇒ spk=None ⇒ **必须回落预设 A**（防「用上一个人的声音冒充」）
        w._spk_voices = {'S2': dict(vec='VEC_S2', ref_path=None)}
        w.speaker_embed = 'VEC_S2'
        w.speaker_name = None
        w._clone_active = True
        w._clone_mode = 'xvector'
        w.clone_mode = True      # 两者同时成立（用户既勾 follow_speaker 又有绑定表）
        decide(w, None)
    else:
        # 模拟按句绑定：worker 已登记该 spk 的克隆音色
        w._spk_voices = {'S2': dict(vec='VEC_S2', ref_path=None)}
        w.speaker_embed = 'VEC_PRESET_A'
        w.speaker_name = 'A'
        w._clone_active = False
        decide(w, spk_value if spk_value is not None else 'S2')
    return dict(after_embed=w.speaker_embed,
                after_kind=w._last_voice_kind,
                after_spk=w._last_voice_spk,
                clone_still_alive=(w.speaker_embed ==
                                   'VEC_CLONE_FROM_FOLLOW_SPEAKER'),
                clone_active=w._clone_active)


def mutate_remove_else(decision_src: str) -> str:
    """反证 1：把 `else` 分支改成「什么都不做」⇒ 克隆音色保留。

    ⚠️ §101：分支结构已变（`else` 里还有一层 `if`）⇒ 用**行级判定**
    找 `else:` 的**块尾**（下一个同级 `if/else` 之前）。
    """
    lines = decision_src.splitlines()
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        if ln.strip() == 'else:' and not ln.startswith('        else:'):
            # 跳过整个 else 块（缩进 > else 的缩进）
            base = len(ln) - len(ln.lstrip())
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= base:
                    break
                i += 1
            out.append('    pass')
            continue
        i += 1
    return '\n'.join(out)


def mutate_unconditional(decision_src: str) -> str:
    """反证 2（§101 修正）：把决策改成**无条件回落预设 A**
    （`if spk: 什么都不做 / else: 回落`）⇒
    「follow_speaker 下克隆音色必须保留」这条判据（B1）**必须 FAIL**。

    ⚠️ **为什么必须改**：旧版的 `if True:` 变异在**新结构**下
    变成了「无条件走 spk 分支」⇒ 在 follow_speaker 场景里结果与正常**相同**
    ⇒ 反证**恒 PASS = 假反证**（记忆铁律：判据必须能识破假通过）。
    """
    lines = decision_src.splitlines()
    # 找到 `if spk:` 与 `else:` 的位置
    try:
        i_if = next(i for i, l in enumerate(lines)
                    if l.strip() == 'if spk:')
        i_else = next(i for i, l in enumerate(lines)
                      if l.strip() == 'else:' and i > i_if)
    except StopIteration:
        return ''
    # `if spk:` 的块体（到 `else:` 之前）
    body = lines[i_if + 1:i_else]
    out = lines[:i_if]
    out.append('if spk:')
    out.append('    pass')
    # 🔴 `else` 块体**整体替换**为「无条件回落」
    #   ⚠️ 不能只是把原 else 块缩进一级搬过来 —— 那里面**仍保留**
    #     `if self.clone_mode ...` 判断 ⇒ 变异**根本没生效**
    #     ⇒ 反证恒 PASS = 假反证（记忆铁律）。
    out.append('else:')
    out.append("    self._fallback_to_preset('no_spk_label')")
    return '\n'.join(out)


def mutate_always_fallback(decision_src: str) -> str:
    """反证 3（§101 新增）：把 `self.clone_mode and (not _bound)` 改成
    `False` ⇒ 永远回落 ⇒ 判据 B1（follow_speaker 下必须保留克隆）**必须 FAIL**。"""
    return decision_src.replace('self.clone_mode and (not _bound)',
                                'False')


def mutate_never_fallback(decision_src: str) -> str:
    """反证 4（§101 新增）：把 `self.clone_mode and (not _bound)` 改成
    `True` ⇒ 永不回落 ⇒ 判据 B3（按句绑定模式必须回落）**必须 FAIL**。"""
    return decision_src.replace('self.clone_mode and (not _bound)',
                                'True')


# ══════════════════════════════════════════════════════════════════
# ② 静态：主进程在「没有说话人旁路」时恒传 spk=None
# ══════════════════════════════════════════════════════════════════
def check_main_submit(live_dir: str) -> dict:
    """静态核对：`tts.submit(..., spk=voice_for_sentence(...) or None)`
    ⇒ **没有说话人旁路时恒为 None** ⇒ 这是「follow_speaker 每句都回落」的根因。"""
    path = os.path.join(live_dir, 'live_caption_app.py')
    src = norm(read(path))
    out = dict(n_submit_calls=0, uses_voice_for_sentence=0,
               voice_for_sentence_defined=False)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and \
                isinstance(node.func, ast.Attribute) and \
                node.func.attr == 'submit':
            out['n_submit_calls'] += 1
            try:
                txt = ast.unparse(node)
            except Exception:
                continue
            if 'voice_for_sentence' in txt:
                out['uses_voice_for_sentence'] += 1
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and \
                node.name == 'voice_for_sentence':
            out['voice_for_sentence_defined'] = True
    return out


def check_service_cmd(live_dir: str) -> dict:
    """静态核对：`tts_service.submit()` 里 `spk` 键**只在非 None 时**才进命令体
    ⇒ worker **无法区分**「没传 spk」与「传了 spk=None」
    ⇒ 这是「按句绑定 vs follow_speaker」必须靠别的信号区分的原因。"""
    path = os.path.join(live_dir, 'tts_service.py')
    src = norm(read(path))
    tree = ast.parse(src)
    out = dict(spk_key_only_when_not_none=False,
               guards_spk_key=False,
               has_spk_none_sentinel=False)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'submit':
            try:
                txt = ast.unparse(node)
            except Exception:
                continue
            out['guards_spk_key'] = ("cmd['spk'] = spk" in txt
                                     and 'is not None' in txt)
            out['has_spk_none_sentinel'] = ("'spk_none'" in txt
                                           or 'spk_none' in txt)
    return out


def main():
    print('=' * 74)
    print('APP-039/040 走查第 3 轮（§101）：follow_speaker 回归独立验收')
    print('=' * 74)
    print('LIVE = %s' % LIVE)

    # ── 静态 ──
    print('\n[static] 主进程 submit 的 spk 来源：')
    m = check_main_submit(LIVE)
    add('S1 主进程有 tts.submit 调用点', m['n_submit_calls'] > 0,
        str(m))
    add('S2 submit 的 spk 来自 voice_for_sentence（无旁路 ⇒ 恒 None）',
        m['uses_voice_for_sentence'] > 0, str(m))

    print('\n[static] tts_service 的 spk 命令体：')
    s = check_service_cmd(LIVE)
    add('S3 spk 键只在非 None 时进命令体（worker 无法区分两种 None）',
        s['guards_spk_key'], str(s))

    # ── 行为：follow_speaker 场景 ──
    print('\n[behavior] follow_speaker 模式（主进程恒传 spk=None）：')
    try:
        obs = run_scenario(LIVE)
        add('B0 场景可复现', obs is not None, str(obs))
        if obs:
            add('B1 🔴 follow_speaker 下克隆音色**不得**被打回预设 A',
                obs['clone_still_alive'],
                'speaker_embed=%s clone_active=%s'
                % (obs['after_embed'], obs['clone_active']))
    except Exception as e:
        add('B0 场景可复现', False, '异常：%s' % e)

    # ── 行为：按句绑定场景（对照组：回落预设 A 在这里是**对的**）──
    print('\n[behavior] 按句绑定模式（对照组：spk 有值 ⇒ 应切到该 spk 的音色）：')
    try:
        obs_b = run_scenario(LIVE, mode='bound', spk_value='S2')
        add('B2 对照：按句绑定下切到 S2 的克隆音色',
            obs_b is not None and obs_b['after_embed'] == 'VEC_S2'
            and obs_b['after_kind'] == 'clone', str(obs_b))
    except Exception as e:
        add('B2 对照：按句绑定下切到 S2 的克隆音色', False, '异常：%s' % e)

    # ── 行为：按句绑定模式 + 标签晚到（spk=None）⇒ **必须回落预设 A** ──
    print('\n[behavior] 按句绑定模式 + 标签晚到（spk=None ⇒ 必须回落，'
          '防「用上一个人的声音冒充」）：')
    try:
        obs_c = run_scenario(LIVE, mode='bound_no_spk')
        add('B3 按句绑定模式下 spk=None ⇒ 必须回落预设 A（不得沿用克隆音）',
            obs_c is not None and not obs_c['clone_still_alive']
            and obs_c['after_embed'] == 'VEC_PRESET_A'
            and obs_c['after_kind'] == 'preset', str(obs_c))
    except Exception as e:
        add('B3 按句绑定模式下 spk=None ⇒ 必须回落预设 A', False,
            '异常：%s' % e)

    # ── 反证 ──
    print('\n[反证] 判据必须能识破假通过：')
    try:
        obs_mut = run_scenario(LIVE, mutate=mutate_remove_else)
        add('D-B1 反证：去掉 else 回落 ⇒ 克隆音色保留 ⇒ B1 必须 FAIL',
            obs_mut is not None and obs_mut['clone_still_alive'],
            '（若这条 FAIL ⇒ 说明 B1 恒 FAIL，不是真判据）')
    except Exception as e:
        add('D-B1 反证', False, '异常：%s' % e)

    try:
        obs_mut2 = run_scenario(LIVE, mutate=mutate_unconditional)
        add('D-B2 反证：无条件回落预设 A ⇒ B1（follow_speaker 保留克隆）必须 FAIL',
            obs_mut2 is not None and not obs_mut2['clone_still_alive'],
            '（若这条 FAIL ⇒ 说明判据分不出两种模式）')
    except Exception as e:
        add('D-B2 反证', False, '异常：%s' % e)

    try:
        obs_mut3 = run_scenario(LIVE, mutate=mutate_always_fallback)
        add('D-B3 反证：永远回落 ⇒ B1（follow_speaker 保留克隆）必须 FAIL',
            obs_mut3 is not None and not obs_mut3['clone_still_alive'],
            '（若这条 FAIL ⇒ 说明 B1 是恒判据，分不出模式）')
    except Exception as e:
        add('D-B3 反证', False, '异常：%s' % e)

    try:
        obs_mut4 = run_scenario(LIVE, mode='bound_no_spk',
                                mutate=mutate_never_fallback)
        # B3 的断言是「after_embed == 'VEC_PRESET_A' 且 kind=='preset'」
        # ⇒ 变异后应**不再成立** ⇒ 反证成立
        b3_holds = (obs_mut4 is not None
                    and obs_mut4['after_embed'] == 'VEC_PRESET_A'
                    and obs_mut4['after_kind'] == 'preset')
        add('D-B4 反证：永不回落 ⇒ B3（按句绑定必须回落）必须 FAIL',
            obs_mut4 is not None and not b3_holds,
            '（若这条 FAIL ⇒ 说明 B3 是恒判据，分不出模式）')
    except Exception as e:
        add('D-B4 反证', False, '异常：%s' % e)

    verdict = 'PASS' if (PASS > 0 and FAIL == 0) else 'FAIL'
    print('\n' + '=' * 74)
    print('RESULT: %d PASS / %d FAIL  => %s'
          % (PASS, FAIL, verdict))
    print('=' * 74)

    ev = dict(script=os.path.basename(__file__), live=LIVE,
              pass_=PASS, fail=FAIL, verdict=verdict, detail=DETAIL)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('evidence -> %s' % OUT)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
