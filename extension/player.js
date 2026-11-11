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
  // ★★ EXT-027①：**实际用的抓流方式**（'tabCapture' | 'getDisplayMedia'）。
  //   如实上报，绝不写死（写死会让 reviewer 无法核对「抓的是不是页面自己的声音」）。
  captureMode: null,
  echoRecv: 0, echoSent: 0,
  // ★★★ EXT-041：**媒体降速**（`playbackRate`）的**实测**记录。
  //   * `enabled`   —— 用户是否开着这个开关；
  //   * `rate`      —— 实际设上去的倍率（没设成功就是 null，**不臆造**）；
  //   * `applied`   —— 是否真的作用到了媒体元素上（页面里没 <video> ⇒ false）；
  //   * `recommended` —— 服务端建议的倍率（从 /status 拿；没有就是 null）。
  //   ⚠️ 这几个字段会被 `reportClientMetrics()` 上报给服务端
  //     ⇒ 落盘到 `margin.json:slowdown` ⇒ reviewer 可核对「降了多少」。
  slowdown: null,
  slowdownEnabled: true,
  slowdownRecommended: null,
  // ★★★ EXT-026 ③：被当作「重复段」静默丢掉的次数（EXT-024 A 去重命中）。
  //   ★ 必须**如实计数** —— 它是「段被丢了」的**唯一**可观测证据
  //     （EXT-026 ⑤ 的跨会话撞号缺陷就是靠它暴露的）。
  dubDup: 0,
  // ★★★★ EXT-028 ①：PCM 采样率的**可观测性**。
  //   `pcmRateLast`      —— 最近一次排程实际用的采样率（Hz）；
  //   `pcmRateAssumed`   —— 服务端**没带** `sample_rate`、靠兜底猜的次数
  //                        （>0 ⇒ 连的是**老服务端** ⇒ 采样率可能不对）。
  pcmRateLast: null,
  pcmRateAssumed: 0,
  // ★★★★★ EXT-027 ⑤：因「上一句还没播完」而被顺延的次数/累计顺延秒数。
  //   （>0 ⇒ 曾经**叠播**；现在是**不叠播**，但顺延量会计入 lag。）
  dubRescheduled: 0,
  dubRescheduleDelaySec: 0,
  onsetErrs: [], lipErrs: [], schedDetail: [],
  drawMarks: [], origOnsets: [], dubOnsets: [],
  // ★★★ EXT-033 D：**player 端实测的「有符号」同步误差**。
  //   `dubSyncErrs`  —— 每句配音的 signedErrMs（实际起播 − (t0+t_start+D)）
  //                     ⇒ **可为负**（早播）—— EXT-032 用的
  //                     `max(0, TTS就绪 − 截止时刻)` 永远 ≥ 0 ⇒ 恒为 0，
  //                     根本量不出「早播」，口径是错的。
  //   `dubSyncDetail` —— {id, tStart, requested, actual, signedErrMs, lateMs}
  //   `dubSyncLateMs` —— 「迟到量」（单独列，**不代替** signedErrMs）
  //
  // ★★★★★ EXT-034 ①：主口径换成「**覆盖全部段**」的排程起点。
  //   `dubSyncErrs`      —— **主口径**：每段**一条**（startSource='sched'）
  //   `dubSyncErrsOnset` —— **onset 口径**（毫秒级，但可能缺段 ⇒ 只作补充）
  //   `dubSyncDetail`    —— 每段一条，含 `startSource` 标明来源
  //   ⚠️ 旧实现把 onset 的结果**直接**推进 `dubSyncErrs`/`dubSyncDetail`
  //   ⇒ 段数取决于「onset 碰巧配没配上」（实测 13 段只进 7 段）
  //   ⇒ P50/P95 只算了子集（EXT-034 ① 的真缺陷）。
  dubSyncErrs: [], dubSyncDetail: [], dubSyncLateMs: [],
  dubSyncErrsOnset: [],
  dubSyncP50: null, dubSyncP95: null, dubSyncMax: null, dubSyncMin: null,
  // ★★★ EXT-033 D：时间轴原点的**口径**（必须能自证，不能默认）。
  //   `t0Axis`       —— 'audio_clock'（用音频时钟反推，正确）
  //                   | 'page_init'（页面初始化时刻，**旧口径、已弃用**）
  //   `t0Sec`        —— 当前 t0 的值（秒）
  //   `t0Offset16`   —— 抓流样本 0 在音频时钟（16 kHz 域）的位置
  //   `t0UpSec`      —— **上行域**的 t0（换算前的原值，便于自证）
  //   `t0UpPlayerOffsetSec` —— uplink↔player 两个 AudioContext 的原点差
  t0Axis: null, t0Sec: null, t0Offset16: null, t0OffsetSamples: 0,
  t0UpSec: null, t0UpPlayerOffsetSec: null, t0UpPlayerOffsetSpreadSec: null,
  captureStarted: false, audioCtxOk: false,
  // ★★ EXT-027①：抓流方式的**降级证据**。
  //   `captureMode` 只说「最后走了哪条路」，
  //   这两个字段说明「**为什么**降级」⇒ 排查时不必猜。
  captureModeDetail: null,   // 'tabCapture' | 'getDisplayMedia'
  tabCaptureError: null,     // tabCapture.capture 抛出的原文（没失败则 null）
  captureError: null,         // getDisplayMedia 抛出的原文
  // ★ EXT-009：自适应加速播放的当前状态（底栏显示）
  //   speed     —— 当前句采用的语速倍率（1.00 ~ 1.30）
  //   lagSec    —— 当前句的滞后秒数（实际开播 − 目标开播）
  adaptSpeed: 1.0, adaptLagSec: 0, adaptLagPeak: 0,
  adaptSpeedHistory: [],       // {id, speed, lagSec, at}
  adaptTotalSpeed: 1.0,        // 时长适配 × 自适应加速 的总倍率
  // ★★ T-3：原声压低量与字幕开关的**实际生效值**
  //   （不是用户设的值 —— 用来核对「设了到底有没有生效」）。
  duckDb: null,          // 用户设的 dB
  duckGain: null,        // 由 dB 换算出的线性增益
  duckDbApplied: null,   // 已真正套到 origGain 上的 dB（未抓流时为 null）
  subsOn: true,          // 字幕开关是否开启
  // ★★ EXT-024 E：链路状态（**常驻状态条**要显示的 5 个计数 + 滞后）
  //   ⚠️ 全部**如实计数**，绝不臆造：没收到就是 0。
  link: {
    wsConnected: false,      // WS 是否连上
    wsError: null,           // 连接失败的原因
    mode: null,              // 'real'（真实引擎） / 'echo'（回声）
    enginesReady: false,     // 引擎是否就绪
    pipeline: false,         // 是否流水线
    audioRecvSec: 0,         // 已收上行音频秒数
    asrSegments: 0,          // 服务端报的 ASR 段数
    mtSegments: 0,           // 服务端报的 MT 段数
    ttsSegments: 0,          // 服务端报的 TTS 段数
    dubDelivered: 0,         // **本端已下发到 player 的段数**（收到 tts 的次数）
    lagSec: null,            // 当前滞后（秒）
    // ★ 各环节「最后一次有动静」的墙钟时刻（performance.now()）
    //   ⇒ 用来判断「某一环为 0 超过 15 s」并给出**具体原因**。
    lastAudioAt: null,
    lastTtsAt: null,
    lastStatsAt: null,
    startedAt: null,
  },
};

// ★ EXT-009：自适应加速播放的**统一参数**
//   （与 App 一致；服务端 `ext/adaptive_speed.py` 是权威实现，
//     这里只做播放侧的应用与显示）
const ADAPT = {
  lagFreeSec: 3.0,      // lag ≤ 3 s ⇒ 1.0×
  lagHystSec: 2.0,      // 降速滞回门槛
  gainPerSec: 0.025,    // 每秒滞后的加速系数
  speedMax: 1.50,       // 上限（11-08 用户定 1.5×，与 ext/config.py 一致）
  maxStep: 0.10,        // 相邻句变化上限
};

// ── 全局时钟：画面与原声共用同一个 AudioContext ────────────────
let audioCtx = null;
let t0 = 0;
// ★★★ EXT-033 D：**时间轴原点的正确口径**。
//
// ## 旧口径（EXT-032 用过的）为什么是错的
//   `t0 = audioCtx.currentTime`（**页面初始化时刻**），
//   而服务端下发的 `t_start` 是**上行首帧**为原点的音频时间轴。
//   ⇒ 两个原点差了「页面初始化 → 抓流真正开始」这一段（本机实测 ~4~5 s）
//   ⇒ `planned = t0 + t_start + D` **整体偏早** ⇒ 排程被钳到「立即播」
//   ⇒ EXT-032 的时间轴不真实（reviewer 的第 1 条批评）。
//
// ## 新口径
//   抓流样本 0 在**音频时钟**上的位置 = `sampleIndex − audioFrame16`
//   （两者都是 16 kHz 域、都是硬件时基）⇒
//   `t0 = (sampleIndex − audioFrame16) / 16000`
//   ⇒ `t0 + t_start` 才真的落在 AudioContext 时间轴上。
//   ★ 取前 N 帧的**中位数**（首帧有启动瞬态，中位数更稳）。
//
// ★★★★★ EXT-033 D 修正（真实三引擎实测抓到的**跨时钟域**缺陷）：
//   `audioFrame16` 来自**上行 AudioContext**（`upState.ac`，player.js:1364 创建），
//   而 `planned` / `src.start(when)` / onset 的 `at` 全在
//   **player AudioContext**（`audioCtx`，player.js:2582 创建）的时间轴上。
//   两个 AudioContext 的**原点互相独立**（各自从 0 开始计时），
//   ⇒ 直接把 uplink 域算出的 t0 当成 player 域的时刻 ⇒ **系统性偏差**。
//
//   实测证据（run 20261102_121431，真实三引擎）：
//     `t0Sec = -0.0197`（uplink 域）⇒ `requested` 首段 = 9.98 s，
//     而 player 实测首段实际起播 = 29.93 s ⇒ signedErr = **+19.95 s**；
//     `metrics.schedClamped = 13` ⇒ **13 段全部**被钳成「立即播」
//     ⇒ 有符号误差**恒为正**，量不出「早播」—— 这正是 EXT-032 批评的口径问题。
//
//   ## 修法：在 **player 域**内建立 uplink↔player 的偏移
//   同一时刻、两个 context 的 `currentTime` 之差 = 常量偏移 `Δ`：
//     Δ = upState.ac.currentTime − audioCtx.currentTime
//   ⇒ 上行域的「抓流样本 0 时刻」`t0_up` 换算到 player 域：
//     `t0_player = t0_up + Δ`
//   ★ Δ 在两个 context 都 running 时采样，取中位数更稳。
//   ★ 保留 `t0_up` 原值到 metrics，便于自证换算前后的差异。
//
// ★★★★★★ EXT-036 ①：**上面那个换算公式的符号是错的**（真缺陷）。
//
// ## 为什么错
//   `t0_up` 的定义 = 「**上行 AudioContext 的时钟上**，抓流样本 0 的时刻」。
//   `Δ = up.ac.currentTime − player.ac.currentTime` 的定义 =
//     「**同一真实时刻**，上行时钟读数 − player 时钟读数」。
//   ⇒ 要把「上行时钟上的某个时刻」换算成「player 时钟上的同一时刻」，
//     必须**加上** Δ：
//         t_player = t_up + Δ
//   ★★ **但 `t0_up` 本身算出来就是负数！**
//     `t0_up = (sampleIndex − audioFrame16) / 16000`
//     —— 抓流样本 0 对应的**音频时钟位置**通常**早于**该 context
//        的 `currentTime`（worklet 是启动后才拿到第一个音频块的）
//     ⇒ `sampleIndex − audioFrame16` 为负 ⇒ `t0_up` 为负
//     （实测 `t0UpSec = −0.0197 s`）。
//
// ## 实测证据（reviewer EXT-036 ① 的「恒定 ~7 s 缺口」）
//   run 20261102_213515：
//     `t0UpSec = −0.0197`｜`t0UpPlayerOffsetSec = −3.3893`
//     ⇒ 旧公式 `t0 = t0_up + Δ = −3.4091`（**负数**）
//     ⇒ 但 `t0` 的语义是「**抓流样本 0 在 player 域的时刻**」
//        ⇒ 它**必须 ≥ 0**（样本 0 不会出现在 player 域的负时刻）
//     ⇒ 正确值 = `−t0_up − Δ`？**不是**。
//   ⇒ 真正的问题在 **`Δ` 的定义方向**：
//     `Δ = up.ac.currentTime − player.ac.currentTime`
//     若上行 context **先**启动（它是在 `startUplink()` 里建的），
//     则同一真实时刻 `up.ac.currentTime > player.ac.currentTime`
//     ⇒ Δ > 0。
//     实测 Δ = **−3.3893 < 0** ⇒ 说明 **player context 更早启动**。
//   ⇒ 于是「上行时钟上的 t0_up」要换算到 player 时钟：
//         t_player = t0_up − Δ
//     实测 = `−0.0197 − (−3.3893)` = **+3.3696 s** ✅（≥ 0，自洽）
//
// ## 后果（旧公式错在哪）
//   旧：`t0 = t0_up + Δ = −3.4091`（**符号反了**，且少了 0.0197）
//   ⇒ `planned = t0 + t_start + D` **整体偏早 6.818 s**
//   ⇒ 每段配音都被排到「早已过去的时刻」⇒ 被钳成「立即播」
//   ⇒ **播放端与服务端的时间轴差了一个常量 6.818 s**
//   ⇒ 这正是 reviewer 实测到的「server→player 恒定约 7 s 缺口」
//     （6.84–7.82 s，14 段全落在这个区间，且**不随时间增长**⇒
//      不是积压、不是下行慢，就是**轴对不上**）。
//
// ## 修法
//   `t0 = t0_up − Δ`（Δ 的定义是「上行读数 − player 读数」）
//   ⇒ 换算方向与 Δ 的定义**一致** ⇒ 不可能再差一个常量。
//   ★ 保留 `t0UpSec` / `t0UpPlayerOffsetSec` 到 metrics ⇒ 可自证。
const T0_OFFSET_FRAMES = 60;
const t0OffsetCandidates = [];
let t0Established = false;
let t0Src = null;          // 11-08: 配音排程用的 t0（上行样本直接测得）
let dubSyncLogAt = 0;
function dubT0() { return (t0Src == null) ? t0 : t0Src; }
// ★ uplink↔player 两个 AudioContext 的原点差（秒，player 域表示）。
let upToPlayerOffsetSec = null;
const upToPlayerCandidates = [];

/** 把候选偏移（16 kHz 域）取中位数 ⇒ 得到 t0（秒）。 */
function _median(nums) {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
let delaySec = 20;
let ws = null;
let lipSyncData = null;
let capturedStream = null;

// ★★ T-3：popup 的「原声压低量」与「字幕开关」此前是**死控件**
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
// ★★ T-4：面板上的**目标语言**与**音色**。
//   此前 player.js **从不读**这两个设置 ⇒ 在 player 这条上行链路上
//   服务端拿不到它们 ⇒ 面板上的选择在这条路径上**完全丢失**。
//   ⇒ 现在读出来，随 hello 上报（⇒ 服务端真正用它翻译/合成）。
let targetLang = null;
let voicePref = null;

// ★★ T-4：语言 / 音色的归一化（与 popup.js 同一口径）。
//   ⚠️ popup.js 里也有同名函数 —— 两边**必须**保持一致，
//     否则会出现「popup 显示日语、player 上报英语」这类不一致。
//   ★ 语言白名单 = 引擎只认的 4 种（zh/en/ja/ko）；
//     老配置里的语言**全称**（Chinese/English/…）自动迁移成引擎码。
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

// ══════════════════════════════════════════════════════════════
// ★★ EXT-024 E：常驻**链路状态条**
// ══════════════════════════════════════════════════════════════
/**
 * ## 为什么需要（用户 10-31 实测）
 *   用户只看到「延迟原声、没有配音没有字幕」，但**界面上一句话都没有**
 *   ⇒ 既不知道卡在哪一环，也不知道该去看哪个日志。
 *   ⇒ 现在：6 个计数常驻显示；任何一环 15 秒还是 0 ⇒ **红字写明原因**。
 *
 * ## 口径（务必与 reviewer 的验收一致）
 *   * 已收音频 x s —— 上行**音频时长**（不是帧数）；
 *   * ASR 段数 —— 服务端已定稿的段数；
 *   * MT 段数 —— 服务端已翻译的段数；
 *   * TTS 段数 —— 服务端已合成出音频的段数；
 *   * 已下发到 player 段数 —— **player 这一端实际收到的 tts 消息数**
 *     （★ 这是 EXT-024 A 的关键证据：只有它 > 0 才说明下行通了）；
 *   * 当前滞后 —— 排程滞后秒数（EXT-009 的 adaptLagSec）。
 *
 * ⚠️ 计数器本体在 `metrics.link`（见上面的定义）⇒
 *   `report()` 的标量白名单里也有它们 ⇒ 跨上下文可读。
 *
 * ⚠️ **实现位置**：判定逻辑在文件末尾的 `diagnoseLink()`（纯函数）
 *   ⇒ 可被 node 沙箱 harness 直接验证；本节只保留口径说明。
 */

/** 音色只有两个合法值：`A`（预设 A）与 `clone`（克隆说话人）。 */
function normalizeVoice(v) {
  const k = String(v == null ? '' : v).trim().toLowerCase();
  return (k === 'clone') ? 'clone' : 'A';
}

// ══════════════════════════════════════════════════════════════
// P0②：WebCodecs 延迟画面管线
// ══════════════════════════════════════════════════════════════
const encQueue = [];      // 已编码块环形缓冲 {chunk, tsUs}
// 11-06 (reviewer): ring must hold D + headroom of *encoded* frames, otherwise at
//   D=20 s / ENCODE_FPS=15 it is exactly full and the head (incl. key frames) gets
//   dropped => decoder breaks / picture freezes.  Recomputed whenever D changes.
let ENC_CAP = 300;
function recomputeEncCap() {
  const d = (typeof delaySec === 'number' && delaySec > 0) ? delaySec : 20;
  ENC_CAP = Math.max(300, Math.ceil((d + 10) * ENCODE_FPS * 1.5));
  metrics.encCap = ENC_CAP;
}
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
// ★★★★★ EXT-027 ⑤：**已排程配音的最晚结束时刻**（AudioContext 时钟）。
//   用途：保证两句配音**不叠播** —— 后一句的 `when` 必须 ≥ 本值。
//   ⚠️ 只统计**真实配音**（probe 自测不计入，见 scheduleDub）。
let dubPlaybackEnd = 0;
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

// ★★★ EXT-026 ③：**配音录音**（录 player **实际播出**的音频）。
//   为什么必须录「播出来的」而不是服务端的 PCM：
//   服务端 PCM 只证明「服务端算出了音频」⇒ 不能证明
//   「浏览器真的把它播出来了」（排程/增益/总线接错都会导致静音）。
//   ⇒ 在 **dubBus**（配音输出总线）上挂一个 MediaStreamDestination，
//     用 MediaRecorder 录下来 ⇒ reviewer 回转写就能核对中文内容。
// ⚠️ 只接 dubBus（不接 origGain）⇒ 录到的**只有配音**，没有原声。
let dubRecordStream = null;   // MediaStreamDestination 的 stream
let dubRecorder = null;       // MediaRecorder 实例
let dubRecordChunks = [];     // 录到的数据块
let dubRecordStartedAt = 0;   // 开始录制的墙钟时刻（ms)
// ★★★★★★ EXT-036 ⑤：恒定零信号源（`ConstantSourceNode`）
//   挂在 `MediaStreamDestination` 上 ⇒ 录音**永远有输入**
//   ⇒ 没有配音时**时间轴不压缩**（webm 与 WAV 两个问题一起解决）。
let dubSilentSource = null;

// ★★★ EXT-033 B：**无损 PCM 抓取**（wav 的来源）。
//   `dubPcmNode`     —— AudioWorkletNode（'dub-pcm-processor'），并联在 dubBus 上
//   `dubPcmSink`     —— gain=0 的 sink ⇒ 这条支路**静音**（不重复出声）
//   `dubPcmChunks`   —— 抓到的 Float32 块
//   `dubPcmRate`     —— AudioContext 的采样率（本机 48 kHz）
//   `dubPcmActive`   —— 是否正在采集
//   `dubRecordStartAc` —— 开始录音时的 AudioContext 时刻（与 WAV 对齐的时间原点）
let dubPcmNode = null;
let dubPcmSink = null;
let dubPcmChunks = [];
let dubPcmRate = 0;
let dubPcmActive = false;
let dubRecordStartAc = 0;
let dubPcmBytes = 0;
let dubPcmDumpDone = false;   // ★ worklet 是否已把整段 PCM 投上来

/** ★ 把 Float32 PCM 打包成 WAV（16-bit PCM）⇒ base64。 */
function pcmToWavBase64() {
  let total = 0;
  for (const c of dubPcmChunks) total += c.length;
  const rate = dubPcmRate || 48000;
  const nCh = 1;
  const bits = 16;
  const byteRate = rate * nCh * bits / 8;
  const blockAlign = nCh * bits / 8;
  const dataBytes = total * 2;
  const buf = new ArrayBuffer(44 + dataBytes);
  const dv = new DataView(buf);
  const wr = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
  wr(0, 'RIFF'); dv.setUint32(4, 36 + dataBytes, true); wr(8, 'WAVE');
  wr(12, 'fmt '); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true);
  dv.setUint16(22, nCh, true); dv.setUint32(24, rate, true);
  dv.setUint32(28, byteRate, true); dv.setUint16(32, blockAlign, true);
  dv.setUint16(34, bits, true);
  wr(36, 'data'); dv.setUint32(40, dataBytes, true);
  let o = 44;
  for (const c of dubPcmChunks) {
    for (let i = 0; i < c.length; i++) {
      let s = c[i];
      if (s > 1) s = 1; else if (s < -1) s = -1;
      dv.setInt16(o, Math.round(s * 32767), true);
      o += 2;
    }
  }
  // base64（分块，避免超大字符串）
  const bytes = new Uint8Array(buf);
  let bin = '';
  const STEP = 0x8000;
  for (let i = 0; i < bytes.length; i += STEP) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + STEP));
  }
  return { b64: btoa(bin), bytes: bytes.length, rate: rate,
           samples: total, durationSec: total / rate };
}

/**
 * ★★★ EXT-026 ③：开始录制**实际播出的配音**。
 * @param {number} [maxMs] 最长录制时长（毫秒）—— 兜底，防忘记停。
 */
async function startDubRecording(maxMs) {
  if (!audioCtx || !dubBus) return { ok: false, error: '音频总线还没建好' };
  if (dubRecorder && dubRecorder.state === 'recording') {
    return { ok: true, already: true };
  }
  try {
    dubRecordChunks = [];
    // ★★★ EXT-033 B：PCM 抓取**与 webm 录音同时开始**（同一时间原点）。
    dubPcmChunks = [];
    dubPcmBytes = 0;
    dubPcmDumpDone = false;
    dubPcmActive = true;
    // ★ 采集开关**必须**送到 worklet 内部（主线程的标志位它看不到）
    try { if (dubPcmNode) dubPcmNode.port.postMessage({ cmd: 'start' }); }
    catch (e) { /* ignore */ }
    dubRecordStartAc = audioCtx.currentTime;
    const dest = audioCtx.createMediaStreamDestination();
    dubBus.connect(dest);          // ★ 只从 dubBus 取 ⇒ 录到的是配音
    // ★★★★★★ EXT-036 ⑤：**webm 也要有连续的时间轴**（否则同样被压缩）。
    //   ## 为什么 webm 也会被压缩
    //     `MediaStreamDestination` 只在**有输入**时才产出音频帧。
    //     没有配音时 `dubBus` 上**一个输入连接都没有**
    //     ⇒ dest **不产出任何帧** ⇒ MediaRecorder 收不到时间推进
    //     ⇒ webm 的时间轴同样被压缩（与 WAV 同一个病根）。
    //   ## 修法
    //     挂一个**恒定零信号**（`ConstantSourceNode`）到 dest
    //     ⇒ dest **永远有输入** ⇒ 时间轴连续 ⇒ webm 时长 = 实际经过的墙钟。
    //   ★ 信号值是 0 ⇒ **不改变**音频内容（只补时间轴）。
    //   ⚠️ ConstantSourceNode 必须**持续运行**（`start()` 一次即可）。
    try {
      const cs = audioCtx.createConstantSource();
      cs.offset.value = 0;
      cs.connect(dest);
      cs.start();
      dubSilentSource = cs;
    } catch (e) { /* ignore */ }
    dubRecordStream = dest.stream;
    const mime = (typeof MediaRecorder !== 'undefined')
      ? (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
         ? 'audio/webm;codecs=opus' : 'audio/webm') : '';
    dubRecorder = new MediaRecorder(dubRecordStream, mime ? { mimeType: mime } : undefined);
    dubRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) dubRecordChunks.push(e.data);
    };
    // ★★★ EXT-033 B：`timeslice` 分片收集（1000 ms 一片）
    //   ⇒ 录到一半崩了也还有已落盘的片，不会「全丢」。
    dubRecorder.start(1000);
    dubRecordStartedAt = performance.now();
    if (maxMs && maxMs > 0) {
      setTimeout(() => { stopDubRecording(); }, maxMs);
    }
    report({ kind: 'dub_record_start', mime: mime || 'default',
             acTimeSec: dubRecordStartAc, pcmRate: dubPcmRate });
    return { ok: true, mime: mime || 'default',
             acTimeSec: dubRecordStartAc, pcmRate: dubPcmRate };
  } catch (e) {
    report({ kind: 'dub_record_error', error: String((e && e.message) || e) });
    return { ok: false, error: String((e && e.message) || e) };
  }
}

/**
 * ★★★ EXT-033 B：**停止录音并保证文件完整**。
 *
 * ## 为什么要「等 onstop」
 *   `MediaRecorder.stop()` 只是**请求**停止：`dataavailable`（最后一块）与
 *   `onstop` 都是**异步**事件。
 *   ⇒ EXT-032 的旧写法是 `stop()` 之后**立刻**取 blob
 *     ⇒ 最后一块还没进 `dubRecordChunks` ⇒ 文件被截断
 *     ⇒ ffmpeg 报 `File ended prematurely at pos 86970`（EXT-033 第 1 条批评）。
 *
 * ## 两种用法
 *   * `stopDubRecording()`     —— 同步返回（兼容旧调用方），**不**等 onstop；
 *   * `stopDubRecordingAsync()` —— ★ **返回 Promise**，resolve 于 onstop 之后
 *     ⇒ 此时 `dubRecordChunks` 一定完整 ⇒ blob 一定完整。
 */
function stopDubRecording() {
  try {
    if (dubRecorder && dubRecorder.state !== 'inactive') {
      dubRecorder.stop();
    }
  } catch (e) { /* ignore */ }
  // ★ EXT-036 ⑤：停掉恒定零信号源（否则它会一直挂在图上）
  try {
    if (dubSilentSource) {
      dubSilentSource.stop();
      dubSilentSource.disconnect();
      dubSilentSource = null;
    }
  } catch (e) { /* ignore */ }
  return { durationSec: dubRecordStartedAt
    ? (performance.now() - dubRecordStartedAt) / 1000 : 0 };
}

/** ★ 等 `dataavailable` + `onstop` 都完成后再 resolve（EXT-033 B）。 */
function stopDubRecordingAsync() {
  return new Promise((resolve) => {
    const acNow = audioCtx ? audioCtx.currentTime : 0;
    const finish = () => resolve({
        durationSec: dubRecordStartedAt
          ? (performance.now() - dubRecordStartedAt) / 1000 : 0,
        acTimeSec: acNow,
        acStartSec: dubRecordStartAc,
        // ★★★ EXT-036 ⑤：**时间轴完整性**的两个可核对量。
        //   `acElapsedSec` = AudioContext 时钟上真正经过的时长
        //   `wavDurationSec` = PCM 样本数 ÷ 采样率
        //   ⇒ 两者的差 = **时间轴被压缩掉多少**（判据：≤0.2 s）
        acElapsedSec: acNow - dubRecordStartAc,
        wavDurationSec: dubPcmChunks.reduce((a, c) => a + c.length, 0)
          / (dubPcmRate || 48000),
        chunks: dubRecordChunks.length,
        chunkBytes: dubRecordChunks.reduce((a, c) => a + c.size, 0),
        pcmChunks: dubPcmChunks.length,
        pcmSamples: dubPcmChunks.reduce((a, c) => a + c.length, 0),
        pcmRate: dubPcmRate,
    });
    // ★ 通知 worklet 停止采集并**一次性**投递整段 PCM；
    //   然后**等到真的收到**再 resolve
    //   （固定 sleep 会漏掉大数组的传输 ⇒ WAV 尾部被削）。
    const done = () => {
      // ★ EXT-036 ⑤：停掉恒定零信号源（webm 的时间轴靠它保持连续）
      try {
        if (dubSilentSource) {
          dubSilentSource.stop();
          dubSilentSource.disconnect();
          dubSilentSource = null;
        }
      } catch (e) { /* ignore */ }
      try {
        if (dubPcmNode) {
          dubPcmDumpDone = false;
          dubPcmNode.port.postMessage({ cmd: 'stop' });
        }
      } catch (e) { /* ignore */ }
      const t0 = performance.now();
      const waitDump = () => {
        if (dubPcmDumpDone || (performance.now() - t0) > 8000) {
          dubPcmActive = false;
          finish();
          return;
        }
        setTimeout(waitDump, 50);
      };
      setTimeout(waitDump, 50);
    };
    if (!dubRecorder || dubRecorder.state === 'inactive') { done(); return; }
    const prev = dubRecorder.onstop;
    dubRecorder.onstop = (ev) => {
      if (typeof prev === 'function') { try { prev(ev); } catch (e) { /* ignore */ } }
      done();
    };
    try { dubRecorder.stop(); } catch (e) { done(); }
  });
}

/**
 * ★★★ EXT-026 ③：把录到的配音**打包成可下载的 blob**。
 *   返回 { mime, base64, bytes, durationSec }。
 *   ★ 用 base64 而不是二进制数组 ⇒ Playwright 直接取字符串即可落盘。
 */
function dubRecordingBlob() {
  if (!dubRecordChunks || !dubRecordChunks.length) {
    return { ok: false, error: '没有录到任何数据', bytes: 0 };
  }
  const blob = new Blob(dubRecordChunks, { type: dubRecordChunks[0].type || 'audio/webm' });
  return new Promise((resolve) => {
    const fr = new FileReader();
    fr.onload = () => {
      const b64 = String(fr.result || '');
      resolve({
        ok: true,
        mime: blob.type || 'audio/webm',
        bytes: blob.size,
        base64: b64,
        durationSec: dubRecordStartedAt
          ? (performance.now() - dubRecordStartedAt) / 1000 : 0,
      });
    };
    fr.onerror = () => resolve({ ok: false, error: 'FileReader 失败', bytes: 0 });
    fr.readAsDataURL(blob);
  });
}

/**
 * ★★★ EXT-033 B：**把抓到的 PCM 打包成 WAV**（无损）。
 *
 * ## 为什么必须另有 WAV（不能只交 webm）
 *   * webm/opus 是**有损**的 ⇒ 互相关峰 / SNR 的绝对值不可信；
 *   * webm 的容器边界不可控 ⇒ 「录音是否完整」没法用样本数自证；
 *   * WAV 可以**逐样本核对**：样本数 ÷ 采样率 = 时长，
 *     与 ffprobe 报的时长对照 ⇒ 截断立刻暴露。
 * ★ PCM 是从 **dubBus 并联的静音支路**抓的（AudioWorklet），
 *   不经过 MediaRecorder ⇒ 不受 onstop 竞态影响。
 */
function dubRecordingWav() {
  if (!dubPcmChunks.length) {
    return { ok: false, error: '没有抓到 PCM', bytes: 0 };
  }
  const w = pcmToWavBase64();
  // ★ 完整性证据：worklet 报告的「已存样本数 / 被丢弃样本数」
  //   ⇒ 与录音时长对照即可判断 WAV 是否被截断（EXT-033 B 的验收项）。
  return { ok: true, ...w,
           stored: metrics.dubPcmStored == null ? w.samples : metrics.dubPcmStored,
           dropped: metrics.dubPcmDropped == null ? 0 : metrics.dubPcmDropped };
}

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

// ★★★★★ EXT-034 ①：**每段配音的真实起播时刻**（不靠 onset 配对）。
//
// ## 为什么必须新增（reviewer EXT-034 ① 的真缺陷）
//   旧实现**只**在 `onDubOnset()` 里记录「实际起播」：
//     `signedErrMs = (at − requested) × 1000`
//   而 `at` 来自 onset 检测器（AudioWorklet 的**幅度阈值**触发）。
//   ⇒ 实测（run 20261102_121431）：13 段 TTS 只进了 **7** 段
//     `dubSyncDetail`，缺 128000/200480/252640/483840/590400/711840。
//   ⇒ 根因是**两重的**：
//     (a) **onset 配对被抢**：`onDubOnset` 找的是「最近的排程」
//         （`PAIR_WINDOW_SEC=0.25`）。但**下一段**的排程时刻可能离
//         本段的实际起播更近 ⇒ 重复 onset（迟滞抖动、minGap=50 ms
//         ⇒ 实测 dubOnsets 里出现 **50 ms 间隔的连续 onset**）
//         会把本段的排程**抢走** ⇒ 本段永远配不上。
//     (b) **onset 根本没触发**：TTS 是**中文语音**，开头常是
//         辅音/静音 ⇒ 阈值 0.02 未必触发 ⇒ 该段没有任何 onset。
//   ⇒ 于是 `dubSyncDetail` 变成「**碰巧配上的子集**」
//     ⇒ P50/P95 只算了子集（reviewer 明文批评）。
//
// ## 现在的做法（**不依赖 onset**）
//   ★ 每次 `scheduleDub()` 排程时，就**记下这一句将要播的起点**
//     （`when` = 实际排程时刻，已含钳位与顺延）。
//   ★ 再用 `AudioBufferSourceNode.onended` 拿**真实**结束时刻，
//     反推「实际起播 = 结束时刻 − 缓冲时长」。
//   ⇒ 每个**有 TTS 的段**都必然进 `dubSyncDetail`，
//     段数 = TTS 段数（EXT-034 验收：「dubSyncDetail 段数等于 TTS 段数」）。
//
// ## 为什么 `onended` 是可靠的（以及口径的诚实说明）
//   `onended` 只作为**「这句确实播完了」的触发器**（⇒ 每个有 TTS 的段
//   都必然被记录一次 ⇒ 段数 = TTS 段数）。
//   ★ 但 `actual` **不**用 `endedAt − dur` 反推：那样会把
//     「onended 回调的主线程调度延迟」（实测 10–40 ms）
//     **系统性地**当成同步误差 ⇒ 假偏差。
//   ★ `actual` 取 **`when`（排程即播放起点）** —— 这是 Web Audio 的
//     **语义精确值**：`AudioBufferSourceNode.start(when)` 在 `when`
//     时刻**采样精确**地开始播放该缓冲 ⇒ `when` **就是**这段配音
//     在 player AudioContext 时钟上的**真实起播时刻**。
//     （钳位到过去时 `when = currentTime + 5 ms`；顺延时 `when = 上一句结束`
//     —— 两种情况 `when` 同样就是真实起播时刻。）
//   ★ 为了让这个口径**可自证**，同时记录 `endedAt`（实测的结束时刻）
//     与 `endedLagMs`（= endedAt − (when + dur)）⇒ reviewer 可核对
//     「反推的结束时刻与排程是否自洽」。
//
// ## 与 onset 口径的关系（**两个都留，不混算**）
//   * `'sched'` —— 排程起点（**覆盖全部段**，EXT-034 验收要求）；
//   * `'onset'` —— onset 检测的**声学**起点（毫秒级，但**可能缺段**，
//     且会被下一个排程「抢走」⇒ EXT-034 ① 的真缺陷）。
//   ⇒ `dubSyncDetail` 里两者用 `startSource` 区分；
//     P50/P95 的**主口径**用 `'sched'`（全覆盖），
//     onset 的毫秒级数据用 `dubSyncErrsOnset` 单列（不代替主口径）。
//
// ## 口径（**不变**，避免与旧数据不可比）
//   `signedErrMs = 实际起播 − (t0 + t_start + D)`
//   仍用**有符号**（早播为负、晚播为正）⇒ EXT-032 那种
//   `max(0, …)` 恒为 0 的错口径**不会**回来。
const dubStarted = new Map();   // id → {requested, when, dur, tStart, speed}
// ★★★★★ EXT-035：段 id → 「就绪时刻」（AudioContext 时钟）
//   TTS 消息**到达 player** 的时刻 ⇒ 与「起播时刻」同属一个时钟域
//   ⇒ 相减即得纯 player 侧的「就绪→起播」延迟（EXT-035 验收项）。
//   有界：与 dubStarted 同量级。
const dubReadyAt = new Map();   // id → readyAtAc
// ★★★★★★ EXT-036 ①：id → **下行耗时**（毫秒，墙钟口径）
//   `ply_wall_ms − srv_wall_ms` = 服务端产出该段到插件收到该段的真实耗时。
//   ★ 这是「7 s 缺口是下行慢 还是 两端轴对不上」的**判据**：
//     下行耗时若 ≪1 s ⇒ 缺口**不是**下行慢 ⇒ 是**轴对不上**。
const dubDownlinkMs = new Map();
/** ★ 记录一句配音的**排程起点**（= 真实播放起点，语义精确）。 */
function noteDubScheduled(id, requested, when, durSec, tStart, speed, tEnd) {
  if (!id) return;
  dubStarted.set(String(id), {
    requested: requested,
    when: when,
    dur: durSec,
    tStart: tStart,
    // ★★★★★★ EXT-036 ⑥：**源段终点**（源音频域的绝对秒）。
    //   `src_len_sec = tEnd − tStart` ⇒ reviewer 的「实际播放时长 ÷ 源段长」
    //   口径才能算出真实数字（此前 `tEnd` 没贯通 ⇒ 口径 n=0）。
    //   ⚠️ 取不到就是 null（**不臆造**）。
    tEnd: (tEnd == null ? null : tEnd),
    speed: speed,
    endedAt: null,
    // ★★★★★ EXT-035：这段的「**就绪时刻**」（AudioContext 时钟）
    //   = TTS 消息到达 player 的时刻（**排程之前**取）
    //   ⇒ `actual − readyAtAc` = 纯 player 侧「就绪→起播」延迟
    //     （不含 D、不含服务端起步耗时）
    //   ⚠️ 从 `dubReadyAt` 里取（按 id 配对）⇒ 取不到就是 null（不臆造）。
    readyAtAc: (dubReadyAt.has(String(id)) ? dubReadyAt.get(String(id)) : null),
    // ★ onset 检测的声学起点（**可选**：没有触发就是 null）
    onsetActual: null,
    onsetSignedErrMs: null,
  });
  // 有界：只留最近 200 句（与 dubSyncDetail 的上限一致）
  while (dubStarted.size > 200) {
    const first = dubStarted.keys().next().value;
    dubStarted.delete(first);
  }
}

/**
 * ★ 某句配音**播完**了 ⇒ 落进 `dubSyncDetail`（覆盖**全部**有 TTS 的段）。
 * @param {string} id        段 id
 * @param {number} endedAt   onended 时刻（AudioContext 时钟）
 */
function noteDubEnded(id, endedAt) {
  const rec = dubStarted.get(String(id));
  if (!rec || rec.endedAt != null) return;
  rec.endedAt = endedAt;
  // ★ 真实起播 = **排程起点** `when`（Web Audio 的 `start(when)` 是
  //   采样精确的 ⇒ `when` 就是这段配音的真实播放起点）。
  //   ⚠️ **不**用 `endedAt − dur` 反推：那会把 onended 回调的
  //     主线程调度延迟（实测 10–40 ms）系统性地当成同步误差。
  const actual = rec.when;
  const signedErrMs = (actual - rec.requested) * 1000;
  metrics.dubSyncErrs.push(signedErrMs);
  if (metrics.dubSyncErrs.length > 500) metrics.dubSyncErrs.shift();
  metrics.dubSyncDetail.push({
    id: String(id),
    tStart: rec.tStart,
    // ★★★★★★ EXT-036 ⑥：源段终点（供 analyzer 算「播放时长 ÷ 源段长」）
    tEnd: rec.tEnd,
    requested: rec.requested,
    actual: actual,
    signedErrMs: Math.round(signedErrMs * 100) / 100,
    lateMs: Math.round(Math.max(0, signedErrMs) * 100) / 100,
    speed: rec.speed,
    // ★ 来源标明：'sched' = 排程起点（**覆盖全部段**，主口径）
    //            'onset' = onset 检测（毫秒级，但**可能缺段**）
    startSource: 'sched',
    // ★ 排程起点（钳位/顺延后的**真正**排程时刻）
    scheduledAt: rec.when,
    // ★ 自证字段：实测结束时刻 vs 排程推算的结束时刻（差 = 回调延迟）
    endedAt: endedAt,
    endedLagMs: Math.round((endedAt - (rec.when + rec.dur)) * 1000 * 100) / 100,
    // ★ onset 的声学起点（**可能为 null** = 该段没触发 onset）
    //   ⇒ reviewer 可自行比较「排程起点 vs 声学起点」两个口径。
    onsetActual: rec.onsetActual,
    onsetSignedErrMs: rec.onsetSignedErrMs,
    // ★★★★★ EXT-035：「**就绪→起播**」（纯 player 侧，同一 AudioContext 时钟域）
    //   = `actual`（起播） − `readyAtAc`（TTS 消息到达 player）
    //   ⇒ **不含** D、**不含**服务端起步耗时
    //   ⚠️ 取不到就绪时刻就是 null（**不臆造**）
    readyAtAc: rec.readyAtAc,
    readyToStartSec: (rec.readyAtAc != null
                       ? Math.round((actual - rec.readyAtAc) * 1000) / 1000
                       : null),
  });
  if (metrics.dubSyncDetail.length > 200) metrics.dubSyncDetail.shift();
  metrics.dubSyncLateMs.push(Math.max(0, signedErrMs));
  if (metrics.dubSyncLateMs.length > 500) metrics.dubSyncLateMs.shift();
  metrics.dubSyncP50 = pct(metrics.dubSyncErrs, 0.5);
  metrics.dubSyncP95 = pct(metrics.dubSyncErrs, 0.95);
  metrics.dubSyncMax = metrics.dubSyncErrs.length
    ? Math.max(...metrics.dubSyncErrs) : null;
  metrics.dubSyncMin = metrics.dubSyncErrs.length
    ? Math.min(...metrics.dubSyncErrs) : null;
  // ★★★ 注意：**不要**在这里推进 `dubSyncErrsOnset`。
  //   `dubSyncErrsOnset` 是**声学 onset 口径**的序列，
  //   只有 `onDubOnset()` 里真正配到 onset 的那段才会推进它（见 1064 行）。
  //   若这里也推进（推进的是**排程口径**的 signedErrMs）
  //   ⇒ 两个口径**混在同一个数组** ⇒ onset 统计被排程口径污染
  //   ⇒ reviewer 无法单独核对「声学起点」这一个口径。
}

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
    // ★★★ EXT-033 D：**player 端实测「有符号」同步误差**。
    //   signedErrMs = 实际起播（AudioContext 时刻） − (t0 + t_start + D)
    //   ★ `p.requested` 就是 `t0 + t_start + D`（新口径的 t0）。
    //   ★ **有符号**：早播为负、晚播为正 ⇒ EXT-032 那种
    //     `max(0, TTS就绪 − 截止时刻)`（恒 ≥ 0）**量不出早播** ⇒ 口径错。
    //   ★ 「迟到量」另列（lateMs），**不代替** signedErrMs。
    // ★★★★★ EXT-034 ① 修正：onset 口径**不再**直接进主统计。
    //   旧实现：onset 一配到就把 signedErrMs 推进 `dubSyncErrs` /
    //   `dubSyncDetail` ⇒ ① 段数取决于「onset 碰巧配没配上」
    //   （实测 13 段只进 7 段）⇒ ② 同一段可能被**重复** onset
    //   （minGap=50 ms，dubOnsets 里实测有 50 ms 间隔的连续 onset）
    //   记成多条。
    //   ⇒ 现在：onset 的声学起点**只**作为**补充字段**挂到该段上
    //     （`onsetActual` / `onsetSignedErrMs`），
    //     主统计由 `noteDubEnded()`（覆盖全部段）负责。
    const signedErrMs = (at - p.requested) * 1000;
    metrics.dubSyncErrsOnset.push(signedErrMs);
    if (metrics.dubSyncErrsOnset.length > 500) metrics.dubSyncErrsOnset.shift();
    // ★ 把 onset 的声学起点**补记**到该段的排程记录上
    //   ⇒ 等 `onended` 落 `dubSyncDetail` 时一并带出（可自证两者差多少）。
    const rec = dubStarted.get(String(p.id));
    if (rec && rec.onsetActual == null) {
      rec.onsetActual = at;
      rec.onsetSignedErrMs = Math.round(signedErrMs * 100) / 100;
    }
    report({ kind: 'dub_sync', id: p.id, tStart: p.tStart,
             requested: p.requested, actual: at,
             signedErrMs: Math.round(signedErrMs * 100) / 100,
             startSource: 'onset' });
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
  // ★ 2026-11-05 EXT-039 收口：**分位口径统一** = `round(q*(n-1))`。
  //   原实现用 `floor(n*p)` ⇒ 与 Python 侧
  //   （`ext032_deliver._pct` / `p1_pipeline._pct` / `ext033_analyze._pct`，
  //     **也是 reviewer 手算用的口径**）**不一致**
  //   ⇒ 同一批数据在两端给出**两个不同的 P95**：
  //     run `20261105_174558`（n=39）：floor=**22256.7** / round=**21829.2**
  //     run `20261105_112057`（n=14）：floor=**12808.4** / round=**5978.7**
  //       （reviewer EXT-039 ② 报的就是 **5.98** ⇒ round 是对的口径）
  //   ⇒ 统一为 `round(q*(n-1))`，与 Python 侧与 reviewer 三方一致。
  //   ⚠️ **必须复刻 Python 的「银行家舍入」**（round-half-to-even），
  //     不能用 JS 的 `Math.round`（四舍五入）⇒ n=14 的 P50
  //     `round(0.5*13)=round(6.5)`：Python=**6**、JS Math.round=**7**
  //     ⇒ 会差一个元素（s[6]=5.9787 vs s[7]=13.1154）。
  const idx = Math.min(s.length - 1, Math.max(0, pyRoundIndex(p * (s.length - 1))));
  return s[idx];
}

/** Python `round()` 的**银行家舍入**（half-to-even）索引换算。 */
function pyRoundIndex(x) {
  const f = Math.floor(x);
  const diff = x - f;
  if (diff > 0.5) return f + 1;
  if (diff < 0.5) return f;
  // 恰好 .5 ⇒ 取**偶数**
  return (f % 2 === 0) ? f : f + 1;
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

// ★★★★ EXT-028 ①：**从下行消息里解出 PCM 的真实采样率**。
//
// ## 为什么必须独立成一个函数（而不是 inline 一句 `|| 16000`）
//   服务端下发的 TTS 是 **24 kHz** PCM16（`TTS_SAMPLE_RATE`）。
//   旧实现：`b64ToAudioBuffer(msg.pcm24k, msg.sample_rate || 16000)`
//   ⇒ 服务端**没带** `sample_rate` ⇒ 插件按 16 kHz 重建 AudioBuffer
//   ⇒ 24 kHz 波形按 16 kHz 播 ⇒ **快 1.5×、整体升调 ≈7 个半音**
//   ⇒ 用户 11-01 抽听反馈：「基本无法识别内容」。
//
// ## 口径（必须与 `ext/bridge.py` 的 `TTS_SAMPLE_RATE` 一致）
//   * `msg.sample_rate` **存在** ⇒ **以它为准**（服务端是权威）；
//   * `msg.sample_rate` **缺失** ⇒ 说明是**老服务端**（EXT-028 之前）
//     ⇒ 此时**不能猜 16 kHz**（那正是本次的根因）⇒
//     退回 `echo` 消息的语义（TTS 与回声共用一个字段名 ⇒ 老服务端
//     的 tts 其实也没有该字段）⇒ 用**显式的兜底常量**并**如实计数**，
//     绝不静默按错误采样率播放。
//
// ★ 返回值附带 `assumed` 标志 ⇒ 可观测（metrics），便于 reviewer 核对。
const DEFAULT_DUB_SAMPLE_RATE = 24000;   // TTS 输出的采样率（服务端 TTS_SAMPLE_RATE）

/**
 * 取下行 PCM 的采样率。
 * @param {object} msg  下行消息（tts / echo）
 * @returns {{rate: number, assumed: boolean}}
 */
function resolvePcmSampleRate(msg) {
  const raw = msg && msg.sample_rate;
  if (raw != null && isFinite(Number(raw)) && Number(raw) > 0) {
    return { rate: Number(raw), assumed: false };
  }
  // ★ 老服务端：字段缺失 ⇒ 退回 TTS 的标准采样率（24 kHz），
  //   **并标记 assumed=true** ⇒ metrics 里可见，不静默。
  metrics.pcmRateAssumed = (metrics.pcmRateAssumed || 0) + 1;
  return { rate: DEFAULT_DUB_SAMPLE_RATE, assumed: true };
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
  // ★★★★ EXT-028 ①：采样率**以服务端声明为准**（见 resolvePcmSampleRate）。
  //   旧实现写死 `msg.sample_rate || 16000` ⇒ 服务端没带字段时按 16 kHz
  //   播放 24 kHz 的音频 ⇒ 1.5× 语速 + 升调 ⇒ 「基本听不清」。
  const sr = resolvePcmSampleRate(msg);
  const buf = b64ToAudioBuffer(msg.pcm24k, sr.rate);
  metrics.pcmRateLast = sr.rate;
  // 11-08 reviewer: 用「上行样本 ↔ 音频时钟」直接测得的 t0Src 排程（画面 = 抓帧时刻 + D，
  //   配音 = 该句原声被抓到的时刻 + D ⇒ 同一把尺）。旧 t0 推导链曾整体偏早十几秒（配音抢在画面前）。
  const planned = dubT0() + Number(msg.t_start || 0) + delaySec;
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
  let when = Math.max(earliest, planned);

  // ★★★★★ EXT-027 ⑤：**配音必须按序播放，两句不能叠在一起**。
  //
  // ## 证据（reviewer EXT-027 ⑤）
  //   B 轮 20:55:49 **同一秒**下发了 `seg_77393782_798240` 与
  //   `seg_77393782_1004160` 两段，两段都被钳成「立即播」
  //   ⇒ 回转写里「多谢齐先生」排在前面，「都是今日现做的，这个和这个」
  //     **基本消失** ⇒ 两句**叠着播**了。
  //
  // ## 修法（reviewer 明文口径）
  //   `when = max(planned, 上一句结束时刻, currentTime + 5ms)`
  //   ⇒ 严格**按 t_start 顺序**播放，后一句不与前一句重叠。
  //
  // ## 为什么不能只靠 planned
  //   `planned = t0 + t_start + D` 只保证「目标时刻」有序，
  //   **不保证「实际开播」有序**：一旦某句被钳成「立即播」，
  //   后面几句的 planned 可能也都在过去 ⇒ 全部挤到 currentTime+5ms
  //   ⇒ **同时起播** ⇒ 叠播（实测正是如此）。
  //
  // ⚠️ 只对**真实配音**（非 probe）生效 —— probe 是自测探针，
  //   必须严格按 planned 排程，否则排程误差测量会失真。
  if (!isProbe) {
    // ★ 维护「上一句的结束时刻」：取所有**已排程**配音的最晚结束。
    //   用 max 而不是「最后一句」⇒ 即使乱序到达，也不会算出偏小的值。
    const prevEnd = dubPlaybackEnd;
    if (when < prevEnd) {
      // 被上一句的尾巴挡住 ⇒ 顺延到上一句播完之后
      const pushed = prevEnd - when;
      when = prevEnd;
      metrics.dubRescheduled = (metrics.dubRescheduled || 0) + 1;
      metrics.dubRescheduleDelaySec =
        Math.round(((metrics.dubRescheduleDelaySec || 0) + pushed) * 1000) / 1000;
      report({ kind: 'dub_rescheduled', id: msg.id,
               pushedSec: Math.round(pushed * 1000) / 1000,
               planned: planned, when: when });
    }
    // ★ 记录本句的结束时刻（下一句要排在它后面）
    //   ⚠️ 用 `when + buf.duration`（**实际**开播 + 实际时长），
    //     不用 planned（那样算不出「会重叠」）。
    const end = when + buf.duration;
    if (end > dubPlaybackEnd) dubPlaybackEnd = end;
  }
  src.start(when);

  // ★★ EXT-009：自适应加速播放的**播放侧记录**（不改变音频波形）
  //   - `msg.speed` 是服务端算好的**总倍率**（时长适配 × 自适应加速，封顶 1.30×）
  //     ⇒ 音频**已经是**这个倍率的波形（WSOLA 在服务端做的）⇒
  //       这里**绝不能**再对 buffer 做 playbackRate（会二次加速 + 变调）。
  //   - 插件侧实测 lag = 实际开播时刻 − 目标开播时刻
  //     （目标开播时刻 = t0 + t_start + D；实际开播时刻 = when，含钳位）
  //   - 本地按 EXT-009 公式**复核**一遍倍率，便于发现两侧口径差异。
  if (!isProbe) {
    const targetStart = planned;
    if (!isProbe) {
      const _now = audioCtx.currentTime;
      if (!dubSyncLogAt || _now - dubSyncLogAt > 15) {
        dubSyncLogAt = _now;
        bridgeLog('[sync] t_start=' + Number(msg.t_start || 0).toFixed(2) + ' t0Src-t0=' +
          (t0Src == null ? 'na' : (t0Src - t0).toFixed(2)) + 's lag=' + (when - planned).toFixed(2) +
          's speed=' + Number(msg.speed || 1).toFixed(2));
      }
    }
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
    // ★★★ EXT-033 D：排程时刻之外，还要记**这一句的身份**，
    //   否则 player 端算不出「有符号同步误差」的对齐对象。
    tStart: Number(msg.t_start || 0),
    tEnd: Number(msg.t_end || 0),
    speed: Number(msg.speed || 1.0),
    src: (msg.src == null ? null : String(msg.src)),
    tgt: (msg.tgt == null ? null : String(msg.tgt)),
    matched: false, probe: isProbe,
  });
  // ★★★★★ EXT-034 ①：**每段配音都要能算���同步误差**（不靠 onset 配对）。
  //   记下排程起点 ⇒ 等 `onended` 回调反推**真实起播**。
  //   ⚠️ probe（自测探针）**不记** —— probe 不是真实配音，
  //     混进来会污染 EXT-033 D 的口径（EXT-024 P0③ 已有同样要求）。
  if (!isProbe) {
    noteDubScheduled(msg.id, planned, when, buf.duration,
                     Number(msg.t_start || 0), Number(msg.speed || 1.0),
                     (msg.t_end == null ? null : Number(msg.t_end)));
    // ★ `onended` 在缓冲播完时触发（AudioContext 时钟）⇒ 反推起播。
    //   ⚠️ `when` 可能被钳位到过去（schedClamped）⇒ 真实起播会晚于 `when`，
    //     `onended` 反推**自动**把这个滞后算进去（actual = ended − dur）。
    src.onended = () => {
      const at = audioCtx ? audioCtx.currentTime : 0;
      noteDubEnded(msg.id, at);
      report({ kind: 'dub_ended', id: msg.id, endedAt: at,
               startSource: 'ended' });
    };
  }
  scheduleSub(msg, when);
  return { planned: when, requested: planned };
}

// ★ subs 用**有序插入**而不是每次 push 都 sort()。
//   真实缺陷：回声模式下每帧一条 ⇒ 每次 push 都整表重排 ⇒ O(n² log n)。
//   ⇒ 改为「尾部追加 + 尾部乱序时插入排序」（绝大多数情况单调递增 ⇒ O(1)）。
const SUBS_CAP = 200;
const subs = [];
function scheduleSub(msg, when) {
  // ★★ T-3：字幕关着就不入队（省掉无用的文本处理与 DOM 写入）。
  if (!subsOn) {
    metrics.subsDropped = (metrics.subsDropped || 0) + 1;
    return;
  }
  // 11-09 user: show the finalized source text under the translation
  const _src = (msg.src && msg.src !== '—') ? String(msg.src) : '';
  const _tgt = (msg.tgt && msg.tgt !== '—') ? String(msg.tgt) : '';
  const item = { text: _tgt || _src, src: (_tgt && _src) ? _src : '', at: when, id: msg.id };
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
  // ★★ T-3：字幕开关此前是**死控件**（popup 存了 subsOn，
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
    div.innerHTML = `<span>${escapeHtml(s.text)}</span>` +
      (s.src ? `<br><span class="src">${escapeHtml(s.src)}</span>` : '');
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

// ★★ T-5：`gapDetail` 的**保留上限**（条）。
//   为什么需要（P2「30 分钟不崩、内存不持续增长」）：
//   旧实现**只追加、永不裁剪** ⇒ 每次丢帧/采样不连续都永久留一条
//   ⇒ 网络抖动时**无限增长** ⇒ 长会话内存单调上升。
//   上报口径（`slice(-20)`）不变 ⇒ 只是把明细截断在 200 条。
const GAP_DETAIL_CAP = 200;

const upState = {
  ac: null, node: null, source: null, ws: null,
  seq: 0, sampleIndex: 0, frameCount: 0, bytesSent: 0,
  gaps: 0, gapDetail: [], maxAbsSkewMs: 0, maxAbsSkewAllMs: 0, skewSamples: [],
  gapDetailDropped: 0,
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

// ★★★ EXT-026 修正：**状态条的段数恒为 0** ⇒ 真实缺陷。
//
// ## 根因（2026-10-31 真实三引擎实测抓到）
//   `handleBridgeMessage` 里处理 `kind === 'stats'`（EXT-024 E 加的），
//   但**客户端从来没有发过 `{"type":"stats"}` 请求** ⇒
//   服务端的 stats 分支永远进不去 ⇒
//   `metrics.link.asrSegments / mtSegments / ttsSegments` **恒为 0**
//   ⇒ 状态条显示「ASR 0 | MT 0 | TTS 0」
//   ⇒ **最关键的故障信号（TTS 一段都没出）根本显示不出来**，
//      而那一轮实际真跑出了 4 段 TTS（bridge.log 的段级日志里有）。
//
// ## 修法
//   周期性发 `{"type":"stats"}` ⇒ 服务端回 stats ⇒
//   `handleBridgeMessage` 的 stats 分支才有数据可读。
//   ★ 服务端 stats 分派用的是 `_producer_session()`（按 token 找 uplink 会话）
//     ⇒ 无论从哪条连接问，拿到的都是**真会话**的统计。
//
// ★★★ EXT-026 二次修正：**生产路径**下上行 WS 在 **offscreen** 里，
//   player 自己的 `upState.ws` 是 **null**（player 没抓流、没上行）
//   ⇒ 只认 `upState.ws` ⇒ 状态条**永远拿不到 stats** ⇒ 段数恒为 0
//   （实测 2026-10-31 生产路径：段级日志 8 段，状态条 asr/mt/tts 全 0）。
//   ⇒ 修法：**两条 WS 都试** —— 先上行（与产出段同源），
//     没有就用 player 自己那条（role=player，同样按 token 拿真会话）。
const STATS_POLL_MS = 1000;
let statsPollTimer = null;
function pollStats() {
  try {
    // ★ 优先上行 WS（player 自己抓流的那条路径）
    const up = upState.ws;
    if (up && up.readyState === 1) {
      up.send(JSON.stringify({ type: 'stats' }));
      metrics.link.statsPolled = (metrics.link.statsPolled || 0) + 1;
      return;
    }
    // ★ 回落到 player 自己那条 WS（生产路径：上行在 offscreen 里）
    const w = (typeof ws !== 'undefined') ? ws : null;
    if (w && w.readyState === 1) {
      w.send(JSON.stringify({ type: 'stats' }));
      metrics.link.statsPolled = (metrics.link.statsPolled || 0) + 1;
    }
  } catch (e) { /* ignore */ }
}
function startStatsPolling() {
  if (statsPollTimer !== null) return;    // 幂等：别起两个定时器
  statsPollTimer = setInterval(pollStats, STATS_POLL_MS);
  setTimeout(pollStats, 500);              // 立刻问一次（别等第一个周期）
}

function upPost(msg) {
  try {
    chrome.storage.local.get({ extLog: [] }).then((s) => {
      const arr = (s.extLog || []).concat([{ ts: Date.now(), ...msg }]).slice(-200);
      return chrome.storage.local.set({ extLog: arr });
    }).catch(() => {});
  } catch (e) { /* ignore */ }
}

/** 把 48 kHz 抓到的音频重采样到 16 kHz 并上行。 */
async function startUplink(stream, wsUrl, token, captureMode) {
  if (upState.running) return { ok: true, already: true };
  try {
    const track = stream.getAudioTracks()[0];
    if (!track) return { ok: false, error: '没有音频轨' };
    const st = track.getSettings ? track.getSettings() : {};
    upState.sourceRate = st.sampleRate || 48000;
    // ★★ EXT-027①：**如实**上报实际用的抓流方式。
    //   旧实现写死 'getDisplayMedia' ⇒ 即使用了 tabCapture 也报兜底
    //   ⇒ reviewer 无法从数据核对（EXT-005① / EXT-027① 都要求如实）。
    upState.captureMode = captureMode || 'getDisplayMedia';

    // ① WebSocket
    const ws = new WebSocket(wsUrl);
    upState.ws = ws;
    await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('WS 超时')), 8000);
      ws.onopen = () => {
        clearTimeout(t);
        upState.wsOpen = true;
        metrics.link.wsConnected = true;
        metrics.link.wsError = null;
        ws.send(JSON.stringify({
          type: 'hello', token, role: 'uplink', sample_rate: 16000,
          source: 'player', delay_sec: delaySec,
          // ★★ T-1：把**抓流方式**上报给桥接服务。
          //   服务端会把它记进会话 ⇒ stats 回包与 margin.json 都带上
          //   ⇒ EXT-005 ①「tabCapture 生产路径到底有没有被实测过」
          //   **可以从落盘数据核对**，不用人读日志猜。
          //   ⚠️ 这里报的是**实际用的那条路**（上面的 upState.captureMode
          //     就是在拿到流的那一刻赋的值，不是计划值）。
          capture_mode: upState.captureMode,
          // ★★ T-4：把**目标语言**与**音色**也带上来。
          //   此前只有 offscreen 的 hello 带了这两个字段，
          //   而 player 这条上行链路（getDisplayMedia 兜底路径）**没带**
          //   ⇒ 服务端拿不到 ⇒ 面板上选的语言/音色在这条路径上**完全丢失**。
          target_lang: targetLang || null,
          voice: voicePref || null,
        }));
        resolve();
      };
      ws.onerror = () => {
        clearTimeout(t);
        metrics.link.wsConnected = false;
        metrics.link.wsError = '上行 WS 失败（桥接服务未启动或端口不通）';
        reject(new Error('WS 失败'));
      };
      // ★★ EXT-024 A：上行连接**也必须**收消息！
      //   旧实现这里**没有 onmessage** ⇒ 服务端把 tts 发到这条连接上时
      //   被浏览器丢弃 ⇒ **用户只听到延迟原声、没有配音、没有字幕**
      //   （这正是用户 10-31 实测的症状）。
      //   ⇒ 现在两条连接都用同一套处理（`handleBridgeMessage`）。
      ws.onmessage = (ev) => {
        try {
          handleBridgeMessage(JSON.parse(ev.data));
        } catch (e) { /* ignore */ }
      };
      ws.onclose = (ev) => {
        upState.wsOpen = false;
        const r = bridgeCloseReason(ev);
        if (r) { metrics.link.wsConnected = false; metrics.link.wsError = r; }
      };
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

/**
 * ★★★ EXT-026 修正：**尾段永远丢** ⇒ 真实缺陷。
 *
 * ## 根因（2026-10-31 真实三引擎实测抓到）
 *   服务端的流式分段**故意**把最后一段留在缓冲区等后续音频
 *   （`ext/bridge.py` 的 `Session.flush` 的说明：正常直播场景正确），
 *   要收口尾段必须客户端发一条 `{"type":"flush"}`。
 *   ⇒ **但整个插件链路从来没有任何地方发过 flush**
 *     （player / offscreen / sw 都没有）
 *   ⇒ 用户点「停止」时，**最后一句永远不会被翻译、不会被配音**
 *     ⇒ 实测：60 秒英文素材切成 5 段，
 *       前 4 段出了配音，**尾段（2.92 s）直接消失**。
 *
 * ## 修法
 *   上行 WS 发 `{"type":"flush"}` ⇒ 服务端把缓冲区里的尾段跑完并下发。
 *   ★ 走**上行那条 WS**（与产出段的会话同源）。
 *   ★ 服务端 `flush` 分支在非回声模式下才生效（回声是逐帧原样返回）。
 *
 * @returns {Promise<{ok: boolean, error?: string}>}
 */
async function flushUplink() {
  try {
    const w = upState.ws;
    if (!w || w.readyState !== 1) {
      return { ok: false, error: '上行 WS 未连接' };
    }
    w.send(JSON.stringify({ type: 'flush' }));
    metrics.link.flushSent = (metrics.link.flushSent || 0) + 1;
    report({ kind: 'flush_sent' });
    return { ok: true };
  } catch (e) {
    const err = String((e && e.message) || e);
    report({ kind: 'flush_error', error: err });
    return { ok: false, error: err };
  }
}

/**
 * ★★ EXT-028：主动让服务端把**余量统计**落盘（`margin.json`）。
 *
 * ## 为什么必须有这个接口
 *
 * 服务端的 `finally` 落盘路径在 `terminate()`（SIGTERM）下**不会执行**
 * ⇒ 客户端如果直接断开，`margin.json` **永远不落盘**
 * （实测：e2e 两轮跑完，段级日志/音频都在，但 `margin.json` 缺失
 *   ⇒ EXT-028 的余量数据拿不到）。
 *
 * ⇒ 这里走**上行那条 WS**（与产出段的会话同源）发一条 `dump_margin`
 *   ⇒ 服务端**立刻**写盘，不依赖进程退出路径。
 *
 * ⚠️ 服务端消息循环是**单线程串行**的 ⇒ 必须**等回包**
 *   （`margin_dumped`）才算落盘完成，不能发完就当成功。
 *
 * @param {number} [timeoutMs=60000] 等回包的超时
 * @returns {Promise<{ok: boolean, path?: string|null, error?: string}>}
 */
/* ★★★★★★ EXT-036 ①/②：把插件**实测**的下行耗时 / 播放端排队 / 轴偏移
 *   **上报服务端**。
 *   ## 为什么必须加（真缺陷，不是锦上添花）
 *     这些量插件一直测得到（`ply_wall_ms − srv_wall_ms`、`readyToStartSec`、
 *     `t0UpPlayerOffsetSec`），也都落进了 `dub_sync.json`
 *     ⇒ 但**只留在插件本地** ⇒ 服务端 `margin.json` 的 `sync_rootcause`
 *       里这三项**恒为 null** ⇒ 「非 TTS 固定项」少算三项
 *       ⇒ **归因不完整**（reviewer 要求「逐项分解」）。
 *   ⇒ 现在主动上报 ⇒ 服务端 `margin.json` 能直接核对。
 *   ★ 只报**实测到**的值；没测到就不报（绝不用 0 冒充「实测为零」）。
 *   ★ 列表有界（最多 200 项）⇒ 不制造「内存不持续增长」那类回归。
 */
// ★★★ EXT-041：**媒体降速**（`video.playbackRate`）—— 插件侧编排
// ────────────────────────────────────────────────────────────────
// ## 为什么需要（EXT-041 明文）
//   `tts_over_src ≈ 1.09` ⇒ 配音总时长比源语音长约 9% ⇒
//   在任何**固定**缓冲 D 下，配音都会**随时间累积地落后**于画面。
//   ⇒ 用户 2026-11-06 决定放宽「signed P95 ≤ 0.3 s」，并要求
//     **斜率 ≤ 0.01 s/s（不能无限累积）** ⇒ 必须**改机制**，不只是放宽数值。
//   ⇒ 本模块实现 EXT-041 给的**机制①：视频轻微降速**
//     （0.92–0.95，下限 0.9）⇒ 让**画面追配音**。
//
// ## 数学依据（详见 `ext/media_slowdown.py`）
//   媒体降速 `r` ⇒ 源到达速率降为 `r` 倍 ⇒ 不堆积的条件是
//   `r ≤ 1 / tts_over_src`。实测 `tts_over_src = 1.0936` ⇒
//   `r* = 0.9144` ⇒ 取 **0.92**（reviewer 给的区间内，且刚好够）。
//
// ## ★ 时间轴（**关键**：降速为什么不会破坏对齐）
//   * `t_start` 的轴 = **上行链路的采样时间轴**（与服务端 `t0` 无关）；
//   * 媒体降速**不改变** `t_start`（那是**源侧采样点**）；
//   * 降速只改变**墙钟**：源音频到达插件的墙钟变慢 ⇒
//     配音的**目标时刻** `t0 + t_start + D` 随之变慢 ⇒
//     **配音与画面一起慢下来** ⇒ 相对关系保持 ⇒ **斜率被压平**。
//
// ## ★ 诚实说明
//   * 宿主页面上**没有** `<video>`/`<audio>` ⇒ 降速**无效**
//     ⇒ 必须如实回报 `applied=false`，**不假装成功**；
//   * **只降速，永不加速**（>1.0 会改变语义时轴，属另一件事）；
//   * **不改译文、不改引擎、不改 ASR/MT** ⇒ 纯 EXT 侧机制。

/** 媒体降速的**下限 / 上限**（与服务端 `ext/media_slowdown.py` 一致）。 */
const SLOWDOWN_FLOOR = 0.80;   // 11-06: was 0.90 — long videos still drifted (dub/src 1.28, WSOLA capped 1.3x)
const SLOWDOWN_CEIL = 1.00;
const SLOWDOWN_DEFAULT = 0.92;
/** 刷新「服务端建议倍率」的周期（ms）—— 实测占用率要跑几段才有值。 */
const SLOWDOWN_REFRESH_MS = 30000;

/** 读**目标标签页 id**（popup 在起流前写进 storage）。 */
async function cfgTargetTabId() {
  try {
    const cfg = await chrome.storage.local.get({ targetTabId: null });
    const id = cfg && cfg.targetTabId;
    if (id == null) return null;
    const n = Number(id);
    return (isFinite(n) && n > 0) ? n : null;
  } catch (e) {
    return null;
  }
}

/** 恢复 `playbackRate = 1.0`。 */
async function resetMediaSlowdown() {
  const tabId = await cfgTargetTabId();
  if (!tabId) return { ok: false, error: '不知道目标标签页 id' };
  try {
    const res = await chrome.tabs.sendMessage(tabId, { cmd: 'reset-rate' });
    metrics.slowdown = { applied: false, rate: 1.0,
                         videos: (res && res.videos) || null,
                         reason: (res && res.reason) || '已恢复 1.0' };
    report({ kind: 'slowdown_result', result: metrics.slowdown });
    return res;
  } catch (e) {
    metrics.slowdown = { applied: false, rate: null, videos: null,
                         reason: '恢复失败：' + String((e && e.message) || e) };
    return metrics.slowdown;
  }
}

/**
 * ★★★ EXT-041：**媒体降速**的**实测读取**（player 侧）。
 *
 * ## ★ 为什么 player 不自己去注入
 *   `chrome.scripting.executeScript` 需要目标页的 **activeTab / host 权限**。
 *   ★ **popup 的「开始」按钮是真实用户手势** ⇒ 点击时 Chrome 已把
 *     `activeTab` 授予**当前标签页** ⇒ **popup 注入必定成功**。
 *   ⇒ 而 **player.html 是另一个扩展页**，它对目标标签页**没有**授权
 *     ⇒ 从 player 注入会失败（"Cannot access contents of the page"）。
 *   ⇒ 分工：**popup 负责注入 + 设置倍率**，
 *     **player 只负责读实测结果 + 上报给服务端 + 周期刷新建议**。
 *
 * ## 诚实说明
 *   * storage 里**没有**降速记录 ⇒ 没降过速 ⇒ 返回 null（**不臆造**）；
 *   * 记录里 `applied=false` ⇒ 页面里没有媒体元素 ⇒ 如实如实上报。
 */
async function readSlowdownRecord() {
  try {
    const cfg = await chrome.storage.local.get({ slowdown: null });
    const rec = cfg && cfg.slowdown;
    if (!rec || typeof rec !== 'object') return null;
    return rec;
  } catch (e) {
    return null;
  }
}

/**
 * ★★★ EXT-043 C1（真缺陷）：由 WS 地址推出**配对端口**的 `/status` URL。
 *
 * ## 原实现为什么错（node 实测 Invalid URL）
 *   ```js
 *   const base = 'ws://127.0.0.1:8765/'.replace(/^ws:\/\//, 'http://')  // 'http://127.0.0.1:8765'
 *   const host = base.replace(/^https?:\/\/[^/]+/, '')   // ← 把 host:port 整段删了！
 *                      .split('/')[0]                    // ⇒ host = ''
 *                      .replace(/:\d+$/, '');
 *   fetch('http://' + '' + ':' + 8766 + '/status')       // ⇒ 'http://:8766/status'
 *   ```
 *   ⇒ `new URL('http://:8766/status')` 直接抛 Invalid URL
 *   ⇒ **服务端建议倍率从来没生效过**，一直用默认 0.92。
 *
 * ## 修法：用 `URL` 解析**先拆出 hostname/port**，再拼。
 *   * 配对端口 = 桥接端口 + 1（`ext/pair_server.py` 的约定）；
 *   * 拿不到端口时用默认 8765。
 */
function pairStatusUrl(wsUrl) {
  try {
    const raw = String(wsUrl || 'ws://127.0.0.1:8765/');
    // `ws://` / `wss://` ⇒ 先换成 http(s)，否则 URL 解析出的 protocol 不对
    const http = raw.replace(/^ws:\/\//, 'http://').replace(/^wss:\/\//, 'https://');
    const u = new URL(http);
    const port = Number(u.port || (u.protocol === 'https:' ? 443 : 8765));
    const pairPort = port + 1;
    const scheme = (u.protocol === 'https:') ? 'https' : 'http';
    return scheme + '://' + u.hostname + ':' + pairPort + '/status';
  } catch (e) {
    return 'http://127.0.0.1:8766/status';
  }
}

/**
 * 刷新「服务端建议倍率」并（若建议变了）请求 popup 侧重新设置。
 *
 * ★ 为什么要周期刷新：`recommended_rate` 依赖**实测** `tts_over_src`，
 *   而那要等跑出几段才有值 ⇒ 起流时多半还拿不到 ⇒ 需要随会话推进更新。
 *   ⚠️ 刷新**不阻塞**任何主流程；失败**如实**记录。
 */
async function refreshSlowdownRecommendation(wsUrl) {
  try {
    const rec = await readSlowdownRecord();
    if (!rec || !rec.enabled) return null;   // 用户关了 ⇒ 不动
    const cfg = await chrome.storage.local.get({ wsUrl: wsUrl || 'ws://127.0.0.1:8765/' });
    // ★ EXT-043 C1：用 `pairStatusUrl()` 拼地址（原实现拼出 `http://:8766`）。
    const url = pairStatusUrl(cfg.wsUrl);
    const r = await fetch(url);
    if (!r.ok) return null;
    const j = await r.json();
    const sd = (j && j.status && j.status.slowdown) || null;
    if (!sd || typeof sd.recommended_rate !== 'number') return null;
    const newRate = sd.recommended_rate;
    metrics.slowdownRecommended = newRate;
    // ★ 建议变了 ⇒ 请求后台/弹窗重新设置（popup 可能已关闭 ⇒ 这里直接尝试注入）
    const cur = (rec && typeof rec.rate === 'number') ? rec.rate : null;
    if (cur != null && Math.abs(cur - newRate) < 1e-4) return sd;
    const tabId = await cfgTargetTabId();
    if (tabId) {
      const res = await applyMediaSlowdownToTab(tabId, newRate);
      const rec2 = {
        enabled: true,
        applied: !!(res && res.applied),
        rate: (res && typeof res.rate === 'number') ? res.rate : null,
        videos: (res && typeof res.videos === 'number') ? res.videos : null,
        reason: (res && res.reason) ? String(res.reason) : null,
        recommended: newRate,
        at: Date.now(),
      };
      try { await chrome.storage.local.set({ slowdown: rec2 }); } catch (e) { }
      metrics.slowdown = {
        applied: rec2.applied, rate: rec2.rate, videos: rec2.videos,
        reason: rec2.reason,
      };
      report({ kind: 'slowdown_result', result: metrics.slowdown });
    }
    return sd;
  } catch (e) {
    return null;
  }
}

/** 向目标标签页注入内容脚本并设置 `playbackRate`（player 侧兜底路径）。 */
// ── 11-06 (reviewer): closed-loop source-video rate controller ──────────────
//   User: with CUDA TTS the pipeline keeps up, but on videos >300 s sync still
//   drifts.  Cause: the Chinese dub is ~1.28x the source; WSOLA tops out at 1.3x
//   and long sentences overflow, so the backlog creeps up.  Fix: watch the real
//   playback lag (actual dub start − target start, metrics.adaptLagSec) and
//   slow the SOURCE video just enough to hold lag near 0.5 s (0.80–1.00x).
let lagCtlTimer = null, lagCtlRate = 1.0;
// 11-08: send a line to bridge.log (player-side state was invisible in the 11-08 user test)
function bridgeLog(text) {
  try {
    const w = upState.ws && upState.ws.readyState === 1 ? upState.ws : null;
    if (w) w.send(JSON.stringify({ type: 'player_log', text: String(text).slice(0, 400) }));
  } catch (e) { /* ignore */ }
}
function startLagRateController() {
  if (lagCtlTimer) return;
  bridgeLog('降速闭环已启动 floor=' + SLOWDOWN_FLOOR);
  lagCtlTimer = setInterval(async () => {
    try {
      const lag = Number(metrics.adaptLagSec);
      if (!isFinite(lag)) return;
      const target = Math.max(SLOWDOWN_FLOOR, Math.min(SLOWDOWN_CEIL,
        1.0 - 0.04 * Math.max(0, lag - 0.5)));          // 2 s lag -> 0.94x, 5 s -> 0.82x
      const next = lagCtlRate + 0.5 * (target - lagCtlRate);   // smooth
      if (Math.abs(next - lagCtlRate) < 0.01 && Math.abs(target - lagCtlRate) < 0.01) return;
      lagCtlRate = Math.round(next * 100) / 100;
      const tid = await cfgTargetTabId();
      const r = await applyMediaSlowdownToTab(tid, lagCtlRate);
      metrics.slowdown = { applied: !!r.applied, rate: lagCtlRate, videos: r.videos,
                           reason: r.reason || ('闭环：lag=' + lag.toFixed(2) + 's') };
      bridgeLog('降速 rate=' + lagCtlRate + ' lag=' + lag.toFixed(2) + 's applied=' + !!r.applied
                + ' videos=' + r.videos + (r.reason ? ' reason=' + r.reason : ''));
    } catch (e) { bridgeLog('降速闭环异常：' + String((e && e.message) || e)); }
  }, 2000);
}

async function applyMediaSlowdownToTab(tabId, rate) {
  let r = Number(rate);
  if (!isFinite(r) || r <= 0) {
    return { ok: false, applied: false, rate: null, videos: null,
             reason: '倍率非法：' + String(rate) };
  }
  r = Math.max(SLOWDOWN_FLOOR, Math.min(SLOWDOWN_CEIL, r));
  if (tabId == null) {
    return { ok: false, applied: false, rate: r, videos: null,
             reason: '不知道目标标签页 id ⇒ 没有降速' };
  }
  try {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['slowdown.js'],
      });
    } catch (e) {
      // 注入失败（如该页不允许扩展注入）⇒ 如实记录
      return { ok: false, applied: false, rate: r, videos: null,
               reason: '注入内容脚本失败：' + String((e && e.message) || e) };
    }
    const res = await chrome.tabs.sendMessage(tabId, { cmd: 'set-rate', rate: r });
    return {
      ok: !!(res && res.ok),
      applied: !!(res && res.applied),
      rate: (res && typeof res.rate === 'number') ? res.rate : null,
      videos: (res && typeof res.videos === 'number') ? res.videos : null,
      reason: (res && res.reason) ? String(res.reason) : null,
    };
  } catch (e) {
    return { ok: false, applied: false, rate: r, videos: null,
             reason: '设置 playbackRate 失败：' + String((e && e.message) || e) };
  }
}

/**
 * 启动「周期刷新建议倍率」的定时器。
 *
 * ★ 为什么要周期刷新：`recommended_rate` 依赖**实测** `tts_over_src`，
 *   而那要等跑出几段才有值 ⇒ 起流时多半还拿不到 ⇒ 需要随会话推进更新。
 * ⚠️ 幂等：重复调用**不会**起多个定时器（用标记位）。
 */
let _slowdownTimer = null;
function startSlowdownRefreshTimer(wsUrl) {
  if (_slowdownTimer) return;
  _slowdownTimer = setInterval(() => {
    refreshSlowdownRecommendation(wsUrl).catch(() => { });
  }, SLOWDOWN_REFRESH_MS);
}

async function reportClientMetrics() {
  // 上行 WS 优先（它就是产出段的那条连接 ⇒ 记到同一个会话）
  const w = upState.ws
    && upState.ws.readyState === 1 ? upState.ws : null;
  if (!w) return { ok: false, error: '上行 WS 未连接' };
  try {
    const dlMs = [];
    for (const [id, v] of dubDownlinkMs.entries()) {
      if (typeof v === 'number' && isFinite(v) && v >= 0) dlMs.push(v);
    }
    // 播放端排队：detail 里每段的「就绪→起播」
    const pq = [];
    for (const d of (metrics.dubSyncDetail || [])) {
      const v = d && d.readyToStartSec;
      if (typeof v === 'number' && isFinite(v) && v >= 0) pq.push(v);
    }
    const off = metrics.t0UpPlayerOffsetSec;
    // ★★★ EXT-041：上报前**再读一次** storage 里的降速实测。
    //   为什么：降速初始化是 fire-and-forget ⇒ 早于它完成时
    //   `metrics.slowdown` 还是 null ⇒ 会**漏报**「实际降了多少」。
    //   ⇒ 每次上报都取**最新**的实测记录（storage 是 popup 写的唯一真源）。
    //   ⚠️ 读不到就保持原值（**不臆造**）。
    if (metrics.slowdownEnabled) {
      const rec = await readSlowdownRecord();
      if (rec) {
        metrics.slowdown = {
          applied: !!rec.applied,
          rate: (typeof rec.rate === 'number') ? rec.rate : null,
          videos: (typeof rec.videos === 'number') ? rec.videos : null,
          reason: rec.reason || null,
        };
        if (typeof rec.recommended === 'number') {
          metrics.slowdownRecommended = rec.recommended;
        }
      }
    }
    const payload = {
      type: 'client_metrics',
      downlink_ms: dlMs.slice(-200),
      player_queue_sec: pq.slice(-200),
      t0_up_player_offset_sec:
        (typeof off === 'number' && isFinite(off) ? off : null),
      // ★★★ EXT-041：**媒体降速的实测**（实际降了多少 ⇒ 服务端落盘）。
      //   ⚠️ 没降过速 ⇒ `metrics.slowdown` 为 null ⇒ **不报**（不臆造）。
      //   ⚠️ 只报**实测到的**倍率与是否真的作用到了媒体元素上。
      slowdown: (metrics.slowdown || null),
    };
    w.send(JSON.stringify(payload));
    metrics.link.clientMetricsSent =
      (metrics.link.clientMetricsSent || 0) + 1;
    return { ok: true, n_downlink: payload.downlink_ms.length,
             n_player_queue: payload.player_queue_sec.length };
  } catch (e) {
    const err = String((e && e.message) || e);
    report({ kind: 'client_metrics_error', error: err });
    return { ok: false, error: err };
  }
}

async function requestMarginDump(timeoutMs) {
  const to = Number(timeoutMs) > 0 ? Number(timeoutMs) : 60000;
  try {
    const w = upState.ws;
    if (!w || w.readyState !== 1) {
      return { ok: false, error: '上行 WS 未连接' };
    }
    // ★★ EXT-036：先上报**实测**的下行/排队数据 ⇒ 服务端落盘时才有这三项
    //   ⇒ 否则 `sync_rootcause` 里它们恒为 null（归因不完整）。
    const cmRes = await reportClientMetrics();
    report({ kind: 'client_metrics_sent', result: cmRes });
    const got = new Promise((resolve) => {
      const h = (ev) => {
        let m = null;
        try { m = JSON.parse(ev.data); } catch (e) { return; }
        if (m && m.type === 'margin_dumped') {
          try { w.removeEventListener('message', h); } catch (e) {}
          resolve(m);
        }
      };
      w.addEventListener('message', h);
    });
    w.send(JSON.stringify({ type: 'dump_margin' }));
    metrics.link.marginDumpSent = (metrics.link.marginDumpSent || 0) + 1;
    report({ kind: 'margin_dump_sent' });
    const timer = new Promise((resolve) => setTimeout(
      () => resolve(null), to));
    const m = await Promise.race([got, timer]);
    if (!m) return { ok: false, error: '等 margin_dumped 回包超时' };
    report({ kind: 'margin_dumped', path: m.path, dumped: m.dumped });
    return { ok: true, path: (m.path == null ? null : m.path),
             dumped: !!m.dumped };
  } catch (e) {
    const err = String((e && e.message) || e);
    report({ kind: 'margin_dump_error', error: err });
    return { ok: false, error: err };
  }
}

function onUplinkFrame(d) {
  const pcm = d.pcm;
  const nSamples = pcm.byteLength / 2;
  const seq = d.seq;
  const sampleIndex = d.sampleIndex;
  // 11-08 reviewer: 样本 (sampleIndex+n) 刚被抓到 ≈ 现在 ⇒ 样本 0 的音频时钟时刻 ≤ now − 已抓秒数；
  //   取所有帧的最小值（= 真值 + 最小传输延迟，与画面抓帧口径一致）。
  if (audioCtx && typeof sampleIndex === 'number') {
    const est = audioCtx.currentTime - (sampleIndex + nSamples) / 16000;
    if (t0Src == null || est < t0Src) t0Src = est;
  }

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
    // ★★ T-5 修正：**gapDetail 原来只追加、永不裁剪** ⇒
    //   丢帧/采样不连续每次都留一条 ⇒ 网络抖动时**无限增长**
    //   （P2「30 分钟不崩、内存不持续增长」的真缺陷）。
    // ⇒ 加**上限**：超出即丢最旧的，并计数（不静默丢）。
    //   ⚠️ 上报时只取最近 20 条（`slice(-20)`）⇒ 口径不变。
    if (upState.gapDetail.length > GAP_DETAIL_CAP) {
      const drop = upState.gapDetail.length - GAP_DETAIL_CAP;
      upState.gapDetail.splice(0, drop);
      upState.gapDetailDropped = (upState.gapDetailDropped || 0) + drop;
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
    // ★★★ EXT-033 D：用**音频时钟**把时间轴原点钉死（新口径）。
    //   取前 N 帧的中位数（首帧含启动瞬态 ⇒ 用中位数更稳）。
    //
    // ★★ EXT-033 D 修正：**必须换算到 player 域**。
    //   `d.audioFrame16` 是**上行 AudioContext** 的时钟；
    //   而 `planned`/`when`/`at` 全在 **player AudioContext** 的时钟上。
    //   ⇒ 先测 `Δ = up.ac.currentTime − audioCtx.currentTime`（常量偏移），
    //     再 `t0_player = t0_up + Δ`。
    //
    // ⚠️ **实测注意**（浏览器实测，见 tests/smoke/ext033_t0_verify.py）：
    //   两个 AudioContext 的 `currentTime` 是**各自独立更新**的（各自的渲染量子）
    //   ⇒ 单次相减会带上「两次读取落在不同更新点」的抖动（实测 spread ≈ 80 ms）
    //   ⇒ 必须**多次采样取中位数**（下面 `T0_OFFSET_FRAMES=60` 帧 + 中位数），
    //     并把抖动幅度记进 metrics（可自证换算精度）。
    if (upState.ac && audioCtx && upState.ac.state === 'running'
        && audioCtx.state === 'running'
        && upToPlayerOffsetSec == null
        && upToPlayerCandidates.length < T0_OFFSET_FRAMES) {
      upToPlayerCandidates.push(upState.ac.currentTime - audioCtx.currentTime);
    }
    if (!t0Established && t0OffsetCandidates.length < T0_OFFSET_FRAMES) {
      t0OffsetCandidates.push(sampleIndex - d.audioFrame16);
      if (t0OffsetCandidates.length >= 20) {
        const off16 = _median(t0OffsetCandidates);
        if (off16 != null) {
          const t0Up = off16 / 16000;   // ★ 上行域：抓流样本 0 的时刻
          // ★ 换算到 player 域（两个 AudioContext 的原点差）
          const dOff = upToPlayerCandidates.length
            ? _median(upToPlayerCandidates) : null;
          // ★ 换算精度自证：Δ 的采样抖动幅度（max−min）
          //   （两个 context 的 currentTime 各自独立更新 ⇒ 有抖动）
          let dSpread = null;
          if (upToPlayerCandidates.length) {
            let mn = Infinity, mx = -Infinity;
            for (const v of upToPlayerCandidates) {
              if (v < mn) mn = v;
              if (v > mx) mx = v;
            }
            dSpread = mx - mn;
          }
          if (dOff != null) {
            upToPlayerOffsetSec = dOff;
            // ★★★★★★ EXT-036 ①：**换算方向修正**（符号错误）。
            //   `dOff = up.ac.currentTime − player.ac.currentTime`
            //     （同一真实时刻，两个 context 的读数之差）
            //   ⇒ 「上行时钟上的时刻」换算到「player 时钟上的同一时刻」
            //     必须**减去** dOff：
            //         t_player = t_up − dOff
            //   ★ 旧实现写的是 `t0 = t0Up + dOff` ⇒ 符号反了
            //     ⇒ `t0` 变成负数（实测 −3.4091）⇒ `planned` 整体偏早
            //       **6.818 s** ⇒ 每段都被钳成「立即播」
            //     ⇒ 播放端与服务端差一个**常量** 6.818 s
            //       ⇒ 这就是 reviewer 实测的「server→player 恒定 ~7 s 缺口」。
            //   ★ 修后 `t0` 应 **≥ 0**（抓流样本 0 不会在 player 域的负时刻）
            //     ⇒ 顺带得到一个**自证判据**：`t0 >= 0`。
            t0 = t0Up - dOff;          // ★ player 域的 t0（符号正确）
          } else {
            t0 = t0Up;                 // 还没采到偏移 ⇒ 先用上行域值
          }
          t0Established = true;
          metrics.t0Axis = 'audio_clock';
          metrics.t0Sec = t0;
          metrics.t0Offset16 = off16;
          metrics.t0OffsetSamples = t0OffsetCandidates.length;
          metrics.t0UpSec = t0Up;
          metrics.t0UpPlayerOffsetSec = dOff;
          metrics.t0UpPlayerOffsetSpreadSec = dSpread;
          report({ kind: 't0_axis_set', t0Sec: t0, t0UpSec: t0Up,
                   upPlayerOffsetSec: dOff, upPlayerOffsetSpreadSec: dSpread,
                   offset16: off16,
                   n: t0OffsetCandidates.length,
                   oldT0Sec: upState.t0InitAc });
        }
      }
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

  // ★★ EXT-024 E：记「已收上行音频多少秒」+ 最后一帧的墙钟时刻
  //   ⇒ 状态条能判断「音频这一环是不是卡住了」。
  metrics.link.audioRecvSec = upState.sampleIndex / 16000;
  metrics.link.lastAudioAt = performance.now();

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
 *
 * ★★★★ EXT-027 ①：**抓流必须只来自目标标签页自己的音频**。
 *
 * ## 为什么要改（reviewer EXT-027 ① 的现场证据）
 *   EXT-026 的 A/B 两轮都走 `getDisplayMedia` ⇒ 抓的是**整机系统声音**
 *   ⇒ 把机器上别的程序当时在放的中文视频声音也抓进来了
 *   ⇒ 实测：`capture_sec=60` 但 `audioRecvSec=151.89`；
 *     ASR 出来的是**中文古装剧对白**（不是测试素材的英文）；
 *     于是 MT 的输入=中文、目标=中文 ⇒ **英译中这一步根本没测到**
 *     （实测 7/7 段 MT 文本 == ASR 文本）。
 *
 * ## 修法（两条路，按可用性降级）
 *   ① **首选 `chrome.tabCapture.capture({targetTabId})`**
 *      （Chrome/Edge **116+**，扩展页可调）⇒ **只**捕获指定标签页的音频，
 *      天然不含系统声音 ⇒ 这正是 EXT-027① 要的「只来自页面自己的音频」。
 *      目标 tabId 由 popup 在点「开始」时记进 `chrome.storage.local`。
 *   ② **兜底 `getDisplayMedia` + `preferCurrentTab`**
 *      （EXT-027① 原文：「如果还用 getDisplayMedia，就要设置
 *      `preferCurrentTab` 并且只要标签页的声音，不要整机声音」）
 *      ⇒ 约束里显式 `systemAudio:'exclude'` + `surfaceSwitching:'exclude'`
 *        + `selfBrowserSurface:'include'` + `preferCurrentTab:true`
 *        ⇒ 只要**当前标签页**、**排除系统声音**。
 *
 * ⚠️ 两条路都拿不到时**如实报错**（绝不静默回落到「整机声音」）。
 */
async function startCapture() {
  if (metrics.captureStarted) return { ok: true, already: true };
  let stream = null;
  let captureMode = null;
  let captureErr = null;
  try {
    const cfg = await chrome.storage.local.get({
      wsUrl: 'ws://127.0.0.1:8765/', token: '', targetTabId: null,
    });

    // ── ① 首选：tabCapture（只抓目标标签页）────────────
    // ★★ EXT-027① 真实缺陷修复（2026-11-01 实测）：
    //   旧实现调 `chrome.tabCapture.capture({audio, video, targetTabId})`
    //   ⇒ **Chrome 拒绝**：`No matching signature.`
    //   ⇒ 实测每轮都降级到 getDisplayMedia ⇒ 抓到的是**整机系统声音**
    //   ⇒ 英译中根本没测到。
    //   ★ 正确口径（查官方 API 核实）：
    //     `capture()` 的 options = `CaptureOptions`（**无** targetTabId）；
    //     `targetTabId` 属于 `getMediaStreamId(options)`。
    //   ⇒ 先拿流 id，再用 `chromeMediaSource: 'tab'` 消费。
    if (cfg.targetTabId != null && chrome.tabCapture
        && chrome.tabCapture.getMediaStreamId) {
      try {
        const streamId = await chrome.tabCapture.getMediaStreamId({
          targetTabId: Number(cfg.targetTabId),
        });
        if (!streamId) {
          throw new Error('getMediaStreamId 返回空'
            + '（目标标签页没有 activeTab 权限？）');
        }
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            mandatory: {
              chromeMediaSource: 'tab',
              chromeMediaSourceId: streamId,
            },
          },
          // 11-06 (reviewer): real path = delayed-picture window => capture the
          //   tab's VIDEO too (same stream id).  Capped at 1280x720/30 so the
          //   software VP8/VP9 encoder keeps up.  ?video=0 keeps audio-only.
          video: VIDEO_ENABLED ? {
            mandatory: {
              chromeMediaSource: 'tab',
              chromeMediaSourceId: streamId,
              maxWidth: 1280, maxHeight: 720, maxFrameRate: 30,
            },
          } : false,
        });
        captureMode = 'tabCapture';
      } catch (e) {
        captureErr = String((e && e.message) || e);
        report({ kind: 'tabcapture_failed', error: captureErr,
                 targetTabId: cfg.targetTabId });
      }
    }

    // ── ② 兜底：getDisplayMedia（约束成「当前标签页 + 不要系统声音」）──
    if (!stream) {
      const constraints = {
        video: { frameRate: 30 },
        audio: true,
        // ★ EXT-027①：只要标签页的声音，**排除整机系统声音**。
        systemAudio: 'exclude',
        surfaceSwitching: 'exclude',
        selfBrowserSurface: 'include',
        preferCurrentTab: true,
      };
      try {
        stream = await navigator.mediaDevices.getDisplayMedia(constraints);
        captureMode = 'getDisplayMedia';
      } catch (e) {
        const msg = String((e && e.message) || e);
        metrics.captureError = msg;
        report({ kind: 'capture_error', error: msg,
                 tabCaptureError: captureErr });
        return { ok: false, error: msg };
      }
    }

    capturedStream = stream;
    metrics.captureStarted = true;
    metrics.captureMode = captureMode;
    // ★★ EXT-027①：把「**为什么**降级」记进 metrics ⇒ 排查时不必猜。
    metrics.captureModeDetail = captureMode;
    metrics.tabCaptureError = captureErr || null;
    metrics.captureError = null;

    // ★★★ EXT-041：**媒体降速**（让画面追配音 ⇒ 压平累积斜率）。
    //   ★ **popup 已经注入并设置好了倍率**（用户手势 ⇒ activeTab 授权）
    //     ⇒ 这里**只读实测结果**，并**周期刷新**建议（实测 `tts_over_src`
    //     要跑出几段才有值 ⇒ 起流时多半拿不到）。
    //   ⚠️ 失败**不影响**抓流主流程，但必须**如实记录**（`metrics.slowdown`）。
    //   ⚠️ 这一步是**异步**的 ⇒ **不 await 阻塞**抓流（fire-and-forget）。
    try {
      const sdOn = await chrome.storage.local.get({ slowdownOn: true });
      // 11-08 用户：画面速度不调，只调配音语速 ⇒ 永久关闭媒体降速
      metrics.slowdownEnabled = false && !!(sdOn && sdOn.slowdownOn);
    } catch (e) { /* ignore */ }
    if (!metrics.slowdownEnabled) bridgeLog('降速已关闭（slowdownOn=false）');
    if (metrics.slowdownEnabled) {
      startLagRateController();   // 11-08: start before anything that can throw
      (async () => {
        try {
          // ① 先把 popup 的实测结果读进来（没记录 ⇒ null ⇒ **不臆造**）
          const rec = await readSlowdownRecord();
          if (rec) {
            metrics.slowdown = {
              applied: !!rec.applied,
              rate: (typeof rec.rate === 'number') ? rec.rate : null,
              videos: (typeof rec.videos === 'number') ? rec.videos : null,
              reason: rec.reason || null,
            };
            metrics.slowdownRecommended =
              (typeof rec.recommended === 'number') ? rec.recommended : null;
            report({ kind: 'slowdown_result', result: metrics.slowdown });
          }
          // ② 周期刷新建议（建议变了就重新设置）
          await refreshSlowdownRecommendation(cfg.wsUrl);
        } catch (e) {
          metrics.slowdown = { applied: false, rate: null, videos: null,
                               reason: '降速初始化失败：'
                                 + String((e && e.message) || e) };
          report({ kind: 'slowdown_result', result: metrics.slowdown });
        }
      })();
    }

    const vt = stream.getVideoTracks()[0];
    const at = stream.getAudioTracks()[0];
    if (at) {
      const st = at.getSettings ? at.getSettings() : {};
      metrics.sourceRate = st.sampleRate || 48000;
      setupOriginalAudio(new MediaStream([at]));
      // ★ P0① 音频上行（16 kHz → 桥接服务）
      const up = await startUplink(stream, cfg.wsUrl, cfg.token,
                                   captureMode);
      metrics.uplinkStart = up;
    }
    if (vt && VIDEO_ENABLED) await attachVideoTrack(vt);
    report({ kind: 'capture_ready', video: !!vt, audio: !!at,
             captureMode: captureMode,
             tabCaptureError: captureErr,
             uplink: metrics.uplinkStart });
    return { ok: true, captureMode: captureMode, uplink: metrics.uplinkStart };
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
  // ★★★ T-3：这里**不再硬编码 1.0**。
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
 * ★★ T-3：把「原声压低量（dB）」真正应用到原声总线上。
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
          // 11-06 (user: picture too small): canvas was stuck at 640x360.
          //   Match the source resolution; CSS scales it to ~80% of the window.
          cv.width = encSize.w; cv.height = encSize.h;
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
/**
 * ★★ EXT-024 A：**统一下行消息处理**。
 *
 * ## 为什么必须抽成共用函数（用户 10-31 实测的根因）
 *
 * 旧实现里 player 开了**两条** WS：
 *   * `connectBridge(..., 'player')` —— **有** onmessage（收 tts/echo）；
 *   * `startUplink()` 的 `upState.ws` —— **只发 pcm，没有 onmessage**。
 * 而服务端的 `tts` 任务只 `websocket.send` 回**本连接**
 * ⇒ 上行连接上会话产出的 `tts` 全被浏览器丢弃
 * ⇒ player 连接收不到 PCM，什么也不产出
 * ⇒ **用户只听到延迟原声，没有配音、没有字幕**。
 *
 * ⇒ 现在（服务端已改成按 token 广播）：
 *   * 两条连接**都**挂上 onmessage ⇒ 无论任务从哪条连接来都能收到；
 *   * 处理逻辑**共用**本函数（不重复实现）。
 *
 * ⚠️ **去重**：服务端可能把同一条 tts 广播给两条连接 ⇒ 同一段会收到两次
 *   ⇒ 用 `id` 去重（只排程一次），但**计数只加一次**。
 */
const seenDubIds = new Set();
const SEEN_DUB_CAP = 500;

// ★★★ EXT-026 ⑤：**当前会话标识**（由服务端的 hello_ack.session_id 给出）。
//   段 id 已带会话前缀（服务端改动）⇒ 跨会话**不会撞号**；
//   这里再加一道**客户端保险**：收到**新会话**的 hello_ack 时清空
//   `seenDubIds` ⇒ 即使连的是**旧服务端**（段 id 没前缀），
//   第二个会话的段也不会被误判成「重复段」而**静默丢掉**。
//   ⇒ 双保险：服务端改 id + 客户端清缓存。
let currentSessionId = null;

function handleBridgeMessage(m) {
  if (!m || typeof m !== 'object') return;
  const kind = m.type;
  if (kind === 'hello_ack') {
    if (m.delay_sec != null && isNaN(D_OVERRIDE)) { delaySec = m.delay_sec; recomputeEncCap(); }
    // ★★ EXT-024 F：服务端告诉客户端「现在是真实引擎还是回声」。
    metrics.link.mode = m.mode || null;
    metrics.link.enginesReady = !!m.engines_ready;
    metrics.link.pipeline = !!m.pipeline;
    // ★★★ EXT-026 ⑤：识别**新会话** ⇒ 清空去重缓存。
    //   ⚠️ 只有 session_id **变了**才清 ⇒ 同一会话的重复 hello_ack
    //     （两条 WS 各发一次）**不会**把已排程的段清掉。
    const sid = (m.session_id == null) ? null : String(m.session_id);
    if (sid && currentSessionId !== null && sid !== currentSessionId) {
      const n = seenDubIds.size;
      seenDubIds.clear();
      metrics.link.dubDupsCleared = (metrics.link.dubDupsCleared || 0) + n;
      report({ kind: 'session_reset', session_id: sid, cleared: n });
    }
    if (sid) currentSessionId = sid;
    report({ kind: 'hello_ack', delay_sec: m.delay_sec,
             sample_rate: m.sample_rate, segmentation: m.segmentation,
             mode: m.mode, engines_ready: m.engines_ready,
             pipeline: m.pipeline, session_id: sid });
  } else if (kind === 'echo' || kind === 'tts') {
    // ★★ EXT-024 A：去重 —— 同一段可能被广播到两条连接。
    const did = String(m.id || '');
    if (did) {
      if (seenDubIds.has(did)) {
        metrics.dubDup++;
        report({ kind: 'dub_dup', id: did });
        return;
      }
      seenDubIds.add(did);
      if (seenDubIds.size > SEEN_DUB_CAP) {
        // 丢最旧的（Set 保持插入顺序）
        const first = seenDubIds.values().next().value;
        seenDubIds.delete(first);
      }
    }
    metrics.echoRecv++;
    // ★★ EXT-024 E：这是「**已经下发到 player**」的证据 ⇒ 计数 +1。
    if (kind === 'tts') {
      metrics.link.dubDelivered++;
      metrics.link.lastTtsAt = performance.now();
      // ★★★★★★ EXT-036 ①：**墙钟**（与服务端同一时基）。
      //   ## 为什么必须加
      //     reviewer 的原话：「每段在同一个时钟上记下服务端发出时刻和
      //     插件收到时刻……先证明这 7 s 是哪一种」。
      //   ⇒ 服务端在 `tts` 消息里带 `srv_wall_ms`（`Date.now()` 同源时基）
      //     ⇒ 这里记 `ply_wall_ms`（`Date.now()`）
      //     ⇒ `ply_wall_ms − srv_wall_ms` = **真实下行耗时**（含收口→WS→解析）。
      //   ★ 这个量若很小（≪1 s）⇒ 7 s 缺口**不是**下行慢
      //     ⇒ 必然是**两端音频轴对不上**（⇒ 排程本身错了）。
      const _plyWall = Date.now();
      const _srvWall = (typeof m.srv_wall_ms === 'number') ? m.srv_wall_ms : null;
      const _dl = (_srvWall != null) ? (_plyWall - _srvWall) : null;
      // ★ 有界：只留最近 200 句（与 dubReadyAt 同量级）
      if (dubDownlinkMs.size > 200) {
        const fk = dubDownlinkMs.keys().next().value;
        dubDownlinkMs.delete(fk);
      }
      if (String(m.id || '')) dubDownlinkMs.set(String(m.id), _dl);
      metrics.dubDownlinkLastMs = _dl;
      // ★★★★★ EXT-035 验收项：「**首段就绪→起播 < 0.5 s**」。
      //   ## 为什么需要这个字段
      //     EXT-034 ③ 的根因分解里有一项是「**就绪→起播**」：
      //       跨时钟域 t0 换算 + 按序播放排队（实测 4.18~6.7 s）
      //     ⇒ 但**之前没有任何地方记录「就绪时刻」**
      //       ⇒ 这一项只能估算 ⇒ 归因不可核对。
      //   ## 口径（**同一个时钟域** ⇒ 可直接相减）
      //     `readyAtAc` = TTS 消息**到达 player** 时的 AudioContext 时刻
      //     `actual`    = 该段**实际起播**的 AudioContext 时刻（`start(when)`）
      //     ⇒ `readyToStartSec = actual − readyAtAc`
      //     ⇒ **不含** D、**不含**服务端起步耗时 ⇒ 就是纯 player 侧延迟
      //   ⚠️ 必须在**排程之前**取（`scheduleDub` 之前）
      //     ⇒ 否则把「排程等待」也算进去 ⇒ 口径混淆。
      if (audioCtx) {
        try {
          metrics.dubReadyAtAc = audioCtx.currentTime;
          metrics.dubReadyAtAcId = String(m.id || '');
          // ★ 按 id 记「就绪时刻」⇒ 排程时由 `noteDubScheduled` 取用
          const rid = String(m.id || '');
          if (rid) {
            dubReadyAt.set(rid, audioCtx.currentTime);
            // 有界：只留最近 200 句
            while (dubReadyAt.size > 200) {
              const fk = dubReadyAt.keys().next().value;
              dubReadyAt.delete(fk);
            }
          }
        } catch (e) { /* ignore */ }
      }
    }
    const r = scheduleDub(m);
    report({ kind: 'dub', id: m.id, t_start: m.t_start, t_end: m.t_end,
             planned: r && r.planned, requested: r && r.requested,
             isTts: kind === 'tts' });
  } else if (kind === 'stats') {
    // ★★ EXT-024 E：服务端报的段数/滞后 ⇒ 记进状态条。
    metrics.link.lastStatsAt = performance.now();
    // ★★ EXT-024 E 修正：**原来把三者都设成同一个 `m.n_segments`**
    //   ⇒ **口径失真**：只要服务端收口过一段，`n_segments` 就 >0，
    //     于是「TTS 从没出段」这种**最关键的故障信号**永远显示不出来。
    //   ⇒ 现在读服务端**真实分开**的三段计数
    //     （ext/bridge.py 的 Session.stats()：asr=有文本 /
    //      mt=有译文 / tts=有音频）。
    //   ⚠️ 兼容：老服务端没有这三个字段时，退回旧的 `n_segments`
    //     （保持向后兼容，不让状态条直接空掉）。
    const hasSplit = typeof m.asr_segments === 'number'
      || typeof m.mt_segments === 'number'
      || typeof m.tts_segments === 'number';
    if (hasSplit) {
      if (typeof m.asr_segments === 'number') {
        metrics.link.asrSegments = m.asr_segments;
      }
      if (typeof m.mt_segments === 'number') {
        metrics.link.mtSegments = m.mt_segments;
      }
      if (typeof m.tts_segments === 'number') {
        metrics.link.ttsSegments = m.tts_segments;
      }
    } else if (typeof m.n_segments === 'number') {
      metrics.link.asrSegments = m.n_segments;
      metrics.link.mtSegments = m.n_segments;
      metrics.link.ttsSegments = m.n_segments;
    }
    const mg = m.margin || {};
    if (typeof mg.last_segment_lag_sec === 'number') {
      metrics.link.lagSec = mg.last_segment_lag_sec;
    }
    if (typeof m.capture_mode === 'string') {
      metrics.link.captureMode = m.capture_mode;
    }
  }
}

function connectBridge(wsUrl, token, role) {
  return new Promise((resolve, reject) => {
    const w = new WebSocket(wsUrl);
    w.binaryType = 'arraybuffer';
    const t = setTimeout(() => { try { w.close(); } catch (e) {} reject(new Error('WS 超时')); }, 8000);
    w.onopen = () => {
      clearTimeout(t);
      metrics.link.wsConnected = true;
      metrics.link.wsError = null;
      metrics.link.startedAt = performance.now();
      // ★ 浏览器 WS 不能自定义请求头 ⇒ token 放在首个 hello 里
      w.send(JSON.stringify({
        type: 'hello', token, role, sample_rate: 16000, delay_sec: delaySec,
        // ★★ EXT-024 A/G：player 这条连接也要带上**面板设置**
        //   （服务端会把它们同步给产出段的那个会话）。
        target_lang: targetLang || null,
        voice: voicePref || null,
      }));
      resolve(w);
    };
    w.onerror = () => {
      clearTimeout(t);
      metrics.link.wsConnected = false;
      metrics.link.wsError = 'WS 失败（桥接服务未启动或端口不通）';
      reject(new Error('WS 失败'));
    };
    w.onclose = (ev) => {
      metrics.link.wsConnected = false;
      const r = bridgeCloseReason(ev);
      if (r) metrics.link.wsError = r;
    };
    w.onmessage = (ev) => {
      try {
        handleBridgeMessage(JSON.parse(ev.data));
      } catch (e) { /* ignore */ }
    };
  });
}

// v0.4.2：桥接主动关连接时，把原因翻译成人话（局域网模式同一时间只服务一个人）
function bridgeCloseReason(ev) {
  const code = ev && ev.code, why = String((ev && ev.reason) || '');
  if (code === 1013 || /busy/i.test(why)) return '桥接正在被另一台电脑使用（同一时间只服务一个人），请等对方停止后再点「开始」';
  if (code === 1008 && /peer/i.test(why)) return '桥接拒绝连接：这台电脑不在桥接允许的网段内';
  if (code === 1008 && /origin/i.test(why)) return '桥接拒绝连接：插件身份不对（请重新加载原版插件文件夹）';
  if (code === 1008) return '桥接拒绝连接：' + (why || '策略拒绝');
  return null;
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
  // ★★★ EXT-026 ③：重复段计数（跨会话撞号缺陷的可观测证据）
  'dubDup',
  'uplinkFrames', 'uplinkSeq', 'uplinkGaps', 'uplinkSkewMs',
  'pendingSchedDropped', 'subsDropped',
  'schedClamped', 'probeSchedClamped', 'encodeSkipped', 'encodeBacklogSkipped',
  // ★★ T-3：把设置的实际生效值也带上去（跨上下文可见）
  'duckDb', 'duckGain', 'duckDbApplied', 'subsOn',
  // ★★★ EXT-033 B/D：录音完整性与 player 端实测同步误差
  'dubPcmTapped', 'dubPcmError', 'dubPcmStored', 'dubPcmDropped',
  'dubSyncP50', 'dubSyncP95', 'dubSyncMax', 'dubSyncMin',
  't0Axis', 't0Sec', 't0Offset16', 't0OffsetSamples',
  't0UpSec', 't0UpPlayerOffsetSec', 't0UpPlayerOffsetSpreadSec',
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
  // ★★ T-3：暴露设置相关的可测状态（自测与诊断用）。
  settings: () => ({
    duckDb,
    duckGain: metrics.duckGain,
    duckDbApplied,
    duckGainApplied: origGain ? origGain.gain.value : null,
    subsOn,
    metricsSubsOn: metrics.subsOn,
    subsQueued: subs.length,
    // ★★ T-4：目标语言 / 音色（供自测核对「上报给服务端的值」）
    targetLang,
    voicePref,
  }),
  normalizeLang,
  normalizeVoice,
  dbToGain,
  // ★★★ EXT-026 ③：配音录音（录 player **实际播出**的音频）
  startDubRecording,
  stopDubRecording,
  // ★★★ EXT-033 B：等 `dataavailable` + `onstop` 都完成才 resolve
  //   （旧写法 stop() 后立刻取 blob ⇒ 文件被截断 ⇒
  //     ffmpeg 报 "File ended prematurely"）
  stopDubRecordingAsync,
  dubRecordingBlob,
  // ★★★ EXT-033 B：**无损** PCM 落盘（WAV）
  dubRecordingWav,
  // ★★★ EXT-033 D：player 端实测的同步误差明细（有符号）
  dubSyncStats: () => ({
    axis: metrics.t0Axis,
    t0Sec: metrics.t0Sec,
    t0Offset16: metrics.t0Offset16,
    t0UpSec: metrics.t0UpSec,
    t0UpPlayerOffsetSec: metrics.t0UpPlayerOffsetSec,
    t0UpPlayerOffsetSpreadSec: metrics.t0UpPlayerOffsetSpreadSec,
    errs: metrics.dubSyncErrs.slice(),
    // ★ onset 口径（**补充**，不代替主口径）
    errsOnset: metrics.dubSyncErrsOnset.slice(),
    detail: metrics.dubSyncDetail.slice(),
    p50: metrics.dubSyncP50, p95: metrics.dubSyncP95,
    max: metrics.dubSyncMax, min: metrics.dubSyncMin,
    lateMs: metrics.dubSyncLateMs.slice(),
    // ★★ EXT-034 ①：口径说明 + 覆盖率
    //   （reviewer 验收要「dubSyncDetail 段数 == TTS 段数」）
    basis: 'sched_start_vs_requested',
    basisNote: ('主口径 = 排程起点(actual) − (t0+t_start+D)；'
                + '实际起播取 AudioBufferSourceNode.start(when) 的 when'
                + '（Web Audio 采样精确）⇒ 覆盖全部有 TTS 的段。'
                + 'onset 口径见 errsOnset / detail[].onsetSignedErrMs。'),
    nScheduled: metrics.dubSyncDetail.length,
    nOnset: metrics.dubSyncErrsOnset.length,
    // ★★★★★★ EXT-036 ①：**下行耗时**（墙钟口径，逐段）。
    //   `ply_wall_ms − srv_wall_ms` = 服务端产出该段 → 插件收到该段。
    //   ★ 这是「7 s 缺口是哪种」的**直接判据**：
    //     P95 若 ≪ 0.3 s ⇒ 缺口**不是**下行慢 ⇒ 是**两端音频轴对不上**。
    downlinkMs: Array.from(dubDownlinkMs.entries())
      .map(([id, v]) => ({ id, ms: v })),
  }),
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
  // ★★★ EXT-026 修正：收口尾段（否则最后一句永远丢）
  flushUplink,
  // ★★ EXT-028：让服务端把余量统计落盘（margin.json），并**等回包**
  requestMarginDump,
  // ★★ EXT-036 ①/②：把实测的下行/排队/轴偏移上报服务端（可自测）
  reportClientMetrics,
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
/**
 * ★★ EXT-024 A：订阅 SW 的**运行时广播**（offscreen 转发过来的下行）。
 *
 * ## 为什么必须有这条
 *
 * 抓流有两条路径：
 *   * `player.js` 自己的 `startUplink()` —— 上行 WS **已经有** onmessage；
 *   * **offscreen** 路径（`offscreen.js` 的 `connectWs`）—— 旧实现
 *     **只计数不转发** ⇒ player 页永远收不到 tts ⇒ 没有配音、没有字幕。
 *
 * ⇒ 现在：offscreen 收到 tts ⇒ `sendMessage('sw-broadcast')`
 *   ⇒ SW 用 `chrome.runtime.sendMessage` **广播**给所有扩展页
 *   ⇒ 这里收到 ⇒ 交给同一个 `handleBridgeMessage`。
 *
 * ⚠️ **去重**：player 自己的 WS 可能也收到同一条 tts
 *   ⇒ `handleBridgeMessage` 里的 `seenDubIds` 按 id 去重
 *   ⇒ 只排程一次、只计数一次。
 */
function listenSwBroadcast() {
  try {
    if (!chrome.runtime || !chrome.runtime.onMessage) return;
    chrome.runtime.onMessage.addListener((msg) => {
      if (!msg || msg.target !== 'ext-dub') return false;
      try {
        handleBridgeMessage(msg.payload || {});
      } catch (e) { /* ignore */ }
      return false;
    });
  } catch (e) { /* ignore */ }
}
listenSwBroadcast();

// ── 11-06 (user): play the DUB on headphones when available ─────────────────
//   The delayed original stays on the default device (speakers); the dub is
//   moved to a headphone/headset output via MediaStreamDestination + <audio>
//   .setSinkId().  If no headphone-like device is found, nothing changes.
const HEADPHONE_RE = /耳机|耳麦|headphone|headset|earphone|earbud|buds|airpods|hands-?free|免提|蓝牙|bluetooth/i;
let dubSinkEl = null;
async function listOutputs() {
  let outs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audiooutput');
  if (outs.length && outs.every((d) => !d.label)) {
    // labels are hidden until the page holds a media permission: ask once, release at once
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((t) => t.stop());
      outs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audiooutput');
    } catch (e) { /* user declined: keep default routing */ }
  }
  return outs;
}
async function routeDubToHeadphones() {
  try {
    const pref = (await chrome.storage.local.get({ dubSink: 'auto' })).dubSink;
    if (pref === 'default') { metrics.dubSink = 'default（设置为默认设备）'; return; }
    const outs = await listOutputs();
    const real = outs.filter((d) => d.deviceId !== 'default' && d.deviceId !== 'communications');
    let pick = null;
    if (pref && pref !== 'auto') pick = real.find((d) => d.deviceId === pref || d.label === pref) || null;
    if (!pick) pick = real.find((d) => HEADPHONE_RE.test(d.label)) || null;
    metrics.dubSinkCandidates = outs.map((d) => d.label || '(无名称)');
    if (!pick) { metrics.dubSink = 'default（未发现耳机）'; report({ kind: 'dub_sink', sink: metrics.dubSink, outs: metrics.dubSinkCandidates }); return; }
    const dest = audioCtx.createMediaStreamDestination();
    dubSinkEl = new Audio();
    dubSinkEl.srcObject = dest.stream;
    await dubSinkEl.setSinkId(pick.deviceId);
    await dubSinkEl.play();
    dubBus.disconnect(audioCtx.destination);
    dubBus.connect(dest);
    metrics.dubSink = pick.label;
    report({ kind: 'dub_sink', sink: pick.label, outs: metrics.dubSinkCandidates });
  } catch (e) {
    metrics.dubSink = 'default（切换耳机失败：' + String((e && e.message) || e) + '）';
    report({ kind: 'dub_sink', sink: metrics.dubSink });
  }
}

async function boot() {
  const cfg = await chrome.storage.local.get({
    wsUrl: 'ws://127.0.0.1:8765/', token: '', delaySec: 20,
    // ★★ T-3：把 duckDb / subsOn 一并读出来（此前只有 popup 读，
    //   player 从不读 ⇒ 两个控件都是死控件）。
    duckDb: -15, subsOn: true,
    // ★★ T-4：把目标语言 / 音色也读出来（此前 player 从不读
    //   ⇒ 服务端拿不到 ⇒ 面板上的选择在这条路径上完全丢失）。
    targetLang: 'zh', voice: 'A',
  });
  delaySec = isNaN(D_OVERRIDE) ? (cfg.delaySec || 20) : D_OVERRIDE;
  recomputeEncCap();
  // ★★ T-3：应用原声压低量与字幕开关。
  duckDb = (cfg.duckDb === undefined || cfg.duckDb === null || cfg.duckDb === '')
    ? -15 : Number(cfg.duckDb);
  subsOn = (cfg.subsOn === undefined || cfg.subsOn === null) ? true : !!cfg.subsOn;
  // ★★ T-4：目标语言 / 音色（★ 用与 popup 相同的白名单口径，
  //   老配置里的语言全称迁移成引擎码 ⇒ 避免「选了但服务端不认」）。
  targetLang = normalizeLang(cfg.targetLang);
  voicePref = normalizeVoice(cfg.voice);
  applyDuckDb();     // origGain 还不存在 ⇒ 只记录意图，等抓流后自动套用
  metrics.subsOn = subsOn;

  // ★★ T-3：运行中改设置也要生效（用户在 popup 改了压低量/字幕，
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
        // ★★ T-4：目标语言 / 音色改了也要跟上
        //   （★ 注意：**已建立的 WS 连接不会重发 hello** ⇒
        //     本次改动只对**下一次**上行连接生效 ⇒ 如实记录，不假装即时生效）
        if ('targetLang' in changes) {
          targetLang = normalizeLang(changes.targetLang.newValue);
          report({ kind: 'settings', targetLang });
        }
        if ('voice' in changes) {
          voicePref = normalizeVoice(changes.voice.newValue);
          report({ kind: 'settings', voice: voicePref });
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
  // ★★★ EXT-033 D：记下**旧口径**的 t0（页面初始化时刻），
  //   好在 t0 被音频时钟纠正后，能把「差了多少」写进报告（可核对）。
  upState.t0InitAc = t0;
  metrics.t0Axis = 'page_init';
  metrics.t0Sec = t0;

  // 配音总线 + onset 检测
  dubBus = audioCtx.createGain();
  dubBus.gain.value = 1.0;
  dubBus.connect(audioCtx.destination);
  routeDubToHeadphones();   // 11-06: user wants the dub on headphones when present
  // ★★★ EXT-033 B：**无损 PCM 抓取支路**（并联、sink 静音 ⇒ 不重复出声）。
  //   ★ 为什么用 AudioWorklet 而不是 ScriptProcessor：
  //       ScriptProcessorNode 已在 Chrome 弃用，且跑在**主线程**上
  //       ⇒ 录长音频会把主线程拖住（EXT-003 记录过主线程尖峰问题）。
  //       AudioWorklet 跑在**音频线程**上 ⇒ 不抢主线程。
  try {
    await audioCtx.audioWorklet.addModule(chrome.runtime.getURL('dub-pcm-worklet.js'));
    dubPcmNode = new AudioWorkletNode(audioCtx, 'dub-pcm-processor', {
      numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1],
      processorOptions: { chunk: 4096 },
    });
    dubPcmNode.port.onmessage = (ev) => {
      const d = ev.data;
      if (!d || !d.pcm) return;
      const arr = new Float32Array(d.pcm);
      if (d.dumped) {
        // ★★ 整段 PCM（worklet 收尾时**一次性**投递 ⇒ 不会被端口队列压爆）
        dubPcmChunks = [arr];
        dubPcmBytes = arr.length * 4;
        dubPcmRate = d.sr || dubPcmRate;
        dubPcmDumpDone = true;
        metrics.dubPcmStored = d.stored;
        metrics.dubPcmDropped = d.dropped || 0;
        return;
      }
      if (!dubPcmActive) return;
      dubPcmChunks.push(arr);
      dubPcmBytes += arr.length * 4;
      dubPcmRate = d.sr || dubPcmRate;
    };
    dubPcmSink = audioCtx.createGain();
    dubPcmSink.gain.value = 0;      // ★ 这条支路**必须静音**
    dubBus.connect(dubPcmNode);
    dubPcmNode.connect(dubPcmSink);
    dubPcmSink.connect(audioCtx.destination);
    metrics.dubPcmTapped = true;
  } catch (e) {
    metrics.dubPcmTapped = false;
    metrics.dubPcmError = String((e && e.message) || e);
    report({ kind: 'dub_pcm_error', error: String((e && e.message) || e) });
  }
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

  setInterval(() => { pumpDecoder(); pumpDraws(); pumpSubs(); updateHud(); updateLinkBar(); }, 40);
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
    // 11-06 (reviewer): opened by the popup as the delayed-picture window
    //   (?auto=1) => start capturing the target tab right away.  The popup click
    //   already granted activeTab on that tab, so getMediaStreamId works here.
    if (qs.get('auto') === '1') {
      btn.style.display = 'none';
      const r = await startCapture();
      if (!r || !r.ok) {
        btn.style.display = 'inline-block';
        btn.textContent = '自动开始失败，点此重试：' + ((r && r.error) || '?');
      }
    }
  }

  // ★★★ EXT-026 修正：「停止并收尾」按钮 ⇒ 发 flush 让服务端跑完尾段。
  const btnF = document.getElementById('btnFlush');
  if (btnF) {
    btnF.addEventListener('click', async () => {
      const r = await flushUplink();
      report({ kind: 'flush_clicked', result: r });
      btnF.textContent = '已发收尾指令（等待最后一句…）';
    });
    btnF.style.display = 'inline-block';
  }

  // ★★★ EXT-026 修正：周期性问服务端要 stats（否则段数恒为 0）。
  //   ★ 上行 WS 还没建时 `pollStats` 会因为 readyState≠1 而跳过 ⇒ 安全。
  startStatsPolling();
}

// ══════════════════════════════════════════════════════════════
// ★★ EXT-024 E：链路状态条（**常驻**，并给出「哪一环卡住了」的原因）
// ══════════════════════════════════════════════════════════════
/**
 * 链路状态条的数据源与诊断。
 *
 * ## 为什么需要（用户 10-31 实测）
 *
 * 用户实测的现象是「只有延迟原声、没有配音、没有字幕」，
 * 但**界面上一句提示都没有** ⇒ 用户完全不知道卡在哪一环。
 *
 * ⇒ 现在常驻显示 5 个计数（已收音频 / ASR 段 / MT 段 / TTS 段 /
 *   已下发到 player 段）+ 当前滞后；
 *   **任何一环为 0 超过 15 秒** ⇒ 用**红字**写明具体原因：
 *   - WS 未连        ⇒ 桥接服务没启动 / 端口不通
 *   - 引擎未就绪     ⇒ 真实引擎还在加载（等 20–40 秒）
 *   - 没有音频轨     ⇒ tabCapture 没抓到音轨
 *   - 没收到下行     ⇒ 服务端没产出段（查 bridge.log 的段级日志）
 *
 * ⚠️ **如实**：没有数据就是 0/「—」，**绝不臆造**。
 */

/** 「某一环为 0 超过 N 秒」的判定阈值（EXT-024 E 明文：15 秒）。 */
const LINK_STALL_SEC = 15;

/**
 * 诊断链路状态。返回 {counts, reason, ok}。
 * ⚠️ 纯函数（不碰 DOM）⇒ 可被 node 沙箱 harness 直接验证。
 */
function diagnoseLink(link, nowMs) {
  const L = link || {};
  const now = (nowMs == null) ? 0 : nowMs;
  const since = (t) => (t == null ? null : (now - t) / 1000);

  const counts = {
    audioSec: Number(L.audioRecvSec || 0),
    asrSegments: Number(L.asrSegments || 0),
    mtSegments: Number(L.mtSegments || 0),
    ttsSegments: Number(L.ttsSegments || 0),
    dubDelivered: Number(L.dubDelivered || 0),
  };

  // ★ 音频这一环：从「开始」算起（还没收到第一帧时是 null ⇒ 不算「卡住」）
  const audioAge = since(L.lastAudioAt);
  const audioStalled = L.startedAt != null && audioAge != null
    && audioAge > LINK_STALL_SEC && counts.audioSec <= 0;

  const ttsAge = since(L.lastTtsAt);
  const ttsStalled = L.startedAt != null && counts.dubDelivered <= 0
    && ttsAge != null && ttsAge > LINK_STALL_SEC;

  let reason = null;
  let ok = true;

  if (!L.wsConnected) {
    reason = L.wsError || 'WS 未连接（桥接服务没启动？或开着 VPN？局域网使用要在桥接窗口勾「允许局域网访问」）';
    ok = false;
  } else if (L.mode === 'echo') {
    reason = '★ 回声模式（不是真实翻译配音）';
    ok = false;
  } else if (L.mode === 'real' && !L.enginesReady) {
    reason = '引擎未就绪（正在加载模型，等 20–40 秒）';
    ok = false;
  } else if (L.startedAt == null) {
    reason = null;      // 还没开始抓流 ⇒ 不报原因
    ok = true;
  } else if (audioStalled) {
    reason = '没有音频轨（tabCapture 没抓到声音）';
    ok = false;
  } else if (counts.asrSegments <= 0 && audioAge != null
             && audioAge > LINK_STALL_SEC) {
    reason = '收到音频但服务端没出段（查 bridge.log 的段级日志）';
    ok = false;
  } else if (ttsStalled) {
    reason = '没收到下行（服务端产出了段但没发到 player）';
    ok = false;
  } else if (counts.dubDelivered <= 0 && counts.ttsSegments > 0) {
    reason = '服务端有段但没下发到 player（下行路由断了）';
    ok = false;
  }

  return {
    counts,
    reason,
    ok,
    lagSec: (L.lagSec == null ? null : Number(L.lagSec)),
    mode: L.mode || null,
    enginesReady: !!L.enginesReady,
    pipeline: !!L.pipeline,
    wsConnected: !!L.wsConnected,
    audioAgeSec: audioAge,
  };
}

function updateLinkBar() {
  const el = document.getElementById('linkBar');
  if (!el) return;
  const d = diagnoseLink(metrics.link, performance.now());
  const c = d.counts;
  const parts = [
    '音频 ' + c.audioSec.toFixed(1) + 's',
    'ASR ' + c.asrSegments,
    'MT ' + c.mtSegments,
    'TTS ' + c.ttsSegments,
    '下发 ' + c.dubDelivered,
    '滞后 ' + (d.lagSec == null ? '—' : d.lagSec.toFixed(1) + 's'),
  ];
  el.textContent = parts.join(' | ');
  el.className = d.ok ? 'ok' : 'err';
  const rs = document.getElementById('linkReason');
  if (rs) {
    rs.textContent = d.reason || '';
    rs.className = d.ok ? 'ok' : 'err';
    rs.style.display = d.reason ? 'inline-block' : 'none';
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
  set('mSink', m.dubSink || '—');
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
