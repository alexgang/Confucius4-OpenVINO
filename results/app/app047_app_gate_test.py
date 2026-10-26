r"""app047_app_gate_test.py —— App 侧本轮三项改动的**离线闸门**。

====================================================================
覆盖的三项改动
====================================================================
① **安静窗口闸门**（MT 通知 10 §10.6 / 通知 11 §11.3）
   `machine_lock_app.py` 的 `wait_quiet_window` + `pack_v13.py` /
   `publish_ftp.py` 的接入。
   （详细验收见 `app045_quiet_window_gate_test.py`，本脚本做**回归**。）

② **草稿↔正式稿匹配规则**（`live_caption/caption_render.py`）
   `match_draft_to_final` 改为「三级关系 + 反向拒绝 + 最短剩余正式稿优先
   + 全局一对一」，并用 **MT 真实产物**验证：
   - 段号倒流 **0** 条（独立判据：产品语义）；
   - 一个正式稿被多草稿共用 **0** 条；
   - 与「最小改动版」在真实语料上**逐条一致**。

③ **开发专用文件排除**（`pkg_exclude.py` + `pack_v13.py`）
   `__all__` 指向的三个名字此前**从未实现** ⇒ `from pkg_exclude import *`
   抛 `AttributeError`；本轮补齐，并新增 `app/` 下 `_` 前缀脚本的排除
   （实测客户包 v1.5 里有 `app/_probe_tts_cuda.py`，含开发机绝对路径）。

====================================================================
纪律
====================================================================
🔴 **不 import 被测模块**（`live_caption_app.py` 顶部 import numpy/openvino
   ⇒ import 阶段就可能 abort，try/except 接不住）
   ⇒ 本脚本只 import **纯 stdlib** 的模块：
   `caption_render`（只含 `re`）、`pkg_exclude`（只含 `os`/`re`）、
   `machine_lock_app`（stdlib + ctypes）。
🔴 **不跑推理 / 不测速 / 不占 GPU / 不取真实机器锁 / 不调 MiniMax**
🔴 **不写**客户包、不写 MT 目录 ⇒ 只读。
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
import time
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
sys.path.insert(0, REPO)          # `pkg_exclude` / `machine_lock_app` 在仓库根

import caption_render as CR      # noqa: E402  纯 stdlib
import pkg_exclude as PE         # noqa: E402  纯 stdlib
import pkg_paths as _pkg_paths  # noqa: E402  §48 单一数据源

OUT = os.path.join(HERE, 'app047_app_gate_evidence.json')
MT_ART = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\c111_v5_ts10_nopunct.json'

_results = []


def check(group, name, ok, detail=''):
    _results.append({'group': group, 'name': name,
                     'ok': bool(ok), 'detail': str(detail)[:400]})
    return bool(ok)


def _code_only(rel):
    """返回该文件的**真实代码**（剥掉注释与 docstring），用于内容检索。

    🔴 为什么需要：docstring / 注释里点名禁用串（例如「绝不用 tasklist /FI」）
       会造成误报 ⇒ 只搜真实代码。
    """
    path = os.path.join(REPO, rel)
    with io.open(path, 'rb') as f:
        src = f.read()
    # 去注释
    out = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok)
        code = tokenize.untokenize(out)
    except Exception:
        code = src.decode('utf-8', 'replace')
    # 去 docstring
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body.pop(0)
        return ast.unparse(tree)
    except Exception:
        return code


# ══════════════════════════════════════════════════════════════════════
# ① 安静窗口闸门（回归）
# ══════════════════════════════════════════════════════════════════════
def run_gate_quiet():
    import machine_lock_app as ML
    check('GATE', 'Q1 wait_quiet_window 存在',
          hasattr(ML, 'wait_quiet_window'), '')
    check('GATE', 'Q2 list_processes 存在',
          hasattr(ML, 'list_processes'), '')
    check('GATE', 'Q3 LockHeld.wait_quiet 存在',
          hasattr(ML.LockHeld, 'wait_quiet'), '')
    # 真实执行一次（只看是否存在别的 python 进程，不干预）
    ok, info = ML.wait_quiet_window(quiet_seconds=1.0, timeout=5.0, poll=1.0,
                                    verbose=False)
    check('GATE', 'Q4 wait_quiet_window 可执行且返回结构完整',
          isinstance(ok, bool) and isinstance(info, dict)
          and 'n_samples' in info and 'n_busy_samples' in info
          and 'waited_s' in info,
          f'ok={ok} keys={sorted(info.keys())[:12]}')
    # 接线
    for rel, needle in (('pack_v13.py', 'wait_quiet'),
                        ('publish_ftp.py', 'wait_quiet')):
        code = _code_only(rel)
        check('GATE', f'Q5 {rel} 接入安静窗口',
              'wait_quiet' in code and 'skip_quiet' in code, '')
    # 绝不用 tasklist
    for rel in ('machine_lock_app.py', 'pack_v13.py', 'publish_ftp.py'):
        code = _code_only(rel)
        check('GATE', f'Q6 {rel} 代码里绝不用 tasklist',
              'tasklist' not in code, '')


# ══════════════════════════════════════════════════════════════════════
# ② 草稿↔正式稿匹配规则
# ══════════════════════════════════════════════════════════════════════
def run_gate_match():
    # R-A 反向拒绝：正式稿是草稿的前缀（更短）⇒ 不得配对
    m = CR.match_draft_to_final(
        [{'src': 'we should go now'}],
        [{'src': 'we should go'}])
    check('MATCH', 'M1 反向拒绝（正式 ⊂ 草稿 ⇒ 不配）',
          m == {}, f'match={m}')

    # R-B 方向性前缀成立
    m = CR.match_draft_to_final(
        [{'src': 'we should go'}],
        [{'src': 'we should go now with the plan.'}])
    check('MATCH', 'M2 方向性前缀成立（草稿 ⊂ 正式）',
          m == {0: 0}, f'match={m}')

    # R-C 最短剩余正式稿优先
    m = CR.match_draft_to_final(
        [{'src': 'we should go'}],
        [{'src': 'we should go now with the release plan for Q3.'},
         {'src': 'we should go now.'}])
    check('MATCH', 'M3 最短剩余正式稿优先',
          m == {0: 1}, f'match={m}')

    # R-D 全局一对一
    m = CR.match_draft_to_final(
        [{'src': 'we should go'}, {'src': 'we should'}],
        [{'src': 'we should go now.'}])
    check('MATCH', 'M4 全局一对一（一个正式稿只被一个草稿占）',
          len(m) == len(set(m.values())), f'match={m}')

    # R-E 确定性
    a = CR.match_draft_to_final(
        [{'src': 'a b c'}, {'src': 'a b'}],
        [{'src': 'a b c d'}, {'src': 'a b c'}])
    b = CR.match_draft_to_final(
        [{'src': 'a b c'}, {'src': 'a b'}],
        [{'src': 'a b c d'}, {'src': 'a b c'}])
    check('MATCH', 'M5 确定性（同样输入 → 同样输出）', a == b, f'{a} vs {b}')

    # ── 真实语料（MT 产物）验证 ──────────────────────────────────
    if not os.path.exists(MT_ART):
        check('MATCH', 'M6 MT 真实产物存在', False, MT_ART)
        return
    art = json.load(io.open(MT_ART, encoding='utf-8'))
    units = art['results']['C_draft']['units']
    drafts = [u for u in units if (u.get('kind') or 'final') == 'draft']
    finals = [u for u in units if (u.get('kind') or 'final') != 'draft']
    m = CR.match_draft_to_final(drafts, finals)

    # 独立判据：段号单调性
    n_viol = 0
    for di, fi in m.items():
        ds, fs = drafts[di].get('seg'), finals[fi].get('seg')
        if isinstance(ds, int) and isinstance(fs, int) and fs < ds:
            n_viol += 1
    check('MATCH', 'M6 真实语料：段号倒流 0 条（产品语义判据）',
          n_viol == 0, f'n_violation={n_viol} n_pairs={len(m)}')

    used = {}
    for di, fi in m.items():
        used.setdefault(fi, []).append(di)
    n_multi = sum(1 for v in used.values() if len(v) > 1)
    check('MATCH', 'M7 真实语料：一个正式稿不被多草稿共用',
          n_multi == 0, f'n_multi={n_multi}')

    check('MATCH', 'M8 真实语料：配对数 ≥ 90（覆盖率不显著回退）',
          len(m) >= 90, f'n_pairs={len(m)} n_draft={len(drafts)}')

    # 与「最小改动版」在真实语料上逐条一致
    def minimal(dr, fs):
        cands = []
        for di, d in enumerate(dr):
            dn = CR.norm_src(d.get('src', ''))
            if not dn:
                continue
            for fi, f in enumerate(fs):
                fn = CR.norm_src(f.get('src', ''))
                if not fn:
                    continue
                if dn == fn:
                    rank = 0
                elif fn.startswith(dn) and len(fn) > len(dn):
                    rank = 1
                elif dn in fn:
                    rank = 2
                else:
                    continue
                cands.append((rank, -len(dn), len(fn), di, fi))
        cands.sort()
        out, used_f = {}, set()
        for _r, _n, _fl, di, fi in cands:
            if di in out or fi in used_f:
                continue
            out[di] = fi
            used_f.add(fi)
        return out
    check('MATCH', 'M9 真实语料：与「最小改动版」逐条一致',
          m == minimal(drafts, finals),
          f'shipped={len(m)} minimal={len(minimal(drafts, finals))}')


# ══════════════════════════════════════════════════════════════════════
# ③ 开发专用文件排除
# ══════════════════════════════════════════════════════════════════════
def run_gate_exclude():
    # T-A `__all__` 里每个名字都真实存在
    missing = [n for n in PE.__all__ if not hasattr(PE, n)]
    check('EXCLUDE', 'E1 pkg_exclude.__all__ 无悬空名字',
          not missing, f'missing={missing}')

    # T-B `from pkg_exclude import *` 不抛异常
    ns = {}
    try:
        exec('from pkg_exclude import *', ns)
        ok = True
        err = ''
    except Exception as e:
        ok = False
        err = f'{type(e).__name__}: {e}'
    check('EXCLUDE', 'E2 `from pkg_exclude import *` 可执行', ok, err)

    # T-C 开发探针被排除
    check('EXCLUDE', 'E3 app/_probe_tts_cuda.py 被排除',
          PE.is_app_dev_only('app/_probe_tts_cuda.py')
          and PE.is_excluded('app/_probe_tts_cuda.py'), '')

    # T-D 客户自检脚本不被误伤
    check('EXCLUDE', 'E4 app/selftest_audio_sources.py 不被误伤',
          not PE.is_app_dev_only('app/selftest_audio_sources.py')
          and not PE.is_excluded('app/selftest_audio_sources.py'), '')

    # T-E 正常代码不被误伤
    ok = all(not PE.is_excluded(p) for p in (
        'app/live_caption_app.py', 'app/translator.py', 'app/tts_engine.py',
        'app/tts_worker.py', 'app/device_config.py'))
    check('EXCLUDE', 'E5 正常 App 代码不被误伤', ok, '')

    # T-F 规则只管 app/ 下
    check('EXCLUDE', 'E6 规则只作用于 app/（results/ 不受影响）',
          not PE.is_app_dev_only('results/_tmp.py')
          and not PE.is_excluded('results/_tmp.py'), '')

    # T-G pack_v13 的硬校验里必须有这条断言
    code = _code_only('pack_v13.py')
    check('EXCLUDE', 'E7 pack_v13 硬校验含「开发专用脚本」断言',
          'is_app_dev_only' in code and '开发专用脚本' in code, '')

    # T-H 真实客户包现状：v1.5 里确实有那个探针
    pkg = _pkg_paths.discover_pkg_dir()
    probe = os.path.join(pkg, 'app', '_probe_tts_cuda.py')
    if os.path.exists(pkg):
        check('EXCLUDE', 'E8 客户包 v1.5 现状含开发探针（⇒ 本轮规则有真实靶子）',
              os.path.exists(probe), f'{probe} exists={os.path.exists(probe)}')
        # 新规则下它会被剔出进包清单
        rels = [rel for rel, _ in PE.iter_package_files(pkg)]
        check('EXCLUDE', 'E9 新规则下客户包清单**不含**开发探针',
              'app/_probe_tts_cuda.py' not in rels, '')
        check('EXCLUDE', 'E10 新规则下客户包清单**仍含** selftest_audio_sources.py',
              'app/selftest_audio_sources.py' in rels, '')
    else:
        check('EXCLUDE', 'E8 客户包目录不存在（跳过现状核对）', True, pkg)


def main():
    t0 = time.time()
    run_gate_quiet()
    run_gate_match()
    run_gate_exclude()
    real = [r for r in _results if r['group'] != 'BUG']
    n_pass = sum(1 for r in real if r['ok'])

    payload = {
        'task': 'App 侧本轮三项改动（安静窗口闸门 / 匹配规则 / 开发专用文件排除）的离线闸门',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'discipline': {
            'no_model_import': True, 'no_inference': True, 'no_benchmark': True,
            'no_gpu': True, 'no_real_machine_lock': True, 'no_minimax': True,
            'no_write_to_pkg_or_mt': True,
        },
        'summary': {
            'total': len(real), 'pass': n_pass,
            'fail': len(real) - n_pass,
            'verdict': 'PASS' if n_pass == len(real) else 'FAIL',
            'elapsed_s': round(time.time() - t0, 3),
        },
        'results': _results,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    for r in _results:
        flag = 'PASS' if r['ok'] else 'FAIL'
        print(f"[{r['group']:7s}] {flag}  {r['name']}"
              + (f"   | {r['detail']}" if not r['ok'] and r['detail'] else ''))
    print(f"\n{n_pass}/{len(real)} PASS | verdict={payload['summary']['verdict']}")
    print(f"evidence -> {OUT}")
    return 0 if payload['summary']['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
