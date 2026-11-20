#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119：把 dev 树的改动定点同步进 v2.5 客户包**。

同步范围（**只这 2 个运行时文件**）：
  * ``device_config.py``   —— 出厂默认 GPU.0/GPU.0/NPU ＋ 代次 11 ＋ 迁移判据
  * ``live_caption_app.py`` —— 删除 NPU 互斥强制逻辑（GUI + CLI）

**不**同步整个目录、**不**碰其它模块的文件、**不**打包（APP-119 §3：不打 zip）。
README（zh/en）只改「默认设备摆放」相关的**定点段落**。

纪律：
  * 写盘走 **临时文件 → os.replace**；
  * 写后逐文件 **SHA256 + ast.parse** 复核；
  * README 用**精确字符串替换 + 唯一命中断言**；
  * 证据落盘：``results/app/app119_sync_v25_evidence.json``
    （文件数 / mtime / 字节数 / SHA256）。
"""
import ast
import datetime
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEV = os.path.join(REPO, 'live_caption')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
PKG_APP = os.path.join(PKG, 'app')
OUT = os.path.join(REPO, 'results', 'app', 'app119_sync_v25_evidence.json')

RUNTIME_PY = ['device_config.py', 'live_caption_app.py']

# ── README 定点替换（唯一命中）────────────────────────────────────────────
ZH = os.path.join(PKG, 'README_zh.md')
EN = os.path.join(PKG, 'README_en.md')

ZH_REPL = [
    # ① 默认设备表里的 TTS 行
    ('| **语音输出（TTS）** | **Intel NPU** | **NPU 只给语音输出独占使用** |',
     '| **语音输出（TTS）** | **Intel NPU** | **出厂默认（APP-119 §1）** |'),
    # ② 表下的说明块
    ('> ⚠️ ASR / 翻译的**回退链里不再有 NPU** —— 避免两者和语音输出抢同一个\n'
     '> 加速器，导致三边互相拖慢。CUDA **不是默认值**。',
     '> ℹ️ **三个模块的设备可以自由搭配**（APP-119 §2）—— 不再有任何「谁不许用\n'
     '> NPU」的强制规则：ASR / 翻译 / 语音输出**可以同时放在 NPU**，程序**不会**\n'
     '> 自动改你选的设备。若共用 NPU，语音输出区会有一条**不阻塞的性能提示**\n'
     '> （合成可能慢 25–30 %）。\n'
     '> ⚠️ ASR / 翻译的**回退链里仍没有 NPU** —— 回退只在「你选的设备本机根本\n'
     '> 不存在」时发生；落到 NPU 等于把你**没选的设备**悄悄换上。CUDA **不是默认值**。'),
    # ③ 首段摘要里的「独占」
    ('默认设备摆放定案（ASR/翻译走集显、语音输出独占 NPU）',
     '默认设备摆放定案（ASR/翻译走集显、语音输出走 NPU，三模块设备可自由搭配）'),
]

EN_REPL = [
    ('| **Speech output (TTS)** | **Intel NPU** | **The NPU is used exclusively by speech output** |',
     '| **Speech output (TTS)** | **Intel NPU** | **Factory default (APP-119 §1)** |'),
    ('> ⚠️ The **fallback chains for ASR and translation no longer include the NPU**\n'
     '> — otherwise all three would compete for the same accelerator and slow each\n'
     '> other down. CUDA is **not** a default.',
     '> ℹ️ **The three modules may be placed on any device freely** (APP-119 §2) —\n'
     '> there is no longer any rule reserving the NPU for speech output: ASR,\n'
     '> translation and speech output **may all use the NPU**, and the program will\n'
     '> **never** change the device you picked. When the NPU is shared, the speech\n'
     '> output panel shows one **non-blocking** performance hint (synthesis may be\n'
     '> 25–30 % slower).\n'
     '> ⚠️ The **fallback chains for ASR and translation still exclude the NPU** —\n'
     '> a fallback only happens when the device you picked does not exist on this\n'
     '> machine; falling back to the NPU would silently move a module to a device\n'
     '> you did not choose. CUDA is **not** a default.'),
    ('speech output with exclusive use of the NPU',
     'speech output on the NPU; the three modules may share devices freely'),
]

ZH_NEW_SECTION = """### 5. 🔴 出厂默认改为「语音输出走 NPU」＋ 取消 NPU 独占限制（APP-119）

- **出厂默认**改成 **ASR = Intel 集显（GPU.0）／翻译 = Intel 集显（GPU.0）／
  语音输出 = Intel NPU**。ASR 模型**仍是 R2T2 1.7B**，不变。
- **取消**「MT 和 TTS 不能同时放在 NPU ⇒ 自动把 MT 挪到 GPU.0」这条强制规则：
  三个模块的设备**可以自由搭配**，程序**不再自动改**你选的设备。
  若确实共用 NPU，语音输出区只给一条**不阻塞的性能提示**。
- 旧配置**自动迁移**：没手动改过设备的老配置会迁到新默认；**手动选过的
  保持原样**（迁移过程写进日志）。

"""

EN_NEW_SECTION = """### 5. 🔴 Factory default is now "speech output on the NPU", and the NPU is no
   longer reserved (APP-119)

- The **factory default** is now **ASR = integrated GPU (GPU.0) / translation =
  integrated GPU (GPU.0) / speech output = Intel NPU**. The ASR model is
  **still R2T2 1.7B** — unchanged.
- The rule "MT and TTS may not both sit on the NPU ⇒ MT is moved to GPU.0
  automatically" is **gone**: the three modules may be placed on any device
  freely and the program will **never change the device you picked**. When the
  NPU really is shared, the speech output panel shows a single **non-blocking**
  performance hint.
- Old configurations are **migrated automatically**: a configuration whose
  devices were never changed by hand moves to the new default, while a
  **manually chosen** device is kept as is (the migration is logged).

"""


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix='_app119_sync_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def apply_repl(path, repl, label):
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8')
    hits = []
    for old, new in repl:
        n = text.count(old)
        if n != 1:
            raise SystemExit('FAIL[%s]: 锚点命中 %d 次（要求 1）：%r'
                             % (label, n, old[:60]))
        text = text.replace(old, new)
        hits.append(old[:60])
    # 插入新章节
    anchor = '\n## v2.4 改动说明\n' if label == 'zh' else '\n## What\'s new in v2.4\n'
    if text.count(anchor) != 1:
        raise SystemExit('FAIL[%s]: 章节锚点命中 %d 次' % (label,
                                                          text.count(anchor)))
    section = ZH_NEW_SECTION if label == 'zh' else EN_NEW_SECTION
    text = text.replace(anchor, '\n' + section + anchor.lstrip('\n'))
    write_atomic(path, text.encode('utf-8'))
    with open(path, 'rb') as f:
        back = f.read()
    if back.decode('utf-8') != text:
        raise SystemExit('FAIL[%s]: 写后复核不一致' % label)
    return hits


def main():
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'app': 'APP-119', 'pkg': PKG, 'py_files': [], 'readme': [],
           'errors': []}
    if not os.path.isdir(PKG_APP):
        print('FAIL: 包目录不存在 %s' % PKG_APP)
        return 2

    for name in RUNTIME_PY:
        src = os.path.join(DEV, name)
        dst = os.path.join(PKG_APP, name)
        if not os.path.isfile(src):
            rep['errors'].append('dev 缺 %s' % name)
            continue
        data = open(src, 'rb').read()
        before = (sha256_bytes(open(dst, 'rb').read())
                  if os.path.isfile(dst) else None)
        ast.parse(data.decode('utf-8'))          # 写前语法自检
        write_atomic(dst, data)
        back = open(dst, 'rb').read()
        ok = (back == data) and (sha256_bytes(back) == sha256_bytes(data))
        ast.parse(back.decode('utf-8'))          # 写后语法自检
        st = os.stat(dst)
        rep['py_files'].append({
            'name': name,
            'dev_sha256': sha256_bytes(data),
            'pkg_sha256': sha256_bytes(back),
            'pkg_sha256_before': before,
            'changed': before != sha256_bytes(back),
            'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(
                st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'identical_to_dev': ok,
        })
        print('  %s → %s  %d B  sha=%s  %s'
              % (name, dst, st.st_size, sha256_bytes(back)[:16],
                 'OK' if ok else 'FAIL'))

    for path, repl, label in ((ZH, ZH_REPL, 'zh'), (EN, EN_REPL, 'en')):
        hits = apply_repl(path, repl, label)
        st = os.stat(path)
        b = open(path, 'rb').read()
        rep['readme'].append({
            'name': os.path.basename(path),
            'repl_hits': hits,
            'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(
                st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'sha256': sha256_bytes(b),
        })
        print('  README %s  %d B  sha=%s  OK'
              % (label, st.st_size, sha256_bytes(b)[:16]))

    # 包内文件数（验收口径：文件数 / mtime / 字节数 / SHA256 都要报）
    n_files = 0
    for root, _dirs, files in os.walk(PKG):
        n_files += len(files)
    rep['pkg_file_count'] = n_files

    ok = all(f['identical_to_dev'] for f in rep['py_files'])
    rep['result'] = 'PASS' if ok and not rep['errors'] else 'FAIL'
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    print('== APP-119 同步 v2.5 == %s（包内文件数 %d）'
          % (rep['result'], n_files))
    print('证据：%s' % OUT)
    return 0 if rep['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
