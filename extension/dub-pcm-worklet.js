/**
 * dub-pcm-worklet.js — AudioWorkletProcessor
 *   ★ EXT-033 B：**在 AudioContext 的 destination 之前**抓一份**未经压缩**的
 *   PCM（Float32）⇒ 落盘成 WAV。
 *
 * ## 为什么需要它
 *   EXT-032 的 player 录音只有 `MediaRecorder` 出来的 webm/opus：
 *   * 有损 ⇒ 互相关/SNR 的绝对值不可信；
 *   * `stop()` 之后 `dataavailable` / `onstop` 是**异步**的 ⇒
 *     旧实现立刻取 blob ⇒ **尾块丢失** ⇒
 *     ffmpeg 报 `File ended prematurely`（EXT-033 的第 1 条批评）。
 *   ⇒ 必须有一路**逐样本**的 PCM，才能：
 *     ① 证明录音**完整**（样本数 = 采样率 × 时长，可核对）；
 *     ② 用**无损**波形做逐段对比（时长比 / 互相关峰 / SNR）。
 *
 * ## 接线方式（见 player.js 的 initAudio）
 *   dubBus ──┬─────────────────────────► audioCtx.destination   （可听路径，不变）
 *            └─► dubPcmNode ─► tapSink(gain=0) ─► destination   （**静音**抓取支路）
 *
 *   ★ 为什么用「并联的静音支路」而不是把 dubBus 串进 worklet：
 *     串进去会改变可听路径（worklet 必须做无损拷贝，任何一次拷贝 bug
 *     都会直接**改掉用户听到的声音**）⇒ 风险不可接受。
 *     并联支路只多一条静音通路 ⇒ 即使抓取有 bug，也**不影响播放**。
 *
 * ## 采样率
 *   worklet 全局的 `sampleRate` = AudioContext 的采样率（本机 48 kHz）
 *   ⇒ 落盘 WAV 的采样率就是它，**不做任何重采样**（重采样会引入失真）。
 */
class DubPcmProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opt = (options && options.processorOptions) || {};
    this.chunk = opt.chunk || 4096;
    this.buf = new Float32Array(this.chunk);
    this.n = 0;
    this.frames = 0;
    this.active = false;      // ★ 只在录音期间采集（省 CPU）
    // ★ 主线程用 port 消息控制采集开关。
    //   ⚠️ 踩过的坑：主线程把 `dubPcmActive` 置 true 了，但 worklet 里的
    //   `this.active` 仍是 false ⇒ **一块 PCM 都没抓到**（pcmChunks=0），
    //   而现象只是「WAV 是空的」——极易误判成「没有录音」。
    //   ⇒ 采集开关**必须**通过 port 传到 worklet 内部才算数。
    //
    // ★★★ 第二个坑（本轮实测）：**每 4096 样本 postMessage 一次**
    //   ⇒ 245 s 录音就是 **2880 条消息**、主线程忙时端口队列被压爆
    //   ⇒ 实测**只收到前 1120 条**（95.5 s），后面的 PCM **全丢**
    //   ⇒ WAV 被截断（而 webm 是完整的 245 s）⇒ 这正是 EXT-033 要查的
    //     「录音被截断」类缺陷，换了个地方冒出来。
    //   ⇒ 修法：**worklet 自己累积**，收尾时**一次性**投递
    //     ⇒ 245 s 只有 1 条消息 ⇒ 不存在队列压力。
    this.store = new Float32Array(opt.initSamples || (1 << 20));
    this.stored = 0;
    this.dropped = 0;
    this.port.onmessage = (ev) => {
      const d = ev.data || {};
      if (d.cmd === 'start') {
        this.active = true;
        this.frames = 0;
        this.stored = 0;
        this.dropped = 0;
      } else if (d.cmd === 'stop') {
        this.active = false;
        this._flush();          // ★ 停之前把尾巴冲出去
        this._dump();
      } else if (d.cmd === 'dump') {
        this._dump();
      }
    };
  }

  /** 累积：满了就扩容（上限 4000 万样本 ≈ 833 s @48 kHz）。 */
  _append(chunk) {
    if (this.stored + chunk.length > this.store.length) {
      if (this.store.length >= (1 << 25)) {     // 33554432 样本 ≈ 699 s
        this.dropped += chunk.length;
        return;
      }
      let cap = this.store.length;
      while (cap < this.stored + chunk.length) cap *= 2;
      const bigger = new Float32Array(cap);
      bigger.set(this.store.subarray(0, this.stored));
      this.store = bigger;
    }
    this.store.set(chunk, this.stored);
    this.stored += chunk.length;
  }

  /** ★ 一次性把整段 PCM 投给主线程（transfer ⇒ 零拷贝）。 */
  _dump() {
    const out = this.store.slice(0, this.stored);
    this.port.postMessage({
      pcm: out.buffer, sr: sampleRate, dumped: true,
      stored: this.stored, dropped: this.dropped, frames: this.frames,
    }, [out.buffer]);
  }

  _flush() {
    if (!this.n) return;
    const c = this.buf.slice(0, this.n);
    this.n = 0;
    this.frames++;
    this._append(c);      // ★ 累积（不再每块 postMessage ⇒ 不会被队列压爆）
  }

  process(inputs, outputs) {
    const input = inputs[0];
    const ch0 = (input && input.length) ? input[0] : null;

    // ── 采集（仅在 active 时）──
    if (this.active && ch0 && ch0.length) {
      for (let i = 0; i < ch0.length; i++) {
        this.buf[this.n++] = ch0[i];
        if (this.n >= this.chunk) this._flush();
      }
    }

    // ── 直通（这条支路末端接的是 gain=0 的 sink ⇒ 不出声）──
    const output = outputs[0];
    if (output && output.length) {
      const o0 = output[0];
      if (o0) {
        if (ch0) {
          const n = Math.min(o0.length, ch0.length);
          for (let i = 0; i < n; i++) o0[i] = ch0[i];
          if (o0.length > n) o0.fill(0, n);
        } else {
          o0.fill(0);
        }
      }
    }
    return true;
  }
}

registerProcessor('dub-pcm-processor', DubPcmProcessor);
