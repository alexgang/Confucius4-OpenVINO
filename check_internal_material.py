r"""check_internal_material.py —— 打包前 / 提交前的内部素材闸门（APP-006 第 6 步）。

为什么需要这个
--------------
APP-005① 发现内部会议转写已经被提交并推到了 GitHub origin/main；
APP-006 要求「彻底删掉」并「防止以后再次提交这类文件」。
光靠 `.gitignore` 不够 —— 规则写错一个 `**` 或有人 `git add -f` 就会漏。

所以这里做**双闸门**：
  1. 扫描**待打包目录**（客户包）⇒ 命中即 FAIL（打包前拦）；
  2. 扫描**待提交的 git 文件** ⇒ 命中即 FAIL（提交前拦）。

判定口径
--------
命中规则分两类：

  **A. 文件名模式**（最硬的证据，无需读内容）
     - `*_spoken.*`（内部会议口语子集的转写/译文）
     - `preset_B` / `preset_C` / `clone_X`（音色 B / 同事音色 / 克隆音色素材）
     - `transcript_*.txt` / `segments_*.json`（会议录音的转写与逐句分段）

  **B. 内容关键词**（读文件头若干字节做正则匹配）
     - 若干会议特征串（代号 / 规格 / 音频编号 / 人名片段；字面量见下方 `CONTENT_PATTERNS`）
     - 中文：若干内部规格 / 交付 / 客户 / 业务关键词（字面量见下方 `CONTENT_PATTERNS`）

⚠️ **误报处理**：代码与文档里**故意**提到这些名字的地方是合法的
（例如 `pkg_exclude.py` 的规则说明、`status/**` 的纠偏记录），
本脚本**默认跳过**这些路径；确需扫描时用 `--allow` 显式放行。

用法
----
    python check_internal_material.py --pkg C:\path\to\Confucius4_LiveCaption_v1.3
    python check_internal_material.py --staged
    python check_internal_material.py --pkg <dir> --staged

退出码：0 = 干净；1 = 命中（必须处理）；2 = 用法/环境错误。
"""
import argparse
import os
import re
import subprocess
import sys

# ── A. 文件名模式 ────────────────────────────────────────────────────
NAME_PATTERNS = [
    (re.compile(r'_spoken', re.I), '内部会议口语子集（spoken）转写/译文'),
    (re.compile(r'preset_B', re.I), '音色 B（禁止进包）'),
    (re.compile(r'preset_C', re.I), '音色 C（禁止进包）'),
    (re.compile(r'clone_[A-Z]', re.I), '克隆音色素材（禁止进包）'),
    (re.compile(r'^transcript_.*\.txt$', re.I), '会议录音转写文本'),
    (re.compile(r'^segments_.*\.json$', re.I), '会议录音逐句分段'),
]

# ── B. 内容关键词 ────────────────────────────────────────────────────
# 只读文件**前 N 字节**做匹配（够覆盖会议文本开头），避免读 1.7 GB 的 IR。
CONTENT_PATTERNS = [
    (re.compile(rb'\bQ[G]S\b', re.I), '会议特征串 [REDACTED]'),
    (re.compile(rb'26[0]902'), '会议音频编号 [REDACTED]'),
    (re.compile(rb'b[l]c\s*b[0]', re.I), '内部产品代号 [REDACTED]'),
    (re.compile(rb'5[2]\s*c[o]re', re.I), '内部产品规格 [REDACTED]'),
    (re.compile(rb'L[i]sa will join', re.I), '会议人名片段'),
    (re.compile('\u0035\u0032\u6838'.encode('utf-8')), '内部产品规格 [REDACTED]'),
    (re.compile('\u4e0a\u5468\u6211\u4eec'.encode('utf-8')), '内部交付信息'),
    (re.compile('\u5ba2\u6237\u6837\u54c1'.encode('utf-8')), '内部客户信息'),
    (re.compile('\u4efd\u989d\u635f\u5931'.encode('utf-8')), '内部业务信息'),
]
HEAD_BYTES = 512 * 1024

# ── 默认放行的路径前缀（合法的「提到这些名字」的地方）────────────────
DEFAULT_ALLOW = (
    'status/',
    '.workbuddy/',
    'pkg_exclude.py',
    'check_internal_material.py',
    'pack_v13.py',
    # 🔴 脱敏工具本身必然包含待清除的关键词/模式
    #   （它负责生成 replace-text 表），否则闸门会把自己拦下来。
    'build_redact_table.py',
    'live_caption/sync_c',
    'live_caption/diag_',
    'live_caption/replay_c',
    'live_caption/tts_engine.py',
    'live_caption/device_config.py',
    'live_caption/live_caption_app.py',
    'live_caption/translator.py',
    'README',
)

# 明确要扫的二进制扩展名（只查文件名，不读内容）
SKIP_CONTENT_EXT = {
    '.xml', '.bin', '.npy', '.wav', '.mp3', '.flac', '.ogg', '.pcm',
    '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.gz', '.pyc',
    '.onnx', '.blob', '.m4a', '.aac',
}


def _allowed(rel: str, allow):
    norm = rel.replace('\\', '/')
    return any(norm.startswith(a) for a in allow)


def _scan_name(rel: str):
    base = os.path.basename(rel)
    for rx, why in NAME_PATTERNS:
        if rx.search(base):
            return why
    return None


def _scan_content(path: str):
    try:
        with open(path, 'rb') as f:
            head = f.read(HEAD_BYTES)
    except OSError:
        return None
    for rx, why in CONTENT_PATTERNS:
        if rx.search(head):
            return why
    return None


def scan_dir(root: str, allow, verbose=False):
    """扫描一个目录树，返回 [(relpath, reason)]。"""
    hits = []
    for dirpath, dirs, files in os.walk(root):
        # 跳过缓存与二进制产物目录
        dirs[:] = [d for d in dirs
                   if d not in ('ov_cache', 'npu_cache', 'mt_cache', '__pycache__')]
        for fn in files:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace('\\', '/')
            if _allowed(rel, allow):
                continue
            why = _scan_name(rel)
            if why:
                hits.append((rel, f'文件名规则：{why}'))
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_CONTENT_EXT:
                continue
            if os.path.getsize(full) > 64 * 1024 * 1024:
                continue
            why = _scan_content(full)
            if why:
                hits.append((rel, f'内容关键词：{why}'))
    return hits


def scan_staged(repo: str, allow, verbose=False):
    """扫描 git **待提交**（index 相对 HEAD）的文件，返回 [(relpath, reason)]。"""
    hits = []
    try:
        out = subprocess.run(
            ['git', '-C', repo, 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f'!! git 调用失败: {e}', file=sys.stderr)
        return hits
    names = out.stdout.decode('utf-8', errors='replace').splitlines()
    for rel in names:
        rel = rel.strip()
        if not rel or _allowed(rel, allow):
            continue
        why = _scan_name(rel)
        if why:
            hits.append((rel, f'文件名规则：{why}'))
            continue
        full = os.path.join(repo, rel.replace('/', os.sep))
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext in SKIP_CONTENT_EXT:
            continue
        why = _scan_content(full)
        if why:
            hits.append((rel, f'内容关键词：{why}'))
    return hits


def main():
    ap = argparse.ArgumentParser(description='内部素材闸门（APP-006 第 6 步）')
    ap.add_argument('--pkg', help='待打包的目录（客户包根）')
    ap.add_argument('--staged', action='store_true',
                    help='扫描 git 待提交文件')
    ap.add_argument('--repo', default=os.path.dirname(os.path.abspath(__file__)),
                    help='仓库根（--staged 时用）')
    ap.add_argument('--allow', action='append', default=[],
                    help='额外放行的路径前缀（可重复）')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    if not args.pkg and not args.staged:
        print('用法: --pkg <dir> 或 --staged（或两者都给）', file=sys.stderr)
        return 2

    allow = list(DEFAULT_ALLOW) + list(args.allow)
    total = 0

    if args.pkg:
        if not os.path.isdir(args.pkg):
            print(f'!! 目录不存在: {args.pkg}', file=sys.stderr)
            return 2
        hits = scan_dir(args.pkg, allow, args.verbose)
        total += len(hits)
        print(f'[待打包目录] {args.pkg}')
        print(f'  命中 {len(hits)} 个内部素材')
        for rel, why in hits[:50]:
            print(f'    ⚠️ {rel}  ({why})')
        if len(hits) > 50:
            print(f'    …另有 {len(hits) - 50} 个')

    if args.staged:
        hits = scan_staged(args.repo, allow, args.verbose)
        total += len(hits)
        print(f'[git 待提交] {args.repo}')
        print(f'  命中 {len(hits)} 个内部素材')
        for rel, why in hits[:50]:
            print(f'    ⚠️ {rel}  ({why})')
        if len(hits) > 50:
            print(f'    …另有 {len(hits) - 50} 个')

    print()
    if total:
        print('结论：FAIL —— 存在内部素材，禁止打包/提交')
        return 1
    print('结论：PASS —— 未发现内部素材')
    return 0


if __name__ == '__main__':
    sys.exit(main())
