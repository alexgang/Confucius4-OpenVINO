#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app248 — 把**开发树**的改动刷进影子包 `shared/app067_shadow`（零拷贝、安全）。

## 为什么需要（APP-054⑤ + APP-067）
> 不许在用户正在测试的安装目录里原地改文件 ⇒ 代码只在开发目录改 ⇒
> 验证必须在**影子包**上做。

🔴 **本脚本的三条硬纪律**：
1. **只改影子包**；真包 `Confucius4_LiveCaption_v2.2` **一个字节都不动**
   ⇒ 脚本**先记真包 SHA**、**后记真包 SHA**，不一致就报错。
2. 影子包里与真包同名的文件是**硬链接** ⇒ 覆写前**先 `os.remove`**
   （删链接不删真包）⇒ **绝不会回写真包**。
3. 改完**逐字节复核**：影子包 app/ 的每个 .py 必须与开发树一致。

## 刷哪些文件
* `live_caption/`（开发树 App 代码）里**与影子包不同**的 .py
* ASR 侧 `scripts/` 的 4 个交付文件（ASR-045 后）
* 5 s 静态 seg IR（`fp16-w5/`）—— 变了才刷

## 用法
```
python results/app/_app248_refresh_shadow.py
python results/app/_app248_refresh_shadow.py --dry-run
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
SHADOW = os.path.join(HOME, 'shared', 'app067_shadow')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.2')
DEV = os.path.join(REPO, 'live_caption')
ASR_SCRIPTS = os.path.join(HOME, 'qwen3asr_06b', 'scripts')
ASR_MODELS = os.path.join(HOME, 'qwen3asr_06b', 'models')

ASR_FILES = ('asr052_speaker_tracker_api.py', 'asr052_spk_runtime.py',
             'asr_thread_defaults.py', 'asr_spk_window.py')
W5_SRC = os.path.join(ASR_MODELS, 'pyannote_seg', 'ov-fp16-w5')
W5_FILES = ('pyannote_seg_3_0_w5.xml', 'pyannote_seg_3_0_w5.bin')
W5_DST_REL = os.path.join('models', 'spk', 'pyannote_seg_3_0', 'fp16-w5')

OUT_JSON = os.path.join(HERE, 'app248_shadow_refresh_evidence.json')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def pkg_fingerprint(root):
    """真包的「app/*.py + 顶层文件」指纹（用来证明真包没被动过）。"""
    fp = {}
    app = os.path.join(root, 'app')
    if os.path.isdir(app):
        for dirpath, _dirs, files in os.walk(app):
            for fn in files:
                if fn.endswith('.py'):
                    p = os.path.join(dirpath, fn)
                    fp[os.path.relpath(p, root)] = sha256(p)
    for fn in sorted(os.listdir(root)):
        p = os.path.join(root, fn)
        if os.path.isfile(p):
            fp[fn] = sha256(p)
    return fp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': '_app248_refresh_shadow.py',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'shadow': SHADOW, 'real_pkg': PKG, 'dev': DEV,
           'dry_run': bool(args.dry_run), 'actions': [], 'checks': []}

    def chk(name, cond, detail=''):
        out['checks'].append({'name': name, 'ok': bool(cond), 'detail': detail})
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                               (' —— %s' % detail) if detail else ''))
        return bool(cond)

    if not os.path.isdir(SHADOW):
        print('!! 影子包不存在：%s（先跑 _app240_build_app067_shadow.py）' % SHADOW)
        return 2

    before = pkg_fingerprint(PKG)
    print('真包指纹（%d 个文件）已记录' % len(before))

    # ── ① App 代码：影子包 vs 开发树 ───────────────────────────
    sh_app = os.path.join(SHADOW, 'app')
    n_copied = 0
    for fn in sorted(os.listdir(DEV)):
        if not fn.endswith('.py'):
            continue
        src = os.path.join(DEV, fn)
        dst = os.path.join(sh_app, fn)
        if not os.path.isfile(dst):
            continue                      # 影子包里没有这个模块 ⇒ 不加
        s_sha, d_sha = sha256(src), sha256(dst)
        if s_sha == d_sha:
            continue
        rec = {'rel': os.path.join('app', fn), 'src': src, 'dst': dst,
               'old_sha': d_sha, 'new_sha': s_sha,
               'old_bytes': os.path.getsize(dst),
               'new_bytes': os.path.getsize(src),
               'action': 'copy'}
        if not args.dry_run:
            os.remove(dst)               # 🔴 先删硬链接（真包不受影响）
            shutil.copy2(src, dst)       # 🔴 再放真副本
        rec['done'] = not args.dry_run
        out['actions'].append(rec)
        n_copied += 1
        print('  刷新 app/%-24s %8d → %8d B  sha %s → %s'
              % (fn, rec['old_bytes'], rec['new_bytes'],
                 d_sha[:10], s_sha[:10]))
    print('App 代码刷新 %d 个文件' % n_copied)

    # ── ② ASR 侧 4 个交付文件 ─────────────────────────────────
    asr_dst = os.path.join(sh_app, 'asr_spk')
    os.makedirs(asr_dst, exist_ok=True)
    for fn in ASR_FILES:
        src = os.path.join(ASR_SCRIPTS, fn)
        dst = os.path.join(asr_dst, fn)
        if not os.path.isfile(src):
            chk('ASR 侧缺 %s' % fn, False, src)
            continue
        s_sha, d_sha = sha256(src), (sha256(dst) if os.path.isfile(dst) else '')
        if s_sha == d_sha:
            continue
        rec = {'rel': os.path.join('app', 'asr_spk', fn), 'src': src, 'dst': dst,
               'old_sha': d_sha, 'new_sha': s_sha, 'action': 'copy'}
        if not args.dry_run:
            if os.path.exists(dst):
                os.remove(dst)
            shutil.copy2(src, dst)
        rec['done'] = not args.dry_run
        out['actions'].append(rec)
        print('  刷新 app/asr_spk/%-30s sha %s → %s'
              % (fn, (d_sha or '-')[:10], s_sha[:10]))

    # ── ③ 5 s 静态 seg IR ─────────────────────────────────────
    w5_dst = os.path.join(SHADOW, W5_DST_REL)
    for fn in W5_FILES:
        src = os.path.join(W5_SRC, fn)
        dst = os.path.join(w5_dst, fn)
        if not os.path.isfile(src):
            chk('ASR 侧缺 5 s IR：%s' % src, False)
            continue
        s_sha, d_sha = sha256(src), (sha256(dst) if os.path.isfile(dst) else '')
        if s_sha == d_sha:
            continue
        rec = {'rel': os.path.join(W5_DST_REL, fn), 'src': src, 'dst': dst,
               'old_sha': d_sha, 'new_sha': s_sha, 'action': 'copy'}
        if not args.dry_run:
            if os.path.exists(dst):
                os.remove(dst)
            shutil.copy2(src, dst)
        rec['done'] = not args.dry_run
        out['actions'].append(rec)
        print('  刷新 %s sha %s → %s' % (W5_DST_REL, (d_sha or '-')[:10], s_sha[:10]))

    # ── ④ 复核：影子包 app/ == 开发树 ─────────────────────────
    if not args.dry_run:
        n_diff = 0
        for fn in sorted(os.listdir(DEV)):
            if not fn.endswith('.py'):
                continue
            dst = os.path.join(sh_app, fn)
            if not os.path.isfile(dst):
                continue
            if sha256(os.path.join(DEV, fn)) != sha256(dst):
                n_diff += 1
                print('  !! 仍不一致：app/%s' % fn)
        chk('影子包 app/ 与开发树逐字节一致（0 差异）', n_diff == 0,
            '差异 %d 个' % n_diff)

        # ── ⑤ 复核：**真包一个字节都没动** ──────────────────────
        after = pkg_fingerprint(PKG)
        same = (before == after)
        chk('真包 %s 未被改动（前后指纹一致）' % os.path.basename(PKG), same,
            '前 %d 文件 / 后 %d 文件' % (len(before), len(after)))
        out['real_pkg_fp_before_n'] = len(before)
        out['real_pkg_fp_after_n'] = len(after)
        out['real_pkg_unchanged'] = same
        out['real_pkg_changed_files'] = sorted(
            set(before) ^ set(after)) if not same else []

        # ── ⑥ 特征串：证明影子包里是**本轮**的代码 ───────────────
        feats = [(os.path.join('app', 'tts_worker.py'), '_pending_spk_voice',
                  'APP-067 ①(a) worker 加载期排队'),
                 (os.path.join('app', 'live_caption_app.py'),
                  '_sync_mt_combo_to_gpu0', 'APP-067 ③ combo 同步 GPU.0'),
                 (os.path.join('app', 'live_caption_app.py'),
                  '_fit_status_light_width', 'APP-067 ④ 按钮按像素定宽'),
                 (os.path.join('app', 'live_caption_app.py'),
                  '_spk_seg_info', 'APP-067 ② 逐段段表（新）'),
                 (os.path.join('app', 'asr_spk', 'asr_spk_window.py'),
                  'WIN_S_DEFAULT = 5.0', 'ASR-045 唯一事实来源 5 s')]
        for rel, feat, desc in feats:
            p = os.path.join(SHADOW, rel)
            hit = False
            if os.path.isfile(p):
                hit = feat in open(p, 'rb').read().decode('utf-8', 'replace')
            chk('影子包含特征串（%s）' % desc, hit, rel)

    out['verdict'] = 'PASS' if all(c['ok'] for c in out['checks']) else 'FAIL'
    if not args.dry_run:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[evidence] %s' % args.out)
    print('verdict =', out['verdict'])
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
