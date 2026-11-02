#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_ext033_capture.py — ★ EXT-033 A：**只抓页面元素/标签页音频**的可选路径探针

## 为什么需要这个探针
EXT-033 的第一句批评是：「**输入仍是整机声**」。
EXT-032/§25.3 已经把根因钉死：自动化下 `chrome.tabCapture.getMediaStreamId()`
拿不到流 id（`Extension has not been invoked for the current page
(see activeTab permission)`）⇒ 降级到 `getDisplayMedia` ⇒ 抓到整机系统声音
⇒ ASR 里混进实时字幕 App 的中文。

EXT-033 A 明确给了三条路，本探针逐条实测（**不靠猜**）：

| 标签 | 路径 | 说明 |
|---|---|---|
| `A1_base`  | `chrome.tabCapture.getMediaStreamId({targetTabId})` | 不带任何授权开关的基线（复现 EXT-032 的失败） |
| `A1_allow` | 同上 + 浏览器启动参数 `--allowlisted-extension-id=<插件ID>` | EXT-033 A 点名的第一条 |
| `A2_action`| `commands._execute_action` + Windows `SendInput` 合成按键 | EXT-033 A 点名的第二条（**算用户手势**） |
| `A3_element` | 页面里 `createMediaElementSource` + `MediaStreamDestination` | EXT-033 A 点名的第三条（**只抓页面元素**） |

## 判定标准（**可证伪**，不是「拿到流就算过」）

拿到流只是第一步。本探针还会：
1. 用 MediaRecorder 录下**抓到的流** 10 s；
2. 在浏览器里用 `AudioContext.decodeAudioData` 解码 ⇒ 取 100 ms 窗 RMS 包络；
3. 同时算**素材**（英文 SPE 60 s）同一套 RMS 包络；
4. 算两条包络的**互相关**。

⇒ **只有当抓到的音频与素材高度相关（corr ≥ 0.8）才算「真的只抓到了页面元素音频」**。
若抓到的是整机混音（实时字幕 App 的中文），包络会与素材**不相关** ⇒ 判定 FAIL。

## 跑法
    python tests/smoke/probe_ext033_capture.py

## 输出
`.tmp/probe_ext033_capture/result.json`（每次尝试的原始错误 + 判定）+ 抓到的录音 webm
"""
from __future__ import annotations

import json
import os
import sys
import time

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import browser_harness as H          # noqa: E402

OUT_DIR = os.path.join(ROOT, ".tmp", "probe_ext033_capture")

#: 素材：英文 SPE 60 s（只读引用 R2T2 仓库自带）
SRC_WAV = (r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
           r"\test_en_60s.wav")

#: 抓到的流要录多久（秒）—— 够算出包络即可
REC_SEC = 10.0

#: 包络窗长（毫秒）
ENV_WIN_MS = 100


def _log(msg: str) -> None:
    print("[probe-ext033] %s" % msg, flush=True)


# ══════════════════════════════════════════════════════════════════
# 素材包络（Python 侧，与浏览器侧口径一致：100 ms 窗 RMS）
# ══════════════════════════════════════════════════════════════════
def source_envelope(path: str, win_ms: int = ENV_WIN_MS):
    import wave
    w = wave.open(path, "rb")
    nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
    raw = w.readframes(w.getnframes())
    w.close()
    assert nch == 1 and sw == 2, (nch, sw)
    import array
    a = array.array("h")
    a.frombytes(raw)
    step = max(1, int(sr * win_ms / 1000))
    env = []
    for i in range(0, len(a), step):
        chunk = a[i:i + step]
        if not chunk:
            break
        s = 0
        for v in chunk:
            s += v * v
        env.append((s / len(chunk)) ** 0.5 / 32768.0)
    return env, sr


def _pearson(xs, ys):
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx <= 0 or dy <= 0:
        return 0.0
    return num / (dx * dy)


# ══════════════════════════════════════════════════════════════════
# 浏览器侧：抓流 + 录 10 s + 解码算包络
# ══════════════════════════════════════════════════════════════════
JS_GET_TAB_ID = """
() => new Promise((res) => {
  chrome.tabs.query({}, (tabs) => {
    const t = tabs.find(x => x.url && x.url.indexOf(%r) >= 0);
    res(t ? t.id : null);
  });
})
"""

#: 拿流 id（Promise 风格；失败再试 callback 风格）⇒ 再用 chromeMediaSource:'tab' 消费
JS_GRAB_TAB = """
() => new Promise(async (res) => {
  const out = {ok:false, stage:'start'};
  const tid = %d;
  let streamId = null, err = null;
  try {
    streamId = await chrome.tabCapture.getMediaStreamId({targetTabId: tid});
  } catch (e) {
    err = String((e && e.message) || e);
    out.promise_style_error = err;
    try {
      streamId = await new Promise((r) => {
        chrome.tabCapture.getMediaStreamId({targetTabId: tid}, (sid) => {
          const e2 = chrome.runtime.lastError;
          r(e2 ? ('cb:' + e2.message) : sid);
        });
      });
    } catch (e3) {
      err = err + ' | cb:' + String((e3 && e3.message) || e3);
    }
  }
  out.stream_id_present = !!streamId;
  if (!streamId) {
    out.stage = 'getMediaStreamId';
    out.error = err || 'getMediaStreamId 返回空';
    res(out);
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {mandatory: {chromeMediaSource: 'tab', chromeMediaSourceId: streamId}},
      video: false,
    });
    const tr = stream.getAudioTracks()[0];
    out.stage = 'ok';
    out.ok = true;
    out.tracks = stream.getAudioTracks().length;
    out.ready_state = tr ? tr.readyState : null;
    out.settings = tr ? tr.getSettings() : null;
    window.__tabStream = stream;
    res(out);
  } catch (e) {
    out.stage = 'getUserMedia';
    out.error = String((e && e.message) || e);
    res(out);
  }
})
"""

#: 录 10 s ⇒ 解码 ⇒ 100 ms 窗 RMS 包络
JS_RECORD_ENVELOPE = """
() => new Promise(async (res) => {
  const stream = window.__tabStream;
  if (!stream) { res({ok:false, error:'没有 __tabStream'}); return; }
  const chunks = [];
  const mime = (typeof MediaRecorder !== 'undefined')
    ? (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
       ? 'audio/webm;codecs=opus' : 'audio/webm') : '';
  const rec = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
  rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  const done = new Promise((r) => { rec.onstop = r; });
  rec.start(1000);
  await new Promise((r) => setTimeout(r, %d));
  rec.stop();
  await done;                       // ★ 等 onstop（否则会截断）
  const blob = new Blob(chunks, {type: chunks[0] ? chunks[0].type : 'audio/webm'});
  const buf = await blob.arrayBuffer();
  const ac = new AudioContext();
  let audio = null;
  try { audio = await ac.decodeAudioData(buf); } catch (e) {
    res({ok:false, stage:'decode', error:String((e&&e.message)||e), bytes: buf.byteLength});
    return;
  }
  const ch = audio.getChannelData(0);
  const sr = audio.sampleRate;
  const win = Math.max(1, Math.floor(sr * %d / 1000));
  const env = [];
  for (let i = 0; i < ch.length; i += win) {
    let s = 0, n = 0;
    for (let j = i; j < Math.min(ch.length, i + win); j++) { s += ch[j]*ch[j]; n++; }
    if (n) env.push(Math.sqrt(s / n));
  }
  const b64 = await new Promise((r) => {
    const fr = new FileReader();
    fr.onload = () => r(String(fr.result || '').split(',')[1] || '');
    fr.onerror = () => r('');
    fr.readAsDataURL(blob);
  });
  res({ok:true, bytes: buf.byteLength, mime: blob.type, sampleRate: sr,
        duration: audio.duration, channels: audio.numberOfChannels,
        env: env, b64: b64});
})
"""

#: A3：页面内 `createMediaElementSource` ⇒ 只抓页面元素
JS_ELEMENT_CAPTURE = """
() => new Promise(async (res) => {
  try {
    const a = document.getElementById('a');
    if (!a) { res({ok:false, error:'没有 <audio> 元素'}); return; }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    const src = ctx.createMediaElementSource(a);
    const dest = ctx.createMediaStreamDestination();
    src.connect(dest);            // ★ 抓取流
    src.connect(ctx.destination); // ★ 保持可听
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    src.connect(an);
    const buf = new Float32Array(an.fftSize);
    const env = [];
    const t0 = performance.now();
    while (performance.now() - t0 < 3000) {
      an.getFloatTimeDomainData(buf);
      let s = 0;
      for (let i = 0; i < buf.length; i++) s += buf[i]*buf[i];
      env.push(Math.sqrt(s / buf.length));
      await new Promise(r => setTimeout(r, 50));
    }
    window.__elemStream = dest.stream;
    res({ok:true, sampleRate: ctx.sampleRate,
         tracks: dest.stream.getAudioTracks().length,
         env: env, currentTime: a.currentTime, ctxState: ctx.state});
  } catch (e) {
    res({ok:false, error: String((e && e.message) || e)});
  }
})
"""


def _run_attempt(label: str, *, allow_flag: bool, action_key: bool) -> dict:
    """跑一次抓流尝试，返回 attempt dict。"""
    from ext028_029_e2e import start_http_server

    att: dict = {"label": label, "allowlisted_extension_id": allow_flag,
                 "action_key": action_key, "attempts": []}

    srv, http_port, page_url, title = start_http_server(SRC_WAV,
                                                        "EXT033 %s" % label)
    att["page_url"] = page_url
    extra = [
        "--auto-select-tab-capture-source-by-title=%s" % title,
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-running-insecure-content",
        "--disable-features=MediaFoundationVideoCapture",
    ]
    if allow_flag:
        # ★ EXT-033 A 点名的第一条
        extra.append("--allowlisted-extension-id=%s" % H.EXT_ID)

    profile = os.path.join(ROOT, ".tmp", "pw_ext",
                           "ext033probe_%s_%d" % (label, os.getpid()))
    try:
        with H.BrowserSession(profile, extra_args=extra,
                              reuse_profile=True) as bs:
            att["sw_alive"] = bs.ext_sw_alive()
            if not att["sw_alive"]:
                att["error"] = "扩展 SW 没起来"
                return att

            media = bs.new_page()
            media.goto(page_url)
            time.sleep(1.0)
            try:
                media.evaluate("() => { const a=document.getElementById('a');"
                               " a.muted=false; a.volume=1.0; return a.play(); }")
            except Exception as e:
                att["play_error"] = str(e)
            time.sleep(1.5)
            att["media_state"] = media.evaluate(
                "() => { const a=document.getElementById('a');"
                " return {t:a.currentTime, paused:a.paused, dur:a.duration}; }")

            # ★ A3 先在**媒体页**里试（只抓页面元素）
            try:
                att["attempts"].append({"stage": "A3_element",
                                        "result": media.evaluate(JS_ELEMENT_CAPTURE)})
            except Exception as e:
                att["attempts"].append({"stage": "A3_element",
                                        "result": {"ok": False, "error": str(e)}})

            # 拿媒体页 tabId
            popup = bs.open_ext_page("popup.html")
            time.sleep(1.5)
            tab_id = popup.evaluate(JS_GET_TAB_ID % ("127.0.0.1:%d" % http_port))
            att["tab_id"] = tab_id
            if tab_id is None:
                att["error"] = "拿不到媒体页 tabId"
                return att

            # ★ A2：SendInput 合成按键触发 `commands._execute_action`
            if action_key:
                ok = _send_action_hotkey()
                att["action_hotkey_sent"] = ok
                time.sleep(1.5)

            # ★ A1：tabCapture
            grab = popup.evaluate(JS_GRAB_TAB % int(tab_id))
            att["attempts"].append({"stage": "A1_tabCapture", "result": grab})

            if grab.get("ok"):
                media_t = media.evaluate(
                    "() => { const a=document.getElementById('a');"
                    " return a.currentTime; }")
                att["media_time_at_grab"] = media_t
                rec = popup.evaluate(JS_RECORD_ENVELOPE % (int(REC_SEC * 1000),
                                                          ENV_WIN_MS))
                att["attempts"].append({"stage": "A1_record",
                                        "result": {k: v for k, v in rec.items()
                                                   if k != "b64"}})
                if rec.get("ok"):
                    b64 = rec.pop("b64", "")
                    import base64
                    wav_path = os.path.join(OUT_DIR, "captured_%s.webm" % label)
                    with open(wav_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    rec["webm_path"] = wav_path
                    att["attempts"][-1]["result"] = rec
    except Exception as e:
        att["error"] = "%s: %s" % (type(e).__name__, e)
    return att


def _send_action_hotkey() -> bool:
    """A2：用 Windows SendInput 合成按键（EXT-033 A 点名的「操作系统级按键」）。

    默认键位 Ctrl+Shift+Y。**只有** manifest 里配了
    `commands._execute_action` 才会被浏览器当成动作快捷键。
    """
    import ctypes
    user32 = ctypes.windll.user32
    VK_CONTROL, VK_SHIFT, VK_Y = 0x11, 0x10, 0x59
    KEYEVENTF_KEYUP = 0x0002

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ki", KEYBDINPUT)]

    def send(vk, up=False):
        inp = INPUT(type=1, ki=KEYBDINPUT(wVk=vk, wScan=0,
                                         dwFlags=KEYEVENTF_KEYUP if up else 0,
                                         time=0, dwExtraInfo=None))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    for vk in (VK_CONTROL, VK_SHIFT, VK_Y):
        send(vk)
        time.sleep(0.03)
    for vk in (VK_Y, VK_SHIFT, VK_CONTROL):
        send(vk, up=True)
        time.sleep(0.03)
    return True


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    src_env, src_sr = source_envelope(SRC_WAV)
    _log("素材包络：%d 窗 @ %d Hz（%d ms/窗）"
         % (len(src_env), src_sr, ENV_WIN_MS))

    result: dict = {"src_envelope_windows": len(src_env),
                    "src_sample_rate": src_sr,
                    "env_win_ms": ENV_WIN_MS,
                    "rec_sec": REC_SEC,
                    "rounds": []}

    rounds = [
        ("A1_base", dict(allow_flag=False, action_key=False)),
        ("A1_allow", dict(allow_flag=True, action_key=False)),
    ]
    for label, kw in rounds:
        _log("── 尝试 %s ──" % label)
        att = _run_attempt(label, **kw)
        # 与素材包络做相关（抓到的 10 s 对应素材开头 10 s）
        for item in att.get("attempts", []):
            env = (item.get("result") or {}).get("env")
            if env and item.get("stage") in ("A1_record",):
                corr = _pearson(src_env[:len(env)], env)
                item["result"]["corr_with_source_envelope"] = round(corr, 4)
                item["result"]["PASS_content_corr_ge_0.8"] = bool(corr >= 0.8)
        result["rounds"].append(att)
        _log("── %s 结果：%r" % (label, json.dumps(
            [{k: v for k, v in (it.get("result") or {}).items()
              if k in ("ok", "stage", "error", "corr_with_source_envelope",
                       "PASS_content_corr_ge_0.8", "tracks", "settings",
                       "promise_style_error")}
             for it in att.get("attempts", [])], ensure_ascii=False)))

    p = os.path.join(OUT_DIR, "result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log("结果已落盘：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
