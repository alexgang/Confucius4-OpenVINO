#!/usr/bin/env python
r"""app014b_v15_preship_check.py —— v1.5 打包前自检（APP-014② 第③④步）

验四组：
  1. **包内代码 == 仓库代码**（逐文件 SHA256）—— 防止「改了仓库忘了同步进包」；
  2. **v1.5 标识就位**（标题版本号 / MANIFEST version / README v1.5 段）；
  3. **本轮四条改动的 README 落地**（假设备清零 / CUDA 警示 / 接缝去重 /
     TTS 转正式默认开启）；
  4. **内部素材闸门 + GUI 冒烟复跑**（复用现有脚本，只做只读/无推理的部分）。

🔴 **口径**：
   - **不加载模型、不推理、不占 GPU**；
   - GUI 冒烟用**客户包的 python**（managed python 无 tkinter），
     但只起 Tk 控件、不连设备；
   - 仓库侧只**读**不改。

用法
----
    "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\python.exe" \
        app014b_v15_preship_check.py --pkg <v1.5目录>
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def norm_newline(b):
    """归一化行尾（仓库可能是 CRLF，包内是 LF）。"""
    return b.replace(b'\r\n', b'\n')


def head_bytes(rel):
    """取 `git show HEAD:<rel>` 的字节；取不到返回 None。

    🔴🔴 **为什么基准是 HEAD 而不是工作区**（2026-10-25 §37 实测）：
       工作区可能躺着**别的并行会话的在制品**（本机就是 APP-015 方案 C，
       133 行未提交改动）⇒ 拿工作区当基准会把「未定稿的在制品」
       当成「必须进包的代码」，从而**逼着在制品进包**
       ⇒ 与 §34.7「v1.5 不带方案 C」直接冲突。
       ⇒ 正确口径：**包内代码 == 已提交的源码（HEAD）**。
    """
    try:
        out = subprocess.run(
            ['git', '-C', REPO, 'show', 'HEAD:%s' % rel],
            capture_output=True, timeout=60)
        if out.returncode != 0:
            return None
        return out.stdout
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    args = ap.parse_args()
    PKG = args.pkg

    print('=' * 70)
    print('v1.5 打包前自检 ——', PKG)
    print('=' * 70)

    # ── ① 包内代码 == 仓库代码（基准 = **HEAD**，不是工作区）──────────
    print()
    print('--- (1) 包内代码 vs 仓库 **HEAD**（SHA256，归一化行尾）---')
    for fn in ('live_caption_app.py', 'device_config.py', 'tts_service.py',
               'tts_worker.py', 'tts_engine.py', 'audio_source.py',
               'backends.py', 'seg_stream.py'):
        rel = 'live_caption/%s' % fn
        rp = os.path.join(REPO, 'live_caption', fn)
        pp = os.path.join(PKG, 'app', fn)
        if not (os.path.isfile(rp) and os.path.isfile(pp)):
            check('%s 存在（仓库+包）' % fn, False,
                  'repo=%s pkg=%s' % (os.path.isfile(rp), os.path.isfile(pp)))
            continue
        hb = head_bytes(rel)
        if hb is None:
            # 取不到 HEAD（不在 git 里）⇒ 退回工作区，但明确标注
            hb = open(rp, 'rb').read()
            print('       [warn] %s 取不到 HEAD，退回工作区文件' % fn)
        a = norm_newline(hb)
        b = norm_newline(open(pp, 'rb').read())
        # 工作区与 HEAD 不同 ⇒ 有在制品；只做**提示**，不进判定
        wt = norm_newline(open(rp, 'rb').read())
        note = ''
        if wt != a:
            note = '  [注] 工作区有未提交改动（在制品，**不进包**）'
        check('%s 与 HEAD 一致' % fn, a == b,
              'head=%s pkg=%s%s' % (hashlib.sha256(a).hexdigest()[:12],
                                    hashlib.sha256(b).hexdigest()[:12], note))

    # ── ② v1.5 标识就位 ───────────────────────────────────────
    print()
    print('--- (2) v1.5 标识 ---')
    import json
    man_path = os.path.join(PKG, 'app', 'MANIFEST.json')
    man = json.load(open(man_path, encoding='utf-8'))
    check("MANIFEST version == '1.5'", man.get('version') == '1.5',
          'version=%r' % man.get('version'))
    notes = man.get('notes') or ''
    check('MANIFEST notes 含 v1.5 修订（设备全名）',
          '（6）**设备下拉按实际硬件显示全名**' in notes)
    check('MANIFEST notes 含 v1.5 修订（CUDA 诚实警示）',
          'ASR 语音分区新增 CUDA 选项 + 去重' in notes)
    check('MANIFEST notes 含 v1.5 修订（TTS 只列实测可用组合）',
          '（10）**语音输出只列' in notes)
    check('MANIFEST notes 含 v1.5 修订（接缝去重）',
          '（8）**修掉段接缝处的重复词**' in notes)
    check('MANIFEST notes 含 v1.5 修订（TTS 转正式）',
          '（9）**TTS（译文语音输出）转为正式功能，默认开启**' in notes)
    check('MANIFEST notes 仍含 v1.4 TTS/INT8 修订',
          '（4）**TTS（Qwen3-TTS / BabelVox）随包分发**' in notes)

    # ── ③ README v1.5 落地 ─────────────────────────────────────
    print()
    print('--- (3) README v1.5 落地 ---')
    zh = open(os.path.join(PKG, 'README_zh.md'), encoding='utf-8').read()
    en = open(os.path.join(PKG, 'README_en.md'), encoding='utf-8').read()

    check('README_zh 标题是 v1.5',
          zh.startswith('# Confucius4-R2T2 实时字幕（技术评估版 v1.5）'))
    check('README_en 标题是 v1.5',
          en.startswith('# Confucius4-R2T2 Live Captions (technical evaluation build v1.5)'))
    check('README_zh 有「## v1.5 改动说明」', '## v1.5 改动说明' in zh)
    check('README_en 有 "## What\'s new in v1.5"', "## What's new in v1.5" in en)
    check('README_zh 保留 v1.4 改动说明（历史可追溯）',
          '## v1.4 改动说明' in zh)
    check('README_en 保留 v1.4 改动说明（历史可追溯）',
          "## What's new in v1.4" in en)

    # 假设备：表格里必须清零（正文提及是允许的 —— 那是在解释它被修掉了）
    for tag, txt in (('zh', zh), ('en', en)):
        rows = [ln for ln in txt.split('\n')
                if ln.startswith('|') and 'Intel GPU 2' in ln]
        check('README_%s 设备表格里无「Intel GPU 2」' % tag, not rows,
              str(rows[:1]))

    check('README_zh 有 CUDA 诚实警示（无 CUDA plugin）',
          '没有安装 CUDA plugin' in zh)
    # ⚠️ 英文警示块是 **markdown 块引用**（每行前缀 `> `），
    #    句子还被行尾折断 ⇒ 必须**去掉 `> ` 前缀 + 归一化空白**后再匹配，
    #    否则误报（§33 已踩过「断言口径不对 ⇒ 假 FAIL」）。
    en_flat = re.sub(r'\s+', ' ', re.sub(r'(?m)^\s*>\s?', '', en))
    check('README_en 有 CUDA 诚实警示（无 CUDA plugin）',
          'does not include the CUDA plugin' in en_flat,
          'flat 匹配')
    check('README_zh 有接缝去重说明', '修掉段接缝处的重复词' in zh)
    check('README_en 有接缝去重说明', 'Repeated words at segment seams are fixed' in en)
    check('README_zh 已知限制写明接缝去重的真实收益量级',
          '段接缝处的重复词已在 v1.5 修掉' in zh)
    check('README_en 已知限制写明接缝去重的真实收益量级',
          'Repeated words at segment seams were fixed in v1.5' in en)
    check('README_zh TTS 写「正式功能，默认开启」',
          '译文语音输出（**正式功能，默认开启**）' in zh)
    check('README_en TTS 写 full feature, on by default',
          'a full feature, on by default' in en)
    check('README_zh 有耳机提示', '请佩戴耳机，避免回授' in zh)
    check('README_en 有耳机提示', 'wear headphones to avoid feedback' in en)
    check('README_zh 无重复的段切分行',
          zh.count('段切分按能量静音判断') == 1,
          'count=%d' % zh.count('段切分按能量静音判断'))
    check('README_en 无重复的段切分行',
          en.count('long speech without pauses is cut at 20 s') == 1,
          'count=%d' % en.count('long speech without pauses is cut at 20 s'))

    # ── ④ 关键实现就位（源码断言）───────────────────────────────
    print()
    print('--- (4) 本轮改动在包内代码里就位 ---')
    src = open(os.path.join(PKG, 'app', 'live_caption_app.py'),
               encoding='utf-8').read()
    check("包内 CLI --tts default=None",
          "'--tts', choices=['off', 'on'], default=None" in src)
    check('包内 GUI 初值按 None=>True',
          "True if _tts_arg is None else _tts_arg == 'on'" in src)
    check('包内接缝去重含 n=1 判据函数',
          '_stitch_is_cut_through_word' in src)
    check('包内接缝开关用下限控制（关闭时不做 n=1）',
          'min_n = 1 if STITCH_SEAM_ENABLED else 2' in src)
    check('包内 prev_text 缺失时保守退化',
          'if not prev_text:' in src)
    # 旧死代码必须已清零（AST 口径，注释不计入）
    import ast
    dead = set()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                '_stitch_char_overlap', '_is_stitch_stopword'):
            dead.add(node.name)
        if isinstance(node, ast.Name) and node.id in (
                '_STITCH_STOPWORDS', '_STITCH_STOPWORD_SET',
                'STITCH_CHAR_MIN', 'STITCH_CHAR_MAX'):
            dead.add(node.id)
    check('旧死代码已清零（AST 口径）', not dead, str(sorted(dead)))

    dsrc = open(os.path.join(PKG, 'app', 'device_config.py'),
                encoding='utf-8').read()
    # ⚠️ 「Intel GPU 2」在 device_config.py 的**注释与 docstring**里是**合法的**
    #    （那是在说明「绝不编造 Intel GPU 2 这种不存在的设备」）⇒
    #    判定必须用 **AST 口径**：真正的**代码字面量**里不得出现该串。
    #    ⚠️ docstring 本身是 ast.Constant ⇒ 需额外排除（判断它是不是
    #    某个函数/模块的第一个语句）。
    docstring_nodes = set()
    # ⚠️ **只 parse 一次**：两次 `ast.parse` 会生成**不同的树对象**，
    #    `id()` 对不上 ⇒ docstring 排除失效（§33 已踩过「口径不对 ⇒ 假 FAIL」）。
    dtree = ast.parse(dsrc)
    for node in ast.walk(dtree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    fake_in_code = []
    for node in ast.walk(dtree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if 'Intel GPU 2' in node.value and id(node) not in docstring_nodes:
                fake_in_code.append((node.lineno, node.value[:60]))
    check('包内无假设备标签「Intel GPU 2」（AST 口径，注释/docstring 不算）',
          not fake_in_code, str(fake_in_code))
    check('包内 device_config 无 GPU.1→Intel 的硬编码标签',
          "'GPU.1': 'Intel GPU 2'" not in dsrc)
    # 设备标签表里 GPU.1 必须**不映射**到 Intel 名
    check('包内 device_config 标签表无「Intel GPU 2」键值',
          'Intel GPU 2' not in (re.search(
              r'_DEVICE_LABELS\s*=\s*\{(.*?)\}', dsrc, re.S).group(1)
              if re.search(r'_DEVICE_LABELS\s*=\s*\{(.*?)\}', dsrc, re.S)
              else ''))
    check('包内有 CUDA 设备识别函数',
          'def is_cuda_device(' in dsrc)
    check('包内有 CUDA plugin 探测函数',
          'def has_cuda_plugin(' in dsrc)

    # ── ⑤ 内部素材闸门（独立脚本，复用单一数据源）───────────────
    print()
    print('--- (5) 内部素材闸门 ---')
    gate = os.path.join(REPO, 'check_internal_material.py')
    if os.path.isfile(gate):
        r = subprocess.run([sys.executable, gate, '--pkg', PKG],
                           capture_output=True, timeout=1800)
        out = r.stdout.decode('utf-8', errors='replace')
        tail = [ln for ln in out.split('\n') if '命中' in ln or '结论' in ln]
        for ln in tail:
            print('   ', ln.strip())
        check('内部素材闸门 PASS', r.returncode == 0)
    else:
        check('内部素材闸门脚本存在', False, gate)

    # ── ⑥ GUI / CLI 冒烟复跑 ────────────────────────────────────
    print()
    print('--- (6) GUI / CLI 冒烟（APP-014① 脚本，不加载模型）---')
    smoke = os.path.join(REPO, 'results', 'app', 'app014_gui_smoke.py')
    if os.path.isfile(smoke):
        r = subprocess.run([sys.executable, smoke], capture_output=True,
                           timeout=600)
        out = r.stdout.decode('utf-8', errors='replace')
        for ln in out.split('\n'):
            if '冒烟：PASS' in ln:
                print('   ', ln.strip())
        check('GUI/CLI 冒烟全 PASS', r.returncode == 0)
    else:
        check('冒烟脚本存在', False, smoke)

    print()
    print('=' * 70)
    print('v1.5 打包前自检：PASS %d 项 / FAIL %d 项' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  x %s' % f)
    print('=' * 70)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
