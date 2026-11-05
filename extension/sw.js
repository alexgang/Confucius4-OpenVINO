/**
 * sw.js — MV3 Service Worker（EXT-003 P0① 的编排层）
 *
 * 职责（EXT-001 A 节）：
 *   popup「开始」→ 拿到目标 tab → chrome.tabCapture.getMediaStreamId()
 *   → 建 offscreen document → 把 streamId + 桥接参数交给 offscreen
 *   → offscreen 里 getUserMedia({chromeMediaSource:'tab'}) 拿到整页音视频流
 *   → AudioWorklet 重采样 16 kHz → WebSocket 上行 {seq, sample_index}
 *
 * ★ 本机实测约束（见 STATUS_EXT.md §2）：
 *   `chrome.tabCapture.getMediaStreamId()` 需要**真实用户点击扩展图标**，
 *   自动化环境会报 "Extension has not been invoked for the current page"。
 *   ⇒ 生产路径 = popup 按钮点击（真实手势）；
 *     自动化/测试路径 = offscreen 里 getDisplayMedia（等价抓整页音视频）。
 *
 * 只做编排；音频处理与上行在 offscreen，延迟画面与配音排程在 player 页面。
 */

const OFFSCREEN_URL = 'offscreen.html';

/**
 * ★★ EXT-031③：读「允许的抓流方式」白名单（**唯一事实源 = manifest**）。
 *
 * - `manifest.json` → `liveDub.captureModes`（发行包由
 *   `release/build_release.py` 改写为 `["tabCapture"]`）
 * - 发行版 = **只有标签页音频路径**（EXT-027①）
 *   ⇒ `getDisplayMedia`（整机声音）**默认关闭**。
 * - 读不到 ⇒ 按**最严**处理（只允许 tabCapture）⇒ 宁可失败，
 *   绝不静默抓整机声音。
 */
function readAllowedCaptureModes() {
  try {
    const m = (chrome.runtime.getManifest() || {});
    const ld = m.liveDub || {};
    const list = Array.isArray(ld.captureModes) ? ld.captureModes : null;
    if (list && list.length) return list;
    return ld.release ? ['tabCapture'] : ['tabCapture', 'getDisplayMedia'];
  } catch (e) {
    return ['tabCapture'];
  }
}

let sessionState = {
  running: false,
  tabId: null,
  wsUrl: null,
  startedAt: null,
  lastError: null,
};

async function hasOffscreen() {
  try {
    if (chrome.offscreen.hasDocument) return await chrome.offscreen.hasDocument();
    const ctx = await chrome.runtime.getContexts({
      contextTypes: ['OFFSCREEN_DOCUMENT'],
      documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
    });
    return ctx.length > 0;
  } catch (e) {
    return false;
  }
}

async function ensureOffscreen() {
  if (!await hasOffscreen()) {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      reasons: ['USER_MEDIA'],
      justification: '捕获标签页音频流，重采样到 16 kHz 并实时上行到本地桥接服务。',
    });
  }
  // ★ offscreen 文档的脚本是**异步加载**的：createDocument 返回时
  //   offscreen.js 还没跑完、还没 connect 上来 ⇒ 控制通道尚未建立。
  //   ⇒ 轮询 ping，等 offscreen 主动连上再继续。
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 200));
    if (offPort) {
      const p = await offscreenCall('ping', {}, 2000);
      if (p && p.ok) return;
    }
  }
  throw new Error('offscreen 未就绪（控制通道未建立）');
}

// ── Port 中继：player ↔ offscreen（视频块） ─────────────────────
// MV3 里 MediaStream 不能跨上下文传递 ⇒ offscreen 抓到流后，
// 把「已编码视频块」通过端口送到 player 窗口；
// player 维护带时间戳的环形缓冲并按 D 延迟解码播放（EXT-001 A 节）。
// ★ 'ext-offscreen' 是 SW↔offscreen 的**控制通道**（见 offscreenCall），
//   不参与下面的中继，否则会与控制通道抢消息。
const PORTS = { offscreen: null, player: null };

chrome.runtime.onConnect.addListener((port) => {
  if (port.name === 'ext-offscreen') return;   // 控制通道，单独处理
  const which = port.name === 'ext-player' ? 'player' : 'offscreen';
  PORTS[which] = port;
  port.onDisconnect.addListener(() => { if (PORTS[which] === port) PORTS[which] = null; });
  port.onMessage.addListener((m) => {
    const other = which === 'player' ? PORTS.offscreen : PORTS.player;
    if (other) { try { other.postMessage(m); } catch (e) { /* ignore */ } }
  });
});

function relayToPlayer(msg) {
  if (PORTS.player) { try { PORTS.player.postMessage(msg); return true; } catch (e) { /* ignore */ } }
  return false;
}
function relayToOffscreen(msg) {
  if (PORTS.offscreen) { try { PORTS.offscreen.postMessage(msg); return true; } catch (e) { /* ignore */ } }
  return false;
}

chrome.runtime.onInstalled.addListener(async () => {
  const defaults = {
    wsUrl: 'ws://127.0.0.1:8765/',
    delaySec: 20,
    // ★★ T-3：targetLang 默认值必须是**引擎码** 'zh'
    //   （旧值 'Chinese' 与引擎的 zh/en/ja/ko 不匹配）。
    targetLang: 'zh',
    voice: 'A',
    duckDb: -15,
    subsOn: true,
    token: '',
  };
  const cur = await chrome.storage.local.get(defaults);
  await chrome.storage.local.set({ ...defaults, ...cur });
});

// ★ MV3 消息通道规则：同一个 channel 里**只能有一个 listener 返回 true**
//   （返回 true = 该 listener 会异步调 sendResponse）。
//   若两个 listener 都返回 true ⇒ 调用方收到
//   "message channel closed before a response was received"。
//   ⇒ SW↔offscreen **不走 sendMessage**，改走 **Port**（见 OFFSCREEN_PORT）。
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (!msg || msg.target !== 'sw') return;
      const r = await handleSw(msg);
      sendResponse({ ok: true, ...r });
    } catch (e) {
      sessionState.lastError = String((e && e.message) || e);
      sendResponse({ ok: false, error: sessionState.lastError });
    }
  })();
  return true; // 异步响应
});

// ── SW ↔ offscreen 的 Port 通道 ─────────────────────────────────
// ★ 关键架构决定（实测踩坑）：
//   MV3 service worker 里 `chrome.runtime.connect()` **必须在 event 回调的
//   同步栈里调用**；一旦跨过 await 再 connect，port 立刻失效，
//   报 "Could not establish connection. Receiving end does not exist."。
//   ⇒ 反过来做：**offscreen 文档在脚本加载时立即 connect 到 SW**，
//     SW 持有该 port 引用并通过它下发命令。
const OFFSCREEN_PORT = 'ext-offscreen';
let offPort = null;          // offscreen 主动连来的控制通道
const offPending = new Map(); // reqId → resolve
let offReqSeq = 0;

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== OFFSCREEN_PORT) return;   // 其它 Port 走中继逻辑
  offPort = port;
  port.onDisconnect.addListener(() => {
    if (offPort === port) offPort = null;
    for (const [, res] of offPending) res({ ok: false, error: 'offscreen 断开' });
    offPending.clear();
  });
  port.onMessage.addListener((m) => {
    if (!m || !m.reqId) return;
    const res = offPending.get(m.reqId);
    if (res) { offPending.delete(m.reqId); res(m.result || { ok: false, error: '无结果' }); }
  });
});

function offscreenCall(cmd, payload, timeoutMs = 15000) {
  return new Promise((resolve) => {
    if (!offPort) {
      resolve({ ok: false, error: 'offscreen 未连接' });
      return;
    }
    const reqId = 'rq_' + (++offReqSeq);
    const timer = setTimeout(() => {
      offPending.delete(reqId);
      resolve({ ok: false, error: 'offscreen 超时' });
    }, timeoutMs);
    offPending.set(reqId, (r) => { clearTimeout(timer); resolve(r); });
    try {
      offPort.postMessage({ cmd, reqId, ...(payload || {}) });
    } catch (e) {
      clearTimeout(timer);
      offPending.delete(reqId);
      resolve({ ok: false, error: String(e) });
    }
  });
}

async function handleSw(msg) {
  switch (msg.cmd) {
    case 'getStreamId': {
      // ★ 真实用户手势路径（popup 按钮点击 → service worker）
      const streamId = await chrome.tabCapture.getMediaStreamId({
        consumerTabId: msg.tabId,
      });
      return { streamId };
    }
    case 'start': {
      await ensureOffscreen();
      // ★★★ EXT-031③：发行版**禁用**整机 getDisplayMedia 回退。
      //   唯一事实源 = manifest 的 `liveDub.captureModes`
      //   （发行包由 `release/build_release.py` 改成 ["tabCapture"]）。
      //   ⇒ 开发目录里仍可回退（自动化冒烟需要），
      //     **发行版里只保留 EXT-027 的标签页音频路径**。
      const allowed = (readAllowedCaptureModes());
      // 生产：先尝试 tabCapture；失败则退回 getDisplayMedia（offscreen 内部判断）
      let streamId = null;
      let captureMode = 'tabCapture';
      if (msg.useDisplayMedia) {
        captureMode = 'getDisplayMedia';
      } else {
        try {
          streamId = await chrome.tabCapture.getMediaStreamId({
            consumerTabId: msg.tabId,
          });
        } catch (e) {
          // 拿不到 stream id（无用户手势 / 自动化）⇒ 走 getDisplayMedia
          captureMode = 'getDisplayMedia';
          streamId = null;
        }
      }
      if (captureMode === 'getDisplayMedia' && !allowed.includes('getDisplayMedia')) {
        // ★ 发行版：**明确失败**，绝不静默抓整机声音。
        throw new Error('发行版已禁用 getDisplayMedia 整机回退（只保留标签页音频路径）：'
          + (streamId ? '' : 'tabCapture 不可用（需要用户点击扩展图标授权）'));
      }
      // ★★ EXT-027①：把**目标标签页 id** 传给 offscreen
      //   ⇒ offscreen 优先用 `chrome.tabCapture.capture({targetTabId})`
      //     **只抓该标签页的音频**（而不是 getDisplayMedia 的整机系统声音）。
      const res = await offscreenCall('start', {
        streamId,
        targetTabId: msg.tabId,
        display: captureMode === 'getDisplayMedia'
          ? { frameRate: msg.frameRate || 30 }
          : null,
        wsUrl: msg.wsUrl,
        token: msg.token,
        delaySec: msg.delaySec,
        // ★★ T-3：把目标语言与音色透传给 offscreen
        //   （⇒ 再由 hello 带给桥接服务）。
        //   旧写法这两个字段**根本没进 start 消息** ⇒ 面板上的
        //   「目标语言」「音色」都是摆设。
        targetLang: msg.targetLang || null,
        voice: msg.voice || null,
      });
      // ★★ EXT-027①：**如实**报告**实际**用的抓流方式。
      //   `captureMode` 上面那个只是**计划值**（SW 想走哪条路）；
      //   真正用的是 offscreen 里的那一条（它会先试
      //   `tabCapture.capture({targetTabId})`，失败才降级）
      //   ⇒ 以 offscreen 回的 `captureMode` 为准，**绝不**把降级说成 tabCapture。
      const actualMode = (res && res.offscreen && res.offscreen.captureMode)
        ? res.offscreen.captureMode : captureMode;
      sessionState = {
        running: true, tabId: msg.tabId, wsUrl: msg.wsUrl,
        startedAt: Date.now(), lastError: null, captureMode: actualMode,
        targetTabId: msg.tabId,
        targetLang: msg.targetLang || null, voice: msg.voice || null,
      };
      return { streamId, captureMode: actualMode, plannedCaptureMode: captureMode,
               offscreen: res };
    }
    case 'stop': {
      try {
        await offscreenCall('stop', {}, 5000);
      } catch (e) { /* offscreen 可能已关 */ }
      sessionState.running = false;
      return { stopped: true };
    }
    // ★★★ EXT-026 修正：**收口尾段**（生产路径）。
    //   ## 为什么需要
    //     服务端的流式分段会把最后一段留在缓冲区 ⇒ 客户端必须发
    //     `{"type":"flush"}` 才能让尾段跑完并下发。
    //   ★ 生产路径的上行 WS 在 **offscreen** 里（不是 player）⇒
    //     flush 必须由 offscreen 发出 ⇒ SW 只是个中转。
    //   ⇒ 用户点「停止」时最后一句不再丢。
    case 'flush': {
      let r = { ok: false, error: 'offscreen 不可用' };
      try {
        r = await offscreenCall('flush', {}, 8000);
      } catch (e) {
        r = { ok: false, error: String((e && e.message) || e) };
      }
      return r;
    }
    case 'status': {
      let stats = {};
      try {
        const r = await offscreenCall('stats', {}, 5000);
        if (r && r.stats) stats = r.stats;
        else if (r && r.ok) stats = r;
      } catch (e) { /* ignore */ }
      return { ...sessionState, ...stats };
    }
    case 'metrics': {
      // player 页面回报指标 ⇒ 转给 offscreen（用于统一汇总）
      relayToOffscreen({ kind: 'playerMetrics', metrics: msg.metrics });
      return { relayed: true };
    }
    default:
      return { error: `unknown cmd ${msg.cmd}` };
  }
}

// 供 player 页面订阅的广播（桥接服务下发的配音任务等）
// ★ 这里**不能**返回 true —— 主 listener 已经占用了异步响应通道。
//   广播本身是单向的，直接 relay 即可。
chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.target !== 'sw-broadcast') return;
  relayToPlayer(msg.payload || {});
  // ★★ EXT-024 A：**同时**用 runtime 广播给所有扩展页面（player.html）。
  //   为什么必须加这条：`relayToPlayer` 走的是 **Port**（'ext-player'），
  //   而 player.html **从来不开 Port** ⇒ 那条路其实是死的
  //   ⇒ offscreen 收到的 tts 根本到不了 player。
  //   ⇒ 现在：offscreen → sendMessage('sw-broadcast') → SW → runtime 广播
  //     → player.html 的 onMessage 监听 ⇒ handleBridgeMessage。
  //   ⚠️ player 自己的 WS 也会收到同一条 tts ⇒ 靠 `seenDubIds` 按 id 去重，
  //     只会排程/计数一次。
  try {
    chrome.runtime.sendMessage({
      target: 'ext-dub',
      payload: msg.payload || {},
    });
  } catch (e) { /* ignore */ }
  return false;
});
