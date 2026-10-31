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

function setBadge(text, cls) {
  const el = $('conn');
  if (!el) return;
  el.textContent = text;
  el.className = 'badge ' + (cls || '');
}

async function saveCfg() {
  const cfg = {
    wsUrl: $('ws').value.trim(),
    token: $('token').value.trim(),
    delaySec: Number($('delay').value) || 10,
    targetLang: $('lang').value,
    voice: $('voice').value,
    duckDb: Number($('duck').value),
    subsOn: $('subs').checked,
    playerOpen: $('player').checked,
  };
  await chrome.storage.local.set(cfg);
  return cfg;
}

async function loadCfg() {
  const cfg = await chrome.storage.local.get({
    wsUrl: 'ws://127.0.0.1:8765/',
    token: '',
    delaySec: 10,
    // ★★ T-3：targetLang 的默认值必须是**引擎码** 'zh'
    //   （旧值 'Chinese' 与引擎的 zh/en/ja/ko 不匹配）。
    targetLang: 'zh',
    voice: 'A',
    duckDb: -15,
    subsOn: true,
    playerOpen: false,
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
    return { ok: false, reason: '桥接服务未启动（先点桌面「实时配音桥接.cmd」）' };
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
    // ★ 自动配对：没 token 就去本机取
    let token = cfg.token;
    if (!token) {
      setStatus('正在自动配对…');
      const r = await fetchToken(cfg.wsUrl);
      if (!r.ok) {
        throw new Error(
          `自动配对失败（${r.error}）。请先启动「实时配音桥接」，` +
          '或手动把 bridge_token.txt 的内容粘贴到上面的 token 框。');
      }
      token = r.token;
    }

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) throw new Error('找不到活动标签页');

    const res = await chrome.runtime.sendMessage({
      target: 'sw',
      cmd: 'start',
      tabId: tab.id,
      wsUrl: cfg.wsUrl,
      token: token,
      delaySec: cfg.delaySec,
      // ★★ T-3：把「目标语言」与「音色」也带上去。
      //   旧写法这两个字段只存进了 storage，**从没进过 start 消息**
      //   ⇒ 用户在面板上选语言/音色完全不起作用。
      targetLang: normalizeLang(cfg.targetLang),
      voice: normalizeVoice(cfg.voice),
    });
    if (!res || !res.ok) throw new Error((res && res.error) || '启动失败');

    if (cfg.playerOpen) {
      await chrome.tabs.create({ url: chrome.runtime.getURL('player.html') });
    }
    $('btnStop').disabled = false;
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

$('btnStop').addEventListener('click', async () => {
  try {
    await chrome.runtime.sendMessage({ target: 'sw', cmd: 'stop' });
  } catch (e) { /* ignore */ }
  $('btnStop').disabled = true;
  $('btnStart').disabled = false;
  setBadge('已停止', 'warn');
  setStatus('已停止');
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
async function refreshStatus() {
  const cfg = await chrome.storage.local.get({ wsUrl: 'ws://127.0.0.1:8765/' });
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
  const url = chrome.runtime.getURL('USER_GUIDE.md');
  await chrome.tabs.create({ url });
});

loadCfg();
refreshStatus();
setInterval(refreshStatus, 2000);
