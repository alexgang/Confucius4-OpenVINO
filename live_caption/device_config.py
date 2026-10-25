"""推理设备选择（ASR / MT / TTS 三个模型各自独立）。

APP-004 第 3 条：三个模型的推理设备都让用户自己选。

设计要点
--------
1. **可选项来自实际检测**：用 ``ov.Core().available_devices`` 探测，
   检测不到的设备**不显示**在界面上。
2. **默认值用各模块的推荐配置**（不是硬编码到代码里，而是集中在这里，
   便于 reviewer 一处核对）。
3. **不可用组合给明确提示并回退默认**：用户选了一个本机没有的设备，
   或选了设备但该档位不支持（例如 NPU 只支持 f16/i8），
   都要提示 + 回退，**不能卡死**。
4. **选择保存到 %LOCALAPPDATA% 配置文件，下次启动恢复**。

⚠️ 已知设备铁律（改这里时不要违反）：
- **NPU 只支持 f16/i8**（``INFERENCE_PRECISION_HINT=f32`` 会被拒）。
- **NPU 上必须「按需加载」IR**：无条件编 4 个 ⇒
  ``Concat ... doesn't fit to output dimension``。
- **声码器在 iGPU 上是负加速 0.42~0.64× 且 SNR 仅 21 dB**
  ⇒ GPU.0 档的声码器必须留 CPU。
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

# ── 配置目录（与 live_caption_app.py::_cache 同一套规则）───────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _config_dir() -> str:
    """用户配置目录。

    优先 ``%LOCALAPPDATA%\\Confucius4LiveCaption``；
    不可写时回落 ``APP_DIR``（只读安装盘也不崩）。
    """
    base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'Confucius4LiveCaption')
    try:
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return d
    except Exception:
        pass
    return APP_DIR


CONFIG_DIR = _config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, 'device_config.json')

# ── 三个模型的默认摆放（各模块 reviewer 推荐的配置）────────────────────
# ASR：GPU.0（集显）。NPU 全 INT8 也能跑但会与 MT/TTS 争用。
# MT：GPU.0（INT8-CW 在集显上 37.5 tok/s，实时够用）。
# TTS：NPU（交接单 §1.1 推荐，RTF 1.04 / 首包 0.67 s）。
DEFAULT_DEVICES: Dict[str, str] = {
    'asr': 'GPU.0',
    'mt': 'GPU.0',
    'tts': 'NPU',
}

# 兜底候选（用户选的设备本机不存在时，依次尝试）
FALLBACK_ORDER: Dict[str, List[str]] = {
    'asr': ['GPU.0', 'NPU', 'CPU'],
    'mt': ['GPU.0', 'NPU', 'CPU'],
    'tts': ['NPU', 'GPU.0', 'CPU'],
}

# ── 设备能力约束 ──────────────────────────────────────────────────────
# NPU 只支持 f16/i8 ⇒ f32 精度在这些设备上会被 OV 直接拒。
PRECISION_UNSUPPORTED: Dict[str, Tuple[str, ...]] = {
    'NPU': ('f32',),
}

# 设备显示名（GUI 下拉框用）
# 🔴🔴 **不要在这里硬编码「GPU.N 是 Intel 集显」**！
#    OpenVINO 的 ``GPU.N`` 编号**不代表厂商**：OV 会把本机所有 GPU 依次编号，
#    本机实测（2026-10-25）::
#
#        GPU.0 = Intel(R) Graphics (iGPU)      ← Intel 集显
#        GPU.1 = NVIDIA GeForce RTX 5050 (dGPU) ← NVIDIA 独显
#
#    ⇒ 把 GPU.1 标成「Intel GPU 2」是**错的**（用户报「设备里出现了不存在的
#    Intel GPU 2」）。**唯一可靠的来源是 ``FULL_DEVICE_NAME``**。
#    ⇒ 见 ``device_label()``：能查到全名就据实生成标签，查不到才回落这里。
_DEVICE_LABELS = {
    'GPU.0': 'Intel GPU（集显）',
    'NPU': 'Intel NPU',
    'CPU': 'CPU（不推荐）',
}

# 全名里的厂商关键字 -> 简洁显示名（用于「Intel GPU（集显）」这种友好文案）
_VENDOR_HINTS = (
    ('nvidia', 'NVIDIA'),
    ('intel', 'Intel'),
    ('amd', 'AMD'),
    ('radeon', 'AMD'),
)

# ── 不进入「可选设备清单」的设备 ─────────────────────────────────────
# 🔴 **CPU 从清单里移除**（用户决定 2026-10-23）。
#    理由：CPU 在本项目的 Intel 平台上**是负加速**（声码器在 iGPU 上
#    0.42~0.64× 且 SNR 仅 21 dB；CPU 推理整体也比集显慢一个量级），
#    列出来只会诱导用户误选。CPU 只保留作**兜底**
#    （``resolve_device`` 找不到任何可用设备时回退到它）。
EXCLUDED_DEVICES = frozenset({'CPU'})


def is_excluded_device(dev: str) -> bool:
    """该设备是否**不进入可选清单**（目前只有 CPU）。

    大小写不敏感（OV 有时给 'cpu'）。
    """
    return (dev or '').strip().upper() in EXCLUDED_DEVICES


def device_label(dev: str) -> str:
    """设备名 -> 界面显示文本。

    🔴🔴 **按实际硬件生成，不按编号猜**（2026-10-25 用户报「设备里出现了
    不存在的 Intel GPU 2」）。

    优先级：
    1. 查 ``FULL_DEVICE_NAME``（OpenVINO 报的真实硬件名）⇒ 据实生成：
       - 名字里含 NVIDIA ⇒ 「NVIDIA 独显（RTX 5050 Laptop GPU）」之类的简称；
       - 名字里含 Intel + Graphics ⇒ 「Intel GPU（集显）」；
       - 名字里含 Intel + AI Boost ⇒ 「Intel NPU」；
    2. 查不到全名（OV 不可用 / 设备已拔出）⇒ 回落 ``_DEVICE_LABELS``；
    3. 都不��� ⇒ 原样返回设备名（**绝不编造「Intel GPU 2」这种不存在的设备**）。

    ⚠️ 标签必须**全局唯一**（GUI 靠 label 反查设备，见 live_caption_app.py
       的 ``_dev_label_back``）⇒ 含厂商的标签天然比「GPU.1」更不容易撞。
    """
    if not dev:
        return '（未指定）'

    full = _full_device_name(dev)
    if full:
        label = _label_from_full_name(full)
        if label:
            return label

    # 回落：静态表（**不含任何猜测编号的 GPU 标签**）
    return _DEVICE_LABELS.get(dev, dev)


_FULL_NAME_CACHE: Dict[str, str] = {}


def _full_device_name(dev: str) -> str:
    """取设备的 ``FULL_DEVICE_NAME``（失败返回空串）。

    🔴 结果**进程内缓存**（设备不会运行时插拔）⇒ 避免每次建 GUI 都新建
       ``ov.Core()``。
    """
    if dev in _FULL_NAME_CACHE:
        return _FULL_NAME_CACHE[dev]
    name = ''
    try:
        import openvino as ov
        core = ov.Core()
        if dev in core.available_devices:
            name = core.get_property(dev, 'FULL_DEVICE_NAME') or ''
    except Exception:
        name = ''
    _FULL_NAME_CACHE[dev] = name
    return name


def _label_from_full_name(full: str) -> str:
    """把 ``FULL_DEVICE_NAME`` 变成简洁的界面标签。

    例：
      「NVIDIA GeForce RTX 5050 Laptop GPU」→ 「NVIDIA 独显（RTX 5050 Laptop GPU）」
      「Intel(R) Graphics (iGPU)」           → 「Intel GPU（集显）」
      「Intel(R) AI Boost」                  → 「Intel NPU」
      「Intel(R) Core(TM) Ultra 7 356H」    → ''（CPU 不在清单里）
    """
    low = full.lower()
    if 'nvidia' in low or 'geforce' in low or 'rtx' in low:
        # NVIDIA 独显：抽出具体型号（去掉厂商前缀与括号噪声）
        model = full
        for pre in ('NVIDIA GeForce ', 'NVIDIA ', 'nvidia '):
            if model.lower().startswith(pre.lower()):
                model = model[len(pre):]
                break
        # 去掉 "(dGPU)" 这类后缀噪声 + 归一空白
        model = re.sub(r'\((?:dGPU|iGPU|discrete|integrated)\)', '', model,
                       flags=re.I).strip()
        model = re.sub(r'\s+', ' ', model).strip(' ()')
        return f'NVIDIA 独显（{model}）' if model else 'NVIDIA 独显'
    if 'intel' in low and ('graphics' in low or 'iris' in low or 'uhd' in low):
        return 'Intel GPU（集显）'
    if 'intel' in low and ('ai boost' in low or 'npu' in low):
        return 'Intel NPU'
    if 'amd' in low or 'radeon' in low:
        return 'AMD 独显' if 'radeon rx' in low or 'radeon pro' in low else 'AMD GPU'
    return ''


# ── NVIDIA / CUDA 设备识别 ───────────────────────────────────────────
# 🔴🔴 **实测结论（2026-10-25，OV 2026.4.1）**：
#   本机 ``available_devices`` = ['CPU', 'GPU.0', 'GPU.1', 'NPU']，
#   其中 ``GPU.1`` 的 FULL_DEVICE_NAME = 「NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)」
#   ⇒ **GPU.N 编号不代表厂商**（OV 把所有 GPU 依次编号）。
#
#   但 ⚠️ **OV 主包里并没有 CUDA plugin 组件**
#   （实测 ``openvino`` 包内 `*cuda*` 匹配数 = 0）
#   ⇒ OV 2026.4 对 NVIDIA 独显**仍然走 Intel GPU plugin**（经 Level Zero），
#      **不是**真正的 CUDA 后端。
#
#   ⇒ 后果（实测 TTS 真实 IR 逐个编译）：
#      GPU.0（Intel 集显）  : 7/7 编译成功
#      GPU.1（NVIDIA 独显） : 3/7 编译成功（4 个在 FP16↔FP32 reorder 节点上
#                            「Could not find a suitable kernel」）
CUDA_DEVICE_HINTS = ('nvidia', 'geforce', 'rtx', 'cuda', 'quadro', 'tesla')


def is_cuda_device(dev: str) -> bool:
    """该设备是否是 **NVIDIA / CUDA** 设备（据 FULL_DEVICE_NAME 判定）。"""
    full = _full_device_name(dev).lower()
    if not full:
        return False
    return any(h in full for h in CUDA_DEVICE_HINTS)


def has_cuda_plugin() -> bool:
    """OpenVINO 是否**真的**带 CUDA plugin（而不是借 Intel GPU plugin 驱动 NVIDIA）。

    判定：``openvino`` 包目录里存在含 ``cuda`` 的组件文件。
    ⇒ False ⇒ ``GPU.N`` 即使是 NVIDIA 硬件，也**不能**按 CUDA 后端用。
    """
    try:
        import openvino
        base = os.path.dirname(os.path.abspath(openvino.__file__))
        for root, _dirs, files in os.walk(base):
            for fn in files:
                low = fn.lower()
                if 'cuda' in low and low.endswith(('.dll', '.so', '.pyd', '.exe')):
                    return True
            # 只扫一层子目录，避免全量 walk 太慢
            break
        return False
    except Exception:
        return False


def detect_devices() -> Dict[str, str]:
    """探测本机 OpenVINO 可用设备。

    返回 ``{设备名: 全名}``；OpenVINO 不可用时返回**空字典**（不抛异常）。

    🔴 **CPU 已从设备清单中移除**（用户决定，2026-10-23）：
       CPU 只作**兜底**存在（见 ``resolve_device``），**不作为可选设备**
       出现在 GUI / CLI 的设备清单里 —— 它在集显/NPU 上是负加速
       （声码器在 iGPU 上 0.42~0.64× 且 SNR 仅 21 dB），列出来只会诱导
       用户误选。
    """
    try:
        import openvino as ov
        core = ov.Core()
        out: Dict[str, str] = {}
        for d in core.available_devices:
            if is_excluded_device(d):
                continue
            try:
                out[d] = core.get_property(d, 'FULL_DEVICE_NAME')
            except Exception:
                out[d] = d
        return out
    except Exception:
        return {}


def available_devices() -> List[str]:
    """本机实际可用的推理设备列表（**不含 CPU**）。

    🔴 CPU 不在清单里（用户决定 2026-10-23）⇒ 本机只有 CPU 时
       这里返回**空列表**。GUI 会据此在下拉里给明确提示，而不是
       让用户在一个没有意义的选项里瞎选。
    """
    devs = detect_devices()
    if not devs:
        return []
    # 顺序：NPU → GPU（高性能在前），其余按名字
    def _key(d: str):
        if d.upper() == 'NPU':
            return (0, d)
        if d.upper().startswith('GPU'):
            return (1, d)
        return (2, d)
    return sorted(devs.keys(), key=_key)


def check_precision(device: str, precision: str) -> Optional[str]:
    """检查设备是否支持该精度。

    返回**错误说明**（None = 支持）。
    """
    bad = PRECISION_UNSUPPORTED.get((device or '').upper(), ())
    if precision in bad:
        return (f'设备 {device} 不支持 {precision} 精度'
                f'（只支持 {" / ".join(x for x in ("f16", "i8", "int8") if x not in bad)}）')
    return None


def resolve_device(role: str, wanted: Optional[str],
                   avail: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    """把「用户想要」解析成「本机可用」。

    返回 ``(最终设备, 提示信息)``：
    - 提示为 None ⇒ 一切正常，直接用最终设备；
    - 提示非 None ⇒ **已经回退**，提示应展示给用户。

    ⚠️ 绝不能因为设备不可用就返回空/卡死 —— 一定有兜底设备。
    """
    if avail is None:
        avail = available_devices()
    if not avail:
        # 🔴 本机只有 CPU（或 OV 不可用）⇒ 清单为空（CPU 已从清单移除）
        #    ⇒ 直接回退到 CPU 兜底，**不能卡死**。
        return 'CPU', '本机未检测到 GPU/NPU，已回退到 CPU 推理'

    def _pick(pref: str) -> Optional[str]:
        if pref in avail:
            return pref
        up = pref.upper()
        for d in avail:
            if d.upper() == up:
                return d
        return None

    if wanted:
        got = _pick(wanted)
        if got:
            return got, None
        # ⚠️ 用户**显式指定了 CPU** ⇒ 尊重用户选择（CLI 场景），
        #    不因为 CPU 不在清单里就否掉。
        if (wanted or '').strip().upper() == 'CPU':
            return 'CPU', None
        msg = f'本机没有设备「{wanted}」，已回退到默认设备'
    else:
        msg = None

    # 回退：先按本模块推荐，再按 FALLBACK_ORDER，最后 CPU
    pref = DEFAULT_DEVICES.get(role, 'CPU')
    got = _pick(pref)
    if got:
        return got, msg
    for c in FALLBACK_ORDER.get(role, []):
        if c.upper() == 'CPU':
            continue                   # CPU 不在清单里 ⇒ 跳过这一档
        got = _pick(c)
        if got:
            return got, msg or f'已回退到设备「{got}」'
    return 'CPU', msg or '已回退到 CPU'


# ── 配置持久化 ────────────────────────────────────────────────────────
def load_config() -> Dict[str, str]:
    """读 ``device_config.json``；损坏/不存在时返回空字典。"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict):
            return {k: v for k, v in d.items() if isinstance(v, str)}
    except Exception:
        pass
    return {}


def save_config(devices: Dict[str, str]) -> bool:
    """写 ``device_config.json``。返回是否成功。

    ⚠️ 写失败（只读目录/权限）**不能抛异常** —— 设备选择只是偏好，
    存不下来最多下次要重选，不该让 App 起不来。
    """
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
        return True
    except Exception:
        return False


def get_devices(cli_overrides: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, str], List[str]]:
    """算出本次启动三个模型实际用的设备。

    优先级：**命令行 > 配置文件 > 推荐默认值**。

    返回 ``(设备字典, 提示列表)``；提示非空表示发生过回退，
    应展示给用户。
    """
    saved = load_config()
    cli = cli_overrides or {}
    avail = available_devices()
    out: Dict[str, str] = {}
    notes: List[str] = []
    for role in ('asr', 'mt', 'tts'):
        wanted = cli.get(role) or saved.get(role) or DEFAULT_DEVICES.get(role)
        dev, note = resolve_device(role, wanted, avail)
        out[role] = dev
        if note:
            notes.append(f'{role.upper()}：{note}')
    return out, notes


if __name__ == '__main__':
    import sys
    print('可用设备：', available_devices())
    print('默认摆放：', DEFAULT_DEVICES)
    print('配置目录：', CONFIG_DIR)
    print('配置文件：', CONFIG_PATH)
    d, n = get_devices()
    print('解析结果：', d)
    if n:
        print('提示：', n)
    if '--save' in sys.argv:
        print('已保存：', save_config(d))
