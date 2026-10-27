/**
 * popup.js — 扩展弹窗
 *
 * EXT-001 A 节：popup 提供 开始/停止、目标语言、延迟 D、音色、原声压低量、
 * 字幕开关、桥接连接状态。
 *
 * ★ 关键：用户点「开始」= **真实用户手势** ⇒ 这是 chrome.tabCapture
 *   拿到 stream id 的**唯一**方式（自动化下会报
 *   "Extension has not been invoked for the current page"，见 STATUS §2）。
 */

const $ = (id) => document.getElementById(id);

function setStatus(text, cls) {
  const el = $('status');
  el.textContent = text;
  el.className = cls || '';
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

$('btnStart').addEventListener('click', async () => {
  const cfg = await saveCfg();
  $('btnStart').disabled = true;
  setStatus('正在启动…');

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) throw new Error('找不到活动标签页');

    const res = await chrome.runtime.sendMessage({
      target: 'sw',
      cmd: 'start',
      tabId: tab.id,
      wsUrl: cfg.wsUrl,
      token: cfg.token,
      delaySec: cfg.delaySec,
    });
    if (!res || !res.ok) throw new Error((res && res.error) || '启动失败');

    if (cfg.playerOpen) {
      await chrome.tabs.create({ url: chrome.runtime.getURL('player.html') });
    }
    $('btnStop').disabled = false;
    setStatus(
      `已启动\n标签页：${tab.title || tab.id}\n延迟 D=${cfg.delaySec}s\n` +
      `抓流方式：${res.captureMode || '?'}`,
      'ok'
    );
  } catch (e) {
    $('btnStart').disabled = false;
    setStatus(`启动失败：${(e && e.message) || e}`, 'err');
  }
});

$('btnStop').addEventListener('click', async () => {
  try {
    await chrome.runtime.sendMessage({ target: 'sw', cmd: 'stop' });
  } catch (e) { /* ignore */ }
  $('btnStop').disabled = true;
  $('btnStart').disabled = false;
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

loadCfg();
