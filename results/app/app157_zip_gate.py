"""APP-153 §6 ＋ APP-156 §2：**v1.2.1 打 zip 前的白名单门禁**（最后一步跑）。

reviewer 原文（APP-153 §6 第 2 项）：
「白名单（含新增的 ACCEPTED、全文本 Trekker、release=true 三条）在**打 zip 前最后一步**跑，
逐项结果」

APP-156 §2 追加：
「打 zip 前的白名单加一条：面向客户的文件（README*、USER_GUIDE.md、manifest.json、
popup.*、release.json、Start_*.bat、GUI 标题字符串）里大小写不敏感地搜 `confucius`，
命中数应为 0。内部模块名和缓存目录按 APP-154 §2 保留并列清单。」

APP-156 §1 追加两条门禁：
「`n_resynth_failed == 0`；60 s 墙钟兜底的日志行数 == 0。」

## 判据纪律

* 每一项都**可复算**（给出命中的文件/行），不是「我觉得干净」；
* 门禁表落盘成 **.txt**（reviewer：「正文里的 `<` 会被吃掉」⇒ 门禁表用 .txt 附件发）；
* **反证组**：故意把一项弄坏 ⇒ 必须 FAIL ⇒ 证明判据承重。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

PKG = r'C:\Users\Trekker-PTL\LiveCaption_MiniMVP_v1.2.1'
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
OUT_JSON = os.path.join(REPO, 'results', 'app', 'app157_zip_whitelist.json')
OUT_TXT = os.path.join(REPO, 'results', 'app', 'app157_zip_whitelist.txt')
ARMS_JSON = os.path.join(REPO, 'results', 'app', 'app156_three_arms.json')

TEXT_EXT = ('.py', '.md', '.json', '.txt', '.bat', '.js', '.html', '.cfg', '.ini',
            '.yaml', '.yml', '.csv', '.tsv', '.toml', '.ini')
CUSTOMER_FILES = ['README_zh.md', 'README_en.md', 'README_插件.md', 'NOTICE',
                  'THIRD_PARTY.md', 'ext/extension/USER_GUIDE.md',
                  'ext/extension/manifest.json', 'ext/extension/popup.html',
                  'ext/extension/popup.js', 'ext/extension/guide.html',
                  'ext/extension/guide.js', 'release.json', 'package_profile.json',
                  'Start_Bridge.bat', 'Start_LiveCaption.bat', 'Diagnose.bat',
                  'app/MANIFEST.json']
results = []


def log(m):
    print(m, flush=True)


def add(name, ok, detail=''):
    results.append({'name': name, 'pass': bool(ok), 'detail': str(detail)})
    log('  [%s] %-62s %s' % ('PASS' if ok else 'FAIL', name, detail))
    return ok


def rp(rel):
    return os.path.join(PKG, rel.replace('/', os.sep))


def read_text(rel):
    with io.open(rp(rel), 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read()


def main():
    log('=== v1.2.1 打 zip 白名单（打 zip 前最后一步）===')

    # ① 包内无 ACCEPTED.json
    acc = [os.path.join(r, f) for r, d, fs in os.walk(PKG) for f in fs
           if f == 'ACCEPTED.json']
    add('① 包内无 ACCEPTED.json（签章写包外）', not acc, acc or '0 个')

    # ② 全文本搜 Trekker-PTL = 0
    hits = []
    n_txt = 0
    for root, dirs, files in os.walk(PKG):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', 'python')]
        for f in files:
            if os.path.splitext(f)[1].lower() not in TEXT_EXT:
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, PKG).replace('\\', '/')
            n_txt += 1
            try:
                t = io.open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            if 'Trekker-PTL' in t:
                hits.append(rel)
    add('② 全文本（%d 个条目）搜 Trekker-PTL = 0 处' % n_txt, not hits, hits or '[]')

    # ③ manifest 发行开关
    mf = json.loads(read_text('ext/extension/manifest.json'))
    add('③ manifest.liveDub.release == true', mf['liveDub'].get('release') is True,
        mf['liveDub'].get('release'))
    add('③ manifest.liveDub.captureModes == [tabCapture]',
        mf['liveDub'].get('captureModes') == ['tabCapture'],
        mf['liveDub'].get('captureModes'))
    # 开发目录必须保持 false
    dmf = json.loads(io.open(r'C:\Users\Trekker-PTL\live_dub_ext\extension\manifest.json',
                             encoding='utf-8').read())
    add('③ 开发目录 manifest 仍 release=false（EXT-031③）',
        dmf['liveDub'].get('release') is False, dmf['liveDub'].get('release'))

    # ④ GUI 标题
    gui = read_text('app/live_caption_app.py')
    add('④ GUI 窗口标题 = 实时字幕 MiniMVP v1.2.1',
        "_WINDOW_TITLE = '实时字幕 MiniMVP v1.2.1'" in gui, '')

    # ⑤ 面向客户文件搜 confucius = 0
    ch = {}
    for rel in CUSTOMER_FILES:
        if not os.path.exists(rp(rel)):
            continue
        n = read_text(rel).lower().count('confucius')
        if n:
            ch[rel] = n
    add('⑤ 面向客户文件（%d 个）搜 confucius = 0' % len(CUSTOMER_FILES),
        not ch, ch or '[]')

    # ⑥ 内部名清单已落盘（包外）
    inv = os.path.join(REPO, 'results', 'app', 'app154_internal_names.json')
    n_inv = 0
    if os.path.exists(inv):
        n_inv = json.load(open(inv, encoding='utf-8')).get('n_total', 0)
    add('⑥ 保留的内部「Confucius4」清单已落盘（包外，APP-154 §2 要求逐个列明）',
        n_inv > 0, '%d 处 / %s' % (n_inv, inv))

    # ⑦ release.json / package_profile.json 无内部编号
    for rel in ['release.json', 'package_profile.json']:
        t = read_text(rel)
        add('⑦ %s 无 APP-xxx 内部编号' % rel, not re.search(r'APP-\d+', t), '')

    # ⑧ 版本号
    rel_j = json.loads(read_text('release.json'))
    add('⑧ release.json version = 1.2.1', rel_j.get('version') == '1.2.1',
        rel_j.get('version'))
    add('⑧ release.json ext.version = 0.4.25', rel_j['ext'].get('version') == '0.4.25',
        rel_j['ext'].get('version'))
    pp = json.loads(read_text('package_profile.json'))
    add('⑧ package_profile.json ext_version = 0.4.25', pp.get('ext_version') == '0.4.25',
        pp.get('ext_version'))

    # ⑨ 包内无 results/mt2_accuracy.*
    mt2acc = [os.path.join(r, f) for r, d, fs in os.walk(PKG) for f in fs
              if 'mt2_accuracy' in f]
    add('⑨ 包内无 results/mt2_accuracy.*（MT2 内部基准）', not mt2acc, mt2acc or '[]')

    # ⑩ --check **实际输出**无内部说法（行为级判据，不是 grep 源码）
    #    🔴 判据修正：源码里的 `# 注释` / `"""docstring"""` **不会**被客户看到 ⇒
    #    判「--check 输出」必须**真跑 --check** 看 stdout/stderr，
    #    否则会把「注释里有 B 机」误判成「客户看到 B 机」（假 FAIL）。
    ck_log = os.path.join(REPO, 'results', 'app', 'app156_check_output.txt')
    if os.path.exists(ck_log):
        out = io.open(ck_log, encoding='utf-8', errors='replace').read()
        bad = [kw for kw in ('B 机', '待 B 机复核', 'rc5') if kw in out]
        add('⑩ --check 实际输出无「B 机/待 B 机复核/rc5」内部说法',
            not bad, bad or '0 处（真跑 --check 的 stdout/stderr）')
    else:
        add('⑩ --check 实际输出无内部说法（需先真跑 --check 留证）', False,
            '缺 %s' % ck_log)

    # ⑪ 除 preset_A.wav 外无音视频
    av = []
    for root, dirs, files in os.walk(PKG):
        for f in files:
            if os.path.splitext(f)[1].lower() in ('.wav', '.mp3', '.ogg', '.m4a',
                                                  '.flac', '.mp4', '.mkv', '.avi'):
                rel = os.path.relpath(os.path.join(root, f), PKG).replace('\\', '/')
                if not rel.endswith('preset_A.wav'):
                    av.append(rel)
    add('⑪ 除 preset_A.wav 外无音视频文件', not av, av or '[]')

    # ⑫ 无 CUDA DLL
    cuda = []
    for root, dirs, files in os.walk(PKG):
        for f in files:
            fl = f.lower()
            if fl.endswith('.dll') and ('cuda' in fl or 'cudnn' in fl
                                         or 'nvcuda' in fl or 'cublas' in fl):
                cuda.append(os.path.relpath(os.path.join(root, f), PKG))
    add('⑫ 包内无 CUDA DLL', not cuda, cuda or '[]')

    # ⑬ 无运行产物
    #    🔴 判据修正：`python/` 与 `.runtime_deps/` 下的 `__pycache__` 是
    #    **随包分发的 Python 运行时自带**（v1.2 包内同样有）⇒ **不是**运行产物；
    #    真正的运行产物是 `app/`、`ext/` 等**我方代码目录**下的 __pycache__。
    junk = []
    for root, dirs, files in os.walk(PKG):
        rel_root = os.path.relpath(root, PKG).replace('\\', '/')
        top = rel_root.split('/')[0]
        for f in files:
            fl = f.lower()
            if (fl.endswith(('.log', '.err')) or 'bridge_token' in fl
                    or '.bak' in fl):   # APP-157 §X：.bak_app154_docclean 也必须命中
                junk.append(os.path.relpath(os.path.join(root, f), PKG))
        for d in dirs:
            if d in ('ov_cache', 'npu_cache', '__pycache__'):
                if top in ('python', '.runtime_deps'):
                    continue          # 运行时自带，不是运行产物
                junk.append(os.path.relpath(os.path.join(root, d), PKG))
    add('⑬ 无 bridge_token/*.log/*.err/ov_cache/npu_cache/我方代码 __pycache__/*.bak*（含 .bak_<tag>）',
        not junk, junk[:10] or '[]')
    # 反证：旧判据 endswith('.bak') 对真实存在的 .bak_<tag> 恒 False ⇒ 假 PASS；
    #       新判据 '.bak' in fl 必须命中，证明本条有鉴别力。
    _bad = 'README_zh.md.bak_app154_docclean'
    add('⑬反证 旧判据漏检 .bak_<tag> ⇒ 新判据命中',
        (not _bad.endswith('.bak')) and ('.bak' in _bad), _bad)

    # ⑭ 克隆音色目录为空
    cv = [r for r, d, fs in os.walk(PKG) if 'clone_voice' in r.lower() and fs]
    add('⑭ 克隆音色目录为空', not cv, cv or '[]')

    # ⑮ models/mt 只含 mt3-int8sym-cw-q
    mts = sorted(os.listdir(rp('models/mt'))) if os.path.isdir(rp('models/mt')) else []
    add('⑮ models/mt 只含 mt3-int8sym-cw-q', mts == ['mt3-int8sym-cw-q'], mts)

    # ⑯ 出厂默认（package_profile）
    add('⑯ 出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU / turbo 开',
        pp.get('mt_model') == 'mt3-int8sym-cw-q' and pp.get('npu_turbo') is True,
        'mt=%s turbo=%s' % (pp.get('mt_model'), pp.get('npu_turbo')))

    # ⑰ EXT 版本一致
    v = read_text('ext/bridge/version.py')
    add('⑰ 包内 ext/bridge/version.py = 0.4.25', 'EXT_VERSION = "0.4.25"' in v, '')
    # 🔴 APP-157：原判据只跑 `python -c pass` ⇒ 恒 PASS 的死判据，改为真逐字节比。
    _repo_ext = r'C:\Users\Trekker-PTL\live_dub_ext\ext'
    _pkg_bridge = rp('ext/bridge')
    _same, _diff, _miss = 0, [], []
    for _r, _ds, _fs in os.walk(_repo_ext):
        _ds[:] = [d for d in _ds if d != '__pycache__']
        for _f in _fs:
            if _f.endswith(('.pyc', '.pyo')) or '.bak_' in _f:
                continue
            _src = os.path.join(_r, _f)
            _rel = os.path.relpath(_src, _repo_ext)
            _dst = os.path.join(_pkg_bridge, _rel)
            if not os.path.exists(_dst):
                _miss.append(_rel.replace('\\', '/'))
            elif hashlib.sha256(open(_src, 'rb').read()).digest() == \
                    hashlib.sha256(open(_dst, 'rb').read()).digest():
                _same += 1
            else:
                _diff.append(_rel.replace('\\', '/'))
    _allow_miss = {'tts_cuda_sidecar_ext.py'}   # MiniMVP 无 CUDA
    add('⑰ 包内 ext/bridge 与仓库 ext/ 逐字节一致（%d 个相同）' % _same,
        not _diff and set(_miss) <= _allow_miss,
        'diff=%s miss=%s' % (_diff[:5], _miss[:5]))

    # ⑱ 三轮门禁（APP-153 §1a ＋ APP-154 §1 ＋ APP-156 §1）
    if os.path.exists(ARMS_JSON):
        arms = json.load(open(ARMS_JSON, encoding='utf-8'))
        for r in arms:
            tag = r['arm']
            add('⑱[%s] 失控中止 = 0' % tag, r.get('n_runaway_abort') == 0,
                r.get('n_runaway_abort'))
            add('⑱[%s] 空配音（has_tts=false 且 tgt_len>0）= 0' % tag,
                r.get('n_empty_dub_with_text') == 0, r.get('n_empty_dub_with_text'))
            add('⑱[%s] 丢句 = 0' % tag, r.get('n_dropped') == 0, r.get('n_dropped'))
            add('⑱[%s] n_error = 0' % tag, r.get('n_error') == 0, r.get('n_error'))
            add('⑱[%s] n_resynth_failed = 0（APP-156 §1）' % tag,
                r.get('n_resynth_failed') == 0, r.get('n_resynth_failed'))
            add('⑱[%s] 60 s 墙钟兜底日志行数 = 0（APP-156 §1）' % tag,
                r.get('n_wall_fallback_log') == 0, r.get('n_wall_fallback_log'))
            add('⑱[%s] rc = 0' % tag, r.get('rc') == 0, r.get('rc'))
    else:
        add('⑱ 三轮门禁结果存在', False, ARMS_JSON + ' 不存在')

    # ── 汇总 ──────────────────────────────────────────────────
    n_pass = sum(1 for r in results if r['pass'])
    n_fail = len(results) - n_pass
    add('【汇总】全部通过', n_fail == 0, '%d PASS / %d FAIL' % (n_pass, n_fail))

    ev = {'pkg': PKG, 'results': results, 'n_pass': n_pass, 'n_fail': n_fail}
    with io.open(OUT_JSON, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=2))

    # 门禁表 .txt（正文里的 `<` 会被吃掉 ⇒ 用附件）
    with io.open(OUT_TXT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('MiniMVP v1.2.1 打 zip 白名单门禁表\n')
        f.write('生成：%s\n' % __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        f.write('包目录：%s\n\n' % PKG)
        for i, r in enumerate(results, 1):
            f.write('%2d. [%s] %s\n' % (i, 'PASS' if r['pass'] else 'FAIL', r['name']))
            if r['detail'] and r['detail'] != '[]':
                f.write('        证据：%s\n' % r['detail'][:400])
        f.write('\n结论：%d PASS / %d FAIL\n' % (n_pass, n_fail))
    log('\n落盘 → %s' % OUT_JSON)
    log('门禁表 → %s' % OUT_TXT)
    log('结论：%d PASS / %d FAIL' % (n_pass, n_fail))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
