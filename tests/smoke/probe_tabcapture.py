#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_tabcapture.py — ★ 快速探针：`chrome.tabCapture.capture({targetTabId})`
到底为什么失败？（EXT-027①）

## 为什么需要这个探针
EXT-028/029 的 e2e 实测：抓流走的是 `getDisplayMedia`（兜底）而不是
`tabCapture`（生产路径）⇒ 抓到的是**整机系统声音** ⇒ ASR 出来是中文
⇒ 英译中根本没测到。

而 `tabCapture` 失败的原因**原文**此前没被记下来（只记了「降级了」）
⇒ 排查只能猜。本探针**专门**把这个错误原文抓出来。

## 跑法
    python tests/smoke/probe_tabcapture.py

## 输出
`.tmp/probe_tabcapture/result.json`（含每次尝试的错误原文）
"""
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

OUT_DIR = os.path.join(ROOT, ".tmp", "probe_tabcapture")
PROFILE = os.path.join(ROOT, ".tmp", "pw_ext",
                        "probe_tabcapture_%d" % os.getpid())

#: 素材：英文 60 s（只读引用 R2T2 仓库自带）
SRC_WAV = (r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
           r"\test_en_60s.wav")


def _log(msg: str) -> None:
    print("[probe-tabcapture] %s" % msg, flush=True)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    from ext028_029_e2e import start_http_server   # 复用 e2e 的 http 服务

    srv, http_port, page_url, title = start_http_server(SRC_WAV,
                                                        "TabCapture probe")
    _log("媒体页：%s" % page_url)
    result: dict = {"page_url": page_url, "attempts": []}

    extra = [
        "--auto-select-tab-capture-source-by-title=%s" % title,
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
    ]
    try:
        with H.BrowserSession(PROFILE, extra_args=extra,
                              reuse_profile=True) as bs:
            if not bs.ext_sw_alive():
                raise RuntimeError("扩展 SW 没起来")
            _log("扩展 SW 已起来")

            # 媒体页要先播起来（tabCapture 只抓「正在出声」的标签页）
            media = bs.new_page()
            media.goto(page_url)
            media.evaluate("() => { const a=document.getElementById('a');"
                           " a.play(); return true; }")
            time.sleep(2.0)
            _log("媒体页状态：%r" % media.evaluate(
                "() => { const a=document.getElementById('a');"
                " return {t:a.currentTime, paused:a.paused}; }"))

            # ★ 从**扩展页**（popup）拿媒体页 tabId
            #   （chrome.tabs 在扩展页可用，普通网页没有）
            popup = bs.open_ext_page("popup.html")
            time.sleep(1.5)
            tab_id = popup.evaluate(
                "() => new Promise((res) => "
                "chrome.tabs.query({},"
                "(tabs)=>{const t=tabs.find("
                "x=>x.url&&x.url.indexOf('127.0.0.1:%d')>=0);"
                "res(t?t.id:null)}))" % http_port)
            _log("媒体页 tabId = %r" % tab_id)
            result["tab_id"] = tab_id

            if tab_id is None:
                result["error"] = "拿不到媒体页 tabId"
            else:
                # ── 尝试 1：直接从扩展页调 chrome.tabCapture.capture ──
                #   （player 页走的就是这条）
                # ★★★ **callback 风格**才是 Chromium 的真实签名：
                #   `capture(options, callback)` ⇒ Promise 风格会抛
                #   "No matching signature"（实测 Edge 156）。
                for label, js in (
                    ("promise_style",
                     "() => chrome.tabCapture.capture({audio:true,"
                     "video:false,targetTabId:%d})"
                     "  .then(s=>({ok:true,tracks:s.getAudioTracks().length,"
                     "           rate:(s.getAudioTracks()[0]&&"
                     "           s.getAudioTracks()[0].getSettings()"
                     "           .sampleRate)||null}))"
                     "  .catch(e=>({ok:false,error:String((e&&e.message)||e),"
                     "            name:(e&&e.name)||null}))" % int(tab_id)),
                    ("callback_style",
                     "() => new Promise((res)=>{"
                     "  try{"
                     "    chrome.tabCapture.capture({audio:true,video:false,"
                     "      targetTabId:%d},(s)=>{"
                     "      if(!s){res({ok:false,error:'callback got null stream'});"
                     "        return;}"
                     "      const t=s.getAudioTracks()[0];"
                     "      res({ok:true,tracks:s.getAudioTracks().length,"
                     "           rate:(t&&t.getSettings?t.getSettings()"
                     "             .sampleRate:null)});});"
                     "  }catch(e){res({ok:false,"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})" % int(tab_id)),
                    ("callback_style_no_target",
                     "() => new Promise((res)=>{"
                     "  try{"
                     "    chrome.tabCapture.capture({audio:true,video:false},"
                     "      (s)=>{"
                     "      if(!s){res({ok:false,error:'callback got null stream'});"
                     "        return;}"
                     "      res({ok:true,tracks:s.getAudioTracks().length});});"
                     "  }catch(e){res({ok:false,"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})"),
                    # ★★ **真正的可行解**：
                    #   `getMediaStreamId({targetTabId})` + offscreen 的
                    #   `getUserMedia({audio:{mandatory:{chromeMediaSource:'tab',
                    #   chromeMediaSourceId: streamId}}})`
                    #   ⇒ 只抓该标签页音频 ⇒ 天然满足 EXT-027①。
                    ("get_media_stream_id_with_target",
                     "() => new Promise((res)=>{"
                     "  try{"
                     "    chrome.tabCapture.getMediaStreamId({targetTabId:%d},"
                     "      (id)=>{"
                     "      res(id?{ok:true,streamId:id}:"
                     "             {ok:false,error:'callback got empty id'});});"
                     "  }catch(e){res({ok:false,"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})" % int(tab_id)),
                    ("get_media_stream_id_no_target",
                     "() => new Promise((res)=>{"
                     "  try{"
                     "    chrome.tabCapture.getMediaStreamId("
                     "      (id)=>{"
                     "      res(id?{ok:true,streamId:id}:"
                     "             {ok:false,error:'callback got empty id'});});"
                     "  }catch(e){res({ok:false,"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})"),
                    # ★★★ 全链路：getMediaStreamId → getUserMedia(chromeMediaSource:'tab')
                    #   ⇒ 这才是 EXT-027①「只抓页面元素音频」的真解。
                    ("full_chain_streamid_then_gum",
                     "() => new Promise((res)=>{"
                     "  const step1=(id)=>{"
                     "    if(!id){res({ok:false,stage:'getMediaStreamId',"
                     "      error:'empty streamId'});return;}"
                     "    navigator.mediaDevices.getUserMedia({audio:{mandatory:{"
                     "      chromeMediaSource:'tab',"
                     "      chromeMediaSourceId:id}},video:false})"
                     "      .then(s=>{const t=s.getAudioTracks()[0];"
                     "        res({ok:true,stage:'gum',streamId:id,"
                     "          tracks:s.getAudioTracks().length,"
                     "          rate:(t&&t.getSettings?t.getSettings()"
                     "            .sampleRate:null),"
                     "          label:(t&&t.label)||null});})"
                     "      .catch(e=>res({ok:false,stage:'gum',streamId:id,"
                     "        error:String((e&&e.message)||e),"
                     "        name:(e&&e.name)||null}));};"
                     "  try{"
                     "    chrome.tabCapture.getMediaStreamId({targetTabId:%d},"
                     "      (id)=>step1(id));"
                     "  }catch(e){res({ok:false,stage:'getMediaStreamId',"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})" % int(tab_id)),
                    ("full_chain_no_target_gum",
                     "() => new Promise((res)=>{"
                     "  const step1=(id)=>{"
                     "    if(!id){res({ok:false,stage:'getMediaStreamId',"
                     "      error:'empty streamId'});return;}"
                     "    navigator.mediaDevices.getUserMedia({audio:{mandatory:{"
                     "      chromeMediaSource:'tab',"
                     "      chromeMediaSourceId:id}},video:false})"
                     "      .then(s=>{const t=s.getAudioTracks()[0];"
                     "        res({ok:true,stage:'gum',streamId:id,"
                     "          tracks:s.getAudioTracks().length,"
                     "          rate:(t&&t.getSettings?t.getSettings()"
                     "            .sampleRate:null),"
                     "          label:(t&&t.label)||null});})"
                     "      .catch(e=>res({ok:false,stage:'gum',streamId:id,"
                     "        error:String((e&&e.message)||e),"
                     "        name:(e&&e.name)||null}));};"
                     "  try{"
                     "    chrome.tabCapture.getMediaStreamId("
                     "      (id)=>step1(id));"
                     "  }catch(e){res({ok:false,stage:'getMediaStreamId',"
                     "    error:String((e&&e.message)||e),"
                     "    name:(e&&e.name)||null});}"
                     "})"),
                ):
                    try:
                        r = popup.evaluate(js)
                    except Exception as e:
                        r = {"ok": False,
                             "error": "%s: %s" % (type(e).__name__, e)}
                    _log("[%s] %r" % (label, r))
                    result["attempts"].append({"label": label, "result": r})

                # ── 尝试 2：先让扩展「被调用」过该标签页 ──
                #   （tabCapture 需要扩展对该页有「invoked」状态）
                try:
                    r2 = popup.evaluate(
                        "() => chrome.tabs.query({active:true,"
                        "currentWindow:true},(tabs)=>{"
                        "  const t=tabs.find(x=>x.url&&"
                        "    x.url.indexOf('127.0.0.1:%d')>=0);"
                        "  return t?{id:t.id,active:t.active}:null;})"
                        % http_port)
                    _log("媒体页是否 active：%r" % r2)
                    result["media_tab_active"] = r2
                except Exception as e:
                    result["media_tab_active_error"] = str(e)

                # ═══ 尝试 3：三种「让扩展被 invoke」的手段 ═══
                #  A. scripting.executeScript 注入目标页（让扩展对该页有 invoked）
                #  B. 把目标页切成 active，再 capture()（capture 抓「当前活动页」）
                #  C. A 之后再 getMediaStreamId({targetTabId})
                strategies = [
                    ("A_scripting_invoke_then_gmsid",
                     "() => new Promise((res)=>{"
                     "  chrome.scripting.executeScript({target:{tabId:%d},"
                     "    func:()=>1}).then(()=>{"
                     "      chrome.tabCapture.getMediaStreamId({targetTabId:%d},"
                     "        (id)=>res({ok:!!id,streamId:id||null}));"
                     "    }).catch(e=>res({ok:false,"
                     "      error:String((e&&e.message)||e)}));})"
                     % (int(tab_id), int(tab_id))),
                    ("B_activate_then_capture",
                     "() => new Promise((res)=>{"
                     "  chrome.tabs.update(%d,{active:true}).then(()=>{"
                     "    setTimeout(()=>{"
                     "      try{"
                     "        chrome.tabCapture.capture({audio:true,video:false},"
                     "          (s)=>res(s?{ok:true,tracks:s.getAudioTracks().length}"
                     "                   :{ok:false,error:'null stream'}));"
                     "      }catch(e){res({ok:false,"
                     "        error:String((e&&e.message)||e)});}"
                     "    },800);"
                     "  }).catch(e=>res({ok:false,"
                     "    error:String((e&&e.message)||e)}));})" % int(tab_id)),
                    ("C_scripting_then_capture",
                     "() => new Promise((res)=>{"
                     "  chrome.scripting.executeScript({target:{tabId:%d},"
                     "    func:()=>1}).then(()=>{"
                     "    setTimeout(()=>{"
                     "      try{"
                     "        chrome.tabCapture.capture({audio:true,video:false},"
                     "          (s)=>res(s?{ok:true,tracks:s.getAudioTracks().length}"
                     "                   :{ok:false,error:'null stream'}));"
                     "      }catch(e){res({ok:false,"
                     "        error:String((e&&e.message)||e)});}"
                     "    },800);"
                     "  }).catch(e=>res({ok:false,"
                     "    error:String((e&&e.message)||e)}));})" % int(tab_id)),
                ]
                for label, js in strategies:
                    try:
                        r = popup.evaluate(js)
                    except Exception as e:
                        r = {"ok": False,
                             "error": "%s: %s" % (type(e).__name__, e)}
                    _log("[%s] %r" % (label, r))
                    result["attempts"].append({"label": label, "result": r})

                # ═══ 尝试 4：**属性是否存在**（不靠试错，直接看 API 面）═══
                #   `capture` 与 `getMediaStreamId` 的 options 属性集**不同**：
                #     capture  ⇒ 只有 {audio, video}（**没有** targetTabId）
                #     getMediaStreamId ⇒ 有 {targetTabId, consumerTabId}
                #   ⇒ 属性不合法时 Chromium 会抛
                #     "Unexpected property: 'xxx'" ⇒ 可用它**反推**属性是否存在。
                for label, js in (
                    ("sig_probe_capture_targetTabId",
                     "() => { try{"
                     "  chrome.tabCapture.capture({audio:true,video:false,"
                     "    targetTabId:%d},()=>{});"
                     "  return {noThrow:true};}catch(e){"
                     "  return {noThrow:false,"
                     "    error:String((e&&e.message)||e)};}}"
                     % int(tab_id)),
                    ("sig_probe_capture_audio_only",
                     "() => { try{"
                     "  chrome.tabCapture.capture({audio:true,video:false},"
                     "    ()=>{});"
                     "  return {noThrow:true};}catch(e){"
                     "  return {noThrow:false,"
                     "    error:String((e&&e.message)||e)};}}"),
                    ("sig_probe_gmsid_targetTabId",
                     "() => { try{"
                     "  chrome.tabCapture.getMediaStreamId({targetTabId:%d},"
                     "    ()=>{});"
                     "  return {noThrow:true};}catch(e){"
                     "  return {noThrow:false,"
                     "    error:String((e&&e.message)||e)};}}"
                     % int(tab_id)),
                    ("sig_probe_gmsid_consumerTabId",
                     "() => { try{"
                     "  chrome.tabCapture.getMediaStreamId({consumerTabId:%d},"
                     "    ()=>{});"
                     "  return {noThrow:true};}catch(e){"
                     "  return {noThrow:false,"
                     "    error:String((e&&e.message)||e)};}}"
                     % int(tab_id)),
                    ("sig_probe_gmsid_empty",
                     "() => { try{"
                     "  chrome.tabCapture.getMediaStreamId(()=>{});"
                     "  return {noThrow:true};}catch(e){"
                     "  return {noThrow:false,"
                     "    error:String((e&&e.message)||e)};}}"),
                ):
                    try:
                        r = popup.evaluate(js)
                    except Exception as e:
                        r = {"ok": False,
                             "error": "%s: %s" % (type(e).__name__, e)}
                    _log("[%s] %r" % (label, r))
                    result["attempts"].append({"label": label, "result": r})

    except Exception as e:
        import traceback
        traceback.print_exc()
        result["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass

    p = os.path.join(OUT_DIR, "result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log("结果已落盘：%s" % p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
