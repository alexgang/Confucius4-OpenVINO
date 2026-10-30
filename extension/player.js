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
// ★ 隔离开关：?video=0 关掉视频管线（只留音频上行）。
//   用途：把「主线程 stall 的来源」拆开对照 ——
//     video=1（默认）：完整管线（抓流 + 编码 + 解码 + 绘制 + 白闪检测）
//     video=0        ：只跑音频上行（AudioWorklet + WebSocket）
//   ⇒ 两者 stall 差异即可定位到具体子系统，而不是靠猜。
const VIDEO_ENABLED = qs.get('video') !== '0';

const cv = document.getElementById('cv');
// ★ 主画布**不要** willReadFrequently：
//   白闪检测已改到独立的小画布（probeCanvas）上做，
//   主画布不再需要像素回读 ⇒ 保持 GPU 加速路径，
//   否则整个 1908×1072 画布走 CPU 软件光栅化（实测 drawImage self time 7.67 s）。
const ctx2d = cv.getContext('2d');
// ★ 白闪检测用的小画布：16×9 ⇒ 整帧回读只有 576 字节，
//   取代旧实现「每帧 5 次 2×2 getImageData」（每次都是同步 GPU→CPU 回读）。
const PROBE_W = 16, PROBE_H = 9;
let probeCanvas = null;
let probeCtx = null;
// ★ 白闪检测的采样频率。
//   ★ 真实缺陷（实测 P0② drawMarks=0，唇音同步无法配对）：
//     源页白闪**只持续 1 帧**（≈33 ms，每 60 帧一次）。
//     降频到每 15 帧（500 ms）⇒ 命中概率仅 33/500 ≈ 6.6%
//     ⇒ 45 s 里 22 次白闪**一次都没抓到**（实测 drawMarks=0）。
//   ⇒ 必须**每帧**检测。但因为用的是**异步** copyTo（不阻塞主线程），
//     每帧一次的代价是「异步 GPU 读 576 字节」而非「同步等待 GPU 队列」，
//     与旧实现（每帧 5 次**同步** getImageData）不是一个量级。
//   ⇒ 设为 1（每帧检测）。
const FLASH_DETECT_EVERY = 1;
let flashFrameCount = 0;

// ★ 编码限速（fps）。
//   实测（5 分钟长测，.tmp/probe_uplink_5min_v5）：源 30 fps，
//   但本机 VP8 软件编码实际吞吐只有 ~18 fps（encoded 8554 / 182 s ≈ 47 fps
//   含降频后的效果；修复前 5 分钟只编出 ~5400 帧 ≈ 18 fps）。
//   ⇒ 每帧都 encode 会把编码器灌爆 ⇒ 积压 ⇒ 解码端突发 ⇒ 主线程 stall。
//   ⇒ 限到 15 fps：延迟画面允许掉帧（EXT-001 只要求「缓冲 D 秒后播放、保持音画同步」，
//     掉帧不影响音画同步，因为音画各走各的时间轴），
//     而 stall 会直接破坏「采样计数 vs 墙钟 < 50 ms」这条硬指标。
//   ⇒ 取 15 fps（低于实测吞吐 18 fps，留出余量 ⇒ 编码器永不积压）。
const ENCODE_FPS = 15;

// ★ 编码器内部队列上限（浏览器规范 API `encodeQueueSize`）。
//   积压 ⇒ 编码落后于实时 ⇒ 解码端会突发吐帧 ⇒ 主线程 stall。
//   ⇒ 队列超过这个数就**直接丢帧**（延迟画面允许丢帧，音画同步不受影响）。
const ENCODE_QUEUE_MAX = 4;

// ★ 编码用的 OffscreenCanvas **复用**（避免每帧分配 8 MB）。
let encCanvas = null;
let encCtx = null;
// ★ 白闪检测用**异步** VideoFrame.copyTo()，不用 canvas.getImageData。
//   实测（CDP CPU Profile）：getImageData self time = 10.35 s（3600 次 ≈ 2.9 ms/次），
//   即使回读只有 576 字节也一样贵 —— 因为它是**同步的 GPU→CPU 管线等待**
//   （要等 GPU 队列排空），主线程被挂住 ⇒ 音频 worklet 消息处理延迟
//   ⇒ 采样计数 vs 墙钟出现数百 ms 尖峰。
//   ⇒ 改用 `await frame.copyTo(buffer)`：WebCodecs 的异步拷贝，
//     不阻塞主线程；顺带把采样降到 16×9 ⇒ 每次只拷 576 字节。
//   ⇒ 用一个「检测中」标志避免重入（同一时刻只允许一次拷贝在飞）。
let flashBusy = false;
async function detectFlash(frame, w, h) {
  try {
    // ★ 采样**中心区域**（源页白闪是整屏纯白，中心最可靠）
    //   取 16×9 的中心块 ⇒ 每次只拷 576 字节
    const cw = Math.min(PROBE_W, w), ch = Math.min(PROBE_H, h);
    const size = cw * ch * 4;
    if (!flashBuf || flashBuf.byteLength !== size) {
      flashBuf = new Uint8Array(size);
    }
    const x0 = Math.max(0, Math.floor((w - cw) / 2));
    const y0 = Math.max(0, Math.floor((h - ch) / 2));
    // ★ 异步拷贝：不阻塞主线程
    //   ★★ 必须显式指定 format: 'RGBA'（真实缺陷，实测 drawMarks=0）：
    //     VideoFrame.copyTo 的 options.format 缺省时**沿用帧的原生格式**。
    //     本机 VP8 解码出的帧是 **I420**（YUV420 平面）⇒ 16×9 区域只有
    //       16×9×1.5 = **216 字节**（Y 144 + U 36 + V 36），
    //     而我们按 RGBA 读 16×9×4 = **576 字节**
    //     ⇒ 多出的 360 字节是**上一帧的陈旧数据/零**
    //     ⇒ 算出来的 avg 永远接近 0 ⇒ **白闪一次都检不出**
    //       （实测 45 s：drawMarks=0，而源页白闪有 22 次 ⇒ 100% 漏检）
    //   ⇒ 显式要 RGBA，copyTo 负责做色彩空间转换（16×9 = 576 字节，代价可忽略）。
    const layout = await frame.copyTo(flashBuf, {
      format: 'RGBA',
      rect: { x: x0, y: y0, width: cw, height: ch },
    });
    if (!layout) throw new Error('copyTo 返回空');
    let sum = 0, n = 0, white = 0;
    const d = flashBuf;
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i + 1], b = d[i + 2];
      sum += r + g + b; n += 3;
      if (r > 235 && g > 235 && b > 235) white++;
    }
    const avg = n ? sum / n : 0;
    const whiteRatio = n ? white / (n / 3) : 0;
    if (avg > 200 && whiteRatio > 0.6) {
      const at = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
      metrics.drawMarks.push(at);
      if (metrics.drawMarks.length > 200) metrics.drawMarks.shift();
    }
  } catch (e) {
    // ★ 兜底：copyTo 不可用（像素格式不支持等）⇒ 退回 canvas 回读，
    //   但**大幅降频**（每 60 帧 = 每秒 1 次）⇒ 性能影响可忽略。
    //   （旧实现是每帧 5 次 ⇒ 每秒 150 次）
    try {
      flashFallbackCount++;
      if (flashFallbackCount % 60 === 0) {
        if (!probeCanvas) {
          probeCanvas = document.createElement('canvas');
          probeCanvas.width = PROBE_W;
          probeCanvas.height = PROBE_H;
          probeCtx = probeCanvas.getContext('2d', { willReadFrequently: true });
        }
        probeCtx.drawImage(frame, 0, 0, PROBE_W, PROBE_H);
        const d = probeCtx.getImageData(0, 0, PROBE_W, PROBE_H).data;
        let sum = 0, n = 0, white = 0;
        for (let i = 0; i < d.length; i += 4) {
          const r = d[i], g = d[i + 1], b = d[i + 2];
          sum += r + g + b; n += 3;
          if (r > 235 && g > 235 && b > 235) white++;
        }
        const avg = n ? sum / n : 0;
        const whiteRatio = n ? white / (n / 3) : 0;
        if (avg > 200 && whiteRatio > 0.6) {
          const at = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
          metrics.drawMarks.push(at);
          if (metrics.drawMarks.length > 200) metrics.drawMarks.shift();
        }
      }
    } catch (e2) { /* ignore */ }
  }
}
let flashFallbackCount = 0;
let flashBuf = null;

const metrics = {
  queued: 0, encoded: 0, decoded: 0, dropped: 0, drawn: 0,
  lipSyncMs: null, schedErrMs: null, schedErrP50: null, schedErrP95: null,
  codecUsed: null, hwAcceleration: null,
  frames: 0, lastFrameAt: 0,
  videoWidth: 0, videoHeight: 0, sourceRate: 0,
  echoRecv: 0, echoSent: 0,
  onsetErrs: [], lipErrs: [], schedDetail: [],
  drawMarks: [], origOnsets: [], dubOnsets: [],
  captureStarted: false, audioCtxOk: false,
  // ★ EXT-009：自适应加速播放的当前状态（底栏显示）
  //   speed     —— 当前句采用的语速倍率（1.00 ~ 1.30）
  //   lagSec    —— 当前句的滞后秒数（实际开播 − 目标开播）
  adaptSpeed: 1.0, adaptLagSec: 0, adaptLagPeak: 0,
  adaptSpeedHistory: [],       // {id, speed, lagSec, at}
  adaptTotalSpeed: 1.0,        // 时长适配 × 自适应加速 的总倍率
  // ★★ EXT-020：原声压低量与字幕开关的**实际生效值**
  //   （不是用户设的值 —— 用来核对「设了到底有没有生效」）。
  duckDb: null,          // 用户设的 dB
  duckGain: null,        // 由 dB 换算出的线性增益
  duckDbApplied: null,   // 已真正套到 origGain 上的 dB（未抓流时为 null）
  subsOn: true,          // 字幕开关是否开启
};

// ★ EXT-009：自适应加速播放的**统一参数**
//   （与 App 一致；服务端 `ext/adaptive_speed.py` 是权威实现，
//     这里只做播放侧的应用与显示）
const ADAPT = {
  lagFreeSec: 3.0,      // lag ≤ 3 s ⇒ 1.0×
  lagHystSec: 2.0,      // 降速滞回门槛
  gainPerSec: 0.025,    // 每秒滞后的加速系数
  speedMax: 1.30,       // 上限
  maxStep: 0.10,        // 相邻句变化上限
};

// ── 全局时钟：画面与原声共用同一个 AudioContext ────────────────
let audioCtx = null;
let t0 = 0;
let delaySec = 10;
let ws = null;
let lipSyncData = null;
let capturedStream = null;

// ★★ EXT-020：popup 的「原声压低量」与「字幕开关」此前是**死控件**
//   —— popup.js 把它们存进了 chrome.storage.local，
//      但 player.js 从来没读过 ⇒ 用户在面板上怎么调都不起作用，
//      而 USER_GUIDE 明确承诺「原声压低量 / 字幕开关」可调。
//   ⇒ 现在真正接线：读 → 用 → 在 metrics 里回报实际生效值。
//
//   duckDb：原声总线的增益（dB，负数 = 压低）。
//   ★ 口径：0 dB = 不压低（增益 1.0）；-15 dB ⇒ 增益 10^(-15/20) ≈ 0.1778。
//     为什么不按「百分比」理解：面板写的是 dB，且 USER_GUIDE 举例
//     「−40 盖住原声、−6 两个都听得清」⇒ 必须是 dB 口径。
let duckDb = -15;
//   字幕开关：true = 显示译文字幕；false = 完全不写 DOM。
let subsOn = true;
//   ★ 记住「用户**实际**设的值」，与「引擎实际生效的值」区分开。
//   duckDb 只在**新设置生效时**写入 origGain.gain（见 applyDuckDb），
//   而 origGain 在抓流成功后才存在 ⇒ 设置值与生效值可能短暂不同。
let duckDbApplied = null;

// ══════════════════════════════════════════════════════════════
// P0②：WebCodecs 延迟画面管线
// ══════════════════════════════════════════════════════════════
const encQueue = [];      // 已编码块环形缓冲 {chunk, tsUs}
const ENC_CAP = 300;      // ≈10 s @30fps
let videoEncoder = null;
let videoDecoder = null;
let decoderCfg = null;
let lastEncTs = -1;

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

// ★ 待绘制帧队列 + **单一**调度器（取代旧实现的「每帧一个 setTimeout」）。
//   旧实现：每帧 setTimeout(drawFrame, waitMs) ⇒ 最多 3000 个定时器同时挂起，
//   一旦主线程被别的活堵住，恢复后这些定时器**集中触发** ⇒ 几十次
//   drawImage 挤在一个 tick 里 ⇒ 数百 ms 的二次 stall（雪崩）。
//   ⇒ 改为：帧进队列，由 pumpDecoder（40 ms 一次）按到期时间取出绘制，
//     并且**每 tick 最多画 DRAW_BUDGET_PER_TICK 帧**，
//     超预算就丢掉最旧的（预览画面允许丢帧；音画同步不受影响，
//     因为音画各走各的时间轴，画面只是给人看）。
const pendingDraws = [];
const DRAW_BUDGET_PER_TICK = 3;   // 3 × ~2 ms ≈ 6 ms/tick，远低于 50 ms 尖峰阈值
const PENDING_DRAW_CAP = 120;     // ≈ 8 s @15 fps

function onDecodedFrame(frame) {
  metrics.decoded++;
  const target = (t0 + frame.timestamp / 1e6) + delaySec;
  pendingDraws.push({ frame, target });
  if (pendingDraws.length > PENDING_DRAW_CAP) {
    // 丢掉最旧的（关掉它，释放 GPU 内存）
    const old = pendingDraws.shift();
    try { old.frame.close(); } catch (e) { /* ignore */ }
    metrics.drawDropped = (metrics.drawDropped || 0) + 1;
  }
}

/** 每 tick 最多画 DRAW_BUDGET_PER_TICK 帧，避免一次性突发绘制。 */
function pumpDraws() {
  if (!pendingDraws.length) return;
  const now = audioCtx ? audioCtx.currentTime : performance.now() / 1000;
  let drawn = 0;
  while (pendingDraws.length && pendingDraws[0].target <= now &&
         drawn < DRAW_BUDGET_PER_TICK) {
    const item = pendingDraws.shift();
    drawFrame(item.frame);
    drawn++;
  }
  // 落后太多（> 1 s）⇒ 丢弃过期帧，别让队列越积越长
  while (pendingDraws.length && now - pendingDraws[0].target > 1.0) {
    const old = pendingDraws.shift();
    try { old.frame.close(); } catch (e) { /* ignore */ }
    metrics.drawDropped = (metrics.drawDropped || 0) + 1;
  }
}

function drawFrame(frame) {
  try {
    // ★ 画布保持**显示尺寸**（HTML 里的 640×360），不要跟着源帧走。
    //   真实缺陷（CDP CPU Profile 实测，修复 getImageData 之后）：
    //     `drawImage` self time = **11.40 s**，取代 getImageData 成为头号开销。
    //   原因：旧代码把 cv.width 设成 frame.displayWidth（**1908×1072**）
    //   ⇒ 每帧把 GPU 的 VideoFrame 合成到 1908×1072 的画布上
    //   ⇒ GPU→CPU 合成成本 ~11 s / 5400 帧 ≈ 2.1 ms/帧。
    //   ⇒ 画布只要显示用（640×360 足够）⇒ 合成成本降 ~9 倍。
    //   （视频编码用的是**源帧**，不受这里影响；画布只是预览。）
    ctx2d.drawImage(frame, 0, 0, cv.width, cv.height);
    metrics.frames++;
    metrics.drawn++;
    metrics.lastFrameAt = performance.now();
    // ★ 白闪检测（唇音同步测试片）：画面接近纯白 ⇒ 记下绘制时刻。
    //
    // ★★ 真实缺陷（CDP CPU Profile 实测，.tmp/probe_profile/browser_probe.json）：
    //   `getImageData` self time = **15.96 s**（非 idle 总 120.16 s 的 13.3%，
    //   所有函数里第 1 名）；`drawImage` 7.67 s 第 2 名。
    //   旧实现每帧调 **5 次** `getImageData(x,y,2,2)`：
    //   每次都是一次**同步的 GPU→CPU 管线等待**（要等 GPU 队列排空）
    //   ⇒ 30 fps × 5 = 每秒 150 次同步等待
    //   ⇒ 主线程周期性阻塞 ⇒ 音频 worklet 消息处理延迟
    //   ⇒ 采样计数 vs 墙钟出现数百 ms 尖峰。
    //   A/B 隔离实测（.tmp/ab_video_on vs .tmp/ab_video_off）：
    //     video=1 ⇒ maxAbsSkew **639.99 ms**（getImageData 10.35 s）
    //     video=0 ⇒ maxAbsSkew **30.88 ms**（getImageData 0，达标）
    //   ⇒ 尖峰 100% 来自视频管线的像素回读。
    //
    //   ⇒ 修复：**异步** `frame.copyTo()`（不阻塞主线程）+ 降频检测。
    flashFrameCount++;
    const needDetect = (flashFrameCount % FLASH_DETECT_EVERY === 0);
    if (needDetect && !flashBusy) {
      // ★ 拷贝是异步的 ⇒ 帧不能在拷贝完成前 close
      //   ⇒ 把 close 交给 detectFlash 在拷贝结束后做。
      flashBusy = true;
      detectFlash(frame, frame.displayWidth || frame.codedWidth || 0,
                frame.displayHeight || frame.codedHeight || 0).then(() => {
        try { frame.close(); } catch (e) { /* ignore */ }
        flashBusy = false;
      });
      return;   // 不再走下面的 close
    }
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
// ★ probe（自测）专用总线 —— 与 dubBus **物理隔离**。
//   理由见 scheduleDub 内的说明：共用总线时，bridge 回声的 onset 会
//   触发 onset-worklet 的 minGapSec=0.05 迟滞 ⇒ 抑制紧随的自测 onset
//   ⇒ 实测稳定复现 43.02 ms 的假误差。
let probeBus = null;
let probeOnsetNode = null;
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

// ★ 配对窗口：onset 与排程计划时刻的最大可接受偏差。
//   超过窗口 ⇒ 该 onset **不属于**任何排程（忽略），
//   否则重复 onset 会「跨排程」误配到下一个排程上，
//   制造出 40+ ms 的假误差（实测双峰 0.02 / 43.02）。
const PAIR_WINDOW_SEC = 0.25;

function onDubOnset(at) {
  if (!pendingSched.length) {
    metrics.dubOnsets.push(at);
    if (metrics.dubOnsets.length > 200) metrics.dubOnsets.shift();
    return;
  }

  // ★ 优先找最近的 **probe 排程**（P0③ 的统计口径）。
  //   bridge 回声排程密度高（≈47 帧/秒）⇒ 若不优先，
  //   probe 的 onset 会被最近的回声排程「抢走」⇒ probe 采不到样本。
  let pIdx = -1, pD = Infinity;
  for (let i = 0; i < pendingSched.length; i++) {
    if (!pendingSched[i].probe) continue;
    const d = Math.abs(pendingSched[i].planned - at);
    if (d < pD) { pD = d; pIdx = i; }
  }
  let idx = pIdx, dist = pD;
  let isProbe = true;
  if (pIdx < 0 || pD > PAIR_WINDOW_SEC) {
    // 没有 probe 候选（或太远）⇒ 退而配到最近的普通排程（只记「发生过」）
    let nIdx = -1, nD = Infinity;
    for (let i = 0; i < pendingSched.length; i++) {
      if (pendingSched[i].probe) continue;
      const d = Math.abs(pendingSched[i].planned - at);
      if (d < nD) { nD = d; nIdx = i; }
    }
    if (nIdx < 0 || nD > PAIR_WINDOW_SEC) {
      // ★ 窗口外 ⇒ 认是「不属于任何排程的 onset」（如重复触发）
      metrics.dubOnsets.push(at);
      if (metrics.dubOnsets.length > 200) metrics.dubOnsets.shift();
      return;
    }
    idx = nIdx; dist = nD; isProbe = false;
  }

  const p = pendingSched.splice(idx, 1)[0];
  p.matched = true;

  if (!isProbe) {
    // bridge 回声排程只记「发生过」，不污染 P0③ 的口径
    metrics.dubOnsets.push(at);
    if (metrics.dubOnsets.length > 200) metrics.dubOnsets.shift();
    return;
  }

  const errMs = (at - p.planned) * 1000;
  metrics.onsetErrs.push(errMs);
  if (metrics.onsetErrs.length > 500) metrics.onsetErrs.shift();
  metrics.schedErrMs = errMs;
  metrics.schedErrP50 = pct(metrics.onsetErrs, 0.5);
  metrics.schedErrP95 = pct(metrics.onsetErrs, 0.95);
  metrics.schedDetail.push({
    id: p.id, planned: p.planned, actual: at,
    errMs: Math.round(errMs * 100) / 100,
    absDiffMs: Math.round(dist * 1000 * 100) / 100,
  });
  if (metrics.schedDetail.length > 100) metrics.schedDetail.shift();
  report({ kind: 'sched', id: p.id, planned: p.planned, actual: at, errMs });
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

/**
 * 排程一句配音到 t0 + t_start + D（AudioContext 绝对时刻）
 *
 * ★ EXT-009：这里同时应用「自适应加速播放」的**播放侧**语义：
 *   - 服务端已把「保持音高」的变速（WSOLA）做完（`pcm24k` 已是加速后的波形），
 *     并把倍率放在 `msg.speed` 里；
 *   - 插件侧**不再**对音频做任何变速（绝不能用 `playbackRate` —— 会变调），
 *     只负责：① 记录/显示倍率与滞后；② 按 EXT-009 的公式**本地复核**一遍，
 *     便于发现「服务端算的 lag」与「插件实测的 lag」差多少。
 */
function scheduleDub(msg) {
  if (!audioCtx || !msg.pcm24k) return null;
  const buf = b64ToAudioBuffer(msg.pcm24k, msg.sample_rate || 16000);
  const planned = t0 + Number(msg.t_start || 0) + delaySec;
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  // ★★ probe（自测）排程走**独立总线**（真实缺陷，实测双峰 0.02 / 43.02 ms）：
  //   原来所有排程都接同一条 dubBus，而 onset 检测器也只挂在 dubBus 上。
  //   ⇒ bridge 回声（每帧回灌，47 帧/秒）的 onset 会先触发
  //     onset-worklet 的**迟滞 + minGapSec=0.05 保护**
  //   ⇒ 紧随其后 50 ms 内的**自测 onset 被抑制**
  //   ⇒ 自测排程只能配到「晚了约 43 ms」的 onset
  //     （实测两次独立探针都精确复现 0.02 / 43.02 / 0.02 ms 三峰）
  //   ⇒ 修法：probe 排程接 **probeBus**，单独挂一个 onset 检测器，
  //     与回声检测器**物理隔离** ⇒ 互不抑制。
  const isProbe = !!msg.probe;
  src.connect(isProbe ? probeBus : dubBus);
  // ★ 钳位（排程时刻已在过去 ⇒ 立即播）**必须计数**，否则错误被静默吞掉。
  //   实测：P0③ 探针固定传 t_start=(0.5,2.0,3.5) ⇒ 第 2、3 次的 planned 已在过去
  //   ⇒ 被钳到 currentTime+0.005 ⇒ 稳定复现 43.02 ms 的假误差
  //   （主线程繁忙时 audioCtx.currentTime 滞后真实音频时钟约 43 ms）。
  //   ⇒ 计数后可见（metrics.schedClamped），不会再「看起来像真实误差」。
  const earliest = audioCtx.currentTime + 0.005;
  if (planned < earliest) {
    metrics.schedClamped = (metrics.schedClamped || 0) + 1;
    if (isProbe) metrics.probeSchedClamped = (metrics.probeSchedClamped || 0) + 1;
  }
  const when = Math.max(earliest, planned);
  src.start(when);

  // ★★ EXT-009：自适应加速播放的**播放侧记录**（不改变音频波形）
  //   - `msg.speed` 是服务端算好的**总倍率**（时长适配 × 自适应加速，封顶 1.30×）
  //     ⇒ 音频**已经是**这个倍率的波形（WSOLA 在服务端做的）⇒
  //       这里**绝不能**再对 buffer 做 playbackRate（会二次加速 + 变调）。
  //   - 插件侧实测 lag = 实际开播时刻 − 目标开播时刻
  //     （目标开播时刻 = t0 + t_start + D；实际开播时刻 = when，含钳位）
  //   - 本地按 EXT-009 公式**复核**一遍倍率，便于发现两侧口径差异。
  if (!isProbe) {
    const targetStart = t0 + Number(msg.t_start || 0) + delaySec;
    const actualStart = when;
    const lagSec = actualStart - targetStart;
    const serverSpeed = Number(msg.speed || 1.0);
    // 本地按 EXT-009 公式复核（纯对照，不用于播放）
    const localRaw = Math.max(1.0, Math.min(ADAPT.speedMax,
      1.0 + (Math.max(0, lagSec) - ADAPT.lagFreeSec) * ADAPT.gainPerSec));
    metrics.adaptSpeed = serverSpeed;
    metrics.adaptTotalSpeed = serverSpeed;
    metrics.adaptLagSec = lagSec;
    if (lagSec > metrics.adaptLagPeak) metrics.adaptLagPeak = lagSec;
    metrics.adaptSpeedHistory.push({
      id: msg.id, speed: serverSpeed, lagSec: Math.round(lagSec * 1000) / 1000,
      localRaw: Math.round(localRaw * 10000) / 10000,
      at: Math.round(audioCtx.currentTime * 1000) / 1000,
      clamped: planned < earliest,
    });
    if (metrics.adaptSpeedHistory.length > 500) metrics.adaptSpeedHistory.shift();
  }
  // ★ 有界：超出上限丢弃最旧的，并计数（不静默丢）
  //   先裁剪再 push ⇒ 长度始终 ≤ CAP
  if (pendingSched.length >= PENDING_SCHED_CAP) {
    const dropped = pendingSched.length - (PENDING_SCHED_CAP - 1);
    pendingSched.splice(0, dropped);
    metrics.pendingSchedDropped = (metrics.pendingSchedDropped || 0) + dropped;
  }
  // ★ probe 标记：P0③ 自测排程与 bridge 回声排程**必须分开统计**。
  //   实测（修复前）：bridge 回声每帧回灌一条（47 帧/秒），
  //   而 onset 检测到的声音分不清来源 ⇒ 自测排程的误差被回声的
  //   onset「抢走」⇒ 出现 0.02 / 43.02 的双峰。
  //   ⇒ 只有 probe 排程才计入 P0③ 的误差统计。
  //   （isProbe 已在上面算好；总线也已按 isProbe 分流。）
  pendingSched.push({
    id: msg.id, planned: when, requested: planned,
    matched: false, probe: isProbe,
  });
  scheduleSub(msg, when);
  return { planned: when, requested: planned };
}

// ★ subs 用**有序插入**而不是每次 push 都 sort()。
//   真实缺陷：回声模式下每帧一条 ⇒ 每次 push 都整表重排 ⇒ O(n² log n)。
//   ⇒ 改为「尾部追加 + 尾部乱序时插入排序」（绝大多数情况单调递增 ⇒ O(1)）。
const SUBS_CAP = 200;
const subs = [];
function scheduleSub(msg, when) {
  // ★★ EXT-020：字幕关着就不入队（省掉无用的文本处理与 DOM 写入）。
  if (!subsOn) {
    metrics.subsDropped = (metrics.subsDropped || 0) + 1;
    return;
  }
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
  // ★★ EXT-020：字幕开关此前是**死控件**（popup 存了 subsOn，
  //   但这里无条件写 DOM ⇒ 勾掉也照样显示字幕）。
  //   ⇒ 关掉时**完全不写 DOM**，并把已有字幕清掉（不留残影）。
  if (!subsOn) {
    const div = document.getElementById('subs');
    if (div && div.innerHTML) div.innerHTML = '';
    // 字幕已关 ⇒ 队列里的字幕直接丢弃（不入队，避免重新打开时补播旧字幕）
    if (subs.length) metrics.subsDropped = (metrics.subsDropped || 0) + subs.length;
    subs.length = 0;
    metrics.subsOn = false;
    return;
  }
  metrics.subsOn = true;
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
  // ★ 音频时钟口径的 skew（EXT-003 的验收量）
  skewAudioSamples: [], skewAudioSpikes: [],
  maxAbsSkewAudioMs: 0, t0Audio16: null,
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
          // ★★ EXT-018：把**抓流方式**上报给桥接服务。
          //   服务端会把它记进会话 ⇒ stats 回包与 margin.json 都带上
          //   ⇒ EXT-005 ①「tabCapture 生产路径到底有没有被实测过」
          //   **可以从落盘数据核对**，不用人读日志猜。
          //   ⚠️ 这里报的是**实际用的那条路**（上面的 upState.captureMode
          //     就是在拿到流的那一刻赋的值，不是计划值）。
          capture_mode: upState.captureMode,
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

  // ★★ 采样计数 vs **音频时钟**（这才是 EXT-003 要验收的量）
  //
  //   ★ 真实缺陷（实测 5 分钟 maxAbsSkew 534 ms 的**测量口径错误**）：
  //     上面那个 skewMs 是拿主线程的 performance.now() 当墙钟，
  //     但主线程同时在跑视频解码 + canvas 合成
  //     （CDP CPU Profile：drawImage 19.2 s、GC 11.5 s / 300 s）
  //     ⇒ **主线程被自己的渲染负载拖慢**
  //     ⇒ AudioWorklet 的消息要等主线程空出来才能被处理
  //     ⇒ 测出来的「偏差」其实是**主线程调度延迟**，不是采样时钟漂移。
  //
  //   ★ 正确口径：音频时钟（AudioContext.currentTime / currentFrame）
  //     由**音频硬件**驱动，在 AudioWorklet 内取值 ⇒ 与主线程负载无关。
  //     采样计数（16 kHz 域累计）与音频时钟（48 kHz 域）都是硬件时基，
  //     两者之差 = 真实的时钟偏差。
  //
  //   换算：audioFrame16 = currentFrame / decim（48 kHz → 16 kHz）
  //        音频时钟在 16 kHz 域的位置 = audioFrame16
  //        ⇒ skewAudio = (sampleIndex − audioFrame16) / 16000
  let skewAudioMs = null;
  if (d.audioFrame16 != null) {
    if (upState.t0Audio16 == null) {
      // 首帧建立基准：音频时钟域的起点 = 首帧 sampleIndex
      upState.t0Audio16 = sampleIndex - d.audioFrame16;
    }
    const audioPos16 = upState.t0Audio16 + d.audioFrame16;
    skewAudioMs = (sampleIndex - audioPos16) / 16000 * 1000;
    if (upState.skewAudioSamples.length < 60000) {
      upState.skewAudioSamples.push(skewAudioMs);
    }
    if (upState.skewAudioSamples.length > WARMUP_FRAMES) {
      if (Math.abs(skewAudioMs) > upState.maxAbsSkewAudioMs) {
        upState.maxAbsSkewAudioMs = Math.abs(skewAudioMs);
      }
      if (Math.abs(skewAudioMs) > 50) {
        upState.skewAudioSpikes.push({
          tRelMs: Math.round(performance.now() - upState.t0),
          skewMs: Math.round(skewAudioMs * 100) / 100,
          seq,
        });
        if (upState.skewAudioSpikes.length > 2000) upState.skewAudioSpikes.shift();
      }
    }
  }

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
  // ★ 音频时钟口径（EXT-003 的验收量）：采样计数 ↔ 音频硬件时钟
  const ska = upState.skewAudioSamples;
  const absa = ska.map(Math.abs).sort((a, b) => a - b);
  const pcta = (p) => (absa.length ? absa[Math.min(absa.length - 1, Math.floor(absa.length * p))] : null);
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
    // ★★ 音频时钟口径（EXT-003 验收量）：采样计数 ↔ 音频硬件时钟
    //   ⇒ 与主线程负载**无关**，是真实的时钟偏差。
    maxAbsSkewAudioMs: upState.maxAbsSkewAudioMs,
    skewAudioP50: pcta(0.50), skewAudioP95: pcta(0.95),
    skewAudioP99: pcta(0.99),
    skewAudioFirst: ska.length ? ska[0] : null,
    skewAudioLast: ska.length ? ska[ska.length - 1] : null,
    skewAudioSamples: ska.length,
    skewAudioSpikes: upState.skewAudioSpikes.slice(-200),
    nSkewAudioSpikes: upState.skewAudioSpikes.length,
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
    if (vt && VIDEO_ENABLED) await attachVideoTrack(vt);
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
  // ★★★ EXT-020：这里**不再硬编码 1.0**。
  //   旧写法 `origGain.gain.value = 1.0` ⇒ popup 的「原声压低量」是死控件。
  //   ⇒ 改为按用户设的 duckDb 算增益（见 applyDuckDb）。
  applyDuckDb();
  origSource.connect(origDelay);
  origDelay.connect(origGain);
  origGain.connect(audioCtx.destination);
  // ★ 原声 onset 检测（唇音同步参考点）
  makeOnsetDetector(origGain, onOrigOnset, 0.02).then(n => { origOnsetNode = n; });
}

/**
 * ★★ EXT-020：把「原声压低量（dB）」真正应用到原声总线上。
 *
 * dB → 线性增益：gain = 10^(dB/20)。
 *   0 dB   ⇒ 1.0      （不压低）
 *   -15 dB ⇒ 0.1778   （≈ −15 dB）
 *   -60 dB ⇒ 0.001    （几乎听不见）
 *
 * ⚠️ **抓流前设置也要能生效**：origGain 是抓流成功后才建的
 *   （setupOriginalAudio 在 startCapture 里被调用）。
 *   ⇒ 设置在 origGain 建好之前也要**记住**，等 origGain 存在时立刻套用
 *   （applyDuckDb 同时被 setupOriginalAudio 和设置变更调用）。
 */
function dbToGain(db) {
  const n = Number(db);
  if (!isFinite(n)) return 1.0;
  // 面板限制在 [-60, 0]；这里再兜一层，防止越界值把增益放大到削波。
  const clamped = Math.max(-60, Math.min(0, n));
  return Math.pow(10, clamped / 20);
}

function applyDuckDb() {
  const gain = dbToGain(duckDb);
  if (origGain) {
    try {
      origGain.gain.value = gain;
      duckDbApplied = duckDb;
    } catch (e) { /* ignore */ }
  }
  metrics.duckDb = duckDb;
  metrics.duckGain = Math.round(gain * 10000) / 10000;
  metrics.duckDbApplied = duckDbApplied;
  return gain;
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

        // ★★ 限速判断**前置**（真实缺陷，实测 v6 证据）：
        //   旧顺序是「先 drawImage 缩放，再判断要不要编码」
        //   ⇒ 被限速丢弃的那一半帧（源 30 fps → 编码 15 fps）
        //     **照样做了一次 1908×1072 的全尺寸缩放**，然后被扔掉。
        //   ⇒ 纯浪费。CDP CPU Profile（v6，300 s）：
        //       drawImage self time = **17.35 s**（非 idle 第 1 名）
        //     其中约一半来自「缩放完就丢」的帧。
        //   ⇒ 现在**先判限速，被丢的帧直接 close，不做缩放**。
        //
        // ★ 编码限速的原因：源 30 fps，但本机 VP8 软件编码实际只有 ~18 fps
        //   ⇒ 旧逻辑（每帧都 encode）会把编码器灌爆 ⇒ 编码队列积压
        //   ⇒ 解码端在某一刻**突发**吐出几十帧 ⇒ 主线程一次性 drawImage
        //     几十次 ⇒ 500 ms 级 stall（实测 stall.maxMs=531 ≈ maxAbsSkew=534）。
        //   ⇒ 限到 ENCODE_FPS fps（低于实测吞吐 ⇒ 编码器永不积压）。
        const minIntervalUs = 1e6 / ENCODE_FPS;
        const encReady = videoEncoder && videoEncoder.state === 'configured';
        // ★ encodeQueueSize 守卫（浏览器规范 API）：编码器内部队列积压时
        //   直接丢帧，比等 output 回调再丢更早、更准。
        const encBacklogged = encReady && (videoEncoder.encodeQueueSize || 0) > ENCODE_QUEUE_MAX;
        if (!encReady || encBacklogged || (tsUs - lastEncTs < minIntervalUs)) {
          metrics.encodeSkipped = (metrics.encodeSkipped || 0) + 1;
          if (encBacklogged) metrics.encodeBacklogSkipped = (metrics.encodeBacklogSkipped || 0) + 1;
          frame.close();
          continue;
        }

        // ★ 统一走 OffscreenCanvas 缩放到编码尺寸（尺寸/格式不一致都会让编码失败）
        //   ⇒ OffscreenCanvas **复用**（不再每帧 new）：
        //   实测 5 分钟长测 `program` self time = 11.32 s、GC = 11.53 s，
        //   每帧 new OffscreenCanvas(1908×1072) ⇒ 每帧一次 8 MB 显存分配 + GC 压力。
        //   （v6 复测：GC 已从 11.53 s 降到 0 ⇒ 复用生效。）
        if (!encCanvas) {
          encCanvas = new OffscreenCanvas(encSize.w, encSize.h);
          encCtx = encCanvas.getContext('2d', { alpha: false });
        }
        encCtx.drawImage(frame, 0, 0, encSize.w, encSize.h);
        frame.close();

        lastEncTs = tsUs;
        const out = new VideoFrame(encCanvas, {
          timestamp: tsUs, duration: Math.round(1e6 / ENCODE_FPS),
        });
        // ★ 首帧强制关键帧（decoderConfig 只在关键帧的 meta 里出现）
        const keyFrame = metrics.encoded === 0 || (metrics.encoded % 60) === 0;
        try {
          videoEncoder.encode(out, { keyFrame });
        } catch (e) {
          metrics.encodeError = String(e);
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
  'schedClamped', 'probeSchedClamped', 'encodeSkipped', 'encodeBacklogSkipped',
  // ★★ EXT-020：把设置的实际生效值也带上去（跨上下文可见）
  'duckDb', 'duckGain', 'duckDbApplied', 'subsOn',
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

// ★ 高频事件的 report 节流。
//   真实缺陷：bridge 回声模式每帧回灌一条 echo（≈47 条/秒），
//   每条都 report() ⇒ 47 次/秒的 chrome.runtime.sendMessage 跨上下文往返，
//   且下游 offscreen 每条都落盘 ⇒ 主线程周期性阻塞 ⇒ 采样时钟尖峰。
//   ⇒ 高频 kind（dub/sched/...）合并到 1 秒一次；
//     关键事件（capture/错误）仍**立即**上报，不被节流。
const REPORT_THROTTLE_MS = 1000;
const REPORT_LOW_PRIORITY = new Set(['dub', 'sched', 'lipsync', 'metrics']);
let reportTimer = null;
let reportPending = null;

function flushReport() {
  reportTimer = null;
  const obj = reportPending;
  reportPending = null;
  if (!obj) return;
  try {
    chrome.runtime.sendMessage({ target: 'sw', cmd: 'metrics',
                                metrics: reportSummary(obj) });
  } catch (e) { /* ignore */ }
}

function report(obj) {
  window.__extMetrics = window.__extMetrics || {};
  if (obj && obj.kind) window.__extMetrics[obj.kind] = obj;
  window.__extMetrics.last = obj;

  const kind = obj && obj.kind;
  if (!REPORT_LOW_PRIORITY.has(kind)) {
    // 关键事件立即上报
    try {
      chrome.runtime.sendMessage({ target: 'sw', cmd: 'metrics',
                                  metrics: reportSummary(obj) });
    } catch (e) { /* ignore */ }
    return;
  }

  // 高频事件：合并（只保留最后一条），1 秒写一次
  reportPending = obj;
  if (reportTimer !== null) return;
  reportTimer = setTimeout(flushReport, REPORT_THROTTLE_MS);
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
// ★ 主线程 stall 探针（event-loop lag）
// ══════════════════════════════════════════════════════════════
/**
 * 测量**主线程事件循环延迟**：用 setTimeout(0) 反复探测，
 * 每次「计划时刻 → 实际回调时刻」的差值 = 主线程被阻塞的时长。
 *
 * ★ 为什么要它：5 分钟长测实测 maxAbsSkew 676.9 ms，而
 *   采样时钟本身是准的（drift ≈ 1 ms/min、P50=18 ms、P95=29 ms）。
 *   skew 尖峰的形态是「一串等差数列，步长恰好 = 帧长（21.25 ms）」，
 *   典型症状是「主线程停摆 → 消息积压 → 恢复后一次性冲刷」。
 *   ⇒ 尖峰的**因**是主线程阻塞，skew 只是**果**。
 *   没有 event-loop lag 探针就只能靠猜 ⇒ 这里补上，
 *   让「谁在阻塞主线程」变成可测量、可归因的事实。
 */
const stall = {
  last: 0, max: 0, n: 0, samples: [], worst: [],
};
function stallProbe() {
  const planned = performance.now();
  setTimeout(() => {
    const lag = performance.now() - planned;
    stall.last = lag;
    stall.n++;
    if (lag > stall.max) stall.max = lag;
    if (lag > 50) {
      stall.samples.push({ tRelMs: Math.round(planned - upState.t0), lagMs: Math.round(lag * 100) / 100 });
      if (stall.samples.length > 2000) stall.samples.shift();
    }
    stallProbe();
  }, 0);
}

// ★ longtask 观察器：把「谁在阻塞主线程」变成**归因数据**。
//   PerformanceObserver('longtask') 给出每个 >50 ms 长任务的
//   attribution（containerType / scriptURL / functionName）。
//   ⇒ 与 stall 探针配合：stall 给出「阻塞了多久」，longtask 给出「被谁阻塞」。
const longTasks = [];
let longTaskObserver = null;
function startLongTaskObserver() {
  if (longTaskObserver || typeof PerformanceObserver === 'undefined') return;
  try {
    longTaskObserver = new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        const a = e.attribution && e.attribution[0];
        longTasks.push({
          tRelMs: Math.round((e.startTime - (upState.t0 || 0))),
          durMs: Math.round(e.duration * 100) / 100,
          containerType: a ? a.containerType : null,
          containerSrc: a && a.containerSrc ? String(a.containerSrc).split('/').pop() : null,
          fn: a ? a.name : null,
        });
        if (longTasks.length > 500) longTasks.shift();
      }
    });
    longTaskObserver.observe({ entryTypes: ['longtask'] });
  } catch (e) { /* ignore */ }
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
    // ★ EXT-009：自适应加速的当前状态（供测试钩子/探针读取）
    adaptSpeed: metrics.adaptSpeed,
    adaptLagSec: metrics.adaptLagSec,
    adaptLagPeak: metrics.adaptLagPeak,
    adaptSpeedHistory: metrics.adaptSpeedHistory.slice(-100),
    uplink: uplinkSnapshot(),
    stall: {
      lastMs: Math.round(stall.last * 100) / 100,
      maxMs: Math.round(stall.max * 100) / 100,
      n: stall.n,
      spikes: stall.samples.slice(-200),
      nSpikes: stall.samples.length,
      longTasks: longTasks.slice(-100),
      nLongTasks: longTasks.length,
    },
  }),
  setDelay: (d) => { delaySec = d; },
  // ★★ EXT-020：暴露设置相关的可测状态（自测与诊断用）。
  settings: () => ({
    duckDb,
    duckGain: metrics.duckGain,
    duckDbApplied,
    duckGainApplied: origGain ? origGain.gain.value : null,
    subsOn,
    metricsSubsOn: metrics.subsOn,
    subsQueued: subs.length,
  }),
  dbToGain,
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
  /** P0③ 自测：直接排程一段 PCM，测浏览器端排程误差（probe=true ⇒ 与回声排程分开统计） */
  selfTestSchedule: (pcmB64, tStart) => scheduleDub({ id: 'selftest', t_start: tStart, pcm24k: pcmB64, probe: true }),
  /** ★ 诊断：排程与配对的完整明细（归因 P0③ 的误差来源） */
  schedDebug: () => ({
    pendingSched: pendingSched.map((p) => ({
      id: p.id, planned: p.planned, requested: p.requested,
      matched: p.matched, probe: p.probe,
    })),
    schedDetail: metrics.schedDetail.slice(-50),
    onsetErrs: metrics.onsetErrs.slice(-50),
    dubOnsets: metrics.dubOnsets.slice(-50),
    t0, now: audioCtx ? audioCtx.currentTime : 0, delaySec,
  }),
};

// ══════════════════════════════════════════════════════════════
// 启动
// ══════════════════════════════════════════════════════════════
async function boot() {
  const cfg = await chrome.storage.local.get({
    wsUrl: 'ws://127.0.0.1:8765/', token: '', delaySec: 10,
    // ★★ EXT-020：把 duckDb / subsOn 一并读出来（此前只有 popup 读，
    //   player 从不读 ⇒ 两个控件都是死控件）。
    duckDb: -15, subsOn: true,
  });
  delaySec = isNaN(D_OVERRIDE) ? (cfg.delaySec || 10) : D_OVERRIDE;
  // ★★ EXT-020：应用原声压低量与字幕开关。
  duckDb = (cfg.duckDb === undefined || cfg.duckDb === null || cfg.duckDb === '')
    ? -15 : Number(cfg.duckDb);
  subsOn = (cfg.subsOn === undefined || cfg.subsOn === null) ? true : !!cfg.subsOn;
  applyDuckDb();     // origGain 还不存在 ⇒ 只记录意图，等抓流后自动套用
  metrics.subsOn = subsOn;

  // ★★ EXT-020：运行中改设置也要生效（用户在 popup 改了压低量/字幕，
  //   不用重启窗口）。
  //   ⇒ 监听 chrome.storage.onChanged ⇒ 只认自己关心的两个键。
  try {
    if (chrome.storage && chrome.storage.onChanged) {
      chrome.storage.onChanged.addListener((changes, area) => {
        if (area !== 'local' || !changes) return;
        if ('duckDb' in changes) {
          const v = changes.duckDb.newValue;
          duckDb = (v === undefined || v === null || v === '') ? -15 : Number(v);
          applyDuckDb();
          report({ kind: 'settings', duckDb, duckGain: metrics.duckGain,
                   duckDbApplied: duckDbApplied });
        }
        if ('subsOn' in changes) {
          const v = changes.subsOn.newValue;
          subsOn = (v === undefined || v === null) ? true : !!v;
          metrics.subsOn = subsOn;
          report({ kind: 'settings', subsOn });
        }
      });
    }
  } catch (e) { /* ignore */ }

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
  // ★ probe 专用总线 + **独立** onset 检测器（隔离回声干扰）
  probeBus = audioCtx.createGain();
  probeBus.gain.value = 1.0;
  probeBus.connect(audioCtx.destination);
  try {
    onsetNode = await makeOnsetDetector(dubBus, onDubOnset, 0.02);
  } catch (e) {
    report({ kind: 'onset_error', error: String(e) });
  }
  try {
    probeOnsetNode = await makeOnsetDetector(probeBus, onDubOnset, 0.02);
  } catch (e) {
    report({ kind: 'probe_onset_error', error: String(e) });
  }

  setInterval(() => { pumpDecoder(); pumpDraws(); pumpSubs(); updateHud(); }, 40);
  setInterval(() => {
    computeLipSync();
    report({ kind: 'metrics', ...metrics, queued: encQueue.length });
  }, 1000);

  // ★ 主线程 stall 探针（定位 skew 尖峰的真正阻塞源）
  stallProbe();
  startLongTaskObserver();

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
  // ★ EXT-009：底栏显示当前语速倍率与滞后秒数
  set('mSpeed', (m.adaptSpeed == null ? 1.0 : m.adaptSpeed).toFixed(2));
  set('mLag', (m.adaptLagSec == null ? 0 : m.adaptLagSec).toFixed(1));
  set('mLagPeak', (m.adaptLagPeak == null ? 0 : m.adaptLagPeak).toFixed(1));
}

boot();
