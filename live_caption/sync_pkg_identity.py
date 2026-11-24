#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""客户包「版本标识一致」**生产路径**执行器（APP-234 轮新增）。

## 为什么要有这个脚本（🔴 真缺陷，不是重复造轮子）

APP-233 轮把两处包内缺陷的**修法**放进了
`live_caption/sync_c172_version_identity_to_pkg.py`（通用版本标识同步器）
—— 修法本身是对的。但**完整版线（v2.x）的成包路径从来不会自动跑它**：

- `live_caption/_app129_build_v26.py` 的 stage 有 4 个：
  `copy` / `sync` / `pack` / `cleanup`；
- `stage=sync` 只写 `app/tts_engine.py`、`app/tts_worker.py`、
  `ext/bridge/*`、`ext/extension/*`、`ext/extension/manifest.json`、
  `Start_Bridge.bat`、`models/bgsep/*`
  ⇒ **从不碰** `README_zh.md` / `README_en.md` / `NOTICE` /
  `app/MANIFEST.json`；
- 唯一会调 `sync_c172` 的是 `pack_v13.py` 的 `main()` ⇒ 而完整版线
  **从来不出 zip**（用户长期规则「不通知 ⇒ 不打包」）⇒ `stage=pack`
  **不执行** ⇒ `sync_c172` **不执行**；
- 实测证据：`results/app/app129_build_v26.log` 全文只有
  `stage=copy`（×2）与 `stage=sync`（×5），**没有一行 `stage=pack`**；
  而 v2.6 的 `README_zh.md` mtime = 2026-11-24 13:14:55
  ⇒ 版本标识是**人工带外**做的。

⇒ **下一版（v2.7）若照抄同一套 stage，README/NOTICE/MANIFEST 的版本标识
又会退回人工步骤** —— 这正是本项目反复踩的
「**修了 harness ≠ 修了产品**」（交付路径与验收路径是两条路）。

## 本脚本做什么

`pack_v13` 已经会调 `sync_c172`；本脚本把**同一套调用**抽成一个
**独立可执行**的入口，让**完整版线**（无 zip）也能在成包路径上自动执行：

1. 从**包目录名**解析目标版本（`..._v2.7` ⇒ `2.7`）；
2. 解析「改动说明」正文文件（**约定优先**，再退回历史命名）：
   - `live_caption/release_notes/v<ver>_{zh,en}.md`（pack_v13 的自动发现约定）
   - `live_caption/_app*_changelog_<ver>_{zh,en}.md`（历史命名兜底）
   ⇒ **找不到不是错**（与 `pack_v13` 一致：只提醒、不阻断）；
3. 跑 `sync_c172_version_identity_to_pkg.py`（**同 pack_v13 的调用路径**）
   ⇒ 改 README_zh/README_en 标题版本号、NOTICE 首行、
   `app/MANIFEST.json` 的 `version`，并插入本版「改动说明」段；
4. 跑 `results/app/app170_version_identity_gate.py`（**同一道闸门**）
   ⇒ D1/D2/D3（标题/NOTICE 版本号）是 **DET（阻断项）** ⇒ 不过就失败；
5. **自己做一遍硬断言**（🔴 闸门的 I1b/D4/D5 是 ADV（建议项）⇒ 不足以
   fail-closed，故本脚本另做**硬**判定）：
   - README_zh 标题版本号 == 目标版本；
   - README_en 标题版本号 == 目标版本；
   - NOTICE 首行版本号 == 目标版本；
   - `app/MANIFEST.json` 的 `version` == 目标版本；
   - README_zh 的 `## v<ver> 改动说明` **恰好 1 次**；
   - README_en 的 `## What's new in v<ver>` **恰好 1 次**；
   ⇒ 任一不成立 ⇒ **退出码非 0**（fail-closed）。

## 🔴 安全护栏：绝不原地改「已签 ACCEPTED」的包（APP-055）

若目标包目录里已有 `ACCEPTED.json` 且其 `version` **等于**目标版本
（即**这个版本本身**已被签收）⇒ **拒绝改写**（退出码 3），
除非显式加 `--allow-accepted`。

⚠️ 注意：升版时新目录是从上一版 `robocopy` 来的 ⇒ 会**带着上一版的**
`ACCEPTED.json`（其 `version` 是**上一版**）⇒ 与目标版本不等 ⇒ **放行**。
本护栏只挡「原地改已签的同版本包」。

## 用法

    python live_caption/sync_pkg_identity.py --pkg <包目录>
    python live_caption/sync_pkg_identity.py --pkg <包目录> --dry-run
    python live_caption/sync_pkg_identity.py --pkg <包目录> \
        --changelog-zh <正文.md> --changelog-en <正文.md> \
        --expect-version 2.7 --json <证据.json>

退出码：`0` = 全部一致；`1` = 有硬断言/闸门失败；`2` = 参数或包目录不对；
`3` = 拒绝改写已签的同版本包。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: `sync_c172`（通用版本标识同步器）—— **与 pack_v13 同一个**
SYNC_C172 = os.path.join(HERE, 'sync_c172_version_identity_to_pkg.py')
#: app170（版本标识一致 + NOTICE 许可署名闸门）—— **与 pack_v13 同一个**
GATE = os.path.join(REPO, 'results', 'app', 'app170_version_identity_gate.py')
#: 「改动说明」正文的**约定**目录（pack_v13 的自动发现处）
RELEASE_NOTES = os.path.join(HERE, 'release_notes')

#: README_zh 标题行：`# Confucius4-R2T2 实时字幕（技术评估版 vX.Y）`
#: 🔴 与 `sync_c172` 的 `_ZH_TITLE_RE` **同口径**（全角括号、**无空格**）
#: —— 实测真包首行是 `实时字幕（技术评估版 v2.6）` ⇒ 「字幕」与「（」之间
#: **没有空格** ⇒ 写成 `\s+` 会**永远匹配不上**（APP-234 轮踩过这个坑）。
_ZH_TITLE_RE = re.compile(
    r'^(#\s*Confucius4-R2T2\s+实时字幕（技术评估版\s+)'
    r'v(\d+(?:\.\d+)+)(）)\s*$', re.M)
#: README_en 标题行：`# Confucius4-R2T2 Live Captions (technical evaluation build vX.Y)`
_EN_TITLE_RE = re.compile(
    r"^(#\s*Confucius4-R2T2\s+Live Captions\s+"
    r"\(technical evaluation build\s+)v(\d+(?:\.\d+)+)(\))\s*$", re.M)
#: NOTICE 首行：`Confucius4 LiveCaption vX.Y — 第三方组件归属与许可证`
_NOTICE_RE = re.compile(r'^Confucius4\s+LiveCaption\s+v(\d+(?:\.\d+)+)', re.M)
#: README_zh 的改动说明段标题：`## vX.Y 改动说明`
_ZH_SEC_RE = re.compile(r'^##\s+v(\d+(?:\.\d+)+)\s+改动说明\s*$', re.M)
#: README_en 的改动说明段标题：`## What's new in vX.Y`
_EN_SEC_RE = re.compile(r"^##\s+What's new in v(\d+(?:\.\d+)+)\s*$", re.M)

MANIFEST_REL = os.path.join('app', 'MANIFEST.json')


def detect_version(pkg_dir: str) -> str:
    """从**包目录名**解析版本号（`..._v2.7` ⇒ `2.7`）。"""
    base = os.path.basename(os.path.normpath(pkg_dir))
    m = re.search(r'_v(\d+(?:\.\d+)+)', base)
    return m.group(1) if m else ''


def resolve_changelog(ver: str, lang: str):
    """解析本版本「改动说明」正文文件。

    **约定优先**：`live_caption/release_notes/v<ver>_<lang>.md`
    （= `pack_v13.py` 的自动发现目录与命名）；
    **再兜底**：`live_caption/_app*_changelog_<ver>_<lang>.md`（历史命名）。

    ⇒ 找不到返回 `None`（**不是错**：与 `pack_v13` 一致 —— 只提醒）。
    """
    cand = os.path.join(RELEASE_NOTES, 'v%s_%s.md' % (ver, lang))
    if os.path.isfile(cand):
        return cand
    import glob
    hits = sorted(glob.glob(os.path.join(
        HERE, '_app*_changelog_%s_%s.md' % (ver, lang))))
    return hits[0] if hits else None


def read_text(path: str) -> str:
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def hard_checks(pkg_dir: str, ver: str, want_en_section: bool = True):
    """🔴 硬断言（fail-closed）—— 逐项返回 (name, ok, detail)。

    ⚠️ `want_en_section=False` 时**不**断言 README_en 的「改动说明」段：
    调用方**没给**英文正文时，英文段**不该**凭空出现（那是内容缺失，
    不是版本标识不一致）⇒ 不该用它来判「身份同步失败」。
    """
    out = []

    zh_p = os.path.join(pkg_dir, 'README_zh.md')
    en_p = os.path.join(pkg_dir, 'README_en.md')
    nt_p = os.path.join(pkg_dir, 'NOTICE')
    mf_p = os.path.join(pkg_dir, MANIFEST_REL)

    zh = read_text(zh_p) if os.path.isfile(zh_p) else ''
    en = read_text(en_p) if os.path.isfile(en_p) else ''
    nt = read_text(nt_p) if os.path.isfile(nt_p) else ''

    m = _ZH_TITLE_RE.search(zh)
    out.append(('README_zh 标题版本号 == %s' % ver,
                bool(m) and m.group(2) == ver,
                'got=%s' % (m.group(2) if m else None)))
    m = _EN_TITLE_RE.search(en)
    out.append(('README_en 标题版本号 == %s' % ver,
                bool(m) and m.group(2) == ver,
                'got=%s' % (m.group(2) if m else None)))
    m = _NOTICE_RE.search(nt)
    out.append(('NOTICE 首行版本号 == %s' % ver,
                bool(m) and m.group(1) == ver,
                'got=%s' % (m.group(1) if m else None)))

    mf_ver = None
    if os.path.isfile(mf_p):
        try:
            mf_ver = json.loads(read_text(mf_p)).get('version')
        except Exception:
            mf_ver = None
    out.append(('app/MANIFEST.json version == %s' % ver,
                str(mf_ver) == str(ver), 'got=%r' % (mf_ver,)))

    # 🔴 只数**本版本**的段标题（`_ZH_SEC_RE` 数的是**所有**版本 ⇒
    #    会把历史版本的段也算进来 ⇒ count 虚高）
    n_zh = sum(1 for m in _ZH_SEC_RE.finditer(zh) if m.group(1) == ver)
    out.append(('README_zh 的 `## v%s 改动说明` 恰好 1 次' % ver,
                n_zh == 1, 'count=%d' % n_zh))
    if want_en_section:
        n_en = sum(1 for m in _EN_SEC_RE.finditer(en) if m.group(1) == ver)
        out.append(('README_en 的 `## What\'s new in v%s` 恰好 1 次' % ver,
                    n_en == 1, 'count=%d' % n_en))
    return out


def _is_delivery_pkg(pkg):
    """判定 `pkg` 是否为**交付候选包目录**（而不是临时影子 / 测试目录）。

    🔴 APP-235 轮实测到的**真缺陷**（生产路径，不是 harness）：
    本脚本原先**无条件**把 app170 闸门证据写到**规范路径**
    `results/app/app170_version_identity_gate_evidence.json`
    ⇒ 在**任何**影子包上跑一次（v2.7 影子、APP-234 轮的 `%TEMP%` 临时目录……）
    就会把「**交付包**的闸门记录」**覆盖成影子包的结果**。
    实测后果：规范证据的 `pkg` 字段变成
    `%TEMP%\\app234_id_klh3m45v\\Confucius4_LiveCaption_v2.10`（**跑完即删**
    ⇒ reviewer **无法复算**）、`pass` 从 **19** 变 **20**、
    真实包那两条**真实 advisory**（I1b / D4）**消失**
    ⇒ **审计链断**（规范证据不再描述任何真实交付包）。

    ⇒ 修法：
      1. **永远**额外写一份**按版本作用域**的证据
         （`app170_version_identity_gate_evidence_v<ver>.json`）⇒ 不可能互相覆盖；
      2. **只有**处理**交付候选目录**时才更新规范文件。
    """
    p = os.path.abspath(pkg)
    if not re.match(r'^Confucius4_LiveCaption_v\d+(?:\.\d+)*$',
                    os.path.basename(p)):
        return False
    temp = os.environ.get('TEMP') or os.environ.get('TMP') or ''
    if temp:
        tp = os.path.abspath(temp)
        if p == tp or p.startswith(tp + os.sep):
            return False
    return True


def run(cmd, timeout=1800):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def main() -> int:
    ap = argparse.ArgumentParser(
        description='客户包「版本标识一致」生产路径执行器'
                    '（sync_c172 + app170 闸门 + 硬断言）')
    ap.add_argument('--pkg', required=True, help='客户包目录（不含 .zip）')
    ap.add_argument('--expect-version', default=None,
                    help='目标版本号（默认从**包目录名**解析）')
    ap.add_argument('--changelog-zh', default=None,
                    help='本版本「改动说明」正文文件（中文）；'
                         '不给则按约定自动发现')
    ap.add_argument('--changelog-en', default=None,
                    help="本版本 'What\'s new' 正文文件（英文）；"
                         '不给则按约定自动发现')
    ap.add_argument('--allow-accepted', action='store_true',
                    help='允许改写「已签 ACCEPTED 的**同版本**」包'
                         '（默认拒绝，APP-055）')
    ap.add_argument('--dry-run', action='store_true',
                    help='只读检查（**不写任何文件**）')
    ap.add_argument('--json', default=None, help='证据输出路径')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg):
        print('[FAIL] 包目录不存在：%s' % pkg)
        return 2
    ver = args.expect_version or detect_version(pkg)
    if not ver:
        print('[FAIL] 包目录名不含版本号：%s' % os.path.basename(pkg))
        return 2

    print('=' * 74)
    print('sync_pkg_identity —— 客户包版本标识一致（生产路径）')
    print('=' * 74)
    print('包目录：%s' % pkg)
    print('目标版本：%s' % ver)

    # ── 🔴 护栏：拒绝原地改「已签 ACCEPTED 的同版本包」（APP-055）────
    acc_p = os.path.join(pkg, 'ACCEPTED.json')
    acc_ver = None
    if os.path.isfile(acc_p):
        try:
            acc_ver = json.loads(read_text(acc_p)).get('version')
        except Exception:
            acc_ver = None
    if str(acc_ver) == str(ver) and not args.allow_accepted:
        print()
        print('[FAIL] 包内已有 ACCEPTED.json 且 version == %s' % ver)
        print('       ⇒ 这是**已签收的同版本包** ⇒ 按 APP-055 拒绝原地改写。')
        print('       （升版时新目录带的是**上一版**的 ACCEPTED.json ⇒ 放行）')
        print('       确需改写请显式加 --allow-accepted。')
        return 3

    cl_zh = args.changelog_zh or resolve_changelog(ver, 'zh')
    cl_en = args.changelog_en or resolve_changelog(ver, 'en')
    print('改动说明正文：zh=%s' % (cl_zh or '（无 ⇒ 只提醒，不阻断）'))
    print('              en=%s' % (cl_en or '（无 ⇒ 只提醒，不阻断）'))

    evidence = {
        'tool': 'live_caption/sync_pkg_identity.py',
        'pkg': pkg,
        'target_version': ver,
        'dry_run': bool(args.dry_run),
        'changelog_zh': cl_zh,
        'changelog_en': cl_en,
        'steps': [],
        'hard_checks': [],
        'files_before': {},
        'files_after': {},
    }
    watch = ['README_zh.md', 'README_en.md', 'NOTICE', MANIFEST_REL]
    for rel in watch:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(p):
            evidence['files_before'][rel] = {
                'bytes': os.path.getsize(p), 'sha256': sha256_of(p)}

    # ── ① sync_c172（**与 pack_v13 同一调用路径**）────────────────────
    cmd = [sys.executable, SYNC_C172, '--pkg', pkg]
    if cl_zh:
        cmd += ['--changelog-zh', cl_zh]
    if cl_en:
        cmd += ['--changelog-en', cl_en]
    if args.dry_run:
        cmd += ['--dry-run']
    print()
    print('① sync_c172（版本标识同步）……')
    rc, out, err = run(cmd)
    print(out[-4000:])
    if err.strip():
        print('stderr: %s' % err[-1000:])
    evidence['steps'].append({
        'step': 'sync_c172', 'cmd': cmd, 'rc': rc,
        'stdout_tail': out[-4000:], 'stderr_tail': err[-1000:]})
    if rc != 0:
        print('[FAIL] sync_c172 返回 %d ⇒ 身份同步失败' % rc)
        _dump(evidence, args)
        return 1

    # ── ② app170 闸门（**同一道闸门**）──────────────────────────────
    if not args.dry_run:
        # 🔴 APP-235：**非交付包**（影子包 / 临时目录）⇒ 闸门证据写**临时文件**
        #    并在用完后删除 ⇒ ① **绝不覆盖**「交付包」的规范闸门记录
        #    ② **零仓库污染**（不在 results/app 留垃圾文件）；
        #    **交付候选包**才写规范文件（与 pack_v13 的既定约定一致：
        #    规范文件＝「当前交付候选包的闸门记录」）。
        import tempfile
        is_delivery = _is_delivery_pkg(pkg)
        tmp_ev_dir = None
        if is_delivery:
            ev_path = os.path.join(
                REPO, 'results', 'app',
                'app170_version_identity_gate_evidence.json')
        else:
            tmp_ev_dir = tempfile.mkdtemp(prefix='app235_gate_ev_')
            ev_path = os.path.join(
                tmp_ev_dir, 'app170_version_identity_gate_evidence.json')
        cmd = [sys.executable, GATE, '--pkg', pkg,
               '--expect-version', ver,
               '--json', ev_path]
        print()
        print('② app170 闸门（版本标识一致 + NOTICE 署名）……')
        rc, out, err = run(cmd)
        print(out[-4000:])
        if err.strip():
            print('stderr: %s' % err[-1000:])
        evidence['steps'].append({
            'step': 'app170_gate', 'cmd': cmd, 'rc': rc,
            'stdout_tail': out[-4000:], 'stderr_tail': err[-1000:]})
        if tmp_ev_dir:
            import shutil
            shutil.rmtree(tmp_ev_dir, ignore_errors=True)
        if rc != 0:
            print('[FAIL] app170 闸门未通过（rc=%d）' % rc)
            _dump(evidence, args)
            return 1

    # ── ③ 硬断言（🔴 自己的判定 ⇒ fail-closed）────────────────────────
    #  🔴 `--dry-run` 的语义：**不写盘** ⇒ 盘上仍是**旧**状态 ⇒ 直接对
    #    盘面断言**必然**失败（那是判据用错对象，不是产品缺陷）
    #    ⇒ dry-run 时改为：把 4 个身份文件复制到**临时影子目录**，
    #    在影子上真跑一遍同步，再对影子断言 ⇒ 断言的是
    #    「**若真跑**会得到什么」，而**真包一个字节都不动**。
    print()
    print('③ 硬断言（版本标识必须**完全**一致）……')
    shadow = None
    try:
        if args.dry_run:
            import shutil
            import tempfile
            # 🔴 影子目录名**必须带版本号**：下游 `sync_c172` / `app170` 的
            #   `detect_version()` 是**从包目录名**解析版本的
            #   ⇒ 目录名不含 `_vX.Y` ⇒ 它们直接失败
            #   （与 app170 的 `make_fake_pkg` 同款做法）。
            _tmp = tempfile.mkdtemp(prefix='sync_pkg_identity_dry_')
            shadow = os.path.join(
                _tmp, 'Confucius4_LiveCaption_v%s' % ver)
            os.makedirs(os.path.join(shadow, 'app'), exist_ok=True)
            for rel in watch:
                s = os.path.join(pkg, rel.replace('/', os.sep))
                if os.path.isfile(s):
                    d = os.path.join(shadow, rel.replace('/', os.sep))
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
            print('   （dry-run ⇒ 在**临时影子**上真跑一遍再断言；'
                  '真包零改动）')
            cmd = [sys.executable, SYNC_C172, '--pkg', shadow]
            if cl_zh:
                cmd += ['--changelog-zh', cl_zh]
            if cl_en:
                cmd += ['--changelog-en', cl_en]
            rc2, out2, err2 = run(cmd)
            if rc2 != 0:
                print('  [FAIL] 影子上的 sync_c172 返回 %d' % rc2)
                print(out2[-2000:])
            checks = hard_checks(shadow, ver,
                                want_en_section=bool(cl_en))
        else:
            checks = hard_checks(pkg, ver, want_en_section=bool(cl_en))
        n_fail = 0
        for name, ok, detail in checks:
            print('  [%s] %s   %s' % ('PASS' if ok else 'FAIL', name, detail))
            if not ok:
                n_fail += 1
        evidence['hard_checks'] = [
            {'name': n, 'ok': bool(o), 'detail': d} for n, o, d in checks]
    finally:
        if shadow:
            import shutil
            shutil.rmtree(os.path.dirname(shadow), ignore_errors=True)

    for rel in watch:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        if os.path.isfile(p):
            evidence['files_after'][rel] = {
                'bytes': os.path.getsize(p), 'sha256': sha256_of(p)}

    evidence['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    evidence['n_fail'] = n_fail

    print()
    print('=' * 74)
    print('结论：%s（硬断言失败 %d 项）' % (
        'PASS' if n_fail == 0 else 'FAIL', n_fail))
    print('=' * 74)
    _dump(evidence, args)
    return 0 if n_fail == 0 else 1


def _dump(evidence, args):
    out = args.json
    if not out:
        return
    d = os.path.dirname(os.path.abspath(out))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    tmp = out + '.tmp_sync_pkg_identity'
    with open(tmp, 'wb') as f:
        f.write(json.dumps(evidence, ensure_ascii=False, indent=2)
                .encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out)
    print('证据：%s' % out)


if __name__ == '__main__':
    sys.exit(main())
