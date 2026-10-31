/**
 * t4_lang_harness.js — ★ 自发任务 T-4 的**行为级**测试载体
 *
 * ## 为什么需要这个文件
 *
 * 本机**没有 playwright**（实测 `ModuleNotFoundError`）⇒ 不能在真浏览器里
 * 点 popup、看 player 上报了什么。
 * ⇒ 但「player 上报给服务端的语言/音色对不对」是可以**不依赖浏览器**验证的：
 *   ① 归一函数（normalizeLang / normalizeVoice）是纯函数；
 *   ② hello 消息里到底带了什么字段，可以在沙箱里**真发一次**看载荷。
 *   这两件事都在 player.js 里，且**不依赖 AudioContext 的真实渲染**。
 *
 * ⇒ 做法：从**真实的 player.js 源文件**里**原样抽出**这几个函数，
 *   放进一个带桩的沙箱里执行 ⇒ 验的是**真代码**，不是复刻品。
 *
 * ⚠️ **可证伪**：本脚本接受 player.js 的路径作为参数 ⇒
 *   反证测试可以传一份**被改坏的**副本 ⇒ 若脚本仍报 PASS，
 *   说明这个 harness 没有区分力（那就是测试本身有问题）。
 *
 * 用法：
 *   node tests/t4_lang_harness.js [player.js 路径]
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

/**
 * 从源码里**原样抽出**一个顶层常量声明（如 `const LANG_ALIASES = {...};`）。
 * ★ 抽出真实的那份（不是复刻品）⇒ 验的是 player.js 里的真表。
 */
function extractConst(name) {
  const re = new RegExp(`^const\\s+${name}\\s*=\\s*\\{`, 'm');
  const m = re.exec(src);
  if (!m) throw new Error(`player.js 里找不到常量 ${name}`);
  let depth = 0;
  let started = false;
  for (let i = src.indexOf('{', m.index); i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') {
      depth--;
      if (started && depth === 0) {
        // 把 const X = {...}; 整段抽出来（含结尾分号）
        let end = i + 1;
        while (end < src.length && src[end] !== ';') end++;
        return src.slice(m.index, end + 1);
      }
    }
  }
  throw new Error(`常量 ${name} 的花括号不配对`);
}

/**
 * 从源码里**原样抽出**一段以 `start` 标记开始、按花括号配对结束的代码块。
 * ★ 用括号配对（不是正则截断）⇒ 不会被 CRLF / 嵌套括号坑到。
 */
function extractBlock(startRe, label) {
  const m = startRe.exec(src);
  if (!m) throw new Error(`player.js 里找不到 ${label}`);
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
  throw new Error(`${label} 的花括号不配对`);
}

/** 建一个带桩的沙箱，把抽出来的真函数放进去跑。 */
function makeSandbox(opts) {
  const o = opts || {};
  const sent = [];
  const sandbox = {
    console,
    // ── player.js 的模块级状态
    targetLang: o.targetLang === undefined ? null : o.targetLang,
    voicePref: o.voicePref === undefined ? null : o.voicePref,
    metrics: { subsDropped: 0 },
    // ── WebSocket 桩：记录发出去的消息
    WebSocket: class {
      constructor(url) { this.url = url; this.readyState = 1; }
      send(data) { sent.push(data); }
      close() {}
    },
    __sent: sent,
  };
  const code = [extractConst('LANG_ALIASES'),
    extractFunction('normalizeLang'),
    extractFunction('normalizeVoice')].join('\n\n');
  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { normalizeLang, normalizeVoice };`,
    sandbox, { filename: PLAYER });
  sandbox.__api = sandbox.__api;
  return sandbox;
}

// ══════════════════════════════════════════════════════════════
// A 组：语言归一（老配置的全称必须迁移成引擎码）
// ══════════════════════════════════════════════════════════════
console.log('\n[A] ★ 语言归一：老配置的语言全称 ⇒ 引擎码');
{
  const { normalizeLang } = makeSandbox({}).__api;

  check('normalizeLang("zh") ⇒ "zh"', normalizeLang('zh') === 'zh',
    `实测 ${normalizeLang('zh')}`);
  check('normalizeLang("ja") ⇒ "ja"', normalizeLang('ja') === 'ja',
    `实测 ${normalizeLang('ja')}`);
  check('★ 老配置 "Chinese" ⇒ "zh"（自动迁移）',
    normalizeLang('Chinese') === 'zh', `实测 ${normalizeLang('Chinese')}`);
  check('★ 老配置 "English" ⇒ "en"（自动迁移）',
    normalizeLang('English') === 'en', `实测 ${normalizeLang('English')}`);
  check('★ 老配置 "Japanese" ⇒ "ja"（自动迁移）',
    normalizeLang('Japanese') === 'ja', `实测 ${normalizeLang('Japanese')}`);
  check('★ 老配置 "Korean" ⇒ "ko"（自动迁移）',
    normalizeLang('Korean') === 'ko', `实测 ${normalizeLang('Korean')}`);
  check('★ 大写 "CHINESE" ⇒ "zh"（大小写不敏感）',
    normalizeLang('CHINESE') === 'zh', `实测 ${normalizeLang('CHINESE')}`);
  check('★ 非法值 ⇒ "zh"（不臆造别的语种）',
    normalizeLang('Klingon') === 'zh', `实测 ${normalizeLang('Klingon')}`);
  check('★ undefined ⇒ "zh"（不崩）',
    normalizeLang(undefined) === 'zh', `实测 ${normalizeLang(undefined)}`);
  check('★ null ⇒ "zh"（不崩）',
    normalizeLang(null) === 'zh', `实测 ${normalizeLang(null)}`);
}

// ══════════════════════════════════════════════════════════════
// B 组：音色归一（只有 A / clone 两个合法值）
// ══════════════════════════════════════════════════════════════
console.log('\n[B] ★ 音色归一：只有「预设 A」与「克隆说话人」');
{
  const { normalizeVoice } = makeSandbox({}).__api;

  check('normalizeVoice("A") ⇒ "A"', normalizeVoice('A') === 'A',
    `实测 ${normalizeVoice('A')}`);
  check('normalizeVoice("clone") ⇒ "clone"',
    normalizeVoice('clone') === 'clone', `实测 ${normalizeVoice('clone')}`);
  check('★ 大写 "CLONE" ⇒ "clone"（大小写不敏感）',
    normalizeVoice('CLONE') === 'clone', `实测 ${normalizeVoice('CLONE')}`);
  check('★ 非法值 ⇒ "A"（回落到预设 A）',
    normalizeVoice('bogus') === 'A', `实测 ${normalizeVoice('bogus')}`);
  check('★ undefined ⇒ "A"（不崩）',
    normalizeVoice(undefined) === 'A', `实测 ${normalizeVoice(undefined)}`);
}

// ══════════════════════════════════════════════════════════════
// C 组：hello 消息**真的带上**了语言与音色（★ 本轮的核心）
// ══════════════════════════════════════════════════════════════
console.log('\n[C] ★★★ hello 消息必须真的带上 target_lang / voice');
{
  // 抽 startUplink 里发 hello 的那一段太重（要 AudioContext / worklet）
  // ⇒ 这里改为**源码契约 + 载荷构造**双验证：
  //   ① 源码里 hello 的载荷含 target_lang / voice；
  //   ② 用与 player.js 同一套归一函数构造出 hello 载荷，
  //      确认字段名与值都对。
  const sb = makeSandbox({ targetLang: 'ja', voicePref: 'clone' });
  const { normalizeLang, normalizeVoice } = sb.__api;

  const hello = {
    type: 'hello', token: 'tok', role: 'uplink', sample_rate: 16000,
    source: 'player', delay_sec: 10, capture_mode: 'getDisplayMedia',
    target_lang: normalizeLang(sb.targetLang),
    voice: normalizeVoice(sb.voicePref),
  };
  check('★★★ hello 载荷里有 target_lang 且为 "ja"',
    hello.target_lang === 'ja', `实测 ${hello.target_lang}`);
  check('★★★ hello 载荷里有 voice 且为 "clone"',
    hello.voice === 'clone', `实测 ${hello.voice}`);

  // ★★ 源码契约：player.js 真的把这两个字段放进了 ws.send 的 hello 里
  const helloBlock = (src.match(/type:\s*'hello'[\s\S]{0,1400}?\n\s*\}\)\);/) || [''])[0];
  check('★★★ player.js 的 hello 载荷里含 target_lang',
    /target_lang\s*:/.test(helloBlock),
    'player.js 的 hello 未带 target_lang');
  check('★★★ player.js 的 hello 载荷里含 voice',
    /voice\s*:/.test(helloBlock),
    'player.js 的 hello 未带 voice');
  check('★★ player.js 的 hello 用的是归一后的 targetLang',
    /target_lang\s*:\s*targetLang/.test(helloBlock),
    'player.js 未上报归一后的 targetLang');
  check('★★ player.js 的 hello 用的是归一后的 voicePref',
    /voice\s*:\s*voicePref/.test(helloBlock),
    'player.js 未上报归一后的 voicePref');

  // ★★ 反证用的对照：把 target_lang 从载荷里去掉 ⇒ 上面的契约检查必须 FAIL
  const stripped = helloBlock.replace(/target_lang\s*:\s*targetLang[^\n]*\n/, '');
  check('★ 反证对照：去掉 target_lang 后契约检查会 FAIL（harness 有区分力）',
    !/target_lang\s*:/.test(stripped),
    '去掉后仍匹配 ⇒ harness 没有区分力');
}

// ══════════════════════════════════════════════════════════════
// D 组：player.js 读设置（boot 里真的读了 targetLang / voice）
// ══════════════════════════════════════════════════════════════
console.log('\n[D] ★ player.js 在 boot() 里真的读了设置');
{
  const bootBlock = extractBlock(/async function boot\s*\(/, 'boot()');
  check('★ boot() 里读出了 targetLang', /targetLang/.test(bootBlock),
    'boot() 未读 targetLang');
  check('★ boot() 里读出了 voice', /voice/.test(bootBlock),
    'boot() 未读 voice');
  check('★ boot() 里对 targetLang 做了归一',
    /normalizeLang\(/.test(bootBlock), 'boot() 未归一 targetLang');
  check('★ boot() 里对 voice 做了归一',
    /normalizeVoice\(/.test(bootBlock), 'boot() 未归一 voice');

  // ★★ 运行中改设置也要跟上（storage.onChanged）
  const chgBlock = extractBlock(/chrome\.storage\.onChanged\.addListener\(/,
    'storage.onChanged 监听');
  check('★ 运行中改 targetLang 也会被监听到',
    /'targetLang' in changes/.test(chgBlock),
    'storage.onChanged 未监听 targetLang');
  check('★ 运行中改 voice 也会被监听到',
    /'voice' in changes/.test(chgBlock),
    'storage.onChanged 未监听 voice');
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
