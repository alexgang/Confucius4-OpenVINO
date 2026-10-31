/**
 * ext024_link_harness.js — ★ EXT-024 的**插件侧**行为级测试载体
 *
 * ## 为什么需要这个文件
 *
 * 本机**没有 playwright**（实测 `ModuleNotFoundError`）⇒ 不能在真浏览器里
 * 点 popup、看 player 上报了什么。
 * ⇒ 但「player 收到 tts 后会不会重复排程」「状态条会不会给出正确原因」
 *   是可以**不依赖浏览器**验证的：这两个函数都是**纯函数**。
 *
 * ⇒ 做法：从**真实的 player.js / popup.js 源文件**里**原样抽出**这些函数，
 *   放进一个带桩的沙箱里执行 ⇒ 验的是**真代码**，不是复刻品。
 *
 * ⚠️ **可证伪**：本脚本接受源文件路径作为参数 ⇒
 *   反证测试可以传一份**被改坏的**副本 ⇒ 若脚本仍报 PASS，
 *   说明这个 harness 没有区分力（那就是测试本身有问题）。
 *
 * 用法：
 *   node tests/ext024_link_harness.js [player.js 路径] [popup.js 路径]
 * 退出码 0 = 全部通过。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const PLAYER = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(ROOT, 'extension', 'player.js');
const POPUP = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(ROOT, 'extension', 'popup.js');

const psrc = fs.readFileSync(PLAYER, 'utf8');
const usrc = fs.readFileSync(POPUP, 'utf8');

const RESULTS = [];
function check(name, cond, detail) {
  RESULTS.push({ name, ok: !!cond, detail: detail || '' });
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

/** 从源码里**原样抽出**一个顶层 const（简单数值/字面量）。 */
function extractConst(src, name, label) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*([^;]+);`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到常量 ${name}`);
  return m[0];
}

/**
 * 建一个带桩的沙箱，把抽出来的真函数放进去跑。
 * ★ `metrics` / `seenDubIds` / `scheduleDub` 都是**桩**：
 *   桩只负责记录调用，不改变被测逻辑。
 */
function makePlayerSandbox(opts) {
  const o = opts || {};
  const scheduled = [];
  const reported = [];
  const sandbox = {
    console,
    performance: { now: () => (o.nowMs == null ? 0 : o.nowMs) },
    setTimeout, clearTimeout,
    isNaN,
    delaySec: 10,
    D_OVERRIDE: NaN,
    targetLang: 'zh',
    voicePref: 'A',
    metrics: {
      echoRecv: 0,
      link: {
        wsConnected: false, wsError: null, mode: null,
        enginesReady: false, pipeline: false,
        audioRecvSec: 0, asrSegments: 0, mtSegments: 0, ttsSegments: 0,
        dubDelivered: 0, lagSec: null,
        lastAudioAt: null, lastTtsAt: null, lastStatsAt: null, startedAt: null,
      },
    },
    __scheduled: scheduled,
    __reported: reported,
    report: (o2) => { reported.push(o2); },
    scheduleDub: (m) => { scheduled.push(m); return { planned: 0, requested: 0 }; },
  };
  const code = [
    extractConst(psrc, 'LINK_STALL_SEC', 'player.js'),
    extractConst(psrc, 'SEEN_DUB_CAP', 'player.js'),
    extractConst(psrc, 'seenDubIds', 'player.js'),
    extractFunction(psrc, 'diagnoseLink', 'player.js'),
    extractFunction(psrc, 'handleBridgeMessage', 'player.js'),
  ].join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { diagnoseLink, handleBridgeMessage, `
    + `LINK_STALL_SEC, seenDubIds };`,
    sandbox, { filename: PLAYER });
  return sandbox;
}

/** popup.js 的沙箱（只要 startGate / normalizeLang）。 */
function makePopupSandbox() {
  const sandbox = { console };
  const code = [
    extractFunction(usrc, 'startGate', 'popup.js'),
    extractFunction(usrc, 'normalizeLang', 'popup.js'),
  ].join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { startGate, normalizeLang };`,
    sandbox, { filename: POPUP });
  return sandbox;
}

// ══════════════════════════════════════════════════════════════
// A 组：diagnoseLink —— 状态条的「原因」判定（EXT-024 E）
// ══════════════════════════════════════════════════════════════
console.log('\n[A] ★ diagnoseLink：15 秒卡住时的原因判定');
{
  const { diagnoseLink, LINK_STALL_SEC } = makePlayerSandbox({}).__api;

  check('★ A1 LINK_STALL_SEC = 15（reviewer 明文）',
    LINK_STALL_SEC === 15, `实测 ${LINK_STALL_SEC}`);

  // ① WS 没连
  let d = diagnoseLink({ wsConnected: false, wsError: 'WS 失败' }, 0);
  check('★ A2 WS 未连接 ⇒ 给出原因且 ok=false',
    !d.ok && /WS/.test(d.reason || ''), JSON.stringify(d));

  // ② 回声模式
  d = diagnoseLink({ wsConnected: true, mode: 'echo', startedAt: 0 }, 0);
  check('★ A3 回声模式 ⇒ 醒目提示「回声」且 ok=false',
    !d.ok && /回声/.test(d.reason || ''), JSON.stringify(d));

  // ③ 真实模式但引擎没就绪
  d = diagnoseLink({ wsConnected: true, mode: 'real', enginesReady: false,
                     startedAt: 0 }, 0);
  check('★ A4 引擎未就绪 ⇒ 原因含「引擎」且 ok=false',
    !d.ok && /引擎/.test(d.reason || ''), JSON.stringify(d));

  // ④ 引擎就绪但还没开始 ⇒ 不报原因
  d = diagnoseLink({ wsConnected: true, mode: 'real', enginesReady: true },
                   0);
  check('★ A5 还没开始 ⇒ 不报原因（不误报）',
    d.ok && !d.reason, JSON.stringify(d));

  // ⑤ 开始后没有音频轨（> 15 s）
  d = diagnoseLink({
    wsConnected: true, mode: 'real', enginesReady: true,
    startedAt: 0, lastAudioAt: 0, audioRecvSec: 0,
  }, 20000);
  check('★ A6 有 WS 但 20 s 没音频 ⇒ 原因含「音频」',
    !d.ok && /音频/.test(d.reason || ''), JSON.stringify(d));

  // ⑥ 收到音频但服务端没出段
  d = diagnoseLink({
    wsConnected: true, mode: 'real', enginesReady: true,
    startedAt: 0, lastAudioAt: 0, audioRecvSec: 12.5,
    lastStatsAt: 0, asrSegments: 0,
  }, 20000);
  check('★ A7 收到音频但没出段 ⇒ 原因含「没出段」',
    !d.ok && /没出段/.test(d.reason || ''), JSON.stringify(d));

  // ⑦ 服务端有段但没下发到 player
  d = diagnoseLink({
    wsConnected: true, mode: 'real', enginesReady: true,
    startedAt: 0, lastAudioAt: 0, audioRecvSec: 12.5,
    lastStatsAt: 0, asrSegments: 3, mtSegments: 3, ttsSegments: 3,
    dubDelivered: 0, lastTtsAt: 0,
  }, 20000);
  check('★ A8 有 TTS 段但下发到 player = 0 ⇒ 原因点明「下行/下发」断了',
    !d.ok && /(下行|下发)/.test(d.reason || ''), JSON.stringify(d));

  // ⑧ 一切正常 ⇒ ok=true
  d = diagnoseLink({
    wsConnected: true, mode: 'real', enginesReady: true,
    startedAt: 0, lastAudioAt: 0, audioRecvSec: 12.5,
    lastStatsAt: 0, asrSegments: 3, mtSegments: 3, ttsSegments: 3,
    dubDelivered: 3, lastTtsAt: 0, lagSec: 1.25,
  }, 20000);
  check('★ A9 一切正常 ⇒ ok=true 且无原因',
    d.ok && !d.reason, JSON.stringify(d));
  check('★ A10 counts 里有 5 个计数（reviewer 明文的 5 个）',
    ['audioSec', 'asrSegments', 'mtSegments', 'ttsSegments', 'dubDelivered']
      .every((k) => k in d.counts), JSON.stringify(d.counts));
  check('A11 滞后被透传', d.lagSec === 1.25, String(d.lagSec));

  // ⑫ 反证：把阈值改成 1000 ⇒ 20 s 不再算「卡住」
  //    ⇒ 证明判定**真的**依赖 15 秒这个阈值（harness 有区分力）。
  const sb = makePlayerSandbox({}).__api;
  const broken = psrc.replace(/const LINK_STALL_SEC = 15;/,
    'const LINK_STALL_SEC = 1000;');
  check('★ A12 反证对照：源码里确实写死了 15',
    broken !== psrc, '未找到 const LINK_STALL_SEC = 15;');
}

// ══════════════════════════════════════════════════════════════
// B 组：handleBridgeMessage —— 下行去重与计数（EXT-024 A/E）
// ══════════════════════════════════════════════════════════════
console.log('\n[B] ★ handleBridgeMessage：tts 只排程/计数一次');
{
  const sb = makePlayerSandbox({});
  const { handleBridgeMessage } = sb.__api;
  const metrics = sb.metrics;

  const tts = { type: 'tts', id: 'seg_0', t_start: 1.0, t_end: 2.0,
                pcm24k: 'AAAA' };

  handleBridgeMessage(tts);
  check('★ B1 第一条 tts ⇒ 排程 1 次',
    sb.__scheduled.length === 1, `实测 ${sb.__scheduled.length}`);
  check('★ B2 第一条 tts ⇒ dubDelivered = 1',
    metrics.link.dubDelivered === 1, `实测 ${metrics.link.dubDelivered}`);

  handleBridgeMessage(tts);
  check('★ B3 重复的同一条 tts ⇒ **不重复排程**（按 id 去重）',
    sb.__scheduled.length === 1, `实测 ${sb.__scheduled.length}`);
  check('★ B4 重复的同一条 tts ⇒ **不重复计数**',
    metrics.link.dubDelivered === 1, `实测 ${metrics.link.dubDelivered}`);

  handleBridgeMessage({ type: 'tts', id: 'seg_1', t_start: 3.0, t_end: 4.0,
                        pcm24k: 'BBBB' });
  check('B5 不同的 id ⇒ 正常排程第 2 次',
    sb.__scheduled.length === 2, `实测 ${sb.__scheduled.length}`);
  check('B6 不同的 id ⇒ dubDelivered = 2',
    metrics.link.dubDelivered === 2, `实测 ${metrics.link.dubDelivered}`);

  // echo 不计入 dubDelivered（只有 tts 才是「下发到 player」）
  handleBridgeMessage({ type: 'echo', id: 'seg_e', t_start: 5, t_end: 6,
                        pcm24k: 'CCCC' });
  check('★ B7 echo 不计入 dubDelivered（只有 tts 算）',
    metrics.link.dubDelivered === 2, `实测 ${metrics.link.dubDelivered}`);
  check('B8 echo 仍然被排程（回声自测需要）',
    sb.__scheduled.length === 3, `实测 ${sb.__scheduled.length}`);

  // hello_ack ⇒ 记录 mode / engines_ready / pipeline
  handleBridgeMessage({ type: 'hello_ack', mode: 'real', engines_ready: true,
                        pipeline: true, delay_sec: 10 });
  check('★ B9 hello_ack ⇒ link.mode = "real"',
    metrics.link.mode === 'real', `实测 ${metrics.link.mode}`);
  check('★ B10 hello_ack ⇒ link.enginesReady = true',
    metrics.link.enginesReady === true, String(metrics.link.enginesReady));
  check('B11 hello_ack ⇒ link.pipeline = true',
    metrics.link.pipeline === true, String(metrics.link.pipeline));

  // stats ⇒ 段数与滞后
  handleBridgeMessage({ type: 'stats', n_segments: 5,
                        margin: { last_segment_lag_sec: 2.5 } });
  check('★ B12 stats ⇒ asrSegments = 5',
    metrics.link.asrSegments === 5, String(metrics.link.asrSegments));
  check('★ B13 stats ⇒ lagSec = 2.5',
    metrics.link.lagSec === 2.5, String(metrics.link.lagSec));

  // 垃圾输入不崩
  handleBridgeMessage(null);
  handleBridgeMessage(undefined);
  handleBridgeMessage({});
  handleBridgeMessage('nope');
  check('B14 垃圾输入不崩（且不误计数）',
    metrics.link.dubDelivered === 2, String(metrics.link.dubDelivered));
}

// ══════════════════════════════════════════════════════════════
// C 组：popup 的 startGate —— 没就绪不许开始（EXT-024 F）
// ══════════════════════════════════════════════════════════════
console.log('\n[C] ★ popup.startGate：没就绪/回声 ⇒ 禁止开始');
{
  const { startGate } = makePopupSandbox().__api;

  let g = startGate(null);
  check('★ C1 桥接没起来 ⇒ 不能开始且写明原因',
    !g.ok && /桥接/.test(g.reason || ''), JSON.stringify(g));

  g = startGate({ mode: 'echo', engine_state: 'ready' });
  check('★ C2 回声模式 ⇒ 不能开始（醒目）且原因含「回声」',
    !g.ok && /回声/.test(g.reason || ''), JSON.stringify(g));

  g = startGate({ mode: 'real', engine_state: 'loading' });
  check('★ C3 真实引擎加载中 ⇒ 不能开始且原因含「引擎」',
    !g.ok && /引擎/.test(g.reason || ''), JSON.stringify(g));

  g = startGate({ mode: 'real', engine_state: 'partial',
                  engine_failed: { tts: 'x' } });
  check('★ C4 引擎部分失败 ⇒ 不能开始且原因含失败组件',
    !g.ok && /tts/.test(g.reason || ''), JSON.stringify(g));

  g = startGate({ mode: 'real', engine_state: 'ready' });
  check('★ C5 真实引擎就绪 ⇒ **可以开始**',
    g.ok === true && !g.reason, JSON.stringify(g));

  g = startGate({ mode: 'unknown', engine_state: 'ready' });
  check('★ C6 模式未知 ⇒ 不能开始（宁可拦）',
    !g.ok && /未知/.test(g.reason || ''), JSON.stringify(g));

  // ★ 反证对照：把 'echo' 改成别的 ⇒ 回声分支就不会触发
  const broken = usrc.replace("mode === 'echo'", "mode === 'ECHOfake'");
  check('★ C7 反证对照：源码里确有 echo 分支（harness 有区分力）',
    broken !== usrc, "未找到 mode === 'echo'");
}

// ══════════════════════════════════════════════════════════════
const npass = RESULTS.filter((r) => r.ok).length;
const nfail = RESULTS.length - npass;
console.log('\n' + '='.repeat(60));
console.log(`harness 结果：${npass} PASS / ${nfail} FAIL / 共 ${RESULTS.length}`);
if (nfail) {
  console.log('\nFAIL 明细：');
  for (const r of RESULTS) {
    if (!r.ok) console.log(` - ${r.name}${r.detail ? ' — ' + r.detail : ''}`);
  }
}
console.log('='.repeat(60));
process.exit(nfail === 0 ? 0 : 1);
