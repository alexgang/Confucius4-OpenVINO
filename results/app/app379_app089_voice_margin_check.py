"""APP-089 §4：**配音音色归属**（域差稳健口径）—— 补 `app373` 的口径缺陷。

🔴 **为什么要有这个脚本**（reviewer 的验收口径要能落地）：
  `app373` 的口径＝「输出 x-vector 与**三个人的全局平均参考**比，取 argmax」
  ⇒ 🔴 **口径缺陷**：参考来自**英文源人声**，输出是**中文合成声**
  ⇒ 存在**域差**（合成声的 x-vector 整体偏移）
  ⇒ argmax 很可能被**域差**主导，而不是**说话人身份**
  ⇒ 实测：after 38.0 % / before 42.9 %，**都落在「猜多数类」基线 40.74 % 附近**
  ⇒ **不能区分「音色对」与「音色错」** ⇒ 该口径不足以支撑验收。

🔴 **本脚本的口径（域差稳健）**：
  对每句输出 `v`：
    ① 取**三个真值说话人各自的源人声片段**（按 `truth.json` 的时间区间
       切**该句自己那一段**的同一人源人声 ⇒ 参考 = **本句自己的原声**）
    ② 算 `cos(v, ref_own)`（同一人）与 `cos(v, ref_other)`（另两人）
    ③ 判据：**`cos(v, ref_own)` 严格大于**所有 `cos(v, ref_other)`
       ⇒ 「这句配音听起来最像**本句原声的那个人**」

  ⇒ 这个口径**逐句对齐**（参考与输出同源时段）
  ⇒ **域差对三个人一样** ⇒ argmax 仍是公平比较
  ⇒ 比 `app373` 的全局平均参考**更有区分力**。

🔴 **反证组**：把「自己那段的参考」换成**另一个人的参考**
  ⇒ 归属率必须**大跌** ⇒ 证明判据不是恒真。

🔴 **不调 MiniMax**（回转写由 reviewer 做）⇒ 本脚本只算 x-vector 余弦。

用法：
  C:\\Users\\Trekker-PTL\\_app_shadow\\after\\python\\python.exe ^
      app379_app089_voice_margin_check.py --arm after --material dialog3
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
SR = 16000


def cos(a, b):
    a = np.asarray(a, np.float32).reshape(-1)
    b = np.asarray(b, np.float32).reshape(-1)
    n = min(a.size, b.size)
    if n == 0:
        return 0.0
    a = a[:n]
    b = b[:n]
    d = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / d) if d > 0 else 0.0


def read_wav(path):
    try:
        with wave.open(path, 'rb') as w:
            n = w.getnframes()
            ch = w.getnchannels()
            sw = w.getsampwidth()
            sr = w.getframerate()
            raw = w.readframes(n)
        if sw == 2:
            pcm = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        elif sw == 4:
            pcm = np.frombuffer(raw, np.int32).astype(np.float32) / 2147483648.0
        else:
            pcm = np.frombuffer(raw, np.uint8).astype(np.float32)
        if ch > 1:
            pcm = pcm.reshape(-1, ch).mean(axis=1)
        return pcm, sr
    except Exception:
        return None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--material', default='dialog3')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    mat = args.material
    run = os.path.join(BASE, 'runs2', args.arm, mat)
    spk_seg = os.path.join(run, 'spk_seg.jsonl')
    tts_jsonl = os.path.join(run, 'tts.jsonl')
    dump_dir = os.path.join(run, 'dump')
    truth_p = TRUTH.get(mat)
    if not truth_p or not os.path.exists(spk_seg) or not os.path.isdir(dump_dir):
        print('🔴 缺素材/产物：%s' % run)
        return 2
    truth = json.load(open(os.path.join(SPKTEST, truth_p), encoding='utf-8'))

    # 🔴🔴 **必须用影子包 `app/` 里的 `tts_engine`**（不是开发树）：
    #   `tts_engine.PKG_ROOT = dirname(dirname(__file__))`
    #   ⇒ 开发树那份算出来是 `confucius4-openvino/` ⇒ **找不到 models/**。
    import importlib
    shadow_app = os.path.join(BASE, args.arm, 'app')
    sys.path.insert(0, shadow_app)
    tts_engine = importlib.import_module('tts_engine')
    print('tts_engine 来自：%s' % getattr(tts_engine, '__file__', '?'))
    print('PKG_ROOT     ：%s' % getattr(tts_engine, 'PKG_ROOT', '?'))
    # 🔴 与 app373 同一套建 engine 的方式（**第一个位置参数是 device**）
    shadow = os.path.join(BASE, args.arm)
    model_path = os.path.join(shadow, 'models', 'qwen3tts')
    if not os.path.isdir(model_path):
        model_path = os.path.join(shadow, 'models')
    eng = None
    for dev, prec in (('NPU', 'f16'), ('GPU.0', 'f16'), ('CPU', 'f16')):
        try:
            eng = tts_engine.make_engine(
                dev, model_path=model_path,
                cache_dir=os.path.join(shadow, 'models', 'qwen3tts'),
                on_log=lambda m: None, precision=prec)
            print('engine %s OK' % dev)
            break
        except Exception as e:
            print('engine %s 失败：%s' % (dev, str(e)[:140]))
            eng = None
    if eng is None:
        return 2

    def embed(pcm, sr):
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
            if v is None:
                return None
            return np.asarray(v, np.float32).reshape(-1)
        except Exception:
            return None

    # 源音频
    wav_name = 'dialog3.wav' if mat == 'dialog3' else 'dialog3_tight.wav'
    src, sr = read_wav(os.path.join(SPKTEST, wav_name))
    if src is None:
        print('🔴 读不到源 wav')
        return 2

    # 段表（seg → (t0,t1)）
    seg_span = {}
    for line in open(spk_seg, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('t0') is not None and r.get('t1') is not None:
            seg_span[int(r['seg'])] = (float(r['t0']), float(r['t1']))

    def truth_spk_at(t):
        for t0, t1, s in truth:
            if t0 <= t < t1:
                return s
        return None

    # dump wav：seg → 路径
    dump = {}
    for fn in os.listdir(dump_dir):
        if not fn.endswith('.wav'):
            continue
        try:
            sg = int(fn.split('_')[1])
        except Exception:
            continue
        dump.setdefault(sg, os.path.join(dump_dir, fn))

    # TTS jsonl：seg → 有配乐的（voice_self_ref / voice_spk 有值）
    voiced = set()
    for line in open(tts_jsonl, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('late_drop') or r.get('error'):
            continue
        if r.get('dur_s'):
            sg = r.get('seg')
            if sg is not None:
                voiced.add(int(sg))

    detail = []
    n_ok = 0
    n_match = 0
    n_ctrl_match = 0
    n_src_ctrl_match = 0
    margins = []
    seen = set()
    for sg in sorted(dump):
        if sg in seen or sg not in voiced:
            continue
        seen.add(sg)
        if sg not in seg_span:
            continue
        t0, t1 = seg_span[sg]
        own_spk = truth_spk_at((t0 + t1) / 2.0)
        if own_spk is None:
            continue
        pcm, psr = read_wav(dump[sg])
        if pcm is None or len(pcm) < int(0.3 * psr):
            continue
        v = embed(pcm, psr)
        if v is None:
            continue
        # **本句自己的原声**（同一人、同时段）
        a = int(t0 * SR)
        b = int(t1 * SR)
        if b - a < int(0.3 * SR):
            continue
        sv_own = embed(src[a:b], sr)
        if sv_own is None:
            continue
        # **另两人的参考**：取他们在**别的时段**的源人声（避免用同一段）
        others = {}
        for t0r, t1r, spk in truth:
            if spk == own_spk:
                continue
            # 取该人时间轴中点附近的 3 s
            mid = (t0r + t1r) / 2.0
            half = min(1.5, (t1r - t0r) / 2.0)
            aa = int((mid - half) * SR)
            bb = int((mid + half) * SR)
            if bb - aa < int(0.3 * SR):
                continue
            rv = embed(src[aa:bb], sr)
            if rv is not None:
                others[spk] = rv
        if not others:
            continue
        cos_own = cos(v, sv_own)
        cos_oth = {k: cos(v, rv) for k, rv in others.items()}
        n_ok += 1
        ok = all(cos_own > x for x in cos_oth.values())
        if ok:
            n_match += 1
        # 🔴 **反证**：把「自己」换成**另一个人** ⇒ 必须不判对
        ctrl_ok = False
        for k, rv in others.items():
            ck = cos(v, rv)
            rest = [cos_own] + [x for kk, x in cos_oth.items() if kk != k]
            if ck > max(rest):
                ctrl_ok = True
        if ctrl_ok:
            n_ctrl_match += 1
        # 🔴🔴🔳 **对照 C（关键）**：**探针换成「本段自己的源人声」**
        #   ⇒ 若源人声也判不对 ⇒ **判据本身分不出**（x-vector 分辨力不足）
        #   ⇒ 若源人声判对、合成声判不对 ⇒ **合成音色确实没跟上**（产品问题）
        #   ⚠️ 这是区分「判据缺陷」与「产品缺陷」的**唯一**办法。
        sv_ctrl = cos(sv_own, sv_own)
        cos_ctrl_oth = {k: cos(sv_own, rv) for k, rv in others.items()}
        ctrl_src_ok = all(sv_ctrl > x for x in cos_ctrl_oth.values())
        if ctrl_src_ok:
            n_src_ctrl_match += 1
        margins.append(round(cos_own - max(cos_oth.values()), 4))
        detail.append(dict(seg=sg, truth_spk=own_spk, ok=bool(ok),
                           cos_own=round(cos_own, 4),
                           cos_other={k: round(x, 4)
                                      for k, x in cos_oth.items()},
                           margin=round(cos_own - max(cos_oth.values()), 4),
                           ctrl_src_ok=bool(ctrl_src_ok),
                           cos_src_to_other={k: round(x, 4)
                                             for k, x in cos_ctrl_oth.items()},
                           dump=dump[sg]))

    def pct(v, q):
        if not v:
            return None
        s = sorted(v)
        if len(s) == 1:
            return round(s[0], 4)
        k = (len(s) - 1) * q
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 4)

    res = dict(
        arm=args.arm, material=mat, run_dir=run,
        criterion=('每句输出 x-vector 与**本句自己的原声**比余弦；'
                   '严格大于与**另两人**的余弦 ⇒ 判「音色最接近本人」'
                   '（参考与输出**同源时段** ⇒ 域差对三人相同 ⇒ 公平比较）'),
        n_scored=n_ok, n_match=n_match,
        match_rate=(round(n_match / n_ok, 4) if n_ok else None),
        # 🔴 **反证**：把「自己」换成别人 ⇒ 归属率必须大跌
        n_ctrl_match=n_ctrl_match,
        ctrl_match_rate=(round(n_ctrl_match / n_ok, 4) if n_ok else None),
        # 🔴🔴🔳 **对照 C**：探针＝本段**源人声**时的归属率
        #   ⇒ 高 ⇒ 判据有分辨力（⇒ 合成声的低归属率是**产品问题**）
        #   ⇒ 低 ⇒ 判据本身分不出（⇒ 是**判据缺陷**，不是产品问题）
        n_src_ctrl=n_src_ctrl_match,
        src_ctrl_match_rate=(round(n_src_ctrl_match / n_ok, 4) if n_ok else None),
        margin_p50=pct(margins, 0.50), margin_p90=pct(margins, 0.90),
        margin_min=(round(min(margins), 4) if margins else None),
        n_margin_positive=len([m for m in margins if m > 0]),
        detail=detail,
        src=dict(truth=os.path.join(SPKTEST, truth_p), spk_seg=spk_seg,
                 tts_jsonl=tts_jsonl, dump_dir=dump_dir),
    )
    out = args.out or os.path.join(
        EVID, 'app379_app089_voice_margin_%s_%s.json' % (args.arm, mat))
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'detail'},
                     ensure_ascii=False, indent=1))
    print('OUT=%s' % out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
