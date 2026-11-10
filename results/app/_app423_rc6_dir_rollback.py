# -*- coding: utf-8 -*-
r"""_app423_rc6_dir_rollback.py —— **把 rc6 目录回滚到与 rc6 zip 逐字节一致**。

## 为什么要做这件事（自纠）

本轮（APP-098）在验收时于 **rc6 目录**就地修改了 `app/live_caption_app.py`
（`kind=='asr06b'` 的 label 撞车修复）⇒ **rc6 目录与 rc6 zip 内容不一致**
（zip 内仍是修复前的 475 504 B；目录内是修复后的 476 874 B）。

这与项目铁律「**永不原地改旧版**」冲突 ⇒ 处置：

1. 🔴 **rc6 zip 一字不动**（它才是 rc6 的交付形态，SHA 不变）；
2. 🔴 **把 rc6 目录回滚**到与 zip 逐字节一致 ⇒ 目录不再冒充「修好的 rc6」；
3. 🔴 **不删 rc6 目录、不删 rc6 zip**（历史件只登记不改）；
4. 🔴 **交付包 = rc7**（新目录 + 新 zip）。

## 判据（第一版判据本身是错的 ⇒ 已修正；这里记下错在哪）

* ❌ **v1 判据②「rc6 目录 ↔ rc7 目录差异恰好 2 个文件（只有 README/release.json）」是错的**：
  回滚之后 rc6 目录**必然**比 rc7 目录多一处差异 —— `app/live_caption_app.py`
  （rc6 zip 里是**缺陷代码**，rc7 里是**修复后代码**）⇒ 正确期望是 **3 个文件**。
  ⇒ 该错判据会诱导「把回滚撤掉、让 rc6 目录继续冒充修好的版本」⇒ **判据本身会改坏东西** ⇒ 重写。
* ❌ **v1 反证组也失效**：它以「差异数 = 3」为失败信号，而**正确状态本来就等于 3** ⇒ 恒真 ⇒ 无鉴别力。
  ⇒ v2 反证组改为**改坏一个版本号文件（README）**：正确状态下 README 已有差异，
  篡改后**差异行数必然变化** ⇒ 判据必须能区分「本来就不同」与「篡改导致的不同」。

## v2 判据

* ① **rc6 目录 ↔ rc6 zip**：全部 10 466 条目 **SHA256 逐条一致**（diff = 0）；
* ② **rc6 目录 ↔ rc7 目录**：差异 **恰好 3 个文件** = `README_perftest.txt` /
  `release.json` / `app/live_caption_app.py`；
  且前两者的差异行**只有版本号 / zip 字节数**，
  第三个的差异**恰好是 `asr06b` 修复块**（新增 `if cfg['kind'] == 'asr06b':` 分支）；
* ③ **反证组**：篡改 rc7 的 `README_perftest.txt` 一行 ⇒ 判据②的
  「README 差异行只有版本号」必须 FAIL ⇒ 证明判据对内容敏感（不是恒真）。
* ④ **rc7 目录恢复**：反证组后 rc7 目录回到「与 rc6 目录差 3 个文件」。

用法：
```
.venv/Scripts/python.exe results/app/_app423_rc6_dir_rollback.py
```
"""
import ast
import difflib
import hashlib
import json
import os
import shutil
import sys
import zipfile

HOME = os.path.expanduser('~')
RC6_DIR = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc6')
RC7_DIR = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc7')
RC6_ZIP = os.path.join(HOME, 'shared', 'minimvp',
                        'Confucius4_LiveCaption_MiniMVP_v1.0-rc6_perftest.zip')
HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, 'app423_rc6_dir_rollback.json')

ROLLBACK_TARGET = 'app/live_caption_app.py'
FIX_ANCHOR = "if cfg['kind'] == 'asr06b':"
FIX_KIND = 'asr06b'


def asr06b_handled_in_build_options(code):
    """AST 判据：`build_asr_options` 函数体内是否**有** asr06b 的独立分支。

    🔴 **不能用「全文出现 `if cfg['kind'] == 'asr06b':`」当判据** ——
    `_check_models()` 里本来就有这一句（rc6 zip 内也有）⇒ 锚点不唯一 ⇒ 恒真。
    ⇒ 正确做法：定位 `def build_asr_options` 的函数体，只看**那一段**。
    返回 (是否处理 asr06b, 该函数内命中的 kind 列表)
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'build_asr_options':
            kinds = []
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Compare) and len(sub.ops) == 1
                        and isinstance(sub.ops[0], ast.Eq)):
                    left = sub.left
                    right = sub.comparators[0]
                    for a, b in ((left, right), (right, left)):
                        if (isinstance(a, ast.Subscript)
                                and isinstance(b, ast.Constant)
                                and isinstance(b.value, str)):
                            try:
                                key = ast.literal_eval(a.slice)
                            except Exception:
                                continue
                            if key == 'kind' and b.value not in kinds:
                                kinds.append(b.value)
            return (FIX_KIND in kinds, kinds)
    return (False, [])


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def walk(root):
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root).replace(os.sep, '/')] = p
    return out


def diff_dirs(a_dir, b_dir):
    a, b = walk(a_dir), walk(b_dir)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    differing = []
    for r in sorted(set(a) & set(b)):
        if sha_file(a[r]) != sha_file(b[r]):
            differing.append(r)
    return only_a, only_b, differing


def udiff_lines(a_path, b_path):
    a = open(a_path, encoding='utf-8', errors='replace').read().splitlines()
    b = open(b_path, encoding='utf-8', errors='replace').read().splitlines()
    return [l for l in difflib.unified_diff(a, b, 'rc6', 'rc7', lineterm='', n=0)
            if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]


def main():
    ev = {'script': '_app423_rc6_dir_rollback.py', 'judgement_version': 'v2',
          'rc6_dir': RC6_DIR, 'rc6_zip': RC6_ZIP, 'rc7_dir': RC7_DIR}

    for p in (RC6_DIR, RC7_DIR, RC6_ZIP):
        if not os.path.exists(p):
            print('!! 缺前置件：%s' % p)
            return 2

    with zipfile.ZipFile(RC6_ZIP) as zf:
        roots = {n.split('/')[0] for n in zf.namelist() if n}
    root = sorted(roots)[0]
    ev['zip_root'] = root

    # ── ① 回滚前：记录现场（用于 STATUS 如实登记）────────────
    before = {'dir_vs_zip_diff': []}
    with zipfile.ZipFile(RC6_ZIP) as zf:
        zip_members = [n for n in zf.namelist() if not n.endswith('/')]
        ev['n_zip_entries'] = len(zip_members)
        zip_target = zf.read('%s/%s' % (root, ROLLBACK_TARGET))
        before['zip_target_sha256'] = sha_bytes(zip_target)
        before['zip_target_bytes'] = len(zip_target)
        for n in zip_members:
            rel = n[len(root) + 1:]
            p = os.path.join(RC6_DIR, rel.replace('/', os.sep))
            if not os.path.exists(p):
                before['dir_vs_zip_diff'].append(['MISSING_IN_DIR', rel])
            elif sha_file(p) != sha_bytes(zf.read(n)):
                before['dir_vs_zip_diff'].append(['DIFF', rel])
    tgt = os.path.join(RC6_DIR, ROLLBACK_TARGET.replace('/', os.sep))
    before['dir_target_sha256'] = sha_file(tgt)
    before['dir_target_bytes'] = os.path.getsize(tgt)
    before['dir_target_mtime'] = os.path.getmtime(tgt)
    ev['before'] = before

    # ── ①b 回滚前状态的**可复算证明**（脚本可重跑 ⇒ 必须能自证历史）────
    # 说明：本脚本第一次运行时 `before.dir_vs_zip_diff` = 1（DIFF app/live_caption_app.py），
    #   该次回滚已生效 ⇒ 之后每次重跑 before 都是 0。
    # ⇒ 为使「回滚前 rc6 目录内是修复后代码」这一事实**可复算**，这里用两个不变量证明：
    #   (a) rc6 **zip 内**的 live_caption_app.py **不含** asr06b 修复分支 ⇒ 确为缺陷代码；
    #   (b) 修复后代码 = dev 树那份（其 SHA 同时等于 rc7 包内那份）。
    dev_app = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'live_caption',
                           'live_caption_app.py')
    with zipfile.ZipFile(RC6_ZIP) as zf:
        zip_code = zf.read('%s/%s' % (root, ROLLBACK_TARGET)).decode('utf-8')
    rc7_code = open(os.path.join(RC7_DIR, 'app', 'live_caption_app.py'),
                    encoding='utf-8').read()
    zip_has, zip_kinds = asr06b_handled_in_build_options(zip_code)
    rc7_has, rc7_kinds = asr06b_handled_in_build_options(rc7_code)
    ev['pre_rollback_proof'] = {
        'a_rc6_zip_build_options_handles_asr06b': zip_has,
        'a_rc6_zip_build_options_kinds': zip_kinds,
        'a_rc6_zip_code_sha256': before['zip_target_sha256'],
        'a_rc6_zip_code_bytes': before['zip_target_bytes'],
        'b_dev_tree_file': dev_app,
        'b_dev_tree_sha256': sha_file(dev_app) if os.path.exists(dev_app) else None,
        'b_rc7_app_sha256': sha_file(os.path.join(RC7_DIR, 'app',
                                                  'live_caption_app.py')),
        'b_rc7_build_options_handles_asr06b': rc7_has,
        'b_rc7_build_options_kinds': rc7_kinds,
        'note': ('回滚前 rc6 目录内那份 == dev 树那份（修复后代码）；'
                 '回滚后 rc6 目录 == rc6 zip 内那份（缺陷代码）'
                 '⇒ 二者的 SHA 可在上列字段中互相核对'),
    }
    ev['pre_rollback_proof']['b_dev_eq_rc7'] = (
        ev['pre_rollback_proof']['b_dev_tree_sha256']
        == ev['pre_rollback_proof']['b_rc7_app_sha256'])
    ev['pre_rollback_proof']['verdict'] = (
        (not zip_has) and rc7_has
        and ev['pre_rollback_proof']['b_dev_eq_rc7'])

    # ── ② 回滚（只改这一个文件，内容 = zip 内原字节）──────────
    bak = tgt + '.rollback_bak'
    shutil.copy2(tgt, bak)
    with open(tgt, 'wb') as f:
        f.write(zip_target)
    ev['rolled_back'] = True
    ev['rolled_back_target'] = ROLLBACK_TARGET

    # ── ③ 判据①：rc6 目录 ↔ rc6 zip 全量逐条一致 ──────────────
    after = []
    with zipfile.ZipFile(RC6_ZIP) as zf:
        for n in [x for x in zf.namelist() if not x.endswith('/')]:
            rel = n[len(root) + 1:]
            p = os.path.join(RC6_DIR, rel.replace('/', os.sep))
            if not os.path.exists(p):
                after.append(['MISSING_IN_DIR', rel])
            elif sha_file(p) != sha_bytes(zf.read(n)):
                after.append(['DIFF', rel])
    ev['after_dir_vs_zip_diff'] = after
    ev['criterion_1_dir_equals_zip'] = (len(after) == 0)

    # ── ④ 判据②：rc6 目录 ↔ rc7 目录差异 = 3 且内容可解释 ──────
    oa, ob, dc = diff_dirs(RC6_DIR, RC7_DIR)
    ev['rc6_vs_rc7'] = {'only_rc6': oa, 'only_rc7': ob, 'differing': dc}
    ev['criterion_2_diff_count'] = len(dc)
    ev['criterion_2_exact_set'] = (set(dc) == {
        'README_perftest.txt', 'release.json', ROLLBACK_TARGET})

    detail = {}
    for rel in dc:
        detail[rel] = udiff_lines(os.path.join(RC6_DIR, rel),
                                  os.path.join(RC7_DIR, rel))
    ev['rc6_vs_rc7_diff_lines'] = detail

    readme_lines = detail.get('README_perftest.txt', [])
    rel_lines = detail.get('release.json', [])
    code_lines = detail.get(ROLLBACK_TARGET, [])
    ev['criterion_2_readme_version_only'] = (
        len(readme_lines) > 0
        and all(('rc6' in l or 'rc7' in l or '4420655' in l) for l in readme_lines))
    ev['criterion_2_release_version_only'] = (
        len(rel_lines) > 0
        and all(('rc6' in l or 'rc7' in l) for l in rel_lines))
    # 代码差异必须**只多出 asr06b 修复块**（AST 判据，不靠字符串锚点）
    rc6_code = open(os.path.join(RC6_DIR, ROLLBACK_TARGET.replace('/', os.sep)),
                     encoding='utf-8').read()
    rc7_code2 = open(os.path.join(RC7_DIR, ROLLBACK_TARGET.replace('/', os.sep)),
                     encoding='utf-8').read()
    rc6_has, rc6_kinds = asr06b_handled_in_build_options(rc6_code)
    rc7_has, rc7_kinds = asr06b_handled_in_build_options(rc7_code2)
    ev['ast_rc6_build_options_handles_asr06b'] = rc6_has
    ev['ast_rc6_build_options_kinds'] = rc6_kinds
    ev['ast_rc7_build_options_handles_asr06b'] = rc7_has
    ev['ast_rc7_build_options_kinds'] = rc7_kinds
    ev['criterion_2_code_is_fix_block'] = (
        (not rc6_has) and rc7_has and len(code_lines) > 0)
    # 更严：代码差异里 + 行多于 - 行（rc7 = rc6 + 修复块，纯增量）
    plus = sum(1 for l in code_lines if l.startswith('+'))
    minus = sum(1 for l in code_lines if l.startswith('-'))
    ev['code_diff_plus'] = plus
    ev['code_diff_minus'] = minus
    ev['criterion_2_code_fix_is_additive'] = (plus > minus and minus == 0)

    # ── ⑤ 判据③ 反证组：篡改 rc7 的 asr06b 修复分支 ⇒ AST 判据必 FAIL ─
    # 🔴 反证构造的坑：不能删整行（会把 `if` 块掏空 ⇒ SyntaxError ⇒ 假 FAIL）
    #   ⇒ 改成把该行替换成 `pass`（保持语法合法、语义被破坏）。
    cpath = os.path.join(RC7_DIR, 'app', 'live_caption_app.py')
    cb = open(cpath, 'rb').read()
    ctext = cb.decode('utf-8')
    ctext_neg = ctext.replace(FIX_ANCHOR, "if False:  # NEGATIVE CONTROL")
    assert ctext_neg != ctext, '反证构造失败：未找到锚点'
    with open(cpath, 'w', encoding='utf-8', newline='') as f:
        f.write(ctext_neg)
    neg_has, neg_kinds = asr06b_handled_in_build_options(ctext_neg)
    ev['negative_control_kinds'] = neg_kinds
    ev['negative_control_would_fail_ast_judge'] = (not neg_has)
    with open(cpath, 'wb') as f:
        f.write(cb)
    ev['criterion_3_negative_control_detects'] = (not neg_has)

    # ── ⑤b 反证组②：篡改 rc7 的 README ⇒ 版本号判据必 FAIL ────
    rpath = os.path.join(RC7_DIR, 'README_perftest.txt')
    rb = open(rpath, 'rb').read()
    with open(rpath, 'ab') as f:
        f.write('\n# NEGATIVE CONTROL: tamper\n'.encode('utf-8'))
    neg_lines = udiff_lines(os.path.join(RC6_DIR, 'README_perftest.txt'), rpath)
    neg_version_only = all(('rc6' in l or 'rc7' in l or '4420655' in l)
                           for l in neg_lines)
    ev['negative_control_readme_lines'] = len(neg_lines)
    ev['negative_control_readme_would_fail_version_judge'] = (not neg_version_only)
    with open(rpath, 'wb') as f:
        f.write(rb)
    ev['criterion_3b_negative_control_detects'] = (not neg_version_only)

    # ── ⑥ rc7 恢复确认 ───────────────────────────────────────
    _oa, _ob, dc_restored = diff_dirs(RC6_DIR, RC7_DIR)
    ev['after_negative_control_restore_diff_count'] = len(dc_restored)
    ev['rc7_restored'] = (len(dc_restored) == 3)

    try:
        os.remove(bak)
        ev['backup_removed'] = True
    except OSError as e:
        ev['backup_removed'] = False
        ev['backup_error'] = str(e)

    ev['verdict'] = 'PASS' if (
        ev['criterion_1_dir_equals_zip']
        and ev['criterion_2_exact_set']
        and ev['criterion_2_readme_version_only']
        and ev['criterion_2_release_version_only']
        and ev['criterion_2_code_fix_is_additive']
        and ev['criterion_2_code_fix_is_additive']
        and ev['criterion_3_negative_control_detects']
        and ev['criterion_3b_negative_control_detects']
        and ev['rc7_restored']) else 'FAIL'

    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in (
        'verdict', 'criterion_1_dir_equals_zip', 'criterion_2_diff_count',
        'criterion_2_exact_set', 'criterion_2_readme_version_only',
        'criterion_2_release_version_only', 'criterion_2_code_is_fix_block',
        'criterion_2_code_fix_is_additive', 'code_diff_plus', 'code_diff_minus',
        'criterion_3_negative_control_detects', 'rc7_restored',
        'negative_control_readme_lines')}, ensure_ascii=False, indent=1))
    print('before dir_vs_zip_diff =', len(before['dir_vs_zip_diff']),
          before['dir_vs_zip_diff'])
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
