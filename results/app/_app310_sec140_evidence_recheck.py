# -*- coding: utf-8 -*-
"""
App 巡检 2026-11-06（§141）：对 STATUS §140 的全部报数做「证据链自证」。

背景：APP-046 ② 规定 last_ack 追平且有未完成项时不得空转。本轮无新编号
（last_ack=APP-078 = 最大编号），APP-075 停在纠偏明写的「需 Opus 复核」
节点，不得自行往下推进、不得打包。因此本轮做不占设备、不越界的实质工作：
逐条回读 §140 引用的结果文件原始字段，核对 STATUS 里的报数是否真实落盘。

纪律：
  - 纯静态：只读 JSON / 文本，不 import 任何被测模块、不加载模型、
    不占 MACHINE_LOCK、不打包、不调 MiniMax、不改 CORRECTIONS_APP.md。
  - 每条结论都指到「结果文件 + 原始字段」。
  - 含反证组（错值 / 缺字段 / 错 gate），证明判据不是恒真。
"""
import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = HERE
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
OUT = os.path.join(RES, '_app310_sec140_evidence_recheck.json')


def meta(p):
    b = open(p, 'rb').read()
    return {
        'file': os.path.relpath(p, ROOT).replace('\\', '/'),
        'bytes': len(b),
        'sha256': hashlib.sha256(b).hexdigest(),
        'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p))),
    }


def dig(j, path):
    cur = j
    for k in path.split('.'):
        if not isinstance(cur, dict) or k not in cur:
            return '<MISSING:%s>' % path
        cur = cur[k]
    return cur


def eq(j, path, expected):
    """单条判据：字段实际值必须等于 STATUS 报数。返回 dict（含 pass 布尔）。"""
    got = dig(j, path)
    return {
        'pass': got == expected,
        'field': path,
        'expected': expected,
        'actual': got if isinstance(got, (int, float, str, bool, type(None))) else repr(got)[:200],
    }


def load(name):
    p = os.path.join(RES, name)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


# (证据文件, 字段, 期望值, STATUS §140 报数说明)
ASSERTIONS = [
    ('_app302_app077_token_gate.json', 'n_pass', 26, 'APP-077① 打包闸门 26/0'),
    ('_app302_app077_token_gate.json', 'n_fail', 0, 'APP-077① 打包闸门 26/0'),
    ('_app302_app077_token_gate.json', 'verdict', 'PASS', 'APP-077① verdict'),
    ('_app304_app076_md5_audit.json', 'n_pass', 39, 'APP-076 md5 对照 39/0'),
    ('_app304_app076_md5_audit.json', 'n_fail', 0, 'APP-076 md5 对照 39/0'),
    ('_app304_app076_md5_audit.json', 'verdict', 'PASS', 'APP-076 verdict'),
    ('_app305_app077_shortcut_selftest.json', 'n_pass', 27, 'APP-077② 启动器 27/0'),
    ('_app305_app077_shortcut_selftest.json', 'n_fail', 0, 'APP-077② 启动器 27/0'),
    ('_app305_app077_shortcut_selftest.json', 'verdict', 'PASS', 'APP-077② verdict'),
    ('_app306_app078_babelvox_audit.json', 'n_pass', 28, 'APP-078 音色审计 28/0'),
    ('_app306_app078_babelvox_audit.json', 'n_fail', 0, 'APP-078 音色审计 28/0'),
    ('_app306_app078_babelvox_audit.json', 'verdict', 'PASS', 'APP-078 verdict'),
    ('_app307_assert_pkg_clean_selftest.json', 'n_pass', 14, 'APP-078 建包闸门 14/0'),
    ('_app307_assert_pkg_clean_selftest.json', 'n_fail', 0, 'APP-078 建包闸门 14/0'),
    ('_app307_assert_pkg_clean_selftest.json', 'verdict', 'PASS', 'APP-078 建包闸门 verdict'),
    ('_app309_fix_r2_submit.json', 'n_pass', 18, '_app309 补齐 submit.jsonl 18/0'),
    ('_app309_fix_r2_submit.json', 'n_fail', 0, '_app309 补齐 submit.jsonl 18/0'),
    ('_app309_fix_r2_submit.json', 'after.n_files', 54, 'r2 最终 54 文件'),
    ('_app309_fix_r2_submit.json', 'after.n_bytes', 20175499, 'r2 最终 20 175 499 B'),
    ('_app309_fix_r2_submit.json', 'gate.true', 21, 'F0 闸门 21 PASS'),
    ('_app309_fix_r2_submit.json', 'gate.false', 19, 'F0 闸门 19 FAIL'),
    ('_app309_fix_r2_submit.json', 'gate.none', 6, 'F0 闸门 6 NONE'),
    ('_app303_build_v23_clone_r2.json', 'n_files', 52, '写前口径 52 文件（§140 已声明作废）'),
    ('_app303_build_v23_clone_r2.json', 'n_bytes', 20160623, '写前口径 20 160 623 B'),
    ('_app295_f0_verify.json', 'f0_criterion.male_max_hz', 160.0, 'F0 闸门 男<160 Hz'),
    ('_app295_f0_verify.json', 'f0_criterion.female_min_hz', 170.0, 'F0 闸门 女>170 Hz'),
    ('_app298_conf_window_recheck.json', 'n_pass', 3, 'APP-075(c) 第二份材料复验 3/0'),
    ('_app298_conf_window_recheck.json', 'n_fail', 0, 'APP-075(c) 第二份材料复验 3/0'),
    ('_app308_write_status_sec140.json', 'n_fail', 0, '§140 写入自检'),
    ('_app308_write_status_sec140.json', 'verdict', 'PASS', '§140 写入自检 verdict'),
    ('app299_app075_reg_diag/app299_app075_reg_diag.json', 'mode', 'offline_stat_embed', '真 x-vector 未产出'),
    ('app299_app075_reg_diag/app299_app075_reg_diag.json', 'verdict', 'FAIL', '统计嵌入硬判据 FAIL'),
    ('app299_app075_reg_diag/app299_app075_reg_diag.json', 'n_pass', 5, 'app299 5 PASS'),
    ('app299_app075_reg_diag/app299_app075_reg_diag.json', 'n_fail', 1, 'app299 1 FAIL'),
]

ANCHORS = [
    'last_ack: APP-078', '26/0', '27/0', '28/0', '14/0', '39/0',
    '18/0', '21/19/6', '54 文件', '20 175 499 B', 'APP-078',
]


def main():
    checks = []
    cache = {}
    for name, field, expected, note in ASSERTIONS:
        if name not in cache:
            cache[name] = load(name)
        c = eq(cache[name], field, expected)
        c['id'] = 'C%02d' % (len(checks) + 1)
        c['source'] = name
        c['note'] = note
        checks.append(c)

    # 反证组：判据必须能识破错误值 / 缺字段 / 错误 gate（证明非恒真）
    j302 = cache['_app302_app077_token_gate.json']
    j309 = cache['_app309_fix_r2_submit.json']
    counter = []

    def neg(name, fn):
        ok = fn()
        counter.append({'name': name, 'caught': bool(ok), 'pass': bool(ok)})
        return {'pass': bool(ok), 'field': 'counter_evidence.' + name,
                'expected': 'must FAIL', 'actual': 'FAIL' if ok else 'PASS',
                'note': '反证：判据须能识破错误输入'}

    checks.append(neg('wrong_expected_value', lambda: eq(j302, 'n_pass', 27)['pass'] is False))
    checks.append(neg('missing_field', lambda: eq({}, 'n_pass', 26)['pass'] is False))
    checks.append(neg('wrong_gate_counts', lambda: eq(j309, 'gate.true', 22)['pass'] is False))
    checks[-3]['id'] = 'X01'
    checks[-2]['id'] = 'X02'
    checks[-1]['id'] = 'X03'
    for c in checks[-3:]:
        c['source'] = 'counter_evidence'

    # STATUS 文本锚点：结论里的数字必须真的写进了 STATUS
    text = open(STATUS, encoding='utf-8').read()
    anchors = []
    for a in ANCHORS:
        hit = a in text
        anchors.append({'anchor': a, 'found': hit})
        checks.append({'id': 'A%02d' % len(anchors), 'source': STATUS,
                       'field': 'STATUS_APP.md text', 'expected': a,
                       'actual': 'found' if hit else 'MISSING', 'pass': hit,
                       'note': '报数须在 STATUS 中落盘'})

    n_pass = sum(1 for c in checks if c['pass'])
    n_fail = len(checks) - n_pass
    verdict = 'PASS' if n_fail == 0 else 'FAIL'

    evidence = [meta(os.path.join(RES, n)) for n in sorted(cache)]
    evidence.append(meta(STATUS))
    evidence.append(meta(CORR))

    out = {
        'tool': 'app310_sec140_evidence_recheck',
        'correction': 'APP-046 ② 无新纠偏续做 — §140 证据链自证',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'checks': checks,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'verdict': verdict,
        'status_anchors': anchors,
        'counter_evidence': counter,
        'evidence_files': evidence,
        'corrections_baseline': meta(CORR),
        'note': ('纯静态复核；不占设备、不打包、不改纠偏文件。'
                 'APP-075 仍停在「需 Opus 复核」节点，本脚本不对其做任何推进或判定。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('VERDICT=%s PASS=%d FAIL=%d OUT=%s (%d B)' %
          (verdict, n_pass, n_fail, OUT, os.path.getsize(OUT)))
    for c in checks:
        if not c['pass']:
            print('  FAIL', c['id'], c['source'], c['field'], c['actual'])
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
