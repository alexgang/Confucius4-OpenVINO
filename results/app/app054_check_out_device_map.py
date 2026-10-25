#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-054：验证 `tts_worker.resolve_out_device` 能把 **WASAPI 端点 id** 转成
sounddevice 能用的输出设备（§42.3 的修复）。

🔴 纪律（MEMORY 铁律）：
  - **不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino ⇒ 可能把进程带崩）
    ⇒ 用 `ast` 抽出 `_match_output_index` / `resolve_out_device` 两个**纯函数**原文，
    `exec` 到独立命名空间再调（它们只依赖 `sounddevice` / `soundcard`）。
  - **不播放音频、不加载模型、不占 GPU** ⇒ 不取机器锁（只做设备枚举 + 字符串匹配）。

判据：
  - 传入**真实**的 soundcard 端点 id（= GUI 实际传的值）⇒ 必须返回 int 索引，
    且该索引的 sounddevice 名字与 soundcard 名字**对得上**；
  - 传入设备名子串 / int / None ⇒ 原样（或默认）；
  - 传入垃圾串 ⇒ 返回 None（默认设备）+ 明确说明（**不静默**）。

用法（客户包 python）：
    python results/app/app054_check_out_device_map.py
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
OUT = os.path.join(HERE, 'app054_check_out_device_map.json')

WANT = ('_match_output_index', 'resolve_out_device')


def load_pure_funcs(path, names):
    """从源码里抽指定**顶层函数**的 AST 原文并 exec（不 import 该模块）。"""
    src = io.open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {}
    found = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            mod = ast.Module(body=[node], type_ignores=[])
            exec(compile(mod, '<%s>' % path, 'exec'), ns)
            found.append(node.name)
    return ns, found


def main() -> int:
    import soundcard as sc
    import sounddevice as sd

    ns, found = load_pure_funcs(SRC, WANT)
    missing = [n for n in WANT if n not in found]
    if missing:
        print('🔴 抽不到函数：%s（源码改过名？）' % missing)
        return 2
    resolve = ns['resolve_out_device']
    print('✅ 已从源码抽出纯函数：%s（未 import tts_worker）' % ', '.join(found))

    # 真实设备清单
    sds = [(i, d) for i, d in enumerate(sd.query_devices())
           if d['max_output_channels'] > 0]
    spks = list(sc.all_speakers())
    print('\nsounddevice 输出设备 %d 个 / soundcard 扬声器 %d 个' % (len(sds), len(spks)))
    for i, d in sds[:8]:
        print('  [%2d] %s' % (i, d['name']))
    for s in spks[:8]:
        print('  (sc) %-40s id=%s' % (s.name, s.id))

    cases = []
    # ① 真实端点 id（GUI 实际传的形态）
    if spks:
        s0 = spks[0]
        cases.append(('真实 WASAPI 端点 id（GUI 形态）', s0.id, s0.name))
    # ② 设备名子串
    if sds:
        nm = sds[0][1]['name']
        cases.append(('设备名子串', nm.split('(')[0].strip()[:12], None))
        cases.append(('int 索引', sds[0][0], None))
    cases.append(('None（系统默认）', None, None))
    cases.append(('垃圾串', 'zzz-not-a-device', None))

    rows = []
    ok_all = True
    print('\n=== 解析结果 ===')
    for label, val, expect_name in cases:
        try:
            dev, how = resolve(val)
        except Exception as e:
            print('  🔴 %-24s 抛异常：%s: %s' % (label, type(e).__name__, e))
            rows.append({'case': label, 'input': str(val), 'error': repr(e),
                         'ok': False})
            ok_all = False
            continue
        # 复核：解析出的索引在 sounddevice 里的名字，与 soundcard 端点名是否对得上
        got_name, match = None, None
        if isinstance(dev, int):
            got_name = sd.query_devices(dev)['name']
            if expect_name:
                a = got_name.strip().lower()
                b = expect_name.strip().lower()
                match = bool(a == b or a.startswith(b) or b.startswith(a)
                             or a in b or b in a)
        elif isinstance(dev, str):
            got_name = sd.query_devices(dev, 'output')['name']
        ok = True
        if expect_name and isinstance(dev, int):
            ok = bool(match)          # 端点 id 必须映射到**同名**设备
        if label == '垃圾串':
            ok = (dev is None)        # 必须回退默认且**说明原因**
        ok_all = ok_all and ok
        print('  %s %-24s ⇒ dev=%-6r  %s' % ('✅' if ok else '🔴', label, dev, how))
        if got_name:
            print('       实际设备名：%s   (期望 %s ⇒ %s)'
                  % (got_name, expect_name, '一致' if match else '不一致'))
        rows.append({'case': label, 'input': str(val), 'dev': dev, 'how': how,
                     'sd_name': got_name, 'expect': expect_name,
                     'name_match': match, 'ok': ok})

    rec = {'sd_output_devices': [{'index': i, 'name': d['name']} for i, d in sds],
           'sc_speakers': [{'name': s.name, 'id': s.id} for s in spks],
           'cases': rows, 'verdict': ok_all}
    io.open(OUT, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结论：%s' % ('PASS — 端点 id 能正确映射到同名播放设备'
                        if ok_all else 'FAIL — 见上面 🔴'))
    print('结果：', OUT)
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
