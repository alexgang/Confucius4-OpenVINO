"""streaming_asr.py — C-006 step3：与后端解耦的 LSP 流式 ASR

主循环原样抄自 `third_party/Confucius4-R2T2/r2t2/r2t2_asr.py` 第 302-578 行
（C-001 要求），唯一改动是：
  - backend.generate_with_prefix(...) 替代 vLLM 的 model.generate([inp], ...)
  - state 字段名与 `backends.ASRStreamingState` 对齐

逻辑要点（与官方一致）：
  - 每个 chunk：buffer → audio_accum 全量累积
  - prefix_text 按 unfixed_chunk_num / unfixed_token_num 回滚（+ 标点检查）
  - 调用 backend → gen_text → 拼 raw_decoded → 解析 language + text
  - 若 <asr_text> 标签缺失且 force_language=None → 该 chunk 不计数
  - finish_streaming_transcribe：flush 剩余 buffer，end_idx = max(1, ...)
"""
from __future__ import annotations
import os, sys, time, json, csv, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np
import soundfile as sf

from backends import (
    ASRBackend, ASRStreamingState, SAMPLE_RATE,
    DEFAULT_PARAMS,
)

# ── 官方 r2t2 同名函数（C-001 直接搬） ────────────────────────────────
_EN2ZH_PUNCT = {',': '，', '.': '。', '!': '！', '?': '？', ';': '；', ':': '：', '(': '（', ')': '）'}
_ZH2EN_PUNCT = {v: k for k, v in _EN2ZH_PUNCT.items()}
_ALL_PUNCT_PAT = re.compile(r'[,\.!?;:()\uff0c\u3002\uff01\uff1f\uff1b\uff1a\uff08\uff09]')


def _normalize_punct_by_context(text: str) -> str:
    def _replace(m):
        punct = m.group(); pos = m.start(); prev_char = ""
        for i in range(pos - 1, -1, -1):
            if not text[i].isspace():
                prev_char = text[i]; break
        if not prev_char: return punct
        if '\u4e00' <= prev_char <= '\u9fff':
            return _EN2ZH_PUNCT.get(punct, punct)
        elif prev_char.isascii() and (prev_char.isalnum() or prev_char in '"\''):
            return _ZH2EN_PUNCT.get(punct, punct)
        return punct
    return _ALL_PUNCT_PAT.sub(_replace, text)


_ASR_TEXT_TAG = '<asr_text>'
_LANG_PREFIX = 'language '


def parse_language_output(raw: str, user_language=None) -> tuple[str, str]:
    if raw is None:
        return '', ''
    if user_language == "English":
        s = str(raw).rstrip()
    else:
        s = str(raw).strip()
    if not s:
        return '', ''
    if user_language:
        return user_language, s
    meta_part = s; text_part = ""
    if _ASR_TEXT_TAG in s:
        meta_part, text_part = s.split(_ASR_TEXT_TAG, 1)
    else:
        return '', s.strip()
    meta_lower = meta_part.lower()
    if "language none" in meta_lower:
        t = text_part.strip()
        if not t:
            return '', ''
        return '', t
    lang = ""
    for line in meta_part.splitlines():
        line = line.strip()
        if not line: continue
        low = line.lower()
        if low.startswith(_LANG_PREFIX):
            val = line[len(_LANG_PREFIX):].strip()
            if val:
                # 简化版：取原始大小写，不做 normalize（与 r2t2 同语义的轻量版）
                lang = val
            break
    return lang, text_part.strip()


def parse_asr_output(raw: str, user_language=None) -> tuple[str, str]:
    """与 r2t2 同语义：返回 (lang, text)。"""
    return parse_language_output(raw, user_language=user_language)


# ── Hallucination reset (per user 2026-10-12 10:26 fallback, C-027 option B) ──
def _detect_ngram_loop(text: str, n: int = 3, min_repeats: int = 3) -> int:
    """检测 text 中 n-gram 重复 >= min_repeats 次.
    返回 loop 起点 (char index), 没有 loop 则返回 -1.

    算法: 滑动窗口, 找出现次数 >= min_repeats 的 n-gram.
    进一步约束: 重复出现时, n-gram 在原文中至少有 1 词间隔 (不能完全重叠).
    - 如果重复 >= 3 次, 截断到**第一次**出现之前 (全部清除)
    - 如果重复 == 2 次, 截断到**第二次**出现之前 (保留第一次)
    """
    import re as _re
    ws = _re.findall(r'\S+', text)
    if len(ws) < n + min_repeats - 1:
        return -1
    ngram_pos = {}
    for i in range(len(ws) - n + 1):
        ng = tuple(ws[i:i + n])
        if ng not in ngram_pos:
            ngram_pos[ng] = []
        ngram_pos[ng].append(i)
    for ng, positions in ngram_pos.items():
        if len(positions) < min_repeats:
            continue
        # 验证位置之间不重叠 (start 差 >= 1)
        valid = []
        for p in positions:
            if not valid or p - valid[-1] >= 1:
                valid.append(p)
        if len(valid) >= min_repeats:
            # >=3 次: 截断到第一次出现之前; ==2 次: 截断到第二次出现之前
            cut_word_idx = valid[0] if len(valid) >= 3 else valid[1]
            prefix_text = ' '.join(ws[:cut_word_idx])
            return len(prefix_text)
    return -1


def _detect_long_phrase_loop(text: str, min_words: int = 6, max_words: int = 30, min_repeats: int = 2) -> int:
    """检测 text 中长度 [min_words, max_words] 的 phrase 重复 >= min_repeats 次."""
    import re as _re
    ws = _re.findall(r'\S+', text)
    n = len(ws)
    if n < min_words * min_repeats:
        return -1
    for L in range(min_words, min(max_words + 1, n // min_repeats + 1)):
        phrase_pos = {}
        for i in range(n - L + 1):
            ph = tuple(ws[i:i + L])
            if ph not in phrase_pos:
                phrase_pos[ph] = []
            phrase_pos[ph].append(i)
        for ph, positions in phrase_pos.items():
            if len(positions) < min_repeats:
                continue
            valid = []
            for p in positions:
                if not valid or p - valid[-1] >= 1:
                    valid.append(p)
            if len(valid) >= min_repeats:
                cut_word_idx = valid[0] if len(valid) >= 3 else valid[1]
                prefix_text = ' '.join(ws[:cut_word_idx])
                return len(prefix_text)
    return -1


def _detect_any_loop(text: str) -> int:
    """统一入口: 先查 3-gram (per user 10:26 spec), 查不到再查 6-30 词 phrase (long loop).
    返回 loop 起点 (char index), 没有 loop 则返回 -1.
    """
    idx = _detect_ngram_loop(text, n=3, min_repeats=3)
    if idx >= 0:
        return idx
    idx = _detect_long_phrase_loop(text, min_words=6, max_words=30, min_repeats=2)
    return idx


def _detect_prefix_overlap(gen_text: str, prefix: str, min_words: int = 6, max_words: int = 20) -> bool:
    """C-033#4: 检测 gen_text 前缀与 prefix 末尾 ≥6 个词重合.
    返回 True 表示检测到 overlap.
    用于 hallucination reset 第二触发条件: 模型生成的 text 在重复 prefix 末尾.
    """
    if not gen_text or not prefix:
        return False
    import re as _re
    gen_words = _re.findall(r'\S+', gen_text)
    prefix_words = _re.findall(r'\S+', prefix)
    if len(gen_words) < min_words or len(prefix_words) < min_words:
        return False
    for L in range(min_words, min(max_words, len(gen_words), len(prefix_words)) + 1):
        if prefix_words[-L:] == gen_words[:L]:
            return True
    return False


# ── C-047: 自适应生成长度（复刻 R2T2 官方 example.py:118-155）────────────
def _is_last_token_chinese(text: str) -> bool:
    """判断文本末字符是否为中文（对应官方 is_last_token_chinese）。"""
    t = str(text).rstrip()
    if not t:
        return False
    for ch in t[-1]:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


def _adaptive_budget_init(state, chunk_size_sec: float, lookahead_sec: float = 0.0):
    """按官方公式计算基准/上限，挂在 state 上（每段首次解码时初始化）。

    base  = max(1, int((step + lookahead) / 1280))     # 1280 samples ≈ 80 ms
    floor = min(32, max(4, 2 * int(step / 1280)))
    """
    step = int(round(chunk_size_sec * SAMPLE_RATE))
    look = int(round(lookahead_sec * SAMPLE_RATE))
    state._adp_base = max(1, int((step + look) / 1280))
    state._adp_floor = min(32, max(4, 2 * int(step / 1280)))
    state._adp_cur = state._adp_base
    state._adp_first = state._adp_base
    state._adp_last_len = 0


def _adaptive_budget_update(state, text_len: int, is_chinese: bool) -> int:
    """官方负反馈：文本增长 → 收紧到 base；停滞 → 放宽；中文 → 翻倍。"""
    if text_len > state._adp_last_len:
        state._adp_cur = state._adp_base
    else:
        if not is_chinese:
            state._adp_cur = state._adp_cur + 1
        else:
            state._adp_cur = state._adp_base
    if is_chinese:
        state._adp_cur = 2 * state._adp_cur
    state._adp_cur = min(state._adp_floor, state._adp_cur)
    state._adp_last_len = text_len
    return state._adp_cur


# ── 主循环（抄自 r2t2 第 302-578 行） ─────────────────────────────────
def streaming_transcribe(backend: ASRBackend,
                         pcm16k: np.ndarray,
                         state: ASRStreamingState,
                         max_new_tokens: int = None,
                         rollback_punctuation: bool = False,
                         enable_hallucination_reset: bool = True,
                         adaptive_budget: bool = False) -> tuple[str, str]:
    x = np.asarray(pcm16k)
    if x.ndim != 1:
        x = x.reshape(-1)
    if x.dtype == np.int16:
        x = (x.astype(np.float32) / 32768.0)
    else:
        x = x.astype(np.float32, copy=False)
    if x.shape[0] > 0:
        state.buffer = np.concatenate([state.buffer, x], axis=0)

    fixed_text = ""
    while state.buffer.shape[0] >= state.chunk_size_samples:
        chunk = state.buffer[: state.chunk_size_samples]
        state.buffer = state.buffer[state.chunk_size_samples:]

        if state.audio_accum.shape[0] == 0:
            state.audio_accum = chunk
        else:
            state.audio_accum = np.concatenate([state.audio_accum, chunk], axis=0)

        # C-033#4: 保存 prev state 以便 reset 时回退 (text, _raw_decoded, chunk_id)
        _prev_text = state.text
        _prev_raw_decoded = state._raw_decoded
        _prev_chunk_id = state.chunk_id

        # ── prefix rollback ──
        prefix = ""
        if state.chunk_id < state.unfixed_chunk_num:
            prefix = ""
        else:
            state._raw_decoded = state._raw_decoded.split("|")[0]
            cur_ids = backend.tokenizer.encode(state._raw_decoded)
            if rollback_punctuation is True:
                _punct = "，。！？、；：.!?;:"
                raw_stripped = state._raw_decoded.strip()
                if raw_stripped and raw_stripped[-1] in _punct:
                    k = 0
                else:
                    k = int(state.unfixed_token_num)
            else:
                k = int(state.unfixed_token_num)
            while True:
                end_idx = max(0, len(cur_ids) - k)
                prefix = backend.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ""
                if '\ufffd' not in prefix:
                    break
                if end_idx == 0:
                    prefix = ""; break
                k += 1
        prefix = prefix.split("|")[0]

        # ── C-047: 自适应生成长度（复刻官方 example.py:118-155）──
        # 固定 max_new_tokens 会让单次自回归失控直接写满冻结前缀（实测 n3=106）。
        # 官方按"文本是否还在增长"做负反馈：增长→收紧，停滞→放宽，上限 floor。
        _budget = max_new_tokens
        if adaptive_budget:
            if not hasattr(state, '_adp_base'):
                _adaptive_budget_init(state, state.chunk_size_sec)
            _budget = state._adp_cur

        # ── backend generate ──
        gen_text = backend.generate_with_prefix(
            state, state.audio_accum, prefix, _budget,
        )
        gen_text = _normalize_punct_by_context(gen_text).replace('\ufffd', '')
        state._raw_decoded = (prefix + gen_text) if prefix else gen_text

        lang = None
        if state.force_language is None:
            lang, _ = parse_language_output(state._raw_decoded, user_language=state.force_language)

        if state.force_language == "Chinese" or lang == "Chinese":
            state._raw_decoded = re.sub(
                r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', state._raw_decoded,
            )

        lang, txt = parse_asr_output(state._raw_decoded, user_language=state.force_language)

        # C-047: 用本轮全文长度更新下一次预算（负反馈）
        _is_zh = _is_last_token_chinese(txt)
        if adaptive_budget:
            _budget_next = _adaptive_budget_update(state, len(txt), _is_zh)
        else:
            _budget_next = _budget

        # C-050：中英混合场景诊断。state.diag_log 由 SegmentedStreamer
        # 在 enable_diag=True 时挂上，记录了每 chunk 的语言标签与生成预算，
        # 用于统计语言翻转次数和中文分支触发率。
        _dlg = getattr(state, 'diag_log', None)
        if _dlg is not None:
            _dlg.append({'chunk': state.chunk_id, 'lang': lang,
                         'budget': _budget, 'budget_next': _budget_next,
                         'is_chinese': bool(_is_zh), 'txt_len': len(txt)})

        has_tag = _ASR_TEXT_TAG in state._raw_decoded
        if has_tag:
            state._raw_decoded = state._raw_decoded.split(_ASR_TEXT_TAG)[0] + _ASR_TEXT_TAG + txt
        else:
            state._raw_decoded = txt

        state._raw_decoded = state._raw_decoded.split("|")[0]
        cur_ids = backend.tokenizer.encode(state._raw_decoded)
        if rollback_punctuation is True:
            _punct = "，。！？、；：,.!?;:"
            raw_stripped = state._raw_decoded.strip()
            if raw_stripped and raw_stripped[-1] in _punct:
                k = 0
            else:
                k = int(state.unfixed_token_num)
        else:
            k = int(state.unfixed_token_num)

        has_tag = _ASR_TEXT_TAG in state._raw_decoded
        if has_tag and state._raw_decoded.split(_ASR_TEXT_TAG)[1] == "":
            k = 0
        while True:
            end_idx = max(0, len(cur_ids) - k)
            fixed_text = backend.tokenizer.decode(cur_ids[:end_idx]) if end_idx > 0 else ""
            if '\ufffd' not in fixed_text:
                break
            if end_idx == 0:
                fixed_text = ""; break
            k += 1
        has_tag = _ASR_TEXT_TAG in fixed_text
        if has_tag:
            meta_part, fixed_text = fixed_text.split(_ASR_TEXT_TAG, 1)
        fixed_text = fixed_text.split("|")[0]

        has_tag = _ASR_TEXT_TAG in state._raw_decoded
        if not has_tag and state.force_language is None:
            state.text = ""
            fixed_text = ""
            continue

        state.language = lang
        # C-033#4: 先计算 proposed_text, 检查 loop, 再决定是否 commit 到 state.text
        proposed_text = txt.split("|")[0]

        # C-033#4 hallucination reset (新语义):
        # 检测 (a) 3-gram 连续 ≥3 次, 或 (b) gen_text 前缀与 prefix 末尾 ≥6 词重合
        # 触发时: 丢弃本次 gen_text, 保留上一步的 fixed_text, 下一个 chunk 照常继续
        # 同一段内连续触发 3 次就 finish 并重开一段
        loop_detected = False
        if enable_hallucination_reset:
            if _detect_any_loop(proposed_text) >= 0:
                loop_detected = True
            elif _detect_prefix_overlap(gen_text, prefix):
                loop_detected = True

        if loop_detected:
            # 软 reset: 回退 state 到本 chunk 处理前, 不更新 text/raw_decoded/chunk_id
            # (audio_accum/buffer 仍保留, 下一 chunk 会接续)
            state.text = _prev_text
            state._raw_decoded = _prev_raw_decoded
            state.chunk_id = _prev_chunk_id
            state._hallucination_reset = True
            state._n_consecutive_resets = getattr(state, '_n_consecutive_resets', 0) + 1
            if state._n_consecutive_resets >= 3:
                # 连续 3 次 reset: 该段已无可救药, 强制 finish 并重开段
                state._force_finish = True
                break
            # 否则: continue 到下一 chunk (state 已回退, 下一 chunk 会基于旧 fixed_text 重新生成)
            continue
        else:
            # 正常路径: commit proposed_text, 重置连续 reset 计数
            state.text = proposed_text
            state.chunk_id += 1
            state._n_consecutive_resets = 0

    return state.text, fixed_text


def finish_streaming_transcribe(backend: ASRBackend,
                                state: ASRStreamingState,
                                max_new_tokens: int = None) -> str:
    if state.buffer is None or state.buffer.shape[0] == 0:
        return state.text
    tail = state.buffer
    state.buffer = np.zeros((0,), dtype=np.float32)
    if state.audio_accum.shape[0] == 0:
        state.audio_accum = tail
    else:
        state.audio_accum = np.concatenate([state.audio_accum, tail], axis=0)

    prefix = ""
    if state.chunk_id < state.unfixed_chunk_num:
        prefix = ""
    else:
        cur_ids = backend.tokenizer.encode(state._raw_decoded)
        end_idx = max(1, len(cur_ids) - int(state.unfixed_token_num))
        prefix = backend.tokenizer.decode(cur_ids[:end_idx])
    prefix = prefix.split("|")[0]

    gen_text = backend.generate_with_prefix(
        state, state.audio_accum, prefix, max_new_tokens,
    )
    gen_text = _normalize_punct_by_context(gen_text).replace('\ufffd', '')
    state._raw_decoded = (prefix + gen_text) if prefix else gen_text
    state._raw_decoded = state._raw_decoded.split("|")[0]
    lang, txt = parse_asr_output(state._raw_decoded, user_language=state.force_language)
    state.language = lang
    state.text = txt.split("|")[0]
    state.chunk_id += 1
    return state.text


# ── 跑入口 ────────────────────────────────────────────────────────────
def run_streaming(backend: ASRBackend,
                  wav_path: str = 'C:/Users/Trekker-PTL/confucius4-r2t2/test.wav',
                  chunk_size_sec: float = 0.32,
                  unfixed_chunk_num: int = 2,
                  unfixed_token_num: int = 5,
                  max_new_tokens: int = 32,
                  rollback_punctuation: bool = False,
                  out_log: str = 'reports/stream_backend.log',
                  out_csv: str = 'reports/stream_chunks.csv',
                  warmup: bool = True):
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    assert sr == SAMPLE_RATE
    audio_dur = len(audio) / sr

    state = backend.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=chunk_size_sec,
    )

    # C-009 #1 预热：先完整跑一遍不计时，避开 OV 首次推理 kernel 编译
    if warmup and backend.name == "openvino":
        wstate = backend.init_streaming_state(
            unfixed_chunk_num=unfixed_chunk_num,
            unfixed_token_num=unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
        )
        feed_chunk_w = int(SAMPLE_RATE * 0.04)
        feed_pos_w = 0
        while feed_pos_w < len(audio):
            end = min(feed_pos_w + feed_chunk_w, len(audio))
            streaming_transcribe(
                backend, audio[feed_pos_w:end], wstate,
                max_new_tokens=max_new_tokens,
                rollback_punctuation=rollback_punctuation,
            )
            feed_pos_w = end
        # finish warmup
        finish_streaming_transcribe(backend, wstate, max_new_tokens=max(64, max_new_tokens))
        # 重置正式 state
        state = backend.init_streaming_state(
            unfixed_chunk_num=unfixed_chunk_num,
            unfixed_token_num=unfixed_token_num,
            chunk_size_sec=chunk_size_sec,
        )
        print(f'[stream] warmup pass done, starting timed run', flush=True)

    feed_chunk = int(SAMPLE_RATE * 0.04)  # 40 ms
    feed_pos = 0
    wall_start = time.perf_counter()

    rows = []
    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        text, fixed = streaming_transcribe(
            backend, audio[feed_pos:end], state,
            max_new_tokens=max_new_tokens,
            rollback_punctuation=rollback_punctuation,
        )
        feed_pos = end
        if state.chunk_id > len(rows):
            rows.append({
                'chunk_id': state.chunk_id,
                'text': state.text,
                'fixed': fixed,
                'audio_so_far_s': len(state.audio_accum) / SAMPLE_RATE,
                'elapsed_s': time.perf_counter() - wall_start,
                'n_tokens': len(backend.tokenizer.encode(state.text, add_special_tokens=False)),
            })

    final = finish_streaming_transcribe(backend, state, max_new_tokens=max(64, max_new_tokens))
    rows.append({
        'chunk_id': state.chunk_id,
        'text': state.text,
        'fixed': final,
        'audio_so_far_s': len(state.audio_accum) / SAMPLE_RATE,
        'elapsed_s': time.perf_counter() - wall_start,
        'n_tokens': len(backend.tokenizer.encode(state.text, add_special_tokens=False)),
        'final_flush': True,
    })
    wall_total = time.perf_counter() - wall_start

    os.makedirs(os.path.dirname(out_log), exist_ok=True)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_log, 'w', encoding='utf-8') as f:
        f.write(f"# {backend.name} streaming ASR\n")
        f.write(f"# chunk_ms={chunk_size_sec*1000:.0f} unfixed_chunk_num={unfixed_chunk_num} "
                f"unfixed_token_num={unfixed_token_num} max_new_tokens={max_new_tokens}\n")
        f.write(f"# audio_dur={audio_dur:.2f}s wall={wall_total:.2f}s RTF={wall_total/audio_dur:.3f}\n\n")
        for r in rows:
            tag = ' [final_flush]' if r.get('final_flush') else ''
            f.write(f"chunk {r['chunk_id']:2d}  t={r['elapsed_s']:6.2f}s  "
                    f"audio={r['audio_so_far_s']:.2f}s  tokens={r['n_tokens']:3d}  "
                    f"text={r['text']!r}{tag}\n")
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['chunk_id', 'elapsed_s', 'audio_so_far_s',
                                          'n_tokens', 'text', 'final_flush'])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in w.fieldnames})
    return {
        'final_text': state.text,
        'final_fixed': final,
        'rows': rows,
        'wall_s': wall_total,
        'audio_dur_s': audio_dur,
        'rtf': wall_total / audio_dur,
    }


# ── CLI ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    from backends import make_backend
    p = argparse.ArgumentParser()
    p.add_argument('--backend', default='openvino', choices=['torch', 'openvino'])
    p.add_argument('--model-dir', default=None)
    p.add_argument('--device', default='GPU.0')
    p.add_argument('--chunk-ms', type=float, default=320)
    p.add_argument('--unfixed-chunk-num', type=int, default=2)
    p.add_argument('--unfixed-token-num', type=int, default=5)
    p.add_argument('--max-new-tokens', type=int, default=32)
    p.add_argument('--wav', default='C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
    p.add_argument('--out-log', default='reports/stream_backend.log')
    p.add_argument('--out-csv', default='reports/stream_chunks.csv')
    args = p.parse_args()

    kw = {}
    if args.backend == 'torch':
        kw['model_dir'] = args.model_dir or 'models/hf'
    else:
        kw['model_dir'] = args.model_dir or 'models/ov-fp16-past'
        kw['device'] = args.device

    print(f'[stream] loading backend={args.backend} ({kw}) ...')
    t0 = time.perf_counter()
    backend = make_backend(args.backend, **kw)
    print(f'[stream] loaded in {time.perf_counter()-t0:.1f}s')

    res = run_streaming(
        backend, wav_path=args.wav,
        chunk_size_sec=args.chunk_ms / 1000,
        unfixed_chunk_num=args.unfixed_chunk_num,
        unfixed_token_num=args.unfixed_token_num,
        max_new_tokens=args.max_new_tokens,
        out_log=args.out_log, out_csv=args.out_csv,
    )
    print()
    print(f'[stream] FINAL text = {res["final_text"]!r}')
    print(f'[stream] {len(res["rows"])} chunks, wall={res["wall_s"]:.2f}s, '
          f'audio={res["audio_dur_s"]:.2f}s, RTF={res["rtf"]:.3f}')
    print(f'[stream] log → {args.out_log}')
    print(f'[stream] csv → {args.out_csv}')
