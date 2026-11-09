#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app301_rc4_readme_nums.py —— **打包前把 rc4 README 的数字改成实测值**。

## 为什么必须先改（reviewer 在 APP-073(c) 抓过同一类缺陷）

rc4 的 README **沿用了 rc3 的**「解压后 约 6.7 GB（10 474 个文件）」，
而 rc4 实际是 **9.967 GB / 10 480 个文件（进包口径）**
⇒ README 与 zip 条目数对不上 ⇒ **打进 zip 的说明书本身就是错的**。

⇒ 本脚本把 README 的数字按**实测值**定点改写（唯一命中断言），
并把「本包尚未实测峰值内存」这类**已被本轮实测推翻**的旧表述一并更新。

## 🔴 纪律
* **断链后写**（rc4 与 rc3 共享 inode ⇒ 原地写会改到 rc3！见 `_app291` 教训）。
* 每条替换都带足够上下文 ⇒ **唯一命中**。
* 写后复核：rc3 **逐字未变** ＋ rc4 命中全部新数字。

## 改哪些（每条都写明为什么）

| # | 位置 | 旧 | 新 | 依据 |
|---|---|---|---|---|
| 1 | 定位段 | 下一版「rc4 / v1.0」 | 「rc5 / v1.0」 | 本包**就是** rc4 |
| 2 | CPU | 只写 Panther Lake / 200 系列 | 补 **Meteor Lake / 100 系列** | 目标机是 **Ultra 7 155H**（Meteor Lake） |
| 3 | NPU | 「TTS 走 NPU」 | 补「**ASR 也可走 NPU**（rc4 新增）」 | rc4 补了 NPU ASR IR |
| 4 | 内存 | 「尚未实测峰值内存」 | **实测峰值 5 212.6 MB**（含 OV 编译期） | `app294` 外部采样 |
| 5 | 磁盘 | 6.7 GB / 10 474 | **约 10.0 GB / 10 480 个文件** | `app300` 清单实测（**zip 条目口径**） |
| 6 | 磁盘 | 合计留 15 GB | 缓存加 `npu_cache ≈ 0.7 GB`；**留 20 GB 以上** | `npu_cache` 实测 697 MB |
| 7 | 实测基线 | 文件数 10 474 → 10 510 | **10 474 → 10 480（zip 条目口径）** | `app300` |
| 8 | 本机基准 | 「CPU 峰值/均值 本机未采集」 | 补**实测峰值内存 5 212.6 MB** | `app294` |

用法：
    .venv/Scripts/python.exe results/app/_app301_rc4_readme_nums.py --dry-run
    .venv/Scripts/python.exe results/app/_app301_rc4_readme_nums.py --run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

HOME = os.path.expanduser('~')
RC3 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')
RC4 = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc4')
EVID = os.path.join(HERE, 'app301_rc4_readme_nums_evidence.json')

#: 🔴 进包清单实测值（`app300` 产出 ⇒ 与 zip 条目数同口径）
N_FILES_IN_PKG = 10480
PKG_GB = 10.0
N_DISK = 10510

#: 实测峰值内存（`app294` 外部采样，ASR=NPU 臂）
PEAK_MEM_MB = 5212.6

PATCHES = (
    # ① 定位段：下一版号
    ('· 正式验收（APP-066 §4）、桌面快捷方式、其余 bug 修复 → 留到下一版\n'
     '    （rc4 / v1.0）。',
     '· 正式验收（APP-066 §4）、桌面快捷方式、其余 bug 修复 → 留到下一版\n'
     '    （rc5 / v1.0）。'),
    # ② CPU：补 Meteor Lake
    ('· CPU     ：Intel Core Ultra（Panther Lake / Core Ultra 200 系列）',
     '· CPU     ：Intel Core Ultra（**Meteor Lake / 100 系列** 或\n'
     '            Panther Lake / 200 系列）'),
    # ③ NPU：补 ASR 也可走 NPU
    ('· NPU     ：Intel NPU（TTS 走 NPU）',
     '· NPU     ：Intel NPU（TTS 走 NPU；**rc4 起 ASR 也可走 NPU**）'),
    # ④ 内存：实测峰值
    ('  · 内存   ：建议 **>= 16 GB**。\n'
     '        ⚠️ 说明：APP-070 里写的「8 GB」是**磁盘**占用（首次运行的 NPU\n'
     '        编译缓存），**不是内存**。本包**尚未实测峰值内存**\n'
     '        （打包时设备被其它模块占用），所以这里给的是**保守建议**，\n'
     '        8 GB 机器可能出现内存不足（OV 编译期内存占用较高）。',
     '  · 内存   ：建议 **>= 16 GB**。\n'
     '        ⚠️ 说明：APP-070 里写的「8 GB」是**磁盘**占用（首次运行的 NPU\n'
     '        编译缓存），**不是内存**。\n'
     '        ⚠️ **rc4 已实测峰值内存**（ASR=NPU 臂，外部采样，含 OV 编译期）：\n'
     '        **%s MB**（iGPU 臂 %s MB）⇒ 8 GB 机器**会**内存不足。'
     % (('5212.6'), ('4819.5'))),
    # ⑤ 磁盘：体积 + 文件数（zip 条目口径）
    ('· 磁盘   ：解压后 **约 6.7 GB**（10 474 个文件）\n'
     '            ＋ 首次运行的编译缓存 **约 8 GB**\n'
     '               （tts_npu_cache ≈ 5 GB、ov_cache ≈ 2 GB、mt_cache ≈ 1 GB）\n'
     '            ⇒ **合计留 15 GB 以上**。',
     '· 磁盘   ：解压后 **约 %.1f GB**（%d 个文件）\n'
     '            ＋ 首次运行的编译缓存 **约 9 GB**\n'
     '               （tts_npu_cache ≈ 5 GB、ov_cache ≈ 2 GB、mt_cache ≈ 1 GB、\n'
     '                **npu_cache ≈ 0.7 GB**〔rc4 新增的 NPU ASR 编译产物〕）\n'
     '            ⇒ **合计留 20 GB 以上**。' % (PKG_GB, N_FILES_IN_PKG)),
    # ⑦ 实测基线里的文件数（zip 条目口径）
    ('    文件数 10 474 → 10 510；**包内 0 个预编译 blob**（编译缓存写用户目录）。',
     '    文件数 10 474 → **%d**（**zip 条目口径**；磁盘上 %d 个，差 %d 个是\n'
     '    `pkg_exclude` 规则排除的测试音频/示例数据）；\n'
     '    **包内 0 个预编译 blob**（编译缓存写用户目录）。'
     % (N_FILES_IN_PKG, N_DISK, N_DISK - N_FILES_IN_PKG)),
    # ⑧ 本机基准：CPU 峰值未采集 → 补实测峰值内存
    ('    · CPU 峰值/均值     **本机未采集**（打包时设备被其它模块占用）\n'
     '                        ⇒ 请在目标机按步骤 3 采一份，我们再对比。',
     '    · 峰值内存          **%s MB**（rc4 实测，ASR=NPU 臂，含 OV 编译期）\n'
     '    · CPU 峰值/均值     **本机未采集**（打包时设备被其它模块占用）\n'
     '                        ⇒ 请在目标机按步骤 3 采一份，我们再对比。'
     % PEAK_MEM_MB),
)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def unlink_then_write(p: str, data: bytes) -> None:
    tmp = p + '.app301.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()

    p4 = os.path.join(RC4, 'README_perftest.txt')
    p3 = os.path.join(RC3, 'README_perftest.txt')
    rc3_before = open(p3, 'rb').read()
    txt = open(p4, 'rb').read().decode('utf-8')

    res = {'script': os.path.basename(__file__), 'patches': [],
           'n_files_in_pkg': N_FILES_IN_PKG, 'pkg_gb': PKG_GB}
    for old, new in PATCHES:
        n = txt.count(old)
        applied = False
        if n == 1:
            txt = txt.replace(old, new, 1)
            applied = True
        res['patches'].append({'old': old.split('\n')[0][:64], 'count': n,
                               'applied': applied})

    print('== 定点替换 ==')
    for x in res['patches']:
        print('  count=%d applied=%s  %s' % (x['count'], x['applied'],
                                             x['old']))
    res['all_applied'] = all(x['applied'] for x in res['patches'])

    if args.dry_run:
        res['verdict'] = 'DRY_RUN'
        _write(res)
        return 0 if res['all_applied'] else 1

    # 🔴 断链后写 ⇒ rc3 不受影响
    unlink_then_write(p4, txt.encode('utf-8'))

    # ── 复核 ─────────────────────────────────────────────────
    rc3_after = open(p3, 'rb').read()
    new_txt = open(p4, encoding='utf-8').read()
    checks = {
        'rc3_bytes_unchanged': (rc3_before == rc3_after),
        'rc3_inode_differs': (os.stat(p4).st_ino != os.stat(p3).st_ino),
        'all_patches_applied': res['all_applied'],
        'readme_has_new_nfiles': ('%d 个文件' % N_FILES_IN_PKG) in new_txt,
        'readme_no_old_claim': ('解压后 **约 6.7 GB**（10 474 个文件）'
                                not in new_txt),
        'readme_has_peak_mem': ('%s MB' % PEAK_MEM_MB) in new_txt,
    }
    checks['pass'] = all(checks.values())
    res['checks'] = checks
    res['verdict'] = 'README_NUMS_OK' if checks['pass'] else 'README_NUMS_FAILED'
    _write(res)
    print('== 复核 ==')
    for k, v in checks.items():
        print('  %-24s %s' % (k, v))
    print('★ %s' % res['verdict'])
    return 0 if checks['pass'] else 1


def _write(obj: dict) -> None:
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    raise SystemExit(main())
