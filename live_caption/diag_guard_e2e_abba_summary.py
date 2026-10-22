r"""diag_guard_e2e_abba_summary.py — 汇总 ABBA 端到端复现实验，判读机器噪声 vs 判据效应

用法：
  python diag_guard_e2e_abba_summary.py <abba目录>

判读逻辑（与 STATUS_hy.md 的 H-004 教训一致）：
  * 组内极差（同一判据两次跑的差）大 → 机器噪声占主导
  * 组内稳定 + 组间稳定分离 → 差异是真实的
  * ABBA 顺序能抵消**单调漂移**（越跑越慢/越跑越快）：
    A 在位置 1、4，B 在位置 2、3 → 若存在单向漂移，两组均值仍然可比
"""

from __future__ import annotations

import os
import sys
import json
import glob


def main():
    d = os.path.abspath(sys.argv[1])
    files = sorted(glob.glob(os.path.join(d, '*.json')))
    if not files:
        print('目录里没有 json:', d)
        return

    runs = []
    for f in files:
        j = json.load(open(f, encoding='utf-8'))
        runs.append(dict(
            file=os.path.basename(f),
            tag=j.get('tag', '?'),
            rel=j.get('rel', '?'),
            drop=j.get('drop', '?'),
            wall=j['wall'],
            end=j['stamps'][-1] if j['stamps'] else 0.0,
            nseg=len(j['finals']),
            finals=j['finals'],
            stamps=j['stamps'],
        ))

    # 按文件名里的序号排（保持 ABBA 的执行顺序）
    def order_key(r):
        base = os.path.splitext(r['file'])[0]
        return base

    print('=' * 78)
    print(f'ABBA 复现实验汇总  目录: {d}')
    print('=' * 78)
    print(f'{"文件":<28}{"判据":<8}{"段数":<7}{"墙钟(s)":<11}{"末段定稿":<11}{"音频":<8}')
    for r in runs:
        print(f'{r["file"]:<28}rel={r["rel"]:<5}{r["nseg"]:<7}'
              f'{r["wall"]:<11.1f}{r["end"]:<11.1f}720.0')

    groups = {}
    for r in runs:
        groups.setdefault(r['rel'], []).append(r)

    print('\n' + '=' * 78)
    print('【分组统计】')
    print('=' * 78)
    for rel in sorted(groups):
        rs = groups[rel]
        walls = [x['wall'] for x in rs]
        ends = [x['end'] for x in rs]
        label = '基线 rel=0 (绝对判据)' if rel == '0' else '新判据 rel=1 (绝对∪相对)'
        print(f'\n【{label}】{len(rs)} 次')
        print(f'   墙钟  : {["%.1f" % w for w in walls]}   '
              f'极差={max(walls)-min(walls):.1f}s  均值={sum(walls)/len(walls):.1f}s')
        print(f'   末段定稿: {["%.1f" % e for e in ends]}   '
              f'极差={max(ends)-min(ends):.1f}s')
        print(f'   段数  : {[x["nseg"] for x in rs]}')
        if len(rs) >= 2:
            same = rs[0]['finals'] == rs[1]['finals']
            print(f'   两次定稿文本逐字相同: {same}')
            if not same:
                wa = [w for f in rs[0]['finals'] for w in f.lower().split()]
                wb = [w for f in rs[1]['finals'] for w in f.lower().split()]
                print(f'   词数: {len(wa)} vs {len(wb)}')

    print('\n' + '=' * 78)
    print('【判读】')
    print('=' * 78)
    if '0' in groups and '1' in groups:
        wa = [x['wall'] for x in groups['0']]
        wb = [x['wall'] for x in groups['1']]
        sa = max(wa) - min(wa)
        sb = max(wb) - min(wb)
        gap = (sum(wb) / len(wb)) - (sum(wa) / len(wa))
        within = max(sa, sb)
        print(f'  A(rel=0) 自身极差 : {sa:.1f}s   均值 {sum(wa)/len(wa):.1f}s')
        print(f'  B(rel=1) 自身极差 : {sb:.1f}s   均值 {sum(wb)/len(wb):.1f}s')
        print(f'  B − A 均值差      : {gap:+.1f}s')
        print()
        if within > 15 and within > abs(gap) * 0.5:
            print('  ⚠️  **组内极差与组间差同量级 → 机器噪声占主导**')
            print('      端到端墙钟差**不可用于评价判据**。')
            print('      结论：首轮「末段晚 56.8s」不是判据引起的，是测量环境的漂移。')
        elif gap > 5:
            print('  ✅ 组内可复现、组间稳定分离 → 差异稳定，需查真实成因。')
        elif gap < -5:
            print('  ✅ 新判据反而更快（差异超出组内噪声），判据未造成退化。')
        else:
            print('  ✅ 组间差小于组内噪声 → **两组无显著差异**，判据不影响吞吐。')


if __name__ == '__main__':
    main()
