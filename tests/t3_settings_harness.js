/**
 * t3_settings_harness.js — ★ 自发任务 T-3 的**行为级**测试载体
 *
 * ## 为什么需要这个文件
 *
 * 本机**没有 playwright**（实测 `ModuleNotFoundError`）⇒ 不能在真浏览器里
 * 点 popup、拖滑块、看原声增益。
 * ⇒ 但「原声压低量 / 字幕开关」这两个控件是否**真的生效**，
 *   是可以**不依赖浏览器**就验证的：
 *   ① dB→增益换算是纯函数；
 *   ② 增益有没有真正写到 origGain 上；
 *   ③ 字幕关掉后有没有还往 DOM 里写。
 *   这三件事都在 player.js 里，且**不依赖 AudioContext 的真实渲染**。
 *
 * ⇒ 做法：从**真实的 player.js 源文件**里**原样抽出**这几个函数，
 *   放进一个带桩的沙箱里执行 ⇒ 验的是**真代码**，不是复刻品。
 *
 * ⚠️ **可证伪**：本脚本接受 player.js 的路径作为参数 ⇒
 *   反证测试可以传一份**被改坏的**副本 ⇒ 若脚本仍报 PASS，
 *   说明这个 harness 没有区分力（那就是测试本身有问题）。
 *
 * 用法：
 *   node tests/t3_settings_harness.js [player.js 路径]
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

const src = fs.readFileSync(PLAYER, 'utf8');

const RESULTS = [];
function check(name, cond, detail) {
  RESULTS.push({ name, ok: !!cond, detail: detail || '' });
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}`
    + (cond || !detail ? '' : ` — ${detail}`));
}

/**
 * 从源码里**原样抽出**一个顶层函数（含其完整花括号体）。
 * ★ 用括号配对而不是正则截断 ⇒ 不会把函数体切一半。
 */
function extractFunction(name) {
  const re = new RegExp(`^function\\s+${name}\\s*\\(`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`player.js 里找不到函数 ${name}`);
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

/** 建一个带桩的沙箱，把抽出来的真函数放进去跑。 */
function makeSandbox(opts) {
  const o = opts || {};
  const divWrites = [];
  const subsDiv = {
    _html: o.initialSubsHtml || '',
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = v; divWrites.push(v); },
  };
  const sandbox = {
    console,
    // ── player.js 的模块级状态（用属性而非 let 声明，便于沙箱注入）
    metrics: { subsDropped: 0 },
    subs: [],
    // ★ SUBS_CAP 也得注入：scheduleSub 里会用到（截断字幕队列）
    SUBS_CAP: 200,
    duckDb: -15,
    duckDbApplied: null,
    subsOn: true,
    // ★ delaySec：setupOriginalAudio 要用它建 DelayNode
    delaySec: 10,
    origGain: o.origGain === undefined ? null : o.origGain,
    origDelay: null,
    origSource: null,
    audioCtx: o.audioCtx === undefined ? { currentTime: 100 } : o.audioCtx,
    // ★ 音频图的最小桩：够 setupOriginalAudio 把「延迟 + 增益」搭起来。
    //   只关心**增益节点**上的值 ⇒ 不需要真的出声。
    makeOnsetDetector: async () => ({}),
    onOrigOnset: () => {},
    origOnsetNode: null,
    escapeHtml: (s) => String(s)
      .replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
      }[c])),
    document: {
      getElementById: (id) => (id === 'subs' ? subsDiv : null),
    },
  };
  // ── AudioContext 的桩（createMediaStreamSource / createDelay / createGain）
  const gainNode = () => ({ gain: { value: 1.0 }, connect() {} });
  const nodeConnect = () => {};
  sandbox.audioCtx = Object.assign({
    currentTime: 100,
    createMediaStreamSource: () => ({ connect: nodeConnect }),
    createDelay: () => ({ delayTime: { value: 0 }, connect: nodeConnect }),
    createGain: gainNode,
    destination: { connect: nodeConnect },
  }, o.audioCtx || {});
  // 让 setupOriginalAudio 真正把新建的增益节点接到 origGain 上
  sandbox.__gainNode = gainNode;
  sandbox.__divWrites = divWrites;
  sandbox.__subsDiv = subsDiv;

  const code = ['dbToGain', 'applyDuckDb', 'scheduleSub', 'pumpSubs',
    'setupOriginalAudio']
    .map(extractFunction).join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { dbToGain, applyDuckDb, scheduleSub, `
    + `pumpSubs, setupOriginalAudio };`,
    sandbox, { filename: PLAYER });
  sandbox.__api = sandbox.__api;
  return sandbox;
}

function approx(a, b, tol) {
  return Math.abs(a - b) <= (tol === undefined ? 1e-4 : tol);
}

// ══════════════════════════════════════════════════════════════
// A 组：原声压低量（ducking）—— dB 换算 + 真的套到 origGain 上
// ══════════════════════════════════════════════════════════════
console.log('\n[A] ★ 原声压低量：dB→增益换算 + 真的套到原声总线上');
{
  const sb = makeSandbox({ origGain: { gain: { value: 1.0 } } });
  const { dbToGain, applyDuckDb } = sb.__api;

  check('dB=0 ⇒ 增益 1.0（不压低）', approx(dbToGain(0), 1.0),
    `实测 ${dbToGain(0)}`);
  check('dB=-15 ⇒ 增益 ≈ 0.1778（= 10^(-15/20)）',
    approx(dbToGain(-15), 0.17783, 1e-4), `实测 ${dbToGain(-15)}`);
  check('dB=-6 ⇒ 增益 ≈ 0.5012（≈ 减半）',
    approx(dbToGain(-6), 0.50119, 1e-4), `实测 ${dbToGain(-6)}`);
  check('dB=-60 ⇒ 增益 ≈ 0.001（几乎听不见）',
    approx(dbToGain(-60), 0.001, 1e-6), `实测 ${dbToGain(-60)}`);

  // ★ 越界值必须被夹住（防止把增益放大到削波）
  check('越界 dB=+6 被夹到 0 dB ⇒ 增益仍是 1.0（不放大）',
    approx(dbToGain(6), 1.0), `实测 ${dbToGain(6)}`);
  check('越界 dB=-100 被夹到 -60 dB',
    approx(dbToGain(-100), 0.001, 1e-6), `实测 ${dbToGain(-100)}`);
  check('非法输入（NaN）⇒ 增益 1.0（不崩）',
    approx(dbToGain('abc'), 1.0), `实测 ${dbToGain('abc')}`);

  // ★★ 关键行为：设了 -15 dB，origGain.gain 必须**真的**变成 0.1778
  sb.duckDb = -15;
  applyDuckDb();
  check('★★ 设 -15 dB 后 origGain.gain 真的被改成 ≈0.1778',
    approx(sb.origGain.gain.value, 0.17783, 1e-4),
    `实测 ${sb.origGain.gain.value}`);
  check('★★ duckDbApplied 如实记成 -15（证明确实套用过了）',
    sb.duckDbApplied === -15, `实测 ${sb.duckDbApplied}`);
  check('★ metrics.duckDb 如实记成用户设的值',
    sb.metrics.duckDb === -15, `实测 ${sb.metrics.duckDb}`);
  check('★ metrics.duckGain 如实记成换算后的增益',
    approx(sb.metrics.duckGain, 0.17783, 1e-4), `实测 ${sb.metrics.duckGain}`);

  // 改设置 ⇒ 增益要跟着变（运行中改设置也生效）
  sb.duckDb = -40;
  applyDuckDb();
  check('★ 运行中改 -40 dB ⇒ origGain.gain 变成 ≈0.01',
    approx(sb.origGain.gain.value, 0.01, 1e-4), `实测 ${sb.origGain.gain.value}`);

  // ★ 抓流前（origGain 还不存在）⇒ 不能假装已套用
  const sb2 = makeSandbox({ origGain: null });
  sb2.duckDb = -20;
  sb2.__api.applyDuckDb();
  check('★ 抓流前（origGain 不存在）⇒ duckDbApplied 保持 null（不假装生效）',
    sb2.duckDbApplied === null, `实测 ${sb2.duckDbApplied}`);
  check('★ 抓流前仍记录 metrics.duckGain（意图已记下）',
    approx(sb2.metrics.duckGain, 0.1, 1e-4), `实测 ${sb2.metrics.duckGain}`);

  // ★★★ 最关键的一条：**走真实的 setupOriginalAudio 建音频图**，
  //   看新建出来的原声增益节点是不是带着用户设的 dB。
  //   ⇒ 这一条才是「用户拖了滑块，原声真的被压低」的端到端证据。
  //   ⚠️ 反证测试把 applyDuckDb() 换回硬编码 1.0 时，**这条必须 FAIL**
  //     （否则说明 harness 没有区分力）。
  const sb3 = makeSandbox({});
  sb3.duckDb = -15;
  sb3.__api.setupOriginalAudio({});
  check('★★★ 走真实 setupOriginalAudio ⇒ 新建的原声增益节点 = 0.1778',
    sb3.origGain && approx(sb3.origGain.gain.value, 0.17783, 1e-4),
    `实测 ${sb3.origGain ? sb3.origGain.gain.value : 'null'}`);
  check('★★★ setupOriginalAudio 之后 duckDbApplied = -15',
    sb3.duckDbApplied === -15, `实测 ${sb3.duckDbApplied}`);

  // 对照组：dB=0 时增益必须是 1.0（别把「压低」做成「静音」）
  const sb4 = makeSandbox({});
  sb4.duckDb = 0;
  sb4.__api.setupOriginalAudio({});
  check('★★★ 对照组：dB=0 ⇒ 原声增益 = 1.0（没被误静音）',
    sb4.origGain && approx(sb4.origGain.gain.value, 1.0),
    `实测 ${sb4.origGain ? sb4.origGain.gain.value : 'null'}`);

  // 对照组：dB=-40 ⇒ 增益 ≈ 0.01
  const sb5 = makeSandbox({});
  sb5.duckDb = -40;
  sb5.__api.setupOriginalAudio({});
  check('★★★ 对照组：dB=-40 ⇒ 原声增益 ≈ 0.01',
    sb5.origGain && approx(sb5.origGain.gain.value, 0.01, 1e-4),
    `实测 ${sb5.origGain ? sb5.origGain.gain.value : 'null'}`);
}

// ══════════════════════════════════════════════════════════════
// B 组：字幕开关 —— 关掉后必须**不写 DOM**，且清掉旧字幕
// ══════════════════════════════════════════════════════════════
console.log('\n[B] ★ 字幕开关：关掉后不写 DOM / 清旧字幕 / 不入队');
{
  // B1：字幕开着 ⇒ 到点就写
  const sb = makeSandbox({});
  sb.subsOn = true;
  sb.subs.push({ text: '你好', at: 99, id: 'a' });
  sb.__api.pumpSubs();
  check('★ 字幕开 ⇒ 到点的字幕被写进 DOM',
    sb.__divWrites.length === 1 && sb.__divWrites[0].includes('你好'),
    `writes=${JSON.stringify(sb.__divWrites)}`);

  // B2：字幕关 ⇒ **一次都不许写**
  const sb2 = makeSandbox({});
  sb2.subsOn = false;
  sb2.subs.push({ text: '不该出现', at: 99, id: 'a' });
  sb2.__api.pumpSubs();
  check('★★ 字幕关 ⇒ DOM **一次都没被写**',
    sb2.__divWrites.length === 0,
    `writes=${JSON.stringify(sb2.__divWrites)}`);
  check('★★ 字幕关 ⇒ 队列里的旧字幕被清空（不留残影）',
    sb2.subs.length === 0, `剩余 ${sb2.subs.length}`);
  check('★ 字幕关 ⇒ metrics.subsOn 如实为 false',
    sb2.metrics.subsOn === false, `实测 ${sb2.metrics.subsOn}`);

  // B3：字幕关 ⇒ 新来的字幕**不入队**
  const sb3 = makeSandbox({});
  sb3.subsOn = false;
  sb3.__api.scheduleSub({ tgt: '新字幕', id: 'b' }, 100);
  check('★★ 字幕关 ⇒ 新字幕不入队', sb3.subs.length === 0,
    `剩余 ${sb3.subs.length}`);
  check('★ 字幕关 ⇒ 丢弃被计数（不静默丢）',
    sb3.metrics.subsDropped >= 1, `实测 ${sb3.metrics.subsDropped}`);

  // B4：字幕开 ⇒ 入队并显示
  const sb4 = makeSandbox({});
  sb4.subsOn = true;
  sb4.__api.scheduleSub({ tgt: '译文', id: 'c' }, 100);
  check('★ 字幕开 ⇒ 字幕正常入队', sb4.subs.length === 1,
    `剩余 ${sb4.subs.length}`);

  // B5：关掉字幕后，**已有的 DOM 内容要清掉**
  const sb5 = makeSandbox({ initialSubsHtml: '<span>旧字幕</span>' });
  sb5.subsOn = false;
  sb5.__api.pumpSubs();
  check('★★ 字幕关 ⇒ 已显示的旧字幕被清空（不留残影）',
    sb5.__subsDiv.innerHTML === '', `实测 ${JSON.stringify(sb5.__subsDiv.innerHTML)}`);
}

// ══════════════════════════════════════════════════════════════
console.log('\n' + '='.repeat(68));
const npass = RESULTS.filter((r) => r.ok).length;
const nfail = RESULTS.length - npass;
console.log(`harness 结果：${npass} PASS / ${nfail} FAIL / 共 ${RESULTS.length}`);
if (nfail) {
  console.log('\nFAIL 明细：');
  for (const r of RESULTS) if (!r.ok) console.log(` - ${r.name} — ${r.detail}`);
}
console.log('='.repeat(68));
process.exit(nfail ? 1 : 0);
