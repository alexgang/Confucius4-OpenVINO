"""c087b_int4_wer.py — C-087#2：用**端到端 WER** 给「NPU 能否跑 INT4」定稿。

## 为什么必须重做判据

`c087a` 的启发式乱码判据（ascii_ratio + 4-gram 重复）**两头都判错了**：

- `int4_npu` 输出 `yay` / `language English`，全是 ASCII → `ascii_ratio=1.0`，
  又因为总长 36 字符 > 20 且总词数 3 < 6，**绕过了所有判据被判成「正常」**；
- `int4_cpu` 第二段末尾有真实的重复退化（`Twenty-eight. A. C.` 循环），
  4-gram 重复触发 → **被误判为乱码**，但它整体是人话。

启发式不可靠。按本项目硬性约束，**精度判据只用真实音频 prompt 的端到端 WER +
配对 bootstrap CI**。这里就按这个来，参照 = 同一切片的 INT8@NPU 现行生产配置。

## 口径

- 切片：720–760 s（40 s 真实音频），与 c087a 一致
- 参照：INT8@NPU（现行生产配置，decoder 与 encoder 同为 NPU）
- 候选：INT4@NPU、INT4@CPU
- method_b 全局对齐归因 + 配对 bootstrap 5000 次（method A 已被 C-059#4 证伪）

输出：reports/c087_int4_npu/wer.json
"""
import json
import os
import re
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

START, END = 720, 760
BASE_JSON = 'reports/c026_minimax_raw.json'
REF = 'reports/c087_int4_npu/transcript_int8_npu.txt'
CANDS = {
    'int4_npu': 'reports/c087_int4_npu/transcript_int4_npu.txt',
    'int4_cpu': 'reports/c087_int4_npu/transcript_int4_cpu.txt',
}
OUT = 'reports/c087_int4_npu/wer.json'


def segs_from_transcript(path):
    segs = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        if m:
            segs.append((float(m.group(1)), float(m.group(2)), m.group(3)))
        else:
            segs.append((None, None, line))
    return segs


def main():
    iters = 5000
    if '--iters' in sys.argv:
        iters = int(sys.argv[sys.argv.index('--iters') + 1])

    from c058m_bootstrap_crosscheck import baseline_words, method_b, boot, norm
    from collections import Counter

    raw = json.load(open(BASE_JSON, encoding='utf-8'))
    words = []
    for ch in raw:
        st = ch.get('start_s', 0.0)
        en = ch.get('end_s', st)
        ws = norm(ch.get('text', ''))
        if not ws:
            continue
        step = (en - st) / len(ws)
        words += [(st + (i + .5) * step, w) for i, w in enumerate(ws)]
    words = sorted([(t, w) for t, w in words if START <= t <= END])
    base_words = [w for _, w in words]
    print('[c087b] baseline 切片词数 %d（%d–%d s）'
          % (len(base_words), START, END), flush=True)

    ref_segs = segs_from_transcript(REF)
    per_r, tot_r, n_r = method_b(base_words, ref_segs)
    ref_wer = 100.0 * tot_r / n_r
    print('[c087b] 参照 INT8@NPU WER = %.3f%%（n_ref=%d, segs=%d）'
          % (ref_wer, n_r, len(ref_segs)), flush=True)

    rep = {
        'note': 'C-087「NPU 能否跑 INT4」的定稿判据：真实音频 prompt 端到端 WER + 配对 '
                'bootstrap CI。**废弃 c087a 的启发式乱码判据**（ascii_ratio 对 `yay` '
                '返回 1.0；4-gram 重复把INT4@CPU 的尾部退化误判为乱码）。',
        'scope': 'slice_720_760s_40s',
        'baseline': BASE_JSON,
        'reference_system': REF,
        'reference_name': 'int8_npu（现行生产配置，enc@NPU + dec@NPU）',
        'iters': iters,
        'method': 'method_b (global SequenceMatcher alignment + per-owner attribution)',
        'reference': {'wer_pct': round(ref_wer, 3), 'ref_words': n_r,
                      'n_segs': len(ref_segs), 'S_plus_D_plus_I': tot_r},
        'by_cfg': {},
    }

    for name, path in CANDS.items():
        if not os.path.exists(path):
            rep['by_cfg'][name] = {'status': 'no transcript', 'path': path}
            continue
        c_segs = segs_from_transcript(path)
        per_c, tot_c, n_c = method_b(base_words, c_segs)
        k = min(len(per_c), len(per_r))
        b = boot(per_r[:k], per_c[:k], iters=iters)
        wer_c = 100.0 * tot_c / n_c
        hyp = [w for _, _, t in c_segs for w in norm(t)]
        d = {'path': path,
             'wer_pct': round(wer_c, 3),
             'wer_ref_pct': round(ref_wer, 3),
             'delta_pp': round(wer_c - ref_wer, 3),
             'ci95': b['ci95'],
             'significant_vs_ref': b['significant'],
             'ref_words': n_c, 'n_segs': len(c_segs), 'paired_n_segs': k,
             'hyp_words': len(hyp),
             'coverage_pct': round(100.0 * len(hyp) / max(1, n_c), 1),
             }
        rep['by_cfg'][name] = d
        print('[c087b] %-10s WER=%8.3f%%  Δ=%+8.3f pp  CI=[%.3f, %.3f]  '
              'seg=%d hyp_words=%d coverage=%.1f%%'
              % (name, wer_c, d['delta_pp'], b['ci95'][0], b['ci95'][1],
                 len(c_segs), len(hyp), d['coverage_pct']), flush=True)

    # 内容量对照：最有说服力的单一指标
    info = {}
    for name, path in [('int8_npu', REF)] + list(CANDS.items()):
        if os.path.exists(path):
            txt = ' '.join(t for _, _, t in segs_from_transcript(path))
            info[name] = {'chars': len(txt), 'words': len(txt.split())}
    rep['information_content'] = {
        'per_config': info,
        'note': '40 s 音频正常应产出约 110 词。INT4@NPU 只产出 3 词 = 信息量崩塌，'
                '这是 WER 接近 100% 的直接原因。',
    }

    i4 = rep['by_cfg'].get('int4_npu', {})
    cpu = rep['by_cfg'].get('int4_cpu', {})
    rep['verdict'] = {
        'npu_can_run_int4': bool(i4.get('wer_pct', 100) < 50
                                 and i4.get('significant_vs_ref') is False),
        'int4_npu_wer_pct': i4.get('wer_pct'),
        'int4_cpu_wer_pct': cpu.get('wer_pct'),
        'conclusion': None,
    }
    if i4.get('wer_pct', 100) > 50and cpu.get('wer_pct', 100) < 50:
        rep['verdict']['conclusion'] = (
            '**不能。** INT4 在 NPU 上 WER 接近全错（信息量崩塌到只剩几个词），'
            '而**同一份 INT4 IR 在 CPU 上 WER 正常**→ 失败定位在 '
            '「INT4 权重 × NPUW 执行」这个组合，C-081/C-083 的排除成立。'
            '本轮用真实音频端到端 WER 复验（不是 dummy prompt token 分叉），'
            '结论与之前一致。')
    else:
        rep['verdict']['conclusion'] = '结果与 C-081 记录不一致，需重新审视。'
    print('\n' + '=' * 70)
    print(rep['verdict']['conclusion'])
    print('=' * 70, flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
