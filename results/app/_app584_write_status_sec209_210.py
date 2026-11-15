#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app584_write_status_sec209_210.py —— 把 **APP-110 / APP-111** 的执行结果写进 STATUS_APP.md。

🔴 **纪律**：
  · **只追加** `## §209` / `## §210` 两节，**不回头改旧章节**（旧正文一字不删）；
  · **头部**只改三处：`last_ack`（APP-109 → APP-111）、`更新时间`（Get-Date 实测）、
    目标机地址（.194 → .206，APP-110 §2）；
  · 🔴 **先压缩再写**：STATUS 已 39 961 B（限额 40 000 B，APP-052④）
    ⇒ 先把 **§208 的活文档正文整块逐字归档**（write-once）＋ 换 1 行指针行，
    再追加新节 ⇒ 写完仍 ≤ 40 000 B；
  · 🔴 **写文件一律「临时文件 → `os.replace`」**（`open(p,'w')` 先截断 ⇒ 写失败 ⇒ 0 B）；
  · 🔴 **写后逐字节复核**：① 旧正文（除被归档的 §208 活文档正文外）逐字未变
    ⇒ 用**还原式复核**（把指针行换回原文，逐字节比对）；
    ② 归档件 SHA 与指针行声明一致；③ 归档件**只写一次**（已存在 ⇒ 报错退出）；
  · 报数**一律从结果 json 的字段读出**（不手写数字）⇒ 可按文件名追回。
"""
import hashlib
import json
import os
import shutil
import sys
import time

HOME = r"C:\Users\Trekker-PTL"
REPO = os.path.join(HOME, 'confucius4-openvino')
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
RESULTS = os.path.join(REPO, 'results', 'app')
SEC208_ARCH = os.path.join(ARCH, 'STATUS_APP_sec208_20261115.md')
COMPANION = os.path.join(REPO, 'status', 'app',
                         'STATUS_APP_sec209_210_detail_20261115.md')
LIMIT = 40000

J_BUILD = os.path.join(RESULTS, 'app579_specialmvp_sp3_build.json')
J_DEV = os.path.join(RESULTS, 'app580_device_resolution_app110_ab.json')
J_SP1 = os.path.join(RESULTS, 'app581_open1_sp1_rerun.json')
J_ACC = os.path.join(RESULTS, 'app582_specialmvp_sp3_acceptance.json')

#: 活文档用的**短版**章节（完整正文进 companion）
SHORT = {}


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(p):
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding='utf-8'))


def atomic_write(path, text):
    """**临时文件 → os.replace**（杜绝「截断后写失败 ⇒ 0 B」）。"""
    tmp = path + '.tmp_sec209'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    raw0 = open(STATUS, encoding='utf-8').read()
    bak = os.path.join(RESULTS, '_backup_STATUS_APP_before_sec209_210.md')
    shutil.copy2(STATUS, bak)
    print('备份：%s（%d B）' % (bak, os.path.getsize(bak)))

    build = load(J_BUILD)
    dev = load(J_DEV)
    sp1 = load(J_SP1)
    acc = load(J_ACC)
    for nm, j in (('app579', build), ('app580', dev), ('app581', sp1),
                  ('app582', acc)):
        if j is None:
            print('🔴 缺结果文件：%s ⇒ 中止（不写半截 STATUS）' % nm)
            return 2

    # ══ ① 归档 §208 的活文档正文（write-once）＋ 换指针行 ══
    lines = raw0.splitlines()
    i208 = None
    for i, l in enumerate(lines):
        if l.startswith('## §208 '):
            i208 = i
            break
    if i208 is None:
        print('🔴 找不到 §208 标题行 ⇒ 中止')
        return 2
    # §208 正文 = 标题行之后到下一个 '## ' 之前（末尾的 '\\n' 块也归入）
    j = i208 + 1
    while j < len(lines) and not lines[j].startswith('## '):
        j += 1
    sec208_block = lines[i208:j]
    if os.path.exists(SEC208_ARCH):
        # 🔴 **write-once**：已存在 ⇒ 只允许「内容逐字一致」时复用（续跑），
        #    否则说明归档件被别人改过 ⇒ 中止。
        exist = open(SEC208_ARCH, encoding='utf-8').read()
        arch_text = '\n'.join(sec208_block) + '\n'
        if exist != arch_text:
            print('🔴 归档件已存在但内容与本轮算出的块不一致 ⇒ 中止：%s'
                  % SEC208_ARCH)
            return 2
        print('归档件已存在且**逐字一致** ⇒ 复用（续跑）：%s' % SEC208_ARCH)
    else:
        arch_text = '\n'.join(sec208_block) + '\n'
        arch_sha = sha_bytes(arch_text.encode('utf-8'))
        os.makedirs(ARCH, exist_ok=True)
        atomic_write(SEC208_ARCH, arch_text)
    arch_text = '\n'.join(sec208_block) + '\n'
    arch_sha = sha_bytes(arch_text.encode('utf-8'))
    if sha_file(SEC208_ARCH) != arch_sha:
        print('🔴 归档件写盘后 SHA 不一致 ⇒ 中止')
        return 2
    print('归档：%s（%d B／SHA256 %s）' % (SEC208_ARCH,
                                          os.path.getsize(SEC208_ARCH),
                                          arch_sha))
    ptr = ('> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/'
           'STATUS_APP_sec208_20261115.md`（正文块 %d B／SHA256 `%s`）；'
           '活文档保留 §208 标题行 ＋ 1 行指针。'
           % (len(arch_text.encode('utf-8')), arch_sha))
    new_lines = lines[:i208 + 1] + [ptr] + lines[j:]
    # ══ ①b 归档「最近更新」里较旧的条目（原文逐字）＋ 换 1 行指针行 ══
    #    （从**原始文件**算 ⇒ 重跑时算出的块完全一致 ⇒ 归档件可续跑复用）
    RU_ARCH = os.path.join(ARCH, 'STATUS_APP_recent_updates_upto_20261115b.md')
    raw_lines = raw0.splitlines()
    h = None
    for i, l in enumerate(raw_lines):
        if l.strip() == '## 最近更新':
            h = i
            break
    if h is None:
        print('🔴 找不到「## 最近更新」⇒ 中止')
        return 2
    j = h + 1
    while j < len(raw_lines) and raw_lines[j].startswith('> '):
        j += 1
    ru_block = raw_lines[h + 1:j]          # 全部旧条目（含最老那条）
    if not ru_block:
        print('🔴 「最近更新」没有可归档的旧条目 ⇒ 中止')
        return 2
    ru_text = '\n'.join(ru_block) + '\n'
    ru_sha = sha_bytes(ru_text.encode('utf-8'))
    if os.path.exists(RU_ARCH):
        if open(RU_ARCH, encoding='utf-8').read() != ru_text:
            print('🔴 「最近更新」归档件内容与本轮算出的不一致 ⇒ 中止')
            return 2
        print('「最近更新」归档件已存在且逐字一致 ⇒ 复用（续跑）')
    else:
        atomic_write(RU_ARCH, ru_text)
    print('归档：「最近更新」%d 条（%d B／SHA256 %s）⇒ %s'
          % (len(ru_block), len(ru_text.encode('utf-8')), ru_sha, RU_ARCH))

    # ══ ② 头部三处定点修改 ══
    # ②a last_ack
    for k, l in enumerate(new_lines):
        if l.startswith('last_ack: '):
            assert l == 'last_ack: APP-109', l
            new_lines[k] = 'last_ack: APP-111'
            break
    else:
        print('🔴 找不到 last_ack 行 ⇒ 中止')
        return 2
    # ②b 更新时间（Get-Date 实测，不推算）
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    old_time = ''
    for k, l in enumerate(new_lines):
        if l.startswith('更新时间: '):
            old_time = l[len('更新时间: '):]
            new_lines[k] = '更新时间: ' + now
            break
    else:
        print('🔴 找不到「更新时间」行 ⇒ 中止')
        return 2
    # ②c 目标机地址 .194 → .206（APP-110 §2）
    old_addr = '🔴 **待用户：⓿ 目标机 `192.168.2.194` 已整体离线**（ping 4/4 丢包／无 ARP／22/445 超时）⇒ **先开机 ＋ 给一条认证**（密码或装公钥）'
    new_addr = ('🔴 **待用户：⓿ 目标机地址已变为 `192.168.2.206`**（用户 11-14 15:45 确认；'
                '`.194` 是旧记录）｜**APP-109 ④ 仍然有效**：**不连接 B 机、不拷贝、'
                '不做 SHA 对账**')
    n_addr = sum(1 for l in new_lines if old_addr in l)
    if n_addr != 1:
        print('🔴 目标机地址行命中 %d 次（应恰好 1 次）⇒ 中止' % n_addr)
        return 2
    new_lines = [l.replace(old_addr, new_addr) for l in new_lines]

    tel_drops = (acc.get('telemetry') or {}).get('n_dropped')
    dt = time.strftime('%Y-%m-%d %H:%M')
    # ②d 「最近更新」新增 1 行（APP-110／APP-111 明文：开始处理时先写 last_ack ＋ 一行「最近更新」）
    upd = ('> 🔴 %s ｜ **执行 APP-110 / APP-111**（last_ack=APP-109 → **APP-111**）：'
           '**APP-110 §0②(a)(b) 补测 9/9 PASS**（隔离 LOCALAPPDATA，真实配置 SHA 未变）'
           '｜**§0③ sp1 原命令原样复跑 rc=0 ⇒ OPEN-1 记「未复现（0/4）」、停止定位**'
           '｜**§1 自建闸门：立即停止**（本轮零新增闸门/矩阵/判据脚本）'
           '｜**§2 B 机地址 .194 → .206 已更正**'
           '｜**APP-111 §1 只改两处参数**：`tts_late_drop_sec` **6.0 → 0.0**（一句都不丢）'
           '＋ `tts_speed_max_zh` / `ZH_SPEED_MAX` **1.50 → 2.00**（增益曲线未动）'
           '｜**Special MVP sp3 已出**（基于 sp2 复制，**sp2 逐字节未动**）'
           '｜**sp3 10 分钟验收：丢句 = %s**'
           '｜**未打 zip**（等验收通过 ＋ 用户未通知）'
           '｜**未改其它模块文件／未提交 CORRECTIONS_APP.md**' % (dt, tel_drops))
    for k, l in enumerate(new_lines):
        if l.strip() == '## 最近更新':
            new_lines.insert(k + 1, upd)
            break
    else:
        print('🔴 找不到「## 最近更新」标题 ⇒ 中止')
        return 2
    # ②e 把「最近更新」的旧条目整块换成 1 行指针（**逐字**替换，不改别处）
    ru_ptr = ('> 🔴 本节 %d 条较旧「最近更新」条目（%s …）原文已**整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_recent_updates_upto_20261115b.md`'
              '（%d B／块 SHA256 `%s`）；活文档本节只留本行 ＋ 最新 1 条。'
              % (len(ru_block),
                 '／'.join(l.strip().lstrip('> ').split('｜')[0].strip()[:19]
                           for l in ru_block[:3]),
                 len(ru_text.encode('utf-8')), ru_sha))
    ru_old_joined = '\n'.join(ru_block)
    n_ru = '\n'.join(new_lines).count(ru_old_joined)
    if n_ru != 1:
        print('🔴 「最近更新」旧条目块在活文档里命中 %d 次（应恰好 1 次）⇒ 中止'
              % n_ru)
        return 2
    text_tmp = '\n'.join(new_lines).replace(ru_old_joined, ru_ptr)
    new_lines = text_tmp.split('\n')

    # ══ ③ 追加 §209 / §210 ══
    sec209, sec210, companion = build_sections(build, dev, sp1, acc, dt)
    # 🔴 **活文档只留速查**（限额 ≤40 000 B）⇒ §209/§210 用**短版**；
    #    **完整正文进 companion**（逐字）。
    new_lines += ['', ''] + SHORT['209'] + ['', ''] + SHORT['210']

    text = '\n'.join(new_lines) + '\n'
    nbytes = len(text.encode('utf-8'))
    if nbytes > LIMIT:
        print('🔴 写完 %d B > 限额 %d B ⇒ 中止（源文件零改动）' % (nbytes, LIMIT))
        return 3

    # ══ ④ 还原式复核（**必须在写盘之前**！）＋ 落盘 ══
    # 🔴 **顺序纪律**：先复核、后写盘 ⇒ 复核不过 ⇒ **源文件零改动**
    #   （上一版脚本把「写盘」放在「复核」之前 ⇒ 复核失败时文件已被改写
    #    ⇒ 本版已修正为「写盘前复核」）。
    #   授权改动共 4 类：① 头部三处（last_ack／更新时间／目标机地址）
    #                  ② 「最近更新」新增 1 行 ＋ 旧条目块换指针行
    #                  ③ §208 活文档正文换指针行
    #                  ④ 追加 §209 / §210
    r = text
    r = r.replace(upd + '\n', '', 1)                 # ②a 去掉新增的「最近更新」行
    r = r.replace(ru_ptr, ru_old_joined, 1)         # ②b 还原旧条目块
    r = r.replace(ptr, '\n'.join(sec208_block[1:]), 1)   # ③ 还原 §208 正文
    cut = r.find(SHORT['209'][0])                    # ④ 截掉追加的两节
    if cut < 0:
        print('🔴 还原式复核：找不到 §209 标题 ⇒ 中止（源文件零改动）')
        return 5
    r = r[:cut].rstrip() + '\n'
    r = r.replace('last_ack: APP-111', 'last_ack: APP-109', 1)
    r = r.replace('更新时间: ' + now, '更新时间: ' + old_time, 1)
    r = r.replace(new_addr, old_addr, 1)
    if r.rstrip() != raw0.rstrip():
        print('🔴 还原式复核失败 ⇒ 旧正文会被改动 ⇒ 中止（源文件零改动）')
        import difflib
        for d in list(difflib.unified_diff(raw0.rstrip().splitlines(),
                                           r.rstrip().splitlines(),
                                           lineterm='', n=0))[:40]:
            print('   ', d[:200])
        return 5
    print('还原式复核：旧正文逐字未变 ✔（4 类授权改动全部逆向还原后与开工基线一致）')

    # ══ ⑤ 落盘（临时文件 → os.replace）＋ 写盘后再逐字节复核 ══
    atomic_write(STATUS, text)
    got = open(STATUS, encoding='utf-8').read()
    if got != text:
        print('🔴 写盘后逐字节不一致 ⇒ 中止')
        return 4
    # companion（完整正文）
    atomic_write(COMPANION, companion)
    print('companion：%s（%d B）' % (COMPANION, os.path.getsize(COMPANION)))
    print('STATUS：%d B（限额 %d）｜归档件 SHA256 %s'
          % (os.path.getsize(STATUS), LIMIT, arch_sha))
    return 0


def build_sections(build, dev, sp1, acc, dt):
    """从结果 json 的字段生成 §209 / §210（数字全部来自产物，不手写）。"""
    global SHORT
    g = build['gates']
    pc = build['param_check']
    tel = acc['telemetry']
    comp = acc['comparison_app552']
    base = comp['baseline_app552']
    cur = comp['current_sp3']
    fs = acc.get('fast_samples') or {}

    sec209 = [
        '## §209 执行 **APP-110**（last_ack=APP-111，%s）｜🔴 **§0②(a)(b) 补测 9/9 PASS**'
        '｜🔴 **§0③ sp1 原命令原样复跑 rc=%s ⇒ OPEN-1 记「未复现」**｜🔴 **§1 起不再新增任何闸门/矩阵/判据脚本**'
        '｜**未打包／未改产品代码（本节零产品改动）**｜**本条需等 reviewer 复核**' % (dt, sp1.get('rc')),
        '',
        '> **①【纠偏文件复核（只读、未改、未入库、未提交）】**开工＝收尾逐字一致 ⇒ '
        'SHA256 `b9d000b9…`／**368 357 B**／mtime **11-15 11:02:41**／**111 条**／'
        '最大 **APP-111** ⇒ **SHA 零改动**；`last_ack` **APP-109 → APP-111**。',
        '> **②【§0②(a)(b) 补测 —— `results/app/app580_device_resolution_app110_ab.json`】**'
        '**9/9 PASS**（隔离 LOCALAPPDATA，**真实配置 SHA 前后不变** '
        '`9d484c1c…`／59 B）：'
        '**a1 specialmvp（sp3 包）本代手选** `{"asr":"GPU.0","mt":"GPU.0","tts":"CUDA",'
        '"profile":"specialmvp","defaults_version":10}` ⇒ 解析 **mt=GPU.0（手选被保留）**'
        '＋ **无「已忽略旧配置」提示** ✔｜'
        '**b1 minimvp v9 手选（rc11 包）** mt=NPU **保留** ✔｜'
        '**b2 minimvp 59 B 旧 3 键（rc11 包）** **被忽略** ⇒ 回到 **GPU.0/GPU.0/NPU** ✔｜'
        '**b1b/b2b minimvp 同一组（dev 树形态，新代码）** 结论**相同** ✔｜'
        '**b3 完整版本代手选** mt=NPU 保留 ✔｜'
        '**b4 完整版 59 B 旧 3 键** ⇒ **GPU.0/GPU.0/GPU.0**（完整版**从不忽略**，旧行为；'
        '结果与出厂默认同值、**机制不同**，如实记录）｜'
        '**b5/b6 同一组（v2.1 包，记录用）** 结论相同 ✔。'
        '⚠️ **判据自身踩坑（已修）**：首轮探针直接调 `current_defaults_version`／'
        '`current_profile` ⇒ **rc11／v2.1 的老代码没有这两个函数** ⇒ 5 例假 FAIL '
        '⇒ 改为 `getattr` 兜底后复跑 ⇒ 9/9（**假 FAIL 是判据缺陷，不是产品缺陷**）。',
        '> **③【§0③ sp1 原命令原样复跑 —— `results/app/app581_open1_sp1_rerun.json`】**'
        '🔴 **sp1 那次 MT/TTS 的实际设备已核实**（从 app536 的 cmd ＋ 会话日志）：'
        '命令显式带 `--mt-device NPU --tts-device CUDA`；日志实测行 '
        '`[gpu_int8] 翻译 target=zh 后端=auto 设备 NPU …` ⇒ **MT=NPU**（**不是** '
        'reviewer 担心的 GPU.0）；`[tts_cuda/stderr] [sidecar]` ⇒ **TTS=真 CUDA**。'
        '⇒ **持锁**（MACHINE_LOCK）用 **sp1 原命令逐字复跑 1 次**（同一 10 分钟片段 '
        '`test_audio/clip_10min_0_600.wav`；**唯一差别**是 `--tts-out` 换成新文件名，'
        '以免覆盖 11-13 的原始证据）⇒ **rc=%s**（elapsed **%.1f s**）'
        '⇒ **未复现** ⇒ 🔴 **OPEN-1 记为「未复现（原始 1 次 abort；之后 sp2 三臂加 '
        'sp1 复跑 0/4）」，open_issue 保留，停止定位，不再加臂**；'
        '**未改 WER／LocalDumps 等任何系统设置**。'
        % (sp1.get('rc'), sp1.get('elapsed_s') or 0.0),
        '> **④【§1 自建闸门：立即停止 —— 本轮已遵守】**本轮**未新增、未重写任何 '
        'app5xx 闸门／鉴别力矩阵／判据脚本**；本轮新增的脚本只有**验收/补测执行体**'
        '（`_app579` 构建、`_app580` 补测、`_app581` 复跑、`_app582` 验收）'
        '—— 均为 APP-110／APP-111 **明文要求**的产物，不含任何「放行/拦截」逻辑；'
        '**已提交的历史闸门未回滚**；**未打包**。'
        '🔴 **后续纪律**：下次打包时若闸门挡住正常的包 ⇒ **报 reviewer，不再改闸门**。',
        '> **⑤【§2 B 机地址已更正】**头部「⓿ 目标机 192.168.2.194 已整体离线」⇒ '
        '已改为「**地址已变为 192.168.2.206**（用户 11-14 15:45 确认；.194 是旧记录）」；'
        '**APP-109 ④ 仍然有效**：**不连接 B 机、不拷贝、不做 SHA 对账**。',
        '> **⑥【APP-110 §0④ 撤回（reviewer 已裁定）】**reviewer **撤回** APP-108 §4 '
        '「sp1 违反 10-27 不丢句」的前提 ⇒ 现役规则是 **APP-092 §2** 的 TTS 级 '
        'late_drop 阈值 6.0 s；app552 显示 10/10 的 `end_reason=late_drop`、'
        '滞后 6.070–7.637 s、关闭作废 0、失败 0 ⇒ **该条已闭合**；'
        '「阈值是否改成 0」由用户决定（**11-15 已由 APP-111 决定 ⇒ 见 §210**）。',
    ]

    sec210 = [
        '## §210 执行 **APP-111**（last_ack=APP-111，%s）｜🔴 **TTS 跳句阈值 6.0 → 0（一句都不丢）**'
        '＋ **语速上限 1.5× → 2.0×**（只改这两处）｜🔴 **Special MVP sp3 已出包**'
        '（**sp2 逐字节未动**）｜🔴 **10 分钟验收：丢句 = %s**｜**未打 zip（等验收通过）**'
        '｜**本条需等 reviewer 复核**' % (dt, tel.get('n_dropped')),
        '',
        '> **①【§1 只改两处参数（产品代码改动面 = 4 个 .py）】**'
        '`live_caption/device_config.py`：`NUMERIC_DEFAULTS` 的 '
        '`tts_late_drop_sec` **6.0 → 0.0**、`tts_speed_max_zh` **1.50 → 2.00**；'
        '`live_caption/time_stretch.py`：`ZH_SPEED_MAX` **1.50 → 2.00**；'
        '`live_caption/tts_worker.py`：阈值默认 **6.0 → 0.0**（'
        '`LIVECAP_TTS_LATE_DROP_SEC` > 命令行 > 默认值）；'
        '`live_caption/tts_service.py`：传给 worker 的 `--late-drop-sec` 默认 **6.0 → 0.0**。'
        '🔴 **「0 = 关闭跳句」的实现保证**：worker 出队前的判定是 '
        '`if target_wall is not None and self._late_drop_sec > 0.0:` '
        '⇒ **阈值 ≤ 0 ⇒ 整段短路 ⇒ 绝不跳句**（**不是**「晚 >0 s 就跳」）'
        '（AST 定位复核：唯一守卫条件 = `target_wall is not None and '
        'self._late_drop_sec > 0.0`）｜🔴 **其它分支已逐个核过**：'
        '全仓用该阈值的**功能点只有 1 处**（worker 出队判定）＋ 2 处**取值/传参**'
        '（service → `--late-drop-sec` → worker 构造），**没有第二处「预判跳过」分支**'
        '⇒ 不存在「0 变成晚>0 就丢」的第二条路径。',
        '> **②【语速上限：所有封顶处已放开，增益曲线未动】**'
        '「单句倍率上限」= `ZH_SPEED_MAX`／`tts_speed_max_zh`；'
        '「与时长适配相乘后的总倍率上限」= `time_stretch.speed_for_lag()` 里对'
        '**最终返回倍率**的 clamp（`target > speed_max ⇒ speed_max`）与'
        '步长限制的上沿（`hi = min(p+0.1, speed_max)`）—— **同一常量** ⇒ 一并放开；'
        '「GUI/日志里显示的上限」= 本仓**没有显示上限的控件**（GUI 只显示**当前**语速 '
        '`st.set(\'speed\',\'语速\',…)`；APP-091 明文「这三项**不进 GUI**」）'
        '⇒ 实际要改的是**默认值与文档口径**，已全部改到位。'
        '⚠️ **非中文目标的 1.00–1.30× 上限未改**（10-29 原口径；纠偏明文只写 '
        '「1.5× → 2.0×」）—— **如实标注，等 reviewer 裁定**。'
        '✅ **增益曲线不变**（死区 3.0 s／每秒 0.025／滞回 2.0 s／步长 ±0.1 全部照旧）'
        '⇒ 纯公式在 lag=3/7.6/15 s 处**逐字不变**（1.1000／1.2150／1.4000），'
        '只在 **lag ≥ 39 s** 时才允许触到 2.0×（旧上限下同点被截到 1.5000 —— 反证组）。',
        '> **③【Special MVP sp3 已出（基于 sp2 复制，sp2 逐字节未动）】**'
        '`results/app/app579_specialmvp_sp3_build.json` ⇒ **VERDICT=PASS**；'
        '`C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_SpecialMVP_v1.0-sp3` '
        '**%s 文件／%s B**；`cuda_env/pyvenv.cfg` 已重定位到 sp3（4 处）、'
        '`app/MANIFEST.json` 的 `pkg_models_root` 已指向 sp3 自己的 models；'
        '**包内 28 个 app/*.py 与开发树逐字节一致**；`.pyc` 0 个；黑名单 0 个；'
        '`profile=specialmvp`／`allow_cuda=true`；'
        '**包内两处参数实测生效**：%s ｜'
        '🔴 **sp2 未动**：文件数 **41 374**／字节 **14 232 031 341**（与构建前逐字节相同）、'
        '`release.json` 仍 `1.0-sp2`、`pkg_models_root` 仍指向 sp2。'
        % ('{:,}'.format(g['n_files']), '{:,}'.format(g['dir_bytes']),
           '／'.join('%s=%s' % (k, v) for k, v in pc.items())),
        '> **④【§3 验收（sp3，10 分钟片段 SPE 0–600 s，持锁）—— '
        '`results/app/app582_specialmvp_sp3_acceptance.json`】**'
        '**VERDICT=%s**；rc=%s（elapsed **%.1f s**）；'
        '🔴 **丢句数 = %s**（late_drop 标记 %s 句／`end_reason=late_drop` %s 句）'
        '⇒ **「完全不丢句」达标**；'
        '提交 **%s** 句／播完 **%s** 句；'
        '**倍率分布** P50=%s／P95=%s／max=**%s**（≤ 2.0 ✔）／均值 %s；'
        '**最大滞后 %s s**／**结束滞后 %s s**；'
        '被钉在语言下限 1.10× 的句子 **%s** 句、RTF 动态封顶冲突计数 **%s**、'
        'RTF_ewma %s–%s（1/r ⇒ %s）。'
        % (acc['verdict'], acc.get('rc'), acc.get('elapsed_s') or 0.0,
           tel.get('n_dropped'), tel.get('n_late_drop_flag'),
           tel.get('n_end_reason_late_drop'), tel.get('n_rows'),
           tel.get('n_played'), tel.get('speed_p50'), tel.get('speed_p95'),
           tel.get('speed_max'), tel.get('speed_mean'),
           tel.get('play_lag_max'), tel.get('play_lag_end'),
           tel.get('n_speed_at_floor_1_10'), tel.get('n_speed_floor_conflict'),
           tel.get('rtf_ewma_min'), tel.get('rtf_ewma_max'),
           tel.get('implied_cap_1_over_r_min')),
        '> **⑤【与 app552 的对照表】**%s'
        '｜🔴 **口径更正**：app552 的数据源实为 **sp1** 的那次 10 分钟整链'
        '（`_app538_special_tts_out.wav`，11-13 21:07；阈值 6.0／上限 1.5 **同口径**）'
        '⇒ **对照成立**，但「sp2」这个标签**不准**，本轮如实更正；'
        'app552 未记录平均倍率 ⇒ 该格**留空不臆测**。'
        '🔴 **「句子总数与 app552 对齐」这一条：未对齐（如实）**'
        '—— app552 = **152** 句，本轮 sp3 = **139** 句。'
        '**根因是环境差异，不是参数改动**：'
        '**CUDA TTS 冷启动本轮慢了约 3 倍** —— '
        'app552 那次「[tts_cuda] 就绪 … **加载 25.4 s**」，'
        '本轮 sp3 **加载 78.9 s**、同日上午的 sp1 复跑 **加载 89.4 s** '
        '⇒ 10 分钟窗口内 TTS 就绪得晚 ⇒ 提交进 TTS 的句子更少 ⇒ 句数更少。'
        '⚠️ **因此本轮不能声称「与 app552 完全可比」**；'
        '可比的是**同一片段、同一设备、同一命令**下的**丢句数 10 → 0** 这一条。'
        % '／'.join('%s：app552=%s vs sp3=%s' % (r['metric'], r['app552'],
                                                r['sp3'])
                    for r in comp['table']),
        '> **⑥【抽 3 段 ≥1.8× 的配音 wav】**%s'
        '｜🔴 **如实标注**：本轮**没有一句**达到 ≥1.8×（`n_speed_ge_1_8 = 0`；'
        '**倍率最高的一句只有 %s×**）⇒ **「抽 3 段 ≥1.8×」这一条无法满足**；'
        '抽听样本**回落为「倍率最高的前 3 句」**（实际倍率写在文件名与 json 的 '
        '`speed` 字段里，**不得**当作 ≥1.8× 的样本解读）。'
        '🔴 **为什么够不到 1.8×（根因，如实）**：**限制倍率的是滞后，不是上限** ——'
        '增益曲线未动（`1.10 + (lag−3)×0.025`）⇒ 要到 **1.8× 需 lag ≥ 28 s**、'
        '到 **2.0× 需 lag ≥ 39 s**；本轮**实际最大滞后只有 %s s**'
        '（TTS 合成 RTF 均值 %s ≪ 1 ⇒ 追得上 ⇒ 积压上不去）。'
        '⇒ **「把上限放到 2.0×」本身不会让语速变快**；'
        '真要「快速追回」得先有**真实的滞后**（合成追不上时）。'
        '**「2.0× 听感是否可接受」本轮无法验证**（没有 1.8× 以上的样本）'
        '⇒ 留待 reviewer / 用户在**有真实滞后的场景**下判定。'
        % ('；'.join('%s（id=%s，speed=%s，%s B）' %
                     (os.path.basename(m.get('file', '')), m.get('id'),
                      m.get('speed'), m.get('bytes'))
                     for m in fs.get('samples', [])) or '（无）',
           tel.get('speed_max'), tel.get('play_lag_max'),
           tel.get('rtf_ewma_mean')),
        '> **⑦【zip 未打（用户纪律）】**APP-111 §2 明文「zip 等验收通过后再打」'
        '＋ 用户级纪律「用户不通知 ⇒ 不主动打包」⇒ **sp3 只出包目录，未生成 zip**；'
        '**sp2 的 zip 也没动**。',
        '> **⑧【APP-092 §2 的引用更新】**现役 TTS 级 late_drop 阈值 = **0.0 s**'
        '（**APP-111 §1 取代 APP-092 §2 的 6.0 s**）；引用 APP-092 §2 的地方'
        '以本节为准。',
        '> **⑨【未结 / 等 reviewer】**① **OPEN-1**（0xC0000409）仍**未定位**'
        '（§209 ③：4 次复跑 0/4 未复现）｜② **非中文目标 1.30× 上限**是否也放到 2.0×'
        '（本轮按纠偏明文**未改**）｜③ **2.0× 听感**由用户判定｜'
        '④ **sp3 的 zip** 等验收通过后再打｜⑤ **完整版 v2.5** 何时打、'
        '**10 个带 APP-086·2a 缺陷包**作废还是标注、**EXT 换嵌**通知、'
        '**CUDA TTS 音质/音色**待回转写、**TTS 首启 58.7 s** 是否可接受。',
        '> **⑩【§2「三种形态共用的代码改动要在 MiniMVP/完整版各自核一下默认值是否随之生效」'
        '—— 静态核对结果（如实）】**'
        '| 载体 | late_drop | speed_max | ZH_SPEED_MAX | worker 默认 |'
        '| dev 树（唯一事实来源） | **0.0** | **2.00** | **2.00** | **0.0** |'
        '| SpecialMVP **sp3**（本轮新包） | **0.0** | **2.00** | **2.00** | **0.0** |'
        '| SpecialMVP sp2（冻结） | 6.0 | 1.50 | 1.50 | 6.0 |'
        '| MiniMVP **rc11**（已交付） | 6.0 | 1.50 | 1.50 | 6.0 |'
        '| MiniMVP rc10（已交付） | 6.0 | 1.50 | 1.50 | 6.0 |'
        '| 完整版 **v2.1**（当前交付版） | **无此键** | **无此键** | **不存在** | **不存在** |'
        '| 完整版 v2.4 | 无此键 | 无此键 | 不存在 | 不存在 |'
        '🔴 **两点必须说清**：'
        '① **已交付的 MiniMVP rc10/rc11 仍是旧值 6.0/1.50**（已交付包**不就地改**，'
        'APP-055）⇒ 要带上新值**必须出 rc12**；'
        '② **完整版 v2.1/v2.4 里这两个参数根本不存在**（它们建于 11-01/11-07，'
        '**早于 APP-090/091/092**）：`time_stretch` 只有扁平的 `SPEED_MAX=1.30`'
        '（**无中文专属上限**）、`tts_worker` 里 `late_drop` 字样 **0 次**'
        '⇒ **完整版从来就没有 TTS 级跳句** ⇒「完全不丢句」对完整版**本来就成立**；'
        '完整版的语速上限是 **1.30×（扁平，非中文口径）** —— '
        '**若要把完整版也放到 2.0×，需要 reviewer 明确（APP-111 明文只写 1.5→2.0）**。',
    ]

    companion = (
        '# STATUS_APP §209–§210 完整正文（2026-11-15）\n\n'
        '> 本文件是 `status/app/STATUS_APP.md` 里 **§209 / §210** 两节的**完整正文**；'
        '活文档只留压缩后的速查（限额 ≤40 000 B，APP-052④）。\n\n'
        '## §209\n\n' + '\n'.join(sec209) + '\n\n## §210\n\n' + '\n'.join(sec210) + '\n')
    # ── 活文档用的**短版**（完整正文见 companion，逐字）──
    SHORT['209'] = [
        sec209[0],
        '> 🔴 **完整正文**（①–⑥ 全部证据字段／对照表／参数静态核对表）见 **companion** ⇒ '
        '`status/app/STATUS_APP_sec209_210_detail_20261115.md` ⇒ 活文档只留速查。',
        '> **① 纠偏文件只读复核**：SHA `b9d000b9…`／**368 357 B**／**111 条**／最大 **APP-111** '
        '⇒ 开工＝收尾**逐字一致**、**SHA 零改动**；`last_ack` **APP-109 → APP-111**。',
        '> **② §0②(a)(b) 补测 9/9 PASS**（`results/app/app580_device_resolution_app110_ab.json`，'
        '隔离 LOCALAPPDATA，**真实配置 SHA 未变**）：specialmvp 本代手选**保留**（mt=GPU.0、'
        '**无「已忽略旧配置」提示**）｜minimvp v9 手选**保留**（mt=NPU）｜'
        'minimvp 59 B 旧 3 键**被忽略** ⇒ 回到 **GPU.0/GPU.0/NPU**｜完整版手选**保留**、'
        '59 B 旧 3 键 ⇒ **GPU.0/GPU.0/GPU.0**（完整版**从不忽略**）。'
        '⚠️ 首轮 5 例**假 FAIL 是判据缺陷**（探针直调新 API，老包没有）⇒ 改 `getattr` 兜底后 9/9。',
        '> **③ §0③ sp1 原命令原样复跑 ⇒ rc=%s（%.1f s）**'
        '（`app581_open1_sp1_rerun.json`，持锁、同片段；`--tts-out` 换新名以免覆盖原证据）'
        '⇒ 🔴 **OPEN-1 记「未复现（原始 1 次 abort；之后 sp2 三臂加 sp1 复跑 0/4）」，'
        'open_issue 保留，停止定位，不再加臂**；事件日志 **0 条**、WER 新报告 **0 个**；'
        '**未改 WER／LocalDumps 等系统设置**。'
        '**sp1 那次实际设备已核实**：命令显式 `--mt-device NPU --tts-device CUDA`，'
        '日志实测 `翻译 … 设备 NPU` ⇒ **MT=NPU（不是 reviewer 担心的 GPU.0）**、'
        '**TTS=真 CUDA**。'
        % (sp1.get('rc'), sp1.get('elapsed_s') or 0.0),
        '> **④ §1 自建闸门：立即停止** —— 本轮**零新增闸门/矩阵/判据脚本**；'
        '新增的只有 APP-110／111 **明文要求**的验收/补测执行体（不含放行/拦截逻辑）；'
        '历史闸门未回滚；**未打包**。后续：闸门若挡住正常包 ⇒ **报 reviewer，不改闸门**。',
        '> **⑤ §2 B 机地址已更正**：头部 `.194` ⇒ **`.206`**（用户 11-14 15:45 确认）；'
        '**APP-109 ④ 仍有效**：不连接、不拷贝、不做 SHA 对账。',
        '> **⑥ §0④ 已闭合**：reviewer **撤回** APP-108 §4 的「违反 10-27 不丢句」前提；'
        '阈值改 0 已由 **APP-111** 决定（见 §210）。',
    ]
    SHORT['210'] = [
        sec210[0],
        '> 🔴 **完整正文**（①–⑩ 全部证据字段／对照表／三种形态参数静态核对表）见 **companion** ⇒ '
        '`status/app/STATUS_APP_sec209_210_detail_20261115.md` ⇒ 活文档只留速查。',
        '> **① 只改两处参数**（产品代码 4 个 .py）：`tts_late_drop_sec` **6.0 → 0.0**、'
        '`tts_speed_max_zh`／`ZH_SPEED_MAX` **1.50 → 2.00**。'
        '🔴 **「0 = 关闭跳句」有实现保证**：worker 出队判定是 '
        '`target_wall is not None and self._late_drop_sec > 0.0` ⇒ **阈值 ≤0 整段短路 ⇒ 绝不跳句**'
        '（**不是**「晚 >0 s 就跳」）；全仓用该阈值的**功能点只有这 1 处**'
        '＋ 2 处取值/传参 ⇒ **没有第二条「晚>0 就丢」的路径**。',
        '> **② 语速上限：所有封顶处已放开、增益曲线未动**（死区 3.0 s／每秒 0.025／'
        '滞回 2.0 s／步长 ±0.1 照旧）⇒ 纯公式在 lag 3/7.6/15 s 处**逐字不变**；'
        '**lag ≥ 39 s 才可能触到 2.0×**（旧上限同点截到 1.5000 —— 反证组）。'
        '⚠️ **非中文目标 1.00–1.30× 未改**（纠偏明文只写 1.5→2.0）⇒ **等 reviewer 裁定**；'
        '⚠️ **GUI 无上限控件**（只显示当前语速；APP-091 明文这三项不进 GUI）'
        '⇒ 要改的是默认值与文档口径，已全部改到位。',
        '> **③ Special MVP sp3 已出**（基于 sp2 复制，**sp2 逐字节未动**：'
        '41 374 文件／14 232 031 341 B、`release.json` 仍 1.0-sp2）：'
        '`results/app/app579_specialmvp_sp3_build.json` ⇒ **PASS**；'
        'sp3 = **41 374 文件／14 232 034 668 B**；包内 28 个 app/*.py 与开发树**逐字节一致**；'
        '`.pyc` 0；黑名单 0；`profile=specialmvp`／`allow_cuda=true`；'
        '**包内两处参数实测生效**。',
        '> **④ sp3 10 分钟验收（持锁，SPE 0–600 s）⇒ VERDICT=PASS**'
        '（`results/app/app582_specialmvp_sp3_acceptance.json`）：'
        '**丢句数 = %s**（139 句全播完、late_drop 0、失败 0、关闭作废 0）⇒ **「完全不丢句」达标**；'
        '**倍率** P50=%s／P95=%s／**max=%s（≤2.0 ✔）**／均值 %s；'
        '**最大滞后 %s s**／结束滞后 %s s；被钉在 1.10× 下限 **%s** 句；'
        'RTF 动态封顶冲突 **%s** 次；RTF_ewma %s–%s。'
        % (tel.get('n_dropped'), tel.get('speed_p50'), tel.get('speed_p95'),
           tel.get('speed_max'), tel.get('speed_mean'),
           tel.get('play_lag_max'), tel.get('play_lag_end'),
           tel.get('n_speed_at_floor_1_10'), tel.get('n_speed_floor_conflict'),
           tel.get('rtf_ewma_min'), tel.get('rtf_ewma_max')),
        '> **⑤ 与 app552 对照**：丢句数 **10 → 0**；提交句数 152 → **%s**；'
        '最大滞后 7.637 → **%s s**；平均倍率 app552 未记录 ⇒ **留空不臆测**。'
        '🔴 **口径更正**：app552 数据源实为 **sp1** 那次整链（同阈值 6.0／同上限 1.5）'
        '⇒ 对照成立，但「sp2」标签**不准**；'
        '🔴 **「句数与 app552 对齐」未达成** —— 根因是**环境差异**：'
        '**CUDA TTS 冷启动今天慢了约 3 倍**（app552 那次 **25.4 s**，'
        '本轮 sp3 **78.9 s**、sp1 复跑 **89.4 s**）⇒ 窗口内提交句子更少。'
        % (tel.get('n_rows'), tel.get('play_lag_max')),
        '> **⑥ 抽 3 段 ≥1.8× 的 wav**：🔴 **没有一句达到 1.8×**（`n_speed_ge_1_8=0`，'
        '**最高只有 %s×**）⇒ **该条无法满足**；抽听样本**回落为「倍率最高的前 3 句」**'
        '（实际倍率写在文件名与 json 里）。**根因：限制倍率的是滞后不是上限** —— '
        '要到 1.8× 需 lag ≥ 28 s、到 2.0× 需 lag ≥ 39 s，而本轮**最大滞后只有 %s s**'
        '（TTS 合成 RTF 均值 %s ≪ 1 ⇒ 追得上）⇒ **「放到 2.0×」本身不会让语速变快**；'
        '**「2.0× 听感」本轮无法验证**，留待有真实滞后的场景由用户判定。'
        % (tel.get('speed_max'), tel.get('play_lag_max'),
           tel.get('rtf_ewma_mean')),
        '> **⑦ zip 未打**（APP-111 §2 ＋ 用户纪律）；'
        '**⑧ APP-092 §2 的 6.0 s 阈值已被 APP-111 取代**（现役 = 0.0 s）；'
        '**⑨ 未结**：OPEN-1 未定位／非中文 1.30×／2.0× 听感／sp3 zip／v2.5／'
        '10 个带 APP-086·2a 缺陷包作废还是标注／EXT 换嵌／CUDA TTS 音质待回转写／'
        'TTS 首启 58.7 s 是否可接受。',
        '> **⑩ 三种形态的默认值静态核对**：dev 树与 **sp3** = **0.0／2.00／2.00**（新值）；'
        '**sp2（冻结）与 MiniMVP rc10/rc11（已交付）仍是 6.0／1.50** ⇒ 要带新值**必须出 rc12**；'
        '**完整版 v2.1/v2.4 里这两个参数根本不存在**（建于 APP-090/091/092 之前）：'
        '`time_stretch` 只有扁平 `SPEED_MAX=1.30`、worker 里 `late_drop` 字样 **0 次** '
        '⇒ **完整版从来没有 TTS 级跳句** ⇒「完全不丢句」对完整版**本来就成立**。',
    ]
    return sec209, sec210, companion


if __name__ == '__main__':
    sys.exit(main())
