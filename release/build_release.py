"""build_release.py — 从**仓库**生成 EXT 发行态（APP-153 §4 ＋ APP-156 §2）。

reviewer 要求（APP-153 §4）：
「按发行流程改写成 release=true、只保留 tabCapture；白名单加一条
「manifest.liveDub.release == true」。」
APP-156 §2 追加：「打包用仓库里的发行构建脚本（`release/build_release.py`）生成。
**不要只改包里的副本**。」

用法（`--out` = 目标发行包里 `ext/` 的目录）：
    python release/build_release.py --out C:\\path\\to\\pkg\\ext

做三件事：
  1. 复制 `ext/`（桥接）→ `<out>/bridge/`；
  2. 复制 `extension/`（插件）→ `<out>/extension/`，并把 `manifest.json` 的
     `liveDub.release` 改写为 **true**、`captureModes` 收敛为 **['tabCapture']**
     （EXT-031③：release=true ⇒ 禁用整机 getDisplayMedia 回退）；
  3. 写 `<out>/release.json` = `{"release": true}`。

开发目录里 `extension/manifest.json` **保持 release=false**（EXT-031③）⇒
本脚本是**唯一**把它变成 true 的地方 ⇒ 发行包与开发目录不会混淆。
"""
import argparse
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
EXT_SRC = os.path.join(REPO, 'ext')
EXTENSION_SRC = os.path.join(REPO, 'extension')


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, text):
    data = text.encode('utf-8')
    tmp = p + '.tmp_build_release'
    with io.open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, p)
    assert open(p, 'rb').read() == data, '写后逐字节复核失败：%s' % p


def _copy_tree(src, dst):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        rel = os.path.relpath(root, src)
        out = os.path.join(dst, rel) if rel != '.' else dst
        os.makedirs(out, exist_ok=True)
        for f in files:
            if f.endswith(('.pyc', '.pyo')):
                continue
            if '.bak_' in f:
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(out, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='发行态 ext/ 的目标目录')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)

    _copy_tree(EXT_SRC, os.path.join(out, 'bridge'))
    _copy_tree(EXTENSION_SRC, os.path.join(out, 'extension'))

    mf_p = os.path.join(out, 'extension', 'manifest.json')
    mf = json.loads(_read(mf_p))
    mf.setdefault('liveDub', {})['release'] = True
    mf['liveDub']['captureModes'] = ['tabCapture']
    _write(mf_p, json.dumps(mf, ensure_ascii=False, indent=2) + '\n')

    _write(os.path.join(out, 'release.json'), json.dumps({'release': True}, indent=2) + '\n')
    print('[build_release] 发行态已生成：%s' % out)
    print('[build_release] manifest.liveDub.release=true / captureModes=[tabCapture]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
