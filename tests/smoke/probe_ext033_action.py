#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""probe_ext033_action.py — ★ EXT-033 A2：**SendInput 合成按键触发
`commands._execute_action`** ⇒ 拿到 activeTab ⇒ tabCapture 可用

## 为什么需要这个探针
官方文档（chrome.tabCapture）：
  * `targetTabId`：**只有**「扩展已被授予 activeTab 权限」的标签页才能作为目标；
  * `getMediaStreamId` **不能**凭空拿到别人的标签页。
EXT-032/§25.3 实测的失败原文正是
  「Extension has not been invoked for the current page (see activeTab permission)」。

★ Chrome/Edge 里**只有 `_execute_action` 快捷键**会被当成「扩展被调用」
  ⇒ 触发 activeTab 授权。EXT-033 A2 点名了这条路。
⇒ 本探针用 **Windows SendInput** 合成 `Ctrl+Alt+Y`（manifest 里的
  `commands._execute_action.suggested_key`），
  **等价于用户按快捷键** ⇒ 按 EXT-033 的口径「**算用户手势**」。

## 关键实现细节（踩过的坑）
* `SendInput` 只发给**前台窗口** ⇒ 必须先把**我们的**浏览器窗口置前。
  用**窗口标题里的唯一标记**定位窗口（而不是 PID —— Edge 会换进程）。
* 合成按键后 Chrome 会**弹出 popup**（因为 manifest 有 default_popup）
  ⇒ popup 抢焦点；但 activeTab 授权**不会**因为 popup 关闭而失效。

## 判定标准
抓到流 ⇒ 录 10 s ⇒ 解码 ⇒ 与素材 RMS 包络互相关 ≥ 0.8 ⇒ 算「只抓到了页面音频」。

## 输出
`.tmp/probe_ext033_action/result.json`
"""
from __future__ import annotations

import base64
import ctypes
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

OUT_DIR = os.path.join(ROOT, ".tmp", "probe_ext033_action")

#: manifest 里登记的快捷键（Ctrl+Shift+Y）
#: ⚠️ **不能含 Alt** —— Chrome 判 `commands[1].default` 非法
#:    ⇒ 扩展加载失败 ⇒ Edge 弹「无法加载该扩展」模态框 ⇒ 浏览器起不来。
HOTKEY = (0x11, 0x10, 0x59)      # VK_CONTROL, VK_SHIFT, VK_Y


def _log(msg: str) -> None:
    print("[probe-ext033c] %s" % msg, flush=True)


# ══════════════════════════════════════════════════════════════════
# Win32：定位窗口 + 置前 + SendInput
# ══════════════════════════════════════════════════════════════════
user32 = ctypes.windll.user32

EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))


def find_window_by_title(marker: str):
    """按**标题子串**找顶层窗口（比 PID 可靠：Edge 会换进程）。"""
    found = []

    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if marker in buf.value:
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def focus_window(hwnd) -> bool:
    """把窗口置前（SendInput 只发给前台窗口）。"""
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    # 经典技巧：把本线程的输入队列挂到前台线程，再 SetForegroundWindow
    fg = user32.GetForegroundWindow()
    cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    attached = False
    if fg_tid and fg_tid != cur_tid:
        attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
    user32.BringWindowToTop(hwnd)
    ok = bool(user32.SetForegroundWindow(hwnd))
    if attached:
        user32.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(0.4)
    return ok


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    """★ 必须是**真正的** INPUT 大小（x64 = 40 字节）。

    ⚠️ 踩过的坑：早先只声明了 `{type, ki}` ⇒ `sizeof(INPUT)` = 32
       ⇒ `SendInput(n, &inp, 32)` 与 Windows 的 `sizeof(INPUT)`(=40) 不符
       ⇒ **SendInput 直接失败、返回 0、按键根本没发出去**，
       而现象只是「快捷键没反应」，极难定位。
       ⇒ 现在用完整 union（MOUSEINPUT 最大 ⇒ 尺寸自动对齐到 40），
         并且**校验 SendInput 的返回值**，为 0 就直接报错。
    """
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTunion)]


KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0


def send_hotkey(vks=(0x11, 0x10, 0x59)) -> bool:
    """合成一组按键（**带扫描码**，兼容性最好）。返回是否全部发成功。"""
    ok = True

    def send(vk, up=False):
        nonlocal ok
        sc = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        flags = (KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0))
        inp = INPUT(type=1)
        inp.u.ki = KEYBDINPUT(wVk=0, wScan=sc, dwFlags=flags, time=0,
                              dwExtraInfo=None)
        n = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if n != 1:
            ok = False

    for vk in vks:
        send(vk)
        time.sleep(0.04)
    for vk in reversed(vks):
        send(vk, up=True)
        time.sleep(0.04)
    return ok


# ══════════════════════════════════════════════════════════════════
# 浏览器侧：拿 id → 消费 → 录 10 s → 解码算包络
# ══════════════════════════════════════════════════════════════════
JS_MAKE_ID = """
() => new Promise(async (res) => {
  const tid = %d;
  let id = null, err = null;
  try { id = await chrome.tabCapture.getMediaStreamId({targetTabId: tid}); }
  catch (e) {
    err = String((e && e.message) || e);
    try {
      id = await new Promise((r) => {
        chrome.tabCapture.getMediaStreamId({targetTabId: tid}, (sid) => {
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


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    from ext028_029_e2e import start_http_server

    src_env, src_sr = source_envelope(SRC_WAV)
    marker = "EXT033-A2-%d" % int(time.time())
    srv, http_port, page_url, title = start_http_server(SRC_WAV, marker)
    _log("媒体页：%s（标题标记 %s）" % (page_url, marker))

    extra = [
        "--auto-select-tab-capture-source-by-title=%s" % title,
        "--use-fake-ui-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-running-insecure-content",
        "--disable-features=MediaFoundationVideoCapture",
    ]
    result: dict = {"page_url": page_url, "marker": marker, "steps": []}
    profile = os.path.join(ROOT, ".tmp", "pw_ext",
                           "ext033act_%d" % os.getpid())
    try:
        with H.BrowserSession(profile, extra_args=extra,
                              reuse_profile=True) as bs:
            result["sw_alive"] = bs.ext_sw_alive()
            media = bs.new_page()
            media.goto(page_url)
            time.sleep(1.0)
            media.evaluate("() => { const a=document.getElementById('a');"
                           " a.muted=false; a.volume=1.0; return a.play(); }")
            time.sleep(1.5)
            result["media_state"] = media.evaluate(
                "() => { const a=document.getElementById('a');"
                " return {t:a.currentTime, paused:a.paused}; }")

            # ★ ① 定位并置前**我们的**浏览器窗口
            wins = find_window_by_title(marker)
            result["windows_found"] = [w[1] for w in wins]
            if not wins:
                result["error"] = "找不到标题带标记的窗口"
            else:
                hwnd = wins[0][0]
                result["focus_ok"] = focus_window(hwnd)
                _log("窗口已置前：%r（focus_ok=%r）"
                     % (wins[0][1], result["focus_ok"]))

                # ★ ② 媒体页必须是**活动标签页**（activeTab 授权对象）
                try:
                    media.bring_to_front()
                except Exception as e:
                    _log("bring_to_front 异常：%s" % e)
                time.sleep(1.0)

                # ★ ③ SendInput 合成快捷键（= 用户手势）
                send_hotkey(HOTKEY)
                time.sleep(2.5)
                result["pages_after_hotkey"] = [p.url for p in bs.ctx.pages]
                result["popup_opened"] = any(
                    u.startswith("chrome-extension://") for u in result["pages_after_hotkey"])
                _log("快捷键后页面：%r" % result["pages_after_hotkey"])

                # ★ ④ 拿媒体页 tabId（从扩展页查）
                popup = bs.open_ext_page("popup.html")
                time.sleep(1.5)
                tab_id = popup.evaluate(JS_GET_TAB_ID % ("127.0.0.1:%d" % http_port))
                result["target_tab_id"] = tab_id
                _log("target tabId=%r" % tab_id)

                if tab_id is None:
                    result["error"] = "拿不到媒体页 tabId"
                else:
                    # ★ ⑤ 拿流 id → 消费
                    mk = popup.evaluate(JS_MAKE_ID % int(tab_id))
                    result["make_id"] = {k: v for k, v in mk.items() if k != "id"}
                    if not mk.get("ok"):
                        _log("拿 id 失败：%r" % mk.get("error"))
                    else:
                        cs = popup.evaluate(JS_CONSUME % json.dumps(mk["id"]))
                        result["consume"] = cs
                        _log("consume：%r" % json.dumps(cs, ensure_ascii=False)[:200])
                        if cs.get("ok"):
                            rec = popup.evaluate(
                                JS_RECORD_ENVELOPE % (int(REC_SEC * 1000),
                                                      ENV_WIN_MS))
                            env = rec.pop("env", None)
                            if env:
                                corr = _pearson(src_env[:len(env)], env)
                                rec["corr_with_source_envelope"] = round(corr, 4)
                                rec["PASS_content_corr_ge_0.8"] = bool(corr >= 0.8)
                            b64 = rec.pop("b64", "")
                            if b64:
                                p = os.path.join(OUT_DIR, "captured.webm")
                                with open(p, "wb") as f:
                                    f.write(base64.b64decode(b64))
                                rec["webm_path"] = p
                            result["record"] = rec
                            _log("录音：%r" % json.dumps(
                                {k: v for k, v in rec.items() if k != "env"},
                                ensure_ascii=False)[:400])
    except Exception as e:
        result["error"] = "%s: %s" % (type(e).__name__, e)

    p = os.path.join(OUT_DIR, "result.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    _log("结果已落盘：%s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
