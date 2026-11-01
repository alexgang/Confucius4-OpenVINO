#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app221 —— APP-061：**建 v2.2 客户包目录 + 同步本轮改动 + 重签 ACCEPTED**。

## 🔴🔴🔴 纪律（APP-055 / APP-061）

1. **v2.1 目录与 zip 一个字节都不许改** ⇒ 本脚本**只读** v2.1，
   **另建** `Confucius4_LiveCaption_v2.2`。
2. **不整目录覆盖**：仓库 `live_caption/` 与客户包 `app/` 是两份独立副本
   ⇒ 本脚本**只写「本轮改过的那几个文件」**（逐文件定点替换），
   **不是**整目录 rsync。
3. **行尾归一**：仓库工作区是 CRLF（`core.autocrlf=true`），
   客户包是 LF ⇒ 写进包里的文件**一律归一化成 LF**
   （否则包内文件与仓库 blob 逐字节不同 ⇒ app191 指纹口径不一致）。
4. **ACCEPTED 必须重签**（按新代码算指纹）⇒ 否则 zip 内那一份仍绑旧代码
   （APP-052 ② 的教训：R5 必 FAIL）。

## 做法

* `models/`、`python/`（12 GB + 835 MB）⇒ **硬链接**（零拷贝、只读使用）
* `app/`、`ext/`、`docs/`、`results/` 与根文件 ⇒ **真实复制**
* 本轮改过的生产模块 ⇒ 从仓库 `live_caption/` **定点覆盖**（行尾归一 + 逐字节复核）

用法：
    python app221_app061_v22_build.py --src "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.1" \
        --dst "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.2" \
        --json results/app/app221_app061_v22_build_evidence.json
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pkg_exclude  # noqa: E402

#: 🔴🔴🔴 **本轮（APP-061）改过的生产模块**（只同步这几个！）
#:   ⚠️ **只列「本轮真的改过」的文件** ⇒ 不整目录覆盖（铁律）。
CHANGED_MODULES = [
    'live_caption_app.py',      # ①④⑤ GUI 传 clone / is_new / 定时采集停用 / ⑥ 紧凑化
    'tts_worker.py',            # ① CUDA 音色 / ④ / ⑤c 沿用上一句 / ③b③c 预缓冲+倍速封顶
    'tts_service.py',           # ③a 句内欠载累计（uf_* 统计）
]

#: **硬链接**（零拷贝）的子目录（**只读使用** ⇒ 不会被本脚本改动）
HARDLINK_DIRS = ['models', 'python']

#: **真实复制**的子目录
COPY_DIRS = ['app', 'ext', 'docs', 'results']

#: 根级文件（真实复制）
ROOT_FILES = [
    'README_zh.md', 'README_en.md', 'README_插件.md', 'NOTICE',
    'THIRD_PARTY.md', 'Start_LiveCaption.bat', 'Diagnose.bat',
    'release.json', 'ACCEPTED.json',
]

#: reviewer 明确要求的改动白名单（写进 ACCEPTED.waived_changes）
ACCEPTED_WAIVED = {
    'live_caption_app.py': {
        'reason': 'APP-061 ①：GUI 构造 TTSService 时补传 clone=（原来漏传 ⇒ '
                  'worker 的 clone_mode=False ⇒ 每句回落预设 A ⇒ 「男声被女声播出」）；'
                  'APP-061 ④：停用定时克隆采集器（CloneCollector）⇒ 克隆只走'
                  '「按句绑定 + is_new 取样」；APP-061 ④b：_retry_spk_labels 补登记'
                  'is_new（新说话人才会被取样）；APP-061 ⑤d：旁路关闭且选「跟随说话人」'
                  '时给出明确提示（不静默退回定时克隆）；'
                  'APP-061 ②：CUDA 选项检测不到边车环境时置灰并显示原因；'
                  'APP-061 ③a：GUI 会话日志每 30 s 打一行遥测；'
                  'APP-061 ③d：MT/ASR 与 TTS 同在 NPU 时标黄提示；'
                  'APP-061 ⑥：GUI 紧凑化（控件 ≤ 2 行 +「高级」折叠面板 + '
                  '三个分区说明行并进状态条 + 字幕区 ≥ 70 % 窗口高 + 最小宽 1024）',
        'source': 'APP-061 ①④⑤②③(a)(d)⑥（reviewer 明文要求）',
    },
    'tts_worker.py': {
        'reason': 'APP-061 ①：CUDA 分支同时缓存 _preset_name（原来只缓存 '
                  '_preset_ref_path ⇒ 回落把 speaker_name 清空 ⇒ 每句报'
                  '「没有可用的音色」⇒ CUDA 全程无声）；回落路径在 CUDA 下'
                  '只换参考音频、不清空音色名；synth() 的音色检查对 USES_REF_AUDIO '
                  '后端改为查「当前有没有参考音频」；'
                  'APP-061 ⑤c：标签未到时若已有克隆音色则沿用上一句（keep_last）'
                  '（用户方案 A 允许）；'
                  'APP-061 ③a：逐句遥测新增 uf_in_sentence/uf_idle/uf_total_ms；'
                  'APP-061 ③b：预缓冲公式改为 est_dur × (1 − 1/(r·speed))；'
                  'APP-061 ③c：倍速动态封顶 speed ≤ 1/r_recent（用户 1.30× 上限不变）',
        'source': 'APP-061 ①⑤(c)③(a)(b)(c)（reviewer 明文要求）',
    },
    'tts_service.py': {
        'reason': 'APP-061 ③a：主进程侧累计「句内欠载总时长（ms）」「句间空闲」'
                  '与「句内欠载 = 0 的句数」⇒ 供 30 s 遥测行与验收'
                  '（「uf_in_sentence_ms 总和 ≤ 音频总时长的 0.5 %」、'
                  '「≥ 95 % 的句子为 0」）',
        'source': 'APP-061 ③(a)（reviewer 明文要求）',
    },
}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def norm_bytes(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def copy_tree(src, dst):
    """真实复制（保留 mtime）。

    🔴🔴 **必须连 `__pycache__` 一起复制**（本轮实测踩到的坑）：
      `pack_v13.py` 的排除规则**保留** `python/**/__pycache__`
      （包内 Python 恒为 3.12 ⇒ 留着 .pyc 能省首次启动 1~5 s）
      ⇒ 复制时若跳过 `__pycache__` ⇒ v2.2 包会**少 3 519 个 .pyc**
      ⇒ 与 v2.1 的包内容**不一致**（首次启动变慢）⇒ 必须复制。
    """
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt = dst if rel == '.' else os.path.join(dst, rel)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            t = os.path.join(tgt, f)
            if os.path.exists(t):
                os.chmod(t, 0o666)
                os.remove(t)
            shutil.copy2(s, t)


def link_tree(src, dst):
    """硬链接（零拷贝）；已存在同名文件则跳过。

    🔴 **`__pycache__` 也链**（与 `copy_tree` 同口径）⇒ 包内容与 v2.1 一致。
    ⚠️ 硬链接的文件若被**原地改写**会同时影响 v2.1
      ⇒ 只对**运行时只读**的目录用（`models/` `python/`）
      ⇒ Python 写 .pyc 用「临时文件 + os.replace」⇒ **不会原地改写** ⇒ 安全。
    """
    n = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt = dst if rel == '.' else os.path.join(dst, rel)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            t = os.path.join(tgt, f)
            if os.path.exists(t):
                continue
            try:
                os.link(s, t)
                n += 1
            except OSError:
                shutil.copy2(s, t)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='源包目录（v2.1，只读）')
    ap.add_argument('--dst', required=True, help='目标包目录（v2.2）')
    ap.add_argument('--json', default=os.path.join(
        HERE, 'app221_app061_v22_build_evidence.json'))
    ap.add_argument('--sync-only', action='store_true',
                    help='**只**做「定点同步 + 重签 ACCEPTED」（不建目录、不复制）'
                         '⇒ 用于打包前再改一两个文件时')
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    dst = os.path.abspath(a.dst)
    dev = os.path.join(REPO, 'live_caption')

    if os.path.abspath(src) == dst:
        print('!! 源目录与目标目录相同 ⇒ 拒绝（v2.1 一个字节都不能动）')
        return 2
    if os.path.exists(dst) and not a.sync_only:
        print('!! 目标目录已存在：%s' % dst)
        print('   （本脚本只建**新**版本目录；已有目录请人工确认后再处理）')
        return 2

    t0 = time.time()
    print('=' * 70)
    print('app221 —— 建 v2.2 包目录')
    print('  源（只读）:', src)
    print('  目标      :', dst)
    print('=' * 70)

    os.makedirs(dst, exist_ok=True)
    if a.sync_only:
        print('[sync-only] 只做「定点同步 + 重签 ACCEPTED」')
    ev = {'tool': 'app221', 'app': 'APP-061', 'src': src, 'dst': dst,
          'started_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'hardlink_dirs': HARDLINK_DIRS, 'copy_dirs': COPY_DIRS,
          'root_files': ROOT_FILES, 'changed_modules': CHANGED_MODULES,
          'synced': []}

    for d in ([] if a.sync_only else COPY_DIRS):
        s = os.path.join(src, d)
        if not os.path.isdir(s):
            print('  [skip] 源里没有 %s' % d)
            continue
        copy_tree(s, os.path.join(dst, d))
        print('  [copy] %s/ 完成' % d)

    for d in ([] if a.sync_only else HARDLINK_DIRS):
        s = os.path.join(src, d)
        if not os.path.isdir(s):
            print('  [skip] 源里没有 %s' % d)
            continue
        n = link_tree(s, os.path.join(dst, d))
        print('  [link] %s/ 硬链接 %d 个文件（零拷贝）' % (d, n))

    for f in ([] if a.sync_only else ROOT_FILES):
        s = os.path.join(src, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
            print('  [copy] %s' % f)

    # ── **完整性闸门**：包内文件集合必须与源包**一致** ─────────────
    #   🔴 本轮实测踩到的坑：复制时跳过了 `__pycache__`
    #      ⇒ v2.2 少了 3 519 个 .pyc（`pack_v13.py` 的排除规则**保留**
    #        `python/**/__pycache__` ⇒ 少它们 ⇒ 客户首次启动要多编译 1~5 s）
    #      ⇒ 而且「内容一致性校验」**查不出来**（zip ⇄ 包目录是自洽的）
    #      ⇒ 必须**与源包逐名比对**才算数。
    def _names(root):
        out = set()
        for r, _d, fs in os.walk(root):
            for n in fs:
                out.add(os.path.relpath(os.path.join(r, n), root))
        return out

    src_names = _names(src)
    dst_names = _names(dst)
    missing = sorted(src_names - dst_names)
    ev['missing_vs_src'] = missing[:50]
    ev['n_missing_vs_src'] = len(missing)
    ev['n_src_files'] = len(src_names)
    ev['n_dst_files'] = len(dst_names)
    if missing:
        print('🔴🔴 **完整性闸门 FAIL**：包内缺 %d 个源包有的文件！'
              % len(missing))
        for m in missing[:10]:
            print('   -', m)
        print('   ⇒ **不继续**（否则会打出与源包内容不一致的包）')
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        return 4
    print('  [gate] 完整性闸门 PASS：包内 %d 个文件 = 源包 %d 个（无缺失）'
          % (len(dst_names), len(src_names)))

    # ── 定点同步本轮改动的生产模块 ─────────────────────────────
    print('\n-- 同步本轮改动的生产模块（行尾归一 LF + 逐字节复核）--')
    for name in CHANGED_MODULES:
        sp = os.path.join(dev, name)
        tp = os.path.join(dst, 'app', name)
        if not os.path.isfile(sp):
            print('  !! 仓库里没有 %s ⇒ 中止' % name)
            return 3
        raw = open(sp, 'rb').read()
        data = norm_bytes(raw)
        before = sha256_file(tp) if os.path.isfile(tp) else None
        tmp = tp + '.app221_tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        back = open(tmp, 'rb').read()
        assert back == data, '写后逐字节复核失败：%s' % name
        os.replace(tmp, tp)
        after = sha256_file(tp)
        rec = {'module': name, 'bytes': len(data),
               'sha256': after,
               'sha256_before': before,
               'crlf_in_repo': raw.count(b'\r\n'),
               'normalized_to': 'LF'}
        ev['synced'].append(rec)
        print('  [sync] %-22s %8d B  sha256=%s…（原 %s…）'
              % (name, len(data), after[:12], (before or '-')[:12]))

    # ── 重签 ACCEPTED.json（按新代码算指纹）──────────────────────
    print('\n-- 重签 ACCEPTED.json --')
    pkg_app = os.path.join(dst, 'app')
    mods = [n for n in sorted(os.listdir(pkg_app))
            if n.endswith('.py') and not pkg_exclude.is_app_dev_only('app/' + n)]
    per = {}
    h = hashlib.sha256()
    for n in mods:
        with open(os.path.join(pkg_app, n), 'rb') as f:
            d = norm_bytes(f.read())
        per[n] = hashlib.sha256(d).hexdigest()
        h.update(n.encode('utf-8'))
        h.update(b'\0')
        h.update(hashlib.sha256(d).digest())
    fp = h.hexdigest()

    home = os.path.expanduser('~')
    try:
        rel = os.path.relpath(dst, home)
    except ValueError:
        rel = None
    pkg_dir_rec = ('<HOME>\\' + rel.replace(os.sep, '\\')
                   if rel and not rel.startswith('..') else dst)

    ver = '2.2'
    payload = {
        'accepted': True,
        'version': ver,
        'pkg_dir': pkg_dir_rec,
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'corrections': ['APP-043', 'APP-045', 'APP-048', 'APP-051', 'APP-052',
                        'APP-053', 'APP-054', 'APP-055', 'APP-056', 'APP-057',
                        'APP-058', 'APP-061'],
        'binding_gate': 'app191',
        'code_fingerprint': fp,
        'code_fingerprint_alg': (
            'app191.package_fingerprint：SHA256 over（文件名 + NUL + '
            'SHA256(归一化行尾后的模块字节)），按文件名排序；'
            '范围 = 包内 app/ 的**生产模块**'
            '（排除 pkg_exclude.is_app_dev_only）'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'waived_changes': ACCEPTED_WAIVED,
        'scope': '链路 + 结构 + 数字自洽；**音质/不变调/可懂由用户实听与 '
                 'reviewer 判定**',
        'pending_reviewer': [
            'APP-061 ①⑤：GUI 实机复测（CUDA 音色 A / 跟随说话人，各前 5 分钟）'
            '⇒ 「没有可用的音色」0 次、REQ 数 = 提交句数',
            'APP-061 ③：SPE 前 5 分钟实测 uf_in_sentence_ms 总和 ≤ 音频时长 0.5 %'
            '、ASR RTF 增量 ≤ +0.10、丢句 0',
            'APP-061 ③(e)：CPU 卸载候选的 A/B（改默认摆放须先报主会话）',
            'APP-061 D1–D4：旁路窗口时长 / 是否自动开旁路 / 客户包是否保留 '
            'CUDA 选项 / NPU 共用是警告还是禁止 ⇒ **待用户/reviewer 决定**',
        ],
    }
    acc_path = os.path.join(dst, 'ACCEPTED.json')
    tmp = acc_path + '.app221_tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    back = json.load(open(tmp, encoding='utf-8'))
    assert back['code_fingerprint'] == fp, '写后指纹不一致'
    assert back['version'] == ver
    os.replace(tmp, acc_path)
    print('  [accepted] 已重签（%d B）code_fingerprint=%s…（%d 个生产模块）'
          % (os.path.getsize(acc_path), fp[:12], len(mods)))

    ev.update({'code_fingerprint': fp, 'n_production_modules': len(mods),
               'accepted_bytes': os.path.getsize(acc_path),
               'accepted_sha256': sha256_file(acc_path),
               'elapsed_s': round(time.time() - t0, 1)})
    with open(a.json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n证据已写:', a.json)
    print('耗时 %.1f s' % ev['elapsed_s'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
