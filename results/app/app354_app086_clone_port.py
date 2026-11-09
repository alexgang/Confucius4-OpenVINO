# -*- coding: utf-8 -*-
"""app354_app086_clone_port.py — APP-086(2)(3) EXT -> App dev 树定点移植。

只读参考（绝不改 EXT 仓库、不切分支）：
  git -C <live_dub_ext> show claude-dev:ext/clone_voice.py
  git -C <live_dub_ext> show claude-dev:ext/tts_cuda_sidecar_ext.py

三处改动，全部「精确字符串替换 + 唯一命中断言 + ast.parse」：
  1. 新建 live_caption/clone_voice.py —— EXT CloneVoices 的 App 适配版，
     完整实现 APP-086② a–f（无标签不沿用上一句音色 / 临时标签 / 先出临时音色 /
     整句 ICL 更好参考 / 参考冻结 / 克隆工作移出 ASR 线程）；
  2. live_caption/tts_cuda_sidecar.py —— 生成调用改为 ICL（ref_text +
     xvec_only=not _ref_text），采样 temperature 0.6 / top_k 20（APP-086②(d)）；
  3. live_caption/live_caption_app.py —— CUDA 选项 note 补「需要另装 CUDA 环境」，
     默认仍 NPU、包内仍隐藏（APP-062③ D3 / APP-088②），不动布局。

判据：a–f 六项 + 边车 + GUI 共 8 组，每组都带反证（破坏锚点 ⇒ 判据必须 FAIL）。
绝不原地改客户包（脚本只写 live_caption/ 与 results/app/，并复核 v2.4 包内 3 文件 SHA）。
纯 CPU 静态，不加载模型、不占设备、不建 MACHINE_LOCK。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
EXT = r'C:\Users\Trekker-PTL\live_dub_ext'
LC = os.path.join(REPO, 'live_caption')
RA = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RA, 'app354_app086_clone_port_evidence.json')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
PKG_FILES = [r'app\live_caption_app.py', r'app\speaker_voice.py', r'app\tts_cuda_sidecar.py']


def sha(b):
    return hashlib.sha256(b).hexdigest()


def ext_show(rel):
    r = subprocess.run(['git', '-C', EXT, 'show', 'claude-dev:' + rel], capture_output=True)
    assert r.returncode == 0, 'git show failed: %s %s' % (rel, r.stderr[:200])
    return r.stdout.decode('utf-8')


def pkg_snapshot():
    out = {}
    for rel in PKG_FILES:
        p = os.path.join(PKG, rel)
        out[rel] = sha(open(p, 'rb').read()) if os.path.isfile(p) else None
    return out


def read_src(path):
    """MEMORY 九：core.autocrlf=true ⇒ 读入归一化为 LF 做匹配，写回还原原行尾。"""
    raw = open(path, 'rb').read()
    eol = '\r\n' if b'\r\n' in raw else '\n'
    return raw.decode('utf-8').replace('\r\n', '\n'), eol


def to_bytes(text, eol):
    return (text if eol == '\n' else text.replace('\n', eol)).encode('utf-8')


def main():
    checks = []

    def ck(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)[:260]))
        assert ok, 'CHECK FAILED: %s %s' % (name, detail)

    pkg_before = pkg_snapshot()

    # ── 1. clone_voice.py（a–f）─────────────────────────────────
    src = ext_show('ext/clone_voice.py')
    old_imp = ('    def __init__(self, on_log=print):\n'
               '        from .engine_runtime import _ensure_app_on_path\n'
               '        _ensure_app_on_path()\n'
               '        import speaker_tracker\n')
    new_imp = ('    def __init__(self, on_log=print):\n'
               '        # APP-086(2): App dev 树里 speaker_tracker / speaker_voice 与本模块同目录，\n'
               '        # 不需要 EXT 的 engine_runtime 路径引导（EXT 源码只读参考，未改）。\n'
               '        import sys as _sys\n'
               '        _here = os.path.dirname(os.path.abspath(__file__))\n'
               '        if _here not in _sys.path:\n'
               '            _sys.path.insert(0, _here)\n'
               '        import speaker_tracker\n')
    old_dir = ('        self.dir = os.path.join(os.environ.get("LOCALAPPDATA", "."),\n'
               '                                "LiveDubEXT", "clone_voices")\n')
    new_dir = ('        # APP-086(4): 克隆音色一律不进客户包 ⇒ 只落开发机用户目录（包外）。\n'
               '        self.dir = os.path.join(os.environ.get("LIVECAP_CLONE_VOICES_DIR")\n'
               '                                or os.environ.get("LOCALAPPDATA", "."),\n'
               '                                "Confucius4LiveCaption", "clone_voices")\n')
    old_doc = '"""EXT 克隆说话人音色（reviewer 2026-11-08，用户要求接入）。\n'
    new_doc = ('"""APP-086(2)：克隆说话人音色编排层（由 live_dub_ext claude-dev:ext/clone_voice.py 移植）。\n\n'
               '移植口径：a 无标签不沿用上一句音色 / b 临时标签 / c 先出临时音色 /\n'
               'd 整句 clean + ASR 文本走 ICL / e 参考冻结（最多一次升级）/ f 克隆工作移出 ASR 线程。\n'
               '只读参考 EXT，不改 EXT 源码；App 适配仅 3 处：模块路径、音色落盘目录、本说明。\n')
    ck('ext_imp_anchor_unique', src.count(old_imp) == 1, src.count(old_imp))
    ck('ext_dir_anchor_unique', src.count(old_dir) == 1, src.count(old_dir))
    ck('ext_doc_anchor_unique', src.count(old_doc) == 1, src.count(old_doc))
    port = (src.replace(old_imp, new_imp, 1)
               .replace(old_dir, new_dir, 1)
               .replace(old_doc, new_doc, 1))
    ast.parse(port, filename='clone_voice.py')
    ck('clone_voice_ast_parse', True)
    ck('clone_voice_no_ext_relative_import', 'from .engine_runtime' not in port)
    ck('clone_voice_voices_outside_pkg', 'Confucius4LiveCaption", "clone_voices' in port)

    # ── 2. 边车 ICL 补丁 ───────────────────────────────────────
    sidecar_p = os.path.join(LC, 'tts_cuda_sidecar.py')
    s0, eol_s = read_src(sidecar_p)
    old_gen = ('            for chunk, sr, timing in model.generate_voice_clone_streaming(\n'
               '                    text=text, language=_lang(req.get(\'language\')),\n'
               '                    ref_audio=ref, xvec_only=True,\n'
               '                    max_new_tokens=mnt,\n'
               '                    chunk_size=int(req.get(\'chunk_size\') or 8)):\n')
    new_gen = ('''            # 🔴 APP-086②(d)：整句干净参考 + 对应 ASR 文本（<ref>.txt）⇒ CUDA 路径走 ICL 克隆
            #   （ref_text / xvec_only=False）；参考冻结见 clone_voice._register_sentences。
            #   采样参数按 APP-086②(d) 定为 temperature 0.6 / top_k 20，
            #   可用 LIVECAP_TTS_TEMPERATURE / LIVECAP_TTS_TOP_K 覆盖（本地开发树专用）。
            #   只读参考：live_dub_ext claude-dev:ext/tts_cuda_sidecar_ext.py（不改 EXT 源码）。
            _ref_text = ''
            try:
                if ref and os.path.isfile(ref + '.txt'):
                    with open(ref + '.txt', encoding='utf-8') as _f:
                        _ref_text = _f.read().strip()
            except Exception:
                _ref_text = ''
            _gen_kw = dict(text=text, language=_lang(req.get('language')),
                           ref_audio=ref, xvec_only=not _ref_text,
                           max_new_tokens=mnt,
                           temperature=float(os.environ.get('LIVECAP_TTS_TEMPERATURE', '0.6')),
                           top_k=int(os.environ.get('LIVECAP_TTS_TOP_K', '20')),
                           chunk_size=int(req.get('chunk_size') or 8))
            if _ref_text:
                _gen_kw['ref_text'] = _ref_text
            for chunk, sr, timing in model.generate_voice_clone_streaming(**_gen_kw):
''')
    ck('sidecar_gen_anchor_unique', s0.count(old_gen) == 1, s0.count(old_gen))
    ck('sidecar_imports_os', bool(ast.parse(s0).body and
       any(isinstance(n, ast.Import) and any(a.name == 'os' for a in n.names)
           for n in ast.parse(s0).body)))
    s1 = s0.replace(old_gen, new_gen, 1)
    ast.parse(s1, filename='tts_cuda_sidecar.py')
    ck('sidecar_ast_parse_after', True)

    # ── 3. GUI 文案（默认 NPU / 包内隐藏均不动）─────────────────
    app_p = os.path.join(LC, 'live_caption_app.py')
    a0, eol_a = read_src(app_p)
    old_note = "                  '⚠️ 走独立 venv（torch 不进客户包），首次加载 ~27 s'\n"
    new_note = ("                  '⚠️ 需要另装 CUDA 环境（独立 venv，torch 不进客户包），'\n"
                "                  '首次加载 ~27 s'\n")
    ck('gui_note_anchor_unique', a0.count(old_note) == 1, a0.count(old_note))
    a1 = a0.replace(old_note, new_note, 1)
    ast.parse(a1, filename='live_caption_app.py')
    ck('gui_ast_parse_after', True)

    # ── 判据：8 组，每组带反证（破坏锚点 ⇒ 判据必须 FAIL）────────
    CRITERIA = [
        ('a_no_inherit_previous_voice', ['min_sim=0.25', 'def voice_for(', '_nearest('], 'min_sim=0.25'),
        ('b_provisional_label', ['min_sim=0.4', '"provisional"', 'note_final(seg, _p'], 'min_sim=0.4'),
        ('c_interim_voice', ['REF_FIRST_S = 3.0', 'def _register_interim', 'registration_ticket('], 'REF_FIRST_S = 3.0'),
        ('d_icl_reference', ['cover < 0.7', '1.5 <= dur <= 12.0', 'ICL', 'def _candidate'], 'cover < 0.7'),
        ('e_freeze_reference', ['REF_UPGRADE_S = 8.0', '_upgraded'], 'REF_UPGRADE_S = 8.0'),
        ('f_off_asr_thread', ['threading.Thread(target=self._worker', 'self._q.put(', 'def _worker('],
         'threading.Thread(target=self._worker'),
        ('sidecar_icl', ['xvec_only=not _ref_text', "_gen_kw['ref_text']", "'0.6'", "'20'"],
         'xvec_only=not _ref_text'),
        ('gui_cuda_option', ['if not _in_customer_package():', '需要另装 CUDA 环境', "or 'NPU'"],
         '需要另装 CUDA 环境'),
    ]

    def evaluate(text, anchors):
        return all(x in text for x in anchors), [x for x in anchors if x not in text]

    corpus = {'a_no_inherit_previous_voice': port, 'b_provisional_label': port,
              'c_interim_voice': port, 'd_icl_reference': port,
              'e_freeze_reference': port, 'f_off_asr_thread': port,
              'sidecar_icl': s1, 'gui_cuda_option': a1}
    crit_rows = []
    for name, anchors, break_token in CRITERIA:
        body = corpus[name]
        ok, missing = evaluate(body, anchors)
        broken = body.replace(break_token, 'BROKEN_BY_COUNTERPROOF', 1)
        b_ok, _ = evaluate(broken, anchors)
        ck('criterion_' + name + '_pass', ok, 'missing=%s' % missing)
        ck('counterproof_' + name + '_detects', not b_ok,
           'break_token=%s broken_still_pass=%s' % (break_token, b_ok))
        crit_rows.append(dict(name=name, anchors=anchors, pass_on_real=ok,
                              break_token=break_token, fail_on_broken=not b_ok,
                              verdict='PASS' if (ok and not b_ok) else 'FAIL'))

    # ── 写前自检：客户包零写入 + 三处源码只动上述锚点 ──────────
    ck('package_files_exist_all', all(v is not None for v in pkg_before.values()),
       json.dumps(pkg_before, ensure_ascii=False)[:200])
    n_pass_pre = sum(1 for c in checks if c['ok'])
    ck('all_pre_write_checks_pass', n_pass_pre == len(checks), '%d/%d' % (n_pass_pre, len(checks)))

    # ── 落盘（原子替换，先临时文件）─────────────────────────────
    written = []
    for path, text, eol in ((os.path.join(LC, 'clone_voice.py'), port, '\n'),
                            (sidecar_p, s1, eol_s), (app_p, a1, eol_a)):
        data = to_bytes(text, eol)
        tmp = path + '.tmp_app354'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
        got = open(path, 'rb').read()
        ck('disk_matches_' + os.path.basename(path), got == data)
        written.append(dict(path=os.path.relpath(path, REPO).replace('\\', '/'),
                            bytes=len(data), sha256=sha(data),
                            eol='CRLF' if eol == '\r\n' else 'LF'))
    pkg_after = pkg_snapshot()
    ck('v24_package_untouched', pkg_before == pkg_after,
       json.dumps(pkg_after, ensure_ascii=False)[:200])

    ev = dict(
        tool='app354_app086_clone_port',
        ext_ref=dict(repo=EXT, branch='claude-dev',
                     files=['ext/clone_voice.py', 'ext/tts_cuda_sidecar_ext.py'],
                     read_only=True, branch_switched=False),
        app086_mapping=dict(
            a='无标签不沿用上一句音色：voice_for() 用 wespeaker 最近质心 min_sim=0.25，无音色回落预设 A',
            b='定稿即给临时标签：_worker 中 _nearest(min_sim=0.4) + note_final(spk_conf=0.2)，旁路标签覆盖',
            c='先出临时音色：_register_interim 用旁路 clean ranges + registration_ticket（App 闸门 2.5 s）',
            d='更好参考：_candidate 整句 clean（conf>=0.5 / cover>=0.7 / 1.5-12 s）+ ASR 文本；边车 ICL',
            e='参考冻结：REF_FIRST_S=3.0 首次、REF_UPGRADE_S=8.0 最多升级一次、之后不改',
            f='克隆工作全部在 clone-voices 线程（_q 队列），ASR 定稿只入队'),
        criteria=crit_rows,
        n_criteria=len(crit_rows),
        n_criteria_pass=sum(1 for r in crit_rows if r['verdict'] == 'PASS'),
        files_written=written,
        package_v24_before=pkg_before, package_v24_after=pkg_after,
        package_untouched=(pkg_before == pkg_after),
        checks=checks,
        n_pass=sum(1 for c in checks if c['ok']),
        n_fail=sum(1 for c in checks if not c['ok']),
        verdict='PASS' if all(c['ok'] for c in checks) else 'FAIL',
        limitation=('本脚本只落盘 dev 树代码资产与静态判据；APP-086② 要求的'
                    '「带真值多人对话改前/改后 + NPU/CUDA 计时数字 + wav 落盘 shared/app_listen」'
                    '属设备作业，本轮未执行，须持 MACHINE_LOCK 另起后台会话。'),
    )
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict=ev['verdict'], n_pass=ev['n_pass'], n_fail=ev['n_fail'],
                          criteria='%d/%d' % (ev['n_criteria_pass'], ev['n_criteria']),
                          files=[(w['path'], w['bytes']) for w in written],
                          package_untouched=ev['package_untouched']), ensure_ascii=False))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
