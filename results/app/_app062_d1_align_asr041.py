#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 追加：D1 的「同源」读取**对齐 ASR-041 新落地的单一事实来源**。

🔴 **背景**：ASR-041（2026-11-02 10:21）落地了 `scripts/asr_spk_window.py`
  ⇒ 它的 docstring 明写：「**说话人旁路窗口长度的唯一事实来源**（ASR 侧）」
  ⇒ 并列出「同一个常量写在了 3 个地方」：
     ① `asr052_spk_runtime.WIN_S = 10.0`（ASR 侧运行时内核）
     ② `speaker_tracker._WIN_S = 10.0`（**App 侧** ⇒ 就是本轮要改的）
     ③ （ASR 侧脚本里的另一份）
  ⇒ reviewer APP-062 D1 的「**和 ASR 侧常量同源，不要两处各写一个**」
     **正是要跟这个模块对齐**。

🔴 **本轮改什么**：D1 的读取顺序改成
     ① `asr_spk_window.WIN_S`（**ASR-041 的唯一事实来源**）
     ② `asr052_spk_runtime.WIN_S`（**随包分发**的运行时内核 ⇒ 客户机兜底）
     ③ 默认 10.0
  ⇒ **将来 ASR 把 `asr_spk_window.WIN_S` 改成 5.0 并随包分发**
  ⇒ App 侧**自动跟随**（这才是「同源」的真正含义）
  ⇒ **当前两边都仍是 10.0** ⇒ **行为不变**（reviewer D1：「默认先保持 10 s」）。

🔴 **为什么不自行切到 5 s**：ASR-041 的结论是「建议切到 5 s」但**它自己没切**
  （`WIN_S 仍 10.0，未擅自切换` ⇒「切换需 App 线程决定」）
  ⇒ 若 App 侧单方面改成 5 s，而 ASR 运行时内核仍是 10 s
  ⇒ **两边又不一致了** ⇒ 正是 D1 要消灭的缺陷
  ⇒ 故本轮**保持 10 s**，并把「是否切换」交 reviewer（附 ASR-041 的实测数据）。
"""
import ast
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     '..', '..'))
TARGET = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')

OLD = """def _asr_win_s():
    \"\"\"🔴 从 **ASR 侧模块**读 `WIN_S` ⇒ **同源**（读不到 ⇒ None）。\"\"\"
    try:
        import importlib
        import importlib.util
        # ① 已加载过（`_load()` 会把目录加进 sys.path）
        mod = sys.modules.get('asr052_spk_runtime')
        if mod is None:
            # ② 按**旁路资产解析器**给的实际目录找
            #   （包内 `app/asr_spk/` 或研发机 ASR 目录 ⇒ 两边都能找到）
            import speaker_assets
            d = ''
            try:
                info = speaker_assets.resolve()
                d = (info or {}).get('scripts_dir') or ''
            except Exception:
                d = ''
            if not d:
                d = _ASR_SCRIPTS
            p = os.path.join(d, 'asr052_spk_runtime.py')
            if os.path.isfile(p):
                spec = importlib.util.spec_from_file_location(
                    'asr052_spk_runtime', p)
                if spec and spec.loader:
                    m = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(m)
                    mod = m
        if mod is None:
            return None
        v = getattr(mod, 'WIN_S', None)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \\
            else None
    except Exception:
        return None
"""

NEW = '''def _asr_scripts_dir():
    """🔴 定位 **ASR 侧脚本目录**（包内 `app/asr_spk/` 或研发机 ASR 目录）。"""
    try:
        import speaker_assets
        info = speaker_assets.resolve()
        d = (info or {}).get('scripts_dir') or ''
        if d:
            return d
    except Exception:
        pass
    return _ASR_SCRIPTS


def _load_asr_module(mod_name, scripts_dir):
    """🔴 按名字加载 ASR 侧模块（已加载过 ⇒ 直接用；否则从脚本目录按文件加载）。"""
    try:
        import importlib
        import importlib.util
        mod = sys.modules.get(mod_name)
        if mod is not None:
            return mod
        p = os.path.join(scripts_dir, mod_name + '.py')
        if not os.path.isfile(p):
            return None
        spec = importlib.util.spec_from_file_location(mod_name, p)
        if not (spec and spec.loader):
            return None
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception:
        return None


def _asr_win_s():
    """🔴 从 **ASR 侧模块**读 `WIN_S` ⇒ **同源**（读不到 ⇒ None）。

    🔴🔴🔴 **读取顺序（§131 对齐 ASR-041）**：
      ① **`asr_spk_window`** —— ASR-041 落地的**唯一事实来源**
         （其 docstring 明写「说话人旁路窗口长度的唯一事实来源（ASR 侧）」）
         ⇒ **将来 ASR 把它改成 5.0 并随包分发 ⇒ App 侧自动跟随**
      ② **`asr052_spk_runtime`** —— **随包分发**的 ASR 运行时内核
         ⇒ 客户机上 `asr_spk_window` 未随包时的**兜底**
      ③ 都没有 ⇒ 返回 None ⇒ 由 `_resolve_win_s()` 退回默认 10.0
    """
    scripts_dir = _asr_scripts_dir()
    for mod_name in ('asr_spk_window', 'asr052_spk_runtime'):
        mod = _load_asr_module(mod_name, scripts_dir)
        if mod is None:
            continue
        v = getattr(mod, 'WIN_S', None)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v), mod_name
    return None, None
'''

OLD_RESOLVE = """def _resolve_win_s():
    \"\"\"🔴 解析旁路窗长：**环境变量（配置项） > ASR 侧常量（同源） > 默认 10.0**。\"\"\"
    raw = os.environ.get(_WIN_S_ENV, '')
    if raw not in (None, ''):
        try:
            v = float(raw)
            if v > 0:
                return v, '配置项 %s=%s' % (_WIN_S_ENV, raw)
        except Exception:
            pass
    v = _asr_win_s()
    if v is not None and v > 0:
        return v, '同源 asr052_spk_runtime.WIN_S=%s' % v
    return _WIN_S_DEFAULT, '默认 %s' % _WIN_S_DEFAULT
"""

NEW_RESOLVE = """def _resolve_win_s():
    \"\"\"🔴 解析旁路窗长：**环境变量（配置项） > ASR 侧常量（同源） > 默认 10.0**。\"\"\"
    raw = os.environ.get(_WIN_S_ENV, '')
    if raw not in (None, ''):
        try:
            v = float(raw)
            if v > 0:
                return v, '配置项 %s=%s' % (_WIN_S_ENV, raw)
        except Exception:
            pass
    v, mod_name = _asr_win_s()
    if v is not None and v > 0:
        return v, '同源 %s.WIN_S=%s' % (mod_name, v)
    return _WIN_S_DEFAULT, '默认 %s' % _WIN_S_DEFAULT
"""


def main():
    with open(TARGET, 'rb') as f:
        raw = f.read()
    before = hashlib.sha256(raw).hexdigest()
    crlf = raw.count(b'\r\n')
    use_crlf = bool(crlf) and crlf == raw.count(b'\n')
    text = raw.decode('utf-8')
    if use_crlf:
        text = text.replace('\r\n', '\n')

    for name, old, new in (('_asr_win_s 对齐 ASR-041', OLD, NEW),
                           ('_resolve_win_s 用新的返回签名', OLD_RESOLVE,
                            NEW_RESOLVE)):
        n = text.count(old)
        if n != 1:
            print('[FAIL] %s ⇒ 命中 %d 次（须恰好 1 次）' % (name, n))
            return 2
        text = text.replace(old, new, 1)
        print('[OK] %s' % name)

    try:
        ast.parse(text)
    except SyntaxError as e:
        print('[FAIL] ast.parse 失败：%s' % e)
        return 3
    if use_crlf:
        text = text.replace('\n', '\r\n')
    out = text.encode('utf-8')
    with open(TARGET, 'wb') as f:
        f.write(out)
    with open(TARGET, 'rb') as f:
        check = f.read()
    assert check == out
    if use_crlf:
        assert check.count(b'\r\n') == check.count(b'\n'), '出现裸 LF'
    else:
        assert check.count(b'\r\n') == 0, '混入 CRLF'
    print('\n写入完成')
    print('  bytes  %d → %d' % (len(raw), len(check)))
    print('  sha256 %s → %s' % (before, hashlib.sha256(check).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
