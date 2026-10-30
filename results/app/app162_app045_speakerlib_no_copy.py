#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP-045④ 验收：**内置音色不再被复制到用户目录**，但**仍可按名查到**。

🔴 **背景**（reviewer APP-045④ 原文）：
  「SpeakerLibrary 从 %LOCALAPPDATA%\\...\\tts_speakers 加载了
    cindy/lou/phil/steve 4 个音色，请确认来源和许可
    （是否 babelvox 自带，APP-018 曾要求移除）。」

🔴 **实测结论**（本脚本要把它变成可复跑的判据）：
  - 来源：babelvox **自带示例**（`babelvox/data/speakers/`，
    `source_audio` 指向 babelvox 仓库 `tools/reference_audio/*.mp3`，
    tags 含 `example`）；
  - 许可：babelvox = **Apache-2.0**（`License-Expression: Apache-2.0`）；
  - 客户包 zip 层：**已排除**（实测 0 命中，APP-018② 的排除规则生效）；
  - 但 `SpeakerLibrary(copy_builtins=True)` 会在**运行时把它们复制到用户目录**
    ⇒ 用户目录凭空多出 4 个第三方音色 ⇒ 本条要消除这个副作用。

🔴 **判据**：
  ① 初始化 `_attach_speaker_library` 后，**用户目录里不得出现**任何
     `*.json` / `*.npy`（即不得复制内置音色）；
  ② `eng.speaker_library.load('cindy')` **仍能成功**（只读回退可用）；
  ③ `list_profiles()` **仍包含** 4 个内置音色（GUI 不暴露，但 CLI `--voice` 用）；
  ④ **反证**：把 `copy_builtins=False` 改回 `True` ⇒ 判据 ① 必须 FAIL
     ⇒ 证明判据 ① 不是恒真。

🔴 **执行纪律**（记忆 §十一）：
  - **不 import 被测模块**（顶层 numpy ⇒ import 阶段 abort）
    ⇒ `ast` 抽源码 + `exec` 独立命名空间；
  - 抽源码**必须保留 Import**（坑①）+ **模块级常量**（坑②）；
  - **反证改源码文本后再 exec**（坑③）。

用法：
    python app162_app045_speakerlib_no_copy.py
    python app162_app045_speakerlib_no_copy.py --falsify
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ENGINE_PY = os.path.join(REPO, 'live_caption', 'tts_engine.py')

PKG_SITE = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12\python\Lib\site-packages'

FUNC_NAMES = {
    '_attach_speaker_library',
    '_SpeakerLibraryWithBuiltinFallback',
    'builtin_speakers_available',
}


def _build_ns(src_text, func_names=FUNC_NAMES):
    tree = ast.parse(src_text)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep.append(node)                      # 坑①
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and (t.id.isupper() or t.id == 'Optional'):
                    keep.append(node)              # 坑②
                    break
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_names:
                keep.append(node)
        elif isinstance(node, ast.ClassDef):
            if node.name in func_names:
                keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {'__file__': ENGINE_PY, '__name__': 'app162_extracted'}
    exec(compile(mod, '<extracted>', 'exec'), ns)
    return ns


class _FakeEng:
    """假引擎：只用来承载 `speaker_library` 属性。"""

    def __init__(self):
        self.speaker_library = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--falsify', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    if PKG_SITE not in sys.path:
        sys.path.insert(0, PKG_SITE)
    try:
        import numpy as np
        from babelvox.speakers import SpeakerLibrary
    except Exception as e:
        print('✗ 环境不可用（需包内 babelvox + numpy）:', e)
        return 2

    results = []

    def rec(name, ok, detail):
        results.append(dict(name=name, ok=bool(ok), detail=detail))
        print(('  PASS  ' if ok else '  FAIL  ') + name + ' :: ' + detail)

    print('=' * 74)
    print('APP-045④ 内置音色不再复制到用户目录 —— 验收')
    print('  falsify =', args.falsify)
    print('=' * 74)

    src = open(ENGINE_PY, 'r', encoding='utf-8').read()
    if args.falsify:
        # 🔴 反证：把 copy_builtins=False 改回 True（= 旧行为）
        src = src.replace('SpeakerLibrary(lib_dir, copy_builtins=False)',
                          'SpeakerLibrary(lib_dir, copy_builtins=True)')
        print('  [反证] 已注入：copy_builtins=True（旧行为 ⇒ 会复制）')

    ns = _build_ns(src)

    # ── 用**沙箱用户目录**测（绝不碰真实用户目录！）────────────────
    #    `_cache_dir` 是模块级函数 ⇒ 我们**替换**它，让库建在临时目录里。
    sandbox = tempfile.mkdtemp(prefix='app162_sandbox_')
    lib_dir = os.path.join(sandbox, 'tts_speakers')
    ns['_cache_dir'] = lambda name: os.path.join(sandbox, name)

    eng = _FakeEng()
    ok = ns['_attach_speaker_library'](eng, on_log=lambda *a: None)
    rec('① _attach_speaker_library 返回 True', ok, 'ret=%r' % (ok,))

    # ── 判据 ①：用户目录里不得出现内置音色的文件 ────────────────────
    copied = []
    if os.path.isdir(lib_dir):
        copied = sorted(os.listdir(lib_dir))
    rec('判据① 用户目录未被写入任何内置音色文件',
        len(copied) == 0,
        '用户目录=%s 内容=%r' % (lib_dir, copied))

    # ── 判据 ②：内置音色仍可按名查到（只读回退）────────────────────
    try:
        prof = eng.speaker_library.load('cindy')
        emb = np.asarray(prof.embedding)
        rec('判据② 内置音色 cindy 仍可按名加载（只读回退）',
            emb.shape == (1, 1024),
            'embedding shape=%s' % (emb.shape,))
    except Exception as e:
        rec('判据② 内置音色 cindy 仍可按名加载（只读回退）', False,
            '异常：%r' % (e,))

    # ── 判据 ③：list_profiles 仍含 4 个内置音色 ────────────────────
    try:
        names = sorted(p['name'] for p in eng.speaker_library.list_profiles())
    except Exception as e:
        names = []
        print('  ⚠ list_profiles 异常：', e)
    expect4 = {'cindy', 'lou', 'phil', 'steve'}
    rec('判据③ list_profiles 仍含 4 个内置音色',
        expect4.issubset(set(names)),
        'names=%r' % (names,))

    # ── 判据 ④：用户自建音色仍能存进去（不破坏原有能力）────────────
    try:
        from babelvox.speakers import SpeakerProfile
        p = SpeakerProfile(name='myspk', embedding=np.zeros((1, 1024), np.float32))
        eng.speaker_library.save(p)
        again = eng.speaker_library.load('myspk')
        rec('判据④ 用户自建音色可存可取（未被本次改动破坏）',
            np.asarray(again.embedding).shape == (1, 1024),
            'ok')
    except Exception as e:
        rec('判据④ 用户自建音色可存可取（未被本次改动破坏）', False,
            '异常：%r' % (e,))

    # ── 清理沙箱 ─────────────────────────────────────────────────────
    shutil.rmtree(sandbox, ignore_errors=True)

    # ── 汇总 ─────────────────────────────────────────────────────────
    npass = sum(1 for r in results if r['ok'])
    nfail = len(results) - npass
    verdict = 'PASS' if nfail == 0 else 'FAIL'
    print('-' * 74)
    print('PASS=%d FAIL=%d verdict=%s' % (npass, nfail, verdict))

    out = dict(schema='app.app045.speakerlib_no_copy.v1',
               pass_=npass, fail=nfail, verdict=verdict,
               falsify=bool(args.falsify), checks=results)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
