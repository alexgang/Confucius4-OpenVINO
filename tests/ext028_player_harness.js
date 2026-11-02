/**
 * ext028_player_harness.js — ★★★ EXT-028 ①⑤：**插件侧失真链路**行为级测试载体
 *
 * ## 验什么（reviewer EXT-028 明文 + EXT-027 ⑤）
 *
 * EXT-028 第 1 条要求逐段对比三份音频，找出「是哪一环开始失真」。
 * 本脚本验**插件那一环**的三个具体行为：
 *
 *   1. **采样率解析**（EXT-028 ① 的根因 D1）
 *      旧实现：`b64ToAudioBuffer(msg.pcm24k, msg.sample_rate || 16000)`
 *      ⇒ 服务端没带 `sample_rate` ⇒ 24 kHz 波形按 16 kHz 重建
 *      ⇒ **快 1.5× + 升调 ≈7 个半音** ⇒ 用户「基本听不清」。
 *      ⇒ 现在：`resolvePcmSampleRate()` —— 服务端声明为准；缺失才兜底，
 *        且**如实计数** `metrics.pcmRateAssumed`（不静默）。
 *
 *   2. **按序播放**（EXT-027 ⑤）
 *      `when = max(planned, 上一句结束时刻, currentTime + 5ms)`
 *      ⇒ 两句不能叠在一起 ⇒ 顺延量计入 `metrics.dubRescheduled`。
 *
 *   3. **不因钳位而叠播**（EXT-028 的长段静音/叠播成因之一）
 *      多句 planned 都在过去 ⇒ 全部挤到 currentTime+5ms ⇒ 叠播。
 *
 * ## ★ 为什么从**真源码**里抽函数（而不是复刻）
 *
 * `resolvePcmSampleRate` / `scheduleDub` 是**真代码**（`extension/player.js`）
 * ⇒ 抽取后放进带桩的沙箱执行 ⇒ 验的是真逻辑。
 * ⚠️ 沙箱里的 `metrics` / `report` / `audioCtx` 都是**桩**
 *   （只记录调用，不改变被测逻辑）。
 *
 * ## ★ 可证伪（反证）
 *
 * C1c / C2c / C3c 是**反证**：把 `player.js` 的采样率解析或顺序守卫改坏
 * ⇒ **本脚本的 C1b/C2b 必须变红** ⇒ 若仍报 PASS，说明断言恒真。
 * ⚠️ 反证用**子进程**跑（环境变量 EXT028_CHILD=1 ⇒ 子进程**不递归**跑
 *   C1c/C2c/C3c，否则无限递归）。
 *
 * 用法：
 *   node tests/ext028_player_harness.js [player.js 路径]
 * 退出码 0 = 全部通过。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const os = require('os');
const cp = require('child_process');

const ROOT = path.dirname(__dirname);
const PLAYER = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(ROOT, 'extension', 'player.js');
// ★ 子进程标志：反证时由父进程设置 ⇒ 子进程**不递归**跑反证组
const IS_CHILD = process.env.EXT028_CHILD === '1';

const psrc = fs.readFileSync(PLAYER, 'utf8');

const RESULTS = [];
function check(name, cond, detail) {
  RESULTS.push({ name, ok: !!cond });
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}`
    + (cond || !detail ? '' : ` — ${detail}`));
}

/** 从源码里**原样抽出**一个顶层函数（含其完整花括号体）。 */
function extractFunction(src, name, label) {
  const re = new RegExp(`^function\\s+${name}\\s*\\(`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到函数 ${name}`);
  let depth = 0;
  let started = false;
  for (let i = src.indexOf('{', m.index); i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') {
      depth--;
      if (started && depth === 0) return src.slice(m.index, i + 1);
    }
  }
  throw new Error(`函数 ${name} 的花括号不配对`);
}

/** 从源码里**原样抽出**一个顶层 const 声明。 */
function extractConst(src, name, label) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*[^;]+;`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到常量 ${name}`);
  return m[0];
}

/** 从源码里**原样抽出**一个顶层对象字面量 const（如 `ADAPT = {...}`）。 */
function extractConstBlock(src, name, label) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*\\{`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到常量块 ${name}`);
  let depth = 0;
  let started = false;
  for (let i = src.indexOf('{', m.index); i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') {
      depth--;
      if (started && depth === 0) {
        const end = src.indexOf(';', i);
        return src.slice(m.index, end > 0 ? end + 1 : i + 1);
      }
    }
  }
  throw new Error(`常量块 ${name} 的花括号不配对`);
}

/**
 * 把 `scheduleDub` 里的**顺序守卫**整段去掉（用于反证）。
 *
 * ★ 定位方式（**不依赖注释文案**）：
 *   ① 找到 `const prevEnd = dubPlaybackEnd;` 那一行；
 *   ② 往上找最近的 `if (!isProbe) {`（那**就是**顺序守卫的入口）；
 *   ③ 往下找 `src.start(when);`（守卫块在这之前结束）；
 *   ④ 把 ②→③ 之间的整块替换成 `src.start(when);`。
 *
 * ⇒ 改完后：两句会**同时**起播 ⇒ C2b（顺延到上一句结束）必须 FAIL。
 */
function removeOrderGuard(src) {
  const anchor = src.indexOf('const prevEnd = dubPlaybackEnd;');
  if (anchor < 0) return src;
  const start = src.lastIndexOf('if (!isProbe) {', anchor);
  if (start < 0) return src;
  const end = src.indexOf('src.start(when);', anchor);
  if (end < 0) return src;
  // ★ 只删「守卫块」本体 ⇒ 保留 `src.start(when);`
  return src.slice(0, start) + 'src.start(when);' + src.slice(end + 'src.start(when);'.length);
}

/**
 * 建一个带桩的沙箱，把抽出来的**真函数**放进去跑。
 * ★ `metrics` / `report` / `audioCtx` / `b64ToAudioBuffer` 都是**桩**：
 *   桩只负责记录调用，不改变被测逻辑。
 */
function makeSandbox(opts) {
  const o = opts || {};
  const scheduled = [];
  const reported = [];
  const audioCtx = {
    currentTime: o.currentTime == null ? 10.0 : o.currentTime,
    createBufferSource: () => {
      // ★★★ EXT-034 ①：真代码的顺序是
      //   `src.start(when)`（1256 行）**先**、`src.onended = ...`（1319 行）**后**
      //   ⇒ 桩必须**保留同一个对象**（`rec.src`），
      //     让测试在 onended 被赋值之后再取。
      const rec = { when: null, onended: null, dur: null, src: null };
      const node = {
        buffer: null,
        connect: () => {},
        start: (when) => { rec.when = when; scheduled.push(rec); },
        stop: () => {},
      };
      rec.src = node;
      return node;
    },
    createBuffer: (ch, len, sr) => ({ duration: len / sr, sampleRate: sr }),
  };
  const sandbox = {
    console,
    performance: { now: () => (o.nowMs == null ? 0 : o.nowMs) },
    setTimeout, clearTimeout, isNaN,
    delaySec: o.delaySec == null ? 10 : o.delaySec,
    t0: o.t0 == null ? 0 : o.t0,
    audioCtx,
    // ★ 两条总线（真实代码里是 AudioNode）⇒ 这里给**空桩**
    dubBus: { kind: 'dubBus' },
    probeBus: { kind: 'probeBus' },
    // ★ scheduleDub 尾部会用到的几个全局
    pendingSched: [],
    subsOn: false,
    scheduleSub: () => {},
    adaptSpeedHistory: [],
    metrics: {
      pcmRateAssumed: 0,
      dubRescheduled: 0,
      dubRescheduleDelaySec: 0,
      schedClamped: 0,
      dubRateLast: 0,
      adaptSpeed: 1.0,
      adaptTotalSpeed: 1.0,
      adaptLagSec: 0,
      adaptLagPeak: 0,
      adaptSpeedHistory: [],
      pendingSchedDropped: 0,
      subsDropped: 0,
      // ★★★ EXT-034 ①：`noteDubEnded` 会写这些字段
      //   （dubSyncErrs / dubSyncDetail / dubSyncLateMs / dubSyncErrsOnset
      //     + 四个分位数）⇒ 桩里必须**先声明**，否则赋值到未声明变量
      //     在 vm 沙箱里会抛 ReferenceError。
      dubSyncErrs: [],
      dubSyncErrsOnset: [],
      dubSyncDetail: [],
      dubSyncLateMs: [],
      dubSyncP50: null,
      dubSyncP95: null,
      dubSyncMax: null,
      dubSyncMin: null,
      link: { dubDelivered: 0 },
    },
    // ★ `pct` 是真代码里的辅助函数（EXT-033 引入的**缓存版**）
    //   ⇒ `noteDubEnded` 会用它算 P50/P95 ⇒ 沙箱要提供。
    //   （用**真实现**而不是桩 ⇒ 验的是真逻辑）
    _pctCache: new WeakMap(),
    __scheduled: scheduled,
    __reported: reported,
    __audioCtx: audioCtx,
    report: (m) => { reported.push(m); },
    // ★ b64ToAudioBuffer 的桩：**按传入的采样率**建 buffer
    //   ⇒ 时长 = 样本数 / 采样率 ⇒ 能直接验「采样率错配 ⇒ 时长错」
    b64ToAudioBuffer: (b64, sr) => {
      const nBytes = Buffer.from(String(b64), 'base64').length;
      const nSamples = Math.floor(nBytes / 2);
      sandbox.__lastSr = sr;
      return { duration: nSamples / sr, sampleRate: sr, length: nSamples };
    },
  };
  const code = [
    extractConst(psrc, 'DEFAULT_DUB_SAMPLE_RATE', 'player.js'),
    extractConstBlock(psrc, 'ADAPT', 'player.js'),
    extractConst(psrc, 'PENDING_SCHED_CAP', 'player.js'),
    extractFunction(psrc, 'resolvePcmSampleRate', 'player.js'),
    // ★★★ EXT-034 ①：`scheduleDub` 现在会调 `noteDubScheduled()`
    //   并挂 `src.onended` ⇒ 沙箱必须带上**真实现**
    //   （否则 ReferenceError ⇒ 整个 harness 崩）。
    extractFunction(psrc, 'noteDubScheduled', 'player.js'),
    extractFunction(psrc, 'noteDubEnded', 'player.js'),
    // ★ `pct` 是**真代码**（EXT-033 的缓存版分位数）⇒ 抽出来用
    //   （`noteDubEnded` 用它算 P50/P95 ⇒ 验的是真逻辑）
    extractFunction(psrc, 'pct', 'player.js'),
    extractFunction(psrc, 'scheduleDub', 'player.js'),
  ].join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { resolvePcmSampleRate, scheduleDub };`,
    sandbox, { filename: PLAYER });
  // ★ `dubPlaybackEnd` 是 **let** 声明（不是 const）⇒ 单独抽出来注入
  const m = /let\s+dubPlaybackEnd\s*=\s*[^;]+;/.exec(psrc);
  if (!m) throw new Error('player.js 里找不到 `let dubPlaybackEnd = ...` 声明');
  vm.runInContext(m[0], sandbox, { filename: PLAYER });
  // ★★ EXT-034 ①：`dubStarted` 是 **const**（Map）⇒ 也抽出来注入
  const ms = /const\s+dubStarted\s*=\s*new Map\(\)\s*;/.exec(psrc);
  if (!ms) throw new Error('player.js 里找不到 `const dubStarted = new Map();` 声明');
  vm.runInContext(ms[0], sandbox, { filename: PLAYER });
  // ★★★★★ EXT-035：`dubReadyAt` 也是 **const**（Map）⇒ 同样注入
  const mr = /const\s+dubReadyAt\s*=\s*new Map\(\)\s*;/.exec(psrc);
  if (!mr) throw new Error('player.js 里找不到 `const dubReadyAt = new Map();` 声明');
  vm.runInContext(mr[0], sandbox, { filename: PLAYER });
  // ★ 把 `dubReadyAt` 暴露到沙箱上（供 C5 核对「就绪时刻」）
  vm.runInContext('globalThis.__dubReadyAt = dubReadyAt;', sandbox,
                  { filename: PLAYER });
  return sandbox;
}

// ══════════════════════════════════════════════════════════════════
// C1：采样率解析（EXT-028 ① 的根因 D1）
// ══════════════════════════════════════════════════════════════════
console.log('\n[C1] ★ 采样率以服务端声明为准；缺失才兜底且计数');
{
  const sb = makeSandbox({});
  const { resolvePcmSampleRate } = sb.__api;

  const a = resolvePcmSampleRate({ sample_rate: 24000 });
  check('★ C1a 服务端声明 24000 ⇒ rate=24000, assumed=false',
    a.rate === 24000 && a.assumed === false, JSON.stringify(a));

  const b = resolvePcmSampleRate({ sample_rate: '16000' });
  check('★ C1b 字符串 "16000" 也认（Number 转换）',
    b.rate === 16000 && b.assumed === false, JSON.stringify(b));

  const before = sb.metrics.pcmRateAssumed;
  const c = resolvePcmSampleRate({});
  check('★ C1c 字段缺失 ⇒ 兜底 24000（**不是 16000**）',
    c.rate === 24000 && c.assumed === true, JSON.stringify(c));
  check('★ C1d 兜底时如实计数 pcmRateAssumed（不静默）',
    sb.metrics.pcmRateAssumed === before + 1,
    `${before} → ${sb.metrics.pcmRateAssumed}`);

  // ★★ 反证：把「兜底 24000」改回「兜底 16000」⇒ C1c 必须 FAIL
  //   ⚠️ 反证只在**父进程**做（子进程跑真断言，不递归跑反证）
  if (!IS_CHILD) {
    const broken = psrc.replace(
      /const DEFAULT_DUB_SAMPLE_RATE = \d+;/,
      'const DEFAULT_DUB_SAMPLE_RATE = 16000;');
    if (broken !== psrc) {
      const tmp = path.join(os.tmpdir(),
                            'ext028_broken1_player_' + Date.now() + '.js');
      fs.writeFileSync(tmp, broken, 'utf8');
      const r = cp.spawnSync(process.execPath, [__filename, tmp],
        { encoding: 'utf8',
          env: Object.assign({}, process.env, { EXT028_CHILD: '1' }) });
      fs.unlinkSync(tmp);
      const out = r.stdout || '';
      check('★★ C1e 改坏后 C1c **必须 FAIL**',
        out.includes('[FAIL] ★ C1c'),
        '改坏后的输出尾部：' + out.slice(-500));
    } else {
      check('★★ C1e 改坏后 C1c **必须 FAIL**', false,
        '没找到 DEFAULT_DUB_SAMPLE_RATE 声明（无法反证）');
    }
  }
}

// ══════════════════════════════════════════════════════════════════
// C2：按序播放，两句不叠（EXT-027 ⑤ / EXT-028 叠播成因）
// ══════════════════════════════════════════════════════════════════
console.log('\n[C2] ★ 配音按 t_start 顺序播放，后一句不与前一句重叠');
{
  // ⚠️ currentTime 必须**早于** planned，否则会被钳位
  //   （钳位是真实逻辑：排程时刻已在过去 ⇒ 立即播 ⇒ 但那会掩盖
  //     「顺序守卫」的作用 ⇒ 这里把 currentTime 设在 planned 之前）
  const sb = makeSandbox({ currentTime: 5.0, t0: 0, delaySec: 10 });
  const { scheduleDub } = sb.__api;

  // 24 kHz / 1 s 的 PCM（24 000 样本 = 48 000 字节）⇒ duration = 1.0 s
  const pcm1s24k = Buffer.alloc(48000).toString('base64');

  // 第 1 句：t_start=0 ⇒ planned = 0 + 0 + 10 = 10.0
  scheduleDub({ id: 'seg_0', t_start: 0, pcm24k: pcm1s24k,
                sample_rate: 24000 });
  check('★ C2a 第 1 句按 planned 排程（when=10.0）',
    sb.__scheduled.length === 1 && sb.__scheduled[0].when === 10.0,
    JSON.stringify(sb.__scheduled));

  // 第 2 句：t_start=0.2 ⇒ planned = 10.2 < 上一句结束 11.0
  //   ⇒ 必须顺延到 11.0（否则叠播）
  scheduleDub({ id: 'seg_1', t_start: 0.2, pcm24k: pcm1s24k,
                sample_rate: 24000 });
  check('★ C2b 第 2 句被顺延到上一句结束（11.0）',
    sb.__scheduled.length === 2 && Math.abs(sb.__scheduled[1].when - 11.0) < 1e-6,
    JSON.stringify(sb.__scheduled));
  check('★ C2c 顺延被计数 dubRescheduled',
    sb.metrics.dubRescheduled === 1, `${sb.metrics.dubRescheduled}`);
  check('★ C2d 顺延量被累计（0.8 s）',
    Math.abs((sb.metrics.dubRescheduleDelaySec || 0) - 0.8) < 0.02,
    `${sb.metrics.dubRescheduleDelaySec}`);
  check('★ C2e 顺延事件被 report（可观测）',
    sb.__reported.some((r) => r.kind === 'dub_rescheduled'),
    JSON.stringify(sb.__reported.slice(-2)));
  check('★ C2f 两句**不重叠**（第 2 句开始 ≥ 第 1 句结束）',
    sb.__scheduled[1].when >= sb.__scheduled[0].when + 1.0,
    JSON.stringify(sb.__scheduled));

  // ★★ 反证：把顺序守卫整段去掉 ⇒ C2b 必须 FAIL
  //   ⚠️ 反证只在**父进程**做（子进程跑真断言，不递归跑反证）
  //   ⚠️ 定位方式：**按代码**（`const prevEnd = dubPlaybackEnd;` 这一行）
  //     往上找最近的 `if (!isProbe) {`、往下找 `src.start(when);`
  //     ⇒ 不依赖注释文案 ⇒ reviewer 改注释不会误伤反证。
  if (!IS_CHILD) {
    const broken = removeOrderGuard(psrc);
    if (broken !== psrc) {
      const tmp = path.join(os.tmpdir(),
                            'ext028_broken2_player_' + Date.now() + '.js');
      fs.writeFileSync(tmp, broken, 'utf8');
      const r = cp.spawnSync(process.execPath, [__filename, tmp],
        { encoding: 'utf8',
          env: Object.assign({}, process.env, { EXT028_CHILD: '1' }) });
      fs.unlinkSync(tmp);
      const out = r.stdout || '';
      check('★★ C2g 改坏后 C2b **必须 FAIL**',
        out.includes('[FAIL] ★ C2b'),
        '改坏后的输出尾部：' + out.slice(-700));
    } else {
      check('★★ C2g 改坏后 C2b **必须 FAIL**', false,
        '没找到顺序守卫代码块（无法反证）');
    }
  }
}

// ══════════════════════════════════════════════════════════════════
// C3：采样率错配 ⇒ 时长错（EXT-028 失真定位的核心判据）
// ══════════════════════════════════════════════════════════════════
console.log('\n[C3] ★ 采样率错配会让时长按比例错（失真定位判据）');
{
  const sb = makeSandbox({ currentTime: 10.0, t0: 0, delaySec: 10 });
  const { scheduleDub } = sb.__api;
  // 1 s @ 24 kHz = 48 000 样本 = 96 000 字节
  const pcm1s24k = Buffer.alloc(96000).toString('base64');

  scheduleDub({ id: 'seg_0', t_start: 0, pcm24k: pcm1s24k,
                sample_rate: 24000 });
  const dur24 = sb.__scheduled.length
    ? null : null;
  // 用 metrics 里的采样率记录核对
  check('★ C3a 服务端声明 24000 ⇒ 插件按 24000 建 buffer',
    sb.__lastSr === 24000, `${sb.__lastSr}`);

  const sb2 = makeSandbox({ currentTime: 10.0, t0: 0, delaySec: 10 });
  sb2.__api.scheduleDub({ id: 'seg_0', t_start: 0, pcm24k: pcm1s24k });
  check('★ C3b 字段缺失 ⇒ 兜底 24000（**不是** 16000，否则快 1.5×）',
    sb2.__lastSr === 24000, `${sb2.__lastSr}`);
  check('★ C3c 兜底被计数',
    sb2.metrics.pcmRateAssumed === 1,
    `${sb2.metrics.pcmRateAssumed}`);
}

// ══════════════════════════════════════════════════════════════════
// C4：同步测量覆盖**全部**段 + onset 口径不被污染（EXT-034 ①）
// ══════════════════════════════════════════════════════════════════
//
// ★ EXT-034 ① 的两个验收点：
//   ① `dubSyncDetail` 段数 == TTS 段数（**不能**只覆盖 7/13）
//      ⇒ 主口径由 `noteDubEnded()`（排程起点）负责，与 onset 无关；
//   ② `dubSyncErrsOnset` 只能是**声学 onset 口径**
//      ⇒ `noteDubEnded()` 推进的是**排程口径**的误差
//        ⇒ 若它也推进 onset 序列 ⇒ 两个口径混在一起 ⇒ 口径污染。
console.log('\n[C4] ★ 同步测量覆盖全部段；onset 口径不被排程口径污染');
{
  const sb = makeSandbox({ currentTime: 10.0, t0: 0, delaySec: 10 });
  const { scheduleDub } = sb.__api;
  const pcm1s24k = Buffer.alloc(96000).toString('base64');

  // ── 排 3 段（模拟 TTS 产出 3 段）──
  const ids = ['seg_0', 'seg_1', 'seg_2'];
  for (let i = 0; i < ids.length; i++) {
    scheduleDub({ id: ids[i], t_start: i * 5.0, pcm24k: pcm1s24k,
                  sample_rate: 24000 });
  }

  // ★ 模拟「每段播完」⇒ 触发 `noteDubEnded`（真实现）
  //   `src.onended` 由 `scheduleDub` 在 `src.start(when)` **之后**挂上
  //   ⇒ 这里从 `rec.src.onended` 取。
  const onendeds = sb.__scheduled.map((r) => r.src && r.src.onended)
    .filter(Boolean);
  check('★ C4a 每段都挂了 onended（否则永远落不了 detail）',
    onendeds.length === ids.length, `onended=${onendeds.length}/${ids.length}`);

  // ★ 触发 onended（推进沙箱时钟，模拟「播完」）
  sb.__scheduled.forEach((rec) => {
    const fn = rec.src && rec.src.onended;
    if (typeof fn === 'function') {
      sb.__audioCtx.currentTime = (rec.when || 0) + 1.0 + 0.02;
      fn();
    }
  });

  check('★ C4b dubSyncDetail 覆盖**全部**段（段数 == TTS 段数）',
    sb.metrics.dubSyncDetail.length === ids.length,
    `detail=${sb.metrics.dubSyncDetail.length}/${ids.length}`);
  check('★ C4c detail 里的 id 与排的段一一对应',
    sb.metrics.dubSyncDetail.map((d) => d.id).sort().join(',')
      === ids.slice().sort().join(','),
    sb.metrics.dubSyncDetail.map((d) => d.id).join(','));
  check('★ C4d 主口径 dubSyncErrs 段数 == detail 段数',
    sb.metrics.dubSyncErrs.length === sb.metrics.dubSyncDetail.length,
    `errs=${sb.metrics.dubSyncErrs.length} detail=${sb.metrics.dubSyncDetail.length}`);
  check('★ C4e 每条 detail 都带 startSource=\'sched\'（标明口径来源）',
    sb.metrics.dubSyncDetail.every((d) => d.startSource === 'sched'),
    JSON.stringify(sb.metrics.dubSyncDetail.map((d) => d.startSource)));

  // ★★ 关键：`dubSyncErrsOnset` **不得**被 `noteDubEnded` 推进
  //   （本沙箱**没有**触发任何 onset ⇒ onset 序列必须仍为空）
  check('★★ C4f onset 口径序列**未被**排程口径污染（仍为空）',
    sb.metrics.dubSyncErrsOnset.length === 0,
    `onset=${sb.metrics.dubSyncErrsOnset.length} `
    + `errs=${sb.metrics.dubSyncErrs.length}（两者本应不同源）`);

  // ★ 反证：把 `noteDubEnded` 里的 onset 推进**加回来**⇒ C4f 必须 FAIL
  if (!IS_CHILD) {
    // 锚点：`noteDubEnded` 函数体末尾的 P50/P95 之后那几行
    const broken = psrc.replace(
      /(metrics\.dubSyncMin = metrics\.dubSyncErrs\.length[\s\S]{0,200}?:\s*null;)/,
      '$1\n  metrics.dubSyncErrsOnset.push(signedErrMs);');
    if (broken !== psrc) {
      const tmp = path.join(os.tmpdir(),
                            'ext028_broken_c4_player_' + Date.now() + '.js');
      fs.writeFileSync(tmp, broken, 'utf8');
      const r = cp.spawnSync(process.execPath, [__filename, tmp],
        { encoding: 'utf8',
          env: Object.assign({}, process.env, { EXT028_CHILD: '1' }) });
      fs.unlinkSync(tmp);
      const out = r.stdout || '';
      check('★★★ C4g 加回污染后 C4f **必须 FAIL**',
        out.includes('[FAIL] ★★ C4f'),
        '改坏后的输出尾部：' + out.slice(-700));
    } else {
      check('★★★ C4g 加回污染后 C4f **必须 FAIL**', false,
        '没找到 dubSyncMin 赋值（无法反证）');
    }
  }
}

// ══════════════════════════════════════════════════════════════════
// C5：EXT-035「首段就绪→起播 < 0.5 s」的可核对口径
// ══════════════════════════════════════════════════════════════════
//
// ★ EXT-035 验收项：「首段就绪→起播<0.5 s」
//   ## 为什么需要新字段
//     EXT-034 ③ 的根因分解有一项是「**就绪→起播**」
//     （跨时钟域 t0 + 按序播放排队，实测 4.18~6.7 s）
//     ⇒ 但之前**没有任何地方记录「就绪时刻」**
//     ⇒ 这一项只能估算 ⇒ 归因不可核对。
//   ## 口径（**同一个 AudioContext 时钟域** ⇒ 可直接相减）
//     `readyAtAc`      = TTS 消息**到达 player** 的时刻
//     `actual`         = 该段**实际起播**的时刻（`start(when)`）
//     `readyToStartSec` = actual − readyAtAc
//     ⇒ **不含** D、**不含**服务端起步耗时 ⇒ 纯 player 侧延迟
console.log('\n[C5] ★ EXT-035：就绪→起播 是可核对的口径（同一时钟域）');
{
  const sb = makeSandbox({ currentTime: 10.0, t0: 0, delaySec: 10 });
  const { scheduleDub } = sb.__api;
  const pcm1s24k = Buffer.alloc(96000).toString('base64');

  // ① TTS 到达时刻 = 10.0（沙箱 currentTime）
  //    ⚠️ harness 直接调 `scheduleDub`（不经过 `handleBridgeMessage`）
  //      ⇒ 「就绪时刻」要**显式**写进 `dubReadyAt`（与真代码同一条路径）
  sb.__audioCtx.currentTime = 10.0;
  sb.__dubReadyAt.set('seg_0', sb.__audioCtx.currentTime);
  scheduleDub({ id: 'seg_0', t_start: 0, pcm24k: pcm1s24k,
                sample_rate: 24000 });

  // ★ 模拟「就绪 → 排程 → 起播」：
  //   真代码里排程点 = `requested`（t0 + t_start + D）
  //   这里 requested = t0(0) + t_start(0) + D(10) = 10.0
  //   ⇒ 排程起点 `when` = 10.0 ⇒ 与就绪时刻**同刻** ⇒ 就绪→起播 = 0
  const rec = sb.__scheduled[0];
  check('★ C5a 排程起点已记录（when）',
    rec && typeof rec.when === 'number', JSON.stringify(rec));
  // ★ 就绪时刻写进了 dubReadyAt（按 id）
  const readyAt = sb.__dubReadyAt ? sb.__dubReadyAt.get('seg_0') : undefined;
  check('★ C5b 「就绪时刻」按 id 记进了 dubReadyAt',
    readyAt === 10.0, `readyAt=${readyAt}`);

  // ② 起播 ⇒ 触发 onended ⇒ detail 里应有 readyToStartSec
  sb.__audioCtx.currentTime = rec.when + 1.0 + 0.02;
  if (typeof rec.src.onended === 'function') rec.src.onended();
  const d = sb.metrics.dubSyncDetail[0];
  check('★ C5c detail 里有 readyAtAc（就绪时刻）',
    d && d.readyAtAc === 10.0, JSON.stringify(d && d.readyAtAc));
  check('★ C5d detail 里有 readyToStartSec（就绪→起播）',
    d && typeof d.readyToStartSec === 'number',
    JSON.stringify(d && d.readyToStartSec));
  // ★ 口径核对：readyToStartSec == actual − readyAtAc
  check('★ C5e 口径自洽：readyToStartSec == actual − readyAtAc',
    d && Math.abs(d.readyToStartSec - (d.actual - d.readyAtAc)) < 1e-9,
    `${d && d.readyToStartSec} vs ${d && (d.actual - d.readyAtAc)}`);

  // ③ 「就绪→起播」**不含** D 与服务端起步
  //    ⇒ 它应当只反映 player 侧排队 ⇒ 本例应**远小于** D（10 s）
  //    ⇒ 判据用「< 0.5 s」（EXT-035 的验收阈值），不是「== 0」
  //       （真实实现里排程点会有毫秒级偏移 ⇒ 不该要求严格为 0）
  check('★ C5f 就绪→起播**不含** D 与服务端起步（远小于 D=10 s）',
    d && d.readyToStartSec >= 0 && d.readyToStartSec < 0.5,
    `readyToStartSec=${d && d.readyToStartSec}（应 <0.5 s 且 ≥0）`);

  // ④ 取不到就绪时刻 ⇒ null（**不臆造**）
  const sb2 = makeSandbox({ currentTime: 10.0, t0: 0, delaySec: 10 });
  sb2.__api.scheduleDub({ id: 'seg_x', t_start: 0, pcm24k: pcm1s24k,
                          sample_rate: 24000 });
  const rec2 = sb2.__scheduled[0];
  sb2.__audioCtx.currentTime = rec2.when + 1.0 + 0.02;
  if (typeof rec2.src.onended === 'function') rec2.src.onended();
  const d2 = sb2.metrics.dubSyncDetail[0];
  check('★ C5g 取不到就绪时刻 ⇒ readyToStartSec = null（不臆造）',
    d2 && d2.readyToStartSec === null,
    JSON.stringify(d2 && d2.readyToStartSec));
}

const npass = RESULTS.filter((r) => r.ok).length;
const nfail = RESULTS.length - npass;
console.log('\n============================================================');
console.log(`harness 结果：${npass} PASS / ${nfail} FAIL / 共 ${RESULTS.length}`);
console.log('============================================================');
process.exit(nfail === 0 ? 0 : 1);
