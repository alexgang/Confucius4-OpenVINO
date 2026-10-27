/**
 * player.js — 延迟画面播放器 + 配音排程（P0② / P0③）
 *
 * P0②（EXT-003）：WebCodecs 延迟画面
 *   视频轨：MediaStreamTrackProcessor → VideoEncoder → 已编码块的**环形缓冲**（带时间戳）
 *          → 延迟 D 后 VideoDecoder → canvas
 *   原声：  同一个 AudioContext + DelayNode(D) + 压低增益（ducking）
 *   ★ 画面和原声都用**同一个 AudioContext 时钟**（EXT-001 A 节）
 *
 * P0③（EXT-003）：浏览器端回声排程误差
 *   浏览器发音频 → 桥接服务原样回传 → 本页在 t0 + t_start + D 播放
 *   → 用 **onset worklet**（逐样本）测「实际出声时刻 − 计划时刻」（目标 ≤ 20 ms）
 *
 * ★ 本机实测约束（见 STATUS §2）：
 *   本机 WebCodecs **不支持 H.264**（avc1.* 全部 isConfigSupported=false），
 *   支持 VP8 / VP9 / AV1 ⇒ 编码器按 VP9 → VP8 → AV1 顺序回退。
 *
 * 测试参数（URL query）：
 *   ?capture=1  —— 页面加载后**自动**点「开始捕获」按钮（等价真实用户手势）
 *   ?d=<秒>    —— 覆盖延迟 D（默认 10）
 */

const qs = new URLSearchParams(location.search);
const D_OVERRIDE = parseFloat(qs.get('d') || '');
const AUTO_CAPTURE = qs.get('capture') === '1';

const cv = document.getElementById('cv');
// ★ willReadFrequently：白闪检测每帧都要 getImageData ⇒ 声明可读频繁
//   （否则浏览器每次都做 GPU→CPU 回读，掉帧并刷警告）
const ctx2d = cv.getContext('2d', { willReadFrequently: true });

const metrics = {
  queued: 0, encoded: 0, decoded: 0, dropped: 0, drawn: 0,
  lipSyncMs: null, schedErrMs: null, schedErrP50: null, schedErrP95: null,
  codecUsed: null, hwAcceleration: null,
  frames: 0, lastFrameAt: 0,
  videoWidth: 0, videoHeight: 0, sourceRate: 0,
  echoRecv: 0, echoSent: 0,
  onsetErrs: [], lipErrs: [],
  drawMarks: [], origOnsets: [], dubOnsets: [],
  captureStarted: false, audioCtxOk: false,
};

// ── 全局时钟：画面与原声共用同一个 AudioContext ────────────────
let audioCtx = null;
let t0 = 0;
let delaySec = 10;
let ws = null;
let lipSyncData = null;
let capturedStream = null;

// ══════════════════════════════════════════════════════════════
// P0②：WebCodecs 延迟画面管线
// ══════════════════════════════════════════════════════════════
const encQueue = [];      // 已编码块环形缓冲 {chunk, tsUs}
const ENC_CAP = 300;      // ≈10 s @30fps
let videoEncoder = null;
let videoDecoder = null;
let decoderCfg = null;
let lastEncTs = -1;
const pendingDecode = [];

/**
 * 本机可用编码器候选顺序。
 *
 * ★ 实测结论（本机 Edge 156 + RTX 5050，见 STATUS §2）：
 *   - `avc1.*`（H.264）：isConfigSupported 全 false ⇒ 不可用
 *   - `vp09.00.10.08`（VP9）：supported=true，但 **实际编码必失败**
 *     （EncodingError: Flushing error.）⇒ 不能排在前面
 *   - `av01.0.04M.08`（AV1）：supported=true，实际编码失败（Flushing error.）
 *   - `vp8` + `no-preference`：**唯一实测编码成功**的组合
 *     （prefer-hardware 下 isConfigSupported=false）
 *   ⇒ 候选顺序必须是 VP8(no-preference) 打头，失败再回退。
 */
const CODEC_CANDIDATES = [
  { codec: 'vp8', hw: 'no-preference', label: 'VP8' },
  { codec: 'vp8', hw: 'prefer-hardware', label: 'VP8(hw)' },
  { codec: 'vp09.00.10.08', hw: 'no-preference', label: 'VP9' },
  { codec: 'av01.0.04M.08', hw: 'no-preference', label: 'AV1' },
  { codec: 'avc1.42E01E', hw: 'no-preference', label: 'H.264 baseline' },
];

async function initVideoCodecs(width, height) {
  for (const c of CODEC_CANDIDATES) {
    const cfg = {
      codec: c.codec, width, height,
      bitrate: 4_000_000, framerate: 30,
      hardwareAcceleration: c.hw,
    };
    try {
      const sup = await VideoEncoder.isConfigSupported(cfg);
      if (!sup.supported) continue;
      videoEncoder = new VideoEncoder({
        output: (chunk, meta) => {
          metrics.encoded++;
          // ★ decoderConfig 只在首个关键帧的 meta 里给 ⇒ 必须在这里接住，
          //   否则 VideoDecoder 永远 configure 不了（decoded 恒为 0）。
          if (meta && meta.decoderConfig) {
            decoderCfg = meta.decoderConfig;
            try { ensureDecoder(decoderCfg); } catch (e) { /* ignore */ }
          }
          encQueue.push({ chunk, tsUs: chunk.timestamp });
          if (encQueue.length > ENC_CAP) {
            const dropped = encQueue.splice(0, encQueue.length - ENC_CAP);
            metrics.dropped += dropped.length;
          }
        },
        error: (e) => { metrics.encoderError = String(e); },
      });
      videoEncoder.configure(cfg);
      metrics.codecUsed = c.codec;
      metrics.hwAcceleration = c.hw;
      metrics.encWidth = width;
      metrics.encHeight = height;
      return c.codec;
    } catch (e) { /* try next */ }
  }
  throw new Error('无可用视频编码器');
}

async function ensureDecoder(cfg) {
  if (cfg) decoderCfg = cfg;
  if (!decoderCfg) return;
  if (videoDecoder && videoDecoder.state === 'configured') return;
  videoDecoder = new VideoDecoder({
    output: (frame) => onDecodedFrame(frame),
    error: (e) => { metrics.decoderError = String(e); },
  });
  videoDecoder.configure(decoderCfg);
}

function onDecodedFrame(frame) {
  metrics.decoded++;
  const target = (t0 + frame.timestamp / 1e6) + delaySec;
  const now = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
  const waitMs = (target - now) * 1000;
  if (waitMs > 0) {
    const id = setTimeout(() => { drawFrame(frame); }, waitMs);
    pendingDecode.push(id);
    if (pendingDecode.length > 3000) clearTimeout(pendingDecode.shift());
  } else {
    drawFrame(frame);
  }
}

function drawFrame(frame) {
  try {
    if (frame.displayWidth) { cv.width = frame.displayWidth; cv.height = frame.displayHeight; }
    ctx2d.drawImage(frame, 0, 0, cv.width, cv.height);
    metrics.frames++;
    metrics.drawn++;
    metrics.lastFrameAt = performance.now();
    // ★ 白闪检测（唇音同步测试片）：画面接近纯白 ⇒ 记下绘制时刻
    //   采样**中心区域**（源页白闪是整屏纯白，中心最可靠），
    //   取多个采样点求平均，避免缩放/编码噪声误判。
    try {
      const w = cv.width, h = cv.height;
      const pts = [[0.5, 0.5], [0.3, 0.3], [0.7, 0.7], [0.5, 0.2], [0.2, 0.5]];
      let sum = 0, n = 0;
      for (const [fx, fy] of pts) {
        const x = Math.max(0, Math.min(w - 2, Math.floor(w * fx)));
        const y = Math.max(0, Math.min(h - 2, Math.floor(h * fy)));
        const d = ctx2d.getImageData(x, y, 2, 2).data;
        for (let i = 0; i < d.length; i += 4) {
          sum += d[i] + d[i + 1] + d[i + 2]; n += 3;
        }
      }
      const avg = n ? sum / n : 0;
      if (avg > 235) {
        const at = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
        metrics.drawMarks.push(at);
        if (metrics.drawMarks.length > 200) metrics.drawMarks.shift();
      }
    } catch (e) { /* ignore */ }
    frame.close();
  } catch (e) { /* ignore */ }
}

function pumpDecoder() {
  // decoder 还没配置（首个关键帧还没到）⇒ 等
  if (!videoDecoder || videoDecoder.state !== 'configured') {
    if (decoderCfg && videoEncoder && videoEncoder.state === 'configured') {
      try { ensureDecoder(decoderCfg); } catch (e) { /* ignore */ }
    }
    return;
  }
  const now = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
  while (encQueue.length) {
    const head = encQueue[0];
    const target = (t0 + head.tsUs / 1e6) + delaySec;
    if (now < target) break;
    encQueue.shift();
    try { videoDecoder.decode(head.chunk); } catch (e) { /* ignore */ }
  }
}

// ══════════════════════════════════════════════════════════════
// 音频总线 + onset 精确测量
// ══════════════════════════════════════════════════════════════
let dubBus = null;        // 配音输出总线
let origGain = null;      // 延迟后的原声总线
let origDelay = null;
let origSource = null;
let onsetNode = null;     // 配音 onset 检测
let origOnsetNode = null; // 原声 onset 检测（唇音同步用）

/**
 * 建 onset 检测 worklet。
 * @param {AudioNode} src  要监听的源节点
 * @param {Function} cb    回调 (at) => void
 */
async function makeOnsetDetector(src, cb, threshold, count) {
  await audioCtx.audioWorklet.addModule(chrome.runtime.getURL('onset-worklet.js'));
  const node = new AudioWorkletNode(audioCtx, 'onset-processor', {
    numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
    processorOptions: {
      threshold: threshold || 0.02,
      // ★ count=0 ⇒ **连续检测**（唇音同步测试片要捕多个 onset）
      count: count === undefined ? 0 : count,
      minGapSec: 0.05,
    },
  });
  node.port.onmessage = (e) => { if (e.data && e.data.onset) cb(e.data.at); };
  src.connect(node);
  // 分析节点不接 destination（避免二次出声）
  return node;
}

// ★ pendingSched 必须是**有界**的。
//   真实缺陷（实测：5 分钟长测 maxAbsSkew 595 ms）：bridge 回声模式下
//   **每帧**都回灌一个 echo（16 kHz / 20~100 ms 一帧 ⇒ 约 47 帧/秒），
//   而 onDubOnset 只在**检出 onset**时才 shift 一个。
//   源是稀疏 beep 时 onset 很少 ⇒ pendingSched 累积到万级，
//   连带 subs.sort() 变成 O(n² log n) ⇒ 主线程卡顿 ⇒ 采样时钟出现尖峰。
//   ⇒ 这里加**上限**：超出即丢弃最旧的（同时计数，不静默丢）。
const PENDING_SCHED_CAP = 512;
const pendingSched = [];

function onDubOnset(at) {
  if (pendingSched.length) {
    const p = pendingSched.shift();
    const errMs = (at - p.planned) * 1000;
    metrics.onsetErrs.push(errMs);
    if (metrics.onsetErrs.length > 500) metrics.onsetErrs.shift();
    metrics.schedErrMs = errMs;
    metrics.schedErrP50 = pct(metrics.onsetErrs, 0.5);
    metrics.schedErrP95 = pct(metrics.onsetErrs, 0.95);
    report({ kind: 'sched', id: p.id, planned: p.planned, actual: at, errMs });
  } else {
    metrics.dubOnsets.push(at);
    if (metrics.dubOnsets.length > 200) metrics.dubOnsets.shift();
  }
}

function onOrigOnset(at) {
  metrics.origOnsets.push(at);
  if (metrics.origOnsets.length > 500) metrics.origOnsets.shift();
}

// ★ pct 用**缓存的有序副本**，只在数组内容变化时重排。
//   真实缺陷：computeLipSync 每秒调 3 次 pct、onDubOnset 每次也调 2 次，
//   而每次 pct 都 [...arr].sort() 复制+排序最多 500 项 ⇒ 持续的主线程负担。
//   ⇒ 缓存 key 用「数组长度 + 首尾元素」判定是否需要重排（足够且零成本）。
const _pctCache = new WeakMap();
function pct(arr, p) {
  if (!arr.length) return null;
  let c = _pctCache.get(arr);
  const first = arr[0], last = arr[arr.length - 1];
  if (!c || c.len !== arr.length || c.first !== first || c.last !== last) {
    const s = [...arr].sort((a, b) => a - b);
    c = { len: arr.length, first, last, sorted: s };
    _pctCache.set(arr, c);
  }
  const s = c.sorted;
  return s[Math.min(s.length - 1, Math.floor(s.length * p))];
}

// ══════════════════════════════════════════════════════════════
// 配音排程（P0③）
// ══════════════════════════════════════════════════════════════
function b64ToAudioBuffer(b64, sampleRate) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const i16 = new Int16Array(bytes.buffer);
  const buf = audioCtx.createBuffer(1, i16.length, sampleRate || 24000);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < i16.length; i++) ch[i] = i16[i] / 32768;
  return buf;
}

/** 排程一句配音到 t0 + t_start + D（AudioContext 绝对时刻） */
function scheduleDub(msg) {
  if (!audioCtx || !msg.pcm24k) return null;
  const buf = b64ToAudioBuffer(msg.pcm24k, msg.sample_rate || 16000);
  const planned = t0 + Number(msg.t_start || 0) + delaySec;
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(dubBus);
  const when = Math.max(audioCtx.currentTime + 0.005, planned);
  src.start(when);
  // ★ 有界：超出上限丢弃最旧的，并计数（不静默丢）
  //   先裁剪再 push ⇒ 长度始终 ≤ CAP
  if (pendingSched.length >= PENDING_SCHED_CAP) {
    const dropped = pendingSched.length - (PENDING_SCHED_CAP - 1);
    pendingSched.splice(0, dropped);
    metrics.pendingSchedDropped = (metrics.pendingSchedDropped || 0) + dropped;
  }
  pendingSched.push({ id: msg.id, planned: when, requested: planned });
  scheduleSub(msg, when);
  return { planned: when, requested: planned };
}

// ★ subs 用**有序插入**而不是每次 push 都 sort()。
//   真实缺陷：回声模式下每帧一条 ⇒ 每次 push 都整表重排 ⇒ O(n² log n)。
//   ⇒ 改为「尾部追加 + 尾部乱序时插入排序」（绝大多数情况单调递增 ⇒ O(1)）。
const SUBS_CAP = 200;
const subs = [];
function scheduleSub(msg, when) {
  const item = { text: msg.tgt || msg.src || '', at: when, id: msg.id };
  const last = subs[subs.length - 1];
  if (!last || last.at <= when) {
    subs.push(item);
  } else {
    // 少数乱序 ⇒ 二分插入
    let lo = 0, hi = subs.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (subs[mid].at <= when) lo = mid + 1; else hi = mid;
    }
    subs.splice(lo, 0, item);
  }
  if (subs.length > SUBS_CAP) {
    const dropped = subs.length - SUBS_CAP;
    subs.splice(0, dropped);
    metrics.subsDropped = (metrics.subsDropped || 0) + dropped;
  }
}

function pumpSubs() {
  if (!audioCtx) return;
  const now = audioCtx.currentTime;
  const div = document.getElementById('subs');
  while (subs.length && subs[0].at <= now) {
    const s = subs.shift();
    div.innerHTML = `<span>${escapeHtml(s.text)}</span>`;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ══════════════════════════════════════════════════════════════
// P0①：音频上行（16 kHz 重采样 → WebSocket）
// ══════════════════════════════════════════════════════════════
// ★ 实测结论（本机 Edge 156，见 STATUS §2）：
//   **offscreen document 里 AudioWorklet 不被驱动**
//   （ac.state=running，但 worklet 的 process() 从未被调用 ⇒ 0 帧）。
//   而同样的代码在**扩展页**（player.html）里完全正常
//   （实测 2.5 s 内 worklet 回报 18 次，与 48 kHz 渲染速率吻合）。
//   ⇒ 音频上行走**扩展页**；offscreen 保留为生产路径（tabCapture 必须在
//     offscreen 里 getUserMedia）的备选实现。

const upState = {
  ac: null, node: null, source: null, ws: null,
  seq: 0, sampleIndex: 0, frameCount: 0, bytesSent: 0,
  gaps: 0, gapDetail: [], maxAbsSkewMs: 0, maxAbsSkewAllMs: 0, skewSamples: [],
  t0: 0, running: false, wsOpen: false, error: null,
  sourceRate: 0, captureMode: null,
  // ★ skew **尖峰的时间线**：记录最大的 N 个尖峰及其发生的墙钟时刻。
  //   用途：把「主线程卡顿」与「同机其它进程抢 CPU」区分开 ——
  //   若尖峰时刻与外部推理任务的运行时段重合 ⇒ 外部干扰；
  //   若均匀散布 ⇒ 本模块自身的累积型缺陷。
  skewSpikes: [],
};

/** 启动瞬态帧数（前 N 帧不计入「稳定期最大偏差」）。 */
const WARMUP_FRAMES = 50;

function upPost(msg) {
  try {
    chrome.storage.local.get({ extLog: [] }).then((s) => {
      const arr = (s.extLog || []).concat([{ ts: Date.now(), ...msg }]).slice(-200);
      return chrome.storage.local.set({ extLog: arr });
    }).catch(() => {});
  } catch (e) { /* ignore */ }
}

/** 把 48 kHz 抓到的音频重采样到 16 kHz 并上行。 */
async function startUplink(stream, wsUrl, token) {
  if (upState.running) return { ok: true, already: true };
  try {
    const track = stream.getAudioTracks()[0];
    if (!track) return { ok: false, error: '没有音频轨' };
    const st = track.getSettings ? track.getSettings() : {};
    upState.sourceRate = st.sampleRate || 48000;
    upState.captureMode = 'getDisplayMedia';

    // ① WebSocket
    const ws = new WebSocket(wsUrl);
    upState.ws = ws;
    await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('WS 超时')), 8000);
      ws.onopen = () => {
        clearTimeout(t);
        upState.wsOpen = true;
        ws.send(JSON.stringify({
          type: 'hello', token, role: 'uplink', sample_rate: 16000,
          source: 'player', delay_sec: delaySec,
        }));
        resolve();
      };
      ws.onerror = () => { clearTimeout(t); reject(new Error('WS 失败')); };
    });

    // ② AudioContext + AudioWorklet（**必须在扩展页**；offscreen 不渲染音频图）
    const ac = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
    for (let i = 0; i < 10; i++) {
      try { await ac.resume(); } catch (e) { /* ignore */ }
      if (ac.state === 'running') break;
      await new Promise((r) => setTimeout(r, 100));
    }
    upState.ac = ac;
    await ac.audioWorklet.addModule(chrome.runtime.getURL('capture-worklet.js'));

    const node = new AudioWorkletNode(ac, 'capture-processor', {
      numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
      processorOptions: {
        targetRate: 16000, inputRate: upState.sourceRate,
        frameMinMs: 20, frameMaxMs: 100,
      },
    });
    upState.node = node;
    const source = ac.createMediaStreamSource(new MediaStream([track]));
    upState.source = source;
    source.connect(node);
    const mute = ac.createGain();
    mute.gain.value = 0;
    node.connect(mute);
    mute.connect(ac.destination);

    node.port.onmessage = (ev) => onUplinkFrame(ev.data);
    upState.t0 = 0;   // ★ 由首帧的 inSamples 反推真实基准点
    upState.running = true;
    upPost({ type: 'log', msg: `上行启动：${upState.sourceRate} Hz → 16 kHz，ac=${ac.state}` });
    return { ok: true, sourceRate: upState.sourceRate, acState: ac.state };
  } catch (e) {
    upState.error = String((e && e.message) || e);
    return { ok: false, error: upState.error };
  }
}

function onUplinkFrame(d) {
  const pcm = d.pcm;
  const nSamples = pcm.byteLength / 2;
  const seq = d.seq;
  const sampleIndex = d.sampleIndex;

  // ★ 基准点：首个输入样本到达工作线程的时刻。
  //   首帧到达主线程时，worklet 已处理了 inSamples 个 48 kHz 输入样本，
  //   ⇒ 样本 0 的墙钟时刻 ≈ now - inSamples/sourceRate。
  //   （之前用「建好节点后立刻记 t0」做基准，会把抓流管线的固定延迟
  //     算进偏差里，实测恒定 +131 ms；修正后只剩真实漂移。）
  if (upState.seq === 0) {
    const inMs = (d.inSamples || 0) / upState.sourceRate * 1000;
    upState.t0 = performance.now() - inMs;
    upState.pipelineLatencyMs = inMs;
  }

  // 连续性
  if (upState.seq > 0) {
    if (seq !== upState.seq) {
      upState.gaps += (seq - upState.seq);
      upState.gapDetail.push({ kind: 'seq', expect: upState.seq, got: seq });
    }
    if (sampleIndex !== upState.sampleIndex) {
      upState.gaps += 1;
      upState.gapDetail.push({
        kind: 'sample', expect: upState.sampleIndex, got: sampleIndex,
        delta: sampleIndex - upState.sampleIndex,
      });
    }
  }

  // 采样计数 vs 墙钟
  // ★ 口径说明：前若干帧含**启动瞬态**（抓流管线尚未稳定，基准点有几十 ms
  //   的固定偏移）。实测 90 s：skewFirst=-21.3 ms → skewLast=-23.2 ms
  //   （仅变 1.9 ms，漂移 5.5 ms/分钟 ⇒ 不累积）。
  //   ⇒ 稳定性判定用「剔除前 WARMUP_FRAMES 帧后的最大绝对偏差」，
  //     启动瞬态单独记录，不混进稳定性指标。
  const audioSec = sampleIndex / 16000;
  const wallSec = (performance.now() - upState.t0) / 1000;
  const skewMs = (audioSec - wallSec) * 1000;
  if (upState.skewSamples.length < 60000) upState.skewSamples.push(skewMs);
  if (upState.skewSamples.length > WARMUP_FRAMES) {
    if (Math.abs(skewMs) > upState.maxAbsSkewMs) upState.maxAbsSkewMs = Math.abs(skewMs);
    if (Math.abs(skewMs) > upState.maxAbsSkewAllMs) upState.maxAbsSkewAllMs = Math.abs(skewMs);
    // ★ 记录尖峰时间线（只留超过 50 ms 阈值的，避免噪声）
    if (Math.abs(skewMs) > 50) {
      upState.skewSpikes.push({
        wall: new Date().toISOString(),
        tRelMs: Math.round(performance.now() - upState.t0),
        skewMs: Math.round(skewMs * 100) / 100,
        seq,
      });
      if (upState.skewSpikes.length > 2000) upState.skewSpikes.shift();
    }
  } else {
    if (Math.abs(skewMs) > upState.maxAbsSkewAllMs) upState.maxAbsSkewAllMs = Math.abs(skewMs);
  }

  upState.seq = seq + 1;
  upState.sampleIndex = sampleIndex + nSamples;
  upState.frameCount += 1;

  if (upState.ws && upState.ws.readyState === WebSocket.OPEN) {
    const bytes = new Uint8Array(pcm);
    let bin = '';
    const CH = 0x8000;
    for (let i = 0; i < bytes.length; i += CH) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    }
    upState.ws.send(JSON.stringify({
      type: 'pcm', seq, sample_index: sampleIndex, pcm: btoa(bin),
    }));
    upState.bytesSent += bytes.length;
  }
  metrics.uplinkFrames = upState.frameCount;
  metrics.uplinkSeq = upState.seq;
  metrics.uplinkGaps = upState.gaps;
  metrics.uplinkSkewMs = upState.maxAbsSkewMs;
}

function uplinkSnapshot() {
  const sk = upState.skewSamples;
  const abs = sk.map(Math.abs).sort((a, b) => a - b);
  const pct = (p) => (abs.length ? abs[Math.min(abs.length - 1, Math.floor(abs.length * p))] : null);
  // 漂移斜率：对 (时刻, skew) 做最小二乘直线拟合 ⇒ 每分钟漂移多少 ms
  let driftMsPerMin = null;
  if (sk.length >= 20) {
    const n = sk.length;
    let sx = 0, sy = 0, sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) {
      const x = i / n;            // 归一化时间（0..1）
      sx += x; sy += sk[i]; sxx += x * x; sxy += x * sk[i];
    }
    const den = n * sxx - sx * sx;
    if (den !== 0) {
      const slope = (n * sxy - sx * sy) / den;   // ms per 整个样本区间
      driftMsPerMin = slope * 60000 / Math.max(1, (upState.t0
        ? (performance.now() - upState.t0) : 0));
    }
  }
  return {
    running: upState.running,
    captureMode: upState.captureMode,
    sourceRate: upState.sourceRate,
    seq: upState.seq,
    sampleIndex: upState.sampleIndex,
    frameCount: upState.frameCount,
    bytesSent: upState.bytesSent,
    gaps: upState.gaps,
    gapDetail: upState.gapDetail.slice(-20),
    maxAbsSkewMs: upState.maxAbsSkewMs,
    maxAbsSkewAllMs: upState.maxAbsSkewAllMs,
    warmupFrames: WARMUP_FRAMES,
    skewP50: pct(0.50), skewP95: pct(0.95), skewP99: pct(0.99),
    skewFirst: sk.length ? sk[0] : null,
    skewLast: sk.length ? sk[sk.length - 1] : null,
    skewSamples: sk.length,
    skewSpikes: upState.skewSpikes.slice(-200),
    nSkewSpikes: upState.skewSpikes.length,
    driftMsPerMin,
    wsOpen: upState.wsOpen,
    elapsedMs: upState.t0 ? performance.now() - upState.t0 : 0,
    error: upState.error,
  };
}

// ══════════════════════════════════════════════════════════════
// 抓流（真实用户手势触发）
// ══════════════════════════════════════════════════════
/**
 * 开始捕获整页音视频。
 * ★ 必须由**用户手势**调用（getDisplayMedia / tabCapture 都要求手势）。
 *   自动化里由 Playwright 点击「开始捕获」按钮触发（等价真实手势）。
 */
async function startCapture() {
  if (metrics.captureStarted) return { ok: true, already: true };
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 30 }, audio: true,
    });
    capturedStream = stream;
    metrics.captureStarted = true;

    const vt = stream.getVideoTracks()[0];
    const at = stream.getAudioTracks()[0];
    if (at) {
      const st = at.getSettings ? at.getSettings() : {};
      metrics.sourceRate = st.sampleRate || 48000;
      setupOriginalAudio(new MediaStream([at]));
      // ★ P0① 音频上行（16 kHz → 桥接服务）
      const cfg = await chrome.storage.local.get({
        wsUrl: 'ws://127.0.0.1:8765/', token: '',
      });
      const up = await startUplink(stream, cfg.wsUrl, cfg.token);
      metrics.uplinkStart = up;
    }
    if (vt) await attachVideoTrack(vt);
    report({ kind: 'capture_ready', video: !!vt, audio: !!at,
             uplink: metrics.uplinkStart });
    return { ok: true, uplink: metrics.uplinkStart };
  } catch (e) {
    report({ kind: 'capture_error', error: String((e && e.message) || e) });
    return { ok: false, error: String((e && e.message) || e) };
  }
}

/** 原声延迟 + ducking（EXT-001 A 节：与画面同一时钟） */
function setupOriginalAudio(stream) {
  if (!stream || !audioCtx) return;
  origSource = audioCtx.createMediaStreamSource(stream);
  // ★ DelayNode 的 maxDelayTime 是**构造参数**：写成 createDelay(2.0) 再把
  //   delayTime 设成 10 会被钳到 2 秒（实测浏览器警告
  //   "Delay.delayTime.value 10 outside nominal range [0, 2]"）
  //   ⇒ maxDelayTime 必须 ≥ 需要的 D。
  origDelay = audioCtx.createDelay(Math.max(2, delaySec + 1));
  origDelay.delayTime.value = delaySec;
  origGain = audioCtx.createGain();
  origGain.gain.value = 1.0;
  origSource.connect(origDelay);
  origDelay.connect(origGain);
  origGain.connect(audioCtx.destination);
  // ★ 原声 onset 检测（唇音同步参考点）
  makeOnsetDetector(origGain, onOrigOnset, 0.02).then(n => { origOnsetNode = n; });
}

// ══════════════════════════════════════════════════════════════
// P0②：把视频轨接进 WebCodecs 延迟管线
// ══════════════════════════════════════════════════════════════
async function attachVideoTrack(track) {
  const st = track.getSettings ? track.getSettings() : {};
  metrics.sourceWidth = st.width || 0;
  metrics.sourceHeight = st.height || 0;

  const proc = new MediaStreamTrackProcessor({ track });
  const reader = proc.readable.getReader();

  // ★ 编码器尺寸必须来自**真实帧**，不能用 track.getSettings()。
  //   实测：getSettings() 给 2048x1280，而实际帧是 2048x1078
  //   ⇒ 尺寸不符 ⇒ VideoEncoder 直接 OperationError（encoded 恒为 0）。
  //   所以：等第一帧到了，用它的 displayWidth/Height 来配置编码器。
  let encSize = null;

  (async () => {
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!value) continue;
        const frame = value;

        if (!encSize) {
          const w = frame.displayWidth || st.width || 1920;
          const h = frame.displayHeight || st.height || 1080;
          // 尺寸取偶数（I420 要求）
          encSize = { w: w & ~1, h: h & ~1 };
          metrics.videoWidth = encSize.w;
          metrics.videoHeight = encSize.h;
          try {
            const codec = await initVideoCodecs(encSize.w, encSize.h);
            report({ kind: 'video_start', codec, width: encSize.w, height: encSize.h,
                     hw: metrics.hwAcceleration, sourceW: st.width, sourceH: st.height });
          } catch (e) {
            metrics.videoError = 'codec_init_failed: ' + String(e);
            report({ kind: 'video_error', error: metrics.videoError });
            frame.close();
            break;
          }
        }

        const tsUs = Math.round((audioCtx.currentTime - t0) * 1e6);
        // ★ 统一走 OffscreenCanvas 缩放到编码尺寸（尺寸/格式不一致都会让编码失败）
        const oc = new OffscreenCanvas(encSize.w, encSize.h);
        const g = oc.getContext('2d');
        g.drawImage(frame, 0, 0, encSize.w, encSize.h);
        frame.close();
        const out = new VideoFrame(oc, {
          timestamp: tsUs, duration: Math.round(1e6 / 30),
        });

        if (videoEncoder && videoEncoder.state === 'configured') {
          if (tsUs - lastEncTs >= 1e6 / 30) {
            lastEncTs = tsUs;
            // ★ 首帧强制关键帧（decoderConfig 只在关键帧的 meta 里出现）
            const keyFrame = metrics.encoded === 0 || (metrics.encoded % 60) === 0;
            try {
              videoEncoder.encode(out, { keyFrame });
            } catch (e) {
              metrics.encodeError = String(e);
            }
          }
        }
        out.close();
      }
    } catch (e) {
      metrics.videoError = String(e);
      report({ kind: 'video_error', error: String(e) });
    }
  })();
}

// ══════════════════════════════════════════════════════════════
// WebSocket：接桥接服务
// ══════════════════════════════════════════════════════════════
function connectBridge(wsUrl, token, role) {
  return new Promise((resolve, reject) => {
    const w = new WebSocket(wsUrl);
    w.binaryType = 'arraybuffer';
    const t = setTimeout(() => { try { w.close(); } catch (e) {} reject(new Error('WS 超时')); }, 8000);
    w.onopen = () => {
      clearTimeout(t);
      // ★ 浏览器 WS 不能自定义请求头 ⇒ token 放在首个 hello 里
      w.send(JSON.stringify({
        type: 'hello', token, role, sample_rate: 16000, delay_sec: delaySec,
      }));
      resolve(w);
    };
    w.onerror = () => { clearTimeout(t); reject(new Error('WS 失败')); };
    w.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'hello_ack') {
          if (m.delay_sec != null && isNaN(D_OVERRIDE)) delaySec = m.delay_sec;
          report({ kind: 'hello_ack', delay_sec: m.delay_sec,
                   sample_rate: m.sample_rate, segmentation: m.segmentation });
        } else if (m.type === 'echo' || m.type === 'tts') {
          metrics.echoRecv++;
          const r = scheduleDub(m);
          report({ kind: 'dub', id: m.id, t_start: m.t_start, t_end: m.t_end,
                   planned: r && r.planned, requested: r && r.requested });
        }
      } catch (e) { /* ignore */ }
    };
  });
}

// ★ report 只发**摘要**，不发整个 metrics。
//   真实缺陷（实测：5 分钟长测 maxAbsSkew 595 ms）：metrics 里含
//   onsetErrs / lipErrs / drawMarks / origOnsets / dubOnsets
//   五个各 200~500 项的浮点数组，每秒随 report 全量发给 SW，
//   SW 再转发 offscreen，offscreen 又写 chrome.storage.local（保留 200 条）
//   ⇒ 每秒几十 KB~几百 KB 的 JSON 序列化 + 磁盘写入 ⇒ 主线程周期性卡顿。
//   ⇒ 跨上下文只传标量摘要；完整数组留在 player 页，用 __ext.metrics() 按需取。
const REPORT_SCALARS = [
  'queued', 'encoded', 'decoded', 'dropped', 'drawn',
  'lipSyncMs', 'schedErrMs', 'schedErrP50', 'schedErrP95',
  'codecUsed', 'hwAcceleration', 'frames', 'lastFrameAt',
  'videoWidth', 'videoHeight', 'sourceRate',
  'echoRecv', 'echoSent', 'captureStarted', 'audioCtxOk',
  'uplinkFrames', 'uplinkSeq', 'uplinkGaps', 'uplinkSkewMs',
  'pendingSchedDropped', 'subsDropped',
];

function reportSummary(obj) {
  const out = { kind: obj && obj.kind };
  if (obj && obj.kind) {
    // 保留本次事件的标量字段（排除数组）
    for (const k of Object.keys(obj)) {
      if (k === 'kind') continue;
      const v = obj[k];
      if (v === null || typeof v !== 'object') out[k] = v;
    }
  }
  for (const k of REPORT_SCALARS) {
    if (k in metrics) out[k] = metrics[k];
  }
  return out;
}

function report(obj) {
  window.__extMetrics = window.__extMetrics || {};
  if (obj && obj.kind) window.__extMetrics[obj.kind] = obj;
  window.__extMetrics.last = obj;
  // ★ 只发给 SW（SW 是唯一返回 true 的 listener），player 侧不再发
  //   'ext-log'（会与其他上下文抢通道）。
  //   只发标量摘要，不发数组（见 reportSummary 注释）。
  try {
    chrome.runtime.sendMessage({ target: 'sw', cmd: 'metrics',
                                metrics: reportSummary(obj) });
  } catch (e) { /* ignore */ }
}

// ══════════════════════════════════════════════════════════════
// 唇音同步（白闪 + 嘀声）
// ══════════════════════════════════════════════════════════════
/**
 * 白闪（画面）与嘀声（声音）在源时刻 T 同时出现。
 *  * 白帧被**画到 canvas** 的时刻 = t0 + T + 画面链路延迟
 *  * 嘀声（经 DelayNode(D) 延迟后）被**播出**的时刻 = t0 + T + 音频链路延迟
 * 两者之差 = 唇音同步误差（EXT-003 目标 ≤ 40 ms）
 *
 * ★ 配对方式：按时间排序后**一对一最近邻贪心配对**
 *   （旧实现对每个 onset 都取全局最近的 drawMark，会重复用同一个标记，
 *    实测算出 1962 ms 的荒谬值）。
 */
function computeLipSync() {
  const marks = metrics.drawMarks;
  const onsets = metrics.origOnsets;
  if (!marks.length || !onsets.length) return null;

  const pairs = [];
  const sortedOnsets = [...onsets].sort((a, b) => a - b);
  const sortedMarks = [...marks].sort((a, b) => a - b);

  // ★ 单调双指针一对一配对：O(n) 而非 O(n²)。
  //   真实缺陷：旧实现对每个 onset 全表扫描 marks（n=500 ⇒ 25 万次比较/秒，
  //   每秒调一次 computeLipSync）⇒ 主线程持续负担。
  //   两个数组都已排序 ⇒ 用单调指针即可得到**一对一**配对：
  //   对每个 onset，在尚未消费的标记里找**最近**的那个，
  //   配对后该标记被消费（usedMark 语义），指针只向前走。
  //   超过 PAIR_GAP_MAX 的配对直接丢弃（不是同一个源事件）。
  const PAIR_GAP_MAX = 1.0;   // 秒
  let j = 0;
  for (const a of sortedOnsets) {
    // 跳过明显早于 a 的标记（它们属于更早的 onset）
    while (j < sortedMarks.length && sortedMarks[j] < a - PAIR_GAP_MAX) j++;
    // 在 [j, j+2] 里找最近的未消费标记
    let bestK = -1, bestD = Infinity;
    const hi = Math.min(sortedMarks.length - 1, j + 2);
    for (let k = j; k <= hi; k++) {
      const d = Math.abs(sortedMarks[k] - a);
      if (d < bestD) { bestD = d; bestK = k; }
    }
    if (bestK < 0) continue;
    const m = sortedMarks[bestK];
    if (bestD <= PAIR_GAP_MAX) {
      pairs.push({ visualAt: m, audioAt: a, errMs: (m - a) * 1000, gapSec: bestD });
      // ★ 只有成功配对才消费标记（否则会跳过后续 onset 还能用的标记）
      while (j < sortedMarks.length && sortedMarks[j] <= m) j++;
    } else {
      // 最近的也超阈值 ⇒ 当前 onset 落单，标记不消费
      // （指针 j 不动，下一个 onset 仍可从 j 起找）
      continue;
    }
  }
  if (!pairs.length) return null;

  // 只保留「配对间距合理」的配对（>1 s 说明根本不是同一个源事件）
  const good = pairs.filter((p) => p.gapSec <= 1.0);
  if (!good.length) return null;

  const errs = good.map((p) => p.errMs);
  const absErrs = errs.map(Math.abs).sort((a, b) => a - b);
  const pct = (p) => absErrs[Math.min(absErrs.length - 1, Math.floor(absErrs.length * p))];
  const mean = errs.reduce((s, x) => s + x, 0) / errs.length;

  lipSyncData = {
    visualAt: good[0].visualAt, audioAt: good[0].audioAt,
    errMs: errs[0], pairGapSec: good[0].gapSec,
    nPairs: good.length,
    meanErrMs: mean,
    absErrP50: pct(0.50), absErrP95: pct(0.95),
    absErrMax: absErrs[absErrs.length - 1],
  };
  metrics.lipSyncMs = lipSyncData.meanErrMs;
  metrics.lipSyncAbsP95 = pct(0.95);
  metrics.lipSyncMaxAbs = absErrs[absErrs.length - 1];
  metrics.lipPairCount = good.length;
  metrics.lipErrs.push(...errs);
  if (metrics.lipErrs.length > 500) metrics.lipErrs.splice(0, metrics.lipErrs.length - 500);
  report({ kind: 'lipsync', ...lipSyncData });
  return lipSyncData;
}

// ══════════════════════════════════════════════════════════════
// 测试钩子
// ══════════════════════════════════════════════════════════════
window.__ext = {
  metrics: () => ({
    ...metrics,
    queued: encQueue.length,
    lipSync: lipSyncData,
    delaySec,
    audioTime: audioCtx ? audioCtx.currentTime : 0,
    t0,
    schedErrP50: pct(metrics.onsetErrs, 0.5),
    schedErrP95: pct(metrics.onsetErrs, 0.95),
    uplink: uplinkSnapshot(),
  }),
  setDelay: (d) => { delaySec = d; },
  getAudioTime: () => (audioCtx ? audioCtx.currentTime : 0),
  getT0: () => t0,
  computeLipSync,
  report,
  startCapture,
  attachVideoTrack,
  setupOriginalAudio,
  initVideoCodecs,
  connectBridge,
  startUplink,
  uplinkSnapshot,
  /** P0③ 自测：直接排程一段 PCM，测浏览器端排程误差 */
  selfTestSchedule: (pcmB64, tStart) => scheduleDub({ id: 'selftest', t_start: tStart, pcm24k: pcmB64 }),
};

// ══════════════════════════════════════════════════════════════
// 启动
// ══════════════════════════════════════════════════════════════
async function boot() {
  const cfg = await chrome.storage.local.get({
    wsUrl: 'ws://127.0.0.1:8765/', token: '', delaySec: 10,
  });
  delaySec = isNaN(D_OVERRIDE) ? (cfg.delaySec || 10) : D_OVERRIDE;

  // ★ 唯一的时钟源
  try {
    audioCtx = new AudioContext({ sampleRate: 48000, latencyHint: 'interactive' });
    await audioCtx.resume();
    metrics.audioCtxOk = true;
  } catch (e) {
    report({ kind: 'audioctx_error', error: String(e) });
    return;
  }
  t0 = audioCtx.currentTime;

  // 配音总线 + onset 检测
  dubBus = audioCtx.createGain();
  dubBus.gain.value = 1.0;
  dubBus.connect(audioCtx.destination);
  try {
    onsetNode = await makeOnsetDetector(dubBus, onDubOnset, 0.02);
  } catch (e) {
    report({ kind: 'onset_error', error: String(e) });
  }

  setInterval(() => { pumpDecoder(); pumpSubs(); updateHud(); }, 40);
  setInterval(() => {
    computeLipSync();
    report({ kind: 'metrics', ...metrics, queued: encQueue.length });
  }, 1000);

  try {
    ws = await connectBridge(cfg.wsUrl || 'ws://127.0.0.1:8765/', cfg.token || '', 'player');
  } catch (e) {
    report({ kind: 'ws_error', error: String(e) });
  }

  // 「开始捕获」按钮 ⇒ 真实用户手势入口
  const btn = document.getElementById('btnCapture');
  if (btn) {
    btn.addEventListener('click', () => { startCapture(); });
    btn.style.display = 'inline-block';
    if (AUTO_CAPTURE) {
      // 自动模式下由 Playwright 点这个按钮（真实手势）
      report({ kind: 'capture_button_ready' });
    }
  }
}

function updateHud() {
  const m = metrics;
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('mQueue', encQueue.length);
  set('mEnc', m.encoded);
  set('mDec', m.decoded);
  set('mDraw', m.drawn);
  set('mDrop', m.dropped);
  set('mCodec', m.codecUsed || '—');
  set('mDelay', delaySec);
  set('mLip', m.lipSyncMs == null ? '—' : m.lipSyncMs.toFixed(1));
  set('mSched', m.schedErrMs == null ? '—' : m.schedErrMs.toFixed(2));
  set('mCpu', m.cpuPct == null ? '—' : m.cpuPct.toFixed(1));
  set('mMem', m.memMB == null ? '—' : m.memMB.toFixed(1));
}

boot();
