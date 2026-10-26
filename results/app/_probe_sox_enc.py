# -*- coding: utf-8 -*-
"""探测：sox 探测命令的错误字节从哪条路径出来、能不能拿到原文。"""
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

print('=== 环境 ===')
print('PYTHONUTF8 =', os.environ.get('PYTHONUTF8'))
print('PYTHONIOENCODING =', os.environ.get('PYTHONIOENCODING'))

# ① shell=True + 二进制捕获
print('\n=== ① shell=True + PIPE(二进制) ===')
p = subprocess.Popen('sox -h', shell=True, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
out, err = p.communicate()
print('stderr bytes =', err[:60])
for enc in ('gb18030', 'utf-8'):
    try:
        print('  %-8s -> %r' % (enc, err[:44].decode(enc)))
    except Exception as e:
        print('  %-8s -> FAIL %s' % (enc, e))

# ② 关键：os.popen 文本模式拿到的是什么（Python 3.12 的行为）
print('\n=== ② os.popen 文本模式（sox 包实际走的路）===')
try:
    lines = os.popen('sox -h').readlines()
    print('readlines =', repr(lines[:3]))
except Exception as e:
    print('FAIL', type(e).__name__, e)

# ③ 若 os.popen 已被 UTF-8 模式污染，试试 os.popen(...,'rb')
print('\n=== ③ os.popen 二进制模式 ===')
try:
    data = os.popen('sox -h', 'rb').read()
    print('bytes =', data[:60])
    for enc in ('gb18030', 'utf-8'):
        try:
            print('  %-8s -> %r' % (enc, data[:44].decode(enc)))
        except Exception as e:
            print('  %-8s -> FAIL %s' % (enc, e))
except Exception as e:
    print('FAIL', type(e).__name__, e)

# ④ 能不能让 cmd 用英文报错：改 PATH 让 sox 存在但不可执行？
print('\n=== ④ 结论用：哪些是「可恢复」的 ===')
print('→ 若 ②③ 拿到的是 GBK 原文，说明只要在解码层选对编码就能修好；')
print('→ 若 ②③ 已是 U+FFFD，说明字节在 Python 文本层已不可恢复，')
print('   唯一出路是**不让 sox 探测发生**（预置一个假 sox 或直接屏蔽该包）。')
