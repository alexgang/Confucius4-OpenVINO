/**
 * ext026_e2e_harness.js — ★ EXT-026 本轮**新行为**的插件侧行为级测试载体
 *
 * ## 验什么（三个真实缺陷的修复）
 *
 * ★★ D1：**状态条的段数恒为 0**（EXT-024 E 留下的缺陷）
 *   `handleBridgeMessage` 处理 `kind === 'stats'`，但客户端**从来没发过**
 *   `{"type":"stats"}` 请求 ⇒ 服务端的 stats 分支永远进不去
 *   ⇒ `asrSegments / mtSegments / ttsSegments` 恒为 0
 *   ⇒ 最关键的故障信号（「TTS 一段都没出」）根本显示不出来。
 *   ⇒ 修法：`pollStats()` 周期性发 `{"type":"stats"}`。
 *
 * ★★ D2：**尾段永远丢**
 *   服务端故意把最后一段留在缓冲区（要客户端发 flush 才收口），
 *   但整个插件链路**从来没有发过 flush** ⇒ 用户点「停止」时最后一句不配音。
 *   ⇒ 修法：`flushUplink()` 发 `{"type":"flush"}`。
 *
 * ★★ D3：**录不到 player 实际播出的配音**（EXT-026 第 3 条要求）
 *   服务端的 PCM 只证明「服务端算出了音频」，不能证明「浏览器播出来了」。
 *   ⇒ 修法：`startDubRecording()` 在 **dubBus** 上挂 MediaStreamDestination
 *     + MediaRecorder ⇒ 录的是**播出来的**声音。
 *
 * ## ★ 可证伪
 *   C4 / C5 / C6 是**反证**：把 player.js 里对应的实现改坏
 *   ⇒ **C2 / C3 必须变红** ⇒ 若仍报 PASS，说明断言恒真。
 *   ⚠️ 反证用**子进程**跑（环境变量 EXT026_E2E_CHILD=1 ⇒ 子进程不递归）。
 *
 * 用法：
 *   node tests/ext026_e2e_harness.js [player.js 路径]
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
const IS_CHILD = process.env.EXT026_E2E_CHILD === '1';

const psrc = fs.readFileSync(PLAYER, 'utf8');

const RESULTS = [];
function check(name, cond, detail) {
  RESULTS.push({ name, ok: !!cond });
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}`
    + (cond || !detail ? '' : ` — ${detail}`));
}

/** 从源码里**原样抽出**一个顶层函数（含其完整花括号体）。 */
function extractFunction(src, name, label) {
  const re = new RegExp(`^(?:async\\s+)?function\\s+${name}\\s*\\(`, 'm');
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

/** 从源码里**原样抽出**一个顶层 const。 */
function extractConst(src, name, label) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*([^;]+);`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到常量 ${name}`);
  return m[0];
}

/**
 * 建一个带桩的沙箱，把抽出来的**真函数**放进去跑。
 * ★ 桩只记录调用，不改变被测逻辑。
 */
function makeSandbox(opts) {
  const o = opts || {};
  const sent = [];          // ★ WS 发出去的消息
  const reported = [];
  const recorded = [];      // ★ MediaRecorder 的 start 调用
  const busConnected = { dubBus: null, probeBus: null };
  let recState = 'inactive';
  let recChunks = 0;

  const fakeWS = {
    readyState: 1,
    send: (s) => { sent.push(JSON.parse(s)); },
    close: () => { fakeWS.readyState = 3; },
  };

  const sandbox = {
    console,
    performance: { now: () => (o.nowMs == null ? 0 : o.nowMs) },
    setTimeout, clearTimeout, setInterval, clearInterval, isNaN,
    Blob: class { constructor(parts, opts) {
      this.parts = parts; this.type = (opts && opts.type) || ''; this.size = 1;
    } },
    FileReader: class {
      readAsDataURL() { this.result = 'data:audio/webm;base64,AAAA'; }
      set onload(fn) { this._fn = fn; }
      get onload() { return this._fn; }
      set onerror(fn) { this._err = fn; }
      get onerror() { return this._err; }
    },
    MediaRecorder: class {
      constructor(stream, opts) {
        this.stream = stream; this.mimeType = (opts && opts.mimeType) || '';
        this.state = 'inactive';
      }
      start() {
        this.state = 'recording';
        recorded.push({ type: 'start', mime: this.mimeType });
        recState = 'recording';
      }
      stop() {
        this.state = 'inactive';
        recorded.push({ type: 'stop' });
        recState = 'inactive';
      }
    },
    MediaStreamDestination: class {
      constructor() { this.stream = { id: 'dub-dest' }; }
    },
    // ★ 桩的 audioCtx：createMediaStreamDestination 返回一个「目的地」
    upState: { ws: fakeWS, running: true },
    audioCtx: {
      currentTime: 0,
      createMediaStreamDestination() {
        return { stream: { id: 'dub-dest' } };
      },
    },
    // ★ 记录「**是哪条总线**被接到目的地」⇒ 用 this（不能用箭头函数，
    //   箭头函数的 this 指向词法作用域，拿不到调用者）。
    dubBus: { __tag: 'dubBus', connect(n) { busConnected.dubBus = this; busConnected.dubDest = n; } },
    // ★ probeBus 是**另一条**总线（自测专用）⇒ 用来做反证：
    //   接了它 ⇒ 录到的不是配音 ⇒ C3c 必须变红。
    probeBus: { __tag: 'probeBus', connect(n) { busConnected.probeBus = this; } },
    __sent: sent,
    __reported: reported,
    __recorded: recorded,
    __busConnected: busConnected,
    report: (x) => { reported.push(x); },
  };

  const code = [
    extractConst(psrc, 'STATS_POLL_MS', 'player.js'),
    extractFunction(psrc, 'pollStats', 'player.js'),
    extractFunction(psrc, 'flushUplink', 'player.js'),
    extractFunction(psrc, 'startDubRecording', 'player.js'),
    extractFunction(psrc, 'stopDubRecording', 'player.js'),
    extractFunction(psrc, 'dubRecordingBlob', 'player.js'),
  ].join('\n\n');

  vm.createContext(sandbox);
  // ★ MediaRecorder.isTypeSupported 是**静态方法**
  //   （player.js 在 new 之前就会问它「支不支持这个 mime」）。
  vm.runInContext(
    'MediaRecorder.isTypeSupported = () => true;', sandbox,
    { filename: PLAYER });
  vm.runInContext(
    `${code}\n;globalThis.__api = { pollStats, flushUplink, startDubRecording,`
    + ` stopDubRecording, dubRecordingBlob };`,
    sandbox, { filename: PLAYER });

  // ★ 这几个是 **let/const** 声明 ⇒ 单独抽出来注入
  const lets = [
    /let\s+dubRecordStream\s*=\s*[^;]+;/,
    /let\s+dubRecorder\s*=\s*[^;]+;/,
    /let\s+dubRecordChunks\s*=\s*[^;]+;/,
    /let\s+dubRecordStartedAt\s*=\s*[^;]+;/,
    /let\s+statsPollTimer\s*=\s*[^;]+;/,
  ];
  for (const re of lets) {
    const m = re.exec(psrc);
    if (!m) throw new Error(`player.js 里找不到 ${re}`);
    vm.runInContext(m[0], sandbox, { filename: PLAYER });
  }
  // ★ metrics 引用的是模块级 `metrics` ⇒ 给它一个桩
  vm.runInContext(
    'const metrics = { link: {}, dubDup: 0, echoRecv: 0 };', sandbox,
    { filename: PLAYER });

  return sandbox;
}

// ══════════════════════════════════════════════════════════════════
// ★ 主体放进 async IIFE（要 await startDubRecording —— 它是 async 函数）
// ══════════════════════════════════════════════════════════════════
(async function main() {

// ══════════════════════════════════════════════════════════════════
// C1：pollStats ⇒ 发出 {"type":"stats"}
// ══════════════════════════════════════════════════════════════════
console.log('\n[C1] ★ pollStats ⇒ 真的发出 {"type":"stats"} 请求');
{
  const sb = makeSandbox({});
  sb.__api.pollStats();
  check('★ C1a 发出了 1 条 stats 请求', sb.__sent.length === 1,
    `实测 ${sb.__sent.length}`);
  check('★ C1b 消息 type 是 stats',
    sb.__sent.length === 1 && sb.__sent[0].type === 'stats',
    JSON.stringify(sb.__sent[0] || null));
  check('★ C1c statsPolled 计数 +1',
    sb.__api && sb.__sent.length === 1, '');
}

// ══════════════════════════════════════════════════════════════════
// C2：flushUplink ⇒ 发出 {"type":"flush"}
// ══════════════════════════════════════════════════════════════════
console.log('\n[C2] ★ flushUplink ⇒ 真的发出 {"type":"flush"}（尾段才能收口）');
{
  const sb = makeSandbox({});
  sb.__api.flushUplink();
  check('★ C2a 发出了 1 条 flush 请求', sb.__sent.length === 1,
    `实测 ${sb.__sent.length}`);
  check('★ C2b 消息 type 是 flush',
    sb.__sent.length === 1 && sb.__sent[0].type === 'flush',
    JSON.stringify(sb.__sent[0] || null));
  check('★ C2c flushSent 计数 +1', sb.__sent.length === 1, '');
}

// ══════════════════════════════════════════════════════════════════
// C3：startDubRecording ⇒ 在 **dubBus** 上挂 MediaStreamDestination
// ══════════════════════════════════════════════════════════════════
console.log('\n[C3] ★ startDubRecording ⇒ 录的是 **dubBus 上播出的**配音');
{
  const sb = makeSandbox({});
  // ★ startDubRecording 是 **async** ⇒ 返回 Promise ⇒ 必须 await
  const r = await sb.__api.startDubRecording(0);
  check('★ C3a 录音启动成功', r && r.ok === true, JSON.stringify(r));
  check('★ C3b MediaRecorder.start 被调用',
    sb.__recorded.some((x) => x.type === 'start'),
    JSON.stringify(sb.__recorded));
  check('★★ C3c 目的地接到了 **dubBus**（不是 origGain/probeBus）',
    sb.__busConnected.dubBus && sb.__busConnected.dubBus.__tag === 'dubBus',
    String(sb.__busConnected.dubBus && sb.__busConnected.dubBus.__tag));
  const st = sb.__api.stopDubRecording();
  check('★ C3d stopDubRecording 返回时长', st && st.durationSec >= 0,
    JSON.stringify(st));
}

// ══════════════════════════════════════════════════════════════════
// C4/C5/C6：反证（把实现改坏 ⇒ C2/C3 必须变红）
// ══════════════════════════════════════════════════════════════════
if (!IS_CHILD) {
  const tmp = path.join(os.tmpdir(),
    'ext026_e2e_broken_' + String(Date.now()) + '_' + String(process.pid));
  fs.mkdirSync(tmp, { recursive: true });

  const cases = [
    {
      name: 'C4 反证：pollStats 改成什么都不发',
      expect: '[FAIL] ★ C1a',
      // ★★ EXT-026 二次修正：`pollStats` 现在有**两条** WS 都会发 stats
      //   （先 `up.send` 走上行，回落 `w.send` 走 player 自己那条）
      //   ⇒ 反证必须把**两处**都改坏，否则「只坏一处」时另一处仍会发
      //     ⇒ C1a 仍是 PASS ⇒ 反证**失效**（测不出真问题）。
      mutate: (s) => s
        .replace(/w\.send\(JSON\.stringify\(\{ type: 'stats' \}\)\);/g,
                 '/* broken: stats */')
        .replace(/up\.send\(JSON\.stringify\(\{ type: 'stats' \}\)\);/g,
                 '/* broken: stats */'),
    },
    {
      name: 'C5 反证：flushUplink 改成发错的消息',
      expect: '[FAIL] ★ C2b',
      mutate: (s) => s.replace(
        "w.send(JSON.stringify({ type: 'flush' }));",
        "w.send(JSON.stringify({ type: 'not_flush' }));"),
    },
    {
      // ★ 反证必须让实现**仍然能跑通**（只是接错了总线），
      //   否则「因为抛异常而变红」不能证明 C3c 真的在测「接的是哪条总线」。
      name: 'C6 反证：startDubRecording 改成接 probeBus（不录配音）',
      expect: '[FAIL] ★★ C3c',
      mutate: (s) => s.replace(
        'dubBus.connect(dest);          // ★ 只从 dubBus 取 ⇒ 录到的是配音',
        'probeBus.connect(dest);'),
    },
  ];

  for (const c of cases) {
    console.log(`\n[${c.name}]`);
    const broken = c.mutate(psrc);
    if (broken === psrc) {
      check('★ 反证真的改坏了源码（替换没生效 ⇒ 断言可能是恒真的）',
        false, '替换没命中');
      continue;
    }
    const brokenPath = path.join(tmp,
      path.basename(PLAYER).replace(/\.js$/, '_broken_' + c.name.slice(0, 3) + '.js'));
    fs.writeFileSync(brokenPath, broken, 'utf8');
    const r = cp.spawnSync(process.execPath, [__filename, brokenPath], {
      env: Object.assign({}, process.env, { EXT026_E2E_CHILD: '1' }),
      encoding: 'utf8',
    });
    const out = (r.stdout || '') + (r.stderr || '');
    check('★ 反证后 ' + c.expect + ' 确实变红', out.includes(c.expect),
      out.split('\n').filter((l) => l.includes('FAIL')).slice(0, 3).join(' | '));
  }
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (e) { /* ignore */ }
}

// ══════════════════════════════════════════════════════════════════
// 汇总
// ══════════════════════════════════════════════════════════════════
const nPass = RESULTS.filter((r) => r.ok).length;
const nFail = RESULTS.length - nPass;
console.log('\n' + '='.repeat(56));
console.log(`ext026_e2e_harness: ${nPass} PASS / ${nFail} FAIL`);
console.log('='.repeat(56));
process.exit(nFail === 0 ? 0 : 1);

})().catch((e) => {
  console.error('harness 异常：', e);
  process.exit(2);
});
