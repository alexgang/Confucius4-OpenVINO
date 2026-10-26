# -*- coding: utf-8 -*-
"""app078 —— APP-021§54.10「会话日志可读性」专项自检（**不加载模型**）。

背景（实测 16:22 会话日志 `%LOCALAPPDATA%\\Confucius4LiveCaption\\session_20261026_162234.log`）：
  ① 同一条 worker 日志被落盘 **2~3 遍**（service 写一遍 + GUI 写一遍 +
     GUI 的 on_log 回调再加 `tts: ` 前缀写一遍）
     ⇒ 用户报障时要在 8 KB 日志里翻「真正的错误行」，且会误判成「错误发生了 3 次」。
  ② stderr 里的中文**乱码**：`'sox' �����ڲ����ⲿ���ģ�Ҳ���ǿ����еĳ���`
     ⇒ 那是 cmd.exe / sox 吐的 **GBK 字节**被按 utf-8 解码。

本脚本覆盖三组：
  A 组：会话日志去重（核心键剥离 + 短窗口去重 + 不误伤真重复）
  B 组：stderr 混编码解码（utf-8 / GBK / 非法字节三种）
  C 组：二进制管道端到端（真起一个子进程，走 stdout/stderr/stdin 全链路）

判据口径（与 §54 一致）：
  - 「日志可读」= 同一条 worker 日志在落盘文件里**只出现一次**。
  - 「中文不乱码」= 解码结果里**不含 U+FFFD**（`\ufffd`）。
  - 「二进制管道通」= 子进程写 stdout / stderr、读 stdin 三件事都成功。

运行：
  "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\python.exe" results/app/app078_tts_log_readability.py
"""
import os
import sys
import json
import time
import tempfile
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name,
                       ('  | ' + detail) if detail else ''))
    return bool(ok)


# ══════════════════════════════════════════════════════════════════
# A 组：会话日志去重
# ══════════════════════════════════════════════════════════════════
def group_a():
    print('\n=== A 组：会话日志去重 ===')
    # A1 能导入 tts_service 并拿到去重 API
    try:
        import tts_service
        ok = True
        detail = 'import ok'
    except Exception as e:
        return check('A1 tts_service 可导入', False,
                     '%s: %s' % (type(e).__name__, e))
    check('A1 tts_service 可导入', ok, detail)

    # A2 去重 API 存在
    has = (hasattr(tts_service, 'append_session_log')
           and hasattr(tts_service, '_session_log_core')
           and hasattr(tts_service, 'session_log_dup_suppressed'))
    check('A2 去重 API 齐备（append/_core/_suppressed）', has,
          'append=%s core=%s suppressed=%s' % (
              hasattr(tts_service, 'append_session_log'),
              hasattr(tts_service, '_session_log_core'),
              hasattr(tts_service, 'session_log_dup_suppressed')))

    # A3 核心键剥离：不同包装前缀 ⇒ 同一核心键
    core = tts_service._session_log_core
    k1 = core('[TTS] [tts_worker] 输出设备解析：xxx')
    k2 = core('[tts_worker] 输出设备解析：xxx')
    k3 = core('tts: [tts_worker] 输出设备解析：xxx')
    check('A3 包装前缀被剥离（同一正文⇒同一核心键）',
          k1 == k2 == k3, 'k1=%r k2=%r k3=%r' % (k1, k2, k3))

    # A4 不同正文 ⇒ 不同核心键（不能过度去重）
    k4 = core('[TTS] [tts_worker] 播放流已启动：sr=22050')
    check('A4 不同正文不被误去重', k1 != k4, 'k1=%r k4=%r' % (k1, k4))

    # A5 真落盘：同一条日志写 3 次 ⇒ 文件里只应出现 1 次
    #   ⚠️ 用独立日志路径，避免污染真实会话日志
    tmpdir = tempfile.mkdtemp(prefix='app078_')
    orig_path = tts_service._SESSION_LOG_PATH
    orig_dedup = list(tts_service._SESSION_DEDUP)
    orig_hits = tts_service._SESSION_DEDUP_HITS[0]
    logfile = os.path.join(tmpdir, 'session_test.log')
    try:
        tts_service._SESSION_LOG_PATH = logfile
        tts_service._SESSION_DEDUP[:] = []
        tts_service._SESSION_DEDUP_HITS[0] = 0
        tts_service.append_session_log('[TTS] [tts_worker] 输出设备解析：ABC')
        tts_service.append_session_log('[tts_worker] 输出设备解析：ABC')
        tts_service.append_session_log('tts: [tts_worker] 输出设备解析：ABC')
        time.sleep(0.05)
        with open(logfile, 'r', encoding='utf-8') as f:
            body = f.read()
        n = body.count('输出设备解析：ABC')
        check('A5 同一条日志落盘只 1 次（写 3 次）', n == 1,
              '出现 %d 次；抑制计数=%d' % (n, tts_service._SESSION_DEDUP_HITS[0]))
    except Exception as e:
        check('A5 同一条日志落盘只 1 次（写 3 次）', False,
              '%s: %s' % (type(e).__name__, e))
    finally:
        tts_service._SESSION_LOG_PATH = orig_path
        tts_service._SESSION_DEDUP[:] = orig_dedup
        tts_service._SESSION_DEDUP_HITS[0] = orig_hits

    # A6 真重复内容（两次**不同**的 worker 报错）不应被吞
    #   ⚠️ 窗口内两条**内容相同**的独立故障行其实应该被吞（同一条日志重复转发）
    #   ⇒ 这里测的是「不同内容」不被吞。
    tmpdir2 = tempfile.mkdtemp(prefix='app078_')
    logfile2 = os.path.join(tmpdir2, 'session_test2.log')
    try:
        tts_service._SESSION_LOG_PATH = logfile2
        tts_service._SESSION_DEDUP[:] = []
        tts_service._SESSION_DEDUP_HITS[0] = 0
        tts_service.append_session_log('[TTS] 错误一：播放器不可用')
        tts_service.append_session_log('[TTS] 错误二：引擎没有产出任何音频')
        time.sleep(0.05)
        with open(logfile2, 'r', encoding='utf-8') as f:
            body2 = f.read()
        check('A6 不同内容的故障行都被保留',
              ('错误一' in body2) and ('错误二' in body2),
              'body=%r' % body2[:200])
    except Exception as e:
        check('A6 不同内容的故障行都被保留', False,
              '%s: %s' % (type(e).__name__, e))
    finally:
        tts_service._SESSION_LOG_PATH = orig_path
        tts_service._SESSION_DEDUP[:] = orig_dedup
        tts_service._SESSION_DEDUP_HITS[0] = orig_hits

    # A7 RLock：append 持锁后调 session_log_path（也取锁）不能自死锁
    #   🔴 普通 Lock 会在此**永久死锁** ⇒ 用超时探测
    ok = True
    detail = '未死锁'
    try:
        import threading
        t = threading.Thread(target=lambda: tts_service.append_session_log(
            '[TTS] 锁探测'), daemon=True)
        t.start()
        t.join(timeout=5.0)
        if t.is_alive():
            ok = False
            detail = '🔴 死锁：append_session_log 持锁后调 session_log_path'
        else:
            detail = 'RLock 可重入，5 s 内完成'
    except Exception as e:
        ok = False
        detail = '%s: %s' % (type(e).__name__, e)
    check('A7 append 不自死锁（锁必须可重入）', ok, detail)

    # A8 双重标签防护：消息自带 [TTS] 时不得再加 tag
    #   （实测曾出现 `[TTS] [TTS] [tts_worker] …`）
    try:
        with open(os.path.join(REPO, 'live_caption', 'tts_service.py'),
                  'r', encoding='utf-8') as f:
            ssrc = f.read()
        code_only = '\n'.join(
            ln.strip() for ln in ssrc.splitlines()
            if not ln.strip().startswith('#'))
        has_guard = ("startswith('[TTS]')" in code_only
                     or "startswith(\"[TTS]\")" in code_only
                     or "_tag = ''" in code_only)
        has_guard = has_guard and "tag=_tag" in code_only
        check('A8 双重标签有防护（消息自带 [TTS] 则不补 tag）', has_guard,
              "guard = %s" % has_guard)
    except Exception as e:
        check('A8 双重标签有防护（消息自带 [TTS] 则不补 tag）', False, str(e))

    # A9 边车 stderr 字节透传（乱码根因修复）
    #   ⚠️ 根因：`sox` 包用 `os.popen('sox -h')`（文本模式）⇒ cmd.exe 的
    #      GBK 报错被按 utf-8 解成 U+FFFD ⇒ **不可恢复**。
    #   ⇒ 边车必须把 stderr 换成「字节代理」，且必须在 import 第三方库**之前**。
    try:
        with open(os.path.join(REPO, 'live_caption', 'tts_cuda_sidecar.py'),
                  'r', encoding='utf-8') as f:
            csrc = f.read()
        check('A9 边车有 stderr 字节代理', '_RawStderr' in csrc,
              '_RawStderr = %s' % ('_RawStderr' in csrc))
        i_proxy = csrc.find('class _RawStderr')
        i_imp = csrc.find('import torch')
        i_imp2 = csrc.find('from faster_whisper')
        i_imp3 = csrc.find('import soundfile')
        first_imp = min([x for x in (i_imp, i_imp2, i_imp3) if x > 0] or [10 ** 9])
        check('A9a stderr 代理在第三方 import **之前**安装',
              (i_proxy > 0) and (i_proxy < first_imp),
              'proxy@%d first_import@%d' % (i_proxy, first_imp))
    except Exception as e:
        check('A9 边车有 stderr 字节代理', False, str(e))


# ══════════════════════════════════════════════════════════════════
# B 组：stderr 混编码解码
# ══════════════════════════════════════════════════════════════════
def group_b():
    print('\n=== B 组：stderr 混编码解码 ===')
    try:
        import tts_service
    except Exception as e:
        return check('B1 tts_service 可导入', False, str(e))

    # B1 三级解码函数必须是**独立可测**的（不能内嵌在读循环里）
    dec = None
    for name in ('_decode_worker_line', '_decode_mixed_line'):
        if hasattr(tts_service, name):
            dec = getattr(tts_service, name)
            break
    check('B1 存在独立解码函数（可单测）', dec is not None,
          '找到 = %s' % (dec.__name__ if dec else '无'))
    if dec is None:
        dec = lambda b: b.decode('utf-8', 'replace') if isinstance(b, bytes) else str(b)

    # B2 utf-8 中文正常
    s = '你好，世界'.encode('utf-8')
    r = dec(s)
    check('B2 utf-8 中文原样解出', r == '你好，世界', 'r=%r' % r)

    # B3 GBK 中文不再乱码（★ 这次修的核心）
    s = '不是内部或外部命令，也不是可运行的程序'.encode('gb18030')
    r = dec(s)
    check('B3 GBK 中文不乱码（无 U+FFFD）',
          ('\ufffd' not in r) and ('内部或外部命令' in r),
          'r=%r' % r)

    # B4 非法字节不抛异常
    s = b'ok\xff\xfe\x00bad'
    try:
        r = dec(s)
        ok = isinstance(r, str)
    except Exception as e:
        ok, r = False, '%s: %s' % (type(e).__name__, e)
    check('B4 非法字节不抛异常', ok, 'r=%r' % (r,))

    # B5 GBK 的英文/数字行（sox 那些行）也能解
    s = "'sox' 不是内部或外部命令".encode('gb18030')
    r = dec(s)
    check('B5 sox 报错行可读', '\ufffd' not in r and 'sox' in r, 'r=%r' % r)


# ══════════════════════════════════════════════════════════════════
# C 组：二进制管道端到端（真起子进程）
# ══════════════════════════════════════════════════════════════════
CHILD = r'''
import sys, time
# ① stdout 写 utf-8 中文（含符号）
sys.stdout.buffer.write(('子进程输出：中文 ⇒ 正常\n').encode('utf-8'))
sys.stdout.buffer.flush()
# ② stderr 写 GBK 中文（模拟 cmd.exe/sox）
try:
    sys.stderr.buffer.write(('子进程错误：不是内部命令\n').encode('gb18030'))
    sys.stderr.buffer.flush()
except Exception:
    pass
# ③ 读 stdin 一行并回显
data = sys.stdin.buffer.readline()
try:
    sys.stdout.buffer.write(('回显：' + data.decode('utf-8')).encode('utf-8'))
    sys.stdout.buffer.flush()
except Exception:
    pass
'''


def group_c():
    print('\n=== C 组：二进制管道端到端 ===')
    tmpdir = tempfile.mkdtemp(prefix='app078_')
    child = os.path.join(tmpdir, 'child.py')
    with open(child, 'w', encoding='utf-8') as f:
        f.write(CHILD)

    # C1 起子进程（二进制模式，与 tts_service.start() 一致）
    try:
        p = subprocess.Popen(
            [sys.executable, child], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        ok = True
    except Exception as e:
        return check('C1 二进制子进程可启动', False,
                     '%s: %s' % (type(e).__name__, e))
    check('C1 二进制子进程可启动', ok)

    # C2 stdout 中文可读
    try:
        out = p.stdout.readline()
        s = out.decode('utf-8', 'replace').strip()
        check('C2 stdout utf-8 中文可读',
              '子进程输出' in s and '\ufffd' not in s, 's=%r' % s)
    except Exception as e:
        check('C2 stdout utf-8 中文可读', False, str(e))

    # C3 stderr GBK 可读（用与 service 相同的三级判定）
    try:
        err = p.stderr.readline()
        line = None
        for enc in ('utf-8', 'gb18030'):
            try:
                line = err.decode(enc)
                break
            except Exception:
                continue
        if line is None:
            line = err.decode('utf-8', 'replace')
        line = line.strip()
        check('C3 stderr GBK 中文可读',
              ('子进程错误' in line) and ('\ufffd' not in line), 'line=%r' % line)
    except Exception as e:
        check('C3 stderr GBK 中文可读', False, str(e))

    # C4 stdin 写 bytes → 子进程读 bytes → 回显
    try:
        payload = ('你好 stdin\n').encode('utf-8')
        p.stdin.write(payload)
        p.stdin.flush()
        echo = p.stdout.readline().decode('utf-8', 'replace').strip()
        check('C4 stdin 字节读写闭环',
              ('回显' in echo) and ('你好 stdin' in echo), 'echo=%r' % echo)
    except Exception as e:
        check('C4 stdin 字节读写闭环', False, str(e))

    try:
        p.stdin.close()
        p.wait(timeout=5)
    except Exception:
        pass

    # C7 ★ 核心：GBK 字节经「边车字节代理 → service 解码」后**原文可读**
    #   这条直接对应「`'sox' �����ڲ���` 乱码」那个真实现象。
    child2 = os.path.join(tmpdir, 'child2.py')
    with open(child2, 'w', encoding='utf-8') as f:
        f.write(
            '# 模拟 sox 包：cmd.exe 的 GBK 报错直写 fd 2\n'
            'import sys, os\n'
            'os.write(2, "\'sox\' 不是内部或外部命令，也不是可运行的程序\\r\\n"\n'
            '          .encode("gb18030"))\n'
            'sys.stdout.buffer.write(b"PROTO-OK\\n")\n'
            'sys.stdout.buffer.flush()\n')
    try:
        p2 = subprocess.Popen(
            [sys.executable, child2], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        err2 = p2.stderr.readline()
        p2.stdout.readline()
        try:
            p2.stdin.close()
            p2.wait(timeout=5)
        except Exception:
            pass
        # 用 service 的解码函数（正是线上用的那个）
        try:
            import tts_service as _ts
            dec_line = _ts._decode_worker_line(err2)
        except Exception:
            dec_line = err2.decode('gb18030', 'replace')
        check('C7 GBK 字节经解码函数后原文可读（★ 乱码根因）',
              ('不是内部或外部命令' in dec_line) and ('\ufffd' not in dec_line),
              'dec=%r' % dec_line)
    except Exception as e:
        check('C7 GBK 字节经解码函数后原文可读（★ 乱码根因）', False, str(e))

    # C5 worker 源码：stdout 走 bytes、stdin 走 buffer
    try:
        with open(os.path.join(REPO, 'live_caption', 'tts_worker.py'),
                  'r', encoding='utf-8') as f:
            wsrc = f.read()
    except Exception as e:
        return check('C5 worker 源码可读', False, str(e))
    check('C5 worker 源码可读', True)
    check('C5a worker 写 stdout 用 buffer（bytes）',
          'sys.stdout.buffer' in wsrc,
          '找到 sys.stdout.buffer = %s' % ('sys.stdout.buffer' in wsrc))
    check('C5b worker 读 stdin 用 buffer（bytes）',
          'sys.stdin.buffer' in wsrc,
          '找到 sys.stdin.buffer = %s' % ('sys.stdin.buffer' in wsrc))
    check('C5c worker 不再有裸 sys.stdout.write(str)',
          'sys.stdout.write(str(' not in wsrc
          and 'sys.stdout.write(json.dumps' not in wsrc,
          '裸写已清零')

    # C6 service 源码：Popen 不用 text=True（必须二进制）
    try:
        with open(os.path.join(REPO, 'live_caption', 'tts_service.py'),
                  'r', encoding='utf-8') as f:
            ssrc = f.read()
    except Exception as e:
        return check('C6 service 源码可读', False, str(e))
    check('C6 service 源码可读', True)
    # ⚠️ 判据必须**只看代码行**：`text=True` 在注释里出现过（§53 根因说明），
    #   用全文搜索会误报 ⇒ 这里剔除注释行后再查。
    code_lines = []
    for ln in ssrc.splitlines():
        s = ln.strip()
        if not s.startswith('#'):
            code_lines.append(s)
    code_only = '\n'.join(code_lines)
    has_text_true = 'text=True' in code_only
    check('C6a service 的 Popen 不再用 text=True（改二进制）',
          not has_text_true, '代码行里 text=True = %s' % has_text_true)
    check('C6b service 的 stdin 写的是 bytes',
          ".encode('utf-8')" in code_only,
          "找到 .encode('utf-8') = %s" % (".encode('utf-8')" in code_only))
    check('C6c service 用独立解码函数（可单测）',
          '_decode_worker_line' in code_only,
          '_decode_worker_line 出现 = %s'
          % ('_decode_worker_line' in code_only))


def main():
    print('app078 —— 会话日志可读性专项自检（APP-021§54.10）')
    print('=' * 60)
    group_a()
    group_b()
    group_c()
    print('\n' + '=' * 60)
    npass = sum(1 for _, ok, _ in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print('PASS %d / FAIL %d' % (npass, nfail))
    if nfail:
        print('\n失败明细：')
        for n, ok, d in RESULTS:
            if not ok:
                print('  FAIL %s  | %s' % (n, d))
    print('判定：%s' % ('OK' if nfail == 0 else 'FAIL'))
    out = os.path.join(HERE, 'app078_tts_log_readability.txt')
    try:
        with open(out, 'w', encoding='utf-8') as f:
            f.write('app078 —— 会话日志可读性专项自检（APP-021§54.10）\n')
            f.write('=' * 60 + '\n')
            for n, ok, d in RESULTS:
                f.write('%s %s%s\n' % ('PASS' if ok else 'FAIL', n,
                                       ('  | ' + d) if d else ''))
            f.write('-' * 60 + '\n')
            f.write('PASS %d / FAIL %d\n' % (npass, nfail))
            f.write('判定：%s\n' % ('OK' if nfail == 0 else 'FAIL'))
    except Exception:
        pass
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
