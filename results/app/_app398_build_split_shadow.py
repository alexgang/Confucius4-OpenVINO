# -*- coding: utf-8 -*-
"""APP-093 §3.6 补做：**换人切段 开/关 的 ASR RTF 对照** —— 影子包构建（只读探针）。

🔴 **纪律**
* 只在**影子包**（`C:\\Users\\Trekker-PTL\\_app_shadow\\after_split`）里加探针；
  **开发树 `live_caption\\` 一字不改**（本脚本只读它）。
* 探针 = **只加日志 + 一个 env 门控的提前返回**；**不改任何判定/阈值/默认值**。
* 探针 diff 落盘 ⇒ reviewer 可逐行核对「没有改判据」。

🔴 **为什么需要探针**：App 里「换人切段」只有**克隆模式**这一个总闸
（`live_caption_app.py:7538` `if _want_clone and (_t1-_t0) >= 3.2: request_split(...)`）
⇒ 没有独立的「切段开关」⇒ 严格 A/B 只能靠探针把 `request_split` 置空
（env `LIVECAP_PROBE_NOSPLIT=1`）⇒ **其余一切完全相同**。

影子包构成：
* `app/`  ← `_app_shadow/after2/app`（APP-097 设备验收跑过的基线）
* `app/live_caption_app.py` ← **开发树 HEAD**（含 GUI 布局搬移修复）
* `app/clone_voice.py` ← **开发树 HEAD** + 探针
* `models/`、`python/` → `Confucius4_LiveCaption_v2.4`（目录联接，零拷贝）
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
DEV = os.path.join(REPO, 'live_caption')
EVID = os.path.join(REPO, 'results', 'app')
SHADOW_BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SRC_SHADOW = os.path.join(SHADOW_BASE, 'after2')
DST_SHADOW = os.path.join(SHADOW_BASE, 'after_split')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4'
OUT_JSON = os.path.join(EVID, 'app398_build_split_shadow.json')
OUT_DIFF = os.path.join(EVID, 'app398_probe_patch.diff')

# ── 探针补丁（3 处；每处「唯一命中断言」）────────────────────────────
PROBES = [
    # ① request_split：计数 + env 门控提前返回（严格 A/B 的「切段关」）
    (
        """            arr = np.asarray(buf, dtype=np.float32).reshape(-1)
            if arr.size == 0 or not segs:
                return False
""",
        """            arr = np.asarray(buf, dtype=np.float32).reshape(-1)
            if arr.size == 0 or not segs:
                return False
            # 🔬 [PROBE-ONLY·APP-093 §3.6] 只读计数 + env 门控提前返回。
            #    **不改任何判定/阈值** ⇒ 两臂的其余代码路径完全一致。
            _probe_nosplit = (os.environ.get('LIVECAP_PROBE_NOSPLIT', '0')
                              .strip() == '1')
            with self._lock:
                self._probe_req = getattr(self, '_probe_req', 0) + 1
                if _probe_nosplit:
                    self._probe_suppressed = getattr(self, '_probe_suppressed', 0) + 1
            self._log('[split-probe] request seg=%s dur=%.2f suppressed=%s'
                      % (int(seg), arr.size / float(SR), _probe_nosplit))
            if _probe_nosplit:
                return False
""",
    ),
    # ② split_by_speaker：记录质心数与「因质心不足直接返回」的事实
    (
        """        cents = self._split_centroids()
        if len(cents) < 2:
            return segs
""",
        """        cents = self._split_centroids()
        if len(cents) < 2:
            # 🔬 [PROBE-ONLY·APP-093 §3.6] 只记事实，不改判定。
            self._log('[split-probe] bail n_cents=%d (<2) => 不切段' % len(cents))
            return segs
""",
    ),
    # ③ _split_worker：记录每段切分结果 + 编码器是否就绪
    (
        """                parts = self.split_by_speaker(piece, rngs)
                n_parts = len(parts)
""",
        """                parts = self.split_by_speaker(piece, rngs)
                n_parts = len(parts)
                # 🔬 [PROBE-ONLY·APP-093 §3.6] 只记事实。
                self._log('[split-probe] done seg=%s n_parts=%d n_cents=%d '
                          'enc_ready=%s' % (int(seg), n_parts, len(self._cents),
                                            self._split_enc is not None))
""",
    ),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: str) -> str:
    return sha256_bytes(open(p, 'rb').read())


def now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def junction(link: str, target: str) -> str:
    """建目录联接（零拷贝；不需要管理员权限）。"""
    if os.path.islink(link) or os.path.isdir(link):
        return 'exists'
    os.makedirs(os.path.dirname(link), exist_ok=True)
    rc = subprocess.run(['cmd', '/c', 'mklink', '/J', link, target],
                        capture_output=True, text=True)
    if rc.returncode != 0:
        os.symlink(target, link, target_is_directory=True)
        return 'symlink'
    return 'junction'


def main() -> int:
    rep = {'created_at': now(), 'dst_shadow': DST_SHADOW}

    # ① 目标目录（已存在 ⇒ 改名保留，不删）
    if os.path.exists(DST_SHADOW):
        old = DST_SHADOW + '.old_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        os.rename(DST_SHADOW, old)
        rep['renamed_old_to'] = old
    os.makedirs(DST_SHADOW, exist_ok=True)

    # ② app/ ← after2/app（**整目录拷贝的是「影子包自身」**，不是仓库⇄包同步）
    src_app = os.path.join(SRC_SHADOW, 'app')
    dst_app = os.path.join(DST_SHADOW, 'app')
    shutil.copytree(src_app, dst_app)
    rep['app_copied_from'] = src_app

    # ③ models/ + python/ ← v2.4（联接，零拷贝）
    rep['models_link'] = junction(os.path.join(DST_SHADOW, 'models'),
                                  os.path.join(PKG, 'models'))
    rep['python_link'] = junction(os.path.join(DST_SHADOW, 'python'),
                                  os.path.join(PKG, 'python'))

    # ④ app/*.py ← **开发树 HEAD 全量**（包内 30 个 .py 全部用 dev 版）
    #    🔴 起因：`after2/app/tts_service.py` **缺 `spk_voice_seg`**
    #    （dev 的 live_caption_app.py 会调它）⇒ 混用会报
    #    「'TTSService' object has no attribute 'spk_voice_seg'」⇒ self_ref 注册失效
    #    ⇒ 克隆路径没被真正跑到 ⇒ **必须全量对齐 dev**。
    dev_files = {}
    for f in sorted(os.listdir(dst_app)):
        if not f.endswith('.py'):
            continue
        src = os.path.join(DEV, f)
        if not os.path.isfile(src):
            continue
        data = open(src, 'rb').read()
        open(os.path.join(dst_app, f), 'wb').write(data)
        dev_files[f] = {'bytes': len(data), 'sha256': sha256_bytes(data)}
    rep['py_synced_from_dev'] = dev_files
    rep['n_py_synced_from_dev'] = len(dev_files)

    # ⑤ clone_voice.py ← 开发树 HEAD + 探针
    cv_path = os.path.join(DEV, 'clone_voice.py')
    cv = open(cv_path, 'rb').read()
    try:
        text = cv.decode('utf-8')
    except UnicodeDecodeError:
        text = cv.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in text else '\n'
    body = text.replace('\r\n', '\n')
    patched = body
    applied = []
    for old, new in PROBES:
        cnt = patched.count(old)
        if cnt != 1:
            print('🔴 锚点命中 %d 次（要求恰好 1 次）⇒ 中止' % cnt)
            print('---- 锚点 ----\n%s\n------------' % old)
            return 3
        patched = patched.replace(old, new, 1)
        applied.append({'anchor_lines': old.count('\n'),
                        'n_hit': cnt})
    # 行尾还原（原文件行尾风格）
    out = patched.replace('\n', nl)
    dst_cv = os.path.join(dst_app, 'clone_voice.py')
    open(dst_cv, 'wb').write(out.encode('utf-8'))
    rep['clone_voice_py'] = {
        'src': 'dev HEAD + PROBE',
        'dev_bytes': len(cv), 'dev_sha256': sha256_bytes(cv),
        'dst_bytes': len(out.encode('utf-8')),
        'dst_sha256': sha256_bytes(out.encode('utf-8')),
        'probes_applied': len(applied),
        'eol': 'CRLF' if nl == '\r\n' else 'LF',
    }

    # ⑥ 探针 diff（dev 原件 vs 影子包改后）⇒ reviewer 逐行核对
    diff = list(difflib.unified_diff(
        body.splitlines(True), patched.splitlines(True),
        fromfile='dev/live_caption/clone_voice.py',
        tofile='after_split/app/clone_voice.py', n=3))
    open(OUT_DIFF, 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    rep['probe_diff'] = {'path': OUT_DIFF, 'bytes': os.path.getsize(OUT_DIFF),
                         'sha256': sha256_file(OUT_DIFF),
                         'n_diff_lines': len(diff)}

    # ⑦ 自检：除 clone_voice.py（探针）外，其余 app/*.py 必须与 **dev HEAD** 逐字节相同
    diffs = []
    for f in sorted(os.listdir(dst_app)):
        if not f.endswith('.py'):
            continue
        a = os.path.join(DEV, f)
        b = os.path.join(dst_app, f)
        if not os.path.isfile(a):
            continue
        if sha256_file(a) != sha256_file(b):
            diffs.append(f)
    rep['py_files_differing_from_dev'] = diffs
    rep['only_probe_file_differs'] = (diffs == ['clone_voice.py'])
    # 关键接口存在性自检（APP-093 本轮踩到的坑）
    ts = open(os.path.join(dst_app, 'tts_service.py'), encoding='utf-8',
              errors='replace').read()
    rep['tts_service_has_spk_voice_seg'] = ('def spk_voice_seg' in ts)
    rep['live_caption_app_calls_spk_voice_seg'] = (
        'spk_voice_seg' in open(os.path.join(dst_app, 'live_caption_app.py'),
                                encoding='utf-8', errors='replace').read())

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items()
                      if k != 'py_synced_from_dev'}, ensure_ascii=False, indent=1))
    return 0 if (rep['only_probe_file_differs']
                 and rep['tts_service_has_spk_voice_seg']
                 and rep['live_caption_app_calls_spk_voice_seg']) else 4


if __name__ == '__main__':
    raise SystemExit(main())
