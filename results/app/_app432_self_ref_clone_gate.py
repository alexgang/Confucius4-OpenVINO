# -*- coding: utf-8 -*-
"""🔴 App 侧静态+行为级判据：self_ref 克隆**必须**受「克隆模式」闸门约束。

## 背景（§168 ⑤ 已实测的缺陷，本脚本把「读码定案」升级为「机器可复现的判据」）

* 现象：`--tts-voice A`（**预设 A**）+ 说话人识别开 ⇒ **78/78 句**
  `voice_kind='clone'`、`voice_self_ref=true` ⇒ **用户选了预设 A，实际每句都在克隆**。
* §168 读码根因：`_cli_maybe_send_self_ref`（CLI）与 `_maybe_send_self_ref`（GUI）
  **都没有 `_want_clone` / `_clone_enabled` 闸门** ⇒ 只看「该 spk 有没有登记音色」；
  而「登记音色」这条链**被** `_want_clone` 闸住 ⇒ 选中预设 A 时该 spk 永远没有登记音色
  ⇒ 于是**每句都走 self_ref 克隆**。
* 对照：reviewer 2026-11-07（v2.4）已明确写死口径（commit 98cf8fc 的注释原文）：
  > `preset voice selected => never register clone voices`
  > `（v2.4 acceptance: --tts-voice A still dubbed 18/20 sentences with clone voices）`
  ⇒ **「预设 A ⇒ 绝不注册/使用克隆音色」是已被 reviewer 接受的口径**，
  self_ref 通道**漏了同一道闸门** ⇒ 属于**同一口径的漏实现**，不是新口径。

## 本脚本做两件事（都**不改生产代码**）

1. **A 组（AST 直读 + 行为级真跑）**：把 `live_caption_app.py` 里
   `_maybe_send_self_ref`（GUI）与 `_cli_maybe_send_self_ref`（CLI）**真跑一遍**
   （用桩替换 `tts` / `_spk_voices` / `_spk_self_ref`），在
   「克隆模式**关**」与「克隆模式**开**」两种状态下各跑一次 ⇒
   - 克隆模式**关** ⇒ **必须**一次 `spk_voice_seg` 都**不**发（判 FAIL = 缺陷复现）
   - 克隆模式**开** ⇒ **必须**能发（判 FAIL = 功能被误伤 ⇒ 假阴性）
2. **B 组（反证组）**：把 A 组的判据**故意做坏**（去掉闸门的源码副本）
   ⇒ 判据必须从 PASS 变 FAIL ⇒ 证明判据**有鉴别力**（不是恒真）。

⚠️ **不 import 被测模块**（`live_caption_app.py` 顶层 import numpy/ov 依赖）⇒
用 `ast` 抽出目标函数的**源码**，在**独立命名空间**里 `exec` ⇒ 只测目标函数本身。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
APP_PY = os.path.join(REPO, 'live_caption', 'live_caption_app.py')

GUI_FUNC = '_maybe_send_self_ref'
CLI_FUNC = '_cli_maybe_send_self_ref'


# ══════════════════════════════════════════════════════════════════════
# ① 抽源码（AST 定位，不靠正则）
# ══════════════════════════════════════════════════════════════════════
def _norm(text: str) -> str:
    return text.replace('\r\n', '\n')


def extract_func_src(src: str, name: str) -> str:
    """用 AST 定位并**原样**抽出函数源码（含装饰器/缩进还原）。

    🔴 **不用正则**：`re.search(r'def %s' % name)` 会命中**调用点/注释**
    ⇒ §173 的教训（「正则没匹配上」与「事实不存在」输出一样）在此不适用。
    """
    tree = ast.parse(_norm(src))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = _norm(src).splitlines(True)
            start = node.lineno - 1
            # 含装饰器
            for d in getattr(node, 'decorator_list', []):
                start = min(start, d.lineno - 1)
            seg = ''.join(lines[start:node.end_lineno])
            # 去掉 def 行的缩进（嵌套函数用）
            return '\n'.join(l[4:] if l.startswith('    ') else l
                              for l in seg.split('\n'))
    raise KeyError('function not found: %s' % name)


# ══════════════════════════════════════════════════════════════════════
# ② 桩：替代 self.tts / self._spk_voices / self._spk_self_ref
# ══════════════════════════════════════════════════════════════════════
class _StubTTS:
    """记录 `spk_voice_seg` 调用次数的假 TTS。"""

    def __init__(self):
        self.active = True
        self.calls = []

    def spk_voice_seg(self, seg, pcm):
        self.calls.append((seg, len(pcm)))
        return True

    def spk_update_seg(self, seg, spk, vec):
        self.calls.append(('update', seg, spk))
        return True


class _StubVoices:
    """模拟「该 spk 有没有登记音色」。"""

    def __init__(self, registered):
        self._registered = set(registered)

    def spk_of(self, seg):
        return 'S1'

    def has_voice(self, spk):
        return spk in self._registered


class _StubSelf:
    """GUI 侧 `self` 的最小替身。"""

    def __init__(self, clone_enabled, registered=()):
        self.tts = _StubTTS()
        self._clone_enabled = clone_enabled
        self._spk_voices = _StubVoices(registered)
        self._spk_self_ref = {7: b'\x00' * (2 * 16000)}
        self.logs = []

    def _ui_log(self, msg):
        self.logs.append(msg)


def run_gui(src: str, clone_enabled: bool, registered=(), fn_src=None):
    """真跑 GUI 侧 `_maybe_send_self_ref`，返回 `spk_voice_seg` 调用次数。

    `fn_src`：反证组用 —— 直接指定要跑的函数源码（绕过从 `src` 抽取）。
    """
    if fn_src is None:
        fn_src = extract_func_src(src, GUI_FUNC)
    ns = {}
    exec(compile(fn_src, '<gui-self-ref>', 'exec'), ns)
    fn = ns[GUI_FUNC]
    stub = _StubSelf(clone_enabled, registered)
    fn(stub, 7)
    n = sum(1 for c in stub.tts.calls if not isinstance(c[0], str))
    return n, fn_src


def run_cli(src: str, clone_enabled: bool, registered=(), fn_src=None):
    """真跑 CLI 侧 `_cli_maybe_send_self_ref`，返回 `spk_voice_seg` 调用次数。

    🔴 CLI 侧是**闭包**（`tts` / `_spk_voices` / `_spk_self_ref` / `_want_clone`
    都是 `run_cli` 的局部变量）⇒ 造一个同名命名空间来 exec。

    `fn_src`：反证组用 —— 直接指定要跑的函数源码。
    """
    if fn_src is None:
        fn_src = extract_func_src(src, CLI_FUNC)
    stub = _StubSelf(clone_enabled, registered)
    ns = {
        'tts': stub.tts,
        '_spk_voices': stub._spk_voices,
        '_spk_self_ref': stub._spk_self_ref,
        '_want_clone': clone_enabled,
        'print': lambda *a, **k: None,
    }
    exec(compile(fn_src, '<cli-self-ref>', 'exec'), ns)
    fn = ns[CLI_FUNC]
    fn(7)
    n = sum(1 for c in stub.tts.calls if not isinstance(c[0], str))
    return n, fn_src


# ══════════════════════════════════════════════════════════════════════
# ③ 判据本体
# ══════════════════════════════════════════════════════════════════════
def judge(src: str, gui_src=None, cli_src=None):
    """返回 (checks, n_pass, n_fail)。**不修改** src（纯函数）。

    `gui_src` / `cli_src`：**反证组用** —— 传入「被做掉闸门」的函数源码，
    用来证明判据**有鉴别力**（不是恒 PASS）。
    """
    checks = []

    def add(cid, group, name, ok, got, want):
        checks.append({'id': cid, 'group': group, 'name': name,
                       'ok': bool(ok), 'got': got, 'want': want})

    # ── A 组：GUI 侧 ──
    n_off, fn_src = run_gui(src, clone_enabled=False, fn_src=gui_src)
    add('A1', 'A', 'GUI：克隆模式关 ⇒ self_ref 发送次数 == 0', n_off == 0,
        n_off, 0)
    n_on, _ = run_gui(src, clone_enabled=True, fn_src=gui_src)
    add('A2', 'A', 'GUI：克隆模式开 ⇒ self_ref 能发（≥1 次，≠0）', n_on >= 1,
        n_on, '>=1')
    # 该 spk **已有**登记音色 ⇒ 即使克隆模式开也**不该**再发 self_ref
    n_reg, _ = run_gui(src, clone_enabled=True, registered=('S1',),
                       fn_src=gui_src)
    add('A3', 'A', 'GUI：该 spk 已有登记音色 ⇒ 不发 self_ref', n_reg == 0,
        n_reg, 0)

    # ── A 组：CLI 侧 ──
    n_off_c, fn_src_c = run_cli(src, clone_enabled=False, fn_src=cli_src)
    add('B1', 'B', 'CLI：克隆模式关 ⇒ self_ref 发送次数 == 0', n_off_c == 0,
        n_off_c, 0)
    n_on_c, _ = run_cli(src, clone_enabled=True, fn_src=cli_src)
    add('B2', 'B', 'CLI：克隆模式开 ⇒ self_ref 能发（≥1 次，≠0）', n_on_c >= 1,
        n_on_c, '>=1')
    n_reg_c, _ = run_cli(src, clone_enabled=True, registered=('S1',),
                         fn_src=cli_src)
    add('B3', 'B', 'CLI：该 spk 已有登记音色 ⇒ 不发 self_ref', n_reg_c == 0,
        n_reg_c, 0)

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    return checks, n_pass, n_fail, fn_src, fn_src_c


def _strip_gate(fn_src: str, marker: str) -> str:
    """反证用：**整块**去掉闸门（`if` 行 **＋ 它的整个缩进块**），
    在原位放一行 `pass`。

    🔴 **为什么必须整块去**：只把 `if ...:` 换成 `pass` ⇒ 它的函数体
    （`return False`）变成**孤立语句** ⇒ 闸门**依然生效** ⇒ 反证组
    变成「恒 PASS」⇒ **判据失去鉴别力**（实测踩过一次：修好 A1/B1 之后
    C1/C2 反而 FAIL —— 因为闸门还在，缺陷根本没被造出来）。

    🔴 **为什么不用 `if False:` 替换**：那样闸门**仍然存在**（只是不生效），
    同样造不出「缺陷已复现」的源码 ⇒ 一样没有鉴别力。

    ⇒ 正确做法：**把整个 if 语句（含缩进块）删掉**，让被测函数回到
      「修之前」的样子 ⇒ A1/B1 应当**重新 FAIL**。
    """
    lines = fn_src.split('\n')
    out = []
    i = 0
    hit = 0
    while i < len(lines):
        line = lines[i]
        if marker in line:
            hit += 1
            indent = line[:len(line) - len(line.lstrip())]
            out.append(indent + 'pass')          # 占位（保持行数/缩进合法）
            i += 1
            # **吞掉整个缩进块**（if 的函数体）
            if line.rstrip().endswith(':'):
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.strip() == '':
                        i += 1
                        continue
                    nind = nxt[:len(nxt) - len(nxt.lstrip())]
                    if len(nind) <= len(indent):
                        break
                    i += 1
            continue
        out.append(line)
        i += 1
    if hit == 0:
        raise AssertionError('marker not found: %r' % marker)
    return '\n'.join(out)


def main():
    src = open(APP_PY, 'rb').read().decode('utf-8')
    checks, n_pass, n_fail, fn_src, fn_src_c = judge(src)

    # ── C 组：反证组（判据必须有鉴别力）────────────────────────
    # 🔴 **必须整块去掉闸门**（`_strip_gate` 会吞掉 `if` 的整个缩进块）
    #   ⇒ 造出「修之前」的源码 ⇒ A1/B1 应当**重新 FAIL**
    #   ⇒ 若只把 `if` 行换成 `pass` ⇒ `return False` 变孤立语句 ⇒ 闸门仍生效
    #     ⇒ 反证组恒 PASS ⇒ 判据**失去鉴别力**（实测踩过）。
    bad_gui_src = _strip_gate(fn_src, '_clone_enabled')
    c1 = judge(src, gui_src=bad_gui_src)[0]
    c1_a1 = next(c for c in c1 if c['id'] == 'A1')
    checks.append({'id': 'C1', 'group': 'C',
                   'name': '反证：GUI 闸门被做掉 ⇒ A1 必须 FAIL（有鉴别力）',
                   'ok': (c1_a1['ok'] is False), 'got': c1_a1['ok'],
                   'want': False})
    # 反证 2：CLI 闸门做掉 ⇒ B1 必须 FAIL
    bad_cli_src = _strip_gate(fn_src_c, '_want_clone')
    c2 = judge(src, cli_src=bad_cli_src)[0]
    c2_b1 = next(c for c in c2 if c['id'] == 'B1')
    checks.append({'id': 'C2', 'group': 'C',
                   'name': '反证：CLI 闸门被做掉 ⇒ B1 必须 FAIL（有鉴别力）',
                   'ok': (c2_b1['ok'] is False), 'got': c2_b1['ok'],
                   'want': False})

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = len(checks) - n_pass
    out = {
        'task': 'APP-098 §3 自查 + §168 ⑤ 复现：self_ref 克隆必须受克隆模式闸门约束',
        'src_root': os.path.join(REPO, 'live_caption'),
        'src_file': APP_PY,
        'criterion': 'behavior-level (AST-extract + exec in isolated namespace)',
        'note': ('本判据**不改生产代码**；A1/B1 若 FAIL ⇒ dev HEAD 的 self_ref 通道'
                 '确实缺「克隆模式」闸门（与 §168 ⑤ 实测 78/78 一致）。'),
        'pass_count': n_pass, 'fail_count': n_fail, 'total': len(checks),
        'checks': checks,
    }
    dst = os.path.join(REPO, 'results', 'app',
                       'app432_self_ref_clone_gate.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('[app432] self_ref clone-gate criterion: %d PASS / %d FAIL -> %s'
          % (n_pass, n_fail, dst))
    for c in checks:
        print('  [%s] %-4s %s  got=%r want=%r'
              % ('OK ' if c['ok'] else 'FAIL', c['id'], c['name'],
                 c['got'], c['want']))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
