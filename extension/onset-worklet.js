/**
 * onset-worklet.js — AudioWorkletProcessor：精确检测音频起点（onset）
 *
 * 为什么需要它（EXT-003 P0③）：
 *   排程误差「实际出声时刻 − 计划时刻」要**精确到毫秒**。
 *   用 setInterval 轮询 AnalyserNode 只能到 ~40 ms 分辨率，测不出 20 ms 目标。
 *   ⇒ 用 AudioWorklet 逐样本检测：一旦某样本幅度超过阈值，就把
 *     **该样本在 AudioContext 时钟上的绝对时刻**回报给主线程。
 *
 * 时刻换算：worklet 的 currentTime 是**块开始**时刻，
 *   块内偏移 = currentTime + sampleIndex / sampleRate
 *
 * ★ 连发检测（EXT-003 P0② 复测修复）：
 *   旧实现 `armedCount` 默认只报**第一个** onset（每句一次），
 *   ⇒ 唇音同步测试片（每 2 s 一次白闪+嘀声）只能捕到 1 个 onset，
 *     配对必然错（实测 lipSyncMs=1962 ms，完全离谱）。
 *   ⇒ 改为**连续检测 + 迟滞**：
 *      · count = 0  ⇒ 连续模式（每次超阈值都报，带迟滞避免抖动）
 *      · count > 0  ⇒ 报够 count 次后停（保留旧的「每句一次」用法）
 *      · 迟滞：超过 threshold 才触发，回落到 threshold*0.4 以下才重新武装
 */

class OnsetProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opt = (options && options.processorOptions) || {};
    this.threshold = opt.threshold || 0.02;
    this.release = (opt.threshold || 0.02) * 0.4;
    this.count = opt.count || 0;          // 0 = 连续模式
    this.reported = 0;
    this.firing = false;                  // 迟滞状态
    this.minGapSamples = Math.round(
      (opt.minGapSec || 0.05) * sampleRate);   // 两次 onset 最小间隔
    this.lastOnsetSample = -1e9;
    this.sinceOnset = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const ch = input[0];
    if (!ch) return true;

    this.sinceOnset += ch.length;

    for (let i = 0; i < ch.length; i++) {
      const v = Math.abs(ch[i]);
      const at = currentTime + i / sampleRate;

      if (!this.firing) {
        if (v >= this.threshold) {
          // 最小间隔保护：避免同一个音被切成多个 onset
          if (this.sinceOnset < this.minGapSamples) continue;
          this.firing = true;
          this.sinceOnset = 0;
          if (this.count === 0 || this.reported < this.count) {
            this.reported++;
            this.port.postMessage({ onset: true, at, value: v });
          }
        }
      } else {
        // 迟滞：回落到 release 阈值以下才重新武装
        if (v < this.release) {
          this.firing = false;
        }
      }
    }
    return true;
  }
}

registerProcessor('onset-processor', OnsetProcessor);
