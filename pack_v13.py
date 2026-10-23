r"""pack_v13.py —— 打包客户包 v1.3 并校验。

步骤：刷新 MANIFEST → zip → testzip() → 抽查关键文件（MT 模型、translator.py、
MANIFEST、README）→ 硬校验 MANIFEST 的 files/bytes。

C-133 / APP-002：客户包瘦身
---------------------------
编译缓存（`app/ov_cache` 等）**不进包**，排除规则集中在 `pkg_exclude.py`
（单一数据源，与物理清理、MANIFEST 统计共用）。

排除规则摘要：
  - 目录名：`ov_cache` / `npu_cache` / `mt_cache`（任意层级，含包根级）
  - 路径前缀：`app/reports/`、`reports/`
  - 文件名：含 `.bak` 的开发期备份
  - `python/**/__pycache__` **保留**（包内 Python 恒为 3.12，省首次启动 1~5 s）

用法
----
    python pack_v13.py                       # 打包并校验（默认路径）
    python pack_v13.py --dry-run             # 只报告将要打包/排除的内容，不写 zip
    python pack_v13.py --pkg DIR --zip FILE  # 指定路径
"""
import argparse
import hashlib
import json
import os
import sys
import time
import zipfile

# 保证从任意 CWD 运行都能 import 到同目录的 pkg_exclude
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkg_exclude  # noqa: E402

DEFAULT_PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3'
DEFAULT_ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3.zip'
DEFAULT_PREFIX = 'Confucius4_LiveCaption_v1.3'

MANIFEST_REL = 'app/MANIFEST.json'

# 必须存在于 zip 内的关键文件（相对 PREFIX/）
MUST = [
    'app/translator.py',
    'app/live_caption_app.py',
    'app/MANIFEST.json',
    'README_zh.md',
    'README_en.md',
    'THIRD_PARTY.md',
    'Start_LiveCaption.bat',
    'Diagnose.bat',
    'models/mt/mt2-int4sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int4sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int4sym-cw-q/config.json',
    'models/mt/mt2-int4sym-cw-q/chat_template.jinja',
]

# 必须**不存在**于 zip 内的**精确**路径
# （旧的 Instruct 产物 / 备份文件 / v1.3 已移除的 INT8）
# ⚠️ 这类是「历史防回归断言」—— 即使当前源目录里没有，价值也不消失。
MUST_NOT_EXACT = [
    'app/translator.py.bak_instruct_20261022',
    'models/mt/int4sym-cw-q/openvino_model.bin',
    'models/mt/int8sym-cw-q/openvino_model.bin',
    # v1.3 只附带 INT4 —— INT8 必须不在包内
    'models/mt/mt2-int8sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int8sym-cw-q/openvino_model.bin',
    # 开发期备份一律不进包
    'app/live_caption_app.py.bak_c105',
    'app/live_caption_app.py.bak_c106',
    'app/live_caption_app.py.bak_c108',
    'app/live_caption_app.py.bak_c109',
]

# 🔴 内部会议内容：精确点名（APP-003①）
# `results/mt2_memory.json` 的 `out` 字段是「[REDACTED-内部会议引文]
# —— 是 spoken 语料的译文，文件名不含 `_spoken` ⇒ 必须单独点名。
MUST_NOT_EXACT += list(pkg_exclude.INTERNAL_EXACT)

# 必须**不存在**于 zip 内的**目录前缀**（带尾 '/'）
# ⚠️ 必须带尾 '/' —— 否则 `app/ov_cache` 会误伤 `app/ov_cache_helper.py`。
# ⚠️ 从 pkg_exclude 导入（单一数据源），不要在这里重复写。
MUST_NOT_PREFIX = list(pkg_exclude.SKIP_DIR_PREFIXES)

# 🔴 内部会议内容：文件名模式断言（APP-003①）
# `results/**/*_spoken.*` 一律不许进包。
# ⚠️ 不能用「精确列表」—— 文件名会随配置数增长
#    （{int4,int8,bf16} × {gpu,npu} × {json,txt} = 12 个），
#    用**模式**断言才不会漏。规则来自 pkg_exclude（单一数据源）。
MUST_NOT_NAME_RE = pkg_exclude.SPOKEN_FILE_RE

# 额外的目录级断言：整个旧量化目录不该存在（比「目录里某个 .bin 不该存在」更强）
MUST_NOT_PREFIX += [
    'models/mt/int8sym-cw-q/',
    'models/mt/int4sym-cw-q/',
    'models/mt/mt2-int8sym-cw-q/',
]


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def refresh_manifest(pkg):
    """按**排除后的净载荷**刷新 `app/MANIFEST.json` 的 files/bytes。

    C-133 / APP-002：MANIFEST 曾经用「源目录口径」统计，与 zip 内容必然对不上
    （打包排除一旦生效就永远对不上）。现在改成与 `pkg_exclude` 完全同一口径。

    ⚠️ MANIFEST **自身不计入** files/bytes —— 否则自引用：
    它自己写进去的 bytes 字段会改变它自己的长度。

    返回 (old_files, old_bytes, new_files, new_bytes)。
    """
    path = os.path.join(pkg, MANIFEST_REL.replace('/', os.sep))
    if not os.path.isfile(path):
        print(f'[warn] 未找到 {MANIFEST_REL}，跳过刷新')
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    old_files = data.get('files')
    old_bytes = data.get('bytes')
    new_files, new_bytes = pkg_exclude.package_stats(pkg, skip=(MANIFEST_REL,))

    data['files'] = new_files
    data['bytes'] = new_bytes
    with open(path, 'w', encoding='utf-8', newline='') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f'MANIFEST 刷新: files {old_files} -> {new_files}  '
          f'bytes {old_bytes} -> {new_bytes} ({new_bytes / 1024 ** 3:.2f} GB)')
    return old_files, old_bytes, new_files, new_bytes


def report_excluded(pkg):
    """打印将被排除的内容（按类别汇总）。"""
    import collections
    cat = collections.defaultdict(lambda: [0, 0])
    for rel, size in pkg_exclude.iter_excluded(pkg):
        if '__pycache__' in rel.split('/'):
            key = '__pycache__'
        elif '.bak' in rel.lower():
            key = '.bak_*'
        else:
            key = rel.split('/')[0] + '/' + rel.split('/')[1] \
                if rel.count('/') >= 1 else rel
        cat[key][0] += 1
        cat[key][1] += size
    print('将排除的内容：')
    for key, (n, s) in sorted(cat.items(), key=lambda x: -x[1][1]):
        print(f'  {key:24s} {n:6d} 文件  {s / 1024 ** 2:9.1f} MB')
    return cat


def do_dry_run(pkg, prefix):
    print('=' * 70)
    print(f'[dry-run] {prefix}')
    print('=' * 70)
    print('源目录:', pkg)
    print()

    n_files, n_bytes = pkg_exclude.package_stats(pkg, skip=(MANIFEST_REL,))
    print(f'将打包: {n_files} 文件 / {n_bytes} 字节 ({n_bytes / 1024 ** 3:.2f} GB)')
    print()
    report_excluded(pkg)

    # 关键文件是否都在
    print()
    print('关键文件检查：')
    missing = []
    for rel in MUST:
        p = os.path.join(pkg, rel.replace('/', os.sep))
        ok = os.path.isfile(p)
        if not ok:
            missing.append(rel)
        print(f'  [{"OK" if ok else "缺"}] {rel}')

    # 🔴 内部会议内容检查（APP-003①）
    # 源目录里**应该已经**没有这些文件了（APP-003①(d) 要求移出包）。
    # 如果还在，说明物理清理没做 ⇒ 但**打包仍会剔掉**（pkg_exclude 规则生效），
    # 这里只是提醒源目录仍脏。
    print()
    print('内部会议内容检查（results/ 下 *_spoken.* 与点名文件）：')
    dirty = []
    # iter_package_files 已按规则过滤 ⇒ 改用 os.walk 直接看源目录真实状态
    for dirpath, _dirs, filenames in os.walk(pkg):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, pkg).replace('\\', '/')
            if rel in pkg_exclude.INTERNAL_EXACT:
                dirty.append(rel)
            elif rel.startswith(pkg_exclude.RESULTS_DIR) and \
                    MUST_NOT_NAME_RE.search(fn):
                dirty.append(rel)
    print(f'  源目录残留: {len(dirty)} 个内部内容文件')
    for rel in sorted(dirty)[:20]:
        print(f'      ⚠️ {rel}')
    if dirty:
        print('  ⇒ 这些文件**不会进包**（pkg_exclude 规则已生效），'
              '但源目录仍脏，建议按 APP-003①(d) 移出包外。')

    print()
    if missing:
        print('结论：FAIL（关键文件缺失）')
        return 1
    print('结论：PASS（dry-run，未写 zip）')
    return 0


def main():
    ap = argparse.ArgumentParser(description='打包客户包 v1.3 并校验')
    ap.add_argument('--pkg', default=DEFAULT_PKG, help='客户包源目录')
    ap.add_argument('--zip', default=DEFAULT_ZIP, help='输出 zip 路径')
    ap.add_argument('--prefix', default=DEFAULT_PREFIX, help='zip 内顶层目录名')
    ap.add_argument('--level', type=int, default=6,
                    help='压缩级别（默认 6；实测 1/6/9 差异 <1%%，不建议改）')
    ap.add_argument('--dry-run', action='store_true',
                    help='只报告将要打包/排除的内容，不写 zip')
    args = ap.parse_args()

    PKG = args.pkg
    ZIP = args.zip
    PREFIX = args.prefix

    if not os.path.isdir(PKG):
        print(f'!! 源目录不存在: {PKG}')
        return 1

    if args.dry_run:
        return do_dry_run(PKG, PREFIX)

    t0 = time.time()
    print('=' * 70)
    print(f'打包 {PREFIX}')
    print('=' * 70)
    print('源目录:', PKG)
    print('输出  :', ZIP)
    print()

    # ── 打包前刷新 MANIFEST（口径 = 排除后的净载荷，不含 MANIFEST 自身）──
    refresh_manifest(PKG)

    if os.path.exists(ZIP):
        os.remove(ZIP)

    n_files = 0
    total_raw = 0
    with zipfile.ZipFile(ZIP, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=args.level, allowZip64=True) as zf:
        for rel, size in pkg_exclude.iter_package_files(PKG):
            full = os.path.join(PKG, rel.replace('/', os.sep))
            arc = f'{PREFIX}/{rel}'
            zf.write(full, arc)
            n_files += 1
            total_raw += size
            if n_files % 2000 == 0:
                print(f'  ... {n_files} 文件')

    sz = os.path.getsize(ZIP)
    print()
    print(f'文件数     : {n_files}')
    print(f'原始字节   : {total_raw}')
    print(f'压缩后字节 : {sz}  ({sz / 1024 ** 3:.2f} GB)')
    print(f'压缩率     : {sz / total_raw * 100:.1f}%')
    print(f'耗时       : {time.time() - t0:.0f}s')
    print()

    print('-' * 70)
    print('testzip() 校验…')
    with zipfile.ZipFile(ZIP, 'r') as zf:
        bad = zf.testzip()
        if bad is None:
            print('  Everything is Ok')
        else:
            print('  !!! 损坏条目:', bad)
            return 1

        names = set(zf.namelist())
        print()
        print('关键文件抽查：')
        missing = []
        for rel in MUST:
            arc = f'{PREFIX}/{rel}'
            ok = arc in names
            if not ok:
                missing.append(rel)
            size = zf.getinfo(arc).file_size if ok else 0
            print(f'  [{"OK" if ok else "缺"}] {rel}  ({size:,} bytes)')

        print()
        print('旧产物应已移除（精确路径）：')
        stale = []
        for rel in MUST_NOT_EXACT:
            arc = f'{PREFIX}/{rel}'
            ok = arc not in names
            if not ok:
                stale.append(rel)
            print(f'  [{"已移除" if ok else "仍在"}] {rel}')

        print()
        print('缓存目录应已移除（目录前缀）：')
        stale_prefix = []
        for prefix in MUST_NOT_PREFIX:
            hit = sorted(n for n in names if n.startswith(f'{PREFIX}/{prefix}'))
            ok = not hit
            if not ok:
                stale_prefix.append(prefix)
            detail = f'({len(hit)} 条)' if hit else ''
            print(f'  [{"已移除" if ok else "仍在"}] {prefix} {detail}')

        # 🔴 内部会议内容断言（APP-003①）
        # `results/**/*_spoken.*` 与点名文件必须**一个都不在** zip 里。
        spoken_hit = sorted(
            n for n in names
            if n.startswith(f'{PREFIX}/{pkg_exclude.RESULTS_DIR}')
            and MUST_NOT_NAME_RE.search(n.rsplit('/', 1)[-1])
        )
        print()
        print('内部会议内容应已移除（results/ 下 *_spoken.* 与点名文件）：')
        print(f'  [{"已移除" if not spoken_hit else "仍在"}] *_spoken.* '
              f'（{len(spoken_hit)} 条命中）')
        for n in spoken_hit[:20]:
            print(f'      ⚠️ {n}')
        internal_hit = sorted(
            n for n in names
            if n[len(PREFIX) + 1:] in pkg_exclude.INTERNAL_EXACT
        )
        print(f'  [{"已移除" if not internal_hit else "仍在"}] 点名文件 '
              f'（{len(internal_hit)} 条命中）')
        for n in internal_hit:
            print(f'      ⚠️ {n}')

        # MANIFEST 硬校验
        man = json.loads(zf.read(f'{PREFIX}/{MANIFEST_REL}').decode('utf-8'))
        entries = [n for n in names if not n.endswith('/')]
        zip_bytes = sum(zf.getinfo(n).file_size for n in entries)
        man_files = man.get('files')
        man_bytes = man.get('bytes')
        files_ok = (len(entries) == man_files)
        # MANIFEST 自身不计入统计口径 → 校验时补上它的体积
        man_size = zf.getinfo(f'{PREFIX}/{MANIFEST_REL}').file_size
        bytes_ok = (zip_bytes == man_bytes + man_size)
        print()
        print(f'MANIFEST version = {man["version"]}  files={man_files}  bytes={man_bytes}')
        print(f'  [{"OK" if files_ok else "不符"}] zip 条目 {len(entries)} == MANIFEST files {man_files}')
        print(f'  [{"OK" if bytes_ok else "不符"}] zip 原始体积 {zip_bytes} '
              f'== MANIFEST bytes {man_bytes} + MANIFEST 自身 {man_size}')

        # translator.py 关键符号抽查
        src = zf.read(f'{PREFIX}/app/translator.py').decode('utf-8')
        syms = ['mt2-int4sym-cw-q', '_TRANSLATE_INSTR', 'Default Translation',
                'stop_strings = set()', 'split_sentences']
        print()
        print('translator.py 符号抽查：')
        for s in syms:
            print(f'  [{"有" if s in src else "缺"}] {s}')

        # 翻译模型目录清单：v1.3 只允许 INT4
        mt_dirs = sorted({n[len(f'{PREFIX}/models/mt/'):].split('/')[0]
                           for n in names
                           if n.startswith(f'{PREFIX}/models/mt/') and '/' in n[len(f'{PREFIX}/models/mt/'):]})
        print()
        print(f'包内翻译模型目录: {mt_dirs}')
        only_int4 = mt_dirs == ['mt2-int4sym-cw-q']
        print(f'  [{"符合" if only_int4 else "不符"}] v1.3 只附带 INT4')

    print()
    if (missing or stale or stale_prefix or not only_int4 or not files_ok
            or not bytes_ok or spoken_hit or internal_hit):
        print('结论：FAIL')
        return 1
    print(f'结论：PASS  md5={md5(ZIP)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
