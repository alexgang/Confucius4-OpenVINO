/**
 * slowdown.js — ★ EXT-041：**媒体轻微降速**（内容脚本）
 *
 * ## 作用
 *   把目标标签页里正在播放的 `<video>`（以及 `<audio>`）的 `playbackRate`
 *   设成 **< 1.0**（默认 0.92）⇒ **画面/原声变慢** ⇒ 源音频到达插件的
 *   墙钟速率下降 ⇒ 配音不再无限堆积（见 `ext/media_slowdown.py` 的数学依据）。
 *
 * ## 为什么用内容脚本
 *   `playbackRate` 只能设在**页面里的媒体元素**上（扩展页/offscreen 拿不到
 *   宿主页面的 `<video>`）⇒ 必须注入到目标标签页。
 *   manifest 已有 `"scripting"` 权限 + `activeTab`（用户点扩展图标即授予）。
 *
 * ## ★★★ EXT-043 C2 修正（两个真缺陷）
 *   ① **二次注入会抛错**：旧实现用**顶层** `const RATE_FLOOR` /
 *      `const RATE_CEIL` ⇒ 同一个页面第二次 `executeScript` 注入时
 *      Chrome 报 "Identifier 'RATE_FLOOR' has already been declared"
 *      ⇒ **第二次开始时降速注入失败**。
 *      ⇒ 现在**整体包在 IIFE 里**，且用一个**幂等守卫**：
 *        已注入过就**只更新倍率**（不再重复声明任何标识符）。
 *   ② **只管顶层 frame**：iframe 里的视频（嵌入式播放器）不会降速
 *      ⇒ 现在**递归遍历同源 iframe**（跨源 iframe 受同源策略限制，
 *        拿不到就**如实跳过**，不假装覆盖了）。
 *
 * ## ★ 诚实说明（不宣称做不到的事）
 *   * 页面若**没有** `<video>`/`<audio>`（纯音频网页、AUDIO 元素）⇒ 降速**无效**
 *     ⇒ 必须**如实回报** `applied=false`，不能假装成功；
 *   * 只改 `playbackRate`，**不改译文、不改引擎、不改 ASR/MT**。
 *   * 只降速、**永不加速**（>1.0 会改变语义时轴，属另一件事）。
 *
 * ## 与主会话的消息协议
 *   * SW → 内容脚本：`{ cmd: 'set-rate', rate: 0.92 }` ⇒ 设置并回报。
 *   * 内容脚本 → SW：`{ cmd: 'slowdown-result', ok, applied, rate, reason, videos }`
 *   * SW → 内容脚本：`{ cmd: 'reset-rate' }` ⇒ 恢复 1.0。
 */
'use strict';

// ★★★ IIFE + 幂等守卫（EXT-043 C2 ①）
//   * IIFE：所有 `const` 变成**函数作用域** ⇒ 二次注入**不会**撞名；
//   * 守卫：`window.__extSlowdownInstalled` 已为真 ⇒ 只做「更新倍率」
//     ⇒ 二次注入**幂等**（不会重复注册 listener）。
(function () {
  const RATE_FLOOR = 0.90;
  const RATE_CEIL = 1.00;

  const G = (typeof window !== 'undefined') ? window : globalThis;

  // ★★★ 当前已应用的倍率（**必须声明**）
  //   旧实现忘了 `let appliedRate` ⇒ 文件顶层是 'use strict' ⇒ 赋值未声明
  //   变量直接抛 ReferenceError ⇒ 真实浏览器里 set-rate **完全失效**。
  //   （由 tests/ext041_slowdown_probe.js 的执行级探针抓出）
  let appliedRate = null;

  // ★★★ 幂等守卫（EXT-043 C2 ①）：**已注入过** ⇒ 只更新倍率就 return。
  //   * 不再声明任何 `const`（IIFE 已保证作用域隔离，这里连函数都不重复建）；
  //   * 不再注册第二个 `onMessage` listener。
  //   ⇒ 第二次 `executeScript` 注入**不会**抛 "Identifier has already been declared"。
  if (G.__extSlowdownInstalled && typeof G.__extSlowdownApply === 'function') {
    try {
      // ⚠️ 二次注入拿不到 `msg`（executeScript 不带参数）⇒
      //   这里只**重新应用当前倍率**（幂等地确保还是目标倍率）。
      const cur = G.__extSlowdownCurrentRate;
      if (typeof cur === 'number' && isFinite(cur) && cur > 0) {
        G.__extSlowdownApply(cur);
      }
    } catch (e) { /* ignore */ }
    return;
  }

  /** 找到页面里**正在播放**的媒体元素（含同源 iframe 里的）。 */
  function findMedia(root) {
    const out = [];
    const scope = root || document;
    let vids = [];
    let auds = [];
    try {
      vids = Array.from(scope.querySelectorAll('video'));
      auds = Array.from(scope.querySelectorAll('audio'));
    } catch (e) {
      return out;
    }
    for (const el of vids.concat(auds)) out.push(el);
    // ★ EXT-043 C2 ②：递归**同源** iframe（跨源拿不到 ⇒ 跳过，不假装覆盖）
    let frames = [];
    try { frames = Array.from(scope.querySelectorAll('iframe')); } catch (e) { }
    for (const f of frames) {
      try {
        const doc = f.contentDocument;
        if (!doc) continue;               // 跨源 ⇒ 拿不到 ⇒ 如实跳过
        const inner = findMedia(doc);
        for (const el of inner) out.push(el);
      } catch (e) { /* 跨源/沙箱 ⇒ 跳过 */ }
    }
    return out;
  }

  /** 把倍率应用到所有媒体元素。 */
  function applyRate(rate) {
    let r = Number(rate);
    if (!isFinite(r) || r <= 0) {
      return { ok: false, applied: false, rate: null,
               reason: '倍率非法：' + String(rate) };
    }
    // 钳位到 [下限, 上限] ⇒ **永不加速**
    r = Math.max(RATE_FLOOR, Math.min(RATE_CEIL, r));
    const media = findMedia(document);
    if (!media.length) {
      appliedRate = null;
      G.__extSlowdownCurrentRate = null;
      return { ok: true, applied: false, rate: r, videos: 0,
               reason: '页面里没有 <video>/<audio> ⇒ 降速**未生效**' };
    }
    let n = 0;
    const errs = [];
    for (const el of media) {
      try {
        el.playbackRate = r;
        n++;
      } catch (e) {
        errs.push(String((e && e.message) || e));
      }
    }
    appliedRate = r;
    G.__extSlowdownCurrentRate = r;
    return {
      ok: errs.length === 0,
      applied: n > 0,
      rate: r,
      videos: n,
      reason: (n > 0)
        ? ('已把 ' + n + ' 个媒体元素的 playbackRate 设为 ' + r.toFixed(3))
        : ('全部 ' + media.length + ' 个媒体元素设置失败：' + errs.join('; ')),
    };
  }

  /** 恢复 1.0。 */
  function resetRate() {
    const media = findMedia(document);
    let n = 0;
    for (const el of media) {
      try { el.playbackRate = 1.0; n++; } catch (e) { /* ignore */ }
    }
    appliedRate = null;
    G.__extSlowdownCurrentRate = 1.0;
    return { ok: true, applied: n > 0, rate: 1.0, videos: n,
             reason: '已恢复 playbackRate = 1.0（' + n + ' 个元素）' };
  }

  // ★ 幂等守卫标记 + 暴露给「二次注入」路径用
  G.__extSlowdownInstalled = true;
  G.__extSlowdownApply = applyRate;

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || typeof msg !== 'object') return;
    if (msg.cmd === 'set-rate') {
      sendResponse(applyRate(msg.rate));
      return true;
    }
    if (msg.cmd === 'reset-rate') {
      sendResponse(resetRate());
      return true;
    }
    if (msg.cmd === 'get-rate') {
      sendResponse({ ok: true, applied: appliedRate != null,
                     rate: appliedRate, videos: findMedia(document).length,
                     reason: appliedRate != null
                       ? ('当前 playbackRate = ' + appliedRate.toFixed(3))
                       : '尚未设置降速' });
      return true;
    }
  });
})();
