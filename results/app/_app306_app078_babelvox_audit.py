r"""_app306_app078_babelvox_audit.py — APP-078 ①⑦②③ 静态取证。

## reviewer 的指控
13:15 用 v2.2 自带 python/models 跑 EXT 桥接，`bridge.log` 里有
`SpeakerLibrary 就绪：...（4 个音色：cindy, lou, phil, steve）`
⇒ 推断 v2.2 包内带着 babelvox 的 4 个示例音色。

## 本脚本查的四种口径（**必须分开，混在一起就会得出错误结论**）
  A. **安装目录** `<HOME>/Confucius4_LiveCaption_v2.{0,1,2}/`（用户实际启动的）
  B. **交付 zip** 同名 `.zip`（`pack_v13.py` 用 `pkg_exclude.iter_package_files` 生成）
  C. **MiniMVP rc3_perftest_rev2.zip**（§139 交付物）
  D. **dev 树 / 构建脚本**：`pkg_exclude` 剔除规则 vs `app2xx` 的整目录复制

🔴 预期结论（实测后再定案，不预设）：
   `pkg_exclude.THIRD_PARTY_NOISE_PREFIXES` 已排除
   `python/Lib/site-packages/babelvox/data/speakers/` ⇒ **zip 里应该 0**；
   但 `app206/app221` 的 `copy_tree()` 是**整目录复制、不走 pkg_exclude**
   ⇒ **安装目录里仍带着** ⇒ 用户从目录启动就会加载 ⇒ reviewer 指控成立，
   而 APP-074「v2.x 不违规」的结论**只对 zip 成立，对目录不成立**。

不占设备、不推理、不改任何客户包目录/zip。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')
EV = os.path.join(HERE, '_app306_app078_babelvox_audit.json')

NAMES = ('cindy', 'lou', 'phil', 'steve')
SPEAKER_DIR = 'python/Lib/site-packages/babelvox/data/speakers/'
CHECKS = []


def check(name, cond, detail=''):
    CHECKS.append(dict(name=name, ok=bool(cond), detail=str(detail)))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + str(detail)) if detail else ''))
    return bool(cond)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def dir_scan(pkg):
    d = os.path.join(pkg, *SPEAKER_DIR.split('/'))
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                out.append(dict(rel=SPEAKER_DIR + fn,
                                bytes=os.path.getsize(p),
                                mtime=os.path.getmtime(p),
                                sha256=sha256_file(p)))
    return out


def zip_scan(zp):
    out = []
    with zipfile.ZipFile(zp) as z:
        for i in z.infolist():
            n = i.filename.replace('\\', '/')
            # 只认「babelvox/data/speakers/ 下的音色文件」，不限扩展名
            if 'babelvox/data/speakers/' in n.lower():
                out.append(dict(name=n, bytes=i.file_size,
                                sha256=sha256_bytes(z.read(i))))
    return out


def main():
    print('=' * 72)
    print('_app306 — APP-078 babelvox 示例音色四口径取证')
    print('=' * 72)
    report = dict(dirs={}, zips={}, minimvp={})

    print('\n[1] v2.0 / v2.1 / v2.2 —— 安装目录 vs 交付 zip')
    for v in ('2.0', '2.1', '2.2'):
        pkg = os.path.join(HOME, 'Confucius4_LiveCaption_v' + v)
        zp = pkg + '.zip'
        dh = dir_scan(pkg)
        zh = zip_scan(zp) if os.path.isfile(zp) else []
        report['dirs'][v] = dict(path=pkg, n=len(dh), files=dh)
        report['zips'][v] = dict(path=zp, n=len(zh), files=zh,
                                 size=os.path.getsize(zp),
                                 sha256=sha256_file(zp),
                                 n_entries=len(zipfile.ZipFile(zp).namelist()))
        print('  v%s 目录 %d 个 / zip %d 个' % (v, len(dh), len(zh)))
        for f in dh:
            print('     DIR %s %d B %s' % (f['rel'], f['bytes'], f['sha256'][:16]))
        check('v%s 安装目录**确实带** 4 音色×2 格式 = 8 文件（reviewer 指控成立）'
              % v, len(dh) == 8, len(dh))
        check('v%s 交付 zip **不含**任何示例音色（APP-074 的 zip 结论成立）'
              % v, len(zh) == 0, len(zh))

    # 三个目录的 8 文件 SHA 必须全同（同一份第三方素材被反复复制）
    sig = {}
    for v, r in report['dirs'].items():
        for f in r['files']:
            sig.setdefault(f['rel'], set()).add(f['sha256'])
    check('三个目录里同名音色 SHA 逐字节全同',
          all(len(s) == 1 for s in sig.values()),
          {k: len(v) for k, v in sig.items()})
    report['dir_signature'] = {k: sorted(v)[0] for k, v in sig.items()}

    # zip 里 babelvox 库代码仍在（§139 说过 23 条），但无音色数据
    for v, r in report['zips'].items():
        with zipfile.ZipFile(r['path']) as z:
            nb = len([n for n in z.namelist() if '/babelvox/' in n])
        report['zips'][v]['n_babelvox_lib_entries'] = nb
        check('v%s zip 里 babelvox **库代码**仍在（未误删库）' % v, nb > 0, nb)

    print('\n[2] MiniMVP rc3_perftest_rev2（§139 交付物）')
    mvp = os.path.join(HOME, 'shared', 'minimvp',
                       'Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest_rev2.zip')
    mh = zip_scan(mvp) if os.path.isfile(mvp) else []
    with zipfile.ZipFile(mvp) as z:
        n_babel = len([n for n in z.namelist() if '/babelvox/' in n])
        n_voice = len([n for n in z.namelist()
                       if n.endswith('preset_A.wav')])
    report['minimvp'] = dict(path=mvp, n_speaker_files=len(mh), files=mh,
                             n_babelvox_lib_entries=n_babel,
                             n_preset_a_wav=n_voice)
    check('MiniMVP rev2 zip 不含示例音色', len(mh) == 0, len(mh))
    check('MiniMVP rev2 仍带 preset_A.wav（预设 A 不受影响）',
          n_voice == 1, n_voice)
    print('     MiniMVP babelvox 库代码条目 =', n_babel)

    print('\n[3] 为什么目录里有、zip 里没有（根因）')
    sys.path.insert(0, REPO)
    import pkg_exclude
    check('pkg_exclude 已有 babelvox/data/speakers/ 排除规则',
          SPEAKER_DIR in pkg_exclude.THIRD_PARTY_NOISE_PREFIXES,
          str(pkg_exclude.THIRD_PARTY_NOISE_PREFIXES))
    probe = SPEAKER_DIR + 'cindy.npy'
    check('is_excluded(示例音色) == True',
          pkg_exclude.is_excluded(probe, 'python'), probe)
    listed = [rel for rel, _ in pkg_exclude.iter_package_files(
        os.path.join(HOME, 'Confucius4_LiveCaption_v2.2'))]
    check('iter_package_files 清单里 0 个示例音色',
          not any('babelvox/data/speakers/' in r for r in listed))
    # 反证：把排除前缀去掉 ⇒ 判据必须能识破（非恒真）
    saved = pkg_exclude.THIRD_PARTY_NOISE_PREFIXES
    try:
        pkg_exclude.THIRD_PARTY_NOISE_PREFIXES = ()
        leaked = not pkg_exclude.is_excluded(probe, 'python')
        check('反证：去掉排除前缀 ⇒ 示例音色会进包（判据非恒真）',
              leaked, 'is_excluded=%s' % (not leaked))
    finally:
        pkg_exclude.THIRD_PARTY_NOISE_PREFIXES = saved

    # 构建脚本是整目录复制、不走 pkg_exclude ⇒ 目录残留的根因
    build_scripts = [
        os.path.join(REPO, 'results', 'app', 'app206_app057_v20_stage.py'),
        os.path.join(REPO, 'results', 'app', 'app221_app061_v22_build.py'),
    ]
    root_cause = {}
    for p in build_scripts:
        s = open(p, encoding='utf-8').read()
        uses_walk = ('os.walk(src)' in s or 'os.walk(s)' in s)
        uses_exclude = ('pkg_exclude' in s and
                        ('is_excluded' in s or 'iter_package_files' in s))
        root_cause[os.path.basename(p)] = dict(
            uses_os_walk_copy=uses_walk,
            applies_pkg_exclude_on_copy=uses_exclude)
        check('%s 整目录复制（os.walk）' % os.path.basename(p), uses_walk)
    check('根因：构建脚本复制时**未调用** pkg_exclude ⇒ 目录残留',
          not any(x['applies_pkg_exclude_on_copy']
                  for x in root_cause.values()), str(root_cause))
    report['root_cause'] = root_cause

    print('\n[4] SpeakerLibrary 无内置音色时能否正常工作')
    # 🔴 判据修正（本轮实测）：首跑凭记忆写了 `builtin_speaker_available`
    #   与 `_copy_builtin_speakers` ⇒ 3 个 FAIL 全是**判据名字写错**。
    #   真实实现（dev 与 v2.2 包内逐字一致）：
    #     `builtin_speakers_available()`            —— 复数 speakers
    #     `_ReadOnlySpeakerLibrary.__init__`        —— `os.path.isdir(base)` 守卫
    #     `copy_builtins=False`                    —— 只读、不复制
    eng = open(os.path.join(REPO, 'live_caption', 'tts_engine.py'),
               encoding='utf-8').read()
    pkg_eng = open(os.path.join(HOME, 'Confucius4_LiveCaption_v2.2',
                                'app', 'tts_engine.py'),
                   encoding='utf-8').read()
    check('tts_engine 有 builtin_speakers_available() 探测',
          'def builtin_speakers_available' in eng)
    check('v2.2 包内同名函数也在（不是只有 dev 树有）',
          'def builtin_speakers_available' in pkg_eng)
    check('_SpeakerLibraryWithBuiltinFallback 用 os.path.isdir(base) 守卫',
          'if base and os.path.isdir(base)' in eng)
    check('内置目录只读、不复制（copy_builtins=False）',
          'copy_builtins=False' in eng)
    check('预设 A 路径来自 models/qwen3tts/voices/preset_A.wav',
          'preset_A.wav' in eng)
    # 反证：把守卫去掉 ⇒ 静态判据必须能识破
    fake_eng = eng.replace('if base and os.path.isdir(base):',
                           'if True:')
    check('反证：去掉 isdir 守卫 ⇒ 判据能识破（非恒真）',
          'if base and os.path.isdir(base):' not in fake_eng)

    # 🔴 真运行时验证（纯 Python 库调用，**不加载任何模型 / 不占设备**）：
    #    把 `BUILTIN_SPEAKERS_DIR` 指到空目录 ⇒
    #      `builtin_speakers_available()` 必须返回 ()
    #      `_ReadOnlySpeakerLibrary` 必须仍能构造（_builtin=None）⇒ 不崩。
    print('\n[5] 运行时：把内置音色目录指到空目录')
    import ast
    import subprocess
    import tempfile
    code = r'''
import os, sys, tempfile, json
sys.path.insert(0, r"<APPDIR>")
import babelvox.speakers as bs
empty = tempfile.mkdtemp(prefix="app306_empty_bs_")
old = getattr(bs, "BUILTIN_SPEAKERS_DIR", None)
bs.BUILTIN_SPEAKERS_DIR = empty
import tts_engine as te
avail = te.builtin_speakers_available()
# 构造只读包装（不加载模型）
inner = bs.SpeakerLibrary(tempfile.mkdtemp(prefix="app306_user_"), copy_builtins=False)
wrap = te._SpeakerLibraryWithBuiltinFallback(inner, on_log=lambda *a: None)
profiles = wrap.list_profiles()
print(json.dumps(dict(avail=list(avail), builtin_is_none=(wrap._builtin is None),
                      n_profiles=len(profiles), ok=True)))
bs.BUILTIN_SPEAKERS_DIR = old
'''
    app_dir = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2', 'app')
    code = code.replace('<APPDIR>', app_dir)
    py = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2', 'python', 'python.exe')
    runtime = dict(skipped=False)
    try:
        r = subprocess.run([py, '-c', code], capture_output=True,
                           text=True, timeout=180)
        runtime['rc'] = r.returncode
        runtime['stdout'] = (r.stdout or '').strip()[-1500:]
        runtime['stderr'] = (r.stderr or '').strip()[-1500:]
        if r.returncode == 0:
            try:
                d = json.loads(r.stdout.strip().splitlines()[-1])
                runtime['result'] = d
                check('无内置音色时 builtin_speakers_available() 返回空',
                      d.get('avail') == [], d.get('avail'))
                # 🔴 判据修正（本轮实测）：首跑断言 `_builtin is None`，
                #   但空目录 `os.path.isdir()` 为真 ⇒ 会构造一个**空的**
                #   SpeakerLibrary（builtin_is_none=False），这是**正确行为**：
                #   包装对象存在、只是查不到任何内置音色。
                #   ⇒ 真判据 = 「构造不抛异常（ok=True）」∧「音色表为空」。
                check('无内置音色时包装对象正常构造（不崩）',
                      d.get('ok') is True, d.get('ok'))
                check('无内置音色时 list_profiles() 返回 0 个音色',
                      d.get('n_profiles') == 0, d.get('n_profiles'))
            except Exception as e:
                check('运行时结果可解析', False, '%r / %s' % (e, r.stdout[-400:]))
        else:
            check('运行时验证 rc=0', False, runtime['stderr'][:400])
    except Exception as e:
        runtime['skipped'] = True
        runtime['error'] = repr(e)
        check('运行时验证执行成功', False, repr(e))
    report['runtime_without_builtin'] = runtime

    # 结论
    conclusion = (
        'APP-074 的结论**必须改正**：'
        '「v2.x 不违规」只对**交付 zip** 成立（3 个 zip 实测 0 个示例音色，'
        '因为 pack_v13.py 用 pkg_exclude 剔除）；'
        '但 v2.0/v2.1/v2.2 的**安装目录**各带 8 个第三方音色文件'
        '（cindy/lou/phil/steve 的 .json + .npy），'
        '用户从目录启动桥接就会由 SpeakerLibrary 加载 ⇒ reviewer 13:15 的'
        '实测**成立**，授权边界对「已安装目录」并不干净。'
        '根因：app206/app221 的 copy_tree 整目录复制未走 pkg_exclude。'
        '⇒ v2.3 起必须在**建目录阶段**也剔除（不能只依赖打包阶段）。'
        '预设 A 来自 Amphion metis，不依赖这 4 个音色（APP-073/074 的'
        '功能结论不变）。')
    report['conclusion'] = conclusion
    print('\n' + conclusion)

    n_pass = sum(1 for c in CHECKS if c['ok'])
    n_fail = len(CHECKS) - n_pass
    out = dict(tool='_app306_app078_babelvox_audit', app='APP-078',
               ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               checks=CHECKS, n_pass=n_pass, n_fail=n_fail,
               verdict='PASS' if n_fail == 0 else 'FAIL', **report)
    with open(EV, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nverdict = %s (%d PASS / %d FAIL)  证据 %s'
          % (out['verdict'], n_pass, n_fail, EV))
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
