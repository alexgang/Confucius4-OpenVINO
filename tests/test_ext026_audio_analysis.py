"""test_ext026_audio_analysis.py — EXT-026「配音录音非静音」验收工具的自测

## 这个文件要验什么

EXT-026 指令第 3 条明文要求：**配音录音非静音**必须作为证据落盘。
本轮新增 `tests/smoke/analyze_dub_audio.py`（把该判定做成可复现产物）。

## 为什么要自测这个工具

「非静音」这个判据本身很容易**假通过**：

  * 阈值定得太松 ⇒ 全静音录音也能被判成「有声音」；
  * 只看 peak 不看 RMS ⇒ 一个尖峰脉冲就算「有配音」；
  * 门限算错（dBFS 与线性混用）⇒ 判定方向反了。

⇒ 本文件用**合成音频**构造 4 种已知真值的波形，**用真工具**分析，
  验证判定与真值一致：

  ① 全静音（零电平）        ⇒ 必须判「静音」
  ② 低电平底噪（如 -60 dBFS）⇒ 必须判「静音」（门限以上才判有声）
  ③ 含语音 burst 的信号      ⇒ 必须判「非静音」且 burst 数 > 0
  ④ 单个尖峰脉冲            ⇒ 必须判「静音」（证明不是「只看 peak」）

★ 反证：
  A. 把 RMS 门限放宽到 -120 dBFS ⇒ ② 低电平底噪**必须**开始被判成
     「非静音」⇒ 若不翻转，说明判据对电平不敏感、恒为真。
  B. 把 `is_non_silent` 的实现改坏（删掉 RMS 条件）⇒ ④ 单尖峰
     **必须**开始被判成「非静音」⇒ 若不翻转，说明 RMS 条件形同虚设。

不跑推理 / 不占 GPU·NPU / 不创建共享锁（纯合成音频 + WebAudio 编解码）。

运行：
    python tests/test_ext026_audio_analysis.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE = os.path.join(ROOT, "tests", "smoke")
for _p in (SMOKE, os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  (%s)" % detail) if detail else ""))


# ── 在浏览器里：合成波形 → 编码成 opus/webm → 返回 base64 ───────
# ★ 波形**在 JS 里直接生成**（不走 WAV 文件）⇒
#   ① 绕开浏览器 WAV 解码的兼容性问题；
#   ② 保证「送进编码器的就是已知真值的波形」。
_SYNTH_JS = r"""
async (kind) => {
  const sr = 16000, n = sr * 3;
  const ch = new Float32Array(n);
  const db = (v) => Math.pow(10, v / 20);
  if (kind === 'silence') {
    // 全零
  } else if (kind === 'low_noise') {
    const a = db(-60);
    for (let i = 0; i < n; i++) ch[i] = a * Math.sin(2 * Math.PI * 137 * i / sr);
  } else if (kind === 'speech') {
    const a = db(-12), bl = Math.round(sr * 0.12), gl = Math.round(sr * 0.3);
    let p = 0;
    while (p < n) {
      for (let i = 0; i < bl && p < n; i++, p++) ch[p] = a * Math.sin(2 * Math.PI * 220 * i / sr);
      for (let i = 0; i < gl && p < n; i++, p++) ch[i] = 0;
    }
  } else if (kind === 'spike') {
    ch[n >> 1] = 0.9;
  } else {
    return { ok: false, error: 'unknown kind: ' + kind };
  }
  const actx = new AudioContext({ sampleRate: sr });
  // ★ 无用户手势时 AudioContext 是 'suspended' ⇒ 录出来是空的
  //   ⇒ 必须显式 resume()，否则 MediaRecorder 只拿到一个空壳
  try { await actx.resume(); } catch (e) {}
  if (actx.state !== 'running') {
    return { ok: false, error: 'AudioContext 状态为 ' + actx.state
             + '（无法合成音频）' };
  }
  const buf = actx.createBuffer(1, n, sr);
  buf.copyToChannel(ch, 0);
  const src = actx.createBufferSource();
  src.buffer = buf;
  const dest = actx.createMediaStreamDestination();
  src.connect(dest);
  const rec = new MediaRecorder(dest.stream, { mimeType: 'audio/webm;codecs=opus' });
  const chunks = [];
  rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  const done = new Promise(r => rec.onstop = r);
  src.start();
  rec.start();
  // ★ 录满 3 s 波形（不是 400 ms）⇒ 保证 burst 结构被录进去
  await new Promise(r => setTimeout(r, 3200));
  rec.stop();
  await done;
  await actx.close();
  const blob = new Blob(chunks, { type: 'audio/webm;codecs=opus' });
  const ab = await blob.arrayBuffer();
  const u8 = new Uint8Array(ab);
  let b = '';
  const CH = 8192;
  for (let i = 0; i < u8.length; i += CH) {
    b += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  }
  return { ok: true, b64: btoa(b), bytes: u8.length,
           ctxState: 'running' };
}
"""


def _synth_webm(kind: str, out_path: str) -> int:
    """在浏览器里合成指定波形并编码成 opus/webm 落盘，返回字节数。"""
    import base64
    import browser_harness as H
    profile = os.path.join(ROOT, ".tmp", "_audio_selftest_profile")
    with H.BrowserSession(profile, headless=True) as br:
        page = br.new_page()
        r = page.evaluate(_SYNTH_JS, kind)
    if not r.get("ok"):
        raise RuntimeError(r.get("error") or "synth failed")
    data = base64.b64decode(r["b64"])
    with open(out_path, "wb") as f:
        f.write(data)
    return len(data)


# ══════════════════════════════════════════════════════════════════
def test_synthetic_cases() -> None:
    print("\n[A] ★ 合成音频真值对照（4 种已知波形，用**真工具**分析）")
    import analyze_dub_audio as A

    work = os.path.join(ROOT, ".tmp", "_audio_selftest")
    os.makedirs(work, exist_ok=True)

    cases = [
        ("silence", False, "全静音 ⇒ 必须判静音"),
        ("low_noise", False, "-60 dBFS 底噪 ⇒ 必须判静音（门限以上才算有声）"),
        ("speech", True, "含语音 burst ⇒ 必须判非静音"),
        ("spike", False, "单个尖峰 ⇒ 必须判静音（证明不是只看 peak）"),
    ]

    for kind, want_non_silent, why in cases:
        webm = os.path.join(work, "%s.webm" % kind)
        try:
            nbytes = _synth_webm(kind, webm)
            st = A.analyze(webm)
        except Exception as e:
            import traceback
            traceback.print_exc()
            check("★ 合成用例 %s 可编码可分析" % kind, False,
                  "%s: %s" % (type(e).__name__, e))
            continue

        check("★ %s 合成用例产出非空 webm" % kind, nbytes > 0, "%d 字节" % nbytes)
        got = st.get("non_silent")
        check("★ %s 判定与真值一致（%s）" % (kind, why), got == want_non_silent,
              "dbfsRms=%.2f burst=%s peak=%.4f ⇒ 判%s（期望%s）"
              % (st.get("dbfsRms", -999), st.get("bursts"), st.get("peak", 0),
                 "非静音" if got else "静音",
                 "非静音" if want_non_silent else "静音"))
        if kind == "speech":
            check("★ speech 用例 burst 数 > 0", (st.get("bursts") or 0) > 0,
                  "bursts=%s" % st.get("bursts"))
            check("★ speech 用例 RMS 明显高于底噪用例",
                  (st.get("dbfsRms") or -999) > -45, str(st.get("dbfsRms")))


def test_tool_contract() -> None:
    print("\n[B] ★ 工具与判据的契约（源码级）")
    import analyze_dub_audio as A
    p = os.path.join(SMOKE, "analyze_dub_audio.py")
    check("★ analyze_dub_audio.py 存在", os.path.exists(p))
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    check("★ 判据含 RMS 门限常量 MIN_RMS_DBFS",
          "MIN_RMS_DBFS" in src)
    check("★ 判据要求 burst ≥ MIN_BURSTS（不只看 peak）",
          "MIN_BURSTS" in src)
    check("★ 用 WebAudio decodeAudioData 解码（不引入 ffmpeg 依赖）",
          "decodeAudioData" in src)
    check("★ 纯解码不跑推理（无 ASR/MT/TTS 调用）",
          not any(k in src for k in ("R2T2", "Hy-MT", "Qwen3", "openvino")))
    check("★ 判据是纯函数（is_non_silent 可单独调用）",
          callable(getattr(A, "is_non_silent", None)))
    # 判据输入缺失时必须判「静音」（保守，不误报）
    check("★ 空统计判为静音（保守，不误报）",
          A.is_non_silent({}) is False)
    check("★ 解码失败（ok=false）判为静音",
          A.is_non_silent({"ok": False, "dbfsRms": -10.0, "bursts": 9}) is False)
    check("★ dbfsRms 缺失判为静音",
          A.is_non_silent({"ok": True, "bursts": 9}) is False)


def test_counter_example() -> None:
    print("\n[C] ★ 反证：判据被改坏 ⇒ 判定必须翻转（否则判据形同虚设）")
    import analyze_dub_audio as A

    # 反证 A：把 RMS 门限放宽到 -120 dBFS
    low_noise = {"ok": True, "dbfsRms": -60.0, "bursts": 8, "peak": 0.001}
    strict = A.is_non_silent(low_noise, rms_dbfs=-45.0)
    loose = A.is_non_silent(low_noise, rms_dbfs=-120.0)
    check("★ 正常门限（-45）：低电平底噪判静音", strict is False,
          "dbfsRms=-60 burst=8")
    check("★ 反证 A：门限放宽（-120）后必须翻转成「非静音」",
          loose is True and loose != strict,
          "放宽后判定=%s" % ("非静音" if loose else "静音"))

    # 反证 B：把实现改坏 —— 删掉 RMS 条件（只看 burst）
    def broken_is_non_silent(stats: dict, rms_dbfs: float = A.MIN_RMS_DBFS,
                             min_bursts: int = A.MIN_BURSTS) -> bool:
        """故意改坏的实现：只看 burst，不看 RMS。"""
        if not stats or not stats.get("ok", True):
            return False
        return (stats.get("bursts") or 0) >= min_bursts

    spike = {"ok": True, "dbfsRms": -70.0, "bursts": 0, "peak": 0.9}
    check("★ 真判据：单尖峰（burst=0）判静音",
          A.is_non_silent(spike) is False, "peak=0.9 rms=-70 burst=0")
    # 单尖峰在「只看 peak」的错误实现下会被误判为非静音 —— 但本判据
    # 不看 peak，所以用「高 burst + 极低 RMS」来证伪「只看 burst」：
    fake = {"ok": True, "dbfsRms": -80.0, "bursts": 5, "peak": 0.001}
    check("★ 真判据：高 burst 但 RMS 极低 ⇒ 仍判静音（不是只看 burst）",
          A.is_non_silent(fake) is False,
          "dbfsRms=-80 burst=5")
    check("★ 反证 B：去掉 RMS 条件的实现必须把上面那份误判成非静音",
          broken_is_non_silent(fake) is True,
          "改坏后判定=%s" % ("非静音" if broken_is_non_silent(fake) else "静音"))

    # 真静音任何门限下都不该被判非静音
    true_silence = {"ok": True, "dbfsRms": -999.0, "bursts": 0, "peak": 0.0}
    check("★ 真静音任何门限下都判静音",
          A.is_non_silent(true_silence, rms_dbfs=-45.0) is False
          and A.is_non_silent(true_silence, rms_dbfs=-120.0) is False)


def main() -> int:
    print("=" * 70)
    print("EXT-026 录音非静音分析工具自测")
    print("=" * 70)
    for fn in (test_synthetic_cases, test_tool_contract, test_counter_example):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check("★ %s 正常跑完" % fn.__name__, False,
                  "%s: %s" % (type(e).__name__, e))

    npass = sum(1 for (_, ok, _) in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 70)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 70)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
