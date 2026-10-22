r"""diag_guard_energy.py — 离线分析「保护期 probe 能量」的真实分布

背景（C-104）
-------------
`Segmenter._silence_tail()` 里的保护期判据是：

    probe_db = RMS(acc[sil_start-0.35s : sil_start])
    return probe_db > SILENCE_DB(-40.0)      # 绝对阈值

30 分钟样本上实测：**146 段里 141 段（97%）走的是规则1（12s 下限）**，
只有 5 段走「静音超时」规则 —— 说明规则2 形同虚设。
根因假设：句末语音渐弱（fade-out）时，静音起点往前 0.35s 的能量
正好在 -40dB 附近或以下，保护期判定 False → 不切段。

但**这个假设需要先验证**，因为
  (a) `find_trailing_silence` 自己就用 -40dB 找静音起点，
      所以「静音起点」本身已经定义在 -40dB 阈值上；
  (b) 保护期窗口 0.35s 跨越的是「渐弱尾巴」，它的能量分布未知。

本脚本（离线，不加载模型）回答四个问题：

  Q1  静音起点往前 0.35s 的 probe 能量，分布长什么样？
      → 若分布集中在 -42~-38dB，说明保护期在「擦边」上误杀。
  Q2  这些 probe 相对于**本段自身**的噪声底（noise floor）高多少 dB？
      → 决定能不能用「相对噪声底」当判据（方案 1 的关键）。
  Q3  相对噪声底的判据，会不会把「刚开口的爆破音」误判成语音？
      → 需要在「段起始」位置也采样做对照。
  Q4  各候选判据在真实音频上分别会放行/拦截多少个切点？

用法：
  python diag_guard_energy.py <wav> [--minutes 30] [--sil-db -40]
"""

from __future__ import annotations

import os
import sys

import numpy as np
import soundfile as sf

SR = 16000
FRAME_MS = 30
HOP_MS = 10


def frame_db(x: np.ndarray, frame_ms: int = FRAME_MS,
             hop_ms: int = HOP_MS) -> tuple[np.ndarray, int]:
    """逐帧 RMS→dB。返回 (db 数组, hop 样本数)。"""
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.size < n:
        return np.zeros(0, dtype=np.float64), h
    nf = (x.size - n) // h + 1
    out = np.empty(nf, dtype=np.float64)
    for i in range(nf):
        seg = x[i * h:i * h + n].astype(np.float64)
        out[i] = 20.0 * np.log10(np.sqrt(np.mean(seg * seg) + 1e-12) + 1e-7)
    return out, h


def noise_floor_db(db: np.ndarray) -> float:
    """噪声底估计：10 分位（对语音稀疏段足够稳）。"""
    if db.size == 0:
        return -120.0
    return float(np.percentile(db, 10))


def speech_level_db(db: np.ndarray) -> float:
    """语音电平估计：90 分位。"""
    if db.size == 0:
        return -120.0
    return float(np.percentile(db, 90))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    wav = args[0]
    minutes = 30.0
    sil_db = -40.0
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--sil-db' in args:
        sil_db = float(args[args.index('--sil-db') + 1])

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    db, hop = frame_db(d)
    print(f'文件 {os.path.basename(wav)}  {total_s/60:.1f} 分钟  '
          f'帧数 {db.size}  hop {hop} 样本')
    print(f'全局：噪声底(10分位) {noise_floor_db(db):.1f}dB  '
          f'中位 {np.median(db):.1f}dB  语音电平(90分位) {speech_level_db(db):.1f}dB\n')

    # ── 找出所有「连续静音段」（db < sil_db，长度 ≥1.2s）──
    is_sil = db < sil_db
    min_sil_frames = int(1200 / HOP_MS)
    runs = []
    i = 0
    while i < is_sil.shape[0]:
        if is_sil[i]:
            j = i
            while j + 1 < is_sil.shape[0] and is_sil[j + 1]:
                j += 1
            if (j - i + 1) >= min_sil_frames:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1
    print(f'连续静音段（db < {sil_db}dB 且 ≥1.2s）共 {len(runs)} 处\n')

    guard_frames = int(350 / HOP_MS)          # 0.35s 保护期
    ctx_frames = int(10000 / HOP_MS)          # 10s 上下文

    rows = []
    for (s, e) in runs:
        if s < guard_frames:
            continue                            # 前面没数据，跳过
        probe = db[s - guard_frames:s]
        if probe.size == 0:
            continue
        probe_db = float(np.median(probe))
        probe_rms_db = float(20 * np.log10(
            np.sqrt(np.mean(10 ** (probe / 20.0) ** 2)) + 1e-12))
        # 本段上下文（静音段之前的 10s）—— 代表「最近这一段」的电平特征
        cs = max(0, s - ctx_frames)
        ctx = db[cs:s]
        if ctx.size == 0:
            continue
        nf = noise_floor_db(ctx)
        sp = speech_level_db(ctx)
        rows.append(dict(
            at=s * hop / SR,
            probe_db=probe_db,
            probe_rms_db=probe_rms_db,
            nf=nf, sp=sp,
            margin=probe_db - nf,          # probe 高出噪声底多少
            sp_margin=probe_db - sp,       # probe 低于语音电平多少
            sil_len=(e - s + 1) * HOP_MS / 1000.0,
        ))

    if not rows:
        print('没有可分析的静音段')
        return

    probe = np.array([r['probe_db'] for r in rows])
    margin = np.array([r['margin'] for r in rows])
    sp_margin = np.array([r['sp_margin'] for r in rows])
    nf = np.array([r['nf'] for r in rows])

    def q(name, a):
        print(f'  {name:14s} 中位 {np.median(a):7.2f}   '
              f'p10 {np.percentile(a,10):7.2f}   '
              f'p90 {np.percentile(a,90):7.2f}   '
              f'min {a.min():7.2f}   max {a.max():7.2f}')

    print('=' * 74)
    print('Q1/Q2  probe（静音起点前 0.35s 的中位帧能量）与两个基准的关系')
    print('-' * 74)
    q('probe 能量 dB', probe)
    q('本段噪声底 dB', nf)
    q('probe - 噪声底', margin)
    q('本段语音电平', np.array([r['sp'] for r in rows]))
    q('probe - 语音电平', sp_margin)

    print('\n' + '=' * 74)
    print('Q4  各候选判据会「放行」多少个切点（放行 = 允许切段）')
    print('-' * 74)
    cands = [
        ('现状: probe > -40dB (绝对)', probe > sil_db),
        ('相对: probe > 噪声底+6dB', margin > 6.0),
        ('相对: probe > 噪声底+9dB', margin > 9.0),
        ('相对: probe > 噪声底+12dB', margin > 12.0),
        ('相对: probe > 语音电平-12dB', sp_margin > -12.0),
        ('相对: probe > 语音电平-18dB', sp_margin > -18.0),
    ]
    for name, ok in cands:
        n = int(ok.sum())
        print(f'  {name:28s} 放行 {n:4d} / {len(rows)}  '
              f'({n/len(rows)*100:3.0f}%)  拦截 {len(rows)-n:4d}')

    print('\n' + '=' * 74)
    print('最被现状拦截的 10 个切点（probe 能量排序）')
    print('-' * 74)
    order = np.argsort(probe)[:10]
    print(f'{"时刻s":>8} {"probe":>8} {"噪声底":>8} {"高出":>7} {"语音电平":>9} {"静音长":>7}')
    for i in order:
        r = rows[i]
        print(f'{r["at"]:8.1f} {r["probe_db"]:8.1f} {r["nf"]:8.1f} '
              f'{r["margin"]:7.1f} {r["sp"]:9.1f} {r["sil_len"]:7.1f}')

    print('\n' + '=' * 74)
    print('结论判据')
    print('-' * 74)
    blocked_now = int((probe <= sil_db).sum())
    print(f'  现状（probe > {sil_db}dB）会拦截 {blocked_now} / {len(rows)} 个切点')
    for m in (6.0, 9.0, 12.0):
        n = int((margin > m).sum())
        print(f'  相对「噪声底+{m:.0f}dB」会拦截 {len(rows)-n:4d} / {len(rows)} 个切点')
    print('  → 若「相对噪声底」拦截数远小于现状，说明它能救回「现状误杀」的切点；')
    print('    但必须再验「刚开口的爆破音」不会被它误判成语音（需要端到端对照）。')


if __name__ == '__main__':
    main()
