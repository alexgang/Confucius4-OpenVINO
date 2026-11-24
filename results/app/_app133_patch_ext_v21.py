#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：把 v2.6 交付件里的 EXT 从 **4740b06（v0.4.20）** 升到 **b2a4978（v0.4.21）**。

reviewer APP-133（2026-11-24 13:56 邮件）原文：
> reviewer 已提交并推送 **live_dub_ext b2a4978（EXT v0.4.21）**……
> **v2.6 的 EXT 改用 b2a4978**（替代 APP-131 的 4740b06）；
> 验收第 1 项 `tests/test_ext0420_clone_gender.py` 应 **16/16**；
> clone 臂请报 `stats_full.clone_reasons` 与 `n_gender_splits`。

## 纪律（沿用本项目「定点写入三件套」）

1. 备份（`%TEMP%/*.bak`）；
2. **写前**在内存新文本上跑真不变量（唯一命中断言）＋**还原式复核**；
3. 临时文件 → `os.replace` ⇒ 写后**逐字节复核**；
4. **只改字符串常量与注释**，**测试逻辑一行不改**；
5. **行尾风格不变**：用 `newline=''` 读，替换串里的 `\n` 会被
   **自动按该文件的行尾风格归一化**（避免 CRLF 文件被写成孤立 LF）。

## 改动清单（全部是「EXT commit / version」常量 ＋ 对应注释）

| 文件 | 改动 |
|---|---|
| `live_caption/_app129_build_v26.py` | `EXT_VERSION`/`EXT_COMMIT` ⇒ 0.4.21 / b2a4978 ＋ 注释追加 APP-133 |
| `live_caption/_app129_sign_accepted_v26.py` | `EXT_COMMIT` ⇒ b2a4978 ＋ ACCEPTED 描述里的版本串 |
| `results/app/_app129_run_pkg_tests.py` | `EXT_COMMIT` ⇒ b2a4978（测试**按被测版本**取） |
| `results/app/_app129_chain_v26.py` | `bgkeep_e2e.py` 取的 commit ⇒ b2a4978 ＋ 证据 json 里的 `ext_commit` |
| `results/app/_app129_clips_v26.py` | `bgkeep_e2e.py` 取的 commit ⇒ b2a4978 |
"""
from __future__ import annotations

import hashlib
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = os.environ.get('TEMP', '/tmp')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def patch(rel: str, subs):
    """subs = [(old_str, new_str, expected_count), ...]；返回 (before_sha, after_sha)。"""
    p = os.path.join(REPO, rel)
    with open(p, 'rb') as f:
        src_b = f.read()
    with open(p, 'r', encoding='utf-8', newline='') as f:
        src = f.read()

    crlf = '\r\n' in src
    bak = os.path.join(TMP, os.path.basename(rel) + '.bak_app133')
    with open(bak, 'wb') as f:
        f.write(src_b)

    def norm(s: str) -> str:
        """把模式里的 \n 归一化成该文件的行尾风格。"""
        return s.replace('\r\n', '\n').replace('\n', '\r\n') if crlf else s

    out = src
    for old, new, cnt in subs:
        o, nw = norm(old), norm(new)
        c = out.count(o)
        if c != cnt:
            raise SystemExit('FAIL %s：命中 %d 次（要求 %d）：%r'
                             % (rel, c, cnt, old[:80]))
        out = out.replace(o, nw)

    # ── 真不变量（写前，在内存文本上）────────────────────────────
    if (('\r\n' in src) != ('\r\n' in out)):
        raise SystemExit('FAIL %s：行尾风格变了' % rel)
    # 行数变化量必须**恰好**等于各替换片段带来的增量之和
    #（纯常量替换 = 0 行；追加注释块 = 正数）⇒ 防止「多删/少插一行」
    delta_expect = 0
    for old, new, cnt in subs:
        delta_expect += cnt * (norm(new).count('\n') - norm(old).count('\n'))
    delta_got = out.count('\n') - src.count('\n')
    if delta_got != delta_expect:
        raise SystemExit('FAIL %s：行数增量 %d ≠ 预期 %d'
                         % (rel, delta_got, delta_expect))
    # 还原式复核：把新片段换回旧片段 ⇒ 必须逐字节等于原文
    red = out
    for old, new, cnt in subs:
        o, nw = norm(old), norm(new)
        if nw not in red:
            raise SystemExit('FAIL %s：新片段找不到（还原式复核前提失败）' % rel)
        red = red.replace(nw, o)
    if red != src:
        raise SystemExit('FAIL %s：还原式复核失败（还原后 != 原文）' % rel)

    # ── 写盘：临时文件 → os.replace（不截断原文件）────────────────
    out_b = out.encode('utf-8')
    tmp = p + '.tmp_app133'
    with open(tmp, 'wb') as f:
        f.write(out_b)
    os.replace(tmp, p)
    with open(p, 'rb') as f:
        after = f.read()
    if after != out_b:
        raise SystemExit('FAIL %s：写后逐字节复核失败' % rel)
    print('OK  %-46s %d B -> %d B  sha %s -> %s'
          % (rel, len(src_b), len(out_b), sha256_bytes(src_b)[:12],
             sha256_bytes(after)[:12]))
    return sha256_bytes(src_b), sha256_bytes(after)


ADD133 = """#:
#: 🔴🔴 **APP-133**（reviewer 2026-11-24 13:56 邮件）：EXT **再升到**
#:   **b2a4978（v0.4.21）**——按音高把男女混在一起的段切开（音乐下 8 s 硬切
#:   会跨换人）；`stats_full` 新增 `clone_reasons` / `spk_reason_hist` /
#:   `n_gender_splits`；可选 `EXT_BG_DUMP_VOCALS` 落盘分离人声。
#:   ⇒ **b2a4978 替代 4740b06**（v0.4.20 是中间产物，不再交付）。"""


def main():
    results = []

    # ── ① 构建脚本 ────────────────────────────────────────────────
    anchor = "#:   ⇒ 本包（v2.6）**只出这一版**（v0.4.19 的中间产物不再交付）。"
    results.append(patch('live_caption/_app129_build_v26.py', [
        ("EXT_VERSION = '0.4.20'", "EXT_VERSION = '0.4.21'", 1),
        ("EXT_COMMIT = '4740b06'", "EXT_COMMIT = 'b2a4978'", 1),
        (anchor, anchor + "\n" + ADD133, 1),
    ]))

    # ── ② 签 ACCEPTED ─────────────────────────────────────────────
    results.append(patch('live_caption/_app129_sign_accepted_v26.py', [
        ("EXT_COMMIT = '4740b06'", "EXT_COMMIT = 'b2a4978'", 1),
        ("EXT v0.4.19 (3573b2d) + Demucs",
         "EXT v0.4.21 (b2a4978) + Demucs", 1),
    ]))

    # ── ③ 包内离线测试 ───────────────────────────────────────────
    results.append(patch('results/app/_app129_run_pkg_tests.py', [
        ("EXT_COMMIT = '4740b06'", "EXT_COMMIT = 'b2a4978'", 1),
    ]))

    # ── ④ 整链（e2e 工具按 commit 取）─────────────────────────────
    results.append(patch('results/app/_app129_chain_v26.py', [
        ("'4740b06:tools/bgkeep_e2e.py'", "'b2a4978:tools/bgkeep_e2e.py'", 1),
        ("'ext_commit': '4740b06'", "'ext_commit': 'b2a4978'", 2),
    ]))

    # ── ⑤ 抽听样片 ───────────────────────────────────────────────
    results.append(patch('results/app/_app129_clips_v26.py', [
        ("'4740b06:tools/bgkeep_e2e.py'", "'b2a4978:tools/bgkeep_e2e.py'", 1),
    ]))

    print('--- 全部 %d 个文件改完 ---' % len(results))


if __name__ == '__main__':
    main()
