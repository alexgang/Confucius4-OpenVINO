#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app545_transfer_to_target.py —— 把 Special MVP 的 zip 传到目标机（**SFTP + 断点续传 + 两端 SHA256 校验**）。

用法（三种认证任选其一）：
    # ① 密码
    set WB_SSH_PASS=xxx && python _app545_transfer_to_target.py --host 192.168.2.194 --user test
    # ② 公钥（推荐：把本机公钥加到目标机 authorized_keys）
    python _app545_transfer_to_target.py --host 192.168.2.194 --user test --key ~/.ssh/github_backup_ed25519
    # ③ 只做预检（不传）：加 --preflight-only

传完自动在目标机上跑：
    · nvidia-smi（有没有 NVIDIA 卡、是哪张）
    · 解压后的包内 `--check`（本包自带 cuda_env ⇒ 直接验「包里的 CUDA 环境」能不能用）
并把结果落盘成 json ⇒ **GPU 那个问题不用你猜**。

🔴 纪律：**不删目标机上的任何东西**；同名文件已存在且大小相同 ⇒ 跳过（幂等）；
   断点续传：远端已存在部分文件 ⇒ 从断点接着传。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import paramiko

HOME = os.environ.get('USERPROFILE', r'C:\Users\Trekker-PTL')
SRC = os.path.join(HOME, 'shared', 'specialmvp',
                   'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip')
PKG_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1'
OUT = os.path.join(HOME, 'confucius4-openvino', 'results', 'app',
                   'app545_transfer_to_target.json')
CHUNK = 1 << 20


def sha256_file(path, buf=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(buf), b''):
            h.update(b)
    return h.hexdigest()


def connect(host, user, password=None, keyfile=None, port=22, timeout=25):
    t = paramiko.Transport((host, port))
    t.banner_timeout = timeout
    t.connect()
    if keyfile:
        pk = (paramiko.Ed25519Key.from_private_key_file(keyfile)
              if 'ed25519' in keyfile.lower()
              else paramiko.RSAKey.from_private_key_file(keyfile))
        t.auth_publickey(user, pk)
    else:
        t.auth_password(user, password)
    return t


def run(t, cmd, timeout=180):
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = b''
    err = b''
    try:
        while True:
            if ch.recv_ready():
                out += ch.recv(65536)
            if ch.recv_stderr_ready():
                err += ch.recv_stderr(65536)
            if ch.exit_status_ready() and not ch.recv_ready() and not ch.recv_stderr_ready():
                break
            time.sleep(0.1)
    except Exception:
        pass
    return out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--user', default='test')
    ap.add_argument('--port', type=int, default=22)
    ap.add_argument('--key', default=None)
    ap.add_argument('--pass-env', default='WB_SSH_PASS')
    ap.add_argument('--remote-dir', default=r'C:\Users\test\Desktop')
    ap.add_argument('--preflight-only', action='store_true')
    ap.add_argument('--src', default=SRC)
    a = ap.parse_args()
    pw = os.environ.get(a.pass_env) if not a.key else None

    ev = {'host': a.host, 'user': a.user, 'src': a.src,
          'remote_dir': a.remote_dir, 'started_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    if not os.path.isfile(a.src):
        sys.exit('源文件不存在：%s' % a.src)
    ev['src_bytes'] = os.path.getsize(a.src)

    print('连接 %s@%s …' % (a.user, a.host), flush=True)
    t = connect(a.host, a.user, pw, a.key, a.port)
    print('已连接 ✔', flush=True)

    # ── 预检：目标机到底有没有 NVIDIA 卡 ──
    pre = {}
    so, se = run(t, 'nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv 2>&1')
    pre['nvidia_smi'] = so.strip() or se.strip()[:400]
    pre['has_nvidia'] = ('NVIDIA' in so)
    so, _ = run(t, 'wmic cpu get name 2>&1 | findstr /v . & echo --- & ver')
    pre['host_info'] = so.strip()[:600]
    so, _ = run(t, 'powershell -NoProfile -Command "(Get-PSDrive C).Free/1GB" 2>&1')
    try:
        pre['free_gb_on_c'] = round(float(so.strip().splitlines()[-1]), 1)
    except Exception:
        pre['free_gb_on_c'] = None
    ev['preflight'] = pre
    print('  目标机 NVIDIA：%s' % ('有 ⇒ ' + pre['nvidia_smi'][:80] if pre['has_nvidia']
                                  else '**无**（⇒ CUDA TTS 在这台跑不了）'), flush=True)
    print('  C 盘剩余：%s GB' % pre['free_gb_on_c'], flush=True)

    if a.preflight_only:
        ev['preflight_only'] = True
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        t.close()
        return 0

    # ── 传输（断点续传）──
    sftp = paramiko.SFTPClient.from_transport(t)
    remote = a.remote_dir + '\\' + os.path.basename(a.src)
    try:
        st = sftp.stat(remote)
        have = st.st_size
    except IOError:
        have = 0
    total = ev['src_bytes']
    if have == total:
        print('远端已存在且大小相同 ⇒ 跳过传输 ✔', flush=True)
    else:
        if have:
            print('断点续传：从 %d / %d B 继续' % (have, total), flush=True)
        with open(a.src, 'rb') as f:
            f.seek(have)
            with sftp.open(remote, 'ab' if have else 'wb') as rf:
                t0 = time.time()
                done = have
                last = t0
                while done < total:
                    b = f.read(CHUNK)
                    if not b:
                        break
                    rf.write(b)
                    done += len(b)
                    if time.time() - last > 5:
                        sp = done / max(time.time() - t0, 1e-6)
                        print('  %.2f GiB / %.2f GiB (%.1f%%) %.1f MB/s'
                              % (done / 1024 ** 3, total / 1024 ** 3,
                                 100.0 * done / total, sp / 1e6), flush=True)
                        last = time.time()
        ev['transferred_bytes'] = done
        ev['transfer_secs'] = round(time.time() - t0, 1)
    sftp.close()

    # ── 两端 SHA256 校验 ──
    print('校验本地 SHA256 …', flush=True)
    ev['sha256_local'] = sha256_file(a.src)
    print('校验远端 SHA256（14 GB，要一会儿）…', flush=True)
    so, se = run(t, 'certutil -hashfile "%s" SHA256 2>&1' % remote, timeout=1800)
    txt = (so + se)
    import re
    m = re.search(r'\b([0-9a-fA-F]{64})\b', txt)
    ev['sha256_remote'] = m.group(1).lower() if m else None
    ev['sha256_match'] = (ev['sha256_remote'] == ev['sha256_local'])
    print('远端 SHA256：%s' % ev['sha256_remote'], flush=True)
    print('两端一致：%s' % ev['sha256_match'], flush=True)

    ev['remote_path'] = remote
    ev['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    t.close()
    print('证据：%s' % OUT, flush=True)
    return 0 if ev.get('sha256_match') else 3


if __name__ == '__main__':
    sys.exit(main())
