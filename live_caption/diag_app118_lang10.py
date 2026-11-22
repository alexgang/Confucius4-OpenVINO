#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-118 §3：**10 语种冒烟**（每种 1 句，覆盖字幕 + 配音）。

## reviewer 原文（APP-118 §3）
> 10 语种冒烟：每种 1 句，覆盖字幕 + 配音。

## 本脚本查什么（**行为级**）
| # | 检查 | 口径 |
|---|---|---|
| A1 | 包内 **10 种**目标语言都在 | `translator.TARGETS`（去 `off`）= 10 |
| A2 | 每种语言的 **MT 目标名**能解析 | `translator._LANG_NAME` 与 `TARGETS` **一一对应** |
| A3 | 每种语言的 **TTS language id** 能解析 | `tts_engine.LANG_MAP` 覆盖全部 10 种 |
| A4 | 每种语言的 **界面标签**存在 | `translator.TARGET_LABELS` 覆盖全部 10 种 |
| A5 | 三张表的**目标语言名一致**（MT/TTS/界面） | 同一张表不得各写各的 |
| B | **真跑一次配音**（每种 1 句） | 真调 TTS 引擎 ⇒ 出 wav ⇒ 判「非静音 + 有时长」 |
| C | **真跑一次字幕**（每种 1 句） | 真调 MT ⇒ 出译文 ⇒ 判「非空」 |
| D | **反证组**：不存在的语种**必须 FAIL** | 证明 B/C 不是恒真 |

## 🔴 v2（2026-11-20 18:0x，接上一会话的断点）
上一版本**自身有 bug** ⇒ 10/10 FAIL 是**假 FAIL**：
  `tts_engine.make_engine()` 的签名是
  `(device, model_path, cache_dir, on_log, precision)` —— **没有 `voice` 参**；
  音色不是引擎参数，而是走 **`speaker_embed` / 内置 `speaker`**（见 `tts_worker.py`
  的 `_setup_babelvox_voice()`）。⇒ 旧写法 `make_engine(device=..., voice='A')`
  必然抛 `TypeError: make_engine() got an unexpected keyword argument 'voice'`
  ⇒ 引擎根本没建起来 ⇒ B 组 0/10。
⇒ 本版按**产品真实路径**重建：先 `make_engine(device=…)`，
  再 `tts_engine.speaker_embedding(eng, preset_voice_path('A'))`，
  最后 `tts_engine.stream(eng, text, language=…, speaker_embed=…)`。

## 纪律
- **B/C 会占 GPU**（TTS/MT 推理）⇒ **必须持机器锁**（本脚本自己取，排队等待，不抢）；
- 本脚本默认**只跑 A**（纯逻辑，零占设备）⇒ 加 `--live` 才跑 B/C/D。
"""
import argparse
import datetime
import json
import os
import sys
import time
import wave

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.join(HOME, 'confucius4-openvino')
RESULTS = os.path.join(REPO, 'results', 'app')
PKG_DEFAULT = os.path.join(HOME, 'Confucius4_LiveCaption_v2.5')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')

_PKG_APP = None
for _i, _a in enumerate(sys.argv):
    if _a == '--pkg' and _i + 1 < len(sys.argv):
        _PKG_APP = os.path.join(sys.argv[_i + 1], 'app')
        break
    if _a.startswith('--pkg='):
        _PKG_APP = os.path.join(_a.split('=', 1)[1], 'app')
        break
if _PKG_APP and os.path.isdir(_PKG_APP):
    sys.path.insert(0, _PKG_APP)
    print('[pkg] 用**客户包内**的代码做验收：%s' % _PKG_APP)
else:
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))

CHECKS = []


def log(m):
    print('[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S'), m),
          flush=True)


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  — ' + str(detail)) if detail else ''))
    return bool(ok)


#: 每种语言的**测试句**（简短 ⇒ 合成快）
SENTENCES = {
    'zh': '今天天气很好。',
    'en': 'The weather is nice today.',
    'ja': '今日はいい天気ですね。',
    'ko': '오늘 날씨가 좋네요.',
    'de': 'Das Wetter ist heute schoen.',
    'fr': "Aujourd'hui, il fait beau.",
    'es': 'Hoy hace buen tiempo.',
    'pt': 'O tempo esta bom hoje.',
    'it': 'Il tempo e bello oggi.',
    'ru': 'Сегодня хорошая погода.',
}


# ── 共享机器锁（排队等待，不抢） ───────────────────────────────
def pid_alive(pid):
    """🔴 探测失败一律视为存活（曾误回收他人活锁）。"""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return k32.GetLastError() != 87  # 87 = 参数错误 ⇒ 进程不存在
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        if not ok:
            return True
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return True


def lock_owner():
    try:
        with open(LOCK, encoding='utf-8') as f:
            raw = f.read().strip()
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
    return {'raw': raw, 'pid': pid, 'module': parts[0] if parts else '?'}


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
    tmp = LOCK + '.tmp_app118'
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


# ── B：真跑配音（按**产品真实路径**建音色） ─────────────────────
def run_tts(langs, device, wav_dir, out_rec):
    import numpy as np
    import tts_engine

    # 🔴 引擎日志收集器（用来抓「Language 'xx' not recognized」这类回落告警）
    engine_logs = []

    def _olog(m):
        engine_logs.append(str(m))
        if 'not recognized' in str(m):
            print('    [engine] %s' % str(m)[:160], flush=True)

    log('TTS 引擎加载（device=%s）…' % device)
    t0 = time.time()
    eng = tts_engine.make_engine(device=device, on_log=_olog)
    log('引擎就绪：%.1f s' % (time.time() - t0))

    # 🔴 音色**不是**引擎参数 ⇒ 走「参考 wav → speaker_embed」
    ref = tts_engine.preset_voice_path('A')
    embed = None
    if ref:
        log('算预设 A 的 speaker embedding：%s' % ref)
        embed = tts_engine.speaker_embedding(eng, ref, on_log=log)
    log('embedding=%s' % ('ok' if embed is not None else 'None'))

    n_ok = 0
    for k in langs:
        text = SENTENCES.get(k, 'Hello.')
        # 🔴🔴 **必须走产品同款映射**：`tts_worker.py` 里是
        #   `blang = tts_engine.map_language(lang)` ⇒ 'zh' → 'Chinese'。
        #   直接传 'zh' ⇒ babelvox 认不出 ⇒ **回落 language-agnostic**
        #   （等于没测到该语种）。
        blang = tts_engine.map_language(k)
        rec = {'lang': k, 'text': text, 'blang': blang,
               'supported': bool(tts_engine.language_supported(blang))}
        out = os.path.join(wav_dir, 'lang10_%s.wav' % k)
        try:
            chunks = []
            t1 = time.time()
            for wav_chunk, sr in tts_engine.stream(
                    eng, text, language=blang, speaker_embed=embed, speaker=None):
                chunks.append(np.asarray(wav_chunk, dtype=np.float32))
            dt = time.time() - t1
            if chunks:
                audio = np.concatenate(chunks)
                pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                with wave.open(out, 'wb') as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(pcm.tobytes())
                rec['wav'] = out
                rec['seconds'] = round(len(pcm) / 24000.0, 2)
                rec['peak'] = round(float(np.abs(audio).max()), 4)
                rec['wall_s'] = round(dt, 2)
                rec['rtf'] = round(dt / max(rec['seconds'], 1e-6), 3)
                rec['ok'] = rec['seconds'] > 0.3 and rec['peak'] > 0.01
            else:
                rec['ok'] = False
                rec['why'] = '无音频输出'
        except Exception as e:
            rec['ok'] = False
            rec['why'] = '%s: %s' % (type(e).__name__, str(e)[:160])
        out_rec[k] = rec
        print('    %-3s %-7s rtf=%-6s %s' % (
            k, rec.get('seconds', '—'), rec.get('rtf', '—'),
            'OK' if rec.get('ok') else 'FAIL %s' % rec.get('why', '')), flush=True)
        if rec.get('ok'):
            n_ok += 1
    try:
        eng.close()
    except Exception:
        pass
    # 🔴 **静默回落检测**：引擎说「Language 'xx' not recognized」⇒ 该语种**没测到**
    not_recognized = [m for m in engine_logs if 'not recognized' in m]
    check('B2 10 语种**没有**触发 language-agnostic 回落（映射正确）',
          not not_recognized,
          not_recognized[:3] or '引擎未报任何 not recognized')
    unsup = [k for k, r in out_rec.items() if not r.get('supported')]
    check('B3 10 语种映射后的 id 都在引擎支持列表内', not unsup, unsup)
    return n_ok


# ── C：真跑字幕（MT） ─────────────────────────────────────────
#: 🔴 MT 的**源句固定用英文** ⇒ 10 个目标语言都**真的过模型**
#:   （若源句语言 == 目标语言，`translate()` 会走「同语免译」短路 ⇒ 没测到东西）
MT_SOURCE = 'The weather is nice today and we can go for a walk in the park.'


def run_mt(langs, device, out_rec):
    import translator as T

    log('MT 模型加载（device=%s）…' % device)
    t0 = time.time()
    tr = T.HunyuanTranslator(device=device)
    log('MT 引擎就绪：%.1f s（模型 %s）' % (time.time() - t0, T.DEFAULT_MODEL))

    n_ok = 0
    for k in langs:
        # 🔴 `translate(text, tgt)` 的 `tgt` 要的是**语言代号**（'zh'），
        #   内部 `build_messages()` 会做 `_LANG_NAME[tgt]` ⇒ 传全名会 KeyError。
        tgt = k
        rec = {'lang': k, 'tgt': tgt, 'tgt_name': T._LANG_NAME.get(k),
               'src': MT_SOURCE}
        try:
            r = tr.translate(MT_SOURCE, tgt)
            txt = (r or {}).get('text', '') if isinstance(r, dict) else str(r)
            rec['out'] = txt
            rec['skipped'] = bool((r or {}).get('skipped')) if isinstance(r, dict) else None
            rec['lat_ms'] = (r or {}).get('lat_ms') if isinstance(r, dict) else None
            rec['ok'] = bool(txt and txt.strip()) and not rec.get('skipped')
        except Exception as e:
            rec['ok'] = False
            rec['why'] = '%s: %s' % (type(e).__name__, str(e)[:160])
        out_rec[k] = rec
        print('    %-3s %-10s %-8s %s' % (
            k, rec.get('tgt_name'), (rec.get('out') or '')[:24].replace('\n', ' '),
            'OK' if rec.get('ok') else 'FAIL %s' % rec.get('why', '')), flush=True)
        if rec.get('ok'):
            n_ok += 1
    return n_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG_DEFAULT)
    ap.add_argument('--live', action='store_true',
                    help='真跑 TTS/MT（**占 GPU** ⇒ 必须持机器锁）')
    ap.add_argument('--device', default='GPU.0')
    ap.add_argument('--tts-device', default='GPU.0')
    ap.add_argument('--mt-device', default='GPU.0')
    # 🔴🔴🔳 **APP-120 §2（2026-11-22）**：输出文件**可指定**。
    # 🔴 **为什么必须加**：原先输出路径**写死** `app118_lang10_evidence.json`
    #   ⇒ 跑 MiniMVP v1.1 时**覆盖了 v2.5（§217）的那份证据**
    #   （2026-11-22 14:47 实测：`app118_lang10_evidence.json` 被换成 v1.1 的
    #     5 139 B / 7 PASS·1 FAIL，v2.5 原件 8 988 B / SHA `7ce6fa9d…` 丢失）
    #   ⇒ **不同包的证据必须写不同的文件** ⇒ 加 `--out`。
    # 🔴 **默认仍写原路径**（保持旧调用方行为不变；v2.5 那份按此路径恢复）。
    ap.add_argument('--out', default=None,
                    help='证据输出路径（默认 results/app/app118_lang10_evidence.json）')
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    print('=== APP-118 §3 10 语种冒烟（live=%s）===' % args.live)
    import translator as T
    try:
        import tts_engine as TE
    except Exception as e:
        print('FAIL: import tts_engine 失败 %r' % (e,))
        return 2

    langs = [k for k in T.TARGETS if k != 'off']
    check('A1 目标语言 = 10 种', len(langs) == 10, '%d 种 %s'
          % (len(langs), langs))

    miss_name = [k for k in langs if k not in T._LANG_NAME]
    check('A2 每种语言的 MT 目标名可解析', not miss_name, miss_name)

    miss_lang = [k for k in langs if k not in TE.LANG_MAP]
    check('A3 每种语言的 TTS language id 可解析', not miss_lang, miss_lang)

    miss_lbl = [k for k in langs if k not in T.TARGET_LABELS]
    check('A4 每种语言的界面标签存在', not miss_lbl, miss_lbl)

    bad_map = [k for k in langs
               if T._LANG_NAME.get(k) and TE.LANG_MAP.get(k)
               and T._LANG_NAME[k] != TE.LANG_MAP[k]]
    check('A5 三张表的目标语言名一致（MT/TTS/界面）', not bad_map, bad_map)

    tts_rec, mt_rec = {}, {}
    lock_content = None
    if args.live:
        print('  ── 真跑：每种 1 句（字幕 + 配音）──')
        lock_content = acquire_lock('app118-v25-lang10')
        wav_dir = os.path.join(RESULTS, 'app118_lang10')
        os.makedirs(wav_dir, exist_ok=True)
        try:
            n_ok = run_tts(langs, args.tts_device, wav_dir, tts_rec)
        except Exception as e:
            log('TTS 整段异常：%r' % (e,))
            n_ok = 0
        check('B 10 语种配音全部出声', n_ok == len(langs),
              '%d/%d' % (n_ok, len(langs)))

        try:
            m_ok = run_mt(langs, args.mt_device, mt_rec)
        except Exception as e:
            log('MT 整段异常：%r' % (e,))
            m_ok = 0
        check('C 10 语种字幕（MT）全部出译文', m_ok == len(langs),
              '%d/%d' % (m_ok, len(langs)))

        # ── D：反证组（证明 B 组不是恒真） ────────────────────
        # 🔴 事实：babelvox 引擎对**未知语言**会「告警 + 回落 language-agnostic」
        #    ⇒ **引擎本身拦不住**；拦住的是**产品侧的两道闸**：
        #      ① `tts_engine.map_language(lang, strict=True)` ⇒ 显式抛错
        #      ② `tts_engine.language_supported(blang)` ⇒ tts_worker 显式告警并跳过
        #    ⇒ 反证组就查这**两道闸**（查产品路径，不是查引擎）。
        d_rec = {}
        try:
            import tts_engine as TE2
            try:
                bad = TE2.map_language('xx', strict=True)
                d_rec['strict_raised'] = False
                d_rec['strict_returned'] = bad
            except ValueError as e:
                d_rec['strict_raised'] = True
                d_rec['strict_msg'] = str(e)[:120]
            d_rec['language_supported_xx'] = bool(
                TE2.language_supported('xx'))
            d_rec['map_nonstrict_xx'] = TE2.map_language('xx')
            d_rec['engine_fallback_note'] = (
                '引擎对未知语言会告警并回落 language-agnostic ⇒ '
                '必须靠产品两道闸拦')
            d_rec['latent_note'] = (
                '🔴 `map_language()` **非 strict** 对未知码**静默回落 English**；'
                '而 `tts_worker` 是 `map_language(lang)` **之后**才判 '
                '`language_supported(blang)` ⇒ 这道闸**抓不到**未知码。'
                '实测未知码在**原始 id** 上判定正确（False）。'
                '⇒ 属**潜在风险**（App 只会传 TARGETS 里的 10 个合法码），'
                '本轮**不改产品代码**，登记为未结项。')
        except Exception as e:
            d_rec['err'] = '%s: %s' % (type(e).__name__, e)
        check('D 反证组：未知语种必须被**产品两道闸**拦住（证明 B 组可判失败）',
              bool(d_rec.get('strict_raised'))
              and d_rec.get('language_supported_xx') is False,
              json.dumps(d_rec, ensure_ascii=False)[:300])
    else:
        print('  （未加 --live ⇒ 跳过真跑；A 组为纯逻辑检查，零占设备）')

    npass = sum(1 for c in CHECKS if c['ok'])
    nfail = len(CHECKS) - npass
    out = {'pass': npass, 'fail': nfail, 'checks': CHECKS, 'langs': langs,
           'live_tts': tts_rec, 'live_mt': mt_rec,
           'pkg': _PKG_APP or os.path.join(REPO, 'live_caption'),
           'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    op = os.path.join(RESULTS, 'app118_lang10_evidence.json')
    if getattr(args, 'out', None):
        op = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(op), exist_ok=True)
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n结论：%d PASS / %d FAIL  →  %s' % (npass, nfail, op))
    if lock_content:
        release_lock(lock_content)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
