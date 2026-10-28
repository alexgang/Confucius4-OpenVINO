r"""app126_zip_pkg_verify.py —— §86 zip ⇄ 包目录 **只读** 三方复核。

按 §66 口径：不跑 `verify_pkg_zip.py`、不跑 `publish_ftp.py`、不开 FTP。
「已交付」= 客户包目录 + zip 已含最新代码且该代码已入库（HEAD）。

本脚本做**只读**复核，不写任何文件（除落盘的证据 JSON）：
  1. zip 物理属性：文件数 / mtime / 字节数 / SHA256 / `testzip()`
  2. zip 内 `.py` 清单 ⇄ 包目录 `.py` 清单（**集合比对**，列出缺失/多出）
  3. zip 内每个 `.py` 的内容 ⇄ 包目录同名文件（SHA256 逐字节比对）
  4. 仓库 HEAD `live_caption/*.py` ⇄ 包目录 ⇄ zip（归一化换行后三方一致）
  5. zip 内**不得出现**内部素材 / 备份文件 / 内部会议特征串

零推理、零 GPU、零 NPU、不调 MiniMax。
"""
import hashlib
import json
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pkg_paths  # noqa: E402  §48 单一数据源
import pkg_exclude  # noqa: E402  排除规则单一数据源

PKG_ROOT = pkg_paths.discover_pkg_dir()
PKG_APP = pkg_paths.pkg_app_dir()
ZIP_PATH = PKG_ROOT + '.zip'
PREFIX = os.path.basename(PKG_ROOT)
REPO_LIVE = os.path.join(REPO_ROOT, 'live_caption')

OUT = os.path.join(HERE, 'app126_zip_pkg_verify_evidence.json')

# zip 内**禁止**出现的路径片段（内部素材 / 内部备份 / 内部会议特征）
# 🔴 不用子串判 `clone_`：生产模块 `app/clone_collector.py` 是合法代码
#    （APP-027⑤ 采集克隆源语音），子串判据会误伤 ⇒ 改用 pkg_exclude 权威判据。
FORBIDDEN_SUBSTR = ('_backup', 'tts_speakers', 'ov_cache', 'npu_cache',
                    '/_backup', '\\backup')
FORBIDDEN_TEXT = ('QGS', '260902')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for blk in iter(lambda: fh.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def norm(b):
    """归一化换行（LF/CRLF 一律归 LF）后比对。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def git_show(rel):
    return subprocess.run(
        ['git', 'show', 'HEAD:' + rel],
        cwd=REPO_ROOT, capture_output=True, check=True).stdout


def main():
    ev = {'zip_path': ZIP_PATH, 'pkg_root': PKG_ROOT, 'pkg_app': PKG_APP,
          'prefix': PREFIX, 'repo_live': REPO_LIVE, 'checks': {}}
    fails = []

    # ── 1. zip 物理属性 ──────────────────────────────────────────
    if not os.path.isfile(ZIP_PATH):
        ev['verdict'] = 'FAIL'
        ev['fatal'] = 'zip 不存在：' + ZIP_PATH
        with open(OUT, 'w', encoding='utf-8', newline='') as fh:
            json.dump(ev, fh, ensure_ascii=False, indent=2)
        print('[FATAL] zip 不存在：', ZIP_PATH)
        return 1

    st = os.stat(ZIP_PATH)
    ev['zip_size'] = st.st_size
    ev['zip_mtime'] = __import__('datetime').datetime.fromtimestamp(
        st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    ev['zip_sha256'] = sha256_file(ZIP_PATH)
    print(f"[zip] {ZIP_PATH}")
    print(f"[zip] 字节数 = {st.st_size} / mtime = {ev['zip_mtime']}")
    print(f"[zip] SHA256 = {ev['zip_sha256']}")

    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        names = zf.namelist()
        ev['zip_entries_total'] = len(names)

        bad = zf.testzip()
        ev['zip_testzip_bad_entry'] = bad
        if bad is not None:
            fails.append('zip testzip() 损坏条目：%s' % bad)
            print('[FAIL] testzip() 损坏：', bad)
        else:
            print('[OK] testzip() 通过')

        py_in_zip = sorted(n for n in names
                           if n.lower().endswith('.py') and not n.endswith('/'))
        # 🔴 比对范围 = **整个包根**（PKG_ROOT），不是仅 app/：
        #    zip 内含内置解释器 `python/Lib/**.py`（6566 个），只比 app/
        #    会把它们全判成「仅 zip」⇒ 假 FAIL。
        py_in_pkg = []
        for root, dirs, files in os.walk(PKG_ROOT):
            dirs[:] = [d for d in dirs if d not in ('ov_cache', 'npu_cache',
                                                   '__pycache__')]
            for fn in files:
                if fn.lower().endswith('.py'):
                    rel = os.path.relpath(os.path.join(root, fn), PKG_ROOT)
                    py_in_pkg.append(rel.replace('\\', '/'))
        py_in_pkg = sorted(py_in_pkg)
        ev['py_count_zip'] = len(py_in_zip)
        ev['py_count_pkg'] = len(py_in_pkg)

        # zip 内路径前缀是 PREFIX/
        zset = {}
        for n in py_in_zip:
            pre = PREFIX + '/'
            rel = n[len(pre):] if n.startswith(pre) else n
            zset[rel] = n
        # 🔴 包目录侧剔除**被 pkg_exclude 排除**的文件（如
        #    `app/_probe_tts_cuda.py`）：按设计不进 zip ⇒ 预期非缺陷。
        excluded = [rel for rel in py_in_pkg if pkg_exclude.is_excluded(rel)]
        ev['py_excluded_from_pkg'] = sorted(excluded)[:50]
        pset = set(py_in_pkg) - set(excluded)
        only_pkg = sorted(pset - set(zset))
        only_zip = sorted(set(zset) - pset)
        ev['py_only_in_pkg'] = only_pkg
        ev['py_only_in_zip'] = only_zip
        if only_pkg or only_zip:
            fails.append('.py 清单不一致：仅包目录 %d 个 / 仅 zip %d 个'
                         % (len(only_pkg), len(only_zip)))
            print('[FAIL] .py 清单不一致：only_pkg=%s only_zip=%s'
                  % (only_pkg[:10], only_zip[:10]))
        else:
            print('[OK] .py 清单一致：%d 个' % len(zset))

        # ── 3. 逐文件内容比对（.py）────────────────────────────────
        mismatch = []
        for rel in sorted(set(zset) & pset):
            disk = os.path.join(PKG_ROOT, rel.replace('/', os.sep))
            if not os.path.isfile(disk):
                mismatch.append({'rel': rel, 'why': '包目录无此文件'})
                continue
            zdata = zf.read(zset[rel])
            ddata = open(disk, 'rb').read()
            if sha256_bytes(zdata) != sha256_bytes(ddata):
                mismatch.append({'rel': rel, 'why': '内容 SHA256 不一致',
                                 'zip': sha256_bytes(zdata),
                                 'pkg': sha256_bytes(ddata)})
        ev['py_content_mismatch'] = mismatch
        if mismatch:
            fails.append('.py 内容不一致 %d 个' % len(mismatch))
            print('[FAIL] .py 内容不一致：', mismatch[:5])
        else:
            print('[OK] .py 内容逐字节一致：%d 个' % len(set(zset) & pset))

        # ── 4. 仓库 HEAD ⇄ 包目录 ⇄ zip 三方 ──────────────────────
        trio = []
        for rel in sorted(set(zset) & pset):
            repo_rel = 'live_caption/' + rel
            try:
                rdata = git_show(repo_rel)
            except Exception:
                continue        # 仓库无同名文件（如内置解释器 python/Lib/**）
            disk = os.path.join(PKG_ROOT, rel.replace('/', os.sep))
            ddata = open(disk, 'rb').read()
            zdata = zf.read(zset[rel])
            if norm(rdata) != norm(ddata) or norm(ddata) != norm(zdata):
                trio.append(rel)
        ev['trio_inconsistent'] = trio
        if trio:
            fails.append('仓库⇄包目录⇄zip 三方不一致 %d 个' % len(trio))
            print('[FAIL] 三方不一致：', trio[:10])
        else:
            print('[OK] 仓库⇄包目录⇄zip 三方一致')

        # ── 5. zip 内禁止项 ───────────────────────────────────────
        # 🔴 权威判据 = pkg_exclude.is_excluded（与打包清单完全同一套规则）
        #    ⇒ 不会出现「闸门说该拦、实际没拦」或「实际没拦、闸门误报」。
        bad_names = []
        for n in names:
            if n.endswith('/'):
                continue
            rel = n[len(PREFIX) + 1:] if n.startswith(PREFIX + '/') else n
            if pkg_exclude.is_excluded(rel):
                bad_names.append(n)
        ev['zip_forbidden_names'] = bad_names[:50]
        ev['zip_forbidden_name_count'] = len(bad_names)
        if bad_names:
            fails.append('zip 内含被排除项 %d 个' % len(bad_names))
            print('[FAIL] zip 内含被排除项：', bad_names[:10])
        else:
            print('[OK] zip 内无被排除项（备份/克隆素材/音色库/缓存）')

        # 不误伤反证：生产模块 clone_collector.py 必须在 zip 内、且不被排除
        probe = PREFIX + '/app/clone_collector.py'
        ev['clone_collector_in_zip'] = probe in set(names)
        ev['clone_collector_excluded'] = pkg_exclude.is_excluded(
            'app/clone_collector.py')
        if not ev['clone_collector_in_zip'] or ev['clone_collector_excluded']:
            fails.append('clone_collector.py 判定异常（在 zip=%s / 被排除=%s）'
                         % (ev['clone_collector_in_zip'],
                            ev['clone_collector_excluded']))
            print('[FAIL] clone_collector.py 判定异常')
        else:
            print('[OK] clone_collector.py 在 zip 内且未被排除（不误伤）')

        # 内部会议特征串（只扫小文本文件，避免 13 GB 全扫）
        hits = []
        for n in names:
            if n.endswith('/') or not n.lower().endswith(
                    ('.md', '.txt', '.json', '.py')):
                continue
            try:
                data = zf.read(n)
            except Exception:
                continue
            if len(data) > 4 * 1024 * 1024:
                continue
            for s in FORBIDDEN_TEXT:
                if s.encode('utf-8') in data:
                    hits.append({'entry': n, 'token': s})
                    break
        ev['zip_internal_text_hits'] = hits[:50]
        ev['zip_internal_text_hit_count'] = len(hits)
        if hits:
            fails.append('zip 内含内部会议特征串 %d 处' % len(hits))
            print('[FAIL] 内部特征串：', hits[:5])
        else:
            print('[OK] zip 内无内部会议特征串')

    ev['fails'] = fails
    ev['verdict'] = 'FAIL' if fails else 'PASS'
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=2)
    print('\n=== 结论：%s ===' % ev['verdict'])
    if fails:
        for f in fails:
            print('  - ' + f)
    print('证据：', OUT)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
