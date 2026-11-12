# -*- coding: utf-8 -*-
# APP-103 执行：dev 树接入 stateful 后端（一次性代码同步，非审计/判据脚本）。
# 纪律：读入归一化行尾 → 唯一命中断言替换 → ast.parse → 原行尾写回 → 逐字节复核。
import ast
import datetime
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
DEV = os.path.join(REPO, 'live_caption')
APP = os.path.join(DEV, 'live_caption_app.py')
MANIFEST = os.path.join(DEV, 'manifest_gen.py')
BASELINE = os.path.join(DEV, 'asr06b_backend.py')
REPORT = os.path.join(HERE, 'app483_app103_dev_stateful_sync.json')

PATCHES = [
    ('model_alias', APP, """    # 0.6B 解码器（mask2 INT8，带 attention_mask 端口，**无 KV cache**）
    'ov-dec-06b-embed-mask2-int8sym': ['asr06b-decoder-int8'],""",
     """    # 0.6B 解码器（stateful INT8，带 KV cache；APP-101/102：rc8 只带这一份）
    'ov-dec-06b-stateful-int8sym': ['asr06b-decoder-int8'],"""),
    ('section_header', APP,
     "# 🔴🔴🔳 **APP-096：MiniMVP 的 ASR = Qwen3-ASR-0.6B（mask2 INT8）**",
     "# 🔴🔴🔳 **APP-101/102/103：MiniMVP 的 ASR = Qwen3-ASR-0.6B（stateful INT8，KV cache）**"),
    ('comment_kv', APP, """#   ⚠️ 0.6B decoder **无 KV cache**、静态 512、右对齐
#   ⇒ 与 R2T2 的两套后端**接口相似但语义不同** ⇒ 独立实现（`asr06b_backend.py`）。""",
     """#   ⚠️ 0.6B stateful decoder **有 KV cache**、上界 512、每调用重置
#   ⇒ 与 R2T2 的两套后端**接口相似但语义不同** ⇒ 独立实现
#     （`asr06b_stateful_backend.py`）；无 KV 的旧基线只留在 dev 树。"""),
    ('engine_table', APP, """ENGINES_ASR06B = {
    'gpu_int8': dict(label='Intel GPU · INT8', kind='asr06b', device='GPU.0',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-embed-mask2-int8sym',
                     note='集显：Qwen3-ASR-0.6B（编码器 FP16 + 解码器 INT8 mask2）'),
    'npu_int8': dict(label='Intel NPU · INT8', kind='asr06b', device='NPU',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-embed-mask2-int8sym',
                     note='编码器与解码器都在 NPU，不占 GPU（Qwen3-ASR-0.6B INT8 mask2）'),
}""",
     """ENGINES_ASR06B = {
    'gpu_int8': dict(label='Intel GPU · INT8 (stateful)', kind='asr06b', device='GPU.0',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-stateful-int8sym',
                     note='集显：Qwen3-ASR-0.6B（编码器 FP16 + 解码器 stateful INT8 / KV cache）'),
    'npu_int8': dict(label='Intel NPU · INT8 (stateful)', kind='asr06b', device='NPU',
                     enc='ov-encoder-06b-fp16-static',
                     dec='ov-dec-06b-stateful-int8sym',
                     note='NPUW_LLM：Qwen3-ASR-0.6B（编码器 FP16 + 解码器 stateful INT8 / KV cache）'),
}"""),
    ('ir_ready_probe', APP,
     "        dec = _model_path('ov-dec-06b-embed-mask2-int8sym')",
     "        dec = _model_path('ov-dec-06b-stateful-int8sym')"),
    ('backend_init', APP, """        elif self.cfg['kind'] == 'asr06b':
            # 🔴🔴🔳 **APP-096：Qwen3-ASR-0.6B（mask2 INT8）后端**
            # ⚠️ 0.6B 的 decoder **无 KV cache**、静态 512、右对齐
            #    ⇒ 与 R2T2 的两套后端**接口相似但语义不同** ⇒ 独立实现。
            # ⚠️ NPU 上 **不设 NPUW_LLM**：0.6B decoder 不是 causal-LM-with-past 图
            #    （无 KV cache）⇒ 走 plain 编译即可（reviewer 的 NPU 档已实测跑通）。
            from asr06b_backend import ASR06BBackend
            on_log(f'加载 {self.cfg["label"]}（Qwen3-ASR-0.6B mask2 INT8）…')
            self.backend = ASR06BBackend(""",
     """        elif self.cfg['kind'] == 'asr06b':
            # 🔴🔴🔳 **APP-101/102/103：Qwen3-ASR-0.6B stateful（KV cache）后端**
            # ⚠️ NPU 上 decoder 需 NPU_USE_NPUW / NPUW_LLM（B-kit bk_run 口径）；
            #    encoder 不带 NPUW 属性。每次 generate 新建 InferRequest + reset_state。
            # ⚠️ dev 侧可用 LIVECAP_ASR_BACKEND_MODULE 切到无 KV 的旧基线模块
            #    （该模块只在开发树，客户包内不存在，也不出现在 GUI / --check）。
            import importlib
            _mod_name = os.environ.get('LIVECAP_ASR_BACKEND_MODULE',
                                       'asr06b_stateful_backend')
            _backend_cls = importlib.import_module(_mod_name).BACKEND_CLASS
            on_log(f'加载 {self.cfg["label"]}（Qwen3-ASR-0.6B stateful INT8 / KV cache）…')
            self.backend = _backend_cls("""),
    ('check_comment', APP,
     "            #   解码器 = `openvino_model.xml`（mask2 INT8）",
     "            #   解码器 = `openvino_model.xml`（stateful INT8 / KV cache）"),
    ('manifest_decoder', MANIFEST,
     """    ('asr06b-decoder-int8', {
        'source_path': r'qwen3asr_06b\\models\\ov-dec-06b-embed-mask2-int8sym',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'OV IR，mask2 INT8（per-channel 权重）；decoder bin 应与 B 机 rc5 实测 7FBEB8EF999DDFBA… 一致'}),""",
     """    ('asr06b-decoder-int8', {
        'source_path': r'qwen3asr_06b\\models\\ov-dec-06b-stateful-int8sym',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'APP-101/102/103：OV IR，stateful INT8（KV cache）；decoder bin SHA256 应为 0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262baba4dc55e603b600d6a3'}),"""),
    ('manifest_embed', MANIFEST,
     """    ('embed_tokens_06b_f16.npy', {
        'source_path': r'confucius4-openvino\\results\\app\\_rc5_stage\\embed_tokens_06b_f16.npy',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': '从 HF 文本 embedding 表导出的 FP16 权重表 [151936, 1024]；产物在 rc5 构建暂存区'}),""",
     """    ('embed_tokens_06b_f16.npy', {
        'source_path': r'qwen3asr_06b\\b_kit_stateful\\assets\\embed_tokens.npy',
        'source_model': 'Qwen3-ASR-0.6B',
        'note': 'APP-103：B-kit 导出的 fp16 文本 embedding 表 [151936, 1024]（免 torch）；'
                'SHA256 e8d4448c57626ff9a6396b06f05f0e2c2d9ca4fa2436988f012c171e9f861f2c，'
                '与 rc5 暂存区的 embed_tokens_06b_f16.npy 逐字节同一份'}),"""),
    ('baseline_factory', BASELINE,
     """def load_chat_template_06b(tokenizer_dir: str) -> str:
    \"\"\"读 0.6B 的 `chat_template.json`（**仅供诊断/对照**，后端本身不依赖它）。\"\"\"
    p = os.path.join(tokenizer_dir, 'chat_template.json')
    with open(p, encoding='utf-8') as f:
        return json.load(f)['chat_template']""",
     """def load_chat_template_06b(tokenizer_dir: str) -> str:
    \"\"\"读 0.6B 的 `chat_template.json`（**仅供诊断/对照**，后端本身不依赖它）。\"\"\"
    p = os.path.join(tokenizer_dir, 'chat_template.json')
    with open(p, encoding='utf-8') as f:
        return json.load(f)['chat_template']


#: dev 树基线开关：LIVECAP_ASR_BACKEND_MODULE=asr06b_backend 时由工厂取这个类。
#: 🔴 本模块只在开发树，客户包内不存在（APP-101 §4.2）。
BACKEND_CLASS = ASR06BBackend"""),
]


def read_norm(path):
    raw = open(path, 'rb').read()
    eol = b'\r\n' if b'\r\n' in raw else b'\n'
    t = raw.replace(b'\r\n', b'\n').decode('utf-8')
    return raw, eol, t


def main():
    ev = {'at': datetime.datetime.now().isoformat(timespec='seconds'),
          'correction': 'APP-101/102/103', 'checks': [], 'files': []}
    # ── 写前自检：全部锚点唯一命中、全部源文件可 ast.parse ──
    cache = {}
    for tag, path, old, new in PATCHES:
        if path not in cache:
            cache[path] = read_norm(path)
        _, _, t = cache[path]
        cnt = t.count(old)
        ok = (cnt == 1)
        ev['checks'].append({'tag': tag, 'file': os.path.basename(path),
                             'hits': cnt, 'ok': ok})
        if not ok:
            print('!! 写前自检 FAIL:', tag, 'hits=', cnt)
            return 2
    for path, (_, _, t) in cache.items():
        ast.parse(t)
    print('写前自检 PASS: %d 个锚点全部唯一命中；%d 个源文件 ast.parse OK'
          % (len(PATCHES), len(cache)))

    # ── 应用替换 ──
    out = {}
    for path, (raw, eol, t) in cache.items():
        nt = t
        for tag, p2, old, new in PATCHES:
            if p2 == path:
                nt = nt.replace(old, new, 1)
        ast.parse(nt)
        data = nt.encode('utf-8')
        if eol == b'\r\n':
            data = data.replace(b'\n', b'\r\n')
        with open(path, 'wb') as f:
            f.write(data)
        again = open(path, 'rb').read()
        if again != data:
            raise RuntimeError('写后逐字节复核不一致：%s' % path)
        out[path] = data
        ev['files'].append({
            'path': os.path.relpath(path, REPO).replace('\\', '/'),
            'bytes_before': len(raw), 'bytes_after': len(data),
            'sha256_after': hashlib.sha256(data).hexdigest(),
            'eol': 'CRLF' if eol == b'\r\n' else 'LF',
        })
        print('WROTE %s: %d -> %d B (%s)' %
              (os.path.basename(path), len(raw), len(data),
               'CRLF' if eol == b'\r\n' else 'LF'))

    # ── 写后自检：包内会带的 .py 里 mask2 字面必须为 0 ──
    pkg_py = [f for f in os.listdir(DEV) if f.endswith('.py')
              and f not in ('asr06b_backend.py',)]
    hits = {}
    for f in pkg_py:
        n = sum(1 for _ in open(os.path.join(DEV, f), encoding='utf-8',
                                errors='replace').read().split('mask2')) - 1
        if n:
            hits[f] = n
    ev['post_check'] = {
        'dev_py_with_old_decoder_literal': hits,
        'stateful_module_exists': os.path.isfile(
            os.path.join(DEV, 'asr06b_stateful_backend.py')),
        'stateful_module_mask2_hits': open(
            os.path.join(DEV, 'asr06b_stateful_backend.py'), encoding='utf-8'
        ).read().count('mask2'),
        'engine_labels': ['Intel GPU · INT8 (stateful)',
                          'Intel NPU · INT8 (stateful)'],
        'manifest_decoder_source': "qwen3asr_06b\\models\\ov-dec-06b-stateful-int8sym",
    }
    ok = (not hits and ev['post_check']['stateful_module_mask2_hits'] == 0)
    ev['verdict'] = 'PASS' if ok else 'FAIL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('写后自检：dev 树（不含旧基线模块）旧解码器字面命中 =', hits,
          '⇒', ev['verdict'])
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
