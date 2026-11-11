#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app445_app099_wespeaker_sep.py — APP-099 四.6(c)：§3.5 换成 wespeaker 判据后的「可分性」先报。

## reviewer APP-099 第 3 节裁定（原文要点）
> 「改用 wespeaker-resnet34（``qwen3asr_06b\models\wespeaker-resnet34-fp16``，
>   与旁路用的是同一个），对输出 wav 和 truth 的三人参考计算余弦。**先报可分性**：
>   三人参考两两余弦，以及**同一个人两段不同音频之间的余弦，后者要明显更高才算可分**。
>   如果 wespeaker 也分不开，就停下，由 reviewer 抽听。对照组 B（预设 A）要在
>   self_ref 闸门修好以后重跑。」

## 判据（纯序关系，**不自造阈值**）
* ``ref_pair_cosine``   ：三人参考（每人各段嵌入的均值向量）两两余弦，格式与 app329 对齐。
* ``same_spk_pairs``    ：同一说话人「两段不同音频」之间所有两两余弦。
* ``diff_spk_pairs``    ：不同说话人各取一段之间所有两两余弦。
* ``separable = min(same_spk_pairs) > max(diff_spk_pairs)``
  —— 只用大小关系，不引入任何可人为调节的阈值；「明显更高」由 reviewer 看数字裁定。
  ``False`` ⇒ 按裁定**停下，不做 before/after 与对照组 B 重跑**，交 reviewer 抽听。

## 反证组（判据写完必须先跑：确认不是恒真 / 恒假）
* ``swapped``：把「同人两段」的第二段换成**另一个人**的段 ⇒ 应判 ``separable=False``。
* ``random`` ：用随机单位向量代替嵌入 ⇒ 应判 ``separable=False``。
* ``identical``：两段用**同一段**向量 ⇒ 应判 ``separable=True``（阳性对照）。
  任一反证组没被识破 ⇒ 本脚本整体 ``pass=false``，数字不得写进 STATUS。

## 纪律
* 持 ``MACHINE_LOCK``（``machine_lock_app.acquire/release``，fail-closed），锁记录写进 json。
* 用**旁路同一个** IR 与同一个 ``WespeakerOVEncoder``（影子包运行时，只读不改）。
* 不调 MiniMax、不打包、不改任何默认值或判据；不写任何交付包目录。
* 只在 APP-099 第 4 节 1/2 的长作业结束后运行（避免大 I/O / 设备互抢污染计时）。

用法：
    .venv/Scripts/python.exe results/app/_app445_app099_wespeaker_sep.py
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, r'C:\Users\Trekker-PTL\_app_shadow\after2\app\asr_spk')

import machine_lock_app as ML  # noqa: E402
from asr052_spk_runtime import WespeakerOVEncoder  # noqa: E402

SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
TRUTH_JSON = os.path.join(SPKTEST, 'truth.json')
SRC_WAV = os.path.join(SPKTEST, 'dialog3.wav')
WES_IR = r'C:\Users\Trekker-PTL\qwen3asr_06b\models\wespeaker-resnet34-fp16'
DEVICE = 'GPU.0'
SR = 16000
MIN_DUR_S = 1.5          # 与 app373 一致；低于编译期下界 100 帧的段直接跳过
OUT = os.path.join(HERE, 'app445_app099_wespeaker_separability.json')
LEASE_TOKEN = 'b7a6c270'
LEASE_TOOL = r'C:\Users\Trekker-PTL\shared\tools\session_lease.py'


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def beat(msg):
    try:
        subprocess.run([sys.executable, LEASE_TOOL, 'beat', 'app', LEASE_TOKEN, msg],
                       capture_output=True, timeout=20)
    except Exception:
        pass


def read_wav(path):
    with wave.open(path, 'rb') as w:
        sr, sw, n = w.getframerate(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise RuntimeError('只支持 16-bit PCM：sampwidth=%d' % sw)
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if sr != SR:
        raise RuntimeError('需要 16 kHz，实际 %d Hz' % sr)
    return a


def unit(v):
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / (n + 1e-9)


def cos(a, b):
    return float(np.dot(unit(a), unit(b)))


def pair_stats(vals):
    s = sorted(float(x) for x in vals)
    if not s:
        return {'n': 0}
    return {
        'n': len(s),
        'min': round(s[0], 6),
        'p50': round(s[len(s) // 2], 6),
        'max': round(s[-1], 6),
    }


def separable(same_vals, diff_vals):
    """纯序关系判据：同人所有对的最小值 > 异人所有对的最大值。"""
    if not same_vals or not diff_vals:
        return False
    return bool(min(same_vals) > max(diff_vals))


def main():
    beat('APP-099 4.6c：wespeaker 可分性（准备持锁）')
    out = {
        'task': 'APP-099 四.6(c) / reviewer 第 3 节：§3.5 换 wespeaker 后的可分性',
        'created_at': now(),
        'criterion': 'separable = min(同人不同段两两余弦) > max(异人两两余弦)；纯序关系，无自造阈值',
        'source': {
            'truth': TRUTH_JSON,
            'src_wav': SRC_WAV,
            'wespeaker_ir': WES_IR,
            'encoder': r'C:\Users\Trekker-PTL\_app_shadow\after2\app\asr_spk\asr052_spk_runtime.py::WespeakerOVEncoder',
            'device': DEVICE,
            'sample_rate': SR,
            'min_dur_s': MIN_DUR_S,
            'note': 'IR 与编码器就是 ASR 说话人旁路用的那一份；只读取，不修改、不交付',
        },
        'lock': None,
    }

    ok, payload = ML.acquire(module='app', timeout=1800, poll=20)
    if not ok:
        out['pass'] = False
        out['error'] = 'MACHINE_LOCK 取不到（fail-closed，未抢锁）'
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('🔴 ' + out['error'], flush=True)
        return 1
    t_lock0 = now()
    out['lock'] = {'module': 'app', 'payload': payload, 'started': t_lock0,
                   'ended': None, 'pid': os.getpid()}
    print('[lock] 已取得：%s' % payload.replace('\n', ' | ')[:220], flush=True)

    try:
        truth = json.load(open(TRUTH_JSON, encoding='utf-8'))
        src = read_wav(SRC_WAV)
        print('[data] truth=%d 段，src=%.1f s' % (len(truth), len(src) / SR), flush=True)

        enc = WespeakerOVEncoder(WES_IR, DEVICE)
        print('[enc] IR 编译完成 device=%s runtime=%s' % (DEVICE, enc.runtime), flush=True)

        # 按 truth 切段并逐段嵌入（跳过过短/超界段，如实记数）
        segs = []
        skipped = []
        for idx, (t0, t1, spk) in enumerate(truth):
            a, b = int(t0 * SR), int(t1 * SR)
            pcm = src[a:b]
            dur = len(pcm) / SR
            if dur < MIN_DUR_S:
                skipped.append({'idx': idx, 'spk': spk, 'dur_s': round(dur, 3),
                                'reason': 'shorter_than_min_dur'})
                continue
            try:
                v = unit(enc.embed(pcm, SR))
            except Exception as e:
                skipped.append({'idx': idx, 'spk': spk, 'dur_s': round(dur, 3),
                                'reason': '%s: %s' % (type(e).__name__, str(e)[:120])})
                continue
            segs.append({'idx': idx, 'spk': spk, 't0': t0, 't1': t1,
                         'dur_s': round(dur, 3), 'vec': v})
        by_spk = {}
        for s in segs:
            by_spk.setdefault(s['spk'], []).append(s)
        out['data'] = {
            'n_truth': len(truth), 'n_embedded': len(segs), 'n_skipped': len(skipped),
            'per_spk': {k: len(v) for k, v in sorted(by_spk.items())},
            'skipped': skipped[:20],
            'src_seconds': round(len(src) / SR, 2),
        }
        print('[data] 嵌入 %d 段，跳过 %d 段，per_spk=%s' %
              (len(segs), len(skipped), out['data']['per_spk']), flush=True)

        if len(by_spk) < 3 or any(len(v) < 2 for v in by_spk.values()):
            raise RuntimeError('三人里有人可用段 < 2，无法做「同人两段」判据')

        # ① 三人参考：每人各段单位向量的均值，再归一化
        refs = {k: unit(np.mean([s['vec'] for s in v], axis=0))
                for k, v in by_spk.items()}
        ref_pair = {}
        ks = sorted(refs)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                ref_pair['%s-%s' % (ks[i], ks[j])] = round(cos(refs[ks[i]], refs[ks[j]]), 6)

        # ② 同人不同段 / ③ 异人各一段
        same_vals, diff_vals = [], []
        same_detail, diff_detail = [], []
        for k, v in by_spk.items():
            for i in range(len(v)):
                for j in range(i + 1, len(v)):
                    c = cos(v[i]['vec'], v[j]['vec'])
                    same_vals.append(c)
                    same_detail.append({'spk': k, 'a': v[i]['idx'], 'b': v[j]['idx'],
                                        'cos': round(c, 6)})
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                for x in by_spk[ks[i]]:
                    for y in by_spk[ks[j]]:
                        c = cos(x['vec'], y['vec'])
                        diff_vals.append(c)
                        diff_detail.append({'a_spk': ks[i], 'b_spk': ks[j],
                                            'a': x['idx'], 'b': y['idx'], 'cos': round(c, 6)})

        sep = separable(same_vals, diff_vals)
        out['separability'] = {
            'ref_pair_cosine': ref_pair,
            'same_spk_pairs': pair_stats(same_vals),
            'diff_spk_pairs': pair_stats(diff_vals),
            'gap_median_minus_diff_max': round(
                float(np.median(same_vals)) - max(diff_vals), 6),
            'separable': sep,
            'same_pairs_detail': same_detail[:12],
            'diff_pairs_detail': diff_detail[:12],
            'n_same_pairs': len(same_vals),
            'n_diff_pairs': len(diff_vals),
        }

        # ④ 反证组：判据必须能识破「同人」被换成「异人」/随机向量
        rng = np.random.default_rng(20261111)
        neg = {}
        swapped = []
        for k, v in by_spk.items():
            others = [s for kk, vv in by_spk.items() if kk != k for s in vv]
            for i in range(min(len(v), 8)):
                swapped.append(cos(v[i]['vec'], others[i % len(others)]['vec']))
        neg['swapped'] = {
            'detected': (not separable(swapped, diff_vals)),
            'expect_separable': False,
            'got_separable': separable(swapped, diff_vals),
            'note': '把「同人两段」的第二段换成别人的段 ⇒ 判据应判不可分',
        }
        # 🔴 用「确定的不可分构造」做反证，不用随机向量（随机余弦偶尔
        #    会让 min(same) > max(diff) 偶然成立 ⇒ 假 FAIL）。
        neg['diff_as_same'] = {
            'detected': (not separable(diff_vals, diff_vals)),
            'expect_separable': False,
            'got_separable': separable(diff_vals, diff_vals),
            'note': '把异人对冒充同人对 ⇒ min(same) > max(diff) 恒不成立 ⇒ 判据非恒真',
        }
        rnd = [unit(rng.normal(size=256)) for _ in range(12)]
        rnd_same = [cos(rnd[i], rnd[i + 6]) for i in range(6)]
        rnd_diff = [cos(rnd[i], rnd[j]) for i in range(0, 12, 2) for j in range(1, 12, 2)]
        neg['random'] = {
            'detected': (not separable(rnd_same, rnd_diff)),
            'expect_separable': False,
            'got_separable': separable(rnd_same, rnd_diff),
            'note': '随机单位向量 ⇒ 判据应判不可分（辅助，不单独决定 pass）',
        }
        ident_same = [1.0] * 6
        neg['identical'] = {
            'detected': separable(ident_same, diff_vals),
            'expect_separable': True,
            'got_separable': separable(ident_same, diff_vals),
            'note': '同一段向量两次（恒 1.0）⇒ 判据应判可分（阳性对照）',
        }
        out['neg_controls'] = neg
        out['neg_all_detected'] = all(v['detected'] for v in neg.values())
        out['neg_required_detected'] = all(neg[k]['detected']
                                           for k in ('swapped', 'diff_as_same', 'identical'))
        out['pass'] = bool(out['neg_required_detected'])
        out['verdict'] = ('SEPARABLE' if sep else 'NOT_SEPARABLE')
        out['next_step'] = (
            '按第 3 节裁定：wespeaker 可分 ⇒ 需做 before/after × dialog3/tight 四组 + 预设 A 对照组重跑'
            if sep else
            '按第 3 节裁定：wespeaker 也分不开 ⇒ 停下，不做 before/after 与对照组 B，交 reviewer 抽听')
        out['app329_old_encoder_ref_pair'] = {
            'A-B': 0.967428, 'A-C': 0.971264, 'B-C': 0.957272,
            'note': '旧 TTS speaker_encoder 的三人参考两两余弦（app329_app093_voice_attrib.json）'}
    except Exception as e:
        out['pass'] = False
        out['error'] = '%s: %s' % (type(e).__name__, str(e))
        print('🔴 ' + out['error'], flush=True)
    finally:
        out['lock']['ended'] = now()
        out['lock']['released'] = ML.release(payload)
        print('[lock] released=%s' % out['lock']['released'], flush=True)
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[out] %s' % OUT, flush=True)
        beat('APP-099 4.6c：可分性作业结束，已释放锁')

    print(json.dumps({k: out.get(k) for k in
                      ('pass', 'verdict', 'neg_all_detected', 'next_step')},
                     ensure_ascii=False), flush=True)
    if out.get('separability'):
        print(json.dumps(out['separability']['ref_pair_cosine'], ensure_ascii=False), flush=True)
        print('same=%s diff=%s' % (out['separability']['same_spk_pairs'],
                                   out['separability']['diff_spk_pairs']), flush=True)
    return 0 if out.get('pass') else 1


if __name__ == '__main__':
    raise SystemExit(main())
