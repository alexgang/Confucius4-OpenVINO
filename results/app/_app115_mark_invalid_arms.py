"""🔴 **APP-115 §3.3-1**：把 094715 / 100823 两臂的验收 json 补写 `timing_valid=false`。

⚠️ **只读原文件 ⇒ 另写 v2**（reviewer 明确许可：「旧文件保留，另写 v2 文件也可以」）
   ⇒ 原 json **逐字节不动**（写前写后 SHA256 对账）。
⚠️ 报告项/判定逻辑**复用验收 harness 自己的函数**
   （`finalize_app115` / `pct` / `parse_telemetry`）⇒ 与新臂同一套口径，
   数值可直接与 reviewer 的表对表。

用法：python results/app/_app115_mark_invalid_arms.py
"""
import hashlib
import importlib.util
import json
import os
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
RESULTS = os.path.join(REPO, 'results', 'app')
HARNESS = os.path.join(RESULTS, '_app588_sp4_acceptance.py')

#: 两臂 = reviewer 点名的「计时无效」臂
ARMS = [
    ('sp5_zh', '20261117-094715'),
    ('sp5_zh', '20261117-100823'),
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def load_harness():
    spec = importlib.util.spec_from_file_location('h588', HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    H = load_harness()
    report = []
    for tag, run_id in ARMS:
        src = os.path.join(RESULTS, 'app591_acceptance_%s_run%s.json'
                           % (tag, run_id))
        if not os.path.isfile(src):
            print('SKIP（原件不存在）：%s' % src)
            continue
        before = sha256_file(src)
        with open(src, encoding='utf-8') as f:
            ev = json.load(f)
        jsonl = os.path.join(RESULTS, '_app591_%s_run%s_tts_out.wav.tts.jsonl'
                             % (tag, run_id))
        rows = H.parse_telemetry(jsonl)
        sr = [float(r['synth_rtf']) for r in rows
              if r.get('synth_rtf') is not None and not r.get('dropped')]
        tel = ev.setdefault('telemetry', {})
        tel['synth_rtf_n'] = len(sr)
        tel['synth_rtf_p50'] = H.pct(sr, 0.50)
        tel['synth_rtf_p90'] = H.pct(sr, 0.90)
        tel['synth_rtf_max'] = (max(sr) if sr else None)
        tel['synth_rtf_min'] = (min(sr) if sr else None)
        tel['synth_rtf_n_gt_1'] = sum(1 for x in sr if x > 1.0)
        tel['synth_rtf_n_ge_0_75'] = sum(1 for x in sr if x > 0.75)
        # 🔴 复用 harness 的判定/报告项逻辑（同一套口径）
        ev = H.finalize_app115(ev)
        ev['app115'] = {
            'correction': 'APP-115 §3.3-1',
            'v2_of': os.path.basename(src),
            'original_untouched': True,
            'original_sha256_before': before,
            'reason': ('锁在运行中丢失（放锁时锁内容=%r ⇒ 不是本作业）+ '
                       'synth_rtf P90=%.4f > 1.1'
                       % ((ev.get('lock_evidence') or {}).get(
                              'lock_content_at_release'),
                          tel['synth_rtf_p90'])),
            'reviewer_reference': (
                'reviewer 的表：sp5 zh 094715 ⇒ synth_rtf 中位 0.665 / P90 1.165 / '
                'RTF>1 共 37 句；sp5 zh 100823 ⇒ 0.664 / 1.282 / 48 句'
                ' ⇒ 本 v2 用同一批 jsonl + 同一算法复算'),
        }
        ev['purpose'] = (ev.get('purpose', '') +
                         '｜**APP-115 v2**：计时无效（锁在运行中丢失 + synth_rtf P90>1.1）')
        out = os.path.join(RESULTS, 'app591_acceptance_%s_run%s_v2.json'
                           % (tag, run_id))
        tmp = out + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(ev, f, ensure_ascii=False, indent=1)
        os.replace(tmp, out)
        after = sha256_file(src)
        print('%-46s → %s' % (os.path.basename(src), os.path.basename(out)))
        print('   原件 SHA 不变：%s' % (before == after))
        print('   timing_valid=%r  P50=%s P90=%s n>1=%s'
              % (ev.get('timing_valid'), tel['synth_rtf_p50'],
                 tel['synth_rtf_p90'], tel['synth_rtf_n_gt_1']))
        print('   原因：%s' % ev.get('timing_invalid_reason'))
        print('   v2 bytes=%d sha256=%s'
              % (os.path.getsize(out), sha256_file(out)))
        report.append({'src': src, 'out': out, 'sha_before': before,
                       'sha_after': after, 'timing_valid': ev.get('timing_valid'),
                       'p50': tel['synth_rtf_p50'], 'p90': tel['synth_rtf_p90'],
                       'n_gt_1': tel['synth_rtf_n_gt_1'],
                       'bytes': os.path.getsize(out),
                       'sha256': sha256_file(out)})
    rp = os.path.join(RESULTS, 'app591_app115_invalid_arms_v2.json')
    tmp = rp + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'correction': 'APP-115 §3.3-1',
                   'note': ('094715 / 100823 两臂计时无效（锁在运行中丢失 + '
                            'synth_rtf P90>1.1）⇒ 旧 json 逐字节保留，另写 v2；'
                            '本文件是对账索引。'),
                   'arms': report}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, rp)
    print('\n对账索引：%s (%d B)' % (rp, os.path.getsize(rp)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
