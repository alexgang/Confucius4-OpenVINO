/**
 * ext0419_bg_harness.js — v0.4.19「保留背景音」插件侧行为测试（node，不需要浏览器）。
 *
 * 从 extension/player.js **原样抽出** scheduleBg / bgCover / bgDuckDub / bgStopAll / b64ToMultiBuffer /
 * dbToGain，在一个会**求值增益自动化**的假 Web Audio 时钟上跑，验证：
 *   1. 相邻背景块首尾相接：整段只放背景、原声压低总线关掉；最后一块结束后交还原声。
 *   2. 中间缺一块：缺块那段自动退回原声压低（不留空白），后面的块到了再切回背景。
 *   3. 迟到的块：只放还来得及的后半段（计 late）；整块都晚了 ⇒ 不放（计 dropped），原声顶上。
 *   4. 配音期间背景压低 4 dB；相邻两句之间不抬起；最后一句结束后恢复。
 *   5. 关开关 / 桥接报不可用：已排程的背景全部停掉，20 ms 内交还原声。
 *   6. 开关关闭时 scheduleBg 什么都不做（与 v0.4.18 行为一致）。
 * 用法：node tests/ext0419_bg_harness.js [path/to/player.js]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PLAYER = process.argv[2] ? path.resolve(process.argv[2])
  : path.join(path.dirname(__dirname), 'extension', 'player.js');
const src = fs.readFileSync(PLAYER, 'utf8');

function extractFunction(name) {
  const m = new RegExp(`^function\\s+${name}\\s*\\(`, 'm').exec(src);
  if (!m) throw new Error('missing function ' + name);
  let depth = 0, started = false;
  for (let i = src.indexOf('{', m.index); i < src.length; i++) {
    if (src[i] === '{') { depth++; started = true; }
    else if (src[i] === '}') { depth--; if (started && depth === 0) return src.slice(m.index, i + 1); }
  }
  throw new Error('unbalanced ' + name);
}

// ── fake Web Audio: AudioParam with evaluable automation ──
class Param {
  constructor(v) { this.v0 = v; this.ev = []; }
  get value() { return this.at(ctx.currentTime); }
  set value(v) { this.v0 = v; this.ev = []; }
  _add(e) { this.ev.push(e); this.ev.sort((a, b) => a.t - b.t || a.i - b.i); }
  setValueAtTime(v, t) { this._add({ k: 'set', v, t, i: this.ev.length }); }
  linearRampToValueAtTime(v, t) { this._add({ k: 'lin', v, t, i: this.ev.length }); }
  setTargetAtTime(v, t, tau) { this._add({ k: 'tgt', v, t, tau, i: this.ev.length }); }
  cancelScheduledValues(t) { this.ev = this.ev.filter((e) => e.t < t); }
  at(q) {
    let val = this.v0, tPrev = 0, tgt = null;
    for (const e of this.ev) {
      if (tgt && e.t > tgt.t) {            // finish an exponential approach up to this event
        const until = Math.min(q, e.t);
        if (until > tgt.t) val = tgt.v + (val - tgt.v) * Math.exp(-(until - tgt.t) / tgt.tau);
        tgt = null; if (q < e.t) return val;
      }
      if (e.k === 'lin') {
        if (q < e.t) return q <= tPrev ? val : val + (e.v - val) * (q - tPrev) / (e.t - tPrev);
        val = e.v; tPrev = e.t;
      } else if (e.t > q) {
        return tgt ? tgt.v + (val - tgt.v) * Math.exp(-(q - tgt.t) / tgt.tau) : val;
      } else if (e.k === 'set') { val = e.v; tPrev = e.t; }
      else if (e.k === 'tgt') { tgt = { v: e.v, t: e.t, tau: e.tau }; tPrev = e.t; }
    }
    if (tgt && q > tgt.t) val = tgt.v + (val - tgt.v) * Math.exp(-(q - tgt.t) / tgt.tau);
    return val;
  }
}
class Gain { constructor() { this.gain = new Param(1); } connect() {} }
class Buf {
  constructor(ch, n, sr) { this.numberOfChannels = ch; this.length = n; this.sampleRate = sr; this.d = [...Array(ch)].map(() => new Float32Array(n)); }
  get duration() { return this.length / this.sampleRate; }
  getChannelData(c) { return this.d[c]; }
}
const started = [];
class Source {
  constructor() { this.buffer = null; this.stopped = false; }
  connect() {}
  start(when, offset) { this.when = when; this.offset = offset || 0; started.push(this); }
  stop() { this.stopped = true; }
}
const ctx = {
  currentTime: 0,
  createBuffer: (ch, n, sr) => new Buf(ch, n, sr),
  createBufferSource: () => new Source(),
};

const sandbox = {
  console, Math, Number, Set, atob: (b) => Buffer.from(b, 'base64').toString('binary'),
  audioCtx: ctx, delaySec: 20, t0: 100, t0Src: null,
  bgKeep: true, bgCoveredUntil: 0, bgDuckUntil: 0, bgSources: new Set(), BG_DUCK_DB: -4,
  origMix: new Gain(), bgGate: new Gain(), bgDuck: new Gain(),
  metrics: { bg: { blocks: 0, late: 0, dropped: 0, reason: '' } },
  dubMeta: new Map(), dubBus: new Gain(), dubPlaybackEnd: 0,
};
sandbox.bgGate.gain.v0 = 0;
vm.createContext(sandbox);
for (const f of ['dbToGain', 'dubT0', 'b64ToMultiBuffer', 'bgCover', 'scheduleBg', 'bgDuckDub', 'bgStopAll', 'shiftDub']) {
  vm.runInContext(extractFunction(f), sandbox);
}
// let-bound globals inside the sandbox are reached through `this`; re-bind the function scope:
vm.runInContext('var __s = this;', sandbox);

const R = [];
function check(name, ok, detail) { R.push(ok); console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${ok || !detail ? '' : ' — ' + detail}`); }
function block(tStart, sec) {
  const n = Math.round(sec * 48000);
  const i16 = new Int16Array(n * 2).fill(1000);
  return { type: 'bg', t_start: tStart, sample_rate: 48000, channels: 2, n_frames: n,
           pcm: Buffer.from(i16.buffer).toString('base64') };
}
const base = 100 + 20;   // dubT0() + delaySec
const near = (a, b, e = 1e-3) => Math.abs(a - b) < e;

console.log('1. contiguous blocks');
ctx.currentTime = 105;
vm.runInContext('scheduleBg(' + JSON.stringify(block(0, 1)) + ')', sandbox);
vm.runInContext('scheduleBg(' + JSON.stringify(block(1, 1)) + ')', sandbox);
vm.runInContext('scheduleBg(' + JSON.stringify(block(2, 1)) + ')', sandbox);
const og = sandbox.origMix.gain, bgg = sandbox.bgGate.gain;
check('sources start exactly at dubT0+t_start+D', started.length === 3 && near(started[0].when, base) && near(started[2].when, base + 2));
check('before the first block: original on, bg off', og.at(base - 0.1) === 1 && bgg.at(base - 0.1) === 0);
const mid = [base + 0.5, base + 0.999, base + 1.0, base + 1.5, base + 2.0, base + 2.9].map((t) => [og.at(t), bgg.at(t)]);
check('whole run: original off, bg on (incl. seams)', mid.every(([o, b]) => o === 0 && b === 1), JSON.stringify(mid));
check('after the last block: original back', og.at(base + 3.05) === 1 && bgg.at(base + 3.05) === 0);

console.log('2. missing block => original fills the gap');
vm.runInContext('scheduleBg(' + JSON.stringify(block(4, 1)) + ')', sandbox);   // block 3 missing
check('gap [3,4): original on', og.at(base + 3.5) === 1 && bgg.at(base + 3.5) === 0);
check('block 4 plays bg again', og.at(base + 4.5) === 0 && bgg.at(base + 4.5) === 1);

console.log('3. late blocks');
ctx.currentTime = base + 5.4;            // block 5 [5,6) is 0.4 s late
const n0 = started.length;
vm.runInContext('scheduleBg(' + JSON.stringify(block(5, 1)) + ')', sandbox);
const s5 = started[started.length - 1];
check('late block: only the rest plays (offset), late counted', started.length === n0 + 1 && near(s5.offset, 0.43) && sandbox.metrics.bg.late === 1);
check('late block: bg from now+30 ms on', bgg.at(base + 5.5) === 1 && og.at(base + 5.5) === 0);
ctx.currentTime = base + 8;
vm.runInContext('scheduleBg(' + JSON.stringify(block(6, 1)) + ')', sandbox);
check('fully late block: dropped, nothing started', started.length === n0 + 1 && sandbox.metrics.bg.dropped === 1);

console.log('4. duck under the dub');
ctx.currentTime = 200;
const dk = sandbox.bgDuck.gain;
vm.runInContext('bgDuckDub(210, 2)', sandbox);
vm.runInContext('bgDuckDub(212.1, 1.5)', sandbox);      // next sentence 0.1 s later
const low = Math.pow(10, -4 / 20);
check('ducked to -4 dB during the first sentence', near(dk.at(211), low, 0.01));
check('stays ducked between adjacent sentences', near(dk.at(212.08), low, 0.02));
check('restored after the last sentence', dk.at(214.5) > 0.99);

console.log('5. switch off / bridge unavailable');
ctx.currentTime = 300;
vm.runInContext('scheduleBg(' + JSON.stringify({ ...block(181, 1) }) + ')', sandbox);  // plays at 301
const last = started[started.length - 1];
vm.runInContext('bgStopAll("")', sandbox);
check('scheduled bg stopped', last.stopped === true && sandbox.bgSources.size === 0);
check('original back within 20 ms, bg gate closed', og.at(300.03) === 1 && bgg.at(300.03) === 0 && og.at(301.5) === 1);

console.log('6. switch off => no-op');
vm.runInContext('bgKeep = false', sandbox);
const n1 = started.length;
vm.runInContext('scheduleBg(' + JSON.stringify(block(182, 1)) + ')', sandbox);
check('no source started while off', started.length === n1);

console.log('7. dub_shift (onset alignment)');
ctx.currentTime = 400;
vm.runInContext('bgKeep = true', sandbox);
const mk = (id, when, dur) => { const src = new Source(); src.start(when); const buf = new Buf(1, Math.round(dur * 24000), 24000);
  vm.runInContext(`dubMeta.set(${JSON.stringify(id)}, { src: __tmpSrc, buf: __tmpBuf, when: ${when} })`, Object.assign(sandbox, { __tmpSrc: src, __tmpBuf: buf })); return src; };
const a = mk('a', 410, 2), b = mk('b', 420, 2);                 // a planned at t=290 (410-120), b at t=300
vm.runInContext('shiftDub({ id: "a", t_start: 296.75 })', sandbox);   // wants 416.75
const ma = sandbox.dubMeta.get('a');
check('dub moved to the real onset; old source stopped', a.stopped && near(ma.when, 416.75));
vm.runInContext('shiftDub({ id: "a", t_start: 299.5 })', sandbox);    // wants 419.5 -> would hit b at 420
check('never pushed into the next dub', near(sandbox.dubMeta.get('a').when, 420 - 2 - 0.02));
ctx.currentTime = 419.95;
vm.runInContext('shiftDub({ id: "b", t_start: 301 })', sandbox);      // b starts in 50 ms -> too late
check('dub about to start is left alone', !b.stopped && sandbox.metrics.dubShiftTooLate === 1);

const ok = R.every(Boolean);
console.log(`\n${R.filter(Boolean).length}/${R.length} PASS`);
process.exit(ok ? 0 : 1);
