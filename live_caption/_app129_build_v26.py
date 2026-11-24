#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129：构建完整版 **v2.6** 客户包（EXT v0.4.19 + Demucs 模型 + APP-123 c13）。

## 本包的组成（reviewer APP-129 §2）

| 内容 | 来源 | 落点 |
|---|---|---|
| EXT 桥接 | `live_dub_ext@3573b2d`（v0.4.19）`ext/*.py` | `<包根>/ext/bridge/*.py` |
| EXT 插件 | `live_dub_ext@3573b2d` `extension/*` | `<包根>/ext/extension/*` |
| 分离模型 | `live_dub_ext/models/bgsep/htdemucs_core.{xml,bin}` | `<包根>/models/bgsep/` |
| APP-123 c13 | 开发树 `live_caption/tts_engine.py` + `tts_worker.py` | `<包根>/app/` |
| APP-130 cp 自检 | 同上（同一份代码） | `<包根>/app/` |

## 纪律（沿用 `_app116_build_v25.py` 的成包口径）

- **不覆盖/不删除任何旧版本目录与 zip**（v2.5 原封不动）；
- 复制先落到 **`.staging`** 再改名（⇒ 中断不会留下半个 v2.6）；
- **持共享机器锁**（复制与压缩都是重 IO ⇒ 会干扰别的模块计时）；
- 锁的存活判据用 ctypes `OpenProcess` + `GetExitCodeProcess`
  （**259 = STILL_ACTIVE = 活**；**探测失败 ⇒ 视为存活** ⇒ fail-closed）；
- 定点同步：**逐文件 + 唯一命中 + SHA256 + `ast.parse` 复核**；
- 写盘一律 **临时文件 → `os.replace`**（不截断原文件）；
- 包内**不得有** `bridge_token.txt` / `*.log` / `*.pid` / e2e 产物 / clips。

## 用法

    python live_caption/_app129_build_v26.py --stage copy
    python live_caption/_app129_build_v26.py --stage sync
    python live_caption/_app129_build_v26.py --stage pack
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
sys.path.insert(0, HERE)

# 🔴 复用 v2.5 成包脚本里的**锁 / robocopy / 统计**helper（口径一致）
import _app116_build_v25 as B  # noqa: E402

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
STAGING = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6.staging')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6.zip')
SRC_EXT = os.path.join(HOME, 'live_dub_ext')
RESULTS = os.path.join(REPO, 'results', 'app')
LOG = os.path.join(RESULTS, 'app129_build_v26.log')
EVID = os.path.join(RESULTS, 'app129_build_v26_evidence.json')

#: 🔴🔴 APP-131（reviewer 2026-11-24 10:47 邮件）**改写 APP-129 §2**：
#:   「EXT：live_dub_ext **3573b2d**」⇒ 改为「**4740b06**」（EXT v0.4.20，
#:   克隆音色跟随男女切换）。
#:   ⇒ 本包（v2.6）**只出这一版**（v0.4.19 的中间产物不再交付）。
#:
#: 🔴🔴 **APP-133**（reviewer 2026-11-24 13:56 邮件）：EXT **再升到**
#:   **b2a4978（v0.4.21）**——按音高把男女混在一起的段切开（音乐下 8 s 硬切
#:   会跨换人）；`stats_full` 新增 `clone_reasons` / `spk_reason_hist` /
#:   `n_gender_splits`；可选 `EXT_BG_DUMP_VOCALS` 落盘分离人声。
#:   ⇒ **b2a4978 替代 4740b06**（v0.4.20 是中间产物，不再交付）。
EXT_VERSION = '0.4.21'
EXT_COMMIT = 'b2a4978'

#: dev 树 → 包内 `app/` 的**整文件**同步清单（v2.6 是新版本 ⇒ 直接落当前 dev 版本）
APP_FILES = [
    'tts_engine.py',      # APP-123 c13 + APP-130 cp 自检
    'tts_worker.py',      # APP-123 峰值限幅 + APP-130 运行时保险
]

#: 🔴 源 EXT 仓库里**不带**进包的文件（App 侧那份才是交付件）
EXT_SKIP = ('tts_cuda_sidecar_ext.py',)


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


def to_crlf(data: bytes) -> bytes:
    return data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def write_bytes(path, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp_app129'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def copy_tree(src_dir, dst_dir, exts, skip_names=()):
    n = 0
    for fn in sorted(os.listdir(src_dir)):
        if fn in skip_names or fn.startswith('__pycache__'):
            continue
        if not any(fn.endswith(e) for e in exts):
            continue
        s = os.path.join(src_dir, fn)
        if not os.path.isfile(s):
            continue
        write_bytes(os.path.join(dst_dir, fn), to_crlf(open(s, 'rb').read()))
        n += 1
    return n


# ── 🔴 从**指定 commit** 取文件（不是工作树！）─────────────────────────
# 2026-11-24 10:2x 实测：`live_dub_ext` 工作树已被 reviewer 改成 **v0.4.20**
#   （`M ext/bridge.py` / `M ext/version.py` / `M extension/manifest.json` …）
#   ⇒ 而 APP-129 明文要求「EXT：live_dub_ext **3573b2d**（v0.4.19）」
#   ⇒ **必须按 commit 取内容**，否则会把 reviewer 的在制品打进客户包。
# 2026-11-24 12:3x 更新（APP-131）：要求改为 **4740b06（v0.4.20）**；
#   工作树此后又出现 **v0.4.21 在制品**（`split_by_gender` 等，未提交）
#   ⇒ **仍然只按 commit 取**（4740b06），**绝不取工作树**。
def git_show(commit: str, relpath: str):
    p = subprocess.run(['git', '-C', SRC_EXT, 'show', '%s:%s' % (commit, relpath)],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout


def git_files(commit: str, relpath: str):
    p = subprocess.run(['git', '-C', SRC_EXT, 'ls-tree', '-r', '--name-only',
                        commit, relpath], capture_output=True, text=True)
    if p.returncode != 0:
        return []
    return [l.strip() for l in p.stdout.splitlines() if l.strip()]


def sync_ext_from_commit(commit: str):
    """按 commit 取 EXT 源码 ⇒ 落到包内。返回 (n_bridge, n_ui, errors)。"""
    errors = []
    # ── 桥接：`ext/*.py` → `ext/bridge/*.py` ─────────────────────────
    n_bridge = 0
    for rel in git_files(commit, 'ext/'):
        if not rel.startswith('ext/') or not rel.endswith('.py'):
            continue
        base = os.path.basename(rel)
        if base in EXT_SKIP:
            continue
        data = git_show(commit, rel)
        if data is None:
            errors.append('git show 失败：%s' % rel)
            continue
        write_bytes(os.path.join(DST, 'ext', 'bridge', base), to_crlf(data))
        n_bridge += 1
    # ── 插件：`extension/*` → `ext/extension/*` ─────────────────────
    n_ui = 0
    for rel in git_files(commit, 'extension/'):
        if not rel.startswith('extension/'):
            continue
        data = git_show(commit, rel)
        if data is None:
            errors.append('git show 失败：%s' % rel)
            continue
        sub = rel[len('extension/'):]
        write_bytes(os.path.join(DST, 'ext', 'extension', sub.replace('/', os.sep)),
                    data if sub.endswith('.png') else to_crlf(data))
        n_ui += 1
    # ── 桥接启动器 ──────────────────────────────────────────────────
    data = git_show(commit, 'tools/ext_launcher.py')
    if data is None:
        errors.append('git show 失败：tools/ext_launcher.py')
    else:
        write_bytes(os.path.join(DST, 'tools', 'ext_launcher.py'), to_crlf(data))
    return n_bridge, n_ui, errors


# ══════════════════════════════════════════════════════════════════════
# stage copy
# ══════════════════════════════════════════════════════════════════════
def stage_copy():
    if os.path.exists(DST):
        log('🔴 目标目录已存在：%s ⇒ **不覆盖**（旧版本目录不许覆盖）' % DST)
        return False
    if os.path.exists(STAGING):
        # 🔴 本机实测（11-24 10:2x）：**顶层目录改名被系统拒绝**
        #   （PermissionError 13；同名的**嵌套**目录改名/删除都正常 ⇒
        #     是 staging 目录自身的 OS 句柄未释放，不是权限/属性问题）
        #   ⇒ 改法：改名失败就**直接 robocopy 到正式目录**，staging 保留在盘上。
        try:
            os.rename(STAGING, DST)
            log('staging 改名成功：%s ⇒ %s'
                % (os.path.basename(STAGING), os.path.basename(DST)))
            return True
        except Exception as e:
            log('staging 改名失败（%r）⇒ 改为**直接 robocopy**到正式目录；'
                'staging 暂留盘上（待句柄释放后再清理）' % (e,))
    # 🔴 复制是**重 IO** ⇒ 会干扰别的模块的计时 ⇒ **持共享机器锁**
    lock = B.acquire_lock('app build v2.6 copy')
    t0 = time.time()
    try:
        if not B.robocopy(SRC, DST):
            return False
        n, total = B.count_tree(DST)
        log('复制完成：%d 文件 / %d B / %.1f s'
            % (n, total, time.time() - t0))
    finally:
        B.release_lock(lock)
    return True


def stage_cleanup():
    """清理 staging 残留（**尽力而为**；本机删除 shim 可能拦 ⇒ 失败只记录）。"""
    if not os.path.exists(STAGING):
        log('staging 不存在 ⇒ 无需清理')
        return True
    log('清理 staging：%s' % STAGING)
    shutil.rmtree(STAGING, ignore_errors=True)
    ok = not os.path.exists(STAGING)
    log('清理结果：%s' % ('OK' if ok else '**仍有残留**（shim 拦截 / 句柄未释放）'))
    return ok


# ══════════════════════════════════════════════════════════════════════
# stage sync
# ══════════════════════════════════════════════════════════════════════
def stage_sync():
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg': DST, 'ext_version': EXT_VERSION, 'ext_commit': EXT_COMMIT,
           'files': [], 'errors': []}

    if not os.path.isdir(DST):
        log('FAIL: 包目录不存在 %s' % DST)
        return False

    # ── ① App dev 文件（整文件 ⇒ v2.6 就是当前 dev 版本）──────────
    for name in APP_FILES:
        src = os.path.join(HERE, name)
        dst = os.path.join(DST, 'app', name)
        if not os.path.isfile(src):
            rep['errors'].append('源缺失 %s' % name)
            continue
        data = open(src, 'rb').read()
        write_bytes(dst, data)
        after = open(dst, 'rb').read()
        rec = {'rel': 'app/' + name, 'bytes': len(data),
               'sha256': sha256(dst), 'identical': after == data,
               'src_sha256': sha256(src)}
        try:
            import ast
            ast.parse(after.decode('utf-8'))
            rec['ast'] = 'OK'
        except Exception as e:
            rec['ast'] = 'FAIL: %r' % (e,)
            rep['errors'].append('app/%s ast.parse 失败: %r' % (name, e))
        if not rec['identical']:
            rep['errors'].append('app/%s 写后逐字节复核失败' % name)
        rep['files'].append(rec)
        log('① app/%s：%d B  sha=%s  identical=%s'
            % (name, len(data), rec['sha256'][:12], rec['identical']))

    # ── ②③ EXT：🔴 按 **commit 3573b2d** 取内容（不是工作树！）────
    dst_bridge = os.path.join(DST, 'ext', 'bridge')
    dst_ui = os.path.join(DST, 'ext', 'extension')
    n_bridge, n_ui, ext_errs = sync_ext_from_commit(EXT_COMMIT)
    rep['errors'].extend(ext_errs)
    log('② ext/bridge/*.py：按 commit %s 复制 %d 个'
        % (EXT_COMMIT, n_bridge))
    log('③ ext/extension/*：按 commit %s 复制 %d 个文件'
        % (EXT_COMMIT, n_ui))

    main_py = os.path.join(dst_bridge, '__main__.py')
    _main_src = '''# -*- coding: utf-8 -*-
"""__main__ — 让 ``python -m ext.bridge`` 可执行（APP-104 §3）。

🔴 客户包里 EXT 的桥接模块在 ``ext/bridge/``（**是包**，不是模块）⇒
EXT 启动器里的 ``python -m ext.bridge`` 会报
「is a package and cannot be directly executed」。

⇒ 本文件是 **App 打包侧新增**的入口（不改 EXT 源文件）：
``python -m ext.bridge`` ⇒ 等价于 ``python -m ext.bridge.bridge``。
"""
from ext.bridge.bridge import main

if __name__ == '__main__':
    raise SystemExit(main())
'''
    write_bytes(main_py, to_crlf(_main_src.encode('utf-8')))
    log('② ext/bridge/__main__.py：写入')

    # ── ④ manifest.json：version=%s、release=true ─────────────────
    mf = os.path.join(dst_ui, 'manifest.json')
    data = json.load(open(mf, encoding='utf-8'))
    data['version'] = EXT_VERSION
    if isinstance(data.get('liveDub'), dict):
        data['liveDub']['release'] = True
    write_bytes(mf, to_crlf(json.dumps(data, ensure_ascii=False,
                                       indent=2).encode('utf-8') + b'\n'))
    log('④ ext/extension/manifest.json：version=%s release=true' % EXT_VERSION)

    # ── ⑤ Start_Bridge.bat（`tools/ext_launcher.py` 已在 ②③ 按 commit 取）──
    bat = (b'@echo off\n'
           b'REM Start_Bridge.bat - launch the EXT real-time dubbing bridge '
           b'(EXT v' + EXT_VERSION.encode('ascii') + b')\n'
           b'REM (APP-104 s3: relative paths only, no developer-machine paths)\n'
           b'REM (APP-105 s1: CRLF line endings + ASCII only, so it also runs '
           b'on codepage 936)\n'
           b'setlocal\n'
           b'cd /d "%~dp0"\n'
           b'if not exist "python\\pythonw.exe" (\n'
           b'  echo [EXT] package interpreter not found: python\\pythonw.exe\n'
           b'  pause\n'
           b'  exit /b 2\n'
           b')\n'
           b'start "Confucius4 EXT Bridge" "%~dp0python\\pythonw.exe" '
           b'"%~dp0tools\\ext_launcher.py"\n'
           b'endlocal\n')
    bat_crlf = to_crlf(bat)
    try:
        bat_crlf.decode('ascii')
        ascii_ok = True
    except UnicodeDecodeError:
        ascii_ok = False
    write_bytes(os.path.join(DST, 'Start_Bridge.bat'), bat_crlf)
    log('⑤ Start_Bridge.bat：写入（ASCII=%s）' % ascii_ok)
    if not ascii_ok:
        rep['errors'].append('Start_Bridge.bat 不是纯 ASCII')

    # ── ⑥ Demucs 分离模型 → `<包根>/models/bgsep/` ─────────────────
    #    reviewer 明文：xml 1341298 B、bin 106628066 B（对源
    #    `shared\bgkeep\htdemucs_core.*` 记 SHA256）
    model_src = os.path.join(SRC_EXT, 'models', 'bgsep')
    model_dst = os.path.join(DST, 'models', 'bgsep')
    os.makedirs(model_dst, exist_ok=True)
    model_rec = []
    for fn in ('htdemucs_core.xml', 'htdemucs_core.bin'):
        s = os.path.join(model_src, fn)
        d = os.path.join(model_dst, fn)
        shutil.copy2(s, d)
        rec = {'file': 'models/bgsep/' + fn,
               'bytes': os.path.getsize(d), 'sha256': sha256(d),
               'src_sha256': sha256(s)}
        model_rec.append(rec)
        log('⑥ models/bgsep/%s：%d B  sha=%s' % (fn, rec['bytes'],
                                                 rec['sha256'][:12]))
    rep['models'] = model_rec

    # ── ⑦ 污染扫描：包内不得有 bridge_token.txt / *.log / *.pid /
    #       e2e 产物 / clips ────────────────────────────────────────
    banned = []
    for dp, dns, fns in os.walk(DST):
        dns[:] = [d for d in dns
                  if d not in ('python', '__pycache__', 'node_modules')]
        for fn in fns:
            low = fn.lower()
            if low == 'bridge_token.txt' or low.endswith('.pid'):
                banned.append(os.path.relpath(os.path.join(dp, fn), DST))
            elif low.endswith('.log') and 'results' not in dp.lower():
                banned.append(os.path.relpath(os.path.join(dp, fn), DST))
            elif low.startswith('player_mix') or low.endswith('.wav') \
                    and 'clips' in dp.lower():
                banned.append(os.path.relpath(os.path.join(dp, fn), DST))
    rep['banned_found'] = banned
    log('⑦ 污染扫描：%d 项' % len(banned))
    if banned:
        rep['errors'].append('包内有污染文件：%s' % banned[:10])

    # ── ⑧ 复核 ─────────────────────────────────────────────────────
    checks = [
        (os.path.join(dst_bridge, 'bridge.py'), 'ext/bridge/bridge.py'),
        (os.path.join(dst_bridge, 'version.py'), 'ext/bridge/version.py'),
        (os.path.join(dst_bridge, '__main__.py'), 'ext/bridge/__main__.py'),
        (os.path.join(dst_ui, 'manifest.json'), 'ext/extension/manifest.json'),
        (os.path.join(DST, 'tools', 'ext_launcher.py'), 'tools/ext_launcher.py'),
        (os.path.join(DST, 'Start_Bridge.bat'), 'Start_Bridge.bat'),
    ]
    for p, rel in checks:
        ok = os.path.isfile(p)
        rec = {'rel': rel, 'exists': ok, 'bytes': os.path.getsize(p) if ok else 0,
               'sha256': sha256(p) if ok else None}
        if ok and p.endswith('.py'):
            try:
                import ast
                ast.parse(open(p, encoding='utf-8').read())
                rec['ast'] = 'OK'
            except Exception as e:
                rec['ast'] = 'FAIL: %r' % (e,)
                rep['errors'].append('%s ast.parse 失败: %r' % (rel, e))
        if ok and p.endswith('.json'):
            try:
                json.load(open(p, encoding='utf-8'))
                rec['json'] = 'OK'
            except Exception as e:
                rec['json'] = 'FAIL: %r' % (e,)
                rep['errors'].append('%s JSON 解析失败: %r' % (rel, e))
        rep['files'].append(rec)
        log('  复核 %-34s %s %s' % (rel, 'OK' if ok else '缺',
                                    (rec.get('sha256') or '')[:12]))

    try:
        vpy = open(os.path.join(dst_bridge, 'version.py'), encoding='utf-8').read()
        rep['ext_version_consistent'] = ('EXT_VERSION = "%s"' % EXT_VERSION) in vpy
    except Exception:
        rep['ext_version_consistent'] = False

    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % EVID)
    return not rep['errors']


# ══════════════════════════════════════════════════════════════════════
# stage pack
# ══════════════════════════════════════════════════════════════════════
def stage_pack():
    py = sys.executable
    packer = os.path.join(REPO, 'pack_v13.py')
    common = [py, packer, '--version', '2.6', '--pkg', DST, '--zip', ZIP,
              '--prefix', 'Confucius4_LiveCaption_v2.6',
              '--no-rename-pkg-dir', '--no-shortcut']
    log('① dry-run（只读检查，不写 zip）')
    p = subprocess.run(common + ['--dry-run'], capture_output=True, text=True,
                       timeout=3600, cwd=REPO)
    log(p.stdout[-8000:])
    if p.stderr.strip():
        log('dry-run stderr: %s' % p.stderr[-2000:])
    log('② 正式打包')
    t0 = time.time()
    p = subprocess.run(common, capture_output=True, text=True, timeout=10800,
                       cwd=REPO)
    log(p.stdout[-12000:])
    if p.stderr.strip():
        log('pack stderr: %s' % p.stderr[-3000:])
    log('打包用时 %.1f s，rc=%d' % (time.time() - t0, p.returncode))
    return p.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', default='all',
                    choices=['copy', 'sync', 'pack', 'cleanup', 'all'])
    args = ap.parse_args()
    log('=== APP-129 构建 v2.6 · stage=%s ===' % args.stage)
    if args.stage in ('copy', 'all'):
        if not stage_copy():
            return 2
    if args.stage in ('sync', 'all'):
        if not stage_sync():
            return 3
    if args.stage == 'cleanup':
        return 0 if stage_cleanup() else 5
    if args.stage in ('pack', 'all'):
        if not stage_pack():
            return 4
    log('=== 结束 ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
