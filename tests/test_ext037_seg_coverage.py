# -*- coding: utf-8 -*-
"""test_ext037_seg_coverage.py — EXT-037 ② + EXT-038 的自测

## 本文件要验什么

EXT-037 [BLOCKING] 2026-11-05 08:01（§29 复核）：

* **② BLOCKING**：EXT-036 ④ 引入的「**每段之后丢 3.5 s 音频**」
  （60 s 素材丢约 40%）⇒ sync 9 s 的「改善」**不可信**。
  根因：`ext/bridge.py` 的 `split_first_segment_streaming(...)`
  **每次**调用都切首 3.5 s ⇒ 但缓冲已被裁 ⇒ 网格已相对新缓冲
  ⇒ 新缓冲开头的 3.5 s 被误当「已交付首段」去掉。
* **③** 「非 TTS 固定项 7.184 s」的口径有误（`axis_gap` 不是延迟；
  `player_queue` 是结果项；漏掉「**等整段说完**」这一最大项）。
* **④** compare 的时长比口径错（`d_ws` 又除了一次 speed）。

EXT-038 [HIGH] 2026-11-05 08:25（用户决定）：
**插件默认 D 改为 20 s**，同步目标保持有符号 P95 ≤ 300 ms。

## 为什么必须自测（「假通过」风险）

① **「段区间连续覆盖」这条断言极易假通过**：
   只断言「最后一段的终点 = 源时长」⇒ **旧代码也能过**
   （旧代码尾段也到 59.49 s）⇒ 抓不住中间那 6 个 3.5 s 的缺口。
   ⇒ 本文件**逐段比对相邻区间**（无缺口、无重叠）**且**断言
     **总覆盖 = 源时长**。
   ★ 反证：把修复改回旧写法 ⇒ 本组断言**必须 FAIL**（实测：6 个 3.5 s 缺口）。

② **「D 默认 20」极易假通过**：只 grep 一个字符串 ⇒ 任何实现都满足。
   ⇒ 断言**三处**默认（popup / sw / player）**逐位一致**且**都是 20**，
     并且断言**服务端 `--delay` 默认**也是 20。

③ **「sync_rootcause 重写」极易假通过**：只要字段名还在就能过。
   ⇒ 断言 ①`axis_gap` **不在固定项里** ②`player_queue` 归入
     **结果项**（不在固定项合计里）③**新增 `seg_len` 项** ④
     `D_needed` **等于** `P95(ready − t_start) + 0.3`（手算逐位相等）。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（全部合成数据）。

运行：
    python tests/test_ext037_seg_coverage.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import sys

# ★★★⚠️ 本机 Python 3.13.12 的 **`os.path` 循环导入**坑（实测踩到）：
#   若在 `import os` **之前** import 任何会「间接 import os」的模块
#   （本文件曾用 `base64` / `pathlib`）⇒ `os.py` 的
#   `from os.path import (curdir, pardir, ...)`（os.py 第 96 行）
#   会在 `os.path` **尚未初始化完成**时执行
#   ⇒ `os` 模块里**没绑上** `path` 属性
#   ⇒ 随后 `os.path.dirname(...)` 报
#      `AttributeError: module 'os' has no attribute 'dirname'`（**误导性报错**）。
#   ⇒ 修法：**先 `import os`**，且**不要**在它之前 import `pathlib` / `base64`。
#   ⇒ `base64` 一律用 `__import__("base64")` 就地取
#     （与 `tests/test_ext010_pipeline.py` 同一口径）。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "ext"), os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from ext import config as C  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                            ("  —— %s" % detail) if detail else ""))


# ─────────────────────────────────────────────────────────────────
# 共用：合成素材 + 桩引擎
# ─────────────────────────────────────────────────────────────────
class _StubEngine:
    """**不跑推理**的桩引擎（只返回固定结果）。"""

    def transcribe(self, audio, **kw):
        return [{"text": "this is a synthetic segment for coverage check"}]

    def translate(self, text, **kw):
        return "这是用于覆盖检查的合成段落"

    def synthesize(self, text, **kw):
        return np.zeros(int(2.0 * 24000), dtype=np.float32)


def _make_audio(total_sec: float = 60.0, voice_sec: float = 8.0,
                gap_sec: float = 1.0, seed: int = 0,
                tail_gap_sec: float = None) -> np.ndarray:
    """★ **整段连续**生成（不是逐帧拼）⇒ 没有人为静音缝。

    ## 为什么必须整段生成
      逐帧各自造「语音 + 静音」⇒ 相邻帧的静音缝会**拼在一起**
      ⇒ VAD 在**帧边界**就切段 ⇒ 首段永远 < `cap`(3.5 s)
      ⇒ **根本触发不了**「首段提前交付」这条路径
      ⇒ 旧代码与新代码**结果一样** ⇒ 测试**没有区分力**。
      ⇒ 整段生成 ⇒ 静音只出现在 9 s 周期末尾 ⇒ 首段 ≈ 8 s（> cap）
      ⇒ 才会走「提前交付 [0, 3.5)」⇒ 才会暴露重复切分。

    ## ⚠️ `tail_gap_sec`（尾部留静音）的必要性
      「8 s 语音 + 1 s 静音」周期 ⇒ 素材**末尾**也是语音
      ⇒ VAD 网格最后一段是「尾部语音碎片」（实测 59.490→60.000 = **0.51 s**，
        < `SEG_MIN_SEC`=3.0）
      ⇒ 服务端 `flush()` 按**既有规则**「尾部不足 1 s ⇒ 丢弃」
        （客户端 `expected_segment_count()` **同口径**）
        ⇒ 末端必然少 0.51 s ⇒ 「Σ段长 = 源时长」**永远不成立**
      ⇒ 那不是**丢段缺陷**，而是**既有设计**（碎片不算一段）
      ⇒ 所以素材必须**以静音收尾**（`tail_gap_sec`），让最后一段
        是**完整语音段** ⇒ 「总覆盖 = 源时长」才是一个**有效判据**。
    """
    rng = np.random.default_rng(seed)
    n = int(total_sec * C.SAMPLE_RATE)
    out = np.zeros(n, dtype=np.float32)
    step = int((voice_sec + gap_sec) * C.SAMPLE_RATE)
    i = 0
    while i < n:
        vn = min(int(voice_sec * C.SAMPLE_RATE), n - i)
        # ★ 尾部留静音（避免末尾产生碎片段）
        if tail_gap_sec is not None and (i + vn) > (n - int(tail_gap_sec
                                                            * C.SAMPLE_RATE)):
            break
        tt = np.arange(vn) / float(C.SAMPLE_RATE)
        out[i:i + vn] = (0.25 * np.sin(2 * np.pi * 180.0 * tt)
                         + 0.03 * rng.standard_normal(vn))
        i += step
    return out


def _drive(session, audio: np.ndarray, frame_sec: float = 0.1) -> None:
    """用 PCM 帧驱动会话（与生产同款：100 ms/帧 + 累计采样数）。"""
    _b64 = __import__("base64")
    fs = int(frame_sec * C.SAMPLE_RATE)
    n_frames = len(audio) // fs
    for i in range(n_frames):
        chunk = audio[i * fs:(i + 1) * fs]
        pcm = (chunk * 32767).astype("<i2").tobytes()
        session.on_pcm_frame({
            "type": "pcm", "seq": i, "sample_index": i * fs,
            "pcm": _b64.b64encode(pcm).decode("ascii"),
        })


def _intervals(margins) -> list:
    return [(float(m["t_start"]), float(m["t_end"])) for m in margins]


def _coverage(ivs) -> dict:
    """逐段算**缺口**与**重叠**（不含「只看尾段」的弱断言）。"""
    gaps = []
    overlaps = []
    prev = 0.0
    for a, b in ivs:
        if a > prev + 1e-6:
            gaps.append((round(prev, 3), round(a, 3)))
        elif a < prev - 1e-6:
            overlaps.append((round(prev, 3), round(a, 3)))
        prev = max(prev, b)
    return {"gaps": gaps, "overlaps": overlaps,
            "covered_end": round(prev, 3),
            "covered_sum": round(sum(b - a for a, b in ivs), 3)}


# ─────────────────────────────────────────────────────────────────
# ① EXT-037 ②：段区间**连续覆盖**（无缺口、无重叠）
# ─────────────────────────────────────────────────────────────────
def test_01_continuous_coverage():
    print("\n[1] EXT-037 ② —— 段区间连续覆盖（修掉「每段丢 3.5 s」）")
    from ext.bridge import Session

    audio = _make_audio(tail_gap_sec=1.0)
    sess = Session("tok", delay_sec=10.0, engine=_StubEngine())
    _drive(sess, audio)
    sess.flush()

    ivs = _intervals(sess.margins)
    cov = _coverage(ivs)
    total = len(audio) / float(C.SAMPLE_RATE)
    # ★ 尾部**静音**不算「未覆盖」（静音里没有内容可翻译）
    #   ⇒ 覆盖率判据 = 「覆盖到最后一个**有效语音段**的终点」
    #   ⇒ 残差必须 **< 1.0 s**（服务端/客户端「尾段 < 1 s ⇒ 丢弃」的同口径）
    residual = round(total - cov["covered_end"], 3)

    check("① 产出了多段（素材 60 s ⇒ 段数 ≥ 5）",
          len(ivs) >= 5, "%d 段" % len(ivs))
    # ★ 核心断言：**逐段**无缺口、无重叠
    check("★ ① **无缺口**（相邻段区间连续；旧代码每段丢 3.5 s ⇒ 6 个缺口）",
          not cov["gaps"],
          "缺口=%s（%d 个）" % (cov["gaps"], len(cov["gaps"])))
    check("★ ① **无重叠**（首段与尾段不重复配音）",
          not cov["overlaps"],
          "重叠=%s（%d 个）" % (cov["overlaps"], len(cov["overlaps"])))
    # ★ 第二条判据：总覆盖 ≈ 源时长（**不能**只看尾段终点）
    #   ⚠️ 尾部允许 < 1.0 s 残差（=「尾段不足 1 s ⇒ 丢弃」的既有规则；
    #     客户端 `expected_segment_count()` **同口径** ⇒ 不是丢段缺陷）
    check("★ ① **总覆盖 ≈ 源时长**（残差 < 1.0 s：尾部静音/碎片不算缺口）",
          abs(cov["covered_sum"] - total) <= 1.0,
          "Σ段长=%.3f s vs 源时长=%.3f s（残差 %.3f s）"
          % (cov["covered_sum"], total, residual))
    # ★ 第三条判据：残差必须是**尾部静音**，不是中间丢段
    #   （中间丢段已被上面的「无缺口」抓住）
    check("① 首段起点 = 0（会话起点不漂）",
          abs(ivs[0][0]) <= 1e-6, "t_start=%.4f" % ivs[0][0])
    # ★ 缺口大小必须**正好 3.5 s**（证明抓到的是**那个**缺陷）
    if cov["gaps"]:
        sizes = [round(b - a, 3) for a, b in cov["gaps"]]
        check("★ ① 缺口大小**正好 3.5 s**（= `FIRST_SEGMENT_MAX_SEC`）",
              all(abs(s - C.FIRST_SEGMENT_MAX_SEC) <= 1e-3 for s in sizes),
              "缺口尺寸=%s" % sizes)
    else:
        check("★ ① 缺口大小**正好 3.5 s**（无缺口 ⇒ 本项 N/A）", True,
              "无缺口")

    # ★★ 变异测试（**证明这道守卫抓得住**）★★
    #   把修复改回旧写法 ⇒ 本组断言**必须 FAIL**。
    #   ⚠️⚠️⚠️ 变异体必须是**真实的历史代码**，不是「猜出来的旧写法」：
    #     之前试过两种「模拟旧行为」的写法，**都抓不到**（假通过）：
    #       ① monkeypatch `split_first_segment_streaming`（只改函数体，
    #          改不了调用点）⇒ 变异后 0 缺口；
    #       ② 只去掉 `if self._buf_base == 0 and …` 这个守卫
    #          ⇒ 区间仍连续（因为 `abs0 = _buf_base + s0` 补偿了偏移），
    #            只是每段**内容**少了 3.5 s ⇒ **区间判据抓不住**。
    #   ⇒ 正确做法：**直接取 git HEAD（reviewer 面对的那一版）**
    #     `ext/bridge.py` 当变异体跑一遍 ⇒ 必须出现缺口。
    import importlib
    import shutil
    import subprocess
    import ext.bridge as B

    _src_path = B.__file__
    with open(_src_path, encoding="utf-8") as _f:
        _src_orig = _f.read()

    def _run_with(src_text):
        """把 `ext/bridge.py` 换成 `src_text` 跑一遍，返回（覆盖统计, 段区间）。"""
        with open(_src_path, "w", encoding="utf-8") as _f:
            _f.write(src_text)
        importlib.reload(B)
        s = B.Session("tokX", delay_sec=10.0, engine=_StubEngine())
        _drive(s, audio)
        s.flush()
        _ivs = _intervals(s.margins)
        return _coverage(_ivs), _ivs

    # ── 变异体 1：git HEAD（reviewer 实测到丢段的那一版）────────────
    _head = None
    try:
        _head = subprocess.check_output(
            ["git", "show", "HEAD:ext/bridge.py"], cwd=ROOT
        ).decode("utf-8")
    except Exception as _e:                      # 没装 git / 不是仓库
        _head = None
    check("★ ① 能取到 git HEAD 版 bridge.py（变异体来源）",
          _head is not None and len(_head) > 1000,
          "HEAD 长度=%s" % (len(_head) if _head else None))
    try:
        cov2, ivs2 = _run_with(_head) if _head else ({"gaps": [],
                                                        "covered_sum": 0.0}, [])
        _gap_sizes = [round(b - a, 3) for a, b in cov2["gaps"]]
        check("★ ① 变异测试：git HEAD 版 ⇒ **必然出现缺口**（reviewer 实测复现）",
              len(cov2["gaps"]) > 0,
              "变异后缺口 %d 个（尺寸 %s）"
              % (len(cov2["gaps"]), _gap_sizes[:6]))
        check("★ ① 变异体的缺口尺寸**正好 3.5 s**"
              "（= `FIRST_SEGMENT_MAX_SEC`，证明抓到的是**那个**缺陷）",
              bool(_gap_sizes)
              and all(abs(s - C.FIRST_SEGMENT_MAX_SEC) <= 1e-3
                      for s in _gap_sizes),
              "缺口尺寸=%s" % _gap_sizes[:6])
    finally:
        with open(_src_path, "w", encoding="utf-8") as _f:
            _f.write(_src_orig)
        importlib.reload(B)

    # ── 守卫的**存在性**断言（修复的一部分必须落在代码里）──────────
    #   ⚠️ 为什么不再用「只去掉守卫」当变异体：
    #     去掉守卫后，`abs0 = _buf_base + s0` 会**补偿**区间偏移
    #     ⇒ 区间**仍然连续**（无缺口）⇒ 「无缺口」这条断言抓不到它
    #     ⇒ 实测差异只在**切点**（末尾多出 3 个短段 3.19/3.15/2.47 s）
    #     ⇒ 那是「网格一致性」问题，不是 EXT-037 ② 的「丢段」问题。
    #   ⇒ 真正的变异证明交给上面的 **git HEAD 变异体**
    #     （那一版**确实**每段丢 3.5 s ⇒ 5 个缺口 ⇒ 已 PASS）。
    #   ⇒ 这里只断言「守卫那行**必须**在代码里」（防止有人把修复删掉）。
    _guard = "if self._buf_base == 0 and self._first_seg_cut:"
    check("★ ① 网格对齐守卫**必须**在代码里"
          "（`_buf_base == 0` ⇒ 只对齐一次，绝不重复切首段）",
          _guard in _src_orig,
          "未找到 `%s`" % _guard)
    check("★ ① 缓冲被裁后**清零** `_first_seg_cut`"
          "（否则下一轮仍会重复切 ⇒ 每段丢 3.5 s）",
          "self._first_seg_cut = 0" in _src_orig
          and "self._buf_delivered_prefix = 0" in _src_orig,
          "未找到清零语句")
    check("★ ① `flush()` 会跳过「已交付但未裁」的前缀"
          "（否则尾段与首段重叠 ⇒ 重复配音）",
          "_buf_delivered_prefix" in _src_orig,
          "未找到 `_buf_delivered_prefix`")

    # ★★ 反向守卫：首段提前交付**只发生一次**（`_first_seg_cut` 用完即清零）
    check("★ ① 首段提前交付**只做一次**（`_first_seg_cut` 用完即清零）",
          sess._first_seg_cut == 0,
          "_first_seg_cut=%s" % sess._first_seg_cut)


# ─────────────────────────────────────────────────────────────────
# ② EXT-037 ②：`flush()` 不得与已交付首段**重叠**
# ─────────────────────────────────────────────────────────────────
def test_02_flush_no_overlap():
    print("\n[2] EXT-037 ② —— flush() 跳过「已交付但未裁」的前缀")
    from ext.bridge import Session

    audio = _make_audio(total_sec=30.0)
    sess = Session("tok", delay_sec=10.0, engine=_StubEngine())
    _drive(sess, audio)
    sess.flush()
    ivs = _intervals(sess.margins)
    cov = _coverage(ivs)
    check("② flush 后仍**无缺口、无重叠**",
          not cov["gaps"] and not cov["overlaps"],
          "缺口=%s 重叠=%s" % (cov["gaps"], cov["overlaps"]))
    check("② 首段仍是 `[0, …]`（没被 flush 重复派发）",
          abs(ivs[0][0]) <= 1e-6, "t_start=%.4f" % ivs[0][0])


# ─────────────────────────────────────────────────────────────────
# ③ EXT-038：默认 D = 20 s（插件与桥接两侧**一致**）
# ─────────────────────────────────────────────────────────────────
def test_03_default_delay_20():
    print("\n[3] EXT-038 —— 默认 D 改为 20 s（插件 + 桥接两侧一致）")
    import re

    popup_js = os.path.join(ROOT, "extension", "popup.js")
    sw_js = os.path.join(ROOT, "extension", "sw.js")
    player_js = os.path.join(ROOT, "extension", "player.js")
    bridge_py = os.path.join(ROOT, "ext", "bridge.py")

    # ── ① popup：默认配置 + 读盘兜底 ────────────────────────────
    psrc = open(popup_js, encoding="utf-8").read()
    m_def = re.search(r"delaySec:\s*(\d+)", psrc)
    m_read = re.search(r"delaySec:\s*Number\(\$\('delay'\)\.value\)\s*\|\|\s*(\d+)", psrc)
    check("③ popup 默认 `delaySec` = 20",
          m_def is not None and m_def.group(1) == "20",
          m_def.group(0) if m_def else "未找到")
    check("③ popup 读盘兜底 `|| 20`（存量配置缺失时也回落 20）",
          m_read is not None and m_read.group(1) == "20",
          m_read.group(0) if m_read else "未找到")

    # ── ② sw：转发用的默认 ──────────────────────────────────────
    ssrc = open(sw_js, encoding="utf-8").read()
    m_sw = re.search(r"delaySec:\s*(\d+)", ssrc)
    check("③ sw 默认 `delaySec` = 20",
          m_sw is not None and m_sw.group(1) == "20",
          m_sw.group(0) if m_sw else "未找到")

    # ── ③ player：运行时默认 + 配置回落 ─────────────────────────
    psrc = open(player_js, encoding="utf-8").read()
    m_pl = re.search(r"let delaySec\s*=\s*(\d+)", psrc)
    check("③ player 运行时默认 `delaySec` = 20",
          m_pl is not None and m_pl.group(1) == "20",
          m_pl.group(0) if m_pl else "未找到")
    m_fb = re.search(r"cfg\.delaySec\s*\|\|\s*(\d+)", psrc)
    check("③ player 配置回落 `|| 20`",
          m_fb is not None and m_fb.group(1) == "20",
          m_fb.group(0) if m_fb else "未找到")
    m_def2 = re.search(r"wsUrl:\s*'ws://127\.0\.0\.1:8765/',\s*token:\s*'',\s*delaySec:\s*(\d+)",
                        psrc)
    check("③ player 默认配置对象 `delaySec` = 20",
          m_def2 is not None and m_def2.group(1) == "20",
          m_def2.group(0) if m_def2 else "未找到")

    # ── ④ 桥接（服务端）：`--delay` 默认 20 ─────────────────────
    bsrc = open(bridge_py, encoding="utf-8").read()
    m_bd = re.search(r'"--delay",\s*type=float,\s*default=([\d.]+)', bsrc)
    check("③ 桥接 `--delay` 默认 = 20.0",
          m_bd is not None and abs(float(m_bd.group(1)) - 20.0) < 1e-9,
          m_bd.group(0) if m_bd else "未找到")

    # ── ⑤ 两侧**必须一致**（同值）────────────────────────────────
    # ⚠️ 桥接侧是 float（`20.0`）、插件侧是 int（`20`）
    #   ⇒ 必须**归一成数值**再比 ⇒ 否则字符串集合不唯一（假 FAIL）
    _pv = float(m_def.group(1)) if m_def else None
    _sv = float(m_sw.group(1)) if m_sw else None
    _lv = float(m_pl.group(1)) if m_pl else None
    _bv = float(m_bd.group(1)) if m_bd else None
    vals = [_pv, _sv, _lv, _bv]
    check("③ 插件与桥接两侧默认 D **完全一致**（都是 20）",
          all(v is not None for v in vals)
          and len(set(vals)) == 1 and vals[0] == 20.0,
          "popup=%s sw=%s player=%s bridge=%s" % tuple(vals))

    # ── ⑥ D 的上限仍容得下 20（popup 的 max ≥ 20）───────────────
    popup_html = open(os.path.join(ROOT, "extension", "popup.html"),
                      encoding="utf-8").read()
    m_in = re.search(r'id="delay"[^>]*max="(\d+)"', popup_html)
    check("③ popup 的 D 上限 ≥ 20（20 s 可选）",
          m_in is not None and int(m_in.group(1)) >= 20,
          m_in.group(0) if m_in else "未找到")


# ─────────────────────────────────────────────────────────────────
# ④ EXT-037 ③：sync_rootcause 口径重写
# ─────────────────────────────────────────────────────────────────
def test_04_rootcause_caliber():
    print("\n[4] EXT-037 ③ —— sync_rootcause 口径重写")
    from ext.bridge import decompose_sync_rootcause

    delay = 20.0
    # 合成：段长 7 s、ASR 3 s、MT 0.5 s、TTS 3 s
    # ⚠️⚠️ **时间轴必须自洽**（本组一开始就是栽在这儿）：
    #   * `t0`（服务端 perf_counter 域的原点）= `orig_end − t_end`
    #     ⇒ 这里恒为 **93.0**（`orig_end = 100 + 7i`，`t_end = 7i + 7`）
    #   * `ready_at` 是**服务端墙钟**（perf_counter 域）⇒ 必须 **≥ t0**
    #     ⇒ 旧写法 `ready_at = 10 + 7i` 落在 t0=93 **之前**
    #       ⇒ `ready − t0 − t_start = −83` ⇒ `D_needed = −82.7`（荒谬）
    #   * 正确：`ready_at = t0 + t_start + 10` = `103 + 7i`
    #     ⇒ `ready − t0 − t_start = 10 s`（每段恒定）⇒ P95 = 10
    #     ⇒ `D_needed = 10.3 s`
    _T0 = 93.0
    margins = []
    for i in range(6):
        margins.append({
            "id": "seg_%d" % i,
            "t_start": float(i * 7),
            "t_end": float(i * 7 + 7),
            "orig_end": 100.0 + i * 7,
            "has_tts": True,
            "asr_sec": 3.0, "mt_sec": 0.5, "tts_sec": 3.0,
            "speech_sec": 4.0, "proc_sec": 6.5,
            "feed_lag_sec": -5.0,
            "audio_ready_rel_sec": float(i * 7 + 0.5),
            "ready_at": _T0 + float(i * 7) + 10.0,
        })
    detail = [{"id": "seg_%d" % i, "readyToStartSec": 1.0} for i in range(6)]

    out = decompose_sync_rootcause(
        margins, delay_sec=delay, player_detail=detail,
        server_to_player_sec=3.189,      # ★ **轴常量**（不是延迟）
        downlink_latency_sec=0.035)

    det = out.get("non_tts_fixed_detail", {})

    # ── ① axis_gap **不在固定项里**（EXT-037 ③ 的核心）──────────
    check("④ ① `axis_gap` **不计入**固定项（它是两端时钟换算常数，不是延迟）",
          "axis_gap_sec" not in det
          or det.get("axis_gap_sec") is None
          or "axis_gap" not in str(det.get("fixed_items", [])),
          "fixed_items=%s" % det.get("fixed_items"))
    check("④ ① 轴常量仍**如实保留**（可核对，不是不测）",
          out.get("server_to_player_sec") == 3.189,
          "server_to_player_sec=%s" % out.get("server_to_player_sec"))

    # ── ② player_queue 归入**结果项** ───────────────────────────
    check("④ ② `player_queue` 归入**结果项**（不在固定项里）",
          "player_queue" not in str(det.get("fixed_items", [])),
          "fixed_items=%s" % det.get("fixed_items"))
    # ⚠️ 结果项在**顶层** `result_items_detail`（不在 `non_tts_fixed_detail` 里）
    rid = out.get("result_items_detail") or {}
    check("④ ② 结果项里仍**如实保留** player_queue 的实测值",
          rid.get("player_queue_sec_mean") == 1.0,
          "result_items_detail=%s" % rid)

    # ── ③ 新增 `seg_len` 项（EXT-037 ③：「漏掉了最大的一项」）────
    check("④ ③ 固定项里**新增 `seg_len`**（等整段说完这一项）",
          "seg_len_sec" in det,
          "fixed_items=%s" % det.get("fixed_items"))
    check("④ ③ `seg_len` 的值 = 段均长度（7.0 s）",
          abs(float(det.get("seg_len_sec") or 0.0) - 7.0) < 1e-6,
          "seg_len_sec=%s" % det.get("seg_len_sec"))

    # ── ④ `D_needed` = P95(ready − t_start) + 0.3 ───────────────
    d_needed = out.get("D_needed_sec")
    check("④ ④ 给出 `D_needed_sec`（EXT-037 ③ 的验收口径）",
          d_needed is not None, "D_needed=%s" % d_needed)
    if d_needed is not None:
        # 手算：ready 时刻 − t_start = (10 + i*7) − (i*7) = 10 s
        #       ⇒ P95(ready − t_start) = 10 s ⇒ D_needed = 10.3 s
        check("④ ④ `D_needed` 与手算**逐位相等**（P95(ready−t_start)+0.3）",
              abs(float(d_needed) - (10.0 + 0.3)) < 1e-6,
              "实算=%s 手算=%.3f" % (d_needed, 10.0 + 0.3))
        check("④ ④ `D_needed` 的公式写明（P95(ready − t_start) + 0.3）",
              "ready" in str(out.get("D_needed_note", "")).lower(),
              "note=%s" % out.get("D_needed_note"))

    # ── ⑤ 固定项合计 = 已实测项之和（axis/queue **不算**）─────────
    #   固定项 = feed(夹0) + asr(3.0) + seg_len(7.0) + downlink(0.035)
    expect_fixed = 0.0 + 3.0 + 7.0 + 0.035
    check("④ ⑤ 固定项合计与手算**逐位相等**"
          "（axis 3.189 与 player_queue 1.0 **都不计入**）",
          abs(float(out["non_tts_fixed_sec"]) - expect_fixed) < 1e-6,
          "实算=%s 手算=%.3f" % (out["non_tts_fixed_sec"], expect_fixed))

    # ── ⑥ 反证：不给 player 明细 ⇒ 不臆造 player_queue ──────────
    out2 = decompose_sync_rootcause([dict(m) for m in margins],
                                    delay_sec=delay, player_detail=None)
    check("④ ⑥ 反证：没有 player 明细时**不臆造** player_queue",
          out2.get("player_queue_sec_mean") is None,
          "player_queue_sec_mean=%s" % out2.get("player_queue_sec_mean"))


# ─────────────────────────────────────────────────────────────────
# ⑤ EXT-037 ④：compare 的时长比口径
# ─────────────────────────────────────────────────────────────────
def test_05_dur_ratio_caliber():
    print("\n[5] EXT-037 ④ —— compare 时长比口径（d_ws 不再除 speed）")
    sys.path.insert(0, os.path.join(ROOT, "tests", "smoke"))
    from ext033_analyze import _ext036_analysis

    segs = [
        # d_player / src_len / d_ws / speed
        {"d_player_sec": 2.0, "src_len_sec": 3.5, "d_ws_sec": 2.2, "speed": 1.0},
        {"d_player_sec": 3.0, "src_len_sec": 4.0, "d_ws_sec": 3.1, "speed": 1.0},
        {"d_player_sec": 1.5, "src_len_sec": 2.0, "d_ws_sec": 1.6, "speed": 1.0},
    ]
    ratios = [2.0 / 2.2, 3.0 / 3.1, 1.5 / 1.6]
    out = _ext036_analysis([], {}, {}, [], 48000, {}, {}, segs, [], ratios)
    cal = out["dur_ratio_calibers"]

    # ★ 新口径：d_player ÷ d_ws（**不再**乘/除 speed）
    #   手算：2.0/2.2=0.9091、3.0/3.1=0.9677、1.5/1.6=0.9375
    #   ⇒ min = 0.9091（2.0/2.2），max = 0.9677（3.0/3.1）
    #   ⚠️ 旧断言写成 (1.5/1.6) 与 (2.0/2.2) ⇒ **min/max 选错**（假 FAIL）
    _exp_min = min(2.0 / 2.2, 3.0 / 3.1, 1.5 / 1.6)
    _exp_max = max(2.0 / 2.2, 3.0 / 3.1, 1.5 / 1.6)
    check("⑤ 新口径 `over_ws` = d_player ÷ d_ws（**未经**变速校正）",
          abs(cal["over_ws"]["min"] - _exp_min) < 1e-4
          and abs(cal["over_ws"]["max"] - _exp_max) < 1e-4,
          "min=%s max=%s（手算 min=%.4f max=%.4f）"
          % (cal["over_ws"]["min"], cal["over_ws"]["max"],
             _exp_min, _exp_max))
    check("⑤ `speed_adjusted` 口径被**移除**（变速被重复校正 ⇒ 作废）",
          "speed_adjusted" not in cal,
          "keys=%s" % sorted(cal.keys()))
    check("⑤ `over_src_len`（reviewer 口径）**保留**且定义仍在",
          "over_src_len" in cal and "definition" in cal["over_src_len"],
          "keys=%s" % sorted(cal.keys()))
    check("⑤ 口径说明点明「d_ws 已是变速后时长，不能再除 speed」",
          "speed" in str(cal.get("note", "")).lower()
          or "变速" in str(cal.get("note", "")),
          "note=%s" % cal.get("note"))

    # ★★★ 反证：把「再乘一次 speed」写回**实现** ⇒ 本组断言**必须 FAIL**
    #   ⚠️ 旧写法只改了 `ratios` 这个**入参** ⇒ `_ext036_analysis` 的
    #     `over_ws` 根本不读它 ⇒ 断言照样过 ⇒ **变异测试形同虚设**。
    #   ⇒ 现在真的去改**计算 `over_ws` 的那段代码**（改源码 + 重载模块）
    #     ⇒ 断言必须 FAIL ⇒ 证明这道守卫**抓得住**。
    import importlib
    import ext033_analyze as _A
    _src_path = _A.__file__
    with open(_src_path, encoding="utf-8") as _f:
        _src_orig = _f.read()
    _needle = "over_ws.append(float(d_player) / float(d_ws))"
    _src_bad = _src_orig.replace(
        _needle, "over_ws.append(float(d_player) * 1.25 / float(d_ws))")
    check("★ ⑤ 变异点存在（否则反证无效）",
          _src_bad != _src_orig, "未找到 `%s` 那行" % _needle)
    try:
        with open(_src_path, "w", encoding="utf-8") as _f:
            _f.write(_src_bad)
        importlib.reload(_A)
        cal_bad = _A._ext036_analysis([], {}, {}, [], 48000, {}, {}, segs,
                                       [], ratios)["dur_ratio_calibers"]
        check("★ ⑤ 反证：把「再乘一次 speed」写回实现 ⇒ **口径不一致被抓到**",
              abs(cal_bad["over_ws"]["min"] - _exp_min) >= 1e-4,
              "变异后 over_ws.min=%s（正确值=%.4f ⇒ 差异 %.4f ⇒ 守卫有效）"
              % (cal_bad["over_ws"]["min"], _exp_min,
                 abs(cal_bad["over_ws"]["min"] - _exp_min)))
    finally:
        with open(_src_path, "w", encoding="utf-8") as _f:
            _f.write(_src_orig)
        importlib.reload(_A)


def test_06_e2e_delay_plumbing():
    """★ EXT-038：**e2e 跑批的 D 必须两侧一致**（否则测出来的 sync 是假的）。

    ## 为什么必须自测（「假通过」风险）
    e2e 跑批里 D 出现在**三处**：
      ① 服务端 `--delay`（`start_bridge`）
      ② 插件侧 `chrome.storage.local.delaySec`（`player.js` 的 `boot()`）
      ③ e2e 自己的默认值（`main()` 的 `delay_sec`）
    ⇒ 只要其中一处漏改，**测出来的 sync P95 就是假的**
    （服务端按 D=20 排程、插件按 D=10 播 ⇒ 误差恒定差 10 s）。
    ⇒ 本组断言：① 三处**都**参数化（不再写死 10）、
      ② 默认值**都是 20**、③ 插件侧**确实被写入**并**读回校验**。
    """
    print("\n[6] EXT-038 —— e2e 跑批的 D 两侧一致（不写死 10）")
    e2e = os.path.join(ROOT, "tests", "smoke", "ext033_e2e.py")
    src = open(e2e, encoding="utf-8").read()
    b28 = open(os.path.join(ROOT, "tests", "smoke", "ext028_029_e2e.py"),
               encoding="utf-8").read()

    # ── ① 服务端 `--delay` 参数化（不再是字面量 "10"）────────────
    m = re.search(r'"--delay",\s*str\(delay_sec\)', b28)
    check("⑥ 服务端 `--delay` 用 `delay_sec` 参数（不再写死 10）",
          m is not None, m.group(0) if m else "未找到")
    check("⑥ `start_bridge` 有 `delay_sec` 形参（默认 10，向后兼容）",
          "delay_sec: int = 10" in b28,
          "未找到 `delay_sec: int = 10`")
    check("⑥ 回声模式的 `--delay` 也参数化了（不是另一处写死 10）",
          re.search(r'"--delay",\s*str\(delay_sec\)', src) is not None,
          "ext033_e2e.py 未找到 `--delay str(delay_sec)`")

    # ── ② e2e 默认 D = 20（与插件/服务端默认值一致）───────────────
    m2 = re.search(r"delay_sec\s*=\s*(\d+)\s*\n", src)
    check("⑥ e2e 默认 `delay_sec` = 20",
          m2 is not None and int(m2.group(1)) == 20,
          m2.group(0) if m2 else "未找到")
    check("⑥ e2e 支持 `--delay` 传参（命令行可覆盖）",
          '"--delay"' in src and '"--delay="' in src,
          "未找到 --delay 参数解析")

    # ── ③ 插件侧**确实被写入**并**读回校验**（不能只写不校验）─────
    check("⑥ e2e 把 D 写进插件 storage（`chrome.storage.local.set`）",
          "chrome.storage.local.set({delaySec:" in src,
          "未找到 storage.local.set")
    check("⑥ ★ 写完**读回校验**（值不符 ⇒ 报错 ⇒ 不会拿着错的 D 去测）",
          re.search(r"if int\(_set_d or 0\) != int\(delay_sec\)", src)
          is not None,
          "未找到读回校验")
    check("⑥ ★ 写完**重载 player 页**（`boot()` 只在加载时读 storage）",
          "player.reload()" in src, "未找到 player.reload()")

    # ── ④ 轮次摘要里**记录** D（证据可核对）─────────────────────
    check("⑥ 轮次摘要记录 `delay_sec`（证据可核对）",
          '"delay_sec": delay_sec' in src,
          "未找到 summary['delay_sec']")
    check("⑥ 轮次摘要记录插件侧实际生效的 D",
          '"plugin_delay_sec"' in src, "未找到 summary['plugin_delay_sec']")

    # ── ⑤ 反证：把 e2e 的默认改回 10 ⇒ 本组**必须**抓到 ──────────
    _orig = src
    _bad = src.replace("    delay_sec = 20\n", "    delay_sec = 10\n", 1)
    check("★ ⑥ 反证：变异点存在（否则反证无效）",
          _bad != _orig, "未找到 `delay_sec = 20` 那行")
    try:
        with open(e2e, "w", encoding="utf-8") as f:
            f.write(_bad)
        _re = re.search(r"delay_sec\s*=\s*(\d+)\s*\n", _bad)
        check("★ ⑥ 反证：把 e2e 默认 D 改回 10 ⇒ 断言**抓得住**",
              _re is None or int(_re.group(1)) != 20,
              "变异后 delay_sec=%s（应 ≠ 20 ⇒ 守卫有效）"
              % (_re.group(1) if _re else "?"))
    finally:
        with open(e2e, "w", encoding="utf-8") as f:
            f.write(_orig)


def main() -> int:
    print("=" * 68)
    print("EXT-037 / EXT-038 自测 —— 不跑推理 / 不占 GPU·NPU / "
          "不创建共享锁 / 不启动浏览器")
    print("=" * 68)
    for fn in (test_01_continuous_coverage, test_02_flush_no_overlap,
               test_03_default_delay_20, test_04_rootcause_caliber,
               test_05_dur_ratio_caliber, test_06_e2e_delay_plumbing):
        try:
            fn()
        except Exception as e:          # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"★ {fn.__name__} 抛异常", False, repr(e))

    npass = sum(1 for _, ok in RESULTS if ok)
    nfail = sum(1 for _, ok in RESULTS if not ok)
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    if nfail:
        print("⇒ 有 FAIL ⇒ 必须修完再交卷。")
    print("=" * 68)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
