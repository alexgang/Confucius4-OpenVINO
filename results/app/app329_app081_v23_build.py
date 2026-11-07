#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app329 — APP-081：建 **v2.3** 客户包目录（新目录，绝不动 v2.0/2.1/2.2）。

从 v2.2 只读复制/硬链接 ⇒ 新目录，然后按 APP-080 ①–⑤ 定点改造：

  * 剔除 PKG_EXCLUDE_PATTERNS 命中的全部文件（bridge_token / babelvox 8 音色 /
    克隆音色 / 克隆产物 / 测试 wav）——**复制时跳过**，不原地删任何旧包文件；
  * 3 份生产模块先「骨架等价校验后升级基底」到 dev 当前版本
    （§146：v2.2 包内基底只有 14/18 锚点，直接套补丁会 AssertionError），
    再套 v23_preset_only 的 18 锚点构建期补丁（ast + 唯一命中 + 行尾）；
  * 带入 PKG_INCLUDE_FILES（v23_preset_only.py / assert_pkg_clean.py）；
  * 说话人旁路**保留**（字幕标注用途，APP-080 ③ / §143）⇒ 补 5 个 spk 文件
    ＋ 5 s 静态 seg IR `fp16-w5`（D5 取 dev 当前那份，xml 已脱敏）；
  * 重签 ACCEPTED.json（version=2.3，按新代码算指纹）；
  * 建包后立刻跑 assert_pkg_clean 闸门 ⇒ 0 违规才允许继续。

🔴 只读 v2.2；不生成 zip、不占设备、不加载模型、不改桌面 .lnk。
用法：
  python app329_app081_v23_build.py --json results/app/app329_app081_v23_build_evidence.json
"""
from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(REPO, 'live_caption')
if REPO not in sys.path:
    sys.path.insert(0, REPO)          # pkg_exclude / repo 根模块
if DEV not in sys.path:
    sys.path.insert(0, DEV)           # v23_preset_only / assert_pkg_clean

import pkg_exclude            # noqa: E402
import v23_preset_only as v23  # noqa: E402
from assert_pkg_clean import assert_clean, load_exclude_rules  # noqa: E402

HOME = r'C:\Users\Trekker-PTL'
SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.3')
ASR_DEV = os.path.join(HOME, 'qwen3asr_06b')
W5_DEV = os.path.join(ASR_DEV, 'models', 'pyannote_seg', 'ov-fp16-w5')
W5_DST_REL = os.path.join('models', 'spk', 'pyannote_seg_3_0', 'fp16-w5')
SPK_DEV = os.path.join(ASR_DEV, 'scripts')
SPK_DST_REL = os.path.join('app', 'asr_spk')

COPY_DIRS = ['app', 'ext', 'docs', 'results']
HARDLINK_DIRS = ['models', 'python']
ROOT_FILES = [
    'README_zh.md', 'README_en.md', 'README_插件.md', 'NOTICE',
    'THIRD_PARTY.md', 'Start_LiveCaption.bat', 'Diagnose.bat',
    'release.json', 'ACCEPTED.json',
]
PATCH_MODULES = [
    ('live_caption_app.py', 'live_caption/live_caption_app.py'),
    ('tts_service.py', 'live_caption/tts_service.py'),
    ('tts_worker.py', 'live_caption/tts_worker.py'),
]
SPK_FILES = [
    'asr052_speaker_tracker_api.py', 'asr052_spk_runtime.py',
    'asr_thread_defaults.py', 'asr_spk_window.py', 'asr_runtime_switches.py',
]
W5_FILES = ['pyannote_seg_3_0_w5.bin', 'pyannote_seg_3_0_w5.xml']


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def norm_bytes(b):
    return b.replace(b'\r\n', b'\n')


def rel_posix(root, path):
    return os.path.relpath(path, root).replace('\\', '/')


def is_excluded(rel):
    return any(cre.search(rel) for cre, _lab in RULES)


def dir_bytes(root):
    n, total = 0, 0
    for r, _d, fs in os.walk(root):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(r, f))
                n += 1
            except OSError:
                pass
    return n, total


def names(root):
    out = set()
    for r, _d, fs in os.walk(root):
        for f in fs:
            out.add(rel_posix(root, os.path.join(r, f)))
    return out


def copy_tree(src, dst, skip_log):
    for root, _dirs, files in os.walk(src):
        rel_dir = os.path.relpath(root, src)
        tgt = dst if rel_dir == '.' else os.path.join(dst, rel_dir)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            rel = rel_posix(SRC, s)
            if is_excluded(rel):
                skip_log.append(rel)
                continue
            t = os.path.join(tgt, f)
            if os.path.exists(t):
                os.chmod(t, 0o666)
                os.remove(t)
            shutil.copy2(s, t)


def link_tree(src, dst, skip_log):
    n = 0
    for root, _dirs, files in os.walk(src):
        rel_dir = os.path.relpath(root, src)
        tgt = dst if rel_dir == '.' else os.path.join(dst, rel_dir)
        os.makedirs(tgt, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            rel = rel_posix(SRC, s)
            if is_excluded(rel):
                skip_log.append(rel)
                continue
            t = os.path.join(tgt, f)
            if os.path.exists(t):
                continue
            try:
                os.link(s, t)
                n += 1
            except OSError:
                shutil.copy2(s, t)
                n += 1
    return n


def top_level_skeleton(text):
    """代码骨架：顶层函数/类/赋值名集合（用于「升级基底」前的等价校验）。"""
    tree = ast.parse(text)
    out = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--dst', default=DST)
    ap.add_argument('--json', default=os.path.join(
        HERE, 'app329_app081_v23_build_evidence.json'))
    a = ap.parse_args()
    src, dst = os.path.abspath(a.src), os.path.abspath(a.dst)
    global RULES
    RULES = load_exclude_rules()

    if src == dst:
        print('!! 源=目标 ⇒ 拒绝')
        return 2
    if not os.path.isdir(src):
        print('!! 源包不存在：%s' % src)
        return 2
    if os.path.exists(dst):
        print('!! 目标已存在（APP-055：禁止覆盖/原地改）⇒ %s' % dst)
        return 2

    t0 = time.time()
    print('=' * 72)
    print('app329 — 建 v2.3 包目录（APP-081）')
    print('  源（只读）:', src)
    print('  目标      :', dst)
    print('=' * 72)

    # 源包基线（收尾复核「一字节未动」）
    src_probe = {}
    for rel in ['ext/bridge_token.txt', 'app/live_caption_app.py',
                'app/tts_service.py', 'app/tts_worker.py',
                'app/MANIFEST.json']:
        p = os.path.join(src, rel.replace('/', os.sep))
        if os.path.isfile(p):
            src_probe[rel] = {'bytes': os.path.getsize(p),
                              'sha256': sha256_file(p)}
    src_names = names(src)
    src_n, src_bytes = dir_bytes(src)

    ev = {
        'tool': 'app329', 'app': 'APP-081 / APP-080',
        'started_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'src': src, 'dst': dst,
        'src_probe_before': src_probe,
        'src_files': len(src_names), 'src_bytes': src_bytes,
        'n_exclude_rules': len(RULES),
        'skipped_excluded': [], 'added': [], 'synced': [], 'patches': {},
        'spk_assets': [], 'w5_assets': [],
    }

    os.makedirs(dst, exist_ok=True)
    for d in COPY_DIRS:
        s = os.path.join(src, d)
        if os.path.isdir(s):
            copy_tree(s, os.path.join(dst, d), ev['skipped_excluded'])
            print('  [copy] %s/' % d)
    linked = 0
    for d in HARDLINK_DIRS:
        s = os.path.join(src, d)
        if os.path.isdir(s):
            linked += link_tree(s, os.path.join(dst, d), ev['skipped_excluded'])
            print('  [link] %s/' % d)
    ev['n_hardlinks'] = linked
    for f in ROOT_FILES:
        s = os.path.join(src, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
    ev['skipped_excluded'] = sorted(set(ev['skipped_excluded']))
    print('  [exclude] 跳过违规文件 %d 个' % len(ev['skipped_excluded']))
    for r in ev['skipped_excluded'][:15]:
        print('     -', r)

    # ── 定点改造 ①：3 份源文件升级基底 + 18 锚点补丁 ──────────────
    print('\n-- ① 骨架校验 → 升级 dev 基底 → 18 锚点补丁 --')
    for fname, file_key in PATCH_MODULES:
        sp = os.path.join(DEV, fname)
        tp = os.path.join(dst, 'app', fname)
        dev_raw = open(sp, 'rb').read()
        dev_text = norm_bytes(dev_raw).decode('utf-8')
        old_text = open(tp, 'rb').read().decode('utf-8')
        sk_new, sk_old = top_level_skeleton(dev_text), top_level_skeleton(old_text)
        missing = sorted(sk_old - sk_new)
        if missing:
            print('🔴 骨架校验 FAIL：dev 基底缺 %s 的顶层符号 %r ⇒ 中止'
                  % (fname, missing))
            return 3
        patched, applied = v23.apply_patches(dev_text, file_key)
        ok, reasons = v23.verify_source(patched, file_key)
        if not ok:
            print('🔴 verify_source FAIL：%s ⇒ %r' % (fname, reasons))
            return 3
        ast.parse(patched, filename=file_key)
        data = patched.encode('utf-8')
        tmp = tp + '.app329_tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        back = open(tmp, 'rb').read()
        assert back == data, '写后逐字节复核失败 %s' % fname
        os.replace(tmp, tp)
        rec = {
            'module': fname, 'n_anchors': len(applied), 'applied_ids': applied,
            'skeleton_old_n': len(sk_old), 'skeleton_dev_n': len(sk_new),
            'skeleton_missing_in_dev': missing,
            'sha256_before': hashlib.sha256(old_text.encode('utf-8')).hexdigest(),
            'sha256_after': sha256_file(tp), 'bytes': len(data),
            'verify_source_ok': ok,
        }
        ev['synced'].append(rec)
        ev['patches'][file_key] = applied
        print('  [sync] %-22s 锚点 %2d 个  verify_source=PASS  %d B'
              % (fname, len(applied), len(data)))
    ev['n_anchors_total'] = sum(len(v) for v in ev['patches'].values())

    # ── 定点改造 ②：PKG_INCLUDE_FILES 接进包 ───────────────────────
    print('\n-- ② PKG_INCLUDE_FILES 接入 --')
    for rel in v23.PKG_INCLUDE_FILES:
        # dev 源文件在仓库 live_caption/ 下；PKG_INCLUDE_FILES 写的是**包内**
        # 相对路径（app/xxx.py）⇒ 用 basename 映射，不能照拼 REPO/app/。
        sp = os.path.join(DEV, os.path.basename(rel))
        tp = os.path.join(dst, rel.replace('/', os.sep))
        data = norm_bytes(open(sp, 'rb').read())
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        tmp = tp + '.app329_tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        assert open(tmp, 'rb').read() == data
        os.replace(tmp, tp)
        ev['added'].append({'path': rel, 'bytes': len(data),
                            'sha256': sha256_file(tp)})
        print('  [add] %-40s %d B' % (rel, len(data)))

    # ── 定点改造 ③：说话人旁路保留 ⇒ 5 个 spk 文件 + 5 s seg IR ────
    print('\n-- ③ 说话人旁路（字幕标注用途）保留：5 spk + fp16-w5 --')
    for n in SPK_FILES:
        sp = os.path.join(SPK_DEV, n)
        tp = os.path.join(dst, SPK_DST_REL, n)
        data = norm_bytes(open(sp, 'rb').read())
        tmp = tp + '.app329_tmp'
        with open(tmp, 'wb') as f:
            f.write(data)
        assert open(tmp, 'rb').read() == data
        os.replace(tmp, tp)
        ev['spk_assets'].append({'path': '%s/%s' % (SPK_DST_REL.replace('\\', '/'), n),
                                 'bytes': len(data), 'sha256': sha256_file(tp),
                                 'source': sp})
    for n in W5_FILES:
        sp = os.path.join(W5_DEV, n)
        tp = os.path.join(dst, W5_DST_REL, n)
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        shutil.copy2(sp, tp)
        ev['w5_assets'].append({
            'path': '%s/%s' % (W5_DST_REL.replace('\\', '/'), n),
            'bytes': os.path.getsize(tp), 'sha256': sha256_file(tp),
            'source': sp,
            'source_mtime': datetime.datetime.fromtimestamp(
                os.path.getmtime(sp)).strftime('%Y-%m-%d %H:%M:%S'),
        })
        print('  [w5] %-32s %d B  %s' % (n, os.path.getsize(tp),
                                         ev['w5_assets'][-1]['sha256'][:16]))
    print('  [spk] 5 个文件已同步（v2.2 只有 3 个）')

    # ── 完整性闸门：允许「预期剔除」与「预期新增」，其余一律 FAIL ────
    dst_names = names(dst)
    expected = (src_names - set(ev['skipped_excluded']))
    expected |= {r['path'] for r in ev['added']}
    expected |= {r['path'] for r in ev['spk_assets']}
    expected |= {r['path'] for r in ev['w5_assets']}
    missing = sorted(expected - dst_names)
    extra = sorted(dst_names - expected)
    ev['n_src_files'] = len(src_names)
    ev['n_dst_files'] = len(dst_names)
    ev['n_missing'] = len(missing)
    ev['n_extra'] = len(extra)
    if missing or extra:
        print('🔴 完整性闸门 FAIL：missing=%d extra=%d' % (len(missing), len(extra)))
        print('   missing[:8]=%r' % missing[:8])
        print('   extra[:8]=%r' % extra[:8])
        ev['verdict'] = 'FAIL_COMPLETENESS'
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        return 4
    print('  [gate] 完整性闸门 PASS：%d 文件 = 源 %d - 剔除 %d + 新增 %d'
          % (len(dst_names), len(src_names), len(ev['skipped_excluded']),
             len(dst_names) - (len(src_names) - len(ev['skipped_excluded']))))

    # ── 洁净度闸门（APP-081 第 3 点修复后的 6 类规则）────────────────
    print('\n-- ④ 交付洁净度闸门（6 类规则驱动）--')
    rc = assert_clean(dst)
    ev['gate_clean_rc'] = rc
    if rc != 0:
        print('🔴 洁净度闸门 FAIL ⇒ 该目录不可交付')
        ev['verdict'] = 'FAIL_CLEAN_GATE'
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        return 5

    # ── 重签 ACCEPTED.json（version=2.3）──────────────────────────
    print('\n-- ⑤ 重签 ACCEPTED.json --')
    pkg_app = os.path.join(dst, 'app')
    mods = [n for n in sorted(os.listdir(pkg_app))
            if n.endswith('.py') and not pkg_exclude.is_app_dev_only('app/' + n)]
    per, h = {}, hashlib.sha256()
    for n in mods:
        with open(os.path.join(pkg_app, n), 'rb') as f:
            d = norm_bytes(f.read())
        per[n] = hashlib.sha256(d).hexdigest()
        h.update(n.encode('utf-8') + b'\0' + hashlib.sha256(d).digest())
    fp = h.hexdigest()
    payload = {
        'accepted': True,
        'version': '2.3',
        'pkg_dir': '<HOME>\\Confucius4_LiveCaption_v2.3',
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'corrections': ['APP-061', 'APP-063', 'APP-065', 'APP-068', 'APP-076',
                        'APP-077', 'APP-078', 'APP-080', 'APP-081'],
        'binding_gate': 'app191',
        'code_fingerprint': fp,
        'code_fingerprint_alg': (
            'app191.package_fingerprint：SHA256 over（文件名 + NUL + '
            'SHA256(归一化行尾后的模块字节)），按文件名排序；范围 = 包内 app/ 生产模块'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'delivery_scope': 'APP-080 用户决定：v2.3 只交付预设音色；克隆功能移出本版，'
                          '转入后续版本（APP-071/075/079 不阻塞 v2.3）',
        'waived_changes': {
            'live_caption_app.py': 'APP-080 ①：去掉克隆音色选项/字样，'
                                   '②：残留 clone 回落预设 A 并写日志',
            'tts_service.py': 'APP-080 ②：克隆登记/嗓音绑定运行期闸门恒不执行',
            'tts_worker.py': 'APP-080 ②：speaker_enc 克隆调用/音色切换不执行',
            'app/asr_spk/*': 'APP-080 ③：字幕标注用途保留 5 个 spk 文件；'
                             'APP-076：min_clean_ratio 默认 0.6 随旁路',
        },
        'pending_reviewer': [
            'APP-080 ⑥：干净目录解压 --check / CLI SPE 前 5 分钟 / GUI 100%+150% '
            '截图 / 黑名单扫描 / zip SHA256 ⇒ reviewer 复核后才通知用户',
        ],
    }
    acc = os.path.join(dst, 'ACCEPTED.json')
    tmp = acc + '.app329_tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    back = json.load(open(tmp, encoding='utf-8'))
    assert back['code_fingerprint'] == fp and back['version'] == '2.3'
    os.replace(tmp, acc)
    ev['accepted'] = {'bytes': os.path.getsize(acc), 'sha256': sha256_file(acc),
                      'code_fingerprint': fp, 'n_production_modules': len(mods)}

    # MANIFEST.version 预同步（pack_v13 的 check_version_identity 闸门）
    man = os.path.join(dst, 'app', 'MANIFEST.json')
    if os.path.isfile(man):
        m = json.load(open(man, encoding='utf-8'))
        ev['manifest_version_before'] = m.get('version')
        m['version'] = '2.3'
        tmp = man + '.app329_tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            json.dump(m, f, ensure_ascii=False, indent=2)
        os.replace(tmp, man)
        ev['manifest_version_after'] = '2.3'

    # ── 包体积变化 + 源包「一字节未动」复核 ─────────────────────────
    dst_n, dst_bytes = dir_bytes(dst)
    ev['dst_files'] = dst_n
    ev['dst_bytes'] = dst_bytes
    ev['bytes_delta'] = dst_bytes - src_bytes
    src_probe_after = {}
    for rel, rec in src_probe.items():
        p = os.path.join(src, rel.replace('/', os.sep))
        src_probe_after[rel] = {'bytes': os.path.getsize(p),
                                'sha256': sha256_file(p)}
    ev['src_probe_after'] = src_probe_after
    ev['src_unchanged'] = (src_probe == src_probe_after
                           and names(src) == src_names)
    print('\n  [size] %d 文件 / %d B → %d 文件 / %d B  (Δ %+d B)'
          % (src_n, src_bytes, dst_n, dst_bytes, ev['bytes_delta']))
    print('  [src]  v2.2 一字节未动 =', ev['src_unchanged'])

    ev['elapsed_s'] = round(time.time() - t0, 1)
    ev['verdict'] = 'PASS' if ev['src_unchanged'] else 'FAIL_SRC_MODIFIED'
    with open(a.json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n[%s] 证据：%s（耗时 %.1f s）' % (ev['verdict'], a.json, ev['elapsed_s']))
    return 0 if ev['verdict'] == 'PASS' else 6


if __name__ == '__main__':
    raise SystemExit(main())
