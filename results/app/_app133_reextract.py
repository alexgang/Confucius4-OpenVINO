#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：**从落盘的原始文件重抽**整链指标（修正字段名口径）。

## 为什么需要这一步（判据工程）

整链脚本在 **17:45 启动**时加载了当时的 `read_metrics()`；本轮随后核对
**实测的 `margin.json` 字段名**时发现两处口径错：

| 我方当时取的字段 | `margin.json` 里**实际**的字段 | 后果 |
|---|---|---|
| `margin_summary.peak_lag_sec` | `margin_summary.max_lag_sec` | 积压峰值取到 `None` |
| `margin_summary.lag_curve.end_sec` | `adaptive_speed.lag_curve.end_sec` | 收尾积压取到 `None` |

⇒ **原始数据（`bgkeep_e2e.json` ＋ `margin.json`）本身是对的**
（实测 `max_lag_sec`、`lag_curve` 都在）⇒ **不用重跑 30 分钟的链**
⇒ 只要**按正确的字段名重抽一遍**即可。

## 纪律

- **只读**臂目录里的原始文件 ⇒ **不重跑链**；
- 抽出后**覆盖**证据 json 里的 `arms[i].metrics`（其余字段逐字不动）；
- 🔴 **不臆造**：取不到的字段仍写 `None` ＋ 记进 `missing`；
- 写前备份 ＋ 写后逐字节复核 ＋ `missing` 清单对照。
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from _app133_chain_v26 import read_metrics  # noqa: E402  （**修正后**的版本）

RESULTS = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RESULTS, 'app133_chain_v26_evidence.json')
TMP = os.environ.get('TEMP', '/tmp')


def main():
    with open(EVID, 'rb') as f:
        orig = f.read()
    shutil.copy2(EVID, os.path.join(TMP, 'app133_chain_v26_evidence.json.bak'))
    rep = json.loads(orig.decode('utf-8'))

    changed = []
    for a in rep.get('arms') or []:
        old = a.get('metrics') or {}
        new = read_metrics(a)
        # 保留原有的 missing 语义，但以新抽取为准
        a['metrics'] = new
        diffs = []
        for k in sorted(set(old) | set(new)):
            ov, nv = old.get(k), new.get(k)
            if isinstance(ov, (dict, list)) or isinstance(nv, (dict, list)):
                if json.dumps(ov, ensure_ascii=False, sort_keys=True) != \
                        json.dumps(nv, ensure_ascii=False, sort_keys=True):
                    diffs.append(k)
            elif ov != nv:
                diffs.append('%s: %s → %s' % (k, ov, nv))
        changed.append((a.get('arm'), diffs))

    out = json.dumps(rep, ensure_ascii=False, indent=2)
    tmp = EVID + '.tmp_reextract'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)
    os.replace(tmp, EVID)
    with open(EVID, 'rb') as f:
        after = f.read()
    if after != out.encode('utf-8'):
        print('FAIL: 写后逐字节复核失败')
        return 2

    print('已重抽 %d 条臂的指标' % len(changed))
    for arm, diffs in changed:
        print('--- %s：%d 处变化' % (arm, len(diffs)))
        for d in diffs[:40]:
            print('    ', d)
    # 关键字段抽查
    for a in rep.get('arms') or []:
        m = a.get('metrics') or {}
        print('[%s] dubs=%s 丢句=%s 语速max=%s synth_rtf=%s 积压峰值=%s 收尾积压=%s'
              % (a.get('arm'), m.get('dubs'), m.get('n_dropped_dub'),
                 m.get('speed_max'), m.get('synth_rtf'),
                 m.get('max_lag_sec'), m.get('lag_curve_end_sec')))
        if m.get('missing'):
            print('    missing:', m.get('missing'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
