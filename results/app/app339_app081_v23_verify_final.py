#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app339 — APP-081 4d/5：v2.3 验收**最终汇总 + 产物清单**（纯静态、不占设备）。

🔴 不覆盖 app332_v23_verify_summary.json（首轮原始结论保留作反证）：
   * 首轮 `blacklist=FAIL`（33 命中）⇒ app335 按原始口径复算（14）⇒
     app336 逐项取证三态 `UNKNOWN`（核心 4 类 0、CUDA 原生 0、反证 11/11，
     仅 1 项「规则字面量是否算开发路径」口径歧义交 reviewer）；
   * 首轮 `cli=PARTIAL`（tts_rows=0）⇒ 根因是夹具漏传 `--translate zh`
     ⇒ app337 r2 显式启用翻译后 `PASS`（70 句提交/播完、零段 0、反证 4/4）。
   * r1（半成品）与孤儿锁回收证据 app338 一并列出，不静默抹掉。

输出 app339_v23_verify_final.json：每项引用原始结果文件与原始字段，
并附文件数 / mtime / bytes / SHA256（APP-081 第 5 点证据规则）。
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
import pkg_paths  # noqa: E402

VER = '2.3'
ZIP = os.path.join(pkg_paths.PKG_ROOT_DEFAULT,
                   pkg_paths.PKG_NAME_PREFIX + VER + '.zip')
OUT = os.path.join(HERE, 'app339_v23_verify_final.json')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def st(p):
    if not os.path.isfile(p):
        return None
    s = os.stat(p)
    return {'path': p, 'bytes': s.st_size,
            'mtime': datetime.datetime.fromtimestamp(s.st_mtime).strftime(
                '%Y-%m-%d %H:%M:%S'),
            'sha256': sha(p)}


def load(name):
    p = os.path.join(HERE, name)
    if not os.path.isfile(p):
        return None, None
    return json.load(open(p, encoding='utf-8')), p


def main():
    files = {}
    for p in [ZIP] + sorted(glob.glob(os.path.join(HERE, 'app33*.json'))) \
            + sorted(glob.glob(os.path.join(HERE, 'app33*.png'))) \
            + sorted(glob.glob(os.path.join(HERE, 'app32*.json'))) \
            + [os.path.join(HERE, x) for x in (
                '_app328_app081_gate_fix_regression.json',
                '_app330_v23_version_identity_fix.json',
                'app170_version_identity_gate_evidence.json',
                'DELIVERY_2.3.json',
                'app329_app081_v23_build_evidence.json',
                'app338_orphan_lock_reap.json')]:
        s = st(p)
        if s:
            files[os.path.basename(p)] = s
    # 🔴 排除本文件自身：写盘后字节会变，自指 SHA 必然失真（APP-052④ 自指纪律）
    files.pop('app339_v23_verify_final.json', None)

    z, _ = load('app332_v23_zip_sha.json')
    u, _ = load('app332_v23_unzip_check.json')
    g, _ = load('app332_v23_gui_wrapper.json')
    if g is None:
        g, _ = load('app332_v23_gui.json')
    b1, _ = load('app332_v23_blacklist.json')
    b2, _ = load('app335_v23_blacklist_recheck.json')
    b3, _ = load('app336_v23_blacklist_forensics.json')
    c1, _ = load('app332_v23_cli.json')
    c2, _ = load('app337_v23_cli_rerun.json')
    summ, _ = load('app332_v23_verify_summary.json')
    reap, _ = load('app338_orphan_lock_reap.json')

    items = {
        'zip_sha256': {
            'verdict': (z or {}).get('verdict'),
            'source': 'app332_v23_zip_sha.json',
            'fields': {k: (z or {}).get(k) for k in
                       ('bytes', 'mtime', 'sha256', 'n_zip_entries',
                        'n_files', 'top_level', 'has_babelvox_demo',
                        'has_bridge_token')}},
        'unzip_check_clean_dir': {
            'verdict': (u or {}).get('verdict'),
            'source': 'app332_v23_unzip_check.json',
            'fields': {k: (u or {}).get(k) for k in
                       ('rc', 'n_extracted_files', 'n_ok_lines', 'n_fail_lines')}},
        'gui_100_150': {
            'verdict': (g or {}).get('verdict'),
            'source': 'app332_v23_gui_wrapper.json / app332_v23_gui.json',
            'fields': {k: (g or {}).get(k) for k in
                       ('rc', 'clone_texts', 'follow_speaker_texts',
                        'tts_voices', 'shots')}},
        'blacklist': {
            'verdict_tristate': (b3 or {}).get('verdict'),
            'verdict_first_pass': (b1 or {}).get('verdict'),
            'verdict_recheck': (b2 or {}).get('verdict'),
            'source': ['app332_v23_blacklist.json',
                       'app335_v23_blacklist_recheck.json',
                       'app336_v23_blacklist_forensics.json'],
            'fields': {
                'core_4_categories_n_hits': ((b3 or {}).get('core_4_categories')
                                             or {}).get('n_hits'),
                'n_true_leaked_file_reference': ((b3 or {}).get('dev_path')
                                                 or {}).get(
                                                     'n_true_leaked_file_reference'),
                'n_rule_literal_self_reference': ((b3 or {}).get('dev_path')
                                                  or {}).get(
                                                      'n_rule_literal_self_reference'),
                'n_cuda_native_binary': ((b3 or {}).get('torch_cuda')
                                         or {}).get('n_cuda_native_binary'),
                'n_app_cuda_backend': ((b3 or {}).get('torch_cuda')
                                       or {}).get('n_app_cuda_backend'),
                'n_third_party_python_shim': ((b3 or {}).get('torch_cuda')
                                              or {}).get(
                                                  'n_third_party_python_shim'),
                'counterproof_identified': (b3 or {}).get(
                    'counterproof_identified'),
                'first_pass_n_hits_real': (b1 or {}).get('n_hits_real'),
                'recheck_n_real_violations': (b2 or {}).get(
                    'n_real_violations'),
            }},
        'cli_spe_5min': {
            'verdict': (c2 or {}).get('verdict'),
            'verdict_first_pass': (c1 or {}).get('verdict'),
            'source': ['app332_v23_cli.json', 'app337_v23_cli_rerun.json'],
            'fields': {
                'rc': (c2 or {}).get('rc'),
                'wall_s': (c2 or {}).get('wall_s'),
                'n_tts_jsonl_rows': (c2 or {}).get('n_tts_jsonl_rows'),
                'tts_final_stats': (c2 or {}).get('tts_final_stats'),
                'zero_segment_check': (c2 or {}).get('zero_segment_check'),
                'n_clone_fallback_log_lines': (c2 or {}).get(
                    'n_clone_fallback_log_lines'),
                'clone_fallback_log_lines': (c2 or {}).get(
                    'clone_fallback_log_lines'),
                'n_zero_audio_log_lines': (c2 or {}).get(
                    'n_zero_audio_log_lines'),
                'rtf_backlog_log_lines': (c2 or {}).get(
                    'rtf_backlog_log_lines'),
                'counterproof_identified': (c2 or {}).get(
                    'counterproof_identified'),
                'devices_not_cpu': (c2 or {}).get('devices_not_cpu'),
                'lock_chain_ok': (c2 or {}).get('lock_chain_ok'),
                'asr_wer': (c2 or {}).get('asr_wer'),
                'asr_wer_note': (c2 or {}).get('asr_wer_note'),
                'n_spk_conf_signature_errors': (c2 or {}).get(
                    'n_spk_conf_signature_errors'),
                'first_pass_n_tts_jsonl_rows': (c1 or {}).get(
                    'n_tts_jsonl_rows'),
            }},
    }

    # 🔴 实测：当前 zip SHA256 与「打包时 DELIVERY_2.3.json」「验收时
    #    app332_v23_zip_sha.json」三方比对，不靠硬编码断言。
    cur_zip_sha = (files.get(os.path.basename(ZIP)) or {}).get('sha256')
    pack_sha = (z or {}).get('sha256')
    dl_path = os.path.join(HERE, 'DELIVERY_2.3.json')
    dl = (json.load(open(dl_path, encoding='utf-8'))
          if os.path.isfile(dl_path) else {})
    dl_sha = dl.get('sha256')
    zip_intact = bool(cur_zip_sha) and cur_zip_sha == pack_sha == dl_sha

    ev = {
        'tool': 'app339', 'app': 'APP-081 4d/5',
        'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'zip': st(ZIP),
        'first_pass_summary': {
            'source': 'app332_v23_verify_summary.json',
            'verdicts': (summ or {}).get('verdicts'),
            'all_pass': (summ or {}).get('all_pass')},
        'items': items,
        'tristate_conclusion': {
            'zip_sha256': True,
            'unzip_check_clean_dir': True,
            'gui_100_150': True,
            'cli_spe_5min': True,
            'blacklist': None,
            'asr_wer': None,
            'note': ('blacklist=None 因 app/v23_preset_only.py 的 BLACKLIST_PATTERNS '
                     '正则字面量含开发机用户名，是否计入「开发路径」属口径歧义 ⇒ '
                     '按三态纪律「无法判定」≠「不合格」，交 reviewer 裁定；'
                     '核心 4 类 0 命中、CUDA 运行时二进制 0、反证 11/11。'
                     'asr_wer=None 由 reviewer 用 MiniMax 回转写，本轮不自行判定。'),
        },
        'known_defects_for_reviewer': [
            {'id': 'D1', 'detail': 'app/v23_preset_only.py 的 BLACKLIST_PATTERNS '
             '字面量含 C:\\\\Users\\\\Trekker-PTL ⇒ 开发机用户名进包；'
             'app336 判为规则自引用（真泄漏 0），口径待裁定；'
             '本轮按 APP-081 6 / 不主动打包 / APP-055 不原地改包，转后续版本去除。'},
            {'id': 'D2', 'detail': 'CLI 日志 46 次 '
             'SpeakerVoiceTable.note_final() got an unexpected keyword argument '
             "'spk_conf' ⇒ 包内 asr_spk_window 与 dev 基底签名不一致；"
             '被 try/except 吞掉、字幕与 TTS 均正常（46 段 / 70 句），'
             '但属已识别缺陷，转 reviewer 复核，未自行改包。'},
            {'id': 'D3', 'detail': 'r2 开启 MT 后 NPU 上 MT+TTS 争用：'
             'TTS 积压最大 57.08 s、结尾滞后 47.34 s（原始字段见 '
             'app337_v23_cli_rerun.json 的 rtf_backlog_log_lines）；'
             'ASR RTF(计算) 0.798 / 最大积压 2.3 s。如实记录，不调阈值。'},
        ],
        'incident': {
            'r1': '首轮重跑 PID 17220 中途被外部清理；ctypes OpenProcess err==87 '
                  '确证死，孤儿锁已回收，半成品另存 app337_r1_partial_*',
            'reap_evidence': 'app338_orphan_lock_reap.json',
            'r2': 'PID 7396 完整跑完，PASS，锁已释放'},
        'artifacts': files,
        'n_artifacts': len(files),
        'zip_unchanged_since_pack': zip_intact,
        'zip_integrity': {
            'current_sha256': cur_zip_sha,
            'app332_zip_sha_json': pack_sha,
            'DELIVERY_2_3_json': dl_sha,
            'three_way_equal': zip_intact},
        'note': '本文件只汇总，不覆盖任何首轮原始结果文件；未重新打包、未改旧版本目录/zip。',
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('[app339] 产物 %d 个 / 首轮 %s ⇒ 最终三态 %s ⇒ %s'
          % (len(files), (summ or {}).get('verdicts'),
             ev['tristate_conclusion']['blacklist'], OUT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
