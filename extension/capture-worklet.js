/**
 * capture-worklet.js — AudioWorkletProcessor
 *   把标签页音频（48 kHz）重采样到 **16 kHz 单声道 PCM16**，
 *   按 20–100 ms 打包成帧，每帧带 {seq, sample_index}。
 *
 * EXT-001 A 节原文：
 *   "AudioWorklet 重采样到 16 kHz 单声道 PCM16，每帧 20–100 ms，
 *    通过 WebSocket 发到桥接服务。每帧带 {seq, sample_index}。
 *    时间戳用累计采样数换算（不用墙钟，避免漂移），会话起点为 t0。"
 *
 * 关键设计：
 *  * **与播放共用同一个 AudioContext（48 kHz）** —— EXT-001 要求
 *    "画面和原声都用同一个 AudioContext 时钟"。所以降采样在本 worklet 里做，
 *    不能靠 AudioContext(sampleRate:16000)（那会变成两个时钟）。
 *  * 重采样用 **32 抽头 Blackman 窗 sinc FIR**（截止 8 kHz，48→16 抽取 3），
 *    不是朴素丢样本 —— 否则 8 kHz 以上会混叠，ASR 词错率会变差。
 *  * sample_index 是 **16 kHz 域的累计采样数**，跨帧连续 ⇒ 服务端可检出丢帧。
 *
 * ★ 已修的致命 bug（EXT-003 复测发现）：
 *   旧实现用**绝对**输出计数 outCount 计算 FIR 窗口所需的输入样本数
 *   （need = (outCount+1)*decim + CENTER + 1），而历史缓冲固定只有 512 个样本。
 *   ⇒ 输出到第 ~165 个样本（≈55 ms）时 need 永久超过 histLen，
 *     worklet 从此**再也不产出任何样本**，且 outLen 永远达不到
 *     minOut(320) ⇒ _flush() 从不执行 ⇒ **一帧都发不出去**
 *     （实测 frameCount=0）。
 *   修复：用**环形缓冲 + 相对索引**，窗口只回看最近几十个输入样本，
 *        历史长度不再随时间增长。
 *
 * ★ 滤波器抽头数从 32 提到 96（EXT-003 复测发现的第二个真实缺陷）：
 *   32 抽头 Blackman 窗 sinc 的过渡带太宽 —— 实测频响
 *   （截止 8 kHz）：
 *       TAPS= 32 : 7 kHz −2.5 dB / 8 kHz −6.0 dB / 9 kHz **−12.2 dB**
 *       TAPS= 48 : 9 kHz −16.7 dB
 *       TAPS= 64 : 9 kHz −22.3 dB
 *       TAPS= 96 : 9 kHz **−38.7 dB** / 1 kHz 0.00 dB  ✅
 *   ⇒ 9 kHz 只衰 12 dB ⇒ 抽取到 16 kHz 后 8 kHz 以上**会混叠**，
 *     ASR 词错率会变差。改用 96 抽头后阻带衰减到 −38.7 dB。
 */

const TAPS = 96;
const CENTER = 47;          // 窗口相对中心（(TAPS-1)/2 = 47.5，取 47）
const HB = 1024;            // 环形缓冲大小（> TAPS + decim*2 即可）

// 32 抽头 Blackman 窗 sinc 低通（截止 = 8 kHz / 48 kHz = 1/6）
function buildFir() {
  const fc = 8000 / 48000;      // 归一化截止频率（相对 48 kHz）
  const h = new Float32Array(TAPS);
  let sum = 0;
  for (let k = 0; k < TAPS; k++) {
    const x = k - CENTER;
    // sinc(2 * fc * x)
    const sx = 2 * fc * x;
    const s = Math.abs(sx) < 1e-9 ? 1 : Math.sin(Math.PI * sx) / (Math.PI * sx);
    // Blackman 窗
    const w = 0.42 - 0.5 * Math.cos(2 * Math.PI * k / (TAPS - 1))
                    + 0.08 * Math.cos(4 * Math.PI * k / (TAPS - 1));
    h[k] = s * w;
    sum += h[k];
  }
  for (let k = 0; k < TAPS; k++) h[k] /= sum;   // 归一化（DC 增益 1）
  return h;
}

const FIR = buildFir();

class CaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opt = (options && options.processorOptions) || {};
    this.targetRate = opt.targetRate || 16000;
    this.inRate = opt.inputRate || sampleRate;
    this.frameMinMs = opt.frameMinMs || 20;
    this.frameMaxMs = opt.frameMaxMs || 100;

    // 抽取比 = 输入率 / 输出率（本机 48k→16k ⇒ 3）
    this.decim = Math.max(1, Math.round(this.inRate / this.targetRate));
    this.needsFir = this.decim > 1;

    this.minOut = Math.max(1, Math.round(this.targetRate * this.frameMinMs / 1000));
    this.maxOut = Math.max(1, Math.round(this.targetRate * this.frameMaxMs / 1000));

    // ★ 环形输入缓冲（修复：不再用固定 512 长度的线性历史）
    this.hist = new Float32Array(HB);
    this.histWrite = 0;
    this.totalIn = 0;        // 累计输入样本数

    this.outCount = 0;       // 已产生的输出样本数（= 16 kHz 域采样计数）
    this.totalOut = 0;       // 已 flush 的输出样本数（= sample_index 基准）
    this.out = new Int16Array(this.maxOut);
    this.outLen = 0;
    this.seq = 0;

    // 诊断计数
    this.processCalls = 0;
    this.emptyCalls = 0;
  }

  /** 输入一个样本，抽取成 16 kHz 样本（FIR 滤波） */
  _pushIn(s) {
    this.hist[this.histWrite] = s;
    this.histWrite = (this.histWrite + 1) % HB;
    this.totalIn++;

    if (!this.needsFir) {
      // 同率：直接直通（每 decim 个取 1 个）
      if (this.totalIn % this.decim === 0) {
        const idx = (this.histWrite - 1 + HB) % HB;
        this._emit(this.hist[idx]);
      }
      return;
    }

    // 需要覆盖到窗口最大索引 (outCount*decim + CENTER + TAPS-1-CENTER)
    const need = (this.outCount + 1) * this.decim + CENTER + this.decim;
    if (this.totalIn < need) return;

    const base = this.outCount * this.decim - CENTER;
    let acc = 0;
    for (let k = 0; k < TAPS; k++) {
      const idx = base + k;
      if (idx < 0) continue;
      acc += FIR[k] * this.hist[idx % HB];
    }
    this._emit(acc);
  }

  _emit(v) {
    this.outCount++;
    let s = v;
    if (s > 1) s = 1; else if (s < -1) s = -1;
    this.out[this.outLen++] = Math.round(s * 32767);
    if (this.outLen >= this.maxOut) this._flush();
  }

  _flush() {
    if (this.outLen === 0) return;
    const pcm = this.out.slice(0, this.outLen);
    const start = this.totalOut;
    this.totalOut += this.outLen;
    this.outLen = 0;
    this.port.postMessage(
      { pcm: pcm.buffer, sampleIndex: start, seq: this.seq++,
        inSamples: this.totalIn, processCalls: this.processCalls,
        outSamples: this.totalOut },
      [pcm.buffer]
    );
  }

  process(inputs) {
    this.processCalls++;
    const input = inputs[0];
    if (!input || input.length === 0) { this.emptyCalls++; return true; }
    const ch0 = input[0];
    if (!ch0 || ch0.length === 0) { this.emptyCalls++; return true; }

    // 多声道 → 取平均（转单声道）
    const nch = input.length;
    if (nch === 1) {
      for (let i = 0; i < ch0.length; i++) this._pushIn(ch0[i]);
    } else {
      for (let i = 0; i < ch0.length; i++) {
        let acc = 0;
        for (let c = 0; c < nch; c++) acc += input[c][i];
        this._pushIn(acc / nch);
      }
    }

    if (this.outLen >= this.minOut) this._flush();
    return true;
  }
}

registerProcessor('capture-processor', CaptureProcessor);
