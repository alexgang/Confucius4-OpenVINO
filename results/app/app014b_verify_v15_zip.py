r"""app014b_verify_v15_zip.py —— 客户包 zip 的**独立**复核（APP-014② 第⑤步）

🔴 **版本判据参数化**（2026-10-27，APP-028 升 v1.6 时修）
---------------------------------------------------------
本脚本原先把 `MANIFEST version == '1.5'` **写死**在判据里 ⇒ 包一升版
（v1.6）就**必然报 FAIL**，而实际代码可能完全正确 ⇒ **假 FAIL**。
⇒ 现在版本号从 **`pack_v13.PKG_VERSION`（单一数据源）**读，
也可用 `--version` 显式覆盖；**脚本文件名保留 v15**（历史命名，不改）。

为什么要有独立复核脚本
----------------------
`pack_v13.py` 自己会做「zip ⇄ 包目录 逐文件 SHA256」复核，但**同一个脚本
既生产又验证** ⇒ 若它的遍历/过滤逻辑有缺陷，两边会**同时错** ⇒ 复核等于没做。

⇒ 本脚本**完全独立**实现：
  - **不 import** `pack_v13.py` / `pkg_exclude.py`（避免同源缺陷）；
  - zip 内清单**从 zip 本身读**（`namelist()`），不是从包目录推；
  - 用**自己的排除规则**（重新写一遍，且**故意写成显式白名单式关键校验**）；
  - 逐文件 SHA256（读 zip 内字节 vs 读磁盘字节）；
  - MANIFEST 的 files/bytes **独立重算**（全量遍历 zip 条目，不套用任何排除规则）。

⚠️ **版本号是唯一例外**：为避免「版本判据自己过期」，
这里只从 `pack_v13.py` **读一个常量**（不 import 它的任何逻辑）⇒
不存在「同源缺陷」风险（读常量不引入打包逻辑）。

验五组：
  1. **zip 结构**：可打开、`testzip()` 无损坏、顶层目录名正确；
  2. **内容一致**：zip 内每个文件 == 包目录对应文件（SHA256）；
  3. **MANIFEST 自洽**：MANIFEST 的 files/bytes == **zip 条目实算**；
  4. **关键文件齐备**：与 `pack_v13.py` 的 MUST 清单**独立重写**一份；
  5. **不该在的绝不在**：旧量化目录 / 编译缓存 / 音色 B/C / 内部会议内容。

用法
----
    python app014b_verify_v15_zip.py --zip <zip> --pkg <包目录> --prefix <顶层名>
    python app014b_verify_v15_zip.py --zip <zip> --pkg <包目录> --prefix <顶层名> \
        --version 1.6
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile


def _expected_version():
    """期望的包版本（**单一数据源** = `pack_v13.PKG_VERSION`）。

    ⚠️ 只**读常量**：用 `ast` 从源码里抽出 `PKG_VERSION = '...'`
    的字面量，**不 import** `pack_v13`（避免它的执行期副作用，
    同时避免与被复核对象同源）。
    ⇒ 读不到 ⇒ **抛异常**（绝不静默回退到某个硬编码版本，
    否则又会把「判据过期」伪装成「验收通过」）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    src = os.path.join(repo, 'pack_v13.py')
    if not os.path.isfile(src):
        raise FileNotFoundError('找不到 pack_v13.py（版本单一数据源）: %s' % src)
    import ast
    with open(src, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'PKG_VERSION':
                    val = node.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        return val.value
    raise RuntimeError('pack_v13.py 里取不到 PKG_VERSION 字面量')


#: 期望的包版本 —— 默认 **None**，在 main() 里解析（单一数据源
#: `pack_v13.PKG_VERSION` 或 `--version`）。⚠️ 模块级**不放字面量**，
#: 否则「判据里的版本」又会变成第二个需要手工同步的数据源。
EXPECT_VERSION = None

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


# 🔴 关键文件清单（**独立重写**，不 import pack_v13）
MUST = [
    'app/translator.py', 'app/live_caption_app.py', 'app/MANIFEST.json',
    'README_zh.md', 'README_en.md', 'THIRD_PARTY.md',
    'Start_LiveCaption.bat', 'Diagnose.bat',
    'models/mt/mt2-int8sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int8sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int8sym-cw-q/config.json',
    'models/mt/mt2-int8sym-cw-q/chat_template.jinja',
    'models/mt/mt2-int4sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int4sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int4sym-cw-q/config.json',
    'models/mt/mt2-int4sym-cw-q/chat_template.jinja',
    'models/qwen3tts/int8/talker.xml',
    'models/qwen3tts/int8/talker.bin',
    'models/qwen3tts/int8/talker_prefill.xml',
    'models/qwen3tts/int8/talker_prefill.bin',
    'models/qwen3tts/int8/talker_decode.xml',
    'models/qwen3tts/int8/talker_decode.bin',
    'models/qwen3tts/int8/cp_prefill.xml',
    'models/qwen3tts/int8/cp_prefill.bin',
    'models/qwen3tts/int8/cp_decode.xml',
    'models/qwen3tts/int8/cp_decode.bin',
    'models/qwen3tts/int8/code_predictor.xml',
    'models/qwen3tts/int8/code_predictor.bin',
    'models/qwen3tts/int8/tokenizer_encoder.xml',
    'models/qwen3tts/int8/tokenizer_encoder.bin',
    'models/qwen3tts/int8/tokenizer_decoder.xml',
    'models/qwen3tts/int8/tokenizer_decoder.bin',
    'models/qwen3tts/int8/speaker_encoder.xml',
    'models/qwen3tts/int8/speaker_encoder.bin',
    'models/qwen3tts/tokenizer/config.json',
    'models/qwen3tts/tokenizer/tokenizer_config.json',
    'models/qwen3tts/tokenizer/vocab.json',
    'models/qwen3tts/tokenizer/merges.txt',
    'models/qwen3tts/voices/preset_A.wav',
]

# 🔴 不该在 zip 里的目录前缀
MUST_NOT_PREFIX = [
    'models/mt/int4sym-cw-q/', 'models/mt/int8sym-cw-q/',
    'ov_cache/', 'npu_cache/', 'mt_cache/', 'tts_npu_cache/',
    'app/ov_cache/', 'app/npu_cache/', 'app/mt_cache/',
    'app/tts_npu_cache/', 'app/reports/', 'reports/',
    'models/qwen3tts/voices/preset_B', 'models/qwen3tts/voices/preset_C',
    'models/qwen3tts/voices/clone_', 'app/voices/',
]

# 🔴 不该在 zip 里的文件名模式
MUST_NOT_NAME_RE = [
    re.compile(r'_spoken', re.I),
    re.compile(r'preset_B', re.I),
    re.compile(r'preset_C', re.I),
    re.compile(r'clone_[A-Z]', re.I),
    re.compile(r'\.bak', re.I),
    re.compile(r'^transcript_.*\.txt$', re.I),
    re.compile(r'^segments_.*\.json$', re.I),
]

# 🔴 内部内容关键词（与 check_internal_material.py 同口径，独立重写）
CONTENT_PATTERNS = [
    re.compile(rb'\bQ[G]S\b', re.I),
    re.compile(rb'26[0]902'),
    re.compile(rb'b[l]c\s*b[0]', re.I),
    re.compile(rb'5[2]\s*c[o]re', re.I),
    re.compile(rb'L[i]sa will join', re.I),
]
CONTENT_EXT_SKIP = {'.xml', '.bin', '.npy', '.wav', '.mp3', '.flac', '.ogg',
                    '.pcm', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip',
                    '.gz', '.pyc', '.onnx', '.blob', '.m4a', '.aac', '.pyd',
                    '.dll', '.exe'}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True)
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--prefix', required=True)
    ap.add_argument('--no-content', action='store_true',
                    help='跳过逐文件 SHA256（内容级复核）')
    ap.add_argument('--version', default=None,
                    help='期望的包版本（默认从 pack_v13.PKG_VERSION 读）')
    args = ap.parse_args()

    ZIP = args.zip
    PKG = args.pkg
    PREFIX = args.prefix
    global EXPECT_VERSION
    EXPECT_VERSION = args.version or _expected_version()

    print('=' * 70)
    print('v%s zip 独立复核' % EXPECT_VERSION)
    print('  zip   :', ZIP)
    print('  pkg   :', PKG)
    print('  prefix:', PREFIX)
    print('=' * 70)

    if not os.path.isfile(ZIP):
        check('zip 存在', False, ZIP)
        return 1

    # ── ① zip 结构 ────────────────────────────────────────────
    print()
    print('--- (1) zip 结构 ---')
    try:
        zf = zipfile.ZipFile(ZIP, 'r')
    except Exception as e:
        check('zip 可打开', False, '%s: %s' % (type(e).__name__, e))
        return 1
    check('zip 可打开', True)
    bad = zf.testzip()
    check('testzip() 无损坏', bad is None, str(bad))
    names = zf.namelist()
    check('顶层目录名正确',
          all(n.startswith(PREFIX + '/') for n in names if n),
          '样例=%s' % names[:2])
    entries = [n for n in names if not n.endswith('/')]
    print('  条目数（不含目录条目）: %d' % len(entries))

    # ── ② 内容一致性（逐文件 SHA256）──────────────────────────
    print()
    print('--- (2) zip ⇄ 包目录 逐文件 SHA256 ---')
    if args.no_content:
        print('  [skip] --no-content')
    else:
        mism = []
        n = 0
        for name in entries:
            rel = name[len(PREFIX) + 1:] if name.startswith(PREFIX + '/') \
                else name
            disk = os.path.join(PKG, rel.replace('/', os.sep))
            if not os.path.isfile(disk):
                mism.append((rel, '(zip 有 / 磁盘无)', ''))
                continue
            zsha = sha256_bytes(zf.read(name))
            dsha = sha256_file(disk)
            n += 1
            if zsha != dsha:
                mism.append((rel, zsha[:12], dsha[:12]))
        check('全部 %d 个文件逐字节一致' % n, not mism,
              '%d 个不一致' % len(mism))
        for r in mism[:20]:
            print('      ✗', r)

    # ── ③ MANIFEST 自洽（独立重算）─────────────────────────────
    print()
    print('--- (3) MANIFEST 自洽（独立重算 zip 条目）---')
    man_arc = f'{PREFIX}/app/MANIFEST.json'
    try:
        man = json.loads(zf.read(man_arc).decode('utf-8'))
    except Exception as e:
        check('MANIFEST 可读', False, str(e))
        man = {}
    if man:
        check("MANIFEST version == %r" % EXPECT_VERSION,
              man.get('version') == EXPECT_VERSION,
              'version=%r' % man.get('version'))
        # 独立重算：**只减 MANIFEST 自身**（它不计入 files/bytes）
        ent_wo = [n for n in entries if n != man_arc]
        real_bytes = sum(zf.getinfo(n).file_size for n in ent_wo)
        man_bytes = man.get('bytes')
        man_files = man.get('files')
        check('files 一致（zip 条目不含 MANIFEST 自身）',
              len(ent_wo) == man_files,
              'zip=%d man=%s' % (len(ent_wo), man_files))
        check('bytes 一致（zip 原始体积 == MANIFEST bytes）',
              real_bytes == man_bytes,
              'zip=%d man=%s' % (real_bytes, man_bytes))

    # ── ④ 关键文件齐备 ────────────────────────────────────────
    print()
    print('--- (4) 关键文件齐备 ---')
    missing = [r for r in MUST
               if f'{PREFIX}/{r}' not in set(names)]
    check('关键文件 %d 项全部在 zip 内' % len(MUST), not missing,
          str(missing[:5]))

    # ── ⑤ 不该在的绝不在 ──────────────────────────────────────
    print()
    print('--- (5) 不该在的绝不在 ---')
    hit_prefix = []
    for pre in MUST_NOT_PREFIX:
        hits = [n for n in names if n.startswith(f'{PREFIX}/{pre}')]
        if hits:
            hit_prefix.append((pre, len(hits)))
    check('旧量化目录 / 缓存 / 音色 B/C 全部不在 zip 内',
          not hit_prefix, str(hit_prefix))

    hit_name = []
    for n in entries:
        base = n.rsplit('/', 1)[-1]
        if any(rx.search(base) for rx in MUST_NOT_NAME_RE):
            hit_name.append(n)
    check('备份文件 / _spoken / 音色 B/C 全部不在 zip 内',
          not hit_name, str(hit_name[:5]))

    # 内部内容关键词（只扫文本类文件的**前 512 KB**）
    print()
    print('--- (6) 内部内容关键词扫描 ---')
    hits = []
    for n in entries:
        base = n.rsplit('/', 1)[-1]
        ext = os.path.splitext(base)[1].lower()
        if ext in CONTENT_EXT_SKIP:
            continue
        try:
            head = zf.read(n)[:512 * 1024]
        except Exception:
            continue
        for rx in CONTENT_PATTERNS:
            m = rx.search(head)
            if m:
                hits.append((n, m.group(0)[:30]))
                break
    check('zip 内无内部内容关键词', not hits, str(hits[:5]))

    zf.close()
    print()
    print('=' * 70)
    print('独立复核：PASS %d 项 / FAIL %d 项' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  x %s' % f)
    print('=' * 70)
    return 1 if FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
