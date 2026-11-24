#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 补丁②：把 `tts_runaway` 计数**落到唯一权威点**，并让 worker 遥测能看见。

## 为什么还要补这一刀（补丁①留下的两个真问题）

1. 🔴 **阈值计数可能丢失**：补丁①把阈值判据放在 `yield` **之后**
   ⇒ 消费方（`tts_worker`）若先一步 `break`，生成器**不会**被 resume
   ⇒ 那段计数代码**根本不会执行** ⇒ `tts_runaway` 少记。
   ⇒ 修法：阈值判据挪到 `yield` **之前**（先判、先计数、再决定产不产出这一块）。
2. 🔴 **同一句可能被记两次**：worker 侧第三道闸（`tts_worker.py` L2381）与
   `tts_engine` 的运行时保险**同阈值** ⇒ 需「同一句只记一次」的守卫。
   ⇒ 修法：`tts_engine._mark_runaway(eng, reason)` 用 `eng._runaway_counted` 守卫；
   `stream()` 每句开头重置该标记。

## 本补丁改两处

- `live_caption/tts_engine.py`
  - 新增 `_mark_runaway(eng, reason)`（同一句只记一次）；
  - `_guarded_stream`：阈值判据挪到 `yield` 之前 ＋ 改用 `_mark_runaway`
    ＋ 置 `eng._last_end_reason='runaway'`（让 worker 遥测看到）；
  - `stream()`：每句开头重置 `eng._runaway_counted`。
- `live_caption/tts_worker.py`
  - worker 侧第三道闸触发处 ⇒ 调 `_te._mark_runaway(self.engine, 'threshold')`；
  - 逐句遥测处 ⇒ 引擎侧运行时保险触发时把 `runaway` 标记补上。

## 纪律（定点写入三件套）

备份 → 写前真不变量 ＋ **还原式复核** → 临时文件 → `os.replace`
⇒ **写后另起脚本复核** ＋ `git diff --numstat`。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
T_ENGINE = os.path.join(HERE, 'tts_engine.py')
T_WORKER = os.path.join(HERE, 'tts_worker.py')


def crlf(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


# ══════════════════════════════════════════════════════════════════════
# tts_engine.py
# ══════════════════════════════════════════════════════════════════════
E_OLD_MARK = '''
def tts_runaway_count() -> int:
    """🔴 APP-130②：取 `tts_runaway` 累计次数。"""
    return int(_RUNAWAY_STATS.get('tts_runaway', 0))
'''

E_NEW_MARK = '''
def _mark_runaway(eng, reason: str = 'threshold') -> int:
    """🔴🔴🔳 APP-130②：记一次 `tts_runaway`，**同一句只记一次**。

    - `eng._runaway_counted` 是**本句**的守卫标记（由 `stream()` 每句重置）；
    - worker 侧第三道闸与 `tts_engine` 的运行时保险**同阈值**
      ⇒ 两边都判 ⇒ 用本守卫**去重**（否则一句记 2 次）。
    """
    try:
        if getattr(eng, '_runaway_counted', False):
            return tts_runaway_count()
        eng._runaway_counted = True
    except Exception:
        pass
    return bump_tts_runaway(reason)


def tts_runaway_count() -> int:
    """🔴 APP-130②：取 `tts_runaway` 累计次数。"""
    return int(_RUNAWAY_STATS.get('tts_runaway', 0))
'''

E_OLD_LOOP = '''            got_s += n / float(sr or 24000)
            yield item
            if thr is not None and got_s > thr:
                on_log('[tts_engine] 🔴 APP-130 运行时保险：本句已收 %.1f s > '
                       '阈值 %.1f s ⇒ 停止本句（记 tts_runaway）'
                       % (got_s, thr))
                bump_tts_runaway('threshold')
                break
'''

E_NEW_LOOP = '''            got_s += n / float(sr or 24000)
            # 🔴🔴🔳 APP-130②：**阈值判据放在 `yield` 之前**
            #   ⇒ 计数与「停句」**必然发生**
            #   （放在 `yield` 之后 ⇒ 消费方提前 break 时生成器不会被 resume
            #     ⇒ 那段代码根本不执行 ⇒ 计数丢失）。
            if thr is not None and got_s > thr:
                on_log('[tts_engine] 🔴 APP-130 运行时保险：本句已收 %.1f s > '
                       '阈值 %.1f s ⇒ 停止本句（记 tts_runaway）'
                       % (got_s, thr))
                _mark_runaway(eng, 'threshold')
                try:
                    eng._last_end_reason = 'runaway'
                except Exception:
                    pass
                break
            yield item
'''

E_OLD_NAN = '''        bump_tts_runaway('cp_nan')
        try:
            eng._cp_nan_hit = True
            eng._last_end_reason = 'runaway'
        except Exception:
            pass
        return
'''

E_NEW_NAN = '''        _mark_runaway(eng, 'cp_nan')
        try:
            eng._cp_nan_hit = True
            eng._last_end_reason = 'runaway'
        except Exception:
            pass
        return
'''

E_OLD_STREAM = '''    # 🔴🔴🔳 APP-130②：**运行时保险**（生成循环级）
    #   ⇒ code predictor 出 NaN/Inf ⇒ 本句立刻停；已收音频超失控阈值 ⇒ 本句停。
    return _guarded_stream(eng.generate_stream(**kwargs), eng, text,
                            language, est_sec, on_log=on_log)
'''

E_NEW_STREAM = '''    # 🔴🔴🔳 APP-130②：**运行时保险**（生成循环级）
    #   ⇒ code predictor 出 NaN/Inf ⇒ 本句立刻停；已收音频超失控阈值 ⇒ 本句停。
    #   ⚠️ **每句重置「本句已计数」标记** ⇒ 同一句只记 1 次 `tts_runaway`。
    try:
        eng._runaway_counted = False
    except Exception:
        pass
    return _guarded_stream(eng.generate_stream(**kwargs), eng, text,
                            language, est_sec, on_log=on_log)
'''

ENGINE_PATCHES = [
    ('_mark_runaway', E_OLD_MARK, E_NEW_MARK),
    ('阈值判据前移', E_OLD_LOOP, E_NEW_LOOP),
    ('cp_nan 用 _mark_runaway', E_OLD_NAN, E_NEW_NAN),
    ('stream 每句重置守卫', E_OLD_STREAM, E_NEW_STREAM),
]

# ══════════════════════════════════════════════════════════════════════
# tts_worker.py
# ══════════════════════════════════════════════════════════════════════
W_OLD_RUNAWAY = '''                        if _runaway_s is not None and _got_s > _runaway_s:
                            runaway = True
                            self._last_end_reason = 'runaway'
                            log('[tts_worker] 🔴 RUNAWAY id=%d lang=%s len=%d '
'''

W_NEW_RUNAWAY = '''                        if _runaway_s is not None and _got_s > _runaway_s:
                            runaway = True
                            self._last_end_reason = 'runaway'
                            # 🔴🔴🔳 APP-130②：记 `tts_runaway`
                            #   （与 `tts_engine` 的运行时保险**同一句只记一次**
                            #     ⇒ 由 `engine._runaway_counted` 守卫去重）
                            try:
                                _te._mark_runaway(self.engine, 'threshold')
                            except Exception:
                                pass
                            log('[tts_worker] 🔴 RUNAWAY id=%d lang=%s len=%d '
'''

W_OLD_AFTER = '''                # 🔴🔴🔳 APP-042：**变速器的收尾块**（最后一帧的尾巴）
'''

W_NEW_AFTER = '''                # 🔴🔴🔳 APP-130②：**引擎侧运行时保险触发的 RUNAWAY**
                #   （`tts_engine._guarded_stream` 在「超失控阈值」或
                #     「code predictor 出 NaN」时会停句并把
                #     `engine._last_end_reason` 置成 `runaway`
                #     ⇒ 这里把它反映到逐句遥测的 `runaway` 标记上）
                try:
                    if getattr(self.engine, '_runaway_counted', False):
                        runaway = True
                        self._last_end_reason = 'runaway'
                except Exception:
                    pass
                # 🔴🔴🔳 APP-042：**变速器的收尾块**（最后一帧的尾巴）
'''

WORKER_PATCHES = [
    ('worker 第三道闸计数', W_OLD_RUNAWAY, W_NEW_RUNAWAY),
    ('worker 遥测补 runaway 标记', W_OLD_AFTER, W_NEW_AFTER),
]


def apply(path, patches, label):
    raw = open(path, 'rb').read()
    orig = raw.decode('utf-8')
    if '\r\n' not in orig:
        raise SystemExit('FAIL: %s 不是 CRLF ⇒ 停手' % path)
    backup = os.path.join(tempfile.gettempdir(),
                          os.path.basename(path) + '.app130b.bak')
    shutil.copy2(path, backup)
    print('备份[%s]: %s (%d B)' % (label, backup, len(raw)))

    text = orig
    for name, old, new in patches:
        o, n = crlf(old), crlf(new)
        cnt = text.count(o)
        if cnt != 1:
            raise SystemExit('FAIL[%s]: 补丁 %r 命中 %d 次（要求 1 次）⇒ 零改动'
                             % (label, name, cnt))
        text = text.replace(o, n, 1)

    # ── 真不变量（写前）────────────────────────────────────────────
    errs = []
    back = text
    for name, old, new in reversed(patches):
        o, n = crlf(old), crlf(new)
        if back.count(n) != 1:
            errs.append('还原式复核失败：%r 反向命中 %d 次'
                        % (name, back.count(n)))
            break
        back = back.replace(n, o, 1)
    else:
        if back != orig:
            errs.append('还原式复核失败：反向替换后与原文不逐字节相同')
    if text.count('\n') != text.count('\r\n'):
        errs.append('行尾风格被改')
    for name, old, _n in patches:
        if crlf(old).strip() and crlf(old) not in orig:
            errs.append('旧正文片段不在原文件里：%r' % name)
    for sym in ('_mark_runaway', '_runaway_counted'):
        if sym not in text:
            errs.append('缺关键符号：%s' % sym)
    try:
        compile(text, path, 'exec')
    except SyntaxError as e:
        errs.append('语法错误：%s' % e)
    if errs:
        print('自检 FAIL[%s] ⇒ 零改动：' % label)
        for e in errs:
            print('  - %s' % e)
        raise SystemExit(4)

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.app130b.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(text.encode('utf-8'))
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('已打补丁[%s]: %s' % (label, '、'.join(n for n, _o, _x in patches)))
    print('  字节：%d → %d（%+d）／行数：%d → %d（%+d）'
          % (len(raw), len(text.encode('utf-8')),
             len(text.encode('utf-8')) - len(raw),
             orig.count('\n'), text.count('\n'),
             text.count('\n') - orig.count('\n')))


def main() -> int:
    apply(T_ENGINE, ENGINE_PATCHES, 'tts_engine')
    apply(T_WORKER, WORKER_PATCHES, 'tts_worker')
    return 0


if __name__ == '__main__':
    sys.exit(main())
