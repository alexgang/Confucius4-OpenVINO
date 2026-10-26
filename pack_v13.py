r"""pack_v13.py —— 打包客户包并校验（当前版本 v1.5，见 ``PKG_VERSION``）。

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
import re
import sys
import time
import zipfile

# 保证从任意 CWD 运行都能 import 到同目录的 pkg_exclude
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkg_exclude  # noqa: E402

try:
    import machine_lock_app
except Exception:                       # pragma: no cover
    machine_lock_app = None

# ── 客户包版本（单一数据源）────────────────────────────────────────────
# APP-007：打 v1.4。原先三个常量各自写死 "v1.3"，改版本要改三处
# 且 MANIFEST 的 version 是**手填**的（refresh_manifest 从不写它）⇒
# 打包出来的东西自称 v1.3、实际是 v1.4。
# ⇒ 现在版本号只有一个来源（PKG_VERSION），三个常量由它派生。
# APP-014②：打 v1.5（本轮 = 假设备标签修复 + TTS CUDA 选项 + 接缝去重 +
#            TTS 转正式功能默认开启）。
PKG_VERSION = '1.5'
_PKG_NAME = f'Confucius4_LiveCaption_v{PKG_VERSION}'
DEFAULT_PKG = rf'C:\Users\Trekker-PTL\{_PKG_NAME}'
DEFAULT_ZIP = rf'C:\Users\Trekker-PTL\{_PKG_NAME}.zip'
DEFAULT_PREFIX = _PKG_NAME

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
    # 翻译模型：INT8-CW 是**默认**（APP-002 / C-134 用户决定），INT4 保留为可选
    'models/mt/mt2-int8sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int8sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int8sym-cw-q/config.json',
    'models/mt/mt2-int8sym-cw-q/chat_template.jinja',
    'models/mt/mt2-int4sym-cw-q/openvino_model.xml',
    'models/mt/mt2-int4sym-cw-q/openvino_model.bin',
    'models/mt/mt2-int4sym-cw-q/config.json',
    'models/mt/mt2-int4sym-cw-q/chat_template.jinja',
    # TTS（Qwen3-TTS / BabelVox）随包分发（APP-004② / TTS-004 交接单）
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

# 必须**不存在**于 zip 内的**精确**路径
# （旧的 Instruct 产物 / 备份文件 / v1.3 已移除的 INT8）
# ⚠️ 这类是「历史防回归断言」—— 即使当前源目录里没有，价值也不消失。
MUST_NOT_EXACT = [
    'app/translator.py.bak_instruct_20261022',
    'models/mt/int4sym-cw-q/openvino_model.bin',
    'models/mt/int8sym-cw-q/openvino_model.bin',
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
# ⚠️ APP-005②：mt2-int8sym-cw-q **已改为默认模型并随包分发** ⇒ 这里不能再禁它。
MUST_NOT_PREFIX += [
    'models/mt/int8sym-cw-q/',
    'models/mt/int4sym-cw-q/',
]

# 🔴 TTS 音色素材断言（APP-005② 顺手补）
# 客户包**只允许**音色 A（预设音色）。
# 同事音色 B / 克隆音色 C / 任何会议录音一律禁止进包（BRIEF 硬要求）。
MUST_NOT_PREFIX += [
    'models/qwen3tts/voices/preset_B',
    'models/qwen3tts/voices/preset_C',
    'models/qwen3tts/voices/clone_',
    'app/voices/',
]

# 禁止进包的文件名模式（音色 B/C 的 wav/npz 等）
# ⚠️ **注意**：本列表的匹配在硬校验里被**限定在 `models/qwen3tts/` 下**
#    ⇒ 这里放别的规则**不会生效** ⇒ 开发专用脚本的断言单独写
#    （见 `pkg_exclude.is_app_dev_only`）。
MUST_NOT_NAME_RE_LIST = [
    pkg_exclude.SPOKEN_FILE_RE,
    re.compile(r'preset_B', re.I),
    re.compile(r'preset_C', re.I),
    re.compile(r'clone_[A-Z]', re.I),
]


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def verify_zip_matches_pkg(zip_path, pkg_dir, prefix):
    """🔴🔴 **内容级**校验：zip 里的每个文件 == 打 zip 那一刻包目录里的内容。

    为什么必须加这一刀（真实事故，2026-10-23）
    ------------------------------------------
    `pack_v13.py` 是**流式**写 zip 的：遍历包目录 → 逐个 `zf.write()` →
    写完才做 MANIFEST 硬校验 + 关键文件存在性检查。
    **它从不校验「zip 里的内容 == 包目录里的内容」。**

    实测事故（21:00:32 → 21:17:23）：
      - 21:00:32  打包写到 `app/translator.py`（当时是 C-111 旧版）
      - 21:06:56  MT 模块把 C-111-V7 定点同步进包目录（该文件被覆盖）
      - 21:17:23  打包结束、zip 落盘
    ⇒ **zip 里是旧版、包目录里是新版** ⇒ 客户拿到的还是旧的
    ⇒ 而 MANIFEST files/bytes、关键文件 [OK]、符号抽查 **全部 PASS**
    （因为它们**只查存在性与统计口径，不查内容**）。

    ⇒ 本函数用 **SHA256 逐文件**比对，能把「打包期间包目录被改过」直接判 FAIL。

    成本：需要把 zip 全量解压一遍（十几 GB）⇒ 默认**开启**，
    打包总耗时从 ~14 min 增加到 ~20 min；可用 `--no-verify-content` 关掉。

    返回 (ok, n_checked, mismatches)；mismatches 是 (rel, zip_sha, pkg_sha)。
    """
    mismatches = []
    n_checked = 0
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if prefix and name.startswith(prefix + '/'):
                rel = name[len(prefix) + 1:]
            else:
                rel = name
            disk = os.path.join(pkg_dir, rel.replace('/', os.sep))
            if not os.path.isfile(disk):
                mismatches.append((rel, '(zip 有 / 包目录无)', ''))
                continue
            with open(disk, 'rb') as f:
                dbytes = f.read()
            zbytes = zf.read(name)
            n_checked += 1
            if _sha256_bytes(zbytes) != _sha256_bytes(dbytes):
                mismatches.append((rel, _sha256_bytes(zbytes)[:12],
                                   _sha256_bytes(dbytes)[:12]))
    return (not mismatches), n_checked, mismatches


V14_TTS_NOTE = (
    'v1.4 修订（2026-10-23，APP-005② / APP-004 执行后）：'
    '（4）**TTS（Qwen3-TTS / BabelVox）随包分发** —— '
    'models/qwen3tts/（int8 IR 18 文件 + weights 37 文件 + tokenizer + voices/preset_A.wav），'
    '运行时 babelvox 1.7.1 及其依赖（librosa / scipy / num2words / numba / llvmlite / soxr / '
    'soundfile / cloudpickle / joblib / pooch / platformdirs / defusedxml / msgpack / decorator）'
    '以 vendored 方式随包，**客户机离线可跑，无需联网 pip install**；'
    '许可证归属见包根 NOTICE。**只附带音色 A（预设音色）** —— '
    '音色 B / 克隆音色 / 会议录音素材一律不含在包内。'
    '（5）**打包断言已按 INT8 默认模型更新** —— 原「v1.3 只附带 INT4」的断言与目录排除'
    '在 INT8 成为默认后会导致打包必然 FAIL，现改为「INT8 必需 + INT4 可选 + 无旧量化目录」。'
)


V15_APP_NOTE = (
    'v1.5 修订（2026-10-25，APP-014② / APP-012② / APP-014① 执行后）：'
    '（6）**设备下拉按实际硬件显示全名** —— 原先把 NVIDIA 独显误标成'
    '「Intel GPU 2」（该设备不存在），现改为按 OpenVINO 报告的 '
    'FULL_DEVICE_NAME 逐字显示（如「Intel(R) Graphics (iGPU)」/ '
    '「NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)」/「Intel(R) AI Boost」），'
    '查不到全名才回落简写标签。'
    '（7）**语音分区新增 CUDA 选项** —— NVIDIA 设备会在语音设备列表里'
    '单列一条「NVIDIA GPU（CUDA）」。⚠️ **诚实警示：本包内的 OpenVINO 未安装 '
    'CUDA plugin**（`openvino` 包内无 cuda 组件），该选项在 NVIDIA 卡上**仍走 '
    'Intel GPU plugin（Level Zero）**，并非真正的 CUDA 后端；'
    '实测 INT8 TTS IR 在 NVIDIA 独显上 3/7 编译成功（4 个在 FP16↔FP32 reorder '
    '节点报「Could not find a suitable kernel」），集显上 7/7 成功。'
    '（8）**修掉段接缝处的重复词** —— 旧去重只试 3-gram / 2-gram，'
    '而实测段边界的 n-gram 重复分布是 n≥3 = 0、n=2 = 0、n=1 = 36~42 处 ⇒ '
    '**一次都没命中过**，重复词 100% 漏到屏幕上。现改为整词级 1~3-gram，'
    '且 1-gram 用「切点穿词」判据（后段首词大写开头 / 前段末尾非句末标点）'
    '区分「切点穿词」与「真内容」，避免误删真实复读。'
    '（9）**TTS（译文语音输出）转为正式功能，默认开启** —— '
    '去掉「实验性」标注，CLI `--tts` 默认 None（区分「没给」与「显式 off」），'
    'GUI 初值默认开；开关旁常驻「⚠️ 请佩戴耳机，避免回授」提示。'
)


def ensure_v14_notes(data):
    """幂等地保证 notes 里有 v1.4 的 TTS / INT8 修订说明 + v1.5 的本轮修订。

    APP-005②：MANIFEST 的 notes 必须与包内实际内容一致，
    否则就是「对客户不成立的承诺」（C-133 的教训）。
    """
    notes = data.get('notes') or ''
    changed = False
    if '（4）**TTS（Qwen3-TTS / BabelVox）随包分发**' not in notes:
        notes = V14_TTS_NOTE + notes
        changed = True
    if '（6）**设备下拉按实际硬件显示全名**' not in notes:
        notes = V15_APP_NOTE + notes
        changed = True
    data['notes'] = notes
    return changed


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

    # 🔴🔴 **version 必须显式写**（APP-007）。
    #    refresh_manifest 原先只写 files/bytes/packages/notes，
    #    `version` 是**手工填**的 ⇒ 打 v1.4 时包内 MANIFEST 还自称 '1.3'
    #    （客户核对版本号会得到错误结论）。
    old_version = data.get('version')
    data['version'] = PKG_VERSION

    # 🔴 APP-005②：packages 表必须与包内 site-packages 实际一致，
    # 否则客户按 MANIFEST 核对版本会与实机不符（TTS 依赖此前完全没登记）。
    # ⚠️ 包名大小写不统一（Jinja2 vs jinja2）⇒ 按小写归一化去重，
    #    已存在的 key 保留其原有拼写，只更新版本号。
    old_pkgs = data.get('packages') or {}
    new_pkgs = dict(old_pkgs)
    lower2orig = {k.lower(): k for k in old_pkgs}
    for name, ver in collect_installed_packages(pkg).items():
        orig = lower2orig.get(name.lower())
        if orig is not None:
            if old_pkgs.get(orig) != ver:
                new_pkgs[orig] = ver
        else:
            new_pkgs[name] = ver
            lower2orig[name.lower()] = name
    data['packages'] = new_pkgs
    notes_changed = ensure_v14_notes(data)

    with open(path, 'w', encoding='utf-8', newline='') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    added = sorted(set(new_pkgs) - set(old_pkgs))
    changed = sorted(k for k in set(new_pkgs) & set(old_pkgs)
                      if new_pkgs[k] != old_pkgs[k])
    print(f'MANIFEST 刷新: files {old_files} -> {new_files}  '
          f'bytes {old_bytes} -> {new_bytes} ({new_bytes / 1024 ** 3:.2f} GB)')
    print(f'  packages: 新增 {len(added)} 个{added if added else ""}')
    if changed:
        print(f'  packages: 版本变化 {len(changed)} 个{changed if changed else ""}')
    print(f'  notes: {"已追加本轮修订说明" if notes_changed else "已含 v1.4/v1.5 修订说明"}')
    if old_version != PKG_VERSION:
        print(f'  version: {old_version!r} -> {PKG_VERSION!r}')
    return old_files, old_bytes, new_files, new_bytes


def collect_installed_packages(pkg):
    """扫描包内 `python/Lib/site-packages/*.dist-info/METADATA` 拿真实版本。

    只读、stdlib only。返回 {包名: 版本}。
    """
    import re as _re
    sp = os.path.join(pkg, 'python', 'Lib', 'site-packages')
    out = {}
    if not os.path.isdir(sp):
        return out
    try:
        names = os.listdir(sp)
    except OSError:
        return out
    for d in names:
        if not d.endswith('.dist-info'):
            continue
        meta = os.path.join(sp, d, 'METADATA')
        if not os.path.isfile(meta):
            continue
        ver = ''
        try:
            with open(meta, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.startswith('Version:'):
                        ver = line.split(':', 1)[1].strip()
                        break
        except OSError:
            continue
        if not ver:
            continue
        name = d[:-len('.dist-info')]
        # wheel 名是 name-version ⇒ 取第一段作为显示名
        base = name.split('-')[0]
        out[base] = ver
    return out


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
    # 🔴 内部素材闸门（APP-006 第 6 步）—— dry-run 同样要拦
    rc = check_internal_material(pkg)
    if rc:
        print()
        print('结论：FAIL（内部素材闸门未通过）')
        return rc
    print('结论：PASS（dry-run，未写 zip）')
    return 0


def check_internal_material(pkg):
    """打包前内部素材闸门（APP-006 第 6 步）。

    复用独立脚本 `check_internal_material.py`（单一数据源）。
    命中即 **FAIL**，不允许打包 —— 这是防止内部会议素材再次进包的最后一道闸。
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'check_internal_material.py')
    if not os.path.isfile(script):
        print('[warn] 未找到 check_internal_material.py，跳过内部素材闸门')
        return 0
    print()
    print('=' * 70)
    print('内部素材闸门（APP-006 第 6 步）')
    print('=' * 70)
    try:
        r = subprocess.run([sys.executable, script, '--pkg', pkg],
                           capture_output=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f'!! 内部素材闸门执行失败: {e}')
        return 1
    out = r.stdout.decode('utf-8', errors='replace')
    err = r.stderr.decode('utf-8', errors='replace')
    print(out.rstrip())
    if err.strip():
        print(err.rstrip())
    if r.returncode != 0:
        print('⚠️ 内部素材闸门未通过 ⇒ 拒绝打包')
        return 1
    return 0


def check_pkg_path_hardcode():
    """打包前「客户包路径写死」闸门（§48）。

    为什么要有这道闸门（真实事故，2026-10-26）
    ------------------------------------------
    `results/app/test_tts_close_gui_quit_pkg.py` 把客户包版本**写死**成
    `Confucius4_LiveCaption_v1.4`。包一升版，这个「包内验收脚本」就指着
    **旧包**跑 ⇒ 报出 3 项 FAIL ⇒ 看起来像**真回归**，实际只是**脚本过期**。

    ⇒ 同类缺陷还有「会进包的生产模块写死包路径」——
    `tts_cuda.py` 写死 v1.5 的绝对路径 ⇒ 客户机上的包是别的版本/别的路径时
    **音色文件找不到** ⇒ CUDA 后端直接不可用。

    ⇒ 复用独立脚本 `results/app/app049_pkg_path_hardcode_gate.py`
    （**单一数据源**）⇒ 命中即 **FAIL**，不允许打包。
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'results', 'app', 'app049_pkg_path_hardcode_gate.py')
    if not os.path.isfile(script):
        print('[warn] 未找到 app049_pkg_path_hardcode_gate.py，'
              '跳过「包路径写死」闸门')
        return 0
    print()
    print('=' * 70)
    print('包路径写死闸门（§48）')
    print('=' * 70)
    try:
        r = subprocess.run([sys.executable, script],
                           capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f'!! 包路径写死闸门执行失败: {e}')
        return 1
    out = r.stdout.decode('utf-8', errors='replace')
    err = r.stderr.decode('utf-8', errors='replace')
    print(out.rstrip())
    if err.strip():
        print(err.rstrip())
    if r.returncode != 0:
        print('⚠️ 「包路径写死」闸门未通过 ⇒ 拒绝打包')
        print('   修法：用 `pkg_paths.discover_pkg_dir()` / '
              '`pkg_paths.pkg_app_dir()`（单一数据源）')
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=f'打包客户包 v{PKG_VERSION} 并校验')
    ap.add_argument('--pkg', default=DEFAULT_PKG, help='客户包源目录')
    ap.add_argument('--zip', default=DEFAULT_ZIP, help='输出 zip 路径')
    ap.add_argument('--prefix', default=DEFAULT_PREFIX, help='zip 内顶层目录名')
    ap.add_argument('--level', type=int, default=6,
                    help='压缩级别（默认 6；实测 1/6/9 差异 <1%%，不建议改）')
    ap.add_argument('--dry-run', action='store_true',
                    help='只报告将要打包/排除的内容，不写 zip')
    ap.add_argument('--no-verify-content', action='store_true',
                    help='跳过「zip ⇄ 包目录 逐文件 SHA256」内容一致性校验'
                         '（默认开启；关闭可省约 5~6 min 与十几 GB 磁盘读）')
    ap.add_argument('--no-lock', action='store_true',
                    help='不取共享机器锁（默认取；打包是长时重活，会干扰其它模块计时）')
    ap.add_argument('--lock-timeout', type=float, default=10800.0,
                    help='等待共享机器锁的秒数（默认 10800 = 3 小时）'
                         '⚠️ 实测（2026-10-25）：四个模块**轮流**用锁时，'
                         '1 小时的等待不够（TTS 拿了 30 min、MT 又接上）'
                         '⇒ 打包进程会**空等超时退出**（安全：旧包不动、无残留）')
    ap.add_argument('--quiet-seconds', type=float, default=45.0,
                    help='取锁后还要等「安静窗口」的秒数（默认 45）'
                         '🔴 「我持锁」≠「机器空闲」：别的模块的脚本**大多不取锁**'
                         '⇒ 只取锁会被偷跑污染（实测 2026-10-25 16:04：MT 持锁跑批时'
                         'ASR 偷跑同一块 GPU ⇒ MT 计时作废）')
    ap.add_argument('--quiet-timeout', type=float, default=1800.0,
                    help='等待安静窗口的秒数（默认 1800 = 30 min）'
                         '⚠️ 超时 ⇒ **拒绝打包**（不污染别的模块的计时窗口）')
    ap.add_argument('--skip-quiet', action='store_true',
                    help='跳过安静窗口检查（默认**不跳过**；'
                         '仅在明确知道机器空闲时使用）')
    args = ap.parse_args()

    # 🔴 打包是**长时重活**（压缩 13.7 GB + 逐文件 SHA256 复核 11.2 GB zip）
    #    ⇒ 必须持共享机器锁，否则别的模块测速会把它当干扰源（或被它干扰）。
    #    证据：shared/NOTICE_tts_to_app_20261024.md 通知 2；
    #    实测事故 2026-10-23 22:25~22:29（TTS 报 timing_valid=True 假阳性）。
    #    ⚠️ `--dry-run` **不持锁**（只做只读统计，不压缩、不写 zip）。
    if args.dry_run or args.no_lock or machine_lock_app is None:
        if not args.dry_run and machine_lock_app is None:
            print('[warn] 无法 import machine_lock_app ⇒ 未持共享机器锁')
        return _run(args)

    print(f'[lock] 等待共享机器锁（最多等 {args.lock_timeout:.0f}s）…')
    lk = machine_lock_app.LockHeld(module='app-pack', timeout=args.lock_timeout)
    if not lk.acquire():
        print('!! 未能取得共享机器锁 ⇒ 拒绝打包（避免干扰其它模块计时）')
        return 1
    try:
        # 🔴🔴 **第二道闸门：安静窗口**（MT 通知 10 §10.6 明确要求 App 侧加固）
        #    「我持锁」≠「机器空闲」⇒ 别的模块**不取锁**偷跑时，本模块的打包
        #    会污染**它们**的计时 ⇒ 反过来也一样 ⇒ 取锁后必须再等安静窗口。
        if not args.skip_quiet:
            print(f'[lock] 已持锁 ⇒ 等安静窗口（{args.quiet_seconds:.0f}s，'
                  f'最多等 {args.quiet_timeout:.0f}s）…')
            qok, qinfo = lk.wait_quiet(quiet_seconds=args.quiet_seconds,
                                      timeout=args.quiet_timeout)
            if not qok:
                print('!! 未进入安静窗口 ⇒ 拒绝打包'
                      '（宁可不做，也不污染别的模块的计时）')
                print('   采样 %d 次 / 有干扰 %d 次 / 已等 %.0f s'
                      % (qinfo.get('n_samples', 0),
                         qinfo.get('n_busy_samples', 0),
                         qinfo.get('waited_s', 0.0)))
                return 1
        return _run(args)
    finally:
        lk.release()


def _run(args):
    PKG = args.pkg
    ZIP = args.zip
    PREFIX = args.prefix

    if not os.path.isdir(PKG):
        print(f'!! 源目录不存在: {PKG}')
        return 1

    # 🔴🔴 **打包前闸门①**（§48）：包路径写死
    #    ⇒ 「包内验收脚本指向旧包」+「生产模块指向别的版本的绝对路径」
    #       两类缺陷都会**静默**漏到客户手里（打包流水线本身全绿）。
    #    ⚠️ 放在 dry-run **之前** ⇒ 只读、几秒 ⇒ 打包前就能看到问题，
    #       不必等 10 min 打包完才发现。
    rc = check_pkg_path_hardcode()
    if rc:
        print()
        print('结论：FAIL（包路径写死闸门未通过）')
        return rc

    if args.dry_run:
        return do_dry_run(PKG, PREFIX)

    # 🔴 打包前内部素材闸门（APP-006 第 6 步）—— 命中即拒绝打包
    rc = check_internal_material(PKG)
    if rc:
        print()
        print('结论：FAIL（内部素材闸门未通过）')
        return rc

    t0 = time.time()
    print('=' * 70)
    print(f'打包 {PREFIX}')
    print('=' * 70)
    print('源目录:', PKG)
    print('输出  :', ZIP)
    print()

    # ── 打包前刷新 MANIFEST（口径 = 排除后的净载荷，不含 MANIFEST 自身）──
    refresh_manifest(PKG)

    # 🔴🔴 **原子写 zip**：先写临时文件，**校验通过后**才改名到目标路径。
    #
    # 事故（2026-10-24 17:19 实测）：并行会话在写 zip 途中被中断
    # ⇒ 直接写目标路径 ⇒ **好包被截断覆盖**：
    #   `Confucius4_LiveCaption_v1.4.zip` = 3 513 053 709 B（非有效 zip，
    #   `zipfile.BadZipFile: File is not a zip file`），
    #   而 FTP_Share 里的旧副本仍是 11 216 038 195 B 的完好包。
    # ⇒ **旧 zip 在打包成功前绝不能被动**（客户手里的包必须是最后一个完好版本）。
    # ⇒ 流程：写 `ZIP + '.tmp'` → 校验（testzip + 关键文件 + 内容级复核）
    #   → `os.replace()` 原子改名 → 删除临时文件（异常路径）。
    tmp_zip = ZIP + '.tmp'
    if os.path.exists(tmp_zip):
        # 上次中断留下的临时文件 ⇒ 先尽力删除（失败也不阻断：'w' 会覆盖）
        try:
            os.remove(tmp_zip)
            print(f'已清理上次残留的临时 zip: {tmp_zip}')
        except OSError as e:
            print(f'[warn] 清理临时 zip 失败（不影响打包，zipfile 会覆盖写）: {e}')

    n_files = 0
    total_raw = 0
    try:
        with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=args.level, allowZip64=True) as zf:
            for rel, size in pkg_exclude.iter_package_files(PKG):
                full = os.path.join(PKG, rel.replace('/', os.sep))
                arc = f'{PREFIX}/{rel}'
                zf.write(full, arc)
                n_files += 1
                total_raw += size
                if n_files % 2000 == 0:
                    print(f'  ... {n_files} 文件')
    except BaseException as e:
        # 🔴 写失败 ⇒ **保留旧包不动**，只清临时文件
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except OSError:
            pass
        print(f'!! 打包失败（已保留原有 zip 不变）: {type(e).__name__}: {e}')
        raise

    sz = os.path.getsize(tmp_zip)
    print()
    print(f'文件数     : {n_files}')
    print(f'原始字节   : {total_raw}')
    print(f'压缩后字节 : {sz}  ({sz / 1024 ** 3:.2f} GB)')
    print(f'压缩率     : {sz / total_raw * 100:.1f}%')
    print(f'耗时       : {time.time() - t0:.0f}s')
    print()

    print('-' * 70)
    print('testzip() 校验…')
    # ⚠️ 校验在**临时文件**上做（不是目标 ZIP）⇒ 失败时旧包完好无损
    try:
        ok = _verify_and_report(tmp_zip, args, PKG, PREFIX)
    except BaseException as e:
        # 🔴 校验阶段异常 ⇒ **不改名**（旧包保持原样）+ 清理临时文件
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
        except OSError:
            pass
        print(f'!! 校验阶段异常（已保留原有 zip 不变）: {type(e).__name__}: {e}')
        raise
    return _finish(ZIP, tmp_zip, ok)


def _verify_and_report(ZIP, args, PKG, PREFIX):
    """在 ZIP（临时文件）上做全部校验并打印报告。返回 True=全部通过。

    🔴 **不在这里改名** —— 改名由 `_finish()` 在全部校验通过后做。
    """
    # 🔴 预置：下面 `with` 块里才赋值，但**函数末尾的 FAIL 判定**要用
    #    ⇒ 必须先给默认值，否则某些提前 return 的路径会 NameError。
    certain = []
    suspect = []
    with zipfile.ZipFile(ZIP, 'r') as zf:
        bad = zf.testzip()
        if bad is None:
            print('  Everything is Ok')
        else:
            print('  !!! 损坏条目:', bad)
            return False

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

        # 🔴🔴 第三方自带素材断言（APP-018 第 2 条 / APP-019）
        #   babelvox 自带 speaker profile（第三方音色）
        #   scipy 自带测试 wav（第三方音频素材）
        #   ⇒ 授权边界必须干净 ⇒ 一个都不许在 zip 里。
        noise_hit = sorted(
            n for n in names
            if pkg_exclude.is_third_party_noise(
                n[len(PREFIX) + 1:] if n.startswith(PREFIX + '/') else n)
        )
        print()
        print('第三方自带素材应已移除（babelvox 内置音色 / scipy 测试 wav）：')
        print(f'  [{"已移除" if not noise_hit else "仍在"}] 第三方素材 '
              f'（{len(noise_hit)} 条命中）')
        for n in noise_hit[:20]:
            print(f'      ⚠️ {n}')

        # MANIFEST 硬校验
        man = json.loads(zf.read(f'{PREFIX}/{MANIFEST_REL}').decode('utf-8'))
        entries = [n for n in names if not n.endswith('/')]
        zip_bytes = sum(zf.getinfo(n).file_size for n in entries)
        man_files = man.get('files')
        man_bytes = man.get('bytes')
        # 🔴 MANIFEST 自身**不计入**统计口径（否则自引用：它写的 bytes
        #    会改变它自己的长度）⇒ zip 条目里要**减掉** MANIFEST 这一条。
        #    ⚠️ 2026-10-23 修：原先 `files_ok` 直接拿 `len(entries)` 比
        #    `man_files`，而 `entries` **含** MANIFEST ⇒ 永远差 1 ⇒
        #    打包结论恒为 FAIL（bytes 那行补了体积、files 这行没减条数，
        #    两个校验口径不一致）。v1.4 首次打包实测：zip 13978 条 vs
        #    MANIFEST 13977 ⇒ 误报 FAIL，而 zip 内容与包目录**逐条一致**。
        man_arc = f'{PREFIX}/{MANIFEST_REL}'
        man_size = zf.getinfo(man_arc).file_size
        entries_wo_manifest = [n for n in entries if n != man_arc]
        files_ok = (len(entries_wo_manifest) == man_files)
        bytes_ok = (zip_bytes == man_bytes + man_size)
        print()
        print(f'MANIFEST version = {man["version"]}  files={man_files}  bytes={man_bytes}')
        print(f'  [{"OK" if files_ok else "不符"}] zip 条目 {len(entries_wo_manifest)} '
              f'（不含 MANIFEST 自身；含则 {len(entries)}）== MANIFEST files {man_files}')
        print(f'  [{"OK" if bytes_ok else "不符"}] zip 原始体积 {zip_bytes} '
              f'== MANIFEST bytes {man_bytes} + MANIFEST 自身 {man_size}')

        # translator.py 关键符号抽查
        src = zf.read(f'{PREFIX}/app/translator.py').decode('utf-8')
        syms = ['mt2-int8sym-cw-q', '_TRANSLATE_INSTR', 'Default Translation',
                'stop_strings = set()', 'split_sentences']
        print()
        print('translator.py 符号抽查：')
        for s in syms:
            print(f'  [{"有" if s in src else "缺"}] {s}')

        # 翻译模型目录清单：INT8-CW 是默认（必须带），INT4 是可选项（可带可不带）
        # ⚠️ APP-005②：原来是 `mt_dirs == ['mt2-int4sym-cw-q']`（只允许 INT4），
        #    但 INT8 已是默认模型并随包 ⇒ 原判定会让打包必然 FAIL。
        mt_dirs = sorted({n[len(f'{PREFIX}/models/mt/'):].split('/')[0]
                           for n in names
                           if n.startswith(f'{PREFIX}/models/mt/') and '/' in n[len(f'{PREFIX}/models/mt/'):]})
        print()
        print(f'包内翻译模型目录: {mt_dirs}')
        int8_ok = 'mt2-int8sym-cw-q' in mt_dirs
        # 旧量化目录（无 `mt2-` 前缀）一律不允许出现
        legacy_ok = not [d for d in mt_dirs if d in ('int4sym-cw-q', 'int8sym-cw-q')]
        print(f'  [{"符合" if int8_ok else "不符"}] 默认 INT8-CW 目录在包内')
        print(f'  [{"符合" if legacy_ok else "不符"}] 无旧量化目录（int4sym-cw-q / int8sym-cw-q）')
        mt_dirs_ok = int8_ok and legacy_ok

        # 🔴 TTS 音色素材断言（APP-005②）
        # 客户包只允许音色 A；音色 B / C / 克隆素材 / 会议录音一律不许进包。
        tts_bad = sorted(
            n for n in names
            if any(rx.search(n.rsplit('/', 1)[-1]) for rx in MUST_NOT_NAME_RE_LIST)
            and n.startswith(f'{PREFIX}/models/qwen3tts/')
        )
        print()
        print('TTS 音色素材（只允许音色 A）：')
        print(f'  [{"已移除" if not tts_bad else "仍在"}] 音色 B/C/克隆素材 '
              f'（{len(tts_bad)} 条命中）')
        for n in tts_bad[:20]:
            print(f'      ⚠️ {n}')

        # 🔴 开发专用脚本断言（app/ 下的 `_` 前缀，如 `_probe_tts_cuda.py`）
        #    ⚠️ **不能**复用 MUST_NOT_NAME_RE_LIST —— 那个列表的匹配被
        #    「限定在 models/qwen3tts/ 下」⇒ 在这里加规则不会生效。
        #    ⇒ 单独按 `pkg_exclude.is_app_dev_only` 判定（单一数据源）。
        devonly_hit = sorted(
            n for n in names
            if pkg_exclude.is_app_dev_only(n[len(PREFIX) + 1:])
        )
        print()
        print('开发专用脚本（app/ 下的 `_` 前缀）：')
        print(f'  [{"已移除" if not devonly_hit else "仍在"}] 开发专用脚本 '
              f'（{len(devonly_hit)} 条命中）')
        for n in devonly_hit[:20]:
            print(f'      ⚠️ {n}')

        # 🔴🔴 **包内本地模块导入完整性**（APP-042）
        #    真实故障形态：同步脚本给 `app/live_caption_app.py` 加了
        #    `import caption_render`，却**漏了复制** `caption_render.py`
        #    ⇒ 客户包启动即 `ModuleNotFoundError`，
        #    而打包流水线**全绿**（zip 完整 / MANIFEST 一致 / 逐字节一致）
        #    ⇒ **缺陷直接漏到客户手里**。
        #    ⇒ 这道断言是「包能不能跑」的最后一道闸门。
        #    ⚠️ 判据只查**包内 `app/` 下的 `.py`**（客户包的本地模块都在这），
        #       第三方依赖（numpy / soundcard）不在 `app/` 下 ⇒ 不报。
        #    ⚠️ 用 `ast` **静态**解析，不 import、不执行任何包内代码。
        app_py_in_zip = sorted(
            n for n in names
            if n.startswith(f'{PREFIX}/app/') and n.endswith('.py')
        )
        # zip 内 app/ 的模块名清单（比包目录更权威 —— 这是真正要交付的内容）
        zip_app_modules = {n.rsplit('/', 1)[-1][:-3] for n in app_py_in_zip}
        missing_local = []
        for n in app_py_in_zip:
            try:
                src = zf.read(n).decode('utf-8')
            except (KeyError, UnicodeDecodeError):
                continue
            # 🔴 去重：同一文件里同一模块可能 import 多次 ⇒ 只报一次
            seen_mod = set()
            for mod in pkg_exclude._iter_local_imports(src):
                if mod in seen_mod:
                    continue
                seen_mod.add(mod)
                if mod in zip_app_modules:
                    continue
                if mod in pkg_exclude._LOCAL_MODULE_ALLOW:
                    continue
                missing_local.append((n[len(PREFIX) + 1:], mod))
        # 「确定缺失」= 仓库 `live_caption/` 里确实有同名 `.py`
        repo_modules = set()
        repo_live = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'live_caption')
        if os.path.isdir(repo_live):
            repo_modules = {fn[:-3] for fn in os.listdir(repo_live)
                            if fn.endswith('.py')}
        certain = [(f, m) for f, m in missing_local if m in repo_modules]
        suspect = [(f, m) for f, m in missing_local if m not in repo_modules]
        print()
        print('包内本地模块导入完整性（app/ 下互引）：')
        print(f'  zip 内 app/*.py = {len(app_py_in_zip)} 个；'
              f'检查出 {len(certain)} 条确定缺失 / {len(suspect)} 条疑似')
        print(f'  [{"OK" if not certain else "缺失"}] 确定缺失的本地模块 '
              f'（{len(certain)} 条）')
        for f, m in certain[:20]:
            print(f'      ⚠️ {f}  →  import {m}（仓库有 {m}.py，包内没有）')
        if suspect:
            print(f'  [提示] 疑似第三方依赖（不判负）：{len(suspect)} 条')
            for f, m in suspect[:10]:
                print(f'      · {f}  →  {m}')

    print()
    # 🔴🔴 **内容级**校验：zip ⇄ 包目录 逐文件 SHA256（防「打包期间包目录被改过」）
    content_ok = True
    if not args.no_verify_content:
        print('=' * 70)
        print('内容一致性校验（zip ⇄ 包目录，逐文件 SHA256）')
        print('=' * 70)
        content_ok, n_chk, mism = verify_zip_matches_pkg(ZIP, PKG, PREFIX)
        print(f'  比对 {n_chk} 个文件')
        if content_ok:
            print('  [{"OK" if content_ok else "不符"}] 全部逐字节一致')
        else:
            print(f'  ✗ 内容不一致 {len(mism)} 个文件：')
            for rel, zs, ds in mism[:30]:
                print(f'      {rel}  zip [{zs}] != 包目录 [{ds}]')
            print('  ⇒ **打包期间包目录被改过**（同步/打包竞态）'
                  ' ⇒ 客户拿到的是旧内容。')
            print('    修法：确认包目录已定稿后**重跑 pack_v13.py**（不要手动改 zip）。')
    else:
        print('[skip] 内容一致性校验（--no-verify-content）')

    print()
    if (missing or stale or stale_prefix or not mt_dirs_ok or not files_ok
            or not bytes_ok or spoken_hit or internal_hit or tts_bad
            or noise_hit or certain or not content_ok):
        print('结论：FAIL')
        return False
    return True


def _finish(ZIP, tmp_zip, ok):
    """校验结束后的收尾：PASS ⇒ 原子改名；FAIL ⇒ 丢弃临时文件（旧包不动）。"""
    if not ok:
        # FAIL 路径：校验没通过 ⇒ 不改名 ⇒ 旧包（若存在）保持原样
        try:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
            print(f'[info] 校验未通过 ⇒ 已丢弃临时 zip，原 {ZIP} 未被改动')
        except OSError as e:
            print(f'[warn] 清理临时 zip 失败: {e}')
        return 1
    # 🔴🔴 全部校验通过 ⇒ **原子改名**把临时文件变成正式包
    #    （`os.replace` 在同一卷上是原子操作 ⇒ 客户永远看不到半个包）
    os.replace(tmp_zip, ZIP)
    print(f'[info] 校验通过 ⇒ 已原子改名到正式路径: {ZIP}')
    print(f'结论：PASS  md5={md5(ZIP)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
