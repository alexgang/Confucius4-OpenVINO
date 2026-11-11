#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app456_app100_segment_gate.py — APP-100「10 分钟片段口径」**行为级判据**。

## 为什么要有这个判据
APP-100（`status/app/CORRECTIONS_APP.md`，2026-11-11 10:38）要求：
> 「片段起止秒写进脚本和结果 json，**所有臂、所有版本都用这同一段，保证可比**。」
> 「已下发、还没做完的纠偏（例如 ASR-053 第 3 项、APP-099）里的长跑，也按本条执行。」

§175 留下的长跑脚本写的是「0–300 s `--loop` ×2」，其**理由**是
「本机只有 300 s 的 SPE_0000_0500.wav，无法直接取 0–600 s」——
该理由经实测证伪（见 `_app455_app100_segment.py` 的模块 docstring）。

🔴 **本判据是行为级的**：对长跑脚本**真导入**（importlib + exec_module）读出**运行时**
的常量，而不是正则扫文本；片段**真读 wav、真算 SHA256**。
MEMORY 里记着：
> 「『正则没匹配上』与『事实不存在』输出完全一样 ⇒ 判据写完必须先跑反证组。」

## 判据组
A. **片段模块行为**（`_app455_app100_segment.py`）
   A1 canonical 片段存在｜A2 时长 = 600.000 s｜A3 payload SHA256 == 期望
   A4 文件 SHA256 == 期望｜A5 从**全长源**独立复算前 600 s payload SHA256 == 期望
   A6 与 **ASR 侧 canonical clip** 逐字节相同（跨模块同段）
   A7 起点 0.0 s（不顺延）｜A8 终点 600.0 s｜A9 loops=1 且 continuous
B. **长跑脚本运行时常量**（**真 import**）
   B1 LONG_SEG_END_S == 600.0｜B2 LONG_LOOPS == 1｜B3 LONG_AUDIO == canonical clip
   B4 LONG_SEG_START_S == 0.0｜B5 LONG_TIMELINE_S == 600.0
   B6 脚本引用 `_app455_app100_segment`（唯一事实来源）
   B7 ARM_TIMEOUT_S >= 2700（§175 用 1500 ⇒ B 臂在 TTS drain 阶段被误杀）
C. **结果 json 字段**（APP-100 明文：起止秒 + 写入 json）
   C1 报告块含 start_s/end_s/loops｜C2 报告块含 SHA256
   C3 报告块 **能区分** 旧口径（end_s=300 & loops=2）与新口径 ⇒ 判据有鉴别力

## 反证组（**必须能被识破** ⇒ 证明判据有鉴别力，不是恒 PASS）
R1 把 LONG_SEG_END_S 改成 300.0   ⇒ B1/B5 必须 FAIL
R2 把 LONG_LOOPS 改成 2           ⇒ B2/B5 必须 FAIL
R3 把 LONG_AUDIO 指回旧 300 s 截断件 ⇒ B3 必须 FAIL（且 A 组对该文件 FAIL）
R4 篡改片段 1 个字节              ⇒ A3 必须 FAIL
R5 报告块删掉 SHA256 字段          ⇒ C2 必须 FAIL
R6 把 ARM_TIMEOUT_S 改回 1500      ⇒ B7 必须 FAIL

## 用法
    python results/app/_app456_app100_segment_gate.py
退出码 0 = 全绿；非 0 = 有 FAIL。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import _app455_app100_segment as SEG  # noqa: E402

JOB_SCRIPT = os.path.join(HERE, '_app437_app099_device_jobs.py')
OLD_AUDIO = r'C:\Users\Trekker-PTL\shared\SPE_0000_0500.wav'

results = []


def check(name, ok, detail=''):
    results.append({'check': name, 'pass': bool(ok), 'detail': str(detail)})
    print(('  PASS  ' if ok else '  FAIL  ') + name +
          (' :: ' + str(detail) if detail else ''))
    return bool(ok)


def assign_const(src_text, name, value_literal):
    """AST 定位赋值节点并替换字面量（**只改内存里的源码**，不动磁盘）。"""
    tree = ast.parse(src_text)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    hits.append((node.lineno, node.col_offset,
                                 node.end_lineno, node.end_col_offset))
    if len(hits) != 1:
        raise AssertionError('常量 %s 赋值点不唯一：%d 处' % (name, len(hits)))
    lineno, col, end_lineno, _ = hits[0]
    lines = src_text.split('\n')
    indent = lines[lineno - 1][:col]
    lines[lineno - 1:end_lineno] = ['%s%s = %s' % (indent, name, value_literal)]
    return '\n'.join(lines)


def load_job_module(src_text=None, tag='orig'):
    """**真导入**长跑脚本（可传改写后的源码）⇒ 读出运行时常量。

    ⚠️ 脚本里 `REPO = os.path.abspath(os.path.join(HERE, '..', '..'))`
    是按**自身所在目录**算的 ⇒ 复制到临时目录后 REPO 会指错
    ⇒ `machine_lock_app` 导入失败。
    ⇒ 这里把 **repo 根**预先放进 `sys.path`，并在复制后的源码里
       **保持原样**（不改动 REPO 计算，只保证 import 能解析）。
    """
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    tmpdir = tempfile.mkdtemp(prefix='app100_job_%s_' % tag)
    path = os.path.join(tmpdir, '_job_variant.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src_text if src_text is not None
                else open(JOB_SCRIPT, 'r', encoding='utf-8').read())
    spec = importlib.util.spec_from_file_location('_job_variant_%s' % tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._tmpdir = tmpdir
    return mod


def job_checks(mod, src_text):
    """从**运行时模块对象**读常量（不是正则扫文本）。"""
    out = {}
    out['end_s'] = getattr(mod, 'LONG_SEG_END_S', None)
    out['loops'] = getattr(mod, 'LONG_LOOPS', None)
    out['start_s'] = getattr(mod, 'LONG_SEG_START_S', None)
    out['timeline_s'] = getattr(mod, 'LONG_TIMELINE_S', None)
    out['audio'] = getattr(mod, 'LONG_AUDIO', None)
    out['arm_timeout_s'] = getattr(mod, 'ARM_TIMEOUT_S', None)
    out['uses_seg_module'] = ('import _app455_app100_segment as SEG' in src_text)
    return out


def report_block_checks(block):
    """对**报告块**做判据（可直接喂反证组构造的块）。"""
    block = block or {}
    has_sha = bool(block.get('payload_sha256') or block.get('file_sha256'))
    is_legacy = (block.get('end_s') == 300.0 and block.get('loops') == 2)
    is_canonical = (block.get('end_s') == 600.0 and block.get('loops') == 1 and has_sha)
    return {
        'has_fields': 'start_s' in block and 'end_s' in block and 'loops' in block,
        'has_sha': has_sha,
        'is_legacy': is_legacy,
        'is_canonical': is_canonical,
    }


# ───────────────────────── A：片段模块行为 ─────────────────────────
print('=== A · 片段模块行为 ===')
seg_ok, seg_checks, seg_meta = SEG.verify_segment()
for k, v in seg_checks.items():
    if k.endswith('_detail'):
        continue
    check('A.' + k, v, seg_checks.get(k + '_detail', ''))

# ───────────────────────── B：长跑脚本运行时常量 ─────────────────────────
print()
print('=== B · 长跑脚本运行时常量（真 import） ===')
src_orig = open(JOB_SCRIPT, 'r', encoding='utf-8').read()
mod = load_job_module(src_orig, 'orig')
B = job_checks(mod, src_orig)
check('B1.end_s_is_600', B['end_s'] == 600.0, 'LONG_SEG_END_S=%s' % B['end_s'])
check('B2.loops_is_1', B['loops'] == 1, 'LONG_LOOPS=%s' % B['loops'])
check('B3.audio_is_canonical_clip', B['audio'] == SEG.CLIP_WAV, str(B['audio']))
check('B4.start_s_is_0', B['start_s'] == 0.0, 'LONG_SEG_START_S=%s' % B['start_s'])
check('B5.timeline_is_600', B['timeline_s'] == 600.0, 'LONG_TIMELINE_S=%s' % B['timeline_s'])
check('B6.uses_seg_module', B['uses_seg_module'], '')
check('B7.arm_timeout_ge_2700', (B['arm_timeout_s'] or 0) >= 2700,
      'ARM_TIMEOUT_S=%s' % B['arm_timeout_s'])

# ───────────────────────── C：结果 json 字段 ─────────────────────────
print()
print('=== C · 结果 json 字段（APP-100：起止秒 + SHA256 写进 json） ===')
# C 用**脚本真正会写的那段构造**（SEG.segment_meta）⇒ 证明新跑出来的报告会合规
new_block = dict(SEG.segment_meta(SEG.CLIP_WAV), timeline_s=600.0)
rc = report_block_checks(new_block)
check('C1.new_block_has_fields', rc['has_fields'], list(new_block)[:8])
check('C2.new_block_has_sha256', rc['has_sha'],
      [k for k in new_block if 'sha' in k])
check('C3.new_block_is_canonical', rc['is_canonical'],
      'end_s=%s loops=%s' % (new_block.get('end_s'), new_block.get('loops')))
# 鉴别力：旧 §175 的块（end_s=300 & loops=2）必须被识别成 legacy
legacy_block = {'audio': OLD_AUDIO, 'start_s': 0.0, 'end_s': 300.0,
                'loops': 2, 'timeline_s': 600.0}
rcl = report_block_checks(legacy_block)
check('C4.legacy_block_detected_as_legacy',
      rcl['is_legacy'] and not rcl['is_canonical'],
      'is_legacy=%s is_canonical=%s' % (rcl['is_legacy'], rcl['is_canonical']))

# ───────────────────────── 反证组 ─────────────────────────
print()
print('=== 反证组（必须能被识破 ⇒ 判据有鉴别力） ===')

# R1: end_s → 300.0
try:
    bad_src = assign_const(src_orig, 'LONG_SEG_END_S', '300.0')
    bad_mod = load_job_module(bad_src, 'r1')
    b = job_checks(bad_mod, bad_src)
    detected = not (b['end_s'] == 600.0) or not (b['timeline_s'] == 600.0)
    check('R1.end300_detected', detected,
          'end_s=%s timeline=%s' % (b['end_s'], b['timeline_s']))
    shutil.rmtree(bad_mod._tmpdir, ignore_errors=True)
except Exception as e:
    check('R1.end300_detected', False, repr(e))

# R2: loops → 2
try:
    bad_src = assign_const(src_orig, 'LONG_LOOPS', '2')
    bad_mod = load_job_module(bad_src, 'r2')
    b = job_checks(bad_mod, bad_src)
    detected = not (b['loops'] == 1) or not (b['timeline_s'] == 600.0)
    check('R2.loop2_detected', detected,
          'loops=%s timeline=%s' % (b['loops'], b['timeline_s']))
    shutil.rmtree(bad_mod._tmpdir, ignore_errors=True)
except Exception as e:
    check('R2.loop2_detected', False, repr(e))

# R3: audio → 旧 300 s 截断件
try:
    bad_src = assign_const(src_orig, 'LONG_AUDIO', repr(OLD_AUDIO))
    bad_mod = load_job_module(bad_src, 'r3')
    b = job_checks(bad_mod, bad_src)
    detected = not (b['audio'] == SEG.CLIP_WAV)
    dur = None
    try:
        dur = SEG.wav_info(b['audio'])['duration_s']
    except Exception:
        pass
    # 且该文件在 A 组口径下必须不合格（300 s ≠ 600 s）
    a_fail = (dur is None) or (abs(dur - 600.0) >= 1e-3)
    check('R3.legacy_audio_detected', detected and a_fail,
          'audio=%s duration=%s' % (b['audio'], dur))
    shutil.rmtree(bad_mod._tmpdir, ignore_errors=True)
except Exception as e:
    check('R3.legacy_audio_detected', False, repr(e))

# R4: 篡改片段 1 字节 ⇒ payload SHA256 必须不符
try:
    tmpdir = tempfile.mkdtemp(prefix='app100_r4_')
    bad_clip = os.path.join(tmpdir, 'clip_bad.wav')
    shutil.copyfile(SEG.CLIP_WAV, bad_clip)
    with open(bad_clip, 'r+b') as f:
        f.seek(1024)
        b0 = f.read(1)
        f.seek(1024)
        f.write(bytes([b0[0] ^ 0xFF]))
    bad_sha = SEG.wav_payload_sha256(bad_clip)
    check('R4.tampered_detected', bad_sha != SEG.EXPECTED_PAYLOAD_SHA256,
          'sha=%s' % bad_sha[:16])
    shutil.rmtree(tmpdir, ignore_errors=True)
except Exception as e:
    check('R4.tampered_detected', False, repr(e))

# R5: 报告块删掉 SHA256 ⇒ C2 必须 FAIL
try:
    stripped = dict(new_block)
    stripped.pop('payload_sha256', None)
    stripped.pop('file_sha256', None)
    rr = report_block_checks(stripped)
    check('R5.missing_sha_detected', not rr['has_sha'] and not rr['is_canonical'],
          'has_sha=%s is_canonical=%s' % (rr['has_sha'], rr['is_canonical']))
except Exception as e:
    check('R5.missing_sha_detected', False, repr(e))

# R6: ARM_TIMEOUT_S → 1500 ⇒ B7 必须 FAIL
try:
    bad_src = assign_const(src_orig, 'ARM_TIMEOUT_S', '1500')
    bad_mod = load_job_module(bad_src, 'r6')
    b = job_checks(bad_mod, bad_src)
    check('R6.timeout1500_detected', (b['arm_timeout_s'] or 0) < 2700,
          'ARM_TIMEOUT_S=%s' % b['arm_timeout_s'])
    shutil.rmtree(bad_mod._tmpdir, ignore_errors=True)
except Exception as e:
    check('R6.timeout1500_detected', False, repr(e))

shutil.rmtree(getattr(mod, '_tmpdir', ''), ignore_errors=True)

n_pass = sum(1 for r in results if r['pass'])
n_fail = len(results) - n_pass
summary = {
    'gate': 'app100_segment',
    'n_checks': len(results),
    'n_pass': n_pass,
    'n_fail': n_fail,
    'pass': n_fail == 0,
    'checks': results,
    'segment': seg_meta,
    'job_runtime': {k: (str(v) if isinstance(v, str) else v) for k, v in B.items()},
}
out = os.path.join(HERE, 'app456_app100_segment_gate.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=1)

print()
print('=== 汇总 === %d/%d PASS, %d FAIL ⇒ %s' % (
    n_pass, len(results), n_fail, 'PASS' if n_fail == 0 else 'FAIL'))
print('evidence: %s' % out)
raise SystemExit(0 if n_fail == 0 else 1)
