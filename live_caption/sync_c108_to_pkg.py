r"""sync_c108_to_pkg.py — 把 C-108（Qwen3 方案 + 空段守卫）移植到客户包 v1.3

做法与前序（C-105/C-106）一致：**精确字符串替换 + assert 唯一命中**，
避免误伤客户包里可能存在的差异。

改动三处：
  1. 常量区：`SILENCE_CUT_SEC` 1.2 → 0.8（Qwen3 默认 silence_duration_ms）
     + 新增空段守卫常量 `SEG_SPEECH_FRAME_DB` / `SEG_MIN_SPEECH_RUN_MS`
  2. `Segmenter.due()`：切段前加空段守卫
  3. `Segmenter._has_speech()`：新增方法

用法：
  python sync_c108_to_pkg.py <pkg_app_dir>
"""

from __future__ import annotations

import os
import sys


OLD_CONST = """# 静音超时切段（解决「说完话迟迟不定稿」/ cut on silence timeout）
# 段尾连续静音多久就切段定稿。
SILENCE_CUT_SEC = float(os.environ.get('LIVECAP_SILENCE_CUT_SEC', '1.2'))
# 保护期：段尾这么多秒内的静音不算「说话结束」（开头爆破音会被误判）。
SILENCE_TAIL_GUARD_SEC = float(os.environ.get('LIVECAP_SILENCE_GUARD_SEC', '0.35'))
# 静音判定阈值（dBFS），与 seg_stream.find_silence_in_range 的默认值一致。
SILENCE_DB = -40.0
"""

NEW_CONST = """# 静音超时切段（解决「说完话迟迟不定稿」/ cut on silence timeout）
# 段尾连续静音多久就切段定稿。
#
# ★ C-108：按 Qwen3-ASR-Flash-Realtime 的 `session.turn_detection.silence_duration_ms`
#   改造。Qwen3 官方取值：**默认 800ms，范围 [200, 6000]**，
#   并明确「对话和聊天等需快速断句的场景推荐设为 400」。
#   本项目 = 实时字幕 App，取 **800ms**（Qwen3 默认值），理由：
#     * 离线实测（61 分钟真实演讲）800ms 时规则2 从 17 段 → 37 段，
#       **新增的切点 100% 落在词间隙**（0 危险）；
#     * 700ms 起开始出现危险切点，800ms 正好是「收益最大 + 零危险」的上沿。
SILENCE_CUT_SEC = float(os.environ.get('LIVECAP_SILENCE_CUT_SEC', '0.8'))
# 保护期：段尾这么多秒内的静音不算「说话结束」（开头爆破音会被误判）。
SILENCE_TAIL_GUARD_SEC = float(os.environ.get('LIVECAP_SILENCE_GUARD_SEC', '0.35'))
# 静音判定阈值（dBFS），与 seg_stream.find_silence_in_range 的默认值一致。
#
# 对应 Qwen3 的 `session.turn_detection.threshold`（VAD 灵敏度，默认 0.5，
# 范围 [-1, 1]）。⚠️ 二者量纲不同：Qwen3 是**概率**阈值，本项目是**能量 dB**，
# 不能直接换算。-40dB 是本项目全链路实测的基准值，保持不变。
SILENCE_DB = -40.0

# ── 空段守卫（C-108）────────────────────────────────────────────
# 切段前要求段内确实有**成段的连续语音**，否则不切。
#
# 为什么需要：把 hangover 从 1.2s 降到 0.4s 后，空段从 1 个涨到 11 个。
#   典型空段 [41.60, 42.88]：帧 dB max=-36.3 / p90=-44.0，
#   尾静音起点前 0.35s 的 probe=-42.5dB（绝对判据 -40dB 拦下），
#   但相对判据的「段内语音电平 p90」被**噪声突发**拉高到 -40 以上，
#   导致准入门槛误放行 → 切出一个纯静音段。
#
# 判别特征**不是能量电平，而是「有没有成段的连续语音」**：
#   合法段连续语音可达数百毫秒以上；空段只有零星噪声突发。
#
# 离线实测（61 分钟真实演讲）：守卫打开后空段 → **0**，且不损失任何安全切点。
SEG_SPEECH_FRAME_DB = -35.0
SEG_MIN_SPEECH_RUN_MS = int(os.environ.get('LIVECAP_MIN_SPEECH_RUN_MS', '200'))
"""


OLD_DUE = """    def due(self, acc):
        n = acc.shape[0]
        dur = n / SR
        if dur >= MAX_SEG_SEC:
            return True
        # 规则 2：静音超时（优先判定，短段靠它出定稿）
        if self._silence_tail(acc):
            return True
        # 规则 1：常规规则
        if dur < MIN_SEG_SEC:
            return False
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        return self._find(acc, start_sample=start, end_sample=n,
                          silence_db=-40.0, min_silence_ms=300) is not None
"""

NEW_DUE = """    def due(self, acc):
        n = acc.shape[0]
        dur = n / SR
        if dur >= MAX_SEG_SEC:
            return True
        # 空段守卫（C-108）：段内必须有成段的连续语音才允许切段。
        # 放在最前面统一把关 —— 规则1/规则2 都可能切出纯静音段。
        if not self._has_speech(acc):
            return False
        # 规则 2：静音超时（优先判定，短段靠它出定稿）
        if self._silence_tail(acc):
            return True
        # 规则 1：常规规则
        if dur < MIN_SEG_SEC:
            return False
        start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
        return self._find(acc, start_sample=start, end_sample=n,
                          silence_db=-40.0, min_silence_ms=300) is not None

    def _has_speech(self, acc):
        \"\"\"段内是否存在「成段的连续语音」（C-108 空段守卫）。

        判据：30ms 帧能量连续 ≥ ``SEG_MIN_SPEECH_RUN_MS``(200ms) 的帧
        都高于 ``SEG_SPEECH_FRAME_DB``(-35dB)。

        为什么要连续而不是看电平：单个噪声突发（9 帧连续 -36dB）就能把
        「段内 p90 电平」拉到 -40dB 以上，让基于电平的判据误放行；
        而真正的语音必然连续上百毫秒以上。
        \"\"\"
        if SEG_MIN_SPEECH_RUN_MS <= 0:
            return True
        f = _frame_db_series(acc)
        if f.size == 0:
            return False
        need = max(1, SEG_MIN_SPEECH_RUN_MS // 10)   # hop 10ms
        run = 0
        for v in f:
            if v > SEG_SPEECH_FRAME_DB:
                run += 1
                if run >= need:
                    return True
            else:
                run = 0
        return False
"""


def main():
    app_dir = sys.argv[1] if len(sys.argv) > 1 else \
        r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'
    path = os.path.join(app_dir, 'live_caption_app.py')

    with open(path, encoding='utf-8') as f:
        src = f.read()

    for old, new, name in ((OLD_CONST, NEW_CONST, '常量区'),
                           (OLD_DUE, NEW_DUE, 'due() + _has_speech()')):
        cnt = src.count(old)
        assert cnt == 1, f'{name}: 期望唯一命中，实际 {cnt} 次'
        src = src.replace(old, new)
        print(f'  ✔ {name} 移植完成')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'→ 已写入 {path}')

    # 语法检查
    import py_compile
    py_compile.compile(path, doraise=True)
    print('  ✔ 语法检查通过')


if __name__ == '__main__':
    main()
