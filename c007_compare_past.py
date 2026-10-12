"""c007_compare_past.py — C-007 验证

离线 test.wav，FP16，OVBackend(with-past) vs 旧 OVR2T2ASR(no-past)：
- 同一组 prompt 模板 (ids_left + audio_pad*N_audio + ids_right)
- 同一段音频 → 同一段 encoder_hidden_states
- greedy token 序列逐个对比
- 跑在 GPU.0 和 CPU 上
- 输出 token id 序列 + 总耗时
"""
import os, sys, time, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
AUDIO_PAD = 151676
EOS_IDS = [151643, 151645]
WAV = 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav'


def load_audio():
    audio, sr = sf.read(WAV)
    assert sr == SAMPLE_RATE
    return audio.astype(np.float32)


# ── 旧 no-past greedy（来自 ov_r2t2.py） ───────────────────────────
class NoPastDecoder:
    def __init__(self, model_dir, device):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor
        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        self.device = device
        self.full_name = full_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=True)
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(model_dir)
        # 用 tokenizer 直接构造 chat template（无 processor）
        self.tokenizer.chat_template = open(
            os.path.join(model_dir, "chat_template.jinja"), encoding="utf-8",
        ).read()
        core.set_property({"CACHE_DIR": "./ov_cache"})
        self.enc = core.compile_model(
            os.path.join(model_dir, "openvino_encoder_model.xml"), device,
            {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f16"},
        )
        self.dec = core.compile_model(
            os.path.join(model_dir, "openvino_decoder_model.xml"), device,
            {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f16"},
        )
        self._prompt_template_ids = self._build_template()

    def _build_template(self):
        msgs = [{"role": "system", "content": ""},
                {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
        text = self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        tl, tr = text.split("<|audio_start|><|audio_pad|><|audio_end|>")
        return (self.tokenizer.encode(tl, add_special_tokens=False),
                self.tokenizer.encode(tr, add_special_tokens=False))

    def encode(self, wav):
        fea = self.feature_extractor(list(wav), sampling_rate=SAMPLE_RATE, return_tensors="np")
        x = fea["input_features"].astype(np.float32)
        return self.enc({"input_features": x})["last_hidden_state"]

    def greedy(self, ehs, prefix_ids, max_new_tokens=64):
        ids_l, ids_r = self._prompt_template_ids
        N = ehs.shape[1]
        ids = np.array([list(ids_l) + [AUDIO_PAD] * N + list(ids_r) + list(prefix_ids)], dtype=np.int64)
        out = []
        for _ in range(max_new_tokens):
            logits = self.dec({"input_ids": ids, "encoder_hidden_states": ehs})["logits"]
            nxt = int(np.argmax(logits[0, -1]))
            if nxt in EOS_IDS: break
            out.append(nxt)
            ids = np.concatenate([ids, np.array([[nxt]], dtype=np.int64)], axis=1)
        return out


# ── 新 with-past greedy（来自 backends.OVBackend） ──────────────────
class WithPastDecoder:
    def __init__(self, model_dir, device):
        import openvino as ov
        from transformers import AutoTokenizer, WhisperFeatureExtractor
        core = ov.Core()
        full_name = core.get_property(device, "FULL_DEVICE_NAME")
        self.device = device
        self.full_name = full_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, fix_mistral_regex=True)
        self.feature_extractor = WhisperFeatureExtractor.from_pretrained(model_dir)
        self.tokenizer.chat_template = open(
            os.path.join(model_dir, "chat_template.jinja"), encoding="utf-8",
        ).read()
        core.set_property({"CACHE_DIR": "./ov_cache"})
        self.enc = core.compile_model(
            os.path.join(model_dir, "openvino_encoder_model.xml"), device,
            {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f16"},
        )
        self.dec = core.compile_model(
            os.path.join(model_dir, "openvino_decoder_model.xml"), device,
            {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f16"},
        )
        self.dec_infer = self.dec.create_infer_request()
        self._prompt_template_ids = self._build_template()

    def _build_template(self):
        msgs = [{"role": "system", "content": ""},
                {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
        text = self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        tl, tr = text.split("<|audio_start|><|audio_pad|><|audio_end|>")
        return (self.tokenizer.encode(tl, add_special_tokens=False),
                self.tokenizer.encode(tr, add_special_tokens=False))

    def encode(self, wav):
        fea = self.feature_extractor(list(wav), sampling_rate=SAMPLE_RATE, return_tensors="np")
        x = fea["input_features"].astype(np.float32)
        return self.enc({"input_features": x})["last_hidden_state"]

    def greedy(self, ehs, prefix_ids, max_new_tokens=64):
        ids_l, ids_r = self._prompt_template_ids
        N = ehs.shape[1]
        full = list(ids_l) + [AUDIO_PAD] * N + list(ids_r) + list(prefix_ids)
        self.dec_infer.reset_state()
        # prefill
        self.dec_infer.infer({
            "encoder_hidden_states": ehs,
            "input_ids": np.array([full], dtype=np.int64),
            "beam_idx": np.array([0], dtype=np.int32),
        })
        logits = self.dec_infer.get_output_tensor(0).data
        nxt = int(np.argmax(logits[0, -1]))
        out = [nxt]
        if nxt in EOS_IDS: return out
        for _ in range(max_new_tokens - 1):
            self.dec_infer.infer({
                "encoder_hidden_states": ehs,
                "input_ids": np.array([[nxt]], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            })
            logits = self.dec_infer.get_output_tensor(0).data
            nxt = int(np.argmax(logits[0, -1]))
            if nxt in EOS_IDS: break
            out.append(nxt)
        return out


def run_compare(audio, device: str, max_new_tokens: int = 64):
    print(f"\n========== device = {device}  (FULL_DEVICE_NAME = checking...) ==========")
    print("loading no-past decoder ... ", end="", flush=True)
    t0 = time.perf_counter()
    nopast = NoPastDecoder("models/ov-fp16", device)
    print(f"done in {time.perf_counter()-t0:.1f}s   ({nopast.full_name})")
    print("loading with-past decoder ... ", end="", flush=True)
    t0 = time.perf_counter()
    wpast = WithPastDecoder("models/ov-fp16-past", device)
    print(f"done in {time.perf_counter()-t0:.1f}s   ({wpast.full_name})")

    # 同一组音频特征
    print("encode audio (no-past) ... ", end="", flush=True)
    t0 = time.perf_counter()
    ehs1 = nopast.encode(audio)
    t_enc_nopast = time.perf_counter() - t0
    print(f"{t_enc_nopast:.3f}s  shape={ehs1.shape}")
    print("encode audio (with-past) ... ", end="", flush=True)
    t0 = time.perf_counter()
    ehs2 = wpast.encode(audio)
    t_enc_wpast = time.perf_counter() - t0
    print(f"{t_enc_wpast:.3f}s  shape={ehs2.shape}")

    ehs_close = np.allclose(ehs1, ehs2, atol=1e-2)
    print(f"encoder output close? {ehs_close}  (max diff = {np.max(np.abs(ehs1 - ehs2)):.4e})")

    # greedy no-past
    print("greedy no-past ... ", end="", flush=True)
    t0 = time.perf_counter()
    toks_nopast = nopast.greedy(ehs1, prefix_ids=[], max_new_tokens=max_new_tokens)
    t_dec_nopast = time.perf_counter() - t0
    print(f"{t_dec_nopast:.3f}s  n_tokens={len(toks_nopast)}")

    # greedy with-past
    print("greedy with-past ... ", end="", flush=True)
    t0 = time.perf_counter()
    toks_wpast = wpast.greedy(ehs2, prefix_ids=[], max_new_tokens=max_new_tokens)
    t_dec_wpast = time.perf_counter() - t0
    print(f"{t_dec_wpast:.3f}s  n_tokens={len(toks_wpast)}")

    # 序列对比
    n = min(len(toks_nopast), len(toks_wpast))
    first_diff = None
    for i in range(n):
        if toks_nopast[i] != toks_wpast[i]:
            first_diff = i
            break
    if first_diff is None and len(toks_nopast) != len(toks_wpast):
        first_diff = n  # 长度差
    equal = (toks_nopast == toks_wpast)

    print()
    print(f"  no-past tokens ({len(toks_nopast)}): {toks_nopast}")
    print(f"  with-past tokens ({len(toks_wpast)}): {toks_wpast}")
    print(f"  text no-past : {nopast.tokenizer.decode(toks_nopast, skip_special_tokens=True)!r}")
    print(f"  text with-past: {wpast.tokenizer.decode(toks_wpast, skip_special_tokens=True)!r}")
    print()
    print(f"  EQUAL: {equal}  first_diff_idx: {first_diff}")
    print(f"  no-past total:  encode={t_enc_nopast:.3f}s + decode={t_dec_nopast:.3f}s = {t_enc_nopast+t_dec_nopast:.3f}s")
    print(f"  with-past total: encode={t_enc_wpast:.3f}s + decode={t_dec_wpast:.3f}s = {t_enc_wpast+t_dec_wpast:.3f}s")
    print(f"  speedup decode only: {t_dec_nopast/t_dec_wpast:.2f}x")
    return {
        'device': device,
        'toks_nopast': toks_nopast,
        'toks_wpast': toks_wpast,
        'equal': equal,
        'first_diff_idx': first_diff,
        't_enc_nopast': t_enc_nopast, 't_enc_wpast': t_enc_wpast,
        't_dec_nopast': t_dec_nopast, 't_dec_wpast': t_dec_wpast,
        'n_tokens_nopast': len(toks_nopast), 'n_tokens_wpast': len(toks_wpast),
        'encoder_close': bool(ehs_close),
    }


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--devices', default='GPU.0,CPU')
    p.add_argument('--max-new-tokens', type=int, default=64)
    p.add_argument('--out-json', default='reports/c007_compare_past.json')
    args = p.parse_args()
    audio = load_audio()
    print(f'[c007] audio: {len(audio)} samples, {len(audio)/SAMPLE_RATE:.2f}s')

    devices = [d.strip() for d in args.devices.split(',')]
    results = {}
    for d in devices:
        try:
            results[d] = run_compare(audio, d, max_new_tokens=args.max_new_tokens)
        except Exception as e:
            print(f'  ERROR on {d}: {e}')
            results[d] = {'error': str(e)}

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n[c007] results → {args.out_json}')

    # 总结
    all_equal = all(r.get('equal') for r in results.values() if 'equal' in r)
    print(f'\n[c007] ALL_DEVICES_TOKEN_EQUAL = {all_equal}')
    if not all_equal:
        print('[c007] !!! tokens differ !!! → per C-008 step1, set WAITING_REVIEW')
