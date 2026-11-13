# -*- coding: utf-8 -*-
r"""_app524 — **MiniMVP rc11 构建**（APP-107 + APP-106 §2）。

rc11 = rc10 + APP-107（MiniMVP 翻译模型改 **INT8-CW**）+ APP-106 §2（README 实测口径）：

  1. **§1.1 翻译模型换成 INT8-CW**：`models/mt/` 下**只放** `mt2-int8sym-cw-q`
     （拷贝源 `hy_bench\ov\mt2-int8sym-cw-q`，12 文件 / 1 812 121 487 B），
     **不再带 INT4**（rc10 的 `mt2-int4sym-cw-q` 在**拷贝时就不进来**）。
  2. **§1.2 默认 / 「自动」档 = INT8-CW**：包内只有 INT8 ⇒ `DEFAULT_MODEL`
     命中 `models/mt/mt2-int8sym-cw-q` ⇒ 「（默认）」标记与 `auto` label
     都落到 INT8（**行为级断言**，不是查字面）。
  3. **§1.3 模型身份核对**：MANIFEST 增加 `mt/mt2-int8sym-cw-q` 条目
     （拷贝源路径 + **每个 bin/xml 的 SHA256** + 与源目录逐个一致 +
     config `hidden_size 2048` / `num_hidden_layers 32` + INT8_SYM 按通道）。
  4. **§1.4 / APP-106 §2 README 数字**：每个数字都注明**设备组合**，
     并补上**本包出厂默认下的整链 ASR RTF 与 TTS 提交/播完/丢弃**
     （数字来自 `app526_rc11_chain_measurements.json`，**打包时缺它就拒绝**）。
  5. **§1.5 EXT 仍嵌 v0.4.8**，照旧注明在 MiniMVP 里不可用。

⚠️ rc10 **原样保留**（APP-055：不覆盖、不删除）；本脚本只写 rc11 目录与 rc11 zip。

  1. **§7 出厂默认第 2 代**：ASR=GPU.0 / MT=GPU.0 / TTS=NPU
     （`device_config.py::_DEFAULT_DEVICES_MINIMVP`），
     `CONFIG_DEFAULTS_VERSION` 8 → 9（rc9 写的配置按「旧默认」忽略设备项）。
  2. **§1 `Start_Bridge.bat` 能拉起启动器**：CRLF + **只含 ASCII** 的 REM
     ⇒ 打包闸门：**包内所有 `*.bat` 必须 CRLF 且只含 ASCII**
     （含**反证自测**：造一个坏 bat ⇒ 闸门必须报错）。
  3. **§2 不带 `bridge_token.txt`**：黑名单 `bridge_token*` / `*.pid` / `*.log`
     ⇒ 出包前清理 + 闸门断言剩余 **0**（含反证自测）。
  4. **§3 EXT 在 MiniMVP 里 ASR 不可用** ⇒ README 与 `ext/USER_GUIDE.md`
     **如实写明**（不写会让人以为能用的步骤）。
  5. **§4 README 文字修正**：
     · perftest「已知问题」里那句错的「TTS/MT 都放 GPU.0 ⇒ ASR 必须放 NPU」
       改成「**ASR 与 MT 同放 GPU.0**」；
     · `%LOCALAPPDATA%Confucius4LiveCaption` **补反斜杠**；
     · README_en 的「What is inside」表格**整张英文**（与中文表**同源生成**）。

用法：
    python results/app/_app524_build_minimvp_rc11.py --dry-run
    python results/app/_app524_build_minimvp_rc11.py --run
    python results/app/_app524_build_minimvp_rc11.py --zip
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')
BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc10')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11')
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc11'
VERSION = '1.0-rc11'
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
REPORT = os.path.join(HERE, 'app524_minimvp_rc11_build_evidence.json')
ACCEPT_REPORT = os.path.join(HERE, 'app526_app107_rc11_acceptance.json')
#: 🔴 APP-107 §1.4 / APP-106 §2：README 里的「A 机实测」数字**从验收 json 生成**
#:   ⇒ **打 zip 时缺这个文件 ⇒ 拒绝打包**（fail-closed，不许带占位符出包）。
MEAS_PATH = os.path.join(HERE, 'app526_rc11_chain_measurements.json')

EXT_VERSION = '0.4.8'
EXT_COMMIT = '817abcbe30c213844cda6f32c81361524ab53de8'
LEGACY_DIR = 'ov-dec-06b-embed-mask2-int8sym'
STATEFUL_MODULE = 'asr06b_stateful_backend.py'

#: 🔴🔴🔳 APP-105 §2：出包**黑名单**（运行期产物 / 令牌 ⇒ 绝不能随包分发）。
#:   `bridge_token*`：EXT 桥接的令牌（A 本机生成 ⇒ 所有装机共用 A 的令牌，
#:   而启动器又有「允许局域网访问」选项 ⇒ 安全风险）。
#:   `*.pid` / `*.log`：运行期残留（PID 文件 / 日志）。
BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']

#: README 里**禁止出现**的字面（APP-104 §2 的验收口径）。
README_FORBIDDEN = [r'rc5', r'rc6', r'--tts-device NPU', r'2\.71', r'3\.35']

#: 🔴 APP-105 §4：**这两句是错的**，不得再出现在 README 里。
README_FORBIDDEN_APP105 = [
    r'TTS/MT 都放 GPU\.0',                 # 旧口径：把 MT+TTS 写成会崩
    r'ASR 必须放 NPU',                      # 旧口径：与新出厂默认矛盾
    r'%LOCALAPPDATA%Confucius4LiveCaption',  # 少了反斜杠
]

#: README/文档里**禁止出现**的开发机绝对路径（APP-104 §3）
DEV_PATH_FORBIDDEN = ['live_dub_ext', 'C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v']

#: zip 体积字段的**固定宽度**（⇒ README 长度不随数字变化 ⇒ zip 体积自洽）
NUM_WIDTH = 16


# ══════════════════════════════════════════════════════════════
# 基础工具
# ══════════════════════════════════════════════════════════════
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_stats(root):
    n = b = 0
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            try:
                b += os.path.getsize(os.path.join(dp, f))
                n += 1
            except OSError:
                pass
    return n, b


def copy_dev_files(dst_app, names):
    out = []
    for name in names:
        src = os.path.join(DEV, name)
        dst = os.path.join(dst_app, name)
        if not os.path.isfile(src):
            raise RuntimeError('dev 树缺文件：%s' % src)
        data = open(src, 'rb').read().replace(b'\r\n', b'\n')
        with open(dst, 'wb') as f:
            f.write(data)
        if open(dst, 'rb').read() != data:
            raise RuntimeError('写入后复核不一致：%s' % name)
        out.append(name)
    return out


def write_text(path, text):
    """写 UTF-8 + LF（不落 CRLF）。"""
    data = text.replace('\r\n', '\n').encode('utf-8')
    with open(path, 'wb') as f:
        f.write(data)
    return len(data)


def write_bat_crlf(path, text):
    """写 **CRLF + 只含 ASCII** 的 bat（APP-105 §1）。

    🔴 **两个坑**（reviewer 实测）：
      ① **LF 行尾**的 bat 在中文代码页（936）下 `cmd` 会把行**粘在一起**
         ⇒ 报「'EXT' 不是内部或外部命令」⇒ **启动器根本拉不起来**；
      ② REM 里的 **UTF-8 中文**在 936 代码页下是乱码 ⇒ 同样会让 `cmd`
         解析失败（reviewer 实测：`chcp 65001` 也一样失败）。
    ⇒ bat 一律：**CRLF 行尾** + **纯 ASCII**。
    """
    if '\r' in text:
        raise RuntimeError('bat 正文里不该有 CR：%r' % text[:60])
    try:
        text.encode('ascii')
    except UnicodeEncodeError as e:
        raise RuntimeError('bat 里出现非 ASCII 字节（%s）' % e)
    data = text.replace('\n', '\r\n').encode('ascii')
    with open(path, 'wb') as f:
        f.write(data)
    # 写后自检
    rb = open(path, 'rb').read()
    if rb != data:
        raise RuntimeError('bat 写入后复核不一致：%s' % path)
    if b'\n' in rb.replace(b'\r\n', b''):
        raise RuntimeError('bat 里存在裸 LF：%s' % path)
    if any(x > 127 for x in rb):
        raise RuntimeError('bat 里存在非 ASCII 字节：%s' % path)
    return len(rb)


# ══════════════════════════════════════════════════════════════
# APP-105 §1：包内所有 *.bat 必须 CRLF + ASCII-only
# ══════════════════════════════════════════════════════════════
#: 🔴 rc9 的三个 bat 里有两个 REM 是中文（`Start_LiveCaption.bat` /
#:   `Diagnose.bat`），一个整体是 LF（`Start_Bridge.bat`）
#:   ⇒ rc10 全部重写为 **ASCII + CRLF**（**命令语义一字不改**）。
BAT_FILES = {
    'Start_Bridge.bat': """@echo off
REM Start_Bridge.bat - launch the EXT real-time dubbing bridge (EXT v0.4.8)
REM (APP-104 s3: relative paths only, no developer-machine paths)
REM (APP-105 s1: CRLF line endings + ASCII only, so it also runs on codepage 936)
setlocal
cd /d "%~dp0"
if not exist "python\\pythonw.exe" (
  echo [EXT] package interpreter not found: python\\pythonw.exe
  pause
  exit /b 2
)
start "Confucius4 EXT Bridge" "%~dp0python\\pythonw.exe" "%~dp0tools\\ext_launcher.py"
endlocal
""",
    'Start_LiveCaption.bat': """@echo off
rem Confucius4 Live Caption / Live Captions
cd /d "%~dp0"
set PYTHONNOUSERSITE=1
set PYTHONUTF8=1
rem APP-098 2.1: keep UTF-8 output when it is redirected to a file
set PYTHONIOENCODING=utf-8
set PYTHONPATH=
set PYTHONHOME=
start "" "%~dp0python\\pythonw.exe" -s "%~dp0app\\live_caption_app.py" %*
""",
    'Diagnose.bat': """@echo off
rem Environment check: devices, available backends, microphones
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONNOUSERSITE=1
set PYTHONUTF8=1
rem APP-098 2.1: keep UTF-8 output when it is redirected to a file
set PYTHONIOENCODING=utf-8
set PYTHONPATH=
set PYTHONHOME=
"%~dp0python\\python.exe" -s "%~dp0app\\live_caption_app.py" --check
echo.
pause
""",
}


def check_bats(pkg_root):
    """包内所有 `*.bat` 必须是 **CRLF** 且 **只含 ASCII**（APP-105 §1）。"""
    rows = []
    for dp, _dn, fn in os.walk(pkg_root):
        for f in fn:
            if not f.lower().endswith('.bat'):
                continue
            p = os.path.join(dp, f)
            b = open(p, 'rb').read()
            crlf = b.count(b'\r\n')
            bare_lf = b.count(b'\n') - crlf
            non_ascii = sum(1 for x in b if x > 127)
            rows.append({
                'file': os.path.relpath(p, pkg_root).replace('\\', '/'),
                'bytes': len(b), 'crlf': crlf, 'bare_lf': bare_lf,
                'non_ascii_bytes': non_ascii,
                'pass': (bare_lf == 0 and non_ascii == 0 and crlf > 0),
            })
    rows.sort(key=lambda r: r['file'])
    return rows


def bat_gate_selftest():
    """**反证自测**：闸门必须能抓到「LF + 非 ASCII」的坏 bat。"""
    out = []
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, 'good.bat')
        write_bat_crlf(good, '@echo off\r\necho hi\r\n'.replace('\r', ''))
        rows = check_bats(td)
        out.append({'case': 'good_crlf_ascii', 'n_rows': len(rows),
                    'all_pass': all(r['pass'] for r in rows),
                    'expected_pass': True,
                    'pass': all(r['pass'] for r in rows)})
        bad_lf = os.path.join(td, 'bad_lf.bat')
        with open(bad_lf, 'wb') as f:
            f.write(b'@echo off\necho hi\n')
        rows = check_bats(td)
        out.append({'case': 'bad_bare_lf', 'n_fail': sum(1 for r in rows
                                                        if not r['pass']),
                    'expected_fail': True,
                    'pass': any(not r['pass'] for r in rows)})
        os.remove(bad_lf)
        bad_enc = os.path.join(td, 'bad_enc.bat')
        with open(bad_enc, 'wb') as f:
            f.write('@echo off\r\nREM 中文\r\n'.encode('utf-8'))
        rows = check_bats(td)
        out.append({'case': 'bad_non_ascii', 'n_fail': sum(1 for r in rows
                                                           if not r['pass']),
                    'expected_fail': True,
                    'pass': any(not r['pass'] for r in rows)})
    return out


# ══════════════════════════════════════════════════════════════
# APP-105 §2：黑名单清理 + 闸门
# ══════════════════════════════════════════════════════════════
def _blacklist_hit(rel):
    import fnmatch
    name = os.path.basename(rel).lower()
    for pat in BLACKLIST_PATTERNS:
        if fnmatch.fnmatch(name, pat.lower()):
            return pat
    return None


def find_blacklist(pkg_root):
    hits = []
    for dp, _dn, fn in os.walk(pkg_root):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), pkg_root).replace('\\', '/')
            pat = _blacklist_hit(rel)
            if pat:
                hits.append({'file': rel, 'pattern': pat,
                             'bytes': os.path.getsize(os.path.join(dp, f))})
    hits.sort(key=lambda h: h['file'])
    return hits


def purge_blacklist(pkg_root, ev):
    """把黑名单文件从包里**删掉**（出包前）⇒ 记录删了什么。"""
    hits = find_blacklist(pkg_root)
    removed = []
    for h in hits:
        p = os.path.join(pkg_root, h['file'].replace('/', os.sep))
        try:
            os.remove(p)
            removed.append(h)
        except OSError as e:
            raise RuntimeError('删不掉黑名单文件 %s：%r' % (h['file'], e))
    ev['blacklist'] = {'patterns': BLACKLIST_PATTERNS,
                       'n_found': len(hits), 'n_removed': len(removed),
                       'removed': removed}
    return removed


def blacklist_gate_selftest():
    """**反证自测**：闸门必须能抓到黑名单文件。"""
    out = []
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, 'ext'))
        open(os.path.join(td, 'ext', 'bridge_token.txt'), 'w').close()
        open(os.path.join(td, 'x.pid'), 'w').close()
        open(os.path.join(td, 'y.log'), 'w').close()
        open(os.path.join(td, 'ok.txt'), 'w').close()
        hits = find_blacklist(td)
        out.append({'case': 'blacklist_detected', 'n_hits': len(hits),
                    'expected': 3, 'pass': len(hits) == 3})
        purge_blacklist(td, {})
        after = find_blacklist(td)
        out.append({'case': 'blacklist_purged', 'n_hits': len(after),
                    'expected': 0, 'pass': len(after) == 0})
    return out




# ══════════════════════════════════════════════════════════════
# APP-107 §1.1 / §1.3：翻译模型换成 **INT8-CW**（只带 INT8，不带 INT4）
# ══════════════════════════════════════════════════════════════
#: 🔴 **拷贝源必须是 MT 模块的导出产物**（APP-107 §1.1 原文）：
#:   `C:\Users\Trekker-PTL\hy_bench\ov\mt2-int8sym-cw-q`
#:   （**v2.4 包里那份只能用来对照，不能当拷贝源**）。
MT_INT8_SRC = os.path.join(HOME, 'hy_bench', 'ov', 'mt2-int8sym-cw-q')
MT_INT8_DIR = 'mt2-int8sym-cw-q'
MT_INT4_DIR = 'mt2-int4sym-cw-q'
#: APP-107 §1.3 要求写明的量化口径与模型维度（**从 config.json 实测核对**）
MT_INT8_META = {'quantization': 'INT8_SYM',
                'scheme': 'symmetric, per-channel weight (cw-q)',
                'hidden_size': 2048, 'num_hidden_layers': 32,
                'source_model': 'Hy-MT2-1.8B'}


def copy_mt_int8(pkg_root, ev):
    """把 INT8-CW 翻译模型拷进包里，并**逐文件 SHA256** 与源目录对拍。

    🔴 APP-107 §1.3：**MANIFEST 要记录拷贝源路径 + 每个 bin/xml 的 SHA256，
       且与源目录逐个一致** ⇒ 这里逐文件算 SHA，比对不符直接终止。
    """
    dst = os.path.join(pkg_root, 'models', 'mt', MT_INT8_DIR)
    if not os.path.isdir(MT_INT8_SRC):
        raise RuntimeError('INT8 拷贝源不存在：%s' % MT_INT8_SRC)
    os.makedirs(dst, exist_ok=True)
    rows = []
    for nm in sorted(os.listdir(MT_INT8_SRC)):
        s = os.path.join(MT_INT8_SRC, nm)
        if os.path.isdir(s):
            continue
        d = os.path.join(dst, nm)
        shutil.copyfile(s, d)
        ss, ds = sha256_file(s), sha256_file(d)
        if ss != ds:
            raise RuntimeError('INT8 模型拷贝后 SHA 不一致：%s' % nm)
        rows.append({'name': nm, 'bytes': os.path.getsize(d),
                     'sha256': ds, 'source_sha256': ss, 'match': True})
    if not rows:
        raise RuntimeError('INT8 拷贝源是空的：%s' % MT_INT8_SRC)
    # 🔴 APP-107 §1.1/§2：包里**不能**再有 INT4
    int4 = os.path.join(pkg_root, 'models', 'mt', MT_INT4_DIR)
    if os.path.isdir(int4):
        raise RuntimeError('包里还有 INT4 翻译模型：%s' % int4)
    cfg = json.load(open(os.path.join(dst, 'config.json'), encoding='utf-8'))
    dims = {'hidden_size': cfg.get('hidden_size'),
            'num_hidden_layers': cfg.get('num_hidden_layers')}
    if dims != {'hidden_size': MT_INT8_META['hidden_size'],
                'num_hidden_layers': MT_INT8_META['num_hidden_layers']}:
        raise RuntimeError('INT8 config 维度不符（要 2048 / 32）：%r' % dims)
    ev['mt_int8'] = {'source': MT_INT8_SRC, 'dst': dst, 'n_files': len(rows),
                     'bytes': sum(r['bytes'] for r in rows),
                     'all_match': True, 'files': rows, 'config': dims,
                     'meta': MT_INT8_META, 'int4_absent': True}
    return ev['mt_int8']


def probe_mt_default(pkg_root, ev):
    """**行为级**断言：包内 `translator` 的默认模型是 INT8-CW。

    🔴 不查字面，查**实载**：DEFAULT_MODEL 指向哪个目录、「（默认）」标记
       落在哪一档、`auto` 的 label、`MT_ENGINES` 里还有没有 INT4 项。
    """
    py = os.path.join(pkg_root, 'python', 'python.exe')
    app = os.path.join(pkg_root, 'app')
    code = ('import json,os,translator;'
            'print(json.dumps({"default_model":str(translator.DEFAULT_MODEL),'
            '"default_quant":translator._default_quant_tag(),'
            '"auto_label":translator._AUTO_LABEL,'
            '"mt_engines":sorted(translator.MT_ENGINES.keys()),'
            '"bundled_int8":translator._is_bundled_q("mt2-int8sym-cw-q"),'
            '"bundled_int4":translator._is_bundled_q("mt2-int4sym-cw-q")},'
            'ensure_ascii=False))')
    r = subprocess.run([py, '-B', '-c', code], cwd=app, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=300)
    if r.returncode != 0:
        raise RuntimeError('包内 MT 默认探测失败：%s' % (r.stderr or '')[:400])
    m = re.search(r'\{.*\}', r.stdout, re.S)
    if not m:
        raise RuntimeError('包内 MT 默认探测输出异常：%r' % r.stdout[:400])
    j = json.loads(m.group(0))
    problems = []
    if j.get('default_quant') != 'int8':
        problems.append('default_quant != int8')
    if 'int8sym' not in str(j.get('default_model', '')):
        problems.append('DEFAULT_MODEL 不是 int8sym')
    if 'INT8-CW' not in str(j.get('auto_label', '')):
        problems.append('auto label 不是 INT8-CW')
    if 'gpu_int8cw' not in (j.get('mt_engines') or []):
        problems.append('MT_ENGINES 里没有 gpu_int8cw')
    if 'gpu_int4cw' in (j.get('mt_engines') or []):
        problems.append('MT_ENGINES 里还有 gpu_int4cw（本包不应有 INT4）')
    if not j.get('bundled_int8'):
        problems.append('int8 不算 bundled')
    if j.get('bundled_int4'):
        problems.append('int4 竟算 bundled')
    ev['mt_default_probe'] = {'data': j, 'problems': problems,
                               'pass': not problems}
    if problems:
        raise RuntimeError('包内 MT 默认不是 INT8-CW：%s' % problems)
    return ev['mt_default_probe']


def load_meas(required=False):
    """读整链实测数据（README 的「A 机实测」数字**全部来自这里**）。"""
    if not os.path.isfile(MEAS_PATH):
        if required:
            raise RuntimeError('缺整链实测数据，拒绝打包：%s' % MEAS_PATH)
        return None
    return json.load(open(MEAS_PATH, encoding='utf-8'))


def _meas_lines(m, lang='zh'):
    """把实测 json 渲染成 README 里的一小段（数字全部来自验收产物）。"""
    if not m:
        return ('（**待 A 机整链实测**）' if lang == 'zh'
                else '(**pending machine-A end-to-end measurement**)')
    dev = m.get('defaults') or {}
    combo = ('ASR=%s / MT=%s / TTS=%s' % (dev.get('asr'), dev.get('mt'),
                                         dev.get('tts')))
    combo_en = combo
    if lang == 'zh':
        return ('ASR RTF **%s**；翻译延迟中位 **%s ms** / P95 **%s ms**、'
                '首字 **%s ms**、**%s tok/s**；TTS 提交 **%s** / 播完 **%s** / '
                '丢弃 **%s**（TTS 落点 **%s**）；设备组合 **%s**'
                % (m.get('asr_rtf'), m.get('mt_latency_median_ms'),
                   m.get('mt_latency_p95_ms'), m.get('mt_ttft_ms'),
                   m.get('mt_tok_per_s'), m.get('tts_submitted'),
                   m.get('tts_played'), m.get('tts_dropped'),
                   m.get('tts_device'), combo))
    return ('ASR RTF **%s**; translation latency median **%s ms** / P95 '
            '**%s ms**, TTFT **%s ms**, **%s tok/s**; TTS submitted **%s** / '
            'played **%s** / dropped **%s** (TTS device **%s**); device combo '
            '**%s**'
            % (m.get('asr_rtf'), m.get('mt_latency_median_ms'),
               m.get('mt_latency_p95_ms'), m.get('mt_ttft_ms'),
               m.get('mt_tok_per_s'), m.get('tts_submitted'),
               m.get('tts_played'), m.get('tts_dropped'),
               m.get('tts_device'), combo_en))

# ══════════════════════════════════════════════════════════════
# 🔴 APP-105 附带清理：包里**不带 .pyc / __pycache__**
# ══════════════════════════════════════════════════════════════
#: 起因（实测）：rc9 的**目录**在验收跑完之后比它的 **zip** 多了 **1 515 个**
#:   `.pyc`（app 5 + python 1 510）—— 那些是**在包目录上跑 `--check` / 整链**
#:   时由 Python 自己生成的。
#:   ⚠️ 其中 `app/__pycache__/device_config.cpython-312.pyc` 是**旧版
#:   device_config.py**（出厂默认还是 ASR=NPU 那版）编译出来的**过期字节码**
#:   ⇒ 绝不能随包分发。
#:   ⚠️ rc9 的 **zip** 本来就是 **0 个 .pyc**（嵌入式 python 树也不带）⇒
#:   rc10 保持同一口径（清单可比、字节码不掺陈的）。
def purge_pyc(pkg_root, ev=None):
    """删掉包内所有 `__pycache__/` 与 `*.pyc`（记录删了多少）。"""
    removed = []
    for dp, dn, _fn in os.walk(pkg_root, topdown=False):
        for d in list(dn):
            if d == '__pycache__':
                p = os.path.join(dp, d)
                for f in os.listdir(p):
                    removed.append(os.path.relpath(os.path.join(p, f),
                                                   pkg_root).replace('\\', '/'))
                shutil.rmtree(p)
    for dp, _dn, fn in os.walk(pkg_root):
        for f in fn:
            if f.endswith('.pyc'):
                p = os.path.join(dp, f)
                removed.append(os.path.relpath(p, pkg_root).replace('\\', '/'))
                os.remove(p)
    if ev is not None:
        ev['pyc_purge'] = {'n_removed': len(removed),
                           'sample': sorted(removed)[:8]}
    return removed


def count_pyc(pkg_root):
    """数**`.pyc` 文件**个数（**不是** `__pycache__` 目录数）。

    🔴 实测（APP-105 rc10 验收）：`PYTHONDONTWRITEBYTECODE=1` 下 Python
       **仍会创建空的 `__pycache__` 目录**（但**不写 .pyc**）
       ⇒ 判据只认「**过期字节码文件**」，空目录另行清理。
    """
    n = 0
    for dp, _dn, fn in os.walk(pkg_root):
        n += sum(1 for f in fn if f.endswith('.pyc'))
    return n


def purge_empty_pycache(pkg_root):
    """删掉**空**的 `__pycache__` 目录（不删文件 ⇒ 不触发批量删除保护）。"""
    removed = []
    for dp, dn, _fn in os.walk(pkg_root, topdown=False):
        for d in list(dn):
            if d != '__pycache__':
                continue
            q = os.path.join(dp, d)
            try:
                if not os.listdir(q):
                    os.rmdir(q)
                    removed.append(os.path.relpath(q, pkg_root)
                                   .replace(os.sep, '/'))
            except OSError:
                pass
    return removed


# ══════════════════════════════════════════════════════════════
# APP-105 §3：USER_GUIDE 定点改写（唯一命中断言；改的是 rc9 的内容）
# ══════════════════════════════════════════════════════════════
USER_GUIDE_PATCHES = [
    # ① 文首加「EXT 的 ASR 在 MiniMVP 不可用」的醒目说明
    ('> 适用版本：EXT v0.4.8 · 更新日期：2026-11-12（**MiniMVP 客户包版**）\n'
     '>\n'
     '> 本插件抓取浏览器**当前标签页**的音频，交给「实时配音桥接」完成',
     '> 适用版本：EXT v0.4.8 · 更新日期：2026-11-12（**MiniMVP 客户包版**）\n'
     '>\n'
     '> ⚠️ **MiniMVP 本版：EXT 的 ASR 不可用**（APP-105 §3）——\n'
     '> EXT v0.4.8 的 `engine_runtime.py` **写死了 R2T2 的 ASR**，而 MiniMVP 包里\n'
     '> 只有 **Qwen3-ASR-0.6B（stateful）** ⇒ 启动桥接后日志会报\n'
     '> `SegmentEncoderOVBackend 构造失败 …`、引擎预热是「成功 2/3」，\n'
     '> **不会出现** `真实引擎已接线` 与 `TTS 就绪` ⇒ **待 EXT 适配 0.6B**\n'
     '> （EXT 侧进行中；本包不等它）。\n'
     '> ⇒ **本包不要用浏览器插件这条链路**；实时字幕 App 自带的语音输出\n'
     '> （Qwen3-TTS，预设音色 A）**不受影响**。\n'
     '>\n'
     '> 本插件抓取浏览器**当前标签页**的音频，交给「实时配音桥接」完成'),
    # ② 第 2 节的「等日志出现 真实引擎已接线 / TTS 就绪」——本版不会出现
    ('3. 点 **「启动」**，等日志出现 `真实引擎已接线` 和 `TTS 就绪`'
     '（**首次加载要 20–40 秒**）；',
     '3. 点 **「启动」** —— ⚠️ **MiniMVP 本版这一步会失败**：EXT v0.4.8 的 ASR '
     '写死 R2T2，本包只有 0.6B stateful ⇒ 日志报 '
     '`SegmentEncoderOVBackend 构造失败 …`、预热「成功 2/3」，'
     '**不会**出现 `真实引擎已接线` / `TTS 就绪`（**待 EXT 适配 0.6B**，见文首）；'),
    # ③ 第 9 节「当前已知限制」补一条
    ('* **同一时间只服务一个人**，暂不支持多人同时远程使用；',
     '* **MiniMVP 本版：EXT 的 ASR 不可用**（EXT v0.4.8 写死 R2T2 ASR，'
     '本包只有 0.6B stateful）⇒ **待 EXT 适配 0.6B**；'
     '此限制**只影响浏览器插件链路**，App 自己的语音输出正常；\n'
     '* **同一时间只服务一个人**，暂不支持多人同时远程使用；'),
    # ④ 示例路径 rc10 → rc11（基座已是 rc10 ⇒ 里面的示例路径就是 rc10）
    ('cd "<本包目录>"            REM 例如 D:\\Confucius4_LiveCaption_MiniMVP_v1.0-rc10',
     'cd "<本包目录>"            REM 例如 D:\\Confucius4_LiveCaption_MiniMVP_v1.0-rc11'),
    # ⑤ 文首日期 + 包版本（rc11）
    ('> 适用版本：EXT v0.4.8 · 更新日期：2026-11-12（**MiniMVP 客户包版**）',
     '> 适用版本：EXT v0.4.8 · 更新日期：2026-11-13（**MiniMVP 客户包版 · rc11**）'),
]


def patch_user_guide(pkg_root, ev):
    """🔴 **幂等**：基座 rc10 的 USER_GUIDE **已经**打过 rc10 的补丁
    ⇒ 「旧文本找不到」时，若**新文本已在** ⇒ 记 skipped（已打过），
    **不报错**；只有「旧文本不在、新文本也不在」才报错（状态异常）。
    """
    p = os.path.join(pkg_root, 'ext', 'USER_GUIDE.md')
    t = open(p, encoding='utf-8').read()
    applied, skipped, bad = [], [], []
    for old, new in USER_GUIDE_PATCHES:
        c_old = t.count(old)
        c_new = t.count(new)
        if c_old == 1:
            t = t.replace(old, new)
            applied.append({'old_head': old[:40], 'count': c_old})
            continue
        if c_old == 0 and c_new >= 1:
            skipped.append({'new_head': new[:40], 'count': c_new})
            continue
        bad.append({'old_head': old[:60], 'n_old': c_old, 'n_new': c_new})
    if bad:
        raise RuntimeError('USER_GUIDE 补丁状态异常：%s' % bad[:3])
    write_text(p, t)
    ev['user_guide'] = {'patched': len(applied), 'skipped_already': len(skipped),
                        'patches': applied, 'skipped': skipped,
                        'bytes': os.path.getsize(p)}
    return ev['user_guide']


# ══════════════════════════════════════════════════════════════
# §2：README 由脚本生成（真实数据；中英同源）
# ══════════════════════════════════════════════════════════════
def probe_pkg_defaults(pkg_root):
    """**在包内**实测 `device_config.DEFAULT_DEVICES`（唯一事实来源）。"""
    py = os.path.join(pkg_root, 'python', 'python.exe')
    app = os.path.join(pkg_root, 'app')
    code = ('import json,device_config;'
            'print(json.dumps({"default_devices":device_config.DEFAULT_DEVICES,'
            '"profile":__import__("package_profile").PROFILE,'
            '"defaults_version":getattr(device_config,"CONFIG_DEFAULTS_VERSION",None)},'
            'ensure_ascii=False))')
    r = subprocess.run([py, '-B', '-c', code], cwd=app, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=300)
    if r.returncode != 0:
        raise RuntimeError('包内 DEFAULT_DEVICES 探测失败：%s' % (r.stderr or '')[:400])
    m = re.search(r'\{.*\}', r.stdout, re.S)
    if not m:
        raise RuntimeError('包内 DEFAULT_DEVICES 探测输出异常：%r' % r.stdout[:400])
    return json.loads(m.group(0))


def _fmt_num(v):
    """固定宽度数字（⇒ README 长度不随数字变化）。"""
    return ('%*s' % (NUM_WIDTH, format(int(v), ',')))


def _dev_label(dev):
    d = str(dev or '').strip()
    return {'GPU.0': 'Intel 集显 GPU.0（Intel iGPU）',
            'NPU': 'Intel NPU',
            'CPU': 'CPU（不推荐）'}.get(d, d)


def _dev_label_en(dev):
    d = str(dev or '').strip()
    return {'GPU.0': 'Intel iGPU (GPU.0)',
            'NPU': 'Intel NPU',
            'CPU': 'CPU (not recommended)'}.get(d, d)


#: 🔴🔴🔳 APP-105 §4：**中英两版表格同源**（同一行数据 ⇒ 不会漂移）。
DEV_ROWS = [
    # (键, 中文模块名, 英文模块名, 中文模型, 英文模型, 中文精度, 英文精度)
    ('asr', '语音识别', 'Speech recognition',
     '**Qwen3-ASR-0.6B**（stateful INT8（KV cache））',
     '**Qwen3-ASR-0.6B** (stateful INT8 (KV cache))',
     'INT8', 'INT8'),
    ('mt', '翻译', 'Translation',
     '**Hy-MT2-1.8B**（**INT8-CW**）', '**Hy-MT2-1.8B** (**INT8-CW**)',
     '**INT8**（对称 · per-channel weight）',
     '**INT8** (symmetric, per-channel weight)'),
    ('tts', '语音输出', 'Speech output',
     '**Qwen3-TTS 0.6B**（INT8 权重 · FP16 计算）',
     '**Qwen3-TTS 0.6B** (INT8 weights, FP16 compute)',
     'INT8/FP16', 'INT8/FP16'),
]


def dev_table(defaults, lang='zh'):
    """由**同一份 DEV_ROWS** 生成中文表或英文表（APP-105 §4）。"""
    dev = defaults['default_devices']
    lab = _dev_label if lang == 'zh' else _dev_label_en
    head = ('| 模块 | 模型 | 精度 | 默认设备 |' if lang == 'zh'
            else '| Module | Model | Precision | Default device |')
    sep = '|---|---|---|---|'
    rows = [head, sep]
    for key, zh_name, en_name, zh_model, en_model, zh_prec, en_prec in DEV_ROWS:
        name = zh_name if lang == 'zh' else en_name
        model = zh_model if lang == 'zh' else en_model
        prec = zh_prec if lang == 'zh' else en_prec
        rows.append('| %s | %s | %s | %s |'
                    % (name, model, prec, lab(dev.get(key))))
    return '\n'.join(rows)


def dev_line(defaults, lang='zh'):
    dev = defaults['default_devices']
    lab = _dev_label if lang == 'zh' else _dev_label_en
    if lang == 'zh':
        return 'ASR=%s，MT=%s，TTS=%s' % (lab(dev.get('asr')), lab(dev.get('mt')),
                                         lab(dev.get('tts')))
    return 'ASR=%s, MT=%s, TTS=%s' % (lab(dev.get('asr')), lab(dev.get('mt')),
                                     lab(dev.get('tts')))


def readme_texts(pkg_root, ev, rel, defaults, n_files, dir_bytes, zip_bytes):
    """生成三份 README 的文本（数据全部来自**实测**）。"""
    profile = defaults.get('profile', 'minimvp')
    # 🔴 APP-107 §1.4 / APP-106 §2：README 的实测数字**全部来自验收 json**
    meas = load_meas()
    measured_zh = _meas_lines(meas, 'zh')
    measured_en = _meas_lines(meas, 'en')
    measured_pt = _meas_lines(meas, 'zh')
    tbl_zh = dev_table(defaults, 'zh')
    tbl_en = dev_table(defaults, 'en')
    line_zh = dev_line(defaults, 'zh')
    line_en = dev_line(defaults, 'en')
    pkg_line_zh = ('**%s 个文件 / %s B（%.3f GiB）**；zip **%s B**'
                   % ('{:,}'.format(n_files), _fmt_num(dir_bytes),
                      dir_bytes / 1024 ** 3, _fmt_num(zip_bytes)))
    pkg_line_en = ('**%s files / %s B (%.3f GiB)**; zip **%s B**'
                   % ('{:,}'.format(n_files), _fmt_num(dir_bytes),
                      dir_bytes / 1024 ** 3, _fmt_num(zip_bytes)))
    top_list = sorted(os.listdir(pkg_root))
    top_line = '、'.join('`%s`' % x for x in top_list)
    top_line_en = ', '.join('`%s`' % x for x in top_list)

    zh = r"""# Confucius4 实时字幕 · MiniMVP %s（最小客户包）

**本包是独立于 v2.x 的新产品线（MiniMVP），版本号单独编号。**

## 里面有什么

%s
* **包含**：EXT 实时翻译配音**插件与桥接服务**（`ext/` 目录，EXT v%s），
  桌面/命令行启动脚本（`Start_LiveCaption.bat` / `Start_Bridge.bat`）。
* **不含**：NVIDIA/CUDA 与 torch 相关内容、开发与测试脚本、会议录音、
  **克隆音色**（MiniMVP 禁用 ⇒ 只有内置预设音色）、
  说话人旁路（pyannote_seg / wespeaker）。
* **出厂默认设备**：**%s**
  （唯一事实来源 = `app/device_config.py` 的 `DEFAULT_DEVICES`）。
  ⚠️ 若本机 `%%LOCALAPPDATA%%\Confucius4LiveCaption\device_config.json`
  是**旧版本**（本包之前写的），App 会**忽略**其中的设备项并改用出厂默认，
  并在日志里写明忽略了哪些旧值（配置文件**不会被删除**）。
* **ASR**：**Qwen3-ASR-0.6B**，**stateful INT8（KV cache）** 配方
  （按通道 INT8 权重、lm_head 保 FP16、带真实 `attention_mask` 端口）。
  同一套 IR 可编到集显（`--engine gpu_int8`）或 NPU（`--engine npu_int8`）。
* **翻译**：**Hy-MT2-1.8B**，**INT8-CW**（**INT8_SYM · 按通道**，
  `mt2-int8sym-cw-q`；hidden_size 2048 / 32 层；拷贝源
  `hy_bench\ov\mt2-int8sym-cw-q`，12 文件 / 1 812 121 487 B）
  ⇒ **本包只带 INT8-CW，不再带 INT4**（APP-107）；翻译设备默认 **GPU.0**。
* **包体积（实测）**：解压后 %s。

## 怎么启动

双击 `Start_LiveCaption.bat`（GUI），或在命令行里（**不传设备参数**即可用出厂默认）：

```
python\python.exe app\live_caption_app.py
```

> **首次启动**：NPU 需要现编译（**不带编译缓存 blob**）⇒ 第一次启动会慢一些，
> 缓存写在用户目录 `%%LOCALAPPDATA%%\Confucius4LiveCaption`。
> **磁盘**：首次运行约需 **8 GB**（编译缓存）。
> **A 机实测（每个数字都注明设备组合）**：
> · ASR stateful RTF（**仅 ASR 单项**）：集显 GPU.0 = **0.397**；NPU = **0.538**；
> · **本包出厂默认（ASR=GPU.0 / MT=GPU.0（INT8-CW）/ TTS=NPU）的包目录整链**：%s
> · **B 机（Meteor Lake 155H）数据：待实测**。

## 配音桥接（EXT）

> ⚠️ **本版（MiniMVP %s）里 EXT 的 ASR 不可用** —— EXT v%s 的
> `engine_runtime.py` **写死了 R2T2 的 ASR**，而本包只有
> **Qwen3-ASR-0.6B（stateful）** ⇒ 启动桥接后日志会报
> `SegmentEncoderOVBackend 构造失败 …`、引擎预热是「成功 2/3」，
> **不会出现** `真实引擎已接线` 与 `TTS 就绪` ⇒ **待 EXT 适配 0.6B**
> （EXT 侧进行中；本包不等它）。
> ⇒ **本包不要用浏览器插件这条链路**；实时字幕 App **自带的语音输出**
> （Qwen3-TTS，预设音色 A）**不受影响**。

## 许可与归属

见 `NOTICE`（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / **babelvox** /
**djwarf** 等的归属与许可证）与 `THIRD_PARTY.md`。

## 本包顶层目录

%s
""" % (VERSION, tbl_zh, EXT_VERSION, line_zh, pkg_line_zh, measured_zh,
       VERSION, EXT_VERSION, top_line)

    en = r"""# Confucius4 Live Caption - MiniMVP %s (minimal customer package)

**Independent product line (MiniMVP), versioned separately from v2.x.**

## What is inside

%s
* **Included**: the EXT real-time dubbing plugin & bridge service
  (folder `ext/`, EXT v%s), plus the launch scripts
  (`Start_LiveCaption.bat` / `Start_Bridge.bat`).
* **Not included**: NVIDIA/CUDA & torch content, dev & test scripts,
  meeting recordings, **cloned voices** (disabled in MiniMVP => preset
  voices only), speaker bypass (pyannote_seg / wespeaker).
* **Factory default devices**: **%s**
  (single source of truth = `DEFAULT_DEVICES` in `app/device_config.py`).
  If a **stale** `device_config.json` (written by an earlier build) is
  present in `%%LOCALAPPDATA%%\Confucius4LiveCaption`, the app **ignores**
  its device entries and falls back to the factory defaults, logging which
  old values were ignored (the file itself is **never deleted**).
* **ASR**: **Qwen3-ASR-0.6B**, **stateful INT8 (KV cache)** recipe
  (per-channel INT8 weights, FP16 lm_head, real `attention_mask` port).
  The same IR pair is compiled either to the iGPU (`--engine gpu_int8`)
  or to the NPU (`--engine npu_int8`).
* **Translation**: **Hy-MT2-1.8B**, **INT8-CW** (**INT8_SYM, per-channel**,
  `mt2-int8sym-cw-q`; hidden_size 2048 / 32 layers; copied from
  `hy_bench\ov\mt2-int8sym-cw-q`, 12 files / 1 812 121 487 B)
  => **this package ships INT8-CW only, INT4 is gone** (APP-107);
  default translation device: **GPU.0**.
* **Package size (measured)**: unpacked %s.

## Run

Double-click `Start_LiveCaption.bat`, or (no device flags needed):

```
python\python.exe app\live_caption_app.py
```

> **First start**: the NPU is compiled on the fly (no blob cache is shipped)
> => the first start is slower; the cache lives in
> `%%LOCALAPPDATA%%\Confucius4LiveCaption`.
> **Measured on machine A (every number states its device combination)**:
> - ASR stateful RTF (**ASR only**): iGPU GPU.0 = **0.397**; NPU = **0.538**;
> - **package end-to-end run with this package's factory defaults
>   (ASR=GPU.0 / MT=GPU.0 (INT8-CW) / TTS=NPU)**: %s
> - **Machine B (Meteor Lake 155H): pending measurement**.

## Dubbing bridge (EXT)

> ⚠️ **In this build (MiniMVP %s) the EXT ASR does NOT work** -- EXT v%s
> hard-codes the R2T2 ASR in `engine_runtime.py`, while this package only
> ships **Qwen3-ASR-0.6B (stateful)** => starting the bridge logs
> `SegmentEncoderOVBackend ... construction failed ...`, engine warm-up
> reports "2/3 succeeded", and `真实引擎已接线` / `TTS 就绪`
> **never appear** => **waiting for EXT to support 0.6B**
> (in progress on the EXT side; this package does not wait for it).
> => **Do not use the browser-plugin path in this package**; the caption
> app's **own speech output** (Qwen3-TTS, preset voice A) is **not affected**.

## Licenses

See `NOTICE` and `THIRD_PARTY.md`.

## Top level of this package

%s
""" % (VERSION, tbl_en, EXT_VERSION, line_en, pkg_line_en, measured_en,
       VERSION, EXT_VERSION, top_line_en)

    pt = r"""========================================================================
  Confucius4 LiveCaption · MiniMVP %s —— 性能测试版说明
========================================================================

【本包定位】
  这是 **MiniMVP %s 的性能测试构建**，用于在其他机器上测
  ASR / MT / TTS 的实时性能，**不是正式发布版**。
  · 本版在上一版（rc10）基础上改了四件事（APP-107 + APP-106 §2）：
      ① **翻译模型换成 INT8-CW**（`mt2-int8sym-cw-q`，12 文件 /
         1 812 121 487 B；rc10 的 INT4 是 1 040 491 337 B，**+0.77 GB**）
         ⇒ **本包只带 INT8，不再带 INT4**；
      ② **出厂默认设备沿用 rc10**：ASR=GPU.0 / MT=GPU.0 / TTS=NPU
         （`defaults_version` 仍是 9）；
      ③ README 的「A 机实测」**每个数字都注明设备组合**，并补上
         **本包出厂默认下的整链 ASR RTF 与 TTS 提交/播完/丢弃**（APP-106 §2）；
      ④ MANIFEST 增加 `mt/mt2-int8sym-cw-q` 条目（拷贝源路径 + 逐文件 SHA256
         + hidden_size 2048 / num_hidden_layers 32 + INT8_SYM 按通道）。
  · **ASR 模型未改动** ⇒ MANIFEST 里 ASR 的 SHA 与上一版一致。

【包体积（实测，%s）】
  · **解压后**：%s 个文件 / %s B（%.3f GiB）
  · **zip**：%s B
  ⚠️ 「解压后 N 个文件」与 zip 的条目数**同一份清单来源** ⇒ 数字必然对得上。

【本包的 ASR：Qwen3-ASR-0.6B（stateful INT8（KV cache））】
  【模型身份（MANIFEST 同源）】
  · asr06b-decoder-int8        ← Qwen3-ASR-0.6B（stateful，bin SHA 0059531a…d6a3）
  · asr06b-encoder-fp16        ← Qwen3-ASR-0.6B（bin SHA 0b7463d6…）
  · asr06b-tokenizer           ← Qwen3-ASR-0.6B（HF 目录，未导出 OV）
  · embed_tokens_06b_f16.npy   ← Qwen3-ASR-0.6B（权重表，FP16，311 165 056 B）
  · mt/mt2-int8sym-cw-q        ← Hy-MT2-1.8B（**INT8_SYM 对称按通道**；
                                拷贝源 hy_bench\ov\mt2-int8sym-cw-q；
                                hidden_size 2048 / num_hidden_layers 32）
  · qwen3tts                   ← Qwen3-TTS

【出厂默认设备（B 机测试按这个组合跑）】
  · ASR=%s，MT=%s，TTS=%s
  ⚠️ 若本机 `%%LOCALAPPDATA%%\Confucius4LiveCaption\device_config.json` 是**旧版本**
    ⇒ App 会**忽略**里面的设备项并改用上面这组出厂默认（日志里会写明忽略了哪些旧值）。

【B 机要跑的两组（每组 10 分钟）】
  · **组 1（本包出厂默认）**：ASR=GPU.0，MT=GPU.0（**INT8-CW**），TTS=NPU
  · **组 2（对照：只把 ASR 换到 NPU）**：ASR=NPU，MT=GPU.0（**INT8-CW**），TTS=NPU
  → 每组都要记：**ASR RTF、WER、TTS 提交 / 播完 / 丢弃 句数**、有没有崩。
  → 组 1 的 TTS 播完句数是本版的**主要验收指标**。
  → ⚠️ **INT8 比 INT4 大 0.77 GB**，而 ASR 与 MT **同在 GPU.0**
    ⇒ 务必留意**显存 / 共享内存峰值**（APP-107 §2）。

【A 机实测（**每个数字都注明设备组合**）】
  · ASR RTF（**仅 ASR 单项**），iGPU（GPU.0）：**0.397**
  · ASR RTF（**仅 ASR 单项**），NPU：**0.538**
    （encoder + decoder 的 EXECUTION_DEVICES 均为 NPU）
  · **本包出厂默认（ASR=GPU.0 / MT=GPU.0（INT8-CW）/ TTS=NPU）的包目录整链**：
%s
  ⚠️ **B 机（Meteor Lake 155H）数据：待 B 机实测**。

【已知问题】
  · TTS 用 GPU.0 时，长会话里可能**丢弃过期句**（`tts_late_drop_sec`）⇒
    每臂测试都要报「提交 / 播完 / 丢弃」句数。
  · **ASR 与 MT 同放 GPU.0**（**本包出厂默认**）—— 旧解码器时期在 B 机
    报过 `CL_OUT_OF_RESOURCES`；那是**旧解码器**的结论，stateful 解码器的
    负载约为旧解码器的 1/3，**待 B 机复核**。
  · 🔴 **本版翻译模型比 rc10 大 0.77 GB**（INT8-CW 1 812 121 487 B vs
    INT4 1 040 491 337 B）⇒ **ASR + MT 同在 GPU.0** 时**显存/共享内存峰值**
    更高 ⇒ 每臂都要盯 `CL_OUT_OF_RESOURCES`（APP-107 §2）。
  · **本版 EXT 的 ASR 不可用**（EXT 写死 R2T2 ASR，本包只有 0.6B stateful）
    ⇒ 浏览器插件那条链路**不要用**；App 自带的语音输出正常。
""" % (VERSION, VERSION, VERSION, '{:,}'.format(n_files), _fmt_num(dir_bytes),
       dir_bytes / 1024 ** 3, _fmt_num(zip_bytes),
       _dev_label(defaults['default_devices'].get('asr')),
       _dev_label(defaults['default_devices'].get('mt')),
       _dev_label(defaults['default_devices'].get('tts')),
       measured_pt)
    return {'README_zh.md': zh, 'README_en.md': en, 'README_perftest.txt': pt}


def readme_checks(name, text, n_files, dir_bytes, zip_bytes, defaults):
    """**单文件**的 README 闸门（可单测 ⇒ 可做反证）。"""
    hits = []
    for pat in README_FORBIDDEN + README_FORBIDDEN_APP105:
        c = len(re.findall(pat, text))
        if c:
            hits.append({'pattern': pat, 'count': c})
    dev_hits = []
    for s in DEV_PATH_FORBIDDEN:
        c = text.count(s)
        if c:
            dev_hits.append({'literal': s, 'count': c})
    has_count = ('{:,}'.format(n_files) in text)
    has_zip = (_fmt_num(zip_bytes).strip() in text)
    has_dir = (_fmt_num(dir_bytes).strip() in text)
    # 🔴 APP-105 §4：README_en 的设备表是**英文** ⇒ 标签也要用英文口径
    #   （否则会拿中文标签去英文 README 里找 ⇒ **恒不命中 = 假 FAIL**）。
    lab = _dev_label_en if name == 'README_en.md' else _dev_label
    dev_table_ok = all(
        lab(defaults['default_devices'].get(k)) in text
        for k in ('asr', 'mt', 'tts'))
    # 🔴 APP-105 §4：配置目录必须带反斜杠
    has_localapp = ('%LOCALAPPDATA%\\Confucius4LiveCaption' in text)
    # 🔴 APP-105 §3：必须写明 EXT 的 ASR 不可用
    has_ext_note = ('EXT' in text and ('不可用' in text or 'does NOT work' in text))
    # 🔴 APP-105 §4：README_en 的**表格整张英文**（正文里引用中文日志行不算）
    cjk = []
    en_table_ok = True
    if name == 'README_en.md':
        # ⚠️ 「含 | 的行」就算表格行（不要求行首是 |）⇒ 反证构造更严
        table_lines = [ln for ln in text.splitlines() if '|' in ln]
        cjk = [c for ln in table_lines for c in ln
               if '\u4e00' <= c <= '\u9fff']
        en_table_ok = (len(table_lines) >= 5 and not cjk
                       and all(h in text for h in
                               ('| Module |', '| Model |', '| Precision |',
                                '| Default device |'))
                       and all(m in text for m in
                               ('| Speech recognition |', '| Translation |',
                                '| Speech output |')))
    no_cjk = (len(cjk) == 0)
    # 🔴 APP-105 §4/§7：perftest 必须写两组 B 机测试
    has_groups = True
    if name == 'README_perftest.txt':
        has_groups = ('组 1' in text and '组 2' in text
                      and 'ASR=NPU' in text and 'ASR=GPU.0' in text)
    return {
        'file': name,
        'forbidden_hits': hits,
        'dev_path_hits': dev_hits,
        'file_count_matches': has_count,
        'zip_bytes_matches': has_zip,
        'dir_bytes_matches': has_dir,
        'device_table_matches_defaults': dev_table_ok,
        'localappdata_has_backslash': has_localapp,
        'ext_unusable_stated': has_ext_note,
        'en_no_cjk': no_cjk,
        'en_table_english': en_table_ok,
        'n_cjk_en': len(cjk),
        'perftest_two_groups': has_groups,
    }


def _row_pass(r):
    return (not r['forbidden_hits'] and not r['dev_path_hits']
            and r['file_count_matches'] and r['zip_bytes_matches']
            and r['dir_bytes_matches'] and r['device_table_matches_defaults']
            and r['localappdata_has_backslash'] and r['ext_unusable_stated']
            and r['en_no_cjk'] and r['en_table_english']
            and r['perftest_two_groups'])


def readme_gate_selftest(defaults):
    """**反证自测**：闸门必须能抓到「错的已知问题句」与「中文表格漏进英文版」。

    🔴 正样本**直接用真实生成器**（`dev_table(defaults, 'zh'/'en')`）
       ⇒ 测的就是真 README 的样子，不会「样本本身就不像」。
    """
    out = []
    n, b, z = 1234, 5678, 9012
    devs = defaults['default_devices']
    labels = ' '.join(_dev_label(devs.get(k)) for k in ('asr', 'mt', 'tts'))
    labels_en = ' '.join(_dev_label_en(devs.get(k))
                         for k in ('asr', 'mt', 'tts'))
    nl = chr(10)
    bs = chr(92)
    nums = ('{:,}'.format(n), _fmt_num(b).strip(), _fmt_num(z).strip())
    good_zh = ('文件 %s / %s / %s %%LOCALAPPDATA%%' % nums
               + bs + 'Confucius4LiveCaption EXT 不可用 %s' % labels
               + nl + dev_table(defaults, 'zh'))
    r = readme_checks('README_zh.md', good_zh, n, b, z, defaults)
    out.append({'case': 'good_text', 'expected_pass': True,
                'pass': _row_pass(r)})
    bad_zh = good_zh + ' TTS/MT 都放 GPU.0 ⇒ ASR 必须放 NPU'
    r = readme_checks('README_zh.md', bad_zh, n, b, z, defaults)
    out.append({'case': 'old_wrong_sentence', 'expected_pass': False,
                'pass': (not _row_pass(r))})
    good_en = ('files %s / %s / %s %%LOCALAPPDATA%%' % nums
               + bs + 'Confucius4LiveCaption EXT does NOT work %s' % labels_en
               + nl + dev_table(defaults, 'en'))
    r = readme_checks('README_en.md', good_en, n, b, z, defaults)
    out.append({'case': 'good_text_en', 'expected_pass': True,
                'pass': _row_pass(r)})
    bad_en = (good_en + '| 语音识别 | **Qwen3-ASR-0.6B** | INT8 | Intel NPU |'
              + nl)
    r = readme_checks('README_en.md', bad_en, n, b, z, defaults)
    out.append({'case': 'cjk_in_english_table', 'expected_pass': False,
                'pass': (not _row_pass(r))})
    bad_en2 = good_en.replace('| Module |', '| Mod |')
    r = readme_checks('README_en.md', bad_en2, n, b, z, defaults)
    out.append({'case': 'english_table_headers_missing',
                'expected_pass': False, 'pass': (not _row_pass(r))})
    bad_slash = good_zh.replace(bs + 'Confucius4LiveCaption',
                                 'Confucius4LiveCaption')
    r = readme_checks('README_zh.md', bad_slash, n, b, z, defaults)
    out.append({'case': 'missing_backslash', 'expected_pass': False,
                'pass': (not _row_pass(r))})
    bad_ext = good_zh.replace('EXT 不可用 ', '')
    r = readme_checks('README_zh.md', bad_ext, n, b, z, defaults)
    out.append({'case': 'missing_ext_unusable_note', 'expected_pass': False,
                'pass': (not _row_pass(r))})
    return out


def write_readmes(pkg_root, ev, rel, defaults, n_files, dir_bytes, zip_bytes):
    texts = readme_texts(pkg_root, ev, rel, defaults, n_files, dir_bytes,
                         zip_bytes)
    sizes = {}
    for name, text in texts.items():
        p = os.path.join(pkg_root, name)
        sizes[name] = write_text(p, text)
    ev['readme'] = {'files': sizes, 'n_files': n_files,
                    'dir_bytes': dir_bytes, 'zip_bytes_field': zip_bytes,
                    'defaults': defaults}
    return texts


def check_readmes(pkg_root, ev, n_files, dir_bytes, zip_bytes, defaults):
    """README 闸门（reviewer 的 grep 口径 + 数字一致性 + APP-105 §3/§4）。"""
    rows = []
    for name in ('README_zh.md', 'README_en.md', 'README_perftest.txt'):
        p = os.path.join(pkg_root, name)
        t = open(p, encoding='utf-8').read()
        r = readme_checks(name, t, n_files, dir_bytes, zip_bytes, defaults)
        r['pass'] = _row_pass(r)
        rows.append(r)
    ev['readme_gate'] = {'rows': rows,
                         'n_pass': sum(1 for r in rows if r['pass']),
                         'n_fail': sum(1 for r in rows if not r['pass'])}
    return ev['readme_gate']


# ══════════════════════════════════════════════════════════════
# 旧解码器闸门（沿用 rc8/rc9）
# ══════════════════════════════════════════════════════════════
def assert_no_legacy(pkg_root):
    reasons = []
    models = os.path.join(pkg_root, 'models')
    for dp, dn, _fn in os.walk(models):
        for d in dn:
            if LEGACY_DIR in d:
                reasons.append('包内出现旧解码器目录：%s' %
                               os.path.relpath(os.path.join(dp, d), pkg_root))
    app = os.path.join(pkg_root, 'app')
    for dp, _dn, fn in os.walk(app):
        for f in fn:
            if not f.endswith(('.py', '.json', '.txt', '.md')):
                continue
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            n = t.count('mask2')
            if n:
                reasons.append('%s 命中 mask2 ×%d' %
                               (os.path.relpath(p, pkg_root), n))
    return (len(reasons) == 0), reasons


def legacy_gate_selftest():
    out = []
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, 'models', LEGACY_DIR))
        os.makedirs(os.path.join(td, 'app'))
        open(os.path.join(td, 'models', LEGACY_DIR, 'keep.txt'), 'w').close()
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_dir_present', 'expected_pass': False,
                    'pass': ok is False})
        shutil.rmtree(os.path.join(td, 'models', LEGACY_DIR))
        open(os.path.join(td, 'app', 'foo.py'), 'w', encoding='utf-8').write(
            '# mask2 appears here\n')
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_literal_in_app', 'expected_pass': False,
                    'pass': ok is False})
    return out


# ══════════════════════════════════════════════════════════════
# 构建
# ══════════════════════════════════════════════════════════════
def build(ev):
    print('[1/9] 复制 rc9 → rc10（真实拷贝，**跳过 .pyc/__pycache__**）…',
          flush=True)
    # 🔴 **拷贝时就排除** `__pycache__` / `*.pyc`：
    #   rc9 的**目录**比它的 zip 多了 1 515 个 .pyc（验收跑出来的），
    #   其中 app/__pycache__/device_config.cpython-312.pyc 是**旧版
    #   device_config.py**（默认还是 ASR=NPU 那版）的**过期字节码**。
    #   ⇒ 不用「事后删除」（会触发批量删除保护），而是**一开始就不拷**。
    # 🔴 APP-107 §1.1：**INT4 模型在拷贝阶段就不进来**（不是事后删）
    #   ⇒ rc11 目录里从一开始就只有 INT8-CW。
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                                                  'mt2-int4sym-cw-q'))
    ev['actions'].append('copy rc10 -> rc11 (real copy, no hardlink, '
                         'skipped __pycache__/*.pyc + **INT4 MT model**)')

    print('[1b/9] APP-107 §1.1/§1.3：拷贝 INT8-CW 翻译模型并逐文件对拍…',
          flush=True)
    copy_mt_int8(DST_PKG, ev)

    print('[2/9] app/*.py 全量对齐 dev 树…', flush=True)
    app = os.path.join(DST_PKG, 'app')
    names = sorted(f for f in os.listdir(app) if f.endswith('.py')
                   and f != STATEFUL_MODULE)
    copied = copy_dev_files(app, names)
    copy_dev_files(app, [STATEFUL_MODULE])
    ev['copied_from_dev'] = copied + [STATEFUL_MODULE]
    ev['actions'].append('align app/*.py from dev: %d files + %s'
                         % (len(copied), STATEFUL_MODULE))

    print('[2b/9] APP-107 §1.2：包内实测「默认 / 自动」= INT8-CW…', flush=True)
    probe_mt_default(DST_PKG, ev)

    print('[3/9] 旧解码器闸门 + 反例自测…', flush=True)
    ev['legacy_gate_selftest'] = legacy_gate_selftest()
    if not all(x['pass'] for x in ev['legacy_gate_selftest']):
        raise RuntimeError('旧解码器闸门反例自测未通过：%s'
                           % ev['legacy_gate_selftest'])
    ok, reasons = assert_no_legacy(DST_PKG)
    ev['gate_legacy'] = {'ok': ok, 'reasons': reasons}
    if not ok:
        raise RuntimeError('包内仍有旧解码器的目录/字面，终止构建：%s'
                           % reasons[:5])

    print('[4/9] APP-105 §2：清黑名单（bridge_token* / *.pid / *.log）'
          '＋ 清 .pyc/__pycache__…', flush=True)
    ev['blacklist_gate_selftest'] = blacklist_gate_selftest()
    if not all(x['pass'] for x in ev['blacklist_gate_selftest']):
        raise RuntimeError('黑名单闸门反例自测未通过：%s'
                           % ev['blacklist_gate_selftest'])
    purge_blacklist(DST_PKG, ev)
    left = find_blacklist(DST_PKG)
    if left:
        raise RuntimeError('包里还有黑名单文件：%s' % left[:5])
    n_pyc = count_pyc(DST_PKG)
    if n_pyc:
        raise RuntimeError('包里还有 %d 个 .pyc/__pycache__' % n_pyc)
    ev['pyc_purge'] = {'n_removed': 0,
                       'note': '拷贝时已排除（ignore_patterns）；此处只做断言'}
    ev['blacklist_after'] = {'n_left': len(left), 'n_pyc': n_pyc}

    print('[5/9] APP-105 §1：bat 改 CRLF+ASCII，并跑 bat 闸门…', flush=True)
    ev['bat_gate_selftest'] = bat_gate_selftest()
    if not all(x['pass'] for x in ev['bat_gate_selftest']):
        raise RuntimeError('bat 闸门反例自测未通过：%s' % ev['bat_gate_selftest'])
    for name, text in BAT_FILES.items():
        p = os.path.join(DST_PKG, name)
        n = write_bat_crlf(p, text)
        ev.setdefault('bats_written', {})[name] = n
    rows = check_bats(DST_PKG)
    ev['bat_gate'] = {'rows': rows,
                      'n_fail': sum(1 for r in rows if not r['pass'])}
    if ev['bat_gate']['n_fail']:
        raise RuntimeError('包内 bat 闸门未通过：%s'
                           % [r for r in rows if not r['pass']][:5])

    print('[6/9] APP-105 §3：USER_GUIDE 定点改写…', flush=True)
    patch_user_guide(DST_PKG, ev)

    print('[7/9] release.json（版本 rc10，EXT 仍 0.4.8 @817abcb）…', flush=True)
    rel_path = os.path.join(DST_PKG, 'release.json')
    rel = json.load(open(rel_path, encoding='utf-8'))
    rel.update({
        'release': True, 'version': VERSION,
        'asr_model': 'Qwen3-ASR-0.6B',
        'asr_recipe': 'stateful INT8 with KV cache (NPUW_LLM on NPU); '
                      'decoder bin SHA 0059531a…d6a3',
        'asr_engines': ['gpu_int8', 'npu_int8'],
        'ext': {'version': EXT_VERSION, 'commit': EXT_COMMIT},
        'corrections': ['APP-096', 'APP-098', 'APP-099', 'APP-100',
                        'APP-101', 'APP-102', 'APP-103', 'APP-104',
                        'APP-105', 'APP-106', 'APP-107'],
        'package_profile': 'package_profile.json',
        'rc10_changes': [
            'APP-105 §7 出厂默认第 2 代：ASR=GPU.0 / MT=GPU.0 / TTS=NPU'
            '（defaults_version 8→9）',
            'APP-105 §1 Start_Bridge.bat 改 CRLF + ASCII；'
            '打包闸门：所有 *.bat 必须 CRLF + ASCII',
            'APP-105 §2 不带 bridge_token.txt（黑名单：bridge_token* / *.pid / *.log）',
            'APP-105 §3 README 与 USER_GUIDE 如实写明 EXT 的 ASR 在本版不可用',
            'APP-105 §4 README 文字修正（已知问题口径 / %LOCALAPPDATA% 反斜杠 / '
            'README_en 表格英文同源生成）',
        ],
        'rc11_changes': [
            'APP-107 §1.1 翻译模型换 INT8-CW：models/mt/ 下只放 mt2-int8sym-cw-q'
            '（拷贝源 hy_bench\\ov\\mt2-int8sym-cw-q，12 文件 / 1 812 121 487 B），'
            '不再带 INT4（rc10 是 1 040 491 337 B）',
            'APP-107 §1.2 MiniMVP 默认 / 「自动」档 = INT8-CW（行为级断言）',
            'APP-107 §1.3 MANIFEST 增加 mt/mt2-int8sym-cw-q 条目（拷贝源路径 + '
            '逐文件 SHA256 + hidden_size 2048 / num_hidden_layers 32 + INT8_SYM 按通道）',
            'APP-106 §2 README「A 机实测」每个数字注明设备组合 + 补本包出厂默认下的'
            '整链 ASR RTF 与 TTS 提交/播完/丢弃（数字从验收 json 生成）',
            'APP-107 §1.5 EXT 仍嵌 v0.4.8（照旧注明在 MiniMVP 里不可用）',
        ],
    })
    with open(rel_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write('\n')
    ev['release'] = rel

    print('[8/9] 包内实测 DEFAULT_DEVICES…', flush=True)
    defaults = probe_pkg_defaults(DST_PKG)
    ev['pkg_defaults'] = defaults
    if defaults.get('profile') != 'minimvp':
        raise RuntimeError('包内 profile 不是 minimvp：%r' % defaults)
    exp = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
    if defaults['default_devices'] != exp:
        raise RuntimeError('包内出厂默认不是 APP-105 §7 的新默认：%r'
                           % defaults['default_devices'])
    if defaults.get('defaults_version') != 9:
        raise RuntimeError('包内 defaults_version 不是 9：%r'
                           % defaults.get('defaults_version'))

    print('[9/9] 生成三份 README（真实数据）…', flush=True)
    n0, b0 = dir_stats(DST_PKG)
    write_readmes(DST_PKG, ev, rel, defaults, n0, b0, 0)
    n1, b1 = dir_stats(DST_PKG)
    write_readmes(DST_PKG, ev, rel, defaults, n1, b1, 0)
    ev['pkg_readme_round'] = {'round1': [n0, b0], 'round2': [n1, b1]}

    # MANIFEST（从源目录生成 + 逐项校验）
    if DEV not in sys.path:
        sys.path.insert(0, DEV)
    import manifest_gen
    mpath = manifest_gen.write_manifest(DST_PKG)
    manifest_gen.verify_or_die(DST_PKG)
    m = json.load(open(mpath, encoding='utf-8'))
    ev['manifest'] = {'path': mpath, 'n_models': m['n_models'],
                      'all_match': m['all_match'],
                      'mismatches': m['mismatches'][:5]}
    if not m['all_match']:
        raise RuntimeError('MANIFEST 校验失败：%s' % ev['manifest'])

    n, b = dir_stats(DST_PKG)
    ev['pkg'] = {'files': n, 'bytes': b, 'gib': round(b / 1024 ** 3, 3)}
    return ev


def make_zip(ev, passes=2):
    """两遍打包：第 1 遍量出 zip 字节数 ⇒ 回填 README ⇒ 第 2 遍体积应相同。"""
    if not os.path.isfile(ACCEPT_REPORT):
        raise RuntimeError('缺包上验收证据，拒绝打包：%s' % ACCEPT_REPORT)
    smoke = json.load(open(ACCEPT_REPORT, encoding='utf-8'))
    if smoke.get('verdict') != 'PASS':
        raise RuntimeError('包上验收未通过（%s），拒绝打包'
                           % smoke.get('verdict'))
    if os.path.exists(ZIP):
        raise RuntimeError('zip 已存在（不覆盖旧版本，APP-055）：%s' % ZIP)
    os.makedirs(os.path.dirname(ZIP), exist_ok=True)

    rel = json.load(open(os.path.join(DST_PKG, 'release.json'), encoding='utf-8'))
    defaults = ev.get('pkg_defaults') or probe_pkg_defaults(DST_PKG)
    # 🔴 APP-107 §1.4 / APP-106 §2：**README 的实测数字必须来自验收 json**
    #   ⇒ 缺它就**拒绝打包**（不许带占位符出包）。
    meas = load_meas(required=True)
    ev['meas_used'] = {'path': MEAS_PATH, 'at': meas.get('at'),
                       'defaults': meas.get('defaults'),
                       'asr_rtf': meas.get('asr_rtf'),
                       'mt_latency_median_ms': meas.get('mt_latency_median_ms'),
                       'mt_latency_p95_ms': meas.get('mt_latency_p95_ms'),
                       'mt_ttft_ms': meas.get('mt_ttft_ms'),
                       'mt_tok_per_s': meas.get('mt_tok_per_s'),
                       'tts_submitted': meas.get('tts_submitted'),
                       'tts_played': meas.get('tts_played'),
                       'tts_dropped': meas.get('tts_dropped'),
                       'tts_device': meas.get('tts_device')}
    # 🔴🔴 **实测数字必须先落盘再打 zip**（第 1 轮实测踩过）：
    #   README 里「待 A 机整链实测」占位符 → 真数字，**会改变 README 的字节长度**
    #   （三份 README 各 +~211 B）⇒ 若第 1 遍 zip 用的是占位符版、第 2 遍才是
    #   真数字版 ⇒ **体积不收敛**（实测 6 697 682 717 vs 6 697 683 352，差 635 B）。
    #   ⇒ 这里**先**用真数字重写三份 README，再进两遍打包循环 ⇒ 两遍等长 ⇒ 收敛。
    n_pre, b_pre = dir_stats(DST_PKG)
    write_readmes(DST_PKG, ev, rel, defaults, n_pre, b_pre, 0)
    # 🔴 **打 zip 前再清一次**：包上验收（`--check` / 整链 / Start_Bridge.bat）
    #   会在包目录里**生成** `.pyc` 与 `ext/bridge_token.txt`
    #   ⇒ APP-105 §2 明文要求「先测试、再生成清单、最后打 zip」。
    #    ⚠️ `.pyc` **不删**（批量删除会触发安全保护）⇒ 验收全程用
    #    `PYTHONDONTWRITEBYTECODE=1` ⇒ 包目录里**本来就不该有** .pyc
    #    ⇒ 这里只做**断言**（有就报错，绝不静默带进 zip）。
    ev['pre_zip_purge'] = {
        'n_pyc_left': count_pyc(DST_PKG),
        'empty_pycache_dirs_removed': purge_empty_pycache(DST_PKG),
        'blacklist_removed': len(purge_blacklist(DST_PKG, ev)),
    }
    if count_pyc(DST_PKG) or find_blacklist(DST_PKG):
        raise RuntimeError('打 zip 前仍有 .pyc / 黑名单文件'
                           '（.pyc 必须在验收时用 PYTHONDONTWRITEBYTECODE=1）')
    sizes = []
    for i in range(passes):
        t0 = time.time()
        tmp_zip = ZIP + '.tmp'
        with zipfile.ZipFile(tmp_zip, 'w', compression=zipfile.ZIP_STORED,
                             allowZip64=True) as zf:
            for dp, _dn, fn in os.walk(DST_PKG):
                for f in fn:
                    p = os.path.join(dp, f)
                    arc = os.path.join(PKG_NAME, os.path.relpath(p, DST_PKG))
                    zf.write(p, arc.replace('\\', '/'))
        sz = os.path.getsize(tmp_zip)
        sizes.append(sz)
        n_files, dir_bytes = dir_stats(DST_PKG)
        write_readmes(DST_PKG, ev, rel, defaults, n_files, dir_bytes, sz)
        if i + 1 < passes:
            os.remove(tmp_zip)
        else:
            os.replace(tmp_zip, ZIP)
    _n, _b = dir_stats(DST_PKG)
    ev['pkg'] = {'files': _n, 'bytes': _b, 'gib': round(_b / 1024 ** 3, 3)}
    ev['zip'] = {'path': ZIP, 'bytes': os.path.getsize(ZIP),
                 'pass_sizes': sizes,
                 'converged': len(set(sizes)) == 1,
                 'accept_verdict': smoke.get('verdict'),
                 'sha256': None, 'sha_note': '用户规则：zip 不做 SHA 校验'}
    if len(set(sizes)) != 1:
        raise RuntimeError('zip 体积未收敛：%s' % sizes)
    n_files, dir_bytes = dir_stats(DST_PKG)
    g = check_readmes(DST_PKG, ev, n_files, dir_bytes, sizes[-1], defaults)
    if g['n_fail']:
        raise RuntimeError('README 闸门未通过：%s' % g)
    ev['actions'].append('zip written after acceptance PASS (2-pass, converged)')
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--zip', action='store_true')
    a = ap.parse_args()
    dry = not (a.run or a.zip)

    ev = {'at': datetime.datetime.now().isoformat(timespec='seconds'),
          'version': VERSION, 'correction': 'APP-107 (+APP-106 §2)',
          'base_pkg': BASE_PKG, 'dst_pkg': DST_PKG, 'dry_run': dry,
          'actions': []}
    try:
        with open(os.path.join(HERE, '_app524_rc11_build.pid'), 'w') as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    if not os.path.isdir(BASE_PKG):
        print('!! rc10 不存在'); return 2
    if a.run and os.path.exists(DST_PKG):
        print('!! rc11 目录已存在（拒绝覆盖，APP-055）：%s' % DST_PKG); return 2
    if a.zip and not os.path.isdir(DST_PKG):
        print('!! rc11 目录不存在'); return 2

    if dry:
        n_base, b_base = dir_stats(BASE_PKG)
        print('[dry-run] 将创建 %s（复制 rc10 的 %d 文件 / %.3f GiB）'
              % (DST_PKG, n_base, b_base / 1024 ** 3))
        ev['legacy_gate_selftest'] = legacy_gate_selftest()
        ev['bat_gate_selftest'] = bat_gate_selftest()
        ev['blacklist_gate_selftest'] = blacklist_gate_selftest()
        ev['readme_gate_selftest'] = readme_gate_selftest(
            {'default_devices': {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}})
        ok = all(all(x['pass'] for x in ev[k])
                 for k in ('legacy_gate_selftest', 'bat_gate_selftest',
                           'blacklist_gate_selftest', 'readme_gate_selftest'))
        print('[dry-run] 闸门反例自测：',
              {k: all(x['pass'] for x in ev[k]) for k in
               ('legacy_gate_selftest', 'bat_gate_selftest',
                'blacklist_gate_selftest', 'readme_gate_selftest')})
        json.dump(ev, open(REPORT, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 0 if ok else 2

    t0 = time.time()
    try:
        if a.run:
            build(ev)
            n_files, dir_bytes = dir_stats(DST_PKG)
            defaults = ev['pkg_defaults']
            write_readmes(DST_PKG, ev, ev['release'], defaults, n_files,
                          dir_bytes, 0)
        if a.zip:
            make_zip(ev)
    except Exception as e:
        ev['error'] = repr(e)
        with open(REPORT, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        print('!! 构建失败：%r' % e)
        raise
    ev['elapsed_s'] = round(time.time() - t0, 1)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('完成：%s / %d 文件 / %.1f s'
          % (ev.get('zip', {}).get('path', DST_PKG),
             ev.get('pkg', {}).get('files', 0), ev['elapsed_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
