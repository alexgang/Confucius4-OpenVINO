#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app170_version_identity_gate.py —— **打包前**「版本标识一致 + NOTICE 许可署名」闸门。

🔴🔴🔴 要防的缺陷（2026-10-30 22:0x 巡检实测，**已复现**）
-----------------------------------------------------------
`pack_v13.py` 升版时只做两件事：

  ① `os.rename` 把源目录 `Confucius4_LiveCaption_v1.12` 改成 `..._v1.13`
     （`pack_v13.py` L691-702）；
  ② `refresh_manifest()` 把 `app/MANIFEST.json` 的 `version` 写成新版本号
     （`pack_v13.py` L395）。

⇒ **README_zh.md / README_en.md / NOTICE 三个文件的版本号一个都没动**
⇒ 而这三个文件**只存在于客户包里**（仓库里没有）⇒ **没有任何脚本会改它们**
⇒ 每次升版都会**原样复发**。

🔴 **实测证据（不是推演）**：
  - 交付 zip `Confucius4_LiveCaption_v1.12.zip`（11:20 生成）内：
      `README_zh.md` 首行 = `# Confucius4-R2T2 实时字幕（技术评估版 **v1.6**）`
      `README_en.md` 首行 = `# ... (technical evaluation build **v1.6**)`
      `NOTICE`    首行 = `Confucius4 LiveCaption **v1.6** — 第三方组件归属与许可证`
    ⇒ **客户拿到的 v1.12 包自称 v1.6**。
  - 并发会话已用 `sync_c171_version_identity_to_pkg.py` 把**包目录**修成 v1.12
    （`pkg_backup_app_c171/` 里是修复前副本，备份可作反证基线）。
  - ⇒ **包目录现在是好的，但「下一次打包」会把缺陷带回来**。

🔴 为什么这条必须进**闸门**而不是只修一次
-----------------------------------------
MEMORY「修掉一处 ≠ 这一类不会再来」（§36）：
手改一次包目录 ⇒ 下一个版本又错 ⇒ 必须让**打包流水线自己拦住**。

⚠️ **只做检查不改文件**：闸门命中即 **FAIL** ⇒ 拒绝打包。
   修复动作由 `live_caption/sync_c172_version_identity_to_pkg.py` 负责
   （定点替换，不整目录覆盖）。

🔴🔴 **判据必须能识破未同步的旧状态**（不是恒真）
------------------------------------------------
- **REAL 组**：对当前包目录（已同步）跑 ⇒ 必须全 PASS；
- **BUG 组**：对**修复前**的副本（`pkg_backup_app_c171/`）跑同一套断言
  ⇒ 判定项必须**全部 FAIL**（命中即证明判据能识破旧状态）。
  ⚠️ 反证基线用**磁盘上的备份目录**，不用 `HEAD`
  —— 本轮改动**只改客户包**，仓库侧没动 ⇒ `HEAD` 取不到「修复前」的那份。

纪律
----
- **不 import 被测模块**（顶层 numpy 等）⇒ 只用 stdlib + `ast`。
- **不跑推理 / 不占 GPU / 不取机器锁**（纯文本读取）。
- 只读客户包 ⇒ **不改任何文件**。
- `--pkg` **必填**（不写死版本 ⇒ 自动发现会指向别的包）。

用法
----
    python results/app/app170_version_identity_gate.py --pkg <包目录>
    python results/app/app170_version_identity_gate.py --pkg <包目录> --json <out.json>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

#: 🔴 **修复前备份目录**（并发会话 `sync_c171` 留下的包外备份）⇒ 反证基线
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app_c171'

#: 版本号匹配（`1.12` / `1.9` / `1.10`）
_VER_RE = re.compile(r'\d+(?:\.\d+)+')

PASS = 0
FAIL = 0
FAILS = []
ADVISORIES = []


def check_group(group, kind, name, cond, detail=''):
    """`group` ∈ {'REAL','BUG'}；`kind` ∈ {'INV','DET','ADV'}。

    期望矩阵：
      | 组别 | INV | DET | ADV |
      |------|-----|-----|-----|
      | REAL | PASS | PASS | PASS（缺失只告警）|
      | BUG  | PASS | FAIL | FAIL（且**不**计入 verdict）|

    ⇒ **DET（阻断项）**：REAL 必须成立、BUG 必须不成立（命中即证明判据能识破旧状态）
      ⇒ REAL 不成立 ⇒ **拒绝打包**。
    ⇒ **ADV（建议项）**：README「改动说明」章节属于**人工撰写的内容**，
      缺一节只是「客户看不到本版改了什么」的提醒，**不是版本标识缺陷**
      ⇒ **不阻断打包**，但要在报告里列出来。
    ⇒ **INV（不变量）**：两组都必须成立（如 NOTICE 的许可署名）。
    """
    global PASS, FAIL
    ok = bool(cond)
    if group == 'BUG' and kind in ('DET', 'ADV'):
        ok = (not ok)
    tag = '%s/%s' % (group, kind)
    if kind == 'ADV':
        # 建议项：**REAL 里不成立 = 告警**；BUG 里不成立 = 判据有效（不算失败）
        if group == 'REAL' and not ok:
            ADVISORIES.append((name, detail))
            print('  [提醒] %-11s %-52s %s' % (tag, name, detail))
            return
        if group == 'BUG' and not ok:
            print('  [PASS] %-11s %-52s %s（判据能识破旧状态）'
                  % (tag, name, detail))
            return
        print('  [PASS] %-11s %-52s %s' % (tag, name, detail))
        return
    if ok:
        PASS += 1
        print('  [PASS] %-11s %-52s %s' % (tag, name, detail))
    else:
        FAIL += 1
        FAILS.append((tag, name, detail))
        print('  [FAIL] %-11s %-52s %s' % (tag, name, detail))


def read_text(path):
    with open(path, 'rb') as f:
        return f.read().decode('utf-8')


def detect_version(pkg_dir):
    m = re.search(r'_v(\d+(?:\.\d+)+)\s*$',
                  os.path.basename(os.path.normpath(pkg_dir)))
    return m.group(1) if m else None


def make_fake_pkg(tmpdir, src_dir, ver):
    """造一份「客户包目录形态」的影子副本（只含被验的三个文本文件 + MANIFEST）。

    ⇒ **不碰真实客户包**（闸门只读）。
    """
    dst = os.path.join(tmpdir, 'Confucius4_LiveCaption_v%s' % ver)
    os.makedirs(os.path.join(dst, 'app'), exist_ok=True)
    for fn in ('README_zh.md', 'README_en.md', 'NOTICE'):
        shutil.copy2(os.path.join(src_dir, fn), os.path.join(dst, fn))
    man = {'files': 0, 'bytes': 0, 'version': ver, 'notes': ''}
    with open(os.path.join(dst, 'app', 'MANIFEST.json'), 'w',
              encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False)
    return dst


def run_group(group, pkg_dir, ver, expect_version=None):
    """在给定包目录上跑全套断言。

    `expect_version`：本次打包的**目标版本号**（默认 = 目录名里的版本号）。

    🔴🔴🔴 **升版场景的关键区分**（2026-10-31 打 v1.13 时暴露）
    ---------------------------------------------------------
    打包流水线里，目录名**已经**改成 `..._v1.13`，但 `MANIFEST.version`
    要到 `refresh_manifest()` 才刷新（那一步在打包**后段**）。

    ⇒ 若 I1 硬要求「目录名 == MANIFEST.version」⇒ **每次升版必被自己的
      闸门拦死**（这是 §113 引入闸门时留下的**顺序缺陷**，不是数据问题）。

    ⇒ 解法（**两道断言，各管一段**）：
      ① **闸门**（本脚本）：判「目录名 == 目标版本」为**硬项**；
         判「MANIFEST.version == 目标版本」在**升版未刷新前降级为提醒**；
      ② **zip 级硬断言**（`pack_v13.py::_verify_and_report`）：
         打包结束时读**zip 内**的 MANIFEST ⇒ 必须 == 目标版本
         ⇒ **交付物**层面的最终保证（此时 refresh_manifest 已跑过）。

    ⚠️ 因此「MANIFEST 不一致」**不再阻断打包**，但**打包后的 zip 断言**
       仍是硬门 ⇒ 客户拿到自称旧版本的包**不可能发生**。
    """
    print('\n== %s 组：%s ==' % (group, pkg_dir))

    zh = read_text(os.path.join(pkg_dir, 'README_zh.md'))
    en = read_text(os.path.join(pkg_dir, 'README_en.md'))
    nt = read_text(os.path.join(pkg_dir, 'NOTICE'))
    man = json.loads(read_text(os.path.join(pkg_dir, 'app', 'MANIFEST.json')))

    target = expect_version or ver
    man_ver = man.get('version')

    # ── INV：不变量（两组都必须 PASS）──
    # I1a：目录名版本 == 目标版本（**硬项**，升版场景下这是真正的判据）
    check_group(group, 'INV', 'I1a 目录名版本 == 目标版本 %s' % target,
                detect_version(pkg_dir) == target,
                'dir=%s target=%s' % (detect_version(pkg_dir), target))
    # I1b：MANIFEST.version == 目标版本
    #   🔴 升版未刷新前**允许不一致**（refresh_manifest 稍后修正）
    #      ⇒ 降级为**提醒**；zip 级硬断言在 pack_v13.py 里做。
    if man_ver == target:
        check_group(group, 'INV', 'I1b MANIFEST.version == 目标版本 %s' % target,
                    True, 'manifest=%s' % man_ver)
    else:
        check_group(group, 'ADV',
                    'I1b MANIFEST.version == 目标版本 %s（升版未刷新，'
                    'zip 级断言兜底）' % target,
                    False, 'manifest=%s target=%s' % (man_ver, target))
    check_group(group, 'INV', 'I2 NOTICE 仍含 wespeaker 署名',
                'wespeaker' in nt, '')
    check_group(group, 'INV', 'I3 NOTICE 仍含 pyannote 署名',
                'pyannote' in nt, '')
    check_group(group, 'INV', 'I4 NOTICE 仍含 MIT 许可',
                'MIT' in nt, '')
    nt_cc = nt.upper().replace('CC-BY', 'CC BY')
    check_group(group, 'INV', 'I5 NOTICE 仍含 CC BY 4.0 许可',
                'CC BY 4.0' in nt_cc, '')
    # 🔴 记忆 §八：**禁止笼统写「均为 Apache-2.0」**
    check_group(group, 'INV', 'I6 NOTICE 未笼统声称「均为 Apache-2.0」',
                '并非全部为 Apache License 2.0' in nt, '')

    # ── DET：判定项（REAL 必须 PASS / BUG 必须 FAIL）──
    m = re.search(r'^# .*?v(\d+(?:\.\d+)+)', zh, re.M)
    check_group(group, 'DET', 'D1 README_zh 标题版本号 == %s' % ver,
                bool(m) and m.group(1) == ver,
                'got=%s' % (m.group(1) if m else None))

    m = re.search(r'^# .*?v(\d+(?:\.\d+)+)', en, re.M)
    check_group(group, 'DET', 'D2 README_en 标题版本号 == %s' % ver,
                bool(m) and m.group(1) == ver,
                'got=%s' % (m.group(1) if m else None))

    m = re.search(r'^Confucius4 LiveCaption v(\d+(?:\.\d+)+)', nt, re.M)
    check_group(group, 'DET', 'D3 NOTICE 首行版本号 == %s' % ver,
                bool(m) and m.group(1) == ver,
                'got=%s' % (m.group(1) if m else None))

    # 🔴🔴 **「改动说明」段缺失 = 建议项，不阻断打包**
    #    理由：章节**正文由人撰写**（脚本不能自动生成）⇒
    #    缺一节只是「客户看不到本版改了什么」的提醒，
    #    **不是**「版本标识不一致」这个缺陷类别。
    #    ⇒ 归入 ADV（只告警）⇒ 不让打包被内容问题卡死。
    #    ⇒ 但**版本身份本身**（标题 / NOTICE 首行）仍是**阻断项**（D1~D3）。
    n = len(re.findall(r'^## v%s 改动说明\s*$' % re.escape(ver), zh, re.M))
    check_group(group, 'ADV', 'D4 README_zh 有 v%s 改动说明段（恰好 1 次）' % ver,
                n == 1, 'count=%d' % n)

    n = len(re.findall(r'^## What\'s new in v%s\s*$' % re.escape(ver), en, re.M))
    check_group(group, 'ADV', 'D5 README_en 有 v%s 段（恰好 1 次）' % ver,
                n == 1, 'count=%d' % n)

    # 🔴 **关键词必须足够特异** ⇒ 旧版 README 里也出现的词不能单独当判据
    #    （否则该探针在 BUG 组里会「恒成立」而失去反证能力）。
    for kw in ('说话人识别', '按句绑定', '自适应加速', '状态信息按模块分区'):
        check_group(group, 'ADV', 'D6 README_zh 披露「%s」' % kw,
                    kw in zh, '')
    for kw in ('speaker diarization', 'bound per sentence', 'Adaptive speed-up',
               'Status information split per module'):
        check_group(group, 'ADV', 'D7 README_en 披露「%s」' % kw,
                    kw.lower() in en.lower(), '')


def main() -> int:
    ap = argparse.ArgumentParser(
        description='打包前「版本标识一致 + NOTICE 许可署名」闸门')
    ap.add_argument('--pkg', required=True, help='客户包目录（不含 .zip）')
    ap.add_argument('--expect-version', default=None,
                    help='**目标版本号**（打包流水线用）⇒ '
                         '目录名与 MANIFEST 都按它判定。'
                         '⚠️ 升版后 MANIFEST.version 尚未刷新时，'
                         '本项降级为**提醒**（由打包流水线的 '
                         'refresh_manifest() 负责修正）；'
                         '**zip 级硬断言**在 pack_v13.py 的 '
                         '_verify_and_report() 里做。')
    ap.add_argument('--json', default=None, help='证据输出路径')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg):
        print('[FAIL] 包目录不存在：%s' % pkg)
        return 2
    ver = detect_version(pkg)
    if not ver:
        print('[FAIL] 包目录名不含版本号：%s' % pkg)
        return 2
    expect = args.expect_version or ver
    print('=' * 74)
    print('app170 —— 版本标识一致 + NOTICE 许可署名 闸门')
    print('=' * 74)
    print('客户包目录：%s（version=%s，目标=%s）' % (pkg, ver, expect))

    # ── REAL 组：当前状态 ──
    run_group('REAL', pkg, expect, expect_version=expect)

    # ── BUG 组：修复前的原始文件（包外备份）──
    if not os.path.isdir(BACKUP_DIR):
        print('\n[WARN] 无修复前备份目录：%s ⇒ 跳过反证组' % BACKUP_DIR)
    else:
        tmp = tempfile.mkdtemp(prefix='app170_bug_')
        try:
            fake = make_fake_pkg(tmp, BACKUP_DIR, ver)
            run_group('BUG', fake, expect, expect_version=expect)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 74)
    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('PASS=%d / FAIL=%d / verdict=%s' % (PASS, FAIL, verdict))
    if ADVISORIES:
        print()
        print('提醒（**不阻断打包**）：')
        for n, d in ADVISORIES:
            print('  · %s %s' % (n, d))
    if FAILS:
        print()
        print('失败明细：')
        for g, n, d in FAILS:
            print('  [%s] %s  %s' % (g, n, d))
    print('=' * 74)

    out = args.json or os.path.join(HERE, 'app170_version_identity_gate_evidence.json')
    ev = {
        'script': os.path.basename(__file__),
        'pkg': pkg,
        'pkg_version': ver,
        'target_version': expect,
        'pass': PASS,
        'fail': FAIL,
        'verdict': verdict,
        'advisories': [{'name': n, 'detail': d} for n, d in ADVISORIES],
        'fails': [{'group': g, 'name': n, 'detail': d} for g, n, d in FAILS],
        'files': {},
    }
    for fn in ('README_zh.md', 'README_en.md', 'NOTICE'):
        p = os.path.join(pkg, fn)
        if os.path.isfile(p):
            import hashlib
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                h.update(f.read())
            ev['files'][fn] = {
                'bytes': os.path.getsize(p),
                'sha256': h.hexdigest(),
                'mtime': os.path.getmtime(p),
            }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('证据：%s' % out)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
