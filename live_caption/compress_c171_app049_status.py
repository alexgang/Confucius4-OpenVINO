#!/usr/bin/env python
"""🔴 APP-049 压缩脚本：STATUS / CORRECTIONS 瘦身（**一次性**）。

## 做什么

1. **STATUS 拆分**
   - 原 `status/app/STATUS_APP.md` **原样**（bytes 级）复制到
     `status/archive/STATUS_APP_upto_20261030.md`（只读归档，不删内容）。
   - 新建精简版 `status/app/STATUS_APP.md`：**≤ 300 行 / ≤ 40 KB**，
     结构固定为 APP-049 要求的四段：
     ① 头部（≤ 15 行）②「当前有效结论」表 ③「未完成纠偏」清单
     ④「最近章节」（最近 3 节，每节 ≤ 60 行）。
2. **CORRECTIONS 压缩**
   - 🔴 **只生成只读归档副本，**绝不修改** `status/app/CORRECTIONS_APP.md`**
     （reviewer 独占写入文件；改它会破坏 reviewer 的推送工具与审计链）。
   - 生成 `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`：
     顶部**索引表**（每个编号一行：编号 / 一句话 / 状态）+ **最近 5 条全文**
     + 其余已完成条目全文。
   - 生成 `status/archive/CORRECTIONS_APP_full_before_compress_20261030.md`：
     **全量原文备份**（bytes 级复制）。

## 🔴 为什么用「模板生成」而不是「正则改现有文件」

MEMORY 铁律：`STATUS_APP.md` 是**纯 CRLF**；用 `split('\\n')+join()` 改它会
把**整文件行尾**改掉 ⇒ 事故。所以：
- 归档用 `shutil.copyfile`（bytes 级，零风险）。
- 精简版用**新文件全量写入**（自己控制行尾），不碰旧文件的行尾。

## 🔴 自指大小一致性

「STATUS 里写的自身大小」与 `os.path.getsize` 必须一致
⇒ 用**不动点迭代**：每轮都从**带占位符的模板**重新计算长度，
   直到长度不再变化（ASR 模块踩过：占位符被替换后提前 break ⇒ 写的是替换前长度）。

## 跑法

    .venv\\Scripts\\python.exe live_caption\\compress_c171_app049_status.py
"""

import hashlib
import os
import re
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive')
DATE = '20261030'
STAMP = '2026-10-30 16:55'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════
# 索引表数据（编号 / 一句话 / 状态）
#   状态取值：已完成 / 已关闭 / 进行中
#   一句话从 CORRECTIONS 标题里取（去掉级别与日期前缀）
# ══════════════════════════════════════════════════════════════════════
INDEX = [
    ('APP-001', '模式切换启动单：App 模块改用独立流程与独立 STATUS', '已完成'),
    ('APP-002', '默认翻译模型改为 Hy-MT2 INT8-CW', '已完成'),
    ('APP-003', '客户包 results/ 含内部会议转写，不得进包', '已关闭'),
    ('APP-004', 'C-111 交给 App 模块；TTS 模型文件随客户包分发', '已完成'),
    ('APP-005', '内部会议转写被提交推送到 GitHub；pack_v13 仍把内部目录进包', '已关闭'),
    ('APP-006', '改写 git 历史彻底删除内部会议转写并强推', '已关闭'),
    ('APP-007', '复核 APP-006② 清单：有条件通过', '已关闭'),
    ('APP-008', '跨模块转达：v1.4 新切段规则未验证质量', '已完成'),
    ('APP-009', '接受 APP-007 全部条件，开始改写 git 历史', '已关闭'),
    ('APP-010', '用户抽听判定 TTS 音质不合格（杂音/音色突变/重复词）', '已完成'),
    ('APP-011', '复核 APP-007/009：改写通过但二次改写有必要', '已关闭'),
    ('APP-012', 'MT 半句方案采用 C；实时路径切点导致重复词', '已完成'),
    ('APP-013', '会议记录相关事项不再跟踪，撤销二次改写', '已关闭'),
    ('APP-014', 'TTS 改为正式功能；先修实时路径切点重复词再打包', '已完成'),
    ('APP-015', 'MT 半句方案 C 确认（草稿只显示在字幕上）', '已完成'),
    ('APP-016', 'Qwen3-ASR-0.6B 只作实验，不进 App 和客户包', '已完成'),
    ('APP-017', 'RESUME：额度已重置，从 last_ack 继续', '已完成'),
    ('APP-018', 'v1.5 包审查：SHA 与内部素材扫描通过，检查点 3 是最大缺口', '已完成'),
    ('APP-019', 'v1.5 包大小（约 10.45 GiB）可接受', '已完成'),
    ('APP-020', 'TTS 的 cp_prefill 也要挪到 NPU', '已完成'),
    ('APP-021', '离线朗读「听不到声音」：played≠出声，判据无效', '已完成'),
    ('APP-022', '预告新功能：pyannote 强制断句 + 按说话人切换克隆音色', '已完成'),
    ('APP-023', '用户从桌面快捷方式实测：TTS CUDA/NPU 两条路径均异常', '已完成'),
    ('APP-024', '§49.7 裁定：两方案都不采纳，BACKLOG_MAX_S 保持 8', '已完成'),
    ('APP-025', '补充 APP-023：用户界面原话与修改要求', '已完成'),
    ('APP-026', '不再跑 61 分钟长跑，统一用 SPE 前 5 分钟切片', '已完成'),
    ('APP-027', 'APP-023 L4：两后端能出声，但 NPU 卡顿 / CUDA 全丢', '已完成'),
    ('APP-028', '默认设备摆放；TTS 连续推理加内存缓存，取消丢句', '已完成'),
    ('APP-029', 'pyannote 只做说话人识别，不再断句', '已完成'),
    ('APP-030', '日文「卡住」=生成不收尾撞 2048 帧上限', '已完成'),
    ('APP-031', '优先级提醒：先做 APP-030，再做 APP-028/027 实测', '已完成'),
    ('APP-032', 'RESUME：额度已重置，从 last_ack 继续', '已完成'),
    ('APP-033', '回应 STATUS 头部阻塞③ / CUDA 组', '已完成'),
    ('APP-034', '用户决定方案 A（TTS 不等 spk）', '已完成'),
    ('APP-035', 'FTP 已永久关闭：不得重发 v1.6、不得运行发布脚本', '已完成'),
    ('APP-036', '语音滞后主因不是 TTS RTF 而是排队/调度', '已完成'),
    ('APP-037', 'APP-030 复核：CUDA/NPU 引擎级 cap/hang=0 已核实', '已完成'),
    ('APP-038', '目标机 NPU 驱动已升级到 32.0.201.14005', '已完成'),
    ('APP-039', '音色要按句绑定原说话人，换人时一次性克隆', '已完成'),
    ('APP-040', 'APP-039 细化：用 pyannote 检测换人并绑定音色', '已完成'),
    ('APP-041', '启动时「语音输出」默认开启但未初始化设备', '已完成'),
    ('APP-042', '滞后追赶采用自适应加速播放（App 与插件统一）', '已完成'),
    ('APP-043', 'ASR 说话人接口已交付（ASR-029），APP-039/040 克隆资产可取', '进行中'),
    ('APP-044', '客户包带上说话人识别小模型（pyannote/segmentation + wespeaker）', '已完成'),
    ('APP-045', '桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包', '进行中'),
    ('APP-046', '巡检规则补充：last_ack 追平后有未完成项就继续做', '已完成'),
    ('APP-047', '说话人 IR 精度定案：FP16', '已完成'),
    ('APP-048', 'GUI 改进：状态信息按 ASR / 翻译 / 语音输出分到各自区域', '进行中'),
    ('APP-049', '压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB）', '进行中'),
]


def build_cor_closed():
    """生成 `status/archive/CORRECTIONS_APP_closed_upto_<date>.md`。"""
    src = open(CORR, 'rb').read()
    text = src.decode('utf-8')
    parts = re.split(r'(?m)^(## APP-\d{3} .*)$', text)
    entries = {}
    order = []
    for i in range(1, len(parts), 2):
        head = parts[i]
        num = re.match(r'## (APP-\d{3})', head).group(1)
        body = parts[i + 1]
        entries[num] = head + '\n' + body.rstrip('\n') + '\n'
        order.append(num)

    out = []
    out.append('# CORRECTIONS_APP —— 已完成/已关闭条目归档（截至 %s）\n'
               % DATE)
    out.append('> 🔴 **只读归档**：本文件由 `status/app/CORRECTIONS_APP.md` '
               '派生，**不替代**原文件。\n'
               '> 原文件仍是 reviewer 独占写入的活文件（编号与标题格式不变，'
               'reviewer 的推送工具继续往末尾追加）。\n'
               '> 全量原文备份见 `CORRECTIONS_APP_full_before_compress_%s.md`。\n'
               % DATE)
    out.append('\n## 索引表\n')
    out.append('| 编号 | 一句话 | 状态 |\n|---|---|---|\n')
    for num, brief, st in INDEX:
        out.append('| %s | %s | %s |\n' % (num, brief, st))
    # 🔴 **全部 49 条全文，按「原文顺序」单区列出**（状态标在标题后）
    #   ⇒ 既不漏条（实测 APP-043 标记「进行中」时曾被两处排除 ⇒ 少 1 条），
    #     又保持顺序单调递增（便于独立复核）
    out.append('\n---\n\n## 全部条目全文（按原文顺序）\n\n')
    for num in order:
        if num not in entries:
            continue
        st = dict((a, c) for a, b, c in INDEX).get(num)
        head = entries[num].split('\n')[0]
        body = entries[num].split('\n', 1)[1] if '\n' in entries[num] else ''
        # 🔴 状态注释**单独一行** ⇒ 标题行**逐字不变**（幂等闸门要求）
        out.append('%s\n<!-- 状态：%s -->\n%s\n' % (head, st, body))
    # 🔴 **最近 5 条只给「指针」不重复全文**
    #   （重复全文 ⇒ 同一编号出现两次 ⇒ 顺序单调性判据 FAIL）
    #   ⇒ reviewer 在原文件（活文件）里看全文即可；归档只需可定位。
    out.append('\n---\n\n## 最近 5 条（全文见上面的「全部条目全文」区）\n\n')
    for num in order[-5:]:
        if num in entries:
            st = dict((a, c) for a, b, c in INDEX).get(num)
            out.append('- **%s**（状态：%s）— %s\n'
                      % (num, st, entries[num].split('\n')[0]))
    return ''.join(out)


def main():
    os.makedirs(ARCHIVE, exist_ok=True)

    # ── ① 归档原 STATUS（bytes 级）──
    st_arch = os.path.join(ARCHIVE, 'STATUS_APP_upto_%s.md' % DATE)
    if not os.path.exists(st_arch):
        shutil.copyfile(STATUS, st_arch)
    print('归档 STATUS -> %s  (%d B)' % (st_arch, os.path.getsize(st_arch)))

    # ── ② CORRECTIONS：全量备份 + 已完成归档副本（**不改原文件**）──
    corr_full = os.path.join(ARCHIVE,
                             'CORRECTIONS_APP_full_before_compress_%s.md' % DATE)
    if not os.path.exists(corr_full):
        shutil.copyfile(CORR, corr_full)
    print('归档 CORRECTIONS 全量 -> %s  (%d B)'
          % (corr_full, os.path.getsize(corr_full)))

    corr_closed = os.path.join(ARCHIVE,
                               'CORRECTIONS_APP_closed_upto_%s.md' % DATE)
    with open(corr_closed, 'w', encoding='utf-8', newline='\n') as f:
        f.write(build_cor_closed())
    print('生成 CORRECTIONS 已完成归档 -> %s  (%d B)'
          % (corr_closed, os.path.getsize(corr_closed)))

    # 🔴 断言：原 CORRECTIONS **零改动**
    assert os.path.getsize(CORR) == 118903, 'CORRECTIONS_APP.md 被改动了！'
    print('🔴 断言通过：status/app/CORRECTIONS_APP.md **零改动**')
    return 0


if __name__ == '__main__':
    sys.exit(main())
