r"""_app314 — APP-079(a)/(2) 的**纯静态**归因（不占设备、不加载模型）。

APP-080 已把 APP-071/075/079 转入后续版本，且「v2.3 发布前不再为克隆占用设备」
⇒ 本脚本只做「为何 submit 行 spk=null / clone_active=False」的落盘证据复核，
   不跑 (b)(c)(d) 的设备级修复与 r3 交付。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
R2 = r'C:\Users\Trekker-PTL\shared\app_listen\v23_clone_r2'
OUT = os.path.join(HERE, '_app314_app079_static_triage.json')


def stat_of(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                sha256=hashlib.sha256(b).hexdigest())


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]


def analyse(submit, tts, seg, gate, svc_text, spkvoice_text):
    """同一把判据，供正证与反证复用（反证必须能被识破）。"""
    checks = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=bool(cond), detail=detail))

    n_submit, n_tts = len(submit), len(tts)
    spk_null = sum(1 for r in submit if r.get('spk') is None)
    conf_null = sum(1 for r in submit if r.get('spk_conf') is None)
    ca_false = sum(1 for r in tts if r.get('clone_active') is False)
    vk_clone = sum(1 for r in tts if r.get('voice_kind') == 'clone')
    vspk_null = sum(1 for r in tts if r.get('voice_spk') is None)
    seg_conf_vals = [r.get('spk_conf') for r in seg if r.get('spk_conf') is not None]
    vc = gate.get('verdict_counts', {})

    chk(n_submit > 0 and n_tts > 0, 'r2_data_present',
        'submit=%d tts=%d' % (n_submit, n_tts))
    chk(conf_null == n_submit, 'submit_spk_conf_all_null',
        'spk_conf null %d/%d ⇒ conf 门槛拿不到输入' % (conf_null, n_submit))
    chk(ca_false == n_tts, 'clone_active_all_false',
        'clone_active=False %d/%d（与 reviewer 独立复核一致）' % (ca_false, n_tts))
    vspk_non_null = n_tts - vspk_null
    chk(vk_clone > 0 and ca_false == n_tts,
        'voice_kind_clone_is_not_clone_evidence',
        "voice_kind='clone'=%d 但 clone_active=False %d/%d ⇒ "
        '旧判据把 voice_kind 当「克隆已生效」证据是失真的'
        % (vk_clone, ca_false, n_tts))
    chk(vspk_non_null > 0,
        'labels_did_reach_worker_via_late_binding',
        'voice_spk 非空 %d/%d ⇒ 标签经 spk_update/seg 晚到路径进了 worker，'
        '不能简单归因为「spk 完全没传」；clone_active 恒 False 的确切根因'
        '属「无法判定」，必须靠 APP-079(a) 的 TTS 入口运行期日志才能定案'
        % (vspk_non_null, n_tts))
    chk(seg_conf_vals and min(seg_conf_vals) < 0.5,
        'seg_conf_below_registration_gate',
        'seg.jsonl 最小 spk_conf=%s < REG_CONF_MIN=0.5 ⇒ '
        'reviewer 指出的 S2 seg1 conf=0.129 本应被登记门槛拒绝'
        % (min(seg_conf_vals) if seg_conf_vals else None,))
    chk(bool(seg_conf_vals), 'seg_has_conf_but_submit_does_not',
        'seg.jsonl 有 %d 个非空 spk_conf（最小 %s）⇒ 断链发生在 seg→submit 传递'
        % (len(seg_conf_vals), min(seg_conf_vals) if seg_conf_vals else None))
    chk("if spk is not None:" in svc_text and "cmd['spk_conf'] = spk_conf" in svc_text,
        'tts_service_submit_drops_null_spk',
        'submit() 只在 spk 非空时写 spk/spk_conf ⇒ spk=None 时命令体无说话人字段')
    chk('REG_CONF_MIN = ' in spkvoice_text and 'float(conf) < REG_CONF_MIN' in spkvoice_text,
        'registration_conf_gate_exists',
        'speaker_voice.py 有 REG_CONF_MIN 门槛 ⇒ conf=None 不可能过闸')
    chk(vc.get('false', -1) == 19 and vc.get('true', -1) == 21
        and vc.get('none', -1) == 6 and gate.get('applicable') == 44,
        'f0_gate_not_passed',
        'gate.json verdict_counts=%s applicable=%s' % (vc, gate.get('applicable')))
    return dict(n_pass=sum(1 for c in checks if c['ok']),
                n_fail=sum(1 for c in checks if not c['ok']),
                checks=checks,
                measured=dict(n_submit=n_submit, n_tts=n_tts,
                              spk_null=spk_null, spk_non_null=n_submit - spk_null,
                              spk_conf_null=conf_null, clone_active_false=ca_false,
                              voice_kind_clone=vk_clone, voice_spk_null=vspk_null,
                              voice_spk_non_null=vspk_non_null,
                              seg_conf_non_null=len(seg_conf_vals),
                              seg_conf_min=min(seg_conf_vals) if seg_conf_vals else None,
                              f0_verdict_counts=vc),
                reviewer_claim=dict(
                    clone_active_all_false_consistent=(ca_false == n_tts),
                    submit_spk_all_null_consistent=(spk_null == n_submit),
                    note=('本机 submit.jsonl 有 %d/%d 行 spk 非空（spk_conf 全 null）；'
                          '与 reviewer「spk/spk_conf 全为 null」的措辞存在口径差异，'
                          '可能与 _app309 补齐的提交映射版本有关 ⇒ 记「需 reviewer 确认」，'
                          '不判 reviewer 错、也不自行改写结论'
                          % (n_submit - spk_null, n_submit))))


def main():
    files = {k: os.path.join(R2, k) for k in
             ('submit.jsonl', 'seg.jsonl', 'tts.jsonl', 'gate.json', 'manifest.json')}
    submit, seg, tts = (jsonl(files[k]) for k in ('submit.jsonl', 'seg.jsonl', 'tts.jsonl'))
    gate = json.load(open(files['gate.json'], encoding='utf-8'))
    svc_text = open(os.path.join(ROOT, 'live_caption', 'tts_service.py'),
                    encoding='utf-8').read()
    spkvoice_text = open(os.path.join(ROOT, 'live_caption', 'speaker_voice.py'),
                         encoding='utf-8').read()
    main_r = analyse(submit, tts, seg, gate, svc_text, spkvoice_text)

    # 🔴 反证组：用**同一判据函数**注入缺陷，必须全被识破（判据非恒真）。
    counter = []

    def cp(name, mutated, expect):
        r = analyse(*mutated)
        identified = (r['n_fail'] > 0)
        counter.append(dict(name=name, identified=identified,
                            expect=expect, n_pass=r['n_pass'], n_fail=r['n_fail'],
                            failed_checks=[c['name'] for c in r['checks'] if not c['ok']]))

    # E1：把 clone_active 全改成 True（冒充「克隆已生效」）⇒ 应被识破
    t1 = [dict(r, clone_active=True, voice_spk='S1') for r in tts]
    cp('E1_fake_clone_active_true', (submit, t1, seg, gate, svc_text, spkvoice_text),
       'clone_active_all_false / voice_kind_evidence')
    # E2：submit 的 spk_conf 全填 0.9（冒充标签齐备）⇒ 应被识破
    s2 = [dict(r, spk_conf=0.9) for r in submit]
    cp('E2_fake_spk_conf', (s2, tts, seg, gate, svc_text, spkvoice_text),
       'submit_spk_conf_all_null')
    # E3：gate.json 计数改成全通过 ⇒ 应被识破
    g3 = dict(gate, verdict_counts={'true': 44, 'false': 0, 'none': 2})
    cp('E3_fake_f0_gate_pass', (submit, tts, seg, g3, svc_text, spkvoice_text),
       'f0_gate_not_passed')
    # E4：删掉 submit() 的「只在非空时写 spk」分支 ⇒ 应被识破
    svc4 = svc_text.replace('if spk is not None:', 'if False:', 1)
    cp('E4_remove_submit_anchor', (submit, tts, seg, gate, svc4, spkvoice_text),
       'tts_service_submit_drops_null_spk')

    n_identified = sum(1 for c in counter if c['identified'])
    verdict = ('PASS' if main_r['n_fail'] == 0
               and n_identified == len(counter) else 'FAIL')
    out = dict(tool='_app314_app079_static_triage', app='APP-079',
               scope='static_only_no_device_no_minimax',
               verdict=verdict, n_pass=main_r['n_pass'], n_fail=main_r['n_fail'],
               counterproof_identified='%d/%d' % (n_identified, len(counter)),
               checks=main_r['checks'], measured=main_r['measured'],
               reviewer_claim=main_r['reviewer_claim'], counterproof=counter,
               conclusion=('APP-079 本条按 APP-080 用户决定转入后续版本（本条需等 reviewer 复核）；'
                           '本轮只交付 (a)/2 的静态归因：submit.spk_conf 82/82 全 null ⇒ '
                           'REG_CONF_MIN 门槛在该链路拿不到输入；submit.spk 73/82 为 null ⇒ '
                           'submit() 命令体不带说话人字段；但 tts.jsonl 的 voice_spk 43/46 非空 ⇒ '
                           '标签其实经晚到绑定进了 worker，不能简单归因为「完全没传」；'
                           "voice_kind='clone' 44/46 与 clone_active=False 46/46 自相矛盾 ⇒ "
                           '旧判据失真，clone_active 恒 False 的确切根因记为「无法判定」，'
                           '须靠 (a) 的 TTS 入口运行期日志定案。'
                           '(b)(c)(d) 需设备级作业，按「v2.3 发布前不再为克隆占用设备」不做。'),
               evidence_files=[stat_of(p) for p in list(files.values()) + [
                   os.path.join(ROOT, 'live_caption', 'tts_service.py'),
                   os.path.join(ROOT, 'live_caption', 'speaker_voice.py')]])
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=verdict, n_pass=main_r['n_pass'],
                          n_fail=main_r['n_fail'],
                          counterproof_identified=out['counterproof_identified'],
                          measured=main_r['measured']), ensure_ascii=False, indent=2))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
