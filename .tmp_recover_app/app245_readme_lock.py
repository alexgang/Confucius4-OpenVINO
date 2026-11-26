"""LOCK-001: 在 shared/README_LOCK.md 顶部加指向段（保留旧文备查）。

幂等：已含 'LOCK-001' 则跳过。行尾按原文件（实测纯 LF）保持。
不变量：CRLF 计数不变（0）、文件变大、首行标题未变、旧正文逐字仍在。
"""
import hashlib
import io
import sys

P = r'C:\Users\Trekker-PTL\shared\README_LOCK.md'

BLOCK = """> 🔴 **LOCK-001（2026-11-26）起改用 `shared\\tools\\machine_lock.py`，不再手工建/删 `MACHINE_LOCK`。**
> 起作业：`python C:\\Users\\Trekker-PTL\\shared\\tools\\machine_lock.py run --module <模块> --note "<说明>" -- <命令>`
> 查状态：`… machine_lock.py status`（`FREE` / `HELD` / `STALE`）；清残留：`… reclaim`（有活作业时它什么都不做）。
> 机制：锁由**作业进程**持操作系统级独占（`MACHINE_LOCK.os`），进程无论正常结束、崩溃、被杀、会话断掉，Windows 都自动释放 ⇒ **不会再有死锁**。仍写人能看懂的 `MACHINE_LOCK`（`<模块> <pid> <时间> machine_lock.py <说明>` + `job_pid …`），作业结束自动删除。
> 退出码：作业自己的 rc；**75 = 等锁超时未跑**（上限 120 min）；**124 = 作业超时被杀**（默认 240 min）。
> 全文见 QQ 邮箱 LOCK-001（2026-11-26 11:59Z）。⚠️ 下面这段是**旧机制**，仅作备查，不要再照做。

"""

OLD_TAIL = "计时或测速作业开始前先创建 MACHINE_LOCK"


def main():
    raw = open(P, 'rb').read()
    src = raw.decode('utf-8')
    crlf_before = src.count('\r\n')
    old_line = [l for l in src.split('\n') if OLD_TAIL in l]
    if 'LOCK-001' in src:
        print('SKIP: 已含 LOCK-001')
        return 0
    if len(old_line) != 1:
        print('FAIL: 旧正文命中 %d 次' % len(old_line))
        return 2
    lines = src.split('\n')
    # lines[0] = '# 共享机器锁…'，lines[1] = 旧正文
    assert lines[0].startswith('# 共享机器锁'), lines[0][:40]
    assert lines[1].strip() == old_line[0].strip()
    new_lines = [lines[0], ''] + BLOCK.rstrip('\n').split('\n') + \
                ['~~旧机制~~：' + lines[1]] + lines[2:]
    out = '\n'.join(new_lines)

    # 不变量
    assert out.count('\r\n') == crlf_before, 'CRLF 计数变了'
    assert len(out.encode()) > len(raw)
    assert old_line[0].strip() in out
    assert out.startswith('# 共享机器锁')

    open(P, 'wb').write(out.encode('utf-8'))
    b = open(P, 'rb').read()
    print('WROTE bytes=%d sha256=%s CRLF=%d lines=%d'
          % (len(b), hashlib.sha256(b).hexdigest(), b.count(b'\r\n'),
             b.decode().count('\n') + 1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
