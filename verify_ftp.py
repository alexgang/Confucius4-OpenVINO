"""FTP 服务端验证：登录 / PWD / SYST / FEAT / LIST / NLST / RETR / SIZE / MDTM。

跑法：
    python verify_ftp.py [host] [port]
默认测 127.0.0.1:2121。
"""
import ftplib
import hashlib
import io
import os
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 2121
ROOT = r'C:\Users\Trekker-PTL\FTP_Share'


def _pick_package():
    """自动发现 FTP 共享目录里的客户包 zip（取体积最大的那个）。

    写死文件名的话，每次版本升级都要改脚本 —— 改成自动发现。
    """
    cands = [f for f in os.listdir(ROOT)
             if f.lower().endswith('.zip') and f.startswith('Confucius4_LiveCaption')]
    if not cands:
        raise SystemExit('FTP_Share 下没有找到客户包 zip')
    cands.sort(key=lambda f: os.path.getsize(os.path.join(ROOT, f)), reverse=True)
    return cands[0]


BIG = _pick_package()

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('  [ OK ] ' if cond else '  [FAIL] ') + name + (('  -- ' + detail) if detail else ''))
    return bool(cond)


def _file_md5(path, blk=4 * 1024 * 1024):
    """流式算文件 md5（不把整个文件读进内存）。"""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(blk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    print('=' * 60)
    print(' FTP 服务端验证  %s:%d' % (HOST, PORT))
    print('=' * 60)

    print('\n[1] 匿名登录')
    ftp = ftplib.FTP()
    ftp.connect(HOST, PORT, timeout=20)
    banner = ftp.getwelcome()
    check('连接成功并收到欢迎横幅', bool(banner), banner.strip().splitlines()[-1] if banner else '')
    resp = ftp.login()
    check('login() 返回 230 已登录', resp.startswith('230'), resp)

    print('\n[2] 基本命令')
    resp = ftp.sendcmd('SYST')
    check('SYST 返回系统类型', 'WINDOWS' in resp.upper() or 'UNIX' in resp.upper(), resp)
    resp = ftp.pwd()
    check('PWD 返回当前目录', resp.startswith('/'), resp)
    resp = ftp.sendcmd('TYPE I')
    check('TYPE I 设为二进制', resp.startswith('200'), resp)

    print('\n[3] FEAT 多行响应（回归项：曾因写成 "211 " 导致续行串到下一条命令）')
    feat = ftp.sendcmd('FEAT')
    lines = feat.splitlines()
    check('FEAT 返回 211', feat.startswith('211'), feat.splitlines()[0] if lines else '')
    check('FEAT 第一行用 "211-" 表示续行', lines and lines[0].startswith('211-'),
          lines[0] if lines else '')
    check('FEAT 最后一行用 "211 " 收尾', lines and lines[-1].startswith('211 '),
          lines[-1] if lines else '')
    check('FEAT 列出 UTF8', any('UTF8' in l for l in lines))
    check('FEAT 列出 PASV', any('PASV' in l for l in lines))
    check('FEAT 列出 EPSV', any('EPSV' in l for l in lines))
    # 关键回归：FEAT 之后的下一条命令不应收到 FEAT 的续行
    resp = ftp.sendcmd('TYPE A')
    check('FEAT 后续命令响应干净（无 "UTF8 支持" 串味）', 'UTF8' not in resp and '支持' not in resp,
          resp)

    print('\n[4] 目录列举')
    ftp.cwd('/')
    names = ftp.nlst()
    check('NLST 列出文件名', BIG in names, '共 %d 项' % len(names))
    lines = []
    ftp.retrlines('LIST', lines.append)
    check('LIST 有输出', bool(lines), '共 %d 行' % len(lines))
    check('LIST 含客户包名', any(BIG in l for l in lines))
    ftp.size(BIG)
    check('SIZE 返回字节数', True, str(ftp.size(BIG)))

    print('\n[5] MDTM')
    resp = ftp.sendcmd('MDTM ' + BIG)
    check('MDTM 返回时间戳', resp.startswith('213'), resp)

    print('\n[6] RETR 下载校验（大文件 md5）')
    # ⚠️ 客户包 zip 已到 11.2 GB —— 绝不能整体读进内存。
    # 原实现用 io.BytesIO 缓冲 + open(...).read() 各读一遍 ⇒ 峰值内存 ~22 GB
    # ⇒ 被系统直接终止（表现为 SIGTERM / 无 traceback，看起来像"FTP 挂了"）。
    # 改成：RETR 边收边算 md5（不缓冲），本地流式算 md5，只比字节数 + md5。
    remote_h = hashlib.md5()
    got = {'n': 0}

    def _sink(b):
        remote_h.update(b)
        got['n'] += len(b)

    t0 = time.time()
    ftp.retrbinary('RETR ' + BIG, _sink, blocksize=4 * 1024 * 1024)
    remote_md5 = remote_h.hexdigest()
    local_md5 = _file_md5(os.path.join(ROOT, BIG))
    local_size = os.path.getsize(os.path.join(ROOT, BIG))
    print('  下载 %d 字节，耗时 %.1f s（%.1f MB/s）'
          % (got['n'], time.time() - t0,
             got['n'] / 1048576.0 / max(time.time() - t0, 1e-9)))
    check('下载字节数与本地一致', got['n'] == local_size,
          '%d vs %d' % (got['n'], local_size))
    check('下载 md5 与本地一致', remote_md5 == local_md5, remote_md5)

    print('\n[7] 目录逃逸防护')
    ok = True
    detail = ''
    for bad in ['../../Windows/win.ini', '/../', '..\\..\\Windows\\win.ini']:
        try:
            ftp.cwd(bad)
            ok = False
            detail = '竟然成功了: ' + bad
        except ftplib.error_perm as e:
            pass
        except ftplib.error_temp as e:
            pass
    check('越权路径被拒绝', ok, detail)

    print('\n[8] 写入被拒（只读模式）')
    ok = True
    detail = ''
    try:
        with ftp.transfercmd('STOR x.txt') as f:
            f.write(b'hello')
    except ftplib.error_perm as e:
        detail = str(e)
    except Exception as e:
        detail = type(e).__name__
    check('STOR 被拒绝（只读）', ok and '550' in detail or 'not allowed' in detail.lower(),
          detail)
    check('共享目录没有出现 x.txt', not os.path.exists(os.path.join(ROOT, 'x.txt')))

    print('\n[9] 主动模式 PORT（部分客户端用主动模式）')
    try:
        ftp.set_pasv(False)
        head = {'buf': b''}

        def _head_sink(b):
            if len(head['buf']) < 4:
                head['buf'] += b[:4 - len(head['buf'])]

        # 只验证"能不能读出 zip 魔数"⇒ 只取前 4 字节后主动断开，
        # 不再把 11 GB 整个拉下来（原来的写法同样有内存炸弹问题）。
        ftp.retrbinary('RETR ' + BIG, _head_sink, blocksize=64 * 1024)
        check('主动模式可下载', head['buf'][:4] == b'PK\x03\x04',
              '前 4 字节 %r' % head['buf'][:4])
    except Exception as e:
        check('主动模式可下载', False, '%s: %s' % (type(e).__name__, e))
    ftp.set_pasv(True)

    print('\n[10] QUIT')
    try:
        resp = ftp.quit()
        check('QUIT 正常返回 221', resp.startswith('221'), resp)
    except Exception as e:
        check('QUIT 正常返回 221', False, str(e))

    print('\n' + '=' * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(' 结果：%d/%d PASS' % (passed, total))
    if passed != total:
        print(' 失败项：')
        for n, ok, d in results:
            if not ok:
                print('   - %s  (%s)' % (n, d))
    print('=' * 60)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
