/**
 * popup.js — 扩展弹窗
 *
 * EXT-001 A 节：popup 提供 开始/停止、目标语言、延迟 D、音色、原声压低量、
 * 字幕开关、桥接连接状态。
 *
 * ★ EXT-012：用户面向的改造
 *   ① **token 自动配对** —— 不再要求用户手动复制 token：
 *      popup 直接向本机配对端点 `http://127.0.0.1:<pair_port>/pair` 取
 *      （端点只接受 `Origin: chrome-extension://` ⇒ 网页拿不到）；
 *   ② **显示桥接连接状态 / 当前延迟 D / 语速倍率 / 滞后**；
 *   ③ **「打开说明」链接**（USER_GUIDE.md）。
 *
 * ★ 关键：用户点「开始」= **真实用户手势** ⇒ 这是 chrome.tabCapture
 *   拿到 stream id 的**唯一**方式（自动化下会报
 *   "Extension has not been invoked for the current page"，见 STATUS §2）。
 */

const $ = (id) => document.getElementById(id);

// ★ 桥接地址 ⇒ 推出配对端点地址（8765 ⇒ 8766）
function pairUrl(wsUrl) {
  try {
    const u = new URL(wsUrl || 'ws://127.0.0.1:8765/');
    const port = (u.port === '8765') ? '8766' : String(Number(u.port || 8765) + 1);
    return `${u.protocol === 'wss:' ? 'https' : 'http'}://${u.hostname}:${port}`;
  } catch (e) {
    return 'http://127.0.0.1:8766';
  }
}

function setStatus(text, cls) {
  const el = $('status');
  el.textContent = text;
  el.className = cls || '';
}

// ────────────────────────────────────────────────────────────────
// ★★★ EXT-041：**媒体轻微降速**（`video.playbackRate`）
//
// ## 为什么在 **popup** 里做（而不是 player.js）
//   `chrome.scripting.executeScript` 往宿主页注入内容脚本，
//   需要该页面的 **activeTab / host 权限**。
//   ★ **popup 的「开始」按钮是真实用户手势** ⇒ 点击时 Chrome 已把
//     `activeTab` 授予**当前标签页** ⇒ 此时注入**必定成功**。
//   ⇒ 而 player.html 是另一个扩展页，它**没有**该标签页的授权
//     ⇒ 从 player.js 注入会失败（"Cannot access contents of the page"）。
//   ⇒ 所以：**popup 在起流时注入并设置倍率**，player.js 只负责
//     **上报实测结果**与**周期刷新**（服务端建议变了要跟着变）。
//
// ## ★ 诚实说明
//   * 页面里**没有** `<video>`/`<audio>` ⇒ 降速**无效**
//     ⇒ 必须如实回报 `applied=false`，**不假装成功**；
//   * 只降速、**永不加速**（>1.0 会改变语义时轴）；
//   * **不改译文、不改引擎、不改 ASR/MT**。
// ────────────────────────────────────────────────────────────────

/** 媒体降速的**下限 / 上限**（与服务端 `ext/media_slowdown.py` 一致）。 */
const SLOWDOWN_FLOOR = 0.90;
const SLOWDOWN_CEIL = 1.00;
const SLOWDOWN_DEFAULT = 0.92;

/**
 * 向桥接服务要**建议倍率**（按实测 `tts_over_src` 算）。
 * 拿不到就返回 null（**不臆造**）⇒ 调用方用默认 0.92。
 *
 * ★ EXT-043 C1：用 `pairUrl()` 拼地址（**不要**手拼 host/port
 *   ⇒ 原写法会拼出 `http://:8766/status`，node 实测 Invalid URL）。
 */
async function fetchSlowdownRecommendation(wsUrl) {
  try {
    const base = pairUrl(wsUrl);
    const r = await fetch(`${base}/status`, { method: 'GET' });
    if (!r.ok) return null;
    const j = await r.json();
    const sd = (j && j.status && j.status.slowdown) || null;
    if (!sd || typeof sd.recommended_rate !== 'number') return null;
    return sd;
  } catch (e) {
    return null;
  }
}

/**
 * ★ 在目标标签页注入内容脚本并设置 `playbackRate`。
 *
 * @param {number} tabId 目标标签页（就是被翻译的那个媒体页）
 * @param {number} rate  倍率（会被钳到 [0.90, 1.00]）
 * @returns {Promise<object>} `{ok, applied, rate, videos, reason}`
 */
async function applyMediaSlowdown(tabId, rate) {
  let r = Number(rate);
  if (!isFinite(r) || r <= 0) {
    return { ok: false, applied: false, rate: null, videos: null,
             reason: '倍率非法：' + String(rate) };
  }
  // 钳位：**永不加速**
  r = Math.max(SLOWDOWN_FLOOR, Math.min(SLOWDOWN_CEIL, r));
  if (tabId == null) {
    return { ok: false, applied: false, rate: r, videos: null,
             reason: '不知道目标标签页 id ⇒ 没有降速' };
  }
  try {
    // ① 注入内容脚本（幂等：已注入过也不报错）
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['slowdown.js'],
      });
    } catch (e) {
      return { ok: false, applied: false, rate: r, videos: null,
               reason: '注入内容脚本失败：' + String((e && e.message) || e) };
    }
    // ② 下发倍率
    const res = await chrome.tabs.sendMessage(tabId, { cmd: 'set-rate', rate: r });
    return {
      ok: !!(res && res.ok),
      applied: !!(res && res.applied),
      rate: (res && typeof res.rate === 'number') ? res.rate : r,
      videos: (res && typeof res.videos === 'number') ? res.videos : null,
      reason: (res && res.reason) ? String(res.reason) : null,
    };
  } catch (e) {
    return { ok: false, applied: false, rate: r, videos: null,
             reason: '设置 playbackRate 失败：' + String((e && e.message) || e) };
  }
}

/**
 * ★ 起流后调用：按服务端建议（或默认）给目标页降速。
 *
 * ⚠️ **不阻塞**起流主流程（降速只是机制，失败不影响翻译配音）。
 * ⚠️ 结果**如实**写进 storage（player.js 会读它并上报给服务端）。
 */
async function setupMediaSlowdown(tabId, wsUrl) {
  let cfg = {};
  try { cfg = await chrome.storage.local.get({ slowdownOn: true }); } catch (e) { }
  // 11-08 用户：画面速度不调，只调配音语速 ⇒ 媒体降速永久关闭（忽略存量配置）
  const enabled = false;
  if (!enabled) {
    const rec = { enabled: false, applied: false, rate: 1.0, videos: null,
                  reason: '用户关闭了媒体降速开关' };
    try { await chrome.storage.local.set({ slowdown: rec }); } catch (e) { }
    return rec;
  }
  const sd = await fetchSlowdownRecommendation(wsUrl);
  const rate = (sd && typeof sd.recommended_rate === 'number'
                && sd.recommended_rate > 0)
    ? sd.recommended_rate : SLOWDOWN_DEFAULT;
  const res = await applyMediaSlowdown(tabId, rate);
  const rec = {
    enabled: true,
    applied: !!res.applied,
    rate: (res && typeof res.rate === 'number') ? res.rate : null,
    videos: (res && typeof res.videos === 'number') ? res.videos : null,
    reason: res.reason || null,
    recommended: (sd && typeof sd.recommended_rate === 'number')
      ? sd.recommended_rate : null,
    at: Date.now(),
  };
  try { await chrome.storage.local.set({ slowdown: rec }); } catch (e) { }
  return rec;
}

function setBadge(text, cls) {
  const el = $('conn');
  if (!el) return;
  el.textContent = text;
  el.className = 'badge ' + (cls || '');
}

async function saveCfg() {
  // ★★ T-6：与即时持久化**共用同一个读取函数**（`readCfg`）⇒
  //   两条写盘路径的口径**必然一致**（都做归一）⇒
  //   不会出现「即时保存存的是引擎码、点开始时又存成别的」这种分叉。
  const cfg = readCfg();
  await chrome.storage.local.set(cfg);
  return cfg;
}

/**
 * ★★ T-6：**设置持久化** —— 改了就立刻落盘，不等用户点「开始」。
 *
 * ## 为什么需要（这是 P2 待办里明写的一项，之前一直「未开始」）
 *
 * 旧实现里，`saveCfg()` **只在点「开始」时**被调用（popup.js 的 btnStart
 * 处理器）⇒ 用户改了「目标语言 / 延迟 D / 原声压低量 / 字幕开关」之后，
 * **直接关掉弹窗**（这是绝大多数人的习惯）⇒ 这些改动**全部丢失** ⇒
 * 下次打开面板又回到旧值 ⇒ 用户的设置**根本没被记住**。
 *
 * ⇒ 修法：给每个设置控件挂 `change`（提交时）与 `input`（输入中，防抖）
 *   ⇒ 改动**立刻**写进 `chrome.storage.local`。
 *
 * ⚠️ **防抖**：文本框每敲一个字符都写一次 storage 会造成无谓的 IO
 *   ⇒ `input` 走 400 ms 防抖；`change`（失焦/确认）立即写。
 *
 * ⚠️ **与 T-3 的关系**：popup 里的值必须**归一**后再存
 *   （语言全称 ⇒ 引擎码）⇒ 复用 `normalizeLang` / `normalizeVoice`，
 *   与 `loadCfg()` 读回来时的口径**完全一致**（不制造「存进去是全称、
 *   读出来是码」的来回跳变）。
 *
 * ⚠️ **不影响「开始」流程**：`btnStart` 里仍然调用 `saveCfg()`
 *   ⇒ 即时保存是**增量**，不是替换。
 */
const PERSIST_DEBOUNCE_MS = 400;
let _persistTimer = null;

/** 读取当前面板上的设置（已归一）—— 不写盘。 */
function readCfg() {
  return {
    wsUrl: $('ws').value.trim(),
    token: $('token').value.trim(),
    delaySec: Number($('delay').value) || 20,
    targetLang: normalizeLang($('lang').value),
    voice: normalizeVoice($('voice').value),
    duckDb: Number($('duck').value),
    subsOn: $('subs').checked,
    bgKeep: $('bgkeep') ? $('bgkeep').checked : true,   // v0.4.19 保留背景音
    playerOpen: $('player').checked,
    slowdownOn: false,   // v0.4.3：用户去掉「视频轻微降速」⇒ 永远不改视频速度
  };
}

/** 把当前设置**立刻**写进 storage（归一后）。 */
async function persistCfgNow() {
  try {
    const cfg = readCfg();
    await chrome.storage.local.set(cfg);
    return cfg;
  } catch (e) {
    return null;
  }
}

/** 防抖版持久化（文本框输入中用）。 */
function schedulePersistCfg() {
  if (_persistTimer !== null) clearTimeout(_persistTimer);
  _persistTimer = setTimeout(() => {
    _persistTimer = null;
    persistCfgNow();
  }, PERSIST_DEBOUNCE_MS);
}

/**
 * 给所有设置控件挂上「改了立刻落盘」的监听。
 * ★ 幂等：重复调用不会挂重复监听（用标记位）。
 */
function bindPersistListeners() {
  if (bindPersistListeners._bound) return;
  bindPersistListeners._bound = true;
  const ids = ['ws', 'token', 'delay', 'lang', 'voice', 'duck', 'subs', 'bgkeep', 'player'];
  for (const id of ids) {
    const el = $(id);
    if (!el) continue;
    // select / checkbox 的 change 本身就是「提交」
    el.addEventListener('change', () => { persistCfgNow(); });
    // 文本框 / number：输入中走防抖
    if (el.type === 'text' || el.type === 'number') {
      el.addEventListener('input', () => { schedulePersistCfg(); });
    }
  }
}

async function loadCfg() {
  const cfg = await chrome.storage.local.get({
    wsUrl: 'ws://127.0.0.1:8765/',
    token: '',
    delaySec: 20,
    // ★★ T-3：targetLang 的默认值必须是**引擎码** 'zh'
    //   （旧值 'Chinese' 与引擎的 zh/en/ja/ko 不匹配）。
    targetLang: 'zh',
    voice: 'A',
    duckDb: -15,
    subsOn: true,
    bgKeep: true,          // v0.4.19：缺省（含升级）= 开
    playerOpen: false,
    // ★★★ EXT-041：媒体降速**默认开**（reviewer 明文）。
    slowdownOn: false,   // 11-08 用户：不调画面速度
  });
  $('ws').value = cfg.wsUrl;
  $('token').value = cfg.token || '';
  $('delay').value = cfg.delaySec;
  // ★★ T-3：若存量配置里存的是旧的语言全称（Chinese/English/Japanese），
  //   迁移成引擎码，避免下拉框选不中任何一项（value 匹配不到 ⇒ 显示空白）。
  $('lang').value = normalizeLang(cfg.targetLang);
  $('voice').value = normalizeVoice(cfg.voice);
  $('duck').value = cfg.duckDb;
  $('subs').checked = !!cfg.subsOn;
  if ($('bgkeep')) $('bgkeep').checked = (cfg.bgKeep === undefined || cfg.bgKeep === null) ? true : !!cfg.bgKeep;
  $('player').checked = !!cfg.playerOpen;
}

/**
 * ★★ T-3：把「语言全称」归一成**引擎认的码**。
 *
 * 为什么需要：popup 的下拉框旧版存的是 'Chinese'/'English'/'Japanese'，
 * 而桥接服务的 --target-lang 与引擎的 LANG_TO_MT/LANG_TO_TTS
 * **只认 zh/en/ja/ko** ⇒ 直接传过去会抛 EngineNeedsChange。
 * ⇒ 这里做一次兼容归一（老配置自动迁移，新配置本来就是码）。
 */
const LANG_ALIASES = {
  chinese: 'zh', zh: 'zh', '中文': 'zh',
  english: 'en', en: 'en',
  japanese: 'ja', ja: 'ja', '日本語': 'ja',
  korean: 'ko', ko: 'ko', '한국어': 'ko',
  // v0.4.4：新增 6 种
  german: 'de', de: 'de', deutsch: 'de',
  french: 'fr', fr: 'fr', 'français': 'fr',
  spanish: 'es', es: 'es', 'español': 'es',
  portuguese: 'pt', pt: 'pt', 'português': 'pt',
  italian: 'it', it: 'it', italiano: 'it',
  russian: 'ru', ru: 'ru', 'русский': 'ru',
};

function normalizeLang(v) {
  const k = String(v == null ? '' : v).trim().toLowerCase();
  return LANG_ALIASES[k] || 'zh';
}

/**
 * ★★ T-4：音色归一（只有两个合法值）。
 *
 * ★ 为什么 popup 也要归一：服务端只认 `A` / `clone`，
 *   而存储里的值可能来自旧版本或被手工改过 ⇒ 不归一就会把
 *   乱七八糟的值发给服务端（服务端会记进 `client_voice`）。
 *   ★ 必须与 `player.js` 的同名函数**保持一致**。
 */
function normalizeVoice(v) {
  const k = String(v == null ? '' : v).trim().toLowerCase();
  return (k === 'clone') ? 'clone' : 'A';
}

/**
 * ★ EXT-012 ①：自动取 token。
 *
 * 向本机配对端点要 token；端点要求 `Origin: chrome-extension://`，
 * 浏览器扩展发起的 fetch 会**自动**带上正确的 Origin ⇒ 拿得到；
 * 普通网页脚本伪造不了这个头 ⇒ 拿不到（安全口径不变）。
 *
 * 失败时不弹窗打断用户，只在界面上说明「需要手动粘贴」。
 */
async function fetchToken(wsUrl) {
  const base = pairUrl(wsUrl);
  try {
    const r = await fetch(`${base}/pair`, { method: 'GET' });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.error || `HTTP ${r.status}`);
    }
    const j = await r.json();
    if (!j || !j.ok || !j.token) throw new Error(j.error || '未拿到 token');
    await chrome.storage.local.set({ token: j.token });
    return { ok: true, token: j.token };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
}

/**
 * ★ EXT-012 ②：轮询本机状态端点，显示连接状态 / 延迟 / 倍率 / 滞后。
 */
async function pollPairStatus(wsUrl) {
  const base = pairUrl(wsUrl);
  try {
    const r = await fetch(`${base}/status`, { method: 'GET' });
    if (!r.ok) return null;
    const j = await r.json();
    return (j && j.ok) ? (j.status || null) : null;
  } catch (e) {
    return null;
  }
}

function fmtLag(v) {
  if (v == null) return '—';
  const n = Number(v);
  return (n >= 0 ? '' : '-') + Math.abs(n).toFixed(1) + ' s';
}

/**
 * ★★ EXT-024 F：判断「现在能不能开始」。
 *
 * 返回 { ok, reason }：
 *   * `reason` 非空 ⇒ **不能**开始，按钮禁用并把原因写给用户；
 *   * `reason` 为空 ⇒ 可以开始。
 *
 * ★ 诚实性：
 *   * 桥接服务没起来（拿不到 /status）⇒ 不能开始（点下去必然连不上）；
 *   * **回声模式** ⇒ 不能开始（回声不是真实翻译配音，用户会误以为
 *     「翻译没出声音」；宁可拦住并说清楚）；
 *   * 真实引擎但**还没就绪** ⇒ 不能开始（模型还在加载）。
 *   * 真实引擎 + 就绪 ⇒ 可以开始。
 *
 * ⚠️ **只看真实字段**：`mode` 来自服务端的 `hello_ack`/`/status`，
 *   `engine_state` 来自 `/status`。任何一个拿不到 ⇒ 视为**未就绪**
 *   （宁可拦，不可让用户白跑一趟）。
 */
function startGate(st) {
  if (!st) {
    return { ok: false, reason: '连不上桥接服务（没启动？开着 VPN？局域网使用要在桥接窗口勾「允许局域网访问」）' };
  }
  // v0.4.2：局域网模式同一时间只服务一个人
  if (st.active_peer && st.you && st.active_peer !== st.you) {
    return { ok: false, reason: '桥接正在被另一台电脑（' + st.active_peer + '）使用，同一时间只服务一个人，请等对方停止' };
  }
  const mode = st.mode;
  if (mode === 'echo') {
    return { ok: false, reason: '★ 当前是【回声模式】，不是真实翻译配音 —— 请用真实引擎启动桥接' };
  }
  if (mode !== 'real') {
    return { ok: false, reason: '桥接模式未知（' + (mode || '无响应') + '），请重启桥接服务' };
  }
  const state = st.engine_state || 'unknown';
  if (state === 'partial') {
    const failed = Object.keys(st.engine_failed || {});
    return { ok: false, reason: '引擎未就绪：' + (failed.length ? failed.join('/') + ' 加载失败' : '未知') };
  }
  if (state !== 'ready') {
    return { ok: false, reason: '引擎未就绪（正在加载模型…）' };
  }
  return { ok: true, reason: '' };
}

$('btnStart').addEventListener('click', async () => {
  // v0.3.8：桥接在别的机器上 ⇒ 先申请该主机的访问权限（必须在用户点击的同步阶段发起）
  try {
    const _h = new URL($('ws').value.trim().replace(/^ws/, 'http')).hostname;
    if (_h && _h !== '127.0.0.1' && _h !== 'localhost') {
      const ok = await chrome.permissions.request({ origins: ['http://' + _h + '/*'] });
      if (!ok) { setStatus('未授权访问桥接主机 ' + _h, 'err'); return; }
    }
  } catch (e) { /* 地址解析失败 ⇒ 交给后面的连接报错 */ }
  // ★★ EXT-024 F：点之前**再查一次**门禁（轮询有 2 秒间隔 ⇒ 状态可能已变）
  try {
    const gcfg = await chrome.storage.local.get({ wsUrl: 'ws://127.0.0.1:8765/' });
    const gst = await pollPairStatus(gcfg.wsUrl);
    const g = startGate(gst);
    if (!g.ok) {
      setStatus('不能开始：' + g.reason, 'err');
      setBadge('未连接', 'err');
      $('btnStart').disabled = true;
      return;
    }
  } catch (e) { /* 查不到就按原来的流程走（下面还会再报真实错误） */ }

  const cfg = await saveCfg();
  $('btnStart').disabled = true;
  setStatus('正在启动…');

  try {
    // v0.4.0：用户取消 token 配对 ⇒ 不再取 token
    const token = 'nopair';

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) throw new Error('找不到活动标签页');

    // ★★ EXT-027①：把**目标标签页 id** 记进 storage ⇒ player 页的
    //   `chrome.tabCapture.capture({targetTabId})` 能**只抓这个标签页的音频**
    //   （而不是 getDisplayMedia 的整机系统声音）。
    //   ⚠️ 必须在**起流之前**写入 ⇒ player 页随时能读到。
    try {
      await chrome.storage.local.set({ targetTabId: tab.id });
    } catch (e) { /* ignore */ }

    // 11-06 (reviewer): REAL PATH = delayed-picture window.
    //   The player window captures the tab's picture + sound itself (tabCapture,
    //   activeTab granted by this click), shows the picture D s late and plays
    //   the dub in sync.  The old offscreen audio-only path only delayed the dub,
    //   never the picture; it stays reachable via storage captureVia='offscreen'.
    const via = (await chrome.storage.local.get({ captureVia: 'player' })).captureVia;
    let res;
    if (via === 'offscreen') {
      res = await chrome.runtime.sendMessage({
        target: 'sw',
        cmd: 'start',
        tabId: tab.id,
        wsUrl: cfg.wsUrl,
        token: token,
        delaySec: cfg.delaySec,
        targetLang: normalizeLang(cfg.targetLang),
        voice: normalizeVoice(cfg.voice),
      });
    } else {
      // window is opened at the very end: opening it moves focus away and
      // Chrome closes this popup (killing any code after it).
      res = { ok: true, captureMode: 'tabCapture（画面延迟窗口）' };
    }
    if (!res || !res.ok) throw new Error((res && res.error) || '启动失败');

    // ★★★ EXT-041：**媒体轻微降速**（让画面追配音 ⇒ 压平累积斜率）。
    //   ★ **必须在这里做**：popup 的「开始」是**真实用户手势**
    //     ⇒ Chrome 已把 `activeTab` 授予**当前标签页**
    //     ⇒ 此时 `chrome.scripting.executeScript` 注入**必定成功**。
    //   ⚠️ **不阻塞**启动主流程：降速失败只影响「机制①」，
    //     翻译配音照常（**不假装成功**：结果如实写进 storage）。
    // v0.4.3：用户去掉「视频轻微降速」⇒ 不再调用 setupMediaSlowdown，视频速度永远不动

    if (via === 'offscreen' && cfg.playerOpen) {
      await chrome.tabs.create({ url: chrome.runtime.getURL('player.html') });
    }
    if (via !== 'offscreen') {
      await closePlayerWindows();
      await chrome.windows.create({
        url: chrome.runtime.getURL('player.html?auto=1'),
        type: 'popup', state: 'maximized', focused: true,
      });
    }
    $('btnStop').disabled = false;
    // ★★★ EXT-026：启动成功后，「停止并收尾」才可用。
    $('btnFlush').disabled = false;
    setBadge('已连接', 'ok');
    setStatus(
      `已启动\n标签页：${tab.title || tab.id}\n延迟 D=${cfg.delaySec}s\n` +
      `目标语言：${normalizeLang(cfg.targetLang)}\n` +
      `音色：${normalizeVoice(cfg.voice)}\n` +
      `原声压低：${cfg.duckDb} dB\n` +
      `字幕：${cfg.subsOn ? '开' : '关'}\n` +
      `抓流方式：${res.captureMode || '?'}`,
      'ok'
    );
  } catch (e) {
    $('btnStart').disabled = false;
    setBadge('未连接', 'err');
    setStatus(`启动失败：${(e && e.message) || e}`, 'err');
  }
});

// 11-06 (reviewer): close every open player page (delayed-picture window).
async function closePlayerWindows() {
  try {
    const url = chrome.runtime.getURL('player.html');
    const tabs = await chrome.tabs.query({});
    const ids = tabs.filter((t) => t.url && t.url.startsWith(url)).map((t) => t.id);
    if (ids.length) await chrome.tabs.remove(ids);
  } catch (e) { /* ignore */ }
}

$('btnStop').addEventListener('click', async () => {
  // ★★★ EXT-041：**停止时必须恢复 `playbackRate = 1.0`**。
  //   否则用户点完「停止」后，页面**还在慢放** ⇒ 观感事故。
  //   ⚠️ 恢复失败**不阻断**停止流程（停止是用户的主要诉求）。
  try {
    const st = await chrome.storage.local.get({ targetTabId: null });
    const tid = (st && st.targetTabId != null) ? Number(st.targetTabId) : null;
    if (tid != null && isFinite(tid) && tid > 0) {
      await chrome.tabs.sendMessage(tid, { cmd: 'reset-rate' });
    }
    await chrome.storage.local.set({
      slowdown: { enabled: false, applied: false, rate: 1.0, videos: null,
                  reason: '已停止 ⇒ 已恢复 playbackRate = 1.0', at: Date.now() },
    });
  } catch (e) { /* ignore：恢复失败不影响停止 */ }
  try {
    await chrome.runtime.sendMessage({ target: 'sw', cmd: 'stop' });
  } catch (e) { /* ignore */ }
  await closePlayerWindows();   // 11-06: closing the window ends capture + uplink
  $('btnStop').disabled = true;
  $('btnStart').disabled = false;
  setBadge('已停止', 'warn');
  setStatus('已停止');
});

// ★★★ EXT-026 修正：**停止并收尾**（跑完最后一句）。
//
// ## 为什么需要这个按钮（真实缺陷）
//   服务端的流式分段会**故意**把最后一段留在缓冲区等后续音频
//   （`ext/bridge.py` 的 Session.flush 的说明：直播场景这样是对的）
//   ⇒ 要让尾段跑完并下发，客户端**必须**发一条 `{"type":"flush"}`。
//   ★ 之前**整条插件链路从来没有任何地方发过 flush**
//     ⇒ 用户点「停止」时，**最后一句永远不会被翻译、不会被配音**。
//
//   ⚠️ 顺序很重要：**先 flush（让服务端跑完尾段）→ 再 stop（关上游）**。
//   反过来做 ⇒ 尾段还在路上就被掐断。
$('btnFlush').addEventListener('click', async () => {
  $('btnFlush').disabled = true;
  setStatus('正在收尾（跑完最后一句）…');
  let r = { ok: false };
  try {
    r = await chrome.runtime.sendMessage({ target: 'sw', cmd: 'flush' });
  } catch (e) {
    r = { ok: false, error: String((e && e.message) || e) };
  }
  if (r && r.ok) {
    setStatus('已发收尾指令，正在跑完最后一句…\n（几秒后会自动停止）');
    setBadge('收尾中', 'warn');
    // ★ 留一点时间让尾段推理跑完，再自动停止。
    setTimeout(() => { $('btnStop').click(); }, 12000);
  } else {
    setStatus('收尾失败：' + ((r && r.error) || '未知原因'), 'err');
    setBadge('收尾失败', 'err');
    $('btnFlush').disabled = false;
  }
});

// 轮询统计
setInterval(async () => {
  try {
    const r = await chrome.runtime.sendMessage({ target: 'sw', cmd: 'status' });
    if (r && r.ok && r.running) {
      const skew = (r.maxAbsSkewMs || 0).toFixed(1);
      setStatus(
        `运行中\n帧数 ${r.frameCount}\nseq ${r.seq}\n采样 ${r.sampleIndex}\n` +
        `跳变 ${r.gaps}\n最大时钟偏差 ${skew} ms\n编码器 ${r.codecUsed || '—'}`,
        (r.gaps === 0 && r.maxAbsSkewMs < 50) ? 'ok' : 'warn'
      );
    }
  } catch (e) { /* ignore */ }
}, 1000);

// ★ EXT-012 ②：状态端点轮询（连接状态 / 延迟 / 倍率 / 滞后）
// v0.4.6：桥接在别的电脑上、还没授权访问该主机 ⇒ 返回主机名（否则 null）
async function remoteHostNeedingPermission(wsUrl) {
  try {
    const h = new URL(String(wsUrl || '').trim().replace(/^ws/, 'http')).hostname;
    if (!h || h === '127.0.0.1' || h === 'localhost') return null;
    const ok = await chrome.permissions.contains({ origins: ['http://' + h + '/*'] });
    return ok ? null : h;
  } catch (e) {
    return null;
  }
}

async function refreshStatus() {
  const cfg = await chrome.storage.local.get({ wsUrl: 'ws://127.0.0.1:8765/' });
  const needHost = await remoteHostNeedingPermission(cfg.wsUrl);
  if (needHost) {
    setBadge('需要授权', 'warn');
    const me0 = $('mEngine');
    if (me0) me0.textContent = '—';
    setMode('unknown', '点「开始」，在浏览器弹窗里允许访问 ' + needHost);
    const b = $('btnStart');
    const running = b && b.disabled && !$('btnStop').disabled;
    if (b && !running) { b.disabled = false; b.title = ''; }
    const el = $('status');
    if (el && !running) {
      el.textContent = '桥接在 ' + needHost + '：第一次使用请点「开始」，在浏览器弹窗里点「允许」';
      el.className = 'warn';
    }
    return;
  }
  const st = await pollPairStatus(cfg.wsUrl);
  if (!st) {
    setBadge('桥接未启动', 'err');
    $('mLag').textContent = '—';
    $('mSpeed').textContent = '—';
    $('mDelay').textContent = '—';
    // ★★ EXT-017②：桥接没起来 ⇒ 明确告诉用户「引擎未加载」
    const me = $('mEngine');
    if (me) me.textContent = '桥接未启动';
    // ★★ EXT-024 F：模式未知 + 禁用开始
    setMode('unknown', '桥接服务未启动');
    applyStartGate(null);
    return;
  }
  setBadge(st.has_session ? '已连接' : '桥接就绪', st.has_session ? 'ok' : 'warn');
  $('mDelay').textContent = st.delay_sec != null ? (st.delay_sec + ' s') : '—';
  $('mLag').textContent = fmtLag(st.lag_sec);
  const sp = st.speed_time_share || {};
  let best = null, bestV = -1;
  for (const k of Object.keys(sp)) {
    if ((sp[k] || 0) > bestV) { bestV = sp[k] || 0; best = k; }
  }
  $('mSpeed').textContent = best ? best + '×' : '—';

  // ★★ EXT-017②：引擎加载状态
  //   用户点「开始」后要能立刻看到「正在加载模型…」还是「TTS 就绪」。
  const me = $('mEngine');
  if (me) {
    const state = st.engine_state || 'unknown';
    const loaded = st.engine_loaded || [];
    const failed = st.engine_failed || {};
    if (state === 'ready') {
      me.textContent = 'TTS 就绪';
    } else if (state === 'partial') {
      const keys = Object.keys(failed);
      me.textContent = '未就绪：' + (keys.length ? keys.join('/') + ' 加载失败' : '未知');
    } else if (loaded && loaded.length) {
      me.textContent = '加载中…（' + loaded.join('/') + ' 已就绪）';
    } else {
      me.textContent = '正在加载模型…';
    }
  }

  // v0.4.19 保留背景音：分离状态
  const mb = $('mBg');
  if (mb) {
    const on = $('bgkeep') ? $('bgkeep').checked : true;
    const b = st.bg || null;
    if (!on) mb.textContent = '已关闭（原声压低）';
    else if (!b) mb.textContent = st.has_session ? '桥接未报告（旧版本？按原声压低播放）' : '待开始';
    else if (b.state === 'ok') mb.textContent = '正常' + (b.device ? '（' + b.device + '）' : '');
    else if (b.state === 'starting') mb.textContent = '启动中（加载分离模型）…';
    else if (b.state === 'degraded') mb.textContent = '跟不上（部分时段退回原声压低）';
    else if (b.state === 'unavailable') mb.textContent = '不可用：' + (b.reason || '未知原因') + '（按原声压低播放）';
    else mb.textContent = '已关闭（原声压低）';
  }

  // ★★ EXT-024 F：显示连接模式（真实引擎 / 回声）
  const mode = st.mode || 'unknown';
  if (mode === 'echo') {
    setMode('echo', '★ 回声模式：不是真实翻译配音（仅自测用）');
  } else if (mode === 'real') {
    const ready = (st.engine_state === 'ready');
    setMode('real', ready
      ? '真实引擎（ASR→MT→TTS 已就绪）'
      : '真实引擎（模型加载中…）');
  } else {
    setMode('unknown', '模式未知（桥接服务版本过旧？请重启）');
  }

  // ★★ EXT-024 F：按模式/引擎状态决定「开始」能不能点
  applyStartGate(st);
}

/**
 * ★★ EXT-024 F：显示当前连接模式（回声模式**醒目标出**）。
 */
function setMode(mode, hint) {
  const card = $('modeCard');
  const el = $('mMode');
  if (card) card.className = 'mcard ' + (mode || 'unknown');
  if (el) {
    if (mode === 'echo') el.textContent = '★ 回声模式';
    else if (mode === 'real') el.textContent = '真实引擎';
    else el.textContent = '未知';
  }
  const h = $('modeHint');
  if (h) h.textContent = hint || '';
}

/**
 * ★★ EXT-024 F：按 `startGate` 的结论禁用/启用「开始」按钮并写明原因。
 *
 * ⚠️ 已**在运行**时（btnStart 已 disabled、btnStop 可用）不抢按钮，
 *   只更新模式显示 ⇒ 不打断正在跑的会话。
 */
function applyStartGate(st) {
  const btn = $('btnStart');
  const g = startGate(st);
  if (!btn) return;
  const running = btn.disabled && !$('btnStop').disabled;
  if (running) return;
  btn.disabled = !g.ok;
  btn.title = g.reason || '';
  if (!g.ok) {
    // 把原因写进状态区（用户能直接看到，不用 hover）
    const el = $('status');
    if (el && (!el.textContent || el.textContent.indexOf('不能开始') < 0)) {
      el.textContent = '不能开始：' + g.reason;
      el.className = 'err';
    }
  }
}

// ★ EXT-012 ③：打开说明
$('btnGuide').addEventListener('click', async () => {
  const url = chrome.runtime.getURL('guide.html');  // v0.4.1：UTF-8 渲染，修乱码
  await chrome.tabs.create({ url });
});

loadCfg();
// ★★ T-6：设置**改了立刻落盘**（不等用户点「开始」）
//   ⇒ 绑定必须在 loadCfg() **之后**（否则会被 loadCfg 填 DOM 的动作触发一次误存）。
bindPersistListeners();
refreshStatus();
setInterval(refreshStatus, 2000);
