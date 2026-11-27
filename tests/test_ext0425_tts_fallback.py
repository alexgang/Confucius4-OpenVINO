"""EXT v0.4.25 (APP-156 §1): TTS output with NaN/Inf or no audio must never become an empty dub.
Run as a script (same convention as the other EXT tests): prints 「结果：N PASS / M FAIL / 共 K」."""
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ext import engine_runtime as er  # noqa: E402


def _rt():
    rt = object.__new__(er.RuntimeEngine)
    rt.tts_nan_cut = 0
    rt.tts_wall_fallback = 0
    rt.last_error = {}
    rt.on_log = lambda *a, **k: None
    rt._tts_eng = object()
    return rt


def _install_stream(chunks):
    def stream(eng, text, **kw):
        for c in chunks:
            yield (None if c is None else np.asarray(c, dtype=np.float32)), 24000
    mod = types.ModuleType('tts_engine')
    mod.stream = stream
    sys.modules['tts_engine'] = mod


def t_finite_prefix():
    rt = _rt()
    arr, bad = rt._finite_prefix(np.array([0.1, 0.2, np.nan, 0.3], dtype=np.float32))
    assert bad and arr.shape[0] == 2 and rt.tts_nan_cut == 1
    arr, bad = rt._finite_prefix(np.array([0.1, 0.2], dtype=np.float32))
    assert not bad and arr.shape[0] == 2


def t_nan_is_failure_with_reason():
    rt = _rt()
    _install_stream([np.full(2400, 0.1), [0.1, np.inf, 0.2]])
    pcm, why = rt._collect_tts('x', language='Chinese', max_tok=10, audio_limit=30.0, wall_fallback=60.0)
    assert pcm is None and why and 'nan' in why, (pcm, why)


def t_empty_is_failure_with_reason():
    rt = _rt()
    _install_stream([None])
    pcm, why = rt._collect_tts('x', language='Chinese', max_tok=10, audio_limit=30.0, wall_fallback=60.0)
    assert pcm is None and why == 'empty audio', (pcm, why)


def t_normal_audio_passes():
    rt = _rt()
    _install_stream([np.full(2400, 0.1), np.full(2400, -0.1)])
    pcm, why = rt._collect_tts('x', language='Chinese', max_tok=10, audio_limit=30.0, wall_fallback=60.0)
    assert why is None and len(pcm) == 4800 * 2


def t_truncated_keeps_finite_part():
    rt = _rt()
    _install_stream([np.full(2400, 0.1), [0.2, np.nan, 0.3], np.full(2400, 0.1)])
    pcm = rt._collect_tts_truncated('x', language='Chinese', max_tok=10, audio_limit=30.0, wall_fallback=60.0)
    a = np.frombuffer(pcm, '<i2')
    assert a.shape[0] == 2401, a.shape


if __name__ == '__main__':
    cases = [t_finite_prefix, t_nan_is_failure_with_reason, t_empty_is_failure_with_reason,
             t_normal_audio_passes, t_truncated_keeps_finite_part]
    npass = nfail = 0
    for c in cases:
        try:
            c(); npass += 1; print('PASS', c.__name__)
        except Exception as e:  # noqa: BLE001
            nfail += 1; print('FAIL', c.__name__, repr(e))
    print('结果：%d PASS / %d FAIL / 共 %d' % (npass, nfail, len(cases)))
    sys.exit(1 if nfail else 0)
