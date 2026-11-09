"""APP-089/090/091/092：写 `status/app/STATUS_APP.md` 的 **§161**（定点写入）。

🔴 纪律（APP-052④ + 用户级「STATUS 定点写入」铁律）：
  * **只追加** `## §N` 章节，**不回头改旧章节**。
  * 旧正文错了就在新章节里写「撤回 §x」。
  * 头部 `last_ack` 更新为**已执行完的最大 APP 编号**（APP-092）。
  * 「更新时间」用 **`Get-Date` 实测值**（禁止推算）。
  * **限额 ≤40000 B / ≤300 行** ⇒ 先按 APP-052④ **压缩**（旧章节整块逐字归档）。
  * 写前自检：唯一命中断言 + 反向还原 == 旧全文 + 旧正文逐字未变 + 章节数不减 + LF 未破。
  * **临时文件 → 原子替换** → 写后**逐字节复核**。

用法：python app371_app089_write_status.py --payload <payload.json>
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')
MAX_B = 40000
MAX_L = 300


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get_date() -> str:
    """🔴 用 `Get-Date` 实测（禁止推算）⇒ 走 PowerShell。"""
    r = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
        capture_output=True, text=True)
    out = (r.stdout or '').strip()
    if not out:
        raise RuntimeError('Get-Date failed: %s' % (r.stderr or '')[:200])
    return out


def split_sections(t: str):
    """返回 (pre, [(header, body), ...])。"""
    parts = re.split(r'(?m)^(## §[^\n]*)$', t)
    pre = parts[0]
    secs = []
    for i in range(1, len(parts), 2):
        secs.append((parts[i], parts[i + 1]))
    return pre, secs


def check(name, ok, detail=''):
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', required=True)
    args = ap.parse_args()
    payload = json.load(open(args.payload, encoding='utf-8'))

    raw = open(STATUS, 'rb').read()
    old = raw.decode('utf-8')
    old_sha = sha_bytes(raw)
    pre, secs = split_sections(old)
    n_sec_old = len(secs)
    print('开工：bytes=%d lines=%d sections=%d sha=%s'
          % (len(raw), raw.count(b'\n') + 1, n_sec_old, old_sha[:16]))

    ok = True
    ok &= check('旧文件 LF 行尾（无 CRLF）', b'\r\n' not in raw)

    # ── ① 归档（逐字整块）⇒ 腾出空间 ──
    # 🔴 归档顺序：**从最新往旧**（§160 → §159 → …），**循环归档到够为止**。
    #    （本轮 §161 正文 5152 B ⇒ 需腾 ~5.3 KB ⇒ 单归档 §160（10985 B）
    #      之后仍超限（归档件位置换行反而涨）⇒ 必须再归档 §159。）
    arch_path = None
    new_secs = list(secs)
    arch_paths = []
    arch_map = {}
    ARCHIVABLE = ('## §160 ', '## §159 ', '## §158 ', '## §150 ',
                  '## §149 ', '## §142 ', '## §141 ')
    need = len(raw) + len(payload.get('sec_body', '').encode('utf-8')) - MAX_B
    while need > 0:
        idx = None
        for pref in ARCHIVABLE:
            for i, (h, _b) in enumerate(new_secs):
                if h.startswith(pref):
                    idx = i
                    break
            if idx is not None:
                break
        if idx is None:
            print('  [FAIL] 没有更多可归档章节 ⇒ 无法腾空间')
            return 2
        hdr, body = new_secs[idx]
        block = hdr + body
        os.makedirs(ARCH, exist_ok=True)
        num = hdr.split('§')[1].split(' ')[0]
        ap_path = os.path.join(ARCH, 'STATUS_APP_sec%s_20261110.md' % num)
        with open(ap_path, 'wb') as f:
            f.write(block.encode('utf-8'))
        # 归档件逐字复核
        ab = open(ap_path, 'rb').read()
        ok &= check('归档件逐字等于原 §%s 整块' % num, ab == block.encode('utf-8'),
                    '(sha %s)' % sha_bytes(ab)[:16])
        # 正文换成「已归档」速查行（**正文整块逐字在归档件里** ⇒ 不丢信息）
        # 🔴 口径（与 §159 既有格式**一致**）：正文**换成**速查行，
        #    **不是**「正文 + 速查行」—— 后者不省空间 ⇒ 归档等于白做。
        #    速查行必须自带：归档路径 + 字节数 + 块 SHA256（可自证逐字一致）。
        note = ('\n> 🔴 **本节正文已整块逐字归档** ⇒ '
                '`status/archive/STATUS_APP_sec%s_20261110.md`'
                '（%d B／块 SHA256 `%s`）。\n'
                % (num, len(ab), sha_bytes(ab)))
        new_secs[idx] = (hdr, note)
        arch_paths.append(ap_path)
        arch_map[hdr] = body
        need -= len(body) - len(note)
        print('  归档 §%s ⇒ %s (%d B，腾出 %d B)' % (num, ap_path, len(ab),
                                                       len(body) - len(note)))
    if arch_paths:
        arch_path = arch_paths[0]

    # ── ② 追加 §161 ──
    sec_body = payload['sec_body']
    new_pre = pre
    # 头部三行定点替换
    lines = new_pre.split('\n')
    new_lines = []
    for ln in lines:
        if ln.startswith('last_ack:'):
            new_lines.append('last_ack: %s' % payload['last_ack'])
        elif ln.startswith('更新时间:'):
            new_lines.append('更新时间: %s' % payload['updated'])
        elif ln.startswith('当前任务:'):
            new_lines.append('当前任务: %s' % payload['current_task'])
        elif ln.startswith('阻塞 / 待用户决定:'):
            new_lines.append('阻塞 / 待用户决定: %s' % payload['blocked'])
        else:
            new_lines.append(ln)
    new_pre = '\n'.join(new_lines)
    # 「最近更新」追加一行
    anchor = '## 最近更新\n'
    if anchor not in new_pre:
        print('  [FAIL] 找不到「## 最近更新」锚点')
        return 2
    new_pre = new_pre.replace(anchor, anchor + payload['recent_line'] + '\n', 1)

    new_text = new_pre + ''.join(h + b for h, b in new_secs) + sec_body
    nb = new_text.encode('utf-8')

    # ── ③ 写前自检 ──
    ok &= check('旧正文逐字未变（归档块之外）',
                _old_bodies_intact(old, new_text, secs))
    _, new_secs2 = split_sections(new_text)
    ok &= check('章节数不减', len(new_secs2) >= n_sec_old,
                '(%d → %d)' % (n_sec_old, len(new_secs2)))
    ok &= check('LF 未破', b'\r\n' not in nb)
    ok &= check('≤40000 B', len(nb) <= MAX_B, '(%d)' % len(nb))
    ok &= check('≤300 行', nb.count(b'\n') + 1 <= MAX_L,
                '(%d)' % (nb.count(b'\n') + 1))
    # 反向还原：把 §161 去掉、头部改回 ⇒ 应等于旧全文
    back = _reverse(new_text, old, arch_map, payload.get('recent_line', ''))
    ok &= check('反向还原 == 旧全文', back == old)

    if not ok:
        print('  🔴 写前自检未全过 ⇒ **STATUS 未落盘**')
        return 3

    # ── ④ 临时文件 → 原子替换 ──
    tmp = STATUS + '.tmp_app161'
    with open(tmp, 'wb') as f:
        f.write(nb)
    os.replace(tmp, STATUS)

    # ── ⑤ 写后逐字节复核 ──
    after = open(STATUS, 'rb').read()
    ok &= check('写后逐字节等于预期', after == nb,
                '(sha %s)' % sha_bytes(after)[:16])
    ok &= check('写后 ≤40000 B / ≤300 行',
                len(after) <= MAX_B and after.count(b'\n') + 1 <= MAX_L,
                '(%d B / %d 行)' % (len(after), after.count(b'\n') + 1))
    print('写后：bytes=%d lines=%d sha=%s'
          % (len(after), after.count(b'\n') + 1, sha_bytes(after)[:16]))
    if arch_path:
        print('归档件：%s' % arch_path)
    print('RESULT=%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 3


def _old_bodies_intact(old: str, new: str, secs) -> bool:
    """除被归档的 §160 外，每个旧章节的正文必须逐字出现在新文件里。"""
    for h, b in secs:
        if h.startswith('## §160 '):
            continue
        if (h + b) not in new:
            print('    [FAIL] 旧章节缺失：%s' % h[:40])
            return False
    return True


def _reverse(new: str, old: str, arch_map: dict, recent_line: str) -> str:
    """把新文件反向还原成旧全文 ⇒ 用于不变量校验。

    🔴 **旧版是空壳**（只 `pass`，永远还原不出来 ⇒ 该检查形同虚设）。
       本版真正实现**可逆变换**的逆：

       new = new_pre + 拼接(新章节) + sec_body
       old = old_pre + 拼接(旧章节)

       逆步骤：
       ① 去掉尾部 `sec_body`（即**新增的那一节**）；
       ② 把**被归档**的章节正文从**归档件**逐字还原
          （`arch_map`：header → 原正文）；
       ③ 头部：`new_pre` 里去掉插入的 `recent_line`，
          并把 4 个被定点替换的头部行还原成 `old` 的值
          ⇒ 应逐字等于 `old_pre`。

    ⇒ 全部还原成功 ⇒ `result == old` ⇒ 证明本次写入**只**做了
       「追加一节 + 改 4 个头部行 + 插入 1 行最近更新 + 归档替换」
       这些**已声明**的改动，**没有别的副作用**。

    ⚠️ **不能写死节号**（旧版写死 `'## §161'`，而实际新增的可能是 §162/§163…）
       ⇒ 改为「**最后一个** `## §` 开头」定位 ⇒ 与节号无关。
    """
    # ① 去掉尾部**新增的那一节**（= 最后一个 `## §` 段）
    #    ⚠️ 切点要在**分隔用的换行之前**：旧文件最后一节以 `\n` 结尾，
    #    新文件在它后面接 `\n## §163…` ⇒ 若切到 `\n## §` 的换行**之后**，
    #    会多留一个 `\n`（实测多 1 B ⇒ 校验失败）。
    idx = new.rfind('\n## §')
    if idx < 0:
        return new
    rev = new[:idx]
    # ② 被归档章节：正文还原
    if arch_map:
        for hdr, orig_body in arch_map.items():
            j = rev.find(hdr)
            if j < 0:
                return rev + '<<MISSING_ARCH:%s>>' % hdr[:30]
            k = rev.find('\n## §', j + 1)
            tail = rev[k:] if k >= 0 else ''
            rev = rev[:j] + hdr + orig_body + tail
    # ③ 头部还原
    old_pre, _old_secs = split_sections(old)
    new_pre, _new_secs = split_sections(rev)
    if recent_line and recent_line in new_pre:
        new_pre = new_pre.replace(recent_line + '\n', '', 1)
    for k in ('last_ack', '更新时间', '当前任务', '阻塞 / 待用户决定'):
        old_line = None
        for ln in old_pre.split('\n'):
            if ln.startswith(k + ':'):
                old_line = ln
                break
        if old_line is None:
            continue
        lines = new_pre.split('\n')
        for j, ln in enumerate(lines):
            if ln.startswith(k + ':'):
                lines[j] = old_line
                break
        new_pre = '\n'.join(lines)
    return new_pre + rev[len(split_sections(rev)[0]):]


if __name__ == '__main__':
    raise SystemExit(main())
