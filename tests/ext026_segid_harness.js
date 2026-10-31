/**
 * ext026_segid_harness.js — ★ EXT-026 第 5 条：插件侧行为级测试载体
 *
 * ## 验什么（reviewer EXT-026 明文）
 *
 * > player.js 的 `seenDubIds` 一直不清，而段 id 是 `seg_{s0}`/`seg_{abs0}`
 * > （每个会话从 0 开始）。player 页不关、offscreen 路径重新开始一个会话时，
 * > 新会话的段 id 和旧会话撞了，会被当成重复**静默丢掉**（又是"没配音"）。
 * > 改法二选一：段 id 带上会话前缀，或者收到新会话的 hello_ack 时清空
 * > seenDubIds。**加一个单测。**
 *
 * ⇒ 本脚本验**客户端那一半**：收到**新会话**的 hello_ack 时清空
 *   `seenDubIds` ⇒ 新会话里即使段 id 与旧会话**撞号**也不会被丢掉。
 *
 * ## ★ 为什么从**真源码**里抽函数（而不是复刻）
 *
 * `handleBridgeMessage` 是**真代码**（`extension/player.js`）⇒ 抽取后放进
 * 带桩的沙箱执行 ⇒ 验的是真逻辑。
 * ⚠️ 沙箱里的 `scheduleDub` / `metrics` / `report` 都是**桩**
 *   （只记录调用，不改变被测逻辑）。
 *
 * ## ★ 可证伪
 *
 * C3 / C4 是**反证**：把 `player.js` 的「清空 seenDubIds」或「读 session_id」
 * 改坏 ⇒ **本脚本的 C2b/C2c 必须变红** ⇒ 若仍报 PASS，说明断言恒真。
 * ⚠️ 反证用**子进程**跑（环境变量 EXT026_CHILD=1 ⇒ 子进程**不递归**跑
 *   C3/C4，否则无限递归）。
 *
 * 用法：
 *   node tests/ext026_segid_harness.js [player.js 路径]
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
// ★ 子进程标志：反证时由父进程设置 ⇒ 子进程**只跑 C1/C2**（不递归跑 C3/C4）
const IS_CHILD = process.env.EXT026_CHILD === '1';

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

/** 从源码里**原样抽出**一个顶层 const（简单数值/字面量）。 */
function extractConst(src, name, label) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*([^;]+);`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`${label} 里找不到常量 ${name}`);
  return m[0];
}

/**
 * 建一个带桩的沙箱，把抽出来的**真函数**放进去跑。
 * ★ `metrics` / `seenDubIds` / `scheduleDub` 都是**桩**：
 *   桩只负责记录调用，不改变被测逻辑。
 */
function makeSandbox(opts) {
  const o = opts || {};
  const scheduled = [];
  const reported = [];
  const sandbox = {
    console,
    performance: { now: () => (o.nowMs == null ? 0 : o.nowMs) },
    setTimeout, clearTimeout, isNaN,
    delaySec: 10, D_OVERRIDE: NaN, targetLang: 'zh', voicePref: 'A',
    metrics: {
      echoRecv: 0,
      link: {
        wsConnected: true, wsError: null, mode: null,
        enginesReady: true, pipeline: true,
        audioRecvSec: 0, asrSegments: 0, mtSegments: 0, ttsSegments: 0,
        dubDelivered: 0, lagSec: null,
        lastAudioAt: null, lastTtsAt: null, lastStatsAt: null, startedAt: 0,
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
    extractFunction(psrc, 'handleBridgeMessage', 'player.js'),
  ].join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { handleBridgeMessage, seenDubIds };`,
    sandbox, { filename: PLAYER });
  // ★ `currentSessionId` 是 **let** 声明（不是 const）⇒ 单独抽出来注入
  const m = /let\s+currentSessionId\s*=\s*[^;]+;/.exec(psrc);
  if (!m) throw new Error('player.js 里找不到 `let currentSessionId = ...` 声明');
  vm.runInContext(m[0], sandbox, { filename: PLAYER });
  return sandbox;
}

// ══════════════════════════════════════════════════════════════════
// C1：同一会话内重复 hello_ack ⇒ **不清** seenDubIds
// ══════════════════════════════════════════════════════════════════
console.log('\n[C1] ★ 同一会话的重复 hello_ack ⇒ 不清 seenDubIds');
{
  const sb = makeSandbox({});
  const { handleBridgeMessage } = sb.__api;
  handleBridgeMessage({ type: 'hello_ack', mode: 'real', engines_ready: true,
                        pipeline: true, session_id: 'S1' });
  handleBridgeMessage({ type: 'tts', id: 'seg_0', t_start: 1.0,
                        t_end: 2.0, pcm24k: 'AAAA' });
  check('★ C1a 第一条 tts 被排程', sb.__scheduled.length === 1,
    `实测 ${sb.__scheduled.length}`);
  // 同一会话再收一次 hello_ack（两条 WS 各发一次）
  handleBridgeMessage({ type: 'hello_ack', mode: 'real', engines_ready: true,
                        pipeline: true, session_id: 'S1' });
  handleBridgeMessage({ type: 'tts', id: 'seg_0', t_start: 1.0,
                        t_end: 2.0, pcm24k: 'AAAA' });
  check('★ C1b 同一会话的重复 tts **仍被去重**（没被误清）',
    sb.__scheduled.length === 1, `实测 ${sb.__scheduled.length}`);
}

// ══════════════════════════════════════════════════════════════════
// C2：新会话的 hello_ack ⇒ 清空 seenDubIds
// ══════════════════════════════════════════════════════════════════
console.log('\n[C2] ★ 新会话的 hello_ack ⇒ 清空 seenDubIds（新段不再被丢掉）');
{
  const sb = makeSandbox({});
  const { handleBridgeMessage } = sb.__api;
  handleBridgeMessage({ type: 'hello_ack', mode: 'real', engines_ready: true,
                        pipeline: true, session_id: 'S1' });
  // ★ 刻意用**裸的** id（模拟**旧服务端**：段 id 没有会话前缀）
  //   ⇒ S1 的段 id 是 'seg_0' / 'seg_1'
  //   ⇒ S2 的第 1 段 id **也是** 'seg_0' ⇒ 真实撞号场景。
  handleBridgeMessage({ type: 'tts', id: 'seg_0', t_start: 1.0,
                        t_end: 2.0, pcm24k: 'AAAA' });
  handleBridgeMessage({ type: 'tts', id: 'seg_1', t_start: 3.0,
                        t_end: 4.0, pcm24k: 'BBBB' });
  check('★ C2a 会话 S1 排程了 2 段', sb.__scheduled.length === 2,
    `实测 ${sb.__scheduled.length}`);

  // ── 新会话（S2）──
  handleBridgeMessage({ type: 'hello_ack', mode: 'real', engines_ready: true,
                        pipeline: true, session_id: 'S2' });
  check('★ C2b 新会话 hello_ack ⇒ seenDubIds 被清空',
    sb.__api.seenDubIds.size === 0, `实测 ${sb.__api.seenDubIds.size}`);

  // ★ 关键：旧服务端（段 id 没有会话前缀）时，
  //   新会话的段 id 与旧会话**撞号** ⇒ 清空后**必须**能排程。
  handleBridgeMessage({ type: 'tts', id: 'seg_0', t_start: 1.0,
                        t_end: 2.0, pcm24k: 'CCCC' });
  check('★★ C2c 新会话里与旧会话**撞号**的段 **不再被丢掉**',
    sb.__scheduled.length === 3, `实测 ${sb.__scheduled.length}`);
  check('★ C2d dubDelivered 同步 +1（没被当成重复）',
    sb.metrics.link.dubDelivered === 3,
    `实测 ${sb.metrics.link.dubDelivered}`);
}

// ══════════════════════════════════════════════════════════════════
// C3：★ 反证 —— 去掉「清空」这一步 ⇒ C2b/C2c 必须变红
// ══════════════════════════════════════════════════════════════════
console.log('\n[C3] ★ 反证：破坏「清空」逻辑 ⇒ 断言必须变红（harness 有区分力）');
if (!IS_CHILD) {
  const src = fs.readFileSync(PLAYER, 'utf8');
  // 把「清空 seenDubIds」替换成空操作（模拟没修的旧代码）
  const broken = src.replace(/seenDubIds\.clear\(\)/g, '/* broken */');
  check('★ C3a 反证用的源码确实被改坏（能改到 clear 调用）',
    broken !== src, '没找到 seenDubIds.clear() 调用');
  if (broken !== src) {
    const tmp = path.join(os.tmpdir(),
                          'ext026_broken_player_' + Date.now() + '.js');
    fs.writeFileSync(tmp, broken, 'utf8');
    const r = cp.spawnSync(process.execPath, [__filename, tmp],
      { encoding: 'utf8',
        env: Object.assign({}, process.env, { EXT026_CHILD: '1' }) });
    fs.unlinkSync(tmp);
    const out = r.stdout || '';
    check('★★ C3b 改坏后 C2b **必须 FAIL**（证明断言不是恒真）',
      out.includes('[FAIL] ★ C2b'),
      '改坏后的输出尾部：' + out.slice(-600));
    check('★★ C3c 改坏后 C2c **必须 FAIL**（撞号段必须被丢掉）',
      out.includes('[FAIL] ★★ C2c'),
      '改坏后的输出尾部：' + out.slice(-600));
    check('★ C3d 改坏后子进程退出码非 0',
      r.status !== 0, 'rc=' + r.status);
  }
}

// ══════════════════════════════════════════════════════════════════
// C4：★ 反证 —— 去掉「session_id」读取 ⇒ C2b/C2c 必须变红
// ══════════════════════════════════════════════════════════════════
console.log('\n[C4] ★ 反证：破坏 session_id 读取 ⇒ 断言必须变红');
if (!IS_CHILD) {
  const src = fs.readFileSync(PLAYER, 'utf8');
  const broken = src.replace(
    /const sid = \(m\.session_id == null\) \? null : String\(m\.session_id\);/,
    'const sid = null;');
  check('★ C4a 反证用的源码确实被改坏',
    broken !== src, '没找到 session_id 读取语句');
  if (broken !== src) {
    const tmp = path.join(os.tmpdir(),
                          'ext026_broken2_player_' + Date.now() + '.js');
    fs.writeFileSync(tmp, broken, 'utf8');
    const r = cp.spawnSync(process.execPath, [__filename, tmp],
      { encoding: 'utf8',
        env: Object.assign({}, process.env, { EXT026_CHILD: '1' }) });
    fs.unlinkSync(tmp);
    const out = r.stdout || '';
    check('★★ C4b 改坏后 C2b **必须 FAIL**',
      out.includes('[FAIL] ★ C2b'),
      '改坏后的输出尾部：' + out.slice(-600));
    check('★★ C4c 改坏后 C2c **必须 FAIL**',
      out.includes('[FAIL] ★★ C2c'),
      '改坏后的输出尾部：' + out.slice(-600));
  }
}

const npass = RESULTS.filter((r) => r.ok).length;
const nfail = RESULTS.length - npass;
console.log('\n============================================================');
console.log(`harness 结果：${npass} PASS / ${nfail} FAIL / 共 ${RESULTS.length}`);
console.log('============================================================');
process.exit(nfail === 0 ? 0 : 1);
