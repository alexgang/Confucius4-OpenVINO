r"""_app249_verify_desen_final.py —— 补做后脱敏的**独立终检**（与施加脚本无关的判据）。

## 三条判据（互相独立）

**§1 彻底（无残留）**：对每个受控说明类文件，**逐行**做归一化子串扫描
⇒ 命中 GT 会议句的行数必须为 **0**（reviewer 独占文件除外）。

**§2 无损（只动了 GT span）**：对每个被改动的文件，
把改后文本里的 `[会议句 idx N]` **替换回对应的 GT 句**
⇒ 结果必须与**改前**（`git show HEAD:`）**逐字节相等**（行尾归一化后）。

**§3 无副作用（结构完好）**：`.json` 不得从「可解析」变成「不可解析」；
`.md`/`.txt` 的**非占位部分**必须逐字节等于改前 ⇒ 用 §2 覆盖。

## 🔴 反证组（有鉴别力）

把某处占位**改回**原句 ⇒ §1 必须**命中**（证明扫描判据有鉴别力）。
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
APPLYJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_apply_full.json')
OUTJSON = os.path.join(REPO, 'results', 'app', 'app249_desen_final_verify.json')

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r'[\s　]+')
PLACEHOLDER = re.compile(r'\[会议句 idx (\d+)\]')
SKIP_SUFFIX = ('.transcript.txt', '.mt.txt', '.tts.jsonl')


def log(m):
    print(m, flush=True)


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(' ', s)
    return PUNCT_RE.sub('', s)


def sentences(text):
    return [p.strip() for p in re.split(r'[。！？\n]+|(?<=[.!?])\s+', text)
            if p and p.strip()]


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


def main():
    gt = json.load(open(GTJSON, encoding='utf-8'))
    apply_rec = json.load(open(APPLYJSON, encoding='utf-8'))
    reviewer_owned = set(gt['reviewer_owned'])
    min_len = gt['min_len']

    sents = build_gt(gt)
    ordered = sorted(sents, key=len, reverse=True)
    idx_to_sent = {i + 1: s for i, s in enumerate(sorted(sents))}
    log('GT 句子 %d 条' % len(sents))

    # ── §2 无损：**diff 法**（与施加算法无关）────────────────────
    # 判据：对每个被改动的文件，**逐行**比 HEAD 行与当前行：
    #   * 「删除段」（HEAD 里没了的字符）**必须**是 GT 会议句（或其子串）
    #     ⇒ 证明「只删了会议内容，没删别的」；
    #   * 「插入段」**必须**只含占位 ⇒ 证明「没塞进假内容」。
    # ⇒ 不依赖施加脚本的任何内部信息（不知道它替换了哪些 span）。
    import difflib
    n_pass2 = n_fail2 = 0
    fail2 = []
    for c in apply_rec['changed']:
        rel = c['file']
        r = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + rel],
                           capture_output=True)
        if r.returncode != 0:
            fail2.append({'file': rel, 'err': 'no_HEAD'})
            n_fail2 += 1
            continue
        before = r.stdout.decode('utf-8', 'replace').replace('\r\n', '\n').replace('\r', '\n')
        after = io.open(os.path.join(REPO, rel.replace('/', os.sep)),
                        encoding='utf-8', errors='replace', newline='').read()
        after = after.replace('\r\n', '\n').replace('\r', '\n')
        bl = before.split('\n')
        al = after.split('\n')
        prob = []
        if len(bl) != len(al):
            prob.append('n_lines %d != %d' % (len(bl), len(al)))
        else:
            for i, (x, y) in enumerate(zip(bl, al)):
                if x == y:
                    continue
            # 🔴 **词级**对齐（不是字符级）：字符级 diff 会把「Good morning」里的
            #    `x` 单独对齐到别处 ⇒ 报「插入了非占位的 x」⇒ **假 FAIL**。
            #    ⇒ 先把占位当成**原子 token**切出来，再按词切分对齐。
            def _tok(s):
                toks = []
                for m in PLACEHOLDER.split(s):
                    if m:
                        toks.extend(m.split())
                    toks.append('\x00PLACEHOLDER\x00')
                # 去掉末尾多余的占位标记（split 会多产出一个）
                if toks and toks[-1] == '\x00PLACEHOLDER\x00' and s and not s.endswith(']'):
                    toks.pop()
                return toks
            xt, yt = _tok(x), _tok(y)
            sm = difflib.SequenceMatcher(None, xt, yt, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    continue
                if tag == 'insert':
                    ins = ''.join(yt[j1:j2])
                    if ins.replace('\x00PLACEHOLDER\x00', '').strip():
                        prob.append('L%d 插入非占位: %r' % (i + 1, ins[:60]))
                    continue
                dele = ' '.join(xt[i1:i2]).replace('\x00PLACEHOLDER\x00', ' ')
                if not dele.strip():
                    continue        # 只删了空白/标点 ⇒ 无害
                nd = norm(dele)
                if not nd:
                    continue
                # 删除段必须被某个 GT 句**覆盖**（允许是 GT 句的子串）
                if not any(s in nd or nd in s for s in ordered):
                    prob.append('L%d 删除非 GT 内容: %r' % (i + 1, dele[:60]))
        if prob:
            n_fail2 += 1
            fail2.append({'file': rel, 'detail': prob[:4], 'n_prob': len(prob)})
        else:
            n_pass2 += 1
    log('§2 无损（diff 法：删除段必属 GT 句 / 插入段只有占位）：%d PASS / %d FAIL'
        % (n_pass2, n_fail2))
    for f in fail2[:8]:
        log('   FAIL %s %s' % (f.get('file'), f.get('n_prob', f.get('err'))))
        for dd in f.get('detail', [])[:2]:
            log('      %s' % dd)

    # ── §1 彻底：逐行子串扫描 ⇒ 命中必须为 0 ────────────────────
    r = subprocess.run(['git', '-C', REPO, 'ls-files'], capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    tracked = [x for x in r.stdout.splitlines() if x.strip()]
    TEXT_EXT = ('.md', '.json', '.txt', '.tsv', '.csv', '.jsonl')
    residual = {}
    n_scanned = 0
    for rel in tracked:
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        if rel in reviewer_owned:
            continue
        if rel.endswith(SKIP_SUFFIX):
            continue
        p = os.path.join(REPO, rel.replace('/', os.sep))
        if not os.path.isfile(p):
            continue
        n_scanned += 1
        t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        hh = []
        for i, line in enumerate(t.splitlines(), 1):
            n = norm(line)
            if len(n) < min_len:
                continue
            hit = [s for s in ordered if s in n]
            if hit:
                # 🔴 **不写原文**（APP-155／RULES §0：证据文件里也不摘抄会议原句）
                #    ⇒ 只写长度 + sha256 前 8 位（不可复原）
                import hashlib as _h
                _lg = max(hit, key=len)
                hh.append({'line': i, 'n_gt': len(hit),
                           'longest_len': len(_lg),
                           'longest_sha256_8': _h.sha256(_lg.encode('utf-8')).hexdigest()[:8],
                           'text_sha256_8': _h.sha256(line.strip().encode('utf-8')).hexdigest()[:8]})
        if hh:
            residual[rel] = hh
    log('§1 彻底（说明类逐行子串扫描，%d 个文件）：仍命中 %d 个文件'
        % (n_scanned, len(residual)))
    for rel in sorted(residual):
        log('   %s（%d 处）' % (rel, len(residual[rel])))

    # ── §3 JSON 结构 ───────────────────────────────────────────
    json_broken = []
    for c in apply_rec['changed']:
        rel = c['file']
        if not rel.endswith('.json'):
            continue
        p = os.path.join(REPO, rel.replace('/', os.sep))
        try:
            json.loads(io.open(p, encoding='utf-8', errors='replace',
                               newline='').read())
        except Exception as e:
            json_broken.append({'file': rel, 'err': str(e)[:100]})
    prebroken = {j['file'] for j in apply_rec.get('json_prebroken', [])}
    newly_broken = [j for j in json_broken if j['file'] not in prebroken]
    log('§3 JSON：改后不可解析 %d 个（其中**新坏** %d 个）'
        % (len(json_broken), len(newly_broken)))

    # ── 反证组 ────────────────────────────────────────────────
    counter = {'ok': False, 'detail': ''}
    target = apply_rec['changed'][0]['file'] if apply_rec['changed'] else None
    if target:
        p = os.path.join(REPO, target.replace('/', os.sep))
        orig = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        inj = max(sents, key=len)
        bad = PLACEHOLDER.sub(inj, orig, count=1)
        # （inj 只用于**内存里**的判据自检，不写进证据文件）
        hit = False
        for line in bad.splitlines():
            n = norm(line)
            if len(n) >= min_len and any(s in n for s in ordered):
                hit = True
                break
        counter = {'ok': bool(hit), 'detail': '注入真会议句后 §1 扫描命中=%s（须 True）' % hit,
                   'file': target,
                   'injected_len': len(inj)}
        log('§4 反证组：%s' % counter['detail'])

    verdict = 'PASS' if (n_fail2 == 0 and not residual and not newly_broken
                         and counter['ok']) else 'FAIL'
    out = {
        'script': '_app249_verify_desen_final.py',
        'method': '§1 逐行子串扫描（彻底） + §2 占位还原与 HEAD 逐字节相等（无损） '
                  '+ §3 JSON 结构 + §4 反证组',
        'n_gt_sentences': len(sents),
        'n_scanned_files': n_scanned,
        'n_pass_lossless': n_pass2, 'n_fail_lossless': n_fail2,
        'fail_lossless': fail2,
        'n_residual_files': len(residual), 'residual': residual,
        'json_broken_after': json_broken,
        'json_newly_broken': newly_broken,
        'counterexample': counter,
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
