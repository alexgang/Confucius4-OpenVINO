class ProbeProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.n = 0;
  }
  process(inputs, outputs) {
    this.n++;
    const ch = inputs[0] && inputs[0][0];
    if (ch && outputs[0] && outputs[0][0]) { outputs[0][0].set(ch); }
    if (this.n % 50 === 0) this.port.postMessage({ n: this.n });
    return true;
  }
}
registerProcessor('probe', ProbeProcessor);
