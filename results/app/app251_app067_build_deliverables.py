#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app251 — 产出 **APP-067 ② 的交付物**（reviewer 要的 3 件东西）。

> ① 每段一行的表：seg_id / t0 / t1 / spk / voice_id / voice_kind / 换人检测时间点；
> ② 男声 3 段、女声 3 段 wav，以及同一批句子的预设 A 对照，
>    放在 `shared\\app_listen\\v23_clone\\`；
> ③ 每段对应的原声参考片段，供 reviewer 计算 speaker 相似度。

## 数据来源（**全部是设备级实测产物**，不手工编）
| 数据 | 文件 |
|---|---|
| 逐段（seg/t0/t1/spk） | `app250_device_out/<clone 臂>.seg.jsonl`（App 侧 `--spk-seg-jsonl`） |
| 提交序号 → seg | `app250_device_out/<clone 臂>.seg.jsonl.submit.jsonl`（App 侧记录） |
| 逐句（voice_kind/voice_spk/text） | `app250_device_out/<clone 臂>.tts.jsonl`（worker 侧） |
| 逐句 wav | `app250_device_out/<clone 臂>.wavparts/seg_<jid>_NNNN.wav` |
| 性别（推定） | `app246_app067_spk_gender_segment_evidence.json` → `per_speaker` |
| 切片清单 | `shared/app_listen/v23_clone/mix_segment_manifest.json` |

## 拼接口径（**关键**）
* 逐句 jsonl 的 `id` == worker 的 `jid` == **提交序号**（`tts_service._next_id`）
  ⇒ 与「提交序号 → seg」映射**精确对齐**（**不靠「第 N 段 = 第 N 句」猜**）。
* 🔴 判据**三态**：True / False / None（无法判定）⇒ 缺证据就报 None。

## 用法
```
python results/app/app251_app067_build_deliverables.py
```
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')

DEV_OUT = os.path.join(HERE, 'app250_device_out')
OUT_DIR = os.path.join(HOME, 'shared', 'app_listen', 'v23_clone')
GENDER_EV = os.path.join(HERE, 'app246_app067_spk_gender_segment_evidence.json')
MIX_MAN = os.path.join(OUT_DIR, 'mix_segment_manifest.json')
OUT_JSON = os.path.join(HERE, 'app251_app067_deliverables_evidence.json')


def read_jsonl(path):
    rows = []
    if not path or not os.path.isfile(path):
        return rows
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def pick_dump_wav(dump_dir, jid):
    """在 dump 目录里挑 jid 对应的 wav（取**最大**的那个 = 主体）。"""
    if not dump_dir or not os.path.isdir(dump_dir):
        return None
    pref = 'seg_%d_' % jid
    cands = [f for f in os.listdir(dump_dir)
             if f.startswith(pref) and f.endswith('.wav')]
    if not cands:
        return None
    cands.sort(key=lambda f: -os.path.getsize(os.path.join(dump_dir, f)))
    return os.path.join(dump_dir, cands[0])


def cut_wav(src, dst, t0, t1):
    """按 [t0, t1] 切一段（**逐样本**，不重采样）。"""
    with wave.open(src, 'rb') as w:
        sr = w.getframerate()
        nch = w.getnchannels()
        sw = w.getsampwidth()
        i0 = max(0, int(round(t0 * sr)))
        i1 = min(w.getnframes(), int(round(t1 * sr)))
        if i1 <= i0:
            return None
        w.setpos(i0)
        raw = w.readframes(i1 - i0)
    with wave.open(dst, 'wb') as w:
        w.setnchannels(nch)
        w.setsampwidth(sw)
        w.setframerate(sr)
        w.writeframes(raw)
    return {'bytes': os.path.getsize(dst), 'sr': sr, 'nch': nch,
            'sampwidth': sw, 'n_samples': (i1 - i0),
            'dur_s': round((i1 - i0) / float(sr), 3),
            'src_offset_s': round(i0 / float(sr), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev-out', default=DEV_OUT)
    ap.add_argument('--out-dir', default=OUT_DIR)
    ap.add_argument('--out', default=OUT_JSON)
    ap.add_argument('--n-per-gender', type=int, default=3)
    args = ap.parse_args()

    out = {'script': 'app251_app067_build_deliverables.py',
           'correction': 'APP-067 ②',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': [], 'deliverables': []}

    def add(name, verdict, detail, why=''):
        out['checks'].append({'name': name, 'verdict': verdict,
                              'detail': detail, 'why': why})
        print('  [%s] %s%s' % ({True: 'PASS', False: 'FAIL',
                                None: 'NONE'}[verdict], name,
                               ('  ' + json.dumps(detail, ensure_ascii=False))
                               if detail else ''))

    # ── 定位 clone 臂与 preset 臂 ──────────────────────────────
    def find_arm(prefix):
        if not os.path.isdir(args.dev_out):
            return None
        for fn in sorted(os.listdir(args.dev_out)):
            if fn.startswith(prefix) and fn.endswith('.seg.jsonl'):
                stem = fn[:-len('.seg.jsonl')]
                return os.path.join(args.dev_out, stem)
        return None

    clone_stem = find_arm('tts_on_clone')
    preset_stem = find_arm('tts_on_preset')
    out['clone_stem'] = clone_stem
    out['preset_stem'] = preset_stem
    if not clone_stem:
        add('找到 clone 臂的产物', False, {'dev_out': args.dev_out},
            '设备作业还没产出 seg 表')
        out['verdict'] = 'NO_DATA'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % args.out)
        return 0

    seg_rows = read_jsonl(clone_stem + '.seg.jsonl')
    sub_rows = read_jsonl(clone_stem + '.seg.jsonl.submit.jsonl')
    sent_rows = read_jsonl(clone_stem + '.tts.jsonl')
    preset_sent = read_jsonl(preset_stem + '.tts.jsonl') if preset_stem else []
    by_id = {r.get('id'): r for r in sent_rows if r.get('id') is not None}
    seg_by_no = {r.get('seg'): r for r in seg_rows if r.get('seg') is not None}
    p_by_id = {r.get('id'): r for r in preset_sent if r.get('id') is not None}

    add('clone 臂的段表有数据', len(seg_rows) > 0, {'n_seg_rows': len(seg_rows)})
    add('clone 臂的提交映射有数据', len(sub_rows) > 0,
        {'n_submit_rows': len(sub_rows)})
    add('clone 臂的逐句 jsonl 有数据', len(sent_rows) > 0,
        {'n_sent_rows': len(sent_rows)})

    # ── 拼接：jid → (seg, t0, t1, spk) + 逐句（voice_kind/text）────
    joined = []
    for s in sub_rows:
        jid = s.get('jid')
        seg_no = s.get('seg')
        sent = by_id.get(jid) or {}
        srow = seg_by_no.get(seg_no) or {}
        joined.append({
            'jid': jid,
            'seg_id': seg_no,
            't0': srow.get('t0'),
            't1': srow.get('t1'),
            'spk': srow.get('spk') or s.get('spk'),
            'spk_conf': srow.get('spk_conf'),
            'spk_source': srow.get('spk_source'),
            'voice_id': sent.get('voice_spk') or srow.get('spk'),
            'voice_kind': sent.get('voice_kind'),
            'text': sent.get('text'),
            'dur_s': sent.get('dur_s'),
            'dropped': sent.get('dropped'),
            'error': sent.get('error'),
        })
    n_join_ok = sum(1 for j in joined if j['seg_id'] is not None
                    and j['t0'] is not None and j['t1'] is not None)
    add('每条提交都能对上「段号 + 音频区间 + 逐句遥测」', n_join_ok > 0,
        {'n_joined': len(joined), 'n_with_seg_span': n_join_ok})

    # ── 换人检测时间点（按 seg 顺序看 spk 变化）─────────────────
    switches = []
    prev_spk = None
    for j in sorted(joined, key=lambda x: (x['seg_id'] is None,
                                          x['seg_id'])):
        if j['seg_id'] is None:
            continue
        spk = j['spk']
        if spk and prev_spk is not None and spk != prev_spk:
            switches.append({'seg_id': j['seg_id'], 't_s': j['t0'],
                             'from': prev_spk, 'to': spk})
        if spk:
            prev_spk = spk
    switch_by_seg = {x['seg_id']: x for x in switches}
    for j in joined:
        sw = switch_by_seg.get(j['seg_id'])
        j['switch_at_s'] = sw['t_s'] if sw else None
        j['switch_from'] = sw['from'] if sw else None
        j['switch_to'] = sw['to'] if sw else None

    # ── 性别（**直接实测**：对 App 自己的每一簇，在**混合切片**上测基频）────
    # 🔴🔴 **不能**假设「App 聚类出的 S1 == 参照标注的 S1」
    #   （两套编号**各自独立**：App 是 pyannote+wespeaker 在线聚类，
    #    参照是 ASR-028 离线标注 ⇒ 编号**可能不对应**）
    #   ⇒ 这里**不看参照的编号**，只对 **App 自己的簇**在原音频上量 F0。
    gev = {}
    if os.path.isfile(GENDER_EV):
        gev = {r['spk']: r for r in json.load(
            open(GENDER_EV, encoding='utf-8')).get('per_speaker', [])}
    ref_gender = {}
    for spk, r in gev.items():
        ref_gender[spk] = ('male' if r.get('presumed_class') ==
                           'low_f0_male_presumed' else 'female')
    out['reference_gender_map'] = ref_gender

    man = json.load(open(MIX_MAN, encoding='utf-8')) if \
        os.path.isfile(MIX_MAN) else {}
    mix_wav = (man.get('cut_wav') or {}).get('path')
    if not mix_wav or not os.path.isfile(mix_wav):
        add('找到混合切片 wav', False, {'expected': mix_wav})
        mix_wav = None

    gender, f0_evidence = {}, {}
    if mix_wav:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'a246', os.path.join(HERE, 'app246_app067_spk_gender_segment.py'))
        a246 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(a246)
        ca, csr, _cnf = a246.read_wav(mix_wav)
        by_spk = {}
        for j in joined:
            if j['spk'] and j['t0'] is not None:
                by_spk.setdefault(j['spk'], []).append(j)
        for spk, items in sorted(by_spk.items()):
            frames = []
            for j in items:
                frames.extend(a246.segment_f0(ca, csr, j['t0'], j['t1']))
            med = a246.pct(frames, 50)
            cls = ('male' if (med and med < a246.F0_MALE_MAX) else 'female')
            gender[spk] = cls
            f0_evidence[spk] = {
                'n_segments': len(items), 'n_voiced_frames': len(frames),
                'f0_median_hz': round(med, 2) if med else None,
                'f0_p25_hz': round(a246.pct(frames, 25), 2) if frames else None,
                'f0_p75_hz': round(a246.pct(frames, 75), 2) if frames else None,
                'male_max_hz': a246.F0_MALE_MAX,
                'measured_on': os.path.basename(mix_wav),
                'note': '**直接测 App 自己的簇**（不依赖参照编号）',
            }
    out['gender_map'] = gender
    out['f0_evidence'] = f0_evidence
    print('\n=== 性别（对 App 自己的簇直接测 F0）===')
    for spk, e in f0_evidence.items():
        print('  %s: F0 中位 %s Hz（%d 段 / %d 帧）⇒ %s'
              % (spk, e['f0_median_hz'], e['n_segments'],
                 e['n_voiced_frames'], gender.get(spk)))
    add('性别有直接实测来源（App 自己的簇的 F0）', bool(gender),
        {'n_clusters': len(gender), 'f0_evidence': f0_evidence})
    add('既有男声簇也有女声簇',
        ('male' in gender.values() and 'female' in gender.values()),
        {'gender_map': gender})

    # ── ① 表（每段一行）→ CSV + JSON ────────────────────────────
    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, 'seg_voice_table.csv')
    json_path = os.path.join(args.out_dir, 'seg_voice_table.json')
    cols = ['seg_id', 'jid', 't0', 't1', 'seg_span_s', 'tts_dur_s', 'spk',
            'spk_conf', 'spk_source', 'voice_id', 'voice_kind',
            'gender_presumed', 'switch_at_s', 'switch_from', 'switch_to',
            'dropped', 'error', 'text']
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        wcsv = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        wcsv.writeheader()
        for j in sorted(joined, key=lambda x: (x['seg_id'] is None,
                                              x['seg_id'])):
            row = dict(j)
            row['gender_presumed'] = gender.get(j['spk'])
            row['tts_dur_s'] = row.pop('dur_s', None)
            row['seg_span_s'] = (round(j['t1'] - j['t0'], 3)
                                 if (j['t0'] is not None and
                                     j['t1'] is not None) else None)
            wcsv.writerow(row)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'created_by': 'app251', 'ts': out['ts'],
                   'columns': cols, 'rows': joined,
                   'switches': switches, 'gender_map': gender,
                   'f0_evidence': f0_evidence},
                  f, ensure_ascii=False, indent=1)
    out['table'] = {'csv': csv_path, 'json': json_path,
                    'n_rows': len(joined), 'n_switches': len(switches)}
    print('\n表（逐句）→ %s（%d 行 / 换人 %d 次）' % (csv_path, len(joined),
                                                     len(switches)))

    # ── ① 的**「每段一行」**版本（reviewer 原文口径）────────────
    #   🔴 MT 会把一个 ASR 段拆成多句 ⇒ 逐句表里同一个 seg 会出现多行
    #   ⇒ reviewer 要的「每段一行」= 按 seg 聚合。
    seg_csv = os.path.join(args.out_dir, 'seg_voice_table_by_seg.csv')
    seg_json = os.path.join(args.out_dir, 'seg_voice_table_by_seg.json')
    by_seg = {}
    for j in joined:
        if j['seg_id'] is None:
            continue
        by_seg.setdefault(j['seg_id'], []).append(j)
    seg_rows_out = []
    for seg_no in sorted(by_seg):
        items = by_seg[seg_no]
        first = items[0]
        kinds = [x['voice_kind'] for x in items if x.get('voice_kind')]
        seg_rows_out.append({
            'seg_id': seg_no,
            't0': first['t0'], 't1': first['t1'],
            'seg_span_s': (round(first['t1'] - first['t0'], 3)
                           if (first['t0'] is not None and
                               first['t1'] is not None) else None),
            'spk': first['spk'], 'spk_conf': first['spk_conf'],
            'spk_source': first['spk_source'],
            'voice_id': first['voice_id'],
            'voice_kind': kinds[0] if kinds else None,
            'voice_kind_all': '|'.join(kinds),
            'n_sentences': len(items),
            'n_clone_sentences': sum(1 for k in kinds if k == 'clone'),
            'gender_presumed': gender.get(first['spk']),
            'switch_at_s': first.get('switch_at_s'),
            'switch_from': first.get('switch_from'),
            'switch_to': first.get('switch_to'),
            'texts': ' / '.join((x['text'] or '') for x in items),
        })
    seg_cols = ['seg_id', 't0', 't1', 'seg_span_s', 'spk', 'spk_conf',
                'spk_source', 'voice_id', 'voice_kind', 'voice_kind_all',
                'n_sentences', 'n_clone_sentences', 'gender_presumed',
                'switch_at_s', 'switch_from', 'switch_to', 'texts']
    with open(seg_csv, 'w', encoding='utf-8-sig', newline='') as f:
        wcsv = csv.DictWriter(f, fieldnames=seg_cols, extrasaction='ignore')
        wcsv.writeheader()
        for r in seg_rows_out:
            wcsv.writerow(r)
    with open(seg_json, 'w', encoding='utf-8') as f:
        json.dump({'created_by': 'app251', 'ts': out['ts'],
                   'note': '**每段一行**（reviewer 的「每段一行的表」口径）',
                   'columns': seg_cols, 'rows': seg_rows_out,
                   'switches': switches, 'gender_map': gender,
                   'f0_evidence': f0_evidence},
                  f, ensure_ascii=False, indent=1)
    out['table_by_seg'] = {'csv': seg_csv, 'json': seg_json,
                           'n_rows': len(seg_rows_out)}
    print('表（每段一行）→ %s（%d 段）' % (seg_csv, len(seg_rows_out)))
    add('① 产出「每段一行」的表', len(seg_rows_out) > 0,
        {'path': seg_csv, 'n_rows': len(seg_rows_out)})

    # ── ② + ③ 选出男 3 段 / 女 3 段，产 wav 与原声参考 ───────────
    picked = {'male': [], 'female': []}
    for g in ('male', 'female'):
        cands = [j for j in joined
                 if j['spk'] and gender.get(j['spk']) == g
                 and j['voice_kind'] == 'clone'
                 and j['t0'] is not None and not j['dropped']]
        # 先按「时长够长」排（同句长 ⇒ 更好比对），再按段号
        cands.sort(key=lambda x: (-(x['dur_s'] or 0), x['seg_id'] or 0))
        for j in cands[:args.n_per_gender]:
            picked[g].append(j)

    for g in ('male', 'female'):
        add('② 选出 %s 声 %d 段（voice_kind=clone）' % (g, args.n_per_gender),
            len(picked[g]) >= args.n_per_gender,
            {'n': len(picked[g]),
             'segs': [x['seg_id'] for x in picked[g]]})

    os.makedirs(os.path.join(args.out_dir, 'wav_clone'), exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, 'wav_presetA'), exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, 'wav_original'), exist_ok=True)

    for g in ('male', 'female'):
        for i, j in enumerate(picked[g], 1):
            tag = '%s_%02d_seg%s' % (g, i, j['seg_id'])
            rec = {'gender': g, 'seg_id': j['seg_id'], 'jid': j['jid'],
                   't0': j['t0'], 't1': j['t1'], 'spk': j['spk'],
                   'voice_id': j['voice_id'], 'voice_kind': j['voice_kind'],
                   'text': j['text']}
            # ② clone wav
            src = pick_dump_wav(os.path.join(args.dev_out,
                                             os.path.basename(clone_stem)
                                             + '.wavparts'), j['jid'])
            if src:
                dst = os.path.join(args.out_dir, 'wav_clone',
                                   tag + '_clone.wav')
                shutil.copy2(src, dst)
                rec['clone_wav'] = {'path': dst,
                                    'bytes': os.path.getsize(dst)}
            # ② 预设 A 对照（同一句 ⇒ 同一个 jid）
            if preset_stem:
                psrc = pick_dump_wav(os.path.join(
                    args.dev_out, os.path.basename(preset_stem) + '.wavparts'),
                    j['jid'])
                if psrc:
                    dst = os.path.join(args.out_dir, 'wav_presetA',
                                       tag + '_presetA.wav')
                    shutil.copy2(psrc, dst)
                    rec['presetA_wav'] = {'path': dst,
                                          'bytes': os.path.getsize(dst)}
            # ③ 原声参考片段
            if mix_wav and j['t0'] is not None:
                dst = os.path.join(args.out_dir, 'wav_original',
                                   tag + '_orig.wav')
                info = cut_wav(mix_wav, dst, j['t0'], j['t1'])
                if info:
                    info['path'] = dst
                    rec['original_wav'] = info
            out['deliverables'].append(rec)

    n_clone = sum(1 for r in out['deliverables'] if r.get('clone_wav'))
    n_preset = sum(1 for r in out['deliverables'] if r.get('presetA_wav'))
    n_orig = sum(1 for r in out['deliverables'] if r.get('original_wav'))
    # 🔴 期望条数 = **男 3 + 女 3** = 2 × n_per_gender（不是 3 ×）
    n_expect = 2 * args.n_per_gender
    add('② clone wav 已落盘', n_clone >= n_expect,
        {'n': n_clone, 'expect_min': n_expect})
    add('② 预设 A 对照 wav 已落盘', n_preset >= n_expect,
        {'n': n_preset, 'expect_min': n_expect})
    add('③ 原声参考片段已落盘', n_orig >= n_expect,
        {'n': n_orig, 'expect_min': n_expect})

    n_pass = sum(1 for c in out['checks'] if c['verdict'] is True)
    n_fail = sum(1 for c in out['checks'] if c['verdict'] is False)
    n_none = sum(1 for c in out['checks'] if c['verdict'] is None)
    out['n_pass'], out['n_fail'], out['n_none'] = n_pass, n_fail, n_none
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
