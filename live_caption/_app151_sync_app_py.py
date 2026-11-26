"""APP-151 第 1 项：**候选目录 `app\\*.py` 整体从 dev 树同步**。

## 现状（实测）

候选 `app/` 的 34 个 .py 里，只有 **2 个**与 dev 树不同：

| 文件 | 方向 | 原因 |
|---|---|---|
| `translator.py` | **候选 ← dev** | ★ 候选是 11-20 旧版（96 701 B）⇒ 只认 mt2 ⇒ **GUI 的 MT 下拉 0 项**（APP-151 的阻断点） |
| `tts_engine_patch.py` | **dev ← 候选** | 本轮 APP-139 加的 turbo 注入**只写进了候选**（dev 树还没有）⇒ 反向同步 |

其余 32 个**逐字节相同**。

## 纪律

* 逐文件：写前备份 ＋ 写后**逐字节复核** ＋ `ast.parse`；
* **只同步生产文件**（候选 app/ 里实际有的 34 个）⇒ 不把 400+ 个开发辅助脚本带进包；
* 同步后**列出差异清单**（应为 0，除标注的两个反向同步）。
"""
import ast
import hashlib
import json
import sys
import io
import os
import shutil
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\app'
TAG = 'app151'
OUT = os.path.join(REPO, 'results', 'app', 'app151_app_py_sync.json')

#: 反向同步（dev ← 候选）：本轮 APP-139 的 turbo 注入只写进了候选
REVERSE = {'tts_engine_patch.py'}

rows = []


def sha(b):
    return hashlib.sha256(b).hexdigest()


def copy_checked(src, dst, label):
    sb = open(src, 'rb').read()
    db = open(dst, 'rb').read() if os.path.exists(dst) else None
    if db == sb:
        return {'label': label, 'src': src, 'dst': dst, 'status': 'already_identical',
                'sha256': sha(sb), 'bytes': len(sb)}
    bak = dst + '.bak_' + TAG
    if not os.path.exists(bak):
        shutil.copy2(dst, bak)
    ast.parse(sb.decode('utf-8'))          # 写前先确认语法
    tmp = dst + '.tmp_' + TAG
    with open(tmp, 'wb') as f:
        f.write(sb)
    os.replace(tmp, dst)
    after = open(dst, 'rb').read()
    assert after == sb, '写后逐字节复核失败：%s' % dst
    ast.parse(after.decode('utf-8'))
    return {'label': label, 'src': src, 'dst': dst, 'status': 'updated',
            'old_sha256': sha(db) if db is not None else None,
            'new_sha256': sha(sb), 'old_bytes': len(db) if db is not None else 0,
            'new_bytes': len(sb), 'backup': bak,
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S')}


def main():
    cand_py = sorted(f for f in os.listdir(CAND) if f.endswith('.py'))
    print('候选 app/*.py：%d 个' % len(cand_py))

    # ① 正向：候选 ← dev（生产文件全集）
    for f in cand_py:
        dp = os.path.join(DEV, f)
        if not os.path.exists(dp):
            rows.append({'label': f, 'status': 'dev_missing'})
            continue
        if f in REVERSE:
            continue
        r = copy_checked(dp, os.path.join(CAND, f), '候选←dev  %s' % f)
        rows.append(r)
        if r['status'] == 'updated':
            print('  [更新] %-34s %d → %d B' % (f, r['old_bytes'], r['new_bytes']))

    # ② 反向：dev ← 候选
    for f in REVERSE:
        r = copy_checked(os.path.join(CAND, f), os.path.join(DEV, f), 'dev←候选  %s' % f)
        rows.append(r)
        print('  [反向] %-34s %s' % (f, r['status']))

    # ③ 复核：候选 app/*.py 与 dev 树的差异清单（应为 0）
    diffs = []
    for f in cand_py:
        dp = os.path.join(DEV, f)
        cp = os.path.join(CAND, f)
        if not os.path.exists(dp):
            diffs.append((f, 'dev 缺失'))
            continue
        a = open(dp, 'rb').read()
        b = open(cp, 'rb').read()
        if a != b:
            diffs.append((f, '内容不同'))
    print('\n★ 同步后差异清单（应为 0）：%d 项' % len(diffs))
    for f, why in diffs:
        print('   %-34s %s' % (f, why))

    # ④ translator.py 的 mt3 引用（APP-151 的验收点）
    t = io.open(os.path.join(CAND, 'translator.py'), encoding='utf-8').read()
    mt3_lines = [i + 1 for i, ln in enumerate(t.splitlines()) if 'mt3' in ln]
    print('\ntranslator.py 里含 "mt3" 的行号：%s（共 %d 行）'
          % (mt3_lines[:10], len(mt3_lines)))
    print('translator.py mtime = %s' % time.strftime('%Y-%m-%d %H:%M:%S',
                                                time.localtime(
                                                    os.path.getmtime(
                                                        os.path.join(CAND, 'translator.py')))))

    out = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'candidate_app_py_count': len(cand_py),
           'rows': rows,
           'remaining_diffs': [{'file': f, 'why': w} for f, w in diffs],
           'translator_mt3_lines': mt3_lines,
           'translator_mt3_line_count': len(mt3_lines)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print('\n落盘 ->', OUT)
    return 0 if not diffs else 1


if __name__ == '__main__':
    sys.exit(main())
