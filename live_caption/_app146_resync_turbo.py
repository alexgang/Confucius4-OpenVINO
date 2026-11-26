"""从**完好的原件**（`.bak_app146`）用**行号法**重做 turbo 同步（APP-146 §3 收尾）。

🔴 事故复盘（写进代码注释，避免重犯）：
* 第一版用 difflib 的**文本块**做替换 ⇒ insert 块的 `old` 是**空串**
  ⇒ `text.find('')` 返回 **0** ⇒ 所有 insert 块被插到**文件开头**
  ⇒ 候选目录的 app/tts_engine.py 语法损坏（冒烟实测：`invalid character '🔴'`）。
* 第二版从损坏文件继续 ⇒ 又叠加成 4255 行 ⇒ 更坏。
⇒ **正确做法**：
  ① 每次都从**完好的原件**（`.bak_app146`，已验证 ast OK 且与 dev 只差 turbo 块）出发；
  ② 用 difflib 给出的**行号**做行级替换（位置明确、无歧义）；
  ③ 按**真实行尾**切分/拼接（splitlines + NL，避免 `\r\r\n`）；
  ④ 写后 **ast.parse** ＋ **与 dev 树的剩余差异必须全部是 turbo 块**（否则 fail-closed）。
"""
import ast
import difflib
import io
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\app'
FILES = [('tts_engine.py', 'tts_engine.py.bak_app146'),
         ('npu_delivery_backend.py', 'npu_delivery_backend.py.bak_app146')]


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def sync_from_backup(fname, bakname):
    bak_p = os.path.join(CAND, bakname)
    dst_p = os.path.join(CAND, fname)
    dev_p = os.path.join(REPO, 'live_caption', fname)

    orig_b = read(bak_p)
    orig = orig_b.decode('utf-8')
    ast.parse(orig)                      # ★ 原件必须语法完好
    dev = read(dev_p).decode('utf-8').splitlines()
    cand = orig.splitlines()

    NL = '\r\n' if '\r\n' in orig else '\n'
    sm = difflib.SequenceMatcher(None, cand, dev, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != 'equal']

    def is_turbo(tag, i1, i2, j1, j2):
        seg = '\n'.join(cand[i1:i2]) + '\n' + '\n'.join(dev[j1:j2])
        return 'turbo' in seg.lower() or 'NPU_TURBO' in seg

    turbo_ops = [o for o in ops if is_turbo(*o)]
    other_ops = [o for o in ops if not is_turbo(*o)]
    print('\n[%s] 差异块 %d（turbo %d / 其它 %d）'
          % (fname, len(ops), len(turbo_ops), len(other_ops)))
    for tag, i1, i2, j1, j2 in other_ops:
        print('   ★ 非 turbo 块（**不应用**）：%s cand[%d:%d] %r'
              % (tag, i1, i2, '\n'.join(cand[i1:i2])[:70]))
    if other_ops:
        print('   ⇒ 存在非 turbo 差异 ⇒ **fail-closed，不落盘**')
        return None

    out = list(cand)
    for tag, i1, i2, j1, j2 in reversed(turbo_ops):
        out[i1:i2] = dev[j1:j2]
    text = NL.join(out)
    if orig_b.endswith(NL.encode()) and not text.endswith(NL):
        text += NL

    # 写后复核（**落盘前**先在内存里验）
    ast.parse(text)
    cand2 = text.splitlines()
    sm2 = difflib.SequenceMatcher(None, cand2, dev, autojunk=False)
    ops2 = [o for o in sm2.get_opcodes() if o[0] != 'equal']
    non2 = [o for o in ops2 if not is_turbo(*o)]
    print('   写后剩余差异块 %d（非 turbo %d）' % (len(ops2), len(non2)))
    if non2:
        print('   ⇒ 写后仍有非 turbo 差异 ⇒ **fail-closed，不落盘**')
        return None

    bak2 = dst_p + '.bak_app146_resync2'
    if not os.path.exists(bak2):
        shutil.copy2(dst_p, bak2)
    tmp = dst_p + '.tmp_app146_resync2'
    with open(tmp, 'wb') as f:
        f.write(text.encode('utf-8'))
    os.replace(tmp, dst_p)

    after = read(dst_p).decode('utf-8')
    ast.parse(after)
    print('   ✔ 已落盘：%d 行，turbo 标记 _npu_compile_props=%d / _turbo_compile_props=%d'
          % (len(after.splitlines()),
             after.count('_npu_compile_props'), after.count('_turbo_compile_props')))
    return {'file': fname, 'blocks': len(ops), 'applied': len(turbo_ops),
            'lines': len(after.splitlines()),
            'sha256': __import__('hashlib').sha256(read(dst_p)).hexdigest()}


def main():
    res = []
    for fname, bak in FILES:
        r = sync_from_backup(fname, bak)
        if r is None:
            print('\n★ fail-closed：%s 未落盘' % fname)
            return 1
        res.append(r)
    print('\n' + json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    import json
    sys.exit(main())
