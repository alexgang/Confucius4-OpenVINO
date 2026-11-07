#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app_v24_build — reviewer 2026-11-07: build the **v2.4** customer package directory.

User decision (2026-11-07): "drop v2.3 and package v2.4 once you fix the voice clone
issue and integrate patches into v2.4".  v2.4 = cloning back ON + fixes, and **every**
app module taken from dev (v2.3 shipped 9 modules still at their v2.2 versions,
e.g. speaker_voice.note_final without spk_conf => 46 swallowed TypeErrors).

Same skeleton as app329 (v2.3):
  * python/ + models/ hard-linked from v2.2 (read-only), app/ext/docs/results copied,
    PKG_EXCLUDE_PATTERNS files skipped at copy time (bridge_token, babelvox voices,
    clone voices/artefacts, test wavs);
  * NEW: every top-level app/*.py that exists in dev is replaced by the dev version
    (clone_dev = main + claude-clone: clone-upgrade fix, lazy 512 vocoder, trimmed
    decoder buckets);  v23_preset_only.py is NOT shipped;
  * assert_pkg_clean.py shipped (PKG_INCLUDE gate);
  * app/asr_spk: canonical ASR files + live_caption/asr_spk_v24 overrides (speaker
    clustering v2 as default, user-approved) + 5 s static seg IR fp16-w5;
  * cross-module import scan: any local module imported by the synced code must exist;
  * clean gate (assert_clean) must be 0; ACCEPTED.json + MANIFEST version = 2.4.
Read-only on v2.2; no zip, no device, no models loaded, no .lnk changes.
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
for _p in (REPO, DEV, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pkg_exclude                      # noqa: E402
from assert_pkg_clean import assert_clean, load_exclude_rules  # noqa: E402
import app329_app081_v23_build as B     # noqa: E402  (helpers: copy_tree/link_tree/...)

HOME = r'C:\Users\Trekker-PTL'
SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4')
VERSION = '2.4'
SPK_OVR = os.path.join(DEV, 'asr_spk_v24')
SPK_OVR_FILES = ['asr052_speaker_tracker_api.py', 'asr_spk_cluster_v2.py']
INCLUDE_FILES = ['app/assert_pkg_clean.py']
NOT_SHIPPED = {'v23_preset_only.py'}
# guarded optional imports of dev-only modules (verified 2026-11-07):
#   assert_pkg_clean -> v23_preset_only: try/except, falls back to the same built-in rules
#   backends / npu_embeds_backend -> backends_torch: lazy, raises a clear 'use OpenVINO' error
OPTIONAL_DEV_IMPORTS = {'v23_preset_only', 'backends_torch'}


def _write(tp, data):
    os.makedirs(os.path.dirname(tp), exist_ok=True)
    tmp = tp + '.v24_tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    assert open(tmp, 'rb').read() == data
    os.replace(tmp, tp)


def _local_imports(text):
    out = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            out |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module.split('.')[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--dst', default=DST)
    ap.add_argument('--json', default=os.path.join(HERE, 'app_v24_build_evidence.json'))
    a = ap.parse_args()
    src, dst = os.path.abspath(a.src), os.path.abspath(a.dst)
    B.SRC = src
    B.RULES = load_exclude_rules()
    if src == dst or not os.path.isdir(src):
        print('!! bad src/dst'); return 2
    if os.path.exists(dst):
        print('!! target exists (no overwrite / in-place edits): %s' % dst); return 2

    t0 = time.time()
    print('=' * 72); print('app_v24_build — v2.4 package dir'); print('  src (ro):', src); print('  dst     :', dst); print('=' * 72)
    src_probe = {}
    for rel in ['ext/bridge_token.txt', 'app/live_caption_app.py', 'app/speaker_voice.py', 'app/MANIFEST.json']:
        p = os.path.join(src, rel.replace('/', os.sep))
        if os.path.isfile(p):
            src_probe[rel] = {'bytes': os.path.getsize(p), 'sha256': B.sha256_file(p)}
    src_names = B.names(src)
    src_n, src_bytes = B.dir_bytes(src)
    ev = {'tool': 'app_v24_build', 'version': VERSION,
          'started_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          'src': src, 'dst': dst, 'dev': DEV, 'skipped_excluded': [], 'synced': [],
          'unchanged': [], 'added': [], 'spk_assets': [], 'w5_assets': []}

    os.makedirs(dst)
    for d in B.COPY_DIRS:
        s = os.path.join(src, d)
        if os.path.isdir(s):
            B.copy_tree(s, os.path.join(dst, d), ev['skipped_excluded']); print('  [copy] %s/' % d)
    linked = 0
    for d in B.HARDLINK_DIRS:
        s = os.path.join(src, d)
        if os.path.isdir(s):
            linked += B.link_tree(s, os.path.join(dst, d), ev['skipped_excluded']); print('  [link] %s/' % d)
    ev['n_hardlinks'] = linked
    for f in B.ROOT_FILES:
        s = os.path.join(src, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
    ev['skipped_excluded'] = sorted(set(ev['skipped_excluded']))
    print('  [exclude] skipped %d files' % len(ev['skipped_excluded']))

    # ① every top-level app/*.py that exists in dev -> dev version
    print('\n-- (1) sync ALL app modules to dev --')
    pkg_app = os.path.join(dst, 'app')
    for n in sorted(os.listdir(pkg_app)):
        if not n.endswith('.py'):
            continue
        sp, tp = os.path.join(DEV, n), os.path.join(pkg_app, n)
        if not os.path.isfile(sp):
            ev['unchanged'].append({'module': n, 'why': 'not in dev'}); continue
        data = B.norm_bytes(open(sp, 'rb').read())
        ast.parse(data.decode('utf-8'), filename=n)
        old = B.norm_bytes(open(tp, 'rb').read())
        if old == data:
            ev['unchanged'].append({'module': n, 'why': 'identical'}); continue
        _write(tp, data)
        ev['synced'].append({'module': n, 'sha256_before': hashlib.sha256(old).hexdigest(),
                             'sha256_after': B.sha256_file(tp), 'bytes': len(data)})
        print('  [sync] %s' % n)
    for n in NOT_SHIPPED:
        assert not os.path.exists(os.path.join(pkg_app, n)), n

    # ② include files
    for rel in INCLUDE_FILES:
        sp = os.path.join(DEV, os.path.basename(rel))
        tp = os.path.join(dst, rel.replace('/', os.sep))
        data = B.norm_bytes(open(sp, 'rb').read())
        _write(tp, data)
        ev['added'].append({'path': rel, 'bytes': len(data), 'sha256': B.sha256_file(tp)})
        print('  [add] %s' % rel)

    # ③ speaker side-path: canonical ASR files, then v2.4 overrides, + w5 IR
    print('\n-- (3) asr_spk: canonical + v2.4 overrides (clustering v2 default) + fp16-w5 --')
    for n in B.SPK_FILES:
        sp = os.path.join(B.SPK_DEV, n)
        if n in SPK_OVR_FILES:
            sp = os.path.join(SPK_OVR, n)
        tp = os.path.join(dst, B.SPK_DST_REL, n)
        data = B.norm_bytes(open(sp, 'rb').read())
        _write(tp, data)
        ev['spk_assets'].append({'path': '%s/%s' % (B.SPK_DST_REL.replace('\\', '/'), n),
                                 'bytes': len(data), 'sha256': B.sha256_file(tp), 'source': sp})
    for n in SPK_OVR_FILES:
        if n in B.SPK_FILES:
            continue
        sp = os.path.join(SPK_OVR, n)
        tp = os.path.join(dst, B.SPK_DST_REL, n)
        data = B.norm_bytes(open(sp, 'rb').read())
        _write(tp, data)
        ev['spk_assets'].append({'path': '%s/%s' % (B.SPK_DST_REL.replace('\\', '/'), n),
                                 'bytes': len(data), 'sha256': B.sha256_file(tp), 'source': sp})
    for n in B.W5_FILES:
        sp = os.path.join(B.W5_DEV, n)
        tp = os.path.join(dst, B.W5_DST_REL, n)
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        shutil.copy2(sp, tp)
        ev['w5_assets'].append({'path': '%s/%s' % (B.W5_DST_REL.replace('\\', '/'), n),
                                'bytes': os.path.getsize(tp), 'sha256': B.sha256_file(tp)})
    spk_api = open(os.path.join(dst, B.SPK_DST_REL, 'asr052_speaker_tracker_api.py'), encoding='utf-8').read()
    assert "os.environ.get('ASR_SPK_CLUSTER', 'v2')" in spk_api, 'clustering v2 must be default'
    print('  [spk] %d files, clustering default = v2' % len(ev['spk_assets']))

    # ④ cross-module import scan (a dev module importing a local module the package lacks)
    print('\n-- (4) import scan --')
    pkg_mods = {n[:-3] for n in os.listdir(pkg_app) if n.endswith('.py')}
    spk_mods = {n[:-3] for n in os.listdir(os.path.join(dst, B.SPK_DST_REL)) if n.endswith('.py')}
    dev_mods = {n[:-3] for n in os.listdir(DEV) if n.endswith('.py')}
    missing_imp = {}
    for n in sorted(pkg_mods):
        imps = _local_imports(open(os.path.join(pkg_app, n + '.py'), encoding='utf-8').read())
        miss = sorted(m for m in imps if m in dev_mods and m not in pkg_mods and m not in spk_mods
                      and m not in OPTIONAL_DEV_IMPORTS)
        if miss:
            missing_imp[n] = miss
    ev['import_scan_missing'] = missing_imp
    print('  imports of dev-only modules: %r' % (missing_imp or 'none'))

    # completeness
    dst_names = B.names(dst)
    expected = (src_names - set(ev['skipped_excluded']))
    expected |= {r['path'] for r in ev['added']} | {r['path'] for r in ev['spk_assets']} | {r['path'] for r in ev['w5_assets']}
    missing, extra = sorted(expected - dst_names), sorted(dst_names - expected)
    ev.update(n_missing=len(missing), n_extra=len(extra), missing=missing[:20], extra=extra[:20])
    print('  [gate] completeness missing=%d extra=%d' % (len(missing), len(extra)))

    # clean gate
    print('\n-- (5) clean gate --')
    rc = assert_clean(dst)
    ev['gate_clean_rc'] = rc

    # ACCEPTED.json + MANIFEST
    mods = [n for n in sorted(os.listdir(pkg_app))
            if n.endswith('.py') and not pkg_exclude.is_app_dev_only('app/' + n)]
    per, h = {}, hashlib.sha256()
    for n in mods:
        d = B.norm_bytes(open(os.path.join(pkg_app, n), 'rb').read())
        per[n] = hashlib.sha256(d).hexdigest()
        h.update(n.encode('utf-8') + b'\0' + hashlib.sha256(d).digest())
    fp = h.hexdigest()
    payload = {
        'accepted': True, 'version': VERSION,
        'pkg_dir': '<HOME>\\Confucius4_LiveCaption_v%s' % VERSION,
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'built_by': 'reviewer (user decision 2026-11-07: drop v2.3, build v2.4)',
        'corrections': ['APP-075', 'APP-076', 'APP-078', 'APP-082', 'APP-083'],
        'binding_gate': 'app191', 'code_fingerprint': fp,
        'code_fingerprint_alg': ('app191.package_fingerprint: SHA256 over (name + NUL + '
                                 'SHA256(normalised module bytes)), sorted; scope = app/ production modules'),
        'n_production_modules': len(mods), 'code_fingerprints': per,
        'delivery_scope': ('v2.4: preset + follow_speaker clone voices (clone voices in memory only); '
                           'clone upgrade fix; speaker clustering v2 default (ASR_SPK_CLUSTER=v1 reverts); '
                           'all app modules = dev; TTS NPU cold compile trimmed (lazy 512 vocoder, buckets 8/16/32/33)'),
    }
    _write(os.path.join(dst, 'ACCEPTED.json'),
           json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'))
    man = os.path.join(pkg_app, 'MANIFEST.json')
    if os.path.isfile(man):
        m = json.load(open(man, encoding='utf-8'))
        ev['manifest_version_before'] = m.get('version')
        m['version'] = VERSION
        _write(man, json.dumps(m, ensure_ascii=False, indent=2).encode('utf-8'))

    dst_n, dst_bytes = B.dir_bytes(dst)
    after = {rel: {'bytes': os.path.getsize(os.path.join(src, rel.replace('/', os.sep))),
                   'sha256': B.sha256_file(os.path.join(src, rel.replace('/', os.sep)))} for rel in src_probe}
    ev.update(dst_files=dst_n, dst_bytes=dst_bytes, bytes_delta=dst_bytes - src_bytes,
              src_unchanged=(after == src_probe and B.names(src) == src_names),
              accepted_fp=fp, elapsed_s=round(time.time() - t0, 1))
    ok = (ev['src_unchanged'] and rc == 0 and not missing and not extra and not missing_imp)
    ev['verdict'] = 'PASS' if ok else 'FAIL'
    json.dump(ev, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n  synced %d modules, unchanged %d' % (len(ev['synced']), len(ev['unchanged'])))
    print('[%s] evidence %s (%.1f s)' % (ev['verdict'], a.json, ev['elapsed_s']))
    return 0 if ok else 6


if __name__ == '__main__':
    raise SystemExit(main())
