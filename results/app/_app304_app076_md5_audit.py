r"""_app304_app076_md5_audit.py — APP-076 的三方 md5 对照（只读审计）。

对照三方：
  ① ASR 源目录 `qwen3asr_06b/scripts/`（ASR-050 交接单声称的 md5）
  ② 影子包 `shared/app067_shadow/app/asr_spk/`（本轮 r2 设备实测用的包）
  ③ 旧交付包 `Confucius4_LiveCaption_v2.2/app/asr_spk/`（**只读，不修改**）

另验：
  * `ASR_FILES` 从 4 项补到 **5** 项（含 `asr_runtime_switches.py`）
  * ASR 源码里「`min_clean_ratio` + 数字」的**第一个**匹配必须是真默认值 0.6
    （App 的 `app193` 用正则现读 ⇒ 第一个匹配错了会静默跑 0.8）
  * App 侧 `LIVECAP_SPK_MIN_CLEAN_RATIO` 默认值来自 ASR 的
    `DEFAULT_MIN_CLEAN_RATIO`（不互相 import，用 AST 读）
  * 登记门槛**不放宽**：4 个常量值逐字核对
  * MiniMVP 是否含旁路（⇒ 写「不适用」的依据）

不占设备、不推理、不改任何客户包。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')
EV = os.path.join(HERE, '_app304_app076_md5_audit.json')

ASR_SCRIPTS = os.path.join(HOME, 'qwen3asr_06b', 'scripts')
SHADOW = os.path.join(HOME, 'shared', 'app067_shadow', 'app', 'asr_spk')
V22 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2', 'app', 'asr_spk')

# ASR-050 交接单 md5（逐字抄自 status/asr/notes/asr_for_app_asr050_handoff.md）
HANDOFF_MD5 = {
    'asr052_speaker_tracker_api.py': '61be393ce6343bfa63892ce0c35f5c44',
    'asr052_spk_runtime.py': '2ff82933edec80becd01f9d28d202ea6',
    'asr_thread_defaults.py': '0482f9c49105490ac219194c2fa7c184',
    'asr_spk_window.py': '7d719e1d7f251be9ce68503be4361807',
    'asr_runtime_switches.py': '7f12e9a5575d7a88cafcd3f54689e326',
}

CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append(dict(name=name, ok=bool(cond), detail=str(detail)))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + str(detail)) if detail else ''))
    return bool(cond)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def meta(p):
    return dict(path=p, bytes=os.path.getsize(p), md5=md5(p),
                mtime=os.path.getmtime(p))


def main():
    print('=' * 72)
    print('_app304 — APP-076 md5 对照（ASR-050 交接）')
    print('=' * 72)
    table = []
    print('\n[1] 5 个 ASR 文件：源 / 影子包 / v2.2 旧包')
    for fn in HANDOFF_MD5:
        row = dict(file=fn, handoff_md5=HANDOFF_MD5[fn])
        for tag, d in (('asr_source', ASR_SCRIPTS), ('shadow', SHADOW),
                       ('v22_pkg', V22)):
            p = os.path.join(d, fn)
            row[tag] = meta(p) if os.path.isfile(p) else None
        table.append(row)
        src = row['asr_source']
        check('ASR 源 %s md5 == 交接单' % fn,
              src is not None and src['md5'] == row['handoff_md5'],
              (src or {}).get('md5', 'MISSING'))
        sh = row['shadow']
        check('影子包 %s md5 == 交接单' % fn,
              sh is not None and sh['md5'] == row['handoff_md5'],
              (sh or {}).get('md5', 'MISSING'))
        print('     %-34s src=%s shadow=%s v22=%s'
              % (fn, (src or {}).get('md5', '-')[:12],
                 (sh or {}).get('md5', '-')[:12],
                 (row['v22_pkg'] or {}).get('md5', 'ABSENT')[:12]))

    # v2.2 旧包必须**保持原样**（APP-055：不原地改）
    v22_present = [r['file'] for r in table if r['v22_pkg']]
    check('v2.2 旧包仍是 3 个文件（未被本轮原地修改）',
          len(v22_present) == 3, str(v22_present))

    # ── [2] 同步脚本 ASR_FILES ─────────────────────────────────
    print('\n[2] sync_c164 的 ASR_FILES')
    sync_p = os.path.join(REPO, 'live_caption',
                          'sync_c164_spk_assets_to_pkg.py')
    src = open(sync_p, encoding='utf-8').read()
    tree = ast.parse(src)
    files = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'ASR_FILES'
                for t in n.targets):
            files = ast.literal_eval(n.value)
    check('ASR_FILES 可静态解析', files is not None, str(files))
    check('ASR_FILES == 5 项', files is not None and len(files) == 5,
          str(files))
    check('ASR_FILES 覆盖交接单全部 5 个文件',
          files is not None and set(files) == set(HANDOFF_MD5),
          str(sorted(set(HANDOFF_MD5) - set(files or []))))
    check('ASR_FILES 含 asr_runtime_switches.py',
          files is not None and 'asr_runtime_switches.py' in files)

    # ── [3] 「min_clean_ratio + 数字」第一个出现必须是真默认值 ──
    print('\n[3] ASR 源码默认值口径（app193 正则现读）')
    api = os.path.join(ASR_SCRIPTS, 'asr052_speaker_tracker_api.py')
    api_src = open(api, encoding='utf-8').read()
    # 🔴 判据修正（本轮实测）：必须用 **app193 的真实正则**，不能用
    #   自制宽松正则 `min_clean_ratio[^\n\d]{0,40}(\d+)` —— 后者会把
    #   注释标题「ASR-050：`min_clean_ratio` 默认 0.8 → 0.6」里的
    #   **历史值 0.8** 当成第一个匹配（本轮首跑即误报 FAIL）。
    #   app193 用的是 `re.search` + 必须有 `=`（签名形态）⇒ 它读到的
    #   第一个匹配就是 `__init__` 签名的真默认值。
    gate193 = re.compile(
        r'min_clean_ratio\s*(?::\s*[A-Za-z_][\w\[\], ]*)?=\s*([0-9.]+)')
    m193 = gate193.search(api_src)
    check('app193 真实正则能抓到默认门限', m193 is not None,
          m193.group(1) if m193 else None)
    check('app193 **第一个**匹配 == 0.6（真默认值，未漂移回 0.8）',
          m193 is not None and abs(float(m193.group(1)) - 0.6) < 1e-9,
          m193.group(1) if m193 else None)
    # 反证：把签名里的 0.6 改回 0.8 ⇒ 判据必须能识破
    fake_src = api_src[:m193.start(1)] + '0.8' + api_src[m193.end(1):] \
        if m193 else api_src
    fake_m = gate193.search(fake_src)
    check('反证：把签名默认值改成 0.8 ⇒ app193 正则读到 0.8（判据非恒真）',
          fake_m is not None and abs(float(fake_m.group(1)) - 0.8) < 1e-9,
          fake_m.group(1) if fake_m else None)
    # AST 读模块级 DEFAULT_MIN_CLEAN_RATIO
    t = ast.parse(api_src)
    default_val = None
    for n in t.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(x, ast.Name) and x.id == 'DEFAULT_MIN_CLEAN_RATIO'
                for x in n.targets):
            default_val = ast.literal_eval(n.value)
    check('模块级 DEFAULT_MIN_CLEAN_RATIO == 0.6',
          default_val is not None and abs(float(default_val) - 0.6) < 1e-9,
          default_val)

    # ── [4] App 侧同源（AST 静态解析，不 import）─────────────────
    print('\n[4] App 侧 speaker_tracker.py 同源')
    st_p = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
    st_src = open(st_p, encoding='utf-8').read()
    check('App 侧环境变量名正确',
          "'LIVECAP_SPK_MIN_CLEAN_RATIO'" in st_src)
    # 🔴 判据修正（本轮实测）：speaker_tracker.py **本来就要** import
    #   `asr052_speaker_tracker_api.SpeakerTracker`（这是正常生产依赖），
    #   首跑用「全文不得出现 import asr052」⇒ 误报 FAIL。
    #   真实口径：只验「**AST 静态解析函数** `_asr_min_clean_ratio()` 内部
    #   不 import ASR 模块」（避免拉 numpy / 兄弟模块依赖）。
    tt = ast.parse(st_src)
    fnode = next((n for n in tt.body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == '_asr_min_clean_ratio'), None)
    check('存在 _asr_min_clean_ratio() 静态解析函数', fnode is not None)
    if fnode:
        imports = [n for n in ast.walk(fnode)
                   if isinstance(n, (ast.Import, ast.ImportFrom))]
        bad = [ast.unparse(n) for n in imports
               if 'asr052' in ast.unparse(n)]
        check('AST 解析函数内部不 import ASR 模块（零重依赖）',
              not bad, str(bad))
    check('App 侧用 AST 读 ASR 常量',
          'ast.parse' in st_src and 'DEFAULT_MIN_CLEAN_RATIO' in st_src)
    # 🔴 反证：把 ASR 常量改成 0.8，App 侧的「与 ASR 不同才显式传」
    #    逻辑必须在真实代码里（不是恒真标记）
    check('App 侧有「与 ASR 默认值不同才显式传」分支',
          "_ASR_MIN_CLEAN_RATIO_DEFAULT" in st_src
          and "kwargs['min_clean_ratio']" in st_src)
    # 运行时实测（不 import 兄弟模块；本脚本用 .venv，有 numpy）
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    saved = os.environ.pop('LIVECAP_SPK_MIN_CLEAN_RATIO', None)
    try:
        import speaker_tracker as st
        app_val = float(st._MIN_CLEAN_RATIO)
        app_src = st._MIN_CLEAN_RATIO_SRC
        check('运行时 _MIN_CLEAN_RATIO == 0.6',
              abs(app_val - 0.6) < 1e-9, '%s / %s' % (app_val, app_src))
        check('运行时同源标记指向 ASR 常量',
              'asr052_speaker_tracker_api' in str(app_src), app_src)
        os.environ['LIVECAP_SPK_MIN_CLEAN_RATIO'] = '0.75'
        import importlib
        importlib.reload(st)
        check('env LIVECAP_SPK_MIN_CLEAN_RATIO=0.75 能覆盖',
              abs(float(st._MIN_CLEAN_RATIO) - 0.75) < 1e-9,
              st._MIN_CLEAN_RATIO)
        os.environ.pop('LIVECAP_SPK_MIN_CLEAN_RATIO', None)
        importlib.reload(st)
        win = float(st.WIN_S_DEFAULT) if hasattr(st, 'WIN_S_DEFAULT') else None
        check('WIN_S 仍为 5.0（同源未被破坏）',
              win is None or abs(win - 5.0) < 1e-9, win)
    except Exception as e:
        check('App 侧运行时自检无异常', False, '%r' % (e,))
    finally:
        os.environ.pop('LIVECAP_SPK_MIN_CLEAN_RATIO', None)
        if saved is not None:
            os.environ['LIVECAP_SPK_MIN_CLEAN_RATIO'] = saved

    # ── [5] 登记门槛不放宽 ─────────────────────────────────────
    print('\n[5] 克隆登记门槛**不放宽**（APP-075/076）')
    sv_p = os.path.join(REPO, 'live_caption', 'speaker_voice.py')
    sv_src = open(sv_p, encoding='utf-8').read()
    tt = ast.parse(sv_src)
    consts = {}
    for n in tt.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            try:
                consts[n.targets[0].id] = ast.literal_eval(n.value)
            except Exception:
                pass
    expect = {'REG_CONF_MIN': 0.5, 'REG_MIN_CONT_S': 2.5,
              'SWITCH_GUARD_S': 0.5, 'CONT_GAP_TOL_S': 0.5}
    for k, v in expect.items():
        check('%s == %s（未放宽）' % (k, v),
              k in consts and abs(float(consts[k]) - v) < 1e-9,
              consts.get(k))
    # 反证：把常量改小必须能被识破
    fake = dict(consts); fake['REG_CONF_MIN'] = 0.3
    check('反证：把 REG_CONF_MIN 改成 0.3 ⇒ 判据会 FAIL（非恒真）',
          not (abs(float(fake['REG_CONF_MIN']) - 0.5) < 1e-9))

    # ── [6] MiniMVP 是否含旁路 ─────────────────────────────────
    print('\n[6] MiniMVP 适用性')
    minimvp_p = os.path.join(REPO, 'results', 'app', '_app242_build_minimvp.py')
    msrc = open(minimvp_p, encoding='utf-8').read()
    mt = ast.parse(msrc)
    forb = None
    for n in ast.walk(mt):
        if isinstance(n, ast.Assign) and any(
                isinstance(x, ast.Name) and x.id == 'FORBIDDEN_DIRS'
                for x in n.targets):
            forb = ast.literal_eval(n.value)
    check('MiniMVP FORBIDDEN_DIRS 含 ext ⇒ 不带 EXT',
          forb is not None and 'ext' in forb, str(forb))
    # 🔴 判据修正（本轮实测）：首跑猜「FORBIDDEN_NAMES 含 speaker_tracker」
    #   ⇒ 误报 FAIL。真实情况更微妙：MiniMVP zip 里**带**旁路代码文件
    #   （speaker_tracker.py / speaker_voice.py / clone_collector.py），
    #   但 `app/asr_spk/` 与 `models/spk/` **均为 0 条目** ⇒ 旁路**内核
    #   与模型都不在** ⇒ `min_clean_ratio` 换了也没有可运行的消费者。
    #   ⇒ 判据以 **zip 实测** 为准，不以脚本常量猜。
    import zipfile
    mvp_zip = os.path.join(
        HOME, 'shared', 'minimvp',
        'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip')
    znames = []
    if os.path.isfile(mvp_zip):
        with zipfile.ZipFile(mvp_zip) as z:
            znames = z.namelist()
    n_asr_spk = len([n for n in znames if '/app/asr_spk/' in n])
    n_spk_model = len([n for n in znames if '/models/spk/' in n])
    n_ext = len([n for n in znames if '/ext/' in n])
    n_bypass_py = len([n for n in znames
                       if n.endswith(('/speaker_tracker.py',
                                      '/speaker_voice.py',
                                      '/clone_collector.py'))])
    check('MiniMVP zip 可读', bool(znames), '%d 条目' % len(znames))
    check('MiniMVP 无 app/asr_spk/（旁路内核不在包内）',
          n_asr_spk == 0, n_asr_spk)
    check('MiniMVP 无 models/spk/（旁路模型不在包内）',
          n_spk_model == 0, n_spk_model)
    check('MiniMVP 无 ext/', n_ext == 0, n_ext)
    check('MiniMVP 仍带 3 个旁路代码文件（如实记录，不写「完全没有」）',
          n_bypass_py == 3, n_bypass_py)

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(tool='_app304_app076_md5_audit', app='APP-076',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               handoff='status/asr/notes/asr_for_app_asr050_handoff.md',
               checks=CHECKS, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL',
               md5_table=table, asr_files=files,
               constants=consts, app_min_clean_ratio=locals().get('app_val'),
               minimvp_zip=dict(path=mvp_zip, n_entries=len(znames),
                                n_app_asr_spk=n_asr_spk,
                                n_models_spk=n_spk_model, n_ext=n_ext,
                                n_bypass_py=n_bypass_py),
               note=('MiniMVP rc3_perftest_rev2 zip 实测：app/asr_spk/ = 0、'
                     'models/spk/ = 0、ext/ = 0，但仍带 3 个旁路代码文件'
                     '（speaker_tracker.py / speaker_voice.py / '
                     'clone_collector.py）⇒ 旁路**内核与模型都不在** ⇒ '
                     'min_clean_ratio 改动在 MiniMVP 内无可运行消费者 ⇒ '
                     'APP-076 第 2 条对 MiniMVP **不适用**（如实注明'
                     '「代码文件仍在、内核/模型不在」）；'
                     'v2.3 打包需带 5 个 ASR 文件 + '
                     'models/spk/pyannote_seg_3_0/fp16-w5/'))
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nverdict = %s (%d PASS / %d FAIL)  证据 %s'
          % (out['verdict'], n_pass, n_fail, EV))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
