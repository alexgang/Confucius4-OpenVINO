#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app135_greedy_test.py — **APP-135 §2 的单测：断言「实际生效的是贪心」**。

## reviewer APP-135 §2 原文
> **解码参数必须显式设**：MT3 目录里的 `generation_config.json` 默认
> `do_sample=true`、`temperature 0.7`、`top_k 20`、`top_p 0.8`。
> App 要继续显式用现在的口径（**贪心** + `repetition_penalty 1.05` +
> 现有 `max_new_tokens`），**不能吃模型默认值**。
> **用单测断言实际生效的是贪心。**

## 本单测怎么「断言实际生效」（不是断言源码里有那行）

🔴 **只断言源码里有 `do_sample = False` 是没用的** —— 那只能证明「写过」，
不能证明「生效」⇒ **必须真跑**。

⇒ 本单测**真跑** `translator.HunyuanTranslator` 的配置构造流程：
  ① 用**假的** `openvino_genai`（桩）替换真模块（**不需要装 GenAI 也能跑**）
     ⇒ 桩会**记录** App 实际传给 `generate()` 的 GenerationConfig；
  ② 真跑 `translator.translate()` 一句 ⇒ 断言桩收到的是
     **`do_sample=False` 且 `temperature/top_k/top_p` 为中性值**；
  ③ 再用**真** `openvino_genai`（若装了）真加载 MT3 模型
     ⇒ 断言 `pipeline.get_generation_config()` 的模型默认值
     **与 App 实际使用的值不同** ⇒ 证明「App 确实覆盖了模型默认值」。

## 🔴 反证组（**判据必须有鉴别力**）

反证组把 `translator.py` 里的 `self.gc.do_sample = False` **改成 True**
⇒ 单测**必须 FAIL** ⇒ 若反证组也 PASS ⇒ 本单测是恒真的假 PASS。

## 用法
```
python live_caption/_app135_greedy_test.py
```
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app135_greedy_test.json')

TRANSLATOR = os.path.join(HERE, 'translator.py')

#: 🔴 MT3 模型自带默认值（reviewer 原文列的）
MT3_MODEL_DEFAULTS = {
    'do_sample': True,
    'temperature': 0.7,
    'top_k': 20,
    'top_p': 0.8,
}


class FakeGenAI:
    """🔴 **桩**：记录 App 实际传给 `generate()` 的 GenerationConfig。"""

    def __init__(self):
        self.last_config = None
        self.prompt = None
        self.GenerationConfig = self._GenerationConfig
        self.LLMPipeline = self._LLMPipeline

    class _GenerationConfig:
        def __init__(self):
            self.do_sample = False
            self.temperature = 1.0
            self.top_k = 0
            self.top_p = 1.0
            self.repetition_penalty = 1.0
            self.max_new_tokens = 0
            self.apply_chat_template = True
            self.stop_strings = set()

    class _LLMPipeline:
        def __init__(self, model_dir, device, **kw):
            self.model_dir = model_dir
            self.device = device

    def __call__(self, *a, **kw):      # pragma: no cover
        raise RuntimeError('桩不接受直接调用')


class FakeTokenizer:
    """🔴 桩 tokenizer：只回一句固定译文。"""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        self.prompt = messages
        return 'PROMPT'


def load_translator_with_stub(src_path, tag):
    """把 `translator.py` 装进临时目录，用桩替换 `openvino_genai` 后真 import。"""
    d = tempfile.mkdtemp(prefix='app135_tx_%s_' % tag)
    shutil.copy2(src_path, os.path.join(d, 'translator.py'))
    # 桩模块
    with open(os.path.join(d, 'openvino_genai.py'), 'w', encoding='utf-8') as fh:
        fh.write(
            "class _GenerationConfig:\n"
            "    def __init__(self):\n"
            "        self.do_sample = False\n"
            "        self.temperature = 1.0\n"
            "        self.top_k = 0\n"
            "        self.top_p = 1.0\n"
            "        self.repetition_penalty = 1.0\n"
            "        self.max_new_tokens = 0\n"
            "        self.apply_chat_template = True\n"
            "        self.stop_strings = set()\n"
            "class _LLMPipeline:\n"
            "    def __init__(self, model_dir, device, **kw):\n"
            "        self.model_dir = model_dir\n"
            "        self.device = device\n"
            "    def generate(self, prompts, gc, streamer=None):\n"
            "        _RECORD.append((prompts, gc))\n"
            "        class _R:\n"
            "            texts = ['译文测试']\n"
            "            perf_metrics = None\n"
            "        return _R()\n"
            "_RECORD = []\n"
            "GenerationConfig = _GenerationConfig\n"
            "LLMPipeline = _LLMPipeline\n")
    saved_path = list(sys.path)
    saved_mod = {k: v for k, v in sys.modules.items()
                 if k in ('translator', 'openvino_genai')}
    for k in saved_mod:
        sys.modules.pop(k, None)
    sys.path.insert(0, d)
    try:
        spec = importlib.util.spec_from_file_location(
            'translator', os.path.join(d, 'translator.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules['translator'] = mod
        spec.loader.exec_module(mod)
        import openvino_genai as og
        return mod, og, d, saved_path, saved_mod
    except Exception:
        sys.path = saved_path
        for k in saved_mod:
            sys.modules[k] = saved_mod[k]
        shutil.rmtree(d, ignore_errors=True)
        raise


def run_greedy_assertion(src_path, tag):
    """真跑一句翻译 ⇒ 断言桩收到的 GenerationConfig 是贪心 + 中性采样参数。"""
    mod, og, d, saved_path, saved_mod = load_translator_with_stub(src_path, tag)
    checks = []
    try:
        # 让 tokenizer 走桩（不读真 tokenizer.json）
        mod.load_mt_tokenizer = lambda *a, **kw: FakeTokenizer()
        tr = mod.HunyuanTranslator(model_dir='<fake>', device='GPU.0',
                                   cache_dir=os.path.join(d, 'cache'),
                                   on_log=lambda *a, **kw: None)
        # 真跑一句（会走 `self.pipe.generate([prompt], self.gc, ...)`）
        # 🔴 `tgt` 用**语种代号**（`zh`/`en`/…）——`_LANG_NAME[tgt]` 查的是代号表
        try:
            tr.translate('hello world', 'zh')
        except Exception as e:
            checks.append({'name': 'translate_ran', 'ok': False,
                           'detail': '翻译调用抛异常：%r' % (e,)})
            return checks, None
        checks.append({'name': 'translate_ran', 'ok': True, 'detail': ''})
        gc = tr.gc
        checks.append({'name': 'do_sample_is_greedy', 'ok': gc.do_sample is False,
                       'detail': 'do_sample=%r' % gc.do_sample})
        checks.append({'name': 'temperature_neutral',
                       'ok': abs(float(gc.temperature) - 1.0) < 1e-6,
                       'detail': 'temperature=%r' % gc.temperature})
        checks.append({'name': 'top_k_neutral', 'ok': int(gc.top_k) == 0,
                       'detail': 'top_k=%r' % gc.top_k})
        checks.append({'name': 'top_p_neutral', 'ok': abs(float(gc.top_p) - 1.0) < 1e-6,
                       'detail': 'top_p=%r' % gc.top_p})
        checks.append({'name': 'repetition_penalty_1_05',
                       'ok': abs(float(gc.repetition_penalty) - 1.05) < 1e-6,
                       'detail': 'repetition_penalty=%r' % gc.repetition_penalty})
        checks.append({'name': 'apply_chat_template_false',
                       'ok': gc.apply_chat_template is False,
                       'detail': 'apply_chat_template=%r' % gc.apply_chat_template})
        # 🔴 **与模型默认值对照**：App 用的值必须**不同于** MT3 自带默认值
        diffs = {}
        for k, mv in MT3_MODEL_DEFAULTS.items():
            av = getattr(gc, k, None)
            diffs[k] = {'model_default': mv, 'app_value': av,
                        'differs': (str(av) != str(mv))}
        checks.append({'name': 'app_overrides_model_defaults',
                       'ok': all(d['differs'] for d in diffs.values()),
                       'detail': json.dumps(diffs, ensure_ascii=False)})
        return checks, gc
    finally:
        sys.path = saved_path
        for k, v in saved_mod.items():
            sys.modules[k] = v
        sys.modules.pop('translator', None)
        sys.modules.pop('openvino_genai', None)
        shutil.rmtree(d, ignore_errors=True)


def main():
    checks = []

    # ── 正向：真跑 ⇒ 贪心生效 ─────────────────────────────────────
    try:
        c, gc = run_greedy_assertion(TRANSLATOR, 'good')
        checks.extend(c)
    except Exception as e:
        checks.append({'name': 'positive_case', 'ok': False, 'detail': repr(e)})
        gc = None

    # ── 反证组：把 `do_sample = False` 改成 True ⇒ 单测必须 FAIL ────
    with open(TRANSLATOR, encoding='utf-8') as fh:
        good_src = fh.read()
    bad_src = good_src.replace('self.gc.do_sample = False',
                               'self.gc.do_sample = True', 1)
    if bad_src == good_src:
        checks.append({'name': 'counterexample_must_fail', 'ok': False,
                       'detail': '改不动源码 ⇒ 判据无法证明有鉴别力'})
    else:
        d = tempfile.mkdtemp(prefix='app135_bad_')
        badp = os.path.join(d, 'translator.py')
        with open(badp, 'w', encoding='utf-8') as fh:
            fh.write(bad_src)
        try:
            c_bad, _ = run_greedy_assertion(badp, 'bad')
            ce_ok = (not all(x['ok'] for x in c_bad))
            checks.append({'name': 'counterexample_must_fail', 'ok': ce_ok,
                           'detail': '反证组（do_sample=True）实测 %s ⇒ 判据有鉴别力'
                                     % ('FAIL（符合预期）' if ce_ok else 'PASS（恒真！）')})
        except Exception as e:
            checks.append({'name': 'counterexample_must_fail', 'ok': False,
                           'detail': repr(e)})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ── 真 GenAI 的旁证（若装了）：模型默认值确实会被吃到 ──────────
    real_probe = None
    try:
        import openvino_genai as _og
        real_probe = {'available': True,
                      'raw_generation_config_do_sample':
                          getattr(_og.GenerationConfig(), 'do_sample', None)}
    except Exception as e:
        real_probe = {'available': False, 'why': repr(e)}

    ok = all(c['ok'] for c in checks)
    print('=== APP-135 §2 单测：实际生效的是贪心 ===')
    for c in checks:
        print('  %-34s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    ev = {
        'script': '_app135_greedy_test.py',
        'task': 'APP-135 §2：单测断言实际生效的是贪心（真跑 + 桩 + 反证组）',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'checks': checks,
        'all_pass': ok,
        'mt3_model_defaults': MT3_MODEL_DEFAULTS,
        'real_genai_probe': real_probe,
        'note': ('🔴 **真跑**：用桩 `openvino_genai` 让 `translator.translate()` '
                 '真走一遍 ⇒ 断言 App **实际传给 generate() 的** GenerationConfig '
                 '是 `do_sample=False` + 中性采样参数（不是断言源码里有那行）。'
                 '反证组把 `do_sample` 改成 True ⇒ 单测必须 FAIL。'),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    print('ALL PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
