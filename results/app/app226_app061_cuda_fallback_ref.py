#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app226 —— §130：**CUDA 路线「回落预设」必须换回参考音频**（串音缺陷）的验收。

## 缺陷（reviewer 未点名，§130 自查发现）

`live_caption/tts_worker.py` 的 `_apply_spk_voice()`：
当 `spk` **有值**但**该 spk 没登记音色**（`row is None`）⇒ 回落预设 A，
但**没有** `eng.set_ref_audio(预设A的参考音频)`
⇒ **边车里仍是上一个说话人的克隆参考音频** ⇒ 实播**串音**，
且逐句遥测写 `voice_kind='preset'` **与实际不符** ⇒ **矛盾字段**。

🔴 **对比**：`_fallback_to_preset()` 的 CUDA 分支**本来就会**换 ref
⇒ 两条「回落预设」出口**行为不一致** ⇒ 这就是缺陷点。

## 修法

新增共用出口 `_fallback_to_preset_ref_cuda()`，
`_apply_spk_voice()` 的 3 个回落出口 + `_fallback_to_preset()` 的 CUDA 分支
**全部收敛到它** ⇒ 以后再漏就会很明显。

## 本脚本做什么

🔴 **不 import 被测模块**（顶层 numpy ⇒ import 阶段 abort ⇒ MEMORY 四）
⇒ 用 `ast` 抽源码 + `exec` ⇒ **假 FAIL 不会发生**。
🔴 **判据三态**：True / False / None（无法判定）。
🔴 **反证**：把修好的代码改回旧行为 ⇒ 判据必须 FAIL（证明非恒真）。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
TARGET = os.path.join(REPO, 'live_caption', 'tts_worker.py')
OUT_JSON = os.path.join(HERE, 'app226_app061_cuda_fallback_ref_evidence.json')


# ── 加载被测模块（不 import ⇒ 用 ast 抽源码 + exec） ─────────────────────
def load_module(path=TARGET, name='tts_worker_probe'):
    """🔴 用 `ast` 抽源码 + `exec` ⇒ **不触发**顶层 numpy import。"""
    with open(path, 'rb') as f:
        src = f.read().decode('utf-8')
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        # 🔴 丢掉会 import 重依赖的顶层语句（numpy/torch/transformers…）
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = ''
            if isinstance(node, ast.Import):
                mod = node.names[0].name.split('.')[0]
            else:
                mod = (node.module or '').split('.')[0]
            if mod in ('numpy', 'torch', 'transformers', 'babelvox',
                       'soundcard', 'openvino', 'librosa', 'scipy'):
                continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        keep.append(node)
    mod = types.ModuleType(name)
    mod.__file__ = path
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, 'exec'),
         mod.__dict__)
    return mod


# ── 假 CUDA 引擎（记录 set_ref_audio 调用） ─────────────────────────────
class FakeCudaEngine:
    USES_REF_AUDIO = True

    def __init__(self):
        self.ref_audio = None
        self.calls = []

    def set_ref_audio(self, path):
        self.calls.append(path)
        self.ref_audio = path


class FakeBabelvoxEngine:
    USES_REF_AUDIO = False


def make_worker(mod, engine):
    """🔴 造一个**最小可用**的 worker 实例（只填本判据需要的字段）。"""
    w = mod.TTSWorker.__new__(mod.TTSWorker)
    w.engine = engine
    w.speaker_embed = None
    w.speaker_name = 'A'
    w._preset_embed = None
    w._preset_name = 'A'
    w._preset_ref_path = r'C:\pkg\preset_A.wav'
    w._clone_ref_path = None
    w._clone_active = False
    w._clone_mode = None
    w._last_voice_spk = None
    w._last_voice_kind = 'preset'
    w._spk_voice_lock = __import__('threading').RLock()
    w._spk_voices = {}
    return w


def run_scenario(mod, engine, spk, voices):
    """跑一次「切到某 spk」⇒ 返回 (返回的音色来源, 边车最终 ref, set_ref 序列)。"""
    w = make_worker(mod, engine)
    w._spk_voices = voices
    kind = w._apply_spk_voice(spk)
    return kind, getattr(engine, 'ref_audio', None), list(getattr(engine, 'calls', []))


def main():
    out = {'script': 'app226_app061_cuda_fallback_ref.py',
           'correction': 'APP-061 ①（§130 自查发现的串音缺陷）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO, 'target': TARGET}
    checks = []

    def chk(name, ok, detail):
        checks.append({'name': name, 'ok': (None if ok is None else bool(ok)),
                       'detail': detail})

    try:
        mod = load_module()
    except Exception as e:
        out['error'] = '加载被测模块失败：%s' % e
        out['checks'] = checks
        out['n_pass'] = 0
        out['n_fail'] = len(checks)
        out['verdict'] = 'FAIL'
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('加载失败：%s' % e)
        return 2

    # ── ① 缺陷现场：CUDA 下 spk 未登记音色 ⇒ 必须换回预设 A 的 ref ──────
    eng = FakeCudaEngine()
    voices = {'S1': {'vec': None, 'ref_path': r'C:\tmp\S1_clone.wav'}}
    kind, ref, calls = run_scenario(mod, eng, 'S2', voices)
    chk('cuda_row_none_returns_preset',
        kind == 'preset',
        'spk=S2 未登记 ⇒ 返回音色来源 %r（须 preset）' % kind)
    chk('cuda_row_none_swaps_ref_back_to_preset',
        ref == r'C:\pkg\preset_A.wav',
        '边车最终 ref=%r（须预设 A 的 preset_A.wav）' % ref)
    chk('cuda_row_none_emits_set_ref_audio',
        calls == [r'C:\pkg\preset_A.wav'],
        'set_ref_audio 调用序列=%r（须恰好 1 次，且是预设 A）' % calls)

    # ── ② 前提：先切到已登记的 spk ⇒ 边车用的是**克隆**音频 ────────────
    eng2 = FakeCudaEngine()
    kind2, ref2, calls2 = run_scenario(mod, eng2, 'S1', voices)
    chk('cuda_known_spk_uses_clone_ref',
        kind2 == 'clone' and ref2 == r'C:\tmp\S1_clone.wav',
        'spk=S1 已登记 ⇒ 来源=%r ref=%r（须 clone / S1_clone.wav）' % (kind2, ref2))

    # ── ③ 缺陷现场（完整时序）：S1 克隆 ⇒ 下一个未登记 spk ⇒ 必须换回预设 ──
    eng3 = FakeCudaEngine()
    w = make_worker(mod, eng3)
    w._spk_voices = voices
    k1 = w._apply_spk_voice('S1')
    mid_ref = eng3.ref_audio
    k2 = w._apply_spk_voice('S2')
    chk('crosstalk_scenario_s1_clone_then_s2_unknown',
        (mid_ref == r'C:\tmp\S1_clone.wav'
         and eng3.ref_audio == r'C:\pkg\preset_A.wav'),
        'S1 克隆后 ref=%r；S2 未登记后 ref=%r（须 S1_clone.wav → preset_A.wav）'
        % (mid_ref, eng3.ref_audio))
    chk('crosstalk_scenario_voice_kind',
        (k1 == 'clone' and k2 == 'preset'),
        '来源序列=%r,%r（须 clone,preset）' % (k1, k2))

    # ── ④ 「该 spk 没有 ref」分支 ⇒ 同样要换回预设 ─────────────────────
    eng4 = FakeCudaEngine()
    voices4 = {'S3': {'vec': None, 'ref_path': None}}
    kind4, ref4, calls4 = run_scenario(mod, eng4, 'S3', voices4)
    chk('cuda_no_ref_swaps_back_to_preset',
        (kind4 == 'preset' and ref4 == r'C:\pkg\preset_A.wav'),
        '该 spk 无 ref ⇒ 来源=%r ref=%r（须 preset / preset_A.wav）' % (kind4, ref4))

    # ── ⑤ 「切换参考音频抛异常」分支 ⇒ 也要换回预设 ────────────────────
    class FailingEngine(FakeCudaEngine):
        def set_ref_audio(self, path):
            if path.endswith('S1_clone.wav'):
                raise RuntimeError('模拟切换失败')
            FakeCudaEngine.set_ref_audio(self, path)
    eng5 = FailingEngine()
    kind5, ref5, calls5 = run_scenario(mod, eng5, 'S1', voices)
    chk('cuda_switch_failure_swaps_back_to_preset',
        (kind5 == 'preset' and ref5 == r'C:\pkg\preset_A.wav'),
        '切换失败 ⇒ 来源=%r ref=%r（须 preset / preset_A.wav）' % (kind5, ref5))

    # ── ⑥ 🔴 **反证**：BabelVox 路线**不受影响**（不得被这个修复改掉）───
    eng6 = FakeBabelvoxEngine()
    w6 = make_worker(mod, eng6)
    w6._preset_embed = 'PRESET_EMBED'
    w6._preset_name = 'A'
    w6._spk_voices = voices
    kind6 = w6._apply_spk_voice('S2')
    chk('babelvox_route_unchanged',
        (kind6 == 'preset' and w6.speaker_embed == 'PRESET_EMBED'
         and w6.speaker_name == 'A'),
        'BabelVox 路线 ⇒ 来源=%r embed=%r name=%r（须 preset / PRESET_EMBED / A）'
        % (kind6, w6.speaker_embed, w6.speaker_name))

    # ── ⑦ 🔴 **反证（判据自检）**：把修好的代码**改回旧行为** ⇒ 必须 FAIL ──
    #   ⇒ 证明判据**非恒真**（不是「怎么都 PASS」）。
    try:
        raw = open(TARGET, 'rb').read()
        use_crlf = raw.count(b'\r\n') == raw.count(b'\n') and raw.count(b'\r\n') > 0
        src = raw.decode('utf-8')
        # 🔴 **行尾归一化**：本文件是 CRLF ⇒ 补丁片段用 \n 写会**匹配不上**
        #   ⇒ 先统一成 \n 再替换，写回时还原 CRLF。
        if use_crlf:
            src = src.replace('\r\n', '\n')
        n_before = src.count('_fallback_to_preset_ref_cuda(')
        # 把 `_apply_spk_voice` 里的共用出口调用**去掉**（模拟改前）
        broken = src.replace(
            "            self._fallback_to_preset_ref_cuda('spk 未登记音色')\n",
            '', 1)
        broken = broken.replace(
            "                self._fallback_to_preset_ref_cuda('该 spk 没有参考音频')\n",
            '', 1)
        broken = broken.replace(
            "                self._fallback_to_preset_ref_cuda('切换参考音频失败')\n",
            '', 1)
        # 让 `_fallback_to_preset` 的 CUDA 分支退回旧写法
        broken = broken.replace(
            "            self._fallback_to_preset_ref_cuda(why)\n",
            "            self.speaker_embed = None\n"
            "            self.speaker_name = self._preset_name or 'A'\n"
            "            ref = self._preset_ref_path\n"
            "            if ref:\n"
            "                try:\n"
            "                    eng.set_ref_audio(ref)\n"
            "                except Exception as e:\n"
            "                    log('[tts_worker] fail %s' % e)\n"
            "            else:\n"
            "                log('[tts_worker] no preset ref')\n", 1)
        n_after = broken.count('_fallback_to_preset_ref_cuda(')
        # 🔴 **反证必须真的把修复拆掉** ⇒ 否则反证无鉴别力
        if n_after >= n_before:
            raise RuntimeError('反证构造未生效：调用数 %d → %d（须减少）'
                               % (n_before, n_after))
        if use_crlf:
            broken = broken.replace('\n', '\r\n')
        tmp = os.path.join(HERE, '_app226_mutant_tts_worker.py')
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(broken)
        mod_m = load_module(tmp, 'tts_worker_mutant')
        emg = FakeCudaEngine()
        k, r, c = run_scenario(mod_m, emg, 'S2', voices)
        chk('counterproof_old_behavior_is_caught',
            (k == 'preset' and r != r'C:\pkg\preset_A.wav'),
            '改回旧行为（调用数 %d→%d）⇒ 来源=%r ref=%r（须 preset / **不是** preset_A.wav）'
            % (n_before, n_after, k, r))
        os.remove(tmp)
    except Exception as e:
        chk('counterproof_old_behavior_is_caught', None,
            '反证构造失败 ⇒ 无法判定：%s' % e)

    n_pass = sum(1 for c in checks if c['ok'] is True)
    n_fail = sum(1 for c in checks if c['ok'] is False)
    n_none = sum(1 for c in checks if c['ok'] is None)
    out['checks'] = checks
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail
    out['n_none'] = n_none
    out['verdict'] = 'PASS' if (n_fail == 0 and n_none == 0) else 'FAIL'

    print('===== app226 CUDA 回落换 ref（串音缺陷）=====')
    for c in checks:
        mark = 'NONE' if c['ok'] is None else ('PASS' if c['ok'] else 'FAIL')
        print('  [%s] %s' % (mark, c['detail']))
    print('\n结果：%d PASS / %d FAIL / %d 无法判定 ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
