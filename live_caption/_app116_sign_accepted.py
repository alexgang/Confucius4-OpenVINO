#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §5：**重签 v2.5 的 `ACCEPTED.json`**（APP-055「打新版本号 ⇒ 重签」）。

🔴 **必须复用 `pack_v13.py` 自己的指纹函数**
   （`_acc_module_fingerprints` / `_acc_aggregate` / `_acc_production_modules`）
   ⇒ 否则「签的」与「打包闸门⑤ 重算的」口径不一致 ⇒ **必 FAIL**。

🔴 **时机**：必须在**验收通过之后**、**打包之前**签
   （闸门⑤ 的语义就是「交付包 == 被验收过的包」）。
   ⇒ 打包只会重写 README/NOTICE/MANIFEST.json（**不在指纹范围**）⇒ 先签后打包安全。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
VERSION = '2.5'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--version', default=VERSION)
    ap.add_argument('--json', default=os.path.join(
        REPO, 'results', 'app', 'app116_sign_accepted_evidence.json'))
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

    # 读旧文件（保留上一版的说明字段，便于审计）
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
        'built_by': ('App module / APP-116 (2026-11-20): TTS output-device fix + '
                     'preset B (male) asset + GUI 4 options removed; '
                     'acceptance run on this package before signing'),
        'corrections': ['APP-116'],
        'binding_gate': 'app191',
        'code_fingerprint': agg,
        'code_fingerprint_alg': ('app191.package_fingerprint: SHA256 over (name + NUL + '
                                 'SHA256(normalised module bytes)), sorted; '
                                 'scope = app/ production modules'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'delivery_scope': (
            'v2.5: (1) TTS 输出设备修复（GUI 反查表方向纠正 + 逐跳日志 + 不静默回落 + '
            '运行中切设备只重开播放流）；(2) 音色下拉「预设 A（女声）」，'
            '「预设 B（男声）」**仅在参考音频存在时列出**；'
            '🔴 **preset_B.wav 未随包分发**（reviewer APP-116 §2：用户抽听点头前不进包）；'
            '(3) GUI 去掉 草稿译文/重试翻译/区分说话人/显示说话人（默认值不变）；'
            '(4) 顺带带入 APP-114/115 的语速上限 1.70× 与「就绪前不丢句」'),
        'preset_b_in_package': False,
        'preset_b_note': ('预设 B（男声）参考音频由 Qwen3-TTS-12Hz-0.6B-CustomVoice '
                          '（Apache-2.0）模型生成，位于仓库 '
                          'results/app/app116_preset_b_gen/preset_B.wav；'
                          '**按 reviewer 要求，用户抽听点头前不进包**'),
    }
    # 保留上一版的其它说明字段（不丢审计信息）
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

    # 写后独立复核：重新读回来 + 用 pack 的函数重算 ⇒ 必须完全一致
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
    ]
    print('=== v2.5 ACCEPTED.json 重签 ===')
    print('  生产模块 %d 个；聚合指纹 %s' % (len(mods), agg2))
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))

    # 再跑一次打包闸门⑤（真正的那道门）
    ok, reason, detail = P.check_acceptance_binding(args.pkg, args.version)
    print('  闸门⑤ check_acceptance_binding：%s（%s）' % (ok, reason))
    if not ok:
        print('  detail: %s' % json.dumps(detail, ensure_ascii=False)[:800])
    ev = {'pkg': args.pkg, 'version': args.version, 'n_modules': len(mods),
          'aggregate': agg2, 'checks': {n: bool(o) for n, o in checks},
          'gate5_ok': bool(ok), 'gate5_reason': reason,
          'gate5_detail': detail, 'bytes': os.path.getsize(out)}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('  证据：%s' % args.json)
    bad = [n for n, o in checks if not o]
    return 0 if (not bad and ok) else 1


if __name__ == '__main__':
    sys.exit(main())
