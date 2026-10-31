"""test_t4_target_lang_effect.py — ★ 自发任务 T-4 自测：目标语言**真正生效**

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

## 背景（为什么做这件事）

闸门 `tools/next_instruction.py --json` → **exit 1**（latest=EXT-017 / last_ack=17）
⇒ 没有新纠偏指令；但按 **EXT-014 ②**（常设规则「`last_ack` 追平后仍要继续下一项」）
⇒ 继续 STATUS 里明列的 P2 待办。

审 T-3（修插件面板「死控件」）时发现 **T-3 只修了一半**：

| 环节 | T-3 之后的状态 |
|---|---|
| popup 存语言码（zh/en/ja/ko） | ✅ 已修 |
| 语言进 `start` 消息 → offscreen → hello | ✅ 已修（**offscreen 这条链路**） |
| 服务端**记录** `client_target_lang` | ✅ 已修 |
| ★ **服务端用这个语言去翻译/合成** | ❌ **没修** |

⇒ **「目标语言」仍然是个死控件**：面板上选日语，
   服务端把它记进 `client_target_lang`，但 **MT/TTS 仍按服务端启动参数
   `--target-lang` 走** ⇒ 用户选什么，输出的语言都不变。

根因（读代码得到）：

* `ext/engine_runtime.py` 的 `RuntimeEngine.target_lang` 是**构造时定死**的
  （= `load_runtime_engine(target_lang=args.target_lang)`）；
* `RuntimeEngine.mt()` / `.tts()` **不接受**按调用的语言参数 ⇒ 没法覆盖；
* `ext/bridge.py` 的 `Session._process_segment()` / `PipelineSession._stage_mt()`
  调的是 `self._engine.mt(text)` / `.tts(text, voice=...)` ⇒ **从不传语言**。

★ 顺带发现的第二个缺口：`extension/player.js` 的 hello **没带**
  `target_lang`/`voice` ⇒ **player 这条上行链路**（getDisplayMedia 兜底路径）
  上，服务端**根本收不到**面板上的选择。

## 本文件的判定原则

* **行为级优先**：能真跑的不看源码字符串。
  * 引擎侧：真起 `RuntimeEngine`（**不加载权重**，只验证语言映射与传参）。
  * 服务端侧：真起桥接服务 + 真 WebSocket（回声模式 + **桩引擎**，不跑推理）。
  * 插件侧：node 沙箱跑 `player.js` 的**真实函数**。
* **有区分力**：每组都配**反证**（把接线拆掉 ⇒ 必须 FAIL），
  避免「恒真断言」把回归掩盖掉。
* **真实退出码**：取真实 `rc`，不 pipe（`| tail` 会洗掉 rc）。

运行：
    python tests/test_t4_target_lang_effect.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EXT_DIR = os.path.join(ROOT, "extension")
HARNESS = os.path.join(ROOT, "tests", "t4_lang_harness.js")
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if (detail and not cond) else ""))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _node() -> str:
    return shutil.which("node") or ""


# ══════════════════════════════════════════════════════════════
# A 组：引擎适配层支持**按调用覆盖**目标语言
# ══════════════════════════════════════════════════════════════
def test_engine_per_call_lang() -> None:
    print("\n[A] ★ 引擎适配层：mt()/tts() 支持按调用覆盖目标语言")
    from ext.engine_runtime import (LANG_TO_MT, LANG_TO_TTS,
                                    EngineNeedsChange, RuntimeEngine)

    eng = RuntimeEngine(target_lang="en")
    check("★ 构造时的默认目标语言是 en",
          eng.target_lang == "en", f"实测 {eng.target_lang!r}")

    # ★★ 核心：按调用覆盖 ⇒ 映射随之改变
    check("★★ mt_target(target_lang='ja') ⇒ 'ja'（覆盖生效）",
          eng.mt_target("ja") == "ja", f"实测 {eng.mt_target('ja')!r}")
    check("★★ tts_language(target_lang='ja') ⇒ 'Japanese'（覆盖生效）",
          eng.tts_language("ja") == "Japanese",
          f"实测 {eng.tts_language('ja')!r}")
    check("★★ mt_target(target_lang='zh') ⇒ 'zh'",
          eng.mt_target("zh") == "zh", f"实测 {eng.mt_target('zh')!r}")
    check("★★ tts_language(target_lang='ko') ⇒ 'Korean'",
          eng.tts_language("ko") == "Korean",
          f"实测 {eng.tts_language('ko')!r}")

    # ★ 对照组：不传 ⇒ 沿用构造时的默认（向后兼容）
    check("★ 对照组：不传 ⇒ 沿用构造时的 'en'",
          eng.mt_target() == "en", f"实测 {eng.mt_target()!r}")
    check("★ 对照组：不传 ⇒ TTS 仍是 'English'",
          eng.tts_language() == "English", f"实测 {eng.tts_language()!r}")

    # ★★ 对照组：非法码必须抛异常，**绝不**静默回落
    for bad in ("xx", "Chinese", "", "jp"):
        try:
            eng.mt_target(bad)
            check(f"★★ 非法语言码 {bad!r} 必须抛异常（不静默回落）", False,
                  "居然返回了默认值")
        except EngineNeedsChange:
            check(f"★★ 非法语言码 {bad!r} 必须抛异常（不静默回落）", True)
        try:
            eng.tts_language(bad)
            check(f"★★ 非法语言码 {bad!r}（TTS）必须抛异常", False,
                  "居然返回了默认值")
        except EngineNeedsChange:
            check(f"★★ 非法语言码 {bad!r}（TTS）必须抛异常", True)

    # ★ 表必须仍只含 4 种（不能因为加了覆盖就放进不认的码）
    check("★ 语言表仍只含引擎支持的 4 种",
          set(LANG_TO_TTS) == {"zh", "en", "ja", "ko"}
          and set(LANG_TO_MT) == {"zh", "en", "ja", "ko"},
          f"{sorted(LANG_TO_TTS)} / {sorted(LANG_TO_MT)}")


# ══════════════════════════════════════════════════════════════
# B 组：服务端真的把**面板上的语言**用起来（★ 本轮的核心）
# ══════════════════════════════════════════════════════════════
class _LangRecordingEngine:
    """记录每次 mt/tts 调用**收到**的目标语言的桩引擎。

    ⚠️ 不触任何设备（不占 GPU/NPU、不跑推理）⇒ 自测可在普通机器跑。
    """

    def __init__(self, target_lang: str = "en", *, supports_lang: bool = True):
        self.target_lang = target_lang
        self.supports_lang = supports_lang
        self.mt_calls = []       # [(text, lang_or_None)]
        self.tts_calls = []      # [(text, voice, lang_or_None)]
        self.n_calls = {"asr": 0, "mt": 0, "tts": 0}

    def available(self) -> dict:
        return {"stub": True}

    def asr(self, audio, t_start, t_end) -> str:
        self.n_calls["asr"] += 1
        return "测试原稿"

    def mt(self, text: str, **kw):
        lang = kw.get("target_lang")
        if lang is not None and not self.supports_lang:
            # 模拟「老引擎不接这个关键字」
            raise TypeError("mt() got an unexpected keyword argument "
                            "'target_lang'")
        self.mt_calls.append((text, lang))
        self.n_calls["mt"] += 1
        return "translated-to-%s" % (lang or self.target_lang)

    def tts(self, text: str, *, voice: str, **kw):
        lang = kw.get("target_lang")
        if lang is not None and not self.supports_lang:
            raise TypeError("tts() got an unexpected keyword argument "
                            "'target_lang'")
        self.tts_calls.append((text, voice, lang))
        self.n_calls["tts"] += 1
        import numpy as np
        n = int(0.2 * 24000)
        return (np.zeros(n, dtype=np.int16)).tobytes(), 0.2

    def stats(self) -> dict:
        return {"stub": True, "n_calls": dict(self.n_calls)}


def test_session_applies_client_lang() -> None:
    print("\n[B] ★★★ 服务端：面板上选的目标语言**真正用于**翻译/合成")
    from ext.bridge import Session

    # ── 实验组：客户端报了 'ja' ⇒ 引擎必须收到 'ja' ──────────────
    eng = _LangRecordingEngine(target_lang="en")
    s = Session("tok", delay_sec=10.0, engine=eng)
    s.note_client({"target_lang": "ja", "voice": "A"})
    check("★ 服务端记下 client_target_lang='ja'",
          s.client_target_lang == "ja", f"实测 {s.client_target_lang}")
    check("★ _effective_target_lang() 返回 'ja'",
          s._effective_target_lang() == "ja",
          f"实测 {s._effective_target_lang()!r}")

    # 直接驱动一段（串行路径的内部逻辑）：构造一个最小可跑的段
    import numpy as np
    audio = np.zeros(16000, dtype=np.float32)
    s._process_segment(seq=0, s0=0, s1=16000, audio=audio)

    check("★★★ MT 真的收到了 'ja'（不是服务端的默认 'en'）",
          bool(eng.mt_calls) and eng.mt_calls[0][1] == "ja",
          f"实测 mt_calls={eng.mt_calls}")
    check("★★★ TTS 真的收到了 'ja'",
          bool(eng.tts_calls) and eng.tts_calls[0][2] == "ja",
          f"实测 tts_calls={eng.tts_calls}")
    check("★★★ applied_target_lang 如实记成 'ja'",
          s.applied_target_lang == "ja",
          f"实测 {s.applied_target_lang!r}")
    check("★★ stats 里的 applied_target_lang = 'ja'",
          s.stats().get("applied_target_lang") == "ja",
          f"实测 {s.stats().get('applied_target_lang')!r}")

    # ★★ 对照组：客户端**没报**语言 ⇒ 沿用引擎默认（不臆造）
    eng2 = _LangRecordingEngine(target_lang="en")
    s2 = Session("tok", delay_sec=10.0, engine=eng2)
    s2.note_client({})
    s2._process_segment(seq=0, s0=0, s1=16000, audio=audio)
    check("★★ 对照组：不报语言 ⇒ MT 不带 target_lang（沿用引擎默认）",
          bool(eng2.mt_calls) and eng2.mt_calls[0][1] is None,
          f"实测 mt_calls={eng2.mt_calls}")
    check("★ 对照组：不报语言 ⇒ applied_target_lang 保持 None（不臆造）",
          s2.applied_target_lang is None,
          f"实测 {s2.applied_target_lang!r}")

    # ★★ 对照组：客户端报的是**非法**码 ⇒ 服务端记成 None
    #   ⇒ 不该把它传给引擎（否则引擎会抛 EngineNeedsChange）
    # ★★ EXT-024 G：**'Chinese' 不再是非法码**（服务端新增全称→引擎码
    #   的白名单映射，见 t3 的对应断言）⇒ 这里的非法码改用真·未知的 'xx'。
    eng3 = _LangRecordingEngine(target_lang="en")
    s3 = Session("tok", delay_sec=10.0, engine=eng3)
    s3.note_client({"target_lang": "xx"})
    s3._process_segment(seq=0, s0=0, s1=16000, audio=audio)
    check("★★ 对照组：非法码 ⇒ 不传给引擎（不会把引擎打挂）",
          bool(eng3.mt_calls) and eng3.mt_calls[0][1] is None,
          f"实测 mt_calls={eng3.mt_calls}")

    # ★★ EXT-024 G：全称 'Chinese' ⇒ 归一成 'zh' **并真的传给引擎**
    #   （这是用户 10-31 实测的现场证据：存量配置里存的就是 "Chinese"）。
    eng3b = _LangRecordingEngine(target_lang="en")
    s3b = Session("tok", delay_sec=10.0, engine=eng3b)
    s3b.note_client({"target_lang": "Chinese"})
    s3b._process_segment(seq=0, s0=0, s1=16000, audio=audio)
    check("★★ EXT-024 G：'Chinese' ⇒ 真的按 'zh' 传给 MT",
          bool(eng3b.mt_calls) and eng3b.mt_calls[0][1] == "zh",
          f"实测 mt_calls={eng3b.mt_calls}")
    check("★★ EXT-024 G：'Chinese' ⇒ applied_target_lang='zh'",
          s3b.applied_target_lang == "zh",
          f"实测 {s3b.applied_target_lang!r}")

    # ★★★ 对照组（**兼容性**）：引擎**不接** target_lang 关键字时
    #   ⇒ 不能崩，要回落旧行为，并**如实**记 None（不假装生效）
    eng4 = _LangRecordingEngine(target_lang="en", supports_lang=False)
    s4 = Session("tok", delay_sec=10.0, engine=eng4)
    s4.note_client({"target_lang": "ja", "voice": "A"})
    try:
        s4._process_segment(seq=0, s0=0, s1=16000, audio=audio)
        check("★★★ 老引擎（不接 target_lang）⇒ 不崩", True)
    except Exception as e:
        check("★★★ 老引擎（不接 target_lang）⇒ 不崩", False,
              f"{type(e).__name__}: {e}")
    check("★★★ 老引擎 ⇒ applied_target_lang 记 None（不假装生效）",
          s4.applied_target_lang is None,
          f"实测 {s4.applied_target_lang!r}")


def test_pipeline_applies_client_lang() -> None:
    print("\n[B2] ★ 流水线路径（生产默认）：同样要真正用上面板语言")
    from ext.bridge import PipelineSession

    eng = _LangRecordingEngine(target_lang="en")
    s = PipelineSession("tok", delay_sec=10.0, engine=eng)
    s.note_client({"target_lang": "ko", "voice": "A"})

    class _Job:
        seg_id = "seg1"
        t_start = 0.0
        t_end = 1.0
        text = "테스트"
        tgt = None
        spk = None
        voice = None
        pcm24k = None
        speech_sec = 0.0
        asr_sec = mt_sec = tts_sec = 0.0
        ready_at = 0.0
        errors: list = []

        def mark_error(self, stage, e):
            self.errors.append((stage, e))

    job = _Job()
    s._stage_mt(job)
    check("★★ 流水线的 MT 阶段收到了 'ko'",
          bool(eng.mt_calls) and eng.mt_calls[0][1] == "ko",
          f"实测 mt_calls={eng.mt_calls}")
    job.tgt = "번역"
    s._stage_tts(job)
    check("★★ 流水线的 TTS 阶段收到了 'ko'",
          bool(eng.tts_calls) and eng.tts_calls[0][2] == "ko",
          f"实测 tts_calls={eng.tts_calls}")
    check("★ 流水线 applied_target_lang = 'ko'",
          s.applied_target_lang == "ko",
          f"实测 {s.applied_target_lang!r}")


# ══════════════════════════════════════════════════════════════
# C 组：真起桥接服务 ⇒ hello 里的语言进 stats + margin.json
# ══════════════════════════════════════════════════════════════
def test_bridge_reports_applied_lang() -> None:
    print("\n[C] ★ 真起桥接 ⇒ 客户端语言进 stats / margin.json（可核对）")
    try:
        import websockets  # noqa: F401
    except Exception:
        check("websockets 可用（跳过本组）", True, "websockets 不可用")
        return
    try:
        from ext import bridge
    except Exception as e:
        check("能 import ext.bridge", False, str(e))
        return

    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]

    holder: dict = {}
    tmpdir = tempfile.mkdtemp()
    token_path = os.path.join(tmpdir, "tok.txt")
    tokens = bridge.TokenStore(token_path)

    async def _serve():
        await bridge.serve("127.0.0.1", port, delay_sec=10.0,
                           echo_mode=True, token_path=token_path,
                           engine=None,
                           margin_out=None, session_holder=holder,
                           use_pipeline=False)

    async def _client():
        import websockets
        origin = "chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib"
        async with websockets.connect(
                "ws://127.0.0.1:%d/" % port,
                additional_headers={"Origin": origin}) as ws:
            await ws.send(json.dumps({
                "type": "hello", "token": tokens.token, "role": "uplink",
                "target_lang": "ja", "voice": "clone",
            }))
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            ack = json.loads(raw)
            await ws.send(json.dumps({"type": "stats"}))
            stats = None
            for _ in range(20):
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                m = json.loads(raw)
                if m.get("type") == "stats":
                    stats = m
                    break
            return ack, stats

    async def _run():
        t = asyncio.create_task(_serve())
        await asyncio.sleep(0.6)
        try:
            return await asyncio.wait_for(_client(), timeout=30)
        finally:
            t.cancel()

    try:
        ack, stats = asyncio.run(_run())
    except Exception as e:
        check("真起桥接并连上（回声模式）", False, f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return

    check("★ hello_ack 正常返回", isinstance(ack, dict) and "type" in ack,
          str(ack)[:200])
    check("★ hello_ack 仍是旧结构（向后兼容：不加新字段）",
          "client_target_lang" not in (ack or {}),
          "hello_ack 被改动了 ⇒ 可能破坏旧客户端")
    if isinstance(stats, dict):
        check("★ stats 里的 client_target_lang = 'ja'",
              stats.get("client_target_lang") == "ja",
              f"实测 {stats.get('client_target_lang')!r}")
        check("★★ stats 里有 applied_target_lang 字段",
              "applied_target_lang" in stats,
              f"keys={sorted(stats.keys())[:20]}")
        # ★ 回声模式没有引擎 ⇒ 没跑过任何一句 ⇒ applied 必须是 None
        check("★ 对照组：回声模式没跑引擎 ⇒ applied_target_lang = None",
              stats.get("applied_target_lang") is None,
              f"实测 {stats.get('applied_target_lang')!r}")


# ══════════════════════════════════════════════════════════════
# D 组：插件侧 —— player.js 的 hello 必须带语言/音色
# ══════════════════════════════════════════════════════════════
def test_plugin_reports_lang() -> None:
    print("\n[D] ★ 插件侧：player.js 的 hello 必须带 target_lang / voice")
    node = _node()
    if not node:
        check("node 可用（跳过本组）", True, "node 不可用")
        return
    src = _read(os.path.join(EXT_DIR, "player.js"))

    check("★ player.js 的 hello 里有 target_lang",
          "target_lang:" in src, "player.js 未上报 target_lang")
    check("★ player.js 的 hello 里有 voice",
          "voice:" in src, "player.js 未上报 voice")
    check("★ player.js 读出了 targetLang", "targetLang" in src)
    check("★ player.js 读出了 voicePref", "voicePref" in src)
    check("★ player.js 有 normalizeLang（与 popup 同口径）",
          "function normalizeLang" in src)
    check("★ player.js 有 normalizeVoice（与 popup 同口径）",
          "function normalizeVoice" in src)

    # ★★ popup 与 player 的归一逻辑必须一致（否则会不一致上报）
    pop = _read(os.path.join(EXT_DIR, "popup.js"))
    check("★★ popup.js 也有 normalizeVoice（两边一致）",
          "function normalizeVoice" in pop)
    # 两边的语言别名表必须一致
    def _aliases(text: str) -> set:
        import re
        m = re.search(r"LANG_ALIASES\s*=\s*\{(.*?)\}", text, re.S)
        return set(re.findall(r"['\"]([^'\"]+)['\"]\s*:", m.group(1))) if m else set()
    check("★★ popup 与 player 的语言别名表一致",
          _aliases(pop) == _aliases(src),
          f"popup={sorted(_aliases(pop))} player={sorted(_aliases(src))}")

    # ★★★ 行为级：node 沙箱跑 player.js 的**真函数**
    if os.path.isfile(HARNESS):
        r = subprocess.run([node, HARNESS],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        out = r.stdout or ""
        check("★★★ node harness 全部通过（rc=0）",
              r.returncode == 0,
              f"rc={r.returncode}；输出尾部：{out[-600:]}")
        check("★★★ harness 至少跑了 10 项断言",
              out.count("[PASS]") >= 10,
              f"PASS 数={out.count('[PASS]')}")
    else:
        check("★★★ node harness 文件存在", False, HARNESS)


# ══════════════════════════════════════════════════════════════
# E 组：文档口径（USER_GUIDE 不能还停留在 T-3 的说法）
# ══════════════════════════════════════════════════════════════
def test_docs_consistent() -> None:
    print("\n[E] ★ 文档：USER_GUIDE 的「目标语言」说法要跟上")
    paths = [os.path.join(ROOT, "USER_GUIDE.md"),
             os.path.join(EXT_DIR, "USER_GUIDE.md")]
    for p in paths:
        if not os.path.isfile(p):
            check(f"★ {os.path.relpath(p, ROOT)} 存在", False, p)
            continue
        s = _read(p)
        rel = os.path.relpath(p, ROOT)
        check(f"★ {rel} 说明了目标语言", "目标语言" in s)
        check(f"★ {rel} 提到了 T-4 或「实际生效」",
              "T-4" in s or "实际生效" in s,
              "文档口径未跟上本轮修复")

    a, b = paths
    if os.path.isfile(a) and os.path.isfile(b):
        check("★ 两份 USER_GUIDE 内容一致", _read(a) == _read(b), "两份不一致")


def main() -> int:
    print("=" * 72)
    print("T-4 自测：目标语言**真正生效**"
          "（面板选的语种要真的用于翻译/合成）")
    print("=" * 72)
    for fn in (test_engine_per_call_lang,
               test_session_applies_client_lang,
               test_pipeline_applies_client_lang,
               test_bridge_reports_applied_lang,
               test_plugin_reports_lang,
               test_docs_consistent):
        try:
            fn()
        except Exception as e:
            traceback.print_exc()
            RESULTS.append((fn.__name__, False, str(e)))
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 72)
    print(f"结果：{npass} PASS / {nfail} FAIL / 共 {len(RESULTS)}")
    if nfail:
        print("\nFAIL 明细：")
        for name, ok, detail in RESULTS:
            if not ok:
                print(" - %s — %s" % (name, detail))
    print("=" * 72)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
