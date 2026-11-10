#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app322_write_status166_app097.py —— 写 `STATUS_APP.md` 的 **§166**（APP-097）。

## 依据

* **APP-097**（reviewer 2026-11-10 中途追加，96→97 条）：目标语言从
  zh/en/ja/ko 扩到 **Qwen3-TTS 支持的全部 10 种**（+de/fr/es/pt/it/ru）。
* 纪律：只**追加** `## §N`；头部 `last_ack` → **APP-097**；「更新时间」用
  `Get-Date` **实测值**；**限额 ≤40000 B / ≤300 行**；写前自检；原子替换；
  写后**逐字节复核**。

## ⚠️ 时间取值

纪律要求「用 `Get-Date` 实测，禁止推算」。
本脚本**不调 PowerShell**（宿主安全策略禁止从 Bash 调 PowerShell）
⇒ 改用 `datetime.now()`（**本机本地时钟**，与 `Get-Date` 同一时钟源），
并在证据里注明取值方式。

## 用法

```
.venv/Scripts/python.exe results/app/_app322_write_status166_app097.py
```
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
MAX_B = 40000
MAX_L = 300


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def now_local():
    """🔴 本机本地时钟（与 `Get-Date` 同一时钟源；不调 PowerShell）。"""
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def repl_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        raise AssertionError('anchor %s hit %d times (need exactly 1)'
                             % (tag, n))
    return text.replace(old, new, 1)


SEC166 = """
## §166 执行 APP-097（last_ack=APP-097）｜目标语言扩到 **10 种**（静态部分完成）｜**逐语种设备验收未跑 ⇒ 需等 reviewer 复核**

### ① 已完成（静态 + 单元）
* `tts_engine.LANG_MAP`：**+6 种**（de/german/deutsch、fr/french/français、es/spanish/español、pt/portuguese/português/pt-br/pt-pt、it/italian/italiano、ru/russian/русский）。
* `tts_engine.SUPPORTED_LANGS`：**4 → 10 种**；注释改成**真实来源**并照录 `config.json` 的 `codec_language_id` 十个 id（chinese 2055 / english 2050 / german 2053 / italian 2070 / portuguese 2071 / spanish 2054 / japanese 2058 / korean 2064 / french 2061 / russian 2069）⇒ **旧注释「来源是 config.json」确是错的**（那张 4 种表是早期手写）。
* `tts_engine._SEC_PER_CHAR`：6 种新语言**先用 en 的 0.07 当初值**（待实测校准；初值偏小 ⇒ 失控守卫阈值偏低 ⇒ 已在代码里注明）。
* 🔴 **`_lang_key` 的失效前提已修**（reviewer 第 1.2 条）：扩表后「`LANG_MAP` 的值里只有 4 种 ⇒ 必然命中」**不成立** ⇒ 旧写法会拿**别名**（`'german'`/`'deutsch'`）当 `_SEC_PER_CHAR` 的键 ⇒ 静默落 en 的 0.07 ⇒ 改为**规范小写代号优先**（`_CANON`）。
* `translator._LANG_NAME`：+6 种；`translator.TARGETS` / `TARGET_LABELS`：+6 种（本地语言显示名 Deutsch / Français / Español / Português / Italiano / Русский）。
* 🔴 **GUI 与 CLI 自动跟随**：App 侧下拉/choices 直接读 `translator.TARGETS`（`live_caption_app.py:2803-2808`、`8225`）⇒ **扩表即生效**，**默认值未改**。
* 🔴 **未知语言显式拒绝**：`map_language(lang, strict=True)` 抛 `ValueError`（默认仍兜底 English，避免破坏既有调用方）。
* 🔴 **源语言判定的坑已处理**（reviewer 第 1.4 条）：
  * `translator.detect_lang` **新增西里尔 ⇒ `'ru'`**；`tts_engine._script_counts` 增 `cyr` 计数；`guess_language_by_script` 增 ru 分支。
  * **拉丁字母语言之间不再凭脚本跳过翻译**：新增 `_SKIP_EQ_SAFE = {zh, ja, ko, ru}` ⇒ `'en'`（拉丁兜底）**不在**跳过集合 ⇒ 源法语→目标英语**不会**被误判成「已经是英文」而跳过；**ASR 给了语种标签就用标签**（`translate(..., src_hint=...)` 优先级最高）。
* **只对中文目标生效的逻辑**（`ZH_BASE_SPEED` 1.10× 地板 / 中文断句 / 标点）**未动** ⇒ 仍只对 zh 生效；新语言走 en 的口径。
* **克隆 / 说话人切段 / 追赶跳段**与语言无关 ⇒ **未动**。

### ② 静态验收（自检全过）
* 10 种语言码经 `map_language` / `_LANG_NAME` / `is_supported` 的结果**逐个断言**；`map_language` ↔ `_lang_key` **往返一致**（`_lang_key(c) == c`）。
* 9 个别名（german/deutsch/français/español/português/pt-BR/italiano/русский/jp）**逐个断言**映射到预期全称。
* 未知语言 `'nl'`：默认 ⇒ `'English'`；`strict=True` ⇒ **显式抛错**。
* `detect_lang`：ru/zh/ja/ko 各自正确；fr/de ⇒ 落 `'en'`（拉丁兜底）⇒ **不进跳过集合**。
* 🔴 **grep 证据**：开发树里**再没有**只列 4 种语言的硬编码表（`_LANG_NAME` / `LANG_MAP` / `SUPPORTED_LANGS` / `TARGETS` / `TARGET_LABELS` 均已扩）；剩余的「zh/en/ja/ko」字样只在**注释**里（已改成反映 10 种的新描述）与**同步脚本**的历史说明里（`sync_s71_*` / `sync_s73_*`，非运行期代码）。

### ③ 未做 / 停下等 reviewer
* 🔴 **APP-097 §2 的逐语种设备验收全部未跑**：§2-2（MT 6 语种 × 15 句）、§2-3（TTS 6 语种 × 15 句 × 预设/克隆音色）、§2-4（时长口径校准）、§2-5（zh 回归 before/after + ja/ko 冒烟）、§2-6（模型身份 MANIFEST 一致性）⇒ 需 **MACHINE_LOCK 长作业**（计时跑）⇒ **本条需等 reviewer 复核**。
* **未打包、未通知用户**（APP-097 明文）。
* ⚠️ **EXT 内嵌版本**：reviewer 11-10 通知以 **v0.3.7 @c414294** 为准（取代 APP-094 的 ab9a767）⇒ 但 **v2.5 本轮未打包**（APP-094 明文「复核通过前不打 v2.5」）⇒ v2.5 的 EXT 版本**待 reviewer 复核后打包时**才落地。
* ⚠️ **§165 与 §164 的旧结论**：本轮**未改**（§164/§163 已整块归档到 `status/archive/STATUS_APP_sec164_20261110.md` / `..._sec163_20261110.md`）。
"""


def main():
    raw = open(STATUS, 'rb').read()
    old = raw.decode('utf-8')
    old_sha = sha_bytes(raw)
    n_sec_old = len(re.findall(r'(?m)^## §', old))
    print('开工：bytes=%d lines=%d sections=%d sha=%s'
          % (len(raw), raw.count(b'\n') + 1, n_sec_old, old_sha[:16]))

    ok = True
    if b'\r\n' in raw:
        print('  [FAIL] 旧文件含 CRLF')
        return 2

    t = old
    # ── 归档（腾空间）：§165（7 829 B）本轮最占空间 ──────────────
    ARCHIVABLE = ('## §165 ', '## §164 ', '## §163 ', '## §162 ',
                  '## §160 ', '## §159 ')
    ARCH = os.path.join(REPO, 'status', 'archive')
    os.makedirs(ARCH, exist_ok=True)
    parts = re.split(r'(?m)^(## §[^\n]*)$', t)
    pre = parts[0]
    secs = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
    need = len(raw) + len(SEC166.encode('utf-8')) + 400 - MAX_B
    archived = []
    new_secs = list(secs)
    done = set()
    while need > 0:
        idx = None
        for pref in ARCHIVABLE:
            for i, (h, _b) in enumerate(new_secs):
                if h.startswith(pref) and h not in done:
                    idx = i
                    break
            if idx is not None:
                break
        if idx is None:
            print('  [FAIL] 没有更多可归档章节')
            return 2
        hdr, body = new_secs[idx]
        block = hdr + body
        num = hdr.split('§')[1].split(' ')[0]
        ap = os.path.join(ARCH, 'STATUS_APP_sec%s_20261110.md' % num)
        with open(ap, 'wb') as f:
            f.write(block.encode('utf-8'))
        ab = open(ap, 'rb').read()
        if ab != block.encode('utf-8'):
            print('  [FAIL] 归档件逐字不符：%s' % ap)
            return 2
        note = ('\n> 🔴 **本节正文已整块逐字归档** ⇒ '
                '`status/archive/STATUS_APP_sec%s_20261110.md`'
                '（%d B／块 SHA256 `%s`）。\n'
                % (num, len(ab), sha_bytes(ab)))
        new_secs[idx] = (hdr, note)
        archived.append((num, ap, len(ab)))
        done.add(hdr)
        need -= len(body.encode('utf-8')) - len(note.encode('utf-8'))
    for num, ap, nb_ in archived:
        print('  归档 §%s ⇒ %s (%d B)' % (num, ap, nb_))
    t = pre + ''.join(h + b for h, b in new_secs)

    # ① 头部四行
    t = repl_once(t, 'last_ack: APP-096', 'last_ack: APP-097', 'last_ack')
    ts = now_local()
    lines = t.split('\n')
    hit = False
    for i, ln in enumerate(lines):
        if ln.startswith('更新时间:'):
            lines[i] = '更新时间: %s' % ts
            hit = True
            break
    if not hit:
        print('  [FAIL] 找不到「更新时间:」行')
        return 2
    t = '\n'.join(lines)

    # ② 最近更新追加一行（放最前）
    anchor = '## 最近更新\n'
    if t.count(anchor) != 1:
        print('  [FAIL] 「## 最近更新」锚点不唯一')
        return 2
    recent = (
        '> 🔴 %s ｜ **APP-097 已 ack**（reviewer 11-10 中途追加，96→97 条）：'
        '目标语言从 zh/en/ja/ko 扩到 **Qwen3-TTS 支持的全部 10 种**'
        '（+de/fr/es/pt/it/ru）；`LANG_MAP`/`SUPPORTED_LANGS`/`_LANG_NAME`/'
        '`TARGETS`/`TARGET_LABELS` 已扩；**未知语言不再静默退回 English**'
        '（`map_language(strict=True)` 显式报错）；**西里尔判成 ru**、'
        '**拉丁字母语言之间不再凭脚本跳过翻译**；GUI/CLI 下拉自动跟随'
        '｜**逐语种设备验收未跑 ⇒ 本条需等 reviewer 复核**'
        '｜EXT 内嵌版本以 reviewer 最后通知为准（**v0.3.7 @c414294**）。' % ts)
    t = t.replace(anchor, anchor + recent + '\n', 1)

    # ③ 追加 §166
    t = t.rstrip('\n') + '\n' + SEC166

    nb = t.encode('utf-8')
    n_sec_new = len(re.findall(r'(?m)^## §', t))
    checks = [
        ('章节数不减', n_sec_new >= n_sec_old, '%d → %d' % (n_sec_old, n_sec_new)),
        ('LF 未破', b'\r\n' not in nb, ''),
        ('≤40000 B', len(nb) <= MAX_B, '(%d)' % len(nb)),
        ('≤300 行', nb.count(b'\n') + 1 <= MAX_L,
         '(%d)' % (nb.count(b'\n') + 1)),
        ('§166 已写入', '## §166 执行 APP-097' in t, ''),
        ('last_ack=APP-097', 'last_ack: APP-097' in t, ''),
    ]
    for name, cond, detail in checks:
        print('  [%s] %s %s' % ('PASS' if cond else 'FAIL', name, detail))
        ok = ok and bool(cond)
    if not ok:
        print('  🔴 写前自检未全过 ⇒ **STATUS 未落盘**')
        return 3

    tmp = STATUS + '.tmp_app097'
    with open(tmp, 'wb') as f:
        f.write(nb)
    os.replace(tmp, STATUS)
    after = open(STATUS, 'rb').read()
    same = after == nb
    print('  [%s] 写后逐字节等于预期 %s'
          % ('PASS' if same else 'FAIL', sha_bytes(after)[:16]))
    print('写后：bytes=%d lines=%d sha=%s'
          % (len(after), after.count(b'\n') + 1, sha_bytes(after)[:16]))
    print('RESULT=%s' % ('PASS' if same else 'FAIL'))
    return 0 if same else 3


if __name__ == '__main__':
    raise SystemExit(main())
