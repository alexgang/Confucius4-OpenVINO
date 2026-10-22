#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ftp_share.py — 局域网 FTP 文件服务（零依赖，只用 Python 标准库）

用途：把客户包放在局域网里，让客户直接用 FTP 客户端 / 资源管理器下载，
不必挨个拷贝 U 盘或网盘。

为什么自己写而不用 pyftpdlib：
  客户机 / 交付环境不一定装了 pyftpdlib，而 FTP 服务端只需要被动模式
  （PASV）就能被 Windows 资源管理器、FileZilla、浏览器（ftp://）访问。
  这里用标准库 socketserver + socket 实现最小可用的 FTP 服务端。

支持：
  USER / PASS / SYST / FEAT / TYPE / PWD / CWD / CDUP / PASV / EPSV
  LIST / NLST / RETR / STOR / DELE / MKD / RMD / RNFR / RNTO / SIZE / MDTM
  NOOP / QUIT
  主动模式（PORT）也支持，但被动模式（PASV）更常用。

安全默认值：
  - **只读**（--write 打开写入）
  - 匿名登录，密码任意（用户名任意）—— 局域网内分发用
  - 根目录锁定在 --root 内，客户端无法用 .. 逃出去
  - 监听 0.0.0.0，供局域网访问

用法：
    python ftp_share.py --root C:\\Users\\Trekker-PTL --port 2121
    python ftp_share.py --root . --port 2121 --write
    python ftp_share.py --root . --port 2121 --lan-only
"""
import argparse
import errno
import os
import socket
import socketserver
import sys
import threading
import time

# FTP 的控制连接用 CRLF；数据连接用二进制原样传输。
CRLF = b'\r\n'


class FTPHandler(socketserver.BaseRequestHandler):
    """一个 FTP 控制连接。"""

    # 由 serve() 注入
    server: 'FTPServer'

    def setup(self):
        self.request.settimeout(300)
        self.rfile = self.request.makefile('rb')
        self.user = None
        self.authed = False
        self.cwd = os.path.abspath(self.server.root)
        self.data_sock = None
        self.data_listen = None
        self.pasv = False
        self.rename_from = None
        self.type = 'I'
        self._send(220, self.server.banner)

    def finish(self):
        try:
            self._close_data()
        except Exception:
            pass
        try:
            self.request.close()
        except Exception:
            pass

    # -- 低层收发 --------------------------------------------------------
    def _send(self, code, msg=''):
        line = f'{code} {msg}'.encode('utf-8', 'replace')
        self.request.sendall(line + CRLF)

    def _readline(self):
        raw = self.rfile.readline()
        if not raw:
            raise EOFError
        return raw.rstrip(b'\r\n').decode('utf-8', 'replace')

    def _close_data(self):
        for attr in ('data_sock', 'data_listen'):
            s = getattr(self, attr, None)
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
                setattr(self, attr, None)

    # -- 路径解析（防目录逃逸）------------------------------------------
    def _resolve(self, arg):
        """把客户端给的路径解析成绝对路径，并确保不跳出 root。"""
        arg = (arg or '').replace('\\', '/')
        if arg.startswith('/'):
            p = os.path.abspath(os.path.join(self.server.root, arg.lstrip('/')))
        else:
            p = os.path.abspath(os.path.join(self.cwd, arg))
        # 用 os.path.commonpath 兜住 .. 逃逸
        try:
            if os.path.commonpath([os.path.abspath(self.server.root), p]) != \
                    os.path.abspath(self.server.root):
                return None
        except ValueError:
            return None
        return p

    def _listable(self, path):
        """真实路径 -> 供 LIST 显示的名字（把 root 前缀去掉）。"""
        rel = os.path.relpath(path, self.server.root)
        return '.' if rel == '.' else rel.replace('\\', '/')

    def _virtual(self, path):
        """真实路径 -> FTP 虚拟路径（必须以 '/' 开头，RFC 959 要求）。

        PWD 要返回这个；很多客户端（资源管理器 / FileZilla）会拿 PWD 的
        结果去拼后续路径，返回 '.' 会被当成相对路径而解析错。
        """
        rel = os.path.relpath(path, self.server.root)
        if rel == '.':
            return '/'
        return '/' + rel.replace('\\', '/')

    # -- 命令处理 --------------------------------------------------------
    def handle(self):
        try:
            while True:
                line = self._readline()
                if not line:
                    break
                if not self._dispatch(line):
                    break
        except (EOFError, ConnectionResetError, socket.timeout):
            pass
        except Exception as e:
            self.server.log(f'会话异常：{type(e).__name__}: {e}')

    def _dispatch(self, line):
        if not line.strip():
            return True
        cmd, _, arg = line.partition(' ')
        cmd = cmd.upper().strip()
        arg = arg.strip()
        fn = getattr(self, 'cmd_' + cmd, None)
        if fn is None:
            self._send(502, f'命令未实现：{cmd}')
            return True
        try:
            return fn(arg)
        except PermissionError:
            self._send(550, '权限不足')
        except FileNotFoundError:
            self._send(550, '文件或目录不存在')
        except Exception as e:
            self.server.log(f'命令 {cmd} 出错：{type(e).__name__}: {e}')
            self._send(451, '本地错误')
        return True

    # ── 登录 / 系统 ────────────────────────────────────────────────
    def cmd_USER(self, arg):
        self.user = arg or 'anonymous'
        self._send(331, '请输入密码（任意密码即可）')
        return True

    def cmd_PASS(self, arg):
        self.authed = True
        self.server.log(f'登录：{self.user or "anonymous"} 来自 {self.client_address[0]}')
        self._send(230, '登录成功')
        return True

    def cmd_SYST(self, arg):
        self._send(215, 'UNIX Type: L8')
        return True

    def cmd_FEAT(self, arg):
        # 有些客户端（尤其 Windows 资源管理器）先问 FEAT。
        # ★ 多行响应的格式必须是「211-」开头（连字符表示续行），
        #   最后一行才用「211 」。写成「211 」会被客户端当成多条独立响应，
        #   后面的续行就会串到下一个命令的响应里去（实测 ftplib 直接报
        #   error_proto: UTF8 支持 UTF-8 文件名）。
        self.request.sendall(b'211-Features:' + CRLF)
        for feat, desc in ((' UTF8', '支持 UTF-8 文件名'),
                           (' PASV', '支持被动模式'),
                           (' EPSV', '支持扩展被动模式'),
                           (' SIZE', '支持 SIZE'),
                           (' MDTM', '支持 MDTM')):
            self.request.sendall(f'{feat} {desc}'.encode('utf-8', 'replace') + CRLF)
        self.request.sendall(b'211 End' + CRLF)
        return True

    def cmd_OPTS(self, arg):
        self._send(200, 'OK')
        return True

    def cmd_NOOP(self, arg):
        self._send(200, 'OK')
        return True

    def cmd_QUIT(self, arg):
        self._send(221, '再见')
        return False

    def cmd_TYPE(self, arg):
        self.type = (arg or 'I').upper()[:1]
        self._send(200, '类型已设为 ' + self.type)
        return True

    # ── 目录操作 ──────────────────────────────────────────────────
    def cmd_PWD(self, arg):
        # 返回虚拟路径（'/' 开头），不要用 _listable —— 那是给 LIST 显示用的
        self._send(257, '"%s" 是当前目录' % self._virtual(self.cwd))
        return True

    def cmd_CWD(self, arg):
        p = self._resolve(arg)
        if not p or not os.path.isdir(p):
            self._send(550, '目录不存在')
            return True
        self.cwd = p
        self._send(250, '目录已切换到 %s' % self._virtual(p))
        return True

    def cmd_CDUP(self, arg):
        return self.cmd_CWD('..')

    def cmd_MKD(self, arg):
        if not self.server.allow_write:
            self._send(550, '只读模式')
            return True
        p = self._resolve(arg)
        if not p:
            self._send(550, '非法路径')
            return True
        os.mkdir(p)
        self._send(257, '"%s" 已创建' % self._listable(p))
        return True

    def cmd_RMD(self, arg):
        if not self.server.allow_write:
            self._send(550, '只读模式')
            return True
        p = self._resolve(arg)
        if not p or not os.path.isdir(p):
            self._send(550, '目录不存在')
            return True
        os.rmdir(p)
        self._send(250, '目录已删除')
        return True

    # ── 数据连接（被动模式 PASV / EPSV）───────────────────────────
    def cmd_PASV(self, arg):
        self._close_data()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 0))
        s.listen(1)
        s.settimeout(60)
        self.data_listen = s
        port = s.getsockname()[1]
        # 用客户端连过来的地址（服务端看到的对端 IP）
        host = self.client_address[0]
        if host.startswith('127.'):
            host = '127.0.0.1'
        h = host.split('.')
        self._send(227, '进入被动模式 (%s,%s,%s,%s,%d,%d)' %
                   (h[0], h[1], h[2], h[3], port >> 8, port & 0xFF))
        return True

    def cmd_EPSV(self, arg):
        self._close_data()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 0))
        s.listen(1)
        s.settimeout(60)
        self.data_listen = s
        port = s.getsockname()[1]
        self._send(229, '进入扩展被动模式 (|||%d|)' % port)
        return True

    def cmd_PORT(self, arg):
        # 主动模式：客户端让服务端连回去
        self._close_data()
        try:
            nums = [int(x) for x in arg.split(',')]
            if len(nums) != 6:
                raise ValueError
            host = '.'.join(str(n) for n in nums[:4])
            port = nums[4] * 256 + nums[5]
            self.data_sock = socket.create_connection((host, port), timeout=30)
            self._send(200, '主动模式已建立')
        except Exception:
            self._send(501, 'PORT 参数无效')
        return True

    def _accept_data(self):
        """接受数据连接（被动模式）。"""
        if self.data_sock is not None:
            return self.data_sock
        if self.data_listen is None:
            raise FileNotFoundError('没有数据连接，请先发 PASV')
        conn, _ = self.data_listen.accept()
        conn.settimeout(300)
        self.data_sock = conn
        return conn

    def _close_data_after(self):
        try:
            if self.data_sock:
                self.data_sock.close()
            if self.data_listen:
                self.data_listen.close()
        except Exception:
            pass
        self.data_sock = None
        self.data_listen = None

    # ── 列表 ──────────────────────────────────────────────────────
    def _list_lines(self, path, want_names_only):
        out = []
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if want_names_only:
                    out.append(name)
                else:
                    # 经典 UNIX ls 格式：权限 链接数 属主 属组 大小 月 日 时间 名
                    isdir = os.path.isdir(full)
                    mode = 'drwxr-xr-x' if isdir else '-rw-r--r--'
                    import time as _t
                    mt = _t.localtime(st.st_mtime)
                    out.append('%s 1 owner group %12d %s %02d %02d %02d %s' % (
                        mode, st.st_size, _t.strftime('%b', mt), mt.tm_mday,
                        mt.tm_hour, mt.tm_min, name))
        elif os.path.isfile(path):
            out.append(os.path.basename(path) if want_names_only else path)
        return out

    def cmd_LIST(self, arg):
        p = self._resolve(arg) if arg else self.cwd
        if not p:
            self._send(550, '非法路径')
            return True
        if not os.path.exists(p):
            self._send(550, '文件不存在')
            return True
        try:
            conn = self._accept_data()
        except Exception as e:
            self._send(425, '无法建立数据连接：%s' % e)
            return True
        self._send(150, '这里有你要的文件列表')
        try:
            lines = self._list_lines(p, want_names_only=False)
            data = ('\r\n'.join(lines) + ('\r\n' if lines else '')).encode('utf-8', 'replace')
            conn.sendall(data)
        finally:
            self._close_data_after()
        self._send(226, '传输完成')
        return True

    def cmd_NLST(self, arg):
        p = self._resolve(arg) if arg else self.cwd
        if not p or not os.path.exists(p):
            self._send(550, '文件不存在')
            return True
        try:
            conn = self._accept_data()
        except Exception as e:
            self._send(425, '无法建立数据连接：%s' % e)
            return True
        self._send(150, '这里有你要的文件列表')
        try:
            lines = self._list_lines(p, want_names_only=True)
            data = ('\r\n'.join(lines) + ('\r\n' if lines else '')).encode('utf-8', 'replace')
            conn.sendall(data)
        finally:
            self._close_data_after()
        self._send(226, '传输完成')
        return True

    # ── 文件传输 ──────────────────────────────────────────────────
    def cmd_RETR(self, arg):
        p = self._resolve(arg)
        if not p or not os.path.isfile(p):
            self._send(550, '文件不存在')
            return True
        try:
            conn = self._accept_data()
        except Exception as e:
            self._send(425, '无法建立数据连接：%s' % e)
            return True
        size = os.path.getsize(p)
        self._send(150, '正在打开 %s（%d 字节）' % (os.path.basename(p), size))
        try:
            with open(p, 'rb') as f:
                sent = 0
                while True:
                    buf = f.read(256 * 1024)
                    if not buf:
                        break
                    conn.sendall(buf)
                    sent += len(buf)
                    if sent % (16 * 1024 * 1024) == 0:
                        self.server.log(f'  传输中 {os.path.basename(p)} '
                                        f'{sent / 1048576:.0f}/{size / 1048576:.0f} MB')
        finally:
            self._close_data_after()
        self._send(226, '传输完成')
        return True

    def cmd_STOR(self, arg):
        if not self.server.allow_write:
            self._send(550, '只读模式')
            return True
        p = self._resolve(arg)
        if not p:
            self._send(550, '非法路径')
            return True
        try:
            conn = self._accept_data()
        except Exception as e:
            self._send(425, '无法建立数据连接：%s' % e)
            return True
        self._send(150, '准备接收 %s' % os.path.basename(p))
        try:
            with open(p, 'wb') as f:
                while True:
                    buf = conn.recv(256 * 1024)
                    if not buf:
                        break
                    f.write(buf)
        finally:
            self._close_data_after()
        self._send(226, '传输完成')
        return True

    def cmd_DELE(self, arg):
        if not self.server.allow_write:
            self._send(550, '只读模式')
            return True
        p = self._resolve(arg)
        if not p or not os.path.isfile(p):
            self._send(550, '文件不存在')
            return True
        os.remove(p)
        self._send(250, '文件已删除')
        return True

    def cmd_RNFR(self, arg):
        if not self.server.allow_write:
            self._send(550, '只读模式')
            return True
        p = self._resolve(arg)
        if not p or not os.path.exists(p):
            self._send(550, '文件不存在')
            return True
        self.rename_from = p
        self._send(350, '准备重命名')
        return True

    def cmd_RNTO(self, arg):
        if not self.server.allow_write or not self.rename_from:
            self._send(550, '只读模式或未指定源文件')
            return True
        p = self._resolve(arg)
        if not p:
            self._send(550, '非法路径')
            return True
        os.rename(self.rename_from, p)
        self.rename_from = None
        self._send(250, '重命名完成')
        return True

    # ── 元信息 ────────────────────────────────────────────────────
    def cmd_SIZE(self, arg):
        p = self._resolve(arg)
        if not p or not os.path.isfile(p):
            self._send(550, '文件不存在')
            return True
        self._send(213, str(os.path.getsize(p)))
        return True

    def cmd_MDTM(self, arg):
        p = self._resolve(arg)
        if not p or not os.path.exists(p):
            self._send(550, '文件不存在')
            return True
        t = time.localtime(os.path.getmtime(p))
        self._send(213, time.strftime('%Y%m%d%H%M%S', t))
        return True

    def cmd_STAT(self, arg):
        self.request.sendall(b'211-Status:' + CRLF)
        self.request.sendall(
            (' 已连接 ' + self.client_address[0]).encode('utf-8', 'replace') + CRLF)
        self.request.sendall(b'211 End' + CRLF)
        return True

    def cmd_HELP(self, arg):
        self._send(214, '支持的命令：USER PASS SYST FEAT TYPE PWD CWD CDUP '
                       'PASV EPSV LIST NLST RETR STOR SIZE MDTM NOOP QUIT')
        return True


class FTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, root, allow_write=False, lan_only=False,
                 banner=None, verbose=True):
        self.root = os.path.abspath(root)
        self.allow_write = allow_write
        self.lan_only = lan_only
        self.verbose = verbose
        self.banner = banner or (
            'Confucius4 LiveCaption 文件服务（局域网）— 匿名登录，密码任意')
        socketserver.ThreadingTCPServer.__init__(self, addr, FTPHandler)

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        socketserver.ThreadingTCPServer.server_bind(self)

    def log(self, msg):
        if self.verbose:
            print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def local_ips():
    """列出本机可用于局域网访问的 IPv4。"""
    ips = set()
    try:
        for fam, _, _, _, addr in socket.getaddrinfo(socket.gethostname(), None):
            if fam == socket.AF_INET:
                ip = addr[0]
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.1f} {unit}'
        n /= 1024.0


def dir_summary(root, limit=40):
    """列出 root 下的一级内容（按大小排序），方便看有什么可下。"""
    rows = []
    try:
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rows.append((name, st.st_size, os.path.isdir(full)))
    except OSError:
        return []
    rows.sort(key=lambda r: (not r[2], -r[1]))
    return rows[:limit]


def main():
    ap = argparse.ArgumentParser(
        description='局域网 FTP 文件服务（零依赖，仅标准库）')
    ap.add_argument('--root', default='.', help='要共享的目录（默认当前目录）')
    ap.add_argument('--port', type=int, default=2121, help='监听端口（默认 2121）')
    ap.add_argument('--host', default='0.0.0.0', help='监听地址（默认 0.0.0.0，即所有网卡）')
    ap.add_argument('--write', action='store_true', help='允许写入（默认只读）')
    ap.add_argument('--lan-only', action='store_true',
                    help='只允许非回环地址连接（默认也允许本机调试）')
    ap.add_argument('--quiet', action='store_true', help='不打印会话日志')
    ap.add_argument('--summary', action='store_true',
                    help='打印共享目录内容摘要后退出（不启动服务）')
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f'错误：目录不存在：{root}', file=sys.stderr)
        return 1

    if args.summary:
        print(f'共享目录：{root}')
        for name, size, isdir in dir_summary(root):
            print(f'  {"[目录]" if isdir else "[文件]"} {name}  {human(size)}')
        return 0

    srv = FTPServer((args.host, args.port), root,
                    allow_write=args.write, lan_only=args.lan_only,
                    verbose=not args.quiet)

    print('=' * 68)
    print('  局域网 FTP 文件服务已启动')
    print('=' * 68)
    print(f'  共享目录：{root}')
    print(f'  权限    ：{"可读写" if args.write else "只读"}')
    print(f'  登录    ：匿名（用户名随意，密码随意）')
    print()
    print('  客户端填这个地址：')
    for ip in local_ips():
        print(f'      ftp://{ip}:{args.port}/')
    print(f'      ftp://127.0.0.1:{args.port}/   （本机自测）')
    print()
    print('  Windows 资源管理器：地址栏输入 ftp://<上面的IP>:<端口>')
    print('  浏览器            ：输入 ftp://<上面的IP>:<端口>/')
    print('  FileZilla         ：主机 <IP>，端口 <端口>，快速连接（匿名）')
    print()
    print('  按 Ctrl+C 停止服务')
    print('=' * 68, flush=True)

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n正在停止…')
    finally:
        srv.shutdown()
        srv.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
