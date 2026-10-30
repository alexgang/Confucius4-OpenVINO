#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c167_redact_spk_assets_to_pkg.py —— §102 / APP-044 补充：把 `app/asr_spk/`
里**含内部会议音频编号**的源码**脱敏**后同步回客户包。

## 为什么必须做（§102 实测）

`§101` 把 ASR 的 SpeakerTracker 接口代码同步进客户包 `<包>/app/asr_spk/`（10 个文件），
但其中 **4 个文件含内部会议音频编号 `260902`** ⇒ **App 自己的内部素材闸门 FAIL**：

```
$ python pack_v13.py --version 1.12 --dry-run
======================================================================
内部素材闸门（APP-006 第 6 步）
======================================================================
[待打包目录] C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12
  命中 4 个内部素材
    ⚠️ app/asr_spk/asr050_spk_qa_speaker_test.py  (内容关键词：会议音频编号 [REDACTED])
    ⚠️ app/asr_spk/asr_slice_common.py  (内容关键词：会议音频编号 [REDACTED])
    ⚠️ app/asr_spk/pya_app_path_seg.py  (内容关键词：会议音频编号 [REDACTED])
    ⚠️ app/asr_spk/pya_stream_segment.py  (内容关键词：会议音频编号 [REDACTED])

结论：FAIL —— 存在内部素材，禁止打包/提交
```

⇒ **这不是「zip 没重打」的问题，而是包内容本身不合规** ⇒ 必须先脱敏再打包。

## 为什么**不能删文件**（§102 实测：依赖闭包）

`asr052_speaker_tracker_api.py`（运行时入口）在**函数体内**真实 import 了它们：

| 位置 | import |
|---|---|
| `asr052:322` | `from asr050_spk_qa_speaker_test import WespeakerOVEncoder` |
| `asr052:323` | `from asr021_bypass_spk_wespeaker import OnlineSpeakerCluster` |
| `asr052:338` | `import pya_bypass_spk as PB` |
| `asr052:339` / `:365` / `:391` | `import pya_stream_segment as P` |

⇒ **删掉任何 4 个之一 ⇒ 客户机 import 链断裂 ⇒ 说话人旁路整条挂掉**。

## 为什么**不能整目录覆盖 / 不能手写替换串**（铁律 §一 / §九）

1. 🔴 仓库 ⇄ 客户包 = 两份独立副本 ⇒ **禁止整目录覆盖**。
2. 🔴 **绝不手写待插入的源码**（含 `\n` / `\t` 转义）⇒ 转义会被 Python 解释成真换行
   ⇒ 写进客户包后 `ast.parse` 报 `unterminated string literal` ⇒ **客户机启动即崩**。
   ⇒ 本脚本只做**「按行边界提取 + 定长替换」**，**不生成任何新源码行**。
3. 🔴 **定点替换必须行尾无关** ⇒ bytes 读入 → 检测 `b'\r\n'` → 归一化 LF 匹配/替换
   → 写回按**原行尾**还原；并要求「同步前后行尾不变」。

## 脱敏策略（§102 实测：命中点全是**测试语料**，无一是运行时逻辑）

`260902` 的 **8 处命中**逐条核对（AST 级）：

| 文件 | 位置 | 性质 |
|---|---|---|
| `asr_slice_common.py` | L5, L10 | docstring 说明 |
| `asr_slice_common.py` | L26 | `SOURCE_WAV` 常量（测试语料路径）|
| `asr050_spk_qa_speaker_test.py` | L7, L19 | docstring 说明 |
| `asr050_spk_qa_speaker_test.py` | L243 | argparse `--wav` 默认值 |
| `pya_app_path_seg.py` | L9 | docstring 说明 |
| `pya_app_path_seg.py` | L556 | 打印语句里的说明文本 |
| `pya_stream_segment.py` | L60 | `WAV` 常量 → argparse `--wav` 默认值 |

⇒ **全部**是「测试语料文件的路径 / 说明」；客户机运行时**不会**读这些 wav
   （客户机没有 `test_audio/` 目录）⇒ 脱敏**行为等价**。

🔴 **脱敏只改「音频编号」这一段字面量**（`260902` → `SPEQA`），**其余字节逐字不动**
   ⇒ 路径结构、argparse 语义、import 链全部保持。

## 用法

```
python sync_c167_redact_spk_assets_to_pkg.py --pkg <包根> [--dry-run]
```

⚠️ **不打包**：本脚本只改**包目录**里的文件；zip 由 `pack_v13.py` 另行重打（需持 `MACHINE_LOCK`）。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import sys

# 🔴 内部会议音频编号 → 中性占位符（**等长**，避免改动行号/字节偏移语义）
REDACT_FROM = b'260902'
REDACT_TO = b'SPEQA'

# 只处理这 4 个文件（§102 实测命中清单）；其余 6 个本就干净
TARGET_FILES = (
    'asr050_spk_qa_speaker_test.py',
    'asr_slice_common.py',
    'pya_app_path_seg.py',
    'pya_stream_segment.py',
)

# 包内 ASR 接口代码目录（相对包根）
PKG_ASR_SUBDIR = os.path.join('app', 'asr_spk')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_lf(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def detect_eol(b: bytes) -> bytes:
    """返回该文件原本的行尾序列（`b'\\r\\n'` 或 `b'\\n'`）。"""
    return b'\r\n' if b'\r\n' in b else b'\n'


def restore_eol(b: bytes, eol: bytes) -> bytes:
    """把归一化 LF 的内容按原行尾还原。"""
    if eol == b'\r\n':
        return b.replace(b'\n', b'\r\n')
    return b


def redact_bytes(raw: bytes) -> tuple:
    """返回 `(新内容, 命中次数)`。

    🔴 **只替换字面量 `260902`**，不触碰其它任何字节 ⇒ 行数、行尾、缩进全部不变。
    """
    n = raw.count(REDACT_FROM)
    if n == 0:
        return raw, 0
    return raw.replace(REDACT_FROM, REDACT_TO), n


def check_ast(path: str, content: bytes) -> None:
    """🔴 写盘前**必须** `ast.parse` 校验 ⇒ 不通过则中止、不落盘。"""
    try:
        src = content.decode('utf-8')
    except UnicodeDecodeError as e:
        raise SystemExit('[FATAL] 不是合法 UTF-8：%s（%s）' % (path, e))
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise SystemExit('[FATAL] ast.parse 失败，拒绝落盘：%s（%s）' % (path, e))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包根目录（含 app/ 与 models/）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pkg = args.pkg
    if not pkg:
        import glob
        cands = sorted(glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*'))
        cands = [c for c in cands if os.path.isdir(c)]
        if not cands:
            print('找不到客户包目录，请用 --pkg 指定')
            return 2
        pkg = cands[-1]
    if not os.path.isdir(pkg):
        print('客户包目录不存在：%s' % pkg)
        return 2

    print('客户包 = %s' % pkg)
    if args.dry_run:
        print('（dry-run：不落盘）')
    print()

    sub = os.path.join(pkg, PKG_ASR_SUBDIR)
    if not os.path.isdir(sub):
        print('包内没有 %s ⇒ 无需脱敏（APP-044 资产未同步？）' % PKG_ASR_SUBDIR)
        return 0

    total_hits = 0
    touched = []
    for fn in TARGET_FILES:
        p = os.path.join(sub, fn)
        if not os.path.isfile(p):
            print('  [MISSING] %s' % fn)
            continue
        raw = open(p, 'rb').read()
        eol = detect_eol(raw)
        body = norm_lf(raw)
        new_body, hits = redact_bytes(body)
        if hits == 0:
            print('  [CLEAN]   %-38s（无需脱敏）' % fn)
            continue
        total_hits += hits
        new_raw = restore_eol(new_body, eol)

        # 🔴 行尾不变 + 行数不变 + ast 合法（写盘前）
        assert detect_eol(new_raw) == eol, '行尾被改动：%s' % fn
        assert new_raw.count(b'\n') == raw.count(b'\n'), '行数被改动：%s' % fn
        check_ast(p, new_raw)

        if args.dry_run:
            print('  [DRY]     %-38s hits=%d  sha256=%s'
                  % (fn, hits, sha256_bytes(new_raw)[:16]))
            touched.append(fn)
            continue

        with open(p, 'wb') as f:
            f.write(new_raw)
        # 🔴 写盘后逐字节断言
        back = open(p, 'rb').read()
        assert back == new_raw, '写盘后内容不一致：%s' % fn
        print('  [REDACTED] %-37s hits=%d  %d → %d B  sha256=%s'
              % (fn, hits, len(raw), len(back), sha256_bytes(back)[:16]))
        touched.append(fn)

    print()
    print('命中合计 %d 处；处理文件 %d 个' % (total_hits, len(touched)))
    if not touched:
        print('⇒ 无需改动（包目录已干净）')
        return 0
    if not args.dry_run:
        print('⇒ 下一步：跑内部素材闸门复核，再重打包（持 MACHINE_LOCK）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
