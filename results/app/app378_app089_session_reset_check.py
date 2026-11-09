"""APP-089 §4 结构检查：**连续开两次会话，第二次开始时克隆目录为空**。

reviewer 原文（APP-089 §4）：
> 连续开两次会话，第二次开始时克隆目录为空。

🔴 本脚本**不跑设备推理**（纯 CPU 静态 + 目录操作）：
  ① 第 1 次「会话」⇒ 往克隆目录里塞**残留文件**（模拟第一次会话留下的）
     ⇒ 包含 `.wav` 与 **`.txt`**（EXT 踩过的坑：旁边的 `.txt` 把克隆切成 ICL）
  ② 调 `CloneVoices.reset_session()`（App 侧 `_reset_clone_session()` 的第一层）
  ③ 断言：克隆目录**为空**（`.txt` 数 = 0、总文件数 = 0）
  ④ 断言：策略层缓存（`_span`/`_nearest`/`_emb`/`_pushed`/`_split_res`）已清

🔴 **反证组**：把 `reset_session()` 里的「清目录」那段去掉
   ⇒ ③ 必须 FAIL（否则本脚本是恒真脚本）

用法：python app378_app089_session_reset_check.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
EVID = os.path.join(REPO, 'results', 'app')

CHECKS = []


def chk(name, ok, detail=''):
    CHECKS.append(dict(name=name, ok=bool(ok), detail=str(detail)[:300]))


def load_module(name):
    """按文件路径加载 live_caption 下的模块（避免包导入副作用）。"""
    path = os.path.join(DEV, name + '.py')
    spec = importlib.util.spec_from_file_location('lc_' + name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, DEV)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(DEV)
    return mod


def scenario(tmpdir, break_cleanup=False):
    """跑一遍「两次会话」场景 ⇒ 返回 (results, clone_dir)。"""
    os.environ['LIVECAP_CLONE_VOICES_DIR'] = tmpdir
    cv = load_module('clone_voice')

    # ── 第 1 次会话：模拟留下残留（含 `.txt`）──
    with open(os.path.join(tmpdir, 'S1_1.wav'), 'wb') as f:
        f.write(b'RIFFfake')
    with open(os.path.join(tmpdir, 'S1_1.txt'), 'w', encoding='utf-8') as f:
        f.write('这是 EXT 踩过的坑：旁边的 .txt 会把克隆切成 ICL')
    with open(os.path.join(tmpdir, 'S2_1.wav'), 'wb') as f:
        f.write(b'RIFFfake')

    # 🔴 **策略层实例**（`CloneVoices` 自建旁路 + 音色表 ⇒ 不依赖外部资源）
    inst = cv.CloneVoices(on_log=lambda m: None)

    # 策略层缓存也填上
    inst._span[1] = (0.0, 1.0)
    inst._nearest[1] = ('S1', 0.9)
    inst._emb[1] = [0.1, 0.2, 0.3]
    inst._pushed[1] = ('S1', 0.9)
    inst._split_res[1] = {'n_parts': 2, 'n_split': 1}

    n_txt_before = len([x for x in os.listdir(tmpdir) if x.endswith('.txt')])
    n_files_before = len(os.listdir(tmpdir))

    # ── 第 2 次会话开始：清空 ──
    if break_cleanup:
        # 🔴 **反证**：只清策略层缓存，**不清克隆目录**
        with inst._lock:
            inst._span.clear()
            inst._nearest.clear()
            inst._emb.clear()
            inst._pushed.clear()
            inst._split_res.clear()
    else:
        inst.reset_session()

    n_txt_after = len([x for x in os.listdir(tmpdir) if x.endswith('.txt')])
    n_files_after = len(os.listdir(tmpdir))
    cache = dict(
        span=len(inst._span), nearest=len(inst._nearest), emb=len(inst._emb),
        pushed=len(inst._pushed), split_res=len(inst._split_res))
    try:
        inst._stop.set()
    except Exception:
        pass
    return dict(n_txt_before=n_txt_before, n_files_before=n_files_before,
                n_txt_after=n_txt_after, n_files_after=n_files_after,
                cache=cache)


def main():
    tmp1 = tempfile.mkdtemp(prefix='lc_clone_test_')
    try:
        r = scenario(tmp1)
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)

    # ── 闸门 ①：会话开始前，目录里确实有残留（含 `.txt`）──
    chk('前置: 第 1 次会话留下残留（含 .txt）',
        r['n_txt_before'] >= 1 and r['n_files_before'] >= 3,
        'before=%s' % r)

    # ── 闸门 ②：第 2 次会话开始时**克隆目录为空**（APP-089 §4 明文）──
    chk('APP-089 §4: 第 2 次会话开始时克隆目录为空（总文件 0）',
        r['n_files_after'] == 0, 'n_files_after=%s' % r['n_files_after'])
    chk('APP-089 §4: 克隆目录 .txt 数 = 0',
        r['n_txt_after'] == 0, 'n_txt_after=%s' % r['n_txt_after'])

    # ── 闸门 ③：策略层缓存已清 ──
    chk('策略层缓存已清（span/nearest/emb/pushed/split_res 全 0）',
        all(v == 0 for v in r['cache'].values()), 'cache=%s' % r['cache'])

    # ── 反证组：去掉「清目录」⇒ 闸门 ② 必须 FAIL ──
    tmp2 = tempfile.mkdtemp(prefix='lc_clone_test_neg_')
    try:
        r_bad = scenario(tmp2, break_cleanup=True)
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)
    chk('反证: 去掉清目录 ⇒ 闸门②真的 FAIL',
        (r['n_files_after'] == 0) and (r_bad['n_files_after'] > 0),
        'good=%s bad=%s' % (r['n_files_after'], r_bad['n_files_after']))

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(n_pass=n_pass, n_fail=n_fail, good=r, neg=r_bad, checks=CHECKS)
    p = os.path.join(EVID, 'app378_app089_session_reset_check.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print('OUT=%s' % p)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
