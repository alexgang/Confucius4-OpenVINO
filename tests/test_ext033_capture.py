# -*- coding: utf-8 -*-
"""test_ext033_capture.py — EXT-033 A/B/D「扩展侧改动」的自测

## 这个文件要验什么

EXT-033 [BLOCKING] 2026-11-02 09:22 要求插件侧做到：
* **A**：只抓页面元素/标签页音频（**不再用 getDisplayMedia 的整机声交卷**）；
* **B**：player 录音**完整**（≥75 s、不截断），另存**无损 WAV**；
* **D**：sync_err 是 **player 端实测的有符号误差**（不是 `max(0, …)`）。

## 为什么这些「静态」检查值得写

本轮真的被两个**不写自测就一定会再犯**的坑绊住：

① **manifest 的 `commands.suggested_key` 带 Alt ⇒ 整个浏览器起不来。**
   Chrome 判 `Invalid value for 'commands[1].default': Ctrl+Alt+Y`
   ⇒ 扩展加载失败 ⇒ Edge 弹「无法加载该扩展」**模态框** ⇒ 浏览器 UI 卡死
   ⇒ CDP 永不就绪 ⇒ 现场只剩一句没头没脑的 "CDP 未就绪"。
   ⇒ 自测必须**把这条规则钉死**：`_execute_action` 的键值**不得含 Alt**。

② **AudioWorklet 的采集开关没送进 worklet ⇒ PCM 一块都没抓到。**
   主线程把 `dubPcmActive` 置 true 了，但 worklet 内部 `this.active` 仍是 false
   ⇒ `pcmChunks=0` ⇒ WAV 是空的 ⇒ 现象只是「WAV 没内容」。
   ⇒ 自测必须断言「开关通过 port 消息送进 worklet」。

③ **录音 stop 后立刻取 blob ⇒ 文件被截断**（EXT-032 的
   `File ended prematurely at pos 86970`）。
   ⇒ 自测必须断言存在「等 `dataavailable` + `onstop`」的异步停止路径。

④ **sync_err 必须是 player 端实测的有符号值** ⇒ 必须存在
   `actual − (t0 + t_start + D)` 的算式，且**不能**夹到 0。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器（纯静态 + 纯函数）。

运行：
    python tests/test_ext033_capture.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "extension")

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  (%s)" % detail) if detail else ""))


def _read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def main() -> int:
    print("=== EXT-033 A/B/D 扩展侧自测（静态 + 纯规则）===")

    # ── ① manifest：`_execute_action` 的键值**不得含 Alt** ──
    man_path = os.path.join(EXT, "manifest.json")
    man = json.loads(_read(man_path))
    cmds = man.get("commands") or {}
    check("① manifest 里有 commands._execute_action",
          "_execute_action" in cmds, str(list(cmds)))
    key = ((cmds.get("_execute_action") or {}).get("suggested_key") or {})
    all_keys = [str(v) for v in key.values()]
    check("① 快捷键**不含 Alt**（含 Alt ⇒ 扩展加载失败 ⇒ 浏览器起不来）",
          all("alt" not in k.lower() for k in all_keys), str(all_keys))
    check("① 快捷键含 Ctrl/Shift 修饰键（Chrome 只认这些）",
          all(("ctrl" in k.lower()) for k in all_keys), str(all_keys))
    check("① manifest 仍是合法 JSON 且 manifest_version=3",
          man.get("manifest_version") == 3)
    check("① tabCapture 权限仍在（生产路径没被删）",
          "tabCapture" in (man.get("permissions") or []),
          str(man.get("permissions")))

    # ── ② PCM worklet：采集开关**必须**经 port 送进 worklet ──
    wl_path = os.path.join(EXT, "dub-pcm-worklet.js")
    check("② 存在 extension/dub-pcm-worklet.js", os.path.isfile(wl_path))
    wl = _read(wl_path) if os.path.isfile(wl_path) else ""
    check("② worklet 注册了 'dub-pcm-processor'",
          "registerProcessor('dub-pcm-processor'" in wl)
    check("② worklet 监听 port 消息（start/stop）",
          "this.port.onmessage" in wl and "'start'" in wl and "'stop'" in wl)
    check("② worklet 的采集标志由消息驱动（this.active）",
          "this.active = true" in wl and "this.active = false" in wl)
    check("② worklet 直通音频（不改变用户听到的声音）",
          "output" in wl and "o0[i] = ch0[i]" in wl)

    # ── ③ player.js：录音完整性 + WAV + 有符号 sync_err + t0 轴 ──
    p_path = os.path.join(EXT, "player.js")
    pl = _read(p_path)
    check("③ 有异步停止路径 stopDubRecordingAsync（等 onstop）",
          "function stopDubRecordingAsync" in pl)
    check("③ 异步停止确实等 onstop 事件",
          "dubRecorder.onstop" in pl and "onstop =" in pl)
    check("③ 有 WAV 打包（PCM → 16-bit WAV）",
          "pcmToWavBase64" in pl and "RIFF" in pl and "fmt " in pl)
    check("③ 录音开始时通知 worklet 采集",
          "postMessage({ cmd: 'start' })" in pl)
    check("③ 录音停止时通知 worklet 并冲尾巴",
          "postMessage({ cmd: 'stop' })" in pl)
    check("③ sync_err 是**有符号**的（没有被 max(0,…) 夹掉）",
          "signedErrMs = (at - p.requested) * 1000" in pl)
    check("③ sync_err 用的是 requested = t0 + t_start + D",
          "requested: planned" in pl and "t_start" in pl)
    check("③ 迟到量单独列出（lateMs），不代替 signedErrMs",
          "lateMs" in pl)
    check("③ t0 轴改成 audio_clock（抓流样本 0 的音频时钟位置）",
          "t0Axis = 'audio_clock'" in pl and "off16 / 16000" in pl)
    # ★★★ EXT-033 D 修正：t0 必须换算到 **player AudioContext 域**
    #   （`planned`/`when`/`at` 都在 player 域；`audioFrame16` 来自 uplink 域）。
    #   ⇒ 必须存在 uplink↔player 的原点差测量与换算。
    check("③ t0 换算到 player 域（uplink↔player 原点差）",
          "upState.ac.currentTime - audioCtx.currentTime" in pl
          and "t0 = t0Up + dOff" in pl)
    check("③ t0 换算前的上行域原值被保留（可自证）",
          "t0UpSec" in pl and "t0UpPlayerOffsetSec" in pl)
    check("③ 新指标进了上报白名单（跨上下文可见）",
          "'dubSyncP50'" in pl and "'t0Axis'" in pl)
    check("③ __ext 导出了新接口",
          "stopDubRecordingAsync," in pl and "dubRecordingWav," in pl
          and "dubSyncStats:" in pl)

    # ── ④ 抓流方式必须**如实**上报（不能写死）──
    check("④ captureMode 由实际路径决定（不是写死 getDisplayMedia）",
          "upState.captureMode = captureMode || 'getDisplayMedia'" in pl)
    check("④ tabCapture 错误原文仍被记录（降级可追因）",
          "tabCaptureError" in pl)

    # ── ⑤ harness：输入必须是「页面元素」而不是整机 ──
    h_path = os.path.join(ROOT, "tests", "smoke", "ext033_e2e.py")
    hs = _read(h_path) if os.path.isfile(h_path) else ""
    check("⑤ e2e 用 createMediaElementSource 抓页面元素",
          "createMediaElementSource" in hs)
    check("⑤ e2e 把抓到的流送进扩展上行链路（startUplink）",
          "startUplink" in hs)
    check("⑤ e2e 的 http 服务带 CORS（否则 WebAudio 拿到静音）",
          "Access-Control-Allow-Origin" in hs)
    check("⑤ e2e **不调用** getDisplayMedia（整机声不能交卷）",
          "getDisplayMedia(" not in hs)
    check("⑤ e2e 录音时长下限 ≥ 75 s",
          re.search(r"MIN_RECORDING_SEC\s*=\s*75", hs)
          or re.search(r"MIN_REC_SEC\s*=\s*75", hs) is not None)

    # ── ⑥ analyzer：阈值必须与 EXT-033 原文一致 ──
    a_path = os.path.join(ROOT, "tests", "smoke", "ext033_analyze.py")
    ans = _read(a_path) if os.path.isfile(a_path) else ""
    for label, pat in (("时长比容差 0.02", r"DUR_RATIO_TOL\s*=\s*0\.02"),
                       ("互相关峰门槛 0.6", r"XCORR_PEAK_MIN\s*=\s*0\.6"),
                       ("sync 目标 300 ms", r"SYNC_ERR_TARGET_MS\s*=\s*300"),
                       ("录音下限 75 s", r"MIN_RECORDING_SEC\s*=\s*75"),
                       ("开口静音上限 15 s", r"MAX_LEADING_SILENCE_SEC\s*=\s*15")):
        check("⑥ analyzer 阈值：%s" % label,
              re.search(pat, ans) is not None)
    check("⑥ analyzer 用细粒度（10 ms）有声跨度检测（250 ms 判不了 ±2%）",
          "VOICE_WIN_MS = 10" in ans)

    # ── ⑦ ★★★ EXT-033 真实 e2e 抓到的两个新缺陷（回归防护）──────────
    #
    # ⑦-1 **t0 跨时钟域**：t0 曾在 **uplink** AudioContext 域算出，
    #      却被 **player** 域消费（`planned`/`when`/`at`）⇒ 系统性偏差
    #      ⇒ 实测 13 段全部被钳成「立即播」（`schedClamped=13`）
    #      ⇒ 有符号误差**恒为正**，量不出「早播」。
    #      ⇒ 必须存在 uplink↔player 的原点差测量与换算。
    # ⑦-2 **设备互斥恒失效**：`_caption_app_running()` 依赖 psutil，
    #      而 bridge 实际跑在 **App 自带的 python** 里（**没有 psutil**）
    #      ⇒ 恒返回 False ⇒ 字幕 App 与本模块同时抢 GPU.0 + NPU。
    #      ⇒ 必须**不依赖 psutil**。
    b_path = os.path.join(ROOT, "ext", "bridge.py")
    br = _read(b_path) if os.path.isfile(b_path) else ""
    # ★ 用 **AST** 精确取「函数体里真正执行的代码」
    #   （跳过 docstring 与注释）——
    #   注释里提到 psutil 是在说明「为什么不用它」，
    #   但若**代码**里再 import psutil ⇒ 互斥又会恒失效。
    _imports_psutil = False
    try:
        import ast
        _tree = ast.parse(br)
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.FunctionDef) \
                    and _n.name == "_caption_app_running":
                for _m in ast.walk(_n):
                    if isinstance(_m, ast.Import):
                        for _a in _m.names:
                            if _a.name.split(".")[0] == "psutil":
                                _imports_psutil = True
                    elif isinstance(_m, ast.ImportFrom) \
                            and (_m.module or "").split(".")[0] == "psutil":
                        _imports_psutil = True
    except Exception:
        pass
    check("⑦ 设备互斥不依赖 psutil（App 自带 python 里没有 psutil）",
          br != "" and not _imports_psutil)
    check("⑦ 设备互斥按 App 真实入口匹配（不靠路径里出现 LiveCaption）",
          "bridgelauncher.py" in br and "livecaptionapp.py" in br)
    check("⑦ 设备互斥拿不到进程列表时保守处理（探测失败≠没在跑）",
          "_caption_app_probe_failed" in br)

    # ── ⑧ ★ t0 换算的**可执行等价物**必须存在（浏览器实测探针）──
    #   理由：换算是纯数学，但「两个 AudioContext 的原点确实不同」
    #   只有在**真实浏览器**里才能证 ⇒ 必须有一个能跑的探针，
    #   否则以后有人把换算删了，静态断言可能仍然通过。
    v_path = os.path.join(ROOT, "tests", "smoke", "ext033_t0_verify.py")
    vv = _read(v_path) if os.path.isfile(v_path) else ""
    check("⑧ t0 换算有**浏览器实测**探针（真实 AudioContext 两域）",
          os.path.isfile(v_path)
          and "new AudioContext" in vv
          and "up.currentTime - player.currentTime" in vv)
    check("⑧ 探针带反证（不换算就会引入 |Δ| 误差）",
          "反证" in vv)
    # ★ player.js 必须把 Δ 的**抖动幅度**记进 metrics（换算精度可自证）
    check("⑧ t0 换算的抖动幅度进 metrics（精度可自证）",
          "t0UpPlayerOffsetSpreadSec" in pl)

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print("=== %d PASS / %d FAIL ===" % (len(RESULTS) - n_fail, n_fail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
