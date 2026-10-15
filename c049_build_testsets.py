"""c049_build_testsets.py — C-049: 构建中英文长音频测试集

背景:
  现有唯一测试集test_audio/260902_SPE_audio.wav 是 61.19min纯英文
  (NVIDIA QGS 会议)。自适应生成长度的中文分支 (is_last_token_chinese)
  从未在真实中文流式上验证过, 这是交付前最大风险点。
  且缺少「中英夹杂」场景 —— 真实会议/演讲里中英混说是常态。

本脚本:
  从 OpenSLR 公开语料(许可清晰、16kHz)构建三套 60min 级测试集:
    1) zh : AISHELL-1 test集拼接(普通话,官方人工转写)
    2) en : LibriSpeech test-clean 拼接(英文,官方转写)
    3) mix: zh/en 按段交替拼接(中英混合场景)

参考文本 (ground truth) 两种口径:
    - official: 直接用语料官方人工转写 (严谨, 可与文献基线对比)
    - minimax : 调 MiniMax cloud ASR 生成 (与现有 61min 口径统一)
  用 --ref-source 选择, 默认official。

产出 (test_data/sets/<name>/):
    audio.wav          16kHz mono PCM_16, 拼接后的长音频
    ref_official.txt   [start-end] text 每行一段
    ref_minimax.txt    MiniMax 转写 (仅 minimax 模式)
    manifest.json      段清单: 每段来源文件/起止/文本

用法:
  .venv python c049_build_testsets.py --target-min 60
  .venv python c049_build_testsets.py --lang zh --target-min 60
  .venv python c049_build_testsets.py --ref-source minimax --lang mix
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import soundfile as sf

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

SR = 16000
# 语料/产物根目录固定在脚本所在目录, 与调用时cwd 无关
ROOT = os.path.dirname(os.path.abspath(__file__))
TESTDATA = os.path.join(ROOT, 'test_data')
OUT_ROOT = os.path.join(TESTDATA, 'sets')


# ── 语料加载 ────────────────────────────────────────────────────────────
# AISHELL-1 官方 test 集说话人（20 人 / 7176 条，与官方 test 集规模一致）。
# OpenSLR 的 data_aishell.tgz 不含 train/dev/test 划分，这是社区通用的划分方式，
# 由 speaker id 顺序确定；已在 C-051 中核对 utterance 条数 = 7176。
AISHELL_TEST_SPK = [
    'S0764', 'S0765', 'S0766', 'S0767', 'S0768', 'S0769', 'S0770',
    'S0901', 'S0902', 'S0903', 'S0904', 'S0905', 'S0906', 'S0907', 'S0908',
    'S0912', 'S0913', 'S0914', 'S0915', 'S0916',
]


def load_aishell(splits=('test',), limit_sec=None):
    """AISHELL-1: wav/S<spk>.tar.gz 解压为 wav/S<spk>/test/.../*.wav。

    转写文件格式: BAC009S0002W0112 中午 天气 ... （人工标注，已按词/字空格分隔）
    utterance id 形如 BAC009S0764W0123 -> 说话人 = id[6:11]
    """
    tdir = os.path.join(TESTDATA, 'data_aishell', 'transcript')
    tpath = None
    for f in glob.glob(os.path.join(tdir, '*.txt')):
        tpath = f
        break
    if not tpath:
        raise SystemExit('AISHELL transcript 未找到, 先解压 data_aishell/')

    want = set(AISHELL_TEST_SPK)

    # 已解压的 wav 索引: utt_id -> path（解压后目录层级不固定，用一次性索引）
    index = {}
    for spk in sorted(want):
        base = os.path.join(TESTDATA, 'data_aishell', 'wav', spk)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                if fn.endswith('.wav'):
                    index[fn[:-4]] = os.path.join(root, fn)

    items = []
    for line in open(tpath, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        parts = line.split(' ', 1)
        if len(parts) != 2:
            continue
        utt, text = parts[0], parts[1].strip()
        if utt[6:11] not in want:
            continue
        wav = index.get(utt)
        if wav:
            items.append({'wav': wav, 'text': text, 'id': utt, 'lang': 'zh'})
    return items


def load_librispeech(split='test-clean', limit_sec=None):
    """LibriSpeech: 章节级 .trans.txt, 每行 "<utt-id> <TEXT>",
    对应同目录的 <utt-id>.flac (不是同名 .trans.txt)。
    """
    items = []
    for tpath in glob.glob(os.path.join(TESTDATA, 'LibriSpeech', split, '*', '*', '*.trans.txt')):
        d = os.path.dirname(tpath)
        for line in open(tpath, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            utt, _, text = line.partition(' ')
            wav = os.path.join(d, utt + '.flac')
            if text.strip() and os.path.exists(wav):
                items.append({'wav': wav, 'text': text.strip(), 'id': utt, 'lang': 'en'})
    return items


# ── 归一化 ──────────────────────────────────────────────────────────────
_PUNCT = re.compile(r'[^0-9a-z一-鿿\s]')


def norm_words(text):
    """中英统一归一化: 小写、去标点、英文按词切、中文按字切。

    中文没有词边界, 按字切是 CER 的标准做法; 英文按空白切词。
    混合文本时两者并存(所以中文按字 + 英文按词)。
    """
    t = text.lower()
    t = _PUNCT.sub(' ', t)
    out = []
    for tok in t.split():
        if re.search(r'[一-鿿]', tok):
            # 混合token (如 "gpu加速"): 拆成 中文单字 + 英文词
            for m in re.finditer(r'[一-鿿]+|[a-z0-9]+', tok):
                w = m.group(0)
                out.extend(list(w) if re.match(r'[一-鿿]', w) else [w])
        else:
            out.append(tok)
    return [w for w in out if w]


# ── 拼接 ────────────────────────────────────────────────────────────────
def build(items, out_dir, target_min, inter_seg_sec=0.35, max_items=None):
    """把 item 拼成一个长音频, 同时产出 [start-end] 格式的参考文本。"""
    os.makedirs(out_dir, exist_ok=True)
    target_sec = target_min * 60
    gap = np.zeros(int(inter_seg_sec * SR), dtype=np.float32)

    chunks, ref_lines, manifest = [], [], []
    pos, total = 0, 0.0

    for it in items:
        if total >= target_sec:
            break
        try:
            a, sr = sf.read(it['wav'], dtype='float32')
        except Exception:
            continue
        if sr != SR or a.ndim > 1:
            continue
        if len(a) < SR:      # 跳过 <1s 的碎片
            continue

        start, dur = total, len(a) / SR
        chunks.append(a)
        chunks.append(gap)
        total = start + dur + inter_seg_sec

        ref_lines.append((start, start + dur, it['text']))
        manifest.append({'id': it['id'], 'lang': it['lang'],
                         'start': round(start, 3), 'end': round(start + dur, 3),
                         'dur': round(dur, 3), 'src': os.path.basename(it['wav'])})
        if max_items and len(manifest) >= max_items:
            break

    if not chunks:
        raise SystemExit('没有可用音频')

    audio = np.concatenate(chunks)
    wav_out = os.path.join(out_dir, 'audio.wav')
    sf.write(wav_out, audio, SR, subtype='PCM_16')

    ref_out = os.path.join(out_dir, 'ref_official.txt')
    with open(ref_out, 'w', encoding='utf-8') as f:
        for s, e, txt in ref_lines:
            f.write(f'[{s:8.1f}-{e:8.1f}] {txt}\n')

    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'sr': SR, 'dur_min': round(total / 60, 2),
                   'n_segments': len(ref_lines),
                   'lang': manifest[0]['lang'] if manifest else '',
                   'segments': manifest}, f, ensure_ascii=False, indent=1)

    n_words = sum(len(norm_words(t)) for _, _, t in ref_lines)
    print(f'  时长 {total/60:.2f} min | 段数 {len(ref_lines)} | '
          f'归一化后 {n_words} 单元')
    print(f'  → {wav_out}')
    print(f'  → {ref_out}')
    return wav_out, ref_out


# ── 混合集: 中英按段交替 ─────────────────────────────────────────────────
def make_blocks(items, block_sec=25.0):
    """把同语言的 utterance 连续打包成 ~block_sec 一个的语言块。

    真实中英混合演讲是「连续说一段中文，再连续说一段英文」，
    而不是每句话都切换。逐句交替会产生每 3 秒一次的极端语码切换，
    既不符合真实场景，也会让每个 VAD 段都横跨两种语言。
    """
    blocks, cur, cur_dur = [], [], 0.0
    for it in items:
        cur.append(it)
        try:
            dur = sf.info(it['wav']).duration
        except Exception:
            dur = 0.0
        cur_dur += dur
        if cur_dur >= block_sec:
            blocks.append(cur)
            cur, cur_dur = [], 0.0
    if cur:
        blocks.append(cur)
    return blocks


def interleave(zh, en, block_sec=25.0):
    """中英语言块交替（zh 块、en 块轮流），块内连续同种语言。"""
    zb, eb = make_blocks(zh, block_sec), make_blocks(en, block_sec)
    out = []
    for i in range(max(len(zb), len(eb))):
        if i < len(zb):
            out.extend(zb[i])
        if i < len(eb):
            out.extend(eb[i])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', choices=['zh', 'en', 'mix'], default='mix')
    ap.add_argument('--target-min', type=float, default=60.0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--block-sec', type=float, default=25.0,
                    help='mix 集中每种语言连续说话的块长度(秒)')
    args = ap.parse_args()

    print(f'=== C-051 构建测试集: lang={args.lang} target={args.target_min}min ===')

    if args.lang in ('zh', 'mix'):
        zh = load_aishell()
        print(f'AISHELL-1 载入 {len(zh)} 段')
    if args.lang in ('en', 'mix'):
        en = load_librispeech()
        print(f'LibriSpeech 载入 {len(en)} 段')

    if args.lang == 'zh':
        items, name = zh, 'zh_60min'
    elif args.lang == 'en':
        items, name = en, 'en_60min'
    else:
        # 混合: 中英语言块交替, 块内连续同种语言
        items, name = interleave(zh, en, args.block_sec), 'mix_60min'

    out_dir = args.out or os.path.join(OUT_ROOT, name)
    print(f'→ {out_dir}')
    build(items, out_dir, args.target_min)
    print('完成。\n')


if __name__ == '__main__':
    main()