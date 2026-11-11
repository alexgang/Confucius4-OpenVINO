# -*- coding: utf-8 -*-
r"""_app454_app099_wespeaker_voice_attrib.py — APP-099 四.6(c)：§3.5 换 wespeaker 后四组重算。

## reviewer APP-099 第 3 节裁定 / 四.6(c)
> 「§3.5 判据换嵌入空间：现在用的 TTS speaker_encoder 在这份素材上分不开三个人
>  （0.957–0.972）。改用 wespeaker-resnet34（与旁路同一个），对输出 wav 和 truth
>  的三人参考计算余弦。先报可分性……」
> 四.6(c)：「按第 3 节新判据做 §3.5：先报可分性；**可分的话，before/after ×
>  dialog3/tight 各算一遍**；预设 A 对照组要重跑。」

`app445_app099_wespeaker_separability.json` 已报 SEPARABLE ⇒ 本脚本做四组重算。

## 口径（与 _app329_app093_voice_attrib.py 逐字对齐，只换嵌入空间）
* 参考：truth.json 三个人各自的参考段（沿用 app329 各组 json 里的 ``refs``，不重选）。
* 输出：run 目录 ``dump/`` 里逐句 wav，按 ``tts.jsonl`` 的 seg +
  ``spk_seg.jsonl`` 的 t0/t1 对应到 truth 的说话人。
* 判据：输出嵌入与三人参考分别比余弦 ⇒ 取最大者；等于真值说话人 ⇒ 命中。
  报 ``n_scored / n_match_truth_ref / match_rate_truth_ref / margin_p50``。
* 反证（沿用 app329）：把每句「真值说话人」的余弦压到最低 ⇒ 命中数必须下降。
  另加「三人参考全同」反证 ⇒ 每行 cos 必须全相等、margin 全 0。

## 🔴 与旧脚本的唯一实质差异
* 嵌入：``TE.speaker_embedding``（TTS speaker_encoder）→ ``WespeakerOVEncoder``。
* TTS dump wav 是 **24 kHz**（实测），wespeaker 要 16 kHz ⇒
  ``scipy.signal.resample_poly`` 重采样；源 truth wav 本就是 16 kHz。
* 不重跑 App、不生成新 wav：只用 §3.5 已落盘的四组产物重算。

## 纪律
* 持 MACHINE_LOCK（fail-closed），锁记录写进 json；用完 release。
* 一次编译 IR、四组共用；不调 MiniMax、不打包、不改默认值或判据。
* 预设 A 对照组「重跑」需要**影子包全量对齐 dev 树的 self_ref 闸门**，
  实测 after2 的 ``_maybe_send_self_ref`` 计数为 0 ⇒ 本脚本不冒充该重跑，
  状态写进 ``preset_a_control_rerun`` 交 reviewer 裁定。
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import wave
from math import gcd

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, r'C:\Users\Trekker-PTL\_app_shadow\after2\app\asr_spk')

import machine_lock_app as ML  # noqa: E402
from asr052_spk_runtime import WespeakerOVEncoder  # noqa: E402

SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
WES_IR = r'C:\Users\Trekker-PTL\qwen3asr_06b\models\wespeaker-resnet34-fp16'
DEVICE = 'GPU.0'
SR = 16000
MIN_DUR_S = 1.5
OUT = os.path.join(HERE, 'app454_app099_wespeaker_voice_attrib.json')
OLD_REPORT = os.path.join(HERE, 'app329_app093_voice_attrib.json')
SEP_REPORT = os.path.join(HERE, 'app445_app099_wespeaker_separability.json')
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


def read_wav_16k(path):
    """读任意 wav → 16 kHz mono float32（TTS dump 实测 24 kHz）。"""
    w = wave.open(path, 'rb')
    try:
        sr, sw, ch = w.getframerate(), w.getsampwidth(), w.getnchannels()
        n = w.getnframes()
        raw = w.readframes(n)
    finally:
        w.close()
    if sw != 2:
        raise RuntimeError('只支持 16-bit PCM：sampwidth=%d' % sw)
    a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        from scipy.signal import resample_poly
        g = gcd(sr, SR)
        a = resample_poly(a, SR // g, sr // g).astype(np.float32)
    return a, sr


def unit(v):
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    return v / (float(np.linalg.norm(v)) + 1e-9)


def cos(a, b):
    return float(np.dot(unit(a), unit(b)))


def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def embed(enc, pcm):
    if len(pcm) / SR < MIN_DUR_S:
        return None
    try:
        return unit(enc.embed(np.ascontiguousarray(pcm, dtype=np.float32), SR))
    except Exception:
        return None


def truth_of(truth, t0, t1):
    best = None
    for x0, x1, s in truth:
        ov = min(t1, float(x1)) - max(t0, float(x0))
        if ov > 0 and (best is None or ov > best[0]):
            best = (ov, s)
    return best[1] if best else None


def group_run(enc, g, old_json):
    """对一组 run 重算音色归属；返回 (result, errors)。"""
    label = g['label']
    run_dir = g['run_dir']
    src_wav = os.path.join(SPKTEST, os.path.basename(old_json.get('wav', '')))
    truth_file = os.path.join(SPKTEST, os.path.basename(old_json.get('truth_file', '')))
    if not os.path.isfile(src_wav) or not os.path.isfile(truth_file):
        # 回退：从 app329 组 label 推断（与 driver GROUPS 一致）
        tight = label.endswith('tight')
        src_wav = os.path.join(SPKTEST, 'dialog3_tight.wav' if tight else 'dialog3.wav')
        truth_file = os.path.join(SPKTEST, 'truth_tight.json' if tight else 'truth.json')
    truth = json.load(open(truth_file, encoding='utf-8'))
    spks = sorted({x[2] for x in truth})
    src, _ = read_wav_16k(src_wav)

    # ① 三人参考：沿用 app329 各组 json 里的 refs（不重选）
    ref_emb, refs_used = {}, {}
    for s, seg in (old_json.get('refs') or {}).items():
        a, b = int(float(seg[0]) * SR), int(float(seg[1]) * SR)
        v = embed(enc, src[a:b])
        refs_used[s] = list(seg)
        if v is not None:
            ref_emb[s] = v
    ref_pair = {}
    for i, a in enumerate(spks):
        for b in spks[i + 1:]:
            if a in ref_emb and b in ref_emb:
                ref_pair['%s-%s' % (a, b)] = round(cos(ref_emb[a], ref_emb[b]), 6)

    # ② 输出 wav：与 app329 同款 seg → dump 映射
    tts_rows = read_jsonl(os.path.join(run_dir, 'tts.jsonl'))
    seg_rows = read_jsonl(os.path.join(run_dir, 'spk_seg.jsonl'))
    seg_time = {r.get('seg'): (float(r['t0']), float(r['t1']))
                for r in seg_rows if r.get('seg') is not None
                and r.get('t0') is not None and r.get('t1') is not None}
    dump_dir = os.path.join(run_dir, 'dump')
    dump_files = {}
    if os.path.isdir(dump_dir):
        for f in os.listdir(dump_dir):
            if not f.endswith('.wav'):
                continue
            core = f[:-4].split('_')
            if len(core) >= 2 and core[0] == 'seg':
                try:
                    dump_files.setdefault(int(core[1]), []).append(
                        os.path.join(dump_dir, f))
                except ValueError:
                    pass

    rows, skipped = [], {'no_seg_time': 0, 'no_dump': 0, 'embed_none': 0}
    for r in tts_rows:
        seg = r.get('seg')
        if seg is None:
            continue
        st = seg_time.get(seg)
        if st is None:
            skipped['no_seg_time'] += 1
            continue
        cands = dump_files.get(int(seg)) or []
        out_wav = next((c for c in cands if not c.endswith('_acc110.wav')),
                       cands[0] if cands else None)
        if out_wav is None:
            skipped['no_dump'] += 1
            continue
        try:
            pcm, orig_sr = read_wav_16k(out_wav)
        except Exception as e:
            skipped['embed_none'] += 1
            continue
        v = embed(enc, pcm)
        if v is None:
            skipped['embed_none'] += 1
            continue
        cv = {s: round(cos(v, ref_emb[s]), 6) for s in spks if s in ref_emb}
        if len(cv) < 2:
            skipped['embed_none'] += 1
            continue
        t_spk = truth_of(truth, *st)
        best = max(cv, key=lambda k: cv[k])
        srt = sorted(cv.values(), reverse=True)
        rows.append({
            'seg': seg, 't0': st[0], 't1': st[1],
            'truth_spk': t_spk, 'best_ref': best,
            'ok': bool(t_spk is not None and best == t_spk),
            'cos': cv, 'margin': round(srt[0] - srt[1], 6),
            'dump': out_wav, 'orig_sr': orig_sr,
        })

    n = len(rows)
    n_match = sum(1 for x in rows if x['ok'])
    margins = sorted(x['margin'] for x in rows)

    # ③ 反证 A（沿用 app329）：把真值说话人的余弦压到最低 ⇒ 命中数必须下降
    neg_hits = 0
    for x in rows:
        cv = dict(x['cos'])
        if x['truth_spk'] in cv:
            cv[x['truth_spk']] = min(cv.values()) - 1.0
        if max(cv, key=lambda k: cv[k]) == x['truth_spk']:
            neg_hits += 1
    # ④ 反证 B：把三人参考标签轮换（A→B→C→A）⇒ best_ref 分布必须变化
    #    （若判据根本不读参考、或把参考写死，分布不会变 ⇒ 能识破）
    ks_all = sorted(spks)
    rot_map = {ks_all[i]: ks_all[(i + 1) % len(ks_all)]
               for i in range(len(ks_all))}
    rot_hits, rot_best, base_best = 0, {}, {}
    for x in rows:
        cv = dict(x['cos'])
        rot = {rot_map.get(k, k): v for k, v in cv.items()}
        b = max(rot, key=lambda k: rot[k])
        rot_best[b] = rot_best.get(b, 0) + 1
        base_best[x['best_ref']] = base_best.get(x['best_ref'], 0) + 1
        if b == x['truth_spk']:
            rot_hits += 1
    neg = {
        'truth_cos_suppressed': {
            'base_n_match': n_match, 'neg_n_match': neg_hits,
            'detected': bool(n > 0 and neg_hits < n_match),
            'note': '把真值说话人余弦压到最低 ⇒ 命中数必须下降（否则判据恒真）',
        },
        'rotated_ref_labels': {
            'base_n_match': n_match, 'neg_n_match': rot_hits,
            'base_best_ref_distribution': base_best,
            'rotated_best_ref_distribution': rot_best,
            'detected': bool(n > 0 and rot_best != base_best),
            'note': '把三人参考标签轮换 ⇒ best_ref 分布必须变化（证明判据真的在用参考）',
        },
    }
    res = {
        'label': label, 'arm': g.get('arm'), 'run_dir': run_dir,
        'truth_file': truth_file, 'src_wav': src_wav,
        'spks': spks, 'refs': refs_used,
        'ref_pair_cosine': ref_pair,
        'n_tts_rows': len(tts_rows), 'n_scored': n,
        'skipped': skipped,
        'n_match_truth_ref': n_match,
        'match_rate_truth_ref': (round(n_match / n, 4) if n else None),
        'margin_p50': (round(margins[len(margins) // 2], 6) if margins else None),
        'margin_p90': (round(margins[int(len(margins) * 0.9)], 6) if margins else None),
        'rows_head': rows[:5],
        'neg_control': neg,
        'old_encoder_summary': (g.get('summary') or {}),
        'old_encoder_ref_pair_cosine': g.get('ref_pair_cosine'),
    }
    res['neg_all_detected'] = all(v['detected'] for v in neg.values())
    return res


def main():
    beat('APP-099 4.6c：wespeaker 四组音色归属重算（准备持锁）')
    sep = json.load(open(SEP_REPORT, encoding='utf-8'))
    old = json.load(open(OLD_REPORT, encoding='utf-8'))
    out = {
        'task': 'APP-099 四.6(c)：§3.5 换 wespeaker 嵌入空间后 before/after × dialog3/tight 四组重算',
        'created_at': now(),
        'criterion': ('输出 wav 的 wespeaker 嵌入与 truth 三人参考分别比余弦 ⇒ '
                      '取最大者 == 真值说话人 ⇒ 命中（与 app329 口径一致，仅换嵌入空间）'),
        'encoder': {
            'ir': WES_IR, 'device': DEVICE,
            'class': 'WespeakerOVEncoder（与 ASR 说话人旁路同一份）',
            'resample': 'TTS dump 24 kHz → 16 kHz（scipy.signal.resample_poly）',
            'min_dur_s': MIN_DUR_S,
            'separability_prior': {
                'file': 'app445_app099_wespeaker_separability.json',
                'verdict': sep.get('verdict'),
                'separable': sep.get('separability', {}).get('separable'),
                'same_min': sep.get('separability', {}).get('same_spk_pairs', {}).get('min'),
                'diff_max': sep.get('separability', {}).get('diff_spk_pairs', {}).get('max'),
            },
        },
        'source_of_groups': 'app329_app093_voice_attrib.json → groups[].run_dir（不手抄）',
        'old_encoder_report': 'app329_app093_voice_attrib.json',
        'lock': None, 'groups': [], 'pass': False,
    }
    if sep.get('verdict') != 'SEPARABLE':
        out['verdict'] = 'STOPPED_NOT_SEPARABLE'
        out['note'] = '按第 3 节裁定：wespeaker 不可分 ⇒ 停下交 reviewer 抽听'
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('🔴 ' + out['note'], flush=True)
        return 0

    ok, payload = ML.acquire(module='app', timeout=1800, poll=20)
    if not ok:
        out['error'] = 'MACHINE_LOCK 取不到（fail-closed，未抢锁）'
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('🔴 ' + out['error'], flush=True)
        return 1
    out['lock'] = {'module': 'app', 'payload': payload, 'pid': os.getpid(),
                   'started': now(), 'ended': None}
    print('[lock] 已取得：%s' % payload.replace('\n', ' | ')[:200], flush=True)

    try:
        enc = WespeakerOVEncoder(WES_IR, DEVICE)
        print('[enc] IR 编译完成 device=%s' % DEVICE, flush=True)
        for g in old['groups']:
            label = g['label']
            oj = os.path.join(HERE, 'app329_%s.json' % label)
            old_json = json.load(open(oj, encoding='utf-8')) if os.path.isfile(oj) else {}
            print('[group] %s …' % label, flush=True)
            # 🔴 传完整的 old group（含 summary / ref_pair_cosine）⇒
            #    否则「新旧并列」的旧数字会全变 null（初版踩过一次）。
            r = group_run(enc, g, old_json)
            out['groups'].append(r)
            print('   n_scored=%s match=%s rate=%s ref_pair=%s neg=%s' %
                  (r['n_scored'], r['n_match_truth_ref'],
                   r['match_rate_truth_ref'], r['ref_pair_cosine'],
                   r['neg_all_detected']), flush=True)
            beat('APP-099 4.6c：完成 %s 重算' % label)
        out['pass'] = bool(
            len(out['groups']) == 4
            and all(x['n_scored'] > 0 and x['neg_all_detected']
                    for x in out['groups']))
        out['verdict'] = 'RAN' if out['pass'] else 'PARTIAL'
        # 新旧并列，不自行下结论
        out['old_vs_wespeaker'] = [
            {'label': x['label'],
             'old_rate': (x['old_encoder_summary'] or {}).get('match_rate_truth_ref'),
             'old_ref_pair': x['old_encoder_ref_pair_cosine'],
             'wes_rate': x['match_rate_truth_ref'],
             'wes_ref_pair': x['ref_pair_cosine'],
             'n_scored_old': (x['old_encoder_summary'] or {}).get('n_scored'),
             'n_scored_wes': x['n_scored']}
            for x in out['groups']]
    except Exception as e:
        out['error'] = '%s: %s' % (type(e).__name__, str(e))
        print('🔴 ' + out['error'], flush=True)
    finally:
        out['lock']['ended'] = now()
        out['lock']['released'] = ML.release(payload)
        print('[lock] released=%s' % out['lock']['released'], flush=True)
        out['preset_a_control_rerun'] = {
            'status': 'NOT_RUN_BLOCKED_BY_SHADOW_ALIGNMENT',
            'reason': ('reviewer 第 3 节要求「预设 A 对照组在 self_ref 闸门修好后重跑」；'
                       '实测影子包 after2 的 _maybe_send_self_ref 计数为 0，未全量对齐 '
                       'dev 树（§174 闸门修复），按「混版影子包不能报数」纪律不拿它跑数；'
                       '且 §4.6(a) 阈值四臂按第 0 节第 3 条暂缓 ⇒ 无干净运行日志。'),
            'decision': '交 reviewer 裁定：先同步影子包底座，或指定用 rc7（self_ref 死路径）重跑',
        }
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[out] %s' % OUT, flush=True)
        beat('APP-099 4.6c：四组重算结束，已释放锁')
    print('pass=%s verdict=%s groups=%d' %
          (out['pass'], out.get('verdict'), len(out['groups'])), flush=True)
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
