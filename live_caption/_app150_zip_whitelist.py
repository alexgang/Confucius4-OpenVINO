"""APP-150 §1：**打 zip 前的白名单检查**（静态检查，不打 zip）。

reviewer 原文：
> 打 zip 前做白名单检查，下面任何一项不满足都不打：
> * clone 目录为空；
> * 没有 bridge_token*.txt、*.log、bridge.err、ov_cache/npu_cache/__pycache__；
> * 包内文本文件里搜 `Trekker-PTL` 为 0 处（README 示例路径也不要写开发机路径）；
> * device_config.json 是出厂默认：ASR=GPU.0、MT=GPU.0、TTS=NPU、NPU_TURBO 开、
>   保留背景音开、克隆关；
> * 除 preset_A.wav 以外没有音频/视频文件，没有 CUDA DLL。

## 🔴 本脚本对「device_config.json」一项的口径说明（**重要，不要误读**）

实测发现：**`device_config.json` 根本不在包内** ——
它是**用户级配置**，路径是 `%LOCALAPPDATA%\Confucius4LiveCaption\device_config.json`
（见 `live_caption/device_config.py:53` 的 `CONFIG_PATH`），
**首次运行时由程序生成**，用户改了也不该进包（否则会把开发机的设置带给客户）。

⇒ 本脚本把这一项拆成**三条可验证的判据**：
① **包内不得有 `device_config.json`**（用户级配置不入包）；
② **代码里的出厂默认**必须符合 reviewer 的口径
   （`device_config.py::_DEFAULT_DEVICES_MINIMVP` ＝ ASR=GPU.0 / MT=GPU.0 / TTS=NPU），
   并核对候选包内的 `package_profile.json`（`npu_turbo=true`、`allow_bgkeep=true`、
   `allow_cuda=false`、`tts_c13=false`）；
③ **「保留背景音开」「克隆关」** 是**插件侧默认**
   ⇒ 直接读候选包内 `ext/extension/popup.js` 的默认值（bgkeep 默认 true、
   克隆默认 preset A）。

🔴 纪律：只读检查，**不打 zip**；结果如实落盘（包外）。
"""
import io
import json
import os
import re
import time

REPO = os.getcwd()
CAND = os.environ.get('APPCAND')
if not CAND:
    CAND = os.path.join(os.path.dirname(REPO),
                        'Confucius4_LiveCaption_MiniMVP_v1.2.candidate')
OUT = os.path.join(REPO, 'results', 'app', 'app150_zip_whitelist.json')

MEDIA_EXT = ('.wav', '.ogg', '.mp3', '.mp4', '.flac')
RUNTIME_PAT = re.compile(
    r'(bridge_token.*\.txt$|\.log$|^bridge\.err$|'
    r'(^|/)(ov_cache|npu_cache|__pycache__)(/|$))', re.I)
TEXT_EXT = ('.py', '.txt', '.md', '.json', '.bat', '.cmd', '.ps1', '.js',
            '.html', '.xml', '.ini', '.cfg', '.yaml', '.yml', '.csv')
DEV_MARK = 'Trekker-PLT'

res = {'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
       'candidate': CAND, 'checks': []}


def chk(name, ok, detail=''):
    res['checks'].append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:400]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           (' — ' + str(detail)[:200]) if detail else ''))
    return ok


print('候选目录：%s' % CAND)

# ── ① clone 目录为空 ─────────────────────────────────────────────────
clone_files = []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), CAND).replace('\\', '/')
        if re.search(r'clone', rel, re.I) and rel.lower().endswith(
                ('.wav', '.ogg', '.npz', '.mp3')):
            clone_files.append(rel)
chk('clone 目录为空（无克隆音色文件）', not clone_files, clone_files[:5])

# ── ② 无运行产物 ─────────────────────────────────────────────────────
runtime_hits = []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), CAND).replace('\\', '/')
        if RUNTIME_PAT.search(rel):
            runtime_hits.append(rel)
chk('无运行产物（bridge_token/log/bridge.err/ov_cache/npu_cache/__pycache__）',
    not runtime_hits, runtime_hits[:8])

# ── ③ 包内文本文件不含开发机路径 ─────────────────────────────────────
dev_hits = []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        if not fn.lower().endswith(TEXT_EXT):
            continue
        p = os.path.join(dp, fn)
        rel = os.path.relpath(p, CAND).replace('\\', '/')
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except OSError:
            continue
        if DEV_MARK.encode('utf-8') in data:
            dev_hits.append((rel, data.count(DEV_MARK.encode('utf-8'))))
chk('包内文本文件搜 `%s` 为 0 处' % DEV_MARK, not dev_hits, dev_hits[:8])

# ── ④ 出厂默认（拆成三条，见文件头说明）───────────────────────────────
# ④a 包内不得有 device_config.json（用户级配置，不入包）
dc_in_pkg = []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        if fn == 'device_config.json':
            dc_in_pkg.append(os.path.relpath(os.path.join(dp, fn), CAND))
chk('包内没有 device_config.json（它是用户级配置，不入包）',
    not dc_in_pkg, dc_in_pkg)

# ④b 代码里的出厂默认
dev_dc = os.path.join(REPO, 'live_caption', 'device_config.py')
dsrc = io.open(dev_dc, encoding='utf-8', newline='').read()
i = dsrc.find('_DEFAULT_DEVICES_MINIMVP')
assert i > 0
seg = dsrc[i:i + 3000]
blk = seg[seg.find('{'):seg.find('}') + 1]
devs = dict(re.findall(r"'(\w+)'\s*:\s*'([^']+)'", blk))
res['default_devices_minimvp'] = devs
print('    代码里的 MiniMVP 出厂默认：%s' % devs)
chk('出厂默认 ASR=GPU.0', devs.get('asr') == 'GPU.0', devs.get('asr'))
chk('出厂默认 MT=GPU.0', devs.get('mt') == 'GPU.0', devs.get('mt'))
chk('出厂默认 TTS=NPU', devs.get('tts') == 'NPU', devs.get('tts'))

# ④c 候选包 profile
pp = json.loads(io.open(os.path.join(CAND, 'package_profile.json'),
                        encoding='utf-8').read())
res['package_profile'] = pp
chk('profile: NPU_TURBO 开', pp.get('npu_turbo') is True, pp.get('npu_turbo'))
chk('profile: 保留背景音开（allow_bgkeep）', pp.get('allow_bgkeep') is True,
    pp.get('allow_bgkeep'))
chk('profile: 不带 CUDA', pp.get('allow_cuda') is False, pp.get('allow_cuda'))
chk('profile: 不带 c13', pp.get('tts_c13') is False, pp.get('tts_c13'))
chk('profile: MT=mt3', pp.get('mt_model') == 'mt3-int8sym-cw-q', pp.get('mt_model'))
chk('profile: EXT v0.4.23', pp.get('ext_version') == '0.4.23', pp.get('ext_version'))

# ④d 插件侧默认：bgkeep 开、克隆关（preset A）
popup_p = os.path.join(CAND, 'ext', 'extension', 'popup.js')
if os.path.isfile(popup_p):
    psrc = io.open(popup_p, encoding='utf-8', errors='replace').read()
    m_bg = re.search(r'bgKeep:\s*\$\([\'"]bgkeep[\'"]\)\s*\?\s*\$\([\'"]bgkeep[\'"]\)'
                     r'\.checked\s*:\s*(true|false)', psrc)
    bg_default = (m_bg.group(1) == 'true') if m_bg else None
    res['bgkeep_default'] = bg_default
    chk('插件侧「保留背景音」默认开', bg_default is True, bg_default)
    # 克隆：默认音色 = <select id="voice"> 的**第一个 option**（不是 clone）
    # 🔴 实测：`popup.js` 里没有「默认音色」的字面量（默认值来自 HTML 的第一个 option）
    popup_h = os.path.join(CAND, 'ext', 'extension', 'popup.html')
    v_default = None
    if os.path.isfile(popup_h):
        hsrc = io.open(popup_h, encoding='utf-8', errors='replace').read()
        mv = re.search(r'<select\s+id="voice">(.*?)</select>', hsrc, re.S)
        if mv:
            mo = re.search(r'<option\s+value="([^"]+)"', mv.group(1))
            v_default = mo.group(1) if mo else None
    res['voice_default'] = v_default
    chk('插件侧「克隆」默认关（默认音色是预设 A，不是 clone）',
        v_default is not None and v_default.lower() != 'clone', v_default)
else:
    chk('候选包内有 ext/extension/popup.js（查插件默认值）', False, '缺失')

# ── ⑤ 除 preset_A.wav 外无音视频；无 CUDA DLL ────────────────────────
media, cuda = [], []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        rel = os.path.relpath(os.path.join(dp, fn), CAND).replace('\\', '/')
        if fn.lower().endswith(MEDIA_EXT):
            media.append(rel)
        if 'cuda' in fn.lower() and fn.lower().endswith('.dll'):
            cuda.append(rel)
other_media = [m for m in media if os.path.basename(m) != 'preset_A.wav']
chk('除 preset_A.wav 外无音视频文件', not other_media, other_media[:8])
chk('无 CUDA DLL', not cuda, cuda[:8])

# ── ⑥ ACCEPTED.json 不在包里 ────────────────────────────────────────
accepted = []
for dp, dns, fns in os.walk(CAND):
    for fn in fns:
        if fn.upper() == 'ACCEPTED.JSON':
            accepted.append(os.path.relpath(os.path.join(dp, fn), CAND))
chk('ACCEPTED.json 不在包内', not accepted, accepted)

n_fail = sum(1 for c in res['checks'] if not c['ok'])
res['n_pass'] = len(res['checks']) - n_fail
res['n_fail'] = n_fail
res['verdict'] = ('PASS（白名单全过；仍需 APP-149 第 6/7 项的冒烟与三轮门禁）'
                  if n_fail == 0 else 'FAIL（%d 项不满足 ⇒ 不打 zip）' % n_fail)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(res, ensure_ascii=False, indent=2))
print('\n结果：%d PASS / %d FAIL' % (res['n_pass'], n_fail))
print('判定：%s' % res['verdict'])
print('落盘 -> %s' % OUT)
