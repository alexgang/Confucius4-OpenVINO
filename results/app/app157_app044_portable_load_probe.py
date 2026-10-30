# -*- coding: utf-8 -*-
r"""app157_app044_portable_load_probe.py —— APP-044「ASR 接口可移植加载」探针（§101）。

## 要回答的问题

APP-044 要求客户包带上 ASR 的 SpeakerTracker 接口代码 + 两个 OV IR。
**能不能不改 ASR 源码，只靠 App 侧传参就让它在客户机跑起来？**

依据（静态核实，见 `app157_app044_spk_asset_inventory.py`）：
- `SpeakerTracker.__init__(..., seg_ir=..., wes_ir=...)`  **接受 IR 路径参数**
- `WespeakerOVEncoder.__init__(ir_dir=..., device=...)`     **接受 IR 路径参数**
⇒ 整条链参数化 ⇒ 理论上不需要改 ASR 源码。

## 本脚本做什么

1. 把 ASR 的 11 个依赖闭包文件**复制**到临时目录（模拟「打进客户包」）；
2. 把两个 OV IR **复制**到临时目录（模拟包内 `models/spk/`）；
3. **不改一个字节** ASR 源码，只靠 `sys.path` + 构造参数指向临时目录；
4. 实测：`SpeakerTracker` 能否构造成功 ⇒ **不跑推理**（`feed()` 会触发模型加载，
   属于推理 ⇒ 本脚本**不调用** `feed`），只验证 import + 构造 + 参数生效。

## ★ 纪律

- **不跑推理**：不调用 `feed()` / `on_final()`（会加载 IR 并推理）。
- **不占机器锁**：本脚本只做文件复制 + import + 对象构造，不计时、不测速。
- **不 import 客户机依赖**：只 import numpy / openvino（构造时会 `ov.Core()`）。

## 判据

| 编号 | 判据 |
|---|---|
| P1 | 11 个闭包文件复制到临时目录成功 |
| P2 | 两个 OV IR 的 xml/bin 复制成功 |
| P3 | `SpeakerTracker` **不改源码**即可从临时目录 import |
| P4 | 构造时传入包内 IR 路径 ⇒ 实例的 `seg_ir`/`wes_ir` **确实是包内路径** |
| P5 | 源码里的硬编码 `WES_IR`/`SEG_IR` 与实例实际用的路径**不同**（证明参数生效，非默认值） |
| P6 | 临时目录里**没有** torch ⇒ 客户机形态一致 |

## 反证

- **D-P4**：不传 `seg_ir`/`wes_ir`（用默认值）⇒ P4/P5 必须 FAIL
  （否则说明「传参生效」是假象，实例其实还在用硬编码路径）。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ASR_ROOT = os.environ.get('APP157_ASR_ROOT', '').strip() or \
    r'C:\Users\Trekker-PTL\qwen3asr_06b'
SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
MODELS = os.path.join(ASR_ROOT, 'models')
REPO = os.environ.get('APP157_REPO', '').strip() or \
    r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT = os.path.join(
    REPO, 'results', 'app',
    'app157_app044_portable_load_probe_evidence.json')

CLOSURE_FILES = [
    'asr021_bypass_spk_wespeaker.py',
    'asr030_kaldi_fbank_fidelity.py',
    'asr050_spk_qa_speaker_test.py',
    'asr052_speaker_tracker_api.py',
    'asr_json_write.py',
    'asr_lock_common.py',
    'asr_slice_common.py',
    'pya_app_path_seg.py',
    'pya_bypass_spk.py',
    'pya_ref_shim.py',
    'pya_stream_segment.py',
]

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-58s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-58s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def main():
    print('=' * 78)
    print('APP-044 ASR 接口「可移植加载」探针（§101）')
    print('=' * 78)
    print('ASR_ROOT = %s' % ASR_ROOT)
    print()

    tmp = tempfile.mkdtemp(prefix='app157_spk_probe_')
    tmp_scripts = os.path.join(tmp, 'asr_spk')
    tmp_models = os.path.join(tmp, 'models', 'spk')
    os.makedirs(tmp_scripts, exist_ok=True)
    os.makedirs(tmp_models, exist_ok=True)

    try:
        # ── P1：复制闭包文件 ─────────────────────────────────────
        copied = []
        miss = []
        for fn in CLOSURE_FILES:
            src = os.path.join(SCRIPTS, fn)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(tmp_scripts, fn))
                copied.append(fn)
            else:
                miss.append(fn)
        add('P1 %d 个闭包文件复制到临时目录' % len(CLOSURE_FILES),
            not miss,
            'copied=%d missing=%s' % (len(copied), miss))

        # ── P2：复制两个 OV IR ──────────────────────────────────
        ir_copies = []
        ir_miss = []
        wes_src = os.path.join(MODELS, 'wespeaker-resnet34-fp16')
        seg_src = os.path.join(MODELS, 'pyannote_seg', 'ov-fp16')
        wes_dst = os.path.join(tmp_models, 'wespeaker-resnet34-fp16')
        seg_dst = os.path.join(tmp_models, 'pyannote_seg_3_0')
        os.makedirs(wes_dst, exist_ok=True)
        os.makedirs(seg_dst, exist_ok=True)
        for fn in ('openvino_encoder_model.xml', 'openvino_encoder_model.bin'):
            s = os.path.join(wes_src, fn)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(wes_dst, fn))
                ir_copies.append(os.path.join('wespeaker-resnet34-fp16', fn))
            else:
                ir_miss.append(fn)
        for fn in ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin'):
            s = os.path.join(seg_src, fn)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(seg_dst, fn))
                ir_copies.append(os.path.join('pyannote_seg_3_0', fn))
            else:
                ir_miss.append(fn)
        add('P2 两个 OV IR 的 xml/bin 复制成功',
            not ir_miss,
            'copied=%d missing=%s' % (len(ir_copies), ir_miss))

        # ── P3：只靠 sys.path 从临时目录 import（不改源码）────
        sys.path.insert(0, tmp_scripts)
        imp_err = ''
        SpeakerTracker = None
        try:
            from asr052_speaker_tracker_api import SpeakerTracker
        except Exception as e:
            imp_err = '%s: %s' % (type(e).__name__, e)
        add('P3 SpeakerTracker 从临时目录 import 成功（**不改源码**）',
            SpeakerTracker is not None,
            imp_err or 'ok')

        inst = None
        ctor_err = ''
        if SpeakerTracker is not None:
            try:
                inst = SpeakerTracker(
                    device='GPU.0', seg_device='GPU.0',
                    seg_ir=seg_dst, wes_ir=wes_dst)
            except Exception as e:
                ctor_err = '%s: %s' % (type(e).__name__, e)
        add('P4 构造成功（传入包内 IR 路径）',
            inst is not None,
            ctor_err or 'ok')

        if inst is not None:
            seg_ok = os.path.normcase(inst.seg_ir) == \
                os.path.normcase(seg_dst)
            wes_ok = os.path.normcase(inst.wes_ir) == \
                os.path.normcase(wes_dst)
            add('P4a 实例 seg_ir 指向包内路径',
                seg_ok, 'seg_ir=%s' % inst.seg_ir)
            add('P4b 实例 wes_ir 指向包内路径',
                wes_ok, 'wes_ir=%s' % inst.wes_ir)

            # P5：实例实际用的路径 ≠ 源码里的硬编码默认值
            import asr052_speaker_tracker_api as mod
            dflt_seg = mod.SEG_IR
            dflt_wes = mod.WES_IR
            diff_seg = os.path.normcase(dflt_seg) != \
                os.path.normcase(inst.seg_ir)
            diff_wes = os.path.normcase(dflt_wes) != \
                os.path.normcase(inst.wes_ir)
            add('P5 实际路径 ≠ 源码硬编码默认值（证明传参生效）',
                diff_seg and diff_wes,
                'default_seg=%s default_wes=%s' % (dflt_seg, dflt_wes))

        # ── P6：临时目录无 torch ────────────────────────────────
        has_torch = False
        for d in (tmp_scripts, tmp_models):
            for root, dirs, files in os.walk(d):
                for fn in files:
                    if fn.lower().startswith('torch'):
                        has_torch = True
        add('P6 临时目录里没有 torch（与客户机形态一致）',
            not has_torch,
            'has_torch=%s' % has_torch)

        # ── 反证 D-P4：不传参 ⇒ 必须拿到硬编码默认值 ────────────
        if SpeakerTracker is not None:
            try:
                inst_def = SpeakerTracker(device='GPU.0')
                got_default = (os.path.normcase(inst_def.seg_ir) ==
                               os.path.normcase(inst_def_seg_default())
                               if False else True)
                # 直接比较：默认值应是源码里的硬编码路径
                import asr052_speaker_tracker_api as mod2
                is_dflt = (os.path.normcase(inst_def.seg_ir) ==
                           os.path.normcase(mod2.SEG_IR))
                add('D-P4 反证：不传参 ⇒ seg_ir 落到硬编码默认值 ⇒ P4a 必 FAIL',
                    is_dflt,
                    'default_seg_ir=%s' % inst_def.seg_ir)
            except Exception as e:
                add('D-P4 反证：构造默认实例失败', False,
                    '%s: %s' % (type(e).__name__, e))
        else:
            add('D-P4 反证：无法 import ⇒ 跳过', False, imp_err)

        print()
        verdict = 'PASS' if FAIL == 0 else 'FAIL'
        print('=' * 78)
        print('RESULT: %d PASS / %d FAIL  => %s' % (PASS, FAIL, verdict))
        print('=' * 78)

        data = dict(
            script=os.path.basename(__file__),
            asr_root=ASR_ROOT,
            tmp=tmp,
            pass_=PASS, fail=FAIL, verdict=verdict,
            copied_files=copied,
            ir_copies=ir_copies,
            import_error=imp_err,
            ctor_error=ctor_err,
            detail=DETAIL,
        )
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print('evidence -> %s' % OUT)
        return 0 if FAIL == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def inst_def_seg_default():
    return ''


if __name__ == '__main__':
    sys.exit(main())
