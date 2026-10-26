#!/usr/bin/env python
r"""把 App 侧各计时脚本的取锁改成**原子写**（TTS 通知 §一 / §三 3.1）。

## 为什么

`shared/NOTICE_tts_lock_atomic_20261026.md`：旧写法 `os.open(O_CREAT|O_EXCL)`
**先建空文件、之后才写内容** ⇒ 存在「文件已存在、内容还是空的」窗口
⇒ 别的模块（ASR 的 `pya_app_path_seg.py` / `p3_run_with_lock.py`）在这个窗口里
读锁 ⇒ **解析不出 pid** ⇒ 判成「陈旧锁」⇒ `os.remove` **删掉别人的活锁**
⇒ 两个模块同时跑 ⇒ 实测作废 TTS 两轮数据（16/30、24/30 行 `timing_valid=false`）。

⇒ App 侧 `machine_lock_app.py::acquire()` 已改（原子写 + 独占）。
🔴 但 **App 侧还有 8 个脚本各自复制了一份取锁代码** ⇒ 同样带这个缺陷
⇒ 本脚本把它们**统一改成调用 `machine_lock_app` 的原子写**。

## 方法（**不手抄代码** ⇒ 抄错风险归零）

- 用**正则**从目标文件里**抽出实际的旧块**（而不是我手写的字符串）
  ⇒ 手抄一个字错位就会「命中 0 次」⇒ 脚本**直接失败、不写盘**。
- 替换后做**唯一命中断言**（`len(matches) == 1`）。
- 逐文件 `py_compile` 语法校验；任一失败 ⇒ **整体不写盘**。
- 不做整目录覆盖。

⚠️ 只改仓库；`live_caption/` 下的开发脚本**不进客户包**，
   但仓库里也要改 ⇒ 防止以后有人直接跑它污染计时。
"""
from __future__ import annotations

import os
import py_compile
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

DRY = '--apply' not in sys.argv

# 🔴 **换行归一化**：这些脚本是 **CRLF** ⇒ 正则里的 `\n` 匹配不到 `\r\n`
# ⇒ 统一先把内容归一化成 `\n` 做匹配与改写，**写回时再还原成原样**。
#    （STATUS 记录：STATUS_APP.md 有 LF/CRLF 两种历史；.py 这批是 CRLF。）

# ── 正则：旧取锁块 ────────────────────────────────────────────────
# 形态：`try:` + `os.open(LOCK, os.O_CREAT|O_EXCL|O_WRONLY)` + 写 + 打印 + return True
#       + `except FileExistsError:` + `pass`
RE_OLD_TRY = re.compile(
    r"[ \t]*try:\n"
    r"[ \t]*fd = os\.open\(LOCK, os\.O_CREAT \| os\.O_EXCL \| os\.O_WRONLY\)\n"
    r"(?:[^\n]*\n)*?"
    r"[ \t]*return True\n"
    r"[ \t]*except FileExistsError:\n"
    r"[ \t]*pass\n"
)

# 形态：`with open(LOCK, 'w', ...) as f:` + f.write(...) + `return True...`
RE_OLD_WITH = re.compile(
    r"[ \t]*with open\(LOCK, 'w', encoding='utf-8'\) as f:\n"
    r"(?:[^\n]*\n)*?"
    r"[ \t]*return True[^\n]*\n"
)

NEW_TRY = """                _pay = ('module: %s\\npid: %d\\nstarted: %s\\n'
                        'host: %s\\n'
                        % (@MOD@, os.getpid(),
                           time.strftime('%Y-%m-%d %H:%M:%S'),
                           os.environ.get('COMPUTERNAME', '?')))
                if machine_lock_app.write_lock_atomic(LOCK, _pay):
                    print(@MSG@)
                    return True
"""

NEW_WITH = """    _pay = ('module: %s\\npid: %d\\nstarted: %s\\n'
            'host: %s\\n'
            % (@MOD@, os.getpid(),
               time.strftime('%Y-%m-%d %H:%M:%S'),
               os.environ.get('COMPUTERNAME', '?')))
    if not machine_lock_app.write_lock_atomic(LOCK, _pay):
        print('[lock] 原子写入失败（锁已被别人占用）', flush=True)
        return @RETFAIL@
"""

IMPORT_BLOCK = """
# 🔴 取锁统一走仓库根的 `machine_lock_app`（**原子写** + 独占 + fail-closed）。
#   旧的「各自复制一份取锁代码」是逻辑漂移的根源 ⇒ 已全部收敛到这里。
#   旧写法 `os.open(O_CREAT|O_EXCL)` **先建空文件、之后才写内容**
#   ⇒ 存在「文件已存在、内容还是空的」窗口 ⇒ 别的模块读到空锁
#   ⇒ 解析不出 pid ⇒ 判成「陈旧锁」⇒ **删掉别人的活锁** ⇒ 两个模块同时跑
#   ⇒ 实测作废 TTS 两轮数据（16/30、24/30 行 timing_valid=false）。
#   依据：shared/NOTICE_tts_lock_atomic_20261026.md §一 / §三 3.1。
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import machine_lock_app
"""

# (相对路径, 模式, 锚点行, 是否需要 import 块)
PLAN = [
    ('results/app/app056_tts_streaming_gap.py', 'try',
     "HERE = os.path.dirname(os.path.abspath(__file__))", True),
    ('results/app/app059_tts_streaming_e2e.py', 'try',
     "HERE = os.path.dirname(os.path.abspath(__file__))", True),
    ('results/app/app061_tts_npu_contention.py', 'try',
     "HERE = os.path.dirname(os.path.abspath(__file__))", True),
    ('results/app/app062_cp_decode_device_ab.py', 'try',
     "HERE = os.path.dirname(os.path.abspath(__file__))", True),
    ('results/app/app065_precision_hint_ab.py', 'try',
     "REPO = os.path.dirname(os.path.dirname(HERE))", True),
    ('results/app/app067_ruler_same_day_recheck.py', 'try',
     "HOME = r'C:\\Users\\Trekker-PTL'", True),
    ('live_caption/diag_c111_e2e.py', 'with',
     "LOCK = r'C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK'", True),
    ('live_caption/replay_c134_mt.py', 'with',
     "LOCK = r'C:\\Users\\Trekker-PTL\\shared\\MACHINE_LOCK'", True),
]


def main():
    changed = []
    failed = []
    for rel, mode, anchor, need_import in PLAN:
        path = os.path.join(REPO, rel)
        with open(path, 'rb') as f:
            raw = f.read()
        # 🔴 **换行风格以 HEAD 为准**（不是以工作区为准）：
        #   实测 `app062` 工作区是 CRLF、HEAD 是 LF ⇒ 按工作区判会**整文件改换行**
        #   ⇒ 制造 378 行假 diff。⇒ 基准取 `git show HEAD:<rel>`。
        try:
            import subprocess
            head_raw = subprocess.run(['git', 'show', 'HEAD:' + rel],
                                      cwd=REPO, capture_output=True).stdout
        except Exception:
            head_raw = b''
        crlf = bool(head_raw) and (b'\r\n' in head_raw)
        text = raw.decode('utf-8').replace('\r\n', '\n')   # 归一化
        orig = text

        rx = RE_OLD_TRY if mode == 'try' else RE_OLD_WITH
        matches = list(rx.finditer(text))
        if len(matches) != 1:
            failed.append((rel, '旧块命中 %d 次（应恰好 1 次）' % len(matches)))
            continue

        old_block = matches[0].group(0)
        # 从旧块里**抽出**要保留的语义（模块名变量 / 打印文案 / 返回值形状）
        m_var = re.search(r"\b(module|tag)\b", old_block)
        var = m_var.group(1) if m_var else 'module'
        # 打印文案：只取 **`print(...)` 的参数部分**（不含 `print(` 与 `)`）
        m_msg = re.search(r"print\((.*)\)\s*\n", old_block)
        msg = m_msg.group(1).strip() if m_msg else "'[lock] 已取得 %s' % LOCK"
        # 返回值形状：`True` / `True, waited, None` ⇒ 失败时把 True 换成 False
        m_ret = re.search(r"return (True[^\n]*)", old_block)
        ret = m_ret.group(1).strip() if m_ret else 'True'
        retfail = ret.replace('True', 'False', 1)

        if mode == 'try':
            new_block = (NEW_TRY.replace('@MOD@', var)
                         .replace('@MSG@', msg))
        else:
            new_block = (NEW_WITH.replace('@MOD@', var)
                         .replace('@RETFAIL@', retfail))
        # 保留「已获取（等了 Ns）」这类紧跟 return 的打印行（with 形态）
        m_after = re.search(r"([ \t]*print\(f?'\[lock\][^\n]*\n)([ \t]*return True[^\n]*\n)",
                            old_block)
        if m_after and m_after.group(1) not in new_block:
            new_block = new_block.replace(
                "    if not machine_lock_app.write_lock_atomic(LOCK, _pay):",
                m_after.group(1) + "    if not machine_lock_app.write_lock_atomic(LOCK, _pay):")

        text = text[:matches[0].start()] + new_block + text[matches[0].end():]

        if need_import and 'import machine_lock_app' not in text:
            if anchor not in text:
                failed.append((rel, '找不到 import 锚点'))
                continue
            text = text.replace(anchor, anchor + '\n' + IMPORT_BLOCK, 1)

        if text == orig:
            failed.append((rel, '无变化'))
            continue
        changed.append((rel, text, crlf))

    print('=' * 66)
    print('待改文件: %d   失败: %d' % (len(PLAN), len(failed)))
    print('=' * 66)
    for rel, why in failed:
        print('  [FAIL] %s  -- %s' % (rel, why))
    for rel, _, _ in changed:
        print('  [ OK ] %s' % rel)

    if DRY:
        print()
        print('（dry-run，未写盘；加 --apply 才落盘）')
        return 1 if failed else 0

    if failed:
        print()
        print('🔴 有失败项 ⇒ **不写任何文件**（避免半改状态）')
        return 1

    print()
    # 🔴 **先编译临时副本，再写盘** ⇒ 任一语法错 ⇒ **目标文件一个都不动**
    #    （上一轮就是「先写后编译」⇒ 写进去才发现语法错 ⇒ 留下坏文件）
    import tempfile
    staged = []
    for rel, text, crlf in changed:
        out = text.replace('\n', '\r\n') if crlf else text
        fd, tmp = tempfile.mkstemp(suffix='.py')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(out.encode('utf-8'))
            try:
                py_compile.compile(tmp, doraise=True)
            except Exception as e:
                print('  [COMPILE-FAIL] %s -- %r' % (rel, e))
                print('🔴 语法错 ⇒ **不写任何文件**')
                return 1
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
        print('  [written+compiled] %s  (crlf=%s)' % (rel, crlf))
    return 0


if __name__ == '__main__':
    sys.exit(main())
