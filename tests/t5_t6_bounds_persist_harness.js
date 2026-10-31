/**
 * t5_t6_bounds_persist_harness.js — ★ 自发任务 T-5 / T-6 的**行为级**测试载体
 *
 * ## 为什么需要这个文件
 *
 * 本机**没有 playwright**（实测 `ModuleNotFoundError`）⇒ 不能在真浏览器里
 * 拖滑块、关弹窗。但下面这两件事是**可以脱离浏览器验证**的：
 *
 *   * **T-5（内存不持续增长）**：把 `gapDetail` 灌到远超上限的条数，
 *     看它**有没有被裁剪到上限**（而不是无限增长）；
 *     以及「统计口径不因裁剪而改变」。
 *   * **T-6（设置持久化）**：把 `popup.js` 的**真实函数**抽到沙箱里，
 *     模拟「用户改了设置但**没点开始**就关掉弹窗」，
 *     看设置**有没有被写进 storage**。
 *
 * ⇒ 做法：从**真实的 player.js / popup.js 源文件**里**原样抽出**相关函数，
 *   放进带桩的沙箱里执行 ⇒ 验的是**真代码**，不是复刻品。
 *
 * ⚠️ **可证伪**：本脚本接受源码路径作为参数（argv[2]=player.js,
 *   argv[3]=popup.js）⇒ 反证测试可以传一份**被改坏的**副本
 *   ⇒ 若脚本仍报 PASS，说明这个 harness 没有区分力（那就是测试本身有问题）。
 *
 * 用法：
 *   node tests/t5_t6_bounds_persist_harness.js [player.js 路径] [popup.js 路径]
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

const playerSrc = fs.readFileSync(PLAYER, 'utf8');
const popupSrc = fs.readFileSync(POPUP, 'utf8');

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
function extractFunction(src, name) {
  // ★ 同时支持 `function f(` 与 `async function f(`
  const re = new RegExp(`^(async\\s+)?function\\s+${name}\\s*\\(`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`源码里找不到函数 ${name}`);
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

/** 从源码里抽一个顶层 `const NAME = <数字>;` 常量的值。 */
function extractConst(src, name) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*(\\d+)\\s*;`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`源码里找不到常量 ${name}`);
  return parseInt(m[1], 10);
}

/**
 * 从源码里**原样抽出**一段以 `if (...) {` 开头、以配对花括号结束的代码块。
 * ★ 用括号配对而不是正则截断 ⇒ 不会把块切一半，
 *   也不受缩进影响（正则在缩进变化时会失效）。
 */
function extractBlock(src, headerRe) {
  const m = headerRe.exec(src);
  if (!m) throw new Error(`源码里找不到匹配 ${headerRe} 的代码块`);
  const start = m.index;
  let depth = 0;
  let started = false;
  for (let i = src.indexOf('{', start); i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') {
      depth--;
      if (started && depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error(`代码块 ${headerRe} 的花括号不配对`);
}

// ══════════════════════════════════════════════════════════════
// A 组（T-5）：player.js 的 gapDetail 必须**有界**
// ══════════════════════════════════════════════════════════════
console.log('\n[A] ★ T-5：player.js 的 gapDetail 必须有界（不无限增长）');

const GAP_CAP_PLAYER = extractConst(playerSrc, 'GAP_DETAIL_CAP');

{
  // ★ 这里不抽整个 onUplinkFrame（它依赖 AudioWorklet 桩），
  //   而是**原样抽出**裁剪逻辑所在的整个 `if` 块执行。
  const block = extractBlock(playerSrc,
    /if \(upState\.gapDetail\.length > GAP_DETAIL_CAP\) \{/);

  const sb = {
    console,
    GAP_DETAIL_CAP: GAP_CAP_PLAYER,
    upState: { gapDetail: [], gapDetailDropped: 0 },
  };
  vm.createContext(sb);
  vm.runInContext(block, sb, { filename: PLAYER });

  // 灌 10 000 条（远超上限）⇒ 必须被裁到上限
  for (let i = 0; i < 10000; i++) {
    sb.upState.gapDetail.push({ kind: 'seq', expect: i, got: i + 1 });
    vm.runInContext(block, sb, { filename: PLAYER });
  }
  check(`★ T-5：player.js 的 gapDetail 灌 10 000 条后被裁到 ≤ ${GAP_CAP_PLAYER}`,
    sb.upState.gapDetail.length <= GAP_CAP_PLAYER,
    `实测 ${sb.upState.gapDetail.length} 条`);
  check('★ T-5：裁掉的条数**如实计数**（不静默丢）',
    (sb.upState.gapDetailDropped || 0) > 0,
    `实测 dropped=${sb.upState.gapDetailDropped}`);
  check('★ T-5：保留的应是**最近**的条（最新一条还在）',
    sb.upState.gapDetail.length > 0
    && sb.upState.gapDetail[sb.upState.gapDetail.length - 1].got === 10000,
    `实测最后一条 got=`
    + `${sb.upState.gapDetail.length ? sb.upState.gapDetail[sb.upState.gapDetail.length - 1].got : '无'}`);
}

// ── 反证：把裁剪块改坏（恒真短路）⇒ 上面必须 FAIL ──────────
{
  const broken = playerSrc.replace(
    /if \(upState\.gapDetail\.length > GAP_DETAIL_CAP\) \{[\s\S]*?\n    \}/,
    'if (false) { /* 反证：裁剪被短路 */ }');
  if (broken === playerSrc) throw new Error('反证替换失败：没匹配到裁剪块');
  const block2 = extractBlock(broken,
    /if \(false\) \{ \/\* 反证：裁剪被短路 \*\/ \}/);
  const sb = {
    console,
    GAP_DETAIL_CAP: GAP_CAP_PLAYER,
    upState: { gapDetail: [], gapDetailDropped: 0 },
  };
  vm.createContext(sb);
  vm.runInContext(block2, sb, { filename: 'broken-player.js' });
  for (let i = 0; i < 10000; i++) {
    sb.upState.gapDetail.push({ kind: 'seq', expect: i, got: i + 1 });
    vm.runInContext(block2, sb, { filename: 'broken-player.js' });
  }
  check('★ T-5 反证：裁剪被短路后 gapDetail **确实会无限增长**（证明上面断言有区分力）',
    sb.upState.gapDetail.length > GAP_CAP_PLAYER,
    `实测 ${sb.upState.gapDetail.length} 条`);
}

// ══════════════════════════════════════════════════════════════
// B 组（T-5）：offscreen.js 的 gapDetail 也必须有界
// ══════════════════════════════════════════════════════════════
console.log('\n[B] ★ T-5：offscreen.js 的 gapDetail 必须有界');
{
  const offSrc = fs.readFileSync(path.join(ROOT, 'extension', 'offscreen.js'), 'utf8');
  const CAP = extractConst(offSrc, 'GAP_DETAIL_CAP');
  const block = extractBlock(offSrc,
    /if \(state\.gapDetail\.length > GAP_DETAIL_CAP\) \{/);
  const sb = {
    console,
    GAP_DETAIL_CAP: CAP,
    state: { gapDetail: [], gapDetailDropped: 0 },
  };
  vm.createContext(sb);
  vm.runInContext(block, sb, { filename: 'offscreen.js' });
  for (let i = 0; i < 10000; i++) {
    sb.state.gapDetail.push({ kind: 'seq', expect: i, got: i + 1 });
    vm.runInContext(block, sb, { filename: 'offscreen.js' });
  }
  check(`★ T-5：offscreen.js 的 gapDetail 灌 10 000 条后被裁到 ≤ ${CAP}`,
    sb.state.gapDetail.length <= CAP, `实测 ${sb.state.gapDetail.length} 条`);
  check('★ T-5：offscreen.js 裁掉的条数如实计数',
    (sb.state.gapDetailDropped || 0) > 0, `实测 dropped=${sb.state.gapDetailDropped}`);
}

// ══════════════════════════════════════════════════════════════
// C 组（T-6）：popup.js 的设置**改了就落盘**（不等点「开始」）
// ══════════════════════════════════════════════════════════════
console.log('\n[C] ★ T-6：popup.js 的设置改了立刻落盘（不等点「开始」）');

/** 建一个带 chrome.storage 桩 + DOM 桩的 popup 沙箱。 */
function makePopupSandbox(srcOverride) {
  const src = srcOverride || popupSrc;
  const store = {};
  const writes = [];
  const els = {
    ws: { value: 'ws://127.0.0.1:8765/', type: 'text' },
    token: { value: '', type: 'text' },
    delay: { value: '10', type: 'number' },
    lang: { value: 'zh', type: 'select-one' },
    voice: { value: 'A', type: 'select-one' },
    duck: { value: '-15', type: 'number' },
    subs: { checked: true, type: 'checkbox' },
    player: { checked: false, type: 'checkbox' },
  };
  const listeners = {};
  for (const id of Object.keys(els)) {
    listeners[id] = { change: [], input: [] };
    els[id].addEventListener = (ev, fn) => {
      (listeners[id][ev] = listeners[id][ev] || []).push(fn);
    };
  }
  const sb = {
    console,
    setTimeout, clearTimeout,
    els,
    listeners,
    writes,
    store,
    chrome: {
      storage: {
        local: {
          set: async (obj) => {
            writes.push(obj);
            Object.assign(store, obj);
          },
          get: async (defs) => {
            const out = {};
            for (const k of Object.keys(defs)) {
              out[k] = (k in store) ? store[k] : defs[k];
            }
            return out;
          },
        },
      },
      tabs: { create: async () => {}, query: async () => [{ id: 1, title: 't' }] },
      runtime: { sendMessage: async () => ({ ok: true }), getURL: (p) => p },
    },
    document: { getElementById: (id) => els[id] || null },
    $: (id) => els[id] || null,
  };
  // popup.js 里的 $ 是顶层 const ⇒ 在沙箱里直接提供 $ 即可
  vm.createContext(sb);

  // 抽出需要验证的函数：readCfg / persistCfgNow / schedulePersistCfg /
  // bindPersistListeners / normalizeLang / normalizeVoice / loadCfg
  const names = ['readCfg', 'persistCfgNow', 'schedulePersistCfg',
    'bindPersistListeners', 'normalizeLang', 'normalizeVoice'];
  const code = names.map((n) => extractFunction(src, n)).join('\n\n');
  // LANG_ALIASES 是 const 对象，原样取出来
  const alias = /const LANG_ALIASES = \{[\s\S]*?\n\};/.exec(src);
  vm.runInContext(
    (alias ? alias[0] + '\n\n' : '') + code
    + '\n;globalThis.__api = { readCfg, persistCfgNow, schedulePersistCfg, '
    + 'bindPersistListeners, normalizeLang, normalizeVoice };',
    sb, { filename: POPUP });
  sb.__api = sb.__api;
  return sb;
}

{
  const sb = makePopupSandbox();
  const { readCfg, persistCfgNow, bindPersistListeners } = sb.__api;

  bindPersistListeners();

  // 模拟用户：改了「目标语言 / 延迟 D / 原声压低量 / 字幕开关」
  sb.els.lang.value = 'ja';
  sb.els.delay.value = '15';
  sb.els.duck.value = '-25';
  sb.els.subs.checked = false;

  // ★ 关键：**不点「开始」**，只触发 change 事件
  for (const id of ['lang', 'delay', 'duck', 'subs']) {
    for (const fn of sb.listeners[id].change) fn();
  }

  check('★ T-6：popup 给所有设置控件都挂了 change 监听',
    sb.listeners.lang.change.length > 0 && sb.listeners.delay.change.length > 0
    && sb.listeners.duck.change.length > 0 && sb.listeners.subs.change.length > 0,
    `lang=${sb.listeners.lang.change.length} delay=${sb.listeners.delay.change.length}`
    + ` duck=${sb.listeners.duck.change.length} subs=${sb.listeners.subs.change.length}`);

  check('★ T-6：文本框/数字框额外挂了 input 监听（即时保存用）',
    sb.listeners.ws.input.length > 0 && sb.listeners.delay.input.length > 0
    && sb.listeners.duck.input.length > 0,
    `ws=${sb.listeners.ws.input.length} delay=${sb.listeners.delay.input.length}`);

  check('★ T-6：★ 改了设置**且没点开始** ⇒ 已经写进了 storage',
    sb.writes.length > 0, `实测写入 ${sb.writes.length} 次`);

  const last = sb.writes.length ? sb.writes[sb.writes.length - 1] : {};
  check('★ T-6：落盘的目标语言 = 用户选的值（ja）',
    last.targetLang === 'ja', `实测 ${last.targetLang}`);
  check('★ T-6：落盘的延迟 D = 15', Number(last.delaySec) === 15,
    `实测 ${last.delaySec}`);
  check('★ T-6：落盘的原声压低量 = -25', Number(last.duckDb) === -25,
    `实测 ${last.duckDb}`);
  check('★ T-6：落盘的字幕开关 = false', last.subsOn === false,
    `实测 ${last.subsOn}`);

  // ★ 归一口径：老配置里的语言**全称**必须被归一成引擎码再落盘
  sb.els.lang.value = 'Chinese';
  const cfg = readCfg();
  check('★ T-6：语言全称在落盘前被归一成引擎码（zh）',
    cfg.targetLang === 'zh', `实测 ${cfg.targetLang}`);

  // ★ 幂等：重复绑定不会挂重复监听
  const before = sb.listeners.lang.change.length;
  bindPersistListeners();
  check('★ T-6：重复调用 bindPersistListeners 不会挂重复监听（幂等）',
    sb.listeners.lang.change.length === before,
    `实测 ${before} → ${sb.listeners.lang.change.length}`);
}

// ── 反证：把绑定函数改坏（不挂监听）⇒ 上面必须 FAIL ────────────
{
  // ⚠️ **行尾符无关**：仓库里的 .js 可能被 git 以 CRLF 检出
  //   ⇒ 正则里不能写死 `\n` ⇒ 统一用 `\r?\n`。
  const broken = popupSrc.replace(
    /function bindPersistListeners\(\) \{[\s\S]*?\r?\n\}\r?\n/,
    'function bindPersistListeners() { /* 反证：不挂监听 */ }\n');
  if (broken === popupSrc) throw new Error('反证替换失败：没匹配到 bindPersistListeners');
  // ★ 用**全新的沙箱**（被改坏的源码）⇒ 不能复用上面那个已声明过
  //   LANG_ALIASES 的上下文（会抛 "already been declared"）。
  const sb = makePopupSandbox(broken);
  sb.__api.bindPersistListeners();
  sb.els.lang.value = 'ja';
  for (const fn of sb.listeners.lang.change) fn();
  check('★ T-6 反证：不挂监听时**不会**写盘（证明上面断言有区分力）',
    sb.writes.length === 0, `实测写入 ${sb.writes.length} 次`);
}

// ══════════════════════════════════════════════════════════════
// 汇总
// ══════════════════════════════════════════════════════════════
const failed = RESULTS.filter((r) => !r.ok);
console.log('\n' + '='.repeat(60));
console.log(`结果：${RESULTS.length - failed.length} PASS / ${failed.length} FAIL / 共 ${RESULTS.length}`);
console.log('='.repeat(60));
if (failed.length) {
  for (const f of failed) console.log(`  FAIL: ${f.name} — ${f.detail}`);
  process.exit(1);
}
process.exit(0);
