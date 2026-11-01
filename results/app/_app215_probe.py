#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-061 判据探针（**被测对象在 sys.argv[1] 指定的目录**）。

🔴 **在独立子进程里跑**（`app215` 调用本脚本）：
  ⇒ 每次都是**全新解释器** ⇒ 模块级状态不串 ⇒ 变异体与正常体互不污染。

本探针只做**行为观测**，不判定通过/失败（判定在 `app215_...py`）：
  * `preset_name_after_setup`   —— `_setup_babelvox_voice()` 之后 `_preset_name`
  * `speaker_name_after_fallback` —— `_fallback_to_preset()` 之后 `speaker_name`
  * `voice_gate_tripped`        —— synth 的音色闸门表达式是否成立
  * `emitted_voice_error`       —— synth 实际是否发出「没有可用的音色」
  * `synth_exc`                 —— synth 是否在闸门**之前**就抛异常（⇒ 探针无效）
  * `keep_last_*`               —— ⑤c 的 `spk_pending⇒keep_last`
输出：单行 JSON（stdout）。
"""
from __future__ import annotations

import io
import json
import os
import sys
import types


def _stub_tts_engine(target: str):
    """🔴 `_setup_babelvox_voice()` 里 `import tts_engine` ⇒ **预置桩模块**，
    免得探针依赖真实的模型目录（客户包/开发目录里 models/ 布局不同）。"""
    stub = types.ModuleType('tts_engine')
    stub.BUILTIN_SPEAKERS = ('cindy', 'anna')
    stub.builtin_speakers_available = lambda: ()
    stub.preset_voice_path = lambda: os.path.join(
        target, 'models', 'qwen3tts', 'voices', 'preset_A.wav')
    stub.speaker_embedding = lambda *a, **k: None
    sys.modules['tts_engine'] = stub
    return stub


class FakeCudaEngine:
    """🔴 假的 CUDA 边车客户端：只实现 worker 用到的三个成员。"""

    USES_REF_AUDIO = True

    def __init__(self, ref=None):
        self.ref_audio = ref
        self.set_ref_calls = []

    def set_ref_audio(self, path):
        self.set_ref_calls.append(path)
        self.ref_audio = path
        return True


def _make_worker(tw, engine):
    """🔴 用 `__new__` 造一个**只填必要字段**的 worker（不跑 `__init__`
    ⇒ 不加载模型、不起线程）。"""
    w = tw.TTSWorker.__new__(tw.TTSWorker)
    w.engine = engine
    w.voice = 'A'
    w.device = 'CUDA'
    w.precision = 'bf16'
    w.speaker_embed = None
    w.speaker_name = 'A'
    w._preset_embed = None
    w._preset_name = None
    w._preset_ref_path = None
    w._clone_embed = None
    w._clone_ref_path = None
    w._clone_audio_s = 0.0
    w._clone_active = False
    w._clone_mode = None
    w._clone_updated_at = 0.0
    w._last_clone_active = False
    w._last_clone_mode = None
    w._last_clone_audio_s = 0.0
    w._last_voice_spk = None
    w._last_voice_kind = 'preset'
    w._last_spk = None
    w._last_spk_conf = None
    w._last_lang = 'zh'
    w._last_lang_src = 'explicit'
    w._last_end_reason = None
    w._last_lead_punct = ''
    w._last_lead_punct_n = 0
    w.clone_mode = False
    w._spk_voices = {}
    w._spk_voice_lock = __import__('threading').RLock()
    w._dequeue_at = {}
    w._recv_at = {}
    w._enqueue_at = {}
    w._cancelled = set()
    w._jsonl_path = None
    w._player = None
    w._synth_lock = __import__('threading').RLock()
    return w


def main() -> int:
    target = os.path.abspath(sys.argv[1])
    sys.path.insert(0, target)
    _stub_tts_engine(target)

    import tts_worker as tw

    out = {}

    # ── 捕获 emit / log ────────────────────────────────────────────
    emitted = []
    logs = []
    _orig_emit = tw.emit
    _orig_log = tw.log

    def _emit(obj):
        try:
            emitted.append(dict(obj))
        except Exception:
            pass
        return _orig_emit(obj)

    def _log(msg):
        try:
            logs.append(str(msg))
        except Exception:
            pass
        return _orig_log(msg)

    tw.emit = _emit
    tw.log = _log

    # ── ①-a：`_setup_babelvox_voice()` 之后 `_preset_name` ─────────
    eng = FakeCudaEngine()
    w = _make_worker(tw, eng)
    try:
        w._setup_babelvox_voice()
        out['setup_exc'] = None
    except Exception as e:
        out['setup_exc'] = repr(e)
    out['preset_name_after_setup'] = getattr(w, '_preset_name', '<missing>')
    out['preset_ref_path_after_setup'] = getattr(w, '_preset_ref_path', '<missing>')

    # ── ①-b：`_fallback_to_preset()` 之后 `speaker_name` ───────────
    try:
        w._fallback_to_preset('no_spk_label')
        out['fallback_exc'] = None
    except Exception as e:
        out['fallback_exc'] = repr(e)
    out['speaker_name_after_fallback'] = getattr(w, 'speaker_name', '<missing>')
    out['speaker_embed_after_fallback'] = getattr(w, 'speaker_embed', '<missing>')

    # ── ①-c：synth 的音色闸门 + 真实 synth 行为 ────────────────────
    gate = (w.speaker_embed is None and not w.speaker_name)
    out['voice_gate_tripped'] = bool(gate)

    # 🔴 **分两种情况**：
    #   A) 参考音频**存在** ⇒ synth **不得**报「没有可用的音色」
    #   B) 参考音频**缺失** ⇒ synth **应当**报（这是正确的降级）
    # ⚠️ 开发目录里没有 `models/` ⇒ 必须**造一个真文件**才能测 A。
    ref_file = os.path.join(target, '_app215_tmp_ref.wav')
    with open(ref_file, 'wb') as f:
        f.write(b'RIFF----WAVEfmt ')
    w._preset_ref_path = ref_file
    try:
        w.engine.ref_audio = ref_file
    except Exception:
        pass

    emitted.clear()
    logs.clear()
    exc = None
    try:
        w.synth(jid=1, text='测试一句中文。', spk=None, lang='zh')
    except Exception as e:
        exc = repr(e)
    out['synth_with_ref_exc'] = exc
    out['synth_with_ref_messages'] = [str(e.get('message', '')) for e in emitted]
    out['synth_with_ref_voice_error'] = any(
        ('没有可用的音色' in str(e.get('message', ''))) for e in emitted)

    # B) 参考音频缺失 ⇒ 应当报「没有可用的音色」
    os.remove(ref_file)
    w._preset_ref_path = None
    try:
        w.engine.ref_audio = None
    except Exception:
        pass
    emitted.clear()
    logs.clear()
    exc = None
    try:
        w.synth(jid=2, text='测试一句中文。', spk=None, lang='zh')
    except Exception as e:
        exc = repr(e)
    out['synth_without_ref_exc'] = exc
    out['synth_without_ref_messages'] = [str(e.get('message', '')) for e in emitted]
    out['synth_without_ref_voice_error'] = any(
        ('没有可用的音色' in str(e.get('message', ''))) for e in emitted)

    # ── ①-b′：**旧状态下**的回落（模拟 v2.1：`_preset_name` 从未被设置）──
    #   旧实现：回落把 `speaker_name` 置成 `self._preset_name` = **None**
    #   ⇒ 后续 `synth` 的音色闸门 `speaker_embed is None and not speaker_name`
    #     **成立** ⇒ 每句报「没有可用的音色」。
    #   新实现：CUDA 路线**只换参考音频**，`speaker_name` 保持 'A'。
    w_old = _make_worker(tw, FakeCudaEngine())
    w_old._preset_name = None
    w_old.speaker_embed = None
    w_old.speaker_name = None
    try:
        w_old._fallback_to_preset('no_spk_label')
        out['old_state_fallback_exc'] = None
    except Exception as e:
        out['old_state_fallback_exc'] = repr(e)
    out['old_state_speaker_name_after_fallback'] = getattr(
        w_old, 'speaker_name', '<missing>')
    out['old_state_voice_gate_tripped'] = bool(
        w_old.speaker_embed is None and not w_old.speaker_name)

    # ── ①-c′：**旧状态下**的 synth（`_preset_name` 未设 + `speaker_name` 为空）──
    #   新闸门查「有没有参考音频」⇒ 参考音频在 ⇒ **不得**报「没有可用的音色」。
    #   旧闸门查 `speaker_embed` / `speaker_name` ⇒ **必然误报**（每句失败）。
    ref_file2 = os.path.join(target, '_app215_tmp_ref2.wav')
    with open(ref_file2, 'wb') as f:
        f.write(b'RIFF----WAVEfmt ')
    w_old._preset_ref_path = ref_file2
    try:
        w_old.engine.ref_audio = ref_file2
    except Exception:
        pass
    # 🔴🔴 **关键**：把状态**强制**回 v2.1 的旧形态
    #   （`_preset_name` 未设 ⇒ 回落后 `speaker_name` 为空 ⇒ `speaker_embed` 为空）
    #   ⇒ 这样「旧闸门」必然误报、「新闸门」必然不报 ⇒ 判据才能区分两者。
    w_old._preset_name = None
    w_old.speaker_embed = None
    w_old.speaker_name = None
    emitted.clear()
    logs.clear()
    exc = None
    try:
        w_old.synth(jid=3, text='测试一句中文。', spk=None, lang='zh')
    except Exception as e:
        exc = repr(e)
    out['old_state_synth_exc'] = exc
    out['old_state_synth_messages'] = [str(e.get('message', '')) for e in emitted]
    out['old_state_synth_voice_error'] = any(
        ('没有可用的音色' in str(e.get('message', ''))) for e in emitted)
    try:
        os.remove(ref_file2)
    except Exception:
        pass

    # ── ①-d：`_has_ref_audio()` 三态 ───────────────────────────────
    res = {}
    try:
        w2 = _make_worker(tw, FakeCudaEngine(ref=None))
        w2._preset_ref_path = None
        w2._clone_ref_path = None
        res['no_ref'] = bool(w2._has_ref_audio())
        tmp = os.path.join(target, '_app215_tmp_ref.wav')
        with open(tmp, 'wb') as f:
            f.write(b'RIFF')
        w2._preset_ref_path = tmp
        res['with_ref'] = bool(w2._has_ref_audio())
        os.remove(tmp)
    except Exception as e:
        res['exc'] = repr(e)
    out['has_ref_audio'] = res

    # ── ⑤-c：`_has_clone_voice()` / `_log_keep_last_clone()` ───────
    res = {}
    try:
        w3 = _make_worker(tw, FakeCudaEngine())
        w3._clone_active = False
        w3._last_voice_kind = 'preset'
        res['no_clone'] = bool(w3._has_clone_voice())
        w3._last_voice_kind = 'clone'
        res['clone_kind'] = bool(w3._has_clone_voice())
        w3._clone_active = True
        w3._last_voice_kind = 'preset'
        res['clone_active'] = bool(w3._has_clone_voice())
        logs.clear()
        w3._log_keep_last_clone()
        res['keep_last_log'] = [s for s in logs if 'keep_last' in s]
        res['keep_last_kind'] = w3._last_voice_kind
    except Exception as e:
        res['exc'] = repr(e)
    out['keep_last'] = res

    tw.emit = _orig_emit
    tw.log = _orig_log
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
