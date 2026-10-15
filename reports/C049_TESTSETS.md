# C-049 中英文长音频测试集

## 为什么需要

现有唯一测试集 `test_audio/260902_SPE_audio.wav`（61.19 min）是**纯英文** NVIDIA QGS
会议录音。交付前有两个缺口：

1. **中文完全未验证** — C-047 引入的自适应生成长度含 `is_last_token_chinese` 分支
   （中文时预算放宽 ×2），代码逻辑已单元级验证，但**从未在真实中文流式上跑过**。
   这是当前最大的未知风险。
2. **无中英夹杂场景** — 真实会议/演讲里中英混说是常态，纯英文集无法覆盖。

## 语料来源

均取自 OpenSLR，16kHz，许可清晰，**不混用语料版权**：

| 语种 | 语料 | 规模 | 转写 | 许可 |
|---|---|---|---|---|
| 中文 | AISHELL-1 (SLR33) | 178h / 400 人 | 官方人工转写（>95% 准确） | Apache 2.0 |
| 英文 | LibriSpeech test-clean (SLR12) | 5.4h / 2620 条 | 官方转写 | CC BY 4.0 |

> **选型说明**：优先找过 TED-LIUM（中英夹杂最典型），但它在 OpenSLR 已下架
> （SLR51/SLR7 均 404）；WenetSpeech 需腾讯会议 SAFEBOX 密码审批。故改用
> 「官方双语语料 + 拼接成混合集」路线 —— 每段都有官方 ground truth，
> 拼接后整体 WER 依然可算，且可与文献基线直接对比。

## 三套测试集

用 `c049_build_testsets.py` 生成，规格与现有测试集**完全一致**：

```
16kHz · mono · PCM_16 · [start-end] text 分段格式
```

| 名称 | 内容 | 时长 | 段数 |
|---|---|---|---|
| `en_60min` | LibriSpeech 拼接 | 60.13 min | 449 |
| `zh_60min` | AISHELL-1 test 集拼接 | ~60 min | ~2400 |
| `mix_60min` | 中英按段交替 | ~60 min | 中英各半 |

产物目录 `test_data/sets/<name>/`：

```
audio.wav            拼接后的长音频
ref_official.txt     语料官方人工转写（ground truth 主口径）
ref_minimax.txt      MiniMax 转写（与现有 61min 口径统一，脚本生成）
manifest.json        段清单：来源文件 / 起止时间 / 文本
```

## Ground truth 双轨口径

| 口径 | 来源 | 用途 |
|---|---|---|
| `ref_official.txt` | 语料官方人工转写 | 主口径，严谨，可与文献基线对比 |
| `ref_minimax.txt` | MiniMax cloud ASR | 与现有 61-min 历史数据同口径，便于横向比较 |

两者差异可给出 WER 的置信区间。

## 构建命令

```powershell
# 下载语料（约 15.3 GB，一次性）
cd test_data
curl -L -C - -o data_aishell.tgz https://www.openslr.org/resources/33/data_aishell.tgz
curl -L -C - -o test-clean.tar.gz https://www.openslr.org/resources/12/test-clean.tar.gz
tar -xzf test-clean.tar.gz
tar -xzf data_aishell.tgz
cd ..

# 构建三套测试集
.venv/Scripts/python.exe c049_build_testsets.py --lang en  --target-min 60
.venv/Scripts/python.exe c049_build_testsets.py --lang zh  --target-min 60
.venv/Scripts/python.exe c049_build_testsets.py --lang mix --target-min 60

# 生成 MiniMax ground truth（需 $MINIMAX_API_KEY）
.venv/Scripts/python.exe c049_minimax_ref.py test_data/sets/zh_60min
```

## 中英混合的归一化口径（重要）

中文无词边界，**按字切**（CER 标准做法）；英文按词切。混合 token（如 `gpu加速`）
拆成 `gpu` + `加` + `速`。实现见 `c049_build_testsets.py::norm_words`。

**这意味着中英混合集的 WER 与纯中文/纯英文集的 WER 不是同一量纲**，横向比较时需注意。
纯中文集应看 CER，纯英文看 WER。

## 跑流式验证

```powershell
# 用现有部署入口（自适应预算为默认）
.venv/Scripts/python.exe transcribe_stream.py test_data/sets/zh_60min/audio.wav

# 计算 WER（注意把 REF 指向对应参考文本）
.venv/Scripts/python.exe c045_wer.py reports/<transcript>.txt
```

> `c045_wer.py` 默认 REF 指向现有 61-min 的 MiniMax 参考文本，跑新测试集时需显式
> 指定对应参考文件，或参照其 `ref_words()` 适配中文字级切分。

## 状态

- [x] 语料下载（LibriSpeech 完成 / AISHELL 下载中）
- [x] `en_60min` 构建完成并通过流式冒烟（输出与参考高度一致）
- [ ] `zh_60min` / `mix_60min` 构建
- [ ] MiniMax ground truth 生成（需 API key）
- [ ] 三套集的完整 WER 实测