#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_fix_dev_path_leak_c190.py —— 定点修掉「包内生产模块写死开发机家目录」。

🔴 **只做定点字符串替换**（唯一命中断言），**不整目录覆盖**。
🔴 **改前先备份**（包外备份目录）。
🔴 **改后 `ast.parse` 校验** ＋ **逐字节复核**。

替换原则：**用 `os.path.expanduser('~')` 推导**，与原硬编码值**逐字节等价**
（已实测：4/4 完全相同 ⇒ 开发机行为**零变化**）。
"""

import ast
import os
import shutil
import sys


def _discover_repo_root(start):
    """**向上查找**仓库根（§119 纪律：不得写死开发机路径）。

    🔴 判据：祖先目录里同时存在 `live_caption/` 与 `pkg_paths.py`。
    ⚠️ **找不到就抛异常** ⇒ 宁可拒绝运行，也不给「指错对象」的假结论
       （绝不退化成「用 cwd 猜」）。
    """
    d = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(d, 'live_caption'))
                and os.path.isfile(os.path.join(d, 'pkg_paths.py'))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    raise RuntimeError(
        '找不到仓库根（向上查找未命中 live_caption/ + pkg_paths.py）⇒ 拒绝运行')


#: 🔴 §121：**向上查找**仓库根（不再写死开发机路径 ⇒ 脚本可随仓库搬走）
REPO = _discover_repo_root(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(REPO, 'live_caption')
BACKUP = os.path.join(REPO, 'results', 'app', 'pkg_backup_app_c190')

#: (相对文件名, [(OLD, NEW), ...]) —— 每个 OLD 必须**唯一命中**
BLOCKS = [
    ('speaker_assets.py', [(
        """DEV_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'""",
        """# 🔴 §120：不再写死开发机家目录 ⇒ 改为按**当前用户家目录**推导
#   （开发机上与原硬编码值**逐字节相同**；客户机上自然指向客户自己的家目录）
DEV_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'),
                               'qwen3asr_06b', 'scripts')""",
    )]),
    ('speaker_tracker.py', [(
        """_ASR_SCRIPTS = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b\\scripts'""",
        """# 🔴 §120：不再写死开发机家目录 ⇒ 改为按**当前用户家目录**推导
#   （开发机上与原硬编码值**逐字节相同**）
_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'),
                            'qwen3asr_06b', 'scripts')""",
    )]),
    ('tts_cuda.py', [(
        """ENV_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\\Users\\Trekker-PTL\\_fq3tts_env\\Scripts\\python.exe')""",
        """# 🔴 §120：默认值不再写死开发机家目录 ⇒ 改为按**当前用户家目录**推导
#   ⚠️ 客户机上家目录下通常没有 `_fq3tts_env` ⇒ `available()` 返 False
#      ⇒ GUI 显示「CUDA 不可用」⇒ 用户按 `docs/CUDA_TTS.md` 设 `LIVECAP_CUDA_PY`。
#   ⚠️ **默认值取不到时必须明确报错**，不能静默指向一个不存在的路径。
_ENV_PY_DEFAULT = os.path.join(os.path.expanduser('~'),
                               '_fq3tts_env', 'Scripts', 'python.exe')
ENV_PY = os.environ.get('LIVECAP_CUDA_PY', _ENV_PY_DEFAULT)""",
    )]),
    ('tts_engine.py', [(
        """    for p in (os.path.join(APP_DIR, 'tts_engine_patch.py'),
              r'C:\\Users\\Trekker-PTL\\qwen3tts_eval\\qwen3tts_patch.py'):""",
        """    # 🔴 §120：回退候选不再写死开发机家目录 ⇒ 按**当前用户家目录**推导
    #   （开发机上与原硬编码值**逐字节相同**；客户机上不存在 ⇒ 自动跳过）
    for p in (os.path.join(APP_DIR, 'tts_engine_patch.py'),
              os.path.join(os.path.expanduser('~'),
                           'qwen3tts_eval', 'qwen3tts_patch.py')):""",
    )]),
    ('tts_worker.py', [(
        """            candidates = [p for p in [tts_dir, r'C:\\Users\\Trekker-PTL\\confucius4-tts'] if p]""",
        """            # 🔴 §120：回退候选不再写死开发机家目录 ⇒ 按**当前用户家目录**推导
            #   （开发机上与原硬编码值**逐字节相同**）
            candidates = [p for p in [tts_dir, os.path.join(
                os.path.expanduser('~'), 'confucius4-tts')] if p]""",
    ), (
        """        base = os.environ.get('LIVECAP_TTS_DIR', '').strip() or \\
            r'C:\\Users\\Trekker-PTL\\confucius4-tts'""",
        """        # 🔴 §120：同上 ⇒ 按当前用户家目录推导（开发机上逐字节相同）
        base = os.environ.get('LIVECAP_TTS_DIR', '').strip() or \\
            os.path.join(os.path.expanduser('~'), 'confucius4-tts')""",
    )]),
]


def main():
    ok = True
    for fname, blocks in BLOCKS:
        src_path = os.path.join(LIVE, fname)
        with open(src_path, 'rb') as f:
            raw = f.read()
        # 🔴🔴 §119 的坑：文件可能是 **CRLF**，而替换块是 **LF**
        #   ⇒ 直接 `count(old)` 恒为 0 ⇒ 定位失效（且**不报错** ⇒ 静默漏改）。
        #   ⇒ 做法：**读入时归一化行尾**（→ LF）做匹配，**写回时还原原行尾**。
        crlf = raw.count(b'\r\n') > 0
        text = raw.decode('utf-8').replace('\r\n', '\n')
        orig = text
        # ---- 备份（包外）----
        bdir = os.path.join(BACKUP, fname)
        os.makedirs(os.path.dirname(bdir), exist_ok=True)
        shutil.copy2(src_path, bdir)
        applied = 0
        for old, new in blocks:
            n = text.count(old)
            if n == 0:
                # 🔴 幂等：OLD 已不存在 ⇒ 说明本块**上一轮已应用**（NEW 在位）
                if new in text:
                    print('  (幂等) %s: 该块已应用，跳过' % fname)
                    continue
                print('FAIL %s: OLD 命中 0 次且 NEW 也不在（要求恰好 1）' % fname)
                ok = False
                continue
            if n != 1:
                print('FAIL %s: OLD 命中 %d 次（要求恰好 1）' % (fname, n))
                ok = False
                continue
            text = text.replace(old, new)
            applied += 1
        if text == orig:
            if applied == 0:
                print('OK   %s: 0 块待改（已全部应用，幂等）' % fname)
            else:
                print('FAIL %s: 无变化' % fname)
                ok = False
            continue
        # ---- ast.parse 校验 ----
        try:
            ast.parse(text)
        except SyntaxError as e:
            print('FAIL %s: ast.parse 失败 %s' % (fname, e))
            ok = False
            continue
        # ---- 写回（还原原行尾）----
        out = text.replace('\n', '\r\n') if crlf else text
        with open(src_path, 'wb') as f:
            f.write(out.encode('utf-8'))
        # ---- 写后逐字节复核 ----
        with open(src_path, 'rb') as f:
            back = f.read().decode('utf-8')
        if back.replace('\r\n', '\n') != text:
            print('FAIL %s: 写后复核不一致' % fname)
            ok = False
            continue
        print('OK   %s: %d 块已替换（行尾 %s，备份 %s）'
              % (fname, applied, 'CRLF' if crlf else 'LF', bdir))
    print('== %s ==' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
