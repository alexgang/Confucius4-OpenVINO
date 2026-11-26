#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§247（APP-147 第 5 步）：**签 MiniMVP v1.2 的 ACCEPTED.json**。

口径**完全照抄** `_app121_sign_accepted_v111.py`（v1.1.1 已通过闸门⑤）：
- 复用 `pack_v13.py` 自己的指纹函数（`_acc_module_fingerprints` / `_acc_aggregate`）
  ⇒ 「签的」与「打包闸门重算的」口径必须一致，否则必 FAIL；
- 时机：**验收通过之后、打包之前**（闸门⑤ 语义＝交付包 == 被验收过的包）；
- 落盘用临时文件 + `os.replace`；写后重读并逐条复核 ＋ 跑闸门⑤。

只改三处**文案与指向**：默认包路径（v1.2）、`built_by`、`corrections`／`delivery_scope`。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2'
VERSION = '1.2'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--version', default=VERSION)
    ap.add_argument('--json', default=os.path.join(
        REPO, 'results', 'app', 'app247_sign_accepted_v12_evidence.json'))
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
        'built_by': ('App module / APP-147 (2026-11-26): MiniMVP v1.2 —— '
                     '在 v1.1.1 基础上并入 EXT 全部功能（含「保留背景音」bgkeep）'
                     '与音色克隆；翻译模型换 Hy-MT3-1.8B INT8-CW（包内只带 mt3）；'
                     'EXT 升到 v0.4.23（ASR 自动适配包内模型族 Qwen3-ASR 0.6B）；'
                     'NPU turbo 默认开。'
                     '验收（本轮实测，证据见 STATUS §245/§247）：'
                     '洁净白名单 19/19 ＋ MT3 权重 3 处固定偏移 hex 与源一致、与 MT2 全不同 '
                     '＋ 三轮整链（背景音关/开/开+克隆）rc=0、lock_lost=0、'
                     'n_pending 排空后为 0、丢句 0、NaN 0、削波 0、'
                     'MT 就绪 Hy-MT3 INT8 @ GPU.0、NPU_TURBO=True、落点 NPU 9 组件 / CPU 0 '
                     '＋ 解压自检。'
                     '🔴 **reviewer 从 zip 复核待做；B 机复验待做**（APP-147：B 机不挡发版）。'),
        'corrections': ['APP-137', 'APP-138', 'APP-139', 'APP-141', 'APP-144',
                        'APP-146', 'APP-147', 'APP-148', 'APP-149', 'APP-150',
                        'APP-151'],
        'binding_gate': 'app191',
        'code_fingerprint': agg,
        'code_fingerprint_alg': ('app191.package_fingerprint: SHA256 over (name + NUL + '
                                 'SHA256(normalised module bytes)), sorted; '
                                 'scope = app/ production modules'),
        'n_production_modules': len(mods),
        'code_fingerprints': per,
        'delivery_scope': (
            'MiniMVP v1.2（按 minimvp profile 裁剪，并入 EXT 全部功能）：'
            '(1) ASR 只带 Qwen3-ASR-0.6B stateful INT8（含 ASR-065/066 优化：'
            'NPUW MAX_PROMPT_LEN=320 + 超长前缀按 token 左截断）；'
            '(2) MT 只带 Hy-MT3-1.8B INT8-CW（`models/mt/` 下只有 mt3，不带 mt2）；'
            '(3) TTS 只带 OpenVINO 版（**无 cuda_env / 无 models/tts_cuda**），出厂 TTS=NPU；'
            '(4) 音色只有预设 A（**preset_B 不进包**）；克隆代码与模型随包，'
            '**包内克隆音色目录为空**（首次使用现场采集）；'
            '(5) EXT v0.4.23（桥接 + 插件，含「保留背景音」默认开、音色克隆默认关）；'
            '(6) 10 语种；出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU，设备自由配置；'
            '(7) NPU turbo 默认开（`LIVECAP_NPU_TURBO=0` 可关）；'
            '(8) 包内**不含**录音/同事音色/克隆音色/babelvox 样本/CUDA。'),
        'preset_b_in_package': False,
        'preset_b_note': ('预设 B 用户尚未抽听点头 ⇒ 不进包'
                          '（APP-120 §1 口径沿用到 v1.2）'),
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
    print('=== MiniMVP v1.2 ACCEPTED.json 签署 ===')
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
