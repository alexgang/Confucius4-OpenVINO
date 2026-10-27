# -*- coding: utf-8 -*-
"""app113 — APP-033 ②：**CUDA 组**日文 A/B 实测（根因证明 + 回归）。

🔴🔴🔴 **必须持机器锁**（推理作业）⇒ 本脚本**自己取锁**（`machine_lock_app`，fail-closed）。
🔴 **不在 CPU 上跑推理** —— 设备 = **CUDA**（RTX 5050 / torch cu128）。
🔴 **不自己调用 MiniMax**（reviewer 侧 `quota.py` 在 **reviewer 本机**，
   目标机**不需要也不该有** ⇒ 见 APP-033 第 1 条 ⇒ 本脚本只负责
   **把 wav + json（含逐句 jsonl）落到固定位置**）。

## reviewer APP-033 第 2 条明文

> CUDA 组：用户 10-27 16:30–16:46 的实测走的是 CUDA 边车（`tts_cuda.py` + 边车自己的
> python），不依赖 dev/包内 python 的 torch。请按 **tts_cuda 实际使用的边车解释器**
> 做 CUDA A/B（日文 29 句×3 改前/改后，撞上限/RUNAWAY/挂起=0），
> 不要以"主 python 无 CUDA torch"为由跳过。找不到边车解释器再如实写明路径和报错。

## 🔴🔴🔴 本脚本纠正了前几轮的一个**事实错误**

§78/§79 的 STATUS 里写「CUDA 对照组客观做不了（本机 torch `2.14.1+cpu`、`cuda=False`；
包内 python 无 torch）」⇒ **那是「主 python / 包内 python」的事实**，
**不是「CUDA 边车」的事实**：

| 解释器 | 角色 | torch | CUDA |
|---|---|---|---|
| `C:\\Users\\Trekker-PTL\\_fq3tts_env\\Scripts\\python.exe` | **CUDA 边车实际用的** | `2.11.0+cu128` | **`cuda_available=True`** |
| `Confucius4_LiveCaption_v1.6\\python\\python.exe` | 包内主 python（ASR/MT/前端） | 无 torch | — |
| dev 的 `Python312\\python.exe` | dev 主 python | `2.14.1+cpu` | `False` |

⇒ **CUDA 组客观可做**（边车解释器 + 4.7 GB HF 缓存 + RTX 5050 8 GB 均实测就绪）。
⇒ 🔴 **撤回 §78/§79 头部「CUDA 对照组客观做不了」这条结论**。

## 两个臂的口径（**改前 = 完整旧实现**，不是只换语言）

reviewer APP-030 验收要「改前撞上限次数如实报告（用来证明根因）」⇒
**只换语言是不够的**（§78 的 NPU 组两个臂都传了 clamp 后的 `max_new_tokens`
⇒ 两臂都受帧上限保护 ⇒ 撞上限恒 0 ⇒ **没有复现根因**）。

| | 改前（before） | 改后（after） |
|---|---|---|
| 客户端 `tts_cuda.py` | **`d80ef22`**（APP-030 之前） | **HEAD** |
| 边车 `tts_cuda_sidecar.py` | **`d80ef22`**（不传 `max_new_tokens` ⇒ **库默认 2048 帧 = 163.8 s**） | **HEAD**（下发按句 clamp 的上限 + 回报 `frames`/`end_reason`） |
| 目标语言 | **`_guess_lang` 兜底**（只分 zh/en ⇒ 日文恒判 en 或 zh） | **显式下传 `ja` ⇒ Japanese** |
| RUNAWAY 守卫 | **无**（只有「多久没块」的看门狗） | **有**（客户端第二道闸） |
| `_q_get` 2 s 超时 | **直接抛** ⇒ **第 0 句必丢** | 超时返哨兵 ⇒ 看门狗按设计生效 |

⚠️ 两臂**各自独立**启动边车 ⇒ 各自加载一次模型（**不是同一进程内 A/B**）。

## 判据（reviewer 明文）

**改后（after）**：
- 撞上限（`end_reason == 'cap'`）= **0**
- RUNAWAY = **0**
- 挂起（单句墙钟 > `max(3×估计, 估计+8 s)`）= **0**
- **第 0 句丢失 = 0**（第一句必须真的产出音频）

**改前（before）**：撞上限 / RUNAWAY / 挂起 / 第 0 句丢失**如实报告**（用来证明根因）。

**回归**：中文 10 句 + 英文 10 句 ⇒ 改后帧数/s 字与改前一致（无回退）。

## 用法

    <pkg>/python/python.exe results/app/app113_cuda_ja_ab.py --repeats 3
"""
from __future__ import annotations

import argparse
import array
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
CORPUS = os.path.join(HOME, 'shared', 'app030_ja_corpus.json')
OUT_DIR = os.path.join(HOME, 'app030_cuda_ab')

#: 🔴🔴 **APP-030 之前的 commit**（= 「改前」臂的源码来源）
#:   `a9ed250` = 「App §75: APP-030 日文失控修复(代码侧 5 项全完成)」
#:   ⇒ 它的**父提交** `d80ef22` = APP-030 修复**之前**的实现。
BEFORE_COMMIT = 'd80ef22'

#: 库默认的生成帧数上限（`faster_qwen3_tts.generate_voice_clone_streaming`
#:   的 `max_new_tokens` 默认值）= 2048 帧 = 163.8 s 音频（12 fps）
#:   ⇒ reviewer 实测一句 7 字日文跑了 106.61 s / 255 块 / 163.0 s 音频。
LIB_DEFAULT_MAX_NEW_TOKENS = 2048

#: 🔴 **「撞上限」的判定阈值（改前臂用）**
#:   改前的边车**不回报 `end_reason`** ⇒ 只能从「实际帧数」反推。
#:   reviewer 实测失控句 = **2038 帧**（上限 2048）⇒ 阈值取 0.97×2048 = 1986。
#:   ⚠️ 正常句的帧数远低于此（短假名句 ~11 帧、典型句 ~50–150 帧）
#:   ⇒ **不会误判正常句**。
CAP_THRESHOLD = int(LIB_DEFAULT_MAX_NEW_TOKENS * 0.97)

#: 🔴 **codec 每帧的采样数** = 1920（24 kHz ⇒ 12.5 fps）
#:   依据：reviewer 实测 `samples=3912960` ⇔ `2038 帧`
#:   ⇒ 3912960 / 2038 = 1920 ⇒ 折算系数 = 24000 / 1920 = **12.5 fps**。
#:   ⚠️ **不是 12.0** ⇒ 用 12.0 会把帧数少算 4%（2038 → 1956 ⇒ 漏判撞上限）。
FRAME_SAMPLES = 1920
FPS = 24000.0 / FRAME_SAMPLES   # = 12.5

#: 单句 wav 的最大秒数（超过则截断落盘，避免失控句写出几百 MB）
WAV_MAX_S = 60.0


def _lock():
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    return ml


def _git_show(commit, relpath):
    """取某 commit 里的文件内容（bytes）。"""
    p = subprocess.run(['git', 'show', '%s:%s' % (commit, relpath)],
                       cwd=REPO, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError('git show %s:%s 失败：%s'
                           % (commit, relpath,
                              p.stderr.decode('utf-8', 'replace')[:400]))
    return p.stdout


def _extract_before_arm(tmpdir):
    """把「改前」臂的两个文件（客户端 + 边车）抽到临时目录。

    🔴 **为什么要抽出来而不是 `git show` 到内存**：客户端用
      `os.path.dirname(__file__)` 定位**边车脚本** ⇒ 两个文件必须**同目录**。
    """
    os.makedirs(tmpdir, exist_ok=True)
    for rel in ('live_caption/tts_cuda.py', 'live_caption/tts_cuda_sidecar.py'):
        dst = os.path.join(tmpdir, os.path.basename(rel))
        with open(dst, 'wb') as f:
            f.write(_git_show(BEFORE_COMMIT, rel))
    return tmpdir


def _old_guess_lang(text):
    """**旧实现**的 `_guess_lang`（`d80ef22:tts_worker.py` L1889）。

    ```python
    cjk = sum(1 for ch in text if '\\u4e00' <= ch <= '\\u9fff')
    return 'zh' if cjk * 4 >= len(text) else 'en'
    ```
    ⇒ **只分 zh/en** ⇒ 日文永远判不出来（reviewer 实测 8 条日文样句
    **5 条判 en、3 条判 zh**）。
    """
    cjk = sum(1 for ch in (text or '') if '\u4e00' <= ch <= '\u9fff')
    return 'zh' if cjk * 4 >= len(text) else 'en'


def _lang_full(code):
    """语言代号 ⇒ 引擎用的全称（与 `tts_engine.map_language` 一致）。"""
    return {'zh': 'Chinese', 'en': 'English',
            'ja': 'Japanese', 'ko': 'Korean'}.get(code, 'English')


def _write_wav(path, samples, sr=24000):
    """把 float32 采样写成 wav（16 bit PCM）。用 numpy 加速（避免逐样本 struct.pack）。"""
    import numpy as np
    a = np.asarray(samples, dtype=np.float32).reshape(-1)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype('<i2').tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return len(pcm)


def _purge_tts_cuda_modules():
    for m in list(sys.modules):
        if m == 'tts_cuda' or m.startswith('tts_cuda_'):
            del sys.modules[m]


def _file_sha256(path):
    """文件 SHA256（十六进制全串）。不存在返回 None。"""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for blk in iter(lambda: f.read(1 << 20), b''):
                h.update(blk)
        return h.hexdigest()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--out', default=None)
    ap.add_argument('--limit', type=int, default=0,
                    help='只跑前 N 句日文（0 = 全部 29 句）')
    ap.add_argument('--skip-before', action='store_true',
                    help='跳过「改前」臂（只跑改后）')
    ap.add_argument('--skip-after', action='store_true',
                    help='跳过「改后」臂')
    ap.add_argument('--skip-reg', action='store_true',
                    help='跳过 zh/en 回归')
    ap.add_argument('--reg-langs', default='zh,en',
                    help='回归语言（逗号分隔）')
    ap.add_argument('--quiet-timeout', type=float, default=3600.0,
                    help='安静窗口等待上限（秒）—— 默认 3600 s，'
                         '因为同机常有别的模块的推理作业在跑（fail-closed 等锁）')
    ap.add_argument('--max-wall-per-sentence', type=float, default=180.0,
                    help='单句墙钟上限（秒）—— 超过则 cancel 该句并记为 hang_cut')
    ap.add_argument('--no-wav', action='store_true', help='不落盘 wav')
    # 🔴🔴🔴 **改后臂语言口径**（本轮实测后新增，必读）
    #   `fixed_ja` = **reviewer APP-030 明文口径**：「改后（lang=Japanese）」
    #      ⇒ 29 句**全部**强制 Japanese（含语料里其实是中文内容的 seq=7/20/21）
    #   `production` = **真实生产行为**：改后臂的语言用
    #      `tts_engine.guess_language_by_script(text)`（APP-030① 的修法本体）
    #      ⇒ 主进程显式下传时本就用它；兜底时才用它
    ap.add_argument('--after-lang', default='fixed_ja',
                    choices=['fixed_ja', 'production'],
                    help='改后臂语言口径（默认 fixed_ja = reviewer 明文）')
    # 🔴 **定向复跑**：只跑指定的句子序号（逗号分隔）⇒ 用于定性某一句的异常
    ap.add_argument('--focus-seq', default='',
                    help='只跑这些句子序号（逗号分隔），与 --limit 互斥')
    # 🔴🔴 **自定义对照文本**（本轮自查抓出 seq=7 的嫌疑点后新增）
    #   格式：`lang_code=text1;;lang_code=text2`（用 `;;` 分隔多条）
    #   ⇒ 用于**对照实验**（同一句改一个字，看异常是否跟随）
    #   ⚠️ `text` 里不要含 `;;`；换行用 `\n` 转义。
    ap.add_argument('--custom-text', default='',
                    help='自定义对照文本，如 "ja=动きます;;ja=，动きます"')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    wav_dir = os.path.join(OUT_DIR, 'wav')
    os.makedirs(wav_dir, exist_ok=True)
    out_path = args.out or os.path.join(OUT_DIR, 'cuda_ja_ab_report.json')
    # 🔴🔴🔴 **jsonl 路径必须跟 `--out` 联动**（本轮自查抓出的脚本缺陷）
    #   旧实现把 jsonl 写死成 `cuda_ja_ab_sentences.jsonl`
    #   ⇒ 任何**定向复跑**（`--out 别的名字`）都会**覆盖掉正式产物的逐句 jsonl**
    #   ⇒ 实测已发生一次（正式 194 行 jsonl 被复跑清空）。
    #   ✅ 修法：jsonl 与 report **同名同目录** ⇒ 一一对应、不会互相覆盖。
    jsonl_path = os.path.splitext(out_path)[0] + '_sentences.jsonl'

    if not os.path.exists(CORPUS):
        print('!! 找不到语料：%s' % CORPUS)
        return 2
    with open(CORPUS, encoding='utf-8') as f:
        corpus = json.load(f)
    ja = list(corpus['ja'])
    #: 自定义对照文本的显式语言（`None` ⇒ 不是自定义模式）
    custom_codes = None
    # 🔴 **自定义对照文本** ⇒ 覆盖语料（用于对照实验）
    if args.custom_text:
        custom = []
        for chunk in args.custom_text.split(';;'):
            chunk = chunk.strip()
            if not chunk:
                continue
            code, _, txt = chunk.partition('=')
            custom.append((code.strip(), txt.replace('\\n', '\n')))
        ja = [t for _c, t in custom]
        custom_codes = [c for c, _t in custom]
        print('[corpus] 自定义对照文本 %d 条：%s'
              % (len(ja), [c for c, _t in custom]))
    elif args.focus_seq:
        keep = set(int(x) for x in args.focus_seq.split(',') if x.strip())
        ja = [s for i, s in enumerate(ja) if i in keep]
        print('[corpus] 定向复跑，句子序号 = %s' % sorted(keep))
    elif args.limit:
        ja = ja[:args.limit]

    # ── 环境探测（**只做一次**）─────────────────────────────────
    print('[env] 探测边车解释器 …')
    env_info = {}
    sidecar_py = None
    try:
        sys.path.insert(0, os.path.join(REPO, 'live_caption'))
        import tts_cuda as _tc
        sidecar_py = _tc.python_exe()
        env_info['sidecar_python'] = sidecar_py
        env_info['sidecar_available'] = bool(_tc.available())
        print('[env] 边车解释器=%s  available=%s'
              % (sidecar_py, env_info['sidecar_available']))
    except Exception as e:
        print('!! 无法确定边车解释器：%s: %s' % (type(e).__name__, e))
        return 2
    if not env_info.get('sidecar_available'):
        print('!! 边车不可用（available()=False）⇒ 退出（如实报告，不跳过）')
        return 2

    try:
        p = subprocess.run(
            [sidecar_py, '-c',
             'import torch;'
             'print("torch",torch.__version__);'
             'print("cuda_available",torch.cuda.is_available());'
             'print("cuda_version",torch.version.cuda);'
             'print("device",torch.cuda.get_device_name(0))'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        out = p.stdout.decode('utf-8', 'replace')
        env_info['sidecar_torch_probe'] = out.strip()
        print('[env] ' + out.strip().replace('\n', ' | '))
    except Exception as e:
        env_info['sidecar_torch_probe_error'] = '%s: %s' % (type(e).__name__, e)
        print('!! 边车 torch 探测失败：%s' % e)

    ml = _lock()
    print('[lock] 申请共享机器锁 …')
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下跑推理）')
        return 3
    print('[lock] 已取得：%r' % (payload,))
    rows = []
    jsonl_f = open(jsonl_path, 'w', encoding='utf-8', newline='\n')
    try:
        print('[lock] 等安静窗口 …')
        ok_quiet, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                   timeout=args.quiet_timeout,
                                                   verbose=True)
        print('[lock] 安静窗口 ok=%s info=%r' % (ok_quiet, qinfo))
        if not ok_quiet:
            print('[lock] !! 没有安静窗口 ⇒ 退出（不与他模块的计时作业抢）')
            return 4

        import tts_engine as TE

        # ── 跑一个臂 ────────────────────────────────────────────
        def run_arm(arm, mod_dir, items, pass_mnt, tag_prefix):
            """跑一个臂。

            @param mod_dir   客户端 + 边车所在目录（两臂不同 ⇒ 独立进程/独立模型）
            @param items     [(text, lang_code, reps, tag), ...]
                            ⇒ **每条自带重复次数与标签** ⇒ 日文 ×3（tag `ja_ja`）、
                              回归 ×1（tag `reg_zh` / `reg_en`）
                            ⇒ **一个臂只加载一次模型**（不重复加载）
            @param pass_mnt  是否下发按句 clamp 的 `max_new_tokens`
            """
            if os.path.abspath(mod_dir) not in [os.path.abspath(p or '.')
                                                for p in sys.path]:
                sys.path.insert(0, mod_dir)
            _purge_tts_cuda_modules()
            import tts_cuda as TC
            eng = None
            arm_rows = []
            try:
                t0 = time.time()
                eng = TC.CudaTTSEngine(on_log=lambda m: None)
                # 🔴🔴 **显式 `start()`**（与生产路径 `tts_worker._make_engine`
                #   完全一致：worker 是 `eng = CudaTTSEngine(...); eng.start()`）
                #   ⇒ **模型加载 + warmup 不计入任何一句的墙钟**
                #   ⇒ 否则第 1 句会背 30 s 的加载时间 ⇒ 挂起判据假阳性。
                print('\n[arm %s] 边车启动中（加载模型 + warmup）…' % arm)
                eng.start()
                print('[arm %s] 边车就绪：device=%r load_s=%r warmup_s=%r'
                      % (arm, eng.device_name, eng.load_s, eng.warmup_s))
                for i, (text, code, reps, item_tag) in enumerate(items):
                    for rep in range(reps):
                        full = _lang_full(code)
                        est_frames = TE.estimate_frames(text, code)
                        est_sec = TE.estimate_sec(text, code)
                        mnt = (TE.clamp_max_new_tokens(text, code)
                               if pass_mnt else None)
                        got_sec = 0.0
                        n_chunks = 0
                        reason = 'eos'
                        err = None
                        samples = array.array('f')
                        # 🔴 **清掉上一句的引擎状态** ⇒ 否则这一句若在 done 之前
                        #   失败，会读到**上一句**的 `_last_frames` / `_last_end_reason`
                        for attr in ('_last_frames', '_last_end_reason'):
                            if hasattr(eng, attr):
                                try:
                                    setattr(eng, attr, None)
                                except Exception:
                                    pass
                        cancel = threading.Event()
                        # 🔴 **墙钟上限用定时器置位 `cancel_event`**（不是循环里 break）
                        #   ⇒ 走的是**生产路径的取消分支**（客户端每条消息前查
                        #     `cancel_event` ⇒ 命中后 `_start_drain` 排空本请求）
                        #   ⇒ 不会留下「上一句的块污染下一句」的错位。
                        timer = threading.Timer(
                            args.max_wall_per_sentence, cancel.set)
                        timer.daemon = True
                        timer.start()
                        t1 = time.perf_counter()
                        try:
                            # 🔴 **走生产路径**（`tts_engine.stream`）⇒
                            #   与 `tts_worker._synth_babelvox` 完全一致
                            #   （含 `normalize_zh_numbers` / `chunk_frames` /
                            #     `max_new_tokens` / `est_sec` 的下传规则）。
                            kwargs = dict(speaker_embed=None, speaker=None,
                                           cancel_event=cancel)
                            if pass_mnt:
                                kwargs['max_new_tokens'] = int(mnt)
                                kwargs['est_sec'] = float(est_sec)
                            for chunk, sr in TE.stream(
                                    eng, text, language=full, **kwargs):
                                got_sec += len(chunk) / float(sr or 24000)
                                n_chunks += 1
                                if len(samples) < 24000 * WAV_MAX_S:
                                    samples.extend(chunk)
                        except Exception as e:
                            err = '%s: %s' % (type(e).__name__, e)
                            reason = 'error'
                        finally:
                            timer.cancel()
                        wall = time.perf_counter() - t1
                        # 🔴 定时器把 `cancel_event` 置位 ⇒ 客户端走取消分支
                        #   ⇒ 本句被主动中止 ⇒ 记为 `hang_cut`（不是 eos）
                        if cancel.is_set() and reason == 'eos':
                            reason = 'hang_cut'
                        n_chars = len([c for c in text if not c.isspace()])
                        # 实际帧数：优先用引擎回报；改前臂没有 ⇒ 用音频秒 × 12 fps 折算
                        frames = getattr(eng, '_last_frames', None)
                        frames_src = 'engine'
                        if frames is None:
                            frames = int(round(got_sec * FPS))
                            frames_src = 'audio_sec_x12'
                        # 撞上限判定（改前臂没有 end_reason ⇒ 用帧数判）
                        if reason == 'eos' and frames_src == 'audio_sec_x12':
                            if frames >= CAP_THRESHOLD:
                                reason = 'cap'
                        eng_reason = getattr(eng, '_last_end_reason', None)
                        if eng_reason in ('cap', 'runaway'):
                            reason = eng_reason
                        hang = wall > max(3 * est_sec, est_sec + 8.0)
                        if hang and reason == 'eos':
                            reason = 'hang'
                        wav_path = None
                        if not args.no_wav and len(samples):
                            wav_path = os.path.join(
                                wav_dir, '%s_%03d_r%d_%s.wav'
                                % (arm, i, rep, code))
                            try:
                                _write_wav(wav_path, samples)
                            except Exception:
                                wav_path = None
                        row = dict(
                            arm=arm,
                            tag=item_tag,
                            rep=rep, seq=i, lang_code=code, lang_down=full,
                            text=text, n_chars=n_chars,
                            est_frames=int(est_frames), est_sec=round(est_sec, 3),
                            max_new_tokens=(int(mnt) if mnt is not None
                                            else 'LIB_DEFAULT_2048'),
                            chunks=n_chunks, got_sec=round(got_sec, 3),
                            frames=int(frames or 0), frames_src=frames_src,
                            s_per_char=round(wall / max(1, n_chars), 4),
                            wall_s=round(wall, 3),
                            end_reason=reason, hang=bool(hang),
                            error=err, wav=wav_path,
                        )
                        arm_rows.append(row)
                        rows.append(row)
                        jsonl_f.write(json.dumps(row, ensure_ascii=False) + '\n')
                        jsonl_f.flush()
                        print('  [%s %2d r%d] lang=%-8s est_f=%4d got=%7.2fs '
                              'f=%4d(%s) s/字=%.3f %s %s'
                              % (arm, i, rep, full, row['est_frames'],
                                 row['got_sec'], row['frames'], frames_src,
                                 row['s_per_char'], row['end_reason'],
                                 'HANG' if hang else ''))
            finally:
                if eng is not None:
                    try:
                        eng.close()
                    except Exception:
                        pass
                print('[arm %s] 用时 %.1f s' % (arm, time.time() - t0))
            return arm_rows

        # ══ 改前臂 ══════════════════════════════════════════════
        if not args.skip_before:
            tmp_before = _extract_before_arm(
                os.path.join(tempfile.gettempdir(), 'app113_before'))
            print('\n=== 改前臂（源码 = %s）===' % BEFORE_COMMIT)
            # 改前臂：语言 = 旧 `_guess_lang` 兜底
            items_before = [(t, _old_guess_lang(t), args.repeats, 'ja_%s'
                          % _old_guess_lang(t)) for t in ja]
            run_arm('before', tmp_before, items_before,
                    pass_mnt=False, tag_prefix='ja_')
            shutil.rmtree(tmp_before, ignore_errors=True)
            _purge_tts_cuda_modules()
            sys.path[:] = [p for p in sys.path
                           if os.path.abspath(p or '.')
                           != os.path.abspath(tmp_before)]

        # ══ 改后臂 ══════════════════════════════════════════════
        if not args.skip_after:
            print('\n=== 改后臂（源码 = HEAD）===')
            # 🔴🔴🔴 **两种语言口径**（本轮实测后并列给出，两者都报）
            #
            #   `fixed_ja` = **reviewer APP-030 明文口径**：
            #     「**改后**（lang=Japanese）各跑」⇒ 29 句**全部**强制 Japanese
            #     ⇒ ⚠️ 语料 `ja` 桶里 **seq=7 / seq=20 / seq=21 其实是中文内容**
            #       （app108 语料脚本把它们放在 §④「≥60 字长句」分类下）
            #     ⇒ 用 Japanese token 读中文 = **分布外** ⇒ 有帧数异常的风险
            #     ⇒ **这是 reviewer 指定的验收口径，不是脚本缺陷**。
            #
            #   `production` = **真实生产行为**：改后臂语言用
            #     `tts_engine.guess_language_by_script(text)`（APP-030① 的修法本体）
            #     ⇒ 主进程显式下传时本就用它；兜底时才用它。
            #
            #   ⇒ 两臂都跑 ⇒ 可同时回答「reviewer 指定口径过不过」
            #     与「生产行为过不过」。
            if custom_codes is not None:
                # 🔴 **自定义对照文本**：语言由命令行显式指定
                items_after = [(t, c, args.repeats, 'ja_ja')
                               for t, c in zip(ja, custom_codes)]
            elif args.after_lang == 'fixed_ja':
                items_after = [(t, 'ja', args.repeats, 'ja_ja') for t in ja]
            else:
                items_after = [(t, TE.guess_language_by_script(t),
                                args.repeats, 'ja_ja') for t in ja]
            if not args.skip_reg:
                for code in [c.strip() for c in args.reg_langs.split(',')
                             if c.strip()]:
                    for t in corpus.get(code, []):
                        items_after.append((t, code, 1, 'reg_%s' % code))
            run_arm('after', os.path.join(REPO, 'live_caption'), items_after,
                    pass_mnt=True, tag_prefix='ja_')

        # ── 汇总 ────────────────────────────────────────────────
        def agg(rs):
            if not rs:
                return dict(n=0, cap=0, runaway=0, hang=0, err=0,
                            hang_cut=0, first_sentence_lost=0, no_audio=0)
            first = rs[0]
            return dict(
                n=len(rs),
                cap=sum(1 for r in rs if r['end_reason'] == 'cap'),
                runaway=sum(1 for r in rs if r['end_reason'] == 'runaway'),
                hang=sum(1 for r in rs if r['hang']),
                err=sum(1 for r in rs if r['error']),
                hang_cut=sum(1 for r in rs if r['end_reason'] == 'hang_cut'),
                # 🔴 「第 0 句丢失」：**第一句必须真的产出音频**
                first_sentence_lost=int(first['got_sec'] <= 0
                                        or bool(first['error'])),
                no_audio=sum(1 for r in rs if r['got_sec'] <= 0),
                got_sec_med=(sorted(r['got_sec'] for r in rs)[len(rs) // 2]
                             if rs else 0),
                s_per_char_med=(sorted(r['s_per_char'] for r in rs)[len(rs) // 2]
                                if rs else 0),
                frames_med=(sorted(r['frames'] for r in rs)[len(rs) // 2]
                            if rs else 0),
            )

        ja_before = [r for r in rows if r['arm'] == 'before'
                     and r['tag'].startswith('ja_')]
        ja_after = [r for r in rows if r['arm'] == 'after'
                    and r['tag'] == 'ja_ja']
        reg = [r for r in rows if r['tag'].startswith('reg_')]

        summary = dict(before=agg(ja_before), after=agg(ja_after),
                       regression=agg(reg))
        ok = (summary['after']['cap'] == 0
              and summary['after']['runaway'] == 0
              and summary['after']['hang'] == 0
              and summary['after']['first_sentence_lost'] == 0)
        summary['verdict_after_clean'] = ok

        report = dict(
            summary=summary, rows=rows, env=env_info,
            before_commit=BEFORE_COMMIT, corpus_file=CORPUS,
            corpus_sha256=_file_sha256(CORPUS),
            corpus_ja_count=len(ja),
            after_lang_mode=args.after_lang,
            jsonl=jsonl_path, wav_dir=wav_dir, repeats=args.repeats,
            ts=time.strftime('%Y-%m-%d %H:%M:%S'),
            note=('CUDA 组实测（边车解释器 = %s）；持机器锁；'
                      '不在 CPU 上跑推理；不调用 MiniMax'
                      % env_info.get('sidecar_python')),
        )
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('\n' + '=' * 68)
        print('汇总：%s' % json.dumps(summary, ensure_ascii=False, indent=1))
        print('改后判据 verdict_after_clean = %s' % ok)
        print('报告：%s' % out_path)
        print('逐句 jsonl：%s' % jsonl_path)
        print('wav 目录：%s' % wav_dir)
        return 0 if ok else 1
    finally:
        try:
            jsonl_f.close()
        except Exception:
            pass
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%s' % e)


if __name__ == '__main__':
    sys.exit(main())
