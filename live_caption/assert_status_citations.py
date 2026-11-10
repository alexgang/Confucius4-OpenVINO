# -*- coding: utf-8 -*-
"""
App 模块 · 静态闸门 A：**STATUS 引用产物路径必须能在磁盘上定位**

为什么需要它
------------
reviewer 在 APP-093 ②(d) 抓到过「§162 引用的 `app391_app089_before_and_overload.json`
**磁盘不存在**（幻影产物）」，并要求「以后验收判据失败，必须在 STATUS 里明写 FAIL」。
⇒ **STATUS 里写的每一条产物路径都必须是真能打开的文件**，否则 reviewer 复核时
会把它当成又一次「引用的证据不存在」。

本闸门做三件事
--------------
① 扫 `status/app/STATUS_APP.md`（**活文档＝reviewer 实际读的那份**）
   ＋ `status/archive/` 下全部 STATUS 归档件，把正文里反引号包裹的、
   看起来是仓库内相对路径的引用抽出来；
② 逐条在 **仓库根 / `shared/` 根（父目录）** 里定位；
③ 把「定位不到」的分成三类分开报，**不混为一谈**：
   - `known_phantom` —— reviewer 已点名、且已在 STATUS 里如实撤回的（app391）；
   - `placeholder`  —— 含 `*` / `…` / `{a,b}` / `XX` 等，**本来就不是具体路径**；
   - `bad`          —— 其余：**真正指不到文件的具体引用**。

判定口径（**与「归档件是冻结的历史记录」相容**）
------------------------------------------------
* **硬闸门 = 活文档 `status/app/STATUS_APP.md`**：一条坏引用都不许有 ⇒ 有则 FAIL。
  （reviewer 点名过的 APP-093 ②(d)「STATUS 引用的 app391 json 不存在」就是活文档里的坏引用。）
* **归档件只做报告、不参与判 FAIL**：归档件是**逐字冻结**的历史正文
  （按 APP-052④「旧正文一字不删」＋「归档件逐字命中」自检，改它会破坏自检），
  所以其中的旧笔误**只登记、不改写**；要改必须在 STATUS 里**新开一节**说明并请 reviewer 裁定。
  ⇒ 归档件里的坏引用进 `archive_findings`（信息项），**不进 FAIL 口径**。

用法（纯 CPU / 静态 / 不占 GPU·NPU / 不需要 MACHINE_LOCK）：
    python live_caption/assert_status_citations.py
    python live_caption/assert_status_citations.py --json results/app/status_citations_sweep_20261110.json

退出码：0 = PASS（活文档无坏引用）；2 = FAIL（活文档有坏引用）。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
PARENT = os.path.dirname(REPO)
SHARED = os.path.join(PARENT, 'shared')

EXT_RE = re.compile(r'\.(json|jsonl|py|md|log|diff|png|txt|csv|wav|pid|patch|yaml|yml|tsv)$', re.I)
PREFIXES = ('results/', 'live_caption/', 'status/', 'shared/', 'reports/', 'scripts/')
# 占位/通配 ⇒ 本来就不是具体路径，不算坏引用
PLACEHOLDER_RE = re.compile(r'(\*|\u2026|\.\.\.|\{[^}]*\}|<[^>]+>|\bXX\b|placeholder)', re.I)
ABSPATH_RE = re.compile(r'^[A-Za-z]:[\\/]')

# reviewer 在 APP-093 ②(d) 点名、且 §164 已如实撤回的幻影产物 ⇒ 单列，不算新缺陷
KNOWN_PHANTOM = {
    'results/app/app391_app089_before_and_overload.json':
        'APP-093 ②(d)：§162 幻影引用；§164 已撤回该引用并改列 app393/app394',
}

# 归档件/历史节里出现的**其它模块**路径与包内相对路径 ⇒ 不在 App 的仓库树里，
# 用「basename 全盘定位」兜一次，仍然找不到就归为「外部路径（不在本仓库树）」。
EXTERNAL_PREFIX_HINT = ('scripts/',)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def candidate_roots(rel):
    out = [os.path.join(REPO, rel)]
    if rel.startswith('shared/'):
        out.append(os.path.join(PARENT, rel))
    return out


def basename_index():
    """按 basename 建索引（用于「同名的文件在别处」提示）。"""
    idx = {}
    for base in (REPO, PARENT):
        for dirpath, dirnames, filenames in os.walk(base):
            # 不扫巨���目录
            dirnames[:] = [d for d in dirnames
                           if d not in ('.git', '__pycache__', 'node_modules', '.venv', 'venv')]
            for fn in filenames:
                idx.setdefault(fn, []).append(os.path.join(dirpath, fn))
    return idx


def collect(text):
    cited = {}
    for m in re.finditer(r'`([^`\n]+)`', text):
        p = m.group(1).strip()
        if not EXT_RE.search(p):
            continue
        if not p.startswith(PREFIXES):
            continue
        cited[p] = cited.get(p, 0) + 1
    return cited


def _is_documented_correction(text, bad_path, actual_rel):
    """该「坏引用」所在行**同时给出了正确路径** ⇒ 属**已如实记录的**错误引用。

    场景：STATUS 里写「引用了 X（不存在），真实路径是 Y」—— 这**不是**「引用了一个
    找不到的证据」，而是**如实记录了一个错误引用**（reviewer 需要看到的就是这段）。
    ⇒ 归入 `documented`（**不判 FAIL**），但仍**登记在册**，让 reviewer 能看到。

    🔴 反证（判据须有鉴别力）：若该行**没有**给出正确路径 ⇒ 仍是 `bad`。
    """
    for line in text.split('\n'):
        if bad_path in line:
            for a in actual_rel:
                if a and a in line:
                    return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=os.path.join('results', 'app',
                                                    'status_citations_sweep_%s.json'
                                                    % datetime.date.today().strftime('%Y%m%d')))
    args = ap.parse_args()

    status_abs = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
    arch_dir = os.path.join(REPO, 'status', 'archive')
    arch_files = []
    if os.path.isdir(arch_dir):
        for fn in sorted(os.listdir(arch_dir)):
            fp = os.path.join(arch_dir, fn)
            if os.path.isfile(fp) and fn.startswith('STATUS_APP'):
                arch_files.append(fp)

    idx = basename_index()

    def scan(file_list):
        """返回 (per_file, ok, bad, known, placeholder, abs_paths, external, documented)。"""
        per_file = []
        ok, bad, known, placeholder, abs_paths, external = [], [], [], [], [], []
        documented = []
        for fp in file_list:
            raw = open(fp, 'rb').read()
            text = raw.decode('utf-8', errors='replace')
            cited = collect(text)
            pf = {'file': os.path.relpath(fp, REPO).replace('\\', '/'),
                  'bytes': len(raw), 'sha256': sha256_of(fp), 'n_cited': len(cited)}
            f_bad = []
            for p in sorted(cited):
                norm = p.replace('\\', '/')
                if ABSPATH_RE.match(norm):
                    abs_paths.append(p)
                    continue
                if PLACEHOLDER_RE.search(norm):
                    placeholder.append(p)
                    continue
                if any(os.path.exists(c) for c in candidate_roots(norm)):
                    ok.append(p)
                    continue
                if norm in KNOWN_PHANTOM:
                    known.append({'path': p, 'note': KNOWN_PHANTOM[norm],
                                  'file': pf['file']})
                    continue
                hits = idx.get(os.path.basename(norm), [])
                in_repo = [h for h in hits if h.lower().startswith(REPO.lower())]
                if in_repo:
                    actual_rel = [os.path.relpath(h, REPO).replace('\\', '/')
                                  for h in in_repo[:3]]
                    item = {'path': p, 'note': '同名文件在别处', 'file': pf['file'],
                            'actual': actual_rel}
                    if _is_documented_correction(text, p, actual_rel):
                        item['note'] = ('同名文件在别处（**同一行已给出正确路径 '
                                        '⇒ 属「已如实记录的错误引用」**）')
                        documented.append(item)
                    else:
                        bad.append(item)
                        f_bad.append(p)
                elif hits:
                    external.append({'path': p,
                                     'note': '在仓库树之外（如客户包 / 其它模块目录）',
                                     'file': pf['file'], 'actual': hits[:3]})
                else:
                    bad.append({'path': p, 'note': '磁盘上找不到', 'file': pf['file'],
                                'actual': []})
                    f_bad.append(p)
            pf['n_bad'] = len(f_bad)
            pf['bad'] = f_bad
            per_file.append(pf)
        return (per_file, ok, bad, known, placeholder, abs_paths, external, documented)

    (live_pf, live_ok, live_bad, live_known, live_ph, live_abs, live_ext,
     live_doc) = scan([status_abs])
    (arch_pf, arch_ok, arch_bad, arch_known, arch_ph, arch_abs, arch_ext,
     arch_doc) = scan(arch_files)

    out = {
        'created_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'criterion': (
            '硬闸门 = 活文档 status/app/STATUS_APP.md：反引号包裹的仓库内相对路径引用必须能在 '
            '仓库根 / shared 根 上定位到；含通配或占位的引用不计；'
            'reviewer 已点名并撤回的幻影单列 known_phantom。'
            '归档件是逐字冻结的历史正文 ⇒ 其中的旧笔误只登记进 archive_findings，不判 FAIL、'
            '也不改写（按「只追加」纪律需在新节说明并请 reviewer 裁定）。'
        ),
        'device_job': False,
        'lock_note': '纯 CPU 静态检查（不加载模型、不占 GPU/NPU）⇒ 不需要 MACHINE_LOCK',
        'n_files_scanned': 1 + len(arch_files),
        'n_cited_unique_live': len(live_ok) + len(live_bad) + len(live_known)
                               + len(live_ph) + len(live_abs),
        'n_ok_live': len(live_ok),
        'n_bad_live': len(live_bad),
        'n_documented_live': len(live_doc),
        'documented_live': live_doc,
        'n_documented_archive': len(arch_doc),
        'n_known_phantom_live': len(live_known),
        'n_placeholder_live': len(live_ph),
        'n_abspath_live': len(live_abs),
        'n_external_outside_repo_live': len(live_ext),
        'bad_live': live_bad,
        'known_phantom_live': live_known,
        'external_outside_repo_live': live_ext,
        'n_archive_findings': len(arch_bad),
        'archive_findings': arch_bad,
        'archive_known_phantom': arch_known,
        'live_per_file': live_pf,
        'archive_per_file': arch_pf,
    }
    out['verdict'] = 'PASS' if not live_bad else 'FAIL'
    out['verdict_note'] = (
        '活文档 STATUS_APP.md 的所有具体产物引用都能在磁盘上定位'
        if not live_bad else
        '活文档存在指不到文件的具体引用 ⇒ 与 APP-093 ②(d)「引用的证据不存在」同类缺陷'
    )

    dest = args.json if os.path.isabs(args.json) else os.path.join(REPO, args.json)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, dest)

    print(json.dumps({k: out[k] for k in (
        'verdict', 'n_files_scanned', 'n_cited_unique_live', 'n_ok_live', 'n_bad_live',
        'n_known_phantom_live', 'n_placeholder_live', 'n_archive_findings')},
        ensure_ascii=False, indent=2))
    for b in live_bad:
        print('BAD(live):', b['path'], '|', b['note'], '|', b['actual'])
    for d in live_doc:
        print('DOCUMENTED(live):', d['path'], '|', d['note'], '|', d['actual'])
    print('--- archive findings (informational, not FAIL) ---')
    for b in arch_bad:
        print('  ARCH:', b['file'], '|', b['path'], '|', b['note'], '|', b['actual'][:1])
    print('WROTE:', dest)
    return 0 if not live_bad else 2


if __name__ == '__main__':
    sys.exit(main())
