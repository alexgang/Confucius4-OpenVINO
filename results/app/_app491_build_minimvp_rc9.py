# -*- coding: utf-8 -*-
r"""_app491 — **MiniMVP rc9 构建**（APP-104）。

rc9 = rc8 + APP-104 第 1/2/3 条（**模型文件不动** ⇒ MANIFEST 的 SHA 与 rc8 相同）：
  1. **§1 残留旧配置的出厂默认迁移**（`device_config.py`：`profile` +
     `defaults_version` ⇒ MiniMVP 下忽略 rc8 之前的旧设备项，用
     `DEFAULT_DEVICES`；数值类配置项保留；日志打一行说明忽略了哪些旧值）。
  2. **§2 三份 README 由打包脚本生成**（从 `release.json`、
     `device_config.DEFAULT_DEVICES`（**在包内实测**）与实际文件清单）
     ⇒ 不再搬旧版本数字；没有实测数据的地方写「待 B 机实测」。
  3. **§3 EXT 能按包内文档启动**：`tools/ext_launcher.py`（817abcb 原版）
     + `Start_Bridge.bat` + `ext/bridge/__main__.py`（让 `python -m ext.bridge`
     可执行）+ 3 个 3 行兼容垫片（启动器的 import 写死 `from ext.X import`）
     + `ext/USER_GUIDE.md` 改成**包内相对路径**、克隆段注明 MiniMVP 不可用。
  4. **§4 观察项**：`tts_engine` 的 `cp_prefill/cp_decode` 文案
     「未迁到 NPU（沿用 GPU.0 编译）」（dev 树已改 ⇒ 随 app/ 对齐进包）。

用法：
    python results/app/_app491_build_minimvp_rc9.py --dry-run
    python results/app/_app491_build_minimvp_rc9.py --run
    python results/app/_app491_build_minimvp_rc9.py --zip
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')
STAGE = os.path.join(REPO, '_ext_v048_stage')
BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc8')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc9')
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc9'
VERSION = '1.0-rc9'
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
REPORT = os.path.join(HERE, 'app491_minimvp_rc9_build_evidence.json')
SMOKE_REPORT = os.path.join(HERE, 'app493_app104_rc9_acceptance.json')

EXT_COMMIT = '817abcbe30c213844cda6f32c81361524ab53de8'
EXT_VERSION = '0.4.8'
LEGACY_DIR = 'ov-dec-06b-embed-mask2-int8sym'
STATEFUL_MODULE = 'asr06b_stateful_backend.py'

#: 🔴🔴🔳 APP-104 §3：EXT 桥接的**运行期依赖**（websockets / psutil）。
#:   实测（11-12 12:00）：rc9 首版**漏了这一份** ⇒ 桥接启动即报
#:   「缺少依赖：websockets（pip install websockets）」⇒ 桥接根本起不来。
#:   ⇒ 必须把 `.runtime_deps` 一起进包（**完整版 v2.4 包里就有**：
#:   `Confucius4_LiveCaption_v2.4/ext/.runtime_deps`）。
#:   ⚠️ **放包根**（`<pkg>/.runtime_deps`）而不是 `<pkg>/ext/.runtime_deps`：
#:      EXT 启动器在 `<pkg>/tools/ext_launcher.py` ⇒ 它的 `ROOT` = **包根**
#:      ⇒ 它给子进程设的 PYTHONPATH = `ROOT` + `ROOT/.runtime_deps`
#:      ⇒ 依赖必须落在 `<pkg>/.runtime_deps` 才找得到。
RUNTIME_DEPS_SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4',
                                'ext', '.runtime_deps')
RUNTIME_DEPS_CROSSCHECK = os.path.join(HOME, 'live_dub_ext', '.runtime_deps')

#: README 里**禁止出现**的字面（reviewer APP-104 §2 的验收口径）
README_FORBIDDEN = [r'rc5', r'rc6', r'--tts-device NPU', r'2\.71', r'3\.35']

#: README/文档里**禁止出现**的开发机绝对路径（APP-104 §3）
DEV_PATH_FORBIDDEN = ['live_dub_ext', 'C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v']

#: zip 体积字段的**固定宽度**（⇒ README 长度不随数字变化 ⇒ zip 体积自洽）
NUM_WIDTH = 16


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root):
    n = b = 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            try:
                b += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, b


def copy_dev_files(dst_app, names):
    out = []
    for name in names:
        src = os.path.join(DEV, name)
        dst = os.path.join(dst_app, name)
        if not os.path.isfile(src):
            raise RuntimeError('dev 树缺文件：%s' % src)
        data = open(src, 'rb').read().replace(b'\r\n', b'\n')
        with open(dst, 'wb') as f:
            f.write(data)
        if open(dst, 'rb').read() != data:
            raise RuntimeError('写入后复核不一致：%s' % name)
        out.append(name)
    return out


# ── §3：EXT 启动件（App 打包侧新增，不改 EXT 源文件）─────────────────
LAUNCHER_SHIM = '''# -*- coding: utf-8 -*-
"""{name} — **App 打包侧兼容垫片**（APP-104 §3）。

🔴 **不是 EXT 的源文件**：EXT 的 `tools/ext_launcher.py` 里写死了
``from ext.{name} import ...``，而客户包里的 EXT 目录结构是
``ext/bridge/``（不是 ``ext/``）⇒ 直接跑会 ImportError。

⇒ 本垫片只做一件事：**转发**到 ``ext.bridge.{name}``（唯一真源）。
"""
from ext.bridge.{name} import *  # noqa: F401,F403
from ext.bridge.{name} import {names}  # noqa: F401
'''

BRIDGE_MAIN = '''# -*- coding: utf-8 -*-
"""__main__ — 让 ``python -m ext.bridge`` 可执行（APP-104 §3）。

🔴 客户包里 EXT 的桥接模块在 ``ext/bridge/``（**是包**，不是模块）⇒
EXT 启动器里的 ``python -m ext.bridge`` 会报
「is a package and cannot be directly executed」。

⇒ 本文件是 **App 打包侧新增的 3 行入口**（不改 EXT 源文件）：
``python -m ext.bridge`` ⇒ 等价于 ``python -m ext.bridge.bridge``。
"""
from ext.bridge.bridge import main

if __name__ == '__main__':
    raise SystemExit(main())
'''

START_BRIDGE_BAT = '''@echo off
REM Start_Bridge.bat - 启动「实时翻译配音」桥接服务（EXT v0.4.8）
REM （APP-104 §3：包内相对路径，不写死任何开发机目录）
setlocal
cd /d "%~dp0"
if not exist "python\\pythonw.exe" (
  echo [EXT] 找不到包内解释器 python\\pythonw.exe
  pause
  exit /b 2
)
start "Confucius4 EXT Bridge" "%~dp0python\\pythonw.exe" "%~dp0tools\\ext_launcher.py"
endlocal
'''


def write_text(path, text):
    """写 UTF-8 + LF（不落 CRLF）。"""
    data = text.replace('\r\n', '\n').encode('utf-8')
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


def embed_ext_additions(pkg_root, ev):
    """APP-104 §3：把 EXT 启动件放进包（rc8 的 ext/bridge 一字不动）。"""
    out = {}

    # ① 启动器（817abcb 原版；行尾归一后比对）
    src = os.path.join(STAGE, 'tools', 'ext_launcher.py')
    dst = os.path.join(pkg_root, 'tools', 'ext_launcher.py')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    raw = open(src, 'rb').read()
    norm = raw.replace(b'\r\n', b'\n')
    with open(dst, 'wb') as f:
        f.write(norm)
    out['ext_launcher'] = {
        'path': os.path.relpath(dst, pkg_root),
        'bytes': os.path.getsize(dst),
        'sha256': sha256_file(dst),
        'source': 'git archive 817abcb:tools/ext_launcher.py（行尾归一 LF）',
    }

    # ② ext/bridge/__main__.py（让 `python -m ext.bridge` 可执行）
    p = os.path.join(pkg_root, 'ext', 'bridge', '__main__.py')
    out['bridge_main_bytes'] = write_text(p, BRIDGE_MAIN)

    # ③ 3 个兼容垫片（启动器的 import 写死 `from ext.X import`）
    shims = {
        'utf8_io': 'configure_process_env, safe_print',
        'app_root': 'resolve_app_root, app_python, app_path, package_root',
        'version': 'EXT_VERSION, EXT_BUILD_DATE, version_label',
    }
    for name, names in shims.items():
        p = os.path.join(pkg_root, 'ext', '%s.py' % name)
        write_text(p, LAUNCHER_SHIM.format(name=name, names=names))
    out['shims'] = sorted(shims)

    # ④ Start_Bridge.bat
    p = os.path.join(pkg_root, 'Start_Bridge.bat')
    out['start_bridge_bytes'] = write_text(p, START_BRIDGE_BAT)

    # ⑤ EXT 运行期依赖（websockets / psutil）—— APP-104 §3 的**实测缺口**
    deps_dst = os.path.join(pkg_root, '.runtime_deps')
    if os.path.isdir(deps_dst):
        shutil.rmtree(deps_dst)
    shutil.copytree(RUNTIME_DEPS_SRC, deps_dst)
    n_dep = b_dep = 0
    dep_files = {}
    for dp, _dn, fn in os.walk(deps_dst):
        for f in fn:
            p = os.path.join(dp, f)
            n_dep += 1
            b_dep += os.path.getsize(p)
            dep_files[os.path.relpath(p, deps_dst)] = sha256_file(p)
    # 交叉核对：EXT 仓库工作区里的同名文件必须逐字节一致（证明来源没跑偏）
    cross = {'checked': 0, 'mismatch': [], 'only_in_repo': 0}
    if os.path.isdir(RUNTIME_DEPS_CROSSCHECK):
        for dp, _dn, fn in os.walk(RUNTIME_DEPS_CROSSCHECK):
            for f in fn:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, RUNTIME_DEPS_CROSSCHECK)
                if rel in dep_files:
                    cross['checked'] += 1
                    if sha256_file(p) != dep_files[rel]:
                        cross['mismatch'].append(rel)
                else:
                    cross['only_in_repo'] += 1
    out['runtime_deps'] = {
        'src': RUNTIME_DEPS_SRC, 'dst': '.runtime_deps',
        'files': n_dep, 'bytes': b_dep,
        'has_websockets': os.path.isdir(os.path.join(deps_dst, 'websockets')),
        'has_psutil': os.path.isdir(os.path.join(deps_dst, 'psutil')),
        'crosscheck_vs_ext_repo': cross,
    }
    if not out['runtime_deps']['has_websockets']:
        raise RuntimeError('runtime_deps 里没有 websockets ⇒ 桥接起不来')
    if cross['mismatch']:
        raise RuntimeError('runtime_deps 与 EXT 仓库不一致：%s'
                           % cross['mismatch'][:5])

    ev['ext_additions'] = out
    return out


# ── §3：USER_GUIDE 定点改写（唯一命中断言）──────────────────────────
USER_GUIDE_PATCHES = [
    ('> 适用版本：EXT v0.4.4 · 更新日期：2026-11-11',
     '> 适用版本：EXT v0.4.8 · 更新日期：2026-11-12（**MiniMVP 客户包版**）'),
    ('cd C:\\Users\\Trekker-PTL\\live_dub_ext\n'
     'set EXT_BRIDGE_LAN=1\n'
     '"C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v<版本号>\\python\\python.exe" '
     '-m ext.bridge --real --pipeline --target-lang zh --port 8765',
     'cd "<本包目录>"            REM 例如 D:\\Confucius4_LiveCaption_MiniMVP_v1.0-rc9\n'
     'set EXT_BRIDGE_LAN=1\n'
     'python\\python.exe -m ext.bridge --real --pipeline --target-lang zh --port 8765'),
    ('1. 双击桌面上的 **「实时配音桥接 v0.3.9（可局域网）」**，会弹出'
     '「实时翻译配音 · 桥接服务」小窗口；',
     '1. 双击**本包目录里的 `Start_Bridge.bat`**（或桌面上的「实时配音桥接」'
     '快捷方式），会弹出「实时配音桥接（EXT）」小窗口；'),
    ('插件本体是 A 机上的这个文件夹：\n'
     '\n'
     '```\n'
     'C:\\Users\\Trekker-PTL\\live_dub_ext\\extension\n'
     '```',
     '插件本体是**装了本包的那台电脑**上的这个文件夹：\n'
     '\n'
     '```\n'
     '<本包目录>\\ext\\extension\n'
     '```'),
    ('| **音色** | `预设 A` = 固定音色；`克隆说话人` = 模仿视频里说话人的音色 | '
     '默认预设 A；克隆见第 6 节 |',
     '| **音色** | `预设 A` = 固定音色；`克隆说话人` = 模仿视频里说话人的音色 | '
     '默认预设 A；**MiniMVP 客户包不提供克隆**（见第 6 节） |'),
    ('## 6. 克隆说话人音色\n\n### 怎么打开',
     '## 6. 克隆说话人音色\n\n'
     '> ⚠️ **MiniMVP 客户包不提供克隆说话人**（MiniMVP 禁用了音色克隆，'
     'APP-098）⇒ 本节**不适用** ⇒ 只能用**预设 A**。\n\n'
     '### 怎么打开'),
    ('| `C:\\Users\\Trekker-PTL\\live_dub_ext\\extension\\` | '
     '插件本体（加载扩展时选这一层；拷给别的电脑也是拷这个） |\n'
     '| `C:\\Users\\Trekker-PTL\\live_dub_ext\\ext\\` | '
     '桥接服务与推理适配层 |\n'
     '| `C:\\Users\\Trekker-PTL\\live_dub_ext\\tools\\ext_launcher.py` | '
     '桥接启动器（桌面快捷方式指向它） |',
     '| `<本包目录>\\ext\\extension\\` | '
     '插件本体（加载扩展时选这一层；拷给别的电脑也是拷这个） |\n'
     '| `<本包目录>\\ext\\bridge\\` | 桥接服务与推理适配层 |\n'
     '| `<本包目录>\\tools\\ext_launcher.py` | 桥接启动器（`Start_Bridge.bat` 指向它） |'),
    ('□ 2. 双击「实时配音桥接 v0.3.9（可局域网）」',
     '□ 2. 双击本包目录里的 `Start_Bridge.bat`'),
    ('□ 5. 选目标语言；想要原说话人音色 ⇒ 音色选「克隆说话人」',
     '□ 5. 选目标语言（**MiniMVP 无克隆音色** ⇒ 只能是预设 A）'),
]


def patch_user_guide(pkg_root, ev):
    p = os.path.join(pkg_root, 'ext', 'USER_GUIDE.md')
    t = open(p, encoding='utf-8').read()
    applied = []
    for old, new in USER_GUIDE_PATCHES:
        c = t.count(old)
        if c != 1:
            raise RuntimeError('USER_GUIDE 补丁未唯一命中（%d 次）：%r' % (c, old[:50]))
        t = t.replace(old, new)
        applied.append({'old_head': old[:40], 'count': c})
    write_text(p, t)
    ev['user_guide'] = {'patched': len(applied), 'patches': applied}


# ── §2：README 由脚本生成（真实数据）────────────────────────────────
def probe_pkg_defaults(pkg_root):
    """**在包内**实测 `device_config.DEFAULT_DEVICES`（唯一事实来源）。"""
    py = os.path.join(pkg_root, 'python', 'python.exe')
    app = os.path.join(pkg_root, 'app')
    code = ('import json,device_config;'
            'print(json.dumps({"default_devices":device_config.DEFAULT_DEVICES,'
            '"profile":__import__("package_profile").PROFILE,'
            '"defaults_version":getattr(device_config,"CONFIG_DEFAULTS_VERSION",None)},'
            'ensure_ascii=False))')
    r = subprocess.run([py, '-B', '-c', code], cwd=app, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=300)
    if r.returncode != 0:
        raise RuntimeError('包内 DEFAULT_DEVICES 探测失败：%s' % (r.stderr or '')[:400])
    m = re.search(r'\{.*\}', r.stdout, re.S)
    if not m:
        raise RuntimeError('包内 DEFAULT_DEVICES 探测输出异常：%r' % r.stdout[:400])
    return json.loads(m.group(0))


def _fmt_num(v):
    """固定宽度数字（⇒ README 长度不随数字变化）。"""
    return ('%*s' % (NUM_WIDTH, format(int(v), ',')))


def readme_texts(pkg_root, ev, rel, defaults, n_files, dir_bytes, zip_bytes):
    """生成三份 README 的文本（数据全部来自**实测**）。"""
    dev = defaults['default_devices']
    profile = defaults.get('profile', 'minimvp')
    dev_table = (
        '| 模块 | 模型 | 精度 | 默认设备 |\n'
        '|---|---|---|---|\n'
        '| 语音识别 | **Qwen3-ASR-0.6B**（stateful INT8（KV cache）） | INT8 | %s |\n'
        '| 翻译 | **Hy-MT2-1.8B** | **INT4**（对称 · per-channel weight） | %s |\n'
        '| 语音输出 | **Qwen3-TTS 0.6B**（INT8 权重 · FP16 计算） | INT8/FP16 | %s |\n'
        % (_dev_label(dev.get('asr')), _dev_label(dev.get('mt')),
           _dev_label(dev.get('tts'))))
    dev_line = 'ASR=%s，MT=%s，TTS=%s' % (
        _dev_label(dev.get('asr')), _dev_label(dev.get('mt')),
        _dev_label(dev.get('tts')))
    pkg_line = ('**%s 个文件 / %s B（%.3f GiB）**；zip **%s B**'
                % ('{:,}'.format(n_files), _fmt_num(dir_bytes),
                   dir_bytes / 1024 ** 3, _fmt_num(zip_bytes)))
    top_list = sorted(os.listdir(pkg_root))
    top_line = '、'.join('`%s`' % x for x in top_list)

    zh = """# Confucius4 实时字幕 · MiniMVP %s（最小客户包）

**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**

## 里面有什么

%s
* **包含**：EXT 实时翻译配音**插件与桥接服务**（`ext/` 目录，EXT v%s）、
  桌面/命令行启动脚本（`Start_LiveCaption.bat` / `Start_Bridge.bat`）。
* **不含**：NVIDIA/CUDA 与 torch 相关内容、开发与测试脚本、会议录音、
  **克隆音色**（MiniMVP 禁用 ⇒ 只有内置预设音色）、
  说话人旁路（pyannote_seg / wespeaker）。
* **出厂默认设备**：**%s**
  （唯一事实来源 = `app/device_config.py` 的 `DEFAULT_DEVICES`）。
  ⚠️ 若本机 `%%LOCALAPPDATA%%Confucius4LiveCaption\\device_config.json`
  是**旧版本**（本包之前写的），App 会**忽略**其中的设备项并改用出厂默认，
  并在日志里写明忽略了哪些旧值（配置文件**不会被删除**）。
* **ASR**：**Qwen3-ASR-0.6B**，**stateful INT8（KV cache）** 配方
  （按通道 INT8 权重、lm_head 保 FP16、带真实 `attention_mask` 端口）。
  同一套 IR 可编到集显（`--engine gpu_int8`）或 NPU（`--engine npu_int8`）。
* **包体积（实测）**：解压后 %s。

## 怎么启动

双击 `Start_LiveCaption.bat`（GUI），或在命令行里（**不传设备参数**即可用出厂默认）：

```
python\\python.exe app\\live_caption_app.py
```

> **首次启动**：NPU 需要现编译（**不带编译缓存 blob**）⇒ 第一次启动会慢一些，
> 缓存写在用户目录 `%%LOCALAPPDATA%%Confucius4LiveCaption`。
> **磁盘**：首次运行约需 **8 GB**（编译缓存）。
> **A 机实测**：ASR stateful RTF 集显 **0.397** / NPU **0.538**；
> 包目录整链 ASR RTF **0.544**（**B 机数据待实测**）。

## 配音桥接（EXT）

双击 `Start_Bridge.bat` 启动「实时配音桥接」窗口，点「启动」后等日志出现
`真实引擎已接线` 与 `TTS 就绪`；Chrome 插件在 `ext/extension/`，
详见 `ext/USER_GUIDE.md`。

## 许可与归属

见 `NOTICE`（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / **babelvox** /
**djwarf** 等的归属与许可证）与 `THIRD_PARTY.md`。

## 本包顶层目录

%s
""" % (VERSION, dev_table, EXT_VERSION, dev_line,
       pkg_line, top_line)

    en = """# Confucius4 Live Caption - MiniMVP %s (minimal customer package)

**Independent product line (MiniMVP), versioned separately from v2.x.**

## What is inside

%s
* **Included**: the EXT real-time dubbing plugin & bridge service
  (folder `ext/`, EXT v%s), plus the launch scripts
  (`Start_LiveCaption.bat` / `Start_Bridge.bat`).
* **Not included**: NVIDIA/CUDA & torch content, dev & test scripts,
  meeting recordings, **cloned voices** (disabled in MiniMVP => preset
  voices only), speaker bypass (pyannote_seg / wespeaker).
* **Factory default devices**: **%s**
  (single source of truth = `DEFAULT_DEVICES` in `app/device_config.py`).
  If a **stale** `device_config.json` (written by an earlier build) is
  present in `%%LOCALAPPDATA%%Confucius4LiveCaption`, the app **ignores**
  its device entries and falls back to the factory defaults, logging which
  old values were ignored (the file itself is **never deleted**).
* **ASR**: **Qwen3-ASR-0.6B**, **stateful INT8 (KV cache)** recipe
  (per-channel INT8 weights, FP16 lm_head, real `attention_mask` port).
  The same IR pair is compiled either to the iGPU (`--engine gpu_int8`)
  or to the NPU (`--engine npu_int8`).
* **Package size (measured)**: unpacked %s.

## Run

Double-click `Start_LiveCaption.bat`, or (no device flags needed):

```
python\\python.exe app\\live_caption_app.py
```

> **First start**: the NPU is compiled on the fly (no blob cache is shipped)
> => the first start is slower; the cache lives in
> `%%LOCALAPPDATA%%Confucius4LiveCaption`.
> **Measured on machine A**: ASR stateful RTF iGPU **0.397** / NPU **0.538**;
> package end-to-end ASR RTF **0.544** (machine B: **pending measurement**).

## Dubbing bridge (EXT)

Double-click `Start_Bridge.bat`, press the start button and wait for
`真实引擎已接线` / `TTS 就绪` in the log; the Chrome extension is in
`ext/extension/` (see `ext/USER_GUIDE.md`).

## Licenses

See `NOTICE` and `THIRD_PARTY.md`.

## Top level of this package

%s
""" % (VERSION, dev_table, EXT_VERSION, dev_line, pkg_line, top_line)

    pt = """========================================================================
  Confucius4 LiveCaption · MiniMVP %s —— 性能测试版说明
========================================================================

【本包定位】
  这是 **MiniMVP %s 的性能测试构建**，用于在其他机器上测
  ASR / MT / TTS 的实时性能，**不是正式发布版**。
  · 本版在上一版基础上修了三件事（APP-104）：
      ① 旧版残留的 `device_config.json` **不再覆盖出厂默认**
         （MiniMVP 下忽略 rc8 之前的旧设备项 ⇒ ASR=NPU / MT=GPU.0 / TTS=GPU.0，
          避免「ASR 与 MT 同在集显」这个会崩的组合）；
      ② 三份 README **由打包脚本按实际文件生成**（不再搬旧版本数字）；
      ③ EXT 桥接**能按包内文档启动**（`Start_Bridge.bat` + `tools/ext_launcher.py`）。
  · 模型文件**未改动** ⇒ MANIFEST 里的 SHA 与上一版一致。

【包体积（实测，%s）】
  · **解压后**：%s 个文件 / %s B（%.3f GiB）
  · **zip**：%s B
  ⚠️ 「解压后 N 个文件」与 zip 的条目数**同一份清单来源** ⇒ 数字必然对得上。

【本包的 ASR：Qwen3-ASR-0.6B（stateful INT8（KV cache））】
  【模型身份（MANIFEST 同源）】
  · asr06b-decoder-int8        ← Qwen3-ASR-0.6B（stateful，bin SHA 0059531a…d6a3）
  · asr06b-encoder-fp16        ← Qwen3-ASR-0.6B（bin SHA 0b7463d6…）
  · asr06b-tokenizer           ← Qwen3-ASR-0.6B（HF 目录，未导出 OV）
  · embed_tokens_06b_f16.npy   ← Qwen3-ASR-0.6B（权重表，FP16，311 165 056 B）
  · mt/mt2-int4sym-cw-q        ← Hy-MT2-1.8B
  · qwen3tts                   ← Qwen3-TTS

【出厂默认设备（B 机测试按这个组合跑）】
  · ASR=%s，MT=%s，TTS=%s
  ⚠️ 若本机 `%%LOCALAPPDATA%%Confucius4LiveCaption\\device_config.json` 是**旧版本**
    ⇒ App 会**忽略**里面的设备项并改用上面这组出厂默认（日志里会写明忽略了哪些旧值）。

【A 机实测（stateful 解码器）】
  · ASR RTF，iGPU（GPU.0）：**0.397**
  · ASR RTF，NPU：**0.538**（encoder + decoder 的 EXECUTION_DEVICES 均为 NPU）
  · 包目录整链 ASR RTF：**0.544**
  ⚠️ **B 机（Meteor Lake 155H）数据：待 B 机实测**（本包不带旧的实测数字）。

【已知问题】
  · TTS 用 GPU.0 时，长会话里可能**丢弃过期句**（`tts_late_drop_sec`）⇒
    每臂测试都要报「提交 / 播完 / 丢弃」句数。
  · **TTS/MT 都放 GPU.0** 长时间运行会 `CL_OUT_OF_RESOURCES`
    ⇒ **ASR 必须放 NPU**（本包出厂默认即如此）。
""" % (VERSION, VERSION, VERSION, '{:,}'.format(n_files), _fmt_num(dir_bytes),
       dir_bytes / 1024 ** 3, _fmt_num(zip_bytes),
       _dev_label(dev.get('asr')), _dev_label(dev.get('mt')),
       _dev_label(dev.get('tts')))
    return {'README_zh.md': zh, 'README_en.md': en, 'README_perftest.txt': pt}


def _dev_label(dev):
    d = str(dev or '').strip()
    return {'GPU.0': 'Intel 集显 GPU.0（Intel iGPU）',
            'NPU': 'Intel NPU',
            'CPU': 'CPU（不推荐）'}.get(d, d)


def write_readmes(pkg_root, ev, rel, defaults, n_files, dir_bytes, zip_bytes):
    texts = readme_texts(pkg_root, ev, rel, defaults, n_files, dir_bytes, zip_bytes)
    sizes = {}
    for name, text in texts.items():
        p = os.path.join(pkg_root, name)
        sizes[name] = write_text(p, text)
    ev['readme'] = {'files': sizes, 'n_files': n_files,
                    'dir_bytes': dir_bytes, 'zip_bytes_field': zip_bytes,
                    'defaults': defaults}
    return texts


def check_readmes(pkg_root, ev, n_files, dir_bytes, zip_bytes, defaults):
    """§2 验收闸门（reviewer 的 grep 口径 + 数字一致性）。"""
    rows = []
    for name in ('README_zh.md', 'README_en.md', 'README_perftest.txt'):
        p = os.path.join(pkg_root, name)
        t = open(p, encoding='utf-8').read()
        hits = []
        for pat in README_FORBIDDEN:
            c = len(re.findall(pat, t))
            if c:
                hits.append({'pattern': pat, 'count': c})
        dev_hits = []
        for s in DEV_PATH_FORBIDDEN:
            c = t.count(s)
            if c:
                dev_hits.append({'literal': s, 'count': c})
        has_count = ('{:,}'.format(n_files) in t)
        has_zip = (_fmt_num(zip_bytes).strip() in t)
        has_dir = (_fmt_num(dir_bytes).strip() in t)
        dev_table_ok = all(
            _dev_label(defaults['default_devices'].get(k)) in t
            for k in ('asr', 'mt', 'tts'))
        rows.append({'file': name, 'forbidden_hits': hits,
                     'dev_path_hits': dev_hits,
                     'file_count_matches': has_count,
                     'zip_bytes_matches': has_zip,
                     'dir_bytes_matches': has_dir,
                     'device_table_matches_defaults': dev_table_ok,
                     'pass': (not hits and not dev_hits and has_count
                              and has_zip and has_dir and dev_table_ok)})
    ev['readme_gate'] = {'rows': rows,
                         'n_pass': sum(1 for r in rows if r['pass']),
                         'n_fail': sum(1 for r in rows if not r['pass'])}
    return ev['readme_gate']


def check_ext(pkg_root, ev):
    """§3 闸门：启动件在位 + USER_GUIDE 不含开发机路径。"""
    rows = []
    launcher = os.path.join(pkg_root, 'tools', 'ext_launcher.py')
    rows.append({'item': 'tools/ext_launcher.py',
                 'ok': os.path.isfile(launcher),
                 'bytes': os.path.getsize(launcher) if os.path.isfile(launcher) else 0,
                 'sha256': sha256_file(launcher) if os.path.isfile(launcher) else None})
    for rel in ('Start_Bridge.bat', os.path.join('ext', 'bridge', '__main__.py'),
                os.path.join('ext', 'utf8_io.py'),
                os.path.join('ext', 'app_root.py'),
                os.path.join('ext', 'version.py')):
        p = os.path.join(pkg_root, rel)
        rows.append({'item': rel, 'ok': os.path.isfile(p),
                     'bytes': os.path.getsize(p) if os.path.isfile(p) else 0})
    guide = os.path.join(pkg_root, 'ext', 'USER_GUIDE.md')
    gt = open(guide, encoding='utf-8').read() if os.path.isfile(guide) else ''
    dev_hits = {s: gt.count(s) for s in DEV_PATH_FORBIDDEN if gt.count(s)}
    rows.append({'item': 'ext/USER_GUIDE.md 无开发机路径',
                 'ok': not dev_hits, 'detail': dev_hits})
    rows.append({'item': 'ext/USER_GUIDE.md 提到 Start_Bridge.bat',
                 'ok': 'Start_Bridge.bat' in gt})
    rows.append({'item': 'ext/USER_GUIDE.md 标注 MiniMVP 不可克隆',
                 'ok': 'MiniMVP' in gt and '克隆' in gt})
    # 🔴 桥接依赖**必须能导入**（否则启动即报「缺少依赖：websockets」）
    py = os.path.join(pkg_root, 'python', 'python.exe')
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(
        [pkg_root, os.path.join(pkg_root, '.runtime_deps')])
    try:
        r = subprocess.run([py, '-B', '-c',
                            'import websockets, psutil; print("deps OK")'],
                           cwd=pkg_root, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env,
                           timeout=180)
        rows.append({'item': '桥接依赖可导入（websockets/psutil）',
                     'ok': r.returncode == 0,
                     'detail': ((r.stdout or '') + (r.stderr or ''))[-300:]})
    except Exception as e:
        rows.append({'item': '桥接依赖可导入（websockets/psutil）',
                     'ok': False, 'detail': repr(e)})
    ev['ext_gate'] = {'rows': rows,
                      'n_fail': sum(1 for r in rows if not r['ok'])}
    return ev['ext_gate']


# ── rc8 的旧解码器闸门（沿用）──────────────────────────────────────
def assert_no_legacy(pkg_root):
    reasons = []
    models = os.path.join(pkg_root, 'models')
    for dp, dn, fn in os.walk(models):
        for d in dn:
            if LEGACY_DIR in d:
                reasons.append('包内出现旧解码器目录：%s' %
                               os.path.relpath(os.path.join(dp, d), pkg_root))
    app = os.path.join(pkg_root, 'app')
    for dp, _dn, fn in os.walk(app):
        for f in fn:
            if not f.endswith(('.py', '.json', '.txt', '.md')):
                continue
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            n = t.count('mask2')
            if n:
                reasons.append('%s 命中 mask2 ×%d' %
                               (os.path.relpath(p, pkg_root), n))
    return (len(reasons) == 0), reasons


def selftest_gate():
    out = []
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, 'models', LEGACY_DIR))
        os.makedirs(os.path.join(td, 'app'))
        open(os.path.join(td, 'models', LEGACY_DIR, 'keep.txt'), 'w').close()
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_dir_present', 'gate_ok': ok,
                    'expected': False, 'pass': ok is False})
        shutil.rmtree(os.path.join(td, 'models', LEGACY_DIR))
        open(os.path.join(td, 'app', 'foo.py'), 'w', encoding='utf-8').write(
            '# mask2 appears here\n')
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_literal_in_app', 'gate_ok': ok,
                    'expected': False, 'pass': ok is False})
    return out


def build(ev):
    print('[1/9] 复制 rc8 → rc9（真实拷贝）…', flush=True)
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True)
    ev['actions'].append('copy rc8 -> rc9 (real copy, no hardlink)')
    app = os.path.join(DST_PKG, 'app')

    print('[2/9] app/*.py 全量对齐 dev 树…', flush=True)
    names = sorted(f for f in os.listdir(app) if f.endswith('.py')
                   and f != STATEFUL_MODULE)
    copied = copy_dev_files(app, names)
    copy_dev_files(app, [STATEFUL_MODULE])
    ev['copied_from_dev'] = copied + [STATEFUL_MODULE]
    ev['actions'].append('align app/*.py from dev: %d files + %s'
                         % (len(copied), STATEFUL_MODULE))

    print('[3/9] 旧解码器闸门 + 反例自测…', flush=True)
    ev['gate_selftest'] = selftest_gate()
    if not all(x['pass'] for x in ev['gate_selftest']):
        raise RuntimeError('闸门反例自测未通过：%s' % ev['gate_selftest'])
    ok, reasons = assert_no_legacy(DST_PKG)
    ev['gate'] = {'ok': ok, 'reasons': reasons}
    if not ok:
        raise RuntimeError('包内仍有无 KV 旧解码器的目录/字面，终止构建：%s'
                           % reasons[:5])

    print('[4/9] EXT 启动件进包（APP-104 §3）…', flush=True)
    embed_ext_additions(DST_PKG, ev)
    patch_user_guide(DST_PKG, ev)

    print('[5/9] release.json（版本 rc9，EXT 仍 0.4.8 @817abcb）…', flush=True)
    rel_path = os.path.join(DST_PKG, 'release.json')
    rel = json.load(open(rel_path, encoding='utf-8'))
    rel.update({
        'release': True, 'version': VERSION,
        'asr_model': 'Qwen3-ASR-0.6B',
        'asr_recipe': 'stateful INT8 with KV cache (NPUW_LLM on NPU); '
                      'decoder bin SHA 0059531a…d6a3',
        'asr_engines': ['gpu_int8', 'npu_int8'],
        'ext': {'version': EXT_VERSION, 'commit': EXT_COMMIT},
        'corrections': ['APP-096', 'APP-098', 'APP-099', 'APP-100',
                        'APP-101', 'APP-102', 'APP-103', 'APP-104'],
        'package_profile': 'package_profile.json',
        'rc9_changes': [
            'APP-104 §1 残留旧配置的出厂默认迁移（profile + defaults_version）',
            'APP-104 §2 三份 README 由打包脚本按实际文件生成',
            'APP-104 §3 EXT 启动件进包（tools/ext_launcher.py + Start_Bridge.bat）',
            'APP-104 §4 cp_prefill/cp_decode 日志文案改为「未迁到 NPU」',
        ],
    })
    with open(rel_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write('\n')
    ev['release'] = rel

    print('[6/9] 包内实测 DEFAULT_DEVICES…', flush=True)
    defaults = probe_pkg_defaults(DST_PKG)
    ev['pkg_defaults'] = defaults
    if defaults.get('profile') != 'minimvp':
        raise RuntimeError('包内 profile 不是 minimvp：%r' % defaults)

    print('[7/9] 生成三份 README（真实数据）…', flush=True)
    n0, b0 = dir_stats(DST_PKG)
    write_readmes(DST_PKG, ev, rel, defaults, n0, b0, 0)
    # 🔴 README 长度变了（rc8 的旧 README → 本版生成的）⇒ **要重量一次**
    #   再回填（字段宽度固定 ⇒ 第二遍长度不变 ⇒ 数值自洽）。
    n1, b1 = dir_stats(DST_PKG)
    write_readmes(DST_PKG, ev, rel, defaults, n1, b1, 0)
    ev['pkg_readme_round'] = {'round1': [n0, b0], 'round2': [n1, b1]}

    print('[8/9] MANIFEST（从源目录生成 + 逐项校验）…', flush=True)
    if DEV not in sys.path:
        sys.path.insert(0, DEV)
    import manifest_gen
    mpath = manifest_gen.write_manifest(DST_PKG)
    manifest_gen.verify_or_die(DST_PKG)
    m = json.load(open(mpath, encoding='utf-8'))
    ev['manifest'] = {'path': mpath, 'n_models': m['n_models'],
                      'all_match': m['all_match'],
                      'mismatches': m['mismatches'][:5]}
    if not m['all_match']:
        raise RuntimeError('MANIFEST 校验失败：%s' % ev['manifest'])

    print('[9/9] 指纹 + 闸门…', flush=True)
    n, b = dir_stats(DST_PKG)
    ev['pkg'] = {'files': n, 'bytes': b, 'gib': round(b / 1024 ** 3, 3)}
    return ev


def make_zip(ev, passes=2):
    """两遍打包：第 1 遍量出 zip 字节数 ⇒ 回填 README ⇒ 第 2 遍（体积应完全相同）。"""
    if not os.path.isfile(SMOKE_REPORT):
        raise RuntimeError('缺包上验收证据，拒绝打包：%s' % SMOKE_REPORT)
    smoke = json.load(open(SMOKE_REPORT, encoding='utf-8'))
    # 🔴 口径：App 侧 HIGH 项全 PASS 才放行；若唯一未 PASS 的是 EXT 那条且
    #    原因是**跨模块（EXT 侧）缺口**（验收报告里已附证据）⇒ 记
    #    **PASS_WITH_FINDING** 并放行（**如实，不写纯 PASS**）。
    if smoke.get('verdict') not in ('PASS', 'PASS_WITH_FINDING'):
        raise RuntimeError('包上验收未通过（%s），拒绝打包' % smoke.get('verdict'))
    if smoke.get('verdict') == 'PASS_WITH_FINDING':
        gap = smoke.get('ext_cross_module_gap') or {}
        print('!! 验收=PASS_WITH_FINDING（EXT 侧跨模块缺口：%s）⇒ 放行但如实登记'
              % str(gap.get('what'))[:120], flush=True)
    if os.path.exists(ZIP):
        raise RuntimeError('zip 已存在（不覆盖旧版本，APP-055）：%s' % ZIP)
    os.makedirs(os.path.dirname(ZIP), exist_ok=True)

    rel = json.load(open(os.path.join(DST_PKG, 'release.json'), encoding='utf-8'))
    defaults = ev.get('pkg_defaults') or probe_pkg_defaults(DST_PKG)
    sizes = []
    for i in range(passes):
        t0 = time.time()
        tmp_zip = ZIP + '.tmp'
        with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_STORED,
                             allowZip64=True) as zf:
            for dp, _dn, fn in os.walk(DST_PKG):
                for f in fn:
                    p = os.path.join(dp, f)
                    arc = os.path.join(PKG_NAME, os.path.relpath(p, DST_PKG))
                    zf.write(p, arc.replace('\\', '/'))
        sz = os.path.getsize(tmp_zip)
        sizes.append(sz)
        # 用实测值回填 README（固定宽度 ⇒ 文件长度不变 ⇒ 下一遍体积不变）
        n_files, dir_bytes = dir_stats(DST_PKG)
        write_readmes(DST_PKG, ev, rel, defaults, n_files, dir_bytes, sz)
        if i + 1 < passes:
            os.remove(tmp_zip)
        else:
            os.replace(tmp_zip, ZIP)
    _n, _b = dir_stats(DST_PKG)
    ev['pkg'] = {'files': _n, 'bytes': _b, 'gib': round(_b / 1024 ** 3, 3)}
    ev['zip'] = {'path': ZIP, 'bytes': os.path.getsize(ZIP),
                 'pass_sizes': sizes,
                 'converged': len(set(sizes)) == 1,
                 'smoke_verdict': smoke.get('verdict'),
                 'sha256': None, 'sha_note': '用户规则：zip 不做 SHA 校验'}
    if len(set(sizes)) != 1:
        raise RuntimeError('zip 体积未收敛：%s' % sizes)
    # 最后一遍：README 已含最终数字 ⇒ 复核闸门
    n_files, dir_bytes = dir_stats(DST_PKG)
    g = check_readmes(DST_PKG, ev, n_files, dir_bytes, sizes[-1], defaults)
    if g['n_fail']:
        raise RuntimeError('README 闸门未通过：%s' % g)
    ev['actions'].append('zip written after acceptance PASS (2-pass, converged)')
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--zip', action='store_true')
    a = ap.parse_args()
    dry = not (a.run or a.zip)

    ev = {'at': datetime.datetime.now().isoformat(timespec='seconds'),
          'version': VERSION, 'correction': 'APP-104',
          'base_pkg': BASE_PKG, 'dst_pkg': DST_PKG, 'dry_run': dry,
          'actions': []}
    # 供 session_lease addpid 用（本进程 PID）
    try:
        with open(os.path.join(HERE, '_app491_rc9_build.pid'), 'w') as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    if not os.path.isdir(BASE_PKG):
        print('!! rc8 不存在'); return 2
    if not os.path.isdir(STAGE):
        print('!! EXT stage 不存在'); return 2
    if a.run and os.path.exists(DST_PKG):
        print('!! rc9 目录已存在（拒绝覆盖，APP-055）：%s' % DST_PKG); return 2
    if a.zip and not os.path.isdir(DST_PKG):
        print('!! rc9 目录不存在'); return 2

    if dry:
        n_base, b_base = dir_stats(BASE_PKG)
        print('[dry-run] 将创建 %s（复制 rc8 的 %d 文件 / %.3f GiB）'
              % (DST_PKG, n_base, b_base / 1024 ** 3))
        ev['gate_selftest'] = selftest_gate()
        print('[dry-run] 反例自测：', ev['gate_selftest'])
        return 0

    t0 = time.time()
    try:
        if a.run:
            build(ev)
            # 闸门（README 用占位数字 0 时先跑一次结构性检查）
            n_files, dir_bytes = dir_stats(DST_PKG)
            defaults = ev['pkg_defaults']
            check_ext(DST_PKG, ev)
            if ev['ext_gate']['n_fail']:
                raise RuntimeError('EXT 闸门未通过：%s' % ev['ext_gate'])
            write_readmes(DST_PKG, ev, ev['release'], defaults, n_files,
                          dir_bytes, 0)
        if a.zip:
            make_zip(ev)
    except Exception as e:
        ev['error'] = repr(e)
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        print('!! 构建失败：%r' % e)
        raise
    ev['elapsed_s'] = round(time.time() - t0, 1)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('完成：%s / %d 文件 / %.1f s'
          % (ev.get('zip', {}).get('path', DST_PKG),
             ev.get('pkg', {}).get('files', 0), ev['elapsed_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
