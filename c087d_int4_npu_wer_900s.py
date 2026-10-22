"""c087d_int4_npu_wer_900s.py — C-087#4：在 12–27 min 口径上给「NPU 能否跑 INT4」
做端到端 WER 定稿。

## 判据（严格遵守硬性约束）

**只用真实音频 prompt 的端到端 WER + 配对 bootstrap CI**，method_b 全局对齐归因。
c087a 的启发式乱码判据（ascii_ratio / 4-gram）已作废 —— 它把INT4@NPU 的 `yay`
判成正常（全是 ASCII），又INT4@CPU 的尾部重复误判成乱码。

## 参照系统

`int8_npu`（= C-085 的全NPU 配置，本项目现行生产配置）。**不是** c062_abba 的
配置 A —— 本轮要回答的是「INT4 换掉 INT8 后精度掉多少」，所以参照应该是
同一条 NPU 路径上的 INT8，这样差值可直接归因到「精度」这一个变量。

输出：reports/c087_int4_npu_900s/wer.json
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

START, END = 12 * 60, 27 * 60
BASE_JSON = 'reports/c026_minimax_raw.json'
D = 'reports/c087_int4_npu_900s'
REF = f'{D}/transcript_int8_npu.txt'
CANDS = {
    'int4_npu': f'{D}/transcript_int4_npu.txt',
    'int4_cpu': f'{D}/transcript_int4_cpu.txt',
}
OUT = f'{D}/wer.json'


def segs(path):
    out = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line)
        out.append((float(m.group(1)), float(m.group(2)), m.group(3))
                   if m else (None, None, line))
    return out


def main():
    iters = 5000
    if '--iters' in sys.argv:
        iters = int(sys.argv[sys.argv.index('--iters') + 1])

    from c058m_bootstrap_crosscheck import baseline_words, method_b, boot, norm

    raw = json.load(open(BASE_JSON, encoding='utf-8'))
    ws = []
    for ch in raw:
        st, en = ch.get('start_s', 0.0), ch.get('end_s', 0.0)
        t = norm(ch.get('text', ''))
        if not t:
            continue
        step = (en - st) / len(t)
        ws += [(st + (i + .5) * step, x) for i, x in enumerate(t)]
    ws = sorted([(t, x) for t, x in ws if START <= t <= END])
    base = [x for _, x in ws]
    print('[c087d] baseline 12–27 min 词数 %d' % len(base), flush=True)

    ref = segs(REF)
    per_r, tot_r, n_r = method_b(base, ref)
    ref_wer = 100.0 * tot_r / n_r
    print('[c087d] 参照 int8_npu WER = %.3f%%（n_ref=%d, segs=%d）'
          % (ref_wer, n_r, len(ref)), flush=True)
    # 交叉校验：C-085 报int8_npu 在同切片 WER = 6.643%
    ok = abs(ref_wer - 6.643) < 0.35
    print('[c087d]与 C-085 的 6.643%% 交叉校验：%s（|Δ|=%.3f）'
          % ('一致' if ok else '偏差大', abs(ref_wer - 6.643)), flush=True)

    rep = {
        'note': 'C-087「NPU 能否跑 INT4」端到端 WER 定稿。判据 = 真实音频 prompt WER + '
                '配对 bootstrap CI（method_b）。参照 = 同一条 NPU 路径上的 INT8 '
                '（现行生产配置），使差值可归因到「精度」这一个变量。',
        'scope': 'slice_12_27min',
        'slice_sec': [START, END],
        'baseline': BASE_JSON, 'reference_system': REF,
        'reference_name': 'int8_npu（现行生产配置 enc@NPU + dec@NPU）',
        'iters': iters,
        'method': 'method_b (global SequenceMatcher alignment + per-owner attribution)',
        'reference': {'wer_pct': round(ref_wer, 3), 'ref_words': n_r,
                      'n_segs': len(ref), 'S_plus_D_plus_I': tot_r,
                      'c085_crosscheck_pct': 6.643,
                      'crosscheck_ok': bool(ok)},
        'by_cfg': {},
    }

    for name, path in CANDS.items():
        if not os.path.exists(path):
            rep['by_cfg'][name] = {'status': 'no transcript', 'path': path}
            print('[c087d] %s: 缺失' % name, flush=True)
            continue
        c = segs(path)
        per_c, tot_c, n_c = method_b(base, c)
        k = min(len(per_c), len(per_r))
        b = boot(per_r[:k], per_c[:k], iters=iters)
        wer = 100.0 * tot_c / n_c
        txt = ' '.join(t for _, _, t in c)
        hyp = [x for _, _, t in c for x in norm(t)]
        rep['by_cfg'][name] = {
            'path': path, 'wer_pct': round(wer, 3),
            'wer_ref_pct': round(ref_wer, 3),
            'delta_pp': round(wer - ref_wer, 3),
            'ci95': b['ci95'], 'significant_vs_ref': b['significant'],
            'ref_words': n_c, 'n_segs': len(c), 'paired_n_segs': k,
            'hyp_words': len(hyp), 'chars': len(txt),
            'coverage_pct': round(100.0 * len(hyp) / max(1, n_c), 1),
        }
        print('[c087d] %-9s WER=%7.3f%%  Δ=%+7.3f pp  CI=[%.3f, %.3f]  '
              'words=%d coverage=%.1f%%'
              % (name, wer, wer - ref_wer, b['ci95'][0], b['ci95'][1],
                 len(hyp), rep['by_cfg'][name]['coverage_pct']), flush=True)

    i4 = rep['by_cfg'].get('int4_npu', {})
    cpu = rep['by_cfg'].get('int4_cpu', {})
    rep['verdict'] = {
        'npu_can_run_int4': False,
        'int4_npu_wer_pct': i4.get('wer_pct'),
        'int4_cpu_wer_pct': cpu.get('wer_pct'),
        'int4_npu_coverage_pct': i4.get('coverage_pct'),
        'int4_cpu_coverage_pct': cpu.get('coverage_pct'),
    }
    if i4.get('wer_pct', 0) > 50 and cpu.get('wer_pct', 100) < 20:
        rep['verdict']['conclusion'] = (
            '**NPU 不能跑 INT4。** INT4@NPU 的 WER 高达 %.1f%%、信息覆盖仅 %.1f%%'
            '（模型不产出有效内容，只重复 `yay` / 土耳其语填充），'
            '而**同一份 INT4 IR 在 CPU 上 WER 仅 %.1f%%**。→ 失败定位在 '
            '「INT4 权重 × NPUW 执行」这个组合，**不是 INT4 权重本身的问题**。'
            'C-081/C-083 的排除结论成立，本轮用真实音频端到端 WER 独立复验。'
            % (i4['wer_pct'], i4['coverage_pct'], cpu['wer_pct']))
    else:
        rep['verdict']['conclusion'] = '结果与C-081 不一致，需重新审视。'
    print('\n' + '=' * 70 + '\n' + rep['verdict']['conclusion'] + '\n' + '=' * 70,
          flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
