"""把 live_caption_app.py 的未提交改动拆成「CUDA 组」与「stitch 组」两个 patch。

🔴 **为什么必须拆**：工作区里混了两份不同来源的改动 ——
   ① App 本轮 CUDA / 设备标签修复（用户诉求：去掉假的「Intel GPU 2」+ TTS 加 CUDA）
   ② APP-012② 切点重复词修复（在制品，**尚未接线、未验证**）
   ⇒ 必须**分两次提交**，否则会把未完成的在制品一起提交进去。

判据：按 hunk 内容分类（含 CUDA / tts_note 的归 CUDA 组，其余归 stitch 组）。

用法：python app024_split_patch.py <repo_root>
输出：<repo_root>/results/app/app024_cuda.patch / app024_stitch.patch
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(
    os.path.join(HERE, '..', '..'))
REL = 'live_caption/live_caption_app.py'

CUDA_MARKERS = (
    'CUDA', 'cuda', 'has_cuda_plugin', 'is_cuda_device',
    '_tts_note_text', 'build_tts_options',
)
STITCH_MARKERS = (
    'STITCH', 'stitch', '_norm_word', 'stopword', 'prev_text',
)


def split_hunks(diff_text):
    """把 unified diff 拆成 (header, [hunk...]) 列表。"""
    lines = diff_text.splitlines(keepends=True)
    out = []
    header = []
    hunks = []
    cur = None
    for ln in lines:
        if ln.startswith('@@'):
            if cur is not None:
                hunks.append(cur)
            cur = [ln]
        elif cur is None:
            header.append(ln)
        else:
            cur.append(ln)
    if cur is not None:
        hunks.append(cur)
    return header, hunks


def classify(hunk):
    body = ''.join(hunk)
    # 只看新增/删除的行（上下文行不参与判定，避免误伤）
    changed = [l for l in hunk[1:]
               if l.startswith('+') or l.startswith('-')]
    text = ''.join(changed)
    is_cuda = any(m in text for m in CUDA_MARKERS)
    is_stitch = any(m in text for m in STITCH_MARKERS)
    if is_cuda and not is_stitch:
        return 'cuda'
    if is_stitch and not is_cuda:
        return 'stitch'
    return 'mixed'


def main():
    diff = subprocess.run(
        ['git', '-C', REPO, 'diff', '--', REL],
        capture_output=True, text=True, check=True).stdout
    if not diff.strip():
        print('NO DIFF')
        return 0
    header, hunks = split_hunks(diff)
    groups = {'cuda': [], 'stitch': [], 'mixed': []}
    for h in hunks:
        groups[classify(h)].append(h)

    print('hunks: cuda=%d stitch=%d mixed=%d'
          % (len(groups['cuda']), len(groups['stitch']), len(groups['mixed'])))

    paths = {}
    for name in ('cuda', 'stitch'):
        if not groups[name]:
            continue
        p = os.path.join(HERE, 'app024_%s.patch' % name)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(''.join(header))
            for h in groups[name]:
                f.write(''.join(h))
        paths[name] = p
        print('WROTE %s (%d hunks, %d bytes)'
              % (p, len(groups[name]), os.path.getsize(p)))

    if groups['mixed']:
        p = os.path.join(HERE, 'app024_mixed.patch')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(''.join(header))
            for h in groups['mixed']:
                f.write(''.join(h))
        print('WROTE %s (%d hunks) <-- 需人工看'
              % (p, len(groups['mixed'])))
        for h in groups['mixed']:
            print('---- mixed hunk ----')
            print(''.join(h)[:2000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
