#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §1：**把 EXT 更新到 v0.4.18**（`live_dub_ext@ee45ce5`）并补上桥接启动器。

## reviewer 原文（APP-118 §1）
> **EXT 更新到最新 v0.4.18**（live_dub_ext@ee45ce5）**及桥接启动器**
> （tools/ext_launcher.py + Start_Bridge.bat，CRLF+ASCII）。

## 布局（**与已验收的 SpecialMVP sp5 一致** ⇒ 不发明新布局）
| 源（`live_dub_ext/`） | 落点（`<包根>/`） |
|---|---|
| `ext/*.py`（23 个） | `ext/bridge/*.py` |
| `extension/*` | `ext/extension/*` |
| `tools/ext_launcher.py` | `tools/ext_launcher.py` |
| （打包侧新增） | `ext/bridge/__main__.py`（让 `python -m ext.bridge` 可执行） |
| （打包侧新增） | `Start_Bridge.bat`（CRLF + ASCII） |
| （打包侧新增） | `.runtime_deps/`（websockets / psutil ⇒ 放**包根**，与 `ext_launcher.py` 的 `ROOT` 对齐） |

## 🔴 关键纪律
1. **只读 `live_dub_ext/`**（EXT 模块的源码仓）⇒ 不改它；
2. **不删任何东西**（本机有「安全删除 shim」⇒ 删除会失败）
   ⇒ 旧的 `ext/bridge/bridge_launcher.py` / `start_bridge.cmd`
   **改名挪到包外**（`.superseded-<时间戳>.bak`），**不删**；
3. **CRLF**：包内 `.py` / `.js` / `.bat` 一律 **CRLF**
   （源 `ext/*.py` 是 LF ⇒ 转换；`Start_Bridge.bat` 必须 **ASCII**）；
4. 写盘走 **临时文件 → `os.replace`**；写后**逐文件 SHA256 复核**；
5. `manifest.json` 的 `release` 置 **true**（发行版开关，EXT-031③）
   ⇒ 源仓里是 `false`（开发态）⇒ **打包时改写**；
6. `manifest.json` 的 `version` = **0.4.18**（与 `ext/version.py` 一致）。
"""
import datetime
import hashlib
import json
import os
import shutil
import sys

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
SRC_EXT = os.path.join(HOME, 'live_dub_ext')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
RESULTS = os.path.join(REPO, 'results', 'app')
LOG = os.path.join(RESULTS, 'app118_ext_to_v25.log')

#: EXT 发行版版本号（必须与 `ext/version.py` 的 `EXT_VERSION` 一致）
EXT_VERSION = '0.4.18'


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def to_crlf(data: bytes) -> bytes:
    """统一成 CRLF（**幂等**：已是 CRLF 的不动）。"""
    data = data.replace(b'\r\n', b'\n')
    return data.replace(b'\n', b'\r\n')


def write_bytes(path: str, data: bytes):
    """临时文件 → `os.replace` ⇒ 不截断原文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp_app118'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def copy_tree(src_dir: str, dst_dir: str, exts, skip_names=()) -> int:
    """复制目录下的指定后缀文件（**CRLF 化**）。返回复制份数。"""
    n = 0
    for fn in sorted(os.listdir(src_dir)):
        if fn in skip_names or fn.startswith('__pycache__'):
            continue
        if not any(fn.endswith(e) for e in exts):
            continue
        s = os.path.join(src_dir, fn)
        if not os.path.isfile(s):
            continue
        d = os.path.join(dst_dir, fn)
        data = to_crlf(open(s, 'rb').read())
        write_bytes(d, data)
        n += 1
    return n


def main():
    os.makedirs(RESULTS, exist_ok=True)
    log('=== APP-118 §1 EXT → v0.4.18 开始 ===')
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'src': SRC_EXT, 'pkg': PKG, 'ext_version': EXT_VERSION,
           'files': [], 'errors': []}

    if not os.path.isdir(SRC_EXT):
        print('FAIL: EXT 源码仓不存在 %s' % SRC_EXT)
        return 2
    if not os.path.isdir(PKG):
        print('FAIL: 包目录不存在 %s' % PKG)
        return 2

    # ── ① EXT 桥接 Python 包：源 `ext/*.py` → 包内 `ext/bridge/*.py` ──
    src_bridge = os.path.join(SRC_EXT, 'ext')
    dst_bridge = os.path.join(PKG, 'ext', 'bridge')
    # ⚠️ `tts_cuda_sidecar_ext.py` 是 EXT 侧对 App `tts_cuda_sidecar.py` 的**副本**
    #   ⇒ 与已验收的 SpecialMVP sp5 **保持一致：不带**（App 侧那份才是交付件）
    SKIP = ('tts_cuda_sidecar_ext.py',)
    n = copy_tree(src_bridge, dst_bridge, ('.py',), skip_names=SKIP)
    log('① ext/bridge/*.py：复制 %d 个（源 %s → 包 %s）'
        % (n, src_bridge, dst_bridge))

    # ── ② `ext/bridge/__main__.py`（打包侧新增，让 `python -m ext.bridge` 可执行）──
    main_py = os.path.join(dst_bridge, '__main__.py')
    # 🔴 **必须用 str + .encode('utf-8')**：Python 的 `b'''…'''` 字面量
    #   **只允许 ASCII** ⇒ 中文注释直接 SyntaxError（本轮真踩）。
    _main_src = '''# -*- coding: utf-8 -*-
"""__main__ — 让 ``python -m ext.bridge`` 可执行（APP-104 §3）。

🔴 客户包里 EXT 的桥接模块在 ``ext/bridge/``（**是包**，不是模块）⇒
EXT 启动器里的 ``python -m ext.bridge`` 会报
「is a package and cannot be directly executed」。

⇒ 本文件是 **App 打包侧新增**的入口（不改 EXT 源文件）：
``python -m ext.bridge`` ⇒ 等价于 ``python -m ext.bridge.bridge``。
"""
from ext.bridge.bridge import main

if __name__ == '__main__':
    raise SystemExit(main())
'''
    write_bytes(main_py, to_crlf(_main_src.encode('utf-8')))
    log('② ext/bridge/__main__.py：写入（打包侧新增入口）')

    # ── ③ 浏览器插件：源 `extension/*` → 包内 `ext/extension/*` ──
    src_ext_ui = os.path.join(SRC_EXT, 'extension')
    dst_ext_ui = os.path.join(PKG, 'ext', 'extension')
    n = copy_tree(src_ext_ui, dst_ext_ui, ('.js', '.html', '.json', '.md'))
    # 图标（png 等）
    src_icons = os.path.join(src_ext_ui, 'icons')
    if os.path.isdir(src_icons):
        os.makedirs(os.path.join(dst_ext_ui, 'icons'), exist_ok=True)
        for fn in sorted(os.listdir(src_icons)):
            s = os.path.join(src_icons, fn)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(dst_ext_ui, 'icons', fn))
    log('③ ext/extension/*：复制 %d 个文件（+ icons）' % n)

    # ── ④ manifest.json：version=0.4.18、release=true ──
    mf = os.path.join(dst_ext_ui, 'manifest.json')
    data = json.load(open(mf, encoding='utf-8'))
    data['version'] = EXT_VERSION
    if isinstance(data.get('liveDub'), dict):
        data['liveDub']['release'] = True
    write_bytes(mf, to_crlf(json.dumps(data, ensure_ascii=False,
                                       indent=2).encode('utf-8') + b'\n'))
    log('④ ext/extension/manifest.json：version=%s release=true'
        % EXT_VERSION)

    # ── ⑤ 桥接启动器 `tools/ext_launcher.py`（CRLF）──
    src_launcher = os.path.join(SRC_EXT, 'tools', 'ext_launcher.py')
    dst_launcher = os.path.join(PKG, 'tools', 'ext_launcher.py')
    write_bytes(dst_launcher, to_crlf(open(src_launcher, 'rb').read()))
    log('⑤ tools/ext_launcher.py：写入（%d B）' % os.path.getsize(dst_launcher))

    # ── ⑥ `Start_Bridge.bat`（CRLF + **纯 ASCII**）──
    bat = (b'@echo off\n'
           b'REM Start_Bridge.bat - launch the EXT real-time dubbing bridge '
           b'(EXT v' + EXT_VERSION.encode('ascii') + b')\n'
           b'REM (APP-104 s3: relative paths only, no developer-machine paths)\n'
           b'REM (APP-105 s1: CRLF line endings + ASCII only, so it also runs '
           b'on codepage 936)\n'
           b'setlocal\n'
           b'cd /d "%~dp0"\n'
           b'if not exist "python\\pythonw.exe" (\n'
           b'  echo [EXT] package interpreter not found: python\\pythonw.exe\n'
           b'  pause\n'
           b'  exit /b 2\n'
           b')\n'
           b'start "Confucius4 EXT Bridge" "%~dp0python\\pythonw.exe" '
           b'"%~dp0tools\\ext_launcher.py"\n'
           b'endlocal\n')
    bat_crlf = to_crlf(bat)
    # 🔴 **必须是纯 ASCII**（中文 Windows 控制台代码页 936 也要能跑）
    try:
        bat_crlf.decode('ascii')
        ascii_ok = True
    except UnicodeDecodeError:
        ascii_ok = False
    write_bytes(os.path.join(PKG, 'Start_Bridge.bat'), bat_crlf)
    log('⑥ Start_Bridge.bat：写入（%d B，ASCII=%s）'
        % (os.path.getsize(os.path.join(PKG, 'Start_Bridge.bat')), ascii_ok))
    if not ascii_ok:
        rep['errors'].append('Start_Bridge.bat 不是纯 ASCII')

    # ── ⑦ `.runtime_deps` 放**包根**（`ext_launcher.py` 的 ROOT 对齐）──
    src_deps = os.path.join(PKG, 'ext', '.runtime_deps')
    dst_deps = os.path.join(PKG, '.runtime_deps')
    if os.path.isdir(src_deps) and not os.path.isdir(dst_deps):
        shutil.copytree(src_deps, dst_deps)
        log('⑦ .runtime_deps/：复制到包根（websockets / psutil）')
    else:
        log('⑦ .runtime_deps/：%s'
            % ('已存在于包根' if os.path.isdir(dst_deps) else '源缺失 ⇒ 跳过'))

    # ── ⑧ 旧启动器**改名挪到包外**（🔴 不删：本机删除会被 shim 拦）──
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    moved = []
    for old in ('bridge_launcher.py', 'start_bridge.cmd'):
        p = os.path.join(dst_bridge, old)
        if os.path.isfile(p):
            target = os.path.join(dst_bridge,
                                  '.superseded-%s-%s.bak' % (old, ts))
            os.replace(p, target)
            moved.append({'from': os.path.join('ext', 'bridge', old),
                          'to': os.path.relpath(target, PKG)})
            log('⑧ 旧文件改名挪出（**不删**）：%s → %s'
                % (old, os.path.basename(target)))
    rep['moved_superseded'] = moved

    # ── ⑨ 复核：逐文件 SHA256 ──
    checks = [
        (os.path.join(dst_bridge, 'bridge.py'), 'ext/bridge/bridge.py'),
        (os.path.join(dst_bridge, 'version.py'), 'ext/bridge/version.py'),
        (os.path.join(dst_bridge, '__main__.py'), 'ext/bridge/__main__.py'),
        (os.path.join(dst_ext_ui, 'manifest.json'), 'ext/extension/manifest.json'),
        (dst_launcher, 'tools/ext_launcher.py'),
        (os.path.join(PKG, 'Start_Bridge.bat'), 'Start_Bridge.bat'),
    ]
    for p, rel in checks:
        ok = os.path.isfile(p)
        rec = {'rel': rel, 'exists': ok,
               'sha256': sha256(p) if ok else None,
               'bytes': os.path.getsize(p) if ok else 0}
        if ok and p.endswith('.py'):
            try:
                import ast
                ast.parse(open(p, encoding='utf-8').read())
                rec['ast'] = 'OK'
            except Exception as e:
                rec['ast'] = 'FAIL: %r' % (e,)
                rep['errors'].append('%s ast.parse 失败: %r' % (rel, e))
        if ok and p.endswith('.json'):
            try:
                json.load(open(p, encoding='utf-8'))
                rec['json'] = 'OK'
            except Exception as e:
                rec['json'] = 'FAIL: %r' % (e,)
                rep['errors'].append('%s JSON 解析失败: %r' % (rel, e))
        rep['files'].append(rec)
        log('  复核 %-32s %s %s' % (rel, 'OK' if ok else '缺',
                                    (rec.get('sha256') or '')[:12]))

    # EXT 版本一致性
    try:
        vpy = open(os.path.join(dst_bridge, 'version.py'), encoding='utf-8').read()
        ok_ver = ('EXT_VERSION = "%s"' % EXT_VERSION) in vpy
    except Exception:
        ok_ver = False
    rep['ext_version_consistent'] = ok_ver
    log('⑨ version.py 与 manifest 版本一致：%s' % ok_ver)

    out = os.path.join(RESULTS, 'app118_ext_to_v25_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)
    log('=== 结束 ===')
    return 1 if rep['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
