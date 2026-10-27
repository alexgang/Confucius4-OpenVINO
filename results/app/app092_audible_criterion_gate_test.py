# -*- coding: utf-8 -*-
"""app092_audible_criterion_gate_test.py —— §62 的验收（**不加载模型**）。

验三件事：
① **REAL 组**：新判据模块 + 类别闸门确实落地且**能拦住**违规；
② **BUG 反证组**：用**固定 commit** 的旧脚本跑**同一条闸门** ⇒ 必须命中
   ⇒ 证明「缺陷曾真实存在」且「闸门确实拦得住」（§31 的教训：
   反证基线**不能**用 HEAD，也不能依赖临时备份目录）；
③ **回归**：`app076` 的既有 38 项断言**全部未回归**。

🔴 反证基线用**固定 commit SHA** `e2d7bc2`（app071 引入弱判据的那个提交）
⇒ 两边都不会失效（HEAD 变修复版也不影响反证）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import traceback

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PY = sys.executable

RESULTS = []
EVIDENCE = {}

# 🔴 固定基线 commit（**不是 HEAD**）⇒ §31 教训
BASELINE_COMMIT = 'e2d7bc2'

WEAK_SCRIPTS = (
    'results/app/app071_tts_worker_error_probe.py',
    'results/app/app074_tts_e2e_cp936.py',
    'results/app/app075_gui_offline_read_real.py',
    'results/app/app077_tts_acceptance_ab.py',
    'results/app/app039_tts_e2e_smoke.py',
)


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(('  PASS  ' if ok else '  FAIL  ') + name + (
        ('  |  ' + detail) if detail else ''))
    return bool(ok)


def section(t):
    print('\n' + '=' * 72)
    print(t)
    print('=' * 72)


def find_weak_criteria(code: str):
    """AST 级找出「用 `n_played` 与 0/1 比较」的代码行。

    🔴 §62：**规则来自 `audible_criterion_lint`（单一事实来源）**
       ⇒ 本验收与 `app076` 的 E 组跑**同一条规则** ⇒ 不会互相矛盾。
    ⚠️ **不剥注释**：`ast.parse` 本来就不含注释节点；手工剥行会
       **破坏多行字符串** ⇒ 解析失败 ⇒ 覆盖面悄悄缩水。
    """
    return _LINT['find_weak_criteria'](code)


def _load_lint():
    """加载 `audible_criterion_lint`（独立 exec，不 import 被测模块）。"""
    p = os.path.join(HERE, 'audible_criterion_lint.py')
    ns = {'__name__': 'lint_probe'}
    exec(compile(open(p, encoding='utf-8').read(), p, 'exec'), ns)
    return ns


_LINT = None


def git_show(rel: str, commit: str) -> str:
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    return r.stdout if r.returncode == 0 else ''


def main() -> int:
    global _LINT
    print('§62 验收：弱判据缺陷类别（APP-021⑦ 的直接执行）')
    # 🔴 扫描器**单一来源**（app076 的 E 组也用它 ⇒ 两边不会互相矛盾）
    try:
        _LINT = _load_lint()
    except Exception as e:
        print('🔴 无法加载 audible_criterion_lint：%r' % (e,))
        return 1
    section('A 组（REAL）：判据模块 + 类别闸门')

    # ── A1：判据模块存在且可独立 exec ────────────────────────────────
    crit = os.path.join(HERE, 'tts_audible_criterion.py')
    check('A1 判据模块存在', os.path.isfile(crit), crit)
    if not os.path.isfile(crit):
        return 1
    csrc = open(crit, encoding='utf-8').read()
    ns = {'__name__': 'crit_probe'}
    try:
        exec(compile(csrc, crit, 'exec'), ns)
        check('A2 判据模块可独立 exec（不 import 被测模块）', True)
    except Exception as e:
        check('A2 判据模块可独立 exec（不 import 被测模块）', False,
              '%s: %s' % (type(e).__name__, e))
        return 1
    ev = ns['evaluate_audible']
    av = ns['audible_verdict']

    ok, r = ev({'n_samples': 120960, 'read_delta': 120960, 'peak': 0.523438})
    check('A3 合格遥测 ⇒ 通过', ok is True, str(r))
    ok, r = ev(None)
    check('A4 无遥测 ⇒ 失败（缺证据不放行）', ok is False, str(r))
    ok, r = ev({'n_samples': 120960, 'read_delta': 68608, 'peak': 0.523438})
    check('A5 read_delta 不足 ⇒ 失败', ok is False, str(r))
    ok, r = ev({'n_samples': 120960, 'read_delta': 120960, 'peak': 1e-4})
    check('A6 峰值过低 ⇒ 失败', ok is False, str(r))
    ok, r = ev({'peak': 0.5})
    check('A7 缺字段 ⇒ 失败', ok is False, str(r))
    v = av({'n_samples': 100, 'read_delta': 100, 'peak': 0.5})
    check('A8 判定文本**不**宣称用户听得见', ('不代表用户听得见' in v), v[:90])

    # ── A9：REAL 组脚本里**已无**弱判据 ─────────────────────────────
    viol = []
    for rel in WEAK_SCRIPTS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            viol.append('%s（不存在）' % rel)
            continue
        hits = find_weak_criteria(open(p, encoding='utf-8').read())
        if hits is None:
            # 🔴 解析失败 ⇒ 闸门失效 ⇒ 必须判 FAIL（不能算「无违规」）
            viol.append('%s（源码无法解析 ⇒ 闸门失效）' % os.path.basename(rel))
            continue
        for m in hits:
            viol.append('%s: %s' % (os.path.basename(rel), m))
    check('A9 5 个脚本都已改用硬判据（无 `n_played >= 1`）', not viol,
          '；'.join(viol[:8]))
    EVIDENCE['A9_violations'] = viol

    # ── A10：判据模块被 5 个脚本**真的引用** ─────────────────────────
    used = []
    for rel in WEAK_SCRIPTS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if os.path.isfile(p):
            src = open(p, encoding='utf-8').read()
            if 'tts_audible_criterion' in src:
                used.append(os.path.basename(rel))
    check('A10 5 个脚本都引用了判据单一来源', len(used) == len(WEAK_SCRIPTS),
          '%d/%d %s' % (len(used), len(WEAK_SCRIPTS), used))
    EVIDENCE['A10_used'] = used

    # ── A11：🔴🔴 **「等本句」必须用相对增量**（这是本轮的核心修复）──
    #   缺陷：`n_played` 是**累计计数** ⇒ `>= 1` 只说明「从服务启动到现在
    #   至少播过一句」⇒ 提交第 ② 句后它**立刻**成立 ⇒ **本句还没出声就被
    #   判成出声了** ⇒ 假通过。
    #   ⇒ 必须能证明：**提交前的基线**能挡住这种「历史计数」。
    crit_ns = {'__name__': 'crit_probe2'}
    exec(compile(csrc, crit, 'exec'), crit_ns)
    sp = crit_ns['sentence_played']
    ps = crit_ns['played_snapshot']

    # 场景 1：提交前已播过 1 句（n_played=1），提交后**还没播**本句
    st_old = dict(n_played=1, last_telemetry={'n_samples': 100,
                                              'read_delta': 100, 'peak': 0.5,
                                              'id': 7})
    ok1, why1 = sp(st_old, played_before=1, telemetry_id_before=7)
    check('A11 提交前已播过别的句 ⇒ 本句未播 ⇒ 判「未播完」（防假通过）',
          ok1 is False, why1)

    # 场景 2：提交前 n_played=1，本句真的播完了（计数 1→2 且遥测 id 变了）
    st_new = dict(n_played=2, last_telemetry={'n_samples': 120960,
                                              'read_delta': 120960,
                                              'peak': 0.523438, 'id': 8})
    ok2, why2 = sp(st_new, played_before=1, telemetry_id_before=7)
    check('A12 本句真播完（相对增量 + 新遥测）⇒ 判「播完」',
          ok2 is True, why2)

    # 场景 3：🔴 遥测 id **没变**（是旧句/测试音的遥测）⇒ 必须判「未播完」
    st_stale = dict(n_played=2, last_telemetry={'n_samples': 100,
                                                'read_delta': 100,
                                                'peak': 0.5, 'id': 7})
    ok3, why3 = sp(st_stale, played_before=1, telemetry_id_before=7)
    check('A13 遥测 id 未变（旧的/测试音的遥测）⇒ 判「未播完」',
          ok3 is False, why3)

    # 场景 4：没有遥测 ⇒ 判「未播完」（缺证据不放行）
    ok4, why4 = sp(dict(n_played=2, last_telemetry=None),
                   played_before=1, telemetry_id_before=7)
    check('A14 没有遥测 ⇒ 判「未播完」（缺证据不放行）', ok4 is False, why4)

    # 场景 5：`played_snapshot` 能正确取基线
    snap = ps(dict(n_played=3, last_telemetry={'id': 11}))
    check('A15 played_snapshot 正确取基线（计数 + 遥测 id）',
          snap == (3, 11), repr(snap))
    EVIDENCE['A11_A15_wait_vs_judge'] = dict(
        old=why1, new=why2, stale=why3, none=why4, snapshot=repr(snap))

    # ── A16：5 个脚本**真的**用了相对增量（源码级）──────────────────
    no_snapshot = []
    for rel in WEAK_SCRIPTS:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        src = open(p, encoding='utf-8').read()
        if 'played_snapshot(' not in src or 'sentence_played(' not in src:
            no_snapshot.append(os.path.basename(rel))
    check('A16 5 个脚本都改用「相对增量」等待（played_snapshot/sentence_played）',
          not no_snapshot, '未改：%s' % no_snapshot)
    EVIDENCE['A16_not_converted'] = no_snapshot

    section('B 组（BUG 反证）：固定基线 %s 的旧脚本 ⇒ 闸门必须命中'
            % BASELINE_COMMIT)

    # ── B1：基线里 app071 确实有弱判据 ───────────────────────────────
    base71 = git_show('results/app/app071_tts_worker_error_probe.py',
                       BASELINE_COMMIT)
    if not base71:
        check('B1 取到基线 app071', False, 'git show %s 失败' % BASELINE_COMMIT)
    else:
        hits = find_weak_criteria(base71)
        check('B1 基线 app071 确实用「n_played >= 1」判定出声',
              hits is not None and len(hits) >= 1,
              '%s' % (hits[:2] if hits else hits))
        EVIDENCE['B1_baseline_hits'] = hits

    # ── B2：基线里**没有**判据单一来源 ───────────────────────────────
    base_crit = git_show('results/app/tts_audible_criterion.py',
                         BASELINE_COMMIT)
    check('B2 基线里**不存在**判据单一来源模块', base_crit == '',
          '长度=%d' % len(base_crit))

    # ── B3：基线里 app071 的判定文案是旧的弱文案 ─────────────────────
    if base71:
        check('B3 基线 app071 用的是旧文案「OK 语音输出正常」',
              'OK 语音输出正常' in base71)
        check('B4 基线 app071 **没有**引用判据模块',
              'tts_audible_criterion' not in base71)

    # ── B5：把基线的 app071 放进**影子目录** ⇒ 跑同一条闸门 ⇒ 必须命中
    #   ⚠️ 影子目录 ⇒ 不碰工作区（§44 教训：验收候选代码要造影子目录）
    with tempfile.TemporaryDirectory() as td:
        shadow = os.path.join(td, 'results', 'app')
        os.makedirs(shadow, exist_ok=True)
        for rel in WEAK_SCRIPTS:
            base = git_show(rel, BASELINE_COMMIT)
            if base:
                dst = os.path.join(shadow, os.path.basename(rel))
                io.open(dst, 'w', encoding='utf-8', newline='\n').write(base)
        # 影子里**不放**判据模块 ⇒ 模拟「缺陷还在、闸门还没建」的状态
        #   ⇒ 闸门脚本若存在但只扫影子目录，应命中
        viol_shadow = []
        for rel in WEAK_SCRIPTS:
            p = os.path.join(shadow, os.path.basename(rel))
            if not os.path.isfile(p):
                continue
            src = open(p, encoding='utf-8').read()
            for m in (find_weak_criteria(src) or []):
                viol_shadow.append('%s: %s' % (os.path.basename(rel), m))
        check('B5 影子目录（基线脚本）⇒ 闸门命中弱判据',
              len(viol_shadow) >= 1, '%d 处：%s'
              % (len(viol_shadow), viol_shadow[:3]))
        EVIDENCE['B5_shadow_violations'] = viol_shadow

    section('C 组：回归 —— app076 既有断言未回归')
    r = subprocess.run([PY, os.path.join(HERE,
                                         'app076_tts_playback_observability.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    tail = r.stdout[-1200:]
    check('C1 app076 退出码 0', r.returncode == 0, 'rc=%d' % r.returncode)
    check('C2 app076 全部 PASS（0 FAIL）',
          '0 FAIL' in (r.stdout or ''), tail[-300:])
    m = None
    for ln in (r.stdout or '').splitlines():
        if ln.startswith('结果：'):
            m = ln.strip()
            break
    check('C3 app076 断言数 ≥ 49（原 47 + 新增 E8/E9/E10 三项闸门）',
          bool(m) and '49' in m, m or '（未解析到）')
    EVIDENCE['C3_app076_summary'] = m

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

    out = os.path.join(HERE, 'app092_audible_criterion_gate_evidence.json')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(
            baseline_commit=BASELINE_COMMIT,
            verdict='PASS' if n_fail == 0 else 'FAIL',
            n_pass=n_pass, n_fail=n_fail,
            checks=[dict(name=n, ok=o, detail=d) for n, o, d in RESULTS],
            evidence=EVIDENCE,
        ), f, ensure_ascii=False, indent=1)
    print('\n证据已写入：%s' % out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
