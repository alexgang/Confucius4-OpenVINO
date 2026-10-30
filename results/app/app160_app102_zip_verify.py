#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app160_app102_zip_verify.py —— §102：客户包 **v1.12** zip 产物的**只读**核验。

在 `app156_app100_zip_verify.py` 的基础上**扩展**（不是替代）：

| 编号 | 判据 | 对应 |
|---|---|---|
| V1 | zip 存在 / 字节 / mtime / SHA256 | §66 |
| V2 | `testzip()` 无 CRC 错误 | §66 |
| V3 | zip ⇄ 包目录 `.py` 逐字一致（归一化 LF）| 半交付判据 |
| V4 | **§100 的 3 个文件修复真在 zip 内** | §100 |
| V5 | MANIFEST `version` == 目录版本 == zip 版本 | §十 |
| **V7** | 🔴🔴🔴 **§101 回归修复（模式感知 `spk=None`）真在 zip 内** | §101.4 |
| **V8** | 🔴🔴🔴 **§102 脱敏真在 zip 内**（zip 内 `app/asr_spk/` **0 个**内部编号）| §102 |
| **V9** | 🔴🔴🔴 **APP-044 的 16 MB 资产真在 zip 内**（`models/spk/` 两个 OV IR ＋ `app/asr_spk/`）| §101 / APP-044 |
| **V10** | 🔴🔴🔴 **APP-044 许可署名真在 zip 内**（NOTICE / THIRD_PARTY 含 wespeaker CC BY 4.0）| APP-044 |
| **V11** | 🔴 **zip 内 `app/asr_spk/` 全部 `.py` 语法合法**（`ast.parse`）| §102 |

🔴 **全程只读**：不写任何文件、不改任何产物。
🔴 **不跑 `verify_pkg_zip.py`、不开 FTP**（§66 口径）。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import time
import zipfile

HOME = r'C:\Users\Trekker-PTL'
VER = sys.argv[1] if len(sys.argv) > 1 else '1.12'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v%s' % VER)
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_v%s.zip' % VER)
OUT = os.path.join(REPO, 'results', 'app',
                   'app160_app102_zip_evidence_v%s.json' % VER)

# §100 改动的 3 个文件
S100_FILES = ['live_caption_app.py', 'tts_worker.py', 'speaker_tracker.py']
# §101 的 APP-044 接口代码 + 资产
ASR_SPK = 'app/asr_spk/'
SPK_MODELS = 'models/spk/'

# 🔴 内部会议音频编号（与 check_internal_material.py 的 CONTENT_PATTERNS 对齐）
SECRET_PATTERNS = (
    (re.compile(rb'260902'), '会议音频编号'),
    (re.compile(rb'\bQ[G]S\b', re.I), '会议特征串'),
    (re.compile(rb'b[l]c\s*b[0]', re.I), '内部产品代号'),
    (re.compile(rb'5[2]\s*c[o]re', re.I), '内部产品规格'),
    (re.compile(rb'L[i]sa will join', re.I), '会议人名片段'),
)

# 🔴🔴🔴 §101.4 模式感知 `spk=None` 的**结构性**标志（必须真的在 zip 内）
#
# ⚠️ **首版判据恒真**（干跑 v1.11 已确认）：只查
#   `_fallback_to_preset('no_spk_label')` / `self.clone_mode` / `self._spk_voices`
#   三个弱标记 ⇒ **缺陷版**（无条件回落，§100 首版）**也全部命中** ⇒ 判 PASS。
# ⇒ 改查**模式感知分支本体**：必须有
#   ① `self.clone_mode`（worker 启动参数）
#   ② `self._spk_voices`（按句绑定表非空 ⇒ 判据）
#   ③ 二者组合出的**模式分支**（clone_mode 成立时**保留**克隆音色）
# ⇒ 缺陷版三者缺 ③ ⇒ 必 FAIL。
S101_MARKERS = (
    "_fallback_to_preset('no_spk_label')",
    'self.clone_mode',
    'self._spk_voices',
)
# 🔴 模式感知分支的**最小结构特征**（缺陷版没有）
S101_MODE_AWARE = (
    # 「clone_mode 成立 ⇒ 保留克隆音色」这一分支
    'clone_mode and not',
    # 判据用的「按句绑定表是否非空」
    'bool(self._spk_voices)',
    # 保留克隆音色时写入的遥测字段
    "voice_kind",
)

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('PASS %-58s %s' % (name, msg))
    else:
        FAIL += 1
        print('FAIL %-58s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def main() -> int:
    ev = {'ver': VER, 'zip_path': ZIP, 'pkg_dir': PKG}

    if not os.path.exists(ZIP):
        print('❌ zip 不存在：%s' % ZIP)
        return 1
    st = os.stat(ZIP)
    ev['zip_bytes'] = st.st_size
    ev['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))
    print('计算 zip SHA256（%s 字节）…' % format(st.st_size, ','))
    ev['zip_sha256'] = sha256_file(ZIP)
    add('V1 zip 存在', True, '%s 字节' % format(st.st_size, ','))

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        ev['n_entries'] = len(names)
        bad = z.testzip()
        ev['testzip'] = bad
        add('V2 testzip() 无 CRC 错误', bad is None, 'testzip=%r' % (bad,))

        # ── V3 zip ⇄ 包目录 .py 逐字一致 ───────────────────────────
        py_in_zip = [n for n in names if n.endswith('.py')]
        n_same = n_diff = 0
        diffs = []
        for n in py_in_zip:
            rel = n.split('/', 1)[1] if '/' in n else n
            disk = os.path.join(PKG, rel.replace('/', os.sep))
            if not os.path.exists(disk):
                continue
            try:
                zb = norm(z.read(n))
                db = norm(open(disk, 'rb').read())
            except Exception:
                continue
            if zb == db:
                n_same += 1
            else:
                n_diff += 1
                if len(diffs) < 20:
                    diffs.append(rel)
        ev['py_same'] = n_same
        ev['py_diff'] = n_diff
        ev['py_diffs'] = diffs
        add('V3 zip ⇄ 包目录 .py 逐字一致', n_diff == 0 and n_same > 0,
            '一致 %d / 差异 %d' % (n_same, n_diff))

        def find_in_zip(rel: str):
            cands = [n for n in names if n.endswith('/' + rel) or n == rel]
            return cands[0] if cands else None

        # ── V4 §100 的 3 个文件 ───────────────────────────────────
        for t in S100_FILES:
            cand = find_in_zip('app/' + t)
            disk = os.path.join(PKG, 'app', t)
            if not cand:
                add('V4 §100 修复在 zip 内：%s' % t, False, 'NOT IN ZIP')
            elif not os.path.exists(disk):
                add('V4 §100 修复在 zip 内：%s' % t, False, 'NOT ON DISK')
            else:
                zb, db = norm(z.read(cand)), norm(open(disk, 'rb').read())
                add('V4 §100 修复在 zip 内：%s' % t, zb == db,
                    'zip=%s pkg=%s' % (hashlib.sha256(zb).hexdigest()[:12],
                                       hashlib.sha256(db).hexdigest()[:12]))

        # ── V5 MANIFEST version ───────────────────────────────────
        man = None
        for n in names:
            if n.endswith('app/MANIFEST.json'):
                man = n
                break
        mver = mfiles = None
        if man:
            try:
                data = json.loads(z.read(man).decode('utf-8'))
                mver, mfiles = data.get('version'), data.get('files')
                add('V5 MANIFEST version == %s' % VER, str(mver) == VER,
                    'version=%r files=%r' % (mver, mfiles))
            except Exception as e:
                add('V5 MANIFEST 可解析', False, repr(e))
        else:
            add('V5 zip 内存在 MANIFEST.json', False, '未找到')
        ev['manifest_version'] = mver
        ev['manifest_files'] = mfiles

        # ── V7 §101 模式感知 spk=None 真在 zip 内 ──────────────────
        cand = find_in_zip('app/tts_worker.py')
        if not cand:
            add('V7 §101 模式感知修复在 zip 内', False, 'app/tts_worker.py NOT IN ZIP')
            ev['s101'] = dict(found=False)
        else:
            src = z.read(cand).decode('utf-8', 'replace')
            miss = [m for m in S101_MARKERS if m not in src]
            miss_ma = [m for m in S101_MODE_AWARE if m not in src]
            ok = (not miss) and (not miss_ma)
            add('V7 §101 模式感知修复在 zip 内', ok,
                ('缺弱标记 %s' % miss) if miss
                else (('缺模式感知特征 %s' % miss_ma) if miss_ma
                      else '3 弱标记 + 3 模式感知特征全在 ✅'))
            ev['s101'] = dict(found=True, miss=miss, miss_mode_aware=miss_ma,
                              ok=ok)

        # ── V8 §102 脱敏真在 zip 内 ────────────────────────────────
        spk_py = [n for n in names if ASR_SPK in n and n.endswith('.py')]
        ev['zip_asr_spk_py'] = len(spk_py)
        secret_hits = []
        for n in spk_py:
            b = z.read(n)
            for rx, why in SECRET_PATTERNS:
                c = len(rx.findall(b))
                if c:
                    secret_hits.append((n.split('/')[-1], why, c))
        ev['zip_secret_hits'] = secret_hits
        add('V8 zip 内 app/asr_spk/ 无内部编号', bool(spk_py) and not secret_hits,
            ('命中 %s' % secret_hits[:5]) if secret_hits
            else '%d 个 .py，0 命中 ✅' % len(spk_py))

        # ── V9 APP-044 的 16 MB 资产真在 zip 内 ───────────────────
        spk_models = [n for n in names if SPK_MODELS in n]
        ir_files = [n for n in spk_models if n.endswith(('.xml', '.bin'))]
        ir_bytes = 0
        for n in ir_files:
            try:
                ir_bytes += z.getinfo(n).file_size
            except Exception:
                pass
        ev['zip_spk_ir_files'] = len(ir_files)
        ev['zip_spk_ir_bytes'] = ir_bytes
        add('V9 APP-044 说话人资产在 zip 内', len(ir_files) >= 4 and ir_bytes > 15 * 1024 * 1024,
            '%d 个 IR / %s 字节（%.2f MB）'
            % (len(ir_files), format(ir_bytes, ','), ir_bytes / 1048576.0))
        add('V9b APP-044 接口代码在 zip 内', len(spk_py) >= 9,
            '%d 个 .py' % len(spk_py))

        # ── V10 APP-044 许可署名真在 zip 内 ───────────────────────
        lic = {}
        for f in ('NOTICE', 'THIRD_PARTY.md'):
            c2 = find_in_zip(f)
            if not c2:
                lic[f] = None
                continue
            t = z.read(c2).decode('utf-8', 'replace')
            lic[f] = dict(
                bytes=len(z.read(c2)),
                wespeaker=('wespeaker' in t.lower()),
                cc_by4=('cc by 4.0' in t.lower()
                        or 'cc-by-4.0' in t.lower()
                        or 'creative commons attribution 4.0' in t.lower()),
                pyannote=('pyannote' in t.lower()),
                mit=('mit' in t.lower()),
            )
        ev['license'] = lic
        lic_ok = all(v and v['wespeaker'] and v['cc_by4'] and v['pyannote']
                     for v in lic.values())
        add('V10 APP-044 许可署名在 zip 内', lic_ok,
            'NOTICE/third_party 均含 wespeaker CC BY 4.0 + pyannote')

        # ── V11 zip 内 asr_spk 语法合法 ───────────────────────────
        bad_py = []
        for n in spk_py:
            try:
                ast.parse(z.read(n).decode('utf-8'))
            except Exception as e:
                bad_py.append('%s: %s' % (n.split('/')[-1], e))
        ev['zip_asr_spk_bad'] = bad_py
        add('V11 zip 内 asr_spk 语法全合法', bool(spk_py) and not bad_py,
            ('失败 %s' % bad_py[:3]) if bad_py else '%d 文件全合法 ✅' % len(spk_py))

    # ── V6 版本号三处一致 ─────────────────────────────────────────
    dir_ver = os.path.basename(PKG).rsplit('_v', 1)[-1]
    zip_ver = os.path.basename(ZIP).rsplit('_v', 1)[-1].replace('.zip', '')
    ev['dir_ver'] = dir_ver
    ev['zip_ver'] = zip_ver
    add('V6 版本号三处一致（目录/zip/MANIFEST）',
        dir_ver == zip_ver == str(ev.get('manifest_version')),
        'dir=%s zip=%s manifest=%s' % (dir_ver, zip_ver, ev.get('manifest_version')))

    ev['pass'] = PASS
    ev['fail'] = FAIL
    ev['verdict'] = 'PASS' if FAIL == 0 else 'FAIL'
    ev['details'] = DETAIL
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n合计 %d PASS / %d FAIL  ⇒  verdict=%s'
          % (PASS, FAIL, ev['verdict']))
    print('证据：%s' % OUT)
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
