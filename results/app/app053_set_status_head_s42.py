#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-053：把 `status/app/STATUS_APP.md` 的**头部**改写到 §42。

🔴 纪律（MEMORY 铁律）：
  - **只改 4 个字段行**（`last_ack` / `更新时间` / `当前任务` / `阻塞`）+ `## 最近更新` 块；
  - **不动正文任何章节**（新章节由人工追加在末尾）；
  - `newline=''` 读写 ⇒ **保持纯 LF**，不引入 CRLF；
  - **幂等**：重复跑结果一致；
  - 「最近更新」≤ 15 行，且**头部「阻塞」必须与最新章节一致**。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.normpath(os.path.join(HERE, '..', '..', 'status', 'app',
                                       'STATUS_APP.md'))

FIELDS = {
    'last_ack': 'APP-017',
    '更新时间': '2026-10-25 22:32',
    '当前任务': (
        '**§42 用户反馈「全流程 CUDA/NPU 都没声音」⇒ 两个产品级真因已修**：'
        '① `device_config.resolve_device` 把 `CUDA` **静默降级成 NPU**'
        '（`_pick(\'CUDA\')` 在 OV 设备清单里找不到 ⇒ 回退默认；改 12 行，'
        '修后 `--tts-device CUDA` **真跑 CUDA**：边车就绪 40.3 s / 首包 4.13 s / 播完 1 丢弃 0）；'
        '② 🔴🔴 **GUI「语音输出 → 输出设备」传的是 WASAPI 端点 id**'
        '（`soundcard` 的 `s.id` = `IMMDevice::GetId()` = `{0.0.0.…}.{guid}`），'
        '而 `sounddevice` 只认 **int 索引或设备名子串** ⇒ '
        '`ValueError: No output device matching` ⇒ `Player._stream=None` ⇒ '
        '**每句都被丢 ⇒ 一句都不出声，与 CUDA/NPU/精度完全无关**'
        '（离线复刻证实：GUID ✗ / 名字子串 ✓ / int ✓；同一个 id 在 '
        '`make_source(\'system\')` 上是**正确**用法 ⇒ 只改播放层）⇒ 新增 '
        '`resolve_out_device` / `_match_output_index` / `_describe_out` + '
        '**开流失败回退系统默认**；③ **三层音频判据**（① `n_played` ② 回环 RMS ③ 人耳）落地，'
        '`app052` 三例 **0.19658 / 0.11482 / 0.12878 全 PASS** ⇒ '
        '**App 侧已把声音送进系统混音器**；④ 新增客户级自检 `app/audio_check.py`；'
        '⑤ ⏳ **v1.5 第三次重打待锁**（`mt pid=9748` 自 21:21 持锁，22:24 已 63 min）'
    ),
    '阻塞': (
        '① 🔴 **v1.5 第三次重打待机器锁释放**（`mt pid=9748` 自 21:21 持有；按纪律**只等不抢**）：'
        '重打内容 = §39 播放修复 + §40/§41 CUDA 边车 + §42 两个修复；'
        '② 🔴 **§42.3 的修复待实机验证**（`--out-device {GUID}` ⇒ 应打印'
        '「端点 id → … → 播放索引 N」且 `n_played=1`）；'
        '③ ✅ **CUDA 落地方式已定**（§41 用户选「只做本机可选后端」）⇒ 不再待决；'
        '④ ⛔ **OV 的 CUDA plugin 不引入**（§39.5 依据不变）；'
        '⑤ ⛔ **APP-017「检查点 3」**由并发 App 会话在做 ⇒ 本会话不重复跑；'
        '⑥ ⛔ **WER +2.6pp 主因**未定位；'
        '⑦ ✅ **APP-015 方案 C 渲染层验收 23/23**，但 `translator.py` 合入仍待 MT 移交'
        '（APP-009② / H-014，App 不代提交）；⚠️ 并发会话在该文件留的在制品**本轮未动**；'
        '⑧ ⛔ 包体 10.45 GiB 优化未做；'
        '⑨ ⛔ V7 残句代价待确认；'
        '⑩ ⛔ 集显 F32 TTS 慢（首包 33.9 s）'
    ),
}

RECENT = [
    '- 22:32 §42 🔴🔴 **真因二（主因）**：GUI「语音输出 → 输出设备」传的是 **WASAPI 端点 id**'
    '（`soundcard` 的 `s.id` = `IMMDevice::GetId()`），而 `sounddevice` 只认 int 索引/设备名子串 '
    '⇒ `ValueError: No output device matching` ⇒ `Player._stream=None` ⇒ **每句都被丢** '
    '⇒ 与 CUDA/NPU/精度**全无关**',
    '- 22:32 §42 ✅ **离线复刻证实**（`ast` 抽 `sounddevice._get_device_id` + 打桩设备表）：'
    'GUID → `ValueError`；`Realtek` 子串 → `id=0`；int → `id=0`',
    '- 22:32 §42 ✅ **修法**：`tts_worker.py` 新增 `resolve_out_device`（GUID → soundcard 端点名 → '
    'sounddevice 索引）/ `_match_output_index` / `_describe_out` + **开流失败回退系统默认**；'
    '日志改为「实际输出: 名字（hostapi=…, ch=…, sr=…）」',
    '- 22:32 §42 🔴 **真因一**：`device_config.resolve_device` 把 `CUDA` **静默降级成 NPU**'
    '（`_pick(\'CUDA\')` 在 OV 清单里找不到）⇒ 修 12 行；CLI 全流程日志由「设备 NPU」→「设备 CUDA」',
    '- 22:32 §42 ✅ **修后全流程实测**：`[tts_cuda] 就绪 RTX 5050 / torch 2.11.0+cu128 / '
    '加载 38.2 s / 预热 1.7 s` ⇒ `首包 4.13 s 提交 1 播完 1 丢弃 0 state=ready`',
    '- 22:32 §42 ✅ **三层音频判据落地**（① `n_played` ② 回环 RMS ③ 人耳）+ `app052` 三例 '
    '**0.19658 / 0.11482 / 0.12878 全 PASS** ⇒ 声音**确实进了系统混音器**',
    '- 22:32 §42 🔴 `app052` 首版只留最后一例（证据被覆盖）⇒ 改 `cases` 数组累加；锁空后重跑留证',
    '- 22:32 §42 ✅ 新增客户级自检 `app/audio_check.py`（逐台输出端点播 440 Hz，含 hostapi）',
    '- 22:32 §42 ⛔ **未动 `live_caption_app.py`**（并发会话 APP-015 方案 C 在制品；且 GUID 应在播放层修）',
    '- 22:32 §42 ⏳ **v1.5 第三次重打未完成**：`mt pid=9748` 自 21:21 持锁（22:24 已 63 min），只等不抢',
    '- 21:25 §41 ✅ 巡检无新条目（`CORRECTIONS_APP.md` 最大 APP-017 = `last_ack`，只读零改动）',
    '- 21:25 §41 ✅ 安静窗口闸门 + 方案 C 渲染层 **23/23** + `pkg_exclude.__all__` 悬空名补齐',
    '- 21:15 §41 ✅ CUDA（PyTorch）做成**本机可选后端**（GUI 第三项、检测不到自动隐藏、包体不变）',
    '- 20:50 §40 🔴 PyTorch+CUDA 实测跑通：TTFA **0.547 s** / RTF **0.892**（`timing_valid=false`）',
    '- 19:50 §39.9 ✅ v1.5 已持锁重打（含播放修复）：md5 `f8475ce511efef7d13209bf9b64b5b95`',
]


def main() -> int:
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        lines = f.read().split('\n')

    # ① 4 个字段行（只认「行首 key: 」，避免误伤正文）
    #    ⚠️ 实际字段名是「阻塞 / 待用户决定」⇒ 用前缀匹配，写回时保留原标签
    LABEL = {'阻塞': '阻塞 / 待用户决定'}

    def _match_key(ln):
        for k in FIELDS:
            if ln.startswith(k) and ':' in ln:
                # 只接受「键（可带补充说明）: 值」这一种形态
                if ln.index(':') <= len(k) + len(' / 待用户决定') + 2:
                    return k
        return None

    hits = set()
    for i, ln in enumerate(lines):
        k = _match_key(ln)
        if k:
            lines[i] = '%s: %s' % (LABEL.get(k, k), FIELDS[k])
            hits.add(k)
        if len(hits) == len(FIELDS):
            break
    missing = set(FIELDS) - hits
    if missing:
        print('🔴 头部缺字段（不写回）：%s' % sorted(missing))
        return 2

    # ② `## 最近更新` 块：从该行到下一个 `## ` 之前的非空内容，整体替换
    try:
        i0 = next(i for i, ln in enumerate(lines) if ln.strip() == '## 最近更新')
    except StopIteration:
        print('🔴 找不到 `## 最近更新`（不写回）')
        return 2
    i1 = i0 + 1
    while i1 < len(lines) and not lines[i1].startswith('## '):
        i1 += 1
    # 保留块尾的空行结构：替换为「标题 + 空行 + 15 条 + 两个空行」
    new_block = ['## 最近更新', ''] + RECENT + ['', '']
    lines = lines[:i0] + new_block + lines[i1:]

    with io.open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines))

    # ③ 自检
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        txt = f.read()
    assert '\r' not in txt, '出现了 CRLF！'
    # ⚠️ 只能用「行首匹配」：正文里有引用 `## 最近更新` 字样的说明文字（§35 附近）
    assert sum(1 for ln in txt.split('\n') if ln.strip() == '## 最近更新') == 1, \
        '最近更新块数量异常'
    seg = txt.split('## 最近更新', 1)[1].split('\n## ', 1)[0]
    n = sum(1 for ln in seg.split('\n') if ln.startswith('- '))
    print('✅ 头部已更新：%s' % STATUS)
    print('   字段：%s' % ', '.join(sorted(FIELDS)))
    print('   最近更新条目 = %d（要求 ≤ 15）' % n)
    print('   总行数 = %d' % txt.count('\n'))
    return 0 if n <= 15 else 3


if __name__ == '__main__':
    sys.exit(main())
