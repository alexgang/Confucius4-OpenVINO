#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120 §2：**签 MiniMVP v1.1 的 `ACCEPTED.json`**（version=1.1）。

## 与 `_app116_sign_accepted.py` 的差别
🔴 **包目录名不同**：`Confucius4_LiveCaption_MiniMVP_v1.1`
   ⇒ `pkg_dir` 必须写成 `<HOME>\\Confucius4_LiveCaption_MiniMVP_v1.1`
   ⇒ 否则出包闸门⑤ `check_acceptance_binding` 会判 `PKG_MISMATCH`（fail-closed）。

## 其余口径与 APP-116 完全一致
- **必须复用 `pack_v13.py` 自己的指纹函数**
  （`_acc_module_fingerprints` / `_acc_aggregate` / `_acc_production_modules`）
  ⇒ 否则「签的」与「打包闸门重算的」口径不一致 ⇒ 必 FAIL；
- 时机：**验收通过之后、打包之前**签
  （闸门⑤ 的语义＝「交付包 == 被验收过的包」）。

## 用法
```
python live_caption/_app120_sign_accepted_v11.py --pkg <v1.1 目录> --version 1.1
```
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1'
VERSION = '1.1'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--version', default=VERSION)
    ap.add_argument('--json', default=os.path.join(
        REPO, 'results', 'app', 'app120_sign_accepted_v11_evidence.json'))
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

    old = {}
    old_path = os.path.join(args.pkg, 'ACCEPTED.json')
    if os.path.isfile(old_path):
        try:
            old = json.load(open(old_path, encoding='utf-8'))
        except Exception:
            old = {}

    pkg_base = os.path.basename(os.path.normpath(args.pkg))
    payload = {
        'accepted': True,
        'version': args.version,
        'pkg_dir': '<HOME>\\%s' % pkg_base,
        'accepted_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'built_by': ('App module / APP-120 (2026-11-22): 从 v2.5 全集按 minimvp '
                     'profile 裁剪 MiniMVP v1.1；ASR-065/066 优化接入；'
                     '验收（自检 + 洁净度 + 模型身份 + 10 分钟整链 + 10 语种 + '
                     '设备切换 + 全新目录/旧配置迁移）在本包上完成后签署'),
        'corrections': ['APP-120'],
        'binding_gate': 'app191',
        'code_fingerprint': agg,
        'code_fingerprint_alg': ('app191.package_fingerprint: SHA256 over (name + NUL + '
                                 'SHA256(normalised module bytes)), sorted; '
                                 'scope = app/ production modules'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'delivery_scope': (
            'MiniMVP v1.1（从 v2.5 全集按 minimvp profile 裁剪）：'
            '(1) ASR 只带 Qwen3-ASR-0.6B stateful INT8，**含 ASR-065/066 优化**'
            '（NPUW MAX_PROMPT_LEN=320 + 超长前缀按 token 左截断 + '
            'asr_enc_tiers 默认 off + 分档失败自动退回 2400 单档）；'
            '(2) MT 只带 Hy-MT2 INT8-CW（无 INT4）；'
            '(3) TTS 只带 OpenVINO 版（**无 cuda_env / 无 models/tts_cuda**）；'
            '(4) 音色只有预设 A（**preset_B 不进包**）、无克隆；'
            '(5) 10 语种 + APP-116/117 界面改动；'
            '(6) 出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU，**设备自由配置**'
            '（APP-119 取消 NPU 互斥）；'
            '(7) 包内**不含**录音/同事音色/克隆音色/babelvox 样本/CUDA。'),
        'preset_b_in_package': False,
        'preset_b_note': ('预设 B 用户尚未抽听点头 ⇒ 按 reviewer 要求不进包'
                          '（APP-120 §1）'),
        'profile': 'minimvp',
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
    ]
    print('=== MiniMVP v1.1 ACCEPTED.json 签署 ===')
    print('  生产模块 %d 个；聚合指纹 %s' % (len(mods), agg2))
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))

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
