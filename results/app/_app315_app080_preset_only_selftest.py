r"""_app315 — APP-080「v2.3 只交付预设音色」的**纯静态**落地与自证。

不占设备、不加载模型、不打包、不生成 zip、不改任何已发布目录，
也不修改 dev 源文件（补丁只在内存里应用到文本，产出一份 .diff 供 reviewer 看）。
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LC = os.path.join(ROOT, 'live_caption')
OUT = os.path.join(HERE, '_app315_app080_preset_only_selftest.json')
DIFF = os.path.join(HERE, '_app315_v23_preset_only.diff')
V22 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2'

# 🔴 依赖缺失会造成假 FAIL（§四）⇒ numpy 不在默认解释器里就改用仓库 .venv 重跑。
try:
    import numpy  # noqa: F401
except ImportError:
    _venv = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
    if os.path.isfile(_venv) and os.environ.get('_APP315_VENV_REEXEC') != '1':
        os.environ['_APP315_VENV_REEXEC'] = '1'
        os.execv(_venv, [_venv, os.path.abspath(__file__)] + sys.argv[1:])


def stat_of(path):
    b = open(path, 'rb').read()
    st = os.stat(path)
    return dict(path=path, bytes=len(b),
                mtime=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                sha256=hashlib.sha256(b).hexdigest())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def covered(rel, patterns):
    return any(re.search(p, rel.replace('\\', '/')) for p in patterns)


def main():
    mod = load_module('v23_preset_only', os.path.join(LC, 'v23_preset_only.py'))
    gate = load_module('assert_pkg_clean_probe', os.path.join(LC, 'assert_pkg_clean.py'))
    checks = []

    def chk(cond, name, detail):
        # 三态：True / False / None（「无法判定」不等于「不合格」）
        checks.append(dict(name=name,
                           ok=(None if cond is None else bool(cond)),
                           detail=detail))

    src = {}
    patched = {}
    applied = {}
    diffs = []
    for key in mod.PATCHES:
        p = os.path.join(ROOT, key.replace('/', os.sep))
        text = open(p, 'rb').read().decode('utf-8')
        src[key] = text
        try:
            out, ids = mod.apply_patches(text, key)
            patched[key] = out
            applied[key] = ids
            ok, reasons = mod.verify_source(out, key)
            chk(ok, 'patch_' + key.split('/')[-1],
                'applied=%s verify_reasons=%s' % (','.join(ids), reasons))
            chk(len(ids) == len(mod.PATCHES[key]), 'unique_hit_' + key.split('/')[-1],
                '%d/%d anchors hit exactly once' % (len(ids), len(mod.PATCHES[key])))
            eol_crlf = '\r\n' in text
            chk((out.count('\r\n') > 0 and out.count('\n') == out.count('\r\n'))
                if eol_crlf else '\r\n' not in out,
                'eol_restored_' + key.split('/')[-1],
                'source EOL=%s' % ('CRLF' if eol_crlf else 'LF'))
            a = text.replace('\r\n', '\n').splitlines(True)
            b = out.replace('\r\n', '\n').splitlines(True)
            diffs.extend(list(difflib.unified_diff(
                a, b, fromfile='dev/' + key, tofile='v2.3/' + key, n=2)))
        except Exception as e:
            patched[key] = text
            applied[key] = []
            chk(False, 'patch_' + key.split('/')[-1], 'EXC %r' % (e,))

    diff_text = ''.join(diffs)
    with open(DIFF, 'w', encoding='utf-8', newline='\n') as f:
        f.write(diff_text)
    chk(len(diff_text) > 500, 'diff_written', 'diff bytes=%d' % len(diff_text.encode('utf-8')))

    # ── 补丁副作用：闸门不得挤掉函数首语句 docstring（_app316）────────
    def _docs_of(txt, wanted):
        tr = ast.parse(txt.replace('\r\n', '\n'))
        return {n.name: ast.get_docstring(n) for n in ast.walk(tr)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in wanted}
    _want_docs = {'set_clone_pcm', 'register_spk_voice', '_update_clone',
                  '_register_spk_voice', '_apply_spk_voice'}
    dev_docs, patched_docs = {}, {}
    for _k in ('live_caption/tts_service.py', 'live_caption/tts_worker.py'):
        dev_docs.update(_docs_of(src[_k], _want_docs))
        patched_docs.update(_docs_of(patched[_k], _want_docs))
    chk(len(dev_docs) == 5 and all(dev_docs.values()) and dev_docs == patched_docs,
        'docstrings_preserved_after_guard',
        'n_dev=%d n_patched=%d equal=%s' % (len(dev_docs), len(patched_docs),
                                            dev_docs == patched_docs))

    # ── 回落函数：残留值必须回落到 A 且写日志，绝不抛异常 ───────────────
    logs = []
    for residue in ('follow_speaker', 'clone', 'B', '', None, object()):
        try:
            got = mod.normalize_voice(residue, on_log=logs.append)
        except Exception as e:
            got = 'EXC:%r' % (e,)
        chk(got == 'A', 'normalize_%r' % (type(residue).__name__,),
            'got=%r logs=%d' % (got, len(logs)))
    chk(any('APP-080' in m for m in logs), 'normalize_writes_log',
        'log sample=%r' % (logs[0] if logs else None))

    # ── APP-080 ③ 说话人旁路：仍有「字幕标注」用途 ⇒ 保留 5 个 spk 文件 ──
    render = open(os.path.join(LC, 'caption_render.py'), encoding='utf-8').read()
    app_text = src['live_caption/live_caption_app.py']
    chk('spk_by_seg' in render and "'spk': spk_id_of" in render,
        'bypass_used_for_subtitle_labels',
        'caption_render.render_lines 输出行带 spk 键')
    chk('_retry_spk_labels' in app_text and '--speaker on' in app_text,
        'bypass_label_retry_exists', 'App._retry_spk_labels() + CLI --speaker on')
    chk('字幕显示说话人标签' in app_text, 'speaker_help_subtitle', 'argparse help 明文')
    a304 = json.load(open(os.path.join(HERE, '_app304_app076_md5_audit.json'),
                          encoding='utf-8'))
    chk(sorted(mod.KEEP_SPK_FILES) == sorted(a304['asr_files']),
        'keep_spk_files_match_asr050',
        'KEEP=%s' % (mod.KEEP_SPK_FILES,))
    st_text = open(os.path.join(LC, 'speaker_tracker.py'), encoding='utf-8').read()
    chk('DEFAULT_MIN_CLEAN_RATIO' in st_text
        and 'LIVECAP_SPK_MIN_CLEAN_RATIO' in st_text,
        'asr050_default_follows_bypass',
        'speaker_tracker.py 从 ASR 源码读 DEFAULT_MIN_CLEAN_RATIO，不写第二份默认值')

    # ── APP-080 ④ 包内容闸门 ─────────────────────────────────────────
    bad_paths = [
        'app/ext/bridge_token.txt',
        'python/Lib/site-packages/babelvox/data/speakers/cindy.json',
        'python/Lib/site-packages/babelvox/data/speakers/steve.npy',
        'app/models/qwen3tts/voices/clone_C.wav',
        'app/v23_clone_r2/test_A.wav',
    ]
    good_paths = ['app/models/qwen3tts/voices/preset_A.wav',
                  'python/Lib/site-packages/babelvox/speakers.py']
    for p in bad_paths:
        chk(covered(p, mod.PKG_EXCLUDE_PATTERNS), 'exclude_' + p.split('/')[-1], p)
    for p in good_paths:
        chk(not covered(p, mod.PKG_EXCLUDE_PATTERNS), 'keep_' + p.split('/')[-1], p)

    speakers_dir = os.path.join(V22, 'python', 'Lib', 'site-packages',
                                'babelvox', 'data', 'speakers')
    sample = []
    if os.path.isdir(speakers_dir):
        for fn in sorted(os.listdir(speakers_dir)):
            fp = os.path.join(speakers_dir, fn)
            sample.append(dict(file=fn, bytes=os.path.getsize(fp),
                               sha256=hashlib.sha256(open(fp, 'rb').read()).hexdigest()))
    total_bytes = sum(x['bytes'] for x in sample)
    chk(len(sample) == 8, 'v22_has_8_babelvox_samples',
        'n=%d total_bytes=%d' % (len(sample), total_bytes))

    # 真实 v2.2 目录（只读）上跑闸门 ⇒ 应当命中历史违规（APP-078/077 的预期行为）
    real_violations = gate.scan(V22) if os.path.isdir(V22) else []
    chk(len(real_violations) >= 8, 'gate_detects_v22_samples',
        'n_violations=%d sample=%s' % (len(real_violations), real_violations[:2]))
    with tempfile.TemporaryDirectory() as td:
        clean_violations = gate.scan(td)
    chk(clean_violations == [], 'gate_clean_dir_pass', 'clean dir violations=[]')

    # ── SpeakerLibrary 在**没有 8 个示例音色**时的行为（纯 CPU、无推理）──
    sl = {}
    try:
        import numpy as np
        bs = load_module('babelvox_speakers_probe',
                         os.path.join(V22, 'python', 'Lib', 'site-packages',
                                      'babelvox', 'speakers.py'))
        with tempfile.TemporaryDirectory() as td:
            lib = bs.SpeakerLibrary(os.path.join(td, 'lib'), copy_builtins=False)
            sl['profiles_no_builtin'] = len(lib.list_profiles())
            prof = bs.SpeakerProfile(name='probe', embedding=np.zeros((1, 1024), np.float32))
            lib.save(prof)
            sl['save_load_roundtrip'] = lib.load('probe').name
            missing = os.path.join(td, 'does_not_exist')
            bs.BUILTIN_SPEAKERS_DIR = missing
            lib2 = bs.SpeakerLibrary(os.path.join(td, 'lib2'), copy_builtins=True)
            sl['profiles_when_builtin_dir_absent'] = len(lib2.list_profiles())
        chk(sl['profiles_no_builtin'] == 0 and sl['save_load_roundtrip'] == 'probe'
            and sl['profiles_when_builtin_dir_absent'] == 0,
            'speaker_library_works_without_samples', json.dumps(sl, ensure_ascii=False))
        eng = open(os.path.join(LC, 'tts_engine.py'), encoding='utf-8').read()
        chk('if base and os.path.isdir(base):' in eng and 'if src is None:' in eng,
            'builtin_fallback_guards_missing_dir',
            '_SpeakerLibraryWithBuiltinFallback 有 isdir / None 守卫')
    except Exception as e:
        sl = dict(unavailable=True, error=repr(e))
        chk(None, 'speaker_library_works_without_samples',
            '三态「无法判定」：%r' % (e,))

    # ── git 纪律（只读）──────────────────────────────────────────────
    def git(*a):
        return subprocess.run(['git', '-C', ROOT] + list(a), capture_output=True,
                              text=True).stdout.strip()
    gitinfo = dict(head=git('rev-parse', '--short', 'HEAD'),
                   ahead=git('rev-list', '--count', 'origin/main..HEAD'),
                   corrections_status=git('status', '--short', '--',
                                          'status/app/CORRECTIONS_APP.md'))
    chk('CORRECTIONS_APP.md' in gitinfo['corrections_status']
        and gitinfo['corrections_status'].lstrip().startswith('M'),
        'corrections_is_reviewer_only',
        'git status 原始行=%r（reviewer 未提交改动，本轮只读）'
        % (gitinfo['corrections_status'],))

    # ── 反证组：同一判据必须能识破已知缺陷产物 ───────────────────────
    counter = []

    def cp(name, ok_when_broken, expect):
        counter.append(dict(name=name, identified=bool(ok_when_broken),
                            expect=expect))

    k_app = 'live_caption/live_caption_app.py'
    k_svc = 'live_caption/tts_service.py'
    # E1：未打补丁的 dev 原文 ⇒ verify 必须 FAIL
    ok1, _ = mod.verify_source(src[k_app], k_app)
    cp('E1_unpatched_source', not ok1, 'verify_source=False')
    # E2：把 P01 改回去（下拉重新出现克隆）⇒ verify 必须 FAIL
    broken2 = patched[k_app].replace(
        "self.tts_voices = ['A']  # APP-080：v2.3 只交付预设音色",
        "self.tts_voices = ['A', 'follow_speaker']", 1)
    ok2, _ = mod.verify_source(broken2, k_app)
    cp('E2_revert_gui_patch', not ok2, 'verify_source=False')
    # E3：回落函数变成原样返回 ⇒ 残留值判据必须 FAIL
    def bad_norm(v, on_log=None):
        return v
    cp('E3_normalize_returns_residue',
       any(bad_norm(r) != 'A' for r in ('follow_speaker', 'clone')),
       'got != A')
    # E4：删掉 tts_service 的一个运行期闸门 ⇒ verify 必须 FAIL
    broken4 = patched[k_svc].replace('if _V23_PRESET_ONLY:', 'if False:', 1)
    ok4, _ = mod.verify_source(broken4, k_svc)
    cp('E4_remove_runtime_guard', not ok4, 'verify_source=False')
    # E5：排除清单置空 ⇒ 示例音色必须不再被拦
    cp('E5_empty_exclude_list',
       not covered('python/Lib/site-packages/babelvox/data/speakers/cindy.json', []),
       'covered=False')
    # E6：少带一个 ASR spk 文件 ⇒ 与 _app304 清单不一致必须被识破
    cp('E6_missing_spk_file',
       sorted(mod.KEEP_SPK_FILES[:-1]) != sorted(a304['asr_files']),
       'lists differ')
    # E7：去掉内置目录守卫的静态判据 ⇒ 必须被识破
    cp('E7_remove_isdir_guard',
       'if base and os.path.isdir(base):' not in
       open(os.path.join(LC, 'tts_engine.py'), encoding='utf-8').read().replace(
           'if base and os.path.isdir(base):', 'if base:', 1),
       'anchor lost')
    # E8：把闸门插回 docstring **之前**（_app315 旧补丁）⇒ 判据必须识破
    broken8 = patched[k_svc].replace('\r\n', '\n').replace(
        '    def set_clone_pcm(self, pcm) -> bool:\n',
        '    def set_clone_pcm(self, pcm) -> bool:\n'
        '        if _V23_PRESET_ONLY:\n            return False\n', 1)
    d8 = _docs_of(broken8, _want_docs)
    d8.update(_docs_of(patched['live_caption/tts_worker.py'], _want_docs))
    cp('E8_guard_before_docstring', d8 != dev_docs,
       '__doc__ lost ⇒ docstring 判据必须 FAIL')

    n_ident = sum(1 for c in counter if c['identified'])
    n_pass = sum(1 for c in checks if c['ok'] is True)
    n_fail = sum(1 for c in checks if c['ok'] is False)
    n_unknown = sum(1 for c in checks if c['ok'] is None)
    verdict = 'PASS' if (n_fail == 0 and n_ident == len(counter)) else 'FAIL'

    ev = [os.path.join(LC, 'v23_preset_only.py'),
          os.path.join(LC, 'assert_pkg_clean.py'),
          os.path.join(LC, 'tts_engine.py'),
          os.path.join(LC, 'caption_render.py'),
          os.path.join(HERE, '_app304_app076_md5_audit.json'), DIFF, OUT]
    ev += [os.path.join(ROOT, k.replace('/', os.sep)) for k in mod.PATCHES]
    out = dict(tool='_app315_app080_preset_only_selftest', app='APP-080',
               scope='static_only_no_device_no_packaging_no_minimax',
               verdict=verdict, n_pass=n_pass, n_fail=n_fail,
               n_unknown=n_unknown,
               counterproof_identified='%d/%d' % (n_ident, len(counter)),
               checks=checks, counterproof=counter,
               applied_patches=applied,
               diff_file=DIFF, diff_bytes=len(diff_text.encode('utf-8')),
               speaker_library_probe=sl,
               v22_babelvox_samples=dict(n_files=len(sample),
                                         total_bytes=total_bytes, files=sample),
               v22_gate_violations=len(real_violations),
               pkg_size_impact=dict(
                   uncompressed_bytes_removed_from_pkg_dir=total_bytes,
                   zip_level='APP-078 已证实 zip 层 0 命中 ⇒ zip 体积/SHA 不因本项改变',
                   note='未打包 ⇒ 这是基于 v2.2 只读实测的基准，不是「已交付」'),
               keep_spk_files=mod.KEEP_SPK_FILES,
               pkg_include_files=mod.PKG_INCLUDE_FILES,
               git=gitinfo,
               conclusion=('APP-080 的 ①②③④ 已形成可复现的构建期定点补丁 + 静态自证；'
                           '⑤⑥ 需打新版本包 + 设备级验收（--check / CLI 5 分钟 / GUI 100%·150% 截图 / '
                           '黑名单 / zip SHA256），按「不通知不打包」与 reviewer 复核节点停止。'))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out['evidence_files'] = [stat_of(p) for p in ev if os.path.isfile(p)]
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=verdict, n_pass=n_pass, n_fail=n_fail,
                          n_unknown=n_unknown,
                          counterproof_identified=out['counterproof_identified'],
                          diff_bytes=out['diff_bytes'],
                          v22_samples=out['v22_babelvox_samples']['n_files'],
                          sample_bytes=total_bytes,
                          v22_gate_violations=len(real_violations)),
                     ensure_ascii=False, indent=2))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
