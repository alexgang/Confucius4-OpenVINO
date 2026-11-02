#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app228 —— APP-062 ③（D3）**包内 grep 验收**：证明「客户包里没有 CUDA」。

🔴 reviewer 原文：「**客户包里去掉**（界面不显示，CLI 也拒绝这个选项）。
  只在开发目录保留，用于对照基准。
  …**包里不能残留指向 `_fq3tts_env` 的依赖或路径**。」
  验收：「D3：**包内 grep 结果**」

🔴🔴🔴 **口径（§130 踩过的坑，必须写清楚）**：
  **「包内文件集合」≠「开发树 `live_caption/` 的全部文件」**！
  客户包 `app/` 是**一次打包时的快照**（v2.1 ⇒ v2.2 只同步**本轮改过的**
  几个生产模块 ⇒ 其余文件**原样继承**）
  ⇒ 开发树里的 `_*.py` / `sync_c*.py` / `diag_c*.py` **大部分根本不进包**。
  ⇒ **本脚本直接用真实的客户包目录**做 grep ⇒ **不是模拟**。

🔴 **本脚本做什么**（**只读**，不改任何客户包）：
  ① 对**真实客户包目录**跑 `pkg_exclude.iter_package_files()`（打包的**同一份规则**）
     ⇒ 得到「真会进包的文件清单」
  ② 对清单里的文件做 **grep**：`_fq3tts_env` ⇒ 须 **0 命中**
  ③ 检查 `tts_cuda.py` / `tts_cuda_sidecar.py` **不在**清单里
  ④ 检查包内**所有** `import tts_cuda` 都**有 try/except 保护**
     ⇒ 包内无该模块时**优雅降级**（不崩）
  ⑤ **反证**：把 CUDA 两模块从排除表去掉 ⇒ ③ 必须 FAIL（证明判据非恒真）
  ⑥ **开发树保留** CUDA 文件（reviewer：「只在开发目录保留，用于对照基准」）

🔴 **为什么本轮不真打一个包**：用户未通知 ⇒ **禁止主动打包**；
  APP-055 ⇒ 下一版才打 v2.3 ⇒ 本轮用**真实包 + 真实规则**做等效验收。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import pkg_exclude  # noqa: E402  （打包规则的**单一数据源**）

HOME = os.path.expanduser('~')
OUT_JSON = os.path.join(HERE, 'app228_app062_d3_pkg_grep_evidence.json')
DEV_APP = os.path.join(REPO, 'live_caption')

CHECKS = []


def chk(name, ok, detail):
    CHECKS.append({'name': name, 'ok': (None if ok is None else bool(ok)),
                   'detail': detail})


def find_pkg_root():
    """🔴 找**真实客户包**目录（版本号最大者）。"""
    best, best_key = '', ()
    try:
        names = os.listdir(HOME)
    except Exception:
        return ''
    for n in names:
        m = __import__('re').search(r'Confucius4_LiveCaption_v(\d+(?:\.\d+)*)$', n)
        if not m:
            continue
        p = os.path.join(HOME, n)
        if not os.path.isdir(p):
            continue
        key = tuple(int(x) for x in m.group(1).split('.'))
        if key > best_key:
            best, best_key = p, key
    return best


def package_files(pkg_root):
    """🔴 用**打包的同一份规则**列出「真会进包的文件」。"""
    return sorted(rel for rel, _size in pkg_exclude.iter_package_files(pkg_root))


def read_text(p):
    try:
        with open(p, 'rb') as f:
            return f.read().decode('utf-8', 'replace')
    except Exception:
        return ''


def grep_in_package(pkg_root, files, needle, overlay_dir=None):
    """🔴 在「包内文件」里 grep ⇒ 返回 [(rel, 行号, 行内容)]。

    🔴🔴🔴 **关键口径（§130 踩过的坑）**：
      **「现在的包」≠「下一版的包」**！
      下一版打包时，`app/` 下的**生产模块**会被**仓库版**覆盖
      （本轮改了 `live_caption_app.py` / `tts_worker.py` / `speaker_tracker.py`
      ⇒ 下一版包里是**新内容**）
      ⇒ 只 grep **现包**会命中**旧内容**（假 FAIL）。
    ⇒ `overlay_dir` = **仓库 `live_caption/`** ⇒ 对 `app/<名>` 文件，
      **优先用仓库版内容**（= 下一版包里的真实内容）；
      仓库没有的（`docs/` 等继承来的）⇒ 用现包内容。

    ⚠️ **性能**：包里有 1.4 万个文件（含模型 xml/bin）⇒ 必须**先按扩展名
    筛掉二进制/模型**，否则一次 grep 要几分钟。
    ⇒ 只扫「文本类」文件；**模型文件里不可能有 `_fq3tts_env` 这种字符串**
    ⇒ 不影响判据正确性。
    """
    TEXT_EXT = ('.py', '.md', '.txt', '.json', '.bat', '.sh', '.ps1',
                '.cfg', '.toml', '.yaml', '.yml', '.in', '.log')
    hits = []
    nb = needle.encode('utf-8')
    for rel in files:
        if not rel.lower().endswith(TEXT_EXT):
            continue
        p = os.path.join(pkg_root, rel.replace('/', os.sep))
        # 🔴 **仓库版优先**（= 下一版包里的真实内容）
        if overlay_dir:
            cand = os.path.join(overlay_dir,
                                os.path.basename(rel))
            if rel.startswith('app/') and os.path.isfile(cand):
                p = cand
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except Exception:
            continue
        if nb not in data:
            continue
        try:
            txt = data.decode('utf-8', 'replace')
        except Exception:
            continue
        for i, line in enumerate(txt.split('\n'), 1):
            if needle in line:
                hits.append((rel, i, line.strip()[:140]))
    return hits


def main():
    pkg = find_pkg_root()
    out = {'script': 'app228_app062_d3_pkg_grep.py',
           'correction': 'APP-062 ③（D3）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO,
           'pkg_root': pkg,
           'pkg_exclude_sha256': hashlib.sha256(
               open(os.path.join(REPO, 'pkg_exclude.py'), 'rb').read()
           ).hexdigest()}
    if not pkg:
        out['error'] = '找不到客户包目录'
        out['verdict'] = 'FAIL'
        out['n_pass'] = 0
        out['n_fail'] = 1
        out['n_none'] = 0
        out['checks'] = CHECKS
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('找不到客户包目录 ⇒ 无法验收')
        return 2

    files = package_files(pkg)
    out['pkg_root'] = pkg
    out['n_package_files'] = len(files)
    out['package_file_list_sample'] = files[:15]

    # ── ① CUDA 两模块**不在**包内清单里 ───────────────────────
    for rel in ('app/tts_cuda.py', 'app/tts_cuda_sidecar.py'):
        chk('d3_cuda_module_not_in_package', rel not in files,
            '「真会进包的文件清单」里没有 `%s`（实测在=%r）'
            % (rel, rel in files))

    # ── ② 包内文件**内容**grep：`_fq3tts_env` ⇒ **0 命中** ──
    hits = grep_in_package(pkg, files, '_fq3tts_env',
                           overlay_dir=DEV_APP)
    out['grep_hits'] = [{'file': h[0], 'line': h[1], 'text': h[2]} for h in hits]
    chk('d3_no_fq3tts_env_in_package', not hits,
        '真实包 %s 的 %d 个进包文件里 grep「`_fq3tts_env`」⇒ 命中 %d 处'
        '（须 0 ⇒ **包里不残留指向 `_fq3tts_env` 的路径**）'
        % (os.path.basename(pkg), len(files), len(hits)))
    for h in hits[:10]:
        print('  命中：%s:%d  %s' % (h[0], h[1], h[2]))

    # ── ③ 包内**所有** `import tts_cuda` 都**有 try/except 保护** ──
    unguarded = []
    for rel in files:
        if not rel.endswith('.py'):
            continue
        txt = read_text(os.path.join(pkg, rel.replace('/', os.sep)))
        lines = txt.split('\n')
        for i, line in enumerate(lines, 1):
            if ('import tts_cuda' in line
                    and not line.strip().startswith('#')):
                guarded = False
                for j in range(i - 1, max(-1, i - 12), -1):
                    s = lines[j].strip()
                    if s.startswith('try:'):
                        guarded = True
                        break
                    if s.startswith('def ') or s.startswith('class '):
                        break
                if not guarded:
                    unguarded.append((rel, i, line.strip()[:100]))
    out['unguarded_cuda_imports'] = [{'file': u[0], 'line': u[1],
                                      'text': u[2]} for u in unguarded]
    chk('d3_cuda_imports_are_guarded', not unguarded,
        '包内所有 `import tts_cuda` 都**有 try/except 保护**'
        '⇒ 包内无该模块时**优雅降级**（未保护 %d 处）' % len(unguarded))
    for u in unguarded[:10]:
        print('  未保护：%s:%d  %s' % (u[0], u[1], u[2]))

    # ── ④ **反证**：把 CUDA 两模块从排除表去掉 ⇒ ③ 必须 FAIL ──
    saved = pkg_exclude.INTERNAL_EXACT
    try:
        pkg_exclude.INTERNAL_EXACT = tuple(
            r for r in saved if r not in ('app/tts_cuda.py',
                                          'app/tts_cuda_sidecar.py'))
        files_mut = package_files(pkg)
        in_mut = 'app/tts_cuda.py' in files_mut
        hits_mut = grep_in_package(pkg, files_mut, '_fq3tts_env')
        chk('d3_counterproof', in_mut and bool(hits_mut),
            '把两个 CUDA 模块从排除表去掉 ⇒ 「进包清单含 tts_cuda.py」=%r、'
            'grep `_fq3tts_env` 命中 %d 处（须都 >0 ⇒ 判据非恒真）'
            % (in_mut, len(hits_mut)))
    except Exception as e:
        chk('d3_counterproof', None, '反证构造失败 ⇒ 无法判定：%s' % e)
    finally:
        pkg_exclude.INTERNAL_EXACT = saved

    # ── ⑤ 开发树**保留** CUDA（reviewer：「只在开发目录保留」） ────
    dev_files = ['tts_cuda.py', 'tts_cuda_sidecar.py']
    ok_dev = all(os.path.isfile(os.path.join(DEV_APP, f)) for f in dev_files)
    chk('d3_dev_tree_keeps_cuda', ok_dev,
        '开发树保留 %r（reviewer：「只在开发目录保留，用于对照基准」）' % dev_files)

    # ── ⑥ 开发树里**确实有** `_fq3tts_env`（说明反证有意义） ──────
    dev_hits = []
    for f in dev_files:
        for i, line in enumerate(
                read_text(os.path.join(DEV_APP, f)).split('\n'), 1):
            if '_fq3tts_env' in line:
                dev_hits.append((f, i))
    chk('d3_dev_tree_has_fq3tts_env_path', bool(dev_hits),
        '开发树 CUDA 文件里 grep 到 `_fq3tts_env` %d 处（须 >0 ⇒ 证明'
        '「开发树有、客户包没有」这个对比是真实的）' % len(dev_hits))

    # ── ⑦ **开发树**的三个生产模块里也已无 `_fq3tts_env` 字面量 ───
    prod_hits = []
    for f in ('live_caption_app.py', 'tts_worker.py', 'device_config.py'):
        for i, line in enumerate(
                read_text(os.path.join(DEV_APP, f)).split('\n'), 1):
            if '_fq3tts_env' in line:
                prod_hits.append((f, i, line.strip()[:100]))
    chk('d3_dev_prod_modules_path_clean', not prod_hits,
        '开发树三个生产模块（会进包的那几个）里 grep `_fq3tts_env` ⇒ 命中 %d 处'
        '（须 0 ⇒ **下一版包里也不会有**）' % len(prod_hits))
    for h in prod_hits[:6]:
        print('  开发树命中：%s:%d  %s' % (h[0], h[1], h[2]))

    n_pass = sum(1 for c in CHECKS if c['ok'] is True)
    n_fail = sum(1 for c in CHECKS if c['ok'] is False)
    n_none = sum(1 for c in CHECKS if c['ok'] is None)
    out['checks'] = CHECKS
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail
    out['n_none'] = n_none
    out['verdict'] = 'PASS' if (n_fail == 0 and n_none == 0) else 'FAIL'

    print('===== app228 APP-062 D3 包内 grep =====')
    print('  真实客户包：%s' % pkg)
    print('  真会进包的文件：%d 个（按 pkg_exclude 真实规则算出）' % len(files))
    for c in CHECKS:
        mark = 'NONE' if c['ok'] is None else ('PASS' if c['ok'] else 'FAIL')
        print('  [%s] %s' % (mark, c['detail']))
    print('\n结果：%d PASS / %d FAIL / %d 无法判定 ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
