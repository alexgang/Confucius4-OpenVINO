#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app091_tts_dump_dir_cli_test.py —— §61 验收：App CLI 暴露 `--tts-dump-dir`（APP-021⑥）。

## 本轮验收什么

APP-021⑥ 的原文：
  > 6. 新增 `--tts-dump-dir`（或者在对话框里勾选"同时保存 wav"）：
  >    离线朗读每段落盘一个 wav，供 reviewer 算 RMS 和回转写。

§54 已经做了**对话框勾选框**那半边（`offline_reader_gui.py::_apply_dump_dir`
→ `svc.set_dump_dir(d)`）。
🔴 但 **App CLI 侧从来没有这个开关** ⇒
`TTSService.__init__` 早就有 `dump_dir` 参数、`start()` 也会拼 `--dump-dir`
给 worker ⇒ **只差 App 这一层的接线** ⇒
**从 App 命令行根本无法触发逐句 wav 落盘** ⇒ reviewer 只能用 GUI 复现。

本脚本验证：
- **A 组（REAL）**：`--tts-dump-dir` 出现在 App CLI 的 argparse 里；
  CLI 模式的 `TTSService(...)` 构造**真的把它透传**下去；
  解析后 `args.tts_dump_dir` 取到用户给的值。
- **B 组（BUG 反证）**：用**修复前的固定 commit** `3afaf7a` 的源码跑同一套断言
  ⇒ 必须**全部落空**（证明该缺陷**曾真实存在**，而不是断言过期）。

🔴 **反证基线必须是固定 commit，不能用 `HEAD`** —— §61 提交后 HEAD 就是修复版
⇒ 用 HEAD ⇒ 反证永远落空 ⇒ 失去证据价值。
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
APP = os.path.join(REPO, 'live_caption', 'live_caption_app.py')

# 🔴 修复前的固定 commit（§61 的 fix 提交之前的最后一版）
BASE_COMMIT = '3afaf7a'

results = []


def check(name, ok, detail=''):
    results.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print('  %s %s%s' % ('PASS' if ok else 'FAIL', name,
                         (' — ' + detail) if detail else ''))
    return bool(ok)


def load_head():
    with open(APP, 'rb') as f:
        return f.read().decode('utf-8')


def load_base():
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:live_caption/live_caption_app.py'
                        % BASE_COMMIT], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show %s 失败: %s'
                           % (BASE_COMMIT, r.stderr.decode('utf-8', 'replace')))
    return r.stdout.decode('utf-8')


def analyze(src):
    """用 ast 静态检查（不 import 被测模块 ⇒ 不会拉起 numpy/torch）。"""
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # 🔴 argparse 的 flag 名是**位置参数**（`add_argument('--tts-dump-dir', ...)`）
            #    不是 keyword ⇒ 必须看 `node.args[0]`。
            for a in node.args:
                if isinstance(a, ast.Constant) and a.value == '--tts-dump-dir':
                    out['has_flag'] = True
            # 找 TTSService(...) 构造里的 dump_dir= 关键字
            fn = node.func
            fname = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
            if fname == 'TTSService':
                for kw in node.keywords:
                    if kw.arg == 'dump_dir':
                        out['has_dump_kwarg'] = True
                        out['dump_expr'] = ast.unparse(kw.value)
    out.setdefault('has_flag', False)
    out.setdefault('has_dump_kwarg', False)
    out.setdefault('dump_expr', None)
    return out


def run_cli(src, tmpdir):
    """把源码写到影子目录并跑 --help，验证 argparse 真的接受该参数。

    🔴 **影子目录**：不碰工作区、不碰客户包。
    🔴 `live_caption_app.py` 顶层 import numpy ⇒ 影子目录里必须能 import 到 numpy
    ⇒ 用系统 3.12（实测有 numpy 2.5.4）。
    🔴🔴 **必须按 bytes 写盘**（不能 `open(..., 'w')`）：
       仓库里的 `live_caption_app.py` 是 **CRLF**（实测 4069 个 \r\n / 0 个裸 \n）
       ⇒ 文本模式写回会把每个 `\n` 再翻成 `\r\n` ⇒ 变成 `\r\r\n`
       ⇒ Python 报 **IndentationError: unexpected indent** ⇒ 影子目录直接起不来
       （本轮第一次跑就踩到了 ⇒ rc=1）。
    🔴🔴 **必须把同目录的其它 .py 也复制过去**：
       `live_caption_app.py` 用的是**扁平 import**（`from translator import ...`）
       ⇒ 只复制它一个 ⇒ `ModuleNotFoundError: No module named 'translator'`
       ⇒ rc=1（本轮第二次踩到）。
       ⇒ 复制 `live_caption/` 下**全部** .py（诊断脚本也带上，无害）。
    """
    import glob
    import shutil
    import tempfile
    shadow = tempfile.mkdtemp(prefix='app091_shadow_')
    try:
        dstdir = os.path.join(shadow, 'live_caption')
        os.makedirs(dstdir, exist_ok=True)
        for p in glob.glob(os.path.join(REPO, 'live_caption', '*.py')):
            shutil.copy2(p, os.path.join(dstdir, os.path.basename(p)))
        tgt = os.path.join(dstdir, 'live_caption_app.py')
        with open(tgt, 'wb') as f:
            f.write(src.encode('utf-8'))
        r = subprocess.run([sys.executable, tgt, '--help'],
                           capture_output=True, cwd=dstdir)
        out = (r.stdout.decode('utf-8', 'replace')
               + r.stderr.decode('utf-8', 'replace'))
        return r.returncode, out
    finally:
        shutil.rmtree(shadow, ignore_errors=True)


def main():
    print('=' * 74)
    print('§61 验收：App CLI 暴露 --tts-dump-dir（APP-021⑥）')
    print('=' * 74)
    print('反证基线 commit: %s' % BASE_COMMIT)
    print('被测文件: %s' % APP)
    print()

    head = load_head()
    base = load_base()

    print('[A] REAL 组（当前工作区 = 修复后）')
    h = analyze(head)
    check('A1 argparse 里有 --tts-dump-dir', h['has_flag'])
    check('A2 CLI 的 TTSService(...) 传了 dump_dir=',
          h['has_dump_kwarg'],
          'expr=%s' % h['dump_expr'])
    check('A3 dump_dir 取自 args.tts_dump_dir',
          h['dump_expr'] is not None and 'args.tts_dump_dir' in h['dump_expr'],
          'expr=%s' % h['dump_expr'])

    # 真正跑一次 --help（影子目录）⇒ 证明 argparse 真的注册了这个参数
    rc, out = run_cli(head, None)
    check('A4 `--help` 里出现 --tts-dump-dir',
          '--tts-dump-dir' in out,
          'rc=%s' % rc)
    check('A5 `--help` 里出现 TTS_DUMP_DIR 占位符',
          'TTS_DUMP_DIR' in out)

    print()
    print('[B] BUG 反证组（修复前的固定 commit ⇒ 必须全部落空）')
    b = analyze(base)
    check('B1 基线里**没有** --tts-dump-dir（缺陷曾真实存在）',
          not b['has_flag'])
    check('B2 基线的 TTSService(...) **没有** dump_dir=',
          not b['has_dump_kwarg'])
    rc2, out2 = run_cli(base, None)
    check('B3 基线 `--help` 里**没有** --tts-dump-dir',
          '--tts-dump-dir' not in out2,
          'rc=%s' % rc2)

    a_items = [r for r in results if r['name'].startswith('A')]
    b_items = [r for r in results if r['name'].startswith('B')]
    real_fail = [r['name'] for r in a_items if not r['ok']]
    # 🔴 B 组语义 = 「**基线里确实有这个缺陷**」⇒ 这几条**通过**才算反证成立。
    #    （不是「命中即 FAIL」—— 那是「缺陷仍然存在于当前代码」的另一种 BUG 组语义。）
    bug_proved = [r['name'] for r in b_items if r['ok']]
    bug_unproved = [r['name'] for r in b_items if not r['ok']]

    verdict = 'PASS' if (not real_fail and not bug_unproved) else 'FAIL'

    evidence = {
        'section': '61',
        'verdict': verdict,
        'baseline_commit': BASE_COMMIT,
        'real_total': len(a_items),
        'real_fail': real_fail,
        'bug_total': len(b_items),
        'bug_proved': bug_proved,
        'bug_unproved': bug_unproved,
        'checks': results,
    }
    outp = os.path.join(HERE, 'app091_tts_dump_dir_cli_evidence.json')
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print()
    print('证据落盘: %s' % outp)
    print('=' * 74)
    print('verdict=%s  REAL %d/%d PASS  BUG 反证 %d/%d 成立'
          % (verdict,
             len(a_items) - len(real_fail), len(a_items),
             len(bug_proved), len(b_items)))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
