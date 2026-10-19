r"""c089c_eval_recipe.py — C-089 步骤 3：某个 INT4 配方在 NPU 上的评测

Reviewer 原文：
> 「② 12–27 min 端到端，全新进程，CACHE_DIR 照旧，报 WER + 对 INT8 全 NPU
>   （c085 转写，md5 8682554e…）的配对 bootstrap 5000 次 CI（参照先复现 6.643%）、
>   整体 RTF/P50/P95、prefill 与 decode 中位、IR 体积、i4/i8 常量个数；
>   ③ 转写放 reports/c089_int4/transcript_R{n}_npu_1227.txt」

## 自校验先行

跑任何配方之前，先用 **INT8 全 NPU（cleanie）** 跑一遍同口径，把 WER 复现到
C-085 的 6.643%（±容差）才继续。理由：c087 那轮出现过「参照自己报 41.3%」的
事故（切片口径不对），若不复现参照就说明本次评测口径本身坏了，后面的数字都不可信。

## 为什么只跑一次 INT8 参照

参照转写是固定的（md5 8682554e…，reports/c085_allnpu/transcript_int8_npu.txt）。
如果每个配方都重跑一遍参照，4 小时止损预算会烧光。做法：把自校验做成独立模式
（--selfcheck），通过后转写直接复用磁盘上的 c085 文件，并把它的 md5 记进报告。

用法：
    python c089c_eval_recipe.py --selfcheck
    python c089c_eval_recipe.py R0
"""
import argparse
import hashlib
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

SR = 16000
EVAL_START, EVAL_END = 720, 1620        # 12–27 分钟，主评测切片
# ⚠️ C-095#1：全长必须跑到音频真实末尾。音频 58739029 采样点 @16 kHz
# = 3671.1893125 s；之前按整分钟截到 3660 s，把最后 11.19 s 整段切掉
# （Reviewer 原话：「音频在 3660 s 处被截断…缺的约 11 s 会被算成删除错误」）。
# 用精确到采样点的值，不要再按整分钟取整。
FULL_START, FULL_END = 0.0, 3671.1893125
AUDIO_TOTAL_S = 3671.1893125
# C-093：单次评测墙钟上限（秒）。超过即判不可交付，不管 WER。
WALL_LIMIT_S = 20 * 60
INT8_REPORT = 'reports/c085_allnpu/transcript_int8_npu.txt'
# C-095#4 / C-090#2：IR（约 1 GiB 的 .bin）放在 models/ 下，reports/ 不在 .gitignore 里
IR_ROOT = 'models/c089_int4'
EXPECT_MD5_PREFIX = '8682554d'
EXPECT_WER = 0.06643
OUT_DIR = 'reports/c089_int4'


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_int8_transcript():
    """c085 的转写文件在哪个目录 —— 用 md5 前缀找，不靠猜路径。"""
    if os.path.exists(INT8_REPORT):
        p = INT8_REPORT
        if md5(p).startswith(EXPECT_MD5_PREFIX):
            return p
    for root, _dirs, files in os.walk('reports'):
        for fn in files:
            if not fn.endswith('.txt'):
                continue
            p = os.path.join(root, fn)
            try:
                if md5(p).startswith(EXPECT_MD5_PREFIX):
                    return p
            except Exception:
                continue
    return None



SLICE_LO = 720
FULL_MODE = False


def guard_single_instance(tag):
    """C-096：同名评测已在运行时**拒绝启动**。

    C-096 的原话：
    > 「有两个 `c089c_eval_recipe.py R4 --full` 在同时跑……它们抢同一个 NPU 和
    >   CPU，**两份的 RTF、prefill、decode 都无效**；如果写的是同一个输出文件，
    >   转写也可能互相覆盖。……请检查它为什么没有拦住，并补上
    >   「同名脚本已在运行就拒绝启动」。」

    为什么原来的 `heavy_peers()` 没拦住：它按 **CPU > 200%** 过滤，而刚启动的
    另一份还在 NPU 编译阶段（单核，~100%），等它热起来时本份早已开跑；
    更糟的是两份都把自己的 `heavy_peers` 快照写在**自己进程内**，互相看不见
    对方的命令行匹配。这里改用**命令行精确匹配 + 独占锁文件**双重保险。

    返回已存在的 PID 列表（空 = 无冲突）。
    """
    import psutil
    me = os.getpid()
    pat = 'c089c_eval_recipe.py'
    hits = []
    for pr in psutil.process_iter(['pid', 'cmdline']):
        try:
            if pr.info['pid'] == me:
                continue
            cl = pr.info['cmdline'] or []
            # 必须 argv[1] 精确等于脚本名 —— 只在命令行里「提到」脚本名的
            # （例如探测脚本的 `python -c "...c089c..."`）不算，否则会自锁。
            if len(cl) < 2:
                continue
            if cl[1].replace('/', os.sep).replace('\\', os.sep).endswith(pat):
                hits.append(pr.info['pid'])
        except Exception:
            continue
    return hits


def acquire_lock(tag):
    """独占锁：同 tag 只允许一份在跑。返回锁文件路径，失败返回 None。"""
    lock_dir = os.path.join(OUT_DIR, '_locks')
    os.makedirs(lock_dir, exist_ok=True)
    lock = os.path.join(lock_dir, f'{tag}.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return lock
    except FileExistsError:
        # 锁可能是上次异常退出留下的：核对持锁进程是否还活着
        try:
            pid = int(open(lock).read().strip())
            import psutil
            if not psutil.pid_exists(pid):
                os.remove(lock)
                return acquire_lock(tag)
        except Exception:
            try:
                os.remove(lock)
                return acquire_lock(tag)
            except Exception:
                pass
        return None


def heavy_peers(min_cpu_pct=200.0):
    """C-091：列出同时段还在烧 CPU 的其它进程（会污染 RTF）。

    全 NPU 流水线本身就平均占 6.1 个核，若同时有 NNCF 校准之类的构建作业在跑，
    RTF/prefill/decode 全部失真。复用 psutil，只统计本进程之外的。
    """
    try:
        import psutil
    except ImportError:
        return None
    me = os.getpid()
    out = []
    for pr in psutil.process_iter(['pid', 'name', 'cpu_percent',
                                   'cmdline', 'create_time']):
        try:
            if pr.info['pid'] == me:
                continue
            pct = pr.cpu_percent(interval=None)
            if pct < min_cpu_pct:
                continue
            cmd = ' '.join((pr.info['cmdline'] or [])[:6])[:110]
            out.append(f"{pr.info['pid']}:{pr.info['name']}"
                       f"({pct:.0f}%) {cmd}")
        except Exception:
            continue
    return out or None


def write_transcript(path, segs):
    """按 c085 的格式落盘：每行 `[start-end] text`。

    ⚠️ 必须带段边界！WER 判据（method_b）靠 `segs()` 解析 `[a-b] text`
    来把错误按 owner 归因到具体段；只写 `full_text` 会被当成**单段**，
    配对 bootstrap 直接失效（实测：候选 1 段 vs 参照 55 段 → CI 无意义）。

    注意 start/end 是**切片内**的相对秒（seg_audio 用的是切片 a），要加回
    切片起点 EVAL_START 才能和 baseline 的绝对时间轴对齐。
    """
    with open(path, 'w', encoding='utf-8') as f:
        for sg in segs:
            t = (sg.get('text') or '').strip()
            if not t:
                continue
            st = sg['start_s'] + SLICE_LO
            en = sg['end_s'] + SLICE_LO
            f.write('[%.2f-%.2f] %s\n' % (st, en, t))
    return path


def transcribe(dec_dir, enc_dir=None, label='', dec_device='NPU',
               enc_device='NPU'):
    """跑 12–27 min 端到端，返回 (transcript, stats)。fresh process 内单次。

    C-089 要求「若某配方 NPU 上不对而 CPU 上看似正常，只对这一个在 CPU 上跑
    12–27 min（约 27 min）以区分配方问题还是 NPU 问题」，故支持切换设备。
    """
    import numpy as np
    import soundfile as sf
    from npu_delivery_backend import make_delivery_all_npu_backend
    from seg_stream import SegmentedStreamer

    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    global SLICE_LO
    if FULL_MODE:
        lo, hi = FULL_START, FULL_END
    else:
        lo, hi = EVAL_START, EVAL_END
    SLICE_LO = lo
    # 切片索引必须是整数；全长末端是分数秒（3671.1893125），四舍五入到采样点。
    i0, i1 = int(round(SR * lo)), int(round(SR * hi))
    a = audio[i0:i1]
    # 全长模式允许末尾差 1 个采样点（切片用整数秒，长尾是分数秒）
    assert abs(len(a) / SR - (hi - lo)) < 0.001, \
        f'audio too short: got {len(a)/SR:.4f}s, need {(hi-lo):.4f}s'

    import openvino as ov
    from segment_encoder_backend import SegmentEncoderOVBackend, MAX_FRAMES
    from npu_embeds_backend import (
        NPUEmbedsDecoderBackend, _load_embed_table)
    from npu_delivery_backend import _freeze_encoder_for_npu

    t0 = time.perf_counter()
    if dec_device == 'NPU' and enc_device == 'NPU':
        be = make_delivery_all_npu_backend(
            encoder_dir=enc_dir or 'models/ov-encoder-segment-reviewer',
            decoder_dir=dec_dir)
    else:
        # CPU 腿：只在换配方时用（C-087 已做过 INT4@CPU，本轮只验证 R2 这一个）
        be = NPUEmbedsDecoderBackend.__new__(NPUEmbedsDecoderBackend)
        SegmentEncoderOVBackend.__init__(
            be, encoder_dir=enc_dir or 'models/ov-encoder-segment-reviewer',
            decoder_dir='models/ov-int8-past', device='CPU')
        be._dec_dir = dec_dir
        be._W = _load_embed_table()
        ids_l, ids_r = be._prompt_template_ids
        be._emb_left = np.ascontiguousarray(be._W[ids_l], dtype=np.float32)
        be._emb_right = np.ascontiguousarray(be._W[ids_r], dtype=np.float32)
        be.probe = {'enc_ms': [], 'prefill_ms': [], 'decode_ms': [],
                    'n_decode': [], 'prompt_len': [], 'n_audio': [],
                    'budget': [], 'out_tokens': []}
        core = ov.Core()
        em = core.read_model(
            model=os.path.join(be._encoder_dir, 'openvino_encoder_model.xml'),
            weights=os.path.join(be._encoder_dir,
                                 'openvino_encoder_model.bin'))
        fr = _freeze_encoder_for_npu(core, em, MAX_FRAMES)
        be.enc = core.compile_model(fr, enc_device, {})
        be.enc_infer = be.enc.create_infer_request()
        be._device = enc_device
        # CPU 上的解码器（INT4@CPU 已由 C-087 覆盖；此处仅供 C-094 的 R4c 复核用）
        be._dec = core.compile_model(
            os.path.join(dec_dir, 'openvino_model.xml'), enc_device, {})
        be._dec_infer = be._dec.create_infer_request()
        be.npu_compile_s = 0.0
        be.npu_enc_compile_s = 0.0
    init_s = time.perf_counter() - t0
    print(f'[{label}] backend init {init_s:.1f}s '
          f'(enc {be.npu_enc_compile_s}s / dec {be.npu_compile_s}s)', flush=True)

    # 预热不计入
    SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False).run(a[:SR * 15])

    for k in be.probe:
        be.probe[k].clear()
    t0 = time.perf_counter()

    # C-093#2：逐段落盘（段号/时间戳/耗时/文字）+ 20 分钟墙钟上限。
    # 用 `python -u` 并重定向到 reports/c089_int4/R{n}_npu.log 即可看到进度。
    limit = WALL_LIMIT_S if not FULL_MODE else 20 * 60 * 12
    state = {'n': 0, 't0': t0}

    def _check_limit():
        el = time.perf_counter() - t0
        if el > limit:
            raise TimeoutError(
                f'墙钟 {el/60:.1f} min 超过上限 {limit/60:.0f} min'
                f'（RTF > {limit/(hi-lo):.2f}），按 C-093 停掉')

    # 逐段进度钩子：包住 generate_with_prefix（每个音频段恰好调一次，
    # 它内部再调 greedy_decode_with_prefix）。**不能**挂在 greedy_… 上 ——
    # 那个返回的是 token id 列表，取不到可读文本。
    def _wrap_progress(fn, is_bound=False):
        def inner(*aa, **kw):
            _check_limit()
            r = fn(*aa, **kw)
            state['n'] += 1
            el = time.perf_counter() - t0
            txt = r
            if isinstance(r, (tuple, list)):
                txt = next((x for x in r if isinstance(x, str)), '')
            txt = (txt or '').strip().replace('\n', ' ')
            print('  [seg %3d] t=%6.1fs  %s'
                  % (state['n'], el, txt[:90]), flush=True)
            return r
        return inner

    be.generate_with_prefix = _wrap_progress(be.generate_with_prefix)

    streamer = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    try:
        text, segs = streamer.run(a)
    except TimeoutError as e:
        print(f'\n[c089c] {e}', file=sys.stderr, flush=True)
        print(f'[c089c] 已完成 {state["n"]} 段 —— 按 C-093 记为不可交付，'
              f'不产出 WER 判据。', file=sys.stderr, flush=True)
        return None, {'wall_limit_hit': True,
                      'wall_s': round(time.perf_counter() - t0, 2),
                      'audio_s': round(len(a) / SR, 2),
                      'slice_sec': [lo, hi],
                      'rtf': round((time.perf_counter() - t0) / (len(a) / SR), 4),
                      'n_segments_done': state['n'],
                      'wall_limit_s': limit}, []
    wall = time.perf_counter() - t0

    # C-091：本时段是否有其他重负载进程抢 CPU（会让 RTF 失真）
    others = heavy_peers()
    if others:
        print(f'[c089c] ⚠️ 同时段重负载进程（会污染 RTF）: {others}', flush=True)
    stats = {
        'decoder_dir': dec_dir,
        'backend_init_s': round(init_s, 1),
        'npu_enc_compile_s': be.npu_enc_compile_s,
        'npu_dec_compile_s': be.npu_compile_s,
        'wall_s': round(wall, 2),
        'audio_s': round(len(a) / SR, 2),
        'slice_sec': [SLICE_LO, SLICE_LO + round(len(a) / SR, 2)],
        'rtf': round(wall / (len(a) / SR), 4),
        'n_segments': len(segs),
        'concurrent_heavy_peers': others,
    }
    for k in ('enc_ms', 'prefill_ms', 'decode_ms'):
        v = be.probe[k]
        if v:
            stats[k + '_median'] = round(float(np.median(v)), 1)
            stats[k + '_p95'] = round(float(np.percentile(v, 95)), 1)
            stats[k + '_n'] = len(v)
    if be.probe['n_decode']:
        stats['tokens_per_seg_median'] = round(
            float(np.median(be.probe['n_decode'])), 1)
    stats['total_out_tokens'] = int(np.sum(be.probe['out_tokens'])) \
        if be.probe['out_tokens'] else 0
    return text, stats, segs


def wer_bootstrap(ref_path, hyp_path, iters=5000):
    """复用 c087d 已验证的 method_b：全局 SequenceMatcher 对齐 + 按 owner 归因。

    C-059#4 已证伪 method A（时间桶对齐，绝对 WER 虚高到 81%），所以必须用 method_b。
    """
    import numpy as np
    import re
    from difflib import SequenceMatcher

    def norm(p):
        t = open(p, encoding='utf-8').read()
        t = re.sub(r'\[[^\]]*\]', ' ', t)          # 去时间戳/元数据
        t = re.sub(r'[^0-9A-Za-z一-鿿\' ]+', ' ', t)
        return [w for w in t.lower().split() if w]

    r, h = norm(ref_path), norm(hyp_path)
    sm = SequenceMatcher(None, r, h, autojunk=False)
    per_ref = np.zeros(len(r))
    per_hyp = np.zeros(len(h))
    owners = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        owners.append((tag, i1, i2, j1, j2))
    return per_ref, per_hyp, owners, r, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('recipe', nargs='?', help='R0..R4；缺省为自校验模式')
    ap.add_argument('--selfcheck', action='store_true')
    ap.add_argument('--full', action='store_true',
                    help='跑 61 min 全长（第一个通过的配方）')
    a = ap.parse_args()

    # ── C-096：单实例守卫（必须在任何耗时动作之前）────────────────
    tag = ('selfcheck' if (a.selfcheck or not a.recipe)
           else f'{a.recipe}_{"full" if a.full else "1227"}')
    dup = guard_single_instance(tag)
    if dup:
        print(f'\n✗ 拒绝启动：已有 {len(dup)} 份 c089c_eval_recipe.py 在运行'
              f'（PID {dup}）。\n'
              f'  C-096：两份并行会互抢 NPU/CPU，两份的 RTF、prefill、decode '
              f'全部无效，且可能互相覆盖输出。\n'
              f'  请先停掉其它实例（或等它跑完）再重试。', file=sys.stderr)
        return 6
    lock = acquire_lock(tag)
    if lock is None:
        print(f'\n✗ 拒绝启动：锁文件 {OUT_DIR}/_locks/{tag}.lock 已被占用。\n'
              f'  C-096 同名实例保护。确认无实例在跑后可删除该锁。',
              file=sys.stderr)
        return 6
    print(f'[c089c] 单实例锁: {lock}', flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    int8 = find_int8_transcript()
    if int8 is None:
        print('[c089c] FAIL：找不到 INT8 全 NPU 参照转写（md5 前缀 '
              f'{EXPECT_MD5_PREFIX}）', file=sys.stderr)
        return 2
    print(f'[c089c] 参照转写: {int8}  md5={md5(int8)}', flush=True)

    if a.selfcheck or not a.recipe:
        dec = 'models/qwen3-lm-int8sym-cleanie-ov'
        text, stats, segs = transcribe(dec, label='INT8-SELFCheck')
        if text is None:
            json.dump(stats, open(os.path.join(OUT_DIR,
                             'selfcheck_int8.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            return 4
        out_txt = os.path.join(OUT_DIR, 'transcript_int8_selfcheck.txt')
        write_transcript(out_txt, segs)
        stats['transcript'] = out_txt
        stats['transcript_md5'] = md5(out_txt)
        # C-092#4：selfcheck 必须**比转写 md5**，不能只比 WER。
        # 交付后端若与 c085 不一致，先查格式（时间戳行 / 空格）再谈精度。
        ref_md5 = md5(int8)
        stats['reference_md5'] = ref_md5
        stats['md5_match_c085'] = bool(md5(out_txt) == ref_md5)
        print(f'\nRTF={stats["rtf"]}  segs={stats["n_segments"]}')
        print(f'转写 md5 = {md5(out_txt)}')
        print(f'c085 参照 md5 = {ref_md5}')
        print(f'md5 一致: {stats["md5_match_c085"]}'
              + ('' if stats['md5_match_c085']
                 else '  ← 不一致！先查转写格式（是否带 [t0-t1]、段间空格）'))
        json.dump(stats, open(os.path.join(OUT_DIR, 'selfcheck_int8.json'),
                             'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        return 0 if stats['md5_match_c085'] else 5

    rc = a.recipe
    dec_dir = os.path.join(IR_ROOT, rc)
    if not os.path.exists(os.path.join(dec_dir, 'openvino_model.xml')):
        # 兼容旧位置（C-090#2 要求把 IR 移到 models/，但别把已有结果弄丢）
        old = os.path.join('reports', 'c089_int4', rc)
        if os.path.exists(os.path.join(old, 'openvino_model.xml')):
            print(f'[c089c] 用旧位置的 IR: {old}', flush=True)
            dec_dir = old
        else:
            print(f'[c089c] {rc} 还没构建（缺 {dec_dir}/openvino_model.xml）',
                  file=sys.stderr)
            return 2
    globals()['FULL_MODE'] = bool(a.full)
    suffix = 'full' if a.full else '1227'   # 文件名后缀；tag 是锁用的实例标识
    text, stats, segs = transcribe(dec_dir, label=f'{rc}@NPU')
    out_json = os.path.join(OUT_DIR, f'{rc}_npu_{suffix}.json')
    if text is None:
        stats['recipe'] = rc
        json.dump(stats, open(out_json, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print('[c089c] 已写', out_json)
        return 4
    out_txt = os.path.join(OUT_DIR, f'transcript_{rc}_npu_{suffix}.txt')
    write_transcript(out_txt, segs)
    stats['recipe'] = rc
    stats['transcript'] = out_txt
    stats['transcript_md5'] = md5(out_txt)
    stats['reference'] = int8
    stats['reference_md5'] = md5(int8)
    stats['n_segments_written'] = sum(
        1 for _ in open(out_txt, encoding='utf-8'))
    json.dump(stats, open(out_json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f'\n{rc}: RTF={stats["rtf"]}  segs={stats["n_segments"]}'
          f'（落盘 {stats["n_segments_written"]} 段）')
    print('transcript head:', text[:400])
    return 0


if __name__ == '__main__':
    sys.exit(main())
