#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app591_build_specialmvp_sp5.py —— 构建 **Special MVP sp5**（APP-114 的改码版）。

🔴 **reviewer 原文（APP-114 §3）**：
  「sp4 还没打 zip，也没被 reviewer 接受，所以**并入 sp4**：在 sp4 目录里重新同步
    app 文件。**如果你那边已经把 sp4 冻结，就出 sp5，sp4 逐字节不动。**
    在 STATUS 里写明选了哪一个。」
  「如果包里内嵌了 EXT（live_dub_ext），版本必须是 **v0.4.16**（写出 commit 和
    版本号的证据）；没有内嵌就写「无 EXT」。」
  「**验收通过前不打 zip。**」

🔴 **本脚本选 sp5（不并入 sp4）** —— 理由（写进 STATUS §213）：
  ① **sp4 的包内容已被两处证据绑定**：
     `results/app/app587_specialmvp_sp4_build.json` → `app_sync.synced`
     （`live_caption_app.py` sha256 `ef367412…`）＋ §212 的三份验收 json
     （`app588_sp4_acceptance_sp4_{zh,en,zh_serial}.json` ⇒ 都跑在 sp4 上）
     ⇒ **原地改 sp4 会让这些证据不再描述磁盘上的 sp4**（APP-206/207/208 的
     「证据必须绑包身份 + 绑包内容」纪律）；
  ② APP-055：**旧版本目录不覆盖不删**、不原地改包；
  ③ APP-114 §3 明确允许这一分支（sp4 逐字节不动）。

🔴 **纪律**：
  · **sp4 只读**（本脚本对它只做 stat）；
  · **不覆盖、不删除**任何旧目录 / zip（sp1–sp4 一律保留）；
  · 仓库 ⇄ 客户包 = 两份独立副本 ⇒ 代码**定点同步**（逐文件 SHA256 校验）；
  · 本机**安全删除 shim** ⇒ 构建脚本**一律不删**（拷贝时排除 `.pyc` /
    `__pycache__`；要替换的 EXT 文件用**覆写**而不是删除）；
  · **不生成 zip**（用户级纪律：用户不通知 ⇒ 不主动打包；APP-114 §3 明文
    「验收通过前不打 zip」）。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
RESULTS = os.path.join(REPO, 'results', 'app')
SP4_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp4'
SP5_NAME = 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp5'
SP4 = os.path.join(HOME, SP4_NAME)
SP5 = os.path.join(HOME, SP5_NAME)
VERSION = '1.0-sp5'
REPORT = os.path.join(RESULTS, 'app591_specialmvp_sp5_build.json')

EXT_REPO = os.path.join(HOME, 'live_dub_ext')
EXT_COMMIT = '7a92f12'
EXT_COMMIT_FULL = ('7a92f12'
                    )
EXT_EXPECTED_VERSION = '0.4.16'

#: 🔴 **随 sp5 同步进包的 App 侧文件**（APP-114 的改动面）
#:   `time_stretch.py`     ⇒ §1 `SPEED_MAX` / `ZH_SPEED_MAX` 2.00 → 1.70
#:   `tts_worker.py`       ⇒ §1 两处兜底 `(1.0, 2.00)` → `(1.0, 1.70)`
#:   `tts_service.py`      ⇒ §1 注释同步（行为经 time_stretch 统一）
#:   `device_config.py`    ⇒ §1 `tts_speed_max_zh` 2.00 → 1.70 + 注释
#:   `live_caption_app.py` ⇒ §2.1 队列不再按时间丢弃（+ worker 失败才清空）
SYNC_FILES = ['live_caption_app.py', 'time_stretch.py', 'tts_worker.py',
              'tts_service.py', 'device_config.py']

BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']

ev = {'pkg': SP5, 'from_pkg': SP4, 'version': VERSION,
      'pkg_name': SP5_NAME,
      'why_sp5_not_sp4': (
          'APP-114 §3 给了两个分支：并入 sp4 ／ sp4 冻结则出 sp5。'
          '本轮选 **sp5**：① sp4 的包内容已被 app587 构建证据'
          '（app_sync.synced.live_caption_app.py sha256）与 §212 的三份验收 json '
          '**绑定** ⇒ 原地改 sp4 会让这些证据不再描述磁盘上的 sp4'
          '（APP-206/207/208：证据必须同时绑「包身份」+「包内容」）；'
          '② APP-055：旧版本目录不覆盖不删、不原地改包。'
          '⇒ **sp4 逐字节不动**（本脚本对 sp4 只做 stat）。'),
      'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'actions': [], 'gates': {}}
t0 = time.time()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root):
    n, total = 0, 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, total


def _blacklist_hit(rel):
    import fnmatch
    for pat in BLACKLIST_PATTERNS:
        if fnmatch.fnmatch(os.path.basename(rel), pat):
            return pat
    return None


def read_bytes(p):
    with open(p, 'rb') as f:
        return f.read()


def write_bytes(p, b):
    tmp = p + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(b)
    os.replace(tmp, p)


def crlf(b):
    """LF → CRLF（**已是 CRLF 的不动**）⇒ 包内统一 CRLF 形态。"""
    return b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def main():
    # ── ⓪ 前置检查 ──
    if not os.path.isdir(SP4):
        print('FAIL: sp4 不存在 %s' % SP4)
        return 2
    if os.path.exists(SP5):
        print('FAIL: sp5 已存在 ⇒ 绝不覆盖（只打新版本号）')
        return 2
    n4, b4 = dir_stats(SP4)
    ev['sp4_before'] = {'n_files': n4, 'bytes': b4, 'path': SP4}
    print('sp4: %d files / %d B' % (n4, b4))

    # ── ① 拷贝 sp4 → sp5（robocopy；排除 .pyc / __pycache__）──
    cmd = ['robocopy', SP4, SP5, '/E', '/XF', '*.pyc', '/XD', '__pycache__',
           '/R:1', '/W:1', '/MT:16', '/NFL', '/NDL', '/NJH', '/NJS', '/NP']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    rc = p.returncode
    if rc >= 8:
        print('FAIL: robocopy rc=%d\n%s\n%s' % (rc, p.stdout, p.stderr))
        return 2
    ev['actions'].append('robocopy sp4→sp5 rc=%d（1 = 有复制成功）' % rc)
    n5, b5 = dir_stats(SP5)
    ev['after_copy'] = {'n_files': n5, 'bytes': b5,
                        'elapsed_s': round(time.time() - t0, 1)}
    print('copied: %d files / %d B' % (n5, b5))

    # ── ② 路径重定位（sp4 → sp5）──
    repoint = []
    for rel in (os.path.join('cuda_env', 'pyvenv.cfg'),
                os.path.join('app', 'MANIFEST.json')):
        pth = os.path.join(SP5, rel)
        raw = read_bytes(pth)
        cnt = raw.count(SP4_NAME.encode('utf-8'))
        if cnt == 0:
            print('FAIL: %s 里没有 sp4 路径引用（预期 ≥1）' % rel)
            return 3
        new = raw.replace(SP4_NAME.encode('utf-8'), SP5_NAME.encode('utf-8'))
        write_bytes(pth, new)
        repoint.append({'file': rel.replace('\\', '/'), 'n_replaced': cnt,
                        'sha256_after': sha256_file(pth)})
    ev['repoint'] = repoint
    ev['actions'].append('路径重定位：%s' % ', '.join(
        '%s(×%d)' % (r['file'], r['n_replaced']) for r in repoint))

    # ── ③ EXT 升 v0.4.16（git archive 7a92f12 → 定点覆写）──
    ext = {'repo': EXT_REPO, 'commit': EXT_COMMIT,
           'expected_version': EXT_EXPECTED_VERSION, 'files': [],
           'shims_kept': [], 'skipped': []}
    if not os.path.isdir(os.path.join(EXT_REPO, '.git')):
        print('FAIL: EXT 仓库不存在 %s' % EXT_REPO)
        return 3
    head = subprocess.run(['git', '-C', EXT_REPO, 'rev-parse', EXT_COMMIT],
                          capture_output=True, text=True)
    ext['commit_full'] = head.stdout.strip()
    if not ext['commit_full']:
        print('FAIL: EXT 仓库里没有 commit %s' % EXT_COMMIT)
        return 3
    tmpdir = tempfile.mkdtemp(prefix='ext416_')
    try:
        arc = subprocess.run(
            ['git', '-C', EXT_REPO, 'archive', '--format=tar', EXT_COMMIT,
             'ext', 'extension', 'USER_GUIDE.md'],
            capture_output=True, timeout=600)
        if arc.returncode != 0:
            print('FAIL: git archive rc=%d' % arc.returncode)
            return 3
        with tarfile.open(fileobj=__import__('io').BytesIO(arc.stdout)) as tf:
            tf.extractall(tmpdir)
        src_ext = os.path.join(tmpdir, 'ext')
        # ③.1 python 模块：repo ext/*.py → pkg ext/bridge/*.py（CRLF）
        pkg_bridge = os.path.join(SP5, 'ext', 'bridge')
        for fn in sorted(os.listdir(src_ext)):
            if not fn.endswith('.py'):
                continue
            src = os.path.join(src_ext, fn)
            dst = os.path.join(pkg_bridge, fn)
            if not os.path.exists(dst):
                ext['skipped'].append({'file': 'ext/bridge/%s' % fn,
                                       'reason': '包内无对应文件（沿用 v0.4.8 的嵌入清单）'})
                continue
            b = crlf(read_bytes(src))
            write_bytes(dst, b)
            ext['files'].append({'file': 'ext/bridge/%s' % fn,
                                 'sha256': hashlib.sha256(b).hexdigest(),
                                 'bytes': len(b)})
        # ③.2 浏览器扩展：repo extension/* → pkg ext/extension/*（CRLF）
        src_inext = os.path.join(tmpdir, 'extension')
        pkg_inext = os.path.join(SP5, 'ext', 'extension')
        for dp, _dn, fns in os.walk(src_inext):
            for fn in sorted(fns):
                src = os.path.join(dp, fn)
                rel = os.path.relpath(src, src_inext)
                dst = os.path.join(pkg_inext, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                b = crlf(read_bytes(src))
                write_bytes(dst, b)
                ext['files'].append({'file': 'ext/extension/%s' % rel.replace('\\', '/'),
                                     'sha256': hashlib.sha256(b).hexdigest(),
                                     'bytes': len(b)})
        # ③.3 USER_GUIDE
        ug = os.path.join(tmpdir, 'USER_GUIDE.md')
        if os.path.isfile(ug):
            b = crlf(read_bytes(ug))
            write_bytes(os.path.join(SP5, 'ext', 'USER_GUIDE.md'), b)
            ext['files'].append({'file': 'ext/USER_GUIDE.md',
                                 'sha256': hashlib.sha256(b).hexdigest(),
                                 'bytes': len(b)})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ③.4 包内 ext/release.json（嵌入清单 + 证据）
    ver_py = os.path.join(SP5, 'ext', 'bridge', 'version.py')
    vtxt = read_bytes(ver_py).decode('utf-8', 'replace')
    got_ver = None
    for ln in vtxt.splitlines():
        if ln.strip().startswith('EXT_VERSION'):
            got_ver = ln.split('=')[1].strip().strip('"\'')
            break
    ext['version_in_bridge_version_py'] = got_ver
    if got_ver != EXT_EXPECTED_VERSION:
        print('FAIL: 包内 ext/bridge/version.py 的 EXT_VERSION=%s（期望 %s）'
              % (got_ver, EXT_EXPECTED_VERSION))
        return 3
    rel_json = {
        'version': EXT_EXPECTED_VERSION,
        'commit': ext['commit_full'],
        'source': ('git archive %s（%s：EXT v%s —— speed cap 2.0x -> 1.7x）'
                   % (EXT_COMMIT, EXT_REPO, EXT_EXPECTED_VERSION)),
        'embedded_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'embedded_by': 'APP-114 §3（App 模块 sp5 构建）',
        'n_files': len(ext['files']),
        'files': ext['files'],
        'shims_kept': [
            'ext/version.py（App 侧垫片，转发 ext.bridge.version）',
            'ext/app_root.py（App 侧垫片）',
            'ext/utf8_io.py（App 侧垫片）',
            'ext/bridge/__main__.py（App 侧 3 行入口，APP-104 §3）',
        ],
        'skipped': ext['skipped'],
    }
    write_bytes(os.path.join(SP5, 'ext', 'release.json'),
                (json.dumps(rel_json, ensure_ascii=False, indent=1)
                 + '\n').encode('utf-8'))
    ext['release_json_sha256'] = sha256_file(os.path.join(SP5, 'ext',
                                                           'release.json'))
    ev['ext'] = ext
    ev['actions'].append('EXT 升级：v0.4.8 → v0.4.16（commit %s，%d 个文件）'
                         % (ext['commit_full'][:7], len(ext['files'])))

    # ── ④ App 侧代码定点同步（dev → 包，逐文件 SHA256）──
    sync = {'sync_files_declared': SYNC_FILES, 'synced': [], 'n_same': 0,
            'mismatch': []}
    pkg_app = os.path.join(SP5, 'app')
    for fn in sorted(os.listdir(pkg_app)):
        if not fn.endswith('.py'):
            continue
        dev_p = os.path.join(DEV, fn)
        pkg_p = os.path.join(pkg_app, fn)
        if not os.path.exists(dev_p):
            continue
        if sha256_file(dev_p) == sha256_file(pkg_p):
            sync['n_same'] += 1
            continue
        if fn not in SYNC_FILES:
            sync['mismatch'].append(fn)
            continue
        b = read_bytes(dev_p)
        write_bytes(pkg_p, b)
        sync['synced'].append({'file': fn, 'sha256': hashlib.sha256(b).hexdigest(),
                               'bytes': len(b),
                               'dev_sha256': sha256_file(dev_p),
                               'pkg_sha256_after': sha256_file(pkg_p)})
    if sync['mismatch']:
        print('FAIL: 包内与 dev 不一致且不在同步清单里的文件：%s' % sync['mismatch'])
        return 3
    ev['app_sync'] = sync
    ev['actions'].append('app 代码同步：%d 个文件被改写；其余与 dev 逐字相同 %d 个'
                         % (len(sync['synced']), sync['n_same']))

    # ── ⑤ 包级 release.json（版本 + corrections + sp5_changes）──
    rj_path = os.path.join(SP5, 'release.json')
    rj = json.loads(read_bytes(rj_path).decode('utf-8'))
    rj['version'] = VERSION
    if 'APP-114' not in rj.get('corrections', []):
        rj.setdefault('corrections', []).append('APP-114')
    rj['ext'] = {'version': EXT_EXPECTED_VERSION, 'commit': ext['commit_full']}
    rj['sp5_changes'] = [
        'APP-114 §1（用户 2026-11-16 22:20 决定「2.0 速度还是太快了听上去不舒服，'
        '最高速度调整到 1.7x」）：**语速上限 2.00× → 1.70×**（**所有目标语言**：'
        '`time_stretch.SPEED_MAX = 1.70`、`ZH_SPEED_MAX = 1.70`、'
        '`tts_worker.py` 两处兜底 `(1.0, 2.00)` → `(1.0, 1.70)`、'
        '`device_config.tts_speed_max_zh` 2.00 → 1.70）。'
        '⚠️ **只改上限**：增益曲线不变（死区 3.0 s / 每秒 0.025 / 滞回 2.0 s / '
        '步长 ±0.1 全部照旧）；中文下限 1.10 不变；丢句阈值 0 不变；视频速度不变。',
        'APP-114 §2.1：**就绪前队列取消「按时间丢弃」**（旧 120 s 阈值删除，'
        '§212 冷启动实测 TTS 就绪 120.1 s 正好压线 ⇒ 必然丢句）⇒ '
        '**只有 TTS worker 明确失败/退出才清空队列**（计数 `n_drop_worker_failed` '
        '+ GUI 明示）；正常加载慢**一律不丢句**。',
        'APP-114 §2.2/§2.4：验收产物**带时间戳/run 编号**（禁止同名覆盖）＋ '
        '结果 json 附**逐句倍率直方图**与排序前 15。',
        'APP-114 §3：**sp4 冻结、逐字节不动** ⇒ 本包为 **sp5**（基于 sp4 复制）；'
        '内嵌 EXT 由 **v0.4.8 升到 v0.4.16**（commit %s）。'
        % ext['commit_full'][:7],
        'APP-114 §4：**验收通过前不打 zip** ⇒ 本轮只出包目录。',
    ]
    write_bytes(rj_path, (json.dumps(rj, ensure_ascii=False, indent=1)
                          + '\n').encode('utf-8'))
    ev['release_json_sha256'] = sha256_file(rj_path)

    # ── ⑥ README 的包体积行（按实测值更新）──
    nfin, bfin = dir_stats(SP5)
    size_txt = '* **包体积（实测）**：解压后 **%d 个文件 / %d B（%.3f GiB）**；' \
               'zip **待打包**（本版**只出包目录**；zip 须**用户通知后**才生成）。' \
               % (nfin, bfin, bfin / 1024.0 ** 3)
    rd = {}
    for fn in ('README_zh.md', 'README_en.md'):
        pth = os.path.join(SP5, fn)
        if not os.path.isfile(pth):
            continue
        txt = read_bytes(pth).decode('utf-8')
        lines = txt.splitlines()
        hit = -1
        for i, ln in enumerate(lines):
            if ('包体积（实测）' in ln) or ('Package size (measured)' in ln):
                hit = i
                break
        if hit < 0:
            rd[fn] = {'note': '未找到包体积行（未改）'}
            continue
        old = lines[hit]
        lines[hit] = size_txt if '包体积' in old else (
            '* **Package size (measured)**: extracted **%d files / %d B '
            '(%.3f GiB)**; zip **pending** (this release ships the folder only; '
            'zip is generated **only after the user asks**).'
            % (nfin, bfin, bfin / 1024.0 ** 3))
        write_bytes(pth, ('\n'.join(lines) + '\n').encode('utf-8'))
        rd[fn] = {'old_line': old[:200], 'new_line': lines[hit][:200],
                  'sha256_after': sha256_file(pth)}
    ev['readme'] = rd

    # ── ⑦ 闸门（只断言，不 purge）──
    g = {}
    g['n_pyc'] = 0
    g['n_blacklist'] = 0
    g['blacklist'] = []
    g['app_files_mismatch_vs_dev'] = []
    for dp, dn, fns in os.walk(SP5):
        dn[:] = [d for d in dn if d != '__pycache__']
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), SP5)
            if fn.endswith('.pyc'):
                g['n_pyc'] += 1
            hit = _blacklist_hit(rel)
            if hit:
                g['n_blacklist'] += 1
                g['blacklist'].append(rel)
    for fn in sorted(os.listdir(pkg_app)):
        if not fn.endswith('.py'):
            continue
        dev_p = os.path.join(DEV, fn)
        if os.path.exists(dev_p):
            if sha256_file(dev_p) != sha256_file(os.path.join(pkg_app, fn)):
                g['app_files_mismatch_vs_dev'].append(fn)
    pv = read_bytes(os.path.join(SP5, 'cuda_env', 'pyvenv.cfg')).decode('utf-8')
    g['pyvenv_cfg_has_sp4_path'] = SP4_NAME in pv
    g['pyvenv_cfg_has_sp5_path'] = SP5_NAME in pv
    mf = read_bytes(os.path.join(SP5, 'app', 'MANIFEST.json')).decode('utf-8')
    g['manifest_has_sp4_path'] = SP4_NAME in mf
    g['manifest_has_sp5_path'] = SP5_NAME in mf
    prof = json.loads(read_bytes(os.path.join(SP5, 'package_profile.json'))
                      .decode('utf-8'))
    g['profile'] = prof.get('profile')
    g['allow_cuda'] = prof.get('allow_cuda')
    g['ext_version'] = ext['version_in_bridge_version_py']
    g['ext_commit'] = ext['commit_full']
    # ── §1/§2.1 的**行为级**判据（AST 直读，不 import）──
    import ast
    ts_src = read_bytes(os.path.join(pkg_app, 'time_stretch.py')).decode('utf-8')
    tst = ast.parse(ts_src)
    consts = {}
    for n in tst.body:
        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                if getattr(tgt, 'id', None) in ('SPEED_MAX', 'ZH_SPEED_MAX',
                                               'SPEED_MIN', 'ZH_SPEED_MIN',
                                               'LAG_DEADZONE_S', 'SPEED_PER_LAG_S',
                                               'LAG_HYSTERESIS_S', 'MAX_STEP_CHANGE'):
                    consts[tgt.id] = ast.literal_eval(n.value)
    g['pkg_speed_constants'] = consts
    g['pkg_speed_max_ok'] = (consts.get('SPEED_MAX') == 1.70
                             and consts.get('ZH_SPEED_MAX') == 1.70)
    g['pkg_gain_curve_unchanged'] = (
        consts.get('LAG_DEADZONE_S') == 3.0
        and consts.get('SPEED_PER_LAG_S') == 0.025
        and consts.get('LAG_HYSTERESIS_S') == 2.0
        and consts.get('MAX_STEP_CHANGE') == 0.1
        and consts.get('SPEED_MIN') == 1.0
        and consts.get('ZH_SPEED_MIN') == 1.10)
    lca_src = read_bytes(os.path.join(pkg_app, 'live_caption_app.py')).decode('utf-8')
    lca = ast.parse(lca_src)
    q_overflow = None
    for n in lca.body:
        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                if getattr(tgt, 'id', None) == '_TTS_QUEUE_OVERFLOW_S':
                    q_overflow = ast.literal_eval(n.value)
    g['pkg_queue_overflow_s'] = q_overflow
    g['pkg_queue_no_time_drop'] = (q_overflow is None)
    g['n_files'] = nfin
    g['dir_bytes'] = bfin
    ev['gates'] = g

    ok = (g['n_pyc'] == 0 and g['n_blacklist'] == 0
          and not g['app_files_mismatch_vs_dev']
          and g['pyvenv_cfg_has_sp5_path'] and not g['pyvenv_cfg_has_sp4_path']
          and g['manifest_has_sp5_path'] and not g['manifest_has_sp4_path']
          and g['profile'] == 'specialmvp' and g['allow_cuda'] is True
          and g['ext_version'] == EXT_EXPECTED_VERSION
          and g['pkg_speed_max_ok'] and g['pkg_gain_curve_unchanged']
          and g['pkg_queue_no_time_drop'])
    ev['verdict'] = 'PASS' if ok else 'FAIL'
    ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    ev['elapsed_s'] = round(time.time() - t0, 1)

    tmp = REPORT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    os.replace(tmp, REPORT)
    print(json.dumps(ev['gates'], ensure_ascii=False, indent=1))
    print('VERDICT=%s  elapsed=%.1fs' % (ev['verdict'], ev['elapsed_s']))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
