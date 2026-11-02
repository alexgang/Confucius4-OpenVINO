#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130 负向测试：拿**故意坏**的产物跑 app224 的同一套判据 ⇒ 必须被抓出来。

🔴 **为什么必须做**（MEMORY 四）：「判据 PASS」≠「判据正确」
⇒ 拿**已知有缺陷的旧产物**跑一遍 ⇒ 判据须能识破 ⇒ 证明**非恒真**。
本测试**不改任何仓库文件** ⇒ 全部在内存 / 临时目录里做。
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

spec = importlib.util.spec_from_file_location(
    'app224', os.path.join(HERE, 'app224_app061_escape_lock_gates.py'))
app = importlib.util.module_from_spec(spec)
sys.modules['app224'] = app
spec.loader.exec_module(app)

CASES = []


def case(name, ok, detail):
    CASES.append({'name': name, 'ok': bool(ok), 'detail': detail})


# ── ① 真实负向：把**基线版本**（带 SyntaxWarning）当成「当前」跑判据
#    ⇒ 「告警归零」必须判 False（**不能**说它已归零）
base = app.git_rev_bytes('live_caption/tts_cuda_sidecar.py', app.BASE_REV)
warns = app.compile_warnings(base, 'live_caption/tts_cuda_sidecar.py')
case('negative_real_artifact_has_warning',
     bool(warns) and not (bool(warns) and not warns),
     '基线版本 compile() 告警 %d 条 ⇒ 「已归零」必须为 False（实得 %r）'
     % (len(warns), bool(warns) and not warns))

# ── ② 真实负向：把「基线常量」故意改一个值 ⇒ 行为常量判据必须抓住
docs_b, others_b = app.split_constants(base)
mutated = list(others_b)
if mutated:
    mutated[0] = mutated[0] + '__MUTANT__'
    d, intact = app.compare_string_constants(others_b, mutated)
    case('negative_behavior_constant_mutated', (not intact),
         '改掉一个行为常量 ⇒ intact=%r（须 False）' % intact)
else:
    case('negative_behavior_constant_mutated', False, '基线没有行为常量 ⇒ 用例无法构造')

# ── ③ 真实负向：**删掉**一个行为常量 ⇒ 必须抓住
if len(others_b) > 1:
    d, intact = app.compare_string_constants(others_b, others_b[:-1])
    case('negative_behavior_constant_dropped', (not intact),
         '删掉一个行为常量 ⇒ intact=%r（须 False）' % intact)
else:
    case('negative_behavior_constant_dropped', False, '行为常量不足 1 个 ⇒ 用例无法构造')

# ── ④ 正向：合法新增常量 ⇒ 必须放过（§129 的真实场景）
docs_n, others_n = app.split_constants(
    open(os.path.join(REPO, 'live_caption', 'tts_cuda_sidecar.py'), 'rb').read())
d, intact = app.compare_string_constants(others_b, others_n)
case('positive_legitimate_additions_allowed', bool(intact),
     '当前版 vs 基线的行为常量（§129 合法演进）⇒ intact=%r（须 True）' % intact)

# ── ⑤ 正向：合法重排常量 ⇒ 必须放过
if len(others_b) > 2:
    d, intact = app.compare_string_constants(others_b, list(reversed(others_b)))
    case('positive_reorder_allowed', bool(intact),
         '仅重排行为常量 ⇒ intact=%r（须 True）' % intact)
else:
    case('positive_reorder_allowed', False, '行为常量不足 3 个 ⇒ 用例无法构造')

n_pass = sum(1 for c in CASES if c['ok'])
print('===== §130 app224 判据负向/正向测试 =====')
for c in CASES:
    print('  [%s] %s' % ('PASS' if c['ok'] else 'FAIL', c['detail']))
print('\n结果：%d PASS / %d FAIL' % (n_pass, len(CASES) - n_pass))
sys.exit(0 if n_pass == len(CASES) else 1)
