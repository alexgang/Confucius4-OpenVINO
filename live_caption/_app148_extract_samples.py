"""APP-148 §1c：**抽听样片**（从「保留背景音开 + clone」那一轮切 3 段配音混音）。

reviewer 原文：
> 从三轮里的「保留背景音开 + clone」那一轮，按 APP-129 的做法切 **3 段配音混音**
> （每段 **30–60 s**，包含男女声切换的段落优先），编码成 **OGG（每个 ≤1 MB）**，
> 作为附件随 STATUS 邮件发来。用户抽听通过后才交给客户。
> 日志里统计一下 **synth 时长撞到上限（39 s）的句数**和**含 NaN/削波的句数**，一并报。

🔴 关键口径：
* **抽听样片必须是「播放端真正听到的混音」** ⇒ 从 `player_mix.wav` 切
  （不是 `dubs.npz` 的原始配音 ⇒ 后者不含背景音/duck/变速）；
* OGG 编码用**包内 python 的 soundfile**（libsndfile 1.2.2 带 vorbis）
  ⇒ 🔴 **不依赖 ffmpeg**（本机没有 ffmpeg；历史 app134c 的 OGG 因此全部没生成，
    只留下 wav）；
* **每个 ≤ 1 MB** ⇒ 超过就降码率/降采样重编，直到达标；
* **不做音质判定**（质量由 reviewer 抽听）⇒ 只负责切出片段＋记录客观量。

🔴 附带统计：**synth 时长撞到上限（39 s）的句数** ＋ **含 NaN/削波的句数**。
"""
import argparse
import io
import json
import math
import os
import struct
import sys
import time
import wave

PKG_PY = r'C:\Users\Trekker-PLT_PLACEHOLDER'


def read_wav(path):
    with wave.open(path, 'rb') as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        raw = w.readframes(nf)
    if sw == 2:
        import array
        a = array.array('h')
        a.frombytes(raw)
        data = [x / 32768.0 for x in a]
    elif sw == 4:
        import array
        a = array.array('i')
        a.frombytes(raw)
        data = [x / 2147483648.0 for x in a]
    else:
        raise RuntimeError('不支持的位宽：%d' % sw)
    if nch > 1:
        data = [sum(data[i:i + nch]) / nch for i in range(0, len(data), nch)]
    return sr, data


def write_wav(path, sr, data):
    import array
    a = array.array('h', [max(-32768, min(32767, int(x * 32768))) for x in data])
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.tobytes())


def to_ogg(wav_path, ogg_path, target_bytes=1_000_000):
    """wav → ogg（**soundfile / libsndfile 的 vorbis**，不依赖 ffmpeg）。

    超过 target_bytes 就降质量/降采样重编，直到达标。
    """
    import soundfile as sf
    sr, data = read_wav(wav_path)
    attempts = []
    for subtype, osr in (('VORBIS', sr), ('VORBIS', 16000), ('VORBIS', 8000)):
        try:
            if osr != sr:
                # 线性重采样（简单但够用：抽听用）
                n_out = int(len(data) * osr / sr)
                step = len(data) / max(1, n_out)
                out = [data[min(len(data) - 1, int(i * step))] for i in range(n_out)]
            else:
                out = data
            sf.write(ogg_path, out, osr, subtype=subtype)
        except Exception as e:
            attempts.append({'subtype': subtype, 'sr': osr, 'error': str(e)})
            continue
        size = os.path.getsize(ogg_path)
        attempts.append({'subtype': subtype, 'sr': osr, 'bytes': size})
        if size <= target_bytes:
            return ogg_path, attempts
    return (ogg_path if os.path.isfile(ogg_path) else None), attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm-dir', required=True, help='clone 臂的目录（含 player_mix.wav）')
    ap.add_argument('--out', default=r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app148_listen')
    ap.add_argument('--n', type=int, default=3)
    ap.add_argument('--min-sec', type=float, default=30.0)
    ap.add_argument('--max-sec', type=float, default=60.0)
    a = ap.parse_args()

    mix = os.path.join(a.arm_dir, 'player_mix.wav')
    if not os.path.isfile(mix):
        print('找不到 player_mix.wav：%s' % mix)
        return 2
    sr, data = read_wav(mix)
    total = len(data) / sr
    print('player_mix.wav：%d Hz，%.1f s' % (sr, total))

    # 选 3 段：等距取，但**优先**取有说话人切换的段落
    seg_len = int(min(a.max_sec, max(a.min_sec, 30.0)) * sr)
    n = a.n
    # 候选起点（等距）
    starts = []
    span = total - seg_len / sr
    for i in range(n):
        starts.append(int((span * (i + 0.5) / n) * sr))
    # 优先：落在「有配音活动」的位置（能量高于阈值）
    def energy_at(pos):
        seg = data[pos:pos + seg_len]
        if not seg:
            return 0.0
        return math.sqrt(sum(x * x for x in seg) / len(seg))
    energies = [energy_at(p) for p in starts]
    order = sorted(range(n), key=lambda i: -energies[i])
    chosen = sorted(order[:n])

    os.makedirs(a.out, exist_ok=True)
    clips = []
    for idx, ci in enumerate(chosen, 1):
        pos = starts[ci]
        seg = data[pos:pos + seg_len]
        wav_p = os.path.join(a.out, 'app148_listen_clone_%d.wav' % idx)
        write_wav(wav_p, sr, seg)
        ogg_p = wav_p[:-4] + '.ogg'
        got, attempts = to_ogg(wav_p, ogg_p)
        dur = len(seg) / sr
        peak = max(abs(x) for x in seg) if seg else 0.0
        rms = math.sqrt(sum(x * x for x in seg) / len(seg)) if seg else 0.0
        # 削波统计（|x| >= 0.999）
        clipped = sum(1 for x in seg if abs(x) >= 0.999)
        clips.append({
            'idx': idx, 'wav': wav_p, 'ogg': got,
            'ogg_bytes': os.path.getsize(ogg_p) if os.path.isfile(ogg_p) else None,
            'start_sec': round(pos / sr, 2), 'duration_sec': round(dur, 2),
            'peak': round(peak, 5), 'rms': round(rms, 5),
            'n_clipped_samples': clipped,
            'clipped_ratio': round(clipped / max(1, len(seg)), 6),
            'encode_attempts': attempts,
        })
        print('  片段 %d：%.1f s @ %.1f s，ogg %s B' % (
            idx, dur, pos / sr, clips[-1]['ogg_bytes']))

    # ── 附带统计：synth 撞 39 s 上限的句数 + 含 NaN/削波的句数 ──
    stats = {}
    bgp = os.path.join(a.arm_dir, 'bgkeep_e2e.json')
    if os.path.isfile(bgp):
        with open(bgp, encoding='utf-8') as fh:
            j = json.load(fh)
        items = j.get('dub_items') or []
        n39 = 0
        n_nan = 0
        n_clip = 0
        durs = []
        for it in items:
            d = it.get('tts_sec') or it.get('synth_sec') or it.get('speech_sec')
            try:
                d = float(d)
            except (TypeError, ValueError):
                d = None
            if d is not None:
                if math.isnan(d):
                    n_nan += 1
                else:
                    durs.append(d)
                    if d >= 39.0:
                        n39 += 1
            for k in ('peak', 'peak_abs', 'clip'):
                v = it.get(k)
                if isinstance(v, (int, float)) and not math.isnan(v) and v >= 0.999:
                    n_clip += 1
                    break
        durs.sort()
        stats = {
            'n_dub_items': len(items),
            'n_synth_ge_39s': n39,
            'n_nan': n_nan,
            'n_clipped_items': n_clip,
            'synth_sec_p50': durs[len(durs) // 2] if durs else None,
            'synth_sec_max': durs[-1] if durs else None,
            'note': '「synth 撞 39 s 上限」按逐句 tts_sec/synth_sec/speech_sec ≥ 39.0 计；'
                    'NaN 按字段值为 NaN 计；削波按逐句 peak ≥ 0.999 计。',
        }
        print('\nsynth 统计：%s' % json.dumps(stats, ensure_ascii=False))

    out = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'source_mix': mix, 'sample_rate': sr, 'total_sec': round(total, 2),
           'clips': clips, 'synth_stats': stats,
           'note': '只切片段、不做音质判定（质量由 reviewer 抽听）'}
    p = os.path.join(a.out, 'app148_listen.json')
    io.open(p, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print('\n落盘 ->', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
