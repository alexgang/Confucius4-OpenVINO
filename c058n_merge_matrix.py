"""c058n_merge_matrix.py — 合并 C-059#1 重导的 (c) 到完整配方矩阵

`c058d --only-c` 会用单元素列表覆盖 `reports/c058_int4_matrix.json`，
本脚本从 `.bak` 恢复原有 (a)(b)(旧 c)，再把新 (c) 并进去，
并按 C-059#1 的新门槛（≤1100 MiB）重算判定，同时补齐 backup_mode / all_layers。

用法：.venv python c058n_merge_matrix.py
"""
import os
import sys
import json

BAK = 'reports/c058_int4_matrix.json.bak'
CUR = 'reports/c058_int4_matrix.json'
OUT = 'reports/c058_int4_matrix.json'
IR_GATE = 1100.0     # C-059#1：900 → 1100 MiB


def mb(p):
    return round(os.path.getsize(p) / 1024 ** 2, 1) if os.path.exists(p) else None


def main():
    new = json.load(open(CUR, encoding='utf-8'))
    new_c = [v for v in new['variants'] if 'r08-i8b' in v['name']]
    assert new_c, '当前 JSON 里没有新 (c)'

    old = json.load(open(BAK, encoding='utf-8')) if os.path.exists(BAK) else \
        {'variants': []}

    merged = []
    for v in old['variants']:
        n = v['name']
        if 'r08' in n and 'i8b' not in n:
            continue                      # 旧 (c) 被新 (c) 取代
        # 补齐 C-059#1 要求显式写明的字段
        v.setdefault('backup_mode', 'NONE(默认)')
        v.setdefault('all_layers', True)
        v['passes_ir_1100'] = (v.get('ir_mib') or 1e9) <= IR_GATE
        v['passes_ir_900'] = (v.get('ir_mib') or 1e9) <= 900
        merged.append(v)
    merged += new_c

    out = {'generated': new.get('generated'), 'src': new.get('src'),
           'calib_max_sec': new.get('calib_max_sec'),
           'ir_gate_mib': IR_GATE,
           'gate_note': ('C-059#1：门槛由 ≤900 放宽到 ≤1100 MiB —— 混合精度的意义就是'
                         '用少量体积换回精度，不该把 ratio<1 的配方整个排除；'
                         '1100 MiB 仍比 INT8 的 1643 MiB 小 ≥33%'),
           'variants': merged}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'{"配方":<26}{"IR MiB":>9}{"≤1100":>7}  {"backup_mode":<14}构成')
    for v in merged:
        comp = ' | '.join(f'{k} {x}' for k, x in v.get('by_precision', {}).items()
                          if x > 0.5)
        print(f'{v["name"]:<26}{v.get("ir_mib", 0):>9.1f}'
              f'{"✓" if v.get("passes_ir_1100") else "✗":>7}  '
              f'{v.get("backup_mode", "-"):<14}{comp}')
    print(f'\nupdated -> {OUT}  (共 {len(merged)} 个配方)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
