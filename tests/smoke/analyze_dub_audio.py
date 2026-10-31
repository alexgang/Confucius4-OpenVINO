"""analyze_dub_audio.py — 分析 player 录制的配音音频（webm/opus）是否非静音。

EXT-026 第 3 条要求「配音录音非静音」作为验收证据。本工具把该判定做成
**可复现的落盘产物**：读 `dub_player.webm` ⇒ 输出 peak / RMS / dBFS /
语音 burst 数 / 语音时长占比 ⇒ 写 `dub_audio_analysis.json`。

★ 为什么用浏览器解码：`dub_player.webm` 是 MediaRecorder 出的
  `audio/webm;codecs=opus`，纯 Python 侧没有可靠 opus 解码器（不引入
  ffmpeg 依赖 ⇒ 保持仓库零外部二进制依赖）。故用 headless Edge/Chrome 的
  WebAudio `decodeAudioData` 解码 ⇒ **纯解码，不跑任何推理**，不抢 GPU/NPU。

★ 单一事实来源：判定阈值 `SILENCE_DBFS` / `MIN_BURSTS` 是**模块级常量**，
  判定函数 `is_non_silent()` 是**纯 Python 函数** ⇒
  - 冒烟脚本的验收判据调用它；
  - 自测（`tests/test_ext026_audio_analysis.py`）也调用它；
  ⇒ 不会出现「工具改了、判据没改」的漂移。

跑法：
    python tests/smoke/analyze_dub_audio.py <webm路径> [--out 分析结果json]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import browser_harness as H          # noqa: E402

# ── 判定阈值（单一事实来源）────────────────────────────────────
#: 窗口 RMS 低于此值（dBFS）视为静音窗口
SILENCE_DBFS = -45.0
#: 至少要有这么多个语音 burst 才算「非静音」
MIN_BURSTS = 1
#: 整体 RMS 下限（dBFS）—— 与 burst 条件是 **AND** 关系
MIN_RMS_DBFS = -45.0


def is_non_silent(stats: dict, rms_dbfs: float = MIN_RMS_DBFS,
                  min_bursts: int = MIN_BURSTS) -> bool:
    """判定一份音频统计是否「非静音」。

    ★ 三个条件是 **AND**：
      1. 整体 RMS 高于 `rms_dbfs`（排除「一个尖峰脉冲」这种假非静音）；
      2. 语音 burst 数 ≥ `min_bursts`（排除「只有底噪」）；
      3. 调用方还应确认样本非空（bytes > 0）。

    ★ 默认参数取模块级常量（`MIN_RMS_DBFS` / `MIN_BURSTS`）⇒
      冒烟脚本与自测共用**同一份判据**，不会漂移。
    """
    if not stats or not stats.get("ok", True):
        return False
    r = stats.get("dbfsRms")
    if r is None or r <= -999:
        return False
    return (r > rms_dbfs) and ((stats.get("bursts") or 0) >= min_bursts)


# 在页面里跑的解码+测量脚本（纯 WebAudio，无网络、无推理）
# ★ 只负责「解码 + 测量」；**判定留给上面的纯 Python 函数**
_DECODE_JS = r"""
async (b64) => {
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const ctx = new OfflineAudioContext(1, 16000, 16000);
  let buf;
  try {
    buf = await ctx.decodeAudioData(bin.buffer);
  } catch (e) {
    return { ok: false, error: 'decodeAudioData failed: ' + (e && e.message || e) };
  }
  const ch = buf.getChannelData(0);
  const sr = buf.sampleRate;
  let peak = 0, sumSq = 0;
  for (let i = 0; i < ch.length; i++) {
    const a = Math.abs(ch[i]);
    if (a > peak) peak = a;
    sumSq += ch[i] * ch[i];
  }
  const rms = Math.sqrt(sumSq / Math.max(1, ch.length));
  // 语音 burst：20ms 窗，窗 RMS 超过门限视为有声音
  const win = Math.max(1, Math.round(sr * 0.02));
  const thr = Math.pow(10, SILENCE_DBFS / 20);
  let bursts = 0, activeSamples = 0, inBurst = false;
  for (let i = 0; i + win <= ch.length; i += win) {
    let s = 0;
    for (let j = 0; j < win; j++) s += ch[i + j] * ch[i + j];
    const wRms = Math.sqrt(s / win);
    if (wRms > thr) {
      activeSamples += win;
      if (!inBurst) { bursts++; inBurst = true; }
    } else {
      inBurst = false;
    }
  }
  return {
    ok: true,
    sampleRate: sr,
    durationSec: buf.duration,
    frames: ch.length,
    peak: peak,
    rms: rms,
    dbfsPeak: peak > 0 ? 20 * Math.log10(peak) : -999,
    dbfsRms: rms > 0 ? 20 * Math.log10(rms) : -999,
    bursts: bursts,
    activeSec: activeSamples / sr,
    activeRatio: activeSamples / Math.max(1, ch.length),
  };
}
"""


def analyze(webm_path: str, threshold_dbfs: float = SILENCE_DBFS) -> dict:
    """解码 webm 并返回统计（含 `non_silent` 判定）。"""
    if not os.path.exists(webm_path):
        raise FileNotFoundError(webm_path)
    with open(webm_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    profile = os.path.join(ROOT, ".tmp", "_audio_analyze_profile")
    with H.BrowserSession(profile, headless=True) as br:
        page = br.new_page()
        # 把门限插值进 JS（避免 JS 里硬编码第二份阈值）
        js = _DECODE_JS.replace("SILENCE_DBFS", repr(float(threshold_dbfs)))
        res = page.evaluate(js, b64)
    res["path"] = os.path.abspath(webm_path)
    res["bytes"] = os.path.getsize(webm_path)
    res["mtime"] = time_str(webm_path)
    res["thresholdDbfs"] = threshold_dbfs
    res["non_silent"] = is_non_silent(res)
    return res


def time_str(p: str) -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S",
                          time.localtime(os.path.getmtime(p)))


def main() -> int:
    ap = argparse.ArgumentParser(description="分析 player 配音录音是否非静音")
    ap.add_argument("webm", help="dub_player.webm 路径")
    ap.add_argument("--out", default="", help="分析结果 json 输出路径")
    ap.add_argument("--threshold-dbfs", type=float, default=SILENCE_DBFS,
                    help="静音窗口门限（dBFS），默认 %.1f" % SILENCE_DBFS)
    a = ap.parse_args()

    res = analyze(a.webm, a.threshold_dbfs)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.out:
        d = os.path.dirname(os.path.abspath(a.out))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print("已落盘：%s" % a.out)
    return 0 if res.get("non_silent") else 1


if __name__ == "__main__":
    sys.exit(main())
