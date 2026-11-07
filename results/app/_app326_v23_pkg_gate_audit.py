r"""_app326 — APP-080 ④⑥ 随包洁净度闸门「覆盖一致性」只读审计（§148）。

背景（历史各轮未验过的判据盲区）：
  §143 落盘两份 dev 资产：
    * live_caption/assert_pkg_clean.py  —— 建包后调用的实际闸门，只查 2 类违规
    * live_caption/v23_preset_only.py   —— 补丁规范，另定义 PKG_EXCLUDE_PATTERNS(5)
                                          与 BLACKLIST_PATTERNS(5)
  APP-080 ④ 明文要求「不含任何克隆音色或测试 wav」＋剔除 babelvox 示例音色
  ＋APP-077 不带 bridge_token.txt ⇒ 两份资产的覆盖范围是否一致，直接决定
  v2.3 打包时闸门是否完备。

纪律：
  * 纯 CPU 静态；不建 MACHINE_LOCK、不加载模型、不跑推理、不调 MiniMax。
  * 被测模块用 ast.parse + exec 载入独立命名空间（不 import、不改 sys.path），
    夹具用 tempfile.TemporaryDirectory 自动清理；dev 源文件与客户包一律只读。
  * 反证组改的都是「被测的那个对象」（正则/模式列表/未打补丁的 dev 原文），
    共用同一判据函数；判据恒真即判 FAIL。
  * 三态：闸门是否需扩展属 reviewer 裁定 ⇒ 记 n_unknown，不写成「已完成」。
"""
from __future__ import annotations

import ast
import collections
import datetime
import glob
import hashlib
import json
import os
import re
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, '_app326_v23_pkg_gate_audit.json')
CORR = os.path.join(ROOT, 'status', 'app', 'CORRECTIONS_APP.md')
STATUS = os.path.join(ROOT, 'status', 'app', 'STATUS_APP.md')
V23 = os.path.join(ROOT, 'live_caption', 'v23_preset_only.py')
GATE = os.path.join(ROOT, 'live_caption', 'assert_pkg_clean.py')
HIST324 = os.path.join(HERE, '_app324_app080_prereq_readonly_audit.json')
HIST322 = os.path.join(HERE, '_app322_v23_pkg_baseline_dryrun.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

DEV_KEYS = {
    'live_caption/live_caption_app.py': os.path.join(ROOT, 'live_caption', 'live_caption_app.py'),
    'live_caption/tts_service.py': os.path.join(ROOT, 'live_caption', 'tts_service.py'),
    'live_caption/tts_worker.py': os.path.join(ROOT, 'live_caption', 'tts_worker.py'),
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def stat_of(path):
    b = open(path, 'rb').read()
    return dict(sha256=sha(b), bytes=len(b))


def load_module(path, name):
    """ast + exec 载入，不 import 被测模块；__name__ 非 __main__ 避免触发 main。"""
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src, filename=path)
    ns = dict(__name__=name, __file__=path, __package__=None)
    exec(compile(tree, path, 'exec'), ns)
    return ns


def docstring_multiset(text):
    """补丁前后所有 def/class/module 首语句字符串常量多重集（§143 _app316 教训）。"""
    tree = ast.parse(text)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body:
                first = node.body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    out.append(first.value.value)
    return collections.Counter(out)


def exclude_hits(rel, patterns):
    """返回命中 PKG_EXCLUDE_PATTERNS 的索引列表（rel 用 / 分隔）。"""
    hits = []
    for i, p in enumerate(patterns):
        if re.search(p, rel):
            hits.append(i)
    return hits


def blacklist_hits(s, patterns):
    return [i for i, p in enumerate(patterns) if re.search(p, s)]


def main():
    checks = []
    counterproof = []

    def chk(cond, name, detail):
        checks.append(dict(name=name, ok=bool(cond), detail=str(detail)[:400]))

    def cp(name, identified, detail):
        counterproof.append(dict(name=name, identified=bool(identified),
                                 detail=str(detail)[:400]))

    # ── 基线 ──────────────────────────────────────────────────────────
    cb = open(CORR, 'rb').read()
    cs = cb.decode('utf-8', errors='replace')
    ids = [int(x) for x in re.findall(r'^## APP-(\d{3})', cs, re.M)]
    corr = dict(sha256=sha(cb), bytes=len(cb),
                mtime=datetime.datetime.fromtimestamp(
                    os.stat(CORR).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                n_headings=len(ids), max_id=max(ids),
                continuous=(ids == list(range(1, max(ids) + 1))))
    chk(corr['n_headings'] == 80 and corr['max_id'] == 80
        and corr['continuous'], 'corrections_baseline_80_continuous', corr)
    st_b = open(STATUS, 'rb').read()
    header = st_b.decode('utf-8').split('\n')[:8]
    last_ack = next((x for x in header if x.startswith('last_ack:')), '')
    chk('APP-080' in last_ack, 'last_ack_is_APP080', last_ack)
    chk(len(st_b) <= 40000 and st_b.count(b'\n') <= 300,
        'status_within_limit', 'bytes=%d lines=%d' % (len(st_b), st_b.count(b'\n')))
    lock_present = os.path.exists(LOCK)
    chk(not lock_present, 'machine_lock_free', 'present=%s' % lock_present)

    # ── 载入两份被测资产（ast + exec，不 import）─────────────────────
    v23 = load_module(V23, '_app326_v23')
    gate = load_module(GATE, '_app326_gate')
    EX = v23['PKG_EXCLUDE_PATTERNS']
    BL = v23['BLACKLIST_PATTERNS']
    chk(len(EX) == 5 and len(BL) == 5, 'patterns_5_and_5',
        'exclude=%d blacklist=%d' % (len(EX), len(BL)))
    try:
        [re.compile(p) for p in EX + BL]
        chk(True, 'all_patterns_compilable', 'n=%d' % (len(EX) + len(BL)))
    except re.error as e:
        chk(False, 'all_patterns_compilable', e)
    chk(v23['PRESET_ONLY'] is True and v23['PRESET_VOICE'] == 'A',
        'preset_constants', 'PRESET_ONLY=%r PRESET_VOICE=%r'
        % (v23['PRESET_ONLY'], v23['PRESET_VOICE']))
    chk(v23['KEEP_SPK_FILES'] == [
        'asr052_speaker_tracker_api.py', 'asr052_spk_runtime.py',
        'asr_thread_defaults.py', 'asr_spk_window.py',
        'asr_runtime_switches.py'], 'keep_spk_files_unchanged',
        v23['KEEP_SPK_FILES'])
    chk(v23['PKG_INCLUDE_FILES'] ==
        ['app/v23_preset_only.py', 'app/assert_pkg_clean.py'],
        'pkg_include_files_unchanged', v23['PKG_INCLUDE_FILES'])

    # ── 夹具：6 类应排除路径 + 4 个干净文件 ──────────────────────────
    VIOL = [
        ('ext/bridge_token.txt', 'APP-077 固定 token'),
        ('python/Lib/site-packages/babelvox/data/speakers/cindy.json', 'APP-078 示例音色'),
        ('python/Lib/site-packages/babelvox/data/speakers/steve.npy', 'APP-078 示例音色'),
        ('app/voices/spk_clone_s1.wav', 'APP-080 ④ 克隆音色'),
        ('app/v23_clone_r2/male_01_seg5.wav', 'APP-080 ④ 克隆产物目录'),
        ('app/audio/foo_test.wav', 'APP-080 ④ 测试 wav'),
    ]
    CLEAN = [
        'app/voices/preset_A.wav',
        'python/Lib/site-packages/babelvox/__init__.py',
        'app/tokenizer/config.json',
        'app/tts_engine.py',
    ]
    with tempfile.TemporaryDirectory(prefix='_app326_gate_') as tmp:
        for rel in [x[0] for x in VIOL] + CLEAN:
            full = os.path.join(tmp, *rel.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as fh:
                fh.write(b'x')
        bad = gate['scan'](tmp)
        bad_rels = [x[0].replace('\\', '/') for x in bad]
        matrix = []
        for rel, why in VIOL:
            matrix.append(dict(path=rel, cls=why,
                               scan_detected=(rel in bad_rels),
                               exclude_hits=exclude_hits(rel, EX)))
        clean_scan = [r for r in bad_rels
                      if any(c in r for c in ('preset_A.wav', '__init__.py',
                                              'config.json', 'tts_engine.py'))]
        clean_ex = {r: exclude_hits(r, EX) for r in CLEAN}

        # 判据：闸门本体只覆盖 2 类（token / babelvox），排除清单覆盖 6 类
        chk(all(m['scan_detected'] for m in matrix[:3]),
            'gate_detects_token_and_babelvox',
            [m['path'] for m in matrix[:3] if m['scan_detected']])
        chk(not any(m['scan_detected'] for m in matrix[3:]),
            'gate_does_not_detect_3_app080_classes',
            [m['cls'] for m in matrix[3:]])
        chk(all(m['exclude_hits'] for m in matrix),
            'exclude_patterns_detect_all_6_classes',
            [len(m['exclude_hits']) for m in matrix])
        chk(not clean_scan and not any(clean_ex.values()),
            'clean_paths_not_flagged',
            dict(clean_scan=clean_scan, clean_ex=clean_ex))
        not_covered = [m['cls'] for m in matrix[3:]]
        chk(len(not_covered) == 3, 'coverage_gap_exactly_3_classes', not_covered)

        # 黑名单正例 / 干净串
        bl_pos = [
            r'C:\Users\Trekker-PTL\confucius4-openvino\hy_bench\run.py',
            'app/results/session_spoken.txt',
            'python/Lib/site-packages/torch/__init__.py',
            'app/cuda_stub.py',
            'reports/hy_bench/log.txt',
        ]
        bl_hits = {s: blacklist_hits(s, BL) for s in bl_pos}
        chk(all(bl_hits.values()), 'blacklist_all_positive_samples_hit', bl_hits)
        chk(all(len(v) >= 1 for v in bl_hits.values())
            and len({i for v in bl_hits.values() for i in v}) == 5,
            'blacklist_5_patterns_all_exercised',
            sorted({i for v in bl_hits.values() for i in v}))
        chk(not any(blacklist_hits(s, BL) for s in
                    ['app/tts_engine.py', 'app/voices/preset_A.wav']),
            'blacklist_no_false_positive_on_clean_strings', 'clean strings')

        # ── 反证组（改的都是被测对象）────────────────────────────────
        orig_token = gate['TOKEN_RE']
        gate['TOKEN_RE'] = re.compile(r'(?!x)x')
        bad2 = [x[0].replace('\\', '/') for x in gate['scan'](tmp)]
        cp('E1_remove_token_regex', 'ext/bridge_token.txt' not in bad2,
           'token_violation_still_reported=%s'
           % ('ext/bridge_token.txt' in bad2))
        gate['TOKEN_RE'] = orig_token

        orig_voice = gate['VOICE_RE']
        gate['VOICE_RE'] = re.compile(r'(?!x)x')
        bad3 = [x[0].replace('\\', '/') for x in gate['scan'](tmp)]
        cp('E2_remove_voice_regex',
           not any('cindy.json' in x or 'steve.npy' in x for x in bad3),
           'demo_voice_still_reported=%s'
           % any('cindy.json' in x or 'steve.npy' in x for x in bad3))
        gate['VOICE_RE'] = orig_voice
        chk(sorted(x[0].replace('\\', '/') for x in gate['scan'](tmp))
            == sorted(bad_rels),
            'gate_restored_after_counterproof', 'scan result identical')

        ex_no_clone = [p for p in EX if 'clone' not in p]
        cp('E3_drop_clone_exclude_pattern',
           not exclude_hits('app/voices/spk_clone_s1.wav', ex_no_clone),
           'clone_wav_still_hit=%s'
           % bool(exclude_hits('app/voices/spk_clone_s1.wav', ex_no_clone)))
        ex_no_token = [p for p in EX if 'bridge_token' not in p]
        cp('E4_drop_token_exclude_pattern',
           not exclude_hits('ext/bridge_token.txt', ex_no_token),
           'token_still_hit=%s'
           % bool(exclude_hits('ext/bridge_token.txt', ex_no_token)))
        cp('E5_empty_blacklist',
           not blacklist_hits(bl_pos[0], []),
           'dev_path_still_hit=%s' % bool(blacklist_hits(bl_pos[0], [])))
        never = [r'(?!x)x']
        cp('E6_never_match_exclude',
           not any(exclude_hits(m['path'], never) for m in matrix),
           'all_violations_missed=%s'
           % (not any(exclude_hits(m['path'], never) for m in matrix)))

    # ── 构建期补丁端到端回归（内存中，不写盘）────────────────────────
    dev_before = {k: stat_of(p) for k, p in DEV_KEYS.items()}
    hist = json.load(open(HIST324, encoding='utf-8'))
    hist_dev = hist['facts']['disk']['dev_sources']
    chk(all(dev_before[k]['sha256'] == hist_dev[k]['sha256']
            and dev_before[k]['bytes'] == hist_dev[k]['bytes']
            for k in DEV_KEYS),
        'dev_sources_match_sec147_recomputed',
        {k: [dev_before[k]['bytes'], hist_dev[k]['bytes']] for k in DEV_KEYS})

    applied_all, patch_rows = [], []
    for k, path in DEV_KEYS.items():
        text = open(path, encoding='utf-8', newline='').read()
        eol_before = '\r\n' if '\r\n' in text else '\n'
        try:
            patched, applied = v23['apply_patches'](text, k)
            ok_patch, err = True, ''
        except Exception as e:
            patched, applied, ok_patch, err = text, [], False, repr(e)
        chk(ok_patch, 'patch_applied_' + k, err or ('n=%d' % len(applied)))
        if not ok_patch:
            continue
        ast.parse(patched.replace('\r\n', '\n'), filename=k)
        ok_verify, reasons = v23['verify_source'](patched, k)
        chk(ok_verify, 'verify_source_' + k, reasons)
        chk(docstring_multiset(text.replace('\r\n', '\n'))
            == docstring_multiset(patched.replace('\r\n', '\n')),
            'docstrings_preserved_' + k, 'multiset equal')
        eol_after = '\r\n' if '\r\n' in patched else '\n'
        chk(eol_before == eol_after, 'eol_restored_' + k,
            'before=%r after=%r' % (eol_before, eol_after))
        # 反证：未打补丁的 dev 原文必须通过不了语义闸门
        ok_bad, why = v23['verify_source'](text, k)
        cp('E7_unpatched_dev_' + k, (not ok_bad) and bool(why),
           'unpatched_ok=%s reasons=%d' % (ok_bad, len(why)))
        applied_all.extend(applied)
        patch_rows.append(dict(file=k, n_anchors=len(applied),
                               verify_source_ok=ok_verify,
                               eol='CRLF' if eol_after == '\r\n' else 'LF'))
    chk(len(applied_all) == 18 and len(set(applied_all)) == 18,
        'total_18_unique_anchors_applied',
        'n=%d unique=%d' % (len(applied_all), len(set(applied_all))))
    dev_after = {k: stat_of(p) for k, p in DEV_KEYS.items()}
    chk(dev_before == dev_after, 'dev_sources_unchanged_on_disk',
        'patch applied in memory only')

    # ── 历史结论字段复核（结果文件 + 原始字段）────────────────────────
    pc = hist['facts']['packaging_chain']
    h322 = json.load(open(HIST322, encoding='utf-8'))
    f322 = h322['facts']
    # 🔴 判据口径：`refs_by_file` 是「每个被扫描文件 → 引用数」的映射
    #    （23 项，值全 0），不是「有引用的文件」清单 ⇒ 必须按值求和，
    #    不能用 len()==0（首跑曾因此假 FAIL，见 §148）。
    chk(pc['total_refs'] == 0
        and sum(pc['refs_by_file'].values()) == 0
        and len(pc['refs_by_file']) == pc['scanned'],
        'sec147_packaging_chain_not_wired',
        'scanned=%s total_refs=%s files=%d sum=%d'
        % (pc['scanned'], pc['total_refs'], len(pc['refs_by_file']),
           sum(pc['refs_by_file'].values())))
    chk(f322['pkg_v22_unique_anchors'] == 14
        and f322['pkg_v22_direct_patch_applicable'] is False,
        'sec146_pkg_v22_baseline_14_of_18',
        'unique=%s applicable=%s total=%s'
        % (f322['pkg_v22_unique_anchors'],
           f322['pkg_v22_direct_patch_applicable'], f322['total_anchors']))
    chk(hist['facts']['bridge']['v22_token_paths']
        and len(hist['facts']['bridge']['v22_token_paths']) >= 1,
        'sec147_bridge_token_still_in_v22',
        hist['facts']['bridge']['v22_token_paths'])
    chk(hist['facts']['seg_w5']['xml_differs'] is True,
        'sec147_d5_xml_differs_unknown', 'xml_differs=true')
    # 独立实算打包链路扫描（排除判据脚本自身）
    build_files = [os.path.join(ROOT, 'pack_v13.py')] + [
        p for p in glob.glob(os.path.join(HERE, '*build*.py'))
        + glob.glob(os.path.join(HERE, '*stage*.py'))
        if '_app32' not in os.path.basename(p)]
    refs = 0
    for p in build_files:
        if not os.path.isfile(p):
            continue
        s = open(p, encoding='utf-8', errors='replace').read()
        refs += s.count('PKG_INCLUDE_FILES') + s.count('assert_pkg_clean') \
            + s.count('v23_preset_only')
    chk(refs == 0, 'independent_packaging_chain_refs_zero',
        'scanned=%d refs=%d' % (len(build_files), refs))

    # ── 停止点（明文锚点存在性）──────────────────────────────────────
    chk('reviewer 复核通过后才通知用户' in cs,
        'app080_stop_at_reviewer', 'anchor present')
    chk('需 Opus 复核' in cs or '需要停下来等' in cs,
        'app075_stop_anchor', 'anchor present')
    chk('v2.3 不得打包' in cs, 'app079_v23_no_pack', 'anchor present')

    n_pass = sum(1 for c in checks if c['ok'])
    n_fail = sum(1 for c in checks if not c['ok'])
    cp_ok = sum(1 for c in counterproof if c['identified'])
    verdict = 'PASS' if (n_fail == 0 and cp_ok == len(counterproof)) else 'FAIL'
    report = dict(
        tool='_app326_v23_pkg_gate_audit',
        generated_at=datetime.datetime.now().isoformat(timespec='seconds'),
        verdict=verdict, n_pass=n_pass, n_fail=n_fail,
        n_unknown=1,
        counterproof_identified='%d/%d' % (cp_ok, len(counterproof)),
        checks=checks, counterproof=counterproof,
        facts=dict(
            corrections=corr,
            last_ack=last_ack,
            status_before=dict(bytes=len(st_b), lines=st_b.count(b'\n'),
                               sha256=sha(st_b)),
            machine_lock_present=lock_present,
            assets=dict(v23_preset_only=stat_of(V23),
                        assert_pkg_clean=stat_of(GATE)),
            pattern_counts=dict(exclude=len(EX), blacklist=len(BL)),
            coverage_matrix=matrix,
            clean_paths_not_flagged=dict(scan=clean_scan, exclude=clean_ex),
            gate_not_covered_classes=not_covered,
            blacklist_positive_hits=bl_hits,
            patches=patch_rows,
            applied_anchor_total=len(applied_all),
            dev_sources=dev_before,
            historical_fields=dict(
                sec147_packaging_chain=dict(scanned=pc['scanned'],
                                            total_refs=pc['total_refs']),
                sec146_pkg_v22_unique_anchors=f322['pkg_v22_unique_anchors'],
                sec146_direct_patch_applicable=f322['pkg_v22_direct_patch_applicable'],
                sec147_bridge_token_paths=hist['facts']['bridge']['v22_token_paths'],
                sec147_seg_w5_xml_differs=hist['facts']['seg_w5']['xml_differs']),
            independent_packaging_scan=dict(scanned=len(build_files), refs=refs),
        ),
        conclusion=(
            'APP-080 ④⑥ 随包闸门覆盖一致性审计：assert_pkg_clean.scan() 实算只检出 '
            'APP-077 固定 token 与 APP-078 babelvox 示例音色 2 类；对「克隆音色 / '
            '克隆产物目录 / 测试 wav」3 类 APP-080 ④ 违规路径 0 检出，而同文件配套的 '
            'PKG_EXCLUDE_PATTERNS 5 条正则对 6 类路径全覆盖 ⇒ 随包闸门覆盖不全 '
            '（NOT_COVERED 3/6）。判据非恒真：9 条反证全被识破。构建期补丁在 dev 基底 '
            '18/18 锚点唯一命中、ast.parse、docstring 多重集不变、行尾还原、磁盘零写入。'),
        unknown=(
            '闸门覆盖缺口是否需在 v2.3 建包前扩展 assert_pkg_clean.py（或改由 '
            'PKG_EXCLUDE_PATTERNS 统一驱动）⇒ 属 APP-080 ⑤ 待办且当前停在 '
            '「reviewer 复核」节点，本轮不自行改代码、不自行裁定。'),
        stop_point=(
            'APP-075 需 Opus 复核 / APP-079 需 reviewer 复核 / APP-080 ⑤⑥ '
            '「reviewer 复核通过后才通知用户」＋用户级「不通知不打包」⇒ '
            '未打包、未打新版本目录与 zip、未改客户安装目录与 .lnk、未占设备。'),
    )
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=verdict, n_pass=n_pass, n_fail=n_fail,
                          counterproof_identified=report['counterproof_identified'],
                          not_covered=not_covered,
                          applied_anchor_total=len(applied_all),
                          independent_packaging_scan=dict(
                              scanned=len(build_files), refs=refs),
                          failing=[c['name'] for c in checks if not c['ok']],
                          cp_failing=[c['name'] for c in counterproof
                                      if not c['identified']]),
                     ensure_ascii=False, indent=2))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
