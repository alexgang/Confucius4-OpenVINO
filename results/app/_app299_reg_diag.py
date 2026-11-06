# -*- coding: utf-8 -*-
"""APP-075(d)：**登记诊断落盘**（每个说话人登记所用的 seg/起止/conf/F0 中位
＋ **x-vector 余弦矩阵 S×S**）。

> APP-075(d) 原文：
> > (d) 诊断落盘：每个说话人登记所用的 (seg, 起止, spk_conf, F0 中位)、x-vector 余弦矩阵（S×S）；

## 🔴🔴🔳 与 app283 的关键区别（**必须说清**）
app283 复刻的是**旧**登记逻辑（「该 spk 的全部 clean 区间并集」）
⇒ **不含** APP-075 的门槛（conf ≥ 0.5 / 切换点守卫 / 连续 ≥ 2.5 s / 最长择段）
⇒ **本脚本复刻的是**「`live_caption/speaker_voice.py` 的**新**登记逻辑」：
   ① `note_final(seg, spk, clean_ranges, spk_conf)`
   ② `registration_ticket(spk)` ⇒ 唯一一段合格登记区间
⇒ ⇒ **本脚本的 `registered` 段落** = **新逻辑真正会拿去登记的那一段**。

## 🔴 x-vector 的口径（**必须分清**）
- 默认（`--stat-embed`）：**纯 CPU 统计嵌入**（mel + 固定投影，1024 维）
  ⇒ 只用于**相对比较**与离线根因定位；**绝对值无意义**。
- `--with-model`：真调生产引擎的 `speaker_embedding_from_pcm`（OpenVINO
  wespeaker）⇒ **占设备** ⇒ 需 MACHINE_LOCK。
  ⇒ reviewer 的硬判据「x-vector 余弦」**必须**用这一档。

## 用法
```
python results/app/_app299_reg_diag.py                # 纯 CPU 统计嵌入
python results/app/_app299_reg_diag.py --with-model   # 真 x-vector（占设备）
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import sys
import wave
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = r'C:\Users\Trekker-PTL'
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import speaker_voice as sv                                  # noqa: E402

V23 = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone')
OUT_DIR = os.path.join(REPO, 'results', 'app', 'app299_app075_reg_diag')
SR = 16000

# 🔴 app246 判据常量（性别判定）
F0_MIN = 60.0
F0_MAX = 400.0
FRAME_MS = 40.0
HOP_MS = 20.0
F0_MALE_MAX = 160.0

# 🔴 reviewer 在 APP-071 (b) 原文给的阈值（**原声参考段的准入**）
REF_CONF_MIN = 0.8
REF_MIN_S = 3.0

MIX_WAV = os.path.join(V23, 'SPE_mix_3303_3603.wav')
MANIFEST = os.path.join(V23, 'mix_segment_manifest.json')
APP293 = os.path.join(REPO, 'results', 'app', '_app293_label_overlap.json')
BYSEG_JSON = os.path.join(V23, 'seg_voice_table_by_seg.json')


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_wav_mono16(path: str):
    import numpy as np
    with wave.open(path, 'rb') as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        assert sw == 2 and nch == 1, '只处理 16-bit 单声道（sw=%d nch=%d）' % (sw, nch)
        raw = w.readframes(nf)
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    return a, sr, nf


def write_wav_mono16(path: str, a, sr: int = SR) -> int:
    import numpy as np
    x = np.asarray(a, dtype=np.float32).reshape(-1)
    pcm = np.clip(x * 32767.0, -32768, 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return os.path.getsize(path)


def f0_autocorr(frame, sr, fmin=F0_MIN, fmax=F0_MAX) -> float:
    """自相关法基频（**逐字复用 app246/app283 的实现** ⇒ 口径一致）。"""
    import numpy as np
    x = frame - float(frame.mean())
    n = x.size
    if n < 64:
        return 0.0
    w = np.hanning(n).astype(np.float32)
    xw = x * w
    energy = float(np.dot(xw, xw))
    if energy <= 1e-8:
        return 0.0
    m = 1 << int(math.ceil(math.log2(2 * n)))
    f = np.fft.rfft(xw, m)
    ac = np.fft.irfft(f * np.conj(f), m)[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    lag_min = max(2, int(sr / fmax))
    lag_max = min(n - 1, int(sr / fmin))
    if lag_max <= lag_min:
        return 0.0
    seg = ac[lag_min:lag_max + 1]
    peaks = []
    for i in range(1, seg.size - 1):
        v = float(seg[i])
        if v >= float(seg[i - 1]) and v > float(seg[i + 1]):
            peaks.append((lag_min + i, v))
    if not peaks:
        return 0.0
    gmax = max(v for _, v in peaks)
    if gmax < 0.25:
        return 0.0
    for lag, v in peaks:
        if v >= 0.85 * gmax:
            return sr / float(lag)
    return sr / float(peaks[0][0])


def segment_f0(a, sr, t0, t1) -> List[float]:
    import numpy as np
    i0 = max(0, int(t0 * sr))
    i1 = min(a.size, int(t1 * sr))
    if i1 - i0 < int(0.3 * sr):
        return []
    seg = a[i0:i1]
    flen = int(FRAME_MS * sr / 1000.0)
    hop = int(HOP_MS * sr / 1000.0)
    out = []
    for s in range(0, max(0, seg.size - flen), hop):
        fr = seg[s:s + flen]
        if float(np.sqrt(np.mean(fr * fr))) < 0.01:
            continue
        f0 = f0_autocorr(fr, sr)
        if f0 > 0 and f0 < 0.97 * F0_MAX:
            out.append(f0)
    return out


def pct(vals, p) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def mel_spectrogram_np_24000(audio):
    """**逐字复用** `live_caption/tts_engine.py::_mel_spectrogram_np_24000`。"""
    import numpy as np
    import librosa
    from librosa.filters import mel as librosa_mel_fn
    S = librosa.stft(audio, n_fft=1024, hop_length=256, win_length=1024,
                     window='hann', center=True, pad_mode='reflect')
    mag = np.abs(S) ** 2
    mel = librosa_mel_fn(sr=24000, n_fft=1024, n_mels=128,
                         fmin=0.0, fmax=12000.0)
    out = mel @ mag
    return out.astype(np.float32)


def stat_embed(pcm, sr: int = SR):
    """**统计嵌入**（1024 维，纯 CPU）⇒ 只用于相对比较。"""
    import numpy as np
    pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
    if pcm.size == 0:
        return None
    if sr != 24000:
        import librosa
        audio = librosa.resample(pcm, orig_sr=sr, target_sr=24000)
    else:
        audio = pcm
    mel = mel_spectrogram_np_24000(audio)
    if mel is None:
        return None
    m = mel.T.astype(np.float64)
    mu = m.mean(axis=0)
    sd = m.std(axis=0)
    mx = np.abs(m).max(axis=0)
    q25 = np.percentile(m, 25, axis=0)
    q75 = np.percentile(m, 75, axis=0)
    v = np.concatenate([mu, sd, mx, q25, q75, mu * sd, sd * sd, mx * q75])
    assert v.size == 1024, '统计嵌入维度应为 1024，实测 %d' % v.size
    e = v.astype(np.float32)
    n = float(np.linalg.norm(e))
    if n < 1e-9:
        return None
    return (e / n).reshape(1, -1)


def true_xvector(pcm, sr: int = SR):
    """🔴 **真 x-vector**（生产链：OpenVINO wespeaker）⇒ 占设备。

    ⚠️ 调用方**必须已持有 MACHINE_LOCK**。
    """
    import numpy as np
    import tts_engine
    pkg = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
    eng = tts_engine.load_engine(pkg_root=pkg, device='NPU', precision='fp16')
    return tts_engine.speaker_embedding_from_pcm(eng, pcm, sr=sr)


def cosine(a, b) -> float:
    import numpy as np
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-model', action='store_true',
                    help='用真 x-vector（占设备 ⇒ 必须持 MACHINE_LOCK）')
    args = ap.parse_args()

    import numpy as np
    os.makedirs(OUT_DIR, exist_ok=True)

    ev: dict = {
        'script': '_app299_reg_diag.py',
        'correction': 'APP-075(d) 登记诊断落盘',
        'ts': datetime.datetime.now().isoformat(timespec='seconds'),
        'mode': 'true_xvector' if args.with_model else 'offline_stat_embed',
        'mode_note': (
            '**真 x-vector**（生产 OpenVINO wespeaker）⇒ reviewer 硬判据可用。'
            if args.with_model else
            '**纯 CPU 统计嵌入**（mel + 固定投影）⇒ 只用于相对比较与离线根因定位；'
            '**不能**替代 reviewer 的真 x-vector 判据。'),
        'criteria': {
            'reg_conf_min': sv.REG_CONF_MIN,
            'reg_min_cont_s': sv.REG_MIN_CONT_S,
            'switch_guard_s': sv.SWITCH_GUARD_S,
            'cont_gap_tol_s': sv.CONT_GAP_TOL_S,
            'ref_conf_min': REF_CONF_MIN,
            'ref_min_s': REF_MIN_S,
            'f0_male_max_hz': F0_MALE_MAX,
        },
        'inputs': {},
        'registered': {},
        'original_refs': {},
        'cosine_matrix': {},
        'judgement': [],
        'n_pass': 0,
        'n_fail': 0,
        'verdict': None,
    }

    # ── 输入 ────────────────────────────────────────────────
    with open(APP293, encoding='utf-8') as f:
        a293 = json.load(f)
    rows = sorted(a293['per_seg'], key=lambda r: (r['t0'], r['seg']))
    ev['inputs']['app293'] = {
        'path': APP293, 'bytes': os.path.getsize(APP293),
        'sha256': sha256_of(APP293), 'n_rows': len(rows),
        'note': 'app293 设备实测逐段（seg/t0/t1/spk/spk_conf/实测 F0）',
    }
    mix, mix_sr, mix_n = read_wav_mono16(MIX_WAV)
    ev['inputs']['mix_wav'] = {
        'path': MIX_WAV, 'bytes': os.path.getsize(MIX_WAV),
        'sha256': sha256_of(MIX_WAV), 'sr': mix_sr,
        'dur_s': round(mix_n / float(mix_sr), 3),
    }

    # ── 🔴🔴🔳 复刻**新**登记逻辑 ────────────────────────────
    tbl = sv.SpeakerVoiceTable()
    for r in rows:
        tbl.note_final(int(r['seg']), str(r['app_spk']),
                       [(float(r['t0']), float(r['t1']))],
                       float(r['app_conf']))
    ev['switch_points'] = tbl._switch_points_locked()

    f0_by_seg = {int(r['seg']): float(r['measured_f0_median'])
                 for r in rows}
    cls_by_seg = {int(r['seg']): r.get('measured_class') for r in rows}

    spks = sorted(set(str(r['app_spk']) for r in rows))
    reg_vecs = {}
    for spk in spks:
        runs = tbl.qualified_runs(spk)
        ticket, key = tbl.registration_ticket(spk)
        runs_all = runs
        meta = {
            'spk': spk,
            'n_qualified_runs': len(runs_all),
            'qualified_runs': runs_all,
            'registration_ticket': ticket,
            'registration_key': key,
            'n_segments_of_spk': sum(1 for r in rows
                                     if str(r['app_spk']) == spk),
            'segments': [{'seg': int(r['seg']), 't0': float(r['t0']),
                          't1': float(r['t1']),
                          'spk_conf': float(r['app_conf']),
                          'measured_f0_median_hz': f0_by_seg.get(int(r['seg'])),
                          'measured_class': cls_by_seg.get(int(r['seg']))}
                         for r in rows if str(r['app_spk']) == spk],
        }
        # 登记所用的那一段：ticket（= 新逻辑真正会拿去登记的那一段）
        if ticket:
            a, b = ticket[0]
            segs = set()
            for x in runs_all:
                if abs(x['a'] - a) < 1e-6 and abs(x['b'] - b) < 1e-6:
                    segs.update(x['segs'])
            f0s = [f0_by_seg[s] for s in sorted(segs) if s in f0_by_seg]
            med = pct(f0s, 50)
            meta['registered_run'] = {
                'a_s': a, 'b_s': b, 'dur_s': round(b - a, 3),
                'segs': sorted(segs),
                'spk_conf_of_segs': [float(r['app_conf']) for r in rows
                                     if int(r['seg']) in segs],
                'f0_median_hz': round(med, 2) if med else None,
                'f0_min_hz': round(min(f0s), 2) if f0s else None,
                'f0_max_hz': round(max(f0s), 2) if f0s else None,
                'presumed_class': ('low_f0_male_presumed'
                                   if (med and med < F0_MALE_MAX)
                                   else 'high_f0_female_presumed'),
            }
            # 参考 PCM（按登记区间切，**逐字复刻** `pcm_for_ranges`）
            i0 = max(0, int(round(a * mix_sr)))
            i1 = min(mix.size, int(round(b * mix_sr)))
            pcm = mix[i0:i1] if i1 > i0 else np.zeros(0, dtype=np.float32)
            max_n = int(10.0 * mix_sr)
            if pcm.size > max_n:
                pcm = pcm[-max_n:]
            wav_path = os.path.join(OUT_DIR, 'regpcm_%s.wav' % spk)
            meta['registered_run']['ref_pcm_wav'] = wav_path
            meta['registered_run']['ref_pcm_wav_bytes'] = write_wav_mono16(
                wav_path, pcm, mix_sr)
            meta['registered_run']['ref_pcm_s'] = round(pcm.size / float(mix_sr), 3)
            vec = (true_xvector(pcm, mix_sr) if args.with_model
                   else stat_embed(pcm, mix_sr))
            if vec is not None:
                npy = os.path.join(OUT_DIR, 'xvec_%s.npy' % spk)
                np.save(npy, vec)
                meta['xvector_npy'] = npy
                meta['xvector_npy_bytes'] = os.path.getsize(npy)
                meta['xvector_shape'] = list(vec.shape)
                reg_vecs[spk] = vec
            else:
                meta['xvector_npy'] = None
        else:
            meta['registered_run'] = None
        ev['registered'][spk] = meta

    # ── 原声参考向量（**真值**来自 app246 的分段 + 实测 conf）────
    with open(BYSEG_JSON, encoding='utf-8') as f:
        byseg = json.load(f)
    truth = byseg if isinstance(byseg, list) else byseg.get('rows', [])
    # 原声参考：按 app246 的真值 spk（`gender_presumed`）取该 spk 的干净长段
    with open(MANIFEST, encoding='utf-8') as f:
        man = json.load(f)
    win_start = man['window']['start_s']
    truth_spk_of = {}
    for r in truth:
        sid = r.get('seg_id')
        if sid is not None:
            truth_spk_of[int(sid)] = str(r.get('spk') or '')
    # 参考向量：从 mix 里按 **app293 的段**（含实测 conf + 真值性别）取
    #   ⇒ 准入：conf ≥ REF_CONF_MIN 且段时长 ≥ REF_MIN_S
    #   ⇒ **每个说话人取「最长的」那一段**（与登记侧同一择段口径 ⇒ 可比）
    ref_best = {}
    for r in rows:
        if float(r['app_conf']) < REF_CONF_MIN:
            continue
        dur = float(r['t1']) - float(r['t0'])
        if dur < REF_MIN_S:
            continue
        spk = str(r['app_spk'])
        if spk not in ref_best or dur > ref_best[spk][0]:
            ref_best[spk] = (dur, r)
    ref_vecs = {}
    for spk, (dur, r) in sorted(ref_best.items()):
        a = float(r['t0'])
        b = float(r['t1'])
        i0 = max(0, int(round(a * mix_sr)))
        i1 = min(mix.size, int(round(b * mix_sr)))
        pcm = mix[i0:i1] if i1 > i0 else np.zeros(0, dtype=np.float32)
        f0s = segment_f0(mix, mix_sr, a, b)
        med = pct(f0s, 50)
        vec = (true_xvector(pcm, mix_sr) if args.with_model
               else stat_embed(pcm, mix_sr))
        meta = {
            'spk': spk, 'seg': int(r['seg']), 't0': a, 't1': b,
            'dur_s': round(dur, 3), 'spk_conf': float(r['app_conf']),
            'f0_median_hz': round(med, 2) if med else None,
            'presumed_class': ('low_f0_male_presumed'
                               if (med and med < F0_MALE_MAX)
                               else 'high_f0_female_presumed'),
        }
        if vec is not None:
            npy = os.path.join(OUT_DIR, 'ref_%s.npy' % spk)
            np.save(npy, vec)
            meta['xvector_npy'] = npy
            meta['xvector_npy_bytes'] = os.path.getsize(npy)
            ref_vecs[spk] = vec
        ev['original_refs'][spk] = meta

    # ── 余弦矩阵（S×S）────────────────────────────────────────
    keys = sorted(set(list(reg_vecs.keys()) + list(ref_vecs.keys())))
    mat = {}
    for rk in keys:
        mat[rk] = {}
        for ck in keys:
            rv = reg_vecs.get(rk)
            cv = ref_vecs.get(ck)
            mat[rk][ck] = round(cosine(rv, cv), 6) if (rv is not None and
                                                      cv is not None) else None
    ev['cosine_matrix'] = {
        'rows': '登记（registered）', 'cols': '原声参考（original_refs）',
        'keys': keys, 'matrix': mat,
    }

    # ── 判据 ────────────────────────────────────────────────
    checks = []

    def add(name, ok, detail):
        checks.append(dict(name=name, verdict=bool(ok), detail=detail))

    # ① 每个 spk 都有登记诊断
    missing = [s for s in spks if not ev['registered'][s].get('registered_run')]
    add('每个 spk 都有「登记所用的那一段」诊断',
        not missing, {'n_spk': len(spks), 'missing': missing})

    # ② 每个登记都有 wav + npy
    bad = []
    for s in spks:
        m = ev['registered'][s]
        rr = m.get('registered_run') or {}
        if not (rr.get('ref_pcm_wav') and os.path.isfile(rr['ref_pcm_wav'])
                and m.get('xvector_npy')
                and os.path.isfile(m['xvector_npy'])):
            bad.append(s)
    add('每个登记都有参考 PCM wav ＋ x-vector npy',
        not bad, {'missing': bad})

    # ③ 余弦矩阵完整
    add('x-vector 余弦矩阵（S×S）完整',
        len(keys) > 0 and all(mat[rk][ck] is not None
                              for rk in keys for ck in keys
                              if rk in reg_vecs and ck in ref_vecs),
        {'keys': keys})

    # ④ **reviewer 的硬判据**：S2 的登记向量对**原声 S2** 的余弦
    #    必须高于对 S1/S3 的余弦
    s2 = mat.get('S2') or {}
    if s2 and s2.get('S2') is not None:
        others = [v for k, v in s2.items()
                  if k != 'S2' and v is not None]
        ok = all(s2['S2'] > v for v in others) if others else False
        add('【reviewer 硬判据】S2 登记向量对原声 S2 的余弦 > 对其它说话人',
            ok, {'cos_S2_S2': s2.get('S2'), 'others': s2})
    else:
        add('【reviewer 硬判据】S2 登记向量对原声 S2 的余弦 > 对其它说话人',
            False, {'why': 'S2 无登记向量或无参考向量',
                    'matrix_keys': keys})

    # ⑤ **登记段性别**：S2 登记段必须是男声（F0 < 160 Hz）
    s2rr = (ev['registered'].get('S2') or {}).get('registered_run') or {}
    f0m = s2rr.get('f0_median_hz')
    add('S2 登记段的实测 F0 中位 < 160 Hz（= 男声 ⇒ 登记对了人）',
        f0m is not None and f0m < F0_MALE_MAX,
        {'f0_median_hz': f0m, 'f0_max_hz': s2rr.get('f0_max_hz'),
         'segs': s2rr.get('segs'), 'a_s': s2rr.get('a_s'),
         'b_s': s2rr.get('b_s')})

    # ⑥ **反证**（判据非恒真）：把 S2 的登记向量换成 S1 的 ⇒ 判据④必须 FAIL
    if 'S2' in reg_vecs and 'S1' in reg_vecs and 'S2' in ref_vecs:
        fake = cosine(reg_vecs['S1'], ref_vecs['S2'])
        real = cosine(reg_vecs['S2'], ref_vecs['S2'])
        add('【反证】把 S2 登记向量换成 S1 ⇒ 对原声 S2 的余弦下降 '
            '⇒ 判据④能识破（非恒真）',
            fake < real, {'real_S2_S2': round(real, 6),
                          'fake_S1_S2': round(fake, 6)})
    else:
        add('【反证】把 S2 登记向量换成 S1 ⇒ 对原声 S2 的余弦下降',
            False, {'why': '缺向量', 'keys': keys})

    ev['judgement'] = checks
    ev['n_pass'] = sum(1 for c in checks if c['verdict'])
    ev['n_fail'] = sum(1 for c in checks if not c['verdict'])
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'

    out_json = os.path.join(OUT_DIR, 'app299_app075_reg_diag.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)

    for c in checks:
        print('[%s] %s  %s' % ('PASS' if c['verdict'] else 'FAIL',
                               c['name'],
                               json.dumps(c['detail'], ensure_ascii=False)[:400]))
    print('\n结果：%d PASS / %d FAIL ⇒ %s'
          % (ev['n_pass'], ev['n_fail'], ev['verdict']))
    print('[evidence] %s' % out_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
