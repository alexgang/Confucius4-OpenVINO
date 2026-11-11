# -*- coding: utf-8 -*-
"""APP-099 四.1 / 四.2：判据修正后的重判证据（不重跑设备作业、不占设备）。

性质说明（APP-099 二.l 禁止「巡检轮自建审计/闸门脚本」）：
    这不是新增守卫，而是对本轮**验收脚本判据本体缺陷**的定点修正复核。
    旧判据三处错：
      ① rec['pass'] = all(checks.values())      —— 完全不看 exit_code
      ② verdict 只数 GPU 臂「个数」            —— 不看退出状态
      ③ timing_valid 无条件写死 True           —— 从不复核
    后果：gpu_control_asr_npu 被 wait(timeout=1500) 后 p.kill() 强杀
    （rc=-9，框架超时强杀，非程序自崩）仍被判 pass=True / verdict=PASS /
    timing_valid=true。

方法（对齐项目「AST 直读表 + 真跑被测函数 + 反证组」判据）：
    · 用 ast 从修好的 _app437 中抽出 run_one 的判定片段、main.finalbody
      的 verdict/timing 片段，compile 后真跑，不手抄第二份判据；
    · 对本轮已落盘的 app437_app099_device.json 原始数据重算结论；
    · 7 组反证验证新判据能被识破、且旧判据确实识破不了；
    · 原始 app437 json 保持 write-once，不改写、不删字段。
"""
import ast
import copy
import hashlib
import json
import os
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(HERE, '_app437_app099_device_jobs.py')
RAW = os.path.join(HERE, 'app437_app099_device.json')
DEV = os.path.join(HERE, 'app437_app099_device')
OUT = os.path.join(HERE, 'app452_app099_device_verdict_recheck.json')


def _true_run_fragments(src):
    """从验收脚本里抽出两段判据代码，返回可 exec 的两个 code 对象。"""
    tree = ast.parse(src)
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    # ── 片段 1：run_one 里的退出状态分类 + pass 修正 ──
    run_one = fns['run_one']
    seg1 = []
    for n in run_one.body:
        if isinstance(n, ast.Assign):
            tgt = n.targets[0]
            key = (tgt.slice.value
                   if isinstance(tgt, ast.Subscript)
                   and isinstance(tgt.slice, ast.Constant) else None)
            if key in ('exit_code', 'seconds', 'cmd', 'pass_components_only',
                       'terminated_by_harness', 'crash', 'crash_at_s',
                       'natural_exit', 'pass'):
                seg1.append(n)
    m1 = ast.fix_missing_locations(ast.Module(body=seg1, type_ignores=[]))
    code1 = compile(m1, '<app437:run_one_judge>', 'exec')

    # ── 片段 2：main.finalbody 里的 ok_arms / timing / verdict ──
    main = fns['main']
    trys = [n for n in ast.walk(main) if isinstance(n, ast.Try) and n.finalbody]
    fb = max(trys, key=lambda n: len(n.finalbody)).finalbody
    lo = min(n.lineno for n in fb if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'all_arms'
                     for t in n.targets))
    hi = max(n.lineno for n in fb if isinstance(n, ast.Assign)
             and isinstance(n.targets[0], ast.Subscript)
             and isinstance(n.targets[0].slice, ast.Constant)
             and n.targets[0].slice.value == 'verdict')
    seg2 = [n for n in fb if lo <= n.lineno <= hi]
    m2 = ast.fix_missing_locations(ast.Module(body=seg2, type_ignores=[]))
    code2 = compile(m2, '<app437:final_verdict>', 'exec')
    return code1, code2, len(seg1), len(seg2)


def run_one_judge(code, rec, rc):
    """真跑 run_one 判定片段（时间桩保证确定性）。"""
    ns = {'rec': rec, 'rc': rc, 'cmd': [], 't0': 0.0,
          'time': types.SimpleNamespace(time=lambda: 0.0)}
    exec(code, ns)
    return ns['rec']


def final_verdict(code, ev):
    """真跑 main.finalbody 判据片段。"""
    ns = {'ev': ev, 'sum': sum, 'len': len}
    exec(code, ns)
    return ns['ev']


def old_verdict(ev):
    """旧判据（只数臂数、不看 GPU 臂退出状态、timing 恒 True）。"""
    ok = sum(1 for a in ev['arms'] if a['pass'] and a['exit_code'] == 0)
    return ('PASS' if len(ev['arms']) == 6 and ok == 6
            and len(ev['gpu_arms']) == 2 else 'PARTIAL'), True


def stall_evidence(name):
    """从采样 jsonl 量化「收尾停滞」：后段是否恒定。"""
    p = os.path.join(DEV, name + '_samples.jsonl')
    rows = [json.loads(x) for x in open(p, encoding='utf-8') if x.strip()]
    tail = rows[int(len(rows) * 0.5):]
    sh = sorted({round((r.get('gpu_shared_bytes') or 0) / 2 ** 20, 1) for r in tail})
    rs = sorted({round((r.get('proc_rss_bytes') or 0) / 2 ** 20, 1) for r in tail})
    return {
        'n_samples': len(rows),
        't_last_s': rows[-1].get('t_s'),
        'n_distinct_shared_mb_in_late_half': len(sh),
        'n_distinct_rss_mb_in_late_half': len(rs),
        'late_half_shared_mb_minmax': [sh[0], sh[-1]] if sh else None,
        'late_half_rss_mb_minmax': [rs[0], rs[-1]] if rs else None,
        'flat_in_late_half': bool(len(sh) == 1 and len(rs) == 1),
    }


def main():
    src = open(SCRIPT, encoding='utf-8').read()
    raw = json.load(open(RAW, encoding='utf-8'))
    ev = {
        'source': 'results/app/app437_app099_device.json',
        'source_sha256': hashlib.sha256(open(RAW, 'rb').read()).hexdigest(),
        'source_verdict_field': 'verdict',
        'source_verdict_value': raw['verdict'],
        'source_timing_valid_field': 'timing_valid',
        'source_timing_valid_value': raw['timing_valid'],
        'purpose': '判据修正复核（非新增审计闸门）；不重跑设备作业',
    }

    # ── 脚本判据锚点 + 语法 ──
    anchors = [
        "rec['pass_components_only'] = rec['pass']",
        "rec['terminated_by_harness'] = (rc == -9)",
        "rec['crash'] = (rc != 0 and rc != -9)",
        "rec['natural_exit'] = (rc == 0)",
        "rec['pass'] = bool(rec['pass'] and rc == 0)",
        "ev['timing_valid'] = (len(non_natural) == 0)",
        "and ev['timing_valid'] else 'PARTIAL')",
    ]
    ev['script_fix'] = {
        'file': 'results/app/_app437_app099_device_jobs.py',
        'sha256': hashlib.sha256(src.encode('utf-8')).hexdigest(),
        'ast_parse': True,
        'anchors': {a: (a in src) for a in anchors},
        'all_anchors_present': all(a in src for a in anchors),
    }
    code1, code2, n1, n2 = _true_run_fragments(src)
    ev['script_fix']['n_stmts_run_one'] = n1
    ev['script_fix']['n_stmts_final_verdict'] = n2

    # ── 真跑修正后判据（对原始已落盘数据重算）──
    fixed = copy.deepcopy(raw)
    fixed = final_verdict(code2, fixed)
    old_v, old_t = old_verdict(copy.deepcopy(raw))
    ev['old_criterion'] = {
        'recomputed_verdict': old_v, 'recomputed_timing_valid': old_t,
        'note': '旧判据只数臂数、timing 恒 True ⇒ 识破不了被框架强杀的对照臂',
    }
    ev['fixed_criterion'] = {
        'verdict': fixed['verdict'],
        'timing_valid': fixed['timing_valid'],
        'timing_notes': fixed['timing_notes'],
        'n_arms': fixed['n_arms'], 'n_arms_ok': fixed['n_arms_ok'],
        'n_gpu_arms': fixed['n_gpu_arms'],
        'n_gpu_arms_ok': fixed['n_gpu_arms_ok'],
    }

    # ── 逐臂退出状态分类（真跑 run_one 片段）──
    cls = {}
    for a in raw['arms'] + raw['gpu_arms']:
        r = run_one_judge(code1, {'pass': a['pass'],
                                 'checks': a.get('checks', {})}, a['exit_code'])
        cls[a['arm']] = {
            'exit_code': a['exit_code'], 'seconds': a['seconds'],
            'pass_components_only': r['pass_components_only'],
            'pass_after_fix': r['pass'],
            'crash': r['crash'],
            'terminated_by_harness': r['terminated_by_harness'],
            'natural_exit': r['natural_exit'],
        }
    ev['arm_classification'] = cls

    # ── 反证组 ──
    neg = []

    def add(name, mutate, expect_v, expect_t, note):
        e = copy.deepcopy(raw)
        mutate(e)
        got = final_verdict(code2, e)
        det = (got['verdict'] == expect_v and got['timing_valid'] == expect_t)
        neg.append({'name': name, 'expect_verdict': expect_v,
                    'expect_timing_valid': expect_t,
                    'got_verdict': got['verdict'],
                    'got_timing_valid': got['timing_valid'],
                    'detected': det, 'note': note})

    def set_exit(arm, rc):
        def f(e):
            for a in e['arms'] + e['gpu_arms']:
                if a['arm'] == arm:
                    a['exit_code'] = rc
        return f

    add('b_arm_to_exit0', set_exit('gpu_control_asr_npu', 0),
        'PASS', True, '把被强杀的对照臂改成自然退出 ⇒ 修正后判据应升为 PASS')
    add('a_arm_to_minus9', set_exit('gpu_same_asr_mt', -9),
        'PARTIAL', False, '把自然退出的 A 臂改成 -9 ⇒ 必须识破')
    add('smoke_arm_to_minus9', set_exit('mt_npu', -9),
        'PARTIAL', False, '六臂冒烟之一改成 -9 ⇒ 必须识破')

    # 旧判据对真实数据仍给 PASS ⇒ 证明旧判据确实识破不了
    neg.append({'name': 'old_criterion_misses_timeout_arm',
                'expect': '旧判据会漏判（仍得 PASS）',
                'got_verdict': old_v, 'got_timing_valid': old_t,
                'detected': bool(old_v == 'PASS' and old_t is True),
                'note': '若旧判据也变 PARTIAL，说明反证构造有问题'})

    # run_one 片段的三态反证
    for name, rc, exp in (
            ('run_one_rc_minus9', -9,
             {'pass': False, 'crash': False,
              'terminated_by_harness': True, 'natural_exit': False}),
            ('run_one_rc_zero', 0,
             {'pass': True, 'crash': False,
              'terminated_by_harness': False, 'natural_exit': True}),
            ('run_one_rc_one', 1,
             {'pass': False, 'crash': True,
              'terminated_by_harness': False, 'natural_exit': False})):
        r = run_one_judge(code1, {'pass': True, 'checks': {'x': True}}, rc)
        got = {k: r[k] for k in exp}
        neg.append({'name': name, 'rc': rc, 'expect': exp, 'got': got,
                    'detected': bool(got == exp),
                    'note': 'checks 恒真；只有 exit_code 变化，验证三态分类与 pass'})

    ev['negative_controls'] = neg
    ev['n_neg'] = len(neg)
    ev['n_neg_detected'] = sum(1 for x in neg if x['detected'])

    # ── 两 GPU 臂的事实数字（全部指到原始文件 + 字段）──
    by = {a['arm']: a for a in raw['gpu_arms']}
    a_arm, b_arm = by['gpu_same_asr_mt'], by['gpu_control_asr_npu']
    ev['gpu_arm_a'] = {
        'arm': 'gpu_same_asr_mt',
        'combo': 'ASR gpu_int8 + MT GPU.0 + TTS NPU（B 机 268 s 崩溃的组合）',
        'exit_code': a_arm['exit_code'], 'seconds': a_arm['seconds'],
        'crash_after_fix': cls['gpu_same_asr_mt']['crash'],
        'natural_exit': cls['gpu_same_asr_mt']['natural_exit'],
        'peak_gpu_dedicated_mb': a_arm['sampling']['peak_gpu_dedicated_mb'],
        'peak_gpu_shared_mb': a_arm['sampling']['peak_gpu_shared_mb'],
        'peak_proc_rss_mb': a_arm['sampling']['peak_proc_rss_mb'],
        'n_samples': a_arm['sampling']['n_samples'],
        'field_path': 'app437_app099_device.json → gpu_arms[gpu_same_asr_mt].sampling.*',
        'conclusion': 'A 机 806.3 s 自然退出、无崩溃 ⇒ 未复现 B 机 268 s 崩溃；'
                      'Dedicated 恒 0 是 Intel 集显 UMA，显存计入 Shared（见 app450）',
    }
    ev['gpu_arm_b'] = {
        'arm': 'gpu_control_asr_npu',
        'combo': 'ASR NPU + MT GPU.0 + TTS NPU（对照）',
        'exit_code': b_arm['exit_code'], 'seconds': b_arm['seconds'],
        'terminated_by_harness': cls['gpu_control_asr_npu']['terminated_by_harness'],
        'crash_after_fix': cls['gpu_control_asr_npu']['crash'],
        'peak_gpu_shared_mb': b_arm['sampling']['peak_gpu_shared_mb'],
        'peak_proc_rss_mb': b_arm['sampling']['peak_proc_rss_mb'],
        'n_samples': b_arm['sampling']['n_samples'],
        'stall': stall_evidence('gpu_control_asr_npu'),
        'field_path': 'app437_app099_device.json → gpu_arms[gpu_control_asr_npu]；'
                      'app437_app099_device/gpu_control_asr_npu_samples.jsonl',
        'conclusion': 'rc=-9 是本脚本 wait(timeout=1500) 后 p.kill() 强杀，'
                      '不是被测程序自崩；日志显示 ASR/MT 已完成（600.4 s / 145 句译文），'
                      '但采样后半段 Shared/RSS 恒定、日志停在 TTS 跳句循环 ⇒ 收尾未退出，'
                      '该臂与自然退出的 A 臂不可比、判为无效',
    }

    ev['per_item'] = {
        '4.1': {
            'result': 'PASS',
            'evidence': 'app437_app099_device.json → arms[6]，6 臂 exit_code=0、'
                        '按组件 checks 全真（ASR/MT/TTS 分开判定）',
            'n_arms': 6, 'n_arms_ok': fixed['n_arms_ok'],
        },
        '4.2': {
            'result': 'PARTIAL',
            'evidence': 'app452 本文件 → fixed_criterion.verdict / gpu_arm_a / gpu_arm_b',
            'reason': 'A 臂有效且未复现崩溃；B 对照臂被框架超时强杀、收尾停滞 ⇒ '
                      '「同样时长」的对照不成立，峰值对比无可比性',
            'no_program_crash_in_either_arm': True,
        },
    }
    ev['raw_json_left_unchanged'] = True
    ev['status_field_note'] = (
        'STATUS §175 请以本文件 fixed_criterion.verdict=PARTIAL 与 per_item 为准；'
        'app437_app099_device.json 的 verdict=PASS / timing_valid=true 是旧判据输出，'
        '已作废但保留原始证据，不得引用。')
    ev['reviewer_decision_needed'] = (
        '是否需要重跑对照臂（约 25 min 持锁）以补齐 §4.2 的「同样时长」对照，'
        '由 reviewer 裁定；本轮不自行重跑、不改判据以外的默认值。')

    ev['pass'] = bool(
        ev['script_fix']['all_anchors_present']
        and ev['n_neg_detected'] == ev['n_neg']
        and fixed['verdict'] == 'PARTIAL'
        and fixed['timing_valid'] is False
        and fixed['n_arms_ok'] == 6
        and fixed['n_gpu_arms_ok'] == 1
        and cls['gpu_control_asr_npu']['terminated_by_harness'] is True
        and cls['gpu_control_asr_npu']['crash'] is False
        and cls['gpu_same_asr_mt']['natural_exit'] is True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('OUT=%s' % OUT)
    print('pass=%s verdict=%s timing_valid=%s n_arms_ok=%s n_gpu_ok=%s neg=%d/%d'
          % (ev['pass'], fixed['verdict'], fixed['timing_valid'],
             fixed['n_arms_ok'], fixed['n_gpu_arms_ok'],
             ev['n_neg_detected'], ev['n_neg']))
    for x in neg:
        print('  neg %-34s detected=%s' % (x['name'], x['detected']))
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
