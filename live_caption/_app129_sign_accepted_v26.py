#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-129 §3.6：**签 v2.6 的 `ACCEPTED.json`**（含 Demucs 模型清单）。

🔴 **必须复用 `pack_v13.py` 自己的指纹函数**
   （`_acc_module_fingerprints` / `_acc_aggregate`）
   ⇒ 否则「签的」与「打包闸门⑤ 重算的」口径不一致 ⇒ **必 FAIL**。

🔴 **时机**：必须在**验收通过之后**、**打包之前**签
   （闸门⑤ 的语义就是「交付包 == 被验收过的包」）。

## 本版新增（APP-129 §2 明文）

> 模型身份核对：xml 1341298 B、bin 106628066 B，
> 并记录两者 SHA256 写进 ACCEPTED 的**模型清单**
> （对源 `shared\bgkeep\htdemucs_core.*`）。

⇒ `model_manifest` 里记录：EXT 版本 + commit、Demucs 两个文件的
   字节数 / SHA256 / 与源 `shared\bgkeep\` 的**逐字节一致**判定。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

#: APP-129 §2 钉死的模型身份（对源 `shared\bgkeep\htdemucs_core.*`）
EXPECT_MODEL = {
    'models/bgsep/htdemucs_core.xml': 1341298,
    'models/bgsep/htdemucs_core.bin': 106628066,
}

#: 🔴🔴 **EXT 版本链**（reviewer 逐条覆盖）：
#:   APP-129 `3573b2d`（v0.4.19）→ APP-131 `4740b06`（v0.4.20）
#:   → **APP-133 `b2a4978`（v0.4.21）＝ 本轮交付口径**
#:   （reviewer：「v2.6 的 EXT 改用 b2a4978（替代 APP-131 的 4740b06）」）
EXT_COMMIT = 'b2a4978'
EXT_VERSION = '0.4.21'
SRC_BG = os.path.join(HOME, 'shared', 'bgkeep')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=os.path.join(
        HOME, 'Confucius4_LiveCaption_v2.6'))
    ap.add_argument('--version', default='2.6')
    ap.add_argument('--json', default=os.path.join(
        REPO, 'results', 'app', 'app129_sign_accepted_v26_evidence.json'))
    args = ap.parse_args()

    sys.path.insert(0, REPO)
    import pack_v13 as P          # 🔴 复用它自己的指纹函数（口径一致）

    app_dir = os.path.join(args.pkg, 'app')
    if not os.path.isdir(app_dir):
        print('FAIL: 包内 app/ 不存在：%s' % app_dir)
        return 2

    per = P._acc_module_fingerprints(app_dir)
    agg = P._acc_aggregate(per)
    mods = sorted(per)

    # ── 模型清单（Demucs）+ 源一致性 ────────────────────────────────
    model_manifest = {}
    model_errors = []
    for rel, want_bytes in EXPECT_MODEL.items():
        p = os.path.join(args.pkg, rel.replace('/', os.sep))
        src = os.path.join(SRC_BG, os.path.basename(rel))
        rec = {'bytes': os.path.getsize(p) if os.path.isfile(p) else None,
               'sha256': sha256(p) if os.path.isfile(p) else None,
               'expect_bytes': want_bytes,
               'source': os.path.relpath(src, HOME)}
        if not os.path.isfile(p):
            rec['ok'] = False
            model_errors.append('模型缺失：%s' % rel)
        elif rec['bytes'] != want_bytes:
            rec['ok'] = False
            model_errors.append('模型字节数不符：%s（%s != %s）'
                                % (rel, rec['bytes'], want_bytes))
        elif not os.path.isfile(src):
            rec['ok'] = False
            model_errors.append('源模型缺失：%s' % src)
        elif sha256(src) != rec['sha256']:
            rec['ok'] = False
            model_errors.append('与源模型 SHA256 不一致：%s' % rel)
        else:
            rec['ok'] = True
        model_manifest[rel] = rec

    # ── EXT 身份 ───────────────────────────────────────────────────
    ext_ver = None
    try:
        vpy = open(os.path.join(args.pkg, 'ext', 'bridge', 'version.py'),
                   encoding='utf-8').read()
        for line in vpy.splitlines():
            if line.startswith('EXT_VERSION'):
                ext_ver = line.split('=', 1)[1].strip().strip('"')
                break
    except Exception:
        pass

    old = {}
    old_path = os.path.join(args.pkg, 'ACCEPTED.json')
    if os.path.isfile(old_path):
        try:
            old = json.load(open(old_path, encoding='utf-8'))
        except Exception:
            old = {}

    payload = {
        'accepted': True,
        'version': args.version,
        'pkg_dir': '<HOME>\\Confucius4_LiveCaption_v%s' % args.version,
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'built_by': ('App module / APP-129 + APP-130 (2026-11-24): '
                     'EXT v0.4.21 (b2a4978) + Demucs 分离模型 + APP-123 c13 '
                     '+ APP-130 code-predictor NPU 自检兜底；'
                     'acceptance run on this package before signing'),
        'corrections': ['APP-129', 'APP-130', 'APP-131',
                         'APP-132', 'APP-133', 'APP-123'],
        'binding_gate': 'app191',
        'code_fingerprint': agg,
        'code_fingerprint_alg': (
            'app191.package_fingerprint: SHA256 over (name + NUL + '
            'SHA256(normalised module bytes)), sorted; '
            'scope = app/ production modules'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'ext': {'version': ext_ver, 'commit': EXT_COMMIT,
                'layout': 'ext/bridge/*.py（包内是**包**，模块 = '
                          'ext/bridge/bridge.py）',
                'plugin': 'ext/extension/*'},
        'model_manifest': model_manifest,
        'delivery_scope': (
            'v2.6（完整版全集，MiniMVP / SpecialMVP 不带）：'
            '(1) EXT **v0.4.21（b2a4978）**——「保留背景音」默认**开**、'
            '默认分离设备 **GPU.0(FP32)**（可用 EXT_BG_DEVICE=CPU 改）、'
            '克隆音色跟随男女切换（v0.4.20，APP-131）＋'
            '按音高把男女混在一起的段切开（v0.4.21，APP-133）；'
            '(2) Demucs 分离模型随包（models/bgsep/，身份见 model_manifest）；'
            '(3) APP-123 c13 小窗 + 直接拼接（38 帧窗口 / 25 帧左上下文 / '
            'crossfade=0）；'
            '(4) APP-130 code predictor 的 **NPU 自检兜底 + 运行时保险**'
            '（自检不过 ⇒ cp 留 CPU；NaN ⇒ 本句立刻停并记 tts_runaway）；'
            '⚠️ 保留背景音与 c13 两项**分开验收、分开报数字**（APP-129 §2）'),
    }
    for k, v in old.items():
        if k not in payload and k not in ('accepted', 'version', 'pkg_dir',
                                          'accepted_at', 'code_fingerprint',
                                          'code_fingerprints',
                                          'n_production_modules'):
            payload[k] = v

    out = os.path.join(args.pkg, 'ACCEPTED.json')
    tmp = out + '.tmp_sign'
    with open(tmp, 'wb') as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, out)

    back = json.load(open(out, encoding='utf-8'))
    per2 = P._acc_module_fingerprints(app_dir)
    agg2 = P._acc_aggregate(per2)
    checks = [
        ('accepted=True', back.get('accepted') is True),
        ('version=%s' % args.version, str(back.get('version')) == args.version),
        ('pkg_dir 目录名一致',
         os.path.basename(str(back.get('pkg_dir')).replace('\\', '/'))
         == os.path.basename(args.pkg)),
        ('code_fingerprints 非空', bool(back.get('code_fingerprints'))),
        ('逐条指纹一致', back.get('code_fingerprints') == per2),
        ('集合一致（无缺/多）',
         set(back.get('code_fingerprints') or {}) == set(per2)),
        ('聚合指纹一致', back.get('code_fingerprint') == agg2),
        ('模型清单齐全且逐条 OK',
         bool(model_manifest) and all(v.get('ok') for v in model_manifest.values())),
        ('EXT 版本 = %s（APP-133）' % EXT_VERSION, ext_ver == EXT_VERSION),
    ]
    print('=== v%s ACCEPTED.json 签名 ===' % args.version)
    print('  生产模块 %d 个；聚合指纹 %s' % (len(mods), agg2))
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))
    for m in model_errors:
        print('  [FAIL] %s' % m)

    ok, reason, detail = P.check_acceptance_binding(args.pkg, args.version)
    print('  闸门⑤ check_acceptance_binding：%s（%s）' % (ok, reason))
    if not ok:
        print('  detail: %s' % json.dumps(detail, ensure_ascii=False)[:800])

    ev = {'pkg': args.pkg, 'version': args.version, 'n_modules': len(mods),
          'aggregate': agg2, 'checks': {n: bool(o) for n, o in checks},
          'model_manifest': model_manifest, 'ext_version': ext_ver,
          'gate5_ok': bool(ok), 'gate5_reason': reason,
          'gate5_detail': detail, 'bytes': os.path.getsize(out)}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('  证据：%s' % args.json)
    bad = [n for n, o in checks if not o]
    return 0 if (not bad and ok and not model_errors) else 1


if __name__ == '__main__':
    sys.exit(main())
