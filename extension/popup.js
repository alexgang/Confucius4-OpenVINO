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
    targetLang: 'Chinese',
    voice: 'A',
    duckDb: -15,
    subsOn: true,
    playerOpen: false,
  });
  $('ws').value = cfg.wsUrl;
  $('token').value = cfg.token || '';
  $('delay').value = cfg.delaySec;
  $('lang').value = cfg.targetLang;
  $('voice').value = cfg.voice;
  $('duck').value = cfg.duckDb;
  $('subs').checked = !!cfg.subsOn;
  $('player').checked = !!cfg.playerOpen;
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

$('btnStart').addEventListener('click', async () => {
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
    });
    if (!res || !res.ok) throw new Error((res && res.error) || '启动失败');

    if (cfg.playerOpen) {
      await chrome.tabs.create({ url: chrome.runtime.getURL('player.html') });
    }
    $('btnStop').disabled = false;
    setBadge('已连接', 'ok');
    setStatus(
      `已启动\n标签页：${tab.title || tab.id}\n延迟 D=${cfg.delaySec}s\n` +
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
}

// ★ EXT-012 ③：打开说明
$('btnGuide').addEventListener('click', async () => {
  const url = chrome.runtime.getURL('USER_GUIDE.md');
  await chrome.tabs.create({ url });
});

loadCfg();
refreshStatus();
setInterval(refreshStatus, 2000);
