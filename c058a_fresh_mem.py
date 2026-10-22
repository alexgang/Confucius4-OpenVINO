"""c058a_fresh_mem.py — C-058②: fresh-process 内存测量编排器

reviewer 要求（CORRECTIONS.md ②）：
  「每个配置、每次测量用全新子进程（加载 → warmup → 稳态采样 → 退出），≥3 次；
    iGPU 显存与 WS/USS 并列报告，主指标用 iGPU 显存」
  「请用 fresh-process 分别测 FP16 / INT8 / INT4+FP16lm_head / INT4 全量四种
    decoder 编译后的显存，与 IR 大小逐项对账」

本脚本按配置矩阵起子进程，每个 (配置 × 轮次) 都是全新 python 进程，
跨配置零污染；结果取中位数并报告极差。

用法：.venv python c058a_fresh_mem.py [--reps 3]
输出：reports/c058_fresh_mem.json + 控制台表格 + 对账分析
"""
import os
import sys
import json
import time
import subprocess
import statistics as st

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

PY = sys.executable
WORKER = 'c058a_fresh_mem_worker.py'
ENC_FP16 = 'models/ov-encoder-segment-reviewer'
ENC_INT4 = 'models/ov-encoder-segment-reviewer-int4'

# (tag, encoder, decoder, 说明)
MATRIX = [
    ('FP16 enc + INT8 dec', ENC_FP16, 'models/ov-int8-past', '当前交付基线'),
    ('FP16 enc + FP16 dec', ENC_FP16, 'models/ov-fp16-past', '全 FP16 参考'),
    ('INT4 enc + INT8 dec', ENC_INT4, 'models/ov-int8-past', '推荐组合候选'),
    ('FP16 enc + INT4lmFP16 dec', ENC_FP16,
     'models/ov-int4-lmfp16-past', '次优 INT4 构建'),
    ('FP16 enc + INT4全量 dec', ENC_FP16,
     'models/ov-int4-lmhead-past', 'C-056 推荐 INT4 构建'),
    ('INT4 enc + INT4全量 dec', ENC_INT4,
     'models/ov-int4-lmhead-past', '理论最省组合'),
]
OUT = 'reports/c058_fresh_mem.json'


def run_one(enc, dec, tag):
    p = subprocess.run(
        [PY, WORKER, enc, dec, tag],
        capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=600)
    for line in p.stdout.splitlines():
        if line.startswith('###JSON###'):
            return json.loads(line[len('###JSON###'):])
    print(f'  !! 子进程失败 [{tag}]')
    if p.stderr:
        print('     ' + p.stderr.strip().splitlines()[-1][:150])
    return None


def main():
    reps = 3
    if '--reps' in sys.argv:
        reps = int(sys.argv[sys.argv.index('--reps') + 1])

    print(f'[c058a] fresh-process 内存测量  {len(MATRIX)} 配置 × {reps} 轮'
          f'（每轮一个全新 python 进程）', flush=True)

    runs = {t: [] for t, _, _, _ in MATRIX}
    for rep in range(reps):
        for tag, enc, dec, note in MATRIX:
            r = run_one(enc, dec, tag)
            if r:
                runs[tag].append(r)
            print(f'  rep{rep} {tag:<28} IR={r["ir_total_mib"] if r else 0:>7.1f}  '
                  f'iGPU={r["igpu_mib"] if r else 0:>7.1f}  '
                  f'WS={r["ws_steady_mib"] if r else 0:>7.1f}  '
                  f'USS={r["uss_steady_mib"] if r else 0:>7.1f} MB', flush=True)
        time.sleep(2)   # 让前一进程完全退出、显存释放

    print('\n=== 中位数（跨 %d 轮独立进程）===' % reps, flush=True)
    print(f'{"配置":<28}{"IR MiB":>9}{"iGPU MiB":>10}{"WS":>9}{"USS":>9}'
          f'{"iGPU−IR":>9}{"极差":>8}')
    med = {}
    for tag, enc, dec, note in MATRIX:
        rs = runs[tag]
        if not rs:
            continue
        g = lambda k: st.median([r[k] for r in rs])
        med[tag] = {k: g(k) for k in
                    ('ir_total_mib', 'igpu_mib', 'ws_steady_mib', 'uss_steady_mib',
                     'enc_ir_mib', 'dec_ir_mib')}
        med[tag]['igpu_range'] = round(
            max(r['igpu_mib'] for r in rs) - min(r['igpu_mib'] for r in rs), 1)
        med[tag]['ws_range'] = round(
            max(r['ws_steady_mib'] for r in rs)
            - min(r['ws_steady_mib'] for r in rs), 1)
        med[tag]['note'] = note
        med[tag]['runs'] = rs
        m = med[tag]
        print(f'{tag:<28}{m["ir_total_mib"]:>9.1f}{m["igpu_mib"]:>10.1f}'
              f'{m["ws_steady_mib"]:>9.1f}{m["uss_steady_mib"]:>9.1f}'
              f'{m["igpu_mib"] - m["ir_total_mib"]:>9.1f}'
              f'{m["igpu_range"]:>8.1f}')

    # ── 对账：iGPU 显存差 vs IR 差（reviewer 追问的 2 倍异常）──
    # C-059#2：不要急着给「已解释」的结论。先看比值的**不确定度**是否大到
    # 能解释 1.72 —— reviewer 指出 INT8 基线 iGPU 极差就有 250 MiB(3 轮)，
    # ΔiGPU=350 的不确定度约 ±125，换算后比值可在 1.1–2.3 之间。
    print('\n=== 对账：iGPU 显存差 vs IR 体积差 ===', flush=True)
    base = 'FP16 enc + INT8 dec'
    ratios = {}
    if base in med:
        b = med[base]
        print(f'{"配置":<28}{"ΔiGPU":>9}{"ΔIR":>9}{"比值":>8}{"比值区间":>18}  说明')
        for tag, _, _, _ in MATRIX:
            if tag == base or tag not in med:
                continue
            m = med[tag]
            di = m['igpu_mib'] - b['igpu_mib']
            dr = m['ir_total_mib'] - b['ir_total_mib']
            ratio = di / dr if abs(dr) > 1 else float('nan')
            # 用两配置各自 iGPU 极差的一半作为 ΔiGPU 的 ± 不确定度，
            # 传播到比值上（|dr| 固定）
            half = (m['igpu_range'] + b['igpu_range']) / 4.0   # 极差/2 再取均值
            lo = (di - half) / dr if dr < 0 else (di + half) / dr
            hi = (di + half) / dr if dr < 0 else (di - half) / dr
            a, bb_ = min(lo, hi), max(lo, hi)
            ratios[tag] = {'ratio': round(ratio, 2),
                           'ci_approx': [round(a, 2), round(bb_, 2)],
                           'half_uncertainty_mib': round(half, 1)}
            print(f'{tag:<28}{di:>9.1f}{dr:>9.1f}{ratio:>8.2f}'
                  f'{"[%.2f, %.2f]" % (a, bb_):>18}  {m["note"]}')

        # C-059#2 判据：1.0 是否落在区间内 → 落在区间内说明「异常」可能只是噪声
        print('\n--- C-059#2 判读 ---')
        for tag, v in ratios.items():
            a, bb_ = v['ci_approx']
            covers_1 = a <= 1.0 <= bb_
            covers_15 = a <= 1.5 <= bb_
            print(f'  {tag:<28} 比值 {v["ratio"]:.2f}  区间 {v["ci_approx"]}  '
                  f'{"包含 1.0 → 差异可能仅是测量噪声 ✓" if covers_1 else "不含 1.0 → 需进一步排查"}')
        special = ratios.get('FP16 enc + INT4lmFP16 dec')
        if special:
            a, bb_ = special['ci_approx']
            print(f'\n  ⚠️ 「2 倍异常」按 C-059#2 降级为**假设**：'
                  f'比值区间 {a:.2f}–{bb_:.2f}'
                  f'{"已覆盖 1.0~1.5，噪声足以解释" if a <= 1.0 else "仍需排查"}；'
                  f'报告写「未解释，可能是测量噪声」。')
            print(f'  换头条仍成立（依据是 846 vs 1440 MiB 与 C-056，与该比值无关）。')

    out = {'generated': time.strftime('%Y-%m-%d %H:%M'), 'reps': reps,
           'method': 'fresh subprocess per (config, rep); '
                     'load -> warmup 2s -> steady sample 8s (last 50%) -> exit',
           'ratios_vs_int8': ratios,
           'medians': {k: {kk: vv for kk, vv in v.items() if kk != 'runs'}
                       for k, v in med.items()},
           'raw': runs}
    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}', flush=True)


if __name__ == '__main__':
    main()
