r"""_app316 — 修掉 APP-080 构建期补丁的 docstring 副作用，并给自证补判据 + 反证。

背景：_app315 首版把 `if _V23_PRESET_ONLY: return ...` 插在 def 行与
docstring 之间 ⇒ 补丁后 5 个函数的 `__doc__` 变成 None（ast 实测：
dev 有 docstring、patched 全 None）。功能不受影响，但属「自证 PASS 却
静默改了另一条语义」⇒ 本脚本把闸门改到 **docstring 之后**，并在自证里
加一条 `docstrings_preserved_after_guard` 判据 + 反证 E8。

纪律：定点字符串替换 + 唯一命中断言 + ast.parse + 原子写回 + 写后逐字节复核；
不碰 dev 源文件（只改构建期补丁规范与自证脚本）、不碰客户包、不占设备。
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
P_MOD = os.path.join(ROOT, 'live_caption', 'v23_preset_only.py')
P_SELF = os.path.join(HERE, '_app315_app080_preset_only_selftest.py')
OUT = os.path.join(HERE, '_app316_docstring_guard_fix.json')

MOD_BLOCKS = []

MOD_BLOCKS.append((r'''_SVC_PATCHES = [
    dict(id='S00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    dict(id='S01-set_clone_pcm', why='APP-080 ② 克隆 PCM 一律不发给 worker',
         old="    def set_clone_pcm(self, pcm) -> bool:\n",
         new="    def set_clone_pcm(self, pcm) -> bool:\n"
             "        if _V23_PRESET_ONLY:\n"
             "            return False  # APP-080：v2.3 不执行克隆登记\n"),
    dict(id='S02-register_spk_voice', why='APP-080 ② 按说话人登记嗓音一律不执行',
         old="    def register_spk_voice(self, spk: str, pcm) -> bool:\n",
         new="    def register_spk_voice(self, spk: str, pcm) -> bool:\n"
             "        if _V23_PRESET_ONLY:\n"
             "            return False  # APP-080\n"),
]
''', r'''_SVC_PATCHES = [
    dict(id='S00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    # 🔴 闸门必须插在 **docstring 之后**：插在 def 行与 docstring 之间会把
    #    docstring 挤成「非首语句」⇒ 函数的 __doc__ 变 None（_app316 ast 实测）。
    #    after_docstring=True ⇒ apply_patches() 用 ast 定位 docstring 结束行再插入。
    dict(id='S01-set_clone_pcm', why='APP-080 ② 克隆 PCM 一律不发给 worker',
         old="    def set_clone_pcm(self, pcm) -> bool:\n",
         func='set_clone_pcm', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return False  # APP-080：v2.3 不执行克隆登记\n"),
    dict(id='S02-register_spk_voice', why='APP-080 ② 按说话人登记嗓音一律不执行',
         old="    def register_spk_voice(self, spk: str, pcm) -> bool:\n",
         func='register_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return False  # APP-080\n"),
]
'''))

MOD_BLOCKS.append((r'''_WORKER_PATCHES = [
    dict(id='W00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    dict(id='W01-update_clone', why='APP-080 ② speaker_enc 的克隆调用不执行',
         old="    def _update_clone(self, pcm):\n",
         new="    def _update_clone(self, pcm):\n"
             "        if _V23_PRESET_ONLY:\n"
             "            return  # APP-080：不提取克隆 x-vector\n"),
    dict(id='W02-register_spk_voice', why='APP-080 ② 克隆嗓音登记不执行',
         old="    def _register_spk_voice(self, msg):\n",
         new="    def _register_spk_voice(self, msg):\n"
             "        if _V23_PRESET_ONLY:\n"
             "            return  # APP-080\n"),
    dict(id='W03-apply_spk_voice', why='APP-080 ② 旁路触发的音色切换不执行（固定预设 A）',
         old="    def _apply_spk_voice(self, spk):\n",
         new="    def _apply_spk_voice(self, spk):\n"
             "        if _V23_PRESET_ONLY:\n"
             "            return  # APP-080：音色固定为预设 A\n"),
]
''', r'''_WORKER_PATCHES = [
    dict(id='W00-import', why='APP-080 ② 运行期闸门', old=_SVC_IMPORT[0], new=_SVC_IMPORT[1]),
    dict(id='W01-update_clone', why='APP-080 ② speaker_enc 的克隆调用不执行',
         old="    def _update_clone(self, pcm):\n",
         func='_update_clone', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080：不提取克隆 x-vector\n"),
    dict(id='W02-register_spk_voice', why='APP-080 ② 克隆嗓音登记不执行',
         old="    def _register_spk_voice(self, msg):\n",
         func='_register_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080\n"),
    dict(id='W03-apply_spk_voice', why='APP-080 ② 旁路触发的音色切换不执行（固定预设 A）',
         old="    def _apply_spk_voice(self, spk):\n",
         func='_apply_spk_voice', after_docstring=True,
         guard="        if _V23_PRESET_ONLY:\n"
               "            return  # APP-080：音色固定为预设 A\n"),
]
'''))

MOD_BLOCKS.append((r'''    for p in PATCHES[file_key]:
        n = norm.count(p['old'])
        if n != 1:
            raise AssertionError('%s: anchor %s hit %d times (need exactly 1)'
                                 % (file_key, p['id'], n))
        norm = norm.replace(p['old'], p['new'], 1)
        applied.append(p['id'])
''', r'''    for p in PATCHES[file_key]:
        n = norm.count(p['old'])
        if n != 1:
            raise AssertionError('%s: anchor %s hit %d times (need exactly 1)'
                                 % (file_key, p['id'], n))
        if p.get('after_docstring'):
            # 🔴 闸门插到 docstring **之后**（保住 __doc__）；位置由 ast 从
            #    当前文本实时定位 ⇒ docstring 内容以后改了也不会失配。
            tree = ast.parse(norm, filename=file_key)
            node = next((x for x in ast.walk(tree)
                         if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and x.name == p['func']), None)
            if node is None:
                raise AssertionError('%s: %s function %r not found'
                                     % (file_key, p['id'], p['func']))
            first = node.body[0]
            if not (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                raise AssertionError('%s: %s has no leading docstring'
                                     % (file_key, p['id']))
            lines = norm.splitlines(True)
            off = sum(len(x) for x in lines[:first.end_lineno])
            norm = norm[:off] + p['guard'] + norm[off:]
        else:
            norm = norm.replace(p['old'], p['new'], 1)
        applied.append(p['id'])
'''))

SELF_BLOCKS = []

SELF_BLOCKS.append((r'''import tempfile
''', r'''import tempfile
import ast
'''))

SELF_BLOCKS.append((r'''    chk(len(diff_text) > 500, 'diff_written', 'diff bytes=%d' % len(diff_text.encode('utf-8')))
''', r'''    chk(len(diff_text) > 500, 'diff_written', 'diff bytes=%d' % len(diff_text.encode('utf-8')))

    # ── 补丁副作用：闸门不得挤掉函数首语句 docstring（_app316）────────
    def _docs_of(txt, wanted):
        tr = ast.parse(txt.replace('\r\n', '\n'))
        return {n.name: ast.get_docstring(n) for n in ast.walk(tr)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in wanted}
    _want_docs = {'set_clone_pcm', 'register_spk_voice', '_update_clone',
                  '_register_spk_voice', '_apply_spk_voice'}
    dev_docs, patched_docs = {}, {}
    for _k in ('live_caption/tts_service.py', 'live_caption/tts_worker.py'):
        dev_docs.update(_docs_of(src[_k], _want_docs))
        patched_docs.update(_docs_of(patched[_k], _want_docs))
    chk(len(dev_docs) == 5 and all(dev_docs.values()) and dev_docs == patched_docs,
        'docstrings_preserved_after_guard',
        'n_dev=%d n_patched=%d equal=%s' % (len(dev_docs), len(patched_docs),
                                            dev_docs == patched_docs))
'''))

SELF_BLOCKS.append((r'''    n_ident = sum(1 for c in counter if c['identified'])
''', r'''    # E8：把闸门插回 docstring **之前**（_app315 旧补丁）⇒ 判据必须识破
    broken8 = patched[k_svc].replace(
        '    def set_clone_pcm(self, pcm) -> bool:\n',
        '    def set_clone_pcm(self, pcm) -> bool:\n'
        '        if _V23_PRESET_ONLY:\n            return False\n', 1)
    d8 = _docs_of(broken8, _want_docs)
    d8.update(_docs_of(patched['live_caption/tts_worker.py'], _want_docs))
    cp('E8_guard_before_docstring', d8 != dev_docs,
       '__doc__ lost ⇒ docstring 判据必须 FAIL')

    n_ident = sum(1 for c in counter if c['identified'])
'''))


def patch_file(path, blocks, report):
    raw = open(path, 'rb').read()
    crlf = b'\r\n' in raw
    text = raw.decode('utf-8')
    norm = text.replace('\r\n', '\n')
    for i, (old, new) in enumerate(blocks, 1):
        n = norm.count(old)
        assert n == 1, '%s block %d hit %d times (need exactly 1)' % (path, i, n)
        norm = norm.replace(old, new, 1)
        report.append(dict(file=os.path.relpath(path, ROOT), block=i,
                           old_sha256=hashlib.sha256(old.encode('utf-8')).hexdigest(),
                           old_bytes=len(old.encode('utf-8')),
                           new_bytes=len(new.encode('utf-8')), unique_hits=n))
    ast.parse(norm, filename=path)
    out = norm.replace('\n', '\r\n') if crlf else norm
    data = out.encode('utf-8')
    tmp = path + '.tmp_app316'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    back = open(path, 'rb').read()
    assert back == data, 'byte-level readback mismatch: %s' % path
    return dict(file=os.path.relpath(path, ROOT), before_bytes=len(raw),
                after_bytes=len(back), eol='CRLF' if crlf else 'LF',
                ast_parse='PASS', readback_equal=True,
                before_sha256=hashlib.sha256(raw).hexdigest(),
                after_sha256=hashlib.sha256(back).hexdigest())


def main():
    report = []
    files = []
    files.append(patch_file(P_MOD, MOD_BLOCKS, report))
    files.append(patch_file(P_SELF, SELF_BLOCKS, report))
    out = dict(tool='_app316_docstring_guard_fix', app='APP-080',
               scope='static_only_no_device_no_packaging',
               generated_at=datetime.datetime.now().isoformat(timespec='seconds'),
               reason=('_app315 首版闸门插在 def 与 docstring 之间 ⇒ '
                       '5 个目标函数补丁后 __doc__ 变 None；'
                       '改为 ast 定位 docstring 结束行后插入，并补判据 + 反证 E8'),
               blocks=report, files=files,
               verdict='PASS' if all(f['readback_equal'] for f in files) else 'FAIL')
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(verdict=out['verdict'],
                          n_blocks=len(report),
                          files=[(f['file'], f['before_bytes'], f['after_bytes'])
                                 for f in files]), ensure_ascii=False))
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
