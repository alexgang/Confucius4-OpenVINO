#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app176 — APP-052 克隆音色失效根因（OV 输出类型）的独立判据。

🔴 **判据铁律**（记忆 §四）：
  - **绝不 import 被测模块**（顶层 numpy ⇒ import 阶段 abort）
    ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间；
  - **双向反证**：判据必须能**识破修复前的行为**
    （`np.asarray(OVDict)` ⇒ TypeError）；
  - 判据 FAIL ⇒ **先怀疑判据本身**。

## 判据内容
  A. `_ov_out_to_array` 存在且可从源码抽出执行；
  B. 对**真实 OpenVINO 输出**（OVDict / Tensor / ConstOutput）返回 numpy；
  C. **反证组**：修复前的写法 `np.asarray(OVDict)` 必须**抛 TypeError**
     ⇒ 证明判据确实在检验「有没有做转换」，而不是恒真；
  D. 对 ndarray / list / tuple / None 的行为正确；
  E. 无法识别的对象返回 None（**不抛异常**）。

用法：
    python results/app/app176_ov_output_convert_gate.py \
        --pkg-python "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.13\\python\\python.exe"
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
EVID = os.path.join(HERE, 'app176_ov_output_convert_evidence.json')

# 🔴🔴 **客户包路径用 `pkg_paths` 单一数据源**（**不写死版本号**）
#   ⇒ §48「包路径写死」闸门：包一升版，本脚本就指错对象 ⇒ 报出假 FAIL
#   （真实事故：2026-10-26 §47.6）。
sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402

PKG_DIR = pkg_paths.discover_pkg_dir()

# 🔴 客户包自带 python（3.12.10，含 openvino 2026.4.1 + numpy）
PKG_PYTHON = os.path.join(PKG_DIR, 'python', 'python.exe')

TARGET_SRC = os.path.join(REPO, 'live_caption', 'tts_engine.py')


# ── 被测源码抽取（在**子进程**里用客户包 python 执行）────────────────
PROBE_SRC = r'''
import ast, json, sys, os

SRC = sys.argv[1]

def extract_fn(path, name):
    """🔴 用 ast 抽出**单个函数**的源码（不 import 被测模块）。"""
    src = open(path, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(src, node)
    raise SystemExit('FUNC-NOT-FOUND: %s' % name)

fn_src = extract_fn(SRC, '_ov_out_to_array')
ns = {'np': None}
import numpy as np
ns['np'] = np
exec(compile(fn_src, '<app176>', 'exec'), ns)
to_arr = ns['_ov_out_to_array']

import openvino as ov
from openvino.utils.data_helpers import OVDict

out = {'checks': []}

def chk(name, ok, detail=''):
    out['checks'].append({'name': name, 'ok': bool(ok), 'detail': str(detail)})

# ── B. 真实 OV 输出 ────────────────────────────────────────────────
# 🔴🔴 **用产品真实的 speaker_encoder.xml**（不是人造模型）
#    ⇒ 与 App 实际路径完全一致 ⇒ 判据忠实
import numpy as np
core = ov.Core()
# 🔴🔴 **包路径由命令行传入**（**不写死版本号** ⇒ §48 闸门）
#   ⇒ 子进程不 import 仓库模块 ⇒ 用 argv 传进来最干净
PKG_DIR = sys.argv[2]
SPK_XML = os.path.join(PKG_DIR, 'models',
                        'qwen3tts', 'int8', 'speaker_encoder.xml')

try:
    if not os.path.isfile(SPK_XML):
        raise FileNotFoundError(SPK_XML)
    m = core.read_model(SPK_XML)
    cm = core.compile_model(m, 'CPU')
    # 动态形状 ⇒ 喂一小段 mel（CPU 档不 pad）
    mel = np.zeros((1, 16, 128), dtype=np.float32)
    ovd = cm({'mel_spectrogram': mel})
    chk('B0_real_ov_output_type', type(ovd).__name__ == 'OVDict',
        'type=%s  src=%s' % (type(ovd).__name__, SPK_XML))
    arr = to_arr(ovd)
    chk('B1_ovdict_to_numpy', isinstance(arr, np.ndarray)
        and arr.ndim == 2 and arr.shape[0] == 1 and arr.shape[1] == 1024,
        'arr shape=%r' % (None if arr is None else arr.shape,))
    chk('B2_ovdict_is_mapping_not_array',
        not isinstance(ovd, np.ndarray),
        'isinstance ndarray = %s' % isinstance(ovd, np.ndarray))
    port = list(ovd.keys())[0]

    # Tensor 分支（**真 Tensor**，含数据）
    t = ov.Tensor(np.arange(6, dtype=np.float32).reshape(2, 3))
    t_arr = to_arr(t)
    chk('B3_tensor_to_numpy', isinstance(t_arr, np.ndarray)
        and t_arr.shape == (2, 3),
        'arr shape=%r' % (None if t_arr is None else t_arr.shape,))

    # ConstOutput 分支
    #   🔴 OV 语义：`ConstOutput.get_tensor()` 返回的是 **DescriptorTensor**
    #   （只有**描述符**、**无数据**）⇒ 转换器正确地返回 None
    #   ⇒ 断言「不抛异常 + 返回 None」
    co_arr = to_arr(port)
    chk('B4_constoutput_descriptor_returns_none', co_arr is None,
        'arr=%r（DescriptorTensor 无数据 ⇒ None 是正确行为）' % (co_arr,))

    # ConstOutput → 经 OVDict 取值才拿得到真实 ndarray
    chk('B5_ovdict_value_is_ndarray',
        isinstance(ovd[port], np.ndarray) and ovd[port].shape == (1, 1024),
        'shape=%r' % (np.asarray(ovd[port]).shape,))
except Exception as e:
    ovd = None
    chk('B0_real_ov_output_type', False, 'EXC %s: %s' % (type(e).__name__, e))

# ── C. 反证组：修复前的写法必须失败 ──────────────────────────────
if ovd is None:
    chk('C1_prefix_code_must_raise', False,
        '前置：真实 OV 输出未构造成功 ⇒ 反证组无法执行')
    chk('C2_ovdict_values_shape', False, '前置：真实 OV 输出未构造成功')
else:
    try:
        np.asarray(ovd, dtype=np.float32)
        chk('C1_prefix_code_must_raise', False,
            '修复前写法居然成功了 ⇒ 判据恒真，失去鉴别力')
    except TypeError as e:
        chk('C1_prefix_code_must_raise', True, 'TypeError: %s' % e)
    except Exception as e:
        chk('C1_prefix_code_must_raise', False,
            '期望 TypeError，实得 %s: %s' % (type(e).__name__, e))

    # 反证组 2：只做 `np.asarray` 转换是不够的（必须解包 OVDict 的第 0 输出）
    try:
        v = list(ovd.values())
        chk('C2_ovdict_values_shape', len(v) == 1
            and np.asarray(v[0]).shape == (1, 1024),
            'n=%d shape=%r' % (len(v), np.asarray(v[0]).shape))
    except Exception as e:
        chk('C2_ovdict_values_shape', False, 'EXC %s: %s' % (type(e).__name__, e))

# ── D. 常规类型 ──────────────────────────────────────────────────
chk('D1_ndarray_passthrough',
    isinstance(to_arr(np.zeros((1, 4), dtype=np.float32)), np.ndarray), '')
chk('D2_list_takes_first',
    to_arr([np.zeros((2, 2), dtype=np.float32)]) is not None
    and to_arr([np.zeros((2, 2), dtype=np.float32)]).shape == (2, 2), '')
chk('D3_tuple_takes_first',
    to_arr((np.zeros((3,), dtype=np.float32),)) is not None
    and to_arr((np.zeros((3,), dtype=np.float32),)).shape == (3,), '')
chk('D4_none_returns_none', to_arr(None) is None, '')

# ── E. 无法识别 ⇒ None，不抛异常 ────────────────────────────────
class Weird:
    pass
try:
    r = to_arr(Weird())
    chk('E1_unknown_returns_none', r is None, 'got %r' % (r,))
except Exception as e:
    chk('E1_unknown_returns_none', False, 'EXC %s: %s' % (type(e).__name__, e))

print(json.dumps(out, ensure_ascii=False))
'''


def run_probe(python_exe: str) -> dict:
    env = dict(os.environ)
    env['PYTHONPATH'] = ''
    env['PYTHONHOME'] = ''
    env['PYTHONNOUSERSITE'] = '1'
    p = subprocess.run([python_exe, '-c', PROBE_SRC, TARGET_SRC, PKG_DIR],
                       capture_output=True, text=True, env=env,
                       cwd=REPO, timeout=600)
    stdout = p.stdout.strip()
    if p.returncode != 0 or not stdout:
        return {'checks': [], 'fatal': (p.stderr or '')[-4000:],
                'rc': p.returncode}
    try:
        return json.loads(stdout.splitlines()[-1])
    except Exception as e:
        return {'checks': [], 'fatal': 'JSON parse failed: %s | %s'
                                    % (e, stdout[-2000:]), 'rc': p.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg-python', default=PKG_PYTHON)
    args = ap.parse_args()

    # ── A. 源码层前置检查 ──────────────────────────────────────
    checks = []
    src = open(TARGET_SRC, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
    fn_names = {n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    checks.append({'name': 'A1_ov_out_to_array_exists',
                   'ok': '_ov_out_to_array' in fn_names,
                   'detail': 'fn names sample=%s'
                             % sorted(x for x in fn_names if 'ov' in x)[:10]})
    checks.append({'name': 'A2_speaker_embedding_from_pcm_uses_converter',
                   'ok': '_ov_out_to_array(result)' in src,
                   'detail': 'call site present'})

    # ── B/C/D/E 在子进程里实测 ────────────────────────────────
    probe = run_probe(args.pkg_python)
    if probe.get('fatal'):
        checks.append({'name': 'F0_probe_ran', 'ok': False,
                       'detail': probe['fatal']})
    else:
        checks.extend(probe['checks'])

    n_fail = sum(1 for c in checks if not c['ok'])
    n_pass = len(checks) - n_fail
    verdict = 'PASS' if n_fail == 0 else 'FAIL'

    os.makedirs(os.path.dirname(EVID), exist_ok=True)
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump({'checks': checks, 'n_pass': n_pass, 'n_fail': n_fail,
                   'verdict': verdict, 'pkg_python': args.pkg_python,
                   'target_src': TARGET_SRC}, f, ensure_ascii=False, indent=2)

    for c in checks:
        print('[%s] %s  %s' % ('PASS' if c['ok'] else 'FAIL',
                                c['name'], c['detail'][:160]))
    print('=' * 60)
    print('结论：%s  PASS=%d FAIL=%d' % (verdict, n_pass, n_fail))
    print('证据：%s' % EVID)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
