"""APP-089 §4：**配音音色归属**验收（x-vector 余弦）。

🔴 reviewer 要求（APP-089 §4，每份素材都要报）：
  > 配音音色最接近正确说话人的占比（用 x-vector 余弦，把输出和三个人的真值参考比较）

🔴 做法：
  ① **真值参考**：从**源音频**按 `truth.json` 的三人时间段切出参考片段
     ⇒ 用 App **自己的** speaker encoder（`tts_engine.speaker_embedding`）
        算 x-vector（**与 App 运行时同一口径** ⇒ 可比）。
  ② **输出**：从 `dump/seg_*_*.wav`（逐句配音）算 x-vector。
  ③ 逐句：取输出 x-vector 与三个真值参考的余弦 ⇒ **argmax = 该句听起来是谁**
     ⇒ 与该句的**真值说话人**（按段号 → 时间 → truth）比 ⇒ 判对/错。
  ④ 输出：占比 + 混淆矩阵 + 逐句明细（落盘 json）。

🔴 铁律：**x-vector 只用于 ASR 内部聚类**（ASR-026/§50）⇒ 本脚本是
   **离线验收**，不改变 App 运行时行为；结果**不落盘用户声纹**。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave

import numpy as np

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = os.path.join(REPO, 'results', 'app')

TRUTH = {'dialog3': 'truth.json', 'dialog3_tight': 'truth_tight.json'}


def read_wav(path):
    w = wave.open(path, 'rb')
    try:
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
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


def slice_wav(a, sr, t0, t1):
    i0 = max(0, int(t0 * sr))
    i1 = min(len(a), int(t1 * sr))
    return a[i0:i1]


def cos(a, b):
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_rows(p):
    rows = []
    if not os.path.exists(p):
        return rows
    for line in open(p, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def pct(vals, q):
    """线性插值分位数（与 app370 同一口径）。"""
    if not vals:
        return None
    vs = sorted(vals)
    if len(vs) == 1:
        return round(vs[0], 4)
    k = (len(vs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vs) - 1)
    return round(vs[lo] + (vs[hi] - vs[lo]) * (k - lo), 4)


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

    # 🔴🔴 **必须用影子包 `app/` 里的模块**（不是开发树）：
    #   `tts_engine.PKG_ROOT = dirname(dirname(__file__))`
    #   ⇒ 开发树那份算出来是 `confucius4-openvino/` ⇒ **找不到 models/**
    #   ⇒ 必须让 `tts_engine` 从**影子包的 app/** 导入 ⇒ PKG_ROOT 才对。
    import importlib
    shadow_app = os.path.join(BASE, args.arm, 'app')
    sys.path.insert(0, shadow_app)
    tts_engine = importlib.import_module('tts_engine')
    print('tts_engine 来自：%s' % getattr(tts_engine, '__file__', '?'))
    print('PKG_ROOT     ：%s' % getattr(tts_engine, 'PKG_ROOT', '?'))

    # ── 建 engine（只要 extract_speaker_embedding）──
    # 🔴 `tts_engine.make_engine(device, model_path, cache_dir, on_log, precision)`
    #   ⇒ **第一个位置参数就是 device**（不是 key）⇒ 别按 ASR 的 `make_backend` 用。
    # 🔴 **模型路径**：开发树没有模型 ⇒ 用**影子包**的 `models/`（联接真包）
    #   ⇒ 与 App 运行时**同一份 IR** ⇒ x-vector 口径可比。
    import json as _json
    shadow = os.path.join(BASE, args.arm)
    model_path = os.path.join(shadow, 'models', 'qwen3tts')
    if not os.path.isdir(model_path):
        model_path = os.path.join(shadow, 'models')

    eng = None
    for dev, prec in (('NPU', 'f16'), ('GPU.0', 'f16')):
        try:
            eng = tts_engine.make_engine(
                dev, model_path=model_path,
                cache_dir=os.path.join(shadow, 'models', 'qwen3tts'),
                on_log=lambda m: None, precision=prec)
            break
        except Exception as e:
            print('engine %s 失败：%s' % (dev, e))
            eng = None
    if eng is None:
        raise RuntimeError('无法建 engine')

    def embed_pcm(pcm, sr):
        try:
            import io
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                w = wave.open(f.name, 'wb')
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
                w.close()
                v = tts_engine.speaker_embedding(eng, f.name,
                                                 on_log=lambda m: None)
            try:
                os.remove(f.name)
            except Exception:
                pass
            return v
        except Exception as e:
            print('embed 失败：%s' % e)
            return None

    # ── ① 真值参考（三人）──
    truth = json.load(open(os.path.join(SPKTEST, TRUTH[mat]), encoding='utf-8'))
    src, sr = read_wav(os.path.join(SPKTEST, mat.replace('dialog3', 'dialog3') + '.wav'
                                    if mat == 'dialog3' else 'dialog3_tight.wav'))
    # 每个真值说话人：把所有属于他的片段首尾拼起来（≥1.5 s 才够提 x-vector）
    by_spk = {}
    for t0, t1, spk in truth:
        by_spk.setdefault(spk, []).append((t0, t1))
    refs = {}
    for spk, spans in by_spk.items():
        chunks = []
        for t0, t1 in spans:
            chunks.append(slice_wav(src, sr, t0, t1))
        pcm = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
        v = embed_pcm(pcm, sr) if len(pcm) >= int(1.5 * sr) else None
        refs[spk] = {'vec': v, 'dur_s': round(len(pcm) / sr, 2)}
        print('真值参考 %s: dur=%.1fs vec=%s' % (spk, len(pcm) / sr,
                                                'None' if v is None else np.shape(v)))
    ref_vecs = {k: v['vec'] for k, v in refs.items() if v['vec'] is not None}
    if not ref_vecs:
        raise RuntimeError('真值参考全失败')

    # ── ② 输出侧：段表 + 逐句 dump wav ──
    segs = load_rows(os.path.join(run, 'spk_seg.jsonl'))
    rows = load_rows(os.path.join(run, 'tts.jsonl'))
    seg_span = {int(s['seg']): (float(s['t0']), float(s['t1']))
                for s in segs if s.get('t0') is not None}
    # seg → 真值说话人（按时间重叠最大）
    def truth_spk_of_seg(seg):
        if seg not in seg_span:
            return None
        a, b = seg_span[seg]
        best, best_ov = None, 0.0
        for t0, t1, spk in truth:
            ov = min(b, t1) - max(a, t0)
            if ov > best_ov:
                best, best_ov = spk, ov
        return best

    # dump wav：文件名含 seg 号 ⇒ seg_5_0007.wav
    dump = {}
    ddir = os.path.join(run, 'dump')
    if os.path.isdir(ddir):
        for f in os.listdir(ddir):
            if not f.endswith('.wav') or '_acc' in f:
                continue
            try:
                seg = int(f.split('_')[1])
            except Exception:
                continue
            dump.setdefault(seg, os.path.join(ddir, f))

    detail = []
    n_ok = 0
    n_match = 0
    conf = {}
    # 🔴🔴 **按 seg 打分，不按 jsonl 行打分**：
    #   一个 seg 可能对应**多行** jsonl（如 seg1 出现两次：jid0/jid1）
    #   ⇒ 若按行打分会**同一段被算两次**（且只用到第一行的 dump）
    #   ⇒ 归属率的分母必须是「**段数**」⇒ 按 seg 去重。
    _seen_seg = set()
    # 🔴🔴 **基线**：**多数类**（永远猜 truth 里段数最多的那个人）
    #   ⇒ 判据的**下界**（比它还低 ⇒ 判据没区分力）
    #   ⚠️ 必须报出来，否则「归属率 34.7 %」这种数字**无法解读**。
    _maj = {}
    for _s in segs:
        if _s.get('t0') is None or _s.get('t1') is None:
            continue
        _a, _b = float(_s['t0']), float(_s['t1'])
        _best, _bo = None, 0.0
        for _t0, _t1, _tspk in truth:
            _ov = min(_b, _t1) - max(_a, _t0)
            if _ov > _bo:
                _best, _bo = _tspk, _ov
        if _best:
            _maj[_best] = _maj.get(_best, 0) + 1
    _maj_total = sum(_maj.values())
    baseline_majority = (round(max(_maj.values()) / _maj_total, 4)
                         if _maj_total else None)
    for r in rows:
        if r.get('late_drop') or r.get('error'):
            continue
        seg = r.get('seg')
        if seg is None or seg not in dump:
            continue
        if int(seg) in _seen_seg:
            continue           # 🔴 同一 seg 只算一次
        _seen_seg.add(int(seg))
        pcm, psr = read_wav(dump[seg])
        if len(pcm) < int(0.3 * psr):
            continue
        v = embed_pcm(pcm, psr)
        if v is None:
            continue
        sims = {k: cos(v, rv) for k, rv in ref_vecs.items()}
        pred = max(sims.items(), key=lambda kv: kv[1])[0]
        t_spk = truth_spk_of_seg(seg)
        n_ok += 1
        ok = (pred == t_spk)
        if ok:
            n_match += 1
        conf[(t_spk, pred)] = conf.get((t_spk, pred), 0) + 1
        # 🔴🔴 **更严的第二口径**：拿**这一段自己的源人声**当参考
        #   （而不是三个人各自的**全局平均**向量）
        #   ⇒ 判据＝「输出的音色最接近**本段原声**」⇒ 更有区分力
        #   ⚠️ 源人声 vs **合成中文** 存在**域差**（合成声的 x-vector 本就偏移）
        #      ⇒ 这个口径**更严**，两个口径一起报最稳妥。
        seg_cos = None
        if seg in seg_span:
            a, b = seg_span[seg]
            sv = embed_pcm(src[int(a * sr):int(b * sr)], sr)
            if sv is not None:
                seg_cos = round(cos(v, sv), 4)
        detail.append({'seg': seg, 'truth_spk': t_spk, 'pred_spk': pred,
                       'ok': bool(ok),
                       'cos': {k: round(x, 4) for k, x in sims.items()},
                       'cos_to_own_source': seg_cos,
                       'dump': dump[seg]})

    res = {
        'arm': args.arm, 'material': mat, 'run_dir': run,
        'n_scored': n_ok,
        'n_match': n_match,
        'match_rate': round(n_match / n_ok, 4) if n_ok else None,
        'baseline_majority_class': baseline_majority,
        'baseline_note': ('基线＝永远猜「truth 里段数最多的那个人」'
                          '⇒ 归属率必须**明显高于**它才有意义'),
        # ── 更严口径：输出 vs **本段源人声** 的余弦 ──
        'cos_to_own_source_p50': pct([d['cos_to_own_source'] for d in detail
                                       if d.get('cos_to_own_source') is not None], 0.50),
        'cos_to_own_source_p90': pct([d['cos_to_own_source'] for d in detail
                                       if d.get('cos_to_own_source') is not None], 0.90),
        'cos_to_own_source_min': (round(min([d['cos_to_own_source'] for d in detail
                                             if d.get('cos_to_own_source') is not None]), 4)
                                  if any(d.get('cos_to_own_source') is not None
                                         for d in detail) else None),
        'truth_refs': {k: {'dur_s': v['dur_s'],
                           'vec_shape': (list(np.shape(v['vec']))
                                         if v['vec'] is not None else None)}
                       for k, v in refs.items()},
        'confusion': {'%s->%s' % k: v for k, v in sorted(
            conf.items(), key=lambda kv: str(kv[0]))},
        'detail': detail,
        'src': {'truth': os.path.join(SPKTEST, TRUTH[mat]),
                'spk_seg_jsonl': os.path.join(run, 'spk_seg.jsonl'),
                'tts_jsonl': os.path.join(run, 'tts.jsonl'),
                'dump_dir': ddir},
    }
    out_p = args.out or os.path.join(
        EVID, 'app373_app089_voice_attr_%s_%s.json' % (args.arm, mat))
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'detail'},
                     ensure_ascii=False, indent=1))
    print('OUT=%s' % out_p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
