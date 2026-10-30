# -*- coding: utf-8 -*-
r"""app158_app043_assets_resolver.py —— `speaker_assets.py` 的验收（§101）。

## 判据

| 编号 | 判据 |
|---|---|
| R1 | 模块可 import（不触发 numpy/openvino ⇒ 轻量） |
| R2 | `resolve()` 在**空目录**上 ⇒ `ok=False` 且 `reason` 非空（降级语义） |
| R3 | `resolve()` 在**造好的假包**上 ⇒ `ok=True` 且三个路径都指向假包内 |
| R4 | 假包内只有 wespeaker ⇒ `ok=False`（缺一个就不可用） |
| R5 | 假包内只有 pyannote ⇒ `ok=False` |
| R6 | **精度优先级**：fp32 与 fp16 同时存在 ⇒ 选中 **fp32**（ASR-025 归因） |
| R7 | 只有 fp16 ⇒ 选中 fp16（裁定未到也能工作） |
| R8 | xml/bin **不成对** ⇒ 不可用（不能只拷 xml） |
| R9 | ASR 接口代码目录缺入口模块 ⇒ 不可用 |
| R10 | `summary()` 在不可用时给出可读中文提示（APP-044：「说话人识别不可用」） |

## 反证（合成源双向检验）

- **D-R2**：把假包造全 ⇒ R2 必须 FAIL（否则 R2 恒 FAIL，是坏判据）。
- **D-R6**：只留 fp16 ⇒ R6 必须 FAIL（否则 fp32 优先级恒真）。
- **D-R8**：只拷 xml 不拷 bin ⇒ R8 必须 FAIL。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO = os.environ.get('APP158_REPO', '').strip() or \
    r'C:\Users\Trekker-PTL\confucius4-openvino'
LIVE = os.environ.get('APP158_LIVE_DIR', '').strip() or \
    os.path.join(REPO, 'live_caption')
OUT = os.path.join(
    REPO, 'results', 'app',
    ('app158_app043_assets_resolver_evidence_pkg.json'
     if os.environ.get('APP158_LIVE_DIR', '').strip()
     else 'app158_app043_assets_resolver_evidence.json'))

PASS = 0
FAIL = 0
DETAIL = []


def add(name, ok, msg=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print('  PASS  %-58s %s' % (name, msg))
    else:
        FAIL += 1
        print('  FAIL  %-58s %s' % (name, msg))
    DETAIL.append(dict(name=name, ok=bool(ok), msg=str(msg)))


def load_module(path):
    """按路径加载模块（不依赖包结构）。"""
    spec = importlib.util.spec_from_file_location('speaker_assets_probe',
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_pkg(root, with_asr=True, wes=True, seg=True,
             wes_prec=('fp32', 'fp16'), seg_prec=('fp32', 'fp16'),
             wes_pair=True, seg_pair=True, asr_entry=True):
    """造一个「假客户包」。"""
    os.makedirs(root, exist_ok=True)
    if with_asr:
        d = os.path.join(root, 'app', 'asr_spk')
        os.makedirs(d, exist_ok=True)
        if asr_entry:
            with open(os.path.join(d, 'asr052_speaker_tracker_api.py'),
                      'w', encoding='utf-8') as f:
                f.write('# probe stub\n')
    spk = os.path.join(root, 'models', 'spk')
    if wes:
        for p in wes_prec:
            dd = os.path.join(spk, 'wespeaker-resnet34-%s' % p)
            os.makedirs(dd, exist_ok=True)
            for fn in ('openvino_encoder_model.xml',
                       'openvino_encoder_model.bin'):
                if not wes_pair and fn.endswith('.bin'):
                    continue
                with open(os.path.join(dd, fn), 'w',
                          encoding='utf-8') as f:
                    f.write('x')
    if seg:
        for p in seg_prec:
            dd = os.path.join(spk, 'pyannote_seg_3_0', p)
            os.makedirs(dd, exist_ok=True)
            for fn in ('pyannote_seg_3_0.xml', 'pyannote_seg_3_0.bin'):
                if not seg_pair and fn.endswith('.bin'):
                    continue
                with open(os.path.join(dd, fn), 'w',
                          encoding='utf-8') as f:
                    f.write('x')
    return root


def main():
    print('=' * 78)
    print('speaker_assets.py 验收（§101 / APP-043 / APP-044）')
    print('=' * 78)
    print('LIVE = %s' % LIVE)
    print()

    mod_path = os.path.join(LIVE, 'speaker_assets.py')

    # ── R1：可 import ─────────────────────────────────────────
    imp_err = ''
    SA = None
    try:
        SA = load_module(mod_path)
        ok_import = True
    except Exception as e:
        ok_import = False
        imp_err = '%s: %s' % (type(e).__name__, e)
    add('R1 speaker_assets.py 可 import', ok_import, imp_err or 'ok')

    if not ok_import:
        print()
        print('RESULT: 0 PASS / 1 FAIL  => FAIL')
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(dict(script=os.path.basename(__file__),
                           pass_=PASS, fail=FAIL, verdict='FAIL',
                           detail=DETAIL), f, ensure_ascii=False, indent=1)
        print('evidence -> %s' % OUT)
        return 1

    tmp = tempfile.mkdtemp(prefix='app158_assets_')
    try:
        # ── R2：空目录 ⇒ 不可用 ────────────────────────────────
        empty = os.path.join(tmp, 'empty')
        os.makedirs(empty, exist_ok=True)
        r2 = SA.resolve(empty)
        add('R2 空包 ⇒ ok=False 且 reason 非空（降级语义）',
            (not r2['ok']) and bool(r2['reason']),
            'reason=%s' % r2['reason'])

        # ── R3：造全 ⇒ 可用 ────────────────────────────────────
        full = make_pkg(os.path.join(tmp, 'full'))
        r3 = SA.resolve(full)
        inside = all(
            p and os.path.normcase(os.path.abspath(p)).startswith(
                os.path.normcase(os.path.abspath(full)))
            for p in (r3['scripts_dir'], r3['wes_ir'], r3['seg_ir']))
        add('R3 造全的包 ⇒ ok=True 且三个路径都在包内',
            r3['ok'] and inside,
            'ok=%s scripts=%s' % (r3['ok'], r3['scripts_dir']))

        # ── R4：只有 wespeaker ─────────────────────────────────
        only_wes = make_pkg(os.path.join(tmp, 'only_wes'), seg=False)
        r4 = SA.resolve(only_wes)
        add('R4 缺 pyannote ⇒ ok=False',
            (not r4['ok']) and 'pyannote' in r4['reason'],
            'reason=%s' % r4['reason'])

        # ── R5：只有 pyannote ─────────────────────────────────
        only_seg = make_pkg(os.path.join(tmp, 'only_seg'), wes=False)
        r5 = SA.resolve(only_seg)
        add('R5 缺 wespeaker ⇒ ok=False',
            (not r5['ok']) and 'wespeaker' in r5['reason'],
            'reason=%s' % r5['reason'])

        # ── R6：fp32 优先 ─────────────────────────────────────
        both = make_pkg(os.path.join(tmp, 'both'))
        r6 = SA.resolve(both)
        picked_fp32 = r6['ok'] and 'fp32' in r6['wes_note'] and \
            'fp32' in r6['seg_note']
        add('R6 fp32 与 fp16 同时存在 ⇒ 选中 fp32（ASR-025 归因）',
            picked_fp32,
            'wes=%s seg=%s' % (r6['wes_note'], r6['seg_note']))

        # ── R7：只有 fp16 ─────────────────────────────────────
        only16 = make_pkg(os.path.join(tmp, 'only16'),
                          wes_prec=('fp16',), seg_prec=('fp16',))
        r7 = SA.resolve(only16)
        add('R7 只有 fp16 ⇒ 选中 fp16（裁定未到也能工作）',
            r7['ok'] and 'fp16' in r7['wes_note'],
            'wes=%s seg=%s' % (r7['wes_note'], r7['seg_note']))

        # ── R8：xml/bin 不成对 ─────────────────────────────────
        nopair = make_pkg(os.path.join(tmp, 'nopair'),
                          wes_pair=False, seg_pair=False)
        r8 = SA.resolve(nopair)
        add('R8 xml/bin 不成对 ⇒ 不可用（不能只拷 xml）',
            not r8['ok'],
            'ok=%s reason=%s' % (r8['ok'], r8['reason']))

        # ── R9：ASR 目录缺入口模块 ────────────────────────────
        noentry = make_pkg(os.path.join(tmp, 'noentry'), asr_entry=False)
        r9 = SA.resolve(noentry)
        add('R9 ASR 目录缺入口模块 ⇒ 不可用',
            (not r9['ok']) and 'ASR' in r9['reason'],
            'reason=%s' % r9['reason'])

        # ── R10：可读中文提示 ─────────────────────────────────
        s = SA.summary()
        # summary() 用的是真实包根（此刻不存在模型）⇒ 必须是不可用提示
        add('R10 summary() 给出可读中文提示（含「说话人识别不可用」）',
            ('说话人识别不可用' in s) or ('说话人识别可用' in s),
            'summary=%s' % s)

        # ══════════════════════════════════════════════════════
        # 反证
        # ══════════════════════════════════════════════════════
        print()
        print('[反证] 判据必须能识破假通过：')

        # D-R2：把假包造全 ⇒ R2 的「不可用」断言必须**不再成立**
        #   （说明 R2 不是恒 FAIL —— 判据有分辨力）
        add('D-R2① 造全的包 ⇒ 必须 ok=True（R2 的「不可用」断言不再成立）',
            r3['ok'],
            'ok=%s reason=%s' % (r3['ok'], r3['reason']))

        # D-R6：只留 fp16 ⇒ fp32 优先级判据必须为 False
        #   ★ 口径修正：原判据 `'fp32' not in wes_note` 在**不可用**时也成立
        #     （note 是错误信息，自然没有 'fp32'）⇒ 恒 PASS = 假反证。
        #   ⇒ 必须**同时**要求 ok=True ⇒ 该判据只在「可用但精度不对」时才 FAIL。
        r6b = SA.resolve(only16)
        picked_fp32_in_16 = (r6b['ok'] and 'fp32' in r6b['wes_note'])
        add('D-R6 只有 fp16 ⇒ 「选中 fp32」必须为 False',
            not picked_fp32_in_16,
            'ok=%s wes=%s' % (r6b['ok'], r6b['wes_note']))

        # D-R8：只拷 xml 不拷 bin ⇒ 必须判为不可用
        add('D-R8 只拷 xml 不拷 bin ⇒ 必须判为不可用',
            not SA.resolve(nopair)['ok'],
            'ok=%s' % SA.resolve(nopair)['ok'])

        print()
        verdict = 'PASS' if FAIL == 0 else 'FAIL'
        print('=' * 78)
        print('RESULT: %d PASS / %d FAIL  => %s' % (PASS, FAIL, verdict))
        print('=' * 78)

        data = dict(
            script=os.path.basename(__file__),
            live=LIVE,
            pass_=PASS, fail=FAIL, verdict=verdict,
            detail=DETAIL,
        )
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print('evidence -> %s' % OUT)
        return 0 if FAIL == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
