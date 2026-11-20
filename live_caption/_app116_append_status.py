#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116：往 `status/app/STATUS_APP.md` **追加** §216（不改旧正文）。

纪律（项目长期记忆 §一/§九）：
  · 只**追加** `## §N` 章节；旧章节**一字不改**；
  · 头部只动「更新时间」一行（`last_ack` 已在开工时写成 APP-116）；
  · 正文放 **companion**（`status/app/STATUS_APP_sec216_detail_20261120.md`）
    ⇒ 活文档只留摘要 + 指针行（§185 归档纪律：正文超限 ⇒ companion）；
  · 写盘走 **临时文件 → os.replace**；写前备份 + 写后**独立**复核；
  · 🔴 **绝不修改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
COMPANION = (r'C:\Users\Trekker-PTL\confucius4-openvino\status\app'
             r'\STATUS_APP_sec216_detail_20261120.md')
PIPE = (r'C:\Users\Trekker-PTL\confucius4-openvino\results\app'
        r'\app116_pipeline_evidence.json')
LIMIT = 40000
MARKER = '## §216 APP-116'

SECTION = """
## §216 APP-116：输出设备 / 预设 B 男声 / GUI 去 4 选项（2026-11-20 10:29）

> 正文见 companion：`status/app/STATUS_APP_sec216_detail_20261120.md`

- **§1** 根因 = GUI 反查表 `_out_label_back` 推导式**变量写反** ⇒ 反查恒 None
  ⇒ `--out-device` 从未传给 worker ⇒ 落回默认设备。已修（逐跳日志＋不静默回落
  ＋运行中切设备只重开播放流）；**A 机实测 21/21 PASS**。
- **§2** 预设 B（男声）由 `Qwen3-TTS-12Hz-0.6B-CustomVoice`（Apache-2.0）**模型生成**
  （24 kHz/单声道/10.0 s/无真人素材）；GUI 显示「预设 A（女声）」「预设 B（男声）」。
  \U0001f534 **用户点头前不进包**。
- **§3** GUI 去 4 个选项（默认值不变）；布局无空洞/无重叠；100 %/150 % 截图已落盘。
- **§5** v2.5 见 companion。未结：⓿抽听＋CER/WER ⓿A 机听感 ⓿是否打 zip（不通知不打）。
- 纪律：只改 App 文件；未改 `CORRECTIONS_APP.md`；未碰 SpecialMVP/MiniMVP；`31e5c67`。
"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def build_body():
    body = SECTION
    if os.path.isfile(PIPE):
        try:
            pe = json.load(open(PIPE, encoding='utf-8'))
            ph = pe.get('phases', {})
            ok = [k for k, v in ph.items() if v.get('rc') == 0]
            bad = [k for k, v in ph.items() if v.get('rc') not in (0, None)]
            pkg = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
            zipf = pkg + '.zip'
            n = tot = 0
            if os.path.isdir(pkg):
                for dp, _dn, fns in os.walk(pkg):
                    for f in fns:
                        n += 1
                        try:
                            tot += os.path.getsize(os.path.join(dp, f))
                        except OSError:
                            pass
            extra = ('\n- **§5 v2.5 出包与验收**（pipeline：`results/app/'
                     'app116_pipeline_evidence.json`）：\n'
                     '  · 成功阶段：%s\n  · 失败阶段：%s\n'
                     '  · 包目录 `Confucius4_LiveCaption_v2.5`：**%d 个文件 / %d B**\n'
                     '  · zip `Confucius4_LiveCaption_v2.5.zip`：%s\n'
                     % (('、'.join(ok) or '无'),
                        ('、'.join(bad) or '无'),
                        n, tot,
                        (('%d B' % os.path.getsize(zipf)) if os.path.isfile(zipf)
                         else '**未打**（用户不通知不打包）')))
            body = body.replace('- **§5 v2.5**：见 companion。',
                                '- **§5 v2.5**：见 companion。' + extra)
        except Exception as e:
            body += '\n- ⚠️ 读取流水线证据失败：%r\n' % (e,)
    return body


def main():
    orig = open(STATUS, 'rb').read()
    text = orig.decode('utf-8')
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    old_time_line = [l for l in text.split('\n')
                     if l.startswith('更新时间: ')][0]
    new_time_line = '更新时间: ' + ts

    body = build_body()

    # 🔴 **幂等**：§216 是**本轮自己新建**的章节 ⇒ 同轮内允许刷新
    #   （旧章节＝上一轮内容 ⇒ 一字不动）。
    if MARKER in text:
        i = text.index(MARKER)
        j = text.find('\n## ', i + 1)
        tail = text[j:] if j != -1 else ''
        base = text[:i].rstrip('\n') + '\n'
    else:
        tail = ''
        base = text.rstrip('\n') + '\n'
    new = base + body.rstrip('\n') + ('\n' + tail if tail else '\n')
    new = new.replace(old_time_line, new_time_line, 1)
    if new_time_line not in new:
        new = new.replace('last_ack: APP-116',
                          'last_ack: APP-116\n' + new_time_line, 1)

    checks = []
    # ① 旧正文（§216 之外）逐字未变：把新文本去掉 §216 整块与新时间行 ⇒ 应等于 base
    stripped = new.replace(body.rstrip('\n') + '\n', '', 1)
    stripped = stripped.replace(new_time_line, old_time_line, 1)
    checks.append(('§216 之外的旧正文逐字未变', stripped == base))
    checks.append(('§216 已写入', MARKER in new))
    checks.append(('§216 只出现一次', new.count(MARKER) == 1))
    checks.append(('CRLF 数不变', new.count('\r\n') == text.count('\r\n')))
    checks.append(('last_ack 唯一且为 APP-116',
                   new.count('last_ack: ') == 1
                   and 'last_ack: APP-116' in new))
    checks.append(('companion 存在', os.path.isfile(COMPANION)))
    checks.append(('字节数 < %d' % LIMIT,
                   len(new.encode('utf-8')) < LIMIT))
    checks.append(('行数 <= 300', new.count('\n') <= 300))
    bad = [n for n, ok in checks if not ok]
    print('（新文本 %d B / %d 行；旧 %d B）'
          % (len(new.encode('utf-8')), new.count('\n'), len(orig)))
    if bad:
        print('FAIL-CLOSED：写前复核未过：', bad)
        print('源文件零改动。')
        return 2

    bak = os.path.join(os.environ.get('TEMP', '.'),
                       'STATUS_APP.bak_app116_%s.md'
                       % time.strftime('%Y%m%d_%H%M%S'))
    shutil.copyfile(STATUS, bak)
    assert open(bak, 'rb').read() == orig

    tmp = STATUS + '.tmp_app116'
    with open(tmp, 'wb') as f:
        f.write(new.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    disk = open(STATUS, 'rb').read()
    ok = (disk == new.encode('utf-8') and sha(disk) != sha(orig))
    print('=== APP-116 §216 写入 ===')
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))
    print('备份      : %s（%d B）' % (bak, os.path.getsize(bak)))
    print('原 SHA256 : %s（%d B）' % (sha(orig), len(orig)))
    print('新 SHA256 : %s（%d B）' % (sha(disk), len(disk)))
    print('写后复核  : %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
