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
    // ★★★★★★ EXT-036 ⑤：静音块计数（没有配音时补写的样本块数）
    //   ⇒ 落盘后可直接核对「时间轴有没有被压缩」。
    this.silentBlocks = 0;
    this.port.onmessage = (ev) => {
      const d = ev.data || {};
      if (d.cmd === 'start') {
        this.active = true;
        this.frames = 0;
        this.stored = 0;
        this.dropped = 0;
        this.silentBlocks = 0;
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
      // ★ EXT-036 ⑤：静音块数（自证「没有配音时也在写样本」）
      silentBlocks: this.silentBlocks,
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

    // ★★★★★★ EXT-036 ⑤：**没有配音时也要写入静音样本**（时间轴不再被压缩）。
    //
    // ## 病根（reviewer EXT-036 ⑤ 的实测）
    //   `dub_player.wav` 只有 **99.10 s**，而 `record_stop.durationSec` 是
    //   **115.56 s**（`acTimeSec − acStartSec = 115.51 s`）⇒ **少了 16.4 s**。
    //   ⇒ 丢失发生在**中间**（seg_0→seg_1 的 7.16 s 空档、
    //     seg_9→seg_10 的 5.4 s 空档在录音里被吃掉）。
    //
    // ## 为什么会被吃掉
    //   `dubBus` 是个 GainNode，**每个配音段的 `AudioBufferSourceNode`
    //   播完就断开** ⇒ 没有配音时 `dubBus` **一个输入连接都没有**
    //   ⇒ Web Audio 判定这条支路「无输入」⇒ 给本 worklet 传
    //     **空输入数组**（`inputs[0].length === 0`）
    //   ⇒ 旧代码 `if (ch0 && ch0.length)` ⇒ **静音期间一块样本都不写**
    //   ⇒ WAV 的时间轴被**压缩**（静音段整段消失）。
    //
    // ## 修法
    //   本节点**永远**在渲染图里（它 → `dubPcmSink` → destination）
    //   ⇒ `process()` 每个渲染量子都会被调用
    //   ⇒ 即使输入为空，也**按渲染量子长度补写静音样本**
    //   ⇒ WAV 的样本数 = 采样率 × 实际经过的墙钟 ⇒ 时间轴**不再压缩**。
    //   ★ 静音样本的值为 0 ⇒ **不改变**音频内容（只补时间轴）。
    const output = outputs[0];
    const o0 = (output && output.length) ? output[0] : null;

    if (this.active) {
      if (ch0 && ch0.length) {
        for (let i = 0; i < ch0.length; i++) {
          this.buf[this.n++] = ch0[i];
          if (this.n >= this.chunk) this._flush();
        }
      } else if (o0 && o0.length) {
        // ★ 静音期：**补写等长的静音样本**（时间轴必须连续）
        for (let i = 0; i < o0.length; i++) {
          this.buf[this.n++] = 0;
          if (this.n >= this.chunk) this._flush();
        }
        this.silentBlocks++;
      }
    }

    // ── 直通（这条支路末端接的是 gain=0 的 sink ⇒ 不出声）──
    if (output && output.length) {
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
