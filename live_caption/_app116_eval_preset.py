#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §2：**预设 A（女声）vs 预设 B（男声）**的 CER/WER 对比 + 抽听样本。

reviewer 要求：
  「preset_B 合成 zh/en 各 10 句，回转写 CER/WER 与 preset_A 同一水平（reviewer 复核）；
    挑 4 条放到 `results/app/app116_preset_b_listen/` 给用户抽听，
    **用户点头前不进包**。」

流程：
  ① 用 **dev 树**的 tts_worker（OV/babelvox 后端，GPU.0）合成 10 zh + 10 en；
     预设 A 与预设 B 各一遍 ⇒ 40 段 wav（--dump-dir 逐句落盘）。
     🔴 dev 树的 `models/qwen3tts/{int8,tokenizer,weights}` 是**指向客户包的
        junction**（不复制 14 GB；**不改包本身**）；`voices/` 是真实目录，
        里面有 preset_A.wav（包的原件）与 preset_B.wav（本轮模型生成的男声）。
  ② 用**仓库现成的** OV ASR（`backends.OVBackend`，models/ov-int8-past，GPU.0）
     逐段回转写。
  ③ CER（中文，按字）/ WER（英文，按词）对比两个音色。
  ④ 挑 4 条（zh 2 + en 2）放进 `results/app/app116_preset_b_listen/` 给用户抽听。

🔴 **GPU 作业**：运行前必须**持共享机器锁**（本脚本自己取，排队等待，不抢）。
"""
import argparse
import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
DEV = os.path.join(REPO, 'live_caption')
RESULTS = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(RESULTS, 'app116_preset_eval')
LISTEN = os.path.join(RESULTS, 'app116_preset_b_listen')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
PKG_PY = os.path.join(HOME, 'Confucius4_LiveCaption_v2.4', 'python', 'python.exe')

ZH = [
    '今天天气很好，我们去公园里走一走吧。',
    '这份报告需要在本周五之前完成提交。',
    '会议将在下午三点开始，请提前十分钟到场。',
    '人工智能正在改变我们的日常工作方式。',
    '请把文件保存到桌面上，然后发送给我。',
    '他去年去了欧洲旅行，学习了很多语言。',
    '这家餐厅的特色菜是红烧肉和清蒸鱼。',
    '实时字幕功能可以帮助听障人士更好地获取信息。',
    '我们需要在下个月之前完成产品的测试工作。',
    '窗外下起了大雨，街上的人都在匆忙赶路。',
]
EN = [
    'The weather is very nice today, let us take a walk in the park.',
    'This report needs to be submitted before the end of this week.',
    'The meeting will start at three in the afternoon, please arrive early.',
    'Artificial intelligence is changing the way we work every day.',
    'Please save the file to the desktop and then send it to me.',
    'He traveled to Europe last year and learned many languages.',
    'The specialty dishes here are braised pork and steamed fish.',
    'The live caption feature can help people with hearing impairment.',
    'We need to finish testing the product before next month.',
    'It started raining heavily outside and everyone was rushing home.',
]

PUNCT_ZH = re.compile(r'[\s，。！？、；：""''（）《》,.!?;:\-\u2014…]+')
PUNCT_EN = re.compile(r"[^a-z0-9' ]+")


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


# ── 机器锁（排队等待，不抢；fail-closed）────────────────────────────
def pid_alive(pid):
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, 0, int(pid))
        if not h:
            return k.GetLastError() != 87
        code = ctypes.c_ulong(0)
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            k.CloseHandle(h)
            return True
        k.CloseHandle(h)
        return code.value == 259
    except Exception:
        return True


def lock_owner():
    try:
        raw = open(LOCK, encoding='utf-8').read().strip()
    except FileNotFoundError:
        return None
    except Exception:
        return {'raw': None, 'pid': None, 'unparsed': True}
    parts = raw.split()
    pid = None
    for p in parts:
        if p.isdigit():
            pid = int(p)
            break
    return {'raw': raw, 'pid': pid,
            'module': parts[0] if parts else '?'}


def acquire_lock(note):
    while True:
        own = lock_owner()
        if own is None:
            break
        pid = own.get('pid')
        if pid == os.getpid():
            return own.get('raw')
        if pid and not pid_alive(pid):
            log('锁持有者 pid=%s 已死 ⇒ 回收' % pid)
            try:
                os.remove(LOCK)
            except Exception:
                pass
            continue
        log('等机器锁（持有者 pid=%s 仍存活 ⇒ 不抢）' % pid)
        time.sleep(20)
    content = 'app %d %s %s' % (os.getpid(),
                                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                note)
    tmp = LOCK + '.tmp_app116'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp, LOCK)
    log('已取机器锁：%s' % content)
    return content


def release_lock(content):
    own = lock_owner()
    if own is None:
        return
    if own.get('raw') == content or own.get('pid') == os.getpid():
        try:
            os.remove(LOCK)
            log('已放机器锁')
        except Exception as e:
            log('放锁失败：%r' % (e,))


# ── 合成 ────────────────────────────────────────────────────────
def synthesize(voice, dump_dir, jsonl_path, mix_wav):
    """起一个 tts_worker，喂 20 条 synth 命令，收集逐句 wav。"""
    if os.path.isdir(dump_dir):
        shutil.rmtree(dump_dir, ignore_errors=True)
    os.makedirs(dump_dir, exist_ok=True)
    cmd = [PKG_PY, os.path.join(DEV, 'tts_worker.py'),
           '--device', 'GPU.0', '--precision', 'f32',
           '--voice', voice,
           '--dump-dir', dump_dir,
           '--jsonl', jsonl_path,
           '--out-wav', mix_wav]
    log('起 worker（音色 %s）：%s' % (voice, ' '.join(cmd[-8:])))
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                         errors='replace', env=env, cwd=DEV, bufsize=1)
    # 先等 ready
    t0 = time.time()
    ready = False
    while time.time() - t0 < 900:
        line = p.stdout.readline()
        if not line:
            break
        ll = line.strip()
        if ll.startswith('{'):
            try:
                msg = json.loads(ll)
            except Exception:
                continue
            if msg.get('kind') == 'ready':
                ready = True
                break
            if msg.get('kind') == 'error':
                log('worker error：%r' % msg)
                break
    if not ready:
        log('🔴 worker 未就绪 ⇒ 中止')
        try:
            p.kill()
        except Exception:
            pass
        return False
    log('worker ready（%.1f s）⇒ 喂 20 句' % (time.time() - t0))

    items = ([('zh', t) for t in ZH] + [('en', t) for t in EN])
    for i, (lang, text) in enumerate(items):
        msg = {'cmd': 'synth', 'id': i + 1, 'text': text,
               'lang': 'Chinese' if lang == 'zh' else 'English',
               'speed': 1.0}
        try:
            p.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n')
            p.stdin.flush()
        except Exception as e:
            log('写入失败：%r' % (e,))
            break
        time.sleep(0.15)
    # 等播完（等 played 事件到齐或超时）
    played = 0
    t1 = time.time()
    while time.time() - t1 < 1800 and played < len(items):
        line = p.stdout.readline()
        if not line:
            break
        ll = line.strip()
        if ll.startswith('{'):
            try:
                msg = json.loads(ll)
            except Exception:
                continue
            if msg.get('kind') == 'played':
                played += 1
                if played % 5 == 0:
                    log('  已播 %d/%d' % (played, len(items)))
            elif msg.get('kind') == 'error':
                log('  句级 error：%r' % msg)
    log('  播放结束：%d/%d（用时 %.0f s）' % (played, len(items), time.time() - t1))
    try:
        p.stdin.write(json.dumps({'cmd': 'quit'}) + '\n')
        p.stdin.flush()
        p.wait(timeout=60)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass
    return True


# ── ASR 回转写 + CER/WER ────────────────────────────────────────
def transcribe(wavs):
    """用仓库现成的 OV ASR 回转写（GPU.0）。

    🔴 **复用 `asr_check_male_candidates.py` 的同一套调用方式**
       （`encode_audio` → `greedy_decode_with_prefix` → `tokenizer.decode`
        → `streaming_asr.parse_asr_output`）⇒ 不新写 ASR 逻辑。
    """
    import numpy as np
    import soundfile as sf
    sys.path.insert(0, REPO)
    from backends import OVBackend, SAMPLE_RATE
    from streaming_asr import parse_asr_output
    log('加载 OV ASR（models/ov-int8-past, GPU.0）…')
    b = OVBackend(model_dir='models/ov-int8-past', device='GPU.0')
    out = {}
    for p in wavs:
        audio, sr = sf.read(p, dtype='float32')
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            n = int(len(audio) * SAMPLE_RATE / sr)
            audio = np.interp(np.linspace(0, len(audio), n),
                              np.arange(len(audio)), audio).astype(np.float32)
        try:
            ehs, n_real, N_audio = b.encode_audio(audio)
            out_ids = b.greedy_decode_with_prefix(ehs, prefix_ids=[],
                                                  max_new_tokens=256)
            text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
            lang, txt = parse_asr_output(text, user_language=None)
            if not txt:
                txt = text
        except Exception as e:
            log('  转写失败 %s：%r' % (os.path.basename(p), e))
            txt = '<ERROR %s>' % e
        out[p] = txt
        log('  %s ⇒ %r' % (os.path.basename(p), (txt or '')[:60]))
    return out


def norm_zh(s):
    return PUNCT_ZH.sub('', (s or '').strip())


def norm_en(s):
    return ' '.join(PUNCT_EN.sub(' ', (s or '').lower()).split())


def lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref, hyp, zh=True):
    if zh:
        r, h = norm_zh(ref), norm_zh(hyp)
        return lev(r, h) / max(1, len(r))
    r, h = norm_en(ref).split(), norm_en(hyp).split()
    return lev(r, h) / max(1, len(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-asr', action='store_true')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LISTEN, exist_ok=True)
    rep = {'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'zh': ZH, 'en': EN, 'voices': {}}

    content = acquire_lock('app116-preset-eval')
    try:
        for voice in ('A', 'B'):
            dump = os.path.join(OUT, 'dump_%s' % voice)
            jsonl = os.path.join(OUT, 'synth_%s.jsonl' % voice)
            mix = os.path.join(OUT, 'mix_%s.wav' % voice)
            ok = synthesize(voice, dump, jsonl, mix)
            wavs = []
            if os.path.isdir(dump):
                wavs = [os.path.join(dump, f) for f in sorted(os.listdir(dump))
                        if f.endswith('.wav')]
            log('音色 %s：落盘 %d 段 wav' % (voice, len(wavs)))
            rec = {'n_wav': len(wavs), 'dump_dir': dump, 'jsonl': jsonl}
            if wavs and not args.skip_asr:
                rec['asr'] = transcribe(wavs)
            rep['voices'][voice] = rec
    finally:
        release_lock(content)

    # ── CER/WER ────────────────────────────────────────────────
    summary = {}
    for voice, rec in rep['voices'].items():
        if 'asr' not in rec:
            continue
        per = []
        items = [('zh', t) for t in ZH] + [('en', t) for t in EN]
        wavs = [os.path.join(rec['dump_dir'], f)
                for f in sorted(os.listdir(rec['dump_dir']))
                if f.endswith('.wav')] if os.path.isdir(rec['dump_dir']) else []
        for i, (lang, ref) in enumerate(items):
            if i >= len(wavs):
                break
            hyp = rec['asr'].get(wavs[i]) or ''
            e = cer(ref, hyp, zh=(lang == 'zh'))
            per.append({'i': i, 'lang': lang, 'ref': ref, 'hyp': hyp,
                        'err_rate': round(e, 4)})
        zhv = [x['err_rate'] for x in per if x['lang'] == 'zh']
        env = [x['err_rate'] for x in per if x['lang'] == 'en']
        rec['per_sentence'] = per
        rec['cer_zh'] = round(sum(zhv) / len(zhv), 4) if zhv else None
        rec['wer_en'] = round(sum(env) / len(env), 4) if env else None
        summary[voice] = {'cer_zh': rec['cer_zh'], 'wer_en': rec['wer_en']}
    rep['summary'] = summary
    log('=== CER/WER 汇总 === %s' % json.dumps(summary, ensure_ascii=False))

    # ── 抽听样本：预设 B 的 2 zh + 2 en ─────────────────────────
    picked = []
    recB = rep['voices'].get('B', {})
    if recB.get('per_sentence'):
        zh_p = [x for x in recB['per_sentence'] if x['lang'] == 'zh']
        en_p = [x for x in recB['per_sentence'] if x['lang'] == 'en']
        for x in (zh_p[:2] + en_p[:2]):
            picked.append(x)
    for x in picked:
        i = x['i']
        src_dir = recB.get('dump_dir')
        if not src_dir or not os.path.isdir(src_dir):
            break
        cand = [f for f in sorted(os.listdir(src_dir)) if f.endswith('.wav')]
        if i >= len(cand):
            continue
        src = os.path.join(src_dir, cand[i])
        dst = os.path.join(LISTEN, 'presetB_%s_%02d.wav' % (x['lang'], i))
        shutil.copyfile(src, dst)
        x['listen_file'] = dst
    rep['listen_dir'] = LISTEN
    rep['picked'] = picked

    out = os.path.join(OUT, 'preset_eval.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('证据：%s' % out)
    log('抽听目录：%s（%d 个）' % (LISTEN, len(os.listdir(LISTEN))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
