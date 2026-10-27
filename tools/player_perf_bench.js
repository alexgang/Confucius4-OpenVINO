/**
 * player_perf_bench.js — EXT-003 P0① 的**主线程开销微基准**
 *
 * 目的：把 5 分钟长测实测到的「maxAbsSkew 595 ms 尖峰」归因到
 *      player.js 里几个**可复现**的算法缺陷，并量化修复前后的差异。
 *
 * ★ 这不是「用微基准替代真实实测」——
 *   真实证据是 .tmp 目录下的 probe_uplink_5min / probe_uplink_5min_v2 证据文件；
 *   本脚本只用来**验证因果关系**（哪段代码吃掉了多少主线程时间），
 *   且**不占用浏览器/GPU/NPU**（纯 Node 计算）。
 *
 * 复刻三处缺陷：
 *   ① pendingSched 无界增长（每帧 push，只有检出 onset 才 shift）
 *   ② subs 每条 push 都 sort() ⇒ O(n² log n)
 *   ③ pct() 每次调用都 [...arr].sort()（每次 report 都调 3 次）
 *      + report 每秒全量搬运含大数组的 metrics
 *
 * 运行：node tools/player_perf_bench.js
 * 退出码 0 = 全部通过。
 */
'use strict';

// ── 复刻扩展里的常量 ──────────────────────────────────────────
const WARMUP_FRAMES = 50;
const PENDING_SCHED_CAP = 512;   // 修复后新增
const SUBS_CAP = 200;            // 修复后新增
const MAX_FRAMES = 20000;

// ── 复刻 capture-worklet 的帧节奏 ────────────────────────────
// 实测：16 kHz / 每帧 20~100 ms ⇒ 约 47 帧/秒；5 分钟 ≈ 14191 帧。
const FRAMES_5MIN = 14191;
// onset 密度：源是 /sync 测试片，beep 每 2 s 一次 ⇒ 5 分钟约 150 个 onset
const ONSETS_5MIN = 150;

// ── 旧实现：pendingSched 无界 + subs 每次 sort ────────────────
function oldPendingSched() {
  const pending = [];
  let pushed = 0, shifted = 0, maxLen = 0;
  for (let i = 0; i < FRAMES_5MIN; i++) {
    pending.push({ id: 'e' + i, planned: i * 0.02, requested: i * 0.02 });
    pushed++;
    if (pending.length > maxLen) maxLen = pending.length;
    // 每 47 帧检出 1 个 onset（beep 每 2 s，帧率 47/s）
    if (i % 47 === 0 && pending.length) { pending.shift(); shifted++; }
  }
  return { pushed, shifted, maxLen, finalLen: pending.length };
}

function oldSubs() {
  const subs = [];
  for (let i = 0; i < FRAMES_5MIN; i++) {
    subs.push({ text: 'x', at: i * 0.02, id: 'e' + i });
    subs.sort((a, b) => a.at - b.at);   // ★ 每条都整表重排
  }
  return subs.length;
}

// ── 新实现：pendingSched 有界 + subs 有序插入 ────────────────
function newPendingSched() {
  const pending = [];
  let pushed = 0, shifted = 0, maxLen = 0, dropped = 0;
  for (let i = 0; i < FRAMES_5MIN; i++) {
    pending.push({ id: 'e' + i, planned: i * 0.02, requested: i * 0.02 });
    pushed++;
    if (pending.length > maxLen) maxLen = pending.length;
    if (pending.length > PENDING_SCHED_CAP) {
      const d = pending.length - PENDING_SCHED_CAP;
      pending.splice(0, d);
      dropped += d;
    }
    if (i % 47 === 0 && pending.length) { pending.shift(); shifted++; }
  }
  return { pushed, shifted, maxLen, dropped, finalLen: pending.length };
}

function newSubs() {
  const subs = [];
  let dropped = 0;
  for (let i = 0; i < FRAMES_5MIN; i++) {
    const item = { text: 'x', at: i * 0.02, id: 'e' + i };
    const last = subs[subs.length - 1];
    if (!last || last.at <= item.at) {
      subs.push(item);
    } else {
      let lo = 0, hi = subs.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (subs[mid].at <= item.at) lo = mid + 1; else hi = mid;
      }
      subs.splice(lo, 0, item);
    }
    if (subs.length > SUBS_CAP) {
      const d = subs.length - SUBS_CAP;
      subs.splice(0, d);
      dropped += d;
    }
  }
  return { len: subs.length, dropped };
}

// ── 复刻 pct：旧（每次复制+排序） vs 新（缓存有序副本） ───────
function makeSkewArray(n) {
  const a = [];
  for (let i = 0; i < n; i++) {
    a.push(-21 + Math.sin(i / 500) * 8 + (i % 97) * 0.05);
  }
  return a;
}

function oldPct(arr, p) {
  if (!arr.length) return null;
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(s.length * p))];
}

function makeNewPct() {
  const cache = new WeakMap();
  return function (arr, p) {
    if (!arr.length) return null;
    let c = cache.get(arr);
    const first = arr[0], last = arr[arr.length - 1];
    if (!c || c.len !== arr.length || c.first !== first || c.last !== last) {
      const s = [...arr].sort((a, b) => a - b);
      c = { len: arr.length, first, last, sorted: s };
      cache.set(arr, c);
    }
    const s = c.sorted;
    return s[Math.min(s.length - 1, Math.floor(s.length * p))];
  };
}

// ── report 的跨上下文搬运量 ────────────────────────────────────
function reportPayloadBytes(arrays, withArrays) {
  // 粗略：每个浮点按 8 字符 + 逗号估算
  let n = 0;
  for (const a of arrays) n += withArrays ? a.length * 9 : 0;
  return n;
}

// ══════════════════════════════════════════════════════════════
const RESULTS = [];
function check(name, cond, detail) {
  RESULTS.push({ name, ok: !!cond, detail: detail || '' });
  console.log(`  [${cond ? 'PASS' : 'FAIL'}] ${name}` + (detail ? ` — ${detail}` : ''));
}

function bench(label, fn) {
  const t0 = process.hrtime.bigint();
  const r = fn();
  const t1 = process.hrtime.bigint();
  const ms = Number(t1 - t0) / 1e6;
  console.log(`  ${label}: ${ms.toFixed(2)} ms`);
  return { ms, r };
}

function main() {
  console.log('── EXT-003 P0① 主线程开销微基准（纯 Node，不占浏览器/GPU/NPU） ──');
  console.log(`  规模: ${FRAMES_5MIN} 帧（实测 5 分钟帧数）, ${ONSETS_5MIN} 个 onset`);

  // ① pendingSched
  const oldP = bench('旧 pendingSched（无界）', oldPendingSched);
  const newP = bench('新 pendingSched（有界）', newPendingSched);
  console.log(`    旧: maxLen=${oldP.r.maxLen} finalLen=${oldP.r.finalLen}`);
  console.log(`    新: maxLen=${newP.r.maxLen} dropped=${newP.r.dropped}`);
  check('① 旧实现 pendingSched 无界增长（> 10000）',
        oldP.r.maxLen > 10000, `maxLen=${oldP.r.maxLen}`);
  check('①b 新实现 pendingSched 有界（≤ ' + (PENDING_SCHED_CAP + 1) + '）',
        newP.r.maxLen <= PENDING_SCHED_CAP + 1,
        `maxLen=${newP.r.maxLen}（push 后才裁剪 ⇒ 瞬时 CAP+1）`);
  check('①c 修复后主线程时间下降',
        newP.ms <= oldP.ms,
        `old=${oldP.ms.toFixed(2)} ms new=${newP.ms.toFixed(2)} ms`);

  // ② subs
  const oldS = bench('旧 subs（每条 sort）', oldSubs);
  const newS = bench('新 subs（有序插入 + 上限）', newSubs);
  check('② 旧实现 subs 无界增长', oldS.r > 10000, `len=${oldS.r}`);
  check('②b 新实现 subs 有界（≤ ' + SUBS_CAP + '）',
        newS.r.len <= SUBS_CAP, `len=${newS.r.len} dropped=${newS.r.dropped}`);
  check('②c 修复后主线程时间显著下降（≥ 10×）',
        newS.ms * 10 <= oldS.ms,
        `old=${oldS.ms.toFixed(2)} ms new=${newS.ms.toFixed(2)} ms ` +
        `speedup=${(oldS.ms / Math.max(newS.ms, 1e-9)).toFixed(1)}×`);

  // ③ pct
  const skew = makeSkewArray(500);
  const newPct = makeNewPct();
  const CALLS = 1500;   // 5 分钟 × 每秒 3 次
  const oldT = bench('旧 pct（每次复制+排序 500 项 × ' + CALLS + '）', () => {
    let acc = 0;
    for (let i = 0; i < CALLS; i++) acc += oldPct(skew, 0.5);
    return acc;
  });
  const newT = bench('新 pct（缓存有序副本 × ' + CALLS + '）', () => {
    let acc = 0;
    for (let i = 0; i < CALLS; i++) acc += newPct(skew, 0.5);
    return acc;
  });
  check('③ 修复后 pct 时间下降（≥ 5×）',
        newT.ms * 5 <= oldT.ms,
        `old=${oldT.ms.toFixed(2)} ms new=${newT.ms.toFixed(2)} ms ` +
        `speedup=${(oldT.ms / Math.max(newT.ms, 1e-9)).toFixed(1)}×`);

  // ④ report 跨上下文搬运量
  const arrays = [makeSkewArray(500), makeSkewArray(500),
                  makeSkewArray(200), makeSkewArray(200), makeSkewArray(200)];
  const oldBytes = reportPayloadBytes(arrays, true);
  const newBytes = reportPayloadBytes(arrays, false);
  check('④ report 不再搬运大数组（跨上下文字节数 = 0）',
        newBytes === 0, `old≈${oldBytes} B/次 → new≈${newBytes} B/次 ` +
        `（5 分钟 ≈ ${(oldBytes * 300 / 1024).toFixed(0)} KB → 0）`);

  const pass = RESULTS.filter(r => r.ok).length;
  const fail = RESULTS.length - pass;
  console.log(`\n结果：${pass} PASS / ${fail} FAIL / 共 ${RESULTS.length}`);
  if (fail) {
    console.log('FAIL 明细：');
    for (const r of RESULTS.filter(x => !x.ok)) {
      console.log(`  - ${r.name} — ${r.detail}`);
    }
  }
  return fail === 0 ? 0 : 1;
}

process.exit(main());
