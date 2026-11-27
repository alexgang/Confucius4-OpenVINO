r"""_app249_sync_pkg_to_dev.py —— 把 **包内**已修好的 4 处**定点回灌**到 dev 树（§249 发现的真缺陷）。

## 为什么必须回灌（§249）

包 `LiveCaption_MiniMVP_v1.2.1` 里已经带了 **APP-153 §3／§5 的修复**：
GUI 标题 v1.2.1、`--check` 里的中性措辞、开发机路径脱敏、黑名单正则泛化。
但 **dev 树 `live_caption/` 里没有** ⇒
**下一次打包时（`_app151_sync_app_py.py` / `pack_v13.py` 都是 dev → 包）这些修复会全部丢失**。

🔴 这与 §234 修掉的缺陷**同类**：「§233 的修法没接进生产路径」。
本轮 §248 把修复只写进了**包副本**，没写进**生产路径（dev 树）**。

## 做法（**精确字符串替换 + 唯一命中断言**，不做整目录覆盖）

* 逐个文件：读 dev 版与包版 ⇒ 算出「包侧多出来的替换块」；
* 每个替换块在 dev 里**必须唯一命中**（`count == 1`）⇒ 否则**中止不改**；
* 写前备份 ＋ 写后**逐字节复核** ＋ `ast.parse`（.py 必须仍可解析）；
* **行尾风格不变**（dev 原样保留 ⇒ 只改内容不动行尾）。

## 纪律

* **只动 dev 树的 4 个文件**，不动包、不动客户 zip；
* 逐文件记录替换块与唯一命中证据 ⇒ `results/app/app249_pkg_to_dev_sync.json`。
"""

from __future__ import annotations

import ast
import difflib
import io
import json
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
PKG = r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1\app'
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_pkg_to_dev_sync.json')
BAKDIR = r'C:\Users\Trekker-PTL\shared\app249_desen_backup'

#: 只回灌这 4 个（其余 app/*.py 与 dev 逐字节一致）
FILES = ['live_caption_app.py', 'device_config.py',
         'asr06b_stateful_backend.py', 'v23_preset_only.py']


def log(m):
    print(m, flush=True)


def eol(b):
    crlf = b.count(b'\r\n')
    return crlf, b.count(b'\n') - crlf


def main():
    rows = []
    all_ok = True
    for fname in FILES:
        dp = os.path.join(DEV, fname)
        pp = os.path.join(PKG, fname)
        if not (os.path.isfile(dp) and os.path.isfile(pp)):
            log('  [跳过] 缺文件：%s' % fname)
            continue
        db = open(dp, 'rb').read()
        pb = open(pp, 'rb').read()
        if db == pb:
            log('  [相同] %s（dev 与包逐字节一致）' % fname)
            rows.append({'file': fname, 'status': 'identical'})
            continue

        d_text = db.decode('utf-8')
        p_text = pb.decode('utf-8')
        # 包侧相对 dev 的「替换块」：取包版的行 ⇒ 必须在 dev 里唯一命中
        d_lines = d_text.splitlines(keepends=True)
        p_lines = p_text.splitlines(keepends=True)
        sm = difflib.SequenceMatcher(None, d_lines, p_lines, autojunk=False)
        reps = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            old = ''.join(d_lines[i1:i2])
            new = ''.join(p_lines[j1:j2])
            reps.append({'tag': tag, 'old': old, 'new': new,
                         'n_old_lines': i2 - i1, 'n_new_lines': j2 - j1})

        # 🔴 **唯一命中断言**：old 块在 dev 全文里必须恰好出现 1 次
        ok = True
        for r in reps:
            n = d_text.count(r['old'])
            r['n_hit_in_dev'] = n
            if n != 1:
                ok = False
        if not ok:
            all_ok = False
            log('  🔴 [中止] %s：替换块在 dev 里不是唯一命中 ⇒ 不改' % fname)
            rows.append({'file': fname, 'status': 'ABORT_NOT_UNIQUE',
                         'reps': [{'n_hit_in_dev': r['n_hit_in_dev'],
                                   'old': r['old'][:120]} for r in reps]})
            continue

        new_text = d_text
        for r in reps:
            new_text = new_text.replace(r['old'], r['new'], 1)
        data = new_text.encode('utf-8')

        # ── 写前不变量 ────────────────────────────────────────
        b_crlf, b_lf = eol(db)
        a_crlf, a_lf = eol(data)
        assert (b_crlf > 0) == (a_crlf > 0) and (b_lf > 0) == (a_lf > 0), \
            '行尾风格变了：%s' % fname
        assert a_crlf == 0 or a_lf == 0, '混入另一种行尾：%s' % fname
        # 🔴 **行数允许变化**：这批替换块里有的把 2 行并成 1 行（去掉「待 B 机复核」尾巴）
        #    ⇒ 行数**理应**变化 ⇒ 改判「行数差 == 替换块预期行数差」（由重放法证明）
        d_n = len(d_text.splitlines())
        a_n = len(data.decode('utf-8').splitlines())
        exp_delta = sum(r['n_new_lines'] - r['n_old_lines'] for r in reps)
        assert a_n - d_n == exp_delta, \
            '行数变化与替换块预期不符：%s（实际 %d，预期 %d）' % (fname, a_n - d_n, exp_delta)
        if fname.endswith('.py'):
            ast.parse(data.decode('utf-8'))     # 必须仍可解析

        if not os.path.isdir(BAKDIR):
            os.makedirs(BAKDIR)
        bakp = os.path.join(BAKDIR, 'dev__' + fname)
        if not os.path.exists(bakp):
            shutil.copy2(dp, bakp)
        tmp = dp + '.tmp_app249'
        with io.open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, dp)
        assert open(dp, 'rb').read() == data, '写后逐字节复核失败：%s' % fname

        # 写后独立复核：dev 现在与包**逐字节相等**？
        same = open(dp, 'rb').read() == pb
        log('  [回灌] %-30s %d 个替换块 ⇒ 与包逐字节一致=%s'
            % (fname, len(reps), same))
        rows.append({'file': fname, 'status': 'SYNCED', 'n_reps': len(reps),
                     'n_hit_in_dev': [r['n_hit_in_dev'] for r in reps],
                     'now_identical_to_pkg': same,
                     'bytes_before': len(db), 'bytes_after': len(data),
                     'backup': bakp,
                     'reps': [{'old': r['old'][:200], 'new': r['new'][:200]}
                              for r in reps]})

    out = {
        'script': '_app249_sync_pkg_to_dev.py',
        'why': '包内已有 APP-153 §3/§5 修复，dev 树没有 ⇒ 下次打包（dev→包）会丢',
        'pkg': PKG,
        'files': rows,
        'all_ok': all_ok,
    }
    tmp = OUTJSON + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUTJSON)
    log('\n证据 → %s' % OUTJSON)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
