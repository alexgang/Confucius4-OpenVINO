"""APP-089/090/091/092：**验收打分**（把设备跑的产物换算成 reviewer 要的数字）。

🔴 reviewer 要的每个数字，都必须能指到**来源 json 的路径和字段名**
   ⇒ 本脚本的输出 json 每一项都带 `src`（来源文件 + 字段）。

🔴 **不调 MiniMax**（回转写由 reviewer 在本机做）⇒ 本脚本只**落盘** wav / 译文，
   并统计「可回转写的段数」「只出字幕的段数」等**不需要 CER** 的项。

🔴 **不引用 MiniMax、不自己判 CER** ⇒ `cer` 字段一律 `None`（标注「待 reviewer 回转写」）。

用法：
  python app370_app089_score_acceptance.py --arm after --materials dialog3,dialog3_tight
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics

BASE = r'C:\Users\Trekker-PTL\_app_shadow'
OUTROOT = os.path.join(BASE, 'runs2')
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'

TRUTH = {
    'dialog3': 'truth.json',
    'dialog3_tight': 'truth_tight.json',
    'dialog3_dave': None,
}


def load_jsonl(p):
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
    if not vals:
        return None
    vs = sorted(vals)
    if len(vs) == 1:
        return round(vs[0], 4)
    k = (len(vs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vs) - 1)
    return round(vs[lo] + (vs[hi] - vs[lo]) * (k - lo), 4)


def score_arm(arm: str, mat: str) -> dict:
    out = os.path.join(OUTROOT, arm, mat)
    tj = os.path.join(out, 'tts.jsonl')
    sj = os.path.join(out, 'spk_seg.jsonl')
    subs = os.path.join(out, 'subtitles.txt')
    rows = load_jsonl(tj)
    segs = load_jsonl(sj)
    man_p = os.path.join(out, 'run_manifest.json')
    man = json.load(open(man_p, encoding='utf-8')) if os.path.exists(man_p) else {}

    n_rows = len(rows)
    # ── TTS 句级统计 ──
    late = [r for r in rows if r.get('late_drop')]
    errs = [r for r in rows if r.get('error')]
    synth = [r for r in rows if not r.get('late_drop') and not r.get('error')]
    # 「只有字幕、没有配音」的段数 ＝ 被 late_drop 跳过的句数（内容仍在字幕里）
    n_sub_only = len(late)
    # 实际合成成功（有波形）
    n_voiced = len([r for r in synth if r.get('dur_s')])
    # 第一句克隆配音出现的时间（源时间，s）
    first_voice_t = None
    for r in synth:
        if r.get('dur_s'):
            first_voice_t = r.get('t_submit')
            break
    # 🔴🔴 **换算成「源时间」**：`t_submit` 是 worker 的 perf_counter
    #   （**进程内相对时刻**）⇒ 跨进程不可比 ⇒ 必须用该句所属 seg 的 `t0`。
    seg_t0 = {}
    for s in segs:
        if s.get('t0') is not None:
            seg_t0[int(s['seg'])] = float(s['t0'])
    first_clone_src_t = None
    first_clone_seg = None
    for r in synth:
        if r.get('dur_s'):
            sg = r.get('seg')
            if sg is not None and int(sg) in seg_t0:
                first_clone_src_t = seg_t0[int(sg)]
                first_clone_seg = int(sg)
            break
    # ── 倍率分布（中文目标）──
    speeds = [float(r['speed']) for r in rows
              if r.get('speed') is not None]
    zh_speeds = [s for s in speeds if s >= 1.0]
    # ── 首包延迟 ──
    fp = [float(r['t_first_packet']) for r in rows
          if r.get('t_first_packet') is not None]
    # ── 音色来源分布 ──
    n_self_ref = len([r for r in rows if r.get('voice_self_ref')])
    n_inherited = len([r for r in rows if r.get('voice_inherited')])
    n_with_label = len([r for r in rows if r.get('spk_label')])
    # ── 说话人标签正确率（对 truth）──
    # 🔴🔴 **口径修正**：truth 用 `A/B/C`，App 旁路用 `S1/S2/S3`
    #   ⇒ **不能按名字直接比** ⇒ 必须**按时间重叠**建立映射
    #   （每个 App 说话人标签 ↔ truth 说话人，取重叠时长最大者）。
    truth_p = TRUTH.get(mat)
    truth = []
    if truth_p:
        tp = os.path.join(SPKTEST, truth_p)
        if os.path.exists(tp):
            truth = json.load(open(tp, encoding='utf-8'))
    n_truth_segs = len(truth)

    def _truth_at(t):
        """t 时刻落在哪个 truth 段（无 ⇒ None）。"""
        for t0, t1, spk in truth:
            if t0 <= t < t1:
                return spk
        return None

    # App 标签 → truth 标签 的映射（按**重叠秒数**投票）
    overlap = {}
    for s in segs:
        lab = s.get('spk')
        if not lab or s.get('t0') is None or s.get('t1') is None:
            continue
        a, b = float(s['t0']), float(s['t1'])
        for t0, t1, tspk in truth:
            ov = min(b, t1) - max(a, t0)
            if ov > 0:
                overlap.setdefault(lab, {})
                overlap[lab][tspk] = overlap[lab].get(tspk, 0.0) + ov
    spk_map = {}
    for lab, d in overlap.items():
        spk_map[lab] = max(d.items(), key=lambda kv: kv[1])[0]

    n_matched = 0
    n_labeled = 0
    n_multi = 0
    for s in segs:
        lab = s.get('spk')
        if not lab or s.get('t0') is None or s.get('t1') is None:
            continue
        n_labeled += 1
        a, b = float(s['t0']), float(s['t1'])
        # 该段覆盖的 truth 说话人集合
        ts = set()
        for t0, t1, tspk in truth:
            if min(b, t1) - max(a, t0) > 0:
                ts.add(tspk)
        if len(ts) > 1:
            n_multi += 1
        if spk_map.get(lab) and spk_map[lab] in ts:
            n_matched += 1

    # ── APP-089 §4：「混了多个说话人的段落数」（**源侧**口径）──
    # 🔴 口径：一个 ASR 段落若在时间上**跨了多个 truth 说话人**
    #   ⇒ 这一段**必然**含多个人的声音 ⇒ 算「混说话人段」。
    n_mixed_src = 0
    if truth:
        for s in segs:
            if s.get('t0') is None or s.get('t1') is None:
                continue
            a, b = float(s['t0']), float(s['t1'])
            ts = set()
            for t0, t1, tspk in truth:
                if min(b, t1) - max(a, t0) > 0:
                    ts.add(tspk)
            if len(ts) > 1:
                n_mixed_src += 1

    # ── 字幕完整度（APP-092 §3a）──
    n_sub_lines = 0
    if os.path.exists(subs):
        n_sub_lines = len([x for x in open(subs, encoding='utf-8',
                                           errors='replace') if x.strip()])
    dump = glob.glob(os.path.join(out, 'dump', '*.wav'))
    clone_txt = []
    cd = man.get('clone_dir')
    if cd and os.path.isdir(cd):
        clone_txt = [x for x in os.listdir(cd) if x.endswith('.txt')]

    res = {
        'arm': arm,
        'material': mat,
        'out_dir': out,
        'run_rc': man.get('rc'),
        'n_artifacts': man.get('n_artifacts'),
        # ── 段级 ──
        'n_tts_rows': n_rows,
        'n_synth_ok': len(synth),
        'n_voiced': n_voiced,
        'n_subtitle_only': n_sub_only,
        'n_errors': len(errs),
        'n_late_drop': len(late),
        # 🔴🔴🔳 APP-092 §2：**真实滞后秒数**（不是 `t_submit`！）
        #   🔴 **旧实现把 `t_submit`（perf_counter，约 8.2e5）写进这个字段**
        #     ⇒ 字段名说「lags」但值是**提交时刻**⇒ 完全是错的
        #     ⇒ reviewer 看数字会以为滞后了几十万秒。
        #   ⇒ 现在取 jsonl 里**逐句**的 `late_drop_lag_s`（worker 落盘）。
        'late_drop_lags_s': [r.get('late_drop_lag_s') for r in late
                             if r.get('late_drop_lag_s') is not None][:20],
        'late_drop_threshold_s': ([r.get('late_drop_threshold_s')
                                   for r in late
                                   if r.get('late_drop_threshold_s') is not None]
                                  or [None]),
        # 🔴🔴🔳 APP-090②a：**等标签等待**（次数 / 累计秒数）—— 从 jsonl 取真值
        #   ⇒ 旧实现**写死 0** ⇒ 弱标记恒真（判据形同虚设）。
        'n_label_wait': max([int(r.get('n_label_wait') or 0)
                             for r in rows] or [0]),
        'label_wait_s': max([float(r.get('label_wait_s') or 0.0)
                             for r in rows] or [0.0]),
        # ── APP-091②：中文倍率分布 ──
        'speed_p50': pct(zh_speeds, 0.50),
        'speed_p90': pct(zh_speeds, 0.90),
        'speed_min': round(min(zh_speeds), 4) if zh_speeds else None,
        'speed_max': round(max(zh_speeds), 4) if zh_speeds else None,
        'speed_buckets': {
            '<1.0': len([s for s in zh_speeds if s < 1.0]),
            '1.0-1.09': len([s for s in zh_speeds if 1.0 <= s < 1.0999]),
            '1.10-1.29': len([s for s in zh_speeds if 1.0999 <= s < 1.2999]),
            '1.30-1.49': len([s for s in zh_speeds if 1.2999 <= s < 1.4999]),
            '>=1.50': len([s for s in zh_speeds if s >= 1.4999]),
        },
        'n_speed_rows': len(zh_speeds),
        # ── 首包延迟 ──
        'first_packet_p50_s': pct(fp, 0.50),
        'first_packet_p95_s': pct(fp, 0.95),
        # ── 音色来源 ──
        'n_voice_self_ref': n_self_ref,
        'n_voice_inherited': n_inherited,
        'n_spk_label': n_with_label,
        'first_clone_voice_t_submit_s': first_voice_t,
        'first_clone_voice_src_t_s': first_clone_src_t,
        'first_clone_voice_seg': first_clone_seg,
        # ── APP-089 §4：混了多个说话人的段落数（**源侧**口径）──
        'n_mixed_spk_segs': n_mixed_src,
        # ── 说话人标签正确率 ──
        'n_truth_segs': n_truth_segs,
        'n_seg_rows': len(segs),
        'n_seg_labeled': n_labeled,
        'n_seg_multi_truth_spk': n_multi,
        'n_spk_match_truth': n_matched,
        'spk_label_map': spk_map,
        'spk_match_rate': (round(n_matched / n_labeled, 4)
                           if n_labeled else None),
        # ── 字幕完整度 ──
        'n_subtitle_lines': n_sub_lines,
        # ── 结构检查（APP-089 §4）──
        'n_clone_txt_files': len(clone_txt),
        'n_dump_wav': len(dump),
        # ── CER：待 reviewer 回转写 ──
        'cer': None,
        'cer_note': '待 reviewer 在本机用 MiniMax 回转写（本机不调 MiniMax）',
        'wav_for_review': os.path.join(out, 'mix.wav'),
        'subs_for_review': subs if os.path.exists(subs) else None,
        'src': {
            'tts_jsonl': tj,
            'spk_seg_jsonl': sj,
            'subtitles': subs,
            'run_manifest': man_p,
        },
    }
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='after')
    ap.add_argument('--materials', default='dialog3')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    mats = [x for x in args.materials.split(',') if x]
    res = {'arm': args.arm, 'materials': mats, 'scores': []}
    for m in mats:
        res['scores'].append(score_arm(args.arm, m))
    out_p = args.out or os.path.join(
        EVID, 'app370_app089_scores_%s.json' % args.arm)
    with open(out_p, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print('OUT=%s' % out_p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
