#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP-045① 验收：**克隆音色纯内存化**（不落盘）与 babelvox 原路径**数值等价**。

🔴 **为什么用「假引擎」而不是真模型**：
  真 babelvox 要加载 NPU/GPU IR ⇒ ① 会与**正在持锁做计时作业**的 TTS 模块
  争用硬件（记忆 §五：NPU 与 GPU.0 共用集显物理引擎）⇒ ② 违反
  「不在 CPU 上跑推理或测速」的纪律。
  ⇒ 改为：**用假引擎捕获 `speaker_enc` 的入参**，逐层比对
    「落盘旧路径」与「内存新路径」喂给 speaker encoder 的 mel 张量是否**逐位相同**。
  ⇒ 这恰好是最容易出错、也最该被卡住的一环（mel 参数漂移 ⇒ 音色失真）。

🔴 **判据**：
  ① mel 数值等价：新路径的 mel 与 babelvox 自己的 `mel_spectrogram_np`
     **逐位相同**（参数对齐）；
  ② resample 等价：内存重采样与 `librosa.load(path, sr=24000)` 的重采样
     **逐位相同**（否则与旧路径不等价）；
  ③ 端到端入参等价：喂给 `speaker_enc` 的 `mel_spectrogram` 张量
     **逐位相同**（落盘旧路径 vs 内存新路径）；
  ④ 不落盘：跑完新函数，`%TEMP%\\confucius4_clone\\` **不得**出现新文件
     （APP-045① 的核心诉求）；
  ⑤ 反证 A：把新函数注入成「落盘实现」⇒ 判据 ④ 必须 FAIL；
  ⑥ 反证 B：把 mel 的 sr 改错 ⇒ 判据 ①③ 必须 FAIL。

🔴 **判据工程铁律**（记忆 §十一）：
  - **不 import 被测模块**（顶层 numpy ⇒ import 阶段 abort）
    ⇒ `ast` 抽源码 + `exec` 独立命名空间；
  - **抽源码必须保留 Import**（坑①）；
  - **模块级常量单独 exec**（坑②）；
  - **反证改源码文本后再 exec**（坑③：反证改文本、exec 却用原 AST）；
  - **判据必须能识破已知缺陷**（反证 A/B 就是干跑这个）。

用法：
    python app161_app045_clone_inmemory_equivalence.py
    python app161_app045_clone_inmemory_equivalence.py --falsify
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ENGINE_PY = os.path.join(REPO, 'live_caption', 'tts_engine.py')

PKG_SITE = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12\python\Lib\site-packages'

FUNC_NAMES = {'speaker_embedding_from_pcm', '_mel_spectrogram_np_24000'}


def _build_ns(src_text, func_names=FUNC_NAMES):
    """抽源码 + exec 到独立命名空间（**不 import 被测模块**）。"""
    tree = ast.parse(src_text)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            keep.append(node)                      # 坑①：必须留 Import
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and (t.id.isupper() or t.id == 'Optional'):
                    keep.append(node)              # 坑②：常量一起抽
                    break
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_names:
                keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[])
    ns = {'__file__': ENGINE_PY, '__name__': 'app161_extracted'}
    exec(compile(mod, '<extracted>', 'exec'), ns)
    return ns


class _FakeEngine:
    """假引擎：捕获 `speaker_enc` 的入参（**不加载任何模型**）。

    🔴 模拟 babelvox 的 NPU 分支字段（`is_npu` / `max_speaker_frames`）
       ⇒ 顺带覆盖 NPU 的 pad 分支。
    """

    def __init__(self, is_npu=False, max_speaker_frames=64):
        self.is_npu = is_npu
        self.max_speaker_frames = max_speaker_frames
        self.captured = None

    def speaker_enc(self, inputs):
        self.captured = {k: np.copy(v) for k, v in inputs.items()}
        return np.zeros((1, 1024), dtype=np.float32)

    def extract_speaker_embedding(self, audio_path):
        """复刻 babelvox 的同名方法（**走文件路径**）—— 反证 A 需要它。

        🔴 反证 A 把新函数注入成「落盘实现」⇒ 它会调这个方法。
        """
        import librosa
        from babelvox.pipeline import mel_spectrogram_np as babelvox_mel
        audio, _sr = librosa.load(audio_path, sr=24000)
        mel = babelvox_mel(audio)
        mel_np = mel.T[np.newaxis, :, :].astype(np.float32)
        self.speaker_enc({'mel_spectrogram': mel_np})
        return np.zeros((1, 1024), dtype=np.float32)


def _clone_tmp_dir():
    return os.path.join(tempfile.gettempdir(), 'confucius4_clone')


def _snapshot(d):
    if not os.path.isdir(d):
        return set()
    return set(os.listdir(d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--falsify', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    if PKG_SITE not in sys.path:
        sys.path.insert(0, PKG_SITE)
    try:
        import numpy as np
        import librosa
        import soundfile as sf
        from babelvox.pipeline import mel_spectrogram_np as babelvox_mel
    except Exception as e:
        print('✗ 环境不可用（需包内 babelvox + numpy + librosa + soundfile）:', e)
        return 2

    results = []
    globals()['np'] = np          # 🔴 假引擎类里用 np（模块级全局）

    def rec(name, ok, detail):
        results.append(dict(name=name, ok=bool(ok), detail=detail))
        print(('  PASS  ' if ok else '  FAIL  ') + name + ' :: ' + detail)

    print('=' * 74)
    print('APP-045① 克隆纯内存化 —— 等价性 + 不落盘 验收')
    print('  falsify =', args.falsify)
    print('=' * 74)

    src = open(ENGINE_PY, 'r', encoding='utf-8').read()
    if args.falsify:
        # 🔴 反证 A：注入「落盘实现」（假装没改）
        src = src.replace(
            "def speaker_embedding_from_pcm(eng, pcm, sr: int = 16000,\n"
            "                               on_log=print) -> Optional['np.ndarray']:",
            "def speaker_embedding_from_pcm(eng, pcm, sr: int = 16000,\n"
            "                               on_log=print) -> Optional['np.ndarray']:\n"
            "    import soundfile as _sf, os as _os, tempfile as _tf\n"
            "    _d = _os.path.join(_tf.gettempdir(), 'confucius4_clone')\n"
            "    _os.makedirs(_d, exist_ok=True)\n"
            "    _p = _os.path.join(_d, 'clone_falsify.wav')\n"
            "    _sf.write(_p, pcm, 16000)\n"
            "    return eng.extract_speaker_embedding(_p)")
        # 🔴 反证 B：把 mel 的 sr 改错（16000 ≠ babelvox 的 24000）
        src = src.replace('sr, n_fft, hop_length = 24000, 1024, 256',
                          'sr, n_fft, hop_length = 16000, 1024, 256')
        print('  [反证] 已注入：落盘实现 + 错误 sr=16000')

    ns = _build_ns(src)
    if 'speaker_embedding_from_pcm' not in ns:
        print('✗ 抽不出 speaker_embedding_from_pcm')
        return 2
    mem_mel = ns['_mel_spectrogram_np_24000']
    spk_from_pcm = ns['speaker_embedding_from_pcm']

    # ── 造确定性测试音频（16 kHz 单声道，5 s）────────────────────────
    rng = np.random.default_rng(20261030)
    t = np.arange(int(16000 * 5.0)) / 16000.0
    pcm = (0.2 * np.sin(2 * np.pi * 220.0 * t)
           + 0.05 * rng.standard_normal(t.size)).astype(np.float32)

    tmpd = _clone_tmp_dir()
    before = _snapshot(tmpd)

    # ── 判据 ②：resample 等价 ───────────────────────────────────────
    #    🔴 **关键事实**（实测得出，不是推测）：
    #      旧落盘实现 `sf.write(path, pcm, 16000)` **默认写 PCM_16**
    #      ⇒ 旧路径本身就带 **16-bit 量化误差**（实测 max|Δ| ≈ 4.1e-05）
    #      ⇒ 内存路径（float32 原样）**比旧路径更精确**，不是回归。
    #    ⇒ 判据分两条：
    #      ②a 内存 resample 与 **float32 无损基准** 逐位相同（严格）
    #      ②b 内存 resample 与 **旧 PCM_16 落盘路径** 的差异 **不超过**
    #         PCM_16 量化误差量级（≤ 1e-4）⇒ 音色不会有可闻差异
    scratch = os.path.join(tempfile.gettempdir(), 'app161_scratch')
    os.makedirs(scratch, exist_ok=True)
    ref_wav = os.path.join(scratch, 'ref.wav')
    ref_wav_f32 = os.path.join(scratch, 'ref_f32.wav')
    try:
        # 旧路径的落盘（**默认 PCM_16**）—— 复刻 `_clone_tmp_wav` 的写法
        sf.write(ref_wav, pcm, 16000)
        # float32 无损落盘 —— 作为「理想基准」
        sf.write(ref_wav_f32, pcm, 16000, subtype='FLOAT')

        loaded_pcm16, _sr = librosa.load(ref_wav, sr=24000)
        loaded_f32, _sr = librosa.load(ref_wav_f32, sr=24000)
        res = librosa.resample(pcm, orig_sr=16000, target_sr=24000)

        d_exact = float(np.abs(loaded_f32 - res).max())
        rec('判据②a 内存 resample 与 float32 无损基准逐位相同',
            d_exact == 0.0 and len(loaded_f32) == len(res),
            'max|Δ|=%.3e len(%d vs %d)' % (d_exact, len(loaded_f32), len(res)))

        d_old = float(np.abs(loaded_pcm16 - res).max())
        rec('判据②b 与旧 PCM_16 落盘路径差异 ≤ 量化误差量级(1e-4)',
            d_old <= 1e-4 and len(loaded_pcm16) == len(res),
            'max|Δ|=%.3e（PCM_16 量化误差 ⇒ 内存路径更精确）' % d_old)

        # ── 判据 ①：mel 数值等价 ────────────────────────────────────
        #    基准取 **float32 无损**（⇒ 严格逐位相同）
        mel_ref = babelvox_mel(loaded_f32)                # babelvox 自己的实现
        mel_new = mem_mel(res)                            # 我们的复刻
        same_shape = mel_ref.shape == mel_new.shape
        rec('判据①a mel 形状一致', same_shape,
            'ref=%s new=%s' % (mel_ref.shape, mel_new.shape))
        if same_shape:
            dd = float(np.abs(mel_ref - mel_new).max())
            rec('判据①b mel 逐位相同（max|Δ| == 0）', dd == 0.0,
                'max|Δ|=%.3e' % dd)
    finally:
        for p in (ref_wav, ref_wav_f32):
            try:
                os.unlink(p)
            except Exception:
                pass
        shutil.rmtree(scratch, ignore_errors=True)

    # ── 判据 ③：端到端入参等价（落盘旧路径 vs 内存新路径）────────────
    #    用假引擎捕获喂给 speaker_enc 的张量
    #    基准取 **float32 无损**（旧路径的 PCM_16 量化已由判据②b 单独度量）
    eng_old = _FakeEngine(is_npu=False)
    eng_new = _FakeEngine(is_npu=False)
    loaded2 = librosa.resample(pcm, orig_sr=16000, target_sr=24000)
    mel_old = babelvox_mel(loaded2).T[np.newaxis, :, :].astype(np.float32)
    eng_old.speaker_enc({'mel_spectrogram': mel_old})

    spk_from_pcm(eng_new, pcm, sr=16000, on_log=lambda *a: None)
    a = eng_old.captured['mel_spectrogram']
    b = eng_new.captured['mel_spectrogram']
    rec('判据③a 端到端入参形状一致', a.shape == b.shape,
        'old=%s new=%s' % (a.shape, b.shape))
    if a.shape == b.shape:
        dd = float(np.abs(a - b).max())
        rec('判据③b 端到端入参逐位相同（max|Δ| == 0）', dd == 0.0,
            'max|Δ|=%.3e' % dd)

    # ── NPU 分支也要覆盖（pad 逻辑）─────────────────────────────────
    eng_npu = _FakeEngine(is_npu=True, max_speaker_frames=64)
    spk_from_pcm(eng_npu, pcm, sr=16000, on_log=lambda *a: None)
    c = eng_npu.captured['mel_spectrogram']
    rec('判据③c NPU 分支已 pad 到固定帧数',
        c.shape == (1, 64, 128), 'shape=%s（期望 (1, 64, 128)）' % (c.shape,))

    # ── 判据 ④：不落盘 ──────────────────────────────────────────────
    #    🔴 **判据要卡住反证 A**：反证 A 的落盘文件名固定
    #       （`clone_falsify.wav`）⇒ 只看「前后差集」可能因前面判据
    #       已清理而漏判 ⇒ 这里**额外**直接查目录里**有没有任何
    #       clone_*.wav**，并在整个测试**最后**再查一次。
    after = _snapshot(tmpd)
    new_files = after - before
    stray = sorted(f for f in after if f.lower().endswith('.wav'))
    rec('判据④a 新函数不产生任何临时文件', len(new_files) == 0,
        '新增=%r 目录=%s' % (sorted(new_files), tmpd))
    rec('判据④b 临时目录内无任何 clone_*.wav 残留', len(stray) == 0,
        '残留 wav=%r' % (stray,))

    # ── 汇总 ─────────────────────────────────────────────────────────
    #    🔴 **终态检查**：整个测试跑完后，临时目录里**不得**有任何 wav
    #    （反证 A 落下的 `clone_falsify.wav` 会被这一条抓到）
    final_files = _snapshot(tmpd)
    final_wav = sorted(f for f in final_files if f.lower().endswith('.wav'))
    rec('判据④c 终态：临时目录内无任何 wav 残留', len(final_wav) == 0,
        '终态残留=%r 目录=%s' % (final_wav, tmpd))
    #    清理（测试自身产生的）
    for f in final_wav:
        try:
            os.unlink(os.path.join(tmpd, f))
        except Exception:
            pass

    npass = sum(1 for r in results if r['ok'])
    nfail = len(results) - npass
    verdict = 'PASS' if nfail == 0 else 'FAIL'
    print('-' * 74)
    print('PASS=%d FAIL=%d verdict=%s' % (npass, nfail, verdict))

    out = dict(schema='app.app045.clone_inmemory_equivalence.v1',
               pass_=npass, fail=nfail, verdict=verdict,
               falsify=bool(args.falsify), checks=results)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
