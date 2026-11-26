"""APP-146 第 4 项：**只跑一次三轮**（持锁，一次持锁到底）。

三轮：**保留背景音关 / 开 / 开+clone**，10 分钟片段，排空到 `n_pending=0`（最多 300 s）。

🔴 口径（APP-142 / APP-146）：
* **一次持锁到底**（三个臂共用一把 `shared\\MACHINE_LOCK`，原子创建 ⇒ 抢不到就等，绝不抢）；
* **用候选目录自带的 python**（APP-120 血泪：判「包能否用」用客户解释器）；
* **用 Start_Bridge.bat 实际走的配置**（⇒ 桥接跑在候选目录的 `ext/`，cwd = 包根）；
* 模型身份按 **APP-145**：只核 config + 目录名 + 文件大小（**不做任何 SHA**）；
* 日志里要能看到 `MT 就绪（Hy-MT3 …）` 和每个 NPU 模型的 `NPU_TURBO=True`。

🔴 背景音关臂：`--bg-off`；clone 臂：`--voice clone`。
"""
import json
import os
import subprocess
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
ROOT = r'C:\Users\Trekker-PTL\shared\bgkeep\e2e_app146\three_arms'
MEDIA = os.path.join(REPO, 'test_audio', 'clip_10min_0_600.wav')
DRIVER = os.path.join(REPO, 'live_caption', '_app137_e2e_driver.py')
OUT = os.path.join(REPO, 'results', 'app', 'app146_three_arms.json')

# 三臂：名称 → (额外 env, 是否 --bg-off, voice)
# 🔴🔴🔳 **TTS 必须显式钉到 NPU**（= MiniMVP 的出厂默认，见 package_profile.json）：
#   * EXT 的 `DEVICE_TTS` 默认是 **AUTO** ⇒ 探测到本机有 CUDA 边车就**走 CUDA**
#     （开发机有 RTX 5050）⇒ **NPU 从未被编译** ⇒ turbo 无处注入、
#     也测不到「出厂默认」这条路（实测：三轮里 TTS 全部走 CUDA 边车）。
#   * 客户机没有 CUDA ⇒ 会回落 NPU ⇒ **NPU 才是 MiniMVP 的真实出厂路径**。
# ⇒ 三轮统一加 `EXT_TTS_DEVICE=NPU`；MT 也按出厂默认钉到 GPU.0。
ENV_NPU = 'EXT_TTS_DEVICE=NPU|EXT_MT_DEVICE=GPU.0'

ARMS = [
    ('bgkeep_off', ENV_NPU, True, 'A'),
    ('bgkeep_on', ENV_NPU, False, 'A'),
    ('bgkeep_on_clone', ENV_NPU, False, 'clone'),
]

results = []
for name, env_extra, bg_off, voice in ARMS:
    print('\n' + '=' * 70, flush=True)
    print('== arm %s  bg_off=%s voice=%s' % (name, bg_off, voice), flush=True)
    print('=' * 70, flush=True)
    cmd = [sys.executable, DRIVER,
           '--app', CAND,
           '--root', os.path.join(ROOT, name),
           '--arms', '%s:%s' % (name, env_extra),
           '--media', MEDIA,
           '--drain-cap', '300',
           '--tail-wait', '30',
           '--voice', voice]
    if bg_off:
        cmd.append('--bg-off')
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    dt = round(time.time() - t0, 1)
    out = p.stdout or ''
    err = p.stderr or ''
    # 提取关键字段
    jf = os.path.join(ROOT, name, name + '_1', 'bgkeep_e2e.json')
    rec = {'arm': name, 'bg_off': bg_off, 'voice': voice,
           'rc': p.returncode, 'elapsed_s': dt}
    if os.path.isfile(jf):
        with open(jf, encoding='utf-8') as fh:
            j = json.load(fh)
        d = j.get('drain') or {}
        pl = (j.get('stats_full') or {}).get('pipeline') or {}
        rec.update({
            'json': jf,
            'dubs': j.get('dubs'),
            'n_pending_at_media_end': d.get('n_pending_at_media_end'),
            'n_pending_after_drain': d.get('n_pending_after_drain'),
            'drained_to_zero': d.get('drained_to_zero'),
            'drain_elapsed_sec': d.get('drain_elapsed_sec'),
            'timing_valid': d.get('timing_valid'),
            'stats_timeout_count': d.get('stats_timeout_count'),
            'n_emitted': pl.get('n_emitted'),
            'n_error': pl.get('n_error'),
            'dub_late_max': (j.get('dub_late_final_summary') or {}).get('max'),
            'dub_late_p90': (j.get('dub_late_final_summary') or {}).get('p90'),
            'synth_rtf': j.get('synth_rtf'),
            'peak_ws_mb': j.get('peak_ws_mb'),
            'clone_reasons': (j.get('stats_full') or {}).get('clone_reasons'),
            'devices': j.get('devices'),
            'bg_state': (j.get('stats_full') or {}).get('bg_state'),
        })
    else:
        rec['json'] = None
        rec['error'] = 'no bgkeep_e2e.json'
    # 锁事件
    ev = os.path.join(ROOT, name, '_lock_events.jsonl')
    if os.path.isfile(ev):
        rec['lock_events'] = [json.loads(l) for l in
                              open(ev, encoding='utf-8') if l.strip()]
    # 关键日志行
    blog = os.path.join(ROOT, name, name + '_1', 'bridge.log')
    if os.path.isfile(blog):
        lines = open(blog, encoding='utf-8', errors='replace').read().splitlines()
        rec['log_mt_ready'] = [l for l in lines if 'MT 就绪' in l]
        rec['log_turbo'] = [l for l in lines if 'NPU_TURBO' in l or 'npu_turbo' in l]
        rec['log_engine_fail'] = [l for l in lines if '加载失败' in l][:2]
        rec['log_tts_ready'] = [l for l in lines if 'TTS 就绪' in l]
    rec['stdout_tail'] = out.strip().splitlines()[-3:] if out.strip() else []
    rec['stderr_tail'] = err.strip().splitlines()[-3:] if err.strip() else []
    results.append(rec)
    print('== arm %s done: rc=%s elapsed=%ss' % (name, p.returncode, dt), flush=True)
    print('   dubs=%s n_pending_end=%s drained=%s rtf=%s' % (
        rec.get('dubs'), rec.get('n_pending_at_media_end'),
        rec.get('drained_to_zero'), rec.get('synth_rtf')), flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'candidate': CAND, 'media': MEDIA,
               'media_duration_sec': 600, 'drain_cap_sec': 300,
               'arms': results}, f, ensure_ascii=False, indent=2)
print('\n落盘 ->', OUT)
