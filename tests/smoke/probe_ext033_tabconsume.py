#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_ext033_tabconsume.py — ★ EXT-033 A：`getMediaStreamId` 拿到 id 后
**到底怎么才能被消费**（逐条实测，原始错误不吞）

## 背景（probe_ext033_capture.py 的实测结论）
* `--allowlisted-extension-id=<插件ID>` ⇒ **`getMediaStreamId` 的 activeTab
  门槛被解除**（不再抛 "Extension has not been invoked for the current page"），
  stream id **能拿到**；
* 但随后 `getUserMedia({chromeMediaSource:'tab', chromeMediaSourceId:id})`
  报 **"Requested device not found"** ⇒ **id 拿对了、消费方式不对**。

## 本探针逐条试的消费方式
| 标签 | 方式 |
|---|---|
| `v1_target_consumer` | `getMediaStreamId({targetTabId:T, consumerTabId:C})` |
| `v2_active_tab` | 先**激活媒体页**，再 `getMediaStreamId({consumerTabId:C})`（抓当前活动页） |
| `v3_active_target_consumer` | 先激活媒体页，再 `getMediaStreamId({targetTabId:T, consumerTabId:C})` |
| `v4_capture_api` | 先激活媒体页，再 `chrome.tabCapture.capture({audio:true}, cb)` |
| `v5_sw_consumer` | 由**后台 SW** 发 id（`consumerTabId` = 消费页 tabId），消费页再取用 |

判定标准同前：抓到流后录 10 s ⇒ 解码 ⇒ 与素材 RMS 包络互相关 ≥ 0.8 才算真抓到。

## 输出
`.tmp/probe_ext033_tabconsume/result.json`
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
from probe_ext033_capture import (SRC_WAV, ENV_WIN_MS, REC_SEC,   # noqa: E402
                                  source_envelope, _pearson,
                                  JS_RECORD_ENVELOPE, JS_GET_TAB_ID)

OUT_DIR = os.path.join(ROOT, ".tmp", "probe_ext033_tabconsume")

#: 拿 id（Promise 优先，失败走 callback）—— 返回 {ok, id, error}
JS_MAKE_ID = """
() => new Promise(async (res) => {
  const opt = %s;
  let id = null, err = null;
  try { id = await chrome.tabCapture.getMediaStreamId(opt); }
  catch (e) {
    err = String((e && e.message) || e);
    try {
      id = await new Promise((r) => {
        chrome.tabCapture.getMediaStreamId(opt, (sid) => {
          const e2 = chrome.runtime.lastError;
          r(e2 ? ('cb:' + e2.message) : sid);
        });
      });
    } catch (e3) { err = err + ' | cb:' + String((e3 && e3.message) || e3); }
  }
  if (!id) { res({ok:false, error: err || 'empty id'}); return; }
  res({ok:true, id: String(id)});
})
"""

#: 用 id 消费（chromeMediaSource:'tab'）
JS_CONSUME = """
() => new Promise(async (res) => {
  const id = %s;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {mandatory: {chromeMediaSource: 'tab', chromeMediaSourceId: id}},
      video: false,
    });
    const tr = stream.getAudioTracks()[0];
    window.__tabStream = stream;
    res({ok:true, tracks: stream.getAudioTracks().length,
         ready_state: tr ? tr.readyState : null,
         settings: tr ? tr.getSettings() : null});
  } catch (e) {
    res({ok:false, error: String((e && e.message) || e),
         name: (e && e.name) || null});
  }
})
"""

#: chrome.tabCapture.capture（老 API，callback 风格）
JS_CAPTURE_API = """
() => new Promise((res) => {
  try {
    chrome.tabCapture.capture({audio:true, video:false}, (s) => {
      const e2 = chrome.runtime.lastError;
      if (e2) { res({ok:false, stage:'capture', error: e2.message}); return; }
      if (!s) { res({ok:false, stage:'capture', error:'null stream'}); return; }
      window.__tabStream = s;
      const tr = s.getAudioTracks()[0];
      res({ok:true, stage:'capture', tracks: s.getAudioTracks().length,
           ready_state: tr ? tr.readyState : null,
           settings: tr ? tr.getSettings() : null});
    });
  } catch (e) { res({ok:false, stage:'capture', error: String((e&&e.message)||e)}); }
})
"""

#: 由后台 SW 发 id（consumerTabId = 消费页 tabId）
JS_SW_MAKE_ID = """
() => new Promise((res) => {
  chrome.runtime.sendMessage({
    kind: 'ext033_make_stream_id', consumerTabId: %d
  }, (r) => {
    const e2 = chrome.runtime.lastError;
    if (e2) { res({ok:false, error: 'sw:' + e2.message}); return; }
    if (!r || !r.ok) { res(r || {ok:false, error:'SW 无返回'}); return; }
    res(r);
  });
})
"""


def _log(msg: str) -> None:
    print("[probe-ext033b] %s" % msg, flush=True)


def _try_chain(popup, media, tab_id, consumer_tab_id, *, activate_first,
               label, src_env):
    """按顺序试若干消费方式，返回 attempt 列表。"""
    out = []
    if activate_first:
        try:
            media.bring_to_front()
            time.sleep(1.2)
        except Exception as e:
            _log("激活媒体页失败：%s" % e)

    variants = [
        ("v1_target_consumer",
         {"targetTabId": tab_id, "consumerTabId": consumer_tab_id}, False),
        ("v2_active_tab",
         {"consumerTabId": consumer_tab_id}, True),
        ("v3_active_target_consumer",
         {"targetTabId": tab_id, "consumerTabId": consumer_tab_id}, True),
    ]
    for name, opt, need_activate in variants:
        if need_activate and not activate_first:
            try:
                media.bring_to_front()
                time.sleep(1.2)
            except Exception:
                pass
        mk = popup.evaluate(JS_MAKE_ID % json.dumps(opt))
        if not mk.get("ok"):
            out.append({"variant": name, "stage": "make_id",
                        "result": {"ok": False, "error": mk.get("error")}})
            _log("  %s：拿 id 失败 %r" % (name, mk.get("error")))
            continue
        cs = popup.evaluate(JS_CONSUME % json.dumps(mk["id"]))
        res = {"make_id": {"ok": True}, "consume": cs}
        if cs.get("ok"):
            rec = popup.evaluate(JS_RECORD_ENVELOPE
                                 % (int(REC_SEC * 1000), ENV_WIN_MS))
            env = rec.pop("env", None)
            if env:
                corr = _pearson(src_env[:len(env)], env)
                rec["corr_with_source_envelope"] = round(corr, 4)
                rec["PASS_content_corr_ge_0.8"] = bool(corr >= 0.8)
            res["record"] = rec
        out.append({"variant": name, "stage": "consume", "result": res})
        _log("  %s：consume=%r" % (name, json.dumps(
            cs, ensure_ascii=False)[:200]))
        if cs.get("ok"):
            break

    # v4：老 API capture（需先激活媒体页）
    try:
        media.bring_to_front()
        time.sleep(1.2)
    except Exception:
        pass
    cap = popup.evaluate(JS_CAPTURE_API)
    res = {"capture_api": cap}
    if cap.get("ok"):
        rec = popup.evaluate(JS_RECORD_ENVELOPE
                             % (int(REC_SEC * 1000), ENV_WIN_MS))
        env = rec.pop("env", None)
        if env:
            corr = _pearson(src_env[:len(env)], env)
            rec["corr_with_source_envelope"] = round(corr, 4)
            rec["PASS_content_corr_ge_0.8"] = bool(corr >= 0.8)
        res["record"] = rec
    out.append({"variant": "v4_capture_api", "stage": "consume", "result": res})
    _log("  v4_capture_api：%r" % json.dumps(cap, ensure_ascii=False)[:200])
    return out


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    from ext028_029_e2e import start_http_server

    src_env, src_sr = source_envelope(SRC_WAV)
    _log("素材包络 %d 窗" % len(src_env))

    srv, http_port, page_url, title = start_http_server(SRC_WAV,
                                                        "EXT033 consume")
    extra = [
        "--auto-select-tab-capture-source-by-title=%s" % title,
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-running-insecure-content",
        "--disable-features=MediaFoundationVideoCapture",
        "--allowlisted-extension-id=%s" % H.EXT_ID,     # ★ EXT-033 A
    ]
    result: dict = {"page_url": page_url, "rounds": []}
    profile = os.path.join(ROOT, ".tmp", "pw_ext",
                           "ext033cons_%d" % os.getpid())
    try:
        with H.BrowserSession(profile, extra_args=extra,
                              reuse_profile=True) as bs:
            if not bs.ext_sw_alive():
                raise RuntimeError("扩展 SW 没起来")
            media = bs.new_page()
            media.goto(page_url)
            time.sleep(1.0)
            media.evaluate("() => { const a=document.getElementById('a');"
                           " a.muted=false; a.volume=1.0; return a.play(); }")
            time.sleep(1.5)
            popup = bs.open_ext_page("popup.html")
            time.sleep(1.5)
            tab_id = popup.evaluate(JS_GET_TAB_ID % ("127.0.0.1:%d" % http_port))
            consumer_tab_id = popup.evaluate(
                "() => new Promise((res)=>chrome.tabs.getCurrent("
                "(t)=>res(t?t.id:null)))")
            _log("target tab=%r consumer tab=%r" % (tab_id, consumer_tab_id))
            result["target_tab_id"] = tab_id
            result["consumer_tab_id"] = consumer_tab_id

            if tab_id is None or consumer_tab_id is None:
                result["error"] = "拿不到 tabId"
            else:
                result["rounds"].append({
                    "label": "consume_chain",
                    "attempts": _try_chain(popup, media, int(tab_id),
                                           int(consumer_tab_id),
                                           activate_first=False,
                                           label="chain", src_env=src_env),
                })
    except Exception as e:
        result["error"] = "%s: %s" % (type(e).__name__, e)

    p = os.path.join(OUT_DIR, "result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log("结果已落盘：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
