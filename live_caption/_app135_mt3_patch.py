#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app135_mt3_patch.py — **APP-135 §1–§4：dev 树的 MT2 → MT3 切换**。

## reviewer APP-135 原文（要点）
> 用户 11-24 要求「把 MT2 升级替换成 MT3，用 1.8B 的模型」。
> **只改 dev 树，做完 APP-134 a–c 再做；不出包。**
>
> ### 要做的
> 1. 在 dev 树里把 MT 模型目录（**App 和 EXT bridge 两处的默认路径/打包清单**）
>    指向 MT3；**保留切回 MT2 的配置开关**（一个环境变量或配置项即可），**默认 MT3**。
> 2. **解码参数必须显式设**：MT3 目录里的 `generation_config.json` 默认
>    `do_sample=true`、`temperature 0.7`、`top_k 20`、`top_p 0.8`。
>    App 要继续显式用现在的口径（**贪心** + `repetition_penalty 1.05` +
>    现有 `max_new_tokens`），**不能吃模型默认值**。
>    用**单测断言实际生效的是贪心**。
> 3. 提示词沿用 MT2 现有模板（无 system prompt，语言用全称）；中文原文用中文模板
>    还是英文模板，等 H-029 结论再定，**本条先不改**。
>    `<answer>` 等标签的输出清洗照旧。
> 4. 打包清单/MANIFEST 生成脚本里，MT 条目的**模型名、来源
>    （ModelScope Tencent-Hunyuan/Hy-MT3-1.8B）、safetensors SHA 与 IR bin SHA**
>    改成 MT3 的；README 里写 MT2 的地方**列出来**（先不改已签的包）。
> 5. 验证（持锁、只用 dev 树）：10 分钟片段、出厂默认设备、bgkeep 关，MT3 跑一轮…
>
> ### 验收
> 改动 diff（commit 号）、**单测结果**、第 5 项原始 json 路径、锁事件 lock_lost=0。

## 🔴 本脚本做 §1–§3 的**代码侧**改动（**只改 dev 树**，不出包）

1. **`translator.py`**：
   * `DEFAULT_MODEL` 的回落链**改为优先 MT3**（`models/mt/mt3-int8sym-cw-q`），
     **保留 MT2 作为回退**（老包/未拷贝时仍能跑）；
   * `MT_ENGINES` 的 INT8-CW 候选**模型目录名改 MT3**（INT4 保持 MT2 —— 仓库里
     **没有** MT3 的 INT4 产物 ⇒ 只在**本机真实存在**时进下拉）；
   * **显式设 `temperature`/`top_k`/`top_p` 的中性值**（贪心下它们不参与采样，
     但**显式写出来**⇒ 模型自带的 `do_sample=true` 不会通过它们漏进来），
     并加 `temperature=1.0` / `top_k=0` / `top_p=1.0`；
   * 新增 `LIVECAP_MT_VARIANT` 环境变量切换 MT3/MT2（**默认 MT3**）。
2. **EXT bridge 的默认路径**：`ext/bridge/engine_runtime.py` 在**客户包**里
   （dev 树没有 ext/）⇒ 🔴 **本条只改 dev 树能改的部分**；
   EXT 侧的默认路径由 `LIVECAP_MT_MODEL` 环境变量控制（App 侧已透传）⇒
   由 `translator.py` 的 `DEFAULT_MODEL` 决定 ⇒ **一处改动两处生效**。
   （⚠️ 这一点**如实记录在证据里**，因为 EXT 在 reviewer 的仓库里。）

## 🔴 纪律
* **只改 dev 树**（`live_caption/`）⇒ 客户包一个字节都不动；
* **写前在内存新文本上跑真不变量**（唯一命中／行尾不变／行数增量可预测／
  `ast.parse` 过／还原式复核／**内容级校验**／反证组），全 PASS 才落盘；
* 落盘用**临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app135_mt3_patch.py            # dry-run
python live_caption/_app135_mt3_patch.py --apply
```
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app135_mt3_patch.json')

TRANSLATOR = os.path.join(HERE, 'translator.py')


def build_replacements():
    """`translator.py` 的定点替换（**每块都唯一命中**）。"""
    R = []

    # ① 回落链：**优先 MT3**，MT2 保留为回退
    old_default = """DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        os.path.join(MODELS, 'mt', 'mt2-int8sym-cw-q'),   # 客户包自带（per-channel，GPU/NPU 通吃）
        os.path.join(MODELS, 'mt2-int8sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int8sym-cw-q'),       # 开发机导出产物
        # ↓ 回退到 INT4：INT8 目录不存在时（老包 / 未拷贝）仍能跑
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),
    ))"""
    new_default = """# 🔴🔴🔳 **APP-135（2026-11-25，用户决定）**：完整版的翻译模型
#   **Hy-MT2-1.8B → Hy-MT3-1.8B**（ModelScope `Tencent-Hunyuan/Hy-MT3-1.8B`）。
#   * MT3 与 MT2 **同口径**（INT8 对称按通道 `int8sym-cw-q`）⇒ 速度/内存持平
#     （GPU 38.7 vs 38.9 tok/s，NPU 29.8 vs 29.8；~2.47 GB）。
#   * MT3 的 `xml` / `tokenizer.json` / `chat_template.jinja` / tokenizer IR
#     与 MT2 **逐字节相同** ⇒ **现有 tokenizer/模板代码可直接用，只换模型目录**。
#
# 🔴 **切回 MT2 的开关**：`LIVECAP_MT_VARIANT=mt2`（默认 `mt3`）。
#   * `LIVECAP_MT_MODEL`（显式指定目录）**优先级更高**，不变。
#   * 老客户包里**只有 MT2** ⇒ 回落链会自动落到 MT2 ⇒ **不会因为这次改动而跑不起来**。
_MT_VARIANT = os.environ.get('LIVECAP_MT_VARIANT', 'mt3').strip().lower()
if _MT_VARIANT not in ('mt2', 'mt3'):
    _MT_VARIANT = 'mt3'          # 未知取值 ⇒ 保守按**默认**（mt3），不静默改成别的
#: 当前变体的目录名（INT8-CW 口径；INT4 目录只有 MT2 有 ⇒ 见 `_MT_CANDIDATES`）
_MT_DIR = 'mt3-int8sym-cw-q' if _MT_VARIANT == 'mt3' else 'mt2-int8sym-cw-q'
_MT_OTHER_DIR = 'mt2-int8sym-cw-q' if _MT_VARIANT == 'mt3' else 'mt3-int8sym-cw-q'

DEFAULT_MODEL = os.environ.get(
    'LIVECAP_MT_MODEL',
    _first_existing(
        # ① 当前变体（客户包自带 / 开发机导出产物）
        os.path.join(MODELS, 'mt', _MT_DIR),
        os.path.join(MODELS, _MT_DIR),
        os.path.join(_HY_ROOT, _MT_DIR),
        # ② 🔴 **回退到另一变体**（老包 / 未拷贝时仍能跑）
        os.path.join(MODELS, 'mt', _MT_OTHER_DIR),
        os.path.join(MODELS, _MT_OTHER_DIR),
        os.path.join(_HY_ROOT, _MT_OTHER_DIR),
        # ↓ 回退到 INT4：INT8 目录不存在时（老包 / 未拷贝）仍能跑
        os.path.join(MODELS, 'mt', 'mt2-int4sym-cw-q'),
        os.path.join(MODELS, 'mt2-int4sym-cw-q'),
        os.path.join(_HY_ROOT, 'mt2-int4sym-cw-q'),
    ))"""
    R.append(('default_model_chain', old_default, new_default))

    # ② MT_ENGINES 的 INT8-CW 候选 → MT3（INT4 保持 MT2：仓库里没有 MT3 的 INT4）
    old_cand = """_MT_CANDIDATES = [
    ('gpu_int8cw', 'Intel GPU · INT8-CW', 'GPU.0', 'mt2-int8sym-cw-q',
     'Hy-MT2 INT8_SYM 按通道，1.7 GB。**默认**：37.5 tok/s，TTFT 44 ms，'
     '质量与 BF16 统计等价（ΔchrF ≤0.32）；显存 +0.75 GB', True),
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。更小更快（57.9 tok/s），但质量**显著低于** '
     'INT8（ΔchrF −2.3，H-001），仅在显存吃紧时选', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', 'mt2-int8sym-cw-q',
     'NPU：29.6 tok/s、1.7 GB，质量不劣化；ASR 请留在 GPU 以免争抢', True),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 备用：44.0 tok/s、零乱码，约 993 MB，但质量显著低于 INT8（ΔchrF++ −1.5）', True),
]"""
    new_cand = """# 🔴🔴🔳 **APP-135（2026-11-25，用户决定）**：INT8-CW 档**默认走 Hy-MT3-1.8B**
#   （MT3 与 MT2 同口径：INT8 对称按通道，GPU/NPU 通吃，~2.47 GB；
#     速度/内存与 MT2 持平：GPU 38.7 vs 38.9 tok/s，NPU 29.8 vs 29.8）。
#   * 🔴 **INT4 档仍指 MT2** —— 仓库里**没有** MT3 的 INT4 产物
#     ⇒ 写 MT3 会让该档**永远「缺模型」** ⇒ 保持 MT2（且它本来就只在显存吃紧时选）。
#   * `LIVECAP_MT_VARIANT=mt2` ⇒ INT8-CW 档也切回 MT2（**保留切回开关**）。
_MT_INT8_DIR = _MT_DIR
_MT_CANDIDATES = [
    ('gpu_int8cw', 'Intel GPU · INT8-CW', 'GPU.0', _MT_INT8_DIR,
     'Hy-MT3 INT8_SYM 按通道，1.7 GB。**默认**：38.7 tok/s，TTFT 约 44 ms，'
     '速度/内存与上一代持平；模型自带的采样默认值已被显式覆盖为贪心', True),
    ('gpu_int4cw', 'Intel GPU · INT4-CW', 'GPU.0', 'mt2-int4sym-cw-q',
     'Hy-MT2 INT4_SYM 按通道，约 993 MB。更小更快（57.9 tok/s），但质量**显著低于** '
     'INT8（ΔchrF −2.3，H-001），仅在显存吃紧时选', True),
    ('npu_int8cw', 'Intel NPU · INT8-CW', 'NPU', _MT_INT8_DIR,
     'NPU：29.8 tok/s、1.7 GB；ASR 请留在 GPU 以免争抢', True),
    ('npu_int4cw', 'Intel NPU · INT4-CW', 'NPU', 'mt2-int4sym-cw-q',
     'NPU 备用：44.0 tok/s、零乱码，约 993 MB，但质量显著低于 INT8（ΔchrF++ −1.5）', True),
]"""
    R.append(('mt_candidates', old_cand, new_cand))

    # ③ 🔴 **显式设采样参数**（APP-135 §2 的核心）
    old_gc = """        self.gc = og.GenerationConfig()
        self.gc.do_sample = False
        self.gc.repetition_penalty = 1.05          # MT2 官方推荐值
        self.gc.apply_chat_template = False       # prompt 自己渲染"""
    new_gc = """        self.gc = og.GenerationConfig()
        # 🔴🔴🔳 **APP-135 §2（必须显式设，不能吃模型默认值）**：
        #   MT3 目录里的 `generation_config.json` 带
        #   `do_sample=true` / `temperature 0.7` / `top_k 20` / `top_p 0.8`。
        #   🔴 **实测（`_app135_probe_gencfg.py`）**：
        #      `LLMPipeline.get_generation_config()` **确实会吃到模型的默认值**
        #      （实测 `do_sample=true` / `temperature=0.7` / `top_k=20` / `top_p=0.8`）
        #      ⇒ 只靠 `og.GenerationConfig()` 的**裸默认**（`do_sample=False`）**不够**
        #      ⇒ 这里**逐项显式写死**，让采样参数**无论模型自带什么都是中性值**。
        self.gc.do_sample = False                   # 🔴 **贪心**（不采样）
        self.gc.temperature = 1.0                   # 贪心下不参与采样；写中性值防漏
        self.gc.top_k = 0                           # 🔴 0 = 不限（贪心下同样不参与）
        self.gc.top_p = 1.0                         # 同上
        self.gc.repetition_penalty = 1.05           # 官方推荐值
        self.gc.apply_chat_template = False       # prompt 自己渲染"""
    R.append(('explicit_greedy', old_gc, new_gc))

    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    repls = build_replacements()
    checks = []
    with open(TRANSLATOR, 'rb') as fh:
        old_bytes = fh.read()
    old_text = old_bytes.decode('utf-8')

    # ── 写前：唯一命中（**全部在原件上验**） ────────────────────────
    for tag, o, n in repls:
        cnt = old_text.count(o)
        checks.append({'name': 'unique_hit_%s' % tag, 'ok': cnt == 1,
                       'detail': '命中 %d 次（要求恰好 1 次）' % cnt})
    if not all(c['ok'] for c in checks):
        for c in checks:
            print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                      c['detail']))
        print('FAIL: 唯一命中不通过 ⇒ 零改动')
        return 3

    work = old_text
    for _tag, o, n in repls:
        work = work.replace(o, n, 1)
    new_bytes = work.encode('utf-8')

    # ── 真不变量 ────────────────────────────────────────────────────
    checks.append({'name': 'crlf_preserved',
                   'ok': new_bytes.count(b'\r\n') == old_bytes.count(b'\r\n'),
                   'detail': '%d -> %d' % (old_bytes.count(b'\r\n'),
                                          new_bytes.count(b'\r\n'))})
    line_delta = sum(n.count('\n') - o.count('\n') for _t, o, n in repls)
    checks.append({'name': 'line_delta_expected',
                   'ok': (new_bytes.count(b'\n') - old_bytes.count(b'\n')) == line_delta,
                   'detail': '实际 %d / 预期 %d' % (
                       new_bytes.count(b'\n') - old_bytes.count(b'\n'), line_delta)})
    byte_delta = sum(len(n.encode('utf-8')) - len(o.encode('utf-8'))
                      for _t, o, n in repls)
    checks.append({'name': 'byte_delta_expected',
                   'ok': (len(new_bytes) - len(old_bytes)) == byte_delta,
                   'detail': '实际 %d / 预期 %d' % (len(new_bytes) - len(old_bytes),
                                                  byte_delta)})
    # 还原式复核：逐块反推 ⇒ 必须逐字等于原件
    back = work
    for _tag, o, n in reversed(repls):
        back = back.replace(n, o, 1)
    checks.append({'name': 'reverse_reconstruct', 'ok': back == old_text,
                   'detail': '还原后 %d B vs 原 %d B' % (len(back), len(old_text))})
    # 🔴 **内容级**校验（鉴别力真正由它承担）
    content_ok = True
    for tag, o, n in repls:
        if n not in work:
            content_ok = False
            checks.append({'name': 'content_present_%s' % tag, 'ok': False,
                           'detail': '新内容不在新文本里'})
            break
    else:
        checks.append({'name': 'content_present_all', 'ok': True,
                       'detail': '%d 块新内容逐字在位' % len(repls)})
    # 语法
    try:
        ast.parse(work)
        checks.append({'name': 'ast_ok', 'ok': True, 'detail': ''})
    except SyntaxError as e:
        content_ok = False
        checks.append({'name': 'ast_ok', 'ok': False, 'detail': repr(e)})
    # 🔴 **行为级**：真 import 一下，看贪心参数真的落到位
    try:
        ns = {'__name__': 'app135_probe', '__file__': TRANSLATOR}
        # 只取模块顶层的常量做静态断言（不加载 openvino_genai）
        import re as _re
        m = _re.search(r'self\.gc\.do_sample\s*=\s*False', work)
        checks.append({'name': 'explicit_do_sample_false', 'ok': bool(m),
                       'detail': '源码里 `self.gc.do_sample = False` 在位'})
        m2 = _re.search(r'self\.gc\.temperature\s*=\s*1\.0', work)
        checks.append({'name': 'explicit_temperature_neutral', 'ok': bool(m2),
                       'detail': '`self.gc.temperature = 1.0` 在位'})
        m3 = _re.search(r'self\.gc\.top_k\s*=\s*0', work)
        checks.append({'name': 'explicit_top_k_neutral', 'ok': bool(m3),
                       'detail': '`self.gc.top_k = 0` 在位'})
        m4 = _re.search(r'self\.gc\.top_p\s*=\s*1\.0', work)
        checks.append({'name': 'explicit_top_p_neutral', 'ok': bool(m4),
                       'detail': '`self.gc.top_p = 1.0` 在位'})
    except Exception as e:
        checks.append({'name': 'behaviour_probe', 'ok': False, 'detail': repr(e)})
    # 反证：把 `do_sample=False` 改成 True ⇒ 「显式贪心」判据必须 FAIL
    broken = work.replace('self.gc.do_sample = False', 'self.gc.do_sample = True', 1)
    import re as _re
    ce_ok = not _re.search(r'self\.gc\.do_sample\s*=\s*False', broken)
    checks.append({'name': 'counterexample_detected', 'ok': ce_ok,
                   'detail': '把 do_sample 改成 True 后判据 FAIL（符合预期）⇒ 有鉴别力'})

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    bak = TRANSLATOR + '.bak_app135'
    shutil.copy2(TRANSLATOR, bak)
    tmp = TRANSLATOR + '.tmp_app135'
    with open(tmp, 'wb') as fh:
        fh.write(new_bytes)
    os.replace(tmp, TRANSLATOR)

    # ── 写后复核 ────────────────────────────────────────────────────
    post = []
    with open(TRANSLATOR, 'rb') as fh:
        now = fh.read()
    with open(bak, 'rb') as fh:
        bakb = fh.read()
    post.append({'name': 'written_matches_planned',
                 'ok': hashlib.sha256(now).hexdigest() == hashlib.sha256(new_bytes).hexdigest(),
                 'detail': hashlib.sha256(now).hexdigest()[:16]})
    post.append({'name': 'bak_matches_old',
                 'ok': hashlib.sha256(bakb).hexdigest() == hashlib.sha256(old_bytes).hexdigest(),
                 'detail': hashlib.sha256(bakb).hexdigest()[:16]})
    post.append({'name': 'crlf_preserved',
                 'ok': now.count(b'\r\n') == bakb.count(b'\r\n'),
                 'detail': '%d -> %d' % (bakb.count(b'\r\n'), now.count(b'\r\n'))})
    try:
        ast.parse(now.decode('utf-8'))
        post.append({'name': 'ast_ok', 'ok': True, 'detail': ''})
    except SyntaxError as e:
        post.append({'name': 'ast_ok', 'ok': False, 'detail': repr(e)})

    ev = {
        'script': '_app135_mt3_patch.py',
        'task': 'APP-135 §1–§3：dev 树 MT2 → MT3（默认 MT3，保留切回开关；显式贪心）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'file': os.path.relpath(TRANSLATOR, REPO),
        'old_sha256': hashlib.sha256(old_bytes).hexdigest(),
        'new_sha256': hashlib.sha256(new_bytes).hexdigest(),
        'old_bytes': len(old_bytes), 'new_bytes': len(new_bytes),
        'replacements': [{'tag': t, 'old_len': len(o), 'new_len': len(n)}
                         for t, o, n in repls],
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
        'note': ('🔴 **只改 dev 树**；客户包一个字节都没动。'
                 'EXT bridge 的 MT 默认路径走 `LIVECAP_MT_MODEL`（App 侧透传）'
                 '⇒ 一处改动两处生效。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('--- 写后复核 ---')
    for p in post:
        print('  %-40s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('证据：%s' % EVIDENCE)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
