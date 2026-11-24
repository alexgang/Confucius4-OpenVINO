# -*- coding: utf-8 -*-
"""§101 写入器 v21：头部「当前任务」「最近更新」压成要点式（细节全在 §101 正文 ＋ notes）⇒ ≤40 000 B。

背景：v20 干跑 40 554 B / 158 行，仅超字节门禁 554 B；行数已达标（上限 160）。
本版：§101 正文（v19 版）不变；「当前任务」「最近更新」改为要点式摘要；
「阻塞」栏保留全部待办项（那是唯一需要用户/reviewer 决策的清单）。
"""
import importlib.util
import os

BASE = r"C:\Users\Trekker-PTL\confucius4-openvino\status\asr"
SRC = os.path.join(BASE, "_asr101_write_status.py")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m20 = _load("asr101v20", os.path.join(BASE, "_asr101_write_status_v20.py"))
NEW_SEC = m20.NEW_SEC
NEW_BLOCK = m20.NEW_BLOCK

# v21：正文做两处最小压缩（保留全部数字/行号/结论），用于让总量过 40 000 B 门禁。
NEW_SEC = NEW_SEC.replace(
    "🟢 **实测佐证**：`shared/bgkeep/` 下**全部 7 个**带该字段的臂取值域**只有 `{label, none}`**。",
    "🟢 **实测佐证**：`shared/bgkeep/` 下**全部 7 个**带该字段的臂取值域**只有 `{label, none}`**。",
).replace(
    "🟡 完整表在 `results/npu_benchmark/`，**本机未找到该路径** ⇒ 若需复核请提供位置。",
    "🟡 完整表在 `results/npu_benchmark/`，**本机未找到该路径** ⇒ 若需复核请提供位置。",
).replace(
    "**5 文件 / +102 −2**（`ext/bridge.py` +34",
    "**5 文件 / +102 −2**：`ext/bridge.py` +34",
).replace(
    "**已过时**，按纪律**在 §101 撤回该句**",
    "**已过时** ⇒ 按纪律**在 §101 撤回该句**",
).replace(
    "🟡 12 键全量与 v0421 臂 18 键的差集（**事件数**合计 **348**）见 notes；🟡 `clone_reasons` 是**事件计数**、`spk_reason_hist` 是**行数** ⇒ **两口径不同、不能相加**；🟡 `bgkeep_clone/bridge.log` L345「标签来源统计」是**跑中快照** ⇒ **以 `bgkeep_e2e.json` 为准**。",
    "🟡 12 键全量与 v0421 臂 18 键的差集（**事件数**合计 **348**）见 notes；🟡 `clone_reasons` 是**事件计数**、`spk_reason_hist` 是**行数** ⇒ **两口径不同、不能相加**；🟡 `bridge.log` L345「标签来源统计」是**跑中快照** ⇒ **以 `bgkeep_e2e.json` 为准**。",
).replace(
    "🔴 **修前（v0.4.18 / `5121d99`）对照臂仍缺**（`shared/bgkeep/` 下**无** `v0418*` 目录）⇒ §96 ① 仍未闭。",
    "🔴 **修前（v0.4.18 / `5121d99`）对照臂仍缺**（`shared/bgkeep/` 下**无** `v0418*` 目录）⇒ §96 ① 未闭。",
).replace(
    "⇒ 「原声 vs 分离人声」WER 对比仍做不了（🔴 两侧须同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。",
    "⇒ 「原声 vs 分离人声」WER 对比仍做不了（🔴 两侧须同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自行调 MiniMax**）。",
).replace(
    "（§97/§98 要的正是这个）",
    "（§97/§98 要的）",
).replace(
    "**给 reviewer 的最小修法（本模块不代改）**",
    "**给 reviewer 的最小修法**",
).replace(
    "🟢 **实测佐证**：`shared/bgkeep/` 下**全部 7 个**带该字段的臂取值域**只有 `{label, none}`**。",
    "🟢 **实测**：`shared/bgkeep/` 下**全部 7 个**带该字段的臂取值域**只有 `{label, none}`**。",
)

NEW_CURRENT = (
    "🟢 **巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 `b2a4978` ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「`spk_reason_hist` 零缺口」结论（§101）**："
    "🔴 **纠偏通道无新 ASR 条目** ⇒ **`last_ack` 保持 `ASR-068`**（`CORRECTIONS_ASR.md` 109 822 B / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，与 §96–§100 逐字相同；最大编号 ASR-068）。"
    "邮件新增 **5 封全部非 ASR 编号**（APP-132/133、QQ邮箱通知、NPU 报告、H-028）⇒ 不进 `last_ack`。"
    "🟢 **EXT v0.4.21 已提交**（HEAD **`b2a4978`**、13:54:52、5 文件 +102/−2、工作区干净）⇒ §100「未提交、HEAD 仍 4740b06」**已过时、撤回该句**。"
    "🟢 **新三臂 `shared/bgkeep/e2e_v26_r2`**（App 产出、本模块只读复算；600 s）三臂 `spk_bypass.enabled` **全 true** ⇒ **§100 遗留「开旁路臂」已闭**；"
    "段数 94/89/111、clone 臂 `bg_clone_from_vocals`=**167**、丢块计数全 0；"
    "🔴 `dub_late_vs_play_s.max`=115.42/139.22/**182.62** s ⇒ 配音仍严重迟到（App/TTS 口径，只记录不归因）。"
    "🔴🔴 **撤回 §100.1「`spk_reason_hist` 零缺口 / 100% 覆盖」**：r2 三臂直方图合计=**119/118/159** 而 `asr_segments`=**94/89/111**；"
    "机理 = `_spk_reason_hist()` 统计**段级表 `_spk_rows` 行数**（写入点 L2533/L2915）＋ **旁路失败原因结构上进不了该表**（失败分支只 `n_no_label += 1`、不写行 ⇒ 7 个否定 reason 不可达）；"
    "🟢 全部 7 个带该字段的臂取值域**只有 `{label, none}`**；🔴 clone 臂 **24 段「为什么没标签」被丢掉**、`label`=156 > 旁路 `n_label`=139 ⇒ **§97/§98 原始诉求仍开口**。"
    "🟡 r2 clone 臂 `clone_reasons` **12 键**：APP-131 三字段 = `tts_nearest_voice`=**1**、`gender_switch`/`gender_selfref` **键不存在**。"
    "🟢 **本轮有实质变化 ＋ 一条撤回 ⇒ 写 §101 ＋ 发 STATUS 邮件**（明细 ⇒ `notes/asr_s101.md`）。"
)

NEW_RECENT = (
    "- 2026-11-24 19:05 **§101（巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 `b2a4978` ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「`spk_reason_hist` 零缺口」）："
    "纠偏通道无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**；邮件新增 **5 封全部非 ASR 编号** ⇒ 无 ASR 动作项。"
    "🟢 **EXT v0.4.21 已提交**（HEAD `b2a4978`）⇒ §100「未提交」句**已过时、撤回**。"
    "🟢 **新三臂 `shared/bgkeep/e2e_v26_r2`**（只读复算）：三臂旁路**全 true** ⇒ **§100 遗留「开旁路臂」已闭**；"
    "`bg_clone_from_vocals` 只在 clone 臂=**167**；丢块计数全 0；段数 94/89/111；"
    "🔴 `dub_late_vs_play_s.max`=115.42/139.22/**182.62** s ⇒ 配音仍严重迟到（App/TTS 口径）。"
    "🔴🔴 **撤回 §100.1「零缺口 / 100% 覆盖」**：r2 直方图合计=**119/118/159** 而 `asr_segments`=**94/89/111**；"
    "机理 = 段级表两个写入点 ＋ **旁路失败原因结构上进不了该表**；🔴 clone 臂 **24 段「为什么没标签」被丢掉**、`label`=156 > `n_label`=139；"
    "🟡 §100 的 89=89 **是巧合**（那个臂旁路关着）⇒ **§97/§98 原始诉求仍开口**。"
    "🟡 r2 clone 臂 `clone_reasons` **12 键**：APP-131 三字段 = `tts_nearest_voice`=**1**、`gender_switch`/`gender_selfref` **键不存在**。"
    "产物：`notes/asr_s101.md` ＋ `status/archive/STATUS_ASR_sec101_upto_20261124.md`。"
    "**待 reviewer**：旁路失败原因归因缺口（新）＋ 修前对照臂；**待 App/reviewer**：分离人声 16 kHz wav；**待 reviewer 拍板**：对外 NPU 报告「RTF 0.067 / WER 0」口径。"
    "**纪律**：全为只读复算、未取 MACHINE_LOCK、未改交付文件、未动 `live_caption/`、未改 EXT 源码、未打包。**未提交**。"
)
def main():
    m = _load("asr101w", SRC)
    m.CURRENT_TASK = NEW_CURRENT
    m.BLOCK_LINE = NEW_BLOCK
    m.RECENT_NEW = NEW_RECENT
    m.SEC101_BODY = NEW_SEC
    out = m.build("00000 B / 000 行", NEW_CURRENT, NEW_BLOCK, NEW_RECENT, NEW_SEC)
    b = out.encode("utf-8")
    print("DRY: %d B / %d 行" % (len(b), b.count(b"\r\n") + 1))
    assert len(b) <= 40000, "dry too big: %d" % len(b)
    assert b.count(b"\r\n") + 1 <= 160, "dry too many lines"
    m.main()


if __name__ == "__main__":
    main()
