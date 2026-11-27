"""test_ext0424_runaway_audio_length.py — ★ APP-154 §1 自测

**背景（APP-153 §1b 的实测根因）**

clone 臂 `bgkeep_on_clone_1/bridge.err` 唯一一行：
`🔴 TTS 失控中止：wall_clock>15.3s (limit 14.5s)（已丢弃该句）`
⇒ 该句 `has_tts=false` ⇒ 空配音 ⇒ **丢句**。

算账（`estimate_sec` 口径：17 字 × 0.25 s/字 + 0.6 s 尾 = **4.85 s**）：
`runaway_threshold_s(4.85) = max(3×4.85, 4.85+8) = **14.55 s**`
⇒ 旧墙钟闸 **15.26 s > 14.55 s** ⇒ 中止并**丢弃该句**。

但 **App 侧同款判据（音频长度）从未触发**（`bridge.log` 里
`APP-130 运行时保险` 出现 **0** 次）⇒ 这一句**音频长度正常**，
只是**机器忙（NPU 争用：克隆 + 背景分离）⇒ 合成慢**。
⇒ 旧墙钟闸把一句「**慢但正常**」的句子误杀 ⇒ 空配音 ⇒ 丢句。

**修法（APP-154 §1）**

1. 失控判据**只看音频长度**（`runaway_threshold_s(estimate_sec(text))`，
   APP-030② 原本的设计）；**不再用墙钟判失控**；
2. 墙钟**只**保留一个很宽的兜底（≥ 60 s，或估算时长的 6 倍，取大者），
   触发时**只记日志**，**不丢句**；
3. 真被判失控（**或调用抛异常**）⇒ **用预设音色 A 重合成一次**；
4. 重合成仍失败 ⇒ **按 1.7× 语速上限截短**后照样下发
   ⇒ **绝不下发空音频、不丢句**（用户规则：跳句阈值 0）；
5. 计数可见（`stats()`）：`tts_runaway` / `tts_resynth` / `tts_wall_fallback`。

**本文件覆盖三种情况（APP-154 §1 明文要求）**

  1. **慢但正常**（墙钟超限、音频长度正常）⇒ **不中止**（回归的根因）；
  2. **音频长度超限** ⇒ **中止** + **用预设音色 A 重合成**；
  3. **重合成也失败** ⇒ **有兜底音频**（不空、不丢句）。

**判据纪律**

* **行为级**：真调 `RuntimeEngine.tts()`，用**假 TTS 流**喂它；
* **有区分力**：
  - 用例 2 断言「重合成那次的 `speaker_embed` 是**预设音色 A**」，
    且**与第一次的克隆 embed 不同** ⇒ 能区分「真换了音色」与「白做」；
  - **反证组**：把生产代码的判据换回「墙钟」⇒ 用例 1 的行为必须改变
    ⇒ 否则本测试恒真；
* **不加载任何模型权重**（不占 GPU/NPU、不需要共享锁）。

运行：
    python tests/test_ext0424_runaway_audio_length.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))


# ──────────────────────────────────────────────────────────────────────
# 假 TTS 流
# ──────────────────────────────────────────────────────────────────────
class FakeTTSStream:
    """假 `tts_engine.stream`。

    ★ 关键参数：
      * `chunk_sec`   —— 每块音频的秒数；
      * `sleep_per`   —— 每块的墙钟耗时（秒）⇒ 造「慢但正常」；
      * `max_chunks`  —— 最多产出多少块。

    产出 `(wave_float32, sample_rate)` —— 与真 `tts_engine.stream` 同形状。
    """

    def __init__(self, chunk_sec=1.0, sleep_per=0.0, max_chunks=1000, sr=24000):
        self.chunk_sec = chunk_sec
        self.sleep_per = sleep_per
        self.max_chunks = max_chunks
        self.sr = sr
        self.calls = []          # 每次调用的参数（用于验「重合成用预设音色」）

    def __call__(self, eng, text, language=None, speaker_embed=None,
                 speaker=None, max_new_tokens=None, on_log=print, **kw):
        self.calls.append({'text': text, 'speaker_embed': speaker_embed,
                            'language': language})
        n = 0
        while n < self.max_chunks:
            if self.sleep_per:
                time.sleep(self.sleep_per)
            import numpy as np
            wave = np.zeros(int(self.chunk_sec * self.sr), dtype=np.float32)
            yield wave, self.sr
            n += 1


def install_fake_tts_engine(stream_obj, threshold_s=None):
    """装一个**假 `tts_engine` 模块**（只提供 `tts()` 用到的符号）。

    `threshold_s`：把 `runaway_threshold_s` 固定成这个值（便于造出
    「音频长度 < 阈值 但 墙钟 > 阈值」的慢但正常场景）。
    """
    m = types.ModuleType("tts_engine")

    def clamp_max_new_tokens(text, lang):
        return 512

    def estimate_sec(text, lang='en'):
        n = len([c for c in (text or '') if not c.isspace()])
        s = 0.25 if str(lang).lower().startswith(('zh', 'chin')) else 0.07
        return n * s + 0.6

    def runaway_threshold_s(est_sec):
        if threshold_s is not None:
            return float(threshold_s)
        try:
            e = float(est_sec)
        except Exception:
            e = 0.0
        return max(3.0 * e, e + 8.0)

    def speaker_embedding(eng, ref_wav=None, on_log=print, **kw):
        # ★ 能区分「克隆 embed」与「预设 A embed」⇒ 重合成断言才有鉴别力。
        return "CLONE_EMBED" if ref_wav else "PRESET_EMBED"

    m.clamp_max_new_tokens = clamp_max_new_tokens
    m.estimate_sec = estimate_sec
    m.runaway_threshold_s = runaway_threshold_s
    m.stream = stream_obj
    m.make_engine = lambda *a, **k: types.SimpleNamespace()
    m.speaker_embedding = speaker_embedding
    sys.modules["tts_engine"] = m
    return m


def make_engine(ext_engine_runtime, preset_embed="PRESET_EMBED"):
    """构造一个**不加载权重**的 RuntimeEngine（只测 tts() 路径）。"""
    eng = ext_engine_runtime.RuntimeEngine(
        target_lang="zh", asr_device="GPU.0", mt_device="GPU.0",
        tts_device="NPU", on_log=lambda m: None)
    eng._tts_eng = types.SimpleNamespace()
    eng._tts_spk_embed = preset_embed
    return eng


def scenario_1_slow_but_normal(ext):
    """**慢但正常**：墙钟超限、音频长度正常 ⇒ **不中止**、不丢句。"""
    print("\n[1] 慢但正常（墙钟超限、音频长度正常）⇒ 不中止")
    # 阈值固定 2.0 s ⇒ 造 3 块 × 0.5 s = **1.5 s 音频**（< 2.0 s ⇒ 长度正常），
    # 但每块墙钟 1.0 s ⇒ 墙钟 3.0 s（> 2.0 s ⇒ **超阈值**）。
    st = FakeTTSStream(chunk_sec=0.5, sleep_per=1.0, max_chunks=3)
    install_fake_tts_engine(st, threshold_s=2.0)
    eng = make_engine(ext)
    # 把**墙钟兜底**压到 0.5 s（默认 = max(60 s, est×6) ⇒ 本例 9.6 s
    # ⇒ 3 s 的墙钟根本触发不到）⇒ 这样才能验证「墙钟超限 ⇒ 只记日志、不丢句」。
    orig_fb = ext.TTS_WALL_CLOCK_FALLBACK_SEC
    orig_ff = ext.TTS_WALL_CLOCK_FALLBACK_FACTOR
    ext.TTS_WALL_CLOCK_FALLBACK_SEC = 0.5
    ext.TTS_WALL_CLOCK_FALLBACK_FACTOR = 0.001
    try:
        pcm, sec = eng.tts("短句测试", voice="")
    finally:
        ext.TTS_WALL_CLOCK_FALLBACK_SEC = orig_fb
        ext.TTS_WALL_CLOCK_FALLBACK_FACTOR = orig_ff
    check("慢但正常 ⇒ 返回了音频（不丢句）", pcm is not None,
          "pcm=%s len=%s" % (type(pcm).__name__, len(pcm) if pcm else 0))
    check("慢但正常 ⇒ 未判失控（tts_runaway=0）", eng.tts_runaway == 0,
          "tts_runaway=%d" % eng.tts_runaway)
    check("慢但正常 ⇒ 未触发重合成（tts_resynth=0）", eng.tts_resynth == 0,
          "tts_resynth=%d" % eng.tts_resynth)
    check("慢但正常 ⇒ 墙钟兜底被记录（**只记日志**）",
          eng.tts_wall_fallback >= 1,
          "tts_wall_fallback=%d" % eng.tts_wall_fallback)
    check("慢但正常 ⇒ 音频长度 1.5 s（未被截短、未被重合成替代）",
          1.4 < sec < 1.6, "speech_sec=%.2f" % sec)
    check("慢但正常 ⇒ TTS 只被调用 1 次（没白重合成）", len(st.calls) == 1,
          "calls=%d" % len(st.calls))


def scenario_2_audio_over_limit(ext):
    """**音频长度超限** ⇒ 中止 + **用预设音色 A 重合成**。"""
    print("\n[2] 音频长度超限 ⇒ 中止并用预设音色 A 重合成")
    calls = {'n': 0}
    tmp_wav = os.path.join(ROOT, '_app154_clone_voice.wav')
    with open(tmp_wav, 'wb') as f:
        f.write(b'RIFFfake')

    class TwoPhaseStream(FakeTTSStream):
        def __call__(self, eng, text, language=None, speaker_embed=None,
                     speaker=None, max_new_tokens=None, on_log=print, **kw):
            calls['n'] += 1
            self.calls.append({'phase': calls['n'], 'speaker_embed': speaker_embed})
            import numpy as np
            if calls['n'] == 1:
                n = 0
                while n < 40:      # 40 s 音频（远超 2.0 s 阈值）
                    yield np.zeros(int(1.0 * self.sr), dtype=np.float32), self.sr
                    n += 1
            else:
                yield np.zeros(int(2.0 * self.sr), dtype=np.float32), self.sr

    st = TwoPhaseStream()
    install_fake_tts_engine(st, threshold_s=2.0)
    eng = make_engine(ext)
    pcm, sec = eng.tts("短句测试", voice=tmp_wav)
    try:
        os.remove(tmp_wav)
    except Exception:
        pass
    check("音频超限 ⇒ 最终返回了音频（不丢句）", pcm is not None,
          "len=%s" % (len(pcm) if pcm else 0))
    check("音频超限 ⇒ 记了失控（tts_runaway=1）", eng.tts_runaway == 1,
          "tts_runaway=%d" % eng.tts_runaway)
    check("音频超限 ⇒ 记了重合成（tts_resynth=1）", eng.tts_resynth == 1,
          "tts_resynth=%d" % eng.tts_resynth)
    check("音频超限 ⇒ TTS 被调用两次（1 次原声 + 1 次重合成）", calls['n'] == 2,
          "calls=%d" % calls['n'])
    if len(st.calls) >= 2:
        e1 = st.calls[0]['speaker_embed']
        e2 = st.calls[1]['speaker_embed']
        check("第 1 次用的是**克隆** embed", e1 == "CLONE_EMBED", "embed=%r" % (e1,))
        check("重合成用的是**预设音色 A**的 embed（**确实换了音色**）",
              e2 == "PRESET_EMBED", "embed=%r" % (e2,))
        check("重合成与第一次的 embed **不同**（可区分「真换」与「白做」）",
              e1 != e2, "e1=%r e2=%r" % (e1, e2))
    check("音频超限 ⇒ 重合成成功后是 2 s 音频", 1.5 < sec < 2.5,
          "speech_sec=%.2f" % sec)


def scenario_3_resynth_also_fails(ext):
    """**重合成也失败** ⇒ **有兜底音频**（不空、不丢句）。"""
    print("\n[3] 重合成也失败 ⇒ 有兜底音频（按 1.7× 语速上限截短）")
    state = {'n': 0}

    class BoomTwice(FakeTTSStream):
        def __call__(self, eng, text, language=None, speaker_embed=None,
                     speaker=None, max_new_tokens=None, on_log=print, **kw):
            state['n'] += 1
            import numpy as np
            if state['n'] <= 2:
                raise RuntimeError("fake TTS boom #%d" % state['n'])
            # 兜底那次：正常产 30 块 1 s ⇒ 会被 cap_sec 截短
            n = 0
            while n < 30:
                yield np.zeros(int(1.0 * self.sr), dtype=np.float32), self.sr
                n += 1

    st = BoomTwice()
    install_fake_tts_engine(st, threshold_s=2.0)
    eng = make_engine(ext)
    pcm, sec = eng.tts("短句测试", voice="")
    check("重合成也失败 ⇒ 仍有兜底音频（**不空**）", pcm is not None,
          "len=%s" % (len(pcm) if pcm else 0))
    check("重合成也失败 ⇒ 记了失控（tts_runaway=1）", eng.tts_runaway == 1,
          "tts_runaway=%d" % eng.tts_runaway)
    check("重合成也失败 ⇒ 记了重合成（tts_resynth=1）", eng.tts_resynth == 1,
          "tts_resynth=%d" % eng.tts_resynth)
    # cap = audio_limit/1.7 = 2.0/1.7 ≈ 1.18 s ⇒ 截短后 ≤ ~1.2 s
    check("兜底音频按 1.7× 语速上限截短（≤ 1.3 s）", 0 < sec <= 1.3,
          "speech_sec=%.2f（cap≈1.18 s）" % sec)


def scenario_4_counterexample(ext):
    """**反证组**：把判据换回「墙钟」⇒ 行为必须与正确版本**不同**。

    ★ 没有这一步，本测试可能是**恒真**的（判据无鉴别力）。
    """
    print("\n[4] 反证组：把判据换回墙钟 ⇒ 用例 1 的行为必须改变")
    src = open(ext.__file__, "rb").read().decode("utf-8")

    # 把「音频长度判据」整段换成「墙钟判据」= **旧实现**。
    old_impl = src.replace(
        "                total = sum(c.shape[0] for c in chunks) / float(sr)\n"
        "                if total > audio_limit:\n"
        "                    aborted = \"audio>%.1fs (limit %.1fs)\" % (total, audio_limit)\n"
        "                    break\n",
        "                elapsed = time.perf_counter() - t0\n"
        "                if elapsed > audio_limit:\n"
        "                    aborted = \"wall_clock>%.1fs\" % elapsed\n"
        "                    break\n"
        "                total = sum(c.shape[0] for c in chunks) / float(sr)\n")
    if old_impl == src:
        print("  [SKIP] 反证源码未命中（生产代码已变 ⇒ 需更新本反证）")
        check("反证组：源码锚点命中", False, "锚点未命中")
        return
    check("反证组：源码锚点命中（可构造「旧墙钟判据」版本）", True)

    mod = types.ModuleType("ext_broken")
    mod.__file__ = ext.__file__
    mod.__package__ = "ext"
    try:
        exec(compile(old_impl, ext.__file__, "exec"), mod.__dict__)
    except Exception as e:
        check("反证组：坏版本可加载", False, "%s: %s" % (type(e).__name__, e))
        return
    check("反证组：坏版本可加载", True)

    # 同一输入（慢但正常：音频 1.5 s < 阈值 2.0 s，墙钟 3.0 s > 阈值）
    st_broken = FakeTTSStream(chunk_sec=0.5, sleep_per=1.0, max_chunks=3)
    install_fake_tts_engine(st_broken, threshold_s=2.0)
    beng = make_engine(mod)
    ofb = mod.TTS_WALL_CLOCK_FALLBACK_SEC
    off = mod.TTS_WALL_CLOCK_FALLBACK_FACTOR
    mod.TTS_WALL_CLOCK_FALLBACK_SEC = 0.5
    mod.TTS_WALL_CLOCK_FALLBACK_FACTOR = 0.001
    try:
        pcm_b, sec_b = beng.tts("短句测试", voice="")
    finally:
        mod.TTS_WALL_CLOCK_FALLBACK_SEC = ofb
        mod.TTS_WALL_CLOCK_FALLBACK_FACTOR = off
    check("反证组：旧墙钟判据 ⇒ **慢但正常被中止**（判据有鉴别力）",
          beng.tts_runaway >= 1,
          "坏版本 runaway=%d resynth=%d（正确版本为 0/0）"
          % (beng.tts_runaway, beng.tts_resynth))

    st_good = FakeTTSStream(chunk_sec=0.5, sleep_per=1.0, max_chunks=3)
    install_fake_tts_engine(st_good, threshold_s=2.0)
    geng = make_engine(ext)
    pcm_g, sec_g = geng.tts("短句测试", voice="")
    check("反证组：正确版本（音频长度判据）⇒ **慢但正常不中止**",
          geng.tts_runaway == 0 and geng.tts_resynth == 0 and pcm_g is not None,
          "正确版本 runaway=%d resynth=%d pcm=%s"
          % (geng.tts_runaway, geng.tts_resynth, len(pcm_g) if pcm_g else 0))


def main():
    print("=" * 68)
    print("APP-154 §1 自测：EXT 失控判据（音频长度 vs 墙钟）")
    print("=" * 68)
    sys.modules.pop("ext.engine_runtime", None)
    from ext import engine_runtime as ext
    print("engine_runtime: %s" % ext.__file__)

    scenario_1_slow_but_normal(ext)
    scenario_2_audio_over_limit(ext)
    scenario_3_resynth_also_fails(ext)
    scenario_4_counterexample(ext)

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print("\n" + "=" * 68)
    print("结果：%d PASS / %d FAIL / 共 %d" % (npass, nfail, len(RESULTS)))
    print("=" * 68)
    if nfail:
        for name, ok, detail in RESULTS:
            if not ok:
                print("  FAIL: %s — %s" % (name, detail))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
