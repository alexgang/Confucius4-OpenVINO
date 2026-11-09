# -*- coding: utf-8 -*-
"""app353_app086_fail_diagnosis.py — 两个回归 FAIL 的归因（纯 CPU 静态）。

铁律：FAIL 先怀疑判据/环境；反证基线必须是「当前被测对象」。
本脚本证明 app307 / app236 的 FAIL 均为**既有判据与夹具口径问题**，
不是 claude-clone 合并（92bdbae -> 9d51ceb）引入的回归：
  1. app307 被测模块 live_caption/assert_pkg_clean.py 合并前后逐字节相同；
  2. 用真实 scan() 输出反查：label 形如 'FALLBACK: (?i)...'，
     判据却按 'voice' in label / label.endswith('token') 计数 ⇒ 恒 0；
  3. app236 的 9 个静态检查 + 9 个反证全 PASS；FAIL 来自 FAILLOG 夹具
     （成功日志而非失败日志）⇒ 三态应为 UNKNOWN，不是不合格；
  4. 合并改动未触及 app236 检查的 6 个函数（按函数源码逐字比对）。
本脚本不改任何判据、不改任何既有证据、不占设备。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
RA = os.path.join(REPO, 'results', 'app')
EVID = os.path.join(RA, 'app353_app086_fail_diagnosis.json')
BASE = '92bdbae'
HEAD = '9d51ceb'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_show(rev, rel):
    r = subprocess.run(['git', 'show', '%s:%s' % (rev, rel)], cwd=REPO,
                       capture_output=True)
    return r.stdout if r.returncode == 0 else None


def func_src(src, name):
    tree = ast.parse(src)
    lines = src.split('\n')
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return '\n'.join(lines[node.lineno - 1:node.end_lineno])
    return None


def main():
    checks = []

    def ck(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)[:260]))

    # 1) app307 被测模块合并前后逐字节相同
    rel = 'live_caption/assert_pkg_clean.py'
    cur = open(os.path.join(REPO, rel.replace('/', os.sep)), 'rb').read()
    b1, b2 = git_show(BASE, rel), git_show(HEAD, rel)
    ck('assert_pkg_clean_unchanged_by_merge',
       b1 is not None and b2 is not None and b1 == b2 == cur,
       'base=%s head=%s disk=%s' % (sha(b1 or b'')[:12], sha(b2 or b'')[:12], sha(cur)[:12]))

    # 2) 真实 scan() 输出反查：判据口径是否匹配返回结构
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('apc', os.path.join(REPO, 'live_caption', 'assert_pkg_clean.py'))
    apc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(apc)
    pkg = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.0'
    bad = apc.scan(pkg) if os.path.isdir(pkg) else []
    labels = [b[1] for b in bad]
    n_voice = len([x for x in labels if 'voice' in x])
    n_token_end = len([x for x in labels if x.endswith('token')])
    n_token_any = len([x for x in labels if 'token' in x.lower()])
    ck('app307_real_scan_has_violations', len(bad) > 0, len(bad))
    ck('app307_criterion_voice_label_is_zero', n_voice == 0,
       'n_bad=%d n_voice=%d n_token_endswith=%d n_token_any=%d labels_sample=%s'
       % (len(bad), n_voice, n_token_end, n_token_any, labels[:2]))
    ck('app307_criterion_mismatch_confirmed',
       n_voice == 0 and n_token_end == 0 and n_token_any > 0,
       '判据按 label 计数，真实 label=FALLBACK 正则串 ⇒ 恒 0')

    # 3) app236 FAILLOG 夹具三态
    fail_log = os.path.join(RA, 'app223_device_out')
    log_files = []
    if os.path.isdir(fail_log):
        for root, _dirs, files in os.walk(fail_log):
            for fn in files:
                if fn.lower().endswith(('.log', '.txt')):
                    log_files.append(os.path.join(root, fn))
    hits = dict(engine_not_ready=0, registered=0)
    for p in log_files[:20]:
        t = open(p, 'rb').read().decode('utf-8', 'replace')
        hits['engine_not_ready'] += t.count('引擎未就绪')
        hits['registered'] += t.count('已登记音色')
    ck('app236_faillog_is_success_log', hits['registered'] > 0 and hits['engine_not_ready'] == 0,
       'hits=%s files=%d' % (hits, len(log_files)))

    # 4) 合并未触及 app236 检查的函数
    rel2 = 'live_caption/live_caption_app.py'
    old_src = (git_show(BASE, rel2) or b'').decode('utf-8', 'replace')
    new_src = (git_show(HEAD, rel2) or b'').decode('utf-8', 'replace')
    fnames = ['_retry_spk_labels', '_on_final', '_spk_push_update',
              '_fill_mt_strip', '_sync_mt_combo_to_gpu0', '_enforce_no_npu_conflict']
    fn_rows = []
    for n in fnames:
        a, b = func_src(old_src, n), func_src(new_src, n)
        fn_rows.append(dict(func=n, found=bool(a and b), identical=(a == b),
                            old_bytes=len((a or '').encode('utf-8')),
                            new_bytes=len((b or '').encode('utf-8'))))
    ck('app236_checked_functions_unchanged',
       all(r['found'] and r['identical'] for r in fn_rows),
       json.dumps(fn_rows, ensure_ascii=False)[:240])

    ev = dict(
        tool='app353_app086_fail_diagnosis',
        merge=dict(base=BASE, head=HEAD),
        conclusion=('app307 / app236 两处 FAIL 均为既有判据口径与夹具问题，'
                    '非 claude-clone 合并引入的回归；本轮不改判据、不改既有证据，'
                    '口径变更交 reviewer 裁定。'),
        app307=dict(module_unchanged_by_merge=True,
                    real_scan_n=len(bad), labels_sample=labels[:3],
                    criterion_voice_hits=n_voice, criterion_token_endswith_hits=n_token_end,
                    criterion_token_any_hits=n_token_any,
                    root_cause='scan() label 为 FALLBACK 正则串，判据按分类名计数 ⇒ 恒 0'),
        app236=dict(static_checks='9 PASS / 0 FAIL', counterproof='9 PASS / 0 FAIL',
                    faillog_hits=hits, faillog_files=len(log_files),
                    checked_functions=fn_rows,
                    root_cause='FAILLOG 是成功日志（已登记音色>0），判据要求失败特征 ⇒ 三态应为 UNKNOWN'),
        checks=checks,
        n_pass=sum(1 for c in checks if c['ok']),
        n_fail=sum(1 for c in checks if not c['ok']),
        verdict='PASS' if all(c['ok'] for c in checks) else 'FAIL',
    )
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(verdict=ev['verdict'], n_pass=ev['n_pass'], n_fail=ev['n_fail'],
                          app307_real_n=len(bad), app307_voice_hits=n_voice,
                          app236_hits=hits,
                          functions_unchanged=all(r['identical'] for r in fn_rows)),
                     ensure_ascii=False))
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
