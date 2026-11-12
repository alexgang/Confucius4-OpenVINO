# -*- coding: utf-8 -*-
r"""_app484 — **MiniMVP rc8 构建**（APP-101/102/103）。

在 rc7 基础上产出 rc8（**新目录**，rc7 一字不动）：
 1. 复制 rc7 → rc8（真实拷贝，不用硬链接）。
 2. ``models/asr06b-decoder-int8/`` 换成 stateful IR（源 ``ov-dec-06b-stateful-int8sym``）。
 3. app/：删掉无 KV 的旧基线模块（含旧解码器字面），加入
    ``asr06b_stateful_backend.py``，其余 .py 从 dev 树全量对齐。
 4. 嵌入 EXT v0.4.8 @817abcb（``ext/bridge`` + ``ext/extension``）。
 5. MANIFEST 由 ``live_caption/manifest_gen.py`` 从源目录生成并逐项校验。
 6. 反例自测（APP-101 §4.5）：包内出现旧目录 / app 里出现旧解码器字面
    ⇒ 闸门必须判 FAIL 并终止打包。
 7. release.json / package_profile.json / 文档术语同步。

🔴 **本脚本只建目录，不打 zip**（zip 由 ``--zip`` 阶段在冒烟 PASS 后执行）。
用法：
    python results/app/_app484_build_minimvp_rc8.py --dry-run
    python results/app/_app484_build_minimvp_rc8.py --run
    python results/app/_app484_build_minimvp_rc8.py --zip
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')
STAGE = os.path.join(REPO, '_ext_v048_stage')
BASE_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc7')
DST_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc8')
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc8'
VERSION = '1.0-rc8'
ZIP = os.path.join(HOME, 'shared', 'minimvp', PKG_NAME + '_perftest.zip')
REPORT = os.path.join(HERE, 'app484_minimvp_rc8_build_evidence.json')
SMOKE_REPORT = os.path.join(HERE, 'app486_app102_rc8_smoke.json')

SRC_DECODER = os.path.join(HOME, 'qwen3asr_06b', 'models',
                           'ov-dec-06b-stateful-int8sym')
DECODER_BIN_SHA = ('0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262'
                   'baba4dc55e603b600d6a3')
ENCODER_BIN_SHA_PREFIX = '0b7463d6f952dd64'
EXT_COMMIT = '817abcbe30c213844cda6f32c81361524ab53de8'
LEGACY_DIR = 'ov-dec-06b-embed-mask2-int8sym'
LEGACY_BASELINE_MODULE = 'asr06b_backend.py'
STATEFUL_MODULE = 'asr06b_stateful_backend.py'
# 不进客户包（APP-088：torch/CUDA 不随包分发）
EXT_SKIP = {'tts_cuda_sidecar_ext.py'}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 22), b''):
            h.update(c)
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


# ── APP-101 §4.5：打包闸门 + 反例自测 ────────────────────────────────
def assert_no_legacy(pkg_root):
    """返回 (ok, reasons)。两种反例都必须让闸门判 FAIL。"""
    reasons = []
    models = os.path.join(pkg_root, 'models')
    for dp, dn, fn in os.walk(models):
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


def selftest_gate():
    """构造 2 个反例，验证闸门确实会终止（不是恒真的弱标记）。"""
    out = []
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, 'models', LEGACY_DIR))
        os.makedirs(os.path.join(td, 'app'))
        open(os.path.join(td, 'models', LEGACY_DIR, 'keep.txt'), 'w').close()
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_dir_present', 'gate_ok': ok,
                    'expected': False, 'pass': ok is False})
        shutil.rmtree(os.path.join(td, 'models', LEGACY_DIR))
        open(os.path.join(td, 'app', 'foo.py'), 'w', encoding='utf-8').write(
            '# mask2 appears here\n')
        ok, _ = assert_no_legacy(td)
        out.append({'case': 'legacy_literal_in_app', 'gate_ok': ok,
                    'expected': False, 'pass': ok is False})
        ok, _ = assert_no_legacy(td)
    return out


def embed_ext(pkg_root, ev):
    """按 v2.4 客户包布局嵌 EXT v0.4.8（只读 stage，不复制 claude-dev 工作区）。"""
    ext_root = os.path.join(pkg_root, 'ext')
    bridge = os.path.join(ext_root, 'bridge')
    extension = os.path.join(ext_root, 'extension')
    os.makedirs(bridge, exist_ok=True)
    os.makedirs(extension, exist_ok=True)
    n_bridge = 0
    for f in sorted(os.listdir(os.path.join(STAGE, 'ext'))):
        if not f.endswith('.py') or f in EXT_SKIP:
            continue
        shutil.copy2(os.path.join(STAGE, 'ext', f), os.path.join(bridge, f))
        n_bridge += 1
    n_ext = 0
    for dp, _dn, fn in os.walk(os.path.join(STAGE, 'extension')):
        rel = os.path.relpath(dp, os.path.join(STAGE, 'extension'))
        dst_dp = extension if rel == '.' else os.path.join(extension, rel)
        os.makedirs(dst_dp, exist_ok=True)
        for f in fn:
            shutil.copy2(os.path.join(dp, f), os.path.join(dst_dp, f))
            n_ext += 1
    shutil.copy2(os.path.join(STAGE, 'USER_GUIDE.md'),
                 os.path.join(ext_root, 'USER_GUIDE.md'))
    mf = json.load(open(os.path.join(extension, 'manifest.json'), encoding='utf-8'))
    rel = {
        'version': '0.4.8',
        'commit': EXT_COMMIT,
        'source': 'git archive 817abcb (master；工作区当时签出 claude-dev)',
        'embedded_at': datetime.datetime.now().isoformat(timespec='seconds'),
    }
    with open(os.path.join(ext_root, 'release.json'), 'w', encoding='utf-8',
              newline='\n') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write('\n')
    guide_hits = []
    for fn in ('USER_GUIDE.md', os.path.join('extension', 'USER_GUIDE.md')):
        p = os.path.join(ext_root, fn)
        if os.path.isfile(p):
            t = open(p, encoding='utf-8', errors='replace').read()
            for kw in ('视频轻微降速', 'token 配对'):
                c = t.count(kw)
                if c:
                    guide_hits.append({'file': fn, 'keyword': kw, 'count': c,
                                       'line': next((ln.strip() for ln in
                                                     t.splitlines() if kw in ln), '')})
    ev['ext'] = {
        'manifest_version': mf.get('version'), 'commit': EXT_COMMIT,
        'bridge_py_files': n_bridge, 'extension_files': n_ext,
        'accel_usage_py': os.path.isfile(os.path.join(bridge, 'accel_usage.py')),
        'guide_keyword_hits': guide_hits,
        'guide_hit_note': ('命中项均为「已取消/不再使用」的说明性表述，'
                           '不是功能项；如实登记，未改 EXT 源文件'),
    }
    if mf.get('version') != '0.4.8':
        raise RuntimeError('EXT manifest 版本不是 0.4.8：%r' % mf.get('version'))
    if not ev['ext']['accel_usage_py']:
        raise RuntimeError('EXT v0.4.8 缺 ext/accel_usage.py')
    return ev['ext']


def sync_docs(pkg_root, ev):
    """文档里旧解码器术语同步为 stateful（纯字面替换，登记命中数）。"""
    pairs = [
        ('ov-dec-06b-embed-mask2-int8sym', 'ov-dec-06b-stateful-int8sym'),
        ('mask2 INT8', 'stateful INT8 (KV cache)'),
        ('INT8 mask2', 'stateful INT8 (KV cache)'),
        ('mask2', 'stateful KV decoder'),
    ]
    out = []
    for name in sorted(os.listdir(pkg_root)):
        if not name.endswith(('.txt', '.md', '.json')):
            continue
        p = os.path.join(pkg_root, name)
        if not os.path.isfile(p):
            continue
        raw = open(p, 'rb').read()
        t = raw.decode('utf-8', errors='replace')
        orig = t
        for old, new in pairs:
            t = t.replace(old, new)
        if t != orig:
            with open(p, 'wb') as f:
                f.write(t.encode('utf-8'))
            out.append({'file': name,
                        'replaced': len(orig.split('mask2')) - 1})
    ev['docs_synced'] = out


def build(ev):
    # ① 复制 rc7 → rc8
    print('[1/8] 复制 rc7 → rc8（真实拷贝）…', flush=True)
    shutil.copytree(BASE_PKG, DST_PKG, symlinks=True)
    ev['actions'].append('copy rc7 -> rc8 (real copy, no hardlink)')
    app = os.path.join(DST_PKG, 'app')
    models = os.path.join(DST_PKG, 'models')

    # ② 换 stateful 解码器
    print('[2/8] 换 stateful 解码器 IR…', flush=True)
    dec_dir = os.path.join(models, 'asr06b-decoder-int8')
    for f in os.listdir(dec_dir):
        os.remove(os.path.join(dec_dir, f))
    src_files = sorted(f for f in os.listdir(SRC_DECODER)
                       if f.endswith(('.xml', '.bin')))
    for f in src_files:
        shutil.copy2(os.path.join(SRC_DECODER, f), os.path.join(dec_dir, f))
    bin_sha = sha256_file(os.path.join(dec_dir, 'openvino_model.bin'))
    ev['decoder'] = {'source': SRC_DECODER, 'files': src_files,
                     'bin_sha256': bin_sha, 'expect': DECODER_BIN_SHA,
                     'match': bin_sha == DECODER_BIN_SHA}
    if not ev['decoder']['match']:
        raise RuntimeError('stateful decoder bin SHA 不符：%s' % bin_sha)
    ev['actions'].append('replace decoder IR with stateful (bin SHA verified)')

    # ③ app/ 对齐 dev 树 + 删旧基线模块 + 加 stateful 模块
    print('[3/8] 从 dev 树全量对齐 app/*.py，删旧基线、加 stateful…', flush=True)
    old = os.path.join(app, LEGACY_BASELINE_MODULE)
    if os.path.isfile(old):
        os.remove(old)
    names = sorted(f for f in os.listdir(app) if f.endswith('.py')
                   and f != STATEFUL_MODULE)
    copied = copy_dev_files(app, names)
    copy_dev_files(app, [STATEFUL_MODULE])
    ev['copied_from_dev'] = copied + [STATEFUL_MODULE]
    ev['removed_from_pkg'] = [LEGACY_BASELINE_MODULE]
    ev['actions'].append('align app/*.py from dev: %d files + %s'
                         % (len(copied), STATEFUL_MODULE))

    # ④ 闸门 + 反例自测
    print('[4/8] 旧解码器闸门 + 反例自测…', flush=True)
    ev['gate_selftest'] = selftest_gate()
    if not all(x['pass'] for x in ev['gate_selftest']):
        raise RuntimeError('闸门反例自测未通过：%s' % ev['gate_selftest'])
    ok, reasons = assert_no_legacy(DST_PKG)
    ev['gate'] = {'ok': ok, 'reasons': reasons}
    if not ok:
        raise RuntimeError('包内仍有无 KV 旧解码器的目录/字面，终止构建：%s'
                           % reasons[:5])
    ev['actions'].append('no-legacy gate PASS (2/2 counterexamples)')

    # ⑤ EXT v0.4.8
    print('[5/8] 嵌 EXT v0.4.8 @817abcb…', flush=True)
    embed_ext(DST_PKG, ev)
    ev['actions'].append('embed EXT 0.4.8 @817abcb')

    # ⑥ release.json / 文档
    print('[6/8] 写 release.json、同步文档术语…', flush=True)
    sync_docs(DST_PKG, ev)
    rel_path = os.path.join(DST_PKG, 'release.json')
    rel = json.load(open(rel_path, encoding='utf-8'))
    rel.update({
        'release': True, 'version': VERSION,
        'asr_model': 'Qwen3-ASR-0.6B',
        'asr_recipe': 'stateful INT8 with KV cache (NPUW_LLM on NPU); '
                      'decoder bin SHA 0059531a…d6a3',
        'asr_engines': ['gpu_int8', 'npu_int8'],
        'ext': {'version': '0.4.8', 'commit': EXT_COMMIT},
        'corrections': ['APP-096', 'APP-098', 'APP-099', 'APP-100',
                        'APP-101', 'APP-102', 'APP-103'],
        'package_profile': 'package_profile.json',
    })
    with open(rel_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write('\n')
    ev['release'] = rel
    ev['actions'].append('write release.json')

    # ⑦ MANIFEST（从源目录生成 + 逐项校验）
    print('[7/8] 生成并校验 MANIFEST…', flush=True)
    if DEV not in sys.path:
        sys.path.insert(0, DEV)
    import manifest_gen
    mpath = manifest_gen.write_manifest(DST_PKG)
    manifest_gen.verify_or_die(DST_PKG)
    m = json.load(open(mpath, encoding='utf-8'))
    dec_rows = m['models']['asr06b-decoder-int8']['files']
    dec_bin = next((r for r in dec_rows if r['name'] == 'openvino_model.bin'), None)
    enc_rows = m['models']['asr06b-encoder-fp16']['files']
    enc_bin = next((r for r in enc_rows if r['name'].endswith('.bin')), None)
    ev['manifest'] = {
        'path': mpath, 'n_models': m['n_models'],
        'all_match': m['all_match'], 'mismatches': m['mismatches'][:5],
        'decoder_source': m['models']['asr06b-decoder-int8']['source_path'],
        'decoder_bin_sha256': dec_bin['sha256'] if dec_bin else None,
        'encoder_bin_sha256': enc_bin['sha256'] if enc_bin else None,
        'decoder_expect_ok': bool(dec_bin and
                                  dec_bin['sha256'] == DECODER_BIN_SHA),
        'encoder_expect_ok': bool(enc_bin and enc_bin['sha256'].lower()
                                  .startswith(ENCODER_BIN_SHA_PREFIX)),
        'embed_source': m['models']['embed_tokens_06b_f16.npy']['source_path'],
    }
    if not (ev['manifest']['decoder_expect_ok']
            and ev['manifest']['encoder_expect_ok'] and m['all_match']):
        raise RuntimeError('MANIFEST 校验失败：%s' % ev['manifest'])
    ev['actions'].append('MANIFEST generated + verified from source dirs')

    # ⑧ 指纹
    print('[8/8] 指纹…', flush=True)
    n, b = dir_stats(DST_PKG)
    ev['pkg'] = {'files': n, 'bytes': b, 'gib': round(b / 1024 ** 3, 3)}
    ev['base_unchanged'] = (dir_stats(BASE_PKG)[1] ==
                            ev.get('base_bytes_before'))
    return ev


def make_zip(ev):
    """APP-102 §3：冒烟 PASS 后才允许打 zip（新文件名，旧 zip 不动）。"""
    if not os.path.isfile(SMOKE_REPORT):
        raise RuntimeError('缺冒烟证据，拒绝打包：%s' % SMOKE_REPORT)
    smoke = json.load(open(SMOKE_REPORT, encoding='utf-8'))
    if smoke.get('verdict') != 'PASS':
        raise RuntimeError('冒烟未 PASS（%s），拒绝打包' % smoke.get('verdict'))
    if os.path.exists(ZIP):
        raise RuntimeError('zip 已存在（不覆盖旧版本，APP-055）：%s' % ZIP)
    os.makedirs(os.path.dirname(ZIP), exist_ok=True)
    t0 = time.time()
    with zipfile.ZipFile(ZIP, 'w', compression=zipfile.ZIP_STORED,
                         allowZip64=True) as zf:
        for dp, _dn, fn in os.walk(DST_PKG):
            for f in fn:
                p = os.path.join(dp, f)
                arc = os.path.join(PKG_NAME, os.path.relpath(p, DST_PKG))
                zf.write(p, arc.replace('\\', '/'))
    ev['zip'] = {'path': ZIP, 'bytes': os.path.getsize(ZIP),
                 'seconds': round(time.time() - t0, 1),
                 'smoke_verdict': smoke.get('verdict'),
                 'sha256': None, 'sha_note': '用户规则：zip 不做 SHA 校验'}
    ev['actions'].append('zip written after smoke PASS')
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--zip', action='store_true')
    a = ap.parse_args()
    dry = not (a.run or a.zip)

    ev = {'at': datetime.datetime.now().isoformat(timespec='seconds'),
          'version': VERSION, 'correction': 'APP-101/102/103',
          'base_pkg': BASE_PKG, 'dst_pkg': DST_PKG, 'dry_run': dry,
          'actions': []}
    if not os.path.isdir(BASE_PKG):
        print('!! rc7 不存在'); return 2
    if not os.path.isdir(SRC_DECODER):
        print('!! stateful 源目录不存在'); return 2
    if not os.path.isdir(STAGE):
        print('!! EXT v0.4.8 stage 不存在'); return 2
    if a.run and os.path.exists(DST_PKG):
        print('!! rc8 目录已存在（拒绝覆盖，APP-055）：%s' % DST_PKG); return 2
    if a.zip and not os.path.isdir(DST_PKG):
        print('!! rc8 目录不存在'); return 2

    if dry:
        n_base, b_base = dir_stats(BASE_PKG)
        print('[dry-run] 将创建 %s（复制 rc7 的 %d 文件 / %.3f GiB）'
              % (DST_PKG, n_base, b_base / 1024 ** 3))
        print('[dry-run] 换 stateful IR / 删旧基线模块 / 加 stateful 模块 / '
              '嵌 EXT 0.4.8 / MANIFEST / release.json')
        ev['gate_selftest'] = selftest_gate()
        print('[dry-run] 反例自测：', ev['gate_selftest'])
        print(json.dumps(ev, ensure_ascii=False, indent=1)[:2000])
        return 0

    t0 = time.time()
    try:
        if a.run:
            ev['base_bytes_before'] = dir_stats(BASE_PKG)[1]
            build(ev)
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
    print('完成：%s / %.3f GiB / %d 文件 / %.1f s'
          % (ev.get('zip', {}).get('path', DST_PKG),
             ev.get('pkg', {}).get('gib', ev.get('zip', {}).get('bytes', 0) / 1024 ** 3),
             ev.get('pkg', {}).get('files', 0), ev['elapsed_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
