r"""sync_c109_to_pkg.py — 把 C-109（MIN_SEG_SEC 12s → 6s）移植到客户包 v1.3

做法与 C-105/C-106/C-108 一致：**精确字符串替换 + assert 唯一命中**。

改动两处：
  1. 常量区：`MIN_SEG_SEC = 12.0` → `6.0`（带 env 开关 + 说明注释）
  2. `Segmenter` 文档字符串：12s → 6s 的描述

用法：
  python sync_c109_to_pkg.py <pkg_app_dir>
"""

from __future__ import annotations

import os
import sys


OLD_CONST = """CHUNK_SEC = 0.64
MIN_SEG_SEC = 12.0
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0
"""

NEW_CONST = """CHUNK_SEC = 0.64

# 规则1 的最短段门槛（计时器兜底）：段长 ≥ MIN_SEG_SEC 且最近 SIL_LOOKBACK_SEC
# 内有 ≥300ms 静音就切段。
#
# ★ C-109：由 12.0s 降到 **6.0s**（用户决策）。
#   背景：12s 门槛是「等满 12 秒才定稿」的计时器兜底，实测它切出了 **94.2%**
#   的段 —— 引擎基本没在做「按停顿切」，白字要等满 12 秒。
#   C-108 已把规则2 的 hangover 降到 0.8s（Qwen3 默认值），规则2 切点
#   29/29 全安全；但素材是连续演讲（≥800ms 停顿仅 1.9 处/分钟），
#   规则2 能切的点有限 → 降规则1 的门槛才能真正提早白字。
#
#   离线实测（61 分钟真实演讲，含空段守卫）：
#     门槛 12s → 300 段，段长 p50=12.16s，其中 **198 段恰好 12.16s**
#                （全是「等满 12 秒」），白字提前中位 0.64s
#     门槛  6s → 532 段，段长 p50= 6.40s，恰好 12.16s 的只剩 **2 段**
#                （计时器兜底基本被消除），白字提前中位 5.12s
#   规则2 切点 23/23 全安全、空段 0、短段(<2s) 仅 2 段。
#
#   代价：段数 300 → 532（+77%），每次切段都要跑一次收尾解码
#   （实测 428ms/次：编码 68 + prefill 108 + 解码 252），
#   61 分钟累计收尾开销 128s → 228s（+100s）。
MIN_SEG_SEC = float(os.environ.get('LIVECAP_MIN_SEG_SEC', '6.0'))
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0
"""


OLD_DOC = """    1. **常规规则**（原 mic_asr_app 的做法）：段长 ≥ ``MIN_SEG_SEC``(12 s)
       且最近 ``SIL_LOOKBACK_SEC``(3 s) 内有 ≥300 ms 静音；段长 ≥
       ``MAX_SEG_SEC``(20 s) 硬切。
"""

NEW_DOC = """    1. **常规规则**（原 mic_asr_app 的做法）：段长 ≥ ``MIN_SEG_SEC``(6 s)
       且最近 ``SIL_LOOKBACK_SEC``(3 s) 内有 ≥300 ms 静音；段长 ≥
       ``MAX_SEG_SEC``(20 s) 硬切。

    ★ C-109：``MIN_SEG_SEC`` 由 12s 降到 **6s**。
       12s 门槛是「等满 12 秒才定稿」的计时器兜底，实测它切出了 **94.2%**
       的段 —— 引擎基本没在做「按停顿切」，白字要等满 12 秒。
       降到 6s 后（61 分钟真实演讲）：段长 p50 12.16s → **6.40s**，
       恰好 12.16s 的段 198 → **2**（计时器兜底基本被消除），
       白字提前中位 0.64s → **5.12s**，规则2 切点仍 23/23 全安全、空段 0。
"""


def main():
    app_dir = sys.argv[1] if len(sys.argv) > 1 else \
        r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'
    path = os.path.join(app_dir, 'live_caption_app.py')

    with open(path, encoding='utf-8') as f:
        src = f.read()

    for old, new, name in ((OLD_CONST, NEW_CONST, '常量区 MIN_SEG_SEC'),
                           (OLD_DOC, NEW_DOC, 'Segmenter 文档字符串')):
        cnt = src.count(old)
        assert cnt == 1, f'{name}: 期望唯一命中，实际 {cnt} 次'
        src = src.replace(old, new)
        print(f'  ✔ {name} 移植完成')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'→ 已写入 {path}')

    import py_compile
    py_compile.compile(path, doraise=True)
    print('  ✔ 语法检查通过')


if __name__ == '__main__':
    main()
