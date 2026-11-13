r"""package_profile.py — **包形态标记**（MiniMVP / 完整版）的**唯一事实来源**。

## 为什么要有这个模块（APP-098 一.1／一.3）

APP-098 要求：
- 三个后端**都去掉所有 NVIDIA/CUDA 选项**；
- 克隆音色在 GUI 上**置灰**（MiniMVP 不提供音色克隆）；
- **「MiniMVP 和 v2.5 共用的部分只改一处」**。

⇒ 这三条的**代码**必须**只写一份**（在开发树 `live_caption/` 里），
   否则 MiniMVP 与 v2.5 就会各有一份副本 ⇒ 以后改一处漏一处。

⇒ 解决办法：**代码是同一份**（都在开发树），**差异由包内的一个标记文件驱动**。
   本模块负责读那个标记，并把结果暴露成**布尔/常量**给其它模块用。

## 标记文件：`package_profile.json`（放在**包根**，即 `app/` 的上一级）

```json
{
  "profile": "minimvp",
  "allow_cuda": false,
  "allow_clone_voice": false,
  "target_langs": 10
}
```

🔴 **为什么放包根而不是 `app/`**：
- `app/` 下的文件是**代码**，会被同步脚本逐个改写 ⇒ 标记放那里容易被覆盖；
- 包根是**包的属性**（跟 `release.json`、`README` 同级）⇒ 天然属于「包」而不是「代码」。

🔴 **缺标记时怎么办**：
- 完整版客户包（v2.5）**不需要**这个文件 ⇒ 默认行为就是「完整版」；
- 开发树（`live_caption/` 的上一级是仓库根）**没有**这个文件 ⇒ 也走默认分支；
⇒ ⇒ **只有 MiniMVP 包才带这个文件** ⇒ 其它包零影响。

## 🔴 三态而不是两态

`profile` 的取值：
- `'minimvp'`   ⇒ MiniMVP：禁 CUDA、禁克隆音色；
- `'full'`      ⇒ 完整版：全功能；
- **`None`**    ⇒ **没有标记文件** ⇒ 按 `'full'` 处理（**不是**「未知 ⇒ 猜测」）。

⇒ 「文件不存在」与「文件里写了 full」是**同一件事** ⇒ 只有一个 bool 出口，
   调用方不需要区分「为什么」。
"""

import json
import os

#: 包根 = 本文件所在目录的上一级（`app/package_profile.py` ⇒ `<包根>/app/` ⇒ 包根）。
#: 🔴 开发树里本文件在 `live_caption/` ⇒ 包根 = 仓库根 ⇒ 仓库根没有标记文件
#    ⇒ 默认 'full' ⇒ 开发树行为**完全不变**（老规矩）。
PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 标记文件名（**唯一**）。
PROFILE_FILE = 'package_profile.json'

#: 🔴 允许的 profile 取值（**白名单**）——不在白名单里的一律当 'full'。
#:    理由：标记文件写错时**绝不能**把完整版降级成 MiniMVP（那是「静默改行为」）。
#: 🔴🔴🔳 **'specialmvp'**（用户 2026-11-13 决定）：**Special MVP** ——
#:    **包内自带 NV5050 的 PyTorch+CUDA 环境** ⇒ TTS 走**真 CUDA**，
#:    ASR 走 iGPU（GPU.0）、MT 走 NPU（Hy-MT2）。
KNOWN_PROFILES = ('minimvp', 'full', 'specialmvp')


def _read_marker():
    """读包根的标记文件；读不到/坏了 ⇒ 返回 ``{}``（**不猜、不抛**）。"""
    try:
        p = os.path.join(PKG_ROOT, PROFILE_FILE)
        if not os.path.isfile(p):
            return {}
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        # 🔴 **坏标记不许让程序起不来** ⇒ 回落成「无标记」⇒ 按 full 处理。
        return {}


_MARKER = _read_marker()

#: 🔴 **唯一事实来源**：包形态。取值见 ``KNOWN_PROFILES``。
PROFILE = str(_MARKER.get('profile') or 'full').strip().lower()
if PROFILE not in KNOWN_PROFILES:
    # 🔴 未知取值 ⇒ 保守回落成 'full'（**不降级**）⇒ 并在 stderr 留痕。
    PROFILE = 'full'
    try:
        import sys
        sys.stderr.write(
            '[profile] ⚠️ package_profile.json 的 profile=%r 不在 %s ⇒ '
            '按 full 处理\n' % (_MARKER.get('profile'), list(KNOWN_PROFILES)))
    except Exception:
        pass


def is_minimvp() -> bool:
    """本包是不是 **MiniMVP**。"""
    return PROFILE == 'minimvp'


def is_specialmvp() -> bool:
    """本包是不是 **Special MVP**（NV5050 CUDA TTS 专供包）。

    🔴🔴🔳 用户 2026-11-13 决定：**包内自带 NV5050 的 PyTorch+CUDA 环境**
    ⇒ TTS 用**真 CUDA** 推理；ASR 用 iGPU（GPU.0）、MT 用 NPU（Hy-MT2）。
    """
    return PROFILE == 'specialmvp'


def allow_cuda() -> bool:
    """本包**是否允许** NVIDIA/CUDA 后端。

    🔴 **默认 False**（不靠标记文件也能满足 APP-098 一.1）：
    完整版客户包**也不带** CUDA 资产（audio.cpp + GGUF 不随包分发，
    见 APP-062 ③ D3「客户包里去掉 TTS=CUDA」）⇒ 完整版同样不该出现 CUDA 选项。
    ⇒ **默认 False** 是对两个包都正确的默认值。

    🔴🔴🔳 **Special MVP 例外**（用户 2026-11-13 决定）：本包**自带**
    CUDA 运行时（`cuda_env/`）⇒ CUDA 档**是本包的出厂 TTS 后端**。
    """
    if is_minimvp():
        return False
    if is_specialmvp():
        return bool(_MARKER.get('allow_cuda', True))
    return bool(_MARKER.get('allow_cuda', False))


def allow_clone_voice() -> bool:
    """本包**是否提供**音色克隆（follow_speaker）。

    🔴 MiniMVP ⇒ False（APP-098 一.3：「MiniMVP 不提供音色克隆」）。
    🔴 完整版 ⇒ True（APP-039/040/089 的克隆能力**必须保留**）。
    ⇒ 这里是**两个包真的不同**的一处 ⇒ **靠标记文件区分**（而不是复制代码）。
    """
    if is_minimvp():
        return False
    return bool(_MARKER.get('allow_clone_voice', True))


def clone_voice_unavailable_reason() -> str:
    """克隆音色不可用的原因（给 GUI 置灰项显示）。"""
    if is_minimvp():
        return 'MiniMVP 不提供音色克隆'
    return '本包不提供音色克隆'


def target_lang_count() -> int:
    """目标语言种数（供 GUI/CLI 自检用）。"""
    try:
        return int(_MARKER.get('target_langs', 10))
    except Exception:
        return 10


def describe() -> dict:
    """本包的形态摘要（落盘到验收 json 里用）。"""
    return {
        'profile': PROFILE,
        'is_minimvp': is_minimvp(),
        'allow_cuda': allow_cuda(),
        'allow_clone_voice': allow_clone_voice(),
        'target_langs': target_lang_count(),
        'marker_file': PROFILE_FILE,
        'marker_present': bool(_MARKER),
        'pkg_root': PKG_ROOT,
    }


if __name__ == '__main__':
    import json as _json
    print(_json.dumps(describe(), ensure_ascii=False, indent=1))
