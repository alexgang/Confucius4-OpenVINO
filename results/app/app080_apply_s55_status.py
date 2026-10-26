import io
import os
import time

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
SEC = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app080_s55_section.md'

with io.open(STATUS, 'rb') as f:
    raw = f.read()
crlf = b'\r\n' in raw
text = raw.decode('utf-8')
if crlf:
    text = text.replace('\r\n', '\n')

section = io.open(SEC, encoding='utf-8').read()

# 🔴 幂等：已存在 §55 则不重复追加
if '## §55 ' in text:
    print('SKIP: §55 已存在')
    raise SystemExit(0)

if not text.endswith('\n'):
    text += '\n'

text = text + section

# ---- 头部：只改 4 个字段行 ----
lines = text.split('\n')
now = '2026-10-26 20:55'
new_task = ('**§55 🔴 响应 APP-022 —— 预留 `spk` / `spk_conf` 接口（**本条已完成**，'
            '未集成）+ TTS-017① `cp_prefill` → NPU 同步** ⇒ ① **APP-022 已完成**：'
            '事件**按需加长**（`spk=None` ⇒ 仍是 5 元组 ⇒ MT 的 `len(e)==5` 断言继续成立）'
            '；`spk` 有值 ⇒ 7 元组；② GUI 新增「跟随说话人（克隆）」**（默认仍是预设 A**）'
            '与「显示说话人」**（默认关闭）**；③ 说话人表**只在内存**、会话结束清空、'
            '**不进客户包**；④ 🔴🔴 **TTS-017① `cp_prefill` 已同步到 NPU**'
            '（形状 `[1,2,1024]`；编译失败**回退 CPU + 记日志 + 返回 False**，不静默降级）；'
            '⑤ ✅ `app079` **REAL 15/15 · BUG 0/2**；⑥ ✅ 客户包 **6/6 synced**'
            '（骨架等价校验后升级基底，逐字一致 + `py_compile` OK）；'
            '⑦ ✅ **已交付 zip 干净**（13 984 entries / 第三方素材 0 / 仅 1 个 wav）；'
            '⚠️ **散包目录仍有 8 + 22 个第三方素材残留**（未清理 ⇒ 不写「已交付」）')

new_block = ('阻塞 / 待用户决定: ① 🔴 **APP-022 集成阶段需等 ASR-013 + TTS-019 交付**'
              '（本条只做接口预留，**未集成**）；② 🔴 **APP-021 验收 C 仍需用户配合**（需人）：'
              '交互会话里系统音量 ≥ 50%、戴耳机/外放 ⇒ **先点「🔊 测试声音」再点离线朗读念一句** ⇒ '
              '把会话日志路径与遥测行写进本 STATUS；③ 🔴 **撤回后的口径**：在用户用耳朵确认之前，'
              '**不得**再宣称「离线朗读能出声」；④ 🔴 **v1.5 zip 未重打**（守 APP-020，'
              '等 cp_prefill 同步后的最终版 + 机器锁）；⑤ 🔴 **散包目录仍有第三方素材残留**'
              '（babelvox speakers 8 + scipy 测试音频 22）⇒ **未清理**，需重打时由 `pkg_exclude` 规则覆盖；'
              '⑥ 🔴 **术语表 / `packaging` 默认值待用户决定**（MT 通知 14 建议：术语表只在芯片/半导体语境下开、'
              '`packaging` 放可选集 ⇒ 属 App 默认值 ⇒ 本轮**未擅自改**）；'
              '⑦ 🔴 **§50.5 需 TTS 模块配合**（App 不代跑尺子）；⑧ 🔴 **§49.7 待裁定**'
              '（APP-020 明确「先不要定」⇒ 未动）；⑨ 🔴 **§45.6①–⑤ 等 reviewer 裁定**；'
              '⑩ 🔴 **等裁定**：是否采纳 `MAX_SEG_SPAN = 2`（§44 候选已备好）；'
              '⑪ 🔴 **需回复 MT 通知 13**；⑫ 🔴 **§46.5** 第三方依赖可满足性闸门；'
              '⑬ 🔴 **§42.3** 修复待用户实机确认；⑭ ⛔ **FTP 服务仍关闭**（守 APP-009③）；'
              '⑮ ⛔ OV 的 CUDA plugin 不引入（§39.5）；⑯ ⛔ 包体优化未做（用户已接受）；'
              '⑰ ⛔ V7 残句代价待确认')

out = []
i = 0
head_done = False
recent_done = False
while i < len(lines):
    ln = lines[i]
    if not head_done:
        if ln.startswith('last_ack:'):
            out.append('last_ack: APP-022')
            i += 1
            continue
        if ln.startswith('更新时间:'):
            out.append('更新时间: %s' % now)
            i += 1
            continue
        if ln.startswith('当前任务:'):
            out.append('当前任务: %s' % new_task)
            i += 1
            continue
        if ln.startswith('阻塞 / 待用户决定:'):
            out.append(new_block)
            i += 1
            continue
        if ln.strip() == '## 最近更新':
            out.append(ln)
            # 🔴 「最近更新」块首插入新条目，块内保持 ≤15 行
            out.append('- 20:55 §55 🔴 **APP-022 已完成（仅接口预留，未集成）**：'
                       '事件**按需加长**（`spk=None` ⇒ 仍是 5 元组 ⇒ MT 的 `len(e)==5` 断言继续成立）')
            out.append('- 20:55 §55 🔴🔴 **TTS-017① `cp_prefill` 已同步到 NPU**：'
                       '形状 `[1,2,1024]`；失败**回退 CPU + 记日志 + 返回 False**（不静默降级）')
            out.append('- 20:55 §55 ✅ GUI 预留两项：「跟随说话人（克隆）」**（默认仍是预设 A）**'
                       '+「显示说话人」**（默认关闭）**；说话人表**只在内存**、会话结束清空')
            out.append('- 20:55 §55 ✅ `app079` **REAL 15/15 · BUG 0/2**；'
                       '客户包 **6/6 synced**（骨架等价校验后升级基底 + 逐字校验 + `py_compile` OK）')
            out.append('- 20:55 §55 ✅ **已交付 v1.5 zip 干净**（13 984 entries / babelvox speakers 0 / '
                       'scipy 测试音频 0 / 仅 `preset_A.wav` 1 个 wav）；⚠️ **散包目录仍有 8 + 22 残留**')
            recent_done = True
            i += 1
            continue
        if not ln.startswith('#') and ln.strip():
            head_done = True
    out.append(ln)
    i += 1

text2 = '\n'.join(out)

# 🔴 「最近更新」块裁剪到 ≤15 行
blocks = text2.split('\n## 最近更新\n')
if len(blocks) >= 2:
    head, rest = blocks[0], '\n## 最近更新\n'.join(blocks[1:])
    lines2 = rest.split('\n')
    # 找到块结束（下一个 '## ' 开头）
    end = len(lines2)
    for idx, l in enumerate(lines2):
        if l.startswith('## ') and idx > 0:
            end = idx
            break
    head_lines = lines2[:end]
    tail_lines = lines2[end:]
    kept = [l for l in head_lines if l.strip().startswith('- ')]
    others = [l for l in head_lines if not l.strip().startswith('- ')]
    kept = kept[:15]
    text2 = head + '\n## 最近更新\n' + '\n'.join(others + kept + tail_lines)

data = text2.replace('\r\n', '\n')
if crlf:
    data = data.replace('\n', '\r\n')
with open(STATUS, 'wb') as f:
    f.write(data.encode('utf-8'))

print('STATUS updated, bytes =', os.path.getsize(STATUS))
