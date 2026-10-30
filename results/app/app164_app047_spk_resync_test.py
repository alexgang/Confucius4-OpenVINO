#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app164_app047_spk_resync_test.py —— APP-047 验收（说话人资产重同步）。

## 本轮验收什么（APP-047 / ASR-033 / ASR-031 §11）

APP-047 明文：
1. 「ASR-033 正在收尾…你按新清单**重新同步 asr_spk**，**不要再做字面量替换**」；
2. 精度定案 **FP16**（`n_diff_segments=0`）；
3. 交付集合**收敛为 3 个文件**（ASR 通知 §10.4 / §11.4）；
4. App 侧要处理新的降级原因 **`embed_shape_out_of_range`**
   （ASR 通知 §11.4 第 6 条）。

## 判据设计（必须有鉴别力 ⇒ 有反证组）

🔴 **「判据 PASS」≠「判据正确」**（记忆 §十一）⇒ 本脚本带 **BUG 组**：
把**被测对象**改成缺陷形态（§十一铁律：反证要改**被测的那个对象**）
⇒ 判据必须**识破**它。

**反证手法**（不碰工作区、不碰客户包）：
- `shadow/` 影子目录：把仓库的 3 个文件复制进去，再按缺陷形态改写；
- 用 `ast`+`exec` 在**独立命名空间**里抽源码执行（§十一：不能 `import` 被测模块）。

## 零推理 / 零 GPU / 不调 MiniMax

本脚本**不加载任何模型**、不跑推理、**不调用 MiniMax**
⇒ 不污染别人的计时作业。
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12'
ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print('  %-6s %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  [%s]' % detail) if detail else ''))
    return bool(ok)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def norm_lf(b):
    return b.replace(b'\r\n', b'\n')


# ═══════════════════════════════════════════════════════════
# ① 包内 `app/asr_spk/` 恰好 3 个文件 + 内容与 ASR 源一致
# ═══════════════════════════════════════════════════════════
EXPECT3 = ('asr052_speaker_tracker_api.py', 'asr052_spk_runtime.py',
           'asr_thread_defaults.py')
OLD_FILES = ('asr021_bypass_spk_wespeaker.py', 'asr030_kaldi_fbank_fidelity.py',
             'asr050_spk_qa_speaker_test.py', 'asr_json_write.py',
             'asr_lock_common.py', 'asr_slice_common.py',
             'pya_app_path_seg.py', 'pya_bypass_spk.py',
             'pya_stream_segment.py', 'pya_ref_shim.py')

# 🔴 内部素材关键字（ASR-033 已在源头清干净 ⇒ 必须 0 命中）
KEYWORDS = ('260902', 'SPE_0000', 'spe_qa_spk', 'qwen3asr_06b',
            r'C:\Users\Trekker-PTL')


def check_pkg_files():
    print('\n[A] 包内 app/asr_spk/ 交付集合（APP-047：恰好 3 个文件）')
    d = os.path.join(PKG, 'app', 'asr_spk')
    if not os.path.isdir(d):
        return rec('A0 包内 asr_spk/ 存在', False, d)
    rec('A0 包内 asr_spk/ 存在', True, d)
    pys = sorted(f for f in os.listdir(d) if f.endswith('.py'))
    rec('A1 恰好 3 个 .py', pys == sorted(EXPECT3),
        '实得 %s' % ','.join(pys))
    left = [f for f in OLD_FILES if os.path.isfile(os.path.join(d, f))]
    rec('A2 旧的 10 个文件已移除', not left,
        '残留 %s' % ','.join(left) if left else '0 残留')
    rec('A3 无 __pycache__ 残留',
        not os.path.isdir(os.path.join(d, '__pycache__')), '')
    # 内容与 ASR 源一致（归一化行尾）
    for fn in EXPECT3:
        src = os.path.join(ASR_SCRIPTS, fn)
        dst = os.path.join(d, fn)
        if not (os.path.isfile(src) and os.path.isfile(dst)):
            rec('A4.%s 源/目标都存在' % fn, False, '')
            continue
        same = norm_lf(open(src, 'rb').read()) == norm_lf(open(dst, 'rb').read())
        rec('A4.%s 与 ASR 源逐字节一致（归一化行尾）' % fn, same,
            sha256_file(dst)[:16])
    return True


def check_pkg_keywords():
    print('\n[B] 包内 asr_spk/ 内部素材关键字（APP-047：不再做字面量替换）')
    d = os.path.join(PKG, 'app', 'asr_spk')
    if not os.path.isdir(d):
        return rec('B0 目录存在', False, d)
    hits = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.py'):
            continue
        p = os.path.join(d, fn)
        try:
            txt = open(p, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        for kw in KEYWORDS:
            if kw in txt:
                hits.append('%s:%s' % (fn, kw))
    rec('B1 3 个交付文件内部关键字 0 命中', not hits,
        '命中 %s' % ','.join(hits) if hits else '0 命中')
    return True


def check_import_chain():
    print('\n[C] 3 个交付文件的运行时 import 链自洽（ASR-033 §10.3）')
    d = os.path.join(PKG, 'app', 'asr_spk')
    local = set(f[:-3] for f in EXPECT3)   # 模块名（去 .py）
    bad = []
    for fn in EXPECT3:
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            bad.append('%s 缺失' % fn)
            continue
        src = open(p, 'rb').read()
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            bad.append('%s 语法错误：%s' % (fn, e))
            continue
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mods.add(a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    mods.add(node.module.split('.')[0])
        # 本地模块名（asr*/pya* 前缀）必须都在 3 文件集合内
        for m in mods:
            if m not in local and (m.startswith('asr') or m.startswith('pya')):
                bad.append('%s → %s（旧模块）' % (fn, m))
    rec('C1 无旧模块引用', not bad, '；'.join(bad) if bad else '0 命中')
    # 关键：asr052 必须依赖 asr_thread_defaults（限线程，ASR-031 §1）
    p = os.path.join(d, 'asr052_speaker_tracker_api.py')
    has_td = False
    if os.path.isfile(p):
        t = ast.parse(open(p, 'rb').read())
        for node in ast.walk(t):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == 'asr_thread_defaults':
                        has_td = True
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'asr_thread_defaults':
                    has_td = True
    rec('C2 asr052 依赖 asr_thread_defaults（限线程不丢）', has_td, '')
    # 限线程必须在 numpy import 之前
    p2 = os.path.join(d, 'asr052_spk_runtime.py')
    order_ok = None
    if os.path.isfile(p2):
        txt = open(p2, 'r', encoding='utf-8', errors='replace').read()
        i_np = txt.find('import numpy')
        i_td = txt.find('asr_thread_defaults')
        order_ok = (i_td != -1 and i_np != -1 and i_td < i_np)
        rec('C3 asr052_spk_runtime 先限线程再 import numpy', order_ok,
            'td@%d numpy@%d' % (i_td, i_np))
    else:
        rec('C3 asr052_spk_runtime 先限线程再 import numpy', False, '文件缺失')
    return True


def check_precision():
    print('\n[D] 精度 = FP16（APP-047 定案）')
    root = os.path.join(PKG, 'models', 'spk')
    rec('D1 wespeaker-resnet34-fp16 存在',
        os.path.isdir(os.path.join(root, 'wespeaker-resnet34-fp16')), '')
    rec('D2 pyannote_seg_3_0/fp16 存在',
        os.path.isdir(os.path.join(root, 'pyannote_seg_3_0', 'fp16')), '')
    rec('D3 无 fp32 目录（不需要 FP32）',
        not os.path.isdir(os.path.join(root, 'wespeaker-resnet34-fp32')), '')
    # App 侧探测顺序必须是 fp16 优先
    src = os.path.join(REPO, 'live_caption', 'speaker_assets.py')
    txt = open(src, 'r', encoding='utf-8').read()
    ok = ("WES_PRECISIONS = ('fp16', 'fp32')" in txt
          and "SEG_PRECISIONS = ('fp16', 'fp32')" in txt)
    rec('D4 App 侧精度探测顺序 fp16 优先', ok, '')
    return True


# ═══════════════════════════════════════════════════════════
# ② 判据自身的行为测试（影子目录，零推理）
# ═══════════════════════════════════════════════════════════
def _exec_shadow(files, fname, ns_extra=None):
    """在独立命名空间里 exec 一个文件（§十一：不能 import 被测模块）。

    `files` = `{文件名: 源码文本}`。
    """
    ns = {'__name__': 'shadow_mod'}
    if ns_extra:
        ns.update(ns_extra)
    src = files[fname]
    tree = ast.parse(src)
    # 只保留函数/类/赋值 + 必要的 import（顶层 numpy 会让 exec 失败 ⇒ 用 stub）
    mod = ast.Module(body=[n for n in tree.body
                           if isinstance(n, (ast.FunctionDef, ast.ClassDef,
                                             ast.Assign, ast.AnnAssign,
                                             ast.Import, ast.ImportFrom))],
                     type_ignores=[])
    code = compile(mod, fname, 'exec')
    exec(code, ns)
    return ns


def check_reason_handling():
    print('\n[E] App 侧 `embed_shape_out_of_range` 分支（APP-047 §11.4-6）')
    src = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
    txt = open(src, 'r', encoding='utf-8').read()
    rec('E1 定义了 NO_LABEL_REASONS', 'NO_LABEL_REASONS' in txt, '')
    rec('E2 含 embed_shape_out_of_range',
        "'embed_shape_out_of_range'" in txt, '')
    # 行为测试：在影子目录里 exec 该模块的纯函数
    tmp = tempfile.mkdtemp(prefix='app164_st_')
    try:
        files = {}
        for fn in ('speaker_tracker.py',):
            with open(os.path.join(REPO, 'live_caption', fn), 'r',
                      encoding='utf-8') as f:
                files[fn] = f.read()
        ns = _exec_shadow(files, 'speaker_tracker.py')
        f = ns.get('reason_is_no_label')
        if f is None:
            rec('E3 reason_is_no_label 可调用', False, '函数不存在')
        else:
            rec('E3 reason_is_no_label 可调用', True, '')
            rec('E4 embed_shape_out_of_range → 无标签',
                f('embed_shape_out_of_range') is True, '')
            rec('E5 not_clean_speech → 无标签',
                f('not_clean_speech') is True, '')
            rec('E6 overlap → 无标签', f('overlap') is True, '')
            rec('E7 None → 不是无标签', f(None) is False, '')
            rec('E8 未知 reason → 不是无标签',
                f('some_new_reason') is False, '')

            # 🔴🔴 **反证**：把被测对象改成缺陷形态（删掉新 reason）
            bad = files['speaker_tracker.py'].replace(
                "'embed_shape_out_of_range',  # 🆕 APP-047：嵌入形状超界 ⇒ 该段无标签\n",
                '')
            if bad == files['speaker_tracker.py']:
                bad = files['speaker_tracker.py'].replace(
                    "'embed_shape_out_of_range',", '')
            files_bad = {'speaker_tracker.py': bad}
            ns_bad = _exec_shadow(files_bad, 'speaker_tracker.py')
            f_bad = ns_bad.get('reason_is_no_label')
            detected = (f_bad is not None
                        and f_bad('embed_shape_out_of_range') is False)
            rec('E9 反证：删掉新 reason 后判据识破（BUG 组）', detected,
                '缺陷版仍判 True ⇒ 判据恒真' if not detected else '')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return True


def check_gui_cli_logging():
    print('\n[F] GUI / CLI 两条路径都记录「本段无标签」的 reason')
    src = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
    txt = open(src, 'r', encoding='utf-8').read()
    rec('F1 GUI 侧 _spk_reason_seen 存在', '_spk_reason_seen' in txt, '')
    rec('F2 CLI 侧 _cli_spk_reason_seen 存在', '_cli_spk_reason_seen' in txt, '')
    rec('F3 两条路径都记 reason', txt.count("get('reason')") >= 2,
        "get('reason') 出现 %d 次" % txt.count("get('reason')"))
    return True


def check_repo_pkg_equivalence():
    print('\n[G] 仓库 ⇄ 客户包 三文件归一化一致（§104 第③层判据）')
    for fn in ('speaker_tracker.py', 'speaker_assets.py', 'live_caption_app.py'):
        a = os.path.join(REPO, 'live_caption', fn)
        b = os.path.join(PKG, 'app', fn)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            rec('G.%s 两边都存在' % fn, False, '')
            continue
        same = norm_lf(open(a, 'rb').read()) == norm_lf(open(b, 'rb').read())
        rec('G.%s 归一化后逐字节一致' % fn, same,
            'pkg sha=%s' % sha256_file(b)[:16])
    return True


def main():
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print('=' * 74)
    print('app164 —— APP-047 验收（说话人资产重同步 / 3 文件清单 / FP16 / 新 reason）')
    print('ts=%s  python=%s' % (ts, sys.version.split()[0]))
    print('=' * 74)
    check_pkg_files()
    check_pkg_keywords()
    check_import_chain()
    check_precision()
    check_reason_handling()
    check_gui_cli_logging()
    check_repo_pkg_equivalence()

    npass = sum(1 for r in RESULTS if r['ok'])
    nfail = len(RESULTS) - npass
    out = dict(script='app164_app047_spk_resync_test.py', ts=ts,
               pkg=PKG, pass_=npass, fail=nfail,
               verdict=('PASS' if nfail == 0 else 'FAIL'),
               checks=RESULTS)
    dst = os.path.join(HERE, 'app164_app047_spk_resync_evidence.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('-' * 74)
    print('结果：PASS %d / FAIL %d  ⇒ %s' % (npass, nfail, out['verdict']))
    print('证据：%s' % dst)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
