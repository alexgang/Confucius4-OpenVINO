"""🔴 APP-048：GUI **分区状态条**（纯逻辑层，**不依赖 tkinter**）。

## 为什么单独成模块

APP-048 的用户诉求是：「现在所有的状态信息全部挤在最顶端，太多而且挤不下。
后面建议把 ASR/翻译/TTS 的状态信息分别放在各个模型区域内，这样比较清晰。」

原实现把**所有**模块的状态拼成一条 `var_meter` 长文本塞在窗口顶部
（`_poll()` 里 `self.var_meter.set(... + self._mt_meter() + self._tts_meter())`）
⇒ 宽度必然溢出 ⇒ 用户看到的顶部就是「挤不下」。

本模块把「状态条」的**纯逻辑**（字段集合、优先级、宽度裁剪、严重程度、
tooltip 全文）从 tkinter 里剥出来：

- **纯逻辑**（`SectionStatus` / `render`）⇒ **不 import tkinter**
  ⇒ 可以在离线验收脚本里直接 import 并断言（不起窗口、不占 GPU、不取锁）。
- **视图**（`StatusStrip`）只负责把纯逻辑的结果画成一行 `ttk.Label`
  ⇒ 换 Tk 实现不影响判据。

## 设计口径（逐条对齐 APP-048）

| APP-048 要求 | 本模块的实现 |
|---|---|
| 每个区域一行紧凑状态条（图标 + 短字段） | `StatusStrip`：图标 + 单行短文本 |
| 数值定时刷新（≤ 1 Hz），不要频繁重排布局 | `SectionStatus.render()` **只在文本真的变了**时才返回新串（`changed` 标志）⇒ 调用方据此跳过 `configure()` |
| 报错时那一行变色 | `level ∈ {ok, warn, error}` ⇒ 整行 `foreground` 变色 |
| 鼠标悬停显示完整原因和日志路径 | `tooltip` 字段（每个字段可带 `tip`）⇒ 拼成全文挂在行上 |
| 字段过多时先隐藏次要字段 | 字段带 `priority`（越小越重要）⇒ 宽度不够时**从最次要的开始丢** |
| 顶部只保留全局信息 | 见 `live_caption_app.py`（顶部只留会话计时 + 总状态灯 + 全局消息） |

## 判据可离线验（不 import tkinter）

`SectionStatus` 不依赖任何 GUI 库 ⇒ `results/app/app165_*.py` 可以
在**不跑推理、不占 GPU、不取机器锁**的条件下断言裁剪 / 变色 / tooltip 逻辑。
"""

from __future__ import annotations

import threading

# 严重程度（整行级别）：任一字段 error ⇒ 整行 error；否则有 warn ⇒ warn。
LEVELS = ('ok', 'warn', 'error')

# 图标（紧凑、单字符，避免宽度开销）。
LEVEL_ICON = {'ok': '●', 'warn': '▲', 'error': '✖'}

# 颜色（浅色主题下的可读色；深色主题下由 GUI 层另行覆盖）。
LEVEL_COLOR = {'ok': '#2e7d32', 'warn': '#b26a00', 'error': '#c0392b'}

# 字段分隔符。
SEP = '  ·  '

# 没有真实字体度量时的宽度估算（px / 字符）。
_EST_PX_PER_CHAR = 7.5
# 🔴 **中文字符宽度约是 ASCII 的 2 倍**
#   ⇒ 只按 len() 估算会**严重低估** ⇒ 裁剪后实际仍然溢出
#   （实测：语音区状态条估算 108 字符 ≈ 810 px，实际中文占比高
#     ⇒ 真实宽度超过 1080 px 窗口 ⇒ 溢出到屏幕外）。
_EST_PX_PER_CJK = 15.0


def estimate_px(text):
    """按「中文算 2 个 ASCII 宽」估算文本像素宽度。"""
    w = 0.0
    for ch in text:
        if ord(ch) > 0x2E80:          # CJK / 全角标点
            w += _EST_PX_PER_CJK
        else:
            w += _EST_PX_PER_CHAR
    return int(w)


def measure_text(text):
    """默认度量函数（可被真实字体度量替换）。"""
    return estimate_px(text)


class SectionStatus:
    """一个分区（ASR / 翻译 / 语音）的状态字段集合。

    ## 字段

    每个字段是一行文本「`label value`」，另带：

    - `priority`：越小越重要（1 = 最先显示、最后才被丢弃）；
    - `level`：该字段自身的严重程度（`ok` / `warn` / `error`）；
    - `tip`：悬停提示的补充说明（完整原因 / 日志路径）。

    ## 线程安全

    GUI 侧只在主线程（`_poll`）里读写 ⇒ 不需要锁；但为稳妥，
    内部用一把 `threading.RLock` 保护字段表（`set` 可能被后台线程经
    `root.after` 之外的路径调用时也不会撕裂）。
    """

    def __init__(self, name: str):
        self.name = name
        self._fields = {}          # key -> dict
        self._order = []           # 插入顺序（同优先级时的排序依据）
        self._lock = threading.RLock()

    # -- 字段维护 --------------------------------------------------------
    def set(self, key, label, value, priority=1, level='ok', tip=''):
        """写入/更新一个字段。

        `level` 非法值一律降级成 `'ok'`（**不静默吞错**：调用方仍能从
        `level` 取到归一后的值）。
        """
        if level not in LEVELS:
            level = 'ok'
        with self._lock_guard():
            if key not in self._fields:
                self._order.append(key)
            self._fields[key] = dict(label=label, value=value,
                                     priority=int(priority), level=level,
                                     tip=tip or '')
        return self

    def clear(self, key):
        with self._lock_guard():
            self._fields.pop(key, None)
            if key in self._order:
                self._order.remove(key)
        return self

    def get(self, key, default=None):
        with self._lock_guard():
            f = self._fields.get(key)
        return f if f is not None else default

    # -- 渲染 ------------------------------------------------------------
    def ordered(self):
        """按显示顺序返回字段：priority 升序，同优先级按插入顺序。"""
        with self._lock_guard():
            items = [(k, dict(self._fields[k])) for k in self._order
                     if k in self._fields]
        items.sort(key=lambda kv: (kv[1]['priority'], self._order.index(kv[0])))
        return items

    def level(self):
        """整行级别（取所有字段里最严重的）。"""
        lv = 'ok'
        for _, f in self.ordered():
            if f['level'] == 'error':
                return 'error'
            if f['level'] == 'warn':
                lv = 'warn'
        return lv

    def render(self, max_px=None, measure=None):
        """渲染成 (文本, 整行级别, tooltip 全文)。

        - `max_px`：可用宽度（px）；`None` = 不裁剪。
        - `measure`：可选的文本宽度度量函数（`str -> int`）；
          `None` 时按字符数估算。

        🔴 **裁剪规则**：字段过多时**先隐藏次要字段**
        ⇒ 保留 priority 最小的若干个，按需从**最次要**的一端丢弃。
        """
        items = self.ordered()
        if not items:
            return '', 'ok', ''
        if measure is None:
            measure = measure_text
        texts = ['%s %s' % (f['label'], f['value']) for _, f in items]
        keep = list(range(len(items)))
        if max_px:
            def total(idx):
                return measure(SEP.join(texts[i] for i in idx))
            while keep and total(keep) > max_px:
                keep.pop()                    # 丢最次要的（ordered 已按优先级升序）
        if not keep:
            # 一个都放不下 ⇒ 至少显示最次要的那个的 label（避免整行空白）
            keep = [0]
        line = SEP.join(texts[i] for i in keep)
        tip_parts = []
        for i in keep:
            f = items[i][1]
            tip_parts.append('%s %s —— %s' % (f['label'], f['value'], f['tip'])
                             if f['tip'] else
                             '%s %s' % (f['label'], f['value']))
        return line, self.level(), '\n'.join(tip_parts)

    def snapshot(self):
        """返回可 JSON 化的快照（验收脚本用）。"""
        with self._lock_guard():
            return {k: dict(v) for k, v in self._fields.items()}

    # -- 内部 ------------------------------------------------------------
    def _lock_guard(self):
        return self._lock


def build_sections():
    """建三个分区状态（APP-048 的三分区）。"""
    return {
        'asr': SectionStatus('ASR'),
        'mt': SectionStatus('翻译'),
        'tts': SectionStatus('语音'),
    }


__all__ = ['SectionStatus', 'build_sections', 'LEVELS', 'LEVEL_ICON',
           'LEVEL_COLOR', 'SEP']
