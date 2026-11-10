"""APP-089 §4：**x-vector 归属判据的对照组**（证明判据本身有效）。

🔴 为什么必须有对照组（MEMORY §四铁律：「PASS ≠ 正确」）：
  归属率低，可能是**判据坏了**，也可能是**真的克隆得不好**
  ⇒ 必须先证明判据在**已知正确**的样本上能识破：
  ① **对照 A（源人声）**：把**源音频里该段的真人原声**算 x-vector，
     与三个真值参考比 ⇒ 应当**几乎全对**（这是判据的**上界**）。
     ⇒ 若 A 也不对 ⇒ 判据/映射坏了 ⇒ 归属率数字**不可用**。
  ② **对照 B（预设 A 音色）**：用**预设 A** 的 x-vector 去比
     ⇒ 应当**几乎全错**（克隆音色 ≠ 预设 A ⇒ 反证成立）。

🔴 结论口径：
  * 对照 A 接近 100 % ⇒ 判据有效 ⇒ after 臂的归属率**就是真实质量**。
  * 对照 B 接近 0 % ⇒ 反证识破 ⇒ 判据不是恒真。

用法：python app374_app089_voice_attr_control.py --arm after --material dialog3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave

import numpy as np

BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'
TRUTH = {'dialog3': 'truth.json', 'dialog3_tight': 'truth_tight.json'}
WAVNAME = {'dialog3': 'dialog3.wav', 'dialog3_tight': 'dialog3_tight.wav'}


def read_wav(path):
    w = wave.open(path, 'rb')
    try:
        n, ch, sw, sr = (w.getnframes(), w.getnchannels(),
                         w.getsampwidth(), w.getframerate())
        raw = w.readframes(n)
    finally:
        w.close()
    if sw == 2:
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        a = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


def cos(a, b):
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_rows(p):
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, encoding='utf-8', errors='replace'):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--material', default='dialog3')
    ap.add_argument('--out', default=None)
    ap.add_argument('--sub', default=None,
                    help='runs 下的子目录名（默认 = 素材名；阈值臂用 <素材>_thr<N>）')
    ap.add_argument('--runs', default=None,
                    help='runs 根目录名（默认 runs2；本轮用 runs3）')
    args = ap.parse_args()
    if args.runs:
        os.environ['APP_RUNS_ROOT'] = args.runs
    mat = args.material
    run = os.path.join(BASE, os.environ.get('APP_RUNS_ROOT', 'runs2'),
                     args.arm, args.sub or mat)

    import importlib
    shadow_app = os.path.join(BASE, args.arm, 'app')
    sys.path.insert(0, shadow_app)
    tts_engine = importlib.import_module('tts_engine')

    eng = None
    for dev in ('NPU', 'GPU.0'):
        try:
            eng = tts_engine.make_engine(
                dev, model_path=os.path.join(shadow_app, '..', 'models', 'qwen3tts'),
                cache_dir=os.path.join(shadow_app, '..', 'models', 'qwen3tts'),
                on_log=lambda m: None, precision='f16')
            break
        except Exception as e:
            print('engine %s 失败：%s' % (dev, e))
            eng = None
    if eng is None:
        raise RuntimeError('无法建 engine')

    def embed_pcm(pcm, sr):
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                w = wave.open(f.name, 'wb')
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
                w.close()
                v = tts_engine.speaker_embedding(eng, f.name, on_log=lambda m: None)
            try:
                os.remove(f.name)
            except Exception:
                pass
            return v
        except Exception as e:
            print('embed 失败：%s' % e)
            return None

    truth = json.load(open(os.path.join(SPKTEST, TRUTH[mat]), encoding='utf-8'))
    src, sr = read_wav(os.path.join(SPKTEST, WAVNAME[mat]))

    # ── 真值参考 ──
    by_spk = {}
    for t0, t1, spk in truth:
        by_spk.setdefault(spk, []).append((t0, t1))
    ref_vecs = {}
    for spk, spans in by_spk.items():
        chunks = []
        for t0, t1 in spans:
            i0, i1 = int(t0 * sr), int(t1 * sr)
            chunks.append(src[i0:i1])
        pcm = np.concatenate(chunks)
        v = embed_pcm(pcm, sr) if len(pcm) >= int(1.5 * sr) else None
        if v is not None:
            ref_vecs[spk] = v

    def truth_spk_of(t0, t1):
        best, bo = None, 0.0
        for a, b, spk in truth:
            ov = min(b, t1) - max(a, t0)
            if ov > bo:
                best, bo = spk, ov
        return best

    # ── 对照 A：源人声（该段真人原声）──
    segs = load_rows(os.path.join(run, 'spk_seg.jsonl'))
    nA = mA = 0
    for s in segs:
        if s.get('t0') is None or s.get('t1') is None:
            continue
        a, b = float(s['t0']), float(s['t1'])
        if (b - a) < 1.0:
            continue
        v = embed_pcm(src[int(a * sr):int(b * sr)], sr)
        if v is None:
            continue
        sims = {k: cos(v, rv) for k, rv in ref_vecs.items()}
        pred = max(sims.items(), key=lambda kv: kv[1])[0]
        t_spk = truth_spk_of(a, b)
        nA += 1
        if pred == t_spk:
            mA += 1

    # ── 对照 B：预设 A 音色（反证）──
    preset = os.path.join(shadow_app, '..', 'models', 'qwen3tts', 'voices', 'preset_A.wav')
    pv = None
    if os.path.exists(preset):
        pv = tts_engine.speaker_embedding(eng, preset, on_log=lambda m: None)
    nB = mB = 0
    if pv is not None:
        for s in segs:
            if s.get('t0') is None or s.get('t1') is None:
                continue
            a, b = float(s['t0']), float(s['t1'])
            sims = {k: cos(pv, rv) for k, rv in ref_vecs.items()}
            pred = max(sims.items(), key=lambda kv: kv[1])[0]
            nB += 1
            if pred == truth_spk_of(a, b):
                mB += 1

    res = {
        'arm': args.arm, 'material': mat, 'run_dir': run,
        'control_A_source_human': {
            'n': nA, 'n_match': mA,
            'match_rate': round(mA / nA, 4) if nA else None,
            'note': ('对照组 A＝**源人声**（已知正确）⇒ 应当接近 1.0 '
                     '⇒ 低于此值说明判据/映射有问题'),
        },
        'control_B_preset_A': {
            'n': nB, 'n_match': mB,
            'match_rate': round(mB / nB, 4) if nB else None,
            'preset_wav': preset if os.path.exists(preset) else None,
            'note': ('对照组 B＝**预设 A 音色**（反证：克隆音色 ≠ 预设 A）'
                     '⇒ 应当接近 0 ⇒ 高于此值说明判据恒真'),
        },
        'src': {'truth': os.path.join(SPKTEST, TRUTH[mat]),
                'spk_seg_jsonl': os.path.join(run, 'spk_seg.jsonl')},
    }
    out_p = args.out or os.path.join(
        EVID, 'app374_app089_voice_ctrl_%s_%s.json' % (args.arm, mat))
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print('OUT=%s' % out_p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
