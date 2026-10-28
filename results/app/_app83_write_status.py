# -*- coding: utf-8 -*-
"""追加 §83 章节到 status/app/STATUS_APP.md（只追加，不回头改旧章节；保持 LF 换行）。"""
import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

ts = sys.argv[1] if len(sys.argv) > 1 else '2026-10-28 12:59'

TITLE = u'## §83 §82 Git 交付闭环已入库（commit `b0f7a43` + 普通 push）＋ 交付口径最终确认（2026-10-28 12:59）'

BODY = u'''
> 🔴 **本节只追加，不回头改旧章节**；`CORRECTIONS_APP.md` 本轮**只读、零改动**（文件 mtime = `2026-10-28 00:47:55`，早于本轮全部操作）。

### §83.0 本节范围

- §82 已完成「实测 + 同步 + STATUS 写入」，但**写在 commit 之前** ⇒ §82 章节内**不含 commit 号与 push 证据**。
- 本节**只补记 git 收尾闭环**这一件事（§82 本身不重写、不撤回）。
- **本轮无新 reviewer 纠偏条目**（`CORRECTIONS_APP.md` = APP-001…APP-033 共 33 条；`last_ack` = APP-033 ⇒ 编号 > last_ack = **0 条**）⇒ 本节**不推进任何新功能**。

### §83.1 ✅ Git 交付闭环（逐文件 add ⇒ commit ⇒ 普通 push）

**提交元数据（`git log -1` 实测）**：

| 字段 | 实测值 |
|---|---|
| 完整 SHA | `b0f7a43acd034d3e6ea8e59eb4fb3228bb4b44d3` |
| 短 SHA | `b0f7a43` |
| 提交时间 | `2026-10-28 12:58:56 +0800` |
| 父提交 | `a56722d`（§81） |
| 提交信息 | `App §82: APP-027 V1（CUDA 连续实时）实测已跑完 + NPU 身份正面实证 + 同类脆弱点全局排查 + 客户包定点同步（zip 未重打）` |
| diffstat | `7 files changed, 1844 insertions(+), 3 deletions(-)` |

**push 记录（`git push origin main` 原样输出）**：

```
To github.com:alexgang/Confucius4-OpenVINO.git
   a56722d..b0f7a43  main -> main
```

⇒ **普通 push（fast-forward，非 force）**：`a56722d..b0f7a43`（`..` 而非 `+`）⇒ **未使用 force push**。

**入库文件清单（`git show --name-only --format="" HEAD` 实测，恰好 7 个）**：

| 文件 | 状态 |
|---|---|
| `live_caption/tts_engine.py` | 改（新增 `execution_devices()` 取证 + `load_s` / `device_desc` 字段） |
| `live_caption/sync_s82_to_pkg.py` | 新（§82 客户包定点同步脚本） |
| `results/app/app119_app027_v1_cuda_real_playback.py` | 新（APP-027 V1 实测驱动） |
| `results/app/app120_npu_exec_device_proof.py` | 新（NPU 身份正面实证） |
| `results/app/app120_sync_s82_report.json` | 新（同步报告） |
| `results/app/_app82_write_status.py` | 新（§82 写入脚本） |
| `status/app/STATUS_APP.md` | 改（追加 §82） |

### §83.2 ✅ 纪律核验（逐条实测，非声明）

| 纪律项 | 核验命令 | 实测结果 | 判定 |
|---|---|---|---|
| **不提交 `CORRECTIONS_APP.md`** | `git show --name-only HEAD \\| grep -c CORRECTIONS` | **0** | ✅ |
| 同上（工作区侧） | `git status --porcelain -- status/app/CORRECTIONS_APP.md` | ` M`（reviewer 的本地改动，**未暂存、未入库**） | ✅ |
| 同上（文件零改动） | `stat status/app/CORRECTIONS_APP.md` | mtime = `2026-10-28 00:47:55`（早于本轮 12 点全部操作） | ✅ |
| **不吞其它模块改动** | `git status --porcelain` 提交后 | **491** 个改动仍在工作区（提交前 498 ⇒ 恰好减少本轮 7 个） | ✅ |
| 同上（归属抽样） | `git status --porcelain \\| grep -v "live_caption/\\|results/app/\\|status/app/" \\| wc -l` | **240** 个（ASR/MT/TTS 侧 `c045_*`/`c046_*`/… 等） | ✅ |
| **只用逐文件 add（禁 `-A`）** | 7 次 `git add -- <path>` | 暂存区 `git diff --cached --name-only \\| wc -l` = **7** | ✅ |
| **仓库只保留 main** | `git branch -a` | `* main` / `remotes/origin/HEAD -> origin/main` / `remotes/origin/main`（**无其它分支**） | ✅ |
| **普通 push / 非 force** | `git push origin main` | `a56722d..b0f7a43` | ✅ |
| **`HEAD == origin/main`** | `git rev-list --left-right --count origin/main...HEAD` | `0\\t0` | ✅ |

### §83.3 🔴 **交付口径最终确认（§82.5.1 的收尾复核）**

**准确表述（唯一可用的口径）**：

> **代码侧已入库（commit `b0f7a43`，已 push 至 `origin/main`）、已同步到客户包目录（`Confucius4_LiveCaption_v1.6\\app\\tts_engine.py`，`sha_disk == sha_cand`）；zip 未重打。**

⛔ **仍不写「已交付」** —— 依据：
- **§66 口径**：「已交付」= 包目录 + zip **已含最新代码**且**已入库** ⇒ 本轮 zip **未重打** ⇒ 三方（仓库 / 包目录 / zip）**未闭环**。
- **APP-031 明文**：「三项做完合在一起重打一次包」⇒ APP-027 的 **V3（克隆 MiniMax + CAMPPlus）**、**V4（用户实听）** 仍未做 ⇒ **APP-027 未完** ⇒ **不得单独重打 zip**。
- 本轮 `git show --name-only HEAD` 中**无任何 zip 产物**，与该口径一致（**没落盘的东西不能写「已交付」**）。

### §83.4 ⛔ **本轮「未做/ 未成立」清单（逐条重申，防止被误读为已闭环）**

1. ⛔ **APP-027 未完**：V1（CUDA 连续实时）本轮已跑完（§82）；**V2** 已于 §81 跑完；**V3（克隆 MiniMax + CAMPPlus）未跑**、**V4（用户实听）未跑** ⇒ **APP-027 整体未完**。
2. ⛔ **zip 未重打** ⇒ 客户包 zip 内**不含** §82 的 `tts_engine.py` 改动 ⇒ **「已交付」不成立**。
3. ⛔ **「用户听得到」仍不成立**：§82 走的是 **CLI + 真实播放路径**（走声卡），**不等于用户真实启动方式**（§63 L4：桌面快捷方式 → `.venv\\Scripts\\pythonw.exe`）⇒ **GUI 复现未做**。
4. ⛔ **「首包」指标定义未裁定**：边车「只缓存一块」机制 ⇒ 客户端量到的 `first_s` 实为**整句 DONE 时间**而非首块时间（与 APP-027⑤「记录第一块」不符）⇒ **待 reviewer 裁定**。
5. ⛔ **RTF 归因边界未裁定**：`synth_rtf_p50=3.6184` / `p95=3.6515` ⇒ 合成仅实时 ~1/3.6 ⇒ 句内必然持续欠载（`underflow_in_sentence` P95 = 399 ≠ 0）⇒ **未改代码**，属 reviewer 裁定项。
6. ⛔ **`app062` A/B 判据本身有实质问题**（手动标志位 `cp_on_cpu` + 基线已过时）⇒ **未重做**（见 §82.3）⇒ **不作为结论引用**。
7. ⛔ **「不变式」判据口径**：本轮 V1 的 `V1-5` 用两段式 `n_played + n_dropped == n_submitted` ⇒ 报 `got=25 / want=76` **FAIL**，但这是**判据口径问题不是产品缺陷**（真实状态：25 播 + 0 丢 + 51 未构建完 = 76 守恒，`close()` 收尾才计丢句，计数发生在状态行打印之后）⇒ **正确口径应为三段式** ⇒ **是否改判据待 reviewer 裁定**（§82.1 与 §82.5.2 第 4 项）。
8. ⛔ **未向 MiniMax 回转写**（质量判定归 reviewer）；**未跑 `verify_pkg_zip.py`**、**未开 FTP**（§66 口径）。

### §83.5 🔴 **待 reviewer 裁定（4 项，与 §82.5.2 一致，本轮**未自行推进**）**

1. 🔴 **RTF 归因边界** —— 是否接受「双侧争用」作为主因解法优先级依据（cp_decode 减负 > ASR 迁 `GPU.1` 独显）？**ASR 迁设备属 ASR 模块决策，App 不自行改**。
2. 🔴 **「首包」指标的定义** —— 边车侧是否需要暴露**真正的首块时间**（而非整句 DONE 时间）？是否要求改 `tts_cuda_sidecar.py`？
3. 🔴 **`app062` A/B 是否重做** —— 判据已过时，是否重跑基线？
4. 🔴 **是否把「不变式」判据改成三段式**（`n_played + n_dropped + n_drop_unbuilt == n_submitted`）？

### §83.6 本节涉及文件清单（本次仅新增 1 个写入脚本）

| 文件 | 字节 | 说明 |
|---|---|---|
| `results/app/_app83_write_status.py` | 本节追加脚本 | 只追加 + 头部字段保持 + `newline=''` 保 LF |
| `status/app/STATUS_APP.md` | — | 追加 §83（**只追加，未改旧章节**） |

### §83.7 头部字段

- `last_ack` = **APP-033**（**保持不变**：本轮无新 reviewer 纠偏条目 ⇒ 无编号可 ack）。
- 「更新时间」= **2026-10-28 12:59**（`Get-Date -Format "yyyy-MM-dd HH:mm"` **实测值**，非推算）。
'''


def main():
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    if TITLE.split(u'（')[0].strip() in text:
        print('ABORT: \u00a782 \u5df2\u5b58\u5728\uff0c\u62d2\u7edd\u91cd\u590d\u8ffd\u52a0')
        return 2
    if not text.endswith(u'\n'):
        text += u'\n'
    text += BODY
    with io.open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print(u'\u00a783 \u5df2\u8ffd\u52a0\uff1b\u603b\u884c\u6570 = %d' % text.count(u'\n'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
