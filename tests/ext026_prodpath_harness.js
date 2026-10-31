/**
 * ext026_prodpath_harness.js — ★ EXT-026 **生产路径**新行为的插件侧行为级测试载体
 *
 * ## 验什么（EXT-026 真实跑批抓到的 3 个生产路径缺陷）
 *
 * ★★★ P1：**生产路径下状态条段数恒为 0**
 *   根因：`pollStats()` 只认 `upState.ws`（player 自己抓流时的那条上行 WS）。
 *   但**生产路径**（popup 点「开始」→ offscreen 抓流 → offscreen 上行）
 *   下，player 的 `upState.ws` 是 **null** ⇒ stats 永远发不出去
 *   ⇒ `asrSegments/mtSegments/ttsSegments` 恒为 0
 *   ⇒ 「TTS 一段都没出」这个最关键的故障信号显示不出来。
 *   ⇒ 修法：回落用 player 自己那条 WS（role=player，服务端按 token 拿真会话）。
 *
 * ★★★ P2：**生产路径没有 flush ⇒ 尾段永远丢**
 *   根因：`sw.js` 与 `offscreen.js` 都**没有** flush 命令
 *   ⇒ 生产路径（offscreen 的上行 WS）永远收不了口
 *   ⇒ 用户点「停止」时最后一句永远没配音。
 *   ⇒ 修法：offscreen 加 `flushUplink()` + SW 加 `flush` 中转 + popup 加按钮。
 *
 * ★★★ P3：**popup 的桥接地址只存 storage 不够**
 *   根因：`popup.js` 的 `loadCfg()` 在页面加载时把 storage 的值**读进 DOM 输入框**
 *   ⇒ 页面加载**之后**再写 storage，输入框里仍是旧值（8765）
 *   ⇒ 点「开始」时 `saveCfg()` 把输入框的旧值写回 ⇒ 连不上桥接。
 *   ⇒ （这是**测试脚手架**要配合的地方，不是产品缺陷；但要在 harness 里锁住）
 *
 * ## ★ 可证伪
 *   每组都有**反证**：把对应实现改坏 ⇒ 对应断言必须变红。
 *   ⚠️ 反证用**子进程**跑（环境变量 EXT026_PROD_CHILD=1 ⇒ 子进程不递归）。
 *
 * 用法：
 *   node tests/ext026_prodpath_harness.js
 * 退出码 0 = 全部通过。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const cp = require('child_process');

const ROOT = path.dirname(__dirname);
const IS_CHILD = process.env.EXT026_PROD_CHILD === '1';

const OFFSCREEN = process.env.EXT026_PROD_OFFSCREEN
  ? path.resolve(process.env.EXT026_PROD_OFFSCREEN)
  : path.join(ROOT, 'extension', 'offscreen.js');
const SW = process.env.EXT026_PROD_SW
  ? path.resolve(process.env.EXT026_PROD_SW)
  : path.join(ROOT, 'extension', 'sw.js');
const POPUP = process.env.EXT026_PROD_POPUP
  ? path.resolve(process.env.EXT026_PROD_POPUP)
  : path.join(ROOT, 'extension', 'popup.js');
const PLAYER = process.env.EXT026_PROD_PLAYER
  ? path.resolve(process.env.EXT026_PROD_PLAYER)
  : path.join(ROOT, 'extension', 'player.js');
const POPUP_HTML = path.join(ROOT, 'extension', 'popup.html');

const osrc = fs.readFileSync(OFFSCREEN, 'utf8');
const ssrc = fs.readFileSync(SW, 'utf8');
const popupSrc = fs.readFileSync(POPUP, 'utf8');
const plsrc = fs.readFileSync(PLAYER, 'utf8');

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
  let depth = 0, started = false;
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
 * 建一个带桩的沙箱，跑**抽出来的真函数**。
 * @param {object} opts
 *   - playerWsReady: player 自己那条 WS 是否连着
 *   - upWsReady:     player 的上行 WS（生产路径下为 null）
 */
function makePlayerSandbox(opts) {
  const o = opts || {};
  const sent = [];

  function mkWs(ready) {
    return {
      readyState: ready ? 1 : 0,
      send: (s) => { sent.push(JSON.parse(s)); },
      close: () => {},
    };
  }

  const sandbox = {
    console, isNaN, setTimeout, clearTimeout, setInterval, clearInterval,
    // ★ player 自己那条 WS（role=player）
    ws: mkWs(o.playerWsReady !== false),
    // ★ player 的上行 WS —— 生产路径下是 null
    upState: { ws: o.upWsReady === false ? null : mkWs(true), running: true },
    report: () => {},
  };

  const code = [
    extractFunction(plsrc, 'pollStats', 'player.js'),
  ].join('\n\n');

  vm.createContext(sandbox);
  vm.runInContext(
    `${code}\n;globalThis.__api = { pollStats };`,
    sandbox, { filename: PLAYER });
  vm.runInContext(
    'const metrics = { link: {} };', sandbox, { filename: PLAYER });

  sandbox.__sent = sent;
  return sandbox;
}

/** offscreen 的 flushUplink 沙箱。 */
function makeOffscreenSandbox(opts) {
  const o = opts || {};
  const sent = [];
  const fakeWS = {
    readyState: o.wsReady === false ? 0 : 1,
    send: (s) => { sent.push(JSON.parse(s)); },
    close: () => {},
  };

  const sandbox = {
    console, isNaN,
    WebSocket: { OPEN: 1 },
    state: { ws: fakeWS },
    log: () => {},
  };

  const code = extractFunction(osrc, 'flushUplink', 'offscreen.js');
  vm.createContext(sandbox);
  vm.runInContext(`${code}\n;globalThis.__api = { flushUplink };`,
    sandbox, { filename: OFFSCREEN });

  sandbox.__sent = sent;
  return sandbox;
}

// ══════════════════════════════════════════════════════════════════
(async function main() {

// ── P1：pollStats 的连接回落 ────────────────────────────────────
console.log('\n[P1] 生产路径下 pollStats 必须能发出去');

const p1a = makePlayerSandbox({ upWsReady: false, playerWsReady: true });
p1a.__api.pollStats();
check('★ 生产路径（上行 WS 不存在）⇒ pollStats 仍发出 stats',
  p1a.__sent.length === 1 && p1a.__sent[0].type === 'stats',
  `sent=${JSON.stringify(p1a.__sent)}`);

const p1b = makePlayerSandbox({ upWsReady: true, playerWsReady: true });
p1b.__api.pollStats();
check('★ 有上行 WS 时优先走上行（与产出段同源）',
  p1b.__sent.length === 1 && p1b.__sent[0].type === 'stats',
  `sent=${JSON.stringify(p1b.__sent)}`);

const p1c = makePlayerSandbox({ upWsReady: false, playerWsReady: false });
p1c.__api.pollStats();
check('两条 WS 都没连 ⇒ 安静跳过（不抛异常）',
  p1c.__sent.length === 0, `sent=${JSON.stringify(p1c.__sent)}`);

// ── P2：offscreen 的 flushUplink ───────────────────────────────
console.log('\n[P2] 生产路径必须能 flush（收口尾段）');

const p2a = makeOffscreenSandbox({});
const r2a = p2a.__api.flushUplink();
check('★ offscreen 发出 {"type":"flush"}',
  p2a.__sent.length === 1 && p2a.__sent[0].type === 'flush',
  `sent=${JSON.stringify(p2a.__sent)}`);
check('★ flushUplink 返回 ok=true', r2a && r2a.ok === true,
  JSON.stringify(r2a));

const p2b = makeOffscreenSandbox({ wsReady: false });
const r2b = p2b.__api.flushUplink();
check('WS 没连 ⇒ 如实返回失败（不假装成功）',
  r2b && r2b.ok === false, JSON.stringify(r2b));
check('WS 没连 ⇒ 不会发出任何消息',
  p2b.__sent.length === 0, `sent=${JSON.stringify(p2b.__sent)}`);

// ── P3：源码契约（SW 中转 / popup 按钮 / player 按钮） ───────
console.log('\n[P3] 源码契约（SW 中转 + popup 按钮）');

check('★ sw.js 有 flush 命令中转到 offscreen',
  /case\s+'flush'\s*:/.test(ssrc)
  && /offscreenCall\(\s*'flush'/.test(ssrc),
  'sw.js 里找不到 flush 中转');

check('★ offscreen.js 的 handleOffscreen 支持 flush',
  /case\s+'flush'\s*:/.test(osrc), 'offscreen.js 里找不到 flush 分支');

check('★ popup.html 有「停止并收尾」按钮',
  /id="btnFlush"/.test(fs.readFileSync(POPUP_HTML, 'utf8')),
  'popup.html 里找不到 btnFlush');

check('★ popup.js 绑定了 btnFlush 且先 flush 再 stop',
  /btnFlush/.test(popupSrc)
  && /cmd:\s*'flush'/.test(popupSrc),
  'popup.js 里找不到 flush 接线');

// ── P4：popup 的桥接地址（DOM 与 storage 要一致） ────────────
console.log('\n[P4] popup 的桥接地址口径');

check('★ popup.js 的 loadCfg 会把 storage 读进 DOM 输入框',
  /\$\('ws'\)\.value\s*=\s*cfg\.wsUrl/.test(popupSrc),
  '没找到 $("ws").value = cfg.wsUrl');

check('★ popup.js 的 pairUrl 从 ws 端口推出配对端口（8765⇒8766，其它 +1）',
  /u\.port\s*===\s*'8765'/.test(popupSrc) && /\+\s*1/.test(popupSrc),
  '没找到 pairUrl 的端口推导');

// ── ★ 反证组（把实现改坏 ⇒ 上面必须变红） ────────────────────
if (!IS_CHILD) {
  console.log('\n[反证] 改坏实现 ⇒ 对应断言必须变红');

  const cases = [
    {
      name: '★ 反证 A：pollStats 只认 upState.ws（生产路径段数恒 0）',
      file: PLAYER,
      // ★ 把「回落到 player 自己那条 WS」那段改成**什么都不做**
      //   ⚠️ 文件是 **CRLF** 换行 ⇒ 正则里用 `\r?\n`（否则匹配不到）
      from: /const w = \(typeof ws !== 'undefined'\) \? ws : null;[\s\S]*?metrics\.link\.statsPolled = \(metrics\.link\.statsPolled \|\| 0\) \+ 1;\r?\n\s*\}/,
      to: 'const w = null; // 故意改坏：生产路径没有回落\n    if (false) { }',
      expectFail: '生产路径（上行 WS 不存在）',
    },
    {
      name: '★ 反证 B：offscreen 的 flushUplink 不发 flush',
      file: OFFSCREEN,
      from: /ws\.send\(JSON\.stringify\(\{ type: 'flush' \}\)\);/,
      to: '// 故意改坏：不发 flush',
      expectFail: 'offscreen 发出',
    },
    {
      name: '★ 反证 C：SW 不再中转 flush',
      file: SW,
      from: /offscreenCall\('flush', \{\}, 8000\)/,
      to: "offscreenCall('stats', {}, 8000)",
      expectFail: 'sw.js 有 flush 命令中转',
    },
    {
      name: '★ 反证 D：popup 没有 flush 按钮接线',
      file: POPUP,
      from: /cmd:\s*'flush'/,
      to: "cmd: 'noFlush'",
      expectFail: 'popup.js 绑定了 btnFlush',
    },
  ];

  for (const c of cases) {
    const src = fs.readFileSync(c.file, 'utf8');
    if (!c.from.test(src)) {
      console.log(`  [WARN] 反证 ${c.name}：目标代码没找到（跳过）`);
      continue;
    }
    const broken = src.replace(c.from, c.to);
    const tmp = path.join(ROOT, 'tests',
      `.tmp_broken_${path.basename(c.file)}`);
    fs.writeFileSync(tmp, broken, 'utf8');
    // ★ 反证要跑**同一个 harness**，但把被改坏的文件喂进去
    //   （用环境变量告诉子进程读哪个文件 ⇒ 子进程只跑断言，不递归反证）
    const env = Object.assign({}, process.env, { EXT026_PROD_CHILD: '1' });
    const key = ({
      [PLAYER]: 'EXT026_PROD_PLAYER',
      [OFFSCREEN]: 'EXT026_PROD_OFFSCREEN',
      [SW]: 'EXT026_PROD_SW',
      [POPUP]: 'EXT026_PROD_POPUP',
    })[c.file];
    env[key] = tmp;
    const res = cp.spawnSync(process.execPath, [__filename], {
      env, encoding: 'utf8',
    });
    const out = (res.stdout || '') + (res.stderr || '');
    // ★ 判定：子进程里**那一条断言**必须报 FAIL
    const failed = /\[FAIL\][^\n]*\S/.test(out)
      && out.split('\n').some(
        (ln) => ln.includes('[FAIL]') && ln.includes(c.expectFail));
    check(c.name, failed,
      failed ? '（断言如期变红 ✓）'
             : `未如期变红（期望含「${c.expectFail}」的 FAIL）：\n${out.slice(0, 800)}`);
    try { fs.unlinkSync(tmp); } catch (e) { /* ignore */ }
  }
}

// ══════════════════════════════════════════════════════════════════
console.log('\n' + '='.repeat(68));
const npass = RESULTS.filter((r) => r.ok).length;
const nfail = RESULTS.length - npass;
console.log(`harness 结果：${npass} PASS / ${nfail} FAIL / 共 ${RESULTS.length}`);
console.log('='.repeat(68));
process.exit(nfail === 0 ? 0 : 1);

})().catch((e) => {
  console.error('harness 崩溃：', e);
  process.exit(2);
});
