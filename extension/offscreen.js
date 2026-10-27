/**
 * offscreen.js — offscreen document：抓流 → 重采样 16 kHz → WebSocket 上行
 *
 * EXT-003 P0① 验收："连续 5 分钟 seq 不断、采样计数和墙钟偏差 < 50 ms"
 *
 * ★ 本机实测到的三条约束（决定了本文件的实现，见 STATUS §2）：
 *   1. `chrome.tabCapture.getMediaStreamId()` 在**自动化**环境里拿不到流 id，
 *      报 "Extension has not been invoked for the current page"；
 *      **真实用户点击扩展图标**时才可用（这正是 popup 的「开始」按钮）。
 *   2. 自动化下可用的等价路径是 `getDisplayMedia({video, audio:true})`
 *      + `--auto-select-tab-capture-source-by-title=<标题>`；
 *      实测能拿到 **1908x1072@30fps + 48 kHz 单声道**的整页音视频，且**有真实音频**。
 *   3. 本机 WebCodecs **不支持 H.264**（avc1.* 全部 false），
 *      支持 VP8 / VP9 / AV1 ⇒ 编码器按此顺序回退。
 *
 * 因此本文件支持**两种抓流来源**（运行时自动判定）：
 *   A. tabCapture（真实用户点击路径，生产用）
 *   B. getDisplayMedia（自动化/兜底路径，测试与无手势场景用）
 */

const TARGET_RATE = 16000;
const FRAME_MIN_MS = 20;
const FRAME_MAX_MS = 100;

const state = {
  ws: null,
  ac: null,
  stream: null,
  node: null,
  source: null,
  running: false,
  seq: 0,
  sampleIndex: 0,
  t0: 0,
  frameCount: 0,
  bytesSent: 0,
  lastFrameAt: 0,
  maxAbsSkewMs: 0,
  skewSamples: [],
  gaps: 0,
  gapDetail: [],
  wsOpen: false,
  error: null,
  captureMode: null,       // 'tabCapture' | 'getDisplayMedia'
  sourceRate: 0,
  acRate: 0,
  echoCount: 0,
  echoBytes: 0,
  echoFirst: null,
};

function post(msg) {
  // ★ 不用 chrome.runtime.sendMessage（会与 SW 的 listener 抢通道）：
  //   统一写进 chrome.storage.local.extLog，popup/探针可读取。
  try {
    chrome.storage.local.get({ extLog: [] }).then((s) => {
      const arr = (s.extLog || []).concat([{ ts: Date.now(), ...msg }]).slice(-200);
      return chrome.storage.local.set({ extLog: arr });
    }).catch(() => {});
  } catch (e) { /* ignore */ }
}
function log(s) { post({ type: 'log', msg: s }); }

// ── WebSocket 上行 ───────────────────────────────────────────────
function connectWs(wsUrl, token) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    state.ws = ws;
    const timer = setTimeout(() => {
      try { ws.close(); } catch (e) {}
      reject(new Error('WebSocket 连接超时'));
    }, 8000);

    ws.onopen = () => {
      clearTimeout(timer);
      state.wsOpen = true;
      ws.send(JSON.stringify({
        type: 'hello', token, sample_rate: TARGET_RATE, source: 'offscreen',
        role: 'uplink',
      }));
      resolve(ws);
    };
    ws.onerror = () => { clearTimeout(timer); reject(new Error('WebSocket 连接失败')); };
    ws.onclose = () => { state.wsOpen = false; };
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'echo' || m.type === 'tts') {
          state.echoCount++;
          state.echoBytes += (m.pcm24k || '').length;
          if (!state.echoFirst) state.echoFirst = { id: m.id, t_start: m.t_start, t_end: m.t_end };
        }
      } catch (e) { /* ignore */ }
    };
  });
}

// ── 抓流：两条路径 ───────────────────────────────────────────────
async function grabTabCapture(streamId) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: { chromeMediaSource: 'tab', chromeMediaSourceId: streamId },
    },
    video: false,
  });
  state.captureMode = 'tabCapture';
  return stream;
}

async function grabDisplayMedia(opts) {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: opts.frameRate || 30 },
    audio: true,
  });
  state.captureMode = 'getDisplayMedia';
  return stream;
}

/**
 * 启动抓流 + 重采样 + 上行。
 * @param {object} p
 * @param {string} [p.streamId]  tabCapture 流 id（真实用户点击路径）
 * @param {object} [p.display]   getDisplayMedia 参数（自动化路径）
 */
async function startCapture(p) {
  let stream;
  if (p.streamId) {
    stream = await grabTabCapture(p.streamId);
  } else if (p.display) {
    stream = await grabDisplayMedia(p.display);
  } else {
    throw new Error('没有可用的抓流方式');
  }
  state.stream = stream;

  const track = stream.getAudioTracks()[0];
  const st = track.getSettings ? track.getSettings() : {};
  state.sourceRate = st.sampleRate || 48000;

  // ★ 与播放共用 48 kHz 时钟（EXT-001：画面和原声都用同一个 AudioContext 时钟）
  const ac = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
  state.ac = ac;
  state.acRate = ac.sampleRate;
  // ★ offscreen document 没有用户手势 ⇒ AudioContext 初始是 **suspended**。
  //   不 resume 的话 AudioWorklet 的 process() 永远不会被调用
  //   （实测：workletProcessCalls=0，一帧都不产出）。
  //   某些 Chrome 版本里 resume() 在无手势上下文会失败，
  //   ⇒ 用「反复 resume + 检查 state」的方式确保真正 running。
  for (let i = 0; i < 10; i++) {
    try { await ac.resume(); } catch (e) { /* ignore */ }
    if (ac.state === 'running') break;
    await new Promise((r) => setTimeout(r, 100));
  }
  state.acState = ac.state;
  if (ac.state !== 'running') {
    log(`AudioContext 未 running（state=${ac.state}），继续尝试`);
  }
  await ac.audioWorklet.addModule(chrome.runtime.getURL('capture-worklet.js'));

  const node = new AudioWorkletNode(ac, 'capture-processor', {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [1],
    processorOptions: {
      targetRate: TARGET_RATE,
      inputRate: state.sourceRate,
      frameMinMs: FRAME_MIN_MS,
      frameMaxMs: FRAME_MAX_MS,
    },
  });
  state.node = node;

  const source = ac.createMediaStreamSource(stream);
  state.source = source;
  source.connect(node);

  // 接到静音增益再接 destination —— 否则某些浏览器会暂停处理图
  const mute = ac.createGain();
  mute.gain.value = 0;
  node.connect(mute);
  mute.connect(ac.destination);

  node.port.onmessage = (ev) => onWorkletFrame(ev.data);
  state.t0 = performance.now();
  state.running = true;
  log(`抓流成功：mode=${state.captureMode} 源 ${state.sourceRate} Hz → 目标 ${TARGET_RATE} Hz，ac=${state.acState}`);
}

function onWorkletFrame(d) {
  const pcm = d.pcm;
  const nSamples = pcm.byteLength / 2;
  const seq = d.seq;
  const sampleIndex = d.sampleIndex;
  state.workletInSamples = d.inSamples || 0;
  state.workletProcessCalls = d.processCalls || 0;

  // ── 连续性检查（EXT-003：连续 5 分钟 seq 不断） ──
  if (state.seq > 0) {
    if (seq !== state.seq) {
      state.gaps += (seq - state.seq);
      state.gapDetail.push({ kind: 'seq', expect: state.seq, got: seq });
    }
    if (sampleIndex !== state.sampleIndex) {
      state.gaps += 1;
      state.gapDetail.push({
        kind: 'sample', expect: state.sampleIndex, got: sampleIndex,
        delta: sampleIndex - state.sampleIndex,
      });
    }
  }

  // ── 采样计数 vs 墙钟 偏差（EXT-003：< 50 ms） ──
  const audioSec = sampleIndex / TARGET_RATE;
  const wallSec = (performance.now() - state.t0) / 1000;
  const skewMs = (audioSec - wallSec) * 1000;
  if (Math.abs(skewMs) > state.maxAbsSkewMs) state.maxAbsSkewMs = Math.abs(skewMs);
  if (state.skewSamples.length < 60000) state.skewSamples.push(skewMs);

  state.seq = seq + 1;
  state.sampleIndex = sampleIndex + nSamples;
  state.frameCount += 1;
  state.lastFrameAt = performance.now();

  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    const bytes = new Uint8Array(pcm);
    let bin = '';
    const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    }
    state.ws.send(JSON.stringify({
      type: 'pcm', seq, sample_index: sampleIndex, pcm: btoa(bin),
    }));
    state.bytesSent += bytes.length;
  }
}

async function stopCapture() {
  state.running = false;
  try { if (state.node) state.node.port.onmessage = null; } catch (e) {}
  try { if (state.source) state.source.disconnect(); } catch (e) {}
  try { if (state.node) state.node.disconnect(); } catch (e) {}
  try { if (state.stream) state.stream.getTracks().forEach(t => t.stop()); } catch (e) {}
  try { if (state.ac && state.ac.state !== 'closed') await state.ac.close(); } catch (e) {}
  try { if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.close(); } catch (e) {}
  state.ws = null; state.ac = null; state.stream = null;
  state.node = null; state.source = null;
}

// ── 消息路由（Port 通道） ───────────────────────────────────────
// ★ 关键架构决定（实测踩坑）：
//   MV3 service worker 里 `chrome.runtime.connect()` **必须在 event 回调的
//   同步栈里调用**；一旦跨过 await 再 connect，port 立刻失效，
//   报 "Could not establish connection. Receiving end does not exist."。
//   ⇒ 反过来做：**offscreen 文档在脚本加载时立即 connect 到 SW**，
//     SW 持有该 port 引用并通过它下发命令。
//   Port 是点对点的 ⇒ 语义确定，不存在 sendMessage 的广播/异步响应归属问题。
const SW_PORT = 'ext-offscreen';
let swPort = null;

function connectToSw() {
  try {
    swPort = chrome.runtime.connect({ name: SW_PORT });
    swPort.onMessage.addListener(async (msg) => {
      const r = await handleOffscreen(msg);
      try { swPort.postMessage({ result: r, reqId: msg && msg.reqId }); } catch (e) { /* ignore */ }
    });
    swPort.onDisconnect.addListener(() => { swPort = null; });
    log('已连接到 service worker 控制通道');
  } catch (e) {
    log('连接 service worker 控制通道失败：' + String(e));
  }
}
connectToSw();

// 测试钩子：把内部状态暴露出去，便于自测与诊断
window.__extOff = {
  startCapture,
  stopCapture,
  snapshot,
  state,
  connectWs,
};

async function handleOffscreen(msg) {
  try {
    switch (msg.cmd) {
      case 'ping': {
        return { ok: true, pong: true };
      }
      case 'start': {
        if (state.running) return { ok: true, already: true };
        await connectWs(msg.wsUrl, msg.token);
        await startCapture(msg);
        return {
          ok: true, started: true, captureMode: state.captureMode,
          acRate: state.acRate, sourceRate: state.sourceRate,
        };
      }
      case 'stop': {
        await stopCapture();
        return { ok: true, stopped: true };
      }
      case 'stats': {
        return { ok: true, stats: snapshot() };
      }
      default:
        return { ok: false, error: `unknown cmd ${msg.cmd}` };
    }
  } catch (e) {
    state.error = String((e && e.message) || e);
    return { ok: false, error: state.error };
  }
}

function snapshot() {
  const sk = state.skewSamples;
  const abs = sk.map(Math.abs).sort((a, b) => a - b);
  const pct = (p) => (abs.length ? abs[Math.min(abs.length - 1, Math.floor(abs.length * p))] : null);
  return {
    running: state.running,
    captureMode: state.captureMode,
    sourceRate: state.sourceRate,
    acRate: state.acRate,
    acState: state.acState,
    seq: state.seq,
    sampleIndex: state.sampleIndex,
    frameCount: state.frameCount,
    bytesSent: state.bytesSent,
    gaps: state.gaps,
    gapDetail: state.gapDetail.slice(-20),
    maxAbsSkewMs: state.maxAbsSkewMs,
    skewP50: pct(0.50), skewP95: pct(0.95), skewP99: pct(0.99),
    skewSamples: sk.slice(-5000),
    wsOpen: state.wsOpen,
    workletInSamples: state.workletInSamples || 0,
    workletProcessCalls: state.workletProcessCalls || 0,
    lastFrameAt: state.lastFrameAt,
    elapsedMs: state.t0 ? performance.now() - state.t0 : 0,
    echoCount: state.echoCount,
    echoBytes: state.echoBytes,
    echoFirst: state.echoFirst,
    error: state.error,
  };
}
