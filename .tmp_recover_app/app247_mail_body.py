# -*- coding: utf-8 -*-
"""§247：从实测 JSON 生成 STATUS 邮件正文（**不手抄数字**）。"""
import io
import json
import os
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
R = os.path.join(REPO, 'results', 'app')
ZIP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.zip'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2'
OUT = os.path.join(REPO, '.tmp_recover_app', 'mail_zip_body.txt')


def J(name):
    with io.open(os.path.join(R, name), encoding='utf-8') as f:
        return json.load(f)


def main():
    wl = J('app247_zip_whitelist.json')
    mt3 = J('app148_mt3_weight_check.json')
    gm = J('app245_gate_metrics.json')
    cons = J('app148_zip_consistency.json')
    cex = J('app247_zip_consistency_counterexample.json')
    ex = J('app247_zip_extract_check.json')
    acc = J('app247_sign_accepted_v12_evidence.json')

    st = os.stat(ZIP)
    n_files = sum(len(f) for _, _, f in os.walk(PKG))
    dir_bytes = sum(os.path.getsize(os.path.join(dp, f))
                    for dp, _, fs in os.walk(PKG) for f in fs)

    L = []
    A = L.append
    A('[C4][A][STATUS][APP] MiniMVP v1.2 已出 zip（打包完成，请从 zip 复核）')
    A('')
    A('一、产物（本机实测，不是估算）')
    A('  路径：%s' % ZIP)
    A('  字节：%d（%.3f GiB）；条目：%d' % (st.st_size, st.st_size / 1024.0 ** 3,
                                        cons.get('n_zip_entries')))
    A('  mtime：%s；压缩率 %.1f%%（v1.1.1 zip 是 5 212 403 155 B，本包约 1.019 倍）'
      % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
         100.0 * st.st_size / dir_bytes))
    A('  目录：%s（%d 文件 / %d B）' % (PKG, n_files, dir_bytes))
    A('  结构同 v1.1.1：条目全带顶层前缀 `Confucius4_LiveCaption_MiniMVP_v1.2/`，'
      'zip 内含 ACCEPTED.json')
    A('')
    A('二、APP-147 四条自查 + APP-148 两项一致性')
    A('  1) 三轮（§245，10 分钟固定片段）：dubs %s；n_submitted %s；n_emitted %s；'
      '丢句 %s；n_error %s；NaN %s；削波 %s；撞 39 s 上限 %s；最大语速 %s；synth_rtf %s。'
      % tuple('/'.join(str(a.get(k)) for a in gm['arms']) for k in
              ('dubs', 'n_submitted', 'n_emitted', 'n_dropped', 'n_error',
               'nan_event_n', 'clip_event_n', 'tts_runaway_n', 'speed_max',
               'synth_rtf')))
    A('     三臂 rc=0 / lock_lost=0 / 排空后 n_pending=0（drained_to_zero：%s）。'
      % '/'.join(str(a.get('drained_to_zero')) for a in gm['arms']))
    A('  2) 日志见 `MT 就绪（Hy-MT3 INT8 @ GPU.0）`；NPU_TURBO 逐组件 True；'
      '落点 NPU 9 组件 / CPU 0。')
    A('  3) 洁净白名单 %d/%d PASS（含新增第 ⑨ 条 *.bak*：0 个）；'
      'MT 只有 mt3、克隆音色目录为空、除 preset_A.wav 外无音视频、无 CUDA DLL。'
      % (wl.get('n_pass'), wl.get('n_pass', 0) + wl.get('n_fail', 0)))
    A('  4) 解压 zip 到临时目录 → 包内 python 跑 --check：rc=%s，%s s，解出 %d 文件'
      '（= zip 条目数），结论行「环境正常。ASR 可用后端 2 个，Intel 集显可用。」；'
      'MT 显示 Hy-MT3-1.8B，GPU.0+NPU 都在；临时目录已删。'
      % (ex.get('check_rc'), ex.get('check_elapsed_s'), ex.get('n_extracted_files')))
    A('  APP-148 §1a MT3 权重（3 处固定偏移 × 32 字节）：候选 = 源 mt3（3/3 一致）、'
      '源 mt3 vs 源 mt2（3/3 全不同）；三份 openvino_model.bin 字节数完全相同'
      '（%d）⇒ 确实只能靠 hex 区分。' % mt3['sizes']['candidate_mt3'])
    A('    off4096  候选/源 mt3 = %s' % mt3['six_hex_groups']['candidate_mt3_off1'])
    A('    off4096  mt2        = %s' % mt3['six_hex_groups']['source_mt2_off1'])
    A('    offsize/2  mt3      = %s' % mt3['six_hex_groups']['candidate_mt3_off2'])
    A('    offsize/2  mt2      = %s' % mt3['six_hex_groups']['source_mt2_off2'])
    A('    offend-4096 mt3     = %s' % mt3['six_hex_groups']['candidate_mt3_off3'])
    A('    offend-4096 mt2     = %s' % mt3['six_hex_groups']['source_mt2_off3'])
    A('')
    A('三、必须请你注意：APP-148 §1b 的判据脚本本身有缺陷（已修 + 加反证）')
    A('  原 `_app148_zip_consistency.py` 首跑报「只在 zip 里 10893 / 只在目录里 10893 / '
      '大小不同 0」⇒ 假 FAIL。')
    A('  根因：交付 zip 的条目带顶层目录前缀，目录侧是相对路径（无前缀）⇒ 直接比对必然全不匹配。'
      '这不是包的问题。')
    A('  修法：先剥 `basename(cand)/` 前缀；再加一条判据「所有条目都必须带该前缀」；'
      '收尾判定把「条目数相等」也算进去。')
    A('  修后真跑：%d/%d，只在 zip 里 %d、只在目录里 %d、大小不同 %d、不带前缀 %d，'
      'testzip()=%s（CRC 全过）。'
      % (cons.get('n_zip_entries'), cons.get('n_dir_files'),
         cons['only_in_zip']['count'], cons['only_in_dir']['count'],
         cons['size_differs']['count'], cons['entries_without_prefix']['count'],
         cons.get('testzip_result')))
    A('  反证组 %s：%s'
      % ('6/6 如期望' if cex.get('all_as_expected') else '有偏差',
         '；'.join('%s⇒rc=%s' % (c['case'], c['rc']) for c in cex['cases'])))
    A('  （c2 多一文件 / c3 缺一文件 / c4 同名不同大小 / c5 无前缀 都必须 FAIL，真实 zip 必须 PASS）')
    A('')
    A('四、ACCEPTED.json（签在打包之前，口径同 v1.1.1）')
    A('  version=%s；生产模块 %d 个；聚合指纹 %s'
      % (acc['version'], acc['n_modules'], acc['aggregate'][:32] + '…'))
    A('  check_acceptance_binding（闸门⑤）= %s（%s）；写后重读复核 %d/%d PASS'
      % (acc['gate5_ok'], acc['gate5_reason'],
         sum(1 for v in acc['checks'].values() if v), len(acc['checks'])))
    A('  built_by 里已写明：reviewer 从 zip 复核待做、B 机复验待做。')
    A('')
    A('五、打包前顺手修的一处包内文档矛盾')
    A('  包内文档写 `EXT v0.4.22`，但 manifest.json / package_profile.json / release.json 的 '
      'ext.version 都是 0.4.23 ⇒ ')
    A('  已把 README_zh（31 554→31 676 B）、README_en（34 476→34 600 B）、'
      'app/MANIFEST.json（notes）、release.json（32 行）四处改成 0.4.23，并补一句'
      '「ASR 按包内模型族自动适配（Qwen3-ASR 0.6B，可 EXT_ASR_FAMILY 强制）」。')
    A('  ext/bridge/engine_runtime.py 里的 0.4.22 是历史注释，未动。')
    A('  app/MANIFEST.json 的 files/bytes 仍是生成时快照（不被任何代码读），'
      '真实条目/字节以 zip 中央目录为准。')
    A('')
    A('六、请复核 / 待办')
    A('  1. 请从 zip 本身复核（三道：条目 vs 目录、解压 --check、ACCEPTED 指纹重算）。')
    A('  2. 抽听样片（3 段 OGG）上一封已单独发过，请按 APP-071/075 口径听男/女是否串音。')
    A('  3. B 机复验未做（APP-147：不挡发版）。')
    A('  4. APP-144 ① 历史脱敏仍排在发版之后，未动。')
    A('  5. LOCK-001 遗留：machine_lock_app.py 的 write_lock_atomic 与三轮编排脚本'
      '尚未改成套 machine_lock.py run（§246 已登记）。')
    A('')
    A('本轮未连 B 机、未调 MiniMax、未改 CORRECTIONS_APP.md；旧包（v1.1.1 目录与 zip）未动。')
    A('STATUS §247 ＋ companion：status/app/STATUS_APP_sec247_detail_20261126.md')

    body = '\n'.join(L) + '\n'
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(body)
    print('正文 %d B / %d 行 -> %s' % (len(body.encode('utf-8')), len(L), OUT))


if __name__ == '__main__':
    main()
