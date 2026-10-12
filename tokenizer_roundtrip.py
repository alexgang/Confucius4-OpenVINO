"""tokenizer_roundtrip.py — C-005 自检

对比 HF tokenizer（models/hf/）与 OpenVINO tokenizer IR（models/ov-fp16/openvino_tokenizer.xml）
对测试句的 encode/decode 一致性。
"""
import os, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
from transformers import AutoTokenizer

TEST_TEXT = '之前有顾客自己带酒水也没加收钱或者不让喝。'


def hf_tokenizer_test():
    tk = AutoTokenizer.from_pretrained('models/hf', fix_mistral_regex=True)
    ids = tk.encode(TEST_TEXT, add_special_tokens=False)
    decoded = tk.decode(ids, skip_special_tokens=True)
    return ids, decoded


def ov_tokenizer_test():
    import openvino as ov
    from transformers import AutoTokenizer
    tk = AutoTokenizer.from_pretrained('models/ov-fp16', fix_mistral_regex=True)
    # OpenVINO tokenizer model takes string input, returns token IDs as numpy
    ov_tok = ov.compile_model('models/ov-fp16/openvino_tokenizer.xml', 'CPU')
    out = ov_tok({'string': np.array([TEST_TEXT], dtype=object)})
    ids = list(out['output_ids'][0])
    decoded = tk.decode(ids, skip_special_tokens=True)
    return ids, decoded


def main():
    print(f'[tok] test text: {TEST_TEXT!r}')
    hf_ids, hf_dec = hf_tokenizer_test()
    print(f'[tok] HF    encode: {hf_ids}')
    print(f'[tok] HF    decode: {hf_dec!r}')
    try:
        ov_ids, ov_dec = ov_tokenizer_test()
        print(f'[tok] OV    encode: {ov_ids}')
        print(f'[tok] OV    decode: {ov_dec!r}')
        ok = (hf_ids == ov_ids) and (hf_dec == ov_dec)
        print(f'[tok] EQUAL: {ok}')
        if not ok:
            print(f'[tok]   HF ids  vs OV ids  : {set(zip(hf_ids, ov_ids))}')
            print(f'[tok]   HF text vs OV text : {hf_dec!r} vs {ov_dec!r}')
        return 0 if ok else 1
    except Exception as e:
        print(f'[tok] OV tokenizer FAILED: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())