r"""_app302_app077_token_gate.py — APP-077 ① 打包侧 token 排除闸门自检。

🔴 **为什么要单独写自检**（判据工程铁律：PASS ≠ 正确）
----------------------------------------------------------
`pkg_exclude.py` 有**两套**独立实现：
  * `is_excluded()`          —— 单路径判定（`iter_excluded` / 物理清理用）
  * `iter_package_files()`   —— os.walk + prune + **文件级规则**（`pack_v13.py` 用它生成 zip 清单）
⇒ 只在 `is_excluded()` 里加规则**会漏进包**（真实踩坑形态）。
本自检对**两套都验**，并用「已知有缺陷的旧规则」做反证，证明判据非恒真。

不占设备、不 import 被测模块的兄弟依赖、不推理、不打包。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pkg_exclude  # noqa: E402

EVIDENCE = os.path.join(HERE, '_app302_app077_token_gate.json')
CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append(dict(name=name, ok=bool(cond), detail=str(detail)))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + str(detail)) if detail else ''))
    return bool(cond)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ── 真实受影响的客户包（只读扫描，绝不修改）────────────────────────
PKG_V22 = os.path.join(os.path.expanduser('~'), 'Confucius4_LiveCaption_v2.2')

# 🔴 reviewer APP-077 要求「在 STATUS 列出受影响的包名和 SHA」
OLD_ZIPS = [
    'Confucius4_LiveCaption_v2.0.zip',
    'Confucius4_LiveCaption_v2.1.zip',
    'Confucius4_LiveCaption_v2.2.zip',
]
MINIMVP_ZIPS = [
    r'C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip',
    r'C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip',
]


def scan_zip(zpath):
    """只读 zip：返回 (条目数, 是否含 bridge_token.txt, 该条目的 SHA256/字节)。"""
    import zipfile
    n = 0
    hits = []
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            n += 1
            if info.filename.rsplit('/', 1)[-1].lower() == 'bridge_token.txt':
                hits.append(dict(name=info.filename,
                                 size=info.file_size,
                                 sha256=hashlib.sha256(z.read(info)).hexdigest()))
    return n, hits


def main():
    t0 = time.time()
    print('=' * 72)
    print('_app302 — APP-077 ① 打包侧 token 排除闸门自检')
    print('=' * 72)

    # ── ① 规则本体 ──────────────────────────────────────────────
    print('\n[1] 规则本体（is_bridge_token_file / is_excluded）')
    positives = [
        'ext/bridge_token.txt',
        'bridge_token.txt',
        'ext/bridge/bridge_token.txt',
        'a/b/bridge_token.txt',
        'EXT/BRIDGE_TOKEN.TXT',
    ]
    for rel in positives:
        check('命中 %s' % rel,
              pkg_exclude.is_bridge_token_file(rel)
              and pkg_exclude.is_excluded(rel, rel.split('/')[0]))

    # ⚠️ 不误伤：文件名精确匹配
    negatives = [
        'app/tokenizer_config.json',
        'ext/bridge/tokenizer_config.json',
        'ext/bridge_token.txt.bak',          # 备份文件由 SKIP_FILE_RE 管，不归本规则
        'models/decoder-gpu-int8/special_tokens_map.json',
        'app/live_caption_app.py',
    ]
    for rel in negatives:
        check('不误伤 %s' % rel,
              not pkg_exclude.is_bridge_token_file(rel))

    # ── ② iter_package_files（pack_v13.py 的实际口径）───────────
    print('\n[2] iter_package_files —— 真实包目录只读扫描')
    check('v2.2 包目录存在（只读）', os.path.isdir(PKG_V22), PKG_V22)
    token_rel = 'ext/bridge_token.txt'
    token_abs = os.path.join(PKG_V22, *token_rel.split('/'))
    token_meta = None
    if os.path.isfile(token_abs):
        token_meta = dict(path=token_abs,
                          size=os.path.getsize(token_abs),
                          sha256=sha256_file(token_abs),
                          mtime=os.path.getmtime(token_abs))
    check('v2.2 源目录里**确实有** token（否则本自检无从证明拦截）',
          token_meta is not None, token_meta)

    listed = [rel for rel, _sz in pkg_exclude.iter_package_files(PKG_V22)]
    check('进包清单不含 ext/bridge_token.txt', token_rel not in listed,
          '清单 %d 个文件' % len(listed))
    check('进包清单不含任何 bridge_token.txt',
          not any(r.rsplit('/', 1)[-1].lower() == 'bridge_token.txt' for r in listed))
    excluded = [rel for rel, _sz in pkg_exclude.iter_excluded(PKG_V22)]
    check('排除清单**含** ext/bridge_token.txt（物理清理口径）',
          token_rel in excluded, '排除清单 %d 个文件' % len(excluded))

    # ── ③ 反证：判据必须能识破「旧规则」────────────────────────
    # 🔴 不手改仓库代码：在临时目录里构造一个**已知有缺陷的旧规则**，
    #    证明「若没有 APP-077 规则，token 一定会被列进包」。
    print('\n[3] 反证（已知有缺陷的旧规则必须被识破）')
    with tempfile.TemporaryDirectory(prefix='app302_gate_') as tmp:
        os.makedirs(os.path.join(tmp, 'ext'), exist_ok=True)
        with open(os.path.join(tmp, 'ext', 'bridge_token.txt'), 'w', encoding='utf-8') as f:
            f.write('gcJcbNA0szeY2QEn2H2idxvfutQkxlkx')
        with open(os.path.join(tmp, 'ext', 'keep.txt'), 'w', encoding='utf-8') as f:
            f.write('keep')

        # 旧规则 = 逐条走 pkg_exclude 的其它规则，唯独去掉 APP-077
        def old_is_excluded(rel, top_dir):
            base = rel.rsplit('/', 1)[-1]
            if pkg_exclude.SKIP_FILE_RE.search(base):
                return True
            if pkg_exclude.BACKUP_FILE_RE.match(base):
                return True
            if any(rel.startswith(p) for p in pkg_exclude.SKIP_PATH_PREFIXES):
                return True
            if rel.startswith(pkg_exclude.MT2_ACC_OUTPUTS_DIR):
                return True
            if rel in pkg_exclude.INTERNAL_EXACT:
                return True
            if rel.startswith(pkg_exclude.RESULTS_DIR) and pkg_exclude.SPOKEN_FILE_RE.search(rel):
                return True
            if pkg_exclude.is_app_dev_only(rel):
                return True
            if pkg_exclude.is_third_party_noise(rel):
                return True
            if pkg_exclude.is_user_voice_artifact(rel):
                return True
            if '__pycache__' in rel.split('/'):
                return top_dir not in pkg_exclude.KEEP_PYCACHE_UNDER
            for seg in rel.split('/')[:-1]:
                if seg in pkg_exclude.SKIP_DIR_NAMES:
                    return True
                if pkg_exclude.BACKUP_DIR_RE.match(seg):
                    return True
            return False

        old_rel = 'ext/bridge_token.txt'
        old_leaks = not old_is_excluded(old_rel, 'ext')
        check('反证①：旧规则**会**把 token 列进包（缺陷可复现）', old_leaks,
              'old_is_excluded(%s) = False' % old_rel)
        check('反证②：新规则拦住同一个 token',
              pkg_exclude.is_excluded(old_rel, 'ext'))
        new_listed = [rel for rel, _ in pkg_exclude.iter_package_files(tmp)]
        check('反证③：临时目录进包清单只剩 keep.txt',
              new_listed == ['ext/keep.txt'], str(new_listed))
        # 反证④：破坏「被测的那个对象」—— 把正则换成恒假，判据必须转为不通过
        saved = pkg_exclude.BRIDGE_TOKEN_FILE_RE
        try:
            import re as _re
            pkg_exclude.BRIDGE_TOKEN_FILE_RE = _re.compile(r'(?!x)x')
            broken = pkg_exclude.is_excluded(old_rel, 'ext')
            check('反证④：把规则改成恒假 ⇒ 拦截失效（判据非恒真）',
                  not broken, 'is_excluded = %s' % broken)
        finally:
            pkg_exclude.BRIDGE_TOKEN_FILE_RE = saved
        check('反证⑤：还原后规则仍生效',
              pkg_exclude.is_excluded(old_rel, 'ext'))

    # ── ④ 旧包取证（绝不原地改）────────────────────────────────
    print('\n[4] 受影响旧包取证（只读 zip，不修改）')
    home = os.path.expanduser('~')
    zip_report = []
    for name in OLD_ZIPS:
        p = os.path.join(home, name)
        if not os.path.isfile(p):
            check('旧包 %s 存在' % name, False, '缺失')
            continue
        n, hits = scan_zip(p)
        zip_report.append(dict(name=name, path=p,
                               size=os.path.getsize(p), sha256=sha256_file(p),
                               entries=n, token_hits=hits,
                               mtime=os.path.getmtime(p)))
        check('旧包 %s 含固定 token（reviewer 指控成立）' % name,
              len(hits) == 1, '%d 条目 / token %s' % (n, hits))
    # 三个包的 token 必须完全相同（reviewer 原文）
    toks = [r['token_hits'][0]['sha256'] for r in zip_report
            if r['token_hits']]
    check('v2.0/v2.1/v2.2 token **逐字节同值**',
          len(toks) == 3 and len(set(toks)) == 1,
          str(sorted(set(toks))))

    mvp_report = []
    for p in MINIMVP_ZIPS:
        if not os.path.isfile(p):
            check('MiniMVP zip 存在 %s' % os.path.basename(p), False, '缺失')
            continue
        n, hits = scan_zip(p)
        mvp_report.append(dict(name=os.path.basename(p), path=p,
                               size=os.path.getsize(p), sha256=sha256_file(p),
                               entries=n, token_hits=hits,
                               mtime=os.path.getmtime(p)))
        check('MiniMVP %s **不含** bridge_token.txt' % os.path.basename(p),
              len(hits) == 0, '%d 条目' % n)

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(tool='_app302_app077_token_gate', app='APP-077',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               elapsed_s=round(time.time() - t0, 2),
               rule=pkg_exclude.BRIDGE_TOKEN_FILE_RE.pattern,
               checks=CHECKS, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL',
               affected_zips=zip_report, minimvp_zips=mvp_report,
               v22_source_token=token_meta)
    with open(EVIDENCE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n' + '=' * 72)
    print('verdict = %s  (%d PASS / %d FAIL)  证据: %s'
          % (out['verdict'], n_pass, n_fail, EVIDENCE))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
