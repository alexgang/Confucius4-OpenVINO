#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119 复跑前置：把 dev 树的 2 个运行时文件定点同步进 v2.5 客户包**。

## 为什么单独写一个脚本（不用 `_app119_sync_to_v25.py`）

`_app119_sync_to_v25.py` 的 README 步骤是**「精确字符串替换 + 唯一命中断言」**
⇒ **不幂等**：01:57 那轮已经把锚点消费掉了，再跑会 `SystemExit('锚点命中 0 次')`
⇒ **fail-closed**（好现象，但会挡住本次只改 .py 的同步）。

⇒ 本脚本**只同步 2 个运行时 .py**（README 本轮**不需要**再改：
   上一轮已改到位，且本轮改动只涉及**加载顺序**，README 里
   「翻译模型在 ASR 就绪后加载」等表述仍准确 ⇒ **不动 README**）。

## 本轮 dev → pkg 的实际改动（唯一一处）

**APP-113 §2 的「ASR/TTS 并行加载」判定**：
`TTS 档位 == CUDA`（写死）⇒ 改成 **「ASR 与 TTS 是否同一张加速卡」**
（`_same_accel()`）。

🔴 根因：APP-119 §1 把完整版**出厂默认**改成 `TTS = NPU`，
   而默认 `ASR = GPU.0` ⇒ **两者本来就是异卡**，
   但旧规则只认「TTS 是不是 CUDA」⇒ **默认配置被静默地永远串行**
   ⇒ **默认配置白丢 APP-113 §2 的并行收益**（验收臂实证：唯一 FAIL 项）。

## 纪律

  * 写盘：**临时文件 → os.replace**（原子）；
  * 写前 `ast.parse` 语法自检、**写后**再 `ast.parse` ＋ 逐字节复核；
  * 证据落盘：``results/app/app119_sync_v25_evidence_r2.json``
    （SHA256 / 字节数 / mtime / 文件数）；
  * **不打 zip**（APP-119 §3）、**不碰** v2.4 / rc11 / sp5。
"""
import ast
import datetime
import hashlib
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEV = os.path.join(REPO, 'live_caption')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
PKG_APP = os.path.join(PKG, 'app')
OUT = os.path.join(HERE, 'app119_sync_v25_evidence_r2.json')

RUNTIME_PY = ['device_config.py', 'live_caption_app.py']


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix='_app119_sync_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def count_files(root):
    n = 0
    for _dp, _dn, _fn in os.walk(root):
        n += len(_fn)
    return n


def main():
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'app': 'APP-119', 'pkg': PKG, 'phase': 'r2（仅运行时 .py；README 本轮不改）',
           'py_files': [], 'readme': [], 'errors': []}
    if not os.path.isdir(PKG_APP):
        print('FAIL: 包目录不存在 %s' % PKG_APP)
        return 2

    for name in RUNTIME_PY:
        src = os.path.join(DEV, name)
        dst = os.path.join(PKG_APP, name)
        if not os.path.isfile(src):
            rep['errors'].append('dev 缺 %s' % name)
            continue
        data = open(src, 'rb').read()
        before = (sha256_bytes(open(dst, 'rb').read())
                  if os.path.isfile(dst) else None)
        ast.parse(data.decode('utf-8'))            # 写前语法自检
        write_atomic(dst, data)
        back = open(dst, 'rb').read()
        ok = (back == data) and (sha256_bytes(back) == sha256_bytes(data))
        ast.parse(back.decode('utf-8'))            # 写后语法自检
        st = os.stat(dst)
        rep['py_files'].append({
            'name': name,
            'dev_sha256': sha256_bytes(data),
            'pkg_sha256': sha256_bytes(back),
            'pkg_sha256_before': before,
            'changed': before != sha256_bytes(back),
            'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(
                st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'identical_to_dev': ok,
            'ast_ok': True,
        })
        print('  %-22s → %d B  sha=%s  %s'
              % (name, st.st_size, sha256_bytes(back)[:16],
                 'OK' if ok else 'FAIL'))
        if not ok:
            rep['errors'].append('%s 写后复核不一致' % name)

    # README **只读核对**：APP-119 的关键口径仍在（不写）
    for path, needles in (
            (os.path.join(PKG, 'README_zh.md'),
             ['出厂默认（APP-119 §1）', '取消', '自动迁移']),
            (os.path.join(PKG, 'README_en.md'),
             ['Factory default (APP-119 §1)', 'migrated automatically'])):
        b = open(path, 'rb').read()
        t = b.decode('utf-8')
        st = os.stat(path)
        rep['readme'].append({
            'name': os.path.basename(path),
            'read_only': True,
            'needles_ok': all((n in t) for n in needles),
            'bytes': st.st_size,
            'mtime': datetime.datetime.fromtimestamp(
                st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'sha256': sha256_bytes(b),
        })
        print('  README %s（只读核对）needles_ok=%s'
              % (os.path.basename(path), rep['readme'][-1]['needles_ok']))

    rep['pkg_file_count'] = count_files(PKG)
    rep['result'] = 'PASS' if not rep['errors'] else 'FAIL'
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('RESULT=%s  包文件数=%d  证据=%s'
          % (rep['result'], rep['pkg_file_count'], OUT))
    return 0 if rep['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
