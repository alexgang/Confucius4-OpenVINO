r"""_app249_replay_desen.py —— APP-155 脱敏的**决定性独立复核（重放法）**。

## 为什么用这个判据

前两版复核都不可靠：
* `app155_verify_desens.py`（§248 引用）判据＝「把占位还原成原句 ⇒ 与改前逐字节相等」，
  它靠 `find` 定位 ⇒ **短片段多处出现就错位** ⇒ 8 个文件 FAIL_STRUCTURE。
* 我第一版骨架法（`_app249_verify_desen_skeleton.py`）判据＝「去占位 vs 去 GT 句」，
  但它只删了 `hits` 里**每行一条**的命中 ⇒ apply 实际在同一行删了**多句** ⇒ 57 个文件假 FAIL。

⇒ 两个判据都**先怀疑自己**（MEMORY：FAIL 先怀疑判据/环境）。

## 本判据（**重放法**：不看 hits，直接重跑变换）

对每个被改动的文件 F：

    expected = apply_transform(HEAD:F)      # 用 apply 的**同一套**算法重跑
    actual   = F(工作树)

    判定：expected == actual（**逐字节**）

这**不依赖 hits 的粒度**，也不依赖任何"还原/定位"启发式 ⇒
* 若相等 ⇒ 工作树文件 **确实**＝「HEAD 去掉 GT 会议句、换成占位」的结果，
  **既没多删也没多写**（结构无损）；
* 再叠加 §2 **穷尽重扫**（工作树里 GT 会议句命中 == 0）⇒ 会议原句**确实**被拿掉了。

## 🔴 反证组（有鉴别力）

把某处占位**改回**原句 ⇒ expected != actual ⇒ 必须 FAIL。
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
GTJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_ground_truth.json')
APPLYJSON = os.path.join(REPO, 'results', 'app', 'app155_desens_apply.json')
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_replay_verify.json')

PLACEHOLDER = re.compile(r'\[会议句 idx \d+\]')
LOG_PREFIX_RE = re.compile(r'^(?:\[[^\]]{1,40}\]\s*)+')
PUNCT = r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]'


def log(m):
    print(m, flush=True)


def norm(s):
    s = s.strip().lower()
    s = re.sub(r'[\s　]+', ' ', s)
    return re.sub(PUNCT, '', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


def strip_log_prefix(s):
    m = LOG_PREFIX_RE.match(s)
    if not m:
        return s, ''
    return s[m.end():], m.group(0)


def git_show_bytes(rel):
    r = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + rel], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def build_gt(gt):
    sents = set()
    for rel in gt['gt_files']:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        if rel.endswith('.jsonl'):
            for line in t.splitlines():
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                for k in ('text', 'tgt', 'src', 'zh', 'en'):
                    if isinstance(o.get(k), str):
                        sents.add(norm(o[k]))
            continue
        for s in sentences(t):
            sents.add(norm(s))
    return {s for s in sents if len(s) >= gt['min_len']}


def apply_transform(text, idx_map, min_len):
    """与 `app155_desens_apply.py` **同算法**：逐行、逐句、长句优先、只替一次。"""
    lines = text.splitlines(keepends=True)
    n_repl = 0
    for i in range(len(lines)):
        raw = lines[i]
        m = re.match(r'^(.*?)((?:\r\n|\r|\n)*)$', raw, re.S)
        body, term = m.group(1), m.group(2)
        cands = []
        for s in sentences(body):
            core, pre = strip_log_prefix(s)
            nc = norm(core)
            if len(nc) >= min_len and nc in idx_map:
                cands.append((len(core), core, pre, nc))
        cands.sort(key=lambda x: -x[0])
        for _ln, core, pre, nc in cands:
            target = pre + core
            if target in body:
                body = body.replace(target, '%s[会议句 idx %d]' % (pre, idx_map[nc]), 1)
                n_repl += 1
        lines[i] = body + term
    return ''.join(lines), n_repl


def main():
    gt = json.load(open(GTJSON, encoding='utf-8'))
    apply_rec = json.load(open(APPLYJSON, encoding='utf-8'))
    sents = build_gt(gt)
    idx_map = {s: i + 1 for i, s in enumerate(sorted(sents))}
    log('GT 句子 %d 条 ⇒ 序号表 %d 条' % (len(sents), len(idx_map)))

    results = []
    n_pass = n_fail = 0
    for c in apply_rec['changed']:
        rel = c['file']
        before_b = git_show_bytes(rel)
        if before_b is None:
            results.append({'file': rel, 'verdict': 'SKIP_NO_HEAD'})
            continue
        before = before_b.decode('utf-8', 'replace')
        expected, n_repl = apply_transform(before, idx_map, gt['min_len'])
        actual = io.open(os.path.join(REPO, rel.replace('/', os.sep)),
                         encoding='utf-8', errors='replace', newline='').read()
        # 🔴🔴 **行尾归一化**（§236 坑⑥／§225 autocrlf）：
        #    `git show HEAD:` 给的是**入库形态（LF）**，而工作树因 `core.autocrlf=true`
        #    是 **CRLF** ⇒ 直接逐字节比 ⇒ **第一个 CRLF 处就分叉** ⇒ 假 FAIL。
        #    变换本身是**逐行**的（保留行尾）⇒ 对 LF 与 CRLF 两种形态**等价**
        #    ⇒ 两边都归一化成 LF 再比，才是「提交进去的内容 == 原内容+变换」。
        exp_b = expected.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        act_b = actual.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        if exp_b == act_b:
            n_pass += 1
            results.append({'file': rel, 'verdict': 'PASS',
                            'n_repl_replayed': n_repl,
                            'n_repl_reported': c['n_repl'],
                            'bytes': len(act_b)})
        else:
            n_fail += 1
            det = []
            if n_repl != c['n_repl']:
                det.append('n_repl replay=%d reported=%d' % (n_repl, c['n_repl']))
            k = 0
            while k < min(len(exp_b), len(act_b)) and exp_b[k] == act_b[k]:
                k += 1
            det.append('first_diff_at=%d' % k)
            det.append('expected_ctx=%r' % exp_b[max(0, k - 50):k + 50].decode('utf-8', 'replace'))
            det.append('actual_ctx=%r' % act_b[max(0, k - 50):k + 50].decode('utf-8', 'replace'))
            results.append({'file': rel, 'verdict': 'FAIL', 'detail': det})
            log('  FAIL %s %s' % (rel, det[:2]))

    log('\n§1 重放法（apply(HEAD) == 工作树，逐字节）：%d PASS / %d FAIL（共 %d）'
        % (n_pass, n_fail, len(results)))

    # ── §2 穷尽重扫：工作树里 GT 会议句命中必须为 0 ─────────────
    r = subprocess.run(['git', '-C', REPO, 'ls-files'], capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    tracked = [x for x in r.stdout.splitlines() if x.strip()]
    skip_suffix = ('.transcript.txt', '.mt.txt', '.tts.jsonl')
    doc_files = []
    for rel in tracked:
        if os.path.splitext(rel)[1].lower() not in ('.md', '.json', '.txt'):
            continue
        if rel.endswith(skip_suffix):
            continue
        doc_files.append(rel)

    residual = {}
    for rel in doc_files:
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        hh = []
        for i, line in enumerate(t.splitlines(), 1):
            for s in sentences(line):
                n = norm(s)
                if len(n) >= gt['min_len'] and n in sents:
                    hh.append({'line': i, 'text': s[:120]})
                    break
        if hh:
            residual[rel] = hh
    log('§2 穷尽重扫：仍命中 %d 个文件' % len(residual))
    for rel in sorted(residual):
        log('   %s（%d 处）' % (rel, len(residual[rel])))

    # ── §3 反证组：把一处占位改回原句 ⇒ 重放法必须 FAIL ──────────
    log('\n§3 反证组')
    counter = {'ok': False, 'detail': ''}
    target = next((c for c in results if c['verdict'] == 'PASS'), None)
    if target:
        rel = target['file']
        p = os.path.join(REPO, rel.replace('/', os.sep))
        orig = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        before = git_show_bytes(rel).decode('utf-8', 'replace')
        expected, _ = apply_transform(before, idx_map, gt['min_len'])
        # 把**第一个**占位换成一段真会议句（从 GT 里挑一条最长的）
        inj = max(sents, key=len)
        bad = PLACEHOLDER.sub(inj, orig, count=1)
        ok_fail = (bad.encode('utf-8') != expected.encode('utf-8'))
        counter = {'ok': bool(ok_fail),
                   'detail': '注入真会议句后 expected!=actual（须 FAIL）=%s' % ok_fail,
                   'file': rel, 'injected_norm_len': len(inj)}
        log('   反证：%s' % counter['detail'])

    verdict = 'PASS' if (n_fail == 0 and len(residual) == 0 and counter['ok']) else 'FAIL'
    out = {
        'script': '_app249_replay_desen.py',
        'method': '重放法：apply_transform(HEAD:F) 与工作树 F 逐字节相等 '
                  '+ §2 穷尽重扫 + §3 反证组',
        'why_new_method': '§248 引用的 app155_desens_verify.json verdict=FAIL，'
                          '但其 §1 判据靠 find 定位（短片段多处出现即错位）⇒ 先怀疑判据',
        'n_gt_sentences': len(sents),
        'n_files': len(results),
        'n_pass': n_pass, 'n_fail': n_fail,
        'n_residual_files': len(residual), 'residual': residual,
        'counterexample': counter,
        'results': results,
        'verdict': verdict,
    }
    tmp = OUTJSON + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUTJSON)
    log('\n结论：%s' % verdict)
    log('证据 → %s' % OUTJSON)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
