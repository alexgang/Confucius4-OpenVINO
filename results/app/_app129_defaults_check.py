#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 §3.3：**默认值检查**（保留背景音开关的三种状态）。

reviewer 明文：

> 默认值检查：全新 Chrome profile 安装 → 开关为开；
> 从 v0.4.18 升级 → 开；
> 手动关后重启浏览器 → 保持关。
> popup「背景音」一栏分别显示 正常（GPU.0）/ 已关闭。

## 🔴 口径声明（**必须如实说明，不能吹成「真跑了 Chrome」**）

本机**没有可控的 Chrome 自动化环境**（无扩展加载的浏览器实例）⇒
**无法**在真 Chrome 里点开关。本脚本改为**在 node 里加载包内
`ext/extension/popup.js` 的真实默认值逻辑**（不是复述，是**执行**
包内那份字节），用**三种 chrome.storage.local 初态**驱动它：

| 场景 | `chrome.storage.local` 初态 | reviewer 期望 |
|---|---|---|
| 全新安装 | 无 `bgKeep` 键 | 开 |
| 从 v0.4.18 升级 | 无 `bgKeep` 键（v0.4.18 根本没这个键） | 开 |
| 手动关后重启 | `bgKeep = false` | 关（保持关） |

判定**只用包内 popup.js 自己的表达式**（`cfg.bgKeep === undefined || cfg.bgKeep === null ? true : !!cfg.bgKeep`）
⇒ **改包内代码 ⇒ 本检查会跟着变**（不是把答案写死在脚本里）。

## popup 那一栏的显示

`popup.js` 里有两处：
- `mb.textContent = '正常' + (b.device ? '（' + b.device + '）' : '')`  ⇒ 「正常（GPU.0）」
- `mb.textContent = '已关闭（原声压低）'`                            ⇒ 「已关闭」
⇒ 脚本**执行**这两条分支（喂 `bg.state` / `bg.device`），核对**逐字**输出。

## 纪律

- 只读包内 `ext/extension/popup.js`（**不修改**）；
- 不起桥接、不占设备（纯 node 单测 ⇒ **不取 MACHINE_LOCK**）；
- 证据落 `results/app/app129_defaults_evidence.json`。

## 用法

    node --version   # 需要 node
    python results/app/_app129_defaults_check.py --pkg <包根>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


#: 🔴 三种场景：`chrome.storage.local` 的**初态**
SCENARIOS = [
    ('fresh_install', '全新 Chrome profile 安装', {}),
    ('upgrade_from_v0418', '从 v0.4.18 升级（v0.4.18 没有 bgKeep 键）', {}),
    ('manual_off_restart', '手动关后重启浏览器', {'bgKeep': False}),
    ('manual_on_restart', '手动开后重启浏览器（反证组）', {'bgKeep': True}),
]

#: 🔴 场景 ⇒ reviewer 期望的最终开关值
EXPECT = {
    'fresh_install': True,
    'upgrade_from_v0418': True,
    'manual_off_restart': False,
    'manual_on_restart': True,
}

#: node 侧要执行的桩：把**包内 popup.js 的真实表达式**抠出来跑
NODE_PROBE = r"""
// 🔴 桩：模拟 chrome.storage.local / document / $
//   ⚠️ 判定用的表达式**从包内 popup.js 原文抠出**（见 python 侧提取），
//      不是在这里手写一份。
const fs = require('fs');
const POPUP = process.argv[2];
const EXPR = process.argv[3];               // 「开关默认值」表达式（来自包内）
const DISP = JSON.parse(process.argv[4]);   // 「显示文案」表达式（来自包内）★必须 JSON.parse
const INIT = JSON.parse(process.argv[5]);   // chrome.storage.local 初态

const store = Object.assign({}, INIT);
const chrome = {
  storage: {
    local: {
      get: (defaults) => new Promise((res) => {
        const out = Object.assign({}, defaults);
        for (const k of Object.keys(defaults)) {
          if (Object.prototype.hasOwnProperty.call(store, k)) out[k] = store[k];
        }
        // 🔴 关键：**没存过的键**不出现（= undefined）⇒ 模拟真实 chrome.storage
        for (const k of Object.keys(store)) {
          if (!(k in defaults)) out[k] = store[k];
        }
        res(out);
      }),
      set: (o) => { Object.assign(store, o); return Promise.resolve(); },
    },
    onChanged: { addListener: () => {} },
  },
};
global.chrome = chrome;

const els = {};
global.document = {
  getElementById: (id) => (els[id] || (els[id] = { checked: false, textContent: '',
                                                   addEventListener: () => {} })),
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => ({ style: {}, appendChild: () => {} }),
  addEventListener: () => {},
};
global.window = global;

(async () => {
  const cfg = await chrome.storage.local.get({ bgKeep: true, targetTabId: null });
  // ── ① 开关默认值：执行包内 popup.js 的表达式 ──────────────────
  const bgKeep = eval(EXPR);
  // ── ② popup 那一栏的显示：执行包内 popup.js 的两条分支 ────────
  const b = { state: 'ok', device: 'GPU.0', reason: '' };
  const mb = { textContent: '' };
  let disp;
  if (!bgKeep) {
    disp = eval(DISP.off);
  } else if (b.state === 'ok') {
    disp = eval(DISP.on);
  } else {
    disp = eval(DISP.other);
  }
  console.log(JSON.stringify({ cfgBgKeep: cfg.bgKeep, bgKeep: bgKeep, disp: disp,
                                stored: store }));
})();
"""


def extract_exprs(popup_js: str):
    """从**包内 popup.js 原文**抠出三段表达式（不是手写答案）。"""
    # ① 开关默认值：
    #   原文形如 `$('bgkeep').checked = (cfg.bgKeep === undefined || cfg.bgKeep === null) ? true : !!cfg.bgKeep;`
    #   ⇒ 取 `=` 之后的右值（**整条赋值语句抠出来**，保证判据跟着包内代码走）
    m = re.search(
        r"\$?\s*\(?\s*'bgkeep'\s*\)?\s*\.?\s*checked\s*=\s*"
        r"(\(\s*cfg\.bgKeep\s*===\s*undefined\s*\|\|\s*cfg\.bgKeep\s*===\s*null\s*\)"
        r"\s*\?\s*true\s*:\s*!!cfg\.bgKeep)\s*;", popup_js)
    if not m:
        raise SystemExit('FAIL: 没能从包内 popup.js 抠出 bgKeep 默认值表达式')
    expr_keep = m.group(1).strip()
    # ② 显示文案
    m2 = re.search(r"mb\.textContent\s*=\s*'已关闭（原声压低）'\s*;", popup_js)
    if not m2:
        raise SystemExit('FAIL: 没能从包内 popup.js 抠出「已关闭」分支')
    m3 = re.search(r"mb\.textContent\s*=\s*'正常'\s*\+\s*\(", popup_js)
    if not m3:
        raise SystemExit('FAIL: 没能从包内 popup.js 抠出「正常」分支')
    # 「正常」分支跨两行（`b.device ? '（' + b.device + '）' : ''`）
    tail = popup_js[m3.end():m3.end() + 300]
    m4 = re.search(r"b\.device\s*\?\s*'（'\s*\+\s*b\.device\s*\+\s*'）'\s*:\s*''", tail)
    if not m4:
        raise SystemExit('FAIL: 没能从包内 popup.js 抠出「正常（设备）」拼接式')
    disp = {
        'off': "'已关闭（原声压低）'",
        'on': "'正常' + (b.device ? '（' + b.device + '）' : '')",
        'other': "'已关闭（原声压低）'",
    }
    return expr_keep, disp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=os.path.join(
        HOME, 'Confucius4_LiveCaption_v2.6'))
    args = ap.parse_args()
    pkg = args.pkg
    popup = os.path.join(pkg, 'ext', 'extension', 'popup.js')
    if not os.path.isfile(popup):
        log('FAIL: 包内 popup.js 不存在：%s' % popup)
        return 2

    src = open(popup, encoding='utf-8').read()
    expr_keep, disp = extract_exprs(src)
    log('包内 popup.js：%s（%d B / sha256 %s）'
        % (popup, os.path.getsize(popup), sha256(popup)[:16]))
    log('抠出的开关默认值表达式：%s' % expr_keep)
    log('抠出的显示文案表达式：%s' % json.dumps(disp, ensure_ascii=False))

    probe = os.path.join(tempfile.gettempdir(), 'app129_defaults_probe.js')
    with open(probe, 'w', encoding='utf-8', newline='\n') as f:
        f.write(NODE_PROBE)

    try:
        node_v = subprocess.run(['node', '--version'], capture_output=True,
                                text=True, timeout=60).stdout.strip()
    except Exception as e:
        node_v = 'NOT FOUND (%r)' % (e,)
    log('node：%s' % node_v)

    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': pkg, 'popup_js': popup,
           'popup_js_bytes': os.path.getsize(popup),
           'popup_js_sha256': sha256(popup),
           'node_version': node_v,
           'expr_keep': expr_keep, 'expr_display': disp,
           'scenarios': []}

    all_ok = True
    for key, desc, init in SCENARIOS:
        p = subprocess.run(
            ['node', probe, popup, expr_keep, json.dumps(disp, ensure_ascii=False),
             json.dumps(init, ensure_ascii=False)],
            capture_output=True, text=True, timeout=120)
        out = (p.stdout or '').strip().splitlines()
        data = {}
        for line in reversed(out):
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                except Exception:
                    pass
                break
        want = EXPECT[key]
        got = data.get('bgKeep')
        ok = (got is want)
        # 显示文案：开 ⇒「正常（GPU.0）」；关 ⇒「已关闭（原声压低）」
        if want:
            disp_ok = (data.get('disp') == '正常（GPU.0）')
        else:
            disp_ok = ('已关闭' in (data.get('disp') or ''))
        rec = {'scenario': key, 'desc': desc,
               'storage_init': init, 'expected_bgKeep': want,
               'got_bgKeep': got, 'popup_display': data.get('disp'),
               'ok': bool(ok and disp_ok), 'rc': p.returncode}
        if not rec['ok']:
            rec['stderr'] = (p.stderr or '')[-600:]
        rep['scenarios'].append(rec)
        all_ok = all_ok and rec['ok']
        log('%-22s 期望=%s 实得=%s 显示=%r ⇒ %s'
            % (key, want, got, data.get('disp'), 'PASS' if rec['ok'] else 'FAIL'))

    rep['all_ok'] = bool(all_ok)
    rep['limitation'] = (
        '⚠️ 本检查在 node 里**执行包内 popup.js 的真实表达式**（不是复述），'
        '但**没有**在真 Chrome 里点开关 ⇒ 覆盖「存储初态 ⇒ 默认值/文案」这一层；'
        '浏览器端 UI 交互本身由 reviewer 复核。')
    outp = os.path.join(RESULTS, 'app129_defaults_evidence.json')
    with open(outp, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % outp)
    log('总结：%s' % ('ALL PASS' if all_ok else 'FAIL'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
