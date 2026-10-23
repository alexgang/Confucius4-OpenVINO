r"""sync_c111_to_pkg.py — 把 C-111（翻译层「段尾半句当段即翻 + 补全后修正」）移植到客户包 v1.3

做法与 C-105/C-106/C-108/C-109/C-133 一致：**定点替换 + assert 唯一命中**，
且**幂等**（已经是 C-111 状态则跳过，不报错）。

背景（APP-002）
--------------
仓库 `live_caption/` 与客户包 `app/` 是**两份独立维护的副本**：

    live_caption_app.py   repo 与 pkg **不同**（pkg 是旧版）⇒ 必须定点替换
    translator.py         repo HEAD 与 pkg **字节一致** ⇒ 可整文件复制

本脚本**严禁整目录覆盖**（否则会把未交付的 TTS 功能带进 v1.3）。

本次移植两处
------------
1. `translator.py` —— 翻译层核心（C-111）。整文件复制（带备份 + 哈希校验）：
   - `_Job` 扩展 kind：final / half / fix / draft
   - `submit()` 重写：段尾半句**当段即翻**（kind='half'，归本段，不朗读）
   - 半句被后续段补成完整句 ⇒ **重翻并原地覆盖**旧译文（kind='fix'，朗读）
   - 半句链上**每段各留一份**，闭合时整句译文原地覆盖**链首**的槽位
   - `flush()` 不再重翻，只把最后半句标记为 final 交出
   - `carry` 属性、`seg_half` 字典相应更新
2. `live_caption_app.py` —— 消费端（与 C-101 TTS 面板无关）：
   - GUI `clear()` 增加 `self.mt.seg_half.clear()`
   - GUI `_save_text()` 文案：旧「（半句，接续下一段）」→「（译文生成中…）」
   - CLI `run_cli()` 两处 outbox 消费：half 只打印不朗读；final/fix 打印 + 提交 TTS
     （客户包**没有** TTS 模块 ⇒ TTS 提交行不移植，保持 no-op）

用法
----
    python sync_c111_to_pkg.py <pkg_app_dir>

默认目标：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys

DEFAULT_PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARKER = 'C-111'   # 幂等标记


# ══════════════════════════════════════════════════════════════════════
# 1) translator.py —— 整文件复制（repo HEAD 与 pkg 字节一致）
# ══════════════════════════════════════════════════════════════════════

def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def sync_translator(pkg):
    src = os.path.join(REPO, 'live_caption', 'translator.py')
    dst = os.path.join(pkg, 'translator.py')
    if not os.path.exists(src):
        raise SystemExit(f'✗ 找不到仓库源文件: {src}')

    src_h, dst_h = _sha(src), _sha(dst)
    if src_h == dst_h:
        print('  · 跳过（客户包已是 C-111 状态，哈希一致）')
        return 0

    # ★ 安全闸：目标必须与**仓库 HEAD 版**字节一致 —— 否则说明客户包被
    #   别人单独改过，整文件覆盖会吞掉那些改动。
    import subprocess
    head = subprocess.run(
        ['git', '-C', REPO, 'show', 'HEAD:live_caption/translator.py'],
        capture_output=True)
    head_h = hashlib.sha256(head.stdout).hexdigest()
    if head_h != dst_h:
        raise SystemExit(
            '✗ 安全闸：客户包 translator.py 与**仓库 HEAD** 不一致\n'
            f'    pkg  {dst_h}\n    HEAD {head_h}\n'
            '    ⇒ 客户包被单独改过，禁止整文件覆盖；请改为定点替换。')

    bak = os.path.join(os.path.dirname(os.path.dirname(dst)),
                       '_backup_c111', os.path.basename(dst) + '.bak')
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    shutil.copy2(dst, bak)
    print(f'  ✓ 已备份（包外）: {bak}')
    shutil.copy2(src, dst)
    print(f'  ✓ 复制 translator.py（{os.path.getsize(src)} B）'
          f'  哈希 {dst_h[:12]} → {_sha(dst)[:12]}')
    return 1


# ══════════════════════════════════════════════════════════════════════
# 2) live_caption_app.py —— 定点替换
# ══════════════════════════════════════════════════════════════════════

OLD_CLEAR = '''    def clear(self):
        self.final_text = ''
        self.blocks = []
        self.mt.seg_keys.clear()
        self.mt.seg_carry.clear()
        self._render('')'''
NEW_CLEAR = '''    def clear(self):
        self.final_text = ''
        self.blocks = []
        self.mt.seg_keys.clear()
        self.mt.seg_carry.clear()
        self.mt.seg_half.clear()
        self._render('')'''

OLD_SAVE = '''                # 本段开头接上了上一段的半句：用 … 标出接续关系（C-099①）
                if self.mt.seg_carry.get(i):
                    mt = '…' + mt
                out.append('〔译〕' + mt)
            elif self.mt.seg_carry.get(i) and self.mt.active:
                # 整段都是半句、已并入下一段：说明译文在哪，避免看起来像丢了
                out.append('〔译〕（半句，接续下一段）')'''
NEW_SAVE = '''                # 本段原文开头承接上一段的半句（C-111：半句的完整译文在**上一行**，
                # 本行的译文是它的后半截）—— 用 … 标出接续关系
                if self.mt.seg_carry.get(i):
                    mt = '…' + mt
                out.append('〔译〕' + mt)
            elif self.mt.seg_carry.get(i) and self.mt.active:
                # 本段译文还没出来（翻译在途）—— 说明它在等什么，避免看起来像丢了
                out.append('〔译〕（译文生成中…）')'''

OLD_CLI1 = '''            for kind, key, txt in mt.pop_outbox():
                if kind == 'final' and txt.strip():
                    print(f'\\n[译文] {txt}', flush=True)'''
NEW_CLI1 = '''            for kind, key, txt in mt.pop_outbox():
                if kind == 'half' and txt.strip():
                    # C-111：段尾半句的初翻译文 —— 显示但**不朗读**
                    print(f'\\n[半句译文] {txt}', flush=True)
                elif kind in ('final', 'fix') and txt.strip():
                    tag = '修正译文' if kind == 'fix' else '译文'
                    print(f'\\n[{tag}] {txt}', flush=True)'''

OLD_CLI2 = '''        for kind, key, txt in mt.pop_outbox():
            if kind == 'final' and txt.strip():
                print(f'[译文] {txt}', flush=True)'''
NEW_CLI2 = '''        for kind, key, txt in mt.pop_outbox():
            if kind == 'half' and txt.strip():
                print(f'[半句译文] {txt}', flush=True)
            elif kind in ('final', 'fix') and txt.strip():
                tag = '修正译文' if kind == 'fix' else '译文'
                print(f'[{tag}] {txt}', flush=True)'''

OLD_CLI3 = """                elif not m and mt.seg_carry.get(i):
                    m = '（半句，接续下一段）'"""
NEW_CLI3 = """                elif not m and mt.seg_carry.get(i):
                    m = '（译文生成中…）'"""

APP_EDITS = [
    ('clear() 清 seg_half', OLD_CLEAR, NEW_CLEAR),
    ('GUI _save_text 文案', OLD_SAVE, NEW_SAVE),
    ('CLI 消费点 1（实时）', OLD_CLI1, NEW_CLI1),
    ('CLI 消费点 2（收尾）', OLD_CLI2, NEW_CLI2),
    ('CLI 落盘文案', OLD_CLI3, NEW_CLI3),
]


def apply_edits(path, edits):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    changed = 0
    for name, old, new in edits:
        if old not in src:
            if new in src:
                print(f'  · 跳过（已是 C-111 状态）: {name}')
                continue
            raise SystemExit(f'✗ 定点替换失败 [{name}] in {path}: 未命中')
        n = src.count(old)
        if n != 1:
            raise SystemExit(f'✗ 定点替换失败 [{name}] in {path}: '
                             f'命中 {n} 次（要求恰好 1 次）')
        src = src.replace(old, new, 1)
        changed += 1
        print(f'  ✓ 替换: {name}')
    if changed:
        # 备份**不能留在客户包内**（会污染交付物）⇒ 放到包外同级目录。
        bak = os.path.join(os.path.dirname(os.path.dirname(path)),
                           '_backup_c111', os.path.basename(path) + '.bak')
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copy2(path, bak)
        print(f'  ✓ 已备份（包外）: {bak}')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
    return changed


def main():
    pkg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PKG
    if not os.path.isdir(pkg):
        raise SystemExit(f'✗ 客户包目录不存在: {pkg}')
    print(f'目标客户包: {pkg}')

    total = 0
    print('\n[1] translator.py（整文件复制）')
    total += sync_translator(pkg)
    print('\n[2] live_caption_app.py（定点替换）')
    total += apply_edits(os.path.join(pkg, 'live_caption_app.py'), APP_EDITS)

    print(f'\n完成：共 {total} 处改动')
    if total == 0:
        print('（客户包已是 C-111 状态，幂等）')

    # 冒烟：语法检查
    import py_compile
    for fn in ('translator.py', 'live_caption_app.py'):
        py_compile.compile(os.path.join(pkg, fn), doraise=True)
        print(f'  ✓ 语法检查通过: {fn}')


if __name__ == '__main__':
    main()
