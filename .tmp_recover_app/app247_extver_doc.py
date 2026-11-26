"""§247 打包前：修掉包内「EXT v0.4.22」的过时文案（实际 0.4.23）。

事实依据：
  ext/extension/manifest.json  -> version = "0.4.23"
  package_profile.json         -> ext_version = "0.4.23"
  release.json                 -> ext.version = "0.4.23"（但 v1.2_changes 里写 0.4.22）

⇒ 包内文档自相矛盾，reviewer 从 zip 复核必然看到 ⇒ 定点修 4 处（不动代码注释里的
   历史版本标注 ext/bridge/engine_runtime.py）。

纪律：备份到包外（包内白名单禁 *.bak*）＋锚点唯一断言 ＋ 行尾必须 LF 不变 ＋
      未改行逐字保留 ＋ 写后重新读盘复核。
"""
import hashlib
import io
import os
import shutil
import time

CAND = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate'
BAKDIR = r'C:\Users\Trekker-PTL\shared\pkg_baks_20261126'

REPS = [
    # (相对路径, 旧串, 新串)
    ('README_zh.md',
     '### 4. EXT 升级到 v0.4.22\n\n'
     '- 桥接侧识别模型查找顺序与本包一致（先 Hy-MT3，回退 Hy-MT2）。\n',
     '### 4. EXT 升级到 v0.4.23\n\n'
     '- 桥接侧识别模型查找顺序与本包一致（先 Hy-MT3，回退 Hy-MT2）。\n'
     '- 桥接侧 ASR 按包内模型族自动适配（本包为 Qwen3-ASR 0.6B；'
     '可用 `EXT_ASR_FAMILY=06b|r2t2` 强制）。\n'),

    ('README_en.md',
     '### 4. EXT upgraded to v0.4.22\n\n'
     '- The bridge looks up the translation model in the same order as this package\n'
     '  (Hy-MT3 first, Hy-MT2 as fallback).\n',
     '### 4. EXT upgraded to v0.4.23\n\n'
     '- The bridge looks up the translation model in the same order as this package\n'
     '  (Hy-MT3 first, Hy-MT2 as fallback).\n'
     '- The bridge picks the ASR family present in this package (Qwen3-ASR 0.6B here;\n'
     '  force it with `EXT_ASR_FAMILY=06b|r2t2`).\n'),

    ('app/MANIFEST.json',
     'EXT v0.4.22；',
     'EXT v0.4.23；'),

    ('release.json',
     '"EXT 升级到 v0.4.22（桥接侧识别模型查找顺序与本包一致）",',
     '"EXT 升级到 v0.4.23（桥接侧 ASR 按包内模型族自动适配 Qwen3-ASR 0.6B，APP-149）",'),
]

fail = []


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    os.makedirs(BAKDIR, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    for rel, old, new in REPS:
        p = os.path.join(CAND, rel.replace('/', os.sep))
        raw = open(p, 'rb').read()
        if raw.count(b'\r\n'):
            fail.append('%s 含 CRLF（预期 LF）' % rel)
            continue
        src = raw.decode('utf-8')

        # 幂等：已是新文案 ⇒ 跳过
        if new in src and old not in src:
            print('SKIP %-18s 已是新文案' % rel)
            continue
        if src.count(old) != 1:
            fail.append('%s 锚点命中 %d 次' % (rel, src.count(old)))
            continue

        bak = os.path.join(BAKDIR, os.path.basename(p) + '.bak_app247_extver')
        if not os.path.isfile(bak):
            shutil.copy2(p, bak)
        bak_ok = (open(bak, 'rb').read() == raw)

        out = src.replace(old, new, 1)
        ob = out.encode('utf-8')
        # 写前不变量
        inv = [
            ('备份逐字节等于原文', bak_ok),
            ('行尾仍全 LF', ob.count(b'\r\n') == 0),
            ('行数变化 = 预期', out.count('\n') - src.count('\n') == new.count('\n') - old.count('\n')),
            ('锚点新串在位', out.count(new) == 1),
            ('旧串已消失', out.count(old) == 0),
            ('字节差 = 预期',
             len(ob) - len(raw) == len(new.encode('utf-8')) - len(old.encode('utf-8'))),
        ]
        bad = [n for n, ok in inv if not ok]
        if bad:
            fail.append('%s 写前不变量不满足：%s' % (rel, bad))
            print('FAIL %-18s %s' % (rel, bad))
            continue

        tmp = p + '.tmp_app247'
        with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        os.replace(tmp, p)

        # 写后复核（重新读盘）
        chk = open(p, 'rb').read()
        post = [
            ('落盘逐字节等于预期', chk == ob),
            ('sha 变了', sha(chk) != sha(raw)),
            ('行尾仍全 LF', chk.count(b'\r\n') == 0),
        ]
        bad2 = [n for n, ok in post if not ok]
        if bad2:
            fail.append('%s 写后复核失败：%s' % (rel, bad2))
            print('FAIL(post) %-14s %s' % (rel, bad2))
            continue
        print('OK   %-18s %d -> %d B (%+d)  lines %d -> %d'
              % (rel, len(raw), len(chk), len(chk) - len(raw),
                 src.count('\n'), out.count('\n')))

    print('\n结果：%s' % ('全部通过' if not fail else '有 %d 项失败' % len(fail)))
    for f in fail:
        print('  -', f)
    return 0 if not fail else 1


if __name__ == '__main__':
    raise SystemExit(main())
