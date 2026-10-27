# -*- coding: utf-8 -*-
"""§80 头部更新脚本（只改 STATUS_APP.md 的头部 4 字段 + 「最近更新」区）。

纪律：
  * 只改 header 的 4 行（last_ack / 更新时间 / 当前任务 / 阻塞）
  * 「最近更新」区：插入 §80 一行 + 删掉最旧一行 ⇒ 保持 ≤15 行
  * 旧章节**不动**（只追加）
  * 失败必须抛异常（绝不静默）
"""
import os

P = r'C:\Users\Trekker-PLT_PLACEHOLDER'
P = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'

NEW_TASK = (
    '当前任务: **§80 🔴🔴 APP-033 三条全部执行完毕（CUDA 组判据**已过** '
    '`verdict_after_clean=true` ＋ APP-028 5 分钟实测已跑完）＋ 自查抓出并修掉 4 处真实缺陷** '
    '⇒ ✅ **APP-033①**：`quota.py` 在 reviewer 本机 ⇒ **不是 App 的阻塞项**'
    '（wav+json+逐句 jsonl 已落盘）'
    '⇒ ✅ **APP-033②**：CUDA 组日文 A/B **已跑完并通过**'
    '（边车解释器 `C:\\Users\\Trekker-PTL\\_fq3tts_env\\Scripts\\python.exe`'
    ' ⇒ torch `2.11.0+cu128` / `cuda_available True` / RTX 5050；持锁 + 安静窗口；'
    '**零 CPU 推理**；**未调 MiniMax**）'
    '⇒ 改前臂（`d80ef22`）**cap=2 / hang=2**，第 9 句「2026年の売上は52%増えました」被判 `lang=en` ⇒ '
    '**frames=2038 / got_sec=163.04 / chunks=255 / hang=true** ⇒ 与 reviewer 记录的'
    '「255 块 / 163.0 s」**逐项吻合**（根因成立）'
    '⇒ 改后臂（HEAD）**cap=0 / runaway=0 / hang=0 / err=0**，87 组配对**异常行 0 条** ⇒ '
    '**`verdict_after_clean=true`**（判据已过）'
    '⇒ 回归（zh/en 各 10 句）同样 0/0/0 ⇒ got_sec 中位 2.88（两臂同）/ '
    's/字 中位 0.1094→**0.1031**（无回退）'
    '⇒ ✅ **APP-033③**：APP-028 的 **SPE 前 5 分钟完整实测已跑完并 10/10 PASS**'
    '（76 句 / `n_played=76` / `n_dropped=0` / `n_restart=0` / `max_backlog_s=68.79` / '
    '`synth_rtf_p95=1.1511` / `max_synth_gap_s=9.61`）⇒ **「丢句=0」现在才成立**'
    '（§79.4 的 60 秒冒烟不构成）'
    '⇒ 🔴🔴 **自查抓出并修掉 4 处真实缺陷**（`machine_lock_app.py`）：'
    '① 解析不出 ASR 的 `PID=` 格式 ② 解析不出锁的起始时间戳 '
    '③ 解析不出 EXT 探针的**第三种锁格式** '
    '④🔴🔴🔴 **等锁循环每 20 s「创建 tmp + 删除 tmp」⇒ 等锁 987 s = 50 次删除 '
    '⇒ 触发批量删除保护 ⇒ 进程被杀 ⇒ 报告未生成 ⇒ 整轮实测白跑**'
    '（本轮实测事故，已修 + 实测复验：等锁 40 s 零 tmp 残留）'
    '⇒ ✅ **验收 `test_machine_lock_app.py` 40/40 PASS**（含 **3 条 AST 重建反证**）'
    '⇒ ✅ **撤回 §78/§79 头部「CUDA 对照组客观做不了」**（那是主/包内 python 的事实，不是边车的）'
    '⇒ ⛔ **APP-027 的 V1–V3 未跑**（V2/ABBA 因安静窗口 900 s 超时 fail-closed 退出 ⇒ '
    '`app027_v2/` 实测为空 ⇒ 无产物）'
    '⇒ ⛔ **GUI 复现 / CER 对比 / 用户实听未做**、⛔ **zip 未重打**（APP-031 合打）⇒ '
    '⛔ **「用户听得到」仍不成立** ⇒ 🔴 **`last_ack` = APP-033**'
)

NEW_BLOCK = (
    '阻塞 / 待用户决定: ① 🔴 **APP-030 的 CUDA 组判据已过**'
    '（§80.2：`verdict_after_clean=true`，改后臂 cap/runaway/hang/err 全 0），'
    '**NPU 组亦已过**（§78）⇒ ✅ **两个引擎组的 A/B 判据都过了** ⇒ 但 **GUI 复现（丢句=0）未做**'
    '（§80.5 走 CLI 回放）⇒ **仍不得写「日文问题全链路已解决」**；'
    '② 🔴 **APP-033① 的口径已更正**：`quota.py` 与 MiniMax 回转写**在 reviewer 本机** ⇒ '
    '**不是 App 的阻塞项** ⇒ App 侧只负责 wav+json+逐句 jsonl 落盘（**已完成**）⇒ '
    '⛔ **本轮未调 MiniMax**（质量判定交 reviewer）；'
    '③ 🔴 **CER 对比未做**（改后日文 CER 不得劣于改前非失控句）⇒ **wav+json 已落盘** ⇒ '
    '**回转写由 reviewer 做**；'
    '④ ⛔ **APP-027 的 V1（CUDA 连续实时）/ V2（ABBA）/ V3（MiniMax+CAMPPlus）未跑**'
    '（V2 因安静窗口 900 s 超时 fail-closed 退出）⇒ **需重跑**；'
    '⑤ ⛔ **「用户听得到」仍不成立**（§63 L4 等用户实测：桌面快捷方式 → CUDA 朗读 → NPU 朗读 → 克隆音色 ⇒ '
    '用户亲口确认前不得写「能出声」）；'
    '⑥ 🔴 **「句首标点」的产品侧处理策略待 reviewer 裁定**'
    '（§80.3：实测唯一触发条件 = **句子以全角标点开头**；句中逗号/句号都不触发）'
    '⇒ 本轮**只修语料、未改生产代码**（MT 译文确实可能以标点开头 ⇒ 是真实输入面 ⇒ 修哪一层属产品决策）；'
    '⑦ ⛔ **zip 未重打**（APP-031 明文「三项做完后合在一起重打一次包」⇒ APP-027 未完）⇒ '
    '按 §66 口径**不写「已交付」**；'
    '⑧ 🔴 **机器锁纪律**：外部 `EXT-p1-real` / `asr` 会持锁 ⇒ ctypes 实测 `exit=259` ⇒ '
    '**活锁 ⇒ 不抢不删**；**孤儿锁必须 `err==87` 才可回收**；等锁路径已改为 **0 次文件写入**'
    '（§80.4 缺陷④）；'
    '⑨ 🔴 **闸门可信度铁律**：解析异常必须判 FAIL；反证用 **AST 重建** ⇒ '
    '已固化在 `app105`/`app107`/`app108`/`app109`/`test_machine_lock_app`；'
    '⑩ 🔴 **本轮自查还抓出并修掉 `app113` 脚本自身的 2 处缺陷**'
    '（jsonl 路径写死会覆盖正式产物；帧率折算系数 12.5 而非 12.0）⇒ '
    '**闸门自身的假通过/假失败都算缺陷**；'
    '⑪ 🔴 **§66 用户新口径仍生效**：不再跑 `verify_pkg_zip.py`、不再跑 `publish_ftp.py`、不开 FTP；'
    '⑫ 🔴 **普通 push 会连带推上他模块已提交的 commit** ⇒ 本轮**逐文件 `git add`、不吞他模块文件**、'
    '**不用 `git add -A`**；'
    '⑬ 🔴 **APP-029 [NORMAL] 仍不认领集成**（reviewer 明文「现在不要集成」）；'
    '⑭ 🔴 **APP-022/APP-024②③④ 仍未做**（reviewer 明文「不要自己改」）⇒ 保持原状。'
)

NEW80_ENTRY = (
    '06:33 §80 🔴🔴 **APP-033 三条全部执行完毕（CUDA 组判据**已过** '
    '`verdict_after_clean=true` ＋ APP-028 5 分钟实测 10/10 PASS）＋ 自查抓出并修掉 4 处真实缺陷**：'
    '⇒ ✅ **①`quota.py` 在 reviewer 本机 ⇒ 不是 App 阻塞项**（wav+json+jsonl 已落盘）'
    '⇒ ✅ **② CUDA 组 A/B 已跑完并通过**'
    '（边车 `torch 2.11.0+cu128`/`cuda_available True`/RTX 5050；持锁+安静窗口；零 CPU 推理；未调 MiniMax）'
    '⇒ 改前臂（`d80ef22`）**cap=2/hang=2**'
    '（第 9 句 `lang=en` ⇒ **2038 帧 / 163.04 s / 255 块 / hang=true** ⇒ 与 reviewer 记录**逐项吻合**）'
    '⇒ 改后臂（HEAD）**cap/runaway/hang/err 全 0**、87 配对**异常 0 条** ⇒ '
    '**`verdict_after_clean=true`**；回归 zh/en 同样 0/0/0；s/字 0.1094→**0.1031**（无回退）'
    '⇒ ✅ **③ APP-028 的 SPE 前 5 分钟完整实测 10/10 PASS**'
    '（76 句 / `n_played=76` / `n_dropped=0` / `max_backlog_s=68.79` / `synth_rtf_p95=1.1511`）'
    '⇒ **「丢句=0」现在才成立**（§79.4 的 60 秒冒烟不构成）'
    '⇒ 🔴🔴 **修掉 4 处真实缺陷**（`machine_lock_app.py`：① ASR `PID=` 格式 ② 起始时间戳 '
    '③ EXT 第三种锁格式 ④🔴🔴🔴 **等锁每 20 s「建 tmp+删 tmp」⇒ 987 s = 50 删 ⇒ '
    '触发批量删除保护 ⇒ 进程被杀 ⇒ 报告未生成 ⇒ 实测白跑**（已修 + 实测复验零 tmp 残留））'
    '⇒ ✅ **验收 40/40 PASS**（含 **3 条 AST 重建反证**）'
    '⇒ ✅ **撤回 §78/§79「CUDA 对照组客观做不了」**'
    '⇒ ⛔ **APP-027 V1–V3 未跑**（V2/ABBA 安静窗口超时 ⇒ 目录实测为空 ⇒ 无产物）、'
    '⛔ **GUI 复现/CER 对比/用户实听未做**、⛔ **zip 未重打** ⇒ ⛔ **「用户听得到」仍不成立**'
)


def main():
    with open(P, encoding='utf-8') as f:
        lines = f.read().split('\n')

    assert lines[0].startswith('# STATUS_APP'), lines[0]
    assert lines[1].startswith('last_ack:'), lines[1]
    assert lines[2].startswith('更新时间:'), lines[2]
    assert lines[3].startswith('当前任务:'), lines[3]
    # 🔴 **阻塞项不在第 4 行**（第 4 行是空行，阻塞项在第 5 行）
    #    ⇒ 先按前缀找，不能写死索引。
    blk = None
    for k, ln in enumerate(lines[:12]):
        if ln.startswith('阻塞 / 待用户决定:'):
            blk = k
            break
    assert blk is not None, '未找到「阻塞 / 待用户决定:」行'

    lines[1] = 'last_ack: APP-033'
    lines[2] = '更新时间: 2026-10-28 06:33'
    lines[3] = NEW_TASK
    lines[blk] = NEW_BLOCK

    i = lines.index('## 最近更新')
    j = i + 1
    while lines[j].strip() == '':
        j += 1
    entry_end = j
    while entry_end < len(lines) and lines[entry_end].strip() != '':
        entry_end += 1
    entries = lines[j:entry_end]
    assert len(entries) == 15, len(entries)

    new_entries = [NEW80_ENTRY] + entries[:14]
    lines[j:entry_end] = new_entries

    out = '\n'.join(lines)
    with open(P, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    b = open(P, 'rb').read()
    print('OK last_ack=%s  最近更新行数=%d  bytes=%d CRLF=%d LF=%d'
          % (lines[1], len(new_entries), len(b), b.count(b'\r\n'), b.count(b'\n')))


if __name__ == '__main__':
    main()
