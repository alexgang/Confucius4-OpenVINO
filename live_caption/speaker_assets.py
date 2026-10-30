# -*- coding: utf-8 -*-
r"""speaker_assets.py —— 🔴🔴🔴 APP-043 / APP-044：包内说话人资产的**定位与可移植化**。

## 为什么需要这一层（APP-043 / APP-044）

APP-043 说「ASR 的说话人接口已交付（ASR-029），APP-039/040 的克隆按句绑定 spk
可以接入了」；APP-044 说「客户包**带上**说话人识别的小模型」。

但 ASR 侧的接口代码与模型**都不在 git 仓库里**，而且**全部硬编码本机绝对路径**：

```python
# asr052_speaker_tracker_api.py（ASR 侧，只读）
WORK   = r'C:\Users\Trekker-PTL\qwen3asr_06b'
REPO   = r'C:\Users\Trekker-PTL\confucius4-openvino'
SHARED = r'C:\Users\Trekker-PTL\shared'
WES_IR = os.path.join(WORK, 'models', 'wespeaker-resnet34-fp16')
SEG_IR = os.path.join(WORK, 'models', 'pyannote_seg', 'ov-fp16')
```

⇒ 在客户机上这些路径**必然不存在** ⇒ 旁路静默降级 ⇒ 用户永远看不到说话人标签。

## 🔴🔴🔴 关键设计决策：**不改 ASR 的源码**

实测（`results/app/app157_app044_portable_load_probe.py`，9 PASS / 0 FAIL）证明：
ASR 的接口**整条链都是参数化的**：

- `SpeakerTracker.__init__(..., seg_ir=..., wes_ir=...)`
- `WespeakerOVEncoder.__init__(ir_dir=..., device=...)`

⇒ **只要在构造时把包内 IR 路径传进去**，就完全不需要改 ASR 的任何一个字节
⇒ 好处：① ASR 模块的资产不被 App 改动 ② ASR 后续更新接口时 App 无需跟进
③ 客户机与研发机跑的是**同一份** ASR 代码。

## 包内布局（APP-044 落地形态）

```
<包根>/
  app/
    asr_spk/                       ← ASR 的 SpeakerTracker 接口代码（11 个文件）
      asr052_speaker_tracker_api.py
      asr050_spk_qa_speaker_test.py
      ...
  models/
    spk/
      wespeaker-resnet34-<精度>/    ← wespeaker 的 OV IR（xml + bin）
        openvino_encoder_model.xml
        openvino_encoder_model.bin
      pyannote_seg_3_0/<精度>/     ← pyannote/segmentation-3.0 的 OV IR
        pyannote_seg_3_0.xml
        pyannote_seg_3_0.bin
```

## 精度口径

APP-044：「精度以 ASR 交付的版本为准，FP16 还是 FP32 **由 reviewer 按 ASR-025 的
复核结论通知**」。

🔴 **该裁定尚未到达**（截至 2026-10-30 09:2x，`shared/` 下无相关通知）
⇒ 本模块**不硬编码**精度，而是**按优先级探测**目录里实际存在的那个：
`fp32` → `fp16`。
⇒ 这样 reviewer 一旦裁定，只需把对应目录打进包即可，**无需改代码**。

## 降级语义（APP-044 明文）

> 模型文件缺失时，旁路自动关闭，GUI 提示"说话人识别不可用"，其他功能不受影响。

⇒ 本模块提供 `resolve()` 返回 `(scripts_dir, wes_ir, seg_ir, reason)`；
找不到时 `reason` 非空 ⇒ 调用方关闭旁路并提示。
"""
from __future__ import annotations

import os
import time
from typing import Optional, Tuple

# ── 包内相对布局（单一数据源）────────────────────────────────────
# 🔴 APP-044：模型放在 `models/spk/` 下；ASR 接口代码放在 `app/asr_spk/`
PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(PKG_ROOT, 'app')
MODELS_DIR = os.path.join(PKG_ROOT, 'models')

# ASR 接口代码的**包内**目录（相对 app/）
ASR_SPK_SUBDIR = 'asr_spk'
# 说话人模型在 `models/` 下的子目录
SPK_MODELS_SUBDIR = 'spk'

# ASR 接口的入口模块名（APP-044 要带的那份代码）
ASR_ENTRY_MODULE = 'asr052_speaker_tracker_api'

# 🔴 精度优先级：**FP32 优先**（ASR-025 归因：FP16 保真不过门槛、
#   FP32 过门槛；余弦 ≥0.999 且相对最大偏差 ≤1e-3）。
#   ⚠️ 裁定未到时，**按实际存在的目录**探测 ⇒ 代码不必因裁定而改。
WES_PRECISIONS = ('fp32', 'fp16')
SEG_PRECISIONS = ('fp32', 'fp16')

# 两种精度下的目录名（wespeaker 与 pyannote 的命名不一致，故分开列）
WES_DIR_TMPL = 'wespeaker-resnet34-%s'
SEG_DIR_TMPL = 'pyannote_seg_3_0/%s'

# 各精度下的 IR 文件名
WES_IR_FILES = ('openvino_encoder_model.xml', 'openvino_encoder_model.bin')
SEG_IR_FILES = ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin')

# 研发机上的 ASR 实验目录（**不在 git 仓库内**）⇒ 客户机必然找不到
DEV_ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'


def _has_pair(d: str, names) -> bool:
    """目录里 xml+bin 是否**成对**存在。"""
    if not d or not os.path.isdir(d):
        return False
    return all(os.path.isfile(os.path.join(d, n)) for n in names)


def find_spk_model_root(pkg_root: Optional[str] = None) -> Optional[str]:
    """定位 `models/spk` 目录（不存在则 None）。

    🔴 `pkg_root` 语义 = **包根**（含 `app/` 与 `models/` 两层）
      ⇒ 与 `find_asr_scripts()` 保持一致。
      （曾把 base 当成 models 目录 ⇒ 拼出 `<base>/spk` ⇒ 永远找不到 ⇒
        假包判据恒 FAIL。）
    """
    root = pkg_root or PKG_ROOT
    cand = os.path.join(root, 'models', SPK_MODELS_SUBDIR)
    return cand if os.path.isdir(cand) else None


def find_asr_scripts(pkg_root: Optional[str] = None) -> Optional[str]:
    """定位包内 ASR 接口代码目录（含入口模块即算有效）。"""
    root = pkg_root or PKG_ROOT
    cand = os.path.join(root, 'app', ASR_SPK_SUBDIR)
    if os.path.isdir(cand) and os.path.isfile(
            os.path.join(cand, ASR_ENTRY_MODULE + '.py')):
        return cand
    return None


def find_wes_ir(pkg_root: Optional[str] = None) -> Tuple[Optional[str], str]:
    """定位 wespeaker 的 OV IR 目录。

    返回 `(目录, 说明)`；目录为 None ⇒ 不可用。
    """
    spk_root = find_spk_model_root(pkg_root)
    if not spk_root:
        return None, '包内无 models/%s 目录' % SPK_MODELS_SUBDIR
    for prec in WES_PRECISIONS:
        d = os.path.join(spk_root, WES_DIR_TMPL % prec)
        if _has_pair(d, WES_IR_FILES):
            return d, 'wespeaker %s' % prec
    return None, '包内无 wespeaker OV IR（%s 需成对）' % ' + '.join(
        WES_IR_FILES)


def find_seg_ir(pkg_root: Optional[str] = None) -> Tuple[Optional[str], str]:
    """定位 pyannote/segmentation-3.0 的 OV IR 目录。"""
    spk_root = find_spk_model_root(pkg_root)
    if not spk_root:
        return None, '包内无 models/%s 目录' % SPK_MODELS_SUBDIR
    for prec in SEG_PRECISIONS:
        d = os.path.join(spk_root, SEG_DIR_TMPL % prec)
        if _has_pair(d, SEG_IR_FILES):
            return d, 'pyannote_seg_3_0 %s' % prec
    return None, '包内无 pyannote_seg_3_0 OV IR'


def resolve(base: Optional[str] = None) -> dict:
    """一次性解析出全部资产位置。

    返回 dict：
    ```
    {
      'ok': bool,            # 全部就绪 ⇒ 旁路可启用
      'scripts_dir': str|None,
      'wes_ir': str|None,
      'seg_ir': str|None,
      'reason': str,         # 不可用时的原因（可直接给用户看）
      'wes_note': str,
      'seg_note': str,
    }
    ```
    """
    scripts = find_asr_scripts(base)
    wes, wes_note = find_wes_ir(base)
    seg, seg_note = find_seg_ir(base)

    missing = []
    if not scripts:
        missing.append('ASR 说话人接口代码（app/%s/）' % ASR_SPK_SUBDIR)
    if not wes:
        missing.append('wespeaker 的 OV IR')
    if not seg:
        missing.append('pyannote/segmentation-3.0 的 OV IR')

    return dict(
        ok=not missing,
        scripts_dir=scripts,
        wes_ir=wes,
        seg_ir=seg,
        reason='' if not missing else '缺少：%s' % '、'.join(missing),
        wes_note=wes_note,
        seg_note=seg_note,
    )


def dev_fallback_scripts() -> str:
    """研发机上的 ASR 目录（**仅开发期**；客户机必然不存在）。"""
    return DEV_ASR_SCRIPTS


# ══════════════════════════════════════════════════════════════
# 🔴🔴🔴 APP-043：「限线程」等启动期事实必须**记进日志**
#
# ★ 为什么日志写器放在这里，而不是用 `tts_service.append_session_log`：
#   APP-043 要求限线程设置**在任何 numpy / OpenVINO import 之前**生效，
#   而 `tts_service` 会 import numpy/openvino 链 ⇒ 此刻还不能用它。
#   ⇒ 本模块**零重依赖**（只用 os/time）⇒ 可在 import numpy 之前调用。
# ══════════════════════════════════════════════════════════════

# 会话日志目录（与 `tts_service.session_log_path()` 同一目录 ⇒ 同一批文件）
LOG_DIR_NAME = 'Confucius4LiveCaption'


def log_dir() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(base, LOG_DIR_NAME)


def append_log(msg: str) -> bool:
    """往会话日志追加一行（**永不抛异常**；失败静默）。

    与 `tts_service.append_session_log` 写**同一个目录**下的
    `session_<时间戳>.log` ⇒ 诊断时能在同一个文件里看到启动期事实。
    """
    try:
        d = log_dir()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'session_%s.log' % time.strftime('%Y%m%d'))
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
        return True
    except Exception:
        return False


def log_thread_env(tag: str = 'App') -> dict:
    """把当前线程相关环境变量**记进日志**（APP-043 明文要求）。

    返回读到的实际值（供调用方显示 / 断言）。
    """
    keys = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')
    vals = {k: os.environ.get(k) for k in keys}
    append_log('%s 线程环境变量：%s' % (tag, vals))
    return vals


def summary() -> str:
    """一行摘要（用于日志 / GUI 提示）。"""
    r = resolve()
    if r['ok']:
        return ('说话人识别可用（%s；%s）'
                % (r['wes_note'], r['seg_note']))
    return '说话人识别不可用：%s' % r['reason']
