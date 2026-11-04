# -*- coding: utf-8 -*-
r"""speaker_assets.py —— 🔴🔴🔴 APP-043 / APP-044：包内说话人资产的**定位与可移植化**。

## 为什么需要这一层（APP-043 / APP-044）

APP-043 说「ASR 的说话人接口已交付（ASR-029），APP-039/040 的克隆按句绑定 spk
可以接入了」；APP-044 说「客户包**带上**说话人识别的小模型」。

但 ASR 侧的接口代码与模型**都不在 git 仓库里**，而且**全部硬编码本机绝对路径**：

```python
# asr052_speaker_tracker_api.py（ASR 侧，只读）
# 🔴 【APP-052 ③】原文示例里写的是开发机的**真实家目录绝对路径**
#    ⇒ 随包发给客户会**泄漏开发机用户名** ⇒ 一律写成 `<HOME>` 占位
#    （🔴 APP-057 ③：连**注释里举例**都不能出现真实家目录 ⇒ 本行同样脱敏）。
WORK   = r'<HOME>\qwen3asr_06b'
REPO   = r'<HOME>\confucius4-openvino'
SHARED = r'<HOME>\shared'
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

# 🔴🔴🔴 **APP-047 精度定案：FP16**（ASR-033 通知 11:49）
#   依据：`asr067_fp16_vs_fp32_cluster.json` 的 `n_diff_segments=0`
#   （FP16 与 FP32 的**聚类结果 0 段不一致**）＋ 嵌入 RTF 增量在固定
#   T 范围 [100, 2048] 后为 0.033（≤ 0.05）。
#   ⇒ 客户包用 `models/spk` 下的 **FP16 IR**，**不需要 FP32**。
#
# ⚠️ 注意与 ASR-025 §8 的**保真门槛**区分（两件事）：
#   - 保真门槛（余弦 ≥0.999 且相对最大偏差 ≤1e-3）：**FP16 不过**、FP32 过；
#   - **聚类效果**（spk 分得对不对）：ASR-028 的 Q&A 场景实测 FP16 可用
#     （n_speakers=5、段级纯度 0.9147）。
#   ⇒ reviewer 的 APP-047 裁定走的是**聚类口径** ⇒ **FP16**。
#
# 🔴 **仍按「实际存在的目录」探测**（不硬编码）⇒ 若将来补了 FP32 目录，
#   探测顺序会让它自然优先，**代码不必因裁定而改**。
WES_PRECISIONS = ('fp16', 'fp32')
SEG_PRECISIONS = ('fp16', 'fp32')

# 两种精度下的目录名（wespeaker 与 pyannote 的命名不一致，故分开列）
WES_DIR_TMPL = 'wespeaker-resnet34-%s'
SEG_DIR_TMPL = 'pyannote_seg_3_0/%s'

# 各精度下的 IR 文件名
WES_IR_FILES = ('openvino_encoder_model.xml', 'openvino_encoder_model.bin')
SEG_IR_FILES = ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin')

# 🔴🔴🔳 **APP-067 ⑤ / ASR-045：窗口变体的 seg IR（5 s ⇒ `fp16-w5`）**
#
# ## 根因（§133 设备级实测）
#   ASR-045 后内核默认窗口 = **5.0 s**（`WIN_N = 80000`），
#   而 seg IR 的输入是**静态形状**：
#     * `fp16`   ⇒ `(1,1,160000)` ⇒ **只能吃 10 s 窗**
#     * `fp16-w5`⇒ `(1,1,80000)`  ⇒ **只能吃 5 s 窗**
#   ⇒ **喂错长度 ⇒ OpenVINO 抛 shape 不兼容 ⇒ 旁路整个失效（零标签）**。
#
# ## 本模块的 bug
#   旧 `find_seg_ir()` 只按 `SEG_PRECISIONS = ('fp16','fp32')` 找
#   ⇒ **永远找不到 `fp16-w5`** ⇒ 把 **10 s 的 IR** 传给 5 s 窗的内核
#   ⇒ 实测（§133 clone 臂）：
#     log「说话人资产（包内）：… pyannote_seg_3_0 **fp16**」
#     log「说话人旁路窗口：**5.000 s**」
#     ⇒ **窗口与 IR 不配套** ⇒ 零标签 ⇒ 克隆 0 %。
#   ⇒ 现在：**按当前窗口选变体**（与 ASR 侧 `asr_spk_window.seg_ir_subdir_for()`
#     **同一口径**）⇒ 5 s ⇒ `fp16-w5`。
#
# 🔴 **窗口长怎么拿**：优先读**包内** `app/asr_spk/asr_spk_window.py`
#   （ASR-045 的**唯一事实来源**，已随包分发）⇒ **不写第二份默认值**。
#   读不到 ⇒ 退回 `asr052_spk_runtime.WIN_S` ⇒ 都没有 ⇒ `None`
#   （⇒ 不做窗口特化 ⇒ 走旧的 `fp16` 路径 ⇒ 行为与改前一致）。
SEG_WINDOW_VARIANTS = {'fp16-w5'}      # 窗口特化的变体目录名
SEG_VARIANT_FILES = {'fp16-w5': ('pyannote_seg_3_0_w5.xml',
                                 'pyannote_seg_3_0_w5.bin')}

# 研发机上的 ASR 实验目录（**不在 git 仓库内**）⇒ 客户机必然找不到
# 🔴 §120：不再写死开发机家目录 ⇒ 改为按**当前用户家目录**推导
#   （开发机上与原硬编码值**逐字节相同**；客户机上自然指向客户自己的家目录）
DEV_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'),
                               'qwen3asr_06b', 'scripts')


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


def _current_window_s(pkg_root: Optional[str] = None):
    """🔴 **当前旁路窗口长（秒）** —— 从**包内** `asr_spk_window` 读。

    🔴 **不写第二份默认值**（APP-062 D1 / ASR-045 的铁律）：
    唯一事实来源 = 包内 `app/asr_spk/asr_spk_window.py` 的 `WIN_S`
    ⇒ 读不到 ⇒ 退回 `asr052_spk_runtime.WIN_S` ⇒ 都没有 ⇒ `None`
    （⇒ 调用方不做窗口特化 ⇒ 行为与改前**完全一致**）。

    ⚠️ `asr_spk_window` 会 `import os` 并算 `WIN_S`（读环境变量）
    ⇒ 这里**只取常量**，不执行任何模型加载。
    """
    root = pkg_root or PKG_ROOT
    scripts = os.path.join(root, 'app', ASR_SPK_SUBDIR)
    for mod_name in ('asr_spk_window', 'asr052_spk_runtime'):
        p = os.path.join(scripts, mod_name + '.py')
        if not os.path.isfile(p):
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                '_spk_win_probe_%s' % mod_name, p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            v = getattr(mod, 'WIN_S', None)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v), mod_name
        except Exception:
            continue
    return None, None


def find_seg_ir(pkg_root: Optional[str] = None) -> Tuple[Optional[str], str]:
    """定位 pyannote/segmentation-3.0 的 OV IR 目录。

    🔴🔴🔳 **APP-067 ⑤ / ASR-045：必须按「当前窗口」选变体**。

    探测顺序：
      ① **窗口变体**（5 s ⇒ `fp16-w5`）—— 由包内 `asr_spk_window.WIN_S` 决定
      ② `SEG_PRECISIONS`（`fp16` / `fp32`）—— 旧行为（10 s 窗的现役 IR）

    ⚠️ ① 命中时**必须用变体自己的文件名**（`pyannote_seg_3_0_w5.*`）
    ⇒ 变体目录里的文件名与 `fp16` 目录**不同**。
    """
    spk_root = find_spk_model_root(pkg_root)
    if not spk_root:
        return None, '包内无 models/%s 目录' % SPK_MODELS_SUBDIR
    # ── ① 窗口变体（ASR-045）──────────────────────────────────
    win_s, win_src = _current_window_s(pkg_root)
    if win_s is not None:
        try:
            import asr_spk_window as _W     # 已在 sys.path 时直接问它
            sub = _W.seg_ir_subdir_for(win_s)
        except Exception:
            sub = 'fp16-w5' if abs(win_s - 5.0) < 1e-9 else 'fp16'
        if sub in SEG_WINDOW_VARIANTS:
            d = os.path.join(spk_root, SEG_DIR_TMPL % sub)
            names = SEG_VARIANT_FILES.get(sub, SEG_IR_FILES)
            if _has_pair(d, names):
                return d, ('pyannote_seg_3_0 %s（窗口 %.3f s，来源 %s）'
                           % (sub, win_s, win_src))
    # ── ② 旧路径（10 s 窗的现役 IR）──────────────────────────
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
