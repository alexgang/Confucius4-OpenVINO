# -*- coding: utf-8 -*-
"""test_ext041_media_slowdown.py — EXT-041 的自测（媒体轻微降速机制）

## EXT-041 原文（2026-11-06，[HIGH]）

> 用户决定：**放宽** "signed P95 ≤ 0.3 s" 目标；改为下面的新验收口径
>
> ### 新目标（在 ≥150 s 素材上测，报 N）
> 1. signed P95 ≤ **1.5 s**，signed P50 ≤ 0.8 s（原来是 P95 ≤ 0.3 s）。
> 2. **不能无限累积**：signed_err 对时间的斜率 ≤ 0.01 s/s。也就是 10 分钟内额外漂移
>    不超过约 6 s，并且全程不耗尽缓冲。
> 3. 不能丢句、不能重复、不能出现异常静音。变速不超过现有上限 1.3×，不提高变速上限。
>
> ### 可选机制（自选并 A/B，在 STATUS 写理由）
> - **视频轻微降速**：按实测的 tts_over_src 自适应设置 `video.playbackRate`，
>   例如 0.92–0.95，下限 0.9，让画面追配音。在插件里给用户一个开关，默认开。
> - **积压时收紧**：…改译文要和 MT 侧对齐…
> - D 可以在 20 s 附近调；改了要说明。

## 本文件要验什么

① **决策函数（`ext/media_slowdown.py`）的数学正确性**
   - 临界倍率 `r* = 1/tts_over_src`；
   - 斜率口径 = `r · speech_over_src − 1`（**不是** `tor − 1/r`，量纲不同）；
   - 落到实测值 `tor=1.0936 / sos=1.0942` ⇒ 斜率 ≤ 0.01 s/s；
② **倍率规则**：`r = clamp(1/tor, 0.90, 1.00)`，
   **不是** `min(default, 1/tor)`（后者在 `tor→1` 时会产生**反向漂移**）；
③ **边界**：下限 0.90 / 上限 1.00（**永不加速**）/ `tor ≤ 1` 不降速；
④ **插件侧接线完整性**：`popup.js`（用户手势 ⇒ activeTab ⇒ 可注入）、
   `slowdown.js`（内容脚本）、`player.js`（只读实测 + 周期刷新）、
   `bridge.py`（分列「建议」与「客户端实测」）；
⑤ ★ **区分力**：改坏上面任一处 ⇒ 判定必须转为 FAIL
   （否则就是"永远 PASS"的假守卫）。

不跑推理 / 不占 GPU·NPU / 不创建共享锁 / 不启动浏览器 / 不需要 e2e。

运行：
    python tests/test_ext041_media_slowdown.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ext.media_slowdown import (  # noqa: E402
    RATE_CEIL, RATE_DEFAULT, RATE_FLOOR, SLOPE_TARGET,
    effective_rate_for_ratio, rate_for,
)

MEDIA_PY = os.path.join(ROOT, "ext", "media_slowdown.py")
PLAYER = os.path.join(ROOT, "extension", "player.js")
POPUP_JS = os.path.join(ROOT, "extension", "popup.js")
POPUP_HTML = os.path.join(ROOT, "extension", "popup.html")
SLOWDOWN_JS = os.path.join(ROOT, "extension", "slowdown.js")
BRIDGE = os.path.join(ROOT, "ext", "bridge.py")

RESULTS = []

#: 上一轮 run `20261105_174558` 的**实测**原始字段（margin.json 的 rtf_breakdown）
MEAS_TOR = 1.0936       # tts_over_src  = Σtts_sec ÷ Σ源音频秒
MEAS_SOS = 1.0942       # speech_over_src = Σspeech_sec ÷ Σ源音频秒


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                            ("  -- %s" % detail) if detail else ""))


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_js_comments(src: str) -> str:
    """去掉 JS 的行注释与块注释（**保留字符串字面量里的内容**）。

    ★ 为什么需要：EXT-043 C1 的**说明注释**里引用了旧的 bug 写法
      （`replace(/^https?:\\/\\/[^/]+/, '')`）⇒ 不剥离注释的话
      守卫会**误判**成「代码里还有 bug 写法」。

    ★ 实现注意：块注释内**不做字符串解析**（注释里出现反引号
      ——例如 markdown 代码块 ```js ——不能当成字符串开始）。
    """
    out = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ''
        if ch == '/' and nxt == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if ch == '/' and nxt == '*':
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
            out.append(' ')
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = src[i]
                out.append(c)
                if c == '\\':
                    if i + 1 < n:
                        out.append(src[i + 1])
                        i += 2
                        continue
                elif c == quote:
                    i += 1
                    break
                i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


#: EXT-043 C1 的 bug 特征：把 `host:port` 整段删掉的 host 提取写法
_C1_BUG_PATTERN = "replace(/^https?:\\/\\/[^/]+/, '')"


#: ★ 执行级探针（node）：EXT-043 C1/C2 的**决定性证据**
PROBE_JS = os.path.join(ROOT, "tests", "ext041_slowdown_probe.js")


def run_probe() -> dict:
    """跑 node 执行级探针，返回解析后的 JSON（失败时返回带 error 的 dict）。

    ★ 为什么必须有执行级证据：
      EXT-043 C1 的**说明注释**里**故意**引用了旧的 bug 写法
      （给后人看「原来错在哪」）⇒ 任何「全文/文本匹配」都会被注释骗过。
      ⇒ 只有**真跑一遍 JS** 才能证明修好了。
      ★ 而且这一步**真的抓出了两个真 bug**（node 探针首次运行就报
        `appliedRate is not defined` + Python 取模残留 ⇒ NaN）。
    """
    import json
    import subprocess
    try:
        p = subprocess.run(
            ["node", PROBE_JS],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": "node 执行失败：%s" % e}
    if p.returncode != 0:
        return {"error": "node 退出码 %d：%s" % (p.returncode, (p.stderr or "")[:400])}
    try:
        return json.loads(p.stdout)
    except Exception as e:  # noqa: BLE001
        return {"error": "探针输出不是合法 JSON：%s / %s"
                         % (e, (p.stdout or "")[:400])}


def _c1_bug_in_code(src: str) -> bool:
    """C1 的旧写法是否**仍在可执行代码**里（注释里不算）。

    ★ 这是**辅助**判断（文本级）；**决定性**证据是 `run_probe()` 的
      C1 部分（真跑 `pairStatusUrl()`，看拼出来的 URL 能不能被解析）。
    ★ 判定办法：
      ① 先剥离**块注释**与**行注释**；
      ② 再看剩下的代码里有没有那个 bug 写法。
    ★ 剥离器的已知坑（都实测踩过并修掉）：
      * 块注释内不做字符串解析（注释里可能有反引号）；
      * 只把 ASCII 引号当字符串定界符（中文引号不是）。
    """
    # ① 去掉行注释（保留字符串内的 // —— 用简易状态机）
    stripped = _strip_js_comments(src)
    # ② 还要去掉字符串字面量里的内容（字符串里也可能出现该文本）
    return _C1_BUG_PATTERN in _strip_string_literals(stripped)


def _strip_string_literals(src: str) -> str:
    """把 JS 的字符串字面量内容替换成空串（保留结构字符）。"""
    out = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            while i < n:
                c = src[i]
                if c == '\\':
                    i += 2
                    continue
                if c == quote:
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


# ══════════════════════════════════════════════════════════════
# ① 决策函数的数学
# ══════════════════════════════════════════════════════════════
def test_math():
    print("\n① 决策函数数学（ext/media_slowdown.py）")

    # ①-1 临界倍率 = 1 / tts_over_src
    d = rate_for(MEAS_TOR, speech_over_src=MEAS_SOS)
    check("临界倍率 = 1/tor",
          abs(d.r_critical - 1.0 / MEAS_TOR) < 1e-9,
          "r_critical=%.6f 期望=%.6f" % (d.r_critical, 1.0 / MEAS_TOR))

    # ①-2 斜率口径 = r·sos − 1（**不是** tor − 1/r）
    #   ⚠️ 必须在**非临界倍率**上验证：临界倍率处两口径都 ≈ 0 ⇒ 无区分力。
    #   ⇒ 用 `default_rate`（0.92）路径：`tor=None` 时取默认倍率，
    #     但 `speech_over_src` 仍会传进去 ⇒ 斜率照样可算。
    d_probe = rate_for(None, speech_over_src=MEAS_SOS)
    expect = d_probe.rate * MEAS_SOS - 1.0
    check("斜率口径 = r·sos − 1",
          d_probe.est_slope is not None
          and abs(d_probe.est_slope - expect) < 1e-9,
          "r=%.2f 时 est_slope=%.6f 期望=%.6f"
          % (d_probe.rate, d_probe.est_slope, expect))

    # ①-3 实测值下斜率达标（EXT-041 新口径 ≤ 0.01 s/s）
    check("实测 tor=1.0936 ⇒ 斜率 ≤ %.2f s/s" % SLOPE_TARGET,
          d.est_slope is not None and d.est_slope <= SLOPE_TARGET,
          "斜率=%.6f s/s，倍率=%.4f" % (d.est_slope, d.rate))

    # ①-4 ★ 反证：旧口径 tor − 1/r 与新口径 r·sos − 1 **不是恒等**
    #   ⚠️ 输入要选对：两口径在 `tor ≈ sos` 时**几乎相等**
    #     （实测 tor=1.0936 / sos=1.0942 ⇒ r=0.92 时只差 2.05e-05）
    #     ⇒ 在实测点上比**没有区分力**。
    #   ⇒ 选 `tor` 明显偏离 `sos` 的场景（tor=1.02、r=0.92）：
    #     旧口径 −0.066957（负！反向漂移）vs 新口径 +0.006664 ⇒ 差 0.0736。
    r_probe = 0.92
    wrong = 1.02 - 1.0 / r_probe
    right = r_probe * MEAS_SOS - 1.0
    check("★ 反证：旧口径 tor−1/r ≠ 本实现口径（非恒等）",
          abs(wrong - right) > 1e-2,
          "tor=1.02, r=0.92 时 旧口径=%.6f vs 新口径=%.6f（差 %.4f）"
          % (wrong, right, abs(wrong - right)))

    # ①-5 终值落后 = S·(sos − 1/r)，在实测 S 上应 ≈ 0（持平）
    S = 179.850   # Σ源音频秒（run 20261105_174558 实测）
    lag_end = S * (MEAS_SOS - 1.0 / d.rate)
    check("终值落后 ≈ 0（不堆积）",
          abs(lag_end) < 1.0,
          "lag_end=%.3f s（S=%.3f）" % (lag_end, S))

    # ①-6 有效倍率反推：tts_over_src = RTF_out × speech_over_src
    #   ⚠️ 阈值要留出**四舍五入余量**：实测值只保留 4 位小数
    #   （RTF_out=0.9994 × sos=1.0942 = 1.093607 vs 实测 tor=1.093600）。
    d2 = effective_rate_for_ratio(MEAS_SOS, 0.9994)
    check("有效倍率反推一致（RTF_out×sos）",
          abs(d2.rate - d.rate) < 1e-3,
          "反推=%.6f 直接=%.6f（容差 1e-3）" % (d2.rate, d.rate))


# ══════════════════════════════════════════════════════════════
# ② 倍率规则（★ 与旧规则的关键差异）
# ══════════════════════════════════════════════════════════════
def test_rate_rule():
    print("\n② 倍率规则与边界")

    # ②-1 ★ 取临界倍率（不是 min(default, r*)）
    d = rate_for(MEAS_TOR, speech_over_src=MEAS_SOS)
    check("取临界倍率 1/tor（不是 min(default, r*)）",
          abs(d.rate - 1.0 / MEAS_TOR) < 1e-9,
          "rate=%.6f 期望=%.6f" % (d.rate, 1.0 / MEAS_TOR))

    # ②-2 ★ tor 接近 1 时**不能**反向漂移（旧规则的真缺陷）
    d2 = rate_for(1.02, speech_over_src=1.02)
    old_rule_rate = min(RATE_DEFAULT, 1.0 / 1.02)   # 旧规则
    old_slope = old_rule_rate * 1.02 - 1.0
    check("★ tor→1 时不反向漂移（旧规则 slope=%.4f）" % old_slope,
          d2.est_slope is not None and d2.est_slope >= -1e-9,
          "新规则 rate=%.6f slope=%+.6f" % (d2.rate, d2.est_slope))

    # ②-3 下限 0.90：tor 太大时取下限，并**如实说明救不了**
    d3 = rate_for(1.15, speech_over_src=1.15)
    check("tor=1.15 ⇒ 取下限 0.90 且如实说明",
          abs(d3.rate - RATE_FLOOR) < 1e-9 and "救不了" in d3.reason,
          "rate=%.4f reason=%s" % (d3.rate, d3.reason))

    # ②-4 上限 1.00：永不加速
    d4 = rate_for(0.5, speech_over_src=0.5)
    check("tor ≤ 1 ⇒ 不降速（rate=1.0）",
          abs(d4.rate - 1.0) < 1e-9 and not d4.needs_slowdown,
          "rate=%.4f" % d4.rate)

    # ②-5 无实测值 ⇒ 保守用默认 0.92，**不臆造**
    d5 = rate_for(None)
    check("无实测值 ⇒ 保守用默认 %.2f" % RATE_DEFAULT,
          abs(d5.rate - RATE_DEFAULT) < 1e-9 and d5.tts_over_src is None,
          "rate=%.4f" % d5.rate)

    # ②-6 开关关闭 ⇒ rate=1.0（不降速）
    d6 = rate_for(MEAS_TOR, enabled=False)
    check("用户关闭开关 ⇒ 不降速",
          abs(d6.rate - 1.0) < 1e-9 and not d6.needs_slowdown,
          "rate=%.4f" % d6.rate)

    # ②-7 永远不超上限
    for tor in (1.0001, 1.01, 1.05, 1.0936, 1.11, 1.5, 5.0):
        r = rate_for(tor, speech_over_src=tor).rate
        if not (RATE_FLOOR - 1e-9 <= r <= RATE_CEIL + 1e-9):
            check("倍率始终落在 [%.2f, %.2f]" % (RATE_FLOOR, RATE_CEIL),
                  False, "tor=%.4f ⇒ rate=%.4f 越界" % (tor, r))
            return
    check("倍率始终落在 [%.2f, %.2f]" % (RATE_FLOOR, RATE_CEIL),
          True, "扫描 7 个 tor 全部合规")

    # ②-8 非法输入不崩
    d8 = rate_for(-1.0)
    check("非法 tor（≤0）⇒ 不降速且不崩",
          abs(d8.rate - 1.0) < 1e-9, "rate=%.4f" % d8.rate)


# ══════════════════════════════════════════════════════════════
# ③ 插件侧接线完整性
# ══════════════════════════════════════════════════════════════
def test_wiring():
    print("\n③ 插件侧接线完整性")

    phtml = read(POPUP_HTML)
    pjs = read(POPUP_JS)
    pplayer = read(PLAYER)
    pslow = read(SLOWDOWN_JS)
    pbridge = read(BRIDGE)

    # ③-1 popup.html 有开关且**默认勾选**
    m = re.search(r'<input[^>]*id="slowdown"[^>]*>', phtml)
    check("popup.html 有「slowdown」开关", m is not None,
          m.group(0) if m else "未找到")
    if m:
        check("开关**默认勾选**（reviewer：默认开）",
              "checked" in m.group(0), m.group(0))

    # ③-2 popup.js 三处接线
    check("popup.js readCfg() 含 slowdownOn",
          re.search(r"slowdownOn:\s*\$\('slowdown'\)\.checked", pjs) is not None)
    check("popup.js 默认值含 slowdownOn: true",
          re.search(r"slowdownOn:\s*true", pjs) is not None)
    check("popup.js 回填含 $('slowdown').checked",
          re.search(r"\$\('slowdown'\)\.checked\s*=", pjs) is not None)
    check("popup.js 持久化监听含 'slowdown'",
          re.search(r"const ids = \[[^\]]*'slowdown'", pjs, re.S) is not None)

    # ③-3 ★ popup 必须**注入**内容脚本（activeTab 权限在 popup 手势上下文）
    check("popup.js 注入 slowdown.js（executeScript）",
          "chrome.scripting.executeScript" in pjs
          and "slowdown.js" in pjs)
    check("popup.js 起流时调用 setupMediaSlowdown",
          "setupMediaSlowdown(" in pjs
          and re.search(r"setupMediaSlowdown\(tab\.id", pjs) is not None)

    # ③-4 ★ 停止时必须恢复 playbackRate = 1.0
    check("★ popup.js 停止时恢复 playbackRate=1.0",
          "reset-rate" in pjs)

    # ③-5 slowdown.js：钳位 + 永不加速 + 无媒体元素时如实报 false
    check("slowdown.js 钳位到 [0.90, 1.00]",
          "RATE_FLOOR" in pslow and "RATE_CEIL" in pslow
          and re.search(r"Math\.max\(RATE_FLOOR,\s*Math\.min\(RATE_CEIL", pslow)
          is not None)
    check("slowdown.js 无媒体元素 ⇒ applied=false（不假装成功）",
          re.search(r"没有 <video>/<audio>", pslow) is not None
          and re.search(r"applied:\s*false", pslow) is not None)
    check("★ slowdown.js 无 Python 语法残留（len(media)）",
          "len(media)" not in pslow,
          "len(media) 是 Python 写法，JS 里会 ReferenceError")

    # ③-5b ★★ EXT-043 C2：二次注入必须**幂等**（旧实现会撞名抛错）
    _slow_code = _strip_js_comments(pslow)
    check("★ C2 slowdown.js 包在 IIFE 里（顶层 const 会撞名）",
          re.search(r"^\(function\s*\(\)\s*\{", _slow_code.strip(), re.M)
          is not None,
          "顶层 const RATE_FLOOR ⇒ 二次注入报 Identifier has already been declared")
    check("★ C2 slowdown.js 有幂等守卫 __extSlowdownInstalled",
          "__extSlowdownInstalled" in _slow_code)
    check("★ C2 slowdown.js 递归同源 iframe",
          re.search(r"querySelectorAll\('iframe'\)", _slow_code) is not None
          and "contentDocument" in _slow_code)

    # ③-5c ★★ EXT-043 C1：/status 的 URL 不能是 `http://:8766`
    check("★ C1 player.js 有 pairStatusUrl()（不再手拼 host）",
          "function pairStatusUrl" in pplayer)
    check("★ C1 player.js 用 pairStatusUrl() 取 /status",
          re.search(r"pairStatusUrl\(cfg\.wsUrl\)", pplayer) is not None)
    # ★★ 文本级**辅助**判断：旧 bug 写法**不应**再出现在可执行代码里
    check("★ C1 player.js 不再手拼 host（文本级辅助）",
          not _c1_bug_in_code(pplayer),
          "该写法会把 host:port 整段删掉 ⇒ 拼出 http://:8766/status")
    check("★ C1 popup.js 用 pairUrl() 取 /status",
          re.search(r"fetch\(`\$\{base\}/status`", read(POPUP_JS)) is not None)

    # ③-6 player.js：只读实测 + 周期刷新（不自己注入——没有 activeTab）
    check("player.js 有 readSlowdownRecord()",
          "async function readSlowdownRecord" in pplayer)
    check("player.js 有周期刷新 refreshSlowdownRecommendation()",
          "async function refreshSlowdownRecommendation" in pplayer)
    check("player.js 起周期定时器", "startSlowdownRefreshTimer" in pplayer)
    check("player.js 上报 slowdown 字段",
          re.search(r"slowdown:\s*\(metrics\.slowdown \|\| null\)", pplayer)
          is not None)

    # ③-7 bridge.py：建议与实测**分列**
    check("bridge.py 有 _slowdown_record()",
          "def _slowdown_record" in pbridge)
    check("bridge.py 分列 recommended_rate 与 client_applied_rate",
          "recommended_rate" in pbridge and "client_applied_rate" in pbridge)
    check("bridge.py 客户端只接受 [0.5, 1.0]（永不加速）",
          "0.5 <= _r <= 1.0" in pbridge)
    check("bridge.py /status 给出 recommended_rate",
          re.search(r'"recommended_rate":\s*_dec\.rate', pbridge) is not None)


# ══════════════════════════════════════════════════════════════
# ⑤ ★★ 执行级证据（node 探针）：EXT-043 C1/C2 的**决定性**判定
# ══════════════════════════════════════════════════════════════
def test_execution_level():
    """用 node **真跑**一遍 JS，而不是靠文本匹配。

    ★ 这一组是**决定性**证据（文本守卫降级为辅助）：
      * C1：真跑 `pairStatusUrl()` ⇒ 拼出来的 URL 必须能被 `new URL()` 解析；
      * C2：把 `slowdown.js` 在 vm 里**跑两遍** ⇒ 幂等（不撞名、不重复注册）；
      * ★ 顺带把「`appliedRate` 未声明」「Python 取模残留」这两类
        **真实跑不出来、文本却看不出来**的 bug 抓住。
    """
    print("\n⑤ ★★ 执行级证据（node 探针）")

    p = run_probe()
    check("★ 执行级探针跑通（node 可用且输出合法 JSON）",
          "error" not in p,
          str(p.get("error", ""))[:300])
    if "error" in p:
        return

    c1 = p.get("c1", {})
    check("★ C1 pairStatusUrl() 存在且被找到",
          bool(c1.get("found")))
    check("★ C1 拼出的 /status URL 全部可被 new URL() 解析",
          bool(c1.get("all_valid")),
          "旧实现拼出 http://:8766/status ⇒ Invalid URL")
    check("★ C1 拼出的 URL 主机名非空（不出现 http://:8766）",
          bool(c1.get("no_empty_host")))
    check("★ C1 配对端口 = 桥接端口 + 1",
          bool(c1.get("port_is_bridge_plus_1")))

    c2 = p.get("c2", {})
    check("★ C2 首次注入不抛错", c2.get("first_error") is None,
          str(c2.get("first_error")))
    check("★ C2 二次注入不抛错（旧实现报 Identifier has already been declared）",
          c2.get("second_error") is None, str(c2.get("second_error")))
    check("★ C2 onMessage listener 只注册 1 次（二次注入幂等）",
          c2.get("listener_count_after_first") == 1
          and c2.get("listener_count_after_second") == 1,
          "first=%s second=%s"
          % (c2.get("listener_count_after_first"),
             c2.get("listener_count_after_second")))
    check("★ C2 幂等判定成立", bool(c2.get("idempotent")))
    check("★ C2 严格模式确实生效（对照实验）",
          bool(c2.get("strict_mode_active")),
          "strict 未生效 ⇒ 抓不到「未声明变量」这类 bug")

    # ★★★ 抓「appliedRate 未声明」：所有调用都不能抛 ReferenceError
    check("★★ set-rate 不抛 ReferenceError（appliedRate 必须声明）",
          c2.get("set_rate_error") is None,
          str(c2.get("set_rate_error")))
    check("★★ set-rate 真的把 playbackRate 设成 0.92",
          bool(c2.get("rate_applied_ok")),
          "实际=%s" % c2.get("media_playback_rate"))
    # ★★★ 抓「Python 取模残留」：reason 不能出现 NaN / %d / %s
    check("★★ reason 不含 NaN（不能是 Python 取模残留）",
          not c2.get("reason_has_nan"))
    check("★★ reason 不含未替换的 %d/%s 占位符",
          not c2.get("reason_has_placeholder"))
    check("★★ reason 必须是字符串（数字说明格式化写错了）",
          bool(c2.get("reason_is_string")),
          "reason_type=%s" % c2.get("reason_type"))
    check("★ C2 永不加速（rate=1.5 ⇒ 钳到 1.00）",
          bool(c2.get("clamp_high_ok")))
    check("★ C2 下限 0.90（rate=0.5 ⇒ 钳到 0.90）",
          bool(c2.get("clamp_low_ok")))
    check("★ C2 reset-rate 恢复 1.00", bool(c2.get("reset_ok")))
    check("★ C2 非法输入如实报错（不抛异常）",
          bool(c2.get("invalid_input_ok")),
          str(c2.get("invalid_input_error")))
    check("★ C2 所有调用均无异常", bool(c2.get("all_calls_ok")))


# ══════════════════════════════════════════════════════════════
# ④ ★ 区分力（变异测试）：改坏一处 ⇒ 必须 FAIL
# ══════════════════════════════════════════════════════════════
def test_discrimination():
    print("\n④ ★ 区分力（变异测试）")

    orig_py = read(MEDIA_PY)
    orig_js = read(POPUP_JS)
    orig_slow = read(SLOWDOWN_JS)
    orig_player = read(PLAYER)

    def write(path: str, text: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    try:
        # M1：把斜率公式改回错误口径（tor − 1/r）
        #   ⚠️ 判定必须打在**非临界倍率**的探针上（0.92 路径）：
        #     在临界倍率处两口径都 ≈ 0 ⇒ 变异**抓不住** ⇒ 那是假通过。
        m1 = orig_py.replace(
            "return rate * float(sos) - 1.0",
            "return float(sos) - 1.0 / rate")
        if m1 == orig_py:
            check("M1 变异（斜率口径改错）应 FAIL", False,
                  "未找到斜率公式文本，变异未生效 ⇒ 守卫无区分力")
        else:
            write(MEDIA_PY, m1)
            try:
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)
                bad = ms.rate_for(None, speech_over_src=MEAS_SOS)
                expect = bad.rate * MEAS_SOS - 1.0
                ok = not (bad.est_slope is not None
                          and abs(bad.est_slope - expect) < 1e-9)
                check("M1 变异（斜率口径改错）⇒ 判定 FAIL",
                      ok,
                      "变异后 slope=%.6f（正确口径应为 %.6f）"
                      % (bad.est_slope, expect))
            finally:
                write(MEDIA_PY, orig_py)
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)

        # M2：把倍率规则改回 min(default, r*)（反向漂移缺陷）
        m2 = orig_py.replace(
            "rate = min(max(r_crit, RATE_FLOOR), RATE_CEIL)",
            "rate = min(max(min(default_rate, r_crit), RATE_FLOOR), RATE_CEIL)")
        if m2 == orig_py:
            check("M2 变异（倍率规则改回 min）应 FAIL", False,
                  "未找到倍率规则文本，变异未生效 ⇒ 守卫无区分力")
        else:
            write(MEDIA_PY, m2)
            try:
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)
                bad = ms.rate_for(1.02, speech_over_src=1.02)
                ok = not (bad.est_slope is not None and bad.est_slope >= -1e-9)
                check("M2 变异（倍率规则改回 min）⇒ 判定 FAIL", ok,
                      "变异后 slope=%+.6f（应 <0 才算被抓住）" % bad.est_slope)
            finally:
                write(MEDIA_PY, orig_py)
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)

        # M3：把下限从 0.90 改成 0.50（违反 reviewer 的下限）
        m3 = orig_py.replace("RATE_FLOOR = 0.90", "RATE_FLOOR = 0.50")
        if m3 == orig_py:
            check("M3 变异（下限改 0.50）应 FAIL", False, "未找到 RATE_FLOOR")
        else:
            write(MEDIA_PY, m3)
            try:
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)
                bad = ms.rate_for(1.15, speech_over_src=1.15)
                ok = abs(bad.rate - 0.90) > 1e-9
                check("M3 变异（下限改 0.50）⇒ 判定 FAIL", ok,
                      "变异后 rate=%.4f（应 ≠0.90 才算被抓住）" % bad.rate)
            finally:
                write(MEDIA_PY, orig_py)
                import importlib
                import ext.media_slowdown as ms
                importlib.reload(ms)

        # M4：把 popup 的开关默认改成 false（违反「默认开」）
        #   ⚠️ ★ **必须替换全部出现**：`slowdownOn: true` 在 popup.js 里
        #     出现**多处**（默认值、readCfg 附近…）⇒ 只替换第一处
        #     ⇒ 判定仍会 PASS ⇒ **那是假通过**（EXT-040 已踩过这个坑）。
        m4 = orig_js.replace("slowdownOn: true", "slowdownOn: false")
        if m4 == orig_js:
            check("M4 变异（默认关）应 FAIL", False, "未找到 slowdownOn: true")
        else:
            check("M4 变异覆盖了**全部**出现",
                  orig_js.count("slowdownOn: true")
                  == m4.count("slowdownOn: false"),
                  "原文 %d 处 ⇒ 变异后 %d 处"
                  % (orig_js.count("slowdownOn: true"),
                     m4.count("slowdownOn: false")))
            write(POPUP_JS, m4)
            try:
                txt = read(POPUP_JS)
                ok = (re.search(r"slowdownOn:\s*true", txt) is None)
                check("M4 变异（默认关）⇒ 判定 FAIL", ok,
                      "变异后仍检出默认值 ⇒ 守卫失效")
            finally:
                write(POPUP_JS, orig_js)

        # M5：把 slowdown.js 的钳位去掉（可能加速）
        m5 = orig_slow.replace(
            "r = Math.max(RATE_FLOOR, Math.min(RATE_CEIL, r));",
            "r = r;")
        if m5 == orig_slow:
            check("M5 变异（去掉钳位）应 FAIL", False, "未找到钳位代码")
        else:
            write(SLOWDOWN_JS, m5)
            try:
                txt = _strip_js_comments(read(SLOWDOWN_JS))
                ok = (re.search(r"Math\.max\(RATE_FLOOR,\s*Math\.min\(RATE_CEIL",
                                txt) is None)
                check("M5 变异（去掉钳位）⇒ 判定 FAIL", ok,
                      "变异后仍检出钳位 ⇒ 守卫失效")
            finally:
                write(SLOWDOWN_JS, orig_slow)

        # M6：★ EXT-043 C2 —— 去掉 IIFE ⇒ 恢复顶层 const ⇒ 二次注入撞名
        m6 = orig_slow.replace(
            "(function () {\n  const RATE_FLOOR = 0.90;",
            "const RATE_FLOOR = 0.90;\nfunction __unused__() {\n  ")
        if m6 == orig_slow:
            check("M6 变异（去掉 IIFE）应 FAIL", False,
                  "未找到 IIFE 起始文本，变异未生效 ⇒ 守卫无区分力")
        else:
            write(SLOWDOWN_JS, m6)
            try:
                txt = _strip_js_comments(read(SLOWDOWN_JS))
                ok = (re.search(r"^\(function\s*\(\)\s*\{", txt.strip(), re.M)
                      is None)
                check("M6 变异（去掉 IIFE）⇒ 判定 FAIL", ok,
                      "变异后仍检出 IIFE ⇒ 守卫失效")
            finally:
                write(SLOWDOWN_JS, orig_slow)

        # M7：★ EXT-043 C1 —— 恢复错误的 host 提取 ⇒ 拼出 http://:8766
        #   ⚠️ ★ 必须变异 **pairStatusUrl() 函数本体**，不能只变异调用点：
        #     执行级探针抽的是**函数本身**并真跑它 ⇒ 只改调用点它抓不到
        #     ⇒ 那样会变成「假通过」（守卫看着有、实际抓不住）。
        m7 = orig_player.replace(
            "return scheme + '://' + u.hostname + ':' + pairPort + '/status';",
            "const _h = String(http).replace(/^https?:\\/\\/[^/]+/, '')"
            ".split('/')[0].replace(/:\\d+$/, '');\n"
            "    return 'http://' + _h + ':8766/status';")
        if m7 == orig_player:
            check("M7 变异（恢复错误 host 提取）应 FAIL", False,
                  "未找到 pairStatusUrl 的 return，变异未生效 ⇒ 守卫无区分力")
        else:
            write(PLAYER, m7)
            try:
                txt = _strip_js_comments(read(PLAYER))
                ok = ("replace(/^https?:\\/\\/[^/]+/, '')" in txt)
                check("M7 变异（恢复错误 host 提取）⇒ 判定 FAIL", ok,
                      "变异后仍检出 pairStatusUrl ⇒ 守卫失效")
                # ★★★ 执行级区分力：变异后 node 探针的 C1 **必须失败**
                #   （文本守卫可能失灵，执行级证据不会）
                pm = run_probe()
                c1m = pm.get("c1", {})
                check("M7 变异 ⇒ ★执行级探针 C1 必须失败（真跑出 Invalid URL）",
                      bool(c1m) and not bool(c1m.get("all_valid")),
                      "all_valid=%s cases=%s"
                      % (c1m.get("all_valid"),
                         [c.get("result") for c in (c1m.get("cases") or [])]))
            finally:
                write(PLAYER, orig_player)

        # M8：★★ 去掉 `let appliedRate` 声明 ⇒ 严格模式下 ReferenceError
        #   ★ 这是**执行级**才能抓到的 bug（文本里看不出「漏声明」）。
        m8 = orig_slow.replace("  let appliedRate = null;\n", "")
        if m8 == orig_slow:
            check("M8 变异（去掉 appliedRate 声明）应 FAIL", False,
                  "未找到 appliedRate 声明，变异未生效 ⇒ 守卫无区分力")
        else:
            write(SLOWDOWN_JS, m8)
            try:
                pm = run_probe()
                c2m = pm.get("c2", {})
                check("M8 变异（去掉 appliedRate 声明）⇒ ★执行级探针必须失败",
                      (not bool(c2m.get("rate_applied_ok"))
                       or c2m.get("set_rate_error") is not None),
                      "set_rate_error=%s rate_applied_ok=%s"
                      % (c2m.get("set_rate_error"),
                         c2m.get("rate_applied_ok")))
            finally:
                write(SLOWDOWN_JS, orig_slow)

        # M9：★★ 把 reason 的 JS 写法改回 Python 取模 ⇒ reason 变 NaN
        m9 = orig_slow.replace(
            "? ('已把 ' + n + ' 个媒体元素的 playbackRate 设为 ' + r.toFixed(3))",
            "? ('已把 %d 个媒体元素的 playbackRate 设为 %.3f' % (n, r))")
        if m9 == orig_slow:
            check("M9 变异（reason 改回 Python 取模）应 FAIL", False,
                  "未找到 reason 拼接文本，变异未生效 ⇒ 守卫无区分力")
        else:
            write(SLOWDOWN_JS, m9)
            try:
                pm = run_probe()
                c2m = pm.get("c2", {})
                _res = c2m.get("set_rate_result") or {}
                check("M9 变异（Python 取模）⇒ ★执行级探针必须失败（reason=NaN）",
                      bool(c2m.get("reason_has_nan")),
                      "reason=%s" % (_res.get("reason")
                                     if isinstance(_res, dict) else _res))
            finally:
                write(SLOWDOWN_JS, orig_slow)

    finally:
        # 无论如何都还原（保证不留下变异残留）
        write(MEDIA_PY, orig_py)
        write(POPUP_JS, orig_js)
        write(SLOWDOWN_JS, orig_slow)
        write(PLAYER, orig_player)
        import importlib
        import ext.media_slowdown as ms
        importlib.reload(ms)


def main() -> int:
    print("=" * 66)
    print("EXT-041 自测：媒体轻微降速机制")
    print("=" * 66)
    test_math()
    test_rate_rule()
    test_wiring()
    test_execution_level()
    test_discrimination()

    n_pass = sum(1 for _n, ok, _d in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 66)
    print("结果：%d PASS / %d FAIL（共 %d 项）" % (n_pass, n_fail, len(RESULTS)))
    if n_fail:
        print("\nFAIL 明细：")
        for n, ok, d in RESULTS:
            if not ok:
                print("  ✗ %s%s" % (n, ("  -- %s" % d) if d else ""))
    print("=" * 66)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
