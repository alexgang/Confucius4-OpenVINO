#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app036_text_integrity_gate_test.py —— 验证「文本编码完整性」闸门（§36）。

背景
----
§29.7 记录过 U+FFFD 乱码 → §31.4 修掉了**两处** ⇒ 但 §32 的提交
`6a1dee6` **又把乱码写回了同一个文件**（`device_config.py` 的 docstring）。

⇒ 「修掉一处」≠「这一类不会再来」⇒ 本轮把「文本编码完整性」
   **加进内部素材闸门**（`check_internal_material.py`），并用本脚本验证：

  T1  乱码文件（U+FFFD）⇒ **必须命中**（否则闸门形同虚设）；
  T2  非 UTF-8 文本 ⇒ **必须命中**；
  T3  **放行名单内**的文件有乱码 ⇒ **仍必须命中**
      （🔴 关键：「允许提到内部素材的名字」≠「允许乱码」）；
  T4  第三方依赖目录（site-packages / 随包 python / models）⇒ **不命中**
      （避免对不是 App 交付责任的文件误报 ⇒ 闸门被绕过）；
  T5  干净文件 ⇒ **不命中**（无误报）；
  T6  真实客户包 v1.5 ⇒ **0 命中**（闸门不误伤交付物）。

口径：**不推理、不测速、不占 GPU、不调 MiniMax**（纯文件 IO）。

用法
----
    python results/app/app036_text_integrity_gate_test.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = os.path.join(REPO, 'check_internal_material.py')
import sys as _sys
_sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import pkg_paths as _pkg_paths

PKG_V15 = _pkg_paths.discover_pkg_dir()

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


def load_gate():
    spec = importlib.util.spec_from_file_location('gate_mod', GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(rel, data) -> str:
    d = tempfile.mkdtemp()
    full = os.path.join(d, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if isinstance(data, str):
        data = data.encode('utf-8')
    with open(full, 'wb') as f:
        f.write(data)
    return d


def main():
    print('=' * 70)
    print('§36 文本编码完整性闸门 —— 自测')
    print('=' * 70)
    g = load_gate()
    allow = list(g.DEFAULT_ALLOW)
    allow_exact = tuple(g.DEFAULT_ALLOW_EXACT)

    # ── T1 U+FFFD 必须命中 ────────────────────────────────────────
    d = write('app/x.py', b'clean line\nbad \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd line\n')
    hits = g.scan_dir(d, allow, False, allow_exact)
    check('T1 U+FFFD 文件被命中', bool(hits), str(hits[:1]))
    check('T1 命中原因标注为编码规则',
          bool(hits) and hits[0][1].startswith('编码规则'), str(hits[:1]))

    # ── T2 非 UTF-8 文本必须命中 ──────────────────────────────────
    d = write('app/y.md', b'\xff\xfe\x00bad bytes\n')
    hits = g.scan_dir(d, allow, False, allow_exact)
    check('T2 非 UTF-8 文本被命中', bool(hits), str(hits[:1]))

    # ── T3 放行名单内的乱码仍必须命中 ──────────────────────────────
    # 🔴 `live_caption/device_config.py` 在 DEFAULT_ALLOW 里（合法提到内部素材名）
    d = write('live_caption/device_config.py',
              b'line \xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\n')
    hits = g.scan_dir(d, allow, False, allow_exact)
    check('T3 放行名单内的乱码仍被命中（不因放行而放过）',
          bool(hits), str(hits[:1]))

    # ── T4 第三方依赖目录不命中 ───────────────────────────────────
    for rel in ('python/Lib/site-packages/x.py',
                'models/tokenizer/tokenizer.json',
                'python/Lib/site-packages/sub/deep.py'):
        d = write(rel, b'\xff\xfe bad \xef\xbf\xbd\n')
        hits = g.scan_dir(d, allow, False, allow_exact)
        check('T4 第三方目录不命中：%s' % rel, not hits, str(hits[:1]))

    # ── T5 干净文件不命中 ─────────────────────────────────────────
    d = write('app/clean.py', '# 中文注释正常\nprint("ok")\n')
    hits = g.scan_dir(d, allow, False, allow_exact)
    check('T5 干净文件不命中（无误报）', not hits, str(hits[:1]))

    # ── T6 真实客户包 v1.5 ⇒ 0 命中 ───────────────────────────────
    if os.path.isdir(PKG_V15):
        hits = g.scan_dir(PKG_V15, allow, False, allow_exact)
        check('T6 真实客户包 v1.5 闸门 0 命中', not hits,
              ('%d 条: %s' % (len(hits), hits[:3])) if hits else '')
    else:
        check('T6 真实客户包 v1.5 存在', False, PKG_V15)

    # ── 证据落盘 ──────────────────────────────────────────────────
    ev = {
        'test': 'app036_text_integrity_gate',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pass': len(PASS),
        'fail': len(FAIL),
        'verdict': 'PASS' if not FAIL else 'FAIL',
        'failed_items': FAIL,
        'passed_items': PASS,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'app036_text_integrity_gate_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print()
    print('证据：%s' % out)
    print('判定：%s （PASS %d / FAIL %d）' % (ev['verdict'], ev['pass'], ev['fail']))
    return 1 if FAIL else 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
