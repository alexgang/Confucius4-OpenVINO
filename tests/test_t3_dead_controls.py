"""test_t3_dead_controls.py — ★ 自发任务 T-3 自测：插件侧「死控件」修复

**新增**自测文件，**不改写**既有断言（避免用改断言掩盖回归）。

## 背景（为什么做这件事）

闸门 `tools/next_instruction.py --json` → **exit 1**（latest=EXT-017 / last_ack=17）
⇒ 没有新纠偏指令；但按 **EXT-014 ②**（常设规则「`last_ack` 追平后仍要继续下一项」）
⇒ 继续 STATUS 里明列的 P2 待办（`克隆音色 / ducking / 字幕 / 设置持久化 / …`）。

审这批待办时发现 **4 个面板控件是「死控件」** ——
用户在插件面板上怎么调都**完全不起作用**，而 `USER_GUIDE.md` 明确承诺它们可调：

| 控件 | 面板承诺 | 实际行为 | 根因 |
|---|---|---|---|
| **原声压低量（dB）** | 「把原声压低多少 dB」 | **永远 1.0**（不压低） | `player.js` 的 `setupOriginalAudio` 硬编码 `origGain.gain.value = 1.0`；`duckDb` 只在 `popup.js` 存进 storage，**player 从不读** |
| **字幕开关** | 「是否显示译文字幕」 | **关掉也照样显示** | `player.js` 的 `pumpSubs` 无条件写 DOM；`subsOn` 同样只存不读 |
| **目标语言** | 「配音要译成的语言」 | **选了不生效** | ① popup 存的是语言**全称**（`Chinese`/`English`/`Japanese`），而引擎只认 `zh/en/ja/ko`；② 更根本：`targetLang` **从没进过 start 消息** ⇒ 服务端根本收不到 |
| **音色** | 「预设 A / 克隆说话人」 | **选了不生效** | `voice` **从没进过 start 消息**；且服务端 `tracker.voice_for()` 完全忽略用户选择（只要有说话人攒够 3 s 就自动切克隆） |

⇒ **T-3 的修复**：把这 4 个控件真正接线（读 → 用 → 如实回报生效值）。

## 本文件的判定原则

* **行为级优先**：能真跑的就不看源码字符串。
  * 插件侧用 **node 沙箱**跑 `player.js` 的**真实函数**（`tests/t3_settings_harness.js`）
    —— 本机**没有 playwright**（实测 `ModuleNotFoundError`）⇒ 不能在真浏览器里点。
  * 服务端用**真起桥接服务 + 真 WebSocket**（回声模式，不跑推理）。
* **有区分力**：每组都配**反证**（把接线拆掉 ⇒ 必须 FAIL），
  避免「恒真断言」把回归掩盖掉。
* **真实退出码**：取真实 `rc`，不 pipe（`| tail` 会洗掉 rc）。

运行：
    python tests/test_t3_dead_controls.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EXT_DIR = os.path.join(ROOT, "extension")
HARNESS = os.path.join(ROOT, "tests", "t3_settings_harness.js")
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
# A 组：插件侧行为级（node 沙箱跑 player.js 的真函数）
# ══════════════════════════════════════════════════════════════
def test_plugin_behavior() -> None:
    print("\n[A] ★ 插件侧行为级：node 沙箱跑 player.js 的真实函数")
    node = _node()
    if not node:
        check("node 可用（跳过本组）", True, "node 不可用")
        return
    check("★ harness 存在", os.path.isfile(HARNESS), HARNESS)
    if not os.path.isfile(HARNESS):
        return

    r = subprocess.run([node, HARNESS], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    out = (r.stdout or "")
    check(f"★ harness 退出码 0（实测 rc={r.returncode}）", r.returncode == 0,
          (out or r.stderr or "")[-500:])
    m = re.search(r"harness 结果：(\d+) PASS / (\d+) FAIL / 共 (\d+)", out)
    check("★ harness 打印了汇总行", m is not None, out[-300:])
    if m:
        npass, nfail, ntot = int(m.group(1)), int(m.group(2)), int(m.group(3))
        check(f"★ harness 全通过（{npass} PASS / {nfail} FAIL / 共 {ntot}）",
              nfail == 0 and ntot > 0, f"实测 {npass}/{nfail}/{ntot}")
        # ★ 关键断言：必须真的覆盖了「原声增益」与「字幕不写 DOM」
        check("★ harness 覆盖了「走真实 setupOriginalAudio ⇒ 增益=0.1778」",
              "走真实 setupOriginalAudio" in out)
        check("★ harness 覆盖了「字幕关 ⇒ DOM 一次都没被写」",
              "DOM **一次都没被写**" in out)

    # ★★ 反证：把 player.js 改坏（ducking 退回硬编码 1.0、字幕开关失效）
    #   ⇒ harness 必须 FAIL（rc≠0）。
    #   ⇒ 若仍 PASS ⇒ 说明 harness 没有区分力（本测试本身就没价值）。
    with tempfile.TemporaryDirectory() as td:
        broken = os.path.join(td, "player_broken.js")
        src = _read(os.path.join(EXT_DIR, "player.js"))
        s2 = src.replace("  applyDuckDb();\n  origSource.connect(origDelay);",
                         "  origGain.gain.value = 1.0;\n  origSource.connect(origDelay);")
        if s2 == src:
            check("★ 反证准备：能在 player.js 里找到 ducking 接线点", False,
                  "没找到 applyDuckDb 调用点")
        else:
            s3 = s2.replace(
                "  if (!subsOn) {\n    const div = document.getElementById('subs');",
                "  if (false) {\n    const div = document.getElementById('subs');")
            with open(broken, "w", encoding="utf-8") as f:
                f.write(s3)
            r2 = subprocess.run([node, HARNESS, broken], cwd=ROOT,
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=120)
            out2 = (r2.stdout or "")
            check(f"★★ 反证：改坏 player.js 后 harness 必须 FAIL（实测 rc={r2.returncode}）",
                  r2.returncode != 0,
                  "harness 对坏实现仍报 PASS ⇒ 没有区分力")
            check("★★ 反证：坏实现时「原声增益」断言必须红",
                  "走真实 setupOriginalAudio" in out2
                  and "FAIL" in out2)
            check("★★ 反证：坏实现时「字幕不写 DOM」断言必须红",
                  "一次都没被写" in out2 and "FAIL" in out2)


# ══════════════════════════════════════════════════════════════
# B 组：语言码接线（popup → sw → offscreen → 服务端）
# ══════════════════════════════════════════════════════════════
def test_lang_wiring() -> None:
    print("\n[B] ★ 目标语言：面板选的值要真正传到服务端")
    html = _read(os.path.join(EXT_DIR, "popup.html"))
    popup = _read(os.path.join(EXT_DIR, "popup.js"))
    sw = _read(os.path.join(EXT_DIR, "sw.js"))
    offscreen = _read(os.path.join(EXT_DIR, "offscreen.js"))

    # ── B1：popup 的下拉框 value 必须是**引擎码** ──
    opts = re.findall(r'<option value="([^"]+)"', html)
    lang_opts = []
    in_lang = False
    for line in html.split("\n"):
        if 'id="lang"' in line:
            in_lang = True
        if in_lang:
            lang_opts += re.findall(r'<option value="([^"]+)"', line)
            if "</select>" in line:
                break
    check("★ popup 的目标语言下拉框存在", bool(lang_opts), str(lang_opts))
    check("★ popup 语言选项用引擎码（zh/en/ja/ko），不是语言全称",
          all(o in ("zh", "en", "ja", "ko") for o in lang_opts),
          f"实测 {lang_opts}")
    # ★ 只看**选项的 value**（不看注释文本）—— 注释里可以提到旧写法。
    lang_option_values = re.findall(
        r'<option\s+value="([^"]+)"[^>]*>\s*[^<]*</option>',
        html[html.find('id="lang"'):html.find('id="lang"') + 600])
    check("★ popup 不再出现 value=\"Chinese\"（引擎不认全称）",
          "Chinese" not in lang_option_values, str(lang_option_values))
    check("★ popup 不再出现 value=\"Japanese\"",
          "Japanese" not in lang_option_values, str(lang_option_values))

    # ── B2：popup.js 要做**归一**（老配置里存的是全称）──
    check("★ popup.js 有语言归一函数 normalizeLang", "normalizeLang" in popup)
    check("★ normalizeLang 把 Chinese 映射成 zh",
          re.search(r"chinese['\"]?\s*:\s*['\"]zh", popup) is not None)
    check("★ popup.js 的 loadCfg 用归一后的值填下拉框",
          "$('lang').value = normalizeLang(cfg.targetLang)" in popup)

    # ── B3：targetLang 必须真的进 start 消息 ──
    check("★★ popup 的 start 消息带 targetLang",
          re.search(r"cmd:\s*'start'.*?targetLang", popup, re.S) is not None)
    check("★★ popup 的 start 消息带 voice",
          re.search(r"cmd:\s*'start'.*?voice", popup, re.S) is not None)

    # ── B4：sw.js 要透传 ──
    check("★★ sw.js 把 targetLang 透传给 offscreen",
          "targetLang: msg.targetLang" in sw)
    check("★★ sw.js 把 voice 透传给 offscreen",
          "voice: msg.voice" in sw)

    # ── B5：offscreen.js 要放进 hello ──
    check("★★ offscreen.js 的 hello 消息带 target_lang",
          "target_lang:" in offscreen)
    check("★ offscreen.js 的 connectWs 接受 opts（targetLang/voice）",
          re.search(r"function\s+connectWs\s*\(\s*wsUrl\s*,\s*token\s*,\s*opts", offscreen)
          is not None)

    # ── B6：服务端要认这个字段，且**只认白名单** ──
    from ext import config as C
    from ext.bridge import Session
    check("★ config.py 定义了 LANG_CODES", hasattr(C, "LANG_CODES"))
    check("★ LANG_CODES 与引擎支持的 4 种一致",
          tuple(C.LANG_CODES) == ("zh", "en", "ja", "ko"),
          str(getattr(C, "LANG_CODES", None)))

    s = Session("tok", delay_sec=10.0, engine=None)
    s.note_client({"target_lang": "ja", "voice": "A"})
    check("★★ 服务端收到 target_lang='ja' ⇒ 记成 'ja'",
          s.client_target_lang == "ja", f"实测 {s.client_target_lang}")

    # ★★ 对照组：全称的处理方式 **EXT-024 G 已改**。
    #   旧断言：「'Chinese' ⇒ 记成 None（不静默接受）」——
    #   那是 EXT-022 之前的行为（插件侧已改用引擎码 ⇒ 全称不再出现）。
    # ★★ EXT-024 G 明确要求：**服务端也要独立地把全称映射成引擎码**。
    #   现场证据：用户 Edge 默认 profile 的 chrome.storage 里
    #   `targetLang` 存的就是 **`"Chinese"`**（存量配置不会自动迁移）
    #   ⇒ 服务端只认 zh/en/ja/ko 时，"Chinese" 落到 None
    #   ⇒ 服务端按启动参数（默认 en）翻译 ⇒ **用户看到「没翻译成中文」**。
    # ⇒ 现在：'Chinese' ⇒ **'zh'**（白名单映射）。
    # ⚠️ 「不臆造」这条**没有被削弱** —— 下面紧跟的 'xx' 与「不带」两组
    #   仍然必须记 None（未知值一律不猜）。
    s2 = Session("tok", delay_sec=10.0, engine=None)
    s2.note_client({"target_lang": "Chinese"})
    check("★★ EXT-024 G：target_lang='Chinese' ⇒ 映射成 'zh'（白名单）",
          s2.client_target_lang == "zh", f"实测 {s2.client_target_lang}")

    s3 = Session("tok", delay_sec=10.0, engine=None)
    s3.note_client({"target_lang": "xx"})
    check("★ 对照组：未知语言码 'xx' ⇒ 记成 None",
          s3.client_target_lang is None, f"实测 {s3.client_target_lang}")

    s4 = Session("tok", delay_sec=10.0, engine=None)
    s4.note_client({})
    check("★ 对照组：不带 target_lang ⇒ 记成 None（不臆造）",
          s4.client_target_lang is None, f"实测 {s4.client_target_lang}")


# ══════════════════════════════════════════════════════════════
# C 组：音色偏好（面板选「预设 A」必须真的是预设 A）
# ══════════════════════════════════════════════════════════════
def test_voice_preference() -> None:
    print("\n[C] ★ 音色：面板选「预设 A」⇒ 一律用预设 A")
    from ext import config as C
    from ext.bridge import Session

    s = Session("tok", delay_sec=10.0, engine=None)
    s.note_client({"voice": "A"})
    check("★ 面板选 'A' ⇒ client_voice 记成 'A'", s.client_voice == "A",
          f"实测 {s.client_voice}")

    # ★★ 关键：即使用户选了「预设 A」，tracker 说某说话人可克隆，
    #   也**不能**自动切到克隆音色（旧实现的 bug）。
    s.tracker._profiles = {}
    s.tracker._last_spk = None
    # 造一个「攒够 3 s」的说话人 profile（voice_id = spk_id ⇒ 克隆就绪）
    from ext.speaker import SpeakerProfile
    prof = SpeakerProfile(spk_id="S1")
    prof.clean_sec = 99.0
    prof.voice_id = "S1"
    s.tracker._profiles["S1"] = prof
    s.tracker._last_spk = "S1"

    v = s._pick_voice("S1")
    check("★★ 面板选 'A' + tracker 说可克隆 ⇒ 仍然用预设 A",
          v == C.PRESET_VOICE, f"实测 {v!r}（期望 {C.PRESET_VOICE!r}）")

    # 对照组：面板选 'clone' ⇒ 沿用 tracker 的判断
    s2 = Session("tok", delay_sec=10.0, engine=None)
    s2.note_client({"voice": "clone"})
    s2.tracker._profiles["S1"] = prof
    s2.tracker._last_spk = "S1"
    v2 = s2._pick_voice("S1")
    check("★ 对照组：面板选 'clone' ⇒ 用 tracker 的克隆音色",
          v2 == "S1", f"实测 {v2!r}")

    # ★ 诚实性：clone 但没有 spk ⇒ 回落到预设 A（不假装克隆生效）
    s3 = Session("tok", delay_sec=10.0, engine=None)
    s3.note_client({"voice": "clone"})
    v3 = s3._pick_voice(None)
    check("★ 诚实性：选 clone 但没有说话人 ⇒ 回落预设 A",
          v3 == C.PRESET_VOICE, f"实测 {v3!r}")


# ══════════════════════════════════════════════════════════════
# D 组：服务端把设置落进 stats 与 margin.json（可核对）
# ══════════════════════════════════════════════════════════════
def test_server_reports_settings() -> None:
    print("\n[D] ★ 服务端：设置要进 stats 与 margin.json（reviewer 能核对）")
    from ext.bridge import Session, _dump_margin

    s = Session("tok", delay_sec=10.0, engine=None)
    s.note_client({"target_lang": "en", "voice": "clone",
                    "capture_mode": "tabCapture", "source_rate": 48000})
    st = s.stats()
    check("★ stats 里有 client_target_lang", "client_target_lang" in st)
    check("★ stats 里的 client_target_lang = 'en'",
          st.get("client_target_lang") == "en",
          f"实测 {st.get('client_target_lang')}")
    check("★ stats 里有 client_voice", "client_voice" in st)
    check("★ stats 里的 client_voice = 'clone'",
          st.get("client_voice") == "clone",
          f"实测 {st.get('client_voice')}")

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "margin.json")
        _dump_margin({"session": s}, out, None)
        check("★ margin.json 落盘了", os.path.isfile(out))
        if os.path.isfile(out):
            with open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
            check("★ margin.json 里有 client_target_lang",
                  "client_target_lang" in data,
                  str(sorted(data.keys())[:20]))
            check("★ margin.json 里的 client_target_lang = 'en'",
                  data.get("client_target_lang") == "en",
                  f"实测 {data.get('client_target_lang')}")
            check("★ margin.json 里的 client_voice = 'clone'",
                  data.get("client_voice") == "clone",
                  f"实测 {data.get('client_voice')}")


# ══════════════════════════════════════════════════════════════
# E 组：真起桥接服务 ⇒ hello 里的 target_lang 真的被记进会话
# ══════════════════════════════════════════════════════════════
def test_bridge_accepts_target_lang() -> None:
    print("\n[E] ★ 行为级：真起桥接 ⇒ hello 的 target_lang 进会话 stats")
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

    # 动态端口（避免撞上正在跑的实例 8765）
    import socket
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]

    holder: dict = {}
    tasks = []
    # ★ serve() 需要一个**真实的 token 文件路径**（它会建 TokenStore）。
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
        # Origin 必须是本插件（EXT-017④）
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
            # 再要一份 stats
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
        tasks.append(t)
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

    check("★ stats 回来了", isinstance(stats, dict), str(stats)[:200])
    if isinstance(stats, dict):
        check("★★ stats 里的 client_target_lang = 'ja'",
              stats.get("client_target_lang") == "ja",
              f"实测 {stats.get('client_target_lang')}")
        check("★★ stats 里的 client_voice = 'clone'",
              stats.get("client_voice") == "clone",
              f"实测 {stats.get('client_voice')}")

    # ★★ 对照组：连一个**不带** target_lang 的客户端 ⇒ 必须是 None
    async def _client2():
        import websockets
        origin = "chrome-extension://kekgmfkijphpfndbbpakjaokamkeooib"
        async with websockets.connect(
                "ws://127.0.0.1:%d/" % port,
                additional_headers={"Origin": origin}) as ws:
            await ws.send(json.dumps({
                "type": "hello", "token": tokens.token, "role": "uplink",
            }))
            await asyncio.wait_for(ws.recv(), timeout=10)
            await ws.send(json.dumps({"type": "stats"}))
            for _ in range(20):
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                m = json.loads(raw)
                if m.get("type") == "stats":
                    return m
            return None

    async def _run2():
        t = asyncio.create_task(_serve())
        tasks.append(t)
        await asyncio.sleep(0.6)
        try:
            return await asyncio.wait_for(_client2(), timeout=30)
        finally:
            t.cancel()

    try:
        st2 = asyncio.run(_run2())
        check("★ 对照组：不带 target_lang 的客户端 ⇒ client_target_lang 是 None",
              isinstance(st2, dict) and st2.get("client_target_lang") is None,
              f"实测 {st2.get('client_target_lang') if isinstance(st2, dict) else st2}")
    except Exception as e:
        check("对照组连接", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# F 组：文档口径同步（USER_GUIDE 不能还写着旧行为）
# ══════════════════════════════════════════════════════════════
def test_docs_consistent() -> None:
    print("\n[F] ★ 文档：USER_GUIDE 与真实行为一致")
    for p in (os.path.join(ROOT, "USER_GUIDE.md"),
              os.path.join(EXT_DIR, "USER_GUIDE.md")):
        check(f"★ {os.path.relpath(p, ROOT)} 存在", os.path.isfile(p), p)
        if not os.path.isfile(p):
            continue
        s = _read(p)
        check(f"★ {os.path.relpath(p, ROOT)} 说明了原声压低量（dB）",
              "压低" in s and "dB" in s)
        check(f"★ {os.path.relpath(p, ROOT)} 说明了字幕开关", "字幕开关" in s)
    # 两份 USER_GUIDE 必须一致（历史上是两份拷贝）
    a = os.path.join(ROOT, "USER_GUIDE.md")
    b = os.path.join(EXT_DIR, "USER_GUIDE.md")
    if os.path.isfile(a) and os.path.isfile(b):
        check("★ 两份 USER_GUIDE 内容一致", _read(a) == _read(b), "两份不一致")


def main() -> int:
    print("=" * 72)
    print("T-3 自测：插件侧「死控件」修复"
          "（原声压低量 / 字幕开关 / 目标语言 / 音色）")
    print("=" * 72)
    for fn in (test_plugin_behavior, test_lang_wiring, test_voice_preference,
               test_server_reports_settings, test_bridge_accepts_target_lang,
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
