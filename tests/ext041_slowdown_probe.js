/**
 * ext041_slowdown_probe.js — ★ EXT-043 C1/C2 的**执行级**探针
 *
 * ## 为什么用 node 真实执行（而不是文本匹配）
 *   * **C1**：`pairStatusUrl()` 拼出来的 `/status` 地址**必须能被 `new URL()` 解析**。
 *     旧实现拼出 `http://:8766/status` ⇒ `new URL` 直接抛 Invalid URL。
 *     ⇒ 只有**真跑一遍**才能证明修好了（文本匹配会被注释里的示例骗过）。
 *   * **C2**：`slowdown.js` **二次注入**必须幂等（不撞名、不重复注册 listener）。
 *     ⇒ 用 `vm` 把文件**跑两遍**，看 listener 到底注册了几次、有没有抛错。
 *
 * ## 输出
 *   stdout：一行 JSON（`{c1: {...}, c2: {...}}`）
 *   exit 0 = 探针本身跑完（**不代表断言通过**⇒ 断言在 Python 侧做）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const PLAYER = path.join(ROOT, 'extension', 'player.js');
const SLOWDOWN = path.join(ROOT, 'extension', 'slowdown.js');

const out = { c1: {}, c2: {}, errors: [] };

// ────────────────────────────────────────────────────────────────
// C1：抽出 player.js 的 pairStatusUrl() 并**真实执行**
// ────────────────────────────────────────────────────────────────
function extractFunction(src, name) {
  const marker = 'function ' + name + '(';
  const start = src.indexOf(marker);
  if (start < 0) return null;
  // 从第一个 '{' 开始按大括号配平
  let i = src.indexOf('{', start);
  if (i < 0) return null;
  const open = i;
  let depth = 0;
  for (; i < src.length; i++) {
    const ch = src[i];
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  return null;
}

try {
  const src = fs.readFileSync(PLAYER, 'utf8');
  const fn = extractFunction(src, 'pairStatusUrl');
  if (!fn) {
    out.c1.found = false;
    out.errors.push('player.js 里找不到 pairStatusUrl()');
  } else {
    out.c1.found = true;
    // eslint-disable-next-line no-new-func
    const factory = new Function(fn + '; return pairStatusUrl;');
    const pairStatusUrl = factory();
    const cases = [
      'ws://127.0.0.1:8765/',
      'ws://127.0.0.1:8765',
      'ws://localhost:9000/',
      'ws://127.0.0.1:8765/',
      'wss://example.com:443/x',
    ];
    out.c1.cases = cases.map((w) => {
      const u = pairStatusUrl(w);
      let valid = true;
      let parsed = null;
      try {
        parsed = new URL(u);
      } catch (e) {
        valid = false;
      }
      return {
        wsUrl: w,
        result: u,
        valid: valid,
        hostname: parsed ? parsed.hostname : null,
        port: parsed ? parsed.port : null,
        pathname: parsed ? parsed.pathname : null,
      };
    });
    // ★ 旧实现会拼出 `http://:8766/status` ⇒ 必须**不含**空主机名
    out.c1.all_valid = out.c1.cases.every((c) => c.valid);
    out.c1.no_empty_host = out.c1.cases.every((c) => c.hostname);
    // ★ 配对端口必须 = 桥接端口 + 1
    out.c1.port_is_bridge_plus_1 = out.c1.cases.every((c) => {
      const m = String(c.wsUrl).match(/:(\d+)/);
      if (!m) return c.port === '8766';
      return Number(c.port) === Number(m[1]) + 1;
    });
  }
} catch (e) {
  out.c1.error = String((e && e.message) || e);
}

// ────────────────────────────────────────────────────────────────
// C2：把 slowdown.js 在 vm 里**跑两遍** ⇒ 验证二次注入幂等
// ────────────────────────────────────────────────────────────────
try {
  const src = fs.readFileSync(SLOWDOWN, 'utf8');
  let listenerCount = 0;
  const mediaEls = [];
  const sandbox = {
    console,
    document: {
      querySelectorAll(sel) {
        if (sel === 'video' || sel === 'audio') return mediaEls;
        if (sel === 'iframe') return [];
        return [];
      },
    },
    chrome: {
      runtime: {
        onMessage: {
          addListener(fn) {
            listenerCount++;
            sandbox.__listener = fn;
          },
        },
      },
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);

  let firstErr = null;
  let secondErr = null;
  try {
    vm.runInContext(src, sandbox, { filename: 'slowdown.js#1' });
  } catch (e) {
    firstErr = String((e && e.message) || e);
  }
  const afterFirst = listenerCount;
  try {
    vm.runInContext(src, sandbox, { filename: 'slowdown.js#2' });
  } catch (e) {
    secondErr = String((e && e.message) || e);
  }
  const afterSecond = listenerCount;

  out.c2.first_error = firstErr;
  out.c2.second_error = secondErr;
  out.c2.listener_count_after_first = afterFirst;
  out.c2.listener_count_after_second = afterSecond;
  // ★ 幂等：第二次注入**不抛错**且**不重复注册** listener
  out.c2.idempotent = (afterFirst === 1 && afterSecond === 1
                       && firstErr === null && secondErr === null);

  // ★★ 严格模式下「未声明变量赋值」必须被抓到
  //   旧实现忘了 `let appliedRate` ⇒ 顶层 'use strict' ⇒ ReferenceError
  //   ⇒ 这里用一个**探针函数**在 strict 模式下给未声明变量赋值，
  //     若抛 ReferenceError ⇒ 说明严格模式生效（这是合法的对照实验）。
  out.c2.strict_mode_active = false;
  try {
    // eslint-disable-next-line no-new-func
    new Function('"use strict"; undeclared_probe_var_xyz = 1;')();
    out.c2.strict_mode_active = false;
  } catch (e) {
    out.c2.strict_mode_active = /ReferenceError|not defined/i.test(String(e));
  }

  // ★ 顺带验证「设置倍率」真能用（媒体元素被设成目标倍率）
  //   ⚠️ 每一次调用都**单独 try/catch** ⇒ 哪怕抛错也能继续测后面的，
  //     且把异常**如实记进输出**（不能因为一次抛错就中断整段 ⇒ 丢失证据）。
  const el = { playbackRate: 1.0 };
  mediaEls.push(el);

  /** 调用内容脚本的 onMessage listener，捕获异常 + 捕获 sendResponse 实参。 */
  function callListener(msg) {
    let response = null;
    try {
      const ret = sandbox.__listener(msg, {}, (v) => { response = v; });
      return { ok: true, value: response, returned: ret };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  }

  const r1 = callListener({ cmd: 'set-rate', rate: 0.92 });
  out.c2.set_rate_result = r1.ok ? r1.value : null;
  out.c2.set_rate_error = r1.ok ? null : r1.error;
  out.c2.media_playback_rate = el.playbackRate;
  out.c2.rate_applied_ok = (r1.ok && Math.abs(el.playbackRate - 0.92) < 1e-9);
  // ★ 旧实现用 Python 风格 `'...%d...' % (n, r)` ⇒ JS 里结果是**数字 NaN**
  //   ⚠️ ★ 关键：JSON.stringify(NaN) === 'null' ⇒ **不能**只看输出里的字符串，
  //     否则 NaN 会被序列化掉、检查永远通过（假通过）。
  //     ⇒ 必须在 **JS 内部**把 reason 转成字符串再判定。
  const reasonRaw = r1.ok ? r1.value.reason : null;
  out.c2.reason_type = (reasonRaw === null) ? 'null'
                       : (typeof reasonRaw);
  const reasonStr = (reasonRaw === null || reasonRaw === undefined)
                    ? '' : String(reasonRaw);
  out.c2.reason_text = reasonStr;
  out.c2.reason_is_number_nan = (typeof reasonRaw === 'number'
                                 && Number.isNaN(reasonRaw));
  out.c2.reason_has_nan = (reasonStr.indexOf('NaN') >= 0)
                          || out.c2.reason_is_number_nan;
  out.c2.reason_has_placeholder = /%[dsf]/.test(reasonStr);
  // ★ reason 必须是**字符串**（不是数字）⇒ 数字说明格式化写错了
  out.c2.reason_is_string = (typeof reasonRaw === 'string');

  // ★ 永不加速：rate=1.5 应被钳到 1.00
  const r2 = callListener({ cmd: 'set-rate', rate: 1.5 });
  out.c2.clamp_high_result = r2.ok ? r2.value : null;
  out.c2.clamp_high_error = r2.ok ? null : r2.error;
  out.c2.clamp_high_ok = (r2.ok && Math.abs(el.playbackRate - 1.0) < 1e-9);

  // ★ 下限：rate=0.5 应被钳到 0.90
  const r3 = callListener({ cmd: 'set-rate', rate: 0.5 });
  out.c2.clamp_low_error = r3.ok ? null : r3.error;
  out.c2.clamp_low_ok = (r3.ok && Math.abs(el.playbackRate - 0.9) < 1e-9);

  // ★ 恢复 1.0
  const r4 = callListener({ cmd: 'reset-rate' });
  out.c2.reset_error = r4.ok ? null : r4.error;
  out.c2.reset_ok = (r4.ok && Math.abs(el.playbackRate - 1.0) < 1e-9);

  // ★ 非法输入必须**如实报错**而不是抛异常
  const r5 = callListener({ cmd: 'set-rate', rate: 'abc' });
  out.c2.invalid_input_error = r5.ok ? null : r5.error;
  out.c2.invalid_input_ok = r5.ok && r5.value && r5.value.ok === false;

  // ★ 汇总：任何一个环节抛错 ⇒ 整体不通过
  out.c2.all_calls_ok = (r1.ok && r2.ok && r3.ok && r4.ok && r5.ok);
} catch (e) {
  out.c2.error = String((e && e.message) || e);
}

process.stdout.write(JSON.stringify(out));
