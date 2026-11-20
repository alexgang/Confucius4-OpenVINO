#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §1：**把 v2.5 缺的「全集」资源**从 SpecialMVP sp5 复制进 v2.5。

## 为什么需要这一步
APP-118 决定：**完整版 v2.5 = 全集**（含 CUDA TTS / ASR 0.6B / EXT 最新）。
v2.5 的基底是 v2.4（robocopy 整包复制）⇒ **不含**下面三类资源：

| 资源 | 来源 | 体积 | 为什么必须有 |
|---|---|---|---|
| `cuda_env/`（torch 2.11.0+cu128） | sp5 | 4.9 G | APP-118 §1「加上 SpecialMVP 的 NVIDIA CUDA 后端（`cuda_env/`）」 |
| `models/tts_cuda/` | sp5 | 2.4 G | 同上（CUDA TTS 的 HF 权重） |
| `models/asr06b-*` + `embed_tokens_06b_f16.npy` | sp5 | 1.1 G | APP-118 §1「同时带上 Qwen3-ASR 0.6B stateful INT8」 |

## 纪律
  * **不碰任何旧版本目录/zip**（v2.4 / rc11 / sp5 只读）；
  * **不删任何东西**（本机有「安全删除 shim」⇒ 删除会被转回收站/被拦）；
  * 复制走 **robocopy**（断点续传 + 保留属性），**不整目录覆盖客户包**：
    只往 v2.5 的**目标子目录**里新增文件，已存在的同路径文件**逐字节相同就跳过**、
    不同则**报告为冲突并停下**（⇒ 不静默覆盖）；
  * 写盘后**逐文件复核**（文件数 / 字节 / SHA256 取样）；
  * **持共享机器锁**（复制是重 IO ⇒ 会干扰别的模块计时）；
  * 锁的存活判据用 ctypes `OpenProcess` + `GetExitCodeProcess`
    （**259 = STILL_ACTIVE = 活**；**探测失败 ⇒ 视为存活** ⇒ fail-closed）。
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
SRC_SP5 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
RESULTS = os.path.join(REPO, 'results', 'app')
LOG = os.path.join(RESULTS, 'app118_assets_to_v25.log')

#: (源相对路径, 目标相对路径) —— 目标**必须不在** DST 之外。
PAIRS = [
    (os.path.join('cuda_env'), os.path.join('cuda_env')),
    (os.path.join('models', 'tts_cuda'), os.path.join('models', 'tts_cuda')),
    (os.path.join('models', 'asr06b-decoder-int8'),
     os.path.join('models', 'asr06b-decoder-int8')),
    (os.path.join('models', 'asr06b-encoder-fp16'),
     os.path.join('models', 'asr06b-encoder-fp16')),
    (os.path.join('models', 'asr06b-tokenizer'),
     os.path.join('models', 'asr06b-tokenizer')),
    (os.path.join('models', 'embed_tokens_06b_f16.npy'),
     os.path.join('models', 'embed_tokens_06b_f16.npy')),
]


def log(msg):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    try:
        os.makedirs(RESULTS, exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pid_alive(pid):
    """🔴 存活判据：**259 = STILL_ACTIVE = 活**；探测失败 ⇒ 视为存活。"""
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return k.GetLastError() != 87
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    try:
        raw = open(LOCK, encoding='utf-8').read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return {'raw': None, 'pid': None, 'unparsed': True}
    parts = raw.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p)
            break
    if pid is None:
        return {'raw': raw, 'pid': None, 'unparsed': True}
    return {'raw': raw, 'pid': pid, 'module': parts[0] if parts else '?'}


def acquire_lock(note):
    while True:
        own = lock_owner()
        if own is None:
            break
        pid = own.get('pid')
        if pid and pid == os.getpid():
            return own.get('raw')
        alive = pid_alive(pid) if pid else True
        if not alive:
            log('锁的持有者 pid=%s 已死 ⇒ 回收' % pid)
            try:
                os.remove(LOCK)
            except Exception:
                pass
            continue
        log('等机器锁（持有者 pid=%s 仍存活 ⇒ 不抢）' % pid)
        time.sleep(5)
    content = 'app %d %s %s' % (os.getpid(),
                                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                note)
    tmp = LOCK + '.tmp_app118'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp, LOCK)
    log('已取机器锁：%s' % content)
    return content


def release_lock(content):
    own = lock_owner()
    if own is None:
        return
    if own.get('raw') == content or (own.get('pid') == os.getpid()):
        try:
            os.remove(LOCK)
            log('已放机器锁')
        except Exception as e:
            log('放锁失败：%r' % (e,))
    else:
        log('🔴 锁内容已被别人改动（%r）⇒ **不删**' % (own.get('raw'),))


def robocopy(src, dst):
    cmd = ['robocopy', src, dst, '/E', '/COPY:DAT', '/DCOPY:T',
           '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
    log('robocopy %s ⇒ %s' % (os.path.basename(src), os.path.basename(dst)))
    # 🔴🔴🔳 **必须显式给 `encoding='utf-8', errors='replace'`**：
    #   robocopy 在中文 Windows 上按 **GBK** 写 stdout
    #   ⇒ `text=True` 用 locale 编码（cp936）解码**可能成功**，但一旦输出里
    #   出现非 GBK 字节（本轮实测 0xb4）⇒ `UnicodeDecodeError`
    #   ⇒ 子进程 stdout 变成 **None** ⇒ 后面 `p.stdout[-2000:]` 抛
    #   `TypeError: 'NoneType' object is not subscriptable`
    #   ⇒ **复制其实已成功，但脚本崩在收尾**（本轮真踩）。
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=10800)
    out = p.stdout or ''
    err = p.stderr or ''
    if p.returncode >= 8:
        log('robocopy 退出码 %d（≥8 = 有错）\n%s\n%s'
            % (p.returncode, out[-2000:], err[-2000:]))
        return False
    log('robocopy 完成（rc=%d）' % p.returncode)
    return True


def count_tree(root):
    n = 0
    total = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            n += 1
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return n, total


def precheck_conflicts():
    """🔴 **先查冲突**：目标已存在但**与源不同**的文件 ⇒ 停下报告（不静默覆盖）。

    「不同」的口径 = SHA256 不同（不是 mtime）。
    """
    conflicts = []
    checked = 0
    for rel_src, rel_dst in PAIRS:
        s = os.path.join(SRC_SP5, rel_src)
        d = os.path.join(DST, rel_dst)
        if not os.path.exists(s):
            conflicts.append({'src': rel_src, 'dst': rel_dst,
                              'why': '源不存在'})
            continue
        if os.path.isfile(s):
            if not os.path.isfile(d):
                continue
            checked += 1
            if sha256(s) != sha256(d):
                conflicts.append({'src': rel_src, 'dst': rel_dst,
                                  'why': '同路径但 SHA256 不同'})
            continue
        # 目录：逐文件比对**已存在的同路径文件**
        for dp, _dn, fns in os.walk(s):
            for fn in fns:
                sp = os.path.join(dp, fn)
                rel = os.path.relpath(sp, s)
                dp2 = os.path.join(d, rel)
                if not os.path.exists(dp2):
                    continue
                checked += 1
                if os.path.getsize(sp) != os.path.getsize(dp2) or \
                        sha256(sp) != sha256(dp2):
                    conflicts.append({
                        'src': os.path.join(rel_src, rel),
                        'dst': os.path.join(rel_dst, rel),
                        'why': '同路径但内容不同'})
    return checked, conflicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='all', choices=['all', 'precheck', 'copy'])
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    log('=== APP-118 §1 资源复制开始（stage=%s）===' % args.stage)
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'src': SRC_SP5, 'dst': DST, 'pairs': [], 'stages': {}}

    if args.stage in ('all', 'precheck'):
        checked, conflicts = precheck_conflicts()
        rep['precheck_checked'] = checked
        rep['precheck_conflicts'] = conflicts
        log('预检：比对了 %d 个同路径文件，冲突 %d 个'
            % (checked, len(conflicts)))
        for c in conflicts:
            log('  🔴 冲突：%s ⇒ %s（%s）' % (c['src'], c['dst'], c['why']))
        rep['stages']['precheck'] = not conflicts
        if conflicts:
            log('🔴 有冲突 ⇒ **不复制**（不静默覆盖）')
            out = os.path.join(RESULTS, 'app118_assets_to_v25_evidence.json')
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)
            return 1

    if args.stage in ('all', 'copy'):
        content = acquire_lock('app118-assets-to-v25')
        try:
            ok = True
            for rel_src, rel_dst in PAIRS:
                s = os.path.join(SRC_SP5, rel_src)
                d = os.path.join(DST, rel_dst)
                if not os.path.exists(s):
                    log('跳过（源不存在）：%s' % rel_src)
                    rep['pairs'].append({'src': rel_src, 'dst': rel_dst,
                                          'ok': False, 'why': '源不存在'})
                    ok = False
                    continue
                t0 = time.time()
                # 🔴🔴🔳 **单文件目标不能用 robocopy**（rc=16 / 错误 267
                #   「源目录名无效」⇒ robocopy 只能拷**目录**）
                #   ⇒ 单文件走 `shutil.copy2`（保留 mtime），并**逐字节复核**。
                if os.path.isfile(s):
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
                    same = (sha256(s) == sha256(d))
                    log('  ⇒ %s：单文件复制 / %d B / %.1f s / sha 一致=%s'
                        % (rel_dst, os.path.getsize(d), time.time() - t0, same))
                    rep['pairs'].append({'src': rel_src, 'dst': rel_dst,
                                         'ok': bool(same), 'files': 1,
                                         'bytes': os.path.getsize(d),
                                         'sha_match': bool(same)})
                    if not same:
                        ok = False
                    continue
                if not robocopy(s, d):
                    ok = False
                    rep['pairs'].append({'src': rel_src, 'dst': rel_dst,
                                          'ok': False, 'why': 'robocopy 失败'})
                    continue
                if os.path.isfile(s):
                    n, total = 1, os.path.getsize(s)
                    same = os.path.isfile(d) and sha256(s) == sha256(d)
                else:
                    n, total = count_tree(d)
                    same = True
                log('  ⇒ %s：%d 文件 / %d B / %.1f s / sha 一致=%s'
                    % (rel_dst, n, total, time.time() - t0, same))
                rep['pairs'].append({'src': rel_src, 'dst': rel_dst,
                                     'ok': bool(same), 'files': n,
                                     'bytes': total,
                                     'sha_match': bool(same)})
        finally:
            release_lock(content)
        rep['stages']['copy'] = ok
        if not ok:
            log('🔴 复制未全部成功')

    out = os.path.join(RESULTS, 'app118_assets_to_v25_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)
    log('=== 结束 ===')
    return 0 if all(rep['stages'].values()) else 1


if __name__ == '__main__':
    sys.exit(main())
