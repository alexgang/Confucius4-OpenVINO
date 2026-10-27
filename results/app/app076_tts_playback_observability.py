"""app076_tts_playback_observability.py — APP-021 自检（**不加载模型**）。

APP-021（2026-10-26 15:25）要求把播放链路做成可观测，并**撤回**
「played ≥ 1 ⇒ 端到端能出声」这个无效判据。本脚本用**假 worker**
把 7 条要求逐条钉住：

① `played` 语义：必须等「音频被播放回调**全部取走**」才发；
   播放器不可用 ⇒ 发**句子级 error**（带 id），**不发** played。
② 每句一行遥测：峰值 / RMS(dBFS) / NaN / 回调增量 / n_read 增量 / 欠载。
③ 会话日志落盘 + 对话框「已播/丢/失败」三个数 + 最近句子级错误。
④ 「🔊 测试声音」：走**同一个** Player 播 440 Hz。
⑤ `cb_tts_out` 绑定变更事件（worker 在跑时改下拉 ⇒ 重启 worker）。
⑥ `--tts-dump-dir` / 运行时 `set_dump_dir` ⇒ 逐句落 wav。
⑦ 源码级断言：`played` 不再在「写进缓冲」时发；app071 判据改成
   `n_read` 增量 ≥ 本句样本数 且 峰值 > 1e-2。

## 🔴 为什么用假 worker
本脚本**不 import 被测模块的重依赖**（铁律：分析脚本一律不 import
被测模块）⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间来测纯逻辑，
worker 侧用**假 Player / 假 ring** 做纯 Python 行为验证。

## 跑法
    python results/app/app076_tts_playback_observability.py
输出：`results/app/app076_tts_playback_observability.txt`
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import threading
import time
import traceback

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
APP = os.path.join(REPO, 'live_caption')

RESULTS = []
EVIDENCE = {}


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(('  PASS  ' if ok else '  FAIL  ') + name + (
        ('  |  ' + detail) if detail else ''))
    return bool(ok)


def section(t):
    print('\n' + '=' * 72)
    print(t)
    print('=' * 72)


# ── 源码抽取（不 import 被测模块）────────────────────────────────────
def load_module_wo_heavy(path, name):
    """把模块源码 **exec** 到独立命名空间（**不 import**）。

    🔴 铁律：分析脚本**一律不要 import 被测模块** ⇒ 连带 numpy ⇒
    进程在 import 阶段 abort，try/except 接不住。
    ⇒ 这里改用「读源码 + exec」：模块顶层的 import 全是标准库
      （numpy / sounddevice / soundfile 都是**函数内懒加载**）⇒
      exec 不会拉起任何重依赖。
    """
    src = open(path, encoding='utf-8').read()
    ns = {'__name__': name, '__file__': path}
    exec(compile(src, path, 'exec'), ns)
    return ns, src


def src_of(rel):
    return open(os.path.join(APP, rel), encoding='utf-8').read()


# ══════════════════════════════════════════════════════════════════════
# A 组：worker 侧 —— played 语义 + 遥测 + 测试音（**纯 Python 假 Player**）
# ══════════════════════════════════════════════════════════════════════
def group_a():
    section('A 组：worker 侧 played 语义 / 遥测 / 测试音')
    path = os.path.join(APP, 'tts_worker.py')
    ns, src = load_module_wo_heavy(path, 'tw_probe')

    # ── A1：`wait_consumed` 语义 ─────────────────────────────────────
    Player = ns.get('Player')
    check('A0 抽到 Player 类', Player is not None)

    class FakeRing:
        def __init__(self, cap=72000):
            self._cap = cap
            self.n_written = 0
            self.n_read = 0
            self.n_blocks = 0
            self._count = 0
            self.stall_s = 5.0

        def read(self, n):
            take = min(n, self._count)
            self._count -= take
            self.n_read += take
            return [0.0] * take

        def write(self, data, should_stop=None):
            self.n_written += len(data)
            self._count += len(data)
            return True

        def level(self):
            return self._count

        def close(self):
            pass

    class FakePlayer:
        """复刻 `Player` 的接口，但**不碰声卡**。"""

        def __init__(self):
            self.sr = 24000
            self.ring = FakeRing()
            self.n_cb = 0
            self.n_underflow = 0
            self.n_silence_fill = 0
            self.out_desc = '假设备（测试）'
            self._stream = object()
            self._lock = threading.Lock()

        def write(self, wav, should_stop=None):
            return self.ring.write(wav, should_stop=should_stop)

        def close(self):
            pass

    # 把 Player 的两个新方法**搬**到假类上（源码级复用，避免重写逻辑）
    for m in ('wait_consumed', 'telemetry', 'test_tone'):
        setattr(FakePlayer, m, getattr(Player, m))

    p = FakePlayer()
    # ── A2：n_read 没追上 ⇒ 必须返回 False（不能 falsely 说「播完了」）──
    p.ring.n_written = 24000
    p.ring.n_read = 0
    ok, diag = p.wait_consumed(24000, timeout_s=0.3)
    check('A2 n_read 未追上 ⇒ 判失败（不是「已播完」）', ok is False,
          'diag=%s' % diag[:60])
    EVIDENCE['A2_not_consumed'] = dict(ok=ok, diag=diag)

    # ── A3：n_read 追上 ⇒ 返回 True ────────────────────────────────
    p2 = FakePlayer()
    p2.ring.n_written = 24000
    p2.ring.n_read = 24000
    ok, diag = p2.wait_consumed(24000, timeout_s=0.3)
    check('A3 n_read 追上 ⇒ 判成功', ok is True, 'diag=%s' % diag[:60])

    # ── A4：后台线程推进 n_read ⇒ wait_consumed 能等到 ──────────────
    p3 = FakePlayer()
    p3.ring.n_written = 24000

    def _feed():
        time.sleep(0.15)
        p3.ring.n_read = 24000

    threading.Thread(target=_feed, daemon=True).start()
    t0 = time.monotonic()
    ok, diag = p3.wait_consumed(24000, timeout_s=3.0)
    dt = time.monotonic() - t0
    check('A4 播放回调推进后能等到「播完」', ok is True and dt < 2.0,
          '耗时 %.2f s' % dt)
    EVIDENCE['A4_wait_consumed'] = dict(ok=ok, elapsed=round(dt, 3))

    # ── A5：telemetry 字段齐全 ─────────────────────────────────────
    tel = p3.telemetry()
    need = ('out_desc', 'sr', 'n_cb', 'n_underflow', 'n_written', 'n_read',
            'n_blocks', 'ring_level', 'ring_cap', 'stream_open')
    miss = [k for k in need if k not in tel]
    check('A5 telemetry 字段齐全', not miss, '缺 %s' % miss)

    # ── A6：测试声音 → 走同一个 ring，n_read 增量 ≈ sr×dur ──────────
    p4 = FakePlayer()
    before_read = p4.ring.n_read
    before_cb = p4.n_cb

    def _feed2():
        # 模拟播放回调在消费
        t = time.monotonic()
        while time.monotonic() - t < 3.0:
            with p4.ring._cv if hasattr(p4.ring, '_cv') else _NullCtx():
                pass
            p4.ring.n_read = p4.ring.n_written
            p4.n_cb += 1
            time.sleep(0.01)

    class _NullCtx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    threading.Thread(target=_feed2, daemon=True).start()
    ok, msg = p4.test_tone(freq=440.0, dur_s=1.0, amp=0.3)
    read_delta = p4.ring.n_read - before_read
    check('A6 测试声音：n_read 增量 ≈ sr×1 s（24000）',
          ok and abs(read_delta - 24000) <= 2400,
          'n_read +%d / 回调 +%d' % (read_delta, p4.n_cb - before_cb))
    EVIDENCE['A6_test_tone'] = dict(ok=ok, msg=msg, read_delta=read_delta)

    # ── A7：播放器不可用 ⇒ test_tone 必须明确失败 ───────────────────
    p5 = FakePlayer()
    p5._stream = None
    ok, msg = p5.test_tone()
    check('A7 无播放器 ⇒ 测试声音明确失败（不假装成功）',
          ok is False and '播放流' in msg, 'msg=%s' % msg[:50])

    # ── A8：源码级 —— `played` **必须**在 `wait_consumed` 之后发出 ─────
    m_play = re_finditer_played(src)
    check('A8 源码：`played` 只在 wait_consumed 之后发出',
          m_play and all(x['before_wait'] for x in m_play),
          'played emit 点 %d 个；before_wait=%s'
          % (len(m_play), [x['before_wait'] for x in m_play]))
    EVIDENCE['A8_played_emit_points'] = m_play


def re_finditer_played(src):
    """用 AST 判定 `synth()` 里 **`played` 的 emit 是否在 `wait_consumed` 之后**。

    🔴 不用字符串位置判定：中间夹着 `emit({'kind':'error'...})`（失败分支）
       会让「上一个 emit」落在 wait_consumed **之后** ⇒ 误判。
    ⇒ 改用 AST 的行号：**`wait_consumed` 调用的行号 < `played` emit 的行号**。
    """
    out = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != 'synth':
            continue
        wait_lines = []
        played_lines = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                fn = sub.func
                nm = (fn.attr if isinstance(fn, ast.Attribute)
                      else (fn.id if isinstance(fn, ast.Name) else ''))
                if nm == 'wait_consumed':
                    wait_lines.append(sub.lineno)
                if nm == 'emit':
                    # `emit({'kind': 'played', ...})` ⇒ kind 是**字典的键**
                    for arg in sub.args:
                        if isinstance(arg, ast.Dict):
                            for k, v in zip(arg.keys, arg.values):
                                if (isinstance(k, ast.Constant)
                                        and k.value == 'kind'
                                        and isinstance(v, ast.Constant)
                                        and v.value == 'played'):
                                    played_lines.append(sub.lineno)
        for pl in played_lines:
            out.append(dict(played_line=pl,
                            wait_lines=wait_lines,
                            before_wait=bool(wait_lines)
                            and min(wait_lines) < pl))
    return out


# ══════════════════════════════════════════════════════════════════════
# E 组：🔴🔴 **「弱判据」这一类缺陷的闸门**（2026-10-27 §62 新增）
# ══════════════════════════════════════════════════════════════════════
# APP-021⑦ 明文要求：「app071 的判据改成：`n_read` 增量 ≥ 本句样本数，
# 并且本句峰值 > 1e-2」+「不要用 "played ≥ 1" 宣称能出声」。
# ⇒ §62 实测：**该要求从未被执行**（app071/app074/app075/app077/app039
#    至今仍用 `n_played >= 1`）⇒ ⇒ 必须有**闸门**（§36 教训：
#    「修掉一处」≠「这一类不会再来」）。
WEAK_SCRIPTS = (
    'results/app/app071_tts_worker_error_probe.py',
    'results/app/app074_tts_e2e_cp936.py',
    'results/app/app075_gui_offline_read_real.py',
    'results/app/app077_tts_acceptance_ab.py',
    'results/app/app039_tts_e2e_smoke.py',
)


def group_e():
    section('E 组：弱判据闸门（`n_played >= 1` ⇒ 不得用来宣称「出声」）')

    # ── E1：判据有**唯一来源**（单一事实来源）────────────────────────
    crit_path = os.path.join(HERE, 'tts_audible_criterion.py')
    check('E0 判据模块存在（单一事实来源）', os.path.isfile(crit_path),
          crit_path)

    crit_src = (open(crit_path, encoding='utf-8').read()
                if os.path.isfile(crit_path) else '')
    check('E1 判据模块含 C1（read_delta ≥ n_samples）',
          'READ_DELTA_KEY' in crit_src and 'N_SAMPLES_KEY' in crit_src)
    check('E2 判据模块含 C2（峰值阈值 1e-2）',
          'PEAK_MIN = 1e-2' in crit_src)

    # ── E3：判据模块的**行为**正确（不 import 被测模块 ⇒ 独立 exec）──
    if crit_src:
        ns = {'__name__': 'crit_probe'}
        try:
            exec(compile(crit_src, crit_path, 'exec'), ns)
            ev = ns['evaluate_audible']
            ok_tel = {'n_samples': 120960, 'read_delta': 120960, 'peak': 0.523438}
            ok, reasons = ev(ok_tel)
            check('E3 合格遥测 ⇒ 判通过', ok is True, str(reasons))
            # 缺证据 ⇒ 判**失败**（不是「无法判断 ⇒ 放行」）
            ok2, r2 = ev(None)
            check('E4 没有遥测 ⇒ 判失败（缺证据不放行）', ok2 is False, str(r2))
            # read_delta 不足 ⇒ 失败
            ok3, r3 = ev({'n_samples': 120960, 'read_delta': 68608, 'peak': 0.5})
            check('E5 read_delta < n_samples ⇒ 判失败', ok3 is False, str(r3))
            # 峰值过低（静音合成）⇒ 失败
            ok4, r4 = ev({'n_samples': 120960, 'read_delta': 120960, 'peak': 1e-4})
            check('E6 峰值 ≤ 1e-2 ⇒ 判失败（静音合成）', ok4 is False, str(r4))
            # 缺字段 ⇒ 失败
            ok5, r5 = ev({'peak': 0.5})
            check('E7 遥测缺字段 ⇒ 判失败', ok5 is False, str(r5))
            EVIDENCE['E_criterion_behaviour'] = dict(
                ok_case=ok, missing=ok2, short_read=ok3, silent=ok4,
                partial=ok5)
        except Exception as e:
            check('E3 判据模块可独立 exec', False,
                  '%s: %s' % (type(e).__name__, e))

    # ── E8：**弱判据回归闸门** —— 扫描**整个** App 侧验收脚本目录 ────
    #   判据：脚本里**不得**再出现「用 `n_played >= 1` 判定出声」这种写法。
    #   🔴 扫描规则由 `audible_criterion_lint` **唯一定义**（单一事实来源）
    #      ⇒ 本闸门与 `app092` 的 A9 跑**同一条规则** ⇒ 不会互相矛盾。
    #   ⚠️ **不剥注释**：`ast.parse` 本来就不含注释节点；手工剥行会
    #      **破坏多行字符串**（bytes 字面量）⇒ 解析失败 ⇒ 覆盖面悄悄缩水。
    #   ⚠️ **解析失败必须判 FAIL**（闸门自己失效），绝不能当成「无违规」。
    lint = _load_lint()
    if lint is None:
        check('E8 弱判据类别闸门（扫描器可用）', False,
              'audible_criterion_lint 模块不可用 ⇒ 闸门失效')
        return
    # ⚠️ `_load_lint()` 返回的是**命名空间 dict** ⇒ 用**下标**取，不是属性
    reports = lint['scan_dir'](os.path.join(HERE))
    summary = lint['summarize'](reports)
    EVIDENCE['E_weak_criterion_scan'] = summary

    check('E8 弱判据扫描器本身可用（规则来自单一来源）',
          summary['gate_valid'],
          '已跟踪文件解析失败=%s' % summary['parse_fail_tracked'])
    check('E9 全目录扫描：无脚本再用「n_played >= 1」判定出声',
          summary['n_violations'] == 0,
          '扫了 %d 个文件，违规 %d 处%s'
          % (summary['n_scanned'], summary['n_violations'],
             ('：' + '；'.join(summary['violations'][:5]))
             if summary['violations'] else ''))
    check('E10 5 个重点脚本都在扫描范围内（覆盖面不退化）',
          all(any(r.name == os.path.basename(rel) for r in reports)
              for rel in WEAK_SCRIPTS),
          'WEAK_SCRIPTS=%d 个' % len(WEAK_SCRIPTS))
    if summary['skipped']:
        print('  ℹ️ 跳过的历史遗留文件（未跟踪，不判 FAIL）：%s'
              % '；'.join(summary['skipped'][:4]))


def _load_lint():
    """加载 `audible_criterion_lint`（**不 import 被测模块** ⇒ 独立 exec）。"""
    p = os.path.join(HERE, 'audible_criterion_lint.py')
    if not os.path.isfile(p):
        return None
    ns = {'__name__': 'lint_probe'}
    try:
        exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), ns)
    except Exception:
        return None
    return ns


def _find_weak_criteria(code: str):
    """🔴🔴 **已废弃**（§62）⇒ 规则迁到 `audible_criterion_lint`（单一来源）。

    ⚠️ 保留这个函数**只为**说明「闸门的第一版错在哪」：
      ① `except SyntaxError: return []` ⇒ 解析失败被当成「无违规」
         ⇒ **闸门永远 PASS** ⇒ **假通过**；
      ② 「剥注释」破坏了多行字符串（bytes 字面量）⇒ 解析失败 ⇒ 覆盖面缩水；
      ③ 只判 `GtE` ⇒ `> 0` / `== 1` 等价写法**漏检**；
      ④ `out = []` 漏写 ⇒ 命中即 `NameError`（闸门直接崩）。

    ⇒ 现在**唯一**的实现是 `audible_criterion_lint.find_weak_criteria()`。
    """
    return _load_lint()['find_weak_criteria'](code)


# ══════════════════════════════════════════════════════════════════════
# B 组：service 侧 —— 会话日志 / 三个计数 / 事件处理
# ══════════════════════════════════════════════════════════════════════
def group_b():
    section('B 组：service 侧 会话日志 / 计数 / 事件处理')
    path = os.path.join(APP, 'tts_service.py')
    ns, src = load_module_wo_heavy(path, 'ts_probe')

    # ── B1：`append_session_log` 真的落盘 ────────────────────────────
    ok = 'append_session_log' in ns
    check('B0 抽到 append_session_log / session_log_path',
          ok and 'session_log_path' in ns)
    if not ok:
        return
    # exec 出来的命名空间里函数之间的引用要能解析 ⇒ 手工塞回去
    ns['append_session_log'] = ns['append_session_log']
    p = ns['session_log_path']()
    ns['append_session_log']('自检写入一行', tag='[TEST]')
    exists = os.path.isfile(p)
    content = open(p, encoding='utf-8').read() if exists else ''
    check('B1 会话日志文件已创建且追加了内容',
          exists and '自检写入一行' in content, '路径=%s' % p)
    check('B2 会话日志路径在 %LOCALAPPDATA%\\Confucius4LiveCaption 下',
          'Confucius4LiveCaption' in p and 'session_' in p, p)
    EVIDENCE['B1_session_log'] = dict(path=p, exists=exists)

    # ── B3：源码级 —— `n_failed` 存在且独立计数 ─────────────────────
    check('B3 service 有 n_failed（独立于 n_dropped）',
          'self.n_failed' in src)
    check('B4 service 有 last_sentence_error',
          'self.last_sentence_error' in src)
    check('B5 stats() 带出 n_failed / last_sentence_error / session_log',
          all(k in src for k in ('n_failed=self.n_failed',
                                 'last_sentence_error=self.last_sentence_error',
                                 'session_log=session_log_path()')))
    # ── B6：处理 `written` 事件（真实积压）───────────────────────────
    check('B6 service 处理 written 事件（真实积压口径）',
          "kind == 'written'" in src)
    check('B7 service 处理 test_tone / telemetry 事件',
          "kind == 'test_tone'" in src and "kind == 'telemetry'" in src)
    check('B8 service 提供 test_tone() / set_dump_dir() 指令',
          "def test_tone(" in src and "def set_dump_dir(" in src)


# ══════════════════════════════════════════════════════════════════════
# C 组：GUI 侧 —— 会话日志落盘 / 设备热切换 / 测试声音按钮
# ══════════════════════════════════════════════════════════════════════
def group_c():
    section('C 组：GUI 侧 会话日志 / 输出设备热切换 / 测试声音按钮')
    src = src_of('live_caption_app.py')
    check('C1 `_ui_log` 落盘到会话日志',
          'append_session_log' in src and
          'def _ui_log' in src)
    check('C2 `cb_tts_out` 绑了 <<ComboboxSelected>>',
          "cb_tts_out.bind('<<ComboboxSelected>>'" in src)
    check('C3 有 `_on_tts_out_changed`（改下拉 ⇒ 重启 worker）',
          'def _on_tts_out_changed' in src)
    check('C4 重启时把新设备写进日志',
          '[tts] 输出设备改为：' in src)
    check('C5 TTS 行有「🔊 测试声音」按钮',
          '🔊 测试声音' in src)
    check('C6 有 `_on_tts_test_sound`',
          'def _on_tts_test_sound' in src)
    check('C7 `_tts_meter` 显示失败数',
          "n_failed" in src)

    src2 = src_of('offline_reader_gui.py')
    check('C8 离线朗读对话框显示「已播 / 丢 / 失败」三个数',
          'var_counts' in src2 and 'n_failed' in src2)
    check('C9 离线朗读对话框显示最近一条句子级错误',
          'last_sentence_error' in src2)
    check('C10 离线朗读对话框有「🔊 测试声音」按钮',
          '🔊 测试声音' in src2 and 'def _test_sound' in src2)
    check('C11 离线朗读对话框有「同时保存 wav」勾选',
          'var_dump' in src2 and '同时保存 wav' in src2)


# ══════════════════════════════════════════════════════════════════════
# D 组：worker CLI / 协议
# ══════════════════════════════════════════════════════════════════════
def group_d():
    section('D 组：worker 协议 / CLI')
    src = src_of('tts_worker.py')
    check('D1 worker 支持 --dump-dir',
          "'--dump-dir'" in src)
    check('D2 worker 支持 set_dump_dir 指令（运行时开关）',
          "cmd == 'set_dump_dir'" in src)
    check('D3 worker 支持 test_tone 指令',
          "cmd == 'test_tone'" in src)
    check('D4 worker 支持 telemetry 指令',
          "cmd == 'telemetry'" in src)
    check('D5 播放器不可用 ⇒ 发句子级 error（含 id）',
          '播放器不可用，音频未输出' in src)
    check('D6 无音频产出 ⇒ 不发 played（改发句子级 error）',
          '引擎没有产出任何音频' in src)
    check('D7 每句遥测写进 worker 日志',
          '遥测 id=%d' in src)
    check('D8 静音合成有显式标记',
          'silent_synth' in src and '静音合成' in src)
    check('D9 `_fmt_telemetry` 含峰值/RMS/NaN/回调/已读/欠载',
          all(k in src for k in ('peak=', 'rms_dbfs=', 'nan_inf=',
                                 'cb_delta=', 'read_delta=',
                                 'underflow_delta=')))
    check('D10 `played` 事件带遥测',
          "'telemetry': tel" in src)


# ══════════════════════════════════════════════════════════════════════
def main():
    print('APP-021 自检：把播放链路做成可观测（不加载模型）')
    print('=' * 72)
    try:
        group_a()
    except Exception:
        traceback.print_exc()
        check('A 组整体执行', False, traceback.format_exc()[-300:])
    try:
        group_b()
    except Exception:
        traceback.print_exc()
        check('B 组整体执行', False, traceback.format_exc()[-300:])
    try:
        group_c()
    except Exception:
        traceback.print_exc()
        check('C 组整体执行', False, traceback.format_exc()[-300:])
    try:
        group_d()
    except Exception:
        traceback.print_exc()
        check('D 组整体执行', False, traceback.format_exc()[-300:])
    try:
        group_e()
    except Exception:
        traceback.print_exc()
        check('E 组整体执行', False, traceback.format_exc()[-300:])

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print('\n' + '=' * 72)
    print('结果：%d PASS / %d FAIL（共 %d 项）' % (n_pass, n_fail, len(RESULTS)))
    print('=' * 72)
    if n_fail:
        print('\n失败项：')
        for name, ok, detail in RESULTS:
            if not ok:
                print('  ✗ %s  |  %s' % (name, detail))

    out = os.path.join(HERE, 'app076_tts_playback_observability.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('APP-021 自检：把播放链路做成可观测\n')
        f.write('时间：%s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write('结果：%d PASS / %d FAIL（共 %d 项）\n\n'
                % (n_pass, n_fail, len(RESULTS)))
        for name, ok, detail in RESULTS:
            f.write('%s  %s%s\n' % ('PASS' if ok else 'FAIL', name,
                                    ('  |  ' + detail) if detail else ''))
        f.write('\n--- 证据 ---\n')
        f.write(json.dumps(EVIDENCE, ensure_ascii=False, indent=2))
    print('\n证据已写入：%s' % out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
