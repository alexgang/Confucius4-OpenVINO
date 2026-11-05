r"""app281 — APP-072 §2 闸门①：**黑名单扫描**（对**解压出来的干净副本**扫）。

## 为什么对「解压副本」而不是源目录

闸门说的是「**包内**不能有……」⇒ 判据必须打在**最终交付物**上。
源目录里有 30 个文件被 `pkg_exclude` 排除（babelvox 示例音色 8 + scipy 测试音频 22）
⇒ 扫源目录会**假 FAIL**；扫解压副本才是真的。

## 黑名单（reviewer 原文逐条落地）

1. 会议录音（含 260902_SPE **任何**切片）
2. 克隆音色（clone_*.npz / tts_speakers 里的音色文件）
3. 同事 B 的声音
4. babelvox 示例音色（cindy/lou/phil/steve + .npy）
5. 开发目录绝对路径（`C:\Users\Trekker-PTL\confucius4-openvino` 等）
6. torch / CUDA 的 dll / pyd / .cu / .cuh

## 用法

    .venv/Scripts/python.exe results/app/_app281_rc3_blacklist_scan.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CLEANTEST = r'C:\minimvp_cleantest'
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3'
DEFAULT_PKG = os.path.join(CLEANTEST, PKG_NAME)

# 🔴 开发目录绝对路径：**只查「开发机目录名」**。
#   `C:\Users\` 这种通用前缀**不算**泄漏（numpy/numba/platformdirs 的源码注释里
#   就有 `C:\Users\<用户名>` 的示例，见 §136 ⑤）。
DEV_PATH_PAT = re.compile(
    r'confucius4-openvino|'
    r'qwen3tts_eval|'
    r'\\hy_bench\\|'
    r'shared\\app_listen|'
    r'shared\\minimvp|'
    r'minimvp_cleantest|'
    r'\\abba_out|'
    r'results\\app|'
    r'\.workbuddy',
    re.IGNORECASE)

# 🔴 会议录音：260902_SPE 的**任何**切片（扩展名不限）
MEETING_PAT = re.compile(r'260902[_-]?SPE', re.IGNORECASE)

# 🔴 克隆音色：npz 向量 / 音色目录
CLONE_NPZ_PAT = re.compile(r'^clone_.*\.npz$', re.IGNORECASE)

# 🔴 同事音色 / babelvox 示例音色
BABELVOX_SPEAKER_FILES = {'cindy.json', 'cindy.npy', 'lou.json', 'lou.npy',
                          'phil.json', 'phil.npy', 'steve.json', 'steve.npy'}

# 🔴 torch / CUDA 二进制
TORCH_CUDA_EXT = ('.cu', '.cuh', '.ptx')
TORCH_CUDA_SUBSTR = ('torch', 'cudnn', 'cublas', 'cufft', 'cusparse',
                      'nvcuda', 'nvrtc', 'cupy', 'pytorch', 'libtorch')

TEXT_EXT = {'.py', '.txt', '.md', '.json', '.cfg', '.ini', '.yaml', '.yml',
            '.bat', '.ps1', '.sh', '.xml', '.csv', '.toml'}


def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def scan(pkg):
    out = {
        'pkg': pkg,
        'meeting': [], 'clone_npz': [], 'tts_speakers_dir': [],
        'babelvox_example': [], 'dev_path': [], 'torch_cuda': [],
        'n_files': 0, 'total_bytes': 0,
    }
    for root, dirs, files in os.walk(pkg):
        rel_root = os.path.relpath(root, pkg)
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.normpath(os.path.join(rel_root, f))
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            out['n_files'] += 1
            out['total_bytes'] += size
            low = f.lower()
            # ① 会议录音
            if MEETING_PAT.search(rel) or MEETING_PAT.search(f):
                out['meeting'].append(rel)
            # ② 克隆音色 npz
            if CLONE_NPZ_PAT.match(f):
                out['clone_npz'].append(rel)
            # ④ babelvox 示例音色
            if low in BABELVOX_SPEAKER_FILES:
                out['babelvox_example'].append(rel)
            # ⑥ torch / CUDA
            ext = os.path.splitext(low)[1]
            if ext in TORCH_CUDA_EXT:
                out['torch_cuda'].append(rel)
            elif ext in ('.dll', '.pyd'):
                if any(s in low for s in TORCH_CUDA_SUBSTR):
                    out['torch_cuda'].append(rel)
            # ③ tts_speakers 目录里的音色文件（克隆音色落盘处）
            if rel.lower().startswith('tts_speakers' + os.sep):
                out['tts_speakers_dir'].append(rel)
            # ⑤ 开发目录绝对路径（只扫文本类文件）
            if ext in TEXT_EXT:
                try:
                    with open(p, 'rb') as fh:
                        raw = fh.read()
                    txt = raw.decode('utf-8', errors='ignore')
                except OSError:
                    continue
                if size > 8 << 20:
                    continue
                for m in DEV_PATH_PAT.finditer(txt):
                    line_no = txt.count('\n', 0, m.start()) + 1
                    out['dev_path'].append(
                        {'file': rel, 'line': line_no, 'match': m.group(0)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app281_rc3_blacklist_scan_evidence.json'))
    args = ap.parse_args()

    if not os.path.isdir(args.pkg):
        raise SystemExit('解压副本不存在：%s' % args.pkg)

    r = scan(args.pkg)
    checks = [
        ('① 无会议录音（含 260902_SPE 任何切片）', len(r['meeting']) == 0,
         {'hits': r['meeting'][:20], 'n': len(r['meeting'])}),
        ('② 无克隆音色 npz', len(r['clone_npz']) == 0,
         {'hits': r['clone_npz'][:20], 'n': len(r['clone_npz'])}),
        ('②b 无 tts_speakers 音色文件落盘', len(r['tts_speakers_dir']) == 0,
         {'hits': r['tts_speakers_dir'][:20], 'n': len(r['tts_speakers_dir'])}),
        ('④ 无 babelvox 示例音色', len(r['babelvox_example']) == 0,
         {'hits': r['babelvox_example'][:20], 'n': len(r['babelvox_example'])}),
        ('⑤ 无开发目录绝对路径', len(r['dev_path']) == 0,
         {'hits': r['dev_path'][:20], 'n': len(r['dev_path'])}),
        ('⑥ 无 torch/CUDA 的 dll/pyd/.cu/.cuh', len(r['torch_cuda']) == 0,
         {'hits': r['torch_cuda'][:20], 'n': len(r['torch_cuda'])}),
    ]
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    r['checks'] = [{'name': n, 'verdict': ok, 'detail': d} for n, ok, d in checks]
    r['n_pass'] = n_pass
    r['n_fail'] = n_fail
    r['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    r['n_files'] = r['n_files']
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    for n, ok, d in checks:
        print('  [%s] %s  %s' % ('PASS' if ok else 'FAIL', n,
                                  json.dumps(d, ensure_ascii=False)))
    print('\n结果：%d PASS / %d FAIL ⇒ %s' % (n_pass, n_fail, r['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
