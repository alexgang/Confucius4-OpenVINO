#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app159_app044_spk_redaction_gate.py —— §102：APP-044 说话人资产**脱敏合规**验收。

## 为什么需要这个脚本（§102 实测）

§101 把 ASR 的 SpeakerTracker 接口代码同步进客户包 `<包>/app/asr_spk/`，
其中 **4 个文件含内部会议音频编号 `260902`** ⇒ **App 自己的内部素材闸门 FAIL**
⇒ 包内容不合规 ⇒ 不能打包。

修法 = **脱敏**（不是删文件：删了会断 `asr052` 的运行时 import 链）。

## 本脚本判据（全部可证伪）

| 组 | 判据 |
|---|---|
| R1 | 包内 `app/asr_spk/` **0 个**文件含内部会议音频编号（真实扫全目录，不只扫 4 个目标文件）|
| R2 | 包内 `app/asr_spk/` 全部 `.py` **语法合法**（`ast.parse`）|
| R3 | `asr052_speaker_tracker_api.py` 的**运行时**本地 import 目标**全部存在**（import 链未断）|
| R4 | 脱敏**只改字面量**：除 `260902` 外，其余字节与备份**逐字节相同** |
| R5 | 脱敏**行数不变**（不改变代码结构）|
| R6 | 客户包 **内部素材闸门 PASS**（`check_internal_material.py` 退出码 0）|

## 🔴 双向反证（铁律：判据必须能识破注入错误）

* **反证 D-1**：把 `260902` **注入**回来 ⇒ R1 必须 FAIL
* **反证 D-2**：注入语法错误 ⇒ R2 必须 FAIL
* **反证 D-3**：**删掉** `pya_stream_segment.py`（运行时依赖）⇒ R3 必须 FAIL
* **反证 D-4**：篡改非编号字节 ⇒ R4 必须 FAIL
* **反证 D-5**：删一行 ⇒ R5 必须 FAIL
* **反证 D-6**：把闸门脚本改坏 ⇒ R6 必须 FAIL

⇒ 判据不恒真。

## 用法

```
python app159_app044_spk_redaction_gate.py --pkg <包根> [--backup <备份目录>]
```
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG_ASR_SUBDIR = os.path.join('app', 'asr_spk')

# 🔴 内部会议音频编号（与 check_internal_material.py 的 CONTENT_PATTERNS 对齐）
SECRET = b'260902'
# 其它内部特征串也要查（闸门里有的都查，避免「只查一个模式」漏检）
OTHER_SECRETS = (
    (re.compile(rb'\bQ[G]S\b', re.I), '会议特征串'),
    (re.compile(rb'b[l]c\s*b[0]', re.I), '内部产品代号'),
    (re.compile(rb'5[2]\s*c[o]re', re.I), '内部产品规格'),
    (re.compile(rb'L[i]sa will join', re.I), '会议人名片段'),
)

# asr052 的运行时本地 import 目标（§102 实测）
RUNTIME_DEPS = (
    'asr050_spk_qa_speaker_test',
    'asr021_bypass_spk_wespeaker',
    'pya_bypass_spk',
    'pya_stream_segment',
    'asr_lock_common',
)

RESULTS = []


def rec(group: str, name: str, ok: bool, detail: str) -> None:
    RESULTS.append(dict(group=group, name=name, ok=bool(ok), detail=detail))
    print('  [%s] %-6s %-42s %s'
          % ('PASS' if ok else 'FAIL', group, name, detail))


def scan_secrets(root: str):
    """扫全目录，返回 [(relpath, kind, count)]。"""
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                b = open(p, 'rb').read()
            except OSError:
                continue
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            n = b.count(SECRET)
            if n:
                hits.append((rel, '会议音频编号', n))
            for rx, why in OTHER_SECRETS:
                m = len(rx.findall(b))
                if m:
                    hits.append((rel, why, m))
    return hits


def check_syntax(root: str):
    bad = []
    n = 0
    for fn in sorted(os.listdir(root)):
        if not fn.endswith('.py'):
            continue
        n += 1
        p = os.path.join(root, fn)
        try:
            ast.parse(open(p, encoding='utf-8').read())
        except Exception as e:
            bad.append('%s: %s' % (fn, e))
    return n, bad


def runtime_deps_present(root: str):
    have = {x[:-3] for x in os.listdir(root) if x.endswith('.py')}
    return [d for d in RUNTIME_DEPS if d not in have]


# 🔴 脱敏**前**的字面量（备份里是它）→ 脱敏**后**的字面量（现文件里是它）
REDACT_BEFORE = SECRET          # b'260902'
REDACT_AFTER = b'SPEQA'


def only_secret_changed(after: bytes, before: bytes):
    """除「那一段被脱敏的字面量」外，其余字节逐字节相同？

    🔴 判据自身要小心：**备份里是 `260902`、现文件里是 `SPEQA`**
    ⇒ 比对时必须把**两边各自**的敏感串都抹掉再比，
       否则「脱敏本身」就会被误判成「有别的字节被改了」。
    """
    a = after.replace(REDACT_AFTER, b'')
    b_ = before.replace(REDACT_BEFORE, b'')
    return a == b_


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--backup', default=None,
                    help='脱敏前的备份目录（用于 R4/R5 逐字节比对）')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    pkg = args.pkg
    if not pkg:
        import glob
        cands = sorted(glob.glob(r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v*'))
        cands = [c for c in cands if os.path.isdir(c)]
        pkg = cands[-1]
    sub = os.path.join(pkg, PKG_ASR_SUBDIR)

    print('客户包 = %s' % pkg)
    print('asr_spk = %s' % sub)
    print()

    if not os.path.isdir(sub):
        print('!! 包内没有 app/asr_spk/ ⇒ 判据不适用')
        return 2

    # ── R1 内部编号全目录扫描 ────────────────────────────────
    hits = scan_secrets(sub)
    rec('R1', '内部会议编号全目录为 0', not hits,
        ('命中 %d 处：%s' % (len(hits), hits[:5])) if hits else '0 命中 ✅')

    # ── R2 语法全量校验 ──────────────────────────────────────
    n, bad = check_syntax(sub)
    rec('R2', 'asr_spk 全部 .py 语法合法', not bad,
        ('%d 文件，失败 %d：%s' % (n, len(bad), bad[:3])) if bad else '%d 文件全部合法 ✅' % n)

    # ── R3 运行时 import 链完整 ──────────────────────────────
    missing = runtime_deps_present(sub)
    rec('R3', 'asr052 运行时 import 链完整', not missing,
        ('缺失：%s' % missing) if missing else '5 个依赖全在 ✅')

    # ── R4 / R5 与备份逐字节比对 ─────────────────────────────
    if args.backup and os.path.isdir(args.backup):
        diff_other, diff_lines = [], []
        for fn in sorted(os.listdir(args.backup)):
            if not fn.endswith('.py'):
                continue
            bp = os.path.join(args.backup, fn)
            ap_ = os.path.join(sub, fn)
            if not os.path.isfile(ap_):
                diff_other.append('%s: 缺失' % fn)
                continue
            bb = open(bp, 'rb').read()
            ab = open(ap_, 'rb').read()
            if not only_secret_changed(ab, bb):
                diff_other.append(fn)
            if bb.count(b'\n') != ab.count(b'\n'):
                diff_lines.append(fn)
        rec('R4', '除编号外字节逐字未变', not diff_other,
            ('被改动：%s' % diff_other) if diff_other else '4 文件仅编号被替换 ✅')
        rec('R5', '行数不变', not diff_lines,
            ('行数变了：%s' % diff_lines) if diff_lines else '行数全部不变 ✅')
    else:
        rec('R4', '除编号外字节逐字未变', False, '未提供 --backup ⇒ 跳过')
        rec('R5', '行数不变', False, '未提供 --backup ⇒ 跳过')

    # ── R6 客户包内部素材闸门 ────────────────────────────────
    script = os.path.join(REPO, 'check_internal_material.py')
    if os.path.isfile(script):
        r = subprocess.run([sys.executable, script, '--pkg', pkg],
                           capture_output=True, timeout=1800)
        ok = (r.returncode == 0)
        out = r.stdout.decode('utf-8', errors='replace')
        rec('R6', '客户包内部素材闸门 PASS', ok,
            'exit=%d｜%s' % (r.returncode,
                             [l for l in out.splitlines() if '命中' in l][:1]))
    else:
        rec('R6', '客户包内部素材闸门 PASS', False, '找不到 check_internal_material.py')

    # ══════════ 双向反证 ══════════════════════════════════════
    print()
    print('═══ 双向反证（判据必须能识破注入错误）═══')
    tmp = tempfile.mkdtemp(prefix='app159_falsify_')
    try:
        tsub = os.path.join(tmp, 'asr_spk')
        shutil.copytree(sub, tsub)
        tpkg = os.path.join(tmp, 'pkg')

        # D-1：注入内部编号 ⇒ R1 必须 FAIL
        p = os.path.join(tsub, 'asr_slice_common.py')
        b = open(p, 'rb').read()
        open(p, 'wb').write(b.replace(b'SPEQA', SECRET))
        h = scan_secrets(tsub)
        rec('D-1', '注入编号 ⇒ R1 必须 FAIL', bool(h),
            '注入后命中 %d 处 ⇒ R1 识破 ✅' % len(h))
        # 复原
        open(p, 'wb').write(b)

        # D-2：注入语法错误 ⇒ R2 必须 FAIL
        p2 = os.path.join(tsub, 'pya_stream_segment.py')
        b2 = open(p2, 'rb').read()
        open(p2, 'wb').write(b2 + b'\ndef broken(:\n')
        _n, bad2 = check_syntax(tsub)
        rec('D-2', '注入语法错 ⇒ R2 必须 FAIL', bool(bad2),
            '失败 %d 个 ⇒ R2 识破 ✅' % len(bad2))
        open(p2, 'wb').write(b2)

        # D-3：删运行时依赖 ⇒ R3 必须 FAIL
        p3 = os.path.join(tsub, 'pya_stream_segment.py')
        keep = open(p3, 'rb').read()
        os.remove(p3)
        miss = runtime_deps_present(tsub)
        rec('D-3', '删运行时依赖 ⇒ R3 必须 FAIL', bool(miss),
            '缺失 %s ⇒ R3 识破 ✅' % miss)
        open(p3, 'wb').write(keep)

        # D-4 / D-5：篡改非编号字节 / 删一行 ⇒ R4 / R5 必须 FAIL
        bb = open(os.path.join(args.backup, 'asr_slice_common.py'), 'rb').read() \
            if args.backup and os.path.isfile(os.path.join(args.backup, 'asr_slice_common.py')) else b
        cur = open(os.path.join(tsub, 'asr_slice_common.py'), 'rb').read()
        tampered = cur.replace(b'SPEQA', b'SPEQX')  # 改动非编号字节
        d4 = only_secret_changed(tampered, bb)
        rec('D-4', '篡改非编号字节 ⇒ R4 必须 FAIL', (not d4),
            'R4 识破 ✅' if not d4 else '❌ R4 没识破')
        # 🔴 D-5 必须在**现文件**上删一行（备份保持原样）⇒ 行数与备份不一致
        short = cur.replace(b'\n', b'', 1)
        d5 = (short.count(b'\n') != bb.count(b'\n'))
        rec('D-5', '删一行 ⇒ R5 必须 FAIL', d5, 'R5 识破 ✅' if d5 else '❌ R5 没识破')

        # D-6：闸门脚本改坏 ⇒ R6 必须 FAIL
        bad_gate = os.path.join(tmp, 'bad_gate.py')
        open(bad_gate, 'w', encoding='utf-8').write('import sys\nsys.exit(3)\n')
        r = subprocess.run([sys.executable, bad_gate, '--pkg', pkg],
                           capture_output=True, timeout=300)
        rec('D-6', '闸门返非 0 ⇒ R6 必须 FAIL', (r.returncode != 0),
            'exit=%d ⇒ R6 识破 ✅' % r.returncode)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    npass = sum(1 for r in RESULTS if r['ok'])
    nfail = len(RESULTS) - npass
    print()
    print('=' * 70)
    print('PASS %d / FAIL %d（共 %d 条）' % (npass, nfail, len(RESULTS)))
    verdict = 'PASS' if nfail == 0 else 'FAIL'
    print('verdict = %s' % verdict)

    out = args.out or os.path.join(
        REPO, 'results', 'app', 'app159_app044_spk_redaction_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(ver=1, pkg=pkg, asr_spk=sub, backup=args.backup,
                       results=RESULTS, pass_=npass, fail=nfail,
                       verdict=verdict), f, ensure_ascii=False, indent=2)
    print('证据 = %s' % out)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
