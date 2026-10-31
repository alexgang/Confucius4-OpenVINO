"""test_ext026_e2e_behaviors.py — ★ EXT-026 本轮**新行为**的自测

## 这个文件要验什么

EXT-026 第 1–4 条的**真实三引擎端到端冒烟**（2026-10-31 实测）里，
抓到了三个**真实缺陷**并已修复。本文件为这三个修复补自测：

★ D1：**状态条的段数恒为 0**
  `handleBridgeMessage` 处理 `kind === 'stats'`（EXT-024 E 加的），
  但客户端**从来没发过** `{"type":"stats"}` 请求 ⇒ 服务端的 stats 分支
  永远进不去 ⇒ `asrSegments / mtSegments / ttsSegments` 恒为 0
  ⇒ **最关键的故障信号（TTS 一段都没出）根本显示不出来**
  （实测那轮真跑出了 4 段 TTS，状态条却显示 0）。
  ⇒ 修法：`pollStats()` 周期性发 `{"type":"stats"}`。

★ D2：**尾段永远丢**
  服务端故意把最后一段留在缓冲区（要客户端发 flush 才收口），
  但整个插件链路**从来没有发过 flush** ⇒ 用户点「停止」时最后一句不配音
  （实测：60 秒英文素材切 5 段，前 4 段出了配音，尾段直接消失）。
  ⇒ 修法：`flushUplink()` 发 `{"type":"flush"}`。

★ D3：**录不到 player 实际播出的配音**（EXT-026 第 3 条明文要求）
  服务端的 PCM 只证明「服务端算出了音频」，不能证明「浏览器播出来了」。
  ⇒ 修法：`startDubRecording()` 在 **dubBus** 上挂 MediaStreamDestination
    + MediaRecorder ⇒ 录的是**播出来的**声音。

另有一处**服务端侧**的证据核验：
★ D4：EXT-026 第 3 条要求「bridge.log 本次会话的段级日志：≥5 段，
  『下发到』含 player 的段数 = TTS 段数，没有『不顶替』/10048」
  ⇒ 本文件把 E2E 脚本里的日志解析口径也做成**可复算**的函数并测它。

## ★ 可证伪（铁律：自测要能区分「真通过」与「假通过」）

  * 插件侧用**独立的 node 沙箱 harness**（`tests/ext026_e2e_harness.js`），
    它从**真源码** `extension/player.js` 抽函数执行，并带**三组反证**
    （把实现改坏 ⇒ 对应断言必须变红）；
  * 服务端侧用**真实日志样本**做解析，并断言「解析出的段数 = 样本里的行数」
    ⇒ 解析器恒返回 0 会被抓住。

不跑推理 / 不占 GPU·NPU / **不创建共享锁**。

运行：
    python tests/test_ext026_e2e_behaviors.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  — " + detail) if (detail and not cond) else ""))


# ═══════════════════════════════════════════════════════════════════
# A 组：插件侧（node 沙箱跑**真** player.js 的真函数）
# ═══════════════════════════════════════════════════════════════════
def test_plugin_e2e_behaviors_harness() -> None:
    print("\n[A] ★ 插件侧行为级（node 沙箱跑 player.js 的**真函数**）")
    harness = os.path.join(ROOT, "tests", "ext026_e2e_harness.js")
    node = shutil.which("node") or ""
    if not node:
        check("node 可用（跳过本组）", True, "node 不可用")
        return
    player = os.path.join(ROOT, "extension", "player.js")
    r = subprocess.run([node, harness, player],
                       capture_output=True, encoding="utf-8",
                       errors="replace", timeout=180)
    out = r.stdout or ""
    print(out.rstrip())
    check("★★★ A-harness 全部通过（rc=0）",
          r.returncode == 0,
          "rc=%d；输出尾部：%s" % (r.returncode, out[-800:]))
    check("A-harness 至少跑了 13 项断言",
          out.count("[PASS]") >= 13, "PASS 数=%d" % out.count("[PASS]"))
    # ★ 注意：输出里**必然**含 "[FAIL]" —— 那是三组反证**故意**让子进程变红的
    #   证据（"反证后 [FAIL] ★ C1a 确实变红"）。
    #   ⇒ 这里只能检查**顶层汇总行**是 0 FAIL。
    m = re.search(r"ext026_e2e_harness:\s*(\d+)\s*PASS\s*/\s*(\d+)\s*FAIL",
                  out)
    check("★ A-harness 顶层汇总 = 0 FAIL",
          m is not None and int(m.group(2)) == 0,
          "实测 %s" % (m.group(0) if m else "没找到汇总行"))
    # ★ 三组反证都必须在（否则断言可能恒真）
    for tag in ("C4 反证", "C5 反证", "C6 反证"):
        check("★ A-harness 含反证「%s」" % tag, tag in out, "")


# ═══════════════════════════════════════════════════════════════════
# B 组：服务端侧 —— player.js 里确实有 stats 请求 / flush 的接线
# ═══════════════════════════════════════════════════════════════════
def test_player_js_wiring() -> None:
    print("\n[B] ★ 服务端侧接线核对（player.js 真源码）")
    with open(os.path.join(ROOT, "extension", "player.js"),
              "r", encoding="utf-8") as f:
        src = f.read()
    check("★ B1 player.js 里有 pollStats 函数",
          "function pollStats(" in src, "")
    check("★ B2 pollStats 真的发 {'type':'stats'}",
          "{ type: 'stats' }" in src, "")
    check("★ B3 player.js 里有 flushUplink 函数",
          "function flushUplink(" in src, "")
    check("★ B4 flushUplink 真的发 {'type':'flush'}",
          "{ type: 'flush' }" in src, "")
    check("★ B5 startStatsPolling 在 boot 里被调用（否则轮询不启动）",
          "startStatsPolling();" in src, "")
    check("★ B6 录音接在 dubBus 上（player 实际播出的配音）",
          "dubBus.connect(dest);" in src, "")
    # ★ player.html 必须有「停止并收尾」按钮（flush 的入口）
    with open(os.path.join(ROOT, "extension", "player.html"),
              "r", encoding="utf-8") as f:
        html = f.read()
    check("★ B7 player.html 有「停止并收尾」按钮",
          'id="btnFlush"' in html, "")


# ═══════════════════════════════════════════════════════════════════
# C 组：E2E 脚本的段级日志解析口径 —— 用**真实日志样本**测
# ═══════════════════════════════════════════════════════════════════
# ★ 这是一份**真实**的 bridge.log 片段（2026-10-31 18:10 那一轮真实三引擎跑批）
REAL_LOG_SAMPLE = """[bridge 18:10:00] ✅ 模型加载完成（ASR/MT/TTS 就绪，耗时 16.49 秒）
[bridge 18:10:10] 已通过首个 hello 消息鉴权（role=player）
[bridge 18:10:15] 已有活跃会话 ⇒ 本连接不顶替（缺陷 15 修复：避免落盘空统计）
[bridge 18:10:33] 段 seg_72344844_0 | t_start=0.000 t_end=12.150 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
[bridge 18:10:54] 段 seg_72344844_194400 | t_start=12.150 t_end=24.410 | ASR='在循环一种痛楚，按压一秒都不能停，必须马上上衣，披上才喜欢，…' | MT='在循环一种痛楚，按压一秒都不能停，必须马上上衣，披上才喜欢，…' | TTS=9.04s | 下发到=player,uplink
[bridge 18:11:10] 段 seg_72344844_390560 | t_start=24.410 t_end=36.570 | ASR='开启就要六万，能不能救回来谁也没你，绝望中无尽四处筹钱，家人…' | MT='开启就要六万，能不能救回来谁也没你，绝望中无尽四处筹钱，家人…' | TTS=10.56s | 下发到=player,uplink
[bridge 18:11:15] 段 seg_72344844_585120 | t_start=36.570 t_end=48.720 | ASR='一份信任，可只要还剩一丝希望，他就愿意为了我，他们说' | MT='一份信任，可只要还剩一丝希望，他就愿意为了我，他们说' | TTS=5.12s | 下发到=player,uplink
[bridge 18:11:34] 段 seg_72344844_779520 | t_start=48.720 t_end=60.870 | ASR='想就是你一生的，拼尽全力脱下白兰卡，他们也是别人的父母，谁忍…' | MT='想就是你一生的，拼尽全力脱下白兰卡，他们也是别人的父母，谁忍…' | TTS=11.76s | 下发到=player,uplink
[bridge 18:11:34] 段 seg_72344844_973920 | t_start=60.870 t_end=73.020 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
[bridge 18:11:44] 段 seg_72344844_1168320 | t_start=73.020 t_end=85.170 | ASR='—' | MT='—' | TTS=0.00s | 下发到=player,uplink
"""


def test_e2e_log_parser() -> None:
    print("\n[C] ★ E2E 段级日志解析口径（用真实日志样本）")
    sys.path.insert(0, os.path.join(ROOT, "tests", "smoke"))
    try:
        import ext026_e2e as E
    except Exception as e:
        check("★ 能 import tests/smoke/ext026_e2e.py", False,
              "%s: %s" % (type(e).__name__, e))
        return

    summary: dict = {}
    # ★ 用真实样本喂解析器（解析器读文件 ⇒ 先写成临时文件）
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".log")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(REAL_LOG_SAMPLE)
        E._summarize.__globals__["OUT_DIR"] = os.path.dirname(path)
        # ★ _summarize 固定读 <out_dir>/bridge.log ⇒ 换个目录名
        d = os.path.dirname(path)
        tgt = os.path.join(d, "bridge.log")
        with open(tgt, "w", encoding="utf-8") as f:
            f.write(REAL_LOG_SAMPLE)
        E._summarize(d, summary)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    bl = summary.get("bridge_log", {})
    check("★ C1 解析出 7 段（样本里就是 7 行段级日志）",
          bl.get("n_segment_lines") == 7,
          "实测 %s" % bl.get("n_segment_lines"))
    check("★ C2 7 段全部「下发到」含 player",
          bl.get("n_segments_to_player") == 7,
          "实测 %s" % bl.get("n_segments_to_player"))
    check("★ C3 其中 4 段有真实 TTS 音频",
          bl.get("n_segments_with_tts") == 4,
          "实测 %s" % bl.get("n_segments_with_tts"))
    check("★ C4 另外 3 段是空段（ASR/MT 为空 ⇒ TTS=0.00s）",
          bl.get("n_segments_empty") == 3,
          "实测 %s" % bl.get("n_segments_empty"))
    check("★ C5 TTS 时长合计 = 9.04+10.56+5.12+11.76 = 36.48 s",
          abs((bl.get("tts_speech_total_sec") or 0) - 36.48) < 0.01,
          "实测 %s" % bl.get("tts_speech_total_sec"))
    check("★ C6 识别出 1 次「不顶替」",
          bl.get("n_not_replaced") == 1,
          "实测 %s" % bl.get("n_not_replaced"))
    check("★ C7 识别出 0 次 10048",
          bl.get("n_port_10048") == 0,
          "实测 %s" % bl.get("n_port_10048"))
    check("★ C8 段级日志行被完整保留（可给 reviewer 逐行核对）",
          len(bl.get("segment_lines") or []) == 7,
          "实测 %d" % len(bl.get("segment_lines") or []))


def main() -> int:
    print("=" * 68)
    print("EXT-026 自测：stats 轮询 / flush 收尾 / 配音录音 / 段级日志解析")
    print("=" * 68)
    for fn in (test_plugin_e2e_behaviors_harness,
               test_player_js_wiring,
               test_e2e_log_parser):
        try:
            fn()
        except Exception:
            traceback.print_exc()
            check("★ %s 未抛异常" % fn.__name__, False, "见上方 traceback")

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 68)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
