# -*- coding: utf-8 -*-
r"""app158_app043_bridge_wiring.py —— `SpeakerBridge` 接入包内资产的端到端验收（§101）。

## 要验什么

APP-043/044 要求客户机上说话人旁路能用。本脚本验的是**链路闭合**（不跑推理）：

1. `SpeakerBridge` **自动**发现包内资产（`app/asr_spk/` + `models/spk/`）；
2. `_load()` 时把**包内 IR 路径**传给 ASR 的 `SpeakerTracker`
   ⇒ 实例的 `seg_ir`/`wes_ir` 指向包内，**不是** ASR 源码里的硬编码本机路径；
3. 包内资产缺失时 ⇒ **安静降级**（`available=False`），**不抛异常**；
4. 研发机形态（无包内资产）⇒ 回退到 ASR 实验目录，行为不变。

## ★ 纪律

- **不跑推理**：不调用 `feed()` / `on_final()`（会加载 IR 并推理）。
- **不占机器锁**：只做「复制文件 + import + 构造」。
- 用**假包**（临时目录）而不是真包 ⇒ 不污染客户包、不触发打包。

## 判据

| 编号 | 判据 |
|---|---|
| B1 | 造好假包 ⇒ `SpeakerBridge` 的 `_scripts_dir` 指向假包内 `app/asr_spk` |
| B2 | `_load()` 成功 ⇒ `available=True` |
| B3 | tracker 实例的 `seg_ir` 指向假包内 |
| B4 | tracker 实例的 `wes_ir` 指向假包内 |
| B5 | 实例路径 ≠ ASR 源码硬编码默认值（证明是**传的**不是**默认的**） |
| B6 | 空包（无资产）⇒ `available=False` 且 `load_error` 非空，**不抛异常** |
| B7 | `SpeakerBridge` 有 `assets` 相关的可用性说明（供 GUI 提示） |

## 反证

- **D-B5**：不传 IR 参数（模拟旧行为）⇒ 必须拿到硬编码默认值 ⇒ B5 必须 FAIL。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO = os.environ.get('APP158_REPO', '').strip() or \
    r'C:\Users\Trekker-PTL\confucius4-openvino'
LIVE = os.environ.get('APP158_LIVE_DIR', '').strip() or \
    os.path.join(REPO, 'live_caption')
ASR_ROOT = os.environ.get('APP158_ASR_ROOT', '').strip() or \
    r'C:\Users\Trekker-PTL\qwen3asr_06b'
SCRIPTS = os.path.join(ASR_ROOT, 'scripts')
MODELS = os.path.join(ASR_ROOT, 'models')

OUT = os.path.join(
    REPO, 'results', 'app',
    ('app158_app043_bridge_wiring_evidence_pkg.json'
     if os.environ.get('APP158_LIVE_DIR', '').strip()
     else 'app158_app043_bridge_wiring_evidence.json'))

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


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def make_pkg(root):
    """造一个「假客户包」：app/asr_spk/ + models/spk/。"""
    d = os.path.join(root, 'app', 'asr_spk')
    os.makedirs(d, exist_ok=True)
    for fn in CLOSURE_FILES:
        src = os.path.join(SCRIPTS, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(d, fn))
    spk = os.path.join(root, 'models', 'spk')
    wes = os.path.join(spk, 'wespeaker-resnet34-fp16')
    seg = os.path.join(spk, 'pyannote_seg_3_0', 'fp16')
    os.makedirs(wes, exist_ok=True)
    os.makedirs(seg, exist_ok=True)
    for fn in ('openvino_encoder_model.xml', 'openvino_encoder_model.bin'):
        s = os.path.join(MODELS, 'wespeaker-resnet34-fp16', fn)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(wes, fn))
    for fn in ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin'):
        s = os.path.join(MODELS, 'pyannote_seg', 'ov-fp16', fn)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(seg, fn))
    return root


def main():
    print('=' * 78)
    print('SpeakerBridge 接入包内资产 · 端到端验收（§101）')
    print('=' * 78)
    print('LIVE = %s' % LIVE)
    print()

    tmp = tempfile.mkdtemp(prefix='app158_bridge_')
    try:
        fake_pkg = make_pkg(os.path.join(tmp, 'pkg'))

        # 把假包插到 sys.path 最前，并让 speaker_assets 的包根可被覆盖
        sys.path.insert(0, fake_pkg)
        sys.path.insert(0, LIVE)

        SA = load_module('speaker_assets', os.path.join(LIVE,
                                                         'speaker_assets.py'))
        # ★ 让 speaker_assets 的 PKG_ROOT 指向假包
        SA.PKG_ROOT = fake_pkg
        SA.MODELS_DIR = os.path.join(fake_pkg, 'models')
        SA.APP_DIR = os.path.join(fake_pkg, 'app')

        ST = load_module('speaker_tracker', os.path.join(LIVE,
                                                         'speaker_tracker.py'))
        # speaker_tracker 用 `import speaker_assets` ⇒ 命中已加载的模块
        sys.modules['speaker_assets'] = SA

        # ── B1/B2/B3/B4/B5 ────────────────────────────────────
        br = ST.SpeakerBridge(device='GPU.0', seg_device='GPU.0',
                              on_log=lambda m: print('    [log] %s' % m))
        add('B1 SpeakerBridge 自动发现包内 ASR 接口代码',
            os.path.normcase(os.path.abspath(br._scripts_dir)).startswith(
                os.path.normcase(os.path.abspath(fake_pkg))),
            'scripts_dir=%s' % br._scripts_dir)

        loaded = br._load()
        add('B2 _load() 成功 ⇒ available=True',
            loaded and br.available,
            'available=%s err=%s' % (br.available, br.load_error))

        tr = br._tracker
        seg_ok = wes_ok = False
        seg_path = wes_path = ''
        if tr is not None:
            seg_path = getattr(tr, 'seg_ir', '') or ''
            wes_path = getattr(tr, 'wes_ir', '') or ''
            seg_ok = os.path.normcase(os.path.abspath(seg_path)).startswith(
                os.path.normcase(os.path.abspath(fake_pkg)))
            wes_ok = os.path.normcase(os.path.abspath(wes_path)).startswith(
                os.path.normcase(os.path.abspath(fake_pkg)))
        add('B3 tracker.seg_ir 指向包内', seg_ok, 'seg_ir=%s' % seg_path)
        add('B4 tracker.wes_ir 指向包内', wes_ok, 'wes_ir=%s' % wes_path)

        diff_ok = False
        if tr is not None:
            import asr052_speaker_tracker_api as mod
            diff_ok = (os.path.normcase(mod.SEG_IR) !=
                       os.path.normcase(seg_path) and
                       os.path.normcase(mod.WES_IR) !=
                       os.path.normcase(wes_path))
        add('B5 实例路径 ≠ ASR 源码硬编码默认值（证明是「传的」）',
            diff_ok,
            'default_seg=%s' % getattr(mod, 'SEG_IR', '?')
            if tr is not None else 'no tracker')

        # ── B6：客户机形态（包内无资产 + 研发机目录不可达）⇒ 安静降级 ──
        #   ★ 口径要点：不能只把 PKG_ROOT 指向空包 —— 因为研发机目录**真的存在**
        #     ⇒ 会走「研发机回退」分支 ⇒ 加载成功 ⇒ 测不到客户机形态。
        #   ⇒ 必须**同时**把 scripts_dir 指向一个不存在的路径（模拟客户机）。
        empty_root = os.path.join(tmp, 'empty_pkg')
        os.makedirs(os.path.join(empty_root, 'app'), exist_ok=True)
        os.makedirs(os.path.join(empty_root, 'models'), exist_ok=True)
        SA.PKG_ROOT = empty_root
        SA.MODELS_DIR = os.path.join(empty_root, 'models')
        nonexistent = os.path.join(tmp, 'no_such_asr_dir')
        br2 = ST.SpeakerBridge(device='GPU.0',
                               scripts_dir=nonexistent,
                               on_log=lambda m: None)
        err = ''
        try:
            br2._load()
        except Exception as e:
            err = '%s: %s' % (type(e).__name__, e)
        add('B6 客户机形态（无包内资产 + 无研发机目录）⇒ available=False 不抛异常',
            (not br2.available) and not err,
            'available=%s load_error=%s raised=%s'
            % (br2.available, br2.load_error, err))
        add('B6b 降级时给出可读原因（供 GUI 提示「说话人识别不可用」）',
            bool(br2.load_error),
            'load_error=%s' % br2.load_error)

        # ── B7：可用性说明供 GUI 提示 ─────────────────────────
        has_msg = hasattr(br, '_assets') and isinstance(br._assets, dict)
        add('B7 SpeakerBridge 暴露资产可用性信息（供 GUI 提示）',
            has_msg,
            'assets_keys=%s' % (sorted(br._assets.keys())
                                 if br._assets else None))

        # ══════════════════════════════════════════════════════
        # 反证
        # ══════════════════════════════════════════════════════
        print()
        print('[反证] 判据必须能识破假通过：')
        # D-B5：不传 IR 参数 ⇒ 必须拿到硬编码默认值
        try:
            import asr052_speaker_tracker_api as mod2
            tr_def = mod2.SpeakerTracker(device='GPU.0')
            is_dflt = (os.path.normcase(tr_def.seg_ir) ==
                       os.path.normcase(mod2.SEG_IR))
            add('D-B5 不传 IR 参数 ⇒ 落到硬编码默认值 ⇒ B5 必须 FAIL',
                is_dflt,
                'default_seg_ir=%s' % tr_def.seg_ir)
        except Exception as e:
            add('D-B5 反证：构造默认实例失败', False,
                '%s: %s' % (type(e).__name__, e))

        print()
        verdict = 'PASS' if FAIL == 0 else 'FAIL'
        print('=' * 78)
        print('RESULT: %d PASS / %d FAIL  => %s' % (PASS, FAIL, verdict))
        print('=' * 78)

        data = dict(
            script=os.path.basename(__file__),
            live=LIVE,
            fake_pkg=fake_pkg,
            pass_=PASS, fail=FAIL, verdict=verdict,
            detail=DETAIL,
        )
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print('evidence -> %s' % OUT)
        return 0 if FAIL == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
