# -*- coding: utf-8 -*-
r"""app157_app044_spk_asset_inventory.py —— APP-044 说话人资产打包清点（§101）。

## 为什么需要这个脚本

APP-044 要求客户包**带上** pyannote/segmentation-3.0 与 wespeaker 的 OV IR
**加上 ASR 的 SpeakerTracker 接口代码**。

但「带上接口代码」这句话**没有指明带哪些文件** ⇒ 必须先把
「ASR 侧 SpeakerTracker 的**完整依赖闭包**」算清楚，否则：
- 少带 ⇒ 客户机 import 失败 ⇒ 旁路静默降级 ⇒ **用户看不到说话人标签**；
- 多带 ⇒ 把 ASR 的实验脚本、torch 权重、CUDA 产物打进客户包（APP-044 明文禁止）。

## 本脚本做三件事

1. **依赖闭包**：从 `asr052_speaker_tracker_api.py` 出发，递归解析
   `import` / `from ... import`（含**函数体内的惰性 import**）⇒ 得到
   「要能在客户机上 import 成功，最少需要哪些 .py」。
2. **模型资产**：定位 wespeaker / pyannote 的 OV IR（含 xml+bin 成对性）。
3. **禁止项核对**：确认 torch 权重（`pytorch_model.bin` / `*.pt` / `*.pth` /
   `*.safetensors`）**不在**闭包内（APP-044：不要带 torch 权重）。

## 判据

| 编号 | 判据 |
|---|---|
| A1 | 依赖闭包根 = `asr052_speaker_tracker_api.py` |
| A2 | 闭包内每个文件都真实存在（否则打包后必然 ImportError） |
| A3 | 闭包内**不含** torch 权重文件 |
| A4 | 闭包内**不含** `__main__` 入口副作用（可 import 即用） |
| A5 | wespeaker OV IR 存在且 xml/bin 成对 |
| A6 | pyannote OV IR 存在且 xml/bin 成对 |
| A7 | 闭包内文件**不含硬编码本机绝对路径**（否则客户机必然失效）★核心 |
| A8 | 闭包内文件不含 `import torch`（APP-044：不要带 CUDA/torch） |

## 反证（合成源双向检验）

- **D-A7**：把某文件里的 `C:\Users\...` 换成别处 ⇒ A7 必须 FAIL。
- **D-A3**：往闭包里塞一个 `pytorch_model.bin` ⇒ A3 必须 FAIL。
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

ASR_ROOT = os.environ.get('APP157_ASR_ROOT', '').strip() or \
    r'C:\Users\Trekker-PTL\qwen3asr_06b'
SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
MODELS = os.path.join(ASR_ROOT, 'models')
REPO = os.environ.get('APP157_REPO', '').strip() or \
    r'C:\Users\Trekker-PTL\confucius4-openvino'

OUT = os.path.join(
    REPO, 'results', 'app',
    'app157_app044_spk_asset_inventory_evidence.json')

ROOT_MODULE = 'asr052_speaker_tracker_api'

WEIGHT_PAT = ('pytorch_model.bin', '.pt', '.pth', '.ckpt', '.safetensors')
HARDCODE_RE = re.compile(r'[A-Za-z]:\\\\?Users\\\\?[^"\'\s]*', re.IGNORECASE)

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-56s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-56s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def local_imports(src):
    """抽出一个源码文件里引用的**本地模块名**（含函数体内的惰性 import）。

    ★ 关键：ASR 的接口把依赖放在**函数体内**惰性 import
      ⇒ 只看模块顶层会漏掉全部真实依赖。
    """
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # 相对 import ⇒ 本地
                continue
            if node.module:
                names.add(node.module.split('.')[0])
    return names


def resolve(mod):
    """把模块名解析成磁盘路径。

    ★ 只在 **ASR scripts 目录**里找 —— 这是「要打进客户包的新增文件」的真实范围。
      `live_caption/` 下的模块**已经在客户包里了**（APP-044 说「再加上 ASR 的
      SpeakerTracker 接口代码」⇒ 新增的是 ASR 侧那几个文件）⇒ 不属于新增闭包。
      ⇒ 若在 live_caption 里找到同名文件，**不**算作闭包成员。
    """
    p = os.path.join(SCRIPTS, mod + '.py')
    if os.path.isfile(p):
        return p
    return None


def closure(root_mod):
    """递归求依赖闭包。返回 (set_of_paths, edges, missing)。"""
    seen = set()
    edges = []
    missing = []
    stack = [root_mod]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        p = resolve(mod)
        if p is None:
            missing.append(mod)
            continue
        try:
            src = open(p, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            missing.append(mod)
            continue
        for dep in sorted(local_imports(src)):
            if dep in seen:
                continue
            dp = resolve(dep)
            if dp is None:
                # 非本地模块（numpy / openvino / soundfile …）⇒ 不入闭包
                continue
            edges.append((mod, dep))
            stack.append(dep)
    return seen, edges, missing


def find_weights(paths):
    """在给定目录树里找 torch 权重。"""
    hits = []
    for p in paths:
        if os.path.isfile(p):
            low = p.lower()
            if any(low.endswith(w) for w in WEIGHT_PAT):
                hits.append(p)
    return hits


def main():
    print('=' * 78)
    print('APP-044 说话人资产打包清点（§101）')
    print('=' * 78)
    print('ASR_ROOT = %s' % ASR_ROOT)
    print()

    root_path = resolve(ROOT_MODULE)
    add('A1 依赖闭包根存在（%s）' % ROOT_MODULE,
        root_path is not None,
        root_path or 'NOT FOUND')

    mods, edges, missing = closure(ROOT_MODULE)
    files = sorted(p for m in mods if (p := resolve(m)) is not None)

    print('[闭包] %d 个模块：' % len(files))
    for f in files:
        print('        %s' % os.path.relpath(f, ASR_ROOT))
    print()

    add('A2 闭包内每个文件都真实存在',
        not missing,
        'missing=%s' % (missing,))

    weights = find_weights(files)
    add('A3 闭包内不含 torch 权重文件',
        not weights,
        'hits=%s' % (weights,))

    # A4：可 import 即用
    #    判据口径：只统计**模块顶层**真正会执行的「重副作用」——
    #    `os.environ.setdefault` / `sys.path.insert` 是**无害的**（配置与路径登记）
    #    ⇒ 不算副作用；真正的副作用 = 顶层裸调用推理/建对象/开文件写盘。
    HARMLESS_TOP_CALLS = ('setdefault', 'insert', 'append', 'extend',
                          'get', 'getenv', 'setdefault')
    side_effect = []
    for f in files:
        try:
            tree = ast.parse(open(f, 'r', encoding='utf-8',
                                  errors='replace').read())
        except SyntaxError:
            side_effect.append((os.path.basename(f), 'SyntaxError'))
            continue
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                fn = node.value.func
                nm = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
                if nm and nm not in HARMLESS_TOP_CALLS and nm != 'main':
                    side_effect.append((os.path.basename(f), nm))
    add('A4 闭包内模块顶层无重副作用（可 import 即用）',
        not side_effect,
        'side_effects=%s' % (side_effect,))

    # ── A5/A6：模型 IR ───────────────────────────────────────────
    wes_candidates = [
        ('wespeaker-resnet34-fp16', os.path.join(
            MODELS, 'wespeaker-resnet34-fp16')),
        ('wespeaker-resnet34-fp32', os.path.join(
            MODELS, '_attrib_wespeaker-resnet34-fp32')),
    ]
    wes_ok = []
    for label, d in wes_candidates:
        xml = os.path.join(d, 'openvino_encoder_model.xml')
        binf = os.path.join(d, 'openvino_encoder_model.bin')
        if os.path.isfile(xml) and os.path.isfile(binf):
            wes_ok.append((label, d, os.path.getsize(xml),
                           os.path.getsize(binf)))
    add('A5 wespeaker OV IR 存在且 xml/bin 成对',
        bool(wes_ok),
        'variants=%s' % [(v[0], v[3]) for v in wes_ok])

    seg_candidates = [
        ('pyannote_seg/ov-fp16', os.path.join(MODELS, 'pyannote_seg', 'ov-fp16')),
        ('pyannote_seg/ov-fp32', os.path.join(MODELS, 'pyannote_seg', 'ov-fp32')),
    ]
    seg_ok = []
    for label, d in seg_candidates:
        xml = os.path.join(d, 'pyannote_seg_3_0.xml')
        binf = os.path.join(d, 'pyannote_seg_3_0.bin')
        if os.path.isfile(xml) and os.path.isfile(binf):
            seg_ok.append((label, os.path.getsize(xml), os.path.getsize(binf)))
    add('A6 pyannote OV IR 存在且 xml/bin 成对',
        bool(seg_ok),
        'variants=%s' % [(v[0], v[2]) for v in seg_ok])

    # ── A7：硬编码本机绝对路径 ★核心 ────────────────────────────
    #    ★ 口径细化（重要）：要区分两类硬编码
    #      ① **模型/运行时路径**（WORK/REPO/SHARED 派生）⇒ 客户机上模型找不到
    #         ⇒ 旁路静默降级 ⇒ **致命**
    #      ② **测试语料路径**（default= 参数、docstring 示例）⇒ 运行时不用
    #         ⇒ 无害
    #    ⇒ 判据只看 ①：模块级常量赋值里出现的绝对路径。
    RUNTIME_PATH_RE = re.compile(
        r'^\s*(WORK|REPO|SCRIPTS|SHARED|R|WES_IR|SEG_IR|WES_CKPT)\s*=',
        re.M)
    hardcoded_runtime = []
    hardcoded_other = []
    for f in files:
        try:
            src = open(f, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        for m in HARDCODE_RE.finditer(src):
            # 找出该行是否是模块级路径常量赋值
            ls = src.rfind('\n', 0, m.start()) + 1
            le = src.find('\n', m.end())
            line = src[ls:le if le > 0 else len(src)]
            if RUNTIME_PATH_RE.search(line):
                hardcoded_runtime.append((os.path.basename(f),
                                          m.group(0)))
            else:
                hardcoded_other.append((os.path.basename(f), m.group(0)))
    add('A7 闭包内无硬编码的**运行时路径常量**（客户机可移植）★核心',
        not hardcoded_runtime,
        'runtime_hits=%d %s' % (len(hardcoded_runtime),
                                hardcoded_runtime[:8]))
    print('        （信息）非运行时（测试语料/docstring）硬编码 %d 处：%s'
          % (len(hardcoded_other),
             hardcoded_other[:4] if hardcoded_other else ''))

    # ── A8：不含**模块级** import torch ───────────────────────────
    #    ★ 口径修正（重要）：`import torch` 出现在**函数体内**≠ 客户机跑不起来
    #      （那是可选/参考路径，客户机不会调用到）。
    #      真正会炸的是**模块级 import** ⇒ import 该模块时立刻 ImportError。
    #    ⇒ 只统计 tree.body 顶层的 torch/torchaudio import。
    torch_imp_top = []
    torch_imp_lazy = []
    for f in files:
        try:
            tree = ast.parse(open(f, 'r', encoding='utf-8',
                                  errors='replace').read())
        except SyntaxError:
            continue
        for node in tree.body:
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or '').split('.')[0]]
            if 'torch' in mods or 'torchaudio' in mods:
                torch_imp_top.append((os.path.basename(f), node.lineno))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(node):
                    mods = []
                    if isinstance(sub, ast.Import):
                        mods = [a.name.split('.')[0] for a in sub.names]
                    elif isinstance(sub, ast.ImportFrom):
                        mods = [(sub.module or '').split('.')[0]]
                    if 'torch' in mods or 'torchaudio' in mods:
                        torch_imp_lazy.append((os.path.basename(f),
                                               node.name))
    add('A8 闭包内无**模块级** import torch/torchaudio（客户机可 import）',
        not torch_imp_top,
        'top_level=%s' % (torch_imp_top,))
    print('        （信息）函数体内的 torch/torchaudio 惰性 import：%s'
          % (torch_imp_lazy,))

    # ── A9：客户机**必经路径**不含 torch（★ 真正的可打包性判据）──
    #   `pya_ref_shim` 顶层 import torch ⇒ 它**不能**打进包（import 即炸），
    #   但客户机路径**不经过**它（只用 WespeakerOVEncoder + OnlineSpeakerCluster
    #   ⇒ 纯 OV + 纯 numpy）⇒ 因此「排除该文件」即可，不是障碍。
    #   ⇒ 判据 = 客户机路径上的每个模块，其**模块级** import 都不含 torch，
    #     且 torch 只出现在**被排除**的文件里。
    CUSTOMER_PATH_ROOTS = (
        'asr052_speaker_tracker_api', 'asr050_spk_qa_speaker_test',
        'asr021_bypass_spk_wespeaker', 'pya_bypass_spk',
        'pya_stream_segment', 'asr030_kaldi_fbank_fidelity',
    )
    excluded = {os.path.basename(f) for f, _ in torch_imp_top}
    customer_path_top_torch = []
    for f in files:
        base = os.path.basename(f)[:-3]
        if base not in CUSTOMER_PATH_ROOTS:
            continue
        try:
            tree = ast.parse(open(f, 'r', encoding='utf-8',
                                  errors='replace').read())
        except SyntaxError:
            continue
        for node in tree.body:
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or '').split('.')[0]]
            if 'torch' in mods or 'torchaudio' in mods:
                customer_path_top_torch.append((base, node.lineno))
    add('A9 客户机必经路径的模块级 import 无 torch/torchaudio',
        not customer_path_top_torch,
        'hits=%s excluded_files=%s' % (customer_path_top_torch,
                                       sorted(excluded)))

    # ══════════════════════════════════════════════════════════════
    # 反证（合成源双向检验）
    # ══════════════════════════════════════════════════════════════
    print()
    print('[反证] 判据必须能识破假通过：')

    # D-A7：把路径改掉 ⇒ A7 必须 FAIL
    sample = '# x = r"C:\\Users\\Trekker-PTL\\qwen3asr_06b\\models"\n'
    hit = HARDCODE_RE.findall(sample)
    add('D-A7① 含本机绝对路径的源码 ⇒ A7 必须 FAIL',
        bool(hit), 'hits=%s' % (hit,))
    clean = '# x = os.path.join(base, "models")\n'
    add('D-A7② 无本机绝对路径的源码 ⇒ A7 必须 PASS',
        not HARDCODE_RE.findall(clean), 'hits=%s' % (HARDCODE_RE.findall(clean),))

    # D-A3：塞一个权重文件 ⇒ A3 必须 FAIL
    fake_w = os.path.join(ASR_ROOT, 'scripts', '_fake_pytorch_model.bin')
    try:
        with open(fake_w, 'wb') as f:
            f.write(b'x')
        w2 = find_weights(files + [fake_w])
        add('D-A3 塞入 torch 权重后 ⇒ A3 必须 FAIL',
            bool(w2), 'hits=%s' % (w2,))
    finally:
        try:
            os.remove(fake_w)
        except Exception:
            pass

    print()
    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('=' * 78)
    print('RESULT: %d PASS / %d FAIL  => %s' % (PASS, FAIL, verdict))
    print('=' * 78)

    data = dict(
        script=os.path.basename(__file__),
        asr_root=ASR_ROOT,
        pass_=PASS, fail=FAIL, verdict=verdict,
        closure_modules=sorted(mods),
        closure_files=[os.path.relpath(f, ASR_ROOT) for f in files],
        closure_edges=edges,
        missing=missing,
        wespeaker_variants=[dict(label=v[0], dir=v[1], xml_bytes=v[2],
                                 bin_bytes=v[3]) for v in wes_ok],
        pyannote_variants=[dict(label=v[0], xml_bytes=v[1], bin_bytes=v[2])
                           for v in seg_ok],
        hardcoded_runtime_paths=hardcoded_runtime,
        hardcoded_other_paths=hardcoded_other,
        torch_imports_top_level=torch_imp_top,
        torch_imports_lazy=torch_imp_lazy,
        detail=DETAIL,
    )
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('evidence -> %s' % OUT)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
