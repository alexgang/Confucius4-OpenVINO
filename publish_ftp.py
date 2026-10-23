r"""publish_ftp.py —— 把**重打好的客户包 zip** 复制到 FTP 共享目录（长时重活，持共享机器锁）。

## 为什么需要这个脚本

🔴 **FTP_Share 里的 zip 是独立副本**（`stat` 的 inode 不同、link count = 1，
**不是硬链接**）⇒ 源 zip 重打后，**FTP 里的那份不会自动更新**
⇒ 「改包目录 ≠ 交付客户」，「重打 zip ≠ 已发布」。
历史上多次出现「zip 是旧的、但所有断言都 PASS」的事故
（2026-10-24 21:00~21:17，见 §17/§18）。

⇒ 所以「复制到 FTP」这一步**必须**：
1. **持共享机器锁**（复制 11.2 GB 是长时重活，会干扰其它模块的计时测量）；
2. **复制后校验**（字节数 + SHA256 双向比对）⇒ 不能只看「复制成功」。

## 用法

    python publish_ftp.py                     # 复制最新的 vX.Y zip 到 FTP_Share
    python publish_ftp.py --zip <路径>        # 指定源 zip
    python publish_ftp.py --check             # 只校验 FTP 里的副本是否与源一致
    python publish_ftp.py --no-lock           # 不取共享机器锁（不建议）

## 纪律

- **不删** FTP 里的旧版本 zip（FTP 是对客户发布的目录，历史版本要留着）。
- 复制用**流式分块**读写（11.2 GB 绝不能整体读进内存 —— `verify_ftp.py`
  曾因 `io.BytesIO` + `read()` 两次读进内存 ≈ 22 GB 被 SIGTERM，那是真根因）。
- 复制到**临时名**再原子改名 ⇒ FTP 服务端不会看到半截文件。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import machine_lock_app
except Exception:                        # pragma: no cover
    machine_lock_app = None

FTP_ROOT = r'C:\Users\Trekker-PTL\FTP_Share'
HOME = r'C:\Users\Trekker-PTL'
BLK = 8 * 1024 * 1024


def sha256(path: str) -> str:
    """流式算 SHA256（不把文件读进内存）。"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(BLK), b''):
            h.update(chunk)
    return h.hexdigest()


def discover_src_zip(home: str = HOME) -> str:
    """自动发现**版本号最大**的 `Confucius4_LiveCaption_vX.Y.zip`（源）。

    🔴 排除 `.bak` / `backup` / `_pre_` 目录（长期记忆铁律：
       验证/发布脚本**不得写死版本号**）。
    """
    best, best_key = None, None
    for name in os.listdir(home):
        if not name.startswith('Confucius4_LiveCaption_v') or \
                not name.lower().endswith('.zip'):
            continue
        low = name.lower()
        if '.bak' in low or 'backup' in low or '_pre_' in low:
            continue
        ver = name.rsplit('_v', 1)[-1][:-4]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        if best_key is None or key > best_key:
            best_key, best = key, os.path.join(home, name)
    if best is None:
        raise SystemExit('[发布] 未找到 Confucius4_LiveCaption_vX.Y.zip')
    return best


def _copy_verify(src: str, dst: str) -> dict:
    """复制 + 校验（字节数 + SHA256）。"""
    size_src = os.path.getsize(src)
    size_dst_before = os.path.getsize(dst) if os.path.exists(dst) else 0
    same = (size_src == size_dst_before)
    sha_same = False
    if same:
        # 体积一样 ⇒ 先比 mtime/SHA；SHA 一致就不用复制
        sha_same = (sha256(src) == sha256(dst))
        if sha_same:
            return dict(copied=False, bytes=size_src,
                        sha_src=sha256(src), sha_dst=sha256(dst))
    print(f'  复制 {size_src:,} 字节 …')
    tmp = dst + '.tmp'
    t0 = time.time()
    with open(src, 'rb') as fs, open(tmp, 'wb') as fd:
        n = 0
        while True:
            b = fs.read(BLK)
            if not b:
                break
            fd.write(b)
            n += len(b)
            if n % (BLK * 8) == 0:
                print('    %.1f%%  (%.1f MB/s)'
                      % (n * 100.0 / size_src,
                         n / 1048576.0 / max(time.time() - t0, 1e-9)), flush=True)
    os.replace(tmp, dst)          # 原子改名 ⇒ FTP 端不会看到半截文件
    el = time.time() - t0
    print('  复制完成：%d 字节，用时 %.1f s（%.1f MB/s）'
          % (n, el, n / 1048576.0 / max(el, 1e-9)))
    sha_src = sha256(src)
    sha_dst = sha256(dst)
    return dict(copied=True, bytes=n, sha_src=sha_src, sha_dst=sha_dst)


_ap = argparse.ArgumentParser(description='发布客户包 zip 到 FTP 共享目录')
_ap.add_argument('--zip', default=None, help='源 zip（默认自动发现最新版本）')
_ap.add_argument('--ftp-root', default=FTP_ROOT, help='FTP 共享目录')
_ap.add_argument('--check', action='store_true',
                help='只校验 FTP 副本是否与源一致（不复制）')
_ap.add_argument('--no-lock', action='store_true',
                help='不取共享机器锁（复制 11.2 GB 是长时重活，不建议）')
_args = _ap.parse_args()


def main():
    args = _args

    src = args.zip or discover_src_zip()
    if not os.path.isfile(src):
        raise SystemExit(f'!! 源 zip 不存在: {src}')
    os.makedirs(args.ftp_root, exist_ok=True)
    name = os.path.basename(src)
    dst = os.path.join(args.ftp_root, name)

    print('=' * 68)
    print(' 客户包 zip 发布到 FTP 共享目录')
    print('=' * 68)
    print(f'源   : {src}')
    print(f'目标 : {dst}')
    print(f'体积 : {os.path.getsize(src):,} 字节')
    print()

    if args.check:
        if not os.path.exists(dst):
            raise SystemExit('!! FTP 副本不存在')
        sha_s = sha256(src)
        sha_d = sha256(dst)
        ok = (sha_s == sha_d)
        print(f'源   SHA256 : {sha_s}')
        print(f'副本 SHA256 : {sha_d}')
        print()
        print('结论：' + ('PASS —— FTP 副本与源一致' if ok else 'FAIL —— 不一致，需重新发布'))
        return 0 if ok else 1

    r = _copy_verify(src, dst)
    print()
    print(f'源   SHA256 : {r["sha_src"]}')
    print(f'副本 SHA256 : {r["sha_dst"]}')
    print(f'副本体积   : {os.path.getsize(dst):,} 字节')
    ok = (r['sha_src'] == r['sha_dst'])
    print()
    print('结论：' + ('PASS —— FTP 副本与源一致' if ok else 'FAIL —— SHA256 不一致！'))
    if not ok:
        return 1
    print(f'（{"已复制" if r["copied"] else "原本就一致，未重复复制"}）')
    return 0


if __name__ == '__main__':
    if _args.no_lock or machine_lock_app is None:
        if not _args.no_lock and machine_lock_app is None:
            print('[warn] 无法 import machine_lock_app ⇒ 未持共享机器锁')
        sys.exit(main())
    lk = machine_lock_app.LockHeld(module='app-ftppub', timeout=3600)
    if not lk.acquire():
        print('!! 未能取得共享机器锁 ⇒ 拒绝执行（避免干扰其它模块计时）')
        sys.exit(1)
    try:
        sys.exit(main())
    finally:
        lk.release()
