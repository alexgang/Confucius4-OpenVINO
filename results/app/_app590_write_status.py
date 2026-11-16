#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app590_write_status.py —— **定点写入** `status/app/STATUS_APP.md`（APP-113 §212）。

🔴 **纪律（§204 / §205 / §185 / APP-052④）**：
  · **先备份** ⇒ 写失败可还原原字节。
  · **临时文件 → `os.replace`**（`open(p,'w')` 先截断 ⇒ 写失败 ⇒ 文件 0 B
    ⇒ §204 真踩过 39 598→0 B）。
  · **还原式复核**：本轮**每一个增量**（头部替换 / 最近更新行 / 表格行 /
    新章节 / 归档指针行）**逐一逆向还原** ⇒ 必须与**开工前的原始字节逐字相同**。
  · **落盘前自检**：`≤40000 B` / `≤300 行`（APP-052④）⇒ 超限 ⇒ **fail-closed 不落盘**。
  · **落盘后复核**：字节 / 行数 / `last_ack` / §212 存在 / 还原式复核再跑一次。

用法：
    python _app590_write_status.py <spec.json> <timestamp>
"""
import hashlib
import json
import os
import shutil
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
MAX_BYTES = 40000
MAX_LINES = 300


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


class Editor:
    """定点编辑：记录 (start, end, replacement) ⇒ 可逐一逆向还原。

    🔴 **位置必须互不相同**：`append` 递增游标 ⇒ 多个追加块各占一段
      （否则逆序还原时无法定位）。
    🔴 **还原要带偏移修正**：删掉一段「替换文本」后，被删段恢复成**原长度**，
      ⇒ 后面（更高位置）的编辑位置要按**累计长度差**修正，否则还原必假 FAIL。
    """

    def __init__(self, text):
        self.orig = text
        self.edits = []
        self._append_pos = len(text)

    def _uniq(self, needle, label):
        n = self.orig.count(needle)
        if n != 1:
            raise RuntimeError('锚点「%s」出现 %d 次（预期 1）⇒ 中止'
                               % (label, n))
        return self.orig.index(needle)

    def replace_once(self, old, new, label):
        i = self._uniq(old, label)
        self.edits.append((i, i + len(old), new))
        return self

    def insert_after(self, anchor, text, label):
        i = self._uniq(anchor, label)
        s = i + len(anchor)
        self.edits.append((s, s, text))
        return self

    def append(self, text):
        s = self._append_pos
        self.edits.append((s, s, text))
        self._append_pos = s + len(text)
        return self

    def build(self):
        """按**原坐标升序**逐个应用，并用累计偏移修正后续位置。

        🔴 **不能按降序应用**：多个追加块的位置是「前一块的末尾」⇒
          降序应用时后面的块会落在**当前文本长度之外** ⇒ 中间留空洞。
        """
        out = self.orig
        applied = []
        shift = 0
        for (s, e, r) in sorted(self.edits, key=lambda x: (x[0], x[1])):
            pos = s + shift
            out = out[:pos] + r + out[pos + (e - s):]
            shift += len(r) - (e - s)
            applied.append((s, e, r))
        return out, applied

    @staticmethod
    def revert(out, applied, orig):
        """把每个增量逐一逆向还原 ⇒ 应回到原文。

        🔴 **还原 = 把「替换文本」换回「原片段」**（不是删除！）：
          删除 ⇒ 原文的该段内容丢失 ⇒ 还原结果与原文不一致（假 FAIL）。
        🔴 **位置不需要偏移修正**：按**原坐标升序**还原时，
          所有**更低位置**的增量都已被还原成原样 ⇒ 此刻文本的前缀
          与原文**逐字相同** ⇒ 第 i 个增量的替换文本就在**原坐标 s_i** 处。
        """
        cur = out
        for (s, e, r) in sorted(applied, key=lambda x: (x[0], x[1])):
            if cur[s:s + len(r)] != r:
                raise RuntimeError('还原式复核失败：位置 %d 处内容不匹配' % s)
            cur = cur[:s] + orig[s:e] + cur[s + len(r):]
        return cur


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    spec_path = sys.argv[1]
    ts = sys.argv[2]
    spec = json.load(open(spec_path, encoding='utf-8'))

    with open(STATUS, encoding='utf-8', newline='') as f:
        orig = f.read()
    orig_bytes = orig.encode('utf-8')
    print('开工：STATUS %d B / %d 行  SHA %s'
          % (len(orig_bytes), orig.count('\n') + 1, sha256_bytes(orig_bytes)[:16]))

    ed = Editor(orig)
    for i, r in enumerate(spec.get('replace', [])):
        ed.replace_once(r['old'], r['new'], r.get('label', 'replace#%d' % i))
    for i, ins in enumerate(spec.get('insert_after', [])):
        ed.insert_after(ins['anchor'], ins['text'],
                        ins.get('label', 'insert#%d' % i))
    # 🔴 **所有追加块合并成「一个」编辑**（原坐标 = 文件末尾）
    #   ⇒ 否则多个追加块的位置互为「前一块的末尾」，还原时位置会漂移。
    _ap = ''.join(a['text'] for a in spec.get('append', []))
    if spec.get('prepend_to_file'):
        _ap += spec['prepend_to_file']
    if _ap:
        ed.append(_ap)

    new, applied = ed.build()

    back = Editor.revert(new, applied, orig)
    if back != orig:
        raise RuntimeError('还原式复核失败：新文本逆向还原后与原文不一致 ⇒ 中止')
    print('还原式复核 PASS（%d 个增量逐一还原后逐字一致）' % len(applied))

    nb = new.encode('utf-8')
    nl = new.count('\n') + 1
    print('新文本：%d B / %d 行（限额 %d B / %d 行）' % (len(nb), nl,
                                                      MAX_BYTES, MAX_LINES))
    if len(nb) > MAX_BYTES or nl > MAX_LINES:
        print('🔴 超限 ⇒ fail-closed 不落盘')
        return 3
    # 🔴 **真不变量**：行尾风格**不得改变**（本文件开工时是纯 LF）
    #   ⇒ 新文本的 CRLF 数必须与原文**一致**（不得混入 CRLF）。
    _crlf_o = orig.count('\r\n')
    _crlf_n = new.count('\r\n')
    if _crlf_o != _crlf_n:
        print('🔴 行尾风格变了（CRLF %d → %d）⇒ fail-closed 不落盘'
              % (_crlf_o, _crlf_n))
        return 4
    print('行尾不变式 PASS（CRLF %d）' % _crlf_n)

    bak = STATUS + '.bak_app113_sec212'
    shutil.copy2(STATUS, bak)
    print('备份：%s（%d B）' % (os.path.basename(bak), os.path.getsize(bak)))

    tmp = STATUS + '.tmp_app113'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    if open(tmp, encoding='utf-8', newline='').read() != new:
        os.remove(tmp)
        raise RuntimeError('临时文件写盘后逐字节不一致 ⇒ 中止（源文件未动）')
    os.replace(tmp, STATUS)

    disk = open(STATUS, encoding='utf-8', newline='').read()
    db = disk.encode('utf-8')
    if db != nb:
        raise RuntimeError('落盘后字节数不符（%d ≠ %d）' % (len(db), nb))
    if 'last_ack: APP-113' not in disk:
        raise RuntimeError('落盘后 last_ack 未更新')
    if '## §212' not in disk:
        raise RuntimeError('落盘后 §212 缺失')
    if Editor.revert(disk, applied, orig) != orig:
        raise RuntimeError('落盘后还原式复核失败')
    print('落盘 PASS：%d B / %d 行  SHA %s  章节数 %d'
          % (len(db), disk.count('\n') + 1, sha256_bytes(db)[:16],
             disk.count('\n## §')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
