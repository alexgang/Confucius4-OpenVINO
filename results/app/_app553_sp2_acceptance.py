#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app553_sp2_acceptance.py —— **Special MVP sp2** 的包上验收（APP-108 §2/§3/§4）。

🔴 **与 sp1 的验收（app536）不同的地方（reviewer APP-108 §3 明文要求）**：
   「在定位之前，验收结论改写为「PASS（有 1 项未结：退出码异常）」，
     **不要写 13/13**。」
   ⇒ 本文件的 ``verdict`` = **「PASS（有 1 项未结：退出码异常）」**，
     且**没有**「13/13」这种计数式结论；未结项在 ``open_issues`` 里点名。

🔴 **核模型身份**（APP-109 ①：「其余打包规则不变：核模型身份
   （config 维度 + 权重 SHA 对源目录）」）⇒ 这里**重算** sp2 里每个
   MANIFEST 登记文件的 SHA256，与 MANIFEST 记录值逐个比对。

🔴 **只读**（除：把 sp2 的 `app/MANIFEST.json` 的 ``pkg_models_root`` 从
   sp1 改成 sp2 —— **定点单字段替换 + 唯一命中断言**；那是「这份 MANIFEST
   描述的是哪个包」的元数据，不改会指向错误的包）。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
SP1 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp1')
SP2 = os.path.join(HOME, 'Confucius4_LiveCaption_SpecialMVP_v1.0-sp2')
DEV = os.path.join(REPO, 'live_caption')
OUT = os.path.join(RESULTS, 'app553_specialmvp_sp2_acceptance.json')
BLACKLIST_PATTERNS = ['bridge_token*', '*.pid', '*.log']

ev = {'pkg': SP2, 'version': '1.0-sp2',
      'started': time.strftime('%Y-%m-%d %H:%M:%S'),
      'checks': [], 'open_issues': []}


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def add(name, ok, detail, **kw):
    c = {'name': name, 'pass': bool(ok), 'detail': detail}
    c.update(kw)
    ev['checks'].append(c)
    print('[%s] %s | %s' % ('PASS' if ok else 'FAIL', name, detail[:110]),
          flush=True)
    return c


def blacklist_hit(rel):
    import fnmatch
    for pat in BLACKLIST_PATTERNS:
        if (fnmatch.fnmatch(rel, pat)
                or fnmatch.fnmatch(os.path.basename(rel), pat)):
            return pat
    return None


# ── ① profile / 标记文件 ──
prof = json.load(open(os.path.join(SP2, 'package_profile.json'),
                      encoding='utf-8'))
add('A1: package_profile.json = specialmvp + allow_cuda=True',
    prof.get('profile') == 'specialmvp' and prof.get('allow_cuda') is True,
    'profile=%s allow_cuda=%s allow_clone_voice=%s'
    % (prof.get('profile'), prof.get('allow_cuda'),
       prof.get('allow_clone_voice')))

# ── ② app 代码与 dev 树逐字节一致 ──
appdir = os.path.join(SP2, 'app')
mism = []
n_app = 0
for f in sorted(os.listdir(appdir)):
    if not f.endswith('.py'):
        continue
    n_app += 1
    src = os.path.join(DEV, f)
    if not os.path.isfile(src):
        mism.append({'file': f, 'why': 'dev 树无同名文件'})
    elif sha256_file(src) != sha256_file(os.path.join(appdir, f)):
        mism.append({'file': f, 'why': 'SHA 不同'})
add('A2: 包内 app/*.py 与 dev 树逐字节一致', not mism,
    '%d 个 .py，不一致 %d 个 %s' % (n_app, len(mism), mism[:3]))

# ── ③ .pyc / 黑名单 ──
n_pyc = 0
black = []
for dp, _dn, fn in os.walk(SP2):
    for f in fn:
        if f.endswith('.pyc'):
            n_pyc += 1
        rel = os.path.relpath(os.path.join(dp, f), SP2).replace('\\', '/')
        pat = blacklist_hit(rel)
        if pat:
            black.append(rel)
add('A3: 包内无 .pyc、无黑名单文件', n_pyc == 0 and not black,
    'pyc=%d blacklist=%d' % (n_pyc, len(black)))

# ── ④ 核模型身份：MANIFEST 逐文件 SHA 重算 ──
mpath = os.path.join(appdir, 'MANIFEST.json')
mtxt = open(mpath, encoding='utf-8', newline='').read()
m = json.loads(mtxt)
cur_root = m.get('pkg_models_root')
want_root = os.path.join(SP2, 'models')
if cur_root != want_root:
    # 🔴🔴 **2026-11-14 §205 修掉的真缺陷（死代码 ⇒ 重定向从未执行）**：
    #    原实现是 `if SP1 in mtxt:` —— `mtxt` 是**裸 JSON 文本**（反斜杠已被转义成
    #    `\\`），而 `SP1` 是**未转义**的单反斜杠路径 ⇒ `SP1 in mtxt` **恒为 False**
    #    ⇒ 整段重定向**从来没执行过** ⇒ sp2 的 `app/MANIFEST.json` 一直带着
    #    **sp1 的** `pkg_models_root`（实测 `...SpecialMVP_v1.0-sp1\\models`）⇒
    #    **MANIFEST 自相矛盾**（指向不在包内的、另一个包的 models 目录）＋
    #    泄漏构建机家目录字面量到交付包。
    #    现在改成：**解码后的值**比较 ＋ **转义形态**定点替换 ＋ 唯一命中断言 ＋
    #    写盘后逐字节复核（不改文件其余任何字节）。
    if not cur_root:
        raise RuntimeError('MANIFEST 缺 pkg_models_root 字段，无法重定向')
    esc_old = json.dumps(cur_root)[1:-1]
    esc_new = json.dumps(want_root)[1:-1]
    n_hit = mtxt.count(esc_old)
    if n_hit != 1:
        raise RuntimeError('MANIFEST 里 pkg_models_root 的转义形态出现 %d 次'
                           '（预期 1）' % n_hit)
    raw2 = mtxt.replace(esc_old, esc_new)
    # created_at：语义 =「这份 MANIFEST 是为哪个包生成的」⇒ 一并刷新（唯一定位，
    # 命中不唯一就**不改**并如实记录，绝不模糊替换）。
    old_created = m.get('created_at')
    created_done = 'skipped'
    if isinstance(old_created, str) and old_created:
        c_old = json.dumps(old_created)[1:-1]
        c_new = json.dumps(time.strftime('%Y-%m-%d %H:%M:%S'))[1:-1]
        if raw2.count(c_old) == 1:
            raw2 = raw2.replace(c_old, c_new)
            created_done = 'updated'
        else:
            created_done = 'kept(count=%d)' % raw2.count(c_old)
    m2 = json.loads(raw2)
    if m2.get('pkg_models_root') != want_root:
        raise RuntimeError('替换后 pkg_models_root 仍不是 %s' % want_root)
    # 只允许这两个键发生变化（其余任何字段的字节都不能动）
    diff_keys = {k for k in set(m) | set(m2) if m.get(k) != m2.get(k)}
    if not diff_keys <= {'pkg_models_root', 'created_at'}:
        raise RuntimeError('MANIFEST 改动范围超出预期（只允许 pkg_models_root'
                           ' 与 created_at，实际多了 %s）'
                           % sorted(diff_keys - {'pkg_models_root',
                                                 'created_at'}))
    with open(mpath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(raw2)
    chk = open(mpath, encoding='utf-8', newline='').read()
    if chk != raw2:
        raise RuntimeError('MANIFEST 写盘后逐字节不一致')
    if json.loads(chk).get('pkg_models_root') != want_root:
        raise RuntimeError('写盘后 pkg_models_root 仍不对')
    ev['manifest_repointed'] = {'from': cur_root, 'to': want_root,
                                'raw_hits': n_hit, 'created_at': created_done,
                                'method': 'escaped-text-targeted-replace',
                                'note': '§205：原 `SP1 in mtxt` 是死代码（裸 JSON '
                                        '文本 vs 未转义路径）⇒ 重定向从未执行'}

m = json.load(open(mpath, encoding='utf-8'))
n_ok = n_bad = 0
bad = []
for key, info in m['models'].items():
    d = os.path.join(SP2, 'models', key.replace('/', os.sep))
    # 🔴 MANIFEST 的 key 可能是**目录**（如 `mt/mt2-int8sym-cw-q`），
    #    也可能是**顶层文件**（如 `embed_tokens_06b_f16.npy`）⇒ 两种都要处理。
    #    （第一版闸门一律拼 `key/name` ⇒ 把顶层文件判成「缺文件」＝**假 FAIL**。）
    is_dir = os.path.isdir(d)
    for fe in info.get('files', []):
        p = os.path.join(d, fe['name']) if is_dir else d
        if not os.path.isfile(p):
            bad.append({'model': key, 'file': fe['name'], 'why': '缺文件',
                        'looked_at': p})
            n_bad += 1
            continue
        h = sha256_file(p)
        if h == fe.get('sha256'):
            n_ok += 1
        else:
            bad.append({'model': key, 'file': fe['name'], 'why': 'SHA 不同',
                        'expect': fe.get('sha256'), 'got': h})
            n_bad += 1
add('A4: 核模型身份（MANIFEST 逐文件 SHA256 对包内实际文件）', n_bad == 0,
    '登记 %d 个文件，一致 %d，不一致 %d %s'
    % (n_ok + n_bad, n_ok, n_bad, bad[:2]), n_ok=n_ok, n_bad=n_bad)

# ── ⑤ cuda_env 可搬迁（pyvenv.cfg 指包内 python/）──
pv = open(os.path.join(SP2, 'cuda_env', 'pyvenv.cfg'), encoding='utf-8').read()
add('A5: cuda_env/pyvenv.cfg 已重定位到 sp2（随包离线可用）',
    (SP2 in pv and SP1 not in pv), pv.splitlines()[0] if pv else '(空)')

# ── ⑥ 设备解析（APP-108 §2 的核心判定）──
p549 = os.path.join(RESULTS, 'app549_sp2_device_resolution.json')
if os.path.isfile(p549):
    d549 = json.load(open(p549, encoding='utf-8'))
    add('B: 隔离 LOCALAPPDATA 下三种配置的设备解析（APP-108 §2）',
        d549.get('verdict') == 'PASS',
        'verdict=%s；真实配置 SHA 前后不变=%s'
        % (d549.get('verdict'), d549.get('real_config_unchanged')),
        detail_cases=[{'id': c['id'], 'resolved': c.get('resolved_devices'),
                       'warn': c.get('warn_asr_mt_same_gpu_present')}
                      for c in d549.get('cases', [])],
        real_config_unchanged=d549.get('real_config_unchanged'))
else:
    add('B: 隔离 LOCALAPPDATA 下三种配置的设备解析（APP-108 §2）', False,
        '缺证据 %s' % p549)

# ── ⑦ MiniMVP / 完整版行为一字不变（回归）──
p552 = os.path.join(RESULTS, 'app552_special_profile_check_after_fix.json')
if os.path.isfile(p552):
    d552 = json.load(open(p552, encoding='utf-8'))
    det = d552.get('detail', {})
    ok = (d552.get('verdict') == 'PASS'
          and det.get('minimvp', {}).get('DEFAULT_DEVICES')
          == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
          and det.get('full', {}).get('DEFAULT_DEVICES')
          == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'GPU.0'})
    add('C: MiniMVP / 完整版默认设备一字不变（回归）', ok,
        'minimvp=%s full=%s' % (det.get('minimvp', {}).get('DEFAULT_DEVICES'),
                                det.get('full', {}).get('DEFAULT_DEVICES')))
else:
    add('C: MiniMVP / 完整版默认设备一字不变（回归）', False,
        '缺证据 %s' % p552)

# ── ⑧ 整链两臂（APP-108 §3）──
p551 = os.path.join(RESULTS, 'app551_open1_two_arm.json')
p551c = os.path.join(RESULTS, 'app551_open1_armC.json')
arms = []
for _p in (p551, p551c):
    if os.path.isfile(_p):
        arms.extend(json.load(open(_p, encoding='utf-8')).get('arms', []))
if arms:
    d551 = {'arms': arms}
    ev['arms'] = [{'id': a.get('id'), 'desc': a.get('desc'), 'rc': a.get('rc'),
                   'rc_hex': a.get('rc_hex'), 'elapsed_s': a.get('elapsed_s'),
                   'start': a.get('start'), 'end': a.get('end'),
                   'tts_out_bytes': a.get('tts_out_bytes'),
                   'eventlog_len': len(a.get('eventlog') or ''),
                   'real_cfg_unchanged': a.get('real_cfg_unchanged'),
                   'eventlog_head': (a.get('eventlog') or '')[:3000],
                   'wer_reports': a.get('wer_reports')}
                  for a in arms]
    n_abort = sum(1 for a in arms if a.get('rc') == 3221226505)
    add('D: 10 分钟对照臂（MT=NPU+TTS off / MT=GPU.0+TTS=CUDA / '
        '阳性对照 MT=NPU+TTS=CUDA）',
        len(arms) >= 2,
        '跑了 %d 臂；rc=%s；abort 臂=%s；事件日志条目合计 %d'
        % (len(arms), [a.get('rc') for a in arms],
           [a.get('id') for a in arms if a.get('rc') == 3221226505],
           sum(len(a.get('eventlog') or '') for a in arms)))
else:
    add('D: 10 分钟对照臂', False, '缺证据 %s / %s' % (p551, p551c))

# ── ⑨ 丢句原因（APP-108 §4）──
p552b = os.path.join(RESULTS, 'app552_specialmvp_dropped_sentences.json')
if os.path.isfile(p552b):
    d552b = json.load(open(p552b, encoding='utf-8'))
    add('E: 10 句丢弃逐句原因（APP-108 §4）',
        d552b.get('summary', {}).get('not_close_cancel')
        and d552b.get('summary', {}).get('not_timeout')
        and d552b.get('summary', {}).get('not_8s_rule'),
        '提交 %s / 播完 %s / 丢弃 %s；全部 late_drop（阈值 %s，滞后 %s–%s s）'
        % (d552b['summary']['n_submitted'], d552b['summary']['n_played'],
           d552b['summary']['n_dropped'],
           d552b['exclusions']['thresholds_seen'],
           d552b['exclusions']['lag_min'], d552b['exclusions']['lag_max']),
        filled=d552b.get('filled_question_marks'))
else:
    add('E: 10 句丢弃逐句原因（APP-108 §4）', False, '缺证据 %s' % p552b)

# ── ⑩ 未结项（reviewer 明文：不并入 PASS，也不掩盖）──
ev['open_issues'] = [{
    'id': 'OPEN-1',
    'title': '长跑退出码 3221226505（0xC0000409）未定位',
    'status': '**未结**（本文件不把它并入 PASS 判定，也不掩盖）',
    'detail': 'sp1 的 10 分钟整链跑完、产物写全后进程 abort（0xC0000409）。'
              'APP-108 §3 要求做 10 分钟两臂对照并附 Windows 事件日志 —— '
              '见 arms 字段与 §202 的结论。',
}]

# ── ⑪ **内容绑定**（§205 新增）：把「验收时的包内容」逐文件 SHA256 记进证据 ──
# 🔴 **为什么必须有**（§204 修完 fail-open 后的剩余轴）：验收证据原先**只记计数**
#    （"28 个 .py，不一致 0 个"）⇒ **一个 sha256 都没有** ⇒ 打包闸门拿它无法判断
#    「包内容自验收以来有没有被改过」⇒ 验收后改包照样能出包。
#    现在把**绑定范围**内的每个文件逐个 SHA256 记进 `pkg_content`，
#    出包闸门（`_app537`）会**逐条重算比对**（见 `check_content_binding`）。
#    绑定范围：**包内代码 + 元数据**；
#    **不含** README*.md / docs/（打包脚本自己会重写 README 的包体积行）、
#    **不含** cuda_env/（数千个运行时文件）、**不含** models/（由 MANIFEST 的
#    逐文件 SHA256 绑定，见 A4）。
BOUND_SCOPE = ('app/*.py', 'release.json', 'package_profile.json',
               'app/MANIFEST.json')
_bound = []
for _f in sorted(os.listdir(appdir)):
    if _f.endswith('.py'):
        _bound.append('app/' + _f)
for _rel in ('release.json', 'package_profile.json', 'app/MANIFEST.json'):
    if os.path.isfile(os.path.join(SP2, _rel.replace('/', os.sep))):
        _bound.append(_rel)
_bound = sorted(set(_bound))
_bound_files = {r: sha256_file(os.path.join(SP2, r.replace('/', os.sep)))
                for r in _bound}
_tdigest = hashlib.sha256()
for _r in sorted(_bound_files):
    _tdigest.update(_r.encode('utf-8') + b'\x00' + _bound_files[_r].encode()
                    + b'\n')
ev['pkg_content'] = {
    'scope': list(BOUND_SCOPE),
    'alg': 'sha256',
    'n_files': len(_bound_files),
    'files': _bound_files,
    'tree_digest': _tdigest.hexdigest(),
    'note': '§205：验收时的包内容指纹；出包闸门逐条重算比对 ⇒ '
            '验收后改包会被拦住',
}

n_fail = sum(1 for c in ev['checks'] if not c['pass'])
ev['n_checks'] = len(ev['checks'])
ev['n_fail'] = n_fail
# 🔴 reviewer 明文：**不要写 13/13** ⇒ 结论带「1 项未结」
ev['verdict'] = ('PASS（有 1 项未结：退出码异常）' if n_fail == 0
                  else 'FAIL（%d 项未过）' % n_fail)
ev['verdict_note'] = (
    '判定只覆盖**用户要求的三条**（TTS=CUDA／ASR=iGPU／MT=NPU）与包内一致性；'
    '**退出码异常单列 open_issues，不掩盖也不并入判定**（APP-108 §3）')
ev['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print('VERDICT =', ev['verdict'], ' n_fail =', n_fail, '->', OUT)
sys.exit(0 if n_fail == 0 else 1)
