#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「接续轮」的结果**追加**到 §217 companion（append-only）。

纪律：
- 开工先备份；写后复核（UTF-8 **文本**比对，不是二次 encode）；
- 一律「临时文件 → os.replace」；
- 自检 FAIL ⇒ **源文件零改动**。
"""
import hashlib
import os
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
COMP = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec217_detail_20261120.md')

ADD = """
---

## §7 接续轮（TAKEOVER，2026-11-20 18:00 → 18:2x）｜🔴 **10 语种「0/10」是假 FAIL：连修 3 处「判据自身」缺陷后才 10/10 PASS**｜🟢 **整包体积实测 24.26 GiB**｜🟢 **EXT v0.4.18 冒烟 7/7 PASS**｜🔴 **完整版出厂默认（ASR+MT+TTS 全 GPU.0）10 分钟整链仍 FAIL**

### 7.1 开工现场（TAKEOVER ⇒ 从断点继续）

- 租约：`session_lease.py acquire app` ⇒ **TAKEOVER**（上一会话 token `0745f901`，
  `last_beat 11-20 16:57:25`，**心跳超时 62 min ⇒ 已死**）⇒ 本轮**不重做**已完成的活。
- 上一会话留下的现场（**全部已落盘、可核对**）：
  v2.5 目录已建成、`ext/` 已换 v0.4.18、模型身份已核对、10 语种静态表已核、
  CUDA 档显隐已核、zh 整链臂（FAIL）、zh CUDA 整链臂（PASS）、§217 companion 初稿。
- 上一会话**死在哪**：**16:57** 的「10 语种真跑」**判为 FAIL（0/10）** ⇒ 会话即死在该处。

### 7.2 🔴 那个「0/10 FAIL」是**假 FAIL**：判据自身有 3 处缺陷（本轮逐一修掉）

| # | 缺陷 | 现象 | 真相 | 修法 |
|---|---|---|---|---|
| ① | `tts_engine.make_engine()` **没有 `voice` 参** | `TypeError: make_engine() got an unexpected keyword argument 'voice'` ⇒ 引擎**根本没建起来** ⇒ B 组 0/10 | 签名是 `(device, model_path, cache_dir, on_log, precision)`（`tts_engine.py:711`）；**音色不是引擎参数**，走 `speaker_embed`／内置 `speaker`（`tts_worker.py:1566-1626` 的 `_setup_babelvox_voice()`） | 先 `make_engine(device=…)` ⇒ `tts_engine.speaker_embedding(eng, preset_voice_path('A'))` ⇒ `tts_engine.stream(eng, text, language=…, speaker_embed=…)` |
| ② | 把**语言代号** `'zh'` 直接喂给引擎 | 日志 `Language 'zh' not recognized; … Falling back to language-agnostic mode.` ⇒ **等于没测到该语种** | 产品真实路径是 `tts_engine.map_language(lang)`（`tts_worker.py:3385`）⇒ `'zh'→'Chinese'`；babelvox 只认**英文全称** | 改走 `map_language()`；并**新增两条判据**：**B2** 引擎**不得**报任何 `not recognized`；**B3** 映射后的 id 必须都在 `SUPPORTED_LANGS` 内 |
| ③ | `translator.translate(text, tgt)` 的 `tgt` 传了**全名** | `KeyError: 'Chinese'` ⇒ C 组 0/10 | `build_messages()` 内部做 `_LANG_NAME[tgt]`（`translator.py:760-780`）⇒ `tgt` 必须是**代号** | 传代号；并把 MT 源句**固定成英文**（源语==目标语会走「同语免译」短路 ⇒ 没测到模型） |

**还改了「反证组」的判据口径**（原判据也不对）：
引擎对**未知语言**其实**会**告警并回落、**照样出声**（实测 0.96 s）⇒ 不能拿
「引擎不出声」当判据；产品真正的两道闸是 ① `map_language(lang, strict=True)` **抛错**
② `language_supported(原始 id)` = **False** ⇒ 反证组改成查这两道闸。

**最终结果**：`results/app/app118_lang10_evidence.json`（8 988 B／SHA `7ce6fa9dbed0d1b0…`
／2026-11-20 18:10:39）＝ **10 PASS / 0 FAIL**。

| 语种 | zh | en | ja | ko | de | fr | es | pt | it | ru |
|---|---|---|---|---|---|---|---|---|---|---|
| 配音时长(s) | 1.60 | 1.52 | 2.48 | 1.52 | 2.00 | 2.32 | 1.92 | 1.60 | 2.56 | 2.16 |
| RTF(集显) | 4.97 | 3.93 | 4.50 | 3.25 | 3.99 | 3.94 | 3.23 | 3.82 | 3.84 | 3.96 |

- **B 10/10 配音出声**（peak 0.3756–0.6765，**非静音**）；**B2/B3** 映射正确（**零回落**）。
- **C 10/10 字幕出译文**（`skipped=False`，逐条实测：zh「今天天气很好，我们可以去公园散步。」／
  ja「今日は天気が良く、公園で散歩に行けます。」／ko「오늘 날씨가 좋으니 공원에서 산책을 할 수 있어요.」／
  de「Das Wetter ist heute schön…」／ru「Сегодня хорошая погода…」…）。
- **D 反证组 PASS**：`map_language('xx', strict=True)` 抛错 ＋ `language_supported('xx')`=False。

🔴 **顺带查出一个「潜在风险」（本轮**不改产品代码**，登记为未结项）：
`map_language()` **非 strict** 对未知码**静默回落 English**；而 `tts_worker` 是
`map_language(lang)` **之后**才判 `language_supported(blang)` ⇒ 这道闸**抓不到**未知码。
实测未知码在**原始 id** 上判定正确（False）。⇒ 风险面＝App 只会传 `TARGETS` 里的 10 个合法码 ⇒ **不构成交付阻塞**。

### 7.3 🟢 整包体积（APP-118 §3：「报告整包体积（预计 20 GB 以上）及各部分的体积构成」）

`results/app/app118_pkg_size.json`（1 628 B／SHA `87081f0d19c101e5…`／18:03:52）：
**26 048 403 469 B ＝ 24.26 GiB／48 789 文件**

| 部分 | 字节 | GiB | 文件数 |
|---|---|---|---|
| `models/` | 20 090 013 347 | 18.71 | 170 |
| `cuda_env/` | 5 105 789 206 | 4.76 | 34 126 |
| `python/` | 842 064 347 | 0.78 | 14 046 |
| `app/` | 3 933 803 | 0.004 | 78 |
| `ext/` | 3 701 492 | 0.003 | 207 |
| 其余（`.runtime_deps`/`docs`/README 等） | < 2.5 MB | — | 162 |

⇒ **>20 GB 的预期成立**（24.26 GiB）。

### 7.4 🟢 EXT v0.4.18 冒烟（APP-118 §3：「EXT v0.4.18 冒烟一次」）

`results/app/app118_ext_smoke_evidence.json`（2 782 B／SHA `064629149952ca46…`／18:14:13）＝ **7 PASS / 0 FAIL**
（**进程级 + HTTP 级**，不是 grep）：
A1 版本一致（`version.py` 与 `manifest.json` 都是 **0.4.18**）｜A2 桥接**真能启动**｜
A3 `/health` 200+JSON｜A4 `/status` 200+JSON 且 popup 需要的字段齐全｜
A5 `/pair` 契约符合 v0.4.0（固定 `token="nopair"`）｜A6 端口被占 ⇒ **退出码 6**（不白等）｜
A7 与实时字幕 App 互斥（本机 App 未运行 ⇒ 不适用）。

- 🔴 **第一版判据自己错了 2 处**（本轮已修并如实记录）：
  ① `python ext/bridge/bridge.py` **跑不起来**（`ImportError: attempted relative import with no
  known parent package`）⇒ **必须 `-m ext.bridge`**（cwd＝包根、`PYTHONPATH`＝包根+`.runtime_deps`）
  ——这正是**产品启动器** `tools/ext_launcher.py:494` 用的那条命令；
  ② `/status` 的契约里**本来就不含版本号**（版本一致性由 A1 单独验）、`/pair` 自 **v0.4.0** 起
  **取消 token 配对**（固定 `nopair`）⇒ 原先那段 Origin 校验在 `return` **之后**＝**死代码**
  （**EXT 自己 v0.4.0 的决定，属 EXT 模块 ⇒ 本轮只记录、不改**）。
- 🔴 **口径限制（如实登记）**：本轮用 **`--echo`（回声自测）模式** ⇒ **不加载** ASR/MT/TTS 引擎
  ⇒ 零占 GPU。⇒ **`--real` 真引擎链路本轮未覆盖**（需独占 GPU 窗口）⇒ 登记为未结项。

### 7.5 🔴 完整版**出厂默认**的 10 分钟整链＝**FAIL**（承上一会话，本轮定性）

| 臂 | 包 | TTS 后端 | 结论 |
|---|---|---|---|
| zh（**出厂默认** ASR/MT/TTS 全 GPU.0） | v2.5 | OV/babelvox（集显 f32） | 🔴 **FAIL**（rc=1／`timing_valid=false`）：译文 150 ⇒ 只提交 **36** 句进 TTS；积压涨到 **917 s**；`r_recent≈4.4` ⇒ **合成跟不上** |
| zh（**CUDA 档**） | v2.5 | NVIDIA CUDA | 🟢 **PASS**（rc=0／`timing_valid=true`）：译文 **150** == 进 TTS **150**，丢弃 **0**，就绪前排队 8 → 补发 8；`speed max=1.576`；RTF P90 **0.6314**；锁全程未被抢（61 采样 0 次外来变动） |

证据：`results/app/app591_acceptance_app118_v25_zh_run20261120-162601.json`
（23 948 B／SHA `0089c6ff02efe618…`）／`…_zh_cuda_run20261120-164527.json`
（25 331 B／SHA `9dcf4498ab531afb…`）。

🔴 **定性（重要）**：查了**全部**历史 `app591_acceptance_*.json` ⇒ **之前的 10 分钟整链臂
（APP-113/114/115 那些）全部跑在 SpecialMVP sp5 上（TTS＝NPU）**，**完整版（v2.x）的 OV 整链
从来没有过一条 PASS**。⇒ **这不是 v2.5 引入的回归**，而是**完整版出厂默认
（ASR+MT+TTS 全塞 Intel 集显 GPU.0）在 10 分钟连续负载下追不上**的**既有局限**。

⚠️ **口径**：`APP-118 §1` 明文「**默认设备不变**：TTS 默认仍按当前完整版的出厂默认（OpenVINO），
CUDA 由用户手动选择。**若要改默认，先问用户**」⇒ 本轮**一个字都没改默认**。
⇒ 该局限**如实登记**，并**等用户裁定**（可选：① 完整版默认把 ASR 挪到 NPU；
② 完整版默认 TTS 改 CUDA；③ 保持现状但把 iGPU 档标成「非实时」）。
"""

def main():
    orig = open(COMP, encoding='utf-8').read()
    if '## §7 接续轮' in orig:
        print('ABORT: companion 里已有 §7 ⇒ 不重复追加')
        return 1
    bak = os.path.join(tempfile.gettempdir(),
                       'STATUS_APP_sec217_detail.bak_%s.md'
                       % COMP.replace(os.sep, '_')[-30:])
    shutil.copyfile(COMP, bak)
    print('备份：%s（%d B）' % (bak, os.path.getsize(bak)))

    new = orig + ADD
    if not new.startswith(orig):
        print('ABORT: 新文本不是原文的前缀')
        return 1
    if len(new.encode('utf-8')) <= len(orig.encode('utf-8')):
        print('ABORT: 追加后没有变长')
        return 1

    # ── 写前自检（在内存里的新文本上做） ──────────────────────
    checks = []
    checks.append(('旧正文逐字保留（原文是新文本的前缀）',
                   new.startswith(orig)))
    checks.append(('旧正文长度未变（逐字）',
                   len(orig) == len(open(bak, encoding='utf-8').read())))
    checks.append(('新增块含 §7 标题', '## §7 接续轮' in new))
    checks.append(('新增块含 10 PASS / 0 FAIL 结论',
                   '10 PASS / 0 FAIL' in new))
    checks.append(('新增块含整包体积数字',
                   '26 048 403 469' in new))
    checks.append(('新增块含 10 语种证据文件名',
                   'app118_lang10_evidence.json' in new))
    checks.append(('新增块含 EXT 证据文件名',
                   'app118_ext_smoke_evidence.json' in new))
    checks.append(('UTF-8 文本解码无错', True))
    bad = [n for n, ok in checks if not ok]
    if bad:
        print('写前自检 FAIL：%s ⇒ 源文件零改动' % bad)
        return 1
    print('写前自检 %d/%d PASS' % (len(checks), len(checks)))

    tmp = COMP + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, COMP)

    # ── 写后复核（独立再读，按 UTF-8 文本比对） ───────────────
    back = open(COMP, encoding='utf-8').read()
    post = [
        ('旧正文逐字未变', back.startswith(orig)),
        ('字节数 = 写前计算', len(back.encode('utf-8'))
         == len(new.encode('utf-8'))),
        ('§7 存在', '## §7 接续轮' in back),
        ('文件可被 UTF-8 解码', True),
    ]
    bad = [n for n, ok in post if not ok]
    if bad:
        print('写后复核 FAIL：%s' % bad)
        return 1
    print('写后复核 %d/%d PASS' % (len(post), len(post)))
    print('companion：%d B → %d B（SHA %s）'
          % (len(orig.encode('utf-8')), len(back.encode('utf-8')),
             hashlib.sha256(back.encode('utf-8')).hexdigest()[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
