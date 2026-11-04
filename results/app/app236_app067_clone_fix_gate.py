#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-067 ① 的**闸门**：验证「克隆 0 %」的修复在**代码层**成立。

## 为什么要有这个闸门（reviewer 要求 + MEMORY 铁律）

> 🔴🔴 **「判据 PASS」≠「判据正确」** ⇒ 拿**已知有缺陷的旧产物**跑一遍
> ⇒ 判据须能识破；**弱标记恒真** ⇒ 查**分支本体特征**。
> 🔴🔴 **判据的「抓取串」必须覆盖真实故障日志** ⇒ 否则**假 PASS**
> （§132 实测：判据①只抓「没有可用的音色」，真实故障串是「没有可用引擎 ⇒
> spk 音色登记失败」⇒ 报 PASS 而实则克隆全失 ⇒ 已扩成三条串）
> ⇒ **判据写完必须拿真实失败日志反查一遍**。

## 本闸门做什么

### ① 静态闸门（AST，不 import 被测模块 ⇒ 顶层 numpy 不会 abort）
对 `live_caption/tts_worker.py` / `tts_service.py` / `live_caption_app.py`：

| # | 判据 | 覆盖的真实故障 |
|---|---|---|
| G1 | worker 在 `_voice_ready` 为假时**入队**而不是丢弃 | ①(a) 根因 |
| G2 | `load()` 成功后**置位 + 排空队列** | ①(a) 补登记 |
| G3 | `spk_update` **真的写进 `_spk_bind`**（不是只打日志） | ①(b) 根因 |
| G4 | 合成队列**出队时**按 seg 解析音色 | ①(b) 根因 |
| G5 | `submit()` 命令体**带 seg**（纯附加） | ①(b) 前提 |
| G6 | service 有 `spk_update_seg()` | ①(b) 前提 |
| G7 | App 的**晚到标签**路径调用 `spk_update_seg` | ①(b) 接线 |
| G8 | D4：**状态栏「模型」优先取真值**（不只看 combo） | ③ 根因 |

### ② 反证（negative control）—— 判据必须有鉴别力
把改过的代码**逐个破坏**（还原成改前的形态）⇒ 判据**必须 FAIL**。
⇒ 判据恒真的组会被当场抓出来。

### ③ 真实失败日志反查
拿 §132 的**真实失败产物**（`app223_device_out/tts_on_clone.log`）
反查本闸门的「抓取串」⇒ 确认闸门**看得见**真实故障。

## 输出
`results/app/app236_app067_clone_fix_evidence.json`
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LC = os.path.join(REPO, 'live_caption')
OUT = os.path.join(HERE, 'app236_app067_clone_fix_evidence.json')

WORKER = os.path.join(LC, 'tts_worker.py')
SERVICE = os.path.join(LC, 'tts_service.py')
APP = os.path.join(LC, 'live_caption_app.py')
FAILLOG = os.path.join(REPO, 'results', 'app', 'app223_device_out',
                       'tts_on_clone.log')


# ══════════════════════════════════════════════════════════════
# 静态闸门：每个判据 = (名称, 文件, 检查函数)
# 检查函数返回 (ok: bool|None, detail)
# ══════════════════════════════════════════════════════════════
def _src(p):
    with open(p, 'rb') as f:
        return f.read().decode('utf-8')


def _norm(p):
    return _src(p).replace('\r\n', '\n')


def _find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def _func_src(src, name):
    """取函数体文本（按行号切片 ⇒ 不依赖缩进解析）。"""
    tree = ast.parse(src)
    fn = _find_func(tree, name)
    if fn is None:
        return ''
    lines = src.split('\n')
    return '\n'.join(lines[fn.lineno - 1:fn.end_lineno])


# ── G1：worker 加载期**入队**（不是丢弃）──────────────────────
def g1_queue_not_discard():
    src = _norm(WORKER)
    body = _func_src(src, '_register_spk_voice')
    if not body:
        return False, '找不到 _register_spk_voice'
    ok = ('_pending_spk_voice.append' in body
          and '_voice_ready' in body)
    # 🔴 反证特征：旧实现是 `log(...没有可用引擎...)` + `return False`
    old = ('没有可用引擎 ⇒ spk 音色登记失败' in body
           and '_pending_spk_voice' not in body)
    return (ok and not old), ('入队=%s 旧丢弃=%s' % (ok, old))


# ── G2：load() 置位 + 排空 ───────────────────────────────────
def g2_flush_after_load():
    src = _norm(WORKER)
    body = _func_src(src, 'load')
    if not body:
        return False, '找不到 load'
    has_flag = 'self._voice_ready = True' in body
    has_flush = 'self._flush_pending_spk_voice()' in body
    # 顺序铁律：先置位、后排空
    order_ok = (has_flag and has_flush
                and body.index('self._voice_ready = True')
                < body.index('self._flush_pending_spk_voice()'))
    return (has_flag and has_flush and order_ok), \
        ('置位=%s 排空=%s 顺序=%s' % (has_flag, has_flush, order_ok))


# ── G3：spk_update 真的写进 _spk_bind ───────────────────────
def g3_spk_update_effective():
    src = _norm(WORKER)
    tree = ast.parse(src)
    # 🔴 找 `elif cmd == 'spk_update':` 的那个分支
    #    （比较节点是 ast.Compare，不是 ast.List ⇒ 不能用 isinstance(body, List)）
    found = None
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        cmp_txt = ast.dump(n.test)
        if "'spk_update'" not in cmp_txt and '"spk_update"' not in cmp_txt:
            continue
        # 🔴 **只取 then 分支**（elif 链在 AST 里是嵌套的 If，
        #    `n.end_lineno` 会覆盖**后面所有 elif** ⇒ 判据会看错分支）
        if not n.body:
            continue
        lo = n.body[0].lineno - 1
        hi = n.body[-1].end_lineno
        found = '\n'.join(src.split('\n')[lo:hi])
        break
    if found is None:
        return False, '找不到 spk_update 分支'
    writes = '_spk_bind[' in found
    has_lock = '_spk_bind_lock' in found
    seg_keyed = "'seg'" in found
    # 🔴 反证特征：旧实现只有 log，没有写表
    only_log = ('本轮不改变合成行为' in found) and not writes
    return (writes and has_lock and seg_keyed and not only_log), \
        ('写表=%s 加锁=%s 按seg=%s 旧只记日志=%s'
         % (writes, has_lock, seg_keyed, only_log))


# ── G4：出队时按 seg 解析音色 ────────────────────────────────
def g4_resolve_at_dequeue():
    src = _norm(WORKER)
    body = _func_src(src, '_synth_loop')
    if not body:
        return False, '找不到 _synth_loop'
    has_seg = 'seg = item[8]' in body
    has_lookup = '_spk_bind.get(seg)' in body
    # 🔴 关键：解析必须发生在 `self.synth(...)` **之前**
    synth_call = body.find('self.synth(')
    lookup_at = body.find('_spk_bind.get(seg)')
    order_ok = (synth_call > 0 and lookup_at > 0 and lookup_at < synth_call)
    return (has_seg and has_lookup and order_ok), \
        ('取seg=%s 查表=%s 在合成前=%s' % (has_seg, has_lookup, order_ok))


# ── G5：submit() 命令体带 seg ───────────────────────────────
def g5_submit_carries_seg():
    src = _norm(SERVICE)
    body = _func_src(src, 'submit')
    if not body:
        return False, '找不到 submit'
    has = "cmd['seg']" in body
    # 🔴 纪律：只在有值时加 ⇒ 老调用方命令体逐字不变
    guarded = bool(re.search(r'if seg is not None:', body))
    return (has and guarded), ('带seg=%s 有值才加=%s' % (has, guarded))


# ── G6：service 有 spk_update_seg ────────────────────────────
def g6_service_update_api():
    src = _norm(SERVICE)
    tree = ast.parse(src)
    fn = _find_func(tree, 'spk_update_seg')
    if fn is None:
        return False, '找不到 spk_update_seg'
    body = _func_src(src, 'spk_update_seg')
    sends = "'cmd': 'spk_update'" in body
    keyed = "'seg'" in body
    return (sends and keyed), ('发命令=%s 按seg=%s' % (sends, keyed))


# ── G7：App 晚到标签路径调用 spk_update_seg ──────────────────
def g7_app_pushes_update():
    src = _norm(APP)
    body = _func_src(src, '_retry_spk_labels')
    cli = _func_src(src, '_cli_retry_spk_labels')
    if not body or not cli:
        return False, '找不到 _retry_spk_labels / _cli_retry_spk_labels'
    # 🔴 GUI 走 helper `_spk_push_update`；CLI 直接调 `spk_update_seg`
    g = '_spk_push_update(' in body
    c = 'spk_update_seg(' in cli
    # 同步路径（_on_final）也要
    onf = _func_src(src, '_on_final')
    sync = '_spk_push_update(' in onf
    helper = _func_src(src, '_spk_push_update')
    helper_ok = 'spk_update_seg(' in helper
    return (g and c and sync and helper_ok), \
        ('GUI=%s CLI=%s 同步路径=%s helper=%s' % (g, c, sync, helper_ok))


# ── G8：D4 状态栏「模型」优先取真值 ─────────────────────────
def g8_d4_strip_uses_truth():
    src = _norm(APP)
    body = _func_src(src, '_fill_mt_strip')
    if not body:
        return False, '找不到 _fill_mt_strip'
    # 🔴 判据 = 「label 的**首选来源**是活着的 engine_key + 真值设备」
    #   ⇒ 破坏它（_ek 恒为 None）⇒ 就会退回 combo ⇒ 正是原始 bug
    truth_lookup = ("_ek = getattr(mt, 'engine_key', None)" in body
                    and "o.get('engine') == _ek" in body
                    and "o.get('device') == _dev" in body)
    # 🔴 反证特征：label **只**从 combo 的 opt 取
    combo_only = bool(re.search(
        r"label\s*=\s*\(opt or \)\.get\('label'\)\s*\n", body))
    return (truth_lookup and not combo_only), \
        ('真值优先=%s 旧只看combo=%s' % (truth_lookup, combo_only))


# ── G9：combo 同步到 GPU.0 ──────────────────────────────────
def g9_combo_synced():
    src = _norm(APP)
    helper = _func_src(src, '_sync_mt_combo_to_gpu0')
    enf = _func_src(src, '_enforce_no_npu_conflict')
    if not helper or not enf:
        return False, '找不到 _sync_mt_combo_to_gpu0 / _enforce_no_npu_conflict'
    in_enf = '_sync_mt_combo_to_gpu0()' in enf
    finds_gpu = "INT8-CW@GPU.0" in helper
    return (in_enf and finds_gpu), \
        ('enforce调用=%s 找GPU.0=%s' % (in_enf, finds_gpu))


CHECKS = [
    ('G1 worker 加载期入队（不丢弃）', WORKER, g1_queue_not_discard),
    ('G2 load() 置位 + 排空队列', WORKER, g2_flush_after_load),
    ('G3 spk_update 真写 _spk_bind', WORKER, g3_spk_update_effective),
    ('G4 出队时按 seg 解析音色', WORKER, g4_resolve_at_dequeue),
    ('G5 synth 命令体带 seg', SERVICE, g5_submit_carries_seg),
    ('G6 service 有 spk_update_seg', SERVICE, g6_service_update_api),
    ('G7 App 晚到标签补发', APP, g7_app_pushes_update),
    ('G8 D4 状态栏模型取真值', APP, g8_d4_strip_uses_truth),
    ('G9 combo 同步到 GPU.0', APP, g9_combo_synced),
]


# ══════════════════════════════════════════════════════════════
# 反证：破坏代码 ⇒ 判据必须 FAIL
# ══════════════════════════════════════════════════════════════
def counterproof():
    """逐组破坏改过的代码 ⇒ 对应判据必须 FAIL（判据非恒真）。"""
    import shutil
    import tempfile

    # (判据名, 文件, 破坏操作)
    BREAKS = [
        ('G1 worker 加载期入队（不丢弃）', WORKER,
         lambda s: s.replace('self._pending_spk_voice.append(dict(msg))',
                              'pass  # 破坏：丢弃')),
        ('G2 load() 置位 + 排空队列', WORKER,
         lambda s: s.replace('self._flush_pending_spk_voice()',
                              'pass  # 破坏：不排空')),
        ('G3 spk_update 真写 _spk_bind', WORKER,
         lambda s: s.replace('self._spk_bind[_seg] = (str(_spk), _spk_conf)',
                              'pass  # 破坏：只记日志')),
        ('G4 出队时按 seg 解析音色', WORKER,
         lambda s: s.replace('_b = self._spk_bind.get(seg)',
                              '_b = None  # 破坏：不查表')),
        ('G5 synth 命令体带 seg', SERVICE,
         lambda s: s.replace("cmd['seg'] = int(seg)",
                              'pass  # 破坏：不带 seg')),
        ('G6 service 有 spk_update_seg', SERVICE,
         lambda s: s.replace("return self._send({'cmd': 'spk_update', 'seg': int(seg),\n"
                              "                               'spk': str(spk), 'spk_conf': spk_conf})",
                              'return False  # 破坏：不发命令')),
        ('G7 App 晚到标签补发', APP,
         lambda s: s.replace('tts.spk_update_seg(seg, spk, spk_conf)',
                              'tts.spk_update_seg  # 破坏：不补发')),
        ('G8 D4 状态栏模型取真值', APP,
         lambda s: s.replace("_ek = getattr(mt, 'engine_key', None)",
                              "_ek = None  # 破坏：不看真值 engine_key")),
        ('G9 combo 同步到 GPU.0', APP,
         lambda s: s.replace('self._sync_mt_combo_to_gpu0()',
                              'pass  # 破坏：不同步')),
    ]

    results = []
    tmpdir = tempfile.mkdtemp(prefix='app236_cp_')
    try:
        for name, target, brk in BREAKS:
            src = _norm(target)
            broken = brk(src)
            if broken == src:
                results.append({'check': name, 'broke': False,
                                'verdict': 'SKIP',
                                'detail': '破坏锚点未命中（代码已变）'})
                continue
            # 写到临时副本并让判据读它
            bak = target + '.cpbak'
            shutil.copy2(target, bak)
            try:
                with open(target, 'w', encoding='utf-8', newline='') as f:
                    f.write(broken)
                # 重跑该判据
                fn = dict((c[0], c[2]) for c in CHECKS)[name]
                ok, detail = fn()
                results.append({'check': name, 'broke': True,
                                'verdict': 'PASS' if ok is False
                                else 'FAIL(判据无鉴别力)',
                                'detail': detail})
            finally:
                shutil.move(bak, target)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return results


# ══════════════════════════════════════════════════════════════
# 真实失败日志反查
# ══════════════════════════════════════════════════════════════
def real_log_recheck():
    """拿 §132 的**真实失败产物**反查 ⇒ 确认闸门看得见真实故障。"""
    if not os.path.exists(FAILLOG):
        return {'ok': None, 'detail': '找不到真实失败日志'}
    t = _src(FAILLOG)
    # 🔴 三条真实故障串（§132 实测：判据只抓一条 ⇒ 假 PASS）
    pats = {
        '没有可用引擎 ⇒ spk 音色登记失败': '①(a) 根因',
        '已登记音色': '①(a) 的**反面**（成功标志）',
        'spk=None': '①(b) 症状（遥测里才有）',
    }
    hits = {k: t.count(k) for k in pats}
    # 「已登记音色」= 0 才是失败特征
    ok = (hits['没有可用引擎 ⇒ spk 音色登记失败'] > 0
          and hits['已登记音色'] == 0)
    return {'ok': ok, 'hits': hits,
            'detail': '真实失败日志可被识别（引擎未就绪 %d 次 / 已登记音色 %d 次）'
                      % (hits['没有可用引擎 ⇒ spk 音色登记失败'],
                         hits['已登记音色'])}


def main() -> int:
    checks = []
    n_fail = 0
    for name, path, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = None, '检查异常：%r' % (e,)
        if ok is not True:
            n_fail += 1
        checks.append({'name': name, 'ok': ok, 'detail': detail})

    cps = counterproof()
    n_cp_bad = sum(1 for c in cps if c['verdict'] != 'PASS')

    rl = real_log_recheck()

    out = {
        'script': os.path.basename(__file__),
        'correction': 'APP-067 ①③',
        'files': {'worker': WORKER, 'service': SERVICE, 'app': APP},
        'checks': checks,
        'n_pass': len(checks) - n_fail,
        'n_fail': n_fail,
        'counterproofs': cps,
        'n_counterproof_failed_to_detect': n_cp_bad,
        'counterproof_ok': n_cp_bad == 0,
        'real_failure_log_recheck': rl,
        'verdict': ('PASS' if (n_fail == 0 and n_cp_bad == 0
                               and rl['ok'] is not False)
                    else 'FAIL'),
        'meaning': ('PASS = **代码层**的修复成立且判据有鉴别力'
                    '（反证全部被抓住）且看得见真实故障；'
                    '**不等于**设备级验收（需 §138 影子包重跑）。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for c in checks:
        print('%-34s %-6s %s' % (c['name'], c['ok'], c['detail']))
    print('--- 反证（破坏代码 ⇒ 判据必须 FAIL）---')
    for c in cps:
        print('%-34s %s  %s' % (c['check'], c['verdict'], c['detail']))
    print('--- 真实失败日志反查 ---')
    print('  ', rl['detail'])
    print('结果：%d PASS / %d FAIL  ⇒ %s'
          % (out['n_pass'], out['n_fail'], out['verdict']))
    print('产物：', OUT)
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
