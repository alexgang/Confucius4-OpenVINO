#!/usr/bin/env python
r"""给 App 侧计时脚本的**每一条测量记录**加「锁自检」字段（TTS 通知 §四）。

## 为什么

TTS 通知 §四：「锁被抢 / 被删 / 被换写」这件事**在数据里完全看不出来**
⇒ TTS 第一轮数据「看着像没事」，实际上 16/30 被污染
⇒ 持锁方必须**逐条自检** ⇒ 锁一断就强制 `timing_valid=false`。

## 改法

在每条 `rows.append({...})` 里加三个字段：
    'timing_valid': <bool>   —— 锁完好 ⇒ True
    'lock_note':    <str>    —— 原因（人可读）
    'lock_pid':     <int>    —— 当前锁内 PID

用 `machine_lock_app.lock_probe()` 取值（与 TTS 侧 `_lock_probe()` 字段对齐）。

## 方法

- **精确字符串替换 + 唯一命中断言**（命中不唯一 ⇒ 失败、不写盘）。
- **先编译临时副本、再写盘**（语法错 ⇒ 目标文件一个都不动）。
- 换行风格以 **HEAD** 为准（避免整文件改换行 ⇒ 假 diff）。
"""
from __future__ import annotations

import ast
import os
import py_compile
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRY = '--apply' not in sys.argv

PROBE_HELPER = '''

def _lock_probe_row():
    """🔴 逐条锁自检（TTS 通知 §四）⇒ 返回 (timing_valid, lock_note, lock_pid)。

    🔴 「锁被抢 / 被删 / 被换写」在数据里**完全看不出来**
    ⇒ 逐条查 ⇒ 锁一断就 `timing_valid=false` ⇒ 污染不会伪装成正常结果。
    """
    p = machine_lock_app.lock_probe()
    return p['lock_ok'], p['lock_note'], p['lock_pid']
'''

# (相对路径, 锚点(行首+文本), 插入的字段文本)
PLAN = [
    ('results/app/app061_tts_npu_contention.py',
     "                rows.append({'id': i, 't_first': round(t_first, 3),\n"
     "                             't_all': round(t_all, 3),\n"
     "                             'audio_s': round(audio, 2),\n"
     "                             'rtf': round(t_all / audio, 3) if audio else None})",
     "                rows.append({'id': i, 't_first': round(t_first, 3),\n"
     "                             't_all': round(t_all, 3),\n"
     "                             'audio_s': round(audio, 2),\n"
     "                             'rtf': round(t_all / audio, 3) if audio else None,\n"
     "                             **_lock_probe_fields()})"),
    ('results/app/app062_cp_decode_device_ab.py',
     "                rows.append({'id': i, 't_first': round(tf, 3),\n"
     "                             't_all': round(ta, 3),\n"
     "                             'audio_s': round(au, 2),\n"
     "                             'rtf': round(rtf, 3) if rtf else None})",
     "                rows.append({'id': i, 't_first': round(tf, 3),\n"
     "                             't_all': round(ta, 3),\n"
     "                             'audio_s': round(au, 2),\n"
     "                             'rtf': round(rtf, 3) if rtf else None,\n"
     "                             **_lock_probe_fields()})"),
]

HELPER = '''

def _lock_probe_fields():
    """🔴 逐条锁自检字段（TTS 通知 §四）。

    🔴 「锁被抢 / 被删 / 被换写」在数据里**完全看不出来**
    ⇒ 逐条查 ⇒ 锁一断就 `timing_valid=false` ⇒ 污染不会伪装成正常结果。
    """
    p = machine_lock_app.lock_probe()
    return {'timing_valid': p['lock_ok'], 'lock_note': p['lock_note'],
            'lock_pid': p['lock_pid']}
'''

HELPER_ANCHOR = "import machine_lock_app\n"


def main():
    changed, failed = [], []
    for rel, old, new in PLAN:
        path = os.path.join(REPO, rel)
        with open(path, 'rb') as f:
            raw = f.read()
        head = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=REPO,
                              capture_output=True).stdout
        crlf = bool(head) and (b'\r\n' in head)
        text = raw.decode('utf-8').replace('\r\n', '\n')

        n = text.count(old)
        if n != 1:
            failed.append((rel, 'rows.append 命中 %d 次（应恰好 1 次）' % n))
            continue

        # 加 helper（放在 import machine_lock_app 之后）
        if '_lock_probe_fields' not in text:
            if text.count(HELPER_ANCHOR) < 1:
                failed.append((rel, '找不到 helper 锚点'))
                continue
            text = text.replace(HELPER_ANCHOR, HELPER_ANCHOR + HELPER, 1)

        text = text.replace(old, new, 1)

        # 语法自检
        try:
            ast.parse(text)
        except SyntaxError as e:
            failed.append((rel, '语法错: %r' % e))
            continue
        changed.append((rel, text, crlf))

    print('=' * 66)
    print('待改文件: %d   失败: %d' % (len(PLAN), len(failed)))
    print('=' * 66)
    for rel, why in failed:
        print('  [FAIL] %s -- %s' % (rel, why))
    for rel, _, _ in changed:
        print('  [ OK ] %s' % rel)

    if DRY:
        print()
        print('（dry-run；加 --apply 才落盘）')
        return 1 if failed else 0
    if failed:
        print()
        print('🔴 有失败项 ⇒ **不写任何文件**')
        return 1

    print()
    staged = []
    for rel, text, crlf in changed:
        out = text.replace('\n', '\r\n') if crlf else text
        fd, tmp = tempfile.mkstemp(suffix='.py')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(out.encode('utf-8'))
            py_compile.compile(tmp, doraise=True)
            staged.append((rel, out, crlf))
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    for rel, out, crlf in staged:
        path = os.path.join(REPO, rel)
        with open(path, 'wb') as f:
            f.write(out.encode('utf-8'))
        print('  [written+compiled] %s (crlf=%s)' % (rel, crlf))
    return 0


if __name__ == '__main__':
    sys.exit(main())
