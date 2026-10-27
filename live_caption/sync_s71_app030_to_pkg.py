#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s71_app030_to_pkg.py —— 把 APP-030（日文失控）同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换块**从 git 自动派生**（不手抄任何代码）⇒ 抄错的风险归零；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 写盘时**保留包内原有的换行风格**。

## 本轮要同步的变更（APP-030 + APP-029 文案）

`app/tts_engine.py`：
① 新增 `LANG_MAP` / `SUPPORTED_LANGS` / `map_language()` / `language_supported()`
   （APP-030① 的**唯一**语言映射表：zh/en/ja/ko → Chinese/English/Japanese/Korean）；
② 新增 `guess_language()` / `guess_language_by_script()` / `_script_counts()`
   （**假名 ⇒ ja**、**谚文 ⇒ ko**、汉字占比 ≥25% ⇒ zh）；
③ 新增 `estimate_frames()` / `estimate_sec()` / `clamp_max_new_tokens()`
   （APP-030②：`clamp(3×估计帧+36, 48, 2048)`）；
④ 新增 `runaway_threshold_s()`（APP-030②：`max(3×估计, 估计+8 s)`）；
⑤ `stream()` 新增 `max_new_tokens` / `est_sec` 透传（**只收紧不放宽**）；
⑥ `_estimate_sec()` **补假名/谚文**计数（APP-030④：旧实现日文恒估 0.4 s）。

`app/tts_worker.py`：
⑦ `synth()` 接收 `lang`；命令协议/合成队列加 `lang`（APP-030①）；
⑧ `_synth_babelvox()` 用 `map_language()`；`normalize_zh_numbers` **只在 Chinese**；
   每段传 `clamp_max_new_tokens()`；
⑨ `_guess_lang()` 改为复用 `guess_language_by_script()`（旧实现只分 zh/en）；
⑩ **第三道闸**：worker 侧引擎无关的 RUNAWAY 兜底；
⑪ **APP-030⑤ 遥测**：逐句 `lang/lang_src/n_chars/est_frames/frames/end_reason`；
⑫ **APP-030⑤ 异常句落盘**：`%LOCALAPPDATA%\\...\\tts_anomaly`（最多 20 个）；
⑬ **APP-029**：`spk_update` 命令（接口预留）+ pyannote 只做说话人识别的文案。

`app/tts_service.py`：
⑭ `submit()` 接受并下传 `lang`（APP-030①）；
⑮ **APP-029**：`spk_update()` 方法（接口预留）。

`app/live_caption_app.py`：
⑯ GUI `_pump_tts()` 与 CLI 两处 `tts.submit(..., lang=...)`（APP-030①）；
⑰ **APP-029**：`_on_mt_changed()` 记一行会话日志（APP-030⑤）；
⑱ **APP-029**：`_split_spk()` 的 docstring 改成新口径（不再断句）。

`app/translator.py`：
⑲ **APP-029**：`spk/spk_conf` 的 docstring 改成新口径（**只透传、不使用**）。

`app/tts_cuda.py`：
⑳ `_q_get()` 超时**返回哨兵**（不再抛）⇒ 看门狗按设计生效、第 0 句不再丢（APP-030③）；
㉑ `generate_stream()` 下发 `max_new_tokens` + 客户端 **RUNAWAY** 判定（APP-030②）；
㉒ `_cancel_request()`（发 `cancel` ⇒ 不行就杀并重启边车）；
㉓ 边车回报 `frames` / `end_reason`（APP-030⑤）。

`app/tts_cuda_sidecar.py`：
㉔ 接受并使用 `max_new_tokens`（旧实现**从不传** ⇒ 库默认 2048 = 163.8 s 音频）；
㉕ 回报实际帧数与结束原因（`eos` / `cap`）；
㉖ 支持 `cancel` 命令（每块检查一次）。

## 基线 commit

🔴 **不能用 `HEAD`** —— 本轮提交后 HEAD 就是新版本 ⇒ 无法派生替换块。
⇒ 用**同步前的固定 commit** `7109c77`
   （= ASR §46/§47 提交；`tts_worker.py` / `tts_service.py` / `tts_cuda.py` /
     `tts_cuda_sidecar.py` / `tts_engine.py` / `live_caption_app.py` /
     `translator.py` 在包内与之**逐字一致** —— 已用 SHA256 逐文件核对过）。

## 用法

    python live_caption/sync_s71_app030_to_pkg.py --check   # 只查差异
    python live_caption/sync_s71_app030_to_pkg.py            # 同步
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s71')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
TARGETS = [
    ('live_caption/tts_engine.py', 'app/tts_engine.py'),
    ('live_caption/tts_worker.py', 'app/tts_worker.py'),
    ('live_caption/tts_service.py', 'app/tts_service.py'),
    ('live_caption/tts_cuda.py', 'app/tts_cuda.py'),
    ('live_caption/tts_cuda_sidecar.py', 'app/tts_cuda_sidecar.py'),
    ('live_caption/live_caption_app.py', 'app/live_caption_app.py'),
    ('live_caption/translator.py', 'app/translator.py'),
]

# 🔴 **同步前的固定 commit**（不是 HEAD！见模块 docstring）
BASE_COMMIT = '7109c77'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(b: bytes) -> bytes:
    """归一化换行（CRLF/CR → LF）⇒ 比对与派生都用它。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _detect_eol(b: bytes) -> bytes:
    """探测原文件的换行风格（\\r\\n 还是 \\n）。"""
    return b'\r\n' if b'\r\n' in b else b'\n'


def _git_show(commit: str, rel: str) -> bytes:
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show %s:%s 失败: %s'
                           % (commit, rel, r.stderr.decode('utf-8', 'replace')))
    return r.stdout


def _pkg_dirs():
    """自动发现最大版本客户包目录（🔴 目录名可能有 `_bak_日期` 后缀
    ⇒ 必须用正则取版本号，不能用 `rsplit('_v',1)[1]`）。"""
    out = []
    for name in os.listdir(HOME):
        p = os.path.join(HOME, name)
        if not os.path.isdir(p):
            continue
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)(?:\.\d+)*$', name)
        if m:
            out.append((int(m.group(1)), name, p))
    out.sort()
    return out


def _derive_blocks(old: bytes, new: bytes):
    """用 difflib 从「同步前 → 同步后」派生替换块（含上下文 ⇒ 唯一命中）。

    🔴🔴 **必须用 `get_grouped_opcodes(n=3)`**（带上下文），
    不能用裸 `get_opcodes()`：
      裸 opcodes 里「纯新增块」的 old 部分是**空串** ⇒
      `text.count('')` = len(text)+1 ⇒ 报「命中 161148 次」⇒ 误导性失败。
    ⇒ 带上下文后，每块都含**前后各若干行公共上下文** ⇒ 可唯一定位。
    """
    old_lines = _norm(old).decode('utf-8').splitlines(keepends=True)
    new_lines = _norm(new).decode('utf-8').splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for group in sm.get_grouped_opcodes(n=3):
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]
        old_b = ''.join(old_lines[i1:i2])
        new_b = ''.join(new_lines[j1:j2])
        if old_b == new_b:
            continue
        blocks.append((old_b, new_b))
    return blocks


def _apply(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise AssertionError('期望恰好命中 1 次，实际 %d 次 ⇒ 块无法唯一定位' % n)
    return text.replace(old, new)


def sync_one(repo_rel: str, pkg_rel: str, pkg_root: str, check_only: bool,
             prev_commit: str = None, base_from_disk: bool = False):
    src = os.path.join(REPO, repo_rel.replace('/', os.sep))
    dst = os.path.join(pkg_root, pkg_rel.replace('/', os.sep))
    if not os.path.isfile(src):
        return ('SKIP', repo_rel, '仓库文件不存在')
    if not os.path.isfile(dst):
        return ('SKIP', repo_rel, '包内文件不存在: %s' % dst)

    with open(src, 'rb') as f:
        cur = f.read()
    with open(dst, 'rb') as f:
        disk = f.read()

    if _norm(disk) == _norm(cur):
        return ('ALREADY', repo_rel, '已与仓库一致，无需同步')

    # 🔴🔴 **基线选择**（三种模式，优先级从高到低）：
    #   ① `--base-from-disk`：**以包内当前内容为基线**（增量同步用）
    #      —— 上一轮同步已写盘 ⇒ 包内不再是任何 git commit 的内容
    #      ⇒ 只能用包内自身当基线。
    #      ⚠️ **安全性不降级**：仍然是 difflib 自动派生 + 唯一命中断言
    #        + 替换后与仓库版逐字一致才写盘。
    #   ② `--prev-commit`：上一轮同步后的 commit（**中间版本**已入库时用）。
    #   ③ `BASE_COMMIT`：首次同步用。
    #   ⚠️ 基线必须**逐字等于包内当前内容**，否则派生块对不上
    #   ⇒ 不匹配就**拒绝派生**（不许盲改）。
    base = None
    base_desc = ''
    if base_from_disk:
        base = disk
        base_desc = '包内当前内容（--base-from-disk）'
    else:
        for cand in ([prev_commit] if prev_commit else []) + [BASE_COMMIT]:
            if not cand:
                continue
            b = _git_show(cand, repo_rel)
            if _norm(b) == _norm(disk):
                base = b
                base_desc = cand
                break
        if base is None:
            return ('FAIL', repo_rel,
                    '基线 %s / %s 均与包内当前内容不一致 ⇒ 拒绝派生'
                    '（包可能被手工改过；如确为增量同步请加 --base-from-disk）'
                    % (prev_commit or '-', BASE_COMMIT))

    blocks = _derive_blocks(base, cur)
    if not blocks:
        return ('FAIL', repo_rel, '无法从基线派生替换块')

    eol = _detect_eol(disk)
    text = _norm(disk).decode('utf-8')
    applied = 0
    for old_b, new_b in blocks:
        try:
            text = _apply(text, old_b, new_b)
            applied += 1
        except AssertionError as e:
            return ('FAIL', repo_rel, '块 %d 未唯一命中: %s' % (applied, e))
    out = text.replace('\n', eol.decode('utf-8')).encode('utf-8')

    # 🔴 写盘前必须与仓库版逐字一致（归一化换行）
    if _norm(out) != _norm(cur):
        return ('FAIL', repo_rel, '替换后与仓库版不一致 ⇒ 中止写盘')

    if check_only:
        return ('DIFF', repo_rel, '%d 块待同步（未写盘，--check）' % applied)

    # 备份（包外）
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(dst, os.path.join(BACKUP_DIR, os.path.basename(dst)))

    tmp = dst + '.s71tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    return ('SYNCED', repo_rel,
            '%d 块；sha %s → %s（%d → %d B）'
            % (applied, _sha(disk)[:16], _sha(out)[:16], len(disk), len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    ap.add_argument('--prev-commit', default=None,
                    help='上一轮同步后的 commit（增量同步用；'
                         '默认尝试 BASE_COMMIT）')
    ap.add_argument('--base-from-disk', action='store_true',
                    help='以**包内当前内容**为基线做增量同步'
                         '（上一轮已写盘 ⇒ 包内不再是任何 commit 的内容）。'
                         '⚠️ 安全性不降级：仍走 difflib 自动派生 + 唯一命中断言 '
                         '+ 写盘前与仓库版逐字一致校验。')
    args = ap.parse_args()

    dirs = _pkg_dirs()
    if not dirs:
        print('!! 找不到客户包目录')
        return 1
    ver, name, root = dirs[-1]
    print('客户包目录: %s（v%d）' % (root, ver))
    if args.base_from_disk:
        print('基线: 包内当前内容（--base-from-disk）')
    else:
        print('基线 commit: %s' % BASE_COMMIT)
        if args.prev_commit:
            print('增量基线: %s' % args.prev_commit)
    print('备份目录（包外）: %s' % BACKUP_DIR)
    print('-' * 70)

    rc = 0
    for repo_rel, pkg_rel in TARGETS:
        st, rel, msg = sync_one(repo_rel, pkg_rel, root, args.check,
                                args.prev_commit,
                                base_from_disk=args.base_from_disk)
        print('[%s] %s — %s' % (st, rel, msg))
        if st == 'FAIL':
            rc = 1
    print('-' * 70)
    print('结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
