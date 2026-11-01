#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app209 —— APP-057：把 EXT 浏览器配音插件整合进 V2.0 发行包。

## 做什么（严格按 APP-057 第 2 条）

包内结构（在 `Confucius4_LiveCaption_v2.0` 下）：

    ext/extension/   ← 插件 unpacked 目录（Edge/Chrome「加载已解压的扩展程序」）
    ext/bridge/      ← 桥接服务代码（ext/ 的 21 个 .py）
    ext/.runtime_deps/← 补装的 websockets / psutil（**不污染**包内 python 的 site-packages）
    release.json     ← {"release": true}（发行版开关：禁用整机 getDisplayMedia 回退）

★ **不另拷一份模型** —— EXT 的引擎根/模型目录全部映射到包内 `app/` 与 `models/`。

## 三处「打包必改」（EXT-031 §9）

1. 包根 `release.json` = `{"release": true}`
2. `extension/manifest.json` 的 `liveDub` 段 ⇒ `release=true` + `captureModes=["tabCapture"]`
   ★ `key` 字段**保持原样**（改了扩展 ID 会变 ⇒ `/pair` 的 Origin 白名单对不上）
3. `extension/USER_GUIDE.md` 里的开发机路径 ⇒ 替换成包内相对路径说法

## 铁律

* **只写 v2.0 目录**（新目录）⇒ 不覆盖、不删除任何旧版本目录/zip。
* **不写死开发机绝对路径**（除本脚本自身的源路径常量，那在脚本里而不是包里）。
* 写文件**先写临时文件再原子替换**（`os.replace`）。
* 改 `manifest.json` / `USER_GUIDE.md` ⇒ 用 **difflib 派生替换块 + 唯一命中断言**，
  绝不手写整份待插入源码。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import time

HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.0')
EXT_SRC = os.path.join(HOME, 'live_dub_ext')

#: 打进包的 ext 代码（EXT 侧 `ext/` 的 21 个 .py ⇒ 平级放到 `ext/bridge/`）
#: ★ 用**目录级**复制（不是逐文件挑），保证 `from .xxx import` 的相对导入成立。
BRIDGE_SRC = os.path.join(EXT_SRC, 'ext')
BRIDGE_DST = os.path.join(PKG, 'ext', 'bridge')

#: 插件 unpacked 目录
PLUGIN_SRC = os.path.join(EXT_SRC, 'extension')
PLUGIN_DST = os.path.join(PKG, 'ext', 'extension')

#: 补装依赖的目标目录（**不污染**包内 python 的 site-packages）
DEPS_DST = os.path.join(PKG, 'ext', '.runtime_deps')

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + detail) if detail else ''))
    return bool(cond)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path, data, encoding='utf-8'):
    """先写临时文件再 os.replace（异常时目标文件不会被清空）。"""
    tmp = path + '.app209_tmp'
    mode = 'wb' if isinstance(data, bytes) else 'w'
    kw = {} if isinstance(data, bytes) else {'encoding': encoding, 'newline': ''}
    with open(tmp, mode, **kw) as f:
        f.write(data)
    os.replace(tmp, path)


# ═══════════════════════════════════════════════════════════════════
# 1) 复制 ext/ 源码 → ext/bridge/
# ═══════════════════════════════════════════════════════════════════
def copy_bridge():
    print('\n[1] 复制桥接代码 ext/ -> ext/bridge/')
    if os.path.isdir(BRIDGE_DST):
        shutil.rmtree(BRIDGE_DST)
    os.makedirs(BRIDGE_DST, exist_ok=True)
    n = 0
    skipped = 0
    for fn in sorted(os.listdir(BRIDGE_SRC)):
        if not fn.endswith('.py'):
            continue
        src = os.path.join(BRIDGE_SRC, fn)
        dst = os.path.join(BRIDGE_DST, fn)
        shutil.copy2(src, dst)
        n += 1
    # __init__.py 必须有（`-m bridge` 需要它当包；相对导入也靠它）
    check('桥接代码复制', n >= 20, '%d 个 .py' % n)

    # 逐字节核对
    bad = []
    for fn in sorted(os.listdir(BRIDGE_DST)):
        if not fn.endswith('.py'):
            continue
        a = sha256_file(os.path.join(BRIDGE_SRC, fn))
        b = sha256_file(os.path.join(BRIDGE_DST, fn))
        if a != b:
            bad.append(fn)
    check('桥接代码逐字节一致', not bad, '不一致: %s' % bad)
    return n


# ═══════════════════════════════════════════════════════════════════
# 2) 复制 extension/ → ext/extension/
# ═══════════════════════════════════════════════════════════════════
def copy_plugin():
    print('\n[2] 复制插件 unpacked 目录 extension/ -> ext/extension/')
    if os.path.isdir(PLUGIN_DST):
        shutil.rmtree(PLUGIN_DST)
    shutil.copytree(PLUGIN_SRC, PLUGIN_DST)
    files = []
    for dp, _dn, fns in os.walk(PLUGIN_DST):
        for fn in fns:
            files.append(os.path.relpath(os.path.join(dp, fn), PLUGIN_DST))
    n = len(files)
    total = sum(os.path.getsize(os.path.join(PLUGIN_DST, f)) for f in files)
    check('插件文件数 == 15', n == 15, '%d 个文件 / %d B' % (n, total))
    # 零测试驱动残留
    bad = [f for f in files if re_search_test(f)]
    check('插件零测试驱动残留', not bad, str(bad))
    return n, total


def re_search_test(rel):
    low = rel.lower()
    for kw in ('playwright', 'pw_ext', 'probe-worklet', 'test_', 'spec.js'):
        if kw in low.replace('\\', '/'):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# 3) 改 manifest.json 的 liveDub 段（**difflib 派生 + 唯一命中断言**）
# ═══════════════════════════════════════════════════════════════════
def patch_manifest():
    print('\n[3] 改 extension/manifest.json 的 liveDub 段')
    p = os.path.join(PLUGIN_DST, 'manifest.json')
    with open(p, 'r', encoding='utf-8') as f:
        old = f.read()
    doc = json.loads(old)
    ld = doc.get('liveDub')
    check('原 liveDub 段存在', isinstance(ld, dict), str(ld))

    key_before = doc.get('key')
    new = dict(doc)
    new['liveDub'] = dict(ld)
    new['liveDub']['release'] = True
    new['liveDub']['captureModes'] = ['tabCapture']
    # ★ `key` 字段保持原样（扩展 ID 由它算出）
    new['key'] = key_before

    # ★ 用 difflib 派生替换块（不手写整份文件）
    diff = list(difflib.unified_diff(
        old.splitlines(True), (json.dumps(new, ensure_ascii=False, indent=2)
                              + '\n').splitlines(True),
        fromfile='manifest.json(原)', tofile='manifest.json(新)'))
    changed = [l for l in diff if l.startswith(('+', '-'))
               and not l.startswith(('+++', '---'))]
    print('    diff 行数: %d' % len(changed))
    for l in changed:
        print('    ' + l.rstrip())

    # 唯一命中断言：只有 liveDub 的两个字段变化，key 不变
    assert doc.get('key') == new.get('key'), 'key 字段被改 ⇒ 扩展 ID 会变'
    assert new['liveDub']['release'] is True
    assert new['liveDub']['captureModes'] == ['tabCapture']

    atomic_write(p, json.dumps(new, ensure_ascii=False, indent=2) + '\n')
    # 写后复核
    with open(p, 'r', encoding='utf-8') as f:
        doc2 = json.load(f)
    check('manifest.liveDub.release == true', doc2['liveDub']['release'] is True)
    check('manifest.liveDub.captureModes == ["tabCapture"]',
          doc2['liveDub']['captureModes'] == ['tabCapture'])
    check('manifest.key 未变（扩展 ID 不变）', doc2.get('key') == key_before)

    # 扩展 ID 实算（与 EXT 侧同一算法）
    import base64
    der = base64.b64decode(key_before, validate=True)
    digest = hashlib.sha256(der).digest()
    alpha = 'abcdefghijklmnop'
    eid = ''.join(alpha[b >> 4] + alpha[b & 0x0F] for b in digest[:16])
    check('扩展 ID 实算 == kekgmfkijphpfndbbpakjaokamkeooib',
          eid == 'kekgmfkijphpfndbbpakjaokamkeooib', eid)
    return eid


# ═══════════════════════════════════════════════════════════════════
# 4) 包根 release.json
# ═══════════════════════════════════════════════════════════════════
def write_release_json():
    print('\n[4] 写包根 release.json')
    p = os.path.join(PKG, 'release.json')
    atomic_write(p, json.dumps({'release': True}, ensure_ascii=False, indent=2)
                 + '\n')
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    check('release.json == {"release": true}', d == {'release': True}, str(d))


# ═══════════════════════════════════════════════════════════════════
# 5) USER_GUIDE.md 的开发机路径 → 包内相对路径（**派生替换块**）
# ═══════════════════════════════════════════════════════════════════
def patch_user_guide():
    print('\n[5] 替换 extension/USER_GUIDE.md 里的开发机路径')
    p = os.path.join(PLUGIN_DST, 'USER_GUIDE.md')
    with open(p, 'r', encoding='utf-8') as f:
        old = f.read()

    # 逐条替换：**长的先替换**（避免短模式把长模式截断）
    # ⚠️ **不是 raw string** ⇒ 这里的 `\\` 表示**一个**反斜杠（文件里就是单反斜杠）
    subs = [
        ('C:\\Users\\Trekker-PTL\\live_dub_ext\\tools\\ext_launcher.py',
         '<包根>\\ext\\bridge\\start_bridge.cmd'),
        ('C:\\Users\\Trekker-PTL\\live_dub_ext\\status\\STATUS_EXT.md',
         '<包根>\\docs\\STATUS_EXT.md'),
        ('C:\\Users\\Trekker-PTL\\live_dub_ext\\extension',
         '<包根>\\ext\\extension'),
        ('C:\\Users\\Trekker-PTL\\live_dub_ext\\ext\\',
         '<包根>\\ext\\bridge\\'),
        ('C:\\Users\\Trekker-PTL\\live_dub_ext\\bridge_token.txt',
         '<包根>\\bridge_token.txt'),
        ('C:\\Users\\Trekker-PTL\\live_dub_ext',
         '<包根>'),
        ('C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v<版本号>',
         '<包根>'),
        ('C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v*',
         '<包根>'),
        ('C:\\Users\\Trekker-PTL', '<用户家目录>'),
    ]
    new = old
    n_sub = 0
    for pat, rep in subs:
        cnt = new.count(pat)
        if cnt == 0:
            continue
        new = new.replace(pat, rep)
        n_sub += cnt
    print('    替换命中 %d 处' % n_sub)

    # ★ 复核：改完后**不得**再有开发机路径
    forbidden = ['confucius4-openvino', 'live_dub_ext', 'hy_bench',
                 'qwen3tts_eval', 'Worktrees', 'Trekker-PTL']
    left = [kw for kw in forbidden if kw in new]
    check('USER_GUIDE 无开发机路径', not left, str(left))

    # diff 派生（给人看）
    diff = list(difflib.unified_diff(old.splitlines(True),
                                      new.splitlines(True),
                                      fromfile='USER_GUIDE.md(原)',
                                      tofile='USER_GUIDE.md(新)'))
    changed = [l for l in diff if l.startswith(('+', '-'))
               and not l.startswith(('+++', '---'))]
    print('    diff 行数: %d' % len(changed))

    atomic_write(p, new)
    with open(p, 'r', encoding='utf-8') as f:
        back = f.read()
    check('USER_GUIDE 写后复核一致', back == new)
    return n_sub


# ═══════════════════════════════════════════════════════════════════
# 6) 补装 websockets / psutil 到 ext/.runtime_deps
# ═══════════════════════════════════════════════════════════════════
def install_deps():
    print('\n[6] 补装 websockets / psutil 到 ext/.runtime_deps/')
    os.makedirs(DEPS_DST, exist_ok=True)
    # websockets：EXT 侧已装好 17.3（cp312，与包内 python 3.12 同 ABI）⇒ 直接复制
    src_ws = os.path.join(EXT_SRC, '.runtime_deps')
    ws_dst = os.path.join(DEPS_DST, 'websockets')
    ws_info = os.path.join(DEPS_DST, 'websockets-17.3.dist-info')
    if not os.path.isdir(ws_dst):
        shutil.copytree(os.path.join(src_ws, 'websockets'), ws_dst)
    if not os.path.isdir(ws_info):
        shutil.copytree(os.path.join(src_ws, 'websockets-17.3.dist-info'),
                        ws_info)
    check('websockets 已就位', os.path.isdir(ws_dst))

    # psutil：包内 python 用 pip --target 装（**不污染** site-packages）
    pkg_py = os.path.join(PKG, 'python', 'python.exe')
    check('包内 python 存在', os.path.isfile(pkg_py))
    if not os.path.isdir(os.path.join(DEPS_DST, 'psutil')):
        import subprocess
        cmd = [pkg_py, '-m', 'pip', 'install', '--no-warn-script-location',
               '--disable-pip-version-check', '--target', DEPS_DST,
               'psutil==7.2.2']
        print('    ' + ' '.join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        print('    rc=%d' % r.returncode)
        if r.returncode != 0:
            print('    stdout:', r.stdout[-1500:])
            print('    stderr:', r.stderr[-1500:])
    check('psutil 已就位', os.path.isdir(os.path.join(DEPS_DST, 'psutil')))

    # 实测：包内 python 能 import 到这两个包
    import subprocess
    env = dict(os.environ)
    env['PYTHONPATH'] = DEPS_DST
    code = ('import websockets, psutil; '
            'print("websockets", websockets.__version__); '
            'print("psutil", psutil.__version__)')
    r = subprocess.run([pkg_py, '-c', code], capture_output=True, text=True,
                       env=env, timeout=300)
    print('    ' + (r.stdout or '').strip())
    if r.returncode != 0:
        print('    stderr:', (r.stderr or '')[-800:])
    check('包内 python + PYTHONPATH 可 import 两个包', r.returncode == 0)
    return r.stdout.strip()


# ═══════════════════════════════════════════════════════════════════
# 7) 桥接启动脚本（用户双击用）
# ═══════════════════════════════════════════════════════════════════
def write_start_script():
    print('\n[7] 写 ext/bridge/start_bridge.cmd（用户双击启动）')
    out_dir = os.path.join(PKG, 'ext', 'bridge')
    p = os.path.join(out_dir, 'start_bridge.cmd')
    body = (
        '@echo off\r\n'
        'rem === Live Dub 桥接服务启动器（发行版）===\r\n'
        'rem 双击即可启动。日志：%%LOCALAPPDATA%%\\LiveDubEXT\\bridge.log\r\n'
        'cd /d "%~dp0..\\.."\r\n'
        'set "PYTHONPATH=%%CD%%\\ext\\.runtime_deps;%%CD%%\\ext;%%PYTHONPATH%%"\r\n'
        'set "PYTHONUTF8=1"\r\n'
        'set "PYTHONIOENCODING=utf-8"\r\n'
        'set "EXT_RELEASE=1"\r\n'
        'set "EXT_APP_ROOT=%%CD%%"\r\n'
        'set "EXT_APP_SEARCH_ROOT=%%CD%%"\r\n'
        'echo 正在启动 Live Dub 桥接服务（端口 8765）...\r\n'
        'echo 若实时字幕 App 正在运行，桥接会拒绝启动（设备互斥），这是正常的。\r\n'
        'echo 关闭本窗口即停止服务。\r\n'
        '"%%CD%%\\python\\python.exe" -m bridge --real --pipeline '
        '--target-lang en --host 127.0.0.1 --port 8765 --pair-port 8766 '
        '--spk-bypass\r\n'
        'pause\r\n'
    )
    atomic_write(p, body)
    check('start_bridge.cmd 已写', os.path.isfile(p),
          '%d B' % os.path.getsize(p))
    return p


# ═══════════════════════════════════════════════════════════════════
# 8) 包内路径扫描（开发机绝对路径闸门）
# ═══════════════════════════════════════════════════════════════════
FORBIDDEN = ('confucius4-openvino', 'live_dub_ext', 'hy_bench',
             'qwen3tts_eval', 'Worktrees', 'WorkBuddy', 'Trekker-PTL',
             'C:\\Users\\Trekker-PTL')

#: 判定「**真**开发机绝对路径」用的**可执行**特征
#:   🔴 **只看字符串字面量与实际存在性**，**不看注释 / docstring**
#:      （`ext/bridge/*.py` 的模块 docstring 里大量提到历史开发机路径，
#:        那是**文档说明**，不是运行时会走的路径 ⇒ 不算缺陷）
#:   ⇒ 但**字面量里出现**就是真问题（运行时可能被用到）
#:      例：`translator.py` 的 `os.path.join(expanduser('~'),'hy_bench','ov')`
#:        = **家目录相对**（不是绝对路径）⇒ 不算「绝对路径」；
#:        但它指向的是**开发机专属目录** ⇒ 客户机上会「找不到模型」
#:        ⇒ 仍要**列出来**（分「绝对路径」「开发机专属相对路径」两类）。

#: **绝对路径**特征：盘符开头 或 UNC
_ABS_PATH_RE = re.compile(r'(?i)([A-Z]:\\|\\\\[A-Za-z0-9_.-]+\\)')


def _py_literal_strings(path):
    """用 AST 抽 .py 里的**字符串字面量**（排除 docstring）。

    🔴 **不 import 被测模块**（项目铁律）⇒ 只用 ast。
    🔴 排除 docstring：显式跳过「`ast.Expr` ＋ 字符串常量」（那是模块/函数说明）。
    """
    import ast
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            tree = ast.parse(f.read(), filename=path)
    except Exception:
        return []
    # 收集所有 docstring 的 node id（要排除）
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_ids.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in doc_ids:
                continue
            out.append((node.lineno, node.value))
    return out


def scan_pkg_for_paths():
    print('\n[8] 扫描包内 .py/.json/.lnk/.cmd 的开发机绝对路径')
    hits = []
    n = 0
    for dp, _dn, fns in os.walk(PKG):
        for fn in fns:
            if not fn.lower().endswith(('.py', '.json', '.lnk', '.cmd')):
                continue
            p = os.path.join(dp, fn)
            n += 1
            rel = os.path.relpath(p, PKG)
            low = fn.lower()

            if low.endswith('.py'):
                # 🔴🔴 **口径修正（APP-057 ③ 复盘）**：`.py` 也**扫全文**
                #    （含 docstring 与注释）⇒ 原版「排除 docstring」会漏检
                #    `ext/bridge/engines.py` / `segmenter.py` / `app_root.py`
                #    里写死的开发机绝对路径 ⇒ 首包 v2.0 就是这样漏过去的。
                #    reviewer 的 ③ 是**文件内容**口径（客户看到的就是那一行）。
                try:
                    with open(p, 'r', encoding='utf-8', errors='replace') as f:
                        txt = f.read()
                except Exception:
                    continue
                items = [('text', i, line)
                         for i, line in enumerate(txt.splitlines(), 1)]
            else:
                # .json / .cmd / .lnk ⇒ 全文（它们没有「注释」概念）
                try:
                    with open(p, 'r', encoding='utf-8', errors='replace') as f:
                        txt = f.read()
                except Exception:
                    continue
                items = [('text', i, line)
                         for i, line in enumerate(txt.splitlines(), 1)]
            for kind, ln, val in items:
                for kw in FORBIDDEN:
                    if kw not in val:
                        continue
                    is_abs = bool(_ABS_PATH_RE.search(val))
                    hits.append({
                        'file': rel, 'line': ln, 'kw': kw,
                        'kind': kind, 'is_abs_path': is_abs,
                        'text': val.strip()[:180],
                    })
    check('扫描文件数 > 0', n > 0, '%d 个 .py/.json/.lnk/.cmd' % n)

    abs_hits = [h for h in hits if h['is_abs_path']]
    rel_hits = [h for h in hits if not h['is_abs_path']]
    print('    命中 %d 处（**绝对路径** %d / 字面量提及 %d）'
          % (len(hits), len(abs_hits), len(rel_hits)))
    for h in abs_hits:
        print('      [ABS] %s:%d [%s] %s' % (h['file'], h['line'], h['kw'],
                                             h['text']))
    # ★ 绝对路径 = **硬失败**（客户机上会指向不存在的位置）
    check('包内无开发机绝对路径（字面量级）', not abs_hits,
          '%d 处: %s' % (len(abs_hits),
                         [h['file'] + ':' + str(h['line']) for h in abs_hits]))

    # 🔴 **鉴别力自检（反证组）**：判据必须能识破「已知有缺陷」的样本
    probe = os.path.join(PKG, 'ext', '_probe_abs_path.py')
    with open(probe, 'w', encoding='utf-8') as f:
        f.write('# 反证组：故意写死开发机绝对路径\n'
                'DEV = "C:\\\\Users\\\\Trekker-PTL\\\\confucius4-openvino"\n'
                'def f():\n'
                '    """docstring 里提到 C:\\\\Users\\\\Trekker-PTL 不算缺陷"""\n'
                '    return DEV\n')
    probe_hits = []
    for ln, val in _py_literal_strings(probe):
        for kw in FORBIDDEN:
            if kw in val and _ABS_PATH_RE.search(val):
                probe_hits.append((ln, kw))
    os.remove(probe)
    check('判据能识破反证组（写死绝对路径 ⇒ 必须 FAIL）',
          bool(probe_hits), '探针命中 %d 处' % len(probe_hits))
    return n, hits, abs_hits, rel_hits


def main():
    global PKG
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    PKG = args.pkg
    t0 = time.time()
    print('=' * 70)
    print('app209 · APP-057 · EXT 整合进 V2.0')
    print('包目录:', PKG)
    print('=' * 70)

    n_py = copy_bridge()
    n_plugin, plugin_bytes = copy_plugin()
    eid = patch_manifest()
    write_release_json()
    n_sub = patch_user_guide()
    deps_out = install_deps()
    script = write_start_script()
    n_scan, hits, abs_hits, rel_hits = scan_pkg_for_paths()

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print()
    print('=' * 70)
    print('结果：%d PASS / %d FAIL' % (npass, nfail))
    print('=' * 70)

    out = {
        'tool': 'app209',
        'app': 'APP-057',
        'pkg': PKG,
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'bridge_py_files': n_py,
        'plugin_files': n_plugin,
        'plugin_bytes': plugin_bytes,
        'extension_id': eid,
        'user_guide_subs': n_sub,
        'deps_import_check': deps_out,
        'start_script': script,
        'scanned_files': n_scan,
        'path_hits': hits,
        'abs_path_hits': abs_hits,
        'literal_mention_hits': rel_hits,
        'results': [{'name': n, 'ok': ok, 'detail': d}
                    for n, ok, d in RESULTS],
        'summary': {'pass': npass, 'fail': nfail},
        'elapsed_s': round(time.time() - t0, 1),
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
